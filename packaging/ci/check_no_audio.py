#!/usr/bin/env python3
"""check_no_audio.py: fail when a folder or a file (an archive) holds audio, before CI uploads it as an artifact, or
before a release, a diagnostics bundle or a tarball ships it.

    python packaging/ci/check_no_audio.py PATH [PATH ...]

A PATH is a folder, whose every file counts, at any depth and through symlinked folders too (the artifact upload follows
them), or a single file. A file is audio when:
- its extension is one of AUDIO_EXTENSIONS (any case);
- or its first bytes are an audio header, whatever its name: RIFF (WAV), FORM...AIFF/AIFC, Ogg, ID3, FLAC, an MP4
  `ftyp` box at offset 4 (M4A, MP4, and also HEIC and AVIF images), Matroska (WebM, MKA), or the 11-bit MPEG frame sync
  (FF Ex), which also matches an ADTS AAC stream, and a UTF-16 text file with its byte-order mark (FF FE): write
  artifacts as UTF-8.
- An archive is opened by its first bytes, not its name: zip, tar, and gzip, xz or bzip2, around a tar or around a
  single file. Each member gets the same test (its name and its first bytes), and an archive inside an archive is
  opened too, to MAX_DEPTH levels. A deeper archive, or one that cannot be read (corrupt, encrypted), counts as a
  failure: what cannot be checked is not passed.

Exit 0: no audio. Exit 1: each audio file or member (`archive!member`), or unreadable file, listed with the reason.
Exit 2: PATH does not exist. Standard library only, so any Python runs it.
"""
from __future__ import annotations

import bz2
import gzip
import lzma
import os
import shutil
import sys
import tarfile
import tempfile
import zipfile
from pathlib import Path

AUDIO_EXTENSIONS = {".wav", ".mp3", ".ogg", ".flac", ".m4a", ".opus", ".aac", ".wma", ".aif", ".aiff"}
MAGIC = {b"RIFF": "a RIFF header (WAV)", b"OggS": "an Ogg header", b"ID3": "an ID3 tag (MP3)",
         b"fLaC": "a FLAC header", b"\x1a\x45\xdf\xa3": "a Matroska header (WebM, MKA)"}
HEAD = 512                    # enough for every header here, and for tar's `ustar` at offset 257
MAX_DEPTH = 4                 # archives inside archives
SPOOL_BYTES = 64 << 20        # a nested archive is copied out to be opened: in memory up to this, then to a temp file
DECOMPRESS = {"gzip": lambda f: gzip.GzipFile(fileobj=f, mode="rb"),   # the mode, or it follows f's (w+b)
              "xz": lambda f: lzma.LZMAFile(f, "rb"), "bzip2": lambda f: bz2.BZ2File(f, "rb")}
COMPRESSED_SUFFIXES = {".gz": "", ".tgz": ".tar", ".xz": "", ".txz": ".tar", ".bz2": "", ".tbz2": ".tar"}


def name_reason(name: str) -> str | None:
    suffix = os.path.splitext(name.rstrip("/"))[1]
    return f"an audio extension ({suffix})" if suffix.lower() in AUDIO_EXTENSIONS else None


def magic_reason(head: bytes) -> str | None:
    """Why bytes starting with `head` are audio, or None."""
    for magic, what in MAGIC.items():
        if head.startswith(magic):
            return f"starts with {what}"
    if head[:4] == b"FORM" and head[8:12] in (b"AIFF", b"AIFC"):
        return "starts with an AIFF header"
    if head[4:8] == b"ftyp":
        return "starts with an MP4 header (ftyp: M4A, MP4)"
    if len(head) >= 2 and head[0] == 0xFF and head[1] & 0xE0 == 0xE0:
        return f"starts with an MPEG frame sync ({head[:2].hex(' ').upper()})"
    return None


def archive_kind(head: bytes) -> str | None:
    """The kind of archive (or compressed stream) that bytes starting with `head` are, or None."""
    if head[:4] in (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08"):
        return "zip"
    if head[257:262] == b"ustar":
        return "tar"
    if head[:2] == b"\x1f\x8b":
        return "gzip"
    if head[:6] == b"\xfd7zXZ\x00":
        return "xz"
    if head[:3] == b"BZh":
        return "bzip2"
    return None


class Checker:
    def __init__(self):
        self.bad: list[str] = []
        self.files = 0
        self.members = 0

    def path(self, path: Path) -> None:
        """One file on disk."""
        self.files += 1
        reason = name_reason(path.name)
        if reason:
            self.bad.append(f"{path}: {reason}")
            return
        try:
            with open(path, "rb") as f:
                self.content(str(path), path.name, f.read(HEAD), f, 1)
        except OSError as e:
            self.bad.append(f"{path}: cannot be read, so cannot be checked ({e.strerror or e})")

    def content(self, label: str, name: str, head: bytes, f, depth: int) -> None:
        """A file whose name was checked: its first bytes, then, for an archive, its members. `f` is seekable."""
        reason = magic_reason(head)
        if reason:
            self.bad.append(f"{label}: {reason}")
            return
        kind = archive_kind(head)
        if kind is None:
            return
        if depth > MAX_DEPTH:
            self.bad.append(f"{label}: a {kind} archive nested deeper than {MAX_DEPTH} levels, so not checked")
            return
        try:
            if kind == "zip":
                self.zip(label, f, depth)
            elif kind == "tar":
                self.tar(label, f, depth)
            else:
                self.compressed(label, name, kind, f, depth)
        except (zipfile.BadZipFile, tarfile.TarError, lzma.LZMAError, EOFError, OSError, RuntimeError, ValueError,
                NotImplementedError) as e:
            self.bad.append(f"{label}: a {kind} archive that cannot be read, so cannot be checked ({e})")

    def member(self, label: str, name: str, open_member, depth: int) -> None:
        """One member of an archive: its name, then its first bytes; a member that is an archive is copied out (to
        be seekable) and opened in turn."""
        self.members += 1
        reason = name_reason(name)
        if reason:
            self.bad.append(f"{label}: {reason}")
            return
        with open_member() as m:
            head = m.read(HEAD)
        if magic_reason(head) or archive_kind(head) is None:
            self.content(label, name, head, None, depth + 1)
            return
        with tempfile.SpooledTemporaryFile(max_size=SPOOL_BYTES) as spool:
            with open_member() as m:
                shutil.copyfileobj(m, spool)
            self.content(label, name, head, spool, depth + 1)

    def zip(self, label: str, f, depth: int) -> None:
        f.seek(0)
        with zipfile.ZipFile(f) as z:
            for info in z.infolist():
                if not info.is_dir():
                    self.member(f"{label}!{info.filename}", info.filename, lambda i=info: z.open(i), depth)

    def tar(self, label: str, f, depth: int) -> None:
        f.seek(0)
        with tarfile.open(fileobj=f, mode="r:*") as t:
            for m in t:
                if m.isdir():
                    continue
                if m.isfile():
                    self.member(f"{label}!{m.name}", m.name, lambda m=m: t.extractfile(m), depth)
                else:                             # a link or a device: only its name (a link's data is another member's)
                    self.members += 1
                    reason = name_reason(m.name)
                    if reason:
                        self.bad.append(f"{label}!{m.name}: {reason}")

    def compressed(self, label: str, name: str, kind: str, f, depth: int) -> None:
        """gzip, xz or bzip2: around a tar (opened as one), or around a single file, named by the outer name less its
        compression suffix."""
        def opened():
            f.seek(0)
            return DECOMPRESS[kind](f)
        with opened() as d:
            head = d.read(HEAD)
        if head[257:262] == b"ustar":
            self.tar(label, f, depth)
            return
        stem, suffix = os.path.splitext(name)
        inner = stem + COMPRESSED_SUFFIXES[suffix.lower()] if suffix.lower() in COMPRESSED_SUFFIXES else name
        self.member(f"{label}!{inner}", inner, opened, depth)


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
        print("usage: check_no_audio.py PATH [PATH ...]", file=sys.stderr)
        return 2
    missing = [arg for arg in argv if not os.path.lexists(arg)]
    if missing:
        print(f"check_no_audio: no such file or folder: {', '.join(missing)}", file=sys.stderr)
        return 2
    c = Checker()
    for arg in argv:
        if Path(arg).is_dir():
            for path in files_under(Path(arg)):
                c.path(path)
        else:
            c.path(Path(arg))
    counted = f"{c.files} files" + (f" and {c.members} archive members" if c.members else "")
    if c.bad:
        print(f"check_no_audio: FAIL, {len(c.bad)} found in {counted}:", *(f"  {b}" for b in c.bad), sep="\n")
        return 1
    print(f"check_no_audio: ok, {counted}, no audio ({', '.join(argv)})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
