# M5-04: the lyrics "alignment is unsure" warning, calibrated (builder's report)

Branch `m5-04-lyrics-warning` (worktree `<wt>/m5-04`), from main at fef103d. The lyrics rule held throughout. No word
of any lyric was printed, logged, saved, committed or returned. The words were read in memory from the packages
(through `eval/stress.py`'s `sng_files` and `eval/lyrics_timing.py`), and the owner's pasted text was read only in
the process that passed it to `pipeline.chart`. Songs are named by their ids below.

## Commits

- `e1aadfc` Lyrics: warn on the share of weak words, not the median word score (`songcharter/engines/lyrics.py`,
  the warning line in `songcharter/pipeline.py`'s `_lyrics_stage`, `tests/test_lyrics.py`)
- `faba8a1` Lyrics tests: a docstring reworded (a common English word that the lyrics scan matched, now gone)
- `fbb9c1f` DESIGN 2.15: the lyrics warning calibrated, and the 50 ms share after M5-01

## What changed

- `engines/lyrics.py`: `LOW_MEDIAN` (0.25) is replaced by `UNSURE_SHARE = 0.108`. `confidence()` still gives
  `words_scored`, `median`, `p10` and `low_share` (the share of words under `LOW_SCORE` 0.05, the "weak words"),
  and passes them to the new `unsure()`. That function adds `statistic: "low_share"` and `threshold: 0.108`, sets
  `low` when the recorded share (3 places) is over the threshold or no word was scored, and adds `why`, e.g.
  "share of weak words (score under 0.05) 0.139, over 0.108" or "no word was scored".
- A cache hit runs `unsure()` again on the cached confidence, so a lyrics.json made under the median rule warns by
  the new one. The cache key and `VERSION` are unchanged: the statistic is already in the cached confidence, so
  nothing needs to be added to the cache.
- `pipeline.py`, one line: `lyrics: the alignment is unsure ({why}): check the lyrics' timing`. pipeline.json's
  `lyrics.confidence` keeps every field (asserted in a test).
- `docs/DESIGN.md` 2.15: the old rule's sentence is replaced; a pointer is added in the M5-09 paragraph; there are
  two new paragraphs ("The warning, calibrated" with the table, and "The 50 ms share after M5-01").

## Steps 1-3: the data (numbers only)

Script: `<scratchpad>/m5-04/collect.py` (never committed). For each song it reads the words from the package in
memory and runs `E.Torchaudio().run` (the engine's own aligner, default settings, CPU, 3 threads) on the kept
golden folder's seeded vocal stem and on its decode (the full mix). It saves only numbers: the human word times,
each syllable's word and line index, the raw and spread times, the characters' probabilities and the 0.1 s levels.
`analyze.py` then computes the timing with `lyrics_timing.compare`, pairing words by index (the text is the
chart's own, so the words match one for one), and the candidate statistics.

Ground truth: good if at least 0.85 within 250 ms, bad if under 0.60.

| run | truth | w250 | w50 | median err | median | p10 | weak share | >2 s | quiet starts | long lines |
|---|---|---|---|---|---|---|---|---|---|---|
| kimochi_warui stem | good | 0.908 | 0.249 | 98 ms | 0.882 | 0.105 | 0.066 | 0.004 | 0 | 0 |
| kimochi_warui mix | bad | 0.198 | 0.044 | 2.4 s | 0.118 | 0.042 | 0.139 | 0 | 0 | 0.024 |
| drunk_drivers stem | good | 0.929 | 0.539 | 43 ms | 0.844 | 0.133 | 0.025 | 0 | 0 | 0 |
| drunk_drivers mix | between | 0.752 | 0.433 | 62 ms | 0.180 | 0.048 | 0.113 | 0 | 0 | 0 |
| take_me_out stem | good | 0.875 | 0.571 | 39 ms | 0.827 | 0.144 | 0.039 | 0 | 0 | 0 |
| take_me_out mix | bad | 0.355 | 0.156 | 718 ms | 0.099 | 0.042 | 0.160 | 0 | 0 | 0 |
| all_the_small_things stem | good | 0.912 | 0.473 | 55 ms | 0.634 | 0.252 | 0.024 | 0.005 | 0 | 0 |
| all_the_small_things mix | bad | 0.561 | 0.229 | 200 ms | 0.123 | 0.038 | 0.161 | 0.005 | 0 | 0 |
| lucretia stem | good | 0.983 | 0.420 | 57 ms | 0.307 | 0.107 | 0.025 | 0 | 0 | 0 |
| lucretia mix | bad | 0 | 0 | 37.8 s | 0.094 | 0.045 | 0.151 | 0 | 0 | 0 |
| creep stem | good | 0.928 | 0.503 | 49 ms | 0.638 | 0.092 | 0.054 | 0.012 | 0 | 0 |
| creep mix | bad | 0.563 | 0.317 | 175 ms | 0.125 | 0.030 | 0.246 | 0 | 0 | 0 |
| troop stem | good | 0.950 | 0.550 | 40 ms | 0.183 | 0.060 | 0.084 | 0 | 0.006 | 0 |
| troop mix | bad | 0.331 | 0.172 | 1.9 s | 0.069 | 0.027 | 0.312 | 0 | 0 | 0 |

The tally is 7 good, 6 bad and 1 between (drunk_drivers mix, left out of the choice). Each alignment took 45-78 s
on 3 threads.

**Margins.** Each margin is the worst good run against the best bad one, as a ratio, which is the log scale. I used
the ratio for every statistic, so that they can be compared and the order's 1.5x rule applies.
- **The share of weak words: 1.65x** (troop stem 0.084 against kimochi_warui mix 0.139).
- The median: 1.46x (0.183 against 0.125).
- The 10th percentile: 1.33x.
- The share of words longer than 2 s (0.25x), the quiet starts (0.39x) and the long lines (1.00x) don't separate the
  runs. A collapsed alignment misplaces the words without stretching them, and the quiet-start test on the audio
  `align` is given can't fire on a full mix.
- Pairwise ORs: the best is weak words or long lines, 1.72x. That is not twice 1.65x, so no OR.
- Shares of 0 are floored at half a word (or line) for the logs.

**Choice:** the share of weak words, at the log-scale midpoint of 0.084 and 0.139, which is **0.108**. Its margin
is over 1.5x, so the order's fallback (the median at 0.197) doesn't apply. It fires on every bad run and on no good
one. It also fires on the between run (0.113).
- Leave-one-song-out moves the threshold within 0.096 (without troop) to 0.113 (without kimochi_warui), and no good
  or bad run changes side.
- The margin rests on two runs: troop's stem and kimochi_warui's mix.

## Step 5: the 50 ms share after M5-01

- **Raw engine word starts.** The references pooled (1,277 words): 0.457 / 0.703 / 0.917 within 50 / 100 / 250 ms,
  exactly M4-10's end-to-end numbers. troop stem: 0.550 / 0.841 / 0.950, median 40 ms.
- **On the chart (the pipeline, the new grid).** The references pooled: 0.505 / 0.612 / 0.901, exactly M4-10's.
  M5-01 didn't change their grids: each reference's SyncTrack hash is the same in the pre-M5-01 golden base and in
  this branch's golden run.
- **troop on the chart: 0.463 / 0.856 / 0.953, median 67 ms**, down from M5-09's 0.681 within 50 ms (median 7 ms) on
  the old 100 BPM map. Its SyncTrack in the lyrics check matches M5-01's stress run (a 200 BPM map).
- **Mechanism.** The 1/16 snap is now 75 ms. The aligner runs early on this song (raw signed median -20 ms; 0.29 of
  its words are 38-75 ms early), and such a word now snaps to the slot before the human's. The chart's signed error
  percentiles 10/25/50/75/90 are -75, -72, +0.5, +8 and +99 ms. On the 150 ms slots it used to snap onto the human's
  slot.
- **A finding for the orchestrator, not fixed here** (the order changes the warning only). The 50 ms share on a fast
  song got worse with M5-01's octave fix. Snapping lyrics to 8th lines on a fast map, or correcting the aligner's
  lead, would be a later order's (M5-99's syllable work is the natural home).

## Checks

All heavy jobs ran through `tools/heavy.sh` (the collection, then one chain). The worktree's environment came from
`uv sync --frozen --extra cpu --extra app --extra dev` and `npm ci`.

- **Suite:** `.venv/bin/python -m pytest -q -p no:cacheprovider --basetemp=/dev/shm/pt-m5-04` with
  SONGCHARTER_SCAN_CHART set. Last line: `951 passed, 3 skipped in 673.17s (0:11:13)`.
- **The new tests, broken six ways** (`<scratchpad>/m5-04/breaks.py`: one edit at a time, with
  `-k "confidence or unsure or cache"`, then restored). Every break failed at least one test:
  - A, the threshold's direction flipped (`<`): 4 failed.
  - B, UNSURE_SHARE set to 0.12: 3 failed.
  - C, the old median rule restored: 3 failed (`test_the_confidence_warns_on_the_share_of_weak_words`,
    `test_a_cached_confidence_is_judged_again`, `test_an_unsure_alignment_is_warned_about`).
  - D, "no word was scored" not low: 1 failed (`test_the_confidence_warns...`).
  - E, a cache hit not judged again: 1 failed (`test_a_cached_confidence_is_judged_again`).
  - F, the pipeline's old warning line: 1 failed (`test_an_unsure_alignment_is_warned_about`).
- **Golden** (`--rerun drums` on both runs: the kept drums output predates M5-01's beatgrid change; the
  orchestrator's later note asked the same):
  - `python -m eval.golden run --code /dev/shm/m504-main --out $DEV/golden/m5-04-old --threads 2 --rerun drums`
    (fef103d): exit 0, `summary: .../m5-04-old/summary.json (341 s)`.
  - `python -m eval.golden run --out $DEV/golden/m5-04-new --threads 2 --rerun drums`: exit 0, `(325 s)`.
  - `python -m eval.golden diff $DEV/golden/m5-04-old $DEV/golden/m5-04-new --expect none`: exit 0, `golden diff: no
    UNEXPECTED change`.
- **The stress set's lyrics check**, `eval/stress.py lyrics`:
  - `troop --run $DEV/golden/stress-base`: `320 of 320 human words paired ... within 50 / 100 / 250 ms 0.463 /
    0.856 / 0.953; phrase starts over 500 ms off 8 of 51; gate OK; the pipeline warned about the lyrics: no`. That
    meets the order's bar: 90 % or more within 250 ms and no warning.
  - `take_me_out --refs $EVAL_DATA/refs --run $DEV/golden/m5-04-new`: 0.567 / 0.684 / 0.870, 2 of 42 phrase starts,
    gate OK, warned: no.
  - `kimochi_warui` (the Car Seat Headrest song), the same way: 0.289 / 0.289 / 0.850, 0 of 41, gate OK, warned: no.
- **The same check through `pipeline.chart`** (`<scratchpad>/m5-04/checks.py`; each chart's SyncTrack is the golden
  run's of this branch):
  - On the stems: the other four references gave no warning either (weak shares 0.024-0.054).
  - With the full mix given to the aligner in place of the stem (an Engines subclass): it warns on troop (`...
    (share of weak words (score under 0.05) 0.312, over 0.108)...`); the other two warn too, at weak shares 0.160
    (`take_me_out`) and 0.139 (`kimochi_warui`). The gate is OK on all three. Those shares equal step 1's engine-level values, so the runs reproduce.
- **The owner's pasted text** of troop, through `pipeline.chart(..., Options(lyrics=text))` on the song's input.wav,
  against the human chart's words. The text was read with `cli.read_lyrics` in that process only.

  | text | words | paired | median | within 50 / 100 / 250 ms | phrase starts > 500 ms | warning |
  |---|---|---|---|---|---|---|
  | the human chart's | 320 | 320 (1.000) | 67 ms | 0.463 / 0.856 / 0.953 | 8 of 51 | no (weak 0.084) |
  | the owner's pasted text | 307 | 302 (0.944 of the human's, 0.984 of ours) | 65 ms | 0.467 / 0.858 / 0.967 | 2 of 43 paired | no (weak 0.088) |

  - The owner's text is paired with the chart's words by their text: difflib's matching blocks over the normalized
    spellings, in memory. Paired by index, as `stress.py` pairs, the pasted text drifts after its first missing word
    and gives 0.0 within 250 ms, which means nothing.
  - The owner's run is a good run, and its weak share of 0.088 is under 0.108 (1.23x below the threshold). If it
    joined the choice, the margin would be 1.58x and the threshold 0.111.
- **CI:** run 42101475004 on e1aadfc was green: linux 22 m (suite `950 passed, 4 skipped`, and the hooks ran),
  windows 44 s. The final head fbb9c1f, run 42116002253 (`<repo>/actions/runs/42116002253`), was green too: linux
  (suite `950 passed, 4 skipped in 518.31s`; hooks 10-lanes, 20-device, 30-install and 40-ui ok) and windows 46 s.
  No CI hook was added: the order's checks are unit tests in the suite.

## The scans

- **Lyrics.** `<scratchpad>/m5-04/scan.py` reads the lyric events of the six references' packages and troop's in
  memory: 252 lines, 53 distinctive words of 8 letters or more, and 722 three-word runs, with the songs' ids and
  title words left out. It prints only counts and line numbers.
  - Run over `git diff main...HEAD`, the commit messages, the whole scratch folder (`<scratchpad>/m5-04`: scripts,
    data, logs) and the progress log. The first run found 1 hit: a common English word in a test docstring. I
    reworded it (`faba8a1`).
  - The final scan of the diff and the commit messages: 0 hits.
  - The data and logs: 0 hits once the song ids were left out (the earlier hits were the ids and titles in the JSON
    and the logs).
  - The scan didn't read the owner's text (the brief allows reading it only in the charting process).
- **Model names and personal details.** A grep over the diff and the commit messages, with the trailer lines left
  out, for assistant-model names, `/home/`, `/tmp/`, a GitHub username, md5s and email-like strings: no match.
- **Built charts deleted.** Every chart with lyrics went into a temporary folder under the kept folders' `.runs/`,
  with its work folder and any `<out>.failed` beside it, and was deleted whole.
  - All 12 `checks.py` runs printed `temporary folder deleted: True`, and the three `stress.py lyrics` runs delete
    theirs.
  - `$DEV/golden/work/.runs` and `$DEV/golden/stress-work/.runs` are empty.
  - The golden runs (m5-04-old and m5-04-new) were built without lyrics.
  - The scratch data and logs hold numbers, ids and the warning's `why` only.

## Not done, uncertain, for the orchestrator

- **The 50 ms regression on fast songs** from M5-01's grid (step 5 above): reported, not fixed.
- **Still printing the median.** The summary line ("median word score X") and the lyrics stage's detail still print
  the median. The order allowed only the warning line in pipeline.py. Showing the weak share there would be a small
  follow-up.
- **Stale notes.** PROGRESS's deferred note "warned: median word score under 0.25" (M4-10) and the M5-04 note are
  stale. I didn't edit PROGRESS, as the brief asked.
- **Index pairing.** `eval/stress.py lyrics` pairs words by index, which is right for the chart's own text and wrong
  for a pasted one. Text pairing, as `checks.py` does it, would let the check take the friend's own texts.
- **The threshold's margin rests on two runs** (troop's stem, kimochi_warui's mix). The friend's real use, the
  owner's text, sits at 0.088 against 0.108. More fast songs with human vocals would test it.
- **Left in place.** `/dev/shm/m504-main` (detached at fef103d) stays for a reviewer's golden rerun; remove it at
  the merge. `$DEV/golden/m5-04-old` and `m5-04-new` hold no lyrics.
- `df -h /`: 17 GB free.

## Review (sc-reviewer, 2026-11-05)

# M5-04 review (sc-reviewer), head fbb9c1f

No major finding. One minor.

## Findings

**R1 (minor): the cache test can't tell "re-judge every hit" from "re-judge old files only".** `tests/test_lyrics.py`
`test_a_cached_confidence_is_judged_again` writes cached confidences with no `why` both times. So a re-judge that
skips files that already carry a verdict passes. That break is `songcharter/engines/lyrics.py` line ~400, `done = done
if "why" in (done.get("confidence") or {}) else {**done, "confidence": unsure(...)}`, and with it
`-k "confidence or unsure or cache"` gives `4 passed, 25 deselected`. Nothing breaks today. DESIGN 2.15 says
"a cached confidence is judged again on every hit", though, and the first later change to UNSURE_SHARE would leave
stale verdicts without a test failing. The fix: one more write in the test, with a stale verdict that carries a
`why` (e.g. low True, a why, low_share 0.0), expecting low False.

## Checked, no defect

- **Lyrics rule.** I read collect.py, checks.py and scan.py: they print numbers and types only. Each check's chart,
  work folder and `<out>.failed` sit under one temporary folder that is deleted. Both `.runs/` folders are empty, and
  no `*.failed` or `*-lyrics-*` is left except synthetic test fixtures. The builder's counts-only scan (run from a copy
  of the script) found 0 hits over the diff, the commit messages, the report, logs/, owner/, data/, table.json, the
  other logs and the scripts. I opened no package, ref chart or owner text.
- **The choice, recomputed** from data/*.json (numbers only): every weak share and median matches the table, and so
  do the labels (7 good, 6 bad, 1 between). Good max 0.084, bad min 0.139, margin 1.655x, log midpoint 0.1081.
  Leave-one-song-out gives 0.0958 and 0.1126, as reported. DESIGN 2.15 and the module docstring agree with the code.
- **Code.** Direction (`>`), the no-scored-word case, the cache hit re-judged, the cache key and VERSION unchanged,
  pipeline.json keeping every field, the warning line, and the UI reading only `low`: all right. The eval code matches
  the warning by its unchanged prefix.
- **Test the tests.** I confirmed the builder's breaks A-F. Mine: `>=` for `>` stays green (it only matters at a
  share of exactly 0.108, so harmless). Dropping the `words_scored` guard stays green (the isinstance check covers
  it). An extra OR on p10 < 0.03 stays green, but it fires on no good run in the data. A threshold of 0.105 or 0.11 is
  caught by the literal `why` strings. H is R1.
- **For you.** The 50 ms regression comes from M5-01's grid. This order touches only the warning, so it can't make it
  worse. The median still shown in the summary and the stage detail is allowed by the order. A follow-up could show
  the weak share there. The owner's text sits at 0.088, 1.23x under the threshold. That is the real risk, and it is
  stated in the report and DESIGN.

## Review fix (orchestrator)

R1: tests/test_lyrics.py gains a cached confidence that already carries a why (low True at a share of 0.0); it comes back not unsure with today's why, and fails on the reviewer's break (re-judging only files without a why). 29 passed in tests/test_lyrics.py; CI green on 2580e02.
