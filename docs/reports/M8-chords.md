# Chords against the takes' agreement (advisor finding 1): measurement report

Prereg: prereg.txt (written 20:01Z before any number; addendum after step 1 on 3 songs). Scripts: scripts/measure.py
(reuses m8-02/C/scripts/m2lib.py and align.py in process; lanes-drums part 1's shape runs copied), scripts/tables.py.
Numbers: results.json (per song, chart, arm, variant), tables.txt (every table), summary.json (bar verdicts).

## Verdict, primary variant first (K=2, highest lane; m05; the 19 songs; primaries)

**Fails, narrowly, on (c).** (a) passes: the gap went down on 12 songs and up on 6, and its mean change was -0.012 [-0.023, -0.003].
(b) passes: exact-lane@50 +0.001, CI low -0.000. (c) fails: the shape-change gap moved -0.007, but the CI high is
+0.003 against the bar's +0.002. (d) passes: F1@50 identical on every chart. (e) passes: chord precision +0.021
[+0.010]. The effect is small. Pooled chord share went from 0.350 to 0.332 against the humans' 0.267. Songs within 0.05
of the humans: 8 before, 8 after. Beside: it passes all five on the 19 well-aligned charts, on 23 primaries and on 23
well-aligned charts. The other 8 variants are exploratory. K2_low and K2_mode match K2_high. K3 and K4 fail (a) on
every set: they bring the pooled share to the humans' or below (0.247, 0.149), but they cut true chords on
chord-heavy songs. They also fail (b) and (c), because the CIs are wide.

## Step 1: the splice's time base. The literal gate failed.

0.511 of 7,565 m05 chord onsets lie within 5 ms of the take their window used, against a gate of 0.95. The cause is
quantization: the build snaps the spliced notes to the chart's grid. The absolute residual has a median of about 3-5
ms, a p90 of 9-36 ms and a maximum under 50 ms, and the signed median per song is within ±5 ms. The amended check
(prereg addendum) tests the time base itself: 0.989 of the chord onsets have an onset in their window's take that,
mapped onto the chart's tempo map, lies within half a 16th of the chart's tick. 0.991 have one within 50 ms. I went
on under the amended gate. If you hold to the 5-ms gate, the rest is void.

## Step 2: does agreement predict a human chord? (m05, primaries, 19 songs, pooled)

| our onset | k (takes of 4 with a chord within 50 ms) | n | human chord within 50 ms |
|---|---|---|---|
| chord | 0 | 49 | 0.041 |
| chord | 1 | 307 | 0.169 |
| chord | 2 | 1,642 | 0.292 |
| chord | 3 | 1,788 | 0.478 |
| chord | 4 | 2,902 | 0.721 |
| single | 0 | 14,220 | 0.026 |
| single | 1 | 2,700 | 0.199 |
| single | >=2 | 1,101 | 0.165 |

Yes, monotonically. Even k=2 chords are human chords only 0.29 of the time, though. Only 356 of 6,688 chords have k<=1,
so K=2 can remove only about 5 % of them. Most of the phantom chords are ones all the takes agree on, and the error is
per song. In s03, 0.705 against 0.002, 318 of the chords are 4-of-4. In creep, s02, s09 and s11 most phantom chords
have k=2-3. Conversely kimochi_warui's missing chords are not fixed by any demotion rule (0.284 against 0.684). Singles
where 2+ takes chord are human chords only 0.165 of the time, so promoting them is not supported. Per-song rows are in
tables.txt.

## Step 4: the `one` arm, for the record

The same table, on the base take alone, with the other 3 takes used only as voters: k=1 chords 0.275, k=4 0.714. K=2
moves the pooled share from 0.351 to 0.294 (19 songs, primaries) and fails (a), with a CI high of +0.007, and (c). The
friend's Quick (one take) has no other takes, so it would need 3 extra engine runs to vote. That is the cost of Best
chart, and it is not a Quick rule. A Quick-side fix would need a signal from within the one take or from the stem.

## Caveats

- 19 or 23 songs, with a paired bootstrap over songs. (c) misses by 0.001 of CI: noise-sized.
- Chord share is measured within the human chart's span. The pooled m05 figure on 23 primaries is 0.331 against
  0.249, consistent with M8-02 A's 0.325 against 0.244 on the takes.
- Alignment was recomputed (M8-02's align.json was gone) against the v0.4.0 golden song.ogg, which has the same tempo
  map and Offset as both arms' charts (checked on all 23).
- The variants were applied in memory to the onsets. Sustains, HOPO and star power were not rebuilt, and the lower
  levels were not checked.
- "mode" counts each take's nearest onset within 50 ms; ties go to the highest lane.
