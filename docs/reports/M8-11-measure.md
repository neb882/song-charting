# M8-11: the thin spike's 16 guitar takes of sooth, scored (measurer, 2026-11-10)

## The question

Does an engine setting (hot T 1.05, or the density knob "speed" at 5 or 6) make the guitar's fast runs on sooth less
thin, by M5-99's bar (fast windows' F1@100 +0.10, no 30-s window down by more than 0.02), raw and through today's
pipeline? And how much of a raw gain does the quantizer keep (ceiling 0.812, docs/reports/M8-ceiling.md)?

## Verdict

- **No arm clears the bar, raw or through the pipeline. No arm even moves the fast windows.** Fast-window F1@100, arm
  minus base (mean of 4 takes against 4): raw hot +0.001, dense5 -0.014, dense6 -0.012; through the pipeline hot
  -0.006, dense5 -0.011, dense6 -0.020. The bar asks +0.10. Every p is 0.40 or more (exact permutation, 70 splits).
- **The design could have seen the bar's gain.** Within-arm SD of fast F1@100 is 0.033 raw, 0.028 piped. The smallest
  difference of means a 4-vs-4 test finds is 0.057 (50 % power) / 0.078 (80 %) raw, 0.049 / 0.067 piped: under 0.10.
  So a +0.10 effect would most likely have shown; what we see is consistent with none (the upper end of what the data
  allow is about +0.05).
- **The "no window down by more than 0.02" clause cannot be judged with 4 takes.** Per 30-s window the within-arm SD
  is 0.020-0.19 (median MDD50 0.076 raw, 0.067 piped; smallest 0.034). Every arm has 5-9 windows whose mean fell by
  more than 0.02, but only 1 per arm (hot, dense6) at p < 0.05, which is the number expected by chance over 17
  comparisons. It would take roughly 30-60 takes per arm to resolve 0.02 per window.
- **Quantizer:** there is no raw gain to keep. The pipeline costs base 0.023 of fast recall (0.723 raw to 0.700) and
  0.012 of fast F1. It caps density: the 1-s peak is 11 on all 16 piped takes (raw 14-22; the human 17), and the mean
  fast-window peak falls from 12.3-14.5 raw to 10.1-10.6 piped. hot's and dense6's raw peak gains (+1.9, +2.3 notes/s,
  not significant) are gone through the pipeline (+0.1, -0.3). Piped base fast recall 0.700 is 0.86 of the 0.812
  ceiling.
- **Cost:** dense arms took twice the time for nothing: generation 1,150 s mean (1,042-1,230) against base 570
  (487-646) and hot 572; tokens about the same (6,663 base, 6,724 hot, 6,861 dense5, 6,858 dense6).
- **Record the dead end for M9:** none of the three settings thickens sooth's fast runs; the references' arm is not
  warranted.

## What was scored against what

- Takes: the zip (sha256 324ae636...30ac, 32 members), unpacked to data/sooth/<arm>/seed_<seed>/. All 16 ran with the
  transcriber on CUDA. Every summary.json's inputSha256 equals the SHA-256 of the stress set's sooth input.wav (the
  primary's own audio), so the takes are on the reference's clock and no audio lag was fitted (raw lag 0).
- Reference: sooth's **primary** human chart only (Expert guitar, read through main's eval/scorer/score.py scan). alt1
  was left out: M8-ceiling classes it as an edit with lag steps (+28 / -44 ms), so it is not well aligned. The primary
  has only **2 fast windows** (276 s and 486 s; 526 human notes, rate8 as in part D) and 16 other windows (1,710 notes).
- Windows and metrics: part D's definitions (eval/m8/m802/D/scripts/d_density.py): 30-s windows over the human span,
  score.py's window_scores, matches at 100 ms counted in the human onset's window; a window is fast when the human plays
  8 or more notes a second over it. F1 per group = 2 matched / (human + ours). Chord share = onsets with 2 or more lanes.
- Pipeline: main (cac4c2b) copied by git archive into code/; the kept sooth folder's assemble.json with the guitar
  source replaced by the take, no takes list (1 take, as the friend gets it), `python -m songcharter.cli assemble`
  under tools/heavy.sh with SONGCHARTER_HEAVY_MIN_FREE_GB=1, all 16 takes (about 40 s each, every build passed the
  gate). The output's audio was aligned to input.wav with score.py's align (lag +3,179.8 ms, 9 of 9 windows, MAD 0, the
  same on all 16; the chart's delay compensates) and then deleted.
- Noise: each arm's 4 takes are treated as repeats (seeds do not reproduce on the GPU). Arm minus base by an exact
  two-sided permutation test of the difference of means over the 70 splits of 8 takes; MDD from the pooled
  within-arm SD with t(6 df).

## Timing: the raw takes are about 60 ms late

The best F1@50 shift is -55 to -60 ms on 15 of 16 raw takes (-40 on one): raw F1@50 0.62 rises to 0.76 shifted. The
pipeline's offset step removes part of it (piped F1@50 0.70; best shifts -15 to -70 ms). At 100 ms this costs little
(raw base fast recall 0.723 at 0, 0.727 shifted), and it is the same in every arm, so it does not change the arm
comparison. It does mean raw F1@50 is not comparable with piped F1@50.

## Unsure / not done

- One song, one human chart, 2 fast windows (526 notes): a fast-run effect elsewhere is not ruled out.
- The pipeline ran main's code with the old checkout's venv (the main checkout's older venv): dependencies at main's
  lock were not checked against it.
- No splicing of an arm's 4 takes (the friend gets 1 take); not asked beyond step 2.
- The window at 96 s has a within-arm SD of 0.19 (one or more takes fail there in every arm); it inflates nothing in the
  fast windows.
- The references' arm was not run (no winner).

## Files (all under this folder)

- scripts/lib.py (loader and metrics), scripts/raw.py (step 1, out/raw.json), scripts/pipe.py and scripts/run_pipe.sh
  (step 2, out/pipe/<arm>_<seed>.json, pipe/<arm>_<seed>/ notes.chart with its metadata redacted; the configs, song.ini and report.json were deleted for the song names they hold),
  scripts/analyze.py (steps 3-4, out/analysis.json, out/tables.md: the tables below).

## Tables (out/tables.md)

Humans (primary): fast windows 2, notes 526; peak (mean over fast windows) 16.0; song 1-s peak 17; chord share fast 0.032, song 0.063
other windows 16 (1710 notes); song notes 2236

**raw**: mean [min, max] over the arm's takes (n per arm: 4)

| measure | base | hot | dense5 | dense6 |
|---|---|---|---|---|
| fast.recall | 0.723 [0.654, 0.779] | 0.736 [0.683, 0.785] | 0.713 [0.677, 0.738] | 0.719 [0.624, 0.819] |
| fast.f1 | 0.797 [0.760, 0.826] | 0.797 [0.766, 0.828] | 0.782 [0.749, 0.798] | 0.784 [0.726, 0.831] |
| fast.ratio | 0.814 [0.721, 0.888] | 0.846 [0.760, 0.895] | 0.823 [0.808, 0.848] | 0.829 [0.719, 0.971] |
| fast.peak_c | 12.250 [10.500, 14.000] | 14.125 [12.000, 15.500] | 12.500 [11.500, 14.500] | 14.500 [10.500, 18.500] |
| fast.chord_c | 0.002 [0.000, 0.005] | 0.001 [0.000, 0.002] | 0.001 [0.000, 0.005] | 0.004 [0.000, 0.017] |
| other.recall | 0.821 [0.788, 0.846] | 0.814 [0.797, 0.822] | 0.827 [0.777, 0.850] | 0.824 [0.806, 0.832] |
| other.f1 | 0.795 [0.785, 0.812] | 0.784 [0.769, 0.806] | 0.788 [0.758, 0.802] | 0.788 [0.773, 0.803] |
| other.ratio | 1.065 [0.999, 1.124] | 1.075 [1.023, 1.130] | 1.098 [1.051, 1.130] | 1.092 [1.070, 1.152] |
| song.recall | 0.798 [0.767, 0.826] | 0.795 [0.784, 0.807] | 0.800 [0.754, 0.824] | 0.800 [0.783, 0.809] |
| song.f1 | 0.796 [0.789, 0.801] | 0.787 [0.780, 0.800] | 0.787 [0.756, 0.801] | 0.788 [0.773, 0.800] |
| song.f1_50 | 0.619 [0.612, 0.625] | 0.603 [0.598, 0.609] | 0.611 [0.601, 0.616] | 0.614 [0.594, 0.649] |
| song.ratio | 1.006 [0.945, 1.067] | 1.021 [0.962, 1.069] | 1.033 [0.994, 1.058] | 1.030 [0.990, 1.065] |
| song.peak1s_c | 17.750 [16.000, 22.000] | 17.500 [15.000, 19.000] | 16.250 [14.000, 19.000] | 18.000 [16.000, 21.000] |
| song.chord_c | 0.072 [0.047, 0.108] | 0.050 [0.033, 0.071] | 0.029 [0.007, 0.062] | 0.060 [0.044, 0.094] |

raw, arm minus base (exact permutation p, 70 splits); pooled within-arm SD; smallest detectable difference (50 % / 80 % power)

| measure | hot | dense5 | dense6 | pooled SD | MDD 50 % / 80 % |
|---|---|---|---|---|---|
| fast.recall | +0.013 (p 0.71) | -0.010 (p 0.80) | -0.004 (p 0.94) | 0.057 | 0.099 / 0.136 |
| fast.f1 | +0.001 (p 0.97) | -0.014 (p 0.46) | -0.012 (p 0.71) | 0.033 | 0.057 / 0.078 |
| fast.ratio | +0.031 (p 0.66) | +0.009 (p 0.86) | +0.015 (p 0.89) | 0.075 | 0.129 / 0.177 |
| fast.peak_c | +1.875 (p 0.23) | +0.250 (p 0.94) | +2.250 (p 0.37) | 2.414 | 4.177 / 5.724 |
| fast.chord_c | -0.001 (p 0.43) | -0.001 (p 0.71) | +0.002 (p 1.00) | 0.005 | 0.008 / 0.011 |
| other.recall | -0.008 (p 0.60) | +0.006 (p 0.69) | +0.003 (p 0.77) | 0.022 | 0.038 / 0.053 |
| other.f1 | -0.011 (p 0.34) | -0.007 (p 0.66) | -0.007 (p 0.51) | 0.017 | 0.029 / 0.039 |
| other.ratio | +0.011 (p 0.83) | +0.033 (p 0.34) | +0.027 (p 0.51) | 0.046 | 0.079 / 0.108 |
| song.recall | -0.003 (p 0.86) | +0.002 (p 1.00) | +0.001 (p 1.00) | 0.022 | 0.038 / 0.052 |
| song.f1 | -0.009 (p 0.17) | -0.009 (p 0.66) | -0.008 (p 0.26) | 0.013 | 0.023 / 0.031 |
| song.f1_50 | -0.016 (p 0.03) | -0.008 (p 0.26) | -0.004 (p 0.80) | 0.013 | 0.023 / 0.031 |
| song.ratio | +0.015 (p 0.77) | +0.027 (p 0.46) | +0.024 (p 0.57) | 0.045 | 0.077 / 0.106 |
| song.peak1s_c | -0.250 (p 1.00) | -1.500 (p 0.54) | +0.250 (p 1.00) | 2.389 | 4.134 / 5.665 |
| song.chord_c | -0.022 (p 0.29) | -0.043 (p 0.09) | -0.012 (p 0.49) | 0.024 | 0.042 / 0.057 |

raw, per 30-s window F1@100: base mean, arm minus base, pooled SD, MDD50

| window start s | fast | human notes | base | hot | dense5 | dense6 | pooled SD | MDD50 |
|---|---|---|---|---|---|---|---|---|
| 6 |  | 83 | 0.927 | -0.031 | -0.028 | -0.003 | 0.043 | 0.074 |
| 36 |  | 74 | 0.920 | -0.029 | +0.007 | +0.021 | 0.051 | 0.089 |
| 66 |  | 54 | 0.851 | -0.052 | -0.011 | -0.014 | 0.054 | 0.093 |
| 96 |  | 77 | 0.697 | +0.134 | +0.212 | +0.109 | 0.186 | 0.322 |
| 126 |  | 69 | 0.749 | -0.023 | +0.034 | +0.038 | 0.063 | 0.110 |
| 156 |  | 106 | 0.856 | -0.030 | -0.060 | -0.022 | 0.059 | 0.102 |
| 186 |  | 132 | 0.926 | -0.010 | -0.039 | +0.004 | 0.045 | 0.078 |
| 216 |  | 99 | 0.739 | +0.019 | +0.008 | -0.016 | 0.030 | 0.051 |
| 246 |  | 94 | 0.564 | +0.039 | -0.004 | -0.004 | 0.035 | 0.061 |
| 276 | yes | 256 | 0.742 | +0.008 | -0.036 | -0.002 | 0.048 | 0.084 |
| 306 |  | 157 | 0.719 | -0.042 | -0.002 | -0.006 | 0.038 | 0.066 |
| 336 |  | 185 | 0.786 | -0.022 | -0.003 | +0.024 | 0.048 | 0.083 |
| 366 |  | 145 | 0.939 | +0.011 | -0.066 | -0.045 | 0.092 | 0.159 |
| 396 |  | 108 | 0.792 | +0.004 | -0.018 | -0.058 | 0.023 | 0.040 |
| 426 |  | 101 | 0.766 | -0.009 | -0.022 | -0.014 | 0.034 | 0.060 |
| 456 |  | 132 | 0.746 | -0.044 | +0.004 | -0.035 | 0.020 | 0.034 |
| 486 | yes | 270 | 0.841 | -0.006 | +0.002 | -0.024 | 0.038 | 0.066 |
| 516 |  | 94 | 0.708 | -0.032 | -0.014 | -0.007 | 0.033 | 0.057 |

hot: windows down > 0.02: 9 (of them p < 0.05: 1), worst -0.052; dense5: windows down > 0.02: 6 (of them p < 0.05: 0), worst -0.066; dense6: windows down > 0.02: 5 (of them p < 0.05: 1), worst -0.058
median window MDD50 0.076, min 0.034

**pipe**: mean [min, max] over the arm's takes (n per arm: 4)

| measure | base | hot | dense5 | dense6 |
|---|---|---|---|---|
| fast.recall | 0.700 [0.641, 0.732] | 0.696 [0.665, 0.724] | 0.693 [0.669, 0.705] | 0.679 [0.622, 0.772] |
| fast.f1 | 0.785 [0.751, 0.806] | 0.779 [0.753, 0.797] | 0.773 [0.749, 0.783] | 0.765 [0.724, 0.820] |
| fast.ratio | 0.782 [0.707, 0.837] | 0.787 [0.743, 0.821] | 0.793 [0.783, 0.808] | 0.770 [0.696, 0.882] |
| fast.peak_c | 10.500 [9.500, 11.000] | 10.625 [10.000, 11.000] | 10.125 [9.500, 11.000] | 10.250 [9.500, 11.000] |
| fast.chord_c | 0.002 [0.000, 0.005] | 0.001 [0.000, 0.002] | 0.001 [0.000, 0.002] | 0.005 [0.000, 0.019] |
| other.recall | 0.813 [0.779, 0.837] | 0.800 [0.777, 0.812] | 0.814 [0.768, 0.837] | 0.808 [0.781, 0.819] |
| other.f1 | 0.795 [0.785, 0.807] | 0.784 [0.765, 0.804] | 0.786 [0.755, 0.803] | 0.785 [0.771, 0.799] |
| other.ratio | 1.046 [0.985, 1.090] | 1.040 [1.019, 1.077] | 1.071 [1.035, 1.123] | 1.059 [1.015, 1.125] |
| song.recall | 0.786 [0.760, 0.811] | 0.775 [0.765, 0.788] | 0.785 [0.745, 0.806] | 0.778 [0.772, 0.787] |
| song.f1 | 0.793 [0.786, 0.799] | 0.783 [0.772, 0.797] | 0.783 [0.753, 0.798] | 0.781 [0.765, 0.792] |
| song.f1_50 | 0.703 [0.693, 0.710] | 0.690 [0.680, 0.700] | 0.699 [0.694, 0.703] | 0.694 [0.678, 0.704] |
| song.ratio | 0.984 [0.934, 1.030] | 0.980 [0.954, 1.015] | 1.006 [0.977, 1.049] | 0.991 [0.970, 1.024] |
| song.peak1s_c | 11.000 [11.000, 11.000] | 11.000 [11.000, 11.000] | 11.000 [11.000, 11.000] | 11.000 [11.000, 11.000] |
| song.chord_c | 0.071 [0.043, 0.106] | 0.051 [0.034, 0.074] | 0.030 [0.006, 0.065] | 0.061 [0.042, 0.097] |

pipe, arm minus base (exact permutation p, 70 splits); pooled within-arm SD; smallest detectable difference (50 % / 80 % power)

| measure | hot | dense5 | dense6 | pooled SD | MDD 50 % / 80 % |
|---|---|---|---|---|---|
| fast.recall | -0.004 (p 0.86) | -0.006 (p 0.89) | -0.021 (p 0.63) | 0.045 | 0.078 / 0.107 |
| fast.f1 | -0.006 (p 0.77) | -0.011 (p 0.40) | -0.020 (p 0.49) | 0.028 | 0.049 / 0.067 |
| fast.ratio | +0.005 (p 0.94) | +0.011 (p 0.80) | -0.011 (p 0.86) | 0.054 | 0.094 / 0.129 |
| fast.peak_c | +0.125 (p 1.00) | -0.375 (p 0.74) | -0.250 (p 0.83) | 0.654 | 1.131 / 1.549 |
| fast.chord_c | -0.001 (p 0.43) | -0.001 (p 0.43) | +0.003 (p 1.00) | 0.005 | 0.009 / 0.012 |
| other.recall | -0.013 (p 0.34) | +0.001 (p 0.91) | -0.005 (p 0.77) | 0.023 | 0.041 / 0.056 |
| other.f1 | -0.011 (p 0.34) | -0.009 (p 0.57) | -0.009 (p 0.34) | 0.016 | 0.028 / 0.038 |
| other.ratio | -0.006 (p 0.80) | +0.026 (p 0.46) | +0.013 (p 0.80) | 0.042 | 0.072 / 0.099 |
| song.recall | -0.011 (p 0.43) | -0.001 (p 0.97) | -0.008 (p 0.51) | 0.019 | 0.034 / 0.046 |
| song.f1 | -0.010 (p 0.17) | -0.010 (p 0.54) | -0.011 (p 0.11) | 0.013 | 0.023 / 0.031 |
| song.f1_50 | -0.013 (p 0.06) | -0.004 (p 0.49) | -0.009 (p 0.23) | 0.008 | 0.015 / 0.020 |
| song.ratio | -0.003 (p 0.91) | +0.022 (p 0.46) | +0.007 (p 0.91) | 0.035 | 0.060 / 0.082 |
| song.peak1s_c | +0.000 (p 1.00) | +0.000 (p 1.00) | +0.000 (p 1.00) | 0.000 | - / - |
| song.chord_c | -0.020 (p 0.26) | -0.041 (p 0.11) | -0.010 (p 0.57) | 0.025 | 0.043 / 0.059 |

pipe, per 30-s window F1@100: base mean, arm minus base, pooled SD, MDD50

| window start s | fast | human notes | base | hot | dense5 | dense6 | pooled SD | MDD50 |
|---|---|---|---|---|---|---|---|---|
| 6 |  | 83 | 0.932 | -0.026 | -0.033 | -0.003 | 0.038 | 0.066 |
| 36 |  | 74 | 0.926 | -0.019 | +0.001 | +0.017 | 0.041 | 0.072 |
| 66 |  | 54 | 0.841 | -0.049 | -0.017 | -0.023 | 0.052 | 0.090 |
| 96 |  | 77 | 0.703 | +0.146 | +0.207 | +0.109 | 0.188 | 0.326 |
| 126 |  | 69 | 0.754 | -0.029 | +0.030 | +0.031 | 0.060 | 0.105 |
| 156 |  | 106 | 0.856 | -0.018 | -0.060 | -0.022 | 0.057 | 0.098 |
| 186 |  | 132 | 0.933 | -0.009 | -0.040 | +0.005 | 0.044 | 0.076 |
| 216 |  | 99 | 0.753 | +0.011 | +0.008 | -0.023 | 0.029 | 0.051 |
| 246 |  | 94 | 0.564 | +0.015 | -0.006 | -0.015 | 0.036 | 0.062 |
| 276 | yes | 256 | 0.742 | +0.001 | -0.033 | -0.005 | 0.045 | 0.078 |
| 306 |  | 157 | 0.708 | -0.035 | +0.001 | -0.003 | 0.034 | 0.059 |
| 336 |  | 185 | 0.756 | -0.021 | -0.013 | +0.007 | 0.039 | 0.067 |
| 366 |  | 145 | 0.939 | +0.011 | -0.065 | -0.045 | 0.092 | 0.159 |
| 396 |  | 108 | 0.792 | -0.002 | -0.014 | -0.054 | 0.022 | 0.039 |
| 426 |  | 101 | 0.769 | -0.005 | -0.017 | -0.012 | 0.028 | 0.048 |
| 456 |  | 132 | 0.751 | -0.042 | -0.003 | -0.029 | 0.020 | 0.035 |
| 486 | yes | 270 | 0.821 | -0.013 | +0.005 | -0.035 | 0.036 | 0.062 |
| 516 |  | 94 | 0.711 | -0.032 | -0.015 | -0.003 | 0.031 | 0.054 |

hot: windows down > 0.02: 7 (of them p < 0.05: 1), worst -0.049; dense5: windows down > 0.02: 5 (of them p < 0.05: 0), worst -0.065; dense6: windows down > 0.02: 7 (of them p < 0.05: 1), worst -0.054
median window MDD50 0.067, min 0.035

**Cost** (summary.json): tokens, generation s, wall s: mean [min, max]

- base: tokens 6663 [6218, 6980]; generation s 570 [487, 646]; wall s 584 [491, 693]; transcriber ['cuda']; T 0.95, speed None
- hot: tokens 6724 [6257, 6985]; generation s 572 [495, 624]; wall s 574 [498, 626]; transcriber ['cuda']; T 1.05, speed None
- dense5: tokens 6861 [6514, 7035]; generation s 1150 [1042, 1201]; wall s 1152 [1045, 1203]; transcriber ['cuda']; T 0.95, speed 5
- dense6: tokens 6858 [6715, 7090]; generation s 1151 [1088, 1230]; wall s 1153 [1091, 1233]; transcriber ['cuda']; T 0.95, speed 6

**Timing bias** (best F1@50 shift, ms; F1@50 at 0 -> at best; fast recall@100 shifted)

- raw base: shifts [-60, -60, -60, -60]; F1@50 0.619 -> 0.769; fast recall@100 shifted 0.727, fast F1@100 shifted 0.802
- raw hot: shifts [-60, -60, -55, -60]; F1@50 0.603 -> 0.759; fast recall@100 shifted 0.740, fast F1@100 shifted 0.802
- raw dense5: shifts [-55, -60, -60, -55]; F1@50 0.611 -> 0.759; fast recall@100 shifted 0.715, fast F1@100 shifted 0.786
- raw dense6: shifts [-60, -55, -40, -55]; F1@50 0.614 -> 0.760; fast recall@100 shifted 0.718, fast F1@100 shifted 0.784
- pipe base: shifts [-20, -55, -70, -15]; F1@50 0.703 -> 0.765; fast recall@100 shifted 0.705, fast F1@100 shifted 0.792
- pipe hot: shifts [-15, -70, -50, -70]; F1@50 0.690 -> 0.755; fast recall@100 shifted 0.699, fast F1@100 shifted 0.783
- pipe dense5: shifts [-45, -45, -40, -55]; F1@50 0.699 -> 0.754; fast recall@100 shifted 0.696, fast F1@100 shifted 0.777
- pipe dense6: shifts [-50, -45, -15, -20]; F1@50 0.694 -> 0.755; fast recall@100 shifted 0.681, fast F1@100 shifted 0.768

## The advisor's reading (a different model, before the result was recorded)

**The conclusion stands, with changes.** The numbers reproduce from the per-take files (arm means, the exact
permutation p-values, 16 of 16 takes, the same input, 2 fast windows and 526 human notes each); the scripts treat no
arm differently. The 95 % upper bound on a raw gain is about +0.06, so +0.10 is excluded on this song.

- **The piped half could not reach the bar whatever the engine does:** sooth's halved grid caps piped fast recall at
  0.812 (M8-ceiling) and the piped 1-s peak is 11 on all 16 takes, so only the raw comparison says anything about the
  engine.
- **Not "dead end" but "refuted at +0.10 on sooth":** smaller effects, other songs and each arm's four takes spliced
  are untested (the order asked for the splice and for both human charts; alt1 is rightly left out, the splice was
  not done).
- **The timing shift is its own finding:** the raw takes sit a near-constant 55-60 ms from the human chart in every
  arm (fair between arms; it costs 0.005 at F1@100), and the piped charts' best shift varies from -15 to -70 ms within
  one arm, which matters to any F1@50 gate. To be checked on a second song: sooth has one usable chart.
- **The cheapest next step, no GPU:** M8-ceiling's slots rule on these 16 takes through the pipeline, to see what
  survives once the cap is lifted.

**The orchestrator's note:** raw fast recall is 0.723 and piped 0.700, so lifting the cap can add at most about 0.02
of recall on this song: the engine's raw notes agree with the human's on 72 % of them, and the rest of the gap is
not the grid's. What the cap does change is the peak density a player sees (11 notes a second against the human's 17
and the raw takes' 14-22). That is a question for a player's hands more than for F1: a slots-rule chart of this song
played against today's is M9's first experiment.
