"""Difficulty reductions on small synthetic parts: Clone Hero's forbidden notes never appear, the onset ladder is nested
and strictly decreasing, the shares of Expert onsets land in their bands, and the 5-fret and drum rules hold."""
import random

import pytest

from songcharter.chart import (DRUM_ACTIVATION, OPEN, STAR_POWER, Chart, DrumHit, FretNote, Phrase, SongInfo, Track,
                               write_chart)
from songcharter.reduce import (FRET_BANDS, check_reductions, hopo_states, onset_ticks, reduce_chart, reduce_level,
                                reduce_track)
from songcharter.tempo import Tempo, TempoMap

RES = 192
M = 4 * RES  # one 4/4 measure
SHAPES = [(0,), (1,), (2,), (3,), (4,), (OPEN,), (0, 1), (0, 2), (1, 3), (2, 4), (0, 3), (0, 4), (1, 4), (0, 2, 4),
          (1, 2, 3), (0, 1, 2), (2, 3, 4)]


def tempo(bpm=142):
    return TempoMap(RES, [Tempo(0, round(bpm * 1000))])


def eighths(measures=40, start=4, frets=lambda i: ((0,), (2,), (1,), (3,))[i % 4]):
    """Continuous 8th notes, one measure after another."""
    return [FretNote(start * M + i * RES // 2, frets(i)) for i in range(measures * 8)]


def random_part(seed, measures=48, chords=True):
    """Expert-like 5-fret part: 8ths, 16th bursts, 8th triplets, rests, chords, opens, taps, flips and sustains."""
    rng = random.Random(seed)
    notes, t = [], 4 * M
    end = (4 + measures) * M
    while t < end:
        kind = rng.random()
        step = RES // 4 if kind < 0.25 else RES // 3 if kind < 0.35 else RES // 2 if kind < 0.85 else RES
        for _ in range(rng.choice((2, 3, 4, 6))):
            if t >= end:
                break
            frets = rng.choice(SHAPES if chords else [(0,), (1,), (2,), (3,), (4,), (OPEN,)])
            length = rng.choice((0, 0, 0, RES // 2, RES, 2 * RES)) if step >= RES // 2 else 0
            notes.append(FretNote(t, frets, length, flip=rng.random() < 0.1, tap=rng.random() < 0.05))
            t += max(step, length + RES // 4) if length else step
        t += rng.choice((0, 0, RES // 2, RES))
    return notes


def fret_track(notes, instrument="Single", sp=(), solos=()):
    return Track("Expert", instrument, notes, [Phrase(a, b, STAR_POWER) for a, b in sp], list(solos))


def shares(levels, expert):
    n = len(onset_ticks(expert))
    return [len(onset_ticks(t)) / n for t in levels]


def errors(issues):
    return [i for i in issues if i.error]


# ------------------------------------------------------------------------------------------------ 5-fret

@pytest.mark.parametrize("seed", range(12))
@pytest.mark.parametrize("bpm", [90, 142, 180])
def test_forbidden_notes_never_appear(seed, bpm):
    tm = tempo(bpm)
    ex = fret_track(random_part(seed), "DoubleBass" if seed % 3 == 0 else "Single",
                    sp=[(8 * M, M), (20 * M, M), (33 * M, 2 * M)], solos=[(24 * M, 30 * M)])
    hard, medium, easy = reduce_track(ex, tm)
    for n in hard.notes:
        assert len(n.frets) <= 2 and not {0, 4} <= set(n.frets)
    for n in medium.notes:
        assert len(n.frets) <= 2 and 4 not in n.frets and not {0, 3} <= set(n.frets)
    for n in easy.notes:
        assert len(n.frets) == 1 and n.frets[0] in (0, 1, 2)
    for tr in (hard, medium, easy):
        assert not any(OPEN in n.frets or n.tap for n in tr.notes)
    issues = check_reductions([ex, hard, medium, easy], tm)
    assert errors(issues) == []
    write_chart(Chart(SongInfo("t", "a"), tm, [], [ex, hard, medium, easy]))  # every note is writable


@pytest.mark.parametrize("seed", range(8))
def test_onset_ladder_is_nested_and_strictly_decreasing(seed):
    tm = tempo(142)
    ex = fret_track(random_part(seed))
    ladder = [ex] + reduce_track(ex, tm)
    counts = [len(onset_ticks(t)) for t in ladder]
    assert counts == sorted(counts, reverse=True) and len(set(counts)) == 4
    for upper, lower in zip(ladder, ladder[1:]):
        assert set(onset_ticks(lower)) <= set(onset_ticks(upper))


def test_bass_keeps_a_denser_ladder_than_guitar():
    """DESIGN 9 Q19: bass thins toward denser targets than guitar, with bass Hard still under the 0.90 error. The
    targets only stop the thinning sooner: each level's minimum gap (its time floor) still binds first, so at 142 BPM
    continuous 8ths keep quarters on Medium and half notes on Easy either way."""
    tm = tempo(142)
    gs, bs = [], []
    for seed in range(8):
        for chords in (False, True):
            notes = random_part(seed, chords=chords)
            gs.append(shares(reduce_track(fret_track(notes), tm), fret_track(notes)))
            bass_ex = fret_track(notes, "DoubleBass")
            bass_levels = reduce_track(bass_ex, tm)
            bs.append(shares(bass_levels, bass_ex))
            assert bs[-1][0] < 0.90 and errors(check_reductions([bass_ex] + bass_levels, tm)) == []
    mean = lambda rows, k: sum(r[k] for r in rows) / len(rows)  # noqa: E731
    assert mean(bs, 0) > mean(gs, 0) + 0.02 and mean(bs, 1) > mean(gs, 1)
    assert all(b[2] >= g[2] - 0.01 for b, g in zip(bs, gs))  # Easy: the 2-beat bass sustain floor protects fewer notes
    ex = eighths()
    g = shares(reduce_track(fret_track(ex), tm), fret_track(ex))
    b = shares(reduce_track(fret_track(ex, "DoubleBass"), tm), fret_track(ex, "DoubleBass"))
    assert b[0] > g[0] + 0.1 and b[1:] == g[1:] == [0.5, 0.25], (g, b)


def test_drums_hard_keeps_8th_note_kicks():
    """DESIGN 9 Q18: 8th-note kicks survive on Hard (all four Harmonix test Hards have them); Medium keeps 2 beats."""
    tm = tempo(142)
    hits = []
    for m in range(4, 36):
        for s in range(8):  # 8th notes
            t = m * M + s * RES // 2
            hits.append(DrumHit(t, 2, cymbal=True))
            if s in (0, 3, 4, 7):  # a busy kick pattern with 8th-note pairs
                hits.append(DrumHit(t, 0))
            if s in (2, 6):
                hits.append(DrumHit(t, 1))
    ex = drum_track(hits)
    hard, medium, _ = reduce_track(ex, tm)
    kicks = lambda tr: sorted(t for t, hs in groups(tr).items() if any(h.pad == 0 for h in hs))  # noqa: E731
    hk = kicks(hard)
    assert min(b - a for a, b in zip(hk, hk[1:])) == RES // 2
    assert len(hk) > 0.75 * len(kicks(ex))
    mk = kicks(medium)
    assert min(b - a for a, b in zip(mk, mk[1:])) >= 2 * RES
    assert errors(check_reductions([ex, hard, medium], tm)) == []


def test_continuous_8ths_lose_the_rbn_positions_first():
    """Hard drops each measure's last 8th and the first half's last 8th (every fourth 8th per half measure);
    Medium is quarter notes and Easy half notes at 142 BPM."""
    tm = tempo(142)
    ex = fret_track(eighths())
    hard, medium, easy = reduce_track(ex, tm)
    last = 43 * M  # the part's last measure: its last note has no neighbour after it, so it stays
    assert {t % M for t in onset_ticks(hard) if t < last} == {0, 96, 192, 384, 480, 576}
    assert {t % M for t in onset_ticks(medium) if t < last} == {0, 192, 384, 576}
    assert {t % M for t in onset_ticks(easy) if t < last} == {0, 384}
    h, m, e = shares([hard, medium, easy], ex)
    assert 0.70 <= h <= 0.80 and 0.45 <= m <= 0.55 and 0.23 <= e <= 0.30


@pytest.mark.parametrize("bpm", [90, 120, 142, 170])
def test_share_bands(bpm):
    """8th-note and Expert-like parts land in DESIGN 2.11's bands; 16th-heavy parts are thinner (Hard plays them as
    8ths), but Hard always stays under 0.9 of Expert and the ladder strictly decreases."""
    tm = tempo(bpm)
    sixteenths = [FretNote(4 * M + i * RES // 4, ((0,), (1,), (2,), (1,))[i % 4]) for i in range(40 * 16)]
    mixed = eighths(20) + [FretNote(24 * M + i * RES // 4, ((2,), (3,))[i % 2]) for i in range(20 * 16)]
    for i, notes in enumerate((eighths(), random_part(1), random_part(2), random_part(5), sixteenths, mixed)):
        ex = fret_track(notes)
        h, m, e = shares(reduce_track(ex, tm), ex)
        assert h < 0.9  # the critique's hard limit
        assert e < m < h < 1
        if i == 0 or 0 < i < 4 and bpm >= 120:  # at 90 BPM Medium may keep 8ths and Easy quarters
            for share, level in ((h, "Hard"), (m, "Medium"), (e, "Easy")):
                lo, hi = FRET_BANDS[level]
                assert lo <= share <= hi, (level, share)


def test_slow_16ths_pass_through_a_gallop_on_hard():
    """At 90 BPM a 16th lasts 167 ms, long enough for Hard: the ladder drops the 16th after each 8th first."""
    tm = tempo(90)
    ex = fret_track([FretNote(4 * M + i * RES // 4, ((0,), (1,), (2,), (3,))[i % 4]) for i in range(32 * 16)])
    hard = reduce_track(ex, tm)[0]
    assert {t % RES for t in onset_ticks(hard)[:-1]} == {0, 48, 96}  # the last note has no neighbour after it


def test_hard_has_no_16ths_at_142_and_medium_no_8ths():
    tm = tempo(142)
    ex = fret_track(random_part(3))
    hard, medium, easy = reduce_track(ex, tm)
    for tr, gap in ((hard, RES // 2), (medium, RES), (easy, 2 * RES)):
        on = onset_ticks(tr)
        assert min(b - a for a, b in zip(on, on[1:])) >= gap


def test_syncopation_and_sustained_notes_survive():
    """1, 2-and (held over 3), 4: the off-beat note has no neighbour within a beat, so no level drops it for being
    weak; a sustained off-beat note beats a plain downbeat on Medium."""
    tm = tempo(142)
    notes = []
    for m in range(4, 36):
        b = m * M
        notes += [FretNote(b, (0,)), FretNote(b + 288, (2,), RES), FretNote(b + 576, (1,)), FretNote(b + 672, (2,))]
    ex = fret_track(notes)
    hard, medium, easy = reduce_track(ex, tm)
    assert all(m * M + 288 in onset_ticks(hard) for m in range(4, 36))
    assert all(m * M + 288 in onset_ticks(medium) for m in range(4, 36))


def test_sustains_trimmed_kept_or_dropped_never_extended():
    tm = tempo(142)
    notes = []
    for m in range(4, 30):
        b = m * M
        notes += [FretNote(b, (0,), 3 * RES), FretNote(b + 3 * RES, (2,))]  # held up to the next note
    ex = fret_track(notes)
    hard, medium, easy = reduce_track(ex, tm)
    for tr, gap in ((hard, RES // 4), (medium, RES // 2), (easy, RES)):
        on = onset_ticks(tr)
        for n in tr.notes:
            src = next(x for x in ex.notes if x.tick == n.tick)
            assert n.length <= src.length
            nxt = next((t for t in on if t > n.tick), None)
            if n.length and nxt is not None:
                assert nxt - (n.tick + n.length) >= gap
    assert all(n.length == 3 * RES - RES // 4 for n in hard.notes if n.tick % M == 0)  # ends a 16th before the note
    assert all(n.length == 3 * RES - RES // 2 for n in medium.notes if n.tick % M == 0)
    medium_length = {n.tick: n.length for n in medium.notes}
    assert all(0 < n.length <= medium_length[n.tick] for n in easy.notes if n.tick % M == 0)  # never longer
    # a sustain shorter than 3/4 beat goes on Hard, and one shorter than a beat on Medium
    short = fret_track([FretNote(4 * M + i * 2 * RES, (i % 3,), 115) for i in range(64)]
                       + [FretNote(4 * M + i * 2 * RES + RES, (2,), 170) for i in range(64)])
    hard, medium, _ = reduce_track(short, tm)
    src = {n.tick: n.length for n in short.notes}
    assert all(n.length == 0 for n in hard.notes if src[n.tick] == 115)
    assert all(n.length == 0 or 3 * RES // 4 <= n.length <= 170 for n in hard.notes)
    assert any(n.length for n in hard.notes) and all(n.length == 0 for n in medium.notes)


def test_hopos_lower_levels_strum_more():
    """At 90 BPM Hard keeps some 16ths: a natural HOPO stays only where Expert has one between the same two notes.
    Medium and Easy strum everything; no taps below Expert."""
    tm = tempo(90)
    notes = []
    for m in range(4, 36):
        b = m * M
        notes += [FretNote(b + i * RES // 4, ((0,), (1,), (2,), (1,))[i % 4]) for i in range(8)]  # HOPO run
        notes += [FretNote(b + 2 * RES + i * RES // 4, ((2,), (3,))[i % 2], flip=True) for i in range(4)]  # strums
        notes += [FretNote(b + 3 * RES, (4,), tap=True), FretNote(b + 3 * RES + RES // 2, (3,), tap=True)]
    ex = fret_track(notes)
    hard, medium, easy = reduce_track(ex, tm)
    ex_state = hopo_states(ex.notes, RES)
    hard_state = hopo_states(hard.notes, RES)
    ex_ticks = onset_ticks(ex)
    hard_ticks = onset_ticks(hard)
    assert any(hard_state.values())
    for i, t in enumerate(hard_ticks):
        if hard_state[t]:
            assert ex_state[t] and ex_ticks[ex_ticks.index(t) - 1] == hard_ticks[i - 1]
    for tr in (medium, easy):
        assert not any(hopo_states(tr.notes, RES).values())
        assert not any(n.tap for n in tr.notes)
    assert errors(check_reductions([ex, hard, medium, easy], tm)) == []


def test_contour_kept_when_lanes_are_cut():
    """A five-lane riff squeezed onto four and three lanes keeps every step's direction."""
    tm = tempo(142)
    riff = [1, 2, 3, 4, 3, 2, 1, 2]  # R Y B O B Y R Y, one per beat
    notes = [FretNote(4 * M + i * RES, (riff[i % len(riff)],)) for i in range(32 * 4)]
    ex = fret_track(notes)
    ex_lane = {n.tick: n.frets[0] for n in ex.notes}
    medium = reduce_level(reduce_level(ex, "Hard", tm), "Medium", tm, expert=ex)
    on = onset_ticks(medium)
    lane = {n.tick: n.frets[0] for n in medium.notes}
    sign = lambda x: (x > 0) - (x < 0)  # noqa: E731
    assert all(sign(lane[b] - lane[a]) == sign(ex_lane[b] - ex_lane[a]) for a, b in zip(on, on[1:]))
    assert max(lane.values()) <= 3


def test_open_notes_become_green_and_chords_simplify():
    tm = tempo(142)
    notes = [FretNote(4 * M + i * RES, f) for i, f in enumerate([(OPEN,), (0, 4), (0, 2, 4), (1, 2, 3), (0, 3)] * 24)]
    ex = fret_track(notes)
    hard, medium, easy = reduce_track(ex, tm)
    by = {n.tick: n.frets for n in hard.notes}
    for n in ex.notes:
        if n.tick in by:
            if n.frets == (OPEN,):
                assert by[n.tick] == (0,)
            elif len(n.frets) == 3:
                assert len(by[n.tick]) == 2
    assert all(len(n.frets) == 1 for n in easy.notes)
    assert errors(check_reductions([ex, hard, medium, easy], tm)) == []


def test_star_power_and_solos_keep_a_note():
    """A phrase over a weak 16th that every level would drop still gets a note on every level."""
    tm = tempo(142)
    notes = eighths(40)
    notes += [FretNote(10 * M + 3 * RES + 3 * RES // 4, (4,))]  # a lone 16th, alone in its phrase
    notes = sorted(notes, key=lambda n: n.tick)
    ex = fret_track(notes, sp=[(10 * M + 3 * RES + 3 * RES // 4, RES // 8)], solos=[(20 * M + 96, 20 * M + 100)])
    levels = reduce_track(ex, tm)
    for tr in levels:
        assert any(10 * M + 3 * RES + 3 * RES // 4 <= t < 10 * M + 4 * RES for t in onset_ticks(tr))
        assert any(20 * M + 96 <= t <= 20 * M + 100 for t in onset_ticks(tr))
        assert tr.phrases == ex.phrases and tr.solos == ex.solos
    assert errors(check_reductions([ex] + levels, tm)) == []


@pytest.mark.parametrize("seed", range(6))
def test_fret_reduction_is_idempotent_and_deterministic(seed):
    tm = tempo([90, 142, 180][seed % 3])
    ex = fret_track(random_part(seed), sp=[(8 * M, M), (20 * M, M)], solos=[(24 * M, 30 * M)])
    levels = reduce_track(ex, tm)
    assert levels == reduce_track(ex, tm)
    for tr in levels:
        assert reduce_level(tr, tr.difficulty, tm, expert=ex) == tr


# ------------------------------------------------------------------------------------------------ drums

def rock_beat(measures=40, start=4, fill_every=4):
    """8th hi-hats, kicks on 1, 3 and 3-and, snare on 2 and 4, a crash on each 4-bar downbeat and a 16th fill on
    snare and toms ending every fourth bar."""
    hits = []
    for m in range(start, start + measures):
        b = m * M
        if fill_every and (m - start) % fill_every == fill_every - 1:
            for s in range(16):
                hits.append(DrumHit(b + s * 48, (1, 1, 2, 3)[s // 4]))
                if s % 4 == 0:
                    hits.append(DrumHit(b + s * 48, 0))
            continue
        for e in range(8):
            t = b + e * 96
            crash = e == 0 and (m - start) % fill_every == 0 if fill_every else e == 0
            hits.append(DrumHit(t, 4, cymbal=True) if crash else DrumHit(t, 2, cymbal=True))
            if e in (0, 4, 5):
                hits.append(DrumHit(t, 0))
            if e in (2, 6):
                hits.append(DrumHit(t, 1))
    return hits


def drum_track(hits, sp=(), fills=()):
    return Track("Expert", "Drums", hits, [Phrase(a, b, STAR_POWER) for a, b in sp]
                 + [Phrase(a, b, DRUM_ACTIVATION) for a, b in fills])


def groups(track):
    out = {}
    for h in track.notes:
        out.setdefault(h.tick, []).append(h)
    return out


def random_drums(seed, measures=40):
    rng = random.Random(seed)
    hits = []
    for m in range(4, 4 + measures):
        for s in range(16):
            t = m * M + s * 48
            if rng.random() < (0.9 if s % 2 == 0 else 0.35):
                pads = rng.sample([1, 2, 3, 4], rng.choice((1, 1, 2)))
                for p in pads:
                    hits.append(DrumHit(t, p, cymbal=p > 1 and rng.random() < 0.6, accent=rng.random() < 0.05,
                                        ghost=p == 1 and rng.random() < 0.1))
                if rng.random() < 0.1 and 2 not in pads:  # a cymbal and a tom on one pad
                    hits += [DrumHit(t, 2, cymbal=True), DrumHit(t, 2)]
            if rng.random() < (0.5 if s % 4 == 0 else 0.15):
                hits.append(DrumHit(t, 0))
            if rng.random() < 0.08:
                hits.append(DrumHit(t, 0, double_kick=True))
    return hits


@pytest.mark.parametrize("seed", range(10))
@pytest.mark.parametrize("bpm", [95, 142, 175])
def test_drums_forbidden_hits_never_appear(seed, bpm):
    tm = tempo(bpm)
    ex = drum_track(random_drums(seed), sp=[(8 * M, M), (21 * M, M)], fills=[(15 * M, M), (31 * M, M)])
    levels = reduce_track(ex, tm, sections=[0, 20 * M])
    hard, medium, easy = levels
    for tr in levels:
        for t, hs in groups(tr).items():
            pads = [h.pad for h in hs]
            assert len(pads) == len(set(pads))
            assert not any(h.double_kick for h in hs)
            assert len([p for p in pads if p]) <= 2
            if tr is hard and 0 in pads:
                assert len(pads) <= 2  # no three-limb hits
            if tr is medium and 0 in pads:
                assert len(pads) <= 2
            if tr is easy and 0 in pads:
                assert pads == [0]
            if tr is easy and len(pads) == 2:
                assert 1 in pads  # two hands only as the snare plus one
    assert errors(check_reductions([ex] + levels, tm)) == []
    write_chart(Chart(SongInfo("t", "a"), tm, [], [ex] + levels))


def test_drums_rock_beat_at_142():
    """Medium: no right-hand 8ths at 140 BPM or more, kicks on beats 2 beats apart; Easy: kick alone or hands only;
    the ladder strictly decreasing with Harmonix-like shares."""
    tm = tempo(142)
    ex = drum_track(rock_beat())
    hard, medium, easy = reduce_track(ex, tm, sections=[0, 20 * M], loudness=[-30.0, -20.0])
    counts = [len(onset_ticks(t)) for t in (ex, hard, medium, easy)]
    assert counts == sorted(counts, reverse=True) and len(set(counts)) == 4
    g = groups(medium)
    for t, hs in g.items():
        if any(h.cymbal and h.pad in (2, 3) for h in hs):
            assert t % RES == 0
    kicks = sorted(t for t, hs in g.items() if any(h.pad == 0 for h in hs))
    assert all(t % RES == 0 for t in kicks) and min(b - a for a, b in zip(kicks, kicks[1:])) >= 2 * RES
    hard_kicks = sorted(t for t, hs in groups(hard).items() if any(h.pad == 0 for h in hs))
    assert min(b - a for a, b in zip(hard_kicks, hard_kicks[1:])) >= RES // 2  # 8th-note kicks (DESIGN 9 Q18)
    eg = groups(easy)
    quiet = [hs for t, hs in eg.items() if t < 20 * M]
    loud = [hs for t, hs in eg.items() if t >= 20 * M]
    assert any(h.pad == 0 for hs in quiet for h in hs) and not any(h.cymbal and h.pad in (2, 3)
                                                                   for hs in quiet for h in hs)
    assert not any(h.pad == 0 for hs in loud for h in hs)
    h, m, e = shares([hard, medium, easy], ex)
    assert 0.62 <= h <= 0.98 and 0.39 <= m <= 0.85 and 0.30 <= e <= 0.71
    assert errors(check_reductions([ex, hard, medium, easy], tm)) == []


def ride_groove(measures=32, start=4, snare_8ths_every=4):
    """Ride 8ths with kicks on 1 and 3, the snare on 2 and 4 (no ride over it) and a ghost snare on the last 16th
    before each; every fourth bar the snare on 4 is a pair of snare 8ths."""
    hits = []
    for m in range(start, start + measures):
        b = m * M
        for e in range(8):
            t = b + e * 96
            pair = e == 7 and (m - start) % snare_8ths_every == snare_8ths_every - 1
            hits.append(DrumHit(t, 1) if e in (2, 6) or pair else DrumHit(t, 3, cymbal=True))
            if e in (0, 4):
                hits.append(DrumHit(t, 0))
        hits += [DrumHit(b + s * 48, 1, ghost=True) for s in (3, 11)]
    return sorted(hits, key=lambda h: (h.tick, h.pad))


def hand_hits(track):
    return {t: hs for t, hs in groups(track).items() if any(h.pad for h in hs)}


@pytest.mark.parametrize("bpm", [100, 120, 142])
def test_easy_keeps_the_off_beat_ride_when_slow(bpm):
    """In a two-hand Easy section, a hit of only hi-hat or ride may sit half a beat from another hand hit at 120 BPM or
    less (Harmonix Easy keeps off-beat rides there); snares stay a beat apart, and faster every hand hit keeps a beat."""
    tm = tempo(bpm)
    ex = drum_track(ride_groove())
    levels = reduce_track(ex, tm, sections=[0], loudness=[-20.0])
    easy = levels[2]
    hands = hand_hits(easy)
    on = sorted(hands)
    close = [(a, b) for a, b in zip(on, on[1:]) if b - a < RES]
    for a, b in close:
        assert b - a >= RES // 2
        assert any(all(h.pad in (2, 3) and h.cymbal for h in hands[t]) for t in (a, b))
    snares = sorted(t for t, hs in hands.items() if any(h.pad == 1 for h in hs))
    assert min(b - a for a, b in zip(snares, snares[1:])) >= RES
    if bpm <= 120:
        assert len({a // M for a, _ in close}) == 32  # an off-beat ride in every bar
    else:
        assert close == []
    assert not any(h.pad == 0 for h in easy.notes)
    assert errors(check_reductions([ex] + levels, tm)) == []


def test_medium_right_hand_on_toms_keeps_a_beat_at_speed():
    """At 147.5 BPM a right hand playing 8ths on the floor tom (or crash) is no right-hand 8ths on Medium either;
    inside an activation lane a tom fill keeps its 8ths."""
    tm = tempo(147.5)
    hits = []
    for m in range(4, 36):
        b = m * M
        if m % 8 == 7:  # an 8th tom fill, in an activation lane up to the next downbeat
            hits += [DrumHit(b + e * 96, (2, 2, 3, 3, 4, 4, 1, 1)[e]) for e in range(8)]
            continue
        for e in range(8):
            t = b + e * 96
            hits.append(DrumHit(t, 4, cymbal=True) if e == 0 and m % 8 == 0 else DrumHit(t, 3))
            if e in (2, 6):
                hits.append(DrumHit(t, 1))
            if e in (0, 4):
                hits.append(DrumHit(t, 0))
        hits += [DrumHit(b + s * 48, 1, ghost=True) for s in (3, 11)]  # ghost 16ths, which Hard drops
    lanes = [(m * M, M) for m in range(7, 36, 8)]
    ex = drum_track(hits, fills=lanes)
    levels = reduce_track(ex, tm, sections=[0], loudness=[-20.0])
    medium = levels[1]
    hands = hand_hits(medium)
    on = sorted(hands)
    in_lane = [a for a, b in zip(on, on[1:]) if b - a < RES and any(s <= a < s + n for s, n in lanes)]
    outside = [(a, b) for a, b in zip(on, on[1:]) if b - a < RES and not any(s <= a < s + n for s, n in lanes)]
    assert outside == []
    assert len(in_lane) >= 3 * len(lanes)
    assert any(h.pad == 3 and not h.cymbal for h in medium.notes)  # the groove itself stays, on quarter notes
    assert errors(check_reductions([ex] + levels, tm)) == []


def test_drums_hard_thins_16ths_and_2x_kicks():
    tm = tempo(142)
    hits = []
    for m in range(4, 36):
        for s in range(16):
            t = m * M + s * 48
            hits.append(DrumHit(t, 2, cymbal=True))  # 16th hi-hats
            if s % 2:
                hits.append(DrumHit(t, 0, double_kick=True))
            elif s % 4 == 0:
                hits.append(DrumHit(t, 0))
            if s in (4, 12):
                hits.append(DrumHit(t, 1))
    ex = drum_track(hits)
    hard = reduce_track(ex, tm)[0]
    on = onset_ticks(hard)
    assert min(b - a for a, b in zip(on, on[1:])) >= RES // 2
    assert not any(h.double_kick for h in hard.notes)
    assert len(on) / len(onset_ticks(ex)) <= 0.5


def test_drum_fill_has_no_kicks_and_keeps_its_activation_note():
    tm = tempo(142)
    hits = rock_beat(fill_every=4)  # each fill ends on the next downbeat's crash + kick
    ex = drum_track(hits, fills=[(6 * M + 3 * RES, M - 3 * RES + M), (10 * M + 2 * RES, M + M - 2 * RES)])
    levels = reduce_track(ex, tm, sections=[0], loudness=[-20.0])
    for tr in levels:
        for p in [p for p in tr.phrases if p.kind == DRUM_ACTIVATION]:
            g = groups(tr)
            inside = sorted(t for t in g if p.tick <= t <= p.tick + p.length)
            assert inside and inside[-1] == p.tick + p.length  # the activation note is on every level
            assert not any(h.pad == 0 for t in inside[:-1] for h in g[t])
    assert errors(check_reductions([ex] + levels, tm)) == []


def test_crashes_go_on_green_and_rides_stay_blue():
    tm = tempo(142)
    hits = []
    for m in range(4, 24):
        b = m * M
        hits.append(DrumHit(b, 3, cymbal=True))  # a lone blue cymbal: a crash
        hits.append(DrumHit(b, 0))
        if m >= 14:
            hits += [DrumHit(b + e * 96, 3, cymbal=True) for e in range(1, 8)]  # a ride pattern
        hits.append(DrumHit(b + 2 * RES, 1))
    ex = drum_track(sorted(hits, key=lambda h: (h.tick, h.pad)))
    hard = reduce_track(ex, tm)[0]
    g = groups(hard)
    for m in range(4, 14):
        assert [(h.pad, h.cymbal) for h in g[m * M] if h.pad] == [(4, True)]
    for m in range(15, 24):
        assert [(h.pad, h.cymbal) for h in g[m * M] if h.pad] == [(3, True)]


def test_cymbal_and_tom_on_one_pad_are_split():
    tm = tempo(142)
    hits = []
    for m in range(4, 20):
        b = m * M
        hits += [DrumHit(b, 2, cymbal=True), DrumHit(b, 2), DrumHit(b + 2 * RES, 1)]
    ex = drum_track(hits)
    hard = reduce_track(ex, tm)[0]
    for t, hs in groups(hard).items():
        if t % M == 0:
            assert sorted((h.pad, h.cymbal) for h in hs) == [(2, True), (3, False)]


def test_drum_star_power_keeps_a_hit():
    tm = tempo(142)
    hits = rock_beat(fill_every=0) + [DrumHit(9 * M + 3 * RES + 144, 1, ghost=True)]  # a lone ghost 16th
    hits = sorted(hits, key=lambda h: (h.tick, h.pad))
    ex = drum_track(hits, sp=[(9 * M + 3 * RES + 144, 20)])
    levels = reduce_track(ex, tm)
    for tr in levels:
        assert any(9 * M + 3 * RES + 144 <= t < 9 * M + 3 * RES + 164 for t in onset_ticks(tr))
    assert errors(check_reductions([ex] + levels, tm)) == []


def test_drum_star_power_of_kicks_alone_keeps_a_kick_on_easy():
    """With no sections Easy is one two-hand section, with no kicks; a phrase over kicks alone still keeps one."""
    tm = tempo(142)
    hits = [h for h in rock_beat(fill_every=0) if not 10 * M <= h.tick < 11 * M]
    hits += [DrumHit(10 * M + b * RES, 0) for b in range(4)]
    ex = drum_track(sorted(hits, key=lambda h: (h.tick, h.pad)), sp=[(10 * M, M)])
    levels = reduce_track(ex, tm)
    for tr in levels:
        assert any(10 * M <= t < 11 * M for t in onset_ticks(tr))
    easy = levels[2]
    assert [h.pad for h in easy.notes if 10 * M <= h.tick < 11 * M] == [0]
    assert sum(h.pad == 0 for h in easy.notes) == 1  # the rest of the song stays two-hand
    assert errors(check_reductions([ex] + levels, tm)) == []


@pytest.mark.parametrize("seed", range(4))
def test_drum_reduction_is_idempotent_and_deterministic(seed):
    tm = tempo([95, 142, 175, 142][seed])
    ex = drum_track(random_drums(seed), sp=[(8 * M, M)], fills=[(15 * M, M)])
    kw = dict(sections=[0, 20 * M], loudness=[-25.0, -20.0]) if seed % 2 else dict(sections=[0, 20 * M])
    levels = reduce_track(ex, tm, **kw)
    assert levels == reduce_track(ex, tm, **kw)
    for tr in levels:
        assert reduce_level(tr, tr.difficulty, tm, expert=ex, **kw) == tr


# ------------------------------------------------------------------------------------------------ checks and API

def test_check_reductions_reports_broken_ladders():
    tm = tempo(142)
    ex = fret_track(eighths(30), sp=[(10 * M, M)])
    good = reduce_track(ex, tm)
    bad_medium = Track("Medium", "Single", [FretNote(n.tick, (4,)) for n in good[1].notes] +
                       [FretNote(5 * M + 48, (0,))], list(ex.phrases))
    bad_easy = Track("Easy", "Single", [FretNote(n.tick, (0, 1)) for n in good[2].notes
                                        if not 10 * M <= n.tick < 11 * M], list(ex.phrases))
    kinds = {(i.difficulty, i.kind) for i in check_reductions([ex, good[0], bad_medium, bad_easy], tm)}
    assert ("Medium", "difficultyForbiddenNote") in kinds
    assert ("Medium", "notNested") in kinds
    assert ("Easy", "difficultyForbiddenNote") in kinds
    assert ("Easy", "emptyStarPower") in kinds
    same = Track("Hard", "Single", list(ex.notes), list(ex.phrases))
    kinds = {(i.difficulty, i.kind) for i in check_reductions([ex, same], tm)}
    assert {("Hard", "difficultyNotReduced"), ("Hard", "hardNotThinned"), ("Hard", "ladder")} <= kinds
    drums = drum_track(rock_beat())
    bad = Track("Easy", "Drums", [DrumHit(4 * M, 0), DrumHit(4 * M, 1), DrumHit(5 * M, 0, double_kick=True)])
    kinds = {i.kind for i in check_reductions([drums, bad], tm)}
    assert {"easyKickWithPad", "difficultyForbiddenNote"} <= kinds


def test_reduce_chart_adds_every_level():
    tm = tempo(142)
    stale = Track("Easy", "Single", [FretNote(4 * M, (0,))])
    chart = Chart(SongInfo("t", "a"), tm, [(0, "Intro"), (20 * M, "Chorus")],
                  [fret_track(eighths(30)), drum_track(rock_beat(30)), stale])
    out = reduce_chart(chart, drum_loudness=[-30.0, -20.0])
    assert sorted(t.name for t in out.tracks) == sorted(f"{d}{i}" for d in ("Expert", "Hard", "Medium", "Easy")
                                                        for i in ("Single", "Drums"))
    assert next(t for t in out.tracks if t.name == "EasySingle").notes != stale.notes
    text = write_chart(out)
    assert "[EasyDrums]" in text and "[HardSingle]" in text


def test_bad_arguments():
    tm = tempo(142)
    ex = fret_track(eighths(4))
    with pytest.raises(ValueError):
        reduce_level(ex, "Expert", tm)
    with pytest.raises(ValueError):
        reduce_track(reduce_level(ex, "Hard", tm), tm)
    with pytest.raises(ValueError):
        reduce_track(drum_track(rock_beat(8)), tm, sections=[0, M], loudness=[-20.0])
