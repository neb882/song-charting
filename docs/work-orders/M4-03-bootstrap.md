# M4-03: the first-launch bootstrap and the launcher

**Branch:** `m4-03-bootstrap`, from `main` after M4-01 and M4-02 have merged. **Wave 2**, beside M4-04. **Agent:**
`sc-builder`, then `sc-reviewer` and `sc-inspector`.

## Intent

On the friend's PC, the first launch must turn the installed files into a working songcharter with no help and no
admin rights. That means:
- a Python;
- the right torch lane for his GPU and driver;
- allin1's own Python;
- Node, scan-chart and autochart's engine with its models;
- every model the pipeline downloads;
- a `doctor.json` that says what it found.

Later launches must work offline. PowerShell does only what needs PowerShell; everything testable lives in Python.

## Scope

Creates:
- `packaging/windows/bootstrap.ps1`, `packaging/windows/Test-Bootstrap.ps1`, `packaging/windows/songcharter.cmd`;
- `packaging/autochart/engine-files.sha256` and `packaging/autochart/make_engine_list.py`, which writes it;
- `songcharter/runtime.py`, `songcharter/launch.py`;
- `tests/test_runtime.py`, `tests/test_launch.py`.

Must not touch:
- `pipeline.py`, `cli.py`, `engines/*` (M4-04 works on those in the same wave);
- `pyproject.toml`, `uv.lock` and `packaging/allin1/`;
- `docs/`.

## The layout [decision, following DESIGN 4.3: the install and the cache share one root]

`R` = `%LOCALAPPDATA%\songcharter` (`$SONGCHARTER_HOME` overrides it; tests and CI use that).

```
<app>\                   the installed files (M4-07): R\app for setup.exe, the extracted folder for the portable zip
                         songcharter\, pyproject.toml, uv.lock, packaging\, tools\scan-chart\ (no node_modules),
                         eval\tools\autochart\{ac_headless.cjs,package.json,package-lock.json}, bootstrap.ps1,
                         songcharter.cmd, bin\uv.exe, VERSION, NOTICE.txt
R\runtime\python\        uv-managed CPython 3.13.17               (UV_PYTHON_INSTALL_DIR)
R\runtime\uv-cache\      uv's cache, same volume, so environments hardlink from it (UV_CACHE_DIR)
R\runtime\env\           the main environment, songcharter installed non-editable (UV_PROJECT_ENVIRONMENT)
R\runtime\allin1\        allin1's environment (packaging\allin1's lock)
R\runtime\node\          Node 24.19.0 (node.exe, npm)
R\runtime\scan-chart\    scan.cjs, package.json, package-lock.json, node_modules\
R\runtime\autochart\     ac_headless.cjs, package.json, package-lock.json, node_modules\ (onnxruntime-node),
                         src\ (autochart at b5a41e8e44db84d4c7288c946cf35aa2264dcbf5), models\fretformer-v2\...
R\runtime\runtime.json   what the bootstrap set up (below)
R\runtime\state\         bootstrap.done (holds the app's VERSION and the lane)
R\models\                ADTOF (models_dir(), unchanged) and hf\ (HF_HOME: htdemucs_6s, allin1's checkpoints)
R\work\  R\ac\  R\trash\ the pipeline's cache (cache.py, unchanged)
R\logs\                  bootstrap-<yyyyMMdd-HHmmss>.log
R\doctor.json
```

autochart's install keeps the layout `find_install` expects (`root/ac_headless.cjs`, `root/src`, `root/models`,
`root/node_modules/onnxruntime-node`), so no engine code changes.

## Spec

### `bootstrap.ps1` (Windows PowerShell 5.1; ASCII only; `Set-StrictMode -Version 2`; `$ErrorActionPreference = 'Stop'`)

- **Parameters:**
  - `-Root` (default `$env:SONGCHARTER_HOME`, else `$env:LOCALAPPDATA\songcharter`);
  - `-App` (default `$PSScriptRoot`);
  - `-Lane auto|cpu|cu126|cu132` (default `$env:SONGCHARTER_LANE`, else `auto`);
  - `-LibraryOnly`: define the functions and return, for the tests.
- **PowerShell 5.1 only:** no `??`, ternaries, `-Parallel`, `ConvertFrom-Json -AsHashtable` or `&&`.
  `$ProgressPreference = 'SilentlyContinue'`.
- **It downloads nothing itself:** `uv.exe` and Python do every download.
- **Steps**, each logged with `Start-Transcript` to `R\logs\`:
  1. **Free disk** on R's drive (`[IO.DriveInfo]`). Needed, by lane: cu132 4.5 GB, cu126 5.0 GB, cpu 1.5 GB, plus
     1.5 GB for Node, the engine and the models.
     - Below that: stop, exit 2, naming the numbers.
     - Below that plus the 5 GB the work folders may use: warn and go on.
  2. **The lane:** `Select-Lane`, unless `-Lane` names one. It returns `@{Lane=...; Reason=...; Gpu=...}`. Rules, in
     order, on the first GPU of `nvidia-smi --query-gpu=name,driver_version,compute_cap
     --format=csv,noheader,nounits` (PATH, else `$env:SystemRoot\System32\nvidia-smi.exe`):
     - no `nvidia-smi`, a non-zero exit, or output that does not parse: `cpu`, "no NVIDIA GPU found" (or "nvidia-smi
       failed: <first line>");
     - compute capability under 5.0: `cpu`, "<name> is too old for these torch builds";
     - compute capability 12.0 or more and driver under 580: `cpu`, "update the NVIDIA driver to 580 or newer to use
       <name>" (the cu126 build has no kernels for it [inference, DESIGN 4.3]);
     - driver 580 or more and capability 7.5 or more: `cu132`;
     - driver 528 or more: `cu126`;
     - otherwise: `cpu`, "update the NVIDIA driver to 528 or newer to use <name>".

     The driver thresholds are DESIGN 4.3's table. Compare driver versions as numbers (`[version]`).
  3. **Python:** `bin\uv.exe python install 3.13.17`, with `UV_PYTHON_INSTALL_DIR`, `UV_CACHE_DIR` and
     `UV_NO_PROGRESS=1` set for every uv call.
  4. **The main environment:** `uv sync --project <App> --frozen --no-dev --no-editable --managed-python --python
     3.13.17 --extra app --extra <lane>`, with `UV_PROJECT_ENVIRONMENT=R\runtime\env`.
  5. **allin1's environment:** `uv sync --project <App>\packaging\allin1 --frozen --managed-python --python 3.13.17
     --extra <lane>`, with `UV_PROJECT_ENVIRONMENT=R\runtime\allin1`.
  6. **The rest:** `R\runtime\env\Scripts\python.exe -m songcharter.runtime setup --root R --app <App> --lane <lane>
     --lane-reason "<reason>"`.
  7. On exit 0 or 1 from step 6: write `R\runtime\state\bootstrap.done` holding `<VERSION> <lane>` (from
     `<App>\VERSION`; `dev` when it is absent), then print the doctor's summary lines.
- **Exit codes:** 0 ready; 1 ready, but `doctor` found problems (printed); 2 a step failed (its name, uv's or
  Python's last lines, and the log's path).
- **Re-runnable:** every step checks rather than trusts. uv sync is idempotent, and `runtime setup` re-verifies
  hashes. The installer runs the bootstrap again after an update.

### `Test-Bootstrap.ps1` (PowerShell 5.1)

- Dot-sources `bootstrap.ps1 -LibraryOnly`, then for each case writes a fake `nvidia-smi.cmd` (an `@echo` of fixed
  CSV, or `exit /b 1`) into a temporary folder put first on PATH, and asserts `Select-Lane`'s lane and reason
  fragment.
- Cases:

  | case | expected |
  |---|---|
  | no nvidia-smi | cpu, "no NVIDIA GPU" |
  | `NVIDIA GeForce RTX 4070, 581.57, 8.9` | cu132 |
  | `NVIDIA GeForce RTX 4070, 560.94, 8.9` | cu126 |
  | `NVIDIA GeForce GTX 1060 6GB, 581.57, 6.1` | cu126 |
  | `NVIDIA GeForce RTX 5070, 572.16, 12.0` | cpu, "580" |
  | `NVIDIA GeForce GTX 970, 512.95, 5.2` | cpu, "528" |
  | exit 1 | cpu, "nvidia-smi failed" |
  | `garbage` | cpu |

- Also: the free-disk numbers for each lane, and that `bootstrap.ps1` is pure ASCII.
- Prints `PASS n/n` and exits 0, or names each failure and exits 1.

### `songcharter/runtime.py`

`python -m songcharter.runtime setup --root R --app A --lane L --lane-reason TEXT` and `python -m
songcharter.runtime check --root R`.

Each step is a function that first checks whether its result is already there and verified, and returns at once if
so. All downloads go through `fetch(url, dest, sha256, size=None)`:
- writes `dest.part`, resuming with an HTTP `Range` header when the `.part` exists;
- retries 3 times;
- checks the size and SHA-256, then `os.replace`s into place;
- honours `SONGCHARTER_OFFLINE=1` (raises `ToolError` naming what is missing);
- `urllib.request` only: it follows the system proxy settings and needs no new dependency.

Steps, in order:

1. **Node.**
   - `https://nodejs.org/dist/v24.19.0/node-v24.19.0-win-x64.zip`, SHA-256
     `57f71ab3652e797d84acddc79c81cc9ff1c6ddb2a1974cdb83f00fee9bff4c73`, 37,304,352 bytes. These are autochart's own
     pins (`scripts/runtime-artifacts.json` at the pinned commit), and also in nodejs.org's `SHASUMS256.txt`.
   - Extract to `R\runtime\node\`, dropping the archive's top folder.
   - Verify `node.exe --version` prints `v24.19.0`.
   - On Linux and macOS (tests, CI's Linux job), use `node` from PATH and record its version.
2. **scan-chart.**
   - Copy `<A>\tools\scan-chart\{scan.cjs,package.json,package-lock.json}` to `R\runtime\scan-chart\`.
   - Run npm there: `node <node>\node_modules\npm\bin\npm-cli.js ci --omit=dev --ignore-scripts --no-audit
     --no-fund`. On Linux, `npm` from PATH.
   - Skip when `node_modules\scan-chart\package.json` exists and its version is 8.0.1.
3. **autochart's engine.**
   - `https://github.com/dvar0/autochart/archive/b5a41e8e44db84d4c7288c946cf35aa2264dcbf5.zip`. GitHub archives
     are not promised byte-stable, so do not check the archive's hash.
   - Extract it to `R\runtime\autochart\src.part\`, without the archive's top folder.
   - Then check every file against `packaging/autochart/engine-files.sha256`: the archive's files, exactly, by
     relative path, SHA-256 and size. No missing file, no extra file.
   - Rename `src.part` to `src` only when all match.
   - Copy `<A>\eval\tools\autochart\{ac_headless.cjs,package.json,package-lock.json}` beside it. Run the same npm
     command there.
   - Then delete `node_modules\onnxruntime-node\bin\napi-v6\{linux,darwin,win32\arm64}` on Windows (about 200 MB
     that never loads). `install_key` hashes `onnxruntime-node/package.json` only, so pruning does not invalidate
     takes.
4. **autochart's models.**
   - Read `src\engine\catalog.json`, component `fretformer-2-onnx`, as `eval/tools/autochart/fetch_models.sh` does.
   - For each file: `bundled-license` copies from `src\engine\<path>`; otherwise
     `fetch("https://huggingface.co/Dvaro/autochart-models/resolve/8a88855d745f0b508f68ac606d7cbdac2878c87d/<path>",
     models\<path>, sha256, size)`.
   - Also fetch the README at that revision (the attribution record the script keeps). About 478 MB in all [here].
5. **The pipeline's own models**, through their modules' pinned and hash-checked loaders, with `HF_HOME=R\models\hf`
   and `HF_HUB_DISABLE_SYMLINKS_WARNING=1` set first:
   - `separate.model_paths("htdemucs_6s")`;
   - `engines.sections.checkpoint_paths("harmonix-all")` (all 8 folds, 11 MB: the ensemble runs on CUDA);
   - the ADTOF weights through `engines.adtof.weights_path()`, with `SONGCHARTER_MODELS=R\models`.
6. **`runtime.json`**, written last, atomically:
   ```
   {"version": 1, "songcharter": __version__, "app": A, "root": R, "lane": L, "lane_reason": TEXT,
    "python": sys.executable, "allin1_python": R\runtime\allin1\Scripts\python.exe,
    "node": ..., "scan_chart": R\runtime\scan-chart\scan.cjs, "autochart": R\runtime\autochart,
    "ffmpeg": imageio_ffmpeg.get_ffmpeg_exe(), "hf_home": R\models\hf, "models_complete": true,
    "cache_root": null, "steps": {name: ISO time verified}}
   ```
   - On Linux, `allin1_python` is `R/runtime/allin1/bin/python` when that exists, else `$SONGCHARTER_ALLIN1_PYTHON`,
     else null (then the sections use the librosa fallback).
   - The Windows paths above are what the bootstrap's layout gives.
7. **Path check and cache root.**
   - Run `device.path_check(R, node)` (R is where the work and scratch folders go, as `launch` sets
     `SONGCHARTER_CACHE`).
   - If `ok` is false, try `<SystemDrive>\songcharter-cache` [decision]:
     - create it, and check that a file can be written and deleted;
     - run `path_check` again;
     - if ok, set `"cache_root"` to it in `runtime.json` and print why: "your profile path is long; song caches go
       to C:\songcharter-cache".
     - Other accounts on the PC can read that folder by default [inference]. The message says so.
   - If neither is ok: a problem saying how to turn on long paths (admin), with Microsoft's registry value
     `HKLM\SYSTEM\CurrentControlSet\Control\FileSystem\LongPathsEnabled = 1`.
8. **Doctor.** With the environment `launch.environment()` builds, call `device.report(full=True)` and write
   `R\doctor.json`.
   - Exit 0 when it is ok, 1 when it found problems, 2 when a step above failed (with its name and error, one
     line, no traceback: the `InputError`/`ToolError`/`OSError` convention).
   - Any other exception exits 3 with its traceback, as the CLI does.

`check` re-verifies every step without downloading, and prints what is missing. Exit 0 when complete, 1 when not.

### `songcharter/launch.py`

- `environment(runtime: dict) -> dict[str, str]`, from `runtime.json`:
  - `SONGCHARTER_HOME`, `SONGCHARTER_NODE`, `SONGCHARTER_AUTOCHART`, `SONGCHARTER_ALLIN1_PYTHON`,
    `SONGCHARTER_SCAN_CHART`, `FFMPEG`, `HF_HOME`, `HF_HUB_DISABLE_SYMLINKS_WARNING=1`;
  - `PATH` with the Node folder first (assemble finds scan-chart's node with `shutil.which("node")`);
  - `PYTHONUTF8=1`;
  - `SONGCHARTER_MODELS=R\models`, and `SONGCHARTER_CACHE` = `cache_root` when it is set, else R. Both are always
    set, so a root other than `%LOCALAPPDATA%\songcharter` (CI, tests) keeps every file under R:
    `cache.user_cache()` and `adtof.models_dir()` do not know `SONGCHARTER_HOME`;
  - `HF_HUB_OFFLINE=1` and `SONGCHARTER_OFFLINE=1` when `models_complete` is true.

  A variable the person already set wins over the computed one: `setdefault`, except `PATH`.
- `main(argv)`:
  - reads `$SONGCHARTER_HOME\runtime\runtime.json` (exit 2 with "run bootstrap.ps1" when absent);
  - applies `environment()` to `os.environ` before importing anything that reads it;
  - with no arguments, runs `songcharter ui` (M4-04; until M4-04 merges, print the doctor summary and exit 0);
  - with arguments, runs `cli.main(argv)`: `songcharter.cmd chart song.mp3 --out X` and `songcharter.cmd doctor`
    both work.

### `songcharter.cmd`

- `SC_APP` = `%~dp0`; `SONGCHARTER_HOME` defaults to `%LOCALAPPDATA%\songcharter`.
- If `%SONGCHARTER_HOME%\runtime\state\bootstrap.done` is missing, or its first word differs from the first line of
  `%SC_APP%VERSION`:
  - run `powershell -NoProfile -ExecutionPolicy Bypass -File "%SC_APP%bootstrap.ps1" -Root "%SONGCHARTER_HOME%"
    -App "%SC_APP%."`;
  - on exit code 2, `pause` and exit 2.
- Then `"%SONGCHARTER_HOME%\runtime\env\Scripts\python.exe" -m songcharter.launch %*`, and exit with its code.
- Title the window `songcharter (keep this window open while you use it)`.

### `packaging/autochart/make_engine_list.py`

- Given a checkout of autochart at the pinned commit (`git -C <src> rev-parse HEAD` must equal it), writes
  `engine-files.sha256`: one line per file in `git ls-files`, `<sha256>  <size>  <path>` (POSIX separators), sorted
  by path.
- Commit the list. 346 files at that commit [here].

## Done means

[dev] In the dev container, with `SONGCHARTER_HOME=/dev/shm/m4-03/home`:

1. `tests/test_runtime.py` and `tests/test_launch.py` pass, with the full suite. They cover:
   - `fetch` resuming a `.part` from a local HTTP server, refusing a wrong SHA-256, and refusing under
     `SONGCHARTER_OFFLINE=1`;
   - the engine-list check refusing one changed, one missing and one extra file;
   - `runtime.json` written last;
   - `environment()`'s variables, including `setdefault` and the offline pair;
   - the path-check fallback with a stand-in `path_check`.
2. `python -m songcharter.runtime setup --root /dev/shm/m4-03/home --app $PWD --lane cpu --lane-reason test`:
   - runs on Linux (Node from PATH, the real downloads of the engine archive and the models; about 0.6 GB);
   - exits 0;
   - writes `runtime.json` with `models_complete: true`.

   A second run downloads nothing and exits 0 in under 60 s.
3. With that `runtime.json`, `python -m songcharter.launch chart <clip.wav> --out /dev/shm/m4-03/out/Clip --device
   cpu --threads 2`:
   - exits 0 and the gate is OK, with scan-chart run (`report.json` `gate.scan_chart.ran` true);
   - the same command again, with a new `--out`, exits 0 offline: `HF_HUB_OFFLINE` and `SONGCHARTER_OFFLINE` are set
     by `launch`. Network blocking is not needed for this check; M4-05 runs it without a network route.
4. `pwsh` (PowerShell 7) is not available in the container. PowerShell checks run in CI.

[CI-windows] M4-05 runs, under `shell: powershell` (5.1) on `windows-latest`:
- `Test-Bootstrap.ps1` (PASS 8/8 lane cases and the rest);
- `bootstrap.ps1 -Root $env:RUNNER_TEMP\sc -App $PWD -Lane auto` to exit 0 or 1 (lane `cpu`, "no NVIDIA GPU
  found");
- `songcharter.cmd doctor` and `songcharter.cmd chart` on the clip, both exit 0;
- the bootstrap run twice: the second downloads nothing (its log shows every step "verified").

[Windows HW] M4-08 times the bootstrap on the cu132 lane and checks the lane and its reason on both PCs.

## Depends on

- M4-01: the lock and `packaging/allin1`;
- M4-02: `device.report`, `device.path_check` and `songcharter doctor`.
