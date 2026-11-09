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


def test_a_full_disk_while_saving_the_stems(runs, tmp_path, monkeypatch, capsys):
    """Too little free space, or the disk filling while they are written: an InputError naming the folder and the
    space needed, no stems folder or staging folder left, and the chart in place (break: the staging folder kept)."""
    root, _, out = runs
    monkeypatch.setenv("SONGCHARTER_CACHE", str(root / "cache"))
    real = A.write_flac
    count = []

    def full(audio, path, rate=SR):
        count.append(path)
        if len(count) == 3:
            raise OSError(errno.ENOSPC, "No space left on device")
        return real(audio, path, rate)

    monkeypatch.setattr(A, "write_flac", full)
    target = tmp_path / "out" / "Click Song"
    with pytest.raises(InputError, match=r"the disk filled while the stems were written into .*Click Song \(stems\): "
                                         r"they need about \d+ MB"):
        P.chart(root / "song.flac", target, P.Options(stems=True), engines=standins()(), log=lambda line: None,
                sampler=None)
    assert sorted(p.name for p in target.parent.iterdir()) == ["Click Song"] and (target / "notes.chart").is_file()
    source = next((root / "cache" / "work").glob("song-*")) / "stems" / standin_key(A.decode(root / "song.flac"))
    with pytest.raises(InputError, match=r"no room for the stems in .*: they need about 51 MB, and 1 MB are free"):
        P.export_stems(source, tmp_path / "x (stems)", free=lambda p: 1)
    assert not (tmp_path / "x (stems)").exists() and not list(tmp_path.glob(".x (stems)*"))
    assert P.stems_bytes(240 * SR) == 190_512_000   # a 4-minute song: about 190 MB


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
