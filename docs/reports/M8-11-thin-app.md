# M8-11's thin spike on the installed app (`eval/gpu.sh thin-spike --app`)

*Merged 2026-11-09 at 3572b24 (branch m8-11-thin-app, head 041ff91; CI run 42686730767 green on Linux and
Windows). An eval-only change: M8-11 (docs/work-orders/M8-11-thin-runs.md) asks that the spike run on the installed
app before the owner is asked, since he has the app and a clone but no eval tools. M8-02 part D recommended the spike
(the fast runs' recall at 100 ms 0.659 against the 0.7 bar), and the owner agreed to run it on 2026-11-09.*

**The review** (one reviewer, who also tested the tests): no privacy defect; one major and three minors, all fixed.
R1 (major): a rerun kept a take made on the CPU or with other settings. A take is now kept only when its input's
SHA-256, seed, temperature, knobs and the transcriber's device all match. No skeptic ran: the fix only narrows when a
take is kept, so a wrong finding would cost one take made again. R2: `ALLOW_CPU=1` skipped the stop after a CPU take
too; now it skips only the start check, and the README tells the owner not to set it. R3: the references' arm named
the six by brace expansion, not a glob that took in the test song. R4: four breaks the tests missed now fail a test
(27 breaks in all, each failing one).

The builder's report follows, with paths as placeholders.

# M8-11 prerequisite: the thin spike on the installed app (`eval/gpu.sh thin-spike --app`)

Branch `m8-11-thin-app` (from origin/main af9b019), worktree `<wt>/m8-11`. Eval-only: eval/gpu.sh,
eval/spike/thin_spike.sh, eval/README.md, tests/test_eval_thin_spike.py. Nothing in songcharter/, nothing that
charts, PROGRESS untouched. Not merged.

## Commits

| commit | what |
|---|---|
| f612b8e | thin spike: several inputs, takes kept by input, a zip of charts and stripped summaries behind a guard |
| 0916bf0 | gpu.sh thin-spike --app: the installed app's autochart, Node, Python and ffmpeg; takes' check first |
| 3afd64d | Tests: the thin spike on a made-up app and on eval/tools, with the real driver and a made-up engine |
| 8c33804 | eval/README: the thin spike with the installed app, and the references' arm |
| fb54a82 | Tests: the thin spike's lines wrapped at 120 |
| 84848a5 | Merge origin/main (M8-02's report and scripts, v0.5.0's version; no file of this branch's) |

Head: **84848a5**, pushed to `origin/m8-11-thin-app`.

## What changed

**eval/gpu.sh**
- `thin-spike [--app] AUDIO...` (and `SONGCHARTER_APP=1`). Under `--app`, `app_env` (the existing function, now also
  reading runtime.json's `autochart`, and keeping its `ffmpeg`, as `APP_AUTOCHART` and `APP_FFMPEG`, not exported)
  gives the spike the app's Python (`EVAL_PY`), Node (first on PATH), autochart (`SONGCHARTER_AUTOCHART`) and ffmpeg
  (`AUTOCHART_FFMPEG_PATH`, `FFMPEG` winning as in the launcher). Nothing is copied from takes.py; the spike runs the
  driver itself, so it needs the install's paths rather than takes.py's `generate`.
- Before anything detaches, under `--app`: `takes.py --app --check --device ${AC_DEVICE:-cuda}`, the check `takes`
  runs (the lane, the CUDA provider, the CUDA 13 and cuDNN libraries). A failure stops it ("check failed: not
  starting"), unless `ALLOW_CPU=1`, as in `takes`. No app: exit 2. `nvidia-smi` is required only for `cuda`, so
  `AC_DEVICE=cpu` makes a dry run on a machine without a GPU.
- `_thin` passes `--app` to the detached half (`SONGCHARTER_APP=$APP setsid ...`, as `_takes` does) and runs
  thin_spike.sh with `SPIKE_OUT=$RUNS/thin_spike`. Without `--app` it runs as before (eval/tools' autochart,
  `SONGCHARTER_AUTOCHART`, the repo's `.venv`).
- `status` also shows the spike's log; the header and `start`'s refusal name thin-spike among the `--app` commands.

**eval/spike/thin_spike.sh**
- **Several inputs, labels, takes kept by input.** `thin_spike.sh AUDIO...`, OUT from `SPIKE_OUT`. Each file's takes
  are `OUT/<label>/<arm>/seed_<seed>/`: a built set's `input.wav` by its folder's id (`refs/<id>/input.wav` -> `<id>`,
  the id matching `[a-z][a-z0-9_]*`), any other file `song` (`song_2`, ... when taken). A take is kept only when its
  summary's `inputSha256` is the file's SHA-256 (`sha256sum`); otherwise it is made again, with a line saying so.
  Why: the brief wants the references' arm served by "the same steps", once per reference's input. With one fixed
  OUT and takes kept by arm and seed alone, the second song's run would have "kept" the first song's takes and zipped
  them as its own. **This is a choice the brief does not make**: the alternative is one detached run per reference
  with a name argument (6-7 manual starts). I chose one line for all of them (`eval/data/refs/*/input.wav`).
- **The patch:** each of the four targets must be found exactly once (it checked only "at least once", though its
  comment said exactly once); the `const HERE = __dirname;` swap is now checked as well.
- **The zip** holds this run's takes only: each `notes.chart` as the engine wrote it, and each
  `autochart_run/summary.json` copied field by field: numbers, booleans, nulls, short names (`[A-Za-z0-9_.+ -]{1,40}`)
  and SHA-256s, recursively, so the driver's `input` (the song's path), `ffmpeg` (the install's path), `runs[].jobDir`
  and any message with a path are dropped; `knobs` and `knobsActive` are kept. **The log is no longer in the zip**
  (it held the driver's stderr, with paths, and the song's file name; the brief says "charts and summaries only").
  Then a guard reads the finished zip back, as `results`' does in a smaller form: the home folder or its real path, a
  Windows user folder, a `\\wsl$` path, or the user name (USER and the home folder's name, 3+ characters, as a whole
  word in any case) stops it, naming the member and the kind; then `check_no_audio.py` (the guard `results` uses). A
  stopped zip is deleted with the one before it.
- **The log** (`OUT/thin_spike.log`, on the PC only): its lines and the driver's stderr have the home folder as `~`
  (the driver's stderr is piped through `tilde_lines` synchronously, so following it with `tail -f` still works).
- Kept as they were: the stop after a take whose transcriber did not run on the asked device (`ALLOW_CPU=1` keeps
  going), the patched copy in OUT (the install's driver untouched), the shared work folder. Also: `SEEDS` takes commas
  (takes.py's form), and the CUDA-library call runs with `-B` (`-I` ignores PYTHONDONTWRITEBYTECODE; it left
  `__pycache__` in the checkout).

**eval/README.md**: a section after "GPU takes with the installed app", for the owner (below).

## The patch on v0.4.0's install and main's

- What the install puts in place: `songcharter.runtime.step_autochart` copies `DRIVER_FILES` (`ac_headless.cjs`,
  `package.json`, `package-lock.json`) from the app's own `eval/tools/autochart` into `runtime/autochart`
  (`_copy_files`); the same in v0.4.0's runtime.py (lines 67 and 436).
- v0.4.0's release asset `songcharter-0.4.0.tar.gz`, downloaded from the release and checked against its
  `SHA256SUMS` (OK): its `eval/tools/autochart/ac_headless.cjs` has SHA-256 `6b6f4809...2725`, the same as main's
  (and as `git show v0.4.0:` gives). `git diff v0.4.0 HEAD` is empty for eval/tools/autochart/, runtime.py,
  install.sh, engines/autochart.py and launch.py.
- The spike's patch (its node block, extracted from thin_spike.sh) on the release's driver: exit 0, all four targets
  once, and `node --check` passes on the result.
- Main's install: the dry run's stand-in was made by the install's own `step_autochart` from this branch's tree (main's
  driver), and the spike patched and ran that installed driver (below). The tests copy `runtime.DRIVER_FILES` from
  eval/tools/autochart the same way and run the real driver patched. No target moved: no fix needed.

## Checks

**Tests** (`tests/test_eval_thin_spike.py`, 15; bash and Node, skipped on Windows; `PYTHONDONTWRITEBYTECODE=1`, no
`__pycache__` left). The real driver, copied as the install copies it and patched as the spike patches it, runs a
made-up engine (Node: it answers the job with result.json, a chart and a report, and records the settings it got):
- `test_app_spike_runs_the_apps_autochart_node_and_ffmpeg_and_zips_no_path`: `eval/gpu.sh thin-spike --app` on a
  made-up PC (the takes tests' `cli_app`: HOME, the app's runtime.json with its autochart elsewhere than the default
  folder, a logging wrapper of the real Node, a stand-in ffmpeg, a stand-in nvidia-smi) with two inputs, a built
  reference's `input.wav` and a song in ~/Music; it waits for the detached run. The check ran and passed; the app's
  Node ran the patched driver; the engine got the app's ffmpeg, `cuda`, the base and dense5 knobs; the zip holds
  exactly the 8 members under `aaa/` and `song/`; the raw summaries hold the home folder, the zip's hold no path, home
  folder or user name; `check_no_audio: ok`; no song.ogg left; the install's driver is untouched; the log has no
  home folder.
- `test_app_spike_refuses_before_anything_detaches` (cu126 lane: the check's problem; no app: exit 2): nothing
  under runs/, no home folder printed.
- `test_the_spike_without_app_runs_eval_tools_autochart_as_before` (`_thin` without --app).
- `test_the_patch_applies_each_target_exactly_once_or_stops` (a target gone, a target twice, the HERE target gone).
- `test_the_install_driver_patches_and_records_the_knobs` (speed=6,chords=2 and T=1.05 reach the job and the
  summary; a second run's zip holds its own takes only).
- `test_the_guard_stops_a_zip_with_a_path_a_user_name_or_audio` (a home path, the user name in upper case, a
  /mnt/c/Users path, a chart starting with RIFF): no zip, not even the one before; the stop line names the member and
  kind; nothing printed or logged holds the home folder.
- `test_a_take_on_the_cpu_stops_the_spike_unless_allowed` (both ways).
- `test_a_take_is_kept_only_for_the_same_input` (kept; another input under the same label made again; two files as
  `song` and `song_2`; commas in SEEDS).

**Each break fails a test** (scratch harness: one edit, the file's tests, the edit undone; all 16 caught):

| break | failing test(s) |
|---|---|
| the summary copy keeps every string | the --app e2e, the guard, cpu, kept, knobs, non-app (the guard stops the zip) |
| the guard ignores its stops | the guard's three path/user plants |
| no check_no_audio | the RIFF plant; the e2e (its "check_no_audio: ok") |
| the patch accepts a target twice | the patch test's "twice" case |
| a take kept whatever its input | kept-by-input |
| no stop after a CPU take | cpu, not allowed |
| the driver's stderr not tilde'd | the e2e and the guard's (no home folder in the log) |
| every file labelled song | the e2e (`aaa/` members) |
| the zip holds every take in OUT | knobs (the second run's zip); missed at first, caught after adding that assertion |
| `_thin` loses --app | the e2e |
| app_env ignores runtime.json's autochart | the e2e (the app's autochart is not in the default folder) |
| `_thin` without the app's ffmpeg | the e2e |
| `_thin` without the app's autochart | the e2e |
| no check before detaching | the cu126 refusal; the e2e ("check: ok") |
| app_env's failure ignored up front | the no-app refusal |
| the non-app OUT moved | the non-app test |

The existing `tests/test_eval_takes.py` (58) passes with the gpu.sh changes.

**The CPU dry run** (heavy.sh, `SONGCHARTER_HEAVY_MIN_FREE_GB=1`):
- **No install.sh here:** the cpu lane is 2.8 GB installed and install.sh wants 8 GB free in $HOME (`need_gb cpu`);
  `/` has 1.4 GB free, and /dev/shm's budget is 2 GB.
- **The stand-in, the nearest one:** `<shm>/m811/app` made by the install's own setup steps,
  `songcharter.runtime.step_node`, `step_autochart` and `step_models`, then `runtime_record` into runtime.json
  (`setup()` without the pipeline's models and doctor), lane cpu, the app = this branch's tree. Node 24.19.0 was
  downloaded from nodejs.org (pinned SHA-256); autochart's archive came from a mirror (`SONGCHARTER_AUTOCHART_URL`,
  `git archive` of the pinned commit of the dev machine's checkout), which the step checked file by file against
  `packaging/autochart/engine-files.sha256`; npm ci fetched onnxruntime-node; the hub's model files were links to the
  dev machine's copies, each checked by the step's size and SHA-256. Stood in: the app's Python (`runtime/env`) was a
  wrapper of the dev `.venv`'s. 479 MB; built in 30 s.
- **The run:** `ARMS=base:T=0.95 SEEDS=20260609 AC_DEVICE=cpu ALLOW_CPU=1 eval/gpu.sh thin-spike --app
  $DEV/golden/work/<the shortest reference>/decode.wav`, with `SONGCHARTER_HOME` the stand-in and `EVAL_DATA` in
  <shm>/m811. The check printed the app (0.4.0, the cpu lane), its autochart and Node, `check: ok`; detached; one
  take in 130 s on the CPU: 1914 tokens, 1291 notes, transcriber on cpu; `thin_spike: 1 takes zipped`;
  `check_no_audio: ok, 1 files and 2 archive members, no audio`; `thin spike finished (exit 0)`.
- **The zip:** 2 members, `song/base/seed_20260609/notes.chart` and `.../autochart_run/summary.json`; no `/home`,
  `/root`, `/dev/shm`, the song's id, "decode" or "user" in either. The summary keeps the settings (seed 20260609, T
  0.95, topP 0.98, knobs all null, knobsActive false), the devices (demucs, timing, transcriber: cpu), tokens, timings;
  `input`, `ffmpeg` and `jobDir` are gone.
- **Against the golden:** the golden's kept CPU take of the same decode at seed 20260609 (songcharter's `generate`,
  the unpatched driver, the dev machine's Node 22) has the same input SHA-256, and its `[SyncTrack]` (355 lines) and
  `[ExpertSingle]` (1293 lines) are identical to the spike's. So the patched driver with no knob set charts as the
  app's does, and --app ran the engine as the app runs it.
- <shm>/m811 peaked at 543 MB, and is deleted. (The checkout was at 0.4.0 then, before main's merge.)

**The full suite** on 84848a5, through `tools/heavy.sh` (`SONGCHARTER_HEAVY_MIN_FREE_GB=1`,
`PYTHONDONTWRITEBYTECODE=1`, `--basetemp=<shm>/m811/pt-suite`; it waited behind another agent's golden run):
`1372 passed, 6 skipped in 1384.49s (0:23:04)`. The skips: allin1 not configured (1), the checkout's own
tools/scan-chart not installed (2), LnkParse3 (3); none of this order's. A first run was stopped at 26 %, when I
merged main under it (the version bump would have met a mixed tree), and run again from the start. Afterwards
`songcharter/__pycache__` (`__init__`, `device`) was in the worktree, written at 18:45 by some existing test's
subprocess that does not inherit PYTHONDONTWRITEBYTECODE. It was not one of this order's tests: they and
test_eval_takes.py (73) run alone leave none. I deleted it. I also deleted an `eval/data/runs/thin_spike` that the
"non-app OUT moved" break had made inside the checkout (that break sends the spike to its default folder).

**CI:** <repo>/actions/runs/42676645006 (workflow_dispatch on 84848a5):
**success**, linux and windows. The Linux suite gave `1374 passed, 4 skipped in 735.85s`, and test_eval_thin_spike.py
is not among the skips (Node 24.19.0 is on the runner). `all 8 Linux hooks passed`; this order adds no hook, since its
checks are in the suite. The first dispatch (run 42672359562, on 8c33804) ran only the Windows job (success), and the
run ended as failure with no Linux job at all: it was created at 18:14:59, during GitHub's "Incident with Actions"
(githubstatus: Actions major_outage from 18:14:58). There was no log to read, so I dispatched again once Actions was
operational (18:44).

**Privacy:** `eval/privacy_check.py` on the four files with `EVAL_DATA=$DEV/eval`: 0 found. With
`EVAL_DATA=$DEV/eval-set20`: 15 found, README.md 6 and gpu.sh 9, the same counts as main's versions; a hash
comparison of each hit's line text and kind says they are main's same 15 lines (no value printed). The branch's diff
and commit messages hold no lyrics, audio, model names (apart from the trailers) or personal details: only made-up
names and paths.

## The owner's commands (eval/README.md, "The thin spike with the installed app")

```sh
cd /path/to/song-charting && git pull
eval/gpu.sh thin-spike --app "/path/to/the song.mp3"   # the check, then the spike, detached
eval/gpu.sh status                                     # the latest lines of eval/data/runs/thin_spike/thin_spike.log
eval/gpu.sh stop                                       # only if needed: the same thin-spike line carries on
```

16 takes, about 2.5 hours (M8-11). The zip: `eval/data/runs/thin_spike/thin_spike_results.zip`;
`(cd eval/data/runs/thin_spike && explorer.exe .)` opens the folder in Windows to send it back. Later, the
references' arm, with the winner in place of `dense5:speed=5`:

```sh
ARMS="base:T=0.95 dense5:speed=5" eval/gpu.sh thin-spike --app eval/data/refs/*/input.wav
```

## Not done, or uncertain

- **CUDA is not run here** (no GPU): the `--app` CUDA path is tested only with stand-ins (the check's provider and
  library folders, the device the made-up engine reports). The check is takes.py's static one: it finds the provider
  and the libraries but runs no CUDA op, so a provider that fails to load still shows only after the first take,
  where the spike stops.
- **The references' arm runs every built `refs/*/input.wav`**, the test song's too if it was built (about twice the
  takes of `takes --app refs`); M8-11 estimated about an hour. The orchestrator may prefer to name the six.
- **Choices beyond the brief:** several inputs in one run with labels and takes kept by input (above); the log left out
  of the zip; the patch's targets exactly once; nvidia-smi needed only for cuda; `status` showing the spike's log.
- The M8-11 and M7-08 orders still write `eval/gpu.sh thin-spike <his sooth file>` without `--app` (docs left to the
  orchestrator, as the brief says).
- Opening the folder with `explorer.exe .` from WSL is standard, but not tried here (no Windows).

## Review fixes (m8-11-app.review.md, R1-R4)

Commits 5b04550 (thin_spike.sh, gpu.sh), 3d82a2a (README), 041ff91 (tests); head **041ff91**.

- **R1:** a take is kept only when its summary's input SHA-256, seed, temperature, knobs and every run's transcriber
  device match what this run would make (a small Node check, `DIFFERS`). Otherwise it is made again, and the log says
  why: "made again (another input | another seed | another temperature | other knobs | the transcriber not on cuda)",
  or "its summary cannot be read".
- **R2:** thin_spike.sh no longer reads ALLOW_CPU. It always stops after a take whose transcriber did not run on
  AC_DEVICE (now for any device; a CPU dry run reports cpu and goes on). gpu.sh's ALLOW_CPU=1 skips only the check
  before the start. The README says so and tells the owner not to set it.
- **R3:** the references' arm is
  `eval/data/refs/{all_the_small_things,creep,drunk_drivers,kimochi_warui,lucretia,take_me_out}/input.wav`, checked
  against eval/refs.json's ids (a test reads both). No test song; the line about it is gone.
- **R4:** 13 new tests (28 in the file). Each break below fails the tests named (a scratch harness: one edit, the
  file's tests, the edit undone). All 27 breaks are caught: these 13, and the first round's 14 that still apply.

| break | failing tests |
|---|---|
| status without the spike's log | the_spike_without_app (`status` shows thin_spike.log) |
| the first input's SHA-256 for every input | a_take_is_kept_only_for_the_same_input (a two-file rerun keeps all 4) |
| the summary copy admits "/" | a_summary_keeps_no_path_however_short (ffmpeg as `bin/ffmpeg`) |
| the guard's user names without the home folder's | the_guard_stops...[home folder's name planted] |
| R1: input not compared | kept_only_when_its_summary...[inputSha256], kept_only_for_the_same_input |
| R1: seed | kept_only_when_its_summary...[seed] |
| R1: temperature | kept_only_when_its_summary...[temperature], a_cpu_take_or_a_changed_arm... |
| R1: knobs | kept_only_when_its_summary...[knobs], a_cpu_take_or_a_changed_arm... |
| R1: device | kept_only_when_its_summary...[cpu device, no runs], a_cpu_take_or_a_changed_arm... |
| R1: every take kept | 9 tests |
| no stop after a take off its device | a_take_off_its_device_stops...[both], a_cpu_take_or_a_changed_arm..., allow_cpu_skips_the_check_only... |
| R2: ALLOW_CPU bypasses the stop again | a_take_off_its_device_stops...[ALLOW_CPU=1], allow_cpu_skips_the_check_only... (via gpu.sh) |
| R3: the README misses a reference | the_readme_names_the_six_references_of_refs_json |

- **A race found in the process:** `allow_cpu_skips_the_check_only...` first asserted the front's rc 0 and "started".
  A run that stops after its first take (here about 1 s) can end before the front's first `running` poll. The front
  then prints "did not start; see gpu_run.log" with the log's tail, and exits 1. That front is the same in `takes` and
  `start`, so the behaviour predates this order. The test now asserts the check's problem line, no "check failed",
  and the finished run (exit 1); it passed 3 of 3 runs alone and in the file.
- **Checks:** `tests/test_eval_thin_spike.py`, 28 passed (`PYTHONDONTWRITEBYTECODE=1`, no `__pycache__` left). As
  asked, the full suite was not rerun. Privacy, both lists on the four files: 0, and 15 hits on main's same lines. The
  diff and commit messages are clean.
- **CI:** <repo>/actions/runs/42686730767 on 041ff91: **success**, linux and windows; the file's tests are not among the Linux suite's skips.
