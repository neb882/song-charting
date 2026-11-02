"""Difficulty reductions: Hard, Medium and Easy built from Expert, for 5-fret parts and for pro drums.

Each level is built from the one above it (Expert -> Hard -> Medium -> Easy), so every onset of a level is an onset
of each level above. The work is done in ticks of the song's own TempoMap, after quantizing: the rules need each
note's metric position (measure line, beat, 8th, 16th), which only the quantized chart has. The rules re-implement
the ideas of Onyx and of the Rock Band Network (RBN) authoring guide (no code copied), with targets measured on 63
Harmonix charts (DESIGN.md 2.11 and its critique, which wins where they differ). Everything is rule-based and
deterministic.

Shared machinery:
  * Metric strength of a tick: downbeat, half-measure line, beat, 8th, 16th or 8th triplet, finer.
  * Tempo: thresholds quoted in BPM ("at 140 BPM or more") and the time floors use the song's median beat, or the
    local measure's where the tempo really changes (more than 15 % away), so a drifting map never flips a rule
    from beat to beat.
  * The thinning ladder. After the spacing rules, while a level keeps more than its ceiling share of the Expert
    onsets (or no fewer onsets than the level above), whole position classes are dropped across the song, finest
    first: finer than 16ths; the 16th after each 8th (and the third 8th triplet); the 16th before it (and the
    middle triplet); the measure's last 8th; the first half's last 8th; the other 8ths; the measure's last beat; the
    first half's last beat; the other beats; the half-measure line. RBN's rule for continuous 8ths on Hard is this
    order (drop the measure's last 8th; at speed, every fourth 8th per half measure), and a 16th run passes through
    a gallop (16th-16th-8th) before it becomes 8ths. Only a "sandwiched" onset goes: one with kept neighbours on
    both sides within one step of its grid (or of the level's own shortest gap, if longer), so syncopations and
    pickups survive. A class is applied when it moves the share toward the target, and regardless of the target
    while the level is not reduced yet or is above its limit. It is never applied below the floor share, unless the
    level still keeps half the onsets of the level above (a dense Expert can leave a thin level legitimately).
  * Coverage: every star-power phrase (and on 5-fret every solo) keeps at least one note on every level. If a phrase
    lost all of them, its strongest upper-level onset comes back and whatever crowds it goes.

5-fret (guitar, bass):
  1. Rhythm. Greedy keep in priority order (DESIGN 2.11: +4 sustained, +2 measure line, +1 on the level grid of
     0.5 / 1 / 2 beats; then metric strength, then earlier), rejecting an onset closer to a kept one than the level's
     minimum gap. The gap is the finest of the level's grid steps that lasts at least a time floor at the song's
     tempo (Hard 1/16, 1/12, 1/8 or 1/4 note with 160 ms; Medium 1/8, 1/4, 1/2 with 300 ms; Easy 1/4, 1/2, 1/1 with
     500 ms; the floors are about the shortest Harmonix gaps per level). At 142 BPM that is 1/8, 1/4 and 1/2 notes.
     Then the ladder, with these shares of Expert onsets (target, ceiling, floor, limit): Hard 0.78 / 0.80 / 0.55 /
     0.90 (the critique's 0.75-0.8; Harmonix 0.75; a Hard at 0.9 or more is an error in `check_reductions`), Medium
     0.50 / 0.58 / 0.33 / 0.65, Easy 0.30 / 0.36 / 0.20 / 0.49 (Harmonix 0.47 and 0.28; limits: DESIGN's bands). A
     note whose sustain survives on the level (trimmed against the next upper onset) is never thinned by the ladder.
  2. Lanes, contour-preserving. Hard keeps all five lanes, Medium uses G R Y B and Easy G R Y. Every onset's low lane
     is chosen by one Viterbi pass over the part: each note stays near its Expert lane scaled onto the level's lanes
     (x 3/4 on Medium, x 1/2 on Easy, which reproduces the Harmonix lane maps), the direction of movement from the
     previous note is kept (a lost step costs 3, a reversed one 6; a quarter as much across a gap of more than two
     beats), and a fast jump (Hard: more than 3 lanes within a beat; Medium and Easy: more than 2 within two beats)
     costs 2 per extra lane. Ties go to the lane nearer the Expert lane. Open notes become green below Expert.
  3. Chords, fitted to the chosen lane (lanes first, then the chord, then a final check: the critique's order). Hard:
     a 3-note chord keeps its outer notes, and a chord holding G and O becomes G+B (span 3). Medium: two notes at most
     two lanes apart (GR, RY, YB, GY, RB; never G+B). Easy: single notes only.
  4. Sustains keep the upper level's length, trimmed to end a gap before the next kept onset (Hard max(1/16 note,
     85 ms), Medium 1/8, Easy 1/4 note) and dropped when shorter than max(200 ms, 3/4 beat) on Hard, 1 beat on
     Medium, 1 1/4 beats on Easy (2 beats on Easy bass): the Harmonix p5 shortest sustains. Never extended.
  5. HOPOs and taps: lower levels strum more. No taps below Expert. Medium and Easy strum everything (natural HOPOs
     are force-strummed with the flip modifier). On Hard a note stays a HOPO only when it is a natural HOPO on the
     Hard notes, Expert plays it as a HOPO or tap, and the Hard note before it is the Expert note before it (the same
     legato pair). Every other natural HOPO is force-strummed; no HOPO is ever forced on (Harmonix Hard: 1.7 % HOPOs).

Drums (4-lane pro), per level:
  1. Kit. No 2x kick below Expert. A cymbal and a tom on one pad (which a .chart cannot hold) keep the cymbal; the
     tom moves to the nearest free tom pad or goes. From Hard down every crash is on green: a blue cymbal with fewer
     than 3 other blue cymbals within two beats on Expert is a crash, not a ride (DESIGN 2.9 puts a ride on blue only
     in a regular run; yellow is the hi-hat). Two cymbals on one hit become one (the crash). From Medium down two
     toms become one. Never more than two hand gems.
  2. Fills (activation lanes): below Expert no kicks inside a fill, except on its last note, the activation note.
  3. Kicks: at least 1 beat apart on Hard and 2 beats on Medium and Easy (4 beats at 170 BPM or more, RBN's one kick
     per measure); from 100 BPM Medium and Easy kicks stay on beats (RBN); on Hard and Medium no kick under an
     off-beat crash. Priority: metric strength, then a kick under a crash, then earlier.
  4. Hands (every pad but the kick, as one stream): kept hits at least 1/2 beat apart on Hard (no 16th patterns or
     rolls; RBN avoids them at 140 BPM or more) and 1 beat on Easy, except that at 120 BPM or less a hit of only
     hi-hat or ride may sit 1/2 beat from another (Harmonix Easy keeps the off-beat ride there; snares stay a beat
     apart). On Medium at 140 BPM or more a hit with the hi-hat or ride, or outside activation lanes with a tom or
     crash, keeps 1 beat from its neighbours (RBN: no right-hand 8ths, no kicks or snares between them; the right
     hand may be on a tom or crash), and other hand hits (snares, fills) 1/2 beat. Priority: metric strength, then
     snare or crash, then not a ghost note.
  5. Limbs: Hard has no three-limb hit (a kick with two hand gems loses its least important hand: hi-hat or ride,
     then tom, then snare, then crash). On Medium a kick stays only with at most one hand gem.
  6. Easy (DESIGN 2.11): a kick is never paired with a pad, and each section is either a kick/snare beat (quiet
     sections: no hi-hat or ride, a kick under a hand gem goes) or a two-hand beat (loud sections: no kicks). A
     section is loud when its loudness (e.g. the drum stem's RMS, from the caller) is at least the song's median;
     without loudness, Expert hits per beat stand in for it. A two-hand Easy hit always includes the snare: the snare
     plus at most one other hand.
     Then any two kept hits are at least 1/16 note apart on Hard and 1/8 on Medium and Easy (the Harmonix shortest
     gaps), the weaker one going: a kick a 16th-triplet off a hand hit is not Hard.
  7. The ladder (Hard 0.85 / 0.87 / 0.62, Medium 0.61 / 0.70 / 0.39, Easy 0.50 / 0.55 / 0.30 of Expert hits; the
     Harmonix and human test-song ladders are 0.81-0.85 / 0.61-0.65 / 0.50-0.53) drops only weak hits: hi-hat, ride
     and ghost gems, and from Medium down lone kicks.
  8. Coverage: every star-power phrase keeps a hit, and every fill keeps its activation note, on every level (on
     Easy in the section's mode, else in the other one: a phrase of kicks alone in a two-hand section keeps a kick).
  Cymbal and tom flags, accents and ghosts are kept wherever the pad is kept.

`check_reductions` re-checks a finished ladder against Clone Hero's limits (scan-chart: difficultyForbiddenNote,
emptyStarPower, babySustain, badSustainGap, difficultyNotReduced) and the rules above.
"""
from __future__ import annotations

import bisect
import math
from dataclasses import dataclass
from statistics import median
from typing import Callable, Sequence

from .chart import DRUM_ACTIVATION, OPEN, STAR_POWER, Chart, DrumHit, FretNote, Track
from .tempo import TempoMap

LEVELS = ("Hard", "Medium", "Easy")
SUSTAIN_MIN_S = 0.200      # Encore's shortest sustain
SUSTAIN_GAP_MIN_S = 0.040  # scan-chart's badSustainGap; Encore asks for 60 ms
BABY_SUSTAIN_S = 0.100     # scan-chart's babySustain


# ------------------------------------------------------------------------------------------------ metric grid

class _Grid:
    """Metric positions on a tempo map: measure lines, metric strength and the song's beat length."""

    def __init__(self, tempo: TempoMap, last_tick: int):
        self.tempo = tempo
        self.res = res = tempo.resolution
        self.starts = tempo.measure_starts(max(last_tick, 0) + 1)
        self.lengths = [tempo.measure_length(tempo.time_signature_at(m)) for m in self.starts]
        self._beat = [(tempo.tick_to_sec(m + n) - tempo.tick_to_sec(m)) * res / n
                      for m, n in zip(self.starts, self.lengths)]
        self.song_beat = median(self._beat)

    def _index(self, tick: int) -> int:
        return max(bisect.bisect_right(self.starts, tick) - 1, 0)

    def measure(self, tick: int) -> tuple[int, int]:
        """(offset of the tick in its measure, the measure's length), in ticks."""
        i = self._index(tick)
        return tick - self.starts[i], self.lengths[i]

    def beat_s(self, tick: int) -> float:
        """Seconds per beat: the song's median, or the measure's own where the tempo really changes."""
        local = self._beat[self._index(tick)]
        return self.song_beat if abs(local / self.song_beat - 1) <= 0.15 else local

    def bpm(self, tick: int) -> float:
        return 60 / self.beat_s(tick)

    def strength(self, tick: int) -> int:
        """0 downbeat, 1 half-measure line, 2 beat, 3 8th, 4 16th or 8th triplet, 5 finer."""
        o, mlen = self.measure(tick)
        res = self.res
        if o == 0:
            return 0
        if 2 * o == mlen and mlen % (2 * res) == 0:
            return 1
        if o % res == 0:
            return 2
        if 2 * o % res == 0:
            return 3
        if 4 * o % res == 0 or 3 * o % res == 0:
            return 4
        return 5

    def thin_class(self, tick: int) -> int | None:
        """The ladder stage (0-9, see the module docstring) that may thin this position; None on a downbeat."""
        o, mlen = self.measure(tick)
        res, s = self.res, self.strength(tick)
        half = mlen // 2 if mlen % (2 * res) == 0 else None
        if s == 5:
            return 0
        if s == 4:  # the 16th after the 8th (and the last triplet) before the 16th before it (and the middle one)
            return 1 if 4 * (o % res) == 3 * res or 3 * (o % res) == 2 * res else 2
        if s == 3:
            return 3 if o == mlen - res // 2 else 4 if half and o == half - res // 2 else 5
        if s == 2:
            return 6 if o == mlen - res else 7 if half and o == half - res else 8
        if s == 1:
            return 9
        return None

    def thin_span(self, cls: int, tick: int) -> int:
        """How close both kept neighbours must be for an onset of this class to count as sandwiched."""
        if cls <= 2:
            return self.res // 2
        if cls <= 5:
            return self.res
        if cls <= 8:
            return 2 * self.res
        return self.measure(tick)[1] // 2

    def step(self, tick: int, steps: Sequence[float], floor_s: float) -> int:
        """The finest of `steps` (beats) that lasts at least floor_s here, in ticks."""
        beat = self.beat_s(tick)
        s = next((s for s in steps if s * beat >= floor_s - 1e-9), steps[-1])
        return round(s * self.res)

    def ticks_before(self, tick: int, seconds: float) -> int:
        """The latest tick at least `seconds` before `tick`."""
        return math.floor(self.tempo.sec_to_tick(self.tempo.tick_to_sec(tick) - seconds) + 1e-6)

    def ticks_after(self, tick: int, seconds: float) -> int:
        """The first tick at least `seconds` after `tick`."""
        return math.ceil(self.tempo.sec_to_tick(self.tempo.tick_to_sec(tick) + seconds) - 1e-6)


def _greedy(ticks, key, conflict: Callable[[int, int], bool]) -> list[int]:
    """Keep ticks in `key` order, skipping any that conflicts with an already kept neighbour. conflict(a, b), a < b."""
    kept: list[int] = []
    for t in sorted(ticks, key=key):
        i = bisect.bisect_left(kept, t)
        if i > 0 and conflict(kept[i - 1], t):
            continue
        if i < len(kept) and conflict(t, kept[i]):
            continue
        kept.insert(i, t)
    return kept


@dataclass(frozen=True)
class _Ladder:
    target: float    # share of Expert onsets the thinning aims at
    ceiling: float   # it runs while the share is above this
    floor: float     # and never takes a class that would go below this and below half the level above
    limit: float     # above this share any class that stays above the floor is taken


def _thin(kept: list[int], grid: _Grid, n_expert: int, n_upper: int, ladder: _Ladder,
          can_drop: Callable[[int], bool], gap: Callable[[int], int]) -> list[int]:
    """The thinning ladder: drop sandwiched onsets one position class at a time, across the whole part.
    gap(t): the level's own shortest gap at t; neighbours that close always count as sandwiching."""
    for cls in range(10):
        share = len(kept) / n_expert
        reduced = len(kept) < n_upper
        if share <= ladder.ceiling and reduced:
            break
        trial = list(kept)
        j = 0
        while j < len(trial):  # in time order, so of three sandwiched triplets only the middle one goes
            t = trial[j]
            if 0 < j < len(trial) - 1 and grid.thin_class(t) == cls and can_drop(t):
                span = max(grid.thin_span(cls, t), gap(t))
                if t - trial[j - 1] <= span and trial[j + 1] - t <= span:
                    del trial[j]
                    continue
            j += 1
        if len(trial) == len(kept):
            continue
        after = len(trial) / n_expert
        if after < ladder.floor and len(trial) < n_upper / 2:  # a dense Expert may leave a thin level legitimately
            break
        if not reduced or share > ladder.limit or abs(after - ladder.target) < abs(share - ladder.target):
            kept = trial
        else:
            break
    return kept


def _spans(track: Track, kind: int, solos: bool = False) -> list[tuple[int, int]]:
    """Half-open tick ranges: phrases of `kind` (as scan-chart reads them) and, if asked, solos (end inclusive)."""
    out = [(p.tick, p.tick + max(p.length, 1)) for p in track.phrases if p.kind == kind]
    if solos:
        out += [(a, b + 1) for a, b in track.solos]
    return sorted(out)


# ------------------------------------------------------------------------------------------------ 5-fret

@dataclass(frozen=True)
class _FretRules:
    lanes: int                  # 5, 4 or 3
    steps: tuple[float, ...]    # minimum-gap candidates, beats, finest first
    floor_s: float              # the gap is the finest step lasting at least this
    grid: float                 # the level grid of the priority, beats
    ladder: _Ladder
    sus_gap: float              # beats between a sustain's end and the next onset
    sus_gap_s: float
    sus_min: float              # shortest sustain, beats (and at least SUSTAIN_MIN_S)
    max_jump: int               # lanes
    jump_window: float          # beats


_FRET_RULES = {
    "Hard": _FretRules(5, (0.25, 1 / 3, 0.5, 1.0), 0.160, 0.5, _Ladder(0.78, 0.80, 0.55, 0.90),
                       0.25, 0.085, 0.75, 3, 1.0),
    "Medium": _FretRules(4, (0.5, 1.0, 2.0), 0.300, 1.0, _Ladder(0.50, 0.58, 0.33, 0.65), 0.5, 0.0, 1.0, 2, 2.0),
    "Easy": _FretRules(3, (1.0, 2.0, 4.0), 0.500, 2.0, _Ladder(0.30, 0.36, 0.20, 0.49), 1.0, 0.0, 1.25, 2, 2.0),
}
_BASS_EASY_SUS_MIN = 2.0  # Harmonix Easy bass: shortest sustains 2 beats

# lane-fitting costs (see the module docstring)
_W_FLAT, _W_REVERSE, _W_JUMP, _W_NEAR = 3.0, 6.0, 2.0, 0.01


def hopo_threshold(resolution: int) -> int:
    """The natural HOPO threshold of a .chart: floor(65/192 x resolution) ticks."""
    return math.floor(65 / 192 * resolution)


def _fret_groups(notes) -> dict[int, FretNote]:
    """One FretNote per tick (a chord's frets merged, its longest sustain, flags or-ed)."""
    out: dict[int, FretNote] = {}
    for n in sorted(notes, key=lambda n: n.tick):
        frets = tuple(sorted(set(n.frets)))
        if n.tick in out:
            o = out[n.tick]
            merged = tuple(sorted(set(o.frets) | set(frets)))
            if OPEN in merged and len(merged) > 1:
                merged = tuple(f for f in merged if f != OPEN)
            out[n.tick] = FretNote(n.tick, merged, max(o.length, n.length), o.flip or n.flip, o.tap or n.tap)
        else:
            out[n.tick] = FretNote(n.tick, frets, n.length, n.flip, n.tap)
    return out


def _natural(prev: tuple[int, ...] | None, frets: tuple[int, ...], gap: int, threshold: int) -> bool:
    """A .chart natural HOPO: a single fret, not the same single fret again, at most `threshold` ticks after."""
    return prev is not None and gap <= threshold and len(frets) == 1 and len(set(frets) | set(prev)) > 1


def hopo_states(notes, resolution: int) -> dict[int, bool]:
    """How Clone Hero plays each onset of a .chart part: True for a HOPO or a tap, False for a strum."""
    groups = _fret_groups(notes)
    threshold = hopo_threshold(resolution)
    out, prev, last = {}, None, 0
    for t in sorted(groups):
        n = groups[t]
        out[t] = n.tap or (_natural(prev, n.frets, t - last, threshold) != n.flip)
        prev, last = n.frets, t
    return out


def _shape(frets: tuple[int, ...], level: str) -> tuple[int, ...]:
    """The chord shape a level allows, as lane offsets from its lowest note."""
    if len(frets) == 1 or level == "Easy" or OPEN in frets:
        return (0,)
    span = frets[-1] - frets[0]
    return (0, min(span, 3 if level == "Hard" else 2))  # Hard: outer notes, G+O -> G+B; Medium: GR RY YB GY RB


def _fit_lanes(items: list[tuple[int, int, int, bool]], rules: _FretRules, res: int) -> list[int]:
    """The low lane of each onset, by Viterbi. items: (tick, Expert low lane, chord span, forced to green)."""
    if not items:
        return []
    L = rules.lanes
    scale = (L - 1) / 4

    def states(span, forced):
        return [0] if forced else list(range(L - span))

    def unary(n, anchor):
        return abs(n - scale * anchor) + _W_NEAR * abs(n - anchor)

    all_states = [states(span, forced) for _, _, span, forced in items]
    cost = [unary(n, items[0][1]) for n in all_states[0]]
    backs: list[list[int]] = []
    for i in range(1, len(items)):
        (t0, a0, s0, _), (t1, a1, s1, _) = items[i - 1], items[i]
        gap = (t1 - t0) / res
        w = 1.0 if gap <= 2 else 0.25
        want = (a1 > a0) - (a1 < a0)
        new_cost, back = [], []
        for n in all_states[i]:
            best, arg = math.inf, 0
            for j, m in enumerate(all_states[i - 1]):
                got = (n > m) - (n < m)
                c = cost[j]
                if got != want:
                    c += w * (_W_FLAT if got == 0 or want == 0 else _W_REVERSE)
                if gap < rules.jump_window:
                    jump = max(0, n - (m + s0), m - (n + s1))  # distance between the two hand positions
                    if jump > rules.max_jump:
                        c += _W_JUMP * (jump - rules.max_jump)
                if c < best - 1e-12:
                    best, arg = c, j
            new_cost.append(best + unary(n, a1))
            back.append(arg)
        backs.append(back)
        cost = new_cost
    j = _argmin(cost)
    lanes = [0] * len(items)
    for i in range(len(items) - 1, -1, -1):
        lanes[i] = all_states[i][j]
        if i:
            j = backs[i - 1][j]
    return lanes


def _argmin(values: list[float]) -> int:
    best, arg = math.inf, 0
    for i, v in enumerate(values):
        if v < best - 1e-12:
            best, arg = v, i
    return arg


def _fret_legal(frets: tuple[int, ...], level: str) -> bool:
    s = set(frets)
    if OPEN in s or len(s) > {"Hard": 2, "Medium": 2, "Easy": 1}[level]:
        return False
    if level == "Hard":
        return not {0, 4} <= s
    if level == "Medium":
        return 4 not in s and not {0, 3} <= s
    return not s & {3, 4}


def _reduce_frets(upper: Track, level: str, tempo: TempoMap, expert: Track) -> Track:
    rules = _FRET_RULES[level]
    sus_min = _BASS_EASY_SUS_MIN if level == "Easy" and upper.instrument == "DoubleBass" else rules.sus_min
    up = _fret_groups(upper.notes)
    ex = _fret_groups(expert.notes)
    res = tempo.resolution
    ticks = sorted(up)
    out = Track(level, upper.instrument, [], list(upper.phrases), list(upper.solos))
    if not ticks:
        return out
    spans = _spans(upper, STAR_POWER, solos=True)
    grid = _Grid(tempo, max([ticks[-1]] + [b for _, b in spans]))
    level_grid = round(rules.grid * res)

    def sustain(t: int, nxt: int | None) -> int:
        """The upper sustain at t on this level, trimmed before the onset at nxt (0 if it gets too short)."""
        n = up[t].length
        if n and nxt is not None:
            end = min(nxt - round(rules.sus_gap * res), grid.ticks_before(nxt, rules.sus_gap_s))
            n = min(n, end - t)
        shortest = max(round(sus_min * res), grid.ticks_after(t, SUSTAIN_MIN_S) - t)
        return n if n >= shortest else 0

    # 1. rhythm. "Sustained" means the sustain survives here even against the next upper onset.
    step = {t: grid.step(t, rules.steps, rules.floor_s) for t in ticks}
    held = {t: sustain(t, ticks[i + 1] if i + 1 < len(ticks) else None) > 0 for i, t in enumerate(ticks)}

    def key(t):
        o = grid.measure(t)[0]
        score = 4 * held[t] + 2 * (o == 0) + (o % level_grid == 0)
        return -score, grid.strength(t), t

    def conflict(a, b):
        return b - a < step[a]

    kept = _greedy(ticks, key, conflict)
    n_upper = len(up) if upper.difficulty != level else math.inf  # a level re-reduced from itself has no level above
    kept = _thin(kept, grid, len(ex), n_upper, rules.ladder, lambda t: not held[t], step.get)
    kept = _cover(kept, ticks, spans, key, conflict)

    # 2-3. lanes, then chords fitted to them
    shapes = {t: _shape(up[t].frets, level) for t in kept}
    source = {t: ex.get(t, up[t]).frets for t in kept}  # the Expert frets of each onset
    items = [(t, 0 if OPEN in source[t] else source[t][0], shapes[t][-1], OPEN in source[t] or OPEN in up[t].frets)
             for t in kept]
    lanes = _fit_lanes(items, rules, res)
    frets = {}
    for t, low in zip(kept, lanes):
        f = tuple(low + s for s in shapes[t])
        while not _fret_legal(f, level):  # cannot happen by construction; the last guard before writing
            f = f[:-1] if len(f) > 1 else (min(f[0], rules.lanes - 1),)
        frets[t] = f

    # 4. sustains
    length = {t: sustain(t, kept[i + 1] if i + 1 < len(kept) else None) for i, t in enumerate(kept)}

    # 5. HOPOs: lower levels strum more
    ex_ticks = sorted(ex)
    ex_hopo = hopo_states(expert.notes, res)
    threshold = hopo_threshold(res)
    notes, prev = [], None
    for i, t in enumerate(kept):
        natural = _natural(frets[prev] if prev is not None else None, frets[t], t - (prev or 0), threshold)
        want = False
        if level == "Hard" and natural and ex_hopo.get(t, False):
            k = bisect.bisect_left(ex_ticks, t)
            want = k > 0 and ex_ticks[k - 1] == prev
        notes.append(FretNote(t, frets[t], length[t], flip=natural != want))
        prev = t
    out.notes = notes
    return out


def _cover(kept: list[int], ticks: list[int], spans: list[tuple[int, int]], key, conflict) -> list[int]:
    """Every span holding upper-level onsets keeps one: its strongest onset comes back and crowding ones go."""
    kept = list(kept)
    protected: set[int] = set()
    for a, b in spans:
        inside = kept[bisect.bisect_left(kept, a):bisect.bisect_left(kept, b)]
        if inside:
            protected.add(min(inside, key=key))
            continue
        cands = sorted(ticks[bisect.bisect_left(ticks, a):bisect.bisect_left(ticks, b)], key=key)
        if not cands:
            continue

        def clash(t, k):
            return t != k and conflict(min(t, k), max(t, k))

        pick = next((t for t in cands if not any(clash(t, p) for p in protected)), cands[0])
        kept = [k for k in kept if k in protected or not clash(pick, k)]
        bisect.insort(kept, pick)
        protected.add(pick)
    return kept


# ------------------------------------------------------------------------------------------------ drums

@dataclass(frozen=True)
class _DrumRules:
    kick_pad: float          # beats between kept kicks
    hand_pad: float          # beats between kept hand hits
    keeper_pad: float        # beats around a right-hand hit (rule 4), at FAST_BPM or more
    onset_gap: float         # beats between any two kept hits (Harmonix shortest gaps: 1/16, 1/8, 1/8 note)
    ladder: _Ladder


_DRUM_RULES = {
    "Hard": _DrumRules(1.0, 0.5, 0.5, 0.25, _Ladder(0.85, 0.87, 0.62, 0.95)),
    "Medium": _DrumRules(2.0, 0.5, 1.0, 0.5, _Ladder(0.61, 0.70, 0.39, 0.85)),
    "Easy": _DrumRules(2.0, 1.0, 1.0, 0.5, _Ladder(0.50, 0.55, 0.30, 0.71)),
}
FAST_BPM = 140          # RBN: no right-hand 8ths on Medium, no 16th rolls on Hard
SLOW_BPM = 120          # Harmonix: off-beat hi-hat or ride hits on Easy up to this tempo (half a beat >= 250 ms)
KICKS_ON_BEATS_BPM = 100  # RBN: Medium kicks on quarter notes from 100-110 BPM
ONE_KICK_BPM = 170      # RBN: one kick per measure on Medium
_RIDE_RUN = 3           # a blue cymbal with fewer other blue cymbals within 2 beats is a crash

Group = dict  # pad -> DrumHit, one hit per pad


def _hand_rank(h: DrumHit) -> int:
    """Which hand gem stays when a hit has too many (lower stays): crash, snare, tom, hi-hat or ride."""
    if h.pad == 4 and h.cymbal:
        return 0
    if h.pad == 1:
        return 1
    return 2 if not h.cymbal else 3


def _keeper(h: DrumHit) -> bool:
    """A time-keeping gem: hi-hat or ride (a yellow or blue cymbal once crashes are on green)."""
    return h.cymbal and h.pad in (2, 3)


def _hands(g: Group) -> list[DrumHit]:
    return [h for p, h in g.items() if p]


def _drum_groups(notes) -> dict[int, list[DrumHit]]:
    out: dict[int, list[DrumHit]] = {}
    for h in notes:
        out.setdefault(h.tick, []).append(h)
    return out


def _crashes(expert_notes, res: int) -> set[tuple[int, int]]:
    """(tick, pad) of the Expert blue cymbals that are crashes, not part of a ride pattern."""
    by_pad: dict[int, list[int]] = {3: []}
    for h in expert_notes:
        if h.cymbal and h.pad in by_pad:
            by_pad[h.pad].append(h.tick)
    out = set()
    for pad, ts in by_pad.items():
        ts.sort()
        for t in ts:
            others = bisect.bisect_right(ts, t + 2 * res) - bisect.bisect_left(ts, t - 2 * res) - 1
            if others < _RIDE_RUN:
                out.add((t, pad))
    return out


def _kit(hits: list[DrumHit], level: str, crashes: set[tuple[int, int]]) -> Group:
    """One upper-level hit made legal on this level's kit (rule 1)."""
    hits = [h for h in hits if not h.double_kick]
    g: Group = {}
    toms: list[DrumHit] = []
    for h in sorted(hits, key=lambda h: (h.pad, not h.cymbal, -h.accent, h.ghost)):
        if h.pad not in g:
            g[h.pad] = h
        elif h.pad and not h.cymbal and g[h.pad].cymbal:
            toms.append(h)  # a tom under a cymbal on the same pad
    for h in toms:
        free = next((p for p in sorted((2, 3, 4), key=lambda p: (abs(p - h.pad), p)) if p not in g), None)
        if free is not None:
            g[free] = DrumHit(h.tick, free, False, False, h.accent, h.ghost)
    h = g.get(3)  # crashes go on green
    if h and h.cymbal and (h.tick, 3) in crashes and (4 not in g or g[4].cymbal):
        del g[3]
        if 4 not in g:
            g[4] = DrumHit(h.tick, 4, True, False, h.accent, h.ghost)
    cymbals = [h for h in _hands(g) if h.cymbal]
    for h in sorted(cymbals, key=lambda h: (_hand_rank(h), -h.pad))[1:]:  # one cymbal: the crash, else the ride
        del g[h.pad]
    if level != "Hard":
        toms = [h for h in _hands(g) if not h.cymbal and h.pad != 1]
        for h in sorted(toms, key=lambda h: -h.pad)[1:]:  # one tom: the lowest
            del g[h.pad]
    for h in sorted(_hands(g), key=lambda h: (_hand_rank(h), h.pad))[2:]:  # two hands
        del g[h.pad]
    return g


def _limbs(g: Group, level: str, quiet: bool | None) -> Group:
    """Rules 5 and 6 on one hit. quiet: Easy only, True for a kick/snare section, False for a two-hand one."""
    g = dict(g)
    hands = sorted(_hands(g), key=lambda h: (_hand_rank(h), h.pad))
    if level == "Hard" and 0 in g and len(hands) == 2:
        del g[hands[-1].pad]
    elif level == "Medium" and 0 in g and len(hands) == 2:
        del g[0]
    elif level == "Easy":
        if quiet:
            for h in hands:
                if _keeper(h):
                    del g[h.pad]
        if 0 in g and (not quiet or len(g) > 1):
            del g[0]
        hands = sorted(_hands(g), key=lambda h: (_hand_rank(h), h.pad))
        if len(hands) == 2 and 1 not in g:  # two hands only as the snare plus one
            del g[hands[1].pad]
    return g


def _loud_sections(expert: Track, grid: _Grid, sections: Sequence[int], loudness: Sequence[float] | None,
                   last_tick: int) -> Callable[[int], bool]:
    """Easy rule 6: whether the section holding a tick is loud (a two-hand beat) rather than quiet (kick/snare).
    The first section also covers anything before it; with no sections the song is one loud section."""
    if loudness is not None:
        if len(loudness) != len(sections):
            raise ValueError(f"{len(loudness)} loudness values for {len(sections)} sections")
        pairs = sorted(zip((int(s) for s in sections), loudness))
        starts, values = [s for s, _ in pairs] or [0], [float(v) for _, v in pairs] or [math.nan]
    else:
        starts = sorted({int(s) for s in sections}) or [0]
        ticks = sorted(h.tick for h in expert.notes)
        values = []
        for i, a in enumerate(starts):
            a = a if i else min(a, 0)
            b = starts[i + 1] if i + 1 < len(starts) else last_tick + 1
            n = bisect.bisect_left(ticks, b) - bisect.bisect_left(ticks, a)
            values.append(n / max((b - a) / grid.res, 1.0) if n else math.nan)  # Expert gems per beat
    known = [v for v in values if not math.isnan(v)]
    mid = median(known) if known else 0.0

    def loud(tick: int) -> bool:
        i = max(bisect.bisect_right(starts, tick) - 1, 0)
        return not values[i] < mid  # nan (no drums) counts as loud: no kicks then
    return loud


def _reduce_drums(upper: Track, level: str, tempo: TempoMap, expert: Track, sections: Sequence[int],
                  loudness: Sequence[float] | None) -> Track:
    rules = _DRUM_RULES[level]
    res = tempo.resolution
    out = Track(level, "Drums", [], list(upper.phrases), list(upper.solos))
    up = _drum_groups(upper.notes)
    if not up:
        return out
    up_ticks = sorted(up)
    sp = _spans(upper, STAR_POWER)
    fills = [(p.tick, p.tick + max(p.length, 0)) for p in upper.phrases if p.kind == DRUM_ACTIVATION]
    last = max([up_ticks[-1]] + [b for _, b in sp + fills])
    grid = _Grid(tempo, last)
    bpm = 60 / grid.song_beat
    crashes = _crashes(expert.notes, res) if upper.difficulty == "Expert" else set()
    loud = _loud_sections(expert, grid, sections, loudness, last) if level == "Easy" else None

    # activation notes: the last upper hit of each fill; kicks inside a fill go, except on it
    activation, in_fill = set(), set()
    for a, b in fills:
        inside = up_ticks[bisect.bisect_left(up_ticks, a):bisect.bisect_right(up_ticks, b)]
        if inside:
            activation.add(inside[-1])
            in_fill.update(inside[:-1])

    def quiet(t: int, other: bool = False) -> bool | None:
        return None if loud is None else loud(t) == other

    def legal(t: int, other: bool = False) -> Group:
        """One upper hit through every per-hit rule of this level (kit, fills, the kick position rules, limbs).
        other: on Easy, judge it by the other section mode (the activation note's last resort)."""
        g = _kit(up[t], level, crashes)
        if 0 in g:
            off_beat = grid.strength(t) >= 3
            if (t in in_fill or (level != "Easy" and off_beat and 4 in g and g[4].cymbal)
                    or (level != "Hard" and off_beat and grid.bpm(t) >= KICKS_ON_BEATS_BPM)):
                del g[0]
        return _limbs(g, level, quiet(t, other))

    groups = {t: legal(t) for t in up_ticks}

    # 3. kicks
    kick_pad = round((4.0 if level != "Hard" and bpm >= ONE_KICK_BPM else rules.kick_pad) * res)

    def kick_key(t):
        g = groups[t]
        return grid.strength(t), not (4 in g and g[4].cymbal), t

    kicks = _greedy([t for t, g in groups.items() if 0 in g], kick_key, lambda a, b: b - a < kick_pad)
    kick_set = set(kicks)

    # 4. hands
    def hand_key(t):
        hs = _hands(groups[t])
        strong = any(h.pad == 1 or (h.pad == 4 and h.cymbal) for h in hs)
        return grid.strength(t), not strong, all(h.ghost for h in hs), t

    lanes = in_fill | activation

    def hand_pad(t):
        """Medium at speed: the right hand (hi-hat or ride, or out of fills a tom or crash) keeps 1 beat."""
        if level == "Medium" and grid.bpm(t) >= FAST_BPM and any(
                _keeper(h) or (h.pad != 1 and t not in lanes) for h in _hands(groups[t])):
            return round(rules.keeper_pad * res)
        return round(rules.hand_pad * res)

    def hand_gap(a: int, ga: Group, b: int, gb: Group) -> int:
        """The shortest gap between two hand hits a < b (groups ga, gb): Easy's slow off-beat hi-hat or ride aside,
        the larger of their pads."""
        if (level == "Easy" and any(_hands(g) and all(_keeper(h) for h in _hands(g)) for g in (ga, gb))
                and max(grid.bpm(a), grid.bpm(b)) <= SLOW_BPM + 1e-6):
            return res // 2
        return max(hand_pad(a), hand_pad(b))

    hands = _greedy([t for t, g in groups.items() if _hands(g)], hand_key,
                    lambda a, b: b - a < hand_gap(a, groups[a], b, groups[b]))
    hand_set = set(hands)
    kept: dict[int, Group] = {}
    for t, g in groups.items():  # part of a legal hit is legal
        g = {p: h for p, h in g.items() if (p == 0 and t in kick_set) or (p and t in hand_set)}
        if g:
            kept[t] = g

    # any two hits keep the level's shortest gap
    def hit_key(t):
        g = kept[t]
        strong = 0 in g or 1 in g or (4 in g and g[4].cymbal)
        return grid.strength(t), not strong, t

    onset_gap = round(rules.onset_gap * res)
    kept = {t: kept[t] for t in _greedy(kept, hit_key, lambda a, b: b - a < onset_gap)}

    # 7. the ladder, on weak hits only
    def weak(t):
        return all(_keeper(h) or h.ghost or (p == 0 and level != "Hard") for p, h in kept[t].items())

    n_upper = len(up_ticks) if upper.difficulty != level else math.inf  # re-reduced from itself: no level above
    ticks = _thin(sorted(kept), grid, len(_drum_groups(expert.notes)), n_upper, rules.ladder, weak,
                  lambda t: max(onset_gap, hand_pad(t)))
    kept = {t: kept[t] for t in ticks}

    # 8. coverage: star power keeps a hit, a fill keeps its activation note
    protected: set[int] = set()

    def restore(t: int, other: bool = False) -> bool:
        g = legal(t, other) if other else groups[t]
        if not g:
            return False
        for k in [k for k in kept if k != t and abs(k - t) < onset_gap and k not in protected]:
            del kept[k]
        if 0 in g:
            for k in [k for k in kept if k != t and 0 in kept[k] and abs(k - t) < kick_pad and k not in protected]:
                kept[k] = {p: h for p, h in kept[k].items() if p}
        if _hands(g):
            for k in [k for k in kept if k != t and _hands(kept[k]) and k not in protected
                      and abs(k - t) < (hand_gap(k, kept[k], t, g) if k < t else hand_gap(t, g, k, kept[k]))]:
                kept[k] = {p: h for p, h in kept[k].items() if not p}
        for k in [k for k, v in kept.items() if not v]:
            del kept[k]
        kept[t] = g
        protected.add(t)
        return True

    for t in sorted(activation):
        if t in kept:
            protected.add(t)
            continue
        # the activation note itself (in the section's mode, else the other one), else the fill's latest hit
        earlier = [k for k in up_ticks if k < t and any(a <= k <= b and a <= t <= b for a, b in fills)][::-1]
        tries = [(t, False)] + ([(t, True)] if loud is not None else [])
        tries += [(k, False) for k in earlier] + ([(k, True) for k in earlier] if loud is not None else [])
        found = next((k for k, other in tries if k in kept or restore(k, other)), None)
        if found is not None:
            protected.add(found)
    for a, b in sp:
        inside = [k for k in kept if a <= k < b]
        if inside:
            protected.add(min(inside, key=hand_key))
            continue
        cands = sorted(up_ticks[bisect.bisect_left(up_ticks, a):bisect.bisect_left(up_ticks, b)], key=hand_key)
        tries = [(k, False) for k in cands] + ([(k, True) for k in cands] if loud is not None else [])
        next((k for k, other in tries if restore(k, other)), None)  # Easy: then in the other section mode

    out.notes = [h for t in sorted(kept) for _, h in sorted(kept[t].items())]
    return out


# ------------------------------------------------------------------------------------------------ public

def reduce_level(upper: Track, difficulty: str, tempo: TempoMap, *, expert: Track | None = None,
                 sections: Sequence[int] = (), loudness: Sequence[float] | None = None) -> Track:
    """One level built from the level above it.

    upper:    the level above (Expert for Hard, Hard for Medium, Medium for Easy), quantized on `tempo`.
    expert:   the part's Expert, the reference for onset shares, Expert lanes and HOPOs, and crash detection
              (defaults to `upper`). Given the Expert, reducing a level's own output again returns it unchanged.
    sections, loudness: drums only, for Easy's kick/snare or two-hand choice (rule 6): section start ticks and,
              if known, one loudness value per section (higher = louder, e.g. drum-stem RMS in dB).
    Phrases (star power, fills) and solos are copied from `upper`.
    """
    if difficulty not in LEVELS:
        raise ValueError(f"cannot reduce to {difficulty}")
    expert = expert or upper
    if upper.is_drums:
        return _reduce_drums(upper, difficulty, tempo, expert, sections, loudness)
    return _reduce_frets(upper, difficulty, tempo, expert)


def reduce_track(expert: Track, tempo: TempoMap, *, sections: Sequence[int] = (),
                 loudness: Sequence[float] | None = None) -> list[Track]:
    """[Hard, Medium, Easy] for an Expert 5-fret or drums track, each built from the one above."""
    if expert.difficulty != "Expert":
        raise ValueError(f"reduce_track needs an Expert track, not {expert.name}")
    out, upper = [], expert
    for level in LEVELS:
        upper = reduce_level(upper, level, tempo, expert=expert, sections=sections, loudness=loudness)
        out.append(upper)
    return out


def reduce_chart(chart: Chart, *, drum_loudness: Sequence[float] | None = None) -> Chart:
    """The chart with Hard, Medium and Easy rebuilt from every Expert track (lower tracks already there are replaced).
    The chart's sections drive Easy drums; drum_loudness gives one value per section."""
    tracks = []
    for t in chart.tracks:
        if t.difficulty == "Expert":
            tracks.append(t)
            tracks += reduce_track(t, chart.tempo, sections=[s for s, _ in chart.sections],
                                   loudness=drum_loudness if t.is_drums else None)
    return Chart(chart.info, chart.tempo, list(chart.sections), tracks)


def onset_ticks(track: Track) -> list[int]:
    """The ticks that hold notes (a chord or a multi-pad hit is one onset)."""
    return sorted({n.tick for n in track.notes})


# ------------------------------------------------------------------------------------------------ checks

@dataclass(frozen=True)
class Issue:
    difficulty: str
    kind: str
    message: str
    tick: int | None = None
    error: bool = True


# shares of Expert onsets outside these only warn (DESIGN 2.11; drums: Harmonix p10-p90)
FRET_BANDS = {"Hard": (0.63, 0.90), "Medium": (0.36, 0.65), "Easy": (0.23, 0.49)}
DRUM_BANDS = {"Hard": (0.62, 0.98), "Medium": (0.39, 0.85), "Easy": (0.30, 0.71)}
HARD_SHARE_LIMIT = 0.90  # 5-fret Hard at this share of Expert onsets or more is an error (the critique)


def check_reductions(tracks: Sequence[Track], tempo: TempoMap) -> list[Issue]:
    """Problems in one instrument's ladder (its Expert and any lower tracks). Errors break Clone Hero's or our rules;
    warnings flag shares of Expert onsets outside the usual bands."""
    by = {t.difficulty: t for t in tracks}
    if "Expert" not in by:
        return [Issue("Expert", "noExpert", "no Expert track")]
    expert = by["Expert"]
    res = tempo.resolution
    issues: list[Issue] = []
    ex_on = onset_ticks(expert)
    ex_set = set(ex_on)
    for a, b in _spans(expert, STAR_POWER):  # scan-chart checks every track; a phrase empty on Expert is the input's
        if not any(a <= t < b for t in ex_on):
            issues.append(Issue("Expert", "emptyStarPower", "a star-power phrase with no notes", a))
    upper = expert
    for level in LEVELS:
        if level not in by:
            continue
        tr = by[level]
        on = onset_ticks(tr)
        bad = sorted(set(on) - set(onset_ticks(upper)))
        if bad:
            issues.append(Issue(level, "notNested", f"{len(bad)} onsets are not onsets of {upper.difficulty}", bad[0]))
        if set(on) - ex_set:
            issues.append(Issue(level, "notNested", "onsets that Expert does not have", min(set(on) - ex_set)))
        if len(on) >= len(onset_ticks(upper)) and ex_on:
            issues.append(Issue(level, "ladder", f"{len(on)} onsets, not fewer than {upper.difficulty}'s "
                                                 f"{len(onset_ticks(upper))}"))
        if sorted(tr.notes, key=_sort_key) == sorted(expert.notes, key=_sort_key) and len(on) > 20:
            issues.append(Issue(level, "difficultyNotReduced", "identical to Expert"))
        share = len(on) / len(ex_on) if ex_on else 0.0
        lo, hi = (DRUM_BANDS if tr.is_drums else FRET_BANDS)[level]
        if ex_on and not lo <= share <= hi:
            issues.append(Issue(level, "share", f"{share:.2f} of Expert onsets, outside {lo}-{hi}", error=False))
        if not tr.is_drums and level == "Hard" and share >= HARD_SHARE_LIMIT:
            issues.append(Issue(level, "hardNotThinned", f"Hard keeps {share:.2f} of Expert onsets"))
        for a, b in _spans(tr, STAR_POWER):
            if not any(a <= t < b for t in on):
                issues.append(Issue(level, "emptyStarPower", "a star-power phrase with no notes", a))
        issues += _check_drums(tr, level, on) if tr.is_drums else _check_frets(tr, level, tempo)
        upper = tr
    return issues


def _sort_key(n):
    return (n.tick, getattr(n, "pad", -1), getattr(n, "frets", ()))


def _check_frets(tr: Track, level: str, tempo: TempoMap) -> list[Issue]:
    issues = []
    groups = _fret_groups(tr.notes)
    ticks = sorted(groups)
    hopo = hopo_states(tr.notes, tempo.resolution)
    for a, b in tr.solos:
        if not any(a <= t <= b for t in ticks):
            issues.append(Issue(level, "emptySoloSection", "a solo with no notes", a))
    for i, t in enumerate(ticks):
        n = groups[t]
        if not _fret_legal(n.frets, level):
            issues.append(Issue(level, "difficultyForbiddenNote", f"frets {n.frets} on {level}", t))
        if n.tap:
            issues.append(Issue(level, "tap", "a tap below Expert", t))
        if hopo[t] and level != "Hard":
            issues.append(Issue(level, "hopo", f"a HOPO on {level}", t))
        if n.length:
            ms = (tempo.tick_to_sec(t + n.length) - tempo.tick_to_sec(t))
            if ms < BABY_SUSTAIN_S:
                issues.append(Issue(level, "babySustain", f"a {ms * 1000:.0f} ms sustain", t))
            elif ms < SUSTAIN_MIN_S - 1e-6:
                issues.append(Issue(level, "shortSustain", f"a {ms * 1000:.0f} ms sustain", t, error=False))
            if i + 1 < len(ticks):
                gap = tempo.tick_to_sec(ticks[i + 1]) - tempo.tick_to_sec(t + n.length)
                if gap < SUSTAIN_GAP_MIN_S:
                    issues.append(Issue(level, "badSustainGap", f"{gap * 1000:.0f} ms to the next note", t))
                elif gap < 0.060:
                    issues.append(Issue(level, "sustainGap", f"{gap * 1000:.0f} ms to the next note", t, error=False))
    return issues


def _check_drums(tr: Track, level: str, on: list[int]) -> list[Issue]:
    issues = []
    for t, hits in sorted(_drum_groups(tr.notes).items()):
        pads = [h.pad for h in hits if not h.double_kick] + [0 for h in hits if h.double_kick]
        hands = [p for p in pads if p]
        kick = 0 in pads
        if any(h.double_kick for h in hits):
            issues.append(Issue(level, "difficultyForbiddenNote", "a 2x kick below Expert", t))
        if len(pads) != len(set(pads)):
            issues.append(Issue(level, "padCollision", "two gems on one pad", t))
        if len(hands) > 2:
            issues.append(Issue(level, "invalidChord", f"{len(hands)} hand gems", t))
        if level == "Easy" and kick and hands:
            issues.append(Issue(level, "difficultyForbiddenNote" if len(hands) >= 2 else "easyKickWithPad",
                                "a kick paired with a pad on Easy", t))
        if level in ("Hard", "Medium") and kick and len(hands) >= 2:
            issues.append(Issue(level, "threeLimbs", f"a three-limb hit on {level}", t))
    for p in tr.phrases:
        if p.kind == DRUM_ACTIVATION and not any(p.tick <= t <= p.tick + p.length for t in on):
            issues.append(Issue(level, "emptyFill", "an activation lane with no note", p.tick))
    return issues
