"""Lyrics: the text a person gives, as Clone Hero shows it, and its events in the chart's [Events] (DESIGN.md 2.15).

    text = parse(lyrics)                       # the words and syllables, what is shown and what is aligned
    phrases, stats = place(text, starts, tm, pad_seconds)   # each syllable on our grid, the phrases split
    events(phrases)                            # the [Events] rows: phrase_start, lyric <syllable>, phrase_end

The text is never written anywhere but the chart: every report holds counts and times only.

**The text** (`parse`), as Clone Hero reads lyrics (the .chart lyrics documentation of the GuitarGame_ChartFormats
project, "Lyrics Markup" and "Displaying as Plain Text"; scan-chart only checks that `"lyric ` events exist):
  * A line is a phrase. A blank line, or a line that is all one [bracketed] heading ("[Chorus]", not sung), is a
    section gap: it ends the phrase too, and the aligner always gets a wildcard there for the music between
    (Syllable.gap marks the first syllable after it).
  * Words are split at whitespace and at `_` (which the game shows as a space).
  * A hyphen inside a word splits it into syllables, each timed on its own and written with `=` (a literal hyphen
    that joins the next syllable), so the game shows the word as typed. A hyphen at either end of a word is left out:
    the game would join the next word to it.
  * Shown as typed, but for what the game would act on: `"` becomes `'` (a .chart event is a quoted string), and the
    markup symbols `+ = # ^ * % $ / § < >` are left out (the game hides them, or reads them as slides, talkies,
    range shifts or rich-text tags). Each change is counted (`Lyrics.dropped`).
  * What the aligner spells (`spelling`): the characters NFKD-decomposed, accents dropped, lower case, curly
    apostrophes straight, `&` as "and", whole numbers spelled out in English; anything else is left out. A token
    with nothing left (a dash, an ellipsis) times nothing: it is shown with the word before it, or with the next
    one at the start of a line. A word with letters but none the aligner spells (another script) keeps its own
    syllable, timed from its neighbours by the engine.

**On the chart** (`place`): each syllable's start, in seconds of the decode, is quantized onto our grid as the notes
are (quantize.SnapGrid.from_ticks over the syllables' own ticks: 1/16 lines, triplet beats where a run of syllables
calls for them); a syllable that lands on or before the one ahead of it moves to the next free slot. Phrases are the
lines, also split where the next syllable starts more than REST_SPLIT_S after the one before it: no human phrase of
the six references (1,076 gaps between word starts inside phrases) has a gap over 3.02 s, 1 has one over 3.0 s, and
a third of the gaps between their phrases are longer. phrase_start comes PHRASE_LEAD_S before the first syllable
(the references' median: 0.151 s) and phrase_end PHRASE_TAIL_S after the last one starts (their median: 0.701 s),
each snapped to the grid, a phrase_end never after the next phrase's first syllable, a phrase_start never before
the phrase_end ahead of it.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Sequence

import numpy as np

from .quantize import RULES, QuantizeRules, SnapGrid
from .tempo import TempoMap

REST_SPLIT_S = 3.0       # a phrase splits where the next syllable starts more than this after the one before it
PHRASE_LEAD_S = 0.151    # phrase_start this long before the first syllable (the references' median)
PHRASE_TAIL_S = 0.701    # phrase_end this long after the last syllable starts (the references' median)
MARKUP = set("+=#^*%$/§<>")   # the symbols Clone Hero acts on: never shown from the person's text
HEADING = re.compile(r"\s*\[[^\[\]]*\]\s*")   # a line that is one [bracketed] heading: a section label, not sung
_ONES = ("zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen "
         "seventeen eighteen nineteen").split()
_TENS = "_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()


@dataclass(frozen=True)
class Syllable:
    text: str          # shown: as typed, with the markup Clone Hero would act on left out
    spelling: str      # what the aligner spells: lower-case letters and apostrophes ("" when none)
    word: int          # its word's index
    line: int          # its line's index: the phrase it opens or continues
    gap: bool          # the first syllable after a section gap (a blank line or a [heading]), or of the text
    last: bool         # the last syllable of its word; otherwise the next one is shown joined to it, with a hyphen


@dataclass(frozen=True)
class Lyrics:
    syllables: tuple[Syllable, ...]
    dropped: int       # characters left out of what is shown, or changed (" to '): the markup the game acts on

    @property
    def words(self) -> int:
        return len({s.word for s in self.syllables})

    @property
    def lines(self) -> int:
        return len({s.line for s in self.syllables})

    def word_spellings(self) -> list[str]:
        """Each word's spelling, its syllables' together."""
        out: dict[int, str] = {}
        for s in self.syllables:
            out[s.word] = out.get(s.word, "") + s.spelling
        return [out[k] for k in sorted(out)]


@dataclass(frozen=True)
class Timed:
    """Lyrics with each syllable's start in seconds of the decode (what engines/lyrics.py's align gives)."""
    lyrics: Lyrics
    starts: tuple[float, ...]


@dataclass(frozen=True)
class Phrase:
    start: int                                # phrase_start tick
    end: int                                  # phrase_end tick
    syllables: tuple[tuple[int, str], ...]    # (tick, the lyric event's text) in order


# ------------------------------------------------------------------------------------------------ the text

def _number(n: int) -> str:
    """A whole number in English words, run together ("twentyone"): what a singer sings for a numeral."""
    if n < 20:
        return _ONES[n]
    if n < 100:
        return _TENS[n // 10] + ("" if n % 10 == 0 else _ONES[n % 10])
    if n < 1000:
        return _ONES[n // 100] + "hundred" + ("" if n % 100 == 0 else _number(n % 100))
    if n < 1_000_000:
        return _number(n // 1000) + "thousand" + ("" if n % 1000 == 0 else _number(n % 1000))
    return "".join(_ONES[int(d)] for d in str(n))   # longer: digit by digit


def spelling(text: str, alphabet: frozenset[str] | set[str] | None = None) -> str:
    """The characters of `text` an aligner spells: NFKD, accents dropped, lower case, curly apostrophes straight, `&`
    as "and", whole numbers spelled out; then only the characters in `alphabet` (default: a-z and the apostrophe)."""
    alphabet = alphabet or _LATIN
    t = unicodedata.normalize("NFKD", text).lower()   # the accents come apart, and the alphabet leaves them out
    t = t.replace("’", "'").replace("‘", "'").replace("ʼ", "'").replace("&", "and")
    t = re.sub(r"\d+", lambda m: _number(int(m[0])), t)
    return "".join(c for c in t if c in alphabet)


_LATIN = frozenset("abcdefghijklmnopqrstuvwxyz'")


def _shown(token: str) -> tuple[str, int]:
    """A token as the game can show it, and how many characters were left out or changed."""
    out, n = [], 0
    for c in token:
        if c == '"':
            out.append("'")
            n += 1
        elif c in MARKUP:
            n += 1
        else:
            out.append(c)
    return "".join(out), n


def parse(text: str) -> Lyrics:
    """The text's words and syllables (the module docstring). No syllable when it holds no word."""
    syllables: list[Syllable] = []
    dropped, word, line, gap = 0, 0, 0, True
    for raw in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if not raw.strip() or HEADING.fullmatch(raw):
            gap = True
            continue
        tokens = raw.replace("_", " ").split()
        pending = ""          # what a line's leading tokens without a letter show, put before the first word
        first_of_line = len(syllables)
        for token in tokens:
            shown, n = _shown(token)
            dropped += n
            stripped = shown.strip("-")
            dropped += len(shown) - len(stripped)
            if not spelling(stripped, _ANY) and not any(c.isalnum() for c in stripped):
                # times nothing: shown with the word before it on this line, else with the next one
                if not stripped:
                    continue
                if len(syllables) > first_of_line:
                    s = syllables[-1]
                    syllables[-1] = Syllable(f"{s.text} {stripped}", s.spelling, s.word, s.line, s.gap, s.last)
                else:
                    pending = f"{pending} {stripped}".strip()
                continue
            parts = [p for p in stripped.split("-")]
            dropped += sum(1 for p in parts if not p)   # a doubled hyphen: one of them is left out
            parts = [p for p in parts if p]
            for k, p in enumerate(parts):
                shown_p = p
                if pending and k == 0:
                    shown_p, pending = f"{pending} {p}", ""
                syllables.append(Syllable(shown_p, spelling(p), word, line, gap and k == 0, k == len(parts) - 1))
            gap = False
            word += 1
        if pending:   # a line with no word at all: what it shows has nothing to be timed with
            dropped += len(pending.replace(" ", ""))
        if len(syllables) > first_of_line:
            line += 1
    return Lyrics(tuple(syllables), dropped)


_ANY = frozenset(chr(c) for c in range(ord("a"), ord("z") + 1))   # letters only: is there a word to time at all


def event_text(s: Syllable) -> str:
    """The lyric event's text: the syllable, with `=` when the next syllable of its word follows."""
    return s.text if s.last else s.text + "="


# ------------------------------------------------------------------------------------------------ the chart

def place(lyrics: Lyrics, starts: Sequence[float], tempo_map: TempoMap, pad_seconds: float = 0.0, *,
          end_tick: int | None = None, rules: QuantizeRules = RULES) -> tuple[list[Phrase], dict]:
    """The phrases on our grid (the module docstring): `starts` holds each syllable's start in seconds of the decode;
    `end_tick` is the last tick an event may take (song.ogg's end). The stats are numbers only."""
    syl = lyrics.syllables
    if len(starts) != len(syl):
        raise ValueError(f"{len(starts)} starts for {len(syl)} syllables")
    if not syl:
        return [], {"phrases": 0, "syllables": 0}
    secs = np.asarray(starts, dtype=np.float64)
    if not np.all(np.isfinite(secs)):
        raise ValueError("every syllable needs a finite start")
    secs = np.maximum.accumulate(secs)    # the text's order is the song's order
    raw = tempo_map.secs_to_ticks(secs + pad_seconds)
    grid = SnapGrid.from_ticks(raw, tempo_map, rules)
    ticks, moved = [], 0
    for t in raw:
        k = grid.snap(float(t))
        if ticks and k <= ticks[-1]:
            k = grid.next_slot(ticks[-1])
            moved += 1
        ticks.append(k)
    shift_ms = np.abs(tempo_map.ticks_to_secs(np.asarray(ticks)) - (secs + pad_seconds)) * 1000
    # the phrases: the lines, split at long rests
    groups: list[list[int]] = []
    for i, s in enumerate(syl):
        if not groups or s.line != syl[i - 1].line or secs[i] - secs[i - 1] > REST_SPLIT_S:
            groups.append([])
        groups[-1].append(i)
    rest_splits = len(groups) - lyrics.lines
    last = end_tick if end_tick is not None else max(ticks) + tempo_map.resolution
    phrases: list[Phrase] = []
    for g, idx in enumerate(groups):
        first, final = ticks[idx[0]], ticks[idx[-1]]
        lead = grid.snap(float(tempo_map.sec_to_tick(secs[idx[0]] + pad_seconds - PHRASE_LEAD_S)))
        start = min(max(lead, phrases[-1].end if phrases else 0), first)
        nxt = ticks[groups[g + 1][0]] if g + 1 < len(groups) else last
        tail = grid.snap(float(tempo_map.sec_to_tick(secs[idx[-1]] + pad_seconds + PHRASE_TAIL_S)))
        end = max(min(tail, nxt, last), final + 1)
        phrases.append(Phrase(start, end, tuple((ticks[i], event_text(syl[i])) for i in idx)))
    stats = {"phrases": len(phrases), "syllables": len(syl), "words": lyrics.words, "lines": lyrics.lines,
             "rest_splits": rest_splits, "moved_to_next_slot": moved,
             "snap_ms": {"median": round(float(np.median(shift_ms)), 2), "max": round(float(np.max(shift_ms)), 2)},
             "triplet_beats": len(grid.triplet_beats)}
    return phrases, stats


def events(phrases: Sequence[Phrase]) -> list[tuple[int, int, str]]:
    """The [Events] rows (tick, order, text) of the phrases: on one tick a phrase_end comes before a phrase_start,
    which comes before its lyric."""
    rows: list[tuple[int, int, str]] = []
    for p in phrases:
        rows.append((p.start, 2, "phrase_start"))
        rows += [(t, 3, f"lyric {text}") for t, text in p.syllables]
        rows.append((p.end, 1, "phrase_end"))
    return rows


EVENT = re.compile(r'(\d+) = E "(phrase_start|phrase_end|lyric .*)"')   # a lyric event line of [Events]
_RE_EVENT = re.compile(r'(\d+) = E "(phrase_start|phrase_end|lyric (.*))"')


def read_events(event_lines: Sequence[str]) -> list[Phrase]:
    """The lyric phrases of a chart's [Events] lines (trimmed), as Clone Hero reads them: a phrase_start opens a
    phrase (ending one still open), a phrase_end closes it, and a lyric outside any phrase is not shown."""
    out: list[Phrase] = []
    start, sylls = None, []
    for line in event_lines:
        m = _RE_EVENT.fullmatch(line)
        if not m:
            continue
        tick = int(m[1])
        if m[2] == "phrase_start":
            if start is not None:
                out.append(Phrase(start, tick, tuple(sylls)))
            start, sylls = tick, []
        elif m[2] == "phrase_end":
            if start is not None:
                out.append(Phrase(start, tick, tuple(sylls)))
            start, sylls = None, []
        elif start is not None:
            sylls.append((tick, m[3]))
    if start is not None:
        out.append(Phrase(start, start, tuple(sylls)))
    return out


def shown_lines(phrases: Sequence[Phrase]) -> list[str]:
    """Each phrase as Clone Hero shows it in plain text: `-` joins the next syllable and is hidden, `=` joins it and
    shows a hyphen, `_` is a space, the other markup symbols are hidden, and syllables not joined are spaced."""
    lines = []
    for p in phrases:
        out, join = "", True
        for _, text in p.syllables:
            joins = text.endswith("-") or text.endswith("=")
            body = text[:-1] + "-" if text.endswith("=") else text.rstrip("-") if joins else text
            body = "".join(c for c in body.replace("_", " ") if c not in MARKUP - {"="} or c == "-")
            out += ("" if join else " ") + body
            join = joins
        lines.append(out.strip())
    return lines
