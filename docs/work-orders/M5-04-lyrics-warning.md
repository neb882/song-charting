# M5-04: the lyrics "alignment is unsure" warning, calibrated

**Branch:** `m5-04-lyrics-warning`, from `main` after wave 2 (wave 3, beside M5-05). **Agent:** `sc-builder`, then
`sc-reviewer`. May push its branch to run CI. **Files:** `songcharter/engines/lyrics.py` (`confidence` and its
constants), `tests/test_lyrics.py` (or the engine's test file), `songcharter/pipeline.py` only for the one warning
line in `_lyrics_stage` (M5-05 edits the guitar stage of the same file in this wave: a different function; the
orchestrator merges M5-04 first), `docs/DESIGN.md` 2.15. **Time budget:** 1 day.

## The lyrics rule (absolute)

`docs/work-orders/M4-10-lyrics.md`'s rule binds this order: timing only; no word printed, logged, saved, committed or
returned, not in your reply, the report, a test, a commit message or an error. Scripts read the human charts' lyric
events in memory and print numbers. The exception covers the reference packages in `$EVAL_DATA/sng/` and the stress
songs' packages (M5-09 keeps them beside the stress set); the pasted text for a run goes to `pipeline.chart(...,
Options(lyrics=text))` in process, never to a file. A tokenizer or aligner error is printed as its type only.

## Why

On the owner's 198 BPM power-metal song (2026-11-05, timing only, against a human chart with vocals) 93 % of the
chart's 323 words paired with the pasted text's 307, median start error 9 ms, 96 % within 250 ms, no phrase start
more than 500 ms off. The page still warned "the alignment is unsure (median word score 0.214)": `LOW_MEDIAN` is
0.25, set on the six references' vocal stems (medians 0.31-0.89) against their full mixes (0.09-0.18, where the
aligner collapses). A fast, dense vocal scores lower per character while timing well, so the threshold fires on a
good song. The warning is the friend's only sign that his lyrics may be off; a false alarm teaches him to ignore it.

## What to build

1. **The data** (a script of your own under the scratch folder, never committed; numbers only):
   - the six references with lyrics: their words from the packages' lyric events in memory (as M4-10's phase A did),
     each aligned to its separated vocal stem (the separation cache answers) and to its full mix (the collapsed case);
   - the power-metal song: its words from the human chart that has vocals (M5-09's stress set holds the package), its
     stem and its mix;
   - for each run, the alignment's timings against the human chart's (M5-09's `eval/lyrics_timing.py`, or the
     scratch `<S>/troop/scripts/lyrtime.py` until it lands): the share within 250 ms and 50 ms, the median error.
   Ground truth: a run is good when at least 85 % of its paired words are within 250 ms, bad when under 60 %;
   anything between is reported and left out of the choice.
2. **Candidate statistics**, each computed from what `align` already has (the characters' probabilities on the path,
   the word times, the stem):
   - the median word score (today's), its 10th percentile, the share of words under `LOW_SCORE`;
   - the share of words longer than 2 s (a collapsed alignment stretches words over silence);
   - the share of words whose start falls where the vocal stem is quiet: the stem's level over [-0.05, +0.20] s
     around the start stays more than 30 dB under its 95th percentile (assemble's `silent_onsets` rule, on the stem
     `align` is given);
   - the share of lines (phrases) whose words span more than 3 x the median line duration.
3. **The choice:** for each statistic the margin between the worst good run and the best bad run (on a log scale
   for shares); choose the statistic, or the OR of two, with the widest margin; put the threshold at the midpoint.
   The warning must fire on every mix run and on no stem run, the power-metal stem included. Report the full table
   (per song: good/bad, each statistic, the timing shares). If no statistic separates them with a margin of at least
   1.5x, keep the median with its threshold lowered to the midpoint between 0.214 and 0.18 and say so.
4. **The code:** `confidence()` returns the chosen statistic(s) with their values and threshold(s), `low` from them,
   and `why` (one clause naming the statistic and its value, e.g. "median word score 0.12, under 0.17"); the
   pipeline's warning prints `why`. pipeline.json keeps `confidence` with every field (numbers only). The cache key
   is unchanged (the statistics are computed from the cached times and scores; if a new one needs data the cache
   lacks, bump the cache version and say so).
5. **The 50 ms share**, for the record: the references' and the power-metal song's share within 50 ms from step 1
   go into DESIGN 2.15 (M4-10 measured 0.453-0.457 pooled on the references at 50 ms; the humans agree 94 % with
   each other at 50 ms on the power-metal song). Improving it is M5-99's.

## Tests

- `confidence()` on made-up scores and times (made-up words only, "zorp blen"): the chosen statistic computed, `low`
  and `why` right on both sides of the threshold; a run with no scored word is `low` with `why` saying so.
- The pipeline's warning line carries `why` (standins).
- Each test fails when its code is broken (say which break).

## Evaluation

- **Golden:** no `--lyrics` in the golden builds: `--expect none` (the cheap run; nothing in the charting path
  without lyrics changes).
- **The stress set, lyrics:** M5-09's lyrics check on the power-metal song (its text from the human chart in memory,
  the chart built with it, timed against the human chart): at least 90 % within 250 ms and no warning; the same on
  two references (Take Me Out and one Car Seat Headrest song), no warning; the full-mix runs warn.

## Done means

- [dev] The suite; the new tests fail when their code is broken; a scan of the branch's diff, the report and the
  scratch folder finds no word text (say what you ran).
- [dev] The golden diff, exit 0; the lyrics checks above.
- [CI] Green on the branch.
- [docs] DESIGN 2.15: the table, the statistic, the threshold and the 50 ms shares.

## Limits

- No change to the aligner, its windows, the star tokens or the weights: the warning only. No new dependency.
- Nothing that could hold a word is written under the repository or the scratch folder: the built charts go to a
  folder you delete at the end, and the report says so.

## Report

`<scratchpad>/briefs/m5-04.report.md`: the commits, the table of step 1-3 (numbers only), the choice and threshold,
the checks' last lines, the deletion of the built charts, anything uncertain.
