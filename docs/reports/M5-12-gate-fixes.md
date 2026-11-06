# M5-12: v0.2.0's release gate fixes (the full review's findings)

Two branches: `m5-12-gate-fixes` (the code findings, built by an sc-builder) and `m5-12-gate-docs` (the docs and
privacy findings, written by the orchestrator), each reviewed by an sc-reviewer. The full review workflow's findings
(four lenses over v0.1.0...77c3c8e, a skeptic per major) are summarised in the order, docs/work-orders/M5-12-gate-fixes.md;
their text stays in the orchestrator's scratch folder because two of them concern where the stress set's private
names had leaked.

## The code branch: the builder's report


Branch `m5-12-gate-fixes` (worktree `<wt>/m5-12`), from main at 9ac6fb8 (77c3c8e plus the order). main had not moved
when the branch was last pushed, so there was nothing to merge in.

## Commits

| commit | what |
|---|---|
| ff9d5ab | The version is 0.2.0 (`__init__.py`, `pyproject.toml`, `uv.lock` by `uv lock`), and build.sh builds only HEAD's version; the hooks 30/50/70 build HEAD's version; 75-update checks HEAD is newer than v0.1.0 and lists the build's own release |
| 523dd5b | The work folder is found by its key when its name changed (`cache.work_folder`, `cache.by_key`); 75-update charts its clip under a made-up long name |
| 47cc9cb | A background.* is a build's own only when the earlier build's report.json recorded it (`assemble._ours`) |
| b08ab88 | A running server of another version is not reused (exit 2, InputError); the notice says "close the songcharter window" |
| 7b7c2ab | Tests: `_octave_pass` when the doubled pass raises InputError; the baseline scrub's four parts |
| 5388b3e | Test fix: build.sh's version test runs the build.sh under test in its clone (two breaks had passed) |
| 89f0fdb | DESIGN: §2 work folder (found by the key), the cache.py row, §2.13 folder names, §2.16 (a person's background), §4.5 (the version check, the notice's words, the running-instance check) |
| 82f11c0 | 75-update: after the bump, bass runs again on the update (its cache key holds songcharter's version); the rest is cached |

20 files, +519 −59.

## Item 1: the version, and build.sh's check

- `songcharter/__init__.py` and `pyproject.toml`: 0.2.0. `uv lock` changed one line of `uv.lock` (songcharter
  v0.1.0 -> v0.2.0); `uv lock --check` passes ("Resolved 117 packages").
- `packaging/release/build.sh <version> <out>`: right after the usage checks, before anything is written, it reads
  HEAD's `songcharter/__init__.py` (`git cat-file blob HEAD:...`, as the rest of build.sh reads HEAD) and HEAD's
  pyproject.toml `[project]` version, and stops with exit 2 unless the dotted-integer part of `<version>`
  (`^[0-9]+(\.[0-9]+)*`) equals that of both. A suffix may follow (`0.2.0-ci-<sha>`, `0.2.0-test`). Message:
  `build.sh: 0.3.0 is not HEAD's version: its songcharter/__init__.py says '0.2.0' and its pyproject.toml '0.2.0'.
  Build that version (a suffix such as -ci-<sha> may follow it), or bump both (then uv lock) and commit first`.
- CI hooks: 30-install.sh, 50-e2e.sh and 70-release.sh hard-coded `0.1.0-ci-<sha>`; each now builds
  `<HEAD's __version__>-ci-<sha>`, read as 75-update.sh reads it. 75-update.sh:
  - fails unless HEAD's version is newer than `old=0.1.0` (`sort -V`), so the update path is always from an older
    install;
  - its doctor check (`songcharter 0.2.0, Python 3`) now tells the two versions apart;
  - `releases-010.json` lists v0.1.0 and v<HEAD's version> (the release this build is): the page must give no
    notice for it, which is the symptom correct-1 described, end to end;
  - after the bump, the update's re-chart runs bass again (see "Found on the way"), so the hook checks bass ran and
    separate, drums, sections and guitar are "(cached)".
- Tests (tests/test_install.py): the two build tests use `<HEAD's version>-test` and the tarball's `__init__.py`
  must say HEAD's version; `test_build_refuses_a_version_that_is_not_heads`: seven wrong versions (minor+1, a 4th
  part, 2 parts, a prefix digit, patch+1 with -ci-, `0.2.01-test`, 0.0.1) each exit 2 with the message and no
  output folder; in a clone running the build.sh under test, an uncommitted bump to 9.9.9 is refused (HEAD says
  0.2.0) and a committed pyproject.toml of 0.0.1 is refused for `0.2.0-ci-abc1234`.

## Item 2: the work folder after M5-06's name change

- `cache.work_folder(root, stem, key)`: today's name (`work/<safe_name(stem)>-<key>`) when it exists; else
  `cache.by_key(root, key)`: the folders `work/*-<key>` that are directories (not links) whose marker
  (`read_marker`, ours) holds `"key": key`, the most recently used first (marker `used`), then by name; else
  today's name. `pipeline.chart` is unchanged (it calls `work_folder`).
- The page's upload name: not changed. The upload is stored as `uploads/<16 hex>/<safe_name(stem)><ext>` and the
  child chart names its work folder from that stem, but the lookup is by key, so the name does not matter to it.
  (A v0.1 upload of the same file under the old name sits in the same `uploads/<16 hex>/` folder and goes with it
  in the 7-day prune.)
- Consequence, written into DESIGN §2: a renamed copy of the same file now finds the same folder (before, "a renamed
  copy gets a folder of its own"). Nothing cached depends on the file's name (the metadata, art and lyrics are made
  per run).
- Tests: `test_cache.py::test_an_older_versions_work_folder_of_the_same_file_is_found` (made-up stem "Imaginary Band
  Name - A Made Up Song Title (Live)", whose v0.1.0 cut is "...Song Tit" and today's "...Song"): no folder: today's
  name and nothing made; a folder of another key, an unmarked one, one whose marker is not ours, a link to a marked
  folder, and a file with the suffix: today's name; the v0.1-named folder: found, also for a renamed stem; another
  key's lookup ignores it; of two, the more recently used; today's name when it exists.
  `test_pipeline.py::test_a_v01_work_folder_of_a_long_named_song_is_reused`: chart, rename the folder to v0.1.0's
  name, chart again: pipeline.json's work is the old folder, no new folder, every stage but assemble cached, the
  guitar engine given the old folder.
- CI: 75-update.sh now charts its clip as `~/clips/Imaginary Band Name - A Made Up Song Title (Live).wav` with the
  real v0.1.0 install, then with the new version, and checks the same work folder is used, that its name is not
  today's `safe_name` (so the lookup is really exercised), and the cached stages.
- By hand (the order's check), through tools/heavy.sh, in a cache of its own (`SONGCHARTER_CACHE` in the scratch
  folder; HOME kept, so the model weights were not fetched again): a 30-s clip made by `packaging/ci/make_clip.py`
  under the made-up long name, charted (`--takes 1 --device cpu --no-preview`), its folder renamed to v0.1.0's cut,
  charted again:
  ```
  work folder: <scratchpad>/byhand/cache/work/Imaginary Band Name - A Made Up Song Tit-c5b7ed9068d6e937 (86 MB; ...)
  [2/7] separate: 6 stems on cpu (cached), 0.1 s
  [3/7] drums: 119 Expert onsets (cached), 0.8 s
  [4/7] bass: 120 Expert onsets (cached), 0.0 s
  [5/7] sections: allin1 harmonix-fold0 on cpu, 3 segments (cached), 2.9 s
  [6/7] guitar: 1 take, 23 Expert onsets in the first (cached), 0.0 s
  stages cached: {'decode': True, 'separate': True, 'drums': True, 'bass': True, 'sections': True, 'guitar': True, 'assemble': False}
  ```
  The first run had taken 23.3 s to separate and 46.2 s for the guitar take; one folder stayed in work/.

## Item 3: a person's own background

- `assemble.BACKGROUNDS` (the three names) and `assemble._ours(folder)`: the lower-case names an earlier build in
  that folder may have left: OUTPUT_FILES less the backgrounds, plus the background whose name report.json's
  `art.background` records with `"added": true`. A missing, unreadable or foreign report.json records none.
  `_foreign` (so `check_output`, for the output and its .failed), `_install` (read before the new report.json
  replaces the old) and `_remove_build` use it.
- So a background.* that no build recorded makes the build refuse the folder, "holds what a build does not write
  (background.png)", exit 2, before any work, as v0.1.0 did; one a build recorded is replaced, or removed by a build
  without one (M4-11's test of that, test_art's "a later build without a background takes the earlier one away",
  still passes). album.* is unchanged: it was in v0.1.0's OUTPUT_FILES, so v0.1 folders can hold a build's album
  art with no record of it.
- Tests: `test_assemble.py::test_a_persons_background_in_an_earlier_builds_folder_is_kept` (no report.json; records
  that are not one: added true without a file, added "yes", art null, a list, not JSON, bad bytes; a person's
  background.png beside a recorded background.jpg: refused, and `_install`, had it been reached, deletes only the
  build's own; the recorded one, in either case, replaced then removed; `_remove_build` of a failed build: its own
  goes with the folder, a person's stays). `test_art.py::test_a_persons_background_in_a_built_folder_stops_the_next_build`:
  a folder built by a chart, a background.png added, charted again with and without `--background`: exit 2 with
  the words, no engine called, every file as it was.

## Item 4: the running old server after an update

- The notice (app.js): "To update: close the songcharter window, open Ubuntu from the Start menu, paste this line
  and press Enter:" (the guide's words).
- `ui/server.py`: `other_version(theirs, url)`; `_main` raises `InputError` when the running instance's hello
  version is not this `__version__`, and `main` prints `songcharter: error: ...` and returns 2. No page is opened,
  the home is not touched. The message: `songcharter 0.1.0 is still running (http://localhost:8765/), and this is
  songcharter 0.2.0: close the songcharter window (closing it stops songcharter 0.1.0), then start songcharter
  again`. A version that is not a short plain string (missing, not a string, control characters) is named "another
  version of songcharter". From the Start-menu shortcut the launcher keeps the window open on a non-zero exit
  ("songcharter stopped (exit status 2); the error is above. Press Enter to close this window").
- Not stopped from here: the server has no way to be stopped from outside (no stop request, no pid file; only
  SIGTERM/SIGHUP/Ctrl+C from its window), and the old one may be running a chart. So, per the order, it says the
  old window must be closed.
- Tests: `test_ui_server.py::test_a_running_server_of_another_version_is_not_reused` (a stand-in old server in a
  thread answering /api/hello: a made-up version, none, one with an escape sequence, a number: exit 2, the exact
  words on stderr, nothing on stdout, no browser, no home made, the stand-in still answering; then this version:
  exit 0, "songcharter is running already", the page opened). The notice test has the new words.

## Item 5: test gaps

- `test_assemble.py::test_the_octave_pass_when_the_doubled_pass_finds_no_beats`: a second pass raising InputError:
  under auto the first grid, octave 1, `second` None, evidence ratio 0.0, the "first grid stays" reason and the
  "check the tempo" warning; with grid_octave 2, the InputError itself.
- `test_eval_stress.py::test_the_baseline_scrub_covers_the_alts_any_case_the_keys_and_the_leftover_paths`: every
  alt's md5 and charter scrubbed (and listed by secrets_of), values in other cases, a key that is an alt md5 and a
  key holding the artist, a path key; then with the path rule turned off (`S.PATH` never matching), a leftover
  `/home/`, `/tmp/`, `<shm>/` or `/root/` path each stops the copy (exit 2, nothing written). eval/stress.py
  is unchanged: no real gap showed.

## Breaking the code (each break, then the tests named; the file restored with git checkout)

All 25 breaks fail a test (`<scratchpad>/breaks/run.py`, results in `breaks/result-1.txt` and the rerun):

| break | caught by |
|---|---|
| build.sh: the check's `exit 2` removed | test_build_refuses_a_version_that_is_not_heads |
| build.sh: pyproject.toml not compared | the same (first MISSED: the clone ran HEAD's build.sh; fixed in 5388b3e) |
| build.sh: the working copy's `__init__.py` read, not HEAD's | the same (first MISSED, as above) |
| build.sh: no suffix allowed | test_build_writes_the_three_assets |
| cache: today's name only | test_an_older_versions_work_folder... (and the pipeline test) |
| cache: the marker's key not compared | test_an_older_versions_work_folder... |
| cache: links count | the same |
| cache: the oldest of several | the same |
| cache: the key lookup before today's name | the same |
| assemble: every background ours (M4-11's rule) | test_a_persons_background_in_an_earlier_builds_folder_is_kept |
| assemble: _install deletes every OUTPUT_FILES name | the same |
| assemble: _remove_build deletes every OUTPUT_FILES name | the same |
| assemble: the record's `added` not checked | the same |
| assemble: a recorded background never ours | the same |
| assemble: `_ours` read from the staging folder | the same |
| server: any version reused | test_a_running_server_of_another_version_is_not_reused |
| server: InputError not caught (exit 3) | the same |
| server: the version printed unchecked | the same |
| app.js: "close this window" | test_the_page_shows_the_update_notice_copies_the_line_and_later_hides_it |
| octave: `except InputError` made dead | test_the_octave_pass_when_the_doubled_pass_finds_no_beats |
| octave: the forced re-raise removed | the same |
| stress: alts out of secrets_of | test_the_baseline_scrub_covers_... |
| stress: case-sensitive | the same |
| stress: keys not scrubbed | the same |
| stress: no leftover-path check | the same |

## Checks

- Full suite, through tools/heavy.sh, `SONGCHARTER_SCAN_CHART=<wt>/tools/scan-chart/scan.cjs .venv/bin/python -m
  pytest -q -p no:cacheprovider --basetemp=<shm>/pt-m5-12` at 89f0fdb (82f11c0 changes only 75-update.sh, which
  no test reads): `1025 passed, 4 skipped in 728.94s (0:12:08)`.
- Golden, two songs, warm: `eval.golden run --code <shm>/m5-12-old` (a detached worktree of 77c3c8e) `--out
  $DEV/golden/m5-12-old --threads 2 --rerun bass --songs kimochi_warui,take_me_out`, the same from the branch into
  `m5-12-new`, then `eval.golden diff ... --expect none`: `golden diff: no UNEXPECTED change`, exit 0; every song's
  hashes, counts and scores identical; pooled F1@50 Expert guitar 0.8679, bass 0.8809, drums 0.9584, beat F1
  0.9820 on both sides. `--rerun bass` on both: the bass engine's cache key holds songcharter's version, so the
  0.2.0 side would have run it unasked (golden refuses that). Kept folders made by 8ba3cbdf590c, none made here.
- `uv lock --check`: "Resolved 117 packages in 3ms" (exit 0).
- `bash -n` on every changed hook.
- CI: run 42193149214 (<repo>/actions/runs/42193149214), workflow_dispatch on
  `m5-12-gate-fixes`, head 82f11c0af438, **success** (windows and linux). The suite there: `1025 passed, 4 skipped`;
  `all 8 Linux hooks passed: 10-lanes.sh 15s 20-device.sh 6s 30-install.sh 165s 40-ui.sh 28s 50-e2e.sh 466s
  60-results.sh 81s 70-release.sh 64s 75-update.sh 175s`. build.sh ran as `songcharter 0.2.0-ci-82f11c0` in 30, 50,
  70 and 75. 75-update's own lines: v0.1.0's chart of the long-named clip used `work/Imaginary Band Name - A Made Up
  Song Tit-c5b7ed9068d6e937`; after the update, doctor `songcharter 0.2.0, Python 3.13.17`, and the re-chart: decode,
  separate, drums, sections and guitar `(cached)`, `bass: 120 Expert onsets, 2.4 s` (run again), `the work folder of
  v0.1.0's name, ... Song Tit-c5b7ed9068d6e937, not today's (Imaginary Band Name - A Made Up Song), with its caches`,
  check_gate ok; with v0.1.0 and v0.2.0 listed and no kept answer, `update check: songcharter 0.2.0 is the newest`,
  `update: None`; `75-update: ok (0.1.0, then 0.2.0-ci-82f11c0 over it, and the notice)`. An earlier run,
  42192803675 (head 89f0fdb), was cancelled by me: its 75-update would have failed on bass, fixed in 82f11c0.

## Found on the way (for the orchestrator)

1. **The bump makes bass run again on each update** (and the lyrics engine, whose key holds the version too):
   `engines/bass.py versions()` puts `__version__` into its cache key ("the libraries whose versions can change the
   notes"). Before the bump both sides of 75-update said 0.1.0 and bass was cached; now it is not, so I changed the
   hook to check that bass ran and that the other engines were cached (82f11c0). Bass is seconds; the expensive
   stages (separation, sections, guitar takes) stay cached. Whether the version should be in bass's key is an
   engine decision outside this order; I left it.
2. The golden runs across this bump need `--rerun bass` on both sides (above). The gate's own golden run of the
   candidate against v0.1.0 already passes `--rerun drums,bass,guitar`.
3. album.* keeps v0.1's rule (a build's own without a record), since v0.1.0 had it in OUTPUT_FILES: a person's own
   album.png in a folder songcharter made is still replaced, as in v0.1.0. Not changed (out of scope, no
   regression).
4. README's update section quotes neither the notice nor the running-instance behaviour, so its words did not
   change; I did not touch it (the docs branch edits the same paragraph for docs-6).

## Not done

- PROGRESS, the work orders, PIPELINE and docs/reports are the orchestrator's (the docs branch).

## Scan

`git diff origin/main...HEAD` and the commit messages scanned for lyrics, audio, model names, personal details
and paths: none. The only matches are the attribution trailers, the generic path prefixes the scrub tests use
(`/home/`, `/tmp/`, `<shm>/`, `/root/`) and a made-up committer for a test's clone
(`made-up@example.invalid`). Test names and paths are made up; nothing of the stress set's songs.

## The code branch: review fixes (orchestrator, commit 11b0ea8)

- **F3** (a background replaced by hand): `assemble._ours` counts a recorded background as the build's own only while
  the file has the size report.json recorded (`art.background.bytes`), so a picture the person put in its place
  under the same name is refused ("holds what a build does not write"), never deleted. Test: the person's picture
  under the recorded name (another case) refused and kept; the recorded size: removed by a build without one. It
  fails when the size check is dropped.
- **F1** (build.sh's `__init__.py` comparison untested): the test commits an `__init__.py` at another version while
  pyproject.toml is HEAD's, and expects exit 2; it fails on the reviewer's break.
- **F2** (the version check skipped for `--no-browser`): the running-server test launches without a browser once; it
  fails on the reviewer's break.
- tests/test_art.py 18 passed; the background, build.sh and server tests pass. CI on 11b0ea8: run 42198171419, success.

## The code branch: the review (sc-reviewer)


**What holds:**
- v0.1.0's `/api/hello` carries `version`, so after the update the old server is refused with exit 2 and no page
  opens. The shortcut's `|| pause` keeps the message on screen, and `install.sh` never starts the page.
- v0.1.0's marker holds `key`, so `cache.by_key` finds v0.1 folders. v0.1.0's real `safe_name` of the CI stem gives
  "…Song Tit", which matches 75-update's expectation.
- build.sh refuses a mismatch on a clean clone (exit 2, the stated message).
- prune keeps a scratch folder that two kept folders share.
- `_install` and `_remove_build` take the earlier build's record before replacing it.
- Mutations the tests caught: cache (symlink check dropped, LRU order inverted, key check dropped, today's-name
  short-circuit dropped); assemble (`_ours(staging)` for `_ours(target)`, `OUTPUT_FILES` in `_remove_build`,
  `OUTPUT_FILES` in `_foreign`, the `added is True` check dropped); server (a missing version treated as the same,
  the `InputError` handler removed).

**F1 (minor, test gap): build.sh's `__init__.py` comparison can be removed without a test failing.** In
`packaging/release/build.sh:40`, `want=$(base "$head_init")` changed to `want=$(base "$head_project")` passes
`tests/test_install.py::test_build_refuses_a_version_that_is_not_heads`. That mutant builds a v0.2.0 tarball from a
commit whose `__init__.py` says 0.1.0 and pyproject 0.2.0 (exit 0): the order's item 1 defect. The real build.sh
refuses it. Every refusal case in the test also fails the pyproject comparison. Fix: a clone case with `__init__.py`
at another version and pyproject at HEAD's, expecting exit 2.

**F2 (minor, test gap): the version check in `songcharter/ui/server.py:1126` can be skipped for `--no-browser`
without a test failing.** `if why is not None:` -> `if why is not None and browser:` passes
`test_a_running_server_of_another_version_is_not_reused`, which always calls `S.main` with `browser=True`. The
Start-menu launch always opens a browser, so the friend's path is not affected. Fix: one call with `browser=False`.

**F3 (minor, by the order's rule): a background a build wrote, then replaced by hand under the same name, is
deleted by the next re-chart without `--background`.** `_ours` (`songcharter/assemble.py:475`) decides by the file
name in report.json alone. report.json's `art.background` keeps `bytes`, so a size check could tell the two apart. A
follow-up, not a blocker.

## The docs branch (orchestrator)

- `docs/reports/m5-plan-review.md`: 13 md5 prefixes (4 hex digits, five packages) replaced by `<id primary>` /
  `<id altN>` labels (docs-2); the rock stress song's title and artist removed from M5-00, M5-09 and PROGRESS
  (tests-3). The history keeps both: whether to rewrite it is the owner's (PROGRESS, deferred).
- `eval/privacy_check.py` (new): the stress set's md5s, their prefixes and its names in every tracked file, printing
  only where; PIPELINE's merge step runs it before every push to main.
- PIPELINE's release gate step 0 and M5-00 section 7 item 0: the version is the release's before the gate's runs
  (docs-1); PIPELINE's usage limit at 75/80 %.
- PROGRESS: the eight deferred items the merged orders fixed removed, `next` current (docs-3); the reports index
  lists M5-01..M5-11.
- DESIGN 3.3 and eval/README's stress table with pm2; DESIGN 3.6 and M5-00's stress check name the baseline each
  means (docs-4). DESIGN 2.6 and M5-01: 3,092 gaps are 19.7 % of the pooled strum gaps, the power-metal charts 37 %
  (docs-5). The README and the guide: the update check looks again an hour after a failed look (docs-6).
- A test flake found by the branch's CI: tests/test_ui_server.py's upload id upper-cased is refused only when it
  differs (the test WAV's bytes, so its key, depend on the runner's sin; one runner's key was all digits).
- CI on b1034db: run 42197210315, success.

## The docs branch: the review (sc-reviewer) and its fixes


Privacy lens: `EVAL_DATA=$DEV/eval python -I eval/privacy_check.py` on the worktree: 256 files, 14 md5s, 36 names, 0 found, exit 0. My own check, written separately (scratchpad/rv/mine.py: md5 substrings of 6+ hex anywhere, 4-5 hex tokens, names after NFKC and whitespace collapsing, so line wraps count, no refs.json skip) finds no md5 or prefix and no private name. Its only hits are one charter that refs.json also holds (25 files, public, skipped by design). The two checks agree on the tree. Separately: one stress charter's visible name (markup stripped) is in DESIGN.md 3 times since v0.1.0, as the official game developer's name. I read that as a coincidence, not a leak, and the tool cannot see it (R2). m5-plan-review.md: all 9 changed lines put the right primary/altN label in place of each prefix (scratchpad/rv/map.py: ok 9, bad 0). The 8 PROGRESS items removed are fixed on main. `next` and the gate entry match gate.log and the findings (4 lenses, 4 confirmed majors, 12 to the fixer; troop +0.161..+0.176, sooth +0.006, break identical, pm2 bass 0.800->0.777).

## R1 (major): eval/privacy_check.py:66-75: a multi-word name split by a line wrap is never found
scan() matches each line on its own, and the docs are hard-wrapped at 120 columns. 13 of the list's 37 names have several words. When the real list's names go through the tool's own scan() with one space turned into a newline, 13 of 13 are missed (scratchpad/rv/edge.py: "missed when wrapped 13 of multiword 13"). Made-up repro: `printf 'We charted Glimmer\nHollow for the set.\n...Glimmer Hollow\n'` with title "Glimmer Hollow". The output is `d.md:5: zorp: primary title` only: line 1-2 is not reported. Fix: scan the text with runs of whitespace collapsed (and map each hit back to its line), and add a test for it.

## R2 (major): privacy_check.py:39: a name that starts or ends with a non-word character can never match
`\b` + re.escape(v) + `\b` needs a word character at each end. 2 of the 37 real names (two charters, which hold markup tags) start and end with one, so the tool would miss them even verbatim. The text a doc would actually hold is the name inside the tags, and that is never checked either (edge2.py, edge3.py). Made-up repro: artist "Panic!", charter "<b>Moss Tarrow</b>", lines "by Panic! today" and "charted by Moss Tarrow": both are missed, exit decided only by the other line. Fix: use `(?<!\w)`/`(?!\w)`, and also check each name with its tags stripped.

## R3 (major, test the tests): tests/test_privacy_check.py misses breaks that would let leaks through
In /dev/shm copies, `python -m pytest tests/test_privacy_check.py` stayed at 5 passed under each of these breaks:
- the default mode gutted (`files = []` when no files are given): the documented pre-push run would then print "0 files ... 0 found" and exit 0. No test runs the git ls-files path.
- `MIN_NAME = 11`: the real run then checks 25 of 36 names. The tests' names are all 11 characters or more, apart from "fenwick", which they never assert is found.
- each hex token printed to stderr: the tests read stdout only, though the docstring promises the value never goes to either.
- the public skip loosened to a substring (`not any(v.lower() in p for p in public)`).
Fix: a test of main([]) in a temporary git repo, one short name asserted found, and stderr checked for the values too.

## R4 (minor): docs/PROGRESS.json next[1]: "the golden charts ... passed on 77c3c8e" overstates
gate.log: "test_song: ... exit 2"; "== golden exit 1"; golden diff "UNEXPECTED: 29". report.md, test_song: "Gate OK -> none ... UNEXPECTED: the build changed". tests-2 says this was an OOM kill caused by the reviewer, not the candidate. The pooled F1 row is right (test_song has no human chart), but the golden run did not pass. Say "6 of 7; test_song killed (tests-2), rerun after M5-12".

## R5 (minor): docs-6 and the version step are only half reflected
- docs/guide/windows-wsl.md:52, which the friend reads, still says "(the page looks once a day)". docs-6 named the guide, and only README was changed.
- PIPELINE.md release gate step 0 and M5-00 section 7 item 0 say `build.sh` refuses another version (M5-12). No such check exists on main, and the code branch m5-12-gate-fixes is not pushed. If this branch merges first, the docs describe a guard the code does not have.

## R6 (minor): privacy_check.py:83-92: failures exit 1, the "found" code, not 2
Outside a git checkout, the default run raises CalledProcessError and exits 1 with a traceback (seen in <shm>/review_m512d). A list that parses but has an entry without "id", or is a dict, gives a KeyError or TypeError and also exits 1. Both fail closed, but the docstring promises 2 for an unreadable list, and CLAUDE.md gives 3 for a bug.


Fixed in 91f53f6 (orchestrator): R1 and R2 (a name split by a line wrap, with comment markers between its words, is
found; so is one with markup or punctuation at its ends, and the name inside its tags); R3 (tests for the default
every-tracked-file run, the shortest name, stderr, the public skip by equality only, wraps, boundaries, tags; each of
the review's and the orchestrator's 11 breaks fails one); R4 (PROGRESS: 6 of 7 songs, the test song to rerun); R5
(the guide's update line); R6 (a list without ids, or no git, is exit 2). A game developer's name that one stress
chart's charter field also holds is skipped by its hash (DESIGN names the developer since before the stress set).
