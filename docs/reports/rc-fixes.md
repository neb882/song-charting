# The release candidate's fixes (branch m4-rc-fixes), 2026-11-04

The fixes from the advisor's review and the skeptics' verdicts (`rc-advisor.md`), built on `m4-rc-fixes`, reviewed
(no major; six minor findings or test gaps), fixed again, and merged. The branch was rebased onto the rewritten
history before its review: the hashes below are the rebased ones.

## rc-fixes: the fixes from the advisor's review of the release candidate

Branch `m4-rc-fixes` from main at d756141, worktree `<scratchpad>/wt/rc-fixes`. Pushed; not merged. Read first: the
brief, the advisor's report (advisor-rc.md), the three skeptics' reports (rc1, rc6, rc7), CLAUDE.md, PIPELINE.md,
PROGRESS.json, then every file each item names.

### Commits

| Commit | What |
|---|---|
| f3baf9e | A guitar take that fails on CUDA says what to try; the takes' reason gives the smoke test's 3.9x |
| a94d4a8 | The page shows doctor's problems, with the disk measured on every status; a full disk answers an upload with 507 |
| 4e68113 | doctor and the server say how to restart WSL in the guide's words |
| d4f67a1 | The guide: how long a chart takes, keeping the PC awake, closing the window before playing; the swap file on C: |
| ce0f1a8 | M4-08: the pre-release first, then part A from the release page; the release candidate review's checks |
| 1882aec | PROGRESS: the release candidate review's decisions and deferred items; rc-fixes in flight |
| 941d790 | M4-08 and M4-07: the release-first order is the owner's decision |

Each ends with the brief's two trailer lines and nothing else of the kind.

Mid-task, the orchestrator relayed that the owner approved item 4's order (2026-11-04): 941d790 writes it as decided ("the owner, 2026-11-04") in M4-08's Input paragraph, M4-07's pre-release section and PROGRESS's decision; publishing stays the owner's step. The orchestrator also said main's history will be rewritten and the branch rebased at the merge: I neither pulled nor rebased main.

### Part A: the docs and M4-08

#### 1. The guide, section 5 (docs/guide/windows-wsl.md)

- **How long:** "with the default options, a 4-minute song takes about 10 to 15 minutes", most of it the guitar's 4
  takes, "the page shows which take it is on ('take 2 of 4')"; "type 1 in the 'Guitar takes' box (in the options,
  under Guitar)": about 4 to 6 minutes. "These times are estimates." The box's name and place are the page's
  (index.html: the label "Guitar takes" in the "Guitar" fieldset of "2. Options").
- "Windows has about 4 GB left for a few minutes" is now "until the chart is done".
- **Keep the PC awake while a song charts** (no menu path given: Windows' power settings' wording varies by build).
- **Before you play, close the songcharter window (and any Ubuntu window)**: "WSL keeps the memory it took while one
  is open; once they are closed, WSL stops and Windows gets that memory back. That can take a minute." I added "and
  any Ubuntu window" because an open Ubuntu window keeps WSL running too [reasoned]; M4-08's A20 checks it.
- Read as the friend would: each bullet is one plain paragraph; "takes" is explained where it first appears, "swap
  file" in section 1, WSL at the top. The guide grew from 948 to 1,144 words of source (M4-07 asked "under two
  pages"; it is now a little over two at a normal font size, by M4-07's 868 words = 1.8 pages).

#### 2. The takes' reason text (songcharter/pipeline.py)

`guitar_takes`' reason now reads "...for 3.9x the guitar stage's time (the GPU smoke test on an RTX 5070: 854 s for
the 6:52 test song, about 219 s for 1 take)", and its docstring gives both figures (3.41x over the takes experiment's
seven songs, 3.9x / +10.6 min in the smoke test (854 - 219 s; +10.7 at first, corrected at review)) and that the default stayed 4 at the release gate. The default is
unchanged. pipeline.py is not in eval/golden.py's ENGINE_FILES (guitar: only engines/autochart.py). To show no chart
moves, I charted the tests' synthetic song with the stand-in engines on CUDA with the default 4 takes from a copy of
main (d756141) and from the branch (a scratch script, deleted after): notes.chart
`73302e0f...bab68` and song.ini `41bb61f9...a77c40` on both; report.json holds neither figure; only pipeline.json's
`takes.why` differs. DESIGN 2.7's cost bullet gains the smoke test's 3.9x.

#### 3. Small disagreements

- `wsl --shutdown in PowerShell` (device.py's note, server.py's `unreachable`) now uses the guide's words: "restart
  WSL. In Terminal (right-click Start), type wsl --shutdown, then open Ubuntu again" (the server's: "or restart WSL:
  in Terminal (right-click Start), type wsl --shutdown, then open Ubuntu again."). Tests updated:
  tests/test_device.py (the note), tests/test_ui_server.py (the header test, and the unreachable test now pins the
  phrase instead of only "wsl --shutdown").
- PROGRESS's torchaudio item: the NOTICE half is gone (NOTICE.txt lines 43 and 128-134 have both); doctor still does
  not list torchaudio, so that half stays.
- README: the cache is `~/.cache/songcharter`, inside WSL's Ubuntu in v0.1, whose disk grows on C:; `%LOCALAPPDATA%`
  is a native run's.
- **The swap file:** install.sh asks 15 GB free on a GPU lane (the downloads unpacked plus 5 GB of work folders; the
  smoke test measured 7.4 GB installed). The guide's 20 GB leaves about 5 GB over that, which does not hold an 8 GB
  swap file on C:, so section 1 now reads "About 20 GB free on C:, and room for up to 8 GB more: when WSL runs short of
  memory during a chart, it keeps some of it in a file on C: (its swap file), which can grow to 8 GB." No deferred
  item for it, since the guide covers it; M4-08's A1 records C:'s free space before the install.

#### 4. M4-08 (docs/work-orders/M4-08-hardware.md) and M4-07

- **The order:** the "Input" paragraph and a new section "The release, before part A (the owner)": R1 tag `v0.1.0` at
  main's commit and check it out; R2 `build.sh 0.1.0 dist`; R3 publish the pre-release (the owner's yes); R4 if part A
  fails, delete the release and the tag, fix, publish again. One version string, `0.1.0`; `0.1.0-rc1` and `--from`
  are gone. Step 5 installs with the line copied from the release page. **A17** added. M4-07's pre-release section
  now says "before its part A", with the checkout and build in the recipe, and its Done-means item 3 likewise.
- **A18** (step 8): two cold charts with the defaults (`rm -rf ~/.cache/songcharter/work ~/.cache/songcharter/ac`
  before each: the work folder and autochart's scratch, whose engine cache would otherwise answer), `cmp` of the
  two notes.chart; the result goes to DESIGN (section 1, Determinism; I added a line there now saying it is not yet
  shown on CUDA and that A18 settles it) and PROGRESS, either way. The pass list has the [decision] for both outcomes.
- **VRAM:** `nvidia-smi` before each chart and the peak during it (steps 7-9), once with a browser playing video and
  a chat app open (**A19**); the provoked GPU failure is **A23** (under step 10), with what the Done screen should
  now say.
- **Memory after a chart (A20)** and **sleep mid-chart (A21)**, under step 11.
- **What CUDA buys the guitar (A22):** Device CPU and Guitar takes 1, placed after A7 and A18 on purpose: run before
  step 8, its CPU take would replace the CUDA take 1 in the same seed folder, and A7 would then time 4 takes, not 3.
- **The takes rule:** judged on the friend's 4070 (part B's times), not the 5070 (10.6 min there); a change would be
  for v0.1.1. A7's note says it measures 3 takes. Part B's brief to the friend names the box and asks for the zip
  after the last chart.
- **Criteria added:** the zip through `packaging/ci/check_no_audio.py` (its real path) and a yes/no check for pasted
  text (**A24**); the reinstall starts from the shortcut and charts (A16 extended).
- **A choice the brief left open:** the pasted-text check looks for three pasted words in a row, not one word, since
  common words appear in any log. The snippet is inline in M4-08 (it prints only `yes` or `no`); I ran it on made-up
  text: a clean zip gave `no`, one holding three of the made-up words in a row gave `yes`.
- **The install's last lines:** part A copies them (user names and paths left out); part B reads the zip's
  doctor.json, which the closing summary prints. The zip does not hold the terminal's lines themselves.
- **Optional when time runs short:** steps 15 and 19 marked so; step 3 kept as it was.
- **The results document:** Done means says it quotes nothing personal. I also changed part B's "Also record for
  PROGRESS (... driver, ... Windows build ...)" to the requirement form CLAUDE.md now asks (no exact driver, Windows
  or WSL versions), and fixed step 2's "until step 18 restores yours" to step 20, which is the step that restores it.
- **Untested claims:** A3 asks whether the window really closes at the install's restart; A12 asks whether Scan Songs
  is at Settings > General.
- Not changed: M4-00-plan.md line 196 still says "Create the pre-release when part A passes" (the plan, kept as
  written; M4-07 and M4-08 now say otherwise).

#### 5. PROGRESS

Deferred: the upgrade test before v0.1.1; the CPU retry (the skeptic's option b); the work cache's 24-hour exemption;
the install summary's later fix and what it must not hide (appended to the release gate's existing item); item 9's
note (appended to the existing lyrics-download item). Decisions: the release order, and v0.1's handling of a failed
CUDA take. M4's status and `next`; `in_flight` is this order, then the merge.

### Part B: code

#### 6. A guitar take that fails on CUDA (pipeline.py, app.css)

The guitar stage wraps both engines.guitar calls in `run_takes`; `on_take` also records the take that runs (index,
count). A ToolError on cuda is raised again as `gpu_failed(index, count, error)`: "The guitar's GPU run failed in
take k of n; the takes that finished are kept. Close programs that use the GPU (games, Clone Hero, video) and chart
it again, or set Guitar takes to 1 (it uses the first take if that one finished). If it fails again, set Device to
CPU." then a blank line and autochart's message. Two small choices: "the takes that finished are kept" is left out
for take 1 (none finished), and "or set Guitar takes to 1" is left out when n is 1. Exit 2 as before (ToolError);
no fallback recorded; on the CPU the message is unchanged. Each clause was checked in the test against the real
autochart.generate (below). `#done-text { white-space: pre-wrap; overflow-wrap: anywhere; }`. No golden run:
pipeline.py is not in ENGINE_FILES and no chart changes (item 2's check).

Test `tests/test_pipeline.py::test_a_guitar_take_that_fails_on_cuda_says_what_to_do`: the real Engines.guitar and
autochart.generate with a stand-in driver (exit 1 with an onnxruntime allocation line for one seed), through the CLI
with `--events`: take 2 of 4 fails (message, exit 2, `fallbacks` []); then `--takes 1` runs no take; then the
defaults run only 101, 202, 303; on a second work folder take 1 of 4 fails, `--device cpu` runs the take on the CPU,
`--takes 1` on CUDA fails as "take 1 of 1" without the takes-1 advice; on the CPU (`auto` → cpu) the message is
autochart's alone and the only fallback is the "device" one.

#### 7. The page shows doctor's problems (device.py, server.py, app.js, index.html, app.css)

- `device.refresh_disk(r)`: the free disk measured again (home and, when it was measured, C:), then problems and
  `ok` from `findings` (notes untouched); `_disk_now` is shared with `refresh`.
- `App.doctor` = the cached `_doctor()` (unchanged: doctor.json's refresh once per version, or the quick report once)
  plus `refresh_disk` on every call; a failure there shows the cached report. `status()` returns `problems`.
- The page: `<ul id="problems" class="error" hidden>` between the guitar line and Details; renderStatus fills it and
  hides it when empty; "Chart it" stays enabled. I also made "Chart another song" fetch /api/status again
  (`refreshStatus`), since the page read it only at load: without that, a page left open through an evening would
  never show the disk filling. A few lines; say if it is beyond the brief.
- Upload ENOSPC: the rest of the body is read (`_skip`), then 507 "C: (or WSL's disk) is full: free some space on C:,
  then drop the song again" (`DISK_FULL`), also when upload.json's write meets it. What the page shows: the drop
  screen's error line, red, with that text (app.js's non-200 path shows `data.error`); checked in the node test.
- Tests (tests/test_ui_server.py): the same served App, disk patched 50 GB, then 3 GB (the two problems, `ok` false),
  then 40 GB (cleared), with .wslconfig read once; app.js in node with a stand-in DOM (problems shown and hidden,
  "Chart it" enabled, the 507 text on the drop screen, the refresh after "Chart another song", the HTML order, the
  pre-wrap rules); the 507 for the file (body of more than 3 chunks, nothing left behind, no "internal error" logged,
  the next upload 200) and for its record. The node test is skipped without node (CI's Linux job has it).
- Not done, as the brief says: pruning library/, exports/, replaced/.

#### 8. The install's last summary

No code. PROGRESS's release-gate item gets the skeptic's later fix and what it must not hide; M4-08 records the
lines (item 4).

#### 9. The lyrics download's line on the page (optional)

Not done: it needs a weights check in the pipeline (lyrics.weights_path's file, and whether lyrics.json is cached),
and the stand-in engines would then depend on the dev machine's model folder. Left in PROGRESS's deferred item, with
a note.

### Checks

- **Mutations** (a scratch script, deleted after: each break run against its test, then restored): 18 of 18 caught.
  pipeline: no advice on CUDA; advice on the CPU too; the take not tracked; the takes-1 clause always; the kept clause
  always; the second call not wrapped. device: refresh_disk a no-op. server: no `problems` in status; doctor not
  measured again; ENOSPC a bug again; the rest of the body not read; the record's ENOSPC a bug. page: problems not
  rendered; always hidden; no refresh after a chart; #done-text not pre-wrap. wording: doctor's and the server's
  PowerShell wording back.
- **Targeted:** test_pipeline's new test and the takes tests; test_ui_server.py and test_device.py whole (67 passed).
- **Full suite:** `tools/heavy.sh python -m pytest -q -p no:cacheprovider --basetemp=/dev/shm/pt-rcfix-full` (SONGCHARTER_SCAN_CHART set), at 1882aec's code (941d790 changed docs only): `837 passed, 4 skipped in 577.00s (0:09:37)`, exit 0.
- **CI:** https://github.com/neb882/song-charting/actions/runs/41880930981 on 941d790 (the branch's last commit): success. linux 15m27s: the suite `837 passed, 4 skipped in 293.74s` (the skips are allin1's and LnkParse3's, so the new node test ran), every hook ok (10-lanes, 20-device, 30-install, 40-ui, 50-e2e, 60-results, 70-release); windows 55s ok. The run on 1882aec (41879970104) was cancelled by the next push (the workflow's concurrency group).
- **Golden charts:** not run. Nothing in ENGINE_FILES changed and no chart's notes depend on the changed lines;
  shown instead by the stand-in chart from main and the branch (item 2: identical notes.chart and song.ini).
- **Scan:** `git diff main...HEAD` before main was rewritten, and again as `git diff d756141..HEAD` (the branch's own base: main...HEAD now spans the rewritten history) and the commit messages, for model names, emails, home and profile paths, user
  names and lyrics: none (the hits were "CLAUDE.md" as a file name, `<scratchpad>` placeholders, and the tests'
  made-up `C:\Users\x`).

### Uncertain

- Whether closing the window gives the memory back within a minute, and whether a sleeping PC pauses or breaks a
  chart: reasoned only; M4-08's A20 and A21 check them, and the guide's wording does not depend on the answer.
- The guide is now a little over M4-07's two pages.
- The CPU retry, the 24-hour exemption and the upgrade test are deferred, not done.
- Scratch deleted (the mutation and comparison scripts, the copy of main, the /dev/shm test folders); `df -h /`: 7.3 GB free.

### Review fixes

The orchestrator rebased the 7 commits onto the rewritten main (d756141 → d756141; the last, 941d790, is now
941d790). The review (rc-fixes.review.md) had no majors and six minor findings or test gaps; all are fixed on 941d790:

| Commit | What |
|---|---|
| 7afc9e9 | F1, F5: a take killed by a signal says it was stopped for memory; only an engine failure gets the GPU advice |
| e2122b1 | F6, F4: an upload whose record meets ENOSPC deletes its song file; other OSErrors stay 500s |
| 22a87fa | the note: doctor's WSL-memory problem in the guide's words |
| 3d1b7e5 | F2, F3 and the notes: A24, A22, A20 and A21 in M4-08; 10.7 → 10.6 in M4-08 and DESIGN; DESIGN's ui row |

- **F1:** `take_failed` reads autochart's exit code from its ToolError's first line (`AUTOCHART_EXIT`), so
  engines/autochart.py (in ENGINE_FILES) is untouched and no golden run is needed. Exit > 0: `gpu_failed`, as before.
  Exit < 0: `stopped`: "The guitar's run was stopped in take k of n (signal 9, SIGKILL), which usually means WSL
  ran out of memory; the takes that finished are kept. Close other programs (browsers, games, Clone Hero) and
  chart it again, or set Guitar takes to 1 (...)." The memory clause is for SIGKILL only. A timeout and an exit 0
  with no take keep autochart's message. Still on CUDA only, as the brief had it: on the CPU a killed take keeps
  autochart's message.
- **F2:** the snippet takes the title and file name as more arguments and drops their 3-word runs. Made-up text
  (the lyric line holds a three-word title): title and file name in the zip, no names passed → `yes`; with them →
  `no`; another pasted line in a log → `yes`.
- **F3:** the smaller change, a doc change only: A22 is compared with A7 / 3 (both transcription only, autochart's
  cache warm). The take's summary.json shows `demucs` null when that cache answered; if not, compare with A6.
- **F4, F6:** the tests check EACCES on the file and on the record gives a 500 logged as a bug (on a small upload,
  which the server has read whole before it answers), and that the record's 507 leaves no song file. The file is
  kept when an earlier upload of the same file already had a record.
- **Notes:** device.py:533 in the guide's words; A20 and A21 each say what to record and what follows when they
  fail; the Windows 10 wording is left as it was.

Checks:
- breaks, each against its test: 8 of 8 caught (a signal given the GPU advice; a timeout given it; the SIGKILL
  clause on another signal; the catch widened to Exception; every OSError a 507 on the file, and on the record;
  the song file kept; doctor's bare "(wsl --shutdown)" back);
- test_device.py and test_ui_server.py: 67 passed; the pipeline test passed;
- full suite through tools/heavy.sh at 3d1b7e5: `837 passed, 4 skipped in 560.33s (0:09:20)`, exit 0 (the new cases are inside existing tests, so the count is unchanged);
- CI on 3d1b7e5, https://github.com/neb882/song-charting/actions/runs/41889646778: success. linux: the suite `837 passed, 4 skipped`, every hook ok (70-release.sh's "install.sh: FAILED" line is its tampered-file case); windows ok;
- scan of `e330b5f..HEAD` (the branch's base on the rewritten main) and all its commit messages: nothing (the only hit was `@pytest.mark` in a test).

## Review: m4-rc-fixes (941d790 on e330b5f)

Lens: correctness of the code changes, whether the docs tell the truth, and the tests tested. Light runs only, in a
`git archive` copy at /dev/shm/review_rc (deleted after). The baseline was green: test_ui_server.py and test_device.py
had 67 passed, and test_pipeline.py had 34 passed.

### Findings

#### F1 minor: every ToolError from autochart on cuda is called a GPU failure (pipeline.py:842-845)
`run_takes` wraps any ToolError from `engines.guitar` when gdev is cuda. That covers three other cases: node killed by
a signal (exit -9: the kernel's OOM killer under WSL's 12 GB cap, which M4-08 once saw kill autochart at 12.8 GB),
the timeout, and exit 0 with no matching summary. Each one gets "Close programs that use the GPU ... If it fails
again, set Device to CPU". For host RAM that advice is wrong, and the tail ("exit -9:" with nothing after it) does not
tell the friend anything. Probe: a stand-in driver returns -9 with empty stderr for seed 101, on cuda:
```
PROBE code 2
PROBE message "The guitar's GPU run failed in take 2 of 4; the takes that finished are kept. Close programs that use the GPU (games, Clone Hero, video) and chart it again, or set Guitar takes to 1 (...). If it fails again, set Device to CPU.\n\nautochart seed 101 failed (exit -9):\n"
```
The exit code (2) is right, and the engine's tail is kept. Smallest fix: autochart raises its ToolError with the
returncode on it. gpu_failed is used only for returncode > 0 (and the timeout, if you want). A negative returncode
says "autochart was stopped (signal 9: usually out of memory)".

#### F2 minor (doc): A24's pasted-text check answers "yes" for the song's own name (M4-08 step 17)
The diagnostics zip names the song: the logs give the upload name, and pipeline.json gives the work-folder name and
the tags. A title of three or more words is often a line of the song itself. The check then prints `yes` and the pass
item fails, and the owner cannot tell a leak from the title, by design. Probe, all text made up: a lyrics.txt line
holding "clock on borrowed time", and a zip holding only `{"meta": {"title": "Borrowed Time", "name": "Clock On
Borrowed Time"}}` plus a log line naming "Clock On Borrowed Time.mp3". The snippet, extracted from M4-08 verbatim,
prints `yes`. Fix: print the member names that match (never the words), and read a match only in a log line that
names the upload as not a leak. Or pass the file name and title as a third argument and drop their runs from
`pasted`.

#### F3 minor (doc): A22 compares unlike takes (M4-08 step 8)
A22 runs Device CPU with 1 take after A18, so autochart's scratch (`ac/`) already holds the song's separation and
beat map. Those are keyed by the audio's SHA-256 (autochart.py:9, cache.scratch_folder), so they are very likely
reused. The CPU take is then the transcription alone. A6's CUDA take was the first in a fresh distro: separation,
beat map and transcription. "Beside A6's CUDA take" therefore flatters the CPU. Fix: compare against a CUDA
transcription-only take (A7 / 3, or the take events' times for takes 2-4). Or `rm -rf ~/.cache/songcharter/ac`
before A22 and keep the comparison with A6.

#### F4 test gap: the ENOSPC filters can be deleted unnoticed (server.py:695-697, 712-714)
Mutation M5 removes `if e.errno != errno.ENOSPC: raise` on the file path, so every OSError becomes 507. Mutation M6
does the same on the record path. With either one, test_ui_server.py and test_device.py still had 67 passed. A
permission error or a read-only filesystem (ext4 remounted ro after errors) would then tell the friend "free some
space", and nothing would be logged as a bug. Fix: one more case in `test_an_upload_that_fills_the_disk_answers_507`,
with OSError(EACCES) on write, expecting 500 and "internal error" in the log.

#### F5 test gap: `except ToolError` can widen to `except Exception` unnoticed (pipeline.py:842)
Mutation M1: test_pipeline.py still had 34 passed. If that shipped, a bug in the guitar stage on cuda (a KeyError, a
FileNotFoundError) would exit 2 with GPU advice and no traceback on stderr. That breaks CLAUDE.md's "3 a bug". The
bug tests use drums, or the CPU. Fix: one chart_it in the new test whose driver raises KeyError on cuda, expecting
exit 3 and kind "bug".

#### F6 minor: the record's 507 leaves the song file behind (server.py:707-715)
When upload.json's write meets ENOSPC, `dest` (the whole song) stays in uploads/<id>/ with no record. Nothing can use
it, and on a full disk it holds space until the 7-day prune at the next server start. Probe (a print added to the
test):
`PROBE left after the record's 507: ['d94d4ee730ed0bfe/big.wav'] [7056088]`. The test checks only `upload.json*`.
Fix: on that path, `dest.unlink(missing_ok=True)` when no upload.json was there before, and assert `*/*.wav` is gone.

### Test the tests
I wrote 10 breaks of my own (the builder's 18 not repeated). 5 were caught: M2 (take index and count taken from the
call), M3 ("kept" said for take 1), M4 (decrement after the write: `_skip` reads a chunk too many), M7 (refresh_disk
keeps the old `ok`) and M9 (`_skip` a no-op). 5 were missed: M1 (F5), M5 and M6 (F4), and two of low value. M8: the
disk is not measured again for the quick report (no doctor.json); on the friend's install doctor.json exists. M10:
the `except` around refresh_disk narrowed; only a malformed doctor.json reaches it.

### Checked and true
- gpu_failed's clauses. A rerun runs only the takes left: take.json is written per take, and the new test shows it.
  `--takes 1` on cuda reuses take 1 through `_done(..., "cuda")`. Device CPU makes the take again. "Kept" is left out
  for take 1, and the takes-1 advice for n = 1.
- What stays the same: the probe, the moved-transcriber path, `_distinct_takes`, takes.py splicing and `fallbacks`.
  On failure the `takes` record is still not written, as before. pipeline.json's error is longer, and its traceback
  now chains. Cancel is SIGTERM to the group, with no handler in the CLI, so the process dies as before. Ctrl+C is
  KeyboardInterrupt, which the wrapper does not catch.
- refresh_disk: two statvfs calls, plus findings over the shared cached report, which it reads and never mutates.
  So it is safe under the threading server. It is called at page load, on "Chart another song" and at job start.
  Problems do not depend on allin1_python, so recomputing them without it is right.
- The page. The problems list sits between the guitar line and Details, and is hidden when empty. "Chart it" is left
  alone. refreshStatus touches only the header and state.status, whose defaults are the same.
- The 507. The rest of the body is read, because `left` is now decremented before the write. The part file is
  unlinked. The page shows the drop-error text.
- R1-R4 are runnable. The guide's line uses `releases/download/v0.1.0/`, which serves a pre-release; `latest` would
  not. build.sh archives HEAD. `gh release delete --cleanup-tag` then `git tag -d` is correct. install.sh reuses the
  app only by its SHA-256, so a republished 0.1.0 installs. A1-A24 are all present, step 2's "step 20" is right, and
  A18's paths match cache.work_folder and scratch_folder.
- Privacy: no names, paths, exact versions or installed-software lists. The fixture is the made-up
  `C:\Users\x\.wslconfig`, and the GPU model is allowed. No lyrics. No model names outside the trailers.

### Notes
- "In Terminal (right-click Start)" is Windows 11's menu, but the guide still supports Windows 10 ("Windows
  PowerShell" there). This is moot for the friend, whose PC has Smart App Control and so runs Windows 11.
  device.py:533-534's problem still says a bare "(wsl --shutdown)", and the page now shows it.
- A20 and A21 have no rule for the case where they fail. With systemd on, WSL may not stop when its windows close
  (not verified). If so, the guide's "WSL stops" is false and needs `wsl --shutdown`.
- A full C: under WSL's growing disk may show up inside WSL as EIO rather than ENOSPC (not verified), which would be
  a 500. The header's problem still shows.
- 854 - 219 = 635 s, which is 10.6 min, while the text says +10.7 min. That is a rounding gap of 0.1 min.
