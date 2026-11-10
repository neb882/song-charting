# The quantizer's ceiling in fast runs, and the scorer's alignment drift (measurer, 2026-11-09)

## Verdicts

**Part 1: the cap binds, unevenly.** Each human chart's Expert guitar was put through `quantize_part` with the guitar's rules
on our grid. In part D's fast windows it keeps **0.837** of its own onsets at 100 ms (song mean over 10 songs; 0.865
note-pooled), against 0.947 outside them (note-pooled). That is the ceiling part D's GPU m05 recall of **0.659** sits under:
0.659 is 0.79 of it. The cap costs most where our grid's 16th rate is under or near the window's 8 notes a second:
creep 0.675 (92 BPM, 6.2 slots a second), s08 0.658 (111 BPM), s09 0.705 (101 BPM), sooth 0.812 (halved, 77 BPM, 10.3 a
second) and s07 0.827. On the 200 BPM songs it costs little: pm2 0.938, troop 0.922, s10 0.909, s06 0.951, s01 0.976. With 6
straight slots a beat inside runs (x2 on a halved grid) the ceiling is 0.946, and with 8 it is 0.967 (song mean; note-pooled
0.930 and 0.956). So a slots rule would free about 0.11-0.13 of the fast notes, and would bring creep, sooth, s07 and s09 to
0.86-1.00. s08 stays at 0.80 even with 8 slots, and is 0.89 outside the fast windows too: the loss there is more than slots.
On D's own numbers the engine is further from the ceiling than the ceiling is from 1 on most songs, and its gap is largest on
s01 and s10 (0.52 and 0.57 of the ceiling), where the cap barely binds. The cap explains part of the fast-run shortfall, not
all of it. Our pm2/troop peaks of 13.8-14.0 are at the 200 BPM 16th cap (13.3 a second): there, any denser engine setting
the thinning spike tries cannot show more than about 0.94 of the humans' notes through the pipeline.

**Part 2: mostly drift.** Of the 25 badly aligned charts, the 40-window fit classes **11 as drift** (a line, 460-3,260
ppm, most of them 880-1,460 ppm), **3 as another edit**, **8 as unclear** (no audio match: 0-2 windows at ncc 0.3) and **3 as constant**.
The 3 constant ones were flagged only by score.py's 9-window MAD or window count: s06 alt1 and alt2 have ±7 ms window jitter, and
s07 alt3 has 7 good windows. Of the 3 edits, sooth alt1 has two lag steps of +28 and -44 ms and s03 alt1 scatters over only 6 good windows
(its F1@50 is 0.988, so in practice it is aligned). s04 alt4's 6 good windows are lags tens of seconds apart, which is chance
peaks, so it is unclear in substance. A lag line (a + b·t) lifts our m05 chart's F1@50 on the 11 drift charts from 0.39-0.76 to 0.73-0.96. It
lifts the humans' F1@50 on the same pairs from 0.38-0.87 to 0.81-0.99.
- **Exclusions (guitar, 0.6):** s12 leaves the exclusion (0.383 to 0.811: its one alternative drifts by 1,120 ppm).
  s02 (0.499: one alternative, constant lag), s04 (0.250: none of its 4 alternatives matches our audio) and s06 (0.585:
  2 constant, 1 unclear) stay excluded; the line does not touch them. No other song crosses 0.6 either way.
- **Part D's verdict:** reproduced exactly with the constant lag (0.659 song mean, 0.700 note-pooled). With the line on the
  drift charts it becomes **0.660** (0.701 note-pooled), and 5 songs stay under 0.6. Recall at 100 ms in 8-a-second
  windows hardly sees a misalignment of up to about 150 ms, because a neighbouring note is within 100 ms. So D's verdict stands, and
  so does the doubt about its metric's sensitivity.

## How it was computed

- **Alignment** (scripts/a_align.py): score.py's `align` in process. The candidate is our v0.5.0 golden song folder with
  every audio file summed, as score.py's `--cand` does. Our m05 charts' tempo maps equal the v0.5.0 charts' on all 23 songs
  (SyncTrack compared), so the frame is the same. It is run with 9 windows (score.py's) and with 40 (the same function,
  `n_win=40`). The 25 charts part D flagged (ncc 0.3 in 4.5 or fewer of 9 windows, or MAD 2 ms or more) come out the same 25.
  A first pass against song.ogg alone (the backing track without the stems) gave other numbers and was discarded.
- **Part 1** (scripts/p1_ceiling.py): human onsets go into our audio's frame by the chart's constant lag, and become
  TimedNotes (one per tick, the frets' union, sustains and taps kept, HOPO left to our grid). They go through `quantize_part`
  on our chart's tempo map with the lead-in pad, the guitar's rules (`HOPO_RULES["forced"]`, `_halved_slots` on a halved
  grid, `run_chord_s` 0.12) and the offset measured and applied as `assemble._offset` does on `offset_map`. Then they are
  moved back and matched at 100 ms to the unquantized onsets, with part D's windows and fast rule. The variants patch
  `SnapGrid.from_ticks` in memory only: a non-triplet beat holding an onset of a fast run (`quantize.fast_runs`, 8 onsets
  at most 0.125 s apart: the tap rule's run) gets 6 or 8 straight slots (12 or 16 on sooth's halved grid). Nothing in the
  repository was changed.
- **Part 2** (scripts/p2_drift.py): a Theil-Sen line through the windows at ncc 0.3 or more (40-window run). The classes:
  - constant: 80 % of those windows within 20 ms of the line, and the line moves under 20 ms over the span;
  - drift: the same fit, but the line moves 20 ms or more;
  - edit: 2 or more lag steps (contiguous runs within 20 ms) covering 80 %, or 6 or more good windows that fit neither a
    line nor steps;
  - unclear: fewer than 4 good windows, or 4-5 that fit neither.

  The 20 ms tolerance is my choice: with 5 ms, the well-aligned charts' ±7-17 ms window jitter read as steps. F1@50 (score.py's
  match, prf and n_cand_eff, Expert guitar) is then computed with the constant lag and with the line, the drift pairs only.
  The humans' pairs are the alternative's input.wav against the primary's, as `eval/stress.py score` does them.
- scripts/s_summary.py prints the tables below. scripts/cl.py is the shared loader (labels as m2lib maps them).

## Caveats

- 10 songs in part 1. creep and s01 have 1 chart with fast windows each, and s01's only one is alt2, whose alignment is
  unclear (no audio match). The ceiling assumes the human onsets meet our grid at the constant lag. On the drift charts,
  that places notes up to about 150 ms off our beats locally, which costs a few slots' worth of placement.
- The ceiling is quantize_part only: not the take splicing, the run-chord or tap rules' effect on onsets (none), the lower
  levels or the gate. It does not ask whether 6 or 8 slots would give playable or sensible charts, or what they would add on
  ordinary songs (the engine's own off-grid onsets would also gain slots).
- 9 windows (score.py's own) are too few to classify. 9-window and 40-window classes agree on the clear drift cases, but
  the 9-window fit calls s06 alt1 and alt2 drift (-38 ppm) and leaves s01 alt3 and s07 alt2 unclear. s01 alt3 is drift
  on our audio and edit on the humans' pair (15 and 14 good windows of 33-34), so it is borderline.
- The lag line was applied only to charts classed drift. The edit and unclear charts keep the constant lag.

## Tables


**Part 1: recall@100 of the quantized human chart against itself, every chart (part D's rule)**

| song | grid octave | charts | fast-window notes | ceiling fast (base / 6 / 8 slots) | ceiling outside (base / 6 / 8) | D m05 recall fast | D / ceiling |
|---|---|---|---|---|---|---|---|
| creep | 1 | 1 | 268 | 0.675 / 1.000 / 1.000 | 0.878 / 1.000 / 1.000 | 0.519 | 0.768 |
| pm2 | 2 | 5 | 13,320 | 0.938 / 0.978 / 0.996 | 0.970 / 0.992 / 0.994 | 0.768 | 0.818 |
| sooth | 0.5 | 2 | 1,082 | 0.812 / 0.993 / 0.999 | 0.960 / 0.999 / 0.999 | 0.704 | 0.867 |
| troop | 2 | 3 | 5,316 | 0.922 / 0.964 / 0.998 | 0.983 / 0.998 / 0.998 | 0.792 | 0.859 |
| s01 | 2 | 1 | 249 | 0.976 / 1.000 / 1.000 | 0.994 / 0.996 / 0.996 | 0.510 | 0.523 |
| s06 | 1 | 4 | 1,342 | 0.951 / 0.987 / 0.994 | 0.979 / 0.989 / 0.990 | 0.844 | 0.888 |
| s07 | 1 | 4 | 1,330 | 0.827 / 0.979 / 0.988 | 0.924 / 0.978 / 0.985 | 0.774 | 0.936 |
| s08 | 1 | 6 | 4,923 | 0.658 / 0.754 / 0.796 | 0.886 / 0.893 / 0.893 | 0.569 | 0.864 |
| s09 | 1 | 4 | 1,597 | 0.705 / 0.858 / 0.941 | 0.906 / 0.943 / 0.958 | 0.590 | 0.837 |
| s10 | 2 | 4 | 3,040 | 0.909 / 0.948 / 0.952 | 0.978 / 0.989 / 0.991 | 0.517 | 0.569 |

- base: song mean fast 0.837 (10 songs); note-pooled fast 0.865 (32,467 notes); note-pooled outside 0.947 (50,632 notes)
- 6: song mean fast 0.946 (10 songs); note-pooled fast 0.930 (32,467 notes); note-pooled outside 0.970 (50,632 notes)
- 8: song mean fast 0.967 (10 songs); note-pooled fast 0.956 (32,467 notes); note-pooled outside 0.973 (50,632 notes)
- part D's GPU m05 recall, same songs: song mean 0.659

**Part 1, well-aligned charts only (part D's aligned set)**

| song | grid octave | charts | fast-window notes | ceiling fast (base / 6 / 8 slots) | ceiling outside (base / 6 / 8) | D m05 recall fast | D / ceiling |
|---|---|---|---|---|---|---|---|
| creep | 1 | 1 | 268 | 0.675 / 1.000 / 1.000 | 0.878 / 1.000 / 1.000 | - | - |
| pm2 | 2 | 5 | 13,320 | 0.938 / 0.978 / 0.996 | 0.970 / 0.992 / 0.994 | - | - |
| sooth | 0.5 | 1 | 526 | 0.812 / 0.990 / 1.000 | 0.958 / 0.999 / 0.999 | - | - |
| troop | 2 | 3 | 5,316 | 0.922 / 0.964 / 0.998 | 0.983 / 0.998 / 0.998 | - | - |
| s06 | 1 | 1 | 271 | 0.993 / 0.993 / 0.993 | 0.987 / 0.989 / 0.989 | - | - |
| s07 | 1 | 2 | 788 | 0.847 / 0.974 / 0.984 | 0.928 / 0.975 / 0.982 | - | - |
| s08 | 1 | 3 | 2,346 | 0.656 / 0.756 / 0.796 | 0.882 / 0.891 / 0.891 | - | - |
| s09 | 1 | 3 | 761 | 0.712 / 0.871 / 0.947 | 0.911 / 0.952 / 0.967 | - | - |
| s10 | 2 | 1 | 660 | 0.918 / 0.991 / 1.000 | 1.000 / 1.000 / 1.000 | - | - |

- base: song mean fast 0.830 (9 songs); note-pooled fast 0.891 (24,256 notes); note-pooled outside 0.940 (25,155 notes)
- 6: song mean fast 0.946 (9 songs); note-pooled fast 0.950 (24,256 notes); note-pooled outside 0.967 (25,155 notes)
- 8: song mean fast 0.968 (9 songs); note-pooled fast 0.975 (24,256 notes); note-pooled outside 0.971 (25,155 notes)

**Part 2: the 25 badly aligned charts (part D's flag), class from the 40-window fit (9-window fit beside)**

| song | chart | class (40 win) | good windows | slope ppm | share within 20 ms of the line | 9-win class | humans' pair class | F1@50 m05 const / line | humans' F1@50 const / line |
|---|---|---|---|---|---|---|---|---|---|
| sooth | alt1 | edit (scatter) | 36 of 39 | -58 | 0.639 | drift | edit | 0.788 / - | 0.712 / - |
| s01 | alt2 | unclear (under 2 good windows) | 0 of 35 | - | - | unclear | unclear | 0.458 / - | 0.450 / - |
| s01 | alt3 | drift (a line) | 15 of 33 | -1369 | 0.800 | unclear | edit | 0.448 / 0.770 | 0.634 / - |
| s03 | alt1 | edit (scatter) | 6 of 33 | -215 | 0.667 | unclear | edit | 0.988 / - | 0.991 / - |
| s04 | alt1 | unclear (under 2 good windows) | 0 of 37 | - | - | unclear | unclear | 0.264 / - | 0.256 / - |
| s04 | alt2 | unclear (under 2 good windows) | 0 of 37 | - | - | unclear | unclear | 0.264 / - | 0.256 / - |
| s04 | alt3 | unclear (under 2 good windows) | 0 of 39 | - | - | unclear | unclear | 0.285 / - | 0.251 / - |
| s04 | alt4 | edit (scatter) | 6 of 37 | - | 0.000 | unclear | unclear | 0.222 / - | 0.237 / - |
| s05 | alt1 | drift (a line) | 35 of 37 | 1163 | 0.943 | drift | drift | 0.475 / 0.963 | 0.406 / 0.930 |
| s05 | alt5 | drift (a line) | 34 of 35 | 1163 | 0.941 | drift | drift | 0.454 / 0.934 | 0.428 / 0.948 |
| s06 | alt1 | constant (flat) | 29 of 32 | -5 | 0.897 | drift | constant | 0.763 / - | 0.868 / - |
| s06 | alt2 | constant (flat) | 29 of 32 | -5 | 0.897 | drift | constant | 0.418 / - | 0.446 / - |
| s06 | alt3 | unclear (under 2 good windows) | 1 of 35 | - | - | unclear | unclear | 0.366 / - | 0.440 / - |
| s07 | alt2 | drift (a line) | 10 of 35 | -3261 | 0.900 | unclear | drift | 0.601 / 0.878 | 0.679 / 0.924 |
| s07 | alt3 | constant (flat) | 7 of 35 | -51 | 1.000 | unclear | constant | 0.876 / - | 0.927 / - |
| s08 | alt2 | unclear (under 2 good windows) | 1 of 35 | - | - | unclear | unclear | 0.442 / - | 0.491 / - |
| s08 | alt3 | drift (a line) | 28 of 34 | -1463 | 0.929 | drift | drift | 0.522 / 0.788 | 0.670 / 0.957 |
| s08 | alt4 | unclear (2 good windows) | 2 of 34 | - | 1.000 | unclear | unclear | 0.446 / - | 0.532 / - |
| s09 | alt1 | drift (a line) | 32 of 33 | 1093 | 1.000 | drift | drift | 0.533 / 0.727 | 0.600 / 0.847 |
| s10 | alt1 | drift (a line) | 19 of 34 | -1234 | 1.000 | drift | drift | 0.574 / 0.805 | 0.778 / 0.888 |
| s10 | alt2 | unclear (under 2 good windows) | 1 of 38 | - | - | unclear | unclear | 0.397 / - | 0.408 / - |
| s10 | alt3 | drift (a line) | 25 of 33 | 881 | 1.000 | drift | drift | 0.757 / 0.848 | 0.874 / 0.980 |
| s11 | alt2 | drift (a line) | 38 of 38 | 461 | 0.842 | drift | drift | 0.585 / 0.858 | 0.630 / 0.986 |
| s11 | alt3 | drift (a line) | 36 of 36 | 1109 | 0.917 | drift | drift | 0.390 / 0.809 | 0.457 / 0.962 |
| s12 | alt1 | drift (a line) | 34 of 35 | 1123 | 0.941 | drift | drift | 0.411 / 0.770 | 0.383 / 0.811 |

- counts (40-window class): {'edit': 3, 'unclear': 8, 'drift': 11, 'constant': 3}
- the 19 well-aligned alternative charts beside them: {'constant': 19}; primaries: {'constant': 23, 'drift': 0, 'edit': 0, 'unclear': 0}

**Humans' agreement (guitar Expert F1@50, alternative against primary, mean over a song's alternatives)**

| song | alternatives | constant lag | lag line for the drift pairs | under 0.6 const / line |
|---|---|---|---|---|
| break | 1 | 0.951 | 0.951 | no / no |
| pm2 | 4 | 0.943 | 0.943 | no / no |
| sooth | 1 | 0.712 | 0.712 | no / no |
| troop | 2 | 0.921 | 0.921 | no / no |
| s01 | 3 | 0.685 | 0.685 | no / no |
| s02 (excluded) | 1 | 0.499 | 0.499 | yes / yes |
| s03 | 1 | 0.991 | 0.991 | no / no |
| s04 (excluded) | 4 | 0.250 | 0.250 | yes / yes |
| s05 | 5 | 0.739 | 0.948 | no / no |
| s06 (excluded) | 3 | 0.585 | 0.585 | yes / yes |
| s07 | 3 | 0.843 | 0.924 | no / no |
| s08 | 5 | 0.730 | 0.787 | no / no |
| s09 | 3 | 0.797 | 0.879 | no / no |
| s10 | 3 | 0.687 | 0.758 | no / no |
| s11 | 3 | 0.696 | 0.983 | no / no |
| s12 (excluded) | 1 | 0.383 | 0.811 | yes / no |
| s13 | 1 | 0.887 | 0.887 | no / no |

**Part D's rate8 recall@100, GPU m05, constant lag against the lag line for the drift charts**

| song | recall const (D's rule) | recall line | part D's |
|---|---|---|---|
| creep | 0.519 | 0.519 | 0.519 |
| pm2 | 0.768 | 0.768 | 0.768 |
| sooth | 0.704 | 0.704 | 0.704 |
| troop | 0.792 | 0.792 | 0.792 |
| s01 | 0.510 | 0.510 | 0.510 |
| s06 | 0.844 | 0.844 | 0.844 |
| s07 | 0.774 | 0.776 | 0.774 |
| s08 | 0.569 | 0.573 | 0.569 |
| s09 | 0.590 | 0.592 | 0.590 |
| s10 | 0.517 | 0.518 | 0.517 |

- song mean: const 0.659, line 0.660; note-pooled: const 0.700, line 0.701; songs under 0.6: const 5, line 5

**Part 1 per chart** (kept@100: recall of the quantized chart against itself)

| song | chart | aligned | offset applied ms | fast notes | kept@100 fast base / 6 / 8 | outside notes | kept@100 outside base / 6 / 8 |
|---|---|---|---|---|---|---|---|
| creep | primary | yes | 0.090 | 268 | 0.675 / 1.000 / 1.000 | 613 | 0.878 / 1.000 / 1.000 |
| pm2 | primary | yes | -7.697 | 2,327 | 0.953 / 0.991 / 0.999 | 1,266 | 0.980 / 0.999 / 0.999 |
| pm2 | alt1 | yes | -3.969 | 3,240 | 0.923 / 0.963 / 0.990 | 713 | 0.921 / 0.966 / 0.971 |
| pm2 | alt2 | yes | -8.794 | 2,347 | 0.946 / 0.983 / 0.997 | 1,252 | 0.990 / 0.998 / 1.000 |
| pm2 | alt3 | yes | -11.192 | 2,786 | 0.915 / 0.972 / 0.999 | 1,199 | 0.965 / 0.997 / 1.000 |
| pm2 | alt4 | yes | -35.343 | 2,620 | 0.954 / 0.980 / 0.995 | 1,117 | 0.993 / 1.000 / 1.000 |
| sooth | primary | yes | -34.678 | 526 | 0.812 / 0.990 / 1.000 | 1,710 | 0.958 / 0.999 / 0.999 |
| sooth | alt1 | no | 3.033 | 556 | 0.813 / 0.996 / 0.998 | 1,826 | 0.962 / 0.999 / 0.999 |
| troop | primary | yes | -1.450 | 1,842 | 0.927 / 0.967 / 1.000 | 771 | 0.992 / 1.000 / 1.000 |
| troop | alt1 | yes | -2.024 | 1,558 | 0.912 / 0.951 / 0.996 | 937 | 0.977 / 0.998 / 0.998 |
| troop | alt2 | yes | 6.728 | 1,916 | 0.928 / 0.974 / 0.999 | 762 | 0.979 / 0.996 / 0.997 |
| s01 | primary | yes | 0.000 | 0 | - / - / - | 1,539 | 0.992 / 0.993 / 0.993 |
| s01 | alt1 | yes | 0.000 | 0 | - / - / - | 1,527 | 0.999 / 1.000 / 1.000 |
| s01 | alt2 | no | 0.000 | 249 | 0.976 / 1.000 / 1.000 | 1,428 | 0.995 / 1.000 / 1.000 |
| s01 | alt3 | no | -13.439 | 0 | - / - / - | 1,541 | 0.989 / 0.990 / 0.990 |
| s06 | primary | yes | -0.589 | 271 | 0.993 / 0.993 / 0.993 | 2,017 | 0.987 / 0.989 / 0.989 |
| s06 | alt1 | no | -5.810 | 285 | 0.961 / 1.000 / 1.000 | 2,315 | 0.988 / 0.995 / 0.995 |
| s06 | alt2 | no | 0.000 | 288 | 0.931 / 1.000 / 1.000 | 2,106 | 0.979 / 0.989 / 0.989 |
| s06 | alt3 | no | 0.000 | 498 | 0.918 / 0.956 / 0.984 | 2,727 | 0.963 / 0.984 / 0.985 |
| s07 | primary | yes | 2.427 | 510 | 0.863 / 0.955 / 0.975 | 1,411 | 0.938 / 0.982 / 0.992 |
| s07 | alt1 | yes | -7.039 | 278 | 0.831 / 0.993 / 0.993 | 1,624 | 0.918 / 0.969 / 0.971 |
| s07 | alt2 | no | 0.000 | 277 | 0.805 / 0.989 / 0.989 | 1,638 | 0.920 / 0.984 / 0.990 |
| s07 | alt3 | no | -3.682 | 265 | 0.808 / 0.977 / 0.996 | 1,623 | 0.918 / 0.978 / 0.989 |
| s08 | primary | yes | 7.877 | 606 | 0.649 / 0.759 / 0.802 | 1,540 | 0.866 / 0.879 / 0.880 |
| s08 | alt1 | yes | 9.532 | 878 | 0.654 / 0.747 / 0.795 | 1,296 | 0.890 / 0.897 / 0.897 |
| s08 | alt2 | no | 0.000 | 856 | 0.657 / 0.741 / 0.792 | 1,207 | 0.888 / 0.888 / 0.888 |
| s08 | alt3 | no | 0.000 | 867 | 0.663 / 0.744 / 0.782 | 1,347 | 0.891 / 0.898 / 0.898 |
| s08 | alt4 | no | 0.000 | 854 | 0.664 / 0.772 / 0.815 | 1,293 | 0.890 / 0.897 / 0.897 |
| s08 | alt5 | yes | -13.225 | 862 | 0.665 / 0.761 / 0.790 | 1,336 | 0.891 / 0.896 / 0.896 |
| s09 | primary | yes | 2.416 | 248 | 0.718 / 0.911 / 0.972 | 1,526 | 0.930 / 0.963 / 0.974 |
| s09 | alt1 | no | 36.362 | 836 | 0.683 / 0.818 / 0.923 | 1,334 | 0.891 / 0.916 / 0.933 |
| s09 | alt2 | yes | 4.614 | 263 | 0.703 / 0.875 / 0.962 | 1,677 | 0.904 / 0.952 / 0.974 |
| s09 | alt3 | yes | -4.531 | 250 | 0.716 / 0.828 / 0.908 | 1,664 | 0.899 / 0.940 / 0.953 |
| s10 | primary | yes | 0.085 | 660 | 0.918 / 0.991 / 1.000 | 724 | 1.000 / 1.000 / 1.000 |
| s10 | alt1 | no | 0.000 | 308 | 1.000 / 1.000 / 1.000 | 947 | 0.978 / 0.993 / 0.995 |
| s10 | alt2 | no | 0.000 | 1,210 | 0.772 / 0.804 / 0.810 | 563 | 0.933 / 0.964 / 0.970 |
| s10 | alt3 | no | -6.135 | 862 | 0.945 / 0.999 / 1.000 | 516 | 1.000 / 1.000 / 1.000 |

## Files

- scripts/cl.py, a_align.py, p1_ceiling.py, p2_drift.py, s_summary.py (run in that order; the working data in <shm>/ceiling was deleted at the end).
