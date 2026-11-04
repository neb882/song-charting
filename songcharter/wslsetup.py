"""The Windows side of the install, from WSL (M4-03): WSL's memory in %UserProfile%\\.wslconfig, and the Start-menu
shortcut. install.sh runs it after the downloads, once Python can read Windows' RAM.

    python -m songcharter.wslsetup apply [--yes] [--windows-ram-gb N] [--home H] [--launcher PATH]
                                         [--restart-flag FILE]

  * **The memory rule** (`plan`): the target is Windows' RAM, rounded to the nearest whole GB (a "16 GB" PC reports
    about 15.9 GiB), less 4 GB for Windows: memory=12GB on 16 GB.
      - no .wslconfig, or no memory in its [wsl2]: memory=<target>GB and swap=8GB are written there;
      - memory at 12 GB or more: kept;
      - memory under 12 GB: "Raise it to <target> GB? [Y/n]" (yes with --yes), and only memory is changed;
      - Windows' RAM unknown: nothing is written, and the person is told how to set it by hand;
      - a target under 8 GB (a PC under 12 GB), or WSL's memory left under 8 GB, is refused (exit 2);
      - WSL's resulting memory under 11 GB (10^9 bytes): runtime.json's allin1_python is set to null, so the
        sections use the librosa fallback, which holds no 7.8 GB model run. With the rounding, that is a PC whose
        RAM rounds to 14 GB or less (memory=10GB, 10.7 * 10^9 bytes): one that rounds to 15 GB gets memory=11GB,
        11.8 * 10^9 bytes, and keeps allin1.
    Sizes in .wslconfig are binary (12GB is 12 GiB, as WSL reads them); the 8 and 11 GB limits are device.py's, in
    10^9 bytes. `--windows-ram-gb N` ($SONGCHARTER_WINDOWS_RAM_GB) replaces the measured RAM (M4-08 writes a 16 GB
    PC's file on a larger PC; the tests).
  * **Writing .wslconfig** goes only through wsl.update_wslconfig (every other line and section kept; a new file in
    CRLF, Windows' convention), as UTF-8, through a temporary file. An existing file is first copied to
    .wslconfig.songcharter-<yyyyMMdd-HHmmss>. The change applies once WSL restarts: `--restart-flag` names a file
    written when .wslconfig changed, and install.sh then runs `wsl.exe --shutdown`.
  * **The shortcut** is <Programs>\\songcharter.lnk (the user's own Start-menu folder: no admin), which runs
    `%windir%\\System32\\cmd.exe /c "wsl.exe -d <distro> --cd ~ -e <launcher> ui --from-shortcut || pause"` in
    %USERPROFILE%, with wsl.exe's icon (winshortcut.py says why a .lnk). `|| pause` keeps the window open when wsl.exe
    itself fails before the launcher can. A reinstall overwrites it. With no interop, or a write that fails, the
    fallback is said: open Ubuntu from the Start menu and type songcharter.
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import sys
import time
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from . import wsl
from .device import ALLIN1_MEMORY, MIN_WSL_MEMORY

GIB = 2 ** 30
WINDOWS_KEEPS_GB = 4      # Windows' RAM less this is WSL's target
ENOUGH_GB = 12            # a .wslconfig memory at or above this is kept
SWAP = "8GB"
BACKUP_PREFIX = ".wslconfig.songcharter-"
BACKUP = re.compile(r"^\.wslconfig\.songcharter-\d{8}-\d{6}$")   # a backup's name, and nothing else
SHORTCUT = "songcharter.lnk"
TARGET = r"%windir%\System32\cmd.exe"
SAFE = re.compile(r"^[A-Za-z0-9._/~+-]+$")   # a distro name or a launcher path the shortcut can carry unquoted
FALLBACK = "open Ubuntu from the Start menu and type songcharter"
REFUSE_PC = "songcharter needs a PC with at least 12 GB of RAM"


class Refused(Exception):
    """The memory rule refuses: the message says why."""


@dataclass(frozen=True)
class Plan:
    action: str               # "write", "keep", "ask", "unknown" or "refuse"
    current: int | None       # .wslconfig's memory in bytes
    ram: int | None           # Windows' RAM in bytes
    target_gb: int | None     # memory=<target_gb>GB


def target_gb(ram_bytes: int) -> int:
    """Windows' RAM rounded to the nearest whole GB, less 4."""
    return round(ram_bytes / GIB) - WINDOWS_KEEPS_GB


def memory_bytes(text: str | None) -> int | None:
    """[wsl2]'s memory in a .wslconfig's text, in bytes, else None: from its lines, found as wsl.update_wslconfig
    finds the line it rewrites (a section header, then `key=value` outside a comment, any case), the value read as
    wsl.parse_wslconfig reads it, the last such line winning. Not configparser's reading alone: it rejects a whole
    file over one bare key such as `nestedVirtualization` (WSL's git-config style parser takes it as true), and that
    file's memory=16GB would read as none set, and be rewritten."""
    section, found = None, None
    for line in (text or "").splitlines():
        s = line.lstrip("\ufeff").strip()
        header = re.match(r"\[([^\]]*)\]", s)
        if header:
            section = header.group(1).strip().lower()
        elif section == "wsl2" and "=" in s and s[0] not in "#;":
            key, value = s.split("=", 1)
            if key.strip().lower() == "memory":
                found = value
    return wsl.parse_size(wsl._value(found)) if found is not None else None


def plan(text: str | None, ram_bytes: int | None) -> Plan:
    """The memory rule for a .wslconfig's text (None: no file) and Windows' RAM (None: unknown)."""
    current = memory_bytes(text)
    if current is not None and current >= ENOUGH_GB * GIB:
        return Plan("keep", current, ram_bytes, None)
    if ram_bytes is None:
        return Plan("unknown", current, None, None)
    target = target_gb(ram_bytes)
    if target * GIB < MIN_WSL_MEMORY:
        return Plan("refuse", current, ram_bytes, target)
    if current is None:
        return Plan("write", None, ram_bytes, target)
    return Plan("ask" if target * GIB > current else "keep", current, ram_bytes, target)


def _gb(n: int | None) -> str:
    return "?" if n is None else f"{n / GIB:.0f}" if n % GIB == 0 else f"{n / GIB:.1f}"


def ram_override(value: str | None) -> int | None:
    """--windows-ram-gb / $SONGCHARTER_WINDOWS_RAM_GB in bytes (N GB of RAM, a positive number), None when unset."""
    if value is None or not str(value).strip():
        return None
    try:
        gb = float(value)
    except ValueError:
        gb = 0.0
    if not gb > 0:
        raise Refused(f"--windows-ram-gb is Windows' RAM in GB, a positive number, not {value!r}")
    return int(gb * GIB)


def windows_side() -> dict:
    """What the install and uninstall need from Windows, through interop: {"interop", "wslconfig" (the Linux path of
    %UserProfile%\\.wslconfig, or None), "wslconfig_windows" (its Windows path), "backups" (songcharter's copies,
    newest first), "programs" (the Start-menu programs folder), "shortcut" (songcharter.lnk there, when it exists),
    "profile" (%USERPROFILE%), "windir"}."""
    out: dict = {"interop": wsl.interop_ok(), "wslconfig": None, "wslconfig_windows": None, "backups": [],
                 "programs": None, "shortcut": None, "profile": None, "windir": None}
    if not out["interop"]:
        return out
    profile = wsl.windows_env("USERPROFILE")
    folder = wsl.to_linux(profile) if profile else None
    out["profile"], out["windir"] = profile, wsl.windows_env("windir")
    if folder is not None and folder.is_dir():
        out["wslconfig"] = folder / ".wslconfig"
        out["wslconfig_windows"] = profile.rstrip("\\") + "\\.wslconfig"
        out["backups"] = sorted((p for p in folder.glob(BACKUP_PREFIX + "*") if BACKUP.match(p.name)),
                               key=lambda p: p.name, reverse=True)
    programs = wsl.shell_folder("Programs")
    out["programs"] = programs
    if programs is not None and (programs / SHORTCUT).is_file():
        out["shortcut"] = programs / SHORTCUT
    return out


def shortcut_arguments(distro: str, launcher: Path) -> str:
    return f'/c "wsl.exe -d {distro} --cd ~ -e {launcher} ui --from-shortcut || pause"'


def write_shortcut(win: dict, launcher: Path, say: Callable[[str], None]) -> Path | None:
    """songcharter.lnk in the Start menu's programs folder, or None with the fallback said."""
    from . import winshortcut
    distro, programs = wsl.distro(), win.get("programs")
    why = ("Windows interop is off" if not win.get("interop") else
           "the Start menu's programs folder was not found" if programs is None else
           "this WSL distro has no name ($WSL_DISTRO_NAME)" if not distro else
           f"the distro name {distro!r} or the launcher {launcher} has characters the shortcut cannot carry"
           if not (SAFE.match(distro) and SAFE.match(str(launcher))) else None)
    if why is None:
        windir = (win.get("windir") or "C:\\Windows").rstrip("\\")
        try:
            path = winshortcut.write(programs / SHORTCUT, TARGET, shortcut_arguments(distro, launcher),
                                     win.get("profile") or "%USERPROFILE%", windir + "\\System32\\wsl.exe")
            say(f"Start menu: songcharter ({path})")
            return path
        except (OSError, ValueError) as e:
            why = f"it could not be written ({type(e).__name__}: {e})"
    say(f"no Start-menu shortcut: {why}. To start songcharter, {FALLBACK}.")
    return None


def _meminfo_bytes() -> int | None:
    try:
        for line in wsl.MEMINFO.read_text(encoding="ascii", errors="replace").splitlines():
            if line.startswith("MemTotal:"):
                return int(line.split()[1]) * 1024
    except (OSError, ValueError, IndexError):
        pass
    return None


def apply(home: Path, launcher: Path, yes: bool = False, ram: int | None = None, *,
          ask: Callable[[str], bool] | None = None, say: Callable[[str], None] = print) -> dict:
    """The memory rule and the shortcut (module docstring). `ram` (bytes) replaces Windows' measured RAM. Returns
    {"changed" (.wslconfig was written), "memory_bytes" (WSL's memory once it restarts, None when unknown),
    "allin1" (kept), "shortcut"}; raises Refused."""
    from .runtime import set_allin1
    out = {"changed": False, "memory_bytes": None, "allin1": True, "shortcut": None}
    if not wsl.is_wsl():
        say("not WSL: nothing to do on the Windows side")
        return out
    win = windows_side()
    path, shown = win["wslconfig"], win["wslconfig_windows"] or "%UserProfile%\\.wslconfig"
    try:
        data = path.read_bytes() if path is not None and path.is_file() else None
    except OSError:
        data = None
    text = wsl._decode(data) if data is not None else None
    if ram is None and path is not None:
        ram = wsl.windows_ram_bytes({"path": shown, "memory_bytes": memory_bytes(text)})
    p = plan(text, ram)
    if path is None:   # no interop, or no profile folder: nothing can be read or written
        p = Plan("unknown", None, None, None)
    by_hand = (f"set it by hand: in {shown}, under [wsl2], memory=<Windows' RAM less 4>GB (12GB on a 16 GB PC) and "
               f"swap={SWAP}, then run wsl --shutdown in Windows' Terminal")
    resulting = p.current
    if p.action == "refuse":
        raise Refused(f"{REFUSE_PC} (this one has {round(p.ram / GIB)} GB)")
    if p.action == "keep":
        say(f".wslconfig: memory={_gb(p.current)}GB kept" + (" (12 GB or more is enough)" if p.target_gb is None else
                                                            f" (a {round(p.ram / GIB)} GB PC gives no more)"))
    elif p.action == "unknown":
        why = "Windows interop is off" if not win["interop"] else "Windows' RAM could not be read"
        say(f".wslconfig: not changed ({why}). songcharter needs about 12 GB for WSL: {by_hand}.")
        resulting = p.current if p.current is not None else _meminfo_bytes()
    else:
        values = {"memory": f"{p.target_gb}GB", "swap": SWAP} if p.action == "write" else {"memory": f"{p.target_gb}GB"}
        question = (f"WSL may use {_gb(p.current)} GB; songcharter needs about 12. Raise it to {p.target_gb} GB? "
                    "[Y/n]")
        if p.action == "ask" and not yes and not (ask or _ask)(question):
            say(f".wslconfig: memory={_gb(p.current)}GB kept, as you answered")
            if p.current < MIN_WSL_MEMORY:
                raise Refused(f"WSL may use only {_gb(p.current)} GB, under 8: songcharter cannot run in that. Run the "
                              f"install again and let it raise the memory, or {by_hand}")
        else:
            backup = None
            if data is not None:
                backup = path.with_name(BACKUP_PREFIX + time.strftime("%Y%m%d-%H%M%S"))
                shutil.copyfile(path, backup)
            new = wsl.update_wslconfig(text or "", values)
            part = path.with_name(".wslconfig.tmp-songcharter")
            part.write_bytes(new.encode("utf-8"))
            os.replace(part, path)
            out["changed"], resulting = True, p.target_gb * GIB
            said = " and ".join(f"{k}={v}" for k, v in values.items())
            say(f".wslconfig: wrote {said} in {shown} (Windows has {round(p.ram / GIB)} GB of RAM)"
                + (f"; the old file is kept as {backup.name}" if backup else ""))
    out["memory_bytes"] = resulting
    out["allin1"] = resulting is None or resulting >= ALLIN1_MEMORY
    if set_allin1(home, out["allin1"]) or not out["allin1"]:
        if not out["allin1"]:
            say(f"WSL will have {_gb(resulting)} GB of memory, under 11 GB: allin1 (the sections model, about 8 GB at "
                "its peak) is left out, so the sections use the librosa fallback")
        else:
            say("allin1 is back in: WSL will have enough memory for it")
    out["shortcut"] = write_shortcut(win, launcher, say)
    return out


def _ask(question: str) -> bool:
    """A [Y/n] question: Enter, or no input at all, is yes."""
    try:
        answer = input(f"{question} ").strip().lower()
    except EOFError:
        print()
        return True
    return answer in ("", "y", "yes")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m songcharter.wslsetup",
                                     description="WSL's memory in .wslconfig, and the Start-menu shortcut.")
    sub = parser.add_subparsers(dest="command", required=True)
    a = sub.add_parser("apply")
    a.add_argument("--yes", action="store_true", help="raise WSL's memory without asking")
    a.add_argument("--windows-ram-gb", default=os.environ.get("SONGCHARTER_WINDOWS_RAM_GB"),
                   help="Windows' RAM in GB, instead of the measured value")
    a.add_argument("--home", type=Path, default=Path(os.environ.get("SONGCHARTER_HOME") or
                                                     "~/.local/share/songcharter"))
    a.add_argument("--launcher", type=Path, default=Path("~/.local/bin/songcharter"))
    a.add_argument("--restart-flag", type=Path, help="a file to write when .wslconfig changed")
    args = parser.parse_args(argv)
    from .runtime import say_failed
    try:
        result = apply(args.home.expanduser(), args.launcher.expanduser(), args.yes,
                       ram_override(args.windows_ram_gb))
    except Refused as e:
        say_failed(f"songcharter: memory failed: {e}. Run the same command again to continue.")
        return 2
    except KeyboardInterrupt:
        say_failed("songcharter: memory failed: interrupted. Run the same command again to continue.")
        return 2
    except Exception:  # noqa: BLE001  a bug
        traceback.print_exc()
        say_failed("songcharter: the Windows side failed: an internal error (a bug: please report it with the "
                   "traceback above). Run the same command again to continue.")
        return 3
    if result["changed"] and args.restart_flag is not None:
        args.restart_flag.parent.mkdir(parents=True, exist_ok=True)
        args.restart_flag.write_text("wslconfig changed\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
