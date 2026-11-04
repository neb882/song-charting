"""The installed songcharter's entry point (M4-03): ~/.local/bin/songcharter runs `python -P -m songcharter.launch`
in the install's own environment (runtime/env); -P keeps a songcharter/ folder in the current one (a checkout) from
being imported instead.

    songcharter                         # the page (`songcharter ui`, M4-04); until M4-04 merges, doctor's summary
    songcharter chart|doctor|... ARGS   # the command line (cli.main), with the install's environment
    songcharter uninstall [--yes]       # what the install made, and then, if asked, the downloads and the caches
    ... --from-shortcut                 # from the Start-menu shortcut: a failure waits for Enter

  * **runtime.json** (songcharter.runtime) says where everything is. Missing, the install has not finished: exit 2.
    The install's own Python finds it beside its environment; $SONGCHARTER_HOME names another install.
  * **The environment** (`environment`): where songcharter finds Node, scan-chart, autochart, allin1's Python, ffmpeg
    and the models, Node's folder first on PATH (assemble finds scan-chart's node there), and, once the install's
    models are in, the hub offline (HF_HUB_OFFLINE=1), so a launch with no network works. SONGCHARTER_OFFLINE is
    left unset: the lyrics aligner's weights, which the install does not fetch, download on the first song with
    lyrics (engines/lyrics.weights_path), and ADTOF's would come again if deleted. Each of songcharter's own
    downloads is pinned and hash-checked and made only when its file is missing: a file already there never goes back
    to the network. A variable the person set wins (SONGCHARTER_OFFLINE=1 forbids those downloads), but for PATH.
  * **--from-shortcut.** The shortcut's window closes when the command ends, so on any non-zero exit the error stays
    on the screen with "Press Enter to close this window" (a launch failure must never just close the window).
  * **uninstall** removes the shortcut, the launcher, the app and runtime/state, then asks once whether the
    downloads and the song caches and library go too (No keeps runtime/, which holds uv's cache, runtime/uv-cache,
    and the models, so a reinstall downloads only install.sh and the app, about 1 MB; none of it with install.sh's
    --from). It counts and deletes only songcharter's own folders: never the person's ~/.cache/uv, which other uv
    projects share. It offers to restore the .wslconfig songcharter backed up, and never deletes .wslconfig. `--yes`
    answers yes to both questions.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import traceback
from pathlib import Path
from typing import Callable, Mapping

DEFAULT_HOME = Path("~/.local/share/songcharter")
LAUNCHER = Path("~/.local/bin/songcharter")
LAUNCHER_MARK = "songcharter.launch"   # in our launcher: uninstall deletes only a launcher that has it
FROM_SHORTCUT = "--from-shortcut"
GB = 10 ** 9


def home_dir() -> Path:
    """$SONGCHARTER_HOME, else the install this Python belongs to (runtime/env's home), else
    ~/.local/share/songcharter."""
    if os.environ.get("SONGCHARTER_HOME"):
        return Path(os.environ["SONGCHARTER_HOME"]).expanduser()
    own = Path(sys.prefix).parent.parent
    if (own / "runtime" / "runtime.json").is_file():
        return own
    return DEFAULT_HOME.expanduser()


def load_runtime(home: Path) -> dict | None:
    try:
        return json.loads((home / "runtime" / "runtime.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def environment(runtime: Mapping, base: Mapping[str, str] | None = None) -> dict[str, str]:
    """`base` (os.environ) with what the install's runtime.json says: SONGCHARTER_HOME, SONGCHARTER_NODE,
    SONGCHARTER_AUTOCHART, SONGCHARTER_ALLIN1_PYTHON (only when it is not null: the memory rule),
    SONGCHARTER_SCAN_CHART, FFMPEG, HF_HOME, HF_HUB_DISABLE_SYMLINKS_WARNING=1, PYTHONUTF8=1, PYTHONSAFEPATH=1 (a
    child Python, such as the UI's chart job, imports songcharter from the install, never from a songcharter/ folder
    in the current one), MPLCONFIGDIR in songcharter's cache (the preview's matplotlib keeps its font cache there, not
    in ~/.cache/matplotlib and ~/.config/matplotlib, which uninstall would leave), and, when models_complete,
    HF_HUB_OFFLINE=1 (never SONGCHARTER_OFFLINE: the module docstring); each only where `base` has no value of its
    own. PATH gets Node's folder first."""
    from .cache import user_cache
    env = dict(os.environ if base is None else base)
    values = {"SONGCHARTER_HOME": runtime.get("home"), "SONGCHARTER_NODE": runtime.get("node"),
              "SONGCHARTER_AUTOCHART": runtime.get("autochart"),
              "SONGCHARTER_ALLIN1_PYTHON": runtime.get("allin1_python"),
              "SONGCHARTER_SCAN_CHART": runtime.get("scan_chart"), "FFMPEG": runtime.get("ffmpeg"),
              "HF_HOME": runtime.get("hf_home"), "HF_HUB_DISABLE_SYMLINKS_WARNING": "1", "PYTHONUTF8": "1",
              "PYTHONSAFEPATH": "1", "MPLCONFIGDIR": user_cache() / "matplotlib"}
    if runtime.get("models_complete"):
        values["HF_HUB_OFFLINE"] = "1"
    for key, value in values.items():
        if value is not None:
            env.setdefault(key, str(value))
    if runtime.get("node"):
        node_dir = str(Path(runtime["node"]).parent)
        rest = [p for p in env.get("PATH", "").split(os.pathsep) if p and p != node_dir]
        env["PATH"] = os.pathsep.join([node_dir, *rest])
    return env


def _ask(question: str, default: bool) -> bool:
    """A yes/no question on the terminal; Enter, or no input at all, gives the default."""
    try:
        answer = input(f"{question} ").strip().lower()
    except EOFError:
        print()
        return default
    return default if not answer else answer in ("y", "yes")


def _cli(argv: list[str]) -> int:
    """cli.main's exit status, argparse's exits included."""
    from . import cli
    try:
        return cli.main(argv)
    except SystemExit as e:   # argparse: --help, --version, a bad option (its message is printed)
        return e.code if isinstance(e.code, int) else 0 if e.code is None else 1


def _run(argv: list[str]) -> int:
    if argv[:1] == ["uninstall"]:
        return uninstall(argv[1:])
    home = home_dir()
    runtime = load_runtime(home)
    if runtime is None:
        print("songcharter is not installed: run the install line again", file=sys.stderr)
        return 2
    os.environ.update(environment(runtime))
    if not argv:   # the page (M4-04)
        argv = ["ui"]
    return _cli(argv)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    try:
        code = _run(argv)
    except KeyboardInterrupt:
        print("songcharter: interrupted", file=sys.stderr)
        code = 130
    except Exception:  # noqa: BLE001  a bug in the launch itself
        traceback.print_exc()
        print("songcharter: internal error (a bug, please report it with the traceback above)", file=sys.stderr)
        code = 3
    if code and FROM_SHORTCUT in argv:
        print(f"\nsongcharter stopped (exit status {code}); the error is above.")
        _ask("Press Enter to close this window", True)
    return code


# ------------------------------------------------------------------------------------------------ uninstall

def du(paths: list[Path]) -> int:
    """`du -scb` of the paths that exist (a file hardlinked between them counts once), in bytes; 0 for none."""
    there = [str(p) for p in paths if p.exists()]
    if not there:
        return 0
    try:
        out = subprocess.run(["du", "-scb", "--", *there], capture_output=True, text=True, timeout=300).stdout
        return int(out.strip().splitlines()[-1].split()[0])
    except (OSError, subprocess.SubprocessError, ValueError, IndexError):
        return 0


def _remove(path: Path, say: Callable[[str], None]) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path)
    else:
        return
    say(f"removed {path}")


def _ours(launcher: Path) -> bool:
    try:
        return LAUNCHER_MARK in launcher.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False


def uninstall(args: list[str], *, ask: Callable[[str, bool], bool] = _ask,
              say: Callable[[str], None] = print) -> int:
    """`songcharter uninstall [--yes]` (module docstring); 0, or 2 for bad usage."""
    unknown = [a for a in args if a not in ("--yes", FROM_SHORTCUT)]
    if unknown:
        print(f"usage: songcharter uninstall [--yes] (not {' '.join(unknown)})", file=sys.stderr)
        return 2
    yes = "--yes" in args
    from . import wsl, wslsetup
    from .cache import user_cache
    home, launcher = home_dir(), LAUNCHER.expanduser()
    # the Windows side first, while the install's Python (in runtime/, which may go) still has every module it needs
    windows = wslsetup.windows_side() if wsl.is_wsl() else None
    if windows and windows.get("shortcut") is not None:
        _remove(windows["shortcut"], say)
    if _ours(launcher):
        _remove(launcher, say)
    for path in (home / "app", home / "runtime" / "state"):
        _remove(path, say)

    runtime, models, cache = home / "runtime", user_cache() / "models", user_cache()
    downloads = du([runtime, models])   # runtime/ holds uv's cache too (install.sh's runtime/uv-cache)
    songs = du([*(p for p in (cache.iterdir() if cache.is_dir() else []) if p != models),
                home / "library", home / "uploads", home / "exports"])
    question = (f"Also delete the downloads (Python packages, Node, autochart and its models: about "
                f"{downloads / GB:.1f} GB) and your song caches and library ({songs / GB:.1f} GB)? A reinstall reuses "
                "the downloads if you keep them. [y/N]")
    if yes or ask(question, False):
        for path in (home, cache):
            _remove(path, say)
    else:
        say(f"kept {runtime} and {models}: a reinstall reuses them, and downloads only install.sh and the app "
            "(about 1 MB)")

    backups = (windows or {}).get("backups") or []
    if backups:
        newest = backups[0]
        if yes or ask(f"Restore {windows['wslconfig']} from {newest.name}, the copy songcharter kept from before "
                      "it changed WSL's memory? [y/N]", False):
            shutil.copyfile(newest, windows["wslconfig"])
            say(f"restored {windows['wslconfig']} from {newest.name}: it applies after wsl --shutdown")
    elif windows and windows.get("wslconfig") is not None and windows["wslconfig"].is_file():
        say(f"{windows['wslconfig']} is left as it is (songcharter wrote it; edit it to change WSL's memory)")
    distro = wsl.distro() or "Ubuntu"
    say("songcharter is uninstalled. WSL's disk does not shrink by itself: the space stays inside WSL's virtual disk "
        "on C:.")
    say(f"To remove everything, if this Ubuntu holds nothing else: wsl --unregister {distro} (in Windows' Terminal). "
        "It deletes everything in it, not only songcharter.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
