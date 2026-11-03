"""Pictures of a built chart beside its audio, to see where it works and where it does not.

    python -m songcharter.preview <song folder> [--out DIR] [--difficulty expert] [--page 60]

  * **Overview** (`overview.png`): the whole song, one row per instrument. Bars are notes per beat in each measure;
    the black step over them is the instrument's stem level in each measure (its peak against the stem's loud level,
    P95), with the raw level in grey behind. Three kinds of measure are flagged:
      - a **gap**: the chart has no note, not even a sustain held from before, and the stem plays: 10% or more of the
        measure within 15 dB of its P95, with two or more new attacks (onset peaks whose level reaches that, above
        the stem's floor: hum or bleed switching on is no attack);
      - **rings past its sustain** (guitar and bass): as loud, but with no new attack, the level carrying on from the
        last note's end: the sustain stops before the sound does. A drum stem that rings on is not flagged;
      - **notes in silence**: notes while the stem stays 25 dB or more below its P95 (assemble's SILENT_DB).
    Sections, star power, the tempo map and the end of song.ogg are drawn too. The flagged stretches also come back
    as text (`flags`), with **notes after audio** for notes that run past the end of song.ogg.
  * **Pages** (`page_01.png`, ...): a minute per page in strips of 15 s. Each instrument's lanes as Clone Hero shows
    them (green, red, yellow, blue, orange; drums with cymbals as triangles and toms as circles, the kick as a bar),
    sustains as lines, HOPOs hollow, star power shaded, drum fills hatched, beat and measure lines, section names,
    and under each instrument its stem's onset strength, so a note can be checked against the hit it belongs to.

Times are song seconds (what the player hears: song.ogg, chart time), drawn to the end of song.ogg, the chart or the
stems, whichever is last. Measure lines follow the chart's own time signatures. The stems come from the folder's
report.json (written by assemble, with the lead-in pad that moves input seconds onto the song), or from `stems=`
(input seconds; `pad=` defaults to the report's pad, else 0); without stems only the notes are drawn. Guitar is judged
against everything but drums, bass and vocals: the 6-stem set's guitar, other and piano summed (what htdemucs_ft's
"other" holds), or "other" alone in a 4-stem set. Needs matplotlib and librosa (`pip install songcharter[preview]`).
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass, field
from pathlib import Path, PureWindowsPath

import numpy as np

from . import audio as A
from .importers import read_song
from .timed import DIFFICULTIES, TimedHit, TimedSong

INSTRUMENTS = ("guitar", "bass", "drums")
STEMS_FOR = {"guitar": ("guitar", "other"), "bass": ("bass",), "drums": ("drums",)}  # as assemble.STEMS_FOR
GUITAR_MIX = ("guitar", "other", "piano")  # with a 6-stem set, guitar is judged against these summed
GAP_DB = -15.0       # a frame within this of the stem's P95 is "playing"
GAP_SHARE = 0.10     # a gap needs this share of the measure's frames playing...
GAP_ATTACKS = 2      # ...and this many new attacks in it
ONSET_PEAK = 0.3     # an attack: a peak of the onset strength (0..1) above this, at least ATTACK_AFTER after the
ATTACK_AFTER = 0.05  # last note's end, the level just after it reaching GAP_DB and more than FLOOR_DB above the
FLOOR_DB = 3.0       # stem's floor (hum or bleed switching on is no attack)
FLOOR_PCT = 20       # the floor: this percentile of the levels in measures with no notes
RING_DB = 6.0        # rings: the level at the measure's start within RING_DB of the level at the last note's end,
RING_DROP_DB = 10.0  # never more than RING_DROP_DB below it in between, and the note still sounding at its end
SILENT_DB = -25.0    # a measure with notes whose stem stays below this is "notes in silence" (assemble's SILENT_DB)
EDGE = 0.05          # seconds at each end of a measure left out of its level (the envelope's frames reach across)
HEAD_S = 0.05        # a note head's radius in seconds on a page: a head this close before a strip still shows there
ENV_SR, ENV_HOP = 22050, 256
LANE_COLORS = ["#21a336", "#e0312b", "#e8c21a", "#2f6fdc", "#f08a1c"]   # green, red, yellow, blue, orange
OPEN_COLOR = "#9b4fd6"
PAD_NAMES = ["kick", "red", "yellow", "blue", "green"]
DRUM_COLORS = ["#f08a1c", "#e0312b", "#e8c21a", "#2f6fdc", "#21a336"]
FLAG_COLORS = {"gap": "#e0312b", "rings past its sustain": "#f08a1c", "notes in silence": "#9b4fd6"}
PEAK_COLOR = "#111111"   # each measure's peak level on the overview
RAW_COLOR = "#bbbbbb"    # the raw level behind the bars


@dataclass
class Envelope:
    times: np.ndarray        # song seconds
    level_db: np.ndarray     # RMS dB against the stem's P95 (0 = loud)
    onset: np.ndarray        # onset strength, 0..1 (its 99th percentile = 1)
    peaks: np.ndarray        # frame indices of the onset strength's peaks above ONSET_PEAK


@dataclass
class Preview:
    folder: Path
    song: TimedSong                     # chart time (song seconds)
    beats: np.ndarray                   # song seconds of every beat on the tempo map
    measures: np.ndarray                # song seconds of every measure line before `duration`
    duration: float                     # the end of song.ogg, the chart or the stems, whichever is last
    envelopes: dict[str, Envelope] = field(default_factory=dict)   # instrument -> its stem's envelope
    stems: dict[str, str] = field(default_factory=dict)            # instrument -> stem name used ("a+b": summed)
    audio_end: float | None = None      # song.ogg's length; None without one
    missing: dict[str, str] = field(default_factory=dict)          # stem -> path report.json lists but not found


@dataclass(frozen=True)
class Flag:
    instrument: str
    kind: str          # "gap", "rings past its sustain", "notes in silence" or "notes after audio"
    start: float       # song seconds
    end: float
    measures: int

    def __str__(self) -> str:
        return f"{self.instrument}: {self.kind} {_mmss(self.start)}-{_mmss(self.end)} ({self.measures} measures)"


def _mmss(t: float) -> str:
    t = round(max(0.0, t), 1)
    m = int(t // 60)
    return f"{m}:{t - 60 * m:04.1f}"


def _envelope(y: np.ndarray, shift: float, duration: float) -> Envelope:
    """y: mono at A.SAMPLE_RATE, in input seconds; shift: what moves it onto the song."""
    import librosa
    from scipy.signal import find_peaks
    x = librosa.resample(np.asarray(y, dtype=np.float32), orig_sr=A.SAMPLE_RATE, target_sr=ENV_SR)
    rms = librosa.feature.rms(y=x, frame_length=4 * ENV_HOP, hop_length=ENV_HOP)[0]
    db = 20 * np.log10(rms + 1e-9)
    db -= np.percentile(db, 95)
    onset = librosa.onset.onset_strength(y=x, sr=ENV_SR, hop_length=ENV_HOP)
    n = min(len(db), len(onset))
    onset = np.clip(onset[:n] / (np.percentile(onset, 99) + 1e-9), 0, 1)
    times = np.arange(n) * ENV_HOP / ENV_SR + shift
    keep = times <= duration + 1
    onset = onset[keep]
    peaks, _ = find_peaks(onset, height=ONSET_PEAK, distance=3)
    return Envelope(times[keep], db[:n][keep], onset, peaks)


def _read_stem(y: np.ndarray | str | Path) -> np.ndarray:
    """A stem as mono float32 at A.SAMPLE_RATE: a WAV path at any rate, or an array taken to be at A.SAMPLE_RATE."""
    rate = A.SAMPLE_RATE
    if isinstance(y, (str, Path)):
        y, rate = A.read_wav(y)
    y = np.asarray(y, dtype=np.float32)
    y = y.mean(axis=0) if y.ndim == 2 else y
    if rate != A.SAMPLE_RATE:
        import librosa
        y = librosa.resample(y, orig_sr=rate, target_sr=A.SAMPLE_RATE)
    return y


def _find_stem(folder: Path, path: str | None) -> Path | None:
    """A stem report.json lists: its path, else a file of that name in the song folder or its stems/ folder (the
    report of a folder copied from another machine names that machine's paths, Windows or POSIX)."""
    if not path:
        return None
    name = PureWindowsPath(path).name
    return next((p for p in (Path(path), folder / name, folder / "stems" / name) if p.is_file()), None)


def _stem_names(instrument: str, stems) -> list[str]:
    if instrument == "guitar" and "guitar" in stems:
        return [s for s in GUITAR_MIX if s in stems]
    return next(([s] for s in STEMS_FOR[instrument] if s in stems), [])


def _audio_length(path: Path) -> float:
    try:
        import soundfile as sf
        info = sf.info(str(path))
        return info.frames / info.samplerate
    except (ImportError, RuntimeError):  # a format libsndfile cannot read: decode it
        return A.decode(path).shape[1] / A.SAMPLE_RATE


def _chart_end(song: TimedSong) -> float:
    """The latest note or sustain end, phrase end or section in the chart."""
    ends = [getattr(n, "end", None) or n.time for p in song.parts.values() for n in p.notes]
    ends += [s.end for p in song.parts.values() for s in p.star_power + p.solos + p.activation]
    return max(ends + [t for t, _ in song.sections], default=0.0)


def _part_end(part) -> float:
    return max((getattr(n, "end", None) or n.time for n in part.notes), default=0.0)


def _extend(times: np.ndarray, end: float) -> np.ndarray:
    """A grid (beats, measure lines) that stops before `end`, carried on past it with its last step: a tempo map
    that ends early keeps its last tempo and meter."""
    if len(times) < 2 or times[-1] >= end:
        return times
    step = times[-1] - times[-2]
    return np.concatenate([times, times[-1] + step * np.arange(1, int((end - times[-1]) / step) + 2)])


def load(folder: Path | str, stems: dict[str, np.ndarray | str | Path] | None = None, pad: float | None = None
         ) -> Preview:
    """The chart in `folder` and, if available, each instrument's stem envelope.
    stems: stem name -> array (at A.SAMPLE_RATE) or WAV path, in input seconds; by default the stems in the folder's
    report.json, when there is one. pad: the lead-in that moves them onto the song; by default the report's."""
    folder = Path(folder)
    song = read_song(folder)
    report = folder / "report.json"
    r = json.loads(report.read_text(encoding="utf-8")) if report.exists() else {}
    missing = {}
    if stems is None:
        listed = {k: v.get("path") for k, v in (r.get("stems") or {}).items() if isinstance(v, dict)}
        found = {k: _find_stem(folder, p) for k, p in listed.items()}
        stems = {k: p for k, p in found.items() if p is not None}
        missing = {k: listed[k] or "" for k, p in found.items() if p is None}
    if pad is None:
        pad = (r.get("lead_in") or {}).get("pad_seconds", 0.0)
    pad = float(pad or 0.0)
    arrays = {}
    for inst in INSTRUMENTS:
        names = _stem_names(inst, stems)
        if names and any(i == inst for i, _ in song.parts):
            ys = [_read_stem(stems[s]) for s in names]
            mix = np.zeros(max(len(y) for y in ys), dtype=np.float32)
            for y in ys:  # summed in time, so leakage in a quiet stem stays under the others' level
                mix[:len(y)] += y
            arrays[inst] = ("+".join(names), mix)
    ogg = folder / "song.ogg"
    audio_end = _audio_length(ogg) if ogg.exists() else None
    duration = max([_chart_end(song) + 2] + [len(y) / A.SAMPLE_RATE + pad for _, y in arrays.values()]
                   + ([audio_end] if audio_end is not None else []))
    beats = _extend(np.array(song.beats, dtype=float), duration)
    measures = _extend(np.array(song.measures or list(song.beats[::4]), dtype=float), duration)
    measures = measures[(measures < duration) | (np.arange(len(measures)) == 0)]
    pv = Preview(folder, song, beats, measures, duration, audio_end=audio_end, missing=missing)
    for inst, (name, y) in arrays.items():
        pv.envelopes[inst] = _envelope(y, pad, duration)
        pv.stems[inst] = name
    return pv


def _rings(env: Envelope, note: float, end: float, start: float, floor: float) -> bool:
    """Whether a note's own sound carries on from its end (`end`; its onset `note`) to `start`: at its end still
    within RING_DROP_DB of its own peak, loud and above the stem's floor; about as loud at `start`; never far below
    in between. Hum that takes over once a note has died away, or stops at once, is no ring."""
    k, i, j = np.searchsorted(env.times, [note, end, start])
    if j >= len(env.times) or j < i:
        return False
    at_end = env.level_db[i]
    return bool(at_end >= max(GAP_DB, floor + FLOOR_DB, env.level_db[k:i + 1].max() - RING_DROP_DB)
                and abs(env.level_db[j] - at_end) <= RING_DB and env.level_db[i:j + 1].min() >= at_end - RING_DROP_DB)


def measure_stats(pv: Preview, instrument: str, difficulty: str = "expert") -> list[dict]:
    """Per measure: start and end (song seconds), onsets, notes per beat, whether a sustain from before is still held
    in it, and from the stem (None without one): its peak and mean level (dB against its P95), the share of its
    frames within GAP_DB of the P95, its new attacks and whether its level rings on from the last note's end.
    A part the chart does not have gives no measures."""
    part = pv.song.parts.get((instrument, difficulty))
    if part is None:
        return []
    onsets = np.array(sorted({round(n.time, 4) for n in part.notes}))
    spans = sorted((n.time, getattr(n, "end", None) or n.time) for n in part.notes)
    starts = np.array([t for t, _ in spans])
    latest = [0] * len(spans)  # latest[i]: of the first i + 1 notes, the one that ends last
    for i in range(1, len(spans)):
        latest[i] = i if spans[i][1] >= spans[latest[i - 1]][1] else latest[i - 1]
    env = pv.envelopes.get(instrument)
    edges = list(pv.measures) + [pv.duration]
    out, frames = [], []
    for a, b in zip(edges, edges[1:]):
        if b <= a:
            continue
        n = int(np.sum((onsets >= a - 1e-3) & (onsets < b - 1e-3)))  # a note on the measure line belongs to it
        beats = max(1, int(np.sum((pv.beats >= a - 1e-6) & (pv.beats < b - 1e-6))))
        k = int(np.searchsorted(starts, a - 1e-3))  # the notes before the measure
        note, last = spans[latest[k - 1]] if k else (None, None)
        row = {"start": float(a), "end": float(b), "onsets": n, "per_beat": n / beats,
               "held": last is not None and last > a, "last_end": last, "peak_db": None, "mean_db": None,
               "loud_share": None, "attacks": None, "rings": None}
        m = None
        if env is not None:
            m = (env.times >= a + EDGE) & (env.times < b - EDGE)
            if m.any():
                lv = env.level_db[m]
                row.update(peak_db=float(lv.max()), mean_db=float(lv.mean()), loud_share=float(np.mean(lv >= GAP_DB)))
            else:
                m = None
        out.append(row)
        frames.append((m, note))
    if env is None:
        return out
    quiet = [m for row, (m, _) in zip(out, frames) if m is not None and row["onsets"] == 0 and not row["held"]]
    floor = float(np.percentile(env.level_db[np.any(quiet, axis=0)], FLOOR_PCT)) if quiet else -np.inf
    peak_times = env.times[env.peaks]
    rise = np.array([env.level_db[i:i + 4].max() for i in env.peaks])  # the level just after each peak
    for row, (m, note) in zip(out, frames):
        if m is None:
            continue
        a, b, last = row["start"], row["end"], row["last_end"]
        t0 = a + EDGE if last is None else max(a + EDGE, last + ATTACK_AFTER)
        row["attacks"] = int(np.sum((peak_times >= t0) & (peak_times < b - EDGE)
                                    & (rise >= max(GAP_DB, floor + FLOOR_DB))))
        row["rings"] = last is not None and _rings(env, note, last, a + EDGE, floor)
    return out


def _kind(row: dict, instrument: str) -> str | None:
    if row["peak_db"] is None:
        return None
    if row["onsets"] == 0 and not row["held"] and row["loud_share"] >= GAP_SHARE:
        if row["attacks"] >= GAP_ATTACKS:
            return "gap"
        if instrument != "drums" and row["rings"]:
            return "rings past its sustain"
    elif row["onsets"] > 0 and row["peak_db"] < SILENT_DB:
        return "notes in silence"
    return None


def flags(pv: Preview, difficulty: str = "expert", min_measures: int = 1) -> list[Flag]:
    """Stretches of measures where the stem plays and the chart is empty (gap, or rings past its sustain), or the
    chart has notes and the stem is silent (notes in silence), merged across consecutive measures; and the notes
    after the end of song.ogg. Only parts the chart has at `difficulty` are judged."""
    out = []
    for inst in INSTRUMENTS:
        part = pv.song.parts.get((inst, difficulty))
        if part is None:
            continue
        end = _part_end(part)
        if pv.audio_end is not None and end > pv.audio_end:
            n = int(np.sum((pv.measures > pv.audio_end) & (pv.measures < end))) + 1
            out.append(Flag(inst, "notes after audio", pv.audio_end, end, n))
        if inst not in pv.envelopes:
            continue
        run: list[dict] = []
        kind = None
        for row in measure_stats(pv, inst, difficulty) + [None]:
            k = None if row is None else _kind(row, inst)
            if k != kind and run:
                if len(run) >= min_measures:
                    out.append(Flag(inst, kind, run[0]["start"], run[-1]["end"], len(run)))
                run = []
            kind = k
            if k is not None:
                run.append(row)
    return sorted(out, key=lambda f: (f.start, f.instrument))


def remarks(pv: Preview, difficulty: str = "expert") -> list[str]:
    """What the flags cannot say: a song.ogg shorter than the chart, levels the chart lacks, parts not judged."""
    out = []
    if pv.audio_end is not None and pv.audio_end < _chart_end(pv.song) - 1:
        stub = " (a stub?)" if pv.audio_end < 2 else ""
        out.append(f"song.ogg is {_mmss(pv.audio_end)} long{stub} but the chart runs to {_mmss(_chart_end(pv.song))}: "
                   f"drawn to {_mmss(pv.duration)}")
    levels = {i: [d for d in DIFFICULTIES if (i, d) in pv.song.parts] for i in INSTRUMENTS}
    if not any((i, difficulty) in pv.song.parts for i in INSTRUMENTS):
        have = sorted({d for ds in levels.values() for d in ds}, key=DIFFICULTIES.index)
        out.append(f"no instrument has a {difficulty} part (levels: {', '.join(have) or 'none'})")
    else:
        for inst, ds in levels.items():
            if ds and difficulty not in ds:
                out.append(f"{inst}: no {difficulty} part (levels: {', '.join(ds)})")
    for inst in INSTRUMENTS:
        if (inst, difficulty) not in pv.song.parts or inst in pv.envelopes:
            continue
        names = GUITAR_MIX if inst == "guitar" else STEMS_FOR[inst]
        lost = [f"{s} at {pv.missing[s]}" for s in names if s in pv.missing]
        out.append(f"{inst} not judged: " + (f"report.json lists stem {', '.join(lost)}, not found" if lost
                                              else f"no {' or '.join(STEMS_FOR[inst])} stem"))
    return out


# ------------------------------------------------------------------------------------------------ drawing

def _plt():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    return plt


def _sections_in(pv: Preview, a: float, b: float):
    return [(t, n) for t, n in pv.song.sections if a <= t < b]


def render_overview(pv: Preview, path: Path | str, difficulty: str = "expert") -> list[Flag]:
    """overview.png: notes per beat per measure against each stem's level, flagged stretches, sections, tempo."""
    plt = _plt()
    insts = [i for i in INSTRUMENTS if (i, difficulty) in pv.song.parts]
    found = flags(pv, difficulty)
    fig, axes = plt.subplots(len(insts) + 1, 1, figsize=(18, 2.1 * len(insts) + 2.6), sharex=True,
                             gridspec_kw={"height_ratios": [2] * len(insts) + [1]}, layout="constrained")
    axes = np.atleast_1d(axes)
    cut = pv.audio_end is not None and pv.audio_end < pv.duration - 0.05
    for ax, inst in zip(axes, insts):
        rows = measure_stats(pv, inst, difficulty)
        x = [r["start"] for r in rows]
        w = [r["end"] - r["start"] for r in rows]
        ax.bar(x, [r["per_beat"] for r in rows], width=w, align="edge", color="#5b7bb5", alpha=0.85, label="notes/beat")
        ax.set_ylim(0, max(4.2, max([r["per_beat"] for r in rows], default=0) * 1.1))
        ax.set_ylabel(f"{inst}\nnotes/beat")
        for f in found:
            if f.instrument == inst and f.kind in FLAG_COLORS:
                ax.axvspan(f.start, f.end, color=FLAG_COLORS[f.kind], alpha=0.25, lw=0)
        part = pv.song.parts[(inst, difficulty)]
        for s in part.star_power:
            ax.axvspan(s.start, s.end, ymin=0.92, ymax=1.0, color="#20b2d8", alpha=0.9, lw=0)
        env = pv.envelopes.get(inst)
        if env is not None:
            back = ax.twinx()  # the raw level, behind the bars (a twin axes draws over its parent unless told)
            back.plot(env.times, np.clip(env.level_db, -45, 3), color=RAW_COLOR, lw=0.6)
            back.set_ylim(-45, 3)
            back.set_ylabel(f"{pv.stems[inst]} stem dB\n(vs its P95)", fontsize=8)
            ax.set_zorder(back.get_zorder() + 1)
            ax.patch.set_visible(False)
            front = ax.twinx()  # each measure's peak, the level the flags judge, and the thresholds, over the bars
            front.set_zorder(ax.get_zorder() + 1)
            peaks = [np.nan if r["peak_db"] is None else float(np.clip(r["peak_db"], -45, 3)) for r in rows]
            if rows:
                front.step(x + [rows[-1]["end"]], peaks + peaks[-1:], where="post", color=PEAK_COLOR, lw=1.4)
            front.axhline(GAP_DB, color=FLAG_COLORS["gap"], lw=1.2, ls=":")
            front.axhline(SILENT_DB, color=FLAG_COLORS["notes in silence"], lw=1.2, ls=":")
            front.set_ylim(-45, 3)
            front.axis("off")
        else:
            ax.text(0.995, 0.5, "no stem: not judged", transform=ax.transAxes, ha="right", va="center", fontsize=10,
                    color="#555555", bbox={"facecolor": "white", "edgecolor": "#999999", "pad": 3})
        for t, _ in pv.song.sections:
            ax.axvline(t, color="#888888", lw=0.5)
        if cut:
            ax.axvline(pv.audio_end, color="#000000", lw=1.2, ls="--")
    top = axes[0]
    for t, name in pv.song.sections:
        top.text(t, top.get_ylim()[1], f" {name}", fontsize=7, rotation=45, va="bottom", ha="left")
    tax = axes[-1]
    if len(pv.beats) > 1:
        mid = (pv.beats[1:] + pv.beats[:-1]) / 2
        tax.plot(mid, 60 / np.diff(pv.beats), color="#2f6fdc", lw=0.8)
    if cut:
        tax.axvline(pv.audio_end, color="#000000", lw=1.2, ls="--")
        tax.text(pv.audio_end, 0.5, " song.ogg ends", transform=tax.get_xaxis_transform(), fontsize=8, va="center")
    tax.set_ylabel("tempo\nBPM")
    tax.set_xlabel("song time (m:ss)")
    ticks = np.arange(0, pv.duration + 1, 30)
    tax.set_xticks(ticks, [_mmss(t)[:-2] for t in ticks])
    tax.set_xlim(0, pv.duration)
    fig.suptitle(f"{pv.folder.name}: {difficulty}. Bars = notes per beat; black = the stem's peak level per measure "
                 "(grey: its raw level).\nRed = gap (stem plays, no notes); orange = rings past its sustain; "
                 "purple = notes in silence; cyan = star power", fontsize=10)
    fig.savefig(path, dpi=90)
    plt.close(fig)
    return found


def _draw_frets(ax, part, y0: float, a: float, b: float) -> None:
    for n in part.notes:
        end = n.end if n.end is not None and n.end > n.time else None
        if n.time >= b or max(n.time, end or n.time) < a - HEAD_S:
            continue
        lanes = [5 if f not in range(5) else f for f in n.frets]
        for lane in lanes:
            y = y0 + lane
            color = OPEN_COLOR if lane == 5 else LANE_COLORS[lane]
            if end is not None:  # a sustain from an earlier strip carries on here
                ax.plot([max(n.time, a), min(end, b)], [y, y], color=color, lw=4, alpha=0.45, solid_capstyle="butt")
            if n.time < a - HEAD_S:
                continue
            if n.tap:
                ax.scatter([n.time], [y], marker="D", s=46, color=color, edgecolors="black", linewidths=0.6, zorder=3)
            elif n.hopo:
                ax.scatter([n.time], [y], marker="o", s=34, facecolors="white", edgecolors=color, linewidths=2,
                           zorder=3)
            else:
                ax.scatter([n.time], [y], marker="o", s=46, color=color, edgecolors="black", linewidths=0.6, zorder=3)


def _draw_drums(ax, part, y0: float, a: float, b: float) -> None:
    for h in part.notes:
        if not (a <= h.time < b):
            continue
        y = y0 + h.pad
        if h.pad == 0:
            ax.plot([h.time - 0.03, h.time + 0.03], [y, y], color=DRUM_COLORS[0], lw=5, solid_capstyle="butt",
                    zorder=3)
        else:
            ax.scatter([h.time], [y], marker="^" if h.cymbal else "o", s=50, color=DRUM_COLORS[h.pad],
                       edgecolors="black", linewidths=0.6, zorder=3)


def render_pages(pv: Preview, out: Path | str, difficulty: str = "expert", page_s: float = 60.0,
                 strip_s: float = 15.0) -> list[Path]:
    """page_NN.png: page_s seconds per page, strips of strip_s seconds, every instrument's lanes over its stem. A page
    that is not a whole number of strips ends on a shorter strip, drawn to the same scale."""
    if not (page_s > 0 and strip_s > 0 and math.isfinite(page_s) and math.isfinite(strip_s)):
        raise ValueError(f"page and strip lengths must be positive seconds, not {page_s} and {strip_s}")
    plt = _plt()
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    insts = [i for i in INSTRUMENTS if (i, difficulty) in pv.song.parts]
    if not insts:
        return []
    lanes = {"guitar": 6, "bass": 6, "drums": 5}
    block = {i: lanes[i] + 2.2 for i in insts}        # lanes, then the onset band, then a gap
    height = sum(block.values())
    strips = max(1, math.ceil(page_s / strip_s - 1e-9))
    cut = pv.audio_end is not None and pv.audio_end < pv.duration - 0.05  # song.ogg ends before the song: mark it
    paths = []
    for p in range(math.ceil(pv.duration / page_s - 1e-9)):
        fig, axes = plt.subplots(strips, 1, figsize=(18, 0.32 * height * strips + 0.8), layout="constrained")
        axes = np.atleast_1d(axes)
        for s, ax in enumerate(axes):
            a = p * page_s + s * strip_s
            b = min(a + strip_s, (p + 1) * page_s)  # what follows is on the next page
            if a >= pv.duration:
                ax.axis("off")
                continue
            ytick, ylab = [], []
            y = 0.0
            for inst in reversed(insts):
                part = pv.song.parts[(inst, difficulty)]
                env = pv.envelopes.get(inst)
                if env is not None:
                    m = (env.times >= a) & (env.times < b)
                    ax.fill_between(env.times[m], y, y + 1.4 * env.onset[m], color="#999999", alpha=0.6, lw=0)
                base = y + 1.8
                for sp in part.star_power:
                    if sp.end > a and sp.start < b:
                        ax.axvspan(max(sp.start, a), min(sp.end, b), ymin=(base - 0.5) / height,
                                   ymax=(base + lanes[inst] - 0.5) / height, color="#20b2d8", alpha=0.15, lw=0)
                for fill in part.activation:
                    if fill.end > a and fill.start < b:
                        ax.axvspan(max(fill.start, a), min(fill.end, b), ymin=(base - 0.5) / height,
                                   ymax=(base + lanes[inst] - 0.5) / height, facecolor="none", hatch="///",
                                   edgecolor="#9b4fd6", alpha=0.5, lw=0)
                if part.notes and isinstance(part.notes[0], TimedHit):
                    _draw_drums(ax, part, base, a, b)
                    names = PAD_NAMES
                else:
                    _draw_frets(ax, part, base, a, b)
                    names = ["G", "R", "Y", "B", "O", "open"]
                for k, nm in enumerate(names):
                    ytick.append(base + k)
                    ylab.append(f"{inst} {nm}" if k == 0 else nm)
                ytick.append(y + 0.6)
                ylab.append(f"{pv.stems.get(inst, 'no')} stem")
                y += block[inst]
            for t in pv.beats[(pv.beats >= a) & (pv.beats < b)]:
                ax.axvline(t, color="#cccccc", lw=0.5, zorder=0)
            for t in pv.measures[(pv.measures >= a) & (pv.measures < b)]:
                ax.axvline(t, color="#777777", lw=0.9, zorder=0)
            for t, name in _sections_in(pv, a, b):
                ax.axvline(t, color="#000000", lw=1.4, zorder=1)
                ax.text(t, height - 0.2, f" {name}", fontsize=9, va="top", weight="bold")
            if cut and a <= pv.audio_end < b:
                ax.axvline(pv.audio_end, color="#000000", lw=1.2, ls="--", zorder=1)
            ax.set_xlim(a, a + strip_s)
            ax.set_ylim(-0.3, height)
            ax.set_yticks(ytick, ylab, fontsize=7)
            xt = np.arange(np.ceil(a), a + strip_s, 1.0)
            ax.set_xticks(xt, [_mmss(t)[:-2] if t % 5 == 0 else "" for t in xt], fontsize=8)
        fig.suptitle(f"{pv.folder.name}: {difficulty}, {_mmss(p * page_s)[:-2]}-{_mmss(min(pv.duration, (p + 1) * page_s))[:-2]}"
                     "   (hollow = HOPO, diamond = tap, triangle = cymbal, grey = the stem's onset strength)",
                     fontsize=10)
        path = out / f"page_{p + 1:02d}.png"
        fig.savefig(path, dpi=80)
        plt.close(fig)
        paths.append(path)
    return paths


def _seconds(s: str) -> float:
    try:
        v = float(s)
    except ValueError:
        raise argparse.ArgumentTypeError(f"not a number of seconds: {s!r}") from None
    if not (v > 0 and math.isfinite(v)):
        raise argparse.ArgumentTypeError(f"must be more than 0 seconds, not {s}")
    return v


def main(argv: list[str] | None = None) -> int:
    # a folder name the console's code page cannot show (cp1252 when Windows redirects stdout) must not cost the
    # printed flags; stderr already escapes such characters
    try:
        sys.stdout.reconfigure(errors="backslashreplace")
    except (AttributeError, ValueError):
        pass
    ap = argparse.ArgumentParser(prog="python -m songcharter.preview", description=__doc__.split("\n\n")[0])
    ap.add_argument("folder", type=Path, help="a song folder (notes.chart or notes.mid, song.ogg; report.json for "
                                              "the stems)")
    ap.add_argument("--out", type=Path, help="where the PNGs go (default: <folder>/preview)")
    ap.add_argument("--difficulty", default="expert", choices=DIFFICULTIES)
    ap.add_argument("--page", type=_seconds, default=60.0, help="seconds per page (default 60)")
    ap.add_argument("--no-pages", action="store_true", help="only the overview")
    a = ap.parse_args(argv)
    if not a.folder.is_dir():
        ap.error(f"{a.folder} is not a folder")
    if not any(f.is_file() and f.suffix.lower() in (".chart", ".mid") for f in a.folder.iterdir()):
        ap.error(f"no .chart or .mid in {a.folder}")
    out = a.out or a.folder / "preview"
    try:
        pv = load(a.folder)
        out.mkdir(parents=True, exist_ok=True)
        found = render_overview(pv, out / "overview.png", a.difficulty)
        pages = [] if a.no_pages else render_pages(pv, out, a.difficulty, a.page)
    except (ValueError, OSError, RuntimeError) as e:  # a chart, stem or song.ogg that cannot be read
        print(f"preview: error: {e}", file=sys.stderr)
        return 2
    print(f"{out / 'overview.png'} and {len(pages)} pages")
    for line in remarks(pv, a.difficulty):
        print(f"  {line}")
    if not pv.envelopes:
        print("  no stems found: notes only, no gap or silence judged")
    for f in found:
        print(f"  {f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
