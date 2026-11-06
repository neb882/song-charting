# M6-01: star power and solo caps on fast songs, from the human charts

**Branch:** `m6-01-fast-sp-solos`, from `main` at the v0.2.0 candidate (6b9fd38). **Agent:** `sc-builder`, then
`sc-reviewer`. May push its branch to run CI. **Files:** `songcharter/starpower.py` (`SoloRules`, the phrase count),
the call sites in `songcharter/assemble.py` only to pass what the rules need (the grid's octave or tempo), their tests,
`docs/DESIGN.md` 2.10 (star power and solos), `docs/work-orders/M5-99-later.md`. **Time budget:** a day, the
measurement included.

*Written by the orchestrator on 2026-11-06 from v0.2.0's gate (docs/reports/v0.2.0-gate.md) and M5-99, at the owner's
go-ahead; M6's full plan (a planner, then the advisor) comes after the owner's v0.2.0 results.*

## Why

On a grid the octave pass doubled (§2.3 step 7), the two rules that count in beats and measures count twice as many:
- **Star power:** K = round(span / 40 beats). On the 198 BPM power-metal stress song (troop) that is 5.04 phrases a
  minute against its human charts' 3.03-4.44; on the 200 BPM fourth song (pm2) 4.94 against 1.65-5.49.
- **Solos:** `SoloRules.max_measures` 56 was set from human charts on our maps; on a 200 BPM map 56 measures are 67 s,
  so pm2's solo at 267-365 s was cut to its densest 56 measures.
The human charts of these songs are themselves at 200 BPM, so "count on the first grid" is not obviously right:
measure first.

## What to do

1. **Measure the humans** (numbers only, `eval/stress.py`'s and `eval/scorer`'s readers; never open a package or
   print a lyric): over every human chart of the reference set and the stress set, star power phrases per minute and
   per 40 of their own beats, against each song's tempo; each human solo's length in seconds and in its own
   measures, and the solo share. Put the table in the report.
2. **Choose the rules** that fit the humans across tempos, for example a phrase count by seconds (or by beats at a
   tempo floor) and a solo cap in seconds (or in measures of a bounded length). Prefer rules that leave every
   reference (all octave 1) unchanged. If no rule fits clearly better than today's, stop and report the table: don't
   tune.
3. Build the chosen rules; report.json records them. Tests with made-up charts: the rule on a 100 and a 200 BPM grid,
   the boundaries, each failing on its break.

## Evaluation

- **Golden** (`--expect none` if the rules leave the references unchanged, else name the parts and say why).
- **The stress set** against main before this order: troop's and pm2's star power per minute inside their humans'
  range, their solo spans' overlap with the humans' not lower (troop's 0.97-1.00), the shred song's and the rock
  song's solos and star power unchanged unless the measurement says otherwise; every other number unchanged.
- Golden and stress runs need `--rerun bass` against the kept folders (the version's bump changed bass's cache key).

## Done means

- [dev] The suite; the new tests fail when their code is broken; the golden diff; the stress table before and after.
- [CI] Green on the branch.
- [docs] DESIGN 2.10 with the human table and the rule chosen; M5-99's two items closed or narrowed.

## Report

`<scratchpad>/briefs/m6-01.report.md`: the commits, the human table, the rule and why, the golden verdict, the stress
table before and after, anything uncertain.
