# M7-04: notes the stem does not support: onsets in silence, repeats with no attack

**Conditional on M7-01 parts B-a and A-d** (below, Bar): build each half only if its candidate cleared its bar; with
neither, the order is closed and its numbers go to `dead_ends`. **Branch:** `m7-04-stem-evidence`, from `main` after
M7-02's merge (both touch assemble.py and quantize.py). **Agent:** `sc-builder`, then `sc-reviewer`. May push its
branch to run CI. **Files:** `songcharter/assemble.py` (the stem stage, beside `trim_silent_edges`), a new
`songcharter/stemcheck.py` if the onset strength needs a home, `songcharter/quantize.py` only for a gap-only repeat
rule, `eval/scorer/score.py` (the repeat share, if the bar reads it), their tests, `docs/DESIGN.md` 2.0 (Silence),
2.6, 2.8 and 9 (Q23). **Time budget:** a day. **Rough cost:** 3-4 % of a week's meter.

*Written by the M7 planner on 2026-11-07 from the video review's findings 4 and 6 (M7-00 section 1) and M7-01's
plan.*

## Why

Onsets inside the song where the part's stem is silent are only warned about (DESIGN 2.0, Q23 open): sooth's guitar
has 160 (the review counts 47 in its quiet intro, and phantom drum hits in a drumless stretch). And the engine writes
a held, bent or vibrato note as same-fret repeats with no sustain (sooth 362 single-note repeats, 0.15 of its notes;
40 of 105 notes in one drumless solo section). A quiet real part (a clean intro under a loud song) and real tremolo
picking look the same to a careless rule, so each rule is judged by the human notes it would remove.

## What to do

1. **Silence** (if B-a's candidate cleared): after the edge trim, remove each Expert onset the candidate names (every
   silent onset, or only those inside a stretch of at least 1 s of a silent stem, at the floor D in dB B-a picked),
   per part as B-a cleared it (guitar, bass, drums apart); the lower levels follow (they are reduced from Expert);
   `trim_silence: false` turns it off with the edges. `report.json` lists the removed onsets (count and the first 50
   times) where it now lists `silent_onsets`, which stays for what is left.
2. **Repeats** (if A-d's candidate cleared): a same-fret single-note repeat the candidate names (a gap of at least G
   ms, and with rule (b) the guitar stem's onset strength under the song's p-th percentile at it) merges into the
   previous note's sustain, before the sustain floor; counted in `report.json`.
3. Tests with made-up stems and notes: a note in a silent stretch removed and one in a quiet but present part kept;
   a repeat on a held tone merged and a picked repeat kept; each failing on its break.

## Bar (M7-01's numbers, then the branch's own runs)

- **Silence:** removal precision at least 0.80 pooled (the removed onsets no human chart has within 50 ms); the
  human notes the rule would remove under 0.5 % of each part's notes on every song (not pooled); F1@50 not lower on
  any song by more than 0.005.
- **Repeats:** removal precision at least 0.75 pooled; guitar F1@50 pooled not lower, no song down by more than
  0.005; the repeat share nearer the humans'.

## Evaluation

- **Golden** against `main`, `--rerun drums,bass,sections` both sides, `--expect` the parts that lose notes.
- **Stress and 20-song sets:** `stress.py compare` "Regressions: 0" on both; notes in silence and the repeat share in
  the feel report beside the humans'.

## Done means

- [dev] The suite; the new tests fail when their code is broken; the golden diff exit 0; the compares; the bar's
  table from the branch's runs.
- [CI] Green on the branch.
- [docs] DESIGN 2.0 and 2.8 (the rule, the numbers), Q23 answered in §9, 2.6 for the repeats.

## Report

`<scratchpad>/m7/m7-04.report.md`: the commits, the halves built and not (with their numbers), the tables, the
checks.
