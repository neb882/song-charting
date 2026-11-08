# M8-03 measurement report (code at v0.4.0 checkout cfbe62b; labels only; floats 3 dp)

Scripts: A/a_line.py, a_b_sample.py, a_b_arrays.py, a_c_prep.py, a_c_run.py, a_c_drive.py, a_c_metrics.py, a_c_grid.py (+songs_map.py); B/b_engine.py, b_gates.py; C/c_starpower.py; common.py.
JSON: A/a_line.json, A/ab_creep.json, A/ab_test_song.json, A/arrays_*.json, A/a_c_metrics.json, A/grid/*.json, A/chunks/*.json, B/b_result.json, C/c_result.json.

## A-a: the line (24 kept folders)
allin1 peak = 354.5 MB + 17.443 MB/s (1.022 GiB/min), residuals -233 / +202 MB (matches the planner's 346 + 17.5). Parent's high-water mark (pipeline.json, whole run) = 614 + 5.5 MB/s, residuals -1228 / +648 (it mostly comes from earlier stages).
Longer than 7 min: pm2, sooth, s06, s08 (and s09/s11/test_song at 6:55-6:58).

## A-b: the parent while allin1 runs (creep 4:00, test song 6:52; cold sections stage, rest from cache, 0.5 s sampling)
| song | parent RSS while child runs | child max | tree max | allin1's own VmHWM |
| creep | 1127-1209 MB | 4492 | 5701 | 4498 |
| test song | 1579-1719 MB | 7532 | 9251 | 7554 |
Parent while child = 499 + 2.96 MB/s (two points). Tree = 853 + 20.4 MB/s (fits both within 0.6 %). The parent's earlier-stage peak (1341, 1985 MB) is higher than during allin1 and not in the tree.
Arrays (a_b_arrays.py, MiB per minute of audio): mix 20.6, six stems 121.1, fold "other" sum 20.2, int16 payload 20.2, astype copy 20.2, tobytes copy 20.2. Held while the child runs: mix + 6 stems + payload + the bytes handed to subprocess = about 182 MiB/min; the payload array (20) and the stems and mix (142) could go: 162 MiB/min = 0.158 GiB/min.
From pipeline.py: after the sections stage only `mix.shape[1]` and, with --lyrics, `stems["vocals"]` are read from memory (the guitar stage does `del mix, stems` and reads decode.wav; assemble reads files). So freeing mix, six stems and payload once the cache key and bytes are made saves 1.42 GiB for 9:00 (1.53 GiB for s06) and reloading costs: all 7 WAVs 1.07 s (4:00), 1.28 s (6:52), warm page cache; only vocals (0.2 s) if lyrics. Cold-disk read speed not measured. **The release bar (>= 1 GiB at 9 min, reload < 10 s) is met.** Tree with release = 853 + 17.7 MB/s.

## A-c: chunks
Whole-song reproduction in process (a_c_run.py, runner's own spectrogram/_model/postprocessing, 2 threads): break and creep identical to the kept segments.json (beats, downbeats, bpm, segments). Chunk outputs: all 24 songs x W 120/180/240 (overlap 30 s, linear crossfade of beat/downbeat/section/function logits, allin1's postprocessing on the stitched whole).
Bar (beat F1>=0.99, downbeat F1>=0.98 at 70 ms, bpm within 1 %, segment-start F1 at 1 s pooled>=0.95 and >=0.90 each):
- W120: pooled seg 0.970, min 0.897; fails 8 songs (kimochi_warui seg; take_me_out bpm; s01, s02, s07, s09, s10, s11 beats/downbeats; s09, s11 bpm; worst beat 0.810, downbeat 0.762, s11 bpm ratio 2.0).
- W180: pooled seg 0.987, min 0.900; fails lucretia (bpm 1.010), s02 (beat 0.986), s08 (downbeat 0.789), s11 (beat 0.934, downbeat 0.916).
- W240: pooled seg 0.996, min 0.966; fails s02 (beat 0.970, downbeat 0.957), s07 (beat 0.986), s11 (bpm ratio 0.664); 6 songs identical.
**No W in {120,180,240} meets the bar.** Per-song numbers in A/a_c_metrics.json.
Grid (a_c_grid.py: first grid, halving pass / doubled route from allin1 beats, with_downbeats; 23 songs, halved: s02, s04, sooth; doubled: s01, s10, troop, pm2): the octave decision (and doubled route's decision) is identical to the whole run's on every song at every W. Grid beat F1 against humans within 0.005 of the whole's on every song at W180; W120 off on pm2 (+0.005 beat, +0.006 down), s10 (+0.007, +0.008; grid vs whole's grid 0.961/0.953); W240 off on s02 (-0.017 beat, -0.029 down; grid vs whole 0.938/0.932); s02 also at W180/W120 grid vs whole 0.980/0.979. The octave of today's report is reproduced from the whole run on all songs.
**Memory finding:** chunking the network does not lower the child's peak. VmHWM per W: creep 4333/4416/4424, s06 10324/10344/10432 (whole: 4527, 10389 records); fits 209+17.40, 295+17.34, 364+17.29 MB/s vs 354+17.44 whole. The phase peaks (a_c_run.py) show why: after the spectrogram and the network (all windows) VmHWM is only 1994 MB (creep) / 4375 MB (s06) (~0.41 GiB/min, 330 MB + 6.9 MB/s); the rest is allin1's postprocess_metrical_structure (madmom DBN beat decoder, 26-33 s of the run's 40-130 s, ~0.6 GiB/min), which still runs on the whole stitched song. Network inference is 8-28 s of a run. A memory fix needs the DBN decoded in windows, not the network; not measured (an untried lead: child peak would sit near 330 + 6.9 MB/s, 4.4 GB at 9:43).
Run seconds (total, 2 threads, with other jobs on the 4 cores): same as whole (creep 56-58 s; s06 131-138 s).

## A-d: what a PC needs (MiB; reserve 1 GiB; tree = parent + child)
| | tree peak vs length d s | longest fitting 10.2 GiB | 11.2 GiB |
| today | 853 + 20.4 d | 7.0 min | 7.8 min |
| arrays freed | 853 + 17.7 d | 8.1 min | 9.0 min |
| chunks (any W), no release | about 700 + 20.4 d | 7.2 min | 8.0 min |
| chunks + release | about 710 + 17.7 d | 8.2 min | 9.2 min |
Residual +-200 MB shifts each length by about +-0.2 min. **L (the length above which M8-05 would chunk / do something else, after the release) = about 8.0 min (8.1 central; 7.9 with the +200 MB residual).** Of the 24 kept songs 3 (s06 9:43, sooth 9:09, pm2 7:23; s08 7:17 borderline) pass it. Since chunking does not cut the peak, L is where the release alone stops being enough.

## B: bass unpitched-onset gates (21 songs with a human bass chart; v0.4.0 bass.py steps; pooled = 18 songs, s06/s08/s10 out; ntl skipped: its work folder is gone)
Only 65-85 % of the chart's bass onsets match an engine onset within 40 ms (others use the chart time for the voiced share). No-voiced-frame 20-150 ms after onset.
| candidate | removed | songs | precision | pooled dF1@50 [CI] | songs down >0.01 | max human notes removed |
| g1 | 233 | 17 | 0.382 | -0.001 [-0.004, 0.003] | s12 -0.010 | 2.5 % (9 songs >= 0.5 %) |
| g2 L4 G110 | 12 | 4 | 0.417 | 0.000 [0.000,0.000] | none | 0.5 % (s02) |
| g2 L4 G150 | 41 | 10 | 0.195 | -0.000 [-0.001, 0.000] | none | 0.7 % |
| g2 L6 G110 | 3 | 1 | 0.667 | 0 | none | 0 |
| g2 L6 G150 | 12 | 4 | 0.167 | 0 | none | 0.3 % |
| g3 (all four) | 0-2 | 0-2 | 0.0 (2 removed) | 0 | none | <= 0.1 % |
Repeat share (mean): ours 0.585, after g1 0.580, humans 0.487. **Bar (precision 0.75, F1 +0.005 with CI>0): no candidate meets it** (best precision 0.667 on 3 onsets; g1 removes real notes 62 %). Full grid in B/b_result.json.

## C: star power at a slow tempo (reproduction of today's placement equals each chart's own star power, tick for tick, on all 24 songs; non-slow songs unchanged at B=100, asserted)
Slow songs (rate/min today -> B100 -> B120; humans' range): creep 2.32 -> 2.58 -> 3.09 (3.33); lucretia 2.34 -> 2.60 -> 3.12 (2.34, one chart: moves away); sooth 1.89 -> 2.45 -> 3.00 (2.34-3.23: into range); s02 2.16 -> 2.56 -> 2.95 (1.03-2.52: inside, B100 leaves it by 0.03); s04 1.90 -> 2.53 -> 2.74 (1.82-2.52: leaves by 0.01 / 0.22); s13 2.23 -> 2.45 -> 2.90 (2.20-2.42: leaves by 0.04 / 0.48). Overlap of our phrase notes inside human phrases, pooled over slow songs: 0.178 today, 0.145 B100, 0.144 B120 (lower). B=120 also changes kimochi_warui, take_me_out, s08, s09, s11 (grid 100-120 BPM).
**Bar (M8-09): fails at B100 and B120** (lucretia, s02, s04, s13 move away or out of range; overlap lower).

## Housekeeping
Kept folders (work, stress-work, set20-work): listing hash before/after A-b in A/kept_before.txt and kept_after.txt. Copies and <shm>/m8 removed.
Paths in scripts are placeholders: <repo> the checkout, <wt> worktrees dir, $DEV the dev data dir, <shm>/m8 scratch in /dev/shm, <scratch> the scratchpad (code checkout at <shm>/m8/code-cpu = v0.4.0).
