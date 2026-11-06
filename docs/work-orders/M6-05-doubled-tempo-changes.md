# M6-05: a tempo change under a doubled grid, from allin1's beats

**Branch:** `m6-05-doubled-tempo-changes`, from `main` at d5d3255 or later. **Agent:** `sc-builder`, then
`sc-reviewer`. May push its branch to run CI. **Files:** `songcharter/assemble.py` (`_octave_pass`'s second pass and
its start grid), `songcharter/beatgrid.py` only if `beat_grid`'s `start=` needs a helper, the code that hands allin1's
beats from the sections engine to assemble (`songcharter/sections.py`, `songcharter/engines/sections.py`,
`songcharter/pipeline.py`, only as needed), their tests, `docs/DESIGN.md` 2.3, `docs/work-orders/M5-99-later.md`.
**Time budget:** a day.

*Written by the orchestrator on 2026-11-06 from a measurement (the measurer's report, in the orchestrator's scratch
folder; its numbers below).*

## Why

On the 200 BPM fourth stress song (pm2) the human charts hold one 170 BPM stretch (about 246-291 s; 128 beats, 33
tempo markers). Both our passes lay a straight line through it: F1 0.39-0.46 in the stretch (71-77 ms off), then a
constant half-beat phase slip after it (F1 0.00 in all 16 windows from 290 s; we land on the "and"). Beat F1 0.598,
where the humans agree at 1.000. `local_periods` finds the stretch and `missed_tempo_changes` warns of it; nothing
acts on either. `keep_line` is not the cause (off, nothing changes on pm2; on troop it earns its place). The beat
tracker's own beats flip phase on this song (F1 0.20-0.32).

allin1's beats (the sections engine runs allin1; `sections/segments.json` holds them, at half the humans' rate on this
song) doubled by midpoints follow the stretch (0.98-1.02 in it) and keep the phase after it: as the second pass's
start grid (`beat_grid(start=...)` at the doubled range), pm2's beat F1 0.598 -> 0.985, windows under 0.9 from 22 to 3
of 45, median window error 11.5 -> 8.6 ms. The entry into the stretch (230-250 s) stays weaker (0.55-0.85).

## What to build

1. In the octave pass's second pass, when the doubled grid's tempo check (`missed_tempo_changes`) is not empty and
   allin1's beats are there, start the doubled grid from them: doubled by midpoints, shifted to the onset-to-beat
   convention our grid uses, at the doubled range; record in report.json which start the grid used and why. With no
   allin1 beats (the librosa fallback, a failed sections stage) or no warning, nothing changes. Check that the
   sections stage has run before assemble on every path (the chart command, the page, a cached run) and say so.
2. Then measure the rule before deciding to keep it: pm2 (the positive case), troop, the shred song, the rock song and
   every reference (their warnings are empty today, so they must not move; confirm). If the warning fires on a song
   it should not, or the start grid makes any song's beat F1 worse, stop and report: don't tune.
3. Tests with made-up beats: a doubled grid with a tempo change and allin1-like beats follows it; no warning or no
   allin1 beats: unchanged; each failing on its break.

## Evaluation

- **Golden** `--expect none` (no reference's tempo warning fires; if one does, stop and report).
- **The stress set** against main before this order: pm2's beat F1 from 0.598 toward 0.98, its guitar, bass and drums
  F1@50 not lower (the notes follow the grid: report them, they may rise); troop, the shred song and the rock song
  unchanged.
- Golden and stress runs need `--rerun bass` against the kept folders (the version's bump changed bass's cache key).

## Done means

- [dev] The suite; the new tests fail when their code is broken; the golden diff exit 0; the stress table.
- [CI] Green on the branch.
- [docs] DESIGN 2.3 (the second pass's start from allin1's beats when a tempo change is missed), with the numbers;
  M5-99's "a tempo change under a doubled grid" closed or narrowed; the shred song's grid at twice the humans' rate
  (allin1 0.967 against our 0.643 there, a side finding) noted under the halving rule.

## Report

`<scratchpad>/briefs/m6-05.report.md`: the commits, the measurement, the rule kept or why not, the checks.
