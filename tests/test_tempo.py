import numpy as np
import pytest

from songcharter.tempo import Tempo, TempoMap, TimeSignature, plan_lead_in


def test_constant_tempo_is_one_marker():
    period = 60 / 142.0
    beats = np.arange(0, 980) * period
    tm = TempoMap.from_beats(beats)
    assert len(tm.tempos) == 1
    assert tm.tempos[0].bpm_milli == 142000
    # every beat within tolerance after a 7-minute song
    for i in (1, 100, 979):
        assert abs(tm.tick_to_sec(i * 192) - beats[i]) < 0.002


def test_rounding_error_does_not_accumulate():
    # a tempo that 0.001 BPM can't represent exactly: one marker would drift, error feedback must not
    period = 60 / 141.99937
    beats = np.arange(0, 1200) * period
    tm = TempoMap.from_beats(beats, tolerance=0.0005)
    err = np.abs(tm.ticks_to_secs(np.arange(1200) * 192) - beats)
    assert err.max() < 0.0005


def test_drifting_tempo_gets_markers_and_stays_within_tolerance():
    rng = np.random.default_rng(1)
    bpm = 120 + np.cumsum(rng.normal(0, 0.4, 600))  # a live drummer wandering around 120
    beats = np.concatenate([[0], np.cumsum(60 / bpm[:-1])])
    tm = TempoMap.from_beats(beats, tolerance=0.002)
    assert 5 < len(tm.tempos) < 600
    err = np.abs(tm.ticks_to_secs(np.arange(600) * 192) - beats)
    assert err.max() <= 0.002 + 1e-9


def test_tick_sec_round_trip():
    tm = TempoMap(192, [Tempo(0, 120000), Tempo(768, 90000), Tempo(1536, 200500)])
    for tick in (0, 100, 768, 1000, 1536, 5000):
        assert tm.sec_to_tick(tm.tick_to_sec(tick)) == pytest.approx(tick, abs=1e-6)
    assert tm.tick_to_sec(768) == pytest.approx(2.0)
    assert tm.tick_to_sec(1536) == pytest.approx(2.0 + 4 * 60 / 90)


def test_time_signature_must_be_on_a_measure_boundary():
    with pytest.raises(ValueError):
        TempoMap(192, [Tempo(0, 120000)], [TimeSignature(0, 4), TimeSignature(500, 3)])
    TempoMap(192, [Tempo(0, 120000)], [TimeSignature(0, 4), TimeSignature(768, 3), TimeSignature(768 + 576, 4)])


def test_sync_track_order_and_anchors():
    tm = TempoMap(192, [Tempo(0, 120000), Tempo(768, 121500)], [TimeSignature(0, 4), TimeSignature(768, 6, 8)])
    assert tm.sync_track_lines() == [(0, "TS 4"), (0, "B 120000"), (768, "TS 6 3"), (768, "A 2000000"), (768, "B 121500")]


def test_lead_in_puts_tick_zero_on_a_measure_line():
    period = 60 / 142.0
    first = 0.0749
    beats = first + np.arange(0, 400) * period  # song with sound from 0 s, first beat at 75 ms
    downbeats = list(range(2, 400, 4))         # two pickup beats, then 4/4
    li = plan_lead_in(beats, downbeats, 44100, min_lead=2.5, duration=beats[-1] + 1)
    assert li.beats[0] == 0.0
    assert li.pad_seconds >= 2.5
    # the song's first downbeat sits on a whole measure of the padded grid
    assert li.first_beat % 4 == 0
    assert li.beats[li.first_beat] == pytest.approx(beats[2] + li.pad_seconds, abs=1e-9)
    tm = TempoMap.from_beats(li.beats, li.bars)
    assert len(tm.tempos) <= 2
    # every detected beat after the first downbeat lands on its tick within 2 ms
    for j, t in enumerate(beats[2:]):
        assert abs(tm.tick_to_sec((li.first_beat + j) * 192) - (t + li.pad_seconds)) < 0.002


def test_lead_in_meter_changes():
    period = 0.5
    beats = 1.0 + np.arange(0, 40) * period
    downbeats = [0, 4, 8, 11, 15, 19, 23]  # one 3-beat measure
    li = plan_lead_in(beats, downbeats, 44100, min_lead=2.0)
    tm = TempoMap.from_beats(li.beats, li.bars)
    nums = [(ts.tick // 192 - li.first_beat, ts.numerator) for ts in tm.time_signatures]
    assert nums[1:] == [(8, 3), (11, 4)]
