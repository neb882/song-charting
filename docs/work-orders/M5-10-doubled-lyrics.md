# M5-10: on a doubled grid, the lyrics snap one slot level coarser

**Branch:** `m5-10-doubled-lyrics`, from `main` after M5-03's merge (it touches `assemble.py`, as M5-03 does).
**Agent:** `sc-builder`, then `sc-reviewer`. May push its branch to run CI. **Files:** `songcharter/assemble.py` (the
`L.place` call and the rule it passes), `songcharter/lyrics.py` only if `place` needs the rule passed differently,
their tests (`tests/test_assemble.py`, `tests/test_lyrics.py`), `docs/DESIGN.md` 2.15. **Time budget:** half a day.

*Written by the orchestrator on 2026-11-05 from M5-04's measurement (docs/reports/M5-04-lyrics-warning.md, step 5).*

## The lyrics rule (absolute)

`docs/work-orders/M4-10-lyrics.md`'s rule binds this order, with M5-04's: timing only; no word printed, logged, saved,
committed or returned, not in a reply, the report, a test, a commit message or an error. Scripts read the human
charts' lyric events in memory and print numbers (M5-09's `eval/stress.py lyrics`); the owner's own pasted text of the
power-metal song (on the dev machine, outside the repository, the session's brief names it) is read only inside the
process that passes it to `pipeline.chart(..., Options(lyrics=text))`. Every chart built with words goes to a
temporary folder that is deleted, `<out>.failed` included. Tests use made-up words only.

## Why

M5-04 measured the lyrics' timing on the chart after M5-01 (step 5 of its report): on the power-metal stress song the
words land a median 67 ms off the human chart's (0.46 within 50 ms, 0.86 within 100 ms), where M5-09 measured 7 ms
(0.68 within 50 ms) on the old 100 BPM grid. The aligner puts about 0.29 of that song's words 38-75 ms early; on
M5-01's 200 BPM grid the lyrics snap to 1/16 slots of 75 ms, so those words land one slot before the human's, where
the old grid's 150 ms slots pulled them onto the beat. It is the bass's case in M5-01 (an engine's spread that the
doubled grid's 16ths cannot resolve), and the same remedy fits: on a doubled grid the lyrics keep the slots today's
grid gave them. The references stay on octave 1, so nothing changes there.

## What to build

1. `assemble.py`: when the grid is doubled (octave 2), `L.place` gets the quantize rules one slot level coarser (the
   doubled grid's 8ths and their triplets, which are the first grid's 16ths and its triplets: `DOUBLED_BASS_SLOTS`,
   or a constant of its own with the same values and a docstring saying why); on octave 1 nothing changes.
   `report["lyrics"]` records which slots were used.
2. Tests: a doubled grid places a word 50 ms before a beat on the beat (the 8th), where the doubled 16th would put it
   a 1/16 early; an octave-1 grid is unchanged; made-up words only. Each fails on its break (octave ignored; the bass
   rule's instrument check copied by mistake, so lyrics never get it).

## Evaluation

- **Golden:** no `--lyrics` in the golden builds: `--expect none` (the cheap run).
- **The lyrics checks** (M5-09's `eval/stress.py lyrics`, and M5-04's way of running the owner's pasted text): the
  power-metal song's words on the chart, against its human chart: median error under 15 ms and at least 0.65 within
  50 ms (M5-09's old-grid figures: 7 ms, 0.68), at least 0.95 within 250 ms; no unsure warning (M5-04's rule); the
  owner's pasted text the same way, reported beside it; take_me_out and the Car Seat Headrest reference unchanged
  (octave 1).

## Done means

- [dev] The suite; the new tests fail when their code is broken; the lyrics checks' numbers, before and after.
- [dev] The golden diff, exit 0.
- [CI] Green on the branch.
- [docs] DESIGN 2.15: the doubled grid's lyric slots, with M5-04's numbers and this order's.

## Limits

- No change to the aligner, its windows, the weights or the warning (M5-04's). No new dependency.
- Nothing that could hold a word is written under the repository or the scratch folder; the report says what was
  deleted.

## Report

`<scratchpad>/briefs/m5-10.report.md`: the commits, the lyrics checks before and after (numbers only), each check's
last lines, the CI run's URL, anything uncertain.
