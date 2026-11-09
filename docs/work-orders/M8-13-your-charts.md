# M8-13: "Your charts", the list of every chart in the library

**Branch:** `m8-13-your-charts`, from `main` after M8-12's merge (df71e82). **Agent:** `sc-builder`, then `sc-reviewer`
(who also looks at the screens). May push its branch to run CI. **Files:** `songcharter/ui/jobs.py` and
`songcharter/ui/server.py` (the library's read and the routes), `songcharter/ui/static/{app.js,index.html,app.css}`,
`tests/test_ui_*.py`, `docs/guide/windows-wsl.md`, `docs/DESIGN.md` 4.5. **Not:** anything that charts, the work cache's
pruning (`cache.py`), deleting a chart from the page. **Time budget:** half a day. **Rough cost:** 1-2 % of a week's
meter.

**Environment:** eval/README.md's step 9, and `SONGCHARTER_HEAVY_MIN_FREE_GB=1` on every heavy job (the suite, builds):
about 1.5 GB is free on `/`.

*Written by the orchestrator on 2026-11-09 from M8-10's design note, part D ("Your charts"), which the orchestrator's
decision on that note made an order of its own after M8-10.*

## Why

M8-10's queue lists the songs of one evening; a chart from last week has no way back onto the page: no list, no
Install again (into a new Clone Hero folder, or after a song was deleted there), no Open. The library already keeps
every chart (`<home>/library/<16 hex>/<name>/` with its `report.json`), so the list is a read of it.

## What to build (M8-10's note, part D)

1. **The list:** the library's folders that hold a `report.json`, newest first: the song's name and artist (its
   song.ini), the date (report.json's time), the gate's verdict in plain words, the audio (one file or split, M8-12),
   and whether its stems were saved. On the start screen under the drop zone, folded when it is long ("Your charts
   (24)"), and reachable from the Done screen and the queue's list.
2. **Install** (`clonehero.install`, with its 409 asking to replace, as today) and **Open** (`/api/open` with the
   folder's id, looked up by the server among the library's folders: no path from the page, as M8-04's "built"), and
   **Download the stems** where the folder's " (stems)" sibling exists (M8-12's route by id).
3. **Look** (the preview and Listen) only while the song's work folder is still in the cache (`cache.by_key`); else not
   offered, and the list says nothing is lost (the chart itself is in the library).
4. **Nothing deleted from the page** (the note's reason: a deleted chart cannot come back; Open lets him delete one in
   Explorer). A folder whose report.json is unreadable is listed by its name with "can't be read", never hidden.
5. Every new route behind the same guards as `/api/jobs` (Host, Origin, `X-Songcharter`); ids are the library's own
   (the 16 hex and the name, checked against the folders the server found), never a path.

## Done means

- [CI] The suite green; the UI tests cover: the list read from a made-up library (several songs, one unreadable
  report.json, a folder without one, a split and a one-file folder, one with stems), newest first; Install and its
  409; Open by id and a path or unknown id refused; Look offered only with the work folder cached; every new route's
  guards. Each new test fails on a break of what it covers (say which; `PYTHONDONTWRITEBYTECODE=1`, no `__pycache__`).
- [dev] The stand-in server on golden folders (made-up names), Chromium at 1280x860 and 700 px, light and dark: the
  start screen with the list, a long list folded, Install and the replace question, Look and its absence; the shots
  looked at, then deleted. No console errors.
- [dev] No file outside the list changed; the golden charts need no run (nothing charts).

## Report

`<scratchpad>/m8/m8-13.report.md`: the commits, the checks, what the screens showed, interpretations to check.
