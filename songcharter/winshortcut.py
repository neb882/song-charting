"""A Windows shortcut (.lnk) written from WSL, for the Start menu (M4-03). Standard library only: the Windows CI job
imports it with no third-party package.

    winshortcut.write(path, target=r"%windir%\\System32\\cmd.exe", arguments='/c "wsl.exe ... || pause"',
                      working_dir=r"C:\\Users\\Jörg", icon=r"C:\\WINDOWS\\System32\\wsl.exe", description="songcharter")

  * **The structure** is [MS-SHLLINK]'s smallest that Windows launches: a ShellLinkHeader with the flags HasName,
    HasWorkingDir, HasArguments, HasIconLocation, IsUnicode and HasExpString; no LinkTargetIDList and no LinkInfo;
    StringData (the description, the working folder, the arguments and the icon, in UTF-16LE); an
    EnvironmentVariableDataBlock holding the target with its %VARIABLES% (in ANSI and in Unicode), which Windows
    expands when it starts the link; then the terminal block. HasName is there for the description.
  * **Why a .lnk.** It is no script file. Written from WSL it carries no Mark of the Web, so Smart App Control's list
    of risky file types, which applies only to files from an untrusted origin, does not touch it; its target cmd.exe,
    and the wsl.exe it starts, are signed by Microsoft [doc: textslashplain.com, 2026-04-28; inference for this case].
  * **A reinstall** writes the file again in place: through `<name>.part` and os.replace (tried again for a second
    while Windows holds the old link open), so a shortcut is never half written.
"""
from __future__ import annotations

import os
import struct
import time
from pathlib import Path

LINK_CLSID = bytes.fromhex("0114020000000000c000000000000046")   # 00021401-0000-0000-C000-000000000046
HAS_NAME, HAS_WORKING_DIR, HAS_ARGUMENTS, HAS_ICON_LOCATION = 0x04, 0x10, 0x20, 0x40
IS_UNICODE, HAS_EXP_STRING = 0x80, 0x200
FLAGS = HAS_NAME | HAS_WORKING_DIR | HAS_ARGUMENTS | HAS_ICON_LOCATION | IS_UNICODE | HAS_EXP_STRING
FILE_ATTRIBUTE_NORMAL = 0x80
SW_SHOWNORMAL = 1
ENVIRONMENT_BLOCK = 0xA0000001    # EnvironmentVariableDataBlock's signature; 0x314 bytes long
ENVIRONMENT_BLOCK_SIZE = 0x314
TARGET_ANSI_BYTES, TARGET_UNICODE_BYTES = 260, 520   # MAX_PATH characters, NUL included
STRING_MAX = 0xFFFF               # a StringData's count of UTF-16 code units is 16 bits
REPLACE_TRIES = 5


def _string(text: str) -> bytes:
    """A StringData: its length in UTF-16 code units, then the text in UTF-16LE, with no NUL."""
    data = text.encode("utf-16-le")
    if len(data) // 2 > STRING_MAX:
        raise ValueError(f"a shortcut string holds at most {STRING_MAX} characters, not {len(data) // 2}")
    return struct.pack("<H", len(data) // 2) + data


def _environment_block(target: str) -> bytes:
    """The EnvironmentVariableDataBlock: the target (with its %VARIABLES%) as ANSI and as Unicode, each
    NUL-terminated and padded with NULs."""
    ansi, wide = target.encode("ascii") + b"\0", target.encode("utf-16-le") + b"\0\0"
    if len(ansi) > TARGET_ANSI_BYTES or len(wide) > TARGET_UNICODE_BYTES:
        raise ValueError(f"a shortcut's target holds at most {TARGET_ANSI_BYTES - 1} characters: {target!r}")
    block = (struct.pack("<II", ENVIRONMENT_BLOCK_SIZE, ENVIRONMENT_BLOCK) + ansi.ljust(TARGET_ANSI_BYTES, b"\0")
             + wide.ljust(TARGET_UNICODE_BYTES, b"\0"))
    assert len(block) == ENVIRONMENT_BLOCK_SIZE
    return block


def build(target: str, arguments: str, working_dir: str, icon: str, description: str, icon_index: int = 0) -> bytes:
    """The .lnk's bytes. `target` is ASCII (a path such as %windir%\\System32\\cmd.exe, whose variables Windows
    expands); the other strings are any Unicode."""
    header = struct.pack("<I16sII8s8s8sIiIHHII", 0x4C, LINK_CLSID, FLAGS, FILE_ATTRIBUTE_NORMAL, b"\0" * 8, b"\0" * 8,
                         b"\0" * 8, 0, icon_index, SW_SHOWNORMAL, 0, 0, 0, 0)
    assert len(header) == 0x4C
    strings = b"".join(_string(s) for s in (description, working_dir, arguments, icon))   # [MS-SHLLINK]'s order
    return header + strings + _environment_block(target) + struct.pack("<I", 0)   # the terminal block


def write(path: Path | str, target: str, arguments: str, working_dir: str, icon: str,
          description: str = "songcharter", icon_index: int = 0) -> Path:
    """Write the shortcut to `path` (replacing one there), through path.part and os.replace."""
    path = Path(path)
    data = build(target, arguments, working_dir, icon, description, icon_index)
    part = path.with_name(path.name + ".part")
    part.write_bytes(data)
    for attempt in range(REPLACE_TRIES):
        try:
            os.replace(part, path)
            return path
        except PermissionError:   # Windows: the old link open for a moment (the Start menu, an indexer)
            if attempt == REPLACE_TRIES - 1:
                part.unlink(missing_ok=True)
                raise
            time.sleep(0.2)
    return path
