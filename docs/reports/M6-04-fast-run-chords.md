# M6-04 report: chords in fast runs, toward the humans'

Builder's report. Branch `m6-04-fast-run-chords`, worktree `<wt>/m6-04`. Everything below was run; nothing is
claimed that was not.

## Commits (after the owner's history rewrite)

- `de9d26d` Quantizer: a chord inside a fast run (both neighbouring onsets under 120 ms) becomes its top note, on
  the guitar. This is the old `b324132` with the same files: the rewrite moved it.
- `a32e334` DESIGN 2.6: no chord inside a fast run, with the humans' chord share by speed, the note chosen, and
  the golden and stress results. M5-99's chord item narrowed.
- `f899f2f` Merge origin/main into the branch: M6-01's star power and the M6-05/M6-06 orders. One conflict, in
  `tests/test_assemble.py`'s imports; I kept both sides (`RUN_CHORD_S` and `SP_RULES`).

Files: `songcharter/quantize.py`, `songcharter/assemble.py` (only `_quantize` passes the guitar's setting, plus
the import line), `tests/test_quantize.py`, `tests/test_assemble.py`, `docs/DESIGN.md` 2.6 step 3,
`docs/work-orders/M5-99-later.md`. `reduce.py` is not touched: the lower levels follow Expert.

## 1. The humans, measured by local speed

Method. I read every chart only through `eval/scorer/score.py`'s reader (`scan`, `tracks_by_key`), and put it
on the primary's audio timeline with the alignment numbers in the runs' score JSONs. The human charts are 18
Expert guitar charts: the 6 references, plus 3 + 2 + 2 + 5 stress charts. Ours are the release candidate's runs,
`gate-rc` and `gate-rc-stress`. Each onset is binned by the larger of its two gaps to the neighbouring onsets, so
an onset counts as "in a run" only when both neighbours are close. Scripts:
`<scratchpad>/m6-04/measure.py`, `sim2.py`, `clusters.py`.

| both neighbours within | human onsets | chords | share | our onsets | chords | share |
|---|---|---|---|---|---|---|
| under 80 ms | 18,896 | 14 | 0.07 % | 2,568 | 151 | 5.9 % |
| 80–100 ms | 2,392 | 1 | 0.04 % | 658 | 8 | 1.2 % |
| 100–120 ms | 865 | 1 | 0.1 % | 166 | 13 | 7.8 % |
| 120–140 ms | 384 | 184 | 48 % | 347 | 122 | 35 % |
| 140–160 ms | 4,971 | 482 | 9.7 % | 3,107 | 294 | 9.5 % |
| 160–200 ms | 1,864 | 81 | 4.3 % | 1,253 | 189 | 15 % |
| 200–300 ms | 3,590 | 1,391 | 39 % | 2,588 | 1,434 | 55 % |
| 300 ms or more | 4,354 | 1,239 | 28 % | 2,238 | 693 | 31 % |

- **In beats**, with both neighbours under a 16th, the humans have 3 chords in 5,469 onsets. Between a 16th and
  an 8th they have 2,190 in 27,277, and slower 1,200 in 4,570. Our grid writes nothing under a 16th, so beats
  cannot separate our fast runs from our strums. The rule is therefore in ms.
- **Where ours and theirs part: under 120 ms.** We have 172 chords there (pm2 139, troop 17, sooth 14, All the
  Small Things 2); the humans have 16 in all. From 120 ms the humans strum chords: 181 of the 236 onsets at
  120–140 ms are on the rock stress song and Take Me Out.
- **pm2's fast chords are two runs of 90 chords in a row.** A "strum section" defined by shape (a chord with a
  chord beside it) would keep every one of them. So the rule tells a strum section by its speed instead.
- **troop's extra chords are mostly not in fast runs.** 85 of its 188 chords sit where both neighbours are 300 ms
  or more away (ours 0.51 of those onsets, the humans 0.22). Another 81 are at 140–160 ms (ours 0.16, the humans
  0.13).

## 2. The rule and why

A guitar chord whose previous and next kept onsets both lie less than 120 ms away (`RUN_CHORD_S`, seconds on our
grid) becomes one note, its top fret.

- It is applied after the chord limits, in `_frets`, before sustains and HOPO states are resolved.
- A chord at a run's start or end stays, as do a chord in a slower passage, a strum section of chords 120 ms or
  more apart, and the part's first and last onsets.
- Only the guitar part passes the setting (`assemble._quantize`); the default `QuantizeRules.run_chord_s` is 0,
  which turns it off.
- report.json's `parts.guitar.quantize.<level>` gains `run_chord_s` (the rule) and `run_chords` (how many chords
  it changed). Every part has the two fields; for bass and drums they are 0.

**Why 120 ms.** It is the bin edge where the human share jumps from 0.07–0.1 % to 48 %, so I took it as a measured
edge, not a tuned value. In the simulation, 100 ms reduces 159 chords and 120 ms 172. 140 ms would also take 120
of the rock song's strummed chords, which sit at 120–140 ms (break 0.805 → 0.557, the humans 0.64–0.67).

**Which note.** At the 172 chords the rule changes, the humans have 747 onsets within 50 ms; 740 of them are
single notes.

| choice | agrees with the human's single note |
|---|---|
| the chord's top fret | 231 / 740 (0.31) |
| the fret nearest the mean of the neighbours' lanes | 136 / 740 (0.18) |
| the bottom fret | 124 / 740 (0.17) |

pm2's 695 decide it (216 / 122 / 111); troop's 41 agree (15 / 14 / 13). In the simulation, every choice lowered
pm2's contour a little, and the top note lowered it least (0.003 on each chart against 0.006 for the other two).
I kept the top note.

**HOPO state.** The new single note takes its state as any single note does. By the guitar's "forced" rule that
is the natural state, so a HOPO after another fret.

## 3. Golden (references): passed

The "before" is the identical-code run explained under Uncertain. The "after" is
`golden run --out golden/m6-04-new --threads 2 --rerun bass` from the branch. The diff command was
`golden diff golden/m6-04-old golden/m6-04-new --expect guitar`, and its last line:
`golden diff: no UNEXPECTED change`.

- Engines that ran: bass on 7 songs, on both sides.
- Every pooled F1@50 is unchanged (guitar expert 0.8527, hard 0.8010, medium 0.7474, easy 0.6150; bass, drums
  and beat F1 unchanged).
- Changed parts, all expected:
  - All the Small Things' Expert guitar: 2 chords; chord share 0.7875 → 0.7847 (the human 0.7662, so toward it).
  - The test song's guitar on all four levels: 20 chords on Expert.
- The other five references are bit-identical, so their chord shares have not moved.
- report.md read. One side effect: All the Small Things' contour goes 0.704 → 0.698 (contour is not a golden
  line).

## 4. Stress set, before and after

The two runs are `golden/m6-04-stress-old` (identical-code before) and `golden/m6-04-stress-new` (branch,
`--rerun bass`). I scored both together with `eval/stress.py score`, against the same references. Then
`eval/stress.py compare old new` gave **Regressions: 0** (exit 0), and `golden diff` on the stress runs with
`--expect guitar` gave no UNEXPECTED change.

Our Expert guitar against each human chart:

| song | chords made one note | chord share | the humans | contour | jump-size distance | big fast jumps / min (the humans) |
|---|---|---|---|---|---|---|
| troop | 17 | 0.0864 → 0.0786 | 0.034–0.046 | 0.521–0.524, unchanged | 0.323–0.402 → 0.321–0.400 | 10.49 → 10.69 (27–42) |
| sooth | 14 | 0.0530 → 0.0466 | 0.044–0.063 | 0.674–0.679 → 0.675–0.681 | 0.090–0.128, unchanged | 2.11, unchanged (2.45) |
| break | 0 | 0.8054, unchanged | 0.640–0.670 | unchanged | unchanged | 0 (0–0.35) |
| pm2 | 139 | 0.1121 → 0.0648 | 0.021–0.038 | 0.520–0.561 → 0.516–0.558 | 0.189–0.252 → 0.177–0.227 | 8.92 → 9.20 (42–55) |

The rest is unchanged:
- every F1@50, F1@100, lowest window, timing error, 1-s peak, star power and solo number;
- bass and drums on every song;
- the beat and downbeat F1s.

pm2's per-note HOPO agreement falls by 0.003–0.006 (the new single notes follow the natural rule), and its HOPO
share goes 0.351 → 0.357.

**Against the order's lines:**
- troop's and pm2's chord shares move toward the humans' (0.02–0.05): **yes**. pm2 moves by 0.047 and troop by
  0.008; neither reaches the humans' range.
- break within a point of today's: **yes** (unchanged).
- every F1@50 not lower: **yes** (unchanged).
- the feel report's contour and jump measures not worse: **mostly**.
  - Jump-size distance: better on pm2 and troop.
  - Big fast jumps: up slightly, which is toward the humans' far higher rates.
  - Contour: **pm2's falls 0.003 on each of its five charts.** Against the primary that is 7 of 2,062 pairs:
    score.py reads a chord by its mean lane, and a single note in its place turns some "same" steps into steps up
    or down. troop's contour is unchanged and sooth's rises 0.001.

## 5. Tests, and breaking them

- `tests/test_quantize.py` has three new tests:
  - `test_a_chord_inside_a_fast_run_becomes_its_top_note`: at 200 BPM, a 2-note and a 3-note chord inside a run
    become their tops and play as HOPOs. These stay: a run's start, a run's end, a chord between 8ths, a strum
    section of 8th-note chords, and the first and last onsets. The report fields are checked; without the rule
    nothing changes.
  - `test_a_chord_in_a_run_of_16ths_under_120_ms`, parametrized at the edge: 126 BPM (119 ms) reduces 4 chords,
    including a 16th-note chord strum; 125 BPM (120 ms) keeps everything.
  - `test_run_chords`: the function on its own.
- `tests/test_assemble.py` has one new test, `test_the_guitar_part_makes_chords_in_fast_runs_one_note`: the
  guitar's levels carry 0.12 in report.json, and bass and drums carry 0.

I broke the code each way below; each break fails a test:

| break | result |
|---|---|
| bottom fret instead of top | 3 failed |
| previous gap only | 1 failed |
| next gap only | 3 failed |
| no gap test | 4 failed |
| first and last onsets too | 4 failed |
| `<=` instead of `<` | 1 failed |
| count not kept | 2 failed |
| rule not recorded | 1 failed |
| rule not called | 2 failed |
| assemble setting removed | 1 failed |
| setting on every part | 1 failed |

One mutant was equivalent: the `max_gap_s <= 0` guard changed nothing, because a gap is never below 0. I removed
the guard.

**Suite:**
- before the merge: `tools/heavy.sh .venv/bin/python -m pytest -q -p no:cacheprovider --basetemp=<shm>/pt-m6-04`,
  last line `1062 passed, 3 skipped in 807.33s (0:13:27)`;
- after merging main (`f899f2f`), the same command: `1071 passed, 4 skipped in 700.16s (0:11:40)`.

**CI:**
- run 42277566130 on the pre-rewrite `b324132` (same files as `de9d26d`): success. The linux suite gave
  `1061 passed, 4 skipped`, and the log line `all 8 Linux hooks passed`; windows passed too.
- the merged head `f899f2f`: run 42288587897 (<repo>/actions/runs/42288587897),
  **success**. Its head SHA is f899f2f. The linux suite gave `1071 passed, 4 skipped in 503.90s`, and
  `all 8 Linux hooks passed`; windows passed too. The change adds no hook of its own: its checks are suite
  tests, and CI runs the full suite.

## Uncertain, or not done as written

- **The "before" runs were reused, not rebuilt.** The brief asked for my own before, built from a detached
  worktree of the order's base. Instead I hard-linked M6-02's before runs (`golden/m6-02-old`,
  `m6-02-old-stress`) as `golden/m6-04-old` and `m6-04-stress-old`.
  - They were built from main before this order, whose code is identical to the base's: the base commit adds
    only the work order.
  - They used `--rerun bass`, `--levels all` and 1 take, from a clean checkout (`dirty: []`).
  - Their gates are all OK.
  - I broke the hard links on every file the scoring rewrites, and rescored the old stress run myself next to
    the new one.
  - It saved about 40 minutes of the shared machine. The orchestrator may prefer a fresh before.
- **The stress run recorded the pre-rewrite hash** `b324132` in its summary. It started before the rewrite
  reached my worktree; the files are identical to `de9d26d`.
- **pm2's contour falls 0.003 on each chart.** That is the one feel measure that moves away (above). Taking the
  rule anyway or not is the orchestrator's (and the owner's) call; I did not tune against it.
- **troop moves only 0.008.** Its extra chords are in slow passages and at 140–160 ms, where the humans chord too,
  so no speed rule reaches them. M5-99's item is narrowed to that, with a stem-based measure as the next step.
- **Untested ground.** A song with strummed 16th-note chords at 126–150 BPM (gaps of 100–119 ms) would have those
  chords thinned to single notes. Neither set holds such a passage, and the humans' 100–120 ms bin has only 865
  onsets (1 chord).
- **Lane agreement is exact-lane only,** and the humans agree with each other only loosely on lanes. The top
  note's lead comes almost all from pm2.
- **M5-99 was edited.** The brief lists "the work orders other than yours" as files not to edit, but the order
  names M5-99 among its files and asks for its chord item to be closed or narrowed. I edited that item only.
- **Privacy.** I scanned the branch diff and the commit messages: no lyrics, audio, model names (beyond the
  required trailer) or personal details. `eval/privacy_check.py` exited 0 before each push. No stress song's
  title, artist, charter or md5 is in this report or the commits.

## The orchestrator's decision and review fixes (commit 2ac96ae)

- **pm2's contour, 0.003 lower on each chart, accepted.** The order asked for the contour "not worse". The review
  confirmed the builder's reading: 18 of the 23 direction changes in our chart are a chord kept at a run's edge next
  to its own top note, which score.py reads by its mean lane; only 5 are between single notes. It is the measure's
  reading of a chord, not a contour the notes lost, against a chord share 0.112 -> 0.065 (the humans 0.021-0.038) with
  no F1 moved.
- **R1** (a test gap): no test held a source-forced state on a chord the rule changes; the rule moved after the HOPO
  flips passed every test and played a forced strum as a HOPO. New test
  `test_a_forced_strum_chord_in_a_fast_run_stays_a_strum_as_one_note`; it fails on that mutant.
- **R2** (docs and a test gap): on a tool's own lower levels (`take_difficulties: "all"`) the rule reads each level's
  own neighbouring onsets; DESIGN 2.6 now says so (our own lower levels still follow Expert through reduce.py). New
  test `test_a_tools_own_lower_level_is_read_against_its_own_onsets` on Expert, Hard and Medium; the rule on Expert
  only fails it on Hard and Medium.
- CI on 2ac96ae: green (run 42302868980; the linux suite and the hooks, Windows).

## Review (sc-reviewer, 2026-11-06)

Branch m6-04-fast-run-chords at f899f2f, diff 5e335c4...HEAD. Copies were broken in <shm>/review_m604 (now deleted).
No major findings. Two minor ones, both test gaps that a mutant survives.

## Findings

### R1 (minor, test gap): a source-forced state on a reduced chord is untested
`songcharter/quantize.py:641-647` (the rule runs before the flip loop at :648-665). Mutant M3 applies `run_chords`
to the output `FretNote`s *after* the flips are computed. All 52 tests in `tests/test_quantize.py` still pass, and so
does `test_assemble.py`, because the new tests only use unforced source notes: their flip is False whatever the order.
The mutant would ship a real defect, though. Take a 16th-run chord (1,3) that the source forced to strum, under the
guitar's "forced" rule at 200 BPM:
- real code: `[(1,), (2,), (3,), (2,), (1,)] ['strum', 'hopo', 'strum', 'hopo', 'hopo']`. The forced strum is kept.
- M3: `[(1,), (2,), (3,), (2,), (1,)] ['strum', 'hopo', 'hopo', 'hopo', 'hopo']`, and `52 passed`. The forced strum
  plays as a HOPO.
The fix is a test: a chord with `hopo=False, hopo_forced=True` inside a run keeps its strum as a single note.

### R2 (minor, doc and test gap): the rule on imported lower levels
`songcharter/assemble.py:1388-1389`. The rule is set for every level `_quantize` takes. With `take_difficulties: "all"`,
the tool's own Hard, Medium and Easy are therefore each thinned by *their own* neighbours. A Hard chord whose Hard
neighbours are 120 ms or more away keeps its chord at a tick where Expert lost its chord. check_reductions has no chord
nesting check, so nothing flags it. DESIGN 2.6 (`docs/DESIGN.md:781`) says "the lower levels follow Expert
(reduce.py)", which is true only for `"expert"`, the default and the friend's config.

Mutant M2 makes the rule change chords on Expert only, while report.json still records it on every level. It passes
`test_quantize.py` and `test_assemble.py`: `test_the_guitar_part_makes_chords_in_fast_runs_one_note` checks only that
Hard records 0.12 and that `run_chords` is an int. Either behaviour may be what is wanted. Say which one in DESIGN, and
assert the Hard count in the fixture.

## Lens 1, checked and sound
- The gaps are measured to the kept onsets, after the spacing drop and the chord limits, on grid seconds. The first
  and last onsets are exempt, and 0 turns the rule off.
- The new note's sustain is the chord's (it is dropped anyway at gaps under 120 ms). Its HOPO is natural unless the
  source forced it. Its lane is `max`, which is never open (limit_chord removes the open from a chord).
- Notes accounting (`check`) holds. The rule is deterministic.
- In `"expert"` mode, reduce.py takes each chord's shape from the level above, so no lower level can gain or keep a
  chord Expert lost.
- `git merge-tree --write-tree 80a3c1f f899f2f` exits 0 with tree 25cc931 and no conflicts. The merged `_quantize`
  applies part_rules first, then the guitar's run_chord_s.

## Lens 2, the numbers
- I re-summed the builder's `measure.json`. The humans have 18 charts and 16 chords in 22,153 onsets under 120 ms.
  Every bin of both tables matches DESIGN. The 120 ms simulation reduces 172 chords, and the agreement is
  top 231, nearest 136, bottom 124, all of 740 (the 747 in the brief counts the 7 human chords).
- The pm2 contour reading is confirmed. Against the primary, the confusion matrix (ref/cand) moves +0/+0 252→241,
  +0/+1 112→116, +0/-1 156→163, +1/+0 140→136 and +1/+1 448→452: net −7 of 2,062 pairs.
- In our own chart, 23 steps change their mean-lane direction. 18 of them are a kept run-edge chord next to its own
  top note (same → up or down), and only 5 are between notes. So the drop is mostly the measure's reading of a chord,
  as the builder says.
- The before runs are at f3b9ebb and the after runs at b324132, whose code equals de9d26d's. Both are clean and
  both predate M6-01.
- 5e335c4's code differs from f3b9ebb's only by M6-01's star power (`starpower.py`, and `sp_record` in
  `assemble.py`), which does not touch the notes. So before and after are a like-for-like pair, but neither run is
  5e335c4's code, and the merged head itself had no golden run (CI only).

## Lens 3, test the tests (my mutants)
| mutant | result |
|---|---|
| M1: record run_chord_s only when a chord changed | fails |
| M2: change chords on Expert only | **survives** (R2) |
| M3: apply the rule after the flips | **survives** (R1) |
| M4: count the frets removed, not the chords | fails |
| M6: only chords of 3 or more notes | fails |
