"""Pictures of a built chart beside its audio, to see where it works and where it does not.

    python -m songcharter.preview <song folder> [--out DIR] [--difficulty expert] [--page 60]

  * **Overview** (`overview.png`): the whole song, one row per instrument. Bars are notes per beat in each measure;
    the line over them is the instrument's own stem level against its loud level (P95). Two kinds of measure are
    flagged: a **gap** (the stem plays, within 15 dB of its P95, and the chart has no note, not even a sustain held
    from before) and **notes in silence**
    (notes while the stem stays 25 dB or more below its P95, assemble's SILENT_DB). Sections, star power and the
    tempo map are drawn too. The flagged stretches also come back as text (`flags`).
  * **Pages** (`page_01.png`, ...): a minute per page in strips of 15 s. Each instrument's lanes as Clone Hero shows
    them (green, red, yellow, blue, orange; drums with cymbals as triangles and toms as circles, the kick as a bar),
    sustains as lines, HOPOs hollow, star power shaded, drum fills hatched, beat and measure lines, section names,
    and under each instrument its stem's onset strength, so a note can be checked against the hit it belongs to.

Times are song seconds (what the player hears: song.ogg, chart time). The stems come from the folder's report.json
(written by assemble, with the lead-in pad that moves input seconds onto the song), or from `stems=` (input seconds,
with `pad=`); without stems only the notes are drawn. Needs matplotlib and librosa (`pip install songcharter[preview]`).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from . import audio as A
from .importers import read_song
from .timed import TimedHit, TimedSong

INSTRUMENTS = ("guitar", "bass", "drums")
STEMS_FOR = {"guitar": ("guitar", "other"), "bass": ("bass",), "drums": ("drums",)}  # as assemble.STEMS_FOR
GAP_DB = -15.0       # a measure whose stem peaks within this of its P95 is "playing"
SILENT_DB = -25.0    # a measure with notes whose stem stays below this is "notes in silence" (assemble's SILENT_DB)
EDGE = 0.05          # seconds at each end of a measure left out of its level (the envelope's frames reach across)
ENV_SR, ENV_HOP = 22050, 256
LANE_COLORS = ["#21a336", "#e0312b", "#e8c21a", "#2f6fdc", "#f08a1c"]   # green, red, yellow, blue, orange
OPEN_COLOR = "#9b4fd6"
PAD_NAMES = ["kick", "red", "yellow", "blue", "green"]
DRUM_COLORS = ["#f08a1c", "#e0312b", "#e8c21a", "#2f6fdc", "#21a336"]


@dataclass
class Envelope:
    times: np.ndarray        # song seconds
    level_db: np.ndarray     # RMS dB against the stem's P95 (0 = loud)
    onset: np.ndarray        # onset strength, 0..1 (its 99th percentile = 1)


@dataclass
class Preview:
    folder: Path
    song: TimedSong                     # chart time (song seconds)
    beats: np.ndarray                   # song seconds of every beat on the tempo map
    measures: np.ndarray                # song seconds of every measure line
    duration: float
    envelopes: dict[str, Envelope] = field(default_factory=dict)   # instrument -> its stem's envelope
    stems: dict[str, str] = field(default_factory=dict)            # instrument -> stem name used


@dataclass(frozen=True)
class Flag:
    instrument: str
    kind: str          # "gap" or "notes in silence"
    start: float       # song seconds
    end: float
    measures: int

    def __str__(self) -> str:
        return f"{self.instrument}: {self.kind} {_mmss(self.start)}-{_mmss(self.end)} ({self.measures} measures)"


def _mmss(t: float) -> str:
    t = round(max(0.0, t), 1)
    m = int(t // 60)
    return f"{m}:{t - 60 * m:04.1f}"


def _measure_lines(chart: Path, beats: np.ndarray) -> np.ndarray:
    """Measure lines from the .chart's time signatures (x/4 throughout unless TS events say otherwise)."""
    if not len(beats):
        return beats
    text = chart.read_text(encoding="utf-8-sig", errors="replace") if chart.suffix.lower() == ".chart" else ""
    res = re.search(r"Resolution\s*=\s*(\d+)", text)
    res = int(res.group(1)) if res else 192
    sync = re.search(r"\[SyncTrack\]\s*\{(.*?)\}", text, re.S)
    ts = sorted((int(t), int(n)) for t, n in re.findall(r"(\d+)\s*=\s*TS\s+(\d+)", sync.group(1) if sync else ""))
    ts = ts or [(0, 4)]
    out, beat, i = [], 0, 0
    while beat < len(beats):
        while i + 1 < len(ts) and ts[i + 1][0] <= beat * res:
            i += 1
        out.append(beats[beat])
        beat += max(1, ts[i][1])
    return np.array(out)


def _envelope(y: np.ndarray, shift: float, duration: float) -> Envelope:
    import librosa
    x = y.mean(axis=0) if y.ndim == 2 else y
    x = librosa.resample(np.asarray(x, dtype=np.float32), orig_sr=A.SAMPLE_RATE, target_sr=ENV_SR)
    rms = librosa.feature.rms(y=x, frame_length=4 * ENV_HOP, hop_length=ENV_HOP)[0]
    db = 20 * np.log10(rms + 1e-9)
    db -= np.percentile(db, 95)
    onset = librosa.onset.onset_strength(y=x, sr=ENV_SR, hop_length=ENV_HOP)
    n = min(len(db), len(onset))
    onset = np.clip(onset[:n] / (np.percentile(onset, 99) + 1e-9), 0, 1)
    times = np.arange(n) * ENV_HOP / ENV_SR + shift
    keep = times <= duration + 1
    return Envelope(times[keep], db[:n][keep], onset[keep])


def load(folder: Path | str, stems: dict[str, np.ndarray | str | Path] | None = None, pad: float | None = None
         ) -> Preview:
    """The chart in `folder` and, if available, each instrument's stem envelope.
    stems: stem name -> array or WAV path, in input seconds (pad: the lead-in that moves them onto the song); by
    default the stems and pad in the folder's report.json, when there is one."""
    folder = Path(folder)
    song = read_song(folder)
    chart = next((folder / n for n in ("notes.chart", "notes.mid") if (folder / n).exists()), folder / "notes.chart")
    beats = np.array(song.beats, dtype=float)
    ogg = folder / "song.ogg"
    report = folder / "report.json"
    if stems is None and report.exists():
        r = json.loads(report.read_text(encoding="utf-8"))
        stems = {k: v["path"] for k, v in r.get("stems", {}).items() if Path(v.get("path", "")).exists()}
        pad = r.get("lead_in", {}).get("pad_seconds", 0.0) if pad is None else pad
    pad = pad or 0.0
    arrays = {}
    for inst in INSTRUMENTS:
        name = next((s for s in STEMS_FOR[inst] if stems and s in stems), None)
        if name is not None and any(i == inst for i, _ in song.parts):
            y = stems[name]
            arrays[inst] = (name, A.read_wav(y)[0] if isinstance(y, (str, Path)) else y)
    if ogg.exists():
        duration = A.decode(ogg).shape[1] / A.SAMPLE_RATE
    else:  # the last note's end, or the stems' end on the song's clock
        ends = [getattr(n, "end", None) or n.time for p in song.parts.values() for n in p.notes]
        duration = max([max(ends, default=0.0) + 2] + [y.shape[-1] / A.SAMPLE_RATE + pad for _, y in arrays.values()])
    if len(beats) >= 2 and beats[-1] < duration:  # a tempo map that ends early: its last beat period to the end
        step = beats[-1] - beats[-2]
        beats = np.concatenate([beats, beats[-1] + step * np.arange(1, int((duration - beats[-1]) / step) + 2)])
    pv = Preview(folder, song, beats, _measure_lines(chart, beats), duration)
    for inst, (name, y) in arrays.items():
        pv.envelopes[inst] = _envelope(y, pad, duration)
        pv.stems[inst] = name
    return pv


def measure_stats(pv: Preview, instrument: str, difficulty: str = "expert") -> list[dict]:
    """Per measure: start and end (song seconds), onsets, notes per beat, whether a sustain from before is still held
    in it, and the stem's peak and mean level (dB against its P95; None without a stem)."""
    part = pv.song.parts.get((instrument, difficulty))
    onsets = np.array(sorted({round(n.time, 4) for n in part.notes})) if part else np.array([])
    held = sorted((n.time, n.end) for n in part.notes if getattr(n, "end", None)) if part else []
    env = pv.envelopes.get(instrument)
    edges = list(pv.measures) + [pv.duration]
    out = []
    for a, b in zip(edges, edges[1:]):
        if b <= a:
            continue
        n = int(np.sum((onsets >= a - 1e-3) & (onsets < b - 1e-3)))  # a note on the measure line belongs to it
        beats = max(1, int(np.sum((pv.beats >= a - 1e-6) & (pv.beats < b - 1e-6))))
        row = {"start": float(a), "end": float(b), "onsets": n, "per_beat": n / beats,
               "held": any(t < a - 1e-3 and e > a for t, e in held), "peak_db": None, "mean_db": None}
        if env is not None:
            m = (env.times >= a + EDGE) & (env.times < b - EDGE)
            if m.any():
                row["peak_db"] = float(env.level_db[m].max())
                row["mean_db"] = float(env.level_db[m].mean())
        out.append(row)
    return out


def flags(pv: Preview, difficulty: str = "expert", min_measures: int = 1) -> list[Flag]:
    """Stretches of measures where the stem plays and the chart is empty (gap), or the chart has notes and the stem
    is silent (notes in silence), merged across consecutive measures."""
    out = []
    for inst in INSTRUMENTS:
        if inst not in pv.envelopes:
            continue
        run: list[dict] = []
        kind = None
        for row in measure_stats(pv, inst, difficulty) + [None]:
            k = None
            if row is not None and row["peak_db"] is not None:
                if row["onsets"] == 0 and not row["held"] and row["peak_db"] >= GAP_DB:
                    k = "gap"
                elif row["onsets"] > 0 and row["peak_db"] < SILENT_DB:
                    k = "notes in silence"
            if k != kind and run:
                if len(run) >= min_measures:
                    out.append(Flag(inst, kind, run[0]["start"], run[-1]["end"], len(run)))
                run = []
            kind = k
            if k is not None:
                run.append(row)
    return sorted(out, key=lambda f: (f.start, f.instrument))


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
    fig, axes = plt.subplots(len(insts) + 1, 1, figsize=(18, 2.1 * len(insts) + 2.4), sharex=True,
                             gridspec_kw={"height_ratios": [2] * len(insts) + [1]})
    axes = np.atleast_1d(axes)
    for ax, inst in zip(axes, insts):
        rows = measure_stats(pv, inst, difficulty)
        x = [r["start"] for r in rows]
        w = [r["end"] - r["start"] for r in rows]
        ax.bar(x, [r["per_beat"] for r in rows], width=w, align="edge", color="#5b7bb5", alpha=0.85, label="notes/beat")
        ax.set_ylim(0, max(4.2, max([r["per_beat"] for r in rows], default=0) * 1.1))
        ax.set_ylabel(f"{inst}\nnotes/beat")
        for f in found:
            if f.instrument == inst:
                ax.axvspan(f.start, f.end, color="#e0312b" if f.kind == "gap" else "#9b4fd6", alpha=0.25, lw=0)
        part = pv.song.parts[(inst, difficulty)]
        for s in part.star_power:
            ax.axvspan(s.start, s.end, ymin=0.92, ymax=1.0, color="#20b2d8", alpha=0.9, lw=0)
        env = pv.envelopes.get(inst)
        if env is not None:
            ax2 = ax.twinx()
            ax2.plot(env.times, np.clip(env.level_db, -45, 3), color="#333333", lw=0.6, alpha=0.8)
            ax2.axhline(GAP_DB, color="#e0312b", lw=0.6, ls=":")
            ax2.axhline(SILENT_DB, color="#9b4fd6", lw=0.6, ls=":")
            ax2.set_ylim(-45, 3)
            ax2.set_ylabel(f"{pv.stems[inst]} stem dB\n(vs its P95)", fontsize=8)
        for t, _ in pv.song.sections:
            ax.axvline(t, color="#888888", lw=0.5)
    top = axes[0]
    for t, name in pv.song.sections:
        top.text(t, top.get_ylim()[1], f" {name}", fontsize=7, rotation=45, va="bottom", ha="left")
    tax = axes[-1]
    if len(pv.beats) > 1:
        mid = (pv.beats[1:] + pv.beats[:-1]) / 2
        tax.plot(mid, 60 / np.diff(pv.beats), color="#2f6fdc", lw=0.8)
    tax.set_ylabel("tempo\nBPM")
    tax.set_xlabel("song time (m:ss)")
    ticks = np.arange(0, pv.duration + 1, 30)
    tax.set_xticks(ticks, [_mmss(t)[:-2] for t in ticks])
    tax.set_xlim(0, pv.duration)
    fig.suptitle(f"{pv.folder.name}: {difficulty}. Red = gap (stem plays, no notes); purple = notes in silence; "
                 "cyan = star power", fontsize=10)
    fig.tight_layout()
    fig.savefig(path, dpi=90)
    plt.close(fig)
    return found


def _draw_frets(ax, part, y0: float, a: float, b: float) -> None:
    for n in part.notes:
        if not (a - 0.5 <= n.time < b):
            continue
        lanes = [5 if f not in range(5) else f for f in n.frets]
        for lane in lanes:
            y = y0 + lane
            color = OPEN_COLOR if lane == 5 else LANE_COLORS[lane]
            if n.end is not None and n.end > n.time:
                ax.plot([n.time, min(n.end, b)], [y, y], color=color, lw=4, alpha=0.45, solid_capstyle="butt")
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
    """page_NN.png: page_s seconds per page, strips of strip_s seconds, every instrument's lanes over its stem."""
    plt = _plt()
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    insts = [i for i in INSTRUMENTS if (i, difficulty) in pv.song.parts]
    lanes = {"guitar": 6, "bass": 6, "drums": 5}
    block = {i: lanes[i] + 2.2 for i in insts}        # lanes, then the onset band, then a gap
    height = sum(block.values())
    strips = max(1, int(round(page_s / strip_s)))
    paths = []
    for p in range(int(np.ceil(pv.duration / page_s))):
        fig, axes = plt.subplots(strips, 1, figsize=(18, 0.32 * height * strips + 0.8))
        axes = np.atleast_1d(axes)
        for s, ax in enumerate(axes):
            a = p * page_s + s * strip_s
            b = a + strip_s
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
            ax.set_xlim(a, b)
            ax.set_ylim(-0.3, height)
            ax.set_yticks(ytick, ylab, fontsize=7)
            xt = np.arange(np.ceil(a), b, 1.0)
            ax.set_xticks(xt, [_mmss(t)[:-2] if t % 5 == 0 else "" for t in xt], fontsize=8)
        fig.suptitle(f"{pv.folder.name}: {difficulty}, {_mmss(p * page_s)[:-2]}-{_mmss(min(pv.duration, (p + 1) * page_s))[:-2]}"
                     "   (hollow = HOPO, diamond = tap, triangle = cymbal, grey = the stem's onset strength)",
                     fontsize=10)
        fig.tight_layout()
        path = out / f"page_{p + 1:02d}.png"
        fig.savefig(path, dpi=80)
        plt.close(fig)
        paths.append(path)
    return paths


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m songcharter.preview", description=__doc__.split("\n\n")[0])
    ap.add_argument("folder", type=Path, help="a song folder (notes.chart, song.ogg; report.json for the stems)")
    ap.add_argument("--out", type=Path, help="where the PNGs go (default: <folder>/preview)")
    ap.add_argument("--difficulty", default="expert", choices=("expert", "hard", "medium", "easy"))
    ap.add_argument("--page", type=float, default=60.0, help="seconds per page (default 60)")
    ap.add_argument("--no-pages", action="store_true", help="only the overview")
    a = ap.parse_args(argv)
    pv = load(a.folder)
    out = a.out or a.folder / "preview"
    out.mkdir(parents=True, exist_ok=True)
    found = render_overview(pv, out / "overview.png", a.difficulty)
    pages = [] if a.no_pages else render_pages(pv, out, a.difficulty, a.page)
    print(f"{out / 'overview.png'} and {len(pages)} pages")
    if not pv.envelopes:
        print("no stems found: notes only, nothing flagged")
    for f in found:
        print(f"  {f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
