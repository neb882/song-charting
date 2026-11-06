"""Clone Hero's Songs folder on Windows, seen from WSL, and a built song folder put into it (M4-06, DESIGN.md 4.5).

    folder, source = clonehero.songs_folder(home)        # (Path, "saved" | "documents") or (None, "not found")
    clonehero.set_songs_folder(home, r"C:\\Users\\Jörg\\Documents\\Clone Hero\\Songs")   # InputError: missing, not writable
    done = clonehero.install(song_folder, songs, home)   # Exists (409), Blocked (403: offer the zip)
    clonehero.export_zip(song_folder, home)              # $SONGCHARTER_HOME/exports/<name>.zip

songcharter runs in WSL and Clone Hero on Windows, so the Songs folder is reached under /mnt/c (drvfs), where
Windows' rules apply: the names (cache.safe_name made the song folder's), the timestamps and modes drvfs refuses, and
the programs that hold a new folder for a moment (OneDrive's sync, antivirus).

  * **Where** (`songs_folder`), the first that exists: the folder saved in $SONGCHARTER_HOME/ui.json
    ("clone_hero_songs"), "saved"; in WSL, <Documents>\\Clone Hero\\Songs, with Documents from the registry
    (wsl.shell_folder("Personal"), so it follows OneDrive when that has moved Documents), "documents"; else
    (None, "not found"). Clone Hero's own settings.ini is not read in v0.1: its keys are unverified (M4-08).
  * **Saving one** (`set_songs_folder`): a Linux path, or a Windows one (C:\\..., \\\\server\\...: wsl.to_linux),
    quotes around it dropped (Explorer's "Copy as path" adds them); refused (InputError) when it does not exist or a
    file cannot be written and deleted there; saved to ui.json atomically.
  * **Installing** (`install`): into songs/<the song folder's name>.
      - A folder of that name there already: Exists, with `ours` (its song.ini says charter = songcharter and it
        holds report.json). Only our own is replaced, and only when asked (replace=True); another charter's never.
      - **Our older charts of the same song under another name** (`older_charts`, M5-13): each folder at the top of
        songs that is ours and whose song.ini has the same name and artist as the new chart's (`song_of`: compared
        without case, runs of spaces as one); not hidden, not a link, and not songs/<name> itself (a name that
        differs only in case is that folder on drvfs, another one on ext4). v0.1.0 cut the library folder's name at
        40 characters and M5-06 at 80, so a song charted under v0.1.0 whose "Artist - Title" ran longer is in songs
        under v0.1.0's cut, and Clone Hero would list the song twice; a folder of ours the person renamed is one
        too. They count as the existing chart: Exists (ours) names the first when replace is false; with
        replace=True each goes to replaced/ as a same-name one does, after the new chart is in place (renamed aside
        to .<the new name>.songcharter-<8 hex>.old, so a move that fails is a leftover the next install clears). A
        folder without our marks, or one of ours with another song in it (a v0.1.0 cut two songs share), is never
        touched. The cost: one look at each folder in songs (report.json), and song.ini read in our own.
      - The copy goes to songs/.<name>.songcharter-<8 hex>.tmp, contents only (shutil.copyfile, never copystat: not
        shutil.copytree, which copies each folder's timestamps and modes, what drvfs refuses).
      - When replacing, the old folder is renamed aside in songs (.<name>.songcharter-<8 hex>.old), the copy renamed
        into place, then the old one moved to $SONGCHARTER_HOME/replaced/<yyyyMMdd-HHmmss>/<name> (shutil.move: from
        /mnt/c to ext4). Renaming aside first keeps the old chart in Songs when the new one cannot be put in place:
        a failed rename into place renames it back.
      - **Every rename under songs is retried** for about 5 s (RENAME_TRIES 10, RENAME_WAIT_S 0.5 apart) on a
        PermissionError or an OSError with errno EACCES, EBUSY or EPERM: OneDrive's sync and antivirus can hold a
        new folder briefly, and through WSL that shows as one of these. Still failing, or failing otherwise (the
        copy too): **Blocked**, the temporary folder removed. The server then makes the zip and offers it. When the
        older chart cannot be put back either, Blocked names its .old folder (`old`).
      - **Our own leftovers** for this name (`leftovers`: .<name>.songcharter-<8 hex>.tmp or .old, each a real
        folder that is_ours), from a blocked replace, a temporary folder Windows would not let go, or a run that
        stopped halfway, are dealt with on the next install of that name that goes ahead: a .old goes to
        $SONGCHARTER_HOME/replaced/ as a replaced chart would, a .tmp is deleted. Anything else is never touched.
  * **Under OneDrive** (`under_onedrive`): whether a path lies under one of wsl.onedrive_roots() (compared without
    case, as drvfs and Windows do). The page says so when a write is blocked; the diagnostics record it.
  * **Windows' name for a path** (`windows_path`, in WSL): X:\\... for /mnt/x/..., \\\\wsl.localhost\\<distro>\\...
    for the Linux side; None outside WSL.
"""
from __future__ import annotations

import errno
import json
import os
import re
import secrets
import shutil
import time
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

from . import wsl
from .errors import InputError

UI_FILE = "ui.json"                  # in $SONGCHARTER_HOME: the UI's settings
KEY = "clone_hero_songs"             # ui.json's key for the Songs folder
RENAME_TRIES = 10                    # each rename under the Songs folder, about 5 s in all
RENAME_WAIT_S = 0.5
RETRY_ERRNOS = (errno.EACCES, errno.EBUSY, errno.EPERM)
REPLACED = "replaced"                # $SONGCHARTER_HOME/replaced/<stamp>/<name>: the charts a replace moved out
EXPORTS = "exports"                  # $SONGCHARTER_HOME/exports/<name>.zip
CHARTER = "songcharter"              # song.ini's charter in a folder songcharter built
_WINDOWS = re.compile(r"^(?:[A-Za-z]:[\\/]|\\\\)")   # C:\..., C:/..., \\server\share or \\wsl.localhost\...
_CHARTER_LINE = re.compile(r"^\s*charter\s*=\s*(.*?)\s*$", re.MULTILINE | re.IGNORECASE)
_LEFTOVER = re.compile(r"^\.(?P<name>.+)\.songcharter-(?P<tag>[0-9a-f]{8})\.(?P<kind>tmp|old)$")


class Exists(Exception):
    """songs/<name> exists: the server answers 409. `ours`: songcharter built it (it may be replaced)."""

    def __init__(self, target: Path, ours: bool):
        super().__init__(f"{target} exists" + ("" if ours else ", and songcharter did not make it"))
        self.target, self.ours = target, ours


class Blocked(Exception):
    """Windows did not let the copy or a rename finish (the module docstring): the server offers the zip (403).
    `old`: the .old folder the older chart stays in when it could not be put back, else None."""

    def __init__(self, why: str, target: Path, old: Path | None = None):
        super().__init__(why)
        self.why, self.target, self.old = why, target, old


@dataclass(frozen=True)
class Installed:
    target: Path                     # songs/<name>
    replaced: Path | None = None     # where the older chart went, when one was replaced (the first, of several)
    note: str | None = None          # what did not go as planned after the install itself (the older chart's move),
                                     # and where the other older charts went, when there were several


# ------------------------------------------------------------------------------------------------ ui.json

def ui_file(home: Path) -> Path:
    return Path(home) / UI_FILE


def read_ui(home: Path) -> dict:
    """ui.json's settings, {} when there is none or it does not read as an object."""
    try:
        data = json.loads(ui_file(home).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def write_ui(home: Path, data: dict) -> None:
    """ui.json written whole, through a .part file and a rename."""
    path = ui_file(home)
    path.parent.mkdir(parents=True, exist_ok=True)
    part = path.with_name(path.name + ".part")
    part.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(part, path)


# ------------------------------------------------------------------------------------------------ the Songs folder

def windows_path(path: Path | str | None) -> str | None:
    """`path` as Windows names it, in WSL: X:\\rest for <the drive mounts>/x/rest (wsl.MNT_C's parent, /mnt), else
    \\\\wsl.localhost\\<distro>\\path; None outside WSL (or without a distro name for a Linux-side path)."""
    if path is None or not wsl.is_wsl():
        return None
    p = Path(path)
    try:
        rel = p.relative_to(wsl.MNT_C.parent)
    except ValueError:
        rel = None
    if rel is not None and rel.parts and len(rel.parts[0]) == 1 and rel.parts[0].isalpha():
        return rel.parts[0].upper() + ":\\" + "\\".join(rel.parts[1:])
    distro = wsl.distro()
    return "\\\\wsl.localhost\\" + distro + str(p).replace("/", "\\") if distro else None


def documents_songs() -> Path | None:
    """<Documents>/Clone Hero/Songs in WSL (Documents from the registry: wsl.shell_folder("Personal")), whether it
    exists or not; None outside WSL or when Documents cannot be read."""
    if not wsl.is_wsl():
        return None
    docs = wsl.shell_folder("Personal")
    return docs / "Clone Hero" / "Songs" if docs is not None else None


def songs_folder(home: Path, documents: Callable[[], Path | None] = documents_songs) -> tuple[Path | None, str]:
    """The Songs folder and where it came from: ("saved" | "documents"), or (None, "not found")."""
    saved = read_ui(home).get(KEY)
    if isinstance(saved, str) and saved and Path(saved).is_dir():
        return Path(saved), "saved"
    guess = documents()
    if guess is not None and guess.is_dir():
        return guess, "documents"
    return None, "not found"


def _fold(text: str) -> str:
    return unicodedata.normalize("NFC", text).casefold()


def under_onedrive(path: Path | str, roots: Iterable[Path] | None = None) -> bool:
    """Whether `path` is one of the OneDrive folders Windows names (wsl.onedrive_roots(), or `roots`) or lies under
    one, compared without case."""
    p = _fold(str(Path(path)))
    for root in (wsl.onedrive_roots() if roots is None else roots):
        r = _fold(str(Path(root))).rstrip("/")
        if r and (p == r or p.startswith(r + "/")):
            return True
    return False


def to_linux_path(text: str) -> Path:
    """What a person typed or pasted as the Songs folder, as a Linux path: quotes and spaces around it dropped; a
    Windows path through wsl.to_linux. InputError when it is empty, relative, or a Windows path WSL cannot turn."""
    raw = text.strip().strip('"').strip()
    if not raw:
        raise InputError("give the Songs folder's path")
    if _WINDOWS.match(raw):
        linux = wsl.to_linux(raw)
        if linux is None:
            raise InputError(f"{raw} is a Windows path, and WSL could not turn it into one of its own (wslpath): "
                             "is this songcharter running in WSL?")
        return linux
    path = Path(raw).expanduser()
    if not path.is_absolute():
        raise InputError(f"{raw} is not a whole path: give it from the drive, like C:\\Users\\you\\Documents\\Clone "
                         "Hero\\Songs")
    return path


def set_songs_folder(home: Path, text: str) -> Path:
    """Save the Songs folder (`text`: to_linux_path) to ui.json, once it exists and a file can be written and deleted
    there; InputError otherwise. The folder as saved."""
    path = to_linux_path(text)
    if not path.is_dir():
        raise InputError(f"{text.strip()} does not exist (or is not a folder): start Clone Hero once, or check the "
                         "path")
    probe = path / f".songcharter-probe-{secrets.token_hex(4)}"
    try:
        probe.write_bytes(b"songcharter checks it can write here\n")
        probe.unlink()
    except OSError as e:
        try:
            probe.unlink(missing_ok=True)
        except OSError:
            pass
        raise InputError(f"songcharter cannot write into {text.strip()} ({e.strerror or type(e).__name__})") from None
    data = read_ui(home)
    data[KEY] = str(path)
    write_ui(home, data)
    return path


# ------------------------------------------------------------------------------------------------ installing

def is_ours(folder: Path) -> bool:
    """Whether songcharter built `folder`: its song.ini says charter = songcharter, and it holds report.json."""
    if not (folder / "report.json").is_file():
        return False
    try:
        text = (folder / "song.ini").read_text(encoding="utf-8-sig", errors="replace")
    except OSError:
        return False
    m = _CHARTER_LINE.search(text)
    return bool(m) and m.group(1).strip().lower() == CHARTER


def song_of(folder: Path) -> tuple[str, str] | None:
    """The song a song folder holds, as Clone Hero lists it: its song.ini's (name, artist), each folded (NFC,
    without case, runs of spaces as one), from the first line of each key; None when song.ini cannot be read, or
    has no name (or an empty one) or no artist line."""
    try:
        text = (Path(folder) / "song.ini").read_text(encoding="utf-8-sig", errors="replace")
    except OSError:
        return None
    found: dict[str, str] = {}
    for line in text.splitlines():
        key, sep, value = line.partition("=")
        key = key.strip().lower()
        if sep and key in ("name", "artist") and key not in found:
            found[key] = _fold(" ".join(value.split()))
    if not found.get("name") or "artist" not in found:
        return None
    return found["name"], found["artist"]


def older_charts(songs: Path | str, song_folder: Path | str) -> list[Path]:
    """Our older charts, in `songs` under another name, of the song in `song_folder` (the module docstring): each
    real folder at the top of `songs` (not a link), not hidden (a leading dot), not songs/<song_folder's name>
    itself (that name, or one that differs only in case and is the same folder, as drvfs and Windows find it), that
    is_ours and holds the same song (song_of); by name."""
    song = song_of(Path(song_folder))
    if song is None:
        return []
    target = Path(songs) / Path(song_folder).name
    try:
        with os.scandir(songs) as it:
            entries = sorted(it, key=lambda e: e.name)
    except OSError:
        return []
    found = []
    for e in entries:
        if e.name.startswith(".") or e.name == target.name:
            continue
        if _fold(e.name) == _fold(target.name) and _same_folder(e.path, target):
            continue
        try:
            real_folder = e.is_dir(follow_symlinks=False)
        except OSError:
            continue
        folder = Path(e.path)
        if real_folder and is_ours(folder) and song_of(folder) == song:
            found.append(folder)
    return found


def _same_folder(a: Path | str, b: Path | str) -> bool:
    """Whether two paths name one folder (os.path.samefile), False when either cannot be looked at."""
    try:
        return os.path.samefile(a, b)
    except OSError:
        return False


def retryable(e: OSError) -> bool:
    """An error a moment's wait may cure (the module docstring)."""
    return isinstance(e, PermissionError) or e.errno in RETRY_ERRNOS


def retry(action: Callable[[], object], what: str, target: Path, sleep: Callable[[float], None] = time.sleep):
    """`action()`, tried RENAME_TRIES times RENAME_WAIT_S apart while it fails retryably; Blocked (with `what` and
    the last error) when it still fails, or fails otherwise."""
    for attempt in range(RENAME_TRIES):
        try:
            return action()
        except OSError as e:
            if not retryable(e):
                raise Blocked(f"{what} failed: {e.strerror or type(e).__name__}", target) from None
            if attempt == RENAME_TRIES - 1:
                raise Blocked(f"{what} was refused {RENAME_TRIES} times in about "
                              f"{RENAME_TRIES * RENAME_WAIT_S:.0f} s: {e.strerror or type(e).__name__}",
                              target) from None
            sleep(RENAME_WAIT_S)
    raise AssertionError("unreachable")


def copy_contents(src: Path, dst: Path) -> None:
    """`src`'s files and folders into the new folder `dst`, contents only: shutil.copyfile, no copystat."""
    os.mkdir(dst)
    for entry in sorted(src.iterdir()):
        if entry.is_dir() and not entry.is_symlink():
            copy_contents(entry, dst / entry.name)
        elif entry.is_file():
            shutil.copyfile(entry, dst / entry.name)


def _remove(folder: Path, sleep: Callable[[float], None]) -> None:
    """Delete our temporary folder, retried like a rename; left (it starts with a dot) when it still cannot go."""
    def rm() -> None:
        try:
            shutil.rmtree(folder)
        except FileNotFoundError:
            pass
    try:
        retry(rm, "deleting the temporary folder", folder, sleep)
    except Blocked:
        pass


def leftovers(songs: Path, name: str) -> list[tuple[str, Path]]:
    """Our own leftovers for the song folder `name` in `songs`: ("tmp" | "old", path) for each
    .<name>.songcharter-<8 hex>.tmp or .old that is a real folder (not a link) and is_ours, by name."""
    try:
        entries = sorted(Path(songs).iterdir())
    except OSError:
        return []
    found = []
    for p in entries:
        m = _LEFTOVER.match(p.name)
        if m and m["name"] == name and p.is_dir() and not p.is_symlink() and is_ours(p):
            found.append((m["kind"], p))
    return found


def _to_replaced(old: Path, home: Path | str, name: str, stamp: str) -> Path:
    """Move an older chart (a .old folder in Songs) to $SONGCHARTER_HOME/replaced/<stamp>/<name> (<stamp>-<its 8
    hex> when that is taken); where it went. shutil.move: from /mnt/c to ext4, a copy and a delete."""
    dest = Path(home) / REPLACED / stamp / name
    if dest.exists():
        m = _LEFTOVER.match(old.name)
        dest = Path(home) / REPLACED / f"{stamp}-{m['tag'] if m else secrets.token_hex(4)}" / name
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(old), str(dest))
    return dest


def _tidy(songs: Path, name: str, home: Path | str, stamp: str, sleep: Callable[[float], None]
          ) -> tuple[list[Path], list[str]]:
    """Deal with our leftovers for `name` (the module docstring): where each .old went, and a note for each that
    stays."""
    moved, notes = [], []
    for kind, p in leftovers(songs, name):
        if kind == "tmp":
            _remove(p, sleep)
            if p.exists():
                notes.append(f"songcharter's temporary folder {p} could not be deleted")
            continue
        try:
            moved.append(_to_replaced(p, home, name, stamp))
        except OSError as e:
            notes.append(f"an older chart stays in {p}: moving it into {Path(home) / REPLACED} failed "
                         f"({e.strerror or type(e).__name__})")
    return moved, notes


def install(song_folder: Path | str, songs: Path | str, home: Path | str, replace: bool = False, *,
            rename: Callable[[Path, Path], None] = os.rename, sleep: Callable[[float], None] = time.sleep,
            now: float | None = None) -> Installed:
    """Put the song folder into the Songs folder (the module docstring). InputError when either is not a folder;
    Exists (409) when songs/<name> exists and is not ours, or when it (ours) or an older chart of ours of the same
    song under another name (older_charts: then Exists names the first) is there and `replace` is false; Blocked
    (403) when Windows does not let it finish. `rename` and `sleep` are os.rename's and time.sleep's stand-ins for
    tests. Our leftovers for the name go first (_tidy), the older charts under other names last (_replace_older);
    `note` says what of them stays, or where an older chart went."""
    src, songs = Path(song_folder), Path(songs)
    if not src.is_dir():
        raise InputError(f"the song folder {src} does not exist")
    if not songs.is_dir():
        raise InputError(f"the Songs folder {songs} does not exist")
    name = src.name
    target = songs / name
    existed = target.exists() or target.is_symlink()
    if existed:
        ours = target.is_dir() and not target.is_symlink() and is_ours(target)
        if not (replace and ours):
            raise Exists(target, ours)
    older = older_charts(songs, src)
    if older and not replace:
        raise Exists(older[0], True)
    stamp = time.strftime("%Y%m%d-%H%M%S", time.localtime(time.time() if now is None else now))
    moved, notes = _tidy(songs, name, home, stamp, sleep)
    notes = [f"an older chart left in Songs went to {p}" for p in moved] + notes
    tag = secrets.token_hex(4)
    tmp = songs / f".{name}.songcharter-{tag}.tmp"
    try:
        copy_contents(src, tmp)
    except OSError as e:
        _remove(tmp, sleep)
        raise Blocked(f"writing into the Songs folder failed: {e.strerror or type(e).__name__}", target) from None
    old = songs / f".{name}.songcharter-{tag}.old" if existed else None
    try:
        if old is not None:
            retry(lambda: rename(target, old), "moving the older chart aside", target, sleep)
        try:
            retry(lambda: rename(tmp, target), "the rename into place", target, sleep)
        except Blocked as e:
            if old is not None:
                try:
                    retry(lambda: rename(old, target), "putting the older chart back", target, sleep)
                except Blocked:
                    raise Blocked(f"{e.why}; putting the older chart back was refused too, so it is in {old} for "
                                  "now: the next install of this song moves it to songcharter's replaced folder",
                                  target, old) from None
            raise
    except Blocked:
        _remove(tmp, sleep)
        raise
    first = None   # where the older chart went (the first, of several)
    if old is not None:
        try:
            first = _to_replaced(old, home, name, stamp)
        except OSError as e:
            notes.append(f"the older chart stays in {old}: moving it into {Path(home) / REPLACED} failed "
                         f"({e.strerror or type(e).__name__}); the next install of this song tries again")
    for folder in older:
        went, why = _replace_older(folder, songs, name, home, stamp, rename, sleep)
        if went is None:
            notes.append(why)
        elif first is None:
            first = went
        else:
            notes.append(f"another older chart of this song, {folder.name}, went to {went}")
    return Installed(target, first if first is not None else (moved[0] if moved else None), "; ".join(notes) or None)


def _replace_older(folder: Path, songs: Path, name: str, home: Path | str, stamp: str,
                   rename: Callable[[Path, Path], None], sleep: Callable[[float], None]) -> tuple[Path | None, str]:
    """One of older_charts out of Songs, once the new chart `name` is in place: renamed aside (retried) to
    .<name>.songcharter-<8 hex>.old, then moved to replaced/<stamp>/<its own name>. (where it went, "") or (None,
    why it stays)."""
    aside = songs / f".{name}.songcharter-{secrets.token_hex(4)}.old"
    try:
        retry(lambda: rename(folder, aside), "moving an older chart of this song aside", folder, sleep)
    except Blocked as e:
        return None, (f"{e.why}: it stays in {folder}, and Clone Hero lists the song twice until that folder is "
                      "deleted")
    try:
        return _to_replaced(aside, home, folder.name, stamp), ""
    except OSError as e:
        return None, (f"an older chart of this song stays in {aside}: moving it into {Path(home) / REPLACED} failed "
                      f"({e.strerror or type(e).__name__}); the next install of this song tries again")


def export_zip(song_folder: Path | str, home: Path | str) -> Path:
    """$SONGCHARTER_HOME/exports/<name>.zip of the song folder (package.zip_folder: the folder itself inside it, to
    extract into Songs), written through a .part file so a download never gets half of one."""
    from .package import zip_folder   # numpy loads with it
    src = Path(song_folder)
    folder = Path(home) / EXPORTS
    folder.mkdir(parents=True, exist_ok=True)
    out = folder / f"{src.name}.zip"
    part = folder / f".{src.name}.zip.{secrets.token_hex(4)}.part"
    try:
        zip_folder(src, part)
        os.replace(part, out)
    finally:
        part.unlink(missing_ok=True)
    return out


def describe(home: Path, documents: Callable[[], Path | None] = documents_songs,
             roots: Callable[[], Iterable[Path]] | None = None) -> dict:
    """{"folder", "windows_path", "source", "under_onedrive", "guess"}: the Songs folder for the page and the
    diagnostics; `guess` (a Windows path) prefills the page's field when none is found. `roots`: the OneDrive
    folders (default wsl.onedrive_roots)."""
    guess = documents()
    folder, source = songs_folder(home, lambda: guess)
    found = folder is not None
    return {"folder": str(folder) if found else None, "windows_path": windows_path(folder),
            "source": source, "under_onedrive": under_onedrive(folder, roots() if roots else None) if found else None,
            "guess": windows_path(guess) if folder is None and guess is not None else None}
