# M4-06: the UI after the build: preview, export, Clone Hero on Windows, diagnostics

**Branch:** `m4-06-ui-results`, from `main` after M4-04 has merged. **Wave 3**, beside M4-05. **Agent:**
`sc-builder`, then `sc-reviewer` and `sc-inspector`. May push its branch to run CI.

## Intent

The last steps of the friend's flow:
- look at the preview;
- put the chart into his Clone Hero Songs folder on Windows with one click, or save a zip;
- when something goes wrong, send one file that explains it and holds no audio.

songcharter runs in WSL and Clone Hero on Windows, so the Songs folder is reached under `/mnt/c`. Its location comes
from the Windows side (Documents may have moved to OneDrive), and Windows' rules apply to the names written there.
DESIGN 4.5's rules hold:
- copy to a temporary folder, then rename;
- a duplicate gets 409;
- a folder the user did not choose is refused;
- a blocked write offers the zip.

## Scope

Creates:
- `songcharter/clonehero.py`, `songcharter/diagnostics.py`;
- `tests/test_clonehero.py`, `tests/test_diagnostics.py`;
- `packaging/ci/linux.d/60-results.sh`.

Changes:
- `songcharter/ui/{server.py,jobs.py,static/*}`;
- `songcharter/cli.py` (`diagnostics`);
- `tests/test_ui_server.py`.

Must not touch: `pipeline.py`, `engines/*`, `wsl.py`, `device.py`, `packaging/linux/`, `docs/`.

## Spec

### Preview

- `GET /api/jobs/current/preview/<name>` serves only `overview.png` and `page_NN.png` from the job's
  `result.preview` folder (the work folder's `preview/`). Anything else is 404.
- **The Done screen:**
  - the overview, then the pages as thumbnails that open full size;
  - the preview's flags as a list titled "Worth a look", or "No preview: <why>";
  - a plain sentence from `preview.py`'s legend: "Blue bars are notes per beat; red marks a stretch where the
    instrument plays but the chart has no notes".

### Zip export

- `POST /api/jobs/current/export/zip` runs `package.zip_folder(folder, $SONGCHARTER_HOME/exports/<name>.zip)` and
  answers `{"url": "/api/exports/<name>.zip"}`.
- `GET /api/exports/<name>.zip` downloads it (`Content-Disposition: attachment`), into the Windows browser's
  Downloads. Only names inside `exports/`; `..` or a separator gives 404.
- Under the button, always: "The zip holds song.ogg, made from your recording. Sharing it is sharing the song."

### Clone Hero (`songcharter/clonehero.py`)

- **`songs_folder() -> (path | None, source)`**, first that exists:
  1. the folder saved in `$SONGCHARTER_HOME/ui.json` (`"clone_hero_songs"`): `"saved"`;
  2. in WSL, `<Documents>/Clone Hero/Songs`, with `<Documents>` from `wsl.shell_folder("Personal")` (the registry,
     so it follows OneDrive): `"documents"`;
  3. `(None, "not found")`.
  - Clone Hero's `settings.ini` is not parsed in v0.1 (its keys are unverified); M4-08 records them.
- **`set_songs_folder(path)`:**
  - accepts a Linux path, or a Windows path (`C:\...`, turned into `/mnt/c/...` with `wsl.to_linux`);
  - refuses one that does not exist (400);
  - checks that a file can be written and deleted there;
  - saves it to `ui.json` atomically.
- **`under_onedrive(path)`:** whether `path` lies under one of `wsl.onedrive_roots()`. Shown in the UI, and recorded
  in the diagnostics.
- **`install(song_folder, songs, replace=False)`:**
  - **The target** is `songs/<song folder's name>`, which M4-04 already made with `cache.safe_name`: safe for Windows,
    40 characters at most.
  - **409** when it exists and `replace` is false, with `ours`: its `song.ini` says `charter = songcharter` and it
    holds `report.json`. A replace of a folder that is not ours is refused (409).
  - **The copy** goes to `songs/.<name>.songcharter-<8 hex>.tmp` with `shutil.copytree(src, tmp,
    copy_function=shutil.copyfile)`: contents only, no `copystat`, whose timestamps and modes are what drvfs refuses
    under `/mnt/c`. Then:
    - when replacing, the old folder moves to `$SONGCHARTER_HOME/replaced/<yyyyMMdd-HHmmss>/<name>` (`shutil.move`:
      it crosses from `/mnt/c` to ext4);
    - then the rename into place.
  - **Every rename under `songs` is retried for about 5 s** (10 tries, 0.5 s apart) on `PermissionError` or `OSError`
    with errno EACCES, EBUSY or EPERM (the advisor's finding 7). OneDrive's sync and antivirus can hold a new folder
    briefly; through WSL that shows as one of these.
  - **`Blocked`** if it still fails, and the temporary folder is removed. The server answers 403 `{"blocked": true,
    "why", "zip_url", "under_onedrive"}` after making the zip.
  - **The page says:**
    - "Windows did not let songcharter finish writing into that folder. Security software, or OneDrive syncing it,
      can do that.";
    - "Try again in a moment, or save the zip and extract it there yourself.";
    - when `under_onedrive`, also "Your Songs folder is inside OneDrive."
- **Routes:**
  - `GET /api/clonehero` gives `{"folder", "windows_path", "source", "under_onedrive"}`;
  - `POST /api/clonehero {"folder"}`;
  - `POST /api/jobs/current/install {"replace"}` gives 200, 400, 403 or 409.
  - The install route takes no path from the client.
- **The page:**
  - "Install into Clone Hero", showing the Windows path;
  - when no folder is known, a field "Your Clone Hero Songs folder (for example `C:\Users\you\Documents\Clone
    Hero\Songs`)", prefilled with the guess;
  - "Replace the older chart?" on 409 for our own folder;
  - on success: "Done. In Clone Hero, open Settings > General and press Scan Songs."
- **"Open folder"** for the installed song and the exports folder: `explorer.exe <windows path>` through `wsl.py`.
  Only those two known paths.

### Diagnostics (`songcharter/diagnostics.py`; `songcharter diagnostics --out PATH`; `GET /api/diagnostics`)

- **The zip holds:**
  - `doctor.json`, `runtime/runtime.json` and `ui.json`;
  - the newest 10 logs;
  - a fresh `device.report(full=False)` as `doctor-now.json`;
  - `clonehero.json`: `{folder, windows_path, source, under_onedrive}`, plus `doctor.json`'s `wsl.documents`
    (the raw registry value, its expansion, and the Linux path). A localized folder name decoded with the wrong code
    page then shows up as mojibake in the bundle (the advisor's finding 8);
  - for the newest 5 work folders: `pipeline.json` (with M4-02's samples and fallbacks), `assemble.json`,
    `songcharter-work.json`, the preview flags, and the built folder's `report.json`;
  - `MANIFEST.txt`.
- **Never:**
  - an audio extension, or audio magic bytes (the same test as `check_no_audio.py`);
  - `notes.chart`, stems or PNGs;
  - any file over 5 MB.
- The page's footer has "Diagnostics" with "This file holds logs and settings, no audio."
- Through the browser, the zip lands in Windows' Downloads. The CLI prints its path, and in WSL also its Windows path.

## Done means

[dev] In the dev container:

1. The suite passes, with new tests:
   - **`test_clonehero.py`,** on temporary folders and stand-in `wsl` functions:
     - detection order;
     - a Windows path turned into `/mnt/c/...`;
     - a missing folder refused;
     - install, then 409, then a replace of our own folder (the old one in `replaced/`);
     - refusing a folder with another charter;
     - a rename that fails 3 times with EBUSY, then succeeds, installs;
     - one that always fails gives `Blocked`, leaves no `.tmp`, and makes the zip;
     - `under_onedrive`;
     - a Songs folder named `Jörg's Söngs` with a space.
   - **`test_diagnostics.py`:** a fixture home with `.wav`, `.ogg`, a renamed WAV, PNGs, `notes.chart` and a 6 MB
     log gives a zip with none of them, and with the JSON files and the manifest.
   - **`test_ui_server.py` additions:** preview and export names outside their patterns give 404; every new POST is
     guarded; `/api/clonehero` refuses a missing folder.
2. Manual: chart the clip through the page with `curl`. Then:
   - export the zip;
   - set a temporary Songs folder, install, get 409, replace;
   - `songcharter diagnostics --out /dev/shm/m4-06/d.zip`, and `check_no_audio.py` on it unpacked.
3. A headless-browser screenshot of the Done screen (if a browser is in the container; otherwise say so), looked at
   and attached.

[CI] Hook `60-results.sh`: the tests; then a diagnostics bundle after the clip (`check_no_audio.py` on it), and the
clip installed through the API into `$CI_TMP/Jörg's Söngs/Clone Hero/Songs`, with its four files checked.

[Hardware] M4-08:
- the Songs folder is found on Windows, including a OneDrive-moved Documents, if a PC has one;
- the chart plays after Scan Songs;
- the zip lands in Downloads.

## Depends on

- M4-04: the server and jobs;
- M4-02: `wsl.py`.
