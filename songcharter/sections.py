"""Practice sections: named markers on measure lines of the song's own tempo map.

A section is a (tick, name) pair, written as `E "section <name>"` in [Events] (Chart.sections). Clone Hero uses them
for practice mode, and the later stages use their starts: the star-power score, fills at section changes and Easy
drums (reduce.py).

Two sources, both in seconds of the input audio (input second t sits at t + pad_seconds on the map):

  * All-In-One (allin1) structure analysis: segments (start, end, label) with labels from its Harmonix-trained set
    (start, end, intro, outro, break, bridge, inst, solo, verse, chorus). `sections_from_segments`:
      1. "start" and "end" mark the silence before and after the music and are dropped.
      2. Every segment start snaps to the nearest measure start (ties to the earlier one); the last segment's end
         snaps too, to measure its length.
      3. A segment shorter than `min_measures` (2) merges into the one before it; the first merges into the one
         after it, which then starts where the first did. The shortest goes first, so two starts that snapped to
         one measure leave one section.
      4. Optionally (`split_over`), DESIGN.md 2.5's merge-then-split: a run of consecutive segments with one label
         becomes one segment, and one longer than `split_over` measures is split at even measure positions into
         round(length / `split_into`) parts (over 16 bars into parts of about 8: a verse of 18 + 10 measures becomes
         four parts of 7). Without it a run keeps its segments' starts.
      5. Names as Clone Hero charts write them: Title Case, "inst" as "Instrumental". A run of consecutive segments
         with one label is one occurrence of it. A label that occurs more than once is numbered ("Verse 1",
         "Verse 2"); one that occurs once is not ("Bridge"). An occurrence in several parts (a run, or a split)
         letters them: "Intro A", "Intro B", "Solo 3A".
  * An imported chart's sections (TimedSong.sections), the fallback: `sections_from_chart` snaps them the same way,
    merges sections under `min_measures` the same way and keeps the source's names, cleaned ("verse_1" becomes
    "Verse 1", as games show Rock Band's section names).

Fold-0 allin1 section quality on unseen songs is unmeasured (the critique), so these are practice markers, not
ground truth. Only solo detection (starpower.py) reads meaning into the names.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import numpy as np

from .errors import InputError
from .tempo import TempoMap

# allin1 labels as Clone Hero charts name them; "start" and "end" are silence and never become sections
LABEL_NAMES = {"intro": "Intro", "outro": "Outro", "verse": "Verse", "chorus": "Chorus", "bridge": "Bridge",
               "inst": "Instrumental", "solo": "Solo", "break": "Break"}
SILENCE = ("start", "end")
MIN_MEASURES = 2


@dataclass(frozen=True)
class Segment:
    """One allin1 segment, in seconds of the input audio."""
    start: float
    end: float
    label: str     # lower case, e.g. "verse"


def read_allin1(path) -> list[Segment]:
    """The segments of an allin1 result JSON (UTF-8, with or without a BOM): `segments` as [start, end, label] lists
    (our cached runs) or as {"start", "end", "label"} objects (allin1's own `save` format). A file that is not such
    a result is a ValueError."""
    data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict) or not isinstance(data.get("segments"), list):
        raise InputError(f"{path}: no 'segments' list")
    out = []
    for i, s in enumerate(data["segments"]):
        try:
            start, end, label = (s["start"], s["end"], s["label"]) if isinstance(s, dict) else s
            out.append(Segment(float(start), float(end), str(label).strip().lower()))
        except (KeyError, TypeError, ValueError) as e:
            raise InputError(f"{path}: segment {i} is not [start, end, label] ({type(e).__name__}: {e})") from e
    return sorted(out, key=lambda s: (s.start, s.end))


def read_allin1_beats(path) -> np.ndarray | None:
    """allin1's beats in an allin1 result JSON (seconds of the input audio, sorted, repeats dropped), or None when
    it holds none: the librosa fallback writes only `segments`. assemble's second pass starts from them when its
    straight line misses a tempo change (DESIGN.md 2.3). A `beats` that is not a list of finite times is an
    InputError."""
    data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    beats = data.get("beats") if isinstance(data, dict) else None
    if beats is None or (isinstance(beats, list) and not beats):
        return None
    try:
        b = np.asarray(beats, dtype=np.float64)
    except (TypeError, ValueError) as e:
        raise InputError(f"{path}: 'beats' is not a list of times ({type(e).__name__}: {e})") from e
    if b.ndim != 1 or not np.isfinite(b).all():
        raise InputError(f"{path}: 'beats' is not a list of finite times")
    return np.unique(b)


def label_name(label: str) -> str:
    """An allin1 label as a section name without its number: "inst" -> "Instrumental"."""
    key = label.strip().lower()
    return LABEL_NAMES.get(key) or clean_name(key)


def clean_name(name: str) -> str:
    """A section name as games show it: underscores as spaces, single spaces, words capitalised, a trailing part
    letter after a number upper-cased ("chorus_2a" -> "Chorus 2A"). Words already holding capitals stay as they are."""
    words = " ".join(name.replace("_", " ").split()).split(" ")
    out = []
    for w in words:
        if re.fullmatch(r"\d+[a-z]", w):
            w = w.upper()
        elif w.islower():
            w = w[:1].upper() + w[1:]
        out.append(w)
    return " ".join(out)


class _Measures:
    """Measure starts of a tempo map, in ticks and in seconds of the map's timeline."""

    def __init__(self, tempo: TempoMap, last_sec: float):
        end = int(tempo.sec_to_tick(last_sec)) + 1
        end += 2 * tempo.measure_length(tempo.time_signature_at(end))  # room past the last time
        self.ticks = tempo.measure_starts(end)
        self.secs = np.array([tempo.tick_to_sec(t) for t in self.ticks])

    def nearest(self, sec: float) -> int:
        """Index of the measure start nearest to `sec` (the earlier one on a tie)."""
        return int(np.argmin(np.abs(self.secs - sec)))


def _merge_short(items: list[list], end: int | None, min_measures: int) -> list[list]:
    """Merge segments shorter than min_measures: [measure index, payload...] items, `end` the measure index where
    the last one ends (None: unknown, the last is never short). The shortest goes first, the earlier on a tie."""
    items = [list(x) for x in items]
    while len(items) > 1:
        lengths = [b[0] - a[0] for a, b in zip(items, items[1:])]
        if end is not None:
            lengths.append(end - items[-1][0])
        short = [(n, i) for i, n in enumerate(lengths) if n < min_measures]
        if not short:
            break
        _, i = min(short)
        if i == 0:
            items[1][0] = items[0][0]   # the first joins the one after it, which starts where the first did
            del items[0]
        else:
            del items[i]                 # joins the one before it
    return items


def sections_from_segments(segments: Sequence[Segment], tempo: TempoMap, pad_seconds: float = 0.0, *,
                           min_measures: int = MIN_MEASURES, split_over: int | None = None,
                           split_into: int = 8) -> list[tuple[int, str]]:
    """Named sections on measure starts from allin1 segments (rules 1-5 of the module docstring).

    split_over: merge each run of one label into one segment, and split one longer than this many measures into
    parts of about `split_into` measures (rule 4).
    """
    music = sorted((s for s in segments if s.label not in SILENCE), key=lambda s: (s.start, s.end))
    if not music:
        return []
    ms = _Measures(tempo, max(s.end for s in music) + pad_seconds)
    items = [[ms.nearest(s.start + pad_seconds), s.label] for s in music]
    end = max(ms.nearest(music[-1].end + pad_seconds), items[-1][0])
    items = _merge_short(items, end, min_measures)
    # occurrences: consecutive segments with one label, as [start measure index, label, segment starts]
    runs: list[list] = []
    for m, label in items:
        if runs and runs[-1][1] == label:
            runs[-1][2].append(m)
        else:
            runs.append([m, label, [m]])
    # parts: [measure index, label, occurrence key]
    parts: list[list] = []
    for occurrence, ((m, label, starts), nxt) in enumerate(zip(runs, runs[1:] + [None])):
        if split_over is None:
            parts += [[s, label, occurrence] for s in starts]  # a run keeps its segments' starts
            continue
        n = (nxt[0] if nxt is not None else end) - m  # a run is one segment, split when long
        pieces = max(1, round(n / split_into)) if n > split_over else 1
        parts += [[m + round(j * n / pieces), label, occurrence] for j in range(pieces)]
    counts: dict[str, list[int]] = {}
    for _, label, occ in parts:
        seen = counts.setdefault(label, [])
        if occ not in seen:
            seen.append(occ)
    out = []
    for i, (m, label, occ) in enumerate(parts):
        name = label_name(label)
        if len(counts[label]) > 1:
            name += f" {counts[label].index(occ) + 1}"
        same = [p for p in parts if p[2] == occ]
        if len(same) > 1:
            letter = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"[min(same.index(parts[i]), 25)]
            name += letter if name[-1].isdigit() else f" {letter}"
        out.append((ms.ticks[m], name))
    return out


def sections_from_chart(sections: Sequence[tuple[float, str]], tempo: TempoMap, pad_seconds: float = 0.0, *,
                        end: float | None = None, min_measures: int = MIN_MEASURES) -> list[tuple[int, str]]:
    """The sections of an imported chart (seconds of input audio, name) on our measure starts, merged like
    allin1's segments (rule 3) and with cleaned names. end: the song's end in input seconds, so the last section's
    length can be checked; without it the last section is kept."""
    named = sorted((t, clean_name(n)) for t, n in sections if clean_name(n))
    if not named:
        return []
    last = max([t for t, _ in named] + ([end] if end is not None else []))
    ms = _Measures(tempo, last + pad_seconds)
    items = [[ms.nearest(t + pad_seconds), n] for t, n in named]
    stop = ms.nearest(end + pad_seconds) if end is not None else None
    items = _merge_short(items, stop, min_measures)
    return [(ms.ticks[m], n) for m, n in items]
