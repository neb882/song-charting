# M5-02 report: a guitar take cut short by the engine's budget is continued and stitched

Builder's report, branch `m5-02-long-songs` (from main at e1ebc5a). Paths are cut to the dev machine's golden folder
(`golden/...`) and the session's scratch folder (`<scratch>/...`).

## Commits

| commit | what |
|---|---|
| 4ff724c | the change: `engines/autochart.py` (detection, the continuation, the cache rule), new `engines/stitch.py`, the guitar stage's warnings, log lines and record in `pipeline.py`, `eval/golden.py`'s `ENGINE_FILES["guitar"]` + stitch.py, the tests |
| a8cdb35 | a test of `playing_until` (a mutation of its threshold was not caught before); the guide's section 5 sentence |
| d3a5778 | an existing test that compares the whole `takes` record now holds the three new fields (CI's first run caught it) |
| 148f15d | DESIGN.md 2.7 (a new subsection with the stress and token-path numbers), the caps line, 8.1's G9 row |
| 34d6a79 | review fixes (below) |
| cbf7be5 | merge of origin/main (M5-01 merged) |

## What changed

- **Detection** (`autochart.cut_short`, `autochart.budget`): a run is cut short when its summary's `runs[0].nTokens`
  reaches the summary's `maxTokens` (or the models' manifest's `stages.transcriber.modelConfig.maxTokens`, when
  lower: the engine reads its budget only there) or `runs[0].nBeats` reaches the manifest's `maxBeats` (else 1280).
  Reason "tokens" or "beats", recorded in `Take.cut_short`.
- **Continuation** (`autochart.continue_take`): T = the whole-song run's last note; B = floor(T) - 1 (`KEEP_BACK`);
  `seed_<seed>/piece_<k>/input.wav` holds the decode from max(0, B - 8 s) to the end (read and written with
  soundfile at the decode's subtype: the same samples); one more driver run with the same seed, env, timeout and work
  folder (the driver makes the fresh job folder), its summary checked against a key of the piece's own SHA-256. A
  piece cut short again continues (up to `MAX_PIECES` = 6); a cut-short piece that advances under 20 s ends the loop
  ("stalled"); `ended` is "end", "stalled", "max_pieces" or "no notes". T = 0: no piece, the engine's files left as
  they are, a `stitch` record with `pieces: []` written into its summary.
- **Stitching** (`engines/stitch.py`): the base is read raw (importers' `_parse_chart`) so its notes before B keep
  their exact ticks, lengths, flips and taps; its tempo map is the stitched take's (written back without anchors,
  as the engine writes it). Pieces are read with `read_song`, moved by their start, kept from their B (a note at B
  is the piece's only; times within 1e-6 s count as equal) to the next piece's B, converted with the base's
  `sec_to_tick` (rounded), sustains too; a sustain over a seam ends 60 ms before it; taps kept; a flip where the
  piece's state differs from `quantize._natural` on the stitched sequence. Pieces' phrases dropped; the base's
  phrases that start before B kept, ending before B. Decision of mine, not in the order: a piece with no note at or
  after its B moves no seam (otherwise the earlier source's last second would be lost for nothing).
- **Files:** the engine's own output moves to `seed_<seed>/cut_short/`; the stitched chart is written with
  chart.py's writer; `autochart_run/summary.json` = the whole-song summary + `stitch` (`cut_short`, `device`,
  `cut_at_s`, `pieces` [start_s, keep_from_s, last_note_s, nTokens, nBeats, seconds, devices, cut_short],
  `last_note_s`, `ended`); take.json last. A run that starts again clears `cut_short/` and `piece_*/` first (needed:
  a run cut off after the move would otherwise fail on the next one).
- **Cache:** `_done` treats a cached take cut short without a `stitch` record (v0.1's) as a miss; the key is
  unchanged. `_on_device` and `Take.devices` count the pieces' devices.
- **Errors:** a piece's failure is the take's ToolError with the same first words, `autochart seed N failed (exit
  C) in piece k (its audio from m:ss):` or `... did not finish within S s in piece k ...`, so `pipeline.failure`
  classifies it as M5-05 does (brief change 2): a GPU failure in a piece takes the chart's one CPU retry (the take
  runs again whole on the CPU and is continued) and counts against `CPU_RETRIES`; killed, timed out and driver
  failures are raised as M5-05 says.
- **Pipeline** (the guitar stage only, plus `log` passed into `_engine_stages`): the warning `guitar take seed N:
  the engine's budget ran out at m:ss of M:SS (R); the rest was transcribed in K more piece(s), to m:ss` (R: "1280
  beats" or "8192 tokens"); a log line per piece; `record["takes"]` gets per-take lists `cut_short`, `pieces` (a
  count) and `last_note_s`. The "ends at" warning when `ended` is "stalled" or "max_pieces" (the order names the
  20-s rule; I added the sixth piece still cut short) and the take's last note is 10 s or more before the guitar
  stem stops playing (`playing_until`: its last 0.1-s frame within 15 dB of its P95, preview's measure; the stem
  read from disk only then).
- **Docs:** DESIGN 2.7 "A take cut short by the engine's budget: continued and stitched (M5-02)", the Caps line,
  8.1's G9 row; the guide's section 5 sentence. PROGRESS.json not touched (the brief).

## Checks

### The suite

- Local, `tools/heavy.sh uv run python -m pytest -q -p no:cacheprovider --basetemp=/dev/shm/pt-m5-02` on the
  branch's code (unchanged since d3a5778): `946 passed, 3 skipped in 712.69s (0:11:52)`.
- CI run https://github.com/neb882/song-charting/actions/runs/42106182847 on 148f15d (the branch's head):
  **success**, Linux suite `945 passed, 4 skipped in 461.40s`, all hooks passed. Before it, run
  https://github.com/neb882/song-charting/actions/runs/42079623229 on d3a5778: **success**. Linux suite
  `945 passed, 4 skipped in 452.86s`; `all 7 Linux hooks passed`; Windows `all 1 Windows hooks passed`. The first
  run (42077845196, on a8cdb35) failed one test (`test_takes_follow_the_guitar_stages_device` compares the whole
  takes record), fixed in d3a5778. No hook of this order's own: its checks are suite tests.
- New tests: tests/test_stitch.py (5), tests/test_engines_autochart.py (+9: both caps' paths, two pieces, the
  20-s rule, MAX_PIECES, a failed and a timed-out piece, under both caps byte-identical, the v0.1 cache rule and T =
  0, a piece on another device, the budget from the manifest, leftovers cleared), tests/test_pipeline.py (+4: the
  warning and record, the "ends at" warning, a failed piece and the CPU retry, `playing_until`).

### The tests fail when their code is broken

Each break applied alone to a copy of the code (outside the worktree, so the golden runs never saw it), the
relevant tests run: 40 breaks, 40 caught.
- stitch.py (11): base keeps notes at B; piece not shifted; base sustain not clipped; piece sustain not clipped at
  the next seam; no flips; taps dropped; ticks truncated; no stop at the next seam; an empty piece moves a seam;
  base phrases not clipped; base flips dropped.
- autochart.py (18): tokens rule strict (`>`); no beats rule; the manifest's budget ignored; context 9 s; keep from
  floor(T); no 20-s rule; a piece cut short not continued; MAX_PIECES 7; the v0.1 cache rule gone; T = 0 without a
  record; engine output copied, not moved; take.json written before the continuation; a piece's error without its
  exit code; Take.devices ignoring pieces; `_on_device` ignoring pieces; leftovers not cleared; a piece's summary
  checked against the take's key; a piece's audio from 0 s.
- pipeline.py (10): no budget warning; no piece log lines; no record field; "ends at" for any end; its gap 0; never;
  the playing threshold -60 dB (missed at first, caught after a8cdb35's test); retries unlimited; no retry for an
  engine failure.
- Not broken: the determinism test (two stitches byte-identical) has no code path to break short of adding
  randomness; it guards against one.

### Golden charts (`--rerun guitar` on both sides, `--expect none`)

Base: a detached worktree of main at e1ebc5a (`--code`); new: the branch at d3a5778 (DESIGN.md uncommitted, the
only dirty file). Threads 2, kept folders `golden/work` (made by fbd9751).

```
golden diff: no UNEXPECTED change; report: golden/m5-02-new/report.md      (exit 0)
```

report.md: "Expected to change: none. **No UNEXPECTED change.** Parts changed as expected: 0. Every song's results
(hashes, counts, scores) identical: yes." Engines that ran: guitar on 7 songs, both sides. Pooled F1@50 unchanged:
guitar Expert 0.8527 (6 songs), Hard 0.8010, Medium 0.7474, Easy 0.6150; bass Expert 0.8247; drums Expert 0.9617;
beat F1 0.8755. Per song every part "unchanged" (onsets and F1@50 equal); no piece or budget line in any song's log.

The references' budget use (each kept take's summary, the same takes the reruns made):

| song | nTokens | nBeats |
|---|---|---|
| lucretia | **3906** (the largest) | 434 |
| test_song | 3581 | **933** (the largest) |
| kimochi_warui | 3328 | 519 |
| take_me_out | 2331 | 453 |
| all_the_small_things | 1914 | 431 |
| creep | 1883 | 365 |
| drunk_drivers | 1869 | 435 |

### The stress check (M5-09's set, 1 CPU take, threads 2)

Before: M5-09's baseline `golden/stress-base` (main at fbd9751). After: `golden/m5-02-stress` (`--rerun guitar`,
d3a5778). `stress.py compare stress-base m5-02-stress`: **0 regressions**; troop and break every number identical;
`golden diff ... --expect guitar`: troop and break every guitar level "unchanged", sooth's four guitar levels
changed (its one UNEXPECTED is procedural: the baseline did not rerun guitar, so its take came from the kept folder).

| line | before | after | pass |
|---|---|---|---|
| `cut_short` and its reason | none | "beats" (nTokens 6543, nBeats 1280) | yes |
| the warning | none | `guitar take seed 20260609: the engine's budget ran out at 8:52 of 9:09 (1280 beats); the rest was transcribed in 1 more piece, to 9:08` | yes |
| the take's last note | 532.29 s | 548.92 s (the built chart's last guitar onset 545.97 s: assemble drops onsets where the stem is silent) | yes: within 5 s of the primary's ref span end, 545.96 s, and later |
| guitar recall@100 after the old cut, vs primary (532.29–545.96 s) | 0 of 31 | 28 of 31 = **0.903** | yes (≥ 0.60) |
| the same vs alt1 (532.29–541.55 s) | 0 of 22 | 17 of 22 = **0.773** | yes |
| 30-s windows F1@100, vs primary | lowest 0.500; last 0.652 | last 0.786, the other 17 identical | yes (no drop) |
| the same, vs alt1 | last 0.656 | last 0.783, the other 17 identical | yes |
| whole song F1@50 / F1@100 vs primary | 0.651 / 0.789 | 0.658 / 0.795 | yes |
| the same vs alt1 | 0.765 / 0.790 | 0.770 / 0.795 | yes |
| the seam (onsets in [B - 1, B + 1], B = 531 s) | — | stitched 10, whole-song run 10, piece 10 (max, not the sum 20); none closer than 20 ms; none that both have missing at 50 ms | yes |
| troop (power-metal): runs, pieces, chart | 1 run | 1 run, no piece, every number and hash identical | yes |
| break (rock): the same | 1 run | 1 run, no piece, identical | yes |

The owner's 4-take CUDA figures before this change, beside these: guitar 0.636 / 0.743 and 0.725 / 0.748.

**How the span recall is counted** (`<scratch>/m5-02/span.py`): score.py itself, run twice per chart: once plain
(its `ref_span_s`), then with `--windows W`, W = 532.294 - the span's start, so its windows are exactly [start,
532.294) and [532.294, end]; score.py counts a matched pair (±100 ms, its one-to-one matching) in its ref onset's
window, so the second window's `matched / n_ref` is the recall after the cut. 532.294 s is the baseline's last
guitar note on input.wav's time (its take's last note; its chart's, less score.py's lag, agrees to 4 ms). Only
numbers are printed; the human charts are read by score.py alone.

**The pieces' sizes and times:** one piece, 26.3 s of audio (523.0–549.3 s), kept from 531.0 s, 246 tokens over 70
beats, 19 s in the stress run (24.9 s when re-run alone), not cut short (`ended: "end"`); the guitar stage took
1145 s in all (the whole-song take most of it). The stitched take has 2242 Expert onsets against the whole-song run's
2201.

**The seam's charts:** golden deletes a run's work folder, so the seam was counted on the same take made again by
`<scratch>/m5-02/seam.py`: `autochart.generate` with a `run` that puts the kept whole-song take's files in place
(the same input, seed and settings) and runs the real driver for the piece. Its piece and stitched take match the
stress run's (246 tokens, 70 beats, last note 9:08, 2242 onsets).

### The token-budget path on real audio

Done without touching the driver or the key code: autochart.py cannot lower the budget (the engine reads it only
from the models' manifest), but `cut_short` reads that manifest's `maxTokens` too, so a scratch install whose
models' manifest says 4096 (every other file a symlink to the real install; its own install key, so its takes never
mix with real ones) makes the engine stop at 4096 tokens and the take be seen as cut short. Run: `songcharter chart`
of the shred instrumental's input.wav, 1 take, CPU, threads 2, `--levels all --no-preview`, through heavy.sh, with
`SONGCHARTER_AUTOCHART` at that install and a work folder made from the kept one (decode and stems hard-linked, the
drums, bass and sections folders copied, no guitar). The engine's log shows `max_tokens=4096`.

| line | the stress baseline (8192 tokens, beat cut at 532.3 s) | the token-cut run (4096) | pass |
|---|---|---|---|
| `cut_short`, the warning | — | "tokens" (nTokens 4097); `the engine's budget ran out at 5:49 of 9:09 (4097 tokens); the rest was transcribed in 1 more piece, to 9:08` | yes |
| the whole-song run's notes before B (348 s) | — | identical to the 8192-token take's (1310 notes) | yes |
| the piece | — | from 340 s (209 s of audio), 2831 tokens, 505 beats, 274 s, not cut short | — |
| the take's last note | 532.29 s | 548.94 s | yes |
| recall@100 after its cut (349.53 s to the span end), primary / alt1 | 698/892 = 0.783, 717/971 = 0.738 (the baseline was not cut there) | 750/892 = **0.841**, 778/971 = **0.801** | yes |
| whole song F1@50 / F1@100, primary | 0.651 / 0.789 | 0.668 / 0.804 | yes |
| the same, alt1 | 0.765 / 0.790 | 0.786 / 0.806 | yes |
| 30-s windows F1@100 vs the baseline, primary | — | 336 s window (the seam's) **-0.024** (0.793 → 0.769: 1 match fewer, 8 onsets more), 366 s -0.003; the five later +0.006 to +0.170 | **no** (by 0.004) |
| the same, alt1 | — | 332 s -0.017, 362 s -0.020 (at the limit), the later five +0.010 to +0.161 | yes |
| the seam, [B - 1, B + 1] = [347, 349] s | — | stitched 1 onset, the whole-song run 3, the piece 1: the piece's; none doubled; none both runs have and the stitch lacks | doubling rule yes; "max of the two" no |

So the continuation recovers the rest on the token path too (recall 0.84 / 0.80 in the 196 s after the cut, both
whole-song F1s up), but the window holding the seam is 0.024 below the continuous decode's against the primary: the
piece is a fresh sampled decode of 340-366 s (it differs from the continuous one as another seed's take would), and
in the second after B it heard one onset where the continuous decode had three. That comparison exists only in this
test: a song really over the budget has no continuous decode to compare with.

## Not done, or uncertain

- The "ends at" warning also fires after the sixth piece still cut short (not only on the 20-s rule); a piece not
  cut short that finds nothing more gives no such warning (the engine's own verdict on the tail).
- `cut_short` reads the models' manifest's maxTokens too (the min with the summary's): the same 8192 by default; it
  is what lets a lower budget be seen, and changes nothing otherwise.
- The stress "before" is M5-09's baseline (main at fbd9751, the kept takes); the runs since then (M5-05) did not
  change a chart, as the golden diff shows for the references.
- A v0.1 take cut short in the friend's cache runs again whole once (the order's rule), costing one take's time.

Scanned `git diff main...HEAD` and the commit messages for lyrics, audio, model names and personal details before
the final push: none (test fixtures use made-up names).

## Review fixes

The review (one major confirmed by a skeptic with the real driver and engine, three minor test gaps):

- **F1 (major): the token path never ran on a real install.** A job that uses the engine's whole token budget ends
  at budget + 1 tokens (Fretformer 2's 9-token prefix, sampled only after it), and the driver's watchdog
  (`AC_MAX_TOKENS`, default 8192, the budget itself) kills exactly those jobs: such a take failed as M5-05's TOKENS
  driver failure. My token-path run above did not meet it because its halved budget (4096) was under the driver's
  default cap. Fix: `generate` sets `AC_MAX_TOKENS` to the budget + `WATCHDOG_MARGIN` (16). The env is in neither the
  take's key nor the install key, `_summary` does not compare `maxTokens`, and `cut_short` takes the lower of the
  summary's and the manifest's (the budget), so its answers are unchanged and no cached take runs again. The tests'
  `CutDriver` now models the engine's count (budget + 1) and the driver's kill (exit 1, the TOKENS lines, no summary,
  when the count passes the env's cap, default 8192): `test_a_take_cut_short_is_continued_and_stitched[tokens]`
  fails without the fix and passes with it; the test asserts the env's cap is above `budget()[0]`. The v0.1 cache
  test's take is now beat-capped (v0.1 could make no token-capped take). DESIGN 2.7: the owner's 4 takes stopped at
  498.6 s on the **beat cap** (beat 1280 of their grid at 498.65 s), not the token budget, as this report's first
  version also said; a bullet on the watchdog.
- **F2:** stops [40, 70, 75] end "stalled" after 2 pieces (3 runs); measuring the advance from the whole-song run's
  last note fails it.
- **F3:** `stitch_lines` with `ended` "max_pieces", "stalled" and "end": the "ends at" warning for the first two
  only, the stem read only then, none within 10 s of the stem's end; dropping "max_pieces" fails it.
- **F4:** (a) a whole-song run on the CPU with its piece on CUDA (CUDA asked) reports the CPU; `if used is not None`
  fails it. (b) a piece note that rounds onto the base's last tick before B, and one 0.4 ticks after another piece
  note, are dropped, never made chords; removing the guard fails it.
- Each break above, applied alone: caught (watchdog removed; cap = budget; F2; F3; F4a; F4b).
- **Checks after the fixes and the merge of main:**
  - targeted: `pytest tests/test_engines_autochart.py tests/test_stitch.py tests/test_golden.py`: 58 passed; the new
    pipeline unit test passed.
  - suite (`tools/heavy.sh uv run python -m pytest -q -p no:cacheprovider --basetemp=/dev/shm/pt-m5-02`, on
    cbf7be5): `968 passed, 4 skipped in 654.74s (0:10:54)`.
  - reference takes: no golden rerun. The env change cannot touch a take that stays under the budget: the driver
    uses `AC_MAX_TOKENS` only in its watchdog check and in summary.json's `maxTokens`, the engine's job.json does not
    hold it, every reference take stays at most 3906 tokens (far below both caps), and the take's key is unchanged,
    so cached takes are hits and a warm run reuses them byte for byte. Checked with one real take made again by this
    code (all_the_small_things, default seed, CPU, threads 2, through heavy.sh): the driver's `maxTokens` was 8208,
    1914 tokens, not cut short, and the chart is identical to the kept take's from [SyncTrack] on (the tempo map,
    the sections and every Expert note). Only the [Song] block's Name and Artist differ, because golden passes the
    song's title and artist and this check did not.
  - CI: https://github.com/neb882/song-charting/actions/runs/42121880233 on cbf7be5: **success**, Linux suite
    `968 passed, 4 skipped in 476.08s`, all 7 Linux hooks and the 1 Windows hook passed.

## Review (sc-reviewer, 2026-11-05)

# M5-02 review (sc-reviewer, continuation-correctness lens)

Branch origin/m5-02-long-songs at 148f15d against origin/main. All breaking was done in a copy (/dev/shm/review_m502, deleted afterwards).

Checked and found sound:
- `_write_piece` is sample-exact for PCM_16, PCM_24 and FLOAT.
- On both real stitched takes (sooth-take, tok), the stitched chart has the base's [SyncTrack] and [Events] unchanged, and its ExpertSingle events before B are byte-identical to the engine's. The only differences are the one sustain clipped at B and a soloend placed before B.
- The cache rule, leftovers clearing, the piece key, the error wording and M5-05's classification match the order.
- Of 16 breaks I made, 7 were caught. The 9 that survived are listed below, or are harmless (seconds reporting, the [Song] tags, a flip on a tap).

## F1 (major): the token path cannot run on a real install. A take that uses its whole token budget is killed by the driver and fails.
- Where: `songcharter/engines/autochart.py`, `cut_short`/`generate` (the "tokens" branch), and `eval/tools/autochart/ac_headless.cjs` lines 129 and 159.
- Cause: the engine's final token count is the budget plus 1. The builder's own run at 4096 reported 4097, and 100 gives 101. The driver's watchdog defaults `AC_MAX_TOKENS` to 8192 and kills the engine when a `partial_chart` tokenCount exceeds it.
- Effect: with the default budgets (8192 for both), a run that reaches the token budget never completes. It fails with `FAILED: expert: token cap 8192 exceeded (8193)`, which is M5-05's TOKENS fixture: a "driver" failure, exit 2, no retry. So `continue_take` is never reached on the token path.
- Why it was missed: the unit tests' stand-in writes a completed run with nTokens 8192. The builder's real token run lowered only the models' manifest (4096) and left the driver's cap at 8192, which bypasses the watchdog.
- Only the beat path works. Dense songs that hit tokens first (Lucretia uses about 9 tokens a beat) fail the whole chart. DESIGN 2.7 and G9 describe the token path as working.
- Side note: the owner's 4 CUDA takes all stopped at the same 498.6 s whatever the seed. That points to the beat cap, not the token budget.
- Fix direction: pass `AC_MAX_TOKENS` above the engine's budget (for example caps[0] + 1) in the driver's env. The env is not in the take's key, but the summary's `maxTokens` would change. Add a stand-in test that kills at the cap.
- Repro: /dev/shm scratch install with the manifest at maxTokens 100 (files symlinked), `AC_MAX_TOKENS=100`, `autochart.generate` on a 30-s clip of a stress song's decode.wav, CPU, through heavy.sh:
```
budget (100, 1280)
TOOLERROR autochart seed 20260609 failed (exit 1):
[autochart] expert 2.0s transcription: decode loop (device=cpu, ... max_tokens=100)
[autochart] expert: killing engine: token cap 100 exceeded (101)
[autochart] FAILED: expert: token cap 100 exceeded (101)
```

## F2 (minor): the 20-s rule's test can be gutted.
- Where: `autochart.py` `continue_take`, `if reached - last < ADVANCE_S`.
- Break: measure the advance from the whole-song run's last note (`base_last`) instead of the previous piece's.
- Result: 23 passed. The stall test stalls on the first piece, so it never tells the two apart.
- What would ship: a piece that advances 5 s after an earlier 30-s advance keeps the loop going, up to 6 engine jobs (minutes each on the CPU). It is then labelled "max_pieces", not "stalled".
- Missing test: stops [40, 70, 75] should end "stalled" after 2 pieces.

## F3 (minor): the "ends at" warning after the sixth piece is untested.
- Where: `pipeline.py` `stitch_lines`, `ended in ("stalled", "max_pieces")`.
- Break: drop "max_pieces". Result: `test_a_continuation_that_stops_short...` and `..._cut_short_is_warned...` both pass (2 passed, 55 s).
- This is the builder's own decision, so the warning it adds is unguarded.

## F4 (minor): two stitch/device guards whose tests can be gutted.
- (a) `Take.devices`: change the condition to `if used is not None:`, so any piece's device overrides. Result: 23 passed.
  - What would ship: when CUDA was asked, the whole-song run fell back to the CPU and a piece ran on CUDA, the take reports CUDA. The pipeline's fallback record and warning are then skipped.
- (b) `stitch.stitch`: remove the `tick <= prev.tick: continue` guard. Result: 23 passed.
  - What would ship: a piece note that rounds onto the base's last tick before B (or onto the previous piece note) becomes a second note on the same tick, which Clone Hero reads as a chord.
  - It is rare, but nothing tests it.

Files: songcharter/engines/autochart.py, songcharter/engines/stitch.py, songcharter/pipeline.py, tests/test_engines_autochart.py, tests/test_pipeline.py.

## Skeptic on F1 (sc-skeptic, 2026-11-05)

# M5-02 skeptic: F1 (a take that uses its whole token budget is killed by the driver)

Verdict: **CONFIRMED, major.** I could not refute it. The arithmetic is exact, and a real run fails every time.

## The engine's count (src/engine/lib/onnx/transcribe.mjs, pipeline.mjs)
- The loop runs from step 0 to totalLimit - 1, where totalLimit = min(maxTokens, prefixLen + maxTokens) = maxTokens.
- Fretformer 2 has sampleOnlyAfterPrefix true and a 9-token prefix (BOS, difficulty, 5 knobs, SOLO flag, SECTION flag). Sampling starts at step 8, so the final tokenList.length is 9 + (maxTokens - 8) = **maxTokens + 1**.
- `onProgress` fires on `step + 1 === totalLimit` with done = true, and pipeline.mjs passes it on as a `partial_chart` whose tokenCount is maxTokens + 1.
- Every earlier partial is at most maxTokens. A run that ends on EOS before the budget is also at most maxTokens. So the only run that crosses the cap is one that uses the whole budget, and that is exactly the run M5-02 must continue.
- The driver (ac_headless.cjs lines 129-137) kills when the partial count is above AC_MAX_TOKENS. This is not a race: stdout is drained before `close`, and `killedFor` makes it fail whatever the engine's exit status.
- autochart.py's env never sets AC_MAX_TOKENS, so the driver uses its default of 8192, the same as the models' manifest. M5-05's TOKENS fixture ("token cap 8192 exceeded (8193)") is this exact failure, and it is classified as a driver failure: exit 2, no retry.

## Reproduced (real driver and engine, CPU, through tools/heavy.sh)
- Setup: a scratch install with the models' manifest at maxTokens 150 and every other file symlinked; a 30-s clip (60-90 s) of the stress shred song's decode.wav; `autochart.generate` from the worktree's code.
  - A, the branch, with the driver cap equal to the budget (150, the same relationship as a default install's 8192/8192): `TOOLERROR autochart seed 20260609 failed (exit 1): ... killing engine: token cap 150 exceeded (151) / FAILED`. `continue_take` is never reached.
  - B, a copy patched with `AC_MAX_TOKENS = caps[0] + 1` and no outer AC_MAX_TOKENS: completed, cut_short "tokens", nTokens 151, driver maxTokens 151. It was continued in 1 piece (from 8.0 s, also cut at 151) and ended "stalled". The last note moved from 17.37 s to 25.97 s. take.json has the same 7 key fields.
  - Control: at budget 300 the clip ended on EOS at 264 tokens and 75 beats. It was not killed under either variant.

## The owner's v0.1 takes
- They completed under this same driver. The driver's history is one commit, so it is unchanged since v0.1, and its cap is 8192 against a budget of 8192.
- By the arithmetic above, a take that reached the token budget could not have completed. So none of the owner's takes reached it.
- The stop at 498.6 s does not depend on the seed and matches the 1280th beat. From the report.json grid, which is numbers only (first beat 0.0162 s, median 153.90 BPM): 0.0162 + 1279 x 60/153.90 = 498.65 s. The takes were **beat-capped**.
- The order's wording ("stopped at 498.6 s on the token budget") is wrong. DESIGN 2.7's "dense songs hit the token cap first" is the case that fails today.

## Fix (autochart.py only; not the driver)
- In `generate`'s env, add `"AC_MAX_TOKENS": str(caps[0] + 16)`.
  - +1 is exact for this model. +16 also covers a model without sampleOnlyAfterPrefix, which ends at prefixLen + budget.
  - The engine bounds its own loop, so a higher watchdog cap loses nothing.
- Key and cache: the take's key (take_key, install_key) holds no env and hashes the driver file, which is unchanged. `_summary` does not compare maxTokens. `cut_short` takes min(summary maxTokens, caps[0]) = caps[0], so it gives the same answer for an old summary (8192) and a new one (8193 or 8208). I checked this: "tokens" for 8193 tokens, None for the reference take troop's 5805. No reference take is rerun.
- Stand-in test: make the tests' `CutDriver` model the driver.
  - For by="tokens", the final count is the budget + 1 (8193).
  - If that is above `int(env.get("AC_MAX_TOKENS", 8192))`, return exit 1 with the TOKENS stderr and write no summary. Otherwise write nTokens 8193 and "maxTokens" = that cap.
  - Then `test_a_take_cut_short_is_continued_and_stitched[tokens]` fails on 148f15d and passes with the fix.
  - Also assert that generate's env has AC_MAX_TOKENS above `budget()[0]`.
