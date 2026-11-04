# M4-06 report: the UI after the build (preview, zip, Clone Hero, diagnostics, the lyrics box)

Branch `m4-06-ui-results` (worktree `<scratchpad>/wt/m4-06`), from main at 0f714d4 (f5b37da plus a PROGRESS-only
commit). The order touches no file on the chart path, so no golden run was made.

## Commits

- 6eb824d M4-06 review fixes: the older chart's renames tested; a stranded .old named, and our leftovers dealt with
- 1db8138 ui: the preview's pages in page order, page_100 after page_99
- 785788d diagnostics: one rule for charts (the .chart suffix), so a mutation cannot hide behind a second
- 4bc3f8c M4-06: the page after the build: preview, zip, Clone Hero, diagnostics, the lyrics box
- 6bc8cff M4-06: clonehero.py (the Songs folder, install, the zip) and the diagnostics bundle

Each ends with the two trailer lines the brief gives.

## What changed

- **`songcharter/clonehero.py`** (new):
  - `songs_folder(home)`: ui.json's `clone_hero_songs` ("saved"), else in WSL `<Documents>/Clone Hero/Songs` from
    `wsl.shell_folder("Personal")` ("documents"), else `(None, "not found")`. settings.ini is not read.
  - `set_songs_folder(home, text)`: quotes and spaces dropped (Explorer's "Copy as path" adds quotes); a Windows path
    (`C:\...`, `\\server\...`) through `wsl.to_linux`; refused (InputError, 400) when it is empty, relative, does not
    exist, or a probe file cannot be written and deleted; saved to ui.json through a .part file, other keys kept.
  - `under_onedrive(path)`: under one of `wsl.onedrive_roots()`, compared NFC-casefolded (drvfs ignores case).
  - `windows_path(path)`: in WSL, `X:\...` for `/mnt/x/...`, `\\wsl.localhost\<distro>\...` for the Linux side;
    None outside WSL. Computed, no `wslpath -w` call (wsl.py has no such function and is out of scope).
  - `install(song_folder, songs, home, replace=False)`: 409 (`Exists`, with `ours`) when the target exists and is not
    ours, or replace is false; contents-only copy to `songs/.<name>.songcharter-<8 hex>.tmp`; every rename retried
    10 times 0.5 s apart on PermissionError or errno EACCES/EBUSY/EPERM; `Blocked` otherwise, with the .tmp removed.
  - `export_zip(folder, home)`: `package.zip_folder` into `exports/<name>.zip` through a .part file.
  - `describe(home)`: `{folder, windows_path, source, under_onedrive, guess}`; `guess` prefills the page's field.
- **`songcharter/diagnostics.py`** (new) and **`songcharter diagnostics --out PATH`** (cli.py): the bundle as the
  order lists it (doctor.json, runtime/runtime.json, ui.json, the newest 10 logs, doctor-now.json, clonehero.json with
  doctor.json's `wsl.documents`, and for the newest 5 work folders by their marker's `used`: pipeline.json,
  assemble.json, songcharter-work.json, preview.json (pipeline.json's preview: flags, remarks, or why none) and the
  built folder's report.json), plus MANIFEST.txt listing every file and every file left out with why. Every file is
  checked by name, size and first bytes: an audio extension or audio magic (check_no_audio.py's lists, copied, and a
  test checks they agree), `.chart`, `.mid`, `.png`, over 5 MB. Only named files are ever picked, so songs, stems,
  decodes and previews are never even opened. The CLI prints the path and, in WSL, its Windows path; exit 0, 2 (cannot
  write), 3 (bug).
- **`songcharter/ui/server.py`**: the routes (module docstring "After the build"):
  - `GET /api/jobs/current/results` (new, the Done screen's source: preview URLs, flags, remarks or the reason for no
    preview; pipeline.json's lyrics as counts; `installable`);
  - `GET /api/jobs/current/preview/<name>`: only `^(?:overview|page_\d{2,3})\.png$`, from the result's preview folder;
  - `POST /api/jobs/current/export/zip`, `GET /api/exports/<name>.zip` (attachment, `filename` and `filename*`);
  - `GET`/`POST /api/clonehero`; `POST /api/jobs/current/install {"replace"}` (200/400/403/409; no path taken from
    the client; one at a time under a lock); `POST /api/open {"what": "song"|"exports"}` (new name: the order names
    the action, not the route); `GET /api/diagnostics`.
- **`songcharter/ui/jobs.py`**: `lyrics` option (None when absent or blank; not text gives 400 naming the type only;
  `Options(...).check()` sees it, so a text with no word gives "the lyrics hold no word to time"). `ChartOptions.lyrics`
  has `repr=False`; `as_dict()` gives `lyrics: true/false`. The job writes the text into a memfd (in memory) and passes
  it to the child with `pass_fds`, as `--lyrics=/dev/fd/<n>`, read by the CLI's own `read_lyrics`; the server closes
  its copy at once. That start is proc.start's three lines with `pass_fds` added (proc.py is outside the order).
  `Job.result()` gives the result event.
- **`songcharter/ui/static/`**: the "Lyrics (optional)" fieldset with "Paste lyrics" and the order's sentence; the
  Done screen (lyrics line and low-confidence note, the overview linked full size, page thumbnails, the legend
  sentence, "Worth a look", "No preview: <why>", "Play it": the install button with the path, the folder field with
  the order's example when none is known, "Replace the older chart?" on 409 for our own folder, the Blocked messages
  with "Save the zip" and the OneDrive line, "Done. In Clone Hero, open Settings > General and press Scan Songs.",
  "Open folder", "Save as a zip" with the sentence under it, "Open the exports folder"); the footer's "Diagnostics" with
  "This file holds logs and settings, no audio." No inline script or style (the CSP test still passes).
- **`packaging/ci/linux.d/60-results.sh`** (new, executable): the order's [CI] check; see below.
- **Tests:** `tests/test_clonehero.py` (27), `tests/test_diagnostics.py` (6), `tests/test_ui_server.py` (+10 tests,
  and the guard test now covers every new POST).

## Choices the order did not spell out (for the reviewer)

1. **A replace renames the old folder aside first.** The order says: move the old folder to `replaced/<stamp>/<name>`
   (shutil.move), then rename the new one into place. I rename the old one to `songs/.<name>.songcharter-<hex>.old`
   (a same-filesystem rename, retried), rename the new one into place, then `shutil.move` the `.old` to
   `replaced/<stamp>/<name>`. The end state is the order's. Why: shutil.move from /mnt/c to ext4 is a copy then a
   delete, and a delete that OneDrive blocks halfway would leave a half-deleted chart in Songs; and with the order's
   sequence a blocked rename into place leaves Songs without the song. Here a blocked rename puts the old one back
   (tested). If the final move to `replaced/` fails, the install still succeeds and answers a `note`; the `.old`
   dot-folder then stays in Songs, where Clone Hero may list it (it scans subfolders) [inference, untested].
2. **No `shutil.copytree`.** The order names `shutil.copytree(src, tmp, copy_function=shutil.copyfile)`, but copytree
   still calls `copystat(src, dst)` on every folder it makes (Python's `shutil._copytree`), which is what the order
   wants to avoid. `copy_contents` makes the folders with `os.mkdir` and copies files with `shutil.copyfile` (a test
   makes copystat, copy2, copymode and copytree raise, and the install still works).
3. **Failures other than the three errnos**, and a failing copy, are `Blocked` at once (no retry): the zip is offered
   for any write Windows refuses (Controlled Folder Access, a full disk).
4. **A chart that failed its gate is neither exported nor installed** (400): its `.failed` folder is for a look. The
   Done screen still shows its preview and lyrics line, without the "Play it" box.
5. Signatures take the home: `songs_folder(home, ...)`, `install(song_folder, songs, home, replace=False)`.
6. The export name check refuses separators, NUL and a leading dot, then requires the file's parent to be
   `exports/`; it does not refuse `..` inside a name, since a song folder may be called "Wait... What" (tested).
7. Preview pages accept 2 or 3 digits (`page_100.png` for a song over 99 minutes; preview.py writes `{:02d}`).

## Checks

- **The full suite** (dev container, at 785788d, under the heavy-job lock):
  `SONGCHARTER_SCAN_CHART=<repo>/tools/scan-chart/scan.cjs tools/heavy.sh <venv python> -m pytest
  -q -p no:cacheprovider --basetemp=/dev/shm/m4-06/pt-suite` → `799 passed, 4 skipped in 569.80s (0:09:29)`.
  The last commit (1db8138) changes one line of server.py and its test: `pytest tests/test_ui_server.py` → `43 passed
  in 12.87s` (and that test fails without the line).
- **The order's tests alone:** `pytest tests/test_clonehero.py tests/test_diagnostics.py tests/test_ui_server.py
  tests/test_ui_jobs.py` → `111 passed in 24.41s` (before the last two commits; each file rerun after them).

### New tests, and the tests of the tests

Each mutation below was applied to a copy of the code and the named test file run (`<scratchpad>/m4-06-mutate.py`,
the last one by hand). All 31 in the table are caught. The first pass (31 mutations) found three survivors: `NEVER_NAMES`'s `notes.chart` was also refused by the
`.chart` suffix, so it was removed (commit "diagnostics: one rule for charts"); the export route's two checks (no
separator; parent is `exports/`) each cover the other, so removing either alone is not observable, and removing both
is caught.

| mutation | file | caught by |
|---|---|---|
| no retry (1 try) | clonehero | test_clonehero (EBUSY 3 times, then installs) |
| EBUSY not retried | clonehero | test_clonehero |
| a folder not ours replaced | clonehero | test_clonehero (another charter, no report.json, a file) |
| .tmp left on Blocked | clonehero | test_clonehero |
| copy by shutil.copytree | clonehero | test_clonehero (copystat refused) |
| ours without report.json | clonehero | test_clonehero |
| no write probe | clonehero | test_clonehero |
| quotes kept on a pasted path | clonehero | test_clonehero |
| OneDrive prefix without "/" | clonehero | test_clonehero (OneDriveX) |
| Documents before the saved folder | clonehero | test_clonehero |
| old chart not put back on a blocked replace | clonehero | test_clonehero |
| old chart not moved to replaced/ | clonehero | test_clonehero |
| no audio magic test | diagnostics | test_diagnostics (the renamed WAV) |
| no 5 MB limit | diagnostics | test_diagnostics (the 6 MB log) |
| 11 logs | diagnostics | test_diagnostics |
| oldest work folders | diagnostics | test_diagnostics |
| PNG allowed | diagnostics | test_diagnostics |
| charts allowed | diagnostics | test_diagnostics |
| no documents in clonehero.json | diagnostics | test_diagnostics |
| preview pattern loosened | server | test_ui_server |
| export: no separator check and no parent check | server | test_ui_server |
| a failed gate exported/installed | server | test_ui_server |
| Blocked without the zip | server | test_ui_server |
| /api/open on any folder | server | test_ui_server |
| the lyrics text in the job's records | jobs | test_ui_server |
| the memfd left open in the server | jobs | test_ui_server |
| blank lyrics kept | jobs | test_ui_server |
| the lyrics value in the 400 message | jobs | test_ui_server |
| the lyrics not passed to the child | jobs | test_ui_server |
| the lyrics not checked by Options.check | jobs | test_ui_server |
| preview pages sorted by name | server | test_ui_server (page_11 against page_100; found not to fail at first, the test fixed) |

The Done screen's JavaScript has no unit test; it was checked through the screenshots below.

### Manual (dev container)

- **The hook, run locally** as the manual check (`CI_PY=<venv python> CI_TMP=/dev/shm/m4-06/ci/tmp
  CI_ART=/dev/shm/m4-06/ci/art CI_CLIP=<make_clip.py's clip> tools/heavy.sh bash -euo pipefail
  packaging/ci/linux.d/60-results.sh`): exit 0. A real `songcharter ui` charted the clip through the API (bass and
  drums on the CPU, the guitar left out as on the runner), the zip exported and downloaded, a Songs folder at
  `.../Jörg's Söngs/Clone Hero/Songs` refused while missing (400) then set, the clip installed (200, four files), again
  (409, ours), replaced (200, the old one in `replaced/`), no `.tmp`/`.old` left. Last lines:

      60-results: the diagnostics bundle: 11 files
      60-results: the lyrics: not added (torchaudio is not installed: pip install songcharter[lyrics]); warned: ['lyrics: not added (torchaudio is not installed: pip 
      60-results: no pasted word in 22 logs, records and answers
      60-results: the diagnostics bundle: 12 files
      check_no_audio: ok, 1 files and 12 archive members, no audio (/dev/shm/m4-06/ci/tmp/d.zip)
      check_no_audio: ok, 12 files, no audio (/dev/shm/m4-06/ci/tmp/d)
      check_no_audio: ok, 1 files and 11 archive members, no audio (/dev/shm/m4-06/ci/art/60-results/chart-diagnostics.zip)
      check_no_audio: ok, 1 files and 12 archive members, no audio (/dev/shm/m4-06/ci/art/60-results/lyrics-diagnostics.zip)
      60-results: ok
      exit 0

  The API is driven with Python's urllib in the hook (JSON and the event stream); curl drove the screenshot run's
  upload, job, results and install (below).
- **Lyrics, wiring only.** torchaudio is not installed in the dev venv, so the aligner was **missing**: the chart was
  made without lyrics, with the warning "lyrics: not added (torchaudio is not installed: pip install
  songcharter[lyrics])", and the Done screen says "Lyrics not added: torchaudio is not installed: ...". In CI (where
  torchaudio is installed) the hook's lyrics run sets SONGCHARTER_OFFLINE=1, so the weights are out of reach and
  nothing is downloaded. The aligner never ran for real; the 1.26 GB weights were not fetched. The pasted text was
  made-up words only. The real CLI read the text from the memfd (the job's log shows `--lyrics=/dev/fd/<n>`), and no
  pasted word was found in 22 logs, records and answers, nor in the bundles.
- **`songcharter diagnostics --out /dev/shm/m4-06/d.zip`** on the hook's home and cache: exit 0;
  `check_no_audio.py /dev/shm/m4-06/d` (unpacked): "ok, 13 files, no audio"; no pasted word in it. Files: MANIFEST.txt,
  clonehero.json, doctor-now.json, ui.json, 4 logs, and work/clip-<key>/{assemble,pipeline,preview,report}.json and
  songcharter-work.json.
- **Screenshots** (headless Chromium through Playwright, a real job on the same home with lyrics pasted; looked at):
  `/dev/shm/m4-06/shots/done.png` (the Done screen: lyrics line, overview, page thumbnail, legend, "Worth a look:
  Nothing flagged.", "Play it" with the folder, the zip sentence, the footer), `install-409.png` (the page's own
  click: "This song is in Clone Hero already (...). Replace the older chart?" with "Replace it"),
  `install-done.png` ("Done. In Clone Hero, open Settings > General and press Scan Songs." after Replace),
  `options.png` (the lyrics box and its sentence). The only console error was the browser logging the 409 itself.
  These live in /dev/shm and go with the machine; copy them before relying on them.

### CI

- **Run 41782384888 on 1db8138: success** (both jobs): https://github.com/neb882/song-charting/actions/runs/41782384888.
  The suite there: `799 passed, 4 skipped in 238.71s`. The hooks: `all 5 Linux hooks passed: 10-lanes.sh 9s
  20-device.sh 4s 30-install.sh 181s 40-ui.sh 19s 60-results.sh 46s`. Read from `gh run view --log --job`, the order's
  own hook ran whole:
  - `76 passed in 12.85s` (its tests);
  - the chart phase: the clip done, its preview, the zip downloaded, `400` for a missing Songs folder, installed into
    `.../ci-tmp/Jörg's Söngs/Clone Hero/Songs/Unknown - clip` with its four files, `409`, `replaced: 200`;
  - the lyrics phase: `the lyrics: not added (the aligner's weights are not in .../models/lyrics and
    SONGCHARTER_OFFLINE=1)`, `no pasted word in 22 logs, records and answers`;
  - `check_no_audio: ok` on `d.zip`, `d/` (unpacked), `chart-diagnostics.zip` and `lyrics-diagnostics.zip`;
    `60-results: ok`; then the artifacts' own check: `ok, 35 files and 35 archive members, no audio`.
- Run 41781352824 on 785788d was cancelled by the workflow's concurrency group when 1db8138 was pushed (its windows
  job had passed).

## Not done, uncertain, or left for others

- **Untested on Windows** (M4-08's): the copy and renames under /mnt/c (drvfs), the retry under OneDrive's sync or
  antivirus, a OneDrive-moved Documents found through the registry, `explorer.exe` opening a folder by its Windows
  path (`wsl.open_url` with `C:\...` or `\\wsl.localhost\...`), the zip landing in Windows' Downloads, the browser's
  handling of `Content-Disposition` with a non-ASCII name. `windows_path` assumes WSL's drives are mounted under
  `wsl.MNT_C`'s parent (`/mnt`), as wsl.py does.
- Clone Hero's `settings.ini` is not read (the order: M4-08 records its keys).
- A move of the older chart to `replaced/` that fails leaves a `.<name>.songcharter-<hex>.old` folder in Songs (choice
  1); Clone Hero may list it.
- `GET /api/clonehero` and the diagnostics ask Windows for the OneDrive roots each time (three cmd.exe calls); only
  Documents is cached for the server's life.
- The lyrics are passed through a memfd, which is Linux only (the UI is POSIX already: proc.py).
- `songcharter/ui/__init__.py`'s docstring lists the home's layout and should gain `exports/`, `replaced/` and
  `ui.json`; it is outside the order's files.

## Doc edits the order leaves to the orchestrator

- **DESIGN 4.5:** a "Built in M4-06" bullet (the Done screen: the static preview, its flags and legend; the zip;
  the install as built: the detection order, settings.ini not read, the retried renames, the old chart to
  `replaced/`, Blocked offers the zip, failed-gate charts not installed; "Open folder"; the diagnostics bundle and what
  it never holds; the lyrics box and the memfd); screen 6's "Install into Clone Hero" text still says settings.ini,
  `SHGetKnownFolderPath` and a portable `PlayerData`, which v0.1 does not do; "Preview in Clone Hero" and "Open polish
  workspace" are not built; the **Status** line ("none of the UI is built") is stale since M4-04.
- **README:** the page's last steps (preview, zip, install, Scan Songs), the lyrics box, and `songcharter diagnostics
  --out PATH` (what it holds, that it holds no audio).
- **PROGRESS:** M4-06 leaves `in_flight`; deferred: the Windows checks above (to M4-08), the `.old` edge, settings.ini;
  the decision that a failed-gate chart is not exported or installed.
- **M4-08:** add the checks listed under "Untested on Windows".
- **`docs/reports/m4-06.md`:** this report.

Scanned before the final push: `git diff main...HEAD` and the commit messages hold no lyrics (only made-up words such
as "zorp"), no audio, no model names (only the required trailers), and no personal details (fixtures use made-up
names: "Jörg", "Jorg", "Fixture Band", "Contoso", `/home/sc`).

## Review fixes

The review (`m4-06.review.md`): no major finding, two minor. Both choices the builder flagged hold (the replace
sequence; no export or install of a failed-gate chart). Fixed in 6eb824d.

- **F1 (test gap):** `failing_rename` in tests/test_clonehero.py now refuses any of the three renames (into place
  `failures`, the older chart aside `aside`, its put-back `back`). New tests: the rename aside refused 3 times then
  succeeding (Installed, the older chart in replaced/); the put-back refused 3 times then succeeding (Blocked, Songs
  holds the older chart whole, no dot-folder left); `shutil.move` raising OSError (Installed, the new chart in place,
  a `note` naming the `.old` and the replaced folder). The reviewer's three surviving breaks now fail:
  `aside-no-retry`, `putback-no-retry`, `move-note-swallowed-fail` all caught.
- **F2:**
  - When the put-back is refused too, `Blocked` names the `.old` folder (`Blocked.old`, and in `why`: "...;
    putting the older chart back was refused too, so it is in <.old> for now: the next install of this song moves it
    to songcharter's replaced folder"). The 403 carries it as `why`/`error` and `older` (its Windows path in WSL), and
    the page adds "Your older chart is kept in <path> for now: the next install moves it out of the Songs folder."
  - On the next install of that name that goes ahead (after the 409 check), our own leftovers for it are dealt with
    first (`leftovers`, `_tidy`): each `.<name>.songcharter-<8 hex>.old` or `.tmp` that is a real folder (not a link)
    and `is_ours` (song.ini `charter = songcharter` and report.json). A `.old` goes to `replaced/<stamp>/<name>`
    (`<stamp>-<its 8 hex>` when taken) as a replace would; a `.tmp` is deleted. What stays is said in `note`; the
    moved older chart is `replaced` when the install replaced nothing itself.
  - Never touched (tested): another charter's `.old`, a partial `.tmp` (notes.chart only: not ours by the marks),
    another song's leftover, a name with no 8-hex tag, another suffix, a name without the leading dot, and a link
    named like a leftover (the folder it points to is untouched).
  - Tests: test_clonehero.py `test_a_blocked_replace_that_cannot_put_back_names_the_old_folder` (the retry installs
    and moves the `.old` to replaced/), `test_our_own_leftovers_go_and_nothing_else_is_touched`,
    `test_a_move_to_replaced_that_fails_still_installs_with_a_note` (the next replace moves the stranded `.old` too);
    test_ui_server.py `test_a_blocked_replace_names_where_the_older_chart_is` (the 403's `older` and `why`, then the
    retry's 200).
- **Breaks of the new code**, each caught (`<scratchpad>/m4-06-mutate.py`): the `.old` left out of `why`, `Blocked`
  without `old`, no tidy, `.tmp` leftovers kept, leftovers not checked with `is_ours`, leftovers followed through
  links, leftovers of any song's name, a leftover `.old` deleted instead of moved, the 403 without `older`.
- **Left as is:** a partial `.tmp` (a run stopped mid-copy, without song.ini or report.json) is not ours by the
  marks, so it stays in Songs; whether Clone Hero lists dot-folders at all is M4-08's to see.
- **Checks:** `pytest tests/test_ui_server.py tests/test_clonehero.py tests/test_diagnostics.py tests/test_ui_jobs.py`
  -> `117 passed in 27.05s` (the files covering the diff). The full suite was not rerun locally; CI runs it.
- **CI:** run 41785468704 on 6eb824d: **success**, both jobs
  (https://github.com/neb882/song-charting/actions/runs/41785468704). Suite `805 passed, 4 skipped in 292.77s`;
  `all 5 Linux hooks passed: ... 60-results.sh 51s`; from its log, the hook's `installed again: 409`, `replaced: 200`,
  the lyrics run (`not added (the aligner's weights ... SONGCHARTER_OFFLINE=1)`, `no pasted word in 22 logs, records
  and answers`) and `60-results: ok`.
