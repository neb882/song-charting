# M7-01: the video reviews' questions, measured against the human charts (2026-11-07/08)

Three sc-measurers (parts A, B and C of docs/work-orders/M7-01-measure.md) on the 23 songs with human charts (the
six references, the stress set's four, the 20-song set's 13 new songs as s01-s13), on main's charting code (a5895ff,
v0.3.1); about 21 hours of machine time in all (A 7.4 h, B 0.5 h, C 7.7 h of takes and 2.8 h of arms, much of it
queued on one heavy-job lock). Part D (the owner's GPU takes) was not run. Each part's own report follows; their
numbers, JSON and scripts were kept in the session's scratch folder, the scripts committed under eval/m7/ (paths as
placeholders).

## What each build order's bar got

| order | the question | best candidate | against the bar | outcome |
|---|---|---|---|---|
| M7-02 | the guitar's HOPO mode (A-a) | A2 "natural" +0.014 [-0.011, +0.044], four songs down > 0.03; R1 +0.005 (sooth +0.113, s10 -0.080) | +0.02, CI above 0, no song down 0.03: no | the engine's forced flags are near coin flips against the humans (forced strums: the humans strum 52 %; forced HOPOs: the humans HOPO 34 %) |
| M7-02 | taps (A-b) | T2, taps only in runs of 8+ notes at 8+ a second: +0.007 [+0.002, +0.013] pooled; on the 8 songs with our taps +0.000..+0.044, none down | the HOPO bar's "on top" is moot; on its own: no song down, CI above 0 | **built (the orchestrator's decision):** our taps match a human tap 6 % of the time |
| M7-02 | sustain floor in seconds (A-c) | A1 (300 ms cap): guitar +0.001 on the slow songs | +0.03 on the slow songs: no | the shortfall is notes the engine never holds, not the floor |
| M7-03 | the bass (B-b) | the lane map +0.011 [+0.004, +0.020]; the held-note gate F1 -0.015, references down | +0.02 / F1 held: no | one more rule (a run of repeats over one voiced pitch) to measure before closing |
| M7-04 | notes over a silent stem (B-a); same-fret repeats (A-d) | guitar removal precision 0.09-0.14; every repeat rule lowers F1 (gap150 -0.040) | precision 0.80 / 0.75: no | closed |
| M7-05 | the take margin (C) | q05 (silent onsets unscored, margin 0.05) +0.0032 [-0.0001, +0.0094]; margins 0-0.10 within +-0.004 | +0.005, CI above 0: no | closed; the take score (agreement among takes) does not track the humans at window level (119-133 of 431 windows pick a take 0.05 below the best); 4 spliced takes against one: +0.004 [-0.009, +0.019] |
| M7-06 | solos (B-c, B-c2) | max_share 0.60: songs move away; max_solos 4: pm2 and s06 gain, coverage +0.012 [0.000, 0.035], none away | coverage up pooled: on its CI's edge | **max_solos 4 (the orchestrator's decision)** |
| M7-07 | drumless stretches (B-d) | allin1 at our octave +0.060 [-0.102, +0.132], 7 of 36 stretches down > 0.05 | no stretch down 0.05: no | closed; the halved grid's tempo shape is M7-09 |
| — | drums: kicks and fill crashes (B-e) | kick thinning right on troop and s06 only (precision 0.97/0.93), wrong elsewhere; a crash at our crashless fill ends 0.35 | — | closed (kick precision 0.911: the humans chart our kicks) |
| — | open notes, HOPO chords, fast-run repeats (A-e) | open share ours 0.007, humans 0.040; HOPO chords 0.029 vs 0.039; fast-run repeats 0.251 vs 0.180 | — | the GPU takes write open notes and the CPU takes do not: part D's question; fast runs: the M8 contour spike |


---

## Part A: M7-01 part A: articulation, sustains and the guitar's repeats (and A-e)

All numbers are Expert, matched at 100 ms (A-d at 50 ms), against every human chart. A song's value is its mean over
its charts; pooled = mean over songs; brackets = difference from base with a paired bootstrap over songs (10,000
resamples) 95 % CI. Columns: all 23 songs / without the six references (17) / without songs whose humans agree under
0.6 on that measure (no song fell under 0.6 on guitar states or on either part's sustains, so the third column is the
first). Floats rounded to 3 decimals.

### The arms and the base check

- Four builds (base, A1 "source" + cap 300 ms, A2 "natural" + cap 400 ms, A3 "forced" + cap 500 ms) of the 23 songs,
  each from a git worktree of main 72f5679 in <shm>/m7/code-<arm> with an uncommitted patch (scripts/patch_arm.py:
  guitar `hopo` in pipeline.py's guitar part; `quantize.sustain_kept` for expert/hard: kept iff >= 200 ms and (>= 0.75
  beat or >= cap)). eval.golden run, --threads 2, scored with stress.py score (references: golden's own scores/).
- **Deviation from the order:** "no --rerun" failed at once (exit 2: "bass ran without being asked: the bass engine's
  kept output did not answer"), so every arm ran with `--rerun bass` (the same for all four arms). Drums/sections came
  from the kept folders (the known 8ba3cbd flag).
- **Base vs the earlier runs (v031, gate3-final-stress, set20-main): identical.** Every track (guitar, bass, drums,
  each of 4 levels) and the tempo map, note by note (tick, type, length, flags), on all 24 song folders (23 + the
  test song); scripts/compare_prior.py, base_vs_prior.json. gate3-final-stress was compared as charts, not scored.
- Our onsets are identical across the four arms on every song and part (0 mismatches), so per-note rules R1/R2/T*/A-d
  are exact recombinations.
- Bass `hopo` stays "forced" in every arm; the floor cap reaches the bass too (reported in A-c).

### Against M7-02's bar

- **HOPO rule (+0.02 pooled, CI above 0, no song down > 0.03):** none clears. A1 +0.005 [-0.008, +0.020] (s10 -0.080,
  lucretia -0.060); A2 +0.014 [-0.011, +0.044] (4 songs down > 0.03, worst s04 -0.084, s02 -0.074, drunk_drivers
  -0.053; big gains lucretia +0.196, s11 +0.196, s07 +0.079, s03 +0.079); R1 (octave rule) +0.005 [-0.007, +0.019],
  on its 7 songs: +0.113 sooth, +0.040 s04, +0.025 s02, +0.011 troop, +0.008 pm2, +0.003 s01, **-0.080 s10** (mean
  +0.017); R2 +0.001 [-0.018, +0.025] (3 songs down > 0.03). The engine's forced strums are strummed by the humans
  only 52 % of the time (forced HOPOs: 34 % HOPO'd; unforced notes: 72 % strummed): its forced flags are near coin
  flips in both directions, which is why no global mode wins.
- **Taps (not lower than the HOPO rule alone, tap precision up):** T1 (no taps) +0.007 [+0.002, +0.014] and T2 (runs
  >= 8 at >= 8/s) +0.007 [+0.002, +0.013] over T0, both CIs above 0 but small; T3 (no tap on a same-fret repeat)
  +0.008 [+0.000, +0.023], driven by kimochi_warui (+0.17). Today's tap precision is 0.061 (8 songs with our taps),
  recall 0.157: our taps are mostly wrong. No HOPO rule clears its bar, so "taps on top of it" is moot; as a lone
  change T1/T2 raise agreement, and T2 removes taps outside fast runs (precision of what is left not measured).
- **Sustain floor (+0.03 on the slow songs, no other song down > 0.01, share nearer the humans):** none clears.
  Guitar, slow songs: A1 +0.001 [-0.004, +0.006], A2 -0.001, A3 0.000; bass slow: A1 +0.016 [-0.019, +0.047], A2
  +0.010 [+0.001, +0.028], A3 +0.005. No non-slow song moves down. The floor rarely bites our own notes (guitar
  sustain share 0.072 -> 0.078 at A1) though it would drop 46 % of the humans' slow-song sustains today (A1: 13 %):
  our sustain shortfall (0.072 vs humans 0.106) comes from notes the engine never holds, not from the floor.
- **A-d (M7-04's repeat removals):** every rule lowers F1@50 (gap150 -0.040, best gap250+stem p25 -0.002 [-0.006,
  -0.000]); removal precision 0.13-0.27: 73-87 % of the removed repeats have a human note within 50 ms. None clears.

### Songs left out and why

- Bass: drunk_drivers and break have no bass part to score (21 songs for bass).
- Taps precision: songs with no taps of ours are not in its mean (8 songs have taps); recall: 13 songs with human taps.
- Fast-run repeat shares: only songs with a run of >= 8 onsets at <= 125 ms gaps (ours 10 songs, humans 15).
- A-e opens: pm2 has **no** opens in our CPU base chart (the 420 opens are the owner's GPU chart, not measured here).

### Machine time and disk

Wall time per arm (refs / stress / 20-song set, seconds, including heavy-lock queueing behind part C): base 734 /
1759 / 3145; A1 1307 / 2064 / 3648; A2 1612 / 3028 / (rescored only: 2071, the build ran in a run cut at 2 h); A3
2535 / 4338 / 4841. About 7.4 h of wall time in all, most of it queueing. Builds in <shm>/m7 (RAM), deleted; the
worktrees removed (git worktree remove). `df -h /` at the end: see the last line.

### Scripts (scripts/)

- patch_arm.py: reads a checkout's pipeline.py/quantize.py, writes the arm's patch; prints the arm.
- run_arm.sh / run_all.sh / gr.sh: build, score and keep one arm / all four (resumable); print progress lines.
- mkprior.sh: lays the earlier runs out as an arm; prints nothing. compare_prior.py: base vs those runs, prints counts.
- alib.py: loader (scores, human charts via scan_notes.cjs, labels), bootstrap; prints nothing.
- analyze.py: reads the arms' charts, the human charts and the kept guitar stems; writes A.json; prints labels.
- report.py: reads A.json, writes tables.md and A_pooled.json. round_json.py: rounds the JSON floats to 3 decimals.

Definitions taken where the order left a choice: "engine forced strum" = A1 (source) strums a note A2 (natural)
HOPOs; R2 = base with those notes set to HOPO; a fast run = >= 8 onsets each <= 125 ms apart; T3 turns a tap on a
repeat into a strum; A-d's stem test uses librosa onset_strength (22.05 kHz, hop 512) peak over [t, t+60 ms] (the
envelope peaks 25-50 ms after our onsets), percentile over our own onsets' values; "inside a human sustain" = any
chart's held note spans it; the floor-drop share judges each human sustain against max(200 ms, min(0.75 beat of our
grid at that time, cap)).

## The tables
### A-a. The HOPO rule (Expert guitar; state agreement at 100 ms, song mean over its human charts)

| song | octave | charts | base | A1 source | A2 natural | R1 | R2 (notes changed) | humans | HOPO share base / A1 / A2 / humans |
|---|---|---|---|---|---|---|---|---|---|
| all_the_small_things | 1 | 1 | 0.997 | 1.000 | 0.997 | 0.997 | 0.997 (0) | - | 0.006 / 0.003 / 0.003 / 0.000 |
| creep | 1 | 1 | 0.976 | 0.976 | 0.976 | 0.976 | 0.976 (20) | - | 0.000 / 0.000 / 0.029 / 0.033 |
| drunk_drivers | 1 | 1 | 0.966 | 0.968 | 0.913 | 0.966 | 0.926 (19) | - | 0.107 / 0.105 / 0.099 / 0.113 |
| kimochi_warui | 1 | 1 | 0.474 | 0.474 | 0.477 | 0.474 | 0.474 (0) | - | 0.002 / 0.002 / 0.000 / 0.164 |
| lucretia | 1 | 1 | 0.571 | 0.512 | 0.767 | 0.571 | 0.762 (527) | - | 0.294 / 0.256 / 0.699 / 0.692 |
| take_me_out | 1 | 1 | 0.946 | 0.947 | 0.921 | 0.946 | 0.921 (51) | - | 0.120 / 0.121 / 0.179 / 0.132 |
| break | 1 | 2 | 0.923 | 0.923 | 0.909 | 0.923 | 0.900 (13) | 0.993 | 0.048 / 0.048 / 0.056 / 0.106 |
| pm2 | 2 | 5 | 0.687 | 0.694 | 0.656 | 0.694 | 0.658 (177) | 0.758 | 0.371 / 0.371 / 0.425 / 0.302 |
| sooth | 0.5 | 2 | 0.525 | 0.638 | 0.529 | 0.638 | 0.525 (19) | 0.741 | 0.647 / 0.421 / 0.615 / 0.472 |
| troop | 2 | 3 | 0.668 | 0.679 | 0.683 | 0.679 | 0.683 (103) | 0.661 | 0.243 / 0.252 / 0.275 / 0.337 |
| s01 | 2 | 4 | 0.825 | 0.828 | 0.824 | 0.828 | 0.821 (8) | 0.796 | 0.142 / 0.150 / 0.144 / 0.150 |
| s02 | 0.5 | 2 | 0.835 | 0.859 | 0.761 | 0.859 | 0.760 (65) | 0.767 | 0.132 / 0.101 / 0.202 / 0.185 |
| s03 | 1 | 2 | 0.913 | 0.913 | 0.992 | 0.913 | 0.913 (0) | 0.989 | 0.079 / 0.079 / 0.000 / 0.011 |
| s04 | 0.5 | 5 | 0.740 | 0.781 | 0.656 | 0.781 | 0.653 (111) | 0.673 | 0.179 / 0.107 / 0.326 / 0.190 |
| s05 | 1 | 6 | 0.987 | 0.987 | 0.987 | 0.987 | 0.987 (0) | 0.995 | 0.014 / 0.014 / 0.014 / 0.002 |
| s06 | 1 | 4 | 0.659 | 0.657 | 0.655 | 0.659 | 0.659 (2) | 0.699 | 0.319 / 0.375 / 0.267 / 0.487 |
| s07 | 1 | 4 | 0.700 | 0.731 | 0.779 | 0.700 | 0.803 (202) | 0.891 | 0.318 / 0.350 / 0.392 / 0.522 |
| s08 | 1 | 6 | 0.785 | 0.790 | 0.791 | 0.785 | 0.782 (23) | 0.840 | 0.189 / 0.214 / 0.191 / 0.165 |
| s09 | 1 | 4 | 0.618 | 0.611 | 0.618 | 0.618 | 0.605 (52) | 0.693 | 0.404 / 0.318 / 0.353 / 0.527 |
| s10 | 2 | 4 | 0.755 | 0.675 | 0.755 | 0.675 | 0.755 (0) | 0.678 | 0.034 / 0.147 / 0.034 / 0.236 |
| s11 | 1 | 4 | 0.656 | 0.658 | 0.852 | 0.656 | 0.672 (59) | 0.948 | 0.289 / 0.287 / 0.133 / 0.207 |
| s12 | 1 | 2 | 0.827 | 0.836 | 0.857 | 0.827 | 0.827 (1) | 0.842 | 0.261 / 0.269 / 0.199 / 0.288 |
| s13 | 1 | 2 | 0.678 | 0.695 | 0.689 | 0.678 | 0.673 (14) | 0.654 | 0.324 / 0.295 / 0.295 / 0.228 |

Pooled (mean over songs; in brackets the difference from base, paired bootstrap 95 % CI):

| | all songs | without the references | without humans under 0.6 |
|---|---|---|---|
| base | 0.770 n=23 | 0.752 n=17 | 0.770 n=23 |
| A1 | 0.775 (+0.005 [-0.008, +0.020]) n=23 | 0.762 (+0.010 [-0.006, +0.027]) n=17 | 0.775 (+0.005 [-0.008, +0.020]) n=23 |
| A2 | 0.784 (+0.014 [-0.011, +0.044]) n=23 | 0.764 (+0.012 [-0.014, +0.044]) n=17 | 0.784 (+0.014 [-0.011, +0.044]) n=23 |
| R1 | 0.775 (+0.005 [-0.006, +0.019]) n=23 | 0.759 (+0.007 [-0.009, +0.024]) n=17 | 0.775 (+0.005 [-0.006, +0.019]) n=23 |
| R2 | 0.771 (+0.001 [-0.018, +0.025]) n=23 | 0.746 (-0.006 [-0.024, +0.013]) n=17 | 0.771 (+0.001 [-0.018, +0.025]) n=23 |
| bass, base (every arm: bass stays "forced") | 0.837 n=21 | 0.827 n=16 | 0.847 n=20 |

Songs whose humans agree under 0.6 on the guitar's states: none.
Songs off octave 1: pm2 (2), sooth (0.5), troop (2), s01 (2), s02 (0.5), s04 (0.5), s10 (2).

Per song, the songs R1 touches (octave not 1):

| song | octave | base | R1 = A1 | R1 - base | humans |
|---|---|---|---|---|---|
| pm2 | 2 | 0.687 | 0.694 | 0.008 | 0.758 |
| sooth | 0.5 | 0.525 | 0.638 | 0.113 | 0.741 |
| troop | 2 | 0.668 | 0.679 | 0.011 | 0.661 |
| s01 | 2 | 0.825 | 0.828 | 0.003 | 0.796 |
| s02 | 0.5 | 0.835 | 0.859 | 0.024 | 0.767 |
| s04 | 0.5 | 0.740 | 0.781 | 0.040 | 0.673 |
| s10 | 2 | 0.755 | 0.675 | -0.080 | 0.678 |

**The confusion by the engine's flag** (matched notes, summed over every song and human chart; "forced strum": the engine strums a note our natural rule makes a HOPO, i.e. A1 strum and A2 HOPO; "forced HOPO" the reverse; "unforced": A1 and A2 agree; "tap": a tap in either):

| class | notes | human strums | human HOPOs | human taps |
|---|---|---|---|---|
| forced_strum | 6118 | 0.519 | 0.463 | 0.018 |
| forced_hopo | 4825 | 0.580 | 0.338 | 0.082 |
| unforced | 68366 | 0.716 | 0.241 | 0.043 |
| tap | 1948 | 0.467 | 0.436 | 0.097 |

Per song, the forced strums (notes; share the humans strum, mean over charts):

| song | octave | forced strums | humans strum | forced HOPOs | humans HOPO |
|---|---|---|---|---|---|
| all_the_small_things | 1 | 2 | 1.000 | 0 | - |
| creep | 1 | 20 | 0.500 | 0 | - |
| drunk_drivers | 1 | 20 | 1.000 | 10 | 0.800 |
| kimochi_warui | 1 | 0 | - | 2 | 0.000 |
| lucretia | 1 | 614 | 0.225 | 56 | 0.768 |
| take_me_out | 1 | 50 | 0.700 | 1 | 1.000 |
| break | 1 | 13 | 0.846 | 4 | 0.100 |
| pm2 | 2 | 184 | 0.741 | 32 | 0.500 |
| sooth | 0.5 | 498 | 0.703 | 46 | 0.366 |
| troop | 2 | 89 | 0.302 | 44 | 0.687 |
| s01 | 2 | 49 | 0.855 | 78 | 0.278 |
| s02 | 0.5 | 66 | 0.733 | 6 | 0.389 |
| s03 | 1 | 0 | - | 60 | 0.000 |
| s04 | 0.5 | 97 | 0.756 | 4 | 0.340 |
| s05 | 1 | 0 | - | 0 | - |
| s06 | 1 | 8 | 0.345 | 154 | 0.418 |
| s07 | 1 | 204 | 0.106 | 111 | 0.886 |
| s08 | 1 | 44 | 0.557 | 70 | 0.224 |
| s09 | 1 | 212 | 0.484 | 136 | 0.513 |
| s10 | 2 | 30 | 0.796 | 151 | 0.174 |
| s11 | 1 | 62 | 0.367 | 274 | 0.081 |
| s12 | 1 | 4 | 0.750 | 64 | 0.337 |
| s13 | 1 | 28 | 0.696 | 24 | 0.311 |

### A-b. Taps (Expert guitar, base charts)

| song | tap share ours | humans | our taps | human taps | precision | recall | T0 | T1 no taps | T2 runs >= 8 at >= 8/s |
|---|---|---|---|---|---|---|---|---|---|
| all_the_small_things | 0.000 | 0.000 | 0 | 0 | - | - | 0.997 | 0.997 | 0.997 |
| creep | 0.000 | 0.000 | 0 | 0 | - | - | 0.976 | 0.976 | 0.976 |
| drunk_drivers | 0.005 | 0.000 | 3 | 0 | 0.000 | - | 0.966 | 0.966 | 0.966 |
| kimochi_warui | 0.611 | 0.103 | 613 | 79 | 0.103 | 0.797 | 0.474 | 0.514 | 0.514 |
| lucretia | 0.006 | 0.000 | 8 | 0 | 0.000 | - | 0.571 | 0.572 | 0.572 |
| take_me_out | 0.000 | 0.000 | 0 | 0 | - | - | 0.946 | 0.946 | 0.946 |
| break | 0.000 | 0.000 | 0 | 0 | - | - | 0.923 | 0.923 | 0.923 |
| pm2 | 0.000 | 0.176 | 0 | 678 | - | 0.000 | 0.687 | 0.687 | 0.687 |
| sooth | 0.142 | 0.033 | 312 | 78 | 0.035 | 0.140 | 0.525 | 0.569 | 0.569 |
| troop | 0.045 | 0.124 | 98 | 318 | 0.337 | 0.105 | 0.668 | 0.672 | 0.669 |
| s01 | 0.000 | 0.013 | 0 | 20 | - | 0.000 | 0.825 | 0.825 | 0.825 |
| s02 | 0.000 | 0.000 | 0 | 0 | - | - | 0.835 | 0.835 | 0.835 |
| s03 | 0.000 | 0.000 | 0 | 0 | - | - | 0.913 | 0.913 | 0.913 |
| s04 | 0.000 | 0.018 | 0 | 13 | - | 0.000 | 0.740 | 0.740 | 0.740 |
| s05 | 0.000 | 0.004 | 0 | 4 | - | 0.000 | 0.987 | 0.987 | 0.987 |
| s06 | 0.014 | 0.063 | 30 | 164 | 0.000 | 0.000 | 0.659 | 0.663 | 0.663 |
| s07 | 0.076 | 0.001 | 126 | 1 | 0.010 | 1.000 | 0.700 | 0.738 | 0.727 |
| s08 | 0.000 | 0.080 | 0 | 174 | - | 0.000 | 0.785 | 0.785 | 0.785 |
| s09 | 0.049 | 0.000 | 74 | 0 | 0.000 | - | 0.618 | 0.656 | 0.656 |
| s10 | 0.000 | 0.035 | 0 | 60 | - | 0.000 | 0.755 | 0.755 | 0.755 |
| s11 | 0.000 | 0.000 | 0 | 0 | - | - | 0.656 | 0.656 | 0.656 |
| s12 | 0.000 | 0.008 | 0 | 10 | - | 0.000 | 0.827 | 0.827 | 0.827 |
| s13 | 0.000 | 0.062 | 0 | 48 | - | 0.000 | 0.678 | 0.678 | 0.678 |

| | all songs | without the references | without humans under 0.6 |
|---|---|---|---|
| T0 | 0.770 n=23 | 0.752 n=17 | 0.770 n=23 |
| T1 | 0.777 (+0.007 [+0.002, +0.014]) n=23 | 0.759 (+0.007 [+0.001, +0.015]) n=17 | 0.777 (+0.007 [+0.002, +0.014]) n=23 |
| T2 | 0.777 (+0.007 [+0.002, +0.013]) n=23 | 0.759 (+0.007 [+0.001, +0.014]) n=17 | 0.777 (+0.007 [+0.002, +0.013]) n=23 |
| tap_precision | 0.061 n=8 | 0.076 n=5 | 0.061 n=8 |
| tap_recall | 0.157 n=13 | 0.104 n=12 | 0.157 n=13 |
| tap_share_ours | 0.041 n=23 | 0.019 n=17 | 0.041 n=23 |
| tap_share_human | 0.031 n=23 | 0.036 n=17 | 0.031 n=23 |

### A-c. Sustains (Expert)

The slow songs (our grid under 100 BPM, report.json grid.bpm_median): creep (92.3), lucretia (98.2), sooth (77.0), s02 (73.1), s04 (73.0), s13 (87.2).


**guitar**: sustain share (ours per arm / the humans), per-note sustain agreement at 100 ms (per arm, the humans' own), the share of the humans' sustains each arm's floor would drop

| song | BPM | share base / A1 / A2 / A3 / humans | agreement base / A1 / A2 / A3 / humans | dropped base / A1 / A2 / A3 |
|---|---|---|---|---|
| all_the_small_things | 148 | 0.018 / 0.018 / 0.018 / 0.018 / 0.006 | 0.987 / 0.987 / 0.987 / 0.987 / - | 0.000 / 0.000 / 0.000 / 0.000 |
| creep (slow) | 92 | 0.141 / 0.142 / 0.141 / 0.141 / 0.092 | 0.957 / 0.959 / 0.957 / 0.957 / - | 0.062 / 0.037 / 0.037 / 0.062 |
| drunk_drivers | 117 | 0.229 / 0.229 / 0.229 / 0.229 / 0.131 | 0.831 / 0.831 / 0.831 / 0.831 / - | 0.231 / 0.013 / 0.231 / 0.231 |
| kimochi_warui | 107 | 0.006 / 0.006 / 0.006 / 0.006 / 0.029 | 0.974 / 0.974 / 0.974 / 0.974 / - | 0.000 / 0.000 / 0.000 / 0.000 |
| lucretia (slow) | 98 | 0.013 / 0.016 / 0.013 / 0.013 / 0.055 | 0.955 / 0.958 / 0.955 / 0.955 / - | 0.816 / 0.487 / 0.658 / 0.816 |
| take_me_out | 105 | 0.075 / 0.075 / 0.075 / 0.075 / 0.069 | 0.995 / 0.995 / 0.995 / 0.995 / - | 0.226 / 0.000 / 0.016 / 0.226 |
| break | 115 | 0.083 / 0.083 / 0.083 / 0.083 / 0.225 | 0.857 / 0.857 / 0.857 / 0.857 / 0.926 | 0.500 / 0.195 / 0.500 / 0.500 |
| pm2 | 200 | 0.036 / 0.036 / 0.036 / 0.036 / 0.034 | 0.964 / 0.964 / 0.964 / 0.964 / 0.974 | 0.224 / 0.224 / 0.224 / 0.224 |
| sooth (slow) | 77 | 0.052 / 0.076 / 0.058 / 0.052 / 0.105 | 0.923 / 0.923 / 0.925 / 0.924 / 0.933 | 0.519 / 0.144 / 0.313 / 0.396 |
| troop | 200 | 0.039 / 0.039 / 0.039 / 0.039 / 0.051 | 0.957 / 0.957 / 0.957 / 0.957 / 0.978 | 0.224 / 0.224 / 0.224 / 0.224 |
| s01 | 194 | 0.069 / 0.069 / 0.069 / 0.069 / 0.099 | 0.887 / 0.887 / 0.887 / 0.887 / 0.902 | 0.151 / 0.151 / 0.151 / 0.151 |
| s02 (slow) | 73 | 0.043 / 0.047 / 0.043 / 0.043 / 0.195 | 0.855 / 0.855 / 0.855 / 0.855 / 0.918 | 0.234 / 0.000 / 0.009 / 0.085 |
| s03 | 148 | 0.140 / 0.140 / 0.140 / 0.140 / 0.021 | 0.838 / 0.838 / 0.838 / 0.838 / 0.967 | 0.276 / 0.026 / 0.276 / 0.276 |
| s04 (slow) | 73 | 0.121 / 0.158 / 0.150 / 0.131 / 0.302 | 0.683 / 0.673 / 0.673 / 0.682 / 0.614 | 0.546 / 0.079 / 0.417 / 0.427 |
| s05 | 158 | 0.006 / 0.006 / 0.006 / 0.006 / 0.067 | 0.932 / 0.932 / 0.932 / 0.932 / 0.987 | 0.236 / 0.236 / 0.236 / 0.236 |
| s06 | 146 | 0.122 / 0.122 / 0.122 / 0.122 / 0.169 | 0.791 / 0.791 / 0.791 / 0.791 / 0.834 | 0.257 / 0.192 / 0.255 / 0.257 |
| s07 | 159 | 0.054 / 0.054 / 0.054 / 0.054 / 0.058 | 0.962 / 0.962 / 0.962 / 0.962 / 0.972 | 0.110 / 0.065 / 0.110 / 0.110 |
| s08 | 111 | 0.072 / 0.073 / 0.072 / 0.072 / 0.137 | 0.855 / 0.855 / 0.855 / 0.855 / 0.881 | 0.286 / 0.195 / 0.245 / 0.286 |
| s09 | 101 | 0.081 / 0.098 / 0.081 / 0.081 / 0.116 | 0.904 / 0.907 / 0.904 / 0.904 / 0.942 | 0.489 / 0.195 / 0.429 / 0.489 |
| s10 | 190 | 0.000 / 0.000 / 0.000 / 0.000 / 0.022 | 0.978 / 0.978 / 0.978 / 0.978 / 0.966 | 0.149 / 0.149 / 0.149 / 0.149 |
| s11 | 107 | 0.033 / 0.033 / 0.033 / 0.033 / 0.037 | 0.967 / 0.967 / 0.967 / 0.967 / 0.989 | 0.101 / 0.097 / 0.101 / 0.101 |
| s12 | 125 | 0.131 / 0.131 / 0.131 / 0.131 / 0.144 | 0.904 / 0.904 / 0.904 / 0.904 / 0.929 | 0.181 / 0.062 / 0.181 / 0.181 |
| s13 (slow) | 87 | 0.087 / 0.150 / 0.087 / 0.087 / 0.274 | 0.757 / 0.768 / 0.757 / 0.757 / 0.637 | 0.598 / 0.031 / 0.538 / 0.575 |

| | all songs | without the references | without humans under 0.6 |
|---|---|---|---|
| agreement base | 0.901 n=23 | 0.883 n=17 | 0.901 n=23 |
| agreement base, the slow songs | 0.855 n=6 | 0.804 n=4 | 0.855 n=6 |
| agreement A1 | 0.901 (+0.000 [-0.001, +0.002]) n=23 | 0.883 (+0.000 [-0.002, +0.002]) n=17 | 0.901 (+0.000 [-0.001, +0.002]) n=23 |
| agreement A1, the slow songs | 0.856 (+0.001 [-0.004, +0.006]) n=6 | 0.805 (+0.000 [-0.007, +0.008]) n=4 | 0.856 (+0.001 [-0.004, +0.006]) n=6 |
| agreement A2 | 0.900 (-0.000 [-0.001, +0.000]) n=23 | 0.883 (-0.000 [-0.002, +0.000]) n=17 | 0.900 (-0.000 [-0.001, +0.000]) n=23 |
| agreement A2, the slow songs | 0.854 (-0.001 [-0.005, +0.001]) n=6 | 0.803 (-0.002 [-0.007, +0.002]) n=4 | 0.854 (-0.001 [-0.005, +0.001]) n=6 |
| agreement A3 | 0.901 (+0.000 [-0.000, +0.000]) n=23 | 0.883 (+0.000 [-0.000, +0.000]) n=17 | 0.901 (+0.000 [-0.000, +0.000]) n=23 |
| agreement A3, the slow songs | 0.855 (+0.000 [-0.001, +0.001]) n=6 | 0.804 (+0.000 [-0.001, +0.001]) n=4 | 0.855 (+0.000 [-0.001, +0.001]) n=6 |
| sustain share base | 0.072 n=23 | 0.069 n=17 | 0.072 n=23 |
| sustain share A1 | 0.078 n=23 | 0.077 n=17 | 0.078 n=23 |
| sustain share A2 | 0.073 n=23 | 0.071 n=17 | 0.073 n=23 |
| sustain share A3 | 0.072 n=23 | 0.069 n=17 | 0.072 n=23 |
| humans' sustains the floor drops, base | 0.279 n=23 | 0.299 n=17 | 0.279 n=23 |
| humans' sustains the floor drops, base, the slow songs | 0.463 n=6 | 0.474 n=4 | 0.463 n=6 |
| humans' sustains the floor drops, A1 | 0.122 n=23 | 0.133 n=17 | 0.122 n=23 |
| humans' sustains the floor drops, A1, the slow songs | 0.130 n=6 | 0.064 n=4 | 0.130 n=6 |
| humans' sustains the floor drops, A2 | 0.230 n=23 | 0.256 n=17 | 0.230 n=23 |
| humans' sustains the floor drops, A2, the slow songs | 0.329 n=6 | 0.319 n=4 | 0.329 n=6 |
| humans' sustains the floor drops, A3 | 0.261 n=23 | 0.274 n=17 | 0.261 n=23 |
| humans' sustains the floor drops, A3, the slow songs | 0.393 n=6 | 0.371 n=4 | 0.393 n=6 |
| sustain share, humans | 0.106 n=23 | 0.121 n=17 | 0.106 n=23 |

Songs whose humans agree under 0.6 on guitar sustains: none.

The humans' guitar sustain lengths (per song, mean over its charts of each chart's median and p10; split at 100 BPM of the human map):

| song | n under 100 | ms p50 / p10 | beats p50 / p10 | n 100 and over | ms p50 / p10 | beats p50 / p10 |
|---|---|---|---|---|---|---|
| all_the_small_things | 0 | - | - | 4 | 6396 / 5994 | 15.75 / 14.53 |
| creep | 81 | 566 / 542 | 0.88 / 0.88 | 0 | - | - |
| drunk_drivers | 0 | - | - | 78 | 388 / 381 | 0.75 / 0.75 |
| kimochi_warui | 0 | - | - | 22 | 1122 / 981 | 2.00 / 1.75 |
| lucretia | 60 | 326 / 230 | 0.50 / 0.38 | 16 | 335 / 224 | 0.56 / 0.38 |
| take_me_out | 0 | - | - | 62 | 497 / 417 | 0.88 / 0.75 |
| break | 0 | - | - | 199 | 422 / 260 | 0.81 / 0.50 |
| pm2 | 0 | - | - | 645 | 353 / 253 | 1.15 / 0.85 |
| sooth | 489 | 544 / 322 | 0.69 / 0.43 | 0 | - | - |
| troop | 0 | - | - | 398 | 353 / 199 | 1.18 / 0.66 |
| s01 | 221 | 703 / 481 | 0.91 / 0.66 | 402 | 366 / 278 | 1.22 / 0.94 |
| s02 | 157 | 784 / 511 | 0.91 / 0.57 | 35 | 594 / 400 | 1.49 / 0.99 |
| s03 | 0 | - | - | 43 | 760 / 363 | 1.87 / 0.87 |
| s04 | 1040 | 599 / 370 | 0.76 / 0.48 | 0 | - | - |
| s05 | 0 | - | - | 431 | 306 / 304 | 0.81 / 0.80 |
| s06 | 518 | 775 / 433 | 0.76 / 0.43 | 1242 | 368 / 250 | 0.89 / 0.63 |
| s07 | 1 | 349 / 349 | 0.50 / 0.50 | 438 | 432 / 302 | 1.15 / 0.74 |
| s08 | 369 | 739 / 419 | 1.21 / 0.69 | 1408 | 423 / 360 | 0.87 / 0.70 |
| s09 | 355 | 517 / 314 | 0.85 / 0.51 | 554 | 425 / 240 | 0.82 / 0.48 |
| s10 | 2 | 13245 / 13245 | 17.50 / 17.50 | 135 | 601 / 473 | 1.75 / 1.40 |
| s11 | 18 | 631 / 492 | 0.69 / 0.56 | 206 | 592 / 367 | 1.69 / 1.05 |
| s12 | 4 | 3285 / 3017 | 5.62 / 5.12 | 317 | 583 / 337 | 1.21 / 0.71 |
| s13 | 85 | 438 / 343 | 0.62 / 0.50 | 334 | 349 / 337 | 1.00 / 0.99 |

**bass**: sustain share (ours per arm / the humans), per-note sustain agreement at 100 ms (per arm, the humans' own), the share of the humans' sustains each arm's floor would drop

| song | BPM | share base / A1 / A2 / A3 / humans | agreement base / A1 / A2 / A3 / humans | dropped base / A1 / A2 / A3 |
|---|---|---|---|---|
| all_the_small_things | 148 | 0.014 / 0.014 / 0.014 / 0.014 / 0.015 | 0.975 / 0.975 / 0.975 / 0.975 / - | 0.000 / 0.000 / 0.000 / 0.000 |
| creep (slow) | 92 | 0.106 / 0.152 / 0.106 / 0.106 / 0.428 | 0.714 / 0.739 / 0.714 / 0.714 / - | 0.299 / 0.000 / 0.000 / 0.299 |
| kimochi_warui | 107 | 0.495 / 0.495 / 0.495 / 0.495 / 0.371 | 0.764 / 0.764 / 0.764 / 0.764 / - | 0.125 / 0.000 / 0.000 / 0.125 |
| lucretia (slow) | 98 | 0.009 / 0.031 / 0.009 / 0.009 / 0.070 | 0.934 / 0.943 / 0.934 / 0.934 / - | 0.976 / 0.549 / 0.793 / 0.976 |
| take_me_out | 105 | 0.273 / 0.273 / 0.273 / 0.273 / 0.099 | 0.656 / 0.656 / 0.656 / 0.656 / - | 0.909 / 0.712 / 0.727 / 0.909 |
| pm2 | 200 | 0.056 / 0.056 / 0.056 / 0.056 / 0.029 | 0.928 / 0.928 / 0.928 / 0.928 / 0.950 | 0.221 / 0.221 / 0.221 / 0.221 |
| sooth (slow) | 77 | 0.068 / 0.102 / 0.072 / 0.068 / 0.146 | 0.917 / 0.912 / 0.921 / 0.918 / - | 0.680 / 0.013 / 0.325 / 0.548 |
| troop | 200 | 0.028 / 0.028 / 0.028 / 0.028 / 0.031 | 0.928 / 0.928 / 0.928 / 0.928 / - | 0.246 / 0.246 / 0.246 / 0.246 |
| s01 | 194 | 0.029 / 0.029 / 0.029 / 0.029 / 0.047 | 0.946 / 0.946 / 0.946 / 0.946 / 0.949 | 0.241 / 0.241 / 0.241 / 0.241 |
| s02 (slow) | 73 | 0.132 / 0.195 / 0.181 / 0.159 / 0.283 | 0.853 / 0.907 / 0.907 / 0.883 / 0.960 | 0.273 / 0.000 / 0.038 / 0.144 |
| s03 | 148 | 0.075 / 0.075 / 0.075 / 0.075 / 0.069 | 0.908 / 0.908 / 0.908 / 0.908 / 0.890 | 0.167 / 0.000 / 0.167 / 0.167 |
| s04 (slow) | 73 | 0.150 / 0.194 / 0.161 / 0.154 / 0.319 | 0.921 / 0.864 / 0.925 / 0.921 / - | 0.056 / 0.000 / 0.000 / 0.000 |
| s05 | 158 | 0.140 / 0.140 / 0.140 / 0.140 / 0.044 | 0.837 / 0.837 / 0.837 / 0.837 / 0.946 | 0.168 / 0.168 / 0.168 / 0.168 |
| s06 | 146 | 0.138 / 0.138 / 0.138 / 0.138 / 0.150 | 0.853 / 0.853 / 0.853 / 0.853 / 0.879 | 0.130 / 0.051 / 0.130 / 0.130 |
| s07 | 159 | 0.026 / 0.026 / 0.026 / 0.026 / 0.020 | 0.979 / 0.979 / 0.979 / 0.979 / 0.998 | 0.083 / 0.083 / 0.083 / 0.083 |
| s08 | 111 | 0.029 / 0.029 / 0.029 / 0.029 / 0.061 | 0.942 / 0.942 / 0.942 / 0.942 / 0.922 | 0.152 / 0.005 / 0.087 / 0.152 |
| s09 | 101 | 0.056 / 0.066 / 0.056 / 0.056 / 0.132 | 0.894 / 0.902 / 0.894 / 0.894 / - | 0.415 / 0.226 / 0.408 / 0.415 |
| s10 | 190 | 0.016 / 0.016 / 0.016 / 0.016 / 0.060 | 0.940 / 0.940 / 0.940 / 0.940 / 0.909 | 0.088 / 0.088 / 0.088 / 0.088 |
| s11 | 107 | 0.088 / 0.088 / 0.088 / 0.088 / 0.071 | 0.905 / 0.905 / 0.905 / 0.905 / 1.000 | 0.034 / 0.029 / 0.034 / 0.034 |
| s12 | 125 | 0.193 / 0.193 / 0.193 / 0.193 / 0.291 | 0.834 / 0.834 / 0.834 / 0.834 / - | 0.009 / 0.009 / 0.009 / 0.009 |
| s13 (slow) | 87 | 0.035 / 0.097 / 0.035 / 0.035 / 0.309 | 0.731 / 0.799 / 0.731 / 0.731 / 0.801 | 0.625 / 0.009 / 0.536 / 0.556 |

| | all songs | without the references | without humans under 0.6 |
|---|---|---|---|
| agreement base | 0.874 n=21 | 0.895 n=16 | 0.874 n=21 |
| agreement base, the slow songs | 0.845 n=6 | 0.856 n=4 | 0.845 n=6 |
| agreement A1 | 0.879 (+0.005 [-0.005, +0.015]) n=21 | 0.899 (+0.004 [-0.008, +0.017]) n=16 | 0.879 (+0.005 [-0.005, +0.015]) n=21 |
| agreement A1, the slow songs | 0.860 (+0.015 [-0.019, +0.046]) n=6 | 0.870 (+0.015 [-0.032, +0.061]) n=4 | 0.860 (+0.015 [-0.019, +0.046]) n=6 |
| agreement A2 | 0.877 (+0.003 [+0.000, +0.008]) n=21 | 0.899 (+0.004 [+0.000, +0.011]) n=16 | 0.877 (+0.003 [+0.000, +0.008]) n=21 |
| agreement A2, the slow songs | 0.855 (+0.010 [+0.001, +0.028]) n=6 | 0.871 (+0.015 [+0.001, +0.041]) n=4 | 0.855 (+0.010 [+0.001, +0.028]) n=6 |
| agreement A3 | 0.876 (+0.002 [+0.000, +0.004]) n=21 | 0.897 (+0.002 [+0.000, +0.006]) n=16 | 0.876 (+0.002 [+0.000, +0.004]) n=21 |
| agreement A3, the slow songs | 0.850 (+0.005 [+0.000, +0.015]) n=6 | 0.863 (+0.008 [+0.000, +0.022]) n=4 | 0.850 (+0.005 [+0.000, +0.015]) n=6 |
| sustain share base | 0.103 n=21 | 0.079 n=16 | 0.103 n=21 |
| sustain share A1 | 0.116 n=21 | 0.092 n=16 | 0.116 n=21 |
| sustain share A2 | 0.106 n=21 | 0.083 n=16 | 0.106 n=21 |
| sustain share A3 | 0.104 n=21 | 0.081 n=16 | 0.104 n=21 |
| humans' sustains the floor drops, base | 0.281 n=21 | 0.224 n=16 | 0.281 n=21 |
| humans' sustains the floor drops, base, the slow songs | 0.485 n=6 | 0.408 n=4 | 0.485 n=6 |
| humans' sustains the floor drops, A1 | 0.126 n=21 | 0.087 n=16 | 0.126 n=21 |
| humans' sustains the floor drops, A1, the slow songs | 0.095 n=6 | 0.006 n=4 | 0.095 n=6 |
| humans' sustains the floor drops, A2 | 0.205 n=21 | 0.174 n=16 | 0.205 n=21 |
| humans' sustains the floor drops, A2, the slow songs | 0.282 n=6 | 0.225 n=4 | 0.282 n=6 |
| humans' sustains the floor drops, A3 | 0.262 n=21 | 0.200 n=16 | 0.262 n=21 |
| humans' sustains the floor drops, A3, the slow songs | 0.421 n=6 | 0.312 n=4 | 0.421 n=6 |
| sustain share, humans | 0.145 n=21 | 0.129 n=16 | 0.145 n=21 |

Songs whose humans agree under 0.6 on bass sustains: none.

The humans' bass sustain lengths (per song, mean over its charts of each chart's median and p10; split at 100 BPM of the human map):

| song | n under 100 | ms p50 / p10 | beats p50 / p10 | n 100 and over | ms p50 / p10 | beats p50 / p10 |
|---|---|---|---|---|---|---|
| all_the_small_things | 0 | - | - | 10 | 1543 / 1506 | 3.75 / 3.75 |
| creep | 163 | 506 / 478 | 0.75 / 0.75 | 1 | 449 / 449 | 0.75 / 0.75 |
| kimochi_warui | 0 | - | - | 56 | 911 / 421 | 1.62 / 0.75 |
| lucretia | 70 | 250 / 228 | 0.38 / 0.38 | 12 | 371 / 239 | 0.62 / 0.40 |
| take_me_out | 0 | - | - | 66 | 288 / 284 | 0.50 / 0.50 |
| pm2 | 0 | - | - | 175 | 459 / 417 | 1.37 / 1.23 |
| sooth | 228 | 402 / 364 | 0.50 / 0.48 | 0 | - | - |
| troop | 0 | - | - | 57 | 525 / 225 | 1.75 / 0.75 |
| s01 | 45 | 738 / 618 | 0.94 / 0.87 | 67 | 863 / 509 | 2.75 / 1.65 |
| s02 | 195 | 973 / 508 | 1.12 / 0.61 | 22 | 421 / 401 | 0.99 / 0.99 |
| s03 | 0 | - | - | 114 | 819 / 351 | 2.00 / 0.87 |
| s04 | 107 | 1027 / 724 | 1.25 / 0.90 | 0 | - | - |
| s05 | 0 | - | - | 218 | 4576 / 4574 | 11.10 / 11.10 |
| s06 | 670 | 636 / 453 | 0.73 / 0.54 | 748 | 382 / 308 | 0.89 / 0.79 |
| s07 | 0 | - | - | 64 | 513 / 323 | 1.37 / 0.87 |
| s08 | 22 | 829 / 679 | 1.37 / 1.12 | 196 | 638 / 454 | 1.37 / 0.87 |
| s09 | 50 | 687 / 236 | 1.14 / 0.39 | 114 | 529 / 229 | 0.89 / 0.39 |
| s10 | 2 | 5719 / 1518 | 7.37 / 2.07 | 92 | 302 / 258 | 0.87 / 0.86 |
| s11 | 0 | - | - | 206 | 528 / 466 | 0.94 / 0.83 |
| s12 | 1 | 11078 / 11078 | 18.75 / 18.75 | 222 | 373 / 363 | 0.77 / 0.77 |
| s13 | 102 | 347 / 342 | 0.50 / 0.50 | 219 | 504 / 340 | 1.49 / 0.99 |

### A-d. The guitar's same-fret repeats (Expert guitar, base charts)

| song | repeat share ours | humans (mean; min-max) | repeats | matched@50 repeats / other | unmatched | in a human sustain | unmatched gap ms p25 / p50 / p75 |
|---|---|---|---|---|---|---|---|
| all_the_small_things | 0.132 | 0.088 (0.088-0.088) | 95 | 0.621 / 0.994 | 36 | 0 | 100 / 101 / 102 |
| creep | 0.284 | 0.562 (0.562-0.562) | 196 | 0.796 / 0.915 | 40 | 3 | 160 / 163 / 163 |
| drunk_drivers | 0.179 | 0.143 (0.143-0.143) | 107 | 0.682 / 0.804 | 34 | 8 | 128 / 128 / 129 |
| kimochi_warui | 0.326 | 0.025 (0.025-0.025) | 327 | 0.801 / 0.694 | 65 | 60 | 280 / 280 / 280 |
| lucretia | 0.160 | 0.099 (0.099-0.099) | 205 | 0.863 / 0.880 | 28 | 18 | 150 / 151 / 153 |
| take_me_out | 0.161 | 0.306 (0.306-0.306) | 140 | 0.857 / 0.937 | 20 | 0 | 249 / 286 / 287 |
| break | 0.025 | 0.021 (0.020-0.023) | 12 | 0.917 / 0.817 | 1 | 1 | 260 / 260 / 260 |
| pm2 | 0.251 | 0.277 (0.263-0.296) | 737 | 0.984 / 0.978 | 12 | 6 | 75 / 150 / 150 |
| sooth | 0.127 | 0.190 (0.179-0.202) | 277 | 0.881 / 0.817 | 33 | 31 | 100 / 200 / 469 |
| troop | 0.451 | 0.300 (0.294-0.304) | 980 | 0.908 / 0.948 | 90 | 51 | 75 / 75 / 94 |
| s01 | 0.267 | 0.277 (0.270-0.281) | 422 | 0.884 / 0.943 | 49 | 39 | 77 / 77 / 77 |
| s02 | 0.165 | 0.054 (0.031-0.077) | 130 | 0.392 / 0.832 | 79 | 73 | 143 / 145 / 210 |
| s03 | 0.045 | 0.042 (0.038-0.047) | 34 | 1.000 / 1.000 | 0 | 0 | - |
| s04 | 0.096 | 0.077 (0.074-0.081) | 72 | 0.736 / 0.873 | 19 | 16 | 207 / 241 / 327 |
| s05 | 0.069 | 0.052 (0.016-0.087) | 74 | 1.000 / 0.991 | 0 | 0 | - |
| s06 | 0.188 | 0.098 (0.075-0.112) | 409 | 0.866 / 0.902 | 55 | 53 | 231 / 255 / 257 |
| s07 | 0.149 | 0.137 (0.130-0.152) | 245 | 0.996 / 0.982 | 1 | 1 | 94 / 94 / 94 |
| s08 | 0.295 | 0.325 (0.317-0.335) | 473 | 0.989 / 0.986 | 5 | 4 | 266 / 280 / 284 |
| s09 | 0.131 | 0.059 (0.041-0.070) | 200 | 0.915 / 0.938 | 17 | 17 | 148 / 150 / 150 |
| s10 | 0.416 | 0.415 (0.245-0.479) | 472 | 0.996 / 0.994 | 2 | 0 | 88 / 95 / 102 |
| s11 | 0.141 | 0.187 (0.167-0.202) | 213 | 0.911 / 0.883 | 19 | 8 | 141 / 281 / 556 |
| s12 | 0.116 | 0.077 (0.075-0.080) | 136 | 0.654 / 0.807 | 47 | 38 | 239 / 242 / 484 |
| s13 | 0.114 | 0.100 (0.091-0.109) | 84 | 0.774 / 0.778 | 19 | 15 | 171 / 172 / 257 |

The candidate rules (removed: summed; precision: pooled over the removed notes, a note with no human chart's note within 50 ms; F1@50 change: song mean over charts, pooled with the bootstrap CI; repeat share after vs the humans'):

| rule | removed | songs touched | precision | F1@50 change (CI) | repeat share after / before / humans |
|---|---|---|---|---|---|
| gap150 | 2871 | 23 | 0.130 | -0.040 [-0.057, -0.026] | 0.090 / 0.186 / 0.170 |
| gap150_stem_p25 | 550 | 23 | 0.191 | -0.006 [-0.011, -0.003] | 0.169 / 0.186 / 0.170 |
| gap150_stem_p50 | 1248 | 23 | 0.179 | -0.016 [-0.026, -0.008] | 0.145 / 0.186 / 0.170 |
| gap200 | 1445 | 22 | 0.184 | -0.020 [-0.037, -0.009] | 0.135 / 0.186 / 0.170 |
| gap200_stem_p25 | 300 | 21 | 0.263 | -0.003 [-0.007, -0.000] | 0.177 / 0.186 / 0.170 |
| gap200_stem_p50 | 630 | 22 | 0.224 | -0.008 [-0.015, -0.002] | 0.165 / 0.186 / 0.170 |
| gap250 | 1112 | 20 | 0.179 | -0.017 [-0.034, -0.005] | 0.149 / 0.186 / 0.170 |
| gap250_stem_p25 | 233 | 18 | 0.270 | -0.002 [-0.006, -0.000] | 0.179 / 0.186 / 0.170 |
| gap250_stem_p50 | 457 | 19 | 0.217 | -0.006 [-0.013, -0.001] | 0.172 / 0.186 / 0.170 |

Per song, the removals (removed / precision / F1@50 change):

| song | gap150 | gap150_stem_p25 | gap150_stem_p50 | gap200 | gap200_stem_p25 | gap200_stem_p50 | gap250 | gap250_stem_p25 | gap250_stem_p50 |
|---|---|---|---|---|---|---|---|---|---|
| all_the_small_things | 57 / 0.00 / -0.044 | 3 / 0.00 / -0.002 | 35 / 0.00 / -0.026 | 56 / 0.00 / -0.043 | 3 / 0.00 / -0.002 | 35 / 0.00 / -0.026 | 0 / - / +0.000 | 0 / - / +0.000 | 0 / - / +0.000 |
| creep | 196 / 0.20 / -0.117 | 56 / 0.12 / -0.036 | 152 / 0.18 / -0.092 | 8 / 0.00 / -0.006 | 2 / 0.00 / -0.002 | 4 / 0.00 / -0.003 | 8 / 0.00 / -0.006 | 2 / 0.00 / -0.002 | 4 / 0.00 / -0.003 |
| drunk_drivers | 73 / 0.10 / -0.067 | 8 / 0.38 / -0.003 | 26 / 0.15 / -0.020 | 73 / 0.10 / -0.067 | 8 / 0.38 / -0.003 | 26 / 0.15 / -0.020 | 73 / 0.10 / -0.067 | 8 / 0.38 / -0.003 | 26 / 0.15 / -0.020 |
| kimochi_warui | 325 / 0.20 / -0.175 | 80 / 0.15 / -0.041 | 147 / 0.15 / -0.079 | 325 / 0.20 / -0.175 | 80 / 0.15 / -0.041 | 147 / 0.15 / -0.079 | 325 / 0.20 / -0.175 | 80 / 0.15 / -0.041 | 147 / 0.15 / -0.079 |
| lucretia | 177 / 0.12 / -0.065 | 24 / 0.21 / -0.007 | 51 / 0.29 / -0.011 | 10 / 0.20 / -0.003 | 3 / 0.00 / -0.001 | 4 / 0.25 / -0.001 | 10 / 0.20 / -0.003 | 3 / 0.00 / -0.001 | 4 / 0.25 / -0.001 |
| take_me_out | 49 / 0.31 / -0.014 | 18 / 0.83 / +0.006 | 27 / 0.56 / +0.000 | 49 / 0.31 / -0.014 | 18 / 0.83 / +0.006 | 27 / 0.56 / +0.000 | 49 / 0.31 / -0.014 | 18 / 0.83 / +0.006 | 27 / 0.56 / +0.000 |
| break | 9 / 0.11 / -0.007 | 1 / 1.00 / +0.001 | 3 / 0.33 / -0.001 | 9 / 0.11 / -0.007 | 1 / 1.00 / +0.001 | 3 / 0.33 / -0.001 | 9 / 0.11 / -0.007 | 1 / 1.00 / +0.001 | 3 / 0.33 / -0.001 |
| pm2 | 129 / 0.05 / -0.021 | 37 / 0.08 / -0.005 | 69 / 0.07 / -0.011 | 37 / 0.05 / -0.005 | 5 / 0.20 / -0.000 | 13 / 0.08 / -0.002 | 31 / 0.06 / -0.004 | 4 / 0.25 / -0.000 | 10 / 0.10 / -0.001 |
| sooth | 231 / 0.10 / -0.040 | 42 / 0.21 / -0.005 | 91 / 0.23 / -0.010 | 48 / 0.27 / -0.006 | 14 / 0.43 / -0.001 | 24 / 0.46 / -0.002 | 48 / 0.27 / -0.006 | 14 / 0.43 / -0.001 | 24 / 0.46 / -0.002 |
| troop | 82 / 0.10 / -0.015 | 2 / 0.00 / +0.000 | 9 / 0.00 / -0.002 | 19 / 0.42 / -0.001 | 0 / - / +0.000 | 2 / 0.00 / -0.001 | 17 / 0.47 / -0.000 | 0 / - / +0.000 | 2 / 0.00 / -0.001 |
| s01 | 176 / 0.06 / -0.041 | 36 / 0.11 / -0.004 | 76 / 0.09 / -0.014 | 34 / 0.18 / -0.003 | 14 / 0.14 / -0.000 | 19 / 0.21 / -0.000 | 11 / 0.27 / -0.001 | 3 / 0.67 / +0.000 | 4 / 0.50 / -0.000 |
| s02 | 67 / 0.52 / +0.001 | 1 / 0.00 / -0.000 | 28 / 0.64 / +0.005 | 47 / 0.53 / -0.000 | 1 / 0.00 / -0.000 | 19 / 0.58 / +0.003 | 11 / 0.18 / -0.004 | 1 / 0.00 / -0.000 | 6 / 0.00 / -0.001 |
| s03 | 34 / 0.00 / -0.022 | 9 / 0.00 / -0.006 | 15 / 0.00 / -0.010 | 34 / 0.00 / -0.022 | 9 / 0.00 / -0.006 | 15 / 0.00 / -0.010 | 0 / - / +0.000 | 0 / - / +0.000 | 0 / - / +0.000 |
| s04 | 63 / 0.25 / -0.008 | 29 / 0.45 / -0.002 | 43 / 0.37 / -0.004 | 58 / 0.28 / -0.007 | 28 / 0.46 / -0.002 | 40 / 0.40 / -0.003 | 18 / 0.28 / -0.003 | 7 / 0.57 / -0.001 | 12 / 0.42 / -0.001 |
| s05 | 74 / 0.00 / -0.027 | 16 / 0.00 / -0.003 | 36 / 0.00 / -0.011 | 0 / - / +0.000 | 0 / - / +0.000 | 0 / - / +0.000 | 0 / - / +0.000 | 0 / - / +0.000 | 0 / - / +0.000 |
| s06 | 350 / 0.14 / -0.042 | 67 / 0.15 / -0.006 | 155 / 0.15 / -0.016 | 232 / 0.19 / -0.023 | 45 / 0.20 / -0.004 | 99 / 0.19 / -0.010 | 169 / 0.24 / -0.014 | 35 / 0.26 / -0.003 | 67 / 0.25 / -0.006 |
| s07 | 129 / 0.00 / -0.034 | 8 / 0.00 / -0.002 | 31 / 0.00 / -0.007 | 14 / 0.00 / -0.004 | 2 / 0.00 / -0.000 | 8 / 0.00 / -0.002 | 8 / 0.00 / -0.002 | 1 / 0.00 / -0.000 | 4 / 0.00 / -0.001 |
| s08 | 166 / 0.02 / -0.043 | 29 / 0.10 / -0.006 | 64 / 0.05 / -0.015 | 97 / 0.04 / -0.021 | 12 / 0.25 / -0.001 | 26 / 0.12 / -0.004 | 97 / 0.04 / -0.021 | 12 / 0.25 / -0.001 | 26 / 0.12 / -0.004 |
| s09 | 59 / 0.03 / -0.016 | 8 / 0.00 / -0.003 | 26 / 0.04 / -0.007 | 35 / 0.03 / -0.010 | 6 / 0.00 / -0.002 | 15 / 0.00 / -0.005 | 35 / 0.03 / -0.010 | 6 / 0.00 / -0.002 | 15 / 0.00 / -0.005 |
| s10 | 115 / 0.00 / -0.038 | 6 / 0.00 / -0.002 | 16 / 0.00 / -0.004 | 18 / 0.00 / -0.004 | 1 / 0.00 / -0.001 | 1 / 0.00 / -0.001 | 17 / 0.00 / -0.004 | 0 / - / +0.000 | 0 / - / +0.000 |
| s11 | 126 / 0.09 / -0.030 | 30 / 0.17 / -0.004 | 59 / 0.14 / -0.009 | 126 / 0.09 / -0.030 | 30 / 0.17 / -0.004 | 59 / 0.14 / -0.009 | 126 / 0.09 / -0.030 | 30 / 0.17 / -0.004 | 59 / 0.14 / -0.009 |
| s12 | 100 / 0.43 / -0.010 | 17 / 0.53 / -0.001 | 41 / 0.59 / +0.000 | 100 / 0.43 / -0.010 | 17 / 0.53 / -0.001 | 41 / 0.59 / +0.000 | 34 / 0.47 / -0.003 | 7 / 0.29 / -0.002 | 14 / 0.57 / -0.000 |
| s13 | 84 / 0.23 / -0.045 | 23 / 0.26 / -0.011 | 48 / 0.23 / -0.025 | 16 / 0.31 / -0.007 | 1 / 0.00 / -0.001 | 3 / 0.33 / -0.001 | 16 / 0.31 / -0.007 | 1 / 0.00 / -0.001 | 3 / 0.33 / -0.001 |

### A-e. The second review's guitar questions (Expert guitar, base charts)

Opens: share of onsets with an open note, ours and the humans' (each chart: primary first), the longest run of consecutive opens; the open-to-green candidate as the exact-lane and contour (lane direction) agreement at 100 ms, before and after (onset F1 cannot move; states as charted).

| song | open share ours (n, longest run) | humans: share (longest run) each chart | exact lanes before / after | contour before / after |
|---|---|---|---|---|
| all_the_small_things | 0.000 (0, 0) | 0.000 (0) | 0.185 / 0.185 | 0.698 / 0.698 |
| creep | 0.000 (0, 0) | 0.000 (0) | 0.252 / 0.252 | 0.900 / 0.900 |
| drunk_drivers | 0.000 (0, 0) | 0.000 (0) | 0.117 / 0.117 | 0.576 / 0.576 |
| kimochi_warui | 0.000 (0, 0) | 0.000 (0) | 0.071 / 0.071 | 0.717 / 0.717 |
| lucretia | 0.000 (0, 0) | 0.000 (0) | 0.414 / 0.414 | 0.695 / 0.695 |
| take_me_out | 0.000 (0, 0) | 0.000 (0) | 0.150 / 0.150 | 0.667 / 0.667 |
| break | 0.000 (0, 0) | 0.104 (4), 0.100 (4) | 0.132 / 0.132 | 0.550 / 0.550 |
| pm2 | 0.000 (0, 0) | 0.000 (0), 0.033 (2), 0.002 (4), 0.001 (1), 0.000 (0) | 0.296 / 0.296 | 0.529 / 0.529 |
| sooth | 0.005 (12, 2) | 0.000 (0), 0.014 (3) | 0.249 / 0.249 | 0.674 / 0.673 |
| troop | 0.030 (65, 19) | 0.000 (0), 0.000 (0), 0.007 (3) | 0.237 / 0.249 | 0.522 / 0.522 |
| s01 | 0.000 (0, 0) | 0.000 (0), 0.000 (0), 0.370 (8), 0.398 (7) | 0.129 / 0.129 | 0.433 / 0.433 |
| s02 | 0.000 (0, 0) | 0.000 (0), 0.000 (0) | 0.245 / 0.245 | 0.589 / 0.589 |
| s03 | 0.000 (0, 0) | 0.000 (0), 0.000 (0) | 0.142 / 0.142 | 0.599 / 0.599 |
| s04 | 0.000 (0, 0) | 0.000 (0), 0.019 (3), 0.019 (3), 0.000 (0), 0.000 (0) | 0.123 / 0.123 | 0.427 / 0.427 |
| s05 | 0.000 (0, 0) | 0.078 (2), 0.118 (2), 0.000 (0), 0.000 (0), 0.078 (2), 0.000 (0) | 0.171 / 0.171 | 0.726 / 0.726 |
| s06 | 0.000 (0, 0) | 0.000 (0), 0.000 (0), 0.000 (0), 0.000 (0) | 0.199 / 0.199 | 0.502 / 0.502 |
| s07 | 0.111 (182, 8) | 0.000 (0), 0.000 (0), 0.110 (2), 0.112 (2) | 0.193 / 0.212 | 0.645 / 0.642 |
| s08 | 0.000 (0, 0) | 0.000 (0), 0.288 (44), 0.000 (0), 0.288 (44), 0.000 (0), 0.311 (44) | 0.230 / 0.230 | 0.558 / 0.558 |
| s09 | 0.001 (2, 2) | 0.000 (0), 0.041 (3), 0.006 (2), 0.068 (2) | 0.171 / 0.171 | 0.559 / 0.559 |
| s10 | 0.000 (0, 0) | 0.000 (0), 0.000 (0), 0.266 (64), 0.000 (0) | 0.337 / 0.337 | 0.655 / 0.655 |
| s11 | 0.001 (2, 1) | 0.000 (0), 0.000 (0), 0.479 (4), 0.456 (4) | 0.258 / 0.258 | 0.725 / 0.728 |
| s12 | 0.000 (0, 0) | 0.000 (0), 0.044 (4) | 0.246 / 0.246 | 0.557 / 0.557 |
| s13 | 0.001 (1, 1) | 0.000 (0), 0.000 (0) | 0.229 / 0.229 | 0.593 / 0.593 |

| | all songs | without the references | without humans under 0.6 |
|---|---|---|---|
| lane_exact_base | 0.208 n=23 | 0.211 n=17 | 0.208 n=23 |
| lane_exact_open2green | 0.209 (+0.001 [+0.000, +0.004]) n=23 | 0.213 (+0.002 [+0.000, +0.005]) n=17 | 0.209 (+0.001 [+0.000, +0.004]) n=23 |
| lane_contour_base | 0.613 n=23 | 0.579 n=17 | 0.613 n=23 |
| lane_contour_open2green | 0.613 (-0.000 [-0.001, +0.000]) n=23 | 0.579 (-0.000 [-0.001, +0.000]) n=17 | 0.613 (-0.000 [-0.001, +0.000]) n=23 |
| state_T3 | 0.778 (+0.008 [+0.000, +0.023]) n=23 | 0.752 (+0.001 [+0.000, +0.001]) n=17 | 0.778 (+0.008 [+0.000, +0.023]) n=23 |
| open share ours | 0.007 n=23 | 0.009 n=17 | 0.007 n=23 |
| open share humans | 0.040 n=23 | 0.054 n=17 | 0.040 n=23 |

The humans' own agreement on the open share: |alt - primary| mean 0.082, max 0.479 over 44 alt charts.


Taps on same-fret repeats and repeats in fast runs (runs of at least 8 onsets at most 1/8 s apart):

| song | our taps / on a repeat / share | humans' taps on a repeat: share (taps) each chart | notes in fast runs ours | repeat share in fast runs ours / humans each | song-wide ours / humans | T0 / T3 state |
|---|---|---|---|---|---|---|
| all_the_small_things | 0 / 0 / - | - (0) | 0 | - / - | 0.132 / 0.088 | 0.997 / 0.997 |
| creep | 0 / 0 / - | - (0) | 0 | - / 0.955 | 0.284 / 0.562 | 0.976 / 0.976 |
| drunk_drivers | 3 / 0 / 0.000 | - (0) | 0 | - / - | 0.179 / 0.143 | 0.966 / 0.966 |
| kimochi_warui | 613 / 327 / 0.533 | 0.190 (79) | 0 | - / - | 0.326 / 0.025 | 0.474 / 0.643 |
| lucretia | 8 / 0 / 0.000 | - (0) | 0 | - / 0.018 | 0.160 / 0.099 | 0.571 / 0.571 |
| take_me_out | 0 / 0 / - | - (0) | 0 | - / - | 0.161 / 0.306 | 0.946 / 0.946 |
| break | 0 / 0 / - | - (0), - (0) | 0 | - / -, 0.000 | 0.025 / 0.020, 0.023 | 0.923 / 0.923 |
| pm2 | 0 / 0 / - | - (0), 0.008 (793), 0.029 (561), 0.003 (1195), 0.008 (840) | 1553 | 0.272 / 0.331, 0.289, 0.319, 0.284, 0.301 | 0.251 / 0.296, 0.263, 0.286, 0.265, 0.276 | 0.687 / 0.687 |
| sooth | 312 / 15 / 0.048 | - (0), 0.363 (157) | 442 | 0.048 / 0.137, 0.210 | 0.127 / 0.179, 0.202 | 0.525 / 0.528 |
| troop | 98 / 4 / 0.041 | - (0), 0.017 (536), 0.005 (419) | 1408 | 0.534 / 0.289, 0.280, 0.317 | 0.451 / 0.294, 0.302, 0.304 | 0.668 / 0.668 |
| s01 | 0 / 0 / - | 0.000 (57), - (0), 0.000 (24), - (0) | 211 | 0.626 / 0.015, 0.000, 0.147, 0.067 | 0.267 / 0.270, 0.278, 0.281, 0.278 | 0.825 / 0.825 |
| s02 | 0 / 0 / - | - (0), - (0) | 35 | 0.000 / 0.000, 0.000 | 0.165 / 0.077, 0.031 | 0.835 / 0.835 |
| s03 | 0 / 0 / - | - (0), - (0) | 0 | - / -, - | 0.045 / 0.038, 0.047 | 0.913 / 0.913 |
| s04 | 0 / 0 / - | - (0), - (0), - (0), 0.000 (64), - (0) | 32 | 0.000 / -, -, -, -, - | 0.096 / 0.081, 0.074, 0.074, 0.075, 0.080 | 0.740 / 0.740 |
| s05 | 0 / 0 / - | 0.000 (5), 0.000 (5), - (0), - (0), 0.000 (5), 0.000 (12) | 0 | - / -, -, -, -, -, - | 0.069 / 0.016, 0.087, 0.051, 0.087, 0.016, 0.052 | 0.987 / 0.987 |
| s06 | 30 / 12 / 0.400 | - (0), 0.103 (628), - (0), 0.069 (29) | 343 | 0.009 / 0.045, 0.059, 0.039, 0.018 | 0.188 / 0.112, 0.099, 0.108, 0.075 | 0.659 / 0.660 |
| s07 | 126 / 14 / 0.111 | 0.000 (5), - (0), - (0), - (0) | 556 | 0.085 / 0.111, 0.152, 0.122, 0.140 | 0.149 / 0.134, 0.130, 0.132, 0.152 | 0.700 / 0.704 |
| s08 | 0 / 0 / - | 0.000 (248), 0.000 (165), 0.000 (106), 0.000 (183), 0.000 (165), 0.000 (175) | 0 | - / 0.169, 0.161, 0.124, 0.190, 0.138, 0.161 | 0.295 / 0.325, 0.328, 0.335, 0.317, 0.325, 0.320 | 0.785 / 0.785 |
| s09 | 74 / 9 / 0.122 | - (0), - (0), - (0), - (0) | 0 | - / 0.000, 0.062, 0.040, 0.029 | 0.131 / 0.041, 0.061, 0.062, 0.070 | 0.618 / 0.619 |
| s10 | 0 / 0 / - | - (0), 0.000 (21), 0.027 (221), - (0) | 193 | 0.834 / 0.613, 0.151, 0.396, 0.612 | 0.416 / 0.476, 0.245, 0.460, 0.479 | 0.755 / 0.755 |
| s11 | 0 / 0 / - | - (0), - (0), - (0), - (0) | 0 | - / -, -, -, - | 0.141 / 0.202, 0.202, 0.176, 0.167 | 0.656 / 0.656 |
| s12 | 0 / 0 / - | - (0), 0.000 (19) | 175 | 0.103 / 0.099, 0.077 | 0.116 / 0.080, 0.075 | 0.827 / 0.827 |
| s13 | 0 / 0 / - | 0.031 (97), - (0) | 0 | - / 0.021, 0.000 | 0.114 / 0.091, 0.109 | 0.678 / 0.678 |

| | all songs | without the references | without humans under 0.6 |
|---|---|---|---|
| repeat share in fast runs, ours | 0.251 n=10 | 0.251 n=10 | 0.251 n=10 |
| repeat share in fast runs, humans | 0.180 n=15 | 0.133 n=13 | 0.180 n=15 |

HOPO chords: the share of Expert guitar chords Clone Hero plays as HOPOs (forced; a chord is never a natural HOPO), ours per arm and each human chart's:

| song | our chords | base / A1 / A2 | humans each chart |
|---|---|---|---|
| all_the_small_things | 565 | 0.004 / 0.004 / 0.000 | 0.000 |
| creep | 168 | 0.000 / 0.000 / 0.000 | 0.000 |
| drunk_drivers | 260 | 0.004 / 0.004 / 0.000 | 0.006 |
| kimochi_warui | 389 | 0.000 / 0.000 / 0.000 | 0.055 |
| lucretia | 103 | 0.000 / 0.000 / 0.000 | 0.139 |
| take_me_out | 399 | 0.000 / 0.000 / 0.000 | 0.000 |
| break | 389 | 0.003 / 0.003 / 0.000 | 0.074, 0.078 |
| pm2 | 190 | 0.005 / 0.005 / 0.000 | 0.042, 0.000, 0.037, 0.047, 0.000 |
| sooth | 102 | 0.108 / 0.108 / 0.000 | 0.000, 0.038 |
| troop | 171 | 0.070 / 0.070 / 0.000 | 0.000, 0.000, 0.000 |
| s01 | 568 | 0.000 / 0.000 / 0.000 | 0.000, 0.014, 0.026, 0.000 |
| s02 | 205 | 0.000 / 0.000 / 0.000 | 0.000, 0.028 |
| s03 | 434 | 0.055 / 0.055 / 0.000 | 0.000, - |
| s04 | 299 | 0.007 / 0.007 / 0.000 | 0.004, 0.103, 0.103, 0.114, 0.110 |
| s05 | 674 | 0.000 / 0.000 / 0.000 | 0.000, 0.000, 0.000, 0.000, 0.000, 0.006 |
| s06 | 426 | 0.009 / 0.009 / 0.000 | 0.037, 0.000, 0.006, 0.010 |
| s07 | 421 | 0.150 / 0.150 / 0.000 | 0.263, 0.318, 0.239, 0.248 |
| s08 | 305 | 0.000 / 0.000 / 0.000 | 0.000, 0.051, 0.039, 0.036, 0.016, 0.019 |
| s09 | 557 | 0.206 / 0.206 / 0.000 | 0.000, 0.076, 0.133, 0.043 |
| s10 | 126 | 0.000 / 0.000 / 0.000 | 0.044, 0.000, 0.044, 0.000 |
| s11 | 350 | 0.040 / 0.040 / 0.000 | 0.000, 0.000, 0.071, 0.086 |
| s12 | 248 | 0.004 / 0.004 / 0.000 | 0.000, 0.051 |
| s13 | 306 | 0.013 / 0.013 / 0.000 | 0.000, 0.000 |

| | all songs | without the references | without humans under 0.6 |
|---|---|---|---|
| HOPO chord share, ours base | 0.029 n=23 | 0.039 n=17 | 0.029 n=23 |
| HOPO chord share, ours A1 | 0.029 n=23 | 0.039 n=17 | 0.029 n=23 |
| HOPO chord share, ours A2 | 0.000 n=23 | 0.000 n=17 | 0.000 n=23 |
| HOPO chord share, humans | 0.039 n=23 | 0.041 n=17 | 0.039 n=23 |

The humans' spread (max - min over a song's charts): mean 0.046, max 0.133 over 16 songs with several charts.


`df -h /` at the end: 2.1G free of 252G (95% used)

---

## Part B: M7-01 part B: silent stems, the bass, solos, drumless stretches

Measured 2026-11-07 on main 72f5679 (charting code a5895ff), read-only checkout. No build: scripts over today's charts
(the references `$SONGCHARTER_GOLDEN/v031`, the stress set `gate3-final-stress`, the 20-song set `set20-main`), their
report.json files and the kept folders (`work`, `stress-work`, `set20-work`). Songs: the 23 (six references by id,
troop, sooth, break, pm2, s01-s13). Expert only.

### How it was computed (the choices taken)

- **Charts.** Every chart is read with eval/scorer/score.py's `scan` (scan-chart 8.0.1); notes only. Timeline: input
  seconds (decode.wav = the reference's input.wav, decode.json). Ours: scan ms + our score JSON's `cand_total_shift_ms`
  (delay - lag); the primary: + its `ref_delay_ms`; each other chart: + `cand_total_shift_ms` of its `human.altN`
  score JSON (set20-main's; for the stress set gate3-new-stress's, since the gate3-final-stress run has no
  stress_scores and the humans' alignment does not depend on our run). Check: our onsets in silence at 25 dB
  reproduce report.json's `silent_onsets` count exactly on all 23 songs and parts.
- **Not the part-A base arm**: B reads today's runs above (no build), as the order's part B says. Whether the base
  arm equals them is part A's check.
- **Charts per song**: break's alt2/alt3 and s11's alt4 have no scored human JSON (no guitar/bass/drums or not
  scorable) and are left out; a part is measured against the charts that have it.
- **F1@50** as score.py (one-to-one matching, its span and margin, n_cand_eff), each chart against our chart over
  that chart's own span; a song's value = the mean over its charts. **Humans' agreement** = each other chart's
  F1@50 against the primary (mean); a song under 0.6 on the part is left out of the pooled F1 figure, named; single-
  chart songs (all references) cannot be judged and stay in; every pooled F1 is given with and without the
  references. **CI**: paired bootstrap over songs, 10,000 resamples, seed 1; written `[mean, lo, hi, n songs]`.
- **B-a**: `assemble.frame_levels` (LEVEL_FRAME_S 0.1 s) of the kept stem (guitar: `guitar`, else `other`, as
  assemble's STEMS_FOR), `silent_onsets`' test re-implemented identically for D 25/30/35. Rule (ii): the onset's
  window starts in a run of frames all under the floor lasting at least 1 s. Removal precision = removed onsets no
  human chart has within 50 ms, pooled by count. "Human notes removed" = the same rule applied to each human chart's
  notes; the per-song figure is the largest share over its charts (the bar's "every song").
  Drums' quiet windows: our sections (report.json), quiet = the drum stem's section loudness
  (`drum_section_loudness_db`) 10 dB or more under the song's median section.
- **B-b**: `engines/bass.py`'s steps in process on the kept bass stem and decode.wav (`hfc_envelope`, `pick_onsets`,
  `leakage_ok`, `pitch_track`, `note_pitches`, `map_lanes`; 448 s for 23 songs). Engine notes are mapped to our
  chart's bass onsets (nearest within 40 ms). "Held" = the previous note's pitch (|d| < 0.5 st) and the pitch
  track voiced within 0.5 st of it over every frame of onset +-50 ms. HFC rise = the scaled envelope's max over +-2
  hops at the onset, ranked within the song. Gate (a): drop held onsets unless in the top X % (X 0, 10, 25, 50).
  Map (b): after map_lanes, a note whose pitch moved 1 st or more but kept the lane moves one lane in the pitch's
  direction (kept at an edge); the change is applied to our chart's lane as a delta. Contour = score.py's
  `lane_direction_agreement` (100 ms matching), mean over charts. The repeat share = single notes whose previous onset
  is a single note on the same lane.
- **B-c**: human solos from scan's solo sections of each chart's Expert guitar (seconds; measures from that chart's
  own time signature at the solo start); share = solo seconds over first..last Expert onset (M5-03 step 1's measure;
  scan instead of `importers.read_song`). Ours: report.json `phrases.guitar`. The re-run: `starpower.place_solos`
  on our Expert guitar onsets (ticks), our tempo map and report.json's section list, with confirm as the run did
  (`config.solos` was "labels" on every song, so no stem test); at max_share 0.40 it reproduces report.json's solos
  exactly on all 23 songs. Cover = human solo time inside ours / human solo time (mean over charts with solos);
  inside = our solo time inside a chart's solos / ours (mean over all charts). Instrumental: report.json
  `stems.vocals.level_db` under -25 dB (the gap: sooth -32.8, every other song -16.0 or louder).
- **B-d**: stretches = report.json `grid.stats.secondary.stretches` with >= 16 beats and under half timed (exactly
  the warning's test). Beat F1 = score.py's (quarter-note lines of each tempo map, `beat_times`, 70 ms), per human
  chart (only charts whose span covers the stretch), meaned. Candidates: allin1's beats (kept `sections/segments.json`);
  librosa `beat_track` (start_bpm = our beats' tempo in the stretch) on the bass stem's `onset_strength`, and on the
  guitar (or other) stem's mel onset strength with fmax 350 Hz. "_oct": the candidate moved to our grid's octave in
  the stretch (midpoints added when ours is twice as fast; every other beat, the phase nearer ours, when half);
  only allin1 needed it (troop and pm2 are doubled grids).

### B-a. Notes over a silent stem

Human notes in silence (each chart; count / share of its Expert notes), per D:

| song | part | stem | humans agree F1@50 | D25 | D30 | D35 | ours silent D25 (report.json) |
|---|---|---|---|---|---|---|---|
| all_the_small_things | guitar | guitar | - | primary 0/0.000 | primary 0/0.000 | primary 0/0.000 | 0 |
| all_the_small_things | bass | bass | - | primary 0/0.000 | primary 0/0.000 | primary 0/0.000 | 0 |
| all_the_small_things | drums | drums | - | primary 0/0.000 | primary 0/0.000 | primary 0/0.000 | 0 |
| creep | guitar | guitar | - | primary 0/0.000 | primary 0/0.000 | primary 0/0.000 | 0 |
| creep | bass | bass | - | primary 0/0.000 | primary 0/0.000 | primary 0/0.000 | 0 |
| creep | drums | drums | - | primary 25/0.032 | primary 5/0.006 | primary 1/0.001 | 8 |
| drunk_drivers | guitar | guitar | - | primary 40/0.067 | primary 20/0.034 | primary 10/0.017 | 43 |
| kimochi_warui | guitar | guitar | - | primary 366/0.477 | primary 303/0.395 | primary 243/0.317 | 410 |
| kimochi_warui | bass | bass | - | primary 0/0.000 | primary 0/0.000 | primary 0/0.000 | 2 |
| kimochi_warui | drums | drums | - | primary 14/0.018 | primary 10/0.013 | primary 8/0.010 | 5 |
| lucretia | guitar | guitar | - | primary 0/0.000 | primary 0/0.000 | primary 0/0.000 | 0 |
| lucretia | bass | bass | - | primary 0/0.000 | primary 0/0.000 | primary 0/0.000 | 0 |
| lucretia | drums | drums | - | primary 0/0.000 | primary 0/0.000 | primary 0/0.000 | 0 |
| take_me_out | guitar | guitar | - | primary 0/0.000 | primary 0/0.000 | primary 0/0.000 | 0 |
| take_me_out | bass | bass | - | primary 13/0.019 | primary 12/0.018 | primary 12/0.018 | 0 |
| take_me_out | drums | drums | - | primary 3/0.003 | primary 0/0.000 | primary 0/0.000 | 3 |
| troop | guitar | guitar | 0.921 | primary 36/0.014; alt1 30/0.012; alt2 36/0.013 | primary 30/0.011; alt1 26/0.010; alt2 30/0.011 | primary 27/0.010; alt1 25/0.010; alt2 28/0.011 | 0 |
| troop | bass | bass | - | primary 191/0.103 | primary 187/0.101 | primary 160/0.086 | 0 |
| troop | drums | drums | - | primary 0/0.000 | primary 0/0.000 | primary 0/0.000 | 5 |
| sooth | guitar | guitar | 0.712 | primary 133/0.059; alt1 139/0.058 | primary 101/0.045; alt1 112/0.047 | primary 81/0.036; alt1 88/0.037 | 145 |
| sooth | bass | bass | - | primary 0/0.000 | primary 0/0.000 | primary 0/0.000 | 0 |
| break | guitar | guitar | 0.951 | primary 0/0.000; alt1 0/0.000 | primary 0/0.000; alt1 0/0.000 | primary 0/0.000; alt1 0/0.000 | 0 |
| pm2 | guitar | guitar | 0.943 | primary 18/0.005; alt1 69/0.018; alt2 17/0.005; alt3 69/0.017; alt4 95/0.025 | primary 18/0.005; alt1 67/0.017; alt2 17/0.005; alt3 67/0.017; alt4 92/0.025 | primary 14/0.004; alt1 56/0.014; alt2 14/0.004; alt3 56/0.014; alt4 81/0.022 | 76 |
| pm2 | bass | bass | 0.710 | primary 0/0.000; alt2 46/0.015 | primary 0/0.000; alt2 45/0.014 | primary 0/0.000; alt2 43/0.014 | 0 |
| pm2 | drums | drums | 0.935 | primary 74/0.022; alt4 51/0.017 | primary 58/0.017; alt4 40/0.013 | primary 4/0.001; alt4 3/0.001 | 4 |
| s01 | guitar | guitar | 0.685 | primary 0/0.000; alt1 0/0.000; alt2 4/0.002; alt3 2/0.001 | primary 0/0.000; alt1 0/0.000; alt2 3/0.002; alt3 2/0.001 | primary 0/0.000; alt1 0/0.000; alt2 3/0.002; alt3 2/0.001 | 11 |
| s01 | bass | bass | 0.980 | primary 0/0.000; alt1 0/0.000 | primary 0/0.000; alt1 0/0.000 | primary 0/0.000; alt1 0/0.000 | 0 |
| s01 | drums | drums | 0.984 | primary 0/0.000; alt1 0/0.000 | primary 0/0.000; alt1 0/0.000 | primary 0/0.000; alt1 0/0.000 | 0 |
| s02 | guitar | guitar | 0.499 | primary 22/0.071; alt1 383/0.469 | primary 20/0.065; alt1 366/0.448 | primary 14/0.045; alt1 344/0.421 | 289 |
| s02 | bass | bass | 0.982 | primary 20/0.052; alt1 19/0.050 | primary 16/0.042; alt1 17/0.044 | primary 12/0.031; alt1 14/0.037 | 2 |
| s02 | drums | drums | 0.962 | primary 33/0.058; alt1 35/0.064 | primary 16/0.028; alt1 19/0.035 | primary 4/0.007; alt1 7/0.013 | 8 |
| s03 | guitar | guitar | 0.991 | primary 0/0.000; alt1 0/0.000 | primary 0/0.000; alt1 0/0.000 | primary 0/0.000; alt1 0/0.000 | 0 |
| s03 | bass | bass | 0.977 | primary 0/0.000; alt1 0/0.000 | primary 0/0.000; alt1 0/0.000 | primary 0/0.000; alt1 0/0.000 | 0 |
| s03 | drums | drums | 0.868 | primary 0/0.000; alt1 2/0.002 | primary 0/0.000; alt1 2/0.002 | primary 0/0.000; alt1 2/0.002 | 0 |
| s04 | guitar | guitar | 0.250 | primary 0/0.000; alt1 0/0.000; alt2 0/0.000; alt3 0/0.000; alt4 0/0.000 | primary 0/0.000; alt1 0/0.000; alt2 0/0.000; alt3 0/0.000; alt4 0/0.000 | primary 0/0.000; alt1 0/0.000; alt2 0/0.000; alt3 0/0.000; alt4 0/0.000 | 0 |
| s04 | bass | bass | - | primary 0/0.000 | primary 0/0.000 | primary 0/0.000 | 0 |
| s04 | drums | drums | - | primary 75/0.110 | primary 40/0.059 | primary 18/0.026 | 8 |
| s05 | guitar | guitar | 0.739 | primary 0/0.000; alt1 79/0.069; alt2 82/0.072; alt3 81/0.073; alt4 0/0.000; alt5 81/0.076 | primary 0/0.000; alt1 68/0.059; alt2 67/0.059; alt3 67/0.060; alt4 0/0.000; alt5 70/0.066 | primary 0/0.000; alt1 59/0.051; alt2 58/0.051; alt3 58/0.052; alt4 0/0.000; alt5 60/0.056 | 82 |
| s05 | bass | bass | 0.852 | primary 0/0.000; alt1 0/0.000; alt2 0/0.000; alt3 0/0.000; alt4 0/0.000 | primary 0/0.000; alt1 0/0.000; alt2 0/0.000; alt3 0/0.000; alt4 0/0.000 | primary 0/0.000; alt1 0/0.000; alt2 0/0.000; alt3 0/0.000; alt4 0/0.000 | 0 |
| s05 | drums | drums | 0.940 | primary 32/0.018; alt1 36/0.020; alt2 32/0.017; alt3 32/0.018 | primary 5/0.003; alt1 8/0.004; alt2 5/0.003; alt3 5/0.003 | primary 0/0.000; alt1 2/0.001; alt2 0/0.000; alt3 0/0.000 | 29 |
| s06 | guitar | guitar | 0.585 | primary 0/0.000; alt1 30/0.011; alt2 22/0.009; alt3 1237/0.384 | primary 0/0.000; alt1 30/0.011; alt2 22/0.009; alt3 1236/0.383 | primary 0/0.000; alt1 29/0.011; alt2 21/0.009; alt3 1234/0.383 | 1 |
| s06 | bass | bass | 0.526 | primary 5/0.002; alt1 32/0.015; alt2 24/0.011; alt3 1106/0.378 | primary 5/0.002; alt1 31/0.014; alt2 23/0.011; alt3 1103/0.377 | primary 5/0.002; alt1 31/0.014; alt2 23/0.011; alt3 1103/0.377 | 0 |
| s06 | drums | drums | 0.655 | primary 4/0.002; alt1 6/0.002; alt2 2/0.001 | primary 1/0.000; alt1 3/0.001; alt2 2/0.001 | primary 0/0.000; alt1 2/0.001; alt2 2/0.001 | 50 |
| s07 | guitar | guitar | 0.843 | primary 0/0.000; alt1 0/0.000; alt2 2/0.001; alt3 0/0.000 | primary 0/0.000; alt1 0/0.000; alt2 2/0.001; alt3 0/0.000 | primary 0/0.000; alt1 0/0.000; alt2 2/0.001; alt3 0/0.000 | 0 |
| s07 | bass | bass | 0.978 | primary 0/0.000; alt1 0/0.000 | primary 0/0.000; alt1 0/0.000 | primary 0/0.000; alt1 0/0.000 | 0 |
| s07 | drums | drums | 0.997 | primary 0/0.000; alt1 0/0.000 | primary 0/0.000; alt1 0/0.000 | primary 0/0.000; alt1 0/0.000 | 0 |
| s08 | guitar | guitar | 0.730 | primary 0/0.000; alt1 0/0.000; alt2 0/0.000; alt3 0/0.000; alt4 28/0.013; alt5 0/0.000 | primary 0/0.000; alt1 0/0.000; alt2 0/0.000; alt3 0/0.000; alt4 27/0.013; alt5 0/0.000 | primary 0/0.000; alt1 0/0.000; alt2 0/0.000; alt3 0/0.000; alt4 27/0.013; alt5 0/0.000 | 0 |
| s08 | bass | bass | 0.505 | primary 10/0.006; alt2 11/0.006 | primary 3/0.002; alt2 4/0.002 | primary 0/0.000; alt2 1/0.001 | 0 |
| s08 | drums | drums | - | primary 23/0.012 | primary 2/0.001 | primary 0/0.000 | 23 |
| s09 | guitar | guitar | 0.797 | primary 0/0.000; alt1 0/0.000; alt2 0/0.000; alt3 0/0.000 | primary 0/0.000; alt1 0/0.000; alt2 0/0.000; alt3 0/0.000 | primary 0/0.000; alt1 0/0.000; alt2 0/0.000; alt3 0/0.000 | 0 |
| s09 | bass | bass | - | primary 5/0.004 | primary 4/0.003 | primary 3/0.002 | 0 |
| s09 | drums | drums | - | primary 0/0.000 | primary 0/0.000 | primary 0/0.000 | 0 |
| s10 | guitar | guitar | 0.687 | primary 0/0.000; alt1 3/0.002; alt2 349/0.197; alt3 0/0.000 | primary 0/0.000; alt1 3/0.002; alt2 340/0.192; alt3 0/0.000 | primary 0/0.000; alt1 3/0.002; alt2 321/0.181; alt3 0/0.000 | 0 |
| s10 | bass | bass | 0.562 | primary 4/0.005; alt1 3/0.004 | primary 2/0.003; alt1 2/0.003 | primary 0/0.000; alt1 0/0.000 | 0 |
| s10 | drums | drums | 0.863 | primary 1/0.001; alt1 0/0.000 | primary 0/0.000; alt1 0/0.000 | primary 0/0.000; alt1 0/0.000 | 0 |
| s11 | guitar | guitar | 0.696 | primary 0/0.000; alt1 0/0.000; alt2 1/0.001; alt3 0/0.000 | primary 0/0.000; alt1 0/0.000; alt2 1/0.001; alt3 0/0.000 | primary 0/0.000; alt1 0/0.000; alt2 0/0.000; alt3 0/0.000 | 1 |
| s11 | bass | bass | 1.000 | primary 135/0.093; alt1 135/0.093 | primary 113/0.078; alt1 113/0.078 | primary 99/0.069; alt1 99/0.069 | 0 |
| s11 | drums | drums | 0.980 | primary 20/0.015; alt1 20/0.015 | primary 1/0.001; alt1 1/0.001 | primary 1/0.001; alt1 1/0.001 | 20 |
| s12 | guitar | guitar | 0.383 | primary 0/0.000; alt1 0/0.000 | primary 0/0.000; alt1 0/0.000 | primary 0/0.000; alt1 0/0.000 | 0 |
| s12 | bass | bass | - | primary 280/0.366 | primary 264/0.345 | primary 248/0.324 | 1 |
| s12 | drums | drums | - | primary 77/0.056 | primary 47/0.034 | primary 27/0.020 | 6 |
| s13 | guitar | guitar | 0.887 | primary 32/0.041; alt1 0/0.000 | primary 30/0.039; alt1 0/0.000 | primary 28/0.036; alt1 0/0.000 | 15 |
| s13 | bass | bass | 0.971 | primary 18/0.034; alt1 0/0.000 | primary 17/0.032; alt1 0/0.000 | primary 14/0.027; alt1 0/0.000 | 0 |
| s13 | drums | drums | 0.990 | primary 34/0.022; alt1 32/0.021 | primary 3/0.002; alt1 3/0.002 | primary 0/0.000; alt1 0/0.000 | 31 |

**guitar**: candidates (removed onsets; removal precision = share no human chart has within 50 ms; the human notes the same rule removes, the largest share over the song's charts; F1@50 change, mean over charts)

| rule | D | songs touched | removed | precision pooled | songs with human removal >= 0.5 % | F1@50 change pooled [95 % CI] (all / no refs) | worst song F1 change |
|---|---|---|---|---|---|---|---|
| i | 25 | 10 | 783 | 0.135 | 11: drunk_drivers, kimochi_warui, troop, sooth, pm2, s02, s05, s06, s08, s10, s13 | [-0.017, -0.045, -0.001, 19] / [-0.004, -0.01, 0.0, 13] | kimochi_warui -0.2460 |
| i | 30 | 9 | 634 | 0.112 | 11: drunk_drivers, kimochi_warui, troop, sooth, pm2, s02, s05, s06, s08, s10, s13 | [-0.013, -0.036, -0.001, 19] / [-0.003, -0.008, 0.0, 13] | kimochi_warui -0.2010 |
| i | 35 | 9 | 505 | 0.101 | 11: drunk_drivers, kimochi_warui, troop, sooth, pm2, s02, s05, s06, s08, s10, s13 | [-0.01, -0.027, -0.0, 19] / [-0.003, -0.006, 0.0, 13] | kimochi_warui -0.1550 |
| ii | 25 | 10 | 746 | 0.133 | 10: drunk_drivers, kimochi_warui, sooth, pm2, s02, s05, s06, s08, s10, s13 | [-0.016, -0.042, -0.001, 19] / [-0.004, -0.01, 0.0, 13] | kimochi_warui -0.2340 |
| ii | 30 | 9 | 570 | 0.100 | 10: drunk_drivers, kimochi_warui, sooth, pm2, s02, s05, s06, s08, s10, s13 | [-0.012, -0.033, -0.001, 19] / [-0.003, -0.008, 0.0, 13] | kimochi_warui -0.1850 |
| ii | 35 | 9 | 453 | 0.091 | 10: drunk_drivers, kimochi_warui, sooth, pm2, s02, s05, s06, s08, s10, s13 | [-0.009, -0.025, -0.0, 19] / [-0.002, -0.006, 0.0, 13] | kimochi_warui -0.1430 |

Left out of the pooled F1 (humans agree under 0.6 on guitar F1@50): s02, s04, s06, s12.

**bass**: candidates (removed onsets; removal precision = share no human chart has within 50 ms; the human notes the same rule removes, the largest share over the song's charts; F1@50 change, mean over charts)

| rule | D | songs touched | removed | precision pooled | songs with human removal >= 0.5 % | F1@50 change pooled [95 % CI] (all / no refs) | worst song F1 change |
|---|---|---|---|---|---|---|---|
| i | 25 | 3 | 5 | 1.000 | 10: take_me_out, troop, pm2, s02, s06, s08, s10, s11, s12, s13 | [0.0, 0.0, 0.001, 18] / [0.0, 0.0, 0.0, 13] | all_the_small_things +0.0000 |
| i | 30 | 0 | 0 | - | 8: take_me_out, troop, pm2, s02, s06, s11, s12, s13 | [0.0, 0.0, 0.0, 18] / [0.0, 0.0, 0.0, 13] | all_the_small_things +0.0000 |
| i | 35 | 0 | 0 | - | 8: take_me_out, troop, pm2, s02, s06, s11, s12, s13 | [0.0, 0.0, 0.0, 18] / [0.0, 0.0, 0.0, 13] | all_the_small_things +0.0000 |
| ii | 25 | 2 | 2 | 1.000 | 10: take_me_out, troop, pm2, s02, s06, s08, s10, s11, s12, s13 | [0.0, 0.0, 0.0, 18] / [0.0, 0.0, 0.0, 13] | all_the_small_things +0.0000 |
| ii | 30 | 0 | 0 | - | 8: take_me_out, troop, pm2, s02, s06, s11, s12, s13 | [0.0, 0.0, 0.0, 18] / [0.0, 0.0, 0.0, 13] | all_the_small_things +0.0000 |
| ii | 35 | 0 | 0 | - | 8: take_me_out, troop, pm2, s02, s06, s11, s12, s13 | [0.0, 0.0, 0.0, 18] / [0.0, 0.0, 0.0, 13] | all_the_small_things +0.0000 |

Left out of the pooled F1 (humans agree under 0.6 on bass F1@50): s06, s08, s10.

**drums**: candidates (removed onsets; removal precision = share no human chart has within 50 ms; the human notes the same rule removes, the largest share over the song's charts; F1@50 change, mean over charts)

| rule | D | songs touched | removed | precision pooled | songs with human removal >= 0.5 % | F1@50 change pooled [95 % CI] (all / no refs) | worst song F1 change |
|---|---|---|---|---|---|---|---|
| i | 25 | 13 | 200 | 0.315 | 10: creep, kimochi_warui, pm2, s02, s04, s05, s08, s11, s12, s13 | [-0.003, -0.005, -0.001, 20] / [-0.003, -0.005, -0.001, 15] | s13 -0.0120 |
| i | 30 | 10 | 40 | 0.675 | 6: creep, kimochi_warui, pm2, s02, s04, s12 | [-0.0, -0.001, 0.0, 20] / [-0.0, -0.001, 0.001, 15] | s04 -0.0020 |
| i | 35 | 3 | 8 | 0.875 | 4: kimochi_warui, s02, s04, s12 | [0.0, 0.0, 0.0, 20] / [0.0, 0.0, 0.0, 15] | all_the_small_things +0.0000 |
| ii | 25 | 7 | 18 | 0.444 | 5: creep, kimochi_warui, pm2, s04, s12 | [-0.0, -0.001, 0.0, 20] / [-0.0, -0.0, 0.0, 15] | creep -0.0040 |
| ii | 30 | 3 | 5 | 0.600 | 4: kimochi_warui, pm2, s04, s12 | [-0.0, -0.0, 0.0, 20] / [-0.0, -0.0, 0.0, 15] | s04 -0.0020 |
| ii | 35 | 1 | 1 | 1.000 | 3: kimochi_warui, s04, s12 | [0.0, 0.0, 0.0, 20] / [0.0, 0.0, 0.0, 15] | all_the_small_things +0.0000 |

Left out of the pooled F1 (humans agree under 0.6 on drums F1@50): none.

Per song (rule i, D 25; removed / precision / largest human share removed / F1 change), where anything is removed:

| song | part | removed | precision | human removed (max share) | F1@50 change | rule ii D25 removed / precision / F1 change |
|---|---|---|---|---|---|---|
| creep | drums | 8 | 0.000 | 0.0320 | -0.0060 | 5 / 0.000 / -0.0040 |
| drunk_drivers | guitar | 43 | 0.233 | 0.0670 | -0.0280 | 39 / 0.256 / -0.0240 |
| kimochi_warui | guitar | 410 | 0.178 | 0.4770 | -0.2460 | 390 / 0.172 / -0.2340 |
| kimochi_warui | bass | 2 | 1.000 | 0.0000 | +0.0050 | 1 / 1.000 / +0.0020 |
| kimochi_warui | drums | 5 | 0.000 | 0.0180 | -0.0030 | 1 / 0.000 / -0.0010 |
| take_me_out | drums | 3 | 0.000 | 0.0030 | -0.0020 | 0 / - / +0.0000 |
| troop | drums | 5 | 1.000 | 0.0000 | +0.0010 | 3 / 1.000 / +0.0010 |
| sooth | guitar | 145 | 0.110 | 0.0590 | -0.0320 | 139 / 0.108 / -0.0310 |
| pm2 | guitar | 76 | 0.000 | 0.0250 | -0.0010 | 69 / 0.000 / -0.0010 |
| pm2 | drums | 4 | 1.000 | 0.0220 | +0.0010 | 1 / 1.000 / +0.0000 |
| s01 | guitar | 11 | 0.455 | 0.0020 | +0.0020 | 11 / 0.455 / +0.0020 |
| s02 | guitar | 289 | 0.111 | 0.4690 | -0.0600 | 284 / 0.106 / -0.0590 |
| s02 | bass | 2 | 1.000 | 0.0520 | +0.0020 | 0 / - / +0.0000 |
| s02 | drums | 8 | 0.000 | 0.0640 | -0.0080 | 0 / - / +0.0000 |
| s04 | drums | 8 | 0.500 | 0.1100 | -0.0040 | 6 / 0.667 / -0.0020 |
| s05 | guitar | 82 | 0.012 | 0.0760 | -0.0190 | 82 / 0.012 / -0.0190 |
| s05 | drums | 29 | 0.000 | 0.0200 | -0.0090 | 1 / 0.000 / -0.0000 |
| s06 | guitar | 1 | 0.000 | 0.3840 | +0.0000 | 1 / 0.000 / +0.0000 |
| s06 | drums | 50 | 0.940 | 0.0020 | +0.0060 | 0 / - / +0.0000 |
| s08 | drums | 23 | 0.043 | 0.0120 | -0.0070 | 0 / - / +0.0000 |
| s11 | guitar | 1 | 1.000 | 0.0010 | +0.0000 | 1 / 1.000 / +0.0000 |
| s11 | drums | 20 | 0.100 | 0.0150 | -0.0080 | 0 / - / +0.0000 |
| s12 | bass | 1 | 1.000 | 0.3660 | +0.0000 | 1 / 1.000 / +0.0000 |
| s12 | drums | 6 | 0.000 | 0.0560 | -0.0030 | 1 / 0.000 / -0.0000 |
| s13 | guitar | 15 | 0.000 | 0.0410 | -0.0030 | 15 / 0.000 / -0.0030 |
| s13 | drums | 31 | 0.000 | 0.0220 | -0.0120 | 0 / - / +0.0000 |

Drums in quiet sections (our sections; quiet = the drum stem's section loudness 10 dB or more under the song's median section):

| song | quiet sections | their seconds | ours onsets/s | humans onsets/s | F1@50 there | F1@50 elsewhere (section mean) |
|---|---|---|---|---|---|---|
| kimochi_warui | 1 | 34 | 0.24 | 0.24 | 0.875 | 0.974 |
| take_me_out | 2 | 24 | 1.35 | 1.43 | 0.970 | 0.942 |
| pm2 | 1 | 10 | 0.52 | 0.47 | 0.945 | 0.934 |
| s01 | 3 | 30 | 0.00 | 0.00 | - | 0.886 |
| s02 | 3 | 86 | 0.01 | 0.01 | 0.000 | 0.860 |
| s05 | 3 | 44 | 0.81 | 1.08 | 0.267 | 0.921 |
| s06 | 1 | 16 | 0.00 | 0.00 | - | 0.673 |
| s08 | 3 | 40 | 0.07 | 0.00 | 0.000 | 0.887 |
| s11 | 6 | 116 | 0.00 | 0.00 | - | 0.856 |
| s12 | 1 | 15 | 0.33 | 5.61 | 0.089 | 0.892 |

### B-b. The bass

| song | charts | humans agree F1@50 | repeat share ours / humans (mean, range) | largest lane ours / humans | humans open share | notes ratio | repeat match@50 / other | F1@50 |
|---|---|---|---|---|---|---|---|---|
| all_the_small_things | 1 | - | 0.797 / 0.490 (0.490-0.490) | 0.345 / 0.335 | 0.000 | 1.594 | 0.564 / 0.734 | 0.735 |
| creep | 1 | - | 0.594 / 0.390 (0.390-0.390) | 0.316 / 0.321 | 0.000 | 1.721 | 0.404 / 0.750 | 0.689 |
| kimochi_warui | 1 | - | 0.410 / 0.347 (0.347-0.347) | 0.310 / 0.245 | 0.000 | 1.218 | 0.467 / 0.844 | 0.758 |
| lucretia | 1 | - | 0.489 / 0.381 (0.381-0.381) | 0.320 / 0.408 | 0.000 | 0.994 | 0.894 / 0.934 | 0.912 |
| take_me_out | 1 | - | 0.658 / 0.723 (0.723-0.723) | 0.336 / 0.332 | 0.000 | 0.969 | 0.927 / 0.928 | 0.912 |
| troop | 1 | - | 0.723 / 0.750 (0.750-0.750) | 0.357 / 0.265 | 0.000 | 0.785 | 0.817 / 0.884 | 0.735 |
| sooth | 1 | - | 0.696 / 0.607 (0.607-0.607) | 0.428 / 0.450 | 0.000 | 1.274 | 0.550 / 0.826 | 0.710 |
| pm2 | 2 | 0.710 | 0.770 / 0.637 (0.423-0.852) | 0.455 / 0.323 | 0.000 | 0.786 | 0.931 / 0.948 | 0.699 |
| s01 | 2 | 0.980 | 0.493 / 0.324 (0.309-0.339) | 0.296 / 0.382 | 0.195 | 1.091 | 0.627 / 0.805 | 0.677 |
| s02 | 2 | 0.982 | 0.540 / 0.352 (0.348-0.356) | 0.289 / 0.273 | 0.059 | 1.167 | 0.614 / 0.782 | 0.714 |
| s03 | 2 | 0.977 | 0.742 / 0.809 (0.803-0.815) | 0.387 / 0.250 | 0.019 | 1.242 | 0.738 / 0.742 | 0.816 |
| s04 | 1 | - | 0.671 / 0.469 (0.469-0.469) | 0.412 / 0.295 | 0.000 | 1.780 | 0.293 / 0.616 | 0.514 |
| s05 | 5 | 0.852 | 0.809 / 0.832 (0.826-0.836) | 0.364 / 0.350 | 0.125 | 1.082 | 0.814 / 0.724 | 0.655 |
| s06 | 4 | 0.526 | 0.502 / 0.320 (0.277-0.381) | 0.315 / 0.266 | 0.035 | 1.084 | 0.848 / 0.967 | 0.532 |
| s07 | 2 | 0.978 | 0.553 / 0.400 (0.340-0.459) | 0.430 / 0.317 | 0.129 | 1.190 | 0.720 / 0.793 | 0.804 |
| s08 | 2 | 0.505 | 0.493 / 0.609 (0.604-0.613) | 0.314 / 0.570 | 0.293 | 1.105 | 0.695 / 0.853 | 0.580 |
| s09 | 1 | - | 0.416 / 0.489 (0.489-0.489) | 0.336 / 0.371 | 0.000 | 1.125 | 0.555 / 0.842 | 0.765 |
| s10 | 2 | 0.562 | 0.592 / 0.477 (0.431-0.523) | 0.377 / 0.425 | 0.204 | 1.173 | 0.829 / 0.921 | 0.656 |
| s11 | 2 | 1.000 | 0.483 / 0.179 (0.161-0.198) | 0.295 / 0.378 | 0.065 | 0.813 | 0.621 / 0.845 | 0.660 |
| s12 | 1 | - | 0.474 / 0.469 (0.469-0.469) | 0.334 / 0.281 | 0.000 | 0.861 | 0.481 / 0.623 | 0.514 |
| s13 | 2 | 0.971 | 0.388 / 0.179 (0.179-0.180) | 0.270 / 0.240 | 0.090 | 1.213 | 0.498 / 0.833 | 0.752 |

Lane spread (lanes 0-4 share of single notes), ours and the humans' mean:

| song | ours | humans |
|---|---|---|
| all_the_small_things | 0.10 0.32 0.34 0.19 0.04 | 0.17 0.34 0.11 0.33 0.05 |
| creep | 0.14 0.20 0.32 0.25 0.09 | 0.32 0.13 0.21 0.32 0.03 |
| kimochi_warui | 0.13 0.23 0.31 0.24 0.09 | 0.12 0.20 0.22 0.24 0.21 |
| lucretia | 0.21 0.32 0.24 0.17 0.06 | 0.41 0.21 0.18 0.13 0.06 |
| take_me_out | 0.21 0.15 0.34 0.20 0.10 | 0.13 0.17 0.19 0.33 0.18 |
| troop | 0.10 0.32 0.36 0.19 0.04 | 0.19 0.26 0.27 0.12 0.17 |
| sooth | 0.10 0.33 0.43 0.12 0.02 | 0.07 0.45 0.12 0.24 0.12 |
| pm2 | 0.08 0.31 0.46 0.14 0.02 | 0.17 0.30 0.23 0.26 0.04 |
| s01 | 0.30 0.23 0.29 0.12 0.07 | 0.22 0.22 0.15 0.15 0.06 |
| s02 | 0.15 0.27 0.29 0.18 0.12 | 0.27 0.19 0.19 0.16 0.12 |
| s03 | 0.14 0.39 0.23 0.20 0.04 | 0.25 0.14 0.24 0.21 0.15 |
| s04 | 0.14 0.26 0.41 0.12 0.06 | 0.29 0.17 0.19 0.13 0.22 |
| s05 | 0.08 0.32 0.36 0.19 0.04 | 0.20 0.22 0.15 0.18 0.12 |
| s06 | 0.17 0.26 0.32 0.17 0.08 | 0.19 0.26 0.25 0.17 0.10 |
| s07 | 0.15 0.43 0.27 0.12 0.03 | 0.24 0.24 0.19 0.13 0.07 |
| s08 | 0.18 0.29 0.31 0.15 0.06 | 0.32 0.13 0.10 0.12 0.04 |
| s09 | 0.16 0.28 0.34 0.16 0.06 | 0.27 0.09 0.37 0.17 0.10 |
| s10 | 0.17 0.31 0.38 0.11 0.04 | 0.25 0.08 0.16 0.16 0.15 |
| s11 | 0.24 0.29 0.24 0.13 0.09 | 0.38 0.20 0.21 0.11 0.04 |
| s12 | 0.21 0.20 0.33 0.17 0.08 | 0.17 0.18 0.28 0.21 0.16 |
| s13 | 0.21 0.23 0.27 0.20 0.09 | 0.19 0.20 0.24 0.16 0.12 |

**The cause** (the engine re-run in process; our consecutive same-lane single notes, by the engine's pitches):

| song | same-lane pairs: same pitch / changed >= 1 st / 0.5-1 st / unknown | same-pitch held through the onset | held: median HFC rank | pitch changes >= 1 st | share keeping the lane |
|---|---|---|---|---|---|
| all_the_small_things | 573 / 3 / 2 / 9 | 427 | 0.51 | 129 | 0.031 |
| creep | 101 / 5 / 6 / 6 | 68 | 0.24 | 218 | 0.069 |
| kimochi_warui | 31 / 3 / 0 / 3 | 6 | 0.41 | 103 | 0.078 |
| lucretia | 266 / 33 / 25 / 20 | 198 | 0.53 | 502 | 0.094 |
| take_me_out | 260 / 15 / 5 / 2 | 150 | 0.44 | 185 | 0.108 |
| troop | 315 / 6 / 2 / 3 | 280 | 0.40 | 262 | 0.072 |
| sooth | 319 / 13 / 17 / 0 | 303 | 0.31 | 431 | 0.102 |
| pm2 | 610 / 11 / 9 / 4 | 535 | 0.45 | 325 | 0.071 |
| s01 | 201 / 9 / 10 / 12 | 127 | 0.32 | 471 | 0.053 |
| s02 | 121 / 20 / 7 / 30 | 67 | 0.34 | 189 | 0.127 |
| s03 | 229 / 6 / 8 / 1 | 179 | 0.40 | 167 | 0.084 |
| s04 | 226 / 10 / 3 / 0 | 186 | 0.44 | 177 | 0.090 |
| s05 | 429 / 5 / 6 / 19 | 380 | 0.50 | 136 | 0.037 |
| s06 | 717 / 93 / 37 / 12 | 556 | 0.38 | 972 | 0.110 |
| s07 | 655 / 24 / 37 / 8 | 420 | 0.40 | 460 | 0.076 |
| s08 | 366 / 18 / 23 / 29 | 289 | 0.42 | 520 | 0.056 |
| s09 | 195 / 28 / 7 / 11 | 151 | 0.30 | 681 | 0.073 |
| s10 | 218 / 7 / 13 / 20 | 155 | 0.41 | 211 | 0.066 |
| s11 | 157 / 17 / 5 / 14 | 120 | 0.40 | 529 | 0.081 |
| s12 | 149 / 9 / 2 / 33 | 111 | 0.35 | 307 | 0.042 |
| s13 | 34 / 13 / 1 / 2 | 31 | 0.35 | 397 | 0.139 |
| all | 6172 / 348 / 225 / 238 | 4739 | | 7372 | 0.083 |

**(a) the gate on held notes** (X: an onset in the song's top X % of HFC rises is kept):

| X | removed | precision pooled | F1@50 change pooled [CI] (all / no refs) | songs down > 0.01 | refs down > 0.01 | repeat share after (song mean) vs ours / humans |
|---|---|---|---|---|---|---|
| 0 | 6647 | 0.392 | [-0.066, -0.112, -0.022, 18] / [-0.061, -0.117, -0.008, 13] | all_the_small_things, lucretia, take_me_out, troop, pm2, s01, s03, s05, s06, s07, s08, s09, s10, s11, s12 | all_the_small_things, lucretia, take_me_out | 0.451 vs 0.585 / 0.487 |
| 10 | 6350 | 0.407 | [-0.055, -0.098, -0.015, 18] / [-0.05, -0.101, -0.002, 13] | all_the_small_things, lucretia, take_me_out, troop, pm2, s01, s03, s05, s06, s07, s08, s10, s11, s12 | all_the_small_things, lucretia, take_me_out | 0.459 vs 0.585 / 0.487 |
| 25 | 5604 | 0.433 | [-0.039, -0.074, -0.004, 18] / [-0.036, -0.077, 0.005, 13] | all_the_small_things, lucretia, take_me_out, troop, pm2, s01, s03, s05, s06, s07, s08, s10, s11, s12 | all_the_small_things, lucretia, take_me_out | 0.476 vs 0.585 / 0.487 |
| 50 | 3943 | 0.476 | [-0.015, -0.039, 0.008, 18] / [-0.015, -0.042, 0.012, 13] | lucretia, take_me_out, troop, pm2, s05, s06, s07, s08, s10, s12 | lucretia, take_me_out | 0.512 vs 0.585 / 0.487 |

**(b) the map** (a pitch change of a semitone or more always changes the lane):

| song | lanes changed | contour before | after | repeat share after |
|---|---|---|---|---|
| all_the_small_things | 3 | 0.832 | 0.832 | 0.793 |
| creep | 8 | 0.624 | 0.624 | 0.578 |
| kimochi_warui | 4 | 0.869 | 0.878 | 0.377 |
| lucretia | 37 | 0.742 | 0.760 | 0.453 |
| take_me_out | 20 | 0.871 | 0.874 | 0.630 |
| troop | 17 | 0.820 | 0.820 | 0.711 |
| sooth | 16 | 0.744 | 0.749 | 0.682 |
| pm2 | 18 | 0.639 | 0.643 | 0.759 |
| s01 | 15 | 0.686 | 0.691 | 0.479 |
| s02 | 19 | 0.734 | 0.791 | 0.502 |
| s03 | 14 | 0.816 | 0.822 | 0.729 |
| s04 | 13 | 0.806 | 0.818 | 0.641 |
| s05 | 5 | 0.787 | 0.785 | 0.803 |
| s06 | 104 | 0.621 | 0.632 | 0.453 |
| s07 | 35 | 0.601 | 0.612 | 0.537 |
| s08 | 21 | 0.497 | 0.498 | 0.482 |
| s09 | 35 | 0.719 | 0.727 | 0.390 |
| s10 | 8 | 0.677 | 0.681 | 0.579 |
| s11 | 31 | 0.464 | 0.479 | 0.457 |
| s12 | 11 | 0.719 | 0.712 | 0.459 |
| s13 | 26 | 0.751 | 0.807 | 0.341 |

Contour change pooled [CI]: [0.011, 0.004, 0.02, 18] (all), [0.013, 0.004, 0.025, 13] (no refs); repeat share after 0.564 (ours 0.585, humans 0.487).
Left out of the pooled figures (humans agree under 0.6 on bass F1@50): s06, s08, s10.

### B-c. Solos

Instrumental: our report.json's vocals stem level under -25.0 dB: sooth (sooth -32.8 dB); every other song is at -16.0 dB or louder.
Largest human solo share: 0.551, so the M5-03 cap would be 0.60.

| song | vocals dB | human charts: solos (measures/s) and share | ours (report): count, share, trimmed/skipped by share | cover humans | ours inside |
|---|---|---|---|---|---|
| all_the_small_things | -6.6 | primary none 0.000 | 0, 0.000, 0/0 | - | - |
| creep | -6.2 | primary none 0.000 | 1, 0.066, 0/0 | - | 0.000 |
| drunk_drivers | -6.1 | primary none 0.000 | 0, 0.000, 0/0 | - | - |
| kimochi_warui | -7.4 | primary 8/17.9 0.064 | 0, 0.000, 0/0 | 0.000 | - |
| lucretia | -11.2 | primary 31.9/77 0.333 | 1, 0.396, 1/0 | 1.000 | 0.842 |
| take_me_out | -7.0 | primary none 0.000 | 1, 0.058, 0/0 | - | 0.000 |
| troop | -8.9 | primary 53/63.6 0.214; alt1 4.3/5.1,4.3/5.1,52.8/63.3 0.248; alt2 4.1/5,4.3/5.1,15.9/19.1,52.9/63.5 0.311 | 1, 0.226, 0/0 | 0.834 | 0.928 |
| sooth | -32.8 | primary none 0.000; alt1 31.8/95.9,32/96.9 0.357 | 3, 0.396, 1/0 | 0.903 | 0.408 |
| break | -7.0 | primary 13/27 0.163; alt1 12/24.9 0.150 | 1, 0.174, 0/0 | 0.792 | 0.712 |
| pm2 | -8.6 | primary 16.6/19.9,16.6/19.9,8/11.3,8/11.3,57.9/69.5 0.302; alt1 16.5/19.8,16.5/19.8,32/45.2,56/67.2 0.348; alt2 16.5/19.8,16.5/19.8,8/11.3 0.117; alt3 16.8/20.1,16.8/20.1,8/11.2,8/11.3,57.3/68.7 0.301; alt4 56.3/67.5 0.154 | 3, 0.272, 0/0 | 0.467 | 0.424 |
| s01 | -13.2 | primary none 0.000; alt1 23.9/29.2 0.095; alt2 3.1/3.5,23.8/27.2,9.2/12.4 0.157; alt3 2.9/3.6,23.6/29 0.106 | 1, 0.224, 0/0 | 0.630 | 0.212 |
| s02 | -7.0 | primary 8.2/27.4 0.119; alt1 none 0.000 | 1, 0.087, 0/0 | 0.972 | 0.500 |
| s03 | -8.6 | primary none 0.000; alt1 none 0.000 | 0, 0.000, 0/0 | - | - |
| s04 | -9.3 | primary none 0.000; alt1 7/21.4 0.081; alt2 7/21.4 0.081; alt3 7/21.5 0.082; alt4 7/21.7 0.085 | 1, 0.081, 0/0 | 0.746 | 0.562 |
| s05 | -11.4 | primary none 0.000; alt1 none 0.000; alt2 none 0.000; alt3 none 0.000; alt4 none 0.000; alt5 none 0.000 | 0, 0.000, 0/0 | - | - |
| s06 | -10.9 | primary 7.9/32.6,8/32.2,156.2/249 0.551; alt1 none 0.000; alt2 156.2/248.9 0.433; alt3 216.3/332.2 0.427 | 3, 0.324, 0/0 | 0.579 | 0.683 |
| s07 | -16.0 | primary 4.2/6.3,4/6,4.1/6.2,4.1/6.2,9/18.5,8/17,4.5/8.9,4/7.8,4/7.6,3.9/7.3,8/14.9 0.346; alt1 12.1/18.2,25.1/42.7,8/16.9,4.4/8.8,4/7.8,4/7.5,4/7.4,7.9/14.8 0.403; alt2 16.6/25,25.1/42.9,7.9/16.9,4.4/8.7,4/7.8,3.9/7.5,3.9/7.3,8/15.1 0.424; alt3 16.1/24.1,25/42.5,7.9/16.7,3.9/7.7,3.9/7.5,3.9/7.3,3.9/7.2,8/14.9 0.415 | 2, 0.394, 1/0 | 0.671 | 0.674 |
| s08 | -13.1 | primary none 0.000; alt1 6.8/16.5,6.4/15.3,12.3/21.7,33.6/36.2,17.8/19 0.257; alt2 6/14.6,6/13.5,12/20,33.8/31.3 0.203; alt3 6.9/16.6,6.2/14.8,12.2/21.5,33.8/36.4 0.211; alt4 5.9/14.4,5.7/13.4,12.2/21.4,33.5/33.8,17.5/17.3 0.244; alt5 6.8/16.4,6.4/15.2,12.3/21.6,33.9/36.5 0.212 | 3, 0.349, 0/0 | 0.604 | 0.321 |
| s09 | -8.3 | primary 8.5/20.4,46/102 0.304; alt1 8.3/20,88.6/98.4 0.294; alt2 8.4/20.1,44.1/98.7 0.295; alt3 8.3/20,97.1/115.7 0.337 | 2, 0.103, 0/0 | 0.337 | 1.000 |
| s10 | -13.7 | primary none 0.000; alt1 none 0.000; alt2 34/30.2 0.123; alt3 none 0.000 | 1, 0.232, 0/0 | 0.000 | 0.000 |
| s11 | -11.2 | primary none 0.000; alt1 none 0.000; alt2 none 0.000; alt3 none 0.000 | 2, 0.069, 0/0 | - | 0.000 |
| s12 | -9.1 | primary 33.5/64.4,20.8/41.9 0.303; alt1 33.6/64.7,20.5/40 0.305 | 2, 0.128, 0/0 | 0.127 | 0.305 |
| s13 | -10.2 | primary 13.6/31.6 0.119; alt1 10.8/26.4 0.099 | 2, 0.276, 0/0 | 0.989 | 0.390 |

Human charts over 0.40: 6 on 2 songs: s06 primary 0.551, s06 alt2 0.433, s06 alt3 0.427, s07 alt1 0.403, s07 alt2 0.424, s07 alt3 0.415.

| arm | songs that change | our share (song mean) | cover humans pooled (songs with human solos) | ours inside pooled | songs whose share leaves its humans' range or moves away |
|---|---|---|---|---|---|
| 0.40 | none | 0.168 | 0.6032 (diff [0.0, 0.0, 0.0, 16]) | 0.4423 (diff [0.0, 0.0, 0.0, 18]) | none |
| cap_0.60 | lucretia, sooth, s07 | 0.176 | 0.6052 (diff [0.002, 0.0, 0.006, 16]) | 0.4326 (diff [-0.01, -0.024, 0.0, 18]) | lucretia, sooth, s07 |
| 0.75_instr | sooth | 0.174 | 0.6032 (diff [0.0, 0.0, 0.0, 16]) | 0.4361 (diff [-0.006, -0.018, 0.0, 18]) | sooth |

Today (0.40), songs whose solo share is outside their humans' range: 13: creep, kimochi_warui, lucretia, take_me_out, sooth, break, s01, s08, s09, s10, s11, s12, s13.

### B-d. Drumless stretches

| song | octave | stretches | seconds | share | whole-song beat F1 (chart mean) | rest of song |
|---|---|---|---|---|---|---|
| all_the_small_things | 1 | 1 | 12.2 | 0.070 | 1.000 | 1.000 |
| creep | 1 | 1 | 11.7 | 0.049 | 0.985 | 1.000 |
| drunk_drivers | 1 | 1 | 11.2 | 0.050 | 1.000 | 1.000 |
| kimochi_warui | 1 | 1 | 8.4 | 0.029 | 1.000 | 0.998 |
| lucretia | 1 | 2 | 30.3 | 0.126 | 0.260 | 0.271 |
| take_me_out | 1 | 1 | 9.8 | 0.041 | 0.983 | 0.983 |
| troop | 2 | 6 | 67.5 | 0.219 | 1.000 | 1.000 |
| sooth | 0.5 | 2 | 44.6 | 0.081 | 0.985 | 0.984 |
| break | 1 | 1 | 15.6 | 0.081 | 0.997 | 0.997 |
| pm2 | 2 | 6 | 82.4 | 0.186 | 0.988 | 1.000 |
| s01 | 2 | 0 | 0 | 0.000 | 0.459 | - |
| s02 | 0.5 | 4 | 132.0 | 0.367 | 0.766 | 0.817 |
| s03 | 1 | 1 | 8.1 | 0.036 | 0.984 | 0.995 |
| s04 | 0.5 | 1 | 14.3 | 0.048 | 0.333 | 0.341 |
| s05 | 1 | 3 | 39.9 | 0.152 | 0.829 | 0.830 |
| s06 | 1 | 2 | 47.2 | 0.081 | 0.705 | 0.731 |
| s07 | 1 | 0 | 0 | 0.000 | 0.835 | - |
| s08 | 1 | 3 | 55.1 | 0.126 | 0.542 | 0.572 |
| s09 | 1 | 2 | 20.4 | 0.049 | 0.600 | 0.609 |
| s10 | 2 | 1 | 46.7 | 0.213 | 0.538 | 0.593 |
| s11 | 1 | 1 | 11.8 | 0.028 | 0.418 | 0.418 |
| s12 | 1 | 1 | 17.1 | 0.048 | 0.649 | 0.664 |
| s13 | 1 | 0 | 0 | 0.000 | 0.541 | - |

Per stretch: beat F1 against the human beat lines (mean over the charts that have beat lines there):

| song | stretch (s) | beats | timed | ours | allin1 | allin1_oct | bass_env | bass_env_oct | guitar_low | guitar_low_oct |
|---|---|---|---|---|---|---|---|---|---|---|
| all_the_small_things | 163.0-175.2 | 31 | 0.032 | no human beat lines |  |  |  |  |  |  |
| creep | 228.0-239.7 | 19 | 0.316 | 0.286 | 0.286 | 0.286 | 0.143 | 0.143 | 0.593 | 0.593 |
| drunk_drivers | 213.5-224.7 | 23 | 0.043 | 0.789 | 0.000 | 0.000 | 0.438 | 0.438 | 0.421 | 0.421 |
| kimochi_warui | 56.2-64.6 | 16 | 0.0 | 0.968 | 0.968 | 0.968 | 0.968 | 0.968 | 0.000 | 0.000 |
| lucretia | 5.0-24.3 | 32 | 0.0 | 0.164 | 0.814 | 0.814 | 0.194 | 0.194 | 0.167 | 0.167 |
| lucretia | 75.0-86.0 | 19 | 0.0 | 0.222 | 0.000 | 0.000 | 0.114 | 0.114 | 0.294 | 0.294 |
| take_me_out | 230.6-240.4 | 18 | 0.444 | no human beat lines |  |  |  |  |  |  |
| troop | 0.2-14.9 | 50 | 0.0 | 0.819 | 0.667 | 0.985 | 0.986 | 0.986 | 0.725 | 0.725 |
| troop | 26.9-42.2 | 52 | 0.0 | 1.000 | 0.675 | 1.000 | 0.731 | 0.731 | 0.590 | 0.590 |
| troop | 146.0-156.5 | 36 | 0.0 | 1.000 | 0.654 | 0.971 | 0.876 | 0.876 | 0.131 | 0.131 |
| troop | 158.9-166.1 | 25 | 0.0 | 1.000 | 0.667 | 0.979 | 1.000 | 1.000 | 0.041 | 0.041 |
| troop | 187.7-195.2 | 26 | 0.0 | 1.000 | 0.684 | 1.000 | 0.947 | 0.947 | 0.118 | 0.118 |
| troop | 295.4-307.7 | 42 | 0.0 | 0.705 | 0.619 | 0.920 | 0.547 | 0.547 | 0.771 | 0.771 |
| sooth | 174.4-196.7 | 30 | 0.0 | 0.983 | 0.763 | 0.763 | 0.121 | 0.121 | 0.069 | 0.069 |
| sooth | 371.7-394.0 | 30 | 0.0 | 0.983 | 0.915 | 0.915 | 0.310 | 0.310 | 0.152 | 0.152 |
| break | 177.2-192.8 | 31 | 0.065 | no human beat lines |  |  |  |  |  |  |
| pm2 | 5.1-22.5 | 59 | 0.0 | 0.992 | 0.667 | 0.991 | 0.376 | 0.376 | 0.079 | 0.079 |
| pm2 | 43.2-50.1 | 24 | 0.0 | 0.979 | 0.629 | 0.957 | 0.877 | 0.877 | 0.979 | 0.979 |
| pm2 | 223.5-247.4 | 76 | 0.0 | 0.769 | 0.537 | 0.771 | 0.797 | 0.797 | 0.775 | 0.775 |
| pm2 | 291.4-302.9 | 39 | 0.0 | 0.997 | 0.657 | 0.976 | 0.971 | 0.971 | 0.806 | 0.806 |
| pm2 | 370.1-388.4 | 62 | 0.0 | 0.992 | 0.674 | 1.000 | 0.836 | 0.836 | 0.904 | 0.904 |
| pm2 | 432.8-437.3 | 16 | 0.0 | 0.968 | 0.539 | 0.853 | 0.942 | 0.942 | 0.000 | 0.000 |
| s02 | 8.4-87.8 | 93 | 0.0 | 0.746 | 0.763 | 0.763 | 0.525 | 0.525 | 0.147 | 0.147 |
| s02 | 106.1-119.7 | 19 | 0.0 | 0.389 | 0.778 | 0.778 | 0.882 | 0.882 | 0.114 | 0.114 |
| s02 | 217.1-229.3 | 17 | 0.0 | 0.420 | 0.610 | 0.610 | 0.239 | 0.239 | 0.473 | 0.473 |
| s02 | 320.9-347.8 | 33 | 0.0 | 0.281 | 0.641 | 0.641 | 0.312 | 0.312 | 0.185 | 0.185 |
| s03 | 217.3-225.4 | 21 | 0.143 | 0.241 | 0.495 | 0.495 | 0.205 | 0.205 | 0.239 | 0.239 |
| s04 | 275.3-289.6 | 16 | 0.0 | 0.000 | 0.129 | 0.129 | 0.118 | 0.118 | 0.151 | 0.151 |
| s05 | 4.6-16.4 | 32 | 0.312 | 0.402 | 0.402 | 0.402 | 0.402 | 0.402 | 0.185 | 0.185 |
| s05 | 188.6-198.8 | 28 | 0.25 | 0.964 | 0.873 | 0.873 | 0.667 | 0.667 | 0.176 | 0.176 |
| s05 | 243.7-261.6 | 48 | 0.042 | no human beat lines |  |  |  |  |  |  |
| s06 | 0.2-32.1 | 63 | 0.127 | 0.142 | 0.536 | 0.536 | 0.208 | 0.208 | 0.233 | 0.233 |
| s06 | 560.4-575.8 | 35 | 0.057 | 0.324 | 0.380 | 0.380 | 0.237 | 0.237 | 0.325 | 0.325 |
| s08 | -0.0-11.1 | 31 | 0.065 | 0.059 | 0.000 | 0.000 | 0.000 | 0.000 | 0.103 | 0.103 |
| s08 | 11.8-45.1 | 70 | 0.257 | 0.205 | 0.224 | 0.224 | 0.172 | 0.172 | 0.480 | 0.480 |
| s08 | 179.2-189.9 | 21 | 0.0 | 0.231 | 0.712 | 0.712 | 0.666 | 0.666 | 0.629 | 0.629 |
| s09 | 6.7-16.4 | 17 | 0.0 | 0.347 | 0.669 | 0.669 | 0.090 | 0.090 | 0.162 | 0.162 |
| s09 | 404.3-415.1 | 19 | 0.0 | 0.144 | 0.237 | 0.237 | 0.272 | 0.272 | 0.224 | 0.224 |
| s10 | 6.1-52.8 | 131 | 0.336 | 0.278 | 0.310 | 0.284 | 0.366 | 0.366 | 0.352 | 0.352 |
| s11 | 405.8-417.6 | 22 | 0.045 | no human beat lines |  |  |  |  |  |  |
| s12 | 339.9-357.0 | 37 | 0.081 | 0.177 | 0.256 | 0.256 | 0.198 | 0.198 | 0.205 | 0.205 |

| candidate | mean over stretches (ours) | difference [CI over songs] | stretches down > 0.05 |
|---|---|---|---|
| allin1 | 0.540 (0.582) | -0.043 [-0.003, -0.148, 0.112, 16] | 18 of 36 |
| allin1_oct | 0.643 (0.582) | +0.060 [0.035, -0.102, 0.132, 16] | 7 of 36 |
| bass_env | 0.493 (0.582) | -0.090 [-0.088, -0.201, -0.001, 16] | 18 of 36 |
| bass_env_oct | 0.493 (0.582) | -0.090 [-0.088, -0.201, -0.001, 16] | 18 of 36 |
| guitar_low | 0.333 (0.582) | -0.249 [-0.187, -0.38, -0.011, 16] | 19 of 36 |
| guitar_low_oct | 0.333 (0.582) | -0.249 [-0.187, -0.38, -0.011, 16] | 19 of 36 |

### B-c2. The solo count cap (max_solos)

Songs with a human chart of more than 3 solos: troop 4, pm2 5, s07 11, s08 5.

Per song where any arm changes (count / share / cover / inside), and the human charts' counts and shares:

| song | humans: count share | n3_s0.40 | n3_s0.60 | n4_s0.40 | n4_s0.60 | n5_s0.40 | n5_s0.60 |
|---|---|---|---|---|---|---|---|
| lucretia | primary 1 0.333 | 1 / 0.396 / 1.000 / 0.842 | 1 / 0.415 / 1.000 / 0.803 | 1 / 0.396 / 1.000 / 0.842 | 1 / 0.415 / 1.000 / 0.803 | 1 / 0.396 / 1.000 / 0.842 | 1 / 0.415 / 1.000 / 0.803 |
| troop | primary 1 0.214; alt1 3 0.248; alt2 4 0.311 | 1 / 0.226 / 0.834 / 0.928 | 1 / 0.226 / 0.834 / 0.928 | 1 / 0.226 / 0.834 / 0.928 | 1 / 0.226 / 0.834 / 0.928 | 1 / 0.226 / 0.834 / 0.928 | 1 / 0.226 / 0.834 / 0.928 |
| sooth | primary 0 0.000; alt1 2 0.357 | 3 / 0.396 / 0.903 / 0.408 | 3 / 0.543 / 0.903 / 0.297 | 3 / 0.396 / 0.903 / 0.408 | 4 / 0.588 / 0.903 / 0.275 | 3 / 0.396 / 0.903 / 0.408 | 4 / 0.588 / 0.903 / 0.275 |
| pm2 | primary 5 0.302; alt1 4 0.348; alt2 3 0.117; alt3 5 0.301; alt4 1 0.154 | 3 / 0.272 / 0.467 / 0.424 | 3 / 0.272 / 0.467 / 0.424 | 4 / 0.320 / 0.631 / 0.473 | 4 / 0.320 / 0.631 / 0.473 | 4 / 0.320 / 0.631 / 0.473 | 4 / 0.320 / 0.631 / 0.473 |
| s06 | primary 3 0.551; alt1 0 0.000; alt2 1 0.433; alt3 1 0.427 | 3 / 0.324 / 0.579 / 0.683 | 3 / 0.324 / 0.579 / 0.683 | 4 / 0.380 / 0.612 / 0.618 | 4 / 0.380 / 0.612 / 0.618 | 4 / 0.380 / 0.612 / 0.618 | 4 / 0.380 / 0.612 / 0.618 |
| s07 | primary 11 0.346; alt1 8 0.403; alt2 8 0.424; alt3 8 0.415 | 2 / 0.394 / 0.671 / 0.674 | 2 / 0.428 / 0.703 / 0.650 | 2 / 0.394 / 0.671 / 0.674 | 2 / 0.428 / 0.703 / 0.650 | 2 / 0.394 / 0.671 / 0.674 | 2 / 0.428 / 0.703 / 0.650 |
| s08 | primary 0 0.000; alt1 5 0.257; alt2 4 0.203; alt3 4 0.211; alt4 5 0.244; alt5 4 0.212 | 3 / 0.349 / 0.604 / 0.321 | 3 / 0.349 / 0.604 / 0.321 | 3 / 0.349 / 0.604 / 0.321 | 3 / 0.349 / 0.604 / 0.321 | 3 / 0.349 / 0.604 / 0.321 | 3 / 0.349 / 0.604 / 0.321 |

| arm | songs that change | cover pooled (diff vs n3 0.40 [CI]) | inside pooled (diff [CI]) | toward the humans' range | away |
|---|---|---|---|---|---|
| n3_s0.40 | none | 0.603 ([0.0, 0.0, 0.0, 16]) | 0.442 ([0.0, 0.0, 0.0, 18]) | none | none |
| n3_s0.60 | lucretia, sooth, s07 | 0.605 ([0.002, 0.0, 0.006, 16]) | 0.433 ([-0.01, -0.024, 0.0, 18]) | none | lucretia, sooth, s07 |
| n4_s0.40 | pm2, s06 | 0.615 ([0.012, 0.0, 0.035, 16]) | 0.441 ([-0.001, -0.011, 0.008, 18]) | none | none |
| n4_s0.60 | lucretia, sooth, pm2, s06, s07 | 0.617 ([0.014, 0.0, 0.037, 16]) | 0.430 ([-0.012, -0.03, 0.003, 18]) | none | lucretia, sooth, s07 |
| n5_s0.40 | pm2, s06 | 0.615 ([0.012, 0.0, 0.035, 16]) | 0.441 ([-0.001, -0.011, 0.008, 18]) | none | none |
| n5_s0.60 | lucretia, sooth, pm2, s06, s07 | 0.617 ([0.014, 0.0, 0.037, 16]) | 0.430 ([-0.012, -0.03, 0.003, 18]) | none | lucretia, sooth, s07 |

Arm names: n<max_solos>_s<max_share>; n3_s0.40 is today. Cover = the humans' solo time inside ours (mean over charts with solos; songs with human solos), inside = our solo time inside a chart's solos (mean over all charts); toward/away = the song's solo share nearer to or further from the range of its human charts' shares than today.


### B-e. Expert drums: kicks and fill endings

20 songs have a human drum chart (drunk_drivers, sooth and break have none); pm2 2 charts, s05 4, s06 3, the rest 1-2. Ours = today's CPU charts (pm2 included: the review's GPU chart was not measured). Each human chart over its own span; ours over the primary's. `*` = ours outside the humans' range.

| song | charts | kicks/s | densest 10 s, kicks/s | kick share | bare-kick share | 2x share | kick P / R @50 (2x out: P / R) | our unmatched kicks: n of all, in 16th runs (matched: in runs), 2x |
|---|---|---|---|---|---|---|---|
| all_the_small_things | 1 | 2.34 [2.38-2.38]* | 2.70 [2.70-2.70] | 0.52 [0.50-0.50]* | 0.11 [0.13-0.13]* | 0.00 [0.00-0.00] | 1.000 / 0.984 (1.000 / 0.984) | 0 of 370, - (0.00), - |
| creep | 1 | 1.57 [1.55-1.55]* | 2.20 [2.00-2.00]* | 0.50 [0.46-0.46]* | 0.11 [0.10-0.10]* | 0.00 [0.00-0.00] | 0.983 / 0.997 (0.983 / 0.997) | 6 of 358, 0.00 (0.00), 0.00 |
| kimochi_warui | 1 | 1.13 [1.15-1.15]* | 3.10 [2.90-2.90]* | 0.40 [0.39-0.39]* | 0.01 [0.33-0.33]* | 0.00 [0.00-0.00] | 0.971 / 0.956 (0.971 / 0.956) | 9 of 310, 0.00 (0.00), 0.00 |
| lucretia | 1 | 2.42 [2.42-2.42]* | 3.20 [3.50-3.50]* | 0.53 [0.52-0.52]* | 0.26 [0.28-0.28]* | 0.00 [0.01-0.01]* | 0.982 / 0.979 (0.978 / 0.980) | 10 of 558, 0.00 (0.01), 0.00 |
| take_me_out | 1 | 1.74 [1.68-1.68]* | 2.50 [2.50-2.50] | 0.42 [0.38-0.38]* | 0.01 [0.09-0.09]* | 0.00 [0.00-0.00] | 0.959 / 0.992 (0.959 / 0.992) | 16 of 395, 0.00 (0.00), 0.00 |
| troop | 1 | 5.55 [4.07-4.07]* | 13.40 [6.70-6.70]* | 0.67 [0.56-0.56]* | 0.30 [0.12-0.12]* | 0.36 [0.00-0.00]* | 0.721 / 0.983 (0.841 / 0.735) | 460 of 1646, 0.96 (0.38), 0.64 |
| pm2 | 2 | 4.64 [3.74-4.69] | 10.70 [6.00-10.90] | 0.62 [0.55-0.60]* | 0.28 [0.17-0.26]* | 0.23 [0.00-0.20]* | 0.898 / 0.988 (0.923 / 0.877) | 3 of 2025, 0.00 (0.39), 0.00 |
| s01 | 2 | 3.37 [3.92-3.96]* | 12.90 [13.00-13.00]* | 0.59 [0.59-0.59]* | 0.27 [0.21-0.21]* | 0.19 [0.31-0.32]* | 0.959 / 0.821 (0.817 / 0.828) | 11 of 908, 0.00 (0.29), 0.00 |
| s02 | 2 | 1.30 [1.08-1.11]* | 3.60 [3.50-3.50]* | 0.69 [0.52-0.53]* | 0.26 [0.14-0.14]* | 0.00 [0.00-0.00] | 0.796 / 0.945 (0.796 / 0.945) | 65 of 345, 0.17 (0.00), 0.00 |
| s03 | 2 | 2.58 [2.70-2.70]* | 3.40 [3.40-3.70] | 0.70 [0.51-0.53]* | 0.12 [0.03-0.04]* | 0.00 [0.00-0.00] | 0.967 / 0.899 (0.967 / 0.899) | 0 of 534, - (0.00), - |
| s04 | 1 | 0.67 [0.67-0.67] | 1.30 [1.30-1.30] | 0.40 [0.27-0.27]* | 0.04 [0.03-0.03]* | 0.00 [0.00-0.00] | 0.995 / 0.995 (0.995 / 0.995) | 1 of 184, 0.00 (0.00), 0.00 |
| s05 | 4 | 2.49 [2.50-2.52]* | 3.90 [3.90-3.90] | 0.34 [0.31-0.33]* | 0.07 [0.05-0.07] | 0.00 [0.00-0.00] | 0.850 / 0.842 (0.850 / 0.842) | 3 of 567, 0.00 (0.00), 0.00 |
| s06 | 3 | 2.32 [1.95-2.09]* | 7.00 [3.00-3.00]* | 0.51 [0.46-0.47]* | 0.08 [0.12-0.13]* | 0.04 [0.00-0.00]* | 0.629 / 0.701 (0.653 / 0.700) | 130 of 1280, 0.43 (0.00), 0.35 |
| s07 | 2 | 2.95 [2.96-2.96]* | 5.50 [5.50-5.50] | 0.61 [0.52-0.52]* | 0.28 [0.24-0.24]* | 0.07 [0.09-0.09]* | 0.995 / 0.990 (0.980 / 0.990) | 4 of 910, 0.00 (0.19), 0.00 |
| s08 | 1 | 2.07 [2.59-2.59]* | 4.00 [5.80-5.80]* | 0.49 [0.50-0.50]* | 0.27 [0.32-0.32]* | 0.00 [0.21-0.21]* | 0.965 / 0.772 (0.859 / 0.874) | 28 of 802, 0.07 (0.18), 0.00 |
| s09 | 1 | 2.17 [2.05-2.05]* | 5.50 [5.50-5.50] | 0.58 [0.52-0.52]* | 0.26 [0.25-0.25]* | 0.00 [0.00-0.00] | 0.897 / 0.950 (0.897 / 0.950) | 90 of 876, 0.06 (0.03), 0.00 |
| s10 | 2 | 4.18 [4.46-4.48]* | 11.40 [11.80-11.80]* | 0.71 [0.66-0.70]* | 0.40 [0.28-0.38]* | 0.34 [0.32-0.39] | 0.906 / 0.852 (0.608 / 0.583) | 13 of 860, 0.00 (0.35), 0.00 |
| s11 | 2 | 1.47 [1.50-1.63]* | 5.00 [4.20-6.60] | 0.53 [0.43-0.46]* | 0.17 [0.16-0.19] | 0.00 [0.00-0.00] | 0.907 / 0.855 (0.907 / 0.855) | 39 of 553, 0.18 (0.07), 0.00 |
| s12 | 1 | 1.83 [1.94-1.94]* | 2.80 [3.00-3.00]* | 0.56 [0.48-0.48]* | 0.11 [0.02-0.02]* | 0.00 [0.00-0.00] | 0.979 / 0.922 (0.979 / 0.922) | 13 of 615, 0.00 (0.00), 0.00 |
| s13 | 2 | 2.02 [2.02-2.04] | 3.30 [3.30-3.40] | 0.40 [0.37-0.37]* | 0.04 [0.05-0.05]* | 0.00 [0.01-0.02]* | 0.857 / 0.851 (0.849 / 0.859) | 67 of 558, 0.06 (0.02), 0.00 |
- kicks/s: ours outside the humans' range on 17 of 20 songs (above on 6)
- densest 10 s, kicks/s: ours outside the humans' range on 10 of 20 songs (above on 5)
- kick share: ours outside the humans' range on 20 of 20 songs (above on 19)
- bare-kick share: ours outside the humans' range on 18 of 20 songs (above on 11)
- 2x share: ours outside the humans' range on 8 of 20 songs (above on 3)
- Kick precision, song mean 0.911; our kicks no human chart has within 50 ms: 968 of 14654, troop 460, s06 130, s09 90 the most.

**Fill endings** (our fills = the chart's drum fill phrases, = report.json's fills; "crash" = starpower's test: a green cymbal, or a yellow or blue one with fewer than 3 others on its pad within 2 beats; humans: pro-drums charts only):

| song | our fills, crash share (report.json) | human charts: fills, crash share | humans: crash on our section starts | added crash: n, judged, a human crash there / any cymbal / any onset |
|---|---|---|---|---|
| all_the_small_things | 15, 0.40 (0.40) | primary 23 0.74 | primary 0.67 | 9, 9, 0.22 / 0.56 / 1.00 |
| creep | 12, 0.08 (0.08) | primary 19 0.63 | primary 0.62 | 11, 11, 0.36 / 1.00 / 1.00 |
| kimochi_warui | 14, 0.00 (0.00) | primary 3 0.00 | primary 0.08 | 14, 14, 0.07 / 0.36 / 1.00 |
| lucretia | 13, 0.54 (0.54) | primary 20 1.00 | primary 1.00 | 6, 6, 0.50 / 1.00 / 1.00 |
| take_me_out | 17, 0.53 (0.53) | primary 24 0.75 | primary 1.00 | 8, 8, 0.12 / 0.50 / 1.00 |
| troop | 39, 0.36 (0.36) | primary 21 1.00 | primary 0.59 | 25, 25, 0.40 / 0.88 / 1.00 |
| pm2 | 54, 0.18 (0.18) | primary 65 0.55; alt4 80 0.66 | primary 0.45; alt4 0.45 | 44, 44, 0.07 / 0.61 / 1.00 |
| s01 | 35, 0.37 (0.37) | alt1 40 0.90 | alt1 0.88 | 22, 22, 0.68 / 0.77 / 0.95 |
| s02 | 11, 0.82 (0.82) | primary 14 0.86 | primary 1.00 | 2, 2, 0.00 / 0.00 / 0.50 |
| s03 | 21, 0.62 (0.62) | primary 29 0.66 | primary 1.00 | 8, 8, 0.62 / 1.00 / 1.00 |
| s04 | 10, 0.90 (0.90) | primary 12 0.75 | primary 0.91 | 1, 1, 0.00 / 1.00 / 1.00 |
| s05 | 20, 0.40 (0.40) | primary 0 -; alt1 0 -; alt2 33 0.76 | primary 0.35; alt1 0.39; alt2 0.47 | 12, 12, 0.42 / 1.00 / 1.00 |
| s06 | 52, 0.27 (0.27) | primary 70 0.74 | primary 0.81 | 38, 38, 0.53 / 0.87 / 0.97 |
| s07 | 30, 0.73 (0.73) | alt1 41 0.66 | alt1 0.65 | 8, 8, 0.25 / 1.00 / 1.00 |
| s08 | 31, 0.23 (0.23) | no pro chart | - | 24, 0, - / - / - |
| s09 | 28, 0.43 (0.43) | primary 26 0.92 | primary 0.86 | 16, 16, 0.38 / 0.81 / 0.81 |
| s10 | 25, 0.36 (0.36) | primary 27 0.56 | primary 0.50 | 16, 16, 0.19 / 0.94 / 1.00 |
| s11 | 21, 0.05 (0.05) | primary 17 0.71 | primary 0.50 | 20, 20, 0.35 / 0.65 / 1.00 |
| s12 | 25, 0.40 (0.40) | primary 18 0.89 | primary 0.88 | 15, 15, 0.60 / 1.00 / 1.00 |
| s13 | 15, 0.20 (0.20) | alt1 26 0.81 | alt1 0.50 | 12, 12, 0.33 / 0.83 / 1.00 |

Our fill crash share is under every human chart's on 16 songs: all_the_small_things, creep, lucretia, take_me_out, troop, pm2, s01, s02, s03, s05, s06, s09, s10, s11, s12, s13.

**Candidate C (a crash added at the end of each of our fills that has none):** 287 added crashes judged (inside a pro human chart's span; s08's only drum chart is not pro), pooled precision 0.348 against the humans' crash test, 0.784 against any cymbal. A note is there on our chart already at almost every fill end, so onset F1@50 does not change; only the pad/cymbal agreement would.

**Candidates K (kicks thinned in runs of 16th-note kicks)**, no build: K<N> removes every second kick of a run of 4+ kicks at gaps of a 16th or less whose rate is N kicks a second or more; K2x removes the runs' double-kick (Expert+) kicks instead. Removal precision = removed kicks with no human kick within 50 ms (pooled by count).

| rule | songs touched | kicks removed | precision pooled | drums onset F1@50 change [CI] | kick F1@50 change [CI] | per song (removed, precision, onset F1 change) |
|---|---|---|---|---|---|---|
| K8 | 6 | 1184 | 0.369 | [-0.0, -0.008, 0.01, 20] | [-0.004, -0.022, 0.016, 20] | troop 439 0.97 +0.080; pm2 384 0.00 -0.005; s01 127 0.00 -0.033; s06 14 0.93 +0.002; s07 75 0.00 -0.009; s10 145 0.00 -0.039 |
| K10 | 4 | 1095 | 0.387 | [0.0, -0.008, 0.011, 20] | [-0.002, -0.02, 0.017, 20] | troop 439 0.97 +0.080; pm2 384 0.00 -0.005; s01 127 0.00 -0.033; s10 145 0.00 -0.039 |
| K12 | 4 | 955 | 0.444 | [0.001, -0.006, 0.011, 20] | [0.001, -0.014, 0.019, 20] | troop 439 0.97 +0.080; pm2 319 0.00 -0.005; s01 127 0.00 -0.033; s10 70 0.00 -0.014 |
| K2x | 7 | 1481 | 0.215 | [-0.002, -0.01, 0.005, 20] | [-0.017, -0.033, -0.004, 20] | lucretia 1 0.00 -0.001; troop 589 0.49 +0.048; pm2 468 0.00 -0.004; s01 163 0.00 -0.038; s06 29 0.97 +0.003; s07 67 0.00 -0.008; s10 164 0.00 -0.046 |

Caveats: 15 of the 20 songs have one or two human drum charts, so "outside the range" is often outside a single value;
the kick share is high partly because we chart fewer non-kick onsets. The 16th-run test uses our tick grid (gap of
res/4 or less). The added-crash precision uses starpower's crash test on the human charts; "any cymbal" also counts a
hi-hat or ride. Not measured: the owner's GPU chart of pm2 (today's CPU chart has 3 unmatched kicks of 2025).

### The bars (one line per order)

- **M7-03 (bass)**: **none clears.** (a) the held-note gate: removal precision 0.39-0.48 pooled (bar 0.75), F1@50
  down at every X (X 50: -0.015 [-0.040, +0.008]), 10-15 songs down by more than 0.01, refs down at every X (stop
  rule). (b) the map: contour +0.011 [+0.004, +0.020] pooled (bar +0.02), repeat share 0.585 to 0.564 (humans 0.487).
  The cause: of our same-lane consecutive pairs 88 % (6172 of 6983) are the same pitch by the engine's own pitch
  track, 5 % changed by a semitone or more; 77 % of the same-pitch ones are onsets on a still-voiced note; only 8.3 %
  of pitch changes of 1 st or more keep the lane. So the excess repeats are the onset detector's (same pitch), not the
  map's, but the gate cannot tell them from the humans' repeated notes (most of what it drops the humans also chart).
- **M7-04 (silence)**: **none clears.** Guitar: precision 0.09-0.14 at every D and rule; bass: precision 1.0 but 0-5
  onsets, and the humans' notes the rule removes are 0.5 % or more on 8-10 songs; drums: precision 0.32 (i, 25) to
  0.875 (i, 35: 8 onsets on 3 songs), human notes removed 0.5 % or more on 3-10 songs at every setting. (Repeats are
  part A's A-d.)
- **M7-06 (solos)**: **the first condition holds, the second does not; none clears.** Six human charts on two songs
  are over 0.40 (s06 0.551/0.433/0.427, s07 0.403/0.424/0.415), none an instrumental (sooth's largest 0.357), so an
  instrumentals-only cap has no evidence. Cap 0.60 (M5-03's rule on the 23 songs): changes lucretia, sooth, s07;
  cover +0.002 [0.000, 0.006], inside -0.010 [-0.024, 0.000], and all three songs' shares move away from their humans'
  range. 0.75 for instrumentals: sooth only, cover unchanged, inside -0.006, moves away.
  B-c2 (max_solos): 4 or 5 at 0.40 change pm2 and s06 only (both gain a 4th solo; 5 picks the same as 4, as no song
  has a 5th candidate that fits); cover +0.012 [0.000, 0.035], inside -0.001 [-0.011, 0.008], both songs stay inside
  their humans' range, no song moves away. At 0.60 the share cap's three songs move away again. The closest to the
  bar is max_solos 4 at 0.40: cover up but its CI touches 0, inside flat.
- **M7-07 (drumless sync)**: **none clears.** 36 stretches on 16 songs have human beat lines (3 have none). allin1 at
  our octave: +0.060 over the stretches (song CI [-0.10, +0.13]; +0.051 without lucretia) but 7 of 36 stretches down
  by more than 0.05 (bar: none); allin1 as is -0.043; the bass envelope -0.090 (18 down); the guitar under 350 Hz -0.249
  (19 down).
- **B-e (drums, no order yet)**: **no candidate clears.** Kick thinning in 16th runs is right only on troop
  (precision 0.97, onset F1 +0.080; its one human chart has no 2x kicks) and s06 (0.93); on pm2, s01, s07 and s10 the
  humans chart the same kicks (precision 0.00), pooled 0.37-0.44 (K2x 0.215). A crash added at our crashless fill ends:
  precision 0.348 by the crash test (0.784 any cymbal), although our fill-crash share is under every human chart's on
  16 songs; onset F1 cannot change.

### Caveats

- The references have one human chart each, so the 0.6 agreement rule cannot reach them; lucretia's whole-song beat
  F1 is 0.26 (its human map is at another beat level), so its stretches say little.
- B-a's "silent" humans: on kimochi_warui and s02 nearly half of a human chart's guitar notes are under the guitar
  stem's floor (the lead is in another stem), the cause of most of the guitar candidates' damage.
- B-b's held test and the HFC rank are this measurement's definitions (the order names the idea, not the
  thresholds); a stricter "held" (longer window) was not tried. The gate drops our chart's onset mapped to the
  engine onset (40 ms); unmapped engine onsets drop nothing.
- B-c: the solo re-run places solos on our grid's sections exactly as the run did (checked); the overlap
  measures have few songs with human solos (16), many single-chart.
- B-d: the candidates were beat-tracked over the whole song and cut to the stretch; a candidate run only inside the
  stretch, or a hybrid, was not tried. The bass and guitar trackers start from our tempo, so they share our octave.
- Not checked: the drums' per-window F1 under an audible hi-hat beyond the quiet-section split (only 3 songs have a
  section 10 dB under their median; our drums there are not blank: 0.24-1.35 onsets/s, as the humans').

### Machine time, disk, scripts

- Machine time: about 25 minutes of CPU (B-a 6 min, B-b 7.5 min, B-c 1 min, B-d 5 min, the note cache 2 min), no
  heavy-job lock needed (no build, chart or take); run with 1-2 threads beside the other parts.
- Disk: `df -h /` before and after: 2.3G available (95 % used); the scratch outputs 0.7 MB; <shm>/m7/B (the note
  and level cache, 18 MB) removed at the end.
- Scripts (in this folder; each starts with what it reads and prints): `common.py` (the loader and note cache),
  `stats.py` (F1, agreement, bootstrap), `ba.py` (B-a), `bb.py` (B-b), `bc.py` (B-c), `bc2.py` and `make_bc2.py` (B-c2), `drums_scan.cjs`, `be.py`, `be_cand.py` and `make_be.py` (B-e), `bd.py` (B-d),
  `make_report.py` (the tables and summary.json), `round3.py` (floats to 3 decimals, for privacy_check), `env.sh` (the environment). Run: `. env.sh; $PY ba.py ba.json; $PY
  bb.py bb.json; $PY bc.py bc.json -25; $PY bd.py bd.json; $PY make_report.py`.
- JSON: `ba.json`, `bb.json`, `bc.json`, `bc2.json`, `be.json`, `be_cand.json`, `bd.json` (per song), `summary.json` (pooled, CIs).

---

## Part C: M7-01 part C: the take margin (M7-05's bar)

Numbers only; songs by label (references by id, the stress set troop/sooth/break/pm2, the 20-song set s01-s13, its
ids sorted). Guitar Expert only. Code: main 72f5679 (charting code a5895ff's), patched in a worktree that was never
committed (`margin.patch`).

### What was run

**C-a, the takes.** All 23 songs (every one has a human guitar chart; test_song has none and is not in the set).
Seeds 101, 202, 303 (`pipeline.take_seeds(4)`) beside each kept take (20260609), with
`songcharter.engines.autochart.generate(install, <kept>/decode.wav, $SONGCHARTER_GOLDEN/m7-takes/<id>, (seed,),
device="cpu", work=<shm>/m7/C-work/<label>)`, the BLAS/OMP thread variables at 2, one `tools/heavy.sh` job per
song (cheapest first by the kept take's generation time; sooth, troop, pm2 last), waiting for 6 GB of free RAM and
refusing under 0.5 GB of disk. 69 takes, none failed, every `inputSha256` equal to the kept take's; the install key
equals the kept takes' (8ddc414b...). Six takes (sooth and pm2, all three seeds each) were cut short by the beat cap and
continued by `continue_take`, as their kept takes were. Engine scratch per song: 66 MB (first song, break: 71 MB) to
247 MB (pm2), deleted after each song, so the order's 1 GB estimate did not occur.

**C-b, the arms: built by `songcharter chart`** (the order's first route, not `assemble` in process). Per song: `cp
-al` of the kept folder to `$SONGCHARTER_GOLDEN/m7-copy/<id>` (same file system), every file under 5 MB then
replaced by a real copy so an in-place write could never reach the kept folder, the three takes hard-linked in as
`guitar/seed_<seed>/`; then `python -m songcharter.cli chart <input.wav> --out <shm>/m7/C-arms/... --work <copy>
--takes 4 --device cpu --no-preview --threads 2` from <shm>/m7/code-C. The patch (`margin.patch`): `takes.splice`
reads `SC_M7_MARGIN` (the margin), `SC_M7_FORCE` (every window from take k: the oracle) and `SC_M7_SILENT` (below).
Every stage but assemble came from the cache (bass ran once a song, as part A saw: its engine changed since the kept
folders). A listing of the kept folder (path, size, mtime, inode) before and after each song was identical for all
23. The copy was deleted after each song. Arms:
- **one**: the one-take chart, today's CPU default. Taken from the base's prior runs (v031, gate3-new-stress,
  set20-main), which part A found identical to its base arm on guitar; part A's own base files were deleted before
  this analysis ran. This part's **f0** arm (every window from the kept take, through the splice path) has the same
  F1@50 and F1@100 against every chart on all 23 songs, which confirms the base.
- **m0, m02, m05, m10**: `takes.MARGIN` 0, 0.02, 0.05 (today), 0.10. m0 was built first; each other margin's picks
  were computed from m0's window scores, and an arm whose picks equal a built arm's was not rebuilt (it is listed
  `same_as`; every built arm's picks were asserted equal to the computed ones).
- **f0-f3** (the oracle, reported only): every window from take 1, 2, 3 or 4.
- **q0, q05**: the review's fix 3.1, added because even m0 leaves windows where a take with more human-matched
  onsets loses (234 windows; below). Each take's onsets that part B's test calls silent (`assemble.silent_onsets` on
  the guitar part's stem levels, the same stem `assemble` uses for its warning, 25 dB, window -0.05/+0.20 s) cannot
  match in the take score (`_m7_agreement`), with the denominators unchanged; margin 0 and 0.05.
- Scoring: `eval/scorer/score.py` through `eval/stress.py`'s `run_score` against the primary and every alt with
  guitar notes (s11's alt4 has none and is not scored, as in set20-main).

220 builds; 2.8 hours of chart time plus their scoring.

**C-c, the numbers.** A song's value: F1@50 against the primary (`p50`, the bar's measure) and the mean over its
human charts (`mean50`); the humans' agreement is the mean F1@50 of each alt against the primary (stress_scores'
`humans`). Pooled: mean over songs. Paired bootstrap over songs, 10,000 resamples, seed fixed. Songs whose humans agree
under 0.6 are left out of the pooled figures and named: **s02 (0.499), s04 (0.250), s06 (0.585), s12 (0.383)**; the
references have one chart and cannot be tested, so each pooled figure is given with them (19 songs) and without
them (13). The all-23 figure, no exclusion, is given too.

**Per window** (`windows.py`): each take's onsets and its human-matched onsets (score.py's one-to-one match at 50
ms) against the primary in each splice window, from the oracle arm of that take (its chart through the pipeline, on
input seconds with score.py's shift); the humans' onsets are the primary's only.

### C-c per song: guitar Expert F1@50, against the primary / the mean over the song's human charts

| song | set | charts | humans | one | m0 | m02 | m05 | m10 | q0 | q05 | takes alone f0/f1/f2/f3 (mean) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| all_the_small_things | refs | 1 | — | 0.971 / 0.971 | 0.977 / 0.977 | 0.979 / 0.979 | 0.979 / 0.979 | 0.979 / 0.979 | 0.977 / 0.977 | 0.979 / 0.979 | 0.971/0.998/0.958/0.988 |
| creep | refs | 1 | — | 0.774 / 0.774 | 0.780 / 0.780 | 0.779 / 0.779 | 0.774 / 0.774 | 0.774 / 0.774 | 0.780 / 0.780 | 0.774 / 0.774 | 0.774/0.728/0.748/0.781 |
| drunk_drivers | refs | 1 | — | 0.785 / 0.785 | 0.765 / 0.765 | 0.757 / 0.757 | 0.788 / 0.788 | 0.785 / 0.785 | 0.765 / 0.765 | 0.788 / 0.788 | 0.785/0.784/0.704/0.645 |
| kimochi_warui | refs | 1 | — | 0.827 / 0.827 | 0.760 / 0.760 | 0.760 / 0.760 | 0.760 / 0.760 | 0.793 / 0.793 | 0.773 / 0.773 | 0.817 / 0.817 | 0.827/0.701/0.600/0.756 |
| lucretia | refs | 1 | — | 0.847 / 0.847 | 0.831 / 0.831 | 0.832 / 0.832 | 0.832 / 0.832 | 0.847 / 0.847 | 0.831 / 0.831 | 0.832 / 0.832 | 0.847/0.824/0.831/0.822 |
| take_me_out | refs | 1 | — | 0.909 / 0.909 | 0.910 / 0.910 | 0.910 / 0.910 | 0.915 / 0.915 | 0.920 / 0.920 | 0.910 / 0.910 | 0.915 / 0.915 | 0.909/0.875/0.913/0.910 |
| break | stress | 2 | 0.9514 | 0.832 / 0.836 | 0.785 / 0.789 | 0.785 / 0.789 | 0.785 / 0.789 | 0.783 / 0.790 | 0.785 / 0.789 | 0.785 / 0.789 | 0.836/0.736/0.704/0.791 |
| pm2 | stress | 5 | 0.9425 | 0.807 / 0.806 | 0.824 / 0.823 | 0.808 / 0.807 | 0.802 / 0.801 | 0.802 / 0.800 | 0.827 / 0.819 | 0.806 / 0.797 | 0.806/0.800/0.825/0.803 |
| sooth | stress | 2 | 0.712 | 0.704 / 0.740 | 0.713 / 0.754 | 0.710 / 0.749 | 0.712 / 0.750 | 0.704 / 0.740 | 0.713 / 0.754 | 0.712 / 0.750 | 0.740/0.722/0.741/0.738 |
| troop | stress | 3 | 0.9213 | 0.784 / 0.792 | 0.764 / 0.777 | 0.767 / 0.780 | 0.787 / 0.795 | 0.785 / 0.793 | 0.764 / 0.778 | 0.788 / 0.796 | 0.792/0.770/0.711/0.777 |
| s01 | set20 | 4 | 0.6846 | 0.735 / 0.596 | 0.780 / 0.607 | 0.780 / 0.607 | 0.783 / 0.606 | 0.778 / 0.606 | 0.778 / 0.605 | 0.781 / 0.604 | 0.596/0.591/0.582/0.599 |
| s02 | set20 | 2 | 0.4986 | 0.426 / 0.578 | 0.442 / 0.594 | 0.442 / 0.594 | 0.440 / 0.595 | 0.440 / 0.595 | 0.445 / 0.597 | 0.436 / 0.592 | 0.578/0.589/0.546/0.570 |
| s03 | set20 | 2 | 0.991 | 0.832 / 0.834 | 0.950 / 0.950 | 0.929 / 0.930 | 0.929 / 0.930 | 0.893 / 0.896 | 0.950 / 0.950 | 0.929 / 0.930 | 0.834/0.945/0.953/0.906 |
| s04 | set20 | 5 | 0.25 | 0.759 / 0.364 | 0.746 / 0.363 | 0.745 / 0.363 | 0.743 / 0.363 | 0.745 / 0.360 | 0.746 / 0.363 | 0.743 / 0.363 | 0.364/0.367/0.354/0.356 |
| s05 | set20 | 6 | 0.7389 | 0.912 / 0.778 | 0.912 / 0.778 | 0.912 / 0.778 | 0.912 / 0.778 | 0.912 / 0.778 | 0.918 / 0.777 | 0.912 / 0.778 | 0.778/0.763/0.777/0.712 |
| s06 | set20 | 4 | 0.5848 | 0.750 / 0.544 | 0.784 / 0.581 | 0.784 / 0.578 | 0.777 / 0.570 | 0.772 / 0.566 | 0.784 / 0.581 | 0.777 / 0.570 | 0.544/0.580/0.561/0.559 |
| s07 | set20 | 4 | 0.8427 | 0.861 / 0.793 | 0.874 / 0.803 | 0.876 / 0.804 | 0.876 / 0.804 | 0.876 / 0.805 | 0.874 / 0.803 | 0.876 / 0.804 | 0.793/0.799/0.801/0.778 |
| s08 | set20 | 6 | 0.7295 | 0.781 / 0.613 | 0.796 / 0.623 | 0.793 / 0.620 | 0.793 / 0.620 | 0.784 / 0.613 | 0.796 / 0.623 | 0.793 / 0.620 | 0.613/0.586/0.629/0.638 |
| s09 | set20 | 4 | 0.797 | 0.771 / 0.701 | 0.785 / 0.712 | 0.777 / 0.704 | 0.773 / 0.701 | 0.767 / 0.697 | 0.785 / 0.712 | 0.773 / 0.701 | 0.701/0.708/0.720/0.693 |
| s10 | set20 | 4 | 0.6866 | 0.844 / 0.657 | 0.846 / 0.660 | 0.837 / 0.652 | 0.839 / 0.650 | 0.832 / 0.642 | 0.846 / 0.660 | 0.839 / 0.650 | 0.657/0.658/0.671/0.658 |
| s11 | set20 | 4 | 0.6959 | 0.855 / 0.672 | 0.861 / 0.677 | 0.859 / 0.674 | 0.862 / 0.676 | 0.857 / 0.673 | 0.861 / 0.677 | 0.862 / 0.676 | 0.672/0.672/0.668/0.658 |
| s12 | set20 | 2 | 0.3831 | 0.748 / 0.580 | 0.748 / 0.584 | 0.749 / 0.585 | 0.749 / 0.583 | 0.748 / 0.580 | 0.748 / 0.584 | 0.749 / 0.583 | 0.580/0.556/0.592/0.560 |
| s13 | set20 | 2 | 0.8867 | 0.727 / 0.709 | 0.727 / 0.708 | 0.726 / 0.707 | 0.738 / 0.719 | 0.727 / 0.709 | 0.731 / 0.713 | 0.738 / 0.719 | 0.709/0.703/0.706/0.647 |

### C-c per song: F1@100 against the primary / the mean

| song | one | m0 | m02 | m05 | m10 | q0 | q05 |
|---|---|---|---|---|---|---|---|
| all_the_small_things | 0.971 / 0.971 | 0.977 / 0.977 | 0.979 / 0.979 | 0.979 / 0.979 | 0.979 / 0.979 | 0.977 / 0.977 | 0.979 / 0.979 |
| creep | 0.864 / 0.864 | 0.869 / 0.869 | 0.869 / 0.869 | 0.864 / 0.864 | 0.864 / 0.864 | 0.869 / 0.869 | 0.864 / 0.864 |
| drunk_drivers | 0.791 / 0.791 | 0.773 / 0.773 | 0.765 / 0.765 | 0.794 / 0.794 | 0.791 / 0.791 | 0.773 / 0.773 | 0.794 / 0.794 |
| kimochi_warui | 0.827 / 0.827 | 0.760 / 0.760 | 0.760 / 0.760 | 0.760 / 0.760 | 0.793 / 0.793 | 0.773 / 0.773 | 0.817 / 0.817 |
| lucretia | 0.908 / 0.908 | 0.895 / 0.895 | 0.897 / 0.897 | 0.895 / 0.895 | 0.908 / 0.908 | 0.895 / 0.895 | 0.895 / 0.895 |
| take_me_out | 0.916 / 0.916 | 0.917 / 0.917 | 0.917 / 0.917 | 0.922 / 0.922 | 0.927 / 0.927 | 0.917 / 0.917 | 0.922 / 0.922 |
| break | 0.855 / 0.853 | 0.806 / 0.799 | 0.806 / 0.799 | 0.806 / 0.799 | 0.806 / 0.806 | 0.806 / 0.799 | 0.806 / 0.799 |
| pm2 | 0.817 / 0.815 | 0.837 / 0.833 | 0.821 / 0.818 | 0.813 / 0.811 | 0.812 / 0.810 | 0.841 / 0.830 | 0.818 / 0.808 |
| sooth | 0.793 / 0.794 | 0.801 / 0.806 | 0.799 / 0.802 | 0.802 / 0.804 | 0.793 / 0.794 | 0.801 / 0.806 | 0.802 / 0.804 |
| troop | 0.805 / 0.811 | 0.774 / 0.787 | 0.779 / 0.791 | 0.803 / 0.810 | 0.806 / 0.812 | 0.775 / 0.787 | 0.804 / 0.810 |
| s01 | 0.833 / 0.727 | 0.864 / 0.744 | 0.864 / 0.744 | 0.865 / 0.744 | 0.862 / 0.742 | 0.862 / 0.742 | 0.864 / 0.742 |
| s02 | 0.474 / 0.632 | 0.490 / 0.645 | 0.490 / 0.645 | 0.489 / 0.648 | 0.489 / 0.648 | 0.492 / 0.648 | 0.485 / 0.645 |
| s03 | 0.832 / 0.835 | 0.951 / 0.951 | 0.930 / 0.932 | 0.930 / 0.932 | 0.894 / 0.897 | 0.951 / 0.951 | 0.930 / 0.932 |
| s04 | 0.800 / 0.564 | 0.791 / 0.565 | 0.789 / 0.563 | 0.788 / 0.564 | 0.785 / 0.559 | 0.791 / 0.565 | 0.788 / 0.564 |
| s05 | 0.912 / 0.938 | 0.912 / 0.939 | 0.912 / 0.938 | 0.912 / 0.938 | 0.912 / 0.938 | 0.918 / 0.937 | 0.912 / 0.938 |
| s06 | 0.764 / 0.683 | 0.809 / 0.713 | 0.808 / 0.711 | 0.800 / 0.704 | 0.795 / 0.700 | 0.809 / 0.713 | 0.800 / 0.704 |
| s07 | 0.887 / 0.864 | 0.895 / 0.872 | 0.901 / 0.875 | 0.902 / 0.876 | 0.902 / 0.876 | 0.895 / 0.872 | 0.902 / 0.876 |
| s08 | 0.802 / 0.711 | 0.819 / 0.723 | 0.817 / 0.721 | 0.814 / 0.720 | 0.805 / 0.712 | 0.819 / 0.723 | 0.814 / 0.720 |
| s09 | 0.796 / 0.765 | 0.817 / 0.783 | 0.806 / 0.773 | 0.802 / 0.768 | 0.794 / 0.762 | 0.817 / 0.783 | 0.802 / 0.768 |
| s10 | 0.871 / 0.794 | 0.862 / 0.787 | 0.852 / 0.782 | 0.853 / 0.783 | 0.848 / 0.778 | 0.862 / 0.787 | 0.853 / 0.783 |
| s11 | 0.876 / 0.838 | 0.880 / 0.840 | 0.879 / 0.838 | 0.881 / 0.841 | 0.877 / 0.839 | 0.880 / 0.840 | 0.881 / 0.841 |
| s12 | 0.771 / 0.738 | 0.772 / 0.741 | 0.774 / 0.742 | 0.774 / 0.741 | 0.771 / 0.738 | 0.772 / 0.741 | 0.774 / 0.741 |
| s13 | 0.776 / 0.760 | 0.782 / 0.766 | 0.782 / 0.766 | 0.791 / 0.775 | 0.776 / 0.760 | 0.786 / 0.771 | 0.791 / 0.775 |

### Windows and seams per song (m0/m02/m05/m10/q0/q05)

| song | windows (with human notes) | switched from the kept take | seams | windows that differ from m05 (m0/m02/m10/q0/q05) | windows where the picked take's F1 vs the primary is below the best take's by > 0.05 |
|---|---|---|---|---|---|
| all_the_small_things | 10 (10) | 7/4/2/1/7/2 | 8/5/3/2/8/3 | 5/2/1/5/0 | 2/2/2/2/2/2 |
| creep | 9 (9) | 6/1/0/0/6/0 | 5/2/0/0/5/0 | 6/1/0/6/0 | 2/0/0/0/2/0 |
| drunk_drivers | 11 (11) | 6/4/1/0/6/1 | 8/6/2/0/8/2 | 5/3/1/5/0 | 4/5/3/3/4/3 |
| kimochi_warui | 14 (14) | 5/5/5/4/6/3 | 5/5/5/5/6/5 | 0/0/1/3/3 | 4/4/4/3/5/2 |
| lucretia | 10 (10) | 8/5/3/0/8/3 | 4/5/5/0/4/5 | 5/2/3/5/0 | 2/2/2/0/2/2 |
| take_me_out | 12 (12) | 11/10/7/5/11/7 | 6/6/10/7/7/10 | 4/3/2/5/1 | 0/0/0/1/0/0 |
| break | 9 (8) | 7/7/7/5/7/7 | 6/6/6/5/6/6 | 0/0/2/0/0 | 3/3/3/3/3/3 |
| pm2 | 43 (43) | 26/14/9/4/26/10 | 28/23/13/8/30/15 | 17/5/5/17/1 | 15/17/19/19/14/18 |
| sooth | 22 (22) | 17/9/5/0/17/4 | 15/12/8/0/15/8 | 12/4/5/12/1 | 6/8/9/9/6/9 |
| troop | 30 (30) | 25/16/4/1/25/4 | 20/21/5/2/19/5 | 21/12/3/22/1 | 11/11/6/5/10/5 |
| s01 | 29 (29) | 27/27/22/16/27/22 | 11/11/13/14/11/14 | 5/5/6/6/1 | 14/14/14/15/14/14 |
| s02 | 14 (11) | 8/8/4/3/8/4 | 6/6/4/3/8/4 | 4/4/1/6/2 | 4/4/5/5/4/5 |
| s03 | 15 (15) | 6/5/5/3/6/5 | 7/6/6/4/7/6 | 1/0/2/1/0 | 5/6/6/7/5/6 |
| s04 | 12 (12) | 5/4/3/2/5/3 | 6/6/5/3/6/5 | 2/1/1/2/0 | 4/4/4/3/4/4 |
| s05 | 19 (18) | 6/0/0/0/8/0 | 8/0/0/0/10/0 | 6/0/0/8/0 | 4/4/4/4/4/4 |
| s06 | 36 (36) | 27/22/15/10/27/15 | 30/25/22/15/30/22 | 12/7/5/12/0 | 9/9/9/12/9/9 |
| s07 | 21 (21) | 18/11/8/7/18/8 | 14/16/11/9/14/11 | 10/3/1/10/0 | 2/3/2/2/2/2 |
| s08 | 22 (22) | 17/13/8/3/17/8 | 15/11/10/6/15/10 | 9/5/5/9/0 | 6/5/6/8/6/6 |
| s09 | 18 (18) | 14/11/9/5/14/9 | 8/10/10/4/8/10 | 5/2/4/5/0 | 6/7/8/9/6/8 |
| s10 | 22 (21) | 13/6/5/4/13/5 | 6/7/5/5/6/5 | 8/1/1/8/0 | 6/7/7/8/6/7 |
| s11 | 22 (22) | 13/7/6/2/13/6 | 14/10/9/3/14/9 | 7/1/4/7/0 | 2/2/2/3/2/2 |
| s12 | 18 (18) | 11/7/3/0/11/3 | 13/11/5/0/13/5 | 8/4/3/8/0 | 6/6/5/7/6/5 |
| s13 | 13 (13) | 9/7/4/0/8/4 | 9/7/5/0/8/5 | 5/3/4/4/0 | 3/4/3/5/3/3 |

Totals over the 23 songs: windows 431; switched m0 292, m02 203, m05 135, m10 75, q0 294, q05 133; seams m0 252, m02 217, m05 162, m10 95, q0 258, q05 165; picked take below the best by > 0.05 F1 m0 120, m02 127, m05 123, m10 133, q0 119, q05 119; by any F1 m0 271, m02 268, m05 267, m10 277, q0 272, q05 265; m0 windows where another take has more matched onsets: 234

### Pooled

**all** (19 songs)

| measure | one | m0 | m02 | m05 | m10 | q0 | q05 | best take per song (oracle) | mean of the 4 takes |
|---|---|---|---|---|---|---|---|---|---|
| p50 | 0.819 | 0.823 | 0.820 | 0.823 | 0.821 | 0.825 | 0.826 | 0.835 | 0.807 |
| p100 | 0.849 | 0.852 | 0.849 | 0.852 | 0.850 | 0.854 | 0.855 | 0.864 | 0.835 |
| mean50 | 0.770 | 0.773 | 0.769 | 0.772 | 0.770 | 0.773 | 0.775 | 0.783 | 0.757 |
| mean100 | 0.831 | 0.833 | 0.830 | 0.832 | 0.831 | 0.833 | 0.835 | 0.844 | 0.815 |

Each arm minus m05 (diff [95 % CI], paired bootstrap over songs, 10,000 resamples):

| measure | one | m0 | m02 | m10 | q0 | q05 |
|---|---|---|---|---|---|---|
| p50 | -0.0043 [-0.0192, +0.0092] | +0.0001 [-0.0050, +0.0051] | -0.0034 [-0.0076, +0.0001] | -0.0024 [-0.0078, +0.0033] | +0.0014 [-0.0039, +0.0067] | +0.0032 [-0.0001, +0.0094] |
| p100 | -0.0031 [-0.0181, +0.0106] | -0.0000 [-0.0056, +0.0055] | -0.0030 [-0.0075, +0.0005] | -0.0022 [-0.0078, +0.0035] | +0.0014 [-0.0044, +0.0071] | +0.0033 [-0.0001, +0.0096] |
| mean50 | -0.0015 [-0.0156, +0.0116] | +0.0008 [-0.0041, +0.0055] | -0.0026 [-0.0067, +0.0006] | -0.0015 [-0.0072, +0.0041] | +0.0014 [-0.0033, +0.0059] | +0.0027 [-0.0007, +0.0090] |
| mean100 | -0.0018 [-0.0160, +0.0115] | +0.0003 [-0.0045, +0.0051] | -0.0027 [-0.0068, +0.0005] | -0.0015 [-0.0072, +0.0042] | +0.0009 [-0.0040, +0.0057] | +0.0027 [-0.0006, +0.0091] |

Each splice arm minus the one-take chart:

| measure | m0 | m02 | m05 | m10 | q0 | q05 |
|---|---|---|---|---|---|---|
| p50 | +0.0044 [-0.0108, +0.0213] | +0.0009 [-0.0130, +0.0160] | +0.0043 [-0.0090, +0.0193] | +0.0020 [-0.0081, +0.0123] | +0.0057 [-0.0084, +0.0223] | +0.0075 [-0.0032, +0.0208] |
| mean50 | +0.0023 [-0.0119, +0.0184] | -0.0011 [-0.0139, +0.0130] | +0.0015 [-0.0115, +0.0158] | -0.0001 [-0.0089, +0.0095] | +0.0029 [-0.0105, +0.0187] | +0.0042 [-0.0059, +0.0169] |

**without_refs** (13 songs)

| measure | one | m0 | m02 | m05 | m10 | q0 | q05 | best take per song (oracle) | mean of the 4 takes |
|---|---|---|---|---|---|---|---|---|---|
| p50 | 0.803 | 0.817 | 0.812 | 0.815 | 0.807 | 0.818 | 0.815 | 0.824 | 0.801 |
| p100 | 0.835 | 0.846 | 0.842 | 0.844 | 0.838 | 0.847 | 0.845 | 0.854 | 0.831 |
| mean50 | 0.733 | 0.743 | 0.739 | 0.740 | 0.734 | 0.743 | 0.740 | 0.749 | 0.728 |
| mean100 | 0.808 | 0.818 | 0.814 | 0.815 | 0.810 | 0.818 | 0.815 | 0.824 | 0.802 |

Each arm minus m05 (diff [95 % CI], paired bootstrap over songs, 10,000 resamples):

| measure | one | m0 | m02 | m10 | q0 | q05 |
|---|---|---|---|---|---|---|
| p50 | -0.0113 [-0.0295, +0.0043] | +0.0020 [-0.0046, +0.0083] | -0.0026 [-0.0065, +0.0006] | -0.0072 [-0.0129, -0.0034] | +0.0029 [-0.0035, +0.0092] | +0.0002 [-0.0003, +0.0010] |
| p100 | -0.0093 [-0.0274, +0.0062] | +0.0018 [-0.0055, +0.0087] | -0.0023 [-0.0069, +0.0013] | -0.0068 [-0.0126, -0.0024] | +0.0029 [-0.0046, +0.0101] | +0.0003 [-0.0003, +0.0012] |
| mean50 | -0.0071 [-0.0256, +0.0074] | +0.0031 [-0.0028, +0.0089] | -0.0014 [-0.0048, +0.0013] | -0.0060 [-0.0114, -0.0021] | +0.0029 [-0.0022, +0.0082] | -0.0004 [-0.0012, +0.0001] |
| mean100 | -0.0075 [-0.0258, +0.0078] | +0.0024 [-0.0038, +0.0084] | -0.0017 [-0.0053, +0.0011] | -0.0058 [-0.0117, -0.0011] | +0.0022 [-0.0037, +0.0081] | -0.0004 [-0.0010, +0.0000] |

Each splice arm minus the one-take chart:

| measure | m0 | m02 | m05 | m10 | q0 | q05 |
|---|---|---|---|---|---|---|
| p50 | +0.0133 [-0.0045, +0.0345] | +0.0088 [-0.0071, +0.0276] | +0.0113 [-0.0042, +0.0303] | +0.0041 [-0.0089, +0.0182] | +0.0142 [-0.0033, +0.0354] | +0.0116 [-0.0039, +0.0293] |
| mean50 | +0.0102 [-0.0059, +0.0316] | +0.0058 [-0.0085, +0.0239] | +0.0071 [-0.0075, +0.0254] | +0.0011 [-0.0103, +0.0140] | +0.0101 [-0.0061, +0.0316] | +0.0067 [-0.0079, +0.0254] |

**All 23 songs, no exclusion** (primary F1@50, arm minus m05): one -0.0047 [-0.0172, +0.0070], worst song s03 -0.0968; m0 +0.0005 [-0.0038, +0.0047], worst song troop -0.0238; m02 -0.0023 [-0.0061, +0.0007], worst song drunk_drivers -0.0308; m10 -0.0021 [-0.0068, +0.0027], worst song s03 -0.0358; q0 +0.0017 [-0.0027, +0.0061], worst song drunk_drivers -0.0230; q05 +0.0025 [-0.0004, +0.0079], worst song s02 -0.0038

### Reading

- **The margin.** Against the primaries, over the 19 songs: m05 0.8232, m0 0.8232 (+0.0001 [-0.0050, +0.0051]),
  m02 0.8198 (-0.0034), m10 0.8208 (-0.0024). Without the references (13): m0 +0.0020 [-0.0046, +0.0083], m10
  -0.0072 [-0.0129, -0.0034] (the only CI that excludes 0, on the losing side). All 23: m0 +0.0005 [-0.0038, +0.0047],
  three songs down by more than 0.01 (troop -0.024, drunk_drivers, s13). No margin moves the pooled figure by 0.005.
- **The margin decides little because the windows mostly differ by take, not by margin.** m0 switches 292 of 431
  windows away from the kept take, m05 135, m10 75; yet the share of windows whose picked take scores more than 0.05
  F1 below the best take against the primary is about the same in every arm (119-133 windows). The take score
  (agreement with the other takes) does not track agreement with the humans at window level.
- **Splicing against one take:** m05 minus one, primary F1@50: +0.0043 [-0.0090, +0.0193] (19 songs), +0.0113
  [-0.0042, +0.0303] without the references. Per song the spread is wide: s03 +0.097, break -0.046, kimochi_warui
  -0.067. The best single take per song (an oracle no rule can reach) would give 0.835, the mean take 0.807.
- **The silent-onset take score (q).** Its picks equal an existing arm's on 14 (q0) and 15 (q05) songs: a silent onset
  the other takes do not share is already unmatched, so the change bites only where takes agree on notes in silence.
  q05 minus m05, primary F1@50: +0.0032 [-0.0001, +0.0094] (19 songs), +0.0002 [-0.0003, +0.0010] without the
  references, +0.0025 [-0.0004, +0.0079] over all 23, no song down by more than 0.004; most of the gain is one
  reference, kimochi_warui (+0.058). q0: +0.0014 [-0.0039, +0.0067].

### M7-05's bar

Bar: pooled primary F1@50 at least +0.005 over 0.05's, CI above 0, no song down by more than 0.01.
**None clears it.** m0 +0.0001 [-0.0050, +0.0051], m02 -0.0034, m10 -0.0024 (19 songs); the best candidate, q05 (the
silent-onset score at 0.05), +0.0032 [-0.0001, +0.0094]: under +0.005 and its CI touches 0, though no song falls by
more than 0.004. Part D's GPU arm was not run.

### Caveats

- Sample: 23 songs, 19 in the pooled figure, 6 of them with one human chart. Takes are sampled: these are one draw
  of three seeds a song on the CPU; the GPU takes (part D) differ.
- The window analysis uses the primary chart only, and a take's onsets as the pipeline quantized them; matched counts
  favour takes with more onsets, so the F1 version is given beside them.
- The one-take arm is the prior runs' scores (part A: guitar identical to its base), confirmed by f0; part A's base
  files were gone when this ran.
- Not checked: the other difficulties (built from the splice; not scored here), the splice's sustain cuts at seams
  (beyond F1), a margin between 0.02 and 0.05.

### Machine time and disk

- Takes: 69 takes, 7.7 hours of take time (the order estimated 6.5), run 2026-11-07 17:42 to 2026-11-08 06:24 UTC
  interleaved with part A on the heavy-job lock.
- Builds and scoring: 2026-11-07 18:05 to 2026-11-08 08:29 UTC, 220 chart runs (2.8 h of chart time) plus scoring.
- `$SONGCHARTER_GOLDEN/m7-takes`: 189 MB (not the 40 MB estimated: each take keeps its engine event log,
  expert_events.ndjson, 187 MB in all; song.ogg and the continued takes' piece input.wav deleted). Kept for M7-05.
- `df -h /` at the end: see the last line of this report.

### Files (this folder)

- `songs.py`: the labels, sets and kept folders (reads the 20-song set's songs.json for its ids).
- `gen_one.py`, `gen_all.sh`: C-a (gen.log, one line a take, a DONE line).
- `build_song.py`, `build_all.sh`: C-b (build.log); `margin.patch`: the uncommitted patch.
- `windows.py`: per-window onsets (arms/<label>.windows.json).
- `analyze.py`: results.json and the summary table; `deltas.py`: deltas.json (per song vs m05, all 23); `tables.py`:
  the tables above.
- `arms/<label>.json`: every arm's scores, picks and the splice report's windows (source paths removed); `arms/<label>/`: each arm's
  notes.chart (our charts; the report.json copies were deleted after the analysis: they held paths).

df -h / at the end: /dev/vda        252G   37G  2.1G  95% /

Privacy check: `eval/privacy_check.py` on report.md, results.json, deltas.json exits 0 with EVAL_DATA=$DEV/eval; with
$DEV/eval-set20 it flags 4 lines of results.json, each a 4-decimal F1 whose digits happen to equal a 4-hex md5 prefix
(false positives: numbers, no names); report.md and deltas.json pass. Round results.json to 3 decimals before any
commit if the check must pass. <shm>/m7/code-C (worktree), C-arms and C-work removed; <shm>/m7 is gone.

---

## Addendum (2026-11-08): B-b2, a run rule for held bass notes (M7-03's last candidate)

L or more consecutive same-lane bass onsets, each G or less after the one before, over one voiced pitch, merged into
the first (L 4, 6, 8; G 110, 150 ms), on the 23 songs (s06, s08 and s10 out of the pooled F1: their humans agree
under 0.6):

| rule | songs | removed | precision | F1@50 change [CI] | songs down > 0.01 |
|---|---|---|---|---|---|
| L4 G110 | 9 | 151 | 0.437 | +0.001 [-0.000, 0.002] | none |
| L4 G150 | 14 | 310 | 0.368 | -0.001 [-0.003, 0.001] | pm2 (-0.017) |
| L6 G110 | 5 | 33 | 0.455 | +0.000 [-0.000, 0.001] | none |
| L6 G150 | 7 | 99 | 0.212 | -0.001 [-0.002, 0.000] | pm2 (-0.012) |
| L8 G110 | 0 | 0 | - | 0 | none |
| L8 G150 | 1 | 17 | 0.000 | -0.000 | none |

The repeat share stays at 0.582-0.585 (the humans' 0.487). Against M7-03's bar (precision 0.75, F1 +0.005 with the CI
above 0): no. On ntl (no human chart) the rule merges 23 of 787 onsets at L4: its 29 runs of 6 or more fast same-lane
onsets hold 254 onsets, but only 28 of them sit in runs where every onset has an engine pitch (559 of the 787 do over
the chart): the bass engine's onsets there are not pitched notes, which is the engine's to fix (M8). **M7-03 is
closed.** Scripts: eval/m7/B/bb2.py, bb2_ntl_diag.py, make_bb2.py.
