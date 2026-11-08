# M8-07: the GPU chart's guitar rules (HOPO and strum flags, the sustain floor, open notes, repeats and contour)

**Conditional on M8-02 part C, per part:** each of (a)-(d) is built only if its candidate cleared its bar in M8-02;
with none clearing, the order is closed and the numbers go to `dead_ends`. If (d)'s re-lane clears beside one of
(a)-(c), the orchestrator may split it into M8-07b, built in the same slot after M8-07 merges (it adds a module).
**Branch:** `m8-07-gpu-guitar`, from `main` after M8-02's report is committed (wave 3, beside M8-06). **Agent:**
`sc-builder`, then `sc-reviewer`. May push its branch to run CI. **Files:** `songcharter/quantize.py` (the sustain
floor), `songcharter/assemble.py` (the guitar part's HOPO, open and repeat rules and its part config keys),
`songcharter/pipeline.py` (the guitar part's config only), for (d)'s re-lane a new `songcharter/contour.py`, their tests
(`tests/test_quantize.py`, `tests/test_assemble.py`, `tests/test_pipeline.py`, a new `tests/test_contour.py`), score.py's
feel measures where a bar's measure is missing (`eval/scorer/score.py`, with a test), `docs/DESIGN.md` 2.6 and 2.7
(Chords, HOPOs, opens and sustains). **Not:** `takes.py` (M8-06's), `engines/`, `starpower.py`. **Time budget:** half a
day per part built, 1 day for (d)'s re-lane; at most 2.5 days. **Rough cost:** 3-7 % of a week's meter.

**Environment:** eval/README.md's step 9, and `SONGCHARTER_HEAVY_MIN_FREE_GB=1` on every heavy job (the suite, the
golden, stress and 20-song runs, builds): about 1.7 GB is free on `/`, `tools/heavy.sh` refuses under 5 GB without
it, and `python -m eval.golden run` takes the lock but not the disk check.

*Written by the M8 planner on 2026-11-08 from M7-01 part A (A-a to A-e), the contour spike and its torchcrepe
addendum, and M8-02 part C's plan.*

## Why

On CPU takes no HOPO mode, sustain floor, repeat rule or pitch tracker beat today's rules against the humans. The
friend's charts are GPU charts, and those differ: the GPU takes write open notes the CPU takes do not, and pm2's GPU
chart repeats a fret 86 % of the time (the video review's count) where the CPU chart's fast runs repeat 0.29, as the
humans do (M8-00 section 1). M8-02 part C re-measures each question on the owner's GPU takes; this order builds what
cleared there.

## What to do (each part only if it cleared; the orchestrator writes the cleared candidate and its numbers here first)

- **(a) HOPO and strum from the engine's flags:** the winning rule of M8-02 C-a: the guitar part's `hopo` mode
  ("source" or "natural" in `pipeline.py`'s guitar part), or R1 (by the grid's octave) or R2 (no forced strum in a fast
  run) as a new `hopo` value in assemble's `HOPO_RULES`; the taps' T2 rule kept on top. `report.json` records the
  rule.
- **(b) The sustain floor in seconds, the guitar only:** `quantize.sustain_kept`'s floor `max(200 ms, min(0.75 beat,
  cap))` for Expert and Hard at the cap that cleared (300, 400 or 500 ms), for the guitar part alone (a part config
  key the guitar part sets; the bass keeps today's floor: it is our CPU rule engine on both devices, and M7-01 A-c
  measured its floor inside noise, 300 ms +0.016 [-0.019, +0.047]; the advisor's finding 1).
- **(c) Open notes:** the winning rule of C-d as the guitar part's `opens` key in assemble ("keep", today; "green";
  "neighbour", the lane of the nearest fretted note before it, else after it; "runs", kept only in a run of 3 or more
  opens, the others as "neighbour"), applied on Expert before the reductions (the lower levels follow from Expert as
  today), the chord rules unchanged (an open never in a chord). If fewer than 8 songs had GPU opens in M8-02 (its
  small-sample bar), (c) is built for GPU charts only, as a trial the owner may veto at the gate.
- **(d) Same-fret repeats and the fast runs' contour:** either C-e's removal rule (a repeat merged into the note
  before it as a sustain, by gap and stem test, as M7-01 A-d defined it), or C-f's re-lane: in a fast run, a
  same-fret repeat where the guitar stem's pitch (pYIN, as the spike ran it) steps a semitone or more moves one lane
  in the step's direction, clamped to the lanes, chords untouched (`contour.py`, called by assemble on Expert after
  the splice and before the quantizer's chord rules). pYIN's settings are the spike's (`eval/m8/contour/pitch.py`).
- **The device:** a part whose CPU arm (M8-02's, the same rule on the tag's CPU arms) dropped the order's floor on any
  song applies to GPU charts only. The rule follows the chart's configured guitar device (the device
  `pipeline.guitar_takes` was given, "cuda" or "cpu"), passed to the part's config and recorded in `report.json` as
  `rules_device`, never per take: a take that `cpu_retry` ran again on the CPU inside a CUDA chart keeps the chart's
  CUDA rule (the advisor's finding 6). Otherwise one rule for both.

## Bars (M8-02 part C; each re-measured on the branch)

| part | bar on the GPU charts (M8-02's `m05` arm rebuilt with the branch's code) | the CPU side |
|---|---|---|
| (a) | state agreement +0.02 pooled at 100 ms, CI above 0, no song down 0.03; tap precision not lower | not lower by 0.005 pooled, no song down 0.03, or GPU only |
| (b) | sustain agreement +0.03 on the slow songs, no song down 0.01 | the same floor, or GPU only |
| (c) | 8 or more songs with GPU opens: exact-lane +0.005 pooled, CI above 0; contour's CI lower end above -0.002; no song's exact-lane down 0.01. Fewer: +0.005 pooled, no song's exact-lane down, contour not lower on any song, and GPU only as a trial | not lower (the CPU charts have few opens: 0.007) |
| (d) removal | precision 0.75; no song's F1@50 down 0.005; human notes removed under 0.5 % on every song | the same |
| (d) re-lane | fast-run direction agreement +0.10 pooled, CI above 0, 3 songs up 0.10; score.py's contour and exact lanes not lower | not lower, or GPU only |

Each within 0.01 of what M8-02 reported for it; the humans' own agreement beside each in the report.

## Evaluation

- **Golden** `--expect guitar` (and `bass` if (b) reaches it); onsets identical unless (d)'s removal is built (then
  `--expect` its F1 change); the references' pooled F1@50 not lower by more than 0.002.
- **Stress and 20-song sets:** 0 regressions; the feel report read (articulation, sustains, the shape).
- **The GPU arms:** M8-02's scripts on the branch, the takes as files (no GPU).
- Determinism: a chart built twice on the branch is byte-identical (pYIN included).

## Done means

- [dev] The suite; each new test fails on its break; the bars re-measured as above.
- [CI] Green on the branch.
- [docs] DESIGN 2.6 and 2.7: each built rule with its numbers on GPU and CPU charts, and its device.

## Report

`<scratchpad>/m8/m8-07.report.md`: the parts built and why, the commits, the re-measured bars, the compares.
