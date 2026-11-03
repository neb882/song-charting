"""`songcharter ui [--port N] [--no-browser] [--from-shortcut]`: the local page's server (M4-04, DESIGN.md 4.5).

A standard-library ThreadingHTTPServer on 127.0.0.1 serves the page in static/ (vanilla JS, no CDN) and a small API;
one chart runs at a time as a child process group (jobs.py). In WSL the Windows browser opens it.

**Startup** (`main`):
  1. **Already running?** GET http://127.0.0.1:<port>/api/hello on 8765-8784 (or --port's alone): when one answers
     {"app": "songcharter"}, its page opens (below) and this exits 0.
  2. **Bind** to 127.0.0.1 on the first free port from 8765 (or --port's). Each start makes an instance token,
     secrets.token_hex(8), which /api/hello returns.
  3. **The Windows self-check** (WSL with interop): wsl.windows_curl("http://localhost:<port>/api/hello") must return
     this instance's token. That proves Windows' localhost reaches this server (WSL forwards "ports bound to wildcard
     or localhost" by default [doc: wsl-config.md]). An answer that is not this token (another program on that port
     on Windows, or none) moves to the next port. When no port of the range passes, the **fallback**: the first free
     port again, and also WSL's own address (the first of `hostname -I`) on that port, allowed as a host and an origin
     too, logged as such. That address is on WSL's host-only NAT network, so it is no wider than localhost
     [inference].
  4. **The browser**, unless --no-browser: in WSL wsl.open_url (explorer.exe), elsewhere webbrowser.open. The URL is
     printed in every case: http://localhost:<port>/ in WSL (what the self-check proved), http://127.0.0.1:<port>/
     elsewhere, or the fallback address.
  5. **Logs** to $SONGCHARTER_HOME/logs/ui-<yyyyMMdd>.log (every request too) and to the console window. Uploads older
     than 7 days go.
  6. **Stops** on SIGHUP or SIGTERM (the window closes) and Ctrl+C: a running job's tree is killed first. A page
     that closes does not stop it.

**Guards:**
  * The Host header must be one of the allowed hosts (127.0.0.1:<port>, localhost:<port>, and the fallback address
    when used); else 403. This stops DNS rebinding: a page on another name that resolves here sends its own Host.
  * Every request but a GET needs `X-Songcharter: 1` and an Origin from the same list; else 403. A form or a
    cross-site fetch cannot send that header without a CORS preflight, which is never granted (no CORS header is ever
    sent).
  * Every response carries the CSP below, X-Content-Type-Options: nosniff and Referrer-Policy: no-referrer.
  * Static files only from the package's ui/static/, by exact name (no path is ever joined from a request).

**API:**
  * GET /api/hello: {"app", "version", "token", "url"}.
  * GET /api/status: the doctor summary ({"device", "gpu", "guitar_device", "guitar_reason", "notes", "ok", "source"}:
    $SONGCHARTER_HOME/doctor.json, else device.report(full=False) made once, at startup), the current job (no
    events), and the defaults with threads_default.
  * POST /api/upload: the raw file as the body, X-Filename its name (percent-encoded). An extension not in AUDIO: 415;
    over 1 GB: 413; no Content-Length: 411. Streamed to uploads/<16 hex of its SHA-256>/<cache.safe_name(stem)><ext>,
    with upload.json beside it; answers {"id", "name", "bytes", "tags", "origin"}: the song.ini values the chart
    would take from the tags or the file's name (pipeline.read_tags and song_metadata), and where each came from.
  * POST /api/jobs {"upload", "options"}: 202 {"job"}; 409 while a job runs; 400 for bad options (Options.check()'s
    message) or an unknown upload.
  * GET /api/jobs/current: its state (running, done, failed, cancelled) and events; 404 before the first job.
  * GET /api/jobs/current/events: Server-Sent Events. Every event so far, then each new one, as `id: <index>` and
    `data: <json>`; a comment every 15 s keeps the connection open; it closes after `result`, `error` or `cancelled`.
    A Last-Event-ID header resumes after that index.
  * POST /api/jobs/current/cancel: 200 with the job's state after the cancel; 409 when no job runs.
"""
from __future__ import annotations

import hashlib
import json
import os
import secrets
import shutil
import signal
import subprocess
import sys
import threading
import time
import traceback
import urllib.error
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources
from pathlib import Path, PureWindowsPath
from typing import Any, Callable, Iterable
from urllib.parse import unquote, urlsplit

from .. import __version__, cache, device, wsl
from ..errors import InputError
from ..timed import DIFFICULTIES, INSTRUMENTS
from . import home as default_home
from .jobs import CLOSING, Jobs, JobRunning, NotRunning

APP = "songcharter"
PORTS = range(8765, 8785)          # 8765-8784
CSP = ("default-src 'self'; img-src 'self' data:; connect-src 'self'; script-src 'self'; style-src 'self'; "
       "base-uri 'none'; form-action 'none'; frame-ancestors 'none'")
SECURITY_HEADERS = {"Content-Security-Policy": CSP, "X-Content-Type-Options": "nosniff",
                    "Referrer-Policy": "no-referrer"}
AUDIO = (".mp3", ".wav", ".flac", ".ogg", ".opus", ".m4a", ".aac", ".wma", ".aiff", ".aif")
MAX_UPLOAD = 10 ** 9               # 1 GB (10^9 bytes, the unit of the project's limits)
MAX_JSON = 1 << 20                 # a JSON request body
DRAIN = 16 << 20                   # a refused body this small is read first, so the client sees the answer
UPLOAD_DAYS = 7                    # uploads older than this go when the server starts
KEEPALIVE_S = 15.0
HELLO_TIMEOUT_S = 0.5
CHUNK = 1 << 20
STATIC_TYPES = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
                ".css": "text/css; charset=utf-8"}


class Log:
    """The UI's log: each line with its time into the log file (when there is one) and, unless `console` is false,
    the console window."""

    def __init__(self, path: Path | None = None, console: Callable[[str], None] | None = None):
        self.path = path
        self.console = console if console is not None else (lambda text: print(text, flush=True))
        self._lock = threading.Lock()

    def __call__(self, text: str, console: bool = True) -> None:
        with self._lock:
            if self.path is not None:
                try:
                    with open(self.path, "a", encoding="utf-8", errors="replace") as f:
                        f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {text}\n")
                except OSError:
                    pass
            if console:
                self.console(text)


def static_files() -> dict[str, bytes]:
    """The page's files: name -> bytes, from the package's ui/static/ (index.html, app.js, app.css)."""
    folder = resources.files(__package__) / "static"
    return {p.name: p.read_bytes() for p in folder.iterdir() if p.is_file() and not p.name.startswith(".")}


class App:
    """What every request shares: the home, this instance's token, the allowed hosts, the jobs, the status."""

    def __init__(self, home: Path, jobs: Jobs | None = None, log: Log | None = None,
                 report: Callable[[], dict] = lambda: device.report(full=False)):
        self.home = Path(home)
        self.log = log or Log()
        self.jobs = jobs or Jobs(self.home, log=self.log)
        self.token = secrets.token_hex(8)
        self.url: str | None = None
        self.static = static_files()
        self._hosts: set[str] = set()
        self._lock = threading.Lock()
        self._report = report
        self._quick: dict | None = None
        self._quick_lock = threading.Lock()

    # --- the guards' lists
    def allow(self, host: str, port: int) -> None:
        with self._lock:
            self._hosts.add(f"{host}:{port}".lower())

    def disallow(self, host: str, port: int) -> None:
        with self._lock:
            self._hosts.discard(f"{host}:{port}".lower())

    def host_ok(self, host: str | None) -> bool:
        with self._lock:
            return bool(host) and host.lower() in self._hosts

    def origin_ok(self, origin: str | None) -> bool:
        with self._lock:
            return bool(origin) and origin.lower() in {f"http://{h}" for h in self._hosts}

    # --- the doctor summary
    def doctor(self) -> dict:
        """The report the header shows: doctor.json when it reads, else device.report(full=False), made once."""
        try:
            r = json.loads((self.home / "doctor.json").read_text(encoding="utf-8"))
            if isinstance(r, dict):
                return {**r, "source": "doctor.json"}
        except (OSError, ValueError):
            pass
        with self._quick_lock:
            if self._quick is None:
                try:
                    self._quick = {**self._report(), "source": "quick check"}
                except Exception as e:  # noqa: BLE001  the page says so; charting may still work
                    self._quick = {"ok": None, "source": "quick check", "error": f"{type(e).__name__}: {e}",
                                   "notes": [f"the machine check failed: {type(e).__name__}: {e}"]}
            return self._quick

    def status(self) -> dict:
        r = self.doctor()
        job = self.jobs.current
        threads = (r.get("cpu") or {}).get("threads_default") or device.default_threads()
        return {**{k: r.get(k) for k in ("device", "gpu", "guitar_device", "guitar_reason", "notes", "ok", "source",
                                          "error")},
                "job": job.snapshot(events=False) if job is not None else None,
                "defaults": {"instruments": list(INSTRUMENTS), "levels": ["expert"], "solos": "labels", "takes": None,
                             "device": "auto", "preview": True, "threads": None, "threads_default": threads,
                             "all_levels": list(DIFFICULTIES)}}

    def auto_device(self) -> str | None:
        return (self.doctor().get("device") or {}).get("chosen")


# ------------------------------------------------------------------------------------------------ uploads

def uploads_folder(home: Path) -> Path:
    return Path(home) / "uploads"


def read_upload(home: Path, upload_id: Any) -> dict | None:
    """An upload's record ({"id", "name", "file", "path", "bytes", "metadata", "origin"}), or None when there is no
    such upload (an id is 16 hex characters, nothing else)."""
    if not isinstance(upload_id, str) or len(upload_id) != cache.KEY_HEX or \
            any(c not in "0123456789abcdef" for c in upload_id):
        return None
    folder = uploads_folder(home) / upload_id
    try:
        record = json.loads((folder / "upload.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    path = folder / str(record.get("file"))
    if not path.is_file() or path.parent != folder:
        return None
    return {**record, "path": str(path)}


def prune_uploads(home: Path, days: float = UPLOAD_DAYS, now: float | None = None) -> list[str]:
    """Delete the uploads (and stray partial uploads) last touched more than `days` ago; their names."""
    now = time.time() if now is None else now
    gone = []
    folder = uploads_folder(home)
    try:
        entries = list(folder.iterdir())
    except OSError:
        return gone
    for p in entries:
        try:
            newest = max([p.stat().st_mtime] + ([c.stat().st_mtime for c in p.iterdir()] if p.is_dir() else []))
        except OSError:
            continue
        if now - newest > days * 86400:
            if p.is_dir():
                shutil.rmtree(p, ignore_errors=True)
            else:
                p.unlink(missing_ok=True)
            gone.append(p.name)
    return gone


# ------------------------------------------------------------------------------------------------ the handler

class Refused(Exception):
    def __init__(self, code: int, message: str):
        super().__init__(message)
        self.code = code


class Handler(BaseHTTPRequestHandler):
    server_version = "songcharter"
    sys_version = ""
    body_read = False   # the request's body was read (or begun): nothing left to drain

    @property
    def app(self) -> App:
        return self.server.app  # type: ignore[attr-defined]

    def end_headers(self) -> None:   # every response, send_error's too
        for k, v in SECURITY_HEADERS.items():
            self.send_header(k, v)
        super().end_headers()

    def log_message(self, format: str, *args) -> None:   # noqa: A002  BaseHTTPRequestHandler's name
        self.app.log(f"{self.address_string()} {format % args}", console=False)

    # --- responses
    def _send(self, code: int, body: bytes, ctype: str, headers: dict | None = None) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, code: int, value: Any) -> None:
        self._send(code, json.dumps(value, ensure_ascii=False, default=str).encode("utf-8"),
                   "application/json; charset=utf-8")

    def _refuse(self, code: int, message: str) -> None:
        self._drain()
        self._json(code, {"error": message})

    def _drain(self) -> None:
        """Read a request body nobody will use, when it is small, so the client sees the answer and not a reset; a
        large one closes the connection instead."""
        if self.body_read:
            return
        self.body_read = True
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            n = 0
        if 0 < n <= DRAIN:
            try:
                while n > 0:
                    got = self.rfile.read(min(n, CHUNK))
                    if not got:
                        break
                    n -= len(got)
            except OSError:
                pass
        elif n > DRAIN:
            self.close_connection = True

    # --- the methods
    def do_GET(self) -> None:   # noqa: N802
        self._handle("GET")

    def do_POST(self) -> None:   # noqa: N802
        self._handle("POST")

    def do_HEAD(self) -> None:   # noqa: N802
        self._handle("HEAD")

    def do_PUT(self) -> None:   # noqa: N802
        self._handle("PUT")

    def do_DELETE(self) -> None:   # noqa: N802
        self._handle("DELETE")

    def do_PATCH(self) -> None:   # noqa: N802
        self._handle("PATCH")

    def do_OPTIONS(self) -> None:   # noqa: N802
        self._handle("OPTIONS")

    def _handle(self, method: str) -> None:
        try:
            if not self.app.host_ok(self.headers.get("Host")):
                return self._refuse(403, "this page answers only as 127.0.0.1 or localhost")
            if method != "GET" and (self.headers.get("X-Songcharter") != "1"
                                    or not self.app.origin_ok(self.headers.get("Origin"))):
                return self._refuse(403, "a request that changes something needs this page's own origin")
            path = urlsplit(self.path).path
            if method == "GET":
                return self._get(path)
            if method == "POST":
                return self._post(path)
            return self._refuse(405, f"{method} is not supported")
        except Refused as e:
            self._refuse(e.code, str(e))
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as e:  # noqa: BLE001  a bug: logged, answered 500, the server stays up
            self.app.log(f"internal error on {method} {self.path}:\n{traceback.format_exc()}")
            try:
                self._json(500, {"error": f"internal error: {type(e).__name__}: {e}"})
            except OSError:
                pass

    def _get(self, path: str) -> None:
        app = self.app
        if path == "/api/hello":
            return self._json(200, {"app": APP, "version": __version__, "token": app.token, "url": app.url})
        if path == "/api/status":
            return self._json(200, app.status())
        if path == "/api/jobs/current":
            job = app.jobs.current
            if job is None:
                return self._refuse(404, "no job yet")
            return self._json(200, job.snapshot())
        if path == "/api/jobs/current/events":
            return self._events()
        name = "index.html" if path == "/" else path[1:]
        if name in app.static:   # an exact name: no path is joined from the request
            return self._send(200, app.static[name], STATIC_TYPES.get(Path(name).suffix, "application/octet-stream"))
        return self._refuse(404, "not found")

    def _post(self, path: str) -> None:
        app = self.app
        if path == "/api/upload":
            return self._json(200, self._upload())
        if path == "/api/jobs":
            body = self._read_json()
            upload = read_upload(app.home, body.get("upload"))
            if upload is None:
                raise Refused(400, f"no such upload: {body.get('upload')!r} (upload the song file again)")
            try:
                job = app.jobs.start(upload, body.get("options"), auto_device=app.auto_device())
            except JobRunning as e:
                raise Refused(409, f"a chart is running already (job {e})") from None
            except InputError as e:
                raise Refused(400, str(e)) from None
            return self._json(202, {"job": job.id})
        if path == "/api/jobs/current/cancel":
            self._drain()
            try:
                job = app.jobs.cancel()
            except NotRunning:
                raise Refused(409, "no chart is running") from None
            return self._json(200, {"job": job.id, "state": job.state})
        raise Refused(404, "not found")

    def _length(self, limit: int) -> int:
        raw = self.headers.get("Content-Length")
        if raw is None:
            raise Refused(411, "the request needs a Content-Length")
        try:
            n = int(raw)
        except ValueError:
            raise Refused(400, f"Content-Length {raw!r} is not a number") from None
        if n < 0:
            raise Refused(400, f"Content-Length {raw!r} is not a number")
        if n > limit:
            raise Refused(413, f"{n} bytes is over the limit of {limit} bytes")
        return n

    def _read_json(self) -> dict:
        n = self._length(MAX_JSON)
        self.body_read = True
        data = self.rfile.read(n)
        try:
            value = json.loads(data.decode("utf-8")) if data else {}
        except (UnicodeDecodeError, ValueError):
            raise Refused(400, "the request body is not JSON") from None
        if not isinstance(value, dict):
            raise Refused(400, "the request body is a JSON object")
        return value

    def _upload(self) -> dict:
        try:
            name = unquote(self.headers.get("X-Filename") or "", errors="strict")
        except UnicodeDecodeError:
            raise Refused(400, "X-Filename is not percent-encoded UTF-8") from None
        name = PureWindowsPath(name.replace("\0", "")).name   # no folder, whichever separator it uses
        stem, ext = os.path.splitext(name)
        if ext.lower() not in AUDIO:
            raise Refused(415, f"{name or 'that file'} is not a song file songcharter takes "
                               f"({', '.join(AUDIO)})")
        n = self._length(MAX_UPLOAD)
        folder = uploads_folder(self.app.home)
        folder.mkdir(parents=True, exist_ok=True)
        part = folder / f".incoming-{secrets.token_hex(8)}.part"
        sha = hashlib.sha256()
        self.body_read = True
        try:
            with open(part, "wb") as f:
                left = n
                while left > 0:
                    got = self.rfile.read(min(left, CHUNK))
                    if not got:
                        raise Refused(400, f"the upload stopped after {n - left} of {n} bytes")
                    sha.update(got)
                    f.write(got)
                    left -= len(got)
            key = sha.hexdigest()
            target = folder / key[:cache.KEY_HEX]
            target.mkdir(exist_ok=True)
            dest = target / (cache.safe_name(stem) + ext.lower())
            os.replace(part, dest)
        finally:
            part.unlink(missing_ok=True)
        from .. import pipeline   # numpy loads with it
        tags = pipeline.read_tags(dest)
        meta, origin = pipeline.song_metadata(Path(name), tags, {})   # the name as dropped, not its safe form
        record = {"id": target.name, "name": name, "file": dest.name, "bytes": n, "sha256": key, "metadata": meta,
                  "origin": origin, "uploaded": time.time()}
        tmp = target / "upload.json.part"
        tmp.write_text(json.dumps(record, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        os.replace(tmp, target / "upload.json")
        os.utime(target)
        self.app.log(f"upload {target.name}: {name} ({n} bytes)")
        return {"id": target.name, "name": name, "bytes": n, "tags": meta, "origin": origin}

    def _events(self) -> None:
        job = self.app.jobs.current
        if job is None:
            return self._refuse(404, "no job yet")
        try:
            after = int(self.headers.get("Last-Event-ID", "")) + 1
        except ValueError:
            after = 0
        self.close_connection = True
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        self.end_headers()
        n = max(0, after)
        while True:
            new, ended = job.wait_events(n, KEEPALIVE_S)
            if not new and not ended:
                self.wfile.write(b": keepalive\n\n")
                self.wfile.flush()
                continue
            for event in new:
                self.wfile.write(f"id: {n}\ndata: {json.dumps(event, ensure_ascii=False)}\n\n".encode("utf-8"))
                n += 1
                if event.get("event") in CLOSING:
                    self.wfile.flush()
                    return
            self.wfile.flush()
            if ended and not new:
                return


class Server(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address: tuple[str, int], app: App):
        self.app = app
        super().__init__(address, Handler)


# ------------------------------------------------------------------------------------------------ startup

def hello(port: int, host: str = "127.0.0.1", timeout: float = HELLO_TIMEOUT_S) -> dict | None:
    """What /api/hello answers on that port, when it is songcharter's, else None."""
    try:
        with urllib.request.urlopen(f"http://{host}:{port}/api/hello", timeout=timeout) as r:
            value = json.loads(r.read(4096).decode("utf-8"))
    except (OSError, ValueError, urllib.error.URLError):
        return None
    return value if isinstance(value, dict) and value.get("app") == APP else None


def find_running(ports: Iterable[int]) -> tuple[int, dict] | None:
    """The first port where songcharter's server answers already, with its hello."""
    for port in ports:
        got = hello(port)
        if got is not None:
            return port, got
    return None


def wsl_address() -> str | None:
    """WSL's own address: the first of `hostname -I`, else None."""
    try:
        out = subprocess.run(["hostname", "-I"], capture_output=True, text=True, timeout=5,
                             stdin=subprocess.DEVNULL).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    words = out.split()
    return words[0] if words else None


def windows_check(app: App, curl: Callable[[str], str | None] = wsl.windows_curl) -> Callable[[int], bool]:
    """The self-check: whether Windows' curl.exe reaches this instance on localhost:<port> (its token answers)."""
    def check(port: int) -> bool:
        answer = curl(f"http://localhost:{port}/api/hello")
        try:
            got = json.loads(answer) if answer else None
        except ValueError:
            got = None
        ok = isinstance(got, dict) and got.get("token") == app.token
        if not ok:
            app.log(f"port {port}: Windows' localhost:{port} " + ("does not answer" if answer is None else
                                                                   "answers another program"), console=False)
        return ok
    return check


class NoPort(Exception):
    pass


def _serve(server: Server) -> threading.Thread:
    t = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.2},
                         name=f"songcharter-ui-{server.server_address[1]}", daemon=True)
    t.start()
    return t


def bind(app: App, ports: Iterable[int], check: Callable[[int], bool] | None = None,
         address: Callable[[], str | None] = wsl_address, local: str = "127.0.0.1") -> list[Server]:
    """The servers, serving: on the first free port of `ports` that passes `check` (None: no check, the first free
    port), with app.url set; else (every free port failed the check) the first free port again, also on
    `address()`'s address when it gives one, which the guards then allow. NoPort when no port is free. A port 0 is
    one the system picks (tests)."""
    ports = list(ports)
    first = None
    for port in ports:
        try:
            server = Server((local, port), app)
        except OSError:
            continue
        port = server.server_address[1]
        app.allow("127.0.0.1", port)
        app.allow("localhost", port)
        _serve(server)
        if check is None or check(port):
            app.url = f"http://{'localhost' if check is not None else '127.0.0.1'}:{port}/"
            return [server]
        server.shutdown()
        server.server_close()
        app.disallow("127.0.0.1", port)
        app.disallow("localhost", port)
        first = port if first is None else first
    if first is None:
        raise NoPort(f"no free port in {', '.join(map(str, ports))}")
    try:
        server = Server((local, first), app)
    except OSError as e:
        raise NoPort(f"port {first} was taken meanwhile ({e})") from None
    app.allow("127.0.0.1", first)
    app.allow("localhost", first)
    servers = [server]
    _serve(server)
    ip = address()
    app.url = f"http://127.0.0.1:{first}/"
    if ip:
        try:
            extra = Server((ip, first), app)
        except OSError as e:
            app.log(f"Windows' localhost does not reach WSL here, and WSL's address {ip} cannot be bound ({e}): "
                    f"the page is at {app.url} inside WSL only")
            return servers
        app.allow(ip, first)
        _serve(extra)
        servers.append(extra)
        app.url = f"http://{ip}:{first}/"
    app.log(f"Windows' localhost does not reach WSL here (localhostForwarding off, or the port is taken); using "
            f"{app.url}")
    return servers


def open_browser(url: str, in_wsl: bool) -> bool:
    try:
        return wsl.open_url(url) if in_wsl else webbrowser.open(url)
    except Exception:  # noqa: BLE001  no browser: the URL is printed anyway
        return False


def main(port: int | None = None, browser: bool = True, from_shortcut: bool = False, home: Path | None = None) -> int:
    """`songcharter ui` (the module docstring). Exit 0 when it stopped (or another one is running), 2 when it cannot
    start (no free port, a home it cannot write), 3 for a bug."""
    try:
        return _main(port, browser, from_shortcut, home)
    except KeyboardInterrupt:
        return 0
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        print("songcharter: internal error (a bug, please report it with the traceback above)", file=sys.stderr)
        return 3


def _main(port: int | None, browser: bool, from_shortcut: bool, home: Path | None) -> int:
    if port is not None and not 1 <= port <= 65535:
        print(f"songcharter: error: --port is 1 to 65535, not {port}", file=sys.stderr)
        return 2
    ports = [port] if port is not None else list(PORTS)
    in_wsl = wsl.is_wsl()
    running = find_running(ports)
    if running is not None:
        url = running[1].get("url") or f"http://{'localhost' if in_wsl else '127.0.0.1'}:{running[0]}/"
        print(f"songcharter is running already: {url}")
        if browser:
            open_browser(url, in_wsl)
        return 0
    root = Path(home) if home is not None else default_home()
    try:
        (root / "logs").mkdir(parents=True, exist_ok=True)
    except OSError as e:
        print(f"songcharter: error: cannot write {root / 'logs'}: {e}", file=sys.stderr)
        return 2
    log = Log(root / "logs" / f"ui-{time.strftime('%Y%m%d')}.log")
    log(f"songcharter {__version__} ui: home {root}" + (", started from the Start-menu shortcut" if from_shortcut
                                                         else ""))
    gone = prune_uploads(root)
    if gone:
        log(f"uploads older than {UPLOAD_DAYS} days deleted: {len(gone)}")
    app = App(root, log=log)
    threading.Thread(target=app.doctor, name="songcharter-doctor", daemon=True).start()   # the header, in advance
    check = windows_check(app) if in_wsl and wsl.interop_ok() else None
    try:
        servers = bind(app, ports, check)
    except NoPort as e:
        log(f"songcharter: error: {e}: close the program that uses them, or pass --port")
        return 2
    stop = threading.Event()

    def on_signal(signum, frame) -> None:
        log(f"{signal.Signals(signum).name}: stopping")
        stop.set()

    for sig in (signal.SIGTERM, signal.SIGHUP):
        signal.signal(sig, on_signal)
    assert app.url is not None
    log(f"songcharter is at {app.url} (Ctrl+C or closing this window stops it)")
    if browser and not open_browser(app.url, in_wsl):
        log("no browser opened: open the address above")
    try:
        while not stop.wait(0.5):
            pass
    except KeyboardInterrupt:
        log("Ctrl+C: stopping")
    finally:
        app.jobs.shutdown()
        for server in servers:
            server.shutdown()
            server.server_close()
        log("stopped")
    return 0
