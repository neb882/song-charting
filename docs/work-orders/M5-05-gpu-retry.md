# M5-05: a guitar take that fails on CUDA is run again on the CPU

**Branch:** `m5-05-gpu-retry`, from `main` after M5-06's merge (wave 1, in the builder slot beside M5-09 once M5-06
is done; it needs nothing of M5-09). **Agent:** `sc-builder`, then `sc-reviewer`. May push its branch to run CI.
**Files:** `songcharter/pipeline.py` (the guitar stage, `Options`, the module docstring), `songcharter/cli.py` (one
flag), `tests/test_pipeline.py`, `songcharter/ui/static/app.js` (the take line only; M5-07 touches app.js after this
merges), `docs/DESIGN.md` 2.7, `docs/guide/windows-wsl.md` (one bullet). **Time budget:** 1 day. M5-02 (wave 2)
adds its stitched-take warnings to the per-seed loop this order makes.

## Why

v0.1 ends a chart when a guitar take fails on CUDA, with advice (`pipeline.gpu_failed`: close programs that use the
GPU, chart again, Guitar takes 1, Device CPU). The skeptic's option (b) on the advisor's finding 1 (`docs/reports/
rc-advisor.md`) deferred the better fix to the next version: run the failed take again on the CPU, record it as a
fallback and keep the rest on CUDA. The friend's 4070 has about 9.5 GB free at idle and the takes peak near 9 GB on
the owner's card; a browser or Clone Hero left open can tip a take over. A retry costs about one CPU transcription
(217 s for the 6:52 test song on the dev container; the friend's CPU is unmeasured) instead of a dead end.

## What to build

1. **Per-seed calls.** The guitar stage runs the takes after the first one seed at a time (`engines.guitar(wav,
   folder, [seed], gdev, ...)`), each with the `take` event numbered as today (index among all the stage's seeds;
   finished takes are cache hits and cost nothing). The first take's probe stays as it is.
2. **The retry.** When a take on CUDA raises a ToolError that `take_failed` classifies as `gpu_failed` (a positive
   exit code: the engine failed inside, as a GPU short of memory does), and `options.cpu_retry` is on, and no take of
   this chart was retried yet (`CPU_RETRIES` = 1): run that seed again with device `"cpu"` into the same folder
   (`_done`'s device rule means a later CUDA run will not reuse it: say so in the docstring), emit a `take` event with
   `"device": "cpu"` and the same index, and record a fallback `{"stage": "guitar", "from": "cuda", "to": "cpu",
   "reason": "take seed_N: the CUDA run failed (<the engine's first error line, at most 120 characters>); run again
   on the CPU"}` with the warning `guitar take seed N: the GPU run failed (...): run again on the CPU, about one
   transcription's time`. Not retried, raised as today: a `stopped` take (a signal: memory, where the CPU would not
   help), a timeout, an exit 0 with no summary, a second `gpu_failed` in the same chart (then `gpu_failed`'s advice,
   with "one take was already run again on the CPU" added), and anything with `cpu_retry` off.
   - A retry that fails raises that failure through `take_failed` with the device named (`gdev` is "cpu" for it).
   - The first take failing on CUDA is retried the same way; the existing probe rule then sees a CPU transcriber and
     keeps that take alone (its warning says why).
3. **Records:** `record["takes"]` gets `devices` (per seed: the device the transcriber ran on, from the take's
   summary) and `cpu_retries` (the seeds retried). `Options.cpu_retry: bool = True`; `songcharter chart
   --no-cpu-retry`; the page gets no control (the default is the friend's).
4. **The page:** the take line shows "take k of n (on the CPU)" for a take event with `device` "cpu" (app.js's
   `take` handler; the fallback banner already shows the warning).

## Tests

- `standins` with a guitar engine that fails with exit 1 on cuda for seed 202 and succeeds on cpu: the calls are per
  seed with the right devices; the fallback record and warning; `record["takes"]["devices"]` and `cpu_retries`; the
  `take` events (index 3 of 4 twice, the second with device cpu); the chart finishes with 4 takes.
- Not retried: a signal (negative exit) raises `stopped`; a timeout raises the engine's ToolError; a second cuda
  failure raises `gpu_failed` with the added sentence; `cpu_retry=False` raises as today; on a cpu chart nothing is
  classified.
- The retry itself failing raises through `take_failed` with cpu named.
- The first take failing and retried: the probe keeps it alone, with the warning.
- The CLI flag reaches `Options`.
- Each test fails when its code is broken (say which break).

## Evaluation

- **Golden:** `pipeline.py` only, a path the CPU golden runs never take: `--expect none` (the cheap run).
- **Hardware, at the release gate** (the owner's PC, M5-00's gate): M4-08's A23 provoked failure under
  `memory=12GB`: during take 2 a program fills the GPU's memory; the chart must finish with take 2 on the CPU, the
  banner showing the fallback, and the job's memory samples (`pipeline.json`, the guitar stage's
  `min_available_ram_mb` and `max_swap_used_mb`) recorded: the CPU engine beside the parent's CUDA context is the
  risk (autochart's node engine was once seen at 12.8 GB on the CPU). If the retry is killed for memory, the chart
  fails with `stopped`'s advice, no worse than v0.1; if swap passes 4 GB during the retry, the default goes to
  `cpu_retry` off for WSL [decision at the gate, the owner's].

## Done means

- [dev] The suite; the new tests fail when their code is broken.
- [dev] The golden diff, exit 0.
- [CI] Green on the branch.
- [docs] DESIGN 2.7 (the retry, its cap and what is not retried; the risk and the gate check); the guide's section 5:
  one bullet (a GPU failure is retried on the CPU once; the page says so); the pipeline docstring.

## Limits

- No change to `engines/autochart.py` or the take's key. The engine's error text is quoted at most to its first line.
- `cpu_retry` on by default [decided by the owner, 2026-11-05: the friend's PC has the memory headroom the install
  set, and a dead end costs him more than a slow take]; recorded as a fallback; the gate measures its memory under
  `memory=12GB` on the owner's PC and can turn it off for WSL.

## Report

`<scratchpad>/briefs/m5-05.report.md`: the commits, each check's last lines, the golden verdict, anything uncertain.
