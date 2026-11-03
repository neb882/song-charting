"""The Windows side, seen from WSL: read-only interop, plus opening a URL (M4-02). Standard library only.

    wsl.is_wsl(), wsl.distro()                   # in WSL at all, and which distro
    wsl.windows_env("USERPROFILE")               # 'C:\\Users\\Jörg', through cmd.exe
    wsl.shell_folder("Personal")                 # Documents as a Linux path (/mnt/c/...), wherever OneDrive moved it
    wsl.wslconfig()                              # %USERPROFILE%\\.wslconfig: memory, swap, localhostForwarding, ...

  * **Interop.** Every Windows program runs through WSL's interop: from PATH (`appendWindowsPath`, on by default),
    else from C:\\Windows\\System32 under /mnt/c. Each call has a timeout and runs with its working folder on /mnt/c,
    so cmd.exe does not warn about a UNC folder (\\\\wsl.localhost\\...). A call that fails (interop off, a missing
    program, a timeout, output that does not parse) returns None (False for the yes/no questions): nothing here
    raises.
  * **Encodings.** `cmd.exe /u` writes its own output (echo) as UTF-16LE, so a user name like Jörg survives; reg.exe
    writes in the console's OEM code page, which `cmd.exe /c chcp` names (cp437 when it cannot be read).
  * **Read-only.** Nothing here changes Windows: queries only, `update_wslconfig` (text in, text out: the install
    writes the file) and `open_url` (explorer.exe) to show the page.
"""
from __future__ import annotations

import codecs
import configparser
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Mapping

MNT_C = Path("/mnt/c")                    # where WSL mounts C: (tests point it elsewhere)
OSRELEASE = Path("/proc/sys/kernel/osrelease")
MEMINFO = Path("/proc/meminfo")
TIMEOUT_S = 10.0                          # every interop call but PowerShell's
POWERSHELL_TIMEOUT_S = 30.0               # PowerShell starts slowly, the more so on a busy PC
SHELL_FOLDERS = r"HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders"
ONEDRIVE_VARS = ("OneDrive", "OneDriveConsumer", "OneDriveCommercial")
UNITS = {"": 1, "B": 1, "K": 2 ** 10, "KB": 2 ** 10, "M": 2 ** 20, "MB": 2 ** 20, "G": 2 ** 30, "GB": 2 ** 30,
         "T": 2 ** 40, "TB": 2 ** 40}    # .wslconfig sizes: 12GB, 12288MB (binary, as WSL reads them)
_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_()]*$")   # an environment variable name cmd.exe can echo safely


def is_wsl() -> bool:
    """Whether this is Linux in WSL: $WSL_DISTRO_NAME is set, or the kernel's release names Microsoft."""
    if os.environ.get("WSL_DISTRO_NAME"):
        return True
    try:
        return "microsoft" in OSRELEASE.read_text(encoding="ascii", errors="replace").lower()
    except OSError:
        return False


def distro() -> str | None:
    """The WSL distro's name ($WSL_DISTRO_NAME), else None."""
    return os.environ.get("WSL_DISTRO_NAME") or None


def _exe(name: str, *where: str) -> str | None:
    """A Windows program: from PATH, else from its folder under /mnt/c (`where`, relative to C:\\)."""
    found = shutil.which(name)
    if found:
        return found
    for folder in where:
        p = MNT_C / folder / name
        if p.is_file():
            return str(p)
    return None


def _cmd() -> str | None:
    return _exe("cmd.exe", "Windows/System32")


def _run(argv: list[str | None], timeout: float = TIMEOUT_S) -> bytes | None:
    """The program's stdout when it ran and exited 0, else None. Its working folder is /mnt/c when that exists."""
    if not argv or argv[0] is None:
        return None
    try:
        proc = subprocess.run([str(a) for a in argv], capture_output=True, timeout=timeout,
                              cwd=str(MNT_C) if MNT_C.is_dir() else None, stdin=subprocess.DEVNULL)
    except (OSError, subprocess.SubprocessError, ValueError):
        return None
    return proc.stdout if proc.returncode == 0 else None


def interop_ok() -> bool:
    """Whether cmd.exe runs (from PATH, or C:\\Windows\\System32 under /mnt/c)."""
    return _run([_cmd(), "/d", "/c", "exit 0"]) is not None


def windows_env(name: str) -> str | None:
    """A Windows environment variable through `cmd.exe /u /c echo %NAME%` (UTF-16LE output), else None: unset (cmd
    echoes `%NAME%` back), a name cmd cannot echo safely, or no interop."""
    if not _NAME.match(name):
        return None
    out = _run([_cmd(), "/d", "/u", "/c", f"echo %{name}%"])
    if out is None:
        return None
    try:
        text = out.decode("utf-16-le").strip("\r\n\x00 ")
    except UnicodeDecodeError:
        return None
    return None if not text or text == f"%{name}%" else text


def to_linux(winpath: str) -> Path | None:
    """A Windows path as WSL sees it (`wslpath -u`), else None."""
    out = _run([shutil.which("wslpath") or "/usr/bin/wslpath", "-u", winpath])
    text = out.decode("utf-8", "replace").strip() if out else ""
    return Path(text) if text else None


def oem_encoding() -> str:
    """The console's OEM code page as a Python codec ("cp850"), from `cmd.exe /c chcp` ("Active code page: 850", or
    a translation of it); cp437 when it cannot be read or Python has no such codec."""
    out = _run([_cmd(), "/d", "/c", "chcp"])
    m = re.search(r":\s*(\d+)", out.decode("ascii", "replace")) if out else None
    if m:
        try:
            codecs.lookup(f"cp{m.group(1)}")
            return f"cp{m.group(1)}"
        except LookupError:
            pass
    return "cp437"


def registry_shell_folder(name: str) -> str | None:
    """The raw value of a User Shell Folders entry (Personal is Documents, Desktop, Programs the Start menu's
    programs), such as %USERPROFILE%\\Documents, from reg.exe's output in the OEM code page; else None."""
    out = _run([_exe("reg.exe", "Windows/System32"), "query", SHELL_FOLDERS, "/v", name])
    if out is None:
        return None
    text = out.decode(oem_encoding(), "replace")
    m = re.search(rf"^\s*{re.escape(name)}\s+REG_(?:EXPAND_)?SZ\s+(.*?)\s*$", text, re.MULTILINE | re.IGNORECASE)
    return m.group(1) if m and m.group(1) else None


def expand(value: str) -> str | None:
    """Each %VAR% in a Windows value expanded with windows_env; None when one does not expand."""
    failed = False

    def sub(m: re.Match) -> str:
        nonlocal failed
        got = windows_env(m.group(1))
        failed |= got is None
        return got or ""

    out = re.sub(r"%([^%]+)%", sub, value)
    return None if failed else out


def shell_folder(name: str) -> Path | None:
    """A User Shell Folders entry as a Linux path, only when that folder exists (registry_shell_folder, expand,
    to_linux). This follows OneDrive when it has moved Documents."""
    raw = registry_shell_folder(name)
    winpath = expand(raw) if raw else None
    path = to_linux(winpath) if winpath else None
    return path if path is not None and path.is_dir() else None


def onedrive_roots() -> list[Path]:
    """The OneDrive folders Windows names (%OneDrive%, %OneDriveConsumer%, %OneDriveCommercial%) as Linux paths,
    each once."""
    roots: list[Path] = []
    for var in ONEDRIVE_VARS:
        winpath = windows_env(var)
        path = to_linux(winpath) if winpath else None
        if path is not None and path not in roots:
            roots.append(path)
    return roots


def parse_size(text: str | None) -> int | None:
    """A .wslconfig size (12GB, 12288MB, 8 GB) in bytes, else None."""
    m = re.match(r"^\s*(\d+(?:\.\d+)?)\s*([KMGT]?B?)\s*$", text or "", re.IGNORECASE)
    return int(float(m.group(1)) * UNITS[m.group(2).upper()]) if m else None


def _bool(text: str | None) -> bool | None:
    word = (text or "").strip().lower()
    return True if word == "true" else False if word == "false" else None


def _decode(data: bytes) -> str:
    """A text file as Notepad may have saved it: UTF-16 with its BOM, or UTF-8 with or without one."""
    if data[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return data.decode("utf-16", "replace")
    return data.decode("utf-8-sig", "replace")


def _value(raw: str | None) -> str | None:
    """A .wslconfig value as git-config style parsing reads it: up to a # or ; outside quotes (a trailing comment),
    stripped, and without the quotes around it ("12GB", '12GB')."""
    if raw is None:
        return None
    out, quote = [], None
    for ch in raw:
        if quote:
            quote = None if ch == quote else quote
        elif ch in "\"'":
            quote = ch
        elif ch in "#;":
            break
        out.append(ch)
    value = "".join(out).strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        value = value[1:-1].strip()
    return value


def parse_wslconfig(text: str) -> dict:
    """The [wsl2] values of a .wslconfig's text (section and keys in any case, values as _value reads them, a BOM
    left by a decoder ignored); each missing or unreadable one None."""
    cp = configparser.ConfigParser(interpolation=None, strict=False, comment_prefixes=("#", ";"))
    try:
        cp.read_string(text.lstrip("\ufeff"))
    except configparser.Error:
        return {"memory_bytes": None, "swap_bytes": None, "localhost_forwarding": None, "networking_mode": None}
    section = next((cp[s] for s in cp.sections() if s.strip().lower() == "wsl2"), {})

    def get(key: str) -> str | None:
        return _value(section.get(key))

    return {"memory_bytes": parse_size(get("memory")), "swap_bytes": parse_size(get("swap")),
            "localhost_forwarding": _bool(get("localhostforwarding")), "networking_mode": get("networkingmode") or None}


def update_wslconfig(text: str, values: Mapping[str, str]) -> str:
    """`text` (a .wslconfig's) with each of `values` ({"memory": "12GB", ...}) set in [wsl2], for the install
    (M4-03), which never writes a second line for a key: the first [wsl2] line that sets the key (any case, quoted or
    commented) becomes `key=value` and later ones go; a key it lacks goes after [wsl2]'s last line, and a [wsl2]
    section is added at the end when there is none. Every other line and section stays as it was, and so do the
    line ends (CRLF for a new file, as Windows writes it). Writing the file is the caller's."""
    nl = "\n" if "\n" in text and "\r\n" not in text else "\r\n"
    want = {k.lower(): (k, v) for k, v in values.items()}
    done: set[str] = set()
    out: list[str] = []
    section, first, end_of_first = None, False, None   # end_of_first: where a missing key goes in `out`
    for line in text.splitlines(keepends=True):
        body = line.rstrip("\r\n")
        bom = "\ufeff" if body.startswith("\ufeff") else ""
        s = body.lstrip("\ufeff").strip()
        header = re.match(r"\[([^\]]*)\]", s)
        if header:
            section = header.group(1).strip().lower()
            first = section == "wsl2" and end_of_first is None
            out.append(line)
            if first:
                end_of_first = len(out)
            continue
        key = s.split("=", 1)[0].strip().lower() if "=" in s and s[0] not in "#;" else None
        if section == "wsl2" and key in want:
            if key in done:   # a second line for the key: dropped
                continue
            done.add(key)
            line = f"{bom}{want[key][0]}={want[key][1]}{line[len(body):] or nl}"
        out.append(line)
        if first and s:
            end_of_first = len(out)
    missing = [f"{k}={v}{nl}" for key, (k, v) in want.items() if key not in done]
    if missing and end_of_first is None:
        if out and not out[-1].endswith(("\n", "\r")):
            out[-1] += nl
        if out and out[-1].strip():
            out.append(nl)
        out += [f"[wsl2]{nl}", *missing]
    elif missing:
        if not out[end_of_first - 1].endswith(("\n", "\r")):
            out[end_of_first - 1] += nl
        out[end_of_first:end_of_first] = missing
    return "".join(out)


def wslconfig() -> dict:
    """%USERPROFILE%\\.wslconfig: {"path" (as Windows names it, None without interop), "exists", "memory_bytes",
    "swap_bytes", "localhost_forwarding", "networking_mode"}, each missing value None."""
    profile = windows_env("USERPROFILE")
    folder = to_linux(profile) if profile else None
    out = {"path": None if profile is None else profile.rstrip("\\") + "\\.wslconfig", "exists": False,
           **parse_wslconfig("")}
    if folder is None:
        return out
    try:
        data = (folder / ".wslconfig").read_bytes()
    except OSError:
        return out
    return {**out, "exists": True, **parse_wslconfig(_decode(data))}


def windows_build() -> str | None:
    """Windows' version from `cmd.exe /c ver` ("10.0.26100.1000"), else None."""
    out = _run([_cmd(), "/d", "/c", "ver"])
    m = re.search(r"(\d+\.\d+\.\d+(?:\.\d+)?)", out.decode("ascii", "replace")) if out else None
    return m.group(1) if m else None


def _meminfo_total_bytes() -> int | None:
    try:
        with open(MEMINFO, encoding="ascii", errors="replace") as f:
            for line in f:
                if line.startswith("MemTotal:"):
                    return int(line.split()[1]) * 1024
    except (OSError, ValueError, IndexError):
        pass
    return None


def windows_ram_bytes(config: dict | None = None) -> int | None:
    """Windows' physical memory in bytes: PowerShell's Win32_ComputerSystem.TotalPhysicalMemory (an inline command,
    not a script file), else, when .wslconfig sets no memory (`config`: wslconfig(), read when not given), twice WSL's
    MemTotal (WSL's default is half of Windows' memory), else None."""
    ps = _exe("powershell.exe", "Windows/System32/WindowsPowerShell/v1.0")
    out = _run([ps, "-NoProfile", "-NonInteractive", "-Command",
                "(Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory"], timeout=POWERSHELL_TIMEOUT_S)
    m = re.search(r"(\d{6,})", out.decode("ascii", "replace")) if out else None
    if m:
        return int(m.group(1))
    config = wslconfig() if config is None else config
    if config.get("path") is not None and config.get("memory_bytes") is None:
        total = _meminfo_total_bytes()
        return 2 * total if total else None
    return None


def windows_curl(url: str) -> str | None:
    """What Windows' own curl.exe (System32's) fetches from `url` in 5 s, else None: whether the Windows side reaches
    a server in WSL (M4-04's localhost-forwarding check)."""
    exe = MNT_C / "Windows" / "System32" / "curl.exe"
    out = _run([str(exe) if exe.is_file() else None, "-s", "-m", "5", url])
    return out.decode("utf-8", "replace") if out is not None else None


def open_url(url: str) -> bool:
    """Open `url` in the Windows browser with explorer.exe; whether explorer.exe started (it exits 1 even when it
    opened the page, so its exit code says nothing)."""
    exe = _exe("explorer.exe", "Windows")
    if exe is None:
        return False
    try:
        subprocess.run([exe, url], capture_output=True, timeout=TIMEOUT_S, stdin=subprocess.DEVNULL,
                       cwd=str(MNT_C) if MNT_C.is_dir() else None)
    except subprocess.TimeoutExpired:
        return True   # started, and still busy
    except (OSError, subprocess.SubprocessError, ValueError):
        return False
    return True
