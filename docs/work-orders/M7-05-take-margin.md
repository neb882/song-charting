# M7-05: the take margin, from 4-take charts against the humans

**Conditional on M7-01 part C** (below, Bar); with no margin clearing it, the order is closed (0.05 stays, its
numbers in DESIGN 2.7). **Branch:** `m7-05-take-margin`, from `main` after M7-01's report is committed. **Agent:**
`sc-builder`, then `sc-reviewer`. May push its branch to run CI. **Files:** `songcharter/takes.py` (`MARGIN` and its
comment), `tests/test_takes.py`, `docs/DESIGN.md` 2.7 (Several takes). **Time budget:** two hours. **Rough cost:**
1-2 % of a week's meter.

*Written by the M7 planner on 2026-11-07 from the video review's finding 3 (M7-00 section 1) and M7-01's plan.*

## Why

`takes.MARGIN` 0.05 keeps the base take (seed 20260609) in a window unless another beats it by that much mean F1
against the others. It was set when the base was the GPU take and the other seeds CPU takes; since M4 all four run on
one device. On the owner's GPU chart of sooth 18 of 22 windows kept the base, several where another take scored
0.03-0.05 higher. Splicing four takes gained +0.013 F1@50 over one on five references (2026-11-02, the takes
experiment); the margin itself was never measured against the humans.

## What to do

1. `MARGIN` set to the value M7-01's C-c picked; its comment says where the number comes from.
2. Tests: a window where another take wins by just over and just under the new margin, failing on its break; the
   existing splice tests pass unchanged (or say why one moved).
3. DESIGN 2.7: the margin's table (each arm's pooled F1@50, its CI, the windows switched), CPU and GPU arms.

## Bar (M7-01 part C)

The margin's pooled guitar F1@50 against the primaries at least +0.005 over 0.05's, its paired-bootstrap CI above 0,
no song down by more than 0.01; and on part D's GPU arm, if it arrived, the same sign.

## Evaluation

- **Golden** `--expect none` (one take: the margin is never read).
- The 4-take charts are M7-01's; the owner's GPU check at the release gate reads the new picks on his charts.

## Done means

- [dev] The suite; the new tests fail when the margin is broken.
- [CI] Green on the branch.
- [docs] DESIGN 2.7's table.

## Report

`<scratchpad>/m7/m7-05.report.md`: the commit, the table, the checks.
