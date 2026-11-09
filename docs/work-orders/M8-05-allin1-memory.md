# M8-05: allin1 on a long song: the fallback said, the memory bounded

**Partly conditional.** Parts 1 and 2 are built in any case; part 3 only if M8-03 part A's numbers clear its bar
(below); part 4 only if part 3 is not built. **Branch:** `m8-05-allin1-memory`, from `main` after the reset, when
M8-03 part A has reported (wave 1, beside M8-04). **Agent:** `sc-builder`, then `sc-reviewer`. May push its branch to
run CI. **Files:** `songcharter/engines/sections.py`, `songcharter/engines/allin1_runner.py`, `songcharter/pipeline.py`
(the sections stage and its events only), `songcharter/device.py` (doctor's memory note), their tests
(`tests/test_engines_sections.py`, `tests/test_pipeline.py`, `tests/test_device.py`), `docs/DESIGN.md` 2.5 and 4.7.
**Not:** `songcharter/ui/` (the page shows a `fallback` event as a banner already: `app.js`), `docs/guide/` (M8-04's in
this wave; the guide's line, if one is needed, goes to the orchestrator for the merge), `wslsetup.py`'s memory rule
(unchanged: allin1 stays out under 11 GB). **Time budget:** a day. **Rough cost:** 3-5 % of a week's meter.

**Environment:** eval/README.md's step 9, and `SONGCHARTER_HEAVY_MIN_FREE_GB=1` on every heavy job (the suite, the
golden, stress and 20-song runs, builds): about 1.7 GB is free on `/`, `tools/heavy.sh` refuses under 5 GB without
it, and `python -m eval.golden run` takes the lock but not the disk check.

*Written by the M8 planner on 2026-11-08 from the v0.4.0 gate's note (PROGRESS `deferred`: allin1 killed for memory on
a 9-minute song, the sections fell back to librosa with only a warning) and the planner's reading of the records
(M8-00 section 6).*

## M8-03's numbers (part A, docs/reports/M8-03-measure-cpu.md)

allin1's child peak on the CPU = 354 MB + 17.44 MB a second (residuals −233 / +202 MB, 24 songs; MB as MiB here);
the tree while allin1 runs, today = 853 MB + 20.4 MB a second (two points: creep and the test song, A-b). A-b: freeing
the mix, the six stems and the int16 payload while allin1 runs saves 0.158 GiB a minute (1.42 GiB at 9:00); reloading
them from the work folder costs 1.1–1.3 s, so **part 3 (b) is built** (tree 853 + 17.7 MB a second). A-c: no window W
of 120, 180 or 240 s met the chunk bar, and chunking does not lower the child's peak (madmom's DBN decoder on the whole
song holds it), so **parts 3 (a) and 3 (c) are not built** and **part 4 is**. A-d: with a reserve of 1 GiB a 10.2 GiB
tree (WSL's 11 GB) fits about 8.1 minutes with the arrays freed, 11.2 GiB (a 16 GB PC's 12 GB) about 9.0 (M8-03's figures, with the reserve alone); the skip's
reserve is the line's largest residual plus 1 GiB (so 7:52 and 8:50). The skip compares with `MemTotal` only (the orchestrator's
decision at the build: swap is not counted, as allin1 deep in swap was never measured and could run for hours, worse than the librosa fallback), so a 16 GB PC's WSL 12 GB fits about 9 minutes with
the arrays freed (8:50 for 11.2 GiB, 9:19 for the 11.7 GiB such a WSL reports; doctor names its PC's figure). Golden, stress and 20-song compares expect no change (`--expect
none`): freeing arrays must not change a chart, and the skip does not fire on the dev machine's 15.7 GiB for the sets'
longest song (9:43).

## Why

allin1's peak on the CPU grows by about 1.0 GiB a minute of audio (0.35 GiB + 17.4 MB a second, 24 songs), and while
it runs the pipeline holds the mix and six stems, so the tree passes 11.2 GiB (a 16 GB PC's 12 GB of WSL) from about 7
minutes of audio, on the CPU and, on the host side, on CUDA too (M8-00 section 6). When allin1 is killed, the chart
loses the halving test and allin1's downbeats, and the page shows one line among the warnings. The friend's CPU
fallback on a long song is the likeliest case.

## What to do

1. **The fallback said** (any case): when the sections fall back to librosa for any reason but `backend librosa`
   asked for (allin1 failed, timed out, was killed, or was left out by the memory rule), the pipeline sends a
   `fallback` event for the sections stage, which the page shows as a banner: what ran instead and what it costs
   ("the bar lines and the tempo's halving test come from a simpler analysis: on a slow or fast song the chart may
   sit at double or half the tempo; the sections have plainer names"; the builder's words, short). `report.json`
   and `pipeline.json` record it as the other fallbacks are recorded.
2. **A kill named** (any case): allin1's runner ended by SIGKILL (returncode -9) is reported as "allin1 was stopped,
   most likely for memory (a song of M:SS needs about X GiB for it on the CPU)", X from M8-03 A-a's line, in the
   warning, the banner and `engine.json`'s `why`; any other failure keeps its message.
3. **The memory bounded** (if M8-03 A clears; the numbers go into this order before it starts):
   - **(a) Chunks:** a song longer than L seconds (M8-03 A-d's) is analysed in windows of W seconds overlapping by
     30 s (A-c's smallest W that cleared), their frame outputs stitched by the linear crossfade A-c measured, then
     allin1's own postprocessing on the whole; on the CPU and on CUDA alike, so a song charts the same on every PC.
     The rule reads the song's length only, never the free memory (CLAUDE.md: deterministic). `engine.json` records
     the windows; the sections' cache key gains the chunk settings (a song under L keeps its key and its cached
     result).
   - **(b) The parent's arrays:** if A-b showed at least 1 GiB saved for a 9-minute song at a reload cost under 10 s,
     the pipeline frees the arrays it does not need while allin1 runs and reads them again from the work folder
     after; byte-identical later stages (the test proves it on a short song).
   - **(c) The CUDA out-of-memory path:** the runner's fallback from a CUDA out-of-memory to the CPU (`run`) uses the
     same chunk rule on the CPU.
4. **If part 3 (a) is not built** (chunks miss their bar): before allin1 runs on the CPU, the predicted tree (A-a's
   line plus the parent's, with the line's largest residual as margin) is compared with WSL's configured memory and
   swap (`MemTotal` and `SwapTotal`, fixed per PC; never `MemAvailable`, which changes from run to run); when it
   cannot fit, allin1 is skipped at once with part 1's banner and part 2's sentence, instead of being killed minutes
   later. doctor's memory note names the longest song this PC charts with allin1, and the report says the
   consequence plainly for the owner and the guide: a 16 GB PC charts songs over about 7 minutes without allin1
   (the advisor's finding 10).
5. DESIGN 2.5 (the sections: the fallback, the chunks or the skip, with M8-03's numbers) and 4.7.

## Bar (M8-03 part A)

Part 3 (a): M8-03 A's chunk bar (every song: beat F1 0.99, downbeat F1 0.98 against the whole run, bpm within 1 %,
segment starts F1 at 1 s 0.95 pooled and 0.90 per song, the grid's octave identical and its beat F1 against the humans
within 0.005). Part 3 (b): the saving and cost above.

## Evaluation

- **Golden** `--expect sections` only for the songs longer than L (with L above 7 minutes, none of the six references
  and not the test song); every other song identical (sections included: compare `sections` in report.json by hand,
  as golden does not).
- **Stress and 20-song sets:** 0 regressions; sooth, pm2 and the 20-song songs over L charted with chunks: their beat
  and downbeat F1 against the humans within 0.005 of the base's, their grid octave identical.
- **The kill path:** a test with a stand-in runner that dies by SIGKILL (part 2's sentence, part 1's banner, the
  librosa sections); a test that a song just under and just over L takes the whole and the chunked path; a test of the
  stitch on made-up frame outputs (a step across an overlap lands where the whole would put it).
- **Memory:** one real chunked run of the longest kept song (9:43) on this machine through `tools/heavy.sh`, its
  allin1 peak and the tree's (VmHWM, sampled) against M8-03's prediction for W.

## Done means

- [dev] The suite; each new test fails on its break (the builder breaks each).
- [CI] Green on the branch.
- [dev] Golden, stress and 20-song compares as above; the long song's peak in the report.
- [docs] DESIGN 2.5 and 4.7; a guide line for the orchestrator if the friend's long songs need one.

## Report

`<scratchpad>/m8/m8-05.report.md`: the commits, which of parts 3 and 4 were built and why, the compares, the peak.
