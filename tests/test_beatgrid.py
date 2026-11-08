"""The beat grid on synthetic drum tracks: kick, snare and hat hits placed on known beats."""
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

import songcharter.beatgrid as B
from songcharter.beatgrid import (BPM_RANGE, DOWNBEAT_MIN_MARGIN, HALF_BEAT_SHIFT, BeatGrid, OnsetFeatures,
                                  bar_phase, beat_grid, downbeat_vote, estimate_tempo, half_beat_phase,
                                  local_beats, local_periods, loess, mel_filterbank, missed_tempo_changes,
                                  onset_features, onset_phase, onset_times, robust_line, shift_half_beat,
                                  track_beats, window_tempi, with_downbeats)
from songcharter.errors import InputError
from songcharter.tempo import TempoMap, plan_lead_in

ROOT = Path(__file__).resolve().parent.parent

SR = 22050  # the onset envelope's reference rate; one test runs at 44100


def drums(beats, duration, sr=SR, kick_phase=0, snare_phase=2, seed=0, active=None):
    """A hat on every beat, a kick on beats with index % 4 == kick_phase, a snare on snare_phase (half-time feel)."""
    rng = np.random.default_rng(seed)
    y = np.zeros(int(duration * sr))
    t = np.arange(int(0.25 * sr)) / sr
    kick = np.sin(2 * np.pi * 55 * t) * np.exp(-t / 0.08)
    snare = (0.5 * np.sin(2 * np.pi * 190 * t) + 0.6 * rng.standard_normal(len(t))) * np.exp(-t / 0.06)
    hat = np.diff(rng.standard_normal(len(t) + 1)) * np.exp(-t / 0.015) * 0.15
    for k, b in enumerate(beats):
        i = int(round(b * sr))
        if (active is not None and not active(b)) or i < 0 or i + len(t) > len(y):
            continue
        y[i:i + len(t)] += hat + (kick if k % 4 == kick_phase else 0) + (snare if k % 4 == snare_phase else 0)
    y += rng.standard_normal(len(y)) * 1e-3
    return (0.5 * y).astype(np.float32)


def plucks(times, duration, sr=SR, seed=0):
    """A guitar-like stem: a decaying harmonic tone at each time, cycling through four pitches, off-beats softer."""
    rng = np.random.default_rng(seed)
    y = np.zeros(int(duration * sr))
    t = np.arange(int(0.3 * sr)) / sr
    fade = np.minimum(1.0, (t[-1] - t) / 0.05)  # no click where the tone is cut off
    for k, b in enumerate(times):
        f0 = (196.0, 247.0, 294.0, 330.0)[k % 4]
        tone = sum(np.sin(2 * np.pi * f0 * h * t) / h for h in range(1, 6)) * np.exp(-t / 0.1) * fade
        i = int(round(b * sr))
        if 0 <= i and i + len(t) <= len(y):
            y[i:i + len(t)] += tone * (1.0 if k % 2 == 0 else 0.7)
    y += rng.standard_normal(len(y)) * 1e-3
    return (0.1 * y).astype(np.float32)


def nearest(beats, truth):
    """For each true beat, the closest grid beat."""
    i = np.clip(np.searchsorted(beats, truth), 1, len(beats) - 1)
    c = np.stack([beats[i - 1], beats[i]], axis=1)
    return c[np.arange(len(truth)), np.argmin(np.abs(c - truth[:, None]), axis=1)]


def spread_ms(beats, truth):
    """(median offset, p95 of |offset - median|) in ms: the grid's constant delay and how well it follows."""
    d = (nearest(beats, truth) - truth) * 1000
    return float(np.median(d)), float(np.percentile(np.abs(d - np.median(d)), 95))


@pytest.fixture(scope="module")
def steady():
    truth = 0.5 + np.arange(119) * 0.5  # 120 BPM, first beat at 0.5 s, kick on beat 0
    return truth, drums(truth, 60.0)


def test_mel_filterbank_and_envelope_match_librosa(steady):
    librosa = pytest.importorskip("librosa")
    assert np.allclose(mel_filterbank(SR, 2048), librosa.filters.mel(sr=SR, n_fft=2048), atol=1e-7)
    _, y = steady
    ours = onset_features(y, SR).env
    ref = librosa.onset.onset_strength(y=y, sr=SR, hop_length=128, n_fft=2048)
    assert len(ours) == len(ref)
    assert np.corrcoef(ours, ref)[0, 1] > 0.9999
    big = ref > 0.5 * ref.max()
    assert np.allclose(ours[big], ref[big], rtol=0.02)


def test_envelope_peaks_do_not_depend_on_the_sample_rate(steady):
    truth, y = steady
    y44 = np.repeat(y, 2)  # the same hits at 44100 Hz (sample-and-hold upsampling keeps the attacks in place)
    a = local_beats(onset_features(y, SR), truth)
    b = local_beats(onset_features(y44, 2 * SR), truth)
    assert np.nanmax(np.abs(a.times - b.times)) < 0.0015


def test_tempo_folds_into_one_octave():
    fps = SR / 128
    n = int(60 * fps)

    def pulses(bpm):
        env = np.zeros(n)
        env[np.round(np.arange(1, 59, 60 / bpm) * fps).astype(int)] = 1.0
        return env

    assert estimate_tempo(pulses(142.0), fps) == pytest.approx(142.0, abs=0.3)
    assert estimate_tempo(pulses(71.0), fps) == pytest.approx(142.0, abs=0.3)   # half-time pulse: doubled
    assert estimate_tempo(pulses(200.0), fps) == pytest.approx(100.0, abs=0.3)  # too fast: halved


SPARSE = ([216, 1118, 1397, 1400, 1403, 1694, 1699, 1732], [0.32, 0.18, 0.45, 0.07, 0.98, 0.7, 0.06, 0.66])  # made up


def test_a_sparse_window_gives_a_tempo_in_range_and_ends():
    """Eight scattered onsets in 20 s (a quiet window): the refined period came out negative here, and folding the
    negative tempo by octaves never ended (a build stuck for an hour). In a subprocess with a time limit, so a hang
    fails the test instead of stopping the suite."""
    code = ("import numpy as np; import songcharter.beatgrid as B; env = np.zeros(2000); "
            f"env[{SPARSE[0]}] = {SPARSE[1]}; lo, hi = B.BPM_RANGE; bpms = np.arange(lo, hi, 0.05); "
            "ac = B._autocorrelation(env, 100.0, int(4.5 * 60 * 100.0 / lo)); "
            "coarse = float(bpms[int(np.argmax(B._tempo_score(ac, 60.0 * 100.0 / bpms)))]); "
            "print(B.estimate_tempo(env, 100.0), coarse)")
    p = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True, timeout=60)
    assert p.returncode == 0, p.stderr[-500:]
    bpm, coarse = map(float, p.stdout.split())
    assert bpm == coarse and BPM_RANGE[0] <= bpm < BPM_RANGE[1]    # the unrefined winner, not just any tempo in range


def test_the_octave_fold_ends_on_any_tempo():
    """A tempo folds by octaves into the range; one that is not a positive finite number takes the fallback (in a
    subprocess with a time limit: without the guard the fold never ends)."""
    assert [B._fold(b, BPM_RANGE, 120.0) for b in (60.0, 240.0, 100.0, 184.9)] == [120.0, 120.0, 100.0, 184.9]
    code = ("from songcharter.beatgrid import _fold, BPM_RANGE; "
            "print([_fold(b, BPM_RANGE, 120.0) for b in (-3.6e-9, -200.0, 0.0, float('inf'), float('-inf'), "
            "float('nan'))])")
    p = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True, timeout=60)
    assert p.returncode == 0 and p.stdout.strip() == str([120.0] * 6), p.stderr[-500:]


def test_steady_drums_give_a_straight_grid_and_the_kick_bar_phase(steady):
    truth, y = steady
    g = beat_grid(y, SR, onset_to_beat_ms=0.0)
    assert isinstance(g, BeatGrid) and np.all(np.diff(g.beats) > 0)
    assert g.mode == "free" and g.stats["evidence"]["confident_share"] > 0.95
    assert abs(g.bpm - 120.0) < 0.01
    delay, spread = spread_ms(g.beats, truth)
    assert 0 < delay < 25 and spread < 1.0  # envelope peaks sit a constant few ms after the attacks
    # the beat before the first hit is on the grid too (beats start at the first grid beat after 0 s)
    assert g.beats[0] == pytest.approx(truth[0] - 0.5 + delay / 1000, abs=0.002)
    # the kick is on truth[0], which is grid beat 1, so bars start at beat 1
    assert g.stats["downbeats"]["phase"] == 1 and not g.stats["downbeats"]["uncertain"]
    assert g.downbeats[0] == 1 and np.all(np.diff(g.downbeats) == 4)


def test_onset_to_beat_shift_and_trim(steady):
    truth, y = steady
    a = beat_grid(y, SR, onset_to_beat_ms=0.0)
    b = beat_grid(y, SR)  # default: beat lines 22 ms before the envelope peaks
    assert b.stats["onset_to_beat_ms"] == -22.0
    shifted = a.beats - 0.022
    assert np.allclose(b.beats, shifted[shifted >= 0])
    assert b.beats[b.downbeats[0]] == pytest.approx(a.beats[a.downbeats[0]] - 0.022)


def test_downbeat_phase_follows_the_kick():
    truth = 0.5 + np.arange(119) * 0.5
    y = drums(truth, 60.0, kick_phase=2, snare_phase=0, seed=5)
    g = beat_grid(y, SR, bpm=120.0, first_beat=0.5)
    first_bar = nearest(g.beats, truth[2:3])[0]
    assert g.beats[g.downbeats[0]] == first_bar
    assert g.stats["downbeats"]["margin"] > 0.5


def test_hints_converge_to_the_same_grid(steady):
    truth, y = steady
    a = beat_grid(y, SR)
    b = beat_grid(y, SR, bpm=120 * 1.003, first_beat=truth[0] + 0.03)  # 0.3 % and 30 ms off
    assert b.stats["start"]["source"] == "hints"
    assert np.max(np.abs(nearest(b.beats, a.beats[1:]) - a.beats[1:])) < 1e-6


def test_free_mode_follows_a_drifting_drummer():
    k = np.arange(206)
    period = 60 / 140
    truth = 0.3 + k * period + 0.025 * np.sin(2 * np.pi * k / 48)  # +-25 ms around a click
    y = drums(truth, 90.0, seed=1)
    free = beat_grid(y, SR, onset_to_beat_ms=0.0)
    click = beat_grid(y, SR, onset_to_beat_ms=0.0, mode="click")
    assert free.mode == "free" and free.stats["start"]["grid"] == "line"
    assert click.mode == "click" and click.stats["mode"]["reason"] == "override"
    assert spread_ms(free.beats, truth)[1] < 3.0
    assert spread_ms(click.beats, truth)[1] > 15.0
    assert free.stats["drift_ms"]["max_abs"] > 20.0  # reported, though it does not decide the mode
    assert free.stats["free"]["tempo_step_max"] <= 0.02 + 1e-9


def test_drumless_intro_is_filled_from_the_line():
    truth = 0.25 + np.arange(158) * 0.5
    y = drums(truth, 80.0, seed=2, active=lambda b: b >= 20.0)
    g = beat_grid(y, SR, onset_to_beat_ms=0.0)
    assert g.mode == "free"
    assert 0.6 < g.stats["evidence"]["confident_share"] < 0.8
    delay, spread = spread_ms(g.beats, truth)
    assert spread < 1.0
    intro = np.diff(g.beats[g.beats < 17.5])  # beats more than 4 beats from the first hit at 20.25 s
    assert np.ptp(intro) < 1e-4  # the line, where there is no evidence within reach


def test_sparse_evidence_gives_click_mode_unless_overridden():
    truth = 0.25 + np.arange(158) * 0.5
    y = drums(truth, 80.0, seed=3, active=lambda b: b >= 56.0)
    g = beat_grid(y, SR)
    assert g.mode == "click" and g.stats["evidence"]["confident_share"] < 0.6
    assert np.ptp(np.diff(g.beats)) < 1e-9  # one straight line
    assert beat_grid(y, SR, mode="free").mode == "free"
    with pytest.raises(ValueError):
        beat_grid(y, SR, mode="loose")


def test_tracker_takes_over_when_the_tempo_moves():
    t = [0.4]
    while t[-1] < 59.0:
        t.append(t[-1] + 60 / (120 + 12 * t[-1] / 60))  # 120 -> 132 BPM over a minute: no click
    truth = np.array(t[:-1])
    y = drums(truth, 60.0, seed=4)
    g = beat_grid(y, SR, onset_to_beat_ms=0.0)
    assert g.stats["start"]["grid"] == "tracker" and g.mode == "free"
    assert g.stats["start"]["tracker_confident_share"] > g.stats["start"]["line_confident_share"] + 0.1
    assert spread_ms(g.beats, truth)[1] < 3.0


@pytest.fixture(scope="module")
def tempo_change():
    early = 0.3 + np.arange(75) * 0.4  # 150 BPM for 30 s (Take Me Out's intro is 142 against 104.6) ...
    late = early[-1] + 60 / 105 + np.arange(100) * 60 / 105  # ... then 105 BPM, which the global tempo picks
    truth = np.concatenate([early, late])
    return truth, drums(truth, 90.0, seed=8)


def test_tracker_follows_a_tempo_change_the_global_period_misses(tempo_change):
    truth, y = tempo_change
    g = beat_grid(y, SR, onset_to_beat_ms=0.0)
    assert g.stats["start"]["bpm"] == pytest.approx(105.0, abs=0.5) and g.stats["start"]["grid"] == "tracker"
    changes = g.stats["start"]["tracker_tempo_changes"]
    assert changes and changes[0][0] == 0.0 and all(b == pytest.approx(150.0, abs=1.0) for _, _, b in changes)
    assert np.mean(np.abs(nearest(g.beats, truth) - truth) <= 0.07) > 0.95
    assert g.stats["tempo_check"] == []
    # the tracker on the global period alone stays near 105 BPM through the 150 BPM part
    f = onset_features(y, SR)
    alone = track_beats(f.env, f.fps, 60 / g.stats["start"]["bpm"])
    early = truth[:75]
    assert np.mean(np.abs(nearest(alone, early) - early) <= 0.07) < 0.5


def test_local_periods_leave_a_steady_song_on_one_period(steady):
    _, y = steady
    f = onset_features(y, SR)
    assert local_periods(f.env, f.fps, 0.5) == (0.5, [])
    # a period per frame decodes exactly as one period when they are all equal
    assert np.array_equal(track_beats(f.env, f.fps, 0.5), track_beats(f.env, f.fps, np.full(len(f.env), 0.5)))


def test_tempo_check_flags_a_grid_that_misses_a_tempo_change(tempo_change):
    truth, y = tempo_change
    line = 0.3 + np.arange(155) * 60 / 105  # a start grid at the song's global 105 BPM throughout
    g = beat_grid(y, SR, onset_to_beat_ms=0.0, start=line)
    flagged = g.stats["tempo_check"]
    assert flagged and flagged[0][0] == 0.0 and all(t1 <= 40.0 for _, t1, _, _ in flagged)
    assert all(bpm == pytest.approx(150.0, abs=1.0) and grid < 115.0 for _, _, bpm, grid in flagged)


def test_onset_phase_measures_a_shift_and_refuses_an_ambiguous_phase():
    beats = np.arange(200) * 0.5
    eighths = np.sort(np.concatenate([beats, beats + 0.25]))[:-1]
    onsets = eighths + 0.010 + np.where(eighths >= 50.0, 0.040, 0.0)  # the stem lags 10 ms, then 50 ms
    calibrate = beats < 50.0
    shift, score, lag, stats = onset_phase(beats, onsets, calibrate)
    assert lag == pytest.approx(0.010, abs=0.0015) and stats["calibration_beats"] == 100
    assert np.all(np.abs(shift[5:95]) < 0.0015) and np.all(np.abs(shift[105:195] - 0.040) < 0.0015)
    assert np.all(score[5:95] > 0.95) and np.all(score[105:195] > 0.95)
    # even 16ths have no 8th-level phase, so a fit a 16th away would score the same: no score
    even = np.concatenate([eighths[eighths < 50.0], 50.0 + np.arange(400) * 0.125]) + 0.010
    _, score, _, _ = onset_phase(beats, even, calibrate)
    assert np.all(score[110:190] == 0.0) and np.all(score[5:95] > 0.95)
    # too few onsets within reach, or too little to calibrate on: no score and no lag
    _, score, _, _ = onset_phase(beats, onsets[::4], calibrate)
    assert np.all(score == 0.0)
    _, score, lag, _ = onset_phase(beats, onsets, np.zeros(200, dtype=bool))
    assert lag is None and np.all(score == 0.0)


def test_onset_times_find_the_plucks():
    times = 0.5 + np.arange(80) * 0.25
    on = onset_times(onset_features(plucks(times, 22.0), SR))
    assert len(on) == len(times)
    lag = on - times
    assert 0 < np.median(lag) < 0.02 and np.ptp(lag) < 0.005  # envelope peaks sit a steady few ms after attacks


def test_drumless_intro_follows_a_second_stem():
    truth = 0.25 + np.arange(158) * 0.5
    y = drums(truth, 80.0, seed=2, active=lambda b: b >= 20.0)
    # the guitar plays 8ths throughout, 12 ms behind the drums; alone in the intro it runs 30 ms late, then
    # comes back to the drummer's time before the drums enter
    eighths = np.sort(np.concatenate([truth, truth + 0.25]))
    late = lambda t: np.interp(t, [0, 12, 18, 80], [0.030, 0.030, 0.0, 0.0])  # noqa: E731
    guitar = plucks(eighths + late(eighths) + 0.012, 80.0, seed=3)
    line = beat_grid(y, SR, onset_to_beat_ms=0.0)
    g = beat_grid(y, SR, onset_to_beat_ms=0.0, secondary=guitar)
    delay, _ = spread_ms(line.beats, truth)
    heard = truth + late(truth) + delay / 1000  # where the band's beats are, in the grid's convention
    intro = (truth > 2) & (truth < 11)
    assert np.median(np.abs(nearest(line.beats, heard[intro]) - heard[intro])) > 0.025  # the line misses them
    assert np.max(np.abs(nearest(g.beats, heard[intro]) - heard[intro])) < 0.004
    sec = g.stats["secondary"]
    assert sec["lag_ms"] == pytest.approx(12.0, abs=6.0) and sec["calibration_score"] > 0.9
    assert sec["stretches"][0][0] < 1.0 and sec["stretches"][0][3] > 0.9
    alone = line.stats["secondary"]  # no second stem: the same drumless stretch is listed, none of it timed
    assert alone["beats_timed"] == 0 and alone["stretches"][0][:3] == sec["stretches"][0][:3]
    assert alone["stretches"][0][3] == 0.0
    drummed = line.beats >= 22.0
    assert np.max(np.abs(g.beats - line.beats)[drummed]) < 0.001  # beats with drum evidence keep the drums' time
    assert g.stats["free"]["tempo_step_max"] <= 0.02 + 1e-9


def test_a_second_stem_without_a_clear_phase_changes_nothing():
    truth = 0.25 + np.arange(158) * 0.5
    y = drums(truth, 80.0, seed=2, active=lambda b: b >= 20.0)
    noise = plucks(np.sort(np.random.default_rng(4).uniform(0, 79, 300)), 80.0, seed=5)  # onsets at random times
    line = beat_grid(y, SR, onset_to_beat_ms=0.0)
    g = beat_grid(y, SR, onset_to_beat_ms=0.0, features=onset_features(y, SR),
                  secondary_features=onset_features(noise, SR))
    sec = g.stats["secondary"]
    assert sec["calibration_score"] < 0.1 and sec["lag_ms"] is None  # it does not follow the drums either
    assert sec["beats_timed"] == 0 and np.array_equal(g.beats, line.beats)
    # click mode: every beat is on the line, whatever the second stem says
    click = beat_grid(y, SR, mode="click", secondary=noise)
    assert click.stats["secondary"]["beats_timed"] == 0 and np.ptp(np.diff(click.beats)) < 1e-9


def test_external_start_is_the_hook_for_a_tracker(steady):
    truth, y = steady
    jitter = np.random.default_rng(7).uniform(-0.03, 0.03, len(truth))
    g = beat_grid(y, SR, onset_to_beat_ms=0.0, start=truth + 0.012 + jitter)
    assert g.stats["start"]["source"] == "external" and g.stats["start"]["grid"] == "tracker"
    assert len(g.beats) == len(truth)
    assert spread_ms(g.beats, truth)[1] < 2.0
    with pytest.raises(ValueError):
        beat_grid(y, SR, start=truth[::-1])


HALVED = dict(bpm_range=(BPM_RANGE[0] / 2, BPM_RANGE[1] / 2), half_beat=False, keep_line=True)  # the halving pass's


@pytest.fixture(scope="module")
def drumless_wander():
    """A click at 75 BPM (a halved grid's level) whose drums enter at 30 s, and start beats (allin1's, in onset
    times as the halving pass passes them) on the drums after that and, in the drumless intro, running ahead from
    12 to 24 s (75 -> 87 -> 75 BPM, about 2 beats gained), as on a real song's intro (M7-09)."""
    dur, period, entry = 120.0, 0.8, 30.0
    truth = 0.4 + np.arange(int((dur - 1.0) / period)) * period
    y = drums(truth, dur, seed=11, active=lambda b: b >= entry)
    body = truth[truth >= entry]
    start, t = list(body + np.random.default_rng(3).uniform(-0.005, 0.005, len(body))), body[0]
    while True:  # the intro's beats, backwards from the drums' entry
        t -= period - (period - 0.69) * np.interp(t, [0, 12, 15, 20, 24, dur], [0, 0, 1, 1, 0, 0])
        if t < 0:
            break
        start.insert(0, t)
    return truth, y, np.array(start) - B.ONSET_TO_BEAT_MS / 1000, dur


def test_a_halved_start_through_a_drumless_wander_keeps_the_straight_line(drumless_wander):
    """line_test (the halving pass, M7-09): a straight line through the start beats finds as much drum evidence as
    they do, so it is the start grid (stats record both shares), keep_line notwithstanding, and the intro stays on
    the click: the tempo map is one marker at 75 BPM. Without the test the grid follows the start beats' wander."""
    truth, y, start, dur = drumless_wander
    f = onset_features(y, SR)
    grids = {t: beat_grid(y, SR, duration=dur, bpm=75.0, features=f, start=start, line_test=t, **HALVED)
             for t in (True, False)}
    g = grids[True]
    st = g.stats["start"]
    assert st["grid"] == "line" and st["source"] == "external" and st["n_beats"] == len(start) == len(truth) + 2
    assert st["bpm"] == pytest.approx(75.0, abs=0.01) and st["first_beat"] == pytest.approx(0.4, abs=0.03)
    assert st["line_confident_share"] > 0.7 and st["tracker_confident_share"] < st["line_confident_share"] + 0.1
    maps = {}
    for t, grid in grids.items():
        lead = plan_lead_in(grid.beats, grid.downbeats, SR, duration=dur)
        maps[t] = TempoMap.from_beats(lead.beats, bars=lead.bars, tolerance=0.003)
    assert [round(x.bpm, 2) for x in maps[True].tempos] == [75.0]
    intro = (truth > 2) & (truth < 28)
    _, p95 = spread_ms(g.beats, truth)  # one constant offset (the attacks against the peaks) everywhere ...
    assert p95 < 3.0
    assert np.abs(nearest(g.beats, truth[intro]) - truth[intro]).max() < 0.015  # ... the intro included
    # the line runs to the song's end, a period or less from it, past the last start beat (2 s before the end)
    assert start[-1] < dur - 1.5 and 0 <= dur - g.beats[-1] < 0.8
    old = grids[False]
    assert old.stats["start"]["grid"] == "tracker" and "line_confident_share" not in old.stats["start"]
    assert len(maps[False].tempos) > 10 and max(x.bpm for x in maps[False].tempos) > 84.0
    assert np.abs(nearest(old.beats, truth[intro]) - truth[intro]).max() > 0.3


def test_a_halved_start_with_a_real_tempo_change_keeps_the_start_beats():
    """line_test on a song that changes tempo (70 -> 84 BPM at 49 s, drums throughout): the start beats find far
    more evidence than any straight line through them (TRACKER_MARGIN more), so the grid is the start beats' as
    without the test, beat for beat and stat for stat, with the line's share recorded beside theirs."""
    a = 0.4 + np.arange(58) * 60 / 70
    b = a[-1] + 60 / 84 + np.arange(200) * 60 / 84
    truth = np.concatenate([a, b[b < 99.0]])
    y = drums(truth, 100.0, seed=12)
    start = truth - B.ONSET_TO_BEAT_MS / 1000 + np.random.default_rng(5).uniform(-0.005, 0.005, len(truth))
    f = onset_features(y, SR)
    with_test, without = (beat_grid(y, SR, duration=100.0, bpm=77.0, features=f, start=start, line_test=t, **HALVED)
                          for t in (True, False))
    st = with_test.stats["start"]
    assert st["grid"] == "tracker" and st["tracker_confident_share"] >= st["line_confident_share"] + B.TRACKER_MARGIN
    assert st["line_confident_share"] < 0.3 and 70.0 < st["bpm"] < 84.0
    assert np.array_equal(with_test.beats, without.beats) and np.array_equal(with_test.downbeats, without.downbeats)
    assert with_test.mode == without.mode == "free"
    assert {k: v for k, v in with_test.stats.items() if k != "start"} == {
        k: v for k, v in without.stats.items() if k != "start"}
    assert {k: v for k, v in st.items() if k not in ("bpm", "first_beat", "line_confident_share")} == \
        without.stats["start"]
    g = with_test.beats  # both tempos followed
    assert 60 / np.median(np.diff(g[g < 45])) == pytest.approx(70.0, abs=0.5)
    assert 60 / np.median(np.diff(g[g > 55])) == pytest.approx(84.0, abs=0.5)


def test_grid_feeds_the_tempo_map(steady):
    truth, y = steady
    g = beat_grid(y, SR)
    lead = plan_lead_in(g.beats, g.downbeats, SR, duration=60.0)
    tm = TempoMap.from_beats(lead.beats, bars=lead.bars, tolerance=0.003)
    assert len(tm.tempos) == 1
    err = tm.ticks_to_secs(np.arange(len(lead.beats)) * 192) - np.array(lead.beats)
    assert np.abs(err).max() <= 0.003
    # the first downbeat lands on a measure line, at its time in the padded audio
    assert lead.first_beat % 4 == 0
    assert tm.tick_to_sec(lead.first_beat * 192) == pytest.approx(g.beats[g.downbeats[0]] + lead.pad_seconds,
                                                                abs=1e-3)


def test_deterministic(steady):
    _, y = steady
    a, b = beat_grid(y, SR), beat_grid(y, SR)
    assert np.array_equal(a.beats, b.beats) and np.array_equal(a.downbeats, b.downbeats) and a.stats == b.stats


def test_silence_has_no_evidence():
    with pytest.raises(InputError, match="no confident drum evidence"):  # the song's, not a bug: exit 2
        beat_grid(np.zeros(SR * 20, dtype=np.float32), SR)


def test_an_envelope_shorter_than_its_kernels_is_no_shape_error():
    """Audio under a second gives an onset envelope shorter than the 1-s trend kernel (and, under a tenth of one,
    than the smoothing kernel); numpy's mode "same" returns the longer of the two, which broke the subtraction."""
    rng = np.random.default_rng(0)
    for n in (5, 30, 99):
        env = np.abs(rng.standard_normal(n))
        assert len(B._smooth(env, 2.0)) == n and np.isfinite(B._autocorrelation(env, 100.0, 270)).all()
        assert BPM_RANGE[0] <= estimate_tempo(env, 100.0) < BPM_RANGE[1]
    env = np.abs(rng.standard_normal(500))  # as long as the kernels or longer: numpy's "same" exactly
    for k in (np.ones(100) / 100, np.ones(13) / 13):
        assert np.array_equal(B._same(env, k), np.convolve(env, k, mode="same"))


def test_robust_line_and_loess_ignore_outliers():
    x = np.arange(100, dtype=float)
    y = 0.5 + 0.42 * x
    y_bad = y.copy()
    y_bad[::10] += 0.05  # a flam every 10 beats
    a, b, _ = robust_line(x, y_bad, np.ones(100))
    assert a == pytest.approx(0.5, abs=1e-6) and b == pytest.approx(0.42, abs=1e-8)
    dev = 0.02 * np.sin(x / 8)
    w = np.ones(100)
    w[:30] = 0  # no evidence in the first 30 beats
    noisy = dev.copy()
    noisy[50] += 0.05
    fit, support = loess(np.where(w > 0, noisy, np.nan), w)
    assert np.max(np.abs(fit[35:95] - dev[35:95])) < 0.002
    assert np.all(fit[:24] == 0) and np.all(support[:24] == 0) and support[60] == pytest.approx(1.0)


def test_track_beats_follows_the_activation():
    fps = 100.0
    t = np.cumsum(np.full(80, 0.5) * np.linspace(1.0, 0.9, 80))  # beats speeding up by 10 %
    act = np.zeros(int((t[-1] + 1) * fps))
    act[np.round(t * fps).astype(int)] = 1.0
    out = track_beats(act, fps, 0.475)
    assert np.max(np.abs(nearest(out, t) - t)) <= 0.011
    assert abs(len(out[(out > t[0] - 0.1) & (out < t[-1] + 0.1)]) - len(t)) == 0


def test_features_reject_nothing_and_accept_stereo(steady):
    _, y = steady
    f = onset_features(np.stack([y, y]), SR)
    assert isinstance(f, OnsetFeatures)
    assert f.fps == pytest.approx(SR / 128) and f.duration == pytest.approx(60.0, abs=0.01)
    assert np.allclose(f.env, onset_features(y, SR).env)


# ------------------------------------------------------------------------------------------------ the fold range

FAST = 60 / 198  # a 198 BPM beat
DOUBLED = (2 * BPM_RANGE[0], 2 * BPM_RANGE[1])  # assemble's second pass: (170, 370)


@pytest.fixture(scope="module")
def fast():
    """198 BPM: kick, snare and hat on every other beat, a soft hat (a tenth as loud) on the beats between, so a
    window's autocorrelation clearly prefers 99 BPM inside the default range (margin 0.58 there)."""
    truth = 0.4 + np.arange(int(58 / FAST)) * FAST
    y = drums(truth[::2], 60.0) + 0.1 * drums(truth[1::2], 60.0, kick_phase=9, snare_phase=9, seed=1)
    return truth, y, onset_features(y, SR)


def test_bpm_range_reaches_every_fold(fast):
    """A hinted 198 BPM is not pulled back to 99 by the tracker's windows when the range is the doubled one; with the
    default range the windows fold it to 99 and the tracker's 99 BPM beats win (the fold assemble's second pass
    avoids). Without a hint, the start line's autocorrelation tempo folds into the range given."""
    truth, y, f = fast
    g = beat_grid(y, SR, bpm=198.0, bpm_range=DOUBLED, features=f)
    assert g.bpm == pytest.approx(198.0, abs=0.1) and g.stats["start"]["grid"] == "line"
    assert g.stats["start"]["tracker_tempo_changes"] == [] and g.stats["tempo_check"] == []
    assert spread_ms(g.beats, truth)[1] < 2.0  # on every beat of the 198, not every other one
    folded = beat_grid(y, SR, bpm=198.0, features=f)  # the hint with the default range
    assert folded.bpm == pytest.approx(99.0, abs=0.1) and folded.stats["start"]["grid"] == "tracker"
    kept = beat_grid(y, SR, bpm=198.0, features=f, keep_line=True)  # keep_line: the tracker never replaces the line
    assert kept.bpm == pytest.approx(198.0, abs=0.1) and kept.stats["start"]["grid"] == "line"
    assert kept.stats["start"]["tracker_confident_share"] == folded.stats["start"]["tracker_confident_share"]
    assert len(folded.stats["start"]["tracker_tempo_changes"]) == 9  # every window at 99
    assert beat_grid(y, SR, features=f).bpm == pytest.approx(99.0, abs=0.1)  # the defaults: 99
    assert beat_grid(y, SR, bpm_range=DOUBLED, features=f).bpm == pytest.approx(198.0, abs=0.1)  # no hint
    assert estimate_tempo(f.env, f.fps, DOUBLED) == pytest.approx(198.0, abs=0.3)
    assert estimate_tempo(f.env, f.fps) == pytest.approx(99.0, abs=0.3)
    # each fold on its own: the windows, the local periods and the tempo check
    assert {round(b) for _, _, b, _ in window_tempi(f.env, f.fps, lambda s, e: FAST, bpm_range=DOUBLED)} == {198}
    assert {round(b) for _, _, b, m in window_tempi(f.env, f.fps, lambda s, e: FAST) if m > 0.5} == {99}
    assert local_periods(f.env, f.fps, FAST, DOUBLED) == (FAST, [])
    assert len(local_periods(f.env, f.fps, FAST)[1]) == 9
    onset_beats = g.beats - g.stats["onset_to_beat_ms"] / 1000
    assert missed_tempo_changes(f, onset_beats, DOUBLED) == []
    assert all(round(bpm) == 99 for _, _, bpm, _ in missed_tempo_changes(f, onset_beats))
    assert len(missed_tempo_changes(f, onset_beats)) == 9
    with pytest.raises(ValueError, match="bpm_range"):
        beat_grid(y, SR, features=f, bpm_range=(185.0, 85.0))


def test_the_windows_estimate_inside_the_range():
    """Pulses at 120 and 180 BPM at once: the best tempo in [85, 185) is 120, in [170, 370) 180, which no octave of
    120 reaches. So a window folded into (170, 370) reads 180 against a 180 reference, not 240."""
    fps = SR / 128
    env = np.zeros(int(60 * fps))
    env[np.round(np.arange(1, 59, 60 / 120) * fps).astype(int)] += 1.0
    env[np.round(np.arange(1, 59, 60 / 180) * fps).astype(int)] += 0.7
    assert estimate_tempo(env, fps) == pytest.approx(120.0, abs=0.3)
    assert estimate_tempo(env, fps, DOUBLED) == pytest.approx(180.0, abs=0.3)
    assert {round(b) for _, _, b, _ in window_tempi(env, fps, lambda s, e: 60 / 180, bpm_range=DOUBLED)} == {180}


def test_the_default_range_changes_nothing(steady):
    """The default range is BPM_RANGE, and every result of the default path is the same as passing it."""
    _, y = steady
    f = onset_features(y, SR)
    a, b = beat_grid(y, SR, features=f), beat_grid(y, SR, features=f, bpm_range=BPM_RANGE)
    assert np.array_equal(a.beats, b.beats) and np.array_equal(a.downbeats, b.downbeats) and a.stats == b.stats
    assert a.bpm == pytest.approx(120.0, abs=0.05) and BPM_RANGE == (85.0, 185.0)


def skank(seed=0):
    """198 BPM: a kick on every beat, a loud snare on every "and" (a fast power-metal beat). The snares are the
    loudest 8ths, so a grid at 198 BPM puts its lines on them."""
    rng = np.random.default_rng(seed)
    truth = 0.4 + np.arange(int(58 / FAST)) * FAST
    y = np.zeros(int(60.0 * SR))
    t = np.arange(int(0.12 * SR)) / SR
    kick = np.sin(2 * np.pi * 55 * t) * np.exp(-t / 0.05)
    snare = (0.5 * np.sin(2 * np.pi * 190 * t) + 0.8 * rng.standard_normal(len(t))) * np.exp(-t / 0.04)
    for b in truth:
        for at, hit in ((b, kick), (b + FAST / 2, snare)):
            i = int(round(at * SR))
            y[i:i + len(t)] += hit
    y += rng.standard_normal(len(y)) * 1e-3
    return truth, (0.4 * y).astype(np.float32)


def test_the_half_beat_test_puts_the_lines_on_the_kick(steady):
    """On the fast beat the grid's lines fall on the snares; half_beat moves them half a beat later, onto the
    kicks, and says so. On a rock beat (kick and snare on the beats, hats between) nothing moves."""
    truth, y = skank()
    f = onset_features(y, SR)
    plain = beat_grid(y, SR, bpm=198.0, bpm_range=DOUBLED, features=f)
    moved = beat_grid(y, SR, bpm=198.0, bpm_range=DOUBLED, features=f, half_beat=True)
    assert abs(spread_ms(plain.beats, truth)[0]) > 100  # on the "and"s
    assert abs(spread_ms(moved.beats, truth)[0]) < 30 and spread_ms(moved.beats, truth)[1] < 5
    hb = moved.stats["half_beat"]
    assert hb["shifted"] and hb["ratio"] > HALF_BEAT_SHIFT and not hb["unsure"] and "half_beat" not in plain.stats
    assert moved.bpm == pytest.approx(198.0, abs=0.1) and len(moved.downbeats)
    # the downbeats are found on the moved beats with their own evidence, not the mask of the beats before the move
    onset = moved.beats - moved.stats["onset_to_beat_ms"] / 1000  # (nothing trimmed here)
    fresh = local_beats(f, onset).confident
    assert hb["confident_after"] == round(float(fresh.mean()), 4) != moved.stats["evidence"]["confident_share"]
    phase = bar_phase(f, onset, fresh)[0]
    assert moved.stats["downbeats"]["phase"] == phase and np.array_equal(moved.downbeats,
                                                                         np.arange(phase, len(moved.beats), 4))
    _, rock = steady
    g = beat_grid(rock, SR, half_beat=True)
    assert not g.stats["half_beat"]["shifted"] and np.array_equal(g.beats, beat_grid(rock, SR).beats)
    # the test itself, and the shift's geometry
    beats = np.arange(1.0, 20.0, 0.5)
    k = np.zeros(4000)
    k[np.round((beats[:-1] + 0.25) * 100).astype(int)] = 1.0
    feats = OnsetFeatures(100.0, np.zeros(4000), np.zeros(4000), k, np.zeros(4000))
    assert half_beat_phase(feats, beats, np.ones(len(beats), bool))[0]
    assert not half_beat_phase(OnsetFeatures(100.0, *(np.zeros(4000),) * 2, np.roll(k, -25), np.zeros(4000)),
                               beats, np.ones(len(beats), bool))[0]
    assert np.allclose(shift_half_beat(np.array([0.1, 0.6, 1.1]), 1.3), [0.35, 0.85])
    assert np.allclose(shift_half_beat(np.array([0.3, 0.8, 1.3]), 2.0), [0.05, 0.55, 1.05, 1.55])


@pytest.mark.parametrize("mids, shifted, unsure", [(0.5, False, False), (0.98, False, True), (1.02, False, True),
                                                   (1.3, True, False)])
def test_the_half_beat_test_needs_a_margin(mids, shifted, unsure):
    """The beats move only when the midpoints carry more than HALF_BEAT_SHIFT (1.25) times the lines' kick: a double
    kick on every 8th (about even, 0.98x or 1.02x) moves nothing and is flagged unsure; 1.3x moves."""
    beats = np.arange(1.0, 20.0, 0.5)
    k = np.zeros(4000)
    k[np.round(beats * 100).astype(int)] = 1.0
    k[np.round((beats[:-1] + 0.25) * 100).astype(int)] = mids
    feats = OnsetFeatures(100.0, np.zeros(4000), np.zeros(4000), k, np.zeros(4000))
    shift, stats = half_beat_phase(feats, beats, np.ones(len(beats), bool))
    assert (shift, stats["shifted"], stats["unsure"]) == (shifted, shifted, unsure)
    assert stats["ratio"] == pytest.approx(mids)



# ------------------------------------------------------------------------------------------------ external downbeats

def test_downbeat_vote_counts_the_beats_the_downbeats_fall_on():
    """Each downbeat votes for its nearest beat within a quarter of the local beat period; the phase is the one
    most votes fall on, the margin its lead over the next one per vote, a tie goes to the lower phase."""
    rng = np.random.default_rng(3)
    beats = 0.5 + np.arange(64) * 0.3                                   # 200 BPM
    on2 = beats[2::4] + rng.uniform(-0.03, 0.03, 16)                    # another tracker's jitter
    assert downbeat_vote(beats, on2) == (2, 1.0, [0, 0, 16, 0], 16)
    stray = beats[[1, 5, 9]] + 0.1                                      # a third of a beat off: no vote
    two = beats[[0, 4]] + 0.07                                          # within a quarter: votes for phase 0
    assert downbeat_vote(beats, np.concatenate([on2, stray, two])) == (2, round(14 / 18, 4), [2, 0, 16, 0], 18)
    assert downbeat_vote(beats, beats[[1, 3, 5, 7]]) == (1, 0.0, [0, 2, 0, 2], 4)        # a tie
    for none in (beats[:-1:4] + 0.15, np.array([])):                                     # midpoints, nothing
        assert downbeat_vote(beats, none) == (None, 0.0, [0, 0, 0, 0], 0)
    # the window follows the local period: 0.09 s votes where beats are 0.4 s apart, not where they are 0.3 s
    slow = np.concatenate([beats[:32], beats[31] + 0.4 * np.arange(1, 33)])
    assert downbeat_vote(slow, slow[[8, 48]] + 0.09) == (0, 1.0, [1, 0, 0, 0], 1)


def test_allin1s_downbeats_set_the_bar_on_a_kick_on_every_beat():
    """A kick on every beat gives the kick's bar phase no margin (a guess, flagged); downbeats from another tracker
    (allin1's, at half the grid's rate as on the fast stress songs: every 8th beat) set it, here two beats from the
    kick's guess. The kick's own phase stays in the stats."""
    _, y = skank()
    g = beat_grid(y, SR, bpm=198.0, bpm_range=DOUBLED, half_beat=True)
    kick = g.stats["downbeats"]
    assert kick["uncertain"] and kick["margin"] < DOWNBEAT_MIN_MARGIN and kick["source"] == "kick"
    want = (kick["phase"] + 2) % 4
    allin1 = g.beats[want::8] + 0.012
    out = with_downbeats(g, allin1)
    assert np.array_equal(out.downbeats, np.arange(want, len(g.beats), 4))
    db = out.stats["downbeats"]
    assert (db["phase"], db["margin"], db["uncertain"], db["source"]) == (want, 1.0, False, "allin1")
    assert db["kick"] == {"phase": kick["phase"], "margin": kick["margin"], "uncertain": True}
    assert db["vote"] == {"counts": [len(allin1) if p == want else 0 for p in range(4)], "given": len(allin1),
                          "voting": len(allin1), "window": 0.25}
    assert db["scores"] == kick["scores"] and db["windows"] == kick["windows"]
    assert np.array_equal(out.beats, g.beats) and out.mode == g.mode and g.stats["downbeats"] is kick  # a copy


def test_allin1s_downbeats_on_an_ordinary_song(steady):
    """On a rock beat the kick's phase is sure, and downbeats that agree keep it; with none, or none near a beat,
    the grid keeps the kick's phase (the same grid when none are given)."""
    truth, y = steady
    g = beat_grid(y, SR)
    kick = int(np.argmin(np.abs(g.beats - truth[0]))) % 4  # the kick is on truth[0]
    assert g.stats["downbeats"]["phase"] == kick and not g.stats["downbeats"]["uncertain"]
    out = with_downbeats(g, truth[0::4] - 0.02)
    assert np.array_equal(out.downbeats, g.downbeats) and out.stats["downbeats"]["source"] == "allin1"
    assert out.stats["downbeats"]["phase"] == out.stats["downbeats"]["kick"]["phase"] == kick
    assert out.stats["downbeats"]["margin"] == 1.0 and not out.stats["downbeats"]["uncertain"]
    assert with_downbeats(g, None) is g
    away = with_downbeats(g, truth[0::4] + 0.25)                         # every one half a beat off
    assert np.array_equal(away.downbeats, g.downbeats) and away.stats["downbeats"]["source"] == "kick"
    assert away.stats["downbeats"]["vote"]["voting"] == 0 and "kick" not in away.stats["downbeats"]
    p = 1 if kick != 1 else 3                                             # a kick phase that is not 0 ...
    g1 = BeatGrid(g.beats, np.arange(p, len(g.beats), 4), g.mode,
                  {**g.stats, "downbeats": {**g.stats["downbeats"], "phase": p}})
    away1 = with_downbeats(g1, truth[0::4] + 0.25)                       # ... kept when no downbeat votes
    assert np.array_equal(away1.downbeats, g1.downbeats) and away1.stats["downbeats"]["phase"] == p


def test_a_split_vote_keeps_a_sure_kick_phase(steady):
    """Downbeats split between the sure kick's phase and another (here one more on the other, a margin of 1/9)
    keep the kick's phase, recorded as a split; split between two other phases, the vote's top phase is taken and
    flagged."""
    truth, y = steady
    g = beat_grid(y, SR)
    kick, other = g.stats["downbeats"]["phase"], (g.stats["downbeats"]["phase"] + 2) % 4
    assert not g.stats["downbeats"]["uncertain"]
    times = np.sort(np.concatenate([g.beats[other::4][:5], g.beats[kick::4][1:5]]))
    out = with_downbeats(g, times)
    db = out.stats["downbeats"]
    assert np.array_equal(out.downbeats, g.downbeats) and db["source"] == "kick" and not db["uncertain"]
    assert db["phase"] == kick and db["vote"]["phase"] == other and db["vote"]["margin"] == round(1 / 9, 4)
    assert db["vote"]["why"] == (f"split between beats {other} and {kick} of the bar, one of them the sure kick's: "
                                 "the kick's phase")
    a, b = (kick + 1) % 4, (kick + 3) % 4
    times = np.sort(np.concatenate([g.beats[a::4][:5], g.beats[b::4][:4]]))
    out = with_downbeats(g, times)
    db = out.stats["downbeats"]
    assert (db["phase"], db["source"], db["uncertain"]) == (a, "allin1", True)
    assert np.array_equal(out.downbeats, np.arange(a, len(g.beats), 4))


@pytest.mark.parametrize("sure, on_kick, on_other, want", [
    (False, 22, 28, 2),   # a split vote (margin 0.12) against an unsure kick (a kick on every beat): the vote's
    (True, 16, 34, 2),    # a clear vote (margin 0.36) against a sure kick: the vote's
    (True, 17, 23, 2),    # margin 0.15, DOWNBEAT_MIN_MARGIN itself: not a split, the vote's
    (True, 43, 57, 0),    # margin 0.14: a split holding the sure kick's phase, the kick's
])
def test_a_split_vote_keeps_only_a_sure_kick_and_only_under_the_threshold(sure, on_kick, on_other, want):
    """The split rule's two conditions on a made-up 200 BPM grid with its kick on phase 0: the kick's phase is
    kept against a vote whose two top phases hold it only when the kick is sure and the vote's margin is under
    DOWNBEAT_MIN_MARGIN (0.15); otherwise the vote's phase (2) is taken, flagged when its margin is under 0.15."""
    beats = 0.5 + np.arange(400) * 0.3
    kick = {"phase": 0, "margin": 0.4 if sure else 0.02, "uncertain": not sure, "source": "kick"}
    g = BeatGrid(beats, np.arange(0, 400, 4), "fixed", {"downbeats": kick})
    times = np.sort(np.concatenate([beats[0::4][:on_kick], beats[2::4][:on_other]]))
    margin = round((on_other - on_kick) / (on_kick + on_other), 4)
    assert DOWNBEAT_MIN_MARGIN == 0.15 and downbeat_vote(beats, times)[:2] == (2, margin)
    db = with_downbeats(g, times).stats["downbeats"]
    assert (db["phase"], db["source"]) == ((0, "kick") if want == 0 else (2, "allin1"))
    assert db["uncertain"] is (not sure if want == 0 else margin < 0.15)
    assert np.array_equal(with_downbeats(g, times).downbeats, np.arange(want, 400, 4))
