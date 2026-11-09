# M8-04: the UI pass after v0.4, and the queue's design note (builder's report)

*Merged 2026-11-09 at da2b8e2 (branch head 4ccf649, CI run 42552379332 green on Linux and Windows: 1309 passed). The
review (an `sc-reviewer`, head 4845a78): no major finding, five minor ones (F1 the update after a multi-take guitar
untested; F2 the results route's flag-page count untested, with the page able to throw before the install box; F3 the
time left too low when take 1 reused a cached separation; F4 a refused "built" showing the Linux path; F5 the
lightbox's title counting the overview), all fixed in 4ccf649 (below); its own ten breaks, seven caught before the
fixes and all ten after.*

Branch `m8-04-ui-pass` (worktree `<wt>/m8-04`), from main at 01084fd, main merged in at 4845a78. Not merged.

## Commits

| Commit | What |
|---|---|
| 8361903 | Item 0: the queue's design note, in docs/work-orders/M8-10-queue.md ("The note"), sent to the orchestrator |
| 375f444 | M8-10: the orchestrator's decision on the note (A, B, C and E; "Your charts" its own order), as relayed |
| 941126c | Items 1-4 (the review's 5-8 and 10): the song's name and Open folder, flags to their pages and to Listen, the Songs folder's guess, Best or Quick |
| aaf94ef | Item 5: the time left after the first take (estimate.remaining, the snapshot's `remaining`, the page's countdown), and the pass's tests |
| f6a994a | Item 6: the not-answering heading |
| 3870449 | Item 7: DESIGN 4.5 and the guide's screens |
| d227637 | The lightbox's arrows as named entities (the 20-song privacy check read a numeric entity's digits as an md5 prefix) |
| 4845a78 | Merge origin/main (the guide's WSL step, PROGRESS, M8-12's order; no conflict) |

Items 1-4 share one commit: their hunks interleave in server.py, app.js and app.css (one CSS block, the OPEN
constant's hunk with PAGE_S, `clonehero()` beside `choices()`), and their tests are in one appended block with the page
test, which also covers item 5, so the tests went with item 5's commit. Files: only the order's (server.py, jobs.py's
snapshot field, estimate.py, the three static files, tests/test_ui_*.py, the guide, DESIGN 4.5, M8-10's "Design").

## What changed

- **Item 1, the built folder.** The Done screen's sentence names the song by its folder's name ("Made-Up Band - A
  Song is charted and passed its check."; a failed build: "<name> did not pass the check, so it is kept for a look
  (Open folder), not for Clone Hero.", without ".failed"). "Open folder" under it: `POST /api/open {"what": "built"}`
  opens the current result's folder (a failed one too); `OPEN` is now song, exports, built, and no path is read from
  the request. The results carry `windows_path`, the button's hover text. Note: `clonehero.windows_path` gives the
  `\\wsl.localhost\<distro>\...` form, the current name of `\\wsl$`; I kept it rather than build a second form.
- **Item 2, flags to pictures and sound.** `server.flag_at` reads a flag's part and start from its text (pipeline.json
  keeps the flags as `preview.Flag` strings, "guitar: gap 1:12.0-1:19.0 (5 measures)") and `flag_page` gives
  `floor(start / 60) + 1` kept among the pages (`PAGE_S` = `preview.render_pages`' default, which a test pins); the
  results' preview gains `page_s` and `at`. The page links each flag's start to its page in a lightbox (one modal
  `<dialog>`: Escape is the browser's own, the arrow keys, Before/After, Full size, Close, a click on the backdrop; a
  ctrl- or middle-click still opens a tab), the overview and thumbnails too; CSP unchanged. "Listen here" (for parts
  the chart has) sets Part and Expert and plays from `start - 1` (`currentTime` set before the file loads and again at
  `loadedmetadata`), scrolling the player into view. Edge: the text's start is rounded to 0.1 s, so a flag at 59.96 s
  reads "1:00.0" and links to page 2 while the stretch begins 0.04 s before it.
- **Item 3, the Songs folder.** `App.clonehero` returns `guess` always (clonehero.py untouched: the server adds it).
  When no folder is found the field holds the guess and the sentence says it is a guess and that no folder is there.
  Interpretation: the page already prefilled the guess when none was found (the review saw an empty box on a stand-in
  outside WSL, where there is no guess); "always" is taken as the server always giving it and the page saying what it
  is. "Another folder" still starts from the current folder.
- **Item 4, Best or Quick.** "Chart it" at the top and at the end. The upload answers `choices` ({"gpu", "best",
  "quick"}: `gpu` = the doctor's device CUDA and the guitar not found on the CPU; each estimate.for_job with default
  options, Quick with 1 take). On a GPU: two radios, "Best chart (4 guitar takes, about 4 to 14 minutes)" and "Quick
  chart (1 take, about 2 to 7 minutes)" for a 4:01 song; elsewhere a line ("This PC charts the guitar on the CPU, so
  it makes 1 guitar take: about 6 to 11 minutes for this song."). The radios only fill the takes box (Best empty,
  Quick 1) and a typed number checks the matching radio or neither, so the options sent are exactly today's. The
  takes box, device and preview are in a folded "More options"; Lyrics and Pictures each in a `<details>` of its own.
- **Item 5, the time left.** `estimate.remaining(est, events)`: at the second take's event, the first take's time is
  that event's `at` less the first's; the takes left (count - index + 1) at that time less its own part
  (`GUITAR_ONCE` x d, its high rate for the low end), nothing off when the first take that ran was not take 1 (the
  cache answered it); plus the stages after the guitar in the plan: `ASSEMBLE` (new: 0.5-5 s + 0.025-0.08 s a second,
  from the test song's 16 and 17.2 s, Take Me Out's 19.3 s, CI's clip about 1 s) and `PREVIEW`. After the guitar's
  stage_end: the later stages alone. None after a CPU retry (`device` on a take event). Worked out once, from that
  event's `at`; the page counts it down on the server's clock and shows "Nearly done, or taking longer than estimated."
  past the high end; the first estimate is struck through. `Job.snapshot()` carries `remaining` (a bug in it gives
  None); the page fetches the snapshot at a take event while it has none, and at the guitar's stage_end. I tried
  refining at each later take from the latest gap: on the test song take 2 (224 s) is slower than 3 and 4 (164, 187),
  so the refined range at take 3 put the actual below its low end; the order's first-take model held, so it stays.
  The 9:05 song's single take times are not in the repository (only its 2173 s total), so the test splits the total
  with the five ordinary songs' mean first-take part (0.13 s a second) and says so.
- **Item 6.** `gone(true)`: "songcharter is not answering", tab "Not answering"; `gone(false)` unchanged.
- **Item 7.** DESIGN 4.5 (a bullet for the pass; the gone sentence; the M7-10 "left for later" line points here and to
  M8-10) and the guide's section 5 (Best/Quick and the time left, More options, Lyrics and Pictures folded, Open
  folder, the guess, the lightbox and Listen here).

## Checks

- **UI tests** (`python -B -m pytest tests/test_ui_estimate.py tests/test_ui_jobs.py tests/test_ui_server.py`): 177
  passed. New: `test_the_time_left_from_the_test_songs_first_take`, `..._905_songs_first_take`,
  `..._after_the_guitar_and_when_it_cannot_say`, `test_the_snapshot_carries_the_time_left_...`,
  `test_open_folder_built_opens_the_results_own_folder_only`, `test_a_flag_links_to_the_page_that_shows_its_start`,
  `test_the_songs_folders_guess_is_always_given`, `test_best_or_quick_offered_on_the_gpu_...` (5 cases),
  `test_the_ui_pass_page` (node, stand-in DOM); updated: the upload's keys, the results' preview, the gone test's
  not-answering case, the harnesses' stand-ins.
- **Breaks:** 48 breaks, each applied alone and the covering test run, all caught: OPEN without "built"; built
  without its folder check; a path from the body read; no windows_path; flag_page ceil, no clamp, an edge moved to the
  page before; flag_at taking any part; PAGE_S 30; the guess describe's only; choices ignoring the guitar device;
  Quick 2 takes; the page sending 2 for Quick, 4 for Best; a typed number keeping a choice; the choice shown on the CPU;
  no minutes on Best; no countdown; the first estimate not struck; a take not asking; the rounding (round for ceil);
  the path back in the sentence; ".failed" kept; no hover text; Open folder sending "song"; a flag linked to the page
  before; a ctrl-click taken; the arrows off; Listen at the flag (not a second before); Listen not on Expert; no seek
  at loadedmetadata; the guess not said; the gone heading, tab, and the stopped case saying not answering; remaining's
  ends swapped, nothing taken off take 1, taken off a cached first, one take short, no build, the preview always, a
  retry kept, the latest pair, counted from take 1, no guitar end, ASSEMBLE wider; the snapshot without remaining, a
  bug escaping. Four were missed at first and their tests tightened (a body path, the rounding grid against
  estimate.round_minutes, Open folder through its button, a level chosen before Listen here).
  **A trap worth noting:** a break of the same byte size as the original, restored within the same second, leaves a
  stale `.pyc` that Python accepts (mtime and size match): it showed as Quick's 2 takes on the first screens. The
  caches were cleared and every break rerun with `python -B` / `PYTHONDONTWRITEBYTECODE=1`: 48 of 48 caught.
- **Full suite** (`SONGCHARTER_HEAVY_MIN_FREE_GB=1 SONGCHARTER_SCAN_CHART=... tools/heavy.sh python -m pytest -q
  -p no:cacheprovider --basetemp=<shm>/m804/suite`, on 3870449's tree): `1305 passed, 6 skipped in 797.37s (0:13:17)`,
  exit 0.
- **Screens** (Chromium via Playwright, deviceScaleFactor 1, into <shm>/m804/, looked at, then deleted): a
  stand-in server (the real App and Jobs; a stand-in chart program sending a real chart's events, paced by files, with
  the job's clock 20x fast so a 13-s first take reads as 264 s), the golden Take Me Out folder's notes.chart under a
  made-up name (song.ogg a link, not a copy, for Listen), its preview rendered by preview.py, made-up flags, GPU and
  CPU doctor summaries, a silent 4:01 WAV dropped through the file chooser. Seen: the options at 1280 light (1536 px
  tall with the folds closed), 700 dark with More options open, 1280 dark on the CPU summary (no choice, the line);
  the progress at take 1 (the estimate alone) and at take 2 ("About 10 to 14 more minutes, from how long the first
  guitar take took." under the struck estimate) at 1280 light and 700 dark; the Done screen at 1280 light and dark and
  700 light ("Ready" y=17, Open folder y=107, "Play it" from y=154, the guess sentence and field); a flag's page in
  the lightbox at 1280 and 700 (Page 1 for 0:59.9; ArrowRight to page 2; Escape closed it); Listen here (Guitar,
  Expert, the player at 1:00 of 4:04, started at 0:58.9). No console errors in any context. The scripts
  (standin_server.py, standin_chart.py, shots.cjs) stay in `<scratchpad>/m8/` for the reviewer's look; the shots, the
  stand-in home and its pictures were deleted. A stand-in artifact: the
  running guitar row's clock reads 0 s, as the page's clock runs at real speed against the scaled event times.
- **Privacy:** the stress check on the changed files: 0 found; the 20-song check: the same per-file counts as main's
  versions (the files' existing hits, none new) once the arrow's numeric entity was replaced; both on the added lines alone:
  nothing; the 20-song check on the commit messages: nothing. The diff and messages scanned for model names, home
  paths, emails and machine names: none but the trailers. Hits were counted, never printed.
- **CI:** run 42547876475 (workflow_dispatch of ci.yml on m8-04-ui-pass), head 4845a78: success; linux ("Suite":
  `1307 passed, 4 skipped in 590.02s`; the CI tools 86 passed; hooks 6 passed) and windows both success. An earlier
  dispatch on d227637 (42547835778) was cancelled for the merge. No CI hook added (the order needs none).
  <repo>/actions/runs/42547876475
- **Golden charts:** not run (nothing charts: no file on the charting path changed).

## Not done, uncertain

- Open folder in real WSL (explorer.exe on the `\\wsl.localhost` path) was not run: the tests and screens stand in
  `wsl.open_url`.
- The time left uses one first take; a song whose first take is fast and later ones slow (Kimochi Warui) can pass
  its high end, as the original estimate's docstring already says.
- PROGRESS.json left to the orchestrator (not among the order's files).

## Review fixes (4ccf649)

The review (head 4845a78) found no majors and five minors, all fixed in one commit, 4ccf649:
- **F1, the time left once a multi-take guitar ends.** The code was right, but nothing tested it. New tests: in
  estimate, a 4-take chart with the guitar's stage_end gives the later stages alone, from that event; on the page, the
  guitar's stage_end asks again and the line becomes "About 1 to 2 more minutes: the guitar is done.".
- **F2, the results route's page count.** New test `test_the_results_link_each_flag_to_a_page_there_is`: three pages,
  flags at 0:59.9, 1:00.0, 1:59.9, 2:00.0 and 3:30.0 give pages 1, 2, 2, 3 and 3 (the last one clamped), and each
  linked page is served. `boxLink` and `flagItem` are now guarded: a flag whose page the preview lacks shows as plain
  text, never a TypeError, so the install box always renders (the page test covers this).
- **F3, a cached take 1.** The events do not say whether autochart's cache held take 1's separation, and
  `pipeline.py` is M8-05's file. So the high end now subtracts nothing from the first take; the low end subtracts the
  high rate as before. The reason is in the docstring and in DESIGN 4.5.
  - The 9:05 song with take 1 at a later take's time: 1181.8-1657.5 s, against about 1636 s left (before the fix:
    1542.9 at the high end).
  - The test song with take 1 at 210.4 s: 333.8-694.8 s, against 602 s.
  - With take 1 not cached, the high ends widen: the test song gives 495-856 s (8 to 15 minutes); the 9:05 song gives
    1394-1870 s (23 to 35 minutes).
- **F4, the refusal's path.** The refusal now names the song: "<name>'s folder is not there any more: it was moved
  or deleted", without ".failed". `openFolder` clears its message when a new open is asked. Tests cover the exact
  error with no path in it, and a refusal on the page followed by an open that clears it.
- **F5, the lightbox's title.** It now reads "Overview" or "Page N of M", where M counts the pages only.

Checks after the fixes:
- **UI tests:** 179 passed.
- **The reviewer's surviving breaks:** all three now fail a test (`len(takes) < 2` after the guitar; no
  askRemaining at the guitar's end; `len(pages) + 1`).
- **Breaks of the fixes:** each fails a test: the high end subtracting again, the path back in the refusal, the
  refusal left in place, a link past the end, the old title. The two earlier breaks whose lines the fixes rewrote (no
  folder check; the ends swapped) were redone and fail too. The other 46 earlier breaks still fail, run without
  bytecode.
- **Privacy:** the stress check on the changed files: 0 found. The 20-song check: the same per-file counts as main's
  versions, and nothing on the added lines or the commit message. No model names, home paths or emails in the diff.
- **CI:** run 42552379332 on 4ccf649: success, linux and windows. The suite: `1309 passed, 4 skipped in 587.23s`.
  Its first attempt failed only in `linux.d/50-e2e.sh prepare` (exit 100), because the runner's apt could not reach
  archive.ubuntu.com (connection timed out). The suite passed on that attempt too. Rerunning the failed job passed.
  <repo>/actions/runs/42552379332
