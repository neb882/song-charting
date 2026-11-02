"""Pro-drum lanes from a five-class drum transcriber's peaks (DESIGN.md 2.9): our own fusion and lane mapping.

The transcriber (adtof.py) gives peak frames for kick (BD), snare (SD), toms (TT), hi-hat (HH) and cymbals (CY), on
the drum stem and on the mix. This module is the ADTOF test's lane mapper (drummap2 with toms by pitch cluster and
hh_cy="stronger"), the baseline a better mapper must beat (M2), with DESIGN.md 2.9's fusion:

  1. **Fusion.** BD, SD and TT come from the drum stem, HH and CY from the mix: a Demucs drum stem can delete the
     ride (CY F 0.16 on the stem against 0.96 on the mix), and the mix adds false kicks (54 against 26 on a
     test-song excerpt). No constant offset.
  2. **Stem evidence for the mix's hats and cymbals** (critique G3). A mix HH or CY peak is kept only where the drum
     stem plays around it: its power over the second around the peak (`hat_gate_window`, every band) within
     `hat_gate_db` (40 dB) of the mix's. Where the song has no drums the stem holds only leakage, about 60 dB under
     the mix, so a guitar's or a voice's transients there give no hats. The window is wide on purpose: the stem
     often lacks the hat itself (the reason HH and CY come from the mix), and asking for the hat's own highs in the
     stem (2 kHz up, -10 to +30 ms, 30 dB) removed a quarter of the test song's hats, all in drummed passages.
  3. **Hits.** Peaks of any class less than `merge_s` (30 ms) after a hit's first peak join that hit, each class
     keeping its strongest activation. At 100 frames a second that is two frames.
  4. **Lanes.** BD kick; SD red; HH yellow cymbal; CY blue cymbal in a regular run (at least 4 CY hits within +-2
     beats, itself included) and green otherwise; TT toms by pitch: the dominant 60-400 Hz peak in the stem's first
     80 ms after the hit, clustered on a log scale into one to three groups split at the widest gaps over 18 %
     (lowest green, highest yellow, middle blue). A hit with both HH and CY keeps the stronger activation.
  5. **Kit.** At most two hand pads per hit (crash, ride, snare, hi-hat, then toms yellow to green). A cymbal and a
     tom on one pad, which a .chart cannot hold, keep the cymbal; the tom is dropped and counted.
  6. **2x kick** (Expert only, the only level an engine writes). In a run of more than `double_kick_rate` (6) kicks,
     each less than 1/6 s after the one before (a second or so of kicks faster than 6 a second), a kick less than
     1/6 s after the run's last single-pedal kick becomes a 2x kick, so the run's single-pedal kicks are at least
     1/6 s apart. Shorter bursts, a quick double among them, stay single.

The beat period for step 4 is the mix's tempo (beatgrid.estimate_tempo, folded into 85-185 BPM) unless given.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np

from ..chart import DrumHit

LABELS = ("BD", "SD", "TT", "HH", "CY")
THRESHOLDS = (0.22, 0.24, 0.32, 0.22, 0.30)   # peak heights per class (DESIGN.md 2.9)
FROM_MIX = ("HH", "CY")
MERGE_S = 0.030
HAT_GATE_DB = 40.0           # G3: the stem within this many dB of the mix ...
HAT_GATE_HZ = 0.0            # ... in the bands from here up (0: every band) ...
HAT_GATE_WINDOW = (-0.5, 0.5)  # ... over this window around the peak (s)
RIDE_BEATS, RIDE_MIN = 2.0, 4   # CY is a ride (blue) with this many CY hits within +-2 beats, itself included
TOM_WINDOW_S = 0.08          # tom pitch: the stem's first 80 ms after the hit ...
TOM_BAND_HZ = (60.0, 400.0)  # ... its strongest peak in this band ...
TOM_FFT = 8192
TOM_CLUSTER_RATIO = 1.18     # ... clusters split where neighbouring pitches differ by more than this
MAX_HANDS = 2
HAND_PRIORITY = ("Gcym", "Bcym", "red", "Ycym", "Ytom", "Btom", "Gtom")  # which hand pads stay on a crowded hit
DOUBLE_KICK_RATE = 6.0       # kicks a second (DESIGN.md 2.9)
PADS = {"kick": (0, False), "red": (1, False), "Ycym": (2, True), "Ytom": (2, False), "Bcym": (3, True),
        "Btom": (3, False), "Gcym": (4, True), "Gtom": (4, False)}


@dataclass(frozen=True)
class Settings:
    thresholds: tuple[float, ...] = THRESHOLDS     # BD, SD, TT, HH, CY
    from_mix: tuple[str, ...] = FROM_MIX           # the classes read from the mix; the rest from the drum stem
    merge_s: float = MERGE_S
    hat_gate_db: float | None = HAT_GATE_DB        # None: no stem evidence asked of the mix's HH and CY
    hat_gate_hz: float = HAT_GATE_HZ
    hat_gate_window: tuple[float, float] = HAT_GATE_WINDOW
    beat_s: float | None = None                    # the beat period for ride or crash; None: the mix's tempo
    double_kick_rate: float | None = DOUBLE_KICK_RATE  # None: no 2x kicks

    def check(self) -> None:
        if len(self.thresholds) != len(LABELS) or not all(0 < t < 1 for t in self.thresholds):
            raise ValueError(f"thresholds are five peak heights in (0, 1) for {', '.join(LABELS)}, not "
                             f"{self.thresholds}")
        if not set(self.from_mix) <= set(LABELS):
            raise ValueError(f"from_mix names classes among {', '.join(LABELS)}, not {self.from_mix}")
        if not 0 <= self.merge_s <= 0.1:
            raise ValueError(f"merge_s is 0 to 0.1 s, not {self.merge_s}")
        if self.hat_gate_db is not None and self.hat_gate_db <= 0:
            raise ValueError(f"hat_gate_db is a positive number of dB or None, not {self.hat_gate_db}")
        a, b = self.hat_gate_window
        if not -2 <= a <= 0 <= b <= 2 or self.hat_gate_hz < 0:
            raise ValueError(f"hat_gate_window runs from at most 0 to at least 0 within +-2 s, and hat_gate_hz is "
                             f"0 Hz or more, not {self.hat_gate_window} and {self.hat_gate_hz}")
        if self.beat_s is not None and not 0.2 <= self.beat_s <= 1.5:
            raise ValueError(f"beat_s is a beat period of 0.2 to 1.5 s or None, not {self.beat_s}")
        if self.double_kick_rate is not None and self.double_kick_rate <= 0:
            raise ValueError(f"double_kick_rate is kicks a second or None, not {self.double_kick_rate}")


@dataclass(frozen=True)
class Hit:
    time: float                                 # seconds of the input audio
    pads: tuple[tuple[int, bool, bool], ...]    # (pad, cymbal, double kick), pads in order


def beat_period(mix: np.ndarray, sample_rate: int = 44100) -> float:
    """The mix's beat period (s): beatgrid's tempo of its onset envelope, in 85-185 BPM."""
    from ..beatgrid import estimate_tempo, onset_features
    f = onset_features(mix, sample_rate)
    return 60.0 / estimate_tempo(f.env, f.fps)


def stem_level_db(stem_bands: np.ndarray, mix_bands: np.ndarray, band_hz: np.ndarray, settings: Settings,
                  fps: int) -> np.ndarray:
    """Per frame, the drum stem's power against the mix's in dB, in the bands from settings.hat_gate_hz up, summed
    over settings.hat_gate_window around the frame. Bands are log10(1 + magnitude), shape (frames, bands); -inf
    where the stem is silent there."""
    use = band_hz >= settings.hat_gate_hz
    a, b = (int(round(w * fps)) for w in settings.hat_gate_window)

    def windowed(bands):
        p = ((10.0 ** bands[:, use].astype(np.float64) - 1.0) ** 2).sum(axis=1)
        c = np.concatenate([[0.0], np.cumsum(np.concatenate([np.zeros(-a), p, np.zeros(b)]))])
        return c[b - a + 1:] - c[:len(p)]

    s, m = windowed(stem_bands), windowed(mix_bands)
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(m > 0, 10 * np.log10(s / np.where(m > 0, m, 1.0)), -np.inf)


def merge(found: dict[str, tuple[np.ndarray, np.ndarray]], fps: int, merge_s: float) -> list[tuple[int, dict]]:
    """Hits: (frame of the first peak, {class: strongest activation}) from each class's (peak frames, activations).
    A peak less than merge_s after a hit's first peak joins it."""
    ev = sorted((int(f), lab, float(s)) for lab, (frames, strength) in found.items()
                for f, s in zip(frames, strength))
    tol = int(round(merge_s * fps))
    out: list[tuple[int, dict]] = []
    for f, lab, s in ev:
        if out and f - out[-1][0] < tol:
            out[-1][1][lab] = max(s, out[-1][1].get(lab, 0.0))
        else:
            out.append((f, {lab: s}))
    return out


def ride_or_crash(times: np.ndarray, beat_s: float) -> list[str]:
    """Bcym for a CY hit in a regular run, Gcym otherwise."""
    times = np.asarray(times, dtype=np.float64)
    return ["Bcym" if np.sum(np.abs(times - t) <= RIDE_BEATS * beat_s) >= RIDE_MIN else "Gcym" for t in times]


def tom_pitch(starts: list[int], x: np.ndarray, sample_rate: int) -> np.ndarray:
    """The dominant TOM_BAND_HZ peak (Hz) in the first TOM_WINDOW_S of x after each start sample (NaN when the
    audio ends first)."""
    n = int(TOM_WINDOW_S * sample_rate)
    f = np.fft.rfftfreq(TOM_FFT, 1 / sample_rate)
    band = (f >= TOM_BAND_HZ[0]) & (f <= TOM_BAND_HZ[1])
    out = []
    for a in starts:
        seg = x[a:a + n]
        if len(seg) < 512:
            out.append(np.nan)
            continue
        s = np.abs(np.fft.rfft(seg * np.hanning(len(seg)), n=TOM_FFT))
        out.append(f[band][np.argmax(s[band])])
    return np.array(out, dtype=np.float64)


def tom_lanes(pitch: np.ndarray) -> list[str]:
    """Toms by pitch cluster: up to two cuts at the widest gaps over TOM_CLUSTER_RATIO on a log scale; lowest Gtom,
    highest Ytom, middle Btom."""
    if len(pitch) == 0:
        return []
    fill = np.nanmedian(pitch) if np.isfinite(pitch).any() else 100.0
    lp = np.log(np.nan_to_num(pitch, nan=fill))
    srt = np.sort(lp)
    gaps = np.diff(srt)
    cuts = sorted(srt[i] + gaps[i] / 2 for i in np.argsort(gaps)[::-1][:2] if gaps[i] > np.log(TOM_CLUSTER_RATIO))
    names = {1: ["Gtom"], 2: ["Gtom", "Ytom"], 3: ["Gtom", "Btom", "Ytom"]}[len(cuts) + 1]
    return [names[i] for i in np.searchsorted(cuts, lp)]


def double_kicks(times: np.ndarray, rate: float) -> np.ndarray:
    """Which kicks (sorted times, s) are 2x kicks. A run of kicks each less than 1/rate after the one before that
    holds more than `rate` of them (about a second or more of kicks faster than `rate` a second) gets them: a kick
    less than 1/rate after the run's last single-pedal kick. Shorter bursts stay single."""
    times = np.asarray(times, dtype=np.float64)
    out = np.zeros(len(times), dtype=bool)
    i = 0
    while i < len(times):
        j = i
        while j + 1 < len(times) and times[j + 1] - times[j] < 1 / rate:
            j += 1
        if j - i + 1 > rate:
            last = times[i]
            for k in range(i + 1, j + 1):
                if times[k] - last < 1 / rate:
                    out[k] = True
                else:
                    last = times[k]
        i = j + 1
    return out


def lanes(found: dict[str, tuple[np.ndarray, np.ndarray]], fps: int, settings: Settings, beat_s: float,
          stem: np.ndarray, sample_rate: int, level_db: np.ndarray | None = None) -> tuple[list[Hit], dict]:
    """The hits with their pads, and counts of what each rule did.

    found: class -> (peak frames, activations at them), each class from the signal settings.from_mix says.
    stem: the drum stem, mono, for the tom pitches. level_db: stem_level_db per frame (needed for hat_gate_db).
    """
    counts = {"peaks": {lab: int(len(found.get(lab, ((), ()))[0])) for lab in LABELS}}
    found = dict(found)
    if settings.hat_gate_db is not None:
        if level_db is None:
            raise ValueError("hat_gate_db needs the stem's level against the mix (stem_level_db)")
        gated = {}
        for lab in settings.from_mix:
            if lab not in ("HH", "CY") or lab not in found:
                continue
            frames, strength = found[lab]
            keep = level_db[np.minimum(frames, len(level_db) - 1)] >= -settings.hat_gate_db
            gated[lab] = int((~keep).sum())
            found[lab] = (frames[keep], strength[keep])
        counts["hat_gate_removed"] = gated
    hits = merge(found, fps, settings.merge_s)
    hop = sample_rate / fps
    cy = [f for f, c in hits if "CY" in c]
    cy_lane = dict(zip(cy, ride_or_crash(np.array(cy) / fps, beat_s)))
    tt = [f for f, c in hits if "TT" in c]
    tt_lane = dict(zip(tt, tom_lanes(tom_pitch([int(round(f * hop)) for f in tt], stem, sample_rate))))
    rank = {lab: i for i, lab in enumerate(HAND_PRIORITY)}
    out: list[tuple[int, list[str]]] = []
    hh_cy = hands_cut = same_pad = 0
    for f, c in hits:
        c = dict(c)
        if "HH" in c and "CY" in c:
            del c["HH" if c["CY"] >= c["HH"] else "CY"]
            hh_cy += 1
        names = {lab for cls, lab in (("BD", "kick"), ("SD", "red"), ("HH", "Ycym")) if cls in c}
        if "CY" in c:
            names.add(cy_lane[f])
        if "TT" in c:
            names.add(tt_lane[f])
        hands = sorted((n for n in names if n != "kick"), key=rank.__getitem__)
        if len(hands) > MAX_HANDS:
            hands_cut += len(hands) - MAX_HANDS
            names -= set(hands[MAX_HANDS:])
        kept, used = [], set()
        for n in sorted(names, key=lambda n: (not n.endswith("cym"), n)):  # a cymbal wins a shared pad
            if PADS[n][0] in used:
                same_pad += 1
                continue
            used.add(PADS[n][0])
            kept.append(n)
        out.append((f, kept))
    kick_frames = [f for f, names in out if "kick" in names]
    doubles = set()
    if settings.double_kick_rate is not None:
        flags = double_kicks(np.array(kick_frames, dtype=np.float64) / fps, settings.double_kick_rate)
        doubles = {f for f, d in zip(kick_frames, flags) if d}
    result = [Hit(f / fps, tuple(sorted((PADS[n][0], PADS[n][1], n == "kick" and f in doubles) for n in names)))
              for f, names in out]
    counts.update(hits=len(result), hh_cy_both=hh_cy, hands_dropped=hands_cut, same_pad_dropped=same_pad,
                  double_kicks=len(doubles), toms=len(tt), cymbals=len(cy), ride=sum(v == "Bcym" for v in
                                                                                     cy_lane.values()))
    return result, counts


def drum_hits(hits: list[Hit], tick_of: Callable[[float], int]) -> list[DrumHit]:
    """The chart's DrumHits, sorted by tick and pad."""
    notes = [DrumHit(tick_of(h.time), pad, cymbal=cym, double_kick=dk) for h in hits for pad, cym, dk in h.pads]
    return sorted(notes, key=lambda n: (n.tick, n.pad))
