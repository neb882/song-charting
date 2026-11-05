"""The beat grid on synthetic drum tracks: kick, snare and hat hits placed on known beats."""
import numpy as np
import pytest

import songcharter.beatgrid as B
from songcharter.beatgrid import (BPM_RANGE, BeatGrid, OnsetFeatures, beat_grid, estimate_tempo, local_beats,
                                  local_periods, loess, mel_filterbank, missed_tempo_changes, onset_features,
                                  onset_phase, onset_times, robust_line, track_beats, window_tempi)
from songcharter.errors import InputError
from songcharter.tempo import TempoMap, plan_lead_in

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
