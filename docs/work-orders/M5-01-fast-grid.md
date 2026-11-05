# M5-01: very fast songs: the grid's tempo octave is the musical pulse, no chord made of notes distinct in time, and the spacing floors at 20 ms

**Branch:** `m5-01-fast-grid`, from `main` after M5-09's merge (wave 2, beside M5-02). It starts as soon as M5-09's
baseline run exists and a builder slot is free: step 2 needs the stress songs' engine charts, which only that run
makes (M5-09's review may still be going; then `stress.py` is read from M5-09's branch, and the branch is rebased at
M5-09's merge). **Agent:** `sc-builder`, then `sc-reviewer`. May push its branch to run CI (`gh workflow run ci --ref
m5-01-fast-grid`). **Files:** `songcharter/beatgrid.py`, `songcharter/quantize.py`, `songcharter/assemble.py`, their
tests, `docs/DESIGN.md` 2.3 and 2.6. Nothing in `pipeline.py`, `ui/` or `eval/` (M5-09 owns `eval/`). **Time
budget:** 2 days, the golden and stress runs included.

*Amended 2026-11-05 after the advisor's review of the plan and its skeptics: the floors are fixed at 20 ms (step 5),
the chord rule drops the farther onset instead of moving it (step 4), the second grid's guard is set from a table
(step 3), the pass lines rest on M5-09's 1-take baseline, and the order says plainly that it builds doubling only.*

**Conventions.** This order follows the charting-conventions report (`docs/reports/charting-conventions.md`, committed
at wave 0; sections 1, 2c and 2g, its ranked gaps 1-3). The rules it assumes are marked **[conventions]** so the
advisor can check them against the report:
- the tempo map is the song's musical pulse, the beat a musician counts, anywhere in 40-300 BPM; nothing in charting
  practice folds a tempo into a range, and every rule songcharter counts in beats or ticks (the HOPO threshold, the
  slots, the sustain floors, star power, fills, sections, solos, the lyric snap) only comes out right at that pulse.
  **This version builds the doubling pass only:** the first pass still folds into 85-185 BPM, a grid that is too
  slow is doubled, and a pulse under 85 BPM (the shred instrumental, whose grid is at twice the humans' tempo) stays
  at double, with its effects on the HOPO states, the star-power count and the solo measures. Halving needs data this
  order records (the backbeat ratio of every song) and goes to M5-99; DESIGN 2.3 says "doubling only";
- a chord is notes that sound together; a run of single notes is never written as a chord; dropping a note is better
  than making a chord of two notes distinct in time;
- the only spacing the games or the lints require is scan-chart's `brokenNote` at 15 ms; human charts reach 17 notes
  a second (about 59 ms), so a floor of 80 ms before a strum deletes real notes, and on a grid at or under 300 BPM
  any floor above about 50 ms (two 1/16 slots apart) can only delete real notes.

## Why

On 2026-11-05 the owner charted a 5-minute power-metal song at 198 BPM (4 CUDA takes; `<S>/troop/`, PROGRESS
`deferred`). `beatgrid.estimate_tempo` folds every tempo into `BPM_RANGE` [85, 185), so the grid came out at 100 BPM:
a 1/16 slot of that grid is 151 ms, and the song's 16ths (76 ms apart) fall two to a slot. `quantize._separate`
keeps two onsets apart only when they lie at least 0.75 slot apart, so the quantizer merged 740 of the guitar's 2,085
onsets into chords (bass 336 of 1,689, drums 595 of 4,094: `report.json`, `parts.*.quantize.merged`). Against three
human charts the guitar has 38 % chords where they have 3-5 %, recall 0.45-0.48 at precision 0.90-0.92, matched
notes 62-68 ms off; drums F1@50 0.857, bass 0.678. The guitar engine itself is near the humans (2,085 notes against
2,495-2,678). The grid's beats were also about 150 ms off the humans' even when doubled (octave-tolerant beat F1
0.40): half a beat at 198 BPM, so the doubled grid's lines fall on the humans' 8th lines and the bar phase is wrong
too. DESIGN 8.1 (G1) planned exactly this for M5: "choose the metrical level together with note density". The
conventions report (section 11, item 1) calls the fold a design error: charters chart the musical tempo and then
force the HOPO states; songcharter did the opposite.

Two more defects the report found in the same path, which the octave fix alone leaves standing: the quantizer drops
any onset closer than 80 ms to the previous strum or 55 ms to the previous HOPO or tap (`STRUM_SPACING_S`,
`HOPO_SPACING_S`), so strummed 16ths above 187.5 BPM are deleted even on the right grid (the power-metal song's
16ths are 76 ms apart; `QuantizeReport.dropped` counts them: a perfect engine, the human chart itself through
`quantize_part` on its own map, loses 19-26 % of its guitar notes to today's floors on that song and 0 on every
reference); and two onsets that snap to one tick merge into a chord whenever the next slot is not free.

## What to build

1. **`beat_grid` takes its fold range as a parameter.** `beat_grid(..., bpm_range=BPM_RANGE)`, threaded through
   `estimate_tempo`, `window_tempi`, `local_periods` and `missed_tempo_changes` (each reads the module constant
   today). With a `bpm` hint the start line already trusts the hint to 0.5 %; the windows' octave choice and the
   tracker's local periods must fold into the range given, so that a hinted 198 BPM is not pulled back to 99 by
   `window_tempi` (its `octaves` list keeps only tempi inside the range). The default range and every default path
   stay as they are: with the defaults, every reference song's grid is bit-identical (the golden check below).
2. **The octave test, in `assemble.py`, after the grid is built and before quantizing** [conventions: the octave
   whose beat is the musical pulse, judged by two tests, the subdivisions the notes sit on and the backbeat]. A pure
   function `grid_octave(onsets_by_part, beats, features, rules) -> (octave, stats)`:
   - `onsets_by_part`: each charted part's distinct Expert onset times (seconds of the input), as the parts' TimedSongs
     give them before quantizing; drums included, as their distinct hit times (hits on one tick are several pads);
     `beats`: the grid's beat times (input seconds, before the lead-in); `features`: the drum stem's `OnsetFeatures`
     the grid was built from (its `snare` band power per frame), None without drums. `beat_grid` does not return its
     features and assemble calls it with audio (`assemble.py:1292`): compute the features once in assemble and pass
     `features=` to both grid passes and to this test.
   - **The density test:** for each part, the intervals between consecutive distinct onsets; the share of them that
     are shorter than `OCTAVE_SHORT` = 0.75 of a 1/16 slot of the local beat (the beat the onset falls in:
     `0.75 * ibi / 4`), i.e. the intervals the quantizer would merge, move or drop. Pool the parts weighted by their
     onset counts, and keep each part's share in the stats. A grid at the pulse holds its notes on 8ths and 16ths
     (human guitar and bass sit about 95 % on 8ths, DESIGN 2.6); a share of intervals that need 1/32s says the grid
     is an octave too slow.
   - **The backbeat test:** the snare band's peak power within +-35 ms of each beat line against that within +-35 ms
     of each beat's midpoint (its 8th line), as medians over the beats with confident drum evidence; `backbeat_ratio`
     = midpoints / beat lines. A snare that lands between the grid's beats (ratio clearly over 1) says the grid is too
     slow; a snare on the beat lines says it is the pulse or faster. The ratio is recorded for every song (M5-99's
     halving rule needs it); without drums it is None and the test is indeterminate.
   - `octave = 2` when the pooled density share is at least `OCTAVE_SHARE` (set below), the backbeat test does not
     contradict it (`backbeat_ratio` is None or at least `BACKBEAT_MIN` = 0.8: the snare is not clearly on the beat
     lines), the grid's median tempo doubled is at most `OCTAVE_MAX_BPM` = 300 [conventions: Magma's 40-300], and the
     song has at least `OCTAVE_MIN_ONSETS` = 200 distinct onsets in all; otherwise 1. Halving is not built (the shred
     instrumental's grid is at double the humans' tempo: record its statistics and leave the rule to M5-99 with
     them); say so in DESIGN.
   - Set `OCTAVE_SHARE` by measurement: both statistics on every reference song (the seven, from the golden kept
     folders' engine charts), on the two stress songs (the engine charts in M5-09's `stress-base` kept folders: this
     is why the order waits for that run; the scratch folders' `ours/notes.chart` are after the merge, with no gap
     under 142 ms, and their `report.json` sources are paths on the owner's PC) and on the test song. Put the
     threshold at the geometric midpoint between the largest density share of a song whose grid is right and the
     smallest of a song whose grid is at half tempo (the power-metal song, the one member of that group: the report
     says the threshold rests on one positive example). Report the table, the backbeat ratios beside it. If the
     margin between the two groups is under a factor of 2, stop and report before building the rest.
3. **The second pass.** When `octave == 2`, build the grid again with `beat_grid(..., bpm=2 * grid_bpm,
   bpm_range=(2 * lo, 2 * hi))`, where `grid_bpm` is the first grid's click tempo (`stats["click"]["bpm"]`), no
   first-beat hint (the comb and the tracker find the phase at the new tempo, which fixes the half-beat offset), the
   same mode override and secondary stem as the first pass. **The guard** that keeps or rejects the second grid is
   set from a table, not guessed: run the second pass on every song of step 2's table and record both grids'
   confident shares (`stats["evidence"]["confident_share"]`) and their drum evidence. A doubled grid has less drum
   evidence per beat by nature: on the power-metal song's mix the advisor measured 0.208 → 0.113 while the beats went
   to F1@70 0.99 against the human map (median error 8 ms), and the drum-stem figure after doubling is unknown. Set
   `OCTAVE_EVIDENCE_MIN` from that table (a ratio of the two shares may fit better than a difference; say which and
   why), report the table, and stop and report if the guard it gives vetoes the power-metal song. When the guard
   rejects the second grid, keep the first and warn `tempo: the notes are dense for N BPM (x % of intervals under a
   16th) but the drums give no evidence at 2N: check the tempo`. Either way `report.json`'s `grid` gets `octave`,
   `octave_stats` (the shares per part, the pooled share, the backbeat ratio, the thresholds, both grids' confident
   shares) and `octave_reason`, and the build warns once when it doubled: `tempo doubled to N BPM: the notes are too
   dense for M BPM (x % of intervals under a 16th)`.
   - The assemble config gets `grid_octave`: `"auto"` (default), `1` or `2` (forced; `2` fails with an InputError when
     the doubled tempo passes 300). `parse_config` validates it like `grid_mode`. No CLI or page option in this
     version (M5-99: the tempo control).
   - Lead-in, tempo map, downbeats, sections, star power and the HOPO threshold all follow the chosen grid as they
     do now [conventions: they are counted in beats of the pulse]: nothing else changes. Star-power phrases roughly
     double on a doubled grid (`round(span / 40 beats)`, `starpower.py`: about 25 one-measure phrases in 5 minutes):
     the evaluation measures phrases per minute against the human charts', the reviewer looks at them before the
     gate, and a change to the phrase rule is not this order's.
4. **No chord made of notes distinct in time** [conventions: a chord is notes that sound together; drop before you
   merge]. In `quantize._frets`, source onsets that snapped to one tick but lie more than `MERGE_MAX_S` = 0.020 s
   apart in the source (a strummed chord's notes come at one time from every source songcharter reads; a flam is
   under 20 ms) are not merged into a chord: the onset nearest the tick is kept and the others are dropped, counted
   in a new `QuantizeReport.dropped_distinct`; a chord is never made of them. Nearest, not earliest: on the shred
   song's bass a "the later one moves" rule pushed on-tick notes a full slot. Nothing moves in this band: `_separate`
   keeps its rule (onsets at least `rules.separate` = 0.75 slot apart move to a free neighbouring slot) and is not
   changed in this order; its own moves, 47-168 ms on the references, are recorded for M5-99. The plan's first
   draft moved the later onset to the next slot when that slot was free; the skeptic's evidence against it, on the
   references' engine charts: of the 118 notes the moving rule would move, 117 are ghost notes or split chords and 1
   a real second note, and moving lowered F1@50 by 0.001-0.028 on every part it touched. Drums are not changed (hits
   on one tick are several pads, not a chord). Report `dropped_distinct` per part on the stress set beside the human
   charts' own figure: each human chart through `quantize_part` on its own map as a perfect engine gives 5.4-6.4 %
   on the power-metal song (its 37.5 ms 32nds and 50 ms sextuplets, which no 1/16 grid holds), so a figure near the
   humans' is the plan working as intended, and one well above it says the engine makes double onsets. Either way
   the 1/32 and 1/24 burst slots are M5-99's next step, with these numbers; not this order's.
5. **The spacing floors at 20 ms** [conventions: nothing requires more than `brokenNote`'s 15 ms]. `STRUM_SPACING_S`
   = `HOPO_SPACING_S` = 0.020 s, fixed (`brokenNote` plus a margin), the rule's shape kept (an onset under the floor
   is dropped, `QuantizeReport.dropped`). Not the human charts' 1st percentile, as the plan first said: the skeptic
   measured that rule at 75 ms, exactly the power-metal song's strummed 16ths at 200 BPM (3,092 gaps at that mass
   point, 37 % of the pooled strum gaps of the eleven human charts), so whether hundreds of that song's notes survive
   depends on tempo differences of 0.0005 %; 74 ms survives clean grids but breaks at drum-like jitter; 20 ms drops
   nothing anywhere and keeps the only guarantee the floors were ever for (DESIGN 2.6 step 3: `brokenNote` cannot
   fire). The key rows, notes dropped from the power-metal song's primary guitar chart (2,495 notes) through
   `quantize_part` as a perfect engine, in the order the evidence came:

   | grid | 80/55 ms (today) | 75/37 ms (the percentile rule) | 74/37 ms | 20/20 ms |
   |---|---|---|---|---|
   | the human map (200.000 BPM) | 485 (19.4 %) | 339 (13.6 %): float rounding at exactly 75.0 | 0 | 0 |
   | the human map at tempo x1.0001 / x0.9999 | 485 / 485 | 485 / 0 | 0 / 0 | 0 / 0 |
   | the human map with beat-position noise, sd 4 ms (periods ±2.3 %) | 483-485 | 216-279 | 68-73 (2.7-2.9 %) | 0 |
   | the real second pass on the mix, click mode (199.9991 BPM) | 485 | 0 (by 0.4 µs) | 0 | 0 |
   | the real second pass, free mode (16ths at 74.47-75.02 ms) | 485 | 85 (3.4 %) | 0 | 0 |
   | the six references, guitar and bass | 0 | 0 | 0 | 0 |

   The floor is dormant on today's slots (two distinct 1/16 ticks are at least 50 ms apart at 300 BPM, 40.5 ms at the
   second pass's 370 BPM cap): it is insurance for exact-tick sources and for M5-99's burst slots, and its test
   needs a direct `_frets` call or a synthetic map fast enough that a 1/16 falls under 20 ms (about 750 BPM). The gap
   table (the skeptic's: gaps by the second note's played state over the eleven human charts, pooled 1st percentile
   75.0 ms for strums and 37.5 ms for HOPOs and taps, the references' minimum 74.7 and 37.0 ms) goes into DESIGN 2.6
   as evidence, not as a setting; nothing in this step reads the human charts again.
6. **HOPO states, measured only** [conventions: the played state is the articulation, which should not depend on
   our octave; the report's gap 4]. On the two stress songs after the octave fix, build each once with the default
   `hopo: "forced"` and once with `"source"` (`assemble.HOPO_RULES`, the existing config key) and report, against
   every human chart, the HOPO share (shares alone mislead: the power-metal song's three human charts have HOPO shares
   of 0.21, 0.51 and 0.29; ours 0.25 and 0.40 today), the per-note strum, HOPO and tap agreement on the matched notes
   (M5-09's `state_agreement`) and the F1s. No default changes in this order; the numbers go to M5-99's entry, and
   the owner can decide the mode at the gate if they are clear (M5-00 section 8).

## Tests

- `beatgrid`: `bpm_range` reaches every fold (a synthetic click at 198 BPM with `bpm=198, bpm_range=(170, 370)` gives
  a 198 BPM grid; the same audio with the defaults gives 99); the defaults unchanged (an existing fixture's grid is
  identical).
- `assemble.grid_octave`: synthetic parts at 16ths on a 198 BPM clock against a 99 BPM grid give octave 2 with the
  stats; the same at 8ths give 1; under `OCTAVE_MIN_ONSETS` give 1; a doubled tempo over 300 gives 1 with the reason;
  a synthetic snare on the grid's beat lines (ratio under `BACKBEAT_MIN`) keeps 1 although the density says 2, and
  one on the midpoints lets it double; no drum features: indeterminate.
- `assemble` end to end on a generated song (tests/test_assemble.py's style): the second pass runs, the report's
  `octave` is 2, the warning is there, the tempo map's median tempo is about doubled; `grid_octave: 1` forces the
  first grid; the evidence guard keeps the first grid and warns; the features computed once reach both passes.
- `quantize`: two onsets 50 ms apart on one tick (under `rules.separate` slots): the one farther from the tick is
  dropped, counted in `dropped_distinct`, no chord is made, and it is the earlier one when the earlier one is farther;
  15 ms apart stay a chord; onsets 0.75 slot apart still move through `_separate` (the existing test); the floors,
  through a direct `_frets` call or a synthetic map over about 750 BPM: an onset one millisecond under
  `STRUM_SPACING_S` is dropped and one at it is kept (the same for the HOPO floor).
- Each test fails when its code is broken (say which break).

## Evaluation

- **Golden** (the charting path changed; `beatgrid.py` is in `ENGINE_FILES["drums"]`): `--rerun drums` on both runs.
  Every reference song's grid must be bit-identical with the defaults (`octave` 1 everywhere: the seven are inside
  85-185 BPM). The floors change nothing on the references (today's floors drop 0 on every golden engine chart's
  guitar and bass); the chord rule will: the skeptic counted 118 same-tick pairs more than 20 ms apart on the
  references' engine charts (117 ghost notes or split chords, 1 a real second note), now dropped instead of merged.
  `--expect` names those parts, and the report lists each changed song with its onsets and F1@50 and F1@100 old →
  new (from `report.md`) and why it moved. Any song whose F1@50 falls by more than 0.005 on any part fails the
  order; the chord shares must move toward the humans' or stay.
- **The stress set** (M5-09's check, `eval/README.md`'s "Stress songs"; M5-09's branch until it merges): the
  power-metal song's chart before and after, scored against its three human charts. "The baseline" below is M5-09's
  1-take CPU run of `main` on the dev machine (`stress-base`); the owner's 4-take CUDA figures of 2026-11-05 are
  reported beside it, never used as a pass line (they measure the take count as much as the fix). Pass:
  - the grid at about 198 BPM (report.json `grid.bpm_median` 190-206), `octave` 2;
  - guitar chord share under 0.10 and moving toward the humans' (0.03-0.05); quantize `merged` under 5 % of
    `notes_in`; `dropped` under 0.5 % of `notes_in` (the floors are dormant: what is left is before tick 0);
    `dropped_distinct` at most the human charts' own figure plus two points (8.5 % with the measured 5.4-6.4 %: the
    builder re-measures the humans' figure under the final rule and states the line it used); the humans' 32nds and
    sextuplets land there by design, so the line is "no worse than a perfect engine, with a margin", not "none";
  - guitar F1@50 at least the baseline's plus 0.10 against each human chart, with the owner's 0.58-0.59, the plan's
    first line of 0.70 and the humans' 0.917-0.922 with each other (the ceiling) reported beside it; bass and drums
    F1@50 not below the baseline's (the owner's run: 0.678, 0.857); matched guitar notes' median timing error under
    15 ms (62-68 ms on the owner's run; the humans agree at about 9 ms, and bass and drums sit at 1-5 ms);
  - plain beat F1@70 ms at least 0.80 [conventions: the octave is scored without octave tolerance] and
    octave-tolerant at least 0.90 (0.40 today); downbeat F1 reported (M5-09's);
  - the per-note state agreement (step 6) reported under `forced` and `source`, not lower than the baseline's under
    the shipped mode;
  - the shred instrumental: no part's F1@50 or F1@100 lower than the baseline's (the owner's run: guitar 0.636 /
    0.743 and 0.725 / 0.748 against its two charts, bass 0.653 / 0.691); its `dropped` and `dropped_distinct` counts
    reported before and after;
  - star-power phrases per minute and the sustain share of both songs reported beside the humans' (they follow the
    octave; the phrases about double on a doubled grid: the reviewer looks at them before the gate).

## Done means

- [dev] `uv run pytest -q` (the suite) passes; the new tests fail when their code is broken.
- [dev] The golden diff as above, exit 0, `report.md` in the report.
- [dev] The stress check's table, before and after, with the pass lines above.
- [CI] Green on the branch.
- [docs] DESIGN 2.3 (the octave pass, doubling only, both tests' tables, the guard's table, the range parameter;
  its step 3's reason for the fold rewritten as the conventions report's section 11 item 1 says), 2.6 (the chord
  rule, drop the farther; the floors at 20 ms with the gap table and the sensitivity table as evidence; its step 3's
  `brokenNote` justification corrected), 8.1's G1 row updated; `docs/work-orders/M5-99-later.md` gets the shred
  instrumental's statistics (the halving rule), `_separate`'s moves, the `dropped_distinct` figures (the burst
  slots) and the HOPO-state numbers.

## Limits

- No change to `BPM_RANGE`'s default for the first pass, to the quantizer's slot levels (1/16 and triplets stay:
  DESIGN 2.6; burst slots are M5-99's), to `_separate` or to the HOPO rules' default. No new dependency.
- Nothing is read from the human charts but what `score.py` and `stress.py` print; no lyrics anywhere. The stress
  songs' human-chart packages have vocal tracks: the full packages (`<S>/troop/human_*`) and the scratch `ref_*`
  folder whose chart still holds 409 lyric events (it was never stripped as `build_refs.sh` strips `ref/`) are read
  only by timing scripts that print numbers, never opened with Read, cat or grep; once M5-09 has merged, only
  `$EVAL_DATA/stress/` refs are read.

## Report

`<scratchpad>/briefs/m5-01.report.md`: the commits; the octave tables (every song's density share and backbeat ratio,
the two groups, the midpoint; both grids' confident shares and the guard); the golden `report.md`; the stress table
before and after (every pass line with its number, the baseline and the owner's figures both); what the chord rule
did on the references; the `dropped_distinct` figures beside the humans'; the HOPO-state and state-agreement
numbers; the star-power phrases per minute; anything uncertain.
