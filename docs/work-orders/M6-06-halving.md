# M6-06: a grid at twice the humans' tempo, halved

**Branch:** `m6-06-halving`, from `main` after M6-05's merge (both touch the octave pass in `assemble.py`). **Agent:**
`sc-builder`, then `sc-reviewer`. May push its branch to run CI. **Files:** `songcharter/assemble.py` (the octave
pass), `songcharter/beatgrid.py` only for a statistic it needs, their tests, `docs/DESIGN.md` 2.3,
`docs/work-orders/M5-99-later.md`. **Time budget:** a day and a half, the measurement included.

*Written by the orchestrator on 2026-11-06 from M5-99 ("The grid at double the humans' tempo") and a measurement for
M6-05 (the measurer's report in the orchestrator's scratch folder).*

## Why

The shred stress song (`sooth`) is charted on a 154 BPM grid; its human charts are at 77 BPM. The first pass folds
tempi into 85-185 BPM, so a pulse under 85 stays at double, and M5-01 builds only the doubling pass. The effects:
about twice the star power (35 phrases, 3.89 a minute, against the humans' 2.34-3.23; M6-01's 160-BPM ceiling does
not reach 154), solo caps in measures half as long, the natural-HOPO threshold in ticks read on the wrong grid, and
plain beat F1 0.643 (octave-tolerant 0.94-0.96). allin1's beats score 0.967 on it at their own rate (the measurer, a
side finding), so the information is there.

## What to do

1. **Measure first** (numbers only): on every song of the reference set, the stress set and, if built, the 20-song
   set (`$DEV/eval-set20`), the candidate statistics a halving decision could use at the first grid: the share of
   onsets on beat lines against off them (the odd 8ths), the snare on every other line, allin1's beat rate against
   ours, the HOPO shares; and each song's humans' tempo against ours. Which statistic separates the songs at twice the
   humans' tempo (today: sooth) from the rest, with what margin?
2. **The rule:** halve the grid (every other beat line, the phase chosen by the same evidence) when the chosen
   statistic says so, with a guard as M5-01's doubling has; record the statistics and the decision in report.json.
   Check the natural-HOPO threshold and the quantizer's slots on the halved grid (the shred song's 16ths must stay
   16ths: on a 77 BPM grid they are its 1/32, so the slot rules follow the octave as the bass's do on a doubled grid).
   If no statistic separates the songs by a clear margin on the songs available, stop and report: don't tune.
3. Tests with made-up beats and onsets: a song at twice its pulse halves; an ordinary song and a doubled song do not;
   the guard; each failing on its break.

## Evaluation

- **Golden** `--expect none` (no reference is at twice its humans' tempo; if one halves, stop and report).
- **The stress set** against main before this order: sooth's beat F1 toward 1.0, its star power per minute inside its
  humans' range, its solo spans' overlap with the humans' not lower, every F1@50 not lower (the notes must keep their
  slots); troop, pm2 and break unchanged.
- Golden and stress runs need `--rerun bass` against kept folders made at 0.1.0's version.

## Done means

- [dev] The suite; the new tests fail when their code is broken; the golden diff exit 0; the stress table.
- [CI] Green on the branch.
- [docs] DESIGN 2.3 (the halving pass beside the doubling one, with the table); M5-99's item closed or narrowed.

## Report

`<scratchpad>/briefs/m6-06.report.md`: the commits, the table, the rule kept or why not, the checks.
