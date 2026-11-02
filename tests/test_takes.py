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
    # one to one: two onsets cannot both match one
    assert agreement(onsets([TimedNote(1.0, (0,)), TimedNote(1.03, (1,))]), onsets([TimedNote(1.01, (0,))])) == 2 / 3


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
    # no change of take at the end of a window: the sustain is left alone
    out, windows = splice([part(other + [TimedNote(29.9, (0,), end=31.0)])] + [part(other)] * 2, SECTIONS)
    assert out.notes[-1].end == 31.0


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
