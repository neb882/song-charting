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
     on Windows, or none) moves to the next port. When no port of the range passes, the **fallback**, only under NAT
     (`fallback_address`): the first free port again, and also WSL's own address on that port, allowed as a host and
     an origin too, logged as such. That address is the source of WSL's default route, not a bridge's such as
     Docker's (`wsl_address`), and it must lie in WSL's NAT range 172.16.0.0/12: on WSL's host-only NAT network it
     is no wider than localhost [inference]. **The server never listens on an address another machine can reach:**
     under mirrored networking (or any networkingMode but NAT) the Linux side carries the PC's own LAN addresses, and
     the guards stop browsers, not a program on the LAN. So with mirrored networking, no address, or one outside that
     range, it stops instead (exit 2) with what to try and where the log is (`unreachable`).
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
    `data: <json>`; a comment every 15 s keeps the connection open; it closes after `result`, `error` or `cancelled`,
    once the job's process has exited (up to 10 s more), so the state is final then. A Last-Event-ID header resumes
    after that index.
  * POST /api/jobs/current/cancel: 200 with the job's state after the cancel; 409 when no job runs.

**After the build** (M4-06). The routes on "the chart" use the current job's `result` event; those that export or
install need one that passed its gate (else 400): a .failed folder is for a look, not for Clone Hero.
  * GET /api/jobs/current/results: {"job", "state", "ok", "folder", "name", "installable", "preview", "lyrics"}:
    the preview's overview and pages as URLs with its flags and remarks, or {"why"} there is none; pipeline.json's
    lyrics as counts ({"given", "added", "words", "phrases", "why", "low"}), null when none were given. 404 before
    the first job.
  * GET /api/jobs/current/preview/<name>: only overview.png and page_NN.png from the result's preview folder (the
    work folder's preview/), by an exact pattern; anything else 404.
  * POST /api/jobs/current/export/zip: clonehero.export_zip into $SONGCHARTER_HOME/exports/<name>.zip; answers
    {"url": "/api/exports/<name>.zip", "name", "windows_path"}. GET /api/exports/<name>.zip downloads it
    (Content-Disposition: attachment): a single name ending .zip that is a file in exports/; anything else 404.
  * GET /api/clonehero: clonehero.describe ({"folder", "windows_path", "source", "under_onedrive", "guess"}).
    POST /api/clonehero {"folder"}: clonehero.set_songs_folder (400 with why when it does not exist or cannot be
    written), then the same answer.
  * POST /api/jobs/current/install {"replace"}: clonehero.install of the chart into the Songs folder (no path comes
    from the page): 200 {"installed", "windows_path", "replaced", "note"}; 400 with no chart or no Songs folder;
    409 {"exists", "ours", "folder", "windows_path"} when that folder is there (a replace of one songcharter did not
    make is refused the same way); 403 {"blocked", "why", "zip_url", "under_onedrive"}, after making the zip, when
    Windows did not let it finish. One install at a time.
  * POST /api/open {"what": "song" | "exports"}: explorer.exe on the last installed song's folder or the exports
    folder (wsl.open_url with its Windows path), only those two; {"opened", "path", "windows_path"}.
  * GET /api/diagnostics: the diagnostics bundle (diagnostics.py) as a download, songcharter-diagnostics-<stamp>.zip.

**The lyrics** a job is given never reach a log, a record or an answer here: the request's body is never logged, the
job's options say only whether there are some, and its errors name the option, never the text (jobs.py).
"""
from __future__ import annotations

import hashlib
import ipaddress
import json
import os
import secrets
import re
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
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
from urllib.parse import quote, unquote, urlsplit

from .. import __version__, cache, clonehero, device, diagnostics, wsl
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
END_WAIT_S = 10.0                  # after a closing event, the stream waits this long for the job's process to exit
HELLO_TIMEOUT_S = 0.5
CHUNK = 1 << 20
STATIC_TYPES = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
                ".css": "text/css; charset=utf-8"}
PREVIEW_NAME = re.compile(r"^(?:overview|page_\d{2,3})\.png$")   # preview.py's files: overview.png, page_01.png, ...
PREVIEW_PAGE = re.compile(r"^page_\d{2,3}\.png$")
OPEN = ("song", "exports")         # POST /api/open's only two folders


def console_line(text: str) -> None:
    """A line on the console (stdout), unbuffered: once the window has closed, a write raises at once (EIO) and
    nothing stays in a buffer for the interpreter's exit to fail on."""
    os.write(1, (text + "\n").encode(sys.stdout.encoding or "utf-8", "replace"))


class Log:
    """The UI's log: each line with its time into the log file (when there is one) and, unless `console` is false,
    the console window. Neither failing stops anything: a console the friend has closed (every write then raises
    EIO) is given up, and the rest of the stop (the job's tree, the servers) goes on."""

    def __init__(self, path: Path | None = None, console: Callable[[str], None] | None = None):
        self.path = path
        self.console: Callable[[str], None] | None = console if console is not None else console_line
        self._lock = threading.Lock()

    def __call__(self, text: str, console: bool = True) -> None:
        with self._lock:
            if self.path is not None:
                try:
                    with open(self.path, "a", encoding="utf-8", errors="replace") as f:
                        f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {text}\n")
                except OSError:
                    pass
            if console and self.console is not None:
                try:
                    self.console(text)
                except (OSError, ValueError):   # the window is gone (EIO), or stdout closed
                    self.console = None


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
        self.install_lock = threading.Lock()   # one install (or Songs folder change) at a time
        self.installed: Path | None = None     # the song folder the last install put into Clone Hero's Songs
        self._documents: tuple[Path | None] | None = None
        self._documents_lock = threading.Lock()

    # --- Clone Hero
    def documents(self) -> Path | None:
        """<Documents>/Clone Hero/Songs (clonehero.documents_songs), asked of Windows once: Documents does not move
        while the page runs."""
        with self._documents_lock:
            if self._documents is None:
                self._documents = (clonehero.documents_songs(),)
            return self._documents[0]

    def clonehero(self) -> dict:
        return clonehero.describe(self.home, self.documents)

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
        if path == "/api/jobs/current/results":
            job = app.jobs.current
            if job is None:
                return self._refuse(404, "no job yet")
            return self._json(200, results(job))
        if path.startswith("/api/jobs/current/preview/"):
            return self._preview(unquote(path[len("/api/jobs/current/preview/"):]))
        if path.startswith("/api/exports/"):
            return self._export(unquote(path[len("/api/exports/"):]))
        if path == "/api/clonehero":
            return self._json(200, app.clonehero())
        if path == "/api/diagnostics":
            return self._diagnostics()
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
        if path == "/api/jobs/current/export/zip":
            self._drain()
            out = clonehero.export_zip(self._built(), app.home)
            app.log(f"exported {out}")
            return self._json(200, {"url": export_url(out.name), "name": out.name,
                                    "windows_path": clonehero.windows_path(out)})
        if path == "/api/clonehero":
            folder = self._read_json().get("folder")
            if not isinstance(folder, str):
                raise Refused(400, "folder is the Songs folder's path, as text")
            with app.install_lock:
                try:
                    saved = clonehero.set_songs_folder(app.home, folder)
                except InputError as e:
                    raise Refused(400, str(e)) from None
            app.log(f"the Clone Hero Songs folder is {saved}")
            return self._json(200, app.clonehero())
        if path == "/api/jobs/current/install":
            return self._install(self._read_json().get("replace") is True)
        if path == "/api/open":
            return self._open(self._read_json().get("what"))
        raise Refused(404, "not found")

    # --- after the build
    def _built(self) -> Path:
        """The current job's song folder, when its chart passed the gate and is in place; else Refused(400)."""
        job = self.app.jobs.current
        result = job.result() if job is not None else None
        if result is None or job.state != "done":
            raise Refused(400, "no finished chart yet")
        folder = Path(str(result.get("folder")))
        if not result.get("ok"):
            raise Refused(400, f"the chart did not pass its check: it is in {folder} for a look, not for Clone Hero")
        if not folder.is_dir():
            raise Refused(400, f"the chart's folder {folder} is not there any more")
        return folder

    def _preview(self, name: str) -> None:
        job = self.app.jobs.current
        result = job.result() if job is not None else None
        folder = result.get("preview") if result else None
        if not folder or not PREVIEW_NAME.match(name):
            return self._refuse(404, "not found")
        path = Path(folder) / name
        try:
            data = path.read_bytes()
        except OSError:
            return self._refuse(404, "not found")
        return self._send(200, data, "image/png")

    def _export(self, name: str) -> None:
        folder = self.app.home / clonehero.EXPORTS
        # one name, no folder: no separator of either kind, so ".." cannot climb (a name may hold "...", as a song's
        # does), nor a leading dot (the .part files)
        if not name.endswith(".zip") or name.startswith(".") or "/" in name or "\\" in name or "\0" in name:
            return self._refuse(404, "not found")
        path = folder / name
        if path.parent != folder or not path.is_file():
            return self._refuse(404, "not found")
        return self._download(path, name)

    def _download(self, path: Path, name: str) -> None:
        """A file as an attachment, streamed: the browser saves it into Downloads."""
        size = path.stat().st_size
        ascii_name = name.encode("ascii", "replace").decode().replace("?", "_").replace('"', "_")
        self.send_response(200)
        self.send_header("Content-Type", "application/zip")
        self.send_header("Content-Length", str(size))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Disposition",
                         f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(name, safe='')}")
        self.end_headers()
        if self.command == "HEAD":
            return
        with open(path, "rb") as f:
            shutil.copyfileobj(f, self.wfile, CHUNK)

    def _diagnostics(self) -> None:
        app = self.app
        name = f"songcharter-diagnostics-{time.strftime('%Y%m%d-%H%M%S')}.zip"
        with tempfile.TemporaryDirectory(prefix="songcharter-diagnostics-") as tmp:
            out = diagnostics.bundle(app.home, Path(tmp) / name, report=app._report,
                                     clonehero_info=lambda home: app.clonehero())
            app.log(f"diagnostics: {name} ({out.stat().st_size} bytes)")
            self._download(out, name)

    def _install(self, replace: bool) -> None:
        app = self.app
        song = self._built()
        with app.install_lock:
            songs, source = clonehero.songs_folder(app.home, app.documents)
            if songs is None:
                raise Refused(400, "no Clone Hero Songs folder is known: give it first")
            try:
                done = clonehero.install(song, songs, app.home, replace=replace)
            except clonehero.Exists as e:
                return self._json(409, {"error": str(e), "exists": True, "ours": e.ours, "folder": str(e.target),
                                        "windows_path": clonehero.windows_path(e.target)})
            except clonehero.Blocked as e:
                out = clonehero.export_zip(song, app.home)
                app.log(f"install into {songs} blocked ({e.why}); the zip is {out}")
                return self._json(403, {"error": e.why, "blocked": True, "why": e.why, "zip_url": export_url(out.name),
                                        "under_onedrive": clonehero.under_onedrive(songs)})
            except InputError as e:
                raise Refused(400, str(e)) from None
            app.installed = done.target
        app.log(f"installed {done.target}" + (f"; the older chart went to {done.replaced}" if done.replaced else "")
                + (f"; {done.note}" if done.note else ""))
        return self._json(200, {"installed": str(done.target), "windows_path": clonehero.windows_path(done.target),
                                "replaced": None if done.replaced is None else str(done.replaced),
                                "note": done.note})

    def _open(self, what: Any) -> None:
        app = self.app
        if what not in OPEN:
            raise Refused(400, f"what is one of {', '.join(OPEN)}")
        if what == "song":
            if app.installed is None or not app.installed.is_dir():
                raise Refused(400, "no song was installed into Clone Hero from this page")
            folder = app.installed
        else:
            folder = app.home / clonehero.EXPORTS
            folder.mkdir(parents=True, exist_ok=True)
        winpath = clonehero.windows_path(folder)
        opened = winpath is not None and wsl.open_url(winpath)
        return self._json(200, {"opened": bool(opened), "path": str(folder), "windows_path": winpath})

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
                    job.wait_end(END_WAIT_S)   # so a closed stream means a final state: a new job may start
                    return
            self.wfile.flush()
            if ended and not new:
                return


def export_url(name: str) -> str:
    return "/api/exports/" + quote(name, safe="")


def _preview_why(pv: Any) -> str:
    """Why there is no preview, from pipeline.json's `preview`."""
    if not isinstance(pv, dict):
        return "the run left no record of it"
    if pv.get("skipped") == "turned off":
        return "it was turned off in the options"
    if pv.get("skipped"):
        return f"it needs matplotlib and librosa ({pv['skipped']})"
    if pv.get("error"):
        return f"it failed ({pv['error']})"
    return "its pictures are not there any more"


def results(job) -> dict:
    """GET /api/jobs/current/results (the module docstring), from the job's result event and its pipeline.json."""
    result = job.result()
    out: dict[str, Any] = {"job": job.id, "state": job.state, "ok": None, "folder": None, "name": None,
                           "installable": False, "preview": None, "lyrics": None}
    if result is None:
        return out
    folder = Path(str(result.get("folder")))
    out.update(ok=bool(result.get("ok")), folder=str(folder), name=folder.name,
               installable=bool(result.get("ok")) and job.state == "done" and folder.is_dir())
    try:
        pipeline = json.loads((Path(str(result.get("work"))) / "pipeline.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        pipeline = {}
    pipeline = pipeline if isinstance(pipeline, dict) else {}
    pv = pipeline.get("preview")
    where = Path(result["preview"]) if result.get("preview") else None
    if where is not None and (where / "overview.png").is_file():
        try:
            pages = sorted(p.name for p in where.iterdir() if PREVIEW_PAGE.match(p.name))
        except OSError:
            pages = []
        base = "/api/jobs/current/preview/"
        pv = pv if isinstance(pv, dict) else {}
        out["preview"] = {"overview": base + "overview.png", "pages": [base + p for p in pages],
                          "flags": list(pv.get("flags") or []), "remarks": list(pv.get("remarks") or [])}
    else:
        out["preview"] = {"why": _preview_why(pv)}
    ly = pipeline.get("lyrics")
    if isinstance(ly, dict):
        out["lyrics"] = {"given": bool(ly.get("given")), "added": bool(ly.get("added")), "words": ly.get("words"),
                         "phrases": (ly.get("chart") or {}).get("phrases"), "why": ly.get("why"),
                         "low": bool((ly.get("confidence") or {}).get("low"))}
    return out


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


WSL_NAT = ipaddress.ip_network("172.16.0.0/12")   # WSL's NAT network [decision; that WSL picks a 172.x: inference]


def wsl_address() -> str | None:
    """WSL's own address: the source of its default route, `ip route get 1.1.1.1`'s `src`, else the source the
    kernel picks for a UDP socket connected to 1.1.1.1 (nothing is sent); None without a default route. Not
    `hostname -I`'s first, which can be a bridge's (Docker's 172.17.0.1), unreachable from Windows."""
    exe = shutil.which("ip")
    if exe:
        try:
            out = subprocess.run([exe, "route", "get", "1.1.1.1"], capture_output=True, text=True, timeout=5,
                                 stdin=subprocess.DEVNULL).stdout
        except (OSError, subprocess.SubprocessError):
            out = ""
        m = re.search(r"\bsrc\s+(\d+\.\d+\.\d+\.\d+)\b", out)
        if m:
            return m.group(1)
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("1.1.1.1", 53))
            return s.getsockname()[0]
    except OSError:
        return None


def fallback_address(networking_mode: str | None, address: Callable[[], str | None] | None = None
                     ) -> tuple[str | None, str]:
    """The address the fallback may listen on, or (None, why not): only under NAT (.wslconfig's networkingMode unset
    or nat), and only WSL's own NAT address (`address()`, default wsl_address, in 172.16.0.0/12), which no other
    machine reaches."""
    mode = (networking_mode or "nat").strip().lower()
    if mode != "nat":
        return None, (f"networkingMode={networking_mode} in .wslconfig: an address beside localhost would be the PC's "
                      "own, which other machines can reach")
    ip = (address or wsl_address)()
    if ip is None:
        return None, "WSL has no address of its own (no default route)"
    try:
        inside = ipaddress.ip_address(ip) in WSL_NAT
    except ValueError:
        inside = False
    if not inside:
        return None, (f"WSL's address {ip} is not on WSL's own NAT network ({WSL_NAT}), so it may be reachable "
                      "from other machines")
    return ip, ""


def unreachable(ports: list[int], why: str, log_path: Path | None) -> str:
    """The message when the page cannot be offered to Windows: why, what to try, where the details are."""
    span = f"port {ports[0]}" if len(ports) == 1 else f"ports {ports[0]}-{ports[-1]}"
    return (f"songcharter: error: Windows cannot reach this page: Windows' localhost did not answer on {span}, and "
            f"songcharter will not listen on another address ({why}). Try: close a program that uses those ports on "
            "Windows, or start songcharter with another port (songcharter ui --port 8800); or restart WSL "
            "(wsl --shutdown in PowerShell, then open Ubuntu again)."
            + (f" Details: {log_path}" if log_path is not None else ""))


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


class Unreachable(Exception):
    """No port passed the self-check, and no fallback address may be used (why: its message)."""


def _serve(server: Server) -> threading.Thread:
    t = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.2},
                         name=f"songcharter-ui-{server.server_address[1]}", daemon=True)
    t.start()
    return t


def bind(app: App, ports: Iterable[int], check: Callable[[int], bool] | None = None,
         fallback: Callable[[], tuple[str | None, str]] = lambda: fallback_address(None),
         local: str = "127.0.0.1") -> list[Server]:
    """The servers, serving: on the first free port of `ports` that passes `check` (None: no check, the first free
    port), with app.url set; else (every free port failed the check) the first free port again, also on the address
    `fallback()` allows (fallback_address), which the guards then allow too. NoPort when no port is free; Unreachable
    (no server left listening) when the fallback gives no address, or its address cannot be bound. A port 0 is one
    the system picks (tests)."""
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
    ip, why = fallback()
    if ip is None:
        raise Unreachable(why)
    try:
        extra = Server((ip, first), app)
    except OSError as e:
        raise Unreachable(f"WSL's address {ip} cannot be bound: {e}") from None
    try:
        server = Server((local, first), app)
    except OSError as e:
        extra.server_close()
        raise NoPort(f"port {first} was taken meanwhile ({e})") from None
    for host in ("127.0.0.1", "localhost", ip):
        app.allow(host, first)
    _serve(server)
    _serve(extra)
    app.url = f"http://{ip}:{first}/"
    app.log(f"Windows' localhost does not reach WSL here (localhostForwarding off, or the port is taken); using "
            f"{app.url}")
    return [server, extra]


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

    def fallback() -> tuple[str | None, str]:
        return fallback_address(wsl.wslconfig().get("networking_mode"))

    try:
        servers = bind(app, ports, check, fallback)
    except NoPort as e:
        log(f"songcharter: error: {e}: close the program that uses them, or pass --port")
        return 2
    except Unreachable as e:
        log(unreachable(ports, str(e), log.path))
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
        try:
            app.jobs.shutdown()
        finally:
            for server in servers:
                server.shutdown()
                server.server_close()
            log("stopped")
    return 0
