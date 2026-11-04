# M4-07: the friend's guide, NOTICE, and the pre-release assets (builder's report)

Branch `m4-07-release` (worktree `<scratchpad>/wt/m4-07`), from main at 5fc1f1e (a192108 plus "PROGRESS: M4-07 in
flight"). Pushed to origin to run CI; nothing published (no tag, no release, no draft).

## Commits (main..m4-07-release)

| commit | what |
|---|---|
| 186c9bb | `packaging/NOTICE.txt`: every third party, its licence as its package states it, and how it arrives |
| 8fc8862 | `docs/guide/windows-wsl.md` (the template) and `packaging/release/build.sh`: `dist/GUIDE.md` rendered, NOTICE.txt at the tarball's root |
| 441cae7 | `install.sh`'s Continue prompt names `<app>/NOTICE.txt`, with its test in `tests/test_install.py` |
| d2e5bc3 | `test_build_writes_the_three_assets`: the file list grows by GUIDE.md (outside the brief's tests/ allowance, see "Deviation") |
| 8d43859 | CI hook `packaging/ci/linux.d/70-release.sh` |
| e811088 | the guide after the read-through as the friend (seven fixes, below) |

| 452ce63 | 70-release: uninstall's "kept" line follows the `[y/N]` prompt when piped (CI run 1's one failure); git in the container, as the other hooks have it |

## What changed

- **`packaging/NOTICE.txt`** (new, 143 lines): a header (what the release holds, where things go on the PC, which
  models are non-commercial), then one block per component: What, Licence, How (the release, downloaded at install,
  GPU lanes only, or on first use). Components: songcharter, uv, CPython (python-build-standalone), PyTorch,
  torchaudio, the NVIDIA CUDA wheels, Demucs and htdemucs_6s, All-In-One, ADTOF (the port and its weights),
  autochart's engine, Fretformer 2, Beat This!, Node.js, onnxruntime-node and its CUDA provider, scan-chart,
  FFmpeg through imageio-ffmpeg, the lyrics aligner's wav2vec 2.0 weights, and "the other Python packages".
- **`docs/guide/windows-wsl.md`** (new): the template, with `{{VERSION}}` (title, install line, NOTICE link) and
  `{{INSTALL_SHA256}}`. The order's eight sections, in its order.
- **`packaging/release/build.sh`**: after SHA256SUMS, `sed` fills both values (install.sh's SHA-256) into
  `<out>/GUIDE.md` through a `.part` file, and stops (exit 1) if a `{{` or `}}` is left. The tarball gets HEAD's
  `packaging/NOTICE.txt` (`git cat-file blob`) at its root with `git archive --add-file`, so the tarball stays
  "committed files only" and byte-identical for one commit (checked: two builds of one commit, the second with
  NOTICE.txt's mtime changed, gave the same SHA-256). GUIDE.md is not in SHA256SUMS (it is the release's notes, not
  an asset). The guide is read from the working tree, as install.sh already is.
- **`packaging/linux/install.sh`**: the one text change. The prompt is now
  `Licences: <app>/NOTICE.txt (some of the models are for non-commercial use only)` then `Continue? [Y/n] `, where
  `<app>` is `$home/app/$VERSION`, where the tarball unpacks (so the file is there from step 6 on; at the prompt of a
  first install it is not there yet, which the wording does not claim).
- **`tests/test_install.py`**: a new test, `test_the_prompt_names_the_licences_and_enter_goes_on` (No stops with
  exit 1 after the exact two prompt lines and fetches nothing; Enter goes on to an installed launcher), and the
  test_build assertion change.
- **`packaging/ci/linux.d/70-release.sh`** (new, 755): see "The hook".

## NOTICE: each licence and its source

Checked on the package itself on 2026-11-04 (PyPI's JSON API for every package in both locks, 117 name/version
pairs; the PyTorch index's PEP 658 metadata for the lanes' torch wheels; the npm registry and the scan-chart
tarball; NuGet's catalog and the provider package's own LICENSE, read with HTTP range requests; the Hugging Face
API's model tags; the repositories' LICENSE files at their pinned commits through raw.githubusercontent.com).

| component | found | source | as the order's table? |
|---|---|---|---|
| songcharter | MIT (LICENSE, 3fe738c); songcharter/engines/adtof.py treated as CC BY-NC-SA 4.0 (its docstring, DESIGN 4.2) | the repository | yes; NOTICE adds the adtof.py carve-out, which is in the release |
| uv 0.13.5 | MIT OR Apache-2.0 | PyPI license_expression; astral-sh/uv LICENSE-MIT at 0.13.5 | yes |
| CPython 3.13.17 | PSF License Agreement; python-build-standalone links libedit, not GNU readline, and leaves GDBM out | python-build-standalone docs/running.rst, "Licensing" | yes (detail added) |
| PyTorch 2.15.0 / 2.14.1 | own LICENSE: BSD-3-Clause; the wheels' License-Expression: `Apache-2.0 AND Apache-2.0 WITH LLVM-exception AND BSD-2-Clause AND BSD-3-Clause AND BSL-1.0 AND ISC AND MIT AND Zlib` (2.14.1: without ISC and Zlib), for what they bundle | pytorch/pytorch LICENSE at v2.15.0; the .metadata of torch-2.15.0+cpu and +cu132 on download-r2.pytorch.org; PyPI for 2.14.1 | **differs in detail**: BSD-3-Clause is its own code; the wheel carries more licences. NOTICE names both. |
| torchaudio 2.11.1 | BSD-2-Clause | pytorch/audio LICENSE at v2.11.1 (PyPI's classifier: BSD License) | yes |
| NVIDIA wheels | `LicenseRef-NVIDIA-Proprietary` (nvidia-curand, -cuda-cccl, -nvjitlink, -cudnn-cu12) or "NVIDIA Proprietary Software" (the cu12 wheels, cusparselt); several cu13 wheels declare none on PyPI | PyPI | yes |
| Demucs | demucs 4.1.0 MIT (songcharter's env); demucs-infer 4.4.0 MIT (allin1's env); htdemucs_6s on the hub (adefossez/HTDemucs-6s at 3c5ee475): no licence tag, the model card says nothing of one; Demucs README lines 321-325: "not clear", "likely CC-NC-BY" | PyPI; adefossez/demucs README and LICENSE; the hub API and model card | yes |
| all-in-one-infer 3.1.0 | MIT; weights tagged `license:mit` (taejunkim/allinone at 379e5fd0); madmom-infer 0.2.0 BSD-2-Clause | PyPI; openmirlab/all-in-one-infer LICENSE; the hub API | yes |
| ADTOF | MZehren/ADTOF README lines 7-8 and LICENSE: CC BY-NC-SA 4.0; xavriley/ADTOF-pytorch: no LICENSE file (404 on main and master), no licence in README or pyproject.toml | raw.githubusercontent.com | yes |
| autochart's engine | AGPL-3.0-or-later (package.json at b5a41e8; LICENSE is the AGPL v3 text, 34,523 bytes) | dvar0/autochart at b5a41e8 | yes |
| Fretformer 2 | CC BY-NC-SA 4.0: the hub's tag (Dvaro/autochart-models at 8a88855d), the engine's catalog.json (`CC-BY-NC-SA-4.0`) and engine/licenses/fretformer-2-attribution.txt; the pack also holds ONNX conversions of htdemucs_6s (MIT per that file) and Beat This (MIT) | the hub API; autochart at b5a41e8 | yes |
| Beat This! | MIT, "code and the published model weights" (its README); in v0.1 only inside autochart's model pack | CPJKU/beat_this README and LICENSE; autochart's attribution | **detail**: not a separate download (DESIGN 4.2's "may be bundled or mirrored" row predates this) |
| Node.js 24.19.0 | MIT for Node.js, with the bundled code's licences in its LICENSE (157,606 bytes); the tarball has LICENSE at its root (listed) | nodejs/node LICENSE at v24.19.0; nodejs.org's tarball listing | yes |
| onnxruntime-node 1.27.0; the CUDA provider | npm: MIT (also onnxruntime-common). NuGet Microsoft.ML.OnnxRuntime.Gpu.Linux 1.27.0: no license expression, `licenseFile: LICENSE`, and that file is MIT; the package also has ThirdPartyNotices.txt | registry.npmjs.org; api.nuget.org catalog; the nupkg's LICENSE (range read) | yes |
| scan-chart 8.0.1 | MIT; its dependencies MIT, ISC, Apache-2.0 (workerpool), BSD, WTFPL, MPL-2.0 (exifreader, stream-audio-fingerprint) | npm registry and the 8.0.1 tarball's package.json (no LICENSE file in the tarball); tools/scan-chart/package-lock.json | yes (dependencies added) |
| FFmpeg via imageio-ffmpeg 0.8.1 | the wheel: BSD-2-Clause. Its Linux binary `ffmpeg-linux-x86_64-v9.0.2` (172,692,552 bytes) reports `ffmpeg version n9.0.2-17-g2a571b6068-20260930`, `configuration: ... --enable-gpl --enable-version3 ...` (`--disable-libfdk-aac`, nothing nonfree), a BtbN FFmpeg-Builds "gpl" build (imageio-ffmpeg's tools/download_ffmpeg.py names that source for linux-*) | the locked wheel `imageio_ffmpeg-0.8.1-py3-none-manylinux_2_28_x86_64.whl` (SHA-256 050d6850...0bda, as uv.lock pins it), downloaded and its binary run with `-version` | **differs in detail**: GPL **version 3 or later**, not only "a GPL build" |
| lyrics aligner | torchaudio's WAV2VEC2_ASR_LARGE_LV60K_960H: "Originally published by the authors of wav2vec 2.0 under MIT License and redistributed with the same license" | pytorch/audio v2.11.1 src/torchaudio/pipelines/_wav2vec2/impl.py (the bundle's docstring) | yes |
| other Python packages | permissive except **lameenc 1.9.0 LGPL-3.0-or-later** (a demucs dependency), **soxr 1.1.0 LGPL-2.1-or-later** (librosa's), **certifi MPL-2.0**, **tqdm MPL-2.0 AND MIT**; **soundfile 0.14.0's wheel bundles libsndfile** (`_soundfile_data/libsndfile_x86_64.so`) and its codecs, LGPL and BSD (its licensing/license_notes.md); sphn 0.2.1 declares nothing on PyPI, its wheel's LICENSE is Apache-2.0 (Cargo.toml: MIT/Apache-2.0); cuda-toolkit declares none | PyPI for all 117; the soundfile and sphn wheels (range reads) | **not in the table**: added as the last block |

Not checked: each nvidia-* wheel's own licence text (only PyPI's metadata); the full text of every permissive
package's licence; python-build-standalone 3.13.17's own licence metadata (its PYTHON.json); the bundled code
inside Node, onnxruntime and the autochart engine beyond their own notice files. Nothing here is legal advice, and
NOTICE says so.

## The guide

- **Rendered:** `bash packaging/release/build.sh 0.1.0-dev /dev/shm/m4-07/dist` (exit 0) wrote
  `/dev/shm/m4-07/dist/GUIDE.md`: **868 words**, no `{{` left; a copy that outlives /dev/shm is
  `<scratchpad>/m4-07/GUIDE-0.1.0-dev.md`. About 1.8 pages of A4 at a normal font size; the install line is one
  145-character code line (GitHub gives it a copy button).
- **Figures** in the guide: about 20 GB free on C: (the order); about 4 GB to download with an NVIDIA GPU (install.sh
  shows 4.2 GB for cu132: 3.2 + 1); the GPU build after a driver update, about 3 GB (install.sh's own warning); the
  first song with lyrics, 1.26 GB once (M4-10, measured). **Estimates, for M4-08 to measure:** the GPU lane's 4 GB
  download and its 3 GB switch, and the 20 GB on C: (install.sh asks 15 GB free on a GPU lane, its own decision;
  only the cpu lane's 2.8 GB and 8 GB are measured, by M4-05). The guide gives no cpu-lane figures: the friend has a
  GPU, and the installer prints its own.
- **Wording choices:**
  - the Licences section says "Some of the models it downloads are for non-commercial use only" where the order had
    "The models it downloads are non-commercial": All-In-One, Beat This and wav2vec 2.0 are MIT. It links NOTICE.txt
    at `github.com/neb882/song-charting/blob/v{{VERSION}}/packaging/NOTICE.txt`, which works once M4-08 pushes the tag;
  - "Paste lyrics": one plain bullet ("paste the song's words into the "Paste lyrics" box, one line for each sung
    line. songcharter times the words you paste to the singing; it never looks lyrics up"), with no example text and
    no song named;
  - `songcharter diagnostics --out diagnostics.zip`, not the order's bare `songcharter diagnostics`: `--out` is
    required (cli.py), and in WSL the command prints "in Windows: \\wsl.localhost\..." for the zip;
  - section 7 adds that `songcharter uninstall` prints the unregister line with the Ubuntu's real name.
- **The read-through as the friend** (start to finish, rendered), and what it changed (commit e811088): how to open
  Command Prompt (Start menu, `cmd`); answer Yes to Windows' question for the admin Terminal; the Ubuntu user name in
  lower-case letters with no spaces, and Ubuntu from the Start menu if its window does not open after the restart;
  Ctrl+V pastes as well as a right-click; what "install.sh: FAILED" means (nothing ran; don't run it another way; ask
  whoever sent the page); the shortcut found by typing `songcharter` in the Start menu rather than "Start menu >
  songcharter"; where Terminal is for `wsl --shutdown`. It reads well after those: plain words, each step one action,
  every term that a gamer may not know glossed (WSL, the admin Terminal, [Y/n]).

## The hook (`70-release.sh`)

Runs build.sh for `0.1.0-ci-<commit>` into `$CI_TMP/release`, then:
1. the four files and nothing else;
2. GUIDE.md: no `{{`/`}}`; exactly one line with `sha256sum -c`, equal to the expected
   `curl -fsSLO https://github.com/neb882/song-charting/releases/download/v<version>/install.sh && echo "<install.sh's SHA-256>  install.sh" | sha256sum -c - && bash install.sh`;
   SHA256SUMS has the same line for install.sh;
3. the tarball has `NOTICE.txt` (byte-equal to packaging/NOTICE.txt) and `LICENSE` at its root; check_no_audio.py
   passes on it;
4. a local `python -m http.server` on 127.0.0.1 serves install.sh, the tarball and SHA256SUMS at
   `/neb882/song-charting/releases/download/v<version>/`; `docker run --network host ubuntu:26.04`, `apt-get install
   curl ca-certificates xz-utils`, `useradd -m friend`; as friend, in a login shell, the guide's line exactly as
   GUIDE.md has it but for `https://github.com/` becoming the server's address (checked to be the only change), with
   `SONGCHARTER_RELEASE_URL` naming the same server:
   - a changed install.sh served: `install.sh: FAILED`, non-zero, and the installer never ran;
   - No at Continue?: `install.sh: OK`, the Licences line naming `~/.local/share/songcharter/app/<version>/NOTICE.txt`,
     `Continue? [Y/n] songcharter: stopped; nothing was downloaded.`, exit 1, and the server log shows no tarball fetch;
   - Enter: the whole install, exit 0, `install.sh: OK`, "is installed"; the server log shows install.sh 3 times and
     the tarball once (so the tarball came through `SONGCHARTER_RELEASE_URL`), and the installed NOTICE.txt is
     byte-equal to packaging/NOTICE.txt;
5. the guide's other Ubuntu commands as written: `songcharter` (its "songcharter is at" address serves the page's
   title, then SIGTERM, exit 0); `songcharter diagnostics --out diagnostics.zip` (the printed path, check_no_audio.py
   on the zip); `songcharter uninstall` with Enter (No: "kept ...", the launcher and app gone, runtime/env kept).
Logs, GUIDE.md, SHA256SUMS, the server log and the diagnostics zip go to `$CI_ART/70-release`.

## Checks

1. **[dev] the render.** `bash packaging/release/build.sh 0.1.0-dev /dev/shm/m4-07/dist` at e811088: exit 0;
   `GUIDE.md SHA256SUMS install.sh songcharter-0.1.0-dev.tar.gz`; GUIDE.md 868 words, no `{{`. Read start to finish
   (above). The tarball: `songcharter-0.1.0-dev/NOTICE.txt` and `/LICENSE` listed; a second build of the same commit,
   NOTICE.txt's mtime changed, gave the same SHA-256 (ec1f62bb... at 186c9bb).
2. **The full suite** (dev container, `tools/heavy.sh`, the session's venv, SONGCHARTER_SCAN_CHART set) at e811088:
   `811 passed, 4 skipped in 581.80s (0:09:41)`, exit 0. The later commit, 452ce63, changes only the hook.
3. **tests/test_install.py**: 28 passed. **Tests of the tests** (each break restored after):
   - the prompt test, 4 breaks of install.sh, each failed it: no Licences line; LICENSE named instead of NOTICE.txt;
     No not stopping; Enter stopping;
   - test_build's new assertions, 5 breaks of build.sh, each failed it: no `--add-file` (no NOTICE.txt); the
     tarball's hash in the guide's line; no GUIDE.md written; `{{VERSION}}` left (the build's own check stops it);
     `{{VERSION}}` left with that check removed.
4. **The hook, here**, with a stand-in `docker` that runs each step locally (a stand-in `id`, /tmp, /ci and
   /home/friend mapped to test folders) and stops at the full install: steps 1-4 passed through the No case. Then 6
   breaks, each failing the hook at the check meant for it: the tarball's hash in the guide's line ("the guide's
   install line is not the expected one"); no NOTICE.txt in the tarball ("the tarball has no NOTICE.txt at its
   root"); install.sh's prompt without the Licences line (the No case fails); the guide's line with `;` instead of
   `&&` before `bash install.sh`, and with `releases/latest/download` (both: "not the expected one"); a fifth file in
   the out folder ("build.sh wrote: ...").
5. **[CI]** run 1, https://github.com/neb882/song-charting/actions/runs/41796214912 (at e811088): windows success;
   linux: the suite and hooks 10-60 passed, 70-release passed every step through the full install, the page and
   diagnostics, and failed at the last check (uninstall's "kept" line, a bug in the check: the uninstall itself
   did what the guide says). From its log: `install.sh: FAILED` / `sha256sum: WARNING: 1 computed checksum did NOT
   match` for the changed file; `Licences: /home/friend/.local/share/songcharter/app/0.1.0-ci-e811088/NOTICE.txt
   (some of the models are for non-commercial use only)` / `Continue? [Y/n] songcharter: stopped; nothing was
   downloaded.`; Enter: `doctor: OK`, `songcharter 0.1.0-ci-e811088 is installed (lane cpu: no NVIDIA GPU found).` in
   39 s; `70-release: the installed NOTICE.txt is packaging/NOTICE.txt`; the page: `songcharter is at
   http://127.0.0.1:8765/ ...`, `SIGTERM: stopping`, `stopped`; diagnostics: `check_no_audio: ok, 1 files and 6
   archive members`.
6. **[CI]** run 2, https://github.com/neb882/song-charting/actions/runs/41798811539 (at 452ce63): **success**,
   windows and linux. Its last lines: `-- songcharter uninstall, answered with Enter (No): ok in 1 s`,
   `70-release: ok`, `==== hook linux.d/70-release.sh ok in 61 s`, `all 7 Linux hooks passed: 10-lanes.sh 13s
   20-device.sh 6s 30-install.sh 154s 40-ui.sh 21s 50-e2e.sh 415s 60-results.sh 56s 70-release.sh 61s`. Every step
   of 70-release ran (the changed install.sh, No, Enter in 35 s, the NOTICE.txt comparison, the page, diagnostics,
   the uninstall).

## Deviation, and questions for the orchestrator

1. **tests/test_install.py beyond the prompt's test.** build.sh now writes GUIDE.md, and
   `test_build_writes_the_three_assets` asserted the out folder holds exactly three files, so the order's build.sh
   change fails the suite as it stood (and CI runs no hook after a failed suite). The brief allowed only the prompt's
   test in tests/. I sent the orchestrator a message when I found it (no answer came during the build) and changed
   that assertion in its own commit, d2e5bc3: the list gains GUIDE.md, and it now also asserts NOTICE.txt and
   LICENSE at the tarball's root and the guide's line with install.sh's hash. Dropping d2e5bc3 brings the failure
   back; redoing it differently is the orchestrator's call.
2. **"Every command in the guide is one CI has run"** holds for the Ubuntu commands only. The Windows ones
   (`nvidia-smi` in Command Prompt, `wsl --update`, `wsl --install`, `wsl --shutdown`, `wsl --unregister Ubuntu`) and
   the Start-menu shortcut cannot run on GitHub's runners; M4-08 (hardware) is where they are run.
3. Licence findings that differ from the order's table (above): PyTorch's wheel licences, the Linux ffmpeg being
   GPL-3.0-or-later, Beat This only inside autochart's pack, and the LGPL/MPL packages not in the table.

## Edits for the orchestrator to fold in at the merge

**README.md**
- Status, the "Next" bullet: "**v0.1 for Windows** runs in WSL2 (M4): the friend's guide is
  `docs/guide/windows-wsl.md`, which `packaging/release/build.sh` renders into each release's notes (`GUIDE.md`)."
- Using it, a first bullet: "**On Windows:** follow the release's guide: set up WSL once, then paste its one line,
  which downloads `install.sh`, checks its SHA-256 and runs it."
- A short "Licence" section after "What does not live here": "songcharter's own code is MIT (LICENSE), except
  `songcharter/engines/adtof.py`, treated as CC BY-NC-SA 4.0. What it downloads has its own licences, some of them
  non-commercial (Fretformer 2, the ADTOF weights, htdemucs_6s): `packaging/NOTICE.txt`, also at the root of each
  release's tarball."

**docs/DESIGN.md**
- §4.2, after the table: "**As built (M4-07):** `packaging/NOTICE.txt` lists every component with its licence as
  its package states it, and how it arrives; it sits at the release tarball's root, and install.sh's Continue prompt
  names `<app>/NOTICE.txt`: v0.1's one-time model-licences notice, in text (no screen). Checked on 2026-11-04: the
  Linux ffmpeg in imageio-ffmpeg 0.8.1 is configured `--enable-gpl --enable-version3` (GPL-3.0-or-later, a BtbN
  build); torch's wheels carry Apache-2.0, BSL-1.0, ISC, MIT and Zlib code beside its own BSD-3-Clause; lameenc
  (LGPL-3.0-or-later), soxr (LGPL-2.1-or-later), certifi and tqdm (MPL-2.0) and soundfile's bundled libsndfile (LGPL)
  are the only non-permissive Python packages; Beat This reaches the PC only inside autochart's model pack."
- §4.2's Beat This row: decision "in v0.1, only as autochart's ONNX export, in its model pack".
- §4.2, "Weight downloads", the line "A one-time "Model licences" screen lists every licence and attribution":
  add "(v0.1: NOTICE.txt, named at install.sh's Continue prompt)".
- §4.6, after M4-05's paragraph: "M4-07's `70-release.sh` builds the release (`build.sh`: the tarball with
  NOTICE.txt and LICENSE at its root, install.sh, SHA256SUMS, GUIDE.md), checks the guide's line against
  install.sh's SHA-256, then runs that line as the guide has it, as a plain user in `ubuntu:26.04`, against a local
  server at the release's path (`SONGCHARTER_RELEASE_URL`): a changed install.sh is stopped by `sha256sum -c`, No at
  Continue? fetches nothing, Enter installs; then `songcharter`, `songcharter diagnostics --out` and
  `songcharter uninstall` as written."
- §5 M4 or wherever the release is described: "The friend's guide: `docs/guide/windows-wsl.md`, a template that
  `build.sh` renders into `dist/GUIDE.md`, the pre-release's notes (M4-07). The pre-release itself is made at M4-08."

**docs/PROGRESS.json** (the orchestrator keeps it): suggested `deferred` lines below.

## Suggested deferred items

- The guide's GPU-lane figures (about 4 GB to download, about 3 GB to switch to the GPU build, about 20 GB free on C:)
  are install.sh's estimates and the order's: M4-08 measures the cu132 lane's download and disk.
- The guide's Windows steps (nvidia-smi in Command Prompt, `wsl --update` then `wsl --install`, the first Ubuntu
  window and its user name, the Start-menu search for songcharter, `wsl --shutdown`, `wsl --unregister`) are run on
  hardware only (M4-08, and the friend's PC).
- The guide's NOTICE.txt link points at the tag `v{{VERSION}}` on GitHub: it works once M4-08 pushes the tag.
- NOTICE.txt is hand-written from the locks of 2026-11-04: a lock or pin change (torch, imageio-ffmpeg, autochart's
  commit, the model revisions) can make it stale. A check that every locked package with a non-permissive licence
  is named in NOTICE.txt would catch it.

## Scan before the push

`git diff main...HEAD` and the commit messages, searched for emails, home or profile paths, the scratch path, and
AI model names: only the hooks' made-up container user (`friend`, `/home/friend`, as 30-install and 50-e2e use)
and the attribution trailers. No lyrics, no song named (the guide's lyrics bullet has no example), no audio: the
hook's artifacts pass check_no_audio.py, and the tarball does in build.sh and in the hook.

## Noticed in passing

- The install ends, on plain Linux, with "(~/.local/bin is not on PATH in this window yet: open a new window
  first, ...)". In WSL the window closes with WSL's restart, so the guide's fallback ("open Ubuntu from the Start
  menu, type songcharter") is always a new window; the hook's login shells confirm `songcharter` is on PATH there.
  One case keeps the window open: a first install whose .wslconfig already gives WSL 12 GB or more is not
  restarted, so the guide's "the window closes" does not happen and `songcharter` is not found in that window. The
  Start-menu shortcut (the launcher's full path) and the guide's fallback (a new Ubuntu window) both still work.

## Disk

`df -h /` at the end: 8.5 GB free of 252 GB (it was 8.5 GB at the start). This order's folders: `/dev/shm/m4-07`
(1.2 MB: the 0.1.0-dev render in dist/, the mutation helpers) and `<scratchpad>/m4-07` (1.3 MB: the licence
sources read, the ffmpeg `-version` output, the stand-in docker, the suite's log, the guide's copy); the ffmpeg
wheel and binary (240 MB) were deleted after reading.

## Review fixes (by the orchestrator)

The review (no major finding, five minor) was fixed on the branch by the orchestrator, since the builder's session had ended
in a machine restart: 559e5a8 (the guide's uninstall, diagnostics and licence wording; build.sh reading install.sh and
the guide from HEAD and naming uncommitted changes; the hook allowing one fetching line in the guide, and its
tampered-install marker made live) and e00114f (the new test's clone copies objects). Breaking build.sh three ways
(install.sh or the guide from the working copy, no note) each fails the new test. CI run 41819654756: suite 812
passed, 4 skipped; all 7 Linux hooks passed, 70-release among them.
