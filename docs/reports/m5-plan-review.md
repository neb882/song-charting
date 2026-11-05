# The M5 plan's review: the advisor and the skeptics (2026-11-05)

The advisor reviewed the M5 plan (branch m5-plan at eab879a) against the conventions report, the feel note and the code; three findings that changed an order's scope each went to a skeptic. The plan was amended on all of them (M5-00).

## Advisor review: the M5 plan (branch `m5-plan` at eab879a)

*2026-11-05. Read-only review at the planning gate (docs/PIPELINE.md, Gates). I read M5-00 to M5-09 and M5-99 at eab879a
(the revision after the conventions report), the PROGRESS diff, the brief, the conventions report, the orchestrator's
feel note, and the code the orders touch. I ran a few small probes under /dev/shm (now deleted). They read the human
charts' notes and tempo maps only, in memory, and printed no text from any chart. One fact for the rule section: a
scratch "ref" folder still holds lyric events (finding 8). No order was edited.*

Severity: **blocks** = fix before the build starts; **should** = change before the build; **note** = for the
builder, the reviewer or the gate. **Scope** means the change alters what an order builds, so it gets a skeptic
before anyone acts on it.

### The probes, in one place

All of these are on the power-metal song (`troop`) unless named, using songcharter's own `beatgrid`, `quantize`,
`importers` and `eval/scorer/score.py`.

| probe | result |
|---|---|
| `beat_grid` on the package's mix (no stems on the dev machine), then a second pass at 2x the click tempo with the fold range patched to 170-370 | default: 100 BPM, F1@70 0.35 against the human map. Second pass: 200 BPM, **F1@70 0.99, median error 8 ms**. Confident share **0.208 → 0.113** |
| the human guitar chart (2,495 onsets, 3.8 % chords) quantized on that doubled grid with today's rules, as a stand-in for a perfect engine | 1,865 kept, **485 dropped by the 80/55 ms floors (19 %)**, 145 merged, **10.4 % chords**. F1@50 against its own raw chart **0.854** |
| the same with the floors at 16 ms | 2,336 kept, 0 dropped, 9.1 % chords, F1@50 **0.965** |
| M5-01 step 5's floors as written: the pooled 1st percentile of the gap before each note, by its played state, over the 7 reference and 5 stress charts | strum p1 **75.0 ms → floor 74 ms**; HOPO/tap p1 37.5 → 37 ms. On the power-metal charts, **914-1,194 gaps per chart lie within 2 ms of the 74 ms floor**. The shred chart <sooth alt1> still loses 55 strums (2.3 %) |
| the human charts scored against each other (score.py, lag-aligned) | F1@50 **0.917-0.922**, timing 9 ms. HOPO share **0.21, 0.51, 0.29** across the three charts. Direction agreement 0.71-0.77 |
| shred song (`sooth`), our chart's report | guitar quantize dropped **0**, merged 50 of 2,187; our chart's shortest gaps are about 94 ms |
| human solo spans (counts and times) | measures 8, 32 (refs); 4, 4, 52 / 52 / 4, 4, 15, 52 (power-metal); 31, 32 (shred, one chart; the other has none). Largest share 0.36 |

### Findings, ranked

#### 1. M5-01 step 5 sets the strum floor 1 ms under the power-metal song's 16ths. Blocks; scope.

- **Evidence.** M5-01:105-108 sets `STRUM_SPACING_S` to "the pooled 1st percentile of each state rounded down to a millisecond, never under 0.020 s".
  - Measured, that rule gives 74 ms. The pool is dominated by the song the floor is meant to fix: its human charts strum 16ths at exactly 75.0 ms (200 BPM).
  - Our grid is free mode. It follows the drummer, with tempo steps of up to 2 % a beat (`beatgrid.MAX_TEMPO_STEP`), so snapped 16ths come out at about 73.5-76.5 ms.
  - So hundreds of notes are kept or dropped by grid jitter. The pass line "`dropped` plus `dropped_distinct` under 2 %" (M5-01:143-144) becomes a coin toss.
  - The rule still deletes the shred chart's human strums at 62.5 ms.
- **Why it matters.** The report's rule is plain: nothing but `brokenNote` (15 ms) asks for a floor (conventions §2g, §11 item 2). On a grid at or under 300 BPM, two distinct slots are at least 50 ms apart (a 1/16 at 300 BPM). So any floor above about 50 ms can only delete real notes. The stand-in shows how much is at stake: the floors alone cost 19 % of a perfect engine's notes and about 0.11 F1.
- **Smallest change.** Fixed floors of 0.020 s for both states (brokenNote plus a margin), with an onset under the floor dropped as now. Keep the human-gap table as evidence for DESIGN 2.6, not as the setting.
- **Scope:** yes, it changes the rule M5-01 builds.

#### 2. M5-01 step 4 moves the second note up to a slot late. Should; scope.

- **Evidence.** M5-01:93-98: two onsets more than 20 ms apart on one tick are not merged; "the later one moves to the next slot when that slot is free".
  - At 120 BPM a 1/16 slot is 125 ms, so a note 25 ms after its neighbour lands about 100 ms late.
  - Today `_separate` moves only onsets at least 0.75 slot apart (`quantize.py:536`), so a moved note stays within about a quarter slot of its time.
- **Why it matters.** The convention is "drop before you merge" (conventions §2c). The feel note's first rule is that a note 60 ms off feels worse than a missing one. Every ordinary rock song with 32nd pickups or engine double-onsets goes through this path. The golden's F1 line catches only large damage.
- **Smallest change.** Between 20 ms and `rules.separate` slots apart: keep the onset nearest the tick, drop the other and count it in `dropped_distinct`. Moving stays with `_separate`'s existing rule. The test "50 ms apart become two notes on consecutive slots" becomes "the farther one is dropped".
- **Note.** On the stand-in, about 145 human notes (5.8 %, the 37.5 ms 32nds and 50 ms sextuplets) would land in `dropped_distinct`. So M5-99's 1 % trigger for burst slots may fire if the engine catches the bursts. That is the plan working as intended; say so in the order.
- **Scope:** yes.

#### 3. M5-01's guitar F1@50 line is absolute, taken from 4-take numbers, and judged on 1-take runs. Should.

- **Evidence.** M5-01:145-146: "at least 0.70 against each human chart (0.58-0.59 today)". Those are the owner's 4-take GPU figures. The same order says to compare with M5-09's 1-take baseline (M5-01:152-153).
- **What the data says.** The humans agree at 0.92 at 50 ms, and a perfect engine through the fixed quantizer reaches about 0.96 against its own chart. So 0.70 is reachable in principle. But the 1-take CPU starting point is unmeasured, so the line may end up measuring the take count rather than the fix.
- **Also.** "Matched notes' median timing error under 25 ms" is loose. Bass and drums sit at 1-5 ms and the humans at 9 ms.
- **Smallest change.**
  - F1@50 at least M5-09's 1-take baseline + 0.10 against every chart, with the 0.70 and the humans' 0.92 reported beside it.
  - Timing error under 15 ms.
- **Scope:** no (pass lines only).

#### 4. The stress table cannot see articulation, contour or measure lines, though the scorer already computes most of them. Should; small scope (M5-09).

- **Evidence.** M5-09:47-51 lists F1s, chord share, timing, density, beat F1 and the lowest window. Yet `score.py` already writes these for every part:
  - `hopo_share`, `tap_share` and `sustain_share`;
  - `lane_direction_agreement` (contour; 0.71-0.79 between humans on these songs).
- **Why it matters.**
  - M5-01 step 6 is meant to inform the `forced`-or-`source` decision (conventions gap 4). But the humans' HOPO shares on the power-metal song are 0.21, 0.51 and 0.29, and the order cites only 0.51. A share against one chart cannot decide it.
  - M5-01 also moves the bar phase on doubled grids, and nothing scores measure lines (feel §8).
- **Smallest change, in M5-09.**
  - Print the four existing fields in the table.
  - Add per-matched-note state agreement (strum, HOPO, tap) to `score.py`. It already matches the notes, so about an hour.
  - Add downbeat F1 beside beat F1.
  - Then M5-01 step 6 reports state agreement for `forced` and `source`, and the owner can decide at the gate if the numbers are clear.
- **Scope:** yes, small (M5-09).

#### 5. M5-01's confident-share guard is a guess and could veto the fix on the song it is for. Should.

- **Evidence.** M5-01:82-83: "Keep the second grid only when its confident share is at least the first grid's minus 0.10".
  - On the mix, the right-tempo second pass fell from 0.208 to 0.113 (−0.095) while its beats went to F1@70 0.99 against the humans.
  - A doubled grid adds beats with less drum evidence by nature. The drum-stem value (0.815 on the owner's run) after doubling is unknown.
- **Smallest change.**
  - Run the second pass on every song of the threshold table and record both shares.
  - Set the guard from that table (a ratio may fit better than a difference).
  - Stop and report if it vetoes the power-metal song.
- **Builder detail.** `beat_grid` does not return its `OnsetFeatures`, and assemble calls it with audio (`assemble.py:1292`). Compute the features once in assemble and pass `features=` to both passes and to the backbeat test.
- **Positive.** The probe supports the plan's claim that the second pass finds the beat phase by itself ("which fixes the half-beat offset", M5-01:81), on the mix at least.
- **Scope:** no.

#### 6. M5-01's threshold needs engine charts the dev machine does not have yet. Should (sequencing).

- **Evidence.** M5-01:72-74 offers `<S>/troop/ours` and `<S>/sooth/ours` until M5-09 exists, "read their `report.json` parts' sources, or chart them". The problems:
  - Those sources are paths on the owner's PC; none exist here.
  - `ours/notes.chart` is after the merge: its shortest gap is 142 ms, so the density statistic reads near 0.
- **Consequence.** `OCTAVE_SHARE` can only be set once M5-09's baseline run has produced the stress songs' engine charts. The half-tempo group then has one member (the power-metal song).
- **Smallest change.** M5-01 step 2 waits for M5-09's `stress-base` kept folders (M5-00's wave 1 note says only the "final numbers" use them). The report states the threshold rests on one positive example.
- **Builder detail.** Say whether "each charted part" includes drums in the density test.
- **Scope:** no.

#### 7. After the update, a take cut short in v0.1 is reused unstitched. Should; small scope (M5-02).

- **Evidence.**
  - The take key is the input, seed, settings and install, not songcharter's code (`autochart.py:146-172`).
  - `_done` reuses any take with that key (`:190-226`).
  - M5-02 detects a cut "after a run" (M5-02:27-30).
  - M5-07 checks that the work cache survives an update.
- **Consequence.** A long song the friend charted in v0.1 comes back with the same lost ending and no warning.
- **Smallest change.** `_done` treats a cached summary with `nTokens >= maxTokens` (or `nBeats >= 1280`) and no `stitch` as unfinished, so the continuation runs. Add one test.
- **Scope:** yes, small.

#### 8. Lyrics hygiene: scratch "ref" folders still hold lyrics, and `<out>.failed` sits outside the temporary folder. Should (rules).

- **Scratch refs.** `<S>/troop/ref_<troop alt2>…/ref/notes.chart` holds 409 lyric events. The scratch refs were not stripped the way `build_refs.sh` strips `ref/`. M5-03:31 points at `human_*`, the full packages with vocals; M5-01 step 5 reads "the five stress charts".
  - Change: before M5-09 merges, treat every scratch folder as a package under M4-10's exception (in memory, numbers only). After it merges, read only `$EVAL_DATA/stress/` refs.
- **The `.failed` folder.** `stress.py lyrics` (M5-09:54-59) runs `pipeline.chart` into a temporary folder. On a failed gate the chart, words included, goes to `<out>.failed`, beside `out` (`pipeline.py:4`).
  - Change: set `out` = `<tmp>/song` and the work folder under `<tmp>`. Assert that nothing under either survives, in the test with made-up words.
- **Stub stems.** The primary package's `drums.opus` is a 135-byte stub that ffmpeg cannot open; `score.py` failed on it as a candidate.
  - Change: M5-09's build and scorer skip an empty stem, with a test.
- **Scope:** no.

#### 9. M5-03's measured caps come out loose. Note.

- **Evidence.** From the human data: the 95th percentile of solo length is about 52 measures, rounded up to 56, and the largest share 0.36 gives a cap of 0.40.
  - On the shred song that still allows about 3.6 minutes of solo markers. Today it is 7 minutes; one human chart marks 3.2 minutes and the other none.
  - The share cap is set by the shred chart itself.
  - The caps count measures of our map, and the shred map is double the humans' (halving is deferred). So a measure cap there means half the seconds it means on the human map.
- **Change.** Cap in seconds as well, taking the smaller. Show the owner the resulting solo spans on the shred song at the gate; he may want a tighter share for songs with vocals.

#### 10. The release gate plays nothing, and no ordinary rock song is checked by hand. Should (gate).

- **Evidence.** M5-00:123-129, step 8: "the two hard songs charted … their previews looked at". Ordinary rock is the friend's main use. M5-01 and M5-02 change the quantizer, the floors and the take path for every song, and only the golden numbers watch that.
- **Change.** The owner plays three songs in Clone Hero: an ordinary rock song (a reference or his own) and the two hard songs. He answers the feel note's short checklist with times (in sync, readable, hand flow, repeats, anything unfair). About 45 minutes.
- **Scope:** gate only.

#### 11. Notes

- **a. "40-300 BPM" overstates what is built** (M5-01:12-13). The first pass still folds into 85-185; only doubling is added. A pulse under 85 (the shred song) stays at double, with its HOPO, star-power and solo-measure effects. Deferring halving is fine (M5-99 gives the reason), but DESIGN 2.3 should say "doubling only".
- **b. M5-04's constraint contradicts its own ground truth.** "Must fire on every mix run and on no stem run" (M5-04:47-48) clashes with timing as the ground truth if a stem run is bad. Make it "fires on every bad run and no good run". Also, about 6 statistics and their pairwise ORs on 14 runs is room to overfit: prefer one statistic unless an OR's margin is clearly wider.
- **c. M5-01's star-power count roughly doubles on doubled grids** (`round(span / 40 beats)`, `starpower.py`): about 25 one-measure phrases in 5 minutes. M5-01 reports it beside the humans' (:151). Have the reviewer look at it before the gate.

### The feel note: what is missing, which measures are sound, and what belongs in this version

These are findings in the same form; the scope flags apply to the plan.

#### F-a. Sound, already computed, missing from the plan. Should; small scope (M5-09).

These are in `score.py` or `report.json` today:
- chord share (feel 2);
- HOPO, tap and sustain shares (5, 7);
- direction agreement, i.e. contour against the human charts (3);
- plain beat F1 (8);
- solo share (7);
- notes in silence and gaps where the stem plays (6; assemble's silent onsets, the preview's flags).

Change: put them all in M5-09's table now, at no cost, as finding 4 says.

#### F-b. Sound and cheap, belongs in this version. Should; small scope (M5-09).

- Per-note state agreement (5).
- Downbeat F1 (8).
- The jump-size distribution against the humans', and the rate of jumps of 3 or more lanes under 100 ms (3).

Each is chart-only work in `score.py`, about an hour.

#### F-c. Unsound as written. Should (do not adopt as worded).

- **Sync against "the guitar stem's own onsets", aiming at a 10 ms median (1).**
  - The onset envelope's peaks sit about 22 ms after human beat lines by calibration (`beatgrid.ONSET_TO_BEAT_MS`), and distorted-guitar onsets are smeared.
  - Human charts of one song can sit 47 ms apart (the shred song's two charts).
  - Use instead: the matched-note timing against the human charts (humans 9 ms apart on the power-metal song) and `QuantizeReport`'s snap errors.
- **"No strum streams faster than about 12 a second" (5).**
  - The humans strum this song's 16ths at 13.3 a second (75 ms) and the shred song at 16 a second (62.5 ms).
  - A cap would rebuild the 80 ms floor of finding 1.
  - Use agreement with the humans' states instead.
- **Contour "with the pitch track" and chord share "against the stem" (2, 3).** songcharter has no guitar pitch track; the frets come from the engine. Use the human charts.
- **Difficulty fit (9)** has no measure. Leave it to the play test.

#### F-d. Later (M6), with the measure possibly now. Note.

- **Repeat consistency (4).**
  - The measure (repeated-label sections, fret-sequence similarity, set against the human chart's own consistency) is about half a day. It fits M5-09 if the orchestrator has room, else M6.
  - The fix (one take, or the best riff, reused across repeats) needs repeat detection and the larger reference set: M6, as the feel note itself suggests ("measure first").
- **The density curve against the stem's energy (6):** later.

#### F-e. Feel pass lines in M5-01: yes, in a sound form. Should; scope (pass lines).

- Sync: timing error under 15 ms against the humans (finding 3).
- Readability: chord share under 0.10 and moving toward the humans'.
- Articulation: state agreement reported, and not lower than the baseline under the shipped mode.
- No absolute strum-rate cap.

#### F-f. The play test at the gate: this version (finding 10).

### What is fine

- **Scope and order.**
  - The owner's findings each map to an order, and the measured defects are fixed before quality work.
  - M5-09 comes before M5-01's numbers.
  - The deferrals in M5-99 each give a reason.
  - 0.2.0 is well argued.
- **The revision takes up the report's gaps 1-3 in M5-01** (octave, drop-before-merge, floors), measures gap 4 for later, and marks every assumed rule [conventions]. Only how the floors are set and the move-or-drop detail are wrong (findings 1 and 2).
- **Fast-run thinning left to M6 is right on the data.**
  - On the shred song the quantizer dropped 0 notes and merged 50 of 2,187, and our chart's shortest gaps are about 94 ms. The engine sets that density; the 80/55 floors play no part there.
  - So the report's suggestion that they explain part of that song's thinning is not borne out. They do matter on the power-metal song once its octave is fixed.
- **The second pass finds the phase:** F1@70 0.99 against the human beats on the mix.
- **M5-02's design is sound:**
  - the whole run first, a continuation only when the engine cut it short;
  - byte-identical otherwise, checked by the golden with `--rerun guitar`;
  - a seam test and `MAX_PIECES`.
  Finding 7 is a small gap at its cache boundary.
- **M5-05's per-seed calls change nothing for the takes.** `generate()` already runs one driver process per seed (`autochart.py:222-258`). The retry's limits (one per chart; no retry on signals, timeouts or a missing summary) are right.
- **M5-06, M5-07 and M5-08 are concrete and testable:**
  - a short or silent song exits 2 (InputError) instead of 3;
  - no new dependencies;
  - the update check sends only a User-Agent, and `SONGCHARTER_OFFLINE` never fetches;
  - the CI upgrade path and the noise check each come with a check that fails on the old behaviour.
- **Waves.** Never more than two builders; the file ownership is disjoint; every heavy run goes through `tools/heavy.sh`; there is a disk floor.
- **Rules.**
  - The M4-10 exception for the stress packages is written into M5-09, and the tests assert no word appears in any output.
  - `lyrics.json` holds numbers only.
  - Nothing committed but `stress.json` and the scores.
  - Determinism is kept: pieces and retries are seeded, and a CPU-retried take is not reused by a later CUDA run.
- **The owner's questions** are the right ones. Add finding 9's solo share and finding 4's HOPO-mode decision if the numbers are in by the gate.

## Skeptic: advisor finding 1 on the M5 plan (M5-01 step 5's spacing floors)

*2026-11-05. Branch `m5-plan` at eab879a, read-only. Probes in /dev/shm/skeptic_m5_1 (deleted). They read notes and
tempo maps through `eval/scorer/scan_notes.cjs` (no sections, lyrics or vocal tracks) and printed numbers only. No
chart's [Events] or vocal track was opened. The one heavy step, `beat_grid` on the power-metal mix, ran under
`tools/heavy.sh`.*

**Verdict: confirmed in substance, with some details corrected.** Written as it stands, M5-01 step 5 puts the strum floor
exactly on the power-metal song's strummed 16ths. Whether hundreds of that song's notes survive then depends on
tempo differences of 0.01 %. Today's 80/55 ms floors drop 19-26 % of a perfect engine's guitar notes on that song.
A fixed floor of 20 ms drops nothing anywhere and keeps the only guarantee the floors were ever there for.

### 1. Gaps by played state, and what the rule gives

These are the gaps between consecutive Expert note groups, keyed by the second note's state as scan-chart resolves
it (ini modifiers applied). The set is 11 human charts: the six reference songs with a human chart (the test song
has none, so "seven" means six), three power-metal charts and two shred charts.

| charts | state | n | min | p1 | gaps < 80 ms | strummed gaps at 73-77 ms |
|---|---|---|---|---|---|---|
| 6 references | strum | 6,167 | 74.7 | 104.3 | 2 | 2 |
| 6 references | HOPO | 1,977 | 37.0 | 70.2 | 154 | - |
| power-metal <troop alt1> / <troop primary> / <troop alt2> guitar | strum | 1,424 / 1,283 / 1,486 | 50 / 50 / 37.5 | **75.0** each | 891 / 759 / 1,051 | **890 / 757 / 1,046** |
| power-metal <troop primary> bass | strum | 1,636 | 75.0 | 75.0 | 392 | 392 |
| shred <sooth alt1> / <sooth primary> guitar | strum | 1,284 / 1,005 | 62.5 / 60.9 | 62.5 / 65.0 | 120 / 17 | 14 / 0 |
| **pooled, 11 charts** | strum | 15,656 | 37.5 | **75.000** | 20.6 % | - |
| pooled | HOPO / tap | 7,184 / 1,191 | 37.0 / 37.5 | **37.5 / 37.5** | - | - |

- Pooled, 0.90 % of strum gaps lie under 75.0 ms and 20.6 % at or under it. So the 1st percentile lands on the
  power-metal song's mass point of 3,092 gaps at 75.0 ms. The power-metal charts make up 37 % of the pooled strum gaps.
- The rule ("1st percentile rounded down to a millisecond") gives **75 ms** by my computation. The advisor read 74.
  The difference is float noise in the reader, and 75 is the worse of the two.
- The HOPO and tap floor comes out at 37 ms. That is the humans' 32nds at 200 BPM (37.5 ms), which is where M5-99's
  burst slots would put the same problem later.
- The advisor counted 914-1,194 gaps per chart within 2 ms of the floor. By scan-chart's states, 757-1,046 strummed
  gaps per guitar chart lie there, plus 392 on the bass chart. The size is the same.

### 2. What each floor drops from the human charts, and how sensitive that is

Method: each human chart's Expert part goes through songcharter's own `quantize_part` as a perfect engine, with the
default `hopo: "forced"` rules and the floors patched. The grids:
- the human map itself;
- the human map scaled in tempo;
- the human map with seeded beat-position noise;
- the advisor's real second pass: `beat_grid` on the <troop alt1> package's mix with `bpm` = 2 × click (100.22 BPM) and the
  fold range at 170-370. It came out in click mode at 199.9991 BPM, confident share 0.208 → 0.113, the same as the
  advisor's; 98 % of the human beats lie within 70 ms of it. The same pass forced into free mode was also run.

Notes dropped from power-metal <troop alt1> guitar (2,495 notes in):

| grid | 80/55 (today) | 75/37 (the rule) | 74/37 | 20/20 |
|---|---|---|---|---|
| human map (200.000 BPM) | 485 (19.4 %) | **339 (13.6 %)**: float rounding at exactly 75.0 | 0 | 0 |
| human map, tempo x1.0001 / x0.9999 | 485 / 485 | **485 / 0** | 0 / 0 | 0 / 0 |
| human map, tempo x1.005 / x0.995 | 485 / 485 | 485 / 0 | 0 / 0 | 0 / 0 |
| position noise sd 1 ms (beat periods p5/p95 ±0.6 %) | 485 | 175-360 | 0 | 0 |
| position noise sd 2 ms (±1.2 %) | 485 | 260-300 | 3-6 | 0 |
| position noise sd 4 ms (±2.3 %) | 483-485 | 216-279 | **68-73 (2.7-2.9 %)** | 0 |
| real second pass, click (199.9991 BPM; 16ths at 75.0004 ms) | 485 | 0 (by 0.4 µs) | 0 | 0 |
| real second pass, free (16ths at 74.47-75.02 ms) | 485 | 85 (3.4 %) | 0 | 0 |

- The other power-metal charts on their own maps, today's floors: <troop primary> guitar 679 of 2,613 (26.0 %), <troop alt2> guitar 630 of
  2,678 (23.5 %), <troop primary> bass 212 of 1,852 (11.4 %). With the rule's 75 ms floor: 412, 406 and 165. With 74 or 20 ms: 0.
- Six references, guitar and bass: 0 dropped by any of the four floors. The golden baseline's own engine charts also
  show `dropped` 0 on guitar and bass for all seven songs. On a normal song the floors never fire.
- On the shred charts the floors drop 0 at today's slot levels. Their 62.5 ms gaps are under a 1/16 of any grid we
  build, so they merge or move first: 560 and 492 guitar merges on the humans' own maps. So the advisor's "still
  deletes the shred chart's 62.5 ms strums" holds for raw gaps only, not for what the quantizer does. That is
  immaterial to the verdict.
- The advisor wrote "73.5-76.5 ms from 2 % tempo steps". `MAX_TEMPO_STEP` is a cap on each step, not the spread. On
  the mix grids the spread is under ±0.7 %. The drum-stem grid the pipeline actually uses cannot be measured here
  (there are no stems). The owner's first-pass drum-stem map for this song has 17.6 % of its beats more than 1.35 %
  faster than its median (p95 +4.2 %). If the doubled grid inherits that, a 74 ms floor fails the 2 % line too.
- Sensitivity, in short:
  - the rule's 75 ms floor is a literal coin toss: 0 % or 19 % depending on a tempo error of 0.0005 %;
  - a 74 ms floor survives clean grids but breaks at drum-like jitter;
  - a 20 ms floor drops 0 in every case.

### 3. Does a 20 ms floor give up anything the 80/55 floors were for?

- **DESIGN 2.6 step 3 and `quantize.py`'s docstring give one reason only:** "so `brokenNote` (≤ 15 ms) cannot occur".
  scan-chart's check (`chart-scanner.ts:464-479`) flags 0 < distance ≤ 15 ms between note groups and skips an open
  note next to a non-open one. 20 ms keeps that guarantee with a 5 ms margin.
- **On today's slots the floor cannot fire at all.** Slots are 1/16 or 1/12 per beat (`SnapGrid`), so two distinct
  ticks are at least a 1/16 apart: 50 ms at 300 BPM, 40.5 ms at the second pass's 370 cap. 20 ms is insurance for
  exact-tick sources (Engine A, DESIGN 2.6 step 5, not built) and for M5-99's burst slots.
- **The games.** No other scan-chart issue concerns spacing. Clone Hero has no minimum spacing. The humans strum this
  song at 13.3 a second, play 37.5 ms HOPOs and taps, and strum the shred song at 16 a second.
- **Residual risk.** On a doubled grid, an engine's spurious double onset now survives as an extra strummed 16th
  instead of being dropped. But the engine is under the humans on this song (2,085 onsets against 2,495-2,678), and
  precision against the human charts would show it. A strum-rate cap is a feel question, not a game rule, and the
  advisor's F-c covers it.

### 4. Recommendation

- **Adopt the advisor's change.** Use fixed `STRUM_SPACING_S = HOPO_SPACING_S = 0.020` (`brokenNote` plus a margin),
  keep "an onset under the floor is dropped", and move the gap table above into DESIGN 2.6 as evidence.
- **Say in the order that the floor is dormant on 1/16 + 1/12 slots.** Its test then needs a synthetic map fast enough
  that a 1/16 falls under 20 ms (about 750+ BPM), or a direct `_frets` call.
- Severity: blocks M5-01 step 5 as written. The fix is cheap.

## Skeptic: the advisor's finding 2 on the M5 plan (M5-01's chord rule)

(Recovered from the skeptic's final message after a machine restart; it wrote no file.)

**Partly confirmed.** The finding's conclusion and its fix hold, and the data backs them more strongly than the review did. But the review's reason for leaving `_separate` alone is wrong. Severity: should; it changes what M5-01 builds (step 4 and its test).

**(1) What each rule does.** M5-01 (lines 93-98): when two onsets snap to one tick but lie more than 20 ms apart, the later one moves to the next slot if that slot is free. Otherwise it is dropped. `_separate` (`quantize.py:516-548`, every fret on one lane) acts only on onsets at least 0.75 slot apart. It moves either the earlier ones back or the later ones forward, whichever slot is free and fits closer. If neither is free, they merge into a chord.

**(2) How late a moved note lands.** A note that snapped to a tick sits within about half a slot of it, so any move puts it at least about 0.45 slot off. Under "the later one moves" it can be more than a slot off.

| grid | moved note's error |
|---|---|
| power-metal song at 200 BPM (human charts stand in for the engine) | 37-50 ms |
| shred song at our 154 BPM | 62-63 ms |
| reference songs' engine output (92-148 BPM) | median 97, p90 149, max 178 ms; 99 % at 50 ms or more |

The review says today's `_separate` keeps a moved note "within about a quarter slot". That is wrong: its 27 moves on the references are 47-168 ms off.

How often it happens: the report's 740 merges come from the half-tempo grid. On the right grid the human charts have 107-119 such ticks per guitar chart, and M5-01 would move only 1-14 of them, because the next slot is usually taken. On the references' engine output: 608 such ticks in 12,080 notes, and M5-01 would move 145.

**(3) What dropping loses.** I set the references' 548 engine pairs against the human charts. In 294 the human has one single note, in 144 nothing, in 36 one chord, and in 74 two notes. M5-01 would move 118 notes: 117 are ghost notes or split chords, and 1 is a real second note. Dropping keeps today's onsets and timing exactly; only the chords go. Moving lowers F1@50 and F1@100 on every part it touches, by 0.001 to 0.028 (Creep's bass: −0.028). Only the 200 BPM song gains, by 0.003 at most (14 notes).

**(4) Recommendation.** Adopt the advisor's change. In the band from 20 ms to `rules.separate` slots, keep the onset nearest the tick (not the earlier one) and count the others in `dropped_distinct`. Nearest matters: on the shred song's bass, "the later moves" pushes on-tick notes a full slot. The test becomes "the farther one is dropped". Leave `_separate` as it is in this order, but record its 47-168 ms moves for M5-99. One more thing for the order: `dropped_distinct` comes out at 5.4-6.4 % on the power-metal charts under either rule, so M5-01's "under 2 %" pass line fails whichever rule is used.

I did not write `S/briefs/skeptic-m5-2.md`, because my instructions forbid writing report files. This message is the report. The probes are deleted, and I removed the 8 `.pyc` files my imports left in the worktree, which is clean at eab879a.
## Skeptic: the advisor's #7 (a v0.1 take cut short by the budget is reused unstitched after the update)

Verdict: **confirmed. It is a should, small scope.** I tried to refute it on four grounds: the key changes on
update, the state cannot be read from a cached take, M5-02 already covers it, or no real run reaches it. None holds.
One detail of the advisor's change needs tightening: the T = 0 take (point 4).

### 1. The take's key, and the update

- `take_key` (autochart.py:168-171) holds inputSha256, seed, difficulties, temperature, topP, engineVersion and
  `install`. `install` is a SHA-256 over five files (`install_key`, :146-165): the engine's manifest and catalog, the
  models' manifest, onnxruntime-node's package.json and the driver `ac_headless.cjs`.
  - No songcharter version and no Python code is in it.
  - The probe's take.json fields: `difficulties, engineVersion, inputSha256, install, seed, temperature, topP`.
- The only songcharter file in the key is the driver. `runtime.py:65` copies it from the app's eval/tools/autochart.
  - `git diff v0.1.0 eab879a` on autochart.py, the driver and audio.py is empty.
  - No M5 order touches the driver, the engine pin (`AUTOCHART_COMMIT`) or the key. M5-02:116-117 and M5-05:76
    forbid it.
  - So the update leaves every v0.1 take's key the same.
- The work folder is keyed by the song file only (cache.py `file_key`, `work_folder`) and sits outside `app/<ver>`.
- M5-07:53 requires the reuse. Its CI installs 0.1.0, charts, updates, charts again, and needs "(cached)" for the
  guitar.
- Reachable: yes. The most likely re-chart after the update is the shred song that prompted M5-02. The owner charted
  it today with 4 CUDA takes, so it is in his cache. The friend's long songs are reachable too, unless the 5 GB LRU
  prune has dropped them.

### 2. Detectable from a cached take: yes, from summary.json alone

- The driver writes top-level `maxTokens` and per run `nTokens`, `nBeats` and `audioDuration` (ac_headless.cjs:
  224-228, 277-278). The driver has not changed since v0.1.0, so v0.1 summaries carry them.
- `_summary` already requires summary.json for a hit. No chart parse is needed.
- All 37 real summaries on the dev machine carry these fields. That covers the 7 golden kept takes, 28 GPU takes,
  the gate and the dev UI.

### 3. M5-02 as written does not handle it

- Detection is "after a run" (M5-02:32).
- "take.json's key is unchanged ... so `_done` reuses a stitched take as it reuses any other" (:59-60) assumes M5-02
  made every take. A pre-update take gets no such check.
- The warnings are only for a take with `stitch` (:64-69).
- Its tests check that `_done` hits a stitched take. None covers a cached take that was cut short and not stitched.
- The order's own stress check probably cannot catch it. golden.py needs `--rerun guitar` once autochart.py changes,
  so neither side ever reads the old cache.

Probe (`/dev/shm/skeptic_m5_7/probe.py`, the test file's stand-in install and driver, now deleted):

| case | driver calls | cached |
|---|---|---|
| first run, nTokens 8192 | 1 | no |
| re-chart, today's `_done` | 1 | **yes**, cut short, no `stitch` |
| re-chart with the rule below | 2 | no (runs again) |
| the same, summary with `stitch` | 2 | yes |
| under both caps (3,906 tokens, 434 beats) | 1 | yes |

### 4. The smallest change, and what it breaks

- **`_done`:** a summary cut short by step 1's rule (`runs[0].nTokens >= maxTokens` or `nBeats >= 1280`) and
  without `stitch` is not a hit. `generate` then runs the take whole and continues it.
  - The cost is one extra whole run per such take, once.
- **Tightening:** M5-02:37 leaves a T = 0 take "as it is". Unless step 3 writes `stitch` for every cut-short take it
  handles (`pieces: []` for T = 0), that take misses and runs again on every chart.
- **Tests:**
  - a cached cut-short take without `stitch` runs again and is continued;
  - with `stitch`, no run;
  - the T = 0 take is a hit on the second run.
- **Breaks nothing:**
  - Determinism holds: the decision is a pure function of the summary.
  - Golden: all 7 kept takes are under both caps (max nTokens 3,906 Lucretia, max nBeats 933 test_song). They still
    hit and stay byte-identical. None of the 28 GPU takes is cut short.
  - M5-07's CI clip is far under the budget and is still "(cached)".
  - The key is unchanged (M5-02:117).
- **Reject the advisor's alternative** (a stitch version in the key). It reruns every take after the update. It would
  fail M5-07:53 and break M5-02's "no change to the take's key".
