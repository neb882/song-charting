#!/usr/bin/env python3
"""ui_guards.py (M4-05): the page's guards and a real cancel, against a real `songcharter ui` with a real chart.

    python packaging/ci/ui_guards.py --cmd "songcharter ui --no-browser --port 8799" --clip CLIP
        [--server-log PATH] [--report PATH] [--timeout S] [--shared-machine]

1. Starts CMD (in a session of its own; its --port says where) and waits up to 60 s for /api/hello.
2. The guards: `Host: evil.example` gives 403; a POST without `X-Songcharter` 403; `Origin: http://evil.example` 403;
   a .txt upload 415.
3. Uploads CLIP and starts a job on it with the defaults (202).
4. Follows the job's SSE stream. At the first `take` event, the guitar's take is about to start: once autochart's node
   driver (ac_headless.cjs) runs in the job's process tree, and its engine (autochart-engine.cjs) too, given up to 30 s
   more, it posts the cancel. Separation runs in the chart's own Python, so a cancel then proves that Node goes too
   (the advisor's finding 4). CLIP must not have been charted with this cache before: a warm cache has the guitar's
   take, sends no `take` event, and fails the check (M4-04's merge note).
5. Within 30 s of the cancel:
   - the job reads `cancelled`;
   - no process is left, as `ps -eo pid,args` would list them (read from /proc, as the Ubuntu image has no ps): none
     whose program is node, nor ac_headless.cjs, autochart-engine.cjs, allin1_runner.py or `songcharter.cli chart`;
     nor any process of the job's tree (the processes under the server at the cancel, their sessions and process
     groups). A zombie (exited, its parent yet to reap it) counts as gone, and is listed;
   - no .partial folder is left in the library. This one cannot fail here: assemble makes its staging folder in the
     stage after the guitar, so none exists at a cancel during the take. tests/test_ui_jobs.py is what guards the
     cleanup; this only checks that nothing else left one.
6. Starts the same job again: it ends `done` with `ok: true`, and every stage before the guitar is cached (the cancel
   kept them).
7. Stops the server with SIGTERM: it exits within 5 s, with status 0.

--shared-machine leaves out the scan of every process (step 5's pattern list) and checks only the job's own tree: on a
dev machine that other agents share, their node processes are not this server's. --report writes what it saw as JSON
(the checks and their times, both jobs' events, the job's tree at the cancel). --server-log takes the server's output
(else it goes to this one's).
Exit 0: every check passed. 1: a check failed (each one printed). 2: bad usage. Standard library only: the install's
Python runs it.
"""
from __future__ import annotations

import argparse
import http.client
import json
import os
import shlex
import signal
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import quote

HELLO_WAIT_S = 60.0
CANCEL_WAIT_S = 30.0        # step 5's window, from the cancel's POST
DRIVER_WAIT_S = 30.0        # after the take event, for ac_headless.cjs to show in the job's tree
ENGINE_WAIT_S = 30.0        # then for autochart-engine.cjs
STOP_WAIT_S = 5.0
READ_TIMEOUT_S = 60.0       # one read of the SSE stream (the server sends a keepalive every 15 s)
SCRIPTS = ("ac_headless.cjs", "autochart-engine.cjs", "allin1_runner.py")
BEFORE_GUITAR = ("decode", "separate", "drums", "bass", "sections")


class Fail(Exception):
    """A check failed: its message is the line the log shows."""


def say(text: str) -> None:
    print(f"ui_guards: {text}", flush=True)


# ------------------------------------------------------------------------------------------------ processes

class Proc:
    """One process, from /proc/<pid>/stat and cmdline."""

    def __init__(self, pid: int, ppid: int, pgid: int, sid: int, state: str, start: int, comm: str, argv: list[str]):
        self.pid, self.ppid, self.pgid, self.sid, self.state, self.start = pid, ppid, pgid, sid, state, start
        self.comm, self.argv = comm, argv

    @property
    def zombie(self) -> bool:
        return self.state in ("Z", "X")

    @property
    def args(self) -> str:
        """As `ps -eo args` shows it: the command line, or [comm] (and <defunct>) when it has none."""
        if self.argv:
            return " ".join(self.argv)
        return f"[{self.comm}]" + (" <defunct>" if self.zombie else "")

    def line(self) -> str:
        return f"{self.pid:>7} {self.args}"

    def key(self) -> tuple[int, int]:
        return self.pid, self.start


def processes() -> dict[int, Proc]:
    """Every process this user can see now, by pid."""
    out = {}
    for name in os.listdir("/proc"):
        if not name.isdigit():
            continue
        try:
            stat = Path(f"/proc/{name}/stat").read_text(encoding="utf-8", errors="replace")
            raw = Path(f"/proc/{name}/cmdline").read_bytes()
        except OSError:   # gone meanwhile
            continue
        head, _, rest = stat.rpartition(")")   # comm may hold spaces and parentheses
        comm = head.partition("(")[2]
        f = rest.split()
        try:
            proc = Proc(int(name), int(f[1]), int(f[2]), int(f[3]), f[0], int(f[19]), comm,
                        [a.decode("utf-8", "replace") for a in raw.split(b"\0") if a])
        except (IndexError, ValueError):
            continue
        out[proc.pid] = proc
    return out


def descendants(table: dict[int, Proc], root: int) -> list[Proc]:
    """The processes under `root`, by their parent links now."""
    children: dict[int, list[Proc]] = {}
    for p in table.values():
        children.setdefault(p.ppid, []).append(p)
    found, todo = [], [root]
    while todo:
        for child in children.get(todo.pop(), []):
            found.append(child)
            todo.append(child.pid)
    return found


def matches(p: Proc) -> bool:
    """One of step 5's names: a node program, one of SCRIPTS, or `songcharter.cli chart`."""
    if not p.argv:
        return p.comm in ("node", "nodejs")
    if os.path.basename(p.argv[0]) in ("node", "nodejs"):
        return True
    if any(os.path.basename(a) in SCRIPTS for a in p.argv):
        return True
    return "songcharter.cli chart" in " ".join(p.argv)


class Tree:
    """The job's process tree as it was at the cancel: the processes under the server, and their sessions and process
    groups (the chart runs in a session of its own, proc.start's), the server's own left out."""

    def __init__(self, server: Proc | None, procs: list[Proc]):
        own = {server.sid, server.pgid} if server is not None else set()
        self.procs = procs
        self.keys = {p.key() for p in procs}
        self.groups = {p.sid for p in procs} | {p.pgid for p in procs}
        self.groups -= own

    def left(self, table: dict[int, Proc]) -> list[Proc]:
        return [p for p in table.values() if p.key() in self.keys or p.sid in self.groups or p.pgid in self.groups]


# ------------------------------------------------------------------------------------------------ HTTP

class Client:
    def __init__(self, port: int):
        self.host, self.port = "127.0.0.1", port
        self.origin = f"http://{self.host}:{port}"
        self.ours = {"X-Songcharter": "1", "Origin": self.origin}

    def request(self, method: str, path: str, body: bytes | None = None, headers: dict | None = None,
                timeout: float = 60.0) -> tuple[int, bytes]:
        """The status and body. A Host header in `headers` replaces http.client's own."""
        conn = http.client.HTTPConnection(self.host, self.port, timeout=timeout)
        try:
            conn.request(method, path, body=body, headers=headers or {})
            r = conn.getresponse()
            return r.status, r.read()
        finally:
            conn.close()

    def json(self, method: str, path: str, value=None, timeout: float = 60.0) -> tuple[int, dict]:
        body = None if value is None else json.dumps(value).encode("utf-8")
        headers = {**self.ours, "Content-Type": "application/json"} if method != "GET" else {}
        code, data = self.request(method, path, body, headers, timeout)
        try:
            got = json.loads(data.decode("utf-8")) if data else {}
        except ValueError:
            got = {"raw": data[:400].decode("utf-8", "replace")}
        return code, got if isinstance(got, dict) else {"value": got}

    def hello(self) -> dict | None:
        try:
            code, got = self.json("GET", "/api/hello", timeout=2)
        except OSError:
            return None
        return got if code == 200 and got.get("app") == "songcharter" else None

    def events(self, deadline: float):
        """The current job's events over SSE (replayed from the first), until the stream closes or `deadline`."""
        conn = http.client.HTTPConnection(self.host, self.port, timeout=READ_TIMEOUT_S)
        try:
            conn.request("GET", "/api/jobs/current/events")
            r = conn.getresponse()
            if r.status != 200:
                raise Fail(f"the event stream answered {r.status}: {r.read()[:400]!r}")
            while True:
                if time.monotonic() > deadline:
                    raise Fail("the job did not end within --timeout")
                raw = r.readline()
                if not raw:
                    return
                line = raw.decode("utf-8", "replace").rstrip("\r\n")
                if line.startswith("data: "):
                    yield json.loads(line[6:])
        finally:
            conn.close()


# ------------------------------------------------------------------------------------------------ the run

class Run:
    def __init__(self, args: argparse.Namespace, port: int):
        self.args = args
        self.cmd = shlex.split(args.cmd)
        self.client = Client(port)
        self.clip = Path(args.clip)
        self.server: subprocess.Popen | None = None
        self.server_out = None
        self.tree: Tree | None = None
        self.checks: list[dict] = []
        self.jobs: list[dict] = []
        self.t0 = time.monotonic()

    def check(self, name: str, ok: bool, detail: str = "") -> None:
        self.checks.append({"check": name, "ok": ok, "detail": detail, "at_s": round(time.monotonic() - self.t0, 1)})
        say(f"{'ok' if ok else 'FAIL'}: {name}{': ' + detail if detail else ''}")
        if not ok:
            raise Fail(name)

    # --- 1. the server
    def start(self) -> None:
        if self.args.server_log:
            self.server_out = open(self.args.server_log, "ab")
        say(f"starting {' '.join(self.cmd)}")
        try:
            self.server = subprocess.Popen(self.cmd, stdin=subprocess.DEVNULL, stdout=self.server_out,
                                           stderr=subprocess.STDOUT if self.server_out else None,
                                           start_new_session=True)
        except OSError as e:
            raise Fail(f"{self.cmd[0]} did not start: {e}") from None
        t = time.monotonic()
        while time.monotonic() - t < HELLO_WAIT_S:
            got = self.client.hello()
            if got is not None:
                self.check("the server answers /api/hello", True,
                           f"version {got.get('version')} in {time.monotonic() - t:.1f} s")
                return
            if self.server.poll() is not None:
                self.check("the server answers /api/hello", False, f"it exited {self.server.returncode} first")
            time.sleep(0.25)
        self.check("the server answers /api/hello", False, f"no answer within {HELLO_WAIT_S:.0f} s")

    # --- 2. the guards
    def guards(self) -> None:
        c, clip = self.client, self.clip.read_bytes()
        cases = [
            ("Host: evil.example gives 403", 403, "GET", "/api/hello", None, {"Host": "evil.example"}),
            ("a POST without X-Songcharter gives 403", 403, "POST", "/api/upload", clip,
             {"Origin": c.origin, "X-Filename": "clip.wav"}),
            ("Origin: http://evil.example gives 403", 403, "POST", "/api/upload", clip,
             {"X-Songcharter": "1", "Origin": "http://evil.example", "X-Filename": "clip.wav"}),
            ("a .txt upload gives 415", 415, "POST", "/api/upload", b"not a song\n",
             {**c.ours, "X-Filename": "notes.txt"}),
        ]
        failed = []
        for name, want, method, path, body, headers in cases:
            code, data = c.request(method, path, body, headers)
            ok = code == want
            self.checks.append({"check": name, "ok": ok, "detail": f"HTTP {code}",
                                "at_s": round(time.monotonic() - self.t0, 1)})
            say(f"{'ok' if ok else 'FAIL'}: {name}: HTTP {code}"
                + ("" if ok else f": {data[:300].decode('utf-8', 'replace')}"))
            if not ok:
                failed.append(name)
        if failed:
            raise Fail("; ".join(failed))

    # --- 3. the upload and the job
    def upload(self) -> str:
        code, data = self.client.request("POST", "/api/upload", self.clip.read_bytes(),
                                         {**self.client.ours, "X-Filename": quote(self.clip.name)})
        got = json.loads(data.decode("utf-8")) if code == 200 else {}
        self.check("the clip uploads", code == 200 and bool(got.get("id")),
                   f"HTTP {code}, id {got.get('id')}, {got.get('bytes')} bytes, as {got.get('name')!r}"
                   if code == 200 else f"HTTP {code}: {data[:300]!r}")
        return got["id"]

    def start_job(self, upload: str, what: str) -> str:
        code, got = self.client.json("POST", "/api/jobs", {"upload": upload, "options": {}})
        self.check(f"{what} starts with the defaults", code == 202, f"HTTP {code}, job {got.get('job')}"
                   if code == 202 else f"HTTP {code}: {got}")
        return got["job"]

    def job(self) -> dict:
        code, got = self.client.json("GET", "/api/jobs/current")
        if code != 200:
            raise Fail(f"GET /api/jobs/current answered {code}: {got}")
        return got

    # --- 4. the cancel, at the first take
    def server_proc(self, table: dict[int, Proc]) -> Proc | None:
        assert self.server is not None
        return table.get(self.server.pid)

    def tree_now(self) -> tuple[dict[int, Proc], list[Proc]]:
        assert self.server is not None
        table = processes()
        return table, [p for p in descendants(table, self.server.pid) if not p.zombie]

    def wait_for(self, script: str, seconds: float) -> list[Proc]:
        t = time.monotonic()
        while True:
            _, procs = self.tree_now()
            found = [p for p in procs if any(os.path.basename(a) == script for a in p.argv)]
            if found or time.monotonic() - t > seconds:
                return found
            time.sleep(0.2)

    def cancel_at_take(self, deadline: float) -> None:
        take = None
        for event in self.client.events(deadline):   # to the stream's end, which comes once the job has ended
            kind = event.get("event")
            if kind == "stage_end":
                say(f"  {event.get('stage')}: {event.get('seconds')} s{' (cached)' if event.get('cached') else ''}")
            if kind == "take":
                take = event
                break
        if take is None:
            snap = self.job()
            self.jobs.append(snap)
            self.check("the job sends a take event", False,
                       f"it ended {snap.get('state')} with none: the guitar's take was cached (a warm cache; "
                       "chart a clip this cache has not seen) or the job failed: "
                       + json.dumps(snap.get("events", [])[-1:])[:600])
        self.check("the job sends a take event", True, json.dumps({k: take.get(k) for k in ("index", "count", "seed")}))
        driver = self.wait_for("ac_headless.cjs", DRIVER_WAIT_S)
        self.check("autochart's node driver runs in the job's tree", bool(driver),
                   ", ".join(f"pid {p.pid}" for p in driver) or f"not within {DRIVER_WAIT_S:.0f} s of the take event")
        engine = self.wait_for("autochart-engine.cjs", ENGINE_WAIT_S)
        say(f"autochart's engine: {', '.join(f'pid {p.pid}' for p in engine) if engine else 'not started within ' + str(int(ENGINE_WAIT_S)) + ' s (the cancel goes ahead: the driver is node)'}")
        table, procs = self.tree_now()
        self.tree = Tree(self.server_proc(table), procs)
        say("the job's tree at the cancel:")
        for p in procs:
            say(f"  {p.line()[:240]}")

        t = time.monotonic()
        code, got = self.client.json("POST", "/api/jobs/current/cancel", {})
        self.check("the cancel is accepted", code == 200, f"HTTP {code}, state {got.get('state')}, "
                   f"in {time.monotonic() - t:.1f} s")
        self.after_cancel(t)

    # --- 5. what the cancel leaves
    def after_cancel(self, t: float) -> None:
        assert self.tree is not None
        while True:
            snap = self.job()
            table = processes()
            mine = os.getpid()
            left = [p for p in self.tree.left(table) if p.pid != mine]
            if not self.args.shared_machine:
                left += [p for p in table.values() if matches(p) and p.pid != mine and p not in left]
            running = [p for p in left if not p.zombie]
            library = self.library(Path(snap["out"]))
            partials = sorted(str(p) for p in library.rglob("*.partial") if p.is_dir()) if library.is_dir() else []
            done = snap.get("state") == "cancelled" and not running and not partials
            if done or time.monotonic() - t > CANCEL_WAIT_S:
                break
            time.sleep(0.5)
        took = f"{time.monotonic() - t:.1f} s after the cancel"
        self.jobs.append(snap)
        self.check("the job reads cancelled", snap.get("state") == "cancelled", f"{snap.get('state')}, {took}")
        zombies = [p for p in left if p.zombie]
        if zombies:
            say("exited, not yet reaped (zombies, counted as gone): " + "; ".join(p.line().strip() for p in zombies))
        scope = "the job's tree" if self.args.shared_machine else "every process and the job's tree"
        self.check(f"no process is left ({scope})", not running,
                   took if not running else "; ".join(p.line().strip()[:200] for p in running))
        self.check("no .partial folder is left in the library", not partials,
                   f"{library}" if not partials else ", ".join(partials))

    @staticmethod
    def library(out: Path) -> Path:
        """<home>/library, from the job's output folder <home>/library/<id>/<name>."""
        return out.parents[1] if len(out.parents) > 1 and out.parents[1].name == "library" else out.parent

    # --- 6. the same job again
    def rerun(self, upload: str, deadline: float) -> None:
        self.start_job(upload, "the same job again")
        ends = []
        for event in self.client.events(deadline):
            if event.get("event") == "stage_end":
                ends.append(event)
                say(f"  {event.get('stage')}: {event.get('seconds')} s{' (cached)' if event.get('cached') else ''}")
        snap = self.job()
        self.jobs.append(snap)
        result = next((e for e in snap.get("events", []) if e.get("event") == "result"), None)
        last = (snap.get("events") or [{}])[-1]
        self.check("the second job ends done with ok: true",
                   snap.get("state") == "done" and result is not None and result.get("ok") is True,
                   f"{snap.get('state')}, exit {snap.get('exit')}, ok {None if result is None else result.get('ok')}"
                   + ("" if result else f": {json.dumps(last)[:600]}"))
        plan = next((e.get("stages") for e in snap.get("events", []) if e.get("event") == "plan"), None) or []
        before = plan[:plan.index("guitar")] if "guitar" in plan else [s for s in plan if s in BEFORE_GUITAR]
        cached = {e.get("stage"): e.get("cached") for e in ends}
        missing = [s for s in before if cached.get(s) is not True]
        self.check("the stages before the guitar are cached (the cancel kept them)", bool(before) and not missing,
                   ", ".join(before) if not missing else f"not cached: {', '.join(missing)} (plan {plan})")
        say("stage times: " + ", ".join(f"{e.get('stage')} {e.get('seconds')} s{' (cached)' if e.get('cached') else ''}"
                                        for e in ends))

    # --- 7. SIGTERM
    def stop(self) -> None:
        assert self.server is not None
        t = time.monotonic()
        self.server.send_signal(signal.SIGTERM)
        try:
            code = self.server.wait(STOP_WAIT_S)
        except subprocess.TimeoutExpired:
            self.check(f"SIGTERM stops the server within {STOP_WAIT_S:.0f} s", False, "it is still running")
            return
        self.check(f"SIGTERM stops the server within {STOP_WAIT_S:.0f} s", code == 0,
                   f"exit {code} in {time.monotonic() - t:.1f} s")

    def cleanup(self) -> None:
        """After a failure: the server (SIGTERM, which kills a running job's tree, then SIGKILL), then whatever is left
        of the job's tree, so the phases after this one find no server and no chart."""
        if self.server is not None and self.server.poll() is None:
            self.server.send_signal(signal.SIGTERM)
            try:
                self.server.wait(15)
            except subprocess.TimeoutExpired:
                os.killpg(self.server.pid, signal.SIGKILL)
                self.server.wait()
        if self.tree is not None:
            for group in self.tree.groups:
                try:
                    os.killpg(group, signal.SIGKILL)
                except OSError:
                    pass

    def report(self) -> None:
        if not self.args.report:
            return
        value = {"cmd": self.cmd, "clip": str(self.clip), "checks": self.checks, "jobs": self.jobs,
                 "tree_at_cancel": [p.line().strip() for p in self.tree.procs] if self.tree else None,
                 "seconds": round(time.monotonic() - self.t0, 1)}
        Path(self.args.report).write_text(json.dumps(value, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")

    def main(self) -> int:
        deadline = lambda: time.monotonic() + self.args.timeout   # noqa: E731
        try:
            self.start()
            self.guards()
            upload = self.upload()
            self.start_job(upload, "a job on the clip")
            self.cancel_at_take(deadline())
            self.rerun(upload, deadline())
            self.stop()
        except Fail as e:
            say(f"FAILED: {e}")
            self.cleanup()
            self.tail()
            return 1
        except BaseException:
            self.cleanup()
            raise
        finally:
            self.report()
            if self.server_out is not None:
                self.server_out.close()
        say(f"all checks passed in {time.monotonic() - self.t0:.0f} s")
        return 0

    def tail(self) -> None:
        if self.args.server_log:
            try:
                lines = Path(self.args.server_log).read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError:
                return
            say(f"the server's last lines ({self.args.server_log}):")
            for line in lines[-30:]:
                print(f"  {line}", flush=True)


def port_of(cmd: list[str]) -> int | None:
    for i, a in enumerate(cmd):
        if a == "--port" and i + 1 < len(cmd):
            return int(cmd[i + 1])
        if a.startswith("--port="):
            return int(a.split("=", 1)[1])
    return None


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="ui_guards.py", description=__doc__.split("\n\n")[0])
    p.add_argument("--cmd", required=True, help="the server's command line, with --port N")
    p.add_argument("--clip", required=True, help="the song file to chart (one this cache has not charted)")
    p.add_argument("--server-log", help="the server's output goes here (default: this program's)")
    p.add_argument("--report", help="write what it saw here, as JSON")
    p.add_argument("--timeout", type=float, default=1800.0, help="seconds each job may take (default 1800)")
    p.add_argument("--shared-machine", action="store_true",
                   help="check only the job's own process tree, not every process (other agents' node)")
    args = p.parse_args(argv)
    try:
        port = port_of(shlex.split(args.cmd))
    except ValueError:
        port = None
    if port is None:
        p.error("--cmd needs --port N (where the server listens)")
    if not Path(args.clip).is_file():
        p.error(f"no clip at {args.clip}")
    return Run(args, port).main()


if __name__ == "__main__":
    sys.exit(main())
