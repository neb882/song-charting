# M4-05a report: the CI skeleton

Branch `m4-05a-ci-skeleton` (from main 56b5591), worktree
`/tmp/claude-0/-home-user/5307d417-c453-5e74-8f13-b43b2df06ab1/scratchpad/wt/m4-05a`. Pushed. The remote head is
5fdb80e (`git ls-remote` agrees). **CI is green on 5fdb80e.**

## Commits

| commit | what |
|---|---|
| 0a9ef34 | CI skeleton: the workflow, the hook runners and the CI helpers (M4-05a). 8 new files, 639 lines |
| 5fdb80e | CI: imageio-ffmpeg on the pip path, since the runner has no ffmpeg (a fix after the first run) |

Files (all new; nothing under `songcharter/`, `tests/`, `docs/` or `pyproject.toml` was touched, checked with `git diff
--name-only main..HEAD`):
- `.github/workflows/ci.yml`
- `packaging/ci/run-hooks.sh`, `packaging/ci/run-hooks.ps1`
- `packaging/ci/linux.d/README.txt`, `packaging/ci/windows.d/README.txt` (the hook contract)
- `packaging/ci/make_clip.py`, `packaging/ci/check_gate.py`, `packaging/ci/check_no_audio.py` (the `.py` files and
  `run-hooks.sh` are executable)

## What was built

### `ci.yml`
- **Triggers and settings:**
  - push to `main` and `m4-*`, `pull_request` and `workflow_dispatch`;
  - `permissions: contents: read`;
  - concurrency group `ci-${{ github.ref }}` with `cancel-in-progress: true`;
  - the five actions at the versions the spec names (checkout@v4, setup-python@v5, setup-node@v4, cache@v4,
    upload-artifact@v4).
- **Job `linux`** (ubuntu-latest, 120 min, `shell: bash`, so `-eo pipefail`):
  1. checkout;
  2. CI_ART and CI_TMP made under `$RUNNER_TEMP` and exported through `$GITHUB_ENV`;
  3. Python 3.13;
  4. Node 24.19.0, with npm's cache keyed on `tools/scan-chart/package-lock.json`;
  5. `actions/cache` on `~/.cache/pip` and `~/.cache/uv`, keyed on the hash of `pyproject.toml`, `uv.lock` and
     `packaging/allin1/uv.lock`;
  6. the install step, which branches on whether `uv.lock` exists:
     - with it: `pip install uv==0.13.5`, then `UV_PYTHON=<setup-python's python> uv sync --frozen --extra cpu
       --extra app --extra dev`, and `CI_PY=.venv/bin/python`;
     - without it: `pip install torch==2.15.0 --index-url https://download.pytorch.org/whl/cpu`, then `pip install -e
       ".[dev,separate,drums,bass,sections,preview]" "imageio-ffmpeg>=0.6"`, and `CI_PY` = setup-python's python;
     - either way, it asserts that `torch.version.cuda is None` (the CPU build) and exports CI_PY;
  7. `npm ci` in `tools/scan-chart`;
  8. the suite: `"$CI_PY" -m pytest -q -p no:cacheprovider --basetemp="$RUNNER_TEMP/pt" -rs`, with
     `SONGCHARTER_SCAN_CHART` set job-wide;
  9. `bash packaging/ci/run-hooks.sh linux`;
  10. `if: always()`: `check_no_audio.py "$CI_ART"`, then the upload (artifact `ci-linux`) only if that check
      succeeded, so audio never gets uploaded.
- **Job `windows`** (windows-latest, 30 min, `shell: pwsh`):
  1. checkout;
  2. CI_ART and CI_TMP;
  3. Python 3.13;
  4. `pip install pytest LnkParse3`, and CI_PY exported;
  5. `./packaging/ci/run-hooks.ps1 windows`;
  6. the same audio check and conditional upload (artifact `ci-windows`).

### The runners
- **`run-hooks.sh linux`:**
  - runs `linux.d/*.sh`, sorted bytewise (`LC_ALL=C sort -z`), each as `bash -euo pipefail <hook>` from the repo root
    with stdin from /dev/null;
  - prints a header and `ok in N s`, or `FAILED (exit N) after N s` and the hooks passed before it, and exits with the
    hook's code;
  - sets the defaults for a run by hand: CI_PY (python3), CI_TMP and CI_ART (made absolute), and CI_CLIP
    (`$CI_TMP/clip.wav`);
  - writes the clip with `make_clip.py ... 30` before the first hook, unless CI_CLIP names another file that already
    exists;
  - with no hooks it prints `no Linux hooks` and passes. A bad argument exits 2.
- **`run-hooks.ps1 windows`:**
  - runs `windows.d/*.ps1` (extension compared exactly, ordinal sort), each in a fresh pwsh started with
    `-NoProfile -NonInteractive -EncodedCommand`;
  - the child sets `$ErrorActionPreference='Stop'`, `Set-StrictMode -Version Latest` and
    `$PSNativeCommandUseErrorActionPreference=$true`, then runs `& $env:CI_HOOK`. An exception prints the error and its
    script stack and exits 1; otherwise it exits with `$LASTEXITCODE`;
  - the hook's path travels in CI_HOOK, so no quoting is needed;
  - headers, times, the stop at the first failure and the defaults work as in the bash runner;
  - with no hooks it prints `no Windows hooks` and passes. A bad argument exits 2.

### The helpers (`check_gate.py` and `check_no_audio.py` use the standard library only)
- **`make_clip.py OUT.wav [SECONDS]`:**
  - the planning generator with a fuller module docstring and an argument check (SECONDS ≥ 2, one bar);
  - the audio code is unchanged: its output is byte-identical to the planning clip.
- **`check_gate.py SONG_FOLDER`** checks:
  - the four files (`notes.chart`, `song.ini`, `song.ogg`, `report.json`);
  - `gate.ok`;
  - `gate.scan_chart.ran`, `playable`, and `chart_issues == 0`;
  - `tracks.{guitar,bass,drums}.expert.onsets > 0`.

  It lists every failure (exit 1), or prints one ok line with the onset counts (exit 0); bad usage exits 2. When the
  folder is missing but `<folder>.failed` exists (where songcharter writes a build the gate failed), it says so and
  lists that report's failures.
- **`check_no_audio.py FOLDER [FOLDER ...]`:**
  - walks every file, following symlinked folders once each (loop-safe);
  - flags the ten extensions (any case) and files that start with `RIFF`, `OggS`, `ID3`, `fLaC` or the 11-bit MPEG
    frame sync (FF Ex). It also flags a file it cannot read;
  - exit 1 lists each file with its reason; exit 2 means the path is not a folder.

## Done means: the checks and their evidence

### 1. [dev]
- **Syntax and compile:**
  - `bash -n packaging/ci/run-hooks.sh` gives `bash -n: ok`;
  - `python -m py_compile packaging/ci/*.py` gives `py_compile: ok`;
  - extra: actionlint 1.7.12 with shellcheck 0.11.0 on PATH, so the inline `run:` scripts are linted too:
    `actionlint: 0 findings` (rerun after the second commit);
  - extra: `shellcheck packaging/ci/run-hooks.sh` exits 0;
  - extra: PowerShell's parser finds 0 errors in `run-hooks.ps1`. PSScriptAnalyzer 1.25.0 finds only the 9
    `PSAvoidUsingWriteHost` warnings, which are deliberate (console output in CI).
- **`check_no_audio.py`,** on real encoder output:

  | folder | exit | reason given |
  |---|---|---|
  | an `.ogg` (soundfile Vorbis) | 1 | `ogg/song.ogg: an audio extension (.ogg)` |
  | a WAV renamed `clip.json` | 1 | `starts with a RIFF header (WAV)` |
  | JSON, PNG, JPEG, UTF-8 text, an empty file, plus a symlink loop | 0 | `check_no_audio: ok, 5 files, no audio` |
  | FLAC renamed `x.dat` | 1 | |
  | Ogg renamed `x.bin` | 1 | |
  | lameenc MP3 with no ID3, renamed `x.txt` | 1 | `MPEG frame sync (FF FB)` |
  | an ID3-tagged file | 1 | |
  | `SONG.WAV` | 1 | |
  | the clean folder plus a nested `.ogg` | 1 | `1 of 6 files` |
  | a missing folder | 2 | |
  | a UTF-16 file with its BOM | 1 | flagged as MPEG FF FE: documented in the docstring |

- **`make_clip.py clip.wav 30`:**
  - prints `... 30.0 s`; soundfile reads it as 2 channels, 44100 Hz, 30.0 s, PCM_16;
  - `cmp` with the planning clip (`m4probe/clip/clip.wav`) shows them identical; sha256 c5b7ed9068d6e937….
- **Extra: the clip end to end here.**
  - Command: `songcharter chart clip.wav --out Clip --device cpu --threads 2`, with the real autochart, allin1 and
    scan-chart, and the work folder under /dev/shm.
  - It exited 0 in 208 s. Stages: separate 44.0 s, drums 3.1, bass 4.7, sections 24.5, guitar 115.9, assemble 5.8,
    preview 3.3.
  - songcharter's own line: `gate: OK (... scan-chart 8.0.1: playable, 0 chart issues)`.
  - `check_gate.py Clip` printed `check_gate: ok, ... Expert onsets guitar 23, bass 120, drums 119`: the planning run's
    counts.
  - `check_no_audio.py` passes on the folder holding only its report.json, and fails on the song folder itself
    (`song.ogg`).
- **`check_gate.py` mutations** (real folder: golden `take_me_out` with an empty song.ogg; it passes with onsets
  868/645/943). Each of these exits 1, naming its failure:
  - gate.ok false (the issue is listed);
  - scan-chart not run (the reason is listed);
  - not playable plus 2 chart issues (both listed);
  - 2 chart issues alone;
  - no drums Expert;
  - 0 bass onsets;
  - no notes.chart or song.ogg;
  - an unreadable report.json, or none;
  - a missing folder;
  - only `Clip.failed` present (its failures are listed).

  Bad usage exits 2.
- **Runner behaviour** (in throwaway repo layouts, including one under a path with `Jörg's Söngs`):
  - bash: `-e` (a `false`), `-u` (an unset variable), pipefail (`false | true`), `exit 7` (the runner exits 7) and a
    dangling symlink hook each fail. The hooks after the failure do not run;
  - bash: the order is bytewise (`10-` < `9-` < `B` < `a`), `README.txt`/`notes.txt` are ignored, stdin is empty, the
    working folder is the repo root, and a given existing CI_CLIP is reused (its mtime is unchanged);
  - pwsh 7.6.7 on Linux: Write-Error, a failing native command, `throw`, `exit 5` (the runner exits 5), an unset
    variable, a .NET exception, a failing cmdlet, and a hook that ends with a non-zero `$LASTEXITCODE` each fail;
  - pwsh: a tolerated failure that is then reset passes; `x.ps1xml` is ignored; CI_CLIP is absent.
- **Breaking the code** (copies of the files, each break caught by the checks above):
  - check_no_audio without the magic-byte rules: the renamed WAV exits 0;
  - check_gate without the chart-issues rule: 2 chart issues exit 0;
  - run-hooks.sh without `-u`: the unset-variable hook passes;
  - run-hooks.ps1 without native stops: a fail-then-succeed native hook passes.
- **The full suite here,** run as CLAUDE.md runs it with this session's venv:
  - before any change, with no scan-chart `node_modules` in the worktree: `509 passed, 3 skipped in 489.05s`;
  - after the build, with `npm ci` done in the worktree's `tools/scan-chart`: `511 passed, 1 skipped in 512.45s`. The
    skip is the allin1 real probe;
  - the six files that failed in CI, with `FFMPEG` set to imageio-ffmpeg's bundled 7.0.2: `138 passed in 552.51s`.

### 2. [CI]
- **Run 1, on 0a9ef34:** https://github.com/neb882/song-charting/actions/runs/41687417489. **It failed**:
  - linux took 2m07s. The suite ended `10 failed, 455 passed, 1 skipped, 46 errors in 53.08s`;
  - every error line is `ToolError: ffmpeg not found` or `No module named 'imageio_ffmpeg'`, and the 3 assertion
    failures quote the same message;
  - windows was green in 27s.
- **Run 2, on 5fdb80e:** https://github.com/neb882/song-charting/actions/runs/41690822922. **Both jobs green.**
  - **linux 4m16s** (ubuntu-24.04 image 20261025.353):
    - install 54 s; it printed `python 3.13.17 torch 2.15.0+cpu`;
    - scan-chart 1 s; Node v24.19.0;
    - Suite step 2m58s: `511 passed, 1 skipped in 176.28s` (the skip is the allin1 probe);
    - Hooks: the clip was written (`/home/runner/work/_temp/ci-tmp/clip.wav 30.0 s`), then `no Linux hooks`;
    - `check_no_audio: ok, 0 files`; the upload ran;
    - `Cache saved with key: python-Linux-3.13-29f892a9…` and the npm cache saved.
  - **windows 29s** (windows-2025-vs2026 image):
    - `CI_PY=C:\hostedtoolcache\windows\Python\3.13.17\x64\python.exe`;
    - `no Windows hooks`;
    - `check_no_audio: ok, 0 files`.
- **What I could and could not read:** `gh run list`, `gh run view` (`--json jobs`, `--log`, `--log-failed`) all
  worked through the proxy. `GET repos/.../actions/caches` was refused with "Access to this GitHub Actions path is
  not permitted through this proxy." (HTTP 403), so the cache sizes are unread. The logs are in
  `/tmp/claude-0/-home-user/5307d417-c453-5e74-8f13-b43b2df06ab1/scratchpad/ci-logs/`.

## Departures from the spec's letter, and why

1. **`"imageio-ffmpeg>=0.6"` on the pip install line.**
   - The runner has no ffmpeg, and the spec's pip extras bring none. That failed 56 tests in run 1.
   - It is the same wheel that M4-01's `ffmpeg` extra (part of `app`) adds on the uv path, and the one
     `songcharter.audio.ffmpeg_exe` falls back to.
   - CLAUDE.md's dev command relies on a system ffmpeg; it may want a note (director, docs).
2. **The Windows job also runs `check_no_audio.py` and uploads `CI_ART`** (artifact `ci-windows`), which the spec's
   three steps do not list.
   - Reason: the hook contract promises every hook a CI_ART that gets uploaded, and only this order may edit ci.yml.
   - Remove those two steps if unwanted.
3. **Windows hooks get no CI_CLIP, and their CI_PY has no songcharter installed.**
   - The spec's Windows job installs only pytest and LnkParse3, so make_clip.py (numpy, soundfile) cannot run there.
   - Hooks import songcharter from the repo root, the working folder. Both points are written in
     `windows.d/README.txt`.
4. **Small additions:**
   - `-rs` on pytest (skip reasons in the log);
   - the torch CPU-build assertion after the install;
   - `UV_PYTHON` pointing uv at setup-python's 3.13;
   - `PIP_DISABLE_PIP_VERSION_CHECK`;
   - `if-no-files-found: ignore` on the uploads;
   - `check_no_audio.py` takes several folders.

## Not done, or uncertain

- **The uv branch of the install step has never run.** No `uv.lock` exists on this branch.
  - Its first run will be on a branch that has both M4-01's lock and this ci.yml.
  - M4-01's and M4-02's branches were cut from main before ci.yml existed, so pushing them alone runs no CI. Merge
    M4-05a first, then rebase or merge them, so that their hooks run (10-lanes needs the uv branch).
  - I read their committed hooks (`10-lanes.sh`, `20-device.sh`) without changing them. They use CI_PY, CI_TMP and
    CI_ART as the contract says, and they touch none of my files.
- **The failing paths of the runners were exercised only locally** (bash; pwsh 7.6.7 on Linux). On GitHub only the
  no-hooks path ran. The Windows runner has not run a real hook on Windows.
- **Annotations on both runs:**
  - "Node.js 20 is deprecated": the v4/v5 actions the spec pins are forced onto Node 24. They worked; newer majors
    exist.
  - "The ubuntu-latest label will migrate to Ubuntu 26 beginning October 19, 2026": this run still got
    ubuntu-24.04. When the label flips, glibc becomes 2.43 and Docker's image set may differ. M4-01's
    `check_wheels.py` comment calls glibc 2.39 "CI's Ubuntu 24.04"; its check stays valid, only that comment would be
    stale.
- **`check_no_audio.py` takes folders only.** M4-03 and M4-07 say it "runs on [the tarball's] listing", so they must
  unpack the tarball first, or the helper needs a small extension (the director's call).
- **`check_no_audio.py` flags a UTF-16 file that has a BOM.** Windows PowerShell 5.1's `>` writes such files; pwsh 7
  writes UTF-8. This is documented.
- **Docs:** the order forbids `docs/`, so PROGRESS and DESIGN are untouched. Suggested for the director at the merge:
  - PROGRESS M4: M4-05a built, CI green on run 41690822922 (linux 4m16s, windows 29s), the ffmpeg finding;
  - the hook contract lives in `packaging/ci/*/README.txt`;
  - DESIGN 4.6 could point at `ci.yml` and the hooks.
- **Leftovers:**
  - scan-chart's `node_modules` (26 MB, gitignored) stays in the worktree's `tools/scan-chart`, so a reviewer can run
    test_package;
  - lint tools: `/tmp/claude-0/-home-user/5307d417-c453-5e74-8f13-b43b2df06ab1/scratchpad/lintvenv` (35 MB);
  - test folders: `/dev/shm/m4-05a` (29 MB). The chart's work folder and the pytest basetemp were deleted.

## Round 2: the review's five minor findings (commit 627c8f0)

**Commit and CI.** All five were fixed in 627c8f0, with tests in the new `packaging/ci/test_ci.py`: 78 pytest tests,
stdlib and pytest only.
- Both CI jobs now run it in a step "Test the CI tools", before the suite and the hooks. The Windows job runs it with
  Windows' own pwsh.
- Run 3: https://github.com/neb882/song-charting/actions/runs/41695429587, **green**:
  - linux 6m14s: test_ci `78 passed in 33.37s` (pwsh is on ubuntu-latest, so nothing skipped); suite
    `511 passed, 1 skipped in 256.17s`; `no Linux hooks`;
  - windows 47s: test_ci `64 passed, 14 skipped in 21.00s` (13 bash-runner tests skip on Windows, and make_clip has
    no numpy there); `no Windows hooks`.
- **Proof that the tests fail without the fixes:** the same test_ci.py, beside 5fdb80e's scripts and READMEs, gives
  `45 failed, 33 passed`. The failures cover every fix:
  - F1: 7 bash and 7 pwsh tests (6 stray entries plus the missing folder, per runner);
  - F2: 4 new header kinds, 20 archive cases (10 archives, each given as its folder and as the file), the clean
    archives (×2), the too-deep and broken archive, and the missing path;
  - F3: 1 test; F4: 1 test; F5: 1 test (the README).
- **One bug found by the new tests before the push:** `GzipFile` took its mode from the spooled temp file (`w+b`)
  and opened a nested `.tar.gz` for writing. All three decompressors now get the read mode explicitly.

**The fixes**
- **F1:** both runners exit 2, before the env, the clip or any hook, when the hook folder is missing, or when it holds
  any entry except README.txt and depth-1 files with the platform's extension. Each such entry is named. Tested
  strays: `.bash`, an extensionless file, the other platform's extension, a subfolder, a hidden file, `.md`/`.psm1`/
  `.ps1xml`. A folder holding only README.txt still prints "no ... hooks" and passes.
- **F2:** `check_no_audio.py`:
  - new headers: AIFF/AIFC (`FORM`....`AIFF`/`AIFC`), MP4/M4A (`ftyp` at offset 4; also HEIC and AVIF, documented),
    Matroska/WebM (`1A 45 DF A3`);
  - archives are found by their first bytes, not their names: zip, tar (`ustar` at 257), and gzip/xz/bzip2 around a
    tar or around a single file (the inner name drops the compression suffix);
  - every member is checked by name and first bytes, and nested archives are opened recursively to 4 levels. A nested
    archive is spooled to memory up to 64 MB, then to a temp file;
  - a deeper, corrupt or encrypted archive counts as a failure;
  - it takes files as well as folders, and a missing path exits 2;
  - also checked by hand: a tar.gz of the real charted clip folder fails, naming `Clip/song.ogg`.
- **F3:** `check_gate.py` fails whenever `SONG_FOLDER.failed` exists, and lists the .failed report's failures. Why
  this rather than comparing report times:
  - a passing build deletes `<output>.failed` (`assemble.py`, `_remove_build(failed_folder(...))` after a passing
    gate), so a `.failed` beside the folder always means the latest build into it failed;
  - no flag is needed, and folder mtimes after a copy or restore are not safe to compare.
- **F4:** the child pwsh runs with `-OutputFormat Text`. Before, with stderr piped, the log showed `#< CLIXML` and an
  `<Objs>` blob; now it shows `WARNING: careful now`. Tested with piped stdout and stderr, on Linux and on Windows.
- **F5:**
  - `windows.d/README.txt` says what a hook must check itself:
    - after `& other.ps1`, `if ($LASTEXITCODE) { exit $LASTEXITCODE }`, or run the sub-script as a native command
      (`pwsh -NoProfile -File other.ps1`), which stops the hook;
    - after `Start-Process -Wait -PassThru`, check `.ExitCode`, since Start-Process does not set `$LASTEXITCODE` at
      all (checked: ExitCode=3 with LASTEXITCODE=0);
  - the runner already ran each hook with `$ErrorActionPreference='Stop'` and failed one whose last `$LASTEXITCODE`
    is non-zero; a test now pins that;
  - three tests check that each of the README's ways catches a sub-script's `exit 1` that is followed by a native
    success;
  - the case cannot be caught in general (a sub-script's exit code overwritten later), so it stays documented, not
    detected.

**Also re-checked after the change:** actionlint (0), shellcheck (0), `bash -n`, `py_compile`, the PowerShell parser
(0 errors; PSScriptAnalyzer only the 9 deliberate Write-Host warnings). The real-encoder folders give the same exits
as before, and `check_gate` passes the charted clip (23/120/119) and the golden folder.

**In scope:** only `.github/workflows/ci.yml` and `packaging/ci/` changed (`test_ci.py` is new). test_ci.py lives in
`packaging/ci`, not `tests/`, because this order may not touch `tests/`. The suite's `testpaths` keeps it out of
CLAUDE.md's suite run, so the suite's counts are unchanged.
