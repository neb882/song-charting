# Several takes against human charts: does the splice beat one take?

2026-11-02. songcharter at `aaab63c` (stable worktree `/tmp/claude-0/-home-user/5307d417-c453-5e74-8f13-b43b2df06ab1/scratchpad/wt/exp-takes`). `takes.splice` and `MARGIN` 0.05 are unchanged. Scores are Expert guitar from score.py, F1 at 50 ms unless named, on the six songs with human charts. The test song is compared with the delivered v1 chart.

## Answer

- **Four takes spliced beat the base take, by a little.** SPL-A is the base (seed 20260609) plus seeds 101, 202 and 303, spliced on allin1's sections.
  - SPL-A minus the base alone (S1): **+0.013 F1@50 on the five songs without Lucretia, bootstrap 95% CI [+0.003, +0.024]**. Per song it runs from +0.000 to +0.027, with no loss outside Lucretia.
  - Lucretia: −0.016. All six songs: +0.009 [−0.004, +0.020].
  - Wilcoxon p = 0.125. That is the smallest p four non-zero differences can give (Creep's difference is exactly 0).
  - **Six songs give a wide and fragile interval.** A percentile bootstrap over five values is anti-conservative: trust its direction, not its size.
- **The gain is robustness, not a better typical take.** As an extra check beyond the brief, I rebuilt SPL-A with each of the four seeds as the base in turn.
  - The splice beats the take it starts from by **+0.033 [+0.005, +0.069]** (five songs).
  - It is better in 14 of 20 song × base pairs; the worst pair is −0.019.
  - Against the best single take (an oracle no build can know), SPL-A is −0.006 [−0.014, +0.003].
  - The spread across bases falls from 0.080 to 0.025, and the worst case rises by +0.064. On Kimochi Warui the 0.600 take becomes 0.804 when spliced.
  - The gain is mostly precision: on the five songs, precision rises by +0.028 on average while recall moves by −0.003. In the windows that took another take, our onsets fell from 935 to 792 with almost the same matches (740 → 732).
- **Section quality hardly matters.**
  - Human sections (SPL-H, the oracle) beat allin1's by +0.004 [+0.000, +0.008] (four songs).
  - Plain 8-measure windows (SPL-F) beat allin1's by +0.0055 [+0.0016, +0.0092] (five songs, 4 of 5 ahead), and beat the base by +0.019 [+0.005, +0.033].
- **Three takes are worse than one, and two do nothing.**
  - SPL-3 (base + 101 + 202) minus S1: −0.017 [−0.058, +0.014]. Kimochi Warui −0.099, Creep −0.020. In its non-base windows, 5 got better and 8 got worse.
  - SPL-2 (base + 101) equals S1 by design. assemble refuses the config, and `splice()` returns the base part object itself with no windows (checked on all six songs).
- **Run time on the RTX 5070:** four takes cost 3.4× one take (2.3–4.4× per song). Over seven songs that is 1001 s for one take and 3414 s for four, about 5.7 extra minutes per song.
- **Recommendation for the any-song tool:** **4 takes (base + 3 seeds) by default when the guitar engine runs on a GPU. Otherwise 1 take, with 4 as the opt-in. Never 2 or 3.** The evidence is in the Recommendation section below.

## What was built

Each song got Expert guitar only, through `songcharter.assemble`, with no bass or drums parts.
- **Stems:** the htdemucs_6s drum stem as `drums` (for the grid) and the 6s guitar stem as `guitar`. The guitar stem is the default second grid stem and the part's own stem for trimming.
- **Settings:** `lead_in` 2.5, `take_difficulties` "expert", `offset` "auto", `hopo` "forced".
- **Metadata:** name, artist, genre and year from `eval/refs/songs.json`. That file has no album, so the album is "eval".
- **Scoring:** each built folder was scored with `/home/user/song-charting/eval/scorer/score.py`, which is identical to the worktree's copy.
- **Same grid everywhere:** every build of a song in the brief's conditions has the same `[SyncTrack]` (checked). The conditions therefore differ only in their notes.

| condition | source | takes | sections |
|---|---|---|---|
| S1–S4 | seed 20260609 / 101 / 202 / 303 | none | allin1 (note 1) |
| SPL-A | 20260609 | 101, 202, 303 | allin1, `g2/sections/runs/<id>/allin1_v310_fold0/segments.json` |
| SPL-H | 20260609 | 101, 202, 303 | the human chart's sections, `sections/<id>/human.json` |
| SPL-F | 20260609 | 101, 202, 303 | 8-measure blocks of the built grid, `sections/<id>/fixed8.json` |
| SPL-3 | 20260609 | 101, 202 | allin1 |
| SPL-2 | 20260609 | 101 | allin1; refused by assemble (note 4) |
| A_b<seed>, F_b<seed> (extra) | 101 / 202 / 303 | the other three, in seed order | allin1 / 8-measure blocks |

Notes and deviations:

1. **S1–S4 also get allin1's sections.** Without sections the gate fails with `noSections`, as the first S1 build did. A part without takes uses sections only to place phrases: take_me_out S1 with and without sections has identical notes on all four levels (checked).
2. **allin1 was available for every song**, so the fallback was never needed. I used `allin1_v310_fold0`, the sections engine's CPU default (`model="auto"` means harmonix-fold0 on the CPU), run in allin1's own Python 3.10 venv. It was the first job in batch.py. The 8-fold ensemble run (`allin1_v110_all`) was not used.
3. **SPL-H section times.**
   - Times are scan-chart's section times plus offset_check.json's `delay_applied_ms`. That delay is 0 on all six songs, because input.wav is the reference's own audio and so shares the chart's clock.
   - I did not add offset_check's `median_offset_ms` (note against onset, −16.7 to +10.9 ms). Adding it would not move any section start to another measure (checked).
   - Each section got a unique label so assemble merges none. assemble then snaps, merges and splits them as it does allin1's. No human section was under 4 measures; one (All the Small Things' last chorus) was split in two.
   - **Kimochi Warui has no SPL-H.** Its reference chart has no sections: `[Events]` holds only music_start, music_end and end. That build stopped with "not found: human.json", so SPL-H means are over 4 songs (5 with Lucretia).
4. **SPL-2 cannot be built.** `parse_config` raises "parts[0]: takes need at least two more runs (three in all) to agree on anything". On each song's real takes, `takes.splice([base, take101], sections)` returns the base `TimedPart` object itself and no windows (`analysis/spl2.json`).
5. **SPL-F blocks** start at the measure holding the first beat and are 8 measures each, one label per block. The last short block merges into the previous one under assemble's 4-measure rule.
6. **Three builds failed the gate**: creep S4, creep A_b202 and creep A_b303, all with `noteAfterAudio`.
   - Seed 303's last chord (236.34 s) has a sustain that ends at 240.41 s, past the audio's end at 240.00 s.
   - Edge trimming removes onsets but does not shorten sustains, so any build using seed 303's last window fails.
   - These builds were scored from their `<output>.failed` folders, which hold the same notes.
   - This is a gap in assemble (sustains are not clipped to the audio's end), not a takes problem. I did not fix it.
7. **Hard/Medium/Easy** can only be scored where the human chart has those levels: the four Harmonix songs. Kimochi Warui's and Drunk Drivers' references are Expert only, so the lower-tier means cover 3 songs (4 with Lucretia).

## Per song

Column notes: density is ours divided by human onsets per second; chord is the chord share of onsets, ours / human; Hard, Medium and Easy are F1@50 of our reductions of each Expert; sections is the number assemble built, which equals the number of splice windows.

### Take Me Out

| build | F1@50 | F1@100 | P@50 | R@50 | density | lane exact | lane dir | chord ours / human | Hard | Medium | Easy | sections | onsets |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| S1 base (20260609) | 0.881 | 0.888 | 0.901 | 0.863 | 0.957 | 0.185 | 0.625 | 0.445 / 0.265 | 0.805 | 0.730 | 0.530 | 12 | 858 |
| S2 (101) | 0.905 | 0.912 | 0.925 | 0.885 | 0.955 | 0.153 | 0.694 | 0.614 / 0.265 | 0.797 | 0.705 | 0.489 | 12 | 857 |
| S3 (202) | 0.913 | 0.920 | 0.939 | 0.889 | 0.946 | 0.187 | 0.723 | 0.418 / 0.265 | 0.862 | 0.773 | 0.587 | 12 | 849 |
| S4 (303) | 0.910 | 0.912 | 0.926 | 0.894 | 0.964 | 0.179 | 0.698 | 0.480 / 0.265 | 0.815 | 0.762 | 0.583 | 12 | 865 |
| SPL-A allin1 | 0.909 | 0.916 | 0.942 | 0.877 | 0.930 | 0.187 | 0.688 | 0.511 / 0.265 | 0.842 | 0.765 | 0.579 | 12 | 834 |
| SPL-H human | 0.916 | 0.923 | 0.949 | 0.885 | 0.932 | 0.181 | 0.728 | 0.482 / 0.265 | 0.841 | 0.763 | 0.576 | 14 | 836 |
| SPL-F 8 bars | 0.918 | 0.925 | 0.950 | 0.888 | 0.934 | 0.160 | 0.675 | 0.504 / 0.265 | 0.849 | 0.768 | 0.582 | 14 | 838 |
| SPL-3 | 0.909 | 0.916 | 0.940 | 0.881 | 0.935 | 0.201 | 0.649 | 0.515 / 0.265 | 0.834 | 0.757 | 0.568 | 12 | 839 |

### All the Small Things

| build | F1@50 | F1@100 | P@50 | R@50 | density | lane exact | lane dir | chord ours / human | Hard | Medium | Easy | sections | onsets |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| S1 base (20260609) | 0.971 | 0.971 | 0.944 | 1.000 | 1.057 | 0.185 | 0.704 | 0.787 / 0.766 | 0.934 | 0.971 | 0.647 | 10 | 720 |
| S2 (101) | 0.993 | 0.993 | 0.996 | 0.990 | 0.993 | 0.143 | 0.833 | 0.911 / 0.766 | 0.857 | 0.966 | 0.644 | 10 | 676 |
| S3 (202) | 0.958 | 0.958 | 0.920 | 1.000 | 1.085 | 0.097 | 0.788 | 0.441 / 0.766 | 0.933 | 0.968 | 0.644 | 10 | 739 |
| S4 (303) | 0.988 | 0.988 | 0.977 | 1.000 | 1.022 | 0.068 | 0.878 | 0.434 / 0.766 | 0.861 | 0.971 | 0.647 | 10 | 696 |
| SPL-A allin1 | 0.974 | 0.974 | 0.959 | 0.990 | 1.031 | 0.187 | 0.721 | 0.756 / 0.766 | 0.857 | 0.966 | 0.644 | 10 | 702 |
| SPL-H human | 0.974 | 0.974 | 0.959 | 0.990 | 1.031 | 0.172 | 0.721 | 0.758 / 0.766 | 0.857 | 0.966 | 0.644 | 11 | 702 |
| SPL-F 8 bars | 0.978 | 0.978 | 0.956 | 1.000 | 1.044 | 0.199 | 0.722 | 0.762 / 0.766 | 0.861 | 0.971 | 0.647 | 13 | 711 |
| SPL-3 | 0.975 | 0.975 | 0.951 | 1.000 | 1.050 | 0.185 | 0.710 | 0.750 / 0.766 | 0.860 | 0.968 | 0.644 | 10 | 715 |

### Creep

| build | F1@50 | F1@100 | P@50 | R@50 | density | lane exact | lane dir | chord ours / human | Hard | Medium | Easy | sections | onsets |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| S1 base (20260609) | 0.770 | 0.860 | 0.875 | 0.687 | 0.783 | 0.223 | 0.899 | 0.512 / 0.036 | 0.826 | 0.790 | 0.701 | 9 | 691 |
| S2 (101) | 0.728 | 0.760 | 0.917 | 0.604 | 0.657 | 0.245 | 0.766 | 0.347 / 0.036 | 0.730 | 0.698 | 0.620 | 9 | 580 |
| S3 (202) | 0.748 | 0.804 | 0.896 | 0.642 | 0.716 | 0.413 | 0.713 | 0.144 / 0.036 | 0.802 | 0.707 | 0.641 | 9 | 632 |
| S4 (303), gate failed (note 6) | 0.781 | 0.870 | 0.868 | 0.711 | 0.817 | 0.284 | 0.905 | 0.373 / 0.036 | 0.838 | 0.800 | 0.686 | 9 | 721 |
| SPL-A allin1 | 0.770 | 0.860 | 0.875 | 0.687 | 0.783 | 0.294 | 0.897 | 0.379 / 0.036 | 0.826 | 0.790 | 0.701 | 9 | 691 |
| SPL-H human | 0.770 | 0.860 | 0.875 | 0.687 | 0.783 | 0.223 | 0.899 | 0.512 / 0.036 | 0.826 | 0.790 | 0.701 | 10 | 691 |
| SPL-F 8 bars | 0.768 | 0.858 | 0.873 | 0.686 | 0.784 | 0.317 | 0.899 | 0.355 / 0.036 | 0.823 | 0.787 | 0.697 | 12 | 692 |
| SPL-3 | 0.750 | 0.831 | 0.881 | 0.653 | 0.740 | 0.239 | 0.892 | 0.464 / 0.036 | 0.811 | 0.744 | 0.684 | 9 | 653 |

### Kimochi Warui (reference is Expert only)

| build | F1@50 | F1@100 | P@50 | R@50 | density | lane exact | lane dir | chord ours / human | sections | onsets |
|---|---|---|---|---|---|---|---|---|---|---|
| S1 base (20260609) | 0.827 | 0.827 | 0.729 | 0.954 | 1.308 | 0.071 | 0.717 | 0.388 / 0.684 | 14 | 1004 |
| S2 (101) | 0.701 | 0.701 | 0.736 | 0.669 | 0.907 | 0.078 | 0.749 | 0.057 / 0.684 | 14 | 697 |
| S3 (202) | 0.600 | 0.600 | 0.490 | 0.773 | 1.576 | 0.045 | 0.508 | 0.560 / 0.684 | 14 | 1210 |
| S4 (303) | 0.724 | 0.724 | 0.604 | 0.905 | 1.498 | 0.001 | 0.646 | 0.997 / 0.684 | 14 | 1150 |
| SPL-A allin1 | 0.838 | 0.838 | 0.758 | 0.937 | 1.236 | 0.070 | 0.735 | 0.418 / 0.684 | 14 | 949 |
| SPL-H human | not built: the reference has no sections | | | | | | | | | |
| SPL-F 8 bars | 0.843 | 0.843 | 0.759 | 0.948 | 1.248 | 0.071 | 0.727 | 0.422 / 0.684 | 16 | 958 |
| SPL-3 | 0.728 | 0.728 | 0.648 | 0.829 | 1.278 | 0.083 | 0.638 | 0.285 / 0.684 | 14 | 981 |

### Drunk Drivers / Killer Whales (reference is Expert only)

| build | F1@50 | F1@100 | P@50 | R@50 | density | lane exact | lane dir | chord ours / human | sections | onsets |
|---|---|---|---|---|---|---|---|---|---|---|
| S1 base (20260609) | 0.710 | 0.713 | 0.689 | 0.731 | 1.060 | 0.124 | 0.542 | 0.315 / 0.299 | 11 | 631 |
| S2 (101) | 0.740 | 0.743 | 0.843 | 0.659 | 0.781 | 0.114 | 0.567 | 0.383 / 0.299 | 11 | 465 |
| S3 (202) | 0.739 | 0.745 | 0.768 | 0.713 | 0.928 | 0.152 | 0.659 | 0.375 / 0.299 | 11 | 552 |
| S4 (303) | 0.686 | 0.692 | 0.832 | 0.583 | 0.701 | 0.283 | 0.591 | 0.273 / 0.299 | 11 | 417 |
| SPL-A allin1 | 0.736 | 0.741 | 0.742 | 0.729 | 0.983 | 0.142 | 0.552 | 0.296 / 0.299 | 11 | 585 |
| SPL-H human | 0.745 | 0.751 | 0.772 | 0.721 | 0.934 | 0.157 | 0.549 | 0.311 / 0.299 | 13 | 556 |
| SPL-F 8 bars | 0.747 | 0.752 | 0.769 | 0.726 | 0.945 | 0.129 | 0.548 | 0.320 / 0.299 | 14 | 562 |
| SPL-3 | 0.712 | 0.715 | 0.694 | 0.731 | 1.054 | 0.121 | 0.565 | 0.322 / 0.299 | 11 | 627 |

### Lucretia (reported separately, as DESIGN §3.2 asks)

| build | F1@50 | F1@100 | P@50 | R@50 | density | lane exact | lane dir | chord ours / human | Hard | Medium | Easy | sections | onsets |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| S1 base (20260609) | 0.847 | 0.908 | 0.878 | 0.818 | 0.932 | 0.387 | 0.701 | 0.184 / 0.142 | 0.651 | 0.587 | 0.613 | 10 | 1284 |
| S2 (101) | 0.824 | 0.889 | 0.870 | 0.782 | 0.898 | 0.290 | 0.677 | 0.296 / 0.142 | 0.654 | 0.591 | 0.615 | 10 | 1238 |
| S3 (202) | 0.831 | 0.897 | 0.868 | 0.797 | 0.918 | 0.304 | 0.597 | 0.198 / 0.142 | 0.654 | 0.589 | 0.615 | 10 | 1265 |
| S4 (303) | 0.822 | 0.889 | 0.854 | 0.792 | 0.927 | 0.298 | 0.654 | 0.193 / 0.142 | 0.645 | 0.567 | 0.593 | 10 | 1278 |
| SPL-A allin1 | 0.831 | 0.894 | 0.872 | 0.794 | 0.911 | 0.346 | 0.659 | 0.213 / 0.142 | 0.653 | 0.590 | 0.611 | 10 | 1255 |
| SPL-H human | 0.831 | 0.894 | 0.873 | 0.792 | 0.907 | 0.345 | 0.647 | 0.214 / 0.142 | 0.655 | 0.593 | 0.613 | 14 | 1250 |
| SPL-F 8 bars | 0.834 | 0.897 | 0.872 | 0.800 | 0.916 | 0.356 | 0.674 | 0.205 / 0.142 | 0.652 | 0.588 | 0.611 | 12 | 1262 |
| SPL-3 | 0.832 | 0.895 | 0.873 | 0.795 | 0.910 | 0.351 | 0.653 | 0.213 / 0.142 | 0.655 | 0.593 | 0.613 | 10 | 1254 |

Why Lucretia behaves differently:
- **The grid is poor.** Our grid's beat F1 on Lucretia is 0.261 (autochart's own map scores 0.29), and the grid is 4/4 throughout, while the human chart has 17 time-signature changes.
- **Assembling costs every take 0.02–0.05 F1** against the raw take (table below).
- **Splicing then costs −0.016, all in two verse windows.** In Verse 1 and Verse 2A, seeds 202 and 303 have the highest mean agreement with the other takes (0.80, against the base's 0.75). The picked take 202 writes 154 onsets in Verse 1 against the base's 171 (the human chart has 177). Against the human chart, 202 and 303 score 0.912 and 0.894 there; the base scores 0.966.
- **This is the failure the agreement rule cannot see:** takes that share an omission outvote the one take that got it right.
- **The loss belongs to this base, not to splicing.** With each seed as the base, the splice minus its base on Lucretia is −0.016 / +0.007 / −0.001 / +0.004 (mean −0.001).

### Context: raw takes and the earlier single-take score

- **Raw takes** are the take folders exactly as autochart wrote them. They have no audio, so score.py assumes lag 0; their notes are in input.wav seconds.
- **Earlier** is `gpu_results/autochart/<id>.score.json`: an earlier GPU run with the default seed and all difficulties.

| song | earlier single take | raw 20260609 / 101 / 202 / 303 | raw seed spread | assembled S1–S4 | assembled − raw (mean) |
|---|---|---|---|---|---|
| Take Me Out | 0.880 | 0.880 / 0.910 / 0.919 / 0.911 | 0.039 | 0.881 / 0.905 / 0.913 / 0.910 | −0.003 |
| All the Small Things | 0.971 | 0.971 / 0.993 / 0.957 / 0.988 | 0.036 | 0.971 / 0.993 / 0.958 / 0.988 | +0.000 |
| Creep | 0.809 | 0.805 / 0.729 / 0.761 / 0.810 | 0.081 | 0.770 / 0.728 / 0.748 / 0.781 | −0.019 |
| Kimochi Warui | 0.813 | 0.813 / 0.683 / 0.477 / 0.710 | 0.336 | 0.827 / 0.701 / 0.600 / 0.724 | +0.042 |
| Drunk Drivers | 0.777 | 0.698 / 0.739 / 0.740 / 0.684 | 0.057 | 0.710 / 0.740 / 0.739 / 0.686 | +0.003 |
| Lucretia | 0.887 | 0.887 / 0.871 / 0.855 / 0.864 | 0.032 | 0.847 / 0.824 / 0.831 / 0.822 | −0.038 |

- On four songs, this run's 20260609 take scores exactly what the earlier run scored.
- On Drunk Drivers the earlier same-seed take scored 0.777, above all four of these takes (0.684–0.740). Takes vary between runs as well as between seeds.

## Paired differences

- **Method:** per-song differences, the mean over songs with a 10,000-resample bootstrap 95% CI (songs resampled), and a Wilcoxon signed-rank p.
- **Six songs give a wide interval.** With five songs the smallest possible two-sided Wilcoxon p is 0.0625; with four non-zero differences it is 0.125.
- **"Best single"** is the oracle: the best of S1–S4 on that song.

### F1@50

| condition | songs | − base (S1): mean [95% CI] (min, max) | Wilcoxon p | − mean of S1–S4 | − best single |
|---|---|---|---|---|---|
| SPL-A | 5, without Lucretia | **+0.013 [+0.003, +0.024]** (+0.000, +0.027) | 0.125 | +0.032 [+0.002, +0.079] | −0.006 [−0.014, +0.003] |
| SPL-A | all 6 | +0.009 [−0.004, +0.020] (−0.016, +0.027) | 0.312 | +0.026 [+0.002, +0.067] | −0.007 [−0.015, +0.001] |
| SPL-H | 4, without Lucretia | +0.018 [+0.001, +0.035] (+0.000, +0.036) | 0.250 | +0.012 [+0.001, +0.023] | −0.006 [−0.015, +0.004] |
| SPL-H | 5 | +0.011 [−0.006, +0.029] (−0.016, +0.036) | 0.375 | +0.010 [+0.000, +0.019] | −0.008 [−0.016, +0.001] |
| SPL-F | 5, without Lucretia | **+0.019 [+0.005, +0.033]** (−0.002, +0.037) | 0.125 | +0.037 [+0.008, +0.084] | −0.000 [−0.010, +0.010] |
| SPL-F | all 6 | +0.014 [−0.001, +0.028] (−0.013, +0.037) | 0.219 | +0.031 [+0.006, +0.072] | −0.002 [−0.011, +0.008] |
| SPL-3 | 5, without Lucretia | −0.017 [−0.058, +0.014] (−0.099, +0.028) | 1.000 | +0.001 [−0.006, +0.009] | −0.036 [−0.068, −0.012] |
| SPL-3 | all 6 | −0.017 [−0.052, +0.011] (−0.099, +0.028) | 0.688 | +0.001 [−0.005, +0.008] | −0.032 [−0.061, −0.013] |
| SPL-2 | all 6 | 0 by design (refused; `splice` returns the base) | | | |

SPL-H's "mean of S1–S4" and "best single" columns use only its own four or five songs, so they leave out Kimochi Warui's large seed spread.

Per song (F1@50):

| song | seed spread (max−min S1–S4) | S1 | mean S1–S4 | best single | SPL-A − S1 | SPL-A − mean | SPL-A − best | SPL-H − S1 | SPL-F − S1 | SPL-3 − S1 |
|---|---|---|---|---|---|---|---|---|---|---|
| Take Me Out | 0.032 | 0.881 | 0.902 | 0.913 | +0.027 | +0.006 | −0.005 | +0.034 | +0.037 | +0.028 |
| All the Small Things | 0.034 | 0.971 | 0.978 | 0.993 | +0.003 | −0.004 | −0.019 | +0.003 | +0.006 | +0.003 |
| Creep | 0.053 | 0.770 | 0.757 | 0.781 | +0.000 | +0.013 | −0.012 | +0.000 | −0.002 | −0.020 |
| Kimochi Warui | 0.227 | 0.827 | 0.713 | 0.827 | +0.011 | +0.125 | +0.011 | – | +0.016 | −0.099 |
| Drunk Drivers | 0.054 | 0.710 | 0.719 | 0.740 | +0.026 | +0.017 | −0.004 | +0.036 | +0.037 | +0.002 |
| Lucretia | 0.025 | 0.847 | 0.831 | 0.847 | −0.016 | +0.000 | −0.016 | −0.016 | −0.013 | −0.015 |

### Splice variants compared with each other (F1@50)

| comparison | songs | mean [95% CI] | Wilcoxon p | per song |
|---|---|---|---|---|
| SPL-H − SPL-A (human vs allin1 sections) | 4 | +0.004 [+0.000, +0.008] | 0.500 | TMO +0.007, ATST +0.000, Creep +0.000, DD +0.010 (Lucretia −0.001) |
| SPL-F − SPL-A (8 bars vs allin1) | 5 | +0.0055 [+0.0016, +0.0092] | 0.125 | TMO +0.009, ATST +0.004, Creep −0.002, KW +0.005, DD +0.011 (Lucretia +0.003) |
| SPL-F − SPL-H (8 bars vs human) | 4 | +0.0015 [−0.0007, +0.0031] | 0.375 | TMO +0.002, ATST +0.004, Creep −0.002, DD +0.001 (Lucretia +0.004) |
| SPL-A − SPL-3 (4 takes vs 3) | 5 | +0.031 [+0.003, +0.071] | 0.312 | TMO −0.001, ATST −0.001, Creep +0.020, KW +0.110, DD +0.024 (Lucretia −0.001) |

### Other metrics, SPL-A − S1 (five songs without Lucretia, then Lucretia)

| metric | mean [95% CI] | per song (TMO, ATST, Creep, KW, DD) | Lucretia |
|---|---|---|---|
| F1@100 | +0.014 [+0.003, +0.024] | | −0.014 |
| precision@50 | +0.028 | +0.041, +0.015, 0, +0.029, +0.053 | −0.006 |
| recall@50 | −0.003 | +0.014, −0.010, 0, −0.017, −0.002 | −0.024 |
| density ratio | −0.040 (toward 1 on 3 of 5, away on TMO, same on Creep) | 0.957→0.930, 1.057→1.031, 0.783→0.783, 1.308→1.236, 1.060→0.983 | 0.932→0.911 |
| lane direction | +0.021 [+0.006, +0.043] | +0.063, +0.017, −0.002, +0.017, +0.010 | −0.042 |
| exact lane | +0.018 [+0.001, +0.046] | +0.002, +0.002, +0.071, −0.001, +0.018 | −0.041 |
| chord share, ours (human) | – | 0.445→0.511 (0.265), 0.787→0.756 (0.766), 0.512→0.379 (0.036), 0.388→0.418 (0.684), 0.315→0.296 (0.299) | 0.184→0.213 (0.142) |
| Hard F1@50 (3 songs) | −0.014 [−0.078, +0.037] | +0.037, −0.078, 0.000 | +0.002 |
| Medium F1@50 (3 songs) | +0.010 [−0.005, +0.035] | +0.035, −0.005, 0.000 | +0.003 |
| Easy F1@50 (3 songs) | +0.015 [−0.003, +0.049] | +0.049, −0.003, 0.000 | −0.002 |

**The reducer, not the splice, moves Hard.** On All the Small Things, SPL-A swaps only the Bridge window (108.8–134.7 s).
- Outside the Bridge, its Expert and Medium notes are identical to S1's.
- Yet Hard drops from 600 to 513 onsets **across the whole song**: Hard F1 goes 0.932 → 0.856 before the Bridge and 0.944 → 0.880 after it.
- The cause: reduce.py's thinning ladder drops whole position classes across the song, based on Hard's share of Expert onsets. A local change to Expert can therefore flip a song-wide class.
- Lower-tier F1 differences here say little about the splice.

### Extra: each seed as the base (beyond the brief)

I rebuilt SPL-A and SPL-F with base 101, 202 and 303, using the other three as takes: 18 + 18 builds, named `A_b*` and `F_b*`. For an unseen song, the default seed's take is just one random draw, so this is the better estimate of what the splice buys.

SPL-A, F1@50:

| song | spliced, base = 20260609 / 101 / 202 / 303 | that take alone | spliced − its base | mean | range spliced / single | worst spliced − worst single |
|---|---|---|---|---|---|---|
| Take Me Out | 0.909 / 0.911 / 0.912 / 0.910 | 0.881 / 0.905 / 0.913 / 0.910 | +0.027 / +0.006 / −0.001 / +0.000 | +0.008 | 0.003 / 0.032 | +0.027 |
| All the Small Things | 0.974 / 0.973 / 0.959 / 0.987 | 0.971 / 0.993 / 0.958 / 0.988 | +0.003 / −0.019 / +0.001 / −0.002 | −0.004 | 0.028 / 0.034 | +0.001 |
| Creep | 0.770 / 0.766 / 0.780 / 0.780 | 0.770 / 0.728 / 0.748 / 0.781 | +0.000 / +0.038 / +0.032 / −0.001 | +0.017 | 0.014 / 0.053 | +0.038 |
| Kimochi Warui | 0.838 / 0.805 / 0.804 / 0.814 | 0.827 / 0.701 / 0.600 / 0.724 | +0.011 / +0.104 / +0.204 / +0.090 | +0.102 | 0.034 / 0.227 | +0.204 |
| Drunk Drivers | 0.736 / 0.782 / 0.753 / 0.768 | 0.710 / 0.740 / 0.739 / 0.686 | +0.026 / +0.042 / +0.013 / +0.082 | +0.041 | 0.046 / 0.054 | +0.050 |
| Lucretia | 0.831 / 0.830 / 0.831 / 0.826 | 0.847 / 0.824 / 0.831 / 0.822 | −0.016 / +0.007 / −0.001 / +0.004 | −0.001 | 0.006 / 0.025 | +0.004 |

- **SPL-A, without Lucretia:** mean of per-song means **+0.033 [+0.005, +0.069]**, Wilcoxon p 0.125.
  - Song × base pairs: 14 better and 4 worse of 20; the worst is −0.019.
  - Range across bases: 0.025 spliced against 0.080 single. Worst spliced minus worst single: +0.064.
  - All six songs: +0.027 [+0.003, +0.060], 16 better and 6 worse of 24.
- **SPL-F, without Lucretia:** **+0.032 [+0.007, +0.065]**, 17 better and 3 worse of 20; the worst is −0.015, and the worst case improves by +0.056. All six: +0.026 [+0.004, +0.057].
- **Lane direction is inconclusive under rotation:** SPL-A +0.027 [−0.012, +0.069], SPL-F +0.023 [−0.002, +0.049]. All the Small Things and Drunk Drivers lose lane direction with some bases (worst −0.071).

The full rotation tables, including lane direction, are in `analysis/rotation.md`.

## Windows: where the splice gained and lost

How each window was scored:
- Our onsets were compared with the human onsets inside the window's span. Spans come from report.json `parts.guitar.takes.windows`, in input seconds; each window starts 50 ms before its section.
- Matching is score.py's one-to-one matching at 50 ms, and our onsets are clipped to the reference span as score.py clips them.
- Summed over a whole song, the windows reproduce score.py's F1 (Take Me Out: 0.9087 against 0.909).
- **Oracle** takes each window from whichever single-take build (S1–S4) scores best there against the human chart.

| build | songs | windows | non-base | better / worse / same vs base | non-base windows pooled: F1 base → spliced (matched; our onsets) | mean song gain | mean oracle gain | non-base pick = human-best take | windows whose human-best take is not the base | mean Spearman (agreement vs human F1) |
|---|---|---|---|---|---|---|---|---|---|---|
| SPL-A | 5 | 56 | 12 | 7 / 2 / 3 | 0.818 → 0.878 (740 → 732 of 875; 935 → 792) | +0.013 | +0.049 | 2 of 12 | 33 of 56 | 0.29 (52) |
| SPL-A | Lucretia | 10 | 3 | 0 / 3 / 0 | 0.959 → 0.909 (382 → 349 of 406; 391 → 362) | −0.016 | +0.006 | 0 of 3 | 5 of 10 | 0.00 (10) |
| SPL-H | 4 | 48 | 15 | 10 / 2 / 3 | 0.826 → 0.895 (696 → 703 of 794; 892 → 777) | +0.018 | +0.053 | 5 of 15 | 36 of 48 | 0.33 (46) |
| SPL-H | Lucretia | 14 | 3 | 1 / 2 / 0 | 0.960 → 0.907 | −0.016 | +0.009 | 0 of 3 | 6 of 14 | 0.14 (13) |
| SPL-F | 5 | 69 | 18 | 13 / 2 / 3 | 0.814 → 0.888 (862 → 876 of 1015; 1102 → 959) | +0.019 | +0.045 | 6 of 18 | 41 of 69 | 0.25 (65) |
| SPL-F | Lucretia | 12 | 3 | 0 / 3 / 0 | 0.960 → 0.909 | −0.013 | +0.009 | 0 of 3 | 6 of 12 | 0.04 (12) |
| SPL-3 | 5 | 56 | 15 | 5 / 8 / 2 | 0.833 → 0.765 (930 → 820 of 1113; 1119 → 1030) | −0.017 | +0.038 | 5 of 15 | 29 of 56 | 0.06 (52) |
| SPL-3 | Lucretia | 10 | 3 | 1 / 2 / 0 | 0.959 → 0.913 | −0.015 | +0.006 | 1 of 3 | 5 of 10 | 0.05 (10) |

What the window table shows:
- **With four takes the rule rarely leaves the base** (12 of 56 windows). When it does, the window usually improves: 7 better, 2 worse, 3 equal. The gain is precision: the replaced windows are ones where the base wrote too many notes.
- **It seldom picks the take that is best against the human chart** (2 of 12). Agreement ranks the takes only weakly as the human chart does (mean per-window Spearman 0.29).
- A perfect per-window picker would gain +0.049, nearly four times the +0.013 achieved. **Agreement works as a safe filter, not as a good ranker.**
- **With three takes**, each take's score is a mean over only two others. Two takes that share a failure then outvote the base: 5 better, 8 worse.

SPL-A's non-base windows per song (F1 in the window against the human chart, base → spliced; the count in brackets is human onsets in the window):

- **Take Me Out (+0.027): six non-base windows.**
  - Gains: Instrumental 67.5–85.8 s, take 303, 0.908 → 0.978 (71). Verse 2 85.8–113.3 s, take 202, 0.802 → 0.920 (115). Solo 191.2–205.0 s, take 202, 0.857 → 0.970 (52).
  - Small losses: Chorus 1 43.4–67.5 s, take 101, 0.871 → 0.867 (101); take 202 would have scored 0.899. Verse 3 136.3–163.4 s, take 202, 0.921 → 0.919 (106).
  - Equal: Verse 1B, where all takes score 0.99.
  - SPL-H and SPL-F do better here (7 better and 1 worse each), because their riff and 8-bar windows isolate the base's over-written riffs.
- **All the Small Things (+0.003).**
  - Bridge 108.8–134.7 s, take 101, 0.946 → 0.963 (97). The base wrote 108 onsets there and 101 wrote 90; take 303 would have scored 1.000.
  - Intro A, take 101: unchanged at 0.990.
  - No losses. The splice stays 0.019 below the best single take (101) because the base keeps its other windows.
- **Creep (+0.000): one non-base window,** the Solo (171.0–186.4 s, take 202). Its onsets score the same (0.700). Only lanes change there: exact lane +0.071, and chord share 0.51 → 0.38 (the human chart's is 0.04). Seed 303, the best single take (0.781), was never picked.
- **Kimochi Warui (+0.011).**
  - Verse 3 144.7–176.1 s, take 202, 0.672 → 0.810 (45). The base wrote 89 onsets there; the spliced chart has 34.
  - The base was kept in the other 13 windows. The three other seeds are poor takes (0.600–0.724), which is why the splice beats even the best single take on this song.
- **Drunk Drivers (+0.026): two non-base windows near the end, both better.**
  - Chorus 2C 184.6–201.0 s, take 101, 0.324 → 0.391 (18).
  - Outro 201.0 s to the end, take 303, 0.235 → 0.519 (11). The base wrote 40 onsets where the human chart has 11.
  - The per-window oracle reaches 0.820, against 0.736 spliced. The gap is in windows where no take beat the base's agreement by 0.05.
- **Lucretia (−0.016): three non-base windows, all worse.** Verse 1 37.5–66.9 s, take 202, 0.966 → 0.912 (177). Verse 2A 91.6–116.2 s, take 202, 0.958 → 0.890 (146). Solo E 217.7 s to the end, take 101, 0.945 → 0.933 (83). See the Lucretia section above.
- **Where SPL-3 lost.**
  - Kimochi Warui, five windows. Examples: Verse 1B 0.976 → 0.574 and Break 0.827 → 0.538, both to take 202. That is the 0.600 take, which writes 1.58× the human density. In Verse 1B the three takes' agreement scores are 0.075 / 0.175 / 0.25, so "best by 0.05" is noise.
  - Creep, Chorus 1 (66.5–87.5 s): take 101, 0.684 → 0.407. Take 101 writes 26 onsets where the base writes 63 and the human chart has 92; take 202 also scores low there (0.386). With 303 also voting (SPL-A), the base is kept.

Every window's agreement scores, per-take human F1, oracle pick and rank are in `analysis/windows.json`.

## How many takes

| takes | what the splice does | F1@50 − base, 5 songs | GPU time, 7 songs (× one take) |
|---|---|---|---|
| 1 | the base alone | 0 | 1001 s (1.00) |
| 2 | nothing: refused by assemble; `splice` returns the base | 0 by design | 1663 s (1.66) for nothing |
| 3 | 2-against-1 votes; a pair sharing a failure outvotes the base | −0.017 [−0.058, +0.014]; KW −0.099 | 2674 s (2.67) |
| 4 | three others vote; the base stays unless clearly beaten | +0.013 [+0.003, +0.024]; rotation +0.033 [+0.005, +0.069] | 3414 s (3.41) |

## Test song (no human chart): GPU SPL-A against the delivered v1 chart

**How SPL-A was built:** from the four GPU takes with the same recipe as above: 6s stems, no beat hints, and allin1's `allin1_v310_fold0` sections, giving 27 windows. v1 used the ft stems, beat hints and its own fold-0 segments, giving 26 windows. The gate passed.

**The charts agree on onsets but not on lanes.**
- Median offset between them is 1.65 ms. After removing it, onset **F1@50 between v1's Expert guitar and SPL-A's is 0.900** (0.902 at 100 ms).
- Onsets: 1289 in SPL-A's built chart, 1201 in v1. The splice itself wrote 1311 onsets, against the base's 1277.
- Exact lanes agree on only 0.17 of matched onsets. Chord share: 0.66 against 0.64.

**The takes are not v1's takes.**
- Same seeds, but no take is identical. Onset F1@50 of each new GPU take against v1's take of the same seed: base 0.763 (1277 against 1139 onsets), 101 0.914, 202 0.758, 303 0.801.
- In 341.5–399 s, v1's base dropped notes (98 onsets); this run's base writes 246. Here it is seed 202 that writes nothing from 341.5 s on (v1's CPU take had 168 there).
- The splice kept the base in those windows (Solo 3C, Solo 3D, Chorus 4A; agreement for example 0.43 / 0.38 / 0.00 / 0.29), which was right.

**The two splices chose differently:**
- SPL-A leaves the base in 10 of 27 windows, covering 36 % of the song; picks per take 17 / 6 / 1 / 3.
- v1 left the base in 17 of 26, covering 66 % of the song; picks per take 9 / 8 / 4 / 5.
- Over the song's time, they agree on base-or-not 48 % of the time (chance level) and on the exact take 27 %.

| what happened in v1's sections | count | sections |
|---|---|---|
| both left the base | 7 | Chorus 1 (both chose 303); Chorus 2, Verse 4, Chorus 3A, Chorus 3B, Instrumental 2 and Solo 3A with different seeds |
| only v1 left the base | 10 | Verse 1A, Verse 1B, Bridge B, Verse 3, Solo 2, Solo 3B–3E, Chorus 4 (mostly the 340–400 s stretch, where v1's base was the broken take) |
| only SPL-A left the base | 3 | Intro C, Bridge A, Instrumental 1 |

The picks follow the takes, and the takes differ between runs. They are not a property of the song's sections.

## Run time (takes.log, RTX 5070)

The first take of a song also runs demucs and the timing stage; later seeds reuse both and run only the transcriber.

| song | audio s | base take s | extra takes s (101, 202, 303) | 1 take | 3 takes | 4 takes | 4 / 1 |
|---|---|---|---|---|---|---|---|
| Kimochi Warui | 288 | 202 | 86, 461, 137 | 202 | 749 | 886 | 4.39 |
| Drunk Drivers | 225 | 74 | 33, 34, 29 | 74 | 141 | 170 | 2.30 |
| Take Me Out | 241 | 96 | 76, 69, 63 | 96 | 241 | 304 | 3.17 |
| All the Small Things | 175 | 59 | 42, 49, 47 | 59 | 150 | 197 | 3.34 |
| Lucretia | 240 | 240 | 166, 197, 230 | 240 | 603 | 833 | 3.47 |
| Creep | 240 | 66 | 35, 37, 47 | 66 | 138 | 185 | 2.80 |
| test song | 412 | 264 | 224, 164, 187 | 264 | 652 | 839 | 3.18 |
| all seven | | | | 1001 | 2674 | 3414 | 3.41 |

- An extra take averages 115 s (range 29–461 s). Three extra takes add 1.6–11.4 minutes per song, 5.7 on average.
- Run time follows the token count. Kimochi Warui's seed 202 ran 461 s for 5586 tokens and was the worst take of the set (0.600).
- assemble takes 10–20 s per build with or without takes; the splice itself is negligible.
- CPU run times were not measured here.

## Recommendation

**Default the any-song tool to 4 takes (the default seed plus three more), spliced, whenever the guitar engine runs on a GPU. On a CPU-only machine, default to 1 take and offer 4 as the opt-in. Never offer 2 or 3.**

The evidence:
- **4 takes beat 1.** Over the default seed's take: +0.013 F1@50 [+0.003, +0.024] on five songs. With any seed as the base: +0.033 [+0.005, +0.069], with 14 of 20 song × base pairs better.
- **The downside is small and the worst case improves.** No per-song loss is larger than −0.019, and the worst case rises by +0.064.
- **Most of the value is protection against a bad draw**, which a single take cannot detect: Kimochi Warui's 0.600 take, Drunk Drivers' over-written outro, the test song's dropped stretch in v1.
- **It meets DESIGN §3.2's adoption rule as written:** a CI excluding 0, and no per-song regression above max(0.05, the seed spread). Two caveats: the Wilcoxon test cannot reach significance at this n, and Lucretia shows the one failure the rule cannot see.
- **The step is 1 → 4.** Two takes do nothing, and three are worse than one (−0.017; Kimochi Warui −0.099).
- **Cost on the 5070:** 3.4× the GPU time, 1.6–11.4 extra minutes per song (5.7 on average).
- **The takes default does not need to wait for better sections.** The splice works as well on fixed 8-measure windows as on allin1's or the human chart's sections, and SPL-F is slightly ahead (+0.0055 over allin1). Whether to switch the windows to 8 bars is a separate, small decision these six songs cannot settle.

The caveats:
- Six songs, four of them Harmonix charts (development-only under DESIGN). CIs from five values are wide and anti-conservative.
- The fixed-base estimate depends on the base seed's luck. The rotation removes that dependence but reuses the same four takes.
- More than four takes was not tested.
- Lower-tier F1 is dominated by the reducer's song-wide ladder.
- Three builds failed the gate on a sustain past the audio's end (note 6). Users would hit that whatever the default number of takes.

---

## Files

All paths are under `/tmp/claude-0/-home-user/5307d417-c453-5e74-8f13-b43b2df06ab1/scratchpad/g2/takes_exp/`.

**Scripts:**
- `/tmp/claude-0/-home-user/5307d417-c453-5e74-8f13-b43b2df06ab1/scratchpad/g2/takes_exp/build.py`
- `/tmp/claude-0/-home-user/5307d417-c453-5e74-8f13-b43b2df06ab1/scratchpad/g2/takes_exp/prep_sections.py`
- `/tmp/claude-0/-home-user/5307d417-c453-5e74-8f13-b43b2df06ab1/scratchpad/g2/takes_exp/run_all.sh`
- `/tmp/claude-0/-home-user/5307d417-c453-5e74-8f13-b43b2df06ab1/scratchpad/g2/takes_exp/run_rot.sh`
- `/tmp/claude-0/-home-user/5307d417-c453-5e74-8f13-b43b2df06ab1/scratchpad/g2/takes_exp/score_raw.sh`
- `/tmp/claude-0/-home-user/5307d417-c453-5e74-8f13-b43b2df06ab1/scratchpad/g2/takes_exp/check_spl2.py`
- `/tmp/claude-0/-home-user/5307d417-c453-5e74-8f13-b43b2df06ab1/scratchpad/g2/takes_exp/analyze.py`
- `/tmp/claude-0/-home-user/5307d417-c453-5e74-8f13-b43b2df06ab1/scratchpad/g2/takes_exp/extra.py`
- `/tmp/claude-0/-home-user/5307d417-c453-5e74-8f13-b43b2df06ab1/scratchpad/g2/takes_exp/rotation.py`
- `/tmp/claude-0/-home-user/5307d417-c453-5e74-8f13-b43b2df06ab1/scratchpad/g2/takes_exp/tables.py`

**Per-build results** (`<id>` is one of take_me_out, all_the_small_things, lucretia, creep, kimochi_warui, drunk_drivers, test_song; `<cond>` is S1–S4, SPLA, SPLH, SPLF, SPL3, SPL2, A_b101/202/303, F_b101/202/303):
- `/tmp/claude-0/-home-user/5307d417-c453-5e74-8f13-b43b2df06ab1/scratchpad/g2/takes_exp/results/<id>/<cond>.build.json`: assemble's summary, sections, take windows and picks, and the gate. For SPL2 it holds the refusal.
- `/tmp/claude-0/-home-user/5307d417-c453-5e74-8f13-b43b2df06ab1/scratchpad/g2/takes_exp/results/<id>/<cond>.score.json`: score.py's output.
- `/tmp/claude-0/-home-user/5307d417-c453-5e74-8f13-b43b2df06ab1/scratchpad/g2/takes_exp/results/<id>/raw_<seed>.score.json`: the raw takes.
- `/tmp/claude-0/-home-user/5307d417-c453-5e74-8f13-b43b2df06ab1/scratchpad/g2/takes_exp/results/take_me_out/S1_nosections.build.json` and `.score.json`: the first S1 build, without sections, which failed the gate.
- `/tmp/claude-0/-home-user/5307d417-c453-5e74-8f13-b43b2df06ab1/scratchpad/g2/takes_exp/configs/<id>/<cond>.json`: the assemble configs.
- `/tmp/claude-0/-home-user/5307d417-c453-5e74-8f13-b43b2df06ab1/scratchpad/g2/takes_exp/builds/<id>/<cond>/`: the built song folders. The three gate failures are in `/tmp/claude-0/-home-user/5307d417-c453-5e74-8f13-b43b2df06ab1/scratchpad/g2/takes_exp/builds/creep/S4.failed/`, `/tmp/claude-0/-home-user/5307d417-c453-5e74-8f13-b43b2df06ab1/scratchpad/g2/takes_exp/builds/creep/A_b202.failed/` and `/tmp/claude-0/-home-user/5307d417-c453-5e74-8f13-b43b2df06ab1/scratchpad/g2/takes_exp/builds/creep/A_b303.failed/`; the first take_me_out build is in `/tmp/claude-0/-home-user/5307d417-c453-5e74-8f13-b43b2df06ab1/scratchpad/g2/takes_exp/builds/take_me_out/S1_nosections.failed/`.
- `/tmp/claude-0/-home-user/5307d417-c453-5e74-8f13-b43b2df06ab1/scratchpad/g2/takes_exp/sections/<id>/human.json`, `fixed8.json` and `prep.json`. Kimochi Warui has no human.json.

**Analysis outputs:**
- `/tmp/claude-0/-home-user/5307d417-c453-5e74-8f13-b43b2df06ab1/scratchpad/g2/takes_exp/analysis/metrics.json`
- `/tmp/claude-0/-home-user/5307d417-c453-5e74-8f13-b43b2df06ab1/scratchpad/g2/takes_exp/analysis/paired.json`
- `/tmp/claude-0/-home-user/5307d417-c453-5e74-8f13-b43b2df06ab1/scratchpad/g2/takes_exp/analysis/windows.json`
- `/tmp/claude-0/-home-user/5307d417-c453-5e74-8f13-b43b2df06ab1/scratchpad/g2/takes_exp/analysis/extra.json`
- `/tmp/claude-0/-home-user/5307d417-c453-5e74-8f13-b43b2df06ab1/scratchpad/g2/takes_exp/analysis/rotation.json`
- `/tmp/claude-0/-home-user/5307d417-c453-5e74-8f13-b43b2df06ab1/scratchpad/g2/takes_exp/analysis/runtime.json`
- `/tmp/claude-0/-home-user/5307d417-c453-5e74-8f13-b43b2df06ab1/scratchpad/g2/takes_exp/analysis/test_song.json`
- `/tmp/claude-0/-home-user/5307d417-c453-5e74-8f13-b43b2df06ab1/scratchpad/g2/takes_exp/analysis/spl2.json`
- `/tmp/claude-0/-home-user/5307d417-c453-5e74-8f13-b43b2df06ab1/scratchpad/g2/takes_exp/analysis/tables.md`
- `/tmp/claude-0/-home-user/5307d417-c453-5e74-8f13-b43b2df06ab1/scratchpad/g2/takes_exp/analysis/extra.md`
- `/tmp/claude-0/-home-user/5307d417-c453-5e74-8f13-b43b2df06ab1/scratchpad/g2/takes_exp/analysis/rotation.md`
- `/tmp/claude-0/-home-user/5307d417-c453-5e74-8f13-b43b2df06ab1/scratchpad/g2/takes_exp/analysis/scan/`: cached scan-chart parses.

**Logs:**
- `/tmp/claude-0/-home-user/5307d417-c453-5e74-8f13-b43b2df06ab1/scratchpad/g2/takes_exp/run.log`
- `/tmp/claude-0/-home-user/5307d417-c453-5e74-8f13-b43b2df06ab1/scratchpad/g2/takes_exp/run_rot.log`
- `/tmp/claude-0/-home-user/5307d417-c453-5e74-8f13-b43b2df06ab1/scratchpad/g2/takes_exp/raw_scores.log`

**Worktree** (left in place, unchanged code): `/tmp/claude-0/-home-user/5307d417-c453-5e74-8f13-b43b2df06ab1/scratchpad/wt/exp-takes` at aaab63c.

**Not written:** `/tmp/claude-0/-home-user/5307d417-c453-5e74-8f13-b43b2df06ab1/scratchpad/g2/takes_exp/REPORT.md`. The harness blocked report files from this subagent; the text above is its content.