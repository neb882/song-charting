"""The Start-menu shortcut's writer (songcharter.winshortcut): a .lnk read back by LnkParse3 (a parser of
[MS-SHLLINK], MIT) gives the target, arguments, working folder, icon and description exactly. Standard library and
LnkParse3 only, so the Windows CI hook (windows.d/30-shortcut.ps1) runs this file too; there Windows itself also
launches a written link."""
import struct

import pytest

from songcharter import winshortcut as W

TARGET = r"%windir%\System32\cmd.exe"
ARGS = '/c "wsl.exe -d Ubuntu-26.04 --cd ~ -e /home/jörg/.local/bin/songcharter ui --from-shortcut || pause"'
WORKDIR = r"C:\Users\Jörg"
ICON = r"C:\WINDOWS\System32\wsl.exe"


def parse(path):
    LnkParse3 = pytest.importorskip("LnkParse3")
    with open(path, "rb") as f:
        return LnkParse3.lnk_file(f).get_json()


def test_a_written_link_reads_back_exactly(tmp_path):
    path = W.write(tmp_path / "songcharter.lnk", TARGET, ARGS, WORKDIR, ICON)
    j = parse(path)
    assert j["header"]["guid"] == "00021401-0000-0000-C000-000000000046"
    assert set(j["header"]["link_flags"]) == {"HasName", "HasWorkingDir", "HasArguments", "HasIconLocation",
                                              "IsUnicode", "HasExpString"}
    assert j["header"]["icon_index"] == 0 and j["header"]["windowstyle"] == "SW_SHOWNORMAL"
    assert j["link_info"] == {}   # no LinkInfo, and no ID list: the environment block is the target
    assert j["data"] == {"description": "songcharter", "working_directory": WORKDIR,
                         "command_line_arguments": ARGS, "icon_location": ICON}
    env = j["extra"]["ENVIRONMENTAL_VARIABLES_LOCATION_BLOCK"]
    assert (env["target_ansi"], env["target_unicode"], env["size"]) == (TARGET, TARGET, 0x314)


def test_the_bytes_follow_ms_shllink(tmp_path):
    """The header's size and CLSID, the flags, a StringData's count in UTF-16 code units (an emoji counts two), the
    environment block's fixed size and the terminal block."""
    data = W.build(TARGET, "/c echo 🎸", "C:\\", ICON, "songcharter")
    assert struct.unpack_from("<I", data)[0] == 0x4C and data[4:20] == W.LINK_CLSID
    assert struct.unpack_from("<I", data, 20)[0] == 0x2F4
    strings = data[0x4C:]
    n = struct.unpack_from("<H", strings)[0]
    assert strings[2:2 + 2 * n].decode("utf-16-le") == "songcharter"
    assert "/c echo 🎸".encode("utf-16-le") in data and struct.pack("<H", 10) + "/c echo 🎸".encode("utf-16-le") in data
    assert data[-4:] == b"\0\0\0\0"
    assert struct.unpack_from("<II", data, len(data) - 4 - 0x314) == (0x314, 0xA0000001)


def test_a_reinstall_writes_over_the_old_link(tmp_path):
    path = tmp_path / "songcharter.lnk"
    W.write(path, TARGET, "/c old", WORKDIR, ICON)
    W.write(path, TARGET, ARGS, WORKDIR, ICON)
    assert parse(path)["data"]["command_line_arguments"] == ARGS
    assert sorted(p.name for p in tmp_path.iterdir()) == ["songcharter.lnk"]   # no .part left


def test_what_a_link_cannot_hold():
    with pytest.raises(UnicodeEncodeError):
        W.build("%windir%\\Jörg\\cmd.exe", "", "", "", "x")   # the target is ANSI: ASCII only
    with pytest.raises(ValueError, match="at most 259"):
        W.build("C:\\" + "x" * 300, "", "", "", "x")
    with pytest.raises(ValueError, match="at most 65535"):
        W.build(TARGET, "x" * 70000, "", "", "x")
