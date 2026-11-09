# M8-05 report: allin1 on a long song (the fallback said, the memory bounded)

Branch `m8-05-allin1-memory` from main e5a2596. Labels only; no titles, ids or md5s. Paths: <repo> the checkout, <wt>
the worktrees, $DEV the dev data folder, <shm> /dev/shm scratch, <scratch> the session's scratchpad.

## Commits

- 7835589 M8-05: allin1's fallback said, a kill named, the arrays let go, the skip before the kill (code and tests)
- 5eac261 M8-05 docs: DESIGN 2.5 and 4.7; the order's "M8-03's numbers" paragraph
- cf4d9ab Merge origin/main (5 commits: the page's wording, the review2 scripts; none of this order's code)
- 3eebad7 the skip counts MemTotal only; the UI header test admits doctor's memory note (the Decisions below)
- b05964e review fixes (F1-F3, below)
- a8a0bed Merge origin/main (2 commits: reports, review3 scripts, PROGRESS; none of this order's code)

## What was built, and why (the brief over the order)

- **Part 1, the fallback said (built).** The pipeline's sections stage records a fallback `{"stage": "sections",
  "from": "allin1", "to": "librosa", "reason": ...}` whenever the sections come from librosa for any reason but
  "backend librosa asked for". It goes to pipeline.json's `fallbacks`, ChartResult.fallbacks and a `fallback` event,
  which the page shows as a banner ("Sections runs on librosa: <cause>. The bar lines and the tempo's halving test come
  from a simpler analysis: on a slow or fast song the chart may sit at double or half the tempo, and the sections have
  plainer names."). The cause is the first line of engine.json's `why`. The warning line is unchanged. report.json (the
  song folder's) records no fallback of any stage today, so this one goes where the others go. No UI change was needed.
- **Part 2, a kill named (built).** A runner that ends with returncode -9 is reported as "allin1 was stopped, most
  likely for memory (a song of M:SS needs about X GiB for it on the CPU)", where X comes from A-a's line (354.5 + 17.443
  MiB a second). The sentence reaches the warning, the banner and engine.json's `why`. On CUDA it is the reason for the
  CPU retry. Other failures keep their message.
- **Part 3 (b), the parent's arrays (built).** `engines/sections.SongArrays` holds the mix and stems. The pipeline
  hands them over and keeps no reference of its own, and its loader (`pipeline._reload`, the separation cache's own
  float32 read of decode.wav and the stem WAVs) is given only when every file exists. The engine makes the runner's
  int16 bytes once and builds the key from a zero-copy view of those bytes (the same key as before). Just before the
  run it releases the arrays, so while the child runs only the bytes stay in the parent. After the stage the pipeline
  takes the arrays back, read again only if they were released (that is, after a run that was not cached). The
  librosa fallback reads them again when it needs them. M8-03's finding was checked in the code: after the sections
  stage only `mix.shape[1]` (guitar) and `stems["vocals"]` (lyrics) are read, then `del mix, stems`. The stage
  reloads all seven arrays, the order's literal design, at 1.1–1.3 s.
- **Part 4, the skip before the kill (built; 3 (a) is not).** Before a run on the CPU (after the cache check, before
  the weights), the engine predicts the tree as child + parent: 853.5 + 20.4 MiB a second with the arrays kept, 17.7
  with them released. It adds the margin (the child line's largest residual, 202 MiB, plus 1 GiB) and compares the sum
  with MemTotal from /proc/meminfo (never MemAvailable; swap not counted, the Decisions below). When the tree does not fit, allin1 is left out at
  once with "allin1 was left out for memory (a song of M:SS needs about X GiB for it on the CPU, T GiB with the rest of
  the chart and a margin; this PC has C GiB of memory)", and part 1's banner follows. doctor adds a note on
  the CPU when allin1 is available and not left out under 11 GB: "allin1 analyses songs up to about M:SS on the CPU
  with this PC's C GiB of memory; ...".
- **Parts 3 (a) and 3 (c), not built**, as M8-03 decided: no window met the chunk bar, and chunks do not lower the
  child's peak.
- **The CUDA path:** nothing is checked before a CUDA run. The host side on CUDA was measured once (11.09 GiB on 6:52,
  M8-00 section 6), not as a line, and no GPU is here to fit one. A CUDA run that fails or is killed goes to the CPU
  (device auto), and that CPU run passes the same check. The arrays are released on CUDA too.
- **Docs:** DESIGN 2.5 (a Memory bullet with M8-03's numbers, the skip, the kill, the banner, the limits, the chunks
  measured and not built) and 4.7 (a long song on a 16 GB PC). The order gains its "M8-03's numbers" paragraph.
  PROGRESS.json is left to the orchestrator (the brief: only the order's files).

## The consequence (for the owner and the guide)

Longest song allin1 analyses on the CPU by the rule (arrays released, margin 1226 MiB, swap not counted): MemTotal
10.2 GiB 7:52, 11.2 GiB 8:50, **12 GiB (a 16 GB PC's WSL 12 GB) 9:36**. The dev
machine (15.7 GiB, no swap) gets 13:11, so the skip does not fire on the sets (the longest, 9:43, needs 12.1 GiB) and
no test-only override was needed. A song over the limit charts with the librosa sections and the banner. Suggested
guide line (for the orchestrator): "On a 16 GB PC, songs over about 9 minutes get simpler
sections and bar lines; the page says so when it happens."

## Checks

- **New tests**, each failing on its break (11 breaks, each run alone, each `1 failed`): the kill's returncode; the
  skip off; swap not counted; the skip on CUDA; the released line; no release; no reload for the fallback; the
  pipeline giving no loader; `_reload` reading the wrong stem; no banner; doctor ignoring swap.
- **Suite** (`tools/heavy.sh python -m pytest -q -p no:cacheprovider`, SONGCHARTER_HEAVY_MIN_FREE_GB=1): `1 failed,
  1283 passed, 6 skipped in 852.88s` before the decisions. The failure is `tests/test_ui_server.py::test_the_header_measures_wsls_memory_again`
  (see Open question 1). The three files of this order pass.
- **CI** run 42530767302 (workflow_dispatch on the branch): windows success, linux failure on the same test (`1
  failed, 1285 passed, 4 skipped`). No CI hooks were added. After the merge, the three files of this order and
  tests/test_ui_server.py were run again: `1 failed, 181 passed, 1 skipped` (the same test). CI run 42537573911 on
  cf4d9ab: superseded. After the decisions, the four files (this order's three and tests/test_ui_server.py): `182
  passed, 1 skipped`; two more breaks (the skip and doctor counting swap) each fail their test. CI run 42538314218
  on 3eebad7: success (linux and windows). The golden runs stand: this machine has no swap, so its capacity is the same under either rule.
- **Memory run** (<scratch>/m805/ab_sample.py, after M8-03's a_b_sample.py, through tools/heavy.sh: sooth's kept folder
  copied to <shm> without sections/, the rest cached, 0.5 s sampling): sooth 549.3 s, allin1 on the CPU, 2 threads.
  allin1's VmHWM was 9899 MiB (line 9937). The parent while the run ran was 659 MiB flat (freed line 642; today's line
  2125). Before the release (stages before, the probe) it peaked at 2261 MiB, which is not in the tree. **Tree max
  10556 MiB** (freed line 10579; today's line 12062): 1.47 GiB lower than today. The child ran for 120 s;
  MemAvailable's minimum was 4733 MiB.
- **Golden** (`python -m eval.golden run --code <wt>/m8-05 --threads 2 --rerun drums,bass,sections`, then `diff ...
  --expect none`). The baselines are v0.4.0 final's (v040f, v040f-stress; main's songcharter/ and eval/golden equal
  4fa0930's) and v040-set20. A first attempt with `--rerun sections` alone was refused by golden (bass from other
  code), so all three reruns were used, as v040f.sh does.
  - refs: run exit 0, diff exit 0, "golden diff: no UNEXPECTED change"; report.json `sections` 7 same, 0 differ (the
    `source` path, the run's own folder, left out).
  - stress: run exit 0, diff exit 0, "no UNEXPECTED change"; sections 4 same, 0 differ.
  - 20-song set (against v040-set20, as v040-b.sh with this code): run exit 0, diff exit 0, "no UNEXPECTED change";
    the 13 report.json files carrying sections are all the same. Only exit lines and the diff's first line were read.
- **Privacy:** both checks on the changed files (and on 3eebad7's added lines) give the same counts as main's versions of them, and on the added
  lines alone: stress `0 found`, 20-song exit 0 with no hit. The diff and commit messages were scanned for model names,
  home paths and emails: none apart from the trailers.

## Open questions

1. **tests/test_ui_server.py** (outside this order's files) pins the header's notes after WSL restarts with 12 GB.
   doctor's new note now appears there, rightly (allin1 is in, on the CPU), so `after["notes"]` has one more item. The
   fix is one line in that test, either admitting the note or filtering notes starting "allin1 analyses songs". It is
   left for the orchestrator, since M8-04 is in the same wave. CI's linux job fails only on it.
2. **Swap.** The rule counts SwapTotal in full, as the order's "WSL's configured memory and swap" reads. With the
   install's swap=8GB the 16 GB PC's limit is about 17 minutes, not the order's "about 7". Whether allin1 finishes in
   reasonable time while swapping several GiB was not measured (its run would end at the 3600 s timeout and fall back
   if not). Counting no swap gives 9:36 for 12 GiB. The change is one term in `sections.capacity_mib`, plus doctor's
   and the tests' figures.
3. The reload reads all seven WAVs (1.1–1.3 s). Reading only the vocals with lyrics would also need a change to the
   guitar stage's `mix.shape[1]` line, which this order does not cover.

## Decisions (the orchestrator's, after the first report)

1. tests/test_ui_server.py's header test admits doctor's new memory note (an allowed exception: M8-04 had not
   started). Done in 3eebad7.
2. Swap is not counted: `sections.capacity_mib` reads MemTotal only, because allin1 deep in swap was never measured
   and could run for hours, which is worse than the librosa fallback. doctor's note, the tests, DESIGN 2.5 and 4.7 and
   the order's paragraph say so; a 16 GB PC's WSL 12 GB fits about 9:36 with the arrays freed. Done in 3eebad7.
3. The reload of all seven WAVs stays.

## Review fixes (the review of 3eebad7)

- **F1 (major, a test gap):** the stand-in sections engine in tests/test_pipeline.py now weak-references the arrays
  it gets, lets them go as allin1's run does, and records how many anything still holds (`alive`). The read-again
  test asserts `[0]`. The stand-in drums, bass and sections engines now record copies, so their own records hold
  nothing. The reviewer's B11 (`del mix, stems` replaced by `_keep = (mix, stems)`) now fails that test (`1 failed`).
- **F2 (minor):** DESIGN 2.5 and 4.7 and the order's paragraph say "about 9 minutes" for a 16 GB PC's WSL 12 GB:
  8:50 for 11.2 GiB, 9:19 for the 11.7 GiB such a WSL reports. doctor's computed figure stands. The order's quote of
  M8-03's "11.2 GiB about 9.0" is marked as M8-03's figure with the reserve alone (the skip's margin gives 8:50).
- **F3 (minor):** `Allin1Error.plain` carries the banner's words for each cause, and the librosa result's
  info["plain"] (also in engine.json) carries them to the pipeline:
  - a timeout: "allin1 did not finish in time";
  - no allin1 Python: "allin1 is left out on this PC to save memory" (WSL with MemTotal under 11 GB, doctor's rule),
    else "allin1 is not installed";
  - the memory skip and the kill: their own sentences;
  - a CUDA failure followed by a CPU failure: the CPU's words;
  - anything else: "allin1 failed (the diagnostics zip has the details)".

  Each is followed by the cost sentence. Paths, commands and exception text stay in the warning, pipeline.json's
  warnings and engine.json's `why`. Tests: one per cause (8 cases) that the words hold no path, command or exception
  name, and the pipeline's banner test (stopped, timeout, failed, asked).
- **Breaks:** B11, the banner showing `why`, the timeout's words removed, "left out" never said, and the CPU retry
  losing the words: each fails its test.
- **Checks:** this order's three test files plus tests/test_ui_server.py on b05964e: `190 passed, 1 skipped`. Both
  privacy checks on the added lines: nothing found. CI run 42542187002 on a8a0bed: success (linux and windows). The golden results stand: the
  fixes touch only the banner's words, a test stand-in and docs, not a chart.

---

## M8-05 review (m8-05-allin1-memory at 3eebad7, against origin/main 0ba8655)

Lenses run in order. Copy at <shm>/review_m805 (removed after). Single test files only.

### Lens 1, the arrays freed: no defect found
The read-back is byte-identical. decode.wav is written FLOAT, atomically, and only kept when its sha matches the
fresh decode. The stems are written FLOAT from the float32 Demucs output, and the cache reads them back the same way.
`_reload` is `A.read_wav` (float32). On a cached sections run the arrays are not released, so `take()` returns the
held arrays. The librosa fallback reloads after the `except` block, so no traceback holds `data`. No other caller of
`Engines.sections` or `find_sections` uses the old signature.

### Findings

**F1 (major): the pipeline's release can be gutted and every test stays green, and the skip then lets through
songs that get killed.** Places: songcharter/pipeline.py:1103 (`del mix, stems`) and the stand-in at
tests/test_pipeline.py:213-218, which calls `song.release()` but never checks that the arrays are gone.
- Break B11: replace `del mix, stems` with `_keep = (mix, stems)`, so `_engine_stages` keeps its own references
  while allin1 runs. Result: `tests/test_pipeline.py`: 62 passed in 346.28s.
- The engine's own guard catches the same break in find_sections (B31: test_the_arrays_are_let_go... fails), but
  nothing guards the pipeline.
- Why this ships a real defect: `memory_skip` uses the freed line (17.7 MiB/s) whenever a loader exists, but with
  the arrays held the tree follows today's line (20.4).
  - Repro: `python -c "import songcharter.engines.sections as S; ..."`. For MemTotal 11980 MiB the freed limit is
    559 s and the kept limit is 485 s.
  - A song at 9:19 then passes the skip but needs 13490 MiB with the margin.
  - So songs between about 8:05 and 9:19 run and are killed. That is the case this order exists to prevent, and the
    1.42 GiB saving goes too.
- Fix: a weakref liveness check in the stand-in's `sections`, as the engine test does.

**F2 (minor): the docs' "9:36 on a 16 GB PC" contradicts M8-03 and the branch's own fixture.**
- docs/DESIGN.md:989 says "9:36 for 12 GiB (a 16 GB PC's WSL 12 GB)", and DESIGN.md:3123 says "about 9:36".
- The order's paragraph (M8-05-allin1-memory.md:28-31) says both "11.2 GiB (a 16 GB PC's 12 GB) about 9.0" and
  "a 16 GB PC's WSL 12 GB fits about 9:36".
- The plan (M8-00-plan.md:211) says "12 GB (11.2 GiB)".
- The branch's own UI test (tests/test_ui_server.py:274-276) has WSL restarted with memory=12GB give MemTotal
  11980 MiB, and doctor then says **9:19**. `longest_s` gives 8:50 for 11.2 GiB.
- MemTotal is always under the .wslconfig figure, so 9:36 is an upper bound the friend's PC does not reach. The
  suggested guide line ("about 9 and a half minutes") repeats it.
- Fix: write "about 9 minutes (8:50-9:19 by MemTotal)" and let doctor's figure stand.

**F3 (minor): the new banner shows raw internals for causes other than memory.**
- Place: pipeline.py:1124 takes the first line of `why` as is, and sections.py:544 builds the timeout's message
  from `str(TimeoutExpired)`.
- Repro: <shm>/review_m805_s/banner.py (removed), which runs find_sections with a run that raises
  TimeoutExpired, and with no allin1 Python. The page's text:
  - `Sections runs on librosa: allin1 did not finish (TimeoutExpired: Command '['/opt/made-up/allin1/bin/python',
    '-c', "import sys; getattr(sys.flags, 'safe_path', False) or sys.path.pop(0); import runpy; ...",
    '<app>/songcharter/engines/allin1_runner.py', 'run', '<tmp>/job.json']' timed out after 3600.0
    seconds). The bar lines ...`
  - `Sections runs on librosa: no allin1 Python: set SONGCHARTER_ALLIN1_PYTHON to a Python with all-in-one-infer
    (or allin1). The bar lines ...`
- The second one appears on every chart of a PC where the install left allin1 out on purpose (WSL under 11 GB),
  and it contradicts doctor's "allin1 is left out to save memory".
- Before this branch both were only warning lines. The memory sentences (skip and kill) read well.

### Test the tests (my breaks, none of them the builder's 11)
| break | result |
|---|---|
| B3: skip always freed=True | test_allin1_is_left_out... fails |
| B4: skip before the cache check | fails |
| B6: banner uses the whole `why` | test_..._is_a_banner fails |
| B28: skip compares the child line only | fails |
| B29: skip reads `released`, not `can_release` | fails |
| B31: find_sections keeps a ref while allin1 runs | test_the_arrays_are_let_go... fails |
| B11: pipeline keeps its refs | **green (F1)** |

### Lens 2, the skip and the kill: correct
- The skip reads MemTotal and the decoded length (`song.samples`, no lead-in), after the cache check and only on the
  CPU, including a CPU retry after CUDA.
- The runner is started directly (`python -c`), so an OOM kill shows as -9. A timeout stays "did not finish" (see F3).
- I checked the arithmetic: 7:52, 8:50 and 9:36 match `longest_s`.
- Doctor's note uses the same rule and is left out on CUDA and under 11 GB.
