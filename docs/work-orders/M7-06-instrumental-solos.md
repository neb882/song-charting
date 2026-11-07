# M7-06: the solos' share cap, from the 23 songs' humans

**Conditional on M7-01 part B-c** (below, Bar); with no candidate clearing it, the order is closed and `max_share`
0.40 stays, with B-c's table in DESIGN 2.10 (the owner's v0.2.0 decision, "revisit with the 20-song set", then
answered). **Branch:** `m7-06-instrumental-solos`, from `main` after M7-05's merge (the same builder slot); if the
rule needs the vocals stem's level, after M7-04's too (assemble.py passes it). **Agent:** `sc-builder`, then
`sc-reviewer`. May push its branch to run CI. **Files:** `songcharter/starpower.py` (`SoloRules`), and only for an
instrumentals-only rule `songcharter/assemble.py` (passing `report.json`'s vocals stem level to the solo choice);
`tests/test_starpower.py`; `docs/DESIGN.md` 2.10. **Time budget:** half a day. **Rough cost:** about 2 % of a week's
meter.

*Written by the M7 planner on 2026-11-07 from the video review's finding 8 (M7-00 section 1) and M7-01's plan.*

## Why

M5-03 set `max_share` 0.40 from 13 human charts (the largest share 0.357, sooth's alt chart). On the owner's sooth
chart a 31-measure candidate (152-249 s) was cut to 5 measures by the share. The review proposes 0.75 for
instrumentals (vocals stem under -35 dB). Sooth's own humans: the primary charts no solo, the alt two of 96 s (share
0.357) [here: M5-03's table]. The 20-song set adds charts, some on solo-heavy songs and perhaps instrumentals.

## What to do

1. The candidate B-c picked: `max_share` for every song at the 23 songs' largest human share rounded up to the next
   0.05 (M5-03's rule), or a separate cap for instrumentals (the vocals stem's level under B-c's threshold), the
   instrumentals' cap from their humans the same way.
2. `report.json`'s `solo_rules` records the cap used and why (instrumental or not, with the level).
3. Tests: a song over the old cap and under the new keeps its solo; an instrumental and a vocal song on each side of
   the threshold; each failing on its break.

## Bar (M7-01 B-c)

- At least two human charts of at least two songs (instrumentals, for an instrumentals-only cap) over 0.40.
- Our solo spans' overlap with the humans' (the share of their solo time we cover, and of ours inside theirs) up
  pooled over the songs with human solos; every song's solo share inside its humans' range or no further from it.

## Evaluation

- **Golden** against `main`, `--rerun drums,bass,sections`, `--expect guitar` on the songs whose solos move: onsets
  identical.
- **Stress and 20-song sets:** `stress.py compare` "Regressions: 0"; the solo share beside the humans'.

## Done means

- [dev] The suite; the new tests fail when their code is broken; the golden diff exit 0; the compares.
- [CI] Green on the branch.
- [docs] DESIGN 2.10's table and the decision.

## Report

`<scratchpad>/m7/m7-06.report.md`: the commits, the cap and its numbers, the spans that moved, the checks.
