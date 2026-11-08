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
