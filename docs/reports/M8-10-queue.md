# M8-10 builder's report: a queue of songs on the page

*Merged 2026-11-09 at abde048 (branch head d47e136; CI run 42565927158 green on its fifth attempt: attempts 1-4 each
failed one install-building hook on an HTTP 504 from GitHub's release downloads while `packaging/release/build.sh`
fetched uv's checksum, the suite passing every time, 1327 passed; deferred). The review: two `sc-reviewer`s on head
c4173ab, one lens each. Lens S (the server): S1 major, a Cancel posted after a song's end cancelled the next song (the
cancel named no job); S2 a waiting song's pasted lyrics lost after a restart without a word; S3 two breaks the tests
let through (Queue.shutdown's check, queued_uploads without "charting"). Lens P (the page): F1 major, songs refused
over the 20-waiting cap when several were added vanished without a word; F2 a song's end or start taking away the
options form being filled; F3 three breaks the tests let through; F4 a killed song's reason ending in a colon. An
`sc-skeptic` on each major: both held, rated medium (F1: reached by 22 or more songs or a second batch on a long list)
and low to medium (S1: a confirm dialog open across a song's end). All seven fixed in d47e136 (below).*

Branch `m8-10-queue` (worktree `<wt>/m8-10`), from main ab2e393. Built the note's parts A, B, C and E as the
orchestrator's decision accepted them; not D ("Your charts"), the cache rule for a queue's finished songs, lyrics held
in memory, "Chart next" or the Windows keep-awake call. Docs: DESIGN 4.5 and the guide only (PROGRESS left to the
orchestrator, as the brief allows only the order's files).

## Commits

- 194450d M8-10: the server's queue (queue.json, the paused restart, Pause, Remove, the two-failures and disk pauses)
  and the routes by job id (parts A and B, with their tests)
- f50dffb M8-10: the page's queue (a drop of several songs and its shared form, the list with Install and Look, the
  title, wake lock, notice and the whole queue's estimate) (part C, with its node test)
- c913bc9 M8-10: DESIGN 4.5's queue, the guide's evening of songs, and the list read again until a song's end is
  recorded (part E, and a fix the screens found)
- c4173ab M8-10 tests: a song that cannot start counts toward the pause, a crash's queue.json, the run time off the
  estimate, the notice held while songs wait (tests made stricter after the first breaks)

## What was built

**A. The server's queue** (`songcharter/ui/jobs.py`, `Queue`; jobs.py's one child process group unchanged).
- `POST /api/jobs` now adds the song to the queue (`Queue.add`): it starts at once when nothing charts and none
  waits (202 `{"job", "entry", "state": "charting"}`), else it waits (202, `"job": null`, `"state": "waiting"`). Its
  options are checked when it is added (`parse_options`, a bad one 400 at once). Lyrics only for a song that starts
  at once: else 400 with `jobs.LYRICS_WAIT`. At most 20 waiting (`QUEUE_MAX`, 409).
- `Jobs.on_end` (new; called on a thread of its own after a job's end state is set, from `_finish` and from
  `cancel`) tells the queue, which records the end and starts the next waiting song. `Queue._settle` records the end
  idempotently from any request too, so a request right after a result sees the true state.
- `<home>/state/queue.json`: written whole through `queue.json.part` and renamed; entries keep the upload's id, name
  and length, the page's options with the pictures as upload ids (re-resolved at start, `App.prepare`), the
  estimate, the state (waiting, charting, ready, check_failed, not_finished, cancelled), the job id and the closing
  event; never lyrics. The last 50 finished songs are kept.
- **Restart:** `Queue.shutdown` (the server's stop path, replacing `jobs.shutdown`) kills the tree and puts the song
  back to waiting at the top (unless it had finished meanwhile). A crash leaving "charting" in queue.json is read
  back as waiting too. With songs waiting, the queue loads paused (`"restart"`, `restarted` = how many) until Carry
  on or Clear the list.
- **Cancel** ends the charting song only (`cancelled`); the next starts. **Pause after this song** (`"you"`),
  **Carry on**, **Remove** (a waiting or finished song; 409 for the charting one), **Clear the list** (every song but
  the charting one).
- **Two in a row that do not finish** (exit 2/3, killed, or a song that cannot start, e.g. its upload gone) pause the
  queue (`"failures"`); a failed check is a finished chart and resets the count, as do ready and cancelled.
- **The disk:** `App.disk_low` (doctor summary with `device.refresh_disk`) before each song the queue starts itself
  (not one added that starts at once, which stays as before: shown, never blocking); under `device.MIN_FREE` the
  queue pauses (`"disk"`, with why: "C: is nearly full (under 6 GB free), so the queue is paused: free some space,
  then Carry on", or "WSL's disk ..." for the home's).
- **Uploads kept:** `prune_uploads(..., keep=jobs.queued_uploads(home))` skips the waiting songs' uploads and their
  pictures.
- **API:** `GET /api/queue` (also `/api/status`'s `queue`), `POST /api/queue/pause|carry-on|clear|remove`, all
  behind the existing guards (they go through `_handle`). The snapshot's `left` is the whole queue's time left.

**B. Routes by job id** (`server.py`, `JOB_PATH`): `/api/jobs/<yyyyMMdd-HHmmss[-n]>/...` beside `current` for the
snapshot, results, preview, art, Listen (POST and GET), install and the zip; the job is the current one or the
queue's record of a finished one (`jobs.Kept`, from queue.json after a restart too). Events and cancel stay the
current job's only. `results(job, ref)` names the job in its URLs as the request did. `app.listened` is keyed by job
id. `POST /api/open {"what": "built", "job"}` opens that job's folder (an id that is not one falls back to current).

**C. The page** (`app.js`, `index.html`, `app.css`):
- The drop zone and the file chooser take several files (`multiple`); each is uploaded in turn ("Uploading X (1 of
  2)…"). One file: the form as before. Several: one shared form ("2 songs, charted one after the other with these
  options:" and their names; Best or Quick and More options; Song fields, Lyrics and Pictures hidden; "Chart them");
  each POSTed in turn. A refused upload among several is said on the options screen.
- Lyrics for a song that would wait: the box is disabled with "Lyrics only for a song that starts at once: ..." above
  it; the server refuses them too.
- The list ("Your songs", a section after the progress screen, before the Done screen; so also on the drop screen):
  each song's name (its chart's folder name once charted), its state ("Waiting (usually about 2 to 10 minutes)",
  "Charting now", "Ready", "The check failed (kept for a look)", "Did not finish: <first line>", "Cancelled"),
  Install and Look when finished, Remove while it waits; the pause banner with Carry on (and Clear the list after a
  restart); "Clear the list" under it when nothing charts; "All N songs: about 1 h 10 min to 3 h 20 min more"; the
  keep-awake line while a queue runs. The progress screen has "Pause after this song" (when songs wait) and an "Add
  songs" drop strip (which goes to the drop screen, with "Back to the chart").
- A song's end with more to come (`moreToCome`: the last list read has songs waiting and no pause): the page waits
  for the server's next job (`between`: the list read each second, up to 30 s) and follows it, the wake lock kept;
  else the Done screen as before, and the list read again until the ended song is no longer "charting"
  (`settleQueue`).
- The tab's title: "1 of 2: Guitar: take 1 of 4 - songcharter" (the run's songs, `run` from the server); at the end
  "2 ready - songcharter", "1 ready, 1 did not finish - songcharter" (a single song keeps "Ready").
- Look: a finished song's own Done screen by its job id (`GET /api/jobs/<id>`'s closing event, then its results);
  its Install, zip, Listen and Open folder use the id (`state.shown`, `jobPath`); the Done screen's button reads
  "Back to the chart" while a song charts, "Add a song" otherwise ("Chart another song" became "Add a song").
- The update notice is held while songs wait, as while one charts.
- The page reads the list every 5 s, and follows a song the server started while it followed none.

**E.** DESIGN 4.5: a "The queue" item (the design, the screens). The guide (5. Chart a song): "Several songs for an
evening". Server and jobs docstrings updated.

## Checks

- **The UI tests** (worktree, `PYTHONDONTWRITEBYTECODE=1`):
  `python -m pytest -q -p no:cacheprovider tests/test_ui_server.py tests/test_ui_jobs.py tests/test_ui_estimate.py`
  -> `190 passed in 38.59s` (at c913bc9); after c4173ab the changed and new tests: `16 passed` in the worktree and
  `15 passed` on a fresh `git archive` copy.
- **New tests:** test_ui_jobs.py: two charts never at once (a stand-in child records its start and end; four songs,
  runs in order, never overlapping), two failures pause, pause/remove/disk, lyrics and the limit, restart, a crash's
  queue.json, a broken queue.json, the whole queue's time left, the uploads kept from pruning. test_ui_server.py: the
  rewritten one-at-a-time test (a second song waits, lyrics refused for it, cancel starts it), routes by job id
  after the next has started (results, preview, install, zip, Listen, Open, and after a restart), the guards on
  every new endpoint (Host, Origin, X-Songcharter) and `disk_low`, and the page in node (QUEUE_PAGE). Two existing
  tests changed: `test_one_job_at_a_time_then_cancel` (409 for a second song became "it waits") and the UI pass
  page's Listen and Open folder paths (now by the results' job id, "j1", not "current").
- **Breaks** (`<scratchpad>/m8/m810-screens/breaks-m810.py`, run on a `git archive` copy in /dev/shm with
  `PYTHONDONTWRITEBYTECODE=1`, `-B`, no `__pycache__` before): 50 breaks, **50 caught, 0 missed**: the queue (next
  started while one runs with Jobs' guard off too; no on_end; starts at once while one charts; a failed check counted
  as a failure; no failures pause; a song that cannot start not counted; a cancel not starting the next; no restart
  pause; a crash leaving charting; shutdown keeping charting; lyrics in a waiting song; no limit; lyrics in
  queue.json; disk not measured; pause ignored; remove of the charting one; the run time not taken off the estimate;
  a song without an estimate counted as 0; finished uploads kept; prune ignoring keep), the server (routes by id
  reading the current job; install by id installing the current; results' URLs saying current; a render served for
  any job; Open built ignoring the job, or taking any ref; the queue's and a job's POSTs skipping the header guard;
  the Host guard off for the queue; disk_low never; status without the queue; lyrics passed to a waiting song), and
  the page (only the first file uploaded or sent; Song fields or lyrics for several; no place in the title; no
  waiting for the next; the lock let go between songs; Look and the list's Install by current; no end count; the
  notice not held while songs wait; the restart words; the lyrics box open while busy; hours as minutes; Carry on
  posting nothing; back to the drop screen while running; Remove on the charting song; no whole estimate). Three
  tests were made stricter after a first look showed a break would pass (c4173ab).
- **Not covered by a test:** `settleQueue` (the list read again after the end; a fix from the screens), the 5-s
  poll's follow of a song started elsewhere, the Add songs strip's drag and drop (its file chooser path is the same
  `uploadFiles`).
- **The full suite** (`tools/heavy.sh`, `SONGCHARTER_HEAVY_MIN_FREE_GB=1`, `--basetemp=<shm>/m810/suite`, at
  c913bc9's code; c4173ab changed tests only, run as above): `1318 passed, 6 skipped in 856.53s (0:14:16)`, exit 0 (run beside the breaks, so slower than usual).
- **The screens** (Chromium via Playwright, deviceScaleFactor 1, 1280x860 and 700 px, light and dark; scripts in
  `<scratchpad>/m8/m810-screens/`: the real App, Jobs and Queue on port 8799 with a stand-in chart program paced by a
  file, a made-up chart and pictures, made-up song names and a made-up GPU summary): the shared form for two songs
  ("Best charts (4 guitar takes)", "Chart them"); the first charting as "1 of 2: Guitar: take 1 of 4" with the list
  (the second waiting, Remove) and "All 2 songs: about 6 min to 24 min more" at 1280 light and 700 dark; after the
  first's end the page followed the second ("2 of 2"), the first Ready with Install and Look; Look showed the
  first's Done screen (Open folder, the Songs folder form, the zip, the preview and flags, Listen, "Back to the
  chart") at 1280 light and 700 dark while the second charted; at the end "2 ready - songcharter" and the second's
  Done screen at 1280 dark and 700 light; a third song, the server stopped mid-chart and started again: "1 song was
  waiting when songcharter closed. Carry on charts it; Clear the list lets it go." with Carry on and Clear the list
  at 1280 light and 700 dark, and Carry on charted it. Console: no errors but one `ERR_CONNECTION_RESET` from the
  page open while the server was killed. Looked at (the shared form, the progress with the list, Look at 700 dark,
  the restart), then deleted.
  - **Found by the screens:** on this machine (1.5 GB free on /) the real disk check paused the list before the
    second song ("WSL's disk is nearly full (under 6 GB free) ..."): the pause works; the stand-in was then given
    its made-up summary's disk. And the list kept "Charting now" for the last song after its Done screen, until the
    next 5-s read: the end's list read came before the server recorded the end; fixed with `settleQueue` (c913bc9).
- **CI:** <repo>/actions/runs/42560795008 (workflow_dispatch on m8-10-queue), **success** on head c4173abcdf4aea5c53d111899676d7a1086655f7: windows ok; linux's Suite `1321 passed, 4 skipped in 603.00s`; the 40-ui hook ran (`==== hook linux.d/40-ui.sh`: `137 passed in 37.48s` for test_proc, test_ui_server and test_ui_jobs, then its real-server checks: Host 403, no header 403, Origin 403, a .txt upload 415, ...).
- **Privacy:** both checks on every changed file before each push. `EVAL_DATA=<dev>/eval`: 0 found. `EVAL_DATA=
  <dev>/eval-set20`: per-file counts equal to main's except jobs.py (3 against 2), test_ui_jobs.py (2 against 1) and
  test_ui_server.py (2 against 1); every one of those hits is a line with the word "tool" (the known false
  positive: `"kind": "tool"`). The branch's diff and commit messages scanned for lyrics, model names and personal
  details: none.

## Interpretations to check

1. **POST /api/jobs became "add to the queue"** rather than a new endpoint, so one path starts every chart; a second
   song while one charts gets 202 "waiting", not 409. CI's 40-ui hook posts one job and is unaffected.
2. **The disk check** runs only before a song the queue starts itself (after an end, or Carry on), not for a song
   that starts at once from a click, which keeps today's rule ("shown, never blocking Chart it").
3. **Cancelled resets the two-failures count**, as ready and check failed do ("in a row" of finished songs).
4. **Clear the list** removes finished songs too (their charts stay in the library); it is offered after a restart
   in the banner, and under the list whenever nothing charts. Finished entries are capped at 50.
5. **"All N songs"** counts the evening's songs (the server's `run`: songs added since the list was last idle), and
   the time is what is left; shown only with two or more.
6. **The title's "k of n"** uses the same run; a single song keeps today's titles.
7. **Look's Done screen** shows the song's own title and words ("Ready", its name), not a separate heading naming
   the song beyond the text.
8. **A pause stays only while songs wait:** with nothing waiting, the queue reports no pause, and a new song starts
   at once.
9. **Several songs' Best and Quick** show no minutes in the form (each song's estimate is in the list).

## Not done

- D ("Your charts"), and the rest the decision left for later.
- PROGRESS.json (the orchestrator's).

## Housekeeping

<shm>/m810 (the suite's and the breaks' temp, the stand-in home, the shots) deleted; `df -h /`: 1.5G free (97 %). The
scripts stay in `<scratchpad>/m8/m810-screens/` for the reviewer.

## Review fixes (commit d47e136)

The two reviews (lens S, lens P) and the skeptics' calls, all seven fixed:
1. **P-F1, refused songs vanished when several were added:** chartIt keeps each refusal (name, status, error); when
   some were added, they are said above the list where the page lands (`#queue-note`, `refusedNote`): "1 song was not
   added (1 is waiting already): <name>. Drop it again once some are charted.", cleared on the next drop. When none
   was added, the form stays with why, as before. The server's words for a list of one: "1 song is waiting already".
2. **S-S1, a late Cancel cancelled the next song:** the page posts `/api/jobs/<the job it shows>/cancel`; the route
   passes the id to `Jobs.cancel(job_id)`, which checks it under its lock and raises NotRunning unless that job is the
   running one (409 "that chart has ended"). `current` keeps today's meaning (CI's 40-ui hook uses it).
3. **P-F2, a song's end while the Add songs form is open:** `adding()` (an upload's form open, not yet sent);
   `attach(quiet)` follows the next song without taking the form away (between and the 5-s follow pass `adding()`);
   `showDone` leaves the Done screen hidden under an open form (the song is in the list with Look); `lockLyrics()` runs
   on every list update and at a song's end, so the box opens once nothing charts; `look()` switches screens (the
   progress screen while a song charts, else the Done screen alone); leaving the form (Another song, Look) clears it.
4. **P-F3 and S-S3, tests:** the page following a song started elsewhere, a refused upload among several said on the
   shared form, Clear the list hidden while a song charts (node test); `Queue.shutdown` with a song whose result was
   out (a "linger" stand-in: recorded ready, not charted twice); `queued_uploads` keeping a crash's charting song.
5. **P-F4, plain words:** an error the job writes itself carries `plain` (`PLAIN_MEMORY` "Stopped: the PC ran short
   of memory, perhaps (Look shows the details)", `PLAIN_STOPPED`, `PLAIN_SILENT` "It stopped without saying why (Look
   shows the details)"); the list shows it, the Done screen keeps the whole message; a first line's trailing colon
   is dropped.
6. **S-S2, lyrics lost unsaid after a restart:** an entry keeps `"lyrics": true` when it had some (never the text);
   a song put back to waiting (`Queue._back`: the window closing, or a crash) gets `lyrics_lost`, and its row says
   "Its pasted lyrics were not kept when songcharter closed: add it again with its lyrics, or chart it without."

**Checks**
- UI tests (`tests/test_ui_server.py tests/test_ui_jobs.py`, `PYTHONDONTWRITEBYTECODE=1`): `138 passed in 44.43s`.
- New tests: test_ui_jobs.py `test_a_cancel_naming_a_song_that_has_ended_never_reaches_the_next`,
  `..._result_was_out_when_the_window_closed_is_not_charted_twice`, `test_a_killed_or_silent_song_says_why_in_plain_
  words`, `test_a_restart_says_a_songs_pasted_lyrics_were_not_kept`, `test_the_full_lists_words`, and the pruning
  test's charting entry; test_ui_server.py `test_a_cancel_by_id_after_its_song_ended_is_refused_and_the_list_full_
  says_so` (QUEUE_MAX 1, three songs) and the page test's new part (QUEUE_MAX 1's refusal note, cancel by id, a
  refused upload among several, the form kept across the next start and the end with the lyrics' lock, Look from
  the form, a song started elsewhere followed, the lost lyrics' line, Clear the list while charting).
- Breaks (`<scratchpad>/m8/m810-screens/breaks2-m810.py`, fresh `git archive` copy, `-B`, no `__pycache__`; baseline
  8 passed): **18 of 18 caught**, the seven findings' own breaks included (the reviewers' five missed breaks among
  them: no follow of a song started elsewhere, a refused upload among several unsaid, Clear the list while charting,
  Queue.shutdown's check off, queued_uploads without charting).
- The full suite was not run again locally: the fix changed jobs.py and server.py in a few lines (the cancel's id,
  the plain words, the lyrics' flag); CI runs it.
- Screens (Chromium, the stand-in server with `QUEUE_MAX` 1, made-up songs): three songs dropped at 1280 light: the
  first charting, the second waiting, and above the list "1 song was not added (1 is waiting already): <the third>.
  Drop it again once some are charted." on the progress screen; at 700 dark, Add songs opened the form (Lyrics
  locked), a title typed, then the first song ended and the second started and ended: the form stayed with "Half
  Filled", only the options screen and the list shown, the Lyrics box open again; Look from it showed the list and
  the Done screen alone. Console: only the refused POST's 409. A stand-in artifact: the made-up WAVs were the same
  silence, so they shared one upload id and the list named them alike. Looked at, then deleted.
- Privacy: both checks on every changed file; per-file counts unchanged from the first push (all "tool", DESIGN.md
  equal to main's); the fix's diff scanned: nothing.
- CI: <repo>/actions/runs/42565927158, **success** on head d47e13694a01f075d95eee83f39198d631a0c53d at its 5th attempt (the failed job re-run): every hook ok (10-lanes, 20-device, 30-install, 40-ui, 50-e2e, 60-results, 70-release, 75-update; windows ok), the Suite `1327 passed, 4 skipped` on every attempt. Attempts 1-4 each failed one install-building hook (30-install, 50-e2e, 75-update, 30-install) on `curl: (22) ... 504`: packaging/release/build.sh's fetch of uv's published sha256 from GitHub's release downloads (3 retries in a few seconds), an outside outage; the same URL answered 200 from here meanwhile. Nothing of the order's touches that path; build.sh's retries are outside the order's files (a note for the orchestrator: CI is fragile against a short GitHub 504).
