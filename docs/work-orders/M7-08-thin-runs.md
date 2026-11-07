# M7-08: the engine thinning fast runs: the spike on the owner's GPU, scored here

**Measurement only; optional** [owner]: it needs about 2.5 hours of the owner's GPU, unattended. No setting is
adopted in M7 (M7-00 section 6): the result decides whether M8 builds one. **Agents:** the owner runs the spike on his
PC; an `sc-measurer` scores it here, writing only to `<scratchpad>/m7/m7-08/`. **Time budget:** two hours here once
the zip has arrived. **Rough cost:** about 1 % of a week's meter.

*Written by the M7 planner on 2026-11-07 from M5-99 ("Fast runs thinned by the guitar engine") and the video review's
finding 1, whose cause is the engine's (M7-00 sections 1 and 6).*

## Why

On the owner's sooth chart the review counts about 4.9 notes a second in runs the guitar plays at 12-16; the
quantizer dropped 30 of 2,485 notes, so the engine (Fretformer 2) wrote too few. M5-99 measured it on 2026-11-05:
peaks of 11 notes a second where both humans reach 17, 47 % of the human notes found at 8-12 notes a second against
92 % in the slow first two minutes. The engine's settings are the one lever; the spike that measures them is ready
since M6 (`eval/spike/thin_spike.sh`).

## What the owner runs

`eval/gpu.sh thin-spike <his sooth file>` (eval/gpu.sh's header): four arms (`base` T 0.95, `hot` T 1.05, `dense5`
and `dense6`, the density knob "speed" at 5 and 6), four seeds each, on CUDA, from a patched copy of the driver (the
install's own is untouched). He sends `thin_spike_results.zip` (charts and summaries, no audio).

## What the measurer does

1. Puts each take on the reference's clock: the lag between his file and sooth's reference audio from his v0.3.0 GPU
   chart folder scored by `score.py` against the primary (its `alignment`), checked on the `base` arm's default seed
   against that chart's guitar (most onsets within 50 ms).
2. Scores each take, and each arm's four takes spliced at today's margin (or M7-05's) on the kept sooth folder, per
   30-s window (F1@100 against both human charts), the fast windows (the humans at 8 or more notes a second) apart;
   the notes ratio, the 1-s density peak and the chord share beside the humans'.
3. Reports each arm against M5-99's bar: the fast windows' F1@100 +0.10, no window down by 0.02. A winning arm then
   needs the references charted on the GPU with it (another hour of his GPU: `eval/gpu.sh thin-spike` once per
   reference's input.wav with `ARMS` set to that arm and to `base`) before M8 could adopt it, since the setting
   changes every song's density and every take's cache key, and the driver it patches ships with the install.

## Done means

- [dev] The table per arm (fast windows, other windows, whole song), the bar's verdict, in
  `<scratchpad>/m7/m7-08.report.md`.
- [owner] The decision for M8 (adopt the setting after the references' check, or record the dead end).
