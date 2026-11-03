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
"""
from __future__ import annotations

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
OPTION_KEYS = (*META_FLAGS, "instruments", "levels", "solos", "takes", "device", "threads", "preview")
TAIL_LINES = 8                     # the log's last lines in an error the job writes itself


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

    def as_dict(self) -> dict:
        return {"instruments": list(self.instruments), "levels": list(self.levels),
                "solos": self.solos if isinstance(self.solos, str) else list(self.solos), "takes": self.takes,
                "device": self.device, "threads": self.threads, "preview": self.preview, **self.metadata}


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
    options = ChartOptions(instruments=instruments, levels=levels, solos=solos, takes=get.get("takes"),
                           device=get.get("device", "auto"), threads=get.get("threads"), preview=preview,
                           metadata=meta)
    pipeline_meta = {"name" if k == "title" else k: v for k, v in meta.items()}
    Options(instruments=options.instruments, takes=options.takes, device=options.device, threads=options.threads,
            metadata=pipeline_meta, solos=options.solos, levels=options.levels, preview=options.preview).check()
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


def output_folder(home: Path, upload: Mapping[str, Any], options: ChartOptions) -> Path:
    """<home>/library/<the upload's id>/<cache.safe_name(f"{artist} - {title}")>."""
    tags = upload.get("metadata") or {}
    artist = options.metadata.get("artist") or tags.get("artist") or "Unknown"
    title = options.metadata.get("title") or tags.get("name") or Path(upload["path"]).stem
    return home / "library" / upload["id"] / cache.safe_name(f"{artist} - {title}")


def partial_folders(out: Path) -> list[Path]:
    """assemble's staging folders for the output `out`: .<name>.*.partial beside it."""
    try:
        return sorted(p for p in out.parent.glob(f".{out.name}.*.partial") if p.is_dir())
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

    def snapshot(self, events: bool = True) -> dict:
        with self.cond:
            out = {"job": self.id, "state": self.state, "upload": {"id": self.upload["id"],
                                                                   "name": self.upload.get("name")},
                   "options": self.options.as_dict(), "out": str(self.out), "log": str(self.log),
                   "started": self.started, "ended": self.ended, "exit": self.returncode, "now": time.time()}
            if events:
                out["events"] = list(self.events)
            return out

    def _closed(self) -> bool:
        return any(e["event"] in CLOSING for e in self.events)


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
        an InputError for bad ones). JobRunning while a job runs."""
        opts = options if isinstance(options, ChartOptions) else parse_options(options)
        with self._lock:
            if self.current is not None and self.current.state == "running":
                raise JobRunning(self.current.id)
            song = Path(upload["path"])
            out = output_folder(self.home, upload, opts)
            cmd = [str(c) for c in self.command(song, out, opts, threads_for(opts, auto_device))]
            job_id, log = self._log_path()
            job = Job(job_id, dict(upload), opts, cmd, out, log)
            env = {**(os.environ if self.env is None else self.env), "PYTHONUTF8": "1"}
            out.parent.mkdir(parents=True, exist_ok=True)
            with open(log, "w", encoding="utf-8") as f:
                f.write(f"songcharter ui job {job_id}: {' '.join(cmd)}\n")
            job.tree = proc.start(cmd, env, None, subprocess.PIPE, subprocess.STDOUT)
            job.reader = threading.Thread(target=self._read, args=(job,), name=f"songcharter-job-{job_id}",
                                          daemon=True)
            self.current = job
            job.reader.start()
            self.log(f"job {job_id}: started on {upload.get('name') or song.name} (pid {job.tree.pid}), into {out}; "
                     f"log {log}")
            return job

    def _read(self, job: Job) -> None:
        assert job.tree is not None and job.tree.stdout is not None
        with open(job.log, "a", encoding="utf-8", errors="replace") as log:
            for raw in job.tree.stdout:
                line = raw.decode("utf-8", "replace").rstrip("\r\n")
                log.write(line + "\n")
                log.flush()
                event = parse_line(line)
                if event is not None:
                    job.add(event)
                elif line.strip():
                    job.tail = (job.tail + [line])[-TAIL_LINES:]
        code = job.tree.wait()
        self._finish(job, code)

    def _finish(self, job: Job, code: int) -> None:
        """The end state from the exit code (a cancel's is set by cancel())."""
        with job.cond:
            job.returncode = code
            if job.cancelling or job.state != "running":
                return
            if code in (0, 1) and any(e["event"] == "result" for e in job.events):
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
        that finished by itself meanwhile keeps its own state. NotRunning when none runs."""
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
            if code in (0, 1) and any(e["event"] == "result" for e in job.events):
                job.state = "done"      # it finished before the kill reached it
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
