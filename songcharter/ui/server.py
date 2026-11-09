"""`songcharter ui [--port N] [--no-browser] [--from-shortcut]`: the local page's server (M4-04, DESIGN.md 4.5).

A standard-library ThreadingHTTPServer on 127.0.0.1 serves the page in static/ (vanilla JS, no CDN) and a small API;
one chart runs at a time as a child process group (jobs.py). In WSL the Windows browser opens it.

**Startup** (`main`):
  1. **Already running?** GET http://127.0.0.1:<port>/api/hello on 8765-8784 (or --port's alone): when one answers
     {"app": "songcharter"} with this version, its page opens (below) and this exits 0. One of another version (an
     update installed while the old server's window stayed open: its page would still say the update is out) is
     not reused: this stops with exit 2 (an InputError), saying to close the songcharter window first, and opens no
     page (M5-12). No request stops a server, and it may be running a chart: closing its window does (6. below).
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
     than 7 days go, but those the queue's waiting songs name (jobs.queued_uploads).
  6. **Stops** on SIGHUP or SIGTERM (the window closes) and Ctrl+C: a running job's tree is killed first, and its
     song goes back to waiting at the top of the queue (Queue.shutdown). A page that closes does not stop it. A
     server killed outright (SIGKILL, a crash) cannot: its chart runs on, and the next start stops it before it
     reads the queue (jobs.stop_orphan, by <home>/state/chart.pid; a second advisor's finding 7).

**The update notice** (M5-07): once the first page (index.html) has been served, never before (nothing on the
startup path waits on the network, or asks it), a daemon thread runs updates.check once per server process: at most
one request a day to GitHub's releases, kept in $SONGCHARTER_HOME/state/update.json. Its one line goes to the log
file, and /api/status carries what it found; the page shows the notice with the install line and a Copy button.
Nothing is downloaded or installed; charting never waits for it.

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
    events), the defaults with threads_default, and `update`: {"version", "line", "url"} once the update check found
    a newer release (`line` null when its SHA256SUMS could not be read), else null (before the check has run too).
  * POST /api/upload: the raw file as the body, X-Filename its name (percent-encoded). An extension not in AUDIO: 415;
    over 1 GB: 413; no Content-Length: 411. Streamed to uploads/<16 hex of its SHA-256>/<cache.safe_name(stem)><ext>,
    with upload.json beside it; answers {"id", "name", "bytes", "tags", "origin", "seconds", "choices"}: the song.ini
    values the chart would take from the tags or the file's name (pipeline.read_tags and song_metadata), where each
    came from, the song's length as ffmpeg's header gives it (estimate.duration; null when it cannot say), and the
    options screen's Best or Quick (M8-04, `App.choices`): {"gpu", "best", "quick"}, `gpu` when the doctor summary
    charts the guitar on the GPU, `best` estimate.for_job's range with every option at its default, `quick` with 1
    take (null off the GPU).
  * POST /api/upload/image (M4-11): a picture for the album art or the background, as the song is uploaded (the same
    guards, folder and pruning; upload.json's kind "image"). An extension not in art.EXTENSIONS: 415; over
    art.MAX_BYTES (20 MB): 413. It must decode as art.py's checks say (a JPEG, PNG or WebP within its pixel limit),
    else 415 with why, and nothing is kept. Answers {"id", "name", "bytes", "format", "width", "height"}.
  * POST /api/jobs {"upload", "options"} (M8-10): the song added to the queue (jobs.Queue), which starts it at once
    when nothing charts and none waits: 202 {"job" (null when it waits), "entry", "state": "charting" or "waiting"};
    400 for bad options (Options.check()'s message, checked when it is added), an unknown upload, or lyrics in a
    song that would wait (jobs.LYRICS_WAIT); 409 with jobs.QUEUE_MAX songs waiting. The options' `album_art` and `background` are image upload ids, which become the
    images' paths here (an unknown one, or a song's: 400), so no path ever comes from the page. The job gets its
    estimate here (M7-10: estimate.for_job, from the upload's length, the options, and the doctor summary's device
    and guitar device); a bug in it is logged, and the chart starts without one.
  * GET /api/jobs/current: its state (running, done, failed, cancelled), its `estimate` ({"seconds", "takes",
    "device", "low_s", "high_s", "low_min", "high_min"}, or null), its `remaining` (M8-04: estimate.remaining, the
    time left once the first take is timed, or null) and events; 404 before the first job.
  * GET /api/jobs/current/events: Server-Sent Events. Every event so far, then each new one, as `id: <index>` and
    `data: <json>`; a comment every 15 s keeps the connection open; it closes after `result`, `error` or `cancelled`,
    once the job's process has exited (up to 10 s more), so the state is final then. A Last-Event-ID header resumes
    after that index. GET /api/jobs/<id>/events is the same for the job of that id, which is what the page follows
    (the v0.5.0 review's correct-2): `current`'s index would be applied to whichever job is current, and the queue
    starts the next song by itself, so a page whose connection dropped while one song ended and the next started
    got the next song's events from the old index on, as the old song's. By id, a reconnect resumes within that job
    only; once it has ended and is no longer current, its closing event alone comes (the end the page missed), and
    the page then follows the next song from its first event.
  * POST /api/jobs/current/cancel: 200 with the job's state after the cancel; 409 when no job runs.
  * The queue (M8-10, DESIGN.md 4.5): GET /api/queue (also /api/status's `queue`): {"paused" (null, "restart",
    "you", "failures" or "disk", only while a song waits), "why" (the disk's), "restarted" (the songs that were
    waiting when songcharter closed), "run", "max", "entries" ({"id", "run", "name", "chart", "state" (waiting,
    charting, ready, check_failed, not_finished, cancelled), "job", "estimate", "added", "started", "ended",
    "error"}), "left" ({"low_s", "high_s", "songs"}: the whole queue's time left, or null)}. POST /api/queue/pause
    (after this song; 409 when none waits), /api/queue/carry-on, /api/queue/clear (every song but the charting
    one), /api/queue/remove {"entry"} (409 for the charting one or none): each answers the queue. A cancel ends the
    charting song only, and the next starts.
  * **By job id** (M8-10): every route below on "current" also takes a job's id (/api/jobs/<yyyyMMdd-HHmmss[-n]>/...,
    JOB_PATH), for a finished song's Done screen once the next has started: the current job, or the queue's record
    of a finished one (jobs.Kept, from queue.json after a restart too), or, once the list has dropped it (Clear the
    list, Remove, the trim), its chart in the library (jobs.Queue.dropped_chart: the server's own record of its
    result's folder, for the server's life; never a path from the page), named by its job id, so a Look still open
    on it keeps working; GET /api/jobs/<id> is its snapshot, with its closing event. The results' URLs name the job
    as the request did. The events by id (above);
    POST /api/jobs/<id>/cancel cancels only while that job is the running one (409 "that chart has ended"
    otherwise: a Cancel confirmed after its song ended never reaches the next, M8-10's review S-S1). POST
    /api/open {"what": "built", "job"} opens that job's folder.
  * **Your charts** (M8-13, DESIGN.md 4.5): GET /api/library: {"charts"}, every chart in <home>/library newest first
    (jobs.library: {"id", "folder", "name", "artist", "time", "readable", "ok", "audio", "stems", "look"}). A chart's
    id (`<16 hex>:<its folder's name>`, jobs.LIBRARY_ID, percent-encoded in a URL) is a job id too: the routes by id
    take it (jobs.Charted, looked up among the library's folders, never made into a path), so the list's Install
    (/install, its 409 as for a job), Open (/api/open {"what": "built", "job": <its id>}), Download the stems
    (/export/stems) and Look (GET /api/jobs/<id> and its /results, the preview and Listen, while its work folder is
    in the cache) are the queue's own routes behind the same guards. POST /api/open's `job`, when given, must be
    one of these ids (400 otherwise: never a path). Nothing deletes a chart.

**After the build** (M4-06). The routes on "the chart" use the job's `result` event (the current one's, or by id); those that export or
install need one that passed its gate (else 400): a .failed folder is for a look, not for Clone Hero. A job whose
`result` is out has its chart in place (the chart prints it last), so these routes take it at once, while its process
is still exiting (a second or more, with its state still `running`): the page asks for the results the moment it
reads that event (the release gate's finding: the Done screen once hid "Install into Clone Hero" after a normal chart).
  * GET /api/jobs/current/results: {"job", "state", "ok", "folder", "name", "windows_path", "installable",
    "preview", "lyrics", "art", "listen", "stems"} (`windows_path`: the folder's, Open folder's hover text): the preview's
    overview and pages as URLs with its flags and remarks, `page_s` (PAGE_S, the seconds a page shows) and `at`, for
    each flag {"part", "start", "page"} (`flag_at`: its start read from its text, its page floor(start / page_s) + 1
    within the pages there are) or null, or {"why"} there is none;
    pipeline.json's lyrics as counts ({"given", "added", "words", "phrases", "why", "low"}), null when none were
    given; the folder's art ({"album_art": its URL or null, "album_from": "embedded", "given" or null,
    "background": whether there is one}); what the Listen control offers ({"parts": {"guitar": ["expert", ...],
    ...}}, the parts with notes and their levels, with "why" when the chart could not be read); the stems the run
    saved ({"name", "files", "bytes"}: the stems folder's name, its .flac files and their size), {"why"} in plain words
    when they were asked for and not saved (pipeline.json's stems.why: the disk filled), null without. 404 before the
    first job.
  * GET /api/jobs/current/art/album.jpg: the result's album art (image/jpeg), that one name only; anything else 404.
  * GET /api/jobs/current/preview/<name>: only overview.png and page_NN.png from the result's preview folder (the
    work folder's preview/), by an exact pattern; anything else 404.
  * POST /api/jobs/current/export/zip: clonehero.export_zip into $SONGCHARTER_HOME/exports/<name>.zip; answers
    {"url": "/api/exports/<name>.zip", "name", "windows_path"}. GET /api/exports/<name>.zip downloads it
    (Content-Disposition: attachment): a single name ending .zip that is a file in exports/; anything else 404.
    POST /api/jobs/current/export/stems (M8-12): the same for the stems folder the run saved ("<song> (stems).zip",
    stored without compression: FLAC does not shrink), a gate that failed too (the stems do not depend on the
    chart); 400 when the run saved none or they are not there any more. A stems zip is about 190 MB for 4 minutes,
    so it is deleted once its GET has sent it, and a new one deletes any other stems zip left there (a download never
    fetched): exports/ never keeps more than the one being fetched (M8-12's review).
  * GET /api/clonehero: clonehero.describe ({"folder", "windows_path", "source", "under_onedrive", "guess"}), with
    `guess` (<Documents>\\Clone Hero\\Songs, Windows' form) always given, not only when no folder is found (M8-04).
    POST /api/clonehero {"folder"}: clonehero.set_songs_folder (400 with why when it does not exist or cannot be
    written), then the same answer.
  * POST /api/jobs/current/install {"replace"}: clonehero.install of the chart into the Songs folder (no path comes
    from the page): 200 {"installed", "windows_path", "replaced", "note"}; 400 with no chart or no Songs folder;
    409 {"exists", "ours", "folder", "windows_path"} when that folder is there (a replace of one songcharter did not
    make is refused the same way); 403 {"blocked", "why", "zip_url", "under_onedrive", "older"}, after making the
    zip, when Windows did not let it finish (`older`: where the older chart stays when it could not be put back,
    also named in `why`). One install at a time.
  * POST /api/open {"what": "song" | "exports" | "built"}: explorer.exe (wsl.open_url with its Windows path) on the
    last installed song's folder, the exports folder, or the current result's folder (M8-04: "Open folder" before an
    install, and for a build that failed its check, which is for a look), only those three: no path is read from the
    request; {"opened", "path", "windows_path"}.
  * GET /api/diagnostics: the diagnostics bundle (diagnostics.py) as a download, songcharter-diagnostics-<stamp>.zip.
  * POST /api/jobs/current/listen {"part", "level"} (M6-09): listen.cached renders that part and level of the
    result's chart (a gate that failed too: it is for a look) over the song, into the work folder's listen/ (a few
    seconds; the same chart's render is there already the next time), one render at a time; 200 {"url", "part",
    "level", "cached", "seconds"}; 400 for a part or level not among INSTRUMENTS and DIFFICULTIES, or not in the
    chart, or no finished chart yet; 500 with why when ffmpeg fails or the render cannot be written. GET /api/jobs/current/listen/<part>-<level>.ogg (audio/ogg, with byte ranges,
    so the player can seek) serves only a file this server rendered for the current job, looked up by that name
    in what the POST recorded: no path from the request reaches the file system; anything else 404.

**The lyrics** a job is given never reach a log, a record or an answer here: the request's body is never logged, the
job's options say only whether there are some, and its errors name the option, never the text (jobs.py).
"""
from __future__ import annotations

import errno
import hashlib
import ipaddress
import json
import math
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

from .. import __version__, cache, clonehero, device, diagnostics, listen, updates, wsl
from .. import art as ART
from ..errors import InputError, ToolError
from ..timed import DIFFICULTIES, INSTRUMENTS
from . import estimate
from . import home as default_home
from .jobs import (CLOSING, LIBRARY_ID, ChartOptions, Charted, Job, Jobs, JobRunning, NotInQueue, NotRunning, Queue,
                   QueueFull, find_chart, library, parse_options, queued_uploads, stop_orphan)

APP = "songcharter"
PORTS = range(8765, 8785)          # 8765-8784
CSP = ("default-src 'self'; img-src 'self' data:; connect-src 'self'; script-src 'self'; style-src 'self'; "
       "base-uri 'none'; form-action 'none'; frame-ancestors 'none'")
SECURITY_HEADERS = {"Content-Security-Policy": CSP, "X-Content-Type-Options": "nosniff",
                    "Referrer-Policy": "no-referrer"}
AUDIO = (".mp3", ".wav", ".flac", ".ogg", ".opus", ".m4a", ".aac", ".wma", ".aiff", ".aif")
STEMS_ZIP = " (stems).zip"   # the stems' zip in exports/ (pipeline.STEMS_SUFFIX and .zip): deleted once sent
MAX_UPLOAD = 10 ** 9               # 1 GB (10^9 bytes, the unit of the project's limits)
MAX_JSON = 1 << 20                 # a JSON request body
DRAIN = 16 << 20                   # a refused body this small is read first, so the client sees the answer
UPLOAD_DAYS = 7                    # uploads older than this go when the server starts
KEEPALIVE_S = 15.0
END_WAIT_S = 10.0                  # after a closing event, the stream waits this long for the job's process to exit
HELLO_TIMEOUT_S = 0.5
CHUNK = 1 << 20
DISK_FULL = "C: (or WSL's disk) is full: free some space on C:, then drop the song again"   # an upload's 507
STATIC_TYPES = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
                ".css": "text/css; charset=utf-8"}
PREVIEW_NAME = re.compile(r"^(?:overview|page_\d{2,3})\.png$")   # preview.py's files: overview.png, page_01.png, ...
PREVIEW_PAGE = re.compile(r"^page_\d{2,3}\.png$")
OPEN = ("song", "exports", "built")
QUEUE_POSTS = ("/api/queue/pause", "/api/queue/carry-on", "/api/queue/clear", "/api/queue/remove")   # POST /api/open's only folders: no path comes from the page
# preview.render_pages' page_s, which pipeline's preview stage leaves at its default: the seconds of song a page shows
PAGE_S = 60.0
# a preview flag's text (preview.Flag's str): "<part>: <kind> <m:ss.s>-<m:ss.s> (<n> measures)"
FLAG_AT = re.compile(r"^(?P<part>[a-z]+): [^0-9]+? (?P<m>\d+):(?P<s>\d{2}(?:\.\d+)?)-\d+:\d{2}")
IMAGE_OPTIONS = {"album_art": "album art", "background": "background image"}   # the options that name an image upload
ART_FILES = (ART.ALBUM,)           # GET /api/jobs/current/art/<name>: only these
RANGE = re.compile(r"^bytes=(\d*)-(\d*)$")   # one byte range (the audio player's); anything else: the whole file
# /api/jobs/<current or a job's id, jobs._log_path's yyyyMMdd-HHmmss[-n], or a library chart's (M8-13: <16 hex>:<name>,
# percent-encoded)>[/<the rest>] (M8-10)
JOB_PATH = re.compile(r"^/api/jobs/(current|\d{8}-\d{6}(?:-\d{1,4})?|[0-9a-f]{16}(?::|%3[Aa])[^/]+)(/.*)?$")
# a job's id as a request's body names it: the current one, a job's, or a library chart's (M8-13)
JOB_REF = re.compile(r"^(?:current|\d{8}-\d{6}(?:-\d{1,4})?)$")


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
    """What every request shares: the home, this instance's token, the allowed hosts, the jobs, the status, and the
    update check (`updates`: called once, with the log, after the first page; None: no check, as in the tests)."""

    def __init__(self, home: Path, jobs: Jobs | None = None, log: Log | None = None,
                 report: Callable[[], dict] = lambda: device.report(full=False),
                 updates: Callable[[Callable[[str], None]], dict | None] | None = None,
                 cache_root: Path | None = None):
        self.home = Path(home)
        self._cache_root = cache_root          # the charts' work folders: cache.cache_root() when None (M8-13)
        self.log = log or Log()
        self.jobs = jobs or Jobs(self.home, log=self.log)
        self.token = secrets.token_hex(8)
        self.url: str | None = None
        self.static = static_files()
        self._hosts: set[str] = set()
        self._lock = threading.Lock()
        self._report = report
        self._quick: dict | None = None
        self._fresh: tuple[tuple[int, int], dict] | None = None   # doctor.json's (mtime, size) and its refresh
        self._quick_lock = threading.Lock()
        self.install_lock = threading.Lock()   # one install (or Songs folder change) at a time
        self.installed: Path | None = None     # the song folder the last install put into Clone Hero's Songs
        self._documents: tuple[Path | None] | None = None
        self._documents_lock = threading.Lock()
        self._updates = updates
        self._update_asked = False
        self.update: dict | None = None        # what the update check found: {"version", "line", "url"}
        self.listen_lock = threading.Lock()    # one render at a time (M6-09)
        self.listened: dict[str, dict[str, Path]] = {}   # job id -> {"<part>-<level>.ogg": its render}
        self.queue = Queue(self.jobs, self.home, prepare=self.prepare, disk_low=self.disk_low, log=self.log)

    # --- the queue (M8-10)
    def prepare(self, entry: dict) -> tuple[dict, ChartOptions, str | None]:
        """A queued song about to start: its upload's record, its options checked again with the pictures' upload ids
        made into their paths (none comes from the page), and the doctor's device; an InputError when its file or a
        picture is gone."""
        name = entry["upload"].get("name") or "the song"
        upload = read_upload(self.home, entry["upload"].get("id"))
        if upload is None:
            raise InputError(f"{name} is not there any more: drop it again")
        options = dict(entry.get("options") or {})
        for key, what in IMAGE_OPTIONS.items():
            if options.get(key) is not None:
                image = read_upload(self.home, options[key], kind="image")
                if image is None:
                    raise InputError(f"the {what} chosen for {name} is not there any more: choose it again")
                options[key] = image["path"]
        return upload, parse_options(options), self.auto_device()

    def disk_low(self) -> str | None:
        """Why the queue pauses before a song, when the free disk (measured again) is under doctor's MIN_FREE, else
        None (DESIGN.md 4.5: an evening's work folders stay in the cache for a day, whatever its budget)."""
        disk = self.doctor().get("disk") or {}
        gb = device.MIN_FREE // device.GB
        for key, where in (("windows_c_free_mb", "C:"), ("home_free_mb", "WSL's disk")):
            free = disk.get(key)
            if isinstance(free, (int, float)) and free * device.MB < device.MIN_FREE:
                return (f"{where} is nearly full (under {gb} GB free), so the queue is paused: free some space, then "
                        "Carry on")
        return None

    # --- the update notice (M5-07)
    def page_served(self) -> None:
        """After a page (index.html) is served: the first one starts the update check, on a daemon thread, once for
        this process."""
        with self._lock:
            if self._updates is None or self._update_asked:
                return
            self._update_asked = True
        threading.Thread(target=self._check_updates, name="songcharter-updates", daemon=True).start()

    def _check_updates(self) -> None:
        try:
            r = self._updates(lambda line: self.log(line, console=False))
        except Exception:  # noqa: BLE001  a bug in the check: logged; the page goes on without a notice
            self.log(f"update check: internal error:\n{traceback.format_exc()}", console=False)
            return
        if isinstance(r, dict) and r.get("latest") and r.get("url"):
            self.update = {"version": r["latest"], "line": r.get("line"), "url": r["url"]}

    # --- Clone Hero
    def documents(self) -> Path | None:
        """<Documents>/Clone Hero/Songs (clonehero.documents_songs), asked of Windows once: Documents does not move
        while the page runs."""
        with self._documents_lock:
            if self._documents is None:
                self._documents = (clonehero.documents_songs(),)
            return self._documents[0]

    def clonehero(self) -> dict:
        """clonehero.describe, with its `guess` (<Documents>\\Clone Hero\\Songs, Windows' form) given always, not only
        when no Songs folder is found: the page's field starts from it whenever it has nothing better (M8-04)."""
        found = clonehero.describe(self.home, self.documents)
        guess = self.documents()
        return {**found, "guess": clonehero.windows_path(guess) if guess is not None else None}

    # --- the options screen's choice (M8-04)
    def choices(self, seconds: Any) -> dict:
        """Best or Quick for a song of `seconds`: {"gpu", "best", "quick"}. `gpu`: the doctor summary charts the guitar
        on the GPU (its device CUDA, the guitar not found on the CPU), where the page offers the two; `best` is
        estimate.for_job's range with every option at its default (4 takes there, 1 on the CPU), `quick` with 1 take
        (None off the GPU). A bug in the estimate is logged, and both are None."""
        doctor = self.doctor()
        auto = (doctor.get("device") or {}).get("chosen")
        guitar = doctor.get("guitar_device")
        gpu = auto == "cuda" and guitar != "cpu"
        try:
            best = estimate.for_job(seconds, ChartOptions(), auto, guitar)
            quick = estimate.for_job(seconds, ChartOptions(takes=1), auto, guitar) if gpu else None
        except Exception:  # noqa: BLE001  the choice is offered without its minutes
            self.log(f"estimate: internal error:\n{traceback.format_exc()}", console=False)
            best = quick = None
        return {"gpu": gpu, "best": best, "quick": quick}

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
        """The report the header shows: doctor.json when it reads, with its memory, disk and .wslconfig measured again
        (device.refresh, once for each version of the file: the install wrote it before WSL restarted with the memory
        it set), else device.report(full=False), made once; either way with the free disk measured again on every
        call (device.refresh_disk: cheap, and a session of charts fills the disk while the server stays up)."""
        r = self._doctor()
        try:
            return device.refresh_disk(r)
        except Exception:  # noqa: BLE001  the header shows the report as it was last measured
            return r

    def _doctor(self) -> dict:
        path = self.home / "doctor.json"
        try:
            st = path.stat()
            r = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            r = None
        if isinstance(r, dict):
            key = (st.st_mtime_ns, st.st_size)
            with self._quick_lock:
                if self._fresh is None or self._fresh[0] != key:
                    try:
                        fresh = device.refresh(r)
                    except Exception:  # noqa: BLE001  the header shows the file as it is then
                        fresh = r
                    self._fresh = (key, {**fresh, "source": "doctor.json"})
                return self._fresh[1]
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
        return {**{k: r.get(k) for k in ("device", "gpu", "guitar_device", "guitar_reason", "problems", "notes", "ok",
                                          "source", "error")},
                "job": job.snapshot(events=False) if job is not None else None,
                "queue": self.queue.snapshot(),
                "update": dict(self.update) if self.update else None,
                "defaults": {"instruments": list(INSTRUMENTS), "levels": ["expert"], "solos": "labels", "takes": None,
                             "device": "auto", "preview": True, "threads": None, "threads_default": threads,
                             "all_levels": list(DIFFICULTIES)}}

    def auto_device(self) -> str | None:
        return (self.doctor().get("device") or {}).get("chosen")

    # --- your charts (M8-13)
    def work_root(self) -> Path:
        """Where the charts' work folders are: the charts this server starts use cache.cache_root() too (its
        environment is theirs)."""
        return Path(self._cache_root if self._cache_root is not None else cache.cache_root()).expanduser()

    def library(self) -> dict:
        """GET /api/library (the module docstring)."""
        return {"charts": library(self.home, self.work_root())}

    def chart(self, chart_id: str, job_id: str | None = None) -> Charted | None:
        """The library's chart of that id, or None; named by `job_id` when it was found through that job (a finished
        song the queue's list has dropped)."""
        folder = find_chart(self.home, chart_id)
        return None if folder is None else Charted(folder, self.work_root(), job_id)


# ------------------------------------------------------------------------------------------------ uploads

def uploads_folder(home: Path) -> Path:
    return Path(home) / "uploads"


def read_upload(home: Path, upload_id: Any, kind: str = "song") -> dict | None:
    """An upload's record ({"id", "name", "file", "path", "bytes", "metadata", "origin"} for a song; "format",
    "width", "height" for an image), or None when there is no such upload of that kind ("song" or "image"; a record
    without one is a song's), as an id is 16 hex characters, nothing else."""
    if not isinstance(upload_id, str) or len(upload_id) != cache.KEY_HEX or \
            any(c not in "0123456789abcdef" for c in upload_id):
        return None
    folder = uploads_folder(home) / upload_id
    try:
        record = json.loads((folder / "upload.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    path = folder / str(record.get("file"))
    if not path.is_file() or path.parent != folder or record.get("kind", "song") != kind:
        return None
    return {**record, "path": str(path)}


def prune_uploads(home: Path, days: float = UPLOAD_DAYS, now: float | None = None,
                  keep: Iterable[str] = ()) -> list[str]:
    """Delete the uploads (and stray partial uploads) last touched more than `days` ago, but those in `keep` (the
    queue's waiting songs and their pictures, jobs.queued_uploads); their names."""
    now = time.time() if now is None else now
    keep = set(keep)
    gone = []
    folder = uploads_folder(home)
    try:
        entries = list(folder.iterdir())
    except OSError:
        return gone
    for p in entries:
        if p.name in keep:
            continue
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

    def _skip(self, n: int) -> None:
        """Read and drop the `n` bytes left of a body this server stopped keeping (at most MAX_UPLOAD), so the browser
        sees the answer and not a reset."""
        try:
            while n > 0:
                got = self.rfile.read(min(n, CHUNK))
                if not got:
                    return
                n -= len(got)
        except OSError:
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
        if path == "/api/queue":
            return self._json(200, app.queue.snapshot())
        if path == "/api/library":
            return self._json(200, app.library())
        m = JOB_PATH.match(path)
        if m:
            ref, rest = unquote(m[1]), m[2] or ""
            if rest == "/events":
                return self._events(ref)
            job = self._job(ref)
            if job is None:
                return self._refuse(404, "no job yet" if ref == "current" else "no such job")
            if rest == "":
                return self._json(200, job.snapshot())
            if rest == "/results":
                return self._json(200, results(job, quote(ref, safe="")))
            if rest.startswith("/preview/"):
                return self._preview(job, unquote(rest[len("/preview/"):]))
            if rest.startswith("/art/"):
                return self._art(job, unquote(rest[len("/art/"):]))
            if rest.startswith("/listen/"):
                return self._listened(job, unquote(rest[len("/listen/"):]))
            return self._refuse(404, "not found")
        if path.startswith("/api/exports/"):
            return self._export(unquote(path[len("/api/exports/"):]))
        if path == "/api/clonehero":
            return self._json(200, app.clonehero())
        if path == "/api/diagnostics":
            return self._diagnostics()
        name = "index.html" if path == "/" else path[1:]
        if name in app.static:   # an exact name: no path is joined from the request
            self._send(200, app.static[name], STATIC_TYPES.get(Path(name).suffix, "application/octet-stream"))
            if name == "index.html":
                app.page_served()   # the update check, after the first page: never on the startup path
            return None
        return self._refuse(404, "not found")

    def _post(self, path: str) -> None:
        app = self.app
        if path == "/api/upload":
            answer = self._upload()
            return self._json(200, {**answer, "choices": app.choices(answer.get("seconds"))})
        if path == "/api/upload/image":
            return self._json(200, self._upload_image())
        if path == "/api/jobs":
            body = self._read_json()
            upload = read_upload(app.home, body.get("upload"))
            if upload is None:
                raise Refused(400, f"no such upload: {body.get('upload')!r} (upload the song file again)")
            options = body.get("options")
            given = dict(options) if isinstance(options, dict) else options   # the queue keeps the pictures' ids
            if isinstance(options, dict):   # the images' upload ids become their paths: none comes from the page
                options = dict(options)
                for key, what in IMAGE_OPTIONS.items():
                    if options.get(key) is not None:
                        image = read_upload(app.home, options[key], kind="image")
                        if image is None:
                            raise Refused(400, f"no such {what}: {options[key]!r} (choose the picture again)")
                        options[key] = image["path"]
            try:
                opts = parse_options(options)
            except InputError as e:
                raise Refused(400, str(e)) from None
            doctor = app.doctor()
            auto = (doctor.get("device") or {}).get("chosen")
            try:
                est = estimate.for_job(upload.get("seconds"), opts, auto, doctor.get("guitar_device"))
            except Exception:  # noqa: BLE001  a bug in the estimate: logged, and the chart starts without one
                app.log(f"estimate: internal error:\n{traceback.format_exc()}", console=False)
                est = None
            try:
                entry, job = app.queue.add(upload, given or {}, estimate=est, lyrics=opts.lyrics)
            except (JobRunning, QueueFull) as e:
                raise Refused(409, str(e) if isinstance(e, QueueFull) else f"a chart is running already (job {e})"
                              ) from None
            except InputError as e:
                raise Refused(400, str(e)) from None
            return self._json(202, {"job": job.id if job is not None else None, "entry": entry["id"],
                                    "state": "charting" if job is not None else "waiting"})
        if path in QUEUE_POSTS:
            return self._queue(path)
        m = JOB_PATH.match(path)
        if m and m[2] == "/cancel":   # by id (M8-10's review S-S1): only while that job is the running one
            self._drain()
            try:
                job = app.jobs.cancel(None if m[1] == "current" else m[1])
            except NotRunning:
                raise Refused(409, "no chart is running" if m[1] == "current" else "that chart has ended") from None
            return self._json(200, {"job": job.id, "state": job.state})
        if m and m[2] in ("/export/zip", "/export/stems", "/install", "/listen"):
            ref, rest = unquote(m[1]), m[2]
            job = self._job(ref, gone=True)
            if rest.startswith("/export/"):
                self._drain()
                if rest == "/export/stems":   # one stems zip at a time: an earlier one never fetched goes
                    stems = self._stems(job)
                    for old in (app.home / clonehero.EXPORTS).glob("*" + STEMS_ZIP):
                        old.unlink(missing_ok=True)
                out = clonehero.export_zip(self._built(job) if rest == "/export/zip" else stems, app.home)
                app.log(f"exported {out}")
                return self._json(200, {"url": export_url(out.name), "name": out.name,
                                        "windows_path": clonehero.windows_path(out)})
            body = self._read_json()
            if rest == "/install":
                return self._install(job, body.get("replace") is True)
            return self._listen(job, quote(ref, safe=""), body.get("part"), body.get("level"))
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
        if path == "/api/open":
            body = self._read_json()
            return self._open(body.get("what"), body.get("job"))
        raise Refused(404, "not found")

    # --- the queue (M8-10)
    def _job(self, ref: str, gone: bool = False):
        """The job a route names: the current one, a finished song's by its id (Queue.job), or a library chart's
        (M8-13: App.chart); None for none. A finished song the list has dropped (Clear the list, the trim) is found
        by its job id through its chart in the library (Queue.dropped_chart: the server's own record of its result's
        folder, never a path from the page), as that job id, so a Look still open on it keeps working (the v0.5.0
        review's correct-1). `gone`: a library id whose folder is not among the library's any more (the list read
        before it was deleted in Windows) is Refused(400) in M8-04's words, by its folder's name."""
        if ref == "current":
            return self.app.jobs.current
        m, as_job = LIBRARY_ID.match(ref), None
        if m is None:
            job = self.app.queue.job(ref)
            dropped = self.app.queue.dropped_chart(ref) if job is None else None
            if dropped is None:
                return job
            ref, m, as_job = dropped, LIBRARY_ID.match(dropped), ref
            if m is None:
                return None
        chart = self.app.chart(ref, as_job)
        if chart is None and gone:
            name = m[2][:-len(".failed")] if m[2].endswith(".failed") else m[2]
            raise Refused(400, f"{name}'s folder is not there any more: it was moved or deleted")
        return chart

    def _queue(self, path: str) -> None:
        queue = self.app.queue
        try:
            if path == "/api/queue/remove":
                queue.remove(self._read_json().get("entry"))
            else:
                self._drain()
                {"/api/queue/pause": queue.pause, "/api/queue/carry-on": queue.carry_on,
                 "/api/queue/clear": queue.clear}[path]()
        except NotInQueue as e:
            raise Refused(409, str(e)) from None
        return self._json(200, queue.snapshot())

    # --- after the build
    def _stems(self, job) -> Path:
        """The stems folder the job's run saved (its result's `stems`), when it is there; else Refused(400)."""
        result = job.result() if job is not None else None
        if result is None:
            raise Refused(400, "no finished chart yet")
        folder = stems_of(result)
        if folder is None:
            raise Refused(400, "this chart was made without the stems" if not result.get("stems") else
                          f"the stems are not in {result['stems']} any more")
        return folder

    def _built(self, job) -> Path:
        """The job's song folder, when its chart passed the gate and is in place (its `result` is out, whatever its
        process is still doing: the module docstring); else Refused(400)."""
        result = job.result() if job is not None else None
        if result is None:
            raise Refused(400, "no finished chart yet")
        folder = Path(str(result.get("folder")))
        if not result.get("ok"):
            raise Refused(400, f"the chart did not pass its check: it is in {folder} for a look, not for Clone Hero")
        if not folder.is_dir():
            raise Refused(400, f"the chart's folder {folder} is not there any more")
        return folder

    def _preview(self, job, name: str) -> None:
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

    def _art(self, job, name: str) -> None:
        """The result's album art, by its exact name only."""
        result = job.result() if job is not None else None
        if result is None or name not in ART_FILES:
            return self._refuse(404, "not found")
        try:
            data = (Path(str(result.get("folder"))) / name).read_bytes()
        except OSError:
            return self._refuse(404, "not found")
        return self._send(200, data, "image/jpeg")

    def _listen(self, job, ref: str, part: Any, level: Any) -> None:
        """Render (or find) one part and level of the job's chart and record it as this job's (the module
        docstring)."""
        app = self.app
        if part not in INSTRUMENTS or level not in DIFFICULTIES:
            raise Refused(400, f"part is one of {', '.join(INSTRUMENTS)} and level one of {', '.join(DIFFICULTIES)}")
        result = job.result() if job is not None else None
        if result is None or not result.get("work"):
            raise Refused(400, "no finished chart yet")
        folder = Path(str(result.get("folder")))
        if not folder.is_dir():
            raise Refused(400, f"the chart's folder {folder} is not there any more")
        name = f"{part}-{level}.ogg"
        began = time.monotonic()
        with app.listen_lock:
            try:
                path, was = listen.cached(folder, Path(str(result["work"])) / "listen", part, level)
            except InputError as e:
                raise Refused(400, str(e)) from None
            except (ToolError, OSError) as e:   # ffmpeg failing, a full disk: no bug, said as it is
                raise Refused(500, f"the {part} on {level.capitalize()} could not be made into sound: {e}") from None
            app.listened.setdefault(job.id, {})[name] = path
        took = round(time.monotonic() - began, 1)
        app.log(f"listen: {part} on {level}" + (" (rendered before)" if was else f" rendered in {took} s"))
        return self._json(200, {"url": f"/api/jobs/{ref}/listen/" + name, "part": part, "level": level,
                                "cached": was, "seconds": took})

    def _listened(self, job, name: str) -> None:
        """A render of the job's, by the name the POST recorded it under; anything else 404."""
        path = self.app.listened.get(job.id, {}).get(name)
        if path is None:
            return self._refuse(404, "not found")
        try:
            data = path.read_bytes()
        except OSError:
            return self._refuse(404, "not found")
        return self._ranged(data, "audio/ogg")

    def _ranged(self, data: bytes, ctype: str) -> None:
        """The whole file, or the one byte range a Range header asks for (206; 416 when it lies past the end)."""
        size = len(data)
        m = RANGE.match((self.headers.get("Range") or "").strip())
        if m is None or not (m[1] or m[2]):
            return self._send(200, data, ctype, {"Accept-Ranges": "bytes"})
        if m[1]:
            start, end = int(m[1]), min(int(m[2]) if m[2] else size - 1, size - 1)
        else:
            start, end = max(0, size - int(m[2])), size - 1 if int(m[2]) else -1
        if start >= size or start > end:
            return self._send(416, b"", ctype, {"Accept-Ranges": "bytes", "Content-Range": f"bytes */{size}"})
        return self._send(206, data[start:end + 1], ctype,
                          {"Accept-Ranges": "bytes", "Content-Range": f"bytes {start}-{end}/{size}"})

    def _export(self, name: str) -> None:
        folder = self.app.home / clonehero.EXPORTS
        # one name, no folder: no separator of either kind, so ".." cannot climb (a name may hold "...", as a song's
        # does), nor a leading dot (the .part files)
        if not name.endswith(".zip") or name.startswith(".") or "/" in name or "\\" in name or "\0" in name:
            return self._refuse(404, "not found")
        path = folder / name
        if path.parent != folder or not path.is_file():
            return self._refuse(404, "not found")
        try:
            return self._download(path, name)
        finally:   # a stems zip is as big as the stems: kept only until it is sent (the module docstring)
            if name.endswith(STEMS_ZIP) and self.command == "GET":
                path.unlink(missing_ok=True)

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

    def _install(self, job, replace: bool) -> None:
        app = self.app
        song = self._built(job)
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
                older = None if e.old is None else clonehero.windows_path(e.old) or str(e.old)
                return self._json(403, {"error": e.why, "blocked": True, "why": e.why, "zip_url": export_url(out.name),
                                        "under_onedrive": clonehero.under_onedrive(songs), "older": older})
            except InputError as e:
                raise Refused(400, str(e)) from None
            app.installed = done.target
        app.log(f"installed {done.target}" + (f"; the older chart went to {done.replaced}" if done.replaced else "")
                + (f"; {done.note}" if done.note else ""))
        return self._json(200, {"installed": str(done.target), "windows_path": clonehero.windows_path(done.target),
                                "replaced": None if done.replaced is None else str(done.replaced),
                                "note": done.note})

    def _open(self, what: Any, ref: Any = None) -> None:
        app = self.app
        if what not in OPEN:
            raise Refused(400, f"what is one of {', '.join(OPEN)}")
        if what == "built":   # the job's result folder, a .failed one too (it is for a look): no path from the page
            if ref is None:
                ref = "current"
            elif not isinstance(ref, str) or not (JOB_REF.match(ref) or LIBRARY_ID.match(ref)):
                raise Refused(400, "job is a chart's id: no such chart")   # never a path (M8-13)
            job = self._job(ref, gone=True)
            result = job.result() if job is not None else None
            if result is None:
                raise Refused(400, "no finished chart yet")
            folder = Path(str(result.get("folder")))
            if not folder.is_dir():   # the song by its folder's name: the page shows no Linux path (M8-04)
                name = folder.name[:-len(".failed")] if folder.name.endswith(".failed") else folder.name
                raise Refused(400, f"{name}'s folder is not there any more: it was moved or deleted")
        elif what == "song":
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

    def _receive(self, kinds: Iterable[str], limit: int, refused: str) -> tuple[str, Path, Path, int, str]:
        """The request's body streamed to uploads/<16 hex of its SHA-256>/<cache.safe_name(stem)><ext>: the name as
        sent (its last part), the folder, the file, its bytes and its SHA-256. An extension not in `kinds`: 415
        (`refused` + the extensions); over `limit`: 413; no length: 411; a full disk: 507."""
        try:
            name = unquote(self.headers.get("X-Filename") or "", errors="strict")
        except UnicodeDecodeError:
            raise Refused(400, "X-Filename is not percent-encoded UTF-8") from None
        name = PureWindowsPath(name.replace("\0", "")).name   # no folder, whichever separator it uses
        stem, ext = os.path.splitext(name)
        if ext.lower() not in kinds:
            raise Refused(415, f"{name or 'that file'} is not {refused} ({', '.join(kinds)})")
        n = self._length(limit)
        folder = uploads_folder(self.app.home)
        folder.mkdir(parents=True, exist_ok=True)
        part = folder / f".incoming-{secrets.token_hex(8)}.part"
        sha = hashlib.sha256()
        self.body_read = True
        left = n
        try:
            with open(part, "wb") as f:
                while left > 0:
                    got = self.rfile.read(min(left, CHUNK))
                    if not got:
                        raise Refused(400, f"the upload stopped after {n - left} of {n} bytes")
                    sha.update(got)
                    left -= len(got)
                    f.write(got)
            key = sha.hexdigest()
            target = folder / key[:cache.KEY_HEX]
            target.mkdir(exist_ok=True)
            dest = target / (cache.safe_name(stem) + ext.lower())
            os.replace(part, dest)
        except OSError as e:   # a full disk is the person's to fix (507), not a bug (500)
            if e.errno != errno.ENOSPC:
                raise
            self._skip(left)
            raise Refused(507, DISK_FULL) from None
        finally:
            part.unlink(missing_ok=True)
        return name, target, dest, n, key

    def _keep(self, target: Path, dest: Path, record: dict) -> None:
        """upload.json beside the upload; a full disk is a 507, and an upload with no record goes."""
        tmp, had = target / "upload.json.part", (target / "upload.json").is_file()
        try:
            tmp.write_text(json.dumps(record, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
            os.replace(tmp, target / "upload.json")
        except OSError as e:
            tmp.unlink(missing_ok=True)
            if e.errno != errno.ENOSPC:
                raise
            if not had:   # a file with no record is of no use, and holds the space until the 7-day prune
                dest.unlink(missing_ok=True)
            raise Refused(507, DISK_FULL) from None
        os.utime(target)

    def _upload(self) -> dict:
        name, target, dest, n, key = self._receive(AUDIO, MAX_UPLOAD, "a song file songcharter takes")
        from .. import pipeline   # numpy loads with it
        tags = pipeline.read_tags(dest)
        meta, origin = pipeline.song_metadata(Path(name), tags, {})   # the name as dropped, not its safe form
        seconds = estimate.duration(dest)   # the progress screen's estimate (M7-10)
        self._keep(target, dest, {"id": target.name, "name": name, "file": dest.name, "bytes": n, "sha256": key,
                                  "metadata": meta, "origin": origin, "seconds": seconds, "uploaded": time.time()})
        self.app.log(f"upload {target.name}: {name} ({n} bytes" + (f", {seconds} s)" if seconds else ")"))
        return {"id": target.name, "name": name, "bytes": n, "tags": meta, "origin": origin, "seconds": seconds}

    def _upload_image(self) -> dict:
        name, target, dest, n, key = self._receive(ART.EXTENSIONS, ART.MAX_BYTES, "a picture songcharter takes")
        try:
            _, source = ART.decode(dest.read_bytes(), f"picture {name}")   # the chart checks it again
        except (InputError, ToolError) as e:
            dest.unlink(missing_ok=True)
            if not (target / "upload.json").is_file():
                shutil.rmtree(target, ignore_errors=True)
            raise Refused(415, str(e)) from None
        self._keep(target, dest, {"id": target.name, "kind": "image", "name": name, "file": dest.name, "bytes": n,
                                  "sha256": key, **{k: source[k] for k in ("format", "width", "height")},
                                  "uploaded": time.time()})
        self.app.log(f"upload {target.name}: picture {name} ({n} bytes, {source['width']}x{source['height']})")
        return {"id": target.name, "name": name, "bytes": n, "format": source["format"], "width": source["width"],
                "height": source["height"]}

    def _events(self, ref: str = "current") -> None:
        """GET /api/jobs/<ref>/events (the module docstring): the job's events from Last-Event-ID on; a finished
        song's record (once the next has started) sends its closing event alone, as the end its page missed."""
        job = self._job(ref)
        if job is None:
            return self._refuse(404, "no job yet" if ref == "current" else "no such job")
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
        if not isinstance(job, Job):   # jobs.Kept or jobs.Charted: it has ended, and its closing event is the last
            for event in [e for e in job.snapshot()["events"] if e.get("event") in CLOSING][-1:]:
                self.wfile.write(f"id: {n}\ndata: {json.dumps(event, ensure_ascii=False)}\n\n".encode("utf-8"))
            self.wfile.flush()
            return None
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


def flag_page(start: float, pages: int, page_s: float = PAGE_S) -> int | None:
    """The preview page (from 1) that shows the song's second `start`: floor(start / page_s) + 1, kept among the
    `pages` there are (a flag past the last page, such as notes after the audio's end, links to the last); None
    without pages. A page shows [(n - 1) * page_s, n * page_s): a flag starting on a page's edge is on the next."""
    if pages < 1:
        return None
    return max(1, min(pages, math.floor(max(0.0, start) / page_s) + 1))


def flag_at(text: str, pages: int, page_s: float = PAGE_S) -> dict | None:
    """A flag's part, its start in seconds (as its text has it, to a tenth) and its page: {"part", "start", "page"},
    or None for a text that is not a flag's (FLAG_AT)."""
    m = FLAG_AT.match(text)
    if m is None or m["part"] not in INSTRUMENTS:
        return None
    start = int(m["m"]) * 60 + float(m["s"])
    return {"part": m["part"], "start": start, "page": flag_page(start, pages, page_s)}


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


def stems_of(result: dict) -> Path | None:
    """The stems folder a result event names (`stems`), when it is a folder holding .flac files; else None."""
    if not result.get("stems"):
        return None
    folder = Path(str(result["stems"]))
    try:
        return folder if folder.is_dir() and any(folder.glob("*.flac")) else None
    except OSError:
        return None


def results(job, ref: str = "current") -> dict:
    """GET /api/jobs/<ref>/results (the module docstring), from the job's result event and its pipeline.json; its
    URLs name the job as the request did (`current`, or its id)."""
    result = job.result()
    out: dict[str, Any] = {"job": job.id, "state": job.state, "ok": None, "folder": None, "name": None,
                           "windows_path": None, "installable": False, "preview": None, "lyrics": None, "art": None,
                           "listen": None, "stems": None}
    if result is None:
        return out
    folder = Path(str(result.get("folder")))
    out.update(ok=bool(result.get("ok")), folder=str(folder), name=folder.name,
               windows_path=clonehero.windows_path(folder),   # Open folder's hover text
               installable=bool(result.get("ok")) and folder.is_dir())   # its state may still be running: exiting
    try:   # a library chart whose work folder has left the cache has none (M8-13)
        pipeline = (json.loads((Path(str(result["work"])) / "pipeline.json").read_text(encoding="utf-8"))
                    if result.get("work") else {})
    except (OSError, ValueError):
        pipeline = {}
    pipeline = pipeline if isinstance(pipeline, dict) else {}
    pv = pipeline.get("preview")
    where = Path(result["preview"]) if result.get("preview") else None
    if where is not None and (where / "overview.png").is_file():
        try:
            pages = sorted((p.name for p in where.iterdir() if PREVIEW_PAGE.match(p.name)),
                           key=lambda name: int(name[5:-4]))   # page_100 after page_99
        except OSError:
            pages = []
        base = f"/api/jobs/{ref}/preview/"
        pv = pv if isinstance(pv, dict) else {}
        flags = [str(f) for f in pv.get("flags") or []]
        out["preview"] = {"overview": base + "overview.png", "pages": [base + p for p in pages],
                          "flags": flags, "remarks": list(pv.get("remarks") or []), "page_s": PAGE_S,
                          "at": [flag_at(f, len(pages)) for f in flags]}
    else:
        out["preview"] = {"why": _preview_why(pv)}
    pictures = pipeline.get("art") if isinstance(pipeline.get("art"), dict) else {}
    album = pictures.get("album_art") if isinstance(pictures.get("album_art"), dict) else {}
    out["art"] = {"album_art": f"/api/jobs/{ref}/art/" + ART.ALBUM if (folder / ART.ALBUM).is_file() else None,
                  "album_from": album.get("from"), "background": (folder / ART.BACKGROUND).is_file()}
    try:
        out["listen"] = {"parts": listen.available(folder)}
    except InputError as e:
        out["listen"] = {"parts": {}, "why": str(e)}
    saved = stems_of(result)
    if saved is not None:
        files = sorted(saved.glob("*.flac"))
        out["stems"] = {"name": saved.name, "files": [f.name for f in files],
                        "bytes": sum(f.stat().st_size for f in files)}
    elif isinstance(pipeline.get("stems"), dict) and pipeline["stems"].get("saved") is False:
        out["stems"] = {"why": str(pipeline["stems"].get("why") or "They were not saved.")}
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


def other_version(theirs: Any, url: str) -> str | None:
    """Why a running server whose hello says the version `theirs` is not this one's to reuse, or None when it is
    this version (the module docstring, Startup 1)."""
    if theirs == __version__:
        return None
    who = (f"songcharter {theirs}" if isinstance(theirs, str) and re.fullmatch(r"[0-9A-Za-z.+-]{1,40}", theirs)
           else "another version of songcharter")
    return (f"{who} is still running ({url}), and this is songcharter {__version__}: close the songcharter window "
            f"(closing it stops {who}), then start songcharter again")


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
            "Windows, or start songcharter with another port (songcharter ui --port 8800); or restart WSL: in "
            "Terminal (right-click Start), type wsl --shutdown, then open Ubuntu again."
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
    """`songcharter ui` (the module docstring). Exit 0 when it stopped (or one of this version is running), 2 when it
    cannot start (no free port, a home it cannot write, another version running), 3 for a bug."""
    try:
        return _main(port, browser, from_shortcut, home)
    except KeyboardInterrupt:
        return 0
    except InputError as e:
        print(f"songcharter: error: {e}", file=sys.stderr)
        return 2
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
        why = other_version(running[1].get("version"), url)
        if why is not None:   # its page is not this version's: never opened (M5-12)
            raise InputError(why)
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
    gone = prune_uploads(root, keep=queued_uploads(root))
    if gone:
        log(f"uploads older than {UPLOAD_DAYS} days deleted: {len(gone)}")
    stop_orphan(root, log)   # a chart a songcharter killed outright left running, before the queue is read (jobs.py)
    app = App(root, log=log, updates=lambda say: updates.check(root, __version__, say=say))
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
            app.queue.shutdown()   # the charting song goes back to waiting at the top of queue.json
        finally:
            for server in servers:
                server.shutdown()
                server.server_close()
            log("stopped")
    return 0
