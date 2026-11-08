# M7-02 and M7-06: taps only in fast runs, four solos (the builder's report)

Branch `m7-02-taps-solos` from main c32f750, worktree `<wt>/m7-02`. Built from the orchestrator's brief: M7-00
sections 11-12, M7-01's A-b (taps) and B-c2 (solos), rule T2 exactly as eval/m7/A/analyze.py's `tapstates`
measured it.

**Superseded in part by the review fix (last section):** a tap outside a fast run now takes its natural state
on our grid (no flip), not a forced HOPO; the sections before it describe the first build.

## Commits

| commit | what |
|---|---|
| 40f67fb | M7-02: a tap is kept only inside a fast run; any other plays as a HOPO (quantize.py, tests/test_quantize.py) |
| cfa33c5 | M7-06: at most 4 solos a song (starpower.py; one warning string in assemble.py; a docstring in pipeline.py; tests/test_starpower.py) |
| f221ad2 | DESIGN 2.6 and 2.10 with the measured numbers; M5-99 narrowed |
| 529db65 | merge of main (3e6911b) |

## What changed

**The tap rule** (`songcharter/quantize.py`):
- `QuantizeRules.tap_run` (8, `TAP_RUN`) and `tap_run_gap_s` (0.125 s, `TAP_RUN_GAP_S`): in `_frets`, after the
  spacing drops, the merges and `run_chords`, every kept onset's time on our grid goes through the new
  `fast_runs(times, min_onsets, max_gap_s)` (analyze.py's loop: a run is consecutive onsets each at most
  0.125 s + 1e-9 after the one before; a run of 8 or more keeps its taps). A tap outside a run gets `tap=False,
  hopo=True`, so the final loop writes a flip wherever the natural state on our grid is a strum: it plays as a HOPO
  (natural, or flipped to one) under every HOPO rule ("forced", "source", "natural"). `tap_run` 0 is the old rule.
- The run counts every onset (chords, opens, untapped notes), not only taps, as T2 did.
- `QuantizeReport.taps_kept` and `taps_to_hopo` (report.json's `parts.*.quantize.<level>`, through `asdict`).
- In RULES, so every 5-fret part and every level the quantizer takes; HOPO_RULES inherit it. Lower levels reduced
  from Expert are untouched: reduce.py writes no tap below Expert and `hopo_states` reads a tap and a HOPO alike, so
  its Hard rule gives the same Hard (a test checks it, with two Hard HOPOs kept from former taps).
- Not touched: assemble.py's part rules, pipeline.py's `hopo`, reduce.py, score.py.

**Four solos** (`songcharter/starpower.py`): `SoloRules.max_solos` 3 -> 4; nothing else in the solo rules. Its
docstrings say 4. Two strings outside starpower.py said 3 and would have been wrong: assemble.py's warning for a
named section that got no solo now reads `SOLO_RULES.max_solos` (one import, one line; not near M7-09's octave
pass), and pipeline.py's module docstring says 4.

**Docs:** DESIGN 2.6 step 4 (the rule, A-b's numbers, the check's table; one sentence on A-a: no HOPO mode beats
"forced", so it stays), step 7, 2.0's taps row; DESIGN 2.10 (the count, B-c2's table, the check); M5-99's HOPO/tap
item and the slow-tempo sustain floor narrowed by M7-01 and M7-02. PROGRESS.json and the work orders are left to the
orchestrator.

## Tests (made-up data) and their breaks

New or changed tests:
- `test_fast_runs`: 8 onsets 0.125 s apart are a run, 7 are not, 0.1251 s apart are not, a gap splits 10 into 4 + 6,
  9 then a far one; 0 and 1 mean every onset.
- `test_a_tap_is_kept_only_inside_a_run_of_8_fast_onsets[first grid, halved grid]`: at 150 BPM (and 75 BPM with the
  halved slots, the same seconds) 8 taps on 16ths stay taps; 7 do not; 8 with one 0.2-s gap do not; 2 taps inside 10
  16ths stay (the run counts every onset); counts 10 kept / 15 to HOPO; `tap_run` 0 keeps all 25 and the same ticks.
- `test_tap_bursts_play_as_hopos[forced, source, natural]`: bursts of 2, 3 and 4 taps (with a same-fret repeat, a
  chord and an open) all play as HOPOs, flipped where the natural state is a strum (5 flips), under all three HOPO
  rules, whatever state the source gave them; `reduce.hopo_states` reads them as HOPOs as it read the taps; the
  reduced Hard/Medium/Easy equal those reduced from the tapped Expert, with 2 Hard HOPOs (80 BPM).
- `test_the_source_hopo_states_are_reproduced`: its lone tap checked under `tap_run` 0 (stays a tap) and under the
  default (plays as the natural HOPO it is, no extra flip).
- `test_at_most_four_solos_the_densest`: four candidates give four solos; of five (the share not binding: five 16-s
  solos in a 259-s span) the least dense is left out; at `max_solos` 5 all five; named sections held to 4.
- Updated for 4: `test_the_share_cap_trims_or_skips_a_solo_and_takes_the_next_that_fits` (its fourth candidate is now
  considered: skipped by the share at 0.25, placed at 0.40; the record's `max_solos` 4);
  `test_the_densest_solos_win` pins `max_solos=3` (its point is the ranking); the old
  `test_at_most_three_solos_with_the_most_notes` is replaced (at 4 its share cap, not the count, held the fifth back).

Breaks, each in a copy of the branch in /dev/shm (`<scratchpad>/m7/m7-02/breaks.py`), each reverted, all caught:

| break | tests that failed |
|---|---|
| B1 the rule never runs | a_tap_is_kept, tap_bursts, source_hopo_states |
| B2 a run needs 9 | fast_runs, a_tap_is_kept |
| B3 a run of 7 counts | fast_runs, a_tap_is_kept |
| B4 a gap of exactly 0.125 s ends a run | fast_runs |
| B5 gaps up to 0.25 s count | fast_runs, a_tap_is_kept, source_hopo_states |
| B6 a tap left to the natural rule (hopo None) | a_tap_is_kept, tap_bursts |
| B7 a tap takes its source state | a_tap_is_kept, tap_bursts, source_hopo_states |
| B8 taps_to_hopo not counted | a_tap_is_kept, tap_bursts, source_hopo_states |
| B9 taps_kept counted before the rule | a_tap_is_kept, source_hopo_states |
| B10 runs of taps only, not of every onset | a_tap_is_kept |
| B11 the default rule off (TAP_RUN 0) | all four |
| S1 max_solos 3 | at_most_four_solos, share_cap |
| S2 max_solos 5 | at_most_four_solos, share_cap |
| S3 the cap counted one past | at_most_four_solos |
| S4 names not held to the cap | at_most_four_solos |

After the breaks: the 9 targeted tests pass again.

## Checks

### The tap rule on the kept folders, in process (`<scratchpad>/m7/m7-02/check_taps.py`)

For each of the 8 songs with our taps: the kept engine take (`$DEV/golden/{work,stress-work,set20-work}/<id>/guitar/
seed_20260609/notes.chart`) re-quantized with the branch's quantizer, on the kept chart's own tempo map (read back
from its notes.chart), its pad (report.json's `pad_samples`), its applied offset and its grid octave, with the part's
rules (`assemble.part_rules`, "forced", `run_chord_s`); once with `tap_run` 0, once with the rule. The kept charts
are v031 (references), gate3-new-stress (stress) and set20-main (the 20-song set), which M7-01 found identical to its
base arm. The state agreement is analyze.py's: Expert guitar, matched at 100 ms with score.py's matcher, per chart
inside its span, the song's mean over its human charts.

Validation of the reproduction: with `tap_run` 0 every report.json quantize count matched (notes in/out, merged,
dropped, flips, ...), and at every onset of the kept chart the state matched (0 mismatches, 0 onsets missing, on all
8); the new rule changes no tick, fret or sustain. The rule's states equal analyze.py's T2 on the kept chart at every
matched note of every chart (0 notes differ).

| song (octave) | charts | our taps | kept | to HOPO | flips old -> new | T0 (part A) | rule (part A's T2) | gain |
|---|---|---|---|---|---|---|---|---|
| kimochi_warui (1) | 1 | 618 | 0 | 618 | 2 -> 395 | 0.474 (0.474) | 0.514 (0.514) | +0.040 |
| lucretia (1) | 1 | 8 | 0 | 8 | 534 -> 534 | 0.571 (0.571) | 0.572 (0.572) | +0.001 |
| drunk_drivers (1) | 1 | 3 | 0 | 3 | 44 -> 45 | 0.966 (0.966) | 0.966 (0.966) | +0.000 |
| sooth (0.5) | 2 | 312 | 31 | 281 | 108 -> 248 | 0.525 (0.525) | 0.569 (0.569) | +0.044 |
| troop (2) | 3 | 99 | 78 | 21 | 137 -> 146 | 0.668 (0.668) | 0.669 (0.669) | +0.001 |
| s06 (1) | 4 | 30 | 0 | 30 | 119 -> 149 | 0.659 (0.659) | 0.663 (0.663) | +0.004 |
| s07 (1) | 4 | 126 | 35 | 91 | 282 -> 303 | 0.700 (0.700) | 0.727 (0.727) | +0.027 |
| s09 (1) | 4 | 75 | 0 | 75 | 181 -> 210 | 0.618 (0.618) | 0.656 (0.656) | +0.038 |

Every song is the same as part A's numbers to the third decimal. The tap counts are the quantizer's over the whole
part (before the stem stage trims its edges), so a few exceed part A's in-span counts (613, 98). The other 15 songs'
kept charts have no Expert guitar tap (checked on each), so the rule cannot change them.

### Four solos on the kept charts, in process (`<scratchpad>/m7/m7-02/check_solos.py`)

`place_solos` on each of the 23 kept charts' Expert guitar onsets, tempo map and sections (report.json), solos mode
"labels" on all 23 (no stem read), at `max_solos` 3 and at the branch's 4 (`max_share` 0.40):
- at 3 it reproduces every kept chart's own solos (report.json's `phrases.guitar.solos`, within 0.05 s): 23 of 23;
- at 4 only pm2 (3 -> 4 solos, share 0.272 -> 0.320, the fourth at 204.0-225.3 s) and s06 (3 -> 4, share
  0.324 -> 0.380, the fourth at 165.1-197.2 s) change; nothing is dropped or moved anywhere, and no other song
  changes. The shares are B-c2's n4_s0.40 figures.

### The suite, CI

- The suite on the worktree at cfa33c5's code (the doc commit after it changes no file a test reads):
  `SONGCHARTER_SCAN_CHART=<wt>/base-main/tools/scan-chart/scan.cjs SONGCHARTER_HEAVY_MIN_FREE_GB=1 tools/heavy.sh
  .venv/bin/python -m pytest -q -p no:cacheprovider --basetemp=<shm>/pt-m7-02` (queued behind another agent's
  chart): `1154 passed, 6 skipped in 806.06s (0:13:26)`, exit 0.

- CI, `gh workflow run ci --ref m7-02-taps-solos`, run 42490233295
  (<repo>/actions/runs/42490233295) on the head f221ad2: success, both jobs. Linux:
  "Suite 1156 passed, 4 skipped in 377.65s", then "all 8 Linux hooks passed" (10-lanes .. 75-update); Windows:
  success. This order adds no CI hook (its checks are unit tests in the suite).
- main moved after the push (3e6911b, M8's contour spike: docs and eval/m8 only); brought in by a merge, 529db65
  (no rebase), the privacy check re-run (343 files, 0 found, exit 0) and CI re-run on the new head: run 42492313154
  (<repo>/actions/runs/42492313154), success on 529db65, both jobs: "Suite 1156
  passed, 4 skipped in 446.58s", "all 8 Linux hooks passed". The branch's head is 529db65.

### Privacy

`EVAL_DATA=$DEV/eval python3 -I eval/privacy_check.py`: "338 files, 14 md5s and 37 names checked, 0 found", exit 0.
The branch's diff and its commit messages were scanned for lyrics, audio, model names, paths and personal details:
none beyond the required trailers.

## Not done, uncertain

- No golden or stress runs (the orchestrator's, after the review). Expected: the guitar of the songs with taps changes
  (states only: flips and tap flags; onsets, frets and sustains identical, as the in-process check shows), pm2 and s06
  in solos.
- The precision of the taps the rule keeps (troop 78, s07 35, sooth 31) was not measured, here or in M7-01.
- A tap that becomes a HOPO is often a forced HOPO on a same-fret repeat or a chord (Kimochi Warui's flips 2 -> 395).
  That is what T2 measured (its played state "hopo"); whether a player finds forced HOPOs on repeats natural is a
  play-test question.
- The rule's runs are measured on the quantizer's onsets, before the stem stage trims a part's silent edges; at an
  edge a run could be cut afterwards. The in-process check found no note where this differs from T2 on the kept charts.
- assemble.py and pipeline.py were touched for the "3 solos" strings only (see above), outside M7-09's octave pass.

## Review fixes (2026-11-08)

The review's R1 (major) and its skeptic: forcing every tap outside a run to a HOPO flips notes the humans strum. The
orchestrator adopted the skeptic's broader fix, "NAT": such a tap takes its natural state on our grid, no flip.

**Commits:** 56850dc (the fix, its tests, DESIGN 2.6 step 4, M5-99), fd4b0fe (a merge of main's b319819: reports and
eval/m8 only, nothing of this branch's files). Head fd4b0fe.

**The change** (`songcharter/quantize.py` `_frets`): a tap outside a run gets `tap=False, hopo=None`, so the final
loop writes no flip: a HOPO where the natural rule makes one, else a strum; no note moves or goes; under every HOPO
rule. `QuantizeReport.taps_to_hopo` now counts the former taps that play as natural HOPOs, and the new
`taps_to_strum` those that strum (`taps_kept` as before). Docstrings, the constants' and the rules' comments, DESIGN
2.0's taps row, 2.6 step 4 and M5-99 say so.

**Tests:** `test_tap_bursts_take_their_natural_state[forced, source, natural]` (renamed from
`test_tap_bursts_play_as_hopos`): at 80 BPM bursts of 1-4 taps with every source state alternating: a burst's first
note after a rest strums, fret changes a 16th apart stay HOPOs, a burst on natural-HOPO positions after a plain note
stays HOPOs, a same-fret repeat strums (after a tap and after a plain note), a chord strums, a burst of 8ths strums;
no flip anywhere; counts 0 kept / 6 HOPO / 9 strum; `reduce.hopo_states` follows; Hard keeps one HOPO, at a former
tap that is a natural HOPO, and no tap. `test_a_tap_is_kept_only_inside_a_run_of_8_fast_onsets` now expects natural
states with no flip (the 0.2-s gap strums on the first grid, 96 ticks, and is a HOPO on the halved one, 48 ticks;
counts 10/12/3 and 10/13/2). `test_the_source_hopo_states_are_reproduced` checks `taps_to_strum` too.

Breaks (`<scratchpad>/m7/m7-02/breaks.py`, a copy in /dev/shm, each reverted), every one caught:

| break | tests that failed |
|---|---|
| N1 every former tap forced to a HOPO (the first build's T2) | a_tap_is_kept, bursts_natural |
| N2 a former tap takes its source state | a_tap_is_kept, bursts_natural, source_hopo_states |
| N3 a former tap on a same-fret repeat forced to a HOPO | bursts_natural |
| N4 every former tap forced to a strum | a_tap_is_kept, bursts_natural, source_hopo_states |
| N5 taps_to_hopo counts every former tap | a_tap_is_kept, bursts_natural |
| N6 taps_to_strum not counted | a_tap_is_kept, bursts_natural |
| N7 the former taps not recorded | a_tap_is_kept, bursts_natural, source_hopo_states |
| B1-B5, B9-B11 (as before), S1-S4 (the solos) | each caught again |

**The check, rerun** (`<scratchpad>/m7/m7-02/check_taps.py`, now with the fix and an independent recombination of
the kept chart's own states, each former tap given its natural state there): the old rule still reproduces every
kept chart; the fix changes no tick, fret or sustain and adds no flip (each song's flips as the kept chart's); its
states equal the recombination at every matched note (0 differ) on all 8. Per-note state agreement at 100 ms, the
song's mean over its human charts:

| song | taps kept / to HOPO / to strum | T0 | T2 (first build) | NAT (this fix) | vs T0 | vs T2 |
|---|---|---|---|---|---|---|
| kimochi_warui | 0 / 225 / 393 | 0.4740 | 0.5137 | 0.7555 | +0.2814 | +0.2418 |
| lucretia | 0 / 8 / 0 | 0.5712 | 0.5720 | 0.5720 | +0.0008 | 0 |
| drunk_drivers | 0 / 2 / 1 | 0.9661 | 0.9661 | 0.9661 | 0 | 0 |
| sooth | 31 / 141 / 140 | 0.5252 | 0.5693 | 0.6398 | +0.1146 | +0.0705 |
| troop | 78 / 12 / 9 | 0.6681 | 0.6686 | 0.6706 | +0.0026 | +0.0021 |
| s06 | 0 / 0 / 30 | 0.6595 | 0.6634 | 0.6659 | +0.0064 | +0.0025 |
| s07 | 35 / 70 / 21 | 0.7004 | 0.7271 | 0.7275 | +0.0272 | +0.0004 |
| s09 | 0 / 46 / 29 | 0.6180 | 0.6558 | 0.6492 | +0.0311 | -0.0066 |

The vs-T2 column equals the skeptic's numbers to four decimals. Pooled over the 23 songs (the other 15 have no tap,
0), bootstrap over songs as part A's (10,000, seed 7): NAT vs T2 +0.0135 [-0.0003, +0.0377]; NAT vs T0 +0.0202
[+0.0016, +0.0492]; T2 vs T0 +0.0067 [+0.0015, +0.0130] (part A's +0.007 [+0.002, +0.013]). No song below T0.

The humans' states at the 1,566 former taps they match (8 songs, every chart): same-fret repeats 338 (strum 213,
HOPO 60, tap 65); other natural-strum positions 497 (strum 385, HOPO 109, tap 3); natural-HOPO positions 731 (HOPO
498, strum 212, tap 21). So NAT matches the humans at 598 of 835 strum positions (72 %) and 498 of 731 HOPO positions
(68 %); a HOPO everywhere matches 667 of 1,566 (43 %). **One difference from the summary I was given:** the humans
do HOPO some repeats, 60 of 338 (s09 27 of 33, s07 10 of 13, s06 8 of 15, kimochi_warui 12 of 262), so "never" does not hold on these
counts (the skeptic may have counted another set of repeats). The 385 of 497 figure matches exactly. DESIGN cites my
counts.

**Suite and CI:** the suite on fd4b0fe through tools/heavy.sh (queued behind another agent's suite): `1154 passed, 6
skipped in 753.87s (0:12:33)`, exit 0. The privacy check before the push: "357 files, 14 md5s and 37 names checked,
0 found", exit 0; the diff and the commit messages scanned again (only the required trailers).

CI run 42496652242 (<repo>/actions/runs/42496652242) on fd4b0fe: success, both
jobs; Linux "Suite 1156 passed, 4 skipped in 529.55s", then "all 8 Linux hooks passed". Main has not moved since
the merge. Expected at the golden run: the 8 tap songs' Expert guitar states change (tap flags; flips as before, so
fewer than the first build's), onsets, frets and sustains identical; pm2 and s06 in solos.

---

## The review


### Findings

**R1 (major; it would change code, so a skeptic should check it).** songcharter/quantize.py:685-690. When the rule turns a tap on a same-fret repeat into a HOPO, the repeat gets a forced flip. Clone Hero plays that note as a HOPO on a fret that is already held, but the human charts mostly strum it. Kimochi Warui's flips go from 2 to 395, and 327 of the flipped notes are former taps on same-fret repeats. At the matched notes the human chart strums 187 of them, HOPOs 12 and taps 63. The proposed fix: T2, plus a former tap on a same-fret repeat stays in its natural state (a strum, no flip). Per song, against the shipped T2 (state agreement, the mean over each song's human charts):

| song | T2 (shipped) | T2 + repeats strummed | change | repeat taps per chart |
|---|---|---|---|---|
| kimochi_warui | 0.5137 | 0.7527 | **+0.2391** | 327 |
| sooth | 0.5693 | 0.5712 | +0.0020 | 9 |
| s06 | 0.6634 | 0.6631 | -0.0003 | 12 |
| s07 | 0.7271 | 0.7259 | -0.0012 | 4 |
| s09 | 0.6558 | 0.6518 | -0.0040 | 9 |
| lucretia, drunk_drivers, troop | unchanged | unchanged | 0 | 0 |

- Pooled over the 23 songs this adds about +0.010 on top of T2's +0.007. That is still under the +0.02 bar, and almost all of it comes from one song with one human chart. No song drops by more than 0.004.
- On s09 the humans HOPO 7 of 9 such repeats, so human charters do use forced HOPOs on repeats and Clone Hero plays them. The shipped state is not broken, only usually not what a human would chart.
- Changing chord taps to strums as well adds +0.001 on sooth only. It is not worth adding.
- **Recommendation: ship T2 with same-fret repeats strummed.** It is one condition in the rule: leave `n.hopo` at None, the natural state, when the onset is the same single note as the previous one. STRUM_SPACING_S and HOPO_SPACING_S are both 0.020 s, so no spacing check changes.
- Repro: `review_check_taps_repeats.py` in `<scratchpad>/m7/m7-02/` (the builder's check_taps.py plus the variant). Run it from the worktree with SONGCHARTER_SCAN_CHART set, through heavy.sh. Its output, for example: `VARIANT kimochi_warui: T2 0.5137 T2+rep-strum 0.7527 (+0.2391) ... humans-at-rep [{'strum': 187, 'hopo': 12, 'tap': 63}]`.

No other findings.

### Checked and clean

- **The rule.**
  - Every 8 songs' T2 numbers reproduce exactly. The old rule reproduces each kept chart.
  - The run is measured on the quantizer's onsets, after the takes are spliced (splice runs before quantize_part) and before trim_silent_edges. On the kept charts no case differs.
  - Reduced levels: reduce.py writes no tap, and hopo_states reads a tap and a HOPO the same way.
  - Determinism: the rule is a pure function of the ticks.
  - forced_only and natural: the rule sets `hopo=True`, which applies under all three HOPO rules.
- **Four solos.** The only "3" strings were in assemble.py and pipeline.py, and both now say 4. The UI, CLI and preview have no solo count. The tests are updated.
  - Gap: no test reads the assemble warning's text. If it were changed back to a literal 3, the tests would still pass. The text is correct today, so this is not a finding.
- **My own breaks of test_quantize.py.** Each one made the tests fail:
  - K2: the first onset of a run not marked as inside it.
  - K8: chord taps kept as taps.
  - K9: open taps kept as taps.
  - K10: the HOPO set only when source_hopo is on.
  - K11: the rule skipped when the source gave a state.
  - K12: run gaps measured in ticks as if the tempo were 150 BPM.
- **Docs.**
  - DESIGN 2.6 and 2.10 match M7-01: precision 0.061, recall 0.157, tap shares 0.041 / 0.031, T1 and T2 +0.007 with their CIs, the humans' tap shares per song, A-a's 52 % and 34 %, and the B-c2 table.
  - M5-99 matches.
  - DESIGN does not mention T3 (+0.008, from M7-01). If R1 is adopted, step 4 needs a sentence on it.

## The skeptic on R1 (partly confirmed)

The mechanism and the reviewer's numbers reproduced exactly (the skeptic's own recombination and two matchers; Clone Hero reads N 5 on a repeated single fret as a HOPO). Weakening it: at kimochi_warui's former taps the one human chart strums chords (our chart collapses them to repeated single notes), and the gain rests on that one chart (without it the repeat-only fix is -0.0002). Widening it: the same forced-HOPO mistake hits former taps whose natural state on our grid is a strum (the humans strum 385 of 497 there). Recommended: every tap outside a run keeps its natural state (NAT): +0.0135 [-0.0004, +0.0377] over the built rule, sooth +0.0705, s09 -0.0066, none below today. Adopted; the builder's counts (the humans HOPO 60 of 338 former taps on a repeat, mostly s09) correct the summary the orchestrator sent it, and DESIGN cites them.
