# M8-11: the engine thinning fast runs: M7-08's spike on the owner's GPU, scored here

**Measurement first; optional** [owner]: it needs about 2.5 hours of the owner's GPU, unattended, and is recommended
only if M8-02 part D finds the GPU takes' fast windows thin (recall at 100 ms under 0.7 pooled where the humans play
8 or more notes a second). A setting is adopted in M8 only if an arm clears M5-99's bar **and** the references' arm
(about another hour of his GPU) comes back in time for a wave-3 slot; otherwise the result is recorded for M9.
**Agents:** the owner runs the spike on his PC; an `sc-measurer` scores it here, writing only to
`<scratchpad>/m8/m8-11/`. **Time budget:** two hours here once the zip has arrived. **Rough cost:** about 1 % of a
week's meter (2-3 % more if a setting is built).

**Environment:** eval/README.md's step 9, and `SONGCHARTER_HEAVY_MIN_FREE_GB=1` on every heavy job (the suite, the
golden, stress and 20-song runs, builds): about 1.7 GB is free on `/`, `tools/heavy.sh` refuses under 5 GB without
it, and `python -m eval.golden run` takes the lock but not the disk check.

*Written by the M8 planner on 2026-11-08 from docs/work-orders/M7-08-thin-runs.md (never run in M7), M5-99 ("Fast runs
thinned by the guitar engine") and M8-02 part D's plan.*

## Why

M5-99 found the engine (Fretformer 2) writing too few notes in fast runs: on the owner's 4-take GPU chart of sooth,
peaks of 11 notes a second where both humans reach 17, and 47 % of the human notes found at 8-12 notes a second against
92 % in the slow first two minutes; the quantizer dropped only 30 of 2,485 notes. The engine's settings are the one
lever. M8-02 part D measures the thinness on the GPU takes of every song first, so the owner's GPU time is spent only
if it is still there.

## What the owner runs

As M7-08 says: `eval/gpu.sh thin-spike <his sooth file>` (four arms: `base` T 0.95, `hot` T 1.05, `dense5` and
`dense6`, the density knob "speed" at 5 and 6; four seeds each; CUDA; a patched copy of the driver, the install's own
untouched), then `thin_spike_results.zip` (charts and summaries, no audio). Check first that `eval/gpu.sh thin-spike`
runs on the installed app (`--app`), as `takes` does since M8-01: if it needs the eval tools he no longer has, the
orchestrator has it fixed before asking him (a small eval-only change, no order of its own).

## What the measurer does

M7-08's steps 1-3: each take on the reference's clock (the lag between his file and sooth's reference audio, from his
GPU chart folder scored by `score.py` against the primary, checked on the `base` arm's default seed); each take and
each arm's four takes spliced at today's margin (or M8-06's) on the kept sooth folder, per 30-s window, F1@100 against
both human charts, the fast windows apart; the notes ratio, the 1-s density peak, the chord share beside the humans'.

## Bar (M5-99)

The fast windows' F1@100 +0.10, no window down by more than 0.02; then, for adoption, the references' pooled F1@50
unchanged on his GPU charts with the setting (`eval/gpu.sh thin-spike` per reference's input with `ARMS` set to the
winner and `base`).

## Done means

- [dev] The table per arm (fast windows, other windows, whole song) and the bar's verdict in
  `<scratchpad>/m8/m8-11.report.md`.
- [owner] The decision: adopt the setting after the references' check (an order written then: the driver's patch in
  the install, every take's key changed), or record the dead end.
