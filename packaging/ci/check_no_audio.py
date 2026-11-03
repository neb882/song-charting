#!/usr/bin/env python3
"""check_no_audio.py: fail when a folder holds audio, before CI uploads it as an artifact (or ships it).

    python packaging/ci/check_no_audio.py FOLDER [FOLDER ...]

Every file under each FOLDER counts, at any depth, through symlinked folders too (the artifact upload follows them).
A file is audio when its extension is one of AUDIO_EXTENSIONS (any case), or when its first bytes are a RIFF, Ogg, ID3,
FLAC or MPEG-frame header, whatever its name. The MPEG test is the 11-bit frame sync (FF Ex), which also matches an
ADTS AAC stream, and a UTF-16 text file with its byte-order mark (FF FE): write artifacts as UTF-8.

Exit 0: no audio. Exit 1: each audio file (or unreadable file) listed with the reason. Exit 2: FOLDER is not a folder.
Standard library only, so any Python runs it.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

AUDIO_EXTENSIONS = {".wav", ".mp3", ".ogg", ".flac", ".m4a", ".opus", ".aac", ".wma", ".aif", ".aiff"}
MAGIC = {b"RIFF": "a RIFF header (WAV)", b"OggS": "an Ogg header", b"ID3": "an ID3 tag (MP3)", b"fLaC": "a FLAC header"}


def audio_reason(path: Path) -> str | None:
    """Why the file at `path` counts as audio, or None when it does not."""
    if path.suffix.lower() in AUDIO_EXTENSIONS:
        return f"an audio extension ({path.suffix})"
    try:
        with open(path, "rb") as f:
            head = f.read(4)
    except OSError as e:
        return f"cannot be read, so cannot be checked ({e.strerror or e})"
    for magic, what in MAGIC.items():
        if head.startswith(magic):
            return f"starts with {what}"
    if len(head) >= 2 and head[0] == 0xFF and head[1] & 0xE0 == 0xE0:
        return f"starts with an MPEG frame sync ({head[:2].hex(' ').upper()})"
    return None


def files_under(folder: Path):
    """Every file under `folder`, following symlinked folders once each (a link loop is not walked twice)."""
    seen = set()
    for top, dirs, files in os.walk(folder, followlinks=True):
        st = os.stat(top)
        if (st.st_dev, st.st_ino) in seen:
            dirs[:] = []
            continue
        seen.add((st.st_dev, st.st_ino))
        dirs.sort()
        for name in sorted(files):
            yield Path(top) / name


def main(argv: list[str]) -> int:
    if argv in (["-h"], ["--help"]):
        print(__doc__.strip())
        return 0
    if not argv:
        print("usage: check_no_audio.py FOLDER [FOLDER ...]", file=sys.stderr)
        return 2
    bad, count = [], 0
    for arg in argv:
        folder = Path(arg)
        if not folder.is_dir():
            print(f"check_no_audio: {arg} is not a folder", file=sys.stderr)
            return 2
        for path in files_under(folder):
            count += 1
            reason = audio_reason(path)
            if reason:
                bad.append(f"{path}: {reason}")
    if bad:
        print(f"check_no_audio: FAIL, {len(bad)} of {count} files:", *(f"  {b}" for b in bad), sep="\n")
        return 1
    print(f"check_no_audio: ok, {count} files, no audio ({', '.join(argv)})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
