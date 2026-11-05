# M5-01: very fast songs: the grid's tempo octave from note density, and no chord made of notes distinct in time

**Branch:** `m5-01-fast-grid`, from `main` after M4-11's merge (wave 1, beside M5-09). **Agent:** `sc-builder`, then
`sc-reviewer`. May push its branch to run CI (`gh workflow run ci --ref m5-01-fast-grid`). **Files:**
`songcharter/beatgrid.py`, `songcharter/quantize.py`, `songcharter/assemble.py`, their tests, `docs/DESIGN.md` 2.3
and 2.6. Nothing in `pipeline.py`, `ui/` or `eval/` (M5-09 owns `eval/`). **Time budget:** 1.5 days, the golden and
stress runs included.

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
too. DESIGN 8.1 (G1) planned exactly this for M5: "choose the metrical level together with note density".

## What to build

1. **`beat_grid` takes its fold range as a parameter.** `beat_grid(..., bpm_range=BPM_RANGE)`, threaded through
   `estimate_tempo`, `window_tempi`, `local_periods` and `missed_tempo_changes` (each reads the module constant
   today). With a `bpm` hint the start line already trusts the hint to 0.5 %; the windows' octave choice and the
   tracker's local periods must fold into the range given, so that a hinted 198 BPM is not pulled back to 99 by
   `window_tempi` (its `octaves` list keeps only tempi inside the range). The default range and every default path
   stay as they are: with the defaults, every reference song's grid is bit-identical (the golden check below).
2. **The octave test, in `assemble.py`, after the grid is built and before quantizing.** A pure function
   `grid_octave(onsets_by_part, beats, rules) -> (octave, stats)`:
   - `onsets_by_part`: each charted part's distinct Expert onset times (seconds of the input), as the parts' TimedSongs
     give them before quantizing; `beats`: the grid's beat times (input seconds, before the lead-in).
   - For each part, the intervals between consecutive distinct onsets; the share of them that are shorter than
     `OCTAVE_SHORT` = 0.75 of a 1/16 slot of the local beat (the beat the onset falls in: `0.75 * ibi / 4`), i.e. the
     intervals the quantizer would merge or move. Pool the parts weighted by their onset counts, and keep each part's
     share in the stats.
   - `octave = 2` when the pooled share is at least `OCTAVE_SHARE` (set below), the grid's median tempo doubled is at
     most `OCTAVE_MAX_BPM` = 300, and the song has at least `OCTAVE_MIN_ONSETS` = 200 distinct onsets in all;
     otherwise 1. Halving is not built (nothing measured asks for it); say so in DESIGN.
   - Set `OCTAVE_SHARE` by measurement: the statistic on every reference song (the seven, from the golden kept folders'
     engine charts), on the two stress songs (M5-09's set, or the scratch folders `<S>/troop/ours` and `<S>/sooth/ours`
     until it exists: read their `report.json` parts' sources, or chart them) and on the test song. Put the threshold
     at the geometric midpoint between the largest value of a song whose grid is right and the smallest of a song whose
     grid is at half tempo (the power-metal song; the shred instrumental's grid is at double the humans' per PROGRESS,
     which this order does not fix: record its value and note it in M5-99). Report the table. If the margin between
     the two groups is under a factor of 2, stop and report before building the rest.
3. **The second pass.** When `octave == 2`, build the grid again with `beat_grid(..., bpm=2 * grid_bpm,
   bpm_range=(2 * lo, 2 * hi))`, where `grid_bpm` is the first grid's click tempo (`stats["click"]["bpm"]`), no
   first-beat hint (the comb and the tracker find the phase at the new tempo, which fixes the half-beat offset), the
   same mode override and secondary stem as the first pass. Keep the second grid only when its confident share is at
   least the first grid's minus 0.10 (`stats["evidence"]["confident_share"]`); otherwise keep the first and warn
   `tempo: the notes are dense for N BPM (x % of intervals under a 16th) but the drums give no evidence at 2N:
   check the tempo`. Either way `report.json`'s `grid` gets `octave`, `octave_stats` (the shares per part, the pooled
   share, the threshold, both grids' confident shares) and `octave_reason`, and the build warns once when it doubled:
   `tempo doubled to N BPM: the notes are too dense for M BPM (x % of intervals under a 16th)`.
   - The assemble config gets `grid_octave`: `"auto"` (default), `1` or `2` (forced; `2` fails with an InputError when
     the doubled tempo passes 300). `parse_config` validates it like `grid_mode`. No CLI or page option in this
     version (M5-99: the tempo control).
   - Lead-in, tempo map, downbeats, sections and star power all follow the chosen grid as they do now: nothing else
     changes.
4. **No chord made of notes distinct in time (the backstop).** In `quantize._frets`, two source onsets that snapped
   to one tick but lie more than `MERGE_MAX_S` = 0.040 s apart in the source (longer than a flam, shorter than the
   HOPO spacing) are not merged into a chord: the later one moves to the next slot when that slot is free on the part,
   as `_separate` does, and counts in a new `QuantizeReport.separated_close`; when the next slot is taken it stays
   merged and counts in `merged_distinct`. Drums are not changed (hits on one tick are several pads, not a chord).
   - Keep this rule only if the golden diff below shows it changes no reference song's Expert F1@50 by more than
     0.005 and lowers none; otherwise leave it out and say so in the report (the octave fix alone is this order's
     promise). Measure it alone (the octave fix off) and together.

## Tests

- `beatgrid`: `bpm_range` reaches every fold (a synthetic click at 198 BPM with `bpm=198, bpm_range=(170, 370)` gives
  a 198 BPM grid; the same audio with the defaults gives 99); the defaults unchanged (an existing fixture's grid is
  identical).
- `assemble.grid_octave`: synthetic parts at 16ths on a 198 BPM clock against a 99 BPM grid give octave 2 with the
  stats; the same at 8ths give 1; under `OCTAVE_MIN_ONSETS` give 1; a doubled tempo over 300 gives 1 with the reason.
- `assemble` end to end on a generated song (tests/test_assemble.py's style): the second pass runs, the report's
  `octave` is 2, the warning is there, the tempo map's median tempo is about doubled; `grid_octave: 1` forces the
  first grid; the confident-share guard keeps the first grid and warns.
- `quantize`: two onsets 50 ms apart on one tick become two notes on consecutive slots; 20 ms apart stay a chord; a
  taken next slot leaves them merged and counted.
- Each test fails when its code is broken (say which break).

## Evaluation

- **Golden** (the charting path changed; `beatgrid.py` is in `ENGINE_FILES["drums"]`): `--rerun drums` on both runs,
  `--expect none`. Every reference song's grid must be bit-identical with the defaults; the backstop rule may move a
  few notes: then `--expect` names those parts, and the report lists each changed song with its onsets and F1@50
  old → new (from `report.md`) and why it moved. Any song whose F1@50 falls on any part fails the order.
- **The stress set** (M5-09's check, `eval/README.md`'s "Stress songs" once merged; until then the same commands on
  the scratch folders): the power-metal song's chart before and after, scored against its three human charts. Pass:
  - the grid at about 198 BPM (report.json `grid.bpm_median` 190-206), `octave` 2;
  - guitar chord share under 0.10 (humans 0.03-0.05), quantize `merged` under 5 % of `notes_in`;
  - guitar F1@50 at least 0.70 against each human chart (0.58-0.59 today), bass and drums F1@50 not below today's
    (0.678, 0.857), matched notes' median timing error under 25 ms (62-68 today);
  - plain beat F1@70 ms at least 0.80 and octave-tolerant at least 0.90 (0.40 today);
  - the shred instrumental: no part's F1@50 or F1@100 lower than today's (guitar 0.636 / 0.743 and 0.725 / 0.748
    against its two charts, bass 0.653 / 0.691).
  These are 1-take CPU charts on the dev machine against the owner's 4-take numbers: compare with M5-09's baseline
  run of `main` (the same machine, 1 take), not with the owner's figures, and report both.

## Done means

- [dev] `uv run pytest -q` (the suite) passes; the new tests fail when their code is broken.
- [dev] The golden diff as above, exit 0, `report.md` in the report.
- [dev] The stress check's table, before and after, with the pass lines above.
- [CI] Green on the branch.
- [docs] DESIGN 2.3 (the octave pass, the threshold's table, the range parameter), 2.6 (the backstop rule and its
  measurement), 8.1's G1 row updated; `docs/work-orders/M5-99-later.md` gets the shred instrumental's double-tempo
  grid if this order does not touch it.

## Limits

- No change to `BPM_RANGE`'s default, to the quantizer's slot levels (1/16 and triplets stay: DESIGN 2.6) or to the
  HOPO rules. No new dependency.
- Nothing is read from the human charts but what `score.py` prints; no lyrics anywhere (the stress songs' charts have
  vocal tracks: never open their [Events]).

## Report

`<scratchpad>/briefs/m5-01.report.md`: the commits; the threshold table (every song's share, the two groups, the
midpoint); the golden `report.md`; the stress table before and after (every pass line with its number); what the
backstop rule did alone and together, and whether it stayed; anything uncertain.
