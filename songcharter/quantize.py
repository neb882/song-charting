"""Quantizing: notes in seconds onto ticks of the song's own tempo map.

Every source of notes hands over a TimedSong in seconds of the input audio (timed.py). This module puts those notes
on our TempoMap, so every part shares one grid whatever tool it came from and no note keeps another tool's timing.
It follows DESIGN.md §2.6 with the critique's corrections (CRITIQUE.json):

  1. **Offset.** A tool can run consistently early or late (on the test song STRUM sits about 30 ms and chartgen
     about 50 ms behind human beat-line placement). `estimate_offset` measures that constant against our grid from
     the circular mean of the note phases: within an 8th note, which is unambiguous for offsets within +-a 16th, and
     within a 16th for precision, then the median residual. A part is shifted by -offset before snapping when the
     phases make the estimate certain (`QuantizeRules.applies`).
  2. **Grid.** Every beat is straight (1/16 slots) or triplet (1/12 slots: 8th-note triplets). A beat goes triplet
     only inside a run of notes that fits triplets clearly better; `SnapGrid.from_ticks` spells out the rule. A note
     snaps to the nearer slot, the coarser line winning near the midpoint (`SnapGrid`); a note that a source on a
     1/32 grid (STRUM) put on an odd 1/32 takes the coarser of the two slots around it when near their midpoint
     (`odd_32nds`). DESIGN.md's 1/32 and 1/24 burst grids are not used (§2.6): drums snap to 1/16 plus triplets
     (§2.9), the sources barely write them (autochart: three 1/32s and no 1/24 on the test song; STRUM's odd 1/32s
     are its rounding), and a 1/32 level would keep that rounding. The minimum spacing is no reason on its own: notes
     a 1/32 apart fall under it only above 136 BPM (HOPOs; strums above 94 BPM), a 1/24 apart above 182 BPM (strums
     above 125).
  3. **5-fret clean-up.** Notes that land on one tick merge (the union of their frets), then the difficulty's chord
     limits apply (`limit_chord`). Onsets at least 3/4 of a slot apart are not merged: one moves to its free
     neighbouring slot instead (`_separate`), so two 16ths never become a chord. An onset closer to the previous one
     than the minimum spacing (strums 80 ms, HOPOs and taps 55 ms) is dropped, so brokenNote (15 ms) cannot fire.
  4. **Sustains.** The end snaps to the grid and stops max(85 ms, a 1/16) before the next note on Expert and Hard (a
     1/8 on Medium, a 1/4 on Easy). A sustain shorter than max(200 ms, 0.75 beat) on Expert and Hard (1 beat on
     Medium, 2 on Easy) is dropped. So badSustainGap (40 ms) and babySustain (100 ms) cannot fire either.
  5. **HOPOs.** The source's HOPO or strum state (TimedNote.hopo) is reproduced on our grid: where the natural state
     on our grid differs from it, the note gets a flip (`N 5`). With `forced_only`, only the states the source forced
     (TimedNote.hopo_forced) are reproduced and the rest follow the natural rule on our grid, so a natural HOPO that
     only the source's wrong tempo map made (8ths on a half-tempo map) does not become a forced one. Taps and open
     notes are kept.
  6. **Drums.** One hit per pad per tick. A pad cannot be cymbal and tom at once: the cymbal stays and the tom
     moves to a free tom pad, yellow first as Rock Band does, or is dropped. At most two hand pads per tick (the
     hits closest to the slot stay, accents first); 2x kick on Expert only; on Easy no kick under two hand pads
     (scan-chart's difficultyForbiddenNote).
  7. **Spans.** Star power, solos and drum fills snap to the grid, then stretch or shrink so they cover exactly the
     notes they covered in the source. A span left with no notes is dropped (no emptyStarPower).

Timeline: tick 0 of the tempo map is the first sample of the padded audio (`plan_lead_in`), so input second t sits
at t + pad_seconds (LeadIn.pad_seconds) on the map.

    lead = plan_lead_in(grid.beats, grid.downbeats, 44100, duration=len_s)
    tm = TempoMap.from_beats(lead.beats, bars=lead.bars, tolerance=0.003)
    for (instrument, difficulty), (track, report) in quantize_song(song, tm, lead.pad_seconds).items(): ...
"""
from __future__ import annotations

import bisect
import math
from dataclasses import dataclass
from fractions import Fraction

import numpy as np

from .chart import DRUM_ACTIVATION, OPEN, STAR_POWER, DrumHit, FretNote, Phrase, Track
from .tempo import TempoMap
from .timed import DIFFICULTIES, TimedHit, TimedNote, TimedPart, TimedSong, TimedSpan

TRACK_INSTRUMENT = {"guitar": "Single", "bass": "DoubleBass", "drums": "Drums"}
TRACK_DIFFICULTY = {"expert": "Expert", "hard": "Hard", "medium": "Medium", "easy": "Easy"}


@dataclass(frozen=True)
class ChordLimits:
    max_notes: int  # frets in one chord
    max_span: int   # highest lane minus lowest lane
    top_lane: int   # highest lane allowed (4 = orange)


# DESIGN.md §2.7 (Expert) and §2.11 step 1 (the lower levels). They include scan-chart's difficultyForbiddenNote:
# Hard has no G+O, Medium no orange and no G+B, Easy no blue or orange.
CHORD_LIMITS = {
    "expert": ChordLimits(3, 3, 4),  # no 4- or 5-note chords, no G+O
    "hard": ChordLimits(2, 3, 4),    # a 3-note chord keeps its outer notes; G+O becomes G+B
    "medium": ChordLimits(2, 2, 3),  # GR, RY, YB, GY or RB; orange moves to blue
    "easy": ChordLimits(1, 0, 2),    # the lowest note, on G, R or Y
}

# sustains: the critique's floor of max(200 ms, 0.75 beat) on Expert and Hard; Medium and Easy as DESIGN.md §2.11
SUSTAIN_MIN_S = 0.200
SUSTAIN_MIN_BEATS = {"expert": 0.75, "hard": 0.75, "medium": 1.0, "easy": 2.0}
SUSTAIN_GAP_S = 0.085  # a sustain ends at least this long before the next note ...
SUSTAIN_GAP_BEATS = {"expert": 0.25, "hard": 0.25, "medium": 0.5, "easy": 1.0}  # ... and at least this many beats

# the measured Expert grid mix (DESIGN.md §2.6), keyed by the slot's denominator in beats: 1 = a beat line (a 1/4
# note), 2 = an 8th line, 4 = a 16th, 3 = an 8th-note triplet, 8 = a 1/32, 6 = a 1/24
SLOT_PRIOR = {1: 0.41, 2: 0.33, 4: 0.17, 3: 0.053, 8: 0.020, 6: 0.011}

HOPO_THRESHOLD = 65 / 192  # of a beat: a .chart natural HOPO is at most floor(65/192 x resolution) ticks after
STRUM_SPACING_S = 0.080    # minimum onset spacing before a strummed note (DESIGN.md §2.6) ...
HOPO_SPACING_S = 0.055     # ... and before a HOPO or a tap
MAX_HANDS = 2              # drum pads other than the kick on one tick
TOM_MOVES = {2: (3, 4), 3: (2, 4), 4: (2, 3)}  # where a tom that collides with a cymbal goes, in order of preference


@dataclass(frozen=True)
class QuantizeRules:
    straight: int = 4                   # straight slots per beat: 1/16 notes
    triplet: int = 3                    # triplet slots per beat: 8th-note triplets; 0 = never
    triplet_min_notes: int = 2          # off-beat notes a triplet run needs
    triplet_ratio: float = 0.25         # a run's squared triplet error at most this x its squared straight error
    triplet_max_error_s: float = 0.025  # every off-beat note of a run this close to its triplet slot (and 1/4 slot)
    triplet_bridge: int = 3             # beats in a row without off-beat notes that a run may span
    sigma_s: float = 0.020              # timing scale of the snapping cost (SnapGrid)
    grid32_share: float = 0.95          # a source is on a 1/32 grid (odd_32nds) when this share of its onsets lies
    grid32_tol: float = 0.05            # within this fraction of a 1/32 of the 1/32 lines of its own beats;
    grid32_reach: float = 0.25          # its notes on odd 1/32s take the coarser slot this close (in slots) to the
                                        # midpoint between two of ours (SnapGrid.snap)
    separate: float = 0.75              # onsets on one lane at least this many slots apart never share a tick
    min_concentration: float = 0.1      # apply a measured offset when the 16th-note phases are this concentrated,
    min_evidence: float = 16.0          # n·R² is at least this (so its standard error is under 1/36 of a 16th),
    max_offset_s: float = 0.060         # and it is no larger than this
    source_hopo: bool = True            # reproduce the source's HOPO/strum states (False: natural HOPOs only)
    forced_only: bool = False           # with source_hopo, only the states the source forced (TimedNote.hopo_forced)
    taps: bool = True                   # keep taps

    def applies(self, offset: float, concentration: float, n_onsets: int) -> bool:
        """Whether a measured offset is trustworthy enough to shift a part by.

        n·R² is the Rayleigh statistic of the 16th-note phases: random phases give about 1 (16 has p ~ 1e-7), and
        the circular standard error of their mean is at most 1/sqrt(2·n·R²) radians, 3 ms at 142 BPM for 16.
        """
        return (concentration >= self.min_concentration and n_onsets * concentration ** 2 >= self.min_evidence
                and abs(offset) <= self.max_offset_s)


RULES = QuantizeRules()


@dataclass
class QuantizeReport:
    """What quantizing did to one part, counted in source notes: notes_in = notes_out + merged + dropped."""
    instrument: str
    difficulty: str
    measured_offset: float = 0.0  # estimate_offset on this part, seconds (positive: the source is late)
    concentration: float = 0.0    # its 16th-note phase concentration (0..1)
    offset: float = 0.0           # seconds subtracted from every time before snapping (0 = no shift)
    notes_in: int = 0
    notes_out: int = 0
    merged: int = 0               # joined another note on its tick
    separated: int = 0            # moved to a neighbouring slot, off a tick a clearly earlier or later note holds
    dropped: int = 0              # left out: before tick 0, under the minimum spacing, a 2x kick below Expert,
                                  # a third hand pad, a tom with no free pad
    limited: int = 0              # changed by the difficulty's limits (chord shape, a tom moved off a cymbal)
    triplet_notes: int = 0        # written on a triplet slot that is not a 1/16 line
    odd_32nds: int = 0            # on an odd 1/32 of a source on a 1/32 grid (odd_32nds): near the midpoint
                                  # between two slots, the coarser one takes it
    median_error: float = 0.0     # |snapped time - source time| after the offset, seconds
    max_error: float = 0.0
    moved_25ms: int = 0           # notes kept more than 25 ms from their source time after the offset (DESIGN.md
    moved_signed_median: float = 0.0  # M1a's "none moved > 25 ms"), and their median signed error (+ = later);
                                  # information only
    sustains_trimmed: int = 0     # ended earlier to leave the gap before the next note
    sustains_dropped: int = 0     # shorter than the minimum, so no sustain
    flips: int = 0                # notes forced against the natural HOPO state on our grid
    spans_dropped: int = 0        # star power, solo or fill spans left with no notes


def estimate_offset(times, tempo_map: TempoMap, pad_seconds: float = 0.0) -> tuple[float, float]:
    """A source's constant timing offset against our grid, and how concentrated its note phases are.

    times: onsets in seconds of the input audio (duplicates count once).
    Returns (offset, concentration). offset is in seconds, positive when the notes sit late: subtract it.

    The circular mean of the phases within a 16th gives the offset up to a whole 16th. The circular mean within an
    8th, unambiguous for offsets within +-a 16th, picks that whole 16th: it is taken over the notes that sit on the
    16th lines the first mean implies (within 1/4 of a 16th), since notes off them (1/32s, triplets) would bias it.
    When it is not significant (Rayleigh n·R² < 9: as many notes on odd 16ths as on 8ths) the branch nearest zero is
    taken. The median residual to the implied 16th lines refines the result. concentration is the 16th-level mean
    resultant length: 1 when every note sits the same distance from a 16th line, about 0 when they ignore the grid.
    """
    t = np.unique(np.asarray(times, dtype=np.float64)) + pad_seconds
    if len(t) == 0:
        return 0.0, 0.0
    res = tempo_map.resolution
    eighth, sixteenth = res / 2, res / 4
    x = tempo_map.secs_to_ticks(t)
    z16 = np.mean(np.exp(2j * np.pi * x / sixteenth))
    fine = np.angle(z16) / (2 * np.pi) * sixteenth  # ticks, within +-1/32
    on = np.abs((x - fine + sixteenth / 2) % sixteenth - sixteenth / 2) <= sixteenth / 4
    z8 = np.mean(np.exp(2j * np.pi * x[on] / eighth)) if on.any() else 0
    if on.sum() * abs(z8) ** 2 >= 9:
        coarse = np.angle(z8) / (2 * np.pi) * eighth  # ticks, within +-1/16
        fine += sixteenth * round((coarse - fine) / sixteenth)
    lines = np.round((x - fine) / sixteenth) * sixteenth
    return float(np.median(t - tempo_map.ticks_to_secs(lines))), float(abs(z16))


def odd_32nds(times, beats, rules: QuantizeRules = RULES) -> np.ndarray:
    """Which onsets sit on an odd 1/32 of the source's own beats (TimedSong.beats), if the source is on a 1/32 grid.

    A source that writes its notes on a 1/32 grid (STRUM) rounds a hit between two of its 16th lines onto the odd
    1/32 halfway between them. SnapGrid's coarser line wins only within 2.5-3.3 ms of that midpoint, and our grid
    differs from the source's locally by more (on the test song STRUM sits 9-30 ms off our 16th lines over 4-bar
    windows), so such notes went to either line. The hit is mostly on the coarser one (the beat or 8th line), which
    `SnapGrid.snap(coarse=True)` takes. Two limits keep real 16ths where they are:
      * an odd note with another onset of the source (any lane) on that coarser 1/32 line is a hit of its own, not
        that line's rounded off, and is not flagged;
      * snap takes the coarser slot only within `rules.grid32_reach` (1/4) slot of the midpoint on our grid. The
        source rounds by at most half a 1/32, a quarter of a 16th, so a hit on one of our lines that it rounded onto an
        odd 1/32 (where its one tempo drifts from the song's, or its beat is two of ours) sits at least that far out.
    Of STRUM's notes on an odd 1/32 on the test song that the stem's onset envelope decides (a 30 ms margin), drums
    go from 123 on the right line and 32 a 16th off to 140 and 15 (of 159), bass from 170 and 27 to 173 and 24 (of
    201); the rest sit on triplet slots. On the four references STRUM ran on, on the human chart's own grid, 61 more
    human guitar and bass onsets get a note (48 on Drunk Drivers) and 11 fewer drum onsets (10 on Take Me Out).

    The source counts as on a 1/32 grid when at least `rules.grid32_share` of its distinct onsets lie within
    `rules.grid32_tol` of a 1/32 of one of its 1/32 lines, the beats interpolated linearly. Measured on the test song
    and the references: STRUM 0.97-1.00 (it rounds some notes a tick off its lines), autochart 0.92-1.00 (0.92 on
    Lucretia, where its beat grid is wrong), ADTOF 0.11-0.12 (what chance gives). Otherwise no onset is flagged.
    The flagged notes still count in the triplet test (SnapGrid.from_ticks): STRUM cannot write a triplet, so its
    1/3 and 2/3 come as 3/8 and 5/8.
    """
    t = np.asarray(times, dtype=np.float64)
    b = np.asarray(beats, dtype=np.float64)
    if len(t) == 0 or len(b) < 2:
        return np.zeros(len(t), dtype=bool)
    i = np.clip(np.searchsorted(b, t, "right") - 1, 0, len(b) - 2)
    length = (b[i + 1] - b[i]) / 8  # a 1/32 of that beat
    k = np.round((t - b[i]) / length)
    near = np.abs(t - b[i] - k * length) <= rules.grid32_tol * length
    u, first = np.unique(t, return_index=True)
    if near[first].mean() < rules.grid32_share:
        return np.zeros(len(t), dtype=bool)
    tc = b[i] + np.where((k - 1) % 4 == 0, k - 1, k + 1) * length  # the coarser 1/32 line beside it: an 8th line
    j = np.searchsorted(u, tc)
    gap = np.minimum(np.abs(u[np.minimum(j, len(u) - 1)] - tc), np.abs(u[np.maximum(j - 1, 0)] - tc))
    return near & (k % 2 == 1) & (gap > rules.grid32_tol * length)


@dataclass(frozen=True)
class SnapGrid:
    """Snapping slots on a tempo map: 1/16 lines, and 1/12 lines in the triplet beats.

    A tick snaps to the cheaper of the two slots around it, cost = (distance / sigma)² / 2 - log(prior of the slot's
    level), the priors being the measured Expert grid mix (DESIGN.md §2.6). That is the nearer slot except near the
    midpoint, where the coarser line wins: at 142 BPM within 2.5 ms of the midpoint between an 8th line and a 16th
    line, within 6 ms between a beat line and a triplet slot. A note exactly between two slots therefore lands on the
    8th, not on the odd 16th, and so does one that a source on a 1/32 grid put there, up to `reach` slots off the
    midpoint on our grid (`snap(coarse=True)`, `odd_32nds`).
    """
    tempo_map: TempoMap
    straight: int = 4
    triplet: int = 3
    triplet_beats: frozenset = frozenset()
    sigma_s: float = 0.020
    reach: float = 0.25

    def beat_of(self, tick: float) -> int:
        """The beat whose slots a fractional tick snaps to. Beats start half a 1/16 early, so a note just ahead of
        a beat line belongs to that beat."""
        res = self.tempo_map.resolution
        return math.floor((tick + res / (2 * self.straight)) / res)

    def _slots(self, tick: float) -> tuple[int, int, float]:
        """(beat, slots per beat, position in slots from the beat line) of a tick."""
        res = self.tempo_map.resolution
        j = self.beat_of(tick)
        n = self.triplet if j in self.triplet_beats else self.straight
        return j, n, (tick - j * res) * n / res

    def _tick(self, j: int, n: int, k: int) -> int:
        res = self.tempo_map.resolution
        return j * res + round(k * res / n)  # round: slots of a resolution not divisible by n

    def snap(self, tick: float, coarse: bool = False) -> int:
        """The cheaper of the two slots around a tick. With `coarse` (a note that a source on a 1/32 grid put halfway
        between two of its 16th lines, `odd_32nds`), the coarser of the two when the tick lies within `reach` slots
        of their midpoint; between slots of one level (two triplet slots), and further out, the cost decides."""
        j, n, q = self._slots(tick)
        k0 = max(math.floor(q), 0)  # a tick just ahead of the beat line goes to the line
        spt = self.tempo_map.tick_to_sec(tick + 1) - self.tempo_map.tick_to_sec(tick)
        sigma = self.sigma_s / spt * n / self.tempo_map.resolution  # in slots

        def prior(k):
            return SLOT_PRIOR.get(Fraction(k % n, n).denominator, min(SLOT_PRIOR.values()))

        def cost(k):
            return ((q - k) / sigma) ** 2 / 2 - math.log(prior(k))

        if coarse and abs(q - k0 - 0.5) <= self.reach:
            return self._tick(j, n, min((k0, k0 + 1), key=lambda k: (-prior(k), cost(k), k)))
        return self._tick(j, n, min((k0, k0 + 1), key=lambda k: (cost(k), k)))

    def _nearest(self, tick: float) -> int:
        j, n, q = self._slots(tick)
        return self._tick(j, n, math.floor(q + 0.5))

    def step(self, tick: float) -> float:
        """Slot length, in ticks, of the beat a tick snaps into."""
        return self.tempo_map.resolution / self._slots(tick)[1]

    def next_slot(self, slot: int) -> int:
        return self._nearest(slot + 0.6 * self.step(slot))

    def prev_slot(self, slot: int) -> int:
        return self._nearest(slot - 0.6 * self.step(slot - 1))

    def is_triplet_slot(self, tick: int) -> bool:
        return tick % (self.tempo_map.resolution / self.straight) != 0 and self.beat_of(tick) in self.triplet_beats

    @classmethod
    def from_ticks(cls, ticks, tempo_map: TempoMap, rules: QuantizeRules = RULES) -> "SnapGrid":
        """The grid for a part's onsets (fractional ticks): straight, with triplet beats where a run calls for them.

        The triplet rule, with tol = min(25 ms, 1/4 of a triplet slot):
          * an onset is off-beat when it does not snap to its beat line. An off-beat onset leans triplet when it is
            nearer its triplet slot than its 1/16 slot, and within tol of it. An on-beat onset is aligned when it is
            within tol of its beat line;
          * a beat is a candidate when it has off-beat onsets, all of them lean triplet and all its on-beat onsets
            are aligned. A beat with an off-beat onset that does not lean triplet, or an on-beat onset that is not
            aligned (the timing there is off, so nothing near it can be read as a triplet), ends any run;
          * a run is a stretch of candidate beats with at most `triplet_bridge` beats in a row between them that
            have no off-beat onsets (rests and aligned on-beat notes neither end a run nor count);
          * a run goes triplet when it has at least `triplet_min_notes` off-beat onsets, an aligned onset on a beat
            line in one of its beats or right after one (the "1" of "1-trip-let", or the line that closes it), and
            the off-beat onsets' summed squared triplet error is at most `triplet_ratio` (1/4) of their summed
            squared 1/16 error: the triplet slots fit at least twice as closely in RMS. At 142 BPM a 1/16 note must
            be 23 ms late (2/3 of the way to the triplet slot) to read as a triplet, and a lone swung note never does.

        On the test song this keeps autochart's own triplets (10 of its 11) and rejects the passages where STRUM's
        chart runs a 1/32 late (notes at 1/8 and 5/8 of the beat, the beat notes too) and where chartgen's beat grid
        wanders. STRUM's odd 1/32s between aligned beat notes can still go triplet, as its 1/3 and 2/3 would come out
        (`odd_32nds`): 7 bass notes (beats 890-892, 898-899, 950) and 4 drum notes (beats 418, 809, 810). The bass
        stem's weak peaks in beats 890 and 891 sit at 0.62-0.64 of the beat, nearer 2/3 than an 8th or 16th line.
        """
        grid = cls(tempo_map, rules.straight, rules.triplet, sigma_s=rules.sigma_s, reach=rules.grid32_reach)
        x = np.unique(np.asarray(ticks, dtype=np.float64))
        if not rules.triplet or len(x) == 0:
            return grid
        res, s, n = tempo_map.resolution, rules.straight, rules.triplet
        beat = np.floor((x + res / (2 * s)) / res)
        r = x - beat * res
        ks, kt = np.floor(r * s / res + 0.5), np.floor(r * n / res + 0.5)
        sec = tempo_map.ticks_to_secs
        t = sec(x)
        err_s = np.abs(sec(beat * res + ks * res / s) - t)
        err_t = np.abs(sec(beat * res + kt * res / n) - t)
        tol = np.minimum(rules.triplet_max_error_s, (sec(beat * res + res / n) - sec(beat * res)) / 4)
        off = ks != 0
        ok = np.where(off, (err_t < err_s) & (err_t <= tol), err_s <= tol)  # leans triplet / aligned
        beats: dict[int, list] = {}  # beat -> [off-beat onsets, all ok, aligned on-beat onset, Σ err_t², Σ err_s²]
        for b, o, good, et, es in zip(beat.astype(int), off, ok, err_t, err_s):
            v = beats.setdefault(int(b), [0, True, False, 0.0, 0.0])
            v[1] = v[1] and bool(good)
            if o:
                v[0] += 1
                v[3] += et * et
                v[4] += es * es
            else:
                v[2] = v[2] or bool(good)
        triplet: set[int] = set()
        run: list[int] = []
        total = [0, 0.0, 0.0, False]  # off-beat onsets, Σ err_t², Σ err_s², anchored

        def close():
            if (run and total[3] and total[0] >= rules.triplet_min_notes
                    and total[1] <= rules.triplet_ratio * total[2]):
                triplet.update(run)
            run.clear()
            total[:] = [0, 0.0, 0.0, False]

        for b in sorted(beats):
            count, good, aligned, et2, es2 = beats[b]
            if run and b == run[-1] + 1 and aligned:
                total[3] = True  # the beat line right after a candidate beat closes its figure
            if run and (not good or b - run[-1] - 1 > rules.triplet_bridge):
                close()
            if good and count:
                run.append(b)
                total[0] += count
                total[1] += et2
                total[2] += es2
                total[3] = total[3] or aligned
        close()
        return cls(tempo_map, s, n, frozenset(triplet), rules.sigma_s, rules.grid32_reach)


def limit_chord(frets, difficulty: str) -> tuple[int, ...]:
    """A note's frets within the difficulty's limits (CHORD_LIMITS), keeping its shape as far as they allow.

    An open note combined with frets loses the open. Lanes above the top lane move down to it; a chord with too many
    notes keeps its lowest and highest notes (and the lowest inner ones); a chord too wide pulls its upper notes down
    to the lowest note + max_span. So Expert GRYBO -> GRB, Hard GYO -> GB, Medium GB -> GY and RO -> RB, Easy GY -> G.
    """
    fr = sorted(set(frets))
    if not fr:
        raise ValueError("a note needs at least one fret")
    if len(fr) > 1 and OPEN in fr:
        fr.remove(OPEN)
    if fr == [OPEN]:
        return (OPEN,)
    lim = CHORD_LIMITS[difficulty]
    fr = sorted({min(f, lim.top_lane) for f in fr})
    if len(fr) > lim.max_notes:
        fr = [fr[0]] if lim.max_notes == 1 else [fr[0], *fr[1:-1][:lim.max_notes - 2], fr[-1]]
    if fr[-1] - fr[0] > lim.max_span:
        fr = sorted({min(f, fr[0] + lim.max_span) for f in fr})
    return tuple(fr)


def _natural(prev: tuple[int, ...] | None, gap: int, frets: tuple[int, ...], threshold: int) -> bool:
    """Clone Hero's natural HOPO in a .chart (scan-chart's resolveFretModifiers): a single note, at most `threshold`
    ticks after the previous note, which is not the same single note."""
    return prev is not None and gap <= threshold and len(frets) == 1 and not (len(prev) == 1 and prev == frets)


def play_states(notes: list[FretNote], resolution: int) -> list[str]:
    """How Clone Hero plays each note of a .chart track: "tap", "hopo" or "strum"."""
    threshold = math.floor(HOPO_THRESHOLD * resolution)
    out, prev = [], None
    for n in sorted(notes, key=lambda n: n.tick):
        frets = tuple(sorted(set(n.frets)))
        hopo = _natural(prev and prev[1], n.tick - prev[0] if prev else 0, frets, threshold) != n.flip
        out.append("tap" if n.tap else "hopo" if hopo else "strum")
        prev = (n.tick, frets)
    return out


def quantize_part(part: TimedPart, tempo_map: TempoMap, pad_seconds: float = 0.0, offset: float | None = None,
                  rules: QuantizeRules = RULES, source_beats: list[float] | None = None
                  ) -> tuple[Track, QuantizeReport]:
    """One part on our grid, as a chart Track, with a report of what changed.

    offset: seconds to subtract from every time before snapping. None measures it on this part and applies it when
            `rules.applies` trusts it; quantize_song passes the instrument's offset to all its difficulties.
    source_beats: the source's own beat times (TimedSong.beats), input seconds. When the source is on a 1/32 grid, its
            notes on odd 1/32s snap to the coarser slot (`odd_32nds`); None or empty skips that.
    """
    if part.instrument not in TRACK_INSTRUMENT or part.difficulty not in TRACK_DIFFICULTY:
        raise ValueError(f"unknown part {part.instrument} {part.difficulty}")
    drums = part.instrument == "drums"
    notes = sorted(part.notes, key=lambda n: (n.time, n.pad) if drums else n.time)
    rep = QuantizeReport(part.instrument, part.difficulty, notes_in=len(notes))
    times = np.array([n.time for n in notes], dtype=np.float64)
    rep.measured_offset, rep.concentration = estimate_offset(times, tempo_map, pad_seconds)
    if offset is None:
        offset = rep.measured_offset if rules.applies(rep.measured_offset, rep.concentration,
                                                      len(np.unique(times))) else 0.0
    rep.offset = offset
    shift = pad_seconds - offset
    x = tempo_map.secs_to_ticks(times + shift) if len(notes) else np.zeros(0)
    grid = SnapGrid.from_ticks(x, tempo_map, rules)
    odd = odd_32nds(times, [] if source_beats is None else source_beats, rules)
    rep.odd_32nds = int(odd.sum())
    ticks = _separate([grid.snap(v, bool(c)) for v, c in zip(x, odd)], times + shift,
                      [n.pad if drums else 0 for n in notes], grid, tempo_map, rules, rep)
    groups: dict[int, list[int]] = {}
    for i, k in enumerate(ticks):
        if k < 0:
            rep.dropped += 1
        else:
            groups.setdefault(k, []).append(i)
    groups = dict(sorted(groups.items()))
    if drums:
        out, src_tick = _drums(notes, groups, times + shift, tempo_map, part.difficulty, rep)
    else:
        out, src_tick = _frets(notes, groups, grid, tempo_map, shift, part.difficulty, rules, rep)
    rep.notes_out = len(out)
    rep.triplet_notes = sum(grid.is_triplet_slot(n.tick) for n in out)
    signed = np.array([tempo_map.tick_to_sec(k) - (times[i] + shift)
                       for i, k in enumerate(src_tick) if k is not None])
    errors = np.abs(signed)
    if len(errors):
        rep.median_error, rep.max_error = float(np.median(errors)), float(errors.max())
        moved = signed[errors > 0.025]
        rep.moved_25ms = int(len(moved))
        rep.moved_signed_median = float(np.median(moved)) if len(moved) else 0.0
    onsets = sorted({n.tick for n in out})

    def spans(source):
        return _spans(source, times, src_tick, onsets, grid, tempo_map, shift, rep)

    phrases = [Phrase(a, b - a, STAR_POWER) for a, b in spans(part.star_power)]
    if drums:
        phrases += [Phrase(a, b - a, DRUM_ACTIVATION) for a, b in spans(part.activation)]
    solos = [(a, b - 1) for a, b in spans(part.solos)]  # Track.solos ends are inclusive
    track = Track(TRACK_DIFFICULTY[part.difficulty], TRACK_INSTRUMENT[part.instrument], out,
                  sorted(phrases, key=lambda p: (p.tick, p.kind)), solos)
    return track, rep


def quantize_song(song: TimedSong, tempo_map: TempoMap, pad_seconds: float = 0.0,
                  offsets: dict[str, float] | None = None,
                  rules: QuantizeRules = RULES) -> dict[tuple[str, str], tuple[Track, QuantizeReport]]:
    """Every part of a TimedSong on our grid, keyed (instrument, difficulty) like TimedSong.parts.

    One offset per instrument, since one stage of one tool timed all its difficulties: offsets[instrument] when
    given, else measured on its Expert part (its largest part when there is none) and applied when trusted. The
    song's own beats go to every part (quantize_part's source_beats).
    """
    out = {}
    for inst in dict.fromkeys(k[0] for k in song.parts):
        parts = {d: p for (i, d), p in song.parts.items() if i == inst}
        if offsets and inst in offsets:
            off = offsets[inst]
        else:
            ref = parts.get("expert") or max(parts.values(), key=lambda p: len(p.notes))
            times = [n.time for n in ref.notes]
            m, c = estimate_offset(times, tempo_map, pad_seconds)
            off = m if rules.applies(m, c, len(set(times))) else 0.0
        for d in DIFFICULTIES:
            if d in parts:
                out[(inst, d)] = quantize_part(parts[d], tempo_map, pad_seconds, off, rules, song.beats)
    return out


def _separate(ticks: list[int], times, lanes: list[int], grid: SnapGrid, tm: TempoMap, rules: QuantizeRules,
              rep: QuantizeReport) -> list[int]:
    """Keep apart onsets on one lane (a pad, or any fret) that snapped to one tick although they lie at least
    `rules.separate` slots apart. The run of onsets on that tick splits at its largest time gap; the earlier part
    moves to the previous slot or the later part to the next one, whichever is free on the lane and fits closer.
    Closer onsets (flams, 1/32 doubles) stay together and merge."""
    ticks = list(ticks)
    taken = {(lane, k) for lane, k in zip(lanes, ticks)}
    by_lane: dict[int, list[int]] = {}
    for i, lane in enumerate(lanes):
        by_lane.setdefault(lane, []).append(i)
    for lane, idx in by_lane.items():
        a = 0
        while a < len(idx):
            b = a
            while b + 1 < len(idx) and ticks[idx[b + 1]] == ticks[idx[a]]:
                b += 1
            run, a = idx[a:b + 1], b + 1
            k = ticks[run[0]]
            t = [times[i] for i in run]
            if len(run) < 2 or t[-1] - t[0] < rules.separate * (tm.tick_to_sec(grid.next_slot(k)) - tm.tick_to_sec(k)):
                continue
            cut = 1 + int(np.argmax(np.diff(t)))
            options = [(max(abs(tm.tick_to_sec(s) - times[i]) for i in part), s, part)
                       for part, s in ((run[:cut], grid.prev_slot(k)), (run[cut:], grid.next_slot(k)))
                       if s >= 0 and (lane, s) not in taken]
            if options:
                _, s, part = min(options, key=lambda o: (o[0], o[1]))
                for i in part:
                    ticks[i] = s
                taken.add((lane, s))
                rep.separated += len(part)
    return ticks


@dataclass
class _Onset:
    tick: int
    frets: tuple[int, ...]
    end: float | None  # source sustain end, input seconds
    hopo: bool | None  # the state wanted: the source's, or None for the natural one
    tap: bool
    src: list[int]


def _frets(notes: list[TimedNote], groups: dict[int, list[int]], grid: SnapGrid, tm: TempoMap, shift: float,
           difficulty: str, rules: QuantizeRules, rep: QuantizeReport) -> tuple[list[FretNote], list]:
    res = tm.resolution
    threshold = math.floor(HOPO_THRESHOLD * res)
    kept: list[_Onset] = []
    for k, idx in groups.items():
        first = notes[idx[0]]
        union = tuple(sorted({f for i in idx for f in notes[i].frets}))
        frets = limit_chord(union, difficulty)
        tap = rules.taps and first.tap
        want = first.hopo if rules.source_hopo and (first.hopo_forced or not rules.forced_only) else None
        if kept:
            prev = kept[-1]
            natural = _natural(prev.frets, k - prev.tick, frets, threshold)
            hopo = tap or (natural if want is None else want)
            if tm.tick_to_sec(k) - tm.tick_to_sec(prev.tick) < (HOPO_SPACING_S if hopo else STRUM_SPACING_S):
                rep.dropped += len(idx)
                continue
        rep.merged += len(idx) - 1
        rep.limited += frets != union
        ends = [notes[i].end for i in idx if notes[i].end is not None]
        kept.append(_Onset(k, frets, max(ends) if ends else None, want, tap, idx))
    out, src_tick, prev = [], [None] * len(notes), None
    for n, nxt in zip(kept, kept[1:] + [None]):
        length = 0
        if n.end is not None:
            end = grid.snap(tm.sec_to_tick(n.end + shift))
            trimmed = False
            if nxt is not None:
                gap = max(SUSTAIN_GAP_BEATS[difficulty] * res,
                          math.ceil(nxt.tick - tm.sec_to_tick(tm.tick_to_sec(nxt.tick) - SUSTAIN_GAP_S) - 1e-9))
                if end > nxt.tick - gap:
                    end, trimmed = int(nxt.tick - gap), True
            if (end - n.tick >= SUSTAIN_MIN_BEATS[difficulty] * res
                    and tm.tick_to_sec(end) - tm.tick_to_sec(n.tick) >= SUSTAIN_MIN_S - 1e-9):
                length = end - n.tick
                rep.sustains_trimmed += trimmed
            else:
                rep.sustains_dropped += 1
        natural = _natural(prev and prev.frets, n.tick - prev.tick if prev else 0, n.frets, threshold)
        flip = not n.tap and n.hopo is not None and n.hopo != natural
        rep.flips += flip
        out.append(FretNote(n.tick, n.frets, length, flip, n.tap))
        for i in n.src:
            src_tick[i] = n.tick
        prev = n
    return out, src_tick


def _drums(hits: list[TimedHit], groups: dict[int, list[int]], times, tm: TempoMap, difficulty: str,
           rep: QuantizeReport) -> tuple[list[DrumHit], list]:
    out, src_tick = [], [None] * len(hits)
    for k, idx in groups.items():
        lanes: dict[tuple[int, bool], list[int]] = {}  # (pad, cymbal) -> source hits
        for i in idx:
            h = hits[i]
            if h.pad == 0 and h.double_kick and difficulty != "expert":
                rep.dropped += 1  # 2x kick is Expert+ only (difficultyForbiddenNote)
                continue
            lanes.setdefault((h.pad, h.cymbal and h.pad >= 2), []).append(i)
        hands = [lane for lane in lanes if lane[0] != 0]
        if len(hands) > MAX_HANDS:  # keep accents first, then the hits nearest the slot
            t = tm.tick_to_sec(k)

            def rank(lane):
                src = lanes[lane]
                return (not any(hits[i].accent for i in src), min(abs(times[i] - t) for i in src), lane)

            for lane in sorted(hands, key=rank)[MAX_HANDS:]:
                rep.dropped += len(lanes.pop(lane))
            hands = [lane for lane in lanes if lane[0] != 0]
        for p in (2, 3, 4):  # a pad cannot be cymbal and tom at once: the tom moves or goes
            if (p, True) in lanes and (p, False) in lanes:
                tom = lanes.pop((p, False))
                q = next((q for q in TOM_MOVES[p] if (q, True) not in lanes and (q, False) not in lanes), None)
                if q is None:
                    rep.dropped += len(tom)
                else:
                    lanes[(q, False)] = tom
                    rep.limited += len(tom)
        hands = [lane for lane in lanes if lane[0] != 0]
        if difficulty == "easy" and len(hands) == 2 and (0, False) in lanes:
            rep.dropped += len(lanes.pop((0, False)))  # Easy: no kick under two hand pads
        for (pad, cymbal), src in sorted(lanes.items()):
            accent = any(hits[i].accent for i in src)
            out.append(DrumHit(k, pad, cymbal, all(hits[i].double_kick for i in src), accent,
                               not accent and all(hits[i].ghost for i in src)))
            rep.merged += len(src) - 1
            for i in src:
                src_tick[i] = k
    return out, src_tick


def _spans(spans: list[TimedSpan], times, src_tick: list, onsets: list[int], grid: SnapGrid, tm: TempoMap,
           shift: float, rep: QuantizeReport) -> list[tuple[int, int]]:
    """Half-open tick spans [a, b) covering the notes the source spans covered (start <= time < end)."""
    out: list[tuple[int, int]] = []
    for s in sorted(spans, key=lambda s: s.start):
        lo_i, hi_i = np.searchsorted(times, s.start, "left"), np.searchsorted(times, s.end, "left")
        inside = sorted({src_tick[i] for i in range(lo_i, hi_i) if src_tick[i] is not None})
        if out:  # a tick shared with the previous span stays with it
            inside = [k for k in inside if k >= out[-1][1]]
        if not inside:
            rep.spans_dropped += 1
            continue
        lo, hi = inside[0], inside[-1]
        a, b = grid.snap(tm.sec_to_tick(s.start + shift)), grid.snap(tm.sec_to_tick(s.end + shift))
        before = bisect.bisect_left(onsets, lo)
        after = bisect.bisect_right(onsets, hi)
        if a > lo or (before and a <= onsets[before - 1]):
            a = lo  # start on the first note rather than take in another
        a = max(a, out[-1][1] if out else 0)
        b = max(b, hi + 1)
        if after < len(onsets):
            b = min(b, onsets[after])
        out.append((a, b))
    return out
