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
    Windows, as M4-06 copies the folder to /mnt/c.
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
  * **Lyrics** (M4-06, from M4-10): the page's pasted text (`lyrics`, None when the box is empty or blank) goes only
    into the chart. The job writes it into a memory file (memfd, Linux), which the child gets as an open file and
    reads as `--lyrics=/dev/fd/<n>`: nothing on disk, and the command line, the log, the job's options (`lyrics`:
    whether given) and every event name the file, never a word of it.
"""
from __future__ import annotations

import glob
import json
import os
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
from ..timed import DIFFICULTIES, INSTRUMENTS

EVENT_PREFIX = "@@songcharter "   # cli.EVENT_PREFIX (not imported: the cli module is the child's)
CLOSING = ("result", "error", "cancelled")   # the events after which a job's stream ends
META_FLAGS = {"title": "--title", "artist": "--artist", "album": "--album", "year": "--year", "genre": "--genre"}
OPTION_KEYS = (*META_FLAGS, "instruments", "levels", "solos", "takes", "device", "threads", "preview", "lyrics")
TAIL_LINES = 8                     # the log's last lines in an error the job writes itself
END_WAIT_S = 10.0                  # how long a new job waits for one whose closing event is out to exit


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

    def as_dict(self) -> dict:
        """The options as the job's records show them: `lyrics` is whether some were given, never the text."""
        return {"instruments": list(self.instruments), "levels": list(self.levels),
                "solos": self.solos if isinstance(self.solos, str) else list(self.solos), "takes": self.takes,
                "device": self.device, "threads": self.threads, "preview": self.preview,
                "lyrics": self.lyrics is not None, **self.metadata}


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
    options = ChartOptions(instruments=instruments, levels=levels, solos=solos, takes=get.get("takes"),
                           device=get.get("device", "auto"), threads=get.get("threads"), preview=preview,
                           metadata=meta, lyrics=lyrics if lyrics and lyrics.strip() else None)
    pipeline_meta = {"name" if k == "title" else k: v for k, v in meta.items()}
    Options(instruments=options.instruments, takes=options.takes, device=options.device, threads=options.threads,
            metadata=pipeline_meta, solos=options.solos, levels=options.levels, preview=options.preview,
            lyrics=options.lyrics).check()
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
    cmd += [f"{flag}={options.metadata[key]}" for key, flag in META_FLAGS.items() if key in options.metadata]
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
    """<home>/library/<the upload's id>/<cache.safe_name(f"{artist} - {title}")>."""
    tags = upload.get("metadata") or {}
    artist = options.metadata.get("artist") or tags.get("artist") or "Unknown"
    title = options.metadata.get("title") or tags.get("name") or Path(upload["path"]).stem
    return home / "library" / upload["id"] / cache.safe_name(f"{artist} - {title}")


def partial_folders(out: Path) -> list[Path]:
    """assemble's staging folders for the output `out`: .<name>.*.partial beside it (the name escaped: a song's
    name keeps [ and ], which a glob reads as a character class)."""
    try:
        return sorted(p for p in out.parent.glob(f".{glob.escape(out.name)}.*.partial") if p.is_dir())
    except OSError:
        return []


def _stamp() -> str:
    return time.strftime("%Y%m%d-%H%M%S")


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
                   "started": self.started, "ended": self.ended, "exit": self.returncode, "now": time.time()}
            if events:
                out["events"] = list(self.events)
            return out

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
        self._lock = threading.Lock()

    def _log_path(self) -> tuple[str, Path]:
        folder = self.home / "logs"
        folder.mkdir(parents=True, exist_ok=True)
        stamp = _stamp()
        name, n = stamp, 1
        while (folder / f"job-{name}.log").exists():
            n += 1
            name = f"{stamp}-{n}"
        return name, folder / f"job-{name}.log"

    def start(self, upload: Mapping[str, Any], options: Any, auto_device: str | None = None) -> Job:
        """Start the chart of `upload` ({"id", "path", "name", "metadata"}) with the page's `options` (parse_options;
        an InputError for bad ones). JobRunning while a job runs; a job that has sent its result or error but whose
        process is still exiting (a second or so) is waited for first, up to END_WAIT_S, as the page offers the next
        song as soon as the result is in."""
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
                job = Job(job_id, dict(upload), opts, cmd, out, log)
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

    def _finish(self, job: Job, code: int) -> None:
        """The end state from the exit code (a cancel's is set by cancel()). A chart that has sent its result is done,
        whatever its exit: the result comes after the build is in place."""
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
                    else:
                        why, kind = f"the chart exited {code}", "tool" if code == 2 else "bug"
                    message = why + (":\n" + "\n".join(job.tail) if job.tail else "")
                    job.events.append({"event": "error", "kind": kind, "message": message,
                                       "at": round(time.time(), 3)})
            job.ended = time.time()
            job.cond.notify_all()
        self.log(f"job {job.id}: {job.state} (exit {code})")

    def cancel(self) -> Job:
        """Kill the running job's whole tree, mark it cancelled, delete assemble's staging beside its output. A job
        whose result or error is out keeps that outcome (done, or failed), with no `cancelled`: its chart had ended,
        and its process was only exiting (about a second after the result) when the kill came. NotRunning when none
        runs, also for a second cancel while the first is at work (the lock is held throughout, so one cancel, one
        `cancelled` event, and no job starts until the staging is gone)."""
        with self._lock:
            job = self.current
            if job is None or job.state != "running" or job.tree is None:
                raise NotRunning()
            with job.cond:
                job.cancelling = True
            code = job.tree.kill(self.kill_timeout)
            if job.reader is not None:
                job.reader.join(timeout=10)   # the pipe closes with the last process of the group
            for folder in partial_folders(job.out):
                shutil.rmtree(folder, ignore_errors=True)
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
        return job

    def shutdown(self) -> None:
        """The server is stopping: a running job's tree goes."""
        try:
            self.cancel()
        except NotRunning:
            pass
