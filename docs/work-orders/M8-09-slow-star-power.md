# M8-09: star power at a slow tempo

**Conditional on M8-03 part C:** built only for the floor tempo B (100 or 120 BPM) that cleared the bar below; with
neither clearing, the order is closed and M5-99's "Beat-counted rules at a slow tempo" goes to `dead_ends` with both
halves measured. **Branch:** `m8-09-slow-star-power`, from `main` after M8-03's report is committed (wave 2, beside
M8-08). **Agent:** `sc-builder`, then `sc-reviewer`. May push its branch to run CI. **Files:** `songcharter/starpower.py`
(`StarPowerRules`: a `min_bpm` beside `max_bpm`), `tests/test_starpower.py`, `docs/DESIGN.md` 2.10. **Not:**
`engines/bass.py` (M8-08's), `assemble.py`, `quantize.py`. **Time budget:** 3 hours. **Rough cost:** 1-2 % of a week's
meter.

*Written by the M8 planner on 2026-11-08 from M5-99 ("Beat-counted rules at a slow tempo", the half M7-01 did not
measure) and M8-03 part C's plan.*

## Why

`starpower.py` places about one phrase per 40 beats of the span from the first to the last Expert onset, the span's
beats counted at most at 160 BPM (M6-01). On a slow grid that reads too few: sooth, halved to 77 BPM, has 1.89
phrases a minute against its humans' 2.33-3.23, who place a phrase every 24-34 beats at that tempo (M5-99). The sustain
floor, the rule's other half, was measured in M7-01 (closed on CPU takes; M8-07 (b) re-measures it on GPU takes).

## What to do

1. `StarPowerRules.min_bpm` (the B that cleared): the span's beats counted at least at that tempo (its average over the
   span), as `max_bpm` caps it; its comment cites M8-03 part C.
2. Tests: a slow made-up chart gains the phrases the floor implies and a chart at 100 BPM or more is unchanged, each
   failing on its break; the existing star power tests pass unchanged.

## Bar (M8-03 part C)

On every slow song (grid under 100 BPM) with a human chart that has star power, the phrase rate moves into or toward
the humans' range and away on none; our phrases' overlap with the humans' not lower pooled over the slow songs; no song
at 100 BPM or over changes. Re-measured on the branch's runs.

## Evaluation

- **Golden** `--expect` the parts whose star power moves; only the slow references (creep, lucretia) may change, and
  only their star power phrases: onsets and F1 identical everywhere, the other four references identical (read
  report.md's track hashes per song).
- **Stress and 20-song sets:** 0 regressions, onsets identical; the slow songs' star power rate in the report.

## Done means

- [dev] The suite; the tests fail on their breaks; the compares as above.
- [CI] Green on the branch.
- [docs] DESIGN 2.10: the floor with M8-03's numbers.

## Report

`<scratchpad>/m8/m8-09.report.md`: the commit, the rates per slow song before and after, the compares.
