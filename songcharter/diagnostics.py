"""The diagnostics bundle: one zip that explains what went wrong, with no audio (M4-06, DESIGN.md 4.5).

    path = diagnostics.bundle(home, out)    # `songcharter diagnostics --out PATH`; the page's GET /api/diagnostics

**What it holds** ($SONGCHARTER_HOME's files under their own names):
  * doctor.json (the install's), runtime/runtime.json and ui.json;
  * logs/: the newest LOGS (10) of logs/*.log;
  * doctor-now.json: a fresh device.report(full=False) (its error, when it fails);
  * clonehero.json: the Songs folder as the page sees it (clonehero.describe: folder, windows_path, source,
    under_onedrive) and doctor.json's wsl.documents (the registry's raw value, its expansion and the Linux path), so a
    localized folder name decoded with the wrong code page shows up as mojibake here;
  * work/<work folder>/ for the newest WORK_FOLDERS (5) work folders in the cache (cache.cache_root()/work, by their
    marker's last use): pipeline.json (with the memory samples and the fallbacks), assemble.json, the marker
    (songcharter-work.json), preview.json (pipeline.json's preview: its flags, remarks or why there is none) and the
    built folder's report.json (pipeline.json's assemble.folder: the song folder or its .failed);
  * feedback.json (M8-14): every chart's rating and marked spots from the page (ui/feedback.py,
    <home>/state/feedback), each with its chart as it is now, its report.json's `pipeline` among it (the seeds,
    takes, devices, fallbacks and engines), and with each spot the chart's Expert guitar notes from 10 s before it to
    10 s after (`around`: numbers only, with the chart's resolution and tempo markers there; capped a spot and a
    file), read from its notes.chart here, so a bad spot can be looked at where the chart cannot be made again (the
    gate advisor's 3: another GPU need not give the same takes); the chart named by its library id, no path. A
    spot's note is the player's own words, as he wrote them. Left out when no chart has a rating or a spot (the
    manifest says so). Over MAX_BYTES, it goes without the notes around the spots (each `around` says why), and the
    manifest says so; still over, it stays out, and the manifest says where the ratings are kept (the gate review's
    F2);
  * MANIFEST.txt: every file with its size and where it came from, then every file left out and why.

**Never** (`refused`, each candidate checked by its name, its size and its first bytes, the files made here too): an audio extension or audio
magic bytes (packaging/ci/check_no_audio.py's test, copied here since that script is not part of the package), a
notes.chart (it holds the lyrics: feedback.json's notes are numbers read from it, never its text), a stem, a picture (PNG, JPEG or WebP by its extension or its first bytes: the
previews, and the album art and backgrounds of M4-11, which may be a person's photo), or any file over MAX_BYTES
(5 MB). Only the files above are ever
picked, so the songs, stems, decodes, previews and charts in the home and the cache are never looked at. The lyrics a
person pasted reach only notes.chart: pipeline.json, assemble.json and report.json count them, never hold a word.
"""
from __future__ import annotations

import json
import os
import secrets
import time
import zipfile
from pathlib import Path
from typing import Any, Callable

from . import __version__, cache, clonehero

LOGS = 10                      # the newest logs
WORK_FOLDERS = 5               # the newest work folders
MAX_BYTES = 5 * 10 ** 6        # 5 MB (10^6 bytes, the project's unit): a file over this stays out
HEAD = 512
# packaging/ci/check_no_audio.py's AUDIO_EXTENSIONS and magic_reason (tests/test_diagnostics.py checks they agree)
AUDIO_EXTENSIONS = {".wav", ".mp3", ".ogg", ".flac", ".m4a", ".opus", ".aac", ".wma", ".aif", ".aiff"}
MAGIC = {b"RIFF": "a RIFF header (WAV)", b"OggS": "an Ogg header", b"ID3": "an ID3 tag (MP3)",
         b"fLaC": "a FLAC header", b"\x1a\x45\xdf\xa3": "a Matroska header (WebM, MKA)"}
NEVER_SUFFIXES = {".png": "a picture (PNG)", ".jpg": "a picture (JPEG)", ".jpeg": "a picture (JPEG)",
                  ".webp": "a picture (WebP)", ".chart": "a chart (notes.chart holds the lyrics)",
                  ".mid": "a chart (MIDI)"}
PICTURE_MAGIC = {b"\x89PNG": "a PNG header", b"\xff\xd8\xff": "a JPEG header"}   # WebP is RIFF: refused as audio
WORK_FILES = ("pipeline.json", "assemble.json", cache.MARKER)
PREVIEW_KEYS = ("ok", "flags", "flags_by_kind", "remarks", "pages", "skipped", "error")


def magic_reason(head: bytes) -> str | None:
    """Why bytes starting with `head` are audio, or None (check_no_audio.py's test)."""
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


def refused(name: str, data: bytes | None = None, size: int | None = None) -> str | None:
    """Why a file named `name`, `size` bytes, starting with `data`, may not go into the bundle; None when it may. A
    stem is audio (a WAV) by its name and its bytes."""
    lower = name.lower()
    suffix = os.path.splitext(lower)[1]
    if suffix in AUDIO_EXTENSIONS:
        return f"an audio extension ({suffix})"
    if suffix in NEVER_SUFFIXES:
        return NEVER_SUFFIXES[suffix]
    if size is not None and size > MAX_BYTES:
        return f"{size} bytes, over {MAX_BYTES}"
    if data is not None:
        why = magic_reason(data[:HEAD])
        if why is not None:
            return f"audio: it {why}"
        why = next((what for magic, what in PICTURE_MAGIC.items() if data.startswith(magic)), None)
        if why is not None:
            return f"a picture: it starts with {why}"
    return None


class Bundle:
    """The zip being made: each file checked (`refused`) as it goes in, and the manifest's lines."""

    def __init__(self, z: zipfile.ZipFile):
        self.z = z
        self.added: list[tuple[str, int, str]] = []    # name in the zip, bytes, where from
        self.left: list[tuple[str, str]] = []          # where from, why not

    def file(self, arcname: str, path: Path) -> bool:
        """`path` into the zip as `arcname`, when it exists and passes; whether it went in."""
        try:
            size = path.stat().st_size
        except OSError as e:
            if not isinstance(e, FileNotFoundError):
                self.left.append((str(path), f"unreadable ({e.strerror or type(e).__name__})"))
            return False
        why = refused(path.name, None, size)
        if why is None:
            try:
                data = path.read_bytes()
            except OSError as e:
                why = f"unreadable ({e.strerror or type(e).__name__})"
            else:
                why = refused(path.name, data, len(data))
        if why is not None:
            self.left.append((str(path), why))
            return False
        self.z.writestr(arcname, data)
        self.added.append((arcname, len(data), str(path)))
        return True

    def json(self, arcname: str, value: Any, source: str) -> bool:
        """`value` as JSON into the zip as `arcname`, when it passes `refused` as a file would (its name, size and
        first bytes: M8-14, the made files under the same guard); whether it went in."""
        data = (json.dumps(value, indent=1, ensure_ascii=False, default=str) + "\n").encode("utf-8")
        why = refused(arcname, data, len(data))
        if why is not None:
            self.left.append((source, why))
            return False
        self.z.writestr(arcname, data)
        self.added.append((arcname, len(data), source))
        return True


def newest_logs(home: Path, n: int = LOGS) -> list[Path]:
    """The newest `n` of $SONGCHARTER_HOME/logs/*.log, newest first."""
    def mtime(p: Path) -> float:
        try:
            return p.stat().st_mtime
        except OSError:
            return 0.0
    try:
        logs = [p for p in (Path(home) / "logs").glob("*.log") if p.is_file()]
    except OSError:
        return []
    return sorted(logs, key=lambda p: (mtime(p), p.name), reverse=True)[:n]


def newest_work_folders(root: Path, n: int = WORK_FOLDERS) -> list[Path]:
    """The newest `n` work folders in the cache `root` (root/work/*, those with our marker), by the marker's last
    use, newest first."""
    found = []
    try:
        entries = list((Path(root) / "work").iterdir())
    except OSError:
        return []
    for p in entries:
        marker = cache.read_marker(p) if p.is_dir() else None
        if marker is not None:
            used = marker.get("used")
            found.append((used if isinstance(used, (int, float)) else 0.0, p.name, p))
    return [p for _, _, p in sorted(found, reverse=True)[:n]]


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _feedback(home: Path) -> dict:
    """feedback.json (the module docstring): ui/feedback.py's record of every chart rated, with the library's own
    lookup of each chart by its id."""
    from .ui import feedback, jobs
    return feedback.for_diagnostics(home, jobs.find_chart)


# the manifest's closing line, by whether feedback.json went in (bundle's `fed`)
FED_LINES = {
    "whole": "feedback.json holds each chart's rating and marked spots, with the guitar's notes around each spot as "
             "numbers (no word of the chart); a spot's note is the player's own words, as he wrote them.",
    "short": "feedback.json holds each chart's rating and marked spots, without the guitar's notes around them: with "
             "them it would be over {mb}; a spot's note is the player's own words, as he wrote them.",
    "none": "The ratings and marked spots are not in this zip: feedback.json would be over {mb} even without the "
            "notes around the spots. They are kept in the state/feedback folder of songcharter's home (above).",
    "nothing": "No chart has a rating or a marked spot yet, so there is no feedback.json."}


def without_notes(rated: dict) -> dict:
    """feedback.json without the guitar's notes: each spot's `around` only says why (a file over MAX_BYTES)."""
    why = {"why": f"left out: the file would be over {MAX_BYTES / 10 ** 6:g} MB"}
    return {**rated, "charts": [{**c, "spots": [{**x, "around": why} for x in c.get("spots") or []]}
                                for c in rated.get("charts") or []]}


def _quick_report() -> dict:
    from . import device
    return device.report(full=False)


def bundle(home: Path | str, out: Path | str, *, report: Callable[[], dict] | None = None,
           cache_root: Path | None = None, clonehero_info: Callable[[Path], dict] | None = None,
           now: float | None = None) -> Path:
    """Write the diagnostics zip to `out` (through a .part file); the path. `report`, `cache_root` and
    `clonehero_info` stand in for device.report(full=False), cache.cache_root() and clonehero.describe (the
    server passes its own; tests theirs)."""
    report = report or _quick_report
    clonehero_info = clonehero_info or clonehero.describe
    home, out = Path(home), Path(out)
    root = Path(cache_root) if cache_root is not None else cache.cache_root().expanduser()
    out.parent.mkdir(parents=True, exist_ok=True)
    part = out.with_name(f".{out.name}.{secrets.token_hex(4)}.part")
    made = time.strftime("%Y-%m-%d %H:%M:%S %z", time.localtime(time.time() if now is None else now))
    try:
        with zipfile.ZipFile(part, "w", compression=zipfile.ZIP_DEFLATED) as z:
            b = Bundle(z)
            for name in ("doctor.json", "runtime/runtime.json", clonehero.UI_FILE):
                b.file(name, home / name)
            for log in newest_logs(home):
                b.file(f"logs/{log.name}", log)
            try:
                now_report = report()
            except Exception as e:  # noqa: BLE001  the bundle says so; it is wanted most when things are broken
                now_report = {"error": f"{type(e).__name__}: {e}"}
            b.json("doctor-now.json", now_report, "device.report(full=False), now")
            try:
                ch = clonehero_info(home)
            except Exception as e:  # noqa: BLE001
                ch = {"error": f"{type(e).__name__}: {e}"}
            doctor = _read_json(home / "doctor.json")
            documents = ((doctor or {}).get("wsl") or {}).get("documents") if isinstance(doctor, dict) else None
            ch = {k: v for k, v in ch.items() if k != "guess"} | {"documents": documents}
            b.json("clonehero.json", ch, "clonehero.describe and doctor.json's wsl.documents")
            for work in newest_work_folders(root):
                where = f"work/{work.name}"
                for name in WORK_FILES:
                    b.file(f"{where}/{name}", work / name)
                pipeline = _read_json(work / "pipeline.json")
                if not isinstance(pipeline, dict):
                    continue
                pv = pipeline.get("preview")
                if isinstance(pv, dict):
                    b.json(f"{where}/preview.json", {k: pv[k] for k in PREVIEW_KEYS if k in pv},
                           f"{work / 'pipeline.json'}'s preview")
                built = (pipeline.get("assemble") or {}).get("folder")
                if isinstance(built, str) and built:
                    b.file(f"{where}/report.json", Path(built) / "report.json")
            try:
                rated = _feedback(home)
            except Exception as e:  # noqa: BLE001  the rest of the bundle goes all the same
                rated = {"error": f"{type(e).__name__}: {e}"}
            fed = None   # feedback.json: None (nothing to send), "whole", "short" (without the notes), or "none"
            if rated.get("charts") or "error" in rated:
                source = "the page's ratings and marked spots (state/feedback), with each chart's report.json pipeline"
                fed = "whole" if b.json("feedback.json", rated, source) else "none"
                if fed == "none" and b.left and b.left[-1][1].endswith(f"over {MAX_BYTES}"):   # too big: without
                    # the notes around the spots, so the ratings still come (the gate review's F2)
                    fed = "short" if b.json("feedback.json", without_notes(rated), f"{source}, without the notes "
                                            "around the spots") else "none"
            lines = [f"songcharter {__version__} diagnostics, made {made}", f"home: {home}", f"cache: {root}",
                     "", "files (bytes, from):"]
            lines += [f"  {name}  {size}  {src}" for name, size, src in b.added]
            lines += ["", "left out (why):"] + ([f"  {src}: {why}" for src, why in b.left] or ["  nothing"])
            lines += ["", "Never in this file: audio, stems, charts (notes.chart), pictures, or a file over "
                          f"{MAX_BYTES // 10 ** 6} MB.",
                      FED_LINES[fed or "nothing"].format(mb=f"{MAX_BYTES / 10 ** 6:g} MB")]
            z.writestr("MANIFEST.txt", "\n".join(lines) + "\n")
        os.replace(part, out)
    finally:
        part.unlink(missing_ok=True)
    return out
