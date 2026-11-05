# M5-05: a guitar take that fails on CUDA is run again on the CPU (builder's report)

Branch `m5-05-gpu-retry`, from main at 9651d58 (after M5-06's merge). Built as the order says; the interpretations
the order left open are listed under "Decisions taken in the build" for the reviewer.

## Commits

- `521c2d9` pipeline: a guitar take that fails on CUDA is run again on the CPU, once a chart (M5-05):
  `songcharter/pipeline.py`, `songcharter/cli.py`, `songcharter/ui/static/app.js`, `tests/test_pipeline.py`.
- `3e10f3b` docs: DESIGN 2.7 and the guide on a guitar take run again on the CPU (M5-05): `docs/DESIGN.md`,
  `docs/guide/windows-wsl.md`.

Only the order's files were touched (`git diff origin/main...HEAD --stat`: those 6 files). PROGRESS.json is untouched,
as the brief says.

## What changed

- **Per-seed calls** (`pipeline._engine_stages`, the guitar stage). The new `run_take(k)` runs take k as a call of its
  own (`engines.guitar(wav, folder, [seed], device, ...)`), and its `take` event keeps the stage's numbering (index
  k+1 of all the stage's seeds; a cache hit sends none, as before). This applies to every chart: the CUDA default
  (probe, then three more), takes asked for, and the CPU. The probe stays as it is: the first take, then the
  transcriber check, then the rest. M5-02 can put its stitched-take warnings in `run_take` or in the loop over
  `zip(seeds, runs)` that follows.
- **The retry.** On CUDA, a ToolError whose exit code is positive (`autochart_exit`, split out of `take_failed`),
  with `options.cpu_retry` on and fewer than `CPU_RETRIES` (1) takes retried so far, runs the seed again with device
  "cpu" into the same folder. It first records the fallback `{"stage": "guitar", "from": "cuda", "to": "cpu",
  "reason": "take seed_N: the CUDA run failed (<line>); run again on the CPU"}` with the warning `guitar take seed N:
  the GPU run failed (<line>): run again on the CPU, about one transcription's time`, so the banner is up while the
  CPU take runs. Then it sends a `take` event with the same index and `"device": "cpu"`. The takes after it go back
  to CUDA.
  - `<line>` is `engine_line`: of the driver's stderr lines that autochart's ToolError quotes (after its own first
    line), the first that names an error or a failure (`error|fail`, case-insensitive), else the first of them,
    else `exit N`; cut to 120 characters with "...".
- **Not retried**, raised as in v0.1:
  - a signal (`stopped`);
  - a timeout and an exit 0 with no take (autochart's own message);
  - a second positive exit on CUDA: `gpu_failed` with " (one take was already run again on the CPU)" after
    "in take k of n";
  - anything with `cpu_retry` off;
  - a CPU chart (never classified, as before).
- **A retry that fails** goes through `take_failed(index, count, e, "cpu")`:
  - a positive exit gives `retry_failed`: "The guitar's run failed in take k of n on the GPU and again on the CPU;
    the takes that finished are kept. Close programs that use the GPU ... and chart it again[, or set Guitar takes
    to 1 ...]." It drops Device CPU, which just failed;
  - a signal gives `stopped` with "The guitar's CPU run was stopped ...";
  - a timeout or an exit 0 keeps autochart's message.
- **The first take retried** (the CUDA default): the probe keeps that take alone.
  - It records one fallback, the retry's, not a second for the probe.
  - It warns `guitar: the first take was run again on the CPU (its GPU run failed): that take is used alone, not 3
    more on the GPU`.
  - `takes.why` ends "; but the first take was run again on the CPU (its GPU run failed), so that take alone", and
    `transcriber_moved_to` is "cpu".
  - The probe treats a retried first take as moved even when its summary reports no device.
  - With takes asked for (no probe), the other takes still run on CUDA.
- **No double record:** the later loop that records "autochart ran on the CPU" for each take skips the retried seeds.
- **Records:** `record["takes"]` gets `devices`, the transcriber's device per seed from the take's summary (a list
  that follows `seeds`, None when a take reports none), and `cpu_retries`, the seeds retried. `Options.cpu_retry:
  bool = True`, checked as a bool. It shows in pipeline.json's `options`.
- **CLI:** `songcharter chart --no-cpu-retry`, which sets `cpu_retry=False`, with its help text and the usage line in
  cli.py's docstring.
- **The page:** app.js's `take` handler shows "take k of n (on the CPU)" for an event with `device` "cpu".
- **The module docstring:**
  - a new bullet on the retry: what is retried, the cap, what is not, the device rule (a later CUDA chart does not
    reuse the CPU take and runs it on CUDA again), and the first-take case;
  - the fallback list now includes the retry;
  - the `take` event's description now includes the CPU retry's event.
- **Docs:**
  - DESIGN 2.7 gets a new subsection, "A take that fails on CUDA: run again on the CPU, once (M5-05)". It covers the
    retry as built, its cap and what is not retried, the owner's default, and the risk the gate measures (the
    memory=12GB A23 provoked failure, `min_available_ram_mb` and `max_swap_used_mb`, the swap > 4 GB rule).
  - The guide's section 5 gets one bullet: a failed take is run again on the CPU once a song, and the page says so.

## Decisions taken in the build (for the reviewer)

1. **Every take is a call of its own, on every device.** The order says "the takes after the first". The first was
   already its own call under the probe, and the non-probe paths (takes asked for, the CPU) are now per seed too.
   That keeps one loop for M5-02. It costs one more SHA-256 of decode.wav and one `install_key` per take, under a
   second each.
2. **The retry's failure messages.** The order says "with the device named" and leaves the wording open:
   - positive exit: `retry_failed`, worded as above;
   - signal: `stopped` with "CPU run".
3. **The warning uses "seed N"** (a space) and the reason "seed_N", as the order writes them. The existing take
   warnings say "seed_N"; M5-02's order also writes "guitar take seed N".
4. **"The engine's first error line"** is read as the first quoted stderr line that names an error or a failure.
   The quoted tail's literal first line is usually a progress line (`[autochart] expert: engine job` in the test's
   OOM tail).
5. **The probe after a retried first take** warns and records nothing more. The order's "its warning says why" is
   met by the warning's text, and one move gets one fallback record.

## Checks

- **[dev] The suite**: `SONGCHARTER_SCAN_CHART=<worktree>/tools/scan-chart/scan.cjs tools/heavy.sh uv run python -m
  pytest -q -p no:cacheprovider --basetemp=/dev/shm/pt-m5-05`. Result: `895 passed, 4 skipped in 699.65s
  (0:11:39)`, exit 0. The worktree's environment was set up first with `tools/heavy.sh sh -c 'uv sync --frozen
  --extra cpu --extra app --extra dev && (cd tools/scan-chart && npm ci)'`.
- **[dev] The tests fail when their code is broken.** A scratch script applied each break to the committed code, ran
  `pytest tests/test_pipeline.py -k <test>` and restored the file. All 21 breaks failed their test:
  - B1, no retry at all (always raise);
  - B2, `CPU_RETRIES = 2` (the second CUDA failure is retried);
  - B3, a signal retried too (`!= 0` for `> 0`), caught by says_what_to_do's -9 case through the driver's
    (seed, device) runs;
  - B4, `cpu_retry` ignored;
  - B5, the retry's failure raised raw (not through `take_failed`);
  - B6, the retry's failure classified as CUDA's;
  - B7, the "one take was already run again" sentence dropped;
  - B8, the probe ignores the retry (the case where the summary reports no device);
  - B8b, a retried first take reported as autochart's own move;
  - B9, the retried take recorded twice ("autochart ran on the CPU");
  - B10, the take event without `device`;
  - B11, the reason quotes the first line, not the error line;
  - B12, the line not cut to 120;
  - B13, `devices` not from the summary;
  - B14, `cpu_retries` empty;
  - B15, the CLI flag not wired to Options;
  - B16, the retry run on CUDA again;
  - B17, `cpu_retry` not checked as a bool;
  - B18, a CPU chart's failure retried (the `gdev != "cuda"` guard removed);
  - B19, the takes after the first in one call;
  - B20, the retry's warning dropped (recorded only).
- **The tests** (`tests/test_pipeline.py`):
  - New: `test_a_guitar_take_that_fails_on_cuda_is_run_again_on_the_cpu`, with the real `Engines.guitar` and
    `autochart.generate` and the stand-in driver `Autochart`, which now fails per device (`how={"cuda": 1}`) and
    records (seed, device) per run. It covers, in order:
    - the 4-take retry of seed 202: calls per seed with their devices, the fallback and warning, take events
      3 of 4 twice (the second with cpu), the banner before the CPU take, `devices` and `cpu_retries`, and 4 takes
      to assemble;
    - a re-chart on CUDA that runs seed 202 on CUDA again;
    - a second CUDA failure;
    - the retry failing by exit 1, by a signal and by a timeout;
    - the first take retried, also with no devices reported;
    - takes asked for with the first take retried.
  - Changed: `real_guitar` is the shared setup, split out of the v0.1 test.
    `test_a_guitar_take_that_fails_on_cuda_says_what_to_do` now runs its exit-1 cases with `--no-cpu-retry`, and
    checks that `options.cpu_retry` is False there and True by default. Its signal, timeout, exit 0 and bug cases
    run with the retry on and show that nothing was rerun.
  - Updated for the per-seed calls and the new keys: `test_takes_follow_the_guitar_stages_device`,
    `test_the_cli_options_reach_the_engines`, `test_the_engines_get_the_decode_its_stems_and_the_options` and
    `test_options_and_seeds` (cpu_retry's default and its check).
- **[dev] Golden, `--expect none`** (`<golden>` is the dev machine's golden folder, `<worktree>` this order's worktree). The commands ran with the brief's environment (EVAL_DATA, SONGCHARTER_GOLDEN,
  SONGCHARTER_SCAN_CHART, SONGCHARTER_AUTOCHART, SONGCHARTER_ALLIN1_PYTHON):
  - `python -m eval.golden run --code <worktree> --out <golden>/m5-05 --threads 2`: 7 songs
    warm, every engine cached, `summary: .../m5-05/summary.json (324 s)`, exit 0.
  - `python -m eval.golden diff <golden>/base <golden>/m5-05 --expect none`: `golden diff:
    no UNEXPECTED change`, exit 0. The report says "Every song's results (hashes, counts, scores) identical: yes",
    and the pooled F1s are unchanged (guitar Expert 0.8527, bass Expert 0.8247, drums Expert 0.9617).
  - The base is main at fbd9751. M5-06's merge changed no note, as the brief says.
- **[CI]** `gh workflow run ci --ref m5-05-gpu-retry`: run 42057109593 on 3e10f3b, conclusion **success**.
  - linux: 22m10s, `895 passed, 4 skipped`, `all 7 Linux hooks passed`.
  - windows: 1m3s.
  - This order adds no CI hook: its checks are in the suite, which CI runs.
- **The page's take line**, by hand in node with tests/test_ui_server.py's stand-in DOM, from a script in the
  scratch folder. On the branch the three events give `["take 3 of 4","take 3 of 4 (on the CPU)","take 4 of 4"]`;
  main's app.js gives `["take 3 of 4","take 3 of 4","take 4 of 4"]`.
- **Scan:** I scanned the branch's diff (`git diff origin/main...HEAD`) and its two commit messages for lyrics,
  audio, assistant model names and personal details (names, usernames, paths, emails). There were none; the commit
  messages carry only the brief's trailer lines.

## Not done, uncertain, for later

- **The hardware check is the release gate's** (the order): M4-08's A23 under memory=12GB on the owner's PC. That is
  where the memory of a CPU engine beside the parent's CUDA context gets measured. Nothing here measured it.
- **README.md lists chart flags** (it mentions `--no-preview`), and it is not among the order's files, so
  `--no-cpu-retry` is not in it. The orchestrator may add it at the merge.
- **M5-02:** a piece that fails "raises exactly as a failed take does (`take_failed` on CUDA ...)". With this order,
  a whole-song take that fails on CUDA is retried on the CPU. M5-02 should decide whether a failing piece is retried
  too, and whether it counts against `CPU_RETRIES`. That belongs in M5-02's order, which this order may not touch.
- **The page's take line has no in-suite test.** tests/test_ui_server.py is not among the order's files. I checked it
  by hand in node with that file's stand-in DOM: "take 3 of 4", then "take 3 of 4 (on the CPU)", then "take 4 of 4"
  on the branch, while main's app.js shows no "(on the CPU)".
- The reason quotes the engine's line verbatim, the "[autochart] FAILED: ..." prefix included, cut to 120
  characters.

## Review fixes

**F1 (major; a skeptic confirmed it with the real driver, engine and models).** `ac_headless.cjs` exits 1 whatever
failed. That includes an engine killed by a signal (the OOM killer), the driver's wall-clock timeout and its stall
kill. `autochart_exit` read 1 for all of them, so the take was retried on the CPU and called a GPU failure; v0.1
already called them GPU failures. The fix follows the orchestrator's decision, the stricter rule, in pipeline.py
only. The driver, `engines/autochart.py` and the take's key are unchanged.

- **The classifier.** `pipeline.failure(error) -> (kind, signum, line)` reads the driver's last `[autochart] FAILED:`
  line in the quoted tail before the exit code:
  - `engine failed (exit <int>) ...` gives "engine". This is the only GPU failure: retried once on the CPU, as built,
    and `gpu_failed`'s advice when not retried.
  - `engine failed (exit null SIG...)` gives "signal". It gets `stopped`'s advice with that signal (SIGKILL: WSL
    likely ran out of memory) and is never retried. A signal name that Python does not know counts as "driver".
  - Any other FAILED line gives "driver": the wall-clock timeout, "no decoder progress", the token cap, models
    missing, no shared beat map, ffmpeg. The new `driver_failed` says "The guitar's run failed in take k of n
    (<the driver's line, at most 120 characters>); the takes that finished are kept.", then autochart's lines. It
    gives no GPU advice and never retries.
  - With no FAILED line, the exit code decides as before: positive "engine", negative "signal", otherwise the
    message stays autochart's own.
- **Callers.** `run_take` retries only kind "engine". `take_failed` sends each kind to its message. On the CPU retry
  the CPU's run is named: "The guitar's CPU run was stopped ..." and "The guitar's CPU run failed (...)".
  `retry_failed` is now reached only for an engine failure on both devices, and its wording stays.
- **Docs.** The module docstring, DESIGN 2.7 (a new bullet "What a failure is", and the not-retried list) and the
  guide's bullet ("or a take was stopped because the PC ran out of memory") follow the new rule.
- **Tests.** The new `test_the_drivers_failed_line_says_what_failed` uses the driver's real lines from the skeptic's
  report: KILLED, TIMEOUT, STALL, TOKENS, MODELS and BEAT_MAP. `Autochart` now accepts a stderr text as `how` (exit
  1 with that stderr). The test covers:
  - the classifier over every class, plus an unknown signal name, a tail with no FAILED line, the driver killed
    itself (-9) and exit 0;
  - on CUDA, each of the six lines: exit 2, no CPU run, no fallback, the message exact and without "GPU";
  - for the CPU retry, KILLED, TIMEOUT and MODELS: the CPU's run named;
  - an engine failure with no FAILED line quoted, which is still retried;
  - `driver_failed`'s 120-character cut.
- **Breaks.** All 9 breaks failed the new test:
  - R1, the FAILED line ignored;
  - R2, a signal retried;
  - R3, a driver failure retried;
  - R4, a driver failure called the GPU's;
  - R5, driver_failed not told the device;
  - R6, stopped not told the device;
  - R7, no exit-code rule without a FAILED line;
  - R9, an unknown signal name taken as a signal;
  - R10, the driver's reason not cut.
- **Commit:** `677512d` Review fixes: the driver's FAILED line decides what a failed guitar take is.
- **Checks:**
  - Targeted run (`-k "failed_line or run_again_on_the_cpu or says_what_to_do"`): `3 passed`.
  - Full suite (`tools/heavy.sh uv run python -m pytest -q -p no:cacheprovider --basetemp=/dev/shm/pt-m5-05`): `896 passed, 4 skipped in 679.82s`, exit 0.
  - CI run 42068700727 on 677512d: **success**. linux 15m53s, `896 passed, 4 skipped`, `all 7 Linux hooks passed`; windows 54s.
  - Golden: not rerun. A CPU chart never reaches the changed code: `failure` and `take_failed` run only when the
    guitar runs on CUDA, and a CPU chart's failure is still raised as it is (`gdev != "cuda"`).
- **Scan:** I scanned the fix commit's diff and message; they hold only the trailer lines and no personal details.

## Review (sc-reviewer, 2026-11-05)

# M5-05 review (sc-reviewer): correctness of the CPU retry

Reviewed origin/main...origin/m5-05-gpu-retry at 3e10f3b, in a git-archive copy at /dev/shm/review_m505 (now deleted).

## F1 major: an engine killed by a signal, or by the driver's own timeout, is retried on the CPU (pipeline.py:1027)

The retry is gated on the exit code of the *driver* (`autochart_exit(e) > 0`). But the process that gets killed
is the engine, which is the driver's child. eval/tools/autochart/ac_headless.cjs:231 turns any engine death into
`fail(...)`, which exits 1 (line 285). The stderr reads `engine failed (exit null SIGKILL)`. So three cases that the
order, the docstring (pipeline.py:62) and DESIGN 2.7 say are not retried all reach the CPU retry:
- the kernel's OOM killer on the engine (M4-02 saw the *engine* OOM-killed at 12.8 GB);
- the driver's wall-clock timeout (AC_TIMEOUT_S = timeout_s, ac_headless.cjs:110). It fires 600 s before Python's
  `TimeoutExpired`, so it is the timeout that happens in practice;
- the driver's stall kill.
The memory case is the risk the gate is meant to guard: a CPU engine starting beside the parent's CUDA context
just after host memory ran out. The timeout case can cost up to another hour on the slower device. The warning also
tells the friend "the GPU run failed", which is wrong in these cases. v0.1 already misclassified these as
`gpu_failed` (rc-fixes F1 assumed exit -9). M5-05 makes that classification decide whether to rerun.

Repro: a test appended to a copy of tests/test_pipeline.py. Its stand-in driver exits 1 for seed 202 on cuda, with
the driver's real kill lines in stderr. Output:
```
REPRO 'wall-clock timeout 3600s' code 0 runs [(202, 'cuda'), (202, 'cpu'), (303, 'cuda')] fallback take seed_202: the CUDA run failed ([autochart] FAILED: expert: engine failed (exit null SIGKILL) transcription); run again on the CPU
REPRO 'no decoder progress for 900s' code 0 runs [(202, 'cuda'), (202, 'cpu'), (303, 'cuda')] ...
REPRO 'OOM killer' code 0 runs [(202, 'cuda'), (202, 'cpu'), (303, 'cuda')] ...
```
Possible fix, for the skeptic: do not retry (and do not call it gpu_failed) when the quoted tail shows
`engine failed (exit null <SIG...>)` or `killing engine:`. Use stopped's advice for a signal, and the driver's own
message for a timeout or stall.

## Other checks: no defects found
- Test the tests. I made 7 breaks of my own on top of the builder's 21, and each one failed a test:
  X1 the takes after a retry stay on the CPU; X2 the fallback recorded after the CPU take; X3 the probe's warning
  dropped; X4 stopped() not told the device; X5 `> 0` loosened to `>= 0`; X6 the CPU take's index taken from
  autochart's 1-of-1; X7 `cpu_retry` off by default.
- Per-seed loop: the take numbering, cache hits sending no event, the shared work/scratch folder, the probe, and the
  strict zip with `retried` skipped in the "ran on the CPU" loop all check out. The take's key and
  engines/autochart.py are unchanged.
- The CLI flag, app.js's take line, and the guide bullet match the code, apart from F1's "signal" claim.
- The five decisions in the builder's report: none of them is a defect.

## Skeptic on F1 (sc-skeptic, 2026-11-05)

# M5-05 skeptic: F1 (engine killed / driver timeout / stall kill retried on the CPU)

**Verdict: CONFIRMED, all three cases. Severity: major** (as the reviewer gave it). Branch m5-05-gpu-retry at 3e10f3b,
read-only; work in /dev/shm/skeptic_m505 (deleted).

## Code paths
- ac_headless.cjs (same file in v0.1.0, main and the branch): `kill(why)` logs `<diff>: killing engine: <why>` and
  SIGKILLs the engine (its child). The wall-clock timer (AC_TIMEOUT_S) and the stall check (AC_STALL_S, in stage
  transcription only) both go through it, then `fail("<diff>: <why>")`. An engine killed from outside gives
  `close(code=null, signal=SIGKILL)`, then `fail("<diff>: engine failed (exit null SIGKILL) ...")`. Every `fail` ends in
  `main().catch` -> `log("FAILED: ...")`, `process.exit(1)`. So the driver exits 1 in all three cases, and the FAILED line
  is the last line of its stderr.
- engines/autochart.py: `proc.returncode != 0` -> `ToolError("autochart seed N failed (exit 1):\n<last 8 lines>")`.
  Python's own `TimeoutExpired` (exit 0 for the gate, not retried) is at timeout_s + 600, so the driver's kill at
  timeout_s always comes first. A returncode < 0 happens only when the driver itself is killed, not the engine.
- pipeline.py:1027 `autochart_exit(e) > 0` reads only that `(exit 1)`. Nothing upstream parses the tail.

## What I ran (real driver, real engine, real models, AC_DEVICE cpu, synthetic sine+noise clips)
`engines.autochart.generate` from the branch, then `autochart_exit`, the gate and `take_failed` on the ToolError:
| case | driver's last line | autochart_exit | retried on CPU |
|---|---|---|---|
| engine SIGKILLed mid-transcription (OOM-killer stand-in) | `FAILED: expert: engine failed (exit null SIGKILL)` | 1 | yes |
| AC_TIMEOUT_S=1 | `killing engine: wall-clock timeout 1s` / `FAILED: expert: wall-clock timeout 1s` | 1 | yes |
| AC_STALL_S=1, engine SIGSTOPped in transcription (a hung decoder) | `killing engine: no decoder progress for 1s` / `FAILED: expert: no decoder progress for 1s` | 1 | yes |

The driver's kill and fail paths do not read AC_DEVICE, so on cuda the ToolError text, and so the gate, are the same.
The reviewer's stand-in showed run_take doing the CPU run after that gate. One small correction: for the timeout and the
stall, the stderr is the `wall-clock timeout` / `no decoder progress` lines above, not `engine failed (exit null SIGKILL)`.

## v0.1's messages
They are affected too. v0.1.0's take_failed has the same `code > 0` -> gpu_failed, and the driver is unchanged. All
three cases print "The guitar's GPU run failed ... If it fails again, set Device to CPU." The OOM kill should get
stopped's "signal 9, SIGKILL, which usually means WSL ran out of memory". The timeout and the stall should get the
driver's own line. stopped() (code < 0) can be reached only if the driver itself is killed, so in practice it never runs.
On the branch, with the retry spent or off, and in retry_failed ("failed on the GPU and again on the CPU"), the message
is wrong in the same way.

## Smallest fix (pipeline.py only; the driver and engines/autochart.py stay as they are)
In autochart_exit, read the driver's FAILED line (always inside the quoted tail) before the exit code:
```python
DRIVER_SIGNAL = re.compile(r"FAILED: \w+: engine failed \(exit null (SIG[A-Z0-9]+)\)")
DRIVER_KILL = re.compile(r"FAILED: \w+: (?:wall-clock timeout|no decoder progress|token cap)")
    ...
    if m and (s := DRIVER_SIGNAL.search(text)):
        sig = getattr(signal, s.group(1), None); return -int(sig) if sig else -1   # the engine killed: stopped
    if m and DRIVER_KILL.search(text):
        return 0                                                                    # the driver's kill: its own message
```
With that change, take_failed and run_take give stopped (with the WSL memory advice) for a signal, and autochart's own
message for a timeout or a stall, with no CPU retry. Update autochart_exit's and take_failed's docstrings. Add 3 tests
to tests/test_pipeline.py with the driver's real lines above (assert: no CPU run, stopped's message for SIGKILL, the
timeout and stall lines as they are). A stricter option: retry only when the last line is `engine failed (exit <int>)`.
That also stops driver-side failures (`models missing`, `takes do not share one beat map`, ffmpeg), which exit 1 too,
from being retried on the CPU and reported as gpu_failed. A test of the classifier against the real driver's stderr would
catch it if the driver's wording changed.
