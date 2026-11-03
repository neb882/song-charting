"""The per-user cache: the pipeline's work folders (DESIGN.md 9, Q30) and, apart from them, the downloaded weights.

    <cache>/work/<name>-<key>/   one song's work folder (pipeline.py): the decode, the stems, every engine's folder
    <cache>/ac/<key[:8]>/        autochart's own scratch folder for that song (its engine-cache and jobs; see below)
    <models>/adtof/...           the drums engine's weights (engines/adtof.py models_dir(): <user cache>/models, or
                                 $SONGCHARTER_MODELS)

  * **<cache>** is %LOCALAPPDATA%\\songcharter on Windows and $XDG_CACHE_HOME/songcharter (else ~/.cache/songcharter)
    elsewhere (`user_cache`, shared with models_dir()); $SONGCHARTER_CACHE puts the work and scratch folders
    somewhere else (`cache_root`) and leaves the weights where they are.
  * **Why not beside the output.** The first default was <out>.work. With --out inside Clone Hero's Songs folder,
    Clone Hero scans it recursively and would list autochart's take folders, which are whole song folders
    (notes.chart, song.ini, song.ogg), as songs. The cache is outside every Songs folder; `--work DIR` still puts
    the work folder anywhere, as before.
  * **<key>** is the first 16 hex characters of the song file's SHA-256 (`file_key`), so the same file reuses its
    caches whatever --out is. **<name>** is the file's stem made safe for Windows (`safe_name`), so a person can
    tell the folders apart.
  * **Path length.** Windows refuses a path of more than 259 characters (MAX_PATH less its NUL) unless long paths
    are turned on, which nothing here can assume. The deepest paths a run creates (`DEEPEST`, with Windows
    separators):
      - in the work folder, a take's report: guitar\\seed_20260609\\autochart_run\\expert_full_song_report.json
        (63 characters);
      - in autochart's scratch folder, its separation's mel tables: engine-cache\\features\\fretformer_demucs_v1\\
        <64 hex>\\demucs_default\\stems_htdemucs_6s\\audio_<26 hex>\\mel-tables.bin (188: our driver's engine-cache
        layout, and the engine's own stem folder name, which it cuts to 32 characters on Windows).
    Inside the work folder, as <work>\\guitar\\work, that scratch would run to 319 characters with a profile of
    C:\\Users\\<20 characters>\\AppData\\Local and a 40-character name. In <cache>\\ac\\<8 hex> the deepest path
    there is 256 characters, and the work folder's 182.
  * **Pruning** (`prune`, after each run): the least recently used work folders under <cache>/work go, with their
    scratch folders, until the rest total at most 5 GB (10^9 bytes; $SONGCHARTER_CACHE_GB sets another budget).
    Only folders that carry our MARKER count or go. Never the current run's, never one used in the last 24 hours
    (a run on another song may be at work in it), never one a --work run used (it is the person's). A run marks
    its folder as used when it starts. A folder that cannot be deleted (a file in use on Windows) stays, with a
    warning; the marker goes last, so the next run tries again.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import time
import unicodedata
from pathlib import Path
from typing import Callable, Iterable

from . import __version__
from .errors import InputError

NAME_MAX = 40            # <name>: at most this many characters (UTF-16 code units, as Windows counts a path)
KEY_HEX = 16             # <key>: this many hex characters of the song file's SHA-256
SCRATCH_HEX = 8          # autochart's scratch folder: <cache>/ac/<this many of them>
MARKER = "songcharter-work.json"  # in each work folder: what made it, its scratch folder, when it was last used
BUDGET_GB = 5.0          # the work folders' budget, in 10^9 bytes ($SONGCHARTER_CACHE_GB)
RECENT_S = 24 * 3600     # a work folder used this recently is never pruned
WINDOWS_PATH_MAX = 259   # characters: MAX_PATH (260) less the terminating NUL
_RESERVED = {"CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$", *(f"{d}{i}" for d in ("COM", "LPT") for i in range(10))}
_FORBIDDEN = set('<>:"/\\|?*')
# letters and marks NFKD does not take apart into ASCII (é is e and an accent; ß, the dashes and quotes are not)
_FOLD = {"ß": "ss", "ẞ": "SS", "æ": "ae", "Æ": "AE", "œ": "oe", "Œ": "OE", "ø": "o", "Ø": "O", "ł": "l", "Ł": "L",
         "đ": "d", "Đ": "D", "ð": "d", "Ð": "D", "þ": "th", "Þ": "Th", "ı": "i", "ŋ": "ng", "Ŋ": "Ng",
         "\u2010": "-", "\u2011": "-", "\u2012": "-", "\u2013": "-", "\u2014": "-", "\u2212": "-",
         "\u2018": "'", "\u2019": "'", "\u201a": "'", "\u201b": "'", "\u201c": "'", "\u201d": "'", "\u201e": "'"}
# the deepest relative paths a run creates (module docstring), Windows-style, with the longest seed and hex ids
DEEPEST = {
    "work": "guitar\\seed_20260609\\autochart_run\\expert_full_song_report.json",
    "scratch": ("engine-cache\\features\\fretformer_demucs_v1\\" + "f" * 64 + "\\demucs_default\\stems_htdemucs_6s\\"
                + ("audio_" + "f" * 64)[:32] + "\\mel-tables.bin"),
}


def user_cache() -> Path:
    """The platform's per-user cache folder for songcharter: %LOCALAPPDATA%\\songcharter on Windows (when it is
    set), else $XDG_CACHE_HOME/songcharter, else ~/.cache/songcharter. engines/adtof.py keeps its weights in
    models/ under it."""
    if sys.platform == "win32" and os.environ.get("LOCALAPPDATA"):
        return Path(os.environ["LOCALAPPDATA"]) / "songcharter"
    return Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache") / "songcharter"


def cache_root() -> Path:
    """Where the work and scratch folders go: $SONGCHARTER_CACHE, else `user_cache()`."""
    return Path(os.environ["SONGCHARTER_CACHE"]) if os.environ.get("SONGCHARTER_CACHE") else user_cache()


def file_key(path: Path | str) -> str:
    """The first KEY_HEX hex characters of the file's SHA-256."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 22), b""):
            h.update(block)
    return h.hexdigest()[:KEY_HEX]


def _units(text: str) -> int:
    """Length in UTF-16 code units (a character outside the BMP, an emoji, counts twice in a Windows path)."""
    return len(text.encode("utf-16-le")) // 2


def _fold(c: str) -> str:
    """A character as ASCII where it has an ASCII form (é -> e, ß -> ss, a full-width A -> A), else itself."""
    if c.isascii():
        return c
    if c in _FOLD:
        return _FOLD[c]
    plain = "".join(x for x in unicodedata.normalize("NFKD", c) if not unicodedata.combining(x))
    return plain if plain and plain.isascii() else c


def safe_name(stem: str, limit: int = NAME_MAX) -> str:
    """A file stem as a folder name any Windows accepts: ASCII-folded where a character has an ASCII form (other
    scripts are kept); control characters and < > : " / \\ | ? * as "_", invisible format characters (a zero-width
    space) left out; runs of spaces as one; no
    leading or trailing dots or spaces; at most `limit` UTF-16 code units; never a reserved device name (CON, PRN,
    AUX, NUL, COM0-9, LPT0-9, CONIN$, CONOUT$, also before an extension: "nul.txt"), which gets a "_" in front.
    Empty: "song"."""
    text = "".join(_fold(c) for c in unicodedata.normalize("NFC", stem))
    text = "".join("_" if c in _FORBIDDEN or unicodedata.category(c) == "Cc" else c for c in text
                   if unicodedata.category(c) != "Cf")
    text = " ".join(text.split())

    def cut(t: str, n: int) -> str:
        while _units(t) > n:
            t = t[:-1]
        return t.strip(" .")

    text = cut(text.strip(" ."), limit)
    if text.split(".")[0].rstrip(" ").upper() in _RESERVED:
        text = "_" + cut(text, limit - 1)
    return text or "song"


def work_folder(root: Path, stem: str, key: str) -> Path:
    """A song's default work folder: root/work/<safe_name(stem)>-<key>."""
    return root / "work" / f"{safe_name(stem)}-{key}"


def scratch_folder(root: Path, key: str) -> Path:
    """autochart's scratch folder for the song with this key: root/ac/<its first SCRATCH_HEX characters> (short, for
    the engine's deep cache layout: module docstring). Two keys that share those characters share it, which is
    safe: the engine keys everything in it by the audio's own SHA-256."""
    return root / "ac" / key[:SCRATCH_HEX]


def read_marker(folder: Path) -> dict | None:
    """The folder's MARKER, or None when it has none we wrote (no file, not JSON, not ours)."""
    try:
        data = json.loads((folder / MARKER).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) and "songcharter" in data else None


def mark(folder: Path, audio: Path, key: str | None, scratch: Path | None, *, pinned: bool = False,
         now: float | None = None) -> dict:
    """Write the MARKER of a work folder a run starts on: what made it, the song file, its key and scratch folder,
    when (`now`, seconds since the epoch: the wall clock, which only pruning reads) and whether a --work run used it
    (`pinned`: never pruned)."""
    now = time.time() if now is None else now
    data = {"songcharter": __version__, "input": str(audio), "key": key,
            "scratch": None if scratch is None else str(scratch), "used": now,
            "used_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)), "pinned": pinned}
    part = folder / (MARKER + ".part")
    part.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(part, folder / MARKER)
    return data


def tree_size(path: Path) -> int:
    """Bytes in the files under `path` (symbolic links not followed; files that vanish while counted skipped)."""
    total = 0
    try:
        entries = list(os.scandir(path))
    except OSError:
        return 0
    for e in entries:
        try:
            if e.is_dir(follow_symlinks=False):
                total += tree_size(Path(e.path))
            elif e.is_file(follow_symlinks=False):
                total += e.stat(follow_symlinks=False).st_size
        except OSError:
            continue
    return total


def size_text(n: int) -> str:
    """Bytes for a person: 812 MB, 1.23 GB (powers of 10)."""
    return f"{n / 1e9:.2f} GB" if n >= 1e9 else f"{n / 1e6:.0f} MB"


def budget_bytes() -> int:
    """The work folders' budget: $SONGCHARTER_CACHE_GB (10^9 bytes, 0 or more) or BUDGET_GB."""
    text = os.environ.get("SONGCHARTER_CACHE_GB", "").strip()
    if not text:
        return int(BUDGET_GB * 1e9)
    try:
        gb = float(text)
    except ValueError:
        gb = -1.0
    if not (gb >= 0 and gb != float("inf")):
        raise InputError(f"SONGCHARTER_CACHE_GB is the work folders' budget in GB (a number, 0 or more), not {text!r}")
    return int(gb * 1e9)


def _inside(path: Path, folder: Path) -> bool:
    try:
        path.resolve().relative_to(folder.resolve())
        return path.resolve() != folder.resolve()
    except ValueError:
        return False


def _delete(folder: Path, scratch: Path | None) -> None:
    """Delete a work folder and its scratch folder; the marker last, so a folder half deleted is still ours."""
    if scratch is not None and scratch.is_dir():
        shutil.rmtree(scratch)
    for child in folder.iterdir():
        if child.name == MARKER:
            continue
        if child.is_dir() and not child.is_symlink():
            shutil.rmtree(child)
        else:
            child.unlink()
    (folder / MARKER).unlink(missing_ok=True)
    folder.rmdir()


def prune(root: Path, budget: int, keep: Iterable[Path] = (), *, now: float | None = None,
          warn: Callable[[str], None] = lambda text: None) -> dict:
    """Delete the least recently used work folders under root/work, each with its scratch folder, until the work
    folders and their scratch folders total at most `budget` bytes (the module docstring's rules: only folders
    with our marker; never one in `keep`, one used in the last RECENT_S or one a --work run used). A deletion that
    fails is warned about and skipped. Returns what it found and did, for pipeline.json."""
    now = time.time() if now is None else now
    work, scratch_root = root / "work", root / "ac"
    keep = {Path(k).resolve() for k in keep}
    found = []
    for folder in sorted(work.iterdir()) if work.is_dir() else []:
        if not folder.is_dir() or folder.is_symlink():
            continue
        m = read_marker(folder)
        if m is None:
            continue
        scratch = Path(m["scratch"]) if m.get("scratch") else None
        scratch = scratch if scratch is not None and _inside(scratch, scratch_root) else None
        used = m.get("used") if isinstance(m.get("used"), (int, float)) else 0.0
        size = tree_size(folder) + (tree_size(scratch) if scratch is not None else 0)
        why = ("current" if folder.resolve() in keep else "pinned" if m.get("pinned")
               else "recent" if now - used < RECENT_S else None)
        found.append({"folder": folder, "scratch": scratch, "used": used, "bytes": size, "kept": why})
    total = sum(f["bytes"] for f in found)
    report: dict = {"root": str(root), "budget_bytes": budget, "folders": len(found), "bytes_before": total,
                    "deleted": [], "failed": []}
    shared = {f["scratch"] for f in found if f["kept"]}  # a scratch folder two keys share stays with the kept one
    for f in sorted((f for f in found if not f["kept"]), key=lambda f: (f["used"], f["folder"].name)):
        if total <= budget:
            break
        try:
            _delete(f["folder"], None if f["scratch"] in shared else f["scratch"])
        except OSError as e:
            left = tree_size(f["folder"]) + (tree_size(f["scratch"]) if f["scratch"] is not None else 0)
            total -= f["bytes"] - left
            report["failed"].append({"folder": str(f["folder"]), "error": f"{type(e).__name__}: {e}"})
            warn(f"the old work folder {f['folder']} could not be deleted ({type(e).__name__}: {e}): it stays, and "
                 "the next run tries again")
            continue
        total -= f["bytes"]
        report["deleted"].append({"folder": str(f["folder"]), "bytes": f["bytes"],
                                  "used_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(f["used"]))})
    report["bytes_after"] = total
    report["kept"] = {why: sum(f["kept"] == why for f in found) for why in ("current", "recent", "pinned")}
    return report
