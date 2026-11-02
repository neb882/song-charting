"""Bass from our own rules on the bass stem (DESIGN.md 2.8, Goal 2): onsets, pitch, lanes and sustains.

    result = generate(mix, bass, "work/bass")      # float32 (2, n) at 44.1 kHz, the stem sample-aligned to the mix
    song = importers.read_song(result.folder)      # Expert bass in seconds of the decode (time_offset 0)

  * **Onsets.** v1's high-frequency-content envelope of the stem (2048-point STFT, hop 256: the rise of log(1 + HFC /
    its median over the song)), picked by librosa.util.peak_pick at delta 0.07 (DESIGN.md: 0.05-0.07; v1's
    prototype on htdemucs_6s stems), a local maximum over +-30 ms, at least 60 ms apart. The times are not snapped:
    the quantizer puts them on our grid (2.6).
  * **Leakage gate** (2.2). An onset stays only where the stem is within 30 dB of the mix over the window around it
    (-50 to +200 ms, assemble's silence window), so a stem's leakage (-34 dB in the test song's intro) writes no note.
  * **Pitch.** librosa.pyin (fmin 30 Hz, fmax 400 Hz) on the stem resampled to 22.05 kHz, frame 2048 (two periods of
    30 Hz need 1470 samples there; at 44.1 kHz they would need 2941), hop 220 (10 ms), in 30-s chunks with 1 s of
    overlap so memory stays bounded. A note's pitch is the median of the voiced frames 20-150 ms after its onset,
    before the next note.
  * **Lanes.** v1's rank/contour map (`map_lanes`, the prototype's map_v2): phrases split at gaps over 1.5 s,
    windows of 12 notes, each window's distinct pitches ranked onto the lanes, one lane per step and two for a 4th or
    more, squeezed into five lanes and centred. A repeated pitch keeps its lane, an unvoiced note takes the previous
    note's pitch, and notes under 0.2 s apart move at most two lanes. Single notes only: no chords, no open notes.
  * **Sustains.** A note holds while the pitch track stays voiced within a semitone of its pitch (an octave error
    counts as the same note) and the stem stays within 30 dB of the mix, bridging dropouts up to 35 ms. A hold of
    200 ms or more is a sustain, ending at the latest 85 ms before the next note: the seconds halves of 2.7's limits
    (the quantizer applies the beat halves on our grid).
  * **HOPOs.** None written: a rule engine has no HOPO intent, so the natural rule on our grid decides (2.6).

The output folder holds notes.chart (Expert bass, [ExpertDoubleBass], on a constant 120 BPM map at resolution 480,
so a tick is 1.04 ms) and engine.json (the settings, library versions, counts and timings). It is also the cache: a
folder whose engine.json has the same key (the samples, every setting, the rules' version and the libraries'
versions) and whose notes.chart is the one it describes is returned as it is.

Needs librosa (`pip install songcharter[bass]`); importing this module does not.
"""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

from .. import __version__
from .. import audio as A
from ..chart import Chart, FretNote, SongInfo, Track, write_chart
from ..tempo import Tempo, TempoMap
from ..timed import TimedNote

SAMPLE_RATE = A.SAMPLE_RATE
VERSION = "1"              # the rules' version: bump it whenever a change moves notes, so old folders are not reused
RESOLUTION, BPM_MILLI = 480, 120000   # the output's constant map: 960 ticks per second
TICKS_PER_S = RESOLUTION * BPM_MILLI / 60000
LEVEL_HOP = 441            # samples (10 ms) per frame of the stem and mix levels
ENGINE = "songcharter.engines.bass"


@dataclass(frozen=True)
class Settings:
    # onsets: v1's HFC detector (research/transcription/lib/onsets.py)
    n_fft: int = 2048
    hop: int = 256
    delta: float = 0.07                    # peak_pick threshold on the envelope scaled to 0..1
    peak_s: float = 0.03                   # a peak is the largest value within this either side
    mean_s: float = 0.10                   # ... and delta above the mean over this either side
    wait_s: float = 0.06                   # onsets at least this far apart
    # leakage gate (DESIGN.md 2.2)
    leak_db: float = 30.0
    leak_window: tuple[float, float] = (-0.05, 0.20)
    # pitch (DESIGN.md 2.8)
    fmin: float = 30.0
    fmax: float = 400.0
    pitch_rate: int = 22050
    frame_length: int = 2048
    pitch_hop: int = 220
    pitch_window: tuple[float, float] = (0.02, 0.15)   # seconds after the onset
    chunk_s: float = 30.0
    overlap_s: float = 1.0
    # lanes: v1's map_v2 (research/transcription/lib/fretmap2.py)
    phrase_gap_s: float = 1.5
    window_notes: int = 12
    fast_s: float = 0.2
    fast_jump: int = 2
    # sustains
    hold_semitones: float = 1.0
    hold_gap_s: float = 0.035
    sustain_min_s: float = 0.2             # Encore's shortest sustain; 2.7's floor is max(200 ms, 0.75 beat)
    sustain_gap_s: float = 0.085           # 2.7's gap before the next note is max(85 ms, a 1/16)

    def __post_init__(self):
        if not 0 < self.fmin < self.fmax < self.pitch_rate / 2:
            raise ValueError(f"pitch range {self.fmin}-{self.fmax} Hz does not fit {self.pitch_rate} Hz")
        if self.frame_length < 2 * self.pitch_rate / self.fmin:
            raise ValueError(f"frame_length {self.frame_length} holds under two periods of fmin {self.fmin} Hz at "
                             f"{self.pitch_rate} Hz (it needs {int(2 * self.pitch_rate / self.fmin) + 1})")
        if self.overlap_s * self.pitch_rate < self.frame_length:
            raise ValueError("overlap_s must cover a pitch frame")
        if self.window_notes < 1 or self.hop < 1 or self.pitch_hop < 1:
            raise ValueError("window_notes, hop and pitch_hop must be positive")


@dataclass(frozen=True)
class Result:
    folder: Path
    chart: Path          # notes.chart
    info: dict           # engine.json
    cached: bool


def _librosa():
    try:
        import librosa
    except ImportError as e:
        raise ImportError("the bass engine needs librosa: pip install songcharter[bass]") from e
    return librosa


def versions() -> dict[str, str]:
    """The libraries whose versions can change the notes."""
    import scipy
    out = {"songcharter": __version__, "librosa": _librosa().__version__, "numpy": np.__version__,
           "scipy": scipy.__version__}
    try:
        import soxr  # librosa's default resampler
        out["soxr"] = soxr.__version__
    except ImportError:
        pass
    return out


def cache_key(mix: np.ndarray, bass: np.ndarray, settings: Settings, libs: dict[str, str]) -> str:
    """A hash of both inputs' samples, every setting, the rules' version and the libraries' versions."""
    h = hashlib.sha256()
    h.update(repr((ENGINE, VERSION, mix.shape, bass.shape, SAMPLE_RATE, sorted(asdict(settings).items()),
                   sorted(libs.items()))).encode())
    for a in (mix, bass):
        h.update(np.ascontiguousarray(a, dtype="<f4").tobytes())
    return h.hexdigest()[:24]


# ----------------------------------------------------------------------------------------------------- onsets
def hfc_envelope(x: np.ndarray, s: Settings) -> np.ndarray:
    """The HFC onset envelope of a mono signal, one value per hop (frame j centred on sample j * hop, zero-padded at
    the ends as librosa.stft does): the rise of log(1 + HFC / median HFC), HFC being the bin-weighted power spectrum."""
    from scipy.signal import get_window
    win = get_window("hann", s.n_fft).astype(np.float32)   # periodic, as librosa.stft's
    y = np.pad(np.asarray(x, dtype=np.float32), s.n_fft // 2)
    frames = 1 + len(x) // s.hop
    view = np.lib.stride_tricks.sliding_window_view(y, s.n_fft)[::s.hop][:frames]
    weight = np.arange(s.n_fft // 2 + 1, dtype=np.float64)
    h = np.empty(frames)
    for a in range(0, frames, 2048):                         # blocks of frames, so memory stays small
        spec = np.fft.rfft(view[a:a + 2048] * win, axis=1)
        h[a:a + 2048] = (np.abs(spec) ** 2) @ weight
    lh = np.log1p(h / np.median(h + 1e-9))
    return np.maximum(0.0, np.diff(lh, prepend=lh[:1]))


def pick_onsets(env: np.ndarray, s: Settings) -> np.ndarray:
    """Onset times (s) from the envelope, scaled to 0..1 over the song and peak-picked."""
    librosa = _librosa()
    if len(env) == 0:
        return np.zeros(0)
    fps = SAMPLE_RATE / s.hop
    e = (env - env.min()) / (env.max() - env.min() + 1e-9)
    peak, mean = max(1, int(s.peak_s * fps)), max(1, int(s.mean_s * fps))
    frames = librosa.util.peak_pick(e, pre_max=peak, post_max=peak, pre_avg=mean, post_avg=mean, delta=s.delta,
                                    wait=max(1, int(s.wait_s * fps)))
    return np.asarray(frames, dtype=np.float64) * s.hop / SAMPLE_RATE


# ------------------------------------------------------------------------------------------------ the levels
def levels(x: np.ndarray) -> np.ndarray:
    """Mean power over both channels per LEVEL_HOP samples (the last frame may be shorter)."""
    n = x.shape[-1]
    out = np.empty((n + LEVEL_HOP - 1) // LEVEL_HOP)
    step = LEVEL_HOP * 6000                                  # 60 s at a time
    for a in range(0, n, step):
        seg = np.asarray(x[..., a:a + step], dtype=np.float64)
        p = np.square(seg).reshape(-1, seg.shape[-1]).mean(axis=0)
        k = len(p) // LEVEL_HOP
        j = a // LEVEL_HOP
        out[j:j + k] = p[:k * LEVEL_HOP].reshape(k, LEVEL_HOP).mean(axis=1)
        if len(p) > k * LEVEL_HOP:
            out[j + k] = p[k * LEVEL_HOP:].mean()
    return out


def leakage_ok(times: np.ndarray, stem_levels: np.ndarray, mix_levels: np.ndarray, s: Settings) -> np.ndarray:
    """True where the stem is within leak_db of the mix over the leakage window around each time."""
    fps = SAMPLE_RATE / LEVEL_HOP
    n = len(stem_levels)
    ok = np.zeros(len(times), bool)
    for i, t in enumerate(times):
        a = int(np.clip(np.floor((t + s.leak_window[0]) * fps), 0, n - 1))
        b = int(np.clip(np.ceil((t + s.leak_window[1]) * fps), a + 1, n))
        ps, pm = stem_levels[a:b].mean(), mix_levels[a:b].mean()
        ok[i] = 10 * np.log10((ps + 1e-12) / (pm + 1e-12)) >= -s.leak_db
    return ok


# ----------------------------------------------------------------------------------------------------- pitch
def pitch_track(x: np.ndarray, s: Settings) -> tuple[np.ndarray, np.ndarray]:
    """pYIN on a mono 44.1-kHz signal: frame times (s) and pitch in MIDI numbers, NaN where unvoiced."""
    librosa = _librosa()
    y = librosa.resample(np.asarray(x, dtype=np.float32), orig_sr=SAMPLE_RATE, target_sr=s.pitch_rate)
    hop, n = s.pitch_hop, len(y)
    frames = 1 + n // hop
    midi = np.full(frames, np.nan)
    chunk = int(s.chunk_s * s.pitch_rate) // hop * hop
    over = int(np.ceil(s.overlap_s * s.pitch_rate / hop)) * hop
    for s0 in range(0, n, chunk):                            # chunks share frame positions with the whole track
        a, b = max(0, s0 - over), min(n, s0 + chunk + over)
        f0, _, _ = librosa.pyin(y[a:b], fmin=s.fmin, fmax=s.fmax, sr=s.pitch_rate, frame_length=s.frame_length,
                                hop_length=hop)
        i0, g0 = (s0 - a) // hop, s0 // hop
        k = min(chunk // hop, frames - g0, len(f0) - i0)
        with np.errstate(divide="ignore", invalid="ignore"):
            midi[g0:g0 + k] = 69 + 12 * np.log2(f0[i0:i0 + k] / 440.0)
    return np.arange(frames) * hop / s.pitch_rate, midi


def _frame(t: float, s: Settings) -> int:
    """The first pitch frame at or after time t."""
    return max(0, int(np.ceil(t * s.pitch_rate / s.pitch_hop - 1e-9)))


def note_pitches(times: np.ndarray, nexts: np.ndarray, midi: np.ndarray, s: Settings) -> np.ndarray:
    """Each note's pitch: the median of the voiced frames from pitch_window[0] after its onset to pitch_window[1]
    after it or the next onset, whichever comes first (NaN when none is voiced)."""
    out = np.full(len(times), np.nan)
    for i, (t, nxt) in enumerate(zip(times, nexts)):
        seg = midi[_frame(t + s.pitch_window[0], s):_frame(min(t + s.pitch_window[1], nxt), s)]
        seg = seg[np.isfinite(seg)]
        if len(seg):
            out[i] = float(np.median(seg))
    return out


# ----------------------------------------------------------------------------------------------------- lanes
def map_lanes(times, pitch, s: Settings = Settings()) -> np.ndarray:
    """Lanes 0-4 for single notes from their pitches (MIDI, NaN unknown): v1's rank/contour map (map_v2).

    Notes split into phrases at gaps over phrase_gap_s, and each phrase into windows of window_notes. A window's
    distinct (rounded) pitches take lane positions in pitch order, one lane per step and two for a step of a 4th or
    more; a span over five lanes is squeezed into them, keeping the order, and a narrower one is centred. A repeated
    pitch keeps its lane; a note without a pitch takes the previous note's pitch (lane 2 before any). Last, a note
    under fast_s after the previous one moves at most fast_jump lanes from it."""
    ts = np.asarray(times, dtype=float)
    p = np.round(np.asarray(pitch, dtype=float))
    n = len(ts)
    for i in range(1, n):
        if not np.isfinite(p[i]) and np.isfinite(p[i - 1]):
            p[i] = p[i - 1]
    lanes = np.full(n, 2, dtype=int)
    starts = [0] + [i for i in range(1, n) if ts[i] - ts[i - 1] > s.phrase_gap_s] + [n]
    for a, b in zip(starts[:-1], starts[1:]):
        for w in range(a, b, s.window_notes):
            idx = range(w, min(b, w + s.window_notes))
            v = p[w:min(b, w + s.window_notes)]
            if not np.isfinite(v).any():
                continue
            u = np.unique(v[np.isfinite(v)])
            if len(u) == 1:
                lane = {u[0]: 2}
            else:
                pos = np.concatenate([[0], np.cumsum(1 + (np.diff(u) >= 5))]).astype(float)
                if pos[-1] > 4:
                    pos = np.round(pos / pos[-1] * 4)
                off = int((4 - pos[-1]) // 2)
                lane = {q: int(x + off) for q, x in zip(u, pos)}
            for i in idx:
                lanes[i] = lane.get(p[i], lanes[i - 1] if i else 2)
    for i in range(1, n):
        if ts[i] - ts[i - 1] < s.fast_s and abs(lanes[i] - lanes[i - 1]) > s.fast_jump:
            lanes[i] = lanes[i - 1] + np.sign(lanes[i] - lanes[i - 1]) * s.fast_jump
    return np.clip(lanes, 0, 4)


# -------------------------------------------------------------------------------------------------- sustains
def sustain_ends(times: np.ndarray, nexts: np.ndarray, pitches: np.ndarray, midi: np.ndarray, frame_ok: np.ndarray,
                 s: Settings) -> list[float | None]:
    """Each note's sustain end (s) where the pitch track holds its pitch, or None (see the module docstring)."""
    fps = s.pitch_rate / s.pitch_hop
    max_miss = int(round(s.hold_gap_s * fps))
    out: list[float | None] = []
    for t, nxt, p in zip(times, nexts, pitches):
        last = None
        if np.isfinite(p):
            miss = 0
            for j in range(_frame(t + s.pitch_window[0], s), min(len(midi), _frame(nxt, s))):
                d = midi[j] - p
                if frame_ok[j] and np.isfinite(d) and min(abs(d), abs(d - 12), abs(d + 12)) <= s.hold_semitones:
                    last, miss = j / fps, 0
                else:
                    miss += 1
                    if miss > max_miss:
                        break
        end = None if last is None else min(last, nxt - s.sustain_gap_s)
        out.append(end if end is not None and end - t >= s.sustain_min_s else None)
    return out


# ------------------------------------------------------------------------------------------------ the engine
def transcribe(mix: np.ndarray, bass: np.ndarray, settings: Settings = Settings()) -> tuple[list[TimedNote], dict]:
    """Expert bass notes in seconds of the input, and what each step found (counts and timings)."""
    s = settings
    _check(mix, bass)
    t0 = time.perf_counter()  # timings are reported only
    x = np.asarray(bass, dtype=np.float32).mean(axis=0)
    onsets = pick_onsets(hfc_envelope(x, s), s)
    t1 = time.perf_counter()
    stem_lv, mix_lv = levels(bass), levels(mix)
    keep = leakage_ok(onsets, stem_lv, mix_lv, s)
    times = onsets[keep]
    t2 = time.perf_counter()
    frame_t, midi = pitch_track(x, s)
    t3 = time.perf_counter()
    duration = mix.shape[1] / SAMPLE_RATE
    nexts = np.append(times[1:], duration)
    pitches = note_pitches(times, nexts, midi, s)
    lanes = map_lanes(times, pitches, s)
    lv = np.minimum((frame_t * SAMPLE_RATE / LEVEL_HOP).astype(int), len(stem_lv) - 1)
    frame_ok = 10 * np.log10((stem_lv[lv] + 1e-12) / (mix_lv[lv] + 1e-12)) >= -s.leak_db
    ends = sustain_ends(times, nexts, pitches, midi, frame_ok, s)
    notes = [TimedNote(float(t), (int(lane),), end) for t, lane, end in zip(times, lanes, ends)]
    t4 = time.perf_counter()
    voiced = np.isfinite(pitches)
    stats = {"counts": {"onsets": int(len(onsets)), "leakage_dropped": int((~keep).sum()), "notes": len(notes),
                        "unvoiced_notes": int((~voiced).sum()), "sustained": sum(e is not None for e in ends),
                        "lanes": np.bincount(lanes, minlength=5).tolist() if len(lanes) else [0] * 5,
                        "voiced_frames": round(float(np.isfinite(midi).mean()), 4) if len(midi) else 0.0},
             "pitch_midi_p5_p50_p95": ([round(float(np.percentile(pitches[voiced], q)), 2) for q in (5, 50, 95)]
                                       if voiced.any() else None),
             "timings_s": {"onsets": round(t1 - t0, 2), "leakage": round(t2 - t1, 2), "pitch": round(t3 - t2, 2),
                           "lanes_sustains": round(t4 - t3, 2), "total": round(t4 - t0, 2)}}
    return notes, stats


def to_chart(notes: list[TimedNote], title: str = "songcharter bass engine") -> Chart:
    """The notes as Expert bass on the constant 120 BPM map (resolution 480)."""
    tm = TempoMap(RESOLUTION, [Tempo(0, BPM_MILLI)])
    out = []
    for n in notes:
        tick = int(round(n.time * TICKS_PER_S))
        length = max(1, int(round(n.end * TICKS_PER_S)) - tick) if n.end is not None else 0
        out.append(FretNote(tick, n.frets, length))
    return Chart(SongInfo(title, "", charter="songcharter"), tm, [], [Track("Expert", "DoubleBass", out)])


def generate(mix: np.ndarray, bass: np.ndarray, out: Path | str, settings: Settings = Settings(), *,
             sample_rate: int = SAMPLE_RATE) -> Result:
    """Chart the bass of `mix` from its bass stem into the folder `out` (notes.chart and engine.json; nothing else
    there is touched). A folder that already holds this input's chart for these settings is returned as it is."""
    if sample_rate != SAMPLE_RATE:
        raise ValueError(f"the bass engine needs {SAMPLE_RATE} Hz audio, not {sample_rate} Hz")
    _check(mix, bass)
    folder = Path(out)
    libs = versions()
    key = cache_key(mix, bass, settings, libs)
    done = _done(folder, key)
    if done is not None:
        return Result(folder, folder / "notes.chart", done, True)
    t0 = time.perf_counter()
    notes, stats = transcribe(mix, bass, settings)
    chart_text = write_chart(to_chart(notes))
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "notes.chart").write_text(chart_text, encoding="utf-8", newline="")
    info = {"engine": ENGINE, "version": VERSION, "key": key, "settings": asdict(settings), "versions": libs,
            "input": {"sample_rate": SAMPLE_RATE, "samples": int(mix.shape[1]),
                      "seconds": round(mix.shape[1] / SAMPLE_RATE, 3)},
            "chart": {"file": "notes.chart", "track": "ExpertDoubleBass", "resolution": RESOLUTION,
                      "bpm": BPM_MILLI / 1000, "sha256": hashlib.sha256(chart_text.encode("utf-8")).hexdigest()},
            **stats}
    info["timings_s"]["generate"] = round(time.perf_counter() - t0, 2)
    meta = json.dumps(info, indent=1)
    (folder / "engine.json").write_text(meta, encoding="utf-8")   # written last: it marks the folder finished
    return Result(folder, folder / "notes.chart", json.loads(meta), False)


def _check(mix: np.ndarray, bass: np.ndarray) -> None:
    for name, a in (("mix", mix), ("bass stem", bass)):
        if a.ndim != 2 or a.shape[0] != 2:
            raise ValueError(f"the {name} must be a stereo (2, n) array, not shape {a.shape}")
    if mix.shape != bass.shape:
        raise ValueError(f"the bass stem {bass.shape} and the mix {mix.shape} differ in length")


def _done(folder: Path, key: str) -> dict | None:
    """engine.json of a finished run in `folder` for this key whose notes.chart is unchanged, else None."""
    chart, meta = folder / "notes.chart", folder / "engine.json"
    if not (chart.is_file() and meta.is_file()):
        return None
    try:
        info = json.loads(meta.read_text(encoding="utf-8"))
    except ValueError:
        return None
    if info.get("key") != key or info.get("chart", {}).get("sha256") != hashlib.sha256(chart.read_bytes()).hexdigest():
        return None
    return info
