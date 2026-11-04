# M4-03 (install): builder's report

Branch `m4-03-install` from `main` 656991d, worktree
`/tmp/claude-0/-home-user/5307d417-c453-5e74-8f13-b43b2df06ab1/scratchpad/wt/m4-03`. Pushed to `origin/m4-03-install`
(the order allows it). It merges with today's `main` (3402bfd) with no conflict (`git merge-tree`); this branch adds 13
files and changes none that exist (`git diff --stat main...HEAD`).

## 1. Commits

| commit | what |
|---|---|
| 3737c4d | `songcharter/runtime.py`, `launch.py`, `wslsetup.py`, `winshortcut.py` and their four test files |
| f6df825 | `packaging/linux/install.sh`, `packaging/release/build.sh`, `tests/test_install.py` |
| f5e0311 | Fix, found by the dev install: the install's Python imported `songcharter/` from the current folder (see 4.1). Also, `check` now reports an app file that differs instead of copying it. |
| 2756b3c | `packaging/ci/linux.d/30-install.sh`, `packaging/ci/windows.d/30-shortcut.ps1` |
| e6233a8 | `fetch` makes 3 retries (4 tries, the spec's wording). huggingface_hub's `EntryNotFoundError` (base: `Exception`) is now a step failure, not a bug. |
| 866e2dd | Test: 12 GB or more is kept whatever Windows' RAM is (the mutation pass found this gap) |

Not touched: `pipeline.py`, `cli.py`, `engines/*`, `wsl.py`, `device.py`, `ui/`, `docs/`, `pyproject.toml`, the locks,
`ci.yml`, `packaging/autochart/*`, every other hook. No M4-04 file.

## 2. What it does (by file)

- **`install.sh`** (template; `build.sh` fills `@VERSION@`, `@APP_SHA256@`, `@RELEASE_URL@`, `@UV_URL@`,
  `@UV_SHA256@`). It runs ten steps, each with a header:
  1. **WSL or not:** `$WSL_DISTRO_NAME` or `microsoft` in osrelease, and interop through `cmd.exe`.
  2. **The lane** (below).
  3. **Disk:** `df -B1` of `$HOME`, and on WSL of `/mnt/c`, against 6 or 15 GB less what the install already holds.
  4. **WSL's memory:** MemTotal, and whether `.wslconfig` exists (via `cmd.exe /u` and `wslpath`).
  5. **The estimate:** download size and time at 25 and 100 Mbit/s, then `Continue? [Y/n]`.
  6. **uv, Python and the app:** uv's tarball checked by its pinned SHA-256 and extracted with `tar`; the app tarball
     checked and extracted to `app/<v>` with a `.release-sha256` stamp (other versions removed);
     `uv python install --no-bin 3.13.17`.
  7. **Two `uv sync --frozen`**, each with exactly one lane (refused with no lane).
  8. **`python -P -m songcharter.runtime setup`**. Exit 2 or 3 stops the install. Exit 1 counts as doctor's problems only
     when `doctor.json` is newer than the start of the step.
  9. **On WSL, `python -P -m songcharter.wslsetup apply`.**
  10. **The launcher**, `install.done`, doctor's summary from `doctor.json`, "lane changed: a → b", and the restart
      lines with `cmd.exe /c wsl.exe --shutdown` when `.wslconfig` changed.

  Every failure ends with `songcharter: <step> failed: <one line>. Run the same command again to continue.`, then exit
  2. That covers the ERR trap, INT and TERM.
- **The lane, at every run** (`choose_lane`):
  - **No GPU:** no nvidia-smi on PATH or at `/usr/lib/wsl/lib`, or one that lists nothing.
  - **A failing nvidia-smi** (non-zero exit or a timeout) is device.py's SMI_FAILED, not a missing GPU. It refuses to
    move a cu126 or cu132 `runtime.json` to cpu, and says why ("the GPU is out of reach, not missing", restart or
    update, or `--lane cpu`). A fresh install takes cpu, with the reason.
  - **The thresholds:**
    - cu132: driver ≥ 580 and capability ≥ 7.5 (an unreadable capability counts as ≥ 7.5);
    - cpu: driver < 528, or capability ≥ 12.0 with a driver < 580;
    - cu126 otherwise, with the order's warning when the driver is under 580. When the driver is 580 or newer but the
      capability is under 7.5, the warning says that instead.
- **`songcharter.runtime`:** `fetch`; the engine-list check and the zip extraction; the steps (node, scan-chart,
  autochart with npm ci and the provider, autochart's models, the pipeline's models); then `runtime.json` (last,
  atomic) and doctor (`launch.environment()`, then `device.report(full=True)` into `doctor.json`); plus `check` and
  `set_allin1`. npm runs are skipped by a stamp: the lock's SHA-256 and the Node version.
- **`songcharter.launch`:**
  - finds the home: `$SONGCHARTER_HOME`, else the install its Python belongs to, else `~/.local/share/songcharter`;
  - `environment()`, as specified, plus `PYTHONSAFEPATH=1`;
  - `main`: `uninstall` first; a missing `runtime.json` gives exit 2; with no arguments, `["doctor", "--quick"]`;
    otherwise `cli.main`, with argparse's SystemExit caught; `--from-shortcut` waits for Enter on any non-zero exit;
  - `uninstall` (below).
- **`songcharter.wslsetup`:** `plan()` (the memory rule as a pure function), `windows_side()`, `apply()` and the shortcut.
  It writes only through `wsl.update_wslconfig`, as UTF-8, through a temporary file, after backing the file up as
  `.wslconfig.songcharter-<yyyyMMdd-HHmmss>`. `--restart-flag` names a file it writes when `.wslconfig` changed;
  install.sh reads it.
- **`songcharter.winshortcut`:** the `.lnk` writer, standard library only. It writes through `.part` and `os.replace`,
  tried again for up to 1 s on a PermissionError.

## 3. Done means: each check, its command, and its last lines

### [dev] 1: the suite, with the new tests

`SONGCHARTER_SCAN_CHART=/home/user/song-charting/tools/scan-chart/scan.cjs <venv>/bin/python -m pytest -q -p no:cacheprovider --basetemp=/dev/shm/pt_m4_03 -rs`
(at e6233a8's tree):
```
SKIPPED [1] tests/test_engines_sections.py:525: no allin1 Python configured ($SONGCHARTER_ALLIN1_PYTHON)
SKIPPED [2] tests/test_package.py:34: run `npm install` in tools/scan-chart
624 passed, 3 skipped in 791.01s (0:13:11)
```
- These are the same three skips as main. 866e2dd only extends one wslsetup test: `tests/test_wslsetup.py` gives
  `11 passed`, and CI ran the whole suite on 866e2dd (section 4).
- I installed LnkParse3 1.6.0 into the shared scratchpad venv (pip), so that venv's runs include the LnkParse3 tests.
- New tests: 49, in `test_runtime.py` 15, `test_launch.py` 7, `test_wslsetup.py` 11, `test_winshortcut.py` 4 and
  `test_install.py` 12 (6 of them one parametrized test).

The order's list, and where each is tested:
- **fetch:** resumes a `.part` from a local HTTP server (the `Range: bytes=1000000-` request is checked), also after a
  dropped connection, and restarts against a server that ignores Range; prints its 50 MB lines (120 MB served: "50 of
  120 MB", "100 of 120 MB", each with MB/s); refuses a wrong SHA-256 (neither the file nor its `.part` left); refuses
  under `SONGCHARTER_OFFLINE=1` with zero requests made. A 404 is not retried.
- **The engine-list check** refuses a changed file (same size, other bytes; or another size), a missing one, an extra
  one and a symlink. `step_autochart` with a served zip refuses an archive with one file changed (no `src/` made),
  then takes the right one.
- **runtime.json is written last:** every step sees the old `runtime.json`, a failing step names itself and leaves it
  unchanged, and doctor runs after it is written.
- **environment():** `setdefault`, PATH with Node first and only once, the offline pair only with `models_complete`,
  no `SONGCHARTER_ALLIN1_PYTHON` when null, and `PYTHONSAFEPATH`.
- **wslsetup**, against stand-in `cmd.exe`, `reg.exe`, `wslpath` and `powershell.exe`:
  - the four memory cases: written, kept, asked and answered no or yes or `--yes`, and RAM unknown;
  - the backup, with the other lines and sections kept;
  - CRLF in a new file (an existing LF file stays LF, as `update_wslconfig` keeps line ends);
  - the under-11-GB rule (`allin1_python` set to null, and back once there is enough memory);
  - 15.9 GiB (17024139264 bytes) writes `memory=12GB`;
  - `--windows-ram-gb 16` on a 64 GB stand-in writes 12GB, and `$SONGCHARTER_WINDOWS_RAM_GB` works through `main`;
  - refused under 12 GB of RAM, and when a raise is declined under 8 GB;
  - interop off and plain Linux.
- **winshortcut:** a written `.lnk` parsed by LnkParse3 gives the description, working folder, arguments, icon, the
  flags and the environment block's target exactly; the bytes' layout is checked; a reinstall writes over the old
  link; what a link cannot hold is refused.
- **`launch --from-shortcut`** in a real child process with stdin from a pipe. After argparse's exit 2, and after "not
  installed", it is still alive 1–2 s later, prints "Press Enter to close this window", and ends after `\n`. With
  `--version` (exit 0) it does not wait.
- **uninstall,** with a temporary HOME:
  - No removes `app/`, `state/` and the launcher, and keeps `runtime/`, `bin/uv`, the uv cache, the models, the work
    folders and the library;
  - Yes removes the home, `~/.cache/songcharter` and `~/.cache/uv`;
  - the sizes in the question come from `du`;
  - a launcher that is not ours is kept;
  - `--yes` answers both questions;
  - on WSL the shortcut goes and the newest backup is restored;
  - `du` counts a hardlinked file once.
- **install.sh** (sourced): each lane threshold, a missing or empty nvidia-smi, a failing one (fresh, cpu before, cu132
  before, which is refused with the exact last line, and `--lane cpu`), the no-lane `sync_env` refusal for `""` and
  `cu999` (uv never runs), usage, the template's refusal and root's refusal.
- **build.sh:** the three assets, with a stand-in curl.

**Breaking the code** (`scratchpad/m4-03-mutate.py`, in a scratch git copy): there were 60 breaks across `runtime.py`,
`launch.py`, `wslsetup.py`, `winshortcut.py`, `install.sh` and `build.sh`. The first pass missed 3:
- **#34:** the "12 GB or more is kept" branch. A new test (866e2dd) catches it now, rechecked.
- **#32:** `du`'s existence filter. It is equivalent: `du` totals the paths that exist anyway.
- **#49:** the ANSI length check. It is equivalent: the Unicode check fires whenever it would.

The log is in `scratchpad/m4-03-logs/mutate.txt`.

### [dev] 2: build, install, rerun

`PYTHON=<venv>/bin/python bash packaging/release/build.sh 0.1.0-dev /dev/shm/m4-03/dist`:
```
check_no_audio: ok, 1 files and 145 archive members, no audio (.../songcharter-0.1.0-dev.tar.gz.part)
build.sh: songcharter 0.1.0-dev in /dev/shm/m4-03/dist
```

**The user and its home.** Docker has no daemon here, so this is a plain user, `useradd -m -d
/dev/shm/m4-03/home/sctest sctest`. Its HOME is on /dev/shm, so the install wrote nothing to the shared disk. It runs
through `runuser` with a clean environment: the proxy, a readable copy of the proxy's CA, and `UV_SYSTEM_CERTS`.

**autochart's archive** (`SONGCHARTER_AUTOCHART_URL`):
- This session's proxy refuses `github.com/dvar0/autochart/archive/...zip` with HTTP 403 ("GitHub access to this
  repository is not enabled"). add_repo answered that git reads work but attached nothing.
- So the dev runs took the archive from a local mirror: `git archive --format=zip --prefix=autochart-<sha>/` of the
  scratchpad's checkout at b5a41e8, served on 127.0.0.1 and named by the new `SONGCHARTER_AUTOCHART_URL`.
- Every file of it passed the engine-list check. CI fetched GitHub's real archive (section 4).

**Run 1:** `bash /dev/shm/m4-03/dist/install.sh --from /dev/shm/m4-03/dist --lane cpu --yes`, as sctest:
```
fetch node-v24.19.0-linux-x64.tar.gz: 50 of 57 MB, 24.8 MB/s
... (autochart's models, 478 MB, by fetch; the hub's models; uv's downloads)
doctor: OK
songcharter 0.1.0-dev is installed (lane cpu: asked for with --lane cpu).
exit 0 after 154 s
```

**On disk:** `~/.local/share/songcharter` 2.7 GB (the uv cache's files are hardlinked into it, so `du` counts them
there), `~/.cache/uv` 4.7 MB of its own, and `~/.cache/songcharter` 67 MB.

**The bug.** The first rerun was started with the current folder in the main checkout. It printed `No module named
songcharter.runtime`, and setup's exit 1 passed as doctor's problems. That is the bug fixed in f5e0311 (4.1). After a
rebuild, two more runs, both from inside the main checkout:
```
run A: exit 0 after 10 s     (new tarball: app re-extracted, songcharter rebuilt, "Prepared 1 package", nothing downloaded)
download lines in A:          (none: grep -nE "Download(ing|ed) |^fetch |^downloading ")
run B: exit 0 after 8 s
download lines in B:          (none)
```

`python -P -m songcharter.runtime check --home ...`: `node: ok … the pipeline's models: ok`, `check: OK`, exit 0.

### [dev] 3: the clip with that install

The clip came from `packaging/ci/make_clip.py` (30 s), run by the installed Python. The command was
`~sctest/.local/bin/songcharter chart /dev/shm/m4-03/out/clip.wav --out /dev/shm/m4-03/out/Clip --device cpu`, run
from inside the main checkout and offline by the launcher's environment:
```
[5/8] sections: allin1 harmonix-fold0 on cpu, 3 segments, 24.1 s
[6/8] guitar: 1 take, 23 Expert onsets in the first, 68.4 s
gate: OK (0 errors, 1 warnings; scan-chart 8.0.1: playable, 0 chart issues)
stages: decode 0.2 s, separate 43.6 s, drums 2.8 s, bass 16.5 s, sections 24.1 s, guitar 68.4 s, assemble 4.6 s, preview 3.4 s; total 163.5 s
chart exit 0 after 166 s
check_gate: ok, /dev/shm/m4-03/out/Clip: gate ok, scan-chart 8.0.1 playable with 0 chart issues; Expert onsets guitar 23, bass 120, drums 119
check_gate exit 0
```

## 4. CI (neb882/song-charting)

- **Run 41727211028** on 2756b3c (https://github.com/neb882/song-charting/actions/runs/41727211028): **success, both
  jobs.**
  - **linux:** the suite gave `623 passed, 4 skipped`; the skips are allin1's probe and the 3 LnkParse3 tests, as that
    venv has no LnkParse3. Then `all 3 Linux hooks passed: 10-lanes.sh 11s 20-device.sh 4s 30-install.sh 118s`.
  - **30-install's phases:**
    - its own LnkParse3 run of `test_winshortcut.py` and `test_wslsetup.py`: `15 passed`;
    - build.sh: `147 archive members, no audio`;
    - the install, killed during its uv sync: the last line was `songcharter: environments failed: interrupted. Run the
      same command again to continue.`, exit 2;
    - the install again: ok in 34 s (`lane cpu: no NVIDIA GPU found`; `runtime.json` lane cpu and that reason);
    - doctor: `doctor: OK`, 79.5 GB free;
    - the clip: `check_gate: ok, … Expert onsets guitar 23, bass 120, drums 119` (46 s);
    - uninstall No, then the reinstall: `the reinstall downloaded nothing` (6 s);
    - uninstall Yes: the home, the cache and the launcher are gone; `30-install: ok`.
  - **windows:** `30-shortcut.ps1 2s`; the LnkParse3 tests gave `4 passed`; then:
    ```
    round 1: Windows launched the link: C:\Users\RUNNER~1\AppData\Local\Temp\lnk-ok.txt says 'ok'
    round 2: Windows launched the link: ... says 'ok'        (written over the first)
    ```
    WScript.Shell reads (diagnosis only): `TargetPath=` empty, `Arguments=/c "echo ok> %TEMP%\lnk-ok.txt || pause"`,
    `WorkingDirectory=C:\Users\runneradmin`, `IconLocation=C:\Windows\System32\wsl.exe,0`.
- **Run 41730370579** on 866e2dd, the branch's head (https://github.com/neb882/song-charting/actions/runs/41730370579):
  **success, both jobs.**
  - **linux:** suite `623 passed, 4 skipped in 207.91s`; `all 3 Linux hooks passed: 10-lanes.sh 12s 20-device.sh 5s
    30-install.sh 138s`, with `the reinstall downloaded nothing` and `30-install: ok`.
  - **windows:** `round 1/2: Windows launched the link … says 'ok'`; `all 1 Windows hooks passed: 30-shortcut.ps1 2s`.
- The logs are in `scratchpad/m4-03-logs/ci-linux.txt` and `ci-windows.log`.

### 4.1 Bugs the checks found

- **The current folder's `songcharter/`.**
  - The dev rerun was started inside a checkout, so `python -m songcharter.runtime` imported the checkout's
    `songcharter/`: `python -m` puts the current folder first on sys.path.
  - The launcher had the same exposure: `songcharter` typed inside a checkout would run the checkout's code.
  - Fixed: `-P` on every call of the install's Python and in the launcher, and `PYTHONSAFEPATH=1` in `environment()`,
    so a child Python (M4-04's chart job, `sys.executable -m songcharter.cli`) is safe too. allin1's runner already
    handles `safe_path`.
  - install.sh also no longer takes Python's own exit 1 for doctor's.
- **huggingface_hub's EntryNotFoundError** is not an OSError, so a missing file on the hub would have been a bug's exit 3.

## 5. Deviations and decisions the order left open (each small; say if one should change)

1. **LnkParse3 is not in the `dev` extra.** M4-00 §5 gives `pyproject.toml` to M4-04 in wave 2, and the director said
   to stop before touching an M4-04 file, so I did not.
   - Instead, the LnkParse3 tests use `pytest.importorskip`;
   - `30-install.sh` installs it into `$CI_PY` with uv (1.6.0) and fails on a skip;
   - the Windows job already has it.
   - The director can add `LnkParse3` to `dev` at the merge, then `uv lock`.
   - **No relock happened**, so PROGRESS's deferred "pin the build backend" item can go ahead after the merge as
     planned.
2. **The flag HasName** is set, besides the order's five, because the order also asks for the description
   "songcharter" (NAME_STRING).
3. **The launcher** holds the install's absolute Python path (`exec "<home>/runtime/env/bin/python" -P -m
   songcharter.launch "$@"`). The spec shows `$HOME/...` and no `-P`; the path is the same for the default home.
4. **`SONGCHARTER_AUTOCHART_URL`** is a mirror override for the archive. It is a test seam, safe because every file is
   checked against the list. **`$SONGCHARTER_HOME`** also moves the install.
5. **wslsetup runs on WSL even with interop off.** It then prints the hand-set `.wslconfig` advice and the shortcut
   fallback, and decides allin1 from MemTotal: a 16 GB PC with WSL's default 8 GB loses allin1. The spec's "(4, 8, 9)
   skipped on plain Linux" is read as 4 and 9 (setup cannot be skipped).
6. **The memory rule's gaps:**
   - a raise changes only `memory` (it does not add `swap`);
   - a declined raise below 8 GB is refused ("only N GB, under 8");
   - Windows' RAM unknown is never refused;
   - `memory` ≥ 12 is kept even on a PC whose own target would be refused.
7. **When allin1 is left out:** `runtime.json`'s `allin1_python` is set to null by `wslsetup apply`, after setup has
   written `runtime.json` and `doctor.json`. On a PC under 16 GB, `doctor.json` (written before WSL restarts anyway)
   can therefore still show allin1 as ok.
8. **The disk check** subtracts what the install already holds (`du` of `runtime/`, uv's cache and
   `~/.cache/songcharter`), so a rerun on a nearly full disk is not stopped for space it already uses.
9. **Small UX choices:**
   - 5 s pass before `wsl --shutdown`, so the restart line can be read (M4-08 A3);
   - "Continue?" answered n exits 1, with nothing downloaded;
   - `uninstall --yes` answers yes to both the delete and the restore questions;
   - `uv python install --no-bin`: uv 0.8+ would otherwise put `python3.13` in `~/.local/bin`.
10. **cu126 gets the CUDA provider too**, as "GPU lane" says. It cannot load there (it needs CUDA 13), but a later
    switch to cu132 then downloads less.
11. **`check` copies and removes nothing.** It reports an app file that differs, and leaves a cpu lane's provider
    alone.

## 6. Not done, or untested

- **Nothing on WSL or Windows proper:**
  - step 4's `.wslconfig` probe, step 9 in a real distro, the restart;
  - the shortcut written under `/mnt/c` and started from the Start menu;
  - Smart App Control.
  - These are M4-08's. The stand-in tests cover the logic.
- **The `.lnk` and the Start menu.** It has no ID list (per the spec): Windows' ShellExecute launches it (CI), but
  WScript.Shell reads an empty TargetPath. Whether the Start menu lists it with the right icon, and what its
  Properties show, is for M4-08 to look at.
- **No GPU lane has run.** The cu132/cu126 sync, `install.js --onnxruntime-node-install=cuda12` from NuGet and the
  provider hash check have run only against stand-ins (`test_the_cuda_provider_by_lane`).
- **Download figures.** The ones printed are the order's (0.45/3.9/3.2 + 1 GB). The cpu install's measured disk use:
  2.7 GB in `~/.local/share/songcharter` (hardlinks included) and 67 MB in `~/.cache/songcharter`. The dev install
  took 154 s; CI's 34 s.
- **`build.sh`** reads uv's `.sha256` from GitHub and checks it against the pinned value. It needs the network.
- **The M4-04 coupling:** `launch._run` has `argv = ["doctor", "--quick"]`, for the director to make `["ui"]` at the
  wave-2 merge. Until then the shortcut's `ui --from-shortcut` fails (argparse) and waits for Enter.

## 7. For the director at the merge (docs: this order edited none)

- **PROGRESS:**
  - M4-03 built; CI green (the run URLs above);
  - the `-P`/`PYTHONSAFEPATH` finding;
  - LnkParse3 to add to `dev`;
  - the empty-TargetPath observation for M4-08;
  - deferred: GitHub's archive URL is blocked in this dev container's proxy (dev runs use the mirror override).
- **DESIGN §4** (the install, with the WSL route): the layout; the ten steps; the lane rule including the
  failing-nvidia-smi refusal; the memory rule as built (section 5, items 5–7); the launcher with `-P`;
  `runtime.json`'s fields; uninstall's two answers.
- **M4-05:**
  - its install phase can reuse `30-install.sh`'s kill pattern (`setsid`, wait for "Downloading" after the "[7/10]"
    header, then `kill -TERM -- -pgid`);
  - "uv reports no download" is checked as no `Download(ing|ed) ` line;
  - the `fetch` lines all start with `fetch `.
- **M4-07:** `$SONGCHARTER_RELEASE_URL` exists. `build.sh`'s placeholders are `@VERSION@`, `@APP_SHA256@`,
  `@RELEASE_URL@`, `@UV_URL@` and `@UV_SHA256@`, and it fails if any is left.

## 8. Cleanup

- **Removed:** `/dev/shm/m4-03` (the sctest home, dist, mirror, logs) and `/dev/shm/pt_m4_03`; the user `sctest`;
  the local mirror server.
- **Kept:** the worktree; `scratchpad/m4-03-logs/` (text logs, 116 KB); `scratchpad/m4-03-mutate.py`; LnkParse3 in
  the scratchpad venv; pyflakes in `scratchpad/lintvenv`.
- **New use of the shared disk:** about 0.2 MB. `/root/.cache/uv` was neither used nor touched: the sctest install had
  its own cache, on /dev/shm.

## 9. Review round 1 (the reviewer's six findings, all fixed)

Commits: **9b0570d** (F5), **f0e82d2** (F1–F4, F6).

- **F1 (downloads' hash checks):** tests now run the whole filled install.sh on stand-ins: curl serving files, uv
  inside its own tarball, the environments' python whose helpers' behaviour is set per test, `id` (not root), `df`
  (100 GB free) and `cmd.exe` (logging). `test_install.py` covers:
  - `test_a_download_that_is_not_the_pinned_file_fails_the_install`, with `wrong` and `truncated` variants: the exact
    "has SHA-256 X, not the pinned Y" line, no `.part` left, no uv, no launcher;
  - `test_a_release_asset_that_is_not_the_built_one_fails_the_install`:
    - a `--from` folder with another tarball gives "is not the file this install.sh was built with";
    - a `--from` folder missing it gives "has no";
    - a `--from` URL prefix with another tarball gives "has SHA-256";
    - the release URL serving nothing gives "could not download";
    - then the right one installs;
  - `test_a_release_installs_with_stand_ins`: the ten steps, a rerun with no curl, and a complete `.part` used as it
    is.
- **F2 (the lane rule):**
  - the parametrized lane cases gain 12.0 with driver 581 (cu132), `[N/A]` with 581 (cu132) and `[N/A]` with 560
    (cu126);
  - a previous cu126 with a failing nvidia-smi refuses with "the GPU is out of reach";
  - `test_an_nvidia_smi_that_does_not_answer_is_a_gpu_out_of_reach`: `SMI_TIMEOUT_S` is now a variable, and exit 124
    is said as "nvidia-smi did not answer within N s". A fresh install takes cpu with that reason; a cu132 install is
    refused.
- **F3 (bug: signals):** `helper()` runs steps 8 and 9. Any end but 0 and 1 ends the install with the line:
  - **the helper's own line**, when the helper wrote it to `$SONGCHARTER_FAILURE` as it printed it. `runtime.main` and
    `wslsetup.main` now do, through `runtime.say_failed`;
  - **otherwise install.sh's own**, e.g. "python -m songcharter.runtime setup stopped before it finished (killed by
    signal 9 (KILL): perhaps Linux ran out of memory)".

  Tests (`test_a_helper_that_fails_ends_the_install_with_the_line`): setup killed, setup exiting 2 silently, setup
  saying its own line (checked to appear once), and wslsetup killed (WSL mode). There are also Python-side checks
  that the failure file is written.
- **F4 (setup's result):**
  - "doctor.json is this run's" is now its `stat -c %y` (nanoseconds) before and after, not `-nt` against a stamp,
    which compares whole seconds on some bash versions;
  - tests: setup's exit 1 before doctor stops the install before the launcher (f5e0311's case);
  - doctor's problems (exit 1, `doctor.json` written) still install, with exit 1;
  - a changed `.wslconfig` prints the restart line and calls `cmd.exe /d /c wsl.exe --shutdown`; with no flag,
    neither happens;
  - letting exit 2 through is caught by the helper tests.
- **F5 (bug):** `wslsetup.memory_bytes()` reads [wsl2]'s memory from the lines, as `update_wslconfig` finds them,
  with values read as `parse_wslconfig` reads them and the last line winning. `plan()` and the RAM fallback use it.
  - The reviewer's file `[wsl2]\nmemory=16GB\nswap=0\nnestedVirtualization\n` is kept byte for byte.
  - With memory=8GB, the raise keeps `swap=0` and the bare key.
  - Plus a unit test of `memory_bytes`.
  - **Left for M4-02's code:** `wsl.parse_wslconfig`, and so doctor, still reads such a file as setting no memory.
- **F6:** `test_a_corrupt_archive_is_downloaded_again_on_the_rerun`: the first 40 bytes of the zip fail with "is not a
  whole zip … downloaded again next time"; the rerun downloads it again (two requests) and succeeds.

**Breaking the code** (`scratchpad/m4-03-mutate-r1.py`): the reviewer's breaks for F1–F6, plus four on the new code
(dropping the helper's own-line check, the last-line-wins rule, `say_failed`'s file write, and passing exit 2
through). All 15 are caught ("missed: 0").

**Suite at f0e82d2:** `641 passed, 3 skipped in 1058.62s` (the same three skips; `m4-03-logs/suite-2.txt`).
**CI run 41735308840** on f0e82d2 (https://github.com/neb882/song-charting/actions/runs/41735308840): success, both
jobs.
