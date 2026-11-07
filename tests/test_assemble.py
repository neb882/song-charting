"""The assemble step end to end on a synthetic song (click drums, tool charts written for the test: a half-tempo
.chart running 30 ms late with its own Hard, and a trimmed-audio .mid for bass and drums), then the gate's checks,
the config and the command line on their own. Only synthetic audio and charts are used."""
import io
import json
import math
import shutil
import sys
from dataclasses import asdict, replace
from pathlib import Path

import numpy as np
import pytest

import songcharter.assemble as assemble_module
from songcharter import audio as A
from songcharter import lyrics as L
from songcharter.assemble import (CLIP_MARGIN_S, HOPO_RULES, OCTAVE_MAX_BPM, OCTAVE_MIN_ONSETS,
                                  OCTAVE_SHARE, OCTAVE_SHORT, GateIssue, OctaveRules, PartConfig, active_span, assemble,
                                  backbeat_ratio, check_inputs, clip_to_audio, difficulty_rating, failed_folder,
                                  find_scan_chart, grid_octave, last_tick_by, load_config, parse_config, part_rules,
                                  run_scan_chart, scan_chart_issues, scan_chart_song, scan_rules, self_check,
                                  short_intervals, silent_onsets, stem_alignment, trim_silent_edges, verify_folder)
from songcharter.beatgrid import ONSET_TO_BEAT_MS, BeatGrid, OnsetFeatures
from songcharter.chart import (DRUM_ACTIVATION, STAR_POWER, Chart, DrumHit, FretNote, Phrase, SongInfo, Track,
                               write_chart)
from songcharter.cli import main
from songcharter.errors import InputError, ToolError
from songcharter.importers import read_chart, read_song
from songcharter.quantize import RUN_CHORD_S, play_states, quantize_part
from songcharter.starpower import SOLO_RULES, SP_RULES
from songcharter.tempo import Tempo, TempoMap
from songcharter.timed import TimedHit, TimedNote, TimedPart, TimedSong, TimedSpan

SR = A.SAMPLE_RATE
FIRST, PERIOD, BEATS = 0.5, 0.5, 164  # 120 BPM from 0.5 s: 41 measures
DURATION = 84.0
LATE = 0.030         # the guitar tool runs this late
TRIM = 0.07          # the .mid tool trimmed this much audio: input time = its time + TRIM
FORCED_PAIR = 10     # measure holding a 16th pair whose second note the tool forces to a strum
FREE_PAIR = 12       # measure holding an unforced 16th pair (a natural HOPO everywhere)


def beat(k: float) -> float:
    return FIRST + k * PERIOD


# ------------------------------------------------------------------------------------------------ synthetic song

def drum_audio(seed=0) -> np.ndarray:
    """A hat on every beat, a kick on beat 1 and a snare on beat 3 of each bar, a little noise (shape (2, n))."""
    rng = np.random.default_rng(seed)
    y = np.zeros(int(DURATION * SR))
    t = np.arange(int(0.25 * SR)) / SR
    kick = np.sin(2 * np.pi * 55 * t) * np.exp(-t / 0.08)
    snare = (0.5 * np.sin(2 * np.pi * 190 * t) + 0.6 * rng.standard_normal(len(t))) * np.exp(-t / 0.06)
    hat = np.diff(rng.standard_normal(len(t) + 1)) * np.exp(-t / 0.015) * 0.15
    for k in range(BEATS):
        i = int(round(beat(k) * SR))
        y[i:i + len(t)] += hat + (kick if k % 4 == 0 else 0) + (snare if k % 4 == 2 else 0)
    y += rng.standard_normal(len(y)) * 1e-3
    y = (0.4 * y).astype(np.float32)
    return np.stack([y, y])


def guitar_times():
    """The guitar part as (beat position, frets, sustain beats, forced strum)."""
    out = []
    for m in range(2, BEATS // 4 - 1):
        for j in range(8):
            if m % 4 == 0 and j in (1, 2, 3):
                continue  # a sustained chord fills the first beat
            if m % 4 == 0 and j == 0:
                out.append((4 * m, (0, 1), 1.0, False))
                continue
            out.append((4 * m + j / 2, ((0, 1, 2, 1, 0, 1, 2, 3)[j],), 0.0, False))
            if m in (FORCED_PAIR, FREE_PAIR) and j == 5:
                out.append((4 * m + j / 2 + 0.25, (4,), 0.0, m == FORCED_PAIR))
    return out


def write_tool_chart(path):
    """autochart-like: the guitar on a half-tempo (60 BPM) map at resolution 480, every note LATE seconds late, so
    every 8th note with a fret change is a natural HOPO on its own map; Expert and a quarter-note Hard."""
    tm = TempoMap(480, [Tempo(0, 60000)])
    tick = lambda t: round(tm.sec_to_tick(t))  # noqa: E731
    expert, hard = [], []
    for pos, frets, sus, forced in guitar_times():
        t = beat(pos) + LATE
        length = tick(t + sus * PERIOD) - tick(t) if sus else 0
        on_map = tick(t)
        expert.append(FretNote(on_map, frets, length, flip=forced))
        if pos == int(pos):
            hard.append(FretNote(on_map, frets[:1], length))
    chart = Chart(SongInfo("tool", "tool"), tm, [(tick(beat(32)), "verse_1")],
                  [Track("Expert", "Single", expert), Track("Hard", "Single", hard)])
    path.write_text(write_chart(chart), encoding="utf-8", newline="")
    return expert, hard


STRAYS = (0.1, 83.2)  # input seconds of two snare hits the .mid tool put where the drum stem is silent


def write_tool_mid(folder):
    """STRUM-like: bass (quarter notes) and drums (kick, snare, hi-hat 8ths) in a .mid timed against audio with the
    first TRIM seconds cut off; the folder's song.ini sets pro_drums, so the hi-hat is a cymbal. The drums also hold
    the STRAYS, before the drum audio starts and after it ends (not in the returned list: assemble trims them)."""
    mido = pytest.importorskip("mido")
    tick = lambda t: round((t - TRIM) * 2 * 480)  # noqa: E731  120 BPM, 480 ticks per beat
    bass, drums = [], []
    for k in range(8, BEATS - 4):
        bass.append((tick(beat(k)), 96 + k % 3, 120))
        for half in (0, 0.5):
            drums.append((tick(beat(k + half)), 98, 60))
        if k % 4 == 0:
            drums.append((tick(beat(k)), 96, 60))
        if k % 4 == 2:
            drums.append((tick(beat(k)), 97, 60))
    mf = mido.MidiFile(type=1, ticks_per_beat=480)
    mf.tracks.append(mido.MidiTrack([mido.MetaMessage("set_tempo", tempo=500000, time=0)]))
    strays = [(tick(t), 97, 60) for t in STRAYS]
    for name, notes in (("PART BASS", bass), ("PART DRUMS", drums + strays)):
        events = []
        for t, pitch, length in notes:
            events += [(t, 1, mido.Message("note_on", note=pitch, velocity=100)),
                       (t + length, 0, mido.Message("note_off", note=pitch, velocity=0))]
        tr = mido.MidiTrack([mido.MetaMessage("track_name", name=name, time=0)])
        last = 0
        for t, _, msg in sorted(events, key=lambda e: (e[0], e[1])):
            tr.append(msg.copy(time=t - last))
            last = t
        mf.tracks.append(tr)
    folder.mkdir(parents=True, exist_ok=True)
    mf.save(folder / "notes.mid")
    (folder / "song.ini").write_text("[song]\r\nname = tool\r\npro_drums = True\r\n", encoding="utf-8")
    return bass, drums


CONFIG = {
    "_about": "synthetic test song",
    "audio": "mix.wav",
    "stems": {"drums": "drums.wav"},
    "beat_hints": None,
    "lead_in": 2.5,
    "parts": [
        {"instrument": "guitar", "source": "tool/notes.chart", "take_difficulties": "all", "hopo": "forced"},
        {"instrument": "bass", "source": "strum", "time_shift": TRIM},
        {"instrument": "drums", "source": "strum", "time_shift": TRIM, "offset": "auto"},
    ],
    "sections": "allin1.json",
    "metadata": {"name": "Click Song", "artist": "songcharter tests", "album": "Synthetic", "genre": "Test",
                 "year": 2026, "album_track": 1, "charter": "songcharter"},
    "output": "out/Click Song",
}


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    pytest.importorskip("mido")
    root = tmp_path_factory.mktemp("assemble")
    drums = drum_audio()
    tone = np.zeros(drums.shape[1], dtype=np.float32)
    for pos, *_ in guitar_times():
        i = int(beat(pos) * SR)
        tone[i:i + 4000] += (0.05 * np.sin(2 * np.pi * 330 * np.arange(4000) / SR)).astype(np.float32)
    A.write_wav(drums + tone, root / "mix.wav")
    A.write_wav(drums, root / "drums.wav")
    (root / "tool").mkdir()
    expert, hard = write_tool_chart(root / "tool" / "notes.chart")
    bass, kit = write_tool_mid(root / "strum")
    # measures of 2 s from 0.5 s: the 2-measure break joins the verse (under 4), whose 20 measures split in two
    segments = [[0.0, 0.5, "start"], [0.5, 16.5, "intro"], [16.5, 52.5, "verse"], [52.5, 56.5, "break"],
                [56.5, 80.5, "chorus"], [80.5, DURATION, "end"]]
    (root / "allin1.json").write_text(json.dumps({"segments": segments}), encoding="utf-8")
    (root / "song.json").write_text(json.dumps(CONFIG), encoding="utf-8")
    result = assemble(root / "song.json")
    return root, result, {"expert": expert, "hard": hard, "bass": bass, "drums": kit}


# ------------------------------------------------------------------------------------------------ end to end

def test_folder_passes_the_gate(built):
    root, result, _ = built
    assert result.folder == root / "out" / "Click Song" and result.package.folder == result.folder
    assert sorted(p.name for p in result.folder.iterdir()) == ["notes.chart", "report.json", "song.ini", "song.ogg"]
    assert [p.name for p in (root / "out").iterdir()] == ["Click Song"]  # no staging folder or .failed left
    assert result.ok, [i for i in result.issues if i.error]
    assert result.package.sync.ok
    report = json.loads((result.folder / "report.json").read_text(encoding="utf-8"))
    assert report["gate"]["ok"] and report["gate"]["errors"] == 0
    assert report["sync"]["ok"] and report["folder"] == str(result.folder)
    scan = report["gate"]["scan_chart"]
    if find_scan_chart()[0] is None:
        assert not scan["ran"] and any(i.kind == "scanChartNotRun" and not i.error for i in result.issues)
    else:  # DESIGN.md 2.13 step 2: scan-chart itself, and its parsed notes match ours
        assert scan["ran"] and scan["playable"] and scan["chart_issues"] == 0 and scan["self_check_errors"] == 0
        assert scan["folder_issues"] == ["noAlbumArt"] and scan["metadata_issues"] == []


def test_grid_and_lead_in(built):
    _, result, _ = built
    r = result.report
    assert abs(r["grid"]["bpm_median"] - 120) < 0.05
    assert r["grid"]["downbeat_phase"] == 0
    assert r["tempo_map"]["max_error_ms"] <= 3.0 + 1e-6
    tm = result.chart.tempo
    pad = result.lead.pad_seconds
    first = tm.tick_to_sec(result.lead.first_beat * tm.resolution)
    assert first >= 2.5 and abs(first - pad - result.grid.beats[0]) < 0.004  # the first beat, moved by the pad
    assert (result.lead.first_beat * tm.resolution) % (4 * tm.resolution) == 0  # on a measure line


def test_offsets_are_measured_per_part(built):
    """The guitar runs LATE behind the drums; the trimmed .mid lines up once time_shift is added."""
    _, result, _ = built
    off = {k: p["offset"] for k, p in result.report["parts"].items()}
    assert all(o["trusted"] and o["applied"] == o["measured"] for o in off.values())
    assert abs(off["guitar"]["applied"] - off["drums"]["applied"] - LATE) < 0.004
    assert abs(off["bass"]["applied"] - off["drums"]["applied"]) < 0.004


def test_notes_land_on_our_grid(built):
    """Every part on 1/16 (or triplet) lines of our map, and all three on the same spot against the audio: the
    guitar's lateness and the .mid's trim are gone."""
    root, result, tool = built
    tm, pad = result.chart.tempo, result.lead.pad_seconds
    true = np.array([beat(k / 2) for k in range(2 * BEATS)])  # the synthetic 8th lines
    devs = {}
    for t in result.chart.tracks:
        assert all(n.tick % 48 == 0 or n.tick % 64 == 0 for n in t.notes), t.name
        if t.difficulty == "Expert":
            times = np.array(sorted({tm.tick_to_sec(n.tick) - pad for n in t.notes}))
            on = times[np.abs(times - true[np.argmin(np.abs(times[:, None] - true[None, :]), axis=1)]) < 0.06]
            devs[t.instrument] = on - true[np.argmin(np.abs(on[:, None] - true[None, :]), axis=1)]
    for inst, d in devs.items():
        assert len(d) > 100 and np.ptp(d) < 0.008, inst
    assert abs(np.median(devs["Single"]) - np.median(devs["Drums"])) < 0.004
    assert abs(np.median(devs["DoubleBass"]) - np.median(devs["Drums"])) < 0.004
    reps = result.report["parts"]
    assert reps["guitar"]["quantize"]["expert"]["notes_out"] == len({n.tick for n in tool["expert"]})
    assert reps["guitar"]["quantize"]["hard"]["notes_out"] == len(tool["hard"])
    assert reps["bass"]["quantize"]["expert"]["notes_out"] == len(tool["bass"])
    song = read_chart(result.folder / "notes.chart")
    assert len(song.parts[("drums", "expert")].notes) == len(tool["drums"])  # the STRAYS trimmed
    assert all(h.cymbal for h in song.parts[("drums", "expert")].notes if h.pad == 2)  # pro_drums from song.ini


def test_the_guitar_part_makes_chords_in_fast_runs_one_note(built):
    """The guitar part is quantized with the rule on chords in fast runs (quantize.run_chords, RUN_CHORD_S), and
    report.json records it with the chords it changed, per level; the bass and the drums go without it."""
    _, result, _ = built
    q = {k: p["quantize"] for k, p in result.report["parts"].items()}
    assert {d: r["run_chord_s"] for d, r in q["guitar"].items()} == {"expert": RUN_CHORD_S, "hard": RUN_CHORD_S}
    assert all(type(r["run_chords"]) is int for r in q["guitar"].values())
    assert all(r["run_chord_s"] == 0 and r["run_chords"] == 0 for k in ("bass", "drums") for r in q[k].values())


def test_onsets_in_the_silence_around_a_stem_are_trimmed(built):
    """The two stray hits before the drum stem starts and after it ends are gone from every drum level (DESIGN.md
    2.8); parts without their own stem (guitar, bass here) are left alone."""
    _, result, _ = built
    tm, pad = result.chart.tempo, result.lead.pad_seconds
    trimmed = result.report["parts"]["drums"]["trimmed"]
    assert trimmed["stem"] == "drums" and list(trimmed["onsets"]) == ["expert"]
    assert len(trimmed["onsets"]["expert"]) == 2
    assert all(abs(t - s) < 0.07 for t, s in zip(trimmed["onsets"]["expert"], STRAYS))
    start, end = trimmed["kept"]
    for t in result.chart.tracks:
        if t.is_drums:
            times = [tm.tick_to_sec(h.tick) - pad for h in t.notes]
            assert start <= min(times) and max(times) < end, t.name
    assert "trimmed" not in result.report["parts"]["guitar"] and "trimmed" not in result.report["parts"]["bass"]


def test_every_difficulty_and_its_ladder(built):
    _, result, tool = built
    song = read_chart(result.folder / "notes.chart")
    for inst in ("guitar", "bass", "drums"):
        onsets = {d: {round(n.time, 6) for n in song.parts[(inst, d)].notes}
                  for d in ("expert", "hard", "medium", "easy")}
        assert onsets["easy"] <= onsets["medium"] <= onsets["hard"] <= onsets["expert"], inst
        assert len(onsets["easy"]) < len(onsets["medium"]) < len(onsets["hard"]), inst
    # guitar Hard is the tool's own (take_difficulties "all"), Medium and Easy come from it
    assert len(song.parts[("guitar", "hard")].notes) == len(tool["hard"])
    for d in ("hard", "medium", "easy"):
        assert not any(n.tap or (d != "hard" and n.hopo) for n in song.parts[("guitar", d)].notes)
        assert not any(h.double_kick for h in song.parts[("drums", d)].notes)


def test_hopos_follow_our_grid_except_where_forced(built):
    """On the tool's half-tempo map every changing 8th is a natural HOPO; on ours they are strums. The forced strum
    on a 16th survives as a flip, the unforced 16th stays a natural HOPO."""
    _, result, _ = built
    tm, pad = result.chart.tempo, result.lead.pad_seconds
    ex = next(t for t in result.chart.tracks if t.name == "ExpertSingle")
    notes = sorted(ex.notes, key=lambda n: n.tick)
    states = dict(zip((n.tick for n in notes), play_states(notes, tm.resolution)))
    grid = result.grid.beats
    sixteenths = {}
    for n in notes:
        t = tm.tick_to_sec(n.tick) - pad
        k = int(np.argmin(np.abs(grid - t)))
        sixteenths[n.tick] = (k, round((t - grid[k]) / PERIOD * 4) % 4)
    pairs = [t for t, (k, q) in sixteenths.items() if q in (1, 3)]
    assert len(pairs) == 2
    forced, free = sorted(pairs)
    assert states[forced] == "strum" and next(n for n in notes if n.tick == forced).flip
    assert states[free] == "hopo"
    # the other HOPOs: the 8th a 16th after each pair's 16th; none of the source's half-tempo 8th HOPOs
    assert sum(s == "hopo" for s in states.values()) == 3
    assert result.report["tracks"]["guitar"]["expert"]["flips"] == 1


def test_phrases_sections_and_metadata(built):
    """Sections follow DESIGN.md 2.5: the 2-measure break merges into the verse, and the 20-measure verse it makes
    splits into two parts of 10 (with the old 2-measure minimum and no split: Intro, Verse, Break, Chorus)."""
    _, result, _ = built
    tm, pad = result.chart.tempo, result.lead.pad_seconds
    assert [n for _, n in result.chart.sections] == ["Intro", "Verse A", "Verse B", "Chorus"]
    for (tick, _), start in zip(result.chart.sections, (0.5, 16.5, 36.5, 56.5)):
        assert abs(tm.tick_to_sec(tick) - pad - start) < 1.0 and tick % (4 * tm.resolution) == 0
    for t in result.chart.tracks:
        sp = [p for p in t.phrases if p.kind == STAR_POWER]
        assert sp, t.name
        if t.is_drums:
            assert [p for p in t.phrases if p.kind == DRUM_ACTIVATION], t.name
    ini = (result.folder / "song.ini").read_text(encoding="utf-8")
    for line in ("name = Click Song", "artist = songcharter tests", "album = Synthetic", "year = 2026",
                 "album_track = 1", "pro_drums = True"):
        assert line in ini
    for key in ("diff_guitar", "diff_bass", "diff_drums"):
        assert f"{key} = {result.report['ratings'][key[5:]]}" in ini
    chorus = tm.tick_to_sec(result.chart.sections[3][0]) * 1000
    assert f"preview_start_time = {round(chorus)}" in ini


def test_report_matches_the_written_chart(built):
    _, result, _ = built
    report = json.loads((result.folder / "report.json").read_text(encoding="utf-8"))
    song = read_chart(result.folder / "notes.chart")
    for inst, levels in report["tracks"].items():
        for d, stats in levels.items():
            assert stats["onsets"] == len({n.time for n in song.parts[(inst, d)].notes}), (inst, d)
    assert report["sections"]["count"] == 4
    assert set(report["parts"]) == {"guitar", "bass", "drums"}
    q = report["parts"]["guitar"]["quantize"]["expert"]
    assert q["notes_in"] == q["notes_out"] + q["merged"] + q["dropped"]
    assert {"odd_32nds", "moved_25ms", "moved_signed_median"} <= set(q)
    assert report["config"]["parts"][0]["hopo"] == "forced"
    assert report["grid"]["secondary_source"] is None  # the fixture has no guitar or other stem
    assert report["config"]["grid_octave"] == "auto" and report["grid"]["octave"] == 1  # 8ths and 16ths at 120
    stats = report["grid"]["octave_stats"]
    assert stats["pooled_share"] < 0.05 and report["grid"]["octave_reason"] == stats["reason"]
    assert stats["first"]["bpm_median"] == report["grid"]["bpm_median"] and "second" not in stats
    assert 0.0 <= report["phrases"]["drums"]["fill_crash_share"] <= 1.0


class _Stop(Exception):
    pass


def test_the_grid_gets_a_second_stem_and_the_quantizer_the_source_beats(built, tmp_path, monkeypatch):
    """By default the guitar or "other" stem times the beats the drums leave without evidence ("none" turns it off,
    and the mix gets none), each part is quantized with its source's own beats (quantize.odd_32nds), and a tempo the
    grid misses or a long stretch timed by neither stem is warned about."""
    root, result, _ = built
    shutil.copy(root / "drums.wav", tmp_path / "other.wav")
    other, _ = A.read_wav(tmp_path / "other.wav")
    real_grid, real_quantize = assemble_module.beat_grid, assemble_module.quantize_part
    seen: dict = {"beats": []}

    def stopped(audio, *args, secondary=None, **kwargs):
        seen["secondary"] = secondary
        raise _Stop

    def config(**change):
        stems = {"drums": "drums.wav", "other": str(tmp_path / "other.wav")}
        return parse_config({**CONFIG, "stems": stems, **change}, root, tmp_path / "out")

    monkeypatch.setattr(assemble_module, "beat_grid", stopped)
    for change, want in (({}, other), ({"grid_secondary": "none"}, None), ({"grid_source": "mix"}, None),
                         ({"grid_secondary": "mix"}, A.decode(root / "mix.wav"))):
        with pytest.raises(_Stop):
            assemble(config(**change))
        assert (seen["secondary"] is None) if want is None else np.array_equal(seen["secondary"], want), change

    def grid(*args, **kwargs):
        g = real_grid(*args, **kwargs)
        g.stats["tempo_check"] = [(10.0, 30.0, 96.0, 120.0)]
        g.stats["secondary"]["stretches"] += [(40.0, 50.0, 20, 0.25), (60.0, 64.0, 8, 0.0), (70.0, 80.0, 20, 0.75)]
        return g

    def quantize(part, *args):
        seen["beats"].append(args[-1])
        return real_quantize(part, *args)

    monkeypatch.setattr(assemble_module, "beat_grid", grid)
    monkeypatch.setattr(assemble_module, "quantize_part", quantize)
    r = assemble(config()).report
    assert r["grid"]["secondary_source"] == "other" and r["gate"]["ok"]
    # guitar Expert and Hard (take_difficulties "all"), then bass and drums with STRUM's beats moved by time_shift
    assert [list(b) for b in seen["beats"]] == [read_song(root / "tool" / "notes.chart").beats] * 2 + [
        read_song(root / "strum", TRIM).beats] * 2
    assert "tempo 96.0 BPM at 10-30 s is not followed by the grid (120.0 BPM): pass beat hints or start= beats" \
        in r["warnings"]
    lines = [w for w in r["warnings"] if "follow the straight line" in w]
    assert lines == ["beats at 40-50 s follow the straight line (no drum or second-stem evidence): check sync there"]
    # a second stem that only repeats the drums changes no count; the last beats, past the drums' last hit, move by
    # about 1 ms
    for inst, levels in r["tracks"].items():
        for d, stats in levels.items():
            old = result.report["tracks"][inst][d]
            assert {k: v for k, v in stats.items() if not k.endswith("_note")} == \
                {k: v for k, v in old.items() if not k.endswith("_note")}, (inst, d)
            assert all(abs(stats[k] - old[k]) < 0.002 for k in ("first_note", "last_note")), (inst, d)


def test_the_bar_phase_follows_allin1s_downbeats(built, tmp_path):
    """With allin1's downbeats in the sections file, the measures start where they fall (here on the kick's beat 3,
    against its sure beat 1: warned), and the report says so; downbeats split between two beats of the bar are
    flagged with allin1's reason. The fixture's sections file holds none: the kick's phase, 0."""
    root, result, _ = built
    assert result.report["grid"]["downbeat_source"] == "kick" and result.report["grid"]["downbeat_phase"] == 0
    segments = json.loads((root / "allin1.json").read_text(encoding="utf-8"))["segments"]

    def build(downbeats, name):
        (tmp_path / f"{name}.json").write_text(json.dumps({"segments": segments, "downbeats": downbeats}),
                                               encoding="utf-8")
        return assemble(parse_config({**CONFIG, "sections": str(tmp_path / f"{name}.json")}, root,
                                     tmp_path / name))

    on3 = [beat(k) + 0.01 for k in range(2, BEATS, 4)]
    r = build(on3, "on3")
    g, tm, pad = r.report["grid"], r.chart.tempo, r.lead.pad_seconds
    assert (g["downbeat_phase"], g["downbeat_source"], g["downbeats_uncertain"]) == (2, "allin1", False)
    assert g["stats"]["downbeats"]["kick"]["phase"] == 0 and r.report["gate"]["ok"]
    first = tm.tick_to_sec(r.lead.first_beat * tm.resolution)
    assert abs(first - pad - beat(2)) < 0.03 and (r.lead.first_beat * tm.resolution) % (4 * tm.resolution) == 0
    assert [w for w in r.report["warnings"] if w.startswith("downbeats")] == [
        f"downbeats follow allin1's, 2 beat(s) after the kick's beat 1 (bar-phase margin "
        f"{g['stats']['downbeats']['kick']['margin']:.3f}): check where beat 1 is"]
    on2 = [beat(k) + 0.01 for k in range(1, BEATS, 4)]   # one beat after the kick's beat 1, not three
    g = build(on2, "on2").report
    assert [w for w in g["warnings"] if w.startswith("downbeats")] == [
        f"downbeats follow allin1's, 1 beat(s) after the kick's beat 1 (bar-phase margin "
        f"{g['grid']['stats']['downbeats']['kick']['margin']:.3f}): check where beat 1 is"]
    split = [beat(k) for k in range(0, BEATS, 4)][::2] + on3[1::2]   # the sure kick's beat 1 and its beat 3
    g = build(sorted(split), "split").report
    assert (g["grid"]["downbeat_source"], g["grid"]["downbeat_phase"], g["grid"]["downbeats_uncertain"]) == (
        "kick", 0, False)
    assert not [w for w in g["warnings"] if w.startswith("downbeats")]
    on4 = [beat(k) + 0.01 for k in range(3, BEATS, 4)]
    split = on2[::2] + on4[1::2]                                       # beats 2 and 4: neither is the kick's
    g = build(sorted(split), "split2").report
    assert g["grid"]["downbeat_source"] == "allin1" and g["grid"]["downbeats_uncertain"]
    assert [w for w in g["warnings"] if w.startswith("downbeats")] == [
        f"downbeats uncertain (bar-phase margin {g['grid']['downbeat_margin']:.3f}): allin1's downbeats fall on "
        "more than one beat of the bar: check where beat 1 is"]


def test_cli_rebuilds_the_same_chart(built, tmp_path, monkeypatch):
    """Byte-identical notes.chart and song.ini from the command line, a config with a UTF-8 BOM (Windows
    PowerShell's), and a folder name stdout's code page cannot show (cp1252, as on Windows when stdout is a pipe)."""
    root, result, _ = built
    out = tmp_path / "again 気持ち"
    config = root / "bom.json"
    config.write_bytes(b"\xef\xbb\xbf" + (root / "song.json").read_bytes())
    stdout = io.TextIOWrapper(io.BytesIO(), encoding="cp1252")
    monkeypatch.setattr(sys, "stdout", stdout)
    assert main(["assemble", str(config), "--out", str(out)]) == 0
    stdout.flush()
    printed = stdout.buffer.getvalue().decode("cp1252")
    assert "gate: OK" in printed and str(tmp_path / "again \\u6c17\\u6301\\u3061") in printed
    for name in ("notes.chart", "song.ini"):
        assert (out / name).read_bytes() == (result.folder / name).read_bytes()
    again = json.loads((out / "report.json").read_text(encoding="utf-8"))
    assert again["tracks"] == result.report["tracks"] and again["parts"] == json.loads(
        json.dumps(result.report["parts"]))


def test_report_names_the_stems_by_absolute_path(built, tmp_path, monkeypatch):
    """A config whose paths are relative to the working directory (assemble(dict)) still writes absolute stem paths
    into report.json, so the preview finds the stems from any directory."""
    root, _, _ = built
    monkeypatch.chdir(root)
    report = assemble(parse_config(CONFIG, ".", tmp_path / "out")).report
    assert report["stems"]["drums"]["path"] == str((root / "drums.wav").resolve())


def test_gate_rejects_a_folder_with_a_second_chart(built, tmp_path):
    _, result, _ = built
    folder = tmp_path / "copy"
    shutil.copytree(result.folder, folder)
    (folder / "notes.mid").write_bytes(b"MThd")
    issues = verify_folder(folder, result.chart, result.lead.pad_seconds, scan_chart=False)
    assert [i.kind for i in issues if i.error] == ["multipleChart"]
    assert [i.kind for i in issues if not i.error] == ["scanChartNotRun"]
    if find_scan_chart()[0] is not None:  # scan-chart's own verdict, ours on the same kind left to it
        record = {}
        kinds = [i.kind for i in verify_folder(folder, result.chart, result.lead.pad_seconds, record=record)
                 if i.error]
        assert {"notPlayable", "multipleChart"} <= set(kinds) and kinds.count("multipleChart") == 1
        assert record["scan_chart"]["ran"] and not record["scan_chart"]["playable"]


def test_gate_without_scan_chart(built, monkeypatch):
    """Without node (or tools/scan-chart's node_modules) the re-implementation stands in and the gate warns; a gate
    told to require scan-chart fails."""
    _, result, _ = built
    monkeypatch.setattr(assemble_module, "find_scan_chart", lambda: (None, "node is not on PATH"))
    record = {}
    issues = verify_folder(result.folder, result.chart, result.lead.pad_seconds, record=record)
    assert [(i.kind, i.error) for i in issues if i.kind.startswith("scanChart")] == [("scanChartNotRun", False)]
    assert not [i for i in issues if i.error]
    assert record["scan_chart"] == {"ran": False, "reason": "node is not on PATH"}
    required = verify_folder(result.folder, result.chart, result.lead.pad_seconds, scan_chart=True)
    assert [i.kind for i in required if i.error] == ["scanChartNotRun"]


def _contents(folder):
    return {p.name: p.read_bytes() for p in folder.iterdir()}


def test_a_failed_gate_leaves_the_output_alone(built, tmp_path, monkeypatch, capsys):
    """A build the gate fails goes to <output>.failed (exit 1) and the earlier build in <output> stays as it was;
    the next good build replaces <output>, an earlier build's extra file and the stale .failed included."""
    root, result, _ = built
    out = (tmp_path / "Click Song").resolve()
    shutil.copytree(result.folder, out)
    before = _contents(out)
    real = assemble_module.verify_folder
    monkeypatch.setattr(assemble_module, "verify_folder",
                        lambda *a, **k: real(*a, **k) + [GateIssue(None, None, "fake", "a gate error")])
    assert main(["assemble", str(root / "song.json"), "--out", str(out)]) == 1
    printed = capsys.readouterr().out
    failed = failed_folder(out)
    assert "gate: FAILED" in printed and f"song folder: {failed}" in printed and "error fake" in printed
    assert _contents(out) == before
    assert sorted(_contents(failed)) == ["notes.chart", "report.json", "song.ini", "song.ogg"]
    report = json.loads((failed / "report.json").read_text(encoding="utf-8"))
    assert not report["gate"]["ok"] and report["folder"] == str(failed)
    monkeypatch.setattr(assemble_module, "verify_folder", real)
    (out / "album.jpg").write_bytes(b"an earlier build's art")
    assert main(["assemble", str(root / "song.json"), "--out", str(out)]) == 0
    assert [p.name for p in tmp_path.iterdir()] == ["Click Song"]
    assert sorted(_contents(out)) == ["notes.chart", "report.json", "song.ini", "song.ogg"]
    assert (out / "notes.chart").read_bytes() == (result.folder / "notes.chart").read_bytes()
    assert json.loads((out / "report.json").read_text(encoding="utf-8"))["folder"] == str(out)


def test_a_build_that_raises_writes_nothing(built, tmp_path, monkeypatch, capsys):
    """A song.ogg out of sync (simulated) is refused with exit 2: the output keeps the earlier build and its
    report, and the half-written staging folder is gone."""
    root, result, _ = built
    out = (tmp_path / "Click Song").resolve()
    shutil.copytree(result.folder, out)
    before = _contents(out)

    def out_of_sync(folder, *args, **kwargs):  # what build_song_folder raises
        (folder / "notes.chart").write_text("half written", encoding="utf-8")
        raise ToolError("song.ogg is out of sync with the chart: simulated")

    monkeypatch.setattr(assemble_module, "build_song_folder", out_of_sync)
    assert main(["assemble", str(root / "song.json"), "--out", str(out)]) == 2
    assert "out of sync" in capsys.readouterr().err
    assert _contents(out) == before and [p.name for p in tmp_path.iterdir()] == ["Click Song"]


def test_cli_exit_codes(built, tmp_path, monkeypatch, capsys):
    """2 for a bad config or input, found before any audio work and never 1 (a failed gate); 3, with the
    traceback, for a bug."""
    root, _, _ = built
    for change, message in (({"audio": "missing.wav"}, "not found: audio"),
                            ({"parts": 5}, "parts must be a list"),
                            ({"stems": ["drums.wav"]}, "stems must be an object"),
                            ({"parts": [{**CONFIG["parts"][0], "time_shift": None}]}, "time_shift must be a number"),
                            ({"tempo_tolerance": -1}, "tempo_tolerance must be above 0"),
                            ({"metadata": {**CONFIG["metadata"], "genre": ""}}, "needs 'genre'"),
                            ({"audio": "allin1.json"}, "ffmpeg could not read")):
        (root / "bad.json").write_text(json.dumps({**CONFIG, **change}), encoding="utf-8")
        assert main(["assemble", str(root / "bad.json"), "--out", str(tmp_path / "x")]) == 2, change
        assert message in capsys.readouterr().err, change
    (root / "bad.json").write_text("{'audio': ", encoding="utf-8")
    assert main(["assemble", str(root / "bad.json")]) == 2 and "is not a JSON config" in capsys.readouterr().err
    assert not (tmp_path / "x").exists()

    def bug(_):
        raise KeyError("a bug")

    monkeypatch.setattr(assemble_module, "assemble", bug)
    assert main(["assemble", str(root / "song.json"), "--out", str(tmp_path / "x")]) == 3
    err = capsys.readouterr().err
    assert "Traceback" in err and "KeyError: 'a bug'" in err and "internal error" in err


# ------------------------------------------------------------------------------------------------ the gate's rules

def _song(parts, sections=((5.0, "Intro"),)):
    return TimedSong("test", {(p.instrument, p.difficulty): p for p in parts}, list(sections))


def _kinds(issues):
    return sorted(((i.instrument, i.difficulty, i.kind) for i in issues if i.error), key=lambda k: str(k))


def test_scan_rules_accept_a_clean_chart():
    notes = [TimedNote(3 + 0.25 * k, (k % 4,)) for k in range(300)]
    drums = [TimedHit(3 + 0.25 * k, k % 2) for k in range(300)]
    sp = [TimedSpan(10, 12)]
    parts = [TimedPart("guitar", "expert", notes, sp), TimedPart("guitar", "hard", notes[::2], sp),
             TimedPart("drums", "expert", drums, sp, activation=[TimedSpan(20, 22)])]
    assert scan_rules(_song(parts)) == []


@pytest.mark.parametrize("difficulty,frets,bad", [
    ("hard", (0, 4), True), ("hard", (0, 3), False), ("medium", (4,), True), ("medium", (0, 3), True),
    ("medium", (0, 2), False), ("easy", (3,), True), ("easy", (2,), False), ("expert", (0, 1, 2, 3, 4), True)])
def test_scan_rules_forbidden_frets(difficulty, frets, bad):
    p = TimedPart("guitar", difficulty, [TimedNote(3.0, (0,)), TimedNote(4.0, frets)])
    ex = TimedPart("guitar", "expert", [TimedNote(3.0, (1,)), TimedNote(4.0, (1,))])
    kinds = [k for _, _, k in _kinds(scan_rules(_song([ex, p])))]
    assert (("difficultyForbiddenNote" in kinds) or ("invalidChord" in kinds)) == bad


def test_scan_rules_drums_sustains_phrases_and_timing():
    drums = [TimedHit(3.0, 0, double_kick=True), TimedHit(4.0, 0), TimedHit(4.0, 1), TimedHit(4.0, 2),
             TimedHit(5.0, 1), TimedHit(5.0, 2), TimedHit(5.0, 3)]
    guitar = [TimedNote(1.5, (0,)),                 # inside the first 2 s
              TimedNote(3.0, (1,), end=3.05),        # babySustain (50 ms)
              TimedNote(4.0, (1,), end=4.15),        # shortSustain (150 ms: Encore)
              TimedNote(4.18, (2,)),                 # 30 ms after a sustain: badSustainGap
              TimedNote(4.19, (3,)),                 # 10 ms after the previous note: brokenNote
              TimedNote(6.0, (2,), end=6.5), TimedNote(6.55, (3,))]  # 50 ms gap: Encore's sustainGap
    parts = [TimedPart("drums", "expert", drums[:1]), TimedPart("drums", "easy", drums[1:]),
             TimedPart("guitar", "expert", guitar, [TimedSpan(8, 9)], [TimedSpan(8, 9)])]
    issues = scan_rules(_song(parts), pad_seconds=1.0, audio_end=6.4)
    kinds = _kinds(issues)
    assert ("drums", "easy", "difficultyForbiddenNote") in kinds   # a kick with two pads on Easy
    assert ("drums", "easy", "invalidChord") in kinds
    for k in ("smallLeadingSilence", "babySustain", "shortSustain", "badSustainGap", "brokenNote", "sustainGap",
              "emptyStarPower", "emptySoloSection", "noteAfterAudio"):
        assert ("guitar", "expert", k) in kinds, k
    assert next(i for i in issues if i.kind == "brokenNote").time == pytest.approx(3.19)  # input seconds
    hard = scan_rules(_song([TimedPart("drums", "expert", [TimedHit(3.0, 1)]),
                             TimedPart("drums", "hard", [TimedHit(3.0, 0, double_kick=True)])]))
    assert ("drums", "hard", "difficultyForbiddenNote") in _kinds(hard)


def test_scan_rules_song_level():
    long = [TimedNote(3 + 0.5 * k, (k % 3,)) for k in range(200)]
    hits = [TimedHit(3 + 0.5 * k, 1) for k in range(200)]
    parts = [TimedPart("guitar", "expert", long), TimedPart("guitar", "hard", list(long)),
             TimedPart("bass", "hard", long[:10]), TimedPart("drums", "expert", hits, [TimedSpan(10, 11)])]
    kinds = _kinds(scan_rules(_song(parts, sections=())))
    assert (None, None, "noSections") in kinds
    assert ("guitar", "expert", "noStarPower") in kinds
    assert ("guitar", "hard", "difficultyNotReduced") in kinds
    assert ("bass", None, "noExpert") in kinds
    assert ("drums", "expert", "noDrumActivationLanes") in kinds
    assert _kinds(scan_rules(_song([]))) == [(None, None, "noNotes")]


def _small_chart():
    tm = TempoMap.from_beats(np.arange(64) * 0.5)
    notes = [FretNote(192 * (8 + k), (k % 3,), 192 if k == 4 else 0) for k in range(20)]
    notes.append(FretNote(192 * 27 + 48, (2,)))  # a 16th after the last note: a natural HOPO
    drums = [DrumHit(192 * (8 + k), k % 2) for k in range(20)] + [DrumHit(192 * 9, 2, cymbal=True)]
    return Chart(SongInfo("x", "y"), tm, [(192 * 8, "Intro")],
                 [Track("Expert", "Single", notes, [Phrase(192 * 8, 192 * 4)], [(192 * 12, 192 * 14)]),
                  Track("Expert", "Drums", drums, [Phrase(192 * 8, 192 * 4), Phrase(192 * 20, 192 * 2, DRUM_ACTIVATION)])])


def test_self_check_finds_what_the_file_lost(tmp_path):
    chart = _small_chart()
    text = write_chart(chart)
    path = tmp_path / "notes.chart"
    path.write_text(text, encoding="utf-8", newline="")
    assert self_check(chart, read_chart(path)) == []
    lines = {f"  {192 * 9} = N 66 0\r\n": "",                                          # the cymbal marker
             f"  {192 * 13} = N 2 0\r\n": f"  {192 * 13} = N 2 0\r\n  {192 * 13} = N 5 0\r\n",  # a flip
             f"  {192 * 12} = N 1 192\r\n": f"  {192 * 12} = N 1 96\r\n"}                  # a shorter sustain
    tampered = text
    for old, new in lines.items():
        assert old in tampered
        tampered = tampered.replace(old, new)
    path.write_text(tampered, encoding="utf-8", newline="")
    msgs = [i.message for i in self_check(chart, read_chart(path))]
    assert any("hits read back differently" in m for m in msgs)
    assert any("different hopo" in m for m in msgs)
    assert any("different sustain" in m for m in msgs)
    assert all(isinstance(i, GateIssue) and i.kind == "selfCheck" for i in self_check(chart, read_chart(path)))


def _scan_chart():
    command, why = find_scan_chart()
    if command is None:
        pytest.skip(f"scan-chart not available: {why}")
    return command


def test_scan_chart_read_back(tmp_path):
    """scan-chart's own parse of what we wrote matches the chart (notes, flags, sustains, star power, solo, fill,
    sections), and the self-check on it finds what a tampered file lost; its issues map to gate errors."""
    command = _scan_chart()
    chart = _small_chart()
    text = write_chart(chart)
    (tmp_path / "notes.chart").write_text(text, encoding="utf-8", newline="")
    data = run_scan_chart(tmp_path, command)
    assert self_check(chart, scan_chart_song(data)) == []
    kinds = {i.kind for i in scan_chart_issues(data)}  # no song.ini or audio, one 120 BPM marker
    assert {"notPlayable", "noAudio", "noMetadata", "isDefaultBPM"} <= kinds and "noAlbumArt" not in kinds
    tampered = (text.replace(f"  {192 * 9} = N 66 0\r\n", "")
                .replace(f"  {192 * 13} = N 2 0\r\n", f"  {192 * 13} = N 2 0\r\n  {192 * 13} = N 5 0\r\n")
                .replace(f"  {192 * 12} = N 1 192\r\n", f"  {192 * 12} = N 1 96\r\n"))
    (tmp_path / "notes.chart").write_text(tampered, encoding="utf-8", newline="")
    msgs = [i.message for i in self_check(chart, scan_chart_song(run_scan_chart(tmp_path, command)))]
    for what in ("hits read back differently", "different hopo", "different sustain"):
        assert any(what in m for m in msgs), what


def _edit_track(text: str, track: str, change) -> str:
    """notes.chart text with one track's lines (without indent) replaced by change(lines), sorted as we write."""
    head, rest = text.split(f"[{track}]\r\n{{\r\n", 1)
    body, tail = rest.split("}\r\n", 1)
    lines = change([line.strip() for line in body.split("\r\n") if line.strip()])
    order = {"N": 0, "S": 1, "E": 2}
    lines.sort(key=lambda s: (int(s.split()[0]), order[s.split()[2]],
                              int(s.split()[3]) if s.split()[2] in "NS" else 0))
    return head + f"[{track}]\r\n{{\r\n" + "".join(f"  {s}\r\n" for s in lines) + "}\r\n" + tail


def _ticks(lines, codes=("0", "1", "2", "3", "4")):
    return sorted({int(s.split()[0]) for s in lines if s.split()[2] == "N" and s.split()[3] in codes})


def _plain(lines):
    """A note tick with one fret and no sustain whose next note is at least an 8th later."""
    ticks = _ticks(lines)
    for a, b in zip(ticks[40:], ticks[41:]):
        notes = [s for s in lines if int(s.split()[0]) == a and s.split()[2] == "N"]
        if b - a >= 96 and len(notes) == 1 and notes[0].split()[4] == "0":
            return a, notes[0].split()[3], b
    raise AssertionError("no plain note")


def _hand_tick(lines):
    return next(t for t in _ticks(lines, ("1", "2", "3", "4"))[30:]
                if len({s.split()[3] for s in lines if int(s.split()[0]) == t and s.split()[3] in "1234"}) == 1)


def _sustain(lines, length):
    a, fret, _ = _plain(lines)
    return [s if s != f"{a} = N {fret} 0" else f"{a} = N {fret} {length}" for s in lines]


def _sustain_into(lines, gap):
    a, fret, b = _plain(lines)
    return [s if s != f"{a} = N {fret} 0" else f"{a} = N {fret} {b - a - gap}" for s in lines]


# each: (track, change, the error both must find); the synthetic chart is at 120 BPM, Resolution 192
MUTATIONS = {
    "five_note_chord": ("ExpertSingle", lambda L: L + [f"{_plain(L)[0]} = N {f} 0" for f in "01234"
                                                        if f != _plain(L)[1]], ("guitar", "expert", "invalidChord")),
    "easy_blue": ("EasySingle", lambda L: [s if int(s.split()[0]) != _ticks(L)[20] or s.split()[2] != "N"
                                           else s.split()[0] + " = N 3 0" for s in L],
                  ("guitar", "easy", "difficultyForbiddenNote")),
    "broken_note": ("ExpertSingle", lambda L: L + [f"{_plain(L)[0] + 4} = N {(int(_plain(L)[1]) + 1) % 5} 0"],
                    ("guitar", "expert", "brokenNote")),
    "baby_sustain": ("ExpertSingle", lambda L: _sustain(L, 20), ("guitar", "expert", "babySustain")),  # 52 ms
    "bad_sustain_gap": ("ExpertSingle", lambda L: _sustain_into(L, 6), ("guitar", "expert", "badSustainGap")),
    "three_hands": ("ExpertDrums", lambda L: L + [f"{_hand_tick(L)} = N {p} 0" for p in "234"
                                                  if f"{_hand_tick(L)} = N {p} 0" not in L],
                    ("drums", "expert", "invalidChord")),
    "hard_double_kick": ("HardDrums", lambda L: L + [f"{_ticks(L, ('0',))[5]} = N 32 0"],
                         ("drums", "hard", "difficultyForbiddenNote")),
    "empty_star_power": ("ExpertDoubleBass", lambda L: L + ["96 = S 2 96"], ("bass", "expert", "emptyStarPower")),
    "empty_solo": ("ExpertDoubleBass", lambda L: L + ["96 = E solo", "190 = E soloend"],
                   ("bass", "expert", "emptySoloSection")),
}


def test_scan_rules_agree_with_scan_chart(built, tmp_path):
    """The stand-in gate and scan-chart find the same errors (track and kind) on broken copies of a built folder,
    so the two cannot drift apart; Encore's stricter rules (ours only) are left out of the comparison."""
    command = _scan_chart()
    _, result, _ = built
    text = (result.folder / "notes.chart").read_bytes().decode("utf-8")  # CRLF kept
    ours_only = {"smallLeadingSilence", "shortSustain", "sustainGap", "noteAfterAudio"}

    def both(name, chart_text):
        folder = tmp_path / name
        folder.mkdir()
        (folder / "notes.chart").write_text(chart_text, encoding="utf-8", newline="")
        for f in ("song.ini", "song.ogg"):
            shutil.copy(result.folder / f, folder / f)
        scan = {(i.instrument, i.difficulty, i.kind) for i in scan_chart_issues(run_scan_chart(folder, command))}
        ours = {(i.instrument, i.difficulty, i.kind) for i in scan_rules(read_chart(folder / "notes.chart"),
                                                                       tempo=result.chart.tempo) if i.error}
        return scan, {k for k in ours if k[2] not in ours_only}

    assert both("clean", text) == (set(), set())
    for name, (track, change, want) in MUTATIONS.items():
        scan, ours = both(name, _edit_track(text, track, change))
        assert want in scan and scan == ours, (name, scan, ours)
    events = text.split("[Events]\r\n{\r\n", 1)
    scan, ours = both("no_sections", events[0] + "[Events]\r\n{\r\n" + events[1].split("}\r\n", 1)[1])
    assert scan == ours == {(None, None, "noSections")}


def test_hopo_forced_from_the_importer_and_forced_only_quantizing(tmp_path):
    """The importer marks the states its source forced; quantize's forced_only keeps those and lets the rest follow
    the natural rule on our grid ("forced" in assemble), while "source" reproduces every played state."""
    expert, _ = write_tool_chart(tmp_path / "notes.chart")
    part = read_chart(tmp_path / "notes.chart").parts[("guitar", "expert")]
    assert sum(n.hopo_forced for n in part.notes) == 1 and sum(n.hopo for n in part.notes) > 100
    shifted = read_chart(tmp_path / "notes.chart").shifted(1.0).parts[("guitar", "expert")]
    assert [n.hopo_forced for n in shifted.notes] == [n.hopo_forced for n in part.notes]
    tm = TempoMap.from_beats([0.0] + [beat(k) + LATE for k in range(BEATS)])  # our grid, with the tool's lateness
    counts = {}
    for mode, rules in HOPO_RULES.items():
        track, _ = quantize_part(TimedPart("guitar", "expert", part.notes), tm, 0.0, 0.0, rules)
        states = play_states(sorted(track.notes, key=lambda n: n.tick), tm.resolution)
        counts[mode] = states.count("hopo")
    assert counts["source"] == sum(n.hopo for n in part.notes)  # every artefact HOPO reproduced
    # natural: each 16th and the 8th after it (both 1/16 apart); forced: the forced 16th strums
    assert counts["natural"] == 4 and counts["forced"] == 3


# ------------------------------------------------------------------------------------------------ helpers

def test_difficulty_rating_models():
    tm = TempoMap.from_beats(np.arange(400) * 0.25)  # 240 BPM map: a beat is 0.25 s
    drums = Track("Expert", "Drums", [DrumHit(192 * k, k % 2) for k in range(240)])  # 4 hits/s for 60 s
    rating, f = difficulty_rating(drums, tm)
    assert f["avg_nps"] == pytest.approx(240 / 59.75, rel=1e-3) and f["max_nps_1s"] == 4.0
    assert f["value"] == pytest.approx(-0.63 + 0.325 * f["avg_nps"] + 0.178 * 4.0, abs=2e-3) and rating == 1
    guitar = Track("Expert", "Single", [FretNote(192 * k, ((0,), (1,), (2,), (0, 1))[k % 4]) for k in range(240)])
    rating, f = difficulty_rating(guitar, tm)
    assert f["chord"] == 0.25 and f["move"] == 1.0 and f["hopo"] == 0.0
    assert 0 <= rating <= 6 and difficulty_rating(Track("Expert", "Single", []), tm) == (0, {})


def test_stem_alignment_and_silence():
    rng = np.random.default_rng(3)
    mix = (rng.standard_normal((2, SR * 12)) * 0.1).astype(np.float32)
    assert stem_alignment(mix, mix * 0.5)["ok"]
    late = np.concatenate([np.zeros((2, 50), np.float32), mix[:, :-50]], axis=1)
    check = stem_alignment(mix, late * 0.5)
    assert not check["ok"] and abs(check["lag_samples"] - 50) < 0.5
    assert stem_alignment(mix, mix * 0.001)["checked"] is False  # -60 dB: not checked
    levels = np.full(100, -10.0)
    levels[60:] = -50.0
    assert silent_onsets([1.0, 7.0], levels, 0.1) == [7.0]


def test_trim_silent_edges():
    """Onsets before the stem's first loud frame or after its last go from every level (by time, so the levels stay
    nested); a stem under which Expert would lose every note is not the part's, and nothing is trimmed."""
    tm = TempoMap.from_beats(np.arange(200) * 0.5)  # 120 BPM from 0 s: tick 192 k is k / 2 seconds
    levels = np.full(1000, -60.0)
    levels[100:800] = -10.0  # 100 ms frames: the stem plays from 10 s to 80 s
    assert active_span(levels) == pytest.approx((9.8, 80.05))
    beats = (10, 20, 40, 100, 159, 161, 170)  # 5, 10, 20, 50, 79.5, 80.5 and 85 s
    expert = Track("Expert", "DoubleBass", [FretNote(192 * k, (k % 3,)) for k in beats])
    hard = Track("Hard", "DoubleBass", expert.notes[::2])
    out, removed = trim_silent_edges({"expert": expert, "hard": hard}, levels, tm, 0.0)
    assert removed == {"expert": [5.0, 80.5, 85.0], "hard": [5.0, 85.0]}
    assert [n.tick // 192 for n in out["expert"].notes] == [20, 40, 100, 159]
    assert [n.tick // 192 for n in out["hard"].notes] == [40, 159]
    shifted, _ = trim_silent_edges({"expert": expert}, levels, tm, 1.0)  # input second t sits at t + pad
    assert [n.tick // 192 for n in shifted["expert"].notes] == [40, 100, 159, 161]
    late = np.full(1000, -60.0)
    late[900:] = -10.0
    assert trim_silent_edges({"expert": expert}, late, tm, 0.0) == ({"expert": expert}, {})


def test_config_parsing_and_errors(tmp_path):
    cfg = parse_config(CONFIG, tmp_path)
    assert cfg.audio == tmp_path / "mix.wav" and cfg.output == tmp_path / "out" / "Click Song"
    assert cfg.parts[1].source == tmp_path / "strum" and cfg.parts[1].from_instrument == "bass"
    assert cfg.parts[0].take_difficulties == "all" and cfg.parts[1].hopo == "forced" and cfg.parts[2].offset == "auto"
    assert cfg.sections == str(tmp_path / "allin1.json") and cfg.bpm is None and cfg.solos == "off"
    (tmp_path / "c.json").write_text(json.dumps({**CONFIG, "parts": [{**CONFIG["parts"][0], "offset": 0.02}]}))
    loaded = load_config(tmp_path / "c.json", tmp_path / "elsewhere")
    assert loaded.output == tmp_path / "elsewhere" and loaded.parts[0].offset == 0.02
    bad = [
        ({"colour": 1}, "unknown key"),
        ({"parts": []}, "no parts"),
        ({"parts": [{"instrument": "keys", "source": "x"}]}, "instruments"),
        ({"parts": [{"instrument": "drums", "source": "x", "source_instrument": "guitar"}]}, "drums come only"),
        ({"parts": [CONFIG["parts"][0], CONFIG["parts"][0]]}, "more than one part"),
        ({"parts": [{**CONFIG["parts"][0], "hopo": "maybe"}]}, "hopo"),
        ({"sections": "from:keys"}, "no part is named"),
        ({"grid_mode": "loose"}, "grid_mode"),
        ({"grid_octave": 3}, "grid_octave is 'auto', 1 or 2, not 3"),
        ({"grid_octave": True}, "grid_octave is 'auto', 1 or 2, not True"),
        ({"grid_octave": "double"}, "grid_octave is 'auto', 1 or 2"),
        ({"metadata": {"name": "x"}}, "artist"),
        ({"beat_hints": {"tempo": 120}}, "unknown key"),
        ({"output": "strum"}, "would be overwritten"),
        # types and ranges, each named
        ({"parts": 5}, "parts must be a list"),
        ({"parts": [{**CONFIG["parts"][0], "source": 5}]}, r"parts\[0\].source must be a non-empty string"),
        ({"parts": [{**CONFIG["parts"][0], "time_shift": None}]}, r"parts\[0\].time_shift must be a number"),
        ({"parts": [{**CONFIG["parts"][0], "offset": "manual"}]}, "offset must be 'auto' or a number"),
        ({"parts": [{**CONFIG["parts"][0], "trim_silence": "yes"}]}, "trim_silence must be true or false"),
        ({"stems": ["drums.wav"]}, "stems must be an object"),
        ({"grid_source": ["drums"]}, "grid_source must be a string or null"),
        ({"grid_secondary": "guitar"}, "grid_secondary 'guitar' is not 'mix', 'none' or one of the stems"),
        ({"grid_secondary": 3}, "grid_secondary must be a string or null"),
        ({"quality": True}, "quality must be a number"),
        ({"quality": 99}, "quality must be at most 10"),
        ({"tempo_tolerance": -1}, "tempo_tolerance must be above 0"),
        ({"lead_in": 1.0}, "lead_in must be at least 2.0"),
        ({"beat_hints": {"bpm": 0}}, "bpm must be above 0"),
        ({"metadata": {**CONFIG["metadata"], "album": ""}}, "needs 'album'"),
        ({"metadata": {k: v for k, v in CONFIG["metadata"].items() if k != "year"}}, "needs 'year'"),
        ({"metadata": {**CONFIG["metadata"], "album_track": 2.5}}, "album_track must be a whole number"),
        ({"album_art": "cover.gif"}, "not a .png or .jpg"),
        ({"solos": []}, "at least one section name"),
        ({"solos": ["Solo 1", ""]}, r"solos\[1\] must be a non-empty string"),
        ({"solos": "sometimes"}, "a list of section names"),
        ({"levels": "expert"}, "levels must be a non-empty list"),
        ({"levels": ["hard", "easy"]}, "levels must include expert"),
        ({"levels": ["expert", "insane"]}, "unknown difficulty insane"),
        ({"parts": [{**CONFIG["parts"][1], "takes": "run2.chart"}]}, r"parts\[0\].takes must be a list"),
        ({"parts": [{**CONFIG["parts"][0], "takes": ["a.chart", "b.chart"]}]}, "takes splice Expert only"),
        ({"parts": [{**CONFIG["parts"][1], "takes": ["a.chart"]}]}, "at least two more runs"),
        ({"parts": [{**CONFIG["parts"][1], "takes": ["r2/notes.chart", "./r2/notes.chart"]}]}, "listed twice"),
        ({"parts": [{**CONFIG["parts"][1], "takes": ["r2", "strum"]}]}, "strum is listed twice"),
        ({"parts": [{**CONFIG["parts"][1], "takes": ["r2/notes.chart", "r3"]}], "output": "r2"},
         "holds part bass's take: it would be overwritten"),
        ({"parts": [{**CONFIG["parts"][1], "takes": ["r2/notes.chart", "r3"]}], "output": "r3"},
         "holds part bass's take: it would be overwritten"),
    ]
    for change, message in bad:
        with pytest.raises(ValueError, match=message):
            parse_config({**CONFIG, **change}, tmp_path)
    assert parse_config({**CONFIG, "sections": "from:guitar"}, tmp_path).sections == "from:guitar"
    assert parse_config(CONFIG, tmp_path).grid_secondary is None  # the default: the guitar stem, else other
    assert parse_config(CONFIG, tmp_path).levels == ("expert", "hard", "medium", "easy")
    named = parse_config({**CONFIG, "solos": ["Solo 1", "solo 2"], "levels": ["Easy", "expert"]}, tmp_path)
    assert named.solos == ("Solo 1", "solo 2") and named.levels == ("expert", "easy")  # names as written; in order
    for value, want in (("None", ""), ("mix", "mix"), ("drums", "drums")):
        assert parse_config({**CONFIG, "grid_secondary": value}, tmp_path).grid_secondary == want
    meta = {k: v for k, v in CONFIG["metadata"].items() if k != "charter"}
    cfg = parse_config({**CONFIG, "metadata": meta, "parts": [{**CONFIG["parts"][0], "offset": "AUTO",
                                                                 "trim_silence": False}]}, tmp_path)
    assert cfg.metadata["charter"] == "songcharter" and cfg.metadata["year"] == "2026"
    assert cfg.parts[0].offset == "auto" and cfg.parts[0].trim_silence is False and cfg.parts[0].time_shift == 0.0
    assert cfg.parts[0].takes == () and parse_config(
        {**CONFIG, "parts": [{**CONFIG["parts"][1], "takes": ["r2/notes.chart", "r3"]}]}, tmp_path
    ).parts[0].takes == (tmp_path / "r2" / "notes.chart", tmp_path / "r3")


def test_check_inputs(tmp_path):
    """Every named file must exist and the sections file be an allin1 result (its beats, when it has them, times);
    the output folder (and its .failed) may hold only what a build writes, plus OS clutter."""
    for name in ("mix.wav", "drums.wav", "tool/notes.chart", "strum/notes.mid"):
        (tmp_path / name).parent.mkdir(exist_ok=True)
        (tmp_path / name).write_bytes(b"x")
    (tmp_path / "allin1.json").write_text(json.dumps({"segments": []}), encoding="utf-8")
    cfg = parse_config(CONFIG, tmp_path)
    check_inputs(cfg)
    out = cfg.output
    out.mkdir(parents=True)
    for name in ("notes.chart", "song.ogg", "report.json", "Album.PNG", "Thumbs.db", ".DS_Store"):
        (out / name).write_bytes(b"")
    check_inputs(cfg)
    for name in ("notes.mid", "Songs"):  # Clone Hero's Songs folder holds song folders
        (out / name).mkdir() if name == "Songs" else (out / name).write_bytes(b"")
        with pytest.raises(ValueError, match=rf"holds what a build does not write \({name}\)"):
            check_inputs(cfg)
        (out / name).rmdir() if name == "Songs" else (out / name).unlink()
    failed_folder(out).mkdir()
    (failed_folder(out) / "notes.txt").write_text("mine", encoding="utf-8")
    with pytest.raises(ValueError, match="Click Song.failed holds"):
        check_inputs(cfg)
    shutil.rmtree(failed_folder(out))
    (tmp_path / "allin1.json").write_text(json.dumps({"segments": [], "beats": [0.5, 1.0]}), encoding="utf-8")
    check_inputs(cfg)  # allin1's beats (the second pass's start on a tempo change, _octave_pass)
    (tmp_path / "allin1.json").write_text(json.dumps({"segments": [], "beats": ["x"]}), encoding="utf-8")
    with pytest.raises(InputError, match="not an allin1 result .*'beats' is not a list of times"):
        check_inputs(cfg)
    (tmp_path / "allin1.json").write_text(json.dumps({"segments": [], "downbeats": [0.5]}), encoding="utf-8")
    check_inputs(cfg)  # allin1's downbeats (the bar phase, beatgrid.with_downbeats)
    (tmp_path / "allin1.json").write_text(json.dumps({"segments": [], "downbeats": [None]}), encoding="utf-8")
    with pytest.raises(InputError, match="not an allin1 result .*'downbeats' is not a list of finite times"):
        check_inputs(cfg)
    (tmp_path / "allin1.json").write_text(json.dumps({"sections": []}), encoding="utf-8")
    with pytest.raises(ValueError, match="not an allin1 result"):
        check_inputs(cfg)
    (tmp_path / "mix.wav").unlink()
    (tmp_path / "drums.wav").unlink()
    with pytest.raises(FileNotFoundError, match="not found: audio .*mix.wav; stem drums .*drums.wav"):
        check_inputs(cfg)


def _earlier_build(folder, background=None, report=None, size=None):
    """A folder an earlier build made: its four files, with report.json's `art` saying it added `background` (a file
    name; `size`: the bytes it recorded) or none (`report`: report.json's text instead)."""
    folder.mkdir(parents=True, exist_ok=True)
    for name in ("notes.chart", "song.ini", "song.ogg"):
        (folder / name).write_bytes(b"earlier")
    record = ({"added": True, "file": background, "from": "given"} if background else
              {"added": False, "file": None, "from": None})
    if size is not None:
        record["bytes"] = size
    (folder / "report.json").write_text(report if report is not None else json.dumps(
        {"gate": {"ok": True}, "art": {"album_art": {"added": False, "file": None, "from": None},
                                       "background": record}}), encoding="utf-8")
    return folder


def _staged(tmp_path, *names):
    """A new build in its staging folder, with `names` (a background) besides the four files; its report.json
    records the background as the build's does."""
    staging = tmp_path / "staging"
    staging.mkdir()
    for name in ("notes.chart", "song.ini", "song.ogg", *names):
        (staging / name).write_bytes(b"new")
    _earlier_build(tmp_path / "record", background=names[0] if names else None)
    shutil.move(tmp_path / "record" / "report.json", staging / "report.json")
    shutil.rmtree(tmp_path / "record")
    return staging


def test_a_persons_background_in_an_earlier_builds_folder_is_kept(tmp_path):
    """A background.* is a build's own only when the earlier build's report.json says it added that file (M5-12):
    v0.1 never wrote one, so a background.png in a folder it made is the person's. The output check refuses that
    folder, as v0.1.0 did, and nothing deletes the file; one a build recorded is replaced, or removed by a build
    without a background, as since M4-11."""
    mine = b"the person's own picture"
    reports = [None, '{"art": {"background": {"added": true}}}', '{"art": {"background": {"added": "yes", '
               '"file": "background.png"}}}', '{"art": null}', "[1, 2]", "not json", "￾\x00"]
    for i, report in enumerate(reports):
        out = _earlier_build(tmp_path / f"Made Up Song {i}", report=report)
        (out / "background.png").write_bytes(mine)
        if i == 0:
            (out / "report.json").unlink()   # no report at all
        with pytest.raises(InputError, match=r"Made Up Song \d+ holds what a build does not write \(background.png\)"):
            assemble_module.check_output(out)
    out = _earlier_build(tmp_path / "Made Up Artist - Made Up Song", background="background.jpg")
    (out / "background.png").write_bytes(mine)   # a background beside the one the build wrote: the person's
    with pytest.raises(InputError, match=r"holds what a build does not write \(background.png\)"):
        assemble_module.check_output(out)
    staging = _staged(tmp_path)
    assemble_module._install(staging, out)   # had it been reached: the build's own goes, the person's stays
    assert sorted(p.name for p in out.iterdir()) == ["background.png", "notes.chart", "report.json", "song.ini",
                                                     "song.ogg"]
    assert (out / "background.png").read_bytes() == mine and (out / "notes.chart").read_bytes() == b"new"
    # what a build recorded is its own: replaced by the next build's, or removed by one without
    for upper in (False, True):
        out = _earlier_build(tmp_path / f"Recorded {upper}", background="background.jpg")
        (out / ("BACKGROUND.JPG" if upper else "background.jpg")).write_bytes(b"ours")
        assemble_module.check_output(out)
        assemble_module._install(_staged(tmp_path, "background.jpg"), out)
        assert (out / "background.jpg").read_bytes() == b"new" and not (out / "BACKGROUND.JPG").exists()
        assemble_module._install(_staged(tmp_path), out)
        assert sorted(p.name for p in out.iterdir()) == ["notes.chart", "report.json", "song.ini", "song.ogg"]
    # a background the build wrote, then replaced by the person under the same name: theirs (its size is not the
    # recorded one), so the folder is refused and the picture stays; the recorded size: the build's, as above
    out = _earlier_build(tmp_path / "Replaced", background="background.jpg", size=len(b"ours"))
    (out / "Background.JPG").write_bytes(mine)
    with pytest.raises(InputError, match=r"holds what a build does not write \(Background.JPG\)"):
        assemble_module.check_output(out)
    (out / "Background.JPG").write_bytes(b"ours")
    assemble_module.check_output(out)
    assemble_module._install(_staged(tmp_path), out)
    assert sorted(p.name for p in out.iterdir()) == ["notes.chart", "report.json", "song.ini", "song.ogg"]
    # an earlier failed build: its own background goes with it, a person's stays and so does the folder
    failed = _earlier_build(tmp_path / "Failed.failed", background="background.png")
    (failed / "background.png").write_bytes(b"ours")
    assemble_module._remove_build(failed)
    assert not failed.exists()
    failed = _earlier_build(failed)
    (failed / "background.png").write_bytes(mine)
    assemble_module._remove_build(failed)
    assert [p.name for p in failed.iterdir()] == ["background.png"]


def test_cli_help_and_errors(tmp_path, capsys):
    with pytest.raises(SystemExit) as e:
        main(["--help"])
    assert e.value.code == 0 and "assemble" in capsys.readouterr().out
    assert main([]) == 2
    (tmp_path / "bad.json").write_text(json.dumps({**CONFIG, "parts": []}))
    assert main(["assemble", str(tmp_path / "bad.json")]) == 2
    assert "no parts" in capsys.readouterr().err


VERSE_CHORD = round((beat(32) + LATE) * 480)  # the tool chart's tick of the sustained chord (lanes 0 and 1) on the
                                              # first verse section's downbeat


def _runs(root):
    """Three runs of the tool's guitar, each in its own folder: "lossy" lost every other onset in the first verse
    section and plays the chord on its downbeat on lanes 1 and 2; run2 and run3 are whole but for one onset each
    outside that section. Returns every Expert tick and the ones lossy lost."""
    text = (root / "tool" / "notes.chart").read_text(encoding="utf-8")
    head, rest = text.split("[ExpertSingle]", 1)
    body, tail = rest.split("}", 1)
    lines = body.splitlines()
    ticks = sorted({int(line.split("=")[0]) for line in lines if " = N " in line})
    gone = set(t for t in ticks if 17.0 * 480 <= t < 35.0 * 480)  # 60 BPM at 480: tick = seconds x 480
    gone = set(sorted(gone)[1::2])
    later = [t for t in ticks if t >= 40.0 * 480]
    lanes = {f"  {VERSE_CHORD} = N 0 ": f"  {VERSE_CHORD} = N 2 "}
    for name, drop, change in (("lossy", gone, lanes), ("run2", {later[3]}, {}), ("run3", {later[40]}, {})):
        kept = [next((line.replace(a, b) for a, b in change.items() if line.startswith(a)), line) for line in lines
                if " = " not in line or int(line.split("=")[0]) not in drop]
        (root / name).mkdir(exist_ok=True)
        (root / name / "notes.chart").write_text(head + "[ExpertSingle]" + "\n".join(kept) + "\n}" + tail,
                                                 encoding="utf-8", newline="")
    return ticks, gone


def _build_takes(root, output, time_shift=0.0):
    cfg = {**CONFIG, "parts": [{"instrument": "guitar", "source": "lossy/notes.chart", "time_shift": time_shift,
                                "takes": ["run2/notes.chart", "run3"]}] + CONFIG["parts"][1:], "output": output}
    result = assemble(parse_config(cfg, root))
    assert result.ok, [i for i in result.issues if i.error]
    info = result.report["parts"]["guitar"]["takes"]
    changed = [w for w in info["windows"] if w["pick"] != 0]
    assert len(changed) == 1 and abs(changed[0]["start"] - (16.5 - 0.05)) < 0.01, info["windows"]  # input seconds
    assert info["picked"] == [len(info["windows"]) - 1, 1, 0]
    expert = next(t for t in result.chart.tracks if t.instrument == "Single" and t.difficulty == "Expert")
    chord = [n for n in expert.notes if n.tick == result.chart.sections[1][0]]  # the verse's downbeat
    assert len(chord) == 1 and chord[0].frets == (0, 1) and chord[0].length > 0  # run2's, with its sustain
    return result, info, expert


def test_takes_splice_the_expert_part(built):
    """Three takes of the tool's guitar: the source lost every other onset in the first verse section; the other
    two are whole there. The verse comes from a take, the rest from the source, so Expert is the whole tool chart."""
    root, _, _ = built
    ticks, gone = _runs(root)
    result, info, expert = _build_takes(root, "out/takes")
    assert info["sources"][0].endswith("notes.chart") and len(info["sources"]) == 3
    assert info["onsets"] == {"source": len(ticks) - len(gone), "spliced": len(ticks)}
    assert len({n.tick for n in expert.notes}) == len(ticks)


def test_takes_are_cut_on_their_own_clock(built):
    """Takes running 55 ms early (a trusted offset): the windows move with them, so the chord just ahead of the
    verse's downbeat still comes from the verse's take, with its sustain."""
    root, built_result, _ = built
    _runs(root)
    early = -0.055 - built_result.report["parts"]["guitar"]["offset"]["applied"]  # the tool runs late on its own
    result, _, _ = _build_takes(root, "out/takes-early", time_shift=early)
    offset = result.report["parts"]["guitar"]["offset"]
    assert offset["trusted"] and abs(offset["applied"] + 0.055) < 0.002


def test_takes_must_be_other_runs(built):
    """A take with the same Expert notes as another run (the source given as a folder, a copy) always agrees with
    it and would outvote the rest: refused before any audio work."""
    root, _, _ = built
    _runs(root)
    (root / "copy").mkdir(exist_ok=True)
    shutil.copy(root / "run2" / "notes.chart", root / "copy" / "notes.chart")
    for takes, same in ((["lossy", "run2"], "lossy"), (["run2/notes.chart", "copy/notes.chart"], "run2")):
        cfg = {**CONFIG, "parts": [{"instrument": "guitar", "source": "lossy/notes.chart", "takes": takes}],
               "output": "out/x"}
        with pytest.raises(ValueError, match=f"{same}.* have the same Expert notes"):
            assemble(parse_config(cfg, root))
    assert not (root / "out" / "x").exists()


def test_expert_only_and_solos_on_named_sections(built):
    """levels ["expert"] writes Expert alone for every instrument; solos named by a person go exactly there (no
    "Solo" label needed), a name no section has is warned about, and the folder passes the gate."""
    root, first, _ = built
    names = [n for _, _, n in first.report["sections"]["list"]]
    pick = names[2]  # a mid-song section full of guitar notes
    cfg = {**CONFIG, "levels": ["expert"], "solos": [pick, "Nowhere"], "output": "out/expert_only"}
    (root / "expert_only.json").write_text(json.dumps(cfg), encoding="utf-8")
    result = assemble(root / "expert_only.json")
    assert result.ok, [i for i in result.issues if i.error]
    assert {t.difficulty for t in result.chart.tracks} == {"Expert"}
    assert {t.instrument for t in result.chart.tracks} == {"Single", "DoubleBass", "Drums"}
    text = (result.folder / "notes.chart").read_text(encoding="utf-8")
    assert "[ExpertSingle]" in text and "[HardSingle]" not in text and "[EasyDrums]" not in text
    lead = next(t for t in result.chart.tracks if t.instrument == "Single")
    secs = sorted(result.chart.sections)
    i = next(k for k, (_, n) in enumerate(secs) if n == pick)
    a, b = secs[i][0], secs[i + 1][0]
    assert len(lead.solos) == 1 and a <= lead.solos[0][0] and lead.solos[0][1] < b
    # report.json: the rules used (not capped: a person's names), and each solo's measures and onsets
    pad = result.report["lead_in"]["pad_seconds"]
    phrases = result.report["phrases"]["guitar"]
    assert phrases["solo_rules"] == {**asdict(SOLO_RULES), "capped": False}
    (row,) = phrases["solo_details"]
    assert [row["start"], row["end"]] == list(phrases["solos"][0]) == [
        round(result.chart.tempo.tick_to_sec(t) - pad, 3) for t in lead.solos[0]]
    assert row["onsets"] == len({n.tick for n in lead.notes if a <= n.tick < b}) and row["measures"] >= 4
    assert phrases["solos_skipped_by_share"] == phrases["solos_skipped_by_gap"] == []
    assert phrases["solos_trimmed_by_share"] == []
    assert any("no section is named 'Nowhere'" in w for w in result.report["warnings"])
    assert result.report["tracks"]["guitar"].keys() == {"expert"}



def test_the_solo_report_without_names(built):
    """With the "Solo" label, a run over the share budget: report.json's solo rows (kept, trimmed, skipped) are in song
    seconds, as the solos are."""
    root, first, _ = built
    segments = [[0.0, 0.5, "start"], [0.5, 16.5, "intro"], [16.5, 52.5, "solo"], [52.5, 64.5, "chorus"],
                [64.5, 80.5, "solo"], [80.5, DURATION, "end"]]
    (root / "solo_sections.json").write_text(json.dumps({"segments": segments}), encoding="utf-8")
    cfg = {**CONFIG, "sections": "solo_sections.json", "solos": "labels", "levels": ["expert"],
           "output": "out/solo_rules"}
    (root / "solo_rules.json").write_text(json.dumps(cfg), encoding="utf-8")
    result = assemble(root / "solo_rules.json")
    assert result.ok, [i for i in result.issues if i.error]
    every = json.loads((result.folder / "report.json").read_text(encoding="utf-8"))["phrases"]
    phrases = every["guitar"]
    assert phrases["solo_rules"] == {**asdict(SOLO_RULES), "capped": True}
    # each part's star-power count (M6-01): the rules, its span's beats counted at most at 160 BPM, the target
    assert every.keys() == {"guitar", "bass", "drums"}
    for part in every.values():
        count = part["star_power_count"]
        assert count["rules"] == asdict(SP_RULES) and count["placed"] == len(part["star_power"]) > 0
        assert count["counted_beats"] == pytest.approx(
            min(count["span_beats"], count["span_seconds"] * SP_RULES.max_bpm / 60), abs=0.01)
        assert count["target"] == round(count["counted_beats"] / SP_RULES.beats_per_phrase) >= count["placed"]
    # the two runs, 16.5-52.5 s and 64.5-80.5 s, are 52 s of a 75.8-s span (0.40 of it: 30.3 s): the denser first
    # run is cut to its densest window within the budget, and the second, with no room left, is skipped
    (trimmed,), (skipped,) = phrases["solos_trimmed_by_share"], phrases["solos_skipped_by_share"]
    assert 16.0 < trimmed["start"] < trimmed["end"] < 52.5 and trimmed["measures"] == 18
    assert 64.0 < skipped["start"] < skipped["end"] < 80.5 and skipped["measures"] == 8
    (row,) = phrases["solo_details"]
    assert [row["start"], row["end"]] == phrases["solos"][0] and row["measures"] < 18
    assert trimmed["start"] <= row["start"] < row["end"] <= trimmed["end"] and row["end"] - row["start"] <= 30.3
    assert phrases["solos_skipped_by_gap"] == []


# ------------------------------------------------------------------------------------------------ the end of the audio

def test_last_tick_by_the_limit():
    tm = TempoMap(192, [Tempo(0, 120000), Tempo(700, 97531), Tempo(1500, 181000)])
    for limit in (0.0, 0.0004, 0.5, 1.82, 3.3333, 4.96, 7.0, 12.345):
        k = last_tick_by(tm, limit)
        assert tm.tick_to_sec(k) <= limit < tm.tick_to_sec(k + 1), limit


def test_clip_to_audio_counts_what_it_cuts():
    """Song.ogg ends at 10 s on a 120 BPM map at 192 (384 ticks a second): with the 1 ms margin the last tick kept
    is 3839 (9.9974 s). A note on 3840 (inside the margin) or later goes; a sustain past 3839 ends there, or is
    removed when that leaves it under its level's shortest sustain (a beat is 192 ticks: Expert 0.75 beat, Medium 1,
    Easy 2)."""
    tm = TempoMap(192, [Tempo(0, 120000)])
    assert last_tick_by(tm, 10.0 - CLIP_MARGIN_S) == 3839
    expert = Track("Expert", "Single", [FretNote(3072, (0,), 1536), FretNote(3700, (1, 2), 0),
                                        FretNote(3800, (1,), 200), FretNote(3840, (2,)), FretNote(4000, (3,), 192)])
    easy = Track("Easy", "Single", [FretNote(3456, (0,), 768)])
    medium = Track("Medium", "Single", [FretNote(3456, (0,), 768)])
    inside = Track("Hard", "Single", [FretNote(384, (0,), 3455)])  # ends on 3839 exactly
    tracks = {"expert": expert, "hard": inside, "medium": medium, "easy": easy}
    out, counts = clip_to_audio(tracks, tm, 10.0)
    assert [(n.tick, n.length) for n in out["expert"].notes] == [(3072, 767), (3700, 0), (3800, 0)]
    assert counts["expert"] == {"onsets_dropped": 2, "sustains_clipped": 1, "sustains_removed": 1}
    assert out["hard"] is inside and counts["hard"] == {"onsets_dropped": 0, "sustains_clipped": 0,
                                                         "sustains_removed": 0}
    assert out["medium"].notes == [FretNote(3456, (0,), 383)]   # 383 ticks: just under 2 beats, over Medium's 1
    assert out["easy"].notes == [FretNote(3456, (0,), 0)] and counts["easy"]["sustains_removed"] == 1  # under 2
    drums = Track("Expert", "Drums", [DrumHit(3839, 0), DrumHit(3840, 1), DrumHit(3840, 2, cymbal=True)])
    out, counts = clip_to_audio({"expert": drums}, tm, 10.0)
    assert out["expert"].notes == [DrumHit(3839, 0)] and counts["expert"]["onsets_dropped"] == 1  # one onset


def _clip_config(root):
    """The guitar tool's chart with notes at and past the end of the 84-s audio: Expert sustains from 81.5 s to
    89 s, and Expert and Hard play at 84.5 s; Hard also has a 83.75-s note sustained to 86 s, which ends 0.25 s
    after it at the end of the audio, under Hard's shortest sustain (0.75 beat, 0.375 s)."""
    tm = TempoMap(480, [Tempo(0, 60000)])
    tick = lambda t: round(tm.sec_to_tick(t + LATE))  # noqa: E731
    expert, hard = write_tool_chart(root / "tool" / "notes.chart")
    a = FretNote(tick(81.5), (2,), tick(89.0) - tick(81.5))
    expert += [a, FretNote(tick(84.5), (1,))]
    hard += [a, FretNote(tick(83.75), (1,), tick(86.0) - tick(83.75)), FretNote(tick(84.5), (0,))]
    chart = Chart(SongInfo("tool", "tool"), tm, [], [Track("Expert", "Single", expert), Track("Hard", "Single", hard)])
    (root / "clip").mkdir(exist_ok=True)
    (root / "clip" / "notes.chart").write_text(write_chart(chart), encoding="utf-8", newline="")
    parts = [{**CONFIG["parts"][0], "source": "clip/notes.chart"}] + CONFIG["parts"][1:]
    return {**CONFIG, "parts": parts, "output": "out/clip"}


def test_notes_past_the_end_of_the_audio_are_clipped(built, monkeypatch):
    """A source that runs past the audio (an excerpt cut mid-note): the build clips every taken level and passes
    the gate, scan-chart's included, with every written track ending CLIP_MARGIN_S or more before song.ogg; the
    counts are in report.json. Without the clip the gate fails it (noteAfterAudio, on every guitar level)."""
    root, _, _ = built
    cfg = _clip_config(root)
    result = assemble(parse_config(cfg, root))
    assert result.ok, [i for i in result.issues if i.error]
    clipped = result.report["parts"]["guitar"]["clipped"]
    assert clipped["audio_end"] == DURATION and clipped["margin_s"] == CLIP_MARGIN_S
    assert clipped["levels"] == {"expert": {"onsets_dropped": 1, "sustains_clipped": 1, "sustains_removed": 0},
                                 "hard": {"onsets_dropped": 1, "sustains_clipped": 0, "sustains_removed": 1}}
    assert all(not any(c.values()) for k in ("bass", "drums") for c in result.report["parts"][k]["clipped"]["levels"]
               .values())
    song_end = DURATION + result.lead.pad_seconds
    song = read_chart(result.folder / "notes.chart")
    assert {d for i, d in song.parts if i == "guitar"} == {"expert", "hard", "medium", "easy"}
    for key, part in song.parts.items():
        last = max([n.time for n in part.notes] + [n.end for n in part.notes if getattr(n, "end", None)])
        assert last <= song_end - CLIP_MARGIN_S + 1e-9, key
    lead = next(t for t in result.chart.tracks if t.instrument == "Single" and t.difficulty == "Expert")
    assert max(n.tick + n.length for n in lead.notes) == last_tick_by(result.chart.tempo, song_end - CLIP_MARGIN_S)
    if find_scan_chart()[0] is not None:
        assert result.report["gate"]["scan_chart"]["ran"]
    # and the command line's summary says so, on the part's line
    from songcharter.cli import _summary
    line = next(x for x in _summary(result).splitlines() if x.startswith("part guitar: "))
    assert line.endswith("; at the end of the audio 1 Expert onsets dropped, 1 sustains clipped, 0 removed"), line
    assert not any("at the end of the audio" in x for x in _summary(result).splitlines() if x.startswith("part bass"))
    monkeypatch.setattr(assemble_module, "clip_to_audio", lambda tracks, tempo, end: (tracks, {}))
    unclipped = assemble(parse_config({**cfg, "output": "out/unclipped"}, root))
    assert not unclipped.ok
    assert {(i.difficulty, i.kind) for i in unclipped.issues if i.error and i.instrument == "guitar"} == {
        (d, "noteAfterAudio") for d in ("expert", "hard", "medium", "easy")}


# ------------------------------------------------------------------------------------------------ the grid's octave

def snare_features(beats, on, fps=200.0, duration=None, mid_level=1.0):
    """OnsetFeatures with a clear drum peak at every beat (so every beat has confident evidence) and the snare band's
    power at `on`: "lines" (the beats), "mids" (their midpoints) or "both"; beats as a grid gives them (the band
    powers sit at the onset times, ONSET_TO_BEAT_MS after the beats)."""
    beats = np.asarray(beats)
    n = int(((duration or beats[-1] + 1.0)) * fps)
    env, snare = np.zeros(n), np.full(n, 0.01)
    u = beats - ONSET_TO_BEAT_MS / 1000
    env[np.round(u * fps).astype(int)] = 1.0
    if on in ("lines", "both"):
        snare[np.round(u * fps).astype(int)] = 1.0
    if on in ("mids", "both"):
        snare[np.round(0.5 * (u[:-1] + u[1:]) * fps).astype(int)] = mid_level
    return OnsetFeatures(fps, env, np.zeros(n), np.zeros(n), snare)


FAST_BEAT = 60 / 198
SLOW_GRID = 1.0 + np.arange(150) * 2 * FAST_BEAT  # a 99 BPM grid under a 198 BPM song: 90 s


def sixteenths(step=0.25, n=600, start=1.0):
    """Onsets every `step` of the 198 BPM beat (0.25: its 16ths, 76 ms apart; 0.5: its 8ths)."""
    return start + np.arange(n) * step * FAST_BEAT


def test_short_intervals_counts_against_the_local_beat():
    beats = np.array([0.0, 1.0, 2.0, 2.5, 3.0])  # a 1/16 is 0.25 s, then 0.125 s in the last two beats
    onsets = [0.0, 0.1, 0.5, 2.0, 2.05, 2.1, 2.2, 3.5]  # 0.1 < 0.1875; 0.4 no; 1.5 no; 0.05, 0.05 < 0.09375; 0.1 no
    assert short_intervals(onsets, beats) == (3, 7)
    assert short_intervals([0.5, 0.5, 0.6], beats) == (1, 1)  # distinct onsets only
    assert short_intervals([1.0], beats) == (0, 0) and OCTAVE_SHORT == 0.75
    # an interval is judged by the beat its earlier onset falls in: 0.15 s is short in the 1 s beat (0.1875), not
    # in the 0.5 s beat its later onset falls in (0.094)
    assert short_intervals([1.9, 2.05], beats) == (1, 1)


def test_grid_octave_doubles_a_grid_too_slow_for_the_notes():
    """16ths of a 198 BPM song on a 99 BPM grid: every interval is a 1/32 of the grid, so it doubles; the stats give
    every part's share, the pooled share, the backbeat and the thresholds. 8ths of the song (16ths of the grid)
    keep it."""
    snare = snare_features(SLOW_GRID, "mids")
    octave, stats = grid_octave({"guitar": sixteenths(), "bass": sixteenths(0.5, 300)}, SLOW_GRID, snare)
    assert octave == 2 and stats["octave"] == 2
    assert stats["parts"]["guitar"] == {"onsets": 600, "intervals": 599, "short": 599, "share": 1.0}
    assert stats["parts"]["bass"]["share"] == 0.0 and stats["onsets"] == 900
    assert stats["pooled_share"] == pytest.approx(600 / 900, abs=1e-3)  # weighted by the onset counts
    assert stats["backbeat_ratio"] > 10 and stats["backbeat_beats"] == len(SLOW_GRID) - 1
    assert stats["bpm"] == pytest.approx(99.0, abs=0.01)
    assert stats["thresholds"] == {"short": OCTAVE_SHORT, "share": OCTAVE_SHARE, "max_bpm": OCTAVE_MAX_BPM,
                                   "min_onsets": OCTAVE_MIN_ONSETS}  # the backbeat has no threshold (M5-11)
    assert stats["reason"].startswith("66.7% of intervals under 0.75 of a 16th")
    octave, stats = grid_octave({"guitar": sixteenths(0.5)}, SLOW_GRID, snare)
    assert octave == 1 and stats["pooled_share"] == 0.0 and "under 0.75 of a 16th (under" in stats["reason"]


def test_grid_octave_needs_enough_onsets_and_room_under_300_bpm():
    snare = snare_features(SLOW_GRID, "mids")
    few = sixteenths(n=OCTAVE_MIN_ONSETS - 1)
    octave, stats = grid_octave({"guitar": few}, SLOW_GRID, snare)
    assert octave == 1 and stats["reason"] == f"{OCTAVE_MIN_ONSETS - 1} onsets (under {OCTAVE_MIN_ONSETS})"
    assert grid_octave({"guitar": few, "bass": few[:1] + 0.01}, SLOW_GRID, snare)[0] == 2  # the parts count together
    fast_grid = 1.0 + np.arange(250) * 60 / 160  # 160 BPM: 320 doubled
    octave, stats = grid_octave({"guitar": 1.0 + np.arange(900) * 60 / 160 / 8}, fast_grid, snare_features(
        fast_grid, "mids"))
    assert octave == 1 and stats["reason"] == "320.0 BPM doubled is over 300"
    assert grid_octave({"guitar": 1.0 + np.arange(900) * 60 / 160 / 8}, fast_grid, None,
                       OctaveRules(max_bpm=320.0))[0] == 2


def test_the_backbeat_is_recorded_not_a_veto():
    """M5-11: the density decides; the backbeat ratio is recorded in the stats and a doubling's reason. A 200 BPM
    song charted at 100 BPM had its snare on the first grid's lines (backbeat 0.19, under M5-01's veto of 0.34, the
    right grids reaching 0.172), so the snare on the lines no longer keeps a grid the notes say is too slow. On the
    midpoints, on both, or without drums (None) it doubles all the same."""
    notes = {"guitar": sixteenths()}
    for on, ratio in (("lines", 0.01), ("mids", 100.0), ("both", 1.0)):
        octave, stats = grid_octave(notes, SLOW_GRID, snare_features(SLOW_GRID, on))
        assert octave == 2 and stats["backbeat_ratio"] == pytest.approx(ratio), on
        assert stats["backbeat_beats"] == len(SLOW_GRID) - 1
        assert stats["reason"] == f"100.0% of intervals under 0.75 of a 16th (at least 35.0%), backbeat {ratio:.2f}"
    octave, stats = grid_octave(notes, SLOW_GRID, None)
    assert octave == 2 and stats["backbeat_ratio"] is None and stats["reason"].endswith(", no drums")
    few = snare_features(SLOW_GRID[:10], "lines", duration=SLOW_GRID[-1] + 1)  # drums in the first 10 beats only
    octave, stats = grid_octave(notes, SLOW_GRID, few)
    assert octave == 2 and stats["backbeat_ratio"] is None and stats["backbeat_beats"] == 10
    assert stats["reason"].endswith(", too few confident beats")
    ratio, used = backbeat_ratio(snare_features(SLOW_GRID, "both"), SLOW_GRID)
    assert ratio == pytest.approx(1.0) and used == len(SLOW_GRID) - 1


def test_a_song_at_half_tempo_with_its_snare_on_the_lines_doubles():
    """The fourth stress song's case (M5-11): its guitar in 16ths of the song, its bass in 8ths, pooled 0.526 on the
    100 BPM grid (0.527 measured), and the snare mostly on the first grid's lines (backbeat 0.19). M5-01's veto kept
    it at 100 BPM; now it doubles, with the ratio recorded."""
    notes = {"guitar": sixteenths(), "bass": sixteenths(0.5, 540)}
    pm2 = snare_features(SLOW_GRID, "both", mid_level=0.19)
    octave, stats = grid_octave(notes, SLOW_GRID, pm2)
    assert octave == 2 and stats["pooled_share"] == pytest.approx(600 / 1140, abs=1e-4)
    assert stats["backbeat_ratio"] == pytest.approx(0.19) and stats["backbeat_beats"] == len(SLOW_GRID) - 1
    assert stats["reason"] == "52.6% of intervals under 0.75 of a 16th (at least 35.0%), backbeat 0.19"


def test_a_dense_song_on_its_right_grid_stays():
    """A 140 BPM song on its own grid, in 16ths, with a bass engine's close double onsets (40 ms apart) on its 8ths:
    the right grids' shares come mostly from those (DESIGN.md 2.3), here pooled 0.25, under 0.35, so the grid
    stays, whatever the snare says (on the midpoints, as at half tempo, too). The threshold: a share of 0.34 stays,
    0.35 and 0.36 double."""
    grid = 1.0 + np.arange(200) * 60 / 140
    sixteenth = 60 / 140 / 4
    guitar = 1.0 + np.arange(700) * sixteenth
    bass = np.sort(np.concatenate([1.0 + np.arange(350) * 2 * sixteenth, 1.04 + np.arange(350) * 2 * sixteenth]))
    for on in ("lines", "mids"):
        octave, stats = grid_octave({"guitar": guitar, "bass": bass}, grid, snare_features(grid, on))
        assert octave == 1 and stats["parts"]["guitar"]["share"] == 0.0, on
        assert stats["parts"]["bass"]["short"] == 350 and stats["pooled_share"] == pytest.approx(0.25, abs=1e-3)
        assert stats["reason"] == "25.0% of intervals under 0.75 of a 16th (under 35.0%)"
        assert stats["backbeat_ratio"] == pytest.approx(0.01 if on == "lines" else 100.0)  # recorded all the same

    def shares(k, n=500):  # k of n intervals short (the song's 16ths on SLOW_GRID), the others its 8ths
        return 1.0 + np.concatenate([[0.0], np.cumsum([0.25 * FAST_BEAT] * k + [0.5 * FAST_BEAT] * (n - k))])

    snare = snare_features(SLOW_GRID, "mids")
    under, stats = grid_octave({"guitar": shares(170)}, SLOW_GRID, snare)
    assert under == 1 and stats["pooled_share"] == pytest.approx(0.34)
    over, stats = grid_octave({"guitar": shares(180)}, SLOW_GRID, snare)
    assert over == 2 and stats["pooled_share"] == pytest.approx(0.36)
    at, stats = grid_octave({"guitar": shares(175)}, SLOW_GRID, snare)   # "at least": exactly 0.35 doubles
    assert at == 2 and stats["pooled_share"] == pytest.approx(0.35)


def test_the_backbeat_ratio_counts_confident_beats_only():
    """Only the beats with confident drum evidence count: the second half (no envelope peak) has the snare between
    the beats, which would make the ratio about 1."""
    half = len(SLOW_GRID) // 2
    mixed = snare_features(SLOW_GRID, "lines")
    late = SLOW_GRID[half:] - ONSET_TO_BEAT_MS / 1000
    mixed.env[np.round(late * mixed.fps).astype(int)] = 0.0
    mixed.snare[np.round(late * mixed.fps).astype(int)] = 0.01
    mixed.snare[np.round((late[:-1] + 0.5 * np.diff(late)) * mixed.fps).astype(int)] = 1.0
    ratio, used = backbeat_ratio(mixed, SLOW_GRID)
    assert ratio < 0.05 and used == half
    # too few confident beats: indeterminate
    assert backbeat_ratio(snare_features(SLOW_GRID[:10], "lines"), SLOW_GRID[:10]) == (None, 9)


FAST_FIRST, FAST_SECONDS = 0.5, 40.0
FAST_NOTES = int((FAST_SECONDS - 2.0) / (FAST_BEAT / 4))  # 16ths of the 198 BPM beat to 38.5 s: 500


def fast_drums(seed=0, beats=None, seconds=FAST_SECONDS) -> np.ndarray:
    """198 BPM from FAST_FIRST: a kick and a crash on every other beat, a snare on the beats between (the backbeat
    at the pulse). The first pass folds the tempo into [85, 185): 99 BPM, its lines on the kicks. `beats` (and the
    song's `seconds`) put the same hits on other beats."""
    rng = np.random.default_rng(seed)
    y = np.zeros(int(seconds * SR))
    t = np.arange(int(0.25 * SR)) / SR
    kick = np.sin(2 * np.pi * 55 * t) * np.exp(-t / 0.08)
    crash = np.diff(np.diff(rng.standard_normal(len(t) + 2))) * np.exp(-t / 0.05)
    snare = 0.5 * (0.5 * np.sin(2 * np.pi * 190 * t) + 0.6 * rng.standard_normal(len(t))) * np.exp(-t / 0.06)
    if beats is None:
        beats = FAST_FIRST + np.arange(int((FAST_SECONDS - 1.0) / FAST_BEAT)) * FAST_BEAT
    for k, b in enumerate(beats):
        i = int(round(b * SR))
        y[i:i + len(t)] += (kick + crash) if k % 2 == 0 else snare
    y += rng.standard_normal(len(y)) * 1e-3
    y = (0.4 * y).astype(np.float32)
    return np.stack([y, y])


@pytest.fixture(scope="module")
def fast_song(tmp_path_factory):
    """A 198 BPM song: the drums above, and a guitar tool chart of straight 16ths (76 ms apart) on its own 198 BPM
    map, four frets round."""
    root = tmp_path_factory.mktemp("fast")
    drums = fast_drums()
    times = FAST_FIRST + np.arange(FAST_NOTES) * FAST_BEAT / 4
    tone = np.zeros(drums.shape[1], dtype=np.float32)
    for t in times:
        i = int(t * SR)
        tone[i:i + 2000] += (0.05 * np.sin(2 * np.pi * 330 * np.arange(2000) / SR)).astype(np.float32)
    A.write_wav(drums + tone, root / "mix.wav")
    A.write_wav(drums, root / "drums.wav")
    tm = TempoMap(480, [Tempo(0, 198000)])
    notes = [FretNote(round(tm.sec_to_tick(t)), ((0, 1, 2, 1)[q % 4],)) for q, t in enumerate(times)]
    (root / "tool").mkdir()
    (root / "tool" / "notes.chart").write_text(write_chart(Chart(SongInfo("tool", "tool"), tm, [], [
        Track("Expert", "Single", notes)])), encoding="utf-8", newline="")
    # a bass at the song's 8ths, 45 ms late: past half the doubled grid's 1/16 (38 ms), and no beat line aligned,
    # so no run reads as triplets
    bass = [FretNote(round(tm.sec_to_tick(FAST_FIRST + q * FAST_BEAT / 2 + 0.045)), (q % 3,))
            for q in range(FAST_NOTES // 2)]
    (root / "tool" / "bass.chart").write_text(write_chart(Chart(SongInfo("tool", "tool"), tm, [], [
        Track("Expert", "DoubleBass", bass)])), encoding="utf-8", newline="")
    segments = [[0.0, 0.5, "start"], [0.5, 20.0, "verse"], [20.0, FAST_SECONDS, "chorus"]]
    (root / "allin1.json").write_text(json.dumps({"segments": segments}), encoding="utf-8")
    config = {"audio": "mix.wav", "stems": {"drums": "drums.wav"}, "lead_in": 2.5, "sections": "allin1.json",
              "parts": [{"instrument": "guitar", "source": "tool/notes.chart"}], "levels": ["expert"],
              "metadata": {**CONFIG["metadata"], "name": "Fast Song"}, "output": "out/fast"}
    return root, config


def test_a_grid_too_slow_for_its_notes_is_doubled(fast_song, monkeypatch):
    """The first pass gives 99 BPM; the notes are 1/32s of it, so the second pass builds the grid at twice its click
    tempo with the fold range doubled and no first-beat hint, on the same features, computed once. The doubled
    grid's evidence holds up, so it stays: every 16th keeps its own tick, the tempo map is at 198 BPM, and the
    build says so once."""
    root, config = fast_song
    real_features, real_grid = assemble_module.onset_features, assemble_module.beat_grid
    seen: dict = {"features": [], "grids": []}

    def features(*args, **kwargs):
        seen["features"].append(real_features(*args, **kwargs))
        return seen["features"][-1]

    def grid(*args, **kwargs):
        seen["grids"].append(kwargs)
        return real_grid(*args, **kwargs)

    monkeypatch.setattr(assemble_module, "onset_features", features)
    monkeypatch.setattr(assemble_module, "beat_grid", grid)
    result = assemble(parse_config(config, root))
    assert result.ok, [i for i in result.issues if i.error]
    g = result.report["grid"]
    assert g["octave"] == 2 and g["bpm_median"] == pytest.approx(198.0, abs=0.2)
    stats = g["octave_stats"]
    assert stats["first"]["bpm_median"] == pytest.approx(99.0, abs=0.1)
    assert stats["second"]["bpm_median"] == g["bpm_median"] and stats["evidence_ratio"] >= 0.9
    assert stats["parts"]["guitar"]["share"] == 1.0 and stats["backbeat_ratio"] > 2
    assert stats["thresholds"]["evidence_min"] == assemble_module.OCTAVE_EVIDENCE_MIN
    assert g["octave_reason"].startswith("100.0% of intervals under 0.75 of a 16th")
    doubled = [w for w in result.report["warnings"] if w.startswith("tempo doubled")]
    assert doubled == [f"tempo doubled to {g['bpm_median']:.1f} BPM: the notes are too dense for "
                       f"{stats['first']['bpm_median']:.1f} BPM (100% of intervals under a 16th)"]
    assert np.median([t.bpm for t in result.chart.tempo.tempos]) == pytest.approx(198.0, abs=1.0)
    # the features once, to both passes; the second at twice the first's click tempo, the range doubled
    assert len(seen["features"]) == 1 and len(seen["grids"]) == 2
    assert all(k["features"] is seen["features"][0] for k in seen["grids"])
    first, second = seen["grids"]
    assert second["bpm"] == pytest.approx(2 * stats["first"]["click_bpm"]) and second["bpm_range"] == (170.0, 370.0)
    assert second.get("first_beat") is None and second["mode"] == first["mode"] is None
    assert second["half_beat"] is True and not first.get("half_beat")  # the half-beat test, on the second pass only
    assert second["keep_line"] is True and not first.get("keep_line")  # and its hinted line stays
    assert stats["second"]["half_beat"]["shifted"] is False  # the kicks are on its lines already
    q = result.report["parts"]["guitar"]["quantize"]["expert"]
    assert q["notes_out"] == FAST_NOTES and q["merged"] == q["dropped_distinct"] == q["dropped"] == 0


def test_grid_octave_forces_the_first_grid_and_the_guard_keeps_it(fast_song, monkeypatch):
    """grid_octave 1 keeps the first grid (the notes then crowd its 1/16 slots: what the second pass is for). With
    a guard the doubled grid's evidence cannot meet, auto keeps the first grid too and warns to check the tempo."""
    root, config = fast_song
    one = assemble(parse_config({**config, "grid_octave": 1, "output": "out/one"}, root)).report
    assert one["grid"]["octave"] == 1 and one["grid"]["octave_reason"] == "forced: grid_octave 1"
    assert one["grid"]["bpm_median"] == pytest.approx(99.0, abs=0.1) and "second" not in one["grid"]["octave_stats"]
    assert not any(w.startswith("tempo") for w in one["warnings"])
    assert one["parts"]["guitar"]["quantize"]["expert"]["notes_out"] < FAST_NOTES * 0.6
    monkeypatch.setattr(assemble_module, "OCTAVE_RULES", replace(assemble_module.OCTAVE_RULES, evidence_min=2.0))
    kept = assemble(parse_config({**config, "output": "out/guard"}, root)).report
    g = kept["grid"]
    assert g["octave"] == 1 and g["bpm_median"] == pytest.approx(99.0, abs=0.1)
    assert g["octave_stats"]["second"]["bpm_median"] == pytest.approx(198.0, abs=0.2)
    assert g["octave_stats"]["thresholds"]["evidence_min"] == 2.0 and "under 2.0): the first grid stays" in \
        g["octave_reason"]
    first = g["octave_stats"]["first"]["bpm_median"]
    assert [w for w in kept["warnings"] if w.startswith("tempo")] == [
        f"tempo: the notes are dense for {first:.1f} BPM (100% of intervals under a 16th) but the drums give no "
        f"evidence at {2 * first:.1f} BPM: check the tempo"]


def test_grid_octave_2_past_300_bpm_is_bad_input(built, monkeypatch):
    """Forcing the doubled grid where it would pass the ceiling is an InputError (exit 2), before any folder is
    written; here the ceiling is lowered under the 120 BPM song's 240."""
    root, _, _ = built
    monkeypatch.setattr(assemble_module, "OCTAVE_RULES", replace(assemble_module.OCTAVE_RULES, max_bpm=200.0))
    with pytest.raises(InputError, match=r"grid_octave 2: the doubled tempo, 240.0 BPM, passes 200 BPM"):
        assemble(parse_config({**CONFIG, "grid_octave": 2, "output": "out/past"}, root))
    assert not (root / "out" / "past").exists()


def test_on_a_doubled_grid_the_bass_snaps_to_8ths(fast_song):
    """On a doubled grid the bass gets the grid's 8ths (the first grid's 16ths) and no triplet slots, so its late
    8ths (its offset fixed at 0 here) stay on 8th lines instead of the 1/16 after them; the guitar keeps 1/16s.
    Undoubled, nothing changes."""
    root, config = fast_song
    parts = config["parts"] + [{"instrument": "bass", "source": "tool/bass.chart", "offset": 0.0}]
    result = assemble(parse_config({**config, "parts": parts, "output": "out/bass"}, root))
    assert result.ok and result.report["grid"]["octave"] == 2
    assert result.report["parts"]["bass"]["slots"] == {"straight": 2, "triplet": 0}
    assert result.report["parts"]["guitar"]["slots"] == {"straight": 4, "triplet": 3}
    res = result.chart.tempo.resolution
    bass = next(t for t in result.chart.tracks if t.name == "ExpertDoubleBass")
    assert len(bass.notes) == FAST_NOTES // 2 and all(n.tick % (res // 2) == 0 for n in bass.notes)
    one = assemble(parse_config({**config, "parts": parts, "grid_octave": 1, "output": "out/bass1"}, root))
    assert one.report["parts"]["bass"]["slots"] == {"straight": 4, "triplet": 3}


def scattered_bass(tm: TempoMap, seed: int = 0) -> list[TimedNote]:
    """A made-up bass engine's straight 8ths on a 200 BPM map (a doubled grid's tempo): each beat line within 5 ms,
    each off-beat 8th 40-50 ms early or late, so it lies within 10 ms of a third of the beat (a triplet slot, 100 ms
    apart) and 40-50 ms from its 8th: the spread that put pm2's bass on triplet slots (DESIGN.md 2.6)."""
    rng = np.random.default_rng(seed)
    notes = []
    for b in range(8, 40):
        notes.append(TimedNote(tm.tick_to_sec(b * tm.resolution) + rng.uniform(-0.005, 0.005), (b % 3,)))
        late = (-1) ** (b // 2) * rng.uniform(0.040, 0.050)  # two beats early, two late, ...
        notes.append(TimedNote(tm.tick_to_sec((b + 0.5) * tm.resolution) + late, ((b + 1) % 3,)))
    return notes


def test_on_a_doubled_grid_the_bass_has_no_triplet_slots():
    """The bass on a doubled grid snaps to the grid's 8ths only (DOUBLED_BASS_SLOTS (2, 0)): an engine's 8ths spread
    40-50 ms off land on their 8ths, where the doubled grid's triplets (the first grid's 16th-note triplets) took them
    a third of a beat off. On an octave-1 grid, and for every other part, the quantizer's own rules: the same onsets
    go triplet there."""
    tm = TempoMap.from_beats(np.arange(48) * 0.3)  # 200 BPM
    res, notes = tm.resolution, scattered_bass(tm)
    want = [b * res + h for b in range(8, 40) for h in (0, res // 2)]
    bass, guitar, drums = (PartConfig(i, Path(f"{i}.chart")) for i in ("bass", "guitar", "drums"))
    for hopo, rules in HOPO_RULES.items():
        assert part_rules(replace(bass, hopo=hopo), 2) == replace(rules, straight=2, triplet=0)
        for p, octave in ((bass, 1), (guitar, 1), (drums, 1), (guitar, 2), (drums, 2)):
            assert part_rules(replace(p, hopo=hopo), octave) == rules, (p.instrument, octave, hopo)
    track, rep = quantize_part(TimedPart("bass", "expert", notes), tm, 0.0, 0.0, part_rules(bass, 2))
    assert [n.tick for n in track.notes] == want and rep.triplet_notes == 0
    for p, octave in ((bass, 1), (guitar, 2)):
        part = TimedPart(p.instrument, "expert", notes)
        track, rep = quantize_part(part, tm, 0.0, 0.0, part_rules(p, octave))
        assert rep.triplet_notes > 20 and [n.tick for n in track.notes] != want, (p.instrument, octave)


def test_on_a_doubled_grid_the_lyrics_snap_to_8ths(fast_song, monkeypatch):
    """On a doubled grid the lyrics get its 8ths and their triplets (lyric_rules: the first grid's 16ths), so made-up
    words sung 50 ms before the beats land on the beat lines, where the doubled grid's 16ths would put them a 1/16
    (76 ms) early; report.json records the slots. Undoubled, the quantizer's own slots, as before."""
    root, config = fast_song
    beats = (20, 24, 28, 32, 36, 40)
    words = L.Timed(L.parse("zorp blen quiv fim wob dak"), tuple(FAST_FIRST + b * FAST_BEAT - 0.050 for b in beats))
    result = assemble(parse_config({**config, "output": "out/lyrics"}, root), lyrics=words)
    assert result.ok and result.report["grid"]["octave"] == 2
    assert result.report["lyrics"]["slots"] == {"straight": 2, "triplet": 3}
    tm, pad = result.chart.tempo, result.lead.pad_seconds
    ticks = [t for t, _, text in sorted(result.chart.lyrics) if text.startswith("lyric ")]
    assert len(ticks) == len(beats) and all(t % tm.resolution == 0 for t in ticks)   # on the beat lines
    assert [tm.tick_to_sec(t) - pad for t in ticks] == pytest.approx([FAST_FIRST + b * FAST_BEAT for b in beats],
                                                                      abs=0.012)
    one = assemble(parse_config({**config, "grid_octave": 1, "output": "out/lyrics1"}, root), lyrics=words)
    assert one.report["grid"]["octave"] == 1 and one.report["lyrics"]["slots"] == {"straight": 4, "triplet": 3}
    # words sung in triplets (beats 20 and 21 in thirds) keep the doubled grid's triplet slots, not its 8ths
    thirds = range(60, 66)
    trip = L.Timed(L.parse("zorp blen quiv fim wob dak"), tuple(FAST_FIRST + k * FAST_BEAT / 3 for k in thirds))
    t3 = assemble(parse_config({**config, "output": "out/lyrics3"}, root), lyrics=trip)
    ticks = [t for t, _, text in sorted(t3.chart.lyrics) if text.startswith("lyric ")]
    res = t3.chart.tempo.resolution
    assert t3.report["grid"]["octave"] == 2 and len(ticks) == len(thirds)
    assert all(t % (res // 3) == 0 for t in ticks) and sum(t % (res // 2) != 0 for t in ticks) == 4
    # the doubled grid tried and rejected by the guard: the first grid stays, and so do its slots
    monkeypatch.setattr(assemble_module, "OCTAVE_RULES", replace(assemble_module.OCTAVE_RULES, evidence_min=2.0))
    kept = assemble(parse_config({**config, "output": "out/lyrics-kept"}, root), lyrics=words).report
    assert kept["grid"]["octave"] == 1 and "second" in kept["grid"]["octave_stats"]
    assert kept["lyrics"]["slots"] == {"straight": 4, "triplet": 3}


def _fake_grid(bpm, share, half_beat=None):
    beats = 1.0 + np.arange(300) * 60 / bpm
    stats = {"click": {"bpm": bpm}, "evidence": {"confident_share": share, "n_confident": int(share * 300),
                                                  "n_beats": 300}}
    if half_beat is not None:
        stats["half_beat"] = half_beat
    return BeatGrid(beats, np.arange(0, 300, 4), "free", stats)


def test_the_octave_pass_forced_2_keeps_the_doubled_grid_and_flags_an_unsure_phase(tmp_path):
    """A forced grid_octave 2 keeps the doubled grid however little evidence it has (auto falls back to the first);
    a doubled grid whose half-beat test was unsure warns."""
    first = _fake_grid(99.0, 0.8)
    onsets = {"guitar": sixteenths()}
    weak = _fake_grid(198.0, 0.4, {"ratio": 1.02, "shifted": False, "unsure": True})  # ratio 0.5, under 0.7
    cfg = parse_config(CONFIG, tmp_path)
    grid, octave, stats, reason, warn = assemble_module._octave_pass(cfg, first, onsets, None, lambda bpm, r: weak)
    assert octave == 1 and grid is first and stats["evidence_ratio"] == 0.5 and warn[0].startswith("tempo: ")
    cfg.grid_octave = 2
    grid, octave, stats, reason, warn = assemble_module._octave_pass(cfg, first, onsets, None, lambda bpm, r: weak)
    assert octave == 2 and grid is weak and reason == "forced: grid_octave 2"
    assert warn == ["tempo doubled to 198.0 BPM: grid_octave 2", "beat phase unsure: the kick is about as strong "
                    "between the beats as on them (ratio 1.02): check that the beat lines are on the kick"]
    cfg.grid_octave = "auto"
    sure = _fake_grid(198.0, 0.8, {"ratio": 2.2, "shifted": True, "unsure": False})
    grid, octave, _, _, warn = assemble_module._octave_pass(cfg, first, onsets, None, lambda bpm, r: sure)
    assert octave == 2 and len(warn) == 1 and warn[0].startswith("tempo doubled")


def test_the_octave_pass_when_the_doubled_pass_finds_no_beats(tmp_path):
    """The doubled pass can raise an InputError (beatgrid: no confident drum evidence, under 3 confident beats on the
    doubled line). Under auto the first grid stays, with an evidence ratio of 0 and the "check the tempo" warning,
    and the chart goes on; a forced grid_octave 2 is that InputError (exit 2), never an AttributeError on the grid
    it did not get (exit 3, a bug)."""
    first = _fake_grid(99.0, 0.8)
    onsets = {"guitar": sixteenths()}
    asked = []

    def nothing(bpm, bpm_range):
        asked.append((bpm, bpm_range))
        raise InputError("no confident drum evidence on the made-up doubled line")

    cfg = parse_config(CONFIG, tmp_path)
    grid, octave, stats, reason, warn = assemble_module._octave_pass(cfg, first, onsets, None, nothing)
    assert asked == [(198.0, (2 * assemble_module.BPM_RANGE[0], 2 * assemble_module.BPM_RANGE[1]))]
    assert grid is first and octave == 1 and stats["second"] is None and stats["evidence_ratio"] == 0.0
    assert reason.endswith("the doubled grid's confident share 0.00 against 0.80 (ratio 0.00, under 0.7): the "
                           "first grid stays")
    assert len(warn) == 1 and warn[0].startswith("tempo: the notes are dense for 99.0 BPM (") and warn[0].endswith(
        ") but the drums give no evidence at 198.0 BPM: check the tempo")
    cfg.grid_octave = 2
    with pytest.raises(InputError, match="no confident drum evidence on the made-up doubled line"):
        assemble_module._octave_pass(cfg, first, onsets, None, nothing)
    assert len(asked) == 2


def test_the_backbeat_test_gets_the_drum_stem_only(fast_song, monkeypatch):
    """grid_octave is given the grid's features when the grid comes from the drum stem, and none from the mix (its
    snare band holds the other instruments too)."""
    root, config = fast_song
    seen = []

    def octave(onsets, beats, features, rules):
        seen.append(features)
        raise _Stop

    monkeypatch.setattr(assemble_module, "grid_octave", octave)
    for change in ({}, {"grid_source": "mix"}):
        with pytest.raises(_Stop):
            assemble(parse_config({**config, **change}, root))
    assert isinstance(seen[0], OnsetFeatures) and seen[1] is None



# ---------------------------------------------------------------------------- a tempo change under a doubled grid

def test_allin1_start_doubles_the_beats_moves_them_to_onset_times_and_checks_their_level():
    """allin1's beats (at a fast song's half rate) as the doubled grid's start: a midpoint between each two, then
    moved to onset times (beat_grid's start= convention, ONSET_TO_BEAT_MS later). None, with why, without beats,
    with under 8 inside the audio, or when doubled they are more than half an octave from the doubled grid."""
    beats = 1.0 + np.arange(100) * 0.6  # 100 BPM
    start, rec = assemble_module.allin1_start(beats, 200.0)
    want = np.sort(np.concatenate([beats, beats[:-1] + 0.3])) - ONSET_TO_BEAT_MS / 1000
    assert ONSET_TO_BEAT_MS < 0 and start == pytest.approx(want, abs=1e-12) and len(start) == 199
    assert rec == {"beats": 100, "doubled": 199, "bpm": 200.0, "why": "allin1's beats doubled: 199 beats at 200.0 BPM"}
    assert assemble_module.allin1_start(beats, 200.0 * 2 ** 0.45)[0] is not None  # inside half an octave
    for other in (400.0, 100.0, 141.0, 283.0):  # past it either way
        none, rec = assemble_module.allin1_start(beats, other)
        assert none is None and rec["why"] == (f"allin1's beats doubled are at 200.0 BPM, not the doubled grid's level "
                                               f"({other:.1f} BPM)")
    assert assemble_module.allin1_start(None, 200.0) == (None, {"beats": None,
                                                                "why": "the sections have no allin1 beats"})
    for few, duration in ((beats[:4], math.inf), (beats, 3.0)):  # 7 doubled; 1.022 to 2.822 s inside 3 s
        none, rec = assemble_module.allin1_start(few, 200.0, duration)
        assert none is None and rec["why"] == "allin1's beats doubled are 7 inside the audio, under 8"


def test_the_octave_pass_starts_the_doubled_grid_from_allin1_when_its_line_misses_a_tempo_change(tmp_path):
    """The doubled grid's straight line misses a tempo change (its tempo check is not empty) and allin1's beats are
    there: the second pass runs again from them, and that grid is the doubled grid, recorded and warned about. No
    allin1 beats, beats at another level, a grid from them that fails, or no missed tempo change: the line stays,
    asked for once when nothing is missed."""
    first = _fake_grid(99.0, 0.8)
    onsets = {"guitar": sixteenths()}
    missed = [(30.0, 50.0, 170.0, 198.0), (35.0, 55.0, 170.0, 198.0)]
    line, followed = _fake_grid(198.0, 0.7), _fake_grid(198.0, 0.75)
    line.stats["tempo_check"], followed.stats["tempo_check"] = missed, []
    allin1 = 1.0 + np.arange(150) * 60 / 99
    calls = []

    def second(bpm, bpm_range, start=None):
        calls.append((bpm, bpm_range, start))
        return line if start is None else followed

    cfg = parse_config(CONFIG, tmp_path)
    grid, octave, stats, reason, warn = assemble_module._octave_pass(cfg, first, onsets, None, second, allin1, 120.0)
    assert grid is followed and octave == 2 and stats["evidence_ratio"] == pytest.approx(0.75 / 0.8, abs=1e-4)
    assert [c[:2] for c in calls] == [(198.0, (170.0, 370.0))] * 2 and calls[0][2] is None
    assert calls[1][2] == pytest.approx(assemble_module.allin1_start(allin1, line.bpm, 120.0)[0], abs=1e-12)
    rec = stats["second_start"]
    assert rec["grid"] == "allin1" and rec["tempo_check"] == [list(w) for w in missed]
    assert rec["why"] == ("the straight line misses a tempo change (2 tempo-check windows, 30-55 s): the grid starts "
                          "from allin1's beats doubled: 299 beats at 198.0 BPM")
    assert rec["allin1"]["beats"] == 150 and rec["line"]["confident_share"] == 0.7
    assert stats["second"]["confident_share"] == 0.75
    assert warn[-1] == ("the doubled grid follows allin1's beats: its straight line missed a tempo change at 30-55 s: "
                        "check sync there")
    tails = {"the sections have no allin1 beats": (None, second),
             "allin1's beats doubled are at 396.0 BPM, not the doubled grid's level (198.0 BPM)":
                 (1.0 + np.arange(300) * 60 / 198, second)}

    def failing(bpm, bpm_range, start=None):
        calls.append((bpm, bpm_range, start))
        if start is None:
            return line
        raise InputError("no confident drum evidence: made up")

    tails["allin1's beats doubled: 299 beats at 198.0 BPM; the grid from them failed: no confident drum evidence: "
          "made up"] = (allin1, failing)
    for tail, (beats, run) in tails.items():
        calls.clear()
        grid, octave, stats, _, warn = assemble_module._octave_pass(cfg, first, onsets, None, run, beats, 120.0)
        assert grid is line and octave == 2 and stats["second"]["confident_share"] == 0.7
        assert stats["second_start"]["grid"] == "line" and "line" not in stats["second_start"]
        assert stats["second_start"]["why"] == ("the straight line misses a tempo change (2 tempo-check windows, "
                                                f"30-55 s), but {tail}")
        assert not any("allin1" in w for w in warn) and len(calls) == (2 if run is failing else 1)
    line.stats["tempo_check"] = [missed[0]]   # one window is enough
    calls.clear()
    grid, octave, stats, _, warn = assemble_module._octave_pass(cfg, first, onsets, None, second, allin1, 120.0)
    assert grid is followed and len(calls) == 2 and stats["second_start"]["grid"] == "allin1"
    assert stats["second_start"]["why"].startswith("the straight line misses a tempo change (1 tempo-check windows, "
                                                   "30-50 s): ")
    line.stats["tempo_check"] = []
    first.stats["tempo_check"] = missed       # the first grid's own check is not the doubled grid's
    calls.clear()
    grid, octave, stats, _, warn = assemble_module._octave_pass(cfg, first, onsets, None, second, allin1, 120.0)
    assert grid is line and octave == 2 and len(calls) == 1 and len(warn) == 1
    assert stats["second_start"] == {"grid": "line", "why": "the tempo check finds no missed tempo change"}


def test_an_imported_charts_sections_have_no_allin1_beats(tmp_path):
    """sections "from:<part>" (the sections of an imported chart) is no allin1 file: no beats, not a file read."""
    cfg = parse_config({**CONFIG, "sections": "from:guitar"}, tmp_path)
    assert assemble_module._read_allin1_beats(cfg) is None
    assert assemble_module._read_allin1_beats(parse_config({**CONFIG, "sections": None}, tmp_path)) is None


STRETCH_START, STRETCH_BEATS = 45.0, 52  # 52 beats at 170 BPM in a 198 BPM song (as on the fourth stress song),
STRETCH = (STRETCH_START, STRETCH_START + STRETCH_BEATS * 60 / 170)  # which leave the 198 line 0.44 beat out after
STRETCH_SECONDS = 90.0


def stretch_beats() -> np.ndarray:
    t = [FAST_FIRST]
    while t[-1] < STRETCH_SECONDS - 2.0:
        t.append(t[-1] + (60 / 170 if STRETCH[0] <= t[-1] < STRETCH[1] - 1e-9 else FAST_BEAT))
    return np.array(t[:-1])


def _beat_f1(lines, truth, lo=-math.inf, hi=math.inf, tol=0.070) -> float:
    """F1 of the beat lines against the true beats inside [lo, hi), each matched within tol (nearest, both ways)."""
    lines, truth = np.asarray(lines), np.asarray(truth)
    t, g = truth[(truth >= lo) & (truth < hi)], lines[(lines >= lo) & (lines < hi)]
    hit_t = np.array([np.min(np.abs(lines - x)) <= tol for x in t])
    hit_g = np.array([np.min(np.abs(truth - x)) <= tol for x in g])
    return float(2 * hit_t.sum() * hit_g.mean() / (hit_t.sum() + len(t) * hit_g.mean())) if hit_t.any() else 0.0


@pytest.fixture(scope="module")
def stretch_song(tmp_path_factory):
    """A 198 BPM song with a 170 BPM stretch at 45-63 s: the fast song's drums and 16ths on its beats, and an
    allin1 result with made-up beats on every other beat (allin1's half rate on such a song), in 10 ms frames and
    off by up to 10 ms; a second sections file without them (the librosa fallback's)."""
    root = tmp_path_factory.mktemp("stretch")
    truth = stretch_beats()
    drums = fast_drums(beats=truth, seconds=STRETCH_SECONDS)
    times = np.concatenate([a + np.arange(4) * (b - a) / 4 for a, b in zip(truth, truth[1:])])
    tone = np.zeros(drums.shape[1], dtype=np.float32)
    for t in times:
        i = int(t * SR)
        tone[i:i + 2000] += (0.05 * np.sin(2 * np.pi * 330 * np.arange(2000) / SR)).astype(np.float32)
    A.write_wav(drums + tone, root / "mix.wav")
    A.write_wav(drums, root / "drums.wav")
    tm = TempoMap(480, [Tempo(0, 198000)])
    notes = [FretNote(round(tm.sec_to_tick(t)), ((0, 1, 2, 1)[q % 4],)) for q, t in enumerate(times)]
    (root / "tool").mkdir()
    (root / "tool" / "notes.chart").write_text(write_chart(Chart(SongInfo("tool", "tool"), tm, [], [
        Track("Expert", "Single", notes)])), encoding="utf-8", newline="")
    segments = [[0.0, 0.5, "start"], [0.5, STRETCH[0], "verse"], [STRETCH[0], STRETCH[1], "bridge"],
                [STRETCH[1], STRETCH_SECONDS, "chorus"]]
    half = truth[::2] + np.random.default_rng(5).uniform(-0.01, 0.01, len(truth[::2]))
    beats = [round(float(b), 2) for b in half]
    (root / "allin1.json").write_text(json.dumps({"segments": segments, "bpm": 99, "beats": beats,
                                                  "downbeats": beats[::4]}), encoding="utf-8")
    (root / "librosa.json").write_text(json.dumps({"segments": segments}), encoding="utf-8")
    config = {"audio": "mix.wav", "stems": {"drums": "drums.wav"}, "lead_in": 2.5, "sections": "allin1.json",
              "parts": [{"instrument": "guitar", "source": "tool/notes.chart"}], "levels": ["expert"],
              "grid_octave": 2, "metadata": {**CONFIG["metadata"], "name": "Stretch Song"}, "output": "out/allin1"}
    return root, config, truth


def test_a_doubled_grid_follows_a_tempo_change_from_allin1s_beats(stretch_song):
    """The doubled grid's straight line misses the 170 BPM stretch (its tempo check warns; on this made-up song
    the first grid follows the stretch, so the line, hinted at twice its tilted click tempo, is off elsewhere too).
    Started from allin1's beats it follows the stretch and the 198 BPM around it, its own tempo check finds nothing,
    and report.json and the warnings say so. From the librosa fallback's sections (no beats) the line stays,
    warned about, as before. (grid_octave 2 on both: without allin1's beats the line's evidence is too thin for the
    octave pass to keep it.)"""
    root, config, truth = stretch_song
    a = assemble(parse_config(config, root))
    b = assemble(parse_config({**config, "sections": "librosa.json", "output": "out/librosa"}, root))
    assert a.ok and b.ok and a.report["grid"]["octave"] == b.report["grid"]["octave"] == 2
    ga, gb = a.report["grid"], b.report["grid"]
    rec = ga["octave_stats"]["second_start"]
    assert rec["grid"] == "allin1" and rec["allin1"]["beats"] == len(truth[::2]) and rec["tempo_check"]
    assert rec["why"].startswith("the straight line misses a tempo change (") and ga["stats"]["start"]["source"] == \
        "external" and ga["stats"]["tempo_check"] == []
    assert rec["line"] == gb["octave_stats"]["second"]  # the line it replaced is the grid without allin1's beats
    assert gb["octave_stats"]["second_start"]["grid"] == "line" and gb["octave_stats"]["second_start"]["why"].endswith(
        "but the sections have no allin1 beats") and gb["stats"]["tempo_check"] == rec["tempo_check"]
    lines = {k: np.asarray(r.lead.beats) - r.lead.pad_seconds for k, r in (("allin1", a), ("line", b))}
    assert _beat_f1(lines["allin1"], truth, *STRETCH) > 0.95 and _beat_f1(lines["allin1"], truth) > 0.95
    assert _beat_f1(lines["allin1"], truth, STRETCH[1]) > 0.9  # and in phase after it
    assert _beat_f1(lines["line"], truth, *STRETCH) < 0.6
    follows = [w for w in a.report["warnings"] if "allin1" in w]
    assert len(follows) == 1 and follows[0].startswith("the doubled grid follows allin1's beats: its straight line "
                                                       "missed a tempo change at ")
    assert not any("is not followed by the grid" in w for w in a.report["warnings"])
    assert any("is not followed by the grid" in w for w in b.report["warnings"])
    assert not any("allin1" in w for w in b.report["warnings"])
    # the bar phase lands on the doubled grid the octave pass returned: allin1's downbeats (every 8th beat of it)
    downbeats = json.loads((root / "allin1.json").read_text(encoding="utf-8"))["downbeats"]
    assert ga["downbeat_source"] == "allin1" and not ga["downbeats_uncertain"]
    vote = ga["stats"]["downbeats"]["vote"]
    assert vote["voting"] == len(downbeats) and max(vote["counts"]) == len(downbeats)
    bars = np.asarray(a.lead.beats)[a.lead.first_beat::4] - a.lead.pad_seconds
    assert np.mean([np.min(np.abs(bars - d)) < 0.05 for d in downbeats]) > 0.95


def test_allin1s_beats_change_nothing_when_the_doubled_grid_misses_no_tempo_change(fast_song):
    """The steady 198 BPM song with allin1's beats in its sections file: its doubled grid's tempo check is empty,
    so the chart is the one built without them, and report.json says the line stayed and why."""
    root, config = fast_song
    beats = [round(FAST_FIRST + k * 2 * FAST_BEAT, 2) for k in range(int((FAST_SECONDS - 1) / (2 * FAST_BEAT)))]
    data = json.loads((root / "allin1.json").read_text(encoding="utf-8"))
    (root / "allin1-beats.json").write_text(json.dumps({**data, "beats": beats}), encoding="utf-8")
    a = assemble(parse_config({**config, "output": "out/steady-plain"}, root))
    b = assemble(parse_config({**config, "sections": "allin1-beats.json", "output": "out/steady-beats"}, root))
    assert a.report["grid"]["octave"] == b.report["grid"]["octave"] == 2
    want = {"grid": "line", "why": "the tempo check finds no missed tempo change"}
    assert a.report["grid"]["octave_stats"]["second_start"] == b.report["grid"]["octave_stats"]["second_start"] == want
    assert (a.folder / "notes.chart").read_bytes() == (b.folder / "notes.chart").read_bytes()
    assert np.array_equal(a.lead.beats, b.lead.beats) and a.report["warnings"] == b.report["warnings"]
