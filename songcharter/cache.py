"""The per-user cache: the pipeline's work folders (DESIGN.md 9, Q30) and, apart from them, the downloaded weights.

    <cache>/work/<name>-<key>/   one song's work folder (pipeline.py): the decode, the stems, every engine's folder
    <cache>/ac/<key[:8]>/        autochart's own scratch folder for that song (its engine-cache and jobs; see below)
    <cache>/trash/<n>/           what a prune is deleting, moved out of work/ and ac/ first (see Pruning)
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
    tell the folders apart. When no folder has that name, an existing work/<other name>-<key> whose MARKER holds
    the key is the song's (`work_folder`, M5-12): v0.1 cut a long stem inside a word where M5-06 cuts at a space,
    and its caches (the separation, the guitar takes) are kept, not made again under the new name. A renamed copy
    of the file finds the same folder.
  * **Path length.** Windows refuses a path of more than 259 characters (MAX_PATH less its NUL) unless long paths
    are turned on, which nothing here can assume. The deepest files a run leaves (`DEEPEST`, with Windows
    separators):
      - in the work folder, a take's report: guitar\\seed_20260609\\autochart_run\\expert_full_song_report.json
        (63 characters);
      - in autochart's scratch folder, its separation's mel tables: engine-cache\\features\\fretformer_demucs_v1\\
        <64 hex>\\demucs_default\\stems_htdemucs_6s\\audio_<26 hex>\\mel-tables.bin (188: our driver's engine-cache
        layout, and the engine's own stem folder name, which it cuts to 32 characters on Windows).
    Inside the work folder, as <work>\\guitar\\work, that scratch would run to 319 characters with a profile of
    C:\\Users\\<20 characters>\\AppData\\Local and a 40-character name. In <cache>\\ac\\<8 hex> the deepest file
    there is 256 characters, and the work folder's 182. But autochart writes each of these files through a staging
    file beside it, .<name>.tmp-<pid>-<uuid> (fileSafety.cjs writeVerifiedAtomic), and those go deeper: 235
    characters below the scratch folder in a real take (traced; the mel tables' with a 4-digit pid), 241 with a
    10-digit one (`DEEPEST["staging"]`), so past 259 on every profile (309 with the one above, 290 with C:\\Users\\X).
    Only Node writes them, and Node's fs takes Windows paths in their \\\\?\\ form, past 259 [doc; untested on
    Windows]; a run killed while one is written leaves it behind, so prune deletes with that form too
    (`long_path`).
  * **Pruning** (`prune`, after each run): the least recently used work folders under <cache>/work go, with their
    scratch folders, until the rest total at most 5 GB (10^9 bytes; $SONGCHARTER_CACHE_GB sets another budget).
    Only folders that carry our MARKER count or go. Never the current run's, never one used in the last 24 hours
    (a run on another song may be at work in it), never one a --work run used (it is the person's). A run marks
    its folder as used when it starts. A folder that goes is first moved whole into <cache>/trash, in one rename,
    its scratch folder before it, and only then deleted there, so no run ever meets a folder half deleted (a run
    trusts the caches it finds: the stems an info.json lists). Its marker is read again just before the move (a
    run may have started on that song since the scan) and once more after it: a run that marked it in between gets
    it back (left open: a run whose folder is moved between its mkdir and its marker, microseconds, fails with
    exit 2). A folder that cannot be moved (on Windows, a file in it in use, or a console's current folder) stays
    whole, with a warning, and the next run tries again; what cannot be deleted in the trash (a file in use, a
    Ctrl+C) stays there, with a warning, and the next prune deletes it first. The trash is ours only with its
    TRASH_MARKER in it: in a folder of that name without one, nothing is moved or deleted.
"""
from __future__ import annotations

import hashlib
import json
import ntpath
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
WORD_BACK = 12           # safe_name: a cut inside a word moves back to a space at most this many units before it
KEY_HEX = 16             # <key>: this many hex characters of the song file's SHA-256
SCRATCH_HEX = 8          # autochart's scratch folder: <cache>/ac/<this many of them>
MARKER = "songcharter-work.json"  # in each work folder: what made it, its scratch folder, when it was last used
TRASH = "trash"          # <cache>/trash: where prune moves a folder before it deletes it (module docstring)
TRASH_MARKER = "songcharter-trash.json"  # in <cache>/trash: the folder is ours, so what is in it may be deleted
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
# the deepest relative paths a run creates (module docstring), Windows-style, with the longest seed and hex ids: the
# files it leaves in the work and scratch folders, and the staging file autochart writes the scratch's beside it
# (.<name>.tmp-<pid>-<uuid>, here with a 10-digit pid, the most a Windows process id has)
_MEL_FOLDER = ("engine-cache\\features\\fretformer_demucs_v1\\" + "f" * 64 + "\\demucs_default\\stems_htdemucs_6s\\"
               + ("audio_" + "f" * 64)[:32])
DEEPEST = {
    "work": "guitar\\seed_20260609\\autochart_run\\expert_full_song_report.json",
    "scratch": _MEL_FOLDER + "\\mel-tables.bin",
    "staging": _MEL_FOLDER + "\\.mel-tables.bin.tmp-" + "4" * 10 + "-" + "-".join("f" * n for n in (8, 4, 4, 4, 12)),
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
    leading or trailing dots or spaces; at most `limit` UTF-16 code units, cut at a word where one ends close
    enough (a cut inside a word goes back to the last space before it when that leaves at least `limit` -
    WORD_BACK units; else it cuts the word); never a reserved device name (CON, PRN, AUX, NUL, COM0-9, LPT0-9,
    CONIN$, CONOUT$, also before an extension: "nul.txt"), which gets a "_" in front. Empty: "song"."""
    text = "".join(_fold(c) for c in unicodedata.normalize("NFC", stem))
    text = "".join("_" if c in _FORBIDDEN or unicodedata.category(c) == "Cc" else c for c in text
                   if unicodedata.category(c) != "Cf")
    text = " ".join(text.split())

    def cut(t: str, n: int) -> str:
        head = t
        while _units(head) > n:
            head = head[:-1]
        if head and len(head) < len(t) and head[-1] != " " and t[len(head)] != " ":   # inside a word
            space = head.rfind(" ")
            if space >= 0 and _units(head[:space].rstrip(" .")) >= n - WORD_BACK:
                head = head[:space]
        return head.strip(" .")

    text = cut(text.strip(" ."), limit)
    if text.split(".")[0].rstrip(" ").upper() in _RESERVED:
        text = "_" + cut(text, limit - 1)
    return text or "song"


def work_folder(root: Path, stem: str, key: str) -> Path:
    """A song's default work folder: root/work/<safe_name(stem)>-<key> when it exists or no other folder holds the
    song's caches; else the existing root/work/<another name>-<key> whose MARKER holds that key (`by_key`): the same
    file under a name safe_name cut otherwise (v0.1 cut inside a word, before M5-06's WORD_BACK), or a renamed copy.
    So an older version's caches of the song (the separation, the sections, the guitar takes) are found, not made
    again beside them (M5-12)."""
    folder = root / "work" / f"{safe_name(stem)}-{key}"
    if folder.exists() or folder.is_symlink():
        return folder
    found = by_key(root, key)
    return found if found is not None else folder


def by_key(root: Path, key: str) -> Path | None:
    """The folder under root/work named <name>-<key> whose MARKER holds `key`, the most recently used when there are
    several (then the first by name), or None. A folder without our marker, with another key in it, or a link is
    not one."""
    work = root / "work"
    found = []
    for folder in sorted(work.glob(f"*-{key}")) if work.is_dir() else []:
        if not folder.is_dir() or folder.is_symlink():
            continue
        m = read_marker(folder)
        if m is not None and m.get("key") == key:
            found.append((-_used(m), folder.name, folder))
    return min(found)[2] if found else None


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


def long_path(path: Path | str, windows: bool | None = None) -> str:
    """`path` for a deletion: on Windows (`windows`, by default whether this is Windows) in its extended-length
    form, \\\\?\\C:\\... or \\\\?\\UNC\\server\\share\\..., which Windows takes past 259 characters even without long
    paths turned on (autochart's staging files: module docstring); elsewhere as it is."""
    if not (sys.platform == "win32" if windows is None else windows):
        return str(path)
    text = str(path)
    if text.startswith("\\\\?\\"):
        return text
    text = ntpath.abspath(text)
    return "\\\\?\\UNC\\" + text[2:] if text.startswith("\\\\") else "\\\\?\\" + text


def _used(m: dict) -> float:
    return m.get("used") if isinstance(m.get("used"), (int, float)) else 0.0


def _kept(m: dict, now: float) -> str | None:
    """Why a marked folder never goes ("pinned", "recent"), else None (the current run's is the caller's)."""
    return "pinned" if m.get("pinned") else "recent" if now - _used(m) < RECENT_S else None


def _trash(root: Path) -> Path:
    """root/TRASH, made ours (its TRASH_MARKER written) when it is new or empty; an OSError when a folder of that
    name holds what we did not put there (a `trash` of the person's where $SONGCHARTER_CACHE points)."""
    trash = root / TRASH
    trash.mkdir(exist_ok=True)
    if not (trash / TRASH_MARKER).is_file():
        if any(trash.iterdir()):
            raise OSError(f"{trash} is not songcharter's (it has no {TRASH_MARKER}): nothing is moved into it")
        (trash / TRASH_MARKER).write_text(json.dumps({"songcharter": __version__}) + "\n", encoding="utf-8")
    return trash


def _aside(path: Path, trash: Path) -> Path:
    """Move `path` into `trash` in one rename, under the first number free there, and return where it went. An
    OSError leaves it where it was, whole (on Windows a folder with a file in use in it cannot be moved)."""
    i = 0
    while True:
        dest = trash / str(i)
        i += 1
        if dest.exists() or dest.is_symlink():
            continue
        try:
            os.rename(path, dest)
        except OSError:
            if dest.exists():  # another run's prune took that number first
                continue
            raise
        return dest


def _remove(entry: Path) -> None:
    """Delete what is at `entry` (a folder and all in it, or a file), in long_path's form."""
    if entry.is_dir() and not entry.is_symlink():
        shutil.rmtree(long_path(entry))
    else:
        entry.unlink(missing_ok=True)


def _empty_trash(root: Path, report: dict, warn: Callable[[str], None]) -> None:
    """Delete what an earlier prune left in root/TRASH (a deletion stopped partway: a file in use, a Ctrl+C), when
    that folder is ours."""
    trash = root / TRASH
    if not (trash / TRASH_MARKER).is_file():
        return
    for entry in sorted(trash.iterdir()):
        if entry.name == TRASH_MARKER:
            continue
        size = tree_size(entry)
        try:
            _remove(entry)
        except OSError as e:
            report["trash_left"].append({"entry": str(entry), "error": f"{type(e).__name__}: {e}"})
            warn(f"{entry}, left from a deletion, could not be deleted ({type(e).__name__}: {e}): the next run tries "
                 "again")
            continue
        report["swept"].append({"entry": str(entry), "bytes": size})


def prune(root: Path, budget: int, keep: Iterable[Path] = (), *, now: float | None = None,
          warn: Callable[[str], None] = lambda text: None) -> dict:
    """Delete the least recently used work folders under root/work, each with its scratch folder, until the work
    folders and their scratch folders total at most `budget` bytes (the module docstring's rules: only folders
    with our marker; never one in `keep`, one used in the last RECENT_S or one a --work run used; each moved whole
    into root/TRASH, then deleted there), after what an earlier prune left in root/TRASH. A folder that cannot be
    moved is warned about and skipped, and so is what cannot be deleted in the trash. Returns what it found and
    did, for pipeline.json."""
    now = time.time() if now is None else now
    work, scratch_root = root / "work", root / "ac"
    keep = {Path(k).resolve() for k in keep}
    report: dict = {"root": str(root), "budget_bytes": budget, "folders": 0, "bytes_before": 0, "deleted": [],
                    "failed": [], "swept": [], "trash_left": []}
    _empty_trash(root, report, warn)
    found = []
    for folder in sorted(work.iterdir()) if work.is_dir() else []:
        if not folder.is_dir() or folder.is_symlink():
            continue
        m = read_marker(folder)
        if m is None:
            continue
        scratch = Path(m["scratch"]) if m.get("scratch") else None
        scratch = scratch if scratch is not None and _inside(scratch, scratch_root) else None
        size = tree_size(folder) + (tree_size(scratch) if scratch is not None else 0)
        why = "current" if folder.resolve() in keep else _kept(m, now)
        found.append({"folder": folder, "scratch": scratch, "used": _used(m), "bytes": size, "kept": why})
    total = sum(f["bytes"] for f in found)
    report.update(folders=len(found), bytes_before=total)
    shared = {f["scratch"] for f in found if f["kept"]}  # a scratch folder two keys share stays with the kept one
    trash = None

    def remove(moved: list[tuple[Path, Path]], folder: Path) -> None:
        for was, went in moved:
            try:
                _remove(went)
            except OSError as e:
                report["trash_left"].append({"entry": str(went), "error": f"{type(e).__name__}: {e}"})
                what = (f"the old work folder {folder}" if was == folder
                        else f"autochart's scratch folder {was} of the old work folder {folder.name}")
                warn(f"{what} is out of the cache, but not all of it could be deleted ({type(e).__name__}: {e}): "
                     f"what is left is in {went}, and the next run deletes it")

    for f in sorted((f for f in found if not f["kept"]), key=lambda f: (f["used"], f["folder"].name)):
        if total <= budget:
            break
        folder = f["folder"]
        scratch = None if f["scratch"] in shared else f["scratch"]
        m = read_marker(folder)  # again: a run may have started on this song since the scan
        if m is None or _kept(m, now):
            if m is not None:
                f["kept"] = _kept(m, now)
                shared.add(f["scratch"])
            elif not folder.exists():  # another run's prune took it meanwhile
                total -= f["bytes"]
            continue
        if trash is None:
            try:
                trash = _trash(root)
            except OSError as e:
                report["failed"].append({"folder": str(folder), "error": f"{type(e).__name__}: {e}"})
                warn(f"no old work folder was deleted ({type(e).__name__}: {e})")
                break
        moved: list[tuple[Path, Path]] = []  # (where it was, where it went)
        try:
            if scratch is not None and scratch.is_dir():  # first: a scratch left behind would belong to no marker
                moved.append((scratch, _aside(scratch, trash)))
            moved.append((folder, _aside(folder, trash)))
        except OSError as e:
            remove(moved, folder)  # the scratch folder, if it went first: the work folder stays, and names it
            total -= f["bytes"] - tree_size(folder) - (tree_size(f["scratch"]) if f["scratch"] is not None else 0)
            report["failed"].append({"folder": str(folder), "error": f"{type(e).__name__}: {e}"})
            warn(f"the old work folder {folder} could not be deleted ({type(e).__name__}: {e}): it stays, and the "
                 "next run tries again")
            continue
        again = read_marker(moved[-1][1])
        if again is not None and (_used(again) != _used(m) or _kept(again, now)):  # marked between the two reads
            for was, went in reversed(moved):
                try:
                    os.rename(went, was)
                except OSError:  # the run has made a new folder there meanwhile: this one goes with the trash
                    pass
            f["kept"] = _kept(again, now) or "recent"
            shared.add(f["scratch"])
            continue
        remove(moved, folder)
        total -= f["bytes"]
        report["deleted"].append({"folder": str(folder), "bytes": f["bytes"],
                                  "used_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(f["used"]))})
    report["bytes_after"] = total
    report["kept"] = {why: sum(f["kept"] == why for f in found) for why in ("current", "recent", "pinned")}
    return report
