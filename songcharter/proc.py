"""A child process and everything it starts, stopped as one (POSIX; M4-04). Standard library only.

    tree = proc.start([sys.executable, "-m", "songcharter.cli", "chart", ...], env, cwd, subprocess.PIPE,
                      subprocess.STDOUT)
    tree.kill()       # SIGTERM to the whole group, SIGKILL after 5 s, then wait(): idempotent

  * **One process group.** The command starts in a session of its own (`start_new_session`), so it leads a process
    group that holds everything it starts and does not move: for `songcharter chart`, autochart's driver (`node`) and
    the engine process the driver starts, allin1's runner, ffmpeg. `kill` signals that group, not one pid, so cancel
    stops all of them; and a Ctrl+C in the server's console reaches only the server, which then kills the group.
  * **Zombies.** A process that has exited but was not reaped yet (in a container whose PID 1 does not reap orphans,
    say) counts as gone: it runs nothing and holds nothing but its pid (`alive`).
  * Windows Job Objects belong to the native route (M4-99).
"""
from __future__ import annotations

import os
import signal
import subprocess
import threading
import time
from pathlib import Path
from typing import IO, Mapping, Sequence

KILL_TIMEOUT_S = 5.0     # from SIGTERM to SIGKILL
POLL_S = 0.05


def alive(pid: int) -> bool:
    """Whether the process `pid` exists and is not a zombie (Linux: /proc/<pid>/stat; elsewhere, whether it
    exists)."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:   # someone else's process: it exists
        return True
    try:
        stat = Path(f"/proc/{pid}/stat").read_text(encoding="ascii", errors="replace")
    except OSError:
        return True
    return stat.rpartition(")")[2].split()[:1] != ["Z"]   # the state follows the command's closing parenthesis


def group_alive(pgid: int) -> bool:
    """Whether the process group `pgid` has a member that is not a zombie (Linux: by /proc; elsewhere, whether a
    member exists)."""
    try:
        os.killpg(pgid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    try:
        entries = os.listdir("/proc")
    except OSError:
        return True
    for name in entries:
        if not name.isdigit():
            continue
        try:
            fields = Path(f"/proc/{name}/stat").read_text(encoding="ascii", errors="replace").rpartition(")")[2].split()
        except OSError:
            continue
        if len(fields) > 2 and fields[2] == str(pgid) and fields[0] != "Z":   # state, ppid, pgrp
            return True
    return False


class Tree:
    """A started command and its process group (`start`)."""

    def __init__(self, popen: subprocess.Popen):
        self.popen = popen
        self.pid = self.pgid = popen.pid   # the session's leader: its pid is the group's id
        self.killed = False                # kill() signalled the group while its leader was running
        self._lock = threading.Lock()
        self._done = False

    @property
    def stdout(self) -> IO | None:
        return self.popen.stdout

    def poll(self) -> int | None:
        return self.popen.poll()

    def wait(self, timeout: float | None = None) -> int:
        return self.popen.wait(timeout)

    def _signal(self, sig: int) -> None:
        try:
            os.killpg(self.pgid, sig)
        except (ProcessLookupError, PermissionError):
            pass

    def kill(self, timeout: float = KILL_TIMEOUT_S) -> int:
        """SIGTERM to the whole group; SIGKILL to it when the leader or any member is still running after `timeout`
        seconds; then wait() for the leader. Its exit code (negative: the signal). Idempotent: a second call (from
        another thread too) waits for the first and returns the same code. A leader that has exited by itself has its
        group signalled all the same, for what it left running."""
        with self._lock:
            if self._done:
                return self.popen.wait()
            self.killed = self.popen.poll() is None
            self._signal(signal.SIGTERM)
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                if self.popen.poll() is not None and not group_alive(self.pgid):
                    break
                time.sleep(POLL_S)
            else:
                self._signal(signal.SIGKILL)
            code = self.popen.wait()
            self._done = True
            return code


def start(cmd: Sequence[str], env: Mapping[str, str] | None = None, cwd: Path | str | None = None,
          stdout: int | IO | None = None, stderr: int | IO | None = None) -> Tree:
    """Start `cmd` in a session (and process group) of its own, stdin from /dev/null, with `env`, `cwd`, `stdout` and
    `stderr` as subprocess.Popen takes them."""
    popen = subprocess.Popen([str(c) for c in cmd], env=None if env is None else dict(env),
                             cwd=None if cwd is None else str(cwd), stdin=subprocess.DEVNULL, stdout=stdout,
                             stderr=stderr, start_new_session=True)
    return Tree(popen)
