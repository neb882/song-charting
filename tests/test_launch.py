"""The installed entry point (songcharter.launch): the environment it gives the command line, an install that has not
finished, --from-shortcut waiting for Enter after a failure (in a real child process, stdin from a pipe), and
uninstall's two answers in a temporary home."""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from songcharter import cli, launch, wsl, wslsetup

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = {"home": "/h", "node": "/h/runtime/node/bin/node", "autochart": "/h/runtime/autochart",
           "allin1_python": "/h/runtime/allin1/bin/python", "scan_chart": "/h/runtime/scan-chart/scan.cjs",
           "ffmpeg": "/h/runtime/env/ffmpeg", "hf_home": "/c/songcharter/models/hf", "models_complete": True}


def test_environment_fills_in_what_the_person_has_not_set():
    base = {"PATH": "/usr/bin:/h/runtime/node/bin:/bin", "SONGCHARTER_NODE": "/my/node", "HF_HOME": "/my/hf"}
    env = launch.environment(RUNTIME, base)
    assert env["SONGCHARTER_NODE"] == "/my/node" and env["HF_HOME"] == "/my/hf"   # the person's win
    assert env["PATH"] == "/h/runtime/node/bin:/usr/bin:/bin"                     # but for PATH: Node first, once
    assert {k: env[k] for k in ("SONGCHARTER_HOME", "SONGCHARTER_AUTOCHART", "SONGCHARTER_ALLIN1_PYTHON",
                                "SONGCHARTER_SCAN_CHART", "FFMPEG", "HF_HUB_DISABLE_SYMLINKS_WARNING",
                                "PYTHONUTF8", "HF_HUB_OFFLINE", "SONGCHARTER_OFFLINE")} == {
        "SONGCHARTER_HOME": "/h", "SONGCHARTER_AUTOCHART": "/h/runtime/autochart",
        "SONGCHARTER_ALLIN1_PYTHON": "/h/runtime/allin1/bin/python", "SONGCHARTER_SCAN_CHART":
        "/h/runtime/scan-chart/scan.cjs", "FFMPEG": "/h/runtime/env/ffmpeg", "HF_HUB_DISABLE_SYMLINKS_WARNING": "1",
        "PYTHONUTF8": "1", "HF_HUB_OFFLINE": "1", "SONGCHARTER_OFFLINE": "1"}
    assert env["PYTHONSAFEPATH"] == "1"
    assert base == {"PATH": "/usr/bin:/h/runtime/node/bin:/bin", "SONGCHARTER_NODE": "/my/node", "HF_HOME": "/my/hf"}
    env = launch.environment({**RUNTIME, "allin1_python": None, "models_complete": False}, {"PATH": "/bin"})
    assert "SONGCHARTER_ALLIN1_PYTHON" not in env   # the memory rule left allin1 out: the librosa fallback
    assert "HF_HUB_OFFLINE" not in env and "SONGCHARTER_OFFLINE" not in env
    assert launch.environment(RUNTIME, {"SONGCHARTER_OFFLINE": "0"})["SONGCHARTER_OFFLINE"] == "0"


@pytest.fixture
def home(tmp_path, monkeypatch):
    """A songcharter home with a runtime.json, as $SONGCHARTER_HOME. os.environ comes back as it was afterwards:
    launch.main sets the install's variables in this process."""
    saved = dict(os.environ)
    h = tmp_path / "home"
    (h / "runtime").mkdir(parents=True)
    (h / "runtime" / "runtime.json").write_text(json.dumps({**RUNTIME, "home": str(h)}), encoding="utf-8")
    monkeypatch.setenv("SONGCHARTER_HOME", str(h))
    yield h
    os.environ.clear()
    os.environ.update(saved)


def test_main_runs_the_command_line_with_the_installs_environment(home, monkeypatch, capsys):
    calls = []
    monkeypatch.setattr(cli, "main", lambda argv: calls.append((argv, os.environ.get("SONGCHARTER_HOME"))) or 0)
    monkeypatch.delenv("PYTHONUTF8", raising=False)
    assert launch.main(["chart", "x.mp3", "--out", "o"]) == 0
    assert calls == [(["chart", "x.mp3", "--out", "o"], str(home))] and os.environ["PYTHONUTF8"] == "1"
    assert launch.main([]) == 0 and calls[-1][0] == ["ui"]   # no arguments: the page
    (home / "runtime" / "runtime.json").unlink()
    assert launch.main(["doctor"]) == 2
    assert capsys.readouterr().err == "songcharter is not installed: run the install line again\n"


def child(home: Path, *args: str) -> subprocess.Popen:
    env = {**os.environ, "SONGCHARTER_HOME": str(home), "PYTHONPATH": str(ROOT), "PYTHONUNBUFFERED": "1"}
    return subprocess.Popen([sys.executable, "-m", "songcharter.launch", *args], stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env, cwd=str(ROOT))


def test_from_the_shortcut_a_failure_waits_for_enter(home):
    """The shortcut's window closes when the command ends: after a non-zero exit (here argparse's, for a command
    that does not exist) the launch waits for Enter on stdin; after exit 0 it does not wait."""
    p = child(home, "no-such-command", "--from-shortcut")
    time.sleep(2.0)
    assert p.poll() is None   # still waiting
    out, err = p.communicate("\n", timeout=60)
    assert p.returncode == 2
    assert "invalid choice: 'no-such-command'" in err
    assert out.endswith("songcharter stopped (exit status 2); the error is above.\nPress Enter to close this window ")
    p = child(home, "--version", "--from-shortcut")
    out, err = p.communicate(timeout=60)   # stdin closed at once: no wait
    assert p.returncode == 0 and "Press Enter" not in out
    (home / "runtime" / "runtime.json").unlink()
    p = child(home, "ui", "--from-shortcut")
    time.sleep(1.0)
    assert p.poll() is None
    out, err = p.communicate("\n", timeout=60)
    assert p.returncode == 2 and "songcharter is not installed" in err and "Press Enter" in out


# ------------------------------------------------------------------------------------------------ uninstall

@pytest.fixture
def installed(tmp_path, monkeypatch):
    """An install in a temporary $HOME with every folder uninstall knows, on plain Linux (no WSL)."""
    user = tmp_path / "user"
    for var in ("SONGCHARTER_HOME", "XDG_CACHE_HOME", "UV_CACHE_DIR", "WSL_DISTRO_NAME"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("HOME", str(user))
    monkeypatch.setattr(wsl, "OSRELEASE", tmp_path / "no-osrelease")
    home = user / ".local" / "share" / "songcharter"
    files = {home / "app" / "0.1.0" / "pyproject.toml": 10, home / "runtime" / "state" / "install.done": 10,
             home / "runtime" / "runtime.json": 10, home / "runtime" / "env" / "lib" / "torch.so": 3000,
             home / "runtime" / "autochart" / "models" / "m.onnx": 4000, home / "bin" / "uv": 500,
             home / "library" / "a" / "notes.chart": 600, home / "uploads" / "u" / "song.mp3": 700,
             home / "exports" / "x.zip": 100, home / "logs" / "ui.log": 10, home / "doctor.json": 10,
             user / ".cache" / "uv" / "archive-v0" / "w": 5000,
             user / ".cache" / "songcharter" / "models" / "hf" / "f": 800,
             user / ".cache" / "songcharter" / "work" / "song-1" / "stems.npy": 9000,
             user / ".local" / "bin" / "songcharter": 0}
    for path, size in files.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"x" * size)
    (user / ".local" / "bin" / "songcharter").write_text(
        f'#!/bin/sh\nexec "{home}/runtime/env/bin/python" -m songcharter.launch "$@"\n', encoding="utf-8")
    return user, home


def run_uninstall(args, answers):
    said, asked = [], []
    answers = list(answers)

    def ask(question, default):
        asked.append((question, default))
        return answers.pop(0)

    assert launch.uninstall(args, ask=ask, say=said.append) == 0
    return said, asked


def test_uninstall_no_keeps_the_downloads(installed):
    user, home = installed
    said, asked = run_uninstall([], [False])
    assert not (home / "app").exists() and not (home / "runtime" / "state").exists()
    assert not (user / ".local" / "bin" / "songcharter").exists()
    cache = user / ".cache"
    for kept in (home / "runtime" / "runtime.json", home / "runtime" / "env" / "lib" / "torch.so", home / "bin" / "uv",
                 cache / "uv" / "archive-v0" / "w", cache / "songcharter" / "models" / "hf" / "f",
                 cache / "songcharter" / "work" / "song-1" / "stems.npy", home / "library" / "a" / "notes.chart"):
        assert kept.is_file(), kept
    [(question, default)] = asked
    assert default is False and question.startswith(
        "Also delete the downloads (Python packages, Node, autochart and its models: about 0.0 GB) and your song "
        "caches and library (0.0 GB)?")
    assert "[y/N]" in question and any("a reinstall downloads nothing" in s for s in said)
    assert said[-1].startswith("To remove everything, if this Ubuntu holds nothing else: wsl --unregister Ubuntu")


def test_uninstall_yes_deletes_everything_and_sizes_the_question(installed, monkeypatch):
    user, home = installed
    sizes = []
    monkeypatch.setattr(launch, "du", lambda paths: sizes.append(sorted(p.name for p in paths)) or 2_500_000_000)
    said, asked = run_uninstall([], [True])
    assert sizes == [["models", "runtime", "uv"], ["exports", "library", "uploads", "work"]]
    assert "about 2.5 GB) and your song caches and library (2.5 GB)?" in asked[0][0]
    cache = user / ".cache"
    for gone in (home, cache / "songcharter", cache / "uv", user / ".local" / "bin" / "songcharter"):
        assert not gone.exists(), gone
    assert (user / ".local" / "bin").is_dir()   # only our launcher goes


def test_du_counts_a_hardlinked_file_once(tmp_path):
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    (tmp_path / "a" / "f").write_bytes(b"x" * 100_000)
    os.link(tmp_path / "a" / "f", tmp_path / "b" / "f")
    assert 100_000 <= launch.du([tmp_path / "a", tmp_path / "b", tmp_path / "nothing"]) < 120_000
    assert launch.du([tmp_path / "nothing"]) == 0


def test_uninstall_keeps_a_launcher_that_is_not_ours_and_yes_answers_both(installed, tmp_path, monkeypatch):
    """--yes answers both questions; on WSL the shortcut goes and the newest backup of .wslconfig comes back (the
    Windows side read before anything is deleted)."""
    user, home = installed
    (user / ".local" / "bin" / "songcharter").write_text("#!/bin/sh\necho someone else's\n", encoding="utf-8")
    profile = tmp_path / "c" / "Users" / "J"
    profile.mkdir(parents=True)
    (profile / ".wslconfig").write_text("[wsl2]\nmemory=12GB\n", encoding="utf-8")
    (profile / ".wslconfig.songcharter-20261101-090000").write_text("[wsl2]\nmemory=4GB\n", encoding="utf-8")
    (profile / ".wslconfig.songcharter-20261102-090000").write_text("[wsl2]\nmemory=6GB\n", encoding="utf-8")
    (profile / "songcharter.lnk").write_bytes(b"L")
    monkeypatch.setenv("WSL_DISTRO_NAME", "Ubuntu-26.04")
    monkeypatch.setattr(wslsetup, "windows_side", lambda: {
        "wslconfig": profile / ".wslconfig", "shortcut": profile / "songcharter.lnk",
        "backups": [profile / ".wslconfig.songcharter-20261102-090000",
                    profile / ".wslconfig.songcharter-20261101-090000"]})
    said, asked = run_uninstall(["--yes"], [])
    assert asked == [] and not home.exists() and not (profile / "songcharter.lnk").exists()
    assert (user / ".local" / "bin" / "songcharter").read_text(encoding="utf-8").endswith("someone else's\n")
    assert (profile / ".wslconfig").read_text(encoding="utf-8") == "[wsl2]\nmemory=6GB\n"
    assert said[-1].startswith("To remove everything, if this Ubuntu holds nothing else: wsl --unregister Ubuntu-26.04")
    assert launch.uninstall(["--all"]) == 2


def test_matplotlib_keeps_its_caches_in_songcharters(monkeypatch, tmp_path):
    """The preview's matplotlib writes ~/.cache/matplotlib and ~/.config/matplotlib unless MPLCONFIGDIR says
    otherwise, and uninstall removes neither (M4-05's CI): the launcher points it into songcharter's cache, which
    uninstall's "delete everything" removes; a value of the user's own is kept."""
    from songcharter.cache import user_cache
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "xdg"))
    assert launch.environment({}, {})["MPLCONFIGDIR"] == str(user_cache() / "matplotlib")
    assert user_cache() == tmp_path / "xdg" / "songcharter"
    assert launch.environment({}, {"MPLCONFIGDIR": "/mine"})["MPLCONFIGDIR"] == "/mine"
