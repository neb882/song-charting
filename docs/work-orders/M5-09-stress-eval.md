# M5-09: the stress set: the two fast songs as a repeatable check, with per-window scores and a lyrics timing check

**Branch:** `m5-09-stress-eval`, from `main` after M4-11's merge (wave 1, beside M5-01; merged first). **Agent:**
`sc-builder`, then `sc-reviewer`. May push its branch to run CI. **Files:** `eval/` only (`stress.json` new,
`build_refs.sh`, `golden.py` where the set's shape needs it, `scorer/score.py`, `stress.py` new, `lyrics_timing.py`
new, `README.md`, `baseline/`), `tests/test_golden.py` and a new `tests/test_eval_stress.py`, `docs/DESIGN.md` 3.3 and
3.6, `docs/PROGRESS.json`'s `golden` entry (the orchestrator folds it in). **Time budget:** 1 day, the baseline run
included (about an hour of machine time, cold).

## The lyrics rule (the exception, committed here so it lives in the repository)

`docs/work-orders/M4-10-lyrics.md`'s rule binds this order. Its exception extends to the stress songs' human charts:
`eval/stress.py lyrics` may read the lyric events of a stress package in memory, to give the words to songcharter's
aligner and compare the timings. Nothing may print, log, save, commit or return a word: not the script, not a test,
not a report. The chart it builds with the text goes to a folder outside the repository that the command deletes
when it has scored it. Tests use made-up words only.

## Why

The owner's two hard songs from 2026-11-05 (a 9-minute shred instrumental and a 5-minute 198 BPM power-metal song;
PROGRESS `deferred`) showed the defects M5-01, M5-02 and M5-03 fix. Their human charts and scores live in the
session's scratch folder (`<S>/sooth/`, `<S>/troop/`: `ref_*` folders, the owner's charts in `ours/`, a timing-only
lyrics script in `troop/scripts/lyrtime.py`), which no later session can rely on. The reference set's machinery
(`eval/build_refs.sh`, `eval/golden.py`, `eval/scorer/score.py`) already does nearly all of this for seven songs; the
stress songs need the same, kept apart from the golden set so the golden baseline and its kept folders stay as they
are. PROGRESS's `next` asks whether the reference set should grow (M5-00 answers: the mechanism now, the songs
later [owner]).

## What to build

1. **`eval/stress.json`:** the stress songs, each with its human charts from Chorus Encore, the first being the
   primary (the one with the most parts). The two songs, their packages' md5s as the scratch folders name them
   (`<S>/troop/dl/`, `<S>/sooth/dl/`; the charters in the md5 list file in `<S>/sooth/` and the packages' song.ini):
   - `troop`: the power-metal song (three charts; the primary has guitar, bass, drums and vocals);
   - `sooth`: the shred instrumental (two charts; the primary has guitar and bass).
   Artist, title, charter and slot as `refs.json` records them. The packages are other people's work: downloaded
   into `$EVAL_DATA/sng/`, never committed.
2. **`eval/build_refs.sh --set stress`** (the default stays `refs`): builds `$EVAL_DATA/stress/<id>/` from the primary
   package as it builds a reference (input.wav from the package's stems, `ref/` with vocals and lyrics stripped,
   ref_notes.json, offset_check.json) and `$EVAL_DATA/stress/<id>/alt/<md5>/` the same way for each other chart, then
   `stress/songs.json`. Reuse `eval/refs/*.py`; change them only where the set's name is hard-wired.
3. **`eval/golden.py` on the stress set:** `python -m eval.golden run --refs $EVAL_DATA/stress --work
   $SONGCHARTER_GOLDEN/stress-work --out DIR` must work as it does for the reference set (its summary with the
   onsets, hashes and the primary ref's F1s; its kept folders apart from the golden set's; the heavy-job lock). Fix
   what assumes the seven ids or the test song; `diff` unchanged.
4. **`eval/stress.py`:**
   - `score RUN_DIR`: for each song of a run, `score.py` against the primary and every alt ref, and the alt refs
     against the primary (the humans' agreement), with `--windows 30`; writes `stress_scores.json` beside the
     summary and prints one table: per song, part and human chart the F1@50 and F1@100, the chord share (ours and
     theirs), the matched notes' median timing error, the notes ratio, the 1-s density peak (ours and theirs), the
     beat F1 plain and octave-tolerant, and the lowest 30-s window F1@100 with its start time;
   - `compare OLD NEW`: the two tables side by side with the differences, exit 1 when any F1@50 of the primary
     comparison falls by more than 0.01 (the stress check's regression rule);
   - `lyrics ID [--run RUN_DIR]`: the words from the primary package's lyric events (in memory), songcharter's
     `pipeline.chart` called in process with `Options(lyrics=text, takes=1, device="cpu", preview=False)` on the
     song's input.wav into a temporary folder, `lyrics_timing.py`'s comparison of the built chart's lyric timings with
     the primary chart's (by word index, after the scorer's alignment lag: 0 here, the same audio), the numbers
     printed (paired share, median, within 50/100/250 ms, phrase starts over 500 ms, whether the pipeline warned),
     the temporary folder deleted. For a song with no vocals it says so and exits 0.
5. **`eval/scorer/score.py`:** `--windows N` adds, per part, F1@100 (and the counts) per N-second window over the
   ref span, to the JSON and one line of the summary; `density_peak_1s` per part (the most onsets in any one-second
   window, ours and the ref's). No existing key changes (the golden summary reads them).
6. **`eval/lyrics_timing.py`:** `lyrtime.py` from the scratch folder, cleaned: a docstring with the rule, `.chart` and
   `.mid` read, word indices and times only, every error printed as its type. Review every print.
7. **The baseline:** `build_refs.sh --set stress`, then the stress run of `main` at the merge base of the M5 branches
   (the commit M5-01 branches from; 1 CPU take, as the golden runs) into `$SONGCHARTER_GOLDEN/stress-base/`, scored;
   `summary.json` and `stress_scores.json` copied to `eval/baseline/stress/` (hashes, counts and scores only: no
   audio, no chart). The `lyrics` check on `troop` run once and its numbers recorded in the report and DESIGN 2.15
   (they are the owner's 2026-11-05 numbers' counterpart on the package's audio).
8. **`eval/README.md`:** a "Stress songs" section: the set, the commands (build, run, score, compare, lyrics), the
   environment (`EVAL_DATA`, `SONGCHARTER_GOLDEN`, the same engines), the cost measured, how a song is added (one
   entry in stress.json, `build_refs.sh --set stress`, a new baseline) and the rule that nothing of it is committed
   but stress.json and the baseline numbers.

## Tests

- `stress.json` parses and every song has a primary; `build_refs.sh --set stress` on a made-up package (a tiny
  `.sng` the test writes, with made-up words in its lyric events) builds the folders and strips the lyrics from
  `ref/`;
- `score.py --windows` on generated charts: the windows' F1s and the density peak;
- `stress.py score` and `compare` on made-up summaries and scores: the table and the exit code;
- `lyrics_timing.py` on two generated charts with made-up words: the numbers, and no word in its output (assert on
  the captured stdout and stderr);
- `stress.py lyrics` with stand-in engines (tests/test_pipeline.py's `standins`) on a made-up package: the numbers,
  the temporary folder gone, no word in the output.
- Each test fails when its code is broken (say which break).

## Evaluation

- No charting path (`eval/` and tests): no golden run; `eval/golden.py`'s own tests must pass and a golden `run`
  of the reference set's summary must be identical to the last one (the `--rerun`-free 6.5-minute run, diffed
  against `eval/baseline/summary.json`'s hashes: say what differed, if anything).

## Done means

- [dev] The suite; the new tests fail when their code is broken; the stress set built on the dev machine; the
  baseline run and scores in `eval/baseline/stress/`; the lyrics check's numbers; `df -h` before and after (the
  kept folders and the separation cache cost about 3 GB: refuse to start under 8 GB free and say so).
- [CI] Green on the branch.
- [docs] eval/README.md's section; DESIGN 3.3 (the stress set beside the reference set) and 3.6; PROGRESS `golden`
  gets the stress baseline's commit and paths (the orchestrator).

## Limits

- Nothing from the packages is committed: no audio, no chart, no lyric. The committed numbers are counts, hashes
  and scores. Charter handles and song titles are recorded as `refs.json` records them.
- The golden set, its kept folders and `eval/baseline/summary.json` are not touched.

## Report

`<scratchpad>/briefs/m5-09.report.md`: the commits, the stress table of the baseline (every number the orders
M5-01 to M5-04 cite as "today's"), the lyrics check's numbers, the costs and disk, each check's last lines, the CI
run's URL, anything uncertain.
