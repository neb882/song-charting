# M8-13 report: "Your charts", every chart in the library on the page

*Merged 2026-11-09 at 04ed46a (branch head 0a2b6f6; CI run 42602005179 green on Linux and Windows, the suite 1359 passed, every
hook). The review (an `sc-reviewer`, head 104deff): no major finding, three minor ones (F1 a chart deleted in Windows
after the list was read answered "no finished chart yet"; F2 the report.json shape check breakable with the tests
green, after which a wrong-shape report.json would empty the list with a 500; F3 the list folded on the first evening
when the library was empty at page load), all fixed; and M8-12's `test_the_stems_download` made to wait for the
server's delete after sending (the race was in the test). Safety, speed (400 charts in 0.92 s) and half-written
folders checked with nothing found.*

Builder's report. Branch `m8-13-your-charts` (worktree `<wt>/m8-13`), from main 4c5b7e3. Not merged.

## Commits

- c793b97 M8-13: the library's read and the routes by a chart's id
- 0b54b01 M8-13: "Your charts" on the page
- 357e35b M8-13: Your charts without a box in a box (the screens)
- ba7692d M8-13: DESIGN 4.5 and the guide: Your charts
- 104deff (head) M8-13: the test library's docstring wrapped

Files: `songcharter/ui/jobs.py`, `songcharter/ui/server.py`, `songcharter/ui/static/{app.js,index.html,app.css}`,
`tests/test_ui_library.py` (new), `tests/test_ui_server.py`, `docs/DESIGN.md` (4.5), `docs/guide/windows-wsl.md`.
Nothing else; `docs/PROGRESS.json` untouched (the orchestrator's, at the merge).

## What was built

1. **The read** (`jobs.library`, `GET /api/library` -> `{"charts"}`): `<home>/library/<16 hex>/<name>/` folders that
   hold a report.json, newest first by report.json's time; each `{"id", "folder", "name", "artist", "time",
   "readable", "ok", "audio", "stems", "look"}`. Name and artist from song.ini (the folder's name without them). Not
   listed: a folder without report.json (the " (stems)" folder, anything else), hidden folders (assemble's
   `.partial` staging), links, folders outside a 16-hex upload folder. A report.json that cannot be read (or has no
   gate) is listed as `readable: false` ("Can't be read"), never hidden.
2. **Ids, not paths:** a chart's id is `<16 hex>:<folder name>` (`jobs.LIBRARY_ID`; a safe name has no ":"),
   percent-encoded in URLs. `jobs.find_chart` finds it among the folders the read lists; nothing joins it into a
   path. `server.JOB_PATH` accepts it beside `current` and job ids, and `Handler._job` resolves it to
   `jobs.Charted` (a job-like object whose `result` is made from the folder: ok, folder, stems beside it, work and
   preview only while its work folder is kept). So the list's **Install** (its 409 asking to replace), **Open**
   (`/api/open {"what": "built", "job": <id>}`), **Download the stems** (`/export/stems`), and **Look**
   (`GET /api/jobs/<id>`, `/results`, preview, art, Listen, the zip) are M8-10's and M8-12's routes behind the same
   `_handle` guards. No new POST route.
3. **Look** only while the song's work folder is in the cache (`cache.by_key` by the upload's 16 hex, the song file's
   key) **and** its pipeline.json's `assemble.folder` is this chart's folder. Else no Look, and the list says nothing
   is lost.
4. **The page:** a `#charts-box` section after the Done screen (so under the drop zone and the queue on the start
   screen), shown with the start, progress and Done screens, hidden over the options form and when there is no chart.
   A `<details>` "Your charts (n)": open with up to 6 charts (`CHARTS_OPEN`), folded beyond; his own open/fold kept
   when the list is read again. A "Your charts (n)" button on the Done screen (beside "Add a song") and under the
   queue's list opens it and scrolls to it. Each row: name, artist, verdict ("Passed its check" / "Did not pass its
   check: kept for a look, not for Clone Hero" / "Can't be read"), the date, "one audio file" / "a sound file per
   instrument", "stems saved"; Install (passed only), Open, Download the stems (when saved), Look (when kept). Two
   lines: without Look nothing is lost; nothing is deleted from here (Open, then delete in Windows). The list is read
   at the start and whenever the queue's list changes (a song that ended is a new chart).
5. **Nothing deleted**: no delete route or button; the tests check the library folders are still there.

## Interpretations to check

- **"the date (report.json's time)":** report.json records no time of its own, so it is the file's modification time
  (assemble writes it last into the staging folder before the rename).
- **Look's condition is stricter than `cache.by_key` alone:** the work folder must also be this chart's (its
  pipeline.json's `assemble.folder`). A later chart of the same song with other options (another library folder, same
  upload key) takes the work folder, its preview, its lyrics counts; showing those under the earlier chart would be
  wrong, so the earlier one is listed without Look.
- **`/api/open`'s `job`, when given, must now be an id** (`current`, a job id or a library id): a path or junk is
  refused (400 "job is a chart's id: no such chart"). Before, a non-id fell back to the current chart; M8-10's test
  asserted that ("../x" -> the current one) and is updated. The order's "a path or unknown id refused" asked for it.
  Omitting `job` still means the current chart.
- **Install from the list without Look:** `installFrom`'s messages for an unknown Songs folder and a blocked write
  sent him to Look; for a row without Look they now say to give the folder on the next chart's Done screen, and a
  blocked write offers "Save the zip" (the 403's own zip) in the row. The queue's messages are unchanged.
- **Where the list sits:** after the Done screen in the page, so on the Done screen it is below "Add a song"; the
  "Your charts" button reaches it. Shown on the progress screen too (folded when long).
- **"Can't be read"** for a report.json that is not JSON or has no boolean gate; such a chart offers Open only.

## Checks

- **New tests** (`tests/test_ui_library.py`, 8 tests): the read on a made-up library (four charts: split with stems
  and its work folder; failed one-file with stems; damaged report.json; an older one whose work folder a later chart
  took; plus four non-charts), newest first; the library's suffixes equal the pipeline's; `find_chart` refuses paths,
  climbs, the stems folder, staging, unknown uploads; Install by id and its 409 and replace, a failed one and unknown
  ids refused, path-shaped URLs 404; Open by id, a path / junk / unknown id refused; the stems by id (a failed one's
  too), Look's snapshot and results with the preview by id, none without the work folder, Listen 400 then; the
  guards (Host on GET /api/library and the results by id; header and Origin on every POST by id, nothing
  installed/opened/exported); the page in node with a stand-in DOM (rows, buttons by condition, fold, the replace
  question, the ids encoded, Open/stems/Look by id, hidden over the form, the queue's change re-reading the list).
- **Tests of the tests:** 29 breaks, each applied to the code and the library tests run, then restored
  (`PYTHONDONTWRITEBYTECODE=1`, no `__pycache__` left). All 29 caught:
  b1 sort reversed; b2 report.json filter dropped; b3 hidden filter dropped; b4 unreadable skipped; b5 Look ignoring
  whose work folder; b6 audio not read; b7 stems not found beside a .failed; b8 id joined into a path; b9 JOB_PATH
  without the library form; b10 Open falling back to current; b11 `_job` ignoring the library; b12 results' URLs not
  encoded; b13 the guard skipped for library ids; b14 GET /api/library skipping Host; b15 a preview without its work
  folder; p1 Install for every chart; p2 the stems button always; p3 Look always; p4 never folded; p5 the stems id
  not encoded; p6 the replace question losing the name; p7 Look by folder name; p8 shown over the form; p9 his fold
  not kept; p10 the nothing-lost line never shown; p11 the queue's change not re-reading; p12 Open not by id; p13 the
  no-Look 403 sending him to Look; p14 the verdict's words.
- **Existing UI tests:** `tests/test_ui_*.py`, 211 passed (before the full suite). Two existing tests changed: the
  M8-10 Open assertion (above), and the update-notice page test, which pins what start() fetches: it now also asks
  `/api/library`.
- **Full suite** (`tools/heavy.sh`, `SONGCHARTER_HEAVY_MIN_FREE_GB=1`, `--basetemp=<shm>/m813/pt-full`):
  `1 failed, 1355 passed, 6 skipped in 1252.73s (0:20:52)`. The one failure is M8-12's
  `test_the_stems_download`: right after the GET of the stems zip, it asserts the zip is gone from exports/, but
  the server deletes it in `_export`'s `finally` after sending, so a client that has read the whole body can check
  before the delete runs. A race under the suite's load: the test passed 6 times out of 6 alone, and in both earlier
  UI runs (211 passed); this branch does not touch `_export` or the zip's deletion. Not fixed here (another order's
  test): for `deferred` (the test could wait a moment for the delete, or the server could delete before it ends the
  response).
- **Screens** (Chromium via Playwright, 1280x860 and 700 px, light and dark, deviceScaleFactor 1; the real App over a
  made-up library in `/dev/shm`, made-up names only; looked at, then deleted):
  - 3 charts: "Your charts (3)" open under the drop zone; rows as above; the Install of the split chart, then a second
    Install: the dialog "First Song is in Clone Hero already, from an earlier chart. Replace the older chart?",
    accepted, "Installed. In Clone Hero, open Settings > General and press Scan Songs."
  - Look on the chart with its work folder: "Ready", "Made-Up Band - First Song is charted and passed its check.",
    Open folder, Play it, the stems, the preview and its pages, Worth a look, Listen, and "Your charts (3)" beside
    "Add a song"; the button scrolls to the list.
  - 8 charts: folded as "Your charts (8)"; opened, the damaged one reads "Can't be read" (amber) with Open only, the
    failed one in red with Open only, the long name wraps; no horizontal scroll at 700 px.
  - First pass had the folded box inside the section's card (a box in a box); the inner border was dropped (357e35b).
  - Console: no script error. One line, at 1280 light: Chromium's own "Failed to load resource: ... 409 (Conflict)"
    for the second Install, the 409 the replace question rests on (as the queue's and the Done screen's Install).
- **Golden charts:** not run; nothing on the charting path changed (UI only).
- **Privacy:** `eval/privacy_check.py` on the 9 changed files with `EVAL_DATA=<eval>`: 0 found. With `<eval-set20>`:
  35 hits, per file DESIGN.md 30, jobs.py 3, test_ui_server.py 2, the same counts as the same files at 4c5b7e3 (35);
  the new test file has none. Commit messages and the diff scanned: no model names but the trailers, no home paths,
  no personal details, no lyrics.
- **CI:** run 42598004028 (workflow_dispatch of ci on `m8-13-your-charts`): the windows job passed; the linux job
  was still running at the hand-back. Its result and whether test_ui_library ran in it are left for the orchestrator
  to read.

## Not done / uncertain

- The list's dates use the browser's locale (`toLocaleString`, e.g. "Nov 7, 2026, 8:00 PM").
- A chart charted from the command line into another folder is not in the library and not listed (the order's scope).
- The reviewer should look at the screens again (the order's agent line).

## Review fixes (after the sc-reviewer's three minor findings; head 0a2b6f6)

Commits: 377313d (F1, F2, F3), f4c2135 (the flaky M8-12 test), 0a2b6f6 (DESIGN 4.5).

- **F1, a chart deleted after the list was read:** `Handler._job(ref, gone=True)` (the POST routes by id: install,
  export/zip, export/stems, listen; and `/api/open` "built") refuses a library id whose folder is no longer among
  the library's with M8-04's words, "<name>'s folder is not there any more: it was moved or deleted", the name
  without .failed. GETs by such an id stay 404. A library-shaped id that never was a chart gets the same words (the
  page only sends ids from the list); a job id unknown still answers "no finished chart yet". The page's row
  actions (`chartAction`) show that answer above the list (`#charts-msg`, warn colour) and read the list again;
  `visible()` reads the list again when the tab is back in front. Tests: `test_a_chart_deleted_after_the_list_was_read`
  (Install, both zips, Listen, Open, a .failed one's name, the list without them), the earlier unknown-id assertions
  updated to the new words, and the page test (the gone answer shown and the list read once more; `visible()` reads
  it once).
- **F2, report.json of the wrong shape:** four more charts in the made-up library, `{"gate": {}}`, `[]`,
  `{"gate": {"ok": "yes"}}`, `{"gate": null}`: each listed as readable false, ok false, and GET /api/library answers
  200. The reviewer's break (`readable = isinstance(gate, dict)`) now fails three tests. No code change was needed.
- **F3, the first chart folded:** the fold follows the count on every read (open up to 6) until he opens or folds it
  himself (`ownFold`: a click on its title, or a "Your charts" button), which is then kept. Test: an empty read, then
  one chart: open, "Your charts (1)"; then 7: folded; his own open kept at 8.
- **The flaky test** (M8-12's `test_the_stems_download`): the race was in the test. It now waits up to 5 s for the
  zip's delete before asserting; the server is unchanged, and a server that never deletes still fails it.
- **Breaks, each run against its tests and restored:** 12, all caught: f1a gone id answered "no finished chart yet";
  f1b `visible()` not re-reading; f1c the gone answer left in its row; f1d the gone name keeping .failed; f2 the
  shape check weakened; f3 the fold set on the first read only; f3b his own fold not kept; the earlier p2, p5, p6,
  p12 again on the moved code; the stems zip never deleted (`test_the_stems_download`).
- **UI tests:** `tests/test_ui_{server,jobs,estimate,library}.py`: 212 passed. No `__pycache__` left by these runs
  (one under songcharter/ from 10:07, during the full suite, was removed; it is git-ignored). Only the UI and its
  tests changed (and DESIGN), so the full suite was not run again.
- **Privacy:** both checks on the 9 changed files: `<eval>` 0 found; `<eval-set20>` 35, per file DESIGN.md 30, jobs.py
  3, test_ui_server.py 2, the same as at 4c5b7e3. Diff and commit messages: no model names but the trailers.
- **CI:** run 42598004028 (104deff): windows passed; linux's Suite step passed, and its install-building hooks were
  then cancelled (Hooks "cancelled": most likely CI's concurrency, when run 42602005179 started on the same branch). Run
  42602005179 on 0a2b6f6: success (windows and linux, its hooks included).
