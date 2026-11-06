"""Star power, drum activation lanes (fills) and solos: placed on each Expert part, then fitted to every difficulty.

Everything works in ticks of the song's own TempoMap, after quantizing (the rules need measure lines) and before the
reductions: reduce.py copies Expert's phrases to every level and keeps a note in each (a star-power phrase keeps a
note, a fill keeps its activation note). `fit_phrases` then fits each level's copies to its own notes. The rules
follow DESIGN.md 2.10 with the critique's corrections (CRITIQUE.json, which wins where they differ), checked against
63 Harmonix and 46 custom charts (scan-chart parses) and YARG's activation-lane generator (its ideas, no code).

Star power (every 5-fret part and drums), `place_star_power`:
  1. Count: K = round(span / 40 beats), the span running from the first to the last Expert onset (Harmonix: one
     phrase per 41 beats, median 11 a song; about 24 on the 6:52 test song), its beats counted at most at 160 BPM
     (`StarPowerRules.max_bpm`), so at most one phrase per 15 s: the human charts of the two 200-BPM stress songs
     write about 0.82 times the slower songs' phrases per beat, and far more a minute than the slower songs' (M6-01,
     DESIGN.md 2.10). Drums may get fewer, since their fills are placed first (the critique: Encore does not ask for
     drum star power).
  2. Shape: one measure. A phrase starts on the measure's first Expert onset (Harmonix 92 %, customs 98 % start on a
     note) and ends on the next measure line: `S 2` covers [T, T + length), so the next downbeat is outside.
  3. Exclusions: none in the first 4 measures from the first onset's measure, and the last at least 8 measures
     before the last onset's (Harmonix: the first phrase about 6 measures in, the last about 14 before the end).
     On drums none near a fill (see the fills).
  4. Score of a measure: +2 a sustain starts in it, +2 it opens a section, +1 its first onset is on the downbeat,
     plus the caller's bonus (DESIGN's +1 for lead-like playing), plus min(onsets, 8) / 8. It needs 2 onsets.
  5. Placement: the eligible measures split into K equal windows; at most one phrase per window, starts at least 24
     beats apart (Harmonix: median 8 measures between phrases, p10 4.5). Of all such sets the one with the most
     phrases, then the highest total score, then the phrases nearest their window centres, then the earliest: an
     exact dynamic programme, so the result never depends on a greedy order.

Drum activation lanes (fills, `S 64`), `schedule_drums` and `place_fills`:
  * A fill is the measure before a measure line D and ends exactly on its activation note: the Expert onset at D,
    unless that onset has no crash and a crash with a kick or snare lies within an 8th of it (YARG's rule, except
    that any crash on the line keeps it: a lone crash never moves the end off the line); with no onset at D, the
    best one within an 8th (a crash with a kick or snare, then any crash, then any hand hit, then the nearest, then
    the earlier). The phrase includes its last tick, and Clone Hero, YARG and the chart-format notes take the note
    at that end as the activation note (YARG takes the first note at or after the end, so a phrase must never end
    past its note). Harmonix: 92 % of fills end on a note, 90 % on a measure line (all of them on the four Harmonix
    test references); median 1 measure.
  * DESIGN asks for fills ending on a crash downbeat. A crash is a preference, never a requirement (a source that
    writes its crashes as hi-hats, like ADTOF on the test song, would lose its fills and then its star power): a
    crash (`_Fills._crash`: a green cymbal, or a yellow or blue one with fewer than 3 others on its pad within 2
    beats) wins only among the lines step 3 below can choose from, and `check_phrases` warns when fewer than half of
    the Expert fills end on one (the four Harmonix test references: 0.63-1.00).
  * A fill needs 2 Expert onsets before its activation note and 16 hits in the 4 measures after it (enough to use
    the star power, YARG's rule), and 4 measures of the part after its measure line.
  * Fills are at least 4 measures apart (activation line to activation line; Harmonix median 4) and never overlap,
    touch or abut star power: 2 clear beats on both sides, and an activation note at least 2 s after the end of the
    phrase before it (YARG). Harmonix overlaps 9 % of its fills with star power; we never do.
  * Scheduling, in the critique's order (fills first at section changes, then star power in the gaps):
      1. a fill at every section change that allows one (the earlier of two close changes wins);
      2. star power in the gaps (rule 5 above, kept clear of those fills);
      3. more fills where they are useful once the player can have star power: one in every gap between two
         phrases that has none (the earliest crash line that allows one, else the earliest line), so the meter can
         be spent before more is due; then one wherever 4 measures pass without a fill (the first crash line among
         the 4 from the first line that allows one, else that line). Harmonix spaces its fills 4 measures apart
         (the four Harmonix test references: median gap 4, p90 4.0-4.3, 5.0-8.7 fills a minute), as YARG's
         generator does (it takes 2 where 4 measures last over 10 s; we do not);
      4. fills the player cannot use are dropped: Clone Hero shows a fill only with half a meter, which takes two
         phrases, so a fill must start after the second phrase ends.
    A part too sparse for these fills gets looser ones (an onset within a beat of the line, none needed around it,
    every 4 measures); if even those find no place the part gets no star power, since star power without fills is
    scan-chart's noDrumActivationLanes and nothing asks for drum star power.
  * Every drum difficulty gets its own fills (the critique: scan-chart checks noDrumActivationLanes per track),
    each ending on a note that exists on that difficulty (`fit_phrases`).

Solos (lead guitar), `place_solos`: on the sections named "Solo" (allin1's solo label), those the caller confirms
when it passes a test (e.g. `stem_confirm`: vocals quiet, guitar loud), or exactly the sections a person names.
Neither signal is reliable (DESIGN 2.10, the solo evaluation): on six references the label and the stem test each
find 1 of the 2 human solos and make 2 and 1 false ones, and the stem test rejects both solos the friend confirmed
on the test song (the vocals stem is active in 0.561 and 0.863 of their frames), where the label covers all of the
second and half of the first. So the pipeline places them by the label; `place_phrases` places none unless asked.
Confirmed solo sections next to each other are one run. A solo is a featured lead break of a length human charters
write, and solos are a minority of the song (DESIGN 2.10; M5-03 measured 14 human solos on 13 human charts):
  * Splitting: a run longer than `SoloRules.max_measures` (56) or `max_seconds` (100 s) gives its densest window:
    from measure line to measure line (or the run's ends), within both caps, the most Expert onsets, ties to the
    earlier start. The rest of the run on either side is split the same way while it is over a cap; every piece is
    a candidate. A run within both caps is one candidate.
  * Choosing: a candidate needs 4 measures and 16 Expert onsets; the densest (onsets per measure, ties to the
    earlier) are taken, at most 3 a song (human median 1, p90 2-3), skipping any that starts or ends within
    `min_gap_measures` (4) of a solo already taken (so a split run never gives back-to-back markers, while a long run
    can still give separated solos). One that would take the solos' seconds past `max_share` (0.40) of the
    first..last Expert onset's is cut to its densest measure-aligned window within the budget left, or skipped when
    that window lacks the minimums. A person's names (`names`) are neither split, gapped nor share-capped.
`E solo` sits on the candidate's first onset and `E soloend` on its last.

Lower difficulties, `fit_phrases`: Expert's phrases on every level, as human charts have them, fitted to its notes:
  * a star-power phrase with no note on the level stretches to the level's nearest onset within a beat if it stays
    clear of the other phrases, else it is dropped there (scan-chart's emptyStarPower);
  * a fill ends on the level's last onset inside it, and is dropped there unless that is a beat after its start
    (all are kept, however short, when none is and the level has star power);
  * a solo with no note on the level is dropped (emptySoloSection).

`check_phrases` re-checks one instrument's tracks: scan-chart's emptyStarPower, noStarPower, emptySoloSection and
noDrumActivationLanes, and our rules (a fill ends on a note of its level, fills keep clear of star power, phrases do
not overlap, and once star power can be used every gap between two phrases holds a fill); it warns when fewer than
half of the Expert fills end on a crash, which points at the source's cymbal labels more often than at the music.
"""
from __future__ import annotations

import bisect
import re
from dataclasses import asdict, dataclass, replace
from typing import Callable, Sequence

import numpy as np

from .chart import DRUM_ACTIVATION, STAR_POWER, Chart, DrumHit, Phrase, Track
from .reduce import Issue
from .tempo import TempoMap

Bonus = Callable[[int, int], float]  # (phrase start tick, end tick) -> extra score


@dataclass(frozen=True)
class StarPowerRules:
    beats_per_phrase: float = 40.0  # K = round(span in beats / this)
    max_bpm: float = 160.0          # the span's beats counted at most at this tempo (its average over the span): on
                                    # 200-BPM songs the humans write 0.82 times the slower songs' phrases per beat
                                    # (M6-01); 160 is the middle of the fit's plateau (150-165), at most 1 per 15 s
    min_start_gap: float = 24.0     # beats between two phrase starts
    lead_measures: int = 4          # no phrase in the first measures from the first onset's
    tail_measures: int = 8          # the last phrase this many measures before the last onset's
    min_onsets: int = 2             # Expert onsets a phrase needs


@dataclass(frozen=True)
class FillRules:
    window: float = 0.5             # beats either side of the measure line to look for the activation note
    min_inside: int = 2             # Expert onsets before the activation note
    after_hits: int = 16            # Expert hits in the measures after it
    after_measures: int = 4
    min_gap_measures: int = 4       # between two fills' activation lines
    period_measures: int = 4        # step 3: a fill wherever this many measures pass without one
    sp_gap_beats: float = 2.0       # clear beats between a fill and a star-power phrase, both sides
    sp_gap_s: float = 2.0           # seconds from a phrase's end to the next activation note
    phrases_before: int = 2         # phrases a player needs before a fill is shown (half a meter)
    min_level_beats: float = 1.0    # a fill on a lower level ends at least this long after its start
    min_crash_share: float = 0.5    # check_phrases warns below this share of Expert fills ending on a crash


@dataclass(frozen=True)
class SoloRules:
    """The solo rules (DESIGN.md 2.10), the caps set from 14 human solos on 13 human charts (the six references and
    the stress set's guitar charts, M5-03): their 95th percentile of length, 52.9 measures and 96.4 s, and their
    largest share of a chart's span, 0.357. M6-01 measured the second 200-BPM song's five charts too: their long solo
    is 56.0-57.9 of their own measures (67-70 s), the measures of our doubled grid, where the 56-measure cap gives
    67 s covering 0.96-1.00 of it; so the caps count our grid's measures, doubled or not."""
    min_measures: int = 4
    min_onsets: int = 16
    max_solos: int = 3              # human median 1 a song, p90 2-3
    max_measures: int = 56          # a candidate's length on our map: p95 rounded up to a multiple of 8, in [16, 64]
    max_seconds: float = 100.0      # the same in seconds (our map may be at twice the humans' tempo): p95 rounded up
                                    # to the next 10 s, in [30, 120]
    max_share: float = 0.40         # the solos' seconds against the first..last Expert onset's: the largest human
                                    # share rounded up to the next 0.05, at least 0.15
    min_gap_measures: float = 4.0   # between two solos, so a split run never gives back-to-back markers


SP_RULES = StarPowerRules()
FILL_RULES = FillRules()
SOLO_RULES = SoloRules()
_SOLO = re.compile(r"\bsolo\b", re.IGNORECASE)


# ------------------------------------------------------------------------------------------------ shared

class _Bars:
    """Measure lines of a tempo map up to a little past a tick."""

    def __init__(self, tempo: TempoMap, last_tick: int, room: int = 8):
        last_tick = max(last_tick, 0)
        self.starts = tempo.measure_starts(last_tick + room * tempo.measure_length(tempo.time_signature_at(last_tick)))

    def index(self, tick: int) -> int:
        return max(bisect.bisect_right(self.starts, tick) - 1, 0)

    def end(self, i: int) -> int:
        return self.starts[i + 1]


def _onsets(track: Track) -> list[int]:
    return sorted({n.tick for n in track.notes})


def _between(ticks: list[int], a: int, b: int) -> list[int]:
    """The ticks in [a, b)."""
    return ticks[bisect.bisect_left(ticks, a):bisect.bisect_left(ticks, b)]


def _kind(track: Track, kind: int) -> list[Phrase]:
    return sorted((p for p in track.phrases if p.kind == kind), key=lambda p: p.tick)


def _long(onsets: list[int], tempo: TempoMap) -> bool:
    """scan-chart's condition for noStarPower and noDrumActivationLanes: over 50 onsets spanning over 60 s."""
    return len(onsets) > 50 and tempo.tick_to_sec(onsets[-1]) - tempo.tick_to_sec(onsets[0]) > 60


def _clear(s: int, e: int, fill: Phrase, tempo: TempoMap, rules: FillRules) -> bool:
    """Whether the star-power phrase [s, e) keeps clear of the fill (rules: FillRules.sp_gap_*)."""
    gap = round(rules.sp_gap_beats * tempo.resolution)
    a, t = fill.tick, fill.tick + fill.length
    if e <= a - gap and tempo.tick_to_sec(t) - tempo.tick_to_sec(e) >= rules.sp_gap_s - 1e-9:
        return True
    return s >= t + gap


# ------------------------------------------------------------------------------------------------ star power

@dataclass(frozen=True)
class _Candidate:
    start: int      # the measure's first onset
    end: int        # the next measure line
    score: float
    window: int
    dist: float     # measures from the window's centre


def place_star_power(expert: Track, tempo: TempoMap, sections: Sequence[int] = (), *, count: int | None = None,
                     bonus: Bonus | None = None, allowed: Callable[[int, int], bool] | None = None,
                     rules: StarPowerRules = SP_RULES, record: dict | None = None) -> list[Phrase]:
    """Star-power phrases for an Expert part (rules 1-5 of the module docstring).

    sections: section start ticks (measure lines); a measure opening one scores +2.
    count:    the number of phrases to aim for, instead of rule 1's.
    bonus:    extra score for a phrase [start, end), e.g. +1 where the part plays lead.
    allowed:  a phrase [start, end) is only placed where this returns True (schedule_drums keeps it off fills).
    record:   filled with rule 1's numbers (report.json's phrases.<part>.star_power_count): "rules" (StarPowerRules'
              values), "span_beats" and "span_seconds" (first to last Expert onset), "counted_beats" (the beats,
              at most span_seconds x max_bpm / 60) and "target" (K, or `count`); the counts are None without onsets.
    """
    onsets = _onsets(expert)
    res = tempo.resolution
    k = count
    if record is not None:
        record.update(rules=asdict(rules), span_beats=None, span_seconds=None, counted_beats=None, target=count)
    if onsets and count is None:
        beats = (onsets[-1] - onsets[0]) / res
        seconds = tempo.tick_to_sec(onsets[-1]) - tempo.tick_to_sec(onsets[0])
        counted = min(beats, seconds * rules.max_bpm / 60)
        k = round(counted / rules.beats_per_phrase)
        if record is not None:
            record.update(span_beats=round(beats, 3), span_seconds=round(seconds, 3), counted_beats=round(counted, 3),
                          target=k)
    if not onsets or len(onsets) < rules.min_onsets or k <= 0:
        return []
    bars = _Bars(tempo, onsets[-1])
    lo = bars.index(onsets[0]) + rules.lead_measures
    hi = bars.index(onsets[-1]) - rules.tail_measures
    if hi < lo:
        return []
    n = hi - lo + 1
    k = min(k, n)
    sustained = sorted({nt.tick for nt in expert.notes if getattr(nt, "length", 0) > 0})
    opens = set(sections)
    cands = []
    for i in range(lo, hi + 1):
        m, e = bars.starts[i], bars.end(i)
        inside = _between(onsets, m, e)
        if len(inside) < rules.min_onsets or (allowed is not None and not allowed(inside[0], e)):
            continue
        s = inside[0]
        score = (2 * bool(_between(sustained, m, e)) + 2 * (m in opens) + (s == m)
                 + min(len(inside), 8) / 8 + (bonus(s, e) if bonus else 0.0))
        w = min(k - 1, (i - lo) * k // n)
        cands.append(_Candidate(s, e, score, w, abs(i + 0.5 - (lo + (w + 0.5) * n / k))))
    chosen = _choose(cands, round(rules.min_start_gap * res))
    return [Phrase(c.start, c.end - c.start, STAR_POWER) for c in chosen]


def _choose(cands: list[_Candidate], gap: int) -> list[_Candidate]:
    """The best chain of candidates (in time order): one per window at most, starts at least `gap` apart.
    Best = most phrases, then highest total score, then smallest distance to the window centres, then earliest."""
    best: list[tuple[tuple, int]] = []
    for j, c in enumerate(cands):
        value, parent = (1, c.score, -c.dist, -c.start), -1
        for i in range(j):
            p = cands[i]
            if p.window < c.window and c.start - p.start >= gap:
                v = best[i][0]
                trial = (v[0] + 1, v[1] + c.score, v[2] - c.dist, v[3] - c.start)
                if trial > value:
                    value, parent = trial, i
        best.append((value, parent))
    if not best:
        return []
    j = max(range(len(best)), key=lambda x: best[x][0])
    out = []
    while j >= 0:
        out.append(cands[j])
        j = best[j][1]
    return out[::-1]


# ------------------------------------------------------------------------------------------------ fills

class _Fills:
    """Fill placement on one Expert drum track."""

    def __init__(self, expert: Track, tempo: TempoMap, rules: FillRules):
        self.tempo, self.rules = tempo, rules
        self.res = tempo.resolution
        self.groups: dict[int, list[DrumHit]] = {}
        for h in expert.notes:
            self.groups.setdefault(h.tick, []).append(h)
        self.onsets = sorted(self.groups)
        self.hit_ticks = sorted(h.tick for h in expert.notes)
        self.solos = list(expert.solos)
        self.bars = _Bars(tempo, self.onsets[-1] if self.onsets else 0)
        # cymbal ticks per pad, to tell a crash from a hi-hat or ride pattern (as reduce.py does)
        self.cymbals = {p: sorted(h.tick for h in expert.notes if h.cymbal and h.pad == p) for p in (2, 3, 4)}

    def _crash(self, h: DrumHit) -> bool:
        if not h.cymbal:
            return False
        if h.pad == 4:
            return True
        span = 2 * self.res
        run = self.cymbals[h.pad]
        others = bisect.bisect_right(run, h.tick + span) - bisect.bisect_left(run, h.tick - span) - 1
        return others < 3

    def _crash_at(self, t: int) -> bool:
        return any(self._crash(h) for h in self.groups[t])

    def _activation(self, line: int) -> int | None:
        """The activation note for a fill ending at a measure line (the module docstring's preference order)."""
        w = round(self.rules.window * self.res)
        near = _between(self.onsets, line - w, line + w + 1)
        if not near:
            return None

        def key(t):
            hits = self.groups[t]
            crash = self._crash_at(t)
            strong = crash and any(h.pad in (0, 1) for h in hits)
            return not strong, not crash, not any(h.pad for h in hits), abs(t - line), t

        best = min(near, key=key)
        if line in self.groups and (self._crash_at(line) or key(best)[0]):
            return line  # the note on the line, unless it has no crash and a crash with a kick or snare is near
        return best

    def candidate(self, k: int) -> Phrase | None:
        """The fill whose activation is at measure line k, if the part allows one there."""
        r, bars = self.rules, self.bars
        if k < 1 or not self.onsets or k + max(r.after_measures, 1) >= len(bars.starts):
            return None
        line, a = bars.starts[k], bars.starts[k - 1]
        t = self._activation(line)
        if t is None or len(_between(self.onsets, a, t)) < r.min_inside:
            return None
        after = bisect.bisect_right(self.hit_ticks, bars.starts[k + r.after_measures]) - \
            bisect.bisect_right(self.hit_ticks, t)
        if after < r.after_hits or bars.starts[k + r.after_measures] > self.onsets[-1]:
            return None
        if any(a <= b0 and s0 <= t for s0, b0 in self.solos):
            return None
        return Phrase(a, t - a, DRUM_ACTIVATION)

    def fits(self, k: int, fill: Phrase, fills: dict[int, Phrase], star_power: Sequence[Phrase]) -> bool:
        if any(abs(k - j) < self.rules.min_gap_measures for j in fills):
            return False
        return all(_clear(p.tick, p.tick + p.length, fill, self.tempo, self.rules) for p in star_power)

    def try_add(self, k: int, fills: dict[int, Phrase], star_power: Sequence[Phrase]) -> bool:
        f = self.candidate(k)
        if f is None or not self.fits(k, f, fills, star_power):
            return False
        fills[k] = f
        return True

    def at_sections(self, sections: Sequence[int], star_power: Sequence[Phrase] = ()) -> dict[int, Phrase]:
        """Step 1: a fill ending at each section change that allows one, the earlier change first."""
        fills: dict[int, Phrase] = {}
        for s in sorted(set(sections)):
            k = self.bars.index(s)
            if k + 1 < len(self.bars.starts) and self.bars.starts[k + 1] - s < s - self.bars.starts[k]:
                k += 1  # a section start off the measure lines uses the nearest one
            self.try_add(k, fills, star_power)
        return fills

    def available(self, star_power: Sequence[Phrase]) -> int:
        """The tick from which a player can have enough star power to activate (0: the part has none)."""
        sp = sorted(star_power, key=lambda p: p.tick)
        if not sp:
            return 0
        p = sp[min(self.rules.phrases_before, len(sp)) - 1]
        return p.tick + p.length

    def _crash_line(self, k: int) -> bool:
        t = self._activation(self.bars.starts[k])
        return t is not None and self._crash_at(t)

    def fill_gaps(self, fills: dict[int, Phrase], star_power: Sequence[Phrase]) -> dict[int, Phrase]:
        """Step 3: a fill in every star-power gap without one, then one wherever `period_measures` pass without, a
        crash line first among the lines each may take. Fills before the player can have star power go first, so
        they do not crowd out the useful ones."""
        sp = sorted(star_power, key=lambda p: p.tick)
        start = self.available(sp)
        fills = {k: f for k, f in fills.items() if f.tick >= start}
        lines = self.bars.starts
        n, period = len(lines), self.rules.period_measures

        def by_crash(ks):
            return sorted(ks, key=lambda k: (not self._crash_line(k), k))

        for p, q in zip(sp, sp[1:]):
            end = p.tick + p.length
            if end < start or any(end < f.tick + f.length < q.tick for f in fills.values()):
                continue
            for k in by_crash(range(self.bars.index(end) + 1, bisect.bisect_left(lines, q.tick))):
                if self.try_add(k, fills, sp):
                    break
        first = self.bars.index(start) + (lines[self.bars.index(start)] < start)
        prev = first - period
        k = max(first, 1)
        while k < n:
            done = [j for j in fills if j <= k]
            if done:
                prev = max(prev, max(done))
            f = self.candidate(k) if k - prev >= period else None
            if f is not None and self.fits(k, f, fills, sp):
                # k takes a fill; a crash line among the next ones takes it instead
                k = prev = next(j for j in by_crash(range(k, min(k + period, n))) if self.try_add(j, fills, sp))
            k += 1
        return fills

    def usable(self, fills: dict[int, Phrase], star_power: Sequence[Phrase]) -> list[Phrase]:
        """Step 4: the fills a player can see, in time order."""
        start = self.available(star_power)
        return [f for _, f in sorted(fills.items()) if f.tick >= start]


def schedule_drums(expert: Track, tempo: TempoMap, sections: Sequence[int] = (), *, count: int | None = None,
                   bonus: Bonus | None = None, sp_rules: StarPowerRules = SP_RULES,
                   fill_rules: FillRules = FILL_RULES,
                   sp_record: dict | None = None) -> tuple[list[Phrase], list[Phrase]]:
    """(star power, fills) for an Expert drum track, scheduled in the module docstring's steps 1-4. sp_record: filled
    as place_star_power's record."""
    if not expert.is_drums:
        raise ValueError(f"schedule_drums needs a drum track, not {expert.name}")
    ctx = _Fills(expert, tempo, fill_rules)
    fills = ctx.at_sections(sections)

    def allowed(s: int, e: int) -> bool:
        return all(_clear(s, e, f, tempo, fill_rules) for f in fills.values())

    sp = place_star_power(expert, tempo, sections, count=count, bonus=bonus, allowed=allowed, rules=sp_rules,
                          record=sp_record)
    fills = ctx.usable(ctx.fill_gaps(fills, sp), sp)
    if sp and not fills and _long(_onsets(expert), tempo):
        # too sparse for the usual fills: try looser ones, else no star power (scan-chart's noDrumActivationLanes
        # fires on star power without fills, and nothing asks for drum star power)
        loose = _Fills(expert, tempo, replace(fill_rules, window=1.0, min_inside=0, after_hits=0, period_measures=4))
        fills = loose.usable(loose.fill_gaps({}, sp), sp)
        if not fills:
            sp = []
    return sp, fills


def place_fills(expert: Track, tempo: TempoMap, sections: Sequence[int] = (),
                star_power: Sequence[Phrase] | None = None, *, rules: FillRules = FILL_RULES) -> list[Phrase]:
    """Fills for an Expert drum track around star power already placed (the track's own unless given): steps 1, 3
    and 4 of the module docstring."""
    if not expert.is_drums:
        raise ValueError(f"place_fills needs a drum track, not {expert.name}")
    sp = list(star_power) if star_power is not None else _kind(expert, STAR_POWER)
    ctx = _Fills(expert, tempo, rules)
    return ctx.usable(ctx.fill_gaps(ctx.at_sections(sections, sp), sp), sp)


# ------------------------------------------------------------------------------------------------ solos

def solo_sections(sections: Sequence[tuple[int, str]], end_tick: int, *,
                  confirm: Callable[[int, int], bool] | None = None,
                  names: Sequence[str] | None = None, tempo: TempoMap | None = None, onsets: Sequence[int] = (),
                  rules: SoloRules = SOLO_RULES) -> list[tuple[int, int]]:
    """The candidate solos: half-open tick ranges of the sections named as solos that `confirm` accepts (all if
    None), consecutive ones one run; the last section runs to end_tick. With `tempo`, a run longer than
    rules.max_measures or rules.max_seconds is split around its densest window of the sorted Expert `onsets` (the
    module docstring's splitting). names: exactly these sections instead (a person's choice, which neither the
    "Solo" label, confirm nor the caps overrule: nothing is split)."""
    secs = sorted(sections)
    runs: list[list[tuple[int, int]]] = []
    for i, (tick, name) in enumerate(secs):
        if (name not in names) if names is not None else not _SOLO.search(name):
            continue
        stop = secs[i + 1][0] if i + 1 < len(secs) else max(end_tick, tick)
        if names is None and confirm is not None and not confirm(tick, stop):
            continue
        if runs and runs[-1][-1][1] == tick:
            runs[-1].append((tick, stop))
        else:
            runs.append([(tick, stop)])
    if tempo is None or names is not None or not runs:
        return [(run[0][0], run[-1][1]) for run in runs]
    caps = _Caps(tempo, max(end_tick, runs[-1][-1][1]), rules)
    return [c for run in runs for c in caps.split(run[0][0], run[-1][1], onsets)]


class _Caps:
    """A solo candidate's length caps (SoloRules.max_measures, max_seconds) on a tempo map's measure lines."""

    def __init__(self, tempo: TempoMap, last_tick: int, rules: SoloRules):
        self.tempo, self.rules = tempo, rules
        self.starts = _Bars(tempo, last_tick).starts

    def measures(self, a: int, b: int) -> int:
        """The measure lines in [a, b): a span from line to line has that many measures."""
        return bisect.bisect_left(self.starts, b) - bisect.bisect_left(self.starts, a)

    def position(self, tick: int) -> float:
        """The tick in measures from the first line, with the fraction of its measure."""
        i = max(bisect.bisect_right(self.starts, tick) - 1, 0)
        j = i + 1 if i + 1 < len(self.starts) else i - 1
        return i + (tick - self.starts[i]) / max(abs(self.starts[j] - self.starts[i]), 1)

    def near(self, c: "_Solo", kept: "_Solo") -> bool:
        """Whether candidate c starts within min_gap_measures after the kept solo's end, or ends within them before
        its start (candidates never overlap)."""
        gap = self.rules.min_gap_measures
        if c.start > kept.end:
            return self.position(c.start) - self.position(kept.end) < gap
        return self.position(kept.start) - self.position(c.end) < gap

    def within(self, a: int, b: int) -> bool:
        return (self.measures(a, b) <= self.rules.max_measures
                and self.tempo.tick_to_sec(b) - self.tempo.tick_to_sec(a) <= self.rules.max_seconds + 1e-9)

    def split(self, a: int, b: int, onsets: Sequence[int]) -> list[tuple[int, int]]:
        """A run's candidates: the run if it is within both caps; else its densest window (`window`) and the rest of
        the run on either side, each split the same way while it is over a cap."""
        if self.within(a, b):
            return [(a, b)]
        s, e = self.window(a, b, onsets)
        return (self.split(a, s, onsets) if s > a else []) + [(s, e)] + (self.split(e, b, onsets) if e < b else [])

    def window(self, a: int, b: int, onsets: Sequence[int]) -> tuple[int, int]:
        """The window of [a, b) within both caps with the most onsets, ties to the earlier start: it starts on a or a
        measure line inside and ends on a line inside or b, at least one measure even when that is over a cap."""
        bounds = [a] + self.starts[bisect.bisect_right(self.starts, a):bisect.bisect_left(self.starts, b)] + [b]
        best, j = None, 1
        for i in range(len(bounds) - 1):
            j = max(j, i + 1)
            while j + 1 < len(bounds) and self.within(bounds[i], bounds[j + 1]):
                j += 1          # the furthest end within both caps never moves back as the start moves on
            n = bisect.bisect_left(onsets, bounds[j]) - bisect.bisect_left(onsets, bounds[i])
            if best is None or n > best[0]:
                best = (n, bounds[i], bounds[j])
        return best[1], best[2]


@dataclass(frozen=True)
class _Solo:
    start: int          # the candidate's first Expert onset
    end: int            # its last (Track.solos ends are inclusive)
    measures: int
    onsets: int
    span: tuple[int, int] = (0, 0)   # the candidate's ticks [a, b): sections, or a window of them

    def row(self) -> dict:
        return {"start": self.start, "end": self.end, "measures": self.measures, "onsets": self.onsets,
                "per_measure": round(self.onsets / max(self.measures, 1), 2)}


def place_solos(expert: Track, tempo: TempoMap, sections: Sequence[tuple[int, str]], *,
                confirm: Callable[[int, int], bool] | None = None, names: Sequence[str] | None = None,
                rules: SoloRules = SOLO_RULES, record: dict | None = None) -> list[tuple[int, int]]:
    """Solos (first onset, last onset; Track.solos ends are inclusive) from the sections named as solos: the
    candidates of `solo_sections` with rules.min_onsets and rules.min_measures, the densest first (Expert onsets per
    measure, ties to the earlier), at most rules.max_solos, skipping any within rules.min_gap_measures of a solo
    already taken (so the parts of a split run never come back to back). One that would take the solos' seconds past
    rules.max_share of the first..last Expert onset's is cut to its densest measure-aligned window that fits the
    budget left (`_trim`), so a song never loses its only solo to the share, or skipped when no such window has the
    minimums. Sorted by start.

    confirm: a test of each solo section [start, end) in ticks, e.g. `stem_confirm` (the vocals stem is quiet).
             It rejects real solos with singing or bleed in the vocals stem: the test song's two confirmed solos
             and Kimochi Warui's (vocals active in 0.561, 0.863 and 0.905 of their frames).
    names:   the sections a person named as solos (exact section names), instead of the label and confirm. The
             test song's player named "Solo 1" and "Solo 2", which the stem test rejects. Nothing is split, and
             neither the gap nor the share applies; the 16-onset and 4-measure minimums and the 3-solo cap do.
    record:  filled with what was used and why (report.json's phrases.guitar): "rules" (SoloRules' values),
             "capped" (False with names), "solos" (per solo: start and end ticks, measures, onsets, onsets per
             measure), "skipped_by_gap" and "skipped_by_share" (the candidates each rule skipped, the same fields)
             and "trimmed_by_share" (the candidates the share cut to a window, as they were).
    """
    if record is not None:
        record.update(rules=asdict(rules), capped=names is None, solos=[], skipped_by_gap=[], trimmed_by_share=[],
                      skipped_by_share=[])
    onsets = _onsets(expert)
    if not onsets:
        return []
    caps = _Caps(tempo, onsets[-1], rules)
    candidates = []
    for a, b in solo_sections(sections, onsets[-1] + 1, confirm=confirm, names=names, tempo=tempo, onsets=onsets,
                              rules=rules):
        inside = _between(onsets, a, b)
        measures = caps.measures(a, b)
        if len(inside) >= rules.min_onsets and measures >= rules.min_measures:
            candidates.append(_Solo(inside[0], inside[-1], measures, len(inside), (a, b)))
    candidates.sort(key=lambda c: (-c.onsets / max(c.measures, 1), c.start))
    sec = tempo.tick_to_sec
    budget = rules.max_share * (sec(onsets[-1]) - sec(onsets[0]))
    picked: list[_Solo] = []
    near: list[_Solo] = []
    trimmed: list[_Solo] = []
    skipped: list[_Solo] = []
    total = 0.0
    for c in candidates:
        if len(picked) == rules.max_solos:
            break
        if names is None and any(caps.near(c, k) for k in picked):
            near.append(c)
            continue
        length = sec(c.end) - sec(c.start)
        if names is None and total + length > budget + 1e-9:
            cut = _trim(c, budget - total, tempo, onsets, rules)
            if cut is None:
                skipped.append(c)
                continue
            trimmed.append(c)
            c, length = cut, sec(cut.end) - sec(cut.start)
        picked.append(c)
        total += length
    picked.sort(key=lambda c: c.start)
    if record is not None:
        record.update(solos=[c.row() for c in picked], skipped_by_gap=[c.row() for c in near],
                      trimmed_by_share=[c.row() for c in trimmed], skipped_by_share=[c.row() for c in skipped])
    return [(c.start, c.end) for c in picked]


def _trim(c: _Solo, room: float, tempo: TempoMap, onsets: list[int], rules: SoloRules) -> _Solo | None:
    """Candidate c cut to its densest window (`_Caps.window`, measure-aligned) whose seconds fit `room`, the share
    budget left; None when even that window fails the minimums or a single measure is over the room."""
    if room <= 0:
        return None
    caps = _Caps(tempo, onsets[-1], replace(rules, max_seconds=min(rules.max_seconds, room)))
    s, e = caps.window(*c.span, onsets)
    inside = _between(onsets, s, e)
    if not caps.within(s, e) or len(inside) < rules.min_onsets or caps.measures(s, e) < rules.min_measures:
        return None
    return _Solo(inside[0], inside[-1], caps.measures(s, e), len(inside), (s, e))


def stem_confirm(tempo: TempoMap, pad_seconds: float, frame_seconds: float, vocals_db: Sequence[float],
                 lead_db: Sequence[float] | None = None, *, quiet_db: float = 30.0, max_vocal_share: float = 0.25,
                 lead_percentile: float = 75.0, min_lead_share: float = 0.5) -> Callable[[int, int], bool]:
    """A solo test from stem loudness, for place_solos (DESIGN.md 2.10: the vocals stem below its P95 - 30 dB while
    the guitar stem is at or above its P75; the thresholds were never tuned, and the solo evaluation ran them on the
    six references and the test song).

    vocals_db, lead_db: one level per frame of frame_seconds from the input audio's start (e.g. 100 ms RMS in dB).
    A section [start, end) passes when at most max_vocal_share of its frames have the vocals within quiet_db of
    their P95 and, with lead_db, at least min_lead_share of its frames have the lead at or above its percentile.
    """
    vocals = np.asarray(vocals_db, dtype=np.float64)
    lead = None if lead_db is None else np.asarray(lead_db, dtype=np.float64)
    v_floor = np.percentile(vocals, 95) - quiet_db
    l_floor = None if lead is None else np.percentile(lead, lead_percentile)

    def frames(tick: int) -> int:
        return max(0, int(round((tempo.tick_to_sec(tick) - pad_seconds) / frame_seconds)))

    def confirm(start: int, end: int) -> bool:
        i, j = frames(start), frames(end)
        v = vocals[i:j]
        if not len(v) or np.mean(v > v_floor) > max_vocal_share:
            return False
        if lead is None:
            return True
        g = lead[i:j]
        return bool(len(g)) and np.mean(g >= l_floor) >= min_lead_share

    return confirm


# ------------------------------------------------------------------------------------------------ levels

def fit_phrases(track: Track, tempo: TempoMap, *, source: Track | None = None,
                fill_rules: FillRules = FILL_RULES) -> Track:
    """The track with the phrases and solos of `source` (its own by default) fitted to its own notes (the module
    docstring's lower-difficulty rules). Other phrase kinds (rolls) are copied as they are."""
    src = source or track
    res = tempo.resolution
    onsets = _onsets(track)
    ends = []
    for f in _kind(src, DRUM_ACTIVATION) if track.is_drums else []:
        inside = onsets[bisect.bisect_left(onsets, f.tick):bisect.bisect_right(onsets, f.tick + f.length)]
        if inside:
            ends.append((f.tick, inside[-1]))
    fills = [Phrase(a, t - a, DRUM_ACTIVATION) for a, t in ends if t - a >= fill_rules.min_level_beats * res - 1e-9]
    if not fills and ends and _kind(src, STAR_POWER):
        fills = [Phrase(a, t - a, DRUM_ACTIVATION) for a, t in ends]  # short fills beat noDrumActivationLanes
    src_sp = _kind(src, STAR_POWER)
    sp: list[Phrase] = []
    for i, p in enumerate(src_sp):
        a, b = p.tick, p.tick + max(p.length, 1)
        if _between(onsets, a, b):
            sp.append(p)
            continue
        lo = sp[-1].tick + sp[-1].length if sp else -1
        hi = src_sp[i + 1].tick if i + 1 < len(src_sp) else None
        near = [t for t in _between(onsets, a - res, b + res + 1) if t > lo - 1 and (hi is None or t < hi)]
        for t in sorted(near, key=lambda t: (a - t if t < a else t - b + 1, t)):
            s, e = (t, b) if t < a else (a, t + 1)
            if (s >= lo and (hi is None or e <= hi)
                    and all(_clear(s, e, f, tempo, fill_rules) for f in fills)):
                sp.append(Phrase(s, e - s, STAR_POWER))
                break
    other = [p for p in src.phrases if p.kind not in (STAR_POWER, DRUM_ACTIVATION)]
    solos = [(a, b) for a, b in src.solos if bisect.bisect_right(onsets, b) > bisect.bisect_left(onsets, a)]
    phrases = sorted(sp + fills + other, key=lambda p: (p.tick, p.kind))
    return Track(track.difficulty, track.instrument, list(track.notes), phrases, solos)


def place_phrases(chart: Chart, *, solos: bool = False, confirm_solo: Callable[[int, int], bool] | None = None,
                  solo_names: Sequence[str] | None = None,
                  bonus: dict[str, Bonus] | None = None, sp_rules: StarPowerRules = SP_RULES,
                  fill_rules: FillRules = FILL_RULES, solo_rules: SoloRules = SOLO_RULES,
                  solo_record: dict | None = None, sp_record: dict | None = None) -> Chart:
    """The chart with new star power on every Expert track, fills on Expert drums and (if `solos`) solos on Expert
    lead guitar, replacing any the tracks had; lower tracks already there get them fitted.

    solos:        place solos on the sections named as solos that confirm_solo accepts (all of them without it).
                  Off by default: no signal for them is reliable (see place_solos); the pipeline asks for them.
    solo_names:   with solos, exactly the sections of these names (see place_solos).
    solo_record:  with solos, filled as place_solos' record for Expert lead guitar.
    sp_record:    filled per instrument with place_star_power's record of its Expert track, and "placed": the
                  phrases it got (drums may get fewer, or none).
    bonus:        per instrument ("Single", "DoubleBass", "Drums", ...), extra score for a phrase [start, end).
    Run it before reduce_chart, which copies Expert's phrases down and keeps a note in each, then `fit_chart`.
    """
    starts = [t for t, _ in chart.sections]
    tracks = {id(t): t for t in chart.tracks}
    for ex in chart.tracks:
        if ex.difficulty != "Expert":
            continue
        b = (bonus or {}).get(ex.instrument)
        rec: dict = {}
        if ex.is_drums:
            sp, fills = schedule_drums(ex, chart.tempo, starts, bonus=b, sp_rules=sp_rules, fill_rules=fill_rules,
                                       sp_record=rec)
            solo = list(ex.solos)
        else:
            sp, fills = place_star_power(ex, chart.tempo, starts, bonus=b, rules=sp_rules, record=rec), []
            solo = place_solos(ex, chart.tempo, chart.sections, confirm=confirm_solo, names=solo_names,
                               rules=solo_rules, record=solo_record) \
                if solos and ex.instrument == "Single" else []
        if sp_record is not None:
            sp_record[ex.instrument] = {**rec, "placed": len(sp)}
        other = [p for p in ex.phrases if p.kind not in (STAR_POWER, DRUM_ACTIVATION)]
        new = Track(ex.difficulty, ex.instrument, list(ex.notes),
                    sorted(sp + fills + other, key=lambda p: (p.tick, p.kind)), solo)
        tracks[id(ex)] = new
        for t in chart.tracks:
            if t.instrument == ex.instrument and t.difficulty != "Expert":
                tracks[id(t)] = fit_phrases(t, chart.tempo, source=new, fill_rules=fill_rules)
    return Chart(chart.info, chart.tempo, list(chart.sections), [tracks[id(t)] for t in chart.tracks])


def fit_chart(chart: Chart, *, fill_rules: FillRules = FILL_RULES) -> Chart:
    """The chart with every track's phrases fitted to its own notes, from its instrument's Expert track where there
    is one (run it after reduce_chart)."""
    experts = {t.instrument: t for t in chart.tracks if t.difficulty == "Expert"}
    tracks = [fit_phrases(t, chart.tempo, source=experts.get(t.instrument), fill_rules=fill_rules)
              for t in chart.tracks]
    return Chart(chart.info, chart.tempo, list(chart.sections), tracks)


# ------------------------------------------------------------------------------------------------ checks

def fill_crash_share(track: Track, tempo: TempoMap) -> float | None:
    """The share of a drum track's fills whose activation note holds a crash (`_Fills._crash`); None without fills.
    Only Expert's is checked: the reductions thin the cymbals, and the crash test counts a cymbal's neighbours."""
    fills = _kind(track, DRUM_ACTIVATION)
    if not fills:
        return None
    ctx = _Fills(track, tempo, FILL_RULES)
    return sum(f.tick + f.length in ctx.groups and ctx._crash_at(f.tick + f.length) for f in fills) / len(fills)


def check_phrases(tracks: Sequence[Track], tempo: TempoMap, *, fill_rules: FillRules = FILL_RULES) -> list[Issue]:
    """Problems with the phrases of one instrument's tracks (any difficulties). Errors are scan-chart chart issues or
    break our rules; warnings flag weaker placement."""
    issues: list[Issue] = []
    for tr in tracks:
        level = tr.difficulty
        on = _onsets(tr)
        long = _long(on, tempo)
        sp = _kind(tr, STAR_POWER)
        fills = _kind(tr, DRUM_ACTIVATION)
        for p in sp:
            if not _between(on, p.tick, p.tick + max(p.length, 1)):
                issues.append(Issue(level, "emptyStarPower", f"{tr.name}: a star-power phrase with no notes", p.tick))
        for p, q in zip(sp, sp[1:]):
            if q.tick < p.tick + p.length:
                issues.append(Issue(level, "starPowerOverlap", f"{tr.name}: overlapping star-power phrases", q.tick))
        if not sp and not tr.is_drums and long:
            issues.append(Issue(level, "noStarPower", f"{tr.name}: no star power"))
        for a, b in tr.solos:
            if bisect.bisect_right(on, b) == bisect.bisect_left(on, a):
                issues.append(Issue(level, "emptySoloSection", f"{tr.name}: a solo with no notes", a))
        if not tr.is_drums:
            continue
        if sp and not fills and long:
            issues.append(Issue(level, "noDrumActivationLanes", f"{tr.name}: star power but no activation lanes"))
        ons = set(on)
        for f in fills:
            end = f.tick + f.length
            if end not in ons:
                issues.append(Issue(level, "fillEnd", f"{tr.name}: an activation lane not ending on a note", f.tick))
            for p in sp:
                if p.tick <= end and f.tick < p.tick + max(p.length, 1):
                    issues.append(Issue(level, "fillOverlapsStarPower",
                                        f"{tr.name}: an activation lane overlapping star power", f.tick))
                elif not _clear(p.tick, p.tick + p.length, f, tempo, fill_rules):
                    issues.append(Issue(level, "fillNearStarPower",
                                        f"{tr.name}: an activation lane next to star power", f.tick, error=False))
        for f, g in zip(fills, fills[1:]):
            if g.tick <= f.tick + f.length:
                issues.append(Issue(level, "fillOverlap", f"{tr.name}: overlapping activation lanes", g.tick))
        share = fill_crash_share(tr, tempo) if level == "Expert" else None
        if share is not None and share < fill_rules.min_crash_share:
            issues.append(Issue(level, "fillNoCrash", f"{tr.name}: {share:.2f} of the activation lanes end on a crash "
                                "(check the source's cymbal labels)", error=False))
        k = max(fill_rules.phrases_before, 1)
        for p, q in zip(sp[k - 1:], sp[k:]):
            end = p.tick + p.length
            if not any(end < f.tick + f.length < q.tick for f in fills):
                issues.append(Issue(level, "noFillBeforeStarPower",
                                    f"{tr.name}: no activation lane between two star-power phrases", end,
                                    error=False))
    return issues
