# The release gate for v0.1, 2026-11-04

The release gate as `docs/PIPELINE.md` sets it, run on main at ceaf1dc (every M4 order merged), with the GPU smoke
test that ran beside it, then the gate's fixes (branch `m4-gate-fixes`, merged at a5ea646). The advisor's review of
the release candidate and the owner's approval come after this report.

## The gate

1. **The full suite:** CI on every merge (812 passed, 4 skipped at ceaf1dc; 833 passed, 4 skipped with the gate's
   fixes, locally and in CI).
2. **The golden charts, the whole reference set:** 656991d (`eval/baseline`'s commit) against ceaf1dc,
   `--rerun drums,bass,guitar` on both, `--threads 2`: old exit 0 (3293 s), new exit 0 (2620 s), diff exit 0, "no
   UNEXPECTED change; every song's results identical". Pooled Expert F1@50: guitar 0.853, bass 0.825, drums 0.962;
   beat F1 0.876. The fixes' branch ran them again at 052436e (it touches `engines/adtof.py`): identical to ceaf1dc.
3. **The full review** (`.claude/workflows/full-review.js`, run wf_be907e55-8b2, 7 agents) over 8a00e3f...ceaf1dc:
   two majors confirmed (lyrics never downloaded under the launcher's offline flag; the Done screen hiding Install
   while the chart's process exits) and a dozen minor findings, all fixed on `m4-gate-fixes` (below), then reviewed
   again: no major, three minor, fixed in round 2.
4. **The test song end to end** with the friend's defaults on the CPU (Expert, 1 take, the preview): exit 0, gate OK
   (0 errors, 4 warnings; playable, 0 chart issues); 1113 Expert guitar onsets, 24 star power phrases, 3 solos on
   allin1's solo sections; 690 s with the stems cached. Its preview, looked at: drums, bass and tempo follow the
   audio; the guitar leaves gaps in solos 3C-3D (about 5:45-6:15) where its stem plays, with one CPU take. M4-08
   compares the GPU's 4-take chart.
5. **The advisor on the release candidate:** after this merge.
6. **The owner approves the release:** after M4-08.

## The GPU smoke test

The first end-to-end chart on a GPU, through the real installer, on main at c0753d6, in an isolated HOME on the
owner's WSL2 (a copy of install.sh with the Windows side off: no .wslconfig, shortcut or WSL restart; WSL had 22 GB).
Run by a session on the owner's PC.

- **Install:** exit 0 first try, 112 s (a fast connection). Lane cu132 ("RTX 5070, driver 599.10, compute capability
  12.0"). Disk: `.local/share/songcharter` 7.4 GB, uv's cache 6.0 GB measured alone (mostly the same files), the
  whole isolated HOME 8.9 GB after two charts. doctor: OK.
- **doctor:** torch 2.15.0+cu132, CUDA 13.2, matmul ok; device cuda; guitar_device cuda; autochart's CUDA provider
  loads (CUDAExecutionProvider 15 nodes, CPU 2).
- **The cold chart** of the test song (412 s of audio), the friend's defaults: exit 0, gate OK (0 errors, 3 warnings;
  playable, 0 chart issues). Stages: decode 1.0 s, separate 10.0 s (cuda), drums 4.5 s (cuda), bass 18.1 s, sections
  42.3 s (cuda, allin1), guitar 854.0 s (cuda, 4 takes, about 177-217 s each), assemble 17.2 s, preview 12.3 s; total
  959 s.
- **Peaks:** VRAM 8,987 MiB of 12,227 (GPU 99%); the chart's process tree 11.09 GiB RSS (during the sections);
  MemAvailable down to 12.22 GiB from 22.34; no swap. M4-08 rechecks both under `memory=12GB`.
- **A warm rerun:** exit 0 in 37.4 s, the same gate; VRAM peak 1,109 MiB.
- **Surprises** (in PROGRESS's deferred list): song.ogg differs between the runs only in each Ogg page's serial number
  and checksum (notes.chart and song.ini identical); the takes' expert_job.json say executionProvider "cpu" while
  their results say "cuda" (the 99% GPU load says cuda); 4 takes cost about 3.9 times one (the default's reasoning
  assumed 3.41). The 4-take default stays (PROGRESS, M4's decisions).


## The fixes

The findings of the full review over v0.1 (workflow run wf_be907e55-8b2, diff 8a00e3f...ceaf1dc), fixed on
`m4-gate-fixes` from main at c0753d6, in the worktree `<scratchpad>/wt/gate-fixes`. Each finding was reproduced
before its fix, each new test was checked by breaking the code it covers, and no file on the charting path changed.

### Commits

| commit | what |
|---|---|
| 4a684cd | Lyrics on an installed copy: the launcher no longer sets SONGCHARTER_OFFLINE |
| 98e30ba | The Done screen: results, export and install take a job once its result is out |
| c8cbcae | install: a uv cache of songcharter's own; uninstall touches only songcharter's folders |
| 68f221f | runtime.fetch: a chunked download cut mid-chunk is retried |
| 12dcb63 | test_install: the lane guard against runtime.json as runtime.py writes it |
| e21db25 | install.sh: the licence prompt names a NOTICE.txt that exists |
| 8923bd8 | The page's header measures memory, disk and .wslconfig again |
| 730b81f | A first install with the GPU out of reach says what to do once it is back |
| 4cb90f0 | Docs for the release gate's fixes |

**Every finding reproduced against the code before the fixes.** The reviewers' three scripts at ceaf1dc (main's code;
c0753d6 changed only PROGRESS) gave their reported output (below, per finding). Then the branch's new and changed
tests, copied into a `git archive` of ceaf1dc, ran against its code: 13 failed, one or more per finding:
`test_environment_fills_in_what_the_person_has_not_set` and `test_the_installed_app_downloads_the_lyrics_weights_on_
first_use` (major 1), `test_the_done_screen_can_install_while_the_chart_is_still_exiting` (major 2),
`test_uninstall_no_keeps_the_downloads`, `test_uninstall_yes_deletes_everything_and_sizes_the_question`,
`test_a_release_installs_with_stand_ins` and `test_the_cpu_lane_needs_8_gb_free[7-False]` (uv cache),
`test_fetch_retries_a_chunked_download_cut_mid_chunk` (IncompleteRead), `test_the_prompt_names_the_licences_and_enter_
goes_on` (NOTICE), `test_the_header_measures_wsls_memory_again` (stale doctor), `test_no_gpu_and_a_gpu_out_of_reach`,
`test_a_first_install_with_the_gpu_out_of_reach_ends_with_what_to_do` and `test_a_gpu_that_answers_on_a_cpu_lane_
install_says_to_rerun_the_install` (GPU blocked). The tests-3 contract test passes there, as it should: that code
was right, and mutation R3 is what shows the gap it closes. The doc findings were checked by reading the code and the
docs (grep), each as its finding quotes it.

### The checks

- **CI, run 41850766306 on 4cb90f0: success**, both jobs (https://github.com/neb882/song-charting/actions/runs/41850766306).
  Read from `gh run view --log --job 126646123107`:
  - the CI tools' tests `86 passed in 29.99s`; the suite `820 passed, 4 skipped in 291.84s`;
  - `all 7 Linux hooks passed: 10-lanes.sh 12s 20-device.sh 5s 30-install.sh 139s 40-ui.sh 21s 50-e2e.sh 389s
    60-results.sh 52s 70-release.sh 60s`;
  - 60-results's new phase ran whole: `the launcher's variables: HF_HUB_DISABLE_SYMLINKS_WARNING=1 HF_HUB_OFFLINE=1
    MPLCONFIGDIR=... PYTHONSAFEPATH=1 PYTHONUTF8=1 SONGCHARTER_HOME=...` (no SONGCHARTER_OFFLINE), then `the lyrics:
    not added, as the first-use download was tried and the dead proxy refused it (the aligner's weights could not be
    downloaded from https://download.pytorch.org/torchaudio/models/wav2vec2_fairseq_large_lv60k_asr_ls960.pth
    (URLError: <urlopen error [Errno 111] Connection refused>))`, `no pasted word in 22 logs, records and answers`,
    `60-results: ok`;
  - 50-e2e and 30-install with the install's own uv cache: `du -sh .../runtime/uv-cache: 1.6G`, `du_all=2.8G`;
    uninstall-keep `kept: .../runtime/uv-cache (23605 files, each as it was)`, then the offline reinstall `nothing
    downloaded`; uninstall-all `gone: .../songcharter` (three lines) and `nothing new left in ~ (to depth 3)` (so no
    `~/.cache/uv`); 30-install's new `~/.cache/uv` check passed; uninstall's No prints `... [y/N] kept
    .../runtime and ...: a reinstall reuses them, and downloads only install.sh and the app (about 1 MB)`;
  - 70-release: `Licences: https://github.com/neb882/song-charting/blob/v0.1.0-ci-4cb90f0/packaging/NOTICE.txt (some
    of the models are for non-commercial use only)` on the first install, and `the installed NOTICE.txt is
    packaging/NOTICE.txt`.
- **Locally** (the session's venv, `tools/heavy.sh` of the main checkout, queued behind the release gate's golden
  run): `bash <scratchpad>/gate-fixes/local_checks.sh`, its log `local_checks.log`:
  - the full suite at 4cb90f0, `SONGCHARTER_SCAN_CHART` set: `820 passed, 4 skipped in 580.61s` (skipped: the allin1
    test with no `$SONGCHARTER_ALLIN1_PYTHON`, the torchaudio test (the dev venv has none), test_package's two
    scan-chart tests);
  - `60-results.sh` on the branch, with a stand-in torchaudio and the branch's code on PYTHONPATH (the launcher's
    PYTHONSAFEPATH=1 otherwise makes the dev venv import the main checkout): exit 0, the same `could not be
    downloaded ... Connection refused` line as CI, `60-results: ok`;
  - the same hook on a copy of the branch whose launcher sets `SONGCHARTER_OFFLINE="1"` again: exit 1 at the new
    assertion, `AssertionError: {'given': True, 'added': False, ..., 'why': "the aligner's weights are not in
    .../models/lyrics and SONGCHARTER_OFFLINE=1", ...}`. So the hook can no longer pass with the bug.
- **Targeted runs while building** (light, not under the lock): `tests/test_launch.py` 9 passed; `tests/
  test_install.py` 32 passed; `tests/test_runtime.py` 18 passed; `tests/test_device.py` 16 passed; the UI server's new
  and neighbouring tests passed; each mutation named below failed its test.
- **Golden charts:** not run. No file on the charting path changed (`git diff --name-only main...HEAD` against
  eval/golden.py's ENGINE_FILES, chart.py and assemble.py): `songcharter/device.py` changed only in `findings` (a
  doctor note) and a new `refresh`, which the pipeline never calls.


### The two majors

#### 1. Lyrics never worked on an installed copy (correct-1, tests-1, install-lyrics-offline, docs-lyrics-offline)

**Reproduced** with the reviewers' `offline_lyrics.py` at ceaf1dc: `launcher sets SONGCHARTER_OFFLINE = 1
HF_HUB_OFFLINE = 1`, `Unavailable: the aligner's weights are not in .../lyrics and SONGCHARTER_OFFLINE=1`,
`download attempted: False`.

**Fix** (`songcharter/launch.py`): `environment()` sets only `HF_HUB_OFFLINE=1` when runtime.json has
`models_complete`; `SONGCHARTER_OFFLINE` is left unset (a value the person set still wins, `setdefault`). The first
song with lyrics downloads the weights once, as documented. Fetching them at install instead stays a small change:
one more call in `runtime.step_pipeline_models` (`lyrics.weights_path(METHODS[DEFAULT_METHOD], download=no_download if
local else None)`, as ADTOF's) and the docs that say "first use" (recorded in DESIGN 4.2 and PROGRESS).

**Every reader of SONGCHARTER_OFFLINE**, and what it does now:

| reader | when it runs | file present | file missing |
|---|---|---|---|
| `runtime.offline()`: `fetch`, `Setup.need`, `step_pipeline_models` | only in `python -m songcharter.runtime setup/check`, which install.sh runs in its own shell (never the launcher's environment); `check` never downloads | unchanged: verified, no request | unchanged (the launcher never reached it) |
| `engines/adtof.weights_path` | every chart with drums | unchanged: SHA-256 checked, no request | before: FileNotFoundError, so every chart with drums failed (exit 2); now: downloaded once from the pinned URL (3.6 MB), hash-checked |
| `engines/lyrics.weights_path` | every chart with lyrics | unchanged: SHA-256 checked, no request | before: Unavailable, so lyrics were never added; now: downloaded once (1.26 GB), hash-checked; a failed download is Unavailable ("could not be downloaded"), and the chart is made without lyrics, with a warning |
| `HF_HUB_OFFLINE` (kept): the hub's htdemucs_6s and allin1 folds | every chart | unchanged: read from the hub's cache, no request | unchanged: the hub refuses, the chart fails |

torchaudio's `bundle.get_model(dl_kwargs={model_dir, file_name})` loads the file `weights_path` has just made sure of,
so it never downloads. Nothing already fetched goes back to the network: both of songcharter's own downloads run only
when the file is missing. With no network at all, a missing lyrics file fails fast (DNS) and the chart is made without
lyrics; e2e's offline phase pastes no lyrics, so it is unaffected.

**Tests** (`tests/test_launch.py`): `test_the_installed_app_downloads_the_lyrics_weights_on_first_use` writes
runtime.json with `runtime_record` itself (`models_complete: true`), runs `launch.main(["chart", ..., "--lyrics",
...])` with `_cli` replaced by the lyrics engine's `weights_path` and a stand-in download: it downloads once, a second
launch only checks the file (no download), the hub stays offline, and the person's own `SONGCHARTER_OFFLINE=1` still
refuses (`... and SONGCHARTER_OFFLINE=1`, no download). `test_environment_fills_in_what_the_person_has_not_set` now
asserts no `SONGCHARTER_OFFLINE`, and that the person's "0" and "1" stay. Broken: restoring `SONGCHARTER_OFFLINE="1"`
in `environment()` fails both tests; dropping `HF_HUB_OFFLINE` fails both.

**CI** (`packaging/ci/linux.d/60-results.sh`): the lyrics phase no longer sets the offline flags by hand. It starts
the server with the variables `launch.environment` gives a finished install (`{"home", "models_complete": true}`,
checked to include `HF_HUB_OFFLINE=1`), plus `https_proxy`/`HTTPS_PROXY` naming 127.0.0.1:9, where nothing listens,
and empty `no_proxy`. The aligner's weights are not there, so the chart must try their download, which fails at once:
CI never fetches the 1.26 GB. The hook asserts the reason starts "the aligner's weights could not be downloaded from
https://download.pytorch.org/", which only an attempted download gives; under the old launcher the reason is "...
and SONGCHARTER_OFFLINE=1" and the hook fails. The privacy checks (no pasted word anywhere) are unchanged.

#### 2. The Done screen could hide "Install into Clone Hero" and the zip (tests-2)

**Reproduced** with the reviewers' `race.py` at ceaf1dc: `results right after the result event: state=running ok=True
installable=False`, then `installable=True` 1.3 s later.

**Fix** (`songcharter/ui/server.py`): a job whose `result` event is out has its chart in place (the CLI prints it
last), so `results()` sets `installable` from the result's `ok` and the folder alone, and `_built()` (export and
install) refuses only when there is no result yet. A job with a result always ends `done` (`Jobs._finish` and
`cancel`), so the state check only ever mattered in the exit window. The `state` field in /results still reports the
process's state. `race.py` against the branch: `state=running ok=True installable=True` right after the event.

**Test** (`tests/test_ui_server.py`, `test_the_done_screen_can_install_while_the_chart_is_still_exiting`): a stand-in
chart (BUILT's mode "linger") that, after its result, exits only once the test creates `work/release`, so the window is
certain rather than timed. The test follows the SSE stream as app.js does, and at the result event: /results is
installable with `state` "running", the zip export answers 200, the install answers 200 into the Songs folder, and
the job is still running after all three; then it releases the stand-in and waits for `done`. Broken: restoring the
state check in `_built()` fails it (`no finished chart yet`); restoring it in `results()` fails it
(`installable: False`).

### The minor findings

- **install-uv-cache-not-ours: fixed** (c8cbcae). Reproduced from the finding (uninstall's Yes removed
  `~/.cache/uv`; the disk check counted it). install.sh exports `UV_CACHE_DIR=<home>/runtime/uv-cache` with its other
  uv variables before its first uv call (`uv --version`, `uv python install`, both `uv sync`s), over any
  `$UV_CACHE_DIR` the person has. The disk check counts `runtime/` (which holds it) and `~/.cache/songcharter` only.
  `launch.uninstall` drops `uv_cache()`: it counts `runtime/` and the models, and Yes removes the home (with the cache)
  and `~/.cache/songcharter`, never `~/.cache/uv`.
  - *A reinstall's "nothing downloaded"* (50-e2e): No keeps `runtime/` except `state/`, so the cache stays and the
    offline reinstall from `--from` still downloads nothing. e2e.sh's figures and uninstall-keep now look at
    `runtime/uv-cache`; uninstall-all checks it went with the home, and `nothing_left` already fails on any new
    `~/.cache/uv`. 30-install.sh's `du` line now names the new cache, and it fails if the install made `~/.cache/uv`.
  - *An install that used `~/.cache/uv`:* its next run fills the new cache once (the Python packages download again:
    about 0.45 GB on cpu, 3.2-3.9 GB on a GPU lane), and the old `~/.cache/uv` is left, no longer counted or deleted.
    v0.1 is unreleased, so only dev and CI installs have one (in PROGRESS's deferred list).
  - Tests: every stand-in uv call gets the install's own cache over the person's `$UV_CACHE_DIR`; with 20 GB
    (sparse) in the person's uv caches, 7 GB free is still refused; uninstall's Yes leaves another project's
    `~/.cache/uv`. Broken three ways (no export; the person's cache counted; uninstall deleting `~/.cache/uv`): each
    fails a test.
- **install-fetch-incompleteread: fixed** (68f221f). Reproduced by the new test before the fix (`http.client.
  IncompleteRead: IncompleteRead(951424 bytes read, 97152 more expected)` out of `fetch`). `fetch` now retries any
  `http.client.HTTPException` like the other network errors, resuming the `.part`. Test: a chunked response cut in its
  chunk after 2 MB; the first 1 MiB block reached the `.part`, and the retry resumes at `bytes=1048576-`.
- **install-stale-doctor: fixed, by the header not depending on it** (8923bd8). Refreshing doctor.json after step 9
  would not help: WSL has its new memory only after the restart that ends the install. `device.refresh(r)` takes a
  report doctor wrote (one with `ram`), measures the memory, the free disk and, with interop, `.wslconfig` again, and
  makes its problems, notes and `ok` again with `findings`; the GPU, torch and the components stay. `App.doctor` shows
  it, cached per version of doctor.json (mtime and size), and falls back to the file as it is if the refresh raises.
  Test: a doctor.json from `findings` at 7.8 GB with no .wslconfig; the header before the restart (the allin1 note and
  the "restart WSL" one) and after it (neither, the other notes as they were). Broken twice (no refresh; a stale
  .wslconfig): it fails. Not changed: the install's own closing summary, printed before the restart, and the GPU in
  the header (both in PROGRESS's deferred list); diagnostics already carries a fresh doctor-now.json.
- **install-notice-before-app / docs-licence-notice-absent: fixed** (e21db25). Reproduced (the prompt named
  `app/0.0.0-test/NOTICE.txt` with `app/` empty). install.sh gets `NOTICE_URL="@NOTICE_URL@"`, which build.sh fills
  with the guide's own link (`https://github.com/neb882/song-charting/blob/v<version>/packaging/NOTICE.txt`); the
  prompt names it until `app/<version>/NOTICE.txt` exists, and that file on a rerun. Tests: the first prompt (the URL),
  Enter installing, then a rerun's prompt (the app's copy, which exists); build.sh's filled value is the guide's link.
  70-release.sh checks the first install's prompt (No and Enter) names the release's URL. Broken (always the app's
  path): the test fails. The tag exists only once M4-08 pushes it (as for the guide's link; PROGRESS).
- **docs-reinstall-downloads: fixed** (c8cbcae, 4cb90f0). Uninstall's No now says "kept <runtime> and <models>: a
  reinstall reuses them, and downloads only install.sh and the app (about 1 MB)"; 70-release.sh greps the new line;
  the launcher's docstring, the guide (section 7), M4-08 (A16, its pass list, M4-05's baseline line) and M4-03 (a
  bracketed note) say the same.
- **docs-kill-timeout: fixed** (4cb90f0). DESIGN 2.0's proc.py row: SIGKILL after 5 s (`KILL_TIMEOUT_S`).
- **docs-allin1-rule: fixed** (4cb90f0). Checked: `plan(None, ram).target_gb` gives memory=10GB (10.7e9 bytes, left
  out) at 14 GiB and 11GB (11.8e9, kept) at 15 GiB. wslsetup's docstring and M4-03 now say "a PC whose RAM rounds to
  14 GB or less". Whether a nominal 16 GB PC that reports under 15.5 GiB should get 12GB is left open (PROGRESS).
- **docs-lyrics-offline: fixed with major 1.** The guide ("The first song with lyrics downloads 1.26 GB, once"),
  packaging/NOTICE.txt ("downloaded once, 1.26 GB, on the first song with lyrics") and DESIGN 4.2's table ("download
  on first --lyrics use") are now true as written. README now says the installed app's too, and that
  `SONGCHARTER_OFFLINE=1` forbids it; DESIGN 4.2 describes the launcher's variables; PROGRESS's M4-10 item says the
  download now works on an installed copy and how to move it to the install.
- **tests-3: fixed** (12dcb63). Reproduced with `lane_contract.sh` (compact layout: `chose cpu`). The new test writes
  runtime.json with `runtime_record`, rewrites it with `set_allin1`, then checks `previous_lane` and the refusal for
  cu126 and cu132. Mutation R3 (`json.dumps` without `indent`) now fails it.
- **install-first-install-gpu-blocked: fixed, both notes** (730b81f). Reproduced (`lane=cpu`, no warning). A first
  install (or a cpu one) with nvidia-smi failing sets `lane_warning`: "the GPU is out of reach, not missing, so this
  is the CPU build: restart Windows (or update the NVIDIA driver), then paste the install line again: it switches to
  the GPU build (about 3 GB)". It is said at step 2 and again right after "is installed" (every lane warning now is).
  doctor adds a note when the device reason is the cpu lane's and a GPU answers: "<name> answers now, but this install
  has the CPU build: paste the install line again, which picks the lane again (the GPU build needs NVIDIA driver 528
  or newer, the guitar on the GPU 580)". The guide's section 3 says what to do. Each of the three pieces broken in
  turn fails a test. The page's header does not show the doctor note (it does not run nvidia-smi again).

### Deferred, and why (in PROGRESS's deferred list)

- The lyrics' first-use download prints no progress and a cut one starts over (`engines/lyrics._download` has no
  Range resume): M4-10's downloader, beyond this brief.
- An existing install's `~/.cache/uv` is left as it is (it cannot be told from another project's).
- The install's closing summary is printed before WSL restarts; the header's GPU is the install's.
- The memory rule's rounding of a nominal 16 GB PC under 15.5 GiB: a behaviour choice, the owner's.

### Uncertain, or not checked here

- CI runs the 1.26 GB download's start only (the dead proxy); the real download through the installed launcher on WSL
  is M4-08's (its new section, "Added at the release gate's fixes", lists it with the other hardware-only checks).
- The local run of 60-results.sh used a stand-in torchaudio (the dev venv has none), so the aligner itself never ran;
  CI's .venv has the real torchaudio.
- e2e.sh, 30-install.sh and 70-release.sh changes run only in CI (Docker); see the run above.

### The scan before the push

`git diff main...HEAD` and the branch's commit messages, searched for assistant model names, emails, home and
profile paths and audio files: only the required trailers, and made-up file names in a test (`s.mp3`, `l.txt`). No
lyrics: the only words are the hooks' and tests' made-up ones. No audio, weights or reference charts are committed.

### Review fixes, round 2

The review of 4cb90f0 (`gate-fixes.review.md`: no major, three minors, two notes) and the owner's decision on the
memory rule, fixed on the same branch from 4cb90f0.

| commit | what |
|---|---|
| 0695f8b | One downloader: the engines' weights go through runtime.download_part (F-3) |
| fc07c79 | Tests for the disk check's credit and the header's per-version cache (F-1, F-2) |
| 196f95a | doctor: no "paste the install line again" for an install asked for the cpu lane (the review's note) |
| 912b440 | The WSL memory rule rounds Windows' RAM up to a whole GB (the owner's decision) |
| 052436e | Docs: one downloader, the memory rule, the uv note (the review's second note) |

**Each change against the old code.** The round's new tests, copied into a `git archive` of 4cb90f0 and run against
its code: 13 failed. F-3's two fail with the review's symptoms (`http.client.IncompleteRead: IncompleteRead(951424
bytes read, 97152 more expected)` for a chunked cut; `Unavailable: the aligner's weights from http://127.0.0.1:.../
w.pth have SHA-256 9ca4..., not the pinned e1eb...` for a short body). Also failing: the asked-lane note test, the
report's `install` test, every case of the rounding test and the 15.4 GiB PC's. F-1's and F-2's tests pass there, as
they should (those were test gaps over correct code): the reviewer's mutations fail them now (below).

- **F-3 (fixed in code).** `runtime.fetch`'s loop is now `runtime.download_part(url, part, size)`: resumed with
  Range, retried on any network end (a body short of Content-Length or of the size, or cut mid-chunk, is a cut
  connection, never the file), a line every 50 MB. fetch keeps its size and SHA-256 check and rename on top of it.
  `engines/lyrics._download` and `engines/adtof._download` are now calls to it (lines on stderr; the lyrics pass the
  pinned size). `lyrics.weights_path` maps the shared downloader's StepFailed to Unavailable ("could not be downloaded
  from <url>", which 60-results.sh asserts), and keeps the `.part`, which the next song with lyrics resumes (a wrong
  SHA-256 still deletes it). ADTOF's weights_path lets StepFailed (a ToolError) end the chart with exit 2, as its
  OSError did. `RETRY_PAUSE_S` (2 s) lets tests skip the pauses.
  - Test (`tests/test_runtime.py`, `test_the_engines_weights_come_through_the_shared_downloader[chunked|short]`): both
    engines' default downloaders against the local server, cut once chunked and once short of its Content-Length:
    each retried and resumed (`bytes=1048576-` and `bytes=2000000-`), "resuming at" on stderr; a `.part` a failed run
    left is resumed by the next call (`bytes=1000000-`); a 404 is a failed download (Unavailable, "HTTP 404").
  - engines/adtof.py is in ENGINE_FILES (drums), so the golden charts ran again (below).
- **F-1 (test).** `test_what_runtime_holds_counts_as_here_already`: 4 GB (sparse) in runtime/uv-cache, df at 6 GB:
  the cpu lane's 8 GB passes with "4.0 GB of it is here already". The review's I4 (dropping `"$runtime"` from the
  loop) fails it.
- **F-2 (test).** `test_a_running_page_reads_a_rewritten_doctor_json_and_survives_a_failing_refresh`, through the real
  server's /api/status: the refresh made once per version; a rewritten doctor.json (a later mtime) is shown, and
  `auto_device` follows it; a refresh that raises leaves /api/status at 200 with the file's notes. R4 (the cache keyed
  only on the first call) and R5 (no try/except: `500`, ZeroDivisionError) each fail it.
- **The `--lane cpu` note.** doctor's report gets `install` ({"lane", "lane_reason"} from runtime.json under
  $SONGCHARTER_HOME, which the launcher sets; None elsewhere), and the "answers now ... paste the install line
  again" note is left out when lane_reason starts with `device.ASKED_LANE` ("asked for with --lane", install.sh's
  choose_lane wording, which test_install now ties to the constant). Tests: the note absent for "asked for with
  --lane cpu", present for an nvidia-smi failure; `_install` reads runtime.json, and None without one. Dropping the
  condition fails the test.
- **The memory rule (the owner).** `wslsetup.pc_gb` = `math.ceil(ram / GiB)`; `target_gb` = pc_gb - 4; the refusal
  ("at least 12 GB of RAM (this one has N GB)"), "a N GB PC gives no more" and "Windows has N GB of RAM" all use
  pc_gb. So 15.4, 15.9 and 16 GiB give memory=12GB; 14.0 GiB gives 10 (allin1 left out), 14.1 gives 11 (kept); 11.1
  GiB gives 8 and 11.0 is refused (a target of 7 GB is under the 8 * 10^9 limit). Tests: those seven cases through
  `target_gb`, `pc_gb` and `plan`, and a 15.4 GiB PC's whole apply (memory=12GB, "Windows has 16 GB of RAM") and a
  refused 10.6 GiB PC ("this one has 11 GB"). Docs: wslsetup's docstring, DESIGN 4.7 (the rule as built), M4-03
  (bracketed), M4-08 (record the reported RAM and the memory written on the friend's PC), PROGRESS (a decision in M4's
  list; the deferred item about rounding removed). The guide states no rounding.
- **The old uv cache's cost (PROGRESS).** Checked with uv 0.13.5 (the release tarball, SHA-256 f68d291c... as
  build.sh pins it) on a probe project shaped like songcharter's (setuptools build, installed `--no-editable`, one
  dependency): after a sync with cache A, a re-sync of the complete environment with an empty cache, offline too,
  printed only `Checked 2 packages` (nothing built or downloaded). A new release (the app at a new path, as
  app/<version> is) rebuilds the project's wheel and needs setuptools: offline it fails ("setuptools was not found in
  the cache"), online it downloaded setuptools (4.4 MB of cache with the index pages); the installed dependency was
  not fetched again. PROGRESS now says so.

#### Round 2's checks

- **CI, run 41862406694 on 052436e: success**, both jobs (https://github.com/neb882/song-charting/actions/runs/41862406694;
  both waited about 20 minutes in GitHub's queue). From the linux job's log: the suite `833 passed, 4 skipped in
  354.97s`; `all 7 Linux hooks passed: 10-lanes.sh 16s 20-device.sh 6s 30-install.sh 156s 40-ui.sh 21s 50-e2e.sh 424s
  60-results.sh 74s 70-release.sh 60s`; 60-results's lyrics phase through the shared downloader (`could not be
  downloaded from https://download.pytorch.org/...`, after its retries: 22 s more than before), `nothing downloaded`
  for the offline reinstall, `nothing new left in ~`, and the first install's licence prompt naming the release's URL.
- **Locally, one heavy job** (`tools/heavy.sh bash <scratchpad>/gate-fixes/round2_checks.sh`, after the test song's
  chart): the full suite at 052436e `833 passed, 4 skipped in 542.90s`; then the **golden charts**, because
  engines/adtof.py is in ENGINE_FILES: `python -m eval.golden run --out <scratchpad>/gate-fixes/golden-branch --threads
  2 --rerun drums,bass,guitar` from a detached checkout of 052436e (2579 s, every song's gate OK), and `diff
  <scratchpad>/gate/golden-new <scratchpad>/gate-fixes/golden-branch --expect none` against the release gate's ceaf1dc
  run (same reruns): `golden diff: no UNEXPECTED change`; report.md: engines that ran drums, bass and guitar on 7
  songs on both sides, "Every song's results (hashes, counts, scores) identical: yes".
- **Mutations**, each alone, then restored: the review's I4 (no `"$runtime"` in the disk loop), R4 (the header's cache
  keyed on the first call only) and R5 (no try/except around the refresh) each fail the new tests; so does dropping
  the asked-lane condition. The F-3 and rounding tests fail on 4cb90f0's code itself (above).
- **Scan** of `git diff 4cb90f0..HEAD` and the round's commit messages: only the required trailers; no lyrics, audio,
  model names or personal details.
- The covering test files while building: test_runtime 20 passed; test_lyrics, test_engines_adtof and test_launch 50
  passed, 1 skipped; test_install 33 passed; test_wslsetup 21 passed; the new device and UI server tests passed.

