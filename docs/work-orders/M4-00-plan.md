# M4 plan: the Windows app, v0.1

*Written 2026-11-03 on branch `m4-plan` from `main` at 11615e2. The scope below was decided before this plan and is
not reopened here. Evidence tags follow DESIGN.md: [here] measured in this dev container, [doc] read from
documentation or a package, [code] read from this repository, [inference], [untested], [decision] a choice made
here.*

## 1. What v0.1 is

The friend plays Clone Hero (Guitar, Expert) on a native Windows PC with an RTX 4070 (12 GB of VRAM; RAM unknown).
With v0.1 he can:

1. install songcharter without help (a per-user `setup.exe`, or a portable zip);
2. drop a song file into a page in his browser;
3. keep the defaults or change the options the command line has;
4. watch one progress line per stage, with cancel, and every CPU fallback shown;
5. look at the static preview (`preview.py`'s overview and pages);
6. click once to put the chart into his Clone Hero Songs folder (or save a zip).

The first launch sets everything up: a uv-managed Python, one of three torch lanes (cu132, cu126, cpu), allin1's own
Python, Node, autochart's engine and models, every model the pipeline uses, and `doctor.json`. A diagnostics bundle
with no audio, and CI on Linux and on GitHub's `windows-latest`, come with it. Everything in M4-99 waits for v0.2.

## 2. Findings that shape the plan

Each is detailed, with its sources, in the report of this planning job and in the order that acts on it.

1. **No CUDA for the guitar on native Windows.** onnxruntime-node 1.27.0 (autochart's pin) ships Windows binaries
   with the CPU, DirectML and WebGPU execution providers only. Its README: "Right now, the Windows version supports
   WebGPU execution provider and DML execution provider. Linux x64 can use CUDA and TensorRT." [doc]. Its install
   script lists no CUDA download for `win32/x64` (`install-metadata.js`), and the Windows binding's strings name
   `cpu`, `dml` and `webgpu` and never `cuda` [here]. autochart's session loader sends a `cuda` request that fails
   to the CPU for the rest of the job (`sessionLoader.cjs` `latchRuntimeFallback`) [code, autochart b5a41e8].
   - So no CUDA or cuDNN DLLs are needed on Windows at all, admin or not: nothing could load them.
   - The Windows GPU route for the guitar is **WebGPU** (Dawn on Direct3D 12, through the NVIDIA display driver;
     its `dxcompiler.dll` and `dxil.dll` ship in the package). It is autochart's own default on Windows
     ("Automatic" tries WebGPU, then the CPU). WSL's WebGPU dead end (PROGRESS) was a software Vulkan adapter;
     a native D3D12 adapter is a different case, untested here [untested].
   - M4-02 maps the guitar's GPU device to `webgpu` on Windows. Its speed on a 4070 is the main unknown of v0.1:
     the owner's run (M4-08) measures it.
2. **The lanes resolve for Windows.** A three-lane uv lock (torch 2.15.0+cpu, 2.14.1+cu126, 2.15.0+cu132, as
   DESIGN 4.3's table says) of the current dependency set plus matplotlib and imageio-ffmpeg resolves: 114 packages
   with the project's Python range and M4-01's extras.
   - Each lane's 62 Windows packages resolve to wheels only for CPython 3.13 win_amd64, by the check M4-01
     specifies [here, uv 0.13.5; also 0.11.32].
   - Each lane passes `uv sync --frozen --dry-run` [here, Linux].
   - Downloads: torch 126 MB (cpu), 2.60 GB (cu126), 2.11 GB (cu132), plus 183 MB for the rest [here, sizes read
     from the indexes].
3. **allin1's Python can share the lane's torch.** torchaudio stops at 2.11 (2.11.0 on the PyTorch indexes, pinned to
   torch 2.11.0), but PyPI's torchaudio 2.11.1 is a `py3-none-win_amd64` wheel that needs only `torch>=2.11`.
   - On Linux, torch 2.15.0+cpu with torchaudio 2.11.1 and all-in-one-infer 3.1.0 passed the real runner's probe and
     the repository's probe test, and segmented a synthetic song with fold 0 on the CPU [here].
   - So allin1's own environment uses the same torch wheel as the main one, and uv's hardlinks make it cost almost
     no extra disk [inference: uv links from its cache].
   - Its lock (105 packages) resolves for Windows in every lane, with one exception to "wheels only":
     hydra-core 1.3.8 pins `antlr4-python3-runtime==4.9.*`, whose 4.9.3 is an sdist. It is pure Python, and uv
     builds it into a `py3-none-any` wheel with no compiler [here]. M4-01's check allows exactly that one sdist,
     and proves it builds.
   - The Windows build of that pairing is untested: CI catches it (M4-05). If it fails, the allin1 environment pins
     torch 2.11.0 with torchaudio 2.11.0 from the lane's index, a second torch download (M4-01 says how).
4. **One Node serves both.** scan-chart's dependencies need Node 18 or newer, and autochart pins Node 24.19.0, with
   the SHA-256 of each archive (`scripts/runtime-artifacts.json`) [code, autochart]. The bootstrap fetches that one
   Node and checks its archive.
5. **autochart's engine is more than `engine/`.** It loads `config/`, `shared/` and three files of `electron/`
   [code]. The bootstrap downloads the whole repository at the pinned commit (346 files, a 6.7 MB archive [here]) and
   checks every file against a committed hash list. We never redistribute the AGPL engine: each PC fetches it from
   its upstream.
6. **A synthetic clip charts end to end.** A 30-s clip made by code (drums, bass, distorted power chords, a hummed
   line; no recording) went through `songcharter chart` with every real engine on the CPU (2 threads) in 144 s. It
   passed the gate: scan-chart playable, 0 chart issues, guitar 23, bass 120 and drums 119 Expert onsets, 1 section
   from allin1 [here]. CI uses this clip (M4-05).
7. **Paths fit, except autochart's staging files.** torch's deepest file under
   `C:\Users\<20 characters>\AppData\Local\songcharter\runtime\env\Lib\site-packages\` is at most 223 characters
   (measured on the cpu wheel with a 6-character-longer prefix) [here]. The
   autochart checkout, its models and the `node_modules` are all shallow (62, 55 and 94 characters below their
   folders) [here]. The open risk stays the one PROGRESS names: autochart's scratch and staging files (section 5,
   risk 4).
8. **GitHub's runners.**
   - `windows-latest` is Windows Server 2025 with Inno Setup 6.7.1 and PowerShell 7.6.7 [doc: runner-images
     README and Windows2025-Readme, image 20261021]. Windows PowerShell 5.1 is `shell: powershell` ("PowerShell
     Desktop") [doc: workflow syntax].
   - A public repository's Windows runner has 4 processors, 16 GB of RAM and 14 GB of SSD [doc: GitHub's runner
     table]. A job may run for 6 hours [doc: Actions limits].
   - The repository is public [here, GitHub API].
9. **This session can push a workflow file, but cannot delete a branch.**
   - A commit adding `.github/workflows/m4-probe.yml` (manual trigger only) was pushed to a new branch
     `m4-workflow-push-probe` and the file is on GitHub [here].
   - Deleting the branch was refused twice: by the proxy for `gh api -X DELETE .../git/refs/...` ("Write access to
     this GitHub API path is not permitted through this proxy"), and with HTTP 403 for `git push --delete`.
   - **The branch is still on GitHub; the owner deletes it** (section 6).
   - The Actions API is partly closed to sessions: `actions/permissions` was refused, while listing the
     repository's runs answered (0 runs). Reading job logs is untested.

## 3. The orders, in build order

| order | name | one line | size |
|---|---|---|---|
| M4-01 | [lanes](M4-01-lanes.md) | three torch lanes (cpu, cu126, cu132) as uv extras, a lock for win_amd64 and Linux, allin1's own locked project, a Windows-wheel check | half a day |
| M4-02 | [device](M4-02-device.md) | `device.py` and `songcharter doctor`: GPU, driver, CUDA kernel, RAM, disk, paths, Smart App Control; the guitar on WebGPU on Windows; every CPU fallback recorded; GPU memory freed and its peaks sampled | 1 day |
| M4-03 | [bootstrap](M4-03-bootstrap.md) | `bootstrap.ps1` (PowerShell 5.1: Python, lane, the two environments), `songcharter.runtime` (Node, npm, autochart's engine and models, every model, `runtime.json`, the path check), the `songcharter.cmd` launcher | 1 day |
| M4-04 | [ui-server](M4-04-ui-server.md) | `songcharter ui`: a stdlib server on 127.0.0.1 with DESIGN 4.5's guards; upload, options, one job at a time as a child process, progress by events over SSE, cancel that kills the whole process tree | 1 day |
| M4-05 | [ci](M4-05-ci.md) | GitHub Actions: Linux (lock and wheel checks, the suite with scan-chart and allin1, the clip end to end, offline re-run) and `windows-latest` (the lane picker under PowerShell 5.1, the bootstrap on the cpu lane, doctor, the clip, offline re-run, the guards), with hook folders for later orders | 1 day |
| M4-06 | [ui-results](M4-06-ui-results.md) | the preview pages, zip export, install into Clone Hero (detect, remember, 409, Controlled Folder Access), the diagnostics bundle (UI and `songcharter diagnostics`) | 1 day |
| M4-07 | [installer](M4-07-installer.md) | Inno Setup per-user `setup.exe` and the portable zip (`build.ps1`), with a pinned `uv.exe` and NOTICE; silent install, first run and silent uninstall in CI | 1 day |
| M4-08 | [hardware](M4-08-hardware.md) | not a build: the owner's native run on the 5070, then the friend's install, with exactly what to run and send back | owner's time |
| M4-99 | [later](M4-99-later.md) | v0.2 and on: the deferred items, nothing to build | — |

That is seven build orders, one more than the brief expected: the UI is split in two (M4-04, M4-06) so that each
fits in a day, and the device checks stay apart from the bootstrap because they change `pipeline.py` and `cli.py`,
which the bootstrap does not touch.

## 4. Build waves (what can run at the same time)

Parallel builds only for orders whose files do not overlap (CLAUDE.md), each in its own worktree.

| wave | orders | why they do not overlap |
|---|---|---|
| 1 | **M4-01** ∥ **M4-02** | M4-01: `pyproject.toml`, `uv.lock`, `packaging/allin1/`, `packaging/check_wheels.py`. M4-02: `songcharter/device.py`, `cli.py`, `pipeline.py`, their tests. |
| 2 | **M4-03** ∥ **M4-04** | M4-03: `packaging/windows/`, `packaging/autochart/`, `songcharter/runtime.py`, `songcharter/launch.py`. M4-04: `songcharter/ui/`, `songcharter/proc.py`, `cli.py`, `pipeline.py`, `engines/autochart.py`, `pyproject.toml` (package data). M4-03 needs M4-01's lock and M4-02's `doctor`; M4-04 needs M4-02's `cli.py` and `pipeline.py` merged first. |
| 3 | **M4-05** ∥ **M4-06** | M4-05: `.github/workflows/ci.yml`, `packaging/ci/`. M4-06: `songcharter/ui/` (after M4-04), `songcharter/clonehero.py`, `songcharter/diagnostics.py`, `cli.py`. M4-06's CI checks go in later as hook files (below). |
| 4 | **M4-07** | `packaging/windows/songcharter.iss`, `build.ps1`, `packaging/NOTICE.txt`, `packaging/ci/windows.d/20-installer.ps1`. |
| then | **M4-08** | on the owner's PC, then the friend's |

- **CI hooks keep the waves apart.** M4-05's workflow runs every `packaging/ci/linux.d/*.sh` and
  `packaging/ci/windows.d/*.ps1` in name order. Later orders add a file there, never edit `ci.yml`.
- **Docs.** Parallel orders do not edit `docs/DESIGN.md`, `docs/PROGRESS.json` or `README.md`. Each writes what
  changed into its report, and the director folds it in at the merge (CLAUDE.md: doc edits are done directly).
- **Worktrees and branches.** One per order, named in its file (`m4-01-lanes`, ...), from `main` after the orders
  it depends on have merged. Nobody pushes, except M4-05 and M4-07, whose checks run on GitHub. Their briefs must
  allow the push (CLAUDE.md).
- **Process** [decision]. Each build order gets `sc-builder`, then `sc-reviewer` and `sc-inspector`, as for an
  ordinary change. Before M4-08, the integrated v0.1 gets the full workflow once (build lenses, verify, fix), since
  CLAUDE.md names the Windows release as big or risky. Read the usage meter before that run and give it a budget.
- **Golden charts.** M4-02 and M4-04 touch `pipeline.py` and must not change any chart on Linux. Once
  `eval/golden.py` is on `main`, each runs it, and its acceptance is no UNEXPECTED change.

## 5. Risks, and what catches each

| # | risk | caught by | fallback or plan |
|---|---|---|---|
| 1 | The guitar on WebGPU is slow or unstable on the 4070, or the 4-take default costs too much there | M4-08 (owner's 5070, then the friend's 4070): guitar stage time, 1 take and 4 | autochart falls back to the CPU by itself, and the first-take-alone check keeps it to 1 take (warned). [decision] If 4 WebGPU takes of the test song add more than 12 min to its guitar stage on the owner's PC, the default on `webgpu` becomes 1 take, a one-line change in `guitar_takes`. |
| 2 | torchaudio 2.11.1 does not load with torch 2.15 on Windows (allin1's environment) | M4-05 windows job: the allin1 probe and the clip's sections stage on the cpu lane | allin1's project pins torch 2.11.0 and torchaudio 2.11.0 per lane (M4-01, "fallback"); until then the librosa fallback runs, warned |
| 3 | The cu132 or cu126 lane does not install or run on native Windows with a GPU | M4-08 (the owner's 5070 is the first GPU on native Windows); `doctor` reports `cuda_works` | the pipeline already falls back to the CPU when no CUDA kernel runs (`separate.cuda_works`), warned. The weekly cu132 CI job is M4-99. |
| 4 | Path length: work folders (182 + root), autochart's deep cache (188 + scratch root) and its staging files (241 + scratch root) | `doctor`'s path check on every install (M4-02, M4-03); CI on the runner's profile; M4-08 on real profiles | Node writes the staging files. Node's `fs` passes Windows paths to the system in their `\\?\` form [doc: Node's `path.toNamespacedPath`; untested], and pruning deletes in that form (`cache.long_path`). If the deep cache would pass 259 (a profile name over about 22 characters), the bootstrap moves the cache root to `%SystemDrive%\songcharter-cache` (M4-03) [decision]. If that cannot be created, it says how to turn on long paths. |
| 5 | PowerShell 5.1 differences (no `??`, encodings, `ConvertFrom-Json`) | M4-05 runs the lane tests and the bootstrap under `shell: powershell` | the bootstrap downloads nothing itself: uv and Python do all fetching, so PowerShell's TLS defaults never matter |
| 6 | SmartScreen on the unsigned `setup.exe`; Smart App Control blocking the unsigned Python, torch DLLs or Node modules | only M4-08 (the friend's PC: SAC is on only on some clean Windows 11 installs) | `doctor` reads SAC's state and says what it means. Instructions are written after M4-08. Signing is M4-99. |
| 7 | Defender scanning makes `uv sync` of a 3 GB lane slow; Controlled Folder Access blocks the write into `Documents\Clone Hero` | M4-08 (times the bootstrap); M4-06's install catches `PermissionError` | the UI offers the zip and "open folder" when the write is blocked |
| 8 | Host RAM: the test song peaked at 10.1 GB for the process tree on the CPU, 7.8 GB of it allin1's runner (DESIGN 5, M3); the friend's RAM is unknown | `doctor` records RAM; M4-02's sampler records the lowest available RAM per stage; M4-08 | on CUDA allin1 runs its ensemble on the GPU [doc]; if RAM is short on the friend's PC, `--threads` and the sections fold come next (v0.2) |
| 9 | VRAM: torch keeps its cache after separation while autochart and allin1 need the GPU | M4-02 frees torch's cache after separation and drums and samples GPU memory per stage; M4-08 reads it | separation already retries on the CPU when CUDA runs out of memory |
| 10 | Clone Hero's Songs folder is not where we look | M4-06 tests; M4-08 on real installs (the owner reports Clone Hero's `settings.ini` keys) | the UI asks for the folder once and remembers it |
| 11 | Port 8765 is busy, or a second launch starts a second server | M4-04 tests | the next free port of 8766–8784; a second launch finds the first through `/api/hello` and opens it |
| 12 | Offline launches still reach the network (the Hugging Face hub) | M4-05: a second clip run with `HF_HUB_OFFLINE=1` and `SONGCHARTER_OFFLINE=1` | the launcher sets both once the bootstrap has every model |
| 13 | CI results cannot be read from a session | M4-05's first push | the owner reads the Actions tab, or sends a run's log zip |

## 6. What needs the owner

1. **Delete the probe branch** `m4-workflow-push-probe` on GitHub, which this session could not delete. It holds
   one manual-only workflow and never runs on its own. In the branch list, or `git push origin --delete
   m4-workflow-push-probe` from your machine.
2. **Allow the CI pushes.** M4-05 and M4-07 push their branches so the workflows run, and the Actions tab must
   accept workflows on this public repository.
3. **Your Windows 5070 PC, natively** (M4-08, part A), once M4-07 has a CI-built installer:
   - install, then run the clip, the test song with 1 take and with the default 4, and Take Me Out;
   - play the test song in Clone Hero;
   - send back the diagnostics bundle and the four numbers M4-08 lists.
   - Your driver must be 580 or newer for the cu132 lane: the 5070 has no kernels in the cu126 build
     [inference, DESIGN 4.3's lane table].
4. **Then the friend's PC** (M4-08, part B): install from the same file without help, chart one song he chose,
   play it, and send the diagnostics bundle. This doubles as the Windows spike PROGRESS still lists under M1a
   (`nvidia-smi`, RAM, Smart App Control).
5. **Answer the open questions** in section 7.

## 7. Open questions only the owner can answer

1. **How does the friend get the installer?** A GitHub Release on this public repository (anyone can download it;
   it holds our code, a bundled `uv.exe` and NOTICE, and fetches the AGPL engine and the non-commercial weights on
   first launch), or a file you pass to him privately from the CI artifacts. M4-07 builds the files either way;
   only the last step differs.
2. **songcharter's own licence.** The repository is public and has no LICENSE file. DESIGN 4.2 says "MIT
   (intended)", with the ADTOF port treated as BY-NC-SA. M4-07's NOTICE states whichever you choose. Until then it
   says "no licence chosen yet".

## 8. Done for v0.1

- Every order's "Done means" passes, CI is green on `main` on both jobs, and the release gate in CLAUDE.md holds:
  the suite, the golden charts (once they exist), the test song end to end with its preview looked at, and your
  approval.
- M4-08 part A passes on your PC, and part B on the friend's: the M4 acceptance of DESIGN 5 for everything v0.1
  covers. The highway preview, metronome, quick fixes and edits are v0.2 (M4-99).
