# M6-02: the bass's triplet slots on a doubled grid

**Branch:** `m6-02-doubled-bass-triplets`, from `main` at the v0.2.0 candidate (6b9fd38). **Agent:** `sc-builder`, then
`sc-reviewer`. May push its branch to run CI. **Files:** `songcharter/assemble.py` (`DOUBLED_BASS_SLOTS`,
`part_rules`), `songcharter/quantize.py` only if the triplet test needs a part's own threshold, their tests,
`docs/DESIGN.md` 2.6, `docs/work-orders/M5-99-later.md`. **Time budget:** half a day.

*Written by the orchestrator on 2026-11-06 from M5-11's review (docs/reports/M5-11-octave-by-density.md) and M5-99.*

## Why

On a doubled grid the bass snaps to the grid's 8ths and their triplets (`DOUBLED_BASS_SLOTS` (2, 3), M5-01). Those
triplets are the first grid's 16th-note triplets, finer than its 8th-note triplets (M5-10's review). On the 200 BPM
fourth stress song (pm2) 174 bass notes land on triplet slots (2 on the first grid), 75 of them unmatched, which is the
whole of its bass F1@50 loss against the primary (0.800 -> 0.777, M5-11; the matched notes' timing unchanged). The
humans chart that bass in straight 8ths and 16ths.

## What to do

1. Measure, on troop and pm2 (the two doubled stress songs) against every human chart with a bass part: bass F1@50,
   the notes on triplet slots, the matched notes' timing, under today's (2, 3), no triplet slots (2, 0), and a
   stricter triplet test for the bass on a doubled grid if `quantize`'s run test allows one without touching other
   parts. Also the humans' own triplet share in their bass.
2. Keep the rule that does best on both songs without lowering either below today's; troop's bass F1@50 0.716 against
   its primary must not fall. If none is clearly better on both, stop and report: don't tune.
3. Tests: a doubled grid's bass with scattered onsets near triplet positions snaps as the rule says; an octave-1 grid
   and every other part unchanged; each failing on its break.

## Evaluation

- **Golden** `--expect none` (the references are all octave 1): every chart identical.
- **The stress set** against main before this order: pm2's and troop's bass as above, every other number unchanged.
- Golden and stress runs need `--rerun bass` against the kept folders (the version's bump changed bass's cache key).

## Done means

- [dev] The suite; the new tests fail when their code is broken; the golden diff exit 0; the stress table.
- [CI] Green on the branch.
- [docs] DESIGN 2.6 (the bass on a doubled grid) with the numbers; M5-99's item closed or narrowed.

## Report

`<scratchpad>/briefs/m6-02.report.md`: the commits, the table, the rule and why, the checks, anything uncertain.
