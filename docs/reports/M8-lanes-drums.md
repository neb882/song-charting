# Held chord shapes and drum pads / regularity, ours at v0.4.0 against the humans (23 songs, measurement only)

*2026-11-09, an `sc-measurer` for the orchestrator, from two findings of that day: kimochi_warui's held chord shapes
(docs/reports/M8-compare-autochart-eu.md, its last section) and a drummer tester's notes (PROGRESS `deferred`).*

Scripts (in eval/m8/lanes-drums/): `measure.py` (scans, alignment, per-chart numbers -> results.json), `tables.py` (per-song and pooled tables
-> summary.json, tables.txt). Run: `python -I measure.py <checkout with scan-chart> $DEV results.json`, then
`python -I tables.py results.json summary.json > tables.txt`. The full tables (tables.txt) and every number (summary.json) stay in the measurer's scratch folder.

## Method
- Charts: ours at v0.4.0 (golden v040f, v040f-stress, v040-set20); humans through score.scan only: each song's primary
  chart and every alt chart that has a ref/ and input.wav. Alignment: score.align of our chart's audio against each
  human chart's input.wav, shifts as score.py. Check: our F1@50 equals the golden score.json on kimochi_warui and troop
  (guitar 0.8267 / 0.7842, drums 0.9766 / 0.8789).
- Weak alignment (score.py's warnings) on 26 alt charts (sooth alt1; s01 alt2-3; s03 alt1; s04 alt1-4; s05 alt2, alt5;
  s06 alt1-3; s07 alt1, alt3; s08 alt1, alt3-4; s09 alt1; s10 alt1-3; s11 alt2, alt4; s12 alt1). Every primary aligns
  (9/9 windows). Weak charts count in intrinsic numbers (shape changes, regularity) but not in matched ones (F1,
  agreement, confusion, the rule).
- Pooled = mean over songs of each song's mean over its human charts (each song once). Pad counts and confusions are
  summed over songs with each song's charts weighted 1/n.
- Shapes: an onset's lane set; a change = consecutive onsets with different sets. Agreement on F1@50 pairs that are
  adjacent in both charts (all onsets; and a variant where all four onsets are chords).
- Drums: only human charts scan-chart types as pro drums (drumType 1); five-lane ones dropped (s08 has none left;
  drunk_drivers, break, sooth have no human drums): 19 songs. Confusion: within each matched onset, shared pads on
  the diagonal, leftovers paired in pad order, the rest against none; the cymbal table only uses matched onsets with
  exactly one cymbal on each side.
- Regularity: each chart's own measures (time signatures, resolution); pattern = set of (pad, round(48 x position)).
  Pairs where both measures are empty are skipped. "Ours repeats where the human repeats": our measure holding the
  human measure's midpoint equals our measure before it.
- R(x): runs where each measure has Jaccard >= x with the one before become the run's most common pattern (ties to
  earliest); changed measures' notes regenerated on the 1/48 grid with our tempo map; unchanged measures keep their
  notes. F1@50 rescored as the scorer does (span, margin, n_cand_eff).

## Part 1: chord shapes, Expert guitar (23 songs)
Pooled: changes per onset human 0.697, ours 0.627 (onsets per change 1.593 / 1.757); chord share 0.244 / 0.329;
chord onsets in same-shape runs of 16+: share 0.027 / 0.029 (29.9 / 29.7 onsets per song); longest run 28.3 onsets
4.623 s / 32.9 onsets 6.809 s. Ours moves less on 15 of 23 songs; ours has more long-run chord share on 6, none by
more than 0.1. Agreement (F1@50 0.799): recall 0.794, precision 0.885; chords-only pairs (about 90 per song) recall
0.639, precision 0.807. On matched adjacent pairs the human changes on 0.707, ours on 0.641.
kimochi_warui is the outlier for long runs, but its human chart holds shapes too: runs16 share human 0.258, ours
0.245; longest human 92 onsets (25.514 s, a chord), ours 204 (57.051 s, a single note); recall 0.339 (lowest),
precision 0.853; ours 3.099 onsets per change vs the human's 2.636 (the M8 finding's 7.0 was another chart: the
owner's GPU chart). all_the_small_things: runs16 human 0.147, ours 0.022, recall 0.43.

Takes (raw engine output, four per song): mean spread of changes per onset across the four 0.173; kept take 0.634,
most-moving take 0.746, human 0.697. The most-moving take is the best-F1 take on 2 of 23 songs; choosing it would
cost F1@50 0.034 on average against the kept take (kimochi_warui: seed 202 moves 0.902 but F1 0.477 vs 0.813).

## Part 2.1: pads, Expert drums (19 songs)
Pooled onsets, human / ours: kick 13353 / 13852, snare 9434 / 7912, Y-cym 7622 / 8288, B-cym 6473 / 6707,
G-cym 2927 / 1534, Y-tom 973 / 174, B-tom 970 / 187, G-tom 486 / 1313.
Cymbal confusion (rows human, cols ours: Y, B, G): Y 5278 406 169 (0.902 kept); B 627 4484 500 (0.799);
G 516 1023 579 (0.273). The crash is the problem: 49 % of human crashes become ride, 25 % hi-hat. Ride becomes
hi-hat on 11 %. Per song the ride is lost on take_me_out (0 B-cym: all on Y), s01 0.253, s02 0.146, s12 0.424; the
hi-hat on s04 (0.0) and s03 0.259. Toms: we chart few Y/B toms and put the toms on G (G-tom 1313 vs 486): human Y-tom
328 and B-tom 260 of matched become G-tom. Extra hits (none -> ours) are mostly Y-cym (930); misses (human -> none)
mostly Y-cym 703, B-tom 404, B-cym 358.

## Part 2.2: regularity
Pooled exact-repeat share human 0.197, ours 0.100; mean Jaccard 0.589 / 0.543. Ours repeats where the human repeats
0.276. Ours repeats less on 15 of 19 songs (more on creep 0.375 vs 0.112, pm2, troop). kimochi_warui: 0.743 / 0.269.

## Part 2.3: the rule (pooled F1@50 0.908 before)
| x | F1 after | dF1 | songs up | songs down > 0.01 (worst) | repeat share after (human 0.197) | gap to human (before 0.138) | ours repeats where human does |
|---|---|---|---|---|---|---|---|
| 0.6 | 0.904 | -0.005 | 5 | 3 (-0.029) | 0.484 | 0.287 | 0.742 |
| 0.7 | 0.906 | -0.002 | 7 | 3 (-0.017) | 0.384 | 0.186 | 0.668 |
| 0.8 | 0.908 | -0.001 | 6 | 0 (-0.007) | 0.301 | 0.118 | 0.588 |
Bar not met at any x: pooled F1 never goes up. At 0.8 no song drops by more than 0.01 and the repeat gap narrows
(0.138 to 0.118), but F1 is flat to slightly down; at 0.6/0.7 the rule over-repeats (0.484 / 0.384 vs 0.197).

## Caveats
CPU charts at v0.4.0 only; the drummer's quiet-drums song is not in the set. Drums: 19 songs, set20 human charts
partly five-lane (dropped). The takes are raw engine output (guitar only), F1 against aligned human charts on the kept
folder's decode.wav clock. The confusion's leftover pairing is a convention; the one-cymbal table is the clean one.
F1@50 is timing only (pads do not count), so the rule's effect on pad accuracy is not in it.

## The orchestrator's reading
- **Chord shapes:** not the engine's habit on the CPU charts (0.627 changes per onset against the humans' 0.697; long
  chord holds as common as theirs). The held sections were the owner's GPU chart of kimochi_warui (one change in 7.0
  onsets against this CPU chart's 3.1): M8-02 part A adds the shape changes per onset per take, GPU against CPU. A
  moving take is no answer (it costs 0.034 F1@50). kimochi_warui's CPU chart holds one single note for 204 onsets
  (57 s): a same-fret repeat, M8-02 part C's question.
- **Drums:** the pads are the defect the drummer heard: the crash kept 0.273 (0.49 to the ride, 0.25 to the hi-hat),
  the toms put on green; a pad-aware score first (F1@50 counts no pads), then a crash and ride rule or model, an order
  for M9 unless M8 has a slot. The irregularity is real (exact repeats 0.100 against 0.197) but R(x) fails its bar:
  no regularity rule.
