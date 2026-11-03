# M4 plan: songcharter v0.1 for the friend, on WSL2

*Rewritten 2026-11-03 on branch `m4-plan`, after the owner moved v0.1 from native Windows to WSL2. The native plan's
orders are kept in this branch's history (commit f9f9377); its findings are in the appendix. Evidence tags follow
DESIGN.md: [here] measured in this dev container, [doc] read from documentation or a package, [code] read from this
repository, [inference], [untested], [decision] a choice made here.*

## 1. Decisions and facts this plan starts from

| | what | from |
|---|---|---|
| route | v0.1 runs in WSL2 on the friend's Windows PC, not natively | the owner, 2026-11-03 |
| delivery | a GitHub pre-release on neb882/song-charting | the owner |
| licence | MIT for songcharter's own code (LICENSE on `main`, 12ebf10); NOTICE lists the third parties | the owner |
| the friend's PC | Windows 11 with Smart App Control **on**; RTX 4070, 12 GB; 16–32 GB of RAM (plan for 16) | the friend, through the owner |

**Why WSL2.**
- **Smart App Control.** It "evaluates trust/signatures of all code (DLLs, scripts, etc) that is loaded by the
  Windows OS Loader and script engines". An unsigned file loads only when Microsoft's cloud knows it. There is no
  per-app exception [doc: textslashplain.com/2026/04/28/smart-app-control/; windowslatest.com, 2025-12-16].
- A native install loads hundreds of unsigned files (uv's CPython, torch's DLLs, numpy's and scipy's compiled
  modules); signing our installer would not cover them.
- Linux programs in WSL2 run in a Linux VM and never pass the Windows loader.
- WSL2 also gives autochart's engine CUDA back (onnxruntime-node's Linux build has it; its Windows build does not:
  appendix).
- And it reuses the Linux build that has run end to end, including on the owner's 5070 under WSL (`eval/gpu.sh`).

## 2. What v0.1 is

The friend can:
1. set up WSL with a short guide, then install songcharter with one line pasted into Ubuntu;
2. start it from a Start-menu shortcut (or by typing `songcharter` in Ubuntu);
3. drop a song file into the page that opens in his Windows browser;
4. keep the defaults or change the options the command line has;
5. watch one line per stage, with cancel, and every CPU fallback shown;
6. look at the static preview;
7. click once to put the chart into his Clone Hero Songs folder on Windows (or save a zip);
8. send a diagnostics zip with no audio when something goes wrong.

**Under the hood:**
- uv's Python and one torch lane (cu132, cu126 or cpu);
- allin1's own environment;
- Node 24, scan-chart, autochart's engine and models, and onnxruntime-node's CUDA provider;
- `doctor`;
- a `.wslconfig` that gives WSL enough memory.

CI runs the install from scratch in an Ubuntu 26.04 container. Everything in M4-99 waits for v0.2.

## 3. Findings that shape the plan

1. **`wsl --install` now installs Ubuntu 26.04.1 LTS.** Microsoft's distribution list marks "Ubuntu" as the
   default and points it at `ubuntu-26.04.1-wsl-amd64.wsl` [doc: github.com/microsoft/WSL
   `distributions/DistributionInfo.json`].
   - That image ships `curl`, `wget`, `git`, `tar`, `xz-utils`, `ca-certificates` and `sudo`, Python 3.14, and
     glibc 2.43 [doc: releases.ubuntu.com/26.04.1, `ubuntu-26.04.1-wsl-amd64.manifest`].
   - So the install needs no `apt`: uv brings Python 3.13, and the manylinux_2_28 wheels run on glibc 2.43.
   - CI uses Docker's `ubuntu:26.04` (it exists [doc: Docker Hub]).
2. **WSL's facts** [doc: MicrosoftDocs/WSL on GitHub, the source of learn.microsoft.com/windows/wsl, both
   reachable from here]:
   - **Install:** Windows 10 2004 (build 19041) or later, or Windows 11; `wsl --install` in an administrator
     PowerShell, then a restart, then a Linux user and password. Errors 0x80070003 or 0x80370102 mean
     virtualization is off in the BIOS, or the Virtual Machine Platform is missing (`install.md`,
     `troubleshooting.md`).
   - **`.wslconfig`:** lives in `%UserProfile%`. `memory` defaults to 50 % of Windows' RAM, so 8 GB on a 16 GB PC;
     `swap` to 25 % of it. Changes apply after `wsl --shutdown`, or about 8 s after every distro window closes
     (`wsl-config.md`).
   - **The browser's route:** `localhostForwarding` defaults to true: "ports bound to wildcard or localhost in the
     WSL 2 VM should be connectable from the host via localhost:port". In mirrored networking mode, localhost is
     shared (`wsl-config.md`, `networking.md`).
   - **Disk:** the distro lives in an `ext4.vhdx` that grows to a 1 TB maximum "even if the amount of disk space on
     your actual Windows device is less", so free space must be checked on the Windows drive too (`disk-space.md`).
   - **Interop:** `[interop] enabled` and `appendWindowsPath` default to true; drives are mounted at `/mnt/c`.
3. **NVIDIA on WSL:** the Windows driver provides CUDA inside WSL as a stubbed `libcuda`; "users must not install any
   NVIDIA GPU Linux driver within WSL 2"; `nvidia-smi` is `/usr/lib/wsl/lib/nvidia-smi` [doc:
   docs.nvidia.com/cuda/wsl-user-guide].
4. **autochart on CUDA under WSL reuses torch's own libraries.**
   - onnxruntime-node 1.27.0's Linux CUDA provider (`libonnxruntime_providers_cuda.so`, from NuGet
     `Microsoft.ML.OnnxRuntime.Gpu.Linux` 1.27.0, 212 MB) needs `libcublas(Lt).so.13`, `libcudart.so.13`,
     `libnvrtc.so.13`, `libcufft.so.12`, `libcurand.so.10`, `libcudnn.so.9` and `libcuda.so.1`: CUDA 13, not 12
     [here, `readelf -d`].
   - The cu132 lane's wheels hold all of them in `site-packages/nvidia/cu13/lib` and `nvidia/cudnn/lib`, except
     curand. `nvidia-curand` 10.4.4.72 (62 MB) adds `nvidia/cu13/lib/libcurand.so.10` [here, the wheels' file
     lists].
   - So the cu132 lane plus that wheel runs the guitar on CUDA, with the node child's `LD_LIBRARY_PATH` pointing
     there. No separate cuDNN environment is needed.
   - On cu126 (a driver under 580), the CUDA 13 provider cannot load: there the guitar runs on the CPU, and
     `doctor` says to update the driver.
5. **Downloads, Linux** [here: the lock's wheel sizes, and HEAD on the PyTorch index]:
   - cpu lane about 0.45 GB, cu126 about 3.9 GB, cu132 about 3.2 GB;
   - plus the CUDA provider (0.21 GB, CUDA lanes), onnxruntime-node (271 MB unpacked), autochart's models (478 MB),
     the pipeline's models (about 70 MB) and Node (57 MB).
6. **Smart App Control on the Windows side.**
   - SAC blocks a list of risky file types from ShellExecute "if a file is from an untrusted origin" (Mark of the
     Web). `.lnk`, `.bat`, `.cmd`, `.ps1` and `.url` are on that list [doc: textslashplain.com, 2026-04-28].
   - A Start-menu `.lnk` that songcharter writes from WSL carries no Mark of the Web, and its target `wsl.exe` is
     Microsoft-signed, so it should run [inference; tested in M4-08].
   - No script file is written on Windows. Interop calls only signed system tools (`cmd.exe`, `reg.exe`,
     `explorer.exe`, `curl.exe`), and PowerShell for one read-only query, with a fallback.
   - Since KB5083769 (April 2026, Windows 11 25H2), SAC can be turned on and off in Windows Security without
     reinstalling; a manual toggle never returns it to Evaluation [doc: admin365.blog, 2026-10-11]. So the owner can
     mimic the friend's SAC for the test (question 1, section 8).
7. **Memory.** On the CPU, the test song peaked at 10.1 GB for the process tree, 7.8 GB of it allin1's runner (DESIGN
   5, M3). With CUDA, allin1's ensemble runs on the GPU: the host peak is unmeasured.
   - With the default 50 %, a 16 GB PC gives WSL 8 GB: too little.
   - So the install writes `memory` = Windows' RAM − 4 GB (12 GB on 16) and `swap=8GB`.
   - M4-08 measures the CUDA peak inside exactly 12 GB.
8. **The `.lnk` writer.** pylnk3 is LGPL; LnkParse3 (a parser) is MIT [doc: PyPI]. songcharter writes the small
   [MS-SHLLINK] structure itself and tests it with LnkParse3, and with Windows itself on `windows-latest`.
9. **Pushes from sessions.** This session pushed a workflow file to a new branch, but could not delete the branch
   (proxy refusal, then HTTP 403). The owner deletes `m4-workflow-push-probe`.

## 4. The orders, in build order

| order | name | one line | size |
|---|---|---|---|
| M4-01 | [lanes](M4-01-lanes.md) | Linux torch lanes cpu/cu126/cu132 as uv extras (cu132 with `nvidia-curand` for autochart's CUDA provider), one Linux lock, allin1's own locked project, a wheels-only check | half a day |
| M4-02 | [device](M4-02-device.md) | `songcharter/wsl.py` (read-only interop) and `songcharter doctor`: WSL, Windows build, memory against `.wslconfig`, GPU, CUDA in torch and in onnxruntime-node, disk in WSL and on C:, localhost forwarding; the pipeline records fallbacks, frees GPU memory and samples RAM, swap and VRAM; autochart's node gets the CUDA 13 library path | 1 day |
| M4-05a | [ci-skeleton](M4-05a-ci-skeleton.md) | the CI workflow from day one: the suite on `ubuntu-latest`, a `windows-latest` job for Windows-side files, hook folders that every later order fills | half a day |
| M4-03 | [install](M4-03-install.md) | `install.sh` (from the release, checked by hash, rerunnable: uv, Python, the lane, two environments), `songcharter.runtime` (Node, npm, autochart and its CUDA provider, models, `runtime.json`), the launcher, `.wslconfig`, the Start-menu shortcut, `songcharter uninstall`, the release build script | 1 day |
| M4-04 | [ui-server](M4-04-ui-server.md) | `songcharter ui` in WSL: guards, upload, one job as a child process group, events over SSE, cancel; the localhost-forwarding self-check from Windows, the browser opened with `explorer.exe` | 1 day |
| M4-05 | [ci](M4-05-ci.md) | end to end in `ubuntu:26.04` as a plain user: the release assets, the install from scratch, doctor (also with a fake `nvidia-smi`), the clip, the guards, cancel on the first take, offline, uninstall and reinstall | 1 day |
| M4-06 | [ui-results](M4-06-ui-results.md) | preview, zip, install into the Windows Songs folder under `/mnt/c` (Documents and OneDrive from the registry, rename retried), the diagnostics bundle | 1 day |
| M4-07 | [release](M4-07-release.md) | the friend's guide (WSL setup, the driver, the one install line), NOTICE, the pre-release assets and their check | half a day |
| M4-08 | [hardware](M4-08-hardware.md) | not a build: the owner's 5070 in a fresh Ubuntu-26.04 distro with 12 GB, then the friend's PC | owner's time |
| M4-99 | [later](M4-99-later.md) | native Windows, signing, the highway preview, quick fixes and the rest; nothing to build | — |

## 5. Waves (parallel builds only for orders whose files do not overlap)

| wave | orders | files |
|---|---|---|
| 1 | **M4-01** ∥ **M4-02** ∥ **M4-05a** | `pyproject.toml`, locks, `packaging/allin1/`, `packaging/check_wheels.py` ∥ `wsl.py`, `device.py`, `cli.py`, `pipeline.py`, `engines/autochart.py` ∥ `.github/workflows/ci.yml`, `packaging/ci/` |
| 2 | **M4-03** ∥ **M4-04** | `packaging/linux/`, `packaging/release/`, `runtime.py`, `launch.py`, `wslsetup.py`, `winshortcut.py` ∥ `ui/`, `proc.py`, `cli.py`, `pipeline.py`, `engines/autochart.py` (the take callback), `pyproject.toml` (package data) |
| 3 | **M4-05** ∥ **M4-06** | `packaging/ci/linux.d/50-*` and `ui_guards.py` ∥ `ui/`, `clonehero.py`, `diagnostics.py`, `cli.py` |
| 4 | **M4-07** | `docs/guide/`, `packaging/NOTICE.txt`, `packaging/release/build.sh` (after M4-03), `packaging/ci/linux.d/70-release.sh` |
| then | the full review workflow over the integrated v0.1, then **M4-08** | |

- **Each order lands its own CI checks as hook files** in `packaging/ci/linux.d/` and `windows.d/`. Nobody but
  M4-05a edits `ci.yml`.
- **M4-02 to M4-07 may push their branches to run CI.** Their briefs must say so (CLAUDE.md).
- **Docs:** parallel orders do not edit DESIGN, PROGRESS or README; each reports what changed, and the director folds
  it in at the merge.
- **Process** [decision]:
  - each order gets `sc-builder`, then `sc-reviewer` and `sc-inspector`;
  - the full workflow runs once over the integrated v0.1 before M4-08;
  - the golden charts run for every order that touches `pipeline.py` or an engine (M4-02, M4-04), as
    `eval/README.md` says, with `EXPECT=none`.

## 6. Risks, and what catches each

| # | risk | caught by | plan |
|---|---|---|---|
| 1 | Peak RAM with CUDA does not fit 12 GB of WSL memory on a 16 GB PC | M4-08 A (owner, with `memory=12GB`), sampled per stage | `swap=8GB` absorbs short peaks. If WSL gets under 11 GB (a PC under 16 GB), the install leaves allin1 out, so the sections use the librosa fallback (warned) [decision]. Under 8 GB, the install refuses (M4-03, the memory rule). |
| 2 | The CUDA 13 provider does not load in WSL (driver, library path) | `doctor`'s provider check (M4-02); M4-08 | the engine falls back to the CPU by itself, and the first-take check keeps that to 1 take (warned) |
| 3 | Localhost forwarding is off, or port 8765 is taken on the Windows side | M4-04's self-check: `curl.exe` from Windows fetches `/api/hello` and compares an instance token | the next port up to 8784. If none works, the server also binds WSL's own address and opens that URL (M4-04, startup step 3). |
| 4 | Interop is off (no `cmd.exe` in WSL) | `doctor` | the page asks for the Songs folder as a `/mnt/c/...` path; the Start-menu shortcut is skipped (the guide's fallback: open Ubuntu, type `songcharter`) |
| 5 | Smart App Control blocks the shortcut or an interop tool | only hardware: M4-08 A with SAC on (if the owner agrees), then the friend | fallback: open Ubuntu from the Start menu and type `songcharter` |
| 6 | A large download fails halfway (3+ GB on cu132) | uv's progress, `UV_HTTP_TIMEOUT=300`, `UV_HTTP_RETRIES=5`; `runtime.fetch` resumes; M4-05 kills a download and reruns | every step reruns safely; the script ends with "run the same line again to continue" |
| 7 | The disk fills: the vhdx grows on C: while WSL reports 1 TB free | the install checks `df` of `$HOME` and of `/mnt/c` before downloading | it stops with the numbers |
| 8 | OneDrive or security software locks the Songs folder during the rename | M4-06's retry (about 5 s) and its "blocked" message | the zip, and "open folder" |
| 9 | Ubuntu 26.04 differs from what CI tests | CI runs in `ubuntu:26.04` as a plain user | M4-08 A on a fresh Ubuntu-26.04 distro |
| 10 | Antivirus slows the install or the runs on the Windows side (vhdx scanning) | only M4-08 (CI has no Defender) | recorded; no fix planned for v0.1 |
| 11 | The friend's driver is under 580 | `doctor`, from `nvidia-smi` | cu126 lane (torch on the GPU, guitar on the CPU), with "update the NVIDIA driver to 580 or newer" shown |

## 7. What needs the owner, and when

1. **Now:** delete the branch `m4-workflow-push-probe` on GitHub (a session cannot), and answer section 8.
2. **During the build:** allow the order branches to push for CI, and read the Actions tab when a session cannot.
3. **After M4-07, on the 5070 PC (M4-08 part A, about two hours):**
   - a fresh `Ubuntu-26.04` distro, with WSL's memory set to 12 GB like the friend's PC (and Smart App Control on,
     if you agree);
   - the install, the test song with 1 and 4 takes, Take Me Out, cancel, Clone Hero, offline, the diagnostics zip,
     uninstall and reinstall.
4. **Then the friend's PC (part B):** you send him the pre-release link and the guide, and he sends back the
   diagnostics zip.
5. **Create the pre-release** when part A passes. `gh release create` may be blocked from a session; by hand otherwise.

## 8. Questions only the owner can answer

1. **For the test, will you turn Smart App Control on on your PC** (Windows Security > App & browser control > Smart
   App Control), then off again after? It needs Windows 11 25H2 with the April 2026 update. It is the only way to try
   the Start-menu shortcut under SAC before the friend does. While it is on, your own unsigned tools may be blocked.
2. **Is the friend's Ubuntu only for songcharter?** If yes, the guide can offer `wsl --unregister Ubuntu` as the
   complete uninstall. If he uses it for other things, only `songcharter uninstall` is offered.

## 9. Done for v0.1

- Every order's "Done means" passes, CI is green on `main`, and CLAUDE.md's release gate holds:
  - the suite;
  - the golden charts;
  - the test song end to end with its preview looked at;
  - the owner's approval.
- M4-08 parts A and B pass, against DESIGN 5 M4's acceptance for what v0.1 covers. The highway preview, metronome,
  quick fixes and edits are v0.2 (M4-99).

## Appendix: why not native Windows on this PC

The native plan (commit f9f9377) remains the route for a PC without Smart App Control, or for a signed release
(M4-99). What it found:
- **Smart App Control on** blocks unsigned code loaded by the Windows loader and script engines, with no per-app
  exception (section 1). Every Python extension module and torch DLL is such a file.
- **No CUDA for the guitar on native Windows.**
  - onnxruntime-node 1.27.0's Windows build has only the CPU, DirectML and WebGPU providers. Its README says so, its
    install script lists no CUDA files for win32/x64, and its binding names no `cuda` [doc; here].
  - autochart's engine falls back to the CPU on a failed `cuda` request [code, autochart b5a41e8].
  - The GPU route would be WebGPU (Direct3D 12), unmeasured on a 4070.
- **The lanes resolve for win_amd64:**
  - 62 Windows packages per lane, all wheels;
  - allin1's project has 64, with one pure-Python sdist (`antlr4-python3-runtime` 4.9.3, built to `py3-none-any`
    without a compiler);
  - torch on Windows: 126 MB (cpu), 2.60 GB (cu126), 2.11 GB (cu132) [here].
- **torchaudio:** 2.11.1 from PyPI (`py3-none`, `torch>=2.11`) works with torch 2.15 for allin1 (Linux: the runner's
  probe, a fold-0 run) [here]. This carries over to WSL unchanged.
- **Paths:** torch's deepest file under a 20-character profile is at most 223 characters. autochart's staging files
  pass 259 on every profile; Node's `\\?\` handling is untested.
- **The runners:**
  - `windows-latest` has Inno Setup 6.7.1 and PowerShell 7.6.7; `shell: powershell` is 5.1;
  - the image turns long paths on and Defender's real-time protection off, so CI cannot prove either
    [doc: runner-images].
- **autochart's archive is checked file by file.** The engine needs `config/`, `shared/` and three `electron/`
  files besides `engine/`, so the whole repository at the pinned commit is fetched and checked against
  `packaging/autochart/engine-files.sha256` (346 files; `make_engine_list.py` writes it). The WSL install uses the
  same check.
