"""The UI's server (songcharter.ui.server) on an ephemeral port: the Host and Origin guards, the CSP on every response,
static files by exact name, uploads, one job at a time, the SSE stream, cancel, the Windows self-check and its
fallback, and `songcharter ui` itself as a process. Jobs run a stand-in chart program (STANDIN); Windows' curl.exe
is a stand-in function. Nothing here needs Windows or a model."""
import hashlib
import http.client
import json
import os
import signal
import socket
import subprocess
import sys
import time
import urllib.parse
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

import songcharter
from songcharter import audio as A
from songcharter import device, proc
from songcharter.ui import jobs as J
from songcharter.ui import server as S

STANDIN = r'''
import json, os, subprocess, sys, time
mode, out = sys.argv[1], sys.argv[2]

def ev(**e):
    sys.stderr.write("@@songcharter " + json.dumps(e) + "\n")
    sys.stderr.flush()

ev(event="plan", stages=["decode", "guitar"])
ev(event="stage_start", stage="decode", index=1, count=2, detail="x")
if mode == "slow":
    time.sleep(1.0)
ev(event="stage_end", stage="decode", seconds=0.1, cached=True, detail="x")
if mode == "hang":
    child = subprocess.Popen(["sleep", "60"])
    ev(event="take", index=1, count=4, seed=20260609, pids=[os.getpid(), child.pid])
    time.sleep(60)
ev(event="result", ok=True, exit=0, folder=out, work="/w", preview=None, summary="gate: OK")
'''
DOCTOR = {"device": {"chosen": "cpu", "reason": "no NVIDIA GPU found"}, "gpu": None, "guitar_device": "cpu",
          "guitar_reason": "no GPU", "notes": ["CPU mode: no NVIDIA GPU found"], "ok": True,
          "cpu": {"logical": 4, "threads_default": 3}, "problems": [], "components": {}}
SECURITY = {"Content-Security-Policy": S.CSP, "X-Content-Type-Options": "nosniff", "Referrer-Policy": "no-referrer"}


def call(port, method, path, body=None, headers=None, host=None, timeout=15, connect="127.0.0.1"):
    conn = http.client.HTTPConnection(connect, port, timeout=timeout)
    try:
        conn.request(method, path, body=body, headers={"Host": host or f"127.0.0.1:{port}", **(headers or {})})
        r = conn.getresponse()
        return r.status, r.headers, r.read()
    finally:
        conn.close()


def guarded(port, host="127.0.0.1"):
    return {"X-Songcharter": "1", "Origin": f"http://{host}:{port}"}


def raw(port, data: bytes) -> bytes:
    with socket.create_connection(("127.0.0.1", port), timeout=10) as s:
        s.sendall(data)
        out = b""
        while chunk := s.recv(65536):
            out += chunk
    return out


def secure(headers) -> bool:
    return all(headers.get(k) == v for k, v in SECURITY.items()) and not any(
        k.lower().startswith("access-control-") for k in headers.keys())


@pytest.fixture
def served(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    (home / "doctor.json").write_text(json.dumps(DOCTOR), encoding="utf-8")
    script = tmp_path / "standin.py"
    script.write_text(STANDIN, encoding="utf-8")
    ctx = SimpleNamespace(mode="hang", threads=[], lines=[], home=home)

    def command(song, out, options, threads):
        ctx.threads.append(threads)
        return [sys.executable, str(script), ctx.mode, str(out)]

    app = S.App(home, jobs=J.Jobs(home, command=command), log=S.Log(None, console=ctx.lines.append),
                report=lambda: pytest.fail("doctor.json is there: no quick report"))
    servers = S.bind(app, [0])
    ctx.app, ctx.port = app, servers[0].server_address[1]
    yield ctx
    app.jobs.shutdown()
    for s in servers:
        s.shutdown()
        s.server_close()


def song(path: Path, seconds: float = 1.0) -> bytes:
    t = np.arange(int(seconds * A.SAMPLE_RATE)) / A.SAMPLE_RATE
    y = 0.2 * np.sin(2 * np.pi * 440 * t)
    A.write_wav(np.stack([y, y]).astype(np.float32), path)
    return path.read_bytes()


def upload(ctx, data: bytes, name: str) -> tuple[int, dict]:
    status, _, body = call(ctx.port, "POST", "/api/upload", data,
                           {**guarded(ctx.port), "X-Filename": urllib.parse.quote(name)})
    return status, json.loads(body)


def sse(port, last_id=None, timeout=15) -> list[tuple[int | None, dict | str]]:
    """The stream's items until it closes: (id, event) for events, (None, comment) for comments."""
    headers = {"Last-Event-ID": str(last_id)} if last_id is not None else {}
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=timeout)
    conn.request("GET", "/api/jobs/current/events", headers={"Host": f"127.0.0.1:{port}", **headers})
    r = conn.getresponse()
    assert r.status == 200 and r.headers["Content-Type"].startswith("text/event-stream") and secure(r.headers)
    items, block = [], []
    for line in r:
        line = line.decode("utf-8").rstrip("\n")
        if line:
            block.append(line)
            continue
        ident = next((int(x[4:]) for x in block if x.startswith("id: ")), None)
        data = "".join(x[6:] for x in block if x.startswith("data: "))
        items.append((ident, json.loads(data)) if data else (None, "\n".join(block)))
        block = []
    conn.close()
    return items


def wait_state(ctx, state, timeout=20):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        job = ctx.app.jobs.current
        if job is not None and job.state == state:
            return job
        time.sleep(0.02)
    raise AssertionError(f"the job is {ctx.app.jobs.current and ctx.app.jobs.current.state}, not {state}")


# ------------------------------------------------------------------------------------------------ the guards

def test_the_host_must_be_ours(served):
    port = served.port
    status, headers, body = call(port, "GET", "/api/hello", host="evil.example")
    assert status == 403 and secure(headers)
    assert call(port, "GET", "/api/hello", host=f"evil.example:{port}")[0] == 403
    assert call(port, "GET", "/", host=f"127.0.0.1:{port + 1}")[0] == 403
    assert raw(port, b"GET /api/hello HTTP/1.0\r\n\r\n").startswith(b"HTTP/1.0 403")   # no Host at all
    for host in (f"127.0.0.1:{port}", f"localhost:{port}", f"LOCALHOST:{port}"):
        status, headers, body = call(port, "GET", "/api/hello", host=host)
        hello = json.loads(body)
        assert status == 200 and secure(headers) and hello["app"] == "songcharter"
        assert hello["token"] == served.app.token and len(hello["token"]) == 16 and hello["version"]


def test_a_post_needs_the_header_and_our_origin(served):
    port = served.port
    for headers in ({}, {"X-Songcharter": "1"}, {"Origin": f"http://127.0.0.1:{port}"},
                    {"X-Songcharter": "yes", "Origin": f"http://127.0.0.1:{port}"},
                    {"X-Songcharter": "1", "Origin": "http://evil.example"},
                    {"X-Songcharter": "1", "Origin": f"https://127.0.0.1:{port}"},
                    {"X-Songcharter": "1", "Origin": "null"}):
        for path in ("/api/upload", "/api/jobs", "/api/jobs/current/cancel"):
            status, h, _ = call(port, "POST", path, b"{}", {"X-Filename": "a.mp3", **headers})
            assert status == 403 and secure(h), (path, headers)
    # a CORS preflight is refused, and nothing ever grants CORS
    status, h, _ = call(port, "OPTIONS", "/api/jobs", None, {"Origin": "http://evil.example",
                                                             "Access-Control-Request-Method": "POST",
                                                             "Access-Control-Request-Headers": "x-songcharter"})
    assert status == 403 and secure(h)
    assert call(port, "PUT", "/api/jobs", b"{}", guarded(port))[0] == 405
    assert call(port, "POST", "/api/jobs/current/cancel", b"", guarded(port, "localhost"))[0] == 409   # passed
    assert served.app.jobs.current is None


def test_the_csp_is_on_every_response(served):
    port = served.port
    got = [call(port, "GET", p) for p in ("/", "/app.js", "/app.css", "/api/hello", "/api/status", "/nope",
                                          "/api/jobs/current")]
    got.append(call(port, "GET", "/", host="evil.example"))
    got.append(call(port, "POST", "/api/upload", b"x", {**guarded(port), "X-Filename": "a.txt"}))
    got.append(call(port, "POST", "/api/jobs", b"not json", guarded(port)))
    assert [g[0] for g in got] == [200, 200, 200, 200, 200, 404, 404, 403, 415, 400]
    assert all(secure(h) for _, h, _ in got)
    head = raw(port, b"GET /api/hello HTTP/1.1\r\nHost: 127.0.0.1:%d\r\n\r\n" % port).split(b"\r\n\r\n")[0]
    assert b"Content-Security-Policy: " + S.CSP.encode() in head.split(b"\r\n")
    assert raw(port, b"BOGUS\r\n\r\n").startswith(b"HTTP/1.0 400")   # the base class's own errors carry it too
    assert b"Content-Security-Policy" in raw(port, b"BOGUS\r\n\r\n")


def test_static_files_by_exact_name_only(served):
    port = served.port
    files = S.static_files()
    assert sorted(files) == ["app.css", "app.js", "index.html"]
    status, h, body = call(port, "GET", "/")
    assert status == 200 and h["Content-Type"] == "text/html; charset=utf-8" and body == files["index.html"]
    assert call(port, "GET", "/index.html")[2] == files["index.html"]
    status, h, body = call(port, "GET", "/app.js?v=1")
    assert status == 200 and h["Content-Type"] == "text/javascript; charset=utf-8" and body == files["app.js"]
    for path in ("/../server.py", "/..%2fserver.py", "/%2e%2e/server.py", "/static/app.js", "/app.js/",
                 "/./app.js", "/server.py", "/__init__.py", "/static", "/ui/static/app.js",
                 "/..\\server.py", "/../../../etc/passwd", "/app.js%00"):
        assert call(port, "GET", path)[0] == 404, path
    assert call(port, "GET", "//app.js")[2] == files["app.js"]   # http.server makes a leading // one /
    # the page itself loads nothing from elsewhere and has no inline script or style
    html = files["index.html"].decode()
    assert "http" not in html.replace("http-equiv", "") and "<style" not in html and " style=" not in html
    assert "<script src=\"/app.js\" defer></script>" in html and html.count("<script") == 1


# ------------------------------------------------------------------------------------------------ the API

def test_status_gives_the_doctor_summary_and_the_defaults(served, tmp_path):
    status, _, body = call(served.port, "GET", "/api/status")
    st = json.loads(body)
    assert status == 200 and st["device"] == DOCTOR["device"] and st["guitar_device"] == "cpu"
    assert st["gpu"] is None and st["notes"] == DOCTOR["notes"] and st["ok"] is True and st["job"] is None
    assert st["source"] == "doctor.json" and st["defaults"]["threads_default"] == 3
    assert st["defaults"]["instruments"] == ["guitar", "bass", "drums"] and st["defaults"]["levels"] == ["expert"]
    # without doctor.json: a quick report, made once
    made = []
    app = S.App(tmp_path, report=lambda: made.append(1) or {**DOCTOR, "notes": ["quick"]})
    assert app.status()["notes"] == ["quick"] and app.status()["source"] == "quick check" and made == [1]
    broken = S.App(tmp_path, report=lambda: 1 / 0)
    assert broken.status()["error"] == "ZeroDivisionError: division by zero" and broken.auto_device() is None


def test_uploads(served, monkeypatch):
    ctx, port = served, served.port
    for name in ("notes.txt", "song", "song.mp3.exe", ""):
        status, body = upload(ctx, b"hello", name)
        assert status == 415 and "not a song file" in body["error"], name
    data = song(ctx.home / "tmp.wav")
    status, body = upload(ctx, data, "C:\\Music\\Jörg's Söng: 1/2.WAV")
    key = hashlib.sha256(data).hexdigest()
    assert status == 200, body
    assert set(body) == {"id", "name", "bytes", "tags", "origin"} and body["id"] == key[:16]
    assert body["bytes"] == len(data) and body["name"] == "2.WAV"   # a path in the name: only its last part
    folder = ctx.home / "uploads" / key[:16]
    assert sorted(p.name for p in folder.iterdir()) == ["2.wav", "upload.json"]
    assert (folder / "2.wav").read_bytes() == data
    record = json.loads((folder / "upload.json").read_text(encoding="utf-8"))
    assert record["sha256"] == key and record["file"] == "2.wav"
    status, body = upload(ctx, data, "Jörg's Söng.wav")
    assert status == 200 and body["name"] == "Jörg's Söng.wav" and body["id"] == key[:16]
    assert (folder / "Jorg's Song.wav").is_file()   # cache.safe_name of the stem
    assert body["tags"]["name"] == "Jörg's Söng" and body["origin"]["name"] == "file name"   # the name as dropped
    assert body["tags"]["artist"] == "Unknown" and body["origin"]["artist"] == "default"
    assert S.read_upload(ctx.home, key[:16])["path"] == str(folder / "Jorg's Song.wav")
    for bad in ("../" + key[:14], key[:15], key[:16].upper(), None, 7):
        assert S.read_upload(ctx.home, bad) is None
    assert not list((ctx.home / "uploads").glob(".incoming-*"))
    # too big: 413 before a byte is read; no length: 411
    monkeypatch.setattr(S, "MAX_UPLOAD", 10)
    status, body = upload(ctx, b"x" * 11, "big.flac")
    assert status == 413 and "over the limit" in body["error"]
    req = (f"POST /api/upload HTTP/1.0\r\nHost: 127.0.0.1:{port}\r\nX-Songcharter: 1\r\n"
           f"Origin: http://127.0.0.1:{port}\r\nX-Filename: a.mp3\r\n\r\n").encode()
    assert raw(port, req).startswith(b"HTTP/1.0 411")
    # a body cut short is refused and leaves nothing behind
    req = (f"POST /api/upload HTTP/1.0\r\nHost: 127.0.0.1:{port}\r\nX-Songcharter: 1\r\nOrigin: http://127.0.0.1:"
           f"{port}\r\nX-Filename: a.mp3\r\nContent-Length: 9\r\n\r\nabc").encode()
    with socket.create_connection(("127.0.0.1", port), timeout=10) as s:
        s.sendall(req)
        s.shutdown(socket.SHUT_WR)
        answer = b""
        while chunk := s.recv(65536):
            answer += chunk
    assert answer.startswith(b"HTTP/1.0 400") and b"stopped after 3 of 9 bytes" in answer
    assert not list((ctx.home / "uploads").glob(".incoming-*"))
    status, body = upload(ctx, b"x", "x.mp3")
    assert status == 200 and body["origin"]["name"] == "file name"   # ffmpeg cannot read it: its chart says so
    status, _, body = call(port, "POST", "/api/upload", b"x", {**guarded(port), "X-Filename": "%FF.mp3"})
    assert status == 400 and "percent-encoded UTF-8" in json.loads(body)["error"]


def test_uploads_older_than_a_week_go(tmp_path):
    uploads = tmp_path / "uploads"
    for name, age in (("a" * 16, 8), ("b" * 16, 6), (".incoming-x.part", 9)):
        p = uploads / name
        if name.startswith("."):
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("x")
        else:
            p.mkdir(parents=True)
            (p / "song.mp3").write_text("x")
            os.utime(p / "song.mp3", (time.time() - age * 86400,) * 2)
        os.utime(p, (time.time() - age * 86400,) * 2)
    assert sorted(S.prune_uploads(tmp_path)) == [".incoming-x.part", "a" * 16]
    assert [p.name for p in uploads.iterdir()] == ["b" * 16]
    assert S.prune_uploads(tmp_path / "nowhere") == []


def test_one_job_at_a_time_then_cancel(served):
    ctx, port = served, served.port
    status, up = upload(ctx, song(ctx.home / "s.wav"), "Song.wav")
    assert status == 200
    status, _, body = call(port, "POST", "/api/jobs", json.dumps({"upload": up["id"], "options": {}}).encode(),
                           guarded(port))
    assert status == 202 and json.loads(body)["job"] == ctx.app.jobs.current.id
    assert ctx.threads == [device.default_threads()]   # doctor's device is the CPU
    job = ctx.app.jobs.current
    for options, code in (({}, 409), ({"takes": 2}, 400)):
        status, _, body = call(port, "POST", "/api/jobs", json.dumps({"upload": up["id"], "options": options})
                               .encode(), guarded(port))
        assert status == code, body
    assert "takes is 1, or 3 or more" in json.loads(body)["error"]
    for body in (b'{"upload": "0000000000000000"}', b'{"options": {}}', b"[]", b"{"):
        assert call(port, "POST", "/api/jobs", body, guarded(port))[0] == 400, body
    status, _, body = call(port, "GET", "/api/jobs/current")
    snap = json.loads(body)
    assert status == 200 and snap["state"] == "running" and snap["job"] == job.id
    assert json.loads(call(port, "GET", "/api/status")[2])["job"]["state"] == "running"
    deadline = time.monotonic() + 15
    while not any(e["event"] == "take" for e in job.events) and time.monotonic() < deadline:
        time.sleep(0.02)
    pids = next(e for e in job.events if e["event"] == "take")["pids"]
    status, _, body = call(port, "POST", "/api/jobs/current/cancel", b"", guarded(port))
    assert status == 200 and json.loads(body) == {"job": job.id, "state": "cancelled"}
    assert not any(proc.alive(p) for p in pids)
    assert call(port, "POST", "/api/jobs/current/cancel", b"", guarded(port))[0] == 409
    assert json.loads(call(port, "GET", "/api/jobs/current")[2])["state"] == "cancelled"
    # and a new one may start
    ctx.mode = "ok"
    status, _, _ = call(port, "POST", "/api/jobs", json.dumps({"upload": up["id"], "options": {"device": "cuda"}})
                        .encode(), guarded(port))
    assert status == 202 and wait_state(ctx, "done") and ctx.threads[-1] is None


def test_sse_replays_to_a_late_client_and_streams_to_an_early_one(served, monkeypatch):
    ctx, port = served, served.port
    assert call(port, "GET", "/api/jobs/current/events")[0] == 404   # no job yet
    _, up = upload(ctx, song(ctx.home / "s.wav"), "Song.wav")
    ctx.mode = "ok"
    assert call(port, "POST", "/api/jobs", json.dumps({"upload": up["id"]}).encode(), guarded(port))[0] == 202
    job = wait_state(ctx, "done")
    items = sse(port)
    assert [i for i, _ in items] == list(range(len(job.events))) == [0, 1, 2, 3]
    assert [e["event"] for _, e in items] == ["plan", "stage_start", "stage_end", "result"]
    assert items == [(n, e) for n, e in enumerate(job.events)]
    # a stream that closed means a final state (the job's process has exited), so the next job may start at once
    ctx.mode = "ok"
    for _ in range(3):
        assert call(port, "POST", "/api/jobs", json.dumps({"upload": up["id"]}).encode(), guarded(port))[0] == 202
        assert sse(port)[-1][1]["event"] == "result" and ctx.app.jobs.current.state == "done"
    assert [e["event"] for _, e in sse(port, last_id=1)] == ["stage_end", "result"]   # resumed after id 1
    # an early client gets the events as they come, a keepalive comment while it waits, and the end
    monkeypatch.setattr(S, "KEEPALIVE_S", 0.2)
    ctx.mode = "slow"
    assert call(port, "POST", "/api/jobs", json.dumps({"upload": up["id"]}).encode(), guarded(port))[0] == 202
    items = sse(port)
    kinds = [e["event"] if i is not None else e for i, e in items]
    assert kinds[:2] == ["plan", "stage_start"] and kinds[-2:] == ["stage_end", "result"]
    assert ": keepalive" in kinds[2:-2] and set(kinds[2:-2]) == {": keepalive"}   # while the stage ran
    # a cancelled job's stream ends with "cancelled"
    assert ctx.app.jobs.current.state == "done"
    ctx.mode = "hang"
    assert call(port, "POST", "/api/jobs", json.dumps({"upload": up["id"]}).encode(), guarded(port))[0] == 202
    ctx.app.jobs.cancel()
    assert sse(port)[-1][1]["event"] == "cancelled"


# ------------------------------------------------------------------------------------------------ startup

def free_ports(n: int) -> list[int]:
    socks = [socket.socket() for _ in range(n)]
    for s in socks:
        s.bind(("127.0.0.1", 0))
    ports = [s.getsockname()[1] for s in socks]
    for s in socks:
        s.close()
    return ports


def test_the_self_check_moves_to_the_next_port(tmp_path):
    app = S.App(tmp_path, log=S.Log(None, console=lambda t: None))
    asked = []

    def curl(url):   # Windows' localhost: another program answers on the first port; this server on the second
        asked.append(url)
        port = int(urllib.parse.urlsplit(url).port)
        if len(asked) == 1:
            return json.dumps({"app": "songcharter", "token": "0" * 16})
        got = S.hello(port)
        return json.dumps(got) if got else None

    first, second = free_ports(2)
    servers = S.bind(app, [first, second], S.windows_check(app, curl))
    try:
        assert asked == [f"http://localhost:{first}/api/hello", f"http://localhost:{second}/api/hello"]
        assert [s.server_address for s in servers] == [("127.0.0.1", second)]
        assert app.url == f"http://localhost:{second}/"
        assert app.host_ok(f"localhost:{second}") and not app.host_ok(f"127.0.0.1:{first}")
        assert S.find_running([first, second]) == (second, S.hello(second)) and S.hello(first) is None
    finally:
        for s in servers:
            s.shutdown()
            s.server_close()


def test_when_every_port_fails_the_fallback_address_is_allowed(tmp_path):
    lines = []
    app = S.App(tmp_path, log=S.Log(None, console=lines.append))
    ports = free_ports(3)
    servers = S.bind(app, ports, S.windows_check(app, lambda url: None), address=lambda: "127.0.0.2")
    try:
        first = ports[0]
        assert [s.server_address for s in servers] == [("127.0.0.1", first), ("127.0.0.2", first)]
        assert app.url == f"http://127.0.0.2:{first}/"
        assert lines[-1] == ("Windows' localhost does not reach WSL here (localhostForwarding off, or the port is "
                             f"taken); using http://127.0.0.2:{first}/")
        status, _, body = call(first, "GET", "/api/hello", host=f"127.0.0.2:{first}", connect="127.0.0.2")
        assert status == 200 and json.loads(body)["token"] == app.token
        # its origin passes the guard (409: no job, not 403); localhost's still does; another port's does not
        assert call(first, "POST", "/api/jobs/current/cancel", b"", guarded(first, "127.0.0.2"),
                    host=f"127.0.0.2:{first}", connect="127.0.0.2")[0] == 409
        assert call(first, "POST", "/api/jobs/current/cancel", b"", guarded(first))[0] == 409
        assert call(first, "GET", "/api/hello", host=f"127.0.0.2:{ports[1]}")[0] == 403
        assert not app.host_ok(f"127.0.0.1:{ports[1]}")
    finally:
        for s in servers:
            s.shutdown()
            s.server_close()
    # no address to fall back on: localhost only
    app = S.App(tmp_path, log=S.Log(None, console=lambda t: None))
    servers = S.bind(app, free_ports(1), lambda port: False, address=lambda: None)
    try:
        assert len(servers) == 1 and app.url.startswith("http://127.0.0.1:")
    finally:
        for s in servers:
            s.shutdown()
            s.server_close()


def test_no_free_port(tmp_path):
    app = S.App(tmp_path, log=S.Log(None, console=lambda t: None))
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    s.listen()
    try:
        with pytest.raises(S.NoPort):
            S.bind(app, [s.getsockname()[1]])
    finally:
        s.close()


def test_songcharter_ui_starts_answers_and_stops_on_sigterm(tmp_path):
    """The command itself: it binds, logs, answers; a second start finds it and exits 0; SIGTERM stops it (and the
    job it runs) within 5 s."""
    home = tmp_path / "home"
    home.mkdir()
    (home / "doctor.json").write_text(json.dumps(DOCTOR), encoding="utf-8")
    port = free_ports(1)[0]
    root = Path(songcharter.__file__).resolve().parents[1]
    env = {**os.environ, "SONGCHARTER_HOME": str(home), "PYTHONPATH": str(root)}
    env.pop("WSL_DISTRO_NAME", None)
    cmd = [sys.executable, "-m", "songcharter.cli", "ui", "--no-browser", "--port", str(port)]
    server = subprocess.Popen(cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, cwd=tmp_path)
    try:
        deadline = time.monotonic() + 30
        while S.hello(port) is None:
            assert server.poll() is None and time.monotonic() < deadline, server.stdout.read().decode()
            time.sleep(0.1)
        second = subprocess.run([*cmd, "--from-shortcut"], env=env, capture_output=True, text=True, timeout=30)
        assert second.returncode == 0 and f"songcharter is running already: http://127.0.0.1:{port}/" in second.stdout
        assert call(port, "GET", "/api/status")[0] == 200
        t0 = time.monotonic()
        server.send_signal(signal.SIGTERM)
        assert server.wait(10) == 0 and time.monotonic() - t0 < 5
    finally:
        if server.poll() is None:
            server.kill()
    out = server.stdout.read().decode()
    assert f"songcharter is at http://127.0.0.1:{port}/" in out and "SIGTERM: stopping" in out and "stopped" in out
    log = next((home / "logs").glob("ui-*.log")).read_text(encoding="utf-8")
    assert "GET /api/status" in log and "SIGTERM: stopping" in log
    assert S.main(port=0) == 2   # a port out of range
