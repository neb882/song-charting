# The owner's third video review (his full v0.4.0 GPU chart of sooth): three claims measured (2026-11-09)

The owner's video review now covers his full v0.4.0 GPU chart of sooth (his own audio file, 544.8 s), whose grid
record matches the CPU chart of the same file at v0.4.0 (octave 0.5, 77.1 BPM, ratio 2.0007, the first-tempo warning
at 500-535 s; the v0.4.0 gate report). Its claims that review 2 had not covered were measured against the human charts
(CPU only, the v0.4.0 gate's runs, the humans' charts through scan-chart's readers). **Verdicts, none clears its bar:**

- **Solos merged instead of skipped (M and its variants):** worse (mean coverage -0.043; his sooth chart -0.471). The
  cause on his file is the sections' labels: 18 consecutive solo sections form one 424-s run, which the caps cut into
  touching pieces. Dropping a solo the share cap would trim under 8 measures (T) is harmless and gains nothing.
- **The tail at 160 BPM:** both human charts keep 80.0 BPM through the last 60 s, and allin1 itself doubled for about
  35 s on his file (722 beats against 698). Halving the doubled stretch needs the right parity: right +0.15 beat F1,
  wrong -0.27, and no rule from our own data picks it. The warning stays; a correction needs a parity rule (deferred).
- **The outro trim:** right as it is. The 16 trimmed onsets lie after both human charts' last guitar notes, and a 40 dB
  floor brings back no onset on any of the 23 songs (pooled precision of today's trimmed onsets 0.159).

Review 2's alignment method (onsets only) locks one 16th off on a song whose onsets repeat every 16th; this review
aligns by audio first. Review 2's intro counts (pm2) do not depend on it; its 100 ms agreements may shift.
Scripts: eval/m8/review3/ (placeholder paths).

---

# M8 review 3: three checks from the owner's third video review (measurement only)

Scripts (placeholders <scratch>, $DEV, <wt>; review 2's lib.py/solos.py reused, `lib.his_map` added): align3.py (superseded, see 0),
audlag3.py, align4.py, solos3.py -> solos3.json / solos3_tab.py -> solos3_table.txt, tail3.py -> tail3.json,
outro3.py -> outro3.json / outro3_tab.py -> outro3_table.txt, outro3b.py -> outro3b.json. Orch main on the path, v0.4.0 gate runs,
humans through scan-chart notes/solo spans/tempo map only. Floats to 3 decimals unless noted.

## 0. Alignment of his sooth chart to the stress set's sooth (corrected)
Onset matching alone (align3.py: Expert guitar onsets, lag 6.178 chart s, 54 % within 10 ms) is WRONG by one 16th (0.2 s):
the charts' onsets are 16th-periodic, so the coarse search can lock one 16th off (his grid's beats sat 0.2 s from the stress
chart's at that lag, drifting 209 -> 180 ms). Fixed by audio: scorer `align` (12 windows, normalised cross-correlation, ncc
0.31-0.50, MAD 17.6 ms) of his song.ogg against the stress sooth's decode, a linear fit of the lag (slope 9.7e-5 s/s), then a linear
residual fit on the onset matches: his chart s -> stress chart s = lag 6.391 s at 0 s, 6.362 s at 500 s. Check: 1,563 of 2,414
his Expert guitar onsets within 10 ms (65 %), 1,743 within 50 ms (72 %), per-60-s residual medians -0.5 to -2.3 ms; 11 s
audio decode only. Checked (the 10 ms rate is below 100 % because the two runs chart different notes). Part 1's his-sooth numbers
were identical under the wrong and the right map (solo spans are tens of seconds); parts 2 and 3 use the right one.
His CPU chart vs his GPU chart: lag 0.000, 2,193 of 2,414 within 10 ms (the grids match).

## 1. Solos on an instrumental (23 songs + his chart; solos3.py)
`place` re-implements `starpower.place_solos` (labels mode); the base arm asserted equal to the library and to report.json's
solos on all 24 charts; asserts also held: no merge candidate -> M/Mc/M+S2 identical to base, no share trim -> T identical.
Arms (my choices where the brief leaves them): **M** = candidates (after the cap split and the 16-onset/4-measure minimums)
closer than min_gap_measures (the library's own `near`, chained) merged into one candidate (union of the spans), then picked as today
(densest first, max_solos 4, the share budget with `_trim`); the merged span is NOT re-cut to max_measures/max_seconds (else the
merge just undoes the split). **Mc** = M, then a merged candidate over a length cap cut to its densest window within the caps.
**Mn** = a gap-near candidate merged into the kept solo it is near when the union is within both caps and the share budget.
**S2** = review 2's. **T** = a candidate the share would trim below 8 measures is dropped, not trimmed.
Cover / outside / n as review 2 (mean over the human charts; his chart scored against sooth's two human charts, one of which has 2 solos).

| song | base n / cover / outside | M (= M+S2) | Mc | T | M+S2+T |
|---|---|---|---|---|---|
| pm2 | 4 / .631 / .527 | 4 / .878 / .457 | same | same | 3 / .810 / .469 |
| troop | 1 / .834 / .072 | 1 / .902 / .246 | same | same | 1 / .902 / .246 |
| s06 | 4 / .635 / .356 | 4 / .667 / .351 | same | same | same as M |
| sooth (stress set) | 3 / .903 / .592 | 2 / .814 / .635 | 3 / .903 / .592 (a 77-93 s solo in place of 211-227) | 2 / .903 / .560 | 2 / .814 / .635 |
| **his sooth** | 3 / .968 / .563 | 2 / .497 / .606 | 2 / .497 / .606 | 2 / .968 / .530 | 2 / .497 / .606 |

Songs not listed (19) are identical under every arm. Per arm (changed songs; bar = coverage rises, outside rises by less than half as much, no song falls over 0.02):
- M and M+S2 (identical here): changes pm2, troop, s06, sooth, his sooth; mean d cover -0.043, d outside +0.037; sooth and his sooth fall (-0.089, -0.471). **Fails.** Without the two sooth charts the other three gain +0.116 cover (outside +0.033; troop's outside +0.174 breaks the half rule alone), as S2 in review 2.
- Mc: changes only the two sooth charts; his falls -0.471. **Fails.** Mn: changes **nothing** on any chart (the caps, 100 s / 56 measures, forbid every union). 
- T: changes only the two sooth charts; cover unchanged, outside -0.032 (the stub's 15 s was mostly outside the humans' solo). Harmless, not a coverage gain (**bar as written: no rise**). M+S2+T: fails like M.
Why merging hurts on sooth: the whole 116-540 s of his chart is labelled "Solo 2A..2R" (18 consecutive sections), i.e. one 424 s run split by the caps
into pieces that touch each other (gaps 0.6 s). Merging them chains to one blob; the share budget then keeps one window (<= 100 s), not three. The reviewer's three skipped candidates
(164-261, 368-420, 520-540 s) are adjacent remainders of that run; their union with a kept solo exceeds the 100 s / 56 measure caps in every case. The stub (139-154 s) sits over rhythm chords by the reviewer's
account; the humans' charts of the stress-set master cover 0.968 of the base. **Verdict: no merge rule clears the bar; the sooth case is the label (an 18-section solo run), not the gap rule.**
Sample: 5 changed charts, human charts per song 1-5.

## 2. The tail's tempo (tail3.py)
Window: his file's last 60 s (input 484.8-544.8 s), the two human charts of the stress sooth (frames via part 0), score.beat_times.
- Humans: 80.0 BPM in the whole window and inside the span (73 beats each in the window, 46 in the span; their last tempo markers 76-80 BPM). They keep the slow tempo; **they do not double it**.
- His chart today: tempo map ramps 79.9 BPM at 506.0 s to 160.0 BPM at 516.1 s, holds 160.0 BPM to the chart's end (median period in the span 0.375 s, 160.0 BPM; 79 beats in the span against the humans' 46); 113 beats in the window against 73.
- Beat F1 at 70 ms in the window (per human chart primary / alt1): today 0.746 / 0.724 (in the span only: 0.672 / 0.640).
- **H** as stated (every other beat inside the reported span 500-535 s, the first kept by continuity of the preceding period): 0.452 / 0.452, WORSE (in span 0.140). The reported span is coarse: it starts at 500 s, 6 s before the ramp, so H also thins correct 80-BPM beats.
- **H2** (thin only the doubled stretch, beats with a next interval under 0.6 s, continuity parity): 0.500 / 0.487. With the other parity (**H2_alt**): 0.901 / 0.874 (in span 0.901 / 0.857); H_alt: 0.869 / 0.841. A lattice from the last slow beat at its own period (H3): 0.696 / 0.671 (the 160-BPM beats are 0.375 s apart, the lattice drifts past 70 ms).
- So the period is right (80 BPM, 40 beats in the span against the humans' 46) but the **phase (which half of the doubled beats to keep) is not settled by the grid's own period**: the ramp 506-516 s breaks continuity; the right parity gives +0.15 F1, the wrong one -0.27. A beat-level fix needs a parity rule (not found here), or better stopping the ramp at the source.
- Why the stress sooth has no span (numbers only): its allin1 beats 689 (the length would give 704 at 76.9 BPM: 15 fewer), tempo map max 80.01 BPM, 80.0 BPM in 500-535 s; the first-tempo windows with ratio near 1: 0. His: allin1 722 beats (698 expected for 544.8 s: 24 extra, about the doubled stretch's 22 surplus beats), ratio 1.04, 1.000, 1.000, 1.000 in four windows. So allin1 itself doubled for about 35 s on his file; on the other master it did not. (Not checked: allin1's own beat times; why only his file.)

## 3. The outro trim (outro3.py, outro3b.py)
Frame as part 0 and review 2's. Stems are the kept folders' guitar (or other) stem; frame_levels as assemble does; the 30 dB span recomputed in process equals every report's `kept` within 0.011 s (asserted, 23 songs). 12 of 23 songs trim an end onset.

- Trimmed Expert guitar onsets (23 songs): 102 at the end (one song 75: 266.7-287.5 s; ten songs exactly 1; the rest 0), 39 at the start (one song). Humans' last note vs the trimmed onset: in 10 of the 11 one-onset songs the trimmed onset is 0.4-7.7 s after every human chart's last note (precision 0 in every chart; the exception, one chart of s06 whose last note is at 777 s, is a human chart with a 195 s longer span), all_the_small_things 12 s after. Precision at 50 ms pooled over charts and weighted by count: 0.159 (dominated by the 75-onset song: 0.21; its humans' last note 283.6 s; the stem's 40.5 dB floor is just beyond 40).
- His sooth: 16 onsets, 540.58-544.14 s (3.56 s), all after both human charts' last guitar note (539.6 s and 539.5 s): precision 0 / 16 (both charts). His report's kept [-0.2, 540.55]. 
- **40 dB floor** (in process): 0 onsets are brought back on all 23 songs and on his chart. Floor needed to keep the first onset of each trimmed end (outro3b: dB below the stem's P95 in its window): 40.5 (the 75-onset song), 43.5, 56-81 on the other ten. His 16: 46.7 ... 69.1 dB (one onset past the stem's end), measured on the stress sooth's stem (his own stems were not kept; the other master/separation, time mapped by part 0; its 30 dB span end maps to 540.21 s against his 540.55 s, 0.34 s off, its 40 dB end to 540.31 s). 
- **Bar for relaxing the floor** (precision of brought-back onsets at least 0.75 pooled over at least 3 songs, none under 0.5): **not testable, 0 onsets come back at 40 dB; the bar's first clause cannot be met on 0 songs. Relaxing to 40 dB changes nothing here.**
- Verdict on the reviewer's "audible flourish": the guitar stem in the tail is 47-69 dB under its P95 (stress master's stem), and no human chart has a note there; whatever is audible is not the separated guitar (a drum or bass ending, or the mix, is not checked). The trim is right on the stem; a floor loose enough to keep them (about 70 dB) would also keep the stray last onsets (precision 0 on 10 other songs).

## Caveats
Part 0's alignment needed audio (only our decode of the stress file and his own song.ogg were read); sample sizes: 5 changed charts (part 1), 2 human charts on 1 song (part 2), 11 trims on 11 songs (part 3); his stems unavailable (part 3 on the stress master's stem); parity rules for H not exhausted; no ear check of the tail.
