# M4-06: the UI after the build: preview, export, Clone Hero, diagnostics

**Branch:** `m4-06-ui-results`, from `main` after M4-04 has merged. **Wave 3**, beside M4-05. **Agent:**
`sc-builder`, then `sc-reviewer` and `sc-inspector`.

## Intent

The last three steps of the friend's flow:
- look at the preview;
- put the chart into Clone Hero with one click (or save a zip);
- when something goes wrong, send the owner one file that explains it and holds no audio.

DESIGN 4.5's export rules apply:
- copy to a temporary folder, then rename;
- a duplicate gets 409;
- an unknown folder is refused;
- offer the zip when Defender's Controlled Folder Access blocks the write.

## Scope

Creates:
- `songcharter/clonehero.py`, `songcharter/diagnostics.py`;
- `tests/test_clonehero.py`, `tests/test_diagnostics.py`;
- `packaging/ci/linux.d/30-diagnostics.sh`, `packaging/ci/windows.d/30-diagnostics.ps1` (once M4-05 has made the
  hook folders; if this order merges first, the director adds them at M4-05's merge).

Changes:
- `songcharter/ui/server.py`, `ui/jobs.py`, `ui/static/*` (the routes and screens below);
- `songcharter/cli.py`: a `diagnostics` command;
- `tests/test_ui_server.py`.

Must not touch:
- `pipeline.py`, `engines/*`, `packaging/windows/`, `.github/`;
- `docs/`.

## Spec

### Preview

- `GET /api/jobs/current/preview/<name>` serves `<name>` from the job's `result.preview` folder (the work folder's
  `preview/`). Only names matching `^(overview|page_\d{2})\.png$` that are in `result.preview.pages` or are its
  overview; anything else is 404.
- The Done screen shows:
  - the overview image, then the pages as thumbnails that open full size;
  - the preview's flags (`result.preview.flags`) as a list under the heading "Worth a look";
  - "No preview: <why>" when `result.preview` is null, from the warning;
  - a sentence explaining the plots in plain words: "Blue bars are notes per beat; red marks a stretch where the
    instrument plays but the chart has no notes", from `preview.py`'s own legend.

### Export: zip

- `POST /api/jobs/current/export/zip`:
  - `package.zip_folder(folder, <home>\exports\<folder name>.zip)`, replacing an older zip of that name;
  - answers `{"url": "/api/exports/<name>.zip"}`.
- `GET /api/exports/<name>.zip`: `Content-Disposition: attachment`. Only names in `<home>\exports\`; a `..` or a
  separator is 404.
- The button's caption: "Save as zip". Under it, always: "The zip holds song.ogg, made from your recording.
  Sharing it is sharing the song."

### Install into Clone Hero (`songcharter/clonehero.py`)

- **`songs_folder(settings) -> tuple[Path | None, str]`**, in order:
  1. the folder saved in `<home>\ui.json` (`{"clone_hero_songs": ...}`) when it still exists: `"saved"`;
  2. `<Documents>\Clone Hero\Songs` when it exists: `"documents"`. `<Documents>` comes from
     `SHGetKnownFolderPath(FOLDERID_Documents)` through ctypes on Windows (it follows a OneDrive move), and
     `~/Documents` elsewhere;
  3. `(None, "not found")`.

  `settings.ini` is not parsed in v0.1: its keys are not verified [untested]. M4-08 records them on a real install.
- **`set_songs_folder(path)`:**
  - refuses a path that does not exist or is not a folder: 400 "That folder does not exist";
  - checks it can be written by creating and deleting `.songcharter-write-test`;
  - saves it to `ui.json` atomically.
- **`install(song_folder, songs, replace=False) -> Path`:**
  - The target is `songs \ <the song folder's own name>`, which is `safe_name(f"{artist} - {title}")` (M4-04).
  - **Duplicates:**
    - if the target exists and `replace` is false: `Exists(ours=...)` (HTTP 409);
    - `ours` is true when the target's `song.ini` says `charter = songcharter` and it holds `report.json`;
    - `replace` is refused for a folder that is not ours: 409 "A song folder with that name is already there and
      was not made by songcharter".
  - **Copy:** to `songs \ .<name>.songcharter-<8 hex>.tmp` (`shutil.copytree`), then:
    - if replacing, `os.replace` the old folder to `<home>\replaced\<yyyyMMdd-HHmmss>\<name>`, with a cross-volume
      fallback of `shutil.move`;
    - then `os.replace` the temporary folder to the target.
    - The temporary folder is removed on any error.
  - **Blocked writes:** a `PermissionError` while writing under `songs` (Controlled Folder Access, or a read-only
    folder) raises `Blocked`. The server answers 403 `{"blocked": true, "why", "zip_url"}` after making the zip; the
    page says "Windows blocked songcharter from writing to that folder. Save the zip and extract it there
    yourself, or allow songcharter in Windows Security > Ransomware protection."
- **Routes:**
  - `GET /api/clonehero` gives `{"folder", "source", "exists"}`;
  - `POST /api/clonehero` with `{"folder"}`;
  - `POST /api/jobs/current/install` with `{"replace": bool}` gives 200 `{"installed": path}`, 409, 403 or 400.
  - The install endpoint takes no target path from the client: only the saved or detected folder.
- **The page:**
  - an "Install into Clone Hero" button showing the target folder;
  - when no folder is known, a text field "Your Clone Hero Songs folder", prefilled with the detected guess, and
    "Use this folder";
  - on 409 for our own folder: "Replace the older chart?" (yes posts `replace: true`);
  - on success: "Done. In Clone Hero, open Settings > General and press Scan Songs."
- **"Open folder" buttons** for the installed song, the library song folder and the exports folder:
  `POST /api/open {"what": "installed"|"library"|"exports"}`. Only those three known paths, never a client-given
  one. `os.startfile` on Windows, `xdg-open` elsewhere.

### Diagnostics (`songcharter/diagnostics.py`, `songcharter diagnostics --out PATH`, `GET /api/diagnostics`)

- **`bundle(home, out_zip, jobs=5) -> dict`** writes a zip with:
  - `doctor.json` and `runtime\runtime.json`;
  - the newest 10 files of `logs\`;
  - `ui.json`;
  - for the newest 5 work folders under the cache root: their `pipeline.json`, `assemble.json`,
    `songcharter-work.json`, `preview\` flags (the `report["preview"]` entry, not the PNGs), and the built song
    folder's `report.json` (read from `pipeline.json`'s output path);
  - a fresh `device.report(full=False)` as `doctor-now.json`;
  - a `MANIFEST.txt` listing every file with its size.
- **Never:**
  - any file with an audio extension, or one that `check_no_audio`'s magic numbers flag (copy that test into
    `diagnostics.py`; CI's script and this one must agree);
  - `notes.chart`, stems or PNGs;
  - anything over 5 MB.
- The person's user name stays in paths: the owner needs them for path-length problems.
- **Routes and button:** `GET /api/diagnostics` streams it as `songcharter-diagnostics-<yyyyMMdd-HHmmss>.zip`. The
  page has a "Diagnostics" link in the footer, with "This file holds logs and settings, no audio. Send it to whoever
  helps you." The CLI writes it to `--out` and prints the path.

## Done means

[dev] In the dev container:

1. The full suite passes, with new tests:
   - `test_clonehero.py`, on temporary folders:
     - detection order;
     - a refused missing folder;
     - install, then 409, then a replace of our own folder (the old one in `replaced\`);
     - refusing to replace a folder whose `song.ini` has another charter;
     - a `PermissionError` stand-in giving `Blocked` and leaving no `.tmp` folder;
     - no client path accepted by the install route.
   - `test_diagnostics.py`: a fixture home with `.wav`, `.ogg`, a renamed WAV, PNGs, `notes.chart` and a 6 MB log
     gives a zip with none of them, and with the JSON files and `MANIFEST.txt`.
   - `test_ui_server.py` additions:
     - preview names outside the pattern give 404;
     - an export name with `..` gives 404;
     - `/api/open` with an unknown `what` gives 400;
     - every new POST route is guarded (403 without the header).
2. Manual, in the container: chart the clip through the page (curl as in M4-04). Then:
   - export the zip; install into a temporary "Songs" folder set by `POST /api/clonehero`, check 409, replace;
   - `songcharter diagnostics --out /dev/shm/m4-06/diag.zip`, then `packaging/ci/check_no_audio.py` on its
     extracted folder exits 0.
3. Screenshots of the Done screen with the preview, from a headless browser (`chromium --headless --screenshot`, if
   present in the container; otherwise say so), looked at and attached to the report.

[CI-linux] and [CI-windows] (hooks):
- `30-diagnostics` makes the bundle after the clip run and runs `check_no_audio.py` on it;
- on Windows, it also installs the clip into `$env:RUNNER_TEMP\CH\Songs` through the API, and checks the folder's
  four files.

[Windows HW] M4-08:
- the friend installs a chart into his real Clone Hero with one click, and it plays after Scan Songs;
- the detected folder is right, or he sets it once;
- Controlled Folder Access, if on, gives the zip route.

## Depends on

- M4-04 (the server, jobs, the result event);
- M4-05 for the hook folders (or the director adds the hook files at merge).
