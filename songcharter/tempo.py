"""Tempo maps: the link between chart ticks and audio seconds.

A chart places every note at an integer tick. The tempo map ([SyncTrack] in a .chart) says how
long a tick lasts at each point, so it decides where every note lands in the audio. It holds:

  * tempo markers: (tick, BPM x 1000 as an integer, the .chart encoding),
  * time signatures: (tick, numerator, denominator), each on a measure boundary.

`TempoMap.from_beats` builds one from detected beat times. It writes as few markers as it can
while keeping every beat within a tolerance of its detected time. It rounds each BPM to the
format's 0.001 and feeds the rounding error forward, so the error never accumulates over a song.
"""
from __future__ import annotations

import bisect
import math
from dataclasses import dataclass, field

import numpy as np

DEFAULT_RESOLUTION = 192  # ticks per quarter note, Moonscraper's default


@dataclass(frozen=True)
class Tempo:
    tick: int
    bpm_milli: int  # BPM x 1000, as written in `B` events

    @property
    def bpm(self) -> float:
        return self.bpm_milli / 1000

    @property
    def seconds_per_beat(self) -> float:
        return 60000 / self.bpm_milli


@dataclass(frozen=True)
class TimeSignature:
    tick: int
    numerator: int
    denominator: int = 4

    @property
    def den_log2(self) -> int:
        return int(round(math.log2(self.denominator)))


@dataclass
class TempoMap:
    resolution: int
    tempos: list[Tempo]
    time_signatures: list[TimeSignature] = field(default_factory=lambda: [TimeSignature(0, 4)])
    anchors: bool = True  # write `A` anchors at the markers (Moonscraper uses them; games ignore them)

    def __post_init__(self) -> None:
        if self.resolution <= 0:
            raise ValueError("resolution must be positive")
        if not self.tempos or self.tempos[0].tick != 0:
            raise ValueError("the first tempo marker must be at tick 0")
        if not self.time_signatures or self.time_signatures[0].tick != 0:
            raise ValueError("the first time signature must be at tick 0")
        for a, b in zip(self.tempos, self.tempos[1:]):
            if b.tick <= a.tick:
                raise ValueError(f"tempo markers must have increasing ticks ({a.tick} then {b.tick})")
        for t in self.tempos:
            if t.bpm_milli <= 0:
                raise ValueError(f"tempo at tick {t.tick} must be positive")
        prev = None
        for ts in self.time_signatures:
            if ts.numerator <= 0 or ts.denominator <= 0 or ts.denominator & (ts.denominator - 1):
                raise ValueError(f"bad time signature {ts.numerator}/{ts.denominator} at tick {ts.tick}")
            if self.resolution * 4 * ts.numerator % ts.denominator:
                raise ValueError(f"{ts.numerator}/{ts.denominator} gives a fractional measure at resolution {self.resolution}")
            if prev is not None:
                if ts.tick <= prev.tick:
                    raise ValueError("time signatures must have increasing ticks")
                if (ts.tick - prev.tick) % self.measure_length(prev):
                    raise ValueError(f"time signature at tick {ts.tick} is not on a measure boundary")
            prev = ts
        # seconds at each tempo marker, for fast conversion
        secs = [0.0]
        for a, b in zip(self.tempos, self.tempos[1:]):
            secs.append(secs[-1] + (b.tick - a.tick) / self.resolution * a.seconds_per_beat)
        self._ticks = [t.tick for t in self.tempos]
        self._secs = secs

    def measure_length(self, ts: TimeSignature) -> int:
        return self.resolution * 4 * ts.numerator // ts.denominator

    def tick_to_sec(self, tick: float) -> float:
        i = bisect.bisect_right(self._ticks, tick) - 1
        i = max(i, 0)
        t = self.tempos[i]
        return self._secs[i] + (tick - t.tick) / self.resolution * t.seconds_per_beat

    def sec_to_tick(self, sec: float) -> float:
        """Fractional tick at a time in seconds (before the first marker, the first tempo extends back)."""
        i = bisect.bisect_right(self._secs, sec) - 1
        i = max(i, 0)
        t = self.tempos[i]
        return t.tick + (sec - self._secs[i]) / t.seconds_per_beat * self.resolution

    def ticks_to_secs(self, ticks) -> np.ndarray:
        return np.array([self.tick_to_sec(float(x)) for x in np.asarray(ticks).ravel()])

    def secs_to_ticks(self, secs) -> np.ndarray:
        return np.array([self.sec_to_tick(float(x)) for x in np.asarray(secs).ravel()])

    def time_signature_at(self, tick: int) -> TimeSignature:
        i = bisect.bisect_right([ts.tick for ts in self.time_signatures], tick) - 1
        return self.time_signatures[max(i, 0)]

    def measure_starts(self, end_tick: int) -> list[int]:
        """Ticks of every measure start from 0 up to end_tick."""
        out = []
        for i, ts in enumerate(self.time_signatures):
            stop = self.time_signatures[i + 1].tick if i + 1 < len(self.time_signatures) else end_tick + 1
            out.extend(range(ts.tick, min(stop, end_tick + 1), self.measure_length(ts)))
        return out

    def sync_track_lines(self) -> list[tuple[int, str]]:
        """[SyncTrack] entries as (tick, text), in Moonscraper's order within a tick: TS, A, B."""
        rows: list[tuple[int, int, str]] = []
        for ts in self.time_signatures:
            text = f"TS {ts.numerator}" if ts.denominator == 4 else f"TS {ts.numerator} {ts.den_log2}"
            rows.append((ts.tick, 0, text))
        for i, t in enumerate(self.tempos):
            if self.anchors and t.tick > 0:
                rows.append((t.tick, 1, f"A {round(self._secs[i] * 1e6)}"))
            rows.append((t.tick, 2, f"B {t.bpm_milli}"))
        rows.sort(key=lambda r: (r[0], r[1]))
        return [(tick, text) for tick, _, text in rows]

    @classmethod
    def from_beats(cls, beats, bars=None, resolution: int = DEFAULT_RESOLUTION, tolerance: float = 0.002,
                   anchors: bool = True) -> "TempoMap":
        """Tempo map with beat i at tick i x resolution.

        beats: beat times in seconds on the chart's audio timeline. beats[0] must be 0.0 (tick 0 is
               the audio's first sample; `plan_lead_in` arranges that) and the list must be strictly
               increasing.
        bars:  beats per measure, as a list of (beat index, beats per measure) changes. The first
               must be at beat 0. Defaults to 4/4 throughout.
        tolerance: largest allowed error, in seconds, between a beat and its tick's time.
        """
        b = np.asarray(beats, dtype=np.float64)
        if b.ndim != 1 or len(b) < 2:
            raise ValueError("need at least two beats")
        if abs(b[0]) > 1e-6:
            raise ValueError("beats[0] must be at 0 s (tick 0)")
        if np.any(np.diff(b) <= 0):
            raise ValueError("beats must be strictly increasing")
        b = b.copy()
        b[0] = 0.0
        n = len(b)
        tempos: list[Tempo] = []
        s, t_map = 0, 0.0  # current segment start (beat index) and the map's time there
        while s < n - 1:
            best = None
            e = s + 1
            while e < n:
                period = (b[e] - t_map) / (e - s)
                bpm_milli = max(1, round(60000 / period))
                p = 60000 / bpm_milli
                k = np.arange(s + 1, e + 1)
                err = np.abs(t_map + (k - s) * p - b[s + 1:e + 1])
                if e > s + 1 and err.max() > tolerance:
                    break
                best = (e, bpm_milli, p)
                e += 1
            e, bpm_milli, p = best
            if not tempos or tempos[-1].bpm_milli != bpm_milli:
                tempos.append(Tempo(s * resolution, bpm_milli))
            t_map += (e - s) * p
            s = e
        bars = bars or [(0, 4)]
        if bars[0][0] != 0:
            raise ValueError("the first bar change must be at beat 0")
        sigs = []
        for idx, num in bars:
            if not sigs or sigs[-1].numerator != num:
                sigs.append(TimeSignature(idx * resolution, num))
        return cls(resolution, tempos, sigs, anchors)


@dataclass(frozen=True)
class LeadIn:
    """How the song audio is shifted so tick 0 is a measure start at the audio's first sample."""
    pad_samples: int       # silence to put in front of the decoded song
    sample_rate: int
    beats: list[float]     # beat times on the padded timeline; beats[0] == 0.0
    bars: list[tuple[int, int]]  # (beat index, beats per measure) changes on the padded timeline
    first_beat: int        # index in `beats` of the song's first detected beat

    @property
    def pad_seconds(self) -> float:
        return self.pad_samples / self.sample_rate


def plan_lead_in(beats, downbeats, sample_rate: int, min_lead: float = 2.5, duration: float | None = None) -> LeadIn:
    """Choose the leading silence and extend the beat grid back to the padded audio's start.

    beats:     detected beat times (seconds, original audio timeline), increasing.
    downbeats: indices into `beats` that start a measure, increasing.
    min_lead:  the first detected beat lands at least this late in the padded audio. Clone Hero
               needs a moment before the first note, and scan-chart flags notes in the first second.
    duration:  the original audio's length; if given, the grid is extended past the last beat to it.

    The grid before the first downbeat is extrapolated with the opening tempo, in whole measures of
    the opening meter, so the padded audio starts on a measure line. Detected pickup beats before
    the first downbeat are replaced by that grid (they agree with it up to the tracker's jitter).
    """
    b = np.asarray(beats, dtype=np.float64)
    d = sorted(int(i) for i in downbeats)
    if len(b) < 4 or not d:
        raise ValueError("need at least four beats and one downbeat")
    f = d[0]
    bar0 = (d[1] - d[0]) if len(d) > 1 else 4
    p0 = float(np.median(np.diff(b[f:f + 9])))  # opening beat period
    measure = bar0 * p0
    # smallest whole number of opening measures before the first downbeat that leaves at least
    # min_lead of silence in front of the song (the song may make sound from its first sample)
    m = max(1, math.ceil((min_lead + b[f]) / measure - 1e-9))
    pad = m * measure - b[f]
    pad_samples = int(round(pad * sample_rate))
    pad = pad_samples / sample_rate
    lead_beats = m * bar0
    grid = [b[f] + pad - j * p0 for j in range(lead_beats, 0, -1)]
    grid[0] = 0.0
    out = grid + list(b[f:] + pad)
    if duration is not None:
        p_last = float(np.median(np.diff(b[-9:])))
        end = duration + pad
        while out[-1] < end:  # until a beat at or past the end, so trailing notes have a grid
            out.append(out[-1] + p_last)
    # measures: the lead-in, then the detected downbeats
    bars = [(0, bar0)]
    for a, c in zip(d, d[1:]):
        num = c - a
        if num != bars[-1][1]:
            bars.append((a - f + lead_beats, num))
    return LeadIn(pad_samples, sample_rate, [float(x) for x in out], bars, lead_beats)
