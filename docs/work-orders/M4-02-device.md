# M4-02: WSL and device checks, `songcharter doctor`, and the pipeline's records

**Branch:** `m4-02-device`, from `main`. **Wave 1**, beside M4-01 and M4-05a. **Agent:** `sc-builder`, then
`sc-reviewer` and `sc-inspector`. May push its branch to run CI.

## Intent

The friend must always see where his chart runs and why: "GPU: RTX 4070 (12 GB)", or "CPU mode: <reason>", for
torch and for the guitar separately. In WSL, that also means the Windows side:
- does WSL have the memory `.wslconfig` asked for?
- can the Windows browser reach the server?
- how much room is left on C:, where WSL's disk grows?

One module answers all this, and `songcharter doctor` writes it to `doctor.json` for the install, the UI and the
diagnostics.

The pipeline gets four things:
- the CUDA 13 library path for autochart's node process (M4-00, finding 4);
- a record of every CPU fallback;
- GPU memory freed between stages;
- RAM, swap and VRAM sampled per stage, for M4-08.

## Scope

Creates:
- `songcharter/wsl.py`: read-only Windows interop, plus opening a URL;
- `songcharter/device.py`;
- `tests/test_wsl.py`, `tests/test_device.py`;
- `packaging/ci/linux.d/20-device.sh`.

Changes:
- `eval/gpu.sh`, its comment only (lines 22–26). It says onnxruntime-node's CUDA provider needs "the CUDA 12
  libraries". The 1.27.0 provider needs CUDA 13 (M4-00, finding 4). Add that the CUDA 12 path it assembles predates
  this, and point to M4-00b. The code stays as it is.
- `songcharter/cli.py` (`doctor`);
- `songcharter/pipeline.py`;
- `songcharter/engines/autochart.py` (the library path);
- `tests/test_pipeline.py`, `tests/test_engines_autochart.py`.

Must not touch:
- `pyproject.toml` and the locks (M4-01);
- `cache.py`;
- `docs/`.

No chart may change on Linux: the golden charts show no UNEXPECTED change.

## Spec

### `songcharter/wsl.py` (standard library only)

Every Windows call runs through interop with `cwd="/mnt/c"` (so `cmd.exe` does not warn about a UNC folder) and a
timeout. A failure returns None; it never raises.

- `is_wsl()`: `$WSL_DISTRO_NAME` is set, or `/proc/sys/kernel/osrelease` contains `microsoft`. `distro()` returns
  `$WSL_DISTRO_NAME`.
- `interop_ok()`: `cmd.exe` runs, from PATH or `/mnt/c/Windows/System32/cmd.exe`.
- `windows_env(name)`:
  - runs `cmd.exe /u /c echo %NAME%`. `/u` makes `cmd`'s own output UTF-16LE, so a user name like `Jörg` survives;
  - decodes the output;
  - returns None when the variable is unset (the output is `%NAME%`).
- `to_linux(winpath)`: `wslpath -u`.
- `oem_encoding()`: from `cmd.exe /c chcp`'s "Active code page: N", as `cpN` (default `cp437`). Used to decode
  `reg.exe`.
- `shell_folder(name)`:
  - runs `reg.exe query "HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders" /v <name>`
    (`Personal` is Documents, `Desktop`, `Programs` the Start-menu programs folder), and decodes it with
    `oem_encoding()`;
  - expands each `%VAR%` with `windows_env`;
  - returns the Linux path only if it exists. That covers OneDrive moving Documents.
- `onedrive_roots()`: `OneDrive`, `OneDriveConsumer` and `OneDriveCommercial` from `windows_env`, as Linux paths.
- `wslconfig()`: `%USERPROFILE%\.wslconfig` parsed (section `[wsl2]`, keys case-insensitive). Returns
  `{"path", "exists", "memory_bytes", "swap_bytes", "localhost_forwarding", "networking_mode"}`, with sizes such as
  `12GB` and `12288MB` turned into bytes, and each missing value None.
- `windows_build()`: from `cmd.exe /c ver`.
- `windows_ram_bytes()`:
  - `powershell.exe -NoProfile -NonInteractive -Command "(Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory"`
    (timeout 30 s). That is an inline command, not a script file; Smart App Control's behaviour on it is untested.
  - Otherwise, when `.wslconfig` sets no `memory`: 2 × `MemTotal` (WSL's default is half of Windows' RAM [doc:
    wsl-config.md]).
  - Otherwise None.
- `windows_curl(url)`: `/mnt/c/Windows/System32/curl.exe -s -m 5 <url>`, for M4-04's forwarding self-check.
- `open_url(url)`: `explorer.exe <url>`. It returns exit code 1 even on success: ignore the code, and report only
  whether it started.

### `songcharter/device.py`

- `nvidia_smi()`:
  - runs `nvidia-smi --query-gpu=name,driver_version,memory.total,compute_cap --format=csv,noheader,nounits`, from
    PATH, else `/usr/lib/wsl/lib/nvidia-smi` [doc: NVIDIA's WSL guide];
  - returns `({"name", "driver", "vram_mb", "compute_cap"}, None)`, or `(None, reason)`.
- `torch_report()`: version, `torch.version.cuda`, `cuda_works` and its error (reuse `separate.cuda_works`), the
  arch list, and a 512×512 matmul when CUDA works.
- `choose_device(asked)`: as `Engines.device` decides, which then calls it, with a sentence for every CPU outcome:
  - "asked for the CPU";
  - "no NVIDIA GPU found";
  - "this install's torch has no CUDA (the cpu lane)";
  - "CUDA did not run on <name>: <error>".
- `autochart_cuda(install)`, run only by `full`. With the autochart install found, a `node -e` script:
  - creates an `onnxruntime-node` session with `executionProviders: ["cuda"]` on the smallest `.onnx` file in
    `<install>/models/fretformer-v2/`;
  - runs with `LD_LIBRARY_PATH` from `engines.autochart.cuda_library_path()`;
  - prints the provider it got;
  - returns `(ok, detail)`; timeout 120 s.
- `guitar_device(torch_device, autochart_ok) -> (device, reason)`:
  - `"cuda"` when both are true;
  - else `"cpu"`, with one of:
    - "no GPU";
    - "the cu126 lane: onnxruntime-node needs CUDA 13, so a 580 or newer driver. Then paste the install line again:
      it switches to the GPU build (about 3 GB)";
    - "the CUDA provider did not load: <detail>".
- `default_threads()`: `max(1, cpu_count − 1)`, for the UI. The CLI default does not change, so no chart moves.
- `memory()`: `MemTotal`, `MemAvailable`, `SwapTotal` and `SwapFree` from `/proc/meminfo`, in MB.
- `report(full=True)` gives `doctor.json`:
  ```
  {"songcharter", "written", "platform", "python",
   "wsl": null | {"distro", "windows_build", "interop", "windows_ram_mb", "wslconfig": wsl.wslconfig(),
                  "memory_matches_config": bool | null,
                  "documents": {"registry": the raw Personal value, "windows": expanded, "linux": the /mnt/c path or
                                null}},
   "gpu", "gpu_error", "torch", "device": {"chosen", "reason"}, "guitar_device", "guitar_reason",
   "cpu": {"logical", "threads_default"}, "ram": memory(),
   "disk": {"home_free_mb", "windows_c_free_mb" (df of /mnt/c, WSL only)},
   "components": {"ffmpeg", "node", "scan_chart", "autochart", "autochart_cuda" (full), "allin1" (full),
                  "demucs", "librosa", "matplotlib"},
   "problems": [...], "notes": [...], "ok"}
  ```
  - **`problems`** (each makes `ok` false):
    - no ffmpeg, scan-chart or autochart;
    - free space under 6 GB in WSL or on C:;
    - WSL memory under 8 GB.
  - **`notes`** (shown, not failing):
    - the CPU-mode reason, and the guitar's. On the cu126 lane it ends: "then paste the install line again: it
      switches to the GPU build (about 3 GB)" (M4-03: a lane change re-syncs);
    - allin1 absent, so the sections use the librosa fallback;
    - WSL memory under 11 GB ("allin1 is left out to save memory", M4-03);
    - `MemTotal` more than 10 % away from `.wslconfig`'s `memory` ("restart WSL: `wsl --shutdown`");
    - interop off;
    - `localhostForwarding` false without `networkingMode=mirrored` ("the page opens on WSL's own address");
    - Windows RAM under 16 GB.

### `songcharter doctor [--json PATH] [--quick]`

- Prints one line per item, then `doctor: OK` or `doctor: N problems`.
- Exit 0 when `ok`, 1 with problems, 2 for bad usage or a write error.
- `--quick` skips the matmul, the CUDA provider check and the allin1 probe.

### `engines/autochart.py`

- `cuda_library_path() -> list[str]`:
  - for each folder of the `nvidia` namespace package in this Python (`importlib.util.find_spec("nvidia")
    .submodule_search_locations`), its `cu13/lib` and `cudnn/lib` when they exist;
  - then `/usr/lib/wsl/lib` when it exists.
- `generate(..., device="cuda")` prepends those to `LD_LIBRARY_PATH` in the node child's environment only.
  - Never in songcharter's own process: torch loads its own copies.
  - The take key does not change (the library path is not an input of the chart).

### `pipeline.py`

1. **Fallbacks:** a `fallback(stage, frm, to, reason)` helper appends to `report["fallbacks"]` and to
   `ChartResult.fallbacks`, and warns with today's wording. It covers four cases:
   - `device` auto choosing the CPU (with `choose_device`'s reason; on a machine with no GPU at all, record it
     without a warning);
   - separation's fallback;
   - allin1 on the CPU;
   - a guitar take whose transcriber ran on the CPU.
2. **GPU memory:**
   - when the device is CUDA, `torch.cuda.empty_cache()` after the separation and after the drums;
   - per in-process stage, `torch_peak_vram_mb` (reset, then `max_memory_allocated`).
3. **The sampler:** a daemon thread started by `chart` and stopped in its `finally`.
   - Every 1 s: `memory()`. Every 2 s, when `nvidia-smi` exists: `memory.used`.
   - Per stage, it records `min_available_ram_mb`, `max_swap_used_mb` and `max_gpu_used_mb` (whole system, children
     included).
   - `chart(..., sampler=None)` in the tests.
4. **Takes:** `guitar_takes` is unchanged: 4 on CUDA, 1 on the CPU. In WSL the guitar's GPU device is `cuda`.

## Done means

[dev] In the dev container:

1. The suite passes (CLAUDE.md's command), with new tests:
   - **`wsl.py`, against stand-in `cmd.exe`, `reg.exe`, `chcp` and `wslpath` scripts on PATH:**
     - `windows_env("USERPROFILE")` returns `C:\Users\Jörg` from UTF-16LE output;
     - `shell_folder("Personal")` expands `%USERPROFILE%\OneDrive\Documents` from cp850 output and checks that it
       exists;
     - `wslconfig()` parses `memory=12GB`, `swap = 8192MB` and a missing file;
     - a missing `cmd.exe` gives None everywhere.
   - **`device.py`:**
     - `choose_device`'s four reasons;
     - `guitar_device`'s three;
     - the `notes` for a WSL memory of 11.5 GB with `.wslconfig` at 12 GB (matches), and of 7.8 GB with 12 GB
       configured (restart).
   - **`cuda_library_path`:** a fake `nvidia/cu13/lib` and `nvidia/cudnn/lib` under a temporary `site-packages`.
   - **`generate`:** the child's `LD_LIBRARY_PATH` holds them for `cuda` and not for `cpu`.
   - **`pipeline`:** the fallbacks record of a stand-in run; the sampler's keys in `pipeline.json` (with a stand-in
     sampler).
2. `songcharter doctor --json /dev/shm/m4-02/doctor.json`, with `SONGCHARTER_AUTOCHART` and the other components
   pointed at real installs (the brief gives the paths), exits 0:
   - `wsl` is null here;
   - `device.reason` is "no NVIDIA GPU found";
   - `guitar_device` is `cpu`.
3. The golden charts (as `eval/README.md` runs them, `EXPECT=none`) show no UNEXPECTED change.

[CI] Hook `20-device.sh` on `ubuntu-latest`:
- `pytest tests/test_wsl.py tests/test_device.py`;
- then `songcharter doctor --quick --json` with a fake `nvidia-smi` first on PATH (printing `NVIDIA GeForce RTX 4070,
  581.57, 12282, 8.9`). Assert:
  - `gpu.name` is parsed;
  - `device.chosen` is `cpu`, with "this install's torch has no CUDA (the cpu lane)".

[Hardware] M4-08 reads `doctor.json` on the 5070 and the 4070:
- `wsl` filled, with `memory_matches_config`;
- `gpu`;
- `device.chosen` cuda;
- `components.autochart_cuda.ok` true;
- `guitar_device` cuda;
- the per-stage samples.

## Depends on

Nothing. M4-05a's hook folder lands in the same wave.
