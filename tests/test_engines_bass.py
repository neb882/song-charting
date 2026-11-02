"""The bass rule engine (songcharter.engines.bass) on a synthetic bass line: onsets, the leakage gate, pitch and
lanes, sustains from the pitch track, the folder an importer reads, determinism and the cache."""
import json

import numpy as np
import pytest

pytest.importorskip("librosa")

import songcharter.engines.bass as B  # noqa: E402
from songcharter.engines.bass import Settings, generate, map_lanes, transcribe  # noqa: E402
from songcharter.importers import read_song  # noqa: E402

SR = B.SAMPLE_RATE
# (onset s, MIDI pitch, how long it rings s): a phrase up and down, a held note, a 2-s rest, two short notes and an
# octave jump
LINE = [(0.50, 40, 0.10), (1.00, 43, 0.10), (1.50, 45, 0.10), (2.00, 47, 0.10), (2.50, 45, 0.40), (3.00, 43, 0.10),
        (3.50, 40, 1.60), (5.50, 38, 0.10), (6.00, 38, 0.10), (6.50, 50, 0.40)]
LANES = [0, 1, 2, 3, 2, 1, 0, 1, 1, 3]   # map_v2 of those pitches: two phrases (the 2-s rest splits them)
SECONDS = 7.5


def bass_line(line=LINE, seconds=SECONDS, seed=0):
    """Plucked harmonic tones (3 ms attack, slow decay, 10 ms release) over a -80 dB noise floor, in stereo."""
    rng = np.random.default_rng(seed)
    n = int(seconds * SR)
    y = 1e-4 * rng.standard_normal(n)
    for t0, midi, ring in line:
        f0 = 440.0 * 2 ** ((midi - 69) / 12)
        a, m = int(t0 * SR), int((ring + 0.01) * SR)
        t = np.arange(m) / SR
        env = np.minimum(1.0, t / 0.003) * np.exp(-t / 0.8) * np.clip((ring + 0.01 - t) / 0.01, 0, 1)
        tone = sum(np.sin(2 * np.pi * f0 * k * t) / k for k in range(1, 30) if f0 * k < 8000)
        y[a:a + m] += 0.3 * env * tone
    return np.stack([y, y]).astype(np.float32)


@pytest.fixture(scope="module")
def stem():
    return bass_line()


@pytest.fixture(scope="module")
def notes(stem):
    return transcribe(stem, stem)


@pytest.fixture(scope="module")
def folder(stem, tmp_path_factory):
    return generate(stem, stem, tmp_path_factory.mktemp("bass") / "engine")


def test_onsets_pitch_and_lanes_follow_the_line(notes):
    got, stats = notes
    assert len(got) == len(LINE)
    assert np.allclose([n.time for n in got], [t for t, _, _ in LINE], atol=0.03)
    assert [n.frets for n in got] == [(lane,) for lane in LANES]
    assert all(n.hopo is None and not n.hopo_forced and not n.tap for n in got)  # natural rules on our grid decide
    c = stats["counts"]
    assert c["onsets"] == c["notes"] == len(LINE) and c["leakage_dropped"] == 0 and c["unvoiced_notes"] == 0
    assert c["lanes"] == np.bincount(LANES, minlength=5).tolist()
    assert stats["pitch_midi_p5_p50_p95"][0] == pytest.approx(38, abs=0.5)


def test_sustains_come_from_where_the_pitch_holds(notes):
    got, _ = notes
    ends = {t: n.end for (t, _, _), n in zip(LINE, got)}
    assert all(ends[t] is None for t, _, ring in LINE if ring < 0.2)      # short notes: no sustain
    assert ends[2.50] == pytest.approx(2.50 + 0.40, abs=0.05)             # held until it stops ringing
    held = got[6]
    assert held.end == pytest.approx(3.50 + 1.60, abs=0.05) and held.end <= 5.50 - 0.085
    assert ends[6.50] == pytest.approx(6.90, abs=0.05)
    # a note that rings into the next one stops 85 ms before it
    legato = [(0.5, 40, 1.2), (1.5, 43, 0.10)]
    got, _ = transcribe(bass_line(legato, 2.5), bass_line(legato, 2.5))
    assert got[0].end == pytest.approx(got[1].time - 0.085, abs=1e-9)


def test_the_leakage_gate_drops_notes_where_the_stem_is_30_db_under_the_mix(stem):
    rng = np.random.default_rng(1)
    loud = stem + 30 * rng.standard_normal(stem.shape).astype(np.float32)   # the mix 40+ dB over the stem
    got, stats = transcribe(loud, stem)
    assert got == [] and stats["counts"]["leakage_dropped"] == stats["counts"]["onsets"] == len(LINE)
    # the rule itself: levels 20 dB and 40 dB under the mix
    s = Settings()
    fps = SR / B.LEVEL_HOP
    stem_lv = np.r_[np.full(int(2 * fps), 1e-2), np.full(int(2 * fps), 1e-4)]
    mix_lv = np.ones(len(stem_lv))
    assert B.leakage_ok(np.array([0.5, 1.0, 2.5, 3.5]), stem_lv, mix_lv, s).tolist() == [True, True, False, False]
    assert B.leakage_ok(np.array([0.5]), stem_lv, mix_lv, Settings(leak_db=45.0)).tolist() == [True]


def test_the_folder_reads_back_as_expert_bass_in_seconds(folder, notes):
    got, _ = notes
    assert folder.chart == folder.folder / "notes.chart" and not folder.cached
    song = read_song(folder.folder)                      # no song.ini: bass needs no modifiers
    assert list(song.parts) == [("bass", "expert")]
    back = song.parts[("bass", "expert")].notes
    tick = 1 / B.TICKS_PER_S
    assert [n.frets for n in back] == [n.frets for n in got]
    assert np.allclose([n.time for n in back], [n.time for n in got], atol=tick / 2 + 1e-9)
    assert [n.end is None for n in back] == [n.end is None for n in got]
    assert all(abs(a.end - b.end) <= tick + 1e-9 for a, b in zip(back, got) if a.end is not None)
    assert not any(n.hopo_forced for n in back)
    text = folder.chart.read_text(encoding="utf-8")
    assert "[ExpertDoubleBass]" in text and "0 = B 120000" in text and "Resolution = 480" in text
    assert " N 5 " not in text and " N 7 " not in text   # no forced HOPOs, no open notes
    info = json.loads((folder.folder / "engine.json").read_text(encoding="utf-8"))
    assert info == folder.info and info["engine"] == B.ENGINE and info["version"] == B.VERSION
    assert info["settings"]["delta"] == 0.07 and info["settings"]["fmin"] == 30.0
    assert set(info["versions"]) >= {"songcharter", "librosa", "numpy", "scipy"}
    assert info["counts"]["notes"] == len(LINE) and info["timings_s"]["pitch"] >= 0
    assert info["input"] == {"sample_rate": SR, "samples": int(SECONDS * SR), "seconds": SECONDS}


def test_two_runs_write_the_same_chart(stem, folder, tmp_path):
    again = generate(stem, stem, tmp_path / "again")
    assert not again.cached and again.info["key"] == folder.info["key"]
    assert again.chart.read_bytes() == folder.chart.read_bytes()


def test_a_finished_folder_is_reused_and_any_change_runs_again(stem, tmp_path, monkeypatch):
    out = tmp_path / "engine"
    first = generate(stem, stem, out)
    calls = []
    real = B.transcribe
    monkeypatch.setattr(B, "transcribe", lambda *a, **k: calls.append(1) or real(*a, **k))
    again = generate(stem, stem, out)
    assert again.cached and calls == [] and again.info == first.info
    generate(stem, stem, out, Settings(delta=0.05))      # another setting
    assert calls == [1]
    other = stem.copy()
    other[:, :10] = 0                                    # other samples
    assert B.cache_key(other, stem, Settings(), B.versions()) != first.info["key"]
    generate(stem, stem, out)
    assert calls == [1, 1]                               # the folder now held the delta 0.05 run
    out.joinpath("notes.chart").write_text("edited", encoding="utf-8")
    assert not generate(stem, stem, out).cached          # an edited chart is not reused
    out.joinpath("engine.json").write_text("{", encoding="utf-8")
    assert not generate(stem, stem, out).cached          # nor a broken engine.json
    assert len(calls) == 4


def test_pitch_chunks_line_up_with_one_pass(stem):
    whole_t, whole = B.pitch_track(stem.mean(0), Settings())
    t, chunked = B.pitch_track(stem.mean(0), Settings(chunk_s=2.0, overlap_s=0.5))
    assert np.array_equal(t, whole_t)
    both = np.isfinite(whole) & np.isfinite(chunked)
    assert both.sum() > 0.9 * np.isfinite(whole).sum()
    assert np.mean(np.abs(whole[both] - chunked[both]) < 0.1) > 0.98


def test_map_lanes_keeps_v1s_rules():
    s = Settings()
    t = np.arange(8) * 0.5
    # repeated pitches keep their lane; an unknown pitch takes the previous one; the range is centred
    assert map_lanes(t[:5], [40, 40, 42, np.nan, 40], s).tolist() == [1, 1, 2, 2, 1]
    # a step of a 4th or more costs two lanes; a span over five lanes is squeezed, keeping the order
    assert map_lanes(t[:2], [40, 45], s).tolist() == [1, 3]
    assert map_lanes(t[:7], [40, 41, 42, 43, 44, 45, 46], s).tolist() == [0, 1, 1, 2, 3, 3, 4]
    # notes under 0.2 s apart move at most two lanes
    assert map_lanes([0.0, 0.5, 1.0, 1.5], [40, 47, 43, 45], s).tolist() == [0, 3, 1, 2]
    assert map_lanes([0.0, 0.1, 0.2, 0.3], [40, 47, 43, 45], s).tolist() == [0, 2, 1, 2]
    # windows of 12 notes are ranked on their own; no pitch at all leaves yellow
    assert map_lanes(np.arange(13) * 0.25, [40] * 12 + [52], s).tolist() == [2] * 13
    assert map_lanes(t[:3], [np.nan] * 3, s).tolist() == [2, 2, 2]
    assert map_lanes([], [], s).tolist() == []


def test_settings_and_inputs_are_checked(stem, tmp_path):
    with pytest.raises(ValueError, match="2941"):
        Settings(pitch_rate=44100)                       # DESIGN.md 2.8: fmin 30 at 44.1 kHz needs 2941
    with pytest.raises(ValueError, match="pitch range"):
        Settings(fmin=500.0)
    with pytest.raises(ValueError, match="stereo"):
        generate(stem[0], stem[0], tmp_path / "x")
    with pytest.raises(ValueError, match="differ in length"):
        generate(stem, stem[:, :-1], tmp_path / "x")
    with pytest.raises(ValueError, match="44100 Hz"):
        generate(stem, stem, tmp_path / "x", sample_rate=48000)
    assert not (tmp_path / "x").exists()


def test_a_silent_stem_writes_a_chart_without_bass(tmp_path):
    quiet = np.zeros((2, 3 * SR), np.float32)
    r = generate(quiet, quiet, tmp_path / "engine")
    assert r.info["counts"]["notes"] == 0 and r.info["pitch_midi_p5_p50_p95"] is None
    assert "[ExpertDoubleBass]" not in r.chart.read_text(encoding="utf-8")
    assert read_song(r.folder).parts == {}
