"""Quantizing: synthetic parts in seconds placed on a tempo map (offset, straight and triplet grids, merges and chord
limits, sustains, HOPO states, taps, drum lanes, spans)."""
from dataclasses import replace

import numpy as np
import pytest

from songcharter.chart import DRUM_ACTIVATION, STAR_POWER, Chart, SongInfo, Track, write_chart
from songcharter.quantize import (HOPO_SPACING_S, MERGE_MAX_S, RULES, RUN_CHORD_S, STRUM_SPACING_S, TAP_RUN,
                                  TAP_RUN_GAP_S, QuantizeRules, SnapGrid, estimate_offset, fast_runs, limit_chord,
                                  odd_32nds, play_states, quantize_part, quantize_song, run_chords)
from songcharter.reduce import hopo_states, reduce_track
from songcharter.tempo import TempoMap
from songcharter.timed import OPEN, TimedHit, TimedNote, TimedPart, TimedSong, TimedSpan

RES = 192
PAD = 1.0  # seconds of lead-in: input second t is at t + PAD on the maps


def const_map(bpm=120.0, beats=400):
    return TempoMap.from_beats(np.arange(beats) * 60 / bpm)


def drifting_map(beats=400):
    rng = np.random.default_rng(3)
    bpm = 140 + np.cumsum(rng.normal(0, 0.3, beats))
    return TempoMap.from_beats(np.concatenate([[0], np.cumsum(60 / bpm[:-1])]), tolerance=0.001)


def at(tm, beat, ms=0.0):
    """Input time of a position on the map, in beats, plus a deviation in ms."""
    return tm.tick_to_sec(beat * RES) - PAD + ms / 1000


def part(notes, instrument="guitar", difficulty="expert", **spans):
    return TimedPart(instrument, difficulty, sorted(notes, key=lambda n: n.time), **spans)


def rock_pattern(beats):
    """Beat positions of a riff: mostly 8ths, some 16ths, a rest every 4th bar."""
    pos = []
    for b in range(beats):
        if b % 16 >= 14:
            continue
        pos += [b, b + 0.5] if b % 4 != 3 else [b, b + 0.25, b + 0.5, b + 0.75]
    return pos


def check(rep):
    assert rep.notes_in == rep.notes_out + rep.merged + rep.dropped + rep.dropped_distinct


# ------------------------------------------------------------------------------------------------ offset

def test_offset_of_a_late_part():
    tm = const_map()
    rng = np.random.default_rng(1)
    pos = rock_pattern(300)
    times = [at(tm, p, 25 + rng.normal(0, 8)) for p in pos]
    off, conc = estimate_offset(times, tm, PAD)
    assert off == pytest.approx(0.025, abs=0.002)
    assert conc > 0.8


def test_offset_past_a_32nd_uses_the_8th_level():
    tm = const_map(142.0)  # a 1/32 is 52.8 ms, a 1/16 105.6 ms
    pos = [b + h for b in range(200) for h in (0, 0.5)] + [b + 0.75 for b in range(0, 200, 4)]
    off, _ = estimate_offset([at(tm, p, 70) for p in pos], tm, PAD)
    assert off == pytest.approx(0.070, abs=0.001)
    early, _ = estimate_offset([at(tm, p, -70) for p in pos], tm, PAD)
    assert early == pytest.approx(-0.070, abs=0.001)


def test_offset_without_8th_evidence_stays_near_zero():
    # as many notes on odd 16ths as on 8ths: the 8th-level phase says nothing, so no 16th-sized jump
    tm = const_map()
    pos = [b + q / 4 for b in range(200) for q in range(4)]
    off, conc = estimate_offset([at(tm, p, 10) for p in pos], tm, PAD)
    assert off == pytest.approx(0.010, abs=0.001)
    assert conc > 0.9


def test_offset_of_notes_that_ignore_the_grid():
    tm = const_map()
    times = np.sort(np.random.default_rng(2).uniform(0, 150, 600))
    off, conc = estimate_offset(times, tm, PAD)
    assert conc < 0.15
    assert not QuantizeRules().applies(off, conc, 600)


def test_a_weak_but_certain_offset_is_applied():
    # 300 notes on 16th lines, 200 on odd 32nds (opposite 16th phase): R ~ 0.2, but over 500 onsets that is certain
    tm = const_map(142.0)
    rng = np.random.default_rng(8)
    pos = [b + q / 4 for b in range(75) for q in range(4)] + [b + 1 / 8 + q / 4 for b in range(100) for q in (0, 2)]
    times = sorted(at(tm, p, 20 + rng.normal(0, 4)) for p in pos)
    off, conc = estimate_offset(times, tm, PAD)
    assert off == pytest.approx(0.020, abs=0.003)
    assert 0.1 < conc < 0.3 and QuantizeRules().applies(off, conc, len(times))


def test_offset_on_a_drifting_tempo_map():
    tm = drifting_map()
    rng = np.random.default_rng(4)
    times = [at(tm, p, 20 + rng.normal(0, 5)) for p in rock_pattern(380)]
    off, conc = estimate_offset(times, tm, PAD)
    assert off == pytest.approx(0.020, abs=0.002)
    assert conc > 0.8


def test_measured_offset_is_removed_before_snapping():
    tm = const_map()
    rng = np.random.default_rng(5)
    pos = rock_pattern(200)
    notes = [TimedNote(at(tm, p, 30 + rng.uniform(-20, 20)), (int(p * 2) % 3,)) for p in pos]
    track, rep = quantize_part(part(notes), tm, PAD)
    assert rep.offset == pytest.approx(0.030, abs=0.003) and rep.offset == rep.measured_offset
    assert [n.tick for n in track.notes] == [round(p * RES) for p in pos]
    assert rep.max_error < 0.025 and rep.moved_25ms == 0 and rep.moved_signed_median == 0.0
    check(rep)
    # notes left more than 25 ms from their source time are counted, with their median signed error
    late = [TimedNote(at(tm, p, 40.0 if i in (5, 9, 13) else 0.0), (0,)) for i, p in enumerate(rock_pattern(8))]
    _, rep = quantize_part(part(late), tm, PAD, offset=0.0)
    assert rep.moved_25ms == 3 and rep.moved_signed_median == pytest.approx(-0.040, abs=1e-6)
    # an untrusted offset (too few notes) is measured but not applied; an explicit one always is
    _, rep = quantize_part(part(notes[:10]), tm, PAD)
    assert rep.offset == 0.0 and rep.measured_offset != 0.0
    _, rep = quantize_part(part(notes[:10]), tm, PAD, offset=0.012)
    assert rep.offset == 0.012



# ------------------------------------------------------------------------------------------------ grid

def snapped(tm, beats_pos, jitter_ms=0.0, seed=0, **kw):
    rng = np.random.default_rng(seed)
    notes = [TimedNote(at(tm, p, rng.uniform(-jitter_ms, jitter_ms)), (i % 5,)) for i, p in enumerate(beats_pos)]
    track, rep = quantize_part(part(notes), tm, PAD, offset=0.0, **kw)
    check(rep)
    return [n.tick for n in track.notes], rep


def test_straight_16ths_with_jitter_never_go_triplet():
    tm = const_map(142.0)
    pos = [b + q / 4 for b in range(160) for q in range(4) if (b + q) % 3]
    ticks, rep = snapped(tm, pos, jitter_ms=22)
    assert rep.triplet_notes == 0
    assert ticks == [round(p * RES) for p in pos]


def test_a_triplet_run_snaps_to_twelfths():
    tm = const_map()
    trip = [8 + k / 3 for k in range(6)]  # two beats of 8th-note triplets
    pos = [b + h for b in range(8) for h in (0, 0.5)] + trip + [b + h for b in range(10, 16) for h in (0, 0.5)]
    ticks, rep = snapped(tm, pos, jitter_ms=12, seed=1)
    assert ticks == [round(p * RES) for p in pos]
    assert rep.triplet_notes == 4


def test_a_lone_triplet_note_stays_straight():
    tm = const_map()
    pos = [0, 0.5, 1, 1 + 1 / 3, 2, 2.5, 3]
    ticks, rep = snapped(tm, pos)
    assert rep.triplet_notes == 0
    assert ticks[3] == RES + RES // 4  # the nearest 1/16


def test_a_shuffle_goes_triplet_across_plain_beats():
    tm = const_map()
    pos = []
    for b in range(16):
        pos += [b, b + 2 / 3] if b % 2 == 0 else [b]  # swung 8ths every other beat; on-beat notes between
    ticks, rep = snapped(tm, pos, jitter_ms=10, seed=2)
    assert ticks == [round(p * RES) for p in pos]
    assert rep.triplet_notes == 8


def test_a_passage_running_a_32nd_late_is_not_read_as_triplets():
    # 8ths shifted a 1/32 late (a source on a 1/32 grid): 5/8 sits near the 2/3 slot, but the beat notes are 1/32 off
    tm = const_map(142.0)
    pos = [b + h + 1 / 8 for b in range(8, 24) for h in (0, 0.5)] + [b + h for b in range(24, 30) for h in (0, 0.5)]
    _, rep = snapped(tm, pos)
    assert rep.triplet_notes == 0
    # the same off-beat notes with no beat notes at all: no anchor, no triplets
    _, rep = snapped(tm, [b + 5 / 8 for b in range(8, 24)])
    assert rep.triplet_notes == 0


def test_a_triplet_figure_is_anchored_by_the_line_that_closes_it():
    tm = const_map()
    pos = [0, 0.5, 1, 1.5, 2 + 1 / 3, 2 + 2 / 3, 3, 3.5, 4]  # "(rest) trip-let" then the beat line
    ticks, rep = snapped(tm, pos, jitter_ms=8, seed=3)
    assert ticks == [round(p * RES) for p in pos] and rep.triplet_notes == 2


def test_triplets_can_be_switched_off():
    tm = const_map()
    ticks, rep = snapped(tm, [0, 1 / 3, 2 / 3, 1, 4 / 3, 5 / 3, 2], rules=QuantizeRules(triplet=0))
    assert rep.triplet_notes == 0 and all(t % 48 == 0 for t in ticks)


def test_snap_grid_beats_start_half_a_16th_early():
    tm = const_map()
    g = SnapGrid(tm, triplet_beats=frozenset({1}))
    assert g.beat_of(RES - 23) == 1 and g.beat_of(RES - 25) == 0
    assert g.snap(RES + 60) == RES + 64 and g.snap(RES + 170) == 2 * RES  # triplet beat
    assert g.snap(2 * RES + 60) == 2 * RES + 48                           # straight beat


def test_a_note_between_two_slots_goes_to_the_coarser_line():
    g = SnapGrid(const_map(142.0))  # 1 tick = 2.2 ms; the 8th/16th boundary moves 2.5 ms toward the 16th
    eighth = 4 * RES + 96
    assert g.snap(eighth + 24) == eighth and g.snap(eighth + 25) == eighth        # midpoint, and 2.2 ms past it
    assert g.snap(eighth + 27) == eighth + 48                                     # 6.6 ms past it
    assert g.snap(eighth - 24) == eighth and g.snap(eighth - 27) == eighth - 48
    # coarse (an odd 1/32 of a source on a 1/32 grid): the 8th up to 1/4 slot (26 ms) off the midpoint
    assert g.snap(eighth + 34, coarse=True) == eighth and g.snap(eighth + 34) == eighth + 48     # 22 ms past it
    assert g.snap(eighth - 34, coarse=True) == eighth and g.snap(eighth - 34) == eighth - 48
    assert g.snap(eighth + 40, coarse=True) == eighth + 48                                      # 35 ms past it
    assert g.snap(4 * RES - 34, coarse=True) == 4 * RES and g.snap(4 * RES - 34) == 4 * RES - 48  # the beat line
    t = SnapGrid(const_map(142.0), triplet_beats=frozenset({1}))  # triplet slots are equally coarse: nearer wins
    assert t.snap(RES + 96 + 6, coarse=True) == RES + 128 and t.snap(RES + 96 - 6, coarse=True) == RES + 64


def on_source_grid(tm, positions, ms, beats=400):
    """A source on a 1/32 grid whose beats sit `ms` off ours: its beat times, and input times of its positions."""
    return [at(tm, b, ms) for b in range(beats)], [at(tm, p, ms) for p in positions]


def test_odd_32nds_only_on_a_source_on_a_32nd_grid():
    tm = const_map(142.0)
    pos = [b + h for b in range(40) for h in (0, 0.5) if b % 4 < 2]                    # notes on beats 0, 1, 4, 5 ...
    free = [b + 7 / 8 for b in range(2, 40, 4)] + [b + 3 / 8 for b in range(3, 40, 4)]  # nothing on 3, 3.5, 7 ...
    taken = [b + 1 / 8 for b in range(0, 40, 4)]  # a 1/32 after a note on the beat: a hit of its own
    beats, times = on_source_grid(tm, pos + free + taken, -12)
    assert list(odd_32nds(times, beats)) == [False] * len(pos) + [True] * len(free) + [False] * len(taken)
    pos += free + taken
    # a note a tick off its line at 480 PPQ still counts (1.25 ms at 100 BPM: the tolerance is 1/20 of a 1/32)
    slow = const_map(100.0)
    beats, times = on_source_grid(slow, [b + 3 / 8 for b in range(40)], 0)
    assert odd_32nds([t + 0.00125 for t in times], beats).all()
    # a source that times notes freely (ADTOF) is not on a 1/32 grid: about 1 in 10 lands near a line by chance
    rng = np.random.default_rng(9)
    beats, times = on_source_grid(tm, pos, 0)
    assert not odd_32nds(np.array(times) + rng.uniform(-0.02, 0.02, len(times)), beats).any()
    assert not odd_32nds(times, []).any() and odd_32nds([], beats).shape == (0,)


def test_odd_32nds_snap_to_the_coarser_line_where_the_grids_differ():
    # the source's grid runs 12 ms early here, which the constant offset does not remove: its 7/8s and 3/8s (hits on
    # the beat and the 8th, rounded onto its odd 1/32s) sit 12 ms short of the midpoint between our 16th lines
    tm = const_map(142.0)
    pos = [b + h for b in range(0, 32) for h in (0, 0.5) if b % 4 != 3] + [b + 7 / 8 for b in range(2, 32, 4)]
    pos += [b + 3 / 8 for b in range(3, 32, 4)]
    beats, times = on_source_grid(tm, pos, -12)
    hits = [TimedHit(t, 1 if p % 1 else 0) for t, p in zip(times, pos)]
    track, rep = quantize_part(part(hits, "drums"), tm, PAD, offset=0.0, source_beats=beats)
    assert sorted(n.tick for n in track.notes) == sorted(round(np.ceil(p * 2) / 2 * RES) for p in pos)
    assert rep.odd_32nds == 16 and rep.triplet_notes == 0
    check(rep)
    plain, rep = quantize_part(part(hits, "drums"), tm, PAD, offset=0.0)  # no source beats: each takes the nearer 16th
    assert rep.odd_32nds == 0
    assert sum(n.tick % 96 != 0 for n in plain.notes) == 16
    # quantize_song hands the song's beats to every part
    out = quantize_song(TimedSong("t", {("drums", "expert"): part(hits, "drums")}, beats=beats), tm, PAD,
                        offsets={"drums": 0.0})
    assert out[("drums", "expert")][0] == track


def test_a_source_beat_that_is_not_ours_moves_nothing():
    # a half-tempo source: its beat is two of ours, so its odd 1/32s are our odd 16th lines, where the notes stay
    tm = const_map(142.0)
    pos = [q / 4 for q in range(160) if q % 3]
    beats = [at(tm, 2 * b) for b in range(100)]
    notes = [TimedNote(at(tm, p), (i % 3,)) for i, p in enumerate(pos)]
    track, rep = quantize_part(part(notes), tm, PAD, offset=0.0, source_beats=beats)
    assert rep.odd_32nds > 0 and [n.tick for n in track.notes] == [round(p * RES) for p in pos]


def test_triplets_of_a_source_on_a_32nd_grid_still_go_triplet():
    # STRUM cannot write triplets: a 1/3 and a 2/3 come out as 3/8 and 5/8, odd 1/32s that still read as triplets
    tm = const_map(142.0)
    trip = [8, 8 + 3 / 8, 8 + 5 / 8, 9, 9 + 3 / 8, 9 + 5 / 8]
    pos = [b + h for b in range(8) for h in (0, 0.5)] + trip + [b + h for b in range(10, 16) for h in (0, 0.5)]
    beats, times = on_source_grid(tm, pos, 0)
    notes = [TimedNote(t, (i % 5,)) for i, t in enumerate(times)]
    track, rep = quantize_part(part(notes), tm, PAD, offset=0.0, source_beats=beats)
    assert rep.odd_32nds == 4 and rep.triplet_notes == 4
    assert [n.tick for n in track.notes if 8 * RES <= n.tick < 10 * RES] == [8 * RES + k * 64 for k in range(6)]


# ------------------------------------------------------------------------------------------------ chords

@pytest.mark.parametrize("frets, difficulty, want", [
    ((0, 1, 2, 3, 4), "expert", (0, 1, 3)),
    ((0, 4), "expert", (0, 3)),
    ((1, 2, 3), "expert", (1, 2, 3)),
    ((0, 2, 4), "hard", (0, 3)),
    ((0, 4), "hard", (0, 3)),
    ((1, 4), "hard", (1, 4)),
    ((0, 3), "medium", (0, 2)),
    ((1, 4), "medium", (1, 3)),
    ((3, 4), "medium", (3,)),
    ((4,), "medium", (3,)),
    ((0, 2), "easy", (0,)),
    ((3,), "easy", (2,)),
    ((OPEN, 2), "expert", (2,)),
    ((OPEN,), "easy", (OPEN,)),
])
def test_limit_chord(frets, difficulty, want):
    assert limit_chord(frets, difficulty) == want


def test_notes_on_one_tick_merge_then_obey_the_limits():
    tm = const_map()
    notes = [TimedNote(at(tm, 4), (0,)), TimedNote(at(tm, 4, 15), (4,)), TimedNote(at(tm, 5), (1,)),
             TimedNote(at(tm, 5, 8), (1,))]
    track, rep = quantize_part(part(notes), tm, PAD, offset=0.0)
    assert [(n.tick, n.frets) for n in track.notes] == [(4 * RES, (0, 3)), (5 * RES, (1,))]
    assert rep.merged == 2 and rep.limited == 1
    check(rep)
    track, _ = quantize_part(part(notes, difficulty="medium"), tm, PAD, offset=0.0)
    assert track.notes[0].frets == (0, 2)


def test_onsets_a_16th_apart_never_share_a_tick():
    tm = const_map(142.0)  # a 1/16 is 105.6 ms
    notes = [TimedNote(at(tm, 3), (2,)), TimedNote(at(tm, 4, -50), (0,)), TimedNote(at(tm, 4, 45), (1,)),
             TimedNote(at(tm, 5, 30), (3,)), TimedNote(at(tm, 5.25, -48), (4,)), TimedNote(at(tm, 5.25), (2,))]
    track, rep = quantize_part(part(notes), tm, PAD, offset=0.0)
    # 4 - 50 ms and 4 + 45 ms both snap to beat 4: the earlier fits its other slot better and moves there.
    # 5.25 - 48 ms and 5.25 are under 3/4 of a slot apart, so they stay on one tick, but 48 ms apart they are no
    # chord: the one on the tick stays (the chord rule)
    assert [(n.tick, n.frets) for n in track.notes] == [
        (3 * RES, (2,)), (4 * RES - 48, (0,)), (4 * RES, (1,)), (5 * RES, (3,)), (5 * RES + 48, (2,))]
    assert rep.separated == 1 and rep.merged == 0 and rep.dropped_distinct == 1
    check(rep)
    # drums: one lane per pad; a flam on one pad merges
    hits = [TimedHit(at(tm, 4, -50), 1), TimedHit(at(tm, 4, 45), 1), TimedHit(at(tm, 4, 45), 2, cymbal=True),
            TimedHit(at(tm, 6), 1), TimedHit(at(tm, 6, 20), 1)]
    track, rep = quantize_part(part(hits, "drums"), tm, PAD, offset=0.0)
    assert [(n.tick, n.pad) for n in track.notes] == [(4 * RES - 48, 1), (4 * RES, 1), (4 * RES, 2), (6 * RES, 1)]
    assert rep.separated == 1 and rep.merged == 1


def test_onsets_distinct_in_time_make_no_chord():
    """Two onsets 50 ms apart on one tick (under 3/4 of a 125 ms slot, so _separate leaves them): the one farther
    from the tick is dropped and counted, the earlier one when it is the farther; its state goes with it. 15 ms
    apart they stay a chord, and a chord never spans more than MERGE_MAX_S. Drum hits are not touched."""
    assert MERGE_MAX_S == 0.020
    tm = const_map()  # 120 BPM: a 1/16 is 125 ms
    notes = [TimedNote(at(tm, 4, -10), (0,)), TimedNote(at(tm, 4, 40), (1,)),            # the later is farther
             TimedNote(at(tm, 6, -40), (2,), tap=True), TimedNote(at(tm, 6, 10), (3,)),  # the earlier is farther
             TimedNote(at(tm, 8, -5), (0,)), TimedNote(at(tm, 8, 10), (2,)),             # 15 ms: a chord
             # each within 20 ms of the one on the tick, 28 ms from each other: the nearer joins it, not both
             TimedNote(at(tm, 10, -12), (0,)), TimedNote(at(tm, 10), (1,)), TimedNote(at(tm, 10, 16), (2,))]
    track, rep = quantize_part(part(notes), tm, PAD, offset=0.0)
    assert [(n.tick, n.frets, n.tap) for n in track.notes] == [
        (4 * RES, (0,), False), (6 * RES, (3,), False), (8 * RES, (0, 2), False), (10 * RES, (0, 1), False)]
    assert rep.dropped_distinct == 3 and rep.merged == 2 and rep.dropped == 0 and rep.separated == 0
    check(rep)
    hits = [TimedHit(at(tm, 4, -10), 1), TimedHit(at(tm, 4, 40), 2, cymbal=True)]  # two pads: not a chord
    track, rep = quantize_part(part(hits, "drums"), tm, PAD, offset=0.0)
    assert [(n.tick, n.pad) for n in track.notes] == [(4 * RES, 1), (4 * RES, 2)] and rep.dropped_distinct == 0


def test_fast_16ths_keep_every_note():
    """At 200 BPM a 1/16 is 75 ms: strummed (the same fret) and HOPO (changing frets) 16ths all stay. The floors of
    80 and 55 ms before them dropped every other strum."""
    tm = const_map(200.0)
    strums = [TimedNote(at(tm, 4 + q / 4), (0,)) for q in range(4)]
    hopos = [TimedNote(at(tm, 8 + q / 4), (q % 3,)) for q in range(4)]
    track, rep = quantize_part(part(strums + hopos), tm, PAD, offset=0.0)
    assert [n.tick for n in track.notes] == [4 * RES + 48 * q for q in range(4)] + [8 * RES + 48 * q for q in range(4)]
    assert play_states(track.notes, RES) == ["strum"] * 5 + ["hopo"] * 3 and rep.dropped == 0
    check(rep)


def test_a_chord_inside_a_fast_run_becomes_its_top_note():
    """With run_chord_s (the guitar's 120 ms), a chord whose previous and next onsets both lie closer than that
    becomes its top fret, and plays as any single note there (a natural HOPO after another fret); a chord at a run's
    start or end, a chord between 8ths, a strum section of 8th-note chords and the part's first and last onsets
    stay. The report records the rule and the chords it changed; without the rule nothing changes."""
    assert RUN_CHORD_S == 0.120
    tm = const_map(200.0)  # a 1/16 is 75 ms, an 8th 150 ms
    seq = [(1, (0, 2)),                                                  # the part's first onset
           (1.25, (1,)), (1.5, (2,)),
           (4, (1,)), (4.25, (2,)), (4.5, (1, 3)), (4.75, (2,)),         # inside a run of 16ths: becomes 3
           (5, (1, 2, 4)), (5.25, (1,)),                                 # and a three-note chord: 4
           (8, (0, 2)), (8.25, (1,)), (8.5, (2,)),                       # a run's start (an 8th rest before it)
           (10, (1,)), (10.25, (2,)), (10.5, (1, 3)),                    # a run's end (a rest after it)
           (12, (0,)), (12.5, (1, 2)), (13, (0,)),                       # between 8ths
           (16, (0, 1)), (16.5, (0, 1)), (17, (1, 2)), (17.5, (1, 2)),   # a strum section in 8ths
           (20, (2,)), (20.25, (3,)), (20.5, (1, 4))]                    # the part's last onset
    notes = [TimedNote(at(tm, b), f) for b, f in seq]
    rules = QuantizeRules(forced_only=True, run_chord_s=RUN_CHORD_S)
    track, rep = quantize_part(part(notes), tm, PAD, offset=0.0, rules=rules)
    want = [f for _, f in seq]
    want[5], want[7] = (3,), (4,)
    assert [n.frets for n in track.notes] == want and [n.tick for n in track.notes] == [b * RES for b, _ in seq]
    assert play_states(track.notes, RES)[4:9] == ["hopo"] * 5
    assert rep.run_chords == 2 and rep.run_chord_s == RUN_CHORD_S and rep.limited == 0
    check(rep)
    track, rep = quantize_part(part(notes), tm, PAD, offset=0.0, rules=QuantizeRules(forced_only=True))
    assert [n.frets for n in track.notes] == [f for _, f in seq] and rep.run_chords == 0 and rep.run_chord_s == 0


def test_a_forced_strum_chord_in_a_fast_run_stays_a_strum_as_one_note():
    """The source's forced state follows the chord into its one note: the HOPO flip is worked out on the note the rule
    leaves (its top fret after another fret is a natural HOPO, so a forced strum needs the flip), not on the chord
    (which is never a natural HOPO, so the flip would be lost and the note played as a HOPO)."""
    tm = const_map(200.0)
    seq = [(4, (1,), None), (4.25, (2,), None), (4.5, (1, 3), False), (4.75, (2,), None), (5, (1,), None)]
    notes = [TimedNote(at(tm, b), f, hopo=h, hopo_forced=h is not None) for b, f, h in seq]
    track, rep = quantize_part(part(notes), tm, PAD, offset=0.0,
                               rules=QuantizeRules(forced_only=True, run_chord_s=RUN_CHORD_S))
    assert [n.frets for n in track.notes] == [(1,), (2,), (3,), (2,), (1,)] and rep.run_chords == 1
    assert play_states(track.notes, RES) == ["strum", "hopo", "strum", "hopo", "hopo"] and rep.flips == 1


@pytest.mark.parametrize("difficulty", ["expert", "hard", "medium"])
def test_a_tools_own_lower_level_is_read_against_its_own_onsets(difficulty):
    """A tool's own lower level (take_difficulties "all") meets the rule on its own notes: a chord in its own 16th run
    becomes one note on every level, and a chord between its own 8ths stays, whatever Expert's notes there are."""
    tm = const_map(200.0)
    fast = [(4, (0,)), (4.25, (1,)), (4.5, (0, 2)), (4.75, (1,)), (5, (0,))]
    slow = [(8, (0,)), (8.5, (0, 2)), (9, (1,))]
    notes = [TimedNote(at(tm, b), f) for b, f in fast + slow]
    track, rep = quantize_part(part(notes, difficulty=difficulty), tm, PAD, offset=0.0,
                               rules=QuantizeRules(run_chord_s=RUN_CHORD_S))
    assert [n.frets for n in track.notes] == [(0,), (1,), (2,), (1,), (0,), (0,), (0, 2), (1,)]
    assert rep.run_chords == 1 and rep.run_chord_s == RUN_CHORD_S


@pytest.mark.parametrize("bpm, one_note", [(126.0, True), (125.0, False)])
def test_a_chord_in_a_run_of_16ths_under_120_ms(bpm, one_note):
    """A 1/16 is 119 ms at 126 BPM, a fast run: its chord becomes one note. At 125 BPM it is 120 ms, where the human
    charts strum chords: a chord there stays, and so does a strum section of 16th-note chords."""
    tm = const_map(bpm)
    seq = [(4, (0,)), (4.25, (1,)), (4.5, (0, 2)), (4.75, (1,)), (5, (0,)),
           (8, (0, 1)), (8.25, (0, 1)), (8.5, (1, 3)), (8.75, (1, 3)), (9, (0, 1))]
    notes = [TimedNote(at(tm, b), f) for b, f in seq]
    track, rep = quantize_part(part(notes), tm, PAD, offset=0.0, rules=QuantizeRules(run_chord_s=RUN_CHORD_S))
    want = [f for _, f in seq] if not one_note else [(0,), (1,), (2,), (1,), (0,), (0, 1), (1,), (3,), (3,), (0, 1)]
    assert [n.frets for n in track.notes] == want and rep.run_chords == (4 if one_note else 0)


def test_run_chords():
    """The rule on its own: times in seconds, and 0 turns it off."""
    t = [0.0, 0.1, 0.2, 0.3, 0.5, 0.6]
    f = [(0, 1), (0, 1), (1, 2, 4), (2,), (0, 3), (1,)]
    assert run_chords(t, f, 0.12) == [(0, 1), (1,), (4,), (2,), (0, 3), (1,)]
    assert run_chords(t, f, 0.25) == [(0, 1), (1,), (4,), (2,), (3,), (1,)]
    assert run_chords(t, f, 0.0) == f and run_chords([], [], 0.12) == [] and run_chords([0.0], [(0, 1)], 1) == [(0, 1)]


@pytest.mark.parametrize("gap, kept", [(0.020, True), (0.019, False)])
def test_the_spacing_floors_are_20_ms(gap, kept):
    """An onset one millisecond under the floor is dropped and one at it is kept, before a strum (the same fret
    again) and before a HOPO (a fret change) alike. 1/16 slots fall that close only above 750 BPM, so the maps here
    are that fast: a 1/16 is `gap` (with a snapping scale under a slot, so a note keeps its 1/16)."""
    assert STRUM_SPACING_S == HOPO_SPACING_S == 0.020
    tm = const_map(60 / (4 * gap), beats=1000)
    rules = QuantizeRules(sigma_s=0.002)
    strum = [TimedNote(at(tm, 40), (0,)), TimedNote(at(tm, 40.25), (0,))]
    hopo = [TimedNote(at(tm, 80), (0,)), TimedNote(at(tm, 80.25), (1,))]
    for notes, state in ((strum, "strum"), (hopo, "hopo")):
        track, rep = quantize_part(part(notes), tm, PAD, offset=0.0, rules=rules)
        gap_s = tm.tick_to_sec(track.notes[-1].tick) - tm.tick_to_sec(track.notes[0].tick)
        if kept:
            assert len(track.notes) == 2 and rep.dropped == 0 and gap_s == pytest.approx(gap, abs=1e-6)
            assert play_states(track.notes, RES)[1] == state
        else:
            assert len(track.notes) == 1 and rep.dropped == 1
        check(rep)


# ------------------------------------------------------------------------------------------------ sustains

def gaps_ok(track, tm, difficulty="expert"):
    """No sustain ends within max(85 ms, a 1/16) of the next onset (scan-chart's badSustainGap uses 40 ms)."""
    onsets = sorted({n.tick for n in track.notes})
    for n in track.notes:
        if n.length:
            nxt = next((t for t in onsets if t > n.tick), None)
            if nxt is not None:
                end = n.tick + n.length
                assert nxt - end >= RES // 4 and tm.tick_to_sec(nxt) - tm.tick_to_sec(end) >= 0.085 - 1e-9


def test_sustains_snap_trim_and_drop():
    tm = const_map()
    notes = [
        TimedNote(at(tm, 0), (0,), end=at(tm, 1.5, 12)),    # ends on its 1/16 line
        TimedNote(at(tm, 2), (1,), end=at(tm, 3.95)),       # runs into the next note: stops a 1/16 before it
        TimedNote(at(tm, 4), (2,), end=at(tm, 4.5)),        # 0.5 beat (250 ms): under 0.75 beat, dropped
        TimedNote(at(tm, 6), (3,), end=at(tm, 6.5, -40)),   # babySustain-sized: dropped
        TimedNote(at(tm, 8), (4,), end=at(tm, 9)),
        TimedNote(at(tm, 9, 5), (0,)),                      # right at the previous sustain's end
    ]
    track, rep = quantize_part(part(notes), tm, PAD, offset=0.0)
    assert [n.length for n in track.notes] == [288, 336, 0, 0, 144, 0]
    assert rep.sustains_trimmed == 2 and rep.sustains_dropped == 2
    gaps_ok(track, tm)
    # Medium leaves a 1/8 and needs a whole beat
    track, _ = quantize_part(part(notes, difficulty="medium"), tm, PAD, offset=0.0)
    assert [n.length for n in track.notes] == [288, 288, 0, 0, 0, 0]


def test_short_sustains_at_a_fast_tempo_need_200_ms():
    tm = const_map(240.0)  # 0.75 beat = 188 ms: the 200 ms floor decides
    notes = [TimedNote(at(tm, 0), (0,), end=at(tm, 0.75)), TimedNote(at(tm, 2), (1,), end=at(tm, 3))]
    track, rep = quantize_part(part(notes), tm, PAD, offset=0.0)
    assert [n.length for n in track.notes] == [0, RES]
    assert rep.sustains_dropped == 1


# ------------------------------------------------------------------------------------------------ HOPOs

def test_the_source_hopo_states_are_reproduced():
    tm = const_map()
    seq = [  # (beat, frets, hopo as the source plays it, tap)
        (0, (0,), False, False),
        (0.25, (1,), True, False),     # a 1/16 fret change: natural HOPO here too
        (0.5, (2,), False, False),     # natural HOPO on our grid, the source strums it: flip
        (1.0, (3,), True, False),      # an 8th: natural strum, the source has a HOPO: flip
        (1.25, (3,), False, False),    # same fret: strum either way
        (1.5, (0, 1), True, False),    # forced HOPO chord: flip
        (2.0, (2,), None, False),      # unknown: natural (strum)
        (2.25, (OPEN,), None, False),  # an open note after a fret: natural HOPO
        (2.5, (4,), False, True),      # a tap: with tap_run 0 it stays a tap, no flip
        (3.0, (1,), False, False),
    ]
    notes = [TimedNote(at(tm, b, 6), f, hopo=h, tap=t) for b, f, h, t in seq]
    track, rep = quantize_part(part(notes), tm, PAD, offset=0.0, rules=QuantizeRules(tap_run=0))
    want = ["tap" if t else "hopo" if h else "strum" for _, _, h, t in seq]
    want[6], want[7] = "strum", "hopo"
    assert play_states(track.notes, RES) == want
    assert [n.flip for n in track.notes] == [False, False, True, True, False, True, False, False, False, False]
    assert rep.flips == 3 and (rep.taps_kept, rep.taps_to_hopo) == (1, 0)
    # the default tap rule: that tap is in no run of 8 fast onsets, so it plays as the natural HOPO it is here
    track, rep = quantize_part(part(notes), tm, PAD, offset=0.0)
    want[8] = "hopo"
    assert play_states(track.notes, RES) == want and not any(n.tap for n in track.notes)
    assert rep.flips == 3 and (rep.taps_kept, rep.taps_to_hopo) == (0, 1)
    natural = quantize_part(part(notes), tm, PAD, offset=0.0, rules=QuantizeRules(source_hopo=False, taps=False))
    assert natural[1].flips == 0 and not any(n.tap for n in natural[0].notes)


# ------------------------------------------------------------------------------------------------ taps

def test_fast_runs():
    """A run is at least min_onsets onsets, each at most max_gap_s after the one before: a gap of exactly 0.125 s is
    inside one, 0.1251 s ends it, and so do the part's ends."""
    assert (TAP_RUN, TAP_RUN_GAP_S) == (8, 0.125) and (RULES.tap_run, RULES.tap_run_gap_s) == (8, 0.125)
    eight = [0.4 + 0.125 * k for k in range(8)]
    assert fast_runs(eight, 8, 0.125) == [True] * 8
    assert fast_runs(eight[:7], 8, 0.125) == [False] * 7
    assert fast_runs([0.4 + 0.1251 * k for k in range(8)], 8, 0.125) == [False] * 8
    split = [0.0, 0.1, 0.2, 0.3, 0.55, 0.65, 0.75, 0.85, 0.95, 1.05]   # 4 and 6: neither is 8
    assert fast_runs(split, 8, 0.125) == [False] * 10
    nine = [0.1 * k for k in range(9)] + [2.0]
    assert fast_runs(nine, 8, 0.125) == [True] * 9 + [False]
    assert fast_runs([0.0, 1.0], 0, 0.125) == fast_runs([0.0, 1.0], 1, 0.125) == [True, True]
    assert fast_runs([], 8, 0.125) == []


def _taps_part(groups):
    """Single notes on a map's seconds: groups of (first second, offsets in seconds from it, tapped indices); frets
    cycle G R Y B in each group, and the source plays every note as a strum (hopo False, not forced)."""
    notes, names = [], {}
    for name, (t0, steps, tapped) in groups.items():
        for i, dt in enumerate(steps):
            notes.append(TimedNote(t0 + dt - PAD + 0.004, (i % 4,), hopo=False, tap=i in tapped))
            names[notes[-1].time] = (name, i)
    return part(notes), names


def _states_by_group(track, tm, names):
    """{group: [play state of each of its notes]} (names: _taps_part's)."""
    states = dict(zip(sorted(n.tick for n in track.notes), play_states(track.notes, RES)))
    out = {}
    for t, (name, i) in sorted(names.items()):
        out.setdefault(name, []).append(states[round(tm.sec_to_tick(t + PAD - 0.004))])
    return out


@pytest.mark.parametrize("bpm, rules", [(150.0, QuantizeRules()), (75.0, QuantizeRules(straight=8, triplet=6))],
                         ids=["first grid", "halved grid"])
def test_a_tap_is_kept_only_inside_a_run_of_8_fast_onsets(bpm, rules):
    """At 150 BPM a 1/16 is 0.1 s (on a halved grid at 75 BPM, its 1/32): 8 taps on 16ths in a row stay taps; 7 do
    not, nor 8 with one gap of an 8th (0.2 s); 2 taps inside a run of 10 16ths stay, since the run counts every onset,
    tapped or not. The others play as HOPOs. tap_run 0 keeps every tap (the rule until M7-02)."""
    tm = const_map(bpm)
    s16 = 0.1
    groups = {"eight": (2.0, [k * s16 for k in range(8)], range(8)),
              "seven": (4.0, [k * s16 for k in range(7)], range(7)),
              "gapped": (6.0, [k * s16 for k in (0, 1, 2, 3, 5, 6, 7, 8)], range(8)),
              "ten": (9.0, [k * s16 for k in range(10)], (3, 4))}
    p, names = _taps_part(groups)
    track, rep = quantize_part(p, tm, PAD, offset=0.0, rules=rules)
    assert rep.notes_out == 33 and rep.dropped == rep.merged == 0
    got = _states_by_group(track, tm, names)
    assert got["eight"] == ["tap"] * 8
    assert got["seven"] == ["hopo"] * 7 and got["gapped"] == ["hopo"] * 8
    assert [s == "tap" for s in got["ten"]] == [i in (3, 4) for i in range(10)]
    assert (rep.taps_kept, rep.taps_to_hopo) == (10, 15)
    check(rep)
    old, rep = quantize_part(p, tm, PAD, offset=0.0, rules=replace(rules, tap_run=0))
    assert sum(n.tap for n in old.notes) == 25 and (rep.taps_kept, rep.taps_to_hopo) == (25, 0)
    assert [(n.tick, n.frets) for n in old.notes] == [(n.tick, n.frets) for n in track.notes]


@pytest.mark.parametrize("hopo", ["forced", "source", "natural"])
def test_tap_bursts_play_as_hopos(hopo):
    """Bursts of 2, 3 and 4 taps are no fast run: each plays as a HOPO under every HOPO rule,
    whatever state the source gave it: natural on our grid where it is one (a fret change a 16th after the note
    before), flipped to one where it is not (a burst's first note after a rest, a same-fret repeat, a chord).
    reduce.hopo_states reads them as HOPOs, as it read the taps, so the levels reduced from Expert are unchanged (at
    80 BPM Hard keeps two of them as HOPOs). Every source note's HOPO state alternates, its ends strummed."""
    tm = const_map(80.0)
    rules = {"forced": QuantizeRules(forced_only=True), "source": QuantizeRules(),
             "natural": QuantizeRules(source_hopo=False)}[hopo]
    beat = 0.75
    seq = [  # (beat, frets, tap)
        (5.0, (0,), False),
        (6.0, (2,), True), (6.25, (3,), True),                                       # 2: flip, natural
        (8.0, (1,), True), (8.25, (1,), True), (8.5, (0, 2), True),                  # 3: flip, repeat, chord
        (10.0, (4,), True), (10.25, (3,), True), (10.5, (2,), True), (10.75, (OPEN,), True),  # 4: flip, natural
        (12.0, (1,), False),
    ]
    notes = [TimedNote(b * beat - PAD + 0.004, f, hopo=bool(i % 2), tap=t) for i, (b, f, t) in enumerate(seq)]
    notes[0], notes[-1] = (replace(n, hopo=False) for n in (notes[0], notes[-1]))
    track, rep = quantize_part(part(notes), tm, PAD, offset=0.0, rules=rules)
    assert [n.tick for n in track.notes] == [round(b * RES) for b, _, _ in seq]
    assert play_states(track.notes, RES) == ["strum"] + ["hopo"] * 9 + ["strum"]
    assert not any(n.tap for n in track.notes)
    assert [n.flip for n in track.notes][1:10] == [True, False, True, True, True, True, False, False, False]
    states = hopo_states(track.notes, RES)
    assert [states[n.tick] for n in track.notes] == [False] + [True] * 9 + [False]
    assert (rep.taps_kept, rep.taps_to_hopo) == (0, 9)
    old, _ = quantize_part(part(notes), tm, PAD, offset=0.0, rules=replace(rules, tap_run=0))
    assert sum(n.tap for n in old.notes) == 9 and hopo_states(old.notes, RES) == states
    reduced = reduce_track(Track("Expert", "Single", track.notes), tm)
    assert reduced == reduce_track(Track("Expert", "Single", old.notes), tm)
    assert [play_states(t.notes, RES).count("hopo") for t in reduced] == [2, 0, 0]


# ------------------------------------------------------------------------------------------------ drums

def test_drum_lanes():
    tm = const_map()
    hits = [
        TimedHit(at(tm, 0), 0), TimedHit(at(tm, 0, 10), 0, double_kick=True),  # 1x and 2x kick: one 1x kick
        TimedHit(at(tm, 0), 2, cymbal=True), TimedHit(at(tm, 0, -12), 2),      # hi-hat and yellow tom: tom moves
        TimedHit(at(tm, 1), 1, accent=True), TimedHit(at(tm, 1, 3), 1),        # same pad twice: one accented snare
        TimedHit(at(tm, 2), 1), TimedHit(at(tm, 2, 4), 3, cymbal=True),        # four hands: two stay
        TimedHit(at(tm, 2, -20), 4, cymbal=True), TimedHit(at(tm, 2, 15), 3),
        TimedHit(at(tm, 3), 0, double_kick=True), TimedHit(at(tm, 3), 1, ghost=True),
    ]
    track, rep = quantize_part(part(hits, "drums"), tm, PAD, offset=0.0)
    got = [(n.tick, n.pad, n.cymbal, n.double_kick, n.accent, n.ghost) for n in track.notes]
    assert got == [
        (0, 0, False, False, False, False), (0, 2, True, False, False, False), (0, 3, False, False, False, False),
        (RES, 1, False, False, True, False),
        (2 * RES, 1, False, False, False, False), (2 * RES, 3, True, False, False, False),
        (3 * RES, 0, False, True, False, False), (3 * RES, 1, False, False, False, True),
    ]
    assert rep.merged == 2 and rep.limited == 1 and rep.dropped == 2
    check(rep)
    # below Expert the 2x kick goes; on Easy a kick under two hands goes too
    hard, rep = quantize_part(part(hits, "drums", "hard"), tm, PAD, offset=0.0)
    assert not any(n.double_kick for n in hard.notes) and rep.dropped == 4  # both 2x kicks and two hands
    easy, _ = quantize_part(part(hits, "drums", "easy"), tm, PAD, offset=0.0)
    assert [(n.tick, n.pad) for n in easy.notes if n.tick == 0] == [(0, 2), (0, 3)]


# ------------------------------------------------------------------------------------------------ spans

def covered(phrase_tick, phrase_len, ticks):
    """Notes inside a phrase as scan-chart counts them: tick <= t < tick + length."""
    return [t for t in ticks if phrase_tick <= t < phrase_tick + max(phrase_len, 1)]


def test_spans_cover_the_same_notes():
    tm = const_map()
    rng = np.random.default_rng(6)
    pos = [b + h for b in range(32) for h in (0, 0.5)]
    dev = {p: rng.uniform(-24, 24) for p in pos}
    notes = [TimedNote(at(tm, p, dev[p]), (int(p) % 4,)) for p in pos]
    t = {p: n.time for p, n in zip(pos, notes)}
    sp = [TimedSpan(t[4], t[7.5] + 0.001),            # starts on its first note, ends just after its last
          TimedSpan(t[12] - 0.2, t[16]),              # wide start; ends at the next note (half-open)
          TimedSpan(t[20.5] + 0.01, t[21] - 0.01)]    # holds no note: dropped
    solos = [TimedSpan(t[24], t[28] + 0.001)]         # 24 .. 28 inclusive
    track, rep = quantize_part(part(notes, star_power=sp, solos=solos), tm, PAD, offset=0.0)
    ticks = [n.tick for n in track.notes]
    phrases = [p for p in track.phrases if p.kind == STAR_POWER]
    assert len(phrases) == 2 and rep.spans_dropped == 1
    assert covered(phrases[0].tick, phrases[0].length, ticks) == [round(p * RES) for p in pos if 4 <= p <= 7.5]
    assert covered(phrases[1].tick, phrases[1].length, ticks) == [round(p * RES) for p in pos if 12 <= p < 16]
    (a, b), = track.solos
    assert [k for k in ticks if a <= k <= b] == [round(p * RES) for p in pos if 24 <= p <= 28]


def test_drum_fills_and_star_power():
    tm = const_map()
    hits = [TimedHit(at(tm, b / 2, 8), 1 if b % 2 else 0) for b in range(64)]
    fill = TimedSpan(at(tm, 12), at(tm, 16, 30))  # ends on the beat-16 kick, which sits 8 ms late
    sp = TimedSpan(at(tm, 20), at(tm, 24))
    track, rep = quantize_part(part(hits, "drums", star_power=[sp], activation=[fill]), tm, PAD, offset=0.0)
    ticks = sorted({n.tick for n in track.notes})
    (act,) = [p for p in track.phrases if p.kind == DRUM_ACTIVATION]
    (star,) = [p for p in track.phrases if p.kind == STAR_POWER]
    assert covered(act.tick, act.length, ticks) == [k * 96 for k in range(24, 33)]
    assert covered(star.tick, star.length, ticks) == [k * 96 for k in range(40, 48)]


# ------------------------------------------------------------------------------------------------ song

def test_quantize_song_uses_one_offset_per_instrument():
    tm = const_map()
    rng = np.random.default_rng(7)
    pos = rock_pattern(200)
    expert = [TimedNote(at(tm, p, 28 + rng.normal(0, 6)), (int(p) % 5,)) for p in pos]
    easy = [TimedNote(at(tm, p, 28 + rng.normal(0, 6)), (0,)) for p in pos[::8]]
    drums = [TimedHit(at(tm, p, -12 + rng.normal(0, 4)), 0) for p in pos]
    song = TimedSong("test", {("guitar", "expert"): part(expert), ("guitar", "easy"): part(easy, difficulty="easy"),
                              ("drums", "expert"): part(drums, "drums")})
    out = quantize_song(song, tm, PAD)
    assert list(out) == [("guitar", "expert"), ("guitar", "easy"), ("drums", "expert")]
    g, e, d = (out[k][1] for k in out)
    assert g.offset == pytest.approx(0.028, abs=0.002) and e.offset == g.offset
    assert d.offset == pytest.approx(-0.012, abs=0.002)
    assert quantize_song(song, tm, PAD, offsets={"guitar": 0.0})[("guitar", "easy")][1].offset == 0.0
    # deterministic, and the tracks write as a .chart
    again = quantize_song(song, tm, PAD)
    assert all(again[k][0] == out[k][0] for k in out)
    chart = Chart(SongInfo("t", "a"), tm, [], [t for t, _ in out.values()])
    assert "[EasySingle]" in write_chart(chart)


def test_an_empty_part_and_a_note_before_tick_zero():
    tm = const_map()
    track, rep = quantize_part(part([], star_power=[TimedSpan(1.0, 2.0)]), tm, PAD)
    assert track.notes == [] and track.phrases == [] and rep.spans_dropped == 1
    track, rep = quantize_part(part([TimedNote(-PAD - 0.2, (0,)), TimedNote(at(tm, 4), (1,))]), tm, PAD, offset=0.0)
    assert [n.tick for n in track.notes] == [4 * RES] and rep.dropped == 1
    check(rep)


def test_the_shared_line_rule_moves_nothing_on_the_other_grids():
    """quantize's shared-line rule (an off-beat onset whose straight and triplet slots are one line leans triplet,
    M6-06) can only act where a grid's two slot sets share an off-beat line: the halved grid's 8/6 at its midpoint.
    On the 16ths and 8th-note triplets (4/3), a doubled grid's lyric slots (2/3) and its bass (2/0) no off-beat
    position has one line for both, and a dense made-up part of every figure, jittered, lands where it did."""
    for s, n in ((4, 3), (2, 3), (8, 6)):
        r = np.arange(1, 10 * RES) / 10 - RES / (2 * s)  # every position in a beat, from half a slot early
        ks, kt = np.floor(r * s / RES + 0.5), np.floor(r * n / RES + 0.5)
        shared = sorted({float(k / s) for k in ks[(ks != 0) & (ks * n == kt * s)]})
        assert shared == ([0.5] if (s, n) == (8, 6) else []), (s, n)
    figures = [[0, 0.5], [0, 0.25, 0.5, 0.75], [0, 1 / 3, 2 / 3], [0, 0.75], [0, 2 / 3], [0, 0.5, 0.75], [0]]
    pos = [b + f for b in range(120) for f in figures[(b // 2) % len(figures)]]
    want = {(4, 3): [round(p * RES) for p in pos]}  # the 8th-note triplet beats and the swung ones go triplet
    for bpm in (95.0, 142.0, 180.0):
        tm = const_map(bpm)
        ticks, rep = snapped(tm, pos, jitter_ms=10, seed=int(bpm))
        assert ticks == want[(4, 3)] and rep.triplet_notes == sum(t % (RES // 4) != 0 for t in ticks) > 40, bpm
    eighths = [b + h for b in range(120) for h in ((0, 0.5) if b % 3 else (0, 1 / 3, 2 / 3))]
    for rules, octave_ok in ((QuantizeRules(straight=2, triplet=3), True), (QuantizeRules(straight=2, triplet=0),
                                                                             False)):
        ticks, rep = snapped(const_map(200.0), eighths, jitter_ms=6, seed=9, rules=rules)
        if octave_ok:
            assert ticks == [round(p * RES) for p in eighths] and rep.triplet_notes == 2 * 40
        else:
            assert rep.triplet_notes == 0 and all(t % (RES // 2) == 0 for t in ticks)
