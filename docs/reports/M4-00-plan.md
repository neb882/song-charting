# Report: the M4 work orders, re-planned for WSL2

Branch `m4-plan` in `/tmp/claude-0/-home-user/5307d417-c453-5e74-8f13-b43b2df06ab1/scratchpad/wt/m4-plan`, rebased
onto `main` (394dd1c: LICENSE, golden charts). Two commits:
- f9f9377: the native plan, kept so its orders stay in history;
- the WSL re-plan on top (hash at the end).

Not pushed.

## History of this job

1. **The native plan** (first commit): installer, bootstrap.ps1, WebGPU for the guitar on Windows.
2. **The advisor's 11 findings and the owner's two decisions** (pre-release delivery, MIT) were being folded in.
   - A WebGPU spike script (`packaging/spike/spike-webgpu.ps1`) was written. It passed PSScriptAnalyzer's 5.1
     compatibility rules (0 findings; the rules were checked to flag 7-only syntax), and a full run under pwsh 7.6.7 on
     Linux with a synthetic clip.
   - It was then dropped, uncommitted, when the route changed.
3. **The owner moved v0.1 to WSL2.** The friend's PC has Smart App Control on and 16–32 GB of RAM. This report
   covers the re-plan.

## Files

- **`docs/work-orders/` rewritten:**
  - M4-00-plan, M4-01-lanes, M4-02-device, M4-04-ui-server, M4-05-ci, M4-06-ui-results, M4-08-hardware, M4-99-later;
  - renamed: M4-03-bootstrap to **M4-03-install**, M4-07-installer to **M4-07-release**;
  - new: **M4-05a-ci-skeleton**.
- **`packaging/autochart/make_engine_list.py` and `engine-files.sha256`** (new): autochart b5a41e8's 346 files with
  SHA-256 and size, from the commit's blobs. They match a `git archive` zip of the commit [here]. M4-03's install
  checks GitHub's archive against the list.
- **`docs/PROGRESS.json`:**
  - the friend (Windows 11, SAC on, 16–32 GB);
  - M4 "planned for WSL2", with the three decisions, a new plan line and four risks;
  - `next` updated (the "GPU run on the 5070" item is folded into M4-08 A).

## The orders

| order | one line |
|---|---|
| M4-01 lanes | Linux lanes cpu/cu126/cu132 (cu132 + `nvidia-curand` 10.4.4.72 for autochart's CUDA provider), one Linux lock, allin1's locked project (all-in-one-infer 3.1.0 + torchaudio 2.11.1 on the lane's torch), a wheels-only check with one allowed pure sdist (antlr4 4.9.3) |
| M4-02 device | `wsl.py` (read-only interop: `cmd.exe /u` for Unicode, `reg.exe` + `chcp` for Documents, `.wslconfig`, Windows RAM, `curl.exe`, `explorer.exe`), `device.py` + `doctor` (WSL memory vs config, GPU, torch CUDA, autochart's CUDA provider loading, disk in WSL and on C:), pipeline fallbacks/empty_cache/RAM-swap-VRAM sampler, autochart's node gets the CUDA 13 library path |
| M4-05a ci-skeleton | ci.yml from wave 1: suite on ubuntu-latest, a windows-latest job for Windows-side files, hook folders `linux.d`/`windows.d`, the clip generator and gate/no-audio helpers |
| M4-03 install | `install.sh` (from the release, hash-checked, rerunnable, no sudo, progress, UV_HTTP_TIMEOUT=300/RETRIES=5, "run the same command again to continue"), `runtime` (Node 24.19.0, npm, autochart archive checked per file, the CUDA provider from NuGet checked by hash, models), launcher with pause-on-error from the shortcut, `.wslconfig` (Windows RAM − 4 GB, swap 8 GB, backup), a `.lnk` written to the Start menu, `songcharter uninstall` keeping downloads on No, `build.sh` |
| M4-04 ui-server | `songcharter ui` in WSL: guards, upload, one job as a process group, `--events` over SSE, cancel; Windows-side self-check with `curl.exe` and an instance token, next port or WSL's own address as fallback; browser via `explorer.exe` |
| M4-05 ci | end to end in `ubuntu:26.04` as a plain user: release assets, interrupted then resumed install, doctor (and with a fake nvidia-smi), the clip, guards, cancel at the first `take` with no node left, offline (network disconnected), uninstall No → reinstall downloads nothing, uninstall Yes |
| M4-06 ui-results | preview, zip, install into the Windows Songs folder under /mnt/c (saved → registry Documents incl. OneDrive), rename retried ~5 s on EACCES/EBUSY/EPERM, blocked message for security software or OneDrive, diagnostics (with `clonehero.json`, no audio) |
| M4-07 release | the friend's guide (checks, `wsl --install`, driver, the one hash-checked install line, start, chart, diagnostics, remove), NOTICE, guide rendering in build.sh, a hook running the guide's exact line; the `gh release create --prerelease` command |
| M4-08 hardware | A: the owner's 5070, a fresh `Ubuntu-26.04` distro with WSL memory 12 GB (and SAC on if agreed), A1–A12 and pass lines; B: the friend alone with the guide |
| M4-99 later | native Windows (the f9f9377 plan; blocked by SAC without signing), CUDA on native Windows, signing, highway, metronome, quick fixes, ×2/÷2, polish workspace, Preview in Clone Hero, weekly cu132 job, settings.ini, estimates, window-free start, updates, memory tuning |

## Waves

| wave | orders |
|---|---|
| 1 | M4-01, M4-02, M4-05a (disjoint: pyproject/locks; wsl/device/cli/pipeline/autochart; ci.yml/packaging/ci) |
| 2 | M4-03, M4-04 (packaging/linux, release, runtime, launch, wslsetup, winshortcut; ui, proc, cli, pipeline, autochart's take callback, pyproject package data) |
| 3 | M4-05, M4-06 (the e2e hook and ui_guards; ui, clonehero, diagnostics, cli) |
| 4 | M4-07 (guide, NOTICE, build.sh after M4-03, the release hook) |
| then | the full review workflow, then M4-08 |

- Each order lands its own CI hook files; only M4-05a edits ci.yml.
- M4-02 to M4-07 may push their branches to run CI.

## Research findings, with sources

### WSL [doc: MicrosoftDocs/WSL on GitHub, the source of learn.microsoft.com/windows/wsl; both were reachable]

- **Install** (`install.md`):
  - Windows 10 2004 (build 19041) or later, or Windows 11;
  - `wsl --install` in an administrator PowerShell, a restart, then a Linux user and password;
  - `--web-download` if the install hangs at 0 %.
- **Options** (`basic-commands.md`): `--install` takes `--distribution`, `--no-launch`, `--web-download` and
  `--location`; `--unregister` deletes a distro and all its data.
- **Errors** (`troubleshooting.md`): 0x80070003 or 0x80370102 mean virtualization is off in the BIOS (SLAT is
  needed), or the Virtual Machine Platform is missing.
- **`.wslconfig`** (`wsl-config.md`):
  - it lives in `%UserProfile%`;
  - `memory` defaults to 50 % of Windows' RAM, and `swap` to 25 % of it;
  - `localhostForwarding` defaults to true ("ports bound to wildcard or localhost in the WSL 2 VM should be
    connectable from the host via localhost:port");
  - `networkingMode` defaults to NAT (mirrored shares localhost);
  - `defaultVhdSize` is 1 TB, and `autoMemoryReclaim` defaults to `dropCache`;
  - changes apply after `wsl --shutdown`, or about 8 s after every window closes;
  - `[interop] enabled` and `appendWindowsPath` default to true, and C: is mounted at `/mnt/c`.
- **Disk** (`disk-space.md`): the ext4.vhdx grows to 1 TB "even if the amount of disk space on your actual Windows
  device is less". So the install checks both `$HOME` and `/mnt/c`.

### The friend's distro

- `wsl --install` now gives **Ubuntu 26.04.1 LTS**: "Ubuntu" is the default, pointing at
  `ubuntu-26.04.1-wsl-amd64.wsl` [doc: microsoft/WSL `distributions/DistributionInfo.json`]. Ubuntu-24.04 and
  Ubuntu-26.04 install as separately named distros.
- The 26.04.1 WSL image ships `curl`, `wget`, `git`, `ca-certificates`, `tar`, `xz-utils` and `sudo`, Python 3.14
  and glibc 2.43; no `unzip` [doc: releases.ubuntu.com/26.04.1, `ubuntu-26.04.1-wsl-amd64.manifest`]. The 24.04 image
  is similar (Python 3.12).
- Docker's `ubuntu:26.04` exists (updated 2026-10-29) [doc: Docker Hub API].

### NVIDIA on WSL

- "Users must not install any NVIDIA GPU Linux driver within WSL 2". The Windows driver is "stubbed inside the WSL 2
  as libcuda". Use `/usr/lib/wsl/lib/nvidia-smi` [doc: docs.nvidia.com/cuda/wsl-user-guide].

### autochart's CUDA provider on Linux

- onnxruntime-node 1.27.0's `libonnxruntime_providers_cuda.so` (251,623,184 bytes, SHA-256 0d3171e4…) needs
  `libcublasLt.so.13`, `libcublas.so.13`, `libcurand.so.10`, `libcufft.so.12`, `libcudart.so.13`, `libnvrtc.so.13`,
  `libcudnn.so.9` and `libcuda.so.1`: **CUDA 13** [here, `readelf -d`].
- It comes from NuGet `Microsoft.ML.OnnxRuntime.Gpu.Linux` 1.27.0, 211,908,180 bytes [here, HEAD]. The package's
  installer checks no hash [code: `install-utils.js`].
- The cu132 lane's lock pulls `nvidia-cublas` 13.4.1.3, `nvidia-cuda-runtime` and `nvidia-cuda-nvrtc` 13.2.86,
  `nvidia-cufft` 12.2.0.57 and `nvidia-cudnn-cu13` 9.26.0.51. Their libraries sit in `nvidia/cu13/lib` and
  `nvidia/cudnn/lib` [here, the wheels' file lists read by HTTP range].
- No curand in that lane: `nvidia-curand` 10.4.4.72 (62 MB, NVIDIA licence) adds `nvidia/cu13/lib/libcurand.so.10`
  [here].
- The cu126 lane is CUDA 12, so its guitar stays on the CPU. A CUDA 13 runtime needs a 580+ driver anyway
  [inference].

### Downloads (Linux, cp313)

- cpu 0.45 GB (torch 209 MB);
- cu126 3.9 GB (torch 869 MB + nvidia cu12 wheels);
- cu132 3.2 GB (torch 539 MB + cu13 wheels);
- plus the CUDA provider 0.21 GB, onnxruntime-node 271 MB unpacked, autochart's models 478 MB, the pipeline's models
  about 70 MB, Node 57 MB.

[here: the lock's wheel sizes, HEAD on the PyTorch index]

### Smart App Control

- **What it checks** [doc: textslashplain.com/2026/04/28/smart-app-control/]:
  - it "evaluates trust/signatures of all code (DLLs, scripts, etc) that is loaded by the Windows OS Loader and script
    engines", with cloud reputation for unsigned files;
  - it blocks risky file types from ShellExecute "if a file is from an untrusted origin" (Mark of the Web): `.bat`,
    `.cmd`, `.lnk`, `.ps1`, `.url`, `.vbs` and more;
  - it verifies MSIs and DLLs too, so a signed stub dropping unsigned code fails.
- **No exceptions:** no per-app exception and no "Run anyway" [doc: windowslatest.com 2025-12-16].
- **Reversible since April 2026:** KB5083769 (14 April 2026, Windows 11 25H2) lets SAC be turned on or off in Windows
  Security; a manual toggle never returns to Evaluation. The state is
  `HKLM\SYSTEM\CurrentControlSet\Control\CI\Policy\VerifiedAndReputablePolicyState` (0 off, 1 on, 2 evaluation), read
  only, never to be edited [doc: admin365.blog 2026-10-11].
- **Consequences for this plan** [inference]:
  - a `.lnk` written from WSL carries no Mark of the Web, and its target `wsl.exe` is Microsoft-signed;
  - interop calls only signed system tools;
  - no script file is written on Windows;
  - tested only in M4-08.

### The `.lnk` writer

pylnk3 is LGPL; LnkParse3 (a parser) is MIT [doc: PyPI]. So songcharter writes [MS-SHLLINK] itself, tests it with
LnkParse3, and on `windows-latest` with WScript.Shell and a real launch.

### Carried over from the native research

- torchaudio 2.11.1 with torch 2.15 passed allin1's real probe and a fold-0 run on Linux [here].
- The allin1 lock's only sdist, antlr4 4.9.3, builds to `py3-none-any` without a compiler [here].
- The lanes resolve wheels-only.
- autochart's engine needs `config/`, `shared/` and three `electron/` files, hence the whole-repo per-file check.
- The synthetic clip charts end to end on the CPU in 144 s (gate OK, scan-chart playable, 0 chart issues) [here].

## How the advisor's findings land under WSL

1. **WebGPU measured late:** moot. WSL gives autochart CUDA. The 4-take default is timed on CUDA in M4-08, with a rule.
2. **Smart App Control asked late:** answered (On), and it drove the route.
3. **Long paths, antivirus:**
   - MAX_PATH work is gone (ext4);
   - Windows rules apply only to `/mnt/c` names (`safe_name`, 40 characters);
   - antivirus timing only from M4-08 (risk 10).
4. **Tests on Windows:**
   - the whole suite runs on Linux, and WSL code is tested with stand-in interop tools;
   - the `.lnk` runs on `windows-latest`;
   - cancel happens at the first `take`, asserting no `node` is left (M4-05).
5. **Uninstall:** `songcharter uninstall` keeps the downloads on No, with `du`-measured figures in the question; the
   reinstall is checked to download nothing (M4-03, M4-05).
6. **First-run downloads:** uv's progress kept; size and estimate first; `UV_HTTP_TIMEOUT=300`,
   `UV_HTTP_RETRIES=5`; `fetch` prints every 50 MB and resumes; "run the same command again to continue"; CI kills
   and resumes an install.
7. **OneDrive:** Documents comes from the registry (follows OneDrive); renames are retried for about 5 s; the message
   covers security software and OneDrive; `under_onedrive` is in the UI and the diagnostics.
8. **Sequencing:** M4-05a in wave 1; hooks per order; pushes allowed.
9. **The installer:** Inno Setup is gone; the release is `install.sh` + tarball + SHA256SUMS + guide.
10. **The GPU path and odd paths:**
    - `doctor` with a fake `nvidia-smi` asserts the parsed name and the cpu-lane reason (M4-02, M4-05);
    - a Songs folder named `Jörg's Söngs`; `cmd.exe /u` for a non-ASCII user name;
    - `check_wheels` runs `--with packaging`.
11. **Errors at launch:** `--from-shortcut` pauses on any non-zero exit.

## DESIGN.md sections to change at the merge

- **§1:**
  - the Goal 2 column ("on the friend's Windows PC");
  - the pipeline's step 1 ("On Windows, always use the bundled ffmpeg": in WSL, imageio-ffmpeg's Linux build);
  - the run-time table (WSL rows);
  - the work folder's location in WSL (`~/.cache/songcharter`).
- **§2 work folder:** the Windows path-length text applies only to a native release; in WSL the limit applies only to
  the copy into `/mnt/c`.
- **§2.0:** the new modules, once built.
- **§4.1–4.7:**
  - 4.2: NOTICE, the NVIDIA wheel licence, the CUDA provider;
  - 4.3: becomes "the WSL install", with native moved under "later";
  - 4.4: the first-run flow (guide, one line, `.wslconfig`, shortcut);
  - 4.5: the server in WSL, the browser on Windows, the self-check, Clone Hero under `/mnt/c`;
  - 4.6: CI in `ubuntu:26.04`, plus the `windows-latest` `.lnk` job;
  - 4.7: the owner's test distro and `.wslconfig` at 12 GB.
- **§5 M4:** scope and acceptance on WSL (the RAM line becomes "inside the WSL memory, no stage killed"; the
  Windows-path lines go; add the shortcut, localhost and the reinstall).
- **§7 and §8.2:** the WSL unknowns (the CUDA peak RAM in 12 GB, SAC and the shortcut, forwarding).
- **§9:**
  - Q4 ("native Windows, decided") becomes "WSL2, decided 2026-11-03 because of Smart App Control";
  - Q10: signing moves to the native route;
  - Q11: cu126 kept, the guitar on the CPU there;
  - record the pre-release and MIT decisions.
- **§10:** the sources above.
- **§11:** a changes entry.

## Questions only the owner can answer

1. Turn Smart App Control on for the 5070 test, then off? It needs 25H2 with the April 2026 update, and may block
   your unsigned tools meanwhile.
2. Is the friend's Ubuntu only for songcharter? That decides whether the guide offers `wsl --unregister Ubuntu`.

Still open from before: delete `m4-workflow-push-probe` on GitHub.

## The owner's 5070 steps (M4-08 part A, in short)

1. `nvidia-smi` shows driver 580 or newer.
2. Back up `%UserProfile%\.wslconfig`, set `memory=12GB` and `swap=8GB`, then `wsl --shutdown`.
3. Optionally, Smart App Control on.
4. `wsl --install -d Ubuntu-26.04`, and make a user.
5. Paste the guide's install line (`install.sh --from <folder>` before the pre-release exists). Note the time, the
   size and the lane.
6. Start menu > songcharter: the page opens; the header says GPU and guitar on the GPU.
7. The test song with 1 take, then the default 4: total time and guitar-stage time.
8. Take Me Out with the defaults.
9. Cancel at "take 1": nothing left in `ps`.
10. Install into Clone Hero, Scan Songs, and play it.
11. Network off, then a new song.
12. Copy `settings.ini`'s song-folder lines.
13. Send the diagnostics zip.
14. `songcharter uninstall` (No), then reinstall: nothing downloaded.
15. `wsl --unregister Ubuntu-26.04`, restore `.wslconfig`, `wsl --shutdown`, and turn SAC off again.

## Not verified

- Nothing ran in WSL or on Windows during this re-plan. All WSL behaviour is [doc] or [inference] until M4-05 (the
  container) and M4-08 (the PCs). In particular:
  - the `.lnk` under SAC;
  - `cmd.exe /u` and `reg.exe` decoding;
  - `curl.exe` from interop for the self-check;
  - `wsl.exe -d … --cd ~ -e …`;
  - the provider loading with the lane's CUDA 13 libraries on a real GPU;
  - the CUDA peak RAM.
- The lane thresholds (580, 528) are DESIGN 4.3's, not re-checked.
- The provider's CUDA 13 dependency is read from the binary; it has run on the owner's 5070 before (the takes
  experiment) with whatever libraries that WSL had.
- The background rerun of the dropped spike test failed (exit 1, not investigated: the script was dropped).

## Commit

7b59cc7 on `m4-plan` (on top of f9f9377, the native plan, and main 394dd1c); not pushed. 16 files: the work orders, PROGRESS, `packaging/autochart/`.

## Round 3: the advisor's review of the WSL plan (12 findings, all taken in)

- **New: M4-00b `cuda13-spike`.** `packaging/spike/cuda13-provider.sh`, about 20 min in the owner's existing WSL.
  - It sets up uv 0.13.5 (release tarball + published sha256), a venv with torch 2.15.0+cu132 and nvidia-curand
    10.4.4.72, Node 24.19.0, and onnxruntime-node 1.27.0 by the repo's autochart lock (`npm ci --ignore-scripts`, then
    its installer run explicitly; the provider checked by hash).
  - It runs the transcriber encoder (`encoder_fp32.onnx`) on `["cuda"]` with `LD_LIBRARY_PATH` = `nvidia/cu13/lib`,
    `nvidia/cudnn/lib` and `/usr/lib/wsl/lib`, and reads ORT's own "Node placements" log.
  - It FAILs loudly on a load error or on zero CUDA nodes, and writes `cuda13-result.json` (copied to Windows'
    Downloads).
- **Tested here:**
  - the CPU path: PASS, 392 CPU nodes;
  - the failure path: banner FAIL with "libcublasLt.so.13: cannot open", exit 1;
  - the real cu132 venv: all seven CUDA 13 libraries found ("missing: nothing"); the provider loads past them and
    fails only at the driver's `libcuda.so.1`; torch CUDA 13.2; venv 5.3 GB.
  - Not testable: the PASS on a GPU, and the zero-CUDA-nodes branch.
- **npm 11.17** warns that onnxruntime-node's postinstall is "not yet covered by allowScripts" but runs it. The spike
  and M4-03 run the installer explicitly.
- **M4-00:**
  - wave 0 (the spike must pass before wave 1 ends) and the fallbacks if it fails;
  - the one-line `launch.main` coupling at the wave-2 merge;
  - the legacy 22.04 mapping;
  - SAC toggling unsettled;
  - the probe branch deleted;
  - question 2 settled (`wsl --unregister` offered with a warning).
- **M4-02:** `gpu.sh`'s comment fix; `wsl.documents` (raw, expanded, Linux path) in `doctor.json`; the cu126 note's
  re-run sentence.
- **M4-03:**
  - uv from the GitHub tarball;
  - `--windows-ram-gb` / `SONGCHARTER_WINDOWS_RAM_GB`;
  - rounding to the nearest GB;
  - the lane re-chosen on each run;
  - the shortcut as `cmd.exe /c "wsl.exe … || pause"`, overwritten on reinstall;
  - the `.lnk` hook passes on `Start-Process` creating `lnk-ok.txt`.
- **M4-05:** `docker exec` phases with the network cut between them; install-only containers for 24.04 (must pass)
  and 22.04 (reported).
- **M4-06:** `copytree(copy_function=shutil.copyfile)`; the Documents decoding in the diagnostics.
- **M4-07:** `wsl --update` first; chart first, play after; VPN off; `wsl --shutdown` on certificate errors; the lane
  re-run note; `--unregister` with a warning.
- **M4-08 part A:**
  - starts with no `.wslconfig`, the install writing the 16 GB one (`--windows-ram-gb 16`), with the restart message
    and `memory_matches_config` checked;
  - SAC optional and conditional;
  - added: closing the window mid-chart, a non-ASCII file dragged in, 409 → replace, the fallback address
    (`localhostForwarding=false`), reinstalling over the shortcut, and an Ubuntu-22.04 install-only run.
