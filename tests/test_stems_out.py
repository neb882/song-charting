"""M8-12: the stems as files of their own (pipeline `stems`, `songcharter chart --stems`), and Clone Hero's multitrack
audio (guitar.ogg, bass.ogg and drums.ogg from the stems and song.ogg the rest, the default; `one_audio` for one file).
The pipeline runs on test_pipeline's synthetic song with its stand-in engines: no model runs here."""
import errno
import json
import sys
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

import songcharter.pipeline as P
from songcharter import audio as A
from songcharter import listen as LI
from songcharter import package as PK
from songcharter.assemble import audio_file_issues, find_scan_chart
from songcharter.cli import main
from songcharter.errors import InputError

sys.path.insert(0, str(Path(__file__).parent))
from test_pipeline import standin_key, standins, write_song  # noqa: E402

SR = A.SAMPLE_RATE
SPLIT = ["bass.ogg", "drums.ogg", "guitar.ogg", "song.ogg"]
SIX = ["bass.flac", "drums.flac", "guitar.flac", "other.flac", "piano.flac", "vocals.flac"]


def files(folder: Path, suffix: str) -> list[str]:
    return sorted(p.name for p in folder.iterdir() if p.suffix == suffix)


@pytest.fixture(scope="module")
def runs(tmp_path_factory):
    """The song charted three ways in one cache: the defaults (split audio, no stems), the stems on into another
    folder (the separation cached by then), and one audio file into a third."""
    root = tmp_path_factory.mktemp("stems")
    parts = write_song(root / "song.flac")
    out = {}
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("SONGCHARTER_CACHE", str(root / "cache"))
        for name, options in (("split", P.Options()), ("stems", P.Options(stems=True)),
                              ("one", P.Options(one_audio=True))):
            engines = standins()()
            events = []
            result = P.chart(root / "song.flac", root / "out" / name / "Click Song", options, engines=engines,
                             log=lambda line: None, sampler=None, events=events.append)
            out[name] = (result, events)
    return root, parts, out


def test_the_audio_is_split_by_default_and_sums_to_the_one_file(runs):
    """guitar.ogg, bass.ogg and drums.ogg hold their stems, song.ogg the rest; the four summed are the one-file
    song.ogg within the encoder's noise (break: song.ogg the whole mix, or a part's file left out)."""
    root, parts, out = runs
    split, one = out["split"][0], out["one"][0]
    assert split.ok and one.ok
    assert files(split.folder, ".ogg") == SPLIT and files(one.folder, ".ogg") == ["song.ogg"]
    report = split.assembled.report
    assert report["audio_files"] == ["song.ogg", "guitar.ogg", "bass.ogg", "drums.ogg"]
    assert report["sync"]["ok"] and report["sync"]["of"] == "the files summed"
    assert set(report["sync"]["files"]) == {"guitar.ogg", "bass.ogg", "drums.ogg"}
    assert one.assembled.report["audio_files"] == ["song.ogg"] and one.assembled.report["sync"]["of"] == "song.ogg"
    pad = split.assembled.lead.pad_samples
    decoded = {f: A.decode(split.folder / f) for f in SPLIT}
    assert len({y.shape for y in decoded.values()}) == 1   # the same length and channels each
    for part in ("guitar", "bass", "drums"):   # each file holds its own stem, on the chart's timeline
        y, stem = decoded[f"{part}.ogg"][0, pad:], parts[part][0]
        assert np.corrcoef(y[:len(stem)], stem[:len(y)])[0, 1] > 0.95, part   # Vorbis: 0.987 on the clicks
    total = sum(decoded.values())
    single = A.decode(one.folder / "song.ogg")
    n = min(total.shape[1], single.shape[1])
    diff_db = 10 * np.log10(np.mean((total[:, :n] - single[:, :n]) ** 2) / np.mean(single[:, :n] ** 2))
    assert diff_db < -20, diff_db   # two lossy encodes apart: -27.5 dB on this song of clicks and noise
    rest = decoded["song.ogg"][0, pad:]   # the vocals and the rest, without the parts charted
    assert np.sqrt(np.mean(rest ** 2)) < 0.5 * np.sqrt(np.mean(single[0, pad:] ** 2))
    if find_scan_chart()[0] is not None:   # scan-chart reads the four as the song's audio
        scan = report["gate"]["scan_chart"]
        assert scan["ran"] and scan["playable"] and not {"invalidAudio", "multipleAudio", "noAudio"} & set(
            scan["folder_issues"]), scan


def test_no_stems_unless_asked_and_then_beside_the_song_folder(runs):
    """Off: no stems folder. On: "<song folder> (stems)" beside it, six 24-bit FLACs at 44.1 kHz of the input's length
    holding the separation's stems (break: written into the song folder, or a stem left out, or another rate)."""
    root, parts, out = runs
    split, stems = out["split"][0], out["stems"][0]
    assert split.stems is None and sorted(p.name for p in split.folder.parent.iterdir()) == ["Click Song"]
    assert "stems" not in json.loads((split.work / "pipeline.json").read_text(encoding="utf-8"))
    folder = stems.folder.with_name("Click Song (stems)")
    assert stems.stems == folder and sorted(p.name for p in stems.folder.parent.iterdir()) == [
        "Click Song", "Click Song (stems)"]
    assert files(folder, ".flac") == SIX and not list(stems.folder.glob("*.flac"))
    samples = parts["drums"].shape[1]
    for name in SIX:
        info = sf.info(str(folder / name))
        assert (info.samplerate, info.channels, info.subtype, info.format) == (SR, 2, "PCM_24", "FLAC"), name
        assert info.frames == samples == parts[name[:-5]].shape[1], name   # the input's length: no lead-in
        y, _ = sf.read(str(folder / name), dtype="float32", always_2d=True)
        assert np.abs(y.T - np.clip(parts[name[:-5]], -1, 1)).max() < 2 ** -22, name   # the stem itself, to 24 bits
    plan = next(e for e in out["stems"][1] if e["event"] == "plan")["stages"]
    assert plan[plan.index("assemble") + 1] == "stems"
    assert "stems" not in next(e for e in out["split"][1] if e["event"] == "plan")["stages"]


def test_a_rerun_with_the_stems_on_reuses_the_cached_separation(runs):
    """The second run (stems on, after one without) finds the separation in the cache and exports from it (break:
    the export separating again, or reading the stems after the cache's prune)."""
    root, parts, out = runs
    first = {s.name: s for s in out["split"][0].stages}
    again = {s.name: s for s in out["stems"][0].stages}
    assert not first["separate"].cached and again["separate"].cached
    key = standin_key(A.decode(root / "song.flac"))
    assert (out["stems"][0].work / "stems" / key / "piano.wav").is_file()   # the cache still holds what was read


def test_two_runs_give_byte_identical_audio_and_stems(runs, tmp_path, monkeypatch):
    """The same song in a cache of its own: every .ogg and .flac is byte-identical to the first run's (break: the
    Ogg stream's random serial, which differed run to run before M8-12)."""
    root, _, out = runs
    monkeypatch.setenv("SONGCHARTER_CACHE", str(tmp_path / "cache"))
    second = P.chart(root / "song.flac", tmp_path / "Click Song", P.Options(stems=True), engines=standins()(),
                     log=lambda line: None, sampler=None)
    first = out["stems"][0]
    for name in SPLIT:
        assert (second.folder / name).read_bytes() == (first.folder / name).read_bytes(), name
    for name in SIX:
        assert (second.stems / name).read_bytes() == (first.stems / name).read_bytes(), name
    assert (second.folder / "notes.chart").read_bytes() == (first.folder / "notes.chart").read_bytes()


@pytest.mark.parametrize("code, said", [(errno.ENOSPC, "the disk filled while the stems were written into "),
                                         (errno.EIO, "the stems could not be written into ")])
def test_a_full_disk_while_saving_the_stems(runs, tmp_path, monkeypatch, capsys, code, said):
    """The disk filling while they are written: a warning, the run ends as its gate says with no stems (the page says
    why in plain words), no stems folder or staging folder left, the chart in place (break: the staging folder kept;
    the error raised, which hid a good chart from the page: M8-12's review). Any other error writing them too: in
    WSL a full C:, where WSL's disk grows, is an I/O error, not ENOSPC (the v0.5.0 review's install-02; break: only
    ENOSPC caught, so the finished chart is reported as failed). Too little room at the export: NoRoom naming the
    folder and the space needed."""
    root, _, out = runs
    monkeypatch.setenv("SONGCHARTER_CACHE", str(root / "cache"))
    real = A.write_flac
    count = []

    def full(audio, path, rate=SR):
        count.append(path)
        if len(count) == 3:
            raise OSError(code, "No space left on device" if code == errno.ENOSPC else "Input/output error")
        return real(audio, path, rate)

    monkeypatch.setattr(A, "write_flac", full)
    target = tmp_path / "out" / "Click Song"
    events = []
    done = P.chart(root / "song.flac", target, P.Options(stems=True), engines=standins()(), log=lambda line: None,
                   sampler=None, events=events.append)
    assert done.ok and done.stems is None and (target / "notes.chart").is_file()
    assert sorted(p.name for p in target.parent.iterdir()) == ["Click Song"]
    assert [w for w in done.warnings if w.startswith(f"stems: not saved ({said}")]
    assert "they need about 51 MB" in done.warnings[-1]
    record = json.loads((done.work / "pipeline.json").read_text(encoding="utf-8"))["stems"]
    assert record["saved"] is False and record["why"] == P.STEMS_NO_ROOM.format(mb="51 MB")
    assert [e["stage"] for e in events if e["event"] == "stage_end"][-2:] == ["stems", "preview"]
    source = next((root / "cache" / "work").glob("song-*")) / "stems" / standin_key(A.decode(root / "song.flac"))
    with pytest.raises(InputError, match=r"no room for the stems in .*: they need about 51 MB, and 1 MB are free"):
        P.export_stems(source, tmp_path / "x (stems)", free=lambda p: 1)
    assert not (tmp_path / "x (stems)").exists() and not list(tmp_path.glob(".x (stems)*"))
    assert P.stems_bytes(240 * SR) == 190_512_000   # a 4-minute song: about 190 MB


def test_in_wsl_the_stems_room_is_measured_on_c_too(tmp_path, monkeypatch):
    """The v0.5.0 review's install-02: in WSL the library is on WSL's own disk, which reports its virtual disk's free
    space (here 950 GB) while that disk grows on C:, nearly full here; the stems' checks right after the decode and at
    the export measure C: as well, as doctor and the queue do, and say so (break: only the library's own disk
    measured: they pass, and 190 MB go onto a full C:). Outside WSL, C: is not asked about."""
    import shutil
    from types import SimpleNamespace
    from songcharter import wsl
    c = tmp_path / "c"
    c.mkdir()
    monkeypatch.setattr(wsl, "MNT_C", c)
    monkeypatch.setattr(wsl, "is_wsl", lambda: True)
    room = {"c": 120_000_000}
    monkeypatch.setattr(shutil, "disk_usage", lambda path: SimpleNamespace(
        free=room["c"] if Path(path) == c else 950 * 10 ** 9))
    folder = tmp_path / "library" / "0123456789abcdef" / "Made-Up Band - Song (stems)"
    with pytest.raises(InputError, match=r"^no room for the stems on C:, where WSL's disk grows: they need about 191 "
                                         r"MB, and 120 MB are free there\. Free some space, or chart again without"):
        P.stems_room(folder, 240 * SR)
    source = tmp_path / "sep"
    source.mkdir()
    for s in P.STEM_FILES:
        A.write_wav(np.zeros((2, SR), dtype=np.float32), source / f"{s}.wav")
    room["c"] = 100_000   # a second of six stems needs about 0.8 MB
    with pytest.raises(P.NoRoom, match=r"^no room for the stems on C:, where WSL's disk grows: they need about 1 MB"):
        P.export_stems(source, folder)
    assert not folder.exists() and not list(folder.parent.glob(".*partial"))
    room["c"] = 10 ** 9
    P.stems_room(folder, 240 * SR)   # room on both
    assert P.export_stems(source, folder)["files"] == [f"{s}.flac" for s in P.STEM_FILES]
    room["c"] = 1
    monkeypatch.setattr(wsl, "is_wsl", lambda: False)   # not WSL: C: is not WSL's disk
    P.stems_room(folder, 240 * SR)


def test_a_stems_folder_holding_other_files_is_refused_first(runs, tmp_path, monkeypatch):
    """A stems folder with a file songcharter did not write stops the chart before any audio work; one holding only
    an earlier export's stems is replaced (break: the check left out, so a person's files would be deleted)."""
    root, _, _ = runs
    monkeypatch.setenv("SONGCHARTER_CACHE", str(root / "cache"))
    target = tmp_path / "Click Song"
    (tmp_path / "Click Song (stems)").mkdir()
    (tmp_path / "Click Song (stems)" / "my mix.wav").write_bytes(b"RIFF")
    engines = standins()()
    with pytest.raises(InputError, match=r"the stems folder .*Click Song \(stems\) holds my mix.wav"):
        P.chart(root / "song.flac", target, P.Options(stems=True), engines=engines, log=lambda line: None,
                sampler=None)
    assert engines.calls == [] and not target.exists()
    (tmp_path / "Click Song (stems)" / "my mix.wav").unlink()
    (tmp_path / "Click Song (stems)" / "drums.flac").write_bytes(b"old")
    done = P.chart(root / "song.flac", target, P.Options(stems=True), engines=standins()(), log=lambda line: None,
                   sampler=None)
    assert files(done.stems, ".flac") == SIX and (done.stems / "drums.flac").read_bytes()[:4] == b"fLaC"


def test_the_cli_flags(runs, tmp_path, monkeypatch, capsys):
    """--stems and --one-audio reach the run, and the result event names the stems folder (break: a flag not passed
    to the options)."""
    root, _, _ = runs
    monkeypatch.setenv("SONGCHARTER_CACHE", str(root / "cache"))
    monkeypatch.setattr(P, "Engines", standins())
    out = tmp_path / "Click Song"
    code = main(["chart", str(root / "song.flac"), "--out", str(out), "--stems", "--one-audio", "--events"])
    stdout, err = capsys.readouterr()
    assert code == 0, err
    assert files(out, ".ogg") == ["song.ogg"] and files(tmp_path / "Click Song (stems)", ".flac") == SIX
    assert f"stems: {tmp_path / 'Click Song (stems)'}" in stdout.splitlines()
    record = json.loads((P.cache.work_folder(P.cache.cache_root(), "song", P.cache.file_key(root / "song.flac"))
                         / "pipeline.json").read_text(encoding="utf-8"))["stems"]
    folder = tmp_path / "Click Song (stems)"
    assert record["folder"] == str(folder) and record["files"] == [f"{s}.flac" for s in P.STEM_FILES]
    assert record["bytes"] == sum((folder / f).stat().st_size for f in SIX)
    result = [json.loads(line[len("@@songcharter "):]) for line in err.splitlines()
              if line.startswith("@@songcharter ") and '"result"' in line][-1]
    assert result["stems"] == str(tmp_path / "Click Song (stems)")
    code = main(["chart", str(root / "song.flac"), "--out", str(out), "--events"])   # the defaults again
    stdout, err = capsys.readouterr()
    assert code == 0, err
    assert files(out, ".ogg") == SPLIT   # split again: the one-file build's song.ogg replaced, nothing foreign
    result = [json.loads(line[len("@@songcharter "):]) for line in err.splitlines()
              if line.startswith("@@songcharter ") and '"result"' in line][-1]
    assert result["stems"] is None
    code = main(["chart", str(root / "song.flac"), "--out", str(out), "--one-audio"])   # and back to one file
    assert code == 0 and files(out, ".ogg") == ["song.ogg"]


def test_the_gates_audio_rule_is_scan_charts():
    """One song.ogg or the four split files pass; a name Clone Hero does not read, a name twice or no song audio do
    not (break: the old rule, one audio file only, which fails the split folder)."""
    assert audio_file_issues(["notes.chart", "song.ogg"]) == []
    assert audio_file_issues(sorted(SPLIT + ["notes.chart", "song.ini", "album.jpg"])) == []
    kinds = lambda names: sorted(i.kind for i in audio_file_issues(names))  # noqa: E731
    assert kinds(["song.ogg", "song.mp3"]) == ["multipleAudio"]
    assert kinds(["track.ogg"]) == ["invalidAudio", "noAudio"]
    assert kinds(["preview.ogg", "guitar.flac"]) == ["noAudio"]   # FLAC is no audio Clone Hero reads in a song folder
    assert kinds([]) == ["noAudio"]


def test_listen_and_the_folders_audio_read_the_files_summed(runs, tmp_path):
    """Listen renders over the four files summed, as over the one file (break: song.ogg alone, without the parts),
    and its cache key follows every audio file."""
    _, _, out = runs
    split, one = out["split"][0].folder, out["one"][0].folder
    assert [p.name for p in A.song_audio_files(split)] == SPLIT
    a, b = LI.render(split, "guitar"), LI.render(one, "guitar")
    n = min(a.audio.shape[1], b.audio.shape[1])
    assert np.sqrt(np.mean((a.audio[:, :n] - b.audio[:, :n]) ** 2)) < 0.1 * np.sqrt(np.mean(b.audio[:, :n] ** 2))
    copy = tmp_path / "copy"
    copy.mkdir()
    for f in split.iterdir():
        (copy / f.name).write_bytes(f.read_bytes())
    key = LI.cache_key(copy, "guitar", "expert")
    (copy / "drums.ogg").write_bytes((one / "song.ogg").read_bytes())
    assert LI.cache_key(copy, "guitar", "expert") != key


def test_package_refuses_a_split_file_out_of_sync(tmp_path, monkeypatch):
    """A split file whose decode lags its own samples fails the build, and a steady tone, which correlates as well a
    period away, does not (break: only the sum checked, which a quiet stem's lag barely moves; or any confident lag
    taken for a shift, which failed a stand-in's sine as "4410 samples off")."""
    from songcharter.chart import Chart, SongInfo
    from songcharter.tempo import Tempo, TempoMap
    from songcharter.errors import ToolError
    rng = np.random.default_rng(3)
    mix = (0.2 * rng.standard_normal((2, 12 * SR))).astype(np.float32)
    guitar = (0.05 * rng.standard_normal((2, 12 * SR))).astype(np.float32)
    chart = Chart(SongInfo("x", "songcharter"), TempoMap(480, [Tempo(0, 120000)]), [], [])
    done = PK.build_song_folder(tmp_path / "ok", chart, mix, 100, split={"guitar": guitar})
    assert done.files == ("song.ogg", "guitar.ogg") and done.sync.ok
    assert done.tracks["guitar.ogg"] == {"windows": 9, "shifted": 0, "length_difference": 0}
    t = np.arange(12 * SR) / SR   # a steady tone: a period away correlates as well as no lag, which is no shift
    tone = np.stack([0.1 * np.sin(2 * np.pi * 330 * t)] * 2).astype(np.float32)
    assert PK.build_song_folder(tmp_path / "tone", chart, mix + tone, 100, split={"guitar": tone}).sync.ok
    real = A.decode

    def late(path, *args, **kwargs):
        y = real(path, *args, **kwargs)
        return np.pad(y, ((0, 0), (5, 0)))[:, :y.shape[1]] if Path(path).name == "guitar.ogg" else y

    monkeypatch.setattr(A, "decode", late)
    with pytest.raises(ToolError, match="guitar.ogg is out of sync with the chart: 5.00 samples off"):
        PK.build_song_folder(tmp_path / "late", chart, mix, 100, split={"guitar": guitar})


def test_no_room_for_the_stems_stops_right_after_the_decode(runs, tmp_path, monkeypatch):
    """The stems' room is checked once the decode gives their size, before the separation and the engines (break:
    the check only at the export, after the whole chart: M8-12's review)."""
    root, _, _ = runs
    monkeypatch.setenv("SONGCHARTER_CACHE", str(root / "cache"))
    monkeypatch.setattr(P, "disk_free", lambda path: 10_000_000)
    engines = standins()()
    with pytest.raises(InputError, match=r"no room for the stems in .*: they need about 51 MB, and 10 MB are free"):
        P.chart(root / "song.flac", tmp_path / "Click Song", P.Options(stems=True), engines=engines,
                log=lambda line: None, sampler=None)
    assert [c[0] for c in engines.calls] == ["threads"] or not any(c[0] == "separate" for c in engines.calls)
    assert not (tmp_path / "Click Song").exists()
    P.chart(root / "song.flac", tmp_path / "Without", P.Options(), engines=standins()(), log=lambda line: None,
            sampler=None)   # without the stems the room is not asked about


def test_a_foreign_flac_or_folder_in_the_stems_folder_is_refused(runs, tmp_path, monkeypatch):
    """A person's own .flac, or a folder, in "<song> (stems)" is not one of ours (break: any .flac counted as ours,
    which the export's replace would delete: M8-12's review)."""
    root, _, _ = runs
    monkeypatch.setenv("SONGCHARTER_CACHE", str(root / "cache"))
    folder = tmp_path / "Click Song (stems)"
    for name, make in (("my mix.flac", lambda f: f.write_bytes(b"fLaC")), ("takes", lambda f: f.mkdir())):
        folder.mkdir(exist_ok=True)
        make(folder / name)
        with pytest.raises(InputError, match=f"holds {name}, which songcharter did not write"):
            P.check_stems_folder(folder)
        (folder / name).unlink() if (folder / name).is_file() else (folder / name).rmdir()
    (folder / "drums.flac").write_bytes(b"old")
    P.check_stems_folder(folder)   # an earlier export's own


def _late(monkeypatch, name: str, samples: int = 0, cut: int = 0):
    real = A.decode

    def decode(path, *args, **kwargs):
        y = real(path, *args, **kwargs)
        if Path(path).name == name:
            y = np.pad(y, ((0, 0), (samples, 0)))[:, :y.shape[1] - cut]
        return y
    monkeypatch.setattr(A, "decode", decode)


@pytest.mark.parametrize("name, samples, cut, why", [
    ("song.ogg", 2205, 0, "the song's audio files together are out of sync with the chart"),   # 50 ms
    ("guitar.ogg", 0, 100, "guitar.ogg is out of sync with the chart: -100 samples long"),
    ("guitar.ogg", 8820, 0, r"guitar.ogg is out of sync with the chart: more than 100 ms off \(correlation"),
])
def test_package_refuses_song_ogg_late_a_short_file_and_a_shift_past_the_search(tmp_path, monkeypatch, name, samples,
                                                                              cut, why):
    """song.ogg late (only the sum checks it), a split file short (only the length checks it), and a split file
    200 ms late, past measure_offset's 100 ms search (a loud window that does not line up at no lag), each fail the
    build (breaks: the sum compared with itself, the length test dropped, a window under CONFIDENT skipped; M8-12's
    review: each left these tests green)."""
    from songcharter.chart import Chart, SongInfo
    from songcharter.errors import ToolError
    from songcharter.tempo import Tempo, TempoMap
    rng = np.random.default_rng(3)
    mix = (0.2 * rng.standard_normal((2, 12 * SR))).astype(np.float32)
    guitar = (0.05 * rng.standard_normal((2, 12 * SR))).astype(np.float32)
    chart = Chart(SongInfo("x", "songcharter"), TempoMap(480, [Tempo(0, 120000)]), [], [])
    _late(monkeypatch, name, samples, cut)
    with pytest.raises(ToolError, match=why):
        PK.build_song_folder(tmp_path / "x", chart, mix, 100, split={"guitar": guitar})


def test_a_strangers_multitrack_folder_is_not_ours(tmp_path):
    """guitar.ogg, bass.ogg and drums.ogg are ours only where our report.json lists them: someone else's multitrack
    folder given as the output is refused, not overwritten (break: the three counted as ours always: M8-12's
    review); an earlier split build of ours is replaced."""
    from songcharter.assemble import check_output
    folder = tmp_path / "Theirs"
    folder.mkdir()
    for name in ("notes.chart", "song.ini", "song.ogg", "guitar.ogg", "bass.ogg", "drums.ogg"):
        (folder / name).write_bytes(b"x")
    with pytest.raises(InputError, match=r"bass.ogg, drums.ogg, guitar.ogg"):
        check_output(folder)
    (folder / "report.json").write_text(json.dumps({"gate": {"ok": True}}), encoding="utf-8")   # no audio_files
    with pytest.raises(InputError, match=r"bass.ogg, drums.ogg, guitar.ogg"):
        check_output(folder)
    (folder / "report.json").write_text(json.dumps({"audio_files": ["song.ogg", "guitar.ogg", "bass.ogg",
                                                                    "drums.ogg"]}), encoding="utf-8")
    check_output(folder)


def test_preview_and_crowd_are_not_the_songs_music(tmp_path):
    """A folder's preview.ogg and crowd.ogg are left out of the song's audio, which Listen and the preview read (break:
    every audio name taken as music)."""
    t = np.arange(SR) / SR
    for name, gain in (("song.ogg", 0.1), ("guitar.ogg", 0.1), ("preview.ogg", 0.4), ("crowd.ogg", 0.4)):
        A.encode_ogg(np.stack([gain * np.sin(2 * np.pi * 220 * t)] * 2).astype(np.float32), tmp_path / name)
    (tmp_path / "notes.chart").write_text("x", encoding="utf-8")
    assert [p.name for p in A.song_audio_files(tmp_path)] == ["guitar.ogg", "song.ogg"]
    peak = float(np.abs(A.decode_song_audio(tmp_path)).max())
    assert 0.18 < peak < 0.22, peak   # the two at 0.1: not the 0.4s
