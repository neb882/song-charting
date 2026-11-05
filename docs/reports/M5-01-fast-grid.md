# M5-01 (fast grid): report

**What it builds:** the grid's tempo octave (doubling only), no chord made of notes distinct in time, and the
spacing floors at 20 ms. It also takes the orchestrator's four decisions of 2026-11-05: `BACKBEAT_MIN` measured;
the second pass keeps its hinted line, then runs the half-beat test; the doubled song's bass snaps one level
coarser; the guard is provisional.

**Branch:** local `m5-01-fast-grid` in `wt/m5-01`, rebased onto origin/main at e24b1b7 (after M5-09's merge).
- It is pushed as **`origin/m5-01-fast-grid-rebased`**. The pre-rebase commits sit on `origin/m5-01-fast-grid`,
  and replacing them would need a force push, which the rules forbid.
- The owner may delete the old remote branch.

## Commits (on e24b1b7)

- `06a7db6` quantize: no chord of notes distinct in time (the nearest stays), and the spacing floors at 20 ms
- `7640447` beatgrid: the fold range as a parameter (bpm_range), threaded through every tempo estimate
- `07e78d0` assemble: the grid's octave pass (doubling only), grid_octave in the config; thresholds partly
  provisional
- `e0f2218` beatgrid: a half-beat phase test for the second grid pass; BACKBEAT_MIN measured at 0.34
- `e2f8be5` DESIGN 2.3, 2.6, 8.1 and M5-99: the octave pass, its tables and decisions; the chord rule and the 20 ms
  floors
- `8d995e1` beatgrid keep_line for the second pass; on a doubled grid the bass snaps to the grid's 8ths
- `b5e0830` DESIGN and M5-99: keep_line and the bass on a doubled grid; the stress run's numbers
- `efd2d8d` M5-99: M5-01's numbers (HOPO states forced against source, dropped_distinct, the shred song's
  statistics, star power)

## What changed

**`beatgrid.py`:**
- **`bpm_range`** reaches every fold: `estimate_tempo` through `start_line`, `window_tempi`'s estimate and octave
  list, `local_periods`, `missed_tempo_changes`.
- **`half_beat`:** `half_beat_phase` compares the kick band at the lines and at their midpoints, medians over the
  confident beats. When the midpoints carry more kick, `shift_half_beat` moves the beats half a beat later, before
  the downbeats are found (`stats["half_beat"]`).
- **`keep_line`:** the tracker never replaces the hinted start line.
- The defaults are unchanged.

**`assemble.py`:**
- **`grid_octave`** (with `short_intervals`, `backbeat_ratio` and `OctaveRules`): octave 2 when the pooled density
  share is ≥ `OCTAVE_SHARE` (0.35), the backbeat ratio is ≥ `BACKBEAT_MIN` (0.34) or there are no drums, the
  doubled tempo is ≤ 300 BPM, and there are ≥ 200 onsets.
- **`_octave_pass`:** the second `beat_grid` at 2 × click bpm, with `bpm_range` (170, 370), no first-beat hint,
  `keep_line` and `half_beat`. The drum features are computed once for both passes and the test.
  - The guard: the doubled grid's confident share must be at least 0.7 × the first grid's, a ratio and provisional.
    When it fails, the first grid stays with the warning.
  - The "tempo doubled …" warning is given once.
  - `report.json`'s `grid` gets `octave`, `octave_stats` and `octave_reason`.
- **Config:** `grid_octave` is "auto", 1 or 2. A forced 2 skips the guard; a forced 2 past 300 BPM is an
  InputError.
- **Bass on a doubled grid:** `part_rules` gives the bass 2 straight and 3 triplet slots per beat
  (`DOUBLED_BASS_SLOTS`) and `report.json` records `parts.*.slots`. Every other part and every undoubled song is
  unchanged.

**`quantize.py`:**
- **The chord rule:** of the source onsets on one tick, the one nearest the tick stays, joined by every onset within
  20 ms of all those kept. The rest are dropped and counted in `dropped_distinct`, so `notes_in` = `notes_out` +
  `merged` + `dropped` + `dropped_distinct`. Drums are unchanged.
- **The floors:** `STRUM_SPACING_S` = `HOPO_SPACING_S` = 0.020.

**Docs:**
- DESIGN 2.3: step 7, and Goal 2's step 3 reason rewritten.
- DESIGN 2.6: step 2's spacing line; step 3's chord rule and floors, with the gap and sensitivity tables; the
  doubled-grid bass.
- DESIGN 8.1's G1 row.
- M5-99: the downbeat follow-up, the provisional guard, the HOPO-state table, the burst-slot numbers, the halving
  statistics, star power on a doubled grid.
- PROGRESS was not edited (per the brief).

## Checks

**Suite:**
- `tools/heavy.sh python -m pytest -q -p no:cacheprovider --basetemp=/dev/shm/m501-pt` (pre-rebase, a7cc14e plus
  the docs): `877 passed, 3 skipped in 608.38s`.
- CI ran the suite on the rebased branch (below).

**Breaks:** every new test was checked by breaking its code; each break was caught.
- 9 in `quantize.py`: the anchor, the rule off, the span rule, the dropped onset's state, the count, the floors at
  80 and 55, the floor made inclusive, the merge window at 40 ms.
- 8 for `bpm_range` in `beatgrid.py`.
- 5 for the half-beat test.
- 1 for `keep_line`, plus `keep_line` off in the second pass.
- 4 in `assemble.py`: the half-beat test off, `BACKBEAT_MIN` back at 0.8, the bass rule off, the bass rule on every
  part.
- A same-size break undone within a second leaves a stale `.pyc`, so the break script deletes `__pycache__` and
  runs with `-B`.

**CI:** https://github.com/neb882/song-charting/actions/runs/42067363211 on `m5-01-fast-grid-rebased`
(workflow_dispatch), **success** on both jobs.
- linux: suite `940 passed, 4 skipped in 287.68s`; the CI tools `86 passed`; the hooks ran.
- windows: success.
- This order adds no hook of its own.

## The octave tables

**The two tests on the first grid** (the engine charts in the kept folders; recomputed, every first grid matches
the golden base's `bpm_median` exactly):

| song | first grid BPM | guitar / bass / drums density | pooled | backbeat ratio |
|---|---|---|---|---|
| troop (power metal; half tempo) | 100.01 | 0.758 / 0.449 / 0.632 | **0.623** | **0.682** |
| test song | 142.00 | 0.003 / 0.087 / 0.003 | 0.025 | 0.002 |
| All the Small Things | 147.62 | 0.000 / 0.189 / 0.007 | 0.085 | 0.172 |
| Creep | 92.34 | 0.000 / 0.403 / 0.023 | 0.154 | 0.007 |
| Drunk Drivers | 117.00 | 0.038 / 0.118 / 0.000 | 0.049 | 0.004 |
| Kimochi Warui | 107.00 | 0.000 / 0.011 / 0.000 | 0.001 | 0.038 |
| Lucretia | 98.23 | 0.233 / 0.311 / 0.009 | **0.199** | 0.003 |
| Take Me Out | 105.34 | 0.013 / 0.014 / 0.001 | 0.009 | 0.001 |
| sooth (shred; at double) | 153.97 | 0.059 / 0.121 / 0.000 | 0.062 | 0.003 |
| break (ordinary rock) | 115.50 | 0.000 / 0.307 / 0.009 | 0.151 | 0.012 |

- **The two groups:** nine right grids against one at half tempo.
- **Density:** the largest right-grid share is 0.199 and the half-tempo share 0.623, a margin of ×3.14. The
  threshold is the geometric midpoint, 0.35.
- **Backbeat:** 0.172 against 0.682, a margin of ×3.95, so `BACKBEAT_MIN` = 0.34. The orchestrator decided this;
  the plan's fixed 0.8 vetoed the power-metal song.

**The guard** (the second pass run on every song):

| song | first → second confident share | ratio |
|---|---|---|
| troop | 0.819 → 0.817 (the tracker); 0.676 (the hinted line, as built) | 0.997; **0.828** as built |
| the nine others (their doublings are never chosen) | 0.659–0.910 → 0.512–0.752 | 0.631–0.936 |

- It is a ratio, because both shares scale with how much the drums play.
- 0.7 is provisional until the 20-song set. A doubled grid with evidence only on the first grid's beats would keep
  0.5. A guard set too high only falls back to v0.1's grid.

**The second pass's phase** on the power-metal song (stress.py, 1 CPU take):

| second pass | plain beat F1 | octave-tolerant |
|---|---|---|
| the tracker (as first specified) | 0.446 | 0.666 |
| the tracker + the half-beat test (kick ratio 2.24) | 0.549–0.557 | 0.660 |
| the hinted line, no test | 0.000 | 0.666 |
| **the hinted line + the half-beat test (built)** | **1.000** | **1.000** |

- The kick is on every beat and the snare on every "and".
- The tracker flips between the beats and their "and"s over parts of the song.
- The line is straight (residuals 3 ms), and the test moves all of it.

## Golden (`--rerun drums` on both runs; old = 8f57b88 at `/dev/shm/m501-main`, new = a7cc14e)

**Commands:**
- `python -m eval.golden run --code /dev/shm/m501-main --out <golden>/m5-01-old --threads 2 --rerun drums`: exit 0.
- `python -m eval.golden run --out <golden>/m5-01-new --threads 2 --rerun drums`: exit 0.
- `python -m eval.golden diff <golden>/m5-01-old <golden>/m5-01-new --expect guitar,bass`: **"golden diff: no
  UNEXPECTED change"**, exit 0.

**From `report.md`:**
- 32 parts changed, as expected. Drums are unchanged on all seven songs, and every grid and tempo map is identical.
- Beat F1 pooled 0.8755 → 0.8755. Every pooled F1@50 is unchanged:

  | part | expert | hard | medium | easy |
  |---|---|---|---|---|
  | guitar | 0.8527 | 0.8010 | 0.7474 | 0.6150 |
  | bass | 0.8247 | 0.7881 | 0.7920 | 0.6964 |
  | drums | 0.9617 | 0.9237 | 0.8787 | 0.7696 |

**What the chord rule did on the references:**
- Onsets are unchanged on every part. Only chord notes go, and per-song F1@50 and F1@100 are unchanged on every
  part, so no part loses more than 0.005 F1@50.
- The Expert parts that changed (notes before → after):
  - Kimochi Warui bass 185 → 184;
  - Drunk Drivers guitar 877 → 865, bass 591 → 574;
  - All the Small Things bass 1,075 → 1,068;
  - Lucretia guitar 1,526 → 1,387, bass 1,213 → 1,161;
  - Creep bass 708 → 659;
  - the test song guitar 1,926 → 1,925, bass 801 → 789.
  - Their lower levels follow.

**Chord shares** (ours → after, against the human's):
- Toward the human's:
  - Creep bass 0.074 → 0 (0);
  - Kimochi Warui bass 0.005 → 0 (0);
  - Lucretia bass 0.045 → 0 (0);
  - Drunk Drivers guitar 0.455 → 0.435 (0.299).
- Away from it (uncertain against the order's "toward or stay"):
  - **Lucretia guitar 0.184 → 0.080 (0.142)** overshoots, so the distance grows from 0.042 to 0.061;
  - All the Small Things bass 0.007 → 0 (0.41).
  - This matches the skeptic's split chords: an engine chord written more than 20 ms apart loses a note. F1 is
    unchanged.

## The stress set (M5-09's tools; base = stress-base, main at fbd9751, 1 CPU take)

**Commands:**
- `golden run --refs $EVAL_DATA/stress --work <golden>/stress-work --out <golden>/m5-01-stress --threads 2 --code
  wt/m5-01 --rerun drums`: exit 0.
- `stress.py score`: exit 0.
- `stress.py compare stress-base m5-01-stress`: exit 0, no regression.

**troop (power metal), base → new against the primary / alt1 / alt2 charts, every pass line:**

| line | base | new | owner's 4-take CUDA run | pass |
|---|---|---|---|---|
| `grid.bpm_median` 190–206, octave 2 | 100.0 | 200.0022, 2 | 100 | yes |
| guitar chord share < 0.10, toward 0.03–0.05 | 0.327 | 0.086 (humans 0.034–0.046) | 0.38 | yes |
| quantize `merged` < 5 % of `notes_in` | 776 / 2,193 | 0 | 740 / 2,085 | yes |
| `dropped` < 0.5 % | 0 | 0 | — | yes |
| `dropped_distinct` ≤ the humans' 6.37 % + 2 = 8.4 % | — | 17 (0.78 %) | — | yes |
| guitar F1@50 ≥ base + 0.10 | 0.614 / 0.623 / 0.632 | **0.784 / 0.784 / 0.808** | 0.58–0.59 | yes (+0.17/+0.16/+0.18; the plan's first line 0.70 met; the humans' ceiling 0.917–0.925) |
| bass F1@50 ≥ base | 0.702 | **0.716** | 0.678 | yes |
| drums F1@50 ≥ base | 0.851 | 0.879 | 0.857 | yes |
| guitar median timing error < 15 ms | 62–69 | 2.9 / 3.9 / −3.1 | 62–68 | yes |
| plain beat F1@70 ≥ 0.80 | 0.30 | **1.000** (×3) | — | yes |
| octave-tolerant ≥ 0.90 | 0.40 | **1.000** (×3) | 0.40 | yes |
| downbeat F1 (reported only) | 0.064–0.070 | **0.000** | — | — (`bar_phase` margin 0.013: M5-99) |
| guitar state agreement (forced) ≥ base | 0.49 / 0.51 / 0.51 | 0.65 / 0.67 / 0.68 | — | yes |

- F1@100: guitar 0.637–0.652 → 0.805–0.823, bass 0.736 → 0.726, drums 0.872 → 0.885.
- Star power: 2.42 → **5.04 phrases a minute** (the humans 3.03–4.44). The phrases double with the grid; the
  reviewer looks at this before the gate.
- Sustain share 0.039 (the humans 0.040–0.065).

**sooth (shred)** stays at octave 1, every part's F1@50 and F1@100 equal to the base:
- guitar 0.651 / 0.765 and 0.789 / 0.790;
- bass 0.692 and 0.734;
- beat F1 0.644 (octave-tolerant 0.963–0.978).
- `dropped` 0 → 0; `dropped_distinct` guitar 52 (2.4 %) and bass 81 (3.9 %), where the base had merged 52 and 81.
- Star power 3.88 a minute (the humans 2.33 / 3.23).

**break (rock)** is unchanged: guitar 0.832 / 0.841; beat F1 0.994 / 1.000.

## Bass on the doubled grid (the diagnosis behind decision 3)

This is the signed error of the matched bass onsets against the primary human chart, from a numbers-only script.
Half a 16th at 200 BPM is 37.5 ms.

| chart | matched@100 | median ms | p10 / p90 ms | within 50 ms | past half a 16th late / early |
|---|---|---|---|---|---|
| the bass engine's onsets | 1,291 of 1,821 | +22.9 | −75.0 / +64.6 | 819 | 415 / 303 |
| first grid (100 BPM) | 1,216 | −2.6 | −6.7 / +71.9 | 993 | 203 / 46 |
| doubled, 1/16 slots | 1,293 | −0.6 | −75.0 / +75.4 | 756 | 232 / 334 |

- It is not the offset. The engine's onsets spread about a 16th either side, and the doubled grid's 16ths kept that
  error (F1@50 0.606).
- With the grid's 8ths (`DOUBLED_BASS_SLOTS`), F1@50 is 0.716.
- On the coarser slots the engine's doubles land on one 8th, so `dropped_distinct` is 316 of 1,821 (17.4 %), where
  the base merged 369. Bass chord share is 0.

## `dropped_distinct` against the humans' own figure

The humans' figure is each chart through `quantize_part` on its own map as a perfect engine. A numbers-only script
read the vocals-stripped `$EVAL_DATA/stress` refs.

| song | humans, guitar | ours, guitar | humans, bass | ours, bass |
|---|---|---|---|---|
| troop | 5.40 / 6.37 / 5.71 % | 0.78 % | 0.05 % | 17.4 % (the engine's doubles; see above) |
| sooth | 22.0 / 23.5 % (charted at half our tempo) | 2.4 % | 3.72 % | 3.9 % |
| break | 1.81 / 0.90 % | 0 | — | 14.7 % (the bass engine's doubles; merged before) |

The floors drop nothing anywhere (`dropped` is 0 on every human chart and every stress build's 5-fret part).

## HOPO states (step 6), troop and sooth rebuilt with "source"

| song, part | HOPO share: base, forced / source (humans) | state agreement: base / forced / source |
|---|---|---|
| troop guitar, 3 charts | 0.29, 0.24 / 0.25 (0.51, 0.21, 0.29) | 0.49–0.51 / 0.65–0.68 / 0.66–0.70 |
| troop bass | 0.21, 0.03 / 0.17 (0.12) | 0.78 / 0.95 / 0.82 |
| sooth guitar, 2 charts | 0.34, 0.34 / 0.42 (0.55, 0.39) | 0.56, 0.66 / 0.56, 0.67 / 0.60, 0.68 |
| sooth bass | 0.11, 0.11 / 0.12 (0.12) | 0.92 / 0.91 / 0.91 |

The F1s are the same under both modes. No default changed; the numbers are in M5-99.

## Uncertain or not done

- **The thresholds rest on one positive example** (the power-metal song). The guard is provisional.
- **Lucretia's guitar chord share** overshoots the human's (above).
- **Downbeats on the power-metal song** are wrong (F1 0.000); that is M5-99's.
- **Star power** doubles on a doubled grid (5.04 a minute against the humans' 3.03–4.44).
- **The bass rule rests on one song** at a doubled grid.
- **Process notes:**
  - The local suite ran before the rebase; CI ran on the rebased branch.
  - The golden and stress runs used the pre-rebase code (a7cc14e). The rebase added only M5-09's eval code and
    tests.
  - All runs were 1 CPU take. The owner's 4-take CUDA figures are quoted only beside them.
- **Hard rules:**
  - I scanned the diff against origin/main and the commit messages for model names, paths, personal details and
    lyrics: none found.
  - Human charts were read only by score.py, stress.py and two numbers-only scripts (`human_perfect.py`,
    `bass_timing.py`), kept in the scratchpad. No chart was opened with Read, cat or grep, and no lyric event was
    read.

## Review fixes (commit 48b1018)

The review found no major and five minor findings; each was handled as the orchestrator decided.

**F1, accepted with no code change** (DESIGN 2.6: the order's line read by its intent; the owner decides at the
gate). Five level-parts' chord shares move away from the human's, in the golden scores (old → new, human):

| part | old | new | human |
|---|---|---|---|
| Lucretia guitar Expert | 0.184 | 0.080 | 0.142 |
| Lucretia guitar Hard | 0.191 | 0.097 | 0.188 |
| Lucretia guitar Medium | 0.185 | 0.094 | 0.203 |
| All the Small Things bass Expert and Hard | 0.007 | 0 | 0.41 |

- The dropped onsets lie 50.5 / 75.8 / 101 ms (p10 / p50 / p90) from the kept one, none 20–40 ms. The reviewer's
  counts: Lucretia guitar 149 of 1,433, Lucretia bass 172 of 1,333, Creep bass 154 of 813, Drunk Drivers guitar 12
  of 611.
- So these are distinct fast notes the old quantizer merged into chords the engine never heard.

**F2, fixed.** `half_beat_phase` shifts only above 1.25 × the lines' kick (`HALF_BEAT_SHIFT`). From 0.8 to 1.25
nothing moves, `stats["half_beat"]["unsure"]` is set, and the build warns "beat phase unsure: …".
- Tests: 0.5 (no shift, no flag), 0.98 and 1.02 (no shift, unsure), 1.3 (shift); the warning through
  `_octave_pass`.
- Breaks caught: the bound at 1.0, the bound at 0.5, no unsure flag, no warning.

**F3, tested.** A forced `grid_octave` 2 keeps a doubled grid with a guard ratio of 0.5, and auto falls back. The
break dropping `forced or` is caught.

**F4, tested.** After the shift, `stats["half_beat"]["confident_after"]` equals the moved beats' own mask, which
differs from the pre-shift share, and the downbeat phase and times equal `bar_phase` on the moved beats with that
mask. The stale-mask break (resized) is caught.

**F5, tested.** Each break is caught:
- the mix's features given to the backbeat test;
- `backbeat_ratio` ignoring the confident mask;
- `short_intervals` using the later onset's beat.

**The earlier breaks, all re-run and caught:** 9 for the half-beat test and `bpm_range`, 10 in assemble.

**Checks after the fixes:**
- **Targeted tests** pass.
- **Suite:** `tools/heavy.sh python -m pytest -q -p no:cacheprovider --basetemp=/dev/shm/m501-pt` gives `947 passed,
  3 skipped in 673.81s`, on the rebased tree with M5-06 and M5-09.
- **CI:** https://github.com/neb882/song-charting/actions/runs/42073192677 on `m5-01-fast-grid-rebased`: success.
- **The power-metal stress song rerun** (`golden run --refs $EVAL_DATA/stress --songs troop --rerun drums`,
  `stress.py score`, `stress.py compare` against a troop-only copy of stress-base's scores: exit 0):
  - every number equals the first stress run: guitar F1@50 0.784 / 0.784 / 0.808, bass 0.716, drums 0.879, beat F1
    1.000 (×3), guitar error 2.9 / 3.9 / −3.1 ms, chord share 0.09;
  - the half-beat ratio is 2.53 (shifted, not unsure);
  - `notes.chart` differs from the first run only in `[Song] Album`, which comes from main's M5-06 (merged before the
    rebase), not this order.
- **Golden recheck:** `golden run --out <golden>/m5-01-new2 --threads 2 --rerun drums` at 48b1018, then `golden diff
  m5-01-new m5-01-new2 --expect none`: "no UNEXPECTED change", exit 0.
  - "Parts changed as expected: 0. Every song's results (hashes, counts, scores) identical: yes."
  - So every reference's grid, tempo map and chart is bit-identical after the fixes and the rebase.

## Review (sc-reviewer, 2026-11-05)

# M5-01 review (charting-path correctness lens), origin/m5-01-fast-grid-rebased efd2d8d

No major defect. What I checked and found sound:
- The golden tempo maps are identical: [SyncTrack] and [Events] md5 old = new on all 7 songs, octave 1 everywhere, ExpertDrums identical.
- The charting code that was run equals the head: `git diff a7cc14e efd2d8d -- beatgrid/quantize/assemble` is empty.
- The chord rule is the nearest onset plus a 20 ms span, the rest dropped and never moved. The floors are 20 ms with a 1e-9 margin, and the accounting identity holds.
- `bpm_range` reaches every fold. keep_line and half_beat are only on the second pass. Features are computed once. Forced 2 past 300 BPM is an InputError. There is no new randomness.

13 breaks made in /dev/shm/review_m501; 5 caught (A3 backbeat sign, A7 pooling, Q4 anchor without shift, Q6 span vs anchor, B5 shift_half_beat's first beat). The survivors are below.

## F1 minor (gate decision): the "chord shares toward the humans' or stay" line fails on 5 level-parts, 3 of them unreported
Golden scores (m5-01-old -> m5-01-new, ref):
- lucretia guitar/expert 0.1838 -> 0.0802 (0.1416)
- guitar/hard 0.1913 -> 0.0972 (0.1876)
- guitar/medium 0.1849 -> 0.0942 (0.2025)
- all_the_small_things bass/expert and bass/hard 0.007 -> 0 (0.41)

The builder's report gives only the Expert figure; Hard was 0.004 off the human's and is now 0.090 off.

It is not split strums. I spied on `_one_time` on the engine charts (`scratchpad/rev/spread.py`): the dropped onsets lie 50.5/75.8/101 ms (p10/50/90) from the kept onset, and none lies 20-40 ms away. The counts: lucretia guitar 149/1433, lucretia bass 172/1333, creep bass 154/813, drunk_drivers guitar 12/611.

These are distinct fast notes that used to be merged into chords. The rule works as the order intends; the engine lacks real chords. The owner needs to waive the literal line at the gate.

## F2 minor: the half-beat test has no margin
beatgrid.py, half_beat_phase: `shift = bool(ratio > 1.0)`.
- Break B4 (`> 0.5`) survives: 30 passed in tests/test_beatgrid.py.
- The repro is a 198 BPM grid already on the pulse, with a double kick on every 8th. Kick at the "and"s 0.98x: `shifted False, ratio 0.98`. At 1.02x: `shifted True, ratio 1.02`.
- So on a doubled song with even double kicks, the whole grid moves half a beat on noise, with no warning. bar_phase, by contrast, has a margin and warns.
- Proposed fix: a margin, plus an "uncertain" warning or an entry in M5-99.

## F3 minor: a forced grid_octave 2 skipping the guard is untested
assemble.py _octave_pass: `if forced or ratio >= rules.evidence_min:`.
- Break A1 (drop `forced or`) survives: 10 passed, the octave tests in test_assemble.py.
- A forced 2 could then quietly fall back to 1, against the docstring and the report.

## F4 minor: the downbeats after the half-beat shift are untested
beatgrid.py beat_grid: `confident = local_beats(f, onset_beats).confident`.
- Break B2 (keep the stale mask, truncated or padded) survives: 30 passed.
- test_the_half_beat_test_puts_the_lines_on_the_kick asserts only `len(moved.downbeats)`.
- The stress song's downbeat F1 is already 0.000 (margin 0.013, M5-99).

## F5 minor: the octave test's inputs are untested
Each break survives the octave tests (10 passed):
- A2 passes the features for a mix-sourced grid too (`features if src == "drums" else None` -> `features`);
- A4 has backbeat_ratio ignore the confident-beat mask;
- A6 has short_intervals take the later onset's beat.

## Notes for the gate (not defects against the order)
- **Star power** 2.42 -> 5.04 phrases a minute on troop (humans 3.03-4.44). The order expected this and leaves the phrase rule to M5-99.
- **Bass dropped_distinct of 15-17 %**: the bass engine's double onsets, 60-100 ms apart. They are also on the references (creep 19 %), where they were merged before (bass chord share 0.07 -> 0, humans 0). The order's +2-point line sits among the guitar lines. Say whether it binds the bass.
- **Thresholds**: the guard holds troop at 0.828 against 0.7, a thin margin. The share and backbeat thresholds rest on one positive song. Both are documented as provisional.
