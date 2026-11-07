# M6-08 report: a tempo estimate always ends (and v0.2.1)

The orchestrator, 2026-11-07, from the owner's report of a build stuck at "Build and check the chart" for over an
hour on his PC (v0.2.0, a 221-s song with lyrics, an album cover and a 1440p background; normally a minute or two).

## The cause

The job log (in the owner's diagnostics zip) ends with numpy's `RuntimeWarning: overflow encountered in scalar
multiply` at `beatgrid.py:264`, `bpm *= 2`; the chart process ran at 94 % CPU. `estimate_tempo` refines the winning
period from parabolas through the autocorrelation's peaks at one to four periods, each through the highest of five
frames and its two neighbours. A neighbour outside those five can be higher: the three points are then no peak, a
curvature near 0 puts the vertex hundreds of frames away, and the period can come out negative. The octave fold
(`while bpm < lo: bpm *= 2`) then doubles a negative tempo for ever. A search over made-up 20-s envelopes found it in
sparse windows (a few scattered onsets, as in a quiet stretch); the art and the lyrics had nothing to do with it.

## The fix

`_fold`: a refined tempo that is not a positive finite number takes the unrefined winner's; nothing else changes.
A first version also bounded the vertex to half a frame (where a peak's always is); over every kept song's whole-song
and 20-s window estimates (2,865: drum, guitar and mix envelopes, three tempo ranges, the reference, stress and first
20-song folders) that changed 357 (0.19 % at the median, more than 5 % on 12, 96 % at most), so it went to M5-99 as an
item to measure against the humans' tempi. The guard alone leaves all 2,865 identical to v0.2.0's.

## Tests and checks

- `test_a_sparse_window_gives_a_tempo_in_range_and_ends`: a made-up sparse window (8 onsets in 20 s) gives the
  unrefined winner, in a subprocess with a 60-s limit so a hang fails the test instead of stopping the suite.
- `test_the_octave_fold_ends_on_any_tempo`: the fold on 60, 240, 100 and 184.9 BPM in process, and on a tiny negative,
  -200, 0, +-inf and nan in a time-limited subprocess.
- Breaks: the guard removed (both fail on their time limits, none hangs), a fallback to the range's lower bound (the
  sparse test fails).
- CI green on the branch (run 42338430567).

## v0.2.1

The same fix on v0.2.0 (branch `release-0.2.1` from the v0.2.0 tag: the fix, its tests, the version 0.2.1 in
pyproject.toml, `__init__` and uv.lock). An independent review (sc-reviewer) found no major finding: `_fold` ends on
every input, the unrefined winner is always inside the range, no other loop of the same shape in songcharter/ can
hang, `updates.py` offers a v0.2.1 pre-release to a v0.2.0 install; its two minors (the sparse test's assertion, a
docstring citing later work orders) were fixed in 23389ac. CI green on 23389ac (run 42338399880). The owner builds it
with `packaging/release/build.sh 0.2.1` from a clean clone at 23389ac and publishes it as a pre-release.
