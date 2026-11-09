"""The UI's chart job: one at a time, as a child process group (proc.py), its events and log, its end state (M4-04).

    jobs = Jobs(home)
    job = jobs.start(upload, options, auto_device="cpu")   # JobRunning while one runs; InputError for bad options
    events, ended = job.wait_events(after=0, timeout=15)   # what the SSE stream sends
    jobs.cancel()                                          # the whole tree killed, assemble's staging deleted

  * **The command:** [sys.executable, "-m", "songcharter.cli", "chart", <upload>, "--out", <out>, "--events", ...]:
    every option one for one with the command line's (values as --flag=VALUE, so one that starts with "-" stays a
    value), with the server's environment (the launcher's) and PYTHONUTF8=1, in the server's working folder (so the
    child runs the server's own code). --threads is device.default_threads() when the options leave it empty and the
    device is the CPU (asked for, or "auto" where doctor found no CUDA).
  * **The output folder:** <home>/library/<the upload's 16 hex>/<cache.safe_name(f"{artist} - {title}")>, the artist
    and title as the chart will have them (the options', else the upload's tags or file name). The name is safe for
    Windows, as M4-06 copies the folder to /mnt/c, and at most LIBRARY_NAME_MAX (80) characters, cut at a word: it
    is the name the friend sees in Clone Hero's Songs folder and on the Done screen, so it is not held to the work
    folder's 40 (cache.NAME_MAX, for autochart's deep cache paths). Installed, its deepest path on the Windows side
    is clonehero.py's copy, C:\\Users\\<profile>\\Documents\\Clone Hero\\Songs\\.<name>.songcharter-<8 hex>.tmp\\
    background.jpg: 178 characters with a 20-character profile, 187 with OneDrive's Documents, under Windows' 259.
  * **Reading the child:** its stderr, with its stdout merged in (one ordered stream, and no pipe left unread), line
    by line (UTF-8, errors="replace"). Every line goes to <home>/logs/job-<yyyyMMdd-HHmmss>.log; each
    `@@songcharter <json>` line is an event, kept with "at" (the server's clock when it was read: the page's ticking
    times).
  * **The end state:** exit 0 or 1 gives `done` (the verdict is in the `result` event), 2 or 3 `failed` (its `error`
    event says why), a cancel `cancelled`. The events always end with one of `result`, `error` or `cancelled`, so the
    SSE stream always closes: when the child sent none (exit 2 or 3 without its error, a signal from elsewhere such as
    the kernel's out-of-memory killer, which is `failed`, not `cancelled`), the job adds an `error` with the log's
    last lines.
  * **Cancel:** proc.Tree.kill() (SIGTERM to the group, SIGKILL after 5 s), then the state `cancelled`, then the
    `.<name>.*.partial` folders beside the output (assemble's staging) are deleted. The work folder's caches stay, so
    the same song charts faster next time.
  * **An orphan** (a second advisor's finding 7): the chart runs in a session of its own, so a server killed outright
    (SIGKILL, a crash: no SIGTERM, SIGHUP or Ctrl+C to clean up) leaves it running under init, and Carry on after the
    restart would start a second chart on the same work folder. <home>/state/chart.pid names the running chart (its
    pid, which is its process group's, and its start time from /proc) and its server (pid and start time), written
    when it starts and removed when it ends; `stop_orphan`, at the server's start once its port is bound, kills that
    group while its leader is still the process it names (a pid used again since is never touched) and its server
    is gone (one this start did not find keeps its chart: the v0.5.0 re-review's R1). Chosen over a parent-death signal (prctl PR_SET_PDEATHSIG): that signal
    follows the thread that started the child, and the server starts charts from request and queue threads that end
    at once, so it would kill every chart within moments.
  * **Lyrics** (M4-06, from M4-10): the page's pasted text (`lyrics`, None when the box is empty or blank) goes only
    into the chart. The job writes it into a memory file (memfd, Linux), which the child gets as an open file and
    reads as `--lyrics=/dev/fd/<n>`: nothing on disk, and the command line, the log, the job's options (`lyrics`:
    whether given) and every event name the file, never a word of it.
  * **Pictures** (M4-11): `album_art` and `background` are the paths of images uploaded through the page; the server
    puts them in for the page's upload ids (server.py: a path never comes from the page) and they become
    --album-art and --background. The job's options say whether each was given.
  * **Stems and the audio** (M8-12): `stems` (off by default) becomes --stems, the six stems as FLAC in
    "<the song folder> (stems)" beside it, whose staging folder a cancel deletes too; `one_audio` (off: Clone Hero's
    multitrack audio, the default) becomes --one-audio. Both are per song: the queue keeps them for a waiting song.
  * **The estimate** (M7-10): how long the chart usually takes (estimate.for_job, which the server works out from
    the upload's length, the options and the doctor summary), given to `start` and kept as it is in the job's
    snapshot (`estimate`, None without one) for the progress screen; and with it, the time left once the guitar's
    first take is timed (`remaining`: estimate.remaining from the estimate and the events' `at`, M8-04; None before,
    without an estimate, or when a bug in it is caught: the snapshot never fails for it).
  * **The queue** (M8-10, `Queue`, DESIGN.md 4.5): the server's waiting list over these jobs, still one child
    process group at a time. `Jobs.on_end` (on a thread of its own) tells it a job has ended, and it starts the next
    waiting song; <home>/state/queue.json keeps the list (no lyrics), and after a restart the queue waits for Carry
    on. A finished song that leaves the list (Clear the list, Remove, the trim) stays known by its job id through its
    chart in the library (`Queue.dropped_chart`, for the server's life), so a Look still open on it keeps working.
  * **The library** (M8-13, "Your charts", DESIGN.md 4.5): every chart the page has made stays in
    <home>/library/<16 hex>/<name>/ with its report.json, and `library` reads them all, newest first (report.json's
    time), for the page's list: the song.ini's name and artist, the gate's verdict, the audio (one file or split,
    M8-12), whether the stems were saved beside it, and whether Look can show it (`look`: the song's work folder is
    still in the cache, cache.by_key by the upload's 16 hex, the song file's key, and its pipeline.json says its last
    chart is this folder). A folder whose report.json cannot be read is listed by its name (`readable` false), never
    hidden; one without a report.json is not a chart. A chart's id is `<16 hex>:<its folder's name>` (`LIBRARY_ID`),
    looked up among the folders the library holds (`find_chart`), never made into a path; `Charted` is a chart as the
    routes by id take it (a `result` made from its folder), so Install, Open, the stems' zip and Look are the queue's
    own routes. Nothing here deletes a chart.
"""
from __future__ import annotations

import glob
import json
import os
import re
import secrets
import shutil
import signal
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from .. import cache, device, proc
from ..errors import InputError
from . import estimate as estimates
from ..timed import DIFFICULTIES, INSTRUMENTS

EVENT_PREFIX = "@@songcharter "   # cli.EVENT_PREFIX (not imported: the cli module is the child's)
CLOSING = ("result", "error", "cancelled")   # the events after which a job's stream ends
META_FLAGS = {"title": "--title", "artist": "--artist", "album": "--album", "year": "--year", "genre": "--genre"}
IMAGE_FLAGS = {"album_art": "--album-art", "background": "--background"}
LIBRARY_NAME_MAX = 80   # the library folder's name: at most this many UTF-16 code units (the module docstring)
OPTION_KEYS = (*META_FLAGS, "instruments", "levels", "solos", "takes", "device", "threads", "preview", "lyrics",
               *IMAGE_FLAGS, "stems", "one_audio")
TAIL_LINES = 8                     # the log's last lines in an error the job writes itself
END_WAIT_S = 10.0                  # how long a new job waits for one whose closing event is out to exit
# an error the job writes itself (the child sent none) in plain words, for the queue's list (M8-10's review, P-F4;
# the Done screen keeps the whole message, with the log's last lines)
PLAIN_MEMORY = "Stopped: the PC ran short of memory, perhaps (Look shows the details)"
PLAIN_STOPPED = "Stopped by the system (Look shows the details)"
PLAIN_SILENT = "It stopped without saying why (Look shows the details)"


class JobRunning(Exception):
    """A job is running already (the server answers 409)."""


class NotRunning(Exception):
    """No job is running (cancel: 409)."""


def parse_line(line: str) -> dict | None:
    """The event in a `@@songcharter <json>` line (a JSON object with "event"), else None."""
    if not line.startswith(EVENT_PREFIX):
        return None
    try:
        event = json.loads(line[len(EVENT_PREFIX):])
    except ValueError:
        return None
    return event if isinstance(event, dict) and isinstance(event.get("event"), str) else None


@dataclass(frozen=True)
class ChartOptions:
    """The page's options, checked (`parse_options`): what pipeline.Options takes, and the song.ini values."""
    instruments: tuple[str, ...] = INSTRUMENTS
    levels: tuple[str, ...] = ("expert",)
    solos: str | tuple[str, ...] = "labels"
    takes: int | None = None
    device: str = "auto"
    threads: int | None = None
    preview: bool = True
    metadata: Mapping[str, str] = field(default_factory=dict)   # title, artist, album, year, genre: the non-blank
    lyrics: str | None = field(default=None, repr=False)       # the pasted text, None without: never shown, never kept
    album_art: str | None = None   # an uploaded image's path (the server's, for the page's upload id), None without
    background: str | None = None
    stems: bool = False       # also the six stems as FLAC beside the song folder (--stems, M8-12)
    one_audio: bool = False   # one song.ogg, not Clone Hero's multitrack audio (--one-audio, M8-12)

    def as_dict(self) -> dict:
        """The options as the job's records show them: `lyrics` is whether some were given, never the text."""
        return {"instruments": list(self.instruments), "levels": list(self.levels),
                "solos": self.solos if isinstance(self.solos, str) else list(self.solos), "takes": self.takes,
                "device": self.device, "threads": self.threads, "preview": self.preview,
                "lyrics": self.lyrics is not None, "album_art": self.album_art is not None,
                "background": self.background is not None, "stems": self.stems, "one_audio": self.one_audio,
                **self.metadata}


def _words(raw: Any, what: str) -> tuple[str, ...]:
    if not isinstance(raw, list) or not all(isinstance(x, str) for x in raw):
        raise InputError(f"{what} is a list of names, not {raw!r}")
    return tuple(x.strip().lower() for x in raw)


def parse_options(raw: Any) -> ChartOptions:
    """The page's options (a JSON object; a missing key or null is the command line's default) checked as
    pipeline.Options.check() checks them; an InputError with its message otherwise."""
    from ..pipeline import Options   # numpy loads with it
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise InputError(f"options is an object, not {raw!r}")
    unknown = sorted(set(raw) - set(OPTION_KEYS))
    if unknown:
        raise InputError(f"unknown option(s): {', '.join(unknown)} (known: {', '.join(OPTION_KEYS)})")
    meta = {}
    for key in META_FLAGS:
        value = raw.get(key)
        if value is not None and not isinstance(value, str):
            raise InputError(f"{key} is text, not {value!r}")
        if value and value.strip():
            meta[key] = " ".join(value.split())
    get = {k: raw[k] for k in OPTION_KEYS if raw.get(k) is not None}
    instruments = _words(get["instruments"], "instruments") if "instruments" in get else INSTRUMENTS
    levels = _words(get["levels"], "levels") if "levels" in get else ("expert",)
    solos = get.get("solos", "labels")
    if isinstance(solos, str):
        solos = solos.strip().lower()
    elif isinstance(solos, list) and all(isinstance(x, str) for x in solos):
        solos = tuple(" ".join(x.split()) for x in solos)
        if any("," in x for x in solos):
            raise InputError("a solo section's name cannot hold a comma (the command line separates names with them)")
    preview = get.get("preview", True)
    lyrics = get.get("lyrics")
    if lyrics is not None and not isinstance(lyrics, str):
        raise InputError(f"lyrics is text, not a {type(lyrics).__name__}")   # the type alone: never the words
    for key in IMAGE_FLAGS:
        if key in get and not isinstance(get[key], str):
            raise InputError(f"{key} is an uploaded image, not {get[key]!r}")
    options = ChartOptions(instruments=instruments, levels=levels, solos=solos, takes=get.get("takes"),
                           device=get.get("device", "auto"), threads=get.get("threads"), preview=preview,
                           metadata=meta, lyrics=lyrics if lyrics and lyrics.strip() else None,
                           album_art=get.get("album_art"), background=get.get("background"),
                           stems=get.get("stems", False), one_audio=get.get("one_audio", False))
    pipeline_meta = {"name" if k == "title" else k: v for k, v in meta.items()}
    Options(instruments=options.instruments, takes=options.takes, device=options.device, threads=options.threads,
            metadata=pipeline_meta, solos=options.solos, levels=options.levels, preview=options.preview,
            lyrics=options.lyrics, album_art=options.album_art, background=options.background, stems=options.stems,
            one_audio=options.one_audio).check()
    return options


def threads_for(options: ChartOptions, auto_device: str | None) -> int | None:
    """--threads: the options', else device.default_threads() when the run is on the CPU (asked for, or "auto"
    where the doctor summary's device is the CPU), else None (the libraries' own default)."""
    if options.threads is not None:
        return options.threads
    on_cpu = options.device == "cpu" or (options.device == "auto" and auto_device == "cpu")
    return device.default_threads() if on_cpu else None


def chart_command(song: Path, out: Path, options: ChartOptions, threads: int | None) -> list[str]:
    """`songcharter chart` for the job, every option as the command line takes it."""
    solos = options.solos if isinstance(options.solos, str) else ",".join(options.solos)
    levels = [d for d in DIFFICULTIES if d in options.levels]
    cmd = [sys.executable, "-m", "songcharter.cli", "chart", str(song), f"--out={out}", "--events",
           f"--instruments={','.join(options.instruments)}", f"--levels={','.join(levels)}", f"--solos={solos}",
           f"--device={options.device}"]
    if options.takes is not None:
        cmd.append(f"--takes={options.takes}")
    if threads is not None:
        cmd.append(f"--threads={threads}")
    if not options.preview:
        cmd.append("--no-preview")
    if options.stems:
        cmd.append("--stems")
    if options.one_audio:
        cmd.append("--one-audio")
    cmd += [f"{flag}={options.metadata[key]}" for key, flag in META_FLAGS.items() if key in options.metadata]
    cmd += [f"{flag}={getattr(options, key)}" for key, flag in IMAGE_FLAGS.items() if getattr(options, key)]
    return cmd


def lyrics_file(text: str) -> int:
    """A memory file (memfd: in memory, never on disk) holding `text` as UTF-8, at its start: its descriptor, which the
    child reads as /dev/fd/<n>. Close-on-exec, so only a child it is passed to (pass_fds) gets it."""
    fd = os.memfd_create("songcharter-lyrics", os.MFD_CLOEXEC)
    try:
        view = memoryview(text.encode("utf-8"))
        while view:
            view = view[os.write(fd, view):]
        os.lseek(fd, 0, os.SEEK_SET)
    except BaseException:
        os.close(fd)
        raise
    return fd


def output_folder(home: Path, upload: Mapping[str, Any], options: ChartOptions) -> Path:
    """<home>/library/<the upload's id>/<cache.safe_name(f"{artist} - {title}", LIBRARY_NAME_MAX)>."""
    tags = upload.get("metadata") or {}
    artist = options.metadata.get("artist") or tags.get("artist") or "Unknown"
    title = options.metadata.get("title") or tags.get("name") or Path(upload["path"]).stem
    return home / "library" / upload["id"] / cache.safe_name(f"{artist} - {title}", LIBRARY_NAME_MAX)


def partial_folders(out: Path) -> list[Path]:
    """assemble's staging folders for the output `out`, and the stems export's: .<name>.*.partial and
    .<name> (stems).*.partial beside it (the name escaped: a song's name keeps [ and ], which a glob reads as a
    character class)."""
    try:
        return sorted(p for name in (out.name, out.name + " (stems)")
                      for p in out.parent.glob(f".{glob.escape(name)}.*.partial") if p.is_dir())
    except OSError:
        return []


def _stamp() -> str:
    return time.strftime("%Y%m%d-%H%M%S")


def pid_path(home: Path) -> Path:
    return Path(home) / "state" / "chart.pid"


def proc_start(pid: int) -> str | None:
    """The process's start time (/proc/<pid>/stat's 22nd field, clock ticks since boot), which a pid used again
    later does not share; None when there is no such process, or no /proc."""
    try:
        stat = Path(f"/proc/{pid}/stat").read_text(encoding="ascii", errors="replace")
    except OSError:
        return None
    fields = stat.rpartition(")")[2].split()   # from the 3rd field, the state
    return fields[19] if len(fields) > 19 else None


def stop_orphan(home: Path, log: Callable[[str], None] | None = None,
                timeout: float = proc.KILL_TIMEOUT_S) -> int | None:
    """At the server's start (server._main, once its port is bound): a chart that chart.pid names and that still
    runs, its leader the very process that was started (its start time the same), whose server (chart.pid's
    `server`, with its start time) is gone, was left by a server killed outright; its whole process group gets
    SIGTERM, then SIGKILL after `timeout` s (the module docstring: an orphan). A server still running (one this start
    did not find: slow to answer, or on another --port) keeps its chart and chart.pid (the v0.5.0 re-review's R1).
    Otherwise chart.pid goes. Returns the pid stopped, else None."""
    path = pid_path(home)
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, ValueError):
        record = None
    pid = record.get("pid") if isinstance(record, dict) else None
    server = record.get("server") if isinstance(record, dict) else None
    if (isinstance(server, int) and not isinstance(server, bool) and server > 1 and proc.alive(server)
            and proc_start(server) is not None and proc_start(server) == record.get("server_start")):
        return None   # its server is alive: not an orphan
    stopped = None
    if (isinstance(pid, int) and not isinstance(pid, bool) and pid > 1 and isinstance(record.get("start"), str)
            and proc.alive(pid) and proc_start(pid) == record["start"]):
        try:
            os.killpg(pid, signal.SIGTERM)   # its pid is its group's: a session of its own (proc.start)
            deadline = time.monotonic() + timeout
            while proc.group_alive(pid) and time.monotonic() < deadline:
                time.sleep(proc.POLL_S)
            if proc.group_alive(pid):
                os.killpg(pid, signal.SIGKILL)
            stopped = pid
        except ProcessLookupError:
            stopped = pid
        except OSError as e:
            (log or (lambda text: None))(f"a chart left running (pid {pid}) could not be stopped: {e}")
        if stopped is not None:
            (log or (lambda text: None))(f"a chart left running by a songcharter that was stopped outright (job "
                                         f"{record.get('job')}, pid {pid}) was stopped; its song waits for Carry on")
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass
    return stopped


@dataclass
class Job:
    id: str
    upload: dict
    options: ChartOptions
    command: list[str]
    out: Path
    log: Path
    started: float = field(default_factory=time.time)
    state: str = "running"                 # running, done, failed, cancelled
    events: list[dict] = field(default_factory=list)
    returncode: int | None = None
    ended: float | None = None
    tree: proc.Tree | None = None
    cancelling: bool = False
    tail: list[str] = field(default_factory=list)   # the log's last lines, for an error the job writes itself
    estimate: dict | None = None           # how long it usually takes (estimate.for_job), for the progress screen
    cond: threading.Condition = field(default_factory=threading.Condition)
    reader: threading.Thread | None = None

    def add(self, event: dict) -> None:
        with self.cond:
            self.events.append({**event, "at": round(time.time(), 3)})
            self.cond.notify_all()

    def wait_events(self, after: int, timeout: float) -> tuple[list[dict], bool]:
        """The events from index `after` on, waiting up to `timeout` s for one when there is none yet; and whether
        the job has ended (no more will come)."""
        with self.cond:
            if len(self.events) <= after and self.state == "running":
                self.cond.wait(timeout)
            return list(self.events[after:]), self.state != "running"

    def wait_end(self, timeout: float) -> bool:
        """Wait up to `timeout` s for the job to end (its closing event comes just before its process exits);
        whether it has."""
        with self.cond:
            return self.cond.wait_for(lambda: self.state != "running", timeout)

    def snapshot(self, events: bool = True) -> dict:
        with self.cond:
            out = {"job": self.id, "state": self.state, "upload": {"id": self.upload["id"],
                                                                   "name": self.upload.get("name")},
                   "options": self.options.as_dict(), "out": str(self.out), "log": str(self.log),
                   "started": self.started, "ended": self.ended, "exit": self.returncode, "now": time.time(),
                   "estimate": dict(self.estimate) if self.estimate else None, "remaining": self._remaining()}
            if events:
                out["events"] = list(self.events)
            return out

    def _remaining(self) -> dict | None:
        """The time left (estimate.remaining; the module docstring), with the condition held."""
        try:
            return estimates.remaining(self.estimate, self.events)
        except Exception:  # noqa: BLE001  the progress screen keeps the first estimate
            return None

    def result(self) -> dict | None:
        """The `result` event (chart --events: ok, exit, folder, work, preview, summary), None before or without one."""
        with self.cond:
            return next((e for e in reversed(self.events) if e["event"] == "result"), None)

    def _closed(self) -> bool:
        return any(e["event"] in CLOSING for e in self.events)

    def _has(self, kind: str) -> bool:
        return any(e["event"] == kind for e in self.events)


class Jobs:
    """The server's one job at a time. `command` builds the child's command line (chart_command; tests stand in a
    program of their own), `env` is its environment (default: the server's, with PYTHONUTF8=1)."""

    def __init__(self, home: Path, command: Callable[[Path, Path, ChartOptions, int | None], Sequence[str]] =
                 chart_command, env: Mapping[str, str] | None = None, log: Callable[[str], None] | None = None,
                 kill_timeout: float = proc.KILL_TIMEOUT_S):
        self.home = Path(home)
        self.command = command
        self.env = env
        self.log = log or (lambda text: None)
        self.kill_timeout = kill_timeout
        self.current: Job | None = None
        self.on_end: Callable[[Job], None] | None = None   # the queue's (M8-10): called on a thread of its own
        self._lock = threading.Lock()

    def _ended(self, job: Job) -> None:
        """A job's end state is set: `on_end` runs on a thread of its own, so the reader thread and cancel() never
        wait on the queue's lock."""
        if self.on_end is not None:
            threading.Thread(target=self.on_end, args=(job,), name=f"songcharter-ended-{job.id}", daemon=True).start()

    def _log_path(self) -> tuple[str, Path]:
        folder = self.home / "logs"
        folder.mkdir(parents=True, exist_ok=True)
        stamp = _stamp()
        name, n = stamp, 1
        while (folder / f"job-{name}.log").exists():
            n += 1
            name = f"{stamp}-{n}"
        return name, folder / f"job-{name}.log"

    def start(self, upload: Mapping[str, Any], options: Any, auto_device: str | None = None,
              estimate: Mapping[str, Any] | None = None) -> Job:
        """Start the chart of `upload` ({"id", "path", "name", "metadata"}) with the page's `options` (parse_options;
        an InputError for bad ones), with its `estimate` (the module docstring). JobRunning while a job runs; a job
        that has sent its result or error but whose process is still exiting (a second or so) is waited for first, up
        to END_WAIT_S, as the page offers the next song as soon as the result is in."""
        opts = options if isinstance(options, ChartOptions) else parse_options(options)
        with self._lock:
            current = self.current
            if current is not None and current.state == "running":
                with current.cond:
                    closed = current._closed()
                if closed:
                    current.wait_end(END_WAIT_S)
            if current is not None and current.state == "running":
                raise JobRunning(current.id)
            song = Path(upload["path"])
            out = output_folder(self.home, upload, opts)
            cmd = [str(c) for c in self.command(song, out, opts, threads_for(opts, auto_device))]
            fd = lyrics_file(opts.lyrics) if opts.lyrics is not None else None
            try:
                if fd is not None:
                    cmd.append(f"--lyrics=/dev/fd/{fd}")
                job_id, log = self._log_path()
                job = Job(job_id, dict(upload), opts, cmd, out, log, estimate=dict(estimate) if estimate else None)
                env = {**(os.environ if self.env is None else self.env), "PYTHONUTF8": "1"}
                out.parent.mkdir(parents=True, exist_ok=True)
                with open(log, "w", encoding="utf-8") as f:
                    f.write(f"songcharter ui job {job_id}: {' '.join(cmd)}\n")
                if fd is None:
                    job.tree = proc.start(cmd, env, None, subprocess.PIPE, subprocess.STDOUT)
                else:   # proc.start's, with the lyrics' memory file passed on
                    job.tree = proc.Tree(subprocess.Popen(cmd, env=env, stdin=subprocess.DEVNULL,
                                                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                                          start_new_session=True, pass_fds=(fd,)))
            finally:
                if fd is not None:
                    os.close(fd)   # the child holds its own copy
            self._mark(job)
            job.reader = threading.Thread(target=self._read, args=(job,), name=f"songcharter-job-{job_id}",
                                          daemon=True)
            self.current = job
            job.reader.start()
            self.log(f"job {job_id}: started on {upload.get('name') or song.name} (pid {job.tree.pid}), into {out}; "
                     f"log {log}")
            return job

    def _read(self, job: Job) -> None:
        """The child's lines into the log and the events, to its end; the end state always follows, even when the
        log cannot be written (a full disk: the lines are read on, so the child never blocks on a full pipe)."""
        assert job.tree is not None and job.tree.stdout is not None
        try:
            log = open(job.log, "a", encoding="utf-8", errors="replace")
        except OSError:
            log = None
        try:
            for raw in job.tree.stdout:
                line = raw.decode("utf-8", "replace").rstrip("\r\n")
                if log is not None:
                    try:
                        log.write(line + "\n")
                        log.flush()
                    except OSError:
                        log = None
                event = parse_line(line)
                if event is not None:
                    job.add(event)
                elif line.strip():
                    job.tail = (job.tail + [line])[-TAIL_LINES:]
        finally:
            if log is not None:
                try:
                    log.close()
                except OSError:
                    pass
            self._finish(job, job.tree.wait())

    def _mark(self, job: Job) -> None:
        """<home>/state/chart.pid for the chart that has just started (the module docstring: an orphan); a disk that
        cannot take it is logged, and the chart goes on."""
        assert job.tree is not None
        path = pid_path(self.home)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({"pid": job.tree.pid, "start": proc_start(job.tree.pid), "job": job.id,
                                        "server": os.getpid(), "server_start": proc_start(os.getpid())}) + "\n",
                            encoding="utf-8")
        except OSError as e:
            self.log(f"job {job.id}: {path} could not be written ({e})")

    def _unmark(self, job: Job) -> None:
        """chart.pid away once the job's chart has ended, when it names that chart."""
        path = pid_path(self.home)
        try:
            if job.tree is not None and json.loads(path.read_text(encoding="utf-8")).get("pid") == job.tree.pid:
                path.unlink()
        except (OSError, ValueError, AttributeError):
            pass

    def _finish(self, job: Job, code: int) -> None:
        """The end state from the exit code (a cancel's is set by cancel()). A chart that has sent its result is done,
        whatever its exit: the result comes after the build is in place."""
        self._unmark(job)
        with job.cond:
            job.returncode = code
            if job.cancelling or job.state != "running":
                return
            if job._has("result"):
                job.state = "done"
            else:
                job.state = "failed"
                if not job._closed():
                    if code < 0:
                        try:
                            name = signal.Signals(-code).name
                        except ValueError:
                            name = f"signal {-code}"
                        why = f"the chart was stopped by {name}" + (" (by the system: out of memory, perhaps)"
                                                                    if -code == signal.SIGKILL else "")
                        kind = "tool"
                        plain = (PLAIN_MEMORY if -code == signal.SIGKILL else PLAIN_STOPPED)
                    else:
                        why, kind = f"the chart exited {code}", "tool" if code == 2 else "bug"
                        plain = PLAIN_SILENT
                    message = why + (":\n" + "\n".join(job.tail) if job.tail else "")
                    job.events.append({"event": "error", "kind": kind, "message": message, "plain": plain,
                                       "at": round(time.time(), 3)})
            job.ended = time.time()
            job.cond.notify_all()
        self.log(f"job {job.id}: {job.state} (exit {code})")
        self._ended(job)

    def cancel(self, job_id: str | None = None) -> Job:
        """Kill the running job's whole tree (only when it is `job_id`'s, when one is given: a Cancel the page sent
        for a song that has ended since must not reach the next, M8-10's review S-S1), mark it cancelled, delete assemble's staging beside its output. A job
        whose result or error is out keeps that outcome (done, or failed), with no `cancelled`: its chart had ended,
        and its process was only exiting (about a second after the result) when the kill came. NotRunning when none
        runs, also for a second cancel while the first is at work (the lock is held throughout, so one cancel, one
        `cancelled` event, and no job starts until the staging is gone)."""
        with self._lock:
            job = self.current
            if job is None or job.state != "running" or job.tree is None or (job_id is not None and job.id != job_id):
                raise NotRunning()
            with job.cond:
                job.cancelling = True
            code = job.tree.kill(self.kill_timeout)
            if job.reader is not None:
                job.reader.join(timeout=10)   # the pipe closes with the last process of the group
            for folder in partial_folders(job.out):
                shutil.rmtree(folder, ignore_errors=True)
            self._unmark(job)
            with job.cond:
                job.returncode = code
                if job._has("result"):
                    job.state = "done"      # it finished before the kill reached it (or while it was exiting)
                elif job._has("error"):
                    job.state = "failed"    # so did this one, with its error
                else:
                    job.state = "cancelled"
                    job.events.append({"event": "cancelled", "at": round(time.time(), 3)})
                job.ended = time.time()
                job.cond.notify_all()
        self.log(f"job {job.id}: {job.state} (exit {code}); the work folder's caches stay")
        self._ended(job)
        return job

    def shutdown(self) -> None:
        """The server is stopping: a running job's tree goes."""
        try:
            self.cancel()
        except NotRunning:
            pass


# ------------------------------------------------------------------------------------------------ the queue (M8-10)

QUEUE_MAX = 20            # waiting songs at most [judgement: the design note's 6.]
KEEP_FINISHED = 50        # finished songs kept in the list and queue.json, the oldest dropped first [judgement]
FAILURES_PAUSE = 2        # this many songs in a row that do not finish pause the queue (exit 2 is often the machine)
STATES = ("waiting", "charting", "ready", "check_failed", "not_finished", "cancelled")
FINISHED = STATES[2:]
LYRICS_WAIT = ("Lyrics only for a song that starts at once: songcharter keeps pasted lyrics only while it uses them. "
               "Chart this song without them, or add it once nothing is charting.")
# a song added again while it waits or charts (the same upload; the v0.5.0 review's install-01): it would chart twice,
# into the same library folder. By where it is: charting, waiting (the list paused: after a restart, say), waiting
ALREADY = {"charting": "This song is already in the list: it is charting now.",
           "paused": "This song is already in the list: press Carry on to chart it.",
           "waiting": "This song is already in the list: it is charted in its turn."}


class QueueFull(Exception):
    """QUEUE_MAX songs wait already (the server answers 409)."""


class NotInQueue(Exception):
    """No such song in the list, the charting one (cancel it instead), or no song waiting to pause (409)."""


def queue_path(home: Path) -> Path:
    return Path(home) / "state" / "queue.json"


def queued_uploads(home: Path) -> set[str]:
    """The uploads queue.json's waiting songs name (each song's file and its pictures): kept past the 7 days' pruning
    until their song is charted or removed."""
    try:
        data = json.loads(queue_path(home).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return set()
    keep: set[str] = set()
    for e in (data.get("entries") or []) if isinstance(data, dict) else []:
        if not _entry_ok(e) or e["state"] not in ("waiting", "charting"):
            continue
        keep.add(e["upload"]["id"])
        keep.update(v for k, v in e["options"].items() if k in IMAGE_FLAGS and isinstance(v, str))
    return keep


def _entry_ok(e: Any) -> bool:
    return (isinstance(e, dict) and isinstance(e.get("id"), str) and e.get("state") in STATES
            and isinstance(e.get("upload"), dict) and isinstance(e["upload"].get("id"), str)
            and isinstance(e.get("options"), dict) and isinstance(e.get("run"), int))


class Kept:
    """A finished song's job as the queue keeps it (its closing event and times): what the routes by job id need once
    it is not the current job, after a restart too (results, preview, art, listen, install, zip, Look)."""

    def __init__(self, entry: Mapping[str, Any]):
        self.entry = entry
        self.id: str = entry["job"]
        self.state: str = entry.get("job_state") or "failed"
        self.upload = entry["upload"]
        self.started = entry.get("started")
        self.ended = entry.get("ended")

    def result(self) -> dict | None:
        closing = self.entry.get("closing")
        return dict(closing) if isinstance(closing, dict) and closing.get("event") == "result" else None

    def snapshot(self, events: bool = True) -> dict:
        closing = self.entry.get("closing")
        out = {"job": self.id, "state": self.state, "upload": {"id": self.upload.get("id"),
                                                               "name": self.upload.get("name")},
               "options": dict(self.entry.get("options") or {}), "started": self.started, "ended": self.ended,
               "exit": None, "now": time.time(), "estimate": self.entry.get("estimate"), "remaining": None,
               "kept": True}
        if events:
            out["events"] = [dict(closing)] if isinstance(closing, dict) else []
        return out


class Queue:
    """The server's waiting list (M8-10, DESIGN.md 4.5): songs added with their options (checked when added), charted
    one after the other by `jobs` (its one child process group at a time), the next started by the server itself when
    one ends (Jobs.on_end), so a closed or hidden tab never stops the evening. Kept in <home>/state/queue.json (whole,
    through a temporary file), with no lyrics: a song that waits never has them (LYRICS_WAIT).

    `prepare(entry)` gives (the upload's record, the ChartOptions, the doctor's device) for a song about to start (an
    InputError when its file or a picture is gone); `disk_low()` a message when the disk is under device.MIN_FREE,
    else None, asked before each song the queue starts itself.

      * **A restart:** the song that was charting goes back to waiting at the top (its stages' and takes' caches stay),
        and with songs waiting the queue is paused ("restart") until Carry on or Clear the list.
      * **Cancel** (Jobs.cancel) ends the charting song only, as `cancelled`; the next starts.
      * **Pause** ("you"): the charting song finishes and none starts until Carry on.
      * **Two songs in a row that do not finish** (exit 2 or 3, killed, or a song that cannot start) pause the queue
        ("failures"); a failed check (exit 1) is a finished chart, "check_failed".
      * **The disk** under device.MIN_FREE before a song: paused ("disk", with why).
    """

    def __init__(self, jobs: Jobs, home: Path, prepare: Callable[[dict], tuple[Mapping, ChartOptions, str | None]],
                 disk_low: Callable[[], str | None] = lambda: None, log: Callable[[str], None] | None = None):
        self.jobs = jobs
        self.path = queue_path(home)
        self.prepare = prepare
        self.disk_low = disk_low
        self.log = log or (lambda text: None)
        self._lock = threading.RLock()
        self.entries: list[dict] = []
        self.paused: str | None = None   # restart, you, failures, disk; None: it goes on
        self.why: str | None = None      # the disk's message
        self.restarted = 0               # the songs that were waiting when songcharter closed
        self.failures = 0                # songs in a row that did not finish
        self.run = 0                     # the current evening's number: a song added to an idle queue starts one
        self.stopping = False
        self.dropped: dict[str, str] = {}   # a finished song's job id -> its chart's library id, once out of the list
        jobs.on_end = self._on_end
        self._load()

    # --- queue.json
    def _load(self) -> None:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return
        except (OSError, ValueError) as e:
            self.log(f"queue: {self.path} could not be read ({e}): the list starts empty")
            return
        if not isinstance(data, dict):
            return
        self.entries = [e for e in data.get("entries") or [] if _entry_ok(e)]
        for e in self.entries:
            if e["state"] == "charting":   # stopped while it charted: back to waiting at the top
                self._back(e)
        run = data.get("run")
        self.run = run if isinstance(run, int) else max((e["run"] for e in self.entries), default=0)
        waiting = len(self._waiting())
        if waiting:
            self.paused, self.restarted = "restart", waiting
            self.log(f"queue: {waiting} song(s) were waiting when songcharter closed: paused until Carry on")

    def _save(self) -> None:
        tmp = self.path.with_name(self.path.name + ".part")
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp.write_text(json.dumps({"version": 1, "run": self.run, "entries": self.entries}, indent=1,
                                      ensure_ascii=False, default=str) + "\n", encoding="utf-8")
            os.replace(tmp, self.path)
        except OSError as e:   # a full disk: the list goes on in memory
            try:
                tmp.unlink(missing_ok=True)
            except OSError:
                pass
            self.log(f"queue: {self.path} could not be written ({e})")

    # --- reading the list
    def _waiting(self) -> list[dict]:
        return [e for e in self.entries if e["state"] == "waiting"]

    def _charting(self) -> dict | None:
        return next((e for e in self.entries if e["state"] == "charting"), None)

    def _find(self, entry_id: Any) -> dict | None:
        return next((e for e in self.entries if e["id"] == entry_id), None)

    def job(self, job_id: str) -> Job | Kept | None:
        """The job of that id: the current one, else a finished song's as the queue keeps it; None for any other."""
        cur = self.jobs.current
        if cur is not None and cur.id == job_id:
            return cur
        with self._lock:
            entry = next((e for e in self.entries if e.get("job") == job_id and e["state"] in FINISHED), None)
            return Kept(entry) if entry is not None else None

    def dropped_chart(self, job_id: str) -> str | None:
        """The library id of the chart a finished song made, once Clear the list, Remove or the trim has taken the
        song out of the list (`_drop`), for this server's life; None for any other id. A Done screen still open on
        that song (a Look) names it by its job id: its chart is a library chart, so the server finds it there
        (server.py's Handler._job; the v0.5.0 review's correct-1)."""
        with self._lock:
            return self.dropped.get(job_id)

    def _drop(self, gone: Sequence[dict]) -> None:
        """Songs leaving the list: each finished one's chart (its result's folder) recorded by its job id."""
        for e in gone:
            closing = e.get("closing") if isinstance(e.get("closing"), dict) else {}
            folder = closing.get("folder") if closing.get("event") == "result" else None
            if isinstance(e.get("job"), str) and folder:
                self.dropped[e["job"]] = chart_id(Path(str(folder)))

    def snapshot(self) -> dict:
        """GET /api/queue: {"paused", "why", "restarted", "run", "max", "entries", "left"} (DESIGN.md 4.5)."""
        with self._lock:
            self._settle()
            waiting = bool(self._waiting())
            return {"paused": self.paused if waiting else None, "why": self.why if waiting else None,
                    "restarted": self.restarted if waiting and self.paused == "restart" else 0,
                    "run": self.run, "max": QUEUE_MAX, "entries": [self._public(e) for e in self.entries],
                    "left": self._left()}

    @staticmethod
    def _public(e: dict) -> dict:
        closing = e.get("closing") if isinstance(e.get("closing"), dict) else {}
        folder = closing.get("folder") if closing.get("event") == "result" else None
        chart = Path(str(folder)).name if folder else None
        if chart and chart.endswith(".failed"):
            chart = chart[:-len(".failed")]
        message = (closing.get("plain") or closing.get("message")) if closing.get("event") == "error" else None
        return {"id": e["id"], "run": e["run"], "name": e["upload"].get("name"), "chart": chart, "state": e["state"],
                "job": e.get("job"), "estimate": e.get("estimate"), "added": e.get("added"),
                "started": e.get("started"), "ended": e.get("ended"),
                "error": str(message).split("\n", 1)[0].rstrip(":") if message else None,
                "lyrics_lost": bool(e.get("lyrics_lost"))}

    def _left(self) -> dict | None:
        """The whole queue's time left: the waiting songs' ranges summed, with the charting song's time left (its
        re-estimate once a take is timed; before, its range less the time it has run), each at least 0; None with
        nothing to chart, or a song without an estimate."""
        waiting, charting = self._waiting(), self._charting()
        if not waiting and charting is None:
            return None
        low = high = 0.0
        for e in waiting:
            est = e.get("estimate") or {}
            if not isinstance(est.get("low_s"), (int, float)) or not isinstance(est.get("high_s"), (int, float)):
                return None
            low, high = low + est["low_s"], high + est["high_s"]
        if charting is not None:
            job = self.jobs.current
            if job is None or job.id != charting.get("job"):
                return None
            snap = job.snapshot(events=False)
            rem, est, now = snap.get("remaining") or {}, snap.get("estimate") or {}, time.time()
            if rem.get("from") is not None and rem.get("high_s") is not None:
                lo, hi = rem["low_s"] - (now - rem["from"]), rem["high_s"] - (now - rem["from"])
            elif isinstance(est.get("low_s"), (int, float)) and isinstance(est.get("high_s"), (int, float)):
                lo, hi = est["low_s"] - (now - job.started), est["high_s"] - (now - job.started)
            else:
                return None
            low, high = low + max(0.0, lo), high + max(0.0, hi)
        return {"low_s": round(low), "high_s": round(high), "songs": len(waiting) + (charting is not None)}

    # --- changing it
    def add(self, upload: Mapping[str, Any], options: Mapping[str, Any], estimate: Mapping[str, Any] | None = None,
            lyrics: str | None = None) -> tuple[dict, Job | None]:
        """A song at the end of the list, with the page's `options` as checked (the pictures as upload ids, no
        lyrics) and its estimate: (its entry, its job when it starts at once: nothing charting and none waiting).
        `lyrics` only for a song that starts at once, else an InputError (LYRICS_WAIT); QueueFull at QUEUE_MAX waiting;
        an InputError (ALREADY) for a song whose upload is already waiting or charting (a finished one may be charted
        again); prepare's InputError, or JobRunning, for a song that cannot start at once (it is not kept). A chart
        whose result is out and whose process is still exiting is waited for first, as Jobs.start does."""
        cur = self.jobs.current
        if cur is not None and cur.state == "running":
            with cur.cond:
                closed = cur._closed()
            if closed:
                cur.wait_end(END_WAIT_S)
        with self._lock:
            self._settle()
            same = next((e for e in self.entries if e["state"] in ("waiting", "charting")
                         and e["upload"].get("id") == upload.get("id")), None)
            if same is not None:
                raise InputError(ALREADY["charting" if same["state"] == "charting" else
                                         "paused" if self.paused is not None else "waiting"])
            waiting = self._waiting()
            now = self._charting() is None and not waiting
            if not now and lyrics is not None:
                raise InputError(LYRICS_WAIT)
            if len(waiting) >= QUEUE_MAX:
                raise QueueFull(f"{QUEUE_MAX} song{' is' if QUEUE_MAX == 1 else 's are'} waiting already: add more "
                                "once some are charted")
            if now:   # a new evening
                self.run, self.failures, self.paused, self.why, self.restarted = self.run + 1, 0, None, None, 0
            entry = {"id": secrets.token_hex(6), "run": self.run,
                     "upload": {k: upload.get(k) for k in ("id", "name", "seconds")},
                     "options": {k: v for k, v in options.items() if k != "lyrics"},
                     "estimate": dict(estimate) if estimate else None, "state": "waiting", "job": None,
                     "lyrics": lyrics is not None,   # whether it had some, never the text (S-S2)
                     "job_state": None, "added": time.time(), "started": None, "ended": None, "closing": None}
            self.entries.append(entry)
            job = None
            if now:
                try:
                    job = self._start(entry, lyrics)
                except BaseException:
                    self.entries.remove(entry)
                    raise
            self._trim()
            self._save()
            self.log(f"queue: {entry['upload'].get('name')} " + (f"started (job {job.id})" if job else
                                                                 f"waits ({len(self._waiting())} waiting)"))
            return dict(entry), job

    def _start(self, entry: dict, lyrics: str | None = None) -> Job:
        upload, opts, auto = self.prepare(entry)
        if lyrics is not None:
            from dataclasses import replace
            opts = replace(opts, lyrics=lyrics)
        job = self.jobs.start(upload, opts, auto_device=auto, estimate=entry.get("estimate"))
        entry.update(state="charting", job=job.id, started=job.started)
        return job

    def pause(self) -> None:
        """Pause after this song: the charting one finishes, none starts until Carry on."""
        with self._lock:
            self._settle()
            if not self._waiting():
                raise NotInQueue("no song is waiting")
            self.paused, self.why = "you", None
            self.log("queue: paused after this song")

    def carry_on(self) -> None:
        with self._lock:
            self._settle()
            self.paused, self.why, self.restarted, self.failures = None, None, 0, 0
            self.log("queue: carry on")
            self._advance()
            self._save()

    def remove(self, entry_id: Any) -> None:
        """A waiting or finished song out of the list (its chart stays in the library); not the charting one."""
        with self._lock:
            self._settle()
            entry = self._find(entry_id)
            if entry is None:
                raise NotInQueue("no such song in the list")
            if entry["state"] == "charting":
                raise NotInQueue("that song is charting: cancel it instead")
            self.entries.remove(entry)
            self._drop([entry])
            if not self._waiting():
                self.paused, self.why, self.restarted = None, None, 0
            self._save()

    def clear(self) -> None:
        """Clear the list: every song but the charting one (their charts stay in the library)."""
        with self._lock:
            self._settle()
            self._drop([e for e in self.entries if e["state"] != "charting"])
            self.entries = [e for e in self.entries if e["state"] == "charting"]
            self.paused, self.why, self.restarted = None, None, 0
            self._save()
            self.log("queue: the list cleared")

    def shutdown(self) -> None:
        """The server is stopping: the charting song's tree goes (Jobs.shutdown), and the song goes back to waiting at
        the top, unless it had finished meanwhile."""
        with self._lock:
            self.stopping = True
        self.jobs.shutdown()
        with self._lock:
            entry = self._charting()
            if entry is not None:
                job = self.jobs.current
                if job is not None and job.id == entry.get("job") and job.state in ("done", "failed"):
                    self._record(entry, job)
                else:
                    self._back(entry)
            self._save()

    @staticmethod
    def _back(entry: dict) -> None:
        """The charting song back to waiting (the window closed, or a crash); its pasted lyrics, which were never
        kept, are said lost (`lyrics_lost`), so the page can say so (S-S2)."""
        entry.update(state="waiting", job=None, job_state=None, started=None, ended=None, closing=None)
        if entry.get("lyrics"):
            entry["lyrics_lost"] = True

    # --- one song's end, and the next
    def _on_end(self, job: Job) -> None:
        with self._lock:
            if self.stopping:
                return
            try:
                self._settle()
                self._advance()
            except Exception as e:  # noqa: BLE001  a bug here must not stop the evening's log
                self.log(f"queue: internal error after job {job.id}: {type(e).__name__}: {e}")

    def _settle(self) -> None:
        """The charting song's end recorded, once its job has ended (idempotent: the end's own thread or any request,
        whichever comes first)."""
        entry = self._charting()
        if entry is None or self.stopping:
            return
        job = self.jobs.current
        if job is not None and job.id == entry.get("job"):
            if job.state != "running":
                self._record(entry, job)
        else:   # never seen: its job is not the current one
            entry.update(state="not_finished", job_state="failed", ended=time.time(),
                         closing={"event": "error", "kind": "bug", "message": "songcharter lost this chart",
                                  "at": round(time.time(), 3)})
            self.failures += 1
            self._save()

    def _record(self, entry: dict, job: Job) -> None:
        with job.cond:
            closing = next((dict(e) for e in reversed(job.events) if e["event"] in CLOSING), None)
            state, ended = job.state, job.ended
        entry.update(job_state=state, ended=ended, closing=closing)
        if state == "done":
            entry["state"] = "ready" if (closing or {}).get("ok") else "check_failed"
            self.failures = 0
        elif state == "cancelled":
            entry["state"] = "cancelled"
            self.failures = 0
        else:
            entry["state"] = "not_finished"
            self.failures += 1
        self.log(f"queue: {entry['upload'].get('name')}: {entry['state']}")
        self._pause_on_failures()
        self._save()

    def _pause_on_failures(self) -> None:
        if self.failures >= FAILURES_PAUSE and self._waiting() and self.paused is None:
            self.paused = "failures"
            self.log(f"queue: {self.failures} songs in a row did not finish: paused")

    def _advance(self) -> None:
        """Start the next waiting song, unless the queue is paused, stopping or charting; the disk is measured first."""
        while not self.stopping and self._charting() is None:
            waiting = self._waiting()
            if not waiting:
                self.paused, self.why, self.restarted = None, None, 0   # nothing left to pause
                return
            if self.paused is not None:
                return
            try:
                low = self.disk_low()
            except Exception:  # noqa: BLE001  the disk not measured: no pause for it
                low = None
            if low:
                self.paused, self.why = "disk", low
                self.log(f"queue: paused: {low}")
                self._save()
                return
            entry = waiting[0]
            try:
                self._start(entry)
            except JobRunning:   # a job outside the queue: its end comes back here
                return
            except Exception as e:  # noqa: BLE001  the song file or a picture gone, a full disk: the song's error
                message = str(e) if isinstance(e, InputError) else f"it could not start: {type(e).__name__}: {e}"
                entry.update(state="not_finished", job_state="failed", ended=time.time(),
                             closing={"event": "error", "kind": "input" if isinstance(e, InputError) else "tool",
                                      "message": message, "at": round(time.time(), 3)})
                self.failures += 1
                self.log(f"queue: {entry['upload'].get('name')} could not start: {message}")
                self._pause_on_failures()
                self._save()
                continue
            self._save()
            return

    def _trim(self) -> None:
        finished = [e for e in self.entries if e["state"] in FINISHED]
        gone = finished[:max(0, len(finished) - KEEP_FINISHED)]
        for e in gone:
            self.entries.remove(e)
        self._drop(gone)


# ------------------------------------------------------------------------------------------------ the library (M8-13)

LIBRARY = "library"                # <home>/library: every chart the page has made (output_folder)
UPLOAD_HEX = re.compile(r"^[0-9a-f]{16}$")   # a library folder's upload: cache.KEY_HEX hex characters
LIBRARY_ID = re.compile(r"^([0-9a-f]{16}):([^/\\\x00]+)$")   # a chart's id: its upload's 16 hex and its folder's name
FAILED = ".failed"                 # pipeline.failed_folder's suffix: a build the gate failed, kept for a look
STEMS_SUFFIX = " (stems)"          # pipeline.STEMS_SUFFIX (not imported: the pipeline is the child's)
SPLIT_FILES = ("guitar.ogg", "bass.ogg", "drums.ogg")   # package.SPLIT_PARTS' own files (M8-12)


def chart_folders(home: Path) -> list[Path]:
    """The library's charts: <home>/library/<16 hex>/<name>/ folders that hold a report.json (readable or not); not
    a hidden one (assemble's .partial staging), not a link."""
    found = []
    try:
        uploads = sorted((home / LIBRARY).iterdir()) if (home / LIBRARY).is_dir() else []
    except OSError:
        return []
    for up in uploads:
        if not UPLOAD_HEX.match(up.name) or up.is_symlink() or not up.is_dir():
            continue
        try:
            folders = sorted(up.iterdir())
        except OSError:
            continue
        found += [f for f in folders if not f.name.startswith(".") and not f.is_symlink() and f.is_dir()
                  and (f / "report.json").is_file()]
    return found


def chart_id(folder: Path) -> str:
    """A library chart's id: `<its upload's 16 hex>:<its folder's name>` (a name has no ":", cache.safe_name)."""
    return f"{folder.parent.name}:{folder.name}"


def find_chart(home: Path, chart: Any) -> Path | None:
    """The library folder of that id, found among the folders the library holds (no path is made from the id); None
    for anything else."""
    if not isinstance(chart, str) or not LIBRARY_ID.match(chart):
        return None
    return next((f for f in chart_folders(home) if chart_id(f) == chart), None)


def _song_ini(folder: Path) -> dict[str, str]:
    """song.ini's [song] values by their lower-case keys; {} when it cannot be read."""
    try:
        lines = (folder / "song.ini").read_text(encoding="utf-8-sig", errors="replace").splitlines()
    except OSError:
        return {}
    out, section = {}, None
    for line in (x.strip() for x in lines):
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1].strip().lower()
        elif "=" in line and section == "song":
            key, _, value = line.partition("=")
            out[key.strip().lower()] = value.strip()
    return out


def _stems(folder: Path) -> Path | None:
    """The stems saved beside the song folder (pipeline.stems_folder: "<its name, without .failed> (stems)"), when
    that folder holds .flac files; else None."""
    base = folder.name[:-len(FAILED)] if folder.name.endswith(FAILED) else folder.name
    stems = folder.with_name(base + STEMS_SUFFIX)
    try:
        return stems if stems.is_dir() and not stems.is_symlink() and any(stems.glob("*.flac")) else None
    except OSError:
        return None


def _work(folder: Path, root: Path | None) -> tuple[Path | None, dict]:
    """The song's work folder in the cache (cache.by_key, by the upload's 16 hex: the song file's key) and its
    pipeline.json, when that record's last chart is this folder (a chart of the same song with other options, made
    later, has the work folder now); else (None, {})."""
    if root is None:
        return None, {}
    try:
        work = cache.by_key(root, folder.parent.name)
        if work is None:
            return None, {}
        record = json.loads((work / "pipeline.json").read_text(encoding="utf-8"))
        made = Path(str(record["assemble"]["folder"]))
        same = made.resolve() == folder.resolve()
    except (OSError, ValueError, KeyError, TypeError):
        return None, {}
    return (work, record) if same else (None, {})


def read_chart(folder: Path, root: Path | None) -> dict:
    """One chart of the library as GET /api/library lists it: {"id", "folder" (its folder's name), "name", "artist"
    (song.ini's; the folder's name when it has none), "time" (report.json's, seconds), "readable" (report.json read,
    with its gate), "ok" (the gate passed: Install), "audio" ("one", "split" or null), "stems" (saved beside it),
    "look" (the work folder is still in the cache: the preview and Listen)}."""
    base = folder.name[:-len(FAILED)] if folder.name.endswith(FAILED) else folder.name
    try:
        when = (folder / "report.json").stat().st_mtime
    except OSError:
        when = None
    try:
        report = json.loads((folder / "report.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        report = None
    gate = report.get("gate") if isinstance(report, dict) else None
    readable = isinstance(gate, dict) and isinstance(gate.get("ok"), bool)
    ini = _song_ini(folder)
    files = report.get("audio_files") if isinstance(report, dict) else None
    if isinstance(files, list) and files:   # M8-12's record of the files it wrote
        audio = "split" if len(files) > 1 else "one"
    else:   # an earlier build's, or no report: the files there
        audio = ("split" if any((folder / f).is_file() for f in SPLIT_FILES) else
                 "one" if (folder / "song.ogg").is_file() else None)
    return {"id": chart_id(folder), "folder": folder.name, "name": ini.get("name") or base,
            "artist": ini.get("artist") or None, "time": when, "readable": readable,
            "ok": readable and gate["ok"] is True and not folder.name.endswith(FAILED), "audio": audio,
            "stems": _stems(folder) is not None, "look": _work(folder, root)[0] is not None}


def library(home: Path, root: Path | None) -> list[dict]:
    """Every chart of the library (read_chart), newest first; one without a time last."""
    charts = [read_chart(f, root) for f in chart_folders(home)]
    return sorted(charts, key=lambda c: (c["time"] is None, -(c["time"] or 0), c["id"]))


class Charted:
    """A chart of the library as the routes by id take it (M8-13): its id, and a `result` made from its folder (the
    gate's verdict, the stems beside it, and the work folder and its preview while the cache keeps them), so Install,
    Open, the zips, the results and Listen are the queue's own routes."""

    def __init__(self, folder: Path, root: Path | None, job_id: str | None = None):
        self.folder = folder
        self.id = job_id or chart_id(folder)   # a finished song's job id when found through it (Queue.dropped_chart)
        self.state = "done"
        self.info = read_chart(folder, root)
        self.work, self.record = _work(folder, root)

    def result(self) -> dict:
        ok = self.info["ok"]
        preview = self.record.get("preview") if isinstance(self.record.get("preview"), dict) else {}
        stems = _stems(self.folder)
        return {"event": "result", "ok": ok, "exit": 0 if ok else 1, "folder": str(self.folder),
                "work": str(self.work) if self.work is not None else None,
                "preview": str(self.work / "preview") if self.work is not None and preview.get("ok") else None,
                "stems": str(stems) if stems is not None else None, "summary": None}

    def snapshot(self, events: bool = True) -> dict:
        out = {"job": self.id, "state": self.state, "upload": {"id": self.folder.parent.name, "name": None},
               "options": {}, "started": None, "ended": self.info["time"], "exit": 0 if self.info["ok"] else 1,
               "now": time.time(), "estimate": None, "remaining": None, "kept": True, "library": True}
        if events:
            out["events"] = [self.result()]
        return out
