# M8-08: the bass's unpitched onsets, gated by the pitch track

**Conditional on M8-03 part B:** built only for the gate (g1, g2 or g3, at the L and G that cleared) that cleared the
bar below; with none clearing, the order is closed and the bass's onsets over held notes go to `dead_ends` with M7-03's
(then three rules measured: the HFC gate, the run rule, the pitch gate). **Branch:** `m8-08-bass-unpitched`, from
`main` after M8-03's report is committed (wave 2). **Agent:** `sc-builder`, then `sc-reviewer`. May push its branch to
run CI. **Files:** `songcharter/engines/bass.py` (the gate, its constants, the engine's version so its cache key
changes), `tests/test_engines_bass.py`, `docs/DESIGN.md` 2.8. **Not:** `assemble.py`, `quantize.py`, `starpower.py`
(M8-09's). **Time budget:** half a day. **Rough cost:** 1-2 % of a week's meter.

**Environment:** eval/README.md's step 9, and `SONGCHARTER_HEAVY_MIN_FREE_GB=1` on every heavy job (the suite, the
golden, stress and 20-song runs, builds): about 1.7 GB is free on `/`, `tools/heavy.sh` refuses under 5 GB without
it, and `python -m eval.golden run` takes the lock but not the disk check.

*Written by the M8 planner on 2026-11-08 from M7-01's B-b and its B-b2 addendum and M8-03 part B's plan.*

## Why

The bass is our rule engine (HFC onsets, pYIN pitch, a rank map). Its same-lane repeats run above the humans' (0.585
against 0.487), and 88 % of our same-lane pairs carry the same pitch by the engine's own track: the excess is the onset
detector's. Two gates were measured and closed (precision 0.21-0.48: they removed real notes). On ntl, a ballad of the
owner's, the fast same-lane runs' onsets mostly carry no pitch at all: M8-03 part B scores a gate that reads that.

## What to do

1. In `engines/bass.py`, after the pitches: drop the onsets the winning gate names (the orchestrator writes its
   definition and numbers here first), before the lane map; `engine.json` counts them (`unpitched_dropped`).
2. The engine's version raised, so every kept bass output is rerun (golden `--rerun bass` both sides already).
3. Tests: an onset the gate drops and one it keeps (voiced; outside a run; not held), each failing on its break, on a
   made-up stem (a synthetic tone with clicks), not a real song.

## Bar (M8-03 part B)

Removal precision 0.75; bass F1@50 +0.005 pooled with its CI above 0 (or not lower, the CI's lower end above -0.002,
for a gate at precision 0.9 or more); no song down by more than 0.01, no reference's bass down by more than 0.01; the
human notes removed under 0.5 % on every song; re-measured on the branch's golden, stress and 20-song runs within
0.005 of M8-03's figure.

## Evaluation

- **Golden** `--expect bass`; the references' bass F1@50 not lower by more than 0.002 each (M7's risk 7: the order
  stops if a reference falls 0.01).
- **Stress and 20-song sets:** 0 regressions; the bass's repeat share after against the humans' in the report.
- ntl's counts, if its work folder is still on the machine (M8-03 says).

## Done means

- [dev] The suite; the tests fail on their breaks; the compares as above.
- [CI] Green on the branch.
- [docs] DESIGN 2.8: the gate with M8-03's numbers.

## Report

`<scratchpad>/m8/m8-08.report.md`: the commit, the compares, the repeat share.
