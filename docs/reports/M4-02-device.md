# M4-02 (device) builder report

Branch `m4-02-device` from `main` 56b5591, in the worktree
`/tmp/claude-0/-home-user/5307d417-c453-5e74-8f13-b43b2df06ab1/scratchpad/wt/m4-02`. Pushed to `origin/m4-02-device` to run CI, as the order allows.

## Commits

On `m4-02-device`, from 56b5591:
- `a5d1cf9` M4-02: autochart's node child gets the CUDA 13 library path (engines/autochart.py, its tests, eval/gpu.sh's comment)
- `c1db8a0` M4-02: wsl.py, device.py and songcharter doctor (plus tests/test_wsl.py, tests/test_device.py, packaging/ci/linux.d/20-device.sh)
- `d15f562` M4-02: the pipeline records fallbacks, frees GPU memory and samples memory (pipeline.py, tests/test_pipeline.py)
- `d22c6a9` Merge main (2b8bc02: M4-05a's CI and M4-01's lanes) into m4-02-device, so that the 20-device hook runs in CI.
  It merged cleanly and changes nothing under songcharter/ or in my tests.
  - The golden gate ran on d15f562. The merge changes no chart code.
  - M4-01 set the precedent ("Merge main into m4-01-lanes").

**Pushed** (the order allows a push to run CI): `git push -u origin m4-02-device` created the branch. CI run
41713516959 (https://github.com/neb882/song-charting/actions/runs/41713516959): **success**.
- linux: 20:32:36 to 20:38:17 (5.7 min). CI tools: `78 passed`. The suite: `572 passed, 1 skipped in 239.86s`.
  Hooks: `10-lanes.sh ok in 15 s`, `20-device.sh ok in 5 s`.
- 20-device's log: `18 passed`; `GPU: NVIDIA GeForce RTX 4070 (12.0 GB), driver 581.57, compute capability 8.9`;
  `device: CPU mode: this install's torch has no CUDA (the cpu lane)`; `doctor exited 1` (no autochart engine in that
  job: a problem, as expected); `20-device: ok: ...`.
- windows: success, 0.6 min (no Windows hooks).

## What changed

### `songcharter/engines/autochart.py`
- `cuda_library_path()`: for each folder of this Python's `nvidia` namespace package (`importlib.util.find_spec`),
  its `cu13/lib` and `cudnn/lib` when they exist, then `/usr/lib/wsl/lib` (`WSL_LIB`) when it exists.
- `cuda_environment(env)`: `env` with those folders first on `LD_LIBRARY_PATH`. If there are none, `env` is returned unchanged.
- `generate(..., device="cuda")` uses it for the node child's environment only. The take key does not change. The
  docstring cites the spike that passed on the owner's 5070 as [here, 5070 spike: M4-00b]: 357 nodes on CUDA, using the same
  three folders in the same order.

### `songcharter/wsl.py` (new, standard library only)
`is_wsl`, `distro`, `interop_ok`, `windows_env` (`cmd.exe /d /u /c "echo %NAME%"`, UTF-16LE),
`to_linux` (`wslpath -u`), `oem_encoding` (the number from `chcp`'s line, so a translated line works too; cp437 by default), `registry_shell_folder` (the raw
value) + `expand` + `shell_folder` (the Linux path only if it exists), `onedrive_roots`, `parse_size`,
`parse_wslconfig`, `wslconfig`, `windows_build`, `windows_ram_bytes`, `windows_curl` (System32's curl.exe),
`open_url` (explorer.exe, exit code ignored). Each call runs with `cwd=/mnt/c` (when it exists) and a timeout
(10 s; PowerShell 30 s). A failure returns None, False or [], and nothing raises.
- I added `/d` to every cmd.exe call (it skips the registry's AutoRun commands, which could pollute the echoed output).
  The spec says `cmd.exe /u /c echo %NAME%`. The flag is a robustness detail.
- `registry_shell_folder` and `expand` are split out of `shell_folder` because doctor.json's `documents` needs the
  raw and the expanded values too.

### `songcharter/device.py` (new)
`nvidia_smi`, `gpu_used_mb`, `torch_report`, `choose` / `choose_device`, `guitar_device`, `autochart_cuda`,
`default_threads`, `memory`, `Sampler`, `components`, `memory_matches`, `findings`, `report`, `summary`.
- `choose_device` reasons are exactly the four sentences of the spec. A fifth, "torch is not installed", is
  reachable only from doctor when torch is absent. For "CUDA did not run on <name>: <error>":
  - the error is cuda_works' kernel error;
  - when torch has CUDA but `is_available()` is false on a GPU nvidia-smi sees (an old driver, say),
    it is `torch.cuda.init()`'s message;
  - the name comes from nvidia-smi, else torch, else "the GPU".
- `choose(asked)` returns a NamedTuple `(device, reason, error)`. `choose_device` is its first two fields.
  `Engines.device` calls `choose`, because the pipeline's warning keeps today's wording, which needs the raw error.
- `guitar_device(torch_device, autochart_ok, detail=None, *, torch_cuda=None)`: the two extra keywords carry the
  provider's detail and the lane, which the spec's reasons need. Order: not CUDA → "no GPU"; provider ok → cuda;
  torch CUDA 12.x → the cu126 sentence; not checked (`--quick`) → cuda (the pipeline tries CUDA and falls back by
  itself); otherwise "the CUDA provider did not load: <detail>".
- `autochart_cuda`:
  - runs `node -e <probe> -- <onnxruntime-node> <smallest .onnx>`, which creates one session with `["cuda"]` and
    ORT's verbose log, with `cuda_environment(os.environ)`;
  - parses ORT's own "placed on [XExecutionProvider]. Number of nodes: N" lines (the spike's method);
  - is ok when any node is on CUDA;
  - otherwise reports the "Failed to load library ... with error: <lib>" text, or the session error.
  - The smallest model is `beat_this_mel_fp32.onnx` (4.4 MB). Its graph has Conv, MatMul, Mul, Add, Sqrt and Log,
    all CUDA EP ops (I read the ops with a small protobuf reader), so a working provider places nodes on CUDA.
    That is not proven on a GPU.
- **Size units** (my reading, documented in the module docstring):
  - The report gives MB (2^20 bytes).
  - The limits (6 GB free, 8 and 11 GB of WSL memory, 16 GB of Windows RAM) are N × 10^9 bytes. That leaves room
    for what firmware and the kernel keep: a "16 GB" PC reports about 15.9 GiB, and WSL's memory=8GB shows about
    7.8 GiB.
  - With 2^30 units, the friend's 16 GB PC would get "Windows RAM under 16 GB", and the install's 8 GB floor would be
    a problem. The memory problem and notes apply only in WSL ("WSL memory").
- `report(full)` follows the spec's schema. `components` entries are `{"ok", ...}`, and `autochart_cuda` and
  `allin1` appear only with `full`. In `--quick` mode the allin1 note comes from whether an allin1 Python is
  configured at all.
- `Sampler`: a daemon thread.
  - It reads /proc/meminfo every 1 s and nvidia-smi's `memory.used` every 2 s, when nvidia-smi exists.
  - It also takes a memory sample as each stage begins and ends.
  - Per stage it keeps `min_available_ram_mb`, `max_swap_used_mb` and `max_gpu_used_mb`.
  - It lives in device.py rather than pipeline.py because it uses device.py's readers.

### `songcharter/cli.py`
`songcharter doctor [--json PATH] [--quick]`:
- prints the summary lines, then `doctor: OK` or `doctor: N problem(s)`;
- `--json` writes atomically (`.part`, then rename) and creates the parent folders;
- exit codes: 0 ok, 1 problems, 2 bad usage (argparse) or a write error, 3 a bug (traceback), 130 on Ctrl+C.

### `songcharter/pipeline.py`
- **Fallbacks.** `fallback(stage, frm, to, reason, *, warning="")` appends to `report["fallbacks"]`, which is the same
  list as `ChartResult.fallbacks`, and warns. The `warning` keyword keeps each case's old wording (None means
  recorded only). The four cases:
  - **device "auto" took the CPU.** Recorded with no warning when the reason is "no NVIDIA GPU found". Otherwise the
    warning is `CUDA does not run here (<error, else the reason>): the models run on the CPU`, which is today's text
    for the CUDA-error case.
  - **separation's fallback**: `separation: <text>`.
  - **allin1 on the CPU**: `sections: <allin1's fallback>`, or `sections: allin1 ran on the CPU (its Python has no
    working CUDA)`.
    - **Judgment call:** this now fires when the *resolved* device is CUDA, so also for "auto" that found CUDA, not
      only for `--device cuda`.
    - The reason: allin1 on the CPU while torch runs on CUDA is exactly the fallback the friend should see.
  - **a guitar take on the CPU**: the probe take whose transcriber moved (old wording), and a take whose transcriber
    ran on the CPU (`guitar take <seed>: autochart ran on the CPU (...)`). A take whose other stages alone ran on the
    CPU is still warned about as before, but not recorded.
- **`pipeline.json`** gains:
  - a top-level `device` entry: `{"asked", "chosen", "reason"}`;
  - per stage, `torch_peak_vram_mb`: None off CUDA, and absent for the guitar stage, which runs in a child process;
  - per stage, the three sampler keys when a sampler runs.
- **GPU memory.** New `Engines.free_gpu`, `vram_reset` and `vram_peak_mb` (no-ops off CUDA). `free_gpu` runs after
  the separation and after the drums.
- **`chart(..., sampler=D.Sampler)`** takes a factory: None means no sampler, and the tests pass a stand-in. The thread
  starts at the top of the try and stops in the finally.
- `guitar_takes` is unchanged.

### Tests
- `tests/test_wsl.py` (new): stand-in `cmd.exe`, `reg.exe`, `wslpath`, `powershell.exe`, `explorer.exe` and System32
  `curl.exe` (Python scripts on a PATH that holds only them; C:\\ is a temporary folder). The cases:
  - Jörg's profile path from UTF-16LE output;
  - `%USERPROFILE%\OneDrive\Documents` from cp850 output, expanded and checked to exist;
  - a cp850 `Bureau privé`;
  - a translated `chcp` line, and a code page Python has no codec for;
  - `memory=12GB`, `swap = 8192MB`, a UTF-16 `.wslconfig`, a missing file and a broken one;
  - Windows RAM, and its 2 × MemTotal fallback;
  - `open_url` and `windows_curl`;
  - no cmd.exe at all, which gives None everywhere.
- `tests/test_device.py` (new):
  - `choose_device`'s four reasons, plus the old-driver case and the real torch;
  - `guitar_device`'s three reasons, plus the quick and cu126 edge cases;
  - nvidia-smi parsing: the CI line, WSL's path, a failure, an empty answer;
  - the provider check against stand-in node output: ok, a load error, CPU only, a timeout, no model;
  - meminfo, threads and the Sampler;
  - the notes for 11.5 GB of WSL memory against a 12 GB `.wslconfig` (it matches: nothing to say) and 7.8 GB against
    12 GB (the restart note, plus the under-11 note);
  - every problem and note;
  - `report()` on this machine, quick and full;
  - the doctor command's exit codes 0, 1, 2 and 3.
- `tests/test_engines_autochart.py`:
  - `cuda_library_path` with a fake `nvidia/cu13/lib`, `nvidia/cudnn/lib` and `cusparselt` under a temporary
    site-packages;
  - the child's `LD_LIBRARY_PATH` for cuda (first, the old value kept) and not for cpu;
  - the take key unchanged.
- `tests/test_pipeline.py`:
  - the stand-ins return the 3-tuple and record their GPU calls;
  - the module fixture passes `sampler=None`;
  - new checks of `device` and `fallbacks` in the default run;
  - the CUDA-error test checks the fallback record;
  - the real `Engines.device` test is updated;
  - `test_every_fallback_is_recorded_and_warned`: every case, with the `free_gpu` order and the per-stage peaks;
  - `test_the_sampler_records_each_stage`: the keys in pipeline.json, and the stop on a failing run;
  - the CLI rerun test checks the real sampler's keys.

### `packaging/ci/linux.d/20-device.sh` (new)
1. Runs `pytest tests/test_wsl.py tests/test_device.py`.
2. Runs `songcharter doctor --quick --json $CI_ART/doctor-fake-gpu.json` with a stand-in nvidia-smi first on PATH,
   which prints `NVIDIA GeForce RTX 4070, 581.57, 12282, 8.9`.
3. Asserts the parsed `gpu`, and `device == {"chosen": "cpu", "reason": "this install's torch has no CUDA (the cpu lane)"}`.

doctor may exit 1 there: the CI job has no autochart engine, which is a problem. Exit 2 or 3 fails the hook.

### `eval/gpu.sh`
The comment only (after line 26): the CUDA 12 path predates the finding that the provider of onnxruntime-node 1.27.0
needs CUDA 13. It points to M4-00b and to `cuda_library_path`.

## Checks

Environment: Python `scratchpad/venv/bin/python` (3.13.18, torch 2.15.0+cu132, no GPU); the golden variables as the
brief gives them (`SONGCHARTER_ALLIN1_PYTHON` = research/timing/venv2, the one the baseline's kept folders used, as
their engine.json says). The evidence is copied to `/tmp/claude-0/-home-user/5307d417-c453-5e74-8f13-b43b2df06ab1/scratchpad/m4-02probe/golden-evidence/` (logs, both summaries, report.md, doctor.json, the suite's output; no audio).

### 1. The full suite (CLAUDE.md's command)
`SONGCHARTER_SCAN_CHART=/home/user/song-charting/tools/scan-chart/scan.cjs <venv python> -m pytest -q -p no:cacheprovider --basetemp=/dev/shm/pt_m4_02`
(with OMP/MKL/OPENBLAS at 2 threads), at d15f562:
```
531 passed, 3 skipped in 601.30s (0:10:01)
exit 0
```
The 3 skips are of the kinds the earlier inspected suite had (500 passed, 3 skipped): scan-chart's npm-install
tests and the opt-in allin1 run. On the merged tree (d22c6a9): `tests/test_wsl.py tests/test_device.py
tests/test_engines_autochart.py packaging/ci/test_ci.py` gave `83 passed, 21 skipped in 7.64s`.

**Breaking the code:** 35 mutations, each run against its tests. Every one failed a test (35 CAUGHT, 0 MISSED):
- **wsl.py (6):** /u dropped; reg.exe decoded as UTF-8; MB taken as 10^6 bytes; shell_folder not checking that the
  folder exists; the 2×MemTotal fallback even with memory set; open_url reporting False.
- **device.py (9):** NO_GPU and the cpu lane swapped; the cu126 branch removed; MATCH 0.5; the mirrored exemption
  dropped; ok on any provider; the sampler keeping a max instead of a min; no GPU samples; the limits in 2^30 bytes;
  the no-GPU shortcut removed.
- **cli.py (1):** doctor always exiting 0.
- **autochart.py (4):** no cudnn/lib; the path for cpu takes too; the old LD_LIBRARY_PATH dropped; no WSL lib.
- **pipeline.py (9):** no free_gpu after the drums; the device fallback never warned; warned with no GPU too; the
  allin1 check only for --device cuda; the sampler not stopped in the finally; the take fallback dropped; the guitar
  given a VRAM peak; the separation not recorded; the sampler's stage keys dropped.

### 2. `songcharter doctor --json /dev/shm/m4-02/doctor.json` with real installs
`SONGCHARTER_AUTOCHART`, `SONGCHARTER_ALLIN1_PYTHON` and `SONGCHARTER_SCAN_CHART` as above. Run twice: at the start,
and at d15f562 after the golden runs. The second run:
```
exit 0
... autochart: ok, 2026.06.16-cross-platform-runtime (.../eval/tools/autochart)
autochart's CUDA provider: does not load: libcurand.so.10: cannot open shared object file: No such file or directory
allin1: ok, all-in-one-infer 3.1.0, CUDA does not run (.../research/timing/venv2/bin/python)
...
note: CPU mode: no NVIDIA GPU found
note: the guitar runs on the CPU: no GPU
doctor: OK
wsl None | device {'chosen': 'cpu', 'reason': 'no NVIDIA GPU found'} | guitar cpu no GPU | ok True
```
`wsl` is null, `device.reason` is "no NVIDIA GPU found" and `guitar_device` is `cpu`, as the order asks. The provider
check really ran node here: the dev venv has no nvidia-curand, so the provider stops at libcurand.so.10, which is the
loader error the spike predicted.

### 3. The golden charts (CLAUDE.md's release gate, `--rerun guitar` on both sides because engines/autochart.py changed)
Old: `git worktree add --detach /dev/shm/m4-02/golden-old 56b5591` (a private path, not /dev/shm/golden-old, because
three builders share the machine). Outputs under /dev/shm/m4-02/golden/. Script: `scratchpad/m4-02probe/golden_side.sh`.
```
python -m eval.golden run --code /dev/shm/m4-02/golden-old --out /dev/shm/m4-02/golden/old --threads 2 --rerun guitar   -> exit 0 (3809 s)
python -m eval.golden run --out /dev/shm/m4-02/golden/new --threads 2 --rerun guitar                                    -> exit 0 (2858 s; code d15f562, clean)
python -m eval.golden diff /dev/shm/m4-02/golden/old /dev/shm/m4-02/golden/new --expect none                            -> exit 0
golden diff: no UNEXPECTED change; report: /dev/shm/m4-02/golden/new/report.md
```
- From report.md: "Parts changed as expected: 0. Every song's results (hashes, counts, scores) identical: yes."
- Engines rerun: guitar on 7 songs on both sides. Kept folders made by 77b2afd; none were made cold.
- Pooled Expert F1@50: guitar 0.8527, bass 0.8247, drums 0.9617; beat F1 0.8755, all +0.0000.
- I also compared the new summary's per-part track hashes with the baseline `golden/base/summary.json` (77b2afd): they
  are identical for all 7 songs, so the guitar reruns reproduced the kept takes.

**Runs that did not count:**
- **The first old run was stopped:** two songs failed.
  - autochart's engine was OOM-killed (memory cgroup, anon-rss 4.5 GB and 4.3 GB) while my test suite (3 GB) and M4-01's (2.4 GB) ran at the same time.
  - After that I ran nothing heavy beside the golden runs, and ran them one after the other.
- **The first new run was stopped after All the Small Things failed.**
  - That song's engine was OOM-killed with anon-rss **12.8 GB**, during the transcription's decode loop.
  - In the rerun the same song peaked at 4.2 GB, and the old run passed it. That is a memory spike I cannot explain
    (same seed, CPU, same install).
  - Across the counted new run, an RSS watcher every 2 s (rss.log) saw the engine peak at 5.7 GB, on test_song.
  - **Worth a line in M4-08's memory risk:** a single CPU guitar take reached 12.8 GB once. It may not reproduce.
- The killed runs' logs are kept as new.oom1.log and new.oom1.atst.log.

**Clean-up:**
- /dev/shm/m4-02/golden and the golden-old worktree were deleted.
- The killed runs' folders in `golden/work/.runs/` were cleared by golden itself at the next start. `.runs/` is empty
  now, and no kept folder was written.
- /dev/shm basetemps were deleted. My disk use at the end: about 0.2 MB of evidence.

### 4. The CI hook, locally
`CI_PY=/dev/shm/m4-01/env/bin/python` (M4-01's cpu-lane env, torch 2.15.0+cpu, read-only with PYTHONDONTWRITEBYTECODE),
`CI_TMP` and `CI_ART` under /dev/shm, `bash -euo pipefail packaging/ci/linux.d/20-device.sh`:
```
18 passed in 4.05s
GPU: NVIDIA GeForce RTX 4070 (12.0 GB), driver 581.57, compute capability 8.9
torch: 2.15.0+cpu, no CUDA (a CPU build)
device: CPU mode: this install's torch has no CUDA (the cpu lane)
doctor: 2 problems          (scan-chart and autochart are absent in a bare worktree, as in that CI job)
doctor exited 1
20-device: ok: NVIDIA GeForce RTX 4070; device cpu: this install's torch has no CUDA (the cpu lane)
hook exit 0
```
The hook follows main's linux.d/README.txt contract: an NN-name.sh file run from the repository root; it uses CI_PY,
CI_TMP and CI_ART, and writes only doctor JSON to CI_ART.

## Doc changes for the director to fold in (the order forbids `docs/`)

- **DESIGN 2.0 (code status):**
  - new rows for `wsl.py` and `device.py`, with the contents above;
  - `pipeline.py`'s row: the `device` record, `fallbacks`, the GPU memory calls and `torch_peak_vram_mb`, the sampler's
    per-stage keys;
  - `cli.py`'s row: `doctor`;
  - `engines/autochart.py`: `cuda_library_path`.
- **DESIGN line 191**, "Log peak VRAM per stage in doctor.json and in the UI": peak VRAM is now in `pipeline.json` per
  stage. doctor.json holds the machine, not a run.
- **PROGRESS:** M4-02 built on `m4-02-device`. Candidates for `deferred`:
  - doctor does not count a missing torch or demucs as a problem (the spec's list), although `chart` refuses to run
    without them;
  - the guitar reason is "no GPU" on the cpu lane even when nvidia-smi sees a GPU (the spec's wording);
  - the onnxruntime-node CUDA check on the smallest model is unproven on a GPU (M4-08 reads it).

## Not done, or uncertain

- **[CI]:** done. Run 41713516959 is green, and its 20-device hook passed with the asserts the order lists.
- **[Hardware]:** not done (M4-08). Three things are unproven on a GPU:
  - `autochart_cuda` on the smallest model (`beat_this_mel_fp32.onnx`), though its graph has only CUDA-EP ops;
  - `torch_peak_vram_mb`;
  - the sampler's `max_gpu_used_mb`.

  The torch/CUDA code paths are covered by stand-ins only.
- **WSL:** nothing in wsl.py has run on real Windows. These are untested:
  - interop's argument quoting for `cmd.exe /d /u /c "echo %NAME%"` (the same shape as eval/README.md's
    `cmd.exe /c 'echo %USERPROFILE%'`, which is known to work);
  - reg.exe's output in a real OEM code page;
  - PowerShell under Smart App Control.
- **Judgment calls**, beyond the letter of the spec:
  - the size units (10^9-byte limits);
  - `choose()`'s 3-tuple, with `Engines.device` returning three values;
  - `guitar_device`'s extra keywords, and its "not checked → cuda" for --quick;
  - the allin1-on-CPU fallback also for "auto" that found CUDA;
  - `/d` on cmd.exe;
  - the fifth reason, "torch is not installed";
  - the stage key `torch_peak_vram_mb`, absent for the guitar.
- **Not in the spec's problem list:** a missing torch or demucs is not a doctor problem. `chart` refuses to run without
  them anyway. Flagged for the director.
- **The OOM spike** described under check 3 (12.8 GB on All the Small Things once).

## Review fixes (R1, R2, R3), after the first report

### Commits (pushed)
- `fd3c23b` **R2:** `Sampler._sample` notes the stage and a generation counter under the lock before its reads, and
  drops a sample whose stage ended meanwhile. The generation goes up by one at each begin and each end.
- `82ab27a` **R3:** `.wslconfig` values are read git-config style. A trailing `#` or `;` comment outside quotes goes,
  and so do the quotes around the value. A BOM left by a decoder is ignored.
  - New `update_wslconfig(text, values)` for M4-03, so an update never writes a second `memory=` line:
    - the first `[wsl2]` line that sets a key, whatever its case, quotes or comment, is replaced, and later ones are dropped;
    - a missing key goes after `[wsl2]`'s last line, and `[wsl2]` is added when there is none;
    - every other line and the line ends are kept (CRLF for a new file).
- `69f1cd4` **R1:** `choose()` and `report()` pass nvidia-smi's error to `_decide`. When nvidia-smi is there but fails
  (anything but "not found" or "listed no GPU"), the reason is "nvidia-smi failed, so CUDA cannot run: <error>", on
  either lane.
  - The pipeline then warns `CUDA does not run here (<error>): the models run on the CPU` and records the reason.
  - doctor's device line and note show the same reason.

### Tests, each failing without its fix
- **R2:** `test_a_slow_sample_is_not_credited_to_the_next_stage` holds a GPU read across the stage change, for a next
  stage of another name and of the same name. Without the fix, drums got 9000 instead of 500. Removing either half of
  the fix fails it.
- **R3:**
  - `test_wslconfig_values_with_inline_comments_and_quotes` covers CRLF, a UTF-8 BOM, `Memory = 12GB # ...`,
    `"8GB" ; ...`, `'false'`, `#` inside quotes, `12GB;8GB` and an empty value.
  - `test_an_update_never_writes_a_second_memory_line` covers: a quoted, commented key plus a duplicate; a key in
    another section left alone; a second update changing nothing; an empty file; LF without a trailing newline.
  - Removing the dedupe, the comment cut or the quote strip each fails a test.
- **R1:**
  - `test_an_nvidia_smi_that_fails_is_a_gpu_out_of_reach` uses a stand-in nvidia-smi. Exit 255 "GPU access blocked"
    and a timeout give the failure reason on both lanes; a missing nvidia-smi, or one that lists no GPU, still gives
    "no NVIDIA GPU found".
  - `test_doctor_gives_the_same_reason` covers report(), the note and summary().
  - `test_a_failing_nvidia_smi_is_warned_about` (pipeline, the real `Engines.device`): the warning and the
    pipeline.json reason when nvidia-smi fails; "no NVIDIA GPU found" with no warning when there is none.
  - Mutations of the `_decide` branch, of `choose()` and of `report()` each fail a test. The report() one showed
    "MISSED" once in my runner: a stale .pyc from an earlier same-size mutation within the same second. By hand it fails.

### Checks
- Full suite at 69f1cd4: `576 passed, 3 skipped in 472.08s (0:07:52)`, exit 0.
- CI run 41718987663 (https://github.com/neb882/song-charting/actions/runs/41718987663): **success**.
  - linux: the suite `578 passed, 1 skipped`; `20-device.sh ok in 5 s` (23 tests); all 2 Linux hooks passed.
  - windows: success.
- The golden charts were not rerun for the review fixes. They change no chart path: the sampler's bookkeeping,
  `.wslconfig` parsing, and the device reason for an nvidia-smi that fails (golden runs with `--device cpu`, which
  never asks nvidia-smi).

### For M4-03 (report only)
The install picks the lane from nvidia-smi on every run, so a rerun while GPU passthrough is broken would quietly switch
the friend to the cpu lane. The install should refuse to downgrade a cu132 or cu126 lane to cpu on an nvidia-smi that
fails (as opposed to a missing one), and say why. `device.SMI_MISSING` and `SMI_NO_GPU` are the two answers that mean
no GPU. M4-03 should also write `.wslconfig` through `wsl.update_wslconfig`.

### For M4-08 (report only)
The reviewer traced the 12.8 GB autochart spike to a plausible cause:
- on the CPU, the decode loop never disposes the past K/V tensors (about 77 MB a step at 1,914 tokens), leaving them to
  V8's garbage collector, which a busy CPU can starve;
- sessionLoader.cjs sets no intraOpNumThreads, so `--threads` does not reach onnxruntime.

To measure: the node engine's own VmRSS and VmHWM every second from /proc/<pid>/status, with `NODE_OPTIONS=--trace-gc`,
over at least 5 runs, idle and under load.
