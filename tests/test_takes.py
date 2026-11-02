"""Splicing several takes of one source by their agreement (songcharter.takes)."""
import numpy as np

from songcharter.takes import GAP, MARGIN, agreement, onsets, splice
from songcharter.timed import TimedHit, TimedNote, TimedPart

SECTIONS = [(0.0, "intro"), (10.0, "verse"), (20.0, "chorus")]


def part(notes, instrument="guitar"):
    return TimedPart(instrument, "expert", sorted(notes, key=lambda n: n.time))


def eighths(a, b, chord_every=0, jitter=0.0, seed=0):
    """8th notes (0.25 s) from a to b; every `chord_every`-th one a two-note chord; times jittered by +-jitter."""
    rng = np.random.default_rng(seed)
    out = []
    for i, t in enumerate(np.arange(a, b, 0.25)):
        frets = (0, 2) if chord_every and i % chord_every == 0 else (i % 3,)
        out.append(TimedNote(float(t + rng.uniform(-jitter, jitter)), frets))
    return out


def test_agreement_needs_the_same_shape():
    a = onsets([TimedNote(1.0, (0,)), TimedNote(2.0, (0, 1)), TimedNote(3.0, (2,))])
    same = onsets([TimedNote(1.02, (1,)), TimedNote(2.01, (2, 3)), TimedNote(3.03, (4,))])
    shape = onsets([TimedNote(1.0, (0, 1)), TimedNote(2.0, (0,)), TimedNote(3.0, (2,))])
    far = onsets([TimedNote(1.2, (0,)), TimedNote(2.2, (0, 1)), TimedNote(3.2, (2,))])
    assert agreement(a, same) == 1.0            # lanes may differ: only onsets and single/chord count
    assert abs(agreement(a, shape) - 1 / 3) < 1e-9
    assert agreement(a, far) == 0.0
    assert agreement(a, onsets([])) == 0.0
    assert agreement(onsets([]), onsets([])) == 1.0  # both agree there is nothing to play
    # one to one: two onsets cannot both match one
    assert agreement(onsets([TimedNote(1.0, (0,)), TimedNote(1.03, (1,))]), onsets([TimedNote(1.01, (0,))])) == 2 / 3
    # nearest first: 1.00 takes 0.99, which leaves 1.03 nothing in reach (0.96 is too far from it)
    near = onsets([TimedNote(0.96, (0,)), TimedNote(0.99, (0,))])
    assert agreement(onsets([TimedNote(1.0, (0,)), TimedNote(1.03, (0,))]), near) == 0.5


def test_the_takes_that_agree_fill_a_stretch_the_base_dropped():
    full = eighths(0, 30)
    base = [n for n in full if not (10 <= n.time < 20 and int(n.time * 4) % 2)]  # half the verse is missing
    takes = [part(base), part(eighths(0, 30, jitter=0.01, seed=1)), part(eighths(0, 30, jitter=0.01, seed=2))]
    out, windows = splice(takes, SECTIONS)
    assert [w.name for w in windows] == ["intro", "verse", "chorus"]
    assert [w.pick for w in windows] == [0, 1, 0] or [w.pick for w in windows] == [0, 2, 0]
    assert windows[0].start == 0.0 and windows[1].start == 10.0 - 0.05 and windows[2].end is None
    assert windows[1].onsets[0] == 20 and windows[1].onsets[1] == 40
    picked = takes[windows[1].pick].notes
    assert [n.time for n in out.notes] == sorted([n.time for n in base if n.time < 9.95]
                                                 + [n.time for n in picked if 9.95 <= n.time < 19.95]
                                                 + [n.time for n in base if n.time >= 19.95])
    assert out.instrument == "guitar" and out.difficulty == "expert"


def test_a_take_that_beats_the_base_by_the_margin_replaces_it():
    base = [n for n in eighths(0, 30) if not (10 <= n.time < 20 and int(n.time * 4) % 4 == 1)]  # a verse 8th in 4
    _, windows = splice([part(base), part(eighths(0, 30)), part(eighths(0, 30))], SECTIONS)
    assert [w.pick for w in windows] == [0, 1, 0]
    assert MARGIN < windows[1].scores[1] - windows[1].scores[0] < 0.1  # 0.071: only just past the margin


def test_takes_that_agree_a_section_is_silent_outvote_a_base_that_plays_there():
    sections = [(0.0, "verse"), (10.0, "break"), (20.0, "chorus")]
    quiet = eighths(0, 10) + eighths(20, 30)     # the other takes leave the break empty
    out, windows = splice([part(eighths(0, 30)), part(quiet), part(quiet)], sections)
    assert [w.pick for w in windows] == [0, 1, 0] and windows[1].onsets == (40, 0, 0)
    assert windows[1].scores == (0.0, 0.5, 0.5)
    assert not [n for n in out.notes if 9.95 <= n.time < 19.95] and len(out.notes) == 80


def test_the_base_stays_within_the_margin():
    # take 1 agrees a little better with take 2 than the base does, but by less than MARGIN
    a = eighths(0, 30)
    b = [n for i, n in enumerate(eighths(0, 30)) if i % 40]       # one onset in 40 missing
    takes = [part(b), part(a), part(a)]
    _, windows = splice(takes, SECTIONS)
    assert all(w.pick == 0 for w in windows)
    assert all(w.scores[1] - w.scores[0] < MARGIN for w in windows)


def test_a_take_that_disagrees_on_chords_loses():
    chords = eighths(0, 30, chord_every=2)
    singles = eighths(0, 30)                     # the same onsets, every one a single note
    _, windows = splice([part(singles), part(chords), part(chords)], SECTIONS)
    assert all(w.pick in (1, 2) for w in windows)


def test_a_sustain_stops_before_another_take_takes_over():
    long = TimedNote(9.0, (0,), end=12.0)        # the base's last intro note rings into the verse
    base = eighths(0, 9) + [long] + [n for n in eighths(10, 30) if int(n.time * 4) % 2 == 0 or n.time >= 20]
    other = eighths(0, 30)
    out, windows = splice([part(base), part(other), part(other)], SECTIONS)
    assert windows[0].pick == 0 and windows[1].pick != 0
    held = [n for n in out.notes if n.time == 9.0]
    assert len(held) == 1 and abs(held[0].end - (10.0 - 0.05 - GAP)) < 1e-9
    # no change of take at the end of the intro (the chorus changes): the sustain is left alone, unless it runs on
    # into the chorus, where it stops before the new take's notes
    base = eighths(0, 9) + eighths(10, 20) + [n for n in eighths(20, 30) if int(n.time * 4) % 2 == 0]
    for end, want in ((12.0, 12.0), (25.0, 20.0 - 0.05 - GAP)):
        out, windows = splice([part(base + [TimedNote(9.0, (0,), end=end)]), part(other), part(other)], SECTIONS)
        assert [w.pick for w in windows][:2] == [0, 0] and windows[2].pick != 0
        held = [n for n in out.notes if n.time == 9.0]
        assert len(held) == 1 and abs(held[0].end - want) < 1e-9


def test_a_sustain_rings_on_over_a_section_no_take_plays_in():
    # the takes hold a chord over a break that every take leaves empty; the verse and the chorus come from take 1,
    # so no other take's note is under it. The same with a few stray onsets in one take in the break.
    sections = [(0.0, "verse"), (16.0, "break"), (24.0, "chorus")]
    whole = eighths(0, 15.5) + [TimedNote(15.5, (0, 2), end=23.5)] + eighths(24, 40)
    base = [n for i, n in enumerate(whole) if i % 2]  # every other onset missing, the chord among them
    strays = [TimedNote(18.0 + k, (1,)) for k in range(3)]
    for takes, scores in (([whole, whole], (1.0, 1.0, 1.0)), ([whole + strays, whole], (0.5, 0.0, 0.5))):
        out, windows = splice([part(base)] + [part(t) for t in takes], sections)
        assert [w.pick for w in windows] == [1, 0, 1] and windows[1].scores == scores
        held = [n for n in out.notes if n.time == 15.5]
        assert len(held) == 1 and held[0].end == 23.5


def _verse_from_take_1(base_extra=(), other_extra=()):
    """The base drops half the verse, so the verse comes from take 1 (both other takes are the same)."""
    base = [n for n in eighths(0, 30) if not (10 <= n.time < 20 and int(n.time * 4) % 2)] + list(base_extra)
    other = part(eighths(0, 30) + list(other_extra))
    out, windows = splice([part(base), other, other], SECTIONS)
    assert [w.pick for w in windows] == [0, 1, 0]
    return out


def test_the_edges_of_a_change_of_take():
    edge = 10.0 - 0.05                           # the verse's window starts here
    at = [n for n in _verse_from_take_1([TimedNote(edge, (4,))], [TimedNote(edge, (3,))]).notes if n.time == edge]
    assert len(at) == 1 and at[0].frets == (3,)  # a note on the edge comes once, from the new take
    # a sustain that ends inside the gap is cut to it; one that starts after the cut loses its sustain
    out = _verse_from_take_1([TimedNote(9.6, (1,), end=9.92)])
    assert [n.end for n in out.notes if n.time == 9.6] == [edge - GAP]
    out = _verse_from_take_1([TimedNote(9.92, (1,), end=10.5)])
    assert [n.end for n in out.notes if n.time == 9.92] == [None]


def test_too_few_takes_or_no_sections_give_the_base():
    a = part(eighths(0, 30))
    for takes, sections in (([a, part(eighths(0, 30, seed=3))], SECTIONS), ([a, a, a], [])):
        out, windows = splice(takes, sections)
        assert out is a and windows == []


def test_drums_count_hits_per_onset():
    def kit(a, b, doubles):
        out = []
        for i, t in enumerate(np.arange(a, b, 0.25)):
            out.append(TimedHit(float(t), 2, cymbal=True))
            if doubles and i % 2 == 0:
                out.append(TimedHit(float(t), 0))
        return out
    base = kit(0, 30, False)                     # the kicks under every other hat are missing
    good = kit(0, 30, True)
    out, windows = splice([part(base, "drums"), part(good, "drums"), part(good, "drums")], SECTIONS)
    assert all(w.pick == 1 for w in windows)
    assert len(out.notes) == len(good) and all(isinstance(n, TimedHit) for n in out.notes)
