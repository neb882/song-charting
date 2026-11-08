# M7-09: the halved grid's tempo shape (the builder's report)

Branch `m7-09-halved-line` (worktree <wt>/m7-09), from main c32f750. Builder's report.

## Commits

| commit | what |
|---|---|
| 2054c68 | beatgrid: `line_test`, a straight line through `start=` beats tested against them (+ 2 tests) |
| 236e39d | assemble: the halving pass takes the line test; `first_tempo_windows` and its warning (+ 2 tests, 3 updated) |
| 63adee1 | tests: the first-tempo windows skip a window with under 4 beats |
| 88f490d | DESIGN 2.3 step 7 ("The halved grid's tempo shape"), M5-99 |

## What changed

1. **`beatgrid.beat_grid(line_test=False)`** (candidate b, as in eval/m7/m709/measure.py's inserted block). With
   `start=` and `line_test`, a robust straight line through the start beats (by index, unit weights, extended over
   the song from its first beat at or after 0 s) is the start grid unless the start beats' confident share is
   `TRACKER_MARGIN` (0.10) above the line's: the first pass's test, with `keep_line` not applying (the halving pass
   passes `keep_line=True`; had it applied, the line would always win). When the line wins, the grid is built as
   the first pass builds around its line (click under `FREE_SHARE`, free above). `stats["start"]` gains `bpm`,
   `first_beat` and `line_confident_share` beside `tracker_confident_share` and `grid`, the first pass's keys.
   Without `line_test` (every other caller) nothing changes; the condition is written `(start is not None or not
   keep_line)` so `line_test` can never override the first pass's `keep_line`.
2. **`assemble._halving_pass`** calls the second pass with `line_test=True`; the second-pass lambda in `assemble()`
   takes and forwards `line_test` (default False). The doubling's start from allin1 (M6-05) does not take the test
   (its line already missed a tempo change; on pm2 the final grids' shares, 0.726 from allin1 against 0.702 from
   the line, are closer than the 0.10 margin, so the test would likely have undone M6-05: an inference, not run). The brief named only the halved pass; this is my reading of it.
3. **The "tempo halved" warning** now says which start the grid kept: "... and the grid follows them" (allin1's
   beats, unchanged text) or "... and the grid follows the straight line through them". Not asked by the brief; a
   wording change only, so that the warning is not false on a line grid (the video-review check's item 2.4 made
   the same point about another warning).
4. **`assemble.first_tempo_windows(first, halved)`** (ratio_guard.py's narrow form): per 20-s window every 5 s
   from 0 s while a window ends before the halved grid's last beat (ratio_guard's loop), the halved grid's median
   beat period over the first grid's, windows with under 4 beats of either skipped; |ratio - 1| <= 0.10 flags the
   window; overlapping flagged windows merge into spans. Constants `HALVED_TEMPO_WINDOW_S`, `HALVED_TEMPO_HOP_S`,
   `HALVED_TEMPO_BACK`. Recorded as `octave_stats.halving.first_tempo` (windows [start, end, ratio], spans,
   parameters) whenever a halved grid was built; a kept halved grid warns "the halved grid runs at the first
   grid's tempo at X-Y s: check sync" once per span (times: the beats' seconds of the input, `{:.0f}`).
5. **Docs:** DESIGN 2.3 step 7 (a new block: cause, rule, the measurement's table, the warning, what was not
   built, the build's checks, the line's limit; a pointer in the halving rule; the Goal 2 note on `start=`);
   M5-99 (correcting such a window is M8's; the index fit is open). PROGRESS.json left to the orchestrator (not in
   the brief's doc list; another builder runs in parallel).

## Checks

- **The suite** (`SONGCHARTER_HEAVY_MIN_FREE_GB=1 tools/heavy.sh python -m pytest -q -p no:cacheprovider
  --basetemp=<shm>/pt-m7-09`, from the worktree, scan-chart from <wt>/base-main, the gate script's variables), on
  88f490d: `1153 passed, 5 skipped in 750.62s (0:12:30)`, exit 0.
- **CI** on the branch head 88f490d (`gh workflow run ci --ref m7-09-halved-line`): run 42492131587,
  <repo>/actions/runs/42492131587, conclusion success, headSha 88f490d; windows
  success, linux success (its suite `1154 passed, 4 skipped in 538.46s`, the same 1158 tests; hooks 10-lanes to
  75-update all ok; this order adds no hook: its checks are suite tests).
- **In process on the kept folders** (eval/m7/m709/measure.py's way, through tools/heavy.sh; script
  <scratchpad>/m7/m7-09/check.py): the first grid, the real `assemble._octave_pass` with no onsets (the density
  test keeps octave 1, so the halving pass runs as in a build), `with_downbeats` from allin1, the tempo map; once
  with main's code (<wt>/orch at c32f750, the branch point) and once with the branch.

  | song | main: start, mode, tempo map | branch: start (line / allin1 share), mode, tempo map | beats and downbeats | first-tempo spans |
  |---|---|---|---|---|
  | `sooth` (stress) | allin1, free, 64 markers 68.1-80.0 | allin1 (0.330 / 0.807), free, 64 markers 68.1-80.0 | identical (689) | none |
  | s02 | allin1, free, 209 markers 55.1-154.8 | allin1 (0.152 / 0.574), free, 209 markers | identical (476) | 225-300 s (12 windows, 0.997-1.054) |
  | s04 | allin1, free, 116 markers 61.6-78.3 | allin1 (0.204 / 0.871), free, 116 markers | identical (350) | none |
  | `ntl` | allin1, free, 35 markers 74.3-86.9 | **line (0.549 / 0.578), click, 1 marker at 75.0** | 251 -> 264 beats (the line runs from 0 s to the end) | none |

  On `sooth`, s02 and s04 every grid stat (tempo check, drift, evidence ratio) is the same as main's; s02 gains
  the first-tempo warning. `ntl`: the halved fold's tempo-check window (main 1) is gone; drift p95 4.99 -> 4.04 ms;
  the guitar take's notes through the real offset and quantizer, distinct ticks off the 48-tick grid in 19-33 s
  of our earlier chart (audio 14.1-29.7 s): main 8 of 41, branch **0 of 41**; elsewhere 5 of 448 -> 4 of 448.
  The measurement's b gave the same (0 of 41, 4 of 448, 75.0 BPM, 1 marker).
- **A real chart of `ntl`** from its work folder with the branch (`tools/heavy.sh python -m songcharter.cli chart
  <shm>/ntl/song.mp3 --work <shm>/ntl/work --out <shm>/m7-09/ntl --levels expert --takes 1 --device cpu`, every
  engine stage reused; exit 0; the output deleted after): gate ok; octave 0.5, 74.9997 BPM, click ("confident
  share 0.55 < 0.60"); `grid.stats.start` = line, its 75.0022 BPM, first beat 0.1312, line share 0.5492, allin1's
  0.5777; tempo map **1 marker, 75.0 BPM** (max error 0.921 ms); tempo check empty; `octave_stats.halving.
  first_tempo` no windows, no spans. Warnings: "tempo halved to 75.0 BPM: ... and the grid follows the straight
  line through them: check sync"; "grid mode click chosen on a thin margin (confident share 0.549 against 0.6);
  grid_mode overrides it" (new for this song: the first pass's existing warning for a line start within
  `MODE_MARGIN` of `FREE_SHARE`); and a drums-onsets-over-silence note as before. In the written notes.chart, the
  Expert guitar's distinct ticks off the 8th grid in the intro window: **0 of 41** (4 of 446 elsewhere).
- **Made-up tests** (tests/test_beatgrid.py): a 75 BPM click whose drums enter at 30 s and whose start beats run
  ahead 75 -> 87 -> 75 BPM over 12-24 s (2 beats gained) keeps the line (shares recorded), one tempo marker at 75.0,
  the intro on the click; without the test, over 10 markers up to 85+ BPM and the intro 0.3 s off. A 70 -> 84 BPM
  change with drums throughout keeps the start beats (share 1.0 against the line's 0.19), beats, downbeats and
  every other stat identical to the path without the test. (tests/test_assemble.py): `first_tempo_windows` on a
  halved grid whose last 28 s run at the first grid's tempo (span 260-295 s), two stretches (90-140, 260-295),
  clean grids (none), a real tempo change both grids follow (none), the 10 % edges, the under-4-beats skip; the
  halving pass records it and warns once per span when kept, not when refused; the call records `line_test=True`
  for the halving and the beat_grid spy sees it in a real build.
- No golden or stress runs (the brief: the orchestrator's, after the review).

## The breaks (each run against tests/test_beatgrid.py and test_assemble.py, -k halved_start or halv or first_tempo or back_at or allin1 or octave or pulse: 31 tests)

| break | tests that failed |
|---|---|
| B1 no line test (start beats always) | drumless wander, real tempo change, pulse song e2e |
| B2 keep_line applies to the line test | real tempo change |
| B3 no TRACKER_MARGIN in the comparison | drumless wander, pulse song e2e |
| B4 the line not moved to its first beat at 0 s | drumless wander |
| B5 the halving pass without line_test | twice-allin1 (call record), halved words (beat_grid spy), pulse song e2e |
| B6 the assemble lambda drops line_test | halved words (spy), pulse song e2e |
| B7 the ratio read against 2, not 1 | first_tempo_windows, warns once per span, twice-allin1, pulse song e2e |
| B8 windows not merged into spans | first_tempo_windows, warns once per span |
| B9 windows with under 4 beats not skipped (< 2) | first_tempo_windows |
| B10 no first-tempo warning | warns once per span |
| B11 the first-tempo warning on a refused grid too | warns once per span |
| B12 the "tempo halved" warning always "follows them" | twice-allin1, pulse song e2e |
| B13 first_tempo recorded only when kept | warns once per span |

Every break failed at least one test; the tree was restored after each (git status clean).

## Uncertain, not done

- **s02's warning span.** The build flags s02 at 225-300 s (12 windows, ratios 0.997-1.054). The measurement's
  report says 225-265 s in its ratio-guard paragraph and 245-300 s in the decision; the code follows the decision's
  rule (ratio_guard's loop, |ratio - 1| <= 0.10) and the first grids are identical to the measurement's, so I take
  the build's number and wrote it into DESIGN. The span is where s02's human charts disagree by an octave.
- **The owner's sooth file** (the warning's real target) has no kept folder; it was checked only by the
  measurement's simulation, not here. The made-up tail test covers the mechanism.
- **The index line's robustness.** In a made-up 75 BPM click whose start beats gain 2 beats over the first 30 s, the
  line holds 75.0 BPM at 120 s of song but reads 76.0 at 90 s (and then the start beats win: today's grid, no
  regression). ntl's case is like the 120-s one. Noted in DESIGN and M5-99; a more robust fit is not built.
- **The pulse song e2e test** (made-up click) now keeps the line; its expectations were updated (the start grid,
  the warning wording, no first-tempo window).
- No golden or stress runs (the orchestrator's, after review). The charting path changed for halved songs only:
  sooth's and s02/s04's grids are identical by the in-process check; ntl changes on purpose.
- Scanned `git diff main...HEAD` and the commit messages for lyrics, audio, model names and personal details:
  only the required trailers. `EVAL_DATA=$DEV/eval python3 -I eval/privacy_check.py`: 0 found, exit 0.
- **Main moved** by one commit after the push (3e6911b, the M8 contour spike: its report, eval/m8/contour/, PROGRESS
  and the reports README), touching none of this branch's files. Not merged in, so that the green CI run stays on
  the branch head (88f490d); a `git merge origin/main` merges cleanly if wanted.
- `ntl`'s work folder vanished once (a container restart wiped `/dev/shm` at about 14:09 UTC); the orchestrator
  restored it, and both ntl checks ran on the restored folder. Left in place, with our earlier chart of it.

## Review fixes (2026-11-08, after the review: no major, two minor test gaps)

Commit f01d623 (tests only: tests/test_assemble.py, tests/test_beatgrid.py).

- **F1: the doubling's start from allin1 skips the line test.** `test_a_doubled_grid_follows_a_tempo_change_from_
  allin1s_beats` spies on assemble's `beat_grid` in the doubled build: 3 calls (the first pass, the doubled line,
  the doubled pass from allin1), and the one with `start` has `line_test` falsy, at the doubled range (170, 370)
  with the half-beat test. Break R1 (the second-pass lambda's default `line_test=True`): that test fails
  (`assert (3 == 3 and 1 == 1 and not True)`).
- **F2: the line runs to the song's end.** The drumless-wander test asserts the last start beat is over 1.5 s
  before the end and the line grid's last beat is within one period (0.8 s) of `dur`. Break R8 (the line ending at
  `tracker[-1]` instead of `dur`): that test fails (last start beat 118.03 s, last grid beat 117.99 s of 120).
- Both breaks were run through tools/heavy.sh and the tree restored (git status clean).
- tests/test_assemble.py and tests/test_beatgrid.py in full: `129 passed in 145.44s`.
- Scan of the new commit: only the trailers; privacy_check 0 found, exit 0.
- CI on f01d623: run 42498691598, <repo>/actions/runs/42498691598, success (windows success, linux success, its suite `1154 passed, 4 skipped in 382.45s`).

---

## The review


No major findings. Two minor test gaps, plus one note on the measurement doc.

### Findings

- **F1 (minor): nothing tests that the doubling's allin1 start skips the line test.**
  - Where: songcharter/assemble.py:1792, the second-pass lambda's `line_test=False` default.
  - Break R1: change that default to `line_test=True`. In a real build this puts M6-05's doubled start from allin1 (assemble.py:1705) on the line test.
  - Result: all 38 selected tests in test_beatgrid.py and test_assemble.py pass. That includes the stretch-song doubled build and the beat_grid spy, which only sees the first pass and the halving.
  - Why the tests miss it: the direct-call tests use fake `second` functions. Test 1787's fake has no `line_test` parameter, so it guards `_octave_pass`'s call, not the lambda.
  - Impact not measured: pm2's kept folder points its stems at a folder that no longer exists (LibsndfileError opening .../stress-work-pm2/pm2/stems/.../drums.wav).
  - Fix: spy on beat_grid in a doubled build that starts from allin1, and assert that call has `line_test` falsy.
- **F2 (minor): nothing tests that the line runs to the song's end.**
  - Where: songcharter/beatgrid.py:822, `line = first + arange(floor((dur - first)/b)+1)*b`.
  - Break R8: end the line at the last start beat instead (`tracker[-1]` for `dur`). The same 38 tests pass.
  - Probe on a made-up 120-s, 75 BPM song with 12 start beats (the first 9.6 s): the branch builds a line grid of 150 beats (max error 9.2 ms). Under R8 it has 11 beats, and the song after 9.6 s has no grid.
  - Fix: in the drumless-wander test, assert the line grid's last beat is within one period of `dur`.
- **Note (doc on main, not in this diff):** docs/reports/M7-09-measure.md says s02's narrow flag is at "225-265 s" (lines 175-177) and gives "8 windows at 245-300 s" (line 162). The measurement's own ratio_guard.json, on candidate b, flags 225-245 through 280-300 at ratios 0.997-1.054, which is 225-300 s. So DESIGN's 225-300 s is right and the report under-states it (its print was cut to 8 windows).

### What I checked and found sound

- **Line test.** The code reduces to the old expression without `line_test`, and `keep_line` is not applied to the line test.
- **Probes on made-up songs** (the line test against the start beats alone):
  - 10 start beats missing: the start beats win, same as today.
  - allin1's beats doubled for 10 beats: the start beats win, same as today.
  - Start beats covering only the first 10 s: the line covers the song, an improvement.
  - Repeated runs give identical beats and stats.
- **The builder's 76.0 limit.** Fine as documented: when the line is off, it falls back to today's grid.
- **Doubled path, branch against main in process on the kept folders:**
  - troop (octave 2, second start: line): 1027 beats, downbeats and warnings identical.
  - s04: 350 beats identical, first-tempo spans `[]`.
  - pm2 could not be run (see F1).
- **Ratio warning.** It runs only inside the halving pass, so unhalved songs never get it. The builder's log shows no spans on sooth, s04 or ntl, and spans 225-300 s on s02.
- **My breaks:** R2 (start beats win unless the line leads by 0.10), R4 (skip a window only when both grids are thin), R5 (the last window dropped), R6 (tolerance doubled) and R7 (warn on the first span only) each fail tests. R1 and R8 leave them green.
- **DESIGN 2.3's new block and M5-99** match the code and the measurement.

The orchestrator's routing: F1 and F2 closed by the builder (tests only, each failing on its break; CI green on f01d623); the doc note fixed on main (19cd50d). pm2's kept folder carries its stems under stems/<key> beside a pipeline.json written under an older work root: golden runs resolve the stems inside the work folder and are not affected.
