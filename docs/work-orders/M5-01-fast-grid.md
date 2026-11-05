# M5-01: very fast songs: the grid's tempo octave is the musical pulse, no chord made of notes distinct in time, and spacing floors from the human charts

**Branch:** `m5-01-fast-grid`, from `main` after M4-11's merge (wave 1, beside M5-09). **Agent:** `sc-builder`, then
`sc-reviewer`. May push its branch to run CI (`gh workflow run ci --ref m5-01-fast-grid`). **Files:**
`songcharter/beatgrid.py`, `songcharter/quantize.py`, `songcharter/assemble.py`, their tests, `docs/DESIGN.md` 2.3
and 2.6. Nothing in `pipeline.py`, `ui/` or `eval/` (M5-09 owns `eval/`). **Time budget:** 2 days, the golden and
stress runs included.

**Conventions.** This order follows the charting-conventions report (`docs/reports/charting-conventions.md`, committed
at wave 0; sections 1, 2c and 2g, its ranked gaps 1-3). The rules it assumes are marked **[conventions]** so the
advisor can check them against the report:
- the tempo map is the song's musical pulse, the beat a musician counts, anywhere in 40-300 BPM; nothing in charting
  practice folds a tempo into a range, and every rule songcharter counts in beats or ticks (the HOPO threshold, the
  slots, the sustain floors, star power, fills, sections, solos, the lyric snap) only comes out right at that pulse;
- a chord is notes that sound together; a run of single notes is never written as a chord; dropping a note is better
  than making a chord of two notes distinct in time;
- the only spacing the games or the lints require is scan-chart's `brokenNote` at 15 ms; human charts reach 17 notes
  a second (about 59 ms), so a floor of 80 ms before a strum deletes real notes.

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
16ths are 76 ms apart; `QuantizeReport.dropped` counts them); and two onsets that snap to one tick merge into a
chord whenever the next slot is not free.

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
     give them before quantizing; `beats`: the grid's beat times (input seconds, before the lead-in); `features`: the
     drum stem's `OnsetFeatures` the grid was built from (its `snare` band power per frame), None without drums.
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
     folders' engine charts), on the two stress songs (M5-09's set, or the scratch folders `<S>/troop/ours` and
     `<S>/sooth/ours` until it exists: read their `report.json` parts' sources, or chart them) and on the test song.
     Put the threshold at the geometric midpoint between the largest density share of a song whose grid is right and
     the smallest of a song whose grid is at half tempo (the power-metal song). Report the table, the backbeat ratios
     beside it. If the margin between the two groups is under a factor of 2, stop and report before building the
     rest.
3. **The second pass.** When `octave == 2`, build the grid again with `beat_grid(..., bpm=2 * grid_bpm,
   bpm_range=(2 * lo, 2 * hi))`, where `grid_bpm` is the first grid's click tempo (`stats["click"]["bpm"]`), no
   first-beat hint (the comb and the tracker find the phase at the new tempo, which fixes the half-beat offset), the
   same mode override and secondary stem as the first pass. Keep the second grid only when its confident share is at
   least the first grid's minus 0.10 (`stats["evidence"]["confident_share"]`); otherwise keep the first and warn
   `tempo: the notes are dense for N BPM (x % of intervals under a 16th) but the drums give no evidence at 2N:
   check the tempo`. Either way `report.json`'s `grid` gets `octave`, `octave_stats` (the shares per part, the pooled
   share, the backbeat ratio, the thresholds, both grids' confident shares) and `octave_reason`, and the build warns
   once when it doubled: `tempo doubled to N BPM: the notes are too dense for M BPM (x % of intervals under a 16th)`.
   - The assemble config gets `grid_octave`: `"auto"` (default), `1` or `2` (forced; `2` fails with an InputError when
     the doubled tempo passes 300). `parse_config` validates it like `grid_mode`. No CLI or page option in this
     version (M5-99: the tempo control).
   - Lead-in, tempo map, downbeats, sections, star power and the HOPO threshold all follow the chosen grid as they
     do now [conventions: they are counted in beats of the pulse]: nothing else changes.
4. **No chord made of notes distinct in time** [conventions: a chord is notes that sound together; drop before you
   merge]. In `quantize._frets`, two source onsets that snapped to one tick but lie more than `MERGE_MAX_S` = 0.020 s
   apart in the source (a strummed chord's notes come at one time from every source songcharter reads; a flam is
   under 20 ms) are not merged into a chord: the later one moves to the next slot when that slot is free on the part,
   as `_separate` does, and counts in a new `QuantizeReport.separated_close`; when the next slot is taken it is
   dropped and counted in `dropped_distinct`, never merged. Drums are not changed (hits on one tick are several
   pads, not a chord). Report `dropped_distinct` per part on the stress set: if it passes 1 % of a part's notes after
   the octave fix, 1/32 and 1/24 burst slots are the next step (M5-99), not this order's.
5. **The spacing floors from the human charts** [conventions: nothing requires more than `brokenNote`'s 15 ms].
   Measure, on the seven reference charts and the five stress charts (numbers only, through
   `eval/scorer/scan_notes.cjs` or `importers.read_chart`; never open a chart's [Events] or vocal track), the gaps
   between consecutive Expert guitar and bass onsets by the played state of the second note (strum, HOPO, tap, from
   `quantize.play_states`): the 1st percentile and the minimum per state, pooled. Set `STRUM_SPACING_S` and
   `HOPO_SPACING_S` to the pooled 1st percentile of each state rounded down to a millisecond, never under 0.020 s
   (`brokenNote` plus a margin), and report the table. Keep the rule's shape (an onset under the floor is dropped,
   `QuantizeReport.dropped`).
6. **HOPO states, measured only** [conventions: the played state is the articulation, which should not depend on
   our octave; the report's gap 4]. On the two stress songs after the octave fix, build each once with the default
   `hopo: "forced"` and once with `"source"` (`assemble.HOPO_RULES`, the existing config key) and report the HOPO
   share against the human charts' (power-metal 0.51, shred 0.55; ours 0.25 and 0.40 today) and the F1s. No default
   changes in this order; the numbers go to M5-99's entry for M6's decision.

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
  first grid; the confident-share guard keeps the first grid and warns.
- `quantize`: two onsets 50 ms apart on one tick become two notes on consecutive slots; 15 ms apart stay a chord; a
  taken next slot drops the later one, counted in `dropped_distinct`, and no chord is made; the new floors: a strum
  one millisecond under `STRUM_SPACING_S` is dropped and one at it is kept (the same for the HOPO floor).
- Each test fails when its code is broken (say which break).

## Evaluation

- **Golden** (the charting path changed; `beatgrid.py` is in `ENGINE_FILES["drums"]`): `--rerun drums` on both runs.
  Every reference song's grid must be bit-identical with the defaults (`octave` 1 everywhere: the seven are inside
  85-185 BPM). The chord rule and the lower floors will move notes on some references (notes dropped today kept,
  a few merges undone): `--expect` names those parts, and the report lists each changed song with its onsets and
  F1@50 and F1@100 old → new (from `report.md`) and why it moved. Any song whose F1@50 falls by more than 0.005 on
  any part fails the order; the chord shares must move toward the humans' or stay.
- **The stress set** (M5-09's check, `eval/README.md`'s "Stress songs" once merged; until then the same commands on
  the scratch folders): the power-metal song's chart before and after, scored against its three human charts. Pass:
  - the grid at about 198 BPM (report.json `grid.bpm_median` 190-206), `octave` 2;
  - guitar chord share under 0.10 (humans 0.03-0.05), quantize `merged` under 5 % of `notes_in`, `dropped` plus
    `dropped_distinct` under 2 % (the floors no longer delete its 16ths);
  - guitar F1@50 at least 0.70 against each human chart (0.58-0.59 today), bass and drums F1@50 not below today's
    (0.678, 0.857), matched notes' median timing error under 25 ms (62-68 today);
  - plain beat F1@70 ms at least 0.80 [conventions: the octave is scored without octave tolerance] and
    octave-tolerant at least 0.90 (0.40 today);
  - the shred instrumental: no part's F1@50 or F1@100 lower than today's (guitar 0.636 / 0.743 and 0.725 / 0.748
    against its two charts, bass 0.653 / 0.691); its `dropped` count reported before and after (the floors);
  - the star-power count and the sustain share of both songs reported beside the humans' (they follow the octave).
  These are 1-take CPU charts on the dev machine against the owner's 4-take numbers: compare with M5-09's baseline
  run of `main` (the same machine, 1 take), not with the owner's figures, and report both.

## Done means

- [dev] `uv run pytest -q` (the suite) passes; the new tests fail when their code is broken.
- [dev] The golden diff as above, exit 0, `report.md` in the report.
- [dev] The stress check's table, before and after, with the pass lines above.
- [CI] Green on the branch.
- [docs] DESIGN 2.3 (the octave pass, both tests' tables, the range parameter; its step 3's reason for the fold
  rewritten as the conventions report's section 11 item 1 says), 2.6 (the chord rule and the floors with their
  tables; its step 3's `brokenNote` justification corrected), 8.1's G1 row updated; `docs/work-orders/M5-99-later.md`
  gets the shred instrumental's statistics (the halving rule) and the HOPO-state numbers.

## Limits

- No change to `BPM_RANGE`'s default for the first pass, to the quantizer's slot levels (1/16 and triplets stay:
  DESIGN 2.6; burst slots are M5-99's) or to the HOPO rules' default. No new dependency.
- Nothing is read from the human charts but what `score.py` prints; no lyrics anywhere (the stress songs' charts have
  vocal tracks: never open their [Events]).

## Report

`<scratchpad>/briefs/m5-01.report.md`: the commits; the octave tables (every song's density share and backbeat ratio,
the two groups, the midpoint); the floors' table (the gaps by state); the golden `report.md`; the stress table
before and after (every pass line with its number); what the chord rule and the floors each did on the references;
the HOPO-state numbers; anything uncertain.
