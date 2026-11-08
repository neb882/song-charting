# M7-09's measurement: the halved grid's tempo shape (2026-11-08)

Main 6a8b1e8 (<wt>/orch, read only). In process, CPU, no engine, no golden run. Scripts here: `measure.py`
(one song per run: rebuilds the first grid, today's halved grid and the candidates from the kept folder; writes
<shm>/m709/out/<label>.json, copied into `results.json`), `tables.py` (the tables below), `drift_guard.py` (guard 2
on the 24 golden runs' report.json), `ratio_guard.py` (an extra guard, see below).

## How

- **today**: `_halving_pass`'s call, `beat_grid(start=allin1 + 22 ms, bpm_range=(42.5, 92.5), keep_line, no half-beat)`,
  then `with_downbeats` from allin1. Calibration: in-process beats against our chart's beats, median 0.6-1.2 ms
  (p95 2.7 ms) on sooth, s02, s04; ntl's tempo map came out 74.321-86.937 BPM as in its report, and its off-grid
  count came out 8 of 42 as in the review.
- **a0 / a1**: every other beat of the first grid as built (its line where the first grid is click, as on ntl; its
  free curve where it is free, as on sooth, s02, s04), each parity, passed as `start=` through the same path as today
  (the free curve fades to the LOESS of those beats). `a_pick` is the parity matching more allin1 beats (70 ms).
- **b**: inside `beat_grid` with `start=`: a robust straight line through the start beats, extended over the song;
  the tracker (allin1's beats) is used only when its confident share is `TRACKER_MARGIN` (0.10) above the line's,
  as on the first pass; otherwise the line path (and click/free by `FREE_SHARE`).
- **c**: today's tracker path, but the base is allin1's LOESS faded to the robust line by the drums' support
  (LOESS support over +-8 beats, `clip(support/0.5)`, step-limited at `MAX_TEMPO_STEP`).
- Variants are today's `beat_grid` source with two inserted blocks (exec'd in a copy of the module namespace; the repo
  is not touched).
- **Beat / downbeat F1**: the scorer's match (70 ms) and `prf`, `n_cand_eff` over the span (the primary's
  `ref_span_s`, an alt's onset range); human beat and measure lines from `score.beat_times` / `downbeat_times` on the
  charts' tempo maps (via M7-01 B's `common.build`); our beats moved by the lead-in pad and `cand_total_shift_ms`.
  Per stretch: today's report stretches (>= 16 beats, under half timed), simple F1 inside each.
- **BPM range**: 240 / (4-beat span), p1-p50-p99 (min-max). `drift_ms` from the grid's stats.
- **Guitar phase**: the guitar (or other) stem's `onset_times`, as positions on the grid's onset-time beats; R8 =
  |mean e^(2 pi i 2u)| (8th-level concentration), whole song and 0-35 s.
- **ntl off-grid**: the real path (`plan_lead_in`, `TempoMap.from_beats`, `offset_map`, `_offset`, `_quantize` at octave
  0.5) on each grid; distinct guitar note ticks off the 48-tick grid (an 8th at the first grid's level; the 96-tick
  count does not give the review's 8 of 42, the 48-tick one does), in the audio window of today's ticks 4608-8640.
- **Guard 1**: `missed_tempo_changes(features, beats with midpoints, BPM_RANGE)`: the halved grid at the first grid's
  fold ("tc first fold"; window BPM / grid BPM). "tc halved" is today's check in the halved fold.
- **Guard 2**: `drift_ms` p95 > 2 beats of the grid's median tempo, on the 24 report.json of v031 (7),
  gate3-final-stress (4), set20-main (13), and on each candidate.
- **owner_sim**: the owner's file has no kept folder, so: the stress set's sooth audio and stems, with the owner's
  chart beats (its SyncTrack minus its pad, aligned by the offset that matches today's halved beats under 480 s:
  6.365 s, 607 of 607 matched) standing in for allin1's beats. Tail = the owner file's last 28 s. Downbeat F1 there
  is meaningless (no allin1 downbeats: kick phase), and its beat F1 is against the stress audio's humans.

## Results (per song and candidate)

### sooth

first grid 153.97 BPM, free (tracker), share 0.682; allin1 76.92 BPM; a parity matches to allin1 {'0': 308, '1': 367} -> a1; errors none; calibration {'today_vs_chart_median_ms': 1.197, 'today_vs_chart_p95_ms': 2.645, 'n_chart_beats_in_audio': 707, 'n_today_beats': 689}

| grid | start | mode | ev ratio | BPM p1-p50-p99 (min-max) | drift p95 ms (2 beats) | tc halved | tc first fold | gtr R8 whole / 0-35s | beat F1 alt1 | beat F1 primary | downbeat F1 alt1 | downbeat F1 primary |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| today | tracker | free | 1.171 | 70.0-77.0-80.1 (68.4-80.1) | 3717 (1558) FIRES | 0 | 0 | 0.072 / 0.212 | 0.981 | 0.980 | 0.980 | 0.983 |
| a0 | tracker | free | 1.038 | 62.3-77.0-80.1 (58.6-80.1) | 3296 (1559) FIRES | 0 | 290-310s 105/131; 295-315s 105/131 | 0.076 / 0.207 | 0.444 | 0.443 | 0.438 | 0.439 |
| a1 | tracker | free | 0.965 | 61.4-77.0-80.1 (58.6-80.2) | 3338 (1558) FIRES | 0 | 290-310s 105/129; 295-315s 105/129 | 0.076 / 0.208 | 0.531 | 0.527 | 0.409 | 0.410 |
| b | tracker | free | 1.171 | 70.0-77.0-80.1 (68.4-80.1) | 3717 (1558) FIRES | 0 | 0 | 0.072 / 0.212 | 0.981 | 0.980 | 0.980 | 0.983 |
| c | tracker | free | 1.134 | 69.1-77.4-102.5 (67.4-108.0) | 3381 (1551) FIRES | 5 | 5-25s 100/195; 10-30s 100/192; 15-35s 100/178; 20-40s 100/161 | 0.050 / 0.134 | 0.908 | 0.889 | 0.876 | 0.861 |

per straight-line stretch (today's report stretches, >= 16 beats, under half timed), beat F1:

| grid | 174-197s (30) alt1 | 174-197s (30) primary | 372-394s (30) alt1 | 372-394s (30) primary |
|---|---|---|---|---|
| today | 0.966 | 0.983 | 0.983 | 0.983 |
| a0 | 0.000 | 0.000 | 0.983 | 0.983 |
| a1 | 0.966 | 0.983 | 0.000 | 0.000 |
| b | 0.966 | 0.983 | 0.983 | 0.983 |
| c | 0.561 | 0.448 | 0.983 | 0.678 |

### s02

first grid 142.38 BPM, free (tracker), share 0.419; allin1 74.07 BPM; a parity matches to allin1 {'0': 254, '1': 104} -> a0; errors none; calibration {'today_vs_chart_median_ms': 0.597, 'today_vs_chart_p95_ms': 2.653, 'n_chart_beats_in_audio': 498, 'n_today_beats': 476}

| grid | start | mode | ev ratio | BPM p1-p50-p99 (min-max) | drift p95 ms (2 beats) | tc halved | tc first fold | gtr R8 whole / 0-35s | beat F1 alt1 | beat F1 primary | downbeat F1 alt1 | downbeat F1 primary |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| today | tracker | free | 1.279 | 61.5-73.1-153.8 (56.1-154.3) | 13845 (1642) FIRES | 0 | 245-265s 141/280; 250-270s 139/278; 255-275s 139/277; 260-280s 139/277; 265-285s 139/277; 270-290s 139/278; 275-295s 139/277; 280-300s 139/276 | 0.106 / - | 0.789 | 0.748 | 0.702 | 0.680 |
| a0 | tracker | free | 1.146 | 69.3-71.3-76.1 (68.8-76.6) | 899 (1684) | 0 | 0 | 0.094 / - | 0.580 | 0.530 | 0.130 | 0.170 |
| a1 | tracker | free | 0.742 | 69.1-71.3-76.2 (68.8-76.6) | 749 (1684) | 0 | 0 | 0.095 / - | 0.253 | 0.241 | 0.104 | 0.079 |
| b | tracker | free | 1.279 | 61.5-73.1-153.8 (56.1-154.3) | 13845 (1642) FIRES | 0 | 245-265s 141/280; 250-270s 139/278; 255-275s 139/277; 260-280s 139/277; 265-285s 139/277; 270-290s 139/278; 275-295s 139/277; 280-300s 139/276 | 0.106 / - | 0.789 | 0.748 | 0.702 | 0.680 |
| c | tracker | free | 0.742 | 69.9-93.8-146.9 (68.7-153.0) | 9506 (1272) FIRES | 15 | 75-95s 143/252; 80-100s 143/250; 85-105s 144/252; 90-110s 143/216; 95-115s 145/189; 100-120s 145/171; 105-125s 141/168; 110-130s 143/171; 115-135s 143/171; 175-195s 143/174; 230-250s 152/217; 235-255s 134/250; 245-265s 141/278; 250-270s 139/277; 255-275s 139/277; 260-280s 139/276; 265-285s 139/276; 270-290s 139/276; 275-295s 139/229; 280-300s 139/201; 285-305s 141/191 | 0.049 / - | 0.356 | 0.303 | 0.207 | 0.177 |

per straight-line stretch (today's report stretches, >= 16 beats, under half timed), beat F1:

| grid | 8-88s (93) alt1 | 8-88s (93) primary | 106-120s (19) alt1 | 106-120s (19) primary | 217-229s (17) alt1 | 217-229s (17) primary | 321-348s (33) alt1 | 321-348s (33) primary |
|---|---|---|---|---|---|---|---|---|
| today | 0.884 | 0.591 | 0.389 | 0.343 | 0.417 | 0.424 | 0.281 | 0.339 |
| a0 | 0.253 | 0.254 | 1.000 | 0.970 | 0.435 | 0.645 | 0.094 | 0.185 |
| a1 | 0.116 | 0.000 | 0.000 | 0.000 | 0.391 | 0.000 | 0.222 | 0.188 |
| b | 0.884 | 0.591 | 0.389 | 0.343 | 0.417 | 0.424 | 0.281 | 0.339 |
| c | 0.132 | 0.179 | 0.167 | 0.229 | 0.085 | 0.125 | 0.092 | 0.061 |

### s04

first grid 146.59 BPM, free (tracker), share 0.575; allin1 73.17 BPM; a parity matches to allin1 {'0': 299, '1': 29} -> a0; errors none; calibration {'today_vs_chart_median_ms': 1.039, 'today_vs_chart_p95_ms': 2.572, 'n_chart_beats_in_audio': 360, 'n_today_beats': 350}

| grid | start | mode | ev ratio | BPM p1-p50-p99 (min-max) | drift p95 ms (2 beats) | tc halved | tc first fold | gtr R8 whole / 0-35s | beat F1 alt1 | beat F1 alt2 | beat F1 alt3 | beat F1 alt4 | beat F1 primary | downbeat F1 alt1 | downbeat F1 alt2 | downbeat F1 alt3 | downbeat F1 alt4 | downbeat F1 primary |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| today | tracker | free | 1.466 | 62.0-73.0-77.9 (61.6-78.3) | 1007 (1643) | 0 | 0 | 0.343 / 0.735 | 0.176 | 0.176 | 0.170 | 0.186 | 0.956 | 0.059 | 0.059 | 0.048 | 0.037 | 0.965 |
| a0 | tracker | free | 1.343 | 69.7-73.2-77.9 (69.2-78.3) | 972 (1640) | 0 | 0 | 0.325 / 0.526 | 0.173 | 0.173 | 0.173 | 0.198 | 0.857 | 0.048 | 0.048 | 0.048 | 0.037 | 0.856 |
| a1 | tracker | free | 0.652 | 70.1-73.1-77.7 (69.8-77.9) | 977 (1639) | 0 | 0 | 0.330 / 0.522 | 0.177 | 0.177 | 0.173 | 0.155 | 0.090 | 0.036 | 0.036 | 0.036 | 0.062 | 0.081 |
| b | tracker | free | 1.466 | 62.0-73.0-77.9 (61.6-78.3) | 1007 (1643) | 0 | 0 | 0.343 / 0.735 | 0.176 | 0.176 | 0.170 | 0.186 | 0.956 | 0.059 | 0.059 | 0.048 | 0.037 | 0.965 |
| c | tracker | free | 1.386 | 66.1-73.1-78.3 (65.2-79.0) | 873 (1641) | 0 | 0 | 0.314 / 0.430 | 0.156 | 0.156 | 0.164 | 0.195 | 0.878 | 0.048 | 0.048 | 0.036 | 0.037 | 0.861 |

per straight-line stretch (today's report stretches, >= 16 beats, under half timed), beat F1:

| grid | 275-290s (16) alt1 | 275-290s (16) alt2 | 275-290s (16) alt3 | 275-290s (16) alt4 | 275-290s (16) primary |
|---|---|---|---|---|---|
| today | - | - | 0.000 | - | 0.000 |
| a0 | - | - | 0.000 | - | 0.303 |
| a1 | - | - | 0.105 | - | 0.121 |
| b | - | - | 0.000 | - | 0.000 |
| c | - | - | 0.000 | - | 0.065 |

### ntl

first grid 150.00 BPM, click (line), share 0.498; allin1 75.00 BPM; a parity matches to allin1 {'0': 222, '1': 26} -> a0; errors none; calibration None

| grid | start | mode | ev ratio | BPM p1-p50-p99 (min-max) | drift p95 ms (2 beats) | tc halved | tc first fold | gtr R8 whole / 0-35s |
|---|---|---|---|---|---|---|---|---|
| today | tracker | free | 1.160 | 74.6-75.0-86.7 (74.5-87.0) | 5 (1600) | 1 | 0 | 0.303 / 0.176 |
| a0 | tracker | free | 1.103 | 74.7-75.0-75.2 (74.5-75.3) | 4 (1600) | 0 | 0 | 0.312 / 0.263 |
| a1 | tracker | free | 0.912 | 74.8-75.0-75.2 (74.7-75.2) | 7 (1600) | 0 | 0 | 0.309 / 0.245 |
| b | line | click | 1.103 | 75.0-75.0-75.0 (75.0-75.0) | 4 (1600) | 0 | 0 | 0.312 / 0.269 |
| c | tracker | free | 1.160 | 73.4-75.0-76.8 (72.7-77.5) | 4 (1600) | 0 | 0 | 0.313 / 0.252 |

ntl guitar notes off the 48-tick grid after the real quantizer (window = ticks 4608-8640 of today's chart, in audio time):

| grid | 19-33 s | rest | tempo map BPM | markers |
|---|---|---|---|---|
| today | 8 of 42 | 5 of 447 | 74.3-86.9 | 35 |
| a0 | 0 of 41 | 4 of 448 | 74.5-75.2 | 17 |
| a1 | 0 of 42 | 4 of 447 | 74.7-75.2 | 22 |
| b | 0 of 41 | 4 of 448 | 75.0-75.0 | 1 |
| c | 8 of 41 | 4 of 448 | 72.1-78.0 | 29 |

### owner_sim

first grid 153.97 BPM, free (tracker), share 0.682; allin1 77.57 BPM; a parity matches to allin1 {'0': 310, '1': 393} -> a1; errors none; calibration {'today_vs_chart_median_ms': 1.532, 'today_vs_chart_p95_ms': 365.319, 'n_chart_beats_in_audio': 707, 'n_today_beats': 743}

| grid | start | mode | ev ratio | BPM p1-p50-p99 (min-max) | drift p95 ms (2 beats) | tc halved | tc first fold | gtr R8 whole / 0-35s | beat F1 alt1 | beat F1 primary | downbeat F1 alt1 | downbeat F1 primary |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| today | tracker | free | 1.141 | 70.3-77.7-160.2 (69.4-160.6) | 16695 (1549) FIRES | 1 | 0 | 0.088 / 0.209 | 0.944 | 0.945 | 0.006 | 0.000 |
| a0 | tracker | free | 1.038 | 62.3-77.0-80.1 (58.6-80.1) | 3296 (1559) FIRES | 0 | 290-310s 105/131; 295-315s 105/131 | 0.076 / 0.207 | 0.444 | 0.443 | 0.438 | 0.439 |
| a1 | tracker | free | 0.965 | 61.4-77.0-80.1 (58.6-80.2) | 3338 (1558) FIRES | 0 | 290-310s 105/129; 295-315s 105/129 | 0.076 / 0.208 | 0.531 | 0.527 | 0.006 | 0.006 |
| b | tracker | free | 1.141 | 70.3-77.7-160.2 (69.4-160.6) | 16695 (1549) FIRES | 1 | 0 | 0.088 / 0.209 | 0.944 | 0.945 | 0.006 | 0.000 |
| c | tracker | free | 1.012 | 67.5-77.1-133.7 (64.7-144.9) | 4612 (1556) FIRES | 7 | 5-25s 100/193; 10-30s 100/190; 15-35s 100/177; 20-40s 100/158; 510-530s 160/233; 515-535s 160/233 | 0.070 / 0.065 | 0.806 | 0.800 | 0.011 | 0.006 |

owner file: offset 6.365 s, 607 of 607 beats matched; its tail 160.0 BPM; its tempo map 68.224-160.246

| grid | tail BPM (last 28 s) | tail beats |
|---|---|---|
| today | 160.029 | 70 |
| a0 | 79.986 | 34 |
| a1 | 79.967 | 34 |
| b | 160.029 | 70 |
| c | 90.583 | 38 |

## Guards

**Guard 1, `tempo_check` at the first grid's fold** (the halved grid's beats with midpoints, `BPM_RANGE`):
- ntl intro: today 0 windows (today's halved-fold check does flag 15-35 s at 50 vs 78.6 BPM, and that warning *is*
  in ntl's report.json: the plan's "no warning fired" holds for the owner's sooth file, not for ntl).
- owner_sim 160 BPM tail: 0 windows on today and b (the 160 BPM tail doubled is 320 against a 160 window: the
  autocorrelation margin stays under `LOCAL_TEMPO_MARGIN`). Does not flag it.
- other halved songs: sooth 0 (today, b); s02 8 windows at 245-300 s (the grid at 139 BPM; the primary chart is at
  69.6 there, alt1 at 140.2: a real octave split, not noise); s04 0. On a0/a1 it flags sooth 290-315 s (the first
  grid's slipped line).
- So guard 1 as specified catches neither target.

**Guard 2, `drift_ms` p95 > 2 beats**: fires on 10 of the 24 golden runs (ref5 17.3 beats, pm2 9.8, sooth 4.8,
s02 16.9, s06 34.6, s07 26.0, s08 8.4, s09 6.0, s10 20.9, s11 2.4; table in `drift_guard.json`), on the owner's file
(21.4 beats) and not on ntl (0.01). No threshold separates the owner's file from the others (s06 34.6 and s07 26.0
are above it). On the halved songs it fires on today's sooth and s02. Too noisy as a warning: drift_ms on a tracker
grid measures the song's distance from a straight line, not an error.

**Extra (not asked; `ratio_guard.py`)**: the first grid's median beat period over the halved grid's per 20-s window,
outside 2 +-10 %. On today/b it flags the owner tail (x1.0 at 510-545 s), sooth 290-315 s (x1.65: the first grid's
slip, not a halved-grid fault), s02 0-25 s and 225-265 s (x1.0, the octave split above); s04 and ntl nothing. A
narrower form, "the halved grid back at the first grid's tempo (ratio within 10 % of 1)", flags only the owner tail
and s02 225-265 s. Not in the brief's guard list; reported for the builder.

## The bar

| candidate | sooth / s02 / s04 beat F1 primary (delta) | worst stretch delta | ntl intro off-grid | owner tail | clears |
|---|---|---|---|---|---|
| today | 0.980 / 0.748 / 0.956 | - | 8 of 42 | 160.0 BPM, unflagged by guard 1 | no |
| a (a_pick) | a1 0.527 (-0.453) / a0 0.530 (-0.218) / a0 0.857 (-0.099) | -0.983 (sooth 372-394 s, a1) | 0 of 41 | 80.0 BPM | no |
| b | 0.980 / 0.748 / 0.956 (0.000 each; alt charts the same) | 0.000 | 0 of 41 | 160.0 BPM (b = today: tracker wins on margin) | no (owner tail) |
| c | 0.889 (-0.091) / 0.303 (-0.445) / 0.878 (-0.078) | -0.535 (sooth 174-197 s) | 8 of 41 | 90.6 BPM | no |

**None clears the whole bar.** b clears the beat F1 bar (identical to today on sooth, s02 and s04, every chart,
every stretch) and ntl (0 of 41 off the grid, a flat 75.0 BPM map, 1 marker, guitar R8 0-35 s 0.176 -> 0.269). On
the owner's file b is today: the tracker's share beats the line's by more than 0.10 on sooth's audio, so the tail
stays at 160 BPM, and neither specified guard flags it (guard 1: 0 windows; guard 2 fires, but on 10 of 24 runs).
a fixes ntl and the tail but loses 0.10-0.45 beat F1 on every halved song with humans (sooth both parities: the
first grid slips a line, so each parity loses one stretch entirely). c helps nothing.

The nearest to clearing: **b with a guard that reads the halved grid against the first grid** (ratio_guard's narrow
form: flag a window where the halved grid runs at the first grid's tempo), which flagged the owner tail and one s02
stretch where the humans themselves split by an octave. That pairing is not measured on the real owner's audio.

## Caveats

- Five songs (three with humans: 2, 2 and 5 charts). s04's four alt charts score 0.16-0.20 on every candidate
  (their beat lines seem at another octave or offset; the primary at 0.956 matches the stress scores); deltas, not
  levels, are read there.
- owner_sim is a simulation: the stress set's audio with the owner's beats in allin1's place. The real owner audio's
  tail may differ (that is where its allin1 diverged); guard 1's result there especially may not transfer.
- Today's in-process primary F1 for sooth is 0.980 against the stress scores' 0.985 (my span/match protocol, not the
  scorer run on a chart).
- One CPU run per song; no GPU check; no engine, so note-level effects beyond ntl's quantized count are not measured.
- c's fade width (+-8 beats) and b's line (robust fit of the start beats) are my choices; the brief left them open.

## The orchestrator's decision (2026-11-08)

Build **candidate b** (a straight line through the halved start beats, kept against the tracker by the first pass's
`TRACKER_MARGIN` evidence test: no change on the three halved songs with human charts, ntl's intro one flat 75 BPM
with its onsets on the grid) **with the ratio guard as a warning** (`ratio_guard.py`: a 20-s window where the halved
grid's beat period is back within 10 % of the first grid's says "the halved grid runs at the first grid's tempo at
X-Y s: check sync"; it fires on the owner's sooth file's outro and on s02's 245-300 s, where its human charts
themselves disagree by an octave, and nowhere else). The `tempo_check` at the first fold (caught nothing) and the
`drift_ms` warning (fires on 10 of 24 runs) are dropped. Correcting such a window (halving it there) is M8's, with
measurements on more songs whose audio ends that way.
