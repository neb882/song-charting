"""The heavy-job lock (docs/PIPELINE.md, Long runs): tools/heavy.sh and eval/golden.py's run queue on one lock, so the
agents sharing a dev machine never run two heavy jobs at once."""
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(sys.platform == "win32" or shutil.which("flock") is None,
                                reason="the dev machine's lock is Linux's flock")

ROOT = Path(__file__).resolve().parents[1]
HEAVY = ROOT / "tools" / "heavy.sh"


@pytest.fixture
def lock(tmp_path, monkeypatch):
    path = tmp_path / "heavy.lock"
    monkeypatch.setenv("SONGCHARTER_HEAVY_LOCK", str(path))
    monkeypatch.delenv("SONGCHARTER_HEAVY_HELD", raising=False)  # set when the suite itself runs under heavy.sh
    monkeypatch.setenv("SONGCHARTER_HEAVY_MIN_FREE_GB", "0")
    return path


def held(path: Path) -> bool:
    """Whether another open of the lock holds it now."""
    return subprocess.run(["flock", "-n", str(path), "true"]).returncode != 0


def holder(path: Path, seconds: float) -> subprocess.Popen:
    """A process holding the lock for `seconds`, returned once it has it."""
    p = subprocess.Popen(["flock", str(path), "sleep", str(seconds)])
    deadline = time.monotonic() + 10
    while not held(path):
        assert time.monotonic() < deadline and p.poll() is None, "the holder never took the lock"
        time.sleep(0.02)
    return p


def heavy_sh(*cmd: str, timeout: float = 20) -> subprocess.CompletedProcess:
    return subprocess.run([str(HEAVY), *cmd], capture_output=True, text=True, timeout=timeout)


def test_heavy_sh_gives_the_commands_status_and_marks_it_held(lock):
    p = heavy_sh("sh", "-c", 'echo "held=$SONGCHARTER_HEAVY_HELD"; exit 7')
    assert (p.returncode, p.stdout) == (7, "held=1\n")
    assert "sh -c" in Path(f"{lock}.who").read_text()


def test_heavy_sh_holds_the_lock_while_the_command_runs_and_only_then(lock):
    p = heavy_sh("sh", "-c", f'if flock -n "{lock}" true; then echo free; else echo held; fi')
    assert p.stdout == "held\n"
    assert not held(lock)


def test_heavy_sh_waits_for_the_holder_and_names_it(lock):
    Path(f"{lock}.who").write_text("123 2026-11-04T00:00:00Z a golden run\n")
    h = holder(lock, 1.0)
    t0 = time.monotonic()
    p = heavy_sh("true")
    waited = time.monotonic() - t0
    h.wait()
    assert p.returncode == 0 and waited > 0.5
    assert "waiting" in p.stderr and "a golden run" in p.stderr


def test_heavy_sh_inside_heavy_sh_does_not_wait_for_itself(lock):
    assert heavy_sh("sh", "-c", f'"{HEAVY}" true').returncode == 0  # the outer sh keeps holding the lock


def test_heavy_sh_refuses_to_start_short_of_disk(lock, monkeypatch, tmp_path):
    monkeypatch.setenv("SONGCHARTER_HEAVY_MIN_FREE_GB", "1000000")
    p = heavy_sh("touch", str(tmp_path / "ran"))
    assert p.returncode == 2 and "GB free" in p.stderr
    assert not (tmp_path / "ran").exists()


def test_heavy_sh_with_the_lock_off_does_not_wait(lock, monkeypatch):
    h = holder(lock, 30)
    monkeypatch.setenv("SONGCHARTER_HEAVY_LOCK", "off")
    try:
        p = heavy_sh("sh", "-c", 'echo "held=${SONGCHARTER_HEAVY_HELD:-}"', timeout=10)
        assert (p.returncode, p.stdout) == (0, "held=\n")  # no lock taken, so none claimed
    finally:
        h.kill()
        h.wait()


def test_heavy_sh_without_a_command_is_bad_input(lock):
    assert heavy_sh().returncode == 2


def test_golden_waits_for_the_holder_names_it_and_releases(lock, capsys):
    G = pytest.importorskip("eval.golden")
    Path(f"{lock}.who").write_text("1 2026-11-04T00:00:00Z the suite\n")
    h = holder(lock, 1.0)
    t0 = time.monotonic()
    with G.heavy("golden run --out x"):
        waited = time.monotonic() - t0
        assert held(lock)
        assert "golden run --out x" in Path(f"{lock}.who").read_text()
    h.wait()
    assert waited > 0.5 and not held(lock)
    assert "the suite" in capsys.readouterr().err


@pytest.mark.parametrize("var, value", [("SONGCHARTER_HEAVY_HELD", "1"), ("SONGCHARTER_HEAVY_LOCK", "off")])
def test_golden_does_not_wait_under_heavy_sh_or_with_the_lock_off(lock, monkeypatch, var, value):
    G = pytest.importorskip("eval.golden")
    h = holder(lock, 30)
    monkeypatch.setenv(var, value)
    try:
        t0 = time.monotonic()
        with G.heavy("golden run"):
            pass
        assert time.monotonic() - t0 < 5
    finally:
        h.kill()
        h.wait()


def test_a_golden_run_builds_inside_the_lock(lock, tmp_path, monkeypatch):
    G = pytest.importorskip("eval.golden")
    try:
        G.scan_chart_script()
        G.node()
    except G.Refused as e:
        pytest.skip(f"scan-chart is not here ({e})")
    refs = tmp_path / "refs"
    (refs / "song_a").mkdir(parents=True)
    (refs / "song_a" / "input.wav").write_bytes(b"not audio: the build is a stand-in")
    (refs / "songs.json").write_text('[{"id": "song_a"}]')
    seen = []

    def build(songs, ctx, holding=False):
        seen.append(held(lock))
        return {"run": {"seconds": 0.0}}, 0

    monkeypatch.setattr(G, "run", build)
    assert G.main(["run", "--out", str(tmp_path / "out"), "--refs", str(refs), "--work", str(tmp_path / "work")]) == 0
    assert seen == [True] and not held(lock)
