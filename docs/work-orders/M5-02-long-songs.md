# M5-02: long, busy songs: a guitar take cut short by the engine's budget is continued and stitched

**Branch:** `m5-02-long-songs`, from `main` after wave 1 (wave 2, beside M5-01; M5-05's per-seed calls in the
guitar stage are merged by then, so the warnings below go in that per-seed loop). **Agent:** `sc-builder`, then
`sc-reviewer`. May push its branch to run CI. **Files:** `songcharter/engines/autochart.py`, a new
`songcharter/engines/stitch.py` (added to `eval/golden.py`'s `ENGINE_FILES["guitar"]`: the one line this order may
change in `eval/`), `songcharter/pipeline.py` (the guitar stage's warnings and log lines only), `songcharter/chart.py`
only if the writer lacks something, their tests, `docs/DESIGN.md` 2.7, the guide's section 5 (one sentence).
**Time budget:** 2 days, the golden run with `--rerun guitar` on both sides included (about 2 hours of machine time).

*Amended 2026-11-05 after the advisor's review (finding 7, confirmed by a skeptic): a take cut short by v0.1 and
cached is continued after the update (step 1's cache rule), and every cut-short take gets a `stitch` record.*

**Conventions** (`docs/reports/charting-conventions.md`, section 2a, ranked gap 5): **[conventions]** Expert is a
literal transcription of the part; a chart whose notes stop while the guitar plays is an underchart and a lost
ending, a fault any player sees. So a take the engine cut short is completed to the end of the song, and when it
cannot be, the user is told where the guitar ends.

## Why

The owner's 9-minute shred instrumental (`<S>/sooth/`, 2026-11-05, 4 CUDA takes): all four takes stop at 498.6 s of
544.8 s while the human charts have notes to about 9:00 and our bass and drums run to 539 s. autochart's decoder has
a budget of 8,192 tokens a job (the model manifest's `maxTokens`; `ac_headless.cjs` logs "decoder used its whole
8192-token budget; the end of the chart may be missing" and records `nTokens` per run) and a cap of 1,280 beats
(`maxBeats`, `buildBeatMel.mjs`); this song used the tokens up after about 2,190 notes. songcharter neither splits a
long song's transcription nor tells the user that the guitar ended early. A dense 5-minute song can reach the budget
too (Lucretia used 9.0 tokens a beat: about 910 beats). DESIGN 2.7 planned windows "split at section boundaries"
for route B2 and 8.1 (G9) lists "token-cap windowing" as untested.

## What to build

The engine stays a black box run per job (route B1). A take runs whole first, as now; a take the engine cut short is
continued from where it stopped, and the pieces are stitched into one take. Every song under the budget takes
exactly today's path and gives a byte-identical take (the golden check).

1. **Detecting a take cut short** (`engines/autochart.py`): after a run, read the driver's summary: the run is cut
   short when `runs[0].nTokens >= maxTokens` (the summary carries both) or `runs[0].nBeats >= 1280`
   (`MAX_BEATS`, the manifest's cap; read it from the models' manifest when it is there, else 1280). Record
   `cut_short` with the reason in the Take.
   - **The cache, for takes v0.1 made:** the take's key holds the input, the seed, the settings and the install, not
     songcharter's code, so a take v0.1 cut short is a cache hit after the update with the same lost ending and no
     warning (the friend's long songs and the owner's shred instrumental are in their caches). So `_done` treats a
     cached take whose summary is cut short by the rule above and has no `stitch` record (step 3) as a miss: the take
     runs whole again, once, and is continued. The driver has not changed since v0.1.0, so v0.1 summaries carry
     `maxTokens`, `nTokens` and `nBeats` (every real summary on the dev machine does). The key is unchanged: a
     version in the key would rerun every take after the update and break M5-07's cached-update check (its CI needs
     "(cached)" for the guitar); all seven golden takes are under both caps and still hit.
2. **The continuation.** For a take cut short, with `T` = the time of the last note of its chart (seconds of the
   decode; 0 notes means `T` = 0, which is "no guitar at all": then no continuation, the take stays as it is, but it
   gets a `stitch` record with `pieces: []` so it is a hit next time):
   - the piece starts at `B = floor(T) - 1` s (`KEEP_FROM`), and its audio is the decode from `B - CONTEXT` (8 s;
     clipped at 0) to the end, written as a WAV beside the take (`seed_<seed>/piece_<k>/input.wav`, the same
     samples as `decode.wav`, so the engine's input is still our decode);
   - the piece is one more engine job with the same seed and settings (a fresh job folder under the scratch; the
     engine separates and times the piece itself, keyed by the piece's own SHA-256), run through the same `run`
     call, timeout and error path as a take; its notes before `B` (absolute time) are dropped, the rest shifted by
     the piece's start;
   - a piece cut short again is continued the same way, at most `MAX_PIECES` = 6 times; a piece whose last note
     advances `T` by under 20 s ends the loop (the engine finds nothing more there) and is still stitched.
3. **Stitching** (`engines/stitch.py`, pure functions, tested on their own): the whole-song run's chart is the base
   (its [SyncTrack] covers the whole audio: the engine's timing stage ran on the whole song, only the decode
   stopped). The stitched Expert track = the base's notes with time `< B`, then each piece's kept notes converted to
   the base's ticks through the base's tempo map (`importers.read_song` for the pieces' notes in seconds, the base's
   TempoMap for `sec_to_tick`, rounded to the nearest tick), with their sustain ends converted the same way, taps
   kept and the HOPO intent kept by writing a flip where the natural state on the base's map differs (as
   `quantize._frets` does). A base sustain crossing `B` ends `GAP` = 0.060 s before `B`. Star power, solos and
   fills of the pieces are dropped (assemble drops every source's phrases anyway). The result is written with
   `chart.py`'s writer as `seed_<seed>/notes.chart`; the engine's own truncated output moves to
   `seed_<seed>/cut_short/` (its notes.chart, song.ini, song.ogg and autochart_run/) and each piece's song folder
   stays in `seed_<seed>/piece_<k>/`. `autochart_run/summary.json` of the stitched take is the whole-song run's
   summary plus `"stitch": {"cut_short": reason, "pieces": [{"start_s", "keep_from_s", "last_note_s", "nTokens",
   "nBeats", "seconds"}], "last_note_s"}`, written for every cut-short take this step handles (`pieces: []` for a
   `T` = 0 take); `take.json`'s key is unchanged (the pieces follow from the seed and the input), so `_done` reuses
   a stitched take as it reuses any other, and a run interrupted mid-stitch leaves no take.json and is run again
   whole next time.
   - `Take.devices` must still answer from the whole-song run; a piece whose transcriber ran on another device than
     asked counts as that device for the take (the pipeline's fallback rules read it).
4. **The pipeline** (`pipeline.py`, the guitar stage): a take with `stitch` gets a warning
   `guitar take seed N: the engine's budget ran out at m:ss of M:SS (R); the rest was transcribed in K more piece(s),
   to m:ss` and a log line per piece; `record["takes"]` lists per take `cut_short`, `pieces` and `last_note_s`. A
   take whose continuation could not advance (the loop ended on the 20-s rule with notes missing to the end of the
   stem's activity) warns `guitar take seed N: the guitar ends at m:ss (the engine found nothing after that): check
   the end of the chart`. A piece that fails raises exactly as a failed take does (`take_failed` on CUDA, the
   engine's own ToolError otherwise): the finished whole-song run and pieces are kept on disk but not as a take.
5. **Memory and time:** a piece is a whole engine job (its separation and beat map included) on at most the song's
   tail plus 8 s: on the shred instrumental about 55 s of audio. Record each piece's seconds in the summary.

## Tests

- `stitch.py`: a base chart and a piece chart made in the test (chart.py's writer on known tempo maps): notes before
  `B` from the base, after from the piece, shifted; a piece note at exactly `B` kept once; a base sustain crossing `B`
  clipped; a piece's HOPO intent kept across the map change (a flip written where needed); taps kept; phrases
  dropped; two stitches of the same inputs byte-identical.
- `engines/autochart.py` with the stand-in `run` of tests/test_engines_autochart.py: a summary with `nTokens` 8192
  and a chart ending at 60 % of a generated song makes a second `run` call whose `--audio` is a WAV from `B - 8 s`
  with the right samples, the stitched notes.chart in place, `cut_short/` and `piece_1/` beside it, take.json
  written last; the `nBeats` 1280 path the same; a piece cut short again continues (two pieces); the 20-s rule ends
  the loop; `MAX_PIECES`; a piece's non-zero exit raises ToolError naming the seed; `_done` hits on the stitched
  take; a summary under both caps makes one `run` call and leaves the engine's files exactly as today (byte-identical
  folder listing and notes.chart); the cache rule: a cached cut-short take without `stitch` (a v0.1 take, made by
  the test with today's files) runs again and is continued; the same with `stitch`, no run; the `T` = 0 take is a
  hit on the second run.
- `pipeline.py` with `standins`: the warning and the record for a stitched take; the "ends at" warning.
- Each test fails when its code is broken (say which break).

## Evaluation

- **Golden:** `engines/autochart.py` changed, so `--rerun guitar` on both runs, `--expect none`: every reference song's
  guitar take must be byte-identical (no reference song reaches the budget: check each kept summary's `nTokens`
  and report the largest; Lucretia's is the one to watch). Any change fails the order.
- **The stress set** (M5-09): the shred instrumental, 1 CPU take, before and after ("today's" is M5-09's baseline
  run of `main`; the owner's 4-take figures are reported beside it). Pass:
  - the stitched take's last note at 530 s or later; `cut_short` recorded with its reason; the warning shown;
  - in the song's last 60 s, guitar F1@100 against each human chart at least 0.60 (`score.py --windows 30`, M5-09;
    today 0 for the last 45 s), and the whole-song F1@50 and F1@100 not below the baseline's (the owner's run:
    0.636 / 0.743 and 0.725 / 0.748);
  - no note within 1 s of the seam `B` missing on both sides or doubled (count the onsets in `[B - 1, B + 1]` in the
    stitched chart against the whole-song run's and the piece's: the stitched count is max(the two), not their sum);
  - the power-metal song and every reference song: one engine run per take, no piece, identical charts.

## Done means

- [dev] The suite; the new tests fail when their code is broken.
- [dev] The golden diff as above (exit 0, `report.md` in the report, the largest `nTokens` among the references).
- [dev] The stress check's lines above, with numbers, before and after.
- [CI] Green on the branch.
- [docs] DESIGN 2.7 (the continuation: when, where it cuts, how it stitches, the cost on the shred instrumental),
  8.1's G9 row; the guide's section 5: one sentence that a very long or busy song's guitar may be transcribed in
  pieces, shown as a note on the Done screen.

## Limits

- No change to the engine, its driver (`eval/tools/autochart/ac_headless.cjs` is in the take's key: changing it reruns
  every take everywhere) or the take's key. No change to `takes.py`'s splice. No new dependency.
- The stitched chart is a take like any other for the splice, the quantizer and the gate: no special path after the
  guitar stage.
- The stress songs' human-chart packages have vocal tracks: they are read only through `stress.py` and `score.py`,
  which print numbers; never open a package's chart, nor the scratch folders' (`<S>/sooth/human_*` and
  `<S>/troop/human_*`, and the scratch `ref_*` folders, one of which still holds lyric events). Once M5-09 has
  merged, only `$EVAL_DATA/stress/` refs are read.

## Report

`<scratchpad>/briefs/m5-02.report.md`: the commits; the golden `report.md` and the references' `nTokens`; the stress
lines before and after; the pieces' sizes and times on the shred instrumental; anything uncertain.
