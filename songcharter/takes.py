"""Several takes of one source, spliced section by section by the takes' agreement (DESIGN.md 2.7, "Several takes").

A note source that samples (autochart) gives a different chart on every run, and one run can drop or garble a
stretch the others agree on (the test song's original take had half the other takes' onsets at 340-400 s). With
three or more takes of the same audio on the same clock, the take the others agree with most in a stretch is the
best guess at what a run would write there:

  1. The song is cut into windows at the section starts (on the takes' clock), each moved `early` seconds earlier
     so a note a little ahead of the downbeat belongs to the section it starts.
  2. In each window every take is scored by its mean F1 against each other take. A match pairs two onsets within
     `tol` one to one, nearest first, and they must agree on the onset's shape: single note against chord on
     5-fret parts, one hit against several on drums. Two takes that both leave the window empty agree fully, so
     takes that agree a stretch is silent outvote one that writes notes there.
  3. The first take (the base) stays unless another take beats it by `margin`; then the best-scoring take is used.
  4. The window's notes come from the chosen take. A sustain is cut `gap` seconds before the next window whose
     notes come from another take (a window where the chosen take writes nothing does not count), so it never runs
     under another take's notes.

Only the Expert part is spliced (the build reduces the other levels from it). The takes' own star power, solos and
fills are dropped, as assemble drops every source's phrases.
"""
from __future__ import annotations

from dataclasses import dataclass, replace

import numpy as np

from .timed import TimedHit, TimedPart

MARGIN = 0.05   # a take must beat the base by this much mean F1 to replace it in a window
EARLY = 0.05    # seconds: a window starts this much before its section (a note slightly ahead of the downbeat)
TOL = 0.05      # seconds: two takes' onsets this close are the same onset
GAP = 0.06      # seconds: a sustain ends this long before a window where another take takes over (Encore's gap)


@dataclass(frozen=True)
class Window:
    start: float                 # seconds on the takes' clock
    end: float | None            # None: to the end of the song
    name: str
    onsets: tuple[int, ...]      # per take
    scores: tuple[float, ...]    # per take: mean F1 against the other takes
    pick: int                    # the take used


def onsets(notes: list) -> tuple[np.ndarray, np.ndarray]:
    """Sorted onset times and, per onset, whether it is a chord (5-fret) or several hits (drums)."""
    width: dict[float, int] = {}
    for n in notes:
        width[n.time] = width.get(n.time, 0) + (1 if isinstance(n, TimedHit) else len(n.frets))
    ts = sorted(width)
    return np.array(ts, dtype=float), np.array([width[t] > 1 for t in ts], dtype=bool)


def agreement(a: tuple[np.ndarray, np.ndarray], b: tuple[np.ndarray, np.ndarray], tol: float = TOL) -> float:
    """F1 of one-to-one onset matches within tol (nearest first) that also agree on single against chord; 1 when
    both are empty (they agree there is nothing to play)."""
    (ta, wa), (tb, wb) = a, b
    if not len(ta) and not len(tb):
        return 1.0
    if not len(ta) or not len(tb):
        return 0.0
    used = np.zeros(len(tb), dtype=bool)
    m = 0
    for t, w in zip(ta, wa):
        lo, hi = np.searchsorted(tb, t - tol), np.searchsorted(tb, t + tol, side="right")
        ks = [k for k in range(lo, hi) if not used[k] and wb[k] == w]
        if ks:
            used[min(ks, key=lambda k: abs(tb[k] - t))] = True
            m += 1
    return 2 * m / (len(ta) + len(tb))


def splice(takes: list[TimedPart], sections: list[tuple[float, str]], *, margin: float = MARGIN,
           early: float = EARLY, tol: float = TOL, gap: float = GAP) -> tuple[TimedPart, list[Window]]:
    """One part from several takes of it (the first is the base), chosen window by window (the module docstring).
    sections: (seconds on the takes' clock, name), sorted; with fewer than three takes, or no sections, the base is
    returned."""
    base = takes[0]
    if len(takes) < 3 or not sections:
        return base, []
    starts = [0.0] + [max(0.0, t - early) for t, _ in sections[1:]]
    names = [n for _, n in sections]
    ends: list[float | None] = starts[1:] + [None]
    ons = [onsets(t.notes) for t in takes]
    windows = []
    for a, b, name in zip(starts, ends, names):
        hi = np.inf if b is None else b
        cut = [(t[(t >= a) & (t < hi)], w[(t >= a) & (t < hi)]) for t, w in ons]
        scores = tuple(float(np.mean([agreement(cut[k], cut[j], tol) for j in range(len(takes)) if j != k]))
                       for k in range(len(takes)))
        best = max(range(len(takes)), key=lambda k: (scores[k], -k))
        pick = best if scores[best] > scores[0] + margin else 0
        windows.append(Window(round(a, 4), None if b is None else round(b, 4), name,
                              tuple(len(c[0]) for c in cut), tuple(round(s, 4) for s in scores), pick))
    notes = []
    for i, w in enumerate(windows):
        hi = np.inf if w.end is None else w.end
        # sustains stop gap seconds before another take's notes begin: at the next window with another pick that
        # writes notes there (a window its take leaves empty, such as a break no take plays in, is skipped)
        cut = next((v.start for v in windows[i + 1:] if v.pick != w.pick and v.onsets[v.pick]), np.inf) - gap
        for n in takes[w.pick].notes:
            if not w.start <= n.time < hi:
                continue
            if not isinstance(n, TimedHit) and n.end is not None and n.end > cut:
                n = replace(n, end=cut if cut > n.time else None)
            notes.append(n)
    notes.sort(key=lambda n: n.time)
    return TimedPart(base.instrument, base.difficulty, notes), windows
