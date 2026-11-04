# M4-03: the install in WSL, the launcher, `.wslconfig`, the Start-menu shortcut and uninstall

**Branch:** `m4-03-install`, from `main` after M4-01, M4-02 and M4-05a have merged. **Wave 2**, beside M4-04.
**Agent:** `sc-builder`, then `sc-reviewer` and `sc-inspector`. May push its branch to run CI.

## Intent

In his new Ubuntu window, the friend pastes one line from the pre-release page. It fetches `install.sh`, checks its
SHA-256, and runs it. The script sets up everything with no `sudo`:
- a Python;
- the right torch lane for his GPU and driver;
- allin1's Python;
- Node, scan-chart, autochart with its models and CUDA provider;
- every model;
- a launcher;
- enough memory for WSL;
- a Start-menu shortcut;
- `doctor.json`.

If any download fails, running the same line again continues. Later launches work offline.

## Scope

Creates:
- `packaging/linux/install.sh` (bash);
- `packaging/release/build.sh`: the release assets;
- `songcharter/runtime.py`, `songcharter/launch.py`, `songcharter/wslsetup.py` (writes `.wslconfig`),
  `songcharter/winshortcut.py` (writes a `.lnk`);
- `tests/test_runtime.py`, `tests/test_launch.py`, `tests/test_wslsetup.py`, `tests/test_winshortcut.py`;
- `packaging/ci/linux.d/30-install.sh`, `packaging/ci/windows.d/30-shortcut.ps1`.

Keeps, unchanged (already on this branch): `packaging/autochart/engine-files.sha256` and `make_engine_list.py`.

Must not touch: `pipeline.py`, `cli.py`, `engines/*`, `wsl.py`, `device.py`, `ui/`, `docs/`.

## The layout [decision]

```
~/.local/share/songcharter/            SONGCHARTER_HOME
  app/<version>/                       the release tarball: songcharter/, pyproject.toml, uv.lock, packaging/, tools/,
                                       eval/tools/autochart/ (the driver and its package files)
  bin/uv                               uv 0.13.5
  runtime/python/  runtime/env/  runtime/allin1/          (UV_PYTHON_INSTALL_DIR, the two UV_PROJECT_ENVIRONMENTs)
  runtime/node/  runtime/scan-chart/  runtime/autochart/  (src/ at b5a41e8, models/, node_modules/, the driver)
  runtime/runtime.json  runtime/state/install.done
  library/  uploads/  exports/  logs/  ui.json  doctor.json   (the UI's, M4-04 and M4-06)
~/.cache/uv/                           uv's cache (default; same ext4 volume, so the environments hardlink from it)
                                       [the release gate moved it to runtime/uv-cache: ~/.cache/uv is the person's]
~/.cache/songcharter/                  the pipeline's cache, unchanged: work/, ac/, trash/, models/ (ADTOF, hf/)
~/.local/bin/songcharter               the launcher
```

Under `/mnt/c` only the Songs folder (M4-06), `.wslconfig` and the shortcut are written.

## Spec

### `install.sh`

- **Usage:** `bash install.sh [--lane auto|cpu|cu126|cu132] [--yes] [--from DIR] [--windows-ram-gb N]`. `--from` takes the release
  assets from a folder or a URL prefix, for CI. `$SONGCHARTER_RELEASE_URL`, when set, replaces the release URL
  prefix. M4-07's CI hook runs the guide's line unchanged against a local server this way.
- **Shell rules:** `set -euo pipefail`. It needs `curl` or `wget`, `tar`, `xz` and `sha256sum`, which the Ubuntu
  26.04 WSL image ships [doc: its manifest]. It refuses to run as root.
- **What the release build fills in** (`build.sh` writes them into the script):
  - the version;
  - the app tarball's name and SHA-256;
  - the release URL prefix (`https://github.com/neb882/song-charting/releases/download/v<version>`);
  - uv's release tarball URL (`https://github.com/astral-sh/uv/releases/download/0.13.5/uv-x86_64-unknown-linux-gnu.tar.gz`)
    and the SHA-256 published beside it in `.sha256` (`f68d291c75783122dad58ab77def0e13f3233f358731db5d6d7e8715603b928f`
    for 0.13.5 [here]). Not the PyPI wheel: a wheel is a zip, and the Ubuntu image has no `unzip`.
- **On a failure**, the last line is always: `songcharter: <step> failed: <one line>. Run the same command again to
  continue.` Then exit 2.

Steps, each printing a header:

1. **Where am I.** WSL or not (`wsl.py`'s rule, in bash).
   - On plain Linux, the Windows steps (4, 8, 9) are skipped with a note. CI uses this.
2. **The lane.**
   - Read `nvidia-smi` (PATH, else `/usr/lib/wsl/lib/nvidia-smi`): name, driver, compute capability.
   - **cu132:** driver 580 or newer, and capability 7.5 or more.
   - **cu126:** driver 528 or newer, with a warning: "the guitar runs on the CPU: update the NVIDIA driver to 580 or
     newer, then paste the install line again: it switches to the GPU build (about 3 GB)".
   - **cpu:** otherwise ("no NVIDIA GPU found", or "update the driver to 528 or newer").
   - Capability 12.0 or more with a driver under 580 gets cpu: the cu126 build has no kernels for it.
   - `--lane` overrides. The thresholds come from DESIGN 4.3's table [inference: not re-checked].
   - **The lane is chosen at each run, not frozen.** A rerun picks the lane again from `nvidia-smi`. If it differs
     from `runtime.json`'s:
     - `uv sync` re-syncs both environments to the new lane: it swaps torch and the CUDA wheels, and keeps the rest;
     - `runtime setup` adds or removes the CUDA provider;
     - the summary says "lane changed: cu126 → cu132".
3. **Disk.** Needed, by lane: cpu 6 GB, cu126 15 GB, cu132 15 GB (the downloads unpacked, plus the 5 GB of work
   folders) [decision; M4-05 measures the cpu lane on disk, M4-08 the cu132].
   - Check `df -B1 "$HOME"`, and on WSL `df -B1 /mnt/c`. WSL's disk reports up to 1 TB free while it really grows on
     C: [doc: disk-space.md].
   - Stop with both numbers if either is short.
4. **Memory** (WSL only): print WSL's `MemTotal` and whether `.wslconfig` exists, so the friend sees it before
   the downloads. The change itself is step 9, once Python can read Windows' RAM.
   - The target is `memory` = Windows' RAM − 4 GB (12 GB on 16), with a floor of 8 GB, and `swap=8GB`.
5. **Show what will be downloaded, and a time estimate,** before anything starts.
   - Per lane: about 0.45 / 3.9 / 3.2 GB for the Python packages, plus 1 GB for the rest (Node, autochart and its
     models, the CUDA provider on GPU lanes, the pipeline's models). M4-05 confirms the figures.
   - The estimate is at 25 and at 100 Mbit/s.
   - Then "Continue? [Y/n]", unless `--yes`.
6. **uv and Python:**
   - download uv's release tarball, check it against the pinned SHA-256 (the published `.sha256`), and extract `uv`
     from it with `tar` to `$SONGCHARTER_HOME/bin/uv`;
   - download the app tarball, check its SHA-256, and extract it to `app/<version>/`;
   - then `uv python install 3.13.17`.
   - Every uv call has `UV_HTTP_TIMEOUT=300` and `UV_HTTP_RETRIES=5`, and keeps uv's own progress output.
7. **The environments:**
   - `uv sync --project app/<v> --frozen --no-dev --no-editable --managed-python --python 3.13.17 --extra app
     --extra <lane>`, with `UV_PROJECT_ENVIRONMENT=runtime/env`;
   - then `packaging/allin1`'s, with `UV_PROJECT_ENVIRONMENT=runtime/allin1`.
8. **The rest:** `runtime/env/bin/python -m songcharter.runtime setup --home "$SONGCHARTER_HOME" --app app/<v>
   --lane <lane> --lane-reason "<reason>"` (below). Its exit code becomes the script's.
9. **The Windows side** (WSL with interop): `python -m songcharter.wslsetup apply`.
   - It writes `.wslconfig`, per the memory rule below.
   - It writes the Start-menu shortcut.
   - It prints what it did.
10. **The launcher:** write `~/.local/bin/songcharter` (below); write `runtime/state/install.done` holding the
    version and lane; print `doctor`'s summary.
    - If step 9 changed `.wslconfig`, the last lines are "WSL restarts now so the new memory setting takes effect.
      Then start songcharter from the Start menu." followed by `cmd.exe /c wsl.exe --shutdown`, which closes this
      window.

### The memory rule (`wslsetup.apply`) [decision]

- **No `.wslconfig`, or no `memory` in `[wsl2]`:** write `memory=<target>GB` and `swap=8GB` into `[wsl2]`. Keep every
  other line and section. Back the old file up as `.wslconfig.songcharter-<yyyyMMdd-HHmmss>`.
- **`memory` at 12 GB or more:** keep it, and say so.
- **`memory` under 12 GB:** ask "WSL may use N GB; songcharter needs about 12. Raise it to <target> GB? [Y/n]", unless
  `--yes`.
- **Windows' RAM unknown:** write nothing, and say how to set it by hand.
- **Rounding:** Windows' RAM is rounded to the nearest whole GB before the 4 GB are taken off. A "16 GB" PC reports
  about 15.9 GiB, which must give `memory=12GB`, not `11.9GB`.
- **Test override:** `--windows-ram-gb N` (or `SONGCHARTER_WINDOWS_RAM_GB=N`) replaces the measured value. M4-08 part A
  uses it to write the friend's 16 GB `.wslconfig` on a larger PC, and the tests use it.
- **The resulting WSL memory under 11 GB** (a PC under 16 GB; as built, one whose RAM rounds to 14 GB or less: 15
  GB gives `memory=11GB`, 11.8 * 10^9 bytes, which keeps allin1): `runtime.json`'s `allin1_python` is null, so the
  sections use the librosa fallback, which holds no 7.8 GB model run. The install says so. Under 8 GB it refuses:
  "songcharter needs a PC with at least 12 GB of RAM".
- `.wslconfig` is written with CRLF line ends, Windows' convention; WSL reads either [inference].

### The Start-menu shortcut (`winshortcut.py`, written by `wslsetup.apply`)

- **Where:** `<Programs>\songcharter.lnk`, with `Programs` from `wsl.shell_folder("Programs")` (the user's own
  Start-menu programs folder: no admin).
- **Target and arguments:** `%windir%\System32\cmd.exe` with `/c "wsl.exe -d <distro> --cd ~ -e
  /home/<user>/.local/bin/songcharter ui --from-shortcut || pause"`.
  - `cmd.exe` is signed and no script file is written.
  - `|| pause` keeps the window open when `wsl.exe` itself fails early (a distro that will not start), before the
    launcher's own pause can run.
  - The working folder is `%USERPROFILE%`; the icon is `wsl.exe`'s; the description is "songcharter".
  - **A reinstall overwrites** an existing `songcharter.lnk` in place.
- **The writer** follows [MS-SHLLINK]:
  - a `ShellLinkHeader` with flags `HasArguments | HasWorkingDir | HasIconLocation | IsUnicode | HasExpString`;
  - no ID list and no LinkInfo;
  - `StringData` for the working folder, the arguments and the icon;
  - an `EnvironmentVariableDataBlock` holding `%windir%\System32\cmd.exe` in ANSI and in Unicode;
  - the terminal block.
- **Why this way:**
  - it is no script file;
  - written from WSL, it has no Mark of the Web, so Smart App Control's list of risky file types, which applies only
    to files from an untrusted origin, does not touch it;
  - `cmd.exe` and `wsl.exe` are Microsoft-signed [doc: textslashplain.com; inference for this case].
- **If writing fails**, or interop is off, the install prints the fallback: open Ubuntu from the Start menu and type
  `songcharter`.

### `songcharter.runtime setup --home H --app A --lane L --lane-reason TEXT`

Each step checks first and returns at once when its result is there and verified.

**`fetch(url, dest, sha256, size=None)`:**
- downloads through `dest.part`, resuming with `Range` (3 retries, 60 s socket timeout);
- prints a line every 50 MB with the total and the rate;
- checks size and SHA-256, then `os.replace`s;
- honours `SONGCHARTER_OFFLINE=1`;
- `urllib.request` only.

Steps:

1. **Node:** `node-v24.19.0-linux-x64.tar.gz` from nodejs.org, SHA-256
   `f625d97cd707df4ff96254916fbc5ff014f09c09effe5a1e0ca8f6d41a8789d4`, 57,409,532 bytes (autochart's own pin,
   `scripts/runtime-artifacts.json`), into `runtime/node/`. Then `node --version` must print `v24.19.0`.
2. **scan-chart:** copy `A/tools/scan-chart/{scan.cjs,package.json,package-lock.json}` to `runtime/scan-chart/`;
   then `npm ci --omit=dev --ignore-scripts --no-audit --no-fund` there, with that Node's `npm`.
3. **autochart:**
   - download `https://github.com/dvar0/autochart/archive/b5a41e8e44db84d4c7288c946cf35aa2264dcbf5.zip`;
   - extract it to `src.part/`;
   - check every file against `A/packaging/autochart/engine-files.sha256`: path, size and SHA-256, no file
     missing, no extra file. The archive's own bytes are not promised stable, so they are not hashed. The list
     matches a `git archive` of the commit [here, planning job];
   - rename it to `src/`.
   - Copy the driver and its package files from `A/eval/tools/autochart/`. Then `npm ci --omit=dev --ignore-scripts`.
   - **On a GPU lane:** `node node_modules/onnxruntime-node/script/install.js --onnxruntime-node-install=cuda12` (the
     manifest's name; it fetches NuGet's `Microsoft.ML.OnnxRuntime.Gpu.Linux` 1.27.0, 212 MB). Then check:
     - `libonnxruntime_providers_cuda.so` SHA-256 `0d3171e422fc7b554cb05af69009b519beec03d6084ebe924782307b29338f39`
       (251,623,184 bytes);
     - `libonnxruntime_providers_shared.so` `c6a12593396095f5670160e284c35d1700b7708cf3037b7042e2a5200ccae772`.

     These hashes come from the planning job's copy of 1.27.0, and onnxruntime-node's installer checks nothing
     itself.
4. **autochart's models:** from `src/engine/catalog.json`'s `fretformer-2-onnx`, as `fetch_models.sh` does: each
   remote file from
   `https://huggingface.co/Dvaro/autochart-models/resolve/8a88855d745f0b508f68ac606d7cbdac2878c87d/<path>` by its
   size and SHA-256; bundled licences copied. About 478 MB.
5. **The pipeline's models**, through their own pinned and hash-checked loaders, with `HF_HOME` set to
   `~/.cache/songcharter/models/hf` and `HF_HUB_DISABLE_SYMLINKS_WARNING=1`:
   - `separate.model_paths("htdemucs_6s")`;
   - `engines.sections.checkpoint_paths("harmonix-all")`;
   - `engines.adtof.weights_path()`.
6. **`runtime.json`**, written last and atomically:
   ```
   {"version": 1, "songcharter", "app", "home", "lane", "lane_reason", "python": sys.executable,
    "allin1_python": runtime/allin1/bin/python | null (the memory rule), "node", "scan_chart", "autochart",
    "ffmpeg": imageio_ffmpeg.get_ffmpeg_exe(), "hf_home", "models_complete": true, "steps": {name: ISO time}}
   ```
7. **Doctor:** with `launch.environment()`, `device.report(full=True)` into `H/doctor.json`.
   - Exit 0 when ok, 1 with problems, 2 when a step failed (its name, one line, then "run the same command again to
     continue"), and 3 for a bug, with its traceback.

`songcharter.runtime check --home H` re-verifies without downloading.

### The launcher and `songcharter.launch`

- **`~/.local/bin/songcharter`:**
  ```sh
  #!/bin/sh
  exec "$HOME/.local/share/songcharter/runtime/env/bin/python" -m songcharter.launch "$@"
  ```
- **`launch.environment(runtime)`:**
  - `SONGCHARTER_HOME`, `SONGCHARTER_NODE`, `SONGCHARTER_AUTOCHART`, `SONGCHARTER_ALLIN1_PYTHON` (only when not
    null), `SONGCHARTER_SCAN_CHART`, `FFMPEG`, `HF_HOME`, `HF_HUB_DISABLE_SYMLINKS_WARNING=1`, `PYTHONUTF8=1`;
  - `PATH` with Node's folder first (assemble finds scan-chart's node with `which`);
  - `HF_HUB_OFFLINE=1` and `SONGCHARTER_OFFLINE=1` when `models_complete` is true [the release gate dropped
    `SONGCHARTER_OFFLINE`, which kept the lyrics weights from their first-use download];
  - a variable the person already set wins (`setdefault`), except `PATH`.
- **`launch.main(argv)`:**
  - reads `runtime.json`; when it is missing: exit 2, "songcharter is not installed: run the install line again";
  - with no arguments, runs `songcharter ui` (M4-04; until M4-04 merges, print `doctor`'s summary);
  - otherwise runs `cli.main(argv)`;
  - `--from-shortcut`: on any non-zero exit, print the error and "Press Enter to close this window", and wait. The
    advisor's finding 11: a launch failure must never just close the window.
- **`songcharter uninstall [--yes]`** (handled in `launch`, before `cli`):
  - removes the shortcut, the launcher, `app/` and `runtime/state/`;
  - then asks once: "Also delete the downloads (Python packages, Node, autochart and its models: about N GB) and your
    song caches and library (M GB)? A reinstall reuses the downloads if you keep them. [y/N]".
    - **No** keeps `runtime/` (except `state/`), `~/.cache/uv` and `~/.cache/songcharter/models`, so a reinstall
      downloads nothing [as built after the release gate: uv's cache is `runtime/uv-cache`, and a reinstall on the
      guide's path downloads install.sh and the app's tarball, about 1 MB];
    - **Yes** deletes those and `~/.cache/songcharter`, `library/`, `uploads/` and `exports/`.
    - N and M are measured with `du` at the time.
  - It offers to restore the newest `.wslconfig.songcharter-*` backup, and never deletes `.wslconfig` itself.
  - Finally it prints:
    - WSL's disk does not shrink by itself;
    - `wsl --unregister <distro>` removes everything, when the distro holds nothing else.

### `packaging/release/build.sh <version> <out>`

- `git archive --format=tar.gz --prefix=songcharter-<v>/ HEAD` gives `songcharter-<v>.tar.gz`. `check_no_audio.py`
  runs on its listing.
- Fill in `install.sh`'s placeholders: the version, the app tarball's SHA-256, uv's release tarball URL with the SHA-256
  read from its published `.sha256`, and the release URL.
- `SHA256SUMS` for both files.

## Done means

[dev] In the dev container:

1. The suite passes, with new tests:
   - **`fetch`:** resumes a `.part` from a local HTTP server, prints its 50 MB lines, refuses a wrong SHA-256, and
     refuses under `SONGCHARTER_OFFLINE=1`.
   - **The engine-list check** refuses a changed, a missing and an extra file.
   - **`runtime.json`** is written last.
   - **`environment()`:** `setdefault`, the offline pair, and `allin1_python` null.
   - **`wslsetup`,** against stand-in interop:
     - the four memory cases, with the backup written and the other sections kept;
     - CRLF;
     - the under-11-GB rule;
     - rounding (a measured 15.9 GiB writes `memory=12GB`);
     - `--windows-ram-gb 16` on a 64 GB stand-in writes `memory=12GB`.
   - **`winshortcut`:** a written `.lnk` parsed by LnkParse3 (dev extra) gives the target, arguments, working folder
     and icon exactly.
   - **`launch --from-shortcut`** waits for Enter after a non-zero exit (stdin from a pipe).
   - **`uninstall`** keeps and deletes the listed folders, with a temporary home.
2. `bash packaging/release/build.sh 0.1.0-dev /dev/shm/m4-03/dist`. The container runs as root and the script
   refuses root, so make a user with `useradd -m sctest`. Then, as that user:
   - `bash /dev/shm/m4-03/dist/install.sh --from /dev/shm/m4-03/dist --lane cpu --yes` exits 0 (this downloads about
     1.5 GB);
   - a second run downloads nothing and exits 0 in under 2 minutes.
3. Using that install, `songcharter chart <clip> --out /dev/shm/m4-03/out/Clip --device cpu` exits 0, and
   `check_gate.py` passes.

[CI]
- **Hook `30-install.sh`** (`ubuntu-latest`, in `docker run ubuntu:26.04` as a plain user, after `apt-get install -y
  curl ca-certificates git xz-utils` to match the WSL image), with the assets from `build.sh` served from a folder:
  - the install exits 0;
  - `songcharter doctor` exits 0 (lane cpu);
  - the clip passes `check_gate.py`;
  - **interrupted downloads:** the install is killed during the uv sync, then rerun to exit 0;
  - **uninstall:** with **No**, the reinstall downloads nothing (uv reports no download, the log has no `fetch`
    lines); with **Yes**, `~/.local/share/songcharter` and `~/.cache/songcharter` are gone.
- **Hook `windows.d/30-shortcut.ps1`** (`windows-latest`):
  - `python -c` writes a `.lnk` with `winshortcut`, shaped like the real one: target `%windir%\System32\cmd.exe`,
    arguments `/c "echo ok> %TEMP%\lnk-ok.txt || pause"`;
  - **the pass condition:** `Start-Process <path>` creates `lnk-ok.txt` within 10 s. Windows itself resolved and
    launched it;
  - reading it back with `(New-Object -ComObject WScript.Shell).CreateShortcut(<path>)` (`TargetPath`, `Arguments`,
    `WorkingDirectory`) is printed for diagnosis only, not as the pass;
  - writing the `.lnk` a second time over the first works (the reinstall case).

[Hardware] M4-08:
- the install on a fresh Ubuntu-26.04 distro, timed, lane cu132;
- `.wslconfig` handled;
- the shortcut starts songcharter (with Smart App Control on, if the owner agrees);
- uninstall with No, then reinstall.

## Depends on

- M4-01: the locks;
- M4-02: `wsl.py`, `device.report`, `doctor`, `cuda_library_path`;
- M4-05a: the hooks and the helpers.

## Added at M4-01's merge

- **No lane, no sync.** `uv sync` with no lane extra installs PyPI's CUDA torch (about 3 GB), and allin1's project then
  has no torchaudio (M4-01 review, F2). The install always passes exactly one lane. Make `install.sh` and any helper
  that syncs refuse with a clear message when no lane is chosen, and test that refusal.
- **No silent downgrade of the lane** (M4-02 review, R1). The install picks the lane from nvidia-smi on every run.
  When nvidia-smi is there but fails (for example "GPU access blocked by the operating system" after a Windows
  update), refuse to move an existing cu132 or cu126 install to the cpu lane, and say why: the GPU is out of reach,
  not missing. Use `songcharter.device`'s distinction between a missing and a failing nvidia-smi.
- **Write `.wslconfig` only through `wsl.update_wslconfig`** (M4-02 review, R3). It keeps every other line, cuts inline
  comments and quotes as WSL reads them, and never leaves a second `memory=` line.
