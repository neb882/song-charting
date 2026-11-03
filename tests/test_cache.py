"""The per-user cache (songcharter.cache): where it is on Windows and elsewhere, the work folders' names and keys,
the Windows path lengths a run reaches, and the pruning of old work folders. Only temporary folders are written."""
import hashlib
import json
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
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
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
    """The deepest paths a run creates (cache.DEEPEST: a take's report in the work folder, autochart's mel tables in
    its scratch folder) stay within Windows' 259 characters with a long but real profile, C:\\Users\\<20
    characters>\\AppData\\Local, and a 40-character name. In the work folder autochart's scratch would not."""
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
               "scratch in the work folder": len(str(work / "guitar" / "work" / cache.DEEPEST["scratch"]))}
    assert lengths == {"work": 182, "scratch": 256, "scratch in the work folder": 319}  # the module docstring's
    assert max(lengths["work"], lengths["scratch"]) <= cache.WINDOWS_PATH_MAX < lengths["scratch in the work folder"]
    # the scratch layout is autochart's: our driver's engine-cache folders, and the engine's stem folder name,
    # which it cuts to 32 characters on Windows (demucsWorkspace.cjs stemFolderName)
    sha = "f" * 64
    assert cache.DEEPEST["scratch"] == "\\".join(["engine-cache", "features", "fretformer_demucs_v1", sha,
                                                  "demucs_default", "stems_htdemucs_6s", f"audio_{sha}"[:32],
                                                  "mel-tables.bin"])
    assert len(cache.DEEPEST["work"]) == 63 and len(cache.DEEPEST["scratch"]) == 188


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
        "failed": [], "bytes_after": 0, "kept": {"current": 0, "recent": 0, "pinned": 0}}


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


def test_a_folder_that_cannot_be_deleted_stays_with_a_warning(tmp_path, monkeypatch):
    """A deletion that fails (a file in use on Windows) is warned about and skipped; the next folder goes in its
    place, the half-deleted one keeps its marker, and the next prune takes it."""
    root = tmp_path / "cache"
    busy = folder(root, "aaaaaaaa-a", NOW - 5 * DAY, 400 * K)
    nxt = folder(root, "bbbbbbbb-b", NOW - 3 * DAY, 300 * K)
    (busy / "decode.wav").write_bytes(b"\0" * 100 * K)
    real = shutil.rmtree

    def rmtree(path, *a, **k):
        if Path(path) == busy / "stems":
            raise PermissionError(13, "The process cannot access the file because it is being used by another "
                                      "process", str(busy / "stems" / "a.wav"))
        return real(path, *a, **k)

    monkeypatch.setattr(cache.shutil, "rmtree", rmtree)
    warned = []
    report = cache.prune(root, 500 * K, now=NOW, warn=warned.append)
    assert len(warned) == 1 and str(busy) in warned[0] and "PermissionError" in warned[0] and "stays" in warned[0]
    assert report["failed"][0]["folder"] == str(busy) and not nxt.exists()
    assert busy.exists() and cache.read_marker(busy) is not None and (busy / "stems" / "a.wav").exists()
    assert report["bytes_after"] == cache.tree_size(busy) and 400 * K < cache.tree_size(busy) < 401 * K  # what is
    assert not (busy / "decode.wav").exists()  # left of it: its stems and its marker
    monkeypatch.setattr(cache.shutil, "rmtree", real)
    assert [Path(d["folder"]) for d in cache.prune(root, 0, now=NOW)["deleted"]] == [busy] and not busy.exists()


def test_tree_size_and_size_text(tmp_path):
    (tmp_path / "a" / "b").mkdir(parents=True)
    (tmp_path / "a" / "x").write_bytes(b"1" * 10)
    (tmp_path / "a" / "b" / "y").write_bytes(b"1" * 32)
    assert cache.tree_size(tmp_path / "a") == 42 and cache.tree_size(tmp_path / "missing") == 0
    assert cache.size_text(812_345_678) == "812 MB" and cache.size_text(1_234_567_890) == "1.23 GB"
