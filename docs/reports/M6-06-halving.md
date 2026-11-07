# M6-06 report: a grid at twice the humans' tempo, halved

Builder, branch `m6-06-halving` (worktree `<wt>/m6-06`), from main a89d6a0 (after M6-05). Paths below: `$DEV` is
the dev data folder, `$G` = `$DEV/golden`, `<scratchpad>` the session's scratch folder.

## Commits

- `dd6aaae` quantize: an off-beat onset whose straight and triplet slots are one line leans triplet
- `4b58f06` M6-06: a first grid at twice allin1's beats, under the fold's floor halved, is built again from them
- `ef1e020` DESIGN 2.3, 2.6, 2.15 and M5-99: the halving pass, its statistic, the build choice and the stress table

## The rule, kept

**Step 1's numbers, checked.** The first grid's median beat rate over allin1's, recomputed from the kept runs of main
after M6-05 (`report.json`'s `octave_stats.first.bpm_median` against `sections/segments.json`'s beats): sooth 2.0016,
the ten others 0.9940-1.0087 (troop and pm2 at their first grids, 1.0001 and 0.9999). It holds.

**The rule** (`assemble.halving_test`, `assemble._halving_pass`), under `grid_octave` "auto" only, with six guards:
1. the density test said 1 (no halving when the notes say double, even if the doubling's guard then refuses);
2. the rate ratio is 2 within 10 % (`HALVE_TOLERANCE`);
3. the halved tempo is under `BPM_RANGE`'s 85 BPM floor. This is the orchestrator's guard, taken: allin1 sits at
   half the humans' tempo on both 200 BPM stress songs, so "allin1 says half" alone is no reason to halve a tempo
   the first pass could hold. Tested at 170/85 (not halved) and 168/84 (halved);
4. at least 16 of allin1's beats inside the audio (`HALVE_MIN_BEATS`);
5. the halved grid's confident share at least 0.7 times the first's (the doubling's guard, `OCTAVE_EVIDENCE_MIN`);
6. `grid_octave` 1 forces the first grid (no halving).
report.json's `grid.octave_stats.halving` records the numbers, the thresholds, why, the halved grid's record, the
evidence ratio and `kept`; `grid.octave` is 0.5; the build warns "tempo halved to ...: check sync" (or "check the
tempo" when the guard refuses).

**The construction: allin1's beats refined (C), not every other line (the order's wording).** On sooth the first
grid's parity on allin1's beats flips at about 300 s: even lines 0.81-1.00 of each 30-s window before, odd 0.78-1.00
after. Our grid has a tempo dip at 297-315 s (beat 380 -> 570 -> 380 ms) that neither the humans (steady 760 ms) nor
allin1 have, and comes out one line off. Beat F1 against the two human charts (scorer `match`/`prf`, 70 ms; today's
grid 0.652/0.649 in this harness, stress.py 0.643/0.644):
- every other line, one phase: 0.536/0.527;
- every other line, the phase from allin1 per +-16 lines (B; 2 odd steps): 0.972/0.962, median |human - ours| 13.1 ms;
- allin1's beats refined onto the drums (C; `beat_grid(start=...)`, the range halved): 0.972/0.969, 14.8 ms, confident
  share 0.798 against 0.682; 84 % of its beats within 5 ms of a first-grid line, 92.5 % within 15 ms;
- allin1's raw beats: 0.984/0.982.
B was the closer reading of "every other beat line" and keeps our lines' timing. I asked; the orchestrator chose C:
one mechanism with M6-05's, no new parameter (B needs a window and a switch rule), and `beat_grid` gives it its own
downbeats, evidence and tempo check (no downbeat code of mine beside `bar_phase`, which is M6-03's). No part fell, so
B was not measured further (the orchestrator's condition).

**The slots follow the octave.** On sooth's first grid 16.7 % of the guitar's Expert notes (27.9 % of the bass's)
sit on odd 16ths and 5.3 % (1.9 %) on 8th-note triplets; 27 % of the guitar's gaps are a 16th or less. So the order's
1/32 sentence holds in effect: on a halved grid every part, and the lyrics, take 8 straight and 6 triplet slots a
beat (`assemble._halved_slots`), and a part's offset is measured on the halved beats with their midpoints
(`assemble.offset_map`), the first grid's level.

**A change outside the order's file list: `songcharter/quantize.py`, one condition** (approved by the
orchestrator). `SnapGrid.from_ticks` read an off-beat onset as leaning triplet only when strictly nearer its triplet
slot. On 8/6 the beat's midpoint is both slots (4/8 = 3/6), and a 16th-note triplet run plays it (the first grid's
beat line), so no beat could ever go triplet: made-up 1/24 notes all snapped to 1/32s. The onset now leans when the
two slots are one line (within the rule's tolerance, as before). On 4/3, 2/3 and 2/0 no off-beat line is shared
(a test sweeps every position), and the golden and stress runs below are identical outside sooth.

## The table (the stress set: main a89d6a0 `$G/main-m605-stress` against the branch 4b58f06 `$G/m6-06-stress-new`)

`--rerun bass,sections` both, 1 CPU take; `eval/stress.py score` both; `eval/stress.py compare`: exit 0,
"**Regressions (a primary F1@50 down by more than 0.01): 0**".

| sooth (primary / alt1) | before -> after | the humans |
|---|---|---|
| grid | 153.97 BPM, octave 1 -> 77.03 BPM, octave 0.5 (689 beats; share 0.682 -> 0.798, guard ratio 1.17) | 77-80 |
| beat F1 | 0.644 / 0.654 -> **0.985 / 0.986** | 1.000 |
| downbeat F1 | 0.278 / 0.281 -> **0.000 / 0.000** (bar-phase margin 0.029, flagged) | 1.000 |
| guitar F1@50 Expert | 0.658 / 0.770 -> 0.704 / 0.777 | 0.712 (alt1 vs primary) |
| guitar F1@50 Hard / Medium / Easy (primary) | 0.655 / 0.594 / 0.439 -> 0.721 / 0.674 / 0.542 | |
| bass F1@50 Expert / Hard / Medium / Easy | 0.692 / 0.825 / 0.842 / 0.634 -> 0.710 / 0.855 / 0.883 / 0.693 | |
| guitar star power a minute | 3.89 -> **1.89** | 2.33 / 3.23 |
| guitar solo time overlapping alt1's (primary: none) | 0.794 -> 0.887 (IoU 0.602 -> 0.728) | |
| guitar HOPO share; play-state agreement | 0.35 -> 0.65; 0.56 / 0.67 -> 0.60 / 0.45 | 0.55 / 0.39 |
| guitar median timing error ms | 39.6 / 8.0 -> 37.1 / 6.5 | |
| offsets measured (guitar / bass / drums) | 0.3 / 56.0 / -0.5 ms -> 2.5 / 57.9 / 1.3 ms | |

troop, break, pm2: all 12 tracks each with identical hashes; beat F1 1.000, 0.994, 0.987 and downbeat F1 0.000,
0.988, 0.000, both runs. Their `halving.why`: "the notes are too dense for the first grid: the density test doubles
it" (troop, pm2); break "the grid's beat rate is 1.001 times allin1's (not 2 within 10%)".

The order's stress lines: beat F1 toward 1.0, met; F1@50 not lower, met (every level rises); the solo overlap not
lower, met (measured with the scorer's scan, numbers only, under the score's own lag, its sign checked by note
matches, 0.801/0.808); troop, pm2 and break unchanged, met. **The star power line fails**: the phrase rule counts
beats (about one phrase per 40 beats), so at 77 BPM the rate halves, to under the humans' 2.33-3.23. That is
`starpower.py`'s rule, outside this order: put in M5-99 (a slow-tempo rate). Downbeat F1 falls from 0.278 to 0.000:
`bar_phase` has no margin on the halved grid. It is M6-03's area; its rule reaches this grid through `beat_grid`.

## Checks

- **Golden** (`python -m eval.golden run --code <wt>/m6-06 --out $G/m6-06-new --threads 2 --rerun bass,sections`,
  exit 0; `python -m eval.golden diff $G/main-m605 $G/m6-06-new --expect none`): exit 0, "golden diff: no UNEXPECTED
  change", "Every song's results (hashes, counts, scores) identical: yes". The seven references' ratios 0.994-1.009.
- **Stress**: above (run exit 0, score exit 0, compare exit 0).
- **Tests**: 11 new (10 in tests/test_assemble.py, 1 in tests/test_quantize.py): CI's suite count went from main's
  1102 to 1113 passed.
- **Breaking the code** (`<scratchpad>/m6-06b/mut/run.py`: one break at a time, the halving, octave and quantize
  tests run, the file restored and checked): each of 19 breaks fails at least one test. Quantize: no shared-line rule
  (5 fail), the condition swapped (5), the shared line without its tolerance (1, after adding the 35-ms-late case).
  Assemble: triplet slots 3 on a halved grid (5), straight 4 (4), no halved part slots (5), no offset map (2), no
  tolerance (2), no floor (1), no minimum count (1), the half-beat test on (1), no evidence guard (1), no onset-time
  shift (1), halving when the notes are dense (9), halving under a forced 1 (2), the fold range not halved (1), no
  halved lyric slots (1), allin1's duplicates counted (1), beats past the audio counted (1). The first runs of A8, A10
  and A13 failed nothing because my test selection missed the test that pins them; rerun with it, each fails it.
- **Suite** (`tools/heavy.sh <venv>/python -m pytest -q -p no:cacheprovider --basetemp=<shm>/pt-m6-06`, at
  ef1e020's code): "1112 passed, 5 skipped in 751.60s (0:12:31)", exit 0.
- **CI**: <repo>/actions/runs/42323389123 on ef1e020 (the branch's head):
  success, linux and windows. Linux suite "1113 passed, 4 skipped" (main a89d6a0's run: 1102), "all 8 Linux hooks
  passed"; windows "all 1 Windows hooks passed". The earlier run on 4b58f06,
  <repo>/actions/runs/42316804816, success too. No hook added: the change's checks
  are suite tests.
- **Privacy**: `EVAL_DATA=$DEV/eval python3 -I eval/privacy_check.py`: "271 files, 14 md5s and 37 names checked, 0
  found", exit 0, before each push. The branch's diff and commit messages scanned (`git diff origin/main...HEAD`):
  no lyrics, audio, model names (only the attribution trailers) or personal details.

## Not done or uncertain

- One positive in eleven songs; the rule's margin is wide, the sample thin (M5-99).
- Star power under the humans' on the halved song; downbeats on it (M6-03).
- A triplet half beside a straight half of one halved beat gets the beat's one choice (up to a 1/24 of the first
  grid's beat off): guitar triplet notes 116 -> 92 on sooth. `SLOT_PRIOR` reads the halved grid's levels (the first
  grid's odd 16ths take the 1/32 prior): left as the humans' mix at their level, not tuned.
- The report's `quantize.measured_offset` (inside `quantize_part`) is still measured on the halved map; the applied
  offset is `offset_map`'s (report.json's `parts.*.offset`).
- No `grid_octave` value forces a halving. A pulse at 85-92.5 BPM that the first pass doubled stays doubled (the
  floor guard).
- The guitar's HOPO share overshoots the primary (0.65 against 0.55; alt1 0.39), and the play-state agreement with
  alt1 falls (0.67 -> 0.45) while the primary's rises (0.56 -> 0.60): the natural threshold now reads 77 BPM.
- Merge with M6-03: my change touches `_octave_pass`'s first branch, a new `_halving_pass`, `part_rules`,
  `lyric_rules`, `_offset`'s map and the second-pass lambda (a `half_beat` argument), and calls no downbeat code.

## Review fixes and the merge with M6-03 (2026-11-07)

The review (`<scratchpad>/briefs/m6-06.review.report.md`) found no defect in the code: one major finding on the
docs (R1) and three untested call sites (R2-R4).

### Commits

- `b279d13` Merge origin/main into m6-06-halving (M6-03: the bar phase from allin1's downbeats, after the octave
  pass). Conflicts only in the assemble.py module docstring and DESIGN 2.3; both kept. M6-03's `with_downbeats`
  runs on the grid `_octave_pass` returns (the halved one too), before `plan_lead_in` and `offset_map`.
- `01fc597` Review fixes (M6-06): the halved song's offset, words and half-beat call pinned.
- `f4ad8f0` DESIGN 2.3 and M5-99 (M6-06 review): the sustain floor and star power read fewer on a halved grid.
- `460f400` DESIGN 2.3 (M6-06): the halved grid's downbeats from allin1's vote on the merged head, and its golden diff.

### The fixes

- **R1 (docs only, the orchestrator's decision).** DESIGN 2.3's sentence that the beat-counted rules read the
  halved grid "as they should" is corrected: the sustain floor (`SUSTAIN_MIN_BEATS`, 0.75 beat: 584 ms at 77 BPM, 292
  ms on the first grid) and the star power rate read fewer there. The stress table has the sustain share (guitar
  0.14 -> 0.05, bass 0.15 -> 0.07; the humans 0.07 / 0.14 and 0.15; Expert sustains dropped 27 -> 217 and 45 ->
  218). M5-99 has one item, "Beat-counted rules at a slow tempo", for both, to measure on the 20-song set's slow
  songs, not on sooth alone; its halving item and the star power item point to it.
- **R2.** The pulse song's guitar tool is now 10 ms late (`PULSE_LATE`) and plays the first grid's 16ths (half of
  them between the halved map's 16ths, so their phases cancel there). The test asserts the halved run's applied
  offset equals the first-grid run's on the same notes (within 2 ms), which is over 8 ms.
- **R3 and R4.** A new test assembles the pulse song with six made-up words on its first-grid 16ths. report.json's
  `lyrics.slots` is 8/6, every word lands on a 1/32 line, three of them odd, each within 12 ms of its time. A spy on
  `beat_grid` sees the first pass ask nothing of the half-beat test and the halving pass (`start=` allin1's beats)
  `half_beat=False`.
- **The review's breaks, run in a copy** (`<shm>/m606-mut`; the worktree was in use by the reruns): B5, `_offset`
  on the chart's map, fails the pulse-song test; B4, the lyric call site at 1, and B6, the lambda's `half_beat=True`,
  each fail the new test. The unbroken copy passes both.

### The rerun on the merged head (b279d13; `--rerun bass,sections`, through the heavy lock)

- **Stress** (`eval.golden run --refs $EVAL_DATA/stress --work $G/stress-work --code <wt>/m6-06 --out
  $G/m6-06-stress-new2`, exit 0; `stress.py score`, exit 0; `stress.py compare $G/m6-03-stress-new
  $G/m6-06-stress-new2`, exit 0): "**Regressions (a primary F1@50 down by more than 0.01): 0**".
  - **sooth's downbeat F1 0.297 / 0.297 -> 0.989 / 0.989** (primary / alt1; M6-03's run, at 154 BPM, against the
    merged head). The vote: allin1 gave 173 downbeats, 172 voted, counts [172, 0, 0, 0], so the margin is 1.000 and
    the result is not flagged. The kick's own phase was 2, margin 0.029, flagged, and was overruled. Before the
    merge, the kick's phase alone gave 0.000.
  - sooth's beat F1 0.644 -> 0.985 / 0.654 -> 0.986. Its Expert F1@50, star power (1.89 a minute) and sustain shares
    are as before the merge. Every lower level gains again, against M6-03's run: guitar Hard / Medium / Easy 0.655 /
    0.594 / 0.442 -> 0.721 / 0.674 / 0.542, bass 0.825 / 0.842 / 0.627 -> 0.855 / 0.883 / 0.693. The solo time
    overlapping alt1's is 0.824 -> 0.903 (IoU 0.637 -> 0.749).
  - troop, break and pm2: all 12 tracks each identical to `$G/m6-03-stress-new`. Downbeat F1 is 1.000, 0.988 and
    0.979 on both runs; beat F1 1.000, 0.994 and 0.987.
- **Golden** (`--out $G/m6-06-new2`, exit 0; `eval.golden diff $G/m6-03-new $G/m6-06-new2 --expect none`): exit 1,
  "UNEXPECTED: 2", both of them the run-level drums flag, one on each run: "drums answered from the kept folders
  (made by 8ba3cbdf590c), but drums's files differ in its code ... pass --rerun drums to both runs". "Parts changed
  as expected: 0. Every song's results (hashes, counts, scores) identical: yes." No track is flagged. It is the flag
  the orchestrator judged a false positive on M6-03: beatgrid.py is in the drums engine's files, and this branch
  does not touch it (`git diff origin/main..HEAD -- songcharter/` is assemble.py and quantize.py only). I made no
  `--rerun drums` pair (it needs a before of my own).
- **Suite** at 460f400 (`SONGCHARTER_SCAN_CHART=... tools/heavy.sh <venv>/python -m pytest -q -p no:cacheprovider
  --basetemp=<shm>/pt-m6-06 -rs`): "1118 passed, 6 skipped in 715.63s", exit 0. The skips are this machine's (no
  allin1 Python, no LnkParse3, scan-chart's npm check). A first run without `SONGCHARTER_SCAN_CHART` gave "1096
  passed, 28 skipped", so I reran it with the variable set.
- **CI**: <repo>/actions/runs/42330952786 on 460f400 (the branch's head): success,
  linux and windows. Linux suite "1120 passed, 4 skipped" (main 600467a's run: 1108, so the twelve new tests ran),
  "all 8 Linux hooks passed"; windows "all 1 Windows hooks passed".
- **Privacy**: `privacy_check.py`, "272 files, 14 md5s and 37 names checked, 0 found", exit 0, before the push. The
  diff against origin/main and the commit messages were scanned: only the attribution trailers.

## The orchestrator's decisions (2026-11-06 and 07)

- **C over B** (the halved grid from allin1's beats refined onto the drums, the same mechanism as M6-05, over every
  other line with a local phase): equal beat F1, one mechanism, no new parameter; on the conditions that sooth's
  F1@50 not fall (it rose on every part and level), that the downbeats come from the grid's own path (M6-03's vote
  then reaches the halved grid: 0.989), and that the halved grid's slots be pinned in tests.
- **The one condition in quantize.py** (`SnapGrid.from_ticks`), outside the order's file list: allowed, with tests on
  the shared midpoint, a test that the 4/3, 2/3 and 2/0 grids do not move, and the golden diff (identical). The
  review confirmed it moves nothing on those grids by arithmetic and by a sweep of 200 random grids each.
- **Star power (1.89 a minute, the humans 2.33-3.23) and the sustain floor (sooth's sustain share 0.14 -> 0.05,
  the humans 0.07-0.14), accepted for this order**: both are beat-counted rules read at 77 BPM, measured on one
  song; M5-99's "Beat-counted rules at a slow tempo" measures them on the 20-song set's slow songs.
- **The golden diff's drums flag** on the merged head is the run-level flag accepted on M6-03 (beatgrid.py, in the
  drums engine's file list, differs from the kept folders' commit; the drums engine imports none of what changed).
  Every song's results identical.

## Review (sc-reviewer, 2026-11-07): M6-06 review (branch m6-06-halving, ef1e020, against a89d6a0)

Reviewer, read-only. Copies and scripts in <shm>/review_m606/ (deleted at the end). Numbers from the kept runs
golden/main-m605-stress and golden/m6-06-stress-new (our charts and report.json only; no ref chart opened).

## Findings

### R1 (major) The halved grid halves both parts' sustains; DESIGN says the sustain floors read it "as they should"
docs/DESIGN.md:614-615 says the beat-counted rules (sustain floors, star power, reductions) read the halved grid
"as they should", and the stress table (DESIGN 2.3 and the builder's report) leaves sustains out. The floor is
quantize.SUSTAIN_MIN_BEATS (0.75 beat on Expert, with SUSTAIN_GAP_BEATS 0.25), so at 77 BPM it is 584 ms where it
was 292 ms. On sooth (report.json, Expert):
- guitar sustains_dropped 27 -> 217 (sustains_trimmed 100 -> 75);
- bass sustains_dropped 45 -> 218.
stress_report.md "sustain o/t": guitar 0.14 -> **0.05** (the humans 0.07 primary / 0.14 alt1); bass 0.15 ->
**0.07** (the human 0.15). Before, both parts matched the humans; after, both fall under them. The humans at the
same 77 BPM keep more, so this is our beat-counted rule, not the tempo. It is the same class as star power
(already in M5-99), but it is not reported, and DESIGN states the opposite. At minimum: put the sustain share in the
table and M5-99, and fix DESIGN 614-615. Whether the floor needs a seconds cap is the orchestrator's call.
Repro: `python3` over `$G/{main-m605-stress,m6-06-stress-new}/sooth/report.json`
`parts.{guitar,bass}.quantize.expert.sustains_dropped`, and the `sustain o/t` column of each stress_report.md.

### R2 (minor) The offset-map wiring is untested: measuring on the chart's map keeps every test green
Break: assemble.py:1806 `_offset(part, song, tm_offset, pad)` -> `_offset(part, song, tm, pad)`. test_assemble,
test_quantize, test_lyrics and test_beatgrid all pass ("201 passed"). The pulse-song test checks `offset["map"]`, but
that is written by a separate `if tm_offset is not tm`, and the synthetic notes have no offset to find. On sooth
the halved map's concentration is 0.55 against offset_map's 0.71 (report.json `quantize.expert.concentration`
against `offset.concentration`), so the break would ship a weaker offset. Fix: give the pulse song's guitar a known
offset of about 10 ms and assert `offset.applied` is near it.

### R3 (minor) The lyric call site on a halved grid is untested
Break: assemble.py:1882 `lyric_rules(octave)` -> `lyric_rules(1 if octave == 0.5 else octave)`. The same four
files pass ("201 passed"). The test calls lyric_rules(0.5) directly, and no assembled halved song has words, so a
halved song's words would snap to the first grid's 8ths without any test failing. Fix: give the pulse song a few
timed words on 16ths and assert their ticks.

### R4 (minor) The second-pass lambda's half_beat argument is untested at its call site
Break: assemble.py lambda `half_beat=half_beat` -> `half_beat=True`, so the halved pass always runs the half-beat
phase test that allin1's beats are meant to replace. Same four files pass ("201 passed"). The unit test uses a fake
second_pass (`calls[0][3] is False`), and the pulse song's phase passes the half-beat test either way. Fix: offset
the pulse song's allin1 beats so that the half-beat test would pick the other line set, or monkeypatch beat_grid and
assert half_beat=False reaches it.

## Answers to the brief's questions

- **HOPO.** The threshold is Clone Hero's own (65/192 beat in ticks), read on 77 BPM as on the humans' 77 BPM charts.
  Nothing of ours doubles it. Of sooth's Expert guitar notes (before vs after, matched by time), **633 non-tap notes
  went strum -> HOPO, all with a gap of 135-270 ms** (the first grid's 8ths, 195 ms = 0.25 beat at 77 BPM, under
  0.338). 621 of them are notes the source (Fretformer 2's chart at about 150 BPM, where a 0.5-beat gap is a natural
  strum) never forced, so HOPO_RULES "forced" hands them to our grid's natural rule, as designed. Only 2 notes went
  HOPO -> strum. The rest kept their state: gaps up to 135 ms were HOPOs on both grids, and over 270 ms strums on both.
  So the overshoot (0.65 against 0.55 / 0.39) is the source's unforced 8ths read at the humans' tempo. The primary
  leaves most of them HOPO and alt1 force-strums many, hence 0.56 -> 0.60 and 0.67 -> 0.45. No defect.
- **Star power**: report.json `phrases...star_power_count.span_beats` 1380.5 -> 694.1 over the same 539.6 s
  (counted_beats equal, under the 160 BPM cap). K = round(beats/40) halves; that is the whole change. Confirmed.
- **quantize.py condition**: `ks*n == kt*s` with ks in [0, s-1] and kt in [0, n] is only true off-beat when ks/s =
  kt/n, which needs a common fraction: none for 4/3 or 2/3, and 2/0 returns early. A random sweep (200 grids each,
  60-220 BPM, jittered straight, triplet and 1/32 positions; prop.py) gives byte-identical triplet beats with and
  without the condition on 4/3, 2/3 and 2/0, and differing on 8/6 (1450 -> 2300 triplet beats). The tolerance (at
  most 1/4 of a triplet slot) is safe. With it, my break of treating every midpoint as shared (B1) is an equivalent
  mutant on 4/3 and 2/3: an onset within tol of a triplet slot is already nearer it than the midpoint.
- **octave 0.5 consumers**: part_rules, lyric_rules, offset_map, _quantize and the report's `slots` and `octave`
  only; nothing else in songcharter/, eval/ or packaging/ reads `octave`. No code assumes 1 or 2.
- **Guards**: the edges are tested (ratio 1.79/1.81/2.19/2.21, floor 170/168, beats 15/16, duration, duplicates,
  evidence +-, the InputError path, forced 1, dense). The rule is deterministic (np.unique and median; no randomness).
- **Merge with M6-03 (310d91f)**: `git merge-tree --write-tree ef1e020 310d91f` conflicts only in the assemble.py
  module docstring (lines 19-27) and DESIGN.md (644-742). With the docstring resolved, test_assemble, test_beatgrid,
  test_sections and test_quantize pass on the merged tree: "191 passed, 2 skipped". The code composes:
  `with_downbeats` runs on the grid _octave_pass returns (the halved one), before plan_lead_in and offset_map, so
  M6-03 votes allin1's downbeats on the 77 BPM beats.

## Tests of the tests (my breaks, not the builder's 19)

B1 midpoint shared on every grid: green (an equivalent mutant, above). B2 bass not halved: 1 fails. B3 _quantize
call site at octave 1: 2 fail. B4 lyric call site: green (R3). B5 offset call site: green (R2). B6 lambda half_beat:
green (R4). B7 offset_map without midpoints: 1 fails.
