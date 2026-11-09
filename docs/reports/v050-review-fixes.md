# v0.5.0's review fixes

*The full review of v0.4.0...f5e6383 (v0.5.0's release gate, step 4: four lenses, a skeptic for the one major) gave 15
minor findings and no major. The skeptic reproduced the major on the real runner and made it minor. Two builders fixed
them on v050-fix-allin1 and v050-review-fixes, merged as v050-fixes. One reviewer reviewed the fixes and then their
delta, and broke the tests (no break survived). Merged 2026-11-09.*

**In this merge, beyond the 15:**
- **The owner's decision, 2026-11-09:** 1 guitar take is the default on every device; Best chart (4 takes) is an
  option. The evidence: M8-02 (+0.005 F1@50, +0.000 at F1@100, about 4x the guitar time), and a repeat-consistency
  measurement: repeated sections whose instances came from different takes lose -0.045 [-0.087, -0.011], and
  same-take pairs do not.
- **From an advisor's look through the project:**
  - report.json records each chart's takes, devices, CPU retries and fallbacks;
  - the page says plainly when the GPU failed and a chart has one CPU take;
  - the page reminds him to keep the PC awake while a queue charts.
- **From a second advisor:**
  - a chart left running by a killed server is stopped at the next start, only once the port is bound and only when
    its server is gone;
  - the separation's cache key holds the device, and the CPU's key is unchanged.
- **The fixes' review:**
  - **First pass, 3 minors, fixed:** the sections cache's fallback text, the Done screen's results by id, and the
    stems message on a failed chart.
  - **Re-review, 3 minors, fixed:** a second start never stops a live server's chart; a separation never writes
    through a hard link; DESIGN's takes tables.

The two builders' reports follow, with paths as placeholders.

## Part A (allin1 on CUDA, report.json's record, the separation key)

# v0.5.0's review fixes, part A: allin1's memory on CUDA

The builder's report for the brief "v0.5.0's review fixes, part A". It covers the findings
`docs-cuda-oom-unchecked` (confirmed) and `docs-16gb-pc-cuda` (to the fixer) from the full review of
v0.4.0...f5e6383. It also covers one item the orchestrator added mid-build: the advisor's finding 2(b), report.json
keeping the takes, devices and fallbacks (its own section below).

- **Branch:** `v050-fix-allin1` from origin/main f5e6383, worktree `<wt>/v050-fixA`; pushed, not merged.
- **Head:** 4699fbb.
- **Commits:**
  - bef1a40 `sections: a CUDA out-of-memory goes to a checked CPU run in a fresh process`: allin1_runner.py,
    sections.py, tests/test_engines_sections.py.
  - fdd5ad0 `docs: what happens to allin1's memory on CUDA (DESIGN 2.5, 4.7, doctor's note)`: docs/DESIGN.md,
    songcharter/device.py (a comment only).
  - d0ba639 `report.json keeps the takes, devices and fallbacks; the one-CPU-take warning in plain words` (the
    added item): songcharter/pipeline.py (the takes code, a helper beside `guitar_takes`, the assemble call's
    argument), songcharter/assemble.py, tests/test_pipeline.py, docs/DESIGN.md 2.7.
  - 1565b15 `sections: a cache hit reports this call's probe and fallback, not the run's` (round 3, the
    reviewer's F1): songcharter/engines/sections.py, tests/test_engines_sections.py.
  - 4699fbb `separate: the device in the stems' cache key, the CPU's key as before` (round 3, a second advisor's
    finding 8): songcharter/separate.py, tests/test_separate.py, docs/DESIGN.md 2.2.
- **Not touched:** songcharter/ui/*, docs/PROGRESS.json, the guide, the work orders and M8-05's report.

## What changed

### The fix (the orchestrator's decision 1: the skeptic's simpler fix, its 3)

- **The runner** (`allin1_runner.run`) runs on the job's device only. The `try/except torch.cuda.OutOfMemoryError`
  that analysed the whole song again on the CPU in the same process is gone. A CUDA out-of-memory now ends the run
  with torch's own traceback (exit 1). The result's `fallback` field went with it, since the runner never moves
  device now. The docstring says why: a CPU run in that process was checked by nothing and kept the CUDA run's host
  memory.
- **The parent** (`sections._allin1`) recognises the out-of-memory in the runner's error line with
  `OUT_OF_MEMORY = re.compile(r"\bOutOfMemoryError: (.*)")`. That matches `torch.OutOfMemoryError` (this torch) and
  `torch.cuda.OutOfMemoryError` (an older torch's name). The parent then:
  - runs the job again on the CPU through `_allin1_job(..., "cpu", ...)`, a fresh process, where `memory_skip` is
    asked first, as for any CPU run;
  - records it in the runner's old words: `CUDA ran out of memory (<torch's message, at most 120 characters>);
    analysed on the CPU`. They go into engine.json's `allin1.fallback` and `why`, which the pipeline copies into
    pipeline.json's `fallbacks` and its warning (pipeline.py unchanged).
  - A song past the line: the retry raises the skip's Allin1Error at once. find_sections falls back to librosa with
    `plain` = the skip's words (the page's banner) and `why` = `CUDA ran out of memory (...), and then on the CPU:
    allin1 was left out for memory (...)`.
  - A song under the line: allin1 runs on the CPU, as before, but in a new process.
- **A choice the brief did not make, flagged here.** The brief says "the parent's device-auto CPU retry". The
  parent's rule was "asked for cuda: no second try". The runner's in-process retry, though, also covered
  `device="cuda"` asked for. Taken literally, the fix would have dropped that path: an out-of-memory with "cuda"
  asked for would have raised (with backend auto, librosa and "allin1 failed").
  - I kept the old behaviour in the parent rather than switch to the skeptic's fix 1-2: an out-of-memory is retried
    on the CPU (checked) for "cuda" too. Any other CUDA failure still raises when "cuda" was asked for.
  - Only API callers reach this path. The pipeline maps the user's "cuda" to "auto" for the sections
    (pipeline.py: `"auto" if options.device == "cuda" else options.device`), and nothing in songcharter/ or eval/
    passes "cuda" to the sections engine.
  - If the orchestrator prefers the literal rule, it is one condition in `_allin1`:
    `if device == "cpu" or s.device != "auto"`. The test `..._for_cuda_asked_for` then needs its "cuda" half
    dropped.
- **Did the simpler fix break anything the in-process fallback was there for?** Nothing on the pipeline's path.
  - The retry is a new process, so it re-reads the stems from stdin (the parent still holds the bytes), recomputes
    the spectrogram and imports torch again: seconds, against a run of minutes.
  - The CPU result is now cached under the CPU's key, not the CUDA key. A second chart of the same song tries CUDA
    again and then hits the CPU's cache. That is what every other failed CUDA run already did (the existing test
    `test_a_failed_cuda_run_is_run_again_on_the_cpu_when_the_device_was_auto` pins it).
  - Each run has its own timeout (3600 s) where the two used to share one.
  - A CUDA error that is not torch's OutOfMemoryError (for example `RuntimeError: CUDA error: out of memory` from a
    library) was not caught by the old in-process retry either; it still takes the generic "the CUDA run failed"
    path.
- **What stays as it was:**
  - A CUDA run that times out is not retried. It goes to librosa with "allin1 did not finish in time", as before.
    A CUDA run deep in host swap can therefore still take up to the hour before librosa. The docs now say so.
  - A CUDA run ended by SIGKILL is retried on the CPU when the device was auto, and checked, as before.

### The docs (the orchestrator's decision 2: no new check before a CUDA run)

- **sections.py's docstring:**
  - CUDA bullet: a failed CUDA run is run again on the CPU in a fresh process, so the CPU's memory check applies.
    Which failures, for auto and for cuda, and the two record phrasings.
  - Memory bullet: on CUDA nothing is checked before the run, whatever the length; an out-of-memory, failure or
    kill goes to the CPU run, which is checked; doctor's figure is the CPU's.
- **allin1_runner.py's docstring:** the runner never retries on the CPU, and why.
- **DESIGN 2.5:**
  - The CUDA bullet: the same rules; a timed-out run is not redone; what the runner did until this review.
  - The Memory bullet, with a bold "On CUDA nothing is checked before the run":
    - the host side was measured once (the whole tree at 11.09 GiB on the 6:52 test song, before M8-05; M8-00
      section 6), not as a line, and the owner's GPU check at this gate reads it;
    - a long song's CUDA run may be killed, or swap for up to the hour;
    - an out-of-memory, failure or kill goes to the checked CPU run;
    - the evidence tag names the stand-in test.
  - The "longest song that fits" sub-bullet: doctor's figure is the CPU lane's, and why it is not shown on CUDA.
- **DESIGN 4.7** ("A long song on a 16 GB PC"):
  - the ~9-minute rule and doctor's figure apply on the CPU lane;
  - on the CUDA lane, the friend's, nothing is checked before allin1's run and doctor names no figure;
  - an out-of-memory, failure or kill goes to a checked CPU retry, so past the line the song gets librosa and the
    page's words;
  - the owner's GPU check at this gate reads allin1's host memory on CUDA.
- **doctor's note (`device.findings`):** unchanged in behaviour; a comment says why it is CPU-only.
  - **Should it also show on CUDA? No.** On CUDA nothing is checked before allin1's run, and the figure bounds only
    the CPU retry after a failed CUDA run.
  - A song longer than the figure still gets allin1 whenever the CUDA run succeeds, the normal case on the friend's
    PC. So a note reading "allin1 analyses songs up to about 9:19 ... a longer song gets the librosa sections"
    would tell him of a limit his PC does not have.
  - A CUDA-specific wording ("if the GPU run fails, the CPU retry takes songs up to ...") would add a note to every
    GPU PC's doctor run for an unobserved path.
  - doctor.json already carries MemTotal, from which the figure follows.
  - Revisit once the owner's GPU check gives a host-memory figure on CUDA: that would be a real CUDA line to name.
  - The existing test `test_doctor_names_the_longest_song_allin1_analyses_on_the_cpu` already pins "not on CUDA".

## Tests (tests/test_engines_sections.py)

- **`test_cuda_out_of_memory_goes_to_a_cpu_run_in_a_fresh_process_that_is_checked_first[fits|over]`** (the brief's
  test):
  - The real allin1_runner runs in processes of its own (`subprocess.run` on the command find_sections builds), on
    the fake All-In-One package on PYTHONPATH.
  - The fake model raises `torch.cuda.OutOfMemoryError` on `.to("cuda")`. A no-tensor torch checkpoint loads with
    `map_location="cuda"` on a CPU-only torch, so the runner reaches the model on any machine.
  - A stand-in probe answers "cuda works"; MemTotal is stubbed just above or just under the line for a 2 s song.
  - It asserts:
    - the CUDA run exits 1 with torch's real `OutOfMemoryError: CUDA out of memory` line;
    - over the line: only one run (cuda), librosa, `plain` = memory_skip's words, `why` = `CUDA ran out of memory
      (...), and then on the CPU: <skip>`;
    - under the line: runs cuda then cpu, the second exits 0, allin1 on the CPU with the fake model's segments, and
      the fallback words in `allin1.fallback` and `why`.
- **`test_cuda_out_of_memory_is_run_again_on_the_cpu_for_auto_and_for_cuda_asked_for`:** the stand-in runner's new
  "oom" mode, for device auto and cuda: runs cuda then cpu, and the exact fallback words.
- **`test_the_runner_on_a_fake_package`:**
  - the result has no `fallback` field;
  - a job on cuda raises `torch.cuda.OutOfMemoryError`, writes no result and runs no model after it.
- **`test_the_pages_words_for_each_cause_...[cuda oom then cpu]`:** an out-of-memory on CUDA, then the CPU run left
  out: the banner is memory_skip's words, with no path, command or exception.
- **FakeAllin1:** gains `fail="oom"`, whose stderr is in the real runner's form; the end-to-end test checks the real
  form. Its result drops `fallback`.

### Testing the tests: each break, the tests that failed

Each break was applied, the related tests run, and the file restored from git (the tree clean after).

| Break | Failed |
|---|---|
| B1 the runner's in-process CPU retry restored | end-to-end [fits], [over]; `test_the_runner_on_a_fake_package` |
| B2 the CPU retry not checked for memory (`... and fallback is None`) | end-to-end [over]; page words [cuda then cpu], [cuda oom then cpu] |
| B3 an out-of-memory retried only for auto (the old rule) | `..._for_cuda_asked_for` |
| B4 the out-of-memory not recognised (`oom = None`) | end-to-end [fits], [over]; `..._for_cuda_asked_for` |
| B5 an out-of-memory not retried at all | end-to-end [fits], [over]; `..._for_cuda_asked_for`; page words [cuda oom then cpu] |
| B6 the regex knows only `torch.cuda.OutOfMemoryError` | end-to-end [fits], [over]; `..._for_cuda_asked_for` |
| B7 the words lose torch's detail | end-to-end [fits], [over]; `..._for_cuda_asked_for` |

B6 shows the end-to-end test pins the real traceback's form (this torch names the class `torch.OutOfMemoryError`).

## Checks

- **The affected test files** (this machine, CPU only), with `PYTHONDONTWRITEBYTECODE=1`; no `__pycache__` was left
  in the worktree:

  ```
  PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider --basetemp=<shm>/pt-fixA \
      tests/test_engines_sections.py tests/test_sections.py tests/test_device.py
  82 passed, 1 skipped in 20.18s
  ```

  The skip is `test_the_configured_allin1_python_passes_its_probe` (no allin1 Python configured here). The new tests
  ran: the end-to-end pair took 2.8 s and 1.5 s.
  - Not wrapped in tools/heavy.sh: the release gate's golden run held the lock, and these three files are light
    (stand-ins, two short subprocesses).
- **The full suite: CI only** (the brief).
  - <repo>/actions/runs/42690811011 (workflow_dispatch at d0ba639): success,
    linux and windows. The linux suite: `1363 passed, 4 skipped in 618.93s`. The only skip in
    test_engines_sections.py is the configured-allin1 probe (no allin1 Python on CI), so the new tests ran.
  - The earlier run at fdd5ad0 (42686052666) passed its suite (`1363 passed, 4 skipped in 967.06s`). Its hooks step
    was cancelled by the workflow's `cancel-in-progress` when the d0ba639 run was dispatched.
  - No CI hook of this order's: the new tests are in the suite.
- **Golden charts:** not run here (the brief: the orchestrator runs a warm golden pair at the final commit).
  - On the CPU lane nothing in the charting path changes: a CPU job never reached the removed code, and the parent's
    CPU path is unchanged.
  - eval/golden.py's ENGINE_FILES lists sections.py and allin1_runner.py for the sections engine. Kept sections
    folders made by f5e6383 will not count as this code's: the warm pair reruns the sections stage (allin1 on the
    CPU) for every song.
- **Privacy:**
  - `EVAL_DATA=$DEV/eval python3 -I eval/privacy_check.py <the 5 changed files>`: 0 found, exit 0.
  - With `EVAL_DATA=$DEV/eval-set20`: 30 hits, all in docs/DESIGN.md, and the same 30 in main's versions of the
    same files, so none is new. Counted only, never printed.
- **The hard-rule scan:**
  - `git diff origin/main...HEAD` and the commit messages (less the trailers) were scanned for assistant-model
    names, home or user paths, emails, machine or user names, package files and lyrics: none found.
  - Both commits end with the session's two trailer lines.

## The added item: report.json keeps the takes (the advisor's finding 2(b))

- **The defect.** When the CUDA default's first guitar take failed inside the engine and was run again on the CPU,
  the chart was that one CPU take. The warning was technical, and only pipeline.json recorded it; the work folder
  that holds pipeline.json is pruned. So a degraded chart could not be told from a good one later.
- **report.json's new `pipeline`.** `pipeline.folder_record(record)` digests pipeline.json's record, and
  `assemble(..., pipeline=)` writes it, as `art=` is written. It holds:
  - `device`: `asked`, `chosen`;
  - `takes` (None without a guitar): `asked` (None for the default), `planned`, `made`, `devices` (each take's
    transcriber device) and `cpu_retries` (the seeds run again on the CPU);
  - `fallbacks`: each one's `stage`, `from` and `to`, with no reason, since an engine's line can hold a path.
  - A bare `songcharter assemble` writes `"pipeline": null`.
  - Example, the degraded case: `{"device": {"asked": "auto", "chosen": "cuda"}, "takes": {"asked": null,
    "planned": 4, "made": 1, "devices": ["cpu"], "cpu_retries": [<seed>]}, "fallbacks": [{"stage": "guitar",
    "from": "cuda", "to": "cpu"}]}`.
- **pipeline.json's `takes` gains `planned`**: the count chosen, before the probe kept the first take alone.
- **The warning**, which the page lists as it is:
  "The GPU failed on the guitar's first take (most likely out of memory: a game, Clone Hero or a video can take
  it), so this chart has 1 take, made on the CPU, instead of 4. Chart the song again later, with those closed, for
  the best result."
  - I used "GPU" and "CPU", not the brief's example's "graphics card" and "processor": the page's other words for
    them are those (the Device menu's "GPU (CUDA)", and gpu_failed's "The guitar's GPU run failed ... Close
    programs that use the GPU").
  - "Most likely out of memory": the retry fires only for the engine failing inside on CUDA, which pipeline.failure
    describes as "as a GPU short of memory mid-take does", so the cause is not certain.
- **The page: no ui/ change.** The words come from the pipeline's `warning` event. app.js appends each one to the
  progress screen's warnings list, and that screen stays visible above the Done screen at the end (`finish` and
  `showDone` do not hide it). The fallback banner above it is unchanged ("Guitar runs on the CPU: take seed_N: the
  CUDA run failed (...); run again on the CPU").
  - In a queue, the next song's attach clears both, so report.json is where the record lasts.
- **DESIGN 2.7:** a "What the song folder keeps" bullet with the record, the warning, and the advisor's 2c (another
  CUDA try for the first take) left for the gate's measurement.
- **The tests** (tests/test_pipeline.py). `test_a_guitar_take_that_fails_on_cuda_is_run_again_on_the_cpu` reads
  the song folder's report.json, through pipeline.json's `assemble.folder`, in three cases:
  - a retried middle take: planned 4, made 4, devices cuda/cuda/cpu/cuda, cpu_retries [202], one guitar fallback;
  - the clean chart after it: 4 of 4 on cuda, no fallback;
  - a retried first take: planned 4, made 1, devices [cpu], cpu_retries [the first seed], one guitar fallback;
  - each time with no "/", "\\" or "seed_" in the record, and, for the first-take case, the warning's exact words.
  - Two exact asserts of pipeline.json's `takes` (`test_takes_follow_the_guitar_stages_device`) gained
    `planned`.
- **Testing the tests.** Each break below failed the retry test; the working copy was restored after each.

| Break | Result |
|---|---|
| P1 the record not passed to assemble | failed (`None == {...}`) |
| P2 `made` reads `planned` | failed |
| P3 the fallbacks keep their reason | failed (the no-path/no-reason check) |
| P4 the old warning words | failed |
| P5 `planned` taken after the probe's cut | failed |
| P6 assemble writes None | failed |

- **Checks.** Not wrapped in tools/heavy.sh, for the same reason as above:

  ```
  SONGCHARTER_SCAN_CHART=<main checkout>/tools/scan-chart/scan.cjs PYTHONDONTWRITEBYTECODE=1 \
      .venv/bin/python -m pytest -q -p no:cacheprovider --basetemp=<shm>/pt-fixA tests/test_pipeline.py \
      -k "takes_follow or fails_on_cuda or piece_that_fails or chart_events"
  8 passed, 54 deselected in 273.57s (0:04:33)
  ```

- **Shared files.**
  - pipeline.py is shared with the other fix branch, which edits stems_room and export_stems. My hunks there:
    - the new `folder_record` after `guitar_takes`;
    - three spots in the guitar stage (`planned`, the warning, the takes record);
    - the `assemble(...)` call, one line;
    - The assemble call sits about ten lines above the `if options.stems:` block; a merge conflict is possible only
      if the other branch edits those lines.
  - assemble.py was not named in the orchestrator's message. I edited it because report.json is written there:
    the signature, the docstring and the report dict's first line.
- **Not done, or uncertain:**
  - **The friend's guide** (docs/guide/windows-wsl.md, "If a guitar take fails on the graphics card") says the
    take is run again on the CPU "and carries on". It does not say that when the first take fails, the chart is
    that one take. Not in this item's files; a sentence there would match the new warning.
  - **"Your charts" and the diagnostics** do not yet show the record; they only carry report.json.
  - **The golden pair:** charts (notes.chart) do not move. report.json gains the `pipeline` key, and pipeline.json's
    `takes` gains `planned`.

## Not done, or uncertain (the first part)

- **Nothing ran on a GPU here.** The out-of-memory comes from a stand-in model raising torch's real exception class
  in the real runner, so the traceback's form is this torch's. A real allin1 out-of-memory on the friend's card is
  still unobserved.
- **The words are capped twice.** The parent reads the error line `_error_line` keeps (200 characters, including
  `torch.OutOfMemoryError: `), then takes at most 120 characters of torch's message, as the runner did.
- **The `cuda` asked-for choice above** is mine; the orchestrator may prefer the literal "auto only" rule.
- **M8-05's committed report** (docs/reports/M8-05-allin1-memory.md) still says "that CPU run passes the same
  check". It was outside this brief's files; the orchestrator may add a note to it, or leave the report as history.
- **PROGRESS.json** is left to the orchestrator: the two findings are fixed on this branch.

## Round 3: the reviewer's F1 and a second advisor's finding 8

### F1: a sections cache hit carried the making run's fallback (1565b15)

- **The cause.** Since bef1a40 the CPU rerun after a CUDA out-of-memory is cached under the CPU key, with its
  fallback text in engine.json's `allin1.fallback`. `_cached` refreshed only `why` and `settings`. So:
  - (a) a later CPU-asked chart got "CUDA ran out of memory; analysed on the CPU", and so did report.json's
    `pipeline.fallbacks`;
  - (b) a CPU-made result answering an auto run's CPU retry carried no fallback, and the pipeline named "its Python
    has no working CUDA".
  - The probe's "CUDA does not run here" fallback had the same flaw before this release.
- **The fix.** `_cached(out, key, live, allin1=...)`: on a hit, this call's probe (`found`) and fallback replace the
  stored ones in `allin1`. That goes into the result and into the engine.json written back. pipeline.py needs no
  change: its rule (a fallback when `allin1.fallback` is set, else "no working CUDA" when CUDA was chosen and allin1
  ran on the CPU) is right once the hit tells the truth.
- **The test** (`test_a_cached_analysis_says_what_this_call_did_not_what_the_run_that_made_it_did`, FakeAllin1):
  - (a) for an out-of-memory and for a broken-CUDA probe: the CPU-asked hit has no fallback and no cuda_error;
  - (b) the auto run's CPU retry hits the CPU-made result and carries the out-of-memory words, in `why` too;
  - engine.json on disk equals the result each time.
- **Breaks, each failing the test:**
  - no override (fails at (a));
  - the fallback overridden but not the probe (fails at (a)'s broken-CUDA case);
  - the override only when this call has no fallback (fails at (b)).

### Finding 8: the separation's cache key had no device (4699fbb)

- **The cause.** `separate.cache_key` had no device. Stems made on the CPU, for example after one CUDA
  out-of-memory, answered every later CUDA request, cached and with no fallback recorded.
- **The fix:**
  - `cache_key(..., device="cpu")`: the CPU's key hashes exactly the old tuple, and a CUDA key adds the device.
  - "auto" is resolved before the cache is read. The pipeline passes the resolved device already.
  - A hit also needs info.json's `device` to equal the device asked for.
  - A hit reports this call's fallback, by the same principle as F1.
  - A CUDA out-of-memory switches to the CPU's key and takes a CPU folder there if one answers; otherwise it
    separates on the CPU and saves there. `info.key` is always the folder the stems are in, which the pipeline
    (and the other branch's `export_stems`) reads as `cache_dir / info.key`: pipeline.py is unchanged.
- **Existing caches:**
  - CPU stems keep their key and still hit. The golden runs' kept folders, counted without printing their paths:
    24 of 24 stem caches say "cpu". golden.py's `seed_stems` computes the key without a device, the CPU's, and its
    tests pass.
  - **The friend's CUDA-made stems** sit under the old key, which is now the CPU's. A CUDA request misses them: one
    fresh separation per song, the first time he charts it again (about 10-20 s on a 4070, an estimate). A CPU
    request also misses them (info.json says cuda) and separates again in place.
  - Until the cache's prune removes the old folder, such a song holds both copies (about 0.13 GB a minute of audio
    each). DESIGN 2.2 says this.
- **The test** (`test_the_device_is_in_the_key_and_the_cpus_key_is_as_before`, the unit-test model):
  - v0.4.0's CPU key pinned as a literal (computed with main's own `cache_key`: 4d21dc63c65a94267d50b396), and the
    CUDA key differs;
  - CPU-made stems do not answer a CUDA request, and each device then hits its own;
  - an earlier version's CUDA stems under the CPU's key make a CPU request separate again in place;
  - an out-of-memory's CPU stems sit under the CPU's key, a second CUDA request tries CUDA and then takes them from
    there with its fallback, and a CPU-asked hit names no fallback.
- **Breaks, each failing the test:**
  - S1 no device in the key;
  - S2 the CPU key changed;
  - S3 no device check on a hit;
  - S4 a hit keeps the run's fallback;
  - S5 the out-of-memory stems saved under the CUDA key;
  - S6 the out-of-memory path not looking in the CPU cache.

### Checks (round 3)

- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider --basetemp=<shm>/pt-fixA
  tests/test_separate.py tests/test_engines_sections.py tests/test_sections.py tests/test_device.py`: `92 passed,
  1 skipped in 168.86s`.
- `tests/test_golden.py -k "stems or linked"`: `3 passed`.
- No `__pycache__` was left in the worktree; one made by a stray command was removed.
- Privacy:
  - `$DEV/eval`: exit 0.
  - `$DEV/eval-set20`: 30, 6 and 8 hits in DESIGN.md, assemble.py and test_pipeline.py, the same counts as main's
    versions of those files (counted, never printed).
- The hard-rule scan of the diff and messages: none; five commits, each with the trailers.
- CI: <repo>/actions/runs/42700571991 (workflow_dispatch at 4699fbb): success,
  linux and windows. Suite: `1365 passed, 4 skipped in 849.36s` (the two new tests added); the only skip in
  test_engines_sections.py is the configured-allin1 probe.

## Part B (the page, the queue, the stems' disk checks, the estimate, the docs, the default)

# v0.5.0's review fixes, part B (builder's report)

Branch `v050-review-fixes` from origin/main f5e6383, worktree `<wt>/v050-fixB`. Head c5a8f25, pushed; CI run 42689305584 green (below). Not merged.

## Commits

- 4154934 correct-1: a Look open on a song the list has dropped keeps working
- 346ca3b correct-2, tests-1, install-01: the events by job id; a song already in the list refused; the stopped texts
  say Carry on
- 73120b0 tests-2 to tests-6: tests for the gaps
- 7baddc7 install-02: the stems' disk checks measure C: in WSL; any write error leaves the chart standing
- 554980a docs-assemble-estimate-split: the time left's split and one-file build rates, and Save the stems
- 66e5289 docs-guide-minutes, docs-listen-section-stale, and DESIGN for the fixes
- c7955cd the advisor's finding 7 (the orchestrator's added item): the keep-awake line for a queue's evening
- c5a8f25 two lines kept within 120 columns

## One line per finding

Each "break" was applied to a copy of the branch and the three UI test files (or the named file) run; each break
fails the named test. The test-gap findings were first reproduced on a copy of f5e6383: each named break left the UI
files green (153 passed; 93 for the two page breaks), as the reviewers said.

| id | reproduced | fix | test | break it fails on |
|---|---|---|---|---|
| correct-1 | yes (probe: after Clear the list A's results 404, preview 404, Install 400 "no finished chart yet") | `Queue.dropped_chart`: a finished entry that Clear the list, Remove or the trim drops keeps its result folder's library id by its job id (for the server's life); `Handler._job` resolves an unknown job id through it to `App.chart` (found among the library's folders, never a path from the page), as a `Charted` named by the job id, so the results' URLs, Listen's renders and `state.shown` stay on the job id | `test_a_look_open_on_a_song_the_list_has_dropped_keeps_working` (results, preview, art, snapshot, Install, zip, Open, Listen after Clear; a deleted chart said gone by name); the trim's case in `test_a_new_evening_and_a_cancel_reset_the_failures...` | `dropped = None` in `_job`: 404 |
| correct-2 / tests-1 | yes (probe: Last-Event-ID 1 on `current` after A ended and B started gave B's stage_end and result) | the smaller change: `GET /api/jobs/<id>/events` (the same stream for that job; a job that has ended and is no longer current sends its closing event alone), and app.js `follow()` asks for the job `attach()` read. Why the smaller: one URL changes on the page, no id format to parse and compare on both sides, and the page also gets the end it missed (then `between()` follows the next song from its first event). `current` is unchanged | `test_a_page_that_reconnects_after_its_song_ended_gets_that_songs_end_not_the_next_songs_events` (fails on f5e6383: the route by id answered 404); the gone page test's events paths; the between page test | events route on the current job whatever the id: the reconnect test; follow() on `current`: the gone page test and the between test |
| install-01 | (a) by reading: gone()'s two texts said "chart the song again" (app.js 904-909); (b) yes (probe: the same upload added while it charts: 202 waiting) | (a) both texts say "reload this page (press F5) and press Carry on: the song waits at the top of the list, and what it had worked out is kept, so it goes faster"; "songcharter stopped" says so only when the list the restarted songcharter answers has that song waiting (by name), "Chart the song again" otherwise. (b) `Queue.add` raises InputError (400) for an upload already waiting or charting: "This song is already in the list: it is charting now." / "it is charted in its turn." / paused: "press Carry on to chart it."; a finished one may be charted again | `test_a_song_already_waiting_or_charting_is_refused_and_a_finished_one_may_be_charted_again` (jobs, with a restart); `test_one_job_at_a_time_a_second_song_waits_then_cancel` (API); `test_the_page_lets_go_when_songcharter_is_gone` (texts) | the check in Queue.add off: the jobs and API tests; the old text: the gone page test |
| install-02 | yes, through the new tests run against the candidate's behaviour (the C: measure removed, the generic OSError re-raised) | `_no_room` (stems_room's and export_stems' check) also measures C: in WSL (`wsl.MNT_C`, the measure of `windows_c_free_mb`) and names it; any OSError while the stems are written is NoRoom, so the chart stands with a warning. The page's `why` for a non-ENOSPC error is still STEMS_NO_ROOM ("the disk ran out of room"): its handler in `chart()` is outside the two functions the brief allows; the warning and pipeline.json's `error` carry the real error | `test_in_wsl_the_stems_room_is_measured_on_c_too`; `test_a_full_disk_while_saving_the_stems[EIO]` | C: not measured: the WSL test; only ENOSPC caught: the EIO case |
| docs-assemble-estimate-split | yes (ASSEMBLE for 240 s: 6.5-24.2 s against creep's 35.1 s split build) | `ASSEMBLE` = split builds' 0.5-5 s + 0.05-0.16 s/s; `ASSEMBLE_ONE` = the old one-file rates, used when the estimate's new `audio` is "one"; `STEMS` 0.5-2 s + 0.01-0.04 s/s when the plan has "stems". Evidence below. estimate.py's docstring and DESIGN 4.5 updated | `test_the_builds_fall_inside_their_range_split_or_one_file`; the time-left tests' new numbers, with the one-file and stems cases | the old ASSEMBLE: 5 tests; no STEMS: 1; no one-file switch: 1 |
| docs-guide-minutes | yes (`chart_seconds(240, 4, "cuda")` gives 241-828 s, 4 to 14; the guide said 5 to 15) | the guide says 4 to 14 (the estimate's whole-chart numbers are unchanged by this branch) | doc | - |
| docs-listen-section-stale | yes, by reading (2.17 named song.ogg only and "the current job" only, against listen.cache_key and App.listened) | 2.17: the cache key over every audio file Clone Hero reads (the split files summed), renders recorded and served per job id (a finished song's Look, one the list has dropped, Your charts) | doc | - |
| tests-2 | yes | - | `test_stopping_the_server_kills_the_running_charts_whole_tree` now queues a second song: both wait in queue.json after the stop, one start in the log | `app.jobs.shutdown()` in `_main`: all three cases |
| tests-3 | yes | - | `test_a_finished_songs_routes_by_its_job_id_after_the_next_has_started`: the album art's URL by job id and its GET; also the correct-1 test | the art URL on `current` |
| tests-4 | yes (all three) | - | `test_a_new_evening_and_a_cancel_reset_the_failures_and_the_list_keeps_the_last_finished` | the new-evening reset off; the cancelled branch's reset off; `_trim` emptied |
| tests-5 | yes | - | `test_the_queues_endpoints_are_behind_the_guards`: WSL's disk low pauses with "WSL's disk is nearly full" | `home_free_mb` out of `App.disk_low` |
| tests-6 | yes (both) | - | `test_the_page_waits_for_the_next_song_and_never_shows_the_last_songs_time_left` (QUEUE_PAGE's stand-ins, a flow of its own) | `between()`'s "a different job" off; askRemaining's job check off |
| advisor 7 (added) | - | a plain line under the list, "Keep your PC awake while these chart: in Windows Settings, set Sleep to Never for now.", while this evening's list holds 2 or more songs and one is charting or waiting; the evening line no longer repeats the sleep advice; the guide says the same. No Windows API call: Windows' own keep-awake call stays a later option (M8-10's note) | `test_the_page_queues_several_songs_and_follows_them_one_after_the_other`: shown with 2 (one charting, one waiting), hidden with 1 and once both finished | shown for 1 song |

## The build's evidence (docs-assemble-estimate-split)

The brief named the kept work folders under `$DEV/golden/work/<reference>/`: their pipeline.json files are from
2026-11-05/06, before M8-12, so they are one-file builds. The candidate's own golden run (`$DEV/golden/v050`, code
f5e6383, every level, 1 take, CPU) kept each song's pipeline.json in its `logs/`; I read the stage names, seconds,
`cached` and the decode's sample count only.

| reference | length | split build at f5e6383 | one-file build (kept folders) |
|---|---|---|---|
| all_the_small_things | 175.2 s | 25.76 s | 10.50 s |
| creep | 240.0 s | 33.06 s | 15.51 s |
| drunk_drivers | 225.0 s | 33.79 s | 13.30 s |
| kimochi_warui | 288.2 s | 38.90 s | 18.72 s |
| lucretia | 239.9 s | 32.80 s | 14.86 s |
| take_me_out | 241.0 s | 34.36 s | 16.14 s |
| test_song | 412.4 s | 59.80 s | 29.63 s |

Split: 0.135-0.150 s a second; with M8-12's creep (Expert only) 35.1 s. One file: 0.060-0.072 s a second; M8-12's
creep 17.1 s, the test song 16 and 17.2 s on the 5070's PC. After the guitar on creep the time left is now 19.9-60.4 s
(was 13.9-41.2) against 35.1 s + about 12 s of preview. OTHER (the whole chart) is unchanged: the split build keeps
the CPU's decode, drums, bass, sections and build at 0.52-0.57 s a second, inside its range, so the page's minutes for
a song do not move (4 to 14 for a 4-minute song on the GPU).

## Checks

- **The affected test files** (worktree, `PYTHONDONTWRITEBYTECODE=1`, `-p no:cacheprovider`, no `__pycache__` left):
  `python -m pytest -q tests/test_ui_jobs.py tests/test_ui_library.py tests/test_ui_server.py tests/test_ui_estimate.py
  tests/test_stems_out.py` → `237 passed in 191.80s`.
- **The breaks** (a copy of the branch, one break at a time, `breaks.py <name>`): correct-1 1 failed; tests-2 3 failed
  (all three stop cases); tests-3 2 failed; tests-4a/4b/4c 1 failed each; tests-5 1 failed; tests-6a/6b 1 failed each;
  c2-page 2 failed; c2-server 2 failed; i01-add 2 failed; i01-text 1 failed; i02-c 1 failed; i02-oserror 1 failed;
  the estimate's three breaks (old ASSEMBLE 5 failed, no STEMS 1, no one-file switch 1); the keep-awake line shown
  for 1 song 1 failed. On f5e6383 the reviewers' test-gap breaks left the UI files green (153 passed, 93 for the page
  breaks), reproduced here.
- **CI**, workflow_dispatch of ci.yml on the branch: <repo>/actions/runs/42689305584,
  head c5a8f25, conclusion success. Linux: Suite `1367 passed, 4 skipped in 604.09s`; "all 8 Linux hooks passed"
  (40-ui.sh's own suite part 154 passed, 50-e2e ok in 403 s); windows: success.
- **The screens** (the stand-in server and chart from m810-screens, adapted: the branch's App, Jobs and Queue, a
  made-up cache, Songs folder, disk and songs; Chromium 1280x860 and 700 px, light and dark, deviceScaleFactor 1):
  the same song dropped while it charts says "This song is already in the list: it is charting now." (700 dark); a
  Look of the first of two finished songs, then Clear the list: its preview pictures load (reloaded after the
  clear), Install says "Done. In Clone Hero, open Settings > General and press Scan Songs.", Listen plays, Open
  folder answers, at 1280 light and 700 dark; after a hard stop (SIGKILL) and a restart the old tabs read
  "songcharter stopped ... Reload this page (press F5) and press Carry on: the song waits at the top of the list,
  and what it had worked out is kept, so it goes faster." with the restart banner under the list; with nothing
  answering, "songcharter is not answering ... start songcharter again from the Start menu, then reload this page and
  press Carry on: ..." (1280 light, 700 dark); the keep-awake line under a list of two (1280 light, 700 dark), shown
  while the second charts, gone at the end. No horizontal scroll at 700 px. Console: only the expected 400 (the
  refusal), 404s (the stopped job's events after the restart) and connection-refused while the server was down; no
  script error. The shots and <shm>/v050fixB (575 MB at most) were deleted after looking.
- **Privacy**: `EVAL_DATA=$DEV/eval` and `$DEV/eval-set20` `python3 -I eval/privacy_check.py` on each changed file:
  per-file hit counts equal to main's (0 for most; DESIGN.md's, jobs.py's and two test files' pre-existing hits
  against the 20-song list, the known false positive); on the branch's added lines and its commit messages, 0 found
  with both lists. The diff and messages were scanned for model names, home paths and user names: none (the trailers
  only).

## Not done, or uncertain

- correct-1's record of dropped songs lives in the server's memory: a Look open across a restart of songcharter on a
  song the list had dropped before it still answers 404 (rare: a Look kept open across a closed window).
- correct-2: `/api/jobs/current/events` keeps applying Last-Event-ID to whichever job is current; nothing on the page
  uses it now.
- install-01: the "songcharter stopped" check matches the waiting song by its upload's name. The not-answering text
  cannot ask the list (nothing answers), so it says Carry on unconditionally. On a normal window close (SIGHUP or
  SIGTERM) the page sees the server's own "cancelled" event first and shows "Cancelled" (as before this branch); the
  "stopped" text shows after a hard stop (the screens used SIGKILL).
- install-02: the page's plain-words `why` for a non-ENOSPC write error is still the "ran out of room" text (outside
  the allowed functions); WSL's behaviour on a full C: (an I/O error) is from the finding, not run here.
- The duplicate refusal's message lands under the form's bottom "Chart it" button, as the form's other errors do; with
  "Chart it" pressed at the top it is below the fold (seen in the 700-px shot).
- DESIGN 2.2 (the stems' room) was edited as well as 2.13, 2.17 and 4.5: the stems' disk check is described there.
- pipeline.py: besides stems_room and export_stems, two private helpers they share (`_c_free`, `_no_room`) and the module docstring's step 4b sentence; nothing else there.
- docs/PROGRESS.json untouched (the brief's rule).
- The full suite was not run here (the brief); CI runs it.

## Follow-up (the orchestrator's two items, after the first report)

- **The Done screen's reason** (26c32f7): export_stems raises `StemsNotSaved` (NoRoom's base) with the error's own
  words for an OSError other than ENOSPC; chart()'s handler gives "The stems could not be saved (input/output error);
  your chart is fine. Chart the song again with the stems ticked to try again; if C: is nearly full, free some space
  first." (`STEMS_NOT_SAVED`); a full disk and the room checks keep `STEMS_NO_ROOM`. Test:
  `test_a_full_disk_while_saving_the_stems[EIO]` checks pipeline.json's `why` (the page's text); break (`full = True`
  in the handler) fails it. tests/test_stems_out.py: 19 passed.
- **The refusal below the fold** (537a58a): `formError()` shows the form's error and scrolls it to the centre (the
  refusal and the takes check). Test: `test_a_refused_song_is_said_where_he_sees_it`; break (no scroll) fails it. The
  four UI test files: 219 passed. Screen: after the top "Chart it", the refusal at y 501-524 of an 860-px viewport at
  700 px dark and light and at 1280 light, no horizontal scroll; looked at, then deleted.
- Privacy checks: 0 found on the added lines with both lists; per-file counts as main's. Head 537a58a; CI run
  <repo>/actions/runs/42694669955 started (in progress when this was written).

## Third round (the orchestrator's three items)

- Merged origin/v050-fixes (allin1's branch and main) into this branch first (884eb99), since items 1 and the
  probe touch pipeline.py's takes code and tests/test_pipeline.py's takes tests, which that branch had edited.
- **F2 / F3 / second advisor's finding 7** (0038dd1): closedNow loads `loadResults(was)`
  (`test_the_done_screen_loads_the_results_of_the_song_that_ended`; break: no id, fails). STEMS_NOT_SAVED says "The
  chart is not affected." (the stems test). Orphans: `<home>/state/chart.pid` (pid = the chart's process group, and
  its /proc start time) written at a chart's start, removed at its end; `jobs.stop_orphan` in server._main stops
  that group before the queue is read, only while its leader is the same process. Chosen over PR_SET_PDEATHSIG,
  which follows the thread that started the child: charts start from request and queue threads that end at once.
  Tests: `test_a_chart_left_by_a_server_killed_outright_is_stopped_at_the_next_start` (SIGKILL a stand-in server;
  the orphan alive; the next start stops it and its grandchild; the song waits, paused; break: no stop_orphan in
  _main, fails), `test_stop_orphan_stops_only_the_chart_its_file_names` (break: start time not compared, fails),
  `test_a_jobs_pid_file_lives_while_its_chart_runs`.
- **Item 1, 1 take by default** (fe7a453): pipeline (CUDA_TAKES 1, guitar_takes' text and evidence), the CLI help,
  estimate (CUDA_TAKES 1, BEST_TAKES 4), App.choices (quick = defaults, best = 4 takes), the page (Quick first and
  checked, "Best chart (4 guitar takes): slower, and only sometimes better" fills the box with 4), guide, DESIGN 2.7
  (a superseding decision with M8-02's and the repeat-consistency evidence), 4.5 and other mentions. A decision I
  made: several takes on CUDA asked for now also run the first take alone first (the probe was for takes=None only,
  so Best would have lost it); one case of the allin1 branch's test changed with it. Tests that relied on the CUDA
  default of 4 now ask for --takes 4. Breaks: CUDA_TAKES back to 4 fails 5 tests (pipeline, estimate, server); Best
  checked in index.html fails the html check. 700-px and 1280-px screens of the options: Quick checked, Best's
  words, takes box 4 on Best; no horizontal scroll.
- Checks: test_pipeline, the four UI files and test_stems_out: all pass (the full run, then the three pipeline tests
  fixed and re-run). Privacy: 0 found on the added lines with both lists, per-file counts equal main's. Golden charts
  are one CPU take: unaffected, not run. Head fe7a453, CI <repo>/actions/runs/42703889909
  (started); the previous run (537a58a) succeeded.
- Left: pipeline's probe comment and warning texts in the guitar stage still speak of "the first take alone first"
  generally (fine); the `auto` record now is True only for 1-take defaults.

## Fourth round (the re-review's R1-R3)

- Merged origin/v050-fixes (b94a41c) first: a fast-forward.
- R1 (a9d315d): stop_orphan runs only after bind; chart.pid records the server's pid and start time, and a chart
  whose server is alive is never stopped. Tests: `test_a_second_start_that_cannot_bind_never_stops_a_live_songcharters_chart`
  (the reviewer's repro; breaks: stop_orphan before bind, the server unchecked: each fails), the unit test's
  live-server case.
- R2: separate unlinks each WAV before writing it; eval/golden's seed_stems skips stems not made on the CPU. Tests:
  `test_stems_written_again_never_write_through_a_hard_link` (break: no unlink, fails), the golden seeding test's
  CUDA case (break: device unread, fails).
- R3: DESIGN's module table and parts table say 1 take by default, 4 for Best.
- Checks: test_ui_jobs, test_ui_library, test_ui_server, test_separate, test_golden: 208 passed. Privacy: 0 found
  on the added lines with both lists; per-file counts equal main's. Head a9d315d; CI run 42708286183 started.
- A stand-in chart left by test_a_cancel_by_id_... (a waiting song the queue started as the fixture shut down; it
  sleeps 60 s and exits) was seen once and killed; it predates this round.
