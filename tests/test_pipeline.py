"""The pipeline (songcharter.pipeline) and `songcharter chart`, with stand-ins for the heavy stages: a synthetic
song (click drums, a bass line, a guitar line, a sung part) in a tagged FLAC, a separation that returns the stems it
was mixed from, and engines that write what each engine writes (a chart on a constant 120 BPM map, a song.ini for
drums, segments.json) at the song's own note times. The decode, the tags, the work folder, the assemble config,
assemble and the gate run for real. No model runs here, and none is downloaded."""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

import songcharter.assemble as assemble_module
from songcharter import audio as A
from songcharter import pipeline as P
from songcharter.assemble import find_scan_chart
from songcharter.chart import Chart, DrumHit, FretNote, SongInfo, Track, write_chart
from songcharter.cli import main
from songcharter.engines.autochart import DEFAULT_SEED
from songcharter.importers import read_song
from songcharter.pipeline import Engines, Options, Run, chart, parse_ffmetadata, read_tags, song_metadata
from songcharter.tempo import Tempo, TempoMap

SR = A.SAMPLE_RATE
FIRST, PERIOD, DURATION = 0.5, 0.5, 64.0     # 120 BPM from 0.5 s: 2-s measures
BEATS = int((DURATION - 1.0 - FIRST) / PERIOD)
TAGS = {"title": "Click Song", "artist": "The Testers", "album": "Synthetic", "date": "2026-05-01", "track": "3/9"}
SEGMENTS = [[0.0, 0.5, "start"], [0.5, 16.5, "intro"], [16.5, 32.5, "verse"], [32.5, 48.5, "chorus"],
            [48.5, 62.5, "verse"], [62.5, DURATION, "end"]]


def beat(k: float) -> float:
    return FIRST + k * PERIOD


# ------------------------------------------------------------------------------------------------ the song

def drum_times():
    """(time, pad, cymbal): a hi-hat on every 8th, a kick on beat 1 and a snare on beat 3 of each bar."""
    out = []
    for k in range(BEATS):
        out += [(beat(k), 2, True), (beat(k + 0.5), 2, True)]
        if k % 4 in (0, 2):
            out.append((beat(k), 0 if k % 4 == 0 else 1, False))
    return out


def bass_times():
    return [(beat(k), (0, 2, 3, 1)[k % 4]) for k in range(8, BEATS - 4)]


def guitar_times():
    return [(beat(k / 2), (0, 1, 2, 1, 0, 1, 2, 3)[k % 8]) for k in range(16, 2 * BEATS - 8)]


def stems(n: int) -> dict[str, np.ndarray]:
    rng = np.random.default_rng(0)
    t = np.arange(int(0.25 * SR)) / SR
    hit = {0: np.sin(2 * np.pi * 55 * t) * np.exp(-t / 0.08),
           1: (0.5 * np.sin(2 * np.pi * 190 * t) + 0.6 * rng.standard_normal(len(t))) * np.exp(-t / 0.06),
           2: np.diff(rng.standard_normal(len(t) + 1)) * np.exp(-t / 0.015) * 0.15}
    out = {name: np.zeros(n) for name in ("drums", "bass", "guitar", "other", "vocals", "piano")}

    def add(name, at, y, gain):
        i = int(round(at * SR))
        y = y[:max(0, n - i)]
        out[name][i:i + len(y)] += gain * y

    for at, pad, _ in drum_times():
        add("drums", at, hit[pad], 0.4)
    for at, lane in bass_times():
        add("bass", at, np.sin(2 * np.pi * (41.2, 49.0, 55.0, 61.7)[lane] * t * 2) * np.exp(-t / 0.2), 0.3)
    for at, lane in guitar_times():
        add("guitar", at, np.sin(2 * np.pi * (330, 370, 415, 440, 494)[lane] * t[:6000]) * np.exp(-t[:6000] / 0.05),
            0.08)
    for a, b in ((16.5, 32.5), (48.5, 62.0)):
        i, j = int(a * SR), int(b * SR)
        out["vocals"][i:j] = 0.05 * np.sin(2 * np.pi * 220 * np.arange(j - i) / SR)
    out["other"] += 1e-3 * rng.standard_normal(n)
    return {k: np.stack([v, v]).astype(np.float32) for k, v in out.items()}


def write_song(path: Path, tags=TAGS) -> dict[str, np.ndarray]:
    """The song as a tagged FLAC (lossless, so the decode is the mix to 24 bits), and its stems."""
    n = int(DURATION * SR)
    parts = stems(n)
    mix = np.sum(list(parts.values()), axis=0)
    wav = path.with_suffix(".src.wav")
    A.write_wav(mix, wav)
    meta = [x for k, v in tags.items() for x in ("-metadata", f"{k}={v}")]
    subprocess.run([A.ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-y", "-i", str(wav), *meta,
                    "-c:a", "flac", "-sample_fmt", "s32", str(path)], check=True)
    wav.unlink()
    return parts


# ------------------------------------------------------------------------------------------------ stand-ins

def _write(path: Path, track: Track) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    chart = Chart(SongInfo("stand-in", "songcharter"), TempoMap(480, [Tempo(0, 120000)]), [], [track])
    path.write_text(write_chart(chart), encoding="utf-8", newline="")


def tick(t: float) -> int:
    return int(round(t * 960))   # the engines' constant map: 120 BPM at resolution 480


def standins(empty: tuple[str, ...] = (), bug: str | None = None):
    """Engines that write what the real ones write, and record each call in `calls`. `empty`: engines that find
    no notes; `bug`: a stage that raises KeyError (a bug)."""

    class StandIns(Engines):
        calls: list[tuple] = []

        def missing(self, options):
            return []

        def device(self, asked):
            return "cpu" if asked == "auto" else asked

        def threads(self, n):
            self.calls.append(("threads", n))

        def _bug(self, stage):
            if bug == stage:
                raise KeyError(f"a bug in {stage}")

        def separate(self, mix, cache_dir, device):
            self._bug("separate")
            folder = cache_dir / "standin"
            cached = (folder / "info.json").is_file()
            if cached:
                out = {s: A.read_wav(folder / f"{s}.wav")[0] for s in json.loads((folder / "info.json").read_text())}
            else:
                out = stems(mix.shape[1])
                folder.mkdir(parents=True)
                for s, y in out.items():
                    A.write_wav(y, folder / f"{s}.wav")
                (folder / "info.json").write_text(json.dumps(list(out)))
            self.calls.append(("separate", mix.shape, cache_dir, device))
            return out, folder, {"device": device, "cached": cached, "key": "standin", "fallback": None}

        def drums(self, mix, drums, out, device):
            self._bug("drums")
            self.calls.append(("drums", mix.shape, float(np.abs(drums).max()), out, device))
            cached = (out / "notes.chart").is_file()
            if not cached:
                hits = [] if "drums" in empty else [DrumHit(tick(t), p, c) for t, p, c in drum_times()]
                _write(out / "notes.chart", Track("Expert", "Drums", hits))
                (out / "song.ini").write_text("[song]\r\nname = ADTOF drums\r\npro_drums = True\r\n")
            return Run(out / "notes.chart", cached, {"notes": len(drum_times())})

        def bass(self, mix, bass, out):
            self._bug("bass")
            self.calls.append(("bass", mix.shape, float(np.abs(bass).max()), out))
            cached = (out / "notes.chart").is_file()
            if not cached:
                notes = [] if "bass" in empty else [FretNote(tick(t), (lane,)) for t, lane in bass_times()]
                _write(out / "notes.chart", Track("Expert", "DoubleBass", notes))
            return Run(out / "notes.chart", cached, {})

        def sections(self, mix, stems, out, device, threads):
            self._bug("sections")
            self.calls.append(("sections", sorted(stems), out, device, threads))
            cached = (out / "segments.json").is_file()
            if not cached:
                out.mkdir(parents=True)
                (out / "segments.json").write_text(json.dumps({"segments": SEGMENTS}))
            return Run(out / "segments.json", cached, {"backend": "librosa", "why": "no allin1 Python (stand-in)",
                                                       "segments": len(SEGMENTS)})

        def guitar(self, audio, out, seeds, device, title, artist):
            self._bug("guitar")
            self.calls.append(("guitar", audio, out, tuple(seeds), device, title, artist))
            runs = []
            for k, seed in enumerate(seeds):
                path = out / f"seed_{seed}" / "notes.chart"
                cached = path.is_file()
                if not cached:  # each take after the first misses one note, in a section of its own
                    notes = [FretNote(tick(t), (lane,)) for j, (t, lane) in enumerate(guitar_times())
                             if not (k and j == 40 * k) and "guitar" not in empty]
                    _write(path, Track("Expert", "Single", notes))
                runs.append(Run(path, cached, {"devices": {"transcriber": device}}))
            return runs

    StandIns.calls = []
    return StandIns


@pytest.fixture(scope="module")
def charted(tmp_path_factory):
    root = tmp_path_factory.mktemp("pipeline")
    write_song(root / "song.flac")
    engines = standins()()
    lines = []
    result = chart(root / "song.flac", root / "out" / "Click Song", Options(takes=3, threads=2,
                                                                          metadata={"genre": "Test"}),
                   engines=engines, log=lines.append)
    return root, result, engines, lines


# ------------------------------------------------------------------------------------------------ end to end

def test_the_song_folder_passes_the_gate(charted):
    root, result, _, _ = charted
    assert result.ok, [i for i in result.assembled.issues if i.error]
    assert result.folder == root / "out" / "Click Song"
    assert sorted(p.name for p in result.folder.iterdir()) == ["notes.chart", "report.json", "song.ini", "song.ogg"]
    assert sorted(p.name for p in (root / "out").iterdir()) == ["Click Song", "Click Song.work"]
    report = result.assembled.report
    assert report["gate"]["ok"] and report["sync"]["ok"] and abs(report["grid"]["bpm_median"] - 120) < 0.05
    if find_scan_chart()[0] is not None:
        scan = report["gate"]["scan_chart"]
        assert scan["ran"] and scan["playable"] and scan["chart_issues"] == 0 and scan["metadata_issues"] == []
    song = read_song(result.folder)
    assert {i for i, _ in song.parts} == {"guitar", "bass", "drums"}
    assert report["sections"]["count"] >= 4 and report["parts"]["guitar"]["takes"]


def test_metadata_comes_from_the_tags_and_the_caller(charted):
    _, result, _, _ = charted
    ini = (result.folder / "song.ini").read_text(encoding="utf-8")
    for line in ("name = Click Song", "artist = The Testers", "album = Synthetic", "year = 2026", "genre = Test",
                 "charter = songcharter", "album_track = 3"):
        assert line in ini.splitlines(), line
    report = json.loads((result.work / "pipeline.json").read_text(encoding="utf-8"))
    assert report["metadata_from"] == {"name": "tag title", "artist": "tag artist", "album": "tag album",
                                       "genre": "given", "year": "tag date", "album_track": "tag track",
                                       "charter": "default"}


def test_the_work_folder_and_the_assemble_config(charted):
    root, result, _, _ = charted
    work = root / "out" / "Click Song.work"
    assert result.work == work and result.config == work / "assemble.json"
    cfg = json.loads(result.config.read_text(encoding="utf-8"))
    assert cfg["audio"] == str(work / "decode.wav") and cfg["output"] == str(result.folder)
    assert cfg["stems"] == {s: str(work / "stems" / "standin" / f"{s}.wav")
                            for s in ("drums", "bass", "guitar", "other", "vocals")}
    assert cfg["sections"] == str(work / "sections" / "segments.json") and cfg["solos"] == "stems"
    assert [p["instrument"] for p in cfg["parts"]] == ["guitar", "bass", "drums"]
    guitar, bass, drums = cfg["parts"]
    assert guitar["source"] == str(work / "guitar" / f"seed_{DEFAULT_SEED}" / "notes.chart")
    assert guitar["takes"] == [str(work / "guitar" / f"seed_{s}" / "notes.chart") for s in (101, 202)]
    assert bass == {"instrument": "bass", "source": str(work / "bass" / "notes.chart"), "hopo": "forced"}
    assert drums == {"instrument": "drums", "source": str(work / "drums" / "notes.chart")}
    # the decode is the FLAC's samples, written once as float32
    mix, sr = A.read_wav(work / "decode.wav")
    assert sr == SR and mix.shape == (2, int(DURATION * SR)) and mix.dtype == np.float32
    assert np.array_equal(mix, A.decode(root / "song.flac"))
    report = json.loads((work / "pipeline.json").read_text(encoding="utf-8"))
    assert [s["stage"] for s in report["stages"]] == ["decode", "separate", "drums", "bass", "sections", "guitar",
                                                      "assemble"]
    assert all(s["seconds"] >= 0 and not s["cached"] for s in report["stages"])
    assert report["assemble"]["ok"] and report["options"]["takes"] == 3 and "error" not in report
    if sys.platform != "win32":
        assert report["peak_rss_mb"]["self"] > 0


def test_the_engines_get_the_decode_its_stems_and_the_options(charted):
    root, result, engines, lines = charted
    work = result.work
    calls = {c[0]: c[1:] for c in engines.calls}
    shape = (2, int(DURATION * SR))
    assert calls["threads"] == (2,)
    assert calls["separate"] == (shape, work / "stems", "cpu")
    assert calls["drums"][0] == shape and calls["drums"][2:] == (work / "drums", "cpu") and calls["drums"][1] > 0.1
    assert calls["bass"][0] == shape and calls["bass"][2] == work / "bass"
    assert calls["sections"] == (["bass", "drums", "guitar", "other", "piano", "vocals"], work / "sections", "auto", 2)
    assert calls["guitar"] == (work / "decode.wav", work / "guitar", (DEFAULT_SEED, 101, 202), "cpu", "Click Song",
                               "The Testers")
    assert lines[0] == "[1/7] decode: song.flac" and lines[-1].startswith("[7/7] assemble: gate OK")
    assert any(line.startswith("[6/7] guitar: autochart, 3 takes (seeds 20260609, 101, 202) on cpu") for line in lines)
    assert any("sections: the librosa fallback (no allin1 Python (stand-in))" in line for line in lines)


def test_a_rerun_reuses_every_stage(charted, monkeypatch, capsys):
    """The command line on the same song and output: every stage before assemble answers from its cache, the
    decode is not rewritten, and the chart is byte-identical."""
    root, result, _, _ = charted
    monkeypatch.setattr(P, "Engines", standins())
    wav = result.work / "decode.wav"
    before = (wav.stat().st_mtime_ns, (result.folder / "notes.chart").read_bytes())
    code = main(["chart", str(root / "song.flac"), "--out", str(result.folder), "--takes", "3", "--genre", "Test"])
    out, err = capsys.readouterr()
    assert code == 0, err
    for stage in ("decode", "separate", "drums", "bass", "sections", "guitar"):
        assert any(f"] {stage}: " in line and "(cached)" in line for line in err.splitlines()), stage
    assert "gate: OK" in out and out.splitlines()[-1].startswith("stages: decode ")
    assert (wav.stat().st_mtime_ns, (result.folder / "notes.chart").read_bytes()) == before


def test_an_engine_without_notes_leaves_its_part_out(tmp_path, monkeypatch, capsys):
    write_song(tmp_path / "song.flac", tags={})
    monkeypatch.setattr(P, "Engines", standins(empty=("bass",)))
    code = main(["chart", str(tmp_path / "song.flac"), "--out", str(tmp_path / "Song"), "--instruments",
                 "drums,bass", "--album", "A", "--year", "2001", "--artist", "  "])
    out, err = capsys.readouterr()
    assert code == 0, err
    assert "bass: the engine found no notes" in err and "[6/6] assemble" in err and "] guitar:" not in err
    cfg = json.loads((tmp_path / "Song.work" / "assemble.json").read_text(encoding="utf-8"))
    assert [p["instrument"] for p in cfg["parts"]] == ["drums"] and cfg["solos"] == "off"
    ini = (tmp_path / "Song" / "song.ini").read_text(encoding="utf-8").splitlines()
    assert any(line.startswith("diff_drums = ") for line in ini)
    assert not any(line.startswith("diff_bass") for line in ini)
    # no tags: the file's name, and placeholders scan-chart does not take for missing values
    assert {"name = song", "artist = Unknown", "album = A", "year = 2001", "genre = Unknown"} <= set(ini)
    # every engine empty: nothing to chart, before assemble
    monkeypatch.setattr(P, "Engines", standins(empty=("bass", "drums")))
    assert main(["chart", str(tmp_path / "song.flac"), "--out", str(tmp_path / "Other"), "--instruments",
                 "drums,bass"]) == 2
    assert "nothing to chart" in capsys.readouterr().err and not (tmp_path / "Other").exists()


def test_cli_exit_codes(charted, tmp_path, monkeypatch, capsys):
    """1 for a failed gate (the build in <out>.failed), 2 for a bad input or option, found before any audio work,
    3 with the traceback for a bug, 130 for Ctrl+C."""
    root, result, _, _ = charted
    song = str(root / "song.flac")
    monkeypatch.setattr(P, "Engines", standins())
    real = assemble_module.verify_folder
    monkeypatch.setattr(assemble_module, "verify_folder", lambda *a, **k: real(*a, **k) + [
        assemble_module.GateIssue(None, None, "fake", "a gate error")])
    out = tmp_path / "Gate"
    work = ["--work", str(result.work)]  # the first build's caches
    assert main(["chart", song, "--out", str(out), *work, "--takes", "3", "--genre", "Test"]) == 1
    printed = capsys.readouterr().out
    assert "gate: FAILED" in printed and (tmp_path / "Gate.failed" / "notes.chart").is_file() and not out.exists()
    monkeypatch.setattr(assemble_module, "verify_folder", real)

    (tmp_path / "Busy").mkdir()
    (tmp_path / "Busy" / "keep.txt").write_text("mine")
    (tmp_path / "not audio.mp3").write_text("hello")
    for args, message in (([str(tmp_path / "missing.mp3")], "does not exist"),
                          ([song, "--takes", "2"], "takes is 1, or 3 or more"),
                          ([song, "--instruments", "guitar,piano"], "instruments are guitar, bass, drums"),
                          ([song, "--instruments", ""], "no instruments"),
                          ([song, "--instruments", "bass", "--takes", "3"], "takes are guitar takes"),
                          ([song, "--threads", "0"], "threads must be"),
                          ([song, "--out", str(tmp_path / "Busy")], "holds what a build does not write"),
                          ([song, "--work", str(tmp_path / "X" / "w")], "must be apart"),
                          ([str(tmp_path / "not audio.mp3")], "ffmpeg could not read")):
        argv = ["chart", *args] + ([] if "--out" in args else ["--out", str(tmp_path / "X")])
        assert main(argv) == 2, args
        assert message in capsys.readouterr().err, args
    assert (tmp_path / "Busy" / "keep.txt").read_text() == "mine" and not (tmp_path / "X").exists()
    assert not (tmp_path / "Busy.work").exists()  # refused before any audio work, not by assemble at the end

    class Missing(standins()):
        def missing(self, options):
            return ["the guitar needs autochart (set SONGCHARTER_AUTOCHART)"]

    monkeypatch.setattr(P, "Engines", Missing)
    assert main(["chart", song, "--out", str(tmp_path / "Y")]) == 2
    assert "cannot chart: the guitar needs autochart (set SONGCHARTER_AUTOCHART)" in capsys.readouterr().err
    assert not (tmp_path / "Y.work").exists()

    monkeypatch.setattr(P, "Engines", standins(bug="drums"))
    assert main(["chart", song, "--out", str(tmp_path / "Z"), *work]) == 3
    err = capsys.readouterr().err
    assert "Traceback" in err and "KeyError: 'a bug in drums'" in err and "internal error" in err
    report = json.loads((result.work / "pipeline.json").read_text(encoding="utf-8"))
    assert report["error"] == "KeyError: 'a bug in drums'" and [s["stage"] for s in report["stages"]] == [
        "decode", "separate"]

    def interrupted(*a, **k):
        raise KeyboardInterrupt

    monkeypatch.setattr(P, "chart", interrupted)
    assert main(["chart", song, "--out", str(tmp_path / "Z")]) == 130
    assert "interrupted" in capsys.readouterr().err


# ------------------------------------------------------------------------------------------------ the parts

def test_ffmetadata_is_parsed_with_its_escapes():
    text = (";FFMETADATA1\ntitle=Ogg Title \\= x\\; y\nARTIST=A\\\\B\ncomment=one\\\ntwo\n#note\n\nalbum=First\n"
            "album=Second\nempty=\n[CHAPTER]\ntitle=a chapter\n")
    assert parse_ffmetadata(text) == {"title": "Ogg Title = x; y", "artist": "A\\B", "comment": "one\ntwo",
                                      "album": "First", "empty": ""}


def test_tags_are_read_from_the_container_and_the_stream(tmp_path):
    """FLAC and MP3 tags are the container's; Ogg keeps its comments on the audio stream."""
    y = (0.1 * np.sin(2 * np.pi * 440 * np.arange(SR) / SR)).astype(np.float32)
    A.write_wav(np.stack([y, y]), tmp_path / "a.wav")
    for ext, codec in (("flac", "flac"), ("ogg", "libvorbis")):
        path = tmp_path / f"a.{ext}"
        subprocess.run([A.ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-y", "-i", str(tmp_path / "a.wav"),
                        "-metadata", "title=Song = One", "-metadata", "artist=Band", "-metadata", "date=1999-03",
                        "-metadata", "track=7/12", "-c:a", codec, str(path)], check=True)
        tags = read_tags(path)
        assert {k: tags.get(k) for k in ("title", "artist", "date", "track")} == {
            "title": "Song = One", "artist": "Band", "date": "1999-03", "track": "7/12"}, ext
    assert read_tags(tmp_path / "nothing.ogg") == {}


def test_metadata_rules():
    meta, origin = song_metadata(Path("x/My Song.mp3"), {"title": " Real  Title ", "album_artist": "Group",
                                                         "date": "Released 1987", "track": "B2"},
                                 {"name": None, "year": "  ", "genre": "Rock"})
    assert meta == {"name": "Real Title", "artist": "Group", "album": "Unknown", "genre": "Rock", "year": "1987",
                    "charter": "songcharter"}
    assert origin["artist"] == "tag album_artist" and origin["year"] == "tag date" and origin["album"] == "default"
    meta, origin = song_metadata(Path("x/My Song.mp3"), {}, {})
    assert meta["name"] == "My Song" and origin["name"] == "file name"
    # scan-chart counts its own defaults as missing (missingValue): ours differ from every one of them
    scan_defaults = {"name": "Unknown Name", "artist": "Unknown Artist", "album": "Unknown Album",
                     "genre": "Unknown Genre", "year": "Unknown Year", "charter": "Unknown Charter"}
    assert all(meta[k] != v and meta[k] for k, v in scan_defaults.items())


def test_options_and_seeds():
    Options().check()
    Options(instruments=("drums",), takes=1, device="cpu", threads=3, solos="off").check()
    for bad, message in (({"instruments": ()}, "no instruments"),
                         ({"instruments": ("drums", "drums")}, "each once"),
                         ({"takes": 2}, "two cannot outvote"), ({"takes": 0}, "takes is 1"),
                         ({"takes": True}, "takes is 1"), ({"device": "tpu"}, "device is"),
                         ({"threads": 1.5}, "threads must"), ({"solos": "labels"}, "solos is"),
                         ({"metadata": {"title": "x"}}, "unknown metadata")):
        with pytest.raises(ValueError, match=message):
            Options(**bad).check()
    assert P.take_seeds(1) == (DEFAULT_SEED,) and P.take_seeds(4) == (DEFAULT_SEED, 101, 202, 303)


def test_a_missing_component_is_named_with_its_fix(monkeypatch):
    import songcharter.engines.autochart as AC
    import songcharter.engines.sections as SE
    monkeypatch.setattr(P, "_has", lambda module: False)
    monkeypatch.setattr(SE, "allin1_python", lambda settings: None)

    def no_install():
        raise FileNotFoundError("autochart engine not ready: node (install Node.js, or set SONGCHARTER_NODE)")

    monkeypatch.setattr(AC, "find_install", no_install)
    problems = Engines().missing(Options())
    text = "\n".join(problems)
    for needle in ("pip install songcharter[separate]", "pip install songcharter[bass]",
                   "pip install songcharter[sections]", "SONGCHARTER_ALLIN1_PYTHON", "install Node.js",
                   "SONGCHARTER_AUTOCHART", "--instruments bass,drums"):
        assert needle in text, needle
    assert len(Engines().missing(Options(instruments=("drums",)))) == 2  # separation and sections only
    monkeypatch.setattr(SE, "allin1_python", lambda settings: "/opt/allin1/python")
    assert Engines().missing(Options(instruments=("drums",))) == [problems[0]]  # allin1 alone serves sections


def test_the_real_engines_are_called_with_the_pipelines_settings(tmp_path, monkeypatch):
    """Each Engines method hands its arguments to its engine module as that module expects (the engines
    themselves are replaced by recorders)."""
    import songcharter.engines.adtof as AD
    import songcharter.engines.autochart as AC
    import songcharter.engines.bass as BA
    import songcharter.engines.sections as SE
    import songcharter.separate as SP
    from types import SimpleNamespace as NS
    seen = {}
    mix = np.zeros((2, 100), np.float32)
    monkeypatch.setattr(SP, "separate", lambda m, **k: (seen.setdefault("separate", k) and None) or (
        {"drums": m}, SP.SeparationInfo("htdemucs_6s", "r", "cpu", None, 1.0, False, "abc", 0, 1, 0.25)))
    stems, folder, info = Engines().separate(mix, tmp_path / "stems", "cpu")
    assert seen["separate"] == {"device": "cpu", "cache_dir": tmp_path / "stems"}
    assert folder == tmp_path / "stems" / "abc" and info["key"] == "abc" and list(stems) == ["drums"]

    def result(**k):
        return NS(chart=tmp_path / "c", path=tmp_path / "s", cached=True, info={"k": 1}, **k)

    monkeypatch.setattr(AD, "generate", lambda m, d, out, device: seen.setdefault("adtof", (out, device)) and result())
    monkeypatch.setattr(BA, "generate", lambda m, b, out: seen.setdefault("bass", out) and result())
    monkeypatch.setattr(SE, "find_sections", lambda m, s, out, settings: seen.setdefault(
        "sections", (sorted(s), out, settings)) and result())
    assert Engines().drums(mix, mix, tmp_path / "d", "cuda") == Run(tmp_path / "c", True, {"k": 1})
    assert Engines().bass(mix, mix, tmp_path / "b").path == tmp_path / "c"
    assert Engines().sections(mix, {"drums": mix}, tmp_path / "x", "auto", 3).path == tmp_path / "s"
    assert seen["adtof"] == (tmp_path / "d", "cuda") and seen["bass"] == tmp_path / "b"
    assert seen["sections"] == (["drums"], tmp_path / "x", SE.Settings(device="auto", threads=3))

    monkeypatch.setattr(AC, "find_install", lambda: "the install")
    take = AC.Take(101, tmp_path / "seed_101" / "notes.chart", {"runs": [{"devices": {"x": "cpu"}}]}, False, 9.5)
    monkeypatch.setattr(AC, "generate", lambda inst, audio, out, seeds, **k: seen.setdefault(
        "guitar", (inst, audio, out, tuple(seeds), k)) and [take])
    runs = Engines().guitar(tmp_path / "decode.wav", tmp_path / "g", (DEFAULT_SEED, 101), "cpu", "T", "A")
    assert seen["guitar"] == ("the install", tmp_path / "decode.wav", tmp_path / "g", (DEFAULT_SEED, 101),
                              {"device": "cpu", "title": "T", "artist": "A"})
    assert runs == [Run(take.chart, False, {"runs": [{"devices": {"x": "cpu"}}], "seconds": 9.5,
                                            "devices": {"x": "cpu"}})]
