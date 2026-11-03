# M4-07: the per-user installer and the portable zip

**Branch:** `m4-07-installer`, from `main` after M4-05 and M4-06 have merged. **Wave 4.** **Agent:** `sc-builder`,
then `sc-reviewer` and `sc-inspector`.

**This order pushes** (`git push origin m4-07-installer`): ISCC runs only on Windows, so its checks run in CI. The
brief must allow the push.

## Intent

The friend downloads one file, runs it, and gets songcharter: no admin rights, Start Menu and desktop shortcuts, the
first-launch bootstrap started for him, and an uninstaller that asks before it deletes his downloads and caches
(DESIGN 4.3, 4.4). The same files also ship as a portable zip for when an installer is unwelcome.

## Scope

Creates:
- `packaging/windows/songcharter.iss`, `packaging/windows/build.ps1`;
- `packaging/NOTICE.txt`;
- `packaging/windows/uv-version.txt`: `0.13.5`, the wheel's file name and its SHA-256, read from PyPI when building
  this order;
- `packaging/ci/windows.d/20-installer.ps1`.

Must not touch:
- `songcharter/`, `tests/`, the locks, `bootstrap.ps1`, `songcharter.cmd` and `.github/`. If the installer needs
  something from them, report it.
- `docs/`.

## Spec

### `build.ps1` (PowerShell 5.1) `-Version X -Out DIR`

`X` defaults to `pyproject.toml`'s version plus `-<short sha>` when the tree is not at a tag.

1. **Stage** into `DIR\stage\`, from `git ls-files` only (never untracked files, so no audio or model can slip in):
   - `songcharter\`, `pyproject.toml`, `uv.lock`, `README.md`;
   - `packaging\allin1\`, `packaging\autochart\engine-files.sha256`;
   - `tools\scan-chart\{scan.cjs,package.json,package-lock.json}`;
   - `eval\tools\autochart\{ac_headless.cjs,package.json,package-lock.json}`;
   - `packaging\windows\{bootstrap.ps1,songcharter.cmd}` to the stage root;
   - `packaging\NOTICE.txt` as `NOTICE.txt`;
   - a `VERSION` file holding X.
2. **uv:**
   - download the wheel named in `uv-version.txt` from `https://files.pythonhosted.org/` (its PyPI URL);
   - check its SHA-256;
   - extract `uv.exe` (the wheel's `uv-*.data/scripts/uv.exe`) to `stage\bin\uv.exe`;
   - also extract uv's `LICENSE-MIT` and `LICENSE-APACHE` from the wheel's `.dist-info` into `stage\bin\`.
3. **The audio and weights check:** `python packaging\ci\check_no_audio.py stage` must pass. No file in the stage may
   end in `.pth`, `.onnx`, `.safetensors`, `.ckpt` or `.npz`.
4. **ISCC:**
   - `& "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe" /DAppVersion=X /DStage=DIR\stage /ODIR
     packaging\windows\songcharter.iss`;
   - fail with "Inno Setup 6 not found" when the path is missing;
   - the output is `DIR\songcharter-setup-X.exe`.
5. **The portable zip:** `Compress-Archive DIR\stage\* DIR\songcharter-X-portable.zip`, holding a top folder
   `songcharter-X\`.
6. `DIR\SHA256SUMS.txt` lists both files (`Get-FileHash`).

### `songcharter.iss` (Inno Setup 6)

- `[Setup]`:
  - `AppId`: a fixed GUID, made once and committed. `AppName=songcharter`, `AppVersion={#AppVersion}`.
  - `PrivilegesRequired=lowest`. No `PrivilegesRequiredOverridesAllowed`: per-user only.
  - `DefaultDirName={localappdata}\songcharter\app`, `DisableDirPage=yes`: the root is shared with the cache
    (DESIGN 4.3), so it is not a choice. `DisableProgramGroupPage=yes`.
  - `ArchitecturesAllowed=x64compatible`, `ArchitecturesInstallIn64BitMode=x64compatible`, `MinVersion=10.0`.
  - `OutputBaseFilename=songcharter-setup-{#AppVersion}`, `Compression=lzma2/max`, `SolidCompression=yes`.
  - `LicenseFile={#Stage}\NOTICE.txt`, so the licences page is the one-time "Model licences" screen of DESIGN 4.2.
  - `UninstallDisplayName=songcharter`, `SetupLogging=yes`.
- `[Files]`: `{#Stage}\*`, `recursesubdirs`, to `{app}`.
- `[Icons]`:
  - Start Menu `songcharter` → `{app}\songcharter.cmd`, working folder `{app}`;
  - Start Menu "songcharter: diagnostics" → `{app}\songcharter.cmd` with `diagnostics --out
    "{userdesktop}\songcharter-diagnostics.zip"`;
  - desktop `songcharter`, as an optional task, checked by default.
- `[Run]`:
  1. `powershell.exe -NoProfile -ExecutionPolicy Bypass -File "{app}\bootstrap.ps1" -Root "{localappdata}\songcharter"
     -App "{app}"`, with the description "Set up songcharter now (downloads about 3 GB with an NVIDIA GPU, under 1 GB
     without)". `postinstall`, checked by default, `waituntilterminated`, in a visible window. Also run silently
     when `/RUNBOOTSTRAP=1` is given: `{param:RUNBOOTSTRAP|0}` checked in `[Code]`, for CI.
  2. `{app}\songcharter.cmd`, "Start songcharter", `postinstall nowait skipifsilent`.
- `[UninstallDelete]`:
  - `filesandordirs`: `{localappdata}\songcharter\runtime`, `{localappdata}\songcharter\logs`,
    `{localappdata}\songcharter\doctor.json` and `{app}`. All of these come back with a bootstrap.
- `[Code]` `CurUninstallStepChanged(usUninstall)`:
  - asks one question: "Also delete the downloaded models (about 0.6 GB) and the song caches, library, uploads and
    exports?" Yes deletes `models`, `work`, `ac`, `trash`, `library`, `uploads`, `exports`, `replaced` and `ui.json`
    under `{localappdata}\songcharter`, and the root if it is then empty. No keeps them.
  - Silent uninstall keeps them, unless `/PURGE=1` (`{param:PURGE|0}`).
  - Never touches anything outside `{localappdata}\songcharter`: Clone Hero's songs stay.
- Upgrades: same `AppId`, so a newer `setup.exe` installs over the old. The bootstrap reruns through `[Run]`, and
  the launcher reruns it when `VERSION` changed.

### `NOTICE.txt`

Plain text, under 200 lines, one block per component: what it is, its licence, whether it is bundled in the
installer or downloaded on first launch, and from where. Check each licence on the package itself when building;
the "status" below is from DESIGN 4.2 and the planning job.

| component | status |
|---|---|
| songcharter | the owner's licence choice (M4-00, open question 2); until then "no licence chosen yet" |
| uv | bundled; MIT OR Apache-2.0 [doc, PyPI] |
| CPython | downloaded; PSF licence |
| PyTorch and the other Python packages | downloaded; each package's own licence |
| htdemucs_6s weights | downloaded; treated as non-commercial (DESIGN 4.2) |
| all-in-one-infer | MIT; its weights tagged MIT on the hub |
| ADTOF port and weights | treated as CC BY-NC-SA 4.0 |
| autochart's engine | AGPL-3.0-or-later; downloaded from https://github.com/dvar0/autochart at the pinned commit, whose full source is then on the PC |
| Fretformer 2 weights | CC BY-NC-SA 4.0, with autochart's attribution file |
| Beat This | MIT |
| Node.js | downloaded; its LICENSE |
| onnxruntime-node | MIT |
| scan-chart | MIT [doc, npm] |
| FFmpeg via imageio-ffmpeg | downloaded; imageio-ffmpeg is BSD-2-Clause [doc, PyPI], and the ffmpeg binary inside it has FFmpeg's own licence. Read which from the wheel when building. |

Close with:
- "songcharter is free and non-commercial in practice, because several of the weights it downloads are
  non-commercial";
- "Charts you make are yours; song.ogg is made from your recording, and sharing it is sharing the song."

### `packaging/ci/windows.d/20-installer.ps1`

1. `build.ps1 -Out $env:RUNNER_TEMP\dist`. The setup file exists, and the zip lists `songcharter-*/bootstrap.ps1`.
2. A silent install with the bootstrap into a fresh root (`SONGCHARTER_HOME` cannot move `{localappdata}`, so the
   CI user's real `%LOCALAPPDATA%\songcharter` is used, which is empty on a runner):
   `songcharter-setup-X.exe /VERYSILENT /SUPPRESSMSGBOXES /NORESTART /SP- /RUNBOOTSTRAP=1 /LOG=<file>`.
   - Exit 0;
   - `%LOCALAPPDATA%\songcharter\app\songcharter.cmd` exists;
   - `runtime\state\bootstrap.done` exists;
   - the Start Menu shortcut exists.
3. `cmd /c "%LOCALAPPDATA%\songcharter\app\songcharter.cmd" chart $env:SC_CLIP --out $env:RUNNER_TEMP\inst\Clip
   --device cpu` exits 0, and `check_gate.py` passes.
4. Portable: extract the zip to `$env:RUNNER_TEMP\portable\`, then run its `songcharter.cmd doctor`. It must
   reuse the runtime the installer set up: same `VERSION`, so no bootstrap runs. Exit 0.
5. A silent uninstall with `/PURGE=1` (`unins000.exe /VERYSILENT /SUPPRESSMSGBOXES /PURGE=1`). After it,
   `%LOCALAPPDATA%\songcharter` does not exist. A second install and an uninstall without `/PURGE` leave `models\`
   and `work\` and remove `runtime\` and `app\`.
6. Print the setup's size, the zip's size and the install's time.

## Done means

1. [dev] `build.ps1` cannot run in the container. The stage list can still be checked: a dry-run listing (`git
   ls-files` filtered by the same rules in a small Python helper, or `build.ps1 -ListOnly` under `pwsh` if
   available) shows no audio and no weights.
2. [CI-windows] After the push, the `windows` job is green with the `20-installer` hook. The report gives:
   - the setup and zip sizes;
   - the install and bootstrap times;
   - the uninstall checks.
3. [CI-windows] The installer's log shows no admin elevation (`PrivilegesRequired=lowest`), and the install
   location is under the runner user's `AppData\Local`.
4. [Windows HW] M4-08: SmartScreen shows the "More info > Run anyway" prompt once on the owner's PC and once on the
   friend's. Both install without admin. Uninstall asks its one question.
5. The setup and zip from the green run are kept as the run's artifacts, 14 days: they are M4-08's inputs.

## Depends on

- M4-03 (bootstrap, launcher, runtime);
- M4-05 (CI and its hooks);
- M4-06 (the `diagnostics` command used by the shortcut).
