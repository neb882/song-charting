# M8-10: a queue of songs and a list of his charts

**Conditional on the design note** (below, "Design"), written by M8-04's builder as that order's first commit and
accepted, narrowed or refused by the orchestrator (with a reviewer's read of it). Refused, the order is closed and
item 9 goes back to M5-99 with the note's reason. **Branch:** `m8-10-queue`, from `main` after M8-04's merge (wave 2
or later; the GPU line's builds take a free slot first). **Agent:** `sc-builder`, then `sc-reviewer` (who also looks at
the screens). May push its branch to run CI. **Files:** `songcharter/ui/jobs.py`, `songcharter/ui/server.py`,
`songcharter/ui/static/{app.js,index.html,app.css}`, `tests/test_ui_*.py`, `docs/guide/windows-wsl.md`, `docs/DESIGN.md`
4.5. **Not:** anything that charts (`pipeline.py`, `cli.py`'s chart command: the child is unchanged), `clonehero.py`
beyond calling it. **Time budget:** 2 days. **Rough cost:** 5-7 % of a week's meter.

**Environment:** eval/README.md's step 9, and `SONGCHARTER_HEAVY_MIN_FREE_GB=1` on every heavy job (the suite, the
golden, stress and 20-song runs, builds): about 1.7 GB is free on `/`, `tools/heavy.sh` refuses under 5 GB without
it, and `python -m eval.golden run` takes the lock but not the disk check.

*Written by the M8 planner on 2026-11-08 from docs/reports/m7-ui-review.md item 9 ("One song at a time, nothing
remembered": 8-16 hours, a design note first) and jobs.py's module docstring.*

## Why

A second drop while a chart runs gets "A chart is running already", and "Chart another song" forgets the last one: no
list, no re-install. An evening's queue of songs and a "Your charts" list (name, date, Install, Open) fit how the friend
uses the page. jobs.py runs one child process group at a time by design (memory: a chart can take 10 GiB or more,
M8-00 section 6), and that stays: a queue is the server's waiting list, never two charts at once.

## Design (written by M8-04's builder; the questions it must answer)

1. **What waits:** an upload and its options (the pasted lyrics too: today a memory file handed to the child, never on
   disk; a queued song's lyrics must stay off disk, or the queue refuses lyrics, said on the page).
2. **Where it lives:** in the server's memory only (lost when the black window closes: said on the page), or on disk
   under `<home>/state/` (survives a restart; then what a restart does with the song that was running).
3. **Cancel and failure:** cancel the running chart and go on with the next, or stop the queue; a failed chart (exit 2
   or 3) and the next; removing and reordering waiting songs.
4. **The page:** where the queue shows (the progress screen's side, or a list under it), the Done screen of each
   finished song (its own result, install and listen, reachable after the next has started), the tab's title and the
   wake lock across songs, the update notice (held until the queue is empty), the estimate for the whole queue.
5. **"Your charts":** the library's folders (`<home>/library/<16 hex>/<name>/` with their `report.json`): name, date,
   the gate's verdict, Install (`clonehero.install`, with its 409 for an existing song), Open; nothing deleted from the
   page unless the note argues for it; the work cache's pruning (5 GB) unaffected, as the library is not the cache.
6. **The disk:** uploads kept until charted (the cache's budget, a cap on waiting songs), and what install.sh's update
   check (which refuses while a server answers) means for a long queue.
7. **The cost:** hours per part, so the orchestrator can narrow the order (for example the list alone, then the queue).

### The note (M8-04's builder, 2026-11-09)

The owner's ask: "think we can add the ability to queue up charts? so that, in theory, someone can load up 10 mp3
files and when they get home after a few hours, the charts will be done?" He left the page to the orchestrator, whose
defaults this note weighs; where it departs from them it says **Changed** and why. Ten 4-minute songs take about 40
to 140 minutes with the GPU's 4 takes and 60 to 110 on the CPU (the page's own ranges, DESIGN 4.5): "a few hours"
holds.

**The shape.** The server runs the queue, not the page: when a chart ends (jobs.py's `_finish`, or `cancel`), the
server starts the next waiting song itself, so a closed tab, a hidden one or a dropped connection never stops the
evening. Still one child process group at a time: a chart's tree peaked at 10.1 GB on the test song (allin1's runner
7.8 GB of it, DESIGN's M3 table; M8-00 section 6). The page shows the list and edits it.

1. **What waits.** An entry: the upload's id, its options checked when it is added (`parse_options`, so a bad one is
   said at once), its estimate, its state (waiting, charting, ready, check failed, did not finish, cancelled). The drop
   zone and the file chooser take several files (`multiple`), each uploaded in turn as today. **Changed: one options
   form for a drop of several songs**, not one per song: ten forms for ten songs is the chore the queue is meant to
   remove. For several, the form lists the songs' names and offers Best or Quick (M8-04 item 4) and More options,
   shared; the Song fields, Lyrics and Pictures are a song's own, so only a drop of one offers them (each song of
   several takes its own tags, as a chart with those fields blank does today). **Lyrics are refused in a waiting
   song**, said beside the box ("Lyrics only for a song that starts at once: songcharter keeps pasted lyrics only
   while it uses them"); a song that starts at once takes them as today, through the memory file. Why not hold them
   in memory while the song waits: for hours, beside a 10 GB chart, a memory file's pages are likely to reach WSL's
   swap file on C: [inference: memfd pages are swappable], which today's few seconds before the child reads it hardly
   allow; and a restart would lose them, a further state for the page. Holding them in memory is the alternative
   (+1 h), if the owner wants lyrics in a queue.
2. **Where it lives: on disk**, `<home>/state/queue.json` (written whole to a temporary file and renamed), with each
   picture's upload id and no lyrics. **Changed: after a restart the queue waits for a click** rather than carrying
   on. When the window closes (its X, Ctrl+C, a Windows restart for an update overnight), the server stops and the
   chart's tree is killed as today; the song that was charting goes back to the top as waiting, its finished stages
   and takes kept by the work cache (each take is cached on its own, `engines/autochart.py`), so it starts again near
   where it stopped. When songcharter starts again the queue is paused, and the page says "3 songs were waiting when
   songcharter closed" with **Carry on** and **Clear the list**. Why not start by itself: closing the window is the
   one way to stop a queue that frees the memory at once, and he may close it to play Clone Hero; opening songcharter
   later to install one song must not start a 10 GB chart under his game. A restart overnight leaves songcharter
   closed in any case, so the evening loses nothing: he clicks Carry on. The uploads queue.json names are kept past the
   7 days' pruning (`prune_uploads` skips them) until their song is charted or removed.
3. **Cancel and failure.** Cancel stops the charting song only (its caches kept, as today), marks it cancelled, and
   the next starts: one bad song must not cost the evening. **Pause after this song** (it finishes, none starts) and
   Carry on; a waiting song has **Remove**. Reordering is left out of the first build ("Chart next", a move to the
   top, +0.5 h if asked). A song that does not finish (exit 2 or 3, or killed: its error as today) is marked with its
   first line, the rest under its Look, and the next starts. **Added: two in a row that do not finish pause the
   queue** ("Two songs in a row did not finish, so the queue is paused: see why"): exit 2 is often the machine, not
   the song (a full disk, a missing model, out of memory), and would fail every song after it. A chart whose gate
   failed (exit 1) is finished, "check failed", not a failure of the queue.
4. **The page.**
   - **The list** sits under the progress screen's stages (at 700 px a side column has no room): each song with its
     state and, when finished, **Install** and **Look** (its own Done screen: the result, the preview and flags,
     Listen, the zip). An "Add songs" drop strip on the progress screen; "Chart another song" becomes "Add a song".
   - **A finished song's Done screen after the next has started:** the routes on "the chart" take a job id
     (`/api/jobs/<id>/results`, `.../preview/`, `.../art/`, `.../listen`, `.../install`, `.../export/zip`; `current`
     stays the name of the latest), behind the same guards. The server keeps the finished jobs' result events (in
     queue.json too, so Install and Look survive a restart). One install and one render at a time as today, both
     allowed while the next song charts (a render is a few seconds of the CPU).
   - **The tab's title:** "2 of 6: Guitar: take 3 of 4 - songcharter"; at the end "6 ready - songcharter" ("5 ready,
     1 did not finish").
   - **The wake lock** is held from the first song's start to the queue's end (not let go between songs) and asked
     for again when the tab is back in view, as today. It holds only while the tab is in view (the browser lets it go
     when the page is hidden: app.js's wake lock note), so while a queue runs the page says: "For an evening's queue,
     leave this tab open in front, or set your PC's sleep to Never: a PC that sleeps stops charting until it wakes"
     [inference: sleep suspends WSL's VM, and the chart goes on at the wake]. Considered and left for later:
     songcharter asking Windows itself to stay awake (powershell.exe calling SetThreadExecutionState for as long as
     the queue runs, tab or no tab); under Smart App Control PowerShell may run in Constrained Language mode, which
     refuses the Add-Type that call needs [inference]: a check on the owner's PC first.
   - **The update notice** is held until the queue is empty (its line says to close the window, which would stop the
     queue), then shown.
   - **The whole queue's estimate:** the waiting songs' ranges summed (each its own `estimate.for_job` from when it
     was added) with the charting song's time left (M8-04 item 5's re-estimate once its first take is measured;
     before, its range less the time it has run, at least 0): "All 6 songs: about 1 h 10 min to 3 h 20 min more".
5. **"Your charts"**, as the question has it: the library's folders with a `report.json`, newest first, with the
   song.ini's name and artist, the date (report.json's time), the verdict, **Install** (`clonehero.install`, its 409
   asking to replace as today) and **Open** (`/api/open` with the folder's id, looked up among the library's folders
   by the server: no path from the page, as M8-04's "built"). The preview and Listen only while the song's work folder
   is still in the cache (`cache.by_key`), else not offered. **Nothing deleted from the page:** a deleted chart cannot
   come back, a library folder is small (song.ogg and the notes, about 5-15 MB [est.]), and Open lets him delete one
   in Explorer. The work cache's pruning is unaffected.
6. **The disk.** Uploads up to 1 GB each as today, and at most 20 waiting songs [judgement]. **A finding the defaults
   miss:** the cache's pruning never deletes a work folder used in the last 24 hours (`cache.RECENT_S`), and a song's
   is 0.7-1.2 GB (Take Me Out 696 MB, the test song 1.19 GB: DESIGN's M3 table), so an evening of 10 songs keeps
   about 7-12 GB in the cache whatever its 5 GB budget, where the guide asks for about 20 GB free on C:. The first
   build measures the free disk before each song (`device.refresh_disk`, as the header does) and pauses the queue
   under doctor's 6 GB (`device.MIN_FREE`), saying so ("C: is nearly full, so the queue is paused: free some space,
   then Carry on"). A rule that keeps the cache inside its budget during a queue (pruning a queue's own finished
   songs, whose Look then loses its preview and Listen) is `cache.py`'s, outside this order's files: the
   orchestrator's call. **The update:** install.sh refuses while a server answers (M5-13), so with a long queue an
   update waits for the queue's end and the window closed, which the held notice reflects.
7. **The cost** (a builder's hours with tests and screens; judgement):

   | Part | Hours |
   |---|---|
   | A. The server's queue: entries, one child at a time, queue.json and the paused restart, the uploads kept, Pause, Remove, the two-failures and disk pauses, its API behind the guards | 5-6 |
   | B. The routes by job id (results, preview, art, listen, install, zip) and the finished jobs kept | 3-4 |
   | C. The page's queue: a drop of several and its shared form, the list with Install and Look, the title, wake lock, notice and whole-queue estimate across songs | 5-6 |
   | D. "Your charts" (the library read, Install, Open by id) | 3-4 |
   | E. DESIGN 4.5, the guide's screen, the screens in Chromium | 2 |

   A, B, C and E: 15-18 hours, inside the order's 2 days; D adds 3-4. **Suggested narrowing:** the queue (A, B, C,
   E) in M8-10, and "Your charts" (D) as a small order of its own after it, since the queue's list already gives
   Install for the evening's songs. The figures are for lyrics refused and no reordering.

### Decision (the orchestrator, 2026-11-09)

The note is accepted with its suggested narrowing:
- M8-10 builds A, B, C and E as the note has them: one shared form for a drop of several; lyrics refused in a waiting
  song; the queue paused after a restart, with Carry on and Clear the list; Pause and Remove; no reordering; two
  failures in a row pause the queue; the disk pause under `device.MIN_FREE`; the update notice held.
- "Your charts" (D) becomes a small order of its own after M8-10.
- The cache rule for a queue's finished songs (`cache.py`) is a follow-up, decided on evidence.
- Lyrics held in memory, "Chart next" and the Windows keep-awake call are later options; the last waits for a check
  on the owner's PC.

## What to do

What the accepted note says, in small commits: the server's queue (jobs.py's one child at a time unchanged), its API
(the note's endpoints, each behind the same guards as `/api/jobs`), the page's queue and "Your charts", DESIGN 4.5 and
the guide's screen.

## Done means

- [CI] The suite green; the UI tests cover: a second song queued while one charts and started when it ends; cancel and
  failure as the note decided; the list read from a made-up library (no real song); install and open from the list;
  every new endpoint's guards (Host, Origin, the `X-Songcharter` header). Each new test fails on a break of what it
  covers.
- [dev] A stand-in server on golden folders (M7-10's route), Chromium at 1280x860 and 700 px, light and dark: two songs
  queued, the second's Done screen after the first's, "Your charts"; the shots looked at, then deleted. No console
  errors.
- [dev] Two charts never run at once (a test with a stand-in child that records its start and end times).

## Report

`<scratchpad>/m8/m8-10.report.md`: the commits, which parts of the note were built, the checks, what the screens showed.
