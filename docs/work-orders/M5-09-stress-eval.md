# M5-09: the stress set: the two fast songs and an ordinary rock song as a repeatable check, with the feel measures, per-window scores and a lyrics timing check

**Branch:** `m5-09-stress-eval`, from `main` after M4-11's merge (wave 1, beside M5-06 and then M5-05; merged before
wave 2). **Agent:** `sc-builder`, then `sc-reviewer`. May push its branch to run CI. **Files:** `eval/` only
(`stress.json` new, `build_refs.sh`, `golden.py` where the set's shape needs it, `scorer/score.py`, `stress.py` new,
`lyrics_timing.py` new, `README.md`, `baseline/`), `tests/test_golden.py` and a new `tests/test_eval_stress.py`,
`docs/DESIGN.md` 3.3 and 3.6, `docs/PROGRESS.json`'s `golden` entry (the orchestrator folds it in). **Time budget:**
1.5 days, the baseline run included (about 1.5 hours of machine time, cold, for three songs); 2 days if the
repeat-consistency measure (step 5) fits. **The baseline run comes first:** M5-01 starts the moment the builder
reports that `stress-base` exists (step 7), before this order's review, so build the set and run the baseline before
the rest of the scorer work, and say in the progress log when it is there.

*Amended 2026-11-05 after the advisor's review and the feel note: the stress table carries the feel measures
(step 4), the lyrics check keeps every file it makes under its temporary folder and the build skips an empty stem
(the hygiene rules), and the owner added an ordinary rock song to the set as a guard against making normal songs
worse (step 1).*

## The lyrics rule (the exception, committed here so it lives in the repository)

`docs/work-orders/M4-10-lyrics.md`'s rule binds this order. Its exception extends to the stress songs' human charts:
`eval/stress.py lyrics` may read the lyric events of a stress package in memory, to give the words to songcharter's
aligner and compare the timings. Nothing may print, log, save, commit or return a word: not the script, not a test,
not a report. The chart it builds with the text goes to a folder outside the repository that the command deletes
when it has scored it. Tests use made-up words only. Until this order's set exists, the scratch folders are
packages under the same exception: the full packages (`<S>/troop/human_*`, `<S>/sooth/human_*`) and the scratch
`ref_*` folders (one of which, the power-metal chart with 409 lyric events, was never stripped as `build_refs.sh`
strips `ref/`) are read only by timing scripts that print numbers, never opened with Read, cat or grep; after the
merge, every order reads `$EVAL_DATA/stress/` refs only.

## Why

The owner's two hard songs from 2026-11-05 (a 9-minute shred instrumental and a 5-minute 198 BPM power-metal song;
PROGRESS `deferred`) showed the defects M5-01, M5-02 and M5-03 fix. Their human charts and scores live in the
session's scratch folder (`<S>/sooth/`, `<S>/troop/`: `ref_*` folders, the owner's charts in `ours/`, a timing-only
lyrics script in `troop/scripts/lyrtime.py`), which no later session can rely on. The reference set's machinery
(`eval/build_refs.sh`, `eval/golden.py`, `eval/scorer/score.py`) already does nearly all of this for seven songs; the
stress songs need the same, kept apart from the golden set so the golden baseline and its kept folders stay as they
are. PROGRESS's `next` asks whether the reference set should grow (M5-00 section 8 answers: the mechanism now, three
songs in this version, the two hard ones and an ordinary rock song as the guard; more are the owner's to pick in
M6).

## What to build

1. **`eval/stress.json`:** the stress songs, each with its human charts from Chorus Encore, the first being the
   primary (the one with the most parts). Three songs [the owner, 2026-11-05]; the first two's packages' md5s as the
   scratch folders name them (`<S>/troop/dl/`, `<S>/sooth/dl/`; the charters in the md5 list file in `<S>/sooth/`
   and the packages' song.ini):
   - `troop`: the power-metal song (three charts; the primary has guitar, bass, drums and vocals);
   - `sooth`: the shred instrumental (two charts; the primary has guitar and bass);
   - `break`: an ordinary rock song, the guard against making normal songs worse: Chorus
     Encore lists four guitar charts of it and none with lyrics; the builder looks them up by artist and title as
     `eval/README.md`'s Encore query does, takes the one with the most parts as the primary and the others as alts,
     and records their md5s. The owner charted it in v0.1 from a file of his own, whose `song.ogg` the orchestrator
     puts at `<S>/break/song.ogg` (never committed): `stress.py align break <file>` runs the scorer's audio
     alignment (`score.py`'s windowed cross-correlation: the share of windows with peak ≥ 0.3 and the lags' MAD) of
     that file against the set's `input.wav` and prints the result; when it aligns (most windows over 0.3, MAD under
     2 ms), the owner's own chart and play test of his file are comparable with the set's numbers and the report
     records the lag; when it does not (a cover or another edit), the report says so and the owner's file is left
     out, but the song stays in the set on the package's audio. The song is dropped from the set, and the report
     says so, only if no package of it has audio the build can use.
   Artist, title, charter and slot as `refs.json` records them. The packages are other people's work: downloaded
   into `$EVAL_DATA/sng/`, never committed.
2. **`eval/build_refs.sh --set stress`** (the default stays `refs`): builds `$EVAL_DATA/stress/<id>/` from the primary
   package as it builds a reference (input.wav from the package's audio, stems summed, `ref/` with vocals and lyrics
   stripped, ref_notes.json, offset_check.json) and `$EVAL_DATA/stress/<id>/alt/<md5>/` the same way for each other
   chart, then `stress/songs.json`. Reuse `eval/refs/*.py`; change them only where the set's name is hard-wired. An
   empty or unopenable stem in a package (the power-metal primary's `drums.opus` is a 135-byte stub ffmpeg cannot
   open) is skipped by the build, named in `build_meta.json`, and skipped by the scorer when it meets one as a
   candidate's or a ref's audio; a test with a stub stem covers both.
3. **`eval/golden.py` on the stress set:** `python -m eval.golden run --refs $EVAL_DATA/stress --work
   $SONGCHARTER_GOLDEN/stress-work --out DIR` must work as it does for the reference set (its summary with the
   onsets, hashes and the primary ref's F1s; its kept folders apart from the golden set's; the heavy-job lock). Fix
   what assumes the seven ids or the test song; `diff` unchanged.
4. **`eval/stress.py`:**
   - `score RUN_DIR`: for each song of a run, `score.py` against the primary and every alt ref, and the alt refs
     against the primary (the humans' agreement, the ceiling of every measure), with `--windows 30`; writes
     `stress_scores.json` beside the summary and prints one table, **the feel report** (`docs/reports/feel.md`,
     committed at wave 0, says what each measure is for; its number is given in brackets): per song, part and human
     chart
     - F1@50 and F1@100, the notes ratio, and the lowest 30-s window F1@100 with its start time;
     - the matched notes' median timing error, per part, the guitar's beside bass's and drums' [sync, 1];
     - the chord share, ours and theirs, and the 1-s density peak, ours and theirs [readability, 2];
     - the contour agreement (`lane_direction_agreement`, 0.71-0.79 between the human charts of these songs), the
       jump-size distribution against the humans' (lanes between consecutive single notes) and the rate of big fast
       jumps, 3 or more lanes under 100 ms, ours and theirs [flow, 3];
     - the HOPO, tap and sustain shares, ours and theirs, and the per-note strum, HOPO and tap agreement on the
       matched notes (`state_agreement`, new in `score.py`: it already matches the notes; shares alone mislead, the
       power-metal song's three charts have HOPO shares of 0.21, 0.51 and 0.29) [articulation, 5];
     - notes in silence (report.json's `silent_onsets` per part) and gaps while the stem plays (`preview.flags` on
       the kept folder with the cached stems: a function, no image) [shape, 6];
     - star-power phrases per minute, ours and theirs, and the solo share of the charted span, ours and theirs
       [sustains and star power, 7];
     - the beat F1 plain and octave-tolerant, and the downbeat F1 (measure lines, new in `score.py`, the same 70 ms
       tolerance against the ref map's downbeats) [beat lines, 8].
     Sync is never measured against the stem's own onsets with a fixed aim, there is no fixed strum-rate cap, and
     contour is against the human charts, not a pitch track (the advisor's corrections to the feel note's first
     draft; `feel.md`'s "Revised" section). Difficulty fit [9] has no measure: the play test at the gate.
   - **Repeat consistency** [learnability, 4], if it fits the budget (about half a day): for sections with the same
     allin1 label (a repeated chorus or riff), the similarity of their Expert fret sequences (the share of
     corresponding notes with the same lanes after aligning the two sections by onset time), ours against the human
     chart's own figure on the same sections. If it does not fit, it is M5-99's (M6) with the fix, and the report says
     so.
   - `compare OLD NEW`: the two tables side by side with the differences, exit 1 when any F1@50 of the primary
     comparison falls by more than 0.01 (the stress check's regression rule);
   - `align ID FILE`: step 1's audio alignment of a file against the song's `input.wav`;
   - `lyrics ID [--run RUN_DIR]`: the words from the primary package's lyric events (in memory), songcharter's
     `pipeline.chart` called in process with `Options(lyrics=text, takes=1, device="cpu", preview=False)` on the
     song's input.wav into a temporary folder, `lyrics_timing.py`'s comparison of the built chart's lyric timings with
     the primary chart's (by word index, after the scorer's alignment lag: 0 here, the same audio), the numbers
     printed (paired share, median, within 50/100/250 ms, phrase starts over 500 ms, whether the pipeline warned),
     the temporary folder deleted. A failed gate writes the chart, words included, to `<out>.failed` beside `out`
     (`pipeline.py`): so `out` is `<tmp>/song` and the work folder is under `<tmp>` too, and the command deletes
     `<tmp>` whole; the test asserts that nothing under either survives. For a song with no vocals it says so and
     exits 0.
5. **`eval/scorer/score.py`:** `--windows N` adds, per part, F1@100 (and the counts) per N-second window over the
   ref span, to the JSON and one line of the summary; `density_peak_1s` per part (the most onsets in any one-second
   window, ours and the ref's); `state_agreement` (per matched note, the share whose played state, strum, HOPO or
   tap as scan-chart resolves it, is the same in both charts, and the confusion counts), `jumps` (the lane-jump
   histogram and the big-fast-jump rate, ours and the ref's), `downbeat_f1_70ms`, `star_power_per_min` and
   `solo_share`, ours and the ref's; an unopenable stem skipped with a note. No existing key changes (the golden
   summary reads them). About an hour each: chart-only work on notes the scorer already matches.
6. **`eval/lyrics_timing.py`:** `lyrtime.py` from the scratch folder, cleaned: a docstring with the rule, `.chart` and
   `.mid` read, word indices and times only, every error printed as its type. Review every print.
7. **The baseline:** `build_refs.sh --set stress`, then the stress run of `main` at this branch's merge base (wave 1's
   `main`, after M4-11; 1 CPU take, as the golden runs) into `$SONGCHARTER_GOLDEN/stress-base/`, scored;
   `summary.json` and `stress_scores.json` copied to `eval/baseline/stress/` (hashes, counts and scores only: no
   audio, no chart). Say in the progress log and the report when `stress-base` exists: M5-01's builder starts on it
   (its octave threshold needs the stress songs' engine charts, which are in the kept folders). The `lyrics` check on
   `troop` run once and its numbers recorded in the report and DESIGN 2.15 (they are the owner's 2026-11-05 numbers'
   counterpart on the package's audio). An order that branches after another charting-path order has merged (wave 3
   on) compares with a stress run of its own merge base, kept beside `stress-base`, not with the baseline.
8. **`eval/README.md`:** a "Stress songs" section: the set, the commands (build, run, score, compare, lyrics), the
   environment (`EVAL_DATA`, `SONGCHARTER_GOLDEN`, the same engines), the cost measured, how a song is added (one
   entry in stress.json, `build_refs.sh --set stress`, a new baseline) and the rule that nothing of it is committed
   but stress.json and the baseline numbers.

## Tests

- `stress.json` parses and every song has a primary; `build_refs.sh --set stress` on a made-up package (a tiny
  `.sng` the test writes, with made-up words in its lyric events, and a 100-byte stub stem) builds the folders,
  strips the lyrics from `ref/` and skips the stub, naming it;
- `score.py --windows` on generated charts: the windows' F1s and the density peak; `state_agreement`, `jumps`,
  `downbeat_f1_70ms`, `star_power_per_min` and `solo_share` on generated charts with known answers; a stub stem
  skipped;
- `stress.py score` and `compare` on made-up summaries and scores: the table and the exit code; `align` on a shifted
  copy of a generated file (the lag) and on noise (no alignment);
- `lyrics_timing.py` on two generated charts with made-up words: the numbers, and no word in its output (assert on
  the captured stdout and stderr);
- `stress.py lyrics` with stand-in engines (tests/test_pipeline.py's `standins`) on a made-up package: the numbers,
  the temporary folder gone with everything under it (a run whose gate fails, so `<out>.failed` was written, leaves
  nothing either), no word in the output.
- Each test fails when its code is broken (say which break).

## Evaluation

- No charting path (`eval/` and tests): no golden run; `eval/golden.py`'s own tests must pass and a golden `run`
  of the reference set's summary must be identical to the last one (the `--rerun`-free 6.5-minute run, diffed
  against `eval/baseline/summary.json`'s hashes: say what differed, if anything).

## Done means

- [dev] The suite; the new tests fail when their code is broken; the stress set built on the dev machine; the
  baseline run and scores in `eval/baseline/stress/`, the feel report's every column filled for the three songs;
  the lyrics check's numbers; the `align` result for the owner's file of the rock song; `df -h` before and after
  (the kept folders and the separation cache cost about 4.5 GB for three songs: refuse to start under 10 GB free and
  say so).
- [CI] Green on the branch.
- [docs] eval/README.md's section; DESIGN 3.3 (the stress set beside the reference set) and 3.6; PROGRESS `golden`
  gets the stress baseline's commit and paths (the orchestrator).

## Limits

- Nothing from the packages is committed: no audio, no chart, no lyric. The committed numbers are counts, hashes
  and scores. Charter handles and song titles are recorded as `refs.json` records them.
- The golden set, its kept folders and `eval/baseline/summary.json` are not touched.

## Report

`<scratchpad>/briefs/m5-09.report.md`: the commits, the stress table of the baseline (every number the orders
M5-01 to M5-04 cite as "today's" or "the baseline", the feel measures included, with the humans' agreement beside
each), whether the repeat-consistency measure was built, the rock song's packages and the `align` result, the lyrics
check's numbers, the costs and disk, each check's last lines, the CI run's URL, anything uncertain.
