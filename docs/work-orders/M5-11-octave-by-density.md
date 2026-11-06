# M5-11: the grid's octave decided by note density; the backbeat recorded, no longer a veto

**Branch:** `m5-11-octave-by-density`, from `main` after M5-10's merge (both touch `assemble.py`). **Agent:**
`sc-builder`, then `sc-reviewer`. May push its branch to run CI. **Files:** `songcharter/assemble.py` (`grid_octave` and
its constants), `tests/test_assemble.py`, `eval/stress.json` (one entry), `eval/baseline/stress/` (the new baseline),
`docs/DESIGN.md` 2.3, `docs/work-orders/M5-99-later.md`. **Time budget:** half a day, the runs included.

*Written by the orchestrator on 2026-11-06 from a fourth stress song the owner added overnight.*

## Why

M5-01 doubles the grid when two tests agree: the onsets are too dense for the first grid's 1/16 (`OCTAVE_SHARE` 0.35
on the pooled share of short intervals) and the snare sits between the beat lines (`BACKBEAT_MIN` 0.34). Both
thresholds were set from one song that needs doubling (the 198 BPM power-metal stress song). A second one, a 7:20
200 BPM power-metal song with five human charts (`pm2`, the owner's audio; titles and md5s in the owner's local list),
is charted at 100 BPM by today's main: its pooled share is 0.527 (doubling indicated) but its backbeat ratio is 0.19,
under 0.34, so the backbeat test vetoes it. The guitar then lands about 70 ms off the human charts' notes, F1@50
0.65-0.68 against human charts that agree at 0.92-0.97 (the owner's v0.1 4-take GPU chart: 0.61-0.64, 34 % chords).
Across the eleven songs measured, density separates the two that need doubling (0.527, 0.623) from the nine that do
not (0.001-0.199) with a margin over 2.6x; the backbeat ratio does not (0.19 against the right grids' 0.001-0.172).

## What to build

1. `grid_octave`: the octave is 2 when the pooled share is at least `OCTAVE_SHARE` and the guard holds, as today; the
   backbeat ratio is computed and recorded in `octave_stats` (and the report) but no longer decides. `OCTAVE_SHARE`
   stays 0.35 unless the table says otherwise (the geometric midpoint of 0.199 and 0.527 is 0.32: say which you keep
   and why). The guard (`OCTAVE_EVIDENCE_MIN` 0.7, provisional) stays.
2. Tests: the pm2-like case (dense onsets, snare on the beat lines) doubles; a right-grid dense song under the share
   stays; the backbeat no longer vetoes (the break restoring the veto fails a test); the recorded ratio.
3. `eval/stress.json`: add `pm2` (a generic slot, as the others; its md5s in the owner's local list
   `$EVAL_DATA/stress.local.json`, never committed), so the stress set has four songs; the new baseline in
   `eval/baseline/stress/` from main at this branch's merge base, scrubbed as M5-09's was.

## Evaluation

- **Golden** (`--expect none`): no reference's pooled share reaches 0.35 (the largest is Lucretia's 0.1985), so every
  grid and chart must stay byte-identical.
- **The stress set**, against a stress run of the merge base: troop, sooth and break unchanged (troop already doubles,
  sooth 0.062 and break 0.151 stay on octave 1); pm2 doubles, and passes M5-01's lines measured against the merge
  base's pm2 run: grid 190-206 BPM, octave 2; guitar F1@50 at least the base's plus 0.10 against each human chart;
  matched guitar notes' median timing error under 15 ms; chord share under 0.10; bass and drums F1@50 not below the
  base's; plain beat F1 at least 0.80. Report the downbeat F1, star power per minute and the solo spans beside the
  humans'.
- If pm2 doubles but fails a line (the beat phase, the bass), stop and report the numbers: don't tune further.

## Done means

- [dev] The suite; the new tests fail when their code is broken; the golden diff exit 0; the stress table before and
  after with every line.
- [CI] Green on the branch.
- [docs] DESIGN 2.3 (the decision by density, the eleven-song table, the backbeat recorded), M5-99 (the thresholds
  still rest on two songs that need doubling: the 20-song set).

## Limits

- No change to the second pass, the half-beat test, the quantizer or the guard. Human charts only through `score.py`
  and `stress.py` (numbers); two of pm2's packages carry vocal tracks: timing scripts only, never opened.

## Report

`<scratchpad>/briefs/m5-11.report.md`: the commits, the table, the golden verdict, the stress table before and after,
anything uncertain.
