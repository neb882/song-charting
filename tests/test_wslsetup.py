"""The Windows side of the install (songcharter.wslsetup): the memory rule in .wslconfig and the Start-menu shortcut,
against stand-in Windows programs on PATH (cmd.exe, reg.exe, wslpath and powershell.exe, as in test_wsl.py) that
answer from a JSON file. C:\\ is a temporary folder; nothing here needs Windows."""
import json
import sys
from pathlib import Path

import pytest

from songcharter import runtime, wsl, wslsetup

GIB = 2 ** 30
CMD = r'''
import json, os, re, sys
cfg = json.load(open(os.environ["FAKE_WINDOWS"], encoding="utf-8"))
args = sys.argv[1:]
line = args[args.index("/c") + 1] if "/c" in args else ""
if not cfg.get("interop", True):
    sys.exit(1)
if line.startswith("echo "):
    out = re.sub(r"%([^%]+)%", lambda m: cfg["env"].get(m.group(1), m.group(0)), line[5:]) + "\r\n"
elif line in ("exit 0", "chcp"):
    out = "Active code page: 850\r\n" if line == "chcp" else ""
else:
    sys.exit(1)
sys.stdout.buffer.write(out.encode("utf-16-le") if "/u" in args else out.encode("cp850"))
'''
REG = r'''
import json, os, sys
cfg = json.load(open(os.environ["FAKE_WINDOWS"], encoding="utf-8"))
name = sys.argv[sys.argv.index("/v") + 1]
if name != "Programs":
    sys.exit(1)
value = "%APPDATA%\\Microsoft\\Windows\\Start Menu\\Programs"
out = "\r\nHKEY_CURRENT_USER\\...\r\n    Programs    REG_EXPAND_SZ    " + value + "\r\n"
sys.stdout.buffer.write(out.encode("cp850"))
'''
WSLPATH = r'''
import json, os, sys
cfg = json.load(open(os.environ["FAKE_WINDOWS"], encoding="utf-8"))
p = sys.argv[2]
if p[1:3] != ":\\":
    sys.exit(1)
print(cfg["c"] + "/" + p[3:].replace("\\", "/"))
'''
POWERSHELL = r'''
import json, os, sys
cfg = json.load(open(os.environ["FAKE_WINDOWS"], encoding="utf-8"))
if cfg.get("ram") is None:
    sys.exit(1)
print(cfg["ram"])
'''


def script(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"#!{sys.executable}\n{body}", encoding="utf-8")
    path.chmod(0o755)


@pytest.fixture
def windows(tmp_path, monkeypatch):
    """WSL on a Windows reached through stand-ins: C:\\ is tmp/c, the user Jörg, a "16 GB" PC (15.9 GiB), WSL with
    7.8 GiB, the distro Ubuntu-26.04. Returns an object with the config (`cfg`, then `write()`), the profile folder,
    the Start-menu folder and a songcharter home with a runtime.json."""
    c = tmp_path / "c"
    profile = c / "Users" / "Jörg"
    programs = profile / "AppData" / "Roaming" / "Microsoft" / "Windows" / "Start Menu" / "Programs"
    programs.mkdir(parents=True)
    bin_ = tmp_path / "bin"
    for name, body in (("cmd.exe", CMD), ("reg.exe", REG), ("wslpath", WSLPATH), ("powershell.exe", POWERSHELL)):
        script(bin_ / name, body)
    cfg = {"c": str(c), "ram": 17024139264, "interop": True,
           "env": {"USERPROFILE": "C:\\Users\\Jörg", "APPDATA": "C:\\Users\\Jörg\\AppData\\Roaming",
                   "windir": "C:\\WINDOWS"}}

    def write():
        (tmp_path / "windows.json").write_text(json.dumps(cfg), encoding="utf-8")

    write()
    monkeypatch.setenv("FAKE_WINDOWS", str(tmp_path / "windows.json"))
    monkeypatch.setenv("PATH", str(bin_))
    monkeypatch.setenv("WSL_DISTRO_NAME", "Ubuntu-26.04")
    monkeypatch.setattr(wsl, "MNT_C", c)
    monkeypatch.setattr(wsl, "MEMINFO", tmp_path / "meminfo")
    (tmp_path / "meminfo").write_text("MemTotal:        8165836 kB\n", encoding="ascii")
    home = tmp_path / "home" / ".local" / "share" / "songcharter"
    (home / "runtime" / "allin1" / "bin").mkdir(parents=True)
    (home / "runtime" / "allin1" / "bin" / "python").write_text("", encoding="utf-8")
    allin1 = str(home / "runtime" / "allin1" / "bin" / "python")
    (home / "runtime" / "runtime.json").write_text(json.dumps({"allin1_python": allin1}), encoding="utf-8")

    class W:
        pass

    w = W()
    w.cfg, w.write, w.profile, w.programs, w.home, w.allin1 = cfg, write, profile, programs, home, allin1
    w.launcher = Path("/home/jorg/.local/bin/songcharter")
    w.config = profile / ".wslconfig"
    return w


def apply(w, *, yes=False, ram=None, answers=()):
    said, asked = [], []
    answers = list(answers)

    def ask(q):
        asked.append(q)
        return answers.pop(0)

    out = wslsetup.apply(w.home, w.launcher, yes, ram, ask=ask, say=said.append)
    return out, said, asked


def backups(w):
    return sorted(p.name for p in w.profile.glob(".wslconfig.songcharter-*"))


def allin1(w):
    return json.loads((w.home / "runtime" / "runtime.json").read_text(encoding="utf-8"))["allin1_python"]


def test_no_wslconfig_gets_one_in_crlf_with_the_rounded_target(windows):
    """A "16 GB" PC reports 15.9 GiB: rounded to 16, less 4, gives memory=12GB (not 11.9GB), with swap=8GB, in a new
    file with CRLF line ends; no backup, as there was no file."""
    w = windows
    out, said, asked = apply(w)
    assert w.config.read_bytes() == b"[wsl2]\r\nmemory=12GB\r\nswap=8GB\r\n"
    assert out["changed"] and out["memory_bytes"] == 12 * GIB and out["allin1"] and not asked
    assert backups(w) == [] and allin1(w) == w.allin1
    assert any("wrote memory=12GB and swap=8GB" in s and "16 GB of RAM" in s for s in said), said
    assert wsl.wslconfig()["memory_bytes"] == 12 * GIB   # read back the way doctor reads it


def test_a_wslconfig_without_memory_keeps_its_other_lines_and_is_backed_up(windows):
    w = windows
    old = ("# mine\r\n[wsl2]\r\nprocessors=6\r\nswap = 2GB # small\r\n\r\n[experimental]\r\n"
           "autoMemoryReclaim=gradual\r\n")
    w.config.write_text(old, encoding="utf-8", newline="")
    out, said, _ = apply(w)
    assert out["changed"]
    assert w.config.read_text(encoding="utf-8", newline="") == (
        "# mine\r\n[wsl2]\r\nprocessors=6\r\nswap=8GB\r\nmemory=12GB\r\n\r\n[experimental]\r\n"
        "autoMemoryReclaim=gradual\r\n")
    [backup] = backups(w)
    assert (w.profile / backup).read_text(encoding="utf-8", newline="") == old
    assert any(f"the old file is kept as {backup}" in s for s in said), said


def test_twelve_gb_or_more_is_kept(windows):
    w = windows
    w.config.write_text("[wsl2]\nmemory=16GB\n", encoding="utf-8")
    out, said, asked = apply(w)
    assert not out["changed"] and out["memory_bytes"] == 16 * GIB and not asked
    assert w.config.read_text(encoding="utf-8") == "[wsl2]\nmemory=16GB\n" and backups(w) == []
    assert any("memory=16GB kept" in s for s in said), said


def test_under_twelve_gb_asks_before_raising(windows):
    """Asked, and answered no: kept as it is. Answered yes, or --yes: raised to the target, only memory changed, the
    old file backed up; LF line ends stay LF."""
    w = windows
    w.config.write_text("[wsl2]\nmemory=10GB\nswap=1GB\n", encoding="utf-8")
    out, said, asked = apply(w, answers=[False])
    assert asked == ["WSL may use 10 GB; songcharter needs about 12. Raise it to 12 GB? [Y/n]"]
    assert not out["changed"] and w.config.read_text(encoding="utf-8") == "[wsl2]\nmemory=10GB\nswap=1GB\n"
    assert out["memory_bytes"] == 10 * GIB and not out["allin1"] and allin1(w) is None   # 10 GiB: under 11 GB
    out, said, asked = apply(w, answers=[True])
    assert out["changed"] and w.config.read_bytes() == b"[wsl2]\nmemory=12GB\nswap=1GB\n" and len(backups(w)) == 1
    assert allin1(w) == w.allin1 and any("allin1 is back in" in s for s in said)
    w.config.write_text("[wsl2]\nmemory=8GB\n", encoding="utf-8")
    out, said, asked = apply(w, yes=True)
    assert out["changed"] and not asked and w.config.read_text(encoding="utf-8") == "[wsl2]\nmemory=12GB\n"


def test_windows_ram_unknown_writes_nothing(windows):
    """PowerShell fails and .wslconfig sets a memory (so WSL's MemTotal says nothing of Windows' RAM): nothing is
    written, and the person is told how to set it by hand."""
    w = windows
    w.cfg["ram"] = None
    w.write()
    w.config.write_text("[wsl2]\nmemory=11GB\n", encoding="utf-8")
    out, said, asked = apply(w)
    assert not out["changed"] and not asked and backups(w) == []
    assert w.config.read_text(encoding="utf-8") == "[wsl2]\nmemory=11GB\n"
    assert any("Windows' RAM could not be read" in s and "set it by hand" in s and "memory=" in s for s in said), said


def test_a_pc_under_16_gb_leaves_allin1_out_and_one_under_12_is_refused(windows):
    w = windows
    w.cfg["ram"] = 14 * GIB - 100 * 2 ** 20   # a "14 GB" PC: memory=10GB, under 11 GB
    w.write()
    out, said, _ = apply(w)
    assert w.config.read_bytes() == b"[wsl2]\r\nmemory=10GB\r\nswap=8GB\r\n"
    assert not out["allin1"] and allin1(w) is None
    assert any("under 11 GB: allin1" in s and "librosa fallback" in s for s in said), said
    w.config.unlink()
    (w.programs / "songcharter.lnk").unlink()
    w.cfg["ram"] = 11 * GIB
    w.write()
    with pytest.raises(wslsetup.Refused, match="at least 12 GB of RAM"):
        apply(w)
    assert not w.config.exists() and not (w.programs / "songcharter.lnk").exists()


def test_declining_a_raise_under_8_gb_is_refused(windows):
    w = windows
    w.config.write_text("[wsl2]\nmemory=6GB\n", encoding="utf-8")
    with pytest.raises(wslsetup.Refused, match="only 6 GB, under 8"):
        apply(w, answers=[False])
    assert w.config.read_text(encoding="utf-8") == "[wsl2]\nmemory=6GB\n"


def test_the_ram_override(windows, monkeypatch):
    """--windows-ram-gb 16 on a 64 GB PC writes a 16 GB PC's file (M4-08 part A); $SONGCHARTER_WINDOWS_RAM_GB too,
    through the command line."""
    w = windows
    w.cfg["ram"] = 64 * GIB
    w.write()
    apply(w, ram=wslsetup.ram_override("16"))
    assert w.config.read_bytes() == b"[wsl2]\r\nmemory=12GB\r\nswap=8GB\r\n"
    w.config.unlink()
    monkeypatch.setenv("SONGCHARTER_WINDOWS_RAM_GB", "24")
    flag = w.home / "restart"
    assert wslsetup.main(["apply", "--home", str(w.home), "--restart-flag", str(flag)]) == 0
    assert w.config.read_bytes() == b"[wsl2]\r\nmemory=20GB\r\nswap=8GB\r\n" and flag.is_file()
    with pytest.raises(wslsetup.Refused, match="positive number"):
        wslsetup.ram_override("lots")


def test_the_shortcut(windows):
    """songcharter.lnk in the user's Start-menu folder: cmd.exe running the launcher in this distro, in the profile
    folder, with wsl.exe's icon; written again over itself."""
    LnkParse3 = pytest.importorskip("LnkParse3")
    w = windows
    out, said, _ = apply(w)
    lnk = w.programs / "songcharter.lnk"
    assert out["shortcut"] == lnk
    with open(lnk, "rb") as f:
        j = LnkParse3.lnk_file(f).get_json()
    assert j["data"] == {"description": "songcharter", "working_directory": "C:\\Users\\Jörg",
                         "command_line_arguments": '/c "wsl.exe -d Ubuntu-26.04 --cd ~ -e '
                                                   '/home/jorg/.local/bin/songcharter ui --from-shortcut || pause"',
                         "icon_location": "C:\\WINDOWS\\System32\\wsl.exe"}
    assert j["extra"]["ENVIRONMENTAL_VARIABLES_LOCATION_BLOCK"]["target_unicode"] == "%windir%\\System32\\cmd.exe"
    apply(w)
    assert sorted(p.name for p in w.programs.iterdir()) == ["songcharter.lnk"]
    side = wslsetup.windows_side()
    assert side["shortcut"] == lnk and side["wslconfig"] == w.config and side["backups"] == []


def test_interop_off_and_plain_linux(windows, monkeypatch):
    """With no interop nothing is written on Windows, and the fallback is said (the memory decision then rests on
    WSL's own memory: 7.8 GiB, so allin1 is left out); on plain Linux nothing happens at all."""
    w = windows
    w.cfg["interop"] = False
    w.write()
    out, said, _ = apply(w)
    assert not out["changed"] and out["shortcut"] is None and not w.config.exists()
    assert any("Windows interop is off" in s and "set it by hand" in s for s in said), said
    assert any("no Start-menu shortcut" in s and "type songcharter" in s for s in said), said
    assert not out["allin1"] and allin1(w) is None
    monkeypatch.delenv("WSL_DISTRO_NAME")
    monkeypatch.setattr(wsl, "OSRELEASE", w.home / "no-such-file")
    out, said, _ = apply(w)
    assert said == ["not WSL: nothing to do on the Windows side"] and not out["changed"]


def test_set_allin1_without_a_runtime_json(tmp_path):
    assert runtime.set_allin1(tmp_path, False) is False
