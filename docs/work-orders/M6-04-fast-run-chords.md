# M6-04: chords in fast runs, toward the humans'

**Branch:** `m6-04-fast-run-chords`, from `main` at f3b9ebb or later. **Agent:** `sc-builder`, then `sc-reviewer`. May
push its branch to run CI. **Files:** `songcharter/quantize.py` (the 5-fret clean-up, `ChordLimits`, `limit_chord`),
the guitar part's call in `songcharter/assemble.py` only to pass a setting, their tests, `docs/DESIGN.md` 2.6,
`docs/work-orders/M5-99-later.md`. Not `songcharter/reduce.py` (the lower levels follow Expert). **Time budget:** a
day, the measurement included.

*Written by the orchestrator on 2026-11-06 from v0.2.0's gate and the feel note (docs/reports/feel.md, part 2:
"a chord appears only where a chord rings").*

## Why

On the fast stress songs our Expert guitar is too chordy: 0.09 of the power-metal song's notes (troop; its human
charts 0.03-0.05) and 0.11 of the fourth song's (pm2; humans 0.02-0.04), after M5-01 stopped merging notes distinct in
time. These are the guitar engine's own chords (several frets at one onset), mostly inside fast runs, where a human
charts single notes: a chord in a 16th-note run is a shape change at speed that the music does not ask for. F1@50
counts onsets, so it does not see them; the play test does.

## What to do

1. **Measure the humans** (numbers only, through eval/stress.py's and eval/scorer's readers): over every human
   chart of the reference set and the stress set, the Expert guitar chord share by local speed (the gap to the
   neighbouring onsets, in ms and in beats: under a 16th, a 16th to an 8th, slower), and the same for ours (the
   gate's runs $SONGCHARTER_GOLDEN/gate-rc and gate-rc-stress). Where do ours and theirs part?
2. **The rule:** in the speed bins where the humans chord rarely, a chord of ours becomes one note. Which note: the
   one that continues the run's contour (nearest the neighbours' lanes), or the chord's top or bottom: measure each
   choice's lane agreement with the humans' notes at those onsets and keep the best. Chords in slower passages stay.
   If no rule brings the fast songs' chord share toward the humans' without moving the references' (their chord
   shares are close to their humans' today), stop and report: don't tune.
3. report.json records the rule and how many chords it reduced per part. Tests with made-up notes: a chord inside a
   fast run becomes the chosen note; a chord in a slow passage, a strum section and a chord at a run's start or end
   stay; each failing on its break.

## Evaluation

- **Golden** (`--expect guitar` if the references' charts move; their pooled F1@50 not lower, their chord shares
  toward or within a point of their humans', and report.md read).
- **The stress set** against main before this order: troop's and pm2's Expert chord share toward the humans'
  (0.02-0.05), the rock song's (break) within a point of today's, every F1@50 not lower; the feel report's contour
  and jump measures not worse.
- Golden and stress runs need `--rerun bass` against the kept folders (the version's bump changed bass's cache key).

## Done means

- [dev] The suite; the new tests fail when their code is broken; the golden diff; the stress table before and after.
- [CI] Green on the branch.
- [docs] DESIGN 2.6 with the human table and the rule; M5-99's item on chords closed or narrowed.

## Report

`<scratchpad>/briefs/m6-04.report.md`: the commits, the human table, the rule and why, the golden verdict, the stress
table before and after, anything uncertain.
