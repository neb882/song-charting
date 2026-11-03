"""songcharter.proc: a child started in a process group of its own, and the whole group stopped by Tree.kill, checked
by pid. The children are small Python programs and `sleep`; POSIX only."""
import os
import subprocess
import sys
import time

import pytest

from songcharter import proc

pytestmark = pytest.mark.skipif(os.name != "posix", reason="process groups are POSIX (Job Objects: M4-99)")

# a child that starts a grandchild (sleep 60), prints both pids, and sleeps; with "stubborn" it ignores SIGTERM
CHILD = r'''
import os, signal, subprocess, sys, time
if "stubborn" in sys.argv:
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
grandchild = subprocess.Popen(["sleep", "60"])
print(os.getpid(), grandchild.pid, flush=True)
time.sleep(60)
'''


def started(*args: str) -> tuple[proc.Tree, int, int]:
    tree = proc.start([sys.executable, "-c", CHILD, *args], dict(os.environ), None, subprocess.PIPE, None)
    child, grandchild = map(int, tree.stdout.readline().split())
    return tree, child, grandchild


def test_kill_stops_the_child_and_its_grandchild():
    tree, child, grandchild = started()
    try:
        assert child == tree.pid and os.getpgid(grandchild) == tree.pgid == child != os.getpgid(0)
        assert proc.alive(child) and proc.alive(grandchild)
        t0 = time.monotonic()
        code = tree.kill()
        assert time.monotonic() - t0 < 4   # SIGTERM was enough: no wait for the SIGKILL
        assert code == -15 and tree.killed
        assert not proc.alive(child) and not proc.alive(grandchild)
        assert not proc.group_alive(tree.pgid)
        # idempotent: a second kill returns the same code at once
        t0 = time.monotonic()
        assert tree.kill() == -15 and time.monotonic() - t0 < 0.5
    finally:
        for pid in (child, grandchild):
            try:
                os.kill(pid, 9)
            except ProcessLookupError:
                pass
        tree.popen.stdout.close()


def test_a_child_that_ignores_sigterm_gets_sigkill_after_the_timeout():
    tree, child, grandchild = started("stubborn")
    try:
        t0 = time.monotonic()
        code = tree.kill(timeout=1.0)
        took = time.monotonic() - t0
        assert code == -9 and 0.9 < took < 4, (code, took)
        assert not proc.alive(child) and not proc.alive(grandchild)   # it ignores SIGTERM too (inherited)
    finally:
        tree.popen.stdout.close()


def test_kill_after_the_leader_exited_by_itself_still_stops_what_it_left():
    # the leader exits at once, leaving its grandchild running in the group
    script = "import subprocess; p = subprocess.Popen(['sleep', '60']); print(p.pid, flush=True)"
    tree = proc.start([sys.executable, "-c", script], None, None, subprocess.PIPE, None)
    try:
        orphan = int(tree.stdout.readline())
        assert tree.wait(10) == 0 and proc.alive(orphan) and proc.group_alive(tree.pgid)
        assert tree.kill() == 0 and not tree.killed
        assert not proc.alive(orphan)
    finally:
        tree.popen.stdout.close()


def test_alive_counts_a_zombie_as_gone():
    p = subprocess.Popen([sys.executable, "-c", "pass"])
    deadline = time.monotonic() + 10
    while proc.alive(p.pid) and time.monotonic() < deadline:   # exited, not reaped yet: a zombie
        time.sleep(0.02)
    assert not proc.alive(p.pid)
    assert p.wait() == 0 and not proc.alive(p.pid)
