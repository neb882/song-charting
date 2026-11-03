# M4-07: the friend's guide, NOTICE, and the pre-release assets

**Branch:** `m4-07-release`, from `main` after M4-05 and M4-06 have merged. **Wave 4.** **Agent:** `sc-builder`,
then `sc-reviewer`. May push its branch to run CI.

## Intent

The friend gets one page: what to check on his PC, how to set up WSL, the one line to paste, how to start and use
songcharter, and how to remove it. The pre-release carries that page, the install script, the app and their
checksums. Every command in the guide is one CI has run. The owner decided: a GitHub pre-release on
neb882/song-charting, and MIT for songcharter's own code (LICENSE on `main`).

## Scope

Creates:
- `docs/guide/windows-wsl.md`: a template with `{{VERSION}}` and `{{INSTALL_SHA256}}`;
- `packaging/NOTICE.txt`;
- `packaging/ci/linux.d/70-release.sh`.

Changes: `packaging/release/build.sh` (M4-03's): render the guide into `dist/GUIDE.md`, and put `NOTICE.txt` at the
tarball's root.

Must not touch: `songcharter/`, `tests/`, `install.sh`'s logic, `ci.yml`, and the other docs (the director folds
README and DESIGN in).

## Spec

### The guide (`docs/guide/windows-wsl.md`)

Plain words, numbered steps, no jargon without a gloss, under two pages. Its sections:

1. **Before you start:**
   - Windows 11, or Windows 10 version 2004 or later;
   - about 20 GB free on C:;
   - the NVIDIA driver, 580 or newer, from nvidia.com or the NVIDIA app. To check: open Command Prompt, type
     `nvidia-smi`, and read "Driver Version";
   - virtualization on: Task Manager > Performance > CPU shows "Virtualization: Enabled". If it says Disabled, it is
     turned on in the PC's BIOS/UEFI settings (Intel VT-x or AMD SVM); the steps depend on the PC.
2. **Set up WSL, once:**
   - right-click Start > "Terminal (Admin)", type `wsl --update`, then `wsl --install`, and restart the PC when it
     finishes. `wsl --update` first, because an older WSL installs Ubuntu 22.04 instead of the current 26.04 [doc:
     Microsoft's DistributionInfo.json, the legacy list];
   - after the restart an Ubuntu window opens: choose a user name and a password.
   - Errors 0x80370102 or 0x80070003 mean virtualization is off [doc: Microsoft's WSL troubleshooting].
   - **Never install an NVIDIA driver inside Ubuntu:** the Windows driver already works there [doc: NVIDIA's WSL
     guide].
3. **Install songcharter.** In the Ubuntu window, paste:
   ```
   curl -fsSLO https://github.com/neb882/song-charting/releases/download/v{{VERSION}}/install.sh && echo "{{INSTALL_SHA256}}  install.sh" | sha256sum -c - && bash install.sh
   ```
   - It shows how much it will download (about 4 GB with an NVIDIA GPU) and how long that takes, then asks to go
     on.
   - If it stops halfway, paste the same line again: it continues.
   - If it says the guitar runs on the CPU because the driver is older than 580: update the driver, then paste the
     line again. It switches to the GPU build (about 3 GB).
   - At the end, it sets WSL's memory and restarts WSL, and the window closes.
4. **Start songcharter:**
   - Start menu > "songcharter". A window opens: keep it open while you use songcharter. Then your browser opens the
     page.
   - If the shortcut does not work: open "Ubuntu" from the Start menu and type `songcharter`.
5. **Chart a song:**
   - **chart first, play after.** While a song charts, songcharter uses most of the PC's memory: on a 16 GB PC
     Windows has about 4 GB left for a few minutes. Don't run games then;
   - drop the file and press "Chart it";
   - when it is done, look at the preview, then "Install into Clone Hero";
   - in Clone Hero: Settings > General > Scan Songs.
6. **If something goes wrong:**
   - **turn off any VPN while installing:** it can block or slow the downloads;
   - **if downloads keep failing with certificate errors**, typically after the PC slept and WSL's clock is wrong:
     in Terminal, `wsl --shutdown`, then open Ubuntu and paste the install line again;
   - the "Diagnostics" link at the bottom of the page saves a zip to Downloads (logs and settings, no audio). Send
     it. Or type `songcharter diagnostics` in Ubuntu.
7. **Remove it:**
   - in Ubuntu, `songcharter uninstall`. Answer No to keep the downloads for a later reinstall;
   - to remove everything: Terminal (Admin) > `wsl --unregister Ubuntu`.
     - **Warning, shown in bold:** this deletes everything in that Ubuntu, not only songcharter. Use it only if you
       keep nothing else there.
     - The owner settled offering it.
8. **Licences:** "songcharter is MIT. The models it downloads are non-commercial (see NOTICE.txt). Charts you make
   are yours; song.ogg is made from your recording, and sharing it is sharing the song."

### `NOTICE.txt`

One block per component: what it is, its licence, and whether it is downloaded at install or part of the release.
The release itself ships only songcharter's code and this file. Check each licence on the package when writing.

| component | status |
|---|---|
| songcharter | MIT (LICENSE, `main` 12ebf10) |
| uv | MIT OR Apache-2.0, downloaded |
| CPython (python-build-standalone) | PSF licence, downloaded |
| PyTorch | BSD-3-Clause, downloaded |
| NVIDIA CUDA libraries (nvidia-* wheels) | NVIDIA's licence (`LicenseRef-NVIDIA-Proprietary` on PyPI), downloaded on GPU lanes |
| Demucs | code MIT; htdemucs_6s weights treated as non-commercial (DESIGN 4.2) |
| all-in-one-infer | MIT; weights tagged MIT |
| ADTOF port and weights | treated as CC BY-NC-SA 4.0 |
| autochart's engine | AGPL-3.0-or-later; downloaded from github.com/dvar0/autochart at b5a41e8, whose full source is then on the PC |
| Fretformer 2 weights | CC BY-NC-SA 4.0, with autochart's attribution file |
| Beat This | MIT |
| Node.js | its LICENSE, downloaded |
| onnxruntime-node and its CUDA provider (NuGet) | MIT |
| scan-chart | MIT |
| FFmpeg via imageio-ffmpeg | the wheel is BSD-2-Clause; its ffmpeg binary is a GPL build (the Windows binary's configuration shows `--enable-gpl` [here]; read the Linux one's when writing) |

### `build.sh` additions

- Render the guide, replacing `{{VERSION}}` and `{{INSTALL_SHA256}}` (`install.sh`'s SHA-256), into `dist/GUIDE.md`.
- Put `NOTICE.txt` at the tarball's root.
- `install.sh`'s "Continue?" prompt names it: "Licences: <app>/NOTICE.txt". This is the one-time "model licences"
  notice of DESIGN 4.2, in text.

### The pre-release (done at M4-08, after part A passes; listed here so it is written down)

```
git tag v0.1.0 <main's commit> && git push origin v0.1.0
gh release create v0.1.0 --prerelease --title "songcharter 0.1.0 (WSL)" --notes-file dist/GUIDE.md \
  dist/install.sh dist/songcharter-0.1.0.tar.gz dist/SHA256SUMS
```

The owner runs it, or a session if the proxy allows release writes (it refused other write paths in the planning
job). Otherwise it is done by hand on GitHub's release page with the same files and notes.

### Hook `70-release.sh`

- `build.sh` gives the four files.
- `GUIDE.md` has no `{{`. Its install line's hash equals `sha256sum install.sh` and `SHA256SUMS`'s line.
- The tarball holds `NOTICE.txt` and `LICENSE`, and `check_no_audio.py` passes on its listing.
- **The guide's line, exactly as written,** run in `ubuntu:26.04` as a plain user against a local HTTP server that
  serves `dist/` at the release path. Use a test override of the URL prefix: an environment variable that
  `install.sh` honours only for this; M4-03 adds it if missing. The hook asserts the `sha256sum -c` step passes.

## Done means

1. [dev] `build.sh 0.1.0-dev /dev/shm/m4-07/dist` renders `GUIDE.md`. The guide reads well: a person reads it and
   says so in the report, with its word count.
2. [CI] `70-release.sh` passes after the push.
3. [Hardware] M4-08: the owner follows the guide on the 5070's fresh distro and notes every step that was unclear;
   the friend follows it on his PC.

## Depends on

- M4-03: `build.sh`, `install.sh`;
- M4-05: the end-to-end run the guide's commands rely on;
- M4-06: diagnostics.
