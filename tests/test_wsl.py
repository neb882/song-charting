"""The Windows side seen from WSL (songcharter.wsl), against stand-in Windows programs on PATH: a cmd.exe that echoes
in UTF-16LE with /u (and in the OEM code page without it) and answers chcp and ver, a reg.exe that writes in the OEM
code page, wslpath mapping C:\\ onto a temporary folder, powershell.exe, explorer.exe and System32's curl.exe. Their
answers come from a JSON file ($FAKE_WINDOWS). Nothing here needs Windows."""
import json
import os
import sys
from pathlib import Path

import pytest

from songcharter import wsl

CMD = r'''
import json, os, re, sys
cfg = json.load(open(os.environ["FAKE_WINDOWS"], encoding="utf-8"))
args = sys.argv[1:]
line = args[args.index("/c") + 1] if "/c" in args else ""
code = 0
if line.startswith("echo "):
    out = re.sub(r"%([^%]+)%", lambda m: cfg["env"].get(m.group(1), m.group(0)), line[5:]) + "\r\n"
elif line == "chcp":
    out = cfg.get("chcp", "Active code page: 850") + "\r\n"
elif line == "ver":
    out = "\r\nMicrosoft Windows [Version 10.0.26100.1000]\r\n"
elif line == "exit 0":
    out = ""
else:
    out, code = "'%s' is not recognized\r\n" % line, 1
sys.stdout.buffer.write(out.encode("utf-16-le") if "/u" in args else out.encode(cfg["codepage"]))
sys.exit(code)
'''
REG = r'''
import json, os, sys
cfg = json.load(open(os.environ["FAKE_WINDOWS"], encoding="utf-8"))
args = sys.argv[1:]
name = args[args.index("/v") + 1]
assert args[:2] == ["query", r"HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders"], args
if name not in cfg["registry"]:
    sys.stderr.write("ERROR: The system was unable to find the specified registry key or value.\r\n")
    sys.exit(1)
kind, value = cfg["registry"][name]
out = "\r\nHKEY_CURRENT_USER\\" + args[1][5:] + "\r\n    %s    %s    %s\r\n\r\n" % (name, kind, value)
sys.stdout.buffer.write(out.encode(cfg["codepage"]))
'''
WSLPATH = r'''
import json, os, sys
cfg = json.load(open(os.environ["FAKE_WINDOWS"], encoding="utf-8"))
assert sys.argv[1] == "-u", sys.argv
p = sys.argv[2]
if not p[1:3] == ":\\":
    sys.exit(1)
print(cfg["drives"][p[0].upper()] + "/" + p[3:].replace("\\", "/"))
'''
POWERSHELL = r'''
import json, os, sys
cfg = json.load(open(os.environ["FAKE_WINDOWS"], encoding="utf-8"))
assert sys.argv[1:4] == ["-NoProfile", "-NonInteractive", "-Command"], sys.argv
if cfg.get("ram") is None:
    sys.exit(1)
sys.stdout.write(str(cfg["ram"]) + "\r\n")
'''
EXPLORER = r'''
import json, os, sys
cfg = json.load(open(os.environ["FAKE_WINDOWS"], encoding="utf-8"))
open(cfg["opened"], "a", encoding="utf-8").write(sys.argv[1] + "\n")
sys.exit(1)   # as explorer.exe does, even when it opened the page
'''
CURL = r'''
import sys
assert sys.argv[1:4] == ["-s", "-m", "5"], sys.argv
if "hello" not in sys.argv[4]:
    sys.exit(7)
sys.stdout.write('{"app": "songcharter", "token": "abc"}')
'''


def script(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"#!{sys.executable}\n{body}", encoding="utf-8")
    path.chmod(0o755)


@pytest.fixture
def windows(tmp_path, monkeypatch):
    """A Windows reached through stand-ins: C:\\ is tmp/c (and /mnt/c), the user is Jörg, the OEM code page 850,
    Documents moved by OneDrive. Returns (the config dict, a function that writes it, C:\\ as a Linux path)."""
    c = tmp_path / "c"
    (c / "Users" / "Jörg" / "OneDrive" / "Documents").mkdir(parents=True)
    bin_ = tmp_path / "bin"
    for name, body in (("cmd.exe", CMD), ("reg.exe", REG), ("wslpath", WSLPATH), ("powershell.exe", POWERSHELL),
                       ("explorer.exe", EXPLORER)):
        script(bin_ / name, body)
    script(c / "Windows" / "System32" / "curl.exe", CURL)
    cfg = {"codepage": "cp850", "drives": {"C": str(c)}, "ram": 17024139264, "opened": str(tmp_path / "opened.txt"),
           "env": {"USERPROFILE": "C:\\Users\\Jörg", "OneDrive": "C:\\Users\\Jörg\\OneDrive",
                   "OneDriveConsumer": "C:\\Users\\Jörg\\OneDrive"},
           "registry": {"Personal": ["REG_EXPAND_SZ", "%USERPROFILE%\\OneDrive\\Documents"],
                        "Desktop": ["REG_SZ", "C:\\Users\\Jörg\\Bureau privé"],
                        "Programs": ["REG_EXPAND_SZ", "%APPDATA%\\Microsoft\\Windows\\Start Menu\\Programs"]}}

    def write():
        (tmp_path / "windows.json").write_text(json.dumps(cfg), encoding="utf-8")

    write()
    monkeypatch.setenv("FAKE_WINDOWS", str(tmp_path / "windows.json"))
    monkeypatch.setenv("PATH", str(bin_))   # nothing of a real Windows (appendWindowsPath) can answer instead
    monkeypatch.setattr(wsl, "MNT_C", c)
    monkeypatch.setattr(wsl, "MEMINFO", tmp_path / "meminfo")
    (tmp_path / "meminfo").write_text("MemTotal:        8165836 kB\nMemFree:  100 kB\n", encoding="ascii")
    return cfg, write, c


def test_windows_env_survives_a_name_outside_ascii(windows):
    """cmd.exe /u writes UTF-16LE, so Jörg's profile folder comes back whole; an unset variable (echoed back as
    %NAME%) and a name cmd could not echo safely are None."""
    assert wsl.windows_env("USERPROFILE") == "C:\\Users\\Jörg"
    assert wsl.windows_env("NOT_SET") is None
    assert wsl.windows_env("A&calc") is None and wsl.windows_env("") is None
    assert wsl.interop_ok() and wsl.windows_build() == "10.0.26100.1000"
    assert wsl.oem_encoding() == "cp850"


def test_shell_folders_are_read_in_the_oem_code_page_and_expanded(windows):
    """reg.exe's value in cp850, its %USERPROFILE% expanded, as a Linux path that exists (Documents moved by
    OneDrive); a folder that does not exist, or a variable that does not expand, gives None."""
    cfg, write, c = windows
    assert wsl.registry_shell_folder("Personal") == "%USERPROFILE%\\OneDrive\\Documents"
    assert wsl.expand("%USERPROFILE%\\OneDrive\\Documents") == "C:\\Users\\Jörg\\OneDrive\\Documents"
    assert wsl.shell_folder("Personal") == c / "Users" / "Jörg" / "OneDrive" / "Documents"
    assert wsl.registry_shell_folder("Desktop") == "C:\\Users\\Jörg\\Bureau privé"   # é and ö as cp850 wrote them
    assert wsl.shell_folder("Desktop") is None                                      # not there
    (c / "Users" / "Jörg" / "Bureau privé").mkdir()
    assert wsl.shell_folder("Desktop") == c / "Users" / "Jörg" / "Bureau privé"
    assert wsl.shell_folder("Programs") is None and wsl.expand("%APPDATA%\\x") is None   # APPDATA is not set here
    assert wsl.registry_shell_folder("NoSuchFolder") is None
    cfg["chcp"] = "Page de codes active : 850"   # a translated chcp still names the code page
    write()
    assert wsl.oem_encoding() == "cp850"
    cfg["chcp"] = "Active code page: 99999"      # one Python has no codec for
    write()
    assert wsl.oem_encoding() == "cp437"
    assert wsl.to_linux("C:\\Users") == c / "Users" and wsl.to_linux("relative") is None
    assert wsl.onedrive_roots() == [c / "Users" / "Jörg" / "OneDrive"]   # OneDriveConsumer is the same folder


def test_wslconfig(windows):
    """%USERPROFILE%\\.wslconfig: memory=12GB and swap = 8192MB in bytes, the [wsl2] section and its keys in any
    case, booleans and the networking mode; a missing file gives every value None."""
    cfg, write, c = windows
    path = c / "Users" / "Jörg" / ".wslconfig"
    got = wsl.wslconfig()
    assert got == {"path": "C:\\Users\\Jörg\\.wslconfig", "exists": False, "memory_bytes": None, "swap_bytes": None,
                   "localhost_forwarding": None, "networking_mode": None}
    path.write_text("# for 16 GB\n[wsl2]\nmemory=12GB\nswap = 8192MB\nlocalhostForwarding=false\n", encoding="utf-8")
    assert wsl.wslconfig() == {"path": "C:\\Users\\Jörg\\.wslconfig", "exists": True, "memory_bytes": 12 * 2 ** 30,
                               "swap_bytes": 8 * 2 ** 30, "localhost_forwarding": False, "networking_mode": None}
    path.write_bytes("[WSL2]\r\nMemory=12288MB\r\nnetworkingMode=Mirrored\r\n".encode("utf-16"))   # Notepad's UTF-16
    got = wsl.wslconfig()
    assert got["memory_bytes"] == 12 * 2 ** 30 and got["networking_mode"] == "Mirrored" and got["swap_bytes"] is None
    path.write_text("[wsl2]\nmemory=lots\n[experimental]\nswap=8GB\n", encoding="utf-8")
    assert wsl.wslconfig()["memory_bytes"] is None and wsl.wslconfig()["swap_bytes"] is None
    path.write_text("not an ini file at all [\n", encoding="utf-8")
    assert wsl.wslconfig()["exists"] and wsl.wslconfig()["memory_bytes"] is None
    assert [wsl.parse_size(x) for x in ("12GB", "8 gb", "512M", "1TB", "4096", "12 GiB", "")] == [
        12 * 2 ** 30, 8 * 2 ** 30, 512 * 2 ** 20, 2 ** 40, 4096, None, None]


def test_wslconfig_values_with_inline_comments_and_quotes():
    """git-config style values: a trailing # or ; comment outside quotes goes, and so do the quotes around a value;
    CRLF, a BOM, any case and every unit still read."""
    text = ("﻿[WSL2]\r\nMemory = 12GB # leave 4 for Windows\r\nswap=\"8GB\" ; plenty\r\n"
            "localhostForwarding = 'false'\r\nnetworkingMode=\"mir#rored\"  # a # inside quotes stays\r\n")
    assert wsl.parse_wslconfig(text) == {"memory_bytes": 12 * 2 ** 30, "swap_bytes": 8 * 2 ** 30,
                                         "localhost_forwarding": False, "networking_mode": "mir#rored"}
    assert wsl.parse_wslconfig("[wsl2]\nmemory=\"12288MB\"\n")["memory_bytes"] == 12 * 2 ** 30
    assert wsl.parse_wslconfig("[wsl2]\nmemory=12GB;8GB\n")["memory_bytes"] == 12 * 2 ** 30
    assert wsl.parse_wslconfig("[wsl2]\nmemory=# nothing\n")["memory_bytes"] is None
    assert wsl.parse_wslconfig(wsl._decode(b"\xef\xbb\xbf[wsl2]\r\nmemory=12GB # x\r\n"))["memory_bytes"] == 12 * 2 ** 30


def wsl2_lines(text: str, key: str) -> list[str]:
    """The lines of [wsl2] (any case) that set `key` (any case)."""
    out, inside = [], False
    for line in text.splitlines():
        s = line.strip().lstrip("﻿")
        if s.startswith("["):
            inside = s.split("]")[0][1:].strip().lower() == "wsl2"
        elif inside and "=" in s and s[0] not in "#;" and s.split("=")[0].strip().lower() == key:
            out.append(line)
    return out


def test_an_update_never_writes_a_second_memory_line():
    """update_wslconfig sets each key in place (the first [wsl2] line that sets it, whatever its case, quotes or
    comment; later ones go), adds the missing ones to [wsl2] (made when there is none), keeps every other line and
    section and the file's line ends, and what it writes reads back."""
    old = ("# mine\r\n[WSL2]\r\nMemory = \"10GB\" # old\r\nprocessors=4\r\nmemory=6GB\r\n# memory=99GB, a comment\r\n"
           "\r\n[experimental]\r\nmemory=1GB\r\n")
    new = wsl.update_wslconfig(old, {"memory": "12GB", "swap": "8GB"})
    assert new == ("# mine\r\n[WSL2]\r\nmemory=12GB\r\nprocessors=4\r\n# memory=99GB, a comment\r\nswap=8GB\r\n"
                   "\r\n[experimental]\r\nmemory=1GB\r\n")
    assert wsl2_lines(new, "memory") == ["memory=12GB"] and wsl2_lines(new, "swap") == ["swap=8GB"]
    assert wsl.parse_wslconfig(new)["memory_bytes"] == 12 * 2 ** 30
    assert wsl.update_wslconfig(new, {"memory": "12GB", "swap": "8GB"}) == new   # again: nothing moves
    assert wsl.update_wslconfig("", {"memory": "12GB", "swap": "8GB"}) == "[wsl2]\r\nmemory=12GB\r\nswap=8GB\r\n"
    unix = wsl.update_wslconfig("[boot]\nsystemd=true", {"memory": "12GB"})
    assert unix == "[boot]\nsystemd=true\n\n[wsl2]\nmemory=12GB\n"
    assert wsl.parse_wslconfig(unix)["memory_bytes"] == 12 * 2 ** 30


def test_windows_ram(windows):
    """PowerShell's TotalPhysicalMemory; without it, twice WSL's MemTotal when .wslconfig sets no memory (WSL's
    default is half), and None when it does."""
    cfg, write, c = windows
    assert wsl.windows_ram_bytes() == 17024139264
    cfg["ram"] = None
    write()
    assert wsl.windows_ram_bytes() == 2 * 8165836 * 1024
    (c / "Users" / "Jörg" / ".wslconfig").write_text("[wsl2]\nmemory=12GB\n", encoding="utf-8")
    assert wsl.windows_ram_bytes() is None


def test_the_browser_and_the_forwarding_check(windows, tmp_path):
    """open_url starts explorer.exe with the URL and ignores its exit code 1; windows_curl is System32's curl.exe."""
    assert wsl.open_url("http://localhost:8765/") is True
    assert (tmp_path / "opened.txt").read_text(encoding="utf-8") == "http://localhost:8765/\n"
    assert wsl.windows_curl("http://localhost:8765/api/hello") == '{"app": "songcharter", "token": "abc"}'
    assert wsl.windows_curl("http://localhost:8765/nothing") is None


def test_without_cmd_exe_everything_is_none(tmp_path, monkeypatch):
    """No Windows programs at all (interop off, or not WSL): every call gives None (False, an empty list, the
    default code page), and none raises."""
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))
    monkeypatch.setattr(wsl, "MNT_C", tmp_path / "no-c")
    assert not wsl.interop_ok()
    assert wsl.windows_env("USERPROFILE") is None and wsl.windows_build() is None
    assert wsl.registry_shell_folder("Personal") is None and wsl.shell_folder("Personal") is None
    assert wsl.oem_encoding() == "cp437" and wsl.onedrive_roots() == []
    assert wsl.wslconfig() == {"path": None, "exists": False, "memory_bytes": None, "swap_bytes": None,
                               "localhost_forwarding": None, "networking_mode": None}
    assert wsl.windows_ram_bytes() is None and wsl.windows_curl("http://localhost/") is None
    assert wsl.open_url("http://localhost/") is False


def test_is_wsl(monkeypatch, tmp_path):
    monkeypatch.setenv("WSL_DISTRO_NAME", "Ubuntu-26.04")
    assert wsl.is_wsl() and wsl.distro() == "Ubuntu-26.04"
    monkeypatch.delenv("WSL_DISTRO_NAME")
    assert wsl.distro() is None
    release = tmp_path / "osrelease"
    release.write_text("6.6.87.2-microsoft-standard-WSL2\n", encoding="ascii")
    monkeypatch.setattr(wsl, "OSRELEASE", release)
    assert wsl.is_wsl()
    release.write_text("6.18.44-fc-v230\n", encoding="ascii")
    assert not wsl.is_wsl()
    monkeypatch.setattr(wsl, "OSRELEASE", tmp_path / "missing")
    assert not wsl.is_wsl()
    assert os.environ.get("WSL_DISTRO_NAME") is None
