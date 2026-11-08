# M8-02: the GPU takes, measured against the human charts

**Agents:** two `sc-measurer`s (a smaller model): **M1** parts A and B, **M2** parts C and D (M2 starts when B has
built the `one` and `m05` GPU arms, about an hour into B). They write only to `<scratchpad>/m8/m8-02/<part>/`, never
to the repository. **No branch.** The orchestrator commits the merged report as `docs/reports/M8-02-measure-gpu.md` and
the scripts the build orders' bars read under `eval/m8/m802/`, after PIPELINE's privacy scan. **Starts** when the
owner's `gpu_results.zip` (M8-01) has arrived and passed the intake (below). **Time budget:** a day of machine time
(about 6-8 hours), each measurer stopping and reporting what it has at 85 % of the weekly meter. **Rough cost:** 5-7 %
of a week's meter.

*Written by the M8 planner on 2026-11-08 from M7-01's report, the M8 spikes (contour, its torchcrepe addendum, the
take score) and M8-01's zip format (eval/README.md, "GPU takes with the installed app").*

## Why

Every M7 measurement used CPU takes; the friend's default is 4 GPU takes, and the owner's GPU charts differ (open
notes, same-fret repeats in fast runs; M8-00 section 1). This order reproduces on GPU takes what M7-01 parts A and C
and the three spikes measured on CPU takes, and says per question whether the GPU changes the answer. The bars are
M8-00 section 4's, fixed before any number.

## The rules of the measurement

- **The code:** a worktree of the **v0.4.0 tag** (`<shm>/m8/code`, detached; never pushed), so wave 1's merges do not
  move the arms; patches only as uncommitted files in it (`eval/m7/C/margin.patch` for the splice arms; part C's floor
  patch as `eval/m7/A/patch_arm.py` writes it). The environment is eval/README.md's step 9 with
  `SONGCHARTER_HEAVY_MIN_FREE_GB=1`; every build and every allin1-free run of more than a minute goes through
  `tools/heavy.sh`, one at a time.
- **The songs** are M7-01's 23 (the six references, troop, sooth, break, pm2, s01-s13). The test song's GPU takes are
  read only for the intake (its input is another encode of the owner's file than the kept folder's: PROGRESS
  `golden.rebuilt_2026_11_05`); it has no human chart.
- **A song's value** is its mean over its human charts unless the bar says the primary; pooled over the songs with the
  part; a paired bootstrap over songs (10,000 resamples, seed fixed) for each difference's 95 % CI; the humans' own
  agreement beside each number; songs whose humans agree under 0.6 on the measure reported and left out of its pooled
  figure, named (guitar F1@50: s02, s04, s06, s12); each pooled figure with and without the references, and over all
  23. Report the CPU's figure beside every GPU figure (M7-01's, or recomputed at the v0.4.0 tag where the tag changed
  it: T2's taps).
- **Privacy:** numbers only. Never print, save or report a lyric, a chart's events or text, a title, an artist, a
  charter, an md5 or a 20-song id; the 20-song songs are s01-s13 (ids sorted, mapped in process as
  `eval/m7/C/songs.py` does). Vocal tracks and lyric events are never read. Process listings cut to 80 characters.
  Round floats to 3 decimals in anything kept (a 4-decimal F1 can look like an md5 prefix to privacy_check).
- **Disk** (about 1.7 GB free on `/`): the zip and its unpacked takes in `<scratchpad>/m8/m8-02/zip` (about 0.1 GB);
  every arm built into `/dev/shm/m8/arms/<arm>/<label>` and deleted once scored, keeping its scores and the splice
  report's windows (a few MB in all) and the `notes.chart` of the `one` and `m05` GPU arms (about 15 MB); never more
  than 1 GB in `/dev/shm`. Refuse to start a job with under 0.5 GB free on `/`; `df -h /` in the report.

## Intake (M1, first; about 30 minutes)

1. The zip passes `python3 -I packaging/ci/check_no_audio.py` on it, then is unpacked into `<scratchpad>/m8/m8-02/zip`
   (an empty folder of its own; run nothing from inside it; read its JSON with `python3 -I`).
2. `takes/set20/set.json` (label, slot, charts, length) equals the dev machine's 20-song set computed the same way
   (`$DEV/eval-set20`, ids sorted, in process): if a label's slot, chart count or length differs, the labels have
   shifted on his PC: stop and report (no id printed).
3. Per take: `take.json`'s `inputSha256` against the SHA-256 of the dev machine's `input.wav` for that label
   (`$DEV/eval/refs/<id>`, `$DEV/eval/stress/<id>`, `$DEV/eval-set20/stress/<id>`); `summary.json`'s transcriber device
   `cuda`; the seed; whether the take was cut short and continued. `takes/takes.jsonl`: made, cached or failed. A song
   with a mismatched input, a CPU transcriber, or fewer than four takes is listed and left out of the 4-take arms
   (its takes still count in part A).
4. The table: per label, the four seeds' status, onsets, tokens, beats, device, cut short; the GPU's take times
   (from summary.json) against the song's length, for the page's estimate (DESIGN 4.5's GPU rates are the 5070's).

## Part A (M1): the takes' shape, GPU against CPU (no build; about 30 minutes)

Per take, read with `eval/scorer/score.py`'s `scan` (Expert guitar, notes only), and per song as the mean of its four
takes, the GPU's and the CPU's (the kept take and `$SONGCHARTER_GOLDEN/m7-takes`' 101, 202, 303), each beside the
humans' (mean and range over the song's charts):
- Expert onsets, and their ratio to the primary's; the chord share; the open share and the longest run of opens;
- the same-fret repeat share (a single note whose previous onset is a single note on the same lane), whole song and in
  fast runs (8 or more onsets each at most 125 ms apart: M7-01's definition);
- the sustain share; the engine's forced-HOPO and forced-strum shares and its tap share (from the flags as the take
  wrote them);
- the 1-s peak density and the share of the song in fast runs.
Then the paired difference GPU minus CPU per song with its CI, pooled. This says how the GPU's takes differ before any
rule reads them.

## Part B (M1): the splice and the take selector (builds; about 4 hours)

**The arms are built by `songcharter assemble <config> --out <folder>`**, which writes only that folder, from the
config v0.4.0's pipeline writes for a 4-take chart:
1. Per song, once: M7-01 part C's route at the v0.4.0 tag (`cp -al` of the kept folder to
   `$SONGCHARTER_GOLDEN/m8-copy/<label>`, every file under 5 MB replaced by a real copy, the three CPU takes of
   `m7-takes` hard-linked in as `guitar/seed_<seed>/`, then `songcharter chart <input.wav> --out
   /dev/shm/m8/arms/cpu_m05/<label> --work <copy> --takes 4 --device cpu --no-preview --threads 2`). That is the **CPU
   m05 arm at the tag**; keep the `assemble.json` it wrote (its paths rewritten from the copy to the kept folder) and
   delete the copy. A listing of the kept folder (path, size, mtime, inode) before and after each song is identical.
2. **The check of the route:** that `assemble.json` built by `songcharter assemble` gives a guitar track identical,
   note for note (tick, type, length, flags), to step 1's chart. If not, stop and report.
3. **The GPU arms:** the same config with the guitar part's `source` the GPU take 20260609's `notes.chart` and `takes`
   the GPU takes 101, 202, 303 (that order); the splice arms through `margin.patch`'s variables:
   - `one`: the GPU take 20260609 alone (no `takes`): the GPU chart with `--takes 1`;
   - `m0`, `m02`, `m05` (today), `m10`: `SC_M7_MARGIN` 0, 0.02, 0.05, 0.10; an arm whose picks equal a built arm's is
     not rebuilt (listed `same_as`; assert the picks equal the computed ones), as part C did;
   - `f0`-`f3` (the oracle, reported only): every window from take 1, 2, 3 or 4 (`SC_M7_FORCE`);
   - `q05`: the silent-onset take score at 0.05 (`SC_M7_SILENT`);
   - the CPU's `one` at the tag (the kept take alone), for the GPU-against-CPU line.
   Scoring as part C did: `eval/stress.py`'s `run_score` against the primary and every alt with guitar notes.
4. **The take scores of the spike** (`eval/m8/takescore/`, in process on the GPU arms' per-window onsets): a (today's
   agreement), b2 (the stem's onset evidence, the song's lag removed), c (q's score), d2 (a/b2 blend), e (the take
   with more onsets when 50 % or 70 % of its extra onsets have stem evidence), at margins 0, 0.02 and 0.05; the
   oracle window and the best take per song.
5. **Two new candidates, each scored only on songs it was not fitted on** (leave one song out: fit on the other 22,
   pick on the held-out song's windows; features and the model's form fixed before the first fit, written in the
   report first):
   - **L1, a learned window score:** a pairwise logistic model over each take's per-window features: today's
     agreement, b2's precision and recall, the take's onsets over the four takes' median, its silent share, its chord,
     open and same-fret repeat shares, and the density term below; the target, which of two takes scores the higher
     F1@50 against the song's charts (mean over charts) in the window; a take replaces take 0 when the model gives it
     a probability over p (0.5, 0.6, 0.7) against take 0.
   - **D1, the humans' density pattern:** each window's onsets a second predicted from the guitar stem's onset rate
     (librosa's `onset_strength` peaks, as b2 reads them) by a ratio fit on the other songs' human charts; the take
     nearest that density is picked, take 0 kept unless another is nearer by more than 10 %.
   Report each one's picks on the CPU takes too (`m7-takes`), with the model fit on GPU windows: the friend's CPU
   lane runs 1 take, so this only says whether `--takes 4` on a CPU would suffer.

**Reported:** per song and pooled, F1@50 and F1@100 against the primary and the mean over charts for every arm and
candidate; each minus `m05` (the GPU's today) and `m05` minus `one`, with CIs; the windows switched and the windows
picked more than 0.05 below the best take; the oracle window's headroom on GPU takes against the CPU's +0.042.

**Bars** (M8-00 section 4): a margin, a spike score, q05, L1 or D1 clears M8-06's bar when its pooled primary F1@50 is
+0.005 or more over `m05`, CI above 0, no song down by more than 0.01 (L1 and D1 on held-out songs only). **The 4-take
default:** if `m05` minus `one` is under +0.005 pooled, say so plainly (M8-00 section 10, the owner's decision 4a).

## Part C (M2): articulation, opens, repeats and the contour on the GPU charts (about 2-3 hours)

On the `m05` GPU arm (the friend's default chart), with the CPU's numbers beside each (M7-01 part A's, the taps at the
tag's T2):
- **C-a, the HOPO rule** (M7-01 A-a): the state agreement under the guitar part's `hopo` "forced" (today), "source"
  and "natural" (built: the config's `hopo` key, no patch), and R1 (the octave rule) and R2 (no forced strums in fast
  runs) computed per note; the confusion of states by the engine's flag (forced strum, forced HOPO, unforced, tap)
  against each human chart. Our onsets must be identical across these arms: assert it.
- **C-b, taps** (A-b): today's T2 on GPU charts: our tap share, precision and recall against the humans', and T1 (no
  taps) beside it.
- **C-c, sustains** (A-c): the sustain share and the per-note sustain agreement under today's floor and the caps 300,
  400 and 500 ms (`quantize.sustain_kept`'s floor `max(200 ms, min(0.75 beat, cap))`, built through the floor patch),
  the slow songs (grid under 100 BPM: creep, lucretia, sooth, s02, s04, s13) apart; the share of the humans' sustains
  each floor would drop.
- **C-d, open notes** (A-e): our open share and longest run against each chart's; our opens' precision (a human open
  within 50 ms) and recall; the exact-lane and contour agreement at 100 ms under o0 (today, the opens kept), o1 (every
  open to green), o2 (every open to the lane of the nearest fretted note before it, else after it), o3 (an open kept
  only in a run of 3 or more opens, the others as o2); per song and pooled over the songs where our GPU charts have
  opens.
- **C-e, same-fret repeats** (A-d): the repeat share whole song and in fast runs, ours and the humans'; our repeats'
  match rate at 50 ms against our other notes'; the removal rules gap150/200/250, with and without the stem test at
  p25 and p50: removed, precision, the F1@50 change, the human notes removed per song.
- **C-f, the fast runs' contour** (the contour spike, `eval/m8/contour/` on the GPU arm): on fast-run pairs matched to
  consecutive human notes, the direction agreement of ours, pYIN, pYIN where it steps a semitone or more
  (`pyin_step1`), and the CQT variants; the re-lane by each (one lane per step, clamped) with score.py's whole-song
  contour and exact lanes before and after. torchcrepe's tiny model only if `pyin_step1` misses and the owner's
  allowance for the spike's throwaway install (outside the shared venv, in memory, deleted after) still stands; else
  not run, and said.

**Bars** (M8-00 section 4): C-a's best rule clears M8-07 (a) at +0.02 pooled state agreement, CI above 0, no song down
0.03, tap precision not lower; C-c's best cap clears (b) at +0.03 on the slow songs, no song down 0.01; C-d's best
clears (c) at exact-lane +0.005 pooled with CI above 0, contour's CI lower end above -0.002, no song's exact-lane down
0.01; C-e's best removal clears (d) at precision 0.75, no song's F1@50 down 0.005 and human notes removed under 0.5 %
on every song; C-f's best re-lane clears (d) at +0.10 pooled direction agreement, CI above 0, at least 3 songs up
0.10, score.py's contour and exact lanes not lower. For each that clears, also its CPU arm (the same rule on the CPU
m05 and one arms at the tag): its pooled change and its worst song (M8-00 section 4: a device-scoped rule).

## Part D (M2): fast runs' density (about 30 minutes)

Per 30-s window of sooth, pm2, troop and every other song with windows where the humans play 8 or more notes a second:
F1@100 against each chart, the notes ratio, the 1-s peak density, ours (GPU `one`, GPU `m05`, CPU `one`) against the
humans'; the fast windows' pooled recall at 100 ms. **The decision for M8-11:** recommend the thinning spike when the
GPU `m05`'s fast windows' recall at 100 ms is under 0.7 pooled (M5-99 found 47 % of the human notes at 8-12 notes a
second on the owner's 4-take GPU chart of sooth).

## The answer per question

A table in the report's first section: each row of M8-00 section 5, the CPU's answer, the GPU's (the number and its
CI), **changed or not**, and the build order it opens or closes (M8-06, M8-07 a-d, M8-11), so the orchestrator can fill
each order's bar from it.

## Done means

- [dev] `<scratchpad>/m8/m8-02/report.md` with the intake, parts A-D and the answer table; JSON per part (rounded);
  the scripts, each starting with what it reads and prints; `eval/privacy_check.py` on every file kept, 0 found with
  `EVAL_DATA=$DEV/eval` and the 20-song list's hits counted only (`| grep -c .`; the word "tool" is a known false
  positive).
- [dev] The kept folders unchanged (the listings); `/dev/shm/m8` and `$SONGCHARTER_GOLDEN/m8-copy` removed; `df -h /`.

## Report

`<scratchpad>/m8/m8-02/report.md` and a summary of at most 1.5k tokens to the orchestrator: the answer table, the
orders it opens, the 4-take default's number.
