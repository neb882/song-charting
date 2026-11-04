"""The UI's server (songcharter.ui.server) on an ephemeral port: the Host and Origin guards, the CSP on every response,
static files by exact name, uploads, one job at a time, the SSE stream, cancel, the Windows self-check and its
fallback, and `songcharter ui` itself as a process. Jobs run a stand-in chart program (STANDIN); Windows' curl.exe
is a stand-in function. Nothing here needs Windows or a model."""
import hashlib
import http.client
import json
import os
import pty
import shutil
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
        for path in ("/api/upload", "/api/jobs", "/api/jobs/current/cancel", "/api/jobs/current/export/zip",
                     "/api/clonehero", "/api/jobs/current/install", "/api/open"):
            status, h, _ = call(port, "POST", path, b"{}", {"X-Filename": "a.mp3", **headers})
            assert status == 403 and secure(h), (path, headers)
    # a CORS preflight is refused, and nothing ever grants CORS
    status, h, _ = call(port, "OPTIONS", "/api/jobs", None, {"Origin": "http://evil.example",
                                                             "Access-Control-Request-Method": "POST",
                                                             "Access-Control-Request-Headers": "x-songcharter"})
    assert status == 403 and secure(h)
    assert call(port, "PUT", "/api/jobs", b"{}", guarded(port))[0] == 405
    assert call(port, "POST", "/api/jobs/current/cancel", b"", guarded(port, "localhost"))[0] == 409   # passed
    for path in ("/api/jobs/current/export/zip", "/api/jobs/current/install"):   # passed too: no chart yet
        assert call(port, "POST", path, b"{}", guarded(port))[0] == 400
    assert served.app.jobs.current is None and not (served.home / "exports").exists()


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
    """Under NAT, as before: the first free port on localhost and on the address the fallback allows (127.0.0.2 here
    stands in for WSL's NAT address, which fallback_address checks: the tests below)."""
    lines = []
    app = S.App(tmp_path, log=S.Log(None, console=lines.append))
    ports = free_ports(3)
    servers = S.bind(app, ports, S.windows_check(app, lambda url: None), lambda: ("127.0.0.2", ""))
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
    # no address the fallback may use, or one that cannot be bound: Unreachable, and nothing left listening
    for fallback, why in ((lambda: (None, "networkingMode=mirrored ..."), "networkingMode=mirrored"),
                          (lambda: ("192.0.2.7", ""), "WSL's address 192.0.2.7 cannot be bound")):
        app = S.App(tmp_path, log=S.Log(None, console=lambda t: None))
        port = free_ports(1)[0]
        with pytest.raises(S.Unreachable, match=why):
            S.bind(app, [port], lambda port: False, fallback)
        with pytest.raises(OSError):
            socket.create_connection(("127.0.0.1", port), timeout=2).close()
        assert app.url is None and not app.host_ok(f"127.0.0.1:{port}")


@pytest.mark.parametrize("mode", ["mirrored", "Mirrored", "bridged", "virtioproxy"])
def test_no_fallback_but_under_nat(mode):
    """Under mirrored networking (or any mode but NAT) the Linux side carries the PC's own addresses: none is used,
    whatever WSL's address looks like."""
    asked = []
    ip, why = S.fallback_address(mode, lambda: asked.append(1) or "172.24.5.6")
    assert ip is None and f"networkingMode={mode}" in why and "other machines can reach" in why and asked == []


@pytest.mark.parametrize("address, ok", [("172.24.5.6", True), ("172.16.0.1", True), ("172.31.255.254", True),
                                         ("172.32.0.1", False), ("172.15.255.1", False), ("192.168.1.20", False),
                                         ("10.0.0.5", False), ("127.0.0.2", False), ("x", False), (None, False)])
def test_under_nat_only_an_address_in_wsls_nat_range(address, ok):
    for mode in (None, "", "nat", "NAT"):
        ip, why = S.fallback_address(mode, lambda: address)
        assert (ip == address and why == "") if ok else ip is None, (mode, address, why)
    if address is None:
        assert "no default route" in why
    elif not ok:
        assert f"WSL's address {address} is not on WSL's own NAT network (172.16.0.0/12)" in why


def test_wsl_address_is_the_default_routes_source_not_a_bridge(tmp_path, monkeypatch):
    """hostname -I lists Docker's bridge first here; the address is the default route's source all the same."""
    bin_ = tmp_path / "bin"
    bin_.mkdir()
    for name, text in (("hostname", "172.17.0.1 172.24.5.6 "),
                       ("ip", "1.1.1.1 via 172.24.0.1 dev eth0 src 172.24.5.6 uid 1000 \n    cache ")):
        (bin_ / name).write_text(f"#!/bin/sh\necho '{text}'\n")
        (bin_ / name).chmod(0o755)
    monkeypatch.setenv("PATH", str(bin_))
    assert S.wsl_address() == "172.24.5.6"
    # without `ip`: the kernel's own choice for a UDP socket to 1.1.1.1 (whatever it is here), never hostname's first
    (bin_ / "ip").unlink()
    assert S.wsl_address() != "172.17.0.1"


@pytest.mark.parametrize("mode, address, why", [
    ("mirrored", "172.24.5.6", "networkingMode=mirrored in .wslconfig"),
    (None, "192.168.1.20", "WSL's address 192.168.1.20 is not on WSL's own NAT network"),
    (None, None, "WSL has no address of its own (no default route)"),
])
def test_songcharter_ui_stops_rather_than_listen_where_others_reach(tmp_path, monkeypatch, mode, address, why):
    """In WSL, with Windows' localhost failing the self-check: no fallback address may be used, so the server
    listens nowhere, says why and what to try, and exits 2 (the environment)."""
    from songcharter import wsl
    home = tmp_path / "home"
    home.mkdir()
    (home / "doctor.json").write_text(json.dumps(DOCTOR), encoding="utf-8")
    monkeypatch.setattr(wsl, "is_wsl", lambda: True)
    monkeypatch.setattr(wsl, "interop_ok", lambda: True)
    monkeypatch.setattr(wsl, "windows_curl", lambda url: None)
    monkeypatch.setattr(wsl, "wslconfig", lambda: {"path": "C:\\X\\.wslconfig", "exists": True, "memory_bytes": None,
                                                   "swap_bytes": None, "localhost_forwarding": None,
                                                   "networking_mode": mode})
    monkeypatch.setattr(S, "wsl_address", lambda: address)
    bound = []
    real = S.Server

    class Recording(real):
        def __init__(self, where, app):
            bound.append(where[0])
            super().__init__(where, app)

    monkeypatch.setattr(S, "Server", Recording)
    printed = []
    monkeypatch.setattr(S, "console_line", printed.append)
    port = free_ports(1)[0]
    assert S.main(port=port, browser=False, home=home) == 2
    assert set(bound) == {"127.0.0.1"}   # never another address
    with pytest.raises(OSError):
        socket.create_connection(("127.0.0.1", port), timeout=2).close()
    log = next((home / "logs").glob("ui-*.log"))
    message = printed[-1]
    assert message.startswith(f"songcharter: error: Windows cannot reach this page: Windows' localhost did not answer "
                              f"on port {port}, and songcharter will not listen on another address ({why}")
    for text in ("songcharter ui --port", "wsl --shutdown", f"Details: {log}"):
        assert text in message, text
    assert message in log.read_text(encoding="utf-8")


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


# `songcharter ui`'s main with the job's command replaced by the stand-in chart (STANDIN, mode "hang": a take that
# never ends, and a grandchild)
DRIVER = r'''
import sys
from pathlib import Path
from songcharter.ui import jobs as J, server as S
standin, home, port = sys.argv[1], Path(sys.argv[2]), int(sys.argv[3])


def command(song, out, options, threads):
    return [sys.executable, standin, "hang", str(out)]


defaults = list(J.Jobs.__init__.__defaults__)
defaults[0] = command
J.Jobs.__init__.__defaults__ = tuple(defaults)
sys.exit(S.main(port=port, browser=False, home=home))
'''


@pytest.mark.skipif(shutil.which("setsid") is None, reason="needs util-linux setsid for the console's pty")
@pytest.mark.parametrize("how", ["SIGTERM", "SIGHUP", "the window closes"])
def test_stopping_the_server_kills_the_running_charts_whole_tree(tmp_path, how):
    """The chart runs in a session of its own, so a hangup or a Ctrl+C never reaches it: only the server's stop
    path kills it. Stopped by SIGTERM, by SIGHUP, or by its console window closing (its controlling terminal is a pty
    whose other end closes: the kernel hangs it up, and every console write then fails with EIO), the server kills
    the chart and its grandchild, closes, logs "stopped" and exits 0."""
    home = tmp_path / "home"
    home.mkdir()
    (home / "doctor.json").write_text(json.dumps(DOCTOR), encoding="utf-8")
    (tmp_path / "standin.py").write_text(STANDIN, encoding="utf-8")
    (tmp_path / "driver.py").write_text(DRIVER, encoding="utf-8")
    port = free_ports(1)[0]
    root = Path(songcharter.__file__).resolve().parents[1]
    env = {**os.environ, "PYTHONPATH": str(root)}
    env.pop("WSL_DISTRO_NAME", None)
    argv = [sys.executable, str(tmp_path / "driver.py"), str(tmp_path / "standin.py"), str(home), str(port)]
    errors = open(tmp_path / "stderr.txt", "w")
    master = None
    if how == "the window closes":   # a new session whose controlling terminal is the pty, as a console window's
        master, slave = pty.openpty()
        server = subprocess.Popen(["setsid", "-c", *argv], env=env, cwd=tmp_path, stdin=slave, stdout=slave,
                                  stderr=errors)
        os.close(slave)
    else:
        server = subprocess.Popen(argv, env=env, cwd=tmp_path, stdout=subprocess.DEVNULL, stderr=errors,
                                  start_new_session=True)
    pids = []
    try:
        deadline = time.monotonic() + 30
        while S.hello(port) is None:
            assert server.poll() is None and time.monotonic() < deadline, (tmp_path / "stderr.txt").read_text()
            time.sleep(0.1)
        ctx = SimpleNamespace(port=port)
        status, up = upload(ctx, song(tmp_path / "s.wav"), "Song.wav")
        assert status == 200
        assert call(port, "POST", "/api/jobs", json.dumps({"upload": up["id"]}).encode(), guarded(port))[0] == 202
        deadline = time.monotonic() + 30
        while not pids:
            assert time.monotonic() < deadline
            events = json.loads(call(port, "GET", "/api/jobs/current")[2])["events"]
            pids = next((e["pids"] for e in events if e["event"] == "take"), [])
            time.sleep(0.05)
        assert all(proc.alive(p) for p in pids)
        if master is not None:
            os.close(master)
            master = None
        else:
            server.send_signal(getattr(signal, how))
        code = server.wait(15)
        assert code == 0, (tmp_path / "stderr.txt").read_text()
        assert not any(proc.alive(p) for p in pids)   # the chart and its grandchild, by pid
        log = next((home / "logs").glob("ui-*.log")).read_text(encoding="utf-8")
        assert "stopping" in log and "cancelled (exit -15)" in log and log.rstrip().endswith("stopped")
    finally:
        if master is not None:
            os.close(master)
        if server.poll() is None:
            server.kill()
        for p in pids:
            if proc.alive(p):
                os.kill(p, signal.SIGKILL)
        errors.close()


# ------------------------------------------------------------------------------------------------ after the build (M4-06)

# a chart's end as the page sees it: the song folder's four files, a work folder with pipeline.json and the preview's
# pictures, and the result event; with --lyrics=/dev/fd/<n>, the text read as `songcharter chart` reads it (its
# SHA-256 and word count reported: proof it came whole, with no word of it). Mode "linger": after the result, the
# process exits only once work/release exists (a real chart's interpreter takes a second or more to exit)
BUILT = r'''
import hashlib, json, sys, time
from pathlib import Path
mode, out, work = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3])
given = next((a[len("--lyrics="):] for a in sys.argv if a.startswith("--lyrics=")), None)

def ev(**e):
    sys.stderr.write("@@songcharter " + json.dumps(e) + "\n")
    sys.stderr.flush()

ev(event="plan", stages=["decode", "lyrics", "assemble", "preview"])
sha = None
if given is not None:
    from songcharter.cli import read_lyrics
    text = read_lyrics(Path(given))
    sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
    ev(event="warning", text=f"lyrics: {len(text.split())} words from {given}")
ok = mode != "fail"
out.mkdir(parents=True, exist_ok=True)
(out / "notes.chart").write_text("[Song]\n{\n}\n", encoding="utf-8")
(out / "song.ini").write_text("[song]\nname = x\ncharter = songcharter\n", encoding="utf-8")
(out / "song.ogg").write_bytes(b"OggS" + bytes(64))
(out / "report.json").write_text(json.dumps({"gate": {"ok": ok}}), encoding="utf-8")
preview = work / "preview"
preview.mkdir(parents=True, exist_ok=True)
for name in ("overview.png", "page_01.png", "page_02.png", "flags.txt", "page_1.png"):
    (preview / name).write_bytes(b"\x89PNG\r\n\x1a\n" + name.encode())
(work / "pipeline.json").write_text(json.dumps({
    "preview": {"ok": True, "flags": ["guitar: gap 0:12.0-0:16.0 (2 measures)"], "remarks": ["no Hard level"]},
    **({"lyrics": {"given": True, "added": True, "words": 5, "chart": {"phrases": 2},
                   "confidence": {"median": 0.2, "low": True}}} if given else {})}), encoding="utf-8")
ev(event="result", ok=ok, exit=0 if ok else 1, folder=str(out), work=str(work), preview=str(preview),
   summary="gate: OK" if ok else "gate: FAILED", lyrics_sha256=sha)
deadline = time.monotonic() + 30
while mode == "linger" and not (work / "release").exists() and time.monotonic() < deadline:
    time.sleep(0.02)
'''
LYRICS = "zorp blen-dak\nquiv\n\n[Glorp]\nsmee plin\n"
LYRIC_WORDS = ("zorp", "blen", "dak", "quiv", "Glorp", "smee", "plin")


@pytest.fixture
def finished(tmp_path, monkeypatch):
    """A server whose jobs run BUILT (mode "ok" or "fail"), not in WSL, with an uploaded song; `run(options)` charts
    it and waits for the end."""
    from songcharter import wsl
    monkeypatch.setattr(wsl, "is_wsl", lambda: False)
    home = tmp_path / "home"
    home.mkdir()
    (home / "doctor.json").write_text(json.dumps(DOCTOR), encoding="utf-8")
    script = tmp_path / "built.py"
    script.write_text(BUILT, encoding="utf-8")
    root = Path(songcharter.__file__).resolve().parents[1]
    ctx = SimpleNamespace(mode="ok", lines=[], home=home, work=tmp_path / "work", commands=[])

    def command(song, out, options, threads):
        return [sys.executable, str(script), ctx.mode, str(out), str(ctx.work)]

    jobs = J.Jobs(home, command=command, env={**os.environ, "PYTHONPATH": str(root)})
    app = S.App(home, jobs=jobs, log=S.Log(home / "ui.log", console=ctx.lines.append), report=lambda: DOCTOR)
    servers = S.bind(app, [0])
    ctx.app, ctx.port = app, servers[0].server_address[1]
    status, ctx.upload = upload(ctx, song(tmp_path / "s.wav"), "Song.wav")
    assert status == 200

    def run(options=None, code=202):
        status, _, body = call(ctx.port, "POST", "/api/jobs", json.dumps({"upload": ctx.upload["id"],
                                                                         "options": options or {}}).encode(),
                               guarded(ctx.port))
        assert status == code, body
        if code != 202:
            return json.loads(body)
        job = wait_state(ctx, "done")
        ctx.commands.append(job.command)
        return job

    ctx.run = run
    yield ctx
    app.jobs.shutdown()
    for s in servers:
        s.shutdown()
        s.server_close()


def post(ctx, path, value=None):
    status, headers, body = call(ctx.port, "POST", path, b"" if value is None else json.dumps(value).encode(),
                                 guarded(ctx.port))
    return status, json.loads(body) if body else None


def get(ctx, path):
    status, headers, body = call(ctx.port, "GET", path)
    return status, headers, body


def test_the_results_and_the_preview_by_exact_name_only(finished):
    ctx = finished
    for path in ("/api/jobs/current/results", "/api/jobs/current/preview/overview.png"):
        assert get(ctx, path)[0] == 404   # no job yet
    job = ctx.run()
    status, _, body = get(ctx, "/api/jobs/current/results")
    res = json.loads(body)
    assert status == 200 and res["ok"] is True and res["installable"] is True and res["lyrics"] is None
    assert res["name"] == job.out.name and res["folder"] == str(job.out)
    base = "/api/jobs/current/preview/"
    assert res["preview"] == {"overview": base + "overview.png", "pages": [base + "page_01.png", base + "page_02.png"],
                              "flags": ["guitar: gap 0:12.0-0:16.0 (2 measures)"], "remarks": ["no Hard level"]}
    for name in ("overview.png", "page_01.png", "page_02.png"):
        status, headers, body = get(ctx, base + name + "?job=1")
        assert status == 200 and headers["Content-Type"] == "image/png" and secure(headers)
        assert body == b"\x89PNG\r\n\x1a\n" + name.encode()
    for name in ("page_100.png", "page_11.png"):   # a song over 99 minutes: in page order, not by name
        (ctx.work / "preview" / name).write_bytes(b"\x89PNG")
    pages = json.loads(get(ctx, "/api/jobs/current/results")[2])["preview"]["pages"]
    assert [p[len(base):] for p in pages] == ["page_01.png", "page_02.png", "page_11.png", "page_100.png"]
    for name in ("flags.txt", "page_1.png", "page_03.png", "overview.PNG", "overview.png.exe", "../pipeline.json",
                 "..%2Fpipeline.json", "%2e%2e%2fpipeline.json", "", "preview/overview.png", "..\\overview.png",
                 "overview.png%00", "/etc/passwd"):
        assert get(ctx, base + name)[0] == 404, name


def test_no_preview_says_why(finished, tmp_path):
    ctx = finished
    ctx.run({"preview": False})
    pipeline = ctx.work / "pipeline.json"
    for record, why in (({"ok": False, "skipped": "turned off"}, "it was turned off in the options"),
                        ({"ok": False, "skipped": "ModuleNotFoundError: x"}, "it needs matplotlib and librosa"),
                        ({"ok": False, "error": "ValueError: y"}, "it failed (ValueError: y)")):
        pipeline.write_text(json.dumps({"preview": record}), encoding="utf-8")
        (ctx.work / "preview" / "overview.png").unlink(missing_ok=True)
        res = json.loads(get(ctx, "/api/jobs/current/results")[2])
        assert res["preview"]["why"].startswith(why), res["preview"]


def test_the_zip_export_and_its_download(finished):
    ctx = finished
    job = ctx.run({"artist": "Fixture Band", "title": "Wait... What (Live)"})
    assert job.out.name == "Fixture Band - Wait... What (Live)"
    status, answer = post(ctx, "/api/jobs/current/export/zip")
    name = f"{job.out.name}.zip"
    assert status == 200 and answer == {"url": "/api/exports/" + urllib.parse.quote(name, safe=""), "name": name,
                                        "windows_path": None}
    assert sorted(p.name for p in (ctx.home / "exports").iterdir()) == [name]
    status, headers, body = get(ctx, answer["url"])
    assert status == 200 and headers["Content-Type"] == "application/zip" and secure(headers)
    assert headers["Content-Disposition"] == (f'attachment; filename="{name}"; '
                                              f"filename*=UTF-8''{urllib.parse.quote(name, safe='')}")
    import io
    import zipfile
    with zipfile.ZipFile(io.BytesIO(body)) as z:
        assert sorted(z.namelist()) == sorted(f"{job.out.name}/{f}" for f in
                                              ("notes.chart", "song.ini", "song.ogg", "report.json"))
    (ctx.home / "ui.json").write_text("{}", encoding="utf-8")
    (ctx.home / "exports" / ".x.zip.part").write_text("x")
    (ctx.home / "exports" / "sub").mkdir()
    (ctx.home / "exports" / "sub" / "y.zip").write_text("x")
    for bad in ("missing.zip", "../ui.json", "..%2Fui.json", "%2e%2e%2fui.json", "..", "sub%2Fy.zip", "sub/y.zip",
                "sub%5Cy.zip", ".x.zip.part", f"{urllib.parse.quote(name)}%00", urllib.parse.quote(job.out.name),
                "", "%2Fetc%2Fpasswd.zip"):
        assert get(ctx, "/api/exports/" + bad)[0] == 404, bad


def test_clone_hero_through_the_api(finished, tmp_path, monkeypatch):
    """No folder known; a missing one refused (400); one saved; install (200), again (409, ours), a replace (200, the
    older chart in replaced/). The install route takes no path from the page."""
    ctx = finished
    job = ctx.run()
    status, _, body = get(ctx, "/api/clonehero")
    assert status == 200 and json.loads(body) == {"folder": None, "windows_path": None, "source": "not found",
                                                  "under_onedrive": None, "guess": None}
    status, answer = post(ctx, "/api/jobs/current/install", {"replace": False})
    assert status == 400 and "no Clone Hero Songs folder is known" in answer["error"]
    songs = tmp_path / "Jörg's Söngs" / "Clone Hero" / "Songs"
    for value, why in (({"folder": str(songs)}, "does not exist"), ({"folder": 7}, "as text"), ({}, "as text"),
                       ({"folder": "Songs"}, "not a whole path")):
        status, answer = post(ctx, "/api/clonehero", value)
        assert status == 400 and why in answer["error"], value
    assert not (ctx.home / "ui.json").exists()
    songs.mkdir(parents=True)
    status, answer = post(ctx, "/api/clonehero", {"folder": str(songs)})
    assert status == 200 and answer["folder"] == str(songs) and answer["source"] == "saved"
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    status, answer = post(ctx, "/api/jobs/current/install", {"replace": False, "folder": str(elsewhere),
                                                              "path": str(elsewhere)})
    target = songs / job.out.name
    assert status == 200 and answer == {"installed": str(target), "windows_path": None, "replaced": None, "note": None}
    assert sorted(p.name for p in target.iterdir()) == ["notes.chart", "report.json", "song.ini", "song.ogg"]
    assert list(elsewhere.iterdir()) == []
    status, answer = post(ctx, "/api/jobs/current/install", {"replace": False})
    assert status == 409 and answer["exists"] is True and answer["ours"] is True and answer["folder"] == str(target)
    status, answer = post(ctx, "/api/jobs/current/install", {"replace": True})
    assert status == 200 and answer["installed"] == str(target)
    replaced = Path(answer["replaced"])
    assert replaced.parent.parent == ctx.home / "replaced" and (replaced / "report.json").is_file()
    assert sorted(p.name for p in songs.iterdir()) == [job.out.name]
    # "Open folder": only the installed song's folder and the exports folder; outside WSL nothing opens
    opened = []
    from songcharter import wsl
    monkeypatch.setattr(wsl, "open_url", opened.append)
    assert post(ctx, "/api/open", {"what": "song"}) == (200, {"opened": False, "path": str(target),
                                                              "windows_path": None})
    status, answer = post(ctx, "/api/open", {"what": "exports"})
    assert status == 200 and answer["path"] == str(ctx.home / "exports") and opened == []
    for what in ("/etc", str(target), None, "replaced"):
        assert post(ctx, "/api/open", {"what": what})[0] == 400, what


def test_open_folder_in_wsl_runs_explorer_on_the_windows_path(finished, tmp_path, monkeypatch):
    from songcharter import wsl
    ctx = finished
    ctx.run()
    assert post(ctx, "/api/open", {"what": "song"})[0] == 400   # nothing installed from this page yet
    songs = tmp_path / "mnt" / "c" / "Songs"
    songs.mkdir(parents=True)
    assert post(ctx, "/api/clonehero", {"folder": str(songs)})[0] == 200
    assert post(ctx, "/api/jobs/current/install", {})[0] == 200
    monkeypatch.setattr(wsl, "MNT_C", tmp_path / "mnt" / "c")
    monkeypatch.setattr(wsl, "is_wsl", lambda: True)
    monkeypatch.setattr(wsl, "distro", lambda: "Ubuntu")
    opened = []
    monkeypatch.setattr(wsl, "open_url", lambda target: opened.append(target) or True)
    status, answer = post(ctx, "/api/open", {"what": "song"})
    name = ctx.app.installed.name
    assert status == 200 and answer["opened"] is True and opened == [f"C:\\Songs\\{name}"]
    status, answer = post(ctx, "/api/open", {"what": "exports"})
    assert answer["windows_path"] == "\\\\wsl.localhost\\Ubuntu" + str(ctx.home / "exports").replace("/", "\\")
    assert opened[-1] == answer["windows_path"]


def test_a_blocked_install_answers_403_with_the_zip(finished, tmp_path, monkeypatch):
    from songcharter import clonehero, wsl
    ctx = finished
    job = ctx.run()
    songs = tmp_path / "OneDrive" / "Documents" / "Clone Hero" / "Songs"
    songs.mkdir(parents=True)
    assert post(ctx, "/api/clonehero", {"folder": str(songs)})[0] == 200

    def refused(src, dst):
        raise PermissionError(13, "Permission denied")

    monkeypatch.setattr(clonehero, "copy_contents", refused)
    monkeypatch.setattr(wsl, "onedrive_roots", lambda: [tmp_path / "OneDrive"])
    status, answer = post(ctx, "/api/jobs/current/install", {"replace": False})
    name = f"{job.out.name}.zip"
    assert status == 403 and answer["blocked"] is True and answer["under_onedrive"] is True
    assert answer["zip_url"] == "/api/exports/" + urllib.parse.quote(name, safe="")
    assert "Permission denied" in answer["why"] and list(songs.iterdir()) == []
    assert get(ctx, answer["zip_url"])[0] == 200
    # a folder of that name that songcharter did not make: 409, and a replace of it too
    monkeypatch.undo()
    monkeypatch.setattr(wsl, "is_wsl", lambda: False)
    other = songs / job.out.name
    other.mkdir()
    (other / "song.ini").write_text("[song]\ncharter = Someone\n", encoding="utf-8")
    for replace in (False, True):
        status, answer = post(ctx, "/api/jobs/current/install", {"replace": replace})
        assert status == 409 and answer["ours"] is False, replace
    assert sorted(p.name for p in other.iterdir()) == ["song.ini"]


def test_the_done_screen_can_install_while_the_chart_is_still_exiting(finished, tmp_path):
    """The release gate's finding: the page asks for the results the moment it reads the `result` event (app.js),
    and the chart's process exits a second or more later (the interpreter's teardown, a CUDA context on a GPU). The
    job then counts as finished: its results are installable, and the zip and the install work, all while its state
    is still running (the stand-in exits only when this test lets it)."""
    ctx = finished
    ctx.mode = "linger"
    songs = tmp_path / "Songs"
    songs.mkdir()
    assert post(ctx, "/api/clonehero", {"folder": str(songs)})[0] == 200
    status, _, body = call(ctx.port, "POST", "/api/jobs", json.dumps({"upload": ctx.upload["id"]}).encode(),
                           guarded(ctx.port))
    assert status == 202, body
    conn = http.client.HTTPConnection("127.0.0.1", ctx.port, timeout=30)
    try:
        conn.request("GET", "/api/jobs/current/events", headers={"Host": f"127.0.0.1:{ctx.port}"})
        for line in conn.getresponse():   # the stream as app.js follows it, up to the result event
            if line.startswith(b"data: ") and json.loads(line[6:])["event"] == "result":
                break
        res = json.loads(get(ctx, "/api/jobs/current/results")[2])
        assert res["state"] == "running" and res["ok"] is True and res["installable"] is True, res
        status, answer = post(ctx, "/api/jobs/current/export/zip")
        assert status == 200 and answer["name"] == f"{res['name']}.zip", answer
        status, answer = post(ctx, "/api/jobs/current/install", {"replace": False})
        assert status == 200 and answer["installed"] == str(songs / res["name"]), answer
        assert ctx.app.jobs.current.state == "running"   # all of it before the chart's process ended
    finally:
        (ctx.work / "release").write_text("go", encoding="utf-8")
        conn.close()
    assert wait_state(ctx, "done").returncode == 0


def test_a_chart_that_failed_its_gate_is_not_exported_or_installed(finished, tmp_path):
    ctx = finished
    ctx.mode = "fail"
    ctx.run()
    res = json.loads(get(ctx, "/api/jobs/current/results")[2])
    assert res["ok"] is False and res["installable"] is False and res["preview"]["overview"]
    songs = tmp_path / "Songs"
    songs.mkdir()
    assert post(ctx, "/api/clonehero", {"folder": str(songs)})[0] == 200
    for path in ("/api/jobs/current/export/zip", "/api/jobs/current/install"):
        status, answer = post(ctx, path, {})
        assert status == 400 and "did not pass its check" in answer["error"], path
    assert list(songs.iterdir()) == [] and not (ctx.home / "exports").exists()


def test_the_diagnostics_download(finished):
    from songcharter import diagnostics
    ctx = finished
    ctx.run()
    status, headers, body = get(ctx, "/api/diagnostics")
    assert status == 200 and headers["Content-Type"] == "application/zip" and secure(headers)
    assert headers["Content-Disposition"].startswith('attachment; filename="songcharter-diagnostics-')
    import io
    import zipfile
    with zipfile.ZipFile(io.BytesIO(body)) as z:
        names = z.namelist()
        assert {"MANIFEST.txt", "doctor.json", "doctor-now.json", "clonehero.json"} <= set(names)
        assert json.loads(z.read("doctor-now.json")) == DOCTOR
        assert any(n.startswith("logs/job-") for n in names)
        for n in names:
            assert diagnostics.refused(n, z.read(n)) is None, n


def _memfds() -> list[str]:
    out = []
    for fd in os.listdir("/proc/self/fd"):
        try:
            out.append(os.readlink(f"/proc/self/fd/{fd}"))
        except OSError:
            pass
    return [x for x in out if "songcharter-lyrics" in x]


def test_pasted_lyrics_go_only_into_the_chart(finished):
    """The box's text reaches the chart whole (the child reads it as `songcharter chart --lyrics` does), and no word of
    it is in the command line, a log, an event, a record, an answer, ui.json or the diagnostics bundle."""
    import hashlib
    ctx = finished
    job = ctx.run({"lyrics": LYRICS})
    result = job.result()
    assert result["lyrics_sha256"] == hashlib.sha256(LYRICS.encode("utf-8")).hexdigest()
    assert job.options.lyrics == LYRICS and "lyrics=" not in repr(job.options) and LYRICS not in repr(job)
    flag = [a for a in job.command if a.startswith("--lyrics=")]
    assert len(flag) == 1 and flag[0].startswith("--lyrics=/dev/fd/")
    assert _memfds() == []   # the server closed its copy of the memory file
    res = json.loads(get(ctx, "/api/jobs/current/results")[2])
    assert res["lyrics"] == {"given": True, "added": True, "words": 5, "phrases": 2, "why": None, "low": True}
    texts = [get(ctx, p)[2] for p in ("/api/jobs/current", "/api/status", "/api/jobs/current/results")]
    snap = json.loads(texts[0])
    assert snap["options"]["lyrics"] is True and any(e["event"] == "warning" and "6 words from /dev/fd/" in e["text"]
                                                     for e in snap["events"])
    texts.append(get(ctx, "/api/diagnostics")[2])
    import io
    import zipfile
    with zipfile.ZipFile(io.BytesIO(texts[-1])) as z:
        texts += [z.read(n) for n in z.namelist()]
    texts += [p.read_bytes() for p in ctx.home.rglob("*") if p.is_file() and p.suffix != ".zip"]
    texts.append("\n".join(ctx.lines).encode())
    texts.append(json.dumps(job.events).encode())
    for data in texts:
        assert not any(w.encode() in data for w in LYRIC_WORDS), data[:300]
    assert (ctx.home / "ui.log").is_file() and list((ctx.home / "logs").glob("job-*.log"))
    # blank is none; a text with no word, or not text, is refused without quoting it
    job = ctx.run({"lyrics": "  \n\t\n"})
    assert job.options.lyrics is None and not any(a.startswith("--lyrics") for a in job.command)
    assert json.loads(get(ctx, "/api/jobs/current")[2])["options"]["lyrics"] is False
    for value, why in (("[Glorp]\n\n", "the lyrics hold no word to time"), (["zorp blen"], "lyrics is text, not a list"),
                       ({"zorp": 1}, "lyrics is text, not a dict")):
        answer = ctx.run({"lyrics": value}, code=400)
        assert answer["error"] == why and not any(w in answer["error"] for w in LYRIC_WORDS)


def test_a_blocked_replace_names_where_the_older_chart_is(finished, tmp_path, monkeypatch):
    """The rename into place and the put-back both refused: the 403 names the .old folder the older chart stays in,
    and the next install moves it to replaced/."""
    from songcharter import clonehero
    ctx = finished
    job = ctx.run()
    songs = tmp_path / "Songs"
    songs.mkdir()
    assert post(ctx, "/api/clonehero", {"folder": str(songs)})[0] == 200
    assert post(ctx, "/api/jobs/current/install", {})[0] == 200

    def refused(src, dst):
        if not Path(dst).name.endswith(".old"):   # the rename aside goes through; into place and back do not
            raise PermissionError(13, "Permission denied")
        os.rename(src, dst)

    real = clonehero.install
    monkeypatch.setattr(clonehero, "install", lambda *a, **k: real(*a, rename=refused, sleep=lambda s: None, **k))
    status, answer = post(ctx, "/api/jobs/current/install", {"replace": True})
    [old] = [p for p in songs.iterdir()]
    assert status == 403 and answer["blocked"] is True and old.name.endswith(".old")
    assert answer["older"] == str(old) and str(old) in answer["why"] and answer["error"] == answer["why"]
    monkeypatch.setattr(clonehero, "install", real)
    status, answer = post(ctx, "/api/jobs/current/install", {})   # "try again"
    assert status == 200 and Path(answer["replaced"]).parent.parent == ctx.home / "replaced"
    assert [p.name for p in songs.iterdir()] == [job.out.name] and "went to" in answer["note"]
