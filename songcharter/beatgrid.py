"""The song's beat grid, measured from the drums.

Every chart is timed by its tempo map, and the tempo map is built from these beats, so they decide where every note
lands. The grid comes from the drum stem (or the mix when the song has no drums) in four steps:

  1. **Start grid.** A straight line of beats: the (bpm, first beat) hints if given, otherwise the tempo from the onset
     envelope's autocorrelation folded into [85, 185) BPM (`bpm_range`; assemble's second pass at twice the tempo
     gives [170, 370)) and the phase from a comb fit. A beat tracker (dynamic
     programming on the same envelope, Ellis-style) runs as well, and when its beats find clearly more drum evidence
     than the line, no straight line fits the song (a band without a click) and the tracker's beats are the start.
     The tracker prefers the line's period except in 20-s windows whose own autocorrelation tempo clearly differs
     (local_periods: Take Me Out's 142 BPM intro in a 104.6 BPM song); stats["tempo_check"] lists any window whose
     tempo the final grid still misses. The full product passes Beat This! beats as `start=`; `track_beats` also
     decodes its activations.
  2. **Local beats.** For each grid beat, the strongest onset-envelope peak within +-60 ms, refined by a parabola,
     with a confidence: how clear the peak is, how strong against the song's drum hits, and how loud the stem is.
  3. **The grid.** A robust straight line through the confident local beats is the click grid. Free mode follows
     the drummer: the local beats' deviations from that line, LOESS-smoothed over about 8 beats, with beats that
     lack evidence (a drumless intro) taken from the line and beat-to-beat tempo changes kept small. Given a second
     stem (`secondary`: the guitar), those beats follow its onsets instead wherever they hold a clear 8th/16th
     phase, with the stem's lag behind the drums measured on the same song (onset_phase); stats["secondary"] says
     which drumless stretches it timed. Free is the default when at least 60 % of beats have confident evidence:
     following a live drummer costs nothing in play. (DESIGN.md's p95-drift click test is only reported, as
     stats["drift_ms"].)
  4. **Downbeats.** 4/4 for v1, in the bar phase that puts the most kick (40-160 Hz, against the snare's 150-400 Hz)
     on beat 1. A small margin (kick on 1 and 3 alike) is flagged in stats["downbeats"]["uncertain"].

The onset envelope is librosa's `onset_strength` (mel spectral flux in dB, 2048-point frames, hop 128 at 22050 Hz),
computed at the input rate with the same frames in seconds. Its peaks sit after the beat lines of human charts: on
the reference set's drum stems (All the Small Things, Take Me Out) the human beats are 24.1 and 20.4 ms (median)
before these peaks. An earlier measurement of 14-18 ms on the same songs used a peak picker that fires on the
envelope's rising edge, about 6-7 ms before the peak (re-run here with that picker: 18.2 and 13.4 ms). So beats are
moved by `onset_to_beat_ms` = -22 ms from the peaks; the constant belongs to this envelope and this peak definition.

The output feeds the tempo map directly:

    grid = beat_grid(drums, 44100)
    lead = plan_lead_in(grid.beats, grid.downbeats, 44100, duration=len_s)
    tm = TempoMap.from_beats(lead.beats, bars=lead.bars, tolerance=0.003)
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .errors import InputError

REF_RATE = 22050           # the onset envelope's reference rate: librosa's default and the calibration's detector
REF_N_FFT = 2048           # ~93 ms frames
REF_HOP = 128              # ~5.8 ms hop
N_MELS = 128
KICK_BAND = (40.0, 160.0)
SNARE_BAND = (150.0, 400.0)
BPM_RANGE = (85.0, 185.0)  # the first pass's fold, one octave; assemble doubles a grid too slow for its notes (2.3)
ONSET_TO_BEAT_MS = -22.0   # human beat lines sit this far from the envelope peaks (see the module docstring)
SEARCH_S = 0.060           # local beats: a peak within this distance of the grid beat
MIN_CONFIDENCE = 0.5       # confident local evidence
FREE_SHARE = 0.60          # free mode when at least this share of beats has confident evidence
LOESS_HALF_WIDTH = 4       # beats on each side: a window of about 8 beats
MAX_TEMPO_STEP = 0.02      # largest beat-to-beat change of the beat period in free mode (2 %, ~3 BPM at 142)
TRACKER_MARGIN = 0.10      # the tracker replaces the straight start line when it finds this much more evidence
LOCAL_TEMPO_WINDOW_S = 20.0  # the tracker's local tempo: the autocorrelation of 20-s windows, ...
LOCAL_TEMPO_HOP_S = 5.0    # ... every 5 s, ...
LOCAL_TEMPO_CHANGE = 0.10  # ... kept where it differs from the global tempo by more than 10 % ...
LOCAL_TEMPO_MARGIN = 0.5   # ... and scores this much higher than the global period there
DOWNBEAT_MIN_MARGIN = 0.15  # below this bar-phase margin the downbeats are flagged for review
SECONDARY_DELTA = 0.12     # a second stem's onsets: peaks this far above the normalised envelope's local mean
SECONDARY_HALF_WIDTH = 4   # their 8th and 16th phase is measured over +-4 beats around each beat, ...
SECONDARY_MIN_ONSETS = 8   # ... from at least 8 onsets, ...
SECONDARY_MIN_SCORE = 0.4  # ... and times a beat the drums leave without evidence from this phase agreement up,
SECONDARY_MIN_EIGHTH = 0.3  # ... with at least this much of it at the 8th level
SECONDARY_MIN_CALIBRATION = 32  # beats with drum support and onsets needed to measure the stem's lag, ...
SECONDARY_MIN_FOLLOW = 0.2  # ... and their mean phase agreement at that lag: the stem follows the drums


@dataclass
class OnsetFeatures:
    """Frame-rate features of one audio signal. Frame i is centred at i / fps seconds."""
    fps: float
    env: np.ndarray        # onset strength (mel spectral flux in dB), librosa's onset_strength equivalent
    level_db: np.ndarray   # frame power in dB (mel bands up to 11025 Hz), for gating quiet passages
    kick: np.ndarray       # power in KICK_BAND
    snare: np.ndarray      # power in SNARE_BAND

    @property
    def duration(self) -> float:
        return len(self.env) / self.fps


@dataclass
class LocalBeats:
    """The drum evidence at each grid beat."""
    times: np.ndarray       # refined envelope-peak time (s), NaN where the window holds no peak
    confidence: np.ndarray  # 0-1; MIN_CONFIDENCE and up counts as evidence
    strength: np.ndarray    # peak height over the song's typical beat peak
    contrast: np.ndarray    # peak height over the envelope's local median (+-1 beat)

    @property
    def confident(self) -> np.ndarray:
        return self.confidence >= MIN_CONFIDENCE


@dataclass
class BeatGrid:
    """The grid, and how it was found.

    stats: start (source, tempo and first beat of the start line, the tracker's local tempo windows, each start
    grid's confident share, the grid used), click (the robust line's tempo, first beat and residuals), evidence
    (confident share and count, local peaks against the grid), drift_ms (the smoothed drummer against the line:
    p50, p95, max), mode (and why), free (largest beat-to-beat period change), secondary (given a second stem: its
    lag, calibration, beats timed; in free mode, with or without one, the drumless stretches), tempo_check (windows
    whose tempo the grid misses), downbeats (phase, margin, uncertain, per-phase scores, per 16 bars),
    onset_to_beat_ms. Times in stats are onset times, before the onset_to_beat shift.
    """
    beats: np.ndarray      # beat times, seconds of input audio, strictly increasing
    downbeats: np.ndarray  # indices into beats that start a measure (4/4)
    mode: str              # "free" (follows the drummer) or "click" (one straight line)
    stats: dict = field(default_factory=dict)

    @property
    def bpm(self) -> float:
        return 60.0 / float(np.median(np.diff(self.beats)))


# ---------------------------------------------------------------------------------------------------- features

def _hz_to_mel(f):
    """Slaney mel scale (librosa's default): linear below 1 kHz, logarithmic above."""
    f = np.asarray(f, dtype=np.float64)
    lin = f / (200.0 / 3)
    log = 15.0 + np.log(np.maximum(f, 1e-9) / 1000.0) / (np.log(6.4) / 27.0)
    return np.where(f >= 1000.0, log, lin)


def _mel_to_hz(m):
    m = np.asarray(m, dtype=np.float64)
    lin = m * (200.0 / 3)
    log = 1000.0 * np.exp((np.log(6.4) / 27.0) * (m - 15.0))
    return np.where(m >= 15.0, log, lin)


def mel_filterbank(sample_rate: int, n_fft: int, n_mels: int = N_MELS, fmax: float = REF_RATE / 2) -> np.ndarray:
    """Slaney-normalised triangular mel filters, shape (n_mels, n_fft // 2 + 1), as librosa.filters.mel."""
    freqs = np.fft.rfftfreq(n_fft, 1.0 / sample_rate)
    edges = _mel_to_hz(np.linspace(_hz_to_mel(0.0), _hz_to_mel(fmax), n_mels + 2))
    fdiff = np.diff(edges)
    ramps = edges[:, None] - freqs[None, :]
    lower = -ramps[:-2] / fdiff[:-1, None]
    upper = ramps[2:] / fdiff[1:, None]
    w = np.maximum(0.0, np.minimum(lower, upper))
    return w * (2.0 / (edges[2:] - edges[:-2]))[:, None]


def onset_features(audio: np.ndarray, sample_rate: int, block_frames: int = 2048) -> OnsetFeatures:
    """Onset envelope and band powers of `audio` (shape (channels, samples) or (samples,); mixed to mono).

    The frames match librosa's at 22050 Hz (2048-point Hann frames, hop 128, centred, zero padded) in seconds, so
    the STFT runs at the input rate with the mel filters stopping at 11025 Hz: the envelope of resampling first.
    """
    y = np.asarray(audio, dtype=np.float32)
    if y.ndim == 2:
        y = y.mean(axis=0)
    scale = sample_rate / REF_RATE
    hop = max(1, int(round(REF_HOP * scale)))
    n_fft = int(round(REF_N_FFT * scale / 2)) * 2
    fps = sample_rate / hop
    n_frames = 1 + len(y) // hop
    pad = np.zeros(len(y) + n_fft + hop, dtype=np.float32)
    pad[n_fft // 2:n_fft // 2 + len(y)] = y
    window = (0.5 - 0.5 * np.cos(2 * np.pi * np.arange(n_fft) / n_fft)).astype(np.float32)  # periodic Hann
    mel = mel_filterbank(sample_rate, n_fft)
    used = np.flatnonzero(mel.any(axis=0))
    lo, hi = used[0], used[-1] + 1
    mel = mel[:, lo:hi].astype(np.float32)
    freqs = np.fft.rfftfreq(n_fft, 1.0 / sample_rate)
    kick_bins = (freqs >= KICK_BAND[0]) & (freqs < KICK_BAND[1])
    snare_bins = (freqs >= SNARE_BAND[0]) & (freqs < SNARE_BAND[1])
    power_scale = np.float32((REF_N_FFT / n_fft) ** 2)  # same magnitudes as the 22050 Hz frames
    mel_power = np.empty((N_MELS, n_frames), dtype=np.float32)
    kick = np.empty(n_frames, dtype=np.float64)
    snare = np.empty(n_frames, dtype=np.float64)
    frames = np.lib.stride_tricks.sliding_window_view(pad, n_fft)[::hop]
    for s in range(0, n_frames, block_frames):
        e = min(n_frames, s + block_frames)
        p = np.abs(np.fft.rfft(frames[s:e] * window, axis=1)) ** 2 * power_scale
        mel_power[:, s:e] = (p[:, lo:hi] @ mel.T).T
        kick[s:e] = p[:, kick_bins].sum(axis=1)
        snare[s:e] = p[:, snare_bins].sum(axis=1)
    # power_to_db(ref=1, amin=1e-10, top_db=80), then the positive first difference averaged over bands
    db = 10.0 * np.log10(np.maximum(mel_power, 1e-10))
    db = np.maximum(db, db.max() - 80.0)
    flux = np.maximum(0.0, db[:, 1:] - db[:, :-1]).mean(axis=0)
    # librosa shifts by lag + n_fft // (2 hop) frames, so a peak sits at its attack rather than its frame's start
    lag = 1 + n_fft // (2 * hop)
    env = np.concatenate([np.zeros(lag), flux])[:n_frames].astype(np.float64)
    level = 10.0 * np.log10(np.maximum(mel_power.sum(axis=0, dtype=np.float64), 1e-10))
    return OnsetFeatures(fps, env, level, kick, snare)


def _interp(x: np.ndarray, pos) -> np.ndarray:
    """x at fractional frame positions (linear; 0 outside)."""
    return np.interp(pos, np.arange(len(x)), x, left=0.0, right=0.0)


def _same(x: np.ndarray, k: np.ndarray) -> np.ndarray:
    """np.convolve(x, k, mode="same"), but as long as x also when the kernel is longer (numpy then returns the
    kernel's length): an envelope shorter than a kernel, from audio under a second, is no shape error."""
    return np.convolve(x, k)[(len(k) - 1) // 2:][:len(x)]


def _smooth(x: np.ndarray, sigma_frames: float) -> np.ndarray:
    r = int(np.ceil(3 * sigma_frames))
    k = np.exp(-0.5 * (np.arange(-r, r + 1) / sigma_frames) ** 2)
    return _same(x, k / k.sum())


# ---------------------------------------------------------------------------------------------------- start grid

def _autocorrelation(env: np.ndarray, fps: float, max_lag: int) -> np.ndarray:
    """The onset envelope's autocorrelation up to max_lag frames, normalised to 1 at lag 0."""
    x = _smooth(env, 2.0) - _same(env, np.ones(int(fps)) / int(fps))  # drop the loudness trend
    n = len(x)
    nfft = 1 << int(np.ceil(np.log2(2 * n)))
    ac = np.fft.irfft(np.abs(np.fft.rfft(x, nfft)) ** 2, nfft)[:max_lag]
    return ac / (ac[0] + 1e-12)


def _tempo_score(ac: np.ndarray, lag) -> np.ndarray:
    """Each beat period's score (lag in frames): the autocorrelation there plus half that at twice the period."""
    return _interp(ac, lag) + 0.5 * _interp(ac, 2 * np.asarray(lag))


def estimate_tempo(env: np.ndarray, fps: float, bpm_range: tuple[float, float] = BPM_RANGE) -> float:
    """Tempo (BPM) in [lo, hi) from the onset envelope's autocorrelation.

    Each candidate tempo scores the autocorrelation at its beat period plus half that at twice the period, so a
    half-time pulse (kick and snare a bar apart) still votes for the beat level, and pulses faster than the range
    land on half their rate. The winner's period is then refined from the parabolic peaks of the autocorrelation at
    one to four periods, weighted by their height (the frame grid alone would be 0.7 % coarse at 142 BPM).
    """
    lo, hi = bpm_range
    ac = _autocorrelation(env, fps, int(4.5 * 60 * fps / lo))
    bpms = np.arange(lo, hi, 0.05)
    score = _tempo_score(ac, 60.0 * fps / bpms)
    period = 60.0 * fps / float(bpms[int(np.argmax(score))])
    num = den = 0.0
    for m in (1, 2, 3, 4):
        c = int(round(m * period))
        if c < 3 or c + 3 >= len(ac):
            break
        i = c - 2 + int(np.argmax(ac[c - 2:c + 3]))
        y0, y1, y2 = ac[i - 1:i + 2]
        curv = y0 - 2 * y1 + y2
        peak = i + (0.5 * (y0 - y2) / curv if curv < 0 else 0.0)
        w = max(float(y1), 0.0)
        num, den = num + w * m * peak, den + w * m * m
    if den > 0:
        period = num / den
    bpm = 60.0 * fps / period
    while bpm < lo:
        bpm *= 2
    while bpm >= hi:
        bpm /= 2
    return float(bpm)


def window_tempi(env: np.ndarray, fps: float, reference, window_s: float = LOCAL_TEMPO_WINDOW_S,
                 hop_s: float = LOCAL_TEMPO_HOP_S, bpm_range: tuple[float, float] = BPM_RANGE
                 ) -> list[tuple[int, int, float, float]]:
    """(first frame, end frame, bpm, margin) of the autocorrelation tempo (estimate_tempo) of each window_s window,
    every hop_s, against a reference period.

    reference(first, end) gives the reference beat period (s) of a window. The bpm is the octave inside bpm_range
    nearest the reference tempo, so a 150 BPM section stays at 150 against 104.6 and a half-time window never leaves
    the reference level; the margin is the window's best tempo score in bpm_range minus the reference period's.
    """
    lo, hi = bpm_range
    n = len(env)
    w, h = int(round(window_s * fps)), int(round(hop_s * fps))
    out = []
    for s in range(0, max(n - w, 0) + 1, h):
        e = min(n, s + w)
        ref = float(reference(s, e))
        ac = _autocorrelation(env[s:e], fps, int(4.5 * 60 * fps / lo))
        bpm = estimate_tempo(env[s:e], fps, bpm_range)
        octaves = [bpm * 2.0 ** k for k in range(-2, 3) if lo <= bpm * 2.0 ** k < hi]
        bpm = min(octaves, key=lambda b: abs(np.log(b * ref / 60.0)))
        margin = float(_tempo_score(ac, 60.0 * fps / np.arange(lo, hi, 0.05)).max() - _tempo_score(ac, ref * fps))
        out.append((s, e, float(bpm), margin))
    return out


def local_periods(env: np.ndarray, fps: float, period: float, bpm_range: tuple[float, float] = BPM_RANGE
                  ) -> tuple[float | np.ndarray, list[tuple]]:
    """The tracker's beat period per frame (s): the global period, except where the song clearly changes tempo.

    A window of window_tempi keeps its own tempo when it differs from the global one by more than LOCAL_TEMPO_CHANGE
    and scores LOCAL_TEMPO_MARGIN above the global period there (Take Me Out's 142 BPM intro against its 104.6 BPM
    song: 0.9-1.3 against -0.3). A neighbour of a kept window joins it on any positive margin when its tempo is
    within 5 % of the kept one's, so a slowing into the new tempo is followed too. Between window centres the period
    runs on a log scale. Returns the global period itself when no window changes it, and the kept windows as
    (start s, end s, bpm). The windows' tempi are folded into bpm_range (window_tempi).
    """
    wins = window_tempi(env, fps, lambda s, e: period, bpm_range=bpm_range)
    bpms = np.array([b for _, _, b, _ in wins])
    margins = np.array([m for _, _, _, m in wins])
    differs = np.abs(np.log(bpms * period / 60.0)) > np.log(1 + LOCAL_TEMPO_CHANGE)
    keep = differs & (margins >= LOCAL_TEMPO_MARGIN)
    grown = keep.any()
    while grown:
        grown = False
        for i in np.flatnonzero(differs & ~keep & (margins > 0)):
            if any(0 <= j < len(keep) and keep[j] and abs(np.log(bpms[i] / bpms[j])) < np.log(1.05)
                   for j in (i - 1, i + 1)):
                keep[i] = grown = True
    if not keep.any():
        return period, []
    centres = np.array([0.5 * (s + e) for s, e, _, _ in wins])
    log_p = np.where(keep, np.log(60.0 / bpms), np.log(period))
    changed = [(round(s / fps, 2), round(e / fps, 2), round(b, 2)) for (s, e, b, _), k in zip(wins, keep) if k]
    return np.exp(np.interp(np.arange(len(env)), centres, log_p)), changed


def missed_tempo_changes(features: OnsetFeatures, beats: np.ndarray, bpm_range: tuple[float, float] = BPM_RANGE
                         ) -> list[tuple[float, float, float, float]]:
    """The windows of window_tempi whose autocorrelation tempo the grid's beats do not follow, as (start s, end s,
    window bpm, grid bpm): it scores LOCAL_TEMPO_MARGIN above the grid's median period there and lies more than
    LOCAL_TEMPO_CHANGE outside the grid's tempi in the window (10th to 90th percentile), so a ritardando the grid
    follows is not flagged. A non-empty list is a tempo change the grid missed (Take Me Out's intro before the
    local periods). The windows' tempi are folded into bpm_range, the grid's own range."""
    fps = features.fps

    def ibis(s: int, e: int) -> np.ndarray:
        b = beats[(beats >= s / fps) & (beats < e / fps)]
        return np.diff(b) if len(b) > 2 else np.diff(beats)
    out = []
    for s, e, bpm, margin in window_tempi(features.env, fps, lambda s, e: float(np.median(ibis(s, e))),
                                          bpm_range=bpm_range):
        slow, fast = 60.0 / np.percentile(ibis(s, e), [90, 10]) * np.array([1 / (1 + LOCAL_TEMPO_CHANGE),
                                                                             1 + LOCAL_TEMPO_CHANGE])
        if margin >= LOCAL_TEMPO_MARGIN and not slow <= bpm <= fast:
            out.append((round(s / fps, 2), round(e / fps, 2), round(bpm, 2),
                        round(60.0 / float(np.median(ibis(s, e))), 2)))
    return out


def fit_comb(env: np.ndarray, fps: float, duration: float, period: float, phase_range: tuple[float, float],
             rel_range: float = 0.004, sigma_s: float = 0.012) -> tuple[float, float]:
    """(period, first beat) of the straight beat line that best covers the onset envelope.

    The comb score is the mean of the smoothed envelope at first + k * period, for the beats inside the audio.
    It searches period * (1 +- rel_range) and first beats in phase_range, coarse to fine.
    """
    es = _smooth(env, sigma_s * fps)
    best = (period, phase_range[0])
    span_p, span_f = rel_range * period, phase_range
    for step_p, step_f in ((span_p / 40, 0.002), (span_p / 400, 0.0005)):
        periods = np.arange(best[0] - span_p, best[0] + span_p + step_p / 2, step_p)
        firsts = np.arange(span_f[0], span_f[1], step_f)
        top = -1.0
        for p in periods:
            k = np.arange(int(np.floor((duration - firsts.min()) / p)) + 1)
            t = firsts[:, None] + k[None, :] * p
            inside = (t >= 0) & (t <= duration)
            s = (_interp(es, t * fps) * inside).sum(axis=1) / np.maximum(inside.sum(axis=1), 1)
            j = int(np.argmax(s))
            if s[j] > top:
                top, best = s[j], (float(p), float(firsts[j]))
        span_p, span_f = step_p * 2, (best[1] - 2 * step_f, best[1] + 2 * step_f)
    return best


def start_line(features: OnsetFeatures, duration: float, bpm: float | None = None,
               first_beat: float | None = None, bpm_range: tuple[float, float] = BPM_RANGE
               ) -> tuple[float, float, str]:
    """(period, first beat, source) of the start grid: refined hints, or autocorrelation tempo (folded into
    bpm_range) and comb phase.

    A bpm hint is trusted to 0.5 % and a first-beat hint to +-60 ms; both are refined on the envelope, since a
    straight line has to stay within the local search window for the whole song. The first beat is the earliest
    beat at or after 0 s unless a first-beat hint says otherwise.
    """
    source = "hints" if bpm or first_beat is not None else "autocorrelation"
    if bpm:
        period, rel = 60.0 / bpm, 0.005
    else:
        period, rel = 60.0 / estimate_tempo(features.env, features.fps, bpm_range), 0.004
    if first_beat is not None:
        phases = (first_beat - SEARCH_S, first_beat + SEARCH_S)
    else:
        phases = (0.0, period)
    period, first = fit_comb(features.env, features.fps, duration, period, phases, rel)
    if first_beat is None:
        first %= period
    return period, first, source


def track_beats(activation: np.ndarray, fps: float, period, tightness: float = 100.0) -> np.ndarray:
    """Beat times (s) by dynamic programming (Ellis 2007, as librosa's beat_track decoder, without trimming).

    activation: any beat activation at fps (the onset envelope now; Beat This! logits in the full product).
    period: the beat period (s), one value or one per frame (local_periods).
    Each beat's score is the activation there plus the best predecessor 0.5-2 periods back, penalised by
    tightness * log(gap / period)^2, so the beats follow tempo changes but prefer the period at that frame.
    """
    n = len(activation)
    taus = np.broadcast_to(np.asarray(period, dtype=np.float64) * fps, (n,))
    sigma = max(float(np.median(taus)) / 32, 0.5)  # librosa's local score: the activation smoothed over a 32nd
    r = int(np.ceil(3 * sigma))
    g = np.exp(-0.5 * (np.arange(-r, r + 1) / sigma) ** 2)
    o = np.convolve(activation / (activation.std() + 1e-12), g / g.sum(), mode="same")
    cum = o.copy()
    back = np.full(n, -1)
    tau = None
    for t in range(1, n):
        if taus[t] != tau:
            tau = taus[t]
            gaps = np.arange(max(1, int(round(0.5 * tau))), int(round(2 * tau)) + 1)
            penalty = -tightness * np.log(gaps / tau) ** 2
        g_t = gaps if t >= gaps[-1] else gaps[gaps <= t]  # gaps ascend, so this is a prefix
        if not len(g_t):
            continue
        cand = cum[t - g_t] + penalty[:len(g_t)]
        j = int(np.argmax(cand))
        cum[t] = o[t] + cand[j]
        back[t] = t - g_t[j]
    tail = np.arange(max(0, n - int(np.ceil(taus[-1]))), n)
    t = int(tail[np.argmax(cum[tail])])
    out = [t]
    while back[t] >= 0:
        t = int(back[t])
        out.append(t)
    return np.array(out[::-1], dtype=np.float64) / fps


# ---------------------------------------------------------------------------------------------------- evidence

def local_beats(features: OnsetFeatures, grid: np.ndarray, window: float = SEARCH_S) -> LocalBeats:
    """The strongest onset-envelope peak within +-window of each grid beat, with its confidence.

    Confidence is the product of three ramps, each 0 to 1:
      * strength: the peak against the song's typical beat peak (the 90th percentile over all beats), full at 15 %,
      * contrast: the peak against the envelope's median over +-1 beat, from 2x (none) to 6x (full),
      * level: the stem's loudness at the peak, from 40 dB (none) to 30 dB (full) below its loud level, so the
        leakage in a drum stem's drumless passages never counts.
    """
    env, fps = features.env, features.fps
    n = len(env)
    K = len(grid)
    times = np.full(K, np.nan)
    peak = np.zeros(K)
    floor = np.zeros(K)
    level = np.full(K, -np.inf)
    period = float(np.median(np.diff(grid))) if K > 1 else 0.5
    w_ctx = max(1, int(round(period * fps)))
    for k, t in enumerate(grid):
        s = max(1, int(np.ceil((t - window) * fps)))
        e = min(n - 1, int(np.floor((t + window) * fps)) + 1)
        if e <= s:
            continue
        seg = env[s:e]
        is_peak = (seg >= env[s - 1:e - 1]) & (seg > env[s + 1:e + 1]) & (seg > 0)
        if not is_peak.any():
            continue
        i = s + int(np.flatnonzero(is_peak)[np.argmax(seg[is_peak])])
        y0, y1, y2 = env[i - 1], env[i], env[i + 1]
        den = y0 - 2 * y1 + y2
        d = float(np.clip(0.5 * (y0 - y2) / den, -0.5, 0.5)) if den < 0 else 0.0
        times[k] = (i + d) / fps
        peak[k] = y1 - 0.25 * (y0 - y2) * d
        c = int(round(t * fps))
        floor[k] = float(np.median(env[max(0, c - w_ctx):c + w_ctx + 1]))
        level[k] = features.level_db[max(0, i - 3):i + 4].max()
    found = ~np.isnan(times)
    ref = float(np.percentile(peak[found], 90)) if found.any() else 1.0
    loud = float(np.percentile(features.level_db, 95))
    strength = peak / (ref + 1e-12)
    contrast = peak / (floor + 0.01 * ref + 1e-12)
    conf = (np.clip(strength / 0.15, 0, 1) * np.clip((contrast - 2.0) / 4.0, 0, 1)
            * np.clip((level - (loud - 40.0)) / 10.0, 0, 1))
    conf[~found] = 0.0
    return LocalBeats(times, conf, strength, contrast)


def robust_line(x: np.ndarray, y: np.ndarray, w: np.ndarray, iterations: int = 10) -> tuple[float, float, float]:
    """(intercept, slope, residual scale) of y = a + b x, by weighted least squares with Tukey bisquare reweighting."""
    x0 = float(np.average(x, weights=w))
    u = np.ones_like(w)
    a = b = scale = 0.0
    for _ in range(iterations):
        ww = w * u
        A = np.stack([np.ones_like(x), x - x0], axis=1) * np.sqrt(ww)[:, None]
        a, b = np.linalg.lstsq(A, y * np.sqrt(ww), rcond=None)[0]
        r = y - a - b * (x - x0)
        scale = max(1.4826 * float(np.median(np.abs(r[w > 0]))), 1e-4)
        z = r / (4.685 * scale)
        u = np.where(np.abs(z) < 1, (1 - z ** 2) ** 2, 0.0)
    return float(a - b * x0), float(b), scale


def loess(y: np.ndarray, w: np.ndarray, half_width: int = LOESS_HALF_WIDTH,
          iterations: int = 3) -> tuple[np.ndarray, np.ndarray]:
    """Robust local-linear LOESS of a series over its index, and each point's support.

    y: values (anything where w == 0); w: prior weights (0 = no evidence). Tricube weights over +-half_width,
    bisquare reweighting against 6 MADs of the residuals. Support is the window's evidence weight relative to a
    full window of weight-1 points (1.0 = full, 0 = nothing within reach). Where support is 0 the fit is 0.
    """
    n = len(y)
    h = int(half_width)
    d = np.arange(-h, h + 1)
    tri = (1 - (np.abs(d) / (h + 1)) ** 3) ** 3
    idx = np.arange(n)[:, None] + d[None, :]
    inside = (idx >= 0) & (idx < n)
    idx = np.clip(idx, 0, n - 1)
    yy = np.where(inside, np.nan_to_num(y)[idx], 0.0)
    w0 = np.where(inside, w[idx], 0.0) * tri[None, :]
    rob = np.ones(n)
    fit = np.zeros(n)
    for it in range(iterations):
        ww = w0 * rob[idx]
        s0, s1, s2 = ww.sum(1), (ww * d).sum(1), (ww * d * d).sum(1)
        t0, t1 = (ww * yy).sum(1), (ww * d * yy).sum(1)
        det = s0 * s2 - s1 * s1
        mean = np.divide(t0, s0, out=np.zeros(n), where=s0 > 0)
        ok = det > 1e-6 * np.maximum(s0, 1e-12) ** 2
        slope = np.divide(s0 * t1 - s1 * t0, det, out=np.zeros(n), where=ok)
        fit = np.where(ok, (t0 - slope * s1) / np.where(s0 > 0, s0, 1), mean)
        # no extrapolation past the window's own values (a one-sided window at the edge of the evidence)
        has = w0 > 0
        lo = np.where(has, yy, np.inf).min(1)
        hi = np.where(has, yy, -np.inf).max(1)
        fit = np.where(has.any(1), np.clip(fit, np.minimum(lo, hi), hi), 0.0)
        if it == iterations - 1:
            break
        r = np.where(w > 0, np.nan_to_num(y) - fit, 0.0)
        mad = float(np.median(np.abs(r[w > 0]))) if (w > 0).any() else 0.0
        z = r / (6 * max(mad, 1e-4))
        rob = np.where(np.abs(z) < 1, (1 - z ** 2) ** 2, 0.0)
    return fit, w0.sum(1) / tri.sum()


def _limit_tempo_steps(base: np.ndarray, dev: np.ndarray, max_step: float,
                       max_iterations: int = 500) -> tuple[np.ndarray, int]:
    """Smooth dev locally until it changes no beat period by more than max_step from the previous one.

    The limit is on what the deviations add to the base (their second difference against the base's beat period),
    so a tracker base's own tempo changes are left alone.
    """
    dev = dev.copy()
    ibi = np.diff(base)
    for it in range(max_iterations):
        d2 = dev[2:] - 2 * dev[1:-1] + dev[:-2]
        bad = np.flatnonzero(np.abs(d2) > max_step * ibi[:-1]) + 1
        if not len(bad):
            return dev, it
        for k in bad:
            for j in range(max(1, k - 1), min(len(dev) - 1, k + 2)):
                dev[j] = 0.25 * dev[j - 1] + 0.5 * dev[j] + 0.25 * dev[j + 1]
    return dev, max_iterations


def onset_times(features: OnsetFeatures, delta: float = SECONDARY_DELTA) -> np.ndarray:
    """Onset times (s) of a stem: onset-envelope peaks that stand out locally, refined by a parabola.

    The envelope is divided by its running 95th percentile over 5 s and clipped at twice that, as the guitar audit's
    detector does. A peak counts when it is the largest within +-30 ms and at least delta above the normalised
    envelope's mean over +-100 ms; peaks more than 40 dB below the stem's loud level (leakage) are dropped.
    """
    env, fps = features.env, features.fps
    n = len(env)
    hop, half = max(1, int(round(fps))), int(round(2.5 * fps))
    centres = np.arange(0, n, hop)
    p95 = np.array([np.percentile(env[max(0, c - half):c + half + 1], 95) for c in centres])
    e = np.clip(env / (np.interp(np.arange(n), centres, p95) + 1e-6 * env.max() + 1e-12), 0, 2) / 2
    a, m = int(round(0.100 * fps)), int(round(0.030 * fps))
    c = np.concatenate([[0.0], np.cumsum(e)])
    lo, hi = np.maximum(np.arange(n) - a, 0), np.minimum(np.arange(n) + a + 1, n)
    mean = (c[hi] - c[lo]) / (hi - lo)
    top = np.lib.stride_tricks.sliding_window_view(np.pad(e, m, constant_values=-np.inf), 2 * m + 1).max(axis=1)
    loud = float(np.percentile(features.level_db, 95))
    i = np.flatnonzero((e >= top) & (e >= mean + delta) & (e > 0) & (features.level_db >= loud - 40.0))
    i = i[(i > 0) & (i < n - 1)]
    y0, y1, y2 = env[i - 1], env[i], env[i + 1]
    den = y0 - 2 * y1 + y2
    d = np.where(den < 0, np.clip(0.5 * (y0 - y2) / np.where(den < 0, den, -1.0), -0.5, 0.5), 0.0)
    return (i + d) / fps


def onset_phase(beats: np.ndarray, onsets: np.ndarray, calibrate: np.ndarray,
                half_width: int = SECONDARY_HALF_WIDTH) -> tuple[np.ndarray, np.ndarray, float | None, dict]:
    """Where a second stem's onsets put each beat: (shift s, score, lag s, stats) against the current beats.

    Each onset is a position in beats. Around every beat, the onsets within +-half_width beats give the mean 8th-
    and 16th-level phase vectors z8, z16; a shift of d beats has the agreements Re(z8 e^(-4 pi i d)) and
    Re(z16 e^(-8 pi i d)) (1 when every onset sits d after an 8th or a 16th line, about 0 when they are spread at
    random), and scores their mean. The stem's own lag is the d that scores best summed over the `calibrate` beats
    (drum supported, with enough onsets), so the shifts keep the drums' convention. A beat's shift is its best d
    within 3/16 of a beat of the lag (+-79 ms at 142 BPM), minus the lag. Its score counts only when the 8th-level
    agreement alone reaches SECONDARY_MIN_EIGHTH, so a 16th-level fit a 16th away from the truth cannot win, and
    when SECONDARY_MIN_ONSETS onsets are in reach; otherwise it is 0. The lag is None (and every score 0) when fewer
    than SECONDARY_MIN_CALIBRATION beats can calibrate it or their mean score at the lag stays below
    SECONDARY_MIN_FOLLOW: a stem that does not follow the drums where both play (0.03-0.05 for onsets at random
    times; 0.39-0.76 for the test song's and the references' guitar, bass and mix) cannot time the beats without them.
    """
    K = len(beats)
    onsets = np.sort(onsets)
    j = np.searchsorted(beats, onsets) - 1
    ok = (j >= 0) & (j < K - 1)
    j = j[ok]
    u = j + (onsets[ok] - beats[j]) / (beats[j + 1] - beats[j])  # ascending
    lo, hi = np.searchsorted(u, np.arange(K) - half_width), np.searchsorted(u, np.arange(K) + half_width)
    count = hi - lo
    z = np.zeros((K, 2), dtype=complex)
    for col, h in enumerate((2, 4)):
        c = np.concatenate([[0], np.cumsum(np.exp(2j * np.pi * h * u))])
        z[:, col] = np.divide(c[hi] - c[lo], count, out=np.zeros(K, dtype=complex), where=count > 0)
    eighth = lambda x: np.real(z[:, :1] * np.exp(-4j * np.pi * x))  # noqa: E731  x: shifts in beats, shape (1, D)
    score_at = lambda x: 0.5 * (eighth(x) + np.real(z[:, 1:] * np.exp(-8j * np.pi * x)))  # noqa: E731
    period = float(np.median(np.diff(beats)))
    d = np.arange(-0.25, 0.25, 0.001 / period)[None, :]  # 1 ms steps
    enough = count >= SECONDARY_MIN_ONSETS
    cal = calibrate & enough
    stats = {"n_onsets": int(len(onsets)), "calibration_beats": int(cal.sum())}
    if cal.sum() < SECONDARY_MIN_CALIBRATION:
        return np.zeros(K), np.zeros(K), None, stats
    lag = float(d[0, int(np.argmax(score_at(d)[cal].sum(axis=0)))])
    stats["calibration_score"] = round(float(np.mean(score_at(np.array([[lag]]))[cal])), 4)
    if stats["calibration_score"] < SECONDARY_MIN_FOLLOW:
        return np.zeros(K), np.zeros(K), None, stats
    d = d[:, np.abs(d[0]) <= 3 / 16]
    sc = score_at(lag + d)
    best = np.argmax(sc, axis=1)
    sure = enough & (eighth(lag + d[0, best][:, None])[:, 0] >= SECONDARY_MIN_EIGHTH)
    return d[0, best] * np.gradient(beats), np.where(sure, sc[np.arange(K), best], 0.0), lag * period, stats


def _secondary_fill(base: np.ndarray, smooth: np.ndarray, support: np.ndarray, free_dev: np.ndarray, repairs: int,
                    features: OnsetFeatures) -> tuple[np.ndarray, int, dict]:
    """The free curve's deviations with the drumless beats timed by a second stem (beat_grid's `secondary`).

    The second stem's shifts (onset_phase, calibrated on the beats with drum support) count where the drums give
    less than half support and the phase agreement reaches SECONDARY_MIN_SCORE. They are LOESS-smoothed on their
    own, weighted by that agreement, and fill in where the drum curve fades: dev = f_d * drums + (1 - f_d) * f_s *
    second stem, f = clip(support / 0.5), so beats with drum support keep the drums' curve. Then the tempo steps
    are limited again. Stats: the stem's lag (ms), calibration, beats timed, and per stretch of 8 or more
    beats without drum support (onset times) the share of its beats the second stem timed.
    """
    beats = base + free_dev
    shift, score, lag, stats = onset_phase(beats, onset_times(features), support >= 0.5)
    use = (support < 0.5) & (score >= SECONDARY_MIN_SCORE)
    stats["lag_ms"] = round(lag * 1000, 2) if lag is not None else None
    stats["beats_timed"] = int(use.sum())
    f_d = np.clip(support / 0.5, 0, 1)
    out = free_dev
    if use.any():
        s_smooth, s_support = loess(np.where(use, free_dev + shift, 0.0), np.where(use, score, 0.0))
        filled = f_d * smooth + (1 - f_d) * np.clip(s_support / 0.5, 0, 1) * s_smooth
        out, repairs = _limit_tempo_steps(base, filled, MAX_TEMPO_STEP)
    stats["stretches"] = drumless_stretches(beats, support, use)
    return out, repairs, stats


def drumless_stretches(beats: np.ndarray, support: np.ndarray, timed: np.ndarray | None = None,
                       min_beats: int = 8) -> list[tuple[float, float, int, float]]:
    """The stretches of min_beats or more beats with under half drum support, as (first beat, last beat, beats, share
    of them a second stem timed: 0 without one)."""
    timed = np.zeros(len(beats), dtype=bool) if timed is None else timed
    edges = np.flatnonzero(np.diff(np.concatenate([[0], (support < 0.5).astype(int), [0]])))
    return [(round(float(beats[a]), 2), round(float(beats[b - 1]), 2), int(b - a), round(float(timed[a:b].mean()), 3))
            for a, b in zip(edges[::2], edges[1::2]) if b - a >= min_beats]


# ---------------------------------------------------------------------------------------------------- downbeats

def bar_phase(features: OnsetFeatures, beats: np.ndarray, use: np.ndarray, beats_per_bar: int = 4,
              half_window: float = 0.035) -> tuple[int, float, list[float]]:
    """(phase, margin, scores): which beat index mod beats_per_bar starts the bar.

    For each beat, the kick and snare band powers' maxima within +-half_window. Per phase, the median over the
    beats in `use`; the score is that phase's share of the kick minus its share of the snare (a snare body also
    has energy below 160 Hz). The margin is the best score minus the second best (0 = no preference, 2 = most).
    """
    fps = features.fps
    hw = int(round(half_window * fps))
    kick = np.zeros(len(beats))
    snare = np.zeros(len(beats))
    for k, t in enumerate(beats):
        c = int(round(t * fps))
        sl = slice(max(0, c - hw), min(len(features.kick), c + hw + 1))
        if sl.stop > sl.start:
            kick[k] = features.kick[sl].max()
            snare[k] = features.snare[sl].max()
    ph = np.arange(len(beats)) % beats_per_bar
    km = np.array([np.median(kick[use & (ph == p)]) if np.any(use & (ph == p)) else 0.0 for p in range(beats_per_bar)])
    sm = np.array([np.median(snare[use & (ph == p)]) if np.any(use & (ph == p)) else 0.0 for p in range(beats_per_bar)])
    scores = km / (km.sum() + 1e-12) - sm / (sm.sum() + 1e-12)
    order = np.argsort(scores)[::-1]
    return int(order[0]), float(scores[order[0]] - scores[order[1]]), [round(float(s), 4) for s in scores]


def half_beat_phase(features: OnsetFeatures, beats: np.ndarray, use: np.ndarray,
                    half_window: float = 0.035) -> tuple[bool, dict]:
    """(shift, stats): whether the beat lines belong half a beat later, on the midpoints between these beats.

    The kick band's (KICK_BAND) peak within +-half_window of each beat and of each beat's midpoint, as medians over
    the beats in `use`: the lines that carry more kick are the beat, as bar_phase puts beat 1 on the kick. A grid at
    twice the tempo can lock onto the 8ths the drums hit hardest, a snare on every "and" over a kick on every beat
    (a fast power-metal beat), which puts its lines on the off-beats; this finds that. stats: the two medians, their
    ratio (midpoints / lines; over 1: shift) and the beats used."""
    fps, kick = features.fps, features.kick
    hw = int(round(half_window * fps))

    def peak(t: np.ndarray) -> np.ndarray:
        c = np.round(t * fps).astype(int)
        return np.array([kick[max(0, i - hw):max(0, min(len(kick), i + hw + 1))].max(initial=0.0) for i in c])

    b = np.asarray(beats, dtype=np.float64)
    if len(b) < 2 or not use[:-1].any():
        return False, {"lines": None, "midpoints": None, "ratio": None, "beats": 0, "shifted": False}
    u = use[:-1]
    lines, mids = float(np.median(peak(b[:-1][u]))), float(np.median(peak(0.5 * (b[:-1] + b[1:])[u])))
    ratio = mids / lines if lines > 0 else (np.inf if mids > 0 else 1.0)
    shift = bool(ratio > 1.0)
    return shift, {"lines": round(lines, 6), "midpoints": round(mids, 6),
                   "ratio": round(float(ratio), 4) if np.isfinite(ratio) else None, "beats": int(u.sum()),
                   "shifted": shift}


def shift_half_beat(beats: np.ndarray, duration: float) -> np.ndarray:
    """The beats moved half a beat later: each beat's midpoint with the next, and one more half a beat before the
    first where it stays at or after 0 s (the last beat's next midpoint is past it, and falls when it passes the
    duration)."""
    b = np.asarray(beats, dtype=np.float64)
    mids = 0.5 * (b[:-1] + b[1:])
    after = b[-1] + 0.5 * (b[-1] - b[-2])
    before = b[0] - 0.5 * (b[1] - b[0])
    return np.concatenate([[before] if before >= 0 else [], mids, [after] if after <= duration else []])


# ---------------------------------------------------------------------------------------------------- the grid

def beat_grid(audio: np.ndarray | None, sample_rate: int, duration: float | None = None, bpm: float | None = None,
              first_beat: float | None = None, mode: str | None = None, onset_to_beat_ms: float = ONSET_TO_BEAT_MS,
              start: np.ndarray | None = None, features: OnsetFeatures | None = None,
              secondary: np.ndarray | None = None, secondary_features: OnsetFeatures | None = None,
              bpm_range: tuple[float, float] = BPM_RANGE, half_beat: bool = False, keep_line: bool = False
              ) -> BeatGrid:
    """The beat grid of a song from its drum stem (or its mix when it has no drums).

    audio:      shape (channels, samples) or (samples,), at sample_rate. May be None when `features` is given.
    duration:   the song's length in seconds (default: the audio's); beats run from the first beat up to it.
    bpm, first_beat: optional hints for the start grid (the first beat as heard, within +-60 ms).
    mode:       "free" or "click" to override the automatic choice.
    onset_to_beat_ms: added to every beat (the convention offset between drum peaks and human beat lines).
    start:      beat times from an external tracker (the hook for Beat This!), used as the start grid instead of
                the straight line and the internal tracker.
    secondary:  a second stem (the guitar or "other" stem, else the bass), or its `secondary_features`. In free
                mode the beats the drums leave without evidence follow its onsets where they hold a clear 8th/16th
                phase (onset_phase), in the drums' convention; elsewhere they stay on the line.
    bpm_range:  the octave every tempo estimate folds into, [lo, hi) BPM: the start line's autocorrelation tempo,
                the tracker's local windows and the tempo check. The default is one metrical level, BPM_RANGE;
                assemble's second pass (a grid at twice the tempo, DESIGN.md 2.3) gives (2 lo, 2 hi), so a 198 BPM
                hint is not folded back to 99 by the windows.
    half_beat:  test the beat phase (half_beat_phase): when the midpoints between the beats carry more kick than
                the beats, the beats move half a beat later, before the downbeats are found. assemble's second pass
                turns it on (stats["half_beat"]); evidence, click and drift stats stay those of the grid found.
    keep_line:  the straight start line is never replaced by the tracker's beats (it still runs, for its stats).
                assemble's second pass sets it: its hint is the first grid's tempo doubled, and on a fast drum stem
                the tracker flips between the beats and their "and"s over parts of the song (DESIGN.md 2.3 step 7).

    The start grid is the straight line unless a tracker's beats find clearly more evidence (TRACKER_MARGIN more
    of the beats confident): then no straight line fits the song, the fill for beats without evidence follows the
    tracker's smoothed beats, and the automatic mode is free.
    """
    if mode not in (None, "free", "click"):
        raise ValueError(f"unknown mode {mode!r}")
    if not 0 < bpm_range[0] < bpm_range[1]:
        raise ValueError(f"bpm_range must be (lo, hi) with 0 < lo < hi, not {bpm_range!r}")
    f = features if features is not None else onset_features(audio, sample_rate)
    dur = float(duration) if duration is not None else f.duration
    stats: dict = {}
    line_ev = None
    if start is not None:
        tracker = np.asarray(start, dtype=np.float64)
        tracker = tracker[(tracker >= 0) & (tracker <= dur)]
        if len(tracker) < 8 or np.any(np.diff(tracker) <= 0):
            raise ValueError("start beats must be strictly increasing, with at least 8 inside the audio")
        stats["start"] = {"source": "external", "n_beats": int(len(tracker))}
    else:
        period, first, source = start_line(f, dur, bpm, first_beat, bpm_range)
        line = first + np.arange(int(np.floor((dur - first) / period)) + 1) * period
        line_ev = local_beats(f, line)
        periods, changes = local_periods(f.env, f.fps, period, bpm_range)
        tracker = track_beats(f.env, f.fps, periods)
        tracker = tracker[(tracker <= dur) & (tracker >= (first_beat - SEARCH_S if first_beat is not None else 0))]
        stats["start"] = {"source": source, "bpm": round(60.0 / period, 4), "first_beat": round(first, 4),
                          "line_confident_share": round(float(line_ev.confident.mean()), 4),
                          "tracker_tempo_changes": changes}
    trk_ev = local_beats(f, tracker)
    use_tracker = line_ev is None or (not keep_line and
                                      trk_ev.confident.mean() >= line_ev.confident.mean() + TRACKER_MARGIN)
    stats["start"]["tracker_confident_share"] = round(float(trk_ev.confident.mean()), 4)
    stats["start"]["grid"] = "tracker" if use_tracker else "line"

    # pass 1 around the start grid gave the evidence; pass 2 around the robust line (or the smoothed tracker)
    ev = trk_ev if use_tracker else line_ev
    conf = ev.confidence * ev.confident
    if conf.sum() < 3:
        raise InputError("no confident drum evidence: pass a tracker's beats as start")
    if use_tracker:
        k = np.arange(len(tracker), dtype=np.float64)
        base, _ = loess(tracker, np.ones(len(tracker)), half_width=8, iterations=1)
        base = base + float(np.median((ev.times - base)[conf > 0]))
        ev = local_beats(f, base)
        conf = ev.confidence * ev.confident
        a, b, _ = robust_line(k, np.nan_to_num(ev.times), conf)
        line = a + b * k
    else:
        k = np.arange(len(line), dtype=np.float64)
        a, b, _ = robust_line(k, np.nan_to_num(ev.times), conf)
        ev = local_beats(f, a + b * k)
        conf = ev.confidence * ev.confident
        a, b, _ = robust_line(k, np.nan_to_num(ev.times), conf)
        line = base = a + b * k
    confident = conf > 0
    res = (ev.times - line)[confident]
    stats["click"] = {"bpm": round(60.0 / b, 4), "first_beat": round(float(line[0]), 4),
                      "residual_ms": {"median_abs": round(float(np.median(np.abs(res))) * 1000, 2),
                                      "p95_abs": round(float(np.percentile(np.abs(res), 95)) * 1000, 2)}}

    # free curve: LOESS of the deviations from the base, faded to the base where evidence runs out
    dev = np.where(confident, ev.times - base, 0.0)
    smooth, support = loess(dev, conf)
    free_dev, repairs = _limit_tempo_steps(base, smooth * np.clip(support / 0.5, 0, 1), MAX_TEMPO_STEP)
    drift = (base + smooth - line)[support >= 0.5]  # the drummer against the straight line, where measured
    share = float(confident.mean())
    stats["evidence"] = {"confident_share": round(share, 4), "n_confident": int(confident.sum()),
                         "n_beats": int(len(base))}
    stats["drift_ms"] = {"p50_abs": round(float(np.median(np.abs(drift))) * 1000, 2) if len(drift) else 0.0,
                         "p95_abs": round(float(np.percentile(np.abs(drift), 95)) * 1000, 2) if len(drift) else 0.0,
                         "max_abs": round(float(np.max(np.abs(drift))) * 1000, 2) if len(drift) else 0.0}
    if mode:
        chosen, reason = mode, "override"
    elif use_tracker:
        chosen, reason = "free", "no straight line fits: the beats follow the tracker"
    else:
        chosen = "free" if share >= FREE_SHARE else "click"
        reason = f"confident share {share:.2f} {'>=' if share >= FREE_SHARE else '<'} {FREE_SHARE:.2f}"
    stats["mode"] = {"mode": chosen, "reason": reason}
    if secondary is not None or secondary_features is not None:
        if chosen == "free":
            g = secondary_features if secondary_features is not None else onset_features(secondary, sample_rate)
            free_dev, repairs, stats["secondary"] = _secondary_fill(base, smooth, support, free_dev, repairs, g)
        else:
            stats["secondary"] = {"beats_timed": 0, "reason": "click mode: every beat is on the line"}
    elif chosen == "free":  # where the beats follow the line for want of evidence
        stats["secondary"] = {"beats_timed": 0, "reason": "no second stem",
                              "stretches": drumless_stretches(base + free_dev, support)}
    onset_beats = base + free_dev if chosen == "free" else line
    if chosen == "free":
        d2 = np.diff(free_dev, 2) / np.diff(base)[:-1]
        stats["free"] = {"tempo_step_max": round(float(np.max(np.abs(d2))), 5) if len(d2) else 0.0,
                         "tempo_step_repair_iterations": repairs}
    stats["tempo_check"] = missed_tempo_changes(f, onset_beats, bpm_range)
    follow = (ev.times - onset_beats)[confident]
    stats["evidence"]["local_minus_grid_ms"] = {"median_abs": round(float(np.median(np.abs(follow))) * 1000, 2),
                                                "p95_abs": round(float(np.percentile(np.abs(follow), 95)) * 1000, 2)}
    if half_beat:
        shift, stats["half_beat"] = half_beat_phase(f, onset_beats, confident)
        if shift:
            onset_beats = shift_half_beat(onset_beats, dur - onset_to_beat_ms / 1000.0)
            confident = local_beats(f, onset_beats).confident

    # downbeats on the onset-time beats (also per 16 bars, to show where the bar phase disagrees), then the
    # convention shift, then trim to the audio
    phase, margin, scores = bar_phase(f, onset_beats, confident)
    windows = []
    idx = np.arange(len(onset_beats))
    for s in range(0, len(onset_beats) - 63, 64):
        use = confident & (idx >= s) & (idx < s + 64)
        if use.sum() >= 16:
            p, m, _ = bar_phase(f, onset_beats, use)
            windows.append((round(float(onset_beats[s]), 2), p, round(m, 3)))
    beats = onset_beats + onset_to_beat_ms / 1000.0
    keep = (beats >= 0) & (beats <= dur)
    first_kept = int(np.argmax(keep))
    beats = beats[keep]
    if np.any(np.diff(beats) <= 0):
        raise RuntimeError("beat grid is not strictly increasing")
    rot = lambda p: (p - first_kept) % 4  # noqa: E731  phases of the untrimmed beats, renumbered
    downbeats = np.arange(rot(phase), len(beats), 4)
    stats["downbeats"] = {"phase": rot(phase), "margin": round(margin, 4), "uncertain": margin < DOWNBEAT_MIN_MARGIN,
                          "scores": [scores[(p + first_kept) % 4] for p in range(4)],
                          "windows": [(t, rot(p), m) for t, p, m in windows],
                          "windows_disagreeing": sum(1 for _, p, _ in windows if p != phase)}
    stats["onset_to_beat_ms"] = onset_to_beat_ms
    return BeatGrid(beats, downbeats, chosen, stats)
