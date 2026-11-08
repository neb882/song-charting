# The owner's second video review (pm2 on v0.4.0's GPU chart): three claims measured (2026-11-08)

The owner had another vendor's video model review his v0.4.0 GPU chart of pm2 (the stress set's 200 BPM song), with
its earlier reviews of sooth, ntl and pm2's v0.3 chart carried over. The orchestrator checked the claims that would
change code:

- **The tempo "crater" at 235-295 s is real music, not a defect:** the same tempo change is in the CPU chart (140.8-214.8
  BPM, M6-05's "the doubled grid follows allin1's beats: its straight line missed a tempo change at 235-300 s"), and
  M6-05 measured our beats there against the human chart at F1 0.98-1.02 within 9-12 ms (the entry near 240 s is the
  weak window, 0.55). Not changed.
- **The "forced HOPO chords" diagnosis is wrong:** `quantize._natural` already makes a chord a natural strum, as Clone
  Hero does; a chord plays as a HOPO only where the engine's take marked it one and the quantizer kept the source's
  state. Whether chords should always strum is part 2 below.
- **The ntl parts** are about its v0.3.1 chart; v0.4.0's GPU chart of ntl (the owner's, 2026-11-08) has the straight
  line and one tempo marker at 75.0 BPM (the v0.4.0 gate report).

A measurer then ran the three parts below (CPU only, the v0.4.0 gate's runs, the humans' charts through scan-chart's
readers: notes, states and solo spans). **Verdicts:** solos (S2, the capped solo's remainder its own solo, outside
`max_solos`) clears its bar on the mean of the three songs it changes, with troop's time outside the humans' solos
rising .072 -> .245: a candidate for an M8 order, weighed there. HOPO chords as strums (C1): +0.001 [-0.002, +0.004],
s07 -0.021: closed (the humans chart HOPO chords at about our rate). The GPU chart's intro: the five human charts split
(two HOPO it, two tap it, one mixes), all 84-87 % non-strum, and M7-02's rule leaves it 70 % strums (agreement .280
against .496 with every tap kept): a GPU-take case for M8-02 part C, which re-measures the tap rule on GPU takes.
Scripts: eval/m8/review2/ (placeholder paths).

---

# M8 review 2: three checks against the human charts (measurement only)

Scripts (placeholders <scratch>, $DEV, <wt>, <python> stand for the paths in the brief; all in this folder; each states what it reads/prints): lib.py (loader), solos.py -> solos.json, solos_tab.py ->
solos_table.txt, align.py -> align.json, hopo.py -> hopo.json, intro.py -> intro.json. Run with
`<python> -I <script>` (orch main 59b36e7 on the path; scan-chart from base-main).
Charts: the v0.4.0 gate's runs (v040, v040-stress, v040-set20); humans through scan-chart notes/states/solo sections only.
Alignment per chart as M7-01 A: each human chart's `ref_delay_ms` and our `cand_total_shift_ms` from its score JSON.

## 1. Solos (23 songs)
Choices: `place` re-implements `starpower.place_solos` (labels mode, which every song's config uses) with two switches; the
base arm is asserted equal to the library and to report.json's solos on all 23 songs. S1/S2 exempt a candidate from the gap
rule only against kept solos of its own (split) run; S1 counts the remainder toward max_solos, S2 does not (a kept solo whose
run already had one kept). The share budget and the 16-onset/4-measure minimums still apply. S3 = max_measures 128;
S3b = also max_seconds 200 (S3 alone keeps the 100 s cap, which still splits pm2's solo: 56+39 measures ~ 115 s).
Assert held: songs with no split run / no gap skip are identical under every arm. Songs with a split run: pm2, sooth,
troop, s01, s06, s08. Cover = share of the humans' solo time we mark (mean over charts), outside = share of our solo time
outside every human solo (mean over charts); see solos_table.txt for all rows.

| song (humans' solos per chart) | today n / cover / outside | S1 | S2 | S3 |
|---|---|---|---|---|
| pm2 [5,4,3,5,1] | 4 / .631 / .527 | 4 / .809 / .470 | 5 / .876 / .457 | 4 / .374 / .554 |
| troop [1,3,4] | 1 / .834 / .072 | 2 / .902 / .245 | 2 / .902 / .245 | 1 / .902 / .246 |
| s06 [3,0,1,1] | 4 / .635 / .356 | 4 / .633 / .284 | 5 / .666 / .351 | 4 / .667 / .351 |
| s01 [0,1,3,2] | 1 / .630 / .788 | same | same | 1 / .630 / .800 |
| sooth, s08 | unchanged under S1, S2, S3 (S3b changes them: sooth cover .903 -> .767) | | | |

Songs changed and means over them (cover n=3, outside n=3): S1 cover +0.081, outside +0.015, but **s06's cover falls
(.635 -> .633)**; S2 cover +0.115, outside +0.033, no song falls; S3 cover -0.039 (pm2 falls .631 -> .374: the 128-measure
solo is still split at 100 s and the window moves), outside +0.052; S3b cover +0.034 (sooth falls), outside +0.034.
Pooled over all songs with humans' solos (n=16): cover .617 -> S1 .632 / S2 .638 / S3 .607 / S3b .629.
**Verdict:** S3 fails; S1 fails the "no song's coverage falls" clause by 0.002 (s06) although its means pass; **S2 clears
the bar as written** on the three songs it changes (pm2 cover .631 -> .876, outside .527 -> .457; troop .834 -> .902 with
outside .072 -> .245, which on its own breaks "less than half"; s06 .635 -> .666). Caveats: S2's gain on pm2 and s06 comes
partly from a 5th solo (pm2 gets 208.8-217.0 back, because the remainder no longer takes a max_solos slot; s06 gets one at
165-197 s), not only from the remainder; the pm2 remainder (322.4-369.1 s) is the 39 measures / 376 onsets the brief names.
The GPU chart's report shows the same drop (42 measures, 478 onsets) - not re-run. Only 3 songs change; human charts per
song 1-5 and disagree widely on solo count.

## 2. HOPO chords
Our HOPO chords (a chord is a HOPO only by a flip): 255 of 7,687 chords (3.3 %) on the 23 CPU charts, concentrated in
s09 115, s07 63, s03 24, s11 14, troop 12, sooth 11; 0 on 11 songs. GPU pm2: 9 of 228 (CPU pm2: 1).
Humans: HOPO share of their own chords 3.8 % pooled over charts (18,564 chords); by song 0-14 %, s07 27 %: humans do chart
HOPO chords, at about our rate. At our HOPO chords (match 50 ms, pooled over charts, 920 events): unmatched 332; matched
588 of which the human has a single note 515 (275 HOPO, 238 strum, 2 tap) and a chord 73 (44 HOPO, 29 strum): so 54 % of
matched are HOPOs on their side (60 % when they chart a chord).
C1 (every HOPO chord a strum; chord taps untouched): state agreement of all Expert guitar notes, 100 ms, song mean over its
charts, 23 songs: today 0.7903, C1 0.7911, diff +0.0008, paired bootstrap 95 % CI [-0.0023, +0.0043]; without the six
references (17) +0.0011 [-0.0032, +0.0061]. No song had humans' agreement under 0.6 (min 0.654), none left out. Changed 10
songs: s03 +0.032, s09 +0.011, break +0.003, s12/sooth +0.001; down: s07 -0.021, s11 -0.005, s04 -0.002, s06 -0.001,
troop -0.000. **Bar (+0.005 pooled, CI above 0, no song down > 0.01): fails** (pooled +0.001, CI spans 0, s07 down 0.021).
The engine's forced chord flags are a coin flip, as M7-01 found for singles. The owner's ballad (ntl) has no human chart:
its 18 chords are not checked. GPU pm2: today 0.670, C1 0.671.

## 3. GPU pm2 intro
Alignment: GPU report pad 3.371 s / audio 439.213 s; CPU 3.586 s / 442.999 s. The pads and lengths do not fix a lag
(the files differ by 4.55 s at the start), so the lag is by onset matching: GPU chart seconds + 4.768 s = CPU chart seconds;
2,356 of 3,445 GPU Expert guitar onsets lie within 10 ms of a CPU onset (2,547 within 50 ms; chance ~16 %), 61-84 % in every
60 s window (no drift). Checked. In the first 25 s the GPU chart has 187 onsets: 131 strum, 36 HOPO, 20 tap; 157 in
3.3-22.7 s (the claimed 154 source taps + 3). Gaps in that region: 45 % at most 0.125 s, median 0.149 s; the fast-run
notes: only 20.
The source take is not on this machine, so "every source tap kept" = every onset in 3.3-22.7 s a tap (157 vs 154: up to 3
too many). Agreement at 100 ms with each human chart over the same stretch (all 187 onsets matched in every chart; humans
have 287 onsets there):

| human chart (their states in the window) | GPU as written | all taps | region all HOPO | CPU chart |
|---|---|---|---|---|
| primary (255 HOPO, 32 strum) | .353 | .155 | .989 | .300 |
| alt2 (identical states) | .353 | .155 | .989 | .300 |
| alt1 (120 tap, 147 HOPO, 20 strum) | .267 | .278 | .749 | .220 |
| alt3 (240 tap, 16 HOPO, 31 strum) | .214 | .947 | .203 | .293 |
| alt4 (240 tap, 15 HOPO, 32 strum) | .214 | .947 | .203 | .280 |

Mean over the five: as written .280, all taps .496, all HOPO .627, CPU chart .279. The humans split: two charts HOPO
the intro, two tap it, one mixes (primary and alt2 are state-identical, so effectively 4 distinct). Neither the written
states nor the CPU chart's agree well with any; the rule as written gets 20 taps, 36 HOPO and 131 strums where every human
has 84-87 % non-strum. No bar; feeds M8-02 part C.

## Caveats
Sample: 23 songs, 1-5 charts each; solo changes on 3 songs only. "All taps" is a reconstruction of the source take
(the take itself unavailable); chord taps untouched in C1; solo spans use chart ms + each chart's shift, the human frame.
Not checked: the ntl count, the GPU chart's own solo re-run, any rule on the real pipeline.
