# Repeat consistency: 4 spliced GPU takes (m05) against one (a second advisor's finding 2)

## Verdict

**The preregistered rule does not fire, but only just.** On the primary measure (repeat_consistency F1, allin1 sections, relaxed pairs), m05 minus one is **-0.014 [-0.033, +0.001]** over 22 songs (break has no pair). The CI's upper end is +0.001, so it is not under 0, and the rule's answer is "no difference detected". Every other reading points the same way and has its CI under 0:
- lane-only, positional: -0.014 [-0.029, -0.001];
- lane agreement among time-matched onsets: -0.038 [-0.078, -0.006];
- strict pairs (equal beats, no shift): F1 -0.020 [-0.042, -0.001], 16 songs;
- the chart's own section events as sections: F1 -0.032 [-0.072, -0.002], 21 songs.

Song counts on the primary: m05 is lower on 11 songs, higher on 6 and equal on 5. **Read: the splice probably costs a little repeat consistency, about 0.01-0.04 on a 0-1 scale. The primary measure cannot rule out zero.** The splice's gain was +0.005 [-0.005, +0.014] F1@50 (M8-02). This cost is about 3 times that gain, at the same uncertainty.

**Ours against the humans (primary F1):** the humans' own repeat consistency is 0.262 (mean over songs). One take scores 0.220, m05 0.205 and the CPU single take 0.210.
- m05 - human: -0.056 [-0.115, -0.008];
- one - human: -0.042 [-0.090, +0.003].

Both of our arms are less consistent than the humans. Only m05's gap is clear of 0. On lane-only, positional, both gaps include 0 (m05 -0.038 [-0.095, +0.010]; one -0.024 [-0.080, +0.022]).

**Absolute level:** by this measure, even the humans repeat a same-label, same-length allin1 section only about 26 % alike. Two things lower it: allin1's labels group sections that are not musically identical, and a bound can be off by more than the 2-beat shift. The measure is useful as a contrast between arms on the same pairs, not as an absolute figure.

**Sanity check, CPU single take (v0.4.0 golden, seed 20260609) minus GPU one:** -0.009 [-0.026, +0.006] F1. The two single takes are alike, as expected, although lane-only positional is -0.021 [-0.042, -0.003].

**Worst songs, m05 minus one (primary F1):**
- s01 -0.157 (m05 0.038, one 0.195, human 0.534);
- drunk_drivers -0.080;
- take_me_out -0.048;
- s12 -0.039;
- s07 -0.030.

**Best songs, m05 minus one:**
- creep +0.045;
- s10 +0.028;
- s05 +0.023.

Under the chart-event sections the worst are kimochi_warui -0.318 and take_me_out -0.236.

## Method (prereg.txt, with 3 addenda, all disclosed)
- **Arms:** M8-02 B's GPU `one` and `m05` Expert guitar charts. Beside them, the v0.4.0 golden CPU single-take charts (`cpu`).
- **Humans:** each song's primary chart only, through the scorer's scan. The alignment is M8-02's align.py, re-run in process on the primary charts with the v0.4.0 golden song.ogg. All 23 songs are well aligned.
- **Sections (addendum 1):** the kept work folder's allin1 segments ('start' and 'end' dropped), each bound + the lead-in pad, snapped to our chart's nearest beat. The plan was the chart's own section events. Creep had 0 pairs under that plan, because the build merges and splits segments. The chart events are kept beside as `events.*`.
- **Pairs (addendum 2):** same allin1 label, |beats difference| <= 2. The comparison runs over the shorter length. A shift of -2..+2 beats is chosen per pair and per chart to maximize F1. The strict rule (equal beats, no shift) is kept beside.
- **F1:** onsets are (offset in our beats, lane set). Two onsets match one-to-one (the scorer's match) within 50 ms at the pair's tempo, only between equal lane sets. F1 = 2 hits / (nA + nB).
- **Lane-only:** the i-th onset of one instance against the i-th of the other, over max(nA, nB).
- **Song value:** the mean over its pairs.
- **Bootstrap:** paired over songs, 10,000 draws, seed 7. All 23 songs decide; the 19 of the bar are beside.
- **Human onsets (addendum 3, made after the first tables):** a fault fix. The human side measured offsets in the human's own beats but cut the window in ours. That broke charts whose tempo map runs at 2x or 0.5x ours (s10, s11, s13, and s06 and s07 at about 1.14). Human onsets are now placed on our beat grid. The first version is kept as results_humangrid.json: human mean 0.278, one - human -0.059 [-0.131, -0.000], m05 - human -0.073 [-0.148, -0.011]. The verdict is the same. This change does not touch m05 - one.
- **Diagnostic:** shifts widened to +-8 beats on 6 songs left the human levels low (0.1-0.5), so the low absolute level is not a window artefact.

## Caveats
- **Small samples:** 351 pairs in all, unevenly spread. sooth has 202; 7 songs have only 1-2 pairs (kimochi_warui, take_me_out, troop, s05, s07, s10, s13). Per-song means weight those songs equally.
- **Ties:** m05 equals one on 5 songs (all_the_small_things, kimochi_warui, s02, s03, s13). The splice changed nothing in their paired sections.
- **Section source:** allin1 label grouping is coarse, and the strict, relaxed and chart-event rules give different pair sets. The direction (m05 lower) holds in all of them; the primary's CI just touches 0.
- **Not checked:**
  - alt human charts;
  - other difficulties;
  - which take each section's windows came from, that is, whether the inconsistent pairs are exactly the ones whose windows used different takes. That is the direct mechanism test, and the next step if this matters.

## Bootstrap tables (all section sources and rules; tables.txt has all of it)
```
=== sections allin1.relaxed
f1 all23 {"m05-one": {"mean": -0.014, "lo": -0.033, "hi": 0.001, "n": 22}, "cpu-human": {"mean": -0.051, "lo": -0.107, "hi": 0.001, "n": 22}, "m05-human": {"mean": -0.056, "lo": -0.115, "hi": -0.008, "n": 22}, "one-human": {"mean": -0.042, "lo": -0.09, "hi": 0.003, "n": 22}, "cpu-one": {"mean": -0.009, "lo": -0.026, "hi": 0.006, "n": 22}, "mean_cpu": 0.21, "mean_m05": 0.205, "mean_one": 0.22, "mean_human": 0.262}
f1 bar19 {"m05-one": {"mean": -0.014, "lo": -0.036, "hi": 0.005, "n": 18}, "cpu-human": {"mean": -0.05, "lo": -0.109, "hi": 0.005, "n": 18}, "m05-human": {"mean": -0.051, "lo": -0.116, "hi": 0.002, "n": 18}, "one-human": {"mean": -0.037, "lo": -0.089, "hi": 0.012, "n": 18}, "cpu-one": {"mean": -0.012, "lo": -0.032, "hi": 0.003, "n": 18}, "mean_cpu": 0.216, "mean_m05": 0.215, "mean_one": 0.228, "mean_human": 0.265}
lane_pos all23 {"m05-one": {"mean": -0.014, "lo": -0.029, "hi": -0.001, "n": 22}, "cpu-human": {"mean": -0.046, "lo": -0.115, "hi": 0.01, "n": 22}, "m05-human": {"mean": -0.038, "lo": -0.095, "hi": 0.01, "n": 22}, "one-human": {"mean": -0.024, "lo": -0.08, "hi": 0.022, "n": 22}, "cpu-one": {"mean": -0.021, "lo": -0.042, "hi": -0.003, "n": 22}, "mean_cpu": 0.16, "mean_m05": 0.168, "mean_one": 0.182, "mean_human": 0.206}
lane_pos bar19 {"m05-one": {"mean": -0.016, "lo": -0.035, "hi": -0.001, "n": 18}, "cpu-human": {"mean": -0.054, "lo": -0.138, "hi": 0.009, "n": 18}, "m05-human": {"mean": -0.045, "lo": -0.115, "hi": 0.012, "n": 18}, "one-human": {"mean": -0.029, "lo": -0.098, "hi": 0.026, "n": 18}, "cpu-one": {"mean": -0.026, "lo": -0.049, "hi": -0.007, "n": 18}, "mean_cpu": 0.168, "mean_m05": 0.177, "mean_one": 0.193, "mean_human": 0.222}
lane_time all23 {"m05-one": {"mean": -0.038, "lo": -0.078, "hi": -0.006, "n": 22}, "cpu-human": {"mean": -0.078, "lo": -0.151, "hi": -0.004, "n": 22}, "m05-human": {"mean": -0.095, "lo": -0.17, "hi": -0.03, "n": 22}, "one-human": {"mean": -0.057, "lo": -0.125, "hi": 0.011, "n": 22}, "cpu-one": {"mean": -0.02, "lo": -0.044, "hi": -0.001, "n": 22}, "mean_cpu": 0.306, "mean_m05": 0.289, "mean_one": 0.326, "mean_human": 0.384}
lane_time bar19 {"m05-one": {"mean": -0.041, "lo": -0.089, "hi": -0.003, "n": 18}, "cpu-human": {"mean": -0.072, "lo": -0.155, "hi": 0.014, "n": 18}, "m05-human": {"mean": -0.094, "lo": -0.18, "hi": -0.019, "n": 18}, "one-human": {"mean": -0.053, "lo": -0.128, "hi": 0.027, "n": 18}, "cpu-one": {"mean": -0.02, "lo": -0.048, "hi": 0.003, "n": 18}, "mean_cpu": 0.303, "mean_m05": 0.281, "mean_one": 0.322, "mean_human": 0.375}
=== sections allin1.strict
f1 all23 {"m05-one": {"mean": -0.02, "lo": -0.042, "hi": -0.001, "n": 16}, "cpu-human": {"mean": -0.072, "lo": -0.144, "hi": -0.0, "n": 16}, "m05-human": {"mean": -0.077, "lo": -0.14, "hi": -0.017, "n": 16}, "one-human": {"mean": -0.057, "lo": -0.117, "hi": 0.001, "n": 16}, "cpu-one": {"mean": -0.015, "lo": -0.05, "hi": 0.012, "n": 16}, "mean_cpu": 0.268, "mean_m05": 0.264, "mean_one": 0.283, "mean_human": 0.34}
f1 bar19 {"m05-one": {"mean": -0.021, "lo": -0.05, "hi": 0.003, "n": 12}, "cpu-human": {"mean": -0.072, "lo": -0.151, "hi": 0.002, "n": 12}, "m05-human": {"mean": -0.067, "lo": -0.137, "hi": -0.005, "n": 12}, "one-human": {"mean": -0.046, "lo": -0.112, "hi": 0.013, "n": 12}, "cpu-one": {"mean": -0.026, "lo": -0.07, "hi": 0.005, "n": 12}, "mean_cpu": 0.265, "mean_m05": 0.27, "mean_one": 0.291, "mean_human": 0.337}
lane_pos all23 {"m05-one": {"mean": -0.021, "lo": -0.043, "hi": -0.008, "n": 16}, "cpu-human": {"mean": -0.022, "lo": -0.058, "hi": 0.016, "n": 16}, "m05-human": {"mean": -0.029, "lo": -0.054, "hi": -0.002, "n": 16}, "one-human": {"mean": -0.007, "lo": -0.038, "hi": 0.023, "n": 16}, "cpu-one": {"mean": -0.014, "lo": -0.053, "hi": 0.013, "n": 16}, "mean_cpu": 0.223, "mean_m05": 0.216, "mean_one": 0.237, "mean_human": 0.245}
lane_pos bar19 {"m05-one": {"mean": -0.026, "lo": -0.053, "hi": -0.008, "n": 12}, "cpu-human": {"mean": -0.019, "lo": -0.061, "hi": 0.02, "n": 12}, "m05-human": {"mean": -0.022, "lo": -0.055, "hi": 0.011, "n": 12}, "one-human": {"mean": 0.004, "lo": -0.035, "hi": 0.041, "n": 12}, "cpu-one": {"mean": -0.023, "lo": -0.067, "hi": 0.002, "n": 12}, "mean_cpu": 0.226, "mean_m05": 0.223, "mean_one": 0.249, "mean_human": 0.245}
lane_time all23 {"m05-one": {"mean": -0.047, "lo": -0.102, "hi": -0.004, "n": 16}, "cpu-human": {"mean": -0.106, "lo": -0.205, "hi": -0.001, "n": 16}, "m05-human": {"mean": -0.135, "lo": -0.218, "hi": -0.056, "n": 16}, "one-human": {"mean": -0.088, "lo": -0.182, "hi": 0.01, "n": 16}, "cpu-one": {"mean": -0.018, "lo": -0.05, "hi": 0.008, "n": 16}, "mean_cpu": 0.342, "mean_m05": 0.314, "mean_one": 0.36, "mean_human": 0.449}
lane_time bar19 {"m05-one": {"mean": -0.054, "lo": -0.123, "hi": 0.002, "n": 12}, "cpu-human": {"mean": -0.082, "lo": -0.196, "hi": 0.032, "n": 12}, "m05-human": {"mean": -0.11, "lo": -0.209, "hi": -0.025, "n": 12}, "one-human": {"mean": -0.056, "lo": -0.165, "hi": 0.052, "n": 12}, "cpu-one": {"mean": -0.026, "lo": -0.066, "hi": 0.005, "n": 12}, "mean_cpu": 0.342, "mean_m05": 0.314, "mean_one": 0.368, "mean_human": 0.424}
=== sections events.relaxed
f1 all23 {"m05-one": {"mean": -0.032, "lo": -0.072, "hi": -0.002, "n": 21}, "cpu-human": {"mean": 0.001, "lo": -0.05, "hi": 0.061, "n": 21}, "m05-human": {"mean": -0.026, "lo": -0.064, "hi": 0.009, "n": 21}, "one-human": {"mean": 0.006, "lo": -0.041, "hi": 0.063, "n": 21}, "cpu-one": {"mean": -0.005, "lo": -0.016, "hi": 0.007, "n": 21}, "mean_cpu": 0.198, "mean_m05": 0.171, "mean_one": 0.203, "mean_human": 0.197}
f1 bar19 {"m05-one": {"mean": -0.04, "lo": -0.089, "hi": -0.003, "n": 17}, "cpu-human": {"mean": 0.0, "lo": -0.057, "hi": 0.072, "n": 17}, "m05-human": {"mean": -0.039, "lo": -0.082, "hi": 0.002, "n": 17}, "one-human": {"mean": 0.001, "lo": -0.053, "hi": 0.07, "n": 17}, "cpu-one": {"mean": -0.0, "lo": -0.013, "hi": 0.012, "n": 17}, "mean_cpu": 0.22, "mean_m05": 0.181, "mean_one": 0.22, "mean_human": 0.22}
lane_pos all23 {"m05-one": {"mean": -0.027, "lo": -0.064, "hi": -0.002, "n": 21}, "cpu-human": {"mean": 0.027, "lo": -0.019, "hi": 0.086, "n": 21}, "m05-human": {"mean": 0.005, "lo": -0.027, "hi": 0.042, "n": 21}, "one-human": {"mean": 0.033, "lo": -0.01, "hi": 0.09, "n": 21}, "cpu-one": {"mean": -0.006, "lo": -0.019, "hi": 0.008, "n": 21}, "mean_cpu": 0.174, "mean_m05": 0.152, "mean_one": 0.18, "mean_human": 0.147}
lane_pos bar19 {"m05-one": {"mean": -0.033, "lo": -0.077, "hi": -0.001, "n": 17}, "cpu-human": {"mean": 0.034, "lo": -0.021, "hi": 0.108, "n": 17}, "m05-human": {"mean": 0.002, "lo": -0.037, "hi": 0.047, "n": 17}, "one-human": {"mean": 0.034, "lo": -0.017, "hi": 0.107, "n": 17}, "cpu-one": {"mean": -0.001, "lo": -0.017, "hi": 0.014, "n": 17}, "mean_cpu": 0.197, "mean_m05": 0.165, "mean_one": 0.198, "mean_human": 0.163}
lane_time all23 {"m05-one": {"mean": -0.042, "lo": -0.089, "hi": -0.004, "n": 21}, "cpu-human": {"mean": -0.054, "lo": -0.138, "hi": 0.023, "n": 21}, "m05-human": {"mean": -0.082, "lo": -0.162, "hi": -0.022, "n": 21}, "one-human": {"mean": -0.04, "lo": -0.117, "hi": 0.031, "n": 21}, "cpu-one": {"mean": -0.014, "lo": -0.029, "hi": -0.0, "n": 21}, "mean_cpu": 0.277, "mean_m05": 0.249, "mean_one": 0.291, "mean_human": 0.331}
lane_time bar19 {"m05-one": {"mean": -0.047, "lo": -0.104, "hi": -0.002, "n": 17}, "cpu-human": {"mean": -0.011, "lo": -0.07, "hi": 0.056, "n": 17}, "m05-human": {"mean": -0.055, "lo": -0.098, "hi": -0.017, "n": 17}, "one-human": {"mean": -0.008, "lo": -0.066, "hi": 0.058, "n": 17}, "cpu-one": {"mean": -0.003, "lo": -0.014, "hi": 0.007, "n": 17}, "mean_cpu": 0.297, "mean_m05": 0.253, "mean_one": 0.3, "mean_human": 0.308}
=== sections events.strict
f1 all23 {"m05-one": {"mean": -0.029, "lo": -0.07, "hi": 0.002, "n": 21}, "cpu-human": {"mean": 0.003, "lo": -0.046, "hi": 0.066, "n": 21}, "m05-human": {"mean": -0.025, "lo": -0.065, "hi": 0.012, "n": 21}, "one-human": {"mean": 0.004, "lo": -0.041, "hi": 0.064, "n": 21}, "cpu-one": {"mean": -0.001, "lo": -0.015, "hi": 0.015, "n": 21}, "mean_cpu": 0.169, "mean_m05": 0.141, "mean_one": 0.17, "mean_human": 0.166}
f1 bar19 {"m05-one": {"mean": -0.038, "lo": -0.088, "hi": 0.0, "n": 17}, "cpu-human": {"mean": 0.003, "lo": -0.053, "hi": 0.079, "n": 17}, "m05-human": {"mean": -0.039, "lo": -0.084, "hi": 0.004, "n": 17}, "one-human": {"mean": -0.0, "lo": -0.051, "hi": 0.073, "n": 17}, "cpu-one": {"mean": 0.004, "lo": -0.012, "hi": 0.022, "n": 17}, "mean_cpu": 0.189, "mean_m05": 0.147, "mean_one": 0.185, "mean_human": 0.185}
lane_pos all23 {"m05-one": {"mean": -0.026, "lo": -0.062, "hi": 0.001, "n": 21}, "cpu-human": {"mean": 0.035, "lo": -0.01, "hi": 0.093, "n": 21}, "m05-human": {"mean": 0.011, "lo": -0.022, "hi": 0.048, "n": 21}, "one-human": {"mean": 0.036, "lo": -0.007, "hi": 0.093, "n": 21}, "cpu-one": {"mean": -0.001, "lo": -0.016, "hi": 0.013, "n": 21}, "mean_cpu": 0.177, "mean_m05": 0.153, "mean_one": 0.179, "mean_human": 0.142}
lane_pos bar19 {"m05-one": {"mean": -0.031, "lo": -0.075, "hi": 0.003, "n": 17}, "cpu-human": {"mean": 0.04, "lo": -0.014, "hi": 0.114, "n": 17}, "m05-human": {"mean": 0.007, "lo": -0.033, "hi": 0.053, "n": 17}, "one-human": {"mean": 0.038, "lo": -0.014, "hi": 0.111, "n": 17}, "cpu-one": {"mean": 0.002, "lo": -0.015, "hi": 0.019, "n": 17}, "mean_cpu": 0.199, "mean_m05": 0.166, "mean_one": 0.197, "mean_human": 0.159}
lane_time all23 {"m05-one": {"mean": -0.036, "lo": -0.085, "hi": 0.004, "n": 21}, "cpu-human": {"mean": -0.048, "lo": -0.133, "hi": 0.032, "n": 21}, "m05-human": {"mean": -0.078, "lo": -0.16, "hi": -0.014, "n": 21}, "one-human": {"mean": -0.042, "lo": -0.12, "hi": 0.035, "n": 21}, "cpu-one": {"mean": -0.006, "lo": -0.022, "hi": 0.012, "n": 21}, "mean_cpu": 0.227, "mean_m05": 0.197, "mean_one": 0.233, "mean_human": 0.275}
lane_time bar19 {"m05-one": {"mean": -0.043, "lo": -0.101, "hi": 0.004, "n": 17}, "cpu-human": {"mean": -0.005, "lo": -0.064, "hi": 0.069, "n": 17}, "m05-human": {"mean": -0.052, "lo": -0.1, "hi": -0.007, "n": 17}, "one-human": {"mean": -0.009, "lo": -0.065, "hi": 0.065, "n": 17}, "cpu-one": {"mean": 0.003, "lo": -0.013, "hi": 0.022, "n": 17}, "mean_cpu": 0.242, "mean_m05": 0.196, "mean_one": 0.239, "mean_human": 0.247}
```

## Per song (primary: allin1.relaxed; columns cpu, m05, one, human)
```
--- per song (allin1.relaxed): pairs | f1 cpu m05 one human | lane_pos cpu m05 one human | well
all_the_small_things      6 | 0.848 0.848 0.848 0.745 | 0.685 0.685 0.685 0.663 | True
creep                     8 | 0.342 0.387 0.342 0.365 | 0.256 0.217 0.256 0.227 | True
drunk_drivers             7 | 0.142 0.083 0.163 0.040 | 0.102 0.058 0.135 0.031 | True
kimochi_warui             1 | 0.145 0.145 0.145 0.000 | 0.086 0.086 0.086 0.000 | True
lucretia                  5 | 0.287 0.261 0.287 0.240 | 0.216 0.153 0.216 0.170 | True
take_me_out               2 | 0.124 0.076 0.124 0.187 | 0.072 0.067 0.072 0.070 | True
break                     0 |   -     -     -     -   |   -     -     -     -   | True
pm2                       7 | 0.188 0.195 0.188 0.274 | 0.170 0.178 0.170 0.148 | True
sooth                   202 | 0.165 0.151 0.173 0.163 | 0.142 0.121 0.149 0.130 | True
troop                     1 | 0.087 0.099 0.087 0.160 | 0.134 0.149 0.134 0.065 | True
s01                       3 | 0.194 0.038 0.195 0.534 | 0.131 0.054 0.178 0.351 | True
s02                       4 | 0.175 0.175 0.175 0.154 | 0.167 0.167 0.167 0.143 | True
s03                      16 | 0.284 0.412 0.412 0.512 | 0.212 0.360 0.360 0.315 | True
s04                       4 | 0.064 0.070 0.071 0.178 | 0.041 0.076 0.072 0.130 | True
s05                       1 | 0.411 0.393 0.370 0.400 | 0.321 0.382 0.375 0.321 | True
s06                      42 | 0.185 0.192 0.219 0.451 | 0.129 0.161 0.172 0.201 | True
s07                       1 | 0.030 0.000 0.030 0.000 | 0.016 0.000 0.016 0.000 | True
s08                       7 | 0.140 0.130 0.113 0.131 | 0.137 0.151 0.128 0.131 | True
s09                       7 | 0.147 0.201 0.215 0.308 | 0.060 0.064 0.070 0.131 | True
s10                       1 | 0.017 0.107 0.079 0.243 | 0.028 0.191 0.178 0.626 | True
s11                      17 | 0.299 0.302 0.303 0.351 | 0.171 0.187 0.191 0.263 | True
s12                       7 | 0.320 0.218 0.257 0.192 | 0.174 0.102 0.107 0.063 | True
s13                       2 | 0.034 0.034 0.034 0.125 | 0.077 0.077 0.077 0.351 | True

```

Other sources' per-song rows: tables.txt. Files: results.json (per song, per arm, per source.rule, by label), summary.json, tables.txt, results_humangrid.json, prereg.txt, scripts/measure.py, scripts/tables.py.

## Addendum: the mechanism test (orchestrator's follow-up, written after the report above)

**The question.** Does the consistency loss sit in pairs whose two instances came from different takes?

**How the pairs were split.**
- Data: the primary pairs and measure (allin1.relaxed F1, and lane-only by order) on m05's window picks. The picks come from M8-02 part B, B/arms/<label>.json, arms.m05.takes.windows.
- Clock: a window's chart time is its input time plus the lead-in pad, the same mapping as the sections.
- An instance's takes are the picks of the windows that overlap its compared span by more than 0.5 s.
- "same" means both instances come wholly from one take, and it is the same take for both. "diff" means anything else.
- The re-run that saved the per-pair rows reproduced every earlier value exactly.

**Result, m05 minus one:**

| group | pairs | pooled F1 | F1 over songs | lane-only over songs |
|---|---:|---:|---:|---:|
| same take | 188 | +0.004 | +0.008 [+0.000, +0.018], 16 songs | -0.001 [-0.007, +0.005] |
| different takes | 163 | -0.044 | -0.045 [-0.087, -0.011], 17 songs | -0.033 [-0.070, -0.004] |

**Songs with both groups (11):** diff minus same is -0.058 [-0.122, -0.007]. Over the 19 of the bar it is -0.048 [-0.130, +0.006], 7 songs.

**What the same-take group contains.** 176 of its 188 pairs use the base take on both sides. Those are identical to `one` by construction: their delta is 0.000 on every pair. Only 12 pairs use another single take on both sides, and their delta is +0.057, so switching take alone does not hurt.

**Read.** The loss sits in the pairs where the splice mixed takes. The splice is the cause.

**Where the loss is largest (different-take pairs, F1):**
- drunk_drivers -0.279 (2 pairs);
- s12 -0.175 (3);
- s01 -0.157 (3);
- s06 -0.062 (18);
- take_me_out -0.048 (2);
- sooth -0.040 (110).

**Caveats.**
- The different-take group is uneven: sooth holds 110 of its 163 pairs.
- Most songs have 1-5 such pairs.
- Assigning takes from window overlap is approximate at window edges.

Files: scripts/mech.py, mech.json, mech.txt. results.json now also carries the per-pair rows.
