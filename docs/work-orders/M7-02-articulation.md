# M7-02: how the guitar's notes are played: HOPO and tap states, and sustains at a slow tempo

**Conditional on M7-01 part A** (below, Bar): build only the sub-changes whose candidate cleared its bar; with none,
the order is closed and its numbers go to `dead_ends`. **Branch:** `m7-02-articulation`, from `main` after M7-01's
report is committed. **Agent:** `sc-builder`, then `sc-reviewer`. May push its branch to run CI. **Files:**
`songcharter/quantize.py` (the sustain floor; a tap rule; a HOPO rule if it needs the quantizer),
`songcharter/assemble.py` (`HOPO_RULES` and the part rules only), `songcharter/pipeline.py` (the guitar part's
`hopo` only), `eval/scorer/score.py` (a measure the bar reads that it lacks: tap precision, sustain agreement), their
tests, `docs/DESIGN.md` 2.6 (steps 4 and 5), 2.7, `docs/work-orders/M5-99-later.md`. Not `engines/`, not the stem
stage of assemble.py (M7-04's). **Time budget:** a day. **Rough cost:** 4-6 % of a week's meter.

*Written by the M7 planner on 2026-11-07 from the video review's findings 2 and 4 (M7-00 section 1), M5-99 ("HOPO,
strum and tap states independent of the octave", "Beat-counted rules at a slow tempo") and M7-01's plan.*

## Why

`hopo: "forced"` keeps the states the engine forced and lets the natural rule decide the rest on our grid. On a
halved grid the true tempo's picked 8ths fall under the 65-tick threshold and become HOPOs (sooth: 621 such notes
went strum to HOPO at M6-06); on tod the engine forced strums on a solo's 16ths (118 of 119). The humans themselves
differ (sooth's primary leaves most of those 8ths HOPO, its alt strums many: M6-06's 0.60 / 0.45). Taps come from
the engine (sooth 0.14 against the humans' 0 and 0.07). The Expert sustain floor counts beats: 584 ms at 77 BPM, where
sooth's sustain share fell to 0.05 against its humans' 0.07 and 0.14, and one halved 20-song song's to 0.04 against
0.25 (v0.3.0's gate).

## What to do

1. **The HOPO rule** M7-01's A-a picked, as a `HOPO_RULES` entry and the guitar part's default in pipeline.py: one of
   "source", "natural", **R1** (the octave rule: the source's states where the grid's octave is not 1, "forced"
   elsewhere; `assemble`'s part rules already choose by octave for the bass) or **R2** (forced, but a strum the
   engine forced where our natural rule makes a HOPO takes the natural state). The bass keeps "forced" unless A-a's
   bass line clears the same bar. `report.json` names the rule and counts the notes whose state it set.
2. **The tap rule** A-b picked (T1: no taps; or T2: taps only in runs of 8 or more notes at 8 or more a second), as a
   `QuantizeRules` field with the old behaviour reachable; counted in `report.json`.
3. **The sustain floor** A-c picked: Expert and Hard keep a sustain of at least max(200 ms, min(0.75 beat, X)), X
   in ms from A-c; the bass takes it only if A-c's bass line clears the bar too; Medium and Easy unchanged.
4. The measure the bar reads, added to score.py's feel measures where it lacks it (tap precision and recall,
   per-note sustain agreement), so `stress.py score` reports it; M7-01's script (`eval/m7/`) is the reference.
5. Tests with made-up notes: each rule on a halved, a doubled and a first-level grid; the floor at 77 and at 154 BPM;
   each failing on its break.

## Bar (M7-01 part A's numbers, then the branch's own runs)

- **HOPO rule:** guitar per-note state agreement +0.02 pooled over the songs whose humans agree (M7-00 section 4)
  against "forced", its CI above 0, no song down by more than 0.03.
- **Taps:** state agreement not lower than with the HOPO rule alone, and tap precision up.
- **Sustain floor:** per-note sustain agreement +0.03 pooled on the slow songs (grid under 100 BPM), no other song
  down by more than 0.01, the slow songs' sustain share inside or nearer their humans' range.
- The branch's runs give the same numbers as M7-01's simulation within 0.005, or the report says why.

## Evaluation

- **Golden** against `main`, `--rerun drums,bass,sections` both sides, `--expect guitar` (and `bass` if the floor
  reaches it): onset counts and every F1 identical (states and lengths only).
- **Stress and 20-song sets** (M7-00 section 4): base and branch runs, `stress.py compare` "Regressions: 0" on both;
  the feel report's HOPO, tap and sustain lines beside the humans'.

## Done means

- [dev] The suite; the new tests fail when their code is broken; the golden diff exit 0; the compares; the bar's
  table from the branch's runs.
- [CI] Green on the branch.
- [docs] DESIGN 2.6 steps 4-5 and 2.7 (the rule, the floor, the table); M5-99's two items closed or narrowed.

## Report

`<scratchpad>/m7/m7-02.report.md`: the commits, the rules built and those not (with their numbers), the tables, the
checks.
