"""The per-user cache (songcharter.cache): where it is on Windows and elsewhere, the work folders' names and keys,
the Windows path lengths a run reaches, and the pruning of old work folders. Only temporary folders are written."""
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path, PureWindowsPath

import pytest

from songcharter import cache
from songcharter.engines import adtof
from songcharter.errors import InputError

DAY = 24 * 3600
NOW = 2_000_000_000.0
K = 1000


def test_the_cache_on_windows_and_elsewhere(tmp_path, monkeypatch):
    """%LOCALAPPDATA%\\songcharter on Windows, $XDG_CACHE_HOME/songcharter or ~/.cache/songcharter elsewhere;
    $SONGCHARTER_CACHE moves the work folders only, and the weights keep their folder and $SONGCHARTER_MODELS."""
    for key in ("SONGCHARTER_CACHE", "SONGCHARTER_MODELS", "XDG_CACHE_HOME", "LOCALAPPDATA"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))  # the home folder Path.home() gives elsewhere,
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "home"))  # and on Windows, which never reads HOME
    local = "C:\\Users\\Ann\\AppData\\Local"
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setenv("LOCALAPPDATA", local)
    assert cache.user_cache() == cache.cache_root() == Path(local) / "songcharter"
    assert adtof.models_dir() == Path(local) / "songcharter" / "models"
    monkeypatch.delenv("LOCALAPPDATA")  # as models_dir() did: no LOCALAPPDATA, the POSIX rule
    assert cache.user_cache() == tmp_path / "home" / ".cache" / "songcharter"
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setenv("LOCALAPPDATA", local)  # ignored off Windows
    assert cache.user_cache() == tmp_path / "home" / ".cache" / "songcharter"
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "xdg"))
    assert cache.cache_root() == tmp_path / "xdg" / "songcharter"
    assert adtof.models_dir() == tmp_path / "xdg" / "songcharter" / "models"
    monkeypatch.setenv("SONGCHARTER_CACHE", str(tmp_path / "elsewhere"))
    assert cache.cache_root() == tmp_path / "elsewhere"
    assert adtof.models_dir() == tmp_path / "xdg" / "songcharter" / "models"  # not moved by SONGCHARTER_CACHE
    monkeypatch.setenv("SONGCHARTER_MODELS", str(tmp_path / "m"))
    assert adtof.models_dir() == tmp_path / "m"


@pytest.mark.parametrize("stem,name", [
    ("Take Me Out", "Take Me Out"),
    ("Beyoncé – Déjà Vu", "Beyonce - Deja Vu"),                      # accents and an en dash folded
    ("Straße Œuvre Ｆｕｌｌ", "Strasse OEuvre Full"),                  # letters NFKD keeps whole; full width
    ("Don’t “Stop”", "Don't 'Stop'"),
    ('AC/DC: "Back in Black"?', "AC_DC_ _Back in Black__"),           # Windows' reserved characters
    ("a\tb\x00c\u200bd", "a_b_cd"),                                   # control characters; a zero-width space
    ("気持ち悪い", "気持ち悪い"),                                       # no ASCII form: kept
    ("  ...hidden. . ", "hidden"),                                    # no leading or trailing dots or spaces
    ("", "song"), ("  . ", "song"),
    ("CON", "_CON"), ("nul.txt", "_nul.txt"), ("Com1", "_Com1"), ("COM¹", "_COM1"), ("LPT0 ", "_LPT0"),
    ("conout$", "_conout$"), ("aux .mp3", "_aux .mp3"), ("CONSOLE", "CONSOLE"), ("con-artist", "con-artist"),
    ("x" * 100, "x" * 40),
    ("é" * 50, "e" * 40),
    ("🎸" * 30, "🎸" * 20),                                            # 2 UTF-16 units each, as Windows counts
    ("a" * 39 + "🎸", "a" * 39),                                       # the emoji would make 41
    ("a" * 39 + ". b", "a" * 39),                                     # no trailing dot after the cut either
    ("CON." + "x" * 60, "_CON." + "x" * 35),                          # 40 with the "_"
])
def test_safe_names(stem, name):
    assert cache.safe_name(stem) == name
    units = len(name.encode("utf-16-le")) // 2
    assert units <= cache.NAME_MAX and name == name.strip(" .") and not set(name) & set('<>:"/\\|?*')


def test_the_key_and_the_folders(tmp_path):
    """The key is the song file's SHA-256, its first 16 hex characters: the same bytes under another name or in
    another folder give the same key; the work folder is <cache>/work/<name>-<key>, the scratch <cache>/ac/<8 hex>."""
    a = tmp_path / "a.mp3"
    a.write_bytes(b"\x00\x01" * 300_000)
    (tmp_path / "x").mkdir()
    b = tmp_path / "x" / "Other name.mp3"
    shutil.copy(a, b)
    key = hashlib.sha256(a.read_bytes()).hexdigest()[:16]
    assert cache.file_key(a) == cache.file_key(b) == key
    b.write_bytes(b.read_bytes() + b"\x00")
    assert cache.file_key(b) != key
    assert cache.work_folder(tmp_path, "CON", key) == tmp_path / "work" / f"_CON-{key}"
    assert cache.scratch_folder(tmp_path, key) == tmp_path / "ac" / key[:8]


def test_windows_paths_stay_under_260_characters(monkeypatch):
    """The deepest files a run leaves (cache.DEEPEST: a take's report in the work folder, autochart's mel tables in
    its scratch folder) stay within Windows' 259 characters with a long but real profile, C:\\Users\\<20
    characters>\\AppData\\Local, and a 40-character name. In the work folder autochart's scratch would not. The
    staging files autochart writes them through go past 259 on any profile (only Node, which takes long paths,
    writes them), and so does nothing in the trash a prune moves folders into."""
    local = "C:\\Users\\" + "u" * 20 + "\\AppData\\Local"
    monkeypatch.delenv("SONGCHARTER_CACHE", raising=False)
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setenv("LOCALAPPDATA", local)
    key = "0123456789abcdef"
    root = PureWindowsPath(str(cache.cache_root()))  # Path(...) / "songcharter" here: one separator either way
    assert str(root) == local + "\\songcharter"
    work = root / "work" / f"{cache.safe_name('ü' * 200)}-{key}"
    scratch = root / "ac" / key[:cache.SCRATCH_HEX]
    assert str(work) == str(PureWindowsPath(str(cache.work_folder(cache.cache_root(), "ü" * 200, key))))
    lengths = {"work": len(str(work / cache.DEEPEST["work"])), "scratch": len(str(scratch / cache.DEEPEST["scratch"])),
               "scratch in the work folder": len(str(work / "guitar" / "work" / cache.DEEPEST["scratch"])),
               "staging": len(str(scratch / cache.DEEPEST["staging"])),
               "staging, C:\\Users\\X": len(str(PureWindowsPath("C:\\Users\\X\\AppData\\Local\\songcharter\\ac")
                                                / key[:cache.SCRATCH_HEX] / cache.DEEPEST["staging"])),
               "scratch in the trash": len(str(root / cache.TRASH / "99" / cache.DEEPEST["scratch"]))}
    assert lengths == {"work": 182, "scratch": 256, "scratch in the work folder": 319, "staging": 309,
                       "staging, C:\\Users\\X": 290, "scratch in the trash": 253}  # the module docstring's
    assert max(lengths["work"], lengths["scratch"], lengths["scratch in the trash"]) <= cache.WINDOWS_PATH_MAX
    assert cache.WINDOWS_PATH_MAX < min(lengths["scratch in the work folder"], lengths["staging, C:\\Users\\X"])
    # the scratch layout is autochart's: our driver's engine-cache folders, and the engine's stem folder name,
    # which it cuts to 32 characters on Windows (demucsWorkspace.cjs stemFolderName); its staging files are
    # .<name>.tmp-<pid>-<uuid> beside their target (fileSafety.cjs writeVerifiedAtomic): 235 characters for the mel
    # tables' with a 4-digit pid in a real take [review's trace], here with a 10-digit one
    sha = "f" * 64
    folder = ["engine-cache", "features", "fretformer_demucs_v1", sha, "demucs_default", "stems_htdemucs_6s",
              f"audio_{sha}"[:32]]
    assert cache.DEEPEST["scratch"] == "\\".join(folder + ["mel-tables.bin"])
    uuid = "94ff8f5f-30ad-4bf2-90f5-3c877e436d24"
    assert len(cache.DEEPEST["staging"]) == len("\\".join(folder + [f".mel-tables.bin.tmp-6477-{uuid}"])) + 6 == 241
    assert len(cache.DEEPEST["work"]) == 63 and len(cache.DEEPEST["scratch"]) == 188


def test_deletion_paths_on_windows_take_the_long_form():
    """prune deletes through Windows' extended-length paths, which go past 259 characters without long paths
    turned on (a staging file a killed run left in autochart's scratch folder); elsewhere paths stay as they are."""
    assert cache.long_path("C:\\Users\\Ann\\AppData\\Local\\songcharter\\trash\\0", windows=True) == (
        "\\\\?\\C:\\Users\\Ann\\AppData\\Local\\songcharter\\trash\\0")
    assert cache.long_path("\\\\server\\share\\songcharter\\trash\\0", windows=True) == (
        "\\\\?\\UNC\\server\\share\\songcharter\\trash\\0")
    assert cache.long_path("\\\\?\\C:\\x", windows=True) == "\\\\?\\C:\\x"
    assert cache.long_path("C:/a/b/../c", windows=True) == "\\\\?\\C:\\a\\c"  # normalised first: Windows does not
    # normalise a path in that form
    assert cache.long_path(Path("/home/ann/x"), windows=False) == "/home/ann/x"
    if sys.platform != "win32":
        assert cache.long_path("/home/ann/x") == "/home/ann/x"


def test_the_budget(monkeypatch):
    monkeypatch.delenv("SONGCHARTER_CACHE_GB", raising=False)
    assert cache.budget_bytes() == 5 * 10 ** 9
    for text, want in (("2.5", 2_500_000_000), ("0", 0), (" 12 ", 12 * 10 ** 9)):
        monkeypatch.setenv("SONGCHARTER_CACHE_GB", text)
        assert cache.budget_bytes() == want, text
    for text in ("abc", "-1", "nan", "inf", "5GB"):
        monkeypatch.setenv("SONGCHARTER_CACHE_GB", text)
        with pytest.raises(InputError, match="SONGCHARTER_CACHE_GB"):
            cache.budget_bytes()


# ------------------------------------------------------------------------------------------------ pruning

def folder(root: Path, name: str, used: float, size: int, *, scratch: int | None = None, pinned: bool = False,
           marker: bool = True, scratch_name: str | None = None) -> Path:
    """A work folder of `size` bytes, marked as used at `used`, with a scratch folder of `scratch` bytes."""
    f = root / "work" / name
    (f / "stems").mkdir(parents=True)
    (f / "stems" / "a.wav").write_bytes(b"\0" * size)
    s = None
    if scratch is not None:
        s = root / "ac" / (scratch_name or name[:8])
        (s / "engine-cache").mkdir(parents=True, exist_ok=True)
        (s / "engine-cache" / f"{name}.bin").write_bytes(b"\0" * scratch)
    if marker:
        cache.mark(f, Path(f"{name}.flac"), name, s, pinned=pinned, now=used)
    return f


def test_mark_and_read_the_marker(tmp_path):
    (tmp_path / "w").mkdir()
    data = cache.mark(tmp_path / "w", Path("song.flac"), "k" * 16, tmp_path / "ac" / "kkkkkkkk", now=NOW)
    assert cache.read_marker(tmp_path / "w") == data and data["used"] == NOW and not data["pinned"]
    assert data["used_at"] == "2033-05-18T03:33:20Z" and not (tmp_path / "w" / f"{cache.MARKER}.part").exists()
    (tmp_path / "x").mkdir()
    assert cache.read_marker(tmp_path / "x") is None
    (tmp_path / "x" / cache.MARKER).write_text('{"someone": "else"}')
    assert cache.read_marker(tmp_path / "x") is None
    (tmp_path / "x" / cache.MARKER).write_text("not json")
    assert cache.read_marker(tmp_path / "x") is None


def test_prune_deletes_the_least_recently_used_until_the_rest_fits(tmp_path):
    """Oldest first, scratch folder and all, until the marked folders fit the budget; never the current run's, one
    used in the last 24 hours, one a --work run used, or a folder without our marker, however old."""
    root = tmp_path / "cache"
    a = folder(root, "aaaaaaaa-a", NOW - 5 * DAY, 400 * K, scratch=50 * K)
    b = folder(root, "bbbbbbbb-b", NOW - 3 * DAY, 300 * K)
    c = folder(root, "cccccccc-c", NOW - 2 * DAY, 200 * K)
    recent = folder(root, "dddddddd-d", NOW - 23 * 3600, 500 * K)
    current = folder(root, "eeeeeeee-e", NOW - 10 * DAY, 100 * K, scratch=10 * K)
    pinned = folder(root, "ffffffff-f", NOW - 20 * DAY, 100 * K, pinned=True)
    foreign = folder(root, "gggggggg-g", NOW - 30 * DAY, 1000 * K, marker=False)
    (root / "work" / "a file").write_text("not a folder")
    size = {f.name: cache.tree_size(f) + cache.tree_size(root / "ac" / f.name[:8])
            for f in (a, b, c, recent, current, pinned)}  # each with its marker (a few hundred bytes)
    warned = []
    report = cache.prune(root, 1000 * K, keep=[current], now=NOW, warn=warned.append)
    assert [Path(d["folder"]).name for d in report["deleted"]] == ["aaaaaaaa-a", "bbbbbbbb-b"] and warned == []
    assert not a.exists() and not b.exists() and not (root / "ac" / "aaaaaaaa").exists()
    assert all(f.exists() for f in (c, recent, current, pinned, foreign)) and (root / "ac" / "eeeeeeee").exists()
    assert report["bytes_before"] == sum(size.values()) > 1650 * K
    assert report["bytes_after"] == sum(size.values()) - size["aaaaaaaa-a"] - size["bbbbbbbb-b"] <= 1000 * K
    assert report["folders"] == 6 and report["kept"] == {"current": 1, "recent": 1, "pinned": 1}
    assert report["deleted"][0]["bytes"] == size["aaaaaaaa-a"] and report["deleted"][0]["used_at"].endswith("Z")
    # a budget of 0 takes every folder it may, and still none of the others
    report = cache.prune(root, 0, keep=[current], now=NOW)
    assert [Path(d["folder"]).name for d in report["deleted"]] == ["cccccccc-c"]
    assert sorted(p.name for p in (root / "work").iterdir()) == ["a file", "dddddddd-d", "eeeeeeee-e", "ffffffff-f",
                                                                 "gggggggg-g"]
    # within the budget nothing goes; an empty or missing cache is no error
    assert cache.prune(root, 10 ** 9, now=NOW)["deleted"] == []
    assert cache.prune(tmp_path / "nothing", 0, now=NOW) == {
        "root": str(tmp_path / "nothing"), "budget_bytes": 0, "folders": 0, "bytes_before": 0, "deleted": [],
        "failed": [], "swept": [], "trash_left": [], "bytes_after": 0, "kept": {"current": 0, "recent": 0, "pinned": 0}}
    # every folder went whole into the trash first, and nothing is left of it there
    assert sorted(p.name for p in (root / cache.TRASH).iterdir()) == [cache.TRASH_MARKER]


def test_prune_leaves_a_scratch_folder_it_does_not_own(tmp_path):
    """A scratch folder two keys share stays while a kept folder uses it; a marker naming a folder outside
    <cache>/ac (edited, or from another cache) never gets that folder deleted."""
    root = tmp_path / "cache"
    old = folder(root, "12345678aa-1", NOW - 9 * DAY, 100, scratch=10, scratch_name="12345678")
    folder(root, "12345678bb-2", NOW - 1 * 3600, 100, scratch=10, scratch_name="12345678")
    outside = tmp_path / "precious"
    outside.mkdir()
    (outside / "keep.txt").write_text("mine")
    stray = folder(root, "99999999-9", NOW - 9 * DAY, 100)
    data = json.loads((stray / cache.MARKER).read_text())
    (stray / cache.MARKER).write_text(json.dumps({**data, "scratch": str(outside)}))
    cache.prune(root, 0, now=NOW)
    assert not old.exists() and not stray.exists() and (root / "ac" / "12345678").is_dir()
    assert (outside / "keep.txt").read_text() == "mine"


IN_USE = "The process cannot access the file because it is being used by another process"


def in_use(monkeypatch, name: str, folders: tuple[Path, ...] = ()):
    """Windows with a program holding a file open: no file called `name` can be deleted (rmtree unlinks by name),
    and none of `folders`, the folders it is in, can be moved."""
    real_rename, real_unlink = os.rename, os.unlink

    def rename(src, dst, *a, **k):
        if Path(src) in folders:
            raise PermissionError(13, IN_USE, str(src))
        return real_rename(src, dst, *a, **k)

    def unlink(path, *a, **k):
        if Path(path).name == name:
            raise PermissionError(13, IN_USE, str(path))
        return real_unlink(path, *a, **k)

    monkeypatch.setattr(os, "rename", rename)
    monkeypatch.setattr(os, "unlink", unlink)


def stems_folder(work: Path) -> Path:
    """A separation cache in a work folder, as separate.py writes it: the stems, then info.json listing them."""
    s = work / "stems" / "8300680adecc2622b6f6a464"
    s.mkdir(parents=True)
    for name in ("bass", "drums", "guitar", "other", "piano", "vocals"):
        (s / f"{name}.wav").write_bytes(b"\0" * 1000)
    (s / "info.json").write_text(json.dumps({"stems": ["bass", "drums", "guitar", "other", "piano", "vocals"]}))
    return s


def test_a_folder_that_cannot_be_deleted_stays_whole_with_a_warning(tmp_path, monkeypatch):
    """A folder that cannot be moved to the trash (on Windows, a file in it in use) stays whole: no file of it is
    deleted, so its caches stay true (its stems' info.json lists only stems that are there), and its marker stays.
    It is warned about and skipped, the next folder goes in its place, and the next prune takes it."""
    root = tmp_path / "cache"
    busy = folder(root, "aaaaaaaa-a", NOW - 5 * DAY, 400 * K, scratch=10 * K)
    nxt = folder(root, "bbbbbbbb-b", NOW - 3 * DAY, 300 * K)
    (busy / "decode.wav").write_bytes(b"\0" * 100 * K)
    stems = stems_folder(busy)
    files = sorted(p.relative_to(busy) for p in busy.rglob("*"))
    in_use(monkeypatch, "guitar.wav", (busy, busy / "stems", stems))
    warned = []
    report = cache.prune(root, 500 * K, now=NOW, warn=warned.append)
    assert len(warned) == 1 and str(busy) in warned[0] and IN_USE in warned[0]
    assert warned[0].endswith(": it stays, and the next run tries again")
    assert report["failed"][0]["folder"] == str(busy) and [d["folder"] for d in report["deleted"]] == [str(nxt)]
    assert sorted(p.relative_to(busy) for p in busy.rglob("*")) == files and cache.read_marker(busy) is not None
    assert not (root / "ac" / "aaaaaaaa").exists()  # its scratch folder went first, and the marker no longer finds it
    assert report["bytes_after"] == cache.tree_size(busy) and 501 * K < cache.tree_size(busy) < 510 * K
    monkeypatch.undo()
    assert [Path(d["folder"]) for d in cache.prune(root, 0, now=NOW)["deleted"]] == [busy] and not busy.exists()
    assert sorted(p.name for p in (root / cache.TRASH).iterdir()) == [cache.TRASH_MARKER]


def test_what_cannot_be_deleted_in_the_trash_goes_with_the_next_prune(tmp_path, monkeypatch):
    """Once a folder is in the trash, a deletion that stops partway (a file in use there, or only its last rmdir
    failing, as for a console's current folder) leaves nothing in the work folders that a run would trust: the
    rest waits in the trash, with a warning, and the next prune deletes it before anything else."""
    root = tmp_path / "cache"
    a = folder(root, "aaaaaaaa-a", NOW - 5 * DAY, 400 * K, scratch=10 * K)
    b = folder(root, "bbbbbbbb-b", NOW - 4 * DAY, 300 * K)
    stems_folder(a)
    in_use(monkeypatch, "guitar.wav")  # opened once a was in the trash (its scratch folder first, then a)
    went, real_aside, real_rmdir = {}, cache._aside, os.rmdir

    def aside(path, trash):
        went[path] = real_aside(path, trash)
        return went[path]

    def rmdir(path, *args, **kw):  # b's own folder cannot go, when the files in it can
        if b in went and Path(path) == went[b]:
            raise PermissionError(32, IN_USE, str(path))
        return real_rmdir(path, *args, **kw)

    monkeypatch.setattr(cache, "_aside", aside)
    monkeypatch.setattr(os, "rmdir", rmdir)
    warned = []
    report = cache.prune(root, 0, now=NOW, warn=warned.append)
    assert [Path(d["folder"]) for d in report["deleted"]] == [a, b] and report["failed"] == []
    assert sorted(p.name for p in (root / "work").iterdir()) == [] and not (root / "ac" / "aaaaaaaa").exists()
    trash = root / cache.TRASH
    assert went == {root / "ac" / "aaaaaaaa": trash / "0", a: trash / "1", b: trash / "0"}  # 0 was free again
    assert [Path(t["entry"]) for t in report["trash_left"]] == [trash / "1", trash / "0"] and len(warned) == 2
    assert all(w.endswith("and the next run deletes it") for w in warned) and str(trash / "1") in warned[0]
    assert (trash / "1" / "stems" / "8300680adecc2622b6f6a464" / "guitar.wav").is_file()
    assert sorted(p.name for p in trash.iterdir()) == ["0", "1", cache.TRASH_MARKER]
    assert list((trash / "0").iterdir()) == []
    monkeypatch.undo()
    report = cache.prune(root, 0, now=NOW)
    assert [Path(s["entry"]) for s in report["swept"]] == [trash / "0", trash / "1"] and report["trash_left"] == []
    assert report["swept"][1]["bytes"] >= 1000 and sorted(p.name for p in trash.iterdir()) == [cache.TRASH_MARKER]


def test_a_run_that_starts_while_prune_deletes_keeps_its_folder(tmp_path, monkeypatch):
    """prune reads each folder's marker again just before it moves the folder out, and once more where it moved it:
    a run that marked an old folder as used after the scan (it started on that song meanwhile) keeps the folder,
    whole and in place, with its scratch folder."""
    root = tmp_path / "cache"
    a = folder(root, "aaaaaaaa-a", NOW - 5 * DAY, 300 * K)
    b = folder(root, "bbbbbbbb-b", NOW - 4 * DAY, 300 * K, scratch=10 * K)
    c = folder(root, "cccccccc-c", NOW - 3 * DAY, 300 * K, scratch=10 * K)
    files = {f: sorted(p.relative_to(f) for p in f.rglob("*")) for f in (b, c)}
    real = cache._aside
    moved = []

    def aside(path, trash):
        if path == a:  # while a goes, a run starts on b's song
            cache.mark(b, Path("b.flac"), "b", root / "ac" / "bbbbbbbb", now=NOW + 1)
        if path == c:  # and one on c's, after prune read c's marker again
            cache.mark(c, Path("c.flac"), "c", root / "ac" / "cccccccc", now=NOW + 2)
        moved.append(path)
        return real(path, trash)

    monkeypatch.setattr(cache, "_aside", aside)
    report = cache.prune(root, 0, now=NOW)
    assert [Path(d["folder"]) for d in report["deleted"]] == [a] and report["kept"]["recent"] == 2
    assert moved == [a, root / "ac" / "cccccccc", c]  # b was never touched; c went, and came back
    for f in (b, c):
        assert sorted(p.relative_to(f) for p in f.rglob("*")) == files[f] and cache.read_marker(f)["used"] > NOW
        assert (root / "ac" / f.name[:8] / "engine-cache" / f"{f.name}.bin").is_file()
    assert sorted(p.name for p in (root / cache.TRASH).iterdir()) == [cache.TRASH_MARKER]


def test_a_trash_folder_that_is_not_ours_is_left_alone(tmp_path):
    """$SONGCHARTER_CACHE pointing where a `trash` folder of the person's is: nothing is moved into it or deleted
    from it, and nothing is pruned (one warning)."""
    root = tmp_path / "cache"
    a = folder(root, "aaaaaaaa-a", NOW - 5 * DAY, 300 * K)
    (root / cache.TRASH / "0").mkdir(parents=True)
    (root / cache.TRASH / "0" / "keep.txt").write_text("mine")
    warned = []
    report = cache.prune(root, 0, now=NOW, warn=warned.append)
    assert report["deleted"] == [] and a.exists() and (root / cache.TRASH / "0" / "keep.txt").read_text() == "mine"
    assert len(warned) == 1 and "is not songcharter's" in warned[0]
    assert sorted(p.name for p in (root / cache.TRASH).iterdir()) == ["0"]


def test_tree_size_and_size_text(tmp_path):
    (tmp_path / "a" / "b").mkdir(parents=True)
    (tmp_path / "a" / "x").write_bytes(b"1" * 10)
    (tmp_path / "a" / "b" / "y").write_bytes(b"1" * 32)
    assert cache.tree_size(tmp_path / "a") == 42 and cache.tree_size(tmp_path / "missing") == 0
    assert cache.size_text(812_345_678) == "812 MB" and cache.size_text(1_234_567_890) == "1.23 GB"
