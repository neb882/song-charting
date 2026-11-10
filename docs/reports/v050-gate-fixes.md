# gate-look: a queue entry's Look shows only its own chart's preview (v0.5.0's gate)

Branch `gate-look` from origin/main 1611346, worktree `<wt>/gate-look`.

## Commits

- `aa29bf3` Look on a queue entry: only its own chart's preview, not a later version's (code and tests)
- `ddb10a9` DESIGN 4.5: the queue's Look keeps its button, its preview goes with a later chart

## What changed

- `songcharter/ui/jobs.py`: `last_chart_is(record, folder) -> bool | None` is now the one comparison. It checks
  pipeline.json's `assemble.folder` against the chart's folder by resolved paths, and gives None when the record
  names no folder. `_work` (the library's Look rule) now calls it. Its behaviour is unchanged: it still needs True.
- `songcharter/ui/server.py`:
  - `record_of(result)` reads the result's work folder's pipeline.json. It is taken out of `results` with the same
    behaviour: {} when there is no `work`, the file cannot be read, or it is not an object.
  - `later_chart(result, record)` is True only when `last_chart_is` says False, that is, when the record names
    another folder.
  - `results`: for such a job, `preview` is `{"why": LATER_CHART}`.
    `LATER_CHART = "it went with a later chart of this song (Look at that one in Your charts)"`, and the Done screen
    shows it as "No preview: it went with a later chart of this song (Look at that one in Your charts)".
  - `_preview` answers 404 for such a job.
  - A record that names no folder keeps the behaviour from before. This matters for the test stand-in BUILT, whose
    pipeline.json has no `assemble`, and for any record that cannot be read.
  - The module docstring entries for results and the preview route are updated.
- `docs/DESIGN.md` 4.5 (Your charts, the read): one sentence on the queue's Look, the shared comparison and the
  wording.
- No change to app.js, the cache keys, the library's rule, or anything that charts. No golden run was needed,
  because nothing charts.

## Listen's answer

Listen plays this job's own chart, so it was left as it is. `_listen` calls `listen.cached(folder, work/listen, ...)`
with the job's own `folder`. The render reads that folder's notes.chart and audio. The cache name is
`<part>-<level>-<key>.ogg`, where the key is a hash of that folder's chart, song.ini and audio, so the work folder's
`listen/` only stores the file. The new server test checks that Listen on version 1 still answers 200 after
version 2 has the work folder.

A side note, not changed: `listen.cached` deletes the older renders of the same part and level. If version 2 renders
guitar Expert after version 1 did, version 1's recorded render URL can answer 404 until its Listen is pressed again,
which renders version 1's own chart again. Playback is never wrong, only re-rendered.

## The Look button's choice

The queue entry keeps its Look button. The library row loses Look because, without the work folder, it has nothing
of its own to show beyond what the row already offers. The queue entry's Done screen is still its own: its summary,
the gate's verdict, Install, the zip and Listen. Taking the button away would take those away from the list. It would
also need a per-entry check in the queue's snapshot. With the button kept, the Done screen says in one line why there
is no preview and where to look ("Your charts", which has a button on that screen). The app.js code is unchanged.

## A question for the orchestrator (not done, outside the brief)

`results` also reads other fields from the same pipeline.json:
- `lyrics` (the counts line);
- `art.album_from` (the "Album art: your picture / the song file's own picture" line);
- `stems.why` (only when no stems folder is beside the chart).

For version 1 after version 2, these are version 2's too. DESIGN 4.5 already says "its preview, lyrics counts and
pictures" go with the later chart. The library drops all of them, because Charted gives no `work`. In practice:
- The pictures come back as uploads in "Chart it differently", so `album_from` is very likely the same.
- The lyrics line can differ: version 2 made without pasting the lyrics again would hide version 1's lyrics line, or
  show "not added".

The brief asked for the preview only, so I left these as they are. The fix would be one line in `results`:
`pipeline = {} if later else pipeline` after `later` is computed, with `pv` kept for the why. The library already
does exactly this.

## Tests (each fails without the fix)

- `tests/test_ui_server.py::test_a_looks_preview_is_its_own_charts_not_a_later_versions`, with the `finished`
  fixture. Version 1 is charted, then version 2 (seed 1: `<16 hex>/v2/<name>`, the same work folder). The test then
  writes the record as the pipeline does, with `assemble.folder` set to version 2's folder. It checks:
  - Version 1's results by its id have `preview == {"why": ...}`, with the literal wording, and are still
    installable.
  - Version 1's overview, page_01 and page_02 answer 404.
  - Version 2's results by its id and as `current` keep the overview, the pages and the flags, and its pictures
    answer 200.
  - After a restart (an App over queue.json), `S.results(kept)` gives version 1 the why and gives version 2 its
    preview.
  - Listen on version 1 answers 200.
  - With the record naming version 1 by an unresolved path (`.../v2/../<name>`), version 1 has its preview again
    and version 2 has none, with a 404.
- `tests/test_ui_library.py::test_the_last_chart_of_a_work_folder_by_resolved_paths`. `last_chart_is` gives:
  - True for the folder spelled two ways;
  - False for the other version's folder;
  - None for `{}`, `{"assemble": {}}`, `{"assemble": None}`, `[]`, `None`, `"x"`, and a path with a NUL.

Against origin/main's jobs.py and server.py, with the new tests:
`2 failed in 1.24s`. The server test failed on version 1's preview, which was version 2's overview, pages and flags,
not the why. The library test failed with no `last_chart_is`.

Breaks of the fix. The five tests run for each break were: the two new tests,
`test_the_stems_and_look_by_a_charts_id`, `test_a_finished_songs_routes_by_its_job_id_after_the_next_has_started`
and `test_the_results_and_the_preview_by_exact_name_only`.

| Break | Result | Failed |
|---|---|---|
| results without later_chart | 1 failed, 4 passed | the new server test |
| the preview route without later_chart | 1 failed, 4 passed | the new server test |
| paths compared unresolved | 2 failed, 3 passed | both new tests |
| a record without assemble.folder read as another chart's | 4 failed, 1 passed | the library unit test and three earlier tests |
| the comparison turned around | 2 failed, 3 passed | the new server test and the library Look test |

"The latest chart's job still has its preview" passes with and without the fix, as it must. It guards against an
over-broad fix, and the "turned around" break fails it.

## Checks

- The affected test files, run with the dev venv's Python and with
  `PYTHONDONTWRITEBYTECODE=1 ... -m pytest -q -p no:cacheprovider --basetemp=<shm>/pt-gate-look
  tests/test_ui_server.py tests/test_ui_library.py tests/test_ui_feedback.py`: `159 passed in 54.89s`
  (on aa29bf3; ddb10a9 changes DESIGN.md only). No `__pycache__` left.
- Not run, as the brief says: the full suite, a golden run, a real chart.
- Privacy checks on the five changed files (hit counts only, the last line). Both runs gave the same counts on the
  branch as on main's copies of the same files:
  - `EVAL_DATA=$DEV/eval`: 0 found on the branch, 0 on main.
  - `EVAL_DATA=$DEV/eval-set20`: 35 found on the branch, 35 on main. Per file, the branch and main agree: jobs.py 3,
    server.py 0, test_ui_server.py 2, test_ui_library.py 0, DESIGN.md 30.
- The diff and the commit messages were scanned for lyrics, audio, model names and personal details. Nothing was
  found apart from the commit trailers.
- CI: run 42740165180 on the push of head ddb10a9 (<repo>/actions/runs/42740165180),
  queued when this report was written; its result was not read here. origin/main had not moved (1611346), so there
  was no merge.

## Follow-up (the coordinator's decision): the rest of the record too

- `c72012e` Look on an earlier chart: none of the later chart's record, not only its preview.
- `results`: when `later_chart` is True, the record is read as `{}`, as the library does. So there are no lyrics
  counts, no `album_from` and no stems' why from the later chart. Reads from the job's own folder are unchanged:
  album.jpg and the stems folder its result names.
- The server test now writes lyrics, art and stems' why into version 2's record, and puts an album.jpg in each
  folder. It checks:
  - version 1: `lyrics` None, `stems` None, and `art` = its own album.jpg URL with `album_from` None;
  - version 2: its own values.
- Breaks run against the new server test:
  - the record still read for everything but the preview: 1 failed;
  - only art kept from the record: 1 failed;
  - only lyrics kept: 1 failed;
  - only stems kept: 1 failed.
- The three UI test files: `159 passed in 53.25s`.
- Privacy checks per changed file (server.py, test_ui_server.py, DESIGN.md): the branch's hit counts equal main's.
  - `eval`: 0 in each file.
  - `eval-set20`: 0 in server.py, 2 in test_ui_server.py, 30 in DESIGN.md.
- The diff scan found nothing apart from the trailers.
- CI: run 42740523718 on head c72012e, still pending when this was written. The earlier run 42740165180 was on ddb10a9.

## The advisor's fixes

The five fixes the advisor found at v0.5.0's release gate (its findings 1, 2, 3, 6 and 7), one commit each on
gate-look after c72012e. Head 0a2b342.

### 1. A rating stays with the chart it was given to: `36d420f`

- `feedback.as_now(record, notes)`: when the record's notes_sha is not the folder's notes.chart now
  (`feedback.notes_id`), the record reads as none yet. Its rating and spots go first in a new `earlier` list
  (each entry: rating, spots, notes_sha, updated; newest first; at most `EARLIER_MAX` = 5).
- A chart charted back to one rated before (the same options, so the same notes.chart) gets its own record
  back from `earlier`.
- `feedback.read(home, id, folder)` applies the rule when it is given the folder. These callers pass it:
  - the box's GET;
  - `App.library`'s counts (one `chart_folders` walk maps ids to folders);
  - the results' `library`.
- `feedback.change` applies the rule before each change, so the first change saves the fresh record.
- `public` gains `earlier`: the newest earlier entry's rating and spot count, while this chart has neither.
- The page's line (app.js `earlierLine`) says, for example: "You rated an earlier chart of this song 5 of 5, with
  2 spots marked. How does this one play?". Nothing is pressed and no spot is listed. Once rated, the line is the
  usual one.
- The zip: `for_diagnostics` sends the record as it stands now, with `earlier`. A record with only earlier entries
  is still sent.
- Code size: about 40 lines in feedback.py, server.py and app.js together, under the brief's ~60.
- Tests:
  - `test_a_rating_stays_with_the_chart_it_was_given_to` checks the GET, the library, the results, the zip before
    and after the first change, a chart charted back, the cap, and a rating taken back.
  - `test_the_box_says_he_rated_an_earlier_chart` runs the page in node.
- Breaks that each failed a test:
  - as_now a no-op;
  - the current rating not moved to earlier;
  - the library or the results read without the folder;
  - change without as_now;
  - no own record for a chart charted back;
  - no cap;
  - the zip without as_now;
  - the zip skipping records that have only earlier entries;
  - public without earlier;
  - the page's line without earlierLine.

### 2. One "Chart it differently" at a time for a song: `931d016`

- `_again`, under `again_lock`: when a version of the song is waiting or charting, the route answers 409 in plain
  words. It uses no seed: the refusal comes before `next_seed`, and `keep_seed` is never reached.
  - A version is an entry of this upload with a seed above 0 (`Handler._version_listed`).
  - Words while it waits: "Version 3 of this song is already in the list: when it is charted, you can chart it
    differently again."
  - While it charts, the same with "is charting now".
- A plain chart of the song in the list does not block it, as the brief says (seed above 0 only).
- A version whose chart is out while its process is still exiting counts as charted. `Queue.add` waits for that
  process anyway.
- The page already shows a non-202, non-drop answer's words in the row's or the Done screen's message line, and
  keeps the lyrics panel. No app.js change was needed.
- Tests:
  - `test_one_version_of_a_song_at_a_time` holds each stand-in chart behind a gate file for its seed and can keep
    the process alive 1.5 s after its result. It checks:
    - a plain chart charting, then a version waiting: 409 from either version;
    - versions.json unchanged by the refusal;
    - the "charting now" words;
    - the press while the version's process is exiting: taken (version 4);
    - after it is charted, version 5.
  - `test_the_page_says_a_version_is_in_the_list` (node) checks the row's line with the lyrics kept, and the Done
    screen's line.
- Breaks that each failed a test:
  - no refusal;
  - the rule on the upload alone;
  - a seed written before the refusal;
  - a version whose chart is out still refused;
  - the page not showing the words;
  - the page emptying the panel on a 409.
- **Chosen differently:** the brief says "the test that expects two back-to-back presses to give two versions
  changes". No such test exists. Every route test waits until the queue is idle between presses, and none failed
  with the refusal. So no test changed. `test_the_queues_duplicate_rule_keys_on_the_upload_and_the_seed` tests
  `Queue.add`, whose rule is unchanged, and stays as it is.

### 3. The notes around a marked spot travel in the zip: `218b895`

- `feedback.guitar_notes(folder)` reads the chart with the project's importer:
  - `importers.read_chart`, with the folder's song.ini modifiers, for the notes, HOPO, tap and sustains as Clone
    Hero plays them;
  - `importers._parse_chart` and `_Clock` for the resolution and the tempo map, as engines/stitch.py already
    does. Ticks come from inverting the clock.
- `feedback.around(guitar, at, left)` adds `around` to each spot of the chart rated, that is, when the record's
  notes_sha is the folder's now. It holds:
  - `from_s` and `to_s` (10 s either side of the spot, clipped at 0);
  - `resolution`;
  - `tempos`: the tempo marker in force at `from_s` first, then those inside the window;
  - `notes`, `left_out`, and `why` when some notes were left out.
- **The clock:** the seconds count from the chart's tick 0, with Offset 0 and no song.ini delay in songcharter's
  charts. That is song.ogg's clock, the lead-in included (assemble.py: "every input second t sits at
  t + pad_seconds on the map"). It is the clock of the spot's `at`, which the length check also uses
  (`song_length` = duration + pad).
- **No words:** nothing from `[Events]`, no section or lyric, no name. The only strings are fixed words of ours.
  A chart that cannot be read gives the exception's type name only, never its message, which could hold a path.
- **Caps:**
  - 400 notes a spot (the nearest are kept);
  - 10,000 notes a file, about 200 bytes a note as written, so about 2 MB of the zip's 5 MB a file;
  - `test_a_full_files_notes_stay_under_the_zips_limit` checks that the worst case stays under 60 % of MAX_BYTES.
- A spot gets `{"why": ...}` alone when:
  - the chart cannot be read ("its notes.chart could not be read as a chart (InputError)");
  - it has no Expert guitar;
  - the spots were marked on another notes.chart than the one there now;
  - the folder is gone.
- `diagnostics.refused` still refuses notes.chart; the test asserts it.
- Updated for this fix:
  - the diagnostics.py docstring and the manifest's feedback line;
  - the page's Diagnostics line ("your ratings, and the guitar notes around each spot you marked; no audio and no
    lyrics");
  - the guide's zip sentence;
  - DESIGN 4.5.
- Tests:
  - `test_the_zip_carries_the_guitar_notes_around_each_spot` uses a made-up notes.chart: two tempos, a made-up
    section and lyric words, a chord, a natural HOPO, a tap, a sustained open, and a dense run. It checks:
    - the exact notes and tempos for spots at 0:10, 0:40 and 1:00;
    - no word of the chart in feedback.json;
    - both caps and their `why`;
    - the unreadable, no-guitar and other-notes.chart cases;
    - notes.chart still refused.
  - `test_a_full_files_notes_stay_under_the_zips_limit`.
- Breaks that each failed a test:
  - no notes;
  - another clock, two ways (the tick's offset, the seconds);
  - a tap reported as its HOPO state;
  - sustain 0;
  - the tempo in force left out;
  - section names or a lyric reaching the file;
  - no cap a spot;
  - no file cap;
  - a file cap of 30,000;
  - the notes_sha check removed.
  - One break passed: adding the raw sections to `guitar_notes`'s return value, because `around` never copies that
    key, so it is no leak path. The two breaks above put a word where it would reach the file.
- **Chosen differently:** the spots of an `earlier` entry carry no `around`, since that chart is no longer in the
  folder. feedback.json's `about` says so.

An example spot entry in feedback.json (the test's made-up chart, the spot at 0:10, shown compact):

```json
{"id": "1a2b3c4d", "at": 10, "reasons": ["off_beat"], "note": null,
 "around": {"from_s": 0.0, "to_s": 20, "resolution": 192,
            "tempos": [{"tick": 0, "bpm": 120.0, "s": 0.0}, {"tick": 4608, "bpm": 60.0, "s": 12.0}],
            "notes": [{"s": 4.0, "tick": 1536, "frets": [0, 2], "open": false, "kind": "strum", "sustain": 0},
                      {"s": 4.167, "tick": 1600, "frets": [1], "open": false, "kind": "hopo", "sustain": 0},
                      {"s": 4.667, "tick": 1792, "frets": [3], "open": false, "kind": "tap", "sustain": 0},
                      {"s": 6.0, "tick": 2304, "frets": [], "open": true, "kind": "strum", "sustain": 192},
                      {"s": 17.0, "tick": 5568, "frets": [4], "open": false, "kind": "strum", "sustain": 0}],
            "left_out": 0}}
```

### 4. The record says what the reproducibility rule needs: `5c5645b`

- `folder_record` (report.json's `pipeline`) gains:
  - `threads`: as asked, None for the default;
  - in `takes`, `stage_devices`: each take's driver devices for every engine stage (`Take.devices`, with a
    continued take's pieces counted);
  - in `takes`, `cached_stages`: each take's `runs[0].cachedStages`.
- Both are kept in pipeline.json's `takes` too.
- `pipeline._names` keeps short names only (the eval tools' NAME pattern), so a path or a message is dropped.
- The record goes only into report.json, so no chart changes. `test_seed`'s byte-identical report.json and
  notes.chart test passes. The golden pair is the orchestrator's.
- DESIGN 2.7: the rule's scope in one sentence (the same record gives the same chart from the same cached stages,
  and a take that reused another device's cached features says so in `cached_stages`), and the record's new
  fields. CLAUDE.md not touched.
- Tests:
  - `test_the_record_says_the_threads_and_each_takes_engine_stages` charts with `--threads 3` and with the default,
    and checks that a path is dropped.
  - Two record tests were updated: `test_takes_follow_the_guitar_stages_device` (its exact dicts, plus every
    stage's devices as shown) and `test_a_guitar_take_that_fails_on_cuda_is_run_again_on_the_cpu`. Its stand-in
    driver now reports a demucs device and cachedStages: [] for the first take, ["demucs", "timing"] for later ones.
- Breaks that each failed a test:
  - threads not recorded;
  - only the transcriber's device;
  - a path kept;
  - cached_stages or stage_devices not copied into report.json.
- The helper is named `_take_stages`: `_engine_stages` was taken.

### 5. A rating that cannot be saved says so plainly: `0a2b342`

- `_feedback` catches OSError and logs it with its path, in the log only.
  - ENOSPC: 507 "This was not saved: C: (or WSL's disk) is full. Free some space on C:, then try again."
  - Any other OSError: 500 "This was not saved: songcharter could not write it (<strerror>). Try again in a moment."
  - No path in either answer.
- The page keeps what he typed for any refusal (F2): renderFeedback runs only on a 200.
- Test: `test_a_rating_that_cannot_be_saved_says_so_plainly` (both errnos, a spot as well as a rating, the log
  lines, the record unchanged).
- Breaks that each failed the test:
  - the error not caught;
  - not logged;
  - the whole error in the answer, so a path;
  - every error said as a full disk.

### Checks

- The affected test files, with the dev venv's Python and `PYTHONDONTWRITEBYTECODE=1 ... -m pytest -q -p
  no:cacheprovider`:
  - `tests/test_ui_feedback.py tests/test_ui_server.py tests/test_ui_library.py tests/test_diagnostics.py`:
    `172 passed in 64.54s`;
  - test_pipeline.py's record tests (`-k "threads_and_each_takes or takes_follow or run_again_on_the_cpu or
    says_what_to_do or cut_short or every_fallback"`): `6 passed, 57 deselected in 155.53s`;
  - earlier, with fix 4's code, the whole of `tests/test_pipeline.py tests/test_seed.py`: 71 passed and 1 failed.
    The failure was the new test reading the module fixture's report.json, which later tests overwrite; it was
    rewritten to make its own charts and passes.
- No `__pycache__` was left.
- Not run, as the brief says: the full suite, a golden run, a real chart.
- Privacy checks, per changed file, hit counts only (the last `privacy_check:` line), against origin/main's copies:
  - `EVAL_DATA=$DEV/eval`: 0 found in every file, on the branch and on main.
  - `EVAL_DATA=$DEV/eval-set20`: the branch's counts equal main's: DESIGN.md 30, tests/test_pipeline.py 8, every
    other changed file 0.
- The diff and the commit messages were scanned for model names, paths, user names, audio and charts. Nothing was
  found apart from the commit trailers. The tests' lyric-like words are made up ("Zibzab", "Zobble", "zib zab").
- Pushed: c72012e..0a2b342 to origin/gate-look (no force). origin/main had not moved (1611346), so there was no
  merge.
- CI: run 42747821082 on push of 0a2b342, in progress when this was written; its result was not read here.
- **Trailer:** the commits carry this session's attribution lines from its own instructions. They name a
  different model from the brief's trailer lines, since the session's instructions say which lines to use.

### The review's two findings (gate-fixes2.review.md)

- **F1: `3f3f8ab`.** A change made while the folder's notes.chart could not be read saved `notes_sha=None` over
  the rated chart's sha. The record then belonged to no chart, and the next chart in the folder took its rating
  and spots as its own.
  - Fix: `change` keeps the sha the record had (`notes_sha=notes if notes is not None else record["notes_sha"]`).
  - Test: `test_a_change_while_notes_chart_cannot_be_read_keeps_the_charts_sha`. It rates the chart, unlinks
    notes.chart, adds a spot (the sha is kept), writes another chart, then GETs: no rating, and `earlier` holds the
    first chart's 5 and 1 spot. Rating the new chart keeps them in `earlier`.
  - Break: saving `notes_sha=notes` failed the test.
- **F2: `9b15b65`.** A feedback.json over MAX_BYTES was left out whole, every rating with it, and the manifest
  still said the zip held the ratings.
  - Fix in `bundle`: a file refused for its size is written again through `diagnostics.without_notes`, with each
    spot's `around` set to {"why": "left out: the file would be over 5 MB"}.
  - The manifest's closing line now follows what went in (`FED_LINES`: whole, short, none, nothing). The first
    refusal stays in its "left out" list.
  - Still too big without the notes: no feedback.json, and the manifest says the ratings are kept in the
    state/feedback folder of songcharter's home. That line holds no path.
  - Test: `test_a_feedback_json_too_big_goes_without_the_notes`, through the real bundle with the reviewer's case:
    16 made-up charts, each with 50 spots of 300 two-byte characters and 5 earlier entries, plus a dense made-up
    chart giving 10,000 notes. It checks:
    - the whole file is over 5 MB;
    - feedback.json is in the zip with every rating and no notes;
    - the manifest's line;
    - with MAX_BYTES at 1 MB, no file and the "not in this zip" line.
  - Breaks that each failed the test: no retry; the closing line chosen by the charts alone; the notes kept in the
    retry.
- Not touched: pipeline.py and anything that charts.
- Checks:
  - `tests/test_ui_feedback.py tests/test_ui_server.py tests/test_ui_library.py tests/test_diagnostics.py`:
    `174 passed in 68.66s`.
  - Privacy checks on the four changed files: hit counts equal main's for both data sets (eval 0 in each;
    eval-set20: DESIGN.md 30, the others 0).
  - Diff scan: nothing found.
  - No `__pycache__` was left.
- Pushed 0a2b342..9b15b65. CI run 42749811675 on 9b15b65 was pending when this was written. The earlier run,
  42747821082 on 0a2b342, had not finished either; its result was not read here.

## The diagnostics zip without the user's name (found on the owner's PC, merged with the gate)

*The builder's report; `<home-root>` stands for the Linux root of home folders in its made-up examples.*

### gate-zipnames: the diagnostics zip names no user (v0.5.0's gate)

Branch `gate-zipnames` in `<wt>/gate-zipnames`. It started at main's cac4c2b and was fast-forwarded to main's 6af0a7f
before the first push (no overlap: that commit touched CLAUDE.md, PROGRESS and a report only). Head 8ba53e1.

### Commits

- 0d352f1: The diagnostics zip names no user: his folders as ~ and C:\Users\<user> in every file
  (`songcharter/diagnostics.py`, `tests/test_diagnostics.py`)
- 8ba53e1: Docs: the diagnostics zip without the user's name (DESIGN 4.5's bundle line, the guide)
  (`docs/DESIGN.md`, `docs/guide/windows-wsl.md`)

Trailer: the commits end with the session's attribution lines, as CLAUDE.md asks.

### What changed

`songcharter/diagnostics.py`:
- `scrub(text, home)` rewrites the user's folders:
  - a Windows profile's name becomes `<user>` in each spelling (`PROFILE`, `WSL_HOME`);
  - then the Linux home becomes `~` (`home_pattern()`).
- `PROFILE` matches `<drive>:` or `/mnt/<drive>`, then a separator, `Users` (any case), a separator and the name.
  - A separator is one or more backslashes (`\`, JSON's `\\`, a repr inside JSON's `\\\\`) or `/`.
  - The name runs to the next separator or a character Windows forbids in names (`<>:"|?*`, control characters).
    A JSON `\uXXXX` escape counts as part of it.
  - `Public`, `Default`, `Default User` and `All Users` are Windows' own folders and stay.
- `WSL_HOME` matches `wsl.localhost` or `wsl$` after a separator, then `<distro>`, `home` and the name. This covers
  `\\wsl.localhost\...`, `\\wsl$\...`, `//wsl.localhost/...`, the doubled forms and `\\?\UNC\wsl...`.
- `home_pattern()` covers Path.home() in four forms: as HOME spells it, its real path, and each as JSON writes it
  (non-ASCII escaped or not). A match must not continue a name, so `<home-root>/x2`, `<home-root>/x.old` and `<home-root>/x-y` stay.
  A home at `/`, or none at all, means there is no home to hide.
- `Bundle.text(bytes)` runs `scrub` with surrogateescape, so bytes that are not UTF-8 are kept as they were.
  - `Bundle.file` scrubs what it reads. `Bundle.json` scrubs the JSON it makes. MANIFEST.txt is scrubbed as a whole:
    the `home:` and `cache:` lines, every source and every reason.
  - `refused` and the manifest's sizes are judged on the scrubbed bytes. A file over MAX_BYTES on disk is still left
    out unread, as before.
- MANIFEST.txt gains `NAMES_LINE`, just before the closing feedback line (tests read that line as the last one):
  "The user's folders are written without his name: the Linux home as ~, a Windows profile as C:\Users\<user>."
- The module docstring has a new paragraph, "The user's name".
- Not changed: the CLI's own "in Windows: ..." line, anything that charts, eval/'s zip, and the logs on disk.

Docs:
- DESIGN 4.5's "Diagnostics bundle" line now says what is hidden and how.
- The guide's Diagnostics sentence (section 6) says the user name is taken out of the folder paths, which read `~`
  and `C:\Users\<user>`.

### Spellings covered (all in the bundle test, made-up names `madeup`, `Made Up`, `M\u00e0deup`)

| Spelling | Written as |
|---|---|
| Linux home `$HOME/...` (also `$HOME` alone), its real path through a link, and `M\u00e0deup` as JSON escapes it | `~/...` |
| `C:\Users\Made Up\...` and lowercase `c:\users\madeup\...` | `C:\Users\<user>\...` (the case is kept) |
| `C:\\Users\\...` (JSON) and `C:\\\\Users\\\\...` (a repr inside JSON) | the same with `<user>` |
| `C:/Users/M\u00e0deup/...` | `C:/Users/<user>/...` |
| `/mnt/c/Users/Made Up/...` | `/mnt/c/Users/<user>/...` |
| `\\wsl.localhost\<distro>\home\madeup\...` and `\\wsl$\<distro>\home\M\u00e0deup\...` | `...\home\<user>\...` |
| `C:\Users\Public\Documents` | kept |

### Tests (`tests/test_diagnostics.py`)

Changed:
- The `home` fixture puts the songcharter home inside a made-up `$HOME` (`<tmp>/users/madeup/.songcharter`), with
  the cache outside it.
- `test_the_bundle_holds_the_reports_and_never_audio` now expects:
  - `home: ~/.songcharter` and `cache: <its path as it is>`;
  - the left-out lines with `~/.songcharter/logs/...`;
  - clonehero.json's `documents.windows` as `C:\Users\<user>\Documents` (it was the mojibake'd made-up name);
  - the manifest's new line.

New:
- `test_no_file_in_the_zip_names_the_user`: each spelling goes in four places: a log, a pipeline.json (with
  `ensure_ascii`, plus a repr of the list in an error string), a report.json (non-ASCII as it is) and clonehero.json
  (made here). It checks:
  - no made-up name, raw or `\u`-escaped, is in any member;
  - every `.json` member loads;
  - each path is there in its written form;
  - the manifest has `home: ~/.songcharter`, the cache as it is, the log's size as written, and `NAMES_LINE`.
- `test_the_guard_and_the_sizes_are_judged_on_what_is_written` (MAX_BYTES set to 1000):
  - a log of 980 bytes on disk that `<user>` makes 1,260 bytes is left out ("1260 bytes, over 1000");
  - a log of home paths goes in as `~/x` lines, and the manifest gives its written size (20).
- `test_what_is_not_his_folder_stays`: `<home-root>/x2`, `.old`, `-x` and a bare name stay; `madeup.` gives `~.`; an
  existing `C:\Users\<user>` is not written again; a home at `/` gives no pattern.
- `test_the_home_as_json_writes_it_and_by_its_real_path`: HOME is a link to `<tmp>/users/M\u00e0deup`, and the real
  path and the JSON-escaped one both become `~`.

Without the fix, all four tests above fail when run against main's diagnostics.py with the new tests:
- the bundle test: clonehero.json's documents are not equal;
- the names test: `('logs/ui.log', 'madeup')` is still in the zip;
- the size test: `logs/grows.log` goes in;
- the two unit tests fail because `home_pattern` does not exist on main.

Command:

```
cp songcharter/diagnostics.py <scratch>/fixed.py; git show origin/main:songcharter/diagnostics.py > songcharter/diagnostics.py
PYTHONDONTWRITEBYTECODE=1 <venv>/python -m pytest -q -p no:cacheprovider --basetemp=<shm>/pt-zipnames tests/test_diagnostics.py
-> 4 failed, 5 passed
```

The fixed file was then restored.

Mutations: 20 breaks, each run against test_diagnostics.py, and every one failed at least one test.

| Break | Caught by |
|---|---|
| no scrub in `Bundle.file` | names, size |
| no scrub in `Bundle.json` | bundle, names |
| no scrub of the manifest | bundle, names |
| `PROFILE` dropped | bundle, names, size |
| `WSL_HOME` dropped | names |
| the Linux home dropped | all four |
| the separator a single backslash | bundle, names |
| the separator without `/` | names |
| the name without `\u` escapes | names |
| `PROFILE` case-sensitive | bundle, names, size |
| `/mnt/<drive>` dropped | names |
| `NOT_USERS` dropped | names |
| the home's lookahead dropped | not-his-folder |
| the home's JSON spellings dropped | home-json |
| the real path dropped | home-json |
| `NAMES_LINE` dropped | bundle, names |
| `refused` on the bytes read | size |
| the manifest's size from the bytes read | names, size |
| a home at `/` not skipped | not-his-folder |

### Checks

Affected test files, run with the session's venv from the worktree (no `__pycache__` left):

```
PYTHONDONTWRITEBYTECODE=1 SONGCHARTER_SCAN_CHART=<checkout>/tools/scan-chart/scan.cjs <venv>/python -m pytest -q \
  -p no:cacheprovider --basetemp=<shm>/pt-zipnames tests/test_diagnostics.py tests/test_ui_feedback.py tests/test_ui_server.py
-> 168 passed in 77.03s
```

After the last test was added, `tests/test_diagnostics.py` alone gave 10 passed. I did not run the suite, a golden
run or a chart, as the brief says. Nothing here is on the charting path.

Privacy checks: per changed file, `EVAL_DATA=$DEV/eval python3 -I eval/privacy_check.py <file>` and the same with
`$DEV/eval-set20`. I read only the last line, and ran each on main's version of the same file too:

| File | eval | eval-set20 |
|---|---|---|
| `songcharter/diagnostics.py` | 0 found (main 0) | 0 found (main 0) |
| `tests/test_diagnostics.py` | 0 found (main 0) | 0 found (main 0) |
| `docs/guide/windows-wsl.md` | 0 found (main 0) | 0 found (main 0) |
| `docs/DESIGN.md` | 0 found (main 0) | 30 found (main 30) |

DESIGN.md's 30 set20 hits are already on main; this branch adds none.

Personal-details scan: I scanned the added lines of `git diff main...HEAD` and both commit messages for home paths,
user and machine names, emails and model names. The only names in them are made up (`madeup`, `Made Up`,
`M\u00e0deup`, `mu`, `Fixture`, `/fixture<home-root>/madeup`). No lyric, and no model name apart from the trailers.

CI: run 42855414836 (push on 8ba53e1), in progress when this report was written:
<repo>/actions/runs/42855414836

### Left with a name in it, or worth knowing

- The CLI's printed "in Windows: \\wsl.localhost\<distro>\home\<name>\..." line is left, as the brief says. It is
  on his own screen and not in the zip.
- A bare user name elsewhere in the text is not chased, as the brief says. For example, a log line that prints a
  user name with no path around it stays.
- Only this machine's Path.home() (and its real path) becomes `~`. Another Linux user's `<home-root>/<other>` stays, and
  so does a home path written while HOME pointed somewhere else. The profile and `\\wsl...` spellings are found by
  pattern whatever the machine.
- Over-reach, which is safe for privacy:
  - a profile folder that ends a path inside a sentence takes the words after it, up to the next separator or a
    character Windows forbids ("saved C:\Users\X for later: ok" becomes "saved C:\Users\<user>: ok");
  - a home path inside a longer path (`/data<home-root>/x/...` when HOME is `<home-root>/x`) becomes `/data~/...`;
  - a folder right under a single-backslash profile whose name starts with `u` and four hex digits is taken as part
    of the name.
- clonehero.json's `documents.windows` no longer shows a user name decoded with the wrong code page, since the name
  is now `<user>`. Mojibake in the folders after it (a localized Documents) still shows, and `documents.linux` being
  null still marks the failure.
- feedback.json: a path typed into a spot's note is rewritten too, because every text member is.
- A file over 5 MB on disk is left out unread, even if the rewrite would have brought it under. Its manifest line is
  rewritten. Zip member names are not rewritten: they hold no home (`logs/<log>`, `work/<song>-<hex>/...`).
- Not touched (outside the brief's list): README.md's line "It holds no audio, charts, lyrics or pictures" and the
  page's Diagnostics caption in `songcharter/ui/static/index.html`. Both still describe the zip correctly and say
  nothing about paths. PROGRESS.json is the orchestrator's.
