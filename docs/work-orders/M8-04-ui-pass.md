# M8-04: the UI pass after v0.4 (and the queue's design note)

**Not conditional** (nothing here charts). **Branch:** `m8-04-ui-pass`, from `main` after the reset (wave 1).
**Agent:** `sc-builder`, then `sc-reviewer` (who also looks at the screens). May push its branch to run CI. **Files:**
`songcharter/ui/server.py`, `songcharter/ui/jobs.py` (the snapshot's fields only: no change to the one-job design),
`songcharter/ui/estimate.py`, `songcharter/ui/static/{app.js,index.html,app.css}`, `tests/test_ui_*.py`,
`docs/guide/windows-wsl.md` (the screens' sentences), `docs/DESIGN.md` 4.5, and the "Design" section of
`docs/work-orders/M8-10-queue.md`. **Not:** anything under `songcharter/` outside `ui/`, `pipeline.py`'s events
(M8-05 owns those in this wave), `clonehero.py`. **Time budget:** 2 days; stop and report at the budget.
**Rough cost:** 5-6 % of a week's meter. **Environment:** the suite through `tools/heavy.sh` with
`SONGCHARTER_HEAVY_MIN_FREE_GB=1` (about 1.7 GB free: heavy.sh refuses under 5 GB otherwise).

*Written by the M8 planner on 2026-11-08 from docs/reports/m7-ui-review.md (items 5-10; the orchestrator's routing
there), the v0.4.0 gate's two notes (PROGRESS `deferred`, "[v0.4.0 gate] The time estimate") and DESIGN 4.5. The owner
left the page to the orchestrator ("I'll leave it up to you. you're the expert").*

## Why

M7-10 put the result above the fold and the estimate on the page. What is left of the review is what the friend meets
after that: a Linux path he cannot open, flags with no way to their picture, a bare text box for the Songs folder, a
2,000-px options form for choices he never changes, an estimate that never improves once the chart is under way, and a
"stopped" heading on a page whose text says the chart may still be running.

## What to do, in this order (a commit each)

0. **The queue's design note** (item 9), first, in M8-10's work order under "Design" (its questions are listed
   there): a page or two, no code. Commit it on this branch and tell the orchestrator, who reads it while the builder
   goes on; M8-10 builds what the orchestrator accepts. About 2-3 hours.
1. **Item 5, the built folder:** the Done screen's sentence names the song (its folder's name), not the Linux path;
   `POST /api/open` takes `"built"` (the result's folder) besides `"song"` and `"exports"`, so "Open folder" works
   before an install too; the `\\wsl$` form of the path only as the button's hover text. The server opens only the
   current result's folder (no path from the page). 1-2 hours.
2. **Items 6 and 10, flags to pictures and sound:** each "Worth a look" flag's start (mm:ss) links to its preview page
   (`floor(start / page seconds) + 1`, the page length from the result); the pages and the overview open in an
   in-page lightbox (one `<dialog>`, keyboard and Escape, the CSP unchanged) rather than a new tab; each flag also
   offers "Listen here": the Listen box set to the flag's part and Expert, the render started at the flag's time
   (`audio.currentTime`, a second before it). 3-4 hours.
3. **Item 7, the Songs folder:** the field is prefilled with `clonehero.describe`'s best guess always (today only when
   none is found), with the sentence saying it is a guess; nothing read from Clone Hero's own settings (M8-00
   section 7). 1 hour.
4. **Item 8, Best or Quick:** at the top of the options, "Chart it" as well as at the bottom; on a GPU, a two-way
   choice, "Best chart (4 guitar takes, about N-M minutes)" and "Quick chart (1 take, about N-M minutes)", each with
   `estimate.for_job`'s range for this song; on the CPU no choice (1 take, as today), a line saying so. The takes'
   number box, the device and "Make a preview" under a folded "More options"; Lyrics and Pictures in a `<details>`
   of their own. The options sent to the job are what they are today for each choice (Best = the defaults); no option
   lost. 2-3 hours.
5. **The re-estimate after the first take** (the gate's note), **with no change to `pipeline.py`** (M8-05's file in
   this wave): the pipeline's `take` event fires as each take starts and carries no seconds, and jobs.py stamps
   every event with `at` (the server's clock), so the first take's seconds are `at` of the second take's event less
   `at` of the first's (the advisor's finding 5); a 1-take chart has only the guitar's `stage_end` seconds, after
   which only the stages after the guitar remain. From the second take's start the progress line becomes "about N-M
   more minutes": the takes left at that first take's measured seconds less its separation part (`estimate.py`'s
   first-take model, its range for the low and high ends), plus the stages after the guitar at their rates; the
   first estimate stays above it, struck through or folded. The model is in `estimate.py` with its evidence in its
   docstring (the takes experiment's later takes against the first; the owner's 9:05 song), so tests can pin it. 2-3
   hours.
6. **The not-answering heading** (the gate's note): when nothing answers (`gone(true)`), the heading reads
   "songcharter is not answering" and the tab "Not answering"; the stopped case (`gone(false)`, a 404 from a
   songcharter started since) keeps "songcharter stopped". 0.5 hour.
7. DESIGN 4.5 and the guide's screens updated to what the page now says.

## Done means

- [CI] The suite green on the branch; the UI tests cover: `/api/open` with `"built"` (and a path from the page refused),
  the flag-to-page arithmetic at a page's edges, the prefill, the options each choice sends (Best and Quick equal
  today's defaults and `--takes 1`), the re-estimate's numbers against hand arithmetic on the test song's and the
  9:05 song's take times, the two headings. Each new test fails on a break of what it covers (the builder breaks each
  and says so).
- [dev] A stand-in server on a golden folder (M7-10's route), Chromium at 1280x860 and 700 px, light and dark: the Done
  screen, a flag's page in the lightbox, Listen from a flag, the options with Best/Quick on a GPU doctor summary and
  without it on a CPU one, the progress screen before and after the first take; the shots looked at by the builder and
  the reviewer, then deleted (they show a song's name). No console errors.
- [dev] No file outside the list changed; the golden charts need no run (nothing charts).

## Report

`<scratchpad>/m8/m8-04.report.md`: the commits, the design note's commit, the checks, what the screens showed.
