# M5-08: install polish: no noise in the install's output, a "done" line after every download, the closing summary

**Branch:** `m5-08-install-polish`, from `main` after wave 3 (wave 4, beside M5-07; merged first, since both may set
the launcher's environment). **Agent:** `sc-builder`, then `sc-reviewer`. May push its branch to run CI. **Files:** `songcharter/runtime.py`, `songcharter/launch.py`
(environment only), `songcharter/device.py` (one component row), `packaging/linux/install.sh` (the closing summary),
`packaging/ci/linux.d/30-install.sh` (the noise check), their tests, `docs/DESIGN.md` 4.3. Not `engines/adtof.py`
(in the golden's `ENGINE_FILES`: the "done" line goes into the downloader it calls). **Time budget:** 1 day.

## Why

Seen in M4-08 part A on the owner's PC (`docs/work-orders/M4-08-results.md`, "Seen on the way"): an HF Hub
"unauthenticated requests" warning and npm's deprecation and .npmignore warnings during the install; allin1's
download bars as wide as the terminal; no "done" line after the ADTOF weights' download. Deferred since the release
gate: the install's closing summary can print "problem: WSL has 7.4 GB of memory, under 8 GB" and "doctor: 1 problem"
five seconds before the restart that cures it (the advisor's finding 7 and its skeptic, `docs/reports/rc-advisor.md`;
PROGRESS `deferred`), and `doctor` does not list torchaudio among the components (M4-10's deferred item).

## What to build

1. **The hub's warning:** find where the "unauthenticated requests" line comes from in the `huggingface_hub` version
   the lanes lock (`uv.lock`; the dev venv's 2.4.0 does not print it, so read the locked version's code), and silence
   it the way the hub documents (an environment variable, or the `huggingface_hub` logger set to ERROR around our
   calls in `runtime.step_pipeline_models`, the separation's, the sections' and the lyrics' first-use downloads, and
   in the launcher's environment). Never by a token or a login.
2. **The bars:** `HF_HUB_DISABLE_PROGRESS_BARS=1` wherever the hub downloads (the install step and the launcher's
   environment), and our own lines instead: `fetch <what>: <N> MB` before each hub download whose size is known and
   `fetch <what>: done, <N> MB` after (a name a person reads: "allin1 fold 3 of 8", "htdemucs_6s", "the lyrics
   aligner"). The lyrics stage's first-use download gets the same lines in the job's log.
3. **The "done" line:** `runtime.download_part` says `fetch <name>: done, <N> MB` when it finishes (the asset `fetch`
   already does), so ADTOF's weights and the lyrics' weights end with one; its progress lines every 50 MB keep their
   shape.
4. **npm's warnings:** `_npm_ci` runs with `npm_config_loglevel=error`, `--no-audit` and `--no-fund` (no network
   calls for them either); npm's own log file stays in the cache for a failure, as now. Find what prints the
   ".npmignore" lines in the install's log (CI's artifacts of the last green run hold one) and silence that too.
5. **The closing summary** (`install.sh`, the heredoc that prints doctor.json, and `code`): when step 9 wrote
   `.wslconfig` (its flag), leave out the "WSL has ... under 8 GB" problem and the two memory notes ("under 11 GB:
   allin1 is left out", "no .wslconfig"), end the summary with "WSL's memory is measured again after the restart", and
   take the exit code from the problems that remain. Unchanged: disk and component problems; the memory problem when
   no restart follows (`.wslconfig` kept, a No, a rerun after an interrupted restart); plain Linux and CI (no flag).
6. **`doctor`:** torchaudio among the components (its version from the main environment; the lyrics aligner needs
   it), as NOTICE.txt already lists it.
7. **The noise check in CI** (`30-install.sh`): the install's log holds no line matching `npm warn`, `WARN`,
   `warning:` from the hub, `unauthenticated`, a carriage return, or a progress-bar character (`█`, `▏`-`▉`); show
   that the check fails on a log from before this order (keep one from CI's artifacts in the report).

## Tests

- `download_part`'s done line (the stand-in opener of tests/test_runtime.py); the hub lines around a stand-in
  `hf_hub_download`; `_npm_ci`'s arguments and environment.
- `install.sh` with tests/test_install.py's `Install(wsl=True)` and the skeptic's two cases: MemTotal just under 8e9
  with the flag set → no memory problem or note printed, the closing line, exit 0; the same with no flag (a kept
  `.wslconfig`) → the problem printed and exit 1; a disk problem with the flag → printed, exit 1; plain Linux
  unchanged.
- `doctor`'s torchaudio row present and absent.
- Each test fails when its code is broken (say which break).

## Evaluation

- No charting path: no golden run (`runtime.py`, `launch.py` and `device.py` are outside `ENGINE_FILES`).
- [CI] 30-install.sh's noise check passes on the branch; its log is quiet.

## Done means

- [dev] The suite; the new tests fail when their code is broken.
- [CI] Green, the noise check included.
- [docs] DESIGN 4.3 (what the install prints, the summary rule); PROGRESS's two deferred items closed by the
  orchestrator at the merge.

## Limits

- No change to what is downloaded, to the lanes or to the locks. A hub switch that would also hide a real error is
  not acceptable: errors must still reach `StepFailed`.

## Report

`<scratchpad>/briefs/m5-08.report.md`: the commits, the source of each noise line and what silenced it, each
check's last lines, the CI run's URL, anything uncertain.
