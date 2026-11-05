# M5-08 install polish: the builder's report

Branch `m5-08-install-polish`, worktree `<wt>/m5-08`, from main at 8ac38dc, with origin/main (85e9363, docs only)
merged in. Order: `docs/work-orders/M5-08-install-polish.md`. No golden run: the order says why (runtime.py,
launch.py and device.py are outside `ENGINE_FILES`; no engine file changed).

## Commits

| commit | what |
|---|---|
| 0fd9ea6 | runtime.py, launch.py and their tests: download_part's done line, npm's log level and flags, the hub's quiet logger, its bars off and our own lines for its downloads; the launcher's two hub variables |
| 82c8436 | device.py: torchaudio among doctor's components; tests |
| 6cfbb28 | install.sh: the closing summary's rule with step 9's restart flag; tests (and a `sleep` stand-in in the harness) |
| 9c1906c | 30-install.sh: the noise check, tried on itself first |
| 9b30313 | DESIGN 4.3: what the WSL install prints, the summary rule |
| 384a532 | merge of origin/main (PROGRESS.json, handoff.md only) |

## The source of each noise line, and what silenced it

All from CI's artifacts of main's last green run before this order (run 42091064166, `30-install/install-2.log`),
the same lines M4-08 part A saw on the owner's PC.

1. **`Warning: You are sending unauthenticated requests to the HF Hub. Please set a HF_TOKEN ...`** (line 238, in step
   8, "the pipeline's models").
   - Source [read, huggingface_hub 2.4.0, the version both `uv.lock` and `packaging/allin1/uv.lock` pin, the same as
     the dev venv's]: the text is not in the client. The hub's server sends it in an `X-HF-Warning` response header;
     `huggingface_hub/utils/_http.py`, `_warn_on_warning_headers`, called from `hf_raise_for_status`, logs it with
     `logger.warning(message)` once per topic, on the `huggingface_hub.utils._http` logger, whose handler is the one
     `utils/logging.py` puts on the library's root logger `huggingface_hub` at import (level WARNING, or
     `HF_HUB_VERBOSITY`).
   - The order's note that the dev venv "does not print it" did not hold here: a plain `hf_hub_download` of
     htdemucs_6s.yaml from this machine, in a terminal (`script`), printed it [measured].
   - Silenced: `runtime.hub_quiet()` sets the `huggingface_hub` logger to ERROR around the install's two hub loaders
     (separation and sections) and restores it after, also after an error; the launcher's environment sets
     `HF_HUB_VERBOSITY=error` where the person has not (the hub's documented variable; it is read at import). No
     token, no login. Errors are exceptions, not log lines, so they still raise and still end as StepFailed (tested
     with a LocalEntryNotFoundError in `check` and an OSError in a download). What ERROR also hides: the hub's
     "Error while downloading ...: Trying to resume download..." warning before an internal retry; the final failure
     still raises.
   - Measured with the real hub in a terminal: the same download through `said_downloads` inside `hub_quiet`
     printed only `fetch htdemucs_6s, file 1 of 2: 0 MB` and `... done, 0 MB`; a second call (cached) printed
     nothing.
2. **`npm warn deprecated fluent-ffmpeg@2.1.3: ...`** (line 202, scan-chart's npm ci): npm's own warn-level log line.
3. **`npm warn gitignore-fallback No .npmignore file found, using .gitignore ...`** (lines 200-201, twice, scan-chart's
   npm ci).
   - Source [read]: npm-packlist (bundled in npm 11; `lib/index.js`, `filterEntries`), `log.warn('gitignore-fallback',
     ...)` when it packs a folder that has a .gitignore and no .npmignore. npm packs git dependencies that way, and
     scan-chart's lock has two (dsp.js and stream-audio-fingerprint, both `git+...` in tools/scan-chart's
     package-lock.json): two lines [reasoned from the count and the source; npm's debug log does not name the
     package].
   - Silenced, both (2) and (3): `_npm_ci` runs npm with `npm_config_loglevel=error` and `--no-audit --no-fund` for
     every caller (the flags were the two callers' before; now `NPM_CI`, so no caller can leave them out). Measured
     here with scan-chart's real lock and Node 24's npm 11.19.1: at loglevel warn the three lines print; at error,
     only "added 19 packages in 2s". npm's debug log in the cache still has both gitignore-fallback lines, and a failing
     npm ci at loglevel error still prints its errors and "A complete log of this run can be found in: ..." with the log
     kept [measured].
4. **allin1's download bars as wide as the terminal** (owner's PC only: CI's log is not a terminal, so the hub hid them
   there). Source: the hub's tqdm bars in step 8's `hf_hub_download` calls (allin1's eight folds; htdemucs_6s).
   Silenced: `HF_HUB_DISABLE_PROGRESS_BARS=1` in `os.environ` before the hub is imported in `step_pipeline_models`
   (the hub reads it at import; nothing imports it earlier in `runtime setup`), and in the launcher's environment.
   In its place, `said_downloads` says `fetch <name>: <N> MB` before each file the hub will download (the size from
   the hub's dry run, `dry_run=True`, which makes no request for a file the cache has at the pinned commit) and
   `fetch <name>: done, <N> MB` after: "htdemucs_6s, file 1 of 2", "htdemucs_6s, file 2 of 2", "allin1 fold 1 of 8"
   to "allin1 fold 8 of 8". A file in the cache says nothing, so the reinstall's "no ^fetch line" check holds.
   - In a terminal, a plain download of one fold left two blank lines (a bar drawn and cleared); ours left none
     [measured; the fold is about 1 MB, so no bar stayed long enough to draw blocks].
5. **No "done" line after ADTOF's weights** (line 239: `fetch adtof_frame_rnn_pytorch_weights.pth: 3 MB`, then
   nothing). Source: `download_part` said no last line; only `fetch` did, after its checks. Now `download_part` ends
   every download with `fetch <name>: done, <N> MB` (a resumed one and a .part already whole too), and `fetch` no
   longer says its own, so it is said once. ADTOF's and the lyrics aligner's weights (both through download_part, on
   stderr: the job's log for the lyrics) end with one.

## The closing summary (install.sh)

When step 9 wrote `.wslconfig` (`$state/restart-wsl`), the heredoc gets `restart`. It computes `device.findings` twice
on doctor.json, once as it is and once with WSL's MemTotal and `memory_matches_config` unknown; what only the first
gives is what doctor said of WSL's memory, and is left out of the problems and notes (doctor.json's own texts are
kept for the rest). The WSL line's "no .wslconfig" becomes ".wslconfig: just written". It then prints the verdict of
what remains and "WSL's memory is measured again after the restart.", and exits 0 or 1 by the remaining problems;
install.sh takes that as its exit status only with the flag (a summary that crashes leaves setup's). With no flag,
the summary and the exit status are as before.

- **Decision beyond the order's list:** the order names the problem and two memory notes; the set difference also
  drops the third memory note, "WSL has X GB of memory, but .wslconfig asks for Y GB: restart WSL", when the flag is
  set. It names the .wslconfig step 9 has just replaced and asks for the restart that is about to happen. With no flag
  it stays (the test's "kept .wslconfig" case prints it).
- Seen with the stand-in harness and the real summary (MemTotal 7618 MB, flag set): no problem line, "doctor: OK",
  the closing line, exit 0, then "WSL restarts now ..." and `wsl.exe --shutdown`.

## Checks

- **[dev] The suite**, from the worktree's own environment (`uv sync --frozen --extra cpu --extra app --extra dev`),
  through `tools/heavy.sh`, on 9b30313's code (the merge after it adds only PROGRESS.json and handoff.md):
  `SONGCHARTER_SCAN_CHART=$PWD/tools/scan-chart/scan.cjs tools/heavy.sh uv run python -m pytest -q -p
  no:cacheprovider --basetemp=/dev/shm/pt-m5-08` → `957 passed, 4 skipped in 647.39s (0:10:47)`.
- **[dev] The tests break when their code does**: 22 breaks, each applied, the touched file's tests run with `-x`,
  then the file restored with git. All 22 caught:

  | break | caught by |
  |---|---|
  | B1 no done line in download_part | test_fetch_resumes_a_part_file (and the new done-line test) |
  | B2 fetch says done a second time | test_download_part_ends_with_a_done_line |
  | B3 npm without loglevel=error | test_npm_ci_keeps_its_cache_inside_the_install |
  | B4 npm without --no-audit/--no-fund | test_npm_ci_runs_once_per_lock |
  | B5 no hub_quiet | test_the_hubs_downloads_have_our_lines_and_no_bars_or_warnings |
  | B6 bars not turned off | the same |
  | B7 lines for files in the cache | the same |
  | B8 no done line for the hub's | the same |
  | B9 hub_quiet does not restore the level | the same |
  | B10 folds numbered from 0 | the same |
  | B11 launcher without HF_HUB_VERBOSITY | test_the_hub_is_quiet_in_the_launchers_environment |
  | B12 launcher without the bars off | the same |
  | B13 no torchaudio row | test_the_report_runs_here |
  | B14 torchaudio's version from another distribution | test_doctor_lists_torchaudio[True] |
  | B15 install.sh never reads the flag | test_a_restart_leaves_the_memory_doctor_measured_before_it_out_of_the_summary |
  | B16 exit status not the summary's | the same |
  | B17 a restart drops every problem | test_a_restart_keeps_the_disk_problem_in_the_summary |
  | B18 no closing line | test_a_restart_leaves_... |
  | B19 the memory notes kept | the same |
  | B20 "no .wslconfig" kept | the same |
  | B21 left out with no flag too | the same (its kept-.wslconfig half) |
  | B22 the summary always exits 0 | test_a_restart_keeps_the_disk_problem_in_the_summary |

- **The noise check fails on a log from before this order**: the hook's `noisy`/`quiet` functions, run here on main's
  last green run's `30-install/install-2.log` (run 42091064166), in the C and the C.UTF-8 locale:
  ```
  200:npm warn gitignore-fallback No .npmignore file found, using .gitignore for file exclusion. Consider creating a .npmignore file to explicitly control published files.
  201:npm warn gitignore-fallback No .npmignore file found, using .gitignore for file exclusion. Consider creating a .npmignore file to explicitly control published files.
  202:npm warn deprecated fluent-ffmpeg@2.1.3: Package no longer supported. Contact Support at https://www.npmjs.com/support for more info.
  238:Warning: You are sending unauthenticated requests to the HF Hub. Please set a HF_TOKEN to enable higher rate limits and faster downloads.
  30-install: the install's log has noise, above (M5-08)
  ```
  (exit 1); its `install-3.log` passes. Its probe (lines it must flag, lines it must not) fails for each of five
  breaks of the pattern: `\r` removed, `█` removed, `npm warn` removed, `[Ww]arning:` as `warning:`, and the bar
  characters as a bracket (which in the C locale flags "cu126 → cu132").
- **[CI] Run 42117751492** (https://github.com/neb882/song-charting/actions/runs/42117751492), on 9c1906c:
  success, both jobs. The hook ran: `==== hook linux.d/30-install.sh`, `30-install: no noise in
  .../30-install/install-2.log`, `30-install: no noise in .../30-install/install-3.log`, `30-install: ok`, `==== hook
  linux.d/30-install.sh ok in 142 s`. Its `install-2.log`, step 8, now reads: npm's "added 19 packages", then
  `fetch htdemucs_6s, file 1 of 2: 0 MB` ... `fetch htdemucs_6s, file 2 of 2: done, 54 MB`, `fetch allin1 fold 1 of
  8: 1 MB` ... `fetch allin1 fold 8 of 8: done, 1 MB`, `fetch adtof_frame_rnn_pytorch_weights.pth: 3 MB`, `fetch
  adtof_frame_rnn_pytorch_weights.pth: done, 3 MB`, `doctor: OK`; the summary has `torchaudio: ok, 2.11.1+cpu`, and
  doctor-full.json `{"ok": true, "version": "2.11.1+cpu"}`. The reinstall printed no `fetch` line (the hook's own
  check). Its `install-1.log` (the killed first run, not checked) has 2 noise lines: curl's meter for uv's tarball.
- **[CI] Run 42120713385 on the head, 384a532** (https://github.com/neb882/song-charting/actions/runs/42120713385):
  success, linux and windows. The hook ran: `30-install: no noise in .../30-install/install-2.log`, `30-install: no
  noise in .../30-install/install-3.log`, `30-install: ok`, `==== hook linux.d/30-install.sh ok in 150 s`.
- **[dev] The real hub, once, in a terminal** (`script`): a plain `hf_hub_download` of htdemucs_6s.yaml printed the
  "unauthenticated requests" warning; the same through `said_downloads` in `hub_quiet` printed only our two lines,
  and a second, cached call nothing. A plain download of one allin1 fold left two blank lines (a bar drawn and
  cleared); ours none.
- **[dev] npm**, scan-chart's real lock with Node 24's npm 11.19.1, at `npm_config_loglevel=warn` and `=error`
  (described above).
- **Scan for the hard rules**: `git diff origin/main...HEAD` and the branch's commit messages grepped for model and
  company names, home paths, the repository's owner and email-like strings: only the attribution trailers, the CI
  container's existing `/home/friend` lines, and the test fixture's made-up `C:\Users\someone\.wslconfig`. No lyrics,
  no audio.

## Not done, or uncertain

- **The lyrics aligner's line names its file**, not "the lyrics aligner": `engines/lyrics.py` calls
  `download_part` without a `name`, and that file is not this order's (M5-04 is editing it). The one-word change
  there is `name="the lyrics aligner"` in `_download`; ADTOF's line names its file too (`engines/adtof.py`, in the
  golden's ENGINE_FILES). Both now end with the done line.
- **Not quiet yet, and not this order's files:** the first install's curl meter for uv's tarball (install.sh's
  `download`, step 6: carriage returns in CI's `install-1.log`, so the noise check leaves that log out) and uv's own
  bars on a terminal (step 7). Both outside "install.sh (the closing summary)".
- The hub-download lines are measured with a stand-in `hf_hub_download` (the loaders and labels are the real ones)
  and once with the real hub for one small file; the install's full first run with the real hub is CI's
  30-install.sh.
- The bars on the owner's PC were not reproduced here (the files download too fast to draw); their switch is the
  hub's documented one, and the test checks it is set when the hub runs.

## Review fixes (8666ee3, then a merge of origin/main, da565e3)

The review (`<scratchpad>/briefs/m5-08.review.report.md`): no major, three minor, all fixed.

- **m1, the noise check's self-test.** The probe now also runs `quiet` itself, in a subshell, on each noisy probe
  line (it must fail) and on the quiet lines (it must pass). It also has uv's lowercase `warning: \`VIRTUAL_ENV=/x\`
  does not match the project environment path` line. Checked here on the hook's own block: unbroken, the self-test
  passes and `quiet` fails main's noisy `install-2.log`. Each break fails the self-test:
  - `quiet` without its `exit 1`: "the noise check passes a log with: npm warn deprecated ...";
  - `[Ww]arning:` narrowed to `Warning:`: "misses: warning: `VIRTUAL_ENV=/x` ...";
  - `\r` removed, and `npm warn` removed, as before.
- **m2, a summary that crashes.** The heredoc's body is in `try`, and `except Exception` prints the traceback and
  exits 3. So with the flag, only 0 and 1 are taken as doctor's verdict (`[ "$summary" -le 1 ]`), and a crash leaves
  setup's status.
  - New test `test_a_summary_that_crashes_leaves_setups_exit_status`: the reviewer's repro (doctor.json with no
    "python", wslsetup changed, setup 0). It expects exit 0, `KeyError: 'python'` on stderr, no closing line, and
    the restart still run.
  - Breaks: no `except` (exit 1 as before): caught. `-le 3`: caught.
- **m3, the old .wslconfig note.** New test `test_a_restart_also_leaves_out_the_old_wslconfigs_memory`: the flag is
  set, and .wslconfig asks for 10 GB, not in force at 7.4 GB. It expects no "asks for" line, "doctor: OK", the
  closing line, and the WSL line ending "; .wslconfig: just written".
  - **The reviewer's break `"wsl": w` does not fail it, and cannot.** In the "memory unknown" view, MemTotal is
    already None, and the note's text carries WSL's total. So that view's note reads "WSL has ? GB of memory, but
    .wslconfig asks for 10.0 GB ...", not "WSL has 7.4 GB ...", and the set difference drops the real note either
    way (checked with `device.findings`).
  - The `memory_matches_config: None` line stays so the rule does not depend on that wording. The new test pins the
    behaviour: a break that keeps the note (`... or "asks for" in n` in the notes filter) fails it, and only it.
- Checks after the fixes: `tests/test_install.py` 39 passed. The suite (tools/heavy.sh, the same command):
  `959 passed, 4 skipped in 600.68s (0:10:00)`. CI run 42124865539 on da565e3
  (https://github.com/neb882/song-charting/actions/runs/42124865539): success, linux and windows. The hook ran,
  self-test included: `30-install: no noise in .../install-2.log`, `... install-3.log`, `30-install: ok`,
  `==== hook linux.d/30-install.sh ok in 148 s`.

## Review (sc-reviewer, 2026-11-05)

# M5-08 review (correctness lens), head 384a532

No major findings. Three minor ones, each reproduced in a copy at /dev/shm/review_m508 (deleted afterwards).

## m1 (minor): the noise check's self-test does not cover `quiet`, or the lowercase `warning:` alternative
packaging/ci/linux.d/30-install.sh:29-43. The probe tests `noisy` only. Two breaks pass the probe and would ship a
check that does not do its job:
- b1: `quiet` with its `exit 1` removed (line 32). On a log containing `npm warn deprecated x` it prints
  `probe passed`, then `30-install: no noise in npm.log`, and exits 0. The check can never fail again.
- b2: `[Ww]arning:` narrowed to `Warning:` (line 25). On a log containing uv's lowercase
  `warning: \`VIRTUAL_ENV=/x\` does not match ...` it prints `probe passed`, then `no noise`, and exits 0. The
  unbroken check flags that line (exit 1). The probe has no lowercase `warning:` line.
Fix: add a lowercase `warning:` probe line, and run `quiet` itself on a noisy probe in a subshell, expecting it to fail.

## m2 (minor): under the restart flag, a summary that crashes sets exit 1, not setup's status
packaging/linux/install.sh:377 and 403. If the Python summary dies with a traceback it exits 1, `summary=1`, and
`[ "$summary" -le 1 ]` takes it. That contradicts the `# else setup's` comment and the report ("a summary that
crashes leaves setup's"). Before the order, a crash was ignored (`|| true`). Repro: Install(wsl=True), real summary
of `{"ok":true,"problems":[],"notes":[],"components":null}`, runtime mode ok:
`wslsetup=changed: exit 1; ["KeyError: 'python'"]` against `wslsetup=ok: exit 0`. The result is an install that says
"doctor found problems" because of a bug. Fix: have the heredoc catch its own failure and exit 3 (or wrap it), so only
0 and 1 count as the verdict.

## m3 (minor): the builder's added decision (dropping ".wslconfig asks for ...: restart WSL") is untested
packaging/linux/install.sh:386, tests/test_install.py:611. In the restart test `.wslconfig` is absent, so
`memory_matches_config` is already None. Break: `"wsl": w and {**w, "memory_matches_config": None}}` changed to
`"wsl": w}` (the note kept under the flag). `pytest tests/test_install.py -k "restart or plain_linux"` gives
`5 passed`. The report's B19 covers only the 11 GB note. Fix: add a flagged case where .wslconfig asks for 10 GB that
is not in force (a raise to 12 GB).

## Checked and sound
- The "done" line, said once per download (fetch no longer repeats it). The hub's lines are said only when
  `will_download` (the real 2.4.0 `dry_run` returns `will_download=False` for a cached pointer or blob). In check
  mode, a missing file raises LocalEntryNotFoundError, which subclasses EntryNotFoundError and OSError, so it becomes
  StepFailed.
- `hub_quiet` is restored in `finally`. Breaks R1 (no finally), R2 (WARNING), R4 (lines for cached files), R5 (bars
  on), R6 (done line), L1 (verbosity override) and the builder's 22 breaks are all caught. R3 (done size from the dry
  run) passes but ships nothing wrong.
- The bars switch is read at the hub's import. Nothing imports the hub before `step_pipeline_models` (the last step).
- The launcher's keys apply only where unset. The torchaudio row is never a problem.
- Under the flag the summary drops only memory findings. A flag implies a target of at least 8 GB (wslsetup refuses
  below it), and step 9 itself says "allin1 is left out", so dropping the 11 GB note hides nothing.
- Skipping install-1.log loses only steps 1-7 of the first run (curl's meter, noted as not covered). Steps 8-10 run
  only in install-2.
- DESIGN 4.3 matches the code.

## The builder's decisions
1. Dropping the third memory note: right, but untested (m3).
2. Leaving the lyrics' name to M5-04: fine.
3. curl and uv bars out of scope, recorded in DESIGN: fine.
4. Hub lines measured with a stand-in and one real file: fine. The real `dry_run` semantics match the stand-in.
