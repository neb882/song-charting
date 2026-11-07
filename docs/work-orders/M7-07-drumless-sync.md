# M7-07: beats in a drumless stretch from a second evidence source

**Conditional on M7-01 part B-d** (below, Bar): with the straight line no worse than the rest of the song in those
stretches, or no source better there, the order is closed and its numbers go to DESIGN 2.3. **Branch:**
`m7-07-drumless-sync`, from `main` after M7-04's merge (both touch assemble.py). **Agent:** `sc-builder`, then
`sc-reviewer`. May push its branch to run CI. **Files:** `songcharter/beatgrid.py`, `songcharter/assemble.py` (the
grid stage, where a stretch without drum or second-stem evidence is found and filled), their tests, `docs/DESIGN.md`
2.3. **Time budget:** a day and a half. **Rough cost:** 4-6 % of a week's meter.

*Written by the M7 planner on 2026-11-07 from the video review's finding 7 (M7-00 section 1) and M7-01's plan.*

## Why

Where neither the drums nor the second stem time the beats for 16 beats or more, the grid lays a straight line and
warns ("beats at A-B s follow the straight line ..."): sooth has three such stretches (0-13, 168-190, 365-388 s), and
the review sees the highway drift in the second. Sooth's whole-song beat F1 is 0.985 against its humans, so the drift
may be small; M7-01 measures it per stretch on every song, with three candidate sources: allin1's beats (the grid
already reads them for the octave, the doubled start and the downbeats), the bass stem's onset envelope, and the
guitar stem's band under 350 Hz (the review's proposal).

## What to do

1. In a straight-line stretch, the beats from the source B-d picked, refined as the grid refines its other evidence,
   with the straight line kept when the source has too little there (its threshold from B-d); `report.json` records
   the source per stretch, and the warning names it ("follow allin1's beats", say) or stays as it is.
2. Tests with made-up evidence: a drumless stretch with a tempo drift is followed; one where the source is empty keeps
   the line; each failing on its break.

## Bar (M7-01 B-d, then the branch's own runs)

- Beat F1 inside the stretches +0.05 pooled over at least five stretches from at least three songs, against the
  straight line; no stretch down by more than 0.05; every song's whole-song beat F1 not lower.

## Evaluation

- **Golden** against `main`, `--rerun drums,bass,sections` both sides (beatgrid.py is in the drums engine's files),
  `--expect` the songs with a straight-line stretch.
- **Stress and 20-song sets**, `--rerun drums`: `stress.py compare` "Regressions: 0", beat and downbeat F1 not lower
  on any song.

## Done means

- [dev] The suite; the new tests fail when their code is broken; the golden diff exit 0; the compares; the stretches'
  table from the branch's runs.
- [CI] Green on the branch.
- [docs] DESIGN 2.3 (the stretches, the source, the numbers).

## Report

`<scratchpad>/m7/m7-07.report.md`: the commits, the source and its numbers, the tables, the checks.
