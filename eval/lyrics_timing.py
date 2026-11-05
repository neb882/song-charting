"""Lyric timings of two charts compared word by word: a human chart's lyric events against the ones songcharter wrote
from the same words (eval/stress.py lyrics; docs/work-orders/M5-09-stress-eval.md).

    python -I eval/lyrics_timing.py REF CAND [--ref-shift-ms MS] [--cand-shift-ms MS]

REF and CAND are notes.chart or notes.mid files (a .mid's PART VOCALS lyrics and its phrase markers, notes 105 and
106; a .chart's [Events] lyric, phrase_start and phrase_end). Each word's start is its first syllable's (a syllable
ending in `-` or `=` joins the next; a `+` alone is a slide, part of the word before; `_` and spaces split words;
a word with no letter or digit, such as `...`, is left out, as songcharter's text model leaves it out). The shifts
put both on one timeline (the human chart's delay; minus our chart's lead-in pad). Words are paired by index.

**The lyrics rule** (docs/work-orders/M4-10-lyrics.md, and M5-09's extension of its exception to the stress songs):
the words are read in memory only, to give them to songcharter's aligner and to compare timings. Nothing here
prints, logs, saves or returns a word: the output is word indices, counts and milliseconds, and every error is
printed as its type only, since a parser's message could quote the text. Tests use made-up words.
"""
from __future__ import annotations

import argparse
import io
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

MARKUP = set("+=#^*%$/§<>")      # songcharter.lyrics.MARKUP: what Clone Hero acts on, never part of a word
PHRASE_NOTES = (105, 106)        # Rock Band's phrase markers in PART VOCALS
OVER_S = 0.5                     # a phrase whose first word is further off than this is counted


@dataclass
class Sung:
    """A chart's words: each one's start (s, on the caller's timeline) and the index of each phrase's first word.
    The words themselves stay in `_texts`, for the aligner's text only: never printed."""
    times: list[float] = field(default_factory=list)
    phrase_first: list[int] = field(default_factory=list)
    _texts: list[str] = field(default_factory=list, repr=False)
    _lines: list[int] = field(default_factory=list, repr=False)

    def shifted(self, seconds: float) -> "Sung":
        return Sung([t + seconds for t in self.times], list(self.phrase_first), self._texts, self._lines)

    def aligner_text(self) -> str:
        """The words as songcharter's lyrics text: one line per phrase (never printed)."""
        lines: dict[int, list[str]] = {}
        for text, line in zip(self._texts, self._lines):
            lines.setdefault(line, []).append(text)
        return "\n".join(" ".join(lines[k]) for k in sorted(lines)) + "\n"


# ------------------------------------------------------------------------------------------------ reading

def _seconds(ticks, tempos: list[tuple[int, float]], resolution: int) -> list[float]:
    """Ticks to seconds on a tempo map of (tick, beats per minute), sorted by tick."""
    tempos = sorted(tempos) or [(0, 120.0)]
    if tempos[0][0] > 0:
        tempos.insert(0, (0, tempos[0][1]))
    starts, at = [], 0.0
    for k, (tick, bpm) in enumerate(tempos):
        if k:
            at += (tick - tempos[k - 1][0]) * 60.0 / (tempos[k - 1][1] * resolution)
        starts.append(at)
    out = []
    marks = [t for t, _ in tempos]
    for tick in ticks:
        k = int(np.searchsorted(marks, tick, side="right")) - 1
        out.append(starts[k] + (tick - tempos[k][0]) * 60.0 / (tempos[k][1] * resolution))
    return out


def read_mid(data: bytes) -> tuple[list[tuple[float, str, int]], int]:
    """A .mid's PART VOCALS syllables: (seconds, text, phrase index), and the phrase count."""
    import mido
    mid = mido.MidiFile(file=io.BytesIO(data))
    tempos, syl, phrases = [], [], []
    for track in mid.tracks:
        tick, name = 0, (track.name or "").strip().upper()
        for msg in track:
            tick += msg.time
            if msg.type == "set_tempo":
                tempos.append((tick, mido.tempo2bpm(msg.tempo)))
            if name != "PART VOCALS":
                continue
            if msg.type == "lyrics" or (msg.type == "text" and not msg.text.lstrip().startswith("[")):
                syl.append((tick, msg.text))
            elif msg.type == "note_on" and msg.velocity > 0 and msg.note in PHRASE_NOTES:
                phrases.append(tick)
    phrases = sorted(set(phrases))
    secs = _seconds([t for t, _ in syl], tempos, mid.ticks_per_beat)
    out = [(s, text, int(np.searchsorted(phrases, tick, side="right")) - 1) for s, (tick, text) in zip(secs, syl)]
    return out, len(phrases)


def read_chart(data: bytes) -> tuple[list[tuple[float, str, int]], int]:
    """A .chart's [Events] lyrics as Clone Hero reads them (songcharter.lyrics.read_events): (seconds, text, phrase
    index), and the phrase count. The chart's [Song] Offset is not applied (the caller's shift is)."""
    from songcharter.importers import _chart_sections, _decode
    from songcharter.lyrics import read_events
    sections = _chart_sections(_decode(data))
    song = {k.strip(): v.strip() for line in sections.get("Song", []) for k, _, v in [line.partition("=")]}
    resolution = int(float(song.get("Resolution", "192")))
    tempos = []
    for line in sections.get("SyncTrack", []):
        m = re.fullmatch(r"(\d+)\s*=\s*B\s+(\d+)", line.strip())
        if m:
            tempos.append((int(m[1]), int(m[2]) / 1000.0))
    phrases = read_events([line.strip() for line in sections.get("Events", [])])
    ticks = [(t, text, k) for k, p in enumerate(phrases) for t, text in p.syllables]
    secs = _seconds([t for t, _, _ in ticks], tempos, resolution)
    return [(s, text, k) for s, (_, text, k) in zip(secs, ticks)], len(phrases)


def words(syllables: list[tuple[float, str, int]]) -> Sung:
    """The words of a chart's syllables (the module docstring)."""
    out = Sung()
    cur, joined = None, False   # cur: [time, text, phrase] of the word being built
    finished: list[list] = []

    def close():
        nonlocal cur
        if cur is not None:
            finished.append(cur)
        cur = None

    for t, raw, phrase in syllables:
        text = raw.strip()
        if cur is not None and phrase != cur[2]:
            close()
            joined = False
        joins = text.endswith("-") or text.endswith("=")
        hyphen = text.endswith("=")
        body = "".join(c for c in text.rstrip("-=") if c not in MARKUP)
        tokens = body.replace("_", " ").split()
        if not tokens:            # a slide (+) or markup alone: part of the word before
            continue
        for k, tok in enumerate(tokens):
            if k == 0 and joined and cur is not None:
                cur[1] += tok
            else:
                close()
                cur = [t, tok, phrase]
        if hyphen:
            cur[1] += "-"
        joined = joins
        if not joins:
            close()
    close()
    seen_phrase = set()
    for t, text, phrase in finished:
        text = text.strip("-")
        if not any(c.isalnum() for c in text):
            continue
        if phrase not in seen_phrase:
            seen_phrase.add(phrase)
            out.phrase_first.append(len(out.times))
        out.times.append(t)
        out._texts.append(text)
        out._lines.append(phrase)
    return out


def read(path_or_bytes, kind: str | None = None) -> Sung:
    """The words of a notes.chart or notes.mid (a path, or its bytes with `kind` "chart" or "mid")."""
    if isinstance(path_or_bytes, (str, Path)):
        kind = kind or Path(path_or_bytes).suffix.lower().lstrip(".")
        data = Path(path_or_bytes).read_bytes()
    else:
        data = path_or_bytes
    syl, _ = read_mid(data) if kind == "mid" else read_chart(data)
    return words(syl)


# ------------------------------------------------------------------------------------------------ comparing

def compare(ref: Sung, cand: Sung) -> dict:
    """Numbers only: words paired by index, their errors (cand - ref) and the phrases whose first word is off."""
    n = min(len(ref.times), len(cand.times))
    out = {"words_ref": len(ref.times), "words_cand": len(cand.times), "paired": n,
           "paired_share": round(n / len(ref.times), 4) if ref.times else None, "phrases": len(ref.phrase_first)}
    if not n:
        return {**out, "median_abs_ms": None, "median_ms": None, "within_50ms": None, "within_100ms": None,
                "within_250ms": None, "phrase_starts_over_500ms": None}
    err = (np.asarray(cand.times[:n]) - np.asarray(ref.times[:n])) * 1000.0
    a = np.abs(err)
    starts = [k for k in ref.phrase_first if k < n]
    return {**out, "median_abs_ms": round(float(np.median(a)), 1), "median_ms": round(float(np.median(err)), 1),
            "within_50ms": round(float(np.mean(a <= 50)), 4), "within_100ms": round(float(np.mean(a <= 100)), 4),
            "within_250ms": round(float(np.mean(a <= 250)), 4),
            "phrase_starts_over_500ms": int(sum(a[k] > OVER_S * 1000 for k in starts)), "phrase_starts_paired": len(starts)}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("ref")
    ap.add_argument("cand")
    ap.add_argument("--ref-shift-ms", type=float, default=0.0)
    ap.add_argument("--cand-shift-ms", type=float, default=0.0)
    a = ap.parse_args(argv)
    try:
        ref = read(a.ref).shifted(a.ref_shift_ms / 1000.0)
        cand = read(a.cand).shifted(a.cand_shift_ms / 1000.0)
        print(json.dumps(compare(ref, cand)))
    except Exception as e:  # noqa: BLE001  the message could quote a word: its type only
        print(f"lyrics_timing: failed ({type(e).__name__})", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
