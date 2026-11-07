# M7-03: the bass on one fret: onsets on a held note, or the lane map

**Conditional on M7-01 part B-b** (below, Bar): build the candidate the measured cause points to and that cleared its
bar; with none, the order is closed and its numbers go to `dead_ends`. **Branch:** `m7-03-bass`, from `main` after
M7-01's report is committed. **Agent:** `sc-builder`, then `sc-reviewer`. May push its branch to run CI. **Files:**
`songcharter/engines/bass.py` (and its rules' version in the engine's cache key), their tests (not
`eval/scorer/score.py`: M7-02 adds the bass's two measures there, the same-lane repeat share and the lane spread;
until M7-02 merges, this order reads its bar with M7-01's script), `docs/DESIGN.md` 2.8. Nothing else.
**Time budget:** a day and a half. **Rough cost:** 4-6 % of a week's meter.

*Written by the M7 planner on 2026-11-07 from the video review's finding 5 (M7-00 section 1) and M7-01's plan.*

## Why

On the owner's charts the bass repeats one lane: sooth 1,759 of 2,368 notes (0.74), tod 360 of 652 (0.55). The bass
is our rule engine (DESIGN 2.8: HFC onsets, pYIN pitch, the rank map in 12-note windows, "a repeated pitch keeps its
lane"). Two causes are possible and M7-01 measures which: onsets on a held note (an onset envelope firing on a drone:
the same pitch, the note still sounding), or the map keeping a pitch change on one lane. The humans repeat lanes too
(one reference repeats the lane on 84.5 % of its pairs, DESIGN 2.8), so the target is their share, not none; and our
bass over-charts several songs (sooth 1.27 times its primary's notes; one 20-song song 1.78) [here: the stress and
20-song scores].

## What to do

1. The candidate M7-01's B-b picked:
   - **(a) the held-note gate:** an onset whose pitch equals the previous note's while the pitch track stays voiced on
     it through the onset is dropped unless its HFC rise is in the song's top X % (X from B-b), before the lanes are
     mapped; counted in `engine.json`;
   - **(b) the map:** a pitch change of a semitone or more changes the lane wherever the window's lanes allow.
   The rules' version in the engine's key moves, so every song's bass reruns once.
2. The measure the bar reads, in score.py's feel measures if it lacks it (same-lane repeat share, the largest
   lane's share), with a test.
3. Tests with made-up stems (a held tone with tremolo, a picked repeated note, a scale on few pitches): the gate keeps
   picked repeats and drops the drone's; the map changes lanes; each failing on its break.

## Bar (M7-01 B-b's numbers, then the branch's own runs)

- (a): removal precision at least 0.75 (the share of dropped onsets no human chart has within 50 ms), bass F1@50
  pooled +0.005 with its CI above 0, no song down by more than 0.01, the repeat share toward the humans'.
- (b): contour (`lane_direction_agreement`) +0.02 pooled, F1 unchanged, the repeat share toward the humans'.
- No reference's bass F1@50 down by more than 0.01 (the engine was tuned on them): otherwise stop and report.

## Evaluation

- **Golden** against `main`, `--rerun drums,bass,sections` both sides, `--expect bass`.
- **Stress and 20-song sets**, `--rerun bass` both runs: `stress.py compare` "Regressions: 0" on both; the bass's
  feel lines beside the humans'.

## Done means

- [dev] The suite; the new tests fail when their code is broken; the golden diff exit 0; the compares; the bar's
  table from the branch's runs.
- [CI] Green on the branch.
- [docs] DESIGN 2.8 (the rule and its numbers).

## Report

`<scratchpad>/m7/m7-03.report.md`: the commits, the candidate and its numbers, the tables, the checks.
