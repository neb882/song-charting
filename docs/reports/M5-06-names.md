# M5-06 (names): the builder's report

Branch `m5-06-names` (worktree `<worktree>`), from main at fbd9751. Order: `docs/work-orders/M5-06-names.md`.

## Commits

| commit | what |
|---|---|
| bb74068 | Names: "Artist - Title" from the file name, and the album's "<name> - (Single)" (pipeline.py metadata, test_pipeline, test_ui_server) |
| 53c5923 | Folder names cut at a word; the library folder's name up to 80 (cache.py, ui/jobs.py, test_cache, test_ui_jobs) |
| b11a4f0 | A song too short or silent is refused after the decode (exit 2) (pipeline.py check_song, test_pipeline) |
| 32eb5bc | CI: the results hook's clip is named "Test Artist - Test Clip" (packaging/ci/linux.d/60-results.sh) |
| b1f8ef0 | DESIGN 2.13 and the README: the names, the two folder limits, the songs refused |
| 52994dd | Review fixes: "- Title" gives the title alone; tests for the reserved branch and three digits |

Each message ends with the brief's two trailer lines.

## What changed

1. **The file name** (`pipeline.from_file_name`, used by `song_metadata`). When no tag gives the artist (`artist`,
   `album_artist`, `albumartist`), the cleaned stem is split on `NAME_SEPARATOR` (a hyphen, en dash or em dash with
   a space on each side, as lookarounds, so "Artist - - Title" splits on both dashes). A track number is dropped when
   it is the whole first part and at least two parts follow ("01 - Artist - Title"), or stripped from the front of the
   first part when followed by a dot or a space ("01. Artist", "1.Artist", "01 Artist"); a first part left blank by
   that ("01. - Title") is dropped too when two parts follow. The artist is the first part, the title the last; a part
   blank after trimming is left out. Both get origin "file name" and fill only keys the caller and the tags left
   empty. No separator, or a tagged artist: the stem is the title, as before (`Path(path).stem`, unchanged).
   `/api/upload` already called `song_metadata` with the name as dropped, so its answer carries "file name" with no
   change to server.py; app.js's `fillOptions` already prefilled every origin but "default", so no change there.
2. **The album placeholder**: `DEFAULTS["album"]` is `"{name} - (Single)"`, formatted with the resolved name (given,
   tag, file name or stem); origin "default", so the page shows it as the Album field's placeholder. Genre and year
   keep "Unknown".
3. **Folder names at a word** (`cache.safe_name`): after the code-unit cut, when the cut fell inside a word (the kept
   text does not end in a space and the next character is not one), it goes back to the last space if what is left,
   trailing spaces and dots stripped, is at least `limit - WORD_BACK` (12) units; else the hard cut stands. The
   reserved-name branch reuses the same cut. The work folder keeps `NAME_MAX` 40; `ui/jobs.LIBRARY_NAME_MAX` = 80 for
   `output_folder`. The deepest installed Windows path (clonehero.py's `.<name>.songcharter-<8 hex>.tmp\background.jpg`
   under `C:\Users\<20 chars>\Documents\Clone Hero\Songs`) is 178 characters, 187 with OneDrive's Documents.
4. **The autochart job's metadata**: checked, nothing to do. `engines.guitar(..., meta["name"], meta["artist"])` sets
   `AC_TITLE`/`AC_ARTIST` from `meta`, and neither is in the take's cache key (`autochart.take_key`), so the guitar
   caches stay valid.
5. **Short or silent songs** (`pipeline.check_song`, called in `_engine_stages` right after `end("decode")`, before
   the device choice and the separation): under `MIN_SONG_S` 10 s, "<file> is 4.00 s long: songcharter charts songs
   of 10 s or more"; peak under `MIN_PEAK_DBFS` -60 dBFS, "<file> is silent (its peak is -60.9 dBFS, under -60
   dBFS): there is nothing to chart", or "(every sample is 0)". InputError, so exit 2; pipeline.json records the
   decode stage and the error.
6. **CI**: 60-results.sh charts its clip as "$CI_TMP/Test Artist - Test Clip.flac" (the hook's clip is a FLAC since
   M4-11, so the order's ".wav" became ".flac"). Its only song.ini check before was `charter = songcharter`, which
   still holds, so the clip was renamed. New checks: the upload answer's artist and title with origin "file name";
   the installed folder named "Test Artist - Test Clip"; song.ini's `name = Test Clip`, `artist = Test Artist`,
   `album = Test Clip - (Single)`.
7. **Docs**: DESIGN 2.13 gains "Names" (the rule, its known misreadings, the placeholders, the two limits) and
   "Songs refused"; two sentences in DESIGN 2.0's code table (pipeline.py's metadata, cache.py's name) were stale and
   now point at 2.13; the README gains a "Title, artist and album" bullet.

## Checks

- **Targeted tests** (while the heavy lock was held by the golden base): the new and changed tests in test_pipeline,
  test_cache, test_ui_jobs and test_ui_server pass; test_cache.py and test_ui_jobs.py whole: 90 passed.
- **Breaking the code** (27 breaks, each restored after; script in the session's scratch folder): every one failed a
  new test. Gate on the artist tag removed; no track number before a separator; none before the artist; hyphen only;
  no spaces needed around the separator; title from the second part; blank parts counted; file name over the tags;
  album "Unknown"; album from the stem instead of the resolved name; origin "tag file"; no length check; `<=` for
  `<` on the length; no silence check; peak without abs; -50 dBFS; check_song not called; check_song moved after the
  separation; no word cut; WORD_BACK 13; WORD_BACK 11; back to a space even at a word's end; the stripped dot
  counted; the library folder at 40; at 81; the page prefilling only tags; the page showing no placeholder.
- **The librosa fallback around the limits** (find_sections, backend librosa): a 4-s tone and 12 s of silence raise
  `ParameterError` (the PROGRESS finding reproduced); a 10-s tone, a 10-s tone or noise at -59 dBFS, a 12-s song that
  is 2 s of tone then silence, silence then 2 s of tone, and a 12-s fade-in all give sections.
- **The full suite** (the worktree's own .venv from `uv sync --frozen --extra cpu --extra app --extra dev`, on the
  heavy lock): `SONGCHARTER_SCAN_CHART=$PWD/tools/scan-chart/scan.cjs uv run python -m pytest -q -p no:cacheprovider
  --basetemp=/dev/shm/pt-m5-06` -> `890 passed, 4 skipped in 641.50s (0:10:41)`. The first try, CLAUDE.md's
  `uv run pytest ...`, stopped at collection: `tests/test_golden.py` `from eval import golden` -> `ModuleNotFoundError:
  No module named 'eval'` (the `pytest` script does not put the checkout on sys.path, and the editable install maps
  `songcharter` only); `python -m pytest`, as CI runs it, does. CLAUDE.md's command may want `uv run python -m pytest`.
- **Golden** (`--expect none`): warm, from the worktree's .venv with the brief's environment, against the base the
  orchestrator made at fbd9751 (`$DEV/golden/base`): `python -m eval.golden run --code <worktree>
  --out $DEV/golden/m5-06 --threads 2` -> `summary: $DEV/golden/m5-06/summary.json (316 s)`,
  exit 0, engines that ran: none (every cache answered); `python -m eval.golden diff $DEV/golden/base
  $DEV/golden/m5-06 --expect none` -> `golden diff: no UNEXPECTED change`, exit 0. Every song's results
  (hashes, counts, scores) identical; pooled guitar Expert F1@50 0.8527 -> 0.8527.
- **CI**: `gh workflow run ci --ref m5-06-names`, run https://github.com/neb882/song-charting/actions/runs/42023982237
  on b1f8ef0: success, `linux` and `windows` both success. The linux log shows the new checks of 60-results.sh:
  `60-results: the names from the file's: Test Artist - Test Clip, ['album = Test Clip - (Single)', 'artist = Test
  Artist', 'name = Test Clip']`, the clip installed into `.../Songs/Test Artist - Test Clip`, and `60-results: ok`.

## Uncertain, or for the orchestrator

- **Read literally: "when no tag gives the artist".** With an artist tag and no title tag, the stem stays the title
  ("01 - Band - Song" stays whole). The order's "a tagged artist over its artist" is then implied by the gate. The
  other reading (each of artist and title falls back to the file name separately) is a one-line change
  (`tagged_artist` gate) and its test (`test_the_tags_and_the_caller_win_over_the_file_name`).
- **Misreadings the spec's rule makes** (DESIGN 2.13 lists them; the page's fields fix them): "3 Doors Down - X" and
  "5 Seconds of Summer - X" lose the leading number as a track number ("one to three digits followed by a space"),
  and "01 - Title" (a ripped track with no artist) gives the artist "01". Not changed: the order's rule is explicit.
- **The order's file list** limits pipeline.py to `song_metadata` and the metadata constants, but item 5 needs a
  check after the decode: `check_song` is a new function beside `_decode` and one call line in `_engine_stages`
  (after the decode's `end`), away from the guitar stage M5-05 touches.
- **Left open**: a file silent but for one click above -60 dBFS passes the peak test and the librosa fallback still
  raises (exit 3); found by hand, not a realistic song. A peak test is what the order asks for.
- **The page's album placeholder** is computed from the upload's title; when the person edits the title, the
  placeholder does not follow, though the chart's album will ("<edited title> - (Single)"). Updating it live would
  need a listener outside `fillOptions`.
- **The uploaded file** is still stored as `safe_name(stem)` at 40 units: the chart child reads that cut name if the
  page's title and artist fields are emptied (the page sends them as given otherwise).
- **"Band - Song -"** (a trailing dash) gives the title "Song -": the trailing dash has no space after it.

## Hard-rules scan

Scanned `git diff main...HEAD` and the five commit messages before the push: no lyrics, no audio or other binary
files (the tests write their WAVs into temporary folders; the diff only names files), no assistant model names (the
messages carry only the brief's trailer lines), no personal details (made-up band and song names, `C:\Users\<profile>`
placeholders). No commit came after the push.

## Housekeeping

- The worktree's `.venv` and `tools/scan-chart/node_modules` stay for the reviewer; `/dev/shm/pt-m5-06*` deleted.
- `$DEV/golden/m5-06` holds the warm run (summary, report.md, song folders); the base is untouched.
- `df -h /`: 18 GB free after the runs.
- PROGRESS.json not edited (the orchestrator keeps it); the order file needed no change.

## Review fixes (52994dd)

The review (no major finding) had three minor ones, all fixed:
- **R3** (the order's "- Title"): `NAME_SEPARATOR` also takes a dash at the start of the stem with a space after it
  (`(?:(?<= )|^)[-\u2013\u2014](?= )`), so "- Some Song" is a blank artist (left out) and the title "Some Song", album
  "Some Song - (Single)". The test row changed from "- Some Song" to "Some Song"; new rows "\u2013 Some Song" (title
  "Some Song") and "-Some Song" (no space after the dash: no separator, the stem is the title). DESIGN 2.13 says so.
- **R1**: a `test_safe_names` row for the reserved branch at the limit: "CON." + 34 x "a" + ".b" -> "_CON." + 34 x "a".
- **R2**: a row "1984 - Made-Up Band - Some Song" -> artist "1984", title "Some Song".
- **Breaks**, each restored after: the reserved branch as `("_" + text)[:limit]` fails the R1 row; `TRACK_NUMBER`
  `{1,4}` fails the R2 row; the old separator (no `^`) fails the "- Some Song" and en-dash rows; a leading dash
  without the space taken as a separator fails the "-Some Song" row.
- **Targeted tests**: 57 passed (test_pipeline and test_cache, the names' and the refusal's tests).
- **Full suite** after the fixes (tools/heavy.sh, `uv run python -m pytest -q -p no:cacheprovider --basetemp=/dev/shm/pt-m5-06`): `894 passed, 4 skipped in 673.45s (0:11:13)`.
- **CI** on 52994dd: https://github.com/neb882/song-charting/actions/runs/42048917512, success (linux and windows); the log has `60-results: the names from the file's: Test Artist - Test Clip, [...]` and `60-results: ok`.
- **Golden** not run again: the fix is in `from_file_name` only, and the reference files are `input.wav`, with no
  separator; golden compares notes, not song.ini.
- **Hard-rules scan** of the new commit's diff and message: test strings and the trailer lines only.

## Review (sc-reviewer, 2026-11-05)

# M5-06 (names): review

Branch m5-06-names at b1f8ef0, diff fbd9751...origin/m5-06-names. Lens: the metadata rule, safe_name's word cut,
the library limit, check_song, the CI hook, docs. Tested in a copy (/dev/shm/review_m506, deleted after); targeted
tests on the copy: 80 passed. 11 breaks run (script: scratchpad/rv/breaks.py): 9 caught, 2 survived (R1, R2).

No major finding. The rule, precedence, origins (pipeline.json/report.json/upload answer share one origin dict),
the 80-unit library limit and its 178-character Windows path, check_song's placement (after the decode's end,
before engines.device/separate; no effect on long songs or on determinism), the CI hook's new asserts and the docs
match the order and the code. The builder's "Decisions for you" are not defects against the order.

## R1 (minor): safe_name's reserved-name branch can be gutted unnoticed
songcharter/cache.py:157 (`text = "_" + cut(text, limit - 1)`). Break: `text = ("_" + text)[:limit]`; tests in
tests/test_cache.py and tests/test_ui_jobs.py: `48 passed`. It ships a name Windows cannot keep (a trailing dot):
  real : safe_name("CON." + "a"*34 + ".b") == '_CON.aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'
  break: '_CON.aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.'
No test feeds the reserved branch a name at the limit. Fix: one parametrize row with that stem.

## R2 (minor): the three-digit bound on a track number before a separator is untested
songcharter/pipeline.py:143 (`TRACK_NUMBER = re.compile(r"[0-9]{1,3}")`). Break: `{1,4}`; tests in
tests/test_pipeline.py -k "metadata or file_name or tags_and or too_short": `18 passed`. Shipped, "1999 - Made-Up
Band - Some Song" would give the artist "Made-Up Band" instead of "1999" (the order: one to three digits). Today's
code: `1999 | Some Song`. Fix: a row "1984 - Made-Up Band - Some Song" -> artist "1984". (The "1984 Band" row only
covers TRACK_PREFIX.)

## R3 (minor): "- Title" keeps the dash in the title and the album
songcharter/pipeline.py:142 (`NAME_SEPARATOR`, lookbehind needs a space before the dash). The order's example
"the stem '- Title' gives no artist" reads the leading dash as a separator with a blank artist part; the code does
not split it, so the dash stays, while "01. - Title" drops it:
  '- Some Song'     -> Unknown | - Some Song | - Some Song - (Single)
  '01. - Some Song' -> Unknown | Some Song   | Some Song - (Single)
tests/test_pipeline.py pins "- Some Song" as the title. Judge whether the order meant "Title"; if so, allow `^` as
well as a space before the dash (or strip a leading separator), and change that row.
