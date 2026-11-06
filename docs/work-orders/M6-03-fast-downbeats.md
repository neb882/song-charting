# M6-03: downbeats on fast songs

**Branch:** `m6-03-fast-downbeats`, from `main` after M6-05's merge (both touch the octave pass, and the downbeats
follow the grid M6-05 chooses: on a song with a tempo change it starts from allin1's beats, whose downbeats are a
candidate here). **Agent:**
`sc-builder`, then `sc-reviewer`. May push its branch to run CI. **Files:** `songcharter/beatgrid.py` (`bar_phase`
and its callers), `songcharter/assemble.py`'s octave pass only to carry a phase, `songcharter/sections.py` or
`songcharter/engines/sections.py` only to read allin1's downbeats if they are chosen, their tests, `docs/DESIGN.md`
2.3, `docs/work-orders/M5-99-later.md`. **Time budget:** a day, the measurement included.

*Written by the orchestrator on 2026-11-06 from v0.2.0's gate and M5-99 ("Downbeats when the kick is on every beat").*

## Why

The bar phase (which beat is "1") is a guess on the fast stress songs: downbeat F1 0.000 on the 198 BPM power-metal
song and 0.014 on the 200 BPM fourth song against their human charts (bar_phase's margin 0.013 there: the kick is on
every beat). Bar lines, the measures star power and solos count, and section starts all hang on it. The references'
downbeats are right (0.988 on the rock stress song, the reference set's beat F1 0.8755 with downbeats in DESIGN 2.3).

## What to do

1. Measure the candidates against every human chart's downbeats (their tempo maps' measure lines), on the
   references and the stress set: today's `bar_phase`; the first grid's phase carried onto the doubled grid;
   allin1's downbeats (the sections engine runs allin1 already; its output may hold them); a vote of these. Report
   downbeat F1 per song and each candidate's margin.
2. Adopt the candidate that fixes the fast songs and leaves every reference's downbeats as they are; if none does
   clearly, stop and report: don't tune.
3. Tests with made-up beats and onsets: the chosen rule on a kick-on-every-beat song and on an ordinary one, each
   failing on its break.

## Evaluation

- **Golden** (`--expect none` if the references' phases stay; else name what moved and why).
- **The stress set** against main before this order: troop's and pm2's downbeat F1 up, the rock song's 0.988 and the
  shred song's 0.278 not lower; star power and solos as they follow; every F1@50 not lower.
- Golden and stress runs need `--rerun bass` against the kept folders (the version's bump changed bass's cache key).

## Done means

- [dev] The suite; the new tests fail when their code is broken; the golden diff; the stress table.
- [CI] Green on the branch.
- [docs] DESIGN 2.3 with the table and the rule; M5-99's item closed or narrowed.

## Report

`<scratchpad>/briefs/m6-03.report.md`: the commits, the table, the rule and why, the checks, anything uncertain.
