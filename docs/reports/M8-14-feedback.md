# M8-14: the friend's feedback and "Chart it differently" (builder's report)

Branch `m8-14-feedback` from origin/main at e792d8a, worktree `<wt>/m8-14`. Pushed; CI started (not merged).

## Commits

- 7692267 the seed as configuration: --seed N, each take's seed and the engines in report.json
- 5878786 how it played, kept with the chart and sent in the diagnostics; versions and "Chart it differently"
- 3ab57aa the page: "How did it play?", "Mark a spot" and "Chart it differently"
- b9a1e1c a chart's two "How did it play?" boxes say the same; the results carry its rating
- 6529e1c the docs: the guide, DESIGN 2.7 and 4.5
- 55430ab tests for Look on a version and the kept seed; the footer and a refusal's words
- c0be40a DESIGN 4.5: what the screens showed

## What changed

### 1. The seed and the recorded configuration (pipeline.py, cli.py)
- `Options.seed` (0 to 999 999; a bool, float, string or out of range is an InputError), `songcharter chart --seed N`.
- `take_seeds(n, seed)`: take 1 is 20260609 + N, takes 2, 3, ... are 101k + N. N = 0 gives exactly the old seeds
  (20260609; 20260609, 101, 202, 303), so the default chart does not change. Within a chart the seeds are always
  distinct; from N = 101 on, a later take can meet another N's (101 + 101 = 202 + 0). This is written down as a
  judgement.
- The take cache already keys on the seed (autochart's take.json `seed`, and the folder seed_<seed>). Nothing was
  changed there; a test checks it.
- report.json's `pipeline` (folder_record) now also holds:
  - `seed`;
  - `takes.seeds` (each take's seed);
  - `engines`, from `engine_identities`: the separation's model, revision (12 hex) and seed; ADTOF's ENGINE_VERSION
    and its weights' SHA (12 hex); the bass rules' VERSION and a hash of their libraries; allin1's version, model and
    a hash of its weights (or librosa's version) with the sections engine's version; autochart's engineVersion and
    the install hash, read from the take's take.json by `Engines.guitar` (new `install` in the run's info).
  - No paths and no URLs.
- I checked the identities against real engine records already on this machine (kept work folders: engine.json and
  take.json files only, no song names printed). All four engines gave filled identities: guitar
  `2026.06.16-cross-platform-runtime`/8ddc414beab1, drums adtof-1/1bc986e596ec, bass "1"/b1fbcc9b21d8, sections
  allin1 3.1.0 harmonix-fold0/4d4bffc4a5c8. The separation's identity comes from separate.SeparationInfo, which I
  only read in the code.
- **Is report.json byte-identical run to run?** On the same machine, with the same folders and cached stages: yes.
  tests/test_seed.py compares two report.json files byte for byte, using the stand-in engines. Across machines or
  folders: no, because it holds the decode, stems and output paths and the devices. Two cold runs with the real
  engines were not compared here.

### 2. Versions and "Chart it differently" (ui/jobs.py, ui/server.py)
- **Where a version goes:** seed N is version N+1, in `library/<16 hex>/v<N+1>/<same name>/`, with the id
  `<hex>:<name>:v<N+1>`. Version 1 keeps its folder and id.
- **How it is found:** `chart_folders` walks the v-folders. `upload_of` and `version_of` read a chart's song file and
  version; `_work` finds the work folder by the upload, not by the v-folder's name. Library rows gain `upload`,
  `version`, `seed`, `guitar` and `lyrics`.
- **The list:** each song's versions are listed together (songs by their newest chart, each song's charts newest
  first).
- **The route:** `POST /api/jobs/<id>/again` re-charts the chart's song.
  - The seed is `App.next_seed`: one more than the largest seed the song has used in the library, in queue entries of
    any state, or in `state/versions.json`. So a version deleted in Windows is never made again.
  - The options come from `jobs.rechart(report.json)`: the parts charted, levels, solos, split audio, the song.ini
    values, and the device and takes asked for.
  - Pictures he gave become image uploads again, made from the chart's own album.jpg and background.jpg (a JPEG
    re-encode of those).
  - The stems are left off: the seed does not change them.
  - Pasted lyrics can be sent in the request body; they are never kept.
  - Refusals: 400 for a chart without a guitar part, a report.json that cannot be read, or an `upload` that is not
    the song file. When the song file is gone (uploads are kept 7 days), it answers 400 with `{"drop": true, "name"}`.
- **The queue:** the duplicate rule now keys on upload + seed. Queue rows carry `version`.
- **Install:** the 409 carries `version` and `installed_version` (read from the installed folder's report.json); a
  200 carries `version`. All versions install into the same Songs/<name> folder.
- **Results:** they carry `library` = {id, version, guitar, lyrics, rating, spots}.

### 3. Feedback (ui/feedback.py, server routes, diagnostics.py)
- **Where it is kept:** `<home>/state/feedback/<24 hex of SHA-256(chart id)>.json`, holding the chart id, rating,
  spots ({id, at, reasons, note}), `notes_sha` (16 hex of notes.chart at the last change) and `updated`.
  - It is written through a temporary file and read back after a restart.
  - It is never written into the song folder.
- **Routes:** `GET` and `POST /api/jobs/<id>/feedback`, behind `_handle`'s guards; ids, never paths. A POST makes one
  change: `rating` (1–5 or null), `add` (`at` as m:ss, or whole seconds), or `remove`.
- **Checks:**
  - a time after the song's end: the song's end is report.json's audio.duration plus lead_in.pad_seconds, which is
    the length Clone Hero plays;
  - reasons from the list, at least one;
  - a note of at most 300 characters, kept as written (a blank note becomes none);
  - at most 50 spots a chart.
- **The list:** `/api/library` rows carry `rating` and `spots`.
- **Diagnostics:** `feedback.json` in the zip, holding every chart with a rating or a spot, each with `now`: whether
  its folder is still there, its notes_sha, its gate, its length, and its report.json `pipeline`. There is no path
  in it. It is left out (and the manifest says so) when nothing is rated. `Bundle.json` now goes through `refused`
  (name, size, first bytes) like a copied file does.

### 4. The page (app.js, index.html, app.css)
- **"How did it play?":** one folded line on the Done screen of a chart that passed, and under each such row in
  Your charts.
  - Opened, it shows 1–5 (pressing the chosen number again takes the rating back), the spots with Remove, and a
    "Mark a spot" form. A missing time or reason is said on the page before anything is sent.
  - The chart's two boxes, and the list as read, stay in step after a change.
- **"Chart it differently":** on the Done screen and on each row with a guitar part.
  - It asks for the lyrics again when the chart had them.
  - When the song file is gone, it goes to the drop screen with a banner and "Not now". A file dropped there goes to
    the re-chart, not to the options form; another song's file is refused in words.
- **Versions:** Your charts says "version N"; the queue says "(version N)". The replace question names the versions.
  The footer says the diagnostics hold the ratings.

### 5. Docs
- The guide: how to rate, mark a spot and chart it differently, and that the ratings go into the diagnostics zip
  with his notes as he wrote them.
- DESIGN 2.7 has a new section, "The seed as configuration (M8-14)". DESIGN 4.5 covers the routes, the files, the
  diagnostics, versions and the screens.
- ui/__init__.py lists the new state files.

## Files outside the brief's list (please check)
- `tests/test_pipeline.py`: two expectations changed because report.json's `pipeline` and the guitar run's info have
  new keys. `in_folder` now takes `seed`, `engines` and `takes.seeds` apart; the `Engines.guitar` run includes
  `install: None`. There are no other edits.
- `tests/test_ui_library.py` and `tests/test_ui_server.py` (both inside `tests/test_ui_*.py`): the new fields and the
  page test's row text.
- I did **not** touch CLAUDE.md. Its determinism rule, and DESIGN §2's Determinism bullet (outside 2.7), still read
  the old way. Both are for the orchestrator.
- I did not touch PROGRESS.json or packaging/ci (no hook was added: the CI runner has no autochart engine, so CI can
  only run the suite).

## Checks
- **New tests:**
  - tests/test_seed.py (9): seeds, the take key, a second seed re-charting only the guitar, Best's 4 seeds, the default
    byte-identical (notes.chart and report.json), engine identities with no path, partial infos, the take key read,
    the CLI.
  - tests/test_ui_feedback.py (42): the routes and guards, validation (21 cases), the limits, the record surviving a
    restart and not written into the folder, the zip (contents, no path, the guard, no file when nothing is rated, an
    error case), versions, the seed on the command line, the install's 409 naming versions, the queue's duplicate
    rule, re-chart options and the next seed, a deleted version not made again, the song file asked for again, the
    guitar and readable checks, pictures and lyrics, results' `library`, Look on a version, and the page in node.
- **Which test covers what:**
  - routes and guards: test_feedback_routes_are_guarded_and_take_ids_not_paths
  - validation: test_bad_feedback_is_refused_in_plain_words, test_the_limits_and_the_song_length
  - saving and the restart: test_feedback_is_kept_with_the_chart_not_in_its_folder_and_survives_a_restart
  - the zip: test_the_diagnostics_zip_carries_every_charts_feedback_and_no_path and the two after it
  - versions side by side: test_versions_live_beside_the_first_and_are_listed_together
  - the replace question: test_the_versions_install_into_one_folder_and_the_question_names_them, and the page test
  - the seed in report.json and in the key: test_seed.py (another_seed, best, take_cache)
  - the default seed: test_the_default_seed_gives_the_same_chart_and_report
  - the queue's duplicate rule: test_the_queues_duplicate_rule_keys_on_the_upload_and_the_seed
- **Run here** (`PYTHONDONTWRITEBYTECODE=1 python -m pytest -q -p no:cacheprovider --basetemp=<shm>/...`):
  - test_seed, test_ui_feedback, test_ui_library, test_ui_jobs, test_ui_server, test_ui_estimate, test_diagnostics:
    **281 passed in 115 s**.
  - test_pipeline, test_stems_out, test_lyrics, test_art: 129 passed and 1 failed (the guitar run's new `install`
    key). After the fix that test passed alone; the four files were not run again together. CI runs the suite.
- **Testing the tests:** 47 breaks, each applied alone, with its tests run (script in the scratchpad).
  - The first pass caught 36. Two were real gaps: a version's work folder found by the v-folder's name, and
    versions.json not read (finished queue entries hid it). Both now have tests.
  - The 9 breaks in app.js showed as missed only because node was not on that run's PATH, so the page test was
    skipped.
  - The second pass caught all 11: **47/47 caught**.
- **Privacy:**
  - eval: 17 files, 0 found.
  - eval-set20: 48 hits, the same per file as main's same 14 files; the 3 new files have 0. I counted only and
    compared file names.
  - I scanned the branch diff and the commit messages: no model names apart from the trailers (and the repository's
    file name CLAUDE.md), no home paths, no lyrics (the test words are made up), and no audio or images committed.
  - While I was finding real engine records, one `find` printed three 20-song ids in this session's own tool output.
    They are not in the repository, the commits or this report.
- **Screens** (stand-in server and chart from the M8-10 scripts, copied to <shm>/m814, made-up songs; Chromium at
  1280x860 and 700 px, light and dark, deviceScaleFactor 1):
  - Your charts with "version 2" and "version 1" together, and "How did it play? 4 of 5, 2 spots marked" opened;
  - a new chart's Done screen, rated 4 with a spot, after "4:10 is after the song's end (3:34)" was refused (what he
    typed stayed);
  - "Chart it differently" giving version 2, whose Done screen says "Version 2: this song charted differently.", and
    whose Install asked "Version 1 of this song is in Clone Hero now (...). Replace it with version 2?";
  - with the song file gone, the drop banner.
  - No horizontal scroll at 700 px. The console's only lines were Chromium's for the 400 and 409 answers.
  - I looked at the shots, then deleted them and <shm>/m814.
  - One fix came from them: the queue rows' borders were showing on the nested spots list.
- **No golden run here** (the brief's rule). Seed 0 asks the guitar for 20260609 alone (tested), so the golden charts
  should not move. The orchestrator's golden run settles it.

## Interpretations to check
1. `--seed N` is an offset on every take's seed (0 is the default), not the first take's literal seed. The record
   holds both (`seed`, `takes.seeds`).
2. Version = seed + 1, in a `v<N>` folder of the same name. The versions install into the same Clone Hero folder.
3. A re-chart's options come from report.json (its config and `pipeline`), not from the queue's record. The stems
   are left off; given pictures are re-encoded from the chart's own album.jpg and background.jpg.
4. A spot's time is Clone Hero's clock (with the lead-in), checked against duration + pad.
5. feedback.json is left out of the zip when nothing is rated.
6. "Chart it differently" is offered for a failed check too (a re-roll may pass); feedback only for a chart that
   passed.
7. A dropped file in "again" mode must be the same song file (the same upload id); another file is refused.

## Not done, or uncertain
- The re-chart's estimate is the whole chart's, but only the guitar and assemble run, so the page overstates the
  minutes.
- No CI hook. The real engines' identities are checked by tests on made-up shapes and once here on real records; a
  golden or test-song report.json should show `pipeline.engines` filled.
- The full suite was not run locally; CI runs it.

## The review's fixes

Branch head c681ac7, which merges origin/main 236513b (the process changes) in 8bd26e0. One conflict, in
docs/DESIGN.md 4.5: I kept both sides, M8-14's bullet and main's Status line with the lyrics rule's clause.

**F1 (major): every version keeps the first chart's folder name.** Commit 5a4ea77.
- "Chart it differently" now sends the chart's own folder name (with any `.failed` suffix removed) as the `name`
  option. `output_folder` uses it when given; version 1's naming is unchanged.
- `name` is checked as one path component (`jobs.folder_name`). It is kept in the queue entry, so it survives
  queue.json, a restart and the "drop the file again" path.
- song.ini's name and artist are the same in every version: the re-chart gives version 1's resolved values as the
  song's fields.
- Tests:
  - `test_every_version_keeps_the_first_charts_folder_name`, three ways: a several-song drop with a long untagged
    name, the page's fields, and a tagged file. A stand-in chart names each song as the pipeline does. Version 2's
    install meets version 1 in one Clone Hero folder with the replace question; version 3 arrives through the dropped
    file.
  - `test_the_name_option_is_one_path_component`.

**F2 (major): nothing typed is lost.** Commit 4a998bf.
- `renderFeedback` puts a half-typed spot (the time, the ticks, the note) back after a change. Only a saved spot
  clears the form.
- `setCharts` makes again only the rows whose chart changed. The other rows stay the same elements, in the new order.
  A changed row keeps its open box, its message and its lyrics panel.
- Test: `test_nothing_typed_is_lost` (node). It types a spot, presses a rating, has a rating refused, adds a third
  chart and changes another chart's rating, then reads the inputs back.

**F3: a refused press uses no version number.** Commit 5a4ea77.
- `next_seed` now only works the number out. `keep_seed` writes versions.json after `_add` has accepted the song,
  still under `again_lock`.
- Test: `test_a_refused_press_uses_no_version_number`. Two refusals, then an accepted press, gives version 3.

**F4: pasted lyrics stay when a press is refused.** Commit 4a998bf.
- The lyrics panel is emptied only on a 202. If the song file has to be dropped again, the panel travels with that
  request.
- Test: `test_nothing_typed_is_lost`. On a refusal the text is still there with the server's words; on acceptance
  the panel is empty.

**F5: plain words, not 500s.** Commit d9a76f2.
- `parse_time` refuses NaN, infinities and anything past 999:59 with the same plain 400 as any bad time.
- A saved spot that does not read is left out wherever records are read; the readable spots are kept.
- Tests:
  - `test_a_time_that_is_no_finite_number_is_a_plain_400`: 1e400, Infinity, NaN and a huge number.
  - `test_a_damaged_spot_is_left_out_and_the_rest_still_works`: GET, add, remove, the library and the zip all work.

**Item 6: DESIGN §2's Determinism bullet** now reads as the rule does. Commit b495378, which also adds the fixes to
DESIGN 4.5.

**Item 7: the re-chart's estimate.** Commits 5a4ea77 and c681ac7, about 12 lines.
- When the song's work folder is still in the cache, the estimate counts the guitar's takes and the build
  (`estimate.CACHED` [est.] replaces `OTHER`). Otherwise it is a whole chart's estimate, as before.
- A plain song's `for_job` call is unchanged (c681ac7: test_ui_server's stand-in takes positional arguments only).
- Test: `test_the_rechart_estimate_counts_the_guitar_when_the_rest_is_cached`.

**Checks**
- Breaking each fix (11 breaks, node on the PATH) fails its test: 11 of 11 caught. The estimate's break was checked
  again after c681ac7 and is still caught.
- After the merge, the affected files (test_seed, test_ui_feedback, test_ui_library, test_ui_jobs, test_ui_server,
  test_ui_estimate, test_diagnostics): **293 passed**.
- Privacy against 236513b:
  - eval: 0 found in 18 files.
  - eval-set20: 48 hits, the same per file as main's; the new files have 0. Hits were counted, not printed.
- I scanned the new commits' diff and messages: no model names apart from the trailers, and no paths.
- The trailers are the session's own, as CLAUDE.md asks ("the attribution trailer the session's instructions
  require").

**CI**
- The earlier run 42721173883 ended "cancelled". Windows had passed; Linux was cancelled when the new push started a
  run on the same branch, so its result is unknown.
- The new run 42725452287 is on c681ac7, started by the push. Both jobs were in progress when I returned.

## The second review's fixes

Branch m8-14-feedback, from c681ac7 to 638db63 (five commits). R1 was fixed after the orchestrator's word that it
stands (the skeptic reproduced it).

**R2 (4ce4c48): a whole number too long for a float is a plain 400, and a saved one is left out.**
- `parse_time` and `_spot_ok` compare against the bounds (0 to MAX_AT) instead of calling `math.isfinite`, which
  raised OverflowError on such a number. The bounds alone refuse NaN and the infinities; `math` is no longer imported.
- In `_spot_ok` the bound is MAX_AT, not the reviewer's `< math.inf`. A 400-digit integer is below infinity, so
  `< math.inf` would keep the spot, and the brief's test asks for it to be left out. `change` never writes a time
  past MAX_AT, so a saved one is damage. To check: this also leaves out a saved float time between MAX_AT and
  infinity, which `change` cannot have written either.
- Tests: `test_a_time_that_is_no_finite_number_is_a_plain_400` gets a fifth case, a 400-digit `at` through the route
  (400, the plain words). `test_a_saved_time_too_long_for_a_float_is_left_out` covers a saved record holding one: GET
  feedback, GET /api/library and a rating all 200, and the spot is left out.

**R3 and R4 (b8929b3): typing goes on when Your charts changes; a moved box says the chart's rating now.**
- R3: `setCharts` takes out only the rows that went, and moves only the rows whose place changed (insertBefore when
  `children[i] !== lis[i]`), with no replaceChildren of every row. `heldFocus`/`giveFocus` keep the field being typed
  in, with its caret, and give it back once its row has been moved or made again (preventScroll).
- R4: a box kept for a remade row, if it was loaded, is freshened after the rows are placed:
  - a different rating sets `fb.data.rating` and renders again with `renderFeedback(fb, false)`;
  - a different spot count reads the record again (`loadFeedback`), since the list gives only a count;
  - a read again that gets no answer leaves the box as it was (`loadFeedback` returns early when `fb.data` is set);
    the first read of a box behaves as before.
- R3 and R4 together: `renderFeedback` gives the focused field (time, note or a tick) to its place in the new form,
  with its caret. Without that, R4's re-render would lose the focus in the case "his own row made again".
- Test changes:
  - The page test's stand-in DOM gets insertBefore and removeChild, and logs what a list takes out and puts in
    (replaceChildren logged as every row out and in). test_ui_library's stand-in gets the same two methods.
  - In the page test, `rows` is now a copy: the list's children change in place, as they do in a browser.
- Tests, in `test_nothing_typed_is_lost`:
  - R3: when a chart is added and v1 is remade, the list's moves are exactly [out old v1, in third, in new v1], so
    the row that stayed is never taken out.
  - R4: the moved box says "5 of 5" with 5 pressed straight away. After the read again it says "5 of 5, 2 spots
    marked" with the two spots listed, and the typing is kept.
  - A read again with no answer keeps the box and the typing.
- Chromium (Playwright, the real index.html, app.css and app.js, the API stubbed, `setCharts` called as a list read
  calls it; scripts in `<scratchpad>/m8/m814-focus/`):

  | Case | This branch | c681ac7 |
  |---|---|---|
  | Another chart added above while typing in a note | focus and caret kept; the next keys land | focus on body; keys lost |
  | His own row remade (rated elsewhere) | focus kept, caret where it was ("half typXed"); 4 pressed | keys lost; line "How did it play?" |
  | His own row's spots changed (re-read) | focus kept; line "4 of 5, 1 spot marked" | keys lost |
  | The time field, row moved to the top | focus kept; "1:05" | keys lost |

  Breaking `giveFocus` in setCharts loses the focus in the moved and remade cases. Breaking the carry in
  renderFeedback loses it in the remade and re-read cases. Each part is needed.

**R5 (55669fa): a test that syncFeedback keeps the other box's typing.**
- The test is in `test_nothing_typed_is_lost`. A rating saved in the row's box keeps the Done screen's half-typed
  spot, and a spot saved in the Done screen's box keeps the row's. syncFeedback's one line serves both directions.

**R1 (f1e4ec7): one press, one version.**
- `chartAgain` keeps a busy flag on the chart's panel, which a remade row keeps, and returns at once while a request
  is out.
- While a request is out, the panel's "Chart it" and "Without lyrics" are disabled, and so is the row's button.
  - That button is `panel.button`, the row's current one, which chartRow sets. It is no longer the old row's button
    held in the closure.
  - A row made during the request creates its button disabled.
- A refusal enables them again and keeps the lyrics (F4 still holds). A 202 empties the panel as before.
- The Done screen needs no `panel.button`: `o.button` is already its button. A version with the line was tried; the
  line was redundant (a break of it was not caught) and was removed.
- Test: `test_one_press_one_version` (node, with /again held until released):
  - two presses on "Without lyrics" and one on "Chart it" send one request;
  - the panel's two buttons and the remade row's button are disabled, and the old row's is not;
  - a row made during the request has its button disabled;
  - a refusal enables all three, keeps the lyrics and says why;
  - two presses on "Chart it" with a 202 send one more request, and the panel empties;
  - on the Done screen, a double click on "Without lyrics" sends one request.
- Chromium, /again held 300 ms, double click on "Without lyrics":

  | Where | This branch | c681ac7 |
  |---|---|---|
  | Done screen | 1 request | 2 requests |
  | Row | 1 request | 1 request (its message line shifts the panel, as the review said) |

**Checks**
- Breaks (each applied in turn, then the covering tests run): 15 of 16 caught.
  - R3: replaceChildren of every row.
  - R4: no freshen; the spots not read again; the form cleared; the box emptied when there is no answer.
  - R5: syncFeedback clearing.
  - R2: isfinite in parse_time; isfinite in _spot_ok; `< inf` in _spot_ok.
  - R1: no flag; the old row's button; a row made during the request enabled; the flag left on after a refusal; the
    panel's two not disabled.
  - Not caught: the Done screen's `panel.button`, the redundant line, which was removed.
  - c681ac7's app.js fails the new tests.
- The affected files (`PYTHONDONTWRITEBYTECODE=1`, single files, no suite): tests/test_ui_feedback.py,
  tests/test_ui_library.py and tests/test_ui_server.py gave **157 passed** at f1e4ec7's code. The later commit
  changes docs only.
- Privacy (hits counted, only the last line read), per changed file, branch against c681ac7 and main:
  - eval: 0 in every file.
  - eval-set20: 0 in every file except docs/DESIGN.md, which has 30 here, 30 at c681ac7 and 30 on main.
- I scanned the diff c681ac7..638db63 and the commit messages for model names, paths, personal details and lyrics.
  Only the trailers turned up, and the words in the tests are made up.
- No `__pycache__`: the three folders in the worktree were an hour older than these runs and are removed.
- `df -h /`: 1.1 GB free.

**CI**
- 42725452287 (c681ac7) had finished, success, before the push.
- The new run 42729465498 is on 638db63, started by the push: <repo>/actions/runs/42729465498.
  It was in progress when I returned.
