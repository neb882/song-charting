"""songcharter.clonehero on temporary folders, with stand-ins for the wsl functions: where the Songs folder is found,
saving one (a Windows path, a missing or unwritable folder), the install (409, a replace of our own folder, another
charter's refused, renames retried, Blocked), OneDrive, Windows' names for paths, and the zip. Nothing here needs
Windows."""
import errno
import json
import os
import shutil
import zipfile
from pathlib import Path

import pytest

from songcharter import clonehero as C
from songcharter import wsl
from songcharter.errors import InputError

FILES = ("notes.chart", "song.ini", "song.ogg", "report.json")
NAME = "Zorp Blen - Quiv Dree"


def built(root: Path, name: str = NAME, charter: str = "songcharter", body: str = "v1") -> Path:
    """A song folder as songcharter builds it (the four files; song.ogg is only its header and a word)."""
    folder = root / name
    folder.mkdir(parents=True)
    (folder / "notes.chart").write_text(f"[Song]\r\n{{\r\n  Name = \"{body}\"\r\n}}\r\n", encoding="utf-8")
    (folder / "song.ini").write_text(f"[song]\r\nname = Quiv Dree\r\ncharter = {charter}\r\n", encoding="utf-8")
    (folder / "song.ogg").write_bytes(b"OggS" + body.encode())
    (folder / "report.json").write_text(json.dumps({"gate": {"ok": True}, "body": body}), encoding="utf-8")
    return folder


@pytest.fixture
def windows(tmp_path, monkeypatch):
    """WSL with C: under tmp_path/mnt/c, Documents in the registry at C:\\Users\\Jorg\\OneDrive\\Documents (moved by
    OneDrive), and OneDrive's root named by Windows."""
    mnt = tmp_path / "mnt"
    c = mnt / "c"
    docs = c / "Users" / "Jorg" / "OneDrive" / "Documents"
    docs.mkdir(parents=True)
    monkeypatch.setattr(wsl, "MNT_C", c)
    monkeypatch.setattr(wsl, "is_wsl", lambda: True)
    monkeypatch.setattr(wsl, "distro", lambda: "Ubuntu")
    asked = []

    def to_linux(winpath):
        asked.append(winpath)
        if len(winpath) >= 3 and winpath[1] == ":" and winpath[2] in "\\/":
            return mnt / winpath[0].lower() / Path(*winpath[3:].replace("\\", "/").split("/"))
        return None

    monkeypatch.setattr(wsl, "to_linux", to_linux)
    monkeypatch.setattr(wsl, "shell_folder", lambda name: docs if name == "Personal" else None)
    monkeypatch.setattr(wsl, "onedrive_roots", lambda: [c / "Users" / "Jorg" / "OneDrive"])
    home = tmp_path / "home"
    home.mkdir()
    return type("W", (), {"mnt": mnt, "c": c, "docs": docs, "home": home, "asked": asked})


# ------------------------------------------------------------------------------------------------ where

def test_the_songs_folder_is_found_in_order(windows, tmp_path):
    home = windows.home
    assert C.songs_folder(home) == (None, "not found")   # Documents has no Clone Hero/Songs yet
    songs = windows.docs / "Clone Hero" / "Songs"
    songs.mkdir(parents=True)
    assert C.songs_folder(home) == (songs, "documents")
    saved = tmp_path / "elsewhere" / "Songs"
    saved.mkdir(parents=True)
    C.write_ui(home, {C.KEY: str(saved), "other": 1})
    assert C.songs_folder(home) == (saved, "saved")
    shutil.rmtree(saved)   # a saved folder that went: Documents again
    assert C.songs_folder(home) == (songs, "documents")
    (home / "ui.json").write_text("not json", encoding="utf-8")
    assert C.songs_folder(home) == (songs, "documents") and C.read_ui(home) == {}
    info = C.describe(home)
    assert info == {"folder": str(songs), "windows_path": "C:\\Users\\Jorg\\OneDrive\\Documents\\Clone Hero\\Songs",
                    "source": "documents", "under_onedrive": True, "guess": None}


def test_outside_wsl_only_the_saved_folder(tmp_path, monkeypatch):
    monkeypatch.setattr(wsl, "is_wsl", lambda: False)
    monkeypatch.setattr(wsl, "shell_folder", lambda name: pytest.fail("no registry outside WSL"))
    assert C.songs_folder(tmp_path) == (None, "not found") and C.documents_songs() is None
    assert C.windows_path(tmp_path) is None
    info = C.describe(tmp_path, roots=lambda: [])
    assert info == {"folder": None, "windows_path": None, "source": "not found", "under_onedrive": None, "guess": None}


def test_the_guess_prefills_the_field_when_nothing_is_found(windows):
    info = C.describe(windows.home)
    assert info["folder"] is None and info["source"] == "not found"
    assert info["guess"] == "C:\\Users\\Jorg\\OneDrive\\Documents\\Clone Hero\\Songs"


def test_windows_names_for_paths(windows, tmp_path):
    assert C.windows_path(windows.c / "Users" / "Jorg") == "C:\\Users\\Jorg"
    assert C.windows_path(windows.mnt / "d" / "Games" / "Clone Hero") == "D:\\Games\\Clone Hero"
    assert C.windows_path(windows.c) == "C:\\"
    assert C.windows_path(Path("/home/sc/.local/share/songcharter/exports")) == \
        "\\\\wsl.localhost\\Ubuntu\\home\\sc\\.local\\share\\songcharter\\exports"
    assert C.windows_path(None) is None


# ------------------------------------------------------------------------------------------------ saving one

def test_a_windows_path_is_turned_into_mnt_c(windows):
    songs = windows.docs / "Clone Hero" / "Songs"
    songs.mkdir(parents=True)
    typed = '  "C:\\Users\\Jorg\\OneDrive\\Documents\\Clone Hero\\Songs"  '   # as Explorer's "Copy as path" gives it
    assert C.set_songs_folder(windows.home, typed) == songs
    assert windows.asked == ["C:\\Users\\Jorg\\OneDrive\\Documents\\Clone Hero\\Songs"]
    assert C.read_ui(windows.home) == {C.KEY: str(songs)}
    assert C.songs_folder(windows.home) == (songs, "saved")
    assert not list(songs.iterdir()) and not list(windows.home.glob("*.part"))   # the probe went, so did ui.json's .part
    # a Linux path as it is; other settings in ui.json stay
    C.write_ui(windows.home, {**C.read_ui(windows.home), "theme": "dark"})
    other = windows.c / "Games" / "Songs"
    other.mkdir(parents=True)
    assert C.set_songs_folder(windows.home, str(other)) == other
    assert C.read_ui(windows.home) == {C.KEY: str(other), "theme": "dark"}


@pytest.mark.parametrize("typed, why", [
    ("C:\\Users\\Jorg\\Documents\\Clone Hero\\Songs", "does not exist"),
    ("/nowhere/Clone Hero/Songs", "does not exist"),
    ("Clone Hero/Songs", "is not a whole path"),
    ("   ", "give the Songs folder's path"),
    ("\\\\server\\share\\Songs", "WSL could not turn it"),
])
def test_a_missing_folder_is_refused(windows, typed, why):
    with pytest.raises(InputError, match=why):
        C.set_songs_folder(windows.home, typed)
    assert not (windows.home / "ui.json").exists()


def test_a_folder_that_cannot_be_written_is_refused(windows, monkeypatch):
    songs = windows.docs / "Clone Hero" / "Songs"
    songs.mkdir(parents=True)
    real = Path.write_bytes

    def refuse(self, data):
        if self.name.startswith(".songcharter-probe-"):
            raise PermissionError(errno.EACCES, "Permission denied")
        return real(self, data)

    monkeypatch.setattr(Path, "write_bytes", refuse)
    with pytest.raises(InputError, match="cannot write into .*Permission denied"):
        C.set_songs_folder(windows.home, str(songs))
    assert not (windows.home / "ui.json").exists() and not list(songs.iterdir())


# ------------------------------------------------------------------------------------------------ installing

def contents(folder: Path) -> dict:
    return {p.name: p.read_bytes() for p in sorted(folder.iterdir())}


def no_temporaries(songs: Path) -> bool:
    return not [p for p in songs.iterdir() if p.name.startswith(".")]


def test_install_then_409_then_replace_our_own(tmp_path):
    home, songs = tmp_path / "home", tmp_path / "Songs"
    songs.mkdir()
    v1 = built(tmp_path / "library1")
    done = C.install(v1, songs, home, now=1_700_000_000)
    assert done.target == songs / NAME and done.replaced is None and done.note is None
    assert contents(done.target) == contents(v1) and sorted(contents(done.target)) == sorted(FILES)
    assert no_temporaries(songs)
    with pytest.raises(C.Exists) as e:
        C.install(v1, songs, home)
    assert e.value.ours is True and e.value.target == songs / NAME
    v2 = built(tmp_path / "library2", body="v2")
    done = C.install(v2, songs, home, replace=True, now=1_700_000_000)
    assert contents(songs / NAME) == contents(v2)
    stamp = done.replaced.parent.name
    assert done.replaced == home / "replaced" / stamp / NAME and len(stamp) == 15 and stamp[8] == "-"
    assert contents(done.replaced) == contents(v1)   # the older chart, whole
    assert no_temporaries(songs) and sorted(p.name for p in songs.iterdir()) == [NAME]


@pytest.mark.parametrize("make", ["another charter", "no report.json", "a file"])
def test_a_folder_songcharter_did_not_make_is_never_replaced(tmp_path, make):
    home, songs = tmp_path / "home", tmp_path / "Songs"
    songs.mkdir()
    if make == "another charter":
        built(songs, charter="Harmonix")
    elif make == "no report.json":
        built(songs)
        (songs / NAME / "report.json").unlink()
    else:
        (songs / NAME).write_text("x")
    before = sorted(str(p) for p in songs.rglob("*"))
    src = built(tmp_path / "library")
    for replace in (False, True):
        with pytest.raises(C.Exists) as e:
            C.install(src, songs, home, replace=replace)
        assert e.value.ours is False and "songcharter did not make it" in str(e.value)
    assert sorted(str(p) for p in songs.rglob("*")) == before and not (home / "replaced").exists()


def test_is_ours_reads_song_ini_as_clone_hero_does(tmp_path):
    folder = built(tmp_path)
    assert C.is_ours(folder)
    (folder / "song.ini").write_text("\ufeff[Song]\nName = x\nCHARTER=SongCharter  \n", encoding="utf-8")
    assert C.is_ours(folder)
    (folder / "song.ini").write_text("[song]\ncharter = songcharter fan\n", encoding="utf-8")
    assert not C.is_ours(folder)
    (folder / "song.ini").unlink()
    assert not C.is_ours(folder)


def test_the_copy_has_no_copystat(tmp_path, monkeypatch):
    """drvfs under /mnt/c refuses the timestamps and modes copystat sets: the copy must not call it."""
    def refuse(*a, **k):
        raise PermissionError(errno.EPERM, "Operation not permitted")

    for name in ("copystat", "copy2", "copymode", "copytree"):
        monkeypatch.setattr(shutil, name, refuse)
    songs = tmp_path / "Songs"
    songs.mkdir()
    src = built(tmp_path / "library")
    (src / "extra").mkdir()
    (src / "extra" / "album.png").write_bytes(b"png")
    done = C.install(src, songs, tmp_path / "home")
    assert (done.target / "song.ogg").read_bytes() == b"OggSv1" and (done.target / "extra" / "album.png").read_bytes() == b"png"


def failing_rename(failures: int = 0, err: int = errno.EBUSY, kind=OSError, aside: int = 0, back: int = 0):
    """os.rename that refuses, with `err`, the rename into place (a .tmp to the target) `failures` times, the rename
    of the older chart aside (the target to a .old) `aside` times, and its put-back (a .old to the target) `back`
    times; then renames."""
    calls = []
    refusals = {"into place": failures, "aside": aside, "back": back}
    seen = dict.fromkeys(refusals, 0)

    def rename(src, dst):
        s, d = Path(src).name, Path(dst).name
        calls.append((s, d))
        which = "into place" if s.endswith(".tmp") else "aside" if d.endswith(".old") else "back"
        seen[which] += 1
        if seen[which] <= refusals[which]:
            raise kind(err, os.strerror(err))
        os.rename(src, dst)

    return rename, calls


def test_a_rename_that_fails_three_times_with_ebusy_then_succeeds_installs(tmp_path):
    home, songs = tmp_path / "home", tmp_path / "Songs"
    songs.mkdir()
    rename, calls = failing_rename(3)
    slept = []
    done = C.install(built(tmp_path / "library"), songs, home, rename=rename, sleep=slept.append)
    assert len(calls) == 4 and slept == [C.RENAME_WAIT_S] * 3
    assert sorted(contents(done.target)) == sorted(FILES) and no_temporaries(songs)


@pytest.mark.parametrize("err, kind", [(errno.EBUSY, OSError), (errno.EACCES, PermissionError),
                                       (errno.EPERM, OSError), (errno.EACCES, OSError)])
def test_a_rename_that_always_fails_is_blocked_and_leaves_no_tmp(tmp_path, err, kind):
    home, songs = tmp_path / "home", tmp_path / "Songs"
    songs.mkdir()
    src = built(tmp_path / "library")
    rename, calls = failing_rename(10 ** 6, err, kind)
    slept = []
    with pytest.raises(C.Blocked) as e:
        C.install(src, songs, home, rename=rename, sleep=slept.append)
    assert len(calls) == C.RENAME_TRIES == 10 and sum(slept) == pytest.approx(4.5)   # about 5 s
    assert "the rename into place was refused 10 times" in e.value.why and e.value.target == songs / NAME
    assert list(songs.iterdir()) == []   # no .tmp, nothing half there
    # the server then makes the zip: the song folder itself inside it, ready to extract into Songs
    zipped = C.export_zip(src, home)
    assert zipped == home / "exports" / f"{NAME}.zip"
    with zipfile.ZipFile(zipped) as z:
        assert sorted(z.namelist()) == sorted(f"{NAME}/{f}" for f in FILES)
        assert z.read(f"{NAME}/song.ogg") == b"OggSv1"
    assert [p.name for p in (home / "exports").iterdir()] == [f"{NAME}.zip"]   # no .part left


def test_another_error_is_blocked_at_once(tmp_path):
    songs = tmp_path / "Songs"
    songs.mkdir()
    rename, calls = failing_rename(10 ** 6, errno.ENOSPC)
    with pytest.raises(C.Blocked, match="No space left"):
        C.install(built(tmp_path / "library"), songs, tmp_path / "home", rename=rename, sleep=lambda s: None)
    assert len(calls) == 1 and list(songs.iterdir()) == []


def test_a_copy_windows_refuses_is_blocked(tmp_path, monkeypatch):
    """Controlled Folder Access, say: the first file written is refused."""
    songs = tmp_path / "Songs"
    songs.mkdir()

    def refuse(src, dst, **k):
        raise PermissionError(errno.EACCES, "Permission denied")

    monkeypatch.setattr(shutil, "copyfile", refuse)
    with pytest.raises(C.Blocked, match="writing into the Songs folder failed: Permission denied"):
        C.install(built(tmp_path / "library"), songs, tmp_path / "home", sleep=lambda s: None)
    assert list(songs.iterdir()) == []


def test_a_blocked_replace_keeps_the_older_chart(tmp_path):
    home, songs = tmp_path / "home", tmp_path / "Songs"
    songs.mkdir()
    old = C.install(built(tmp_path / "library1"), songs, home).target
    before = contents(old)
    rename, calls = failing_rename(10 ** 6)
    with pytest.raises(C.Blocked):
        C.install(built(tmp_path / "library2", body="v2"), songs, home, replace=True, rename=rename,
                  sleep=lambda s: None)
    assert calls[0][1].endswith(".old") and calls[-1][0].endswith(".old") and calls[-1][1] == NAME   # put back
    assert contents(songs / NAME) == before and no_temporaries(songs) and not (home / "replaced").exists()


def test_a_songs_folder_with_a_space_and_umlauts(windows):
    songs = windows.c / "Users" / "Jörg" / "Documents" / "Jörg's Söngs" / "Clone Hero" / "Songs"
    songs.mkdir(parents=True)
    saved = C.set_songs_folder(windows.home, "C:\\Users\\Jörg\\Documents\\Jörg's Söngs\\Clone Hero\\Songs")
    assert saved == songs and C.songs_folder(windows.home) == (songs, "saved")
    assert json.loads((windows.home / "ui.json").read_text(encoding="utf-8"))[C.KEY] == str(songs)
    src = built(windows.home / "library", name="Jörg's Bänd - Söng (Live)")
    done = C.install(src, songs, windows.home)
    assert done.target == songs / "Jörg's Bänd - Söng (Live)" and sorted(contents(done.target)) == sorted(FILES)
    assert C.windows_path(done.target) == ("C:\\Users\\Jörg\\Documents\\Jörg's Söngs\\Clone Hero\\Songs\\"
                                           "Jörg's Bänd - Söng (Live)")
    assert C.describe(windows.home)["under_onedrive"] is False


def test_under_onedrive(tmp_path):
    root = tmp_path / "c" / "Users" / "Jorg" / "OneDrive - Contoso"
    roots = [tmp_path / "c" / "Users" / "Jorg" / "OneDrive", root]
    assert C.under_onedrive(root / "Documents" / "Clone Hero" / "Songs", roots)
    assert C.under_onedrive(root, roots)
    assert C.under_onedrive(Path(str(root).lower()) / "Documents", roots)   # drvfs and Windows ignore case
    assert not C.under_onedrive(tmp_path / "c" / "Users" / "Jorg" / "OneDriveX" / "Songs", roots)
    assert not C.under_onedrive(tmp_path / "c" / "Users" / "Jorg" / "Documents", roots)
    assert not C.under_onedrive(root / "Songs", [])


def dot_folders(songs: Path) -> list[str]:
    return sorted(p.name for p in songs.iterdir() if p.name.startswith("."))


def test_the_rename_aside_refused_three_times_then_succeeding(tmp_path):
    home, songs = tmp_path / "home", tmp_path / "Songs"
    songs.mkdir()
    v1 = contents(C.install(built(tmp_path / "library1"), songs, home).target)
    rename, calls = failing_rename(aside=3)
    slept = []
    done = C.install(built(tmp_path / "library2", body="v2"), songs, home, replace=True, rename=rename,
                     sleep=slept.append)
    assert [d.endswith(".old") for _, d in calls] == [True] * 4 + [False] and slept == [C.RENAME_WAIT_S] * 3
    assert contents(done.target)["song.ogg"] == b"OggSv2" and contents(done.replaced) == v1
    assert dot_folders(songs) == [] and done.note is None


def test_the_put_back_refused_three_times_then_succeeding(tmp_path):
    home, songs = tmp_path / "home", tmp_path / "Songs"
    songs.mkdir()
    v1 = contents(C.install(built(tmp_path / "library1"), songs, home).target)
    rename, calls = failing_rename(10 ** 6, back=3)
    slept = []
    with pytest.raises(C.Blocked) as e:
        C.install(built(tmp_path / "library2", body="v2"), songs, home, replace=True, rename=rename,
                  sleep=slept.append)
    assert e.value.old is None and "putting the older chart back" not in e.value.why
    assert [c[0].endswith(".old") for c in calls].count(True) == 4 and len(slept) == 9 + 3
    assert sorted(p.name for p in songs.iterdir()) == [NAME] and contents(songs / NAME) == v1


def test_a_move_to_replaced_that_fails_still_installs_with_a_note(tmp_path, monkeypatch):
    home, songs = tmp_path / "home", tmp_path / "Songs"
    songs.mkdir()
    v1 = contents(C.install(built(tmp_path / "library1"), songs, home).target)

    def refused(src, dst):
        raise OSError(errno.EIO, "Input/output error")

    monkeypatch.setattr(shutil, "move", refused)
    done = C.install(built(tmp_path / "library2", body="v2"), songs, home, replace=True, now=1_700_000_000)
    [old] = dot_folders(songs)
    assert old.endswith(".old") and contents(songs / old) == v1 and contents(done.target)["song.ogg"] == b"OggSv2"
    assert done.replaced is None and done.note.startswith(f"the older chart stays in {songs / old}: moving it into "
                                                          f"{home / 'replaced'} failed (Input/output error)")
    # the next install of that name moves it to replaced/, as the replace would have
    monkeypatch.undo()
    v2 = contents(done.target)
    done = C.install(built(tmp_path / "library3", body="v3"), songs, home, replace=True, now=1_700_000_000)
    assert dot_folders(songs) == [] and contents(done.target)["song.ogg"] == b"OggSv3"
    went = sorted(p for p in (home / "replaced").rglob(NAME))
    assert sorted(contents(p)["song.ogg"] for p in went) == [b"OggSv1", b"OggSv2"]
    assert contents(done.replaced) == v2 and f"an older chart left in Songs went to " in done.note


def test_a_blocked_replace_that_cannot_put_back_names_the_old_folder(tmp_path):
    """The rename into place and the put-back both refused: the older chart stays whole in its .old folder, which
    Blocked names; the next install (a retry) puts the new chart in place and moves the .old to replaced/."""
    home, songs = tmp_path / "home", tmp_path / "Songs"
    songs.mkdir()
    v1 = contents(C.install(built(tmp_path / "library1"), songs, home).target)
    rename, _ = failing_rename(10 ** 6, back=10 ** 6)
    v2 = built(tmp_path / "library2", body="v2")
    with pytest.raises(C.Blocked) as e:
        C.install(v2, songs, home, replace=True, rename=rename, sleep=lambda s: None)
    [old] = dot_folders(songs)   # the .tmp went
    assert e.value.old == songs / old and old.endswith(".old") and contents(songs / old) == v1
    assert "the rename into place was refused 10 times" in e.value.why and str(songs / old) in e.value.why
    assert "putting the older chart back was refused too" in e.value.why and not (songs / NAME).exists()
    done = C.install(v2, songs, home, now=1_700_000_000)   # "try again"
    assert sorted(p.name for p in songs.iterdir()) == [NAME] and contents(done.target)["song.ogg"] == b"OggSv2"
    assert contents(done.replaced) == v1 and done.replaced.parent.parent == home / "replaced"
    assert done.note == f"an older chart left in Songs went to {done.replaced}"


def test_our_own_leftovers_go_and_nothing_else_is_touched(tmp_path):
    """A run that stopped halfway leaves our .old and .tmp: the next install of that name moves the .old to
    replaced/ and deletes the .tmp. Another charter's, a partial copy, another song's, a name that is not ours and a
    link are left as they are."""
    home, songs = tmp_path / "home", tmp_path / "Songs"
    songs.mkdir()
    ours_old = built(songs, name=f".{NAME}.songcharter-0123abcd.old", body="v0")
    built(songs, name=f".{NAME}.songcharter-4567cdef.tmp", body="v1")
    keep = [built(songs, name=f".{NAME}.songcharter-89abcdef.old", charter="Harmonix"),
            built(songs, name=f".Other Song.songcharter-0123abcd.tmp"),
            built(songs, name=f".{NAME}.songcharter-xyz.tmp"),
            built(songs, name=f".{NAME}.songcharter-0123abcd.bak"),
            built(songs, name=f"{NAME}.songcharter-0123abcd.old")]
    partial = songs / f".{NAME}.songcharter-00000000.tmp"
    partial.mkdir()
    (partial / "notes.chart").write_text("x")
    link = songs / f".{NAME}.songcharter-11111111.old"
    link.symlink_to(built(tmp_path / "elsewhere", body="linked"))
    keep += [partial, link]
    before = {p: sorted(x.name for x in p.iterdir()) for p in keep}
    v0 = contents(ours_old)
    done = C.install(built(tmp_path / "library", body="v2"), songs, home, now=1_700_000_000)
    assert contents(done.target)["song.ogg"] == b"OggSv2" and contents(done.replaced) == v0
    assert sorted(p.name for p in songs.iterdir()) == sorted([NAME, *(p.name for p in keep)])
    assert {p: sorted(x.name for x in p.iterdir()) for p in keep} == before
    assert (tmp_path / "elsewhere" / NAME / "song.ogg").read_bytes() == b"OggSlinked"
    assert C.leftovers(songs, NAME) == []
