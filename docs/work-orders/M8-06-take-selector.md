# M8-06: the take selector, on GPU takes

**Conditional on M8-02 part B:** built only for the candidate that cleared the bar below (a margin, a spike score, the
silent-onset score q05, the learned score L1 or the density rule D1); with none clearing, the order is closed and its
numbers go to `dead_ends` (the take question then rests on GPU takes too). **Branch:** `m8-06-take-selector`, from
`main` after M8-02's report is committed (wave 3). **Agent:** `sc-builder`, then `sc-reviewer`. May push its branch to
run CI. **Files:** `songcharter/takes.py` (the window score, the margin, and for L1 its weights as constants with their
source), `songcharter/assemble.py` only where it hands the splice the stem levels or onset strengths it already has,
`tests/test_takes.py`, `docs/DESIGN.md` 2.7 (Several takes), and for L1 or D1 the fitting script under
`eval/m8/m802/` (the orchestrator commits M8-02's scripts there first). **Not:** `quantize.py`, `pipeline.py`'s guitar
part, the HOPO rules (M8-07's in this wave). **Time budget:** a day (2 hours for a margin alone). **Rough cost:** 2-4 %
of a week's meter.

**Environment:** eval/README.md's step 9, and `SONGCHARTER_HEAVY_MIN_FREE_GB=1` on every heavy job (the suite, the
golden, stress and 20-song runs, builds): about 1.7 GB is free on `/`, `tools/heavy.sh` refuses under 5 GB without
it, and `python -m eval.golden run` takes the lock but not the disk check.

*Written by the M8 planner on 2026-11-08 from M7-01 part C, the take-score spike (docs/reports/M8-spike-takescore.md:
no score clears on CPU takes, the oracle window's headroom +0.042 [+0.031, +0.053]) and M8-02 part B's plan.*

## Why

The splice keeps the base take in a window unless another beats it by 0.05 in mean agreement with the other takes. On
CPU takes the agreement does not track the humans per window (119-133 of 431 windows pick a take 0.05 below the best),
and no margin or score moved the pooled F1 by +0.005. The friend's takes are GPU takes, where the takes experiment saw
the splice gain more (+0.013 on five references). M8-02 part B measures the same candidates on the owner's GPU takes,
plus a learned window score and the humans' density pattern, each scored on songs it was not fitted on.

## What to do

1. The winning candidate in `takes.splice`, exactly as M8-02 measured it (the orchestrator puts its definition and
   numbers here before the order starts):
   - a margin: `MARGIN` and its comment;
   - a spike score (b2, c, d2 or e) or q05: its window score, computed from what assemble already has (the guitar
     stem's levels; an onset-strength envelope only if assemble computes one, else from the stem it has loaded,
     with librosa, which the bass engine already needs: no new dependency);
   - L1: the features as M8-02 defined them, the model's weights fitted on all 23 songs' GPU windows by the committed
     script (deterministic: a fixed solver and seed), the threshold p, all as constants in `takes.py` with the
     script's name and the commit it ran at;
   - D1: the density ratio as a constant from the same script.
2. `report.json`'s `parts.guitar.takes` records the score's name and each window's values, as it does today's.
3. Tests: a window the new score switches and one it keeps, each failing on its break; L1's or D1's constants
   reproduced by the script from a small made-up fixture (no real song in the repository); the existing splice tests
   pass unchanged (or the report says why one moved).

## Bar (M8-02 part B)

Pooled guitar Expert F1@50 against the primaries (the 19 songs whose humans agree) at least +0.005 over today's GPU
splice (`m05`), its paired-bootstrap CI above 0, no song down by more than 0.01; for L1 and D1, on held-out songs
only. That bar holds for M8-02's primary candidates (L1 at p 0.6, D1 at its 10 % rule, q05), named before any number;
an exploratory one (a margin, a spike score, L1 at another p) clears only with the CI's lower end at +0.002 or more
as well (the advisor's finding 3: the best of about 25 candidates against one 95 % CI). Re-measured on the branch:
M8-02's GPU arms rebuilt with the branch's `takes.py` (the takes are files; no GPU needed) within 0.002 of what M8-02
reported. The CPU's `--takes 4` (M7-01's CPU takes) reported beside it, not lower by more than 0.005 pooled.

## Evaluation

- **Golden** `--expect none` (one CPU take: the splice is never reached), identical.
- The stress and 20-song sets: identical (one take).
- The owner's GPU check at the gate reads the new picks on his charts (`parts.guitar.takes`).

## Done means

- [dev] The suite; the new tests fail on their breaks; the GPU arms re-measured as above.
- [CI] Green on the branch.
- [docs] DESIGN 2.7: the candidate, its numbers on GPU and CPU takes, the windows switched.

## Report

`<scratchpad>/m8/m8-06.report.md`: the commit, the re-measured bar, the checks.
