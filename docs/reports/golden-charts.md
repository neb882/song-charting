# Report: golden charts (`eval/golden.py`)

Worktree `S/wt/golden`, branch `golden` from `main` (11615e2). Not pushed. S below is
/tmp/claude-0/-home-user/5307d417-c453-5e74-8f13-b43b2df06ab1/scratchpad.

## Commits (on `golden`)

| commit | what |
|---|---|
| 2e755db | `eval/golden.py` (run, diff), the track hash in `eval/scorer/scan_notes.cjs`, `tests/test_golden.py` |
| 299f93a | the kept folders' own format number (`KEPT_FORMAT`), the commits recorded as a run starts, sharper tests |
| 0947cee | fix: a changed file's name lost its first character in the summary's `dirty` list (porcelain output stripped) |
| 0cdfbab | docs: CLAUDE.md release gate, sc-inspector, eval/README, DESIGN 3.6 and §11, PROGRESS; a detached checkout shows no branch name |
| c597b48 | docs only: the real `--rerun` results and their cost (DESIGN 3.6, eval/README, sc-inspector) |

Files: `eval/golden.py` (new, 854 lines), `tests/test_golden.py` (new, 24 tests), `eval/scorer/scan_notes.cjs`
(+hash, +scan-chart beside `$SONGCHARTER_SCAN_CHART`), `CLAUDE.md`, `.claude/agents/sc-inspector.md`,
`eval/README.md`, `docs/DESIGN.md`, `docs/PROGRESS.json`. Nothing under `songcharter/` changed.

## What the commands do

**`python -m eval.golden run --out DIR [--code CHECKOUT] [--rerun drums,bass,sections,guitar] [--songs ids]
[--refs DIR] [--work DIR] [--stems DIR] [--threads N]`**, run from a checkout's root.

- The reference set: `refs/songs.json` (6 songs with human charts) plus `refs/test_song` when its input.wav exists.
  `--refs` defaults to `$EVAL_DATA/refs` (else eval/data/refs, as takes.py).
- Each song is built by `python -m songcharter.cli chart <refs>/<id>/input.wav --out <out>/<id> --work <private>
  --takes 1 --device cpu --no-preview --levels all --title .. --artist .. [--threads N]`, from the checkout `--code`
  (default: this one; cwd and PYTHONPATH are the checkout, and a probe checks `songcharter` imports from it). `--code`
  is how the baseline was built from `main`, which has no golden.py.
- **Kept folders**: `<work>/<id>` (default `$SONGCHARTER_GOLDEN/work`, else `<user cache>/golden/work`). When a run
  finds one missing or unfinished (no `golden.json` marker), under a per-song `flock` it hard-links the stems from
  `--stems` when separate.py's `cache_key` of the decode (computed with separate()'s own defaults) has a folder there
  with every stem as long as the decode; then builds into it (`--work <kept>`, Expert only, output thrown away),
  deletes autochart's scratch folder (`guitar/work`), and writes `golden.json` last.
- **Each build's own folder** `<work>/.runs/<pid>-<hex>/<id>`: decode.wav and stems/*.wav hard-linked, decode.json,
  info.json and every engine folder copied (minus `--rerun` engines and `guitar/work`). Reason: an engine whose cache
  misses writes in place (`engine.json` by write_text, stems by soundfile), which through a link would reach the kept
  file. A manifest (size, mtime_ns, inode) of every kept file is taken before the build and compared after; any change
  fails the song (exit 1). The build's `SONGCHARTER_CACHE` is forced to an empty folder of the run's, so its prune
  touches nothing. `SONGCHARTER_SCAN_CHART` and `SONGCHARTER_AUTOCHART` are resolved once and passed to every build,
  so old and new use one scan-chart and one autochart install. An output folder is locked (`<out>/.golden.lock`,
  non-blocking: a second run into it exits 2).
- **Writes** `<out>/<id>/` (or `<id>.failed`), `<out>/summary.json`, `<out>/logs/<id>.log` and `.pipeline.json`,
  `<out>/scores/<id>.score.json`. summary.json: `songs` (per song: exit, gate, delay/chart_offset, playable, issues,
  per part and difficulty onsets / notes / hash, and for has_ref songs the F1@50, F1@100 (P, R, matched, n_ref,
  n_cand) per part and difficulty, the beat F1 and the lag); `code` (commit, dirty tracked files); `options`;
  `tools` (scan-chart version, SHA-256 of scan_notes.cjs and score.py); `run` (everything that varies: times per song
  and stage, cold or warm, the engines that ran and those that ran unasked, which commit made the kept folder, paths).
- **The hash** is scan-chart's own `calculateTrackHash` (Chorus Encore's track hash: resolution, tempos, time
  signatures, star power, solos, flex lanes, drum fills, every note's tick, length, type, flags), computed by
  scan_notes.cjs on its parse with the song.ini modifiers. The chart's delay (song.ini delay, .chart Offset), which it
  leaves out, is recorded beside it and compared.
- `--rerun` leaves the named engines' folders out of the build's folder, so they run there; the kept ones are not
  touched. Exit 0 all built (a gate failure is recorded), 1 a build failed or a kept folder changed, 2 bad input.

**`python -m eval.golden diff OLD NEW --expect PARTS [--out DIR]`**: OLD/NEW are summary.json files or their folders.
`--expect`: `none` or comma-separated `part` / `part:difficulty`. Per song, part and difficulty: unchanged; changed
(hash differs, or present on one side, or the song's delay changed) and expected; else UNEXPECTED. Song-level
UNEXPECTED: only in one summary, exit or gate changed, build failed on both sides. Writes report.md (a header table:
commits, engines asked to rerun, engines that ran, kept folders made in the run and by which commit; the verdict;
the pooled F1@50 table per part and difficulty, 2·Σmatched / Σ(n_ref + n_cand), plus beat F1; a table per song:
status, onsets old → new, F1@50 old → new) and report.json. Exit 0, 1 when anything is UNEXPECTED, 2 when the
summaries cannot be compared (missing, not a summary, another format, bad --expect).

## Checks

Environment for every real run: `SONGCHARTER_SCAN_CHART=/home/user/song-charting/tools/scan-chart/scan.cjs
SONGCHARTER_AUTOCHART=S/eval/tools/autochart SONGCHARTER_ALLIN1_PYTHON=S/research/timing/venv2/bin/python`,
`--threads 2` (torch, OMP, OpenBLAS, MKL, numba at 2).

### The full suite

`SONGCHARTER_SCAN_CHART=/home/user/song-charting/tools/scan-chart/scan.cjs S/venv/bin/python -m pytest -q -p no:cacheprovider --basetemp=/dev/shm/pt_golden`
in S/wt/golden:
- at 0cdfbab (final): `500 passed, 3 skipped in 459.31s (0:07:39)`
- at 0947cee: `500 passed, 3 skipped in 457.52s (0:07:37)`
- `main` in the fresh worktree before any change: `476 passed, 3 skipped in 477.67s`. The 24 new tests all run
  (`tests/test_golden.py`: `24 passed`); the 3 skips are main's.

Tests break-checked: 35 mutations of golden.py (onset counting, empty tracks, hash ignored, both --expect matchers,
unknown part allowed, diff exit always 0, missing song / gate change / both failed / delay ignored, pooled formula,
pair order, bold UNEXPECTED, stems copied, engines linked, no manifest check, no song lock, scratch kept, private
cache not forced, no length check in seeding, never finished, cached counted as ran, --rerun ignored, private folder
not removed per song, output lock, apart check, kept build at all levels, identical always, expected-but-unchanged
empty, scores skipped, seeding copies, results include `run`, dirty stripped, detached named) and one of
scan_notes.cjs (a constant hash): every one fails a test (S/golden/mut/mutate.py, logs in S/golden/mut/). Three
initial survivors led to sharper tests; one (a redundant `none` check) was an equivalent mutant and the code was
removed.

### A baseline exists

`cd S/wt/golden && S/venv/bin/python -m eval.golden run --code S/wt/golden-main --refs S/eval/refs --work S/golden/work --stems S/sepcache/cache --threads 2 --out S/golden/base`
(S/wt/golden-main: a detached worktree of main at 11615e2, removed afterwards). Last lines:

```
  test_song: cold: kept folder made in 1081 s, then built in 82 s, gate OK; every engine cached; 1164 s in all
summary: S/golden/base/summary.json (4664 s)
real	77m44.317s
exit 0
```
S/golden/base/summary.json: code 11615e29fc9e…, dirty [], 7 songs, all exit 0, gate OK, 84 part-levels. Its `run`
section's `golden.dirty` shows "claude/agents/sc-inspector.md": that run used the tool before the 0947cee fix (the
docs were uncommitted then); the `run` section is informational only.

Pooled F1@50 on main: guitar Expert 0.8527 (6 songs), Hard 0.8010, Medium 0.7474, Easy 0.6150 (4); bass Expert
0.8247 (5), Hard 0.7881, Medium 0.7920, Easy 0.6964; drums Expert 0.9617 (5), Hard 0.9237, Medium 0.8787, Easy
0.7696; beat F1 0.8755 (6). Take Me Out: guitar 0.909, bass 0.912, drums 0.944, beat 0.9615, the same as DESIGN
§3.5's pipeline run.

**Time per song** (dev container, CPU, 2 threads; stems hard-linked from S/sepcache, so no separation ran):

| song | audio | cold: kept folder made | of which guitar / sections | warm: build | warm: whole song (build + scan + score) |
|---|---|---|---|---|---|
| kimochi_warui | 288 s | 785 s | 504 / 130 s | 53 s | 61 s |
| drunk_drivers | 225 s | 474 s | 253 / 105 s | 43 s | 50 s |
| take_me_out | 241 s | 598 s | 341 / 122 s | 45 s | 53 s |
| all_the_small_things | 175 s | 564 s * | 367 / 96 s | 37 s | 44 s |
| lucretia | 240 s | 809 s | 553 / 116 s | 45 s | 53 s |
| creep | 240 s | 514 s | 265 / 114 s | 44 s | 52 s |
| test_song | 412 s | 1081 s | 650 / 188 s | 75 s | 76 s |
| the set | | 4825 s (80 min) | | | 388 s (6.5 min) |

\* made in the one-song smoke run just before the baseline (same code, main 11615e2); in the baseline it was warm (46 s).
Warm columns from the first warm run (main_w1). A cold song in `run` costs the kept folder plus one warm build.

### Determinism

Two warm runs of main (`run --code <main> --out /dev/shm/golden/main_w1`, then `main_w2`):
```
14:09:49 run main_w1 exit 0, 389 s
14:16:24 run main_w2 exit 0, 395 s
14:16:24 diff /dev/shm/golden/main_w1 /dev/shm/golden/main_w2 --expect none: exit 0
results identical: True
14:16:25 diff S/golden/base /dev/shm/golden/main_w1 --expect none: exit 0
results identical: True
```
"results identical" is `golden.results()`: the whole summary but `run`, canonical JSON, byte-equal. So the cold
baseline equals both warm runs too. (main_w2 overlapped the full suite run, hence 395 s.)

### The diff catches a change

Scratch branch `golden-scratch` (from golden), one line in `songcharter/reduce.py` `_reduce_frets` step 5:
`flip=natural != want` → `flip=natural != (want or level == "Hard" and upper.instrument == "DoubleBass")` (every
bass Hard note a HOPO; gate-safe: scan-chart has no HOPO issue and our checks allow HOPOs on Hard; Medium/Easy take
lanes and HOPO states from Expert, not from Hard). Run `run --code S/wt/golden-scratch --out /dev/shm/golden/scratch_seq`:
```
14:22:55 run scratch_seq exit 0, 390 s
golden diff: no UNEXPECTED change; report: /dev/shm/golden/d_base_scratch_basshard/report.md
14:22:55 diff S/golden/base /dev/shm/golden/scratch_seq --expect bass:hard: exit 0
golden diff: UNEXPECTED: 7 (kimochi_warui: bass hard; drunk_drivers: bass hard; take_me_out: bass hard; all_the_small_things: bass hard; lucretia: bass hard; creep: bass hard; ...); report: /dev/shm/golden/d_base_scratch_guitar/report.md
14:22:55 diff S/golden/base /dev/shm/golden/scratch_seq --expect guitar: exit 1
```
Tally from report.json: `--expect bass:hard`: 84 rows, `('changed','bass','hard'): 7`, the other 77 unchanged, no
song-level findings. `--expect guitar`: `('UNEXPECTED','bass','hard'): 7`, nothing else. Bass Hard HOPOs: Take Me
Out 0 → 540 of 540 notes, Creep 50 → 590 of 590; onsets unchanged, so the pooled F1 is +0.0000 everywhere (onset F1
does not see HOPOs). Branch and worktree deleted (`Deleted branch golden-scratch (was 2eb6e81)`); the run's outputs
deleted from /dev/shm (the reports, summaries and logs kept in S/golden/checks/, 576 KB).

### Two checkouts, one after the other and at the same time

One after the other: the baseline / main_w1 (old, main through `--code`) and scratch_seq (new). At the same time:
`main_con` (S/wt/golden's golden.py, `--code` main) and `scratch_con` (the scratch checkout's own golden.py, no
`--code`), started together, both warm on the same kept folders:
```
14:22:55 fingerprint before
217 files, 4.55 GB (apparent), runs folder entries: 0
14:23:10 run main_con start
14:23:10 run scratch_con start
14:29:49 run scratch_con exit 0, 399 s
14:29:49 run main_con exit 0, 399 s
217 files vs 217 files; differing: 0
14:30:06 fingerprints compared: exit 0
14:30:06 diff /dev/shm/golden/main_w1 /dev/shm/golden/main_con --expect none: exit 0
results identical: True
14:30:06 diff /dev/shm/golden/scratch_seq /dev/shm/golden/scratch_con --expect none: exit 0
results identical: True
```
The fingerprint (S/golden/fingerprint.py) is every kept file's size, mtime_ns, inode, link count and SHA-256. All 42
kept stem WAVs have link count ≥ 2 (linked to S/sepcache). `<work>/.runs` empty afterwards. A cold kept folder raced
by two runs is tested with stand-ins only (`test_two_runs_at_once_make_a_kept_folder_once`: one prepare per song).

### --rerun with the real engines

From S/wt/golden at 0cdfbab (no `--code`; songcharter/ is identical to main), kept folders fingerprinted before and
after (S/golden/rerun.sh, log in S/golden/checks/rerun.log):
```
217 files, 4.55 GB (apparent), runs folder entries: 0
14:38:27 rerun3 start                      # run --rerun drums,bass,sections (all 7 songs)
15:02:34 rerun3 exit 0
golden diff: no UNEXPECTED change; report: /dev/shm/golden_rerun/d_base_rerun3/report.md
15:02:34 diff base rerun3 exit 0           # --expect none; report.json identical (songs): True
15:02:34 rerun_g start                     # run --rerun guitar --songs all_the_small_things
15:06:42 rerun_g exit 0
guitar rerun: ATST entry identical to the baseline's: True ; ran: ['guitar'] ; stage seconds: {... 'guitar': 211.23, 'assemble': 14.67}
217 files vs 217 files; differing: 0
15:07:01 fingerprints compared: exit 0
```
report.md's "engines that ran" row: "drums on 7 songs, bass on 7 songs, sections on 7 songs". So the engines are
deterministic when rerun (a precondition for `--rerun` being useful), and a rerun leaves the kept folders alone.
Cost: drums+bass+sections 149–301 s a song warm (24 min for the set) against 44–76 s; a guitar rerun is the whole
autochart run (211 s for the 2:55 song; the cold guitar stages were 253–650 s).

### Docs

- CLAUDE.md release gate step 2: the three commands (`run --code /dev/shm/golden-old ...`, `run ... --rerun`,
  `diff ... --expect`), must exit 0.
- `.claude/agents/sc-inspector.md` step 3: the three commands with /dev/shm/inspect paths, the environment, what to
  report.
- `eval/README.md`: a "Golden charts" section (commands, environment, run, kept folders and cost, --rerun per engine
  and its files, diff).
- `docs/DESIGN.md`: preamble line, evidence-documents row "golden runs", §3.4 lists golden.py, new §3.6 (why, what is
  compared, diff, kept/private folders [decision], not keyed by code, runs, limits), §11 entry.
- `docs/PROGRESS.json`: `golden` (done, baseline, environment, cost), `in_flight` empty, `next` first item, one
  `deferred` item (limits).

### No audio, stems, reference charts or weights committed

`git diff --name-only main..golden` holds only the 8 files above (no .wav/.mp3/.ogg/.mid/.chart/.npz/.pth/...);
`git status --short` clean. Tests write their synthetic chart folders and a 1-s sine into tmp folders only. No model
names in code or docs (the grep's hits: the scratchpad path `/tmp/claude-0/...` in PROGRESS.json, and the attribution
lines in commit messages).

### Disk

`df -B1 /` available: 4,781,527,040 before (S/golden did not exist), 4,033,531,904 at the end (−748 MB,
including the worktree and logs); `df -h /`: 4.5G → 3.8G avail. `du -sh S/sepcache/cache S/golden` (links counted once): S/golden adds 707 MB: the
kept folders 663 MB (decode.wav 59–139 MB a song, 615 MB in all; engine outputs and takes the rest) and the
baseline 44 MB. (`du -sh S/golden/work` alone says 4.3 G because it counts the linked stems.) Temporary outputs went
to /dev/shm and are deleted.

## Not done, uncertain, decisions to look at

- **`--code`** is my addition: main has no golden.py, so "run on main" needed a way to build one checkout's code with
  another checkout's tool. The inspector and the release gate are written that way (old through `--code`, new from
  its own checkout); running golden.py from each checkout also works (shown by scratch_con).
- **The hash** is scan-chart's `calculateTrackHash`, not one of my own; scan_notes.cjs's output gained a `hash` per
  track and now honours `$SONGCHARTER_SCAN_CHART` (needed in worktrees, which have no tools/scan-chart/node_modules).
  score.py's output is unchanged.
- **Song-level UNEXPECTED** (a missing song, a changed exit or gate, a build failed on both sides, whatever
  `--expect` says) and "a delay change moves every part" are my reading of the brief, so that "no UNEXPECTED" can't
  hide a vanished build. A subset run (`--songs`) compared with the full baseline is therefore always exit 1.
- **Not compared:** sections, song.ini values, the audio. A change to the separation's code does not show (the kept
  stems); a change to the decode or the separation's key shows as `decode`/`separate` among the engines that ran
  (unasked). One CPU take only: the CUDA default (4 spliced takes) is not covered. Linux/WSL only (fcntl, hard links).
- Kept engine outputs are main 11615e2's code; a later engine change without `--rerun` compares that output on both
  sides (report.md's "kept folders made by" row shows which commit made them).
- Warm times were measured while I edited docs and ran unit tests; main_w2 overlapped the full suite.
- Left in place on purpose: S/golden/work (kept folders, 663 MB), S/golden/base (baseline), S/golden/checks
  (evidence), S/wt/golden (the worktree). Removed: the scratch branch and its worktree, the main worktree, every
  /dev/shm output.

## Review fixes (G1–G4), after the first report

Commits: 66c480b (code and tests), c986c6e (docs), plus the PROGRESS line below. Not pushed.

- **G1 (rerun on one side).** Docs: `RERUN` set once and passed to both runs, with the cost (per run and song: about
  half a minute for drums or bass, 1.5–3 min for sections, 3.5–11 min for the guitar). `compare()`: a run-level
  UNEXPECTED finding, shown above the verdict, when the two runs reran different engines; it names the engine, the
  kept commit and the side's own commit. I chose UNEXPECTED (exit 1) over a refusal (exit 2) because the report still
  gets written with the evidence, and exit 2 stays "the summaries cannot be read or compared". Optional (3) done too:
  `run` checks with `git diff --quiet <kept commit> -- ENGINE_FILES[engine]` for every engine not rerun (the working
  tree, so uncommitted changes count), warns, records `stale` in the run section, and `diff` fails on "changed".
  Tests: `test_a_rerun_in_one_run_only_is_unexpected_and_named_above_the_verdict`,
  `test_an_engine_whose_kept_output_is_another_codes_is_unexpected`, `test_stale_engines_compares_each_engines_files_with_the_kept_commit`.
- **G2 (stale summary).** `cmd_run` takes the out lock first, then `clear_out()` (summary.json, report.md, report.json,
  logs/, scores/, the summary's song folders; only in a folder that is golden's) before any check; `run()` does the
  same when called directly. Docs: `rm -rf` of both outs, commands chained with `&&`, "each run must exit 0, and then
  the diff must exit 0". Tests: `test_a_refused_or_killed_run_leaves_no_summary_for_a_diff` (refused: exit 2, nothing
  left, diff exit 2; killed by KeyboardInterrupt: no summary), `test_a_folder_of_the_persons_loses_nothing`.
- **G3 (allin1 variable).** All three docs name SONGCHARTER_AUTOCHART and SONGCHARTER_ALLIN1_PYTHON (and
  SONGCHARTER_SCAN_CHART). `run` stops with exit 2 when any engine (or the decode or separation) ran without being
  asked, naming why: for the librosa fallback "SONGCHARTER_ALLIN1_PYTHON is not set"; for the guitar the autochart
  install; else "--rerun <engine> to both runs". `diff` fails on sections from different backends. Tests:
  `test_a_librosa_fallback_stops_the_run_with_exit_2_and_names_the_variable`, `test_an_engine_that_runs_unasked_stops_the_run`,
  `test_sections_from_another_backend_between_the_runs_are_unexpected`.
- **G4 (exit codes).** `main`: Refused and OSError → 2, KeyboardInterrupt → 130, any other exception → traceback and
  3; `--threads` below 1 refused. Test: `test_bad_input_exits_2_and_a_bug_exits_3`.
- Break-checks: 16 mutations of the fixes (S/golden/mut/mutate2.py), each failing a test; the earlier 35 still do.
- Suite at c986c6e: `509 passed, 3 skipped in 453.71s (0:07:33)`.

**The skeptic's scenarios, run for real** (S/golden/scenarios.sh, log in S/golden/checks/review/), Take Me Out and
Creep: release N = bass.py:266 `>= 5` → `>= 3` with no VERSION bump, N+1 = its revert; kept folders by 11615e2.
- Fixed gate (`--rerun bass` on both): `diff N_rerun N1_rerun --expect none: exit 1` (8 bass rows UNEXPECTED, "identical: no"); with `--expect bass`: exit 0, 8 changed.
- The skeptic's gate (old without, new with `--rerun bass`): exit 1, "bass was rerun in the new run only: the old
  run's bass came from the kept folders (made by 11615e29fc9e), not from its own code (2833f96a770a)" plus the stale line.
- `--rerun` forgotten on both: exit 1 (the old run's bass stale against 11615e2).
- old(no rerun) against old(rerun), one commit: exit 1, now with both causes named above the verdict.
- A refused run (`--rerun basss`) on an out with a summary: "cleared … summary.json, logs, scores, take_me_out, creep", exit 2; the diff then exits 2.
- A run killed with SIGKILL after 25 s on an out with a summary: only logs/ left; the diff exits 2.
- SONGCHARTER_ALLIN1_PYTHON unset: exit 2, "sections ran without being asked: the sections fell back to librosa (the kept folder's came from allin1): SONGCHARTER_ALLIN1_PYTHON is not set …"; no summary.
- Kept folders: 217 files, 0 differing before and after.

**The docs' gate commands, run as written** (the ```sh blocks extracted verbatim from CLAUDE.md and
sc-inspector.md, RERUN="" and EXPECT=none, run at the same time; S/golden/checks/gate/): CLAUDE.md's from the release
checkout (c986c6e) against main at /dev/shm/golden-old: both runs 406 s, `golden diff: no UNEXPECTED change`,
"CLAUDE.md block exit 0". The inspector's from fresh checkouts /dev/shm/inspect/{old,new}: 406 and 407 s, "inspector
block exit 0". The new run against S/golden/base: exit 0, identical. The README's block is the same commands as
CLAUDE.md's. All temporary worktrees, branches and /dev/shm outputs removed; S/golden/work untouched (fingerprints).
Final commits: 66c480b, c986c6e, and the PROGRESS line after them. The suite ran at c986c6e (the PROGRESS commit is
JSON only).
