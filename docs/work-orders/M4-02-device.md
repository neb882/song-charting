# M4-02: device checks, `songcharter doctor`, and the guitar on WebGPU on Windows

**Branch:** `m4-02-device`, from `main`. **Wave 1**, beside M4-01. **Agent:** `sc-builder`, then `sc-reviewer` and
`sc-inspector`.

## Intent

The friend must always see where his chart runs and why: "GPU: RTX 4070 (12 GB)" or "CPU mode: <reason>" (DESIGN
4.3, 4.4). One module answers that, and `songcharter doctor` writes it to `doctor.json` for the bootstrap, the UI
and the diagnostics bundle. Two pipeline changes come with it:
- on Windows the guitar's GPU device must be `webgpu`, since onnxruntime-node has no CUDA there (M4-00, finding 1);
- GPU memory and host RAM per stage are recorded, so the hardware runs (M4-08) can be read.

## Scope

Creates or changes:
- `songcharter/device.py` (new);
- `songcharter/cli.py` (a `doctor` command);
- `songcharter/pipeline.py`: the guitar device, a fallbacks record, freeing torch's CUDA cache, the resource sampler;
- `tests/test_device.py` (new), `tests/test_pipeline.py`, `tests/test_cli*` as needed.

Must not touch:
- `pyproject.toml` or `uv.lock` (M4-01's);
- the engines' own modules;
- `cache.py`, beyond reading its constants;
- `docs/`.

Must not change any chart on Linux: every change below is Windows-only or record-only.

## Spec

### `songcharter/device.py`

Standard library only at import. torch, the engines and `assemble` are imported inside the functions that need them.

- `nvidia_smi() -> tuple[dict | None, str | None]`:
  - runs `nvidia-smi --query-gpu=name,driver_version,memory.total,compute_cap --format=csv,noheader,nounits`
    (timeout 15 s): from PATH, else `%SystemRoot%\System32\nvidia-smi.exe` on Windows;
  - parses the first line into `{"name", "driver", "vram_mb": int, "compute_cap": "8.9"}`;
  - on no executable, a non-zero exit or unparsable output: `(None, reason)`.
- `torch_report() -> dict`:
  - `{"version", "cuda": torch.version.cuda, "available": torch.cuda.is_available()}`;
  - `cuda_works`, `cuda_error`, from `separate.cuda_works()` (reuse it, do not copy it);
  - `arch_list`, `capability` (`"sm_89"`) and `capability_in_build`;
  - `matmul_ok`: a 512×512 matmul on CUDA when `cuda_works`;
  - `{"version": None, "error": ...}` when torch does not import.
- `choose_device(asked: str = "auto") -> tuple[str, str | None]`: the torch device `--device` means, and for every
  CPU outcome a sentence for a person:
  - "asked for the CPU";
  - "no NVIDIA GPU found";
  - "this install's torch has no CUDA (the cpu lane)";
  - "CUDA did not run on <GPU name>: <cuda_error>".

  The same rule as `Engines.device`, which then calls it, so the two never disagree.
- `guitar_device(device: str, platform: str = sys.platform) -> str`:
  - `"cpu"` when `device == "cpu"`;
  - `"webgpu"` on `win32`;
  - `"cuda"` elsewhere.

  Docstring: onnxruntime-node 1.27.0's Windows build has the CPU, DirectML and WebGPU providers only (its README;
  `install-metadata.js` lists no CUDA files for win32/x64), and autochart's engine supports cpu, cuda and webgpu.
- `default_threads() -> int`: `max(1, (os.cpu_count() or 2) - 1)`, for the UI (M4-04) to pass as `--threads` on the
  CPU. The CLI default does not change: that would move charts on Linux.
- `memory() -> dict | None`: `{"total_mb", "available_mb"}`, from `/proc/meminfo` on Linux and
  `GlobalMemoryStatusEx` (ctypes) on Windows; None elsewhere.
- `windows_state() -> dict | None` (Windows only, `winreg`, read-only, no admin; each value None when absent):
  - `smart_app_control`: from `HKLM\SYSTEM\CurrentControlSet\Control\CI\Policy` value
    `VerifiedAndReputablePolicyState`, 0 "off", 1 "on", 2 "evaluation" [untested: confirm in M4-08];
  - `long_paths_enabled`: `HKLM\SYSTEM\CurrentControlSet\Control\FileSystem` `LongPathsEnabled`;
  - `display_adapters`: the names from `Get-CimInstance Win32_VideoController` (powershell, 10 s timeout); empty on a
    timeout, which is what autochart reads as "software only".
- `path_check(root: Path, node: str | None) -> dict`, with root the cache root (`cache.cache_root()`):
  - computes, in Windows form, the longest paths a run makes (`cache.DEEPEST`, `NAME_MAX`, `KEY_HEX`,
    `SCRATCH_HEX`):
    - `work`: `<root>\work\<40 chars>-<16 hex>\` + `DEEPEST["work"]`;
    - `scratch`: `<root>\ac\<8 hex>\` + `DEEPEST["scratch"]`;
    - `staging`: `<root>\ac\<8 hex>\` + `DEEPEST["staging"]`;
  - `ok` is `work <= 259 and scratch <= 259`; `staging_over` is `staging > 259` (expected on every profile);
  - when `node` is given and this is Windows: `node_long_path_ok` and `node_error` (None elsewhere).
    - The test: a `node -e` script makes `<root>\ac\_pathcheck\` + nested folders to the staging length, writes a
      file there through a `.tmp` file and `renameSync`, as autochart's `writeVerifiedAtomic` does, then reads it
      back. Timeout 30 s.
    - Python then deletes the folder with `shutil.rmtree(cache.long_path(...))`.
- `components(full: bool) -> dict[str, dict]`, each entry `{"ok": bool, "detail": str}`:
  - `ffmpeg`: `audio.ffmpeg_exe()` and the first line of `-version`;
  - `node`: `SONGCHARTER_NODE` or PATH, and `--version`;
  - `scan_chart`: `assemble.find_scan_chart()`;
  - `autochart`: `engines.autochart.find_install()`, and `install_key`'s `engineVersion`;
  - `allin1`: `engines.sections.probe(python)` when a Python is configured, `full` only. Not ok means only that the
    librosa fallback will run;
  - `demucs`, `librosa`, `matplotlib`: import checks;
  - `webgpu` (Windows, `full`, autochart installed):
    - node creates an `onnxruntime-node` session with `executionProviders: ["webgpu"]` on the smallest `.onnx` file
      in `<autochart>/models/fretformer-v2/`, and prints the provider it got (timeout 120 s);
    - ok only when it got `webgpu`, and `display_adapters` names a non-Microsoft adapter.
- `report(full: bool = True) -> dict`, the doctor record, written as `doctor.json`:
  ```
  {"songcharter", "written" (UTC ISO), "platform", "python",
   "gpu" | null, "gpu_error", "torch", "device": {"chosen", "reason"}, "guitar_device", "guitar_reason",
   "cpu": {"logical", "threads_default"}, "ram": memory(), "disk": {"root", "free_mb"},
   "paths": path_check(...), "windows": windows_state(), "components": components(full),
   "problems": [str], "notes": [str], "ok": bool}
  ```
  - `problems` (each makes `ok` false): no ffmpeg; no scan-chart; no autochart; `paths.ok` false; free disk under
    6 GB on the cache root's drive.
  - `notes` (shown, not failing):
    - the CPU-mode reason;
    - the guitar on the CPU on Windows because WebGPU did not answer;
    - the allin1 probe failing ("sections use the librosa fallback");
    - Smart App Control "on" or "evaluation";
    - `long_paths_enabled` false while `staging_over` is true and `node_long_path_ok` is not true;
    - RAM under 16 GB ("a 7-minute song peaked at 10.1 GB on the CPU", DESIGN 5 M3).
  - `guitar_reason` explains a `guitar_device` of `cpu` (no GPU, or WebGPU did not answer).

### `songcharter doctor`

- `songcharter doctor [--json PATH] [--quick]`:
  - prints one line per item, then `doctor: OK` or `doctor: N problems`;
  - writes the record to PATH;
  - `--quick` is `report(full=False)`.
- Exit 0 when `ok`, 1 when there are problems, 2 for bad usage or an `OSError` writing PATH (CLI convention).

### `pipeline.py`

1. **The guitar device.**
   - Replace `gdev = "cuda" if device == "cuda" else "cpu"` with `gdev = device_mod.guitar_device(device)`.
   - `guitar_takes` gives `CUDA_TAKES` (4) on `"cuda"` and on `"webgpu"`. Its reason text says "on a GPU (cuda, or
     webgpu on Windows)", and the docstring notes that the 4-take evidence was measured on CUDA.
   - The per-take warning (`if gdev == "cuda" and used and any(v == "cpu" ...)`) becomes `gdev != "cpu"`.
   - The first-take-alone probe needs no change: it compares the transcriber's device with `gdev`.
2. **Fallbacks, recorded.**
   - A helper `fallback(stage, frm, to, reason)` inside `chart`:
     - appends `{"stage", "from", "to", "reason"}` to `report["fallbacks"]` (pipeline.json) and to a new
       `ChartResult.fallbacks: list[dict]`;
     - calls `warn` with the same text as today.
   - Use it at the four places a part moves to the CPU, keeping each warning's wording:
     - `device` auto choosing the CPU while torch has CUDA;
     - separation's `fallback`;
     - sections' allin1 CPU fallback, and "allin1 ran on the CPU";
     - a guitar take whose transcriber ran on the CPU, or moved for the first take.
   - Also record `device=auto` choosing the CPU for no GPU at all, using `choose_device`'s reason, with no warning on
     Linux CPU-only machines: record it, and leave the warning to the UI.
3. **GPU memory.**
   - After the separation stage and after the drums stage, when `device == "cuda"`: `torch.cuda.empty_cache()`.
   - At each stage start and end, when `device == "cuda"`: `torch.cuda.reset_peak_memory_stats()`, then
     `max_memory_allocated() / 2**20` into the stage's record as `torch_peak_vram_mb`.
4. **Resource sampler.** A daemon thread started by `chart` and stopped in its `finally`:
   - every 1 s, `device.memory()`;
   - every 2 s, when `nvidia-smi` exists, `nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits`;
   - per stage, `min_available_ram_mb` and `max_gpu_used_mb` (whole system, children included) go into that stage's
     record in `pipeline.json`.
   - Nothing reads wall time for a decision; the sampler only reports.
   - The tests' stand-in engines must not start `nvidia-smi`: a `sampler` argument on `chart`, None in the tests.

## Done means

[dev] In the dev container:

1. `python -m pytest -q -p no:cacheprovider --basetemp=/dev/shm/pt` (with `SONGCHARTER_SCAN_CHART` as in
   CLAUDE.md) passes: every test that passed on `main` still does, plus new ones that cover:
   - `guitar_device`: cpu, win32, linux;
   - `guitar_takes("webgpu")` is 4;
   - `choose_device`'s four reasons, with stand-ins for `nvidia_smi` and torch;
   - `path_check`'s numbers for a root of `C:\Users\` + 20 characters + `\AppData\Local\songcharter`: work 182, scratch
     256, staging 309, `ok` true. These are DESIGN 2's figures; derive them, do not hard-code them in the code;
   - `path_check` for a 26-character user name gives `ok` false;
   - the fallbacks record of a stand-in run where separation reports a fallback;
   - `doctor --json` writing the schema's keys.
2. `songcharter doctor --json /dev/shm/m4-02/doctor.json` exits 0 in the dev container. Point it at the real
   components as for a real chart run: `SONGCHARTER_AUTOCHART` (the scratchpad's autochart install),
   `SONGCHARTER_ALLIN1_PYTHON`, and `SONGCHARTER_SCAN_CHART` at a `tools/scan-chart` with its `node_modules`. The
   brief gives the paths.
   - It prints `CPU mode: no NVIDIA GPU found` and `guitar: cpu`.
   - The JSON has every key of the schema.
   - Without `SONGCHARTER_AUTOCHART`, it exits 1 and names autochart as the problem.
3. No chart changes on Linux:
   - `songcharter chart` on the synthetic clip gives a `notes.chart` byte-identical before and after this branch,
     with `--device cpu --threads 2` and the same work folder copied. The clip generator lands as
     `packaging/ci/make_clip.py` in M4-05; until then use the planning job's copy, `briefs/m4-assets/make_clip.py`
     in the director's scratchpad, whose full path the brief gives (`python make_clip.py clip.wav 30`);
   - once `eval/golden.py` exists, it shows no UNEXPECTED change.
4. `pipeline.json` of that run has `fallbacks` and, per stage, `min_available_ram_mb`. `max_gpu_used_mb` is null
   here (no `nvidia-smi`).

[CI-windows] M4-05 runs `songcharter doctor --json` on `windows-latest` after the bootstrap. Expected:
- exit 0;
- `device.chosen` cpu, with "no NVIDIA GPU found";
- `guitar_device` cpu;
- `windows.long_paths_enabled` read (true or false, not an error);
- `paths.node_long_path_ok` true.

[Windows HW] M4-08 checks, on the 5070 and the 4070:
- `gpu` filled, `device.chosen` cuda, `guitar_device` webgpu with `components.webgpu.ok` true;
- the per-stage GPU peaks are filled;
- `smart_app_control` matches what Windows Security shows.

## Depends on

Nothing. It defines the `doctor` command M4-03 calls and the `fallbacks` M4-04 forwards to the UI.
