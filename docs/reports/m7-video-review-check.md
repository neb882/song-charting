# Independent review of the video reviews and the orchestrator's verdicts (2026-11-07)

Read: the three reviews, the verdicts, the check, M7-00..08, part A's tables and part B's report, the code on main, the four charts (note tracks, SyncTrack, report.json), the stress scores, the CPU stress run's sooth chart. Counts below are mine (a parser over the note tracks and SyncTrack, scratch deleted). A = agree with the verdict, P = partly, D = disagree.

## 1. The claims

| # | claim | review | verdict | mine | reason |
|---|---|---|---|---|---|
| 1 | halving is a bug; block under 85 | wrong | wrong | **A** | humans at 77; beat F1 0.644 -> 0.985 (stress scores). Also: beatgrid's "click" is the *low-evidence* fallback (confident share < 0.60, `beatgrid.py:869`; ntl's first grid 0.498), not a "verified studio click": the review's premise is false |
| 1a | halved grid makes picked 8ths HOPOs | right | real side effect | **A** | 1592 of 2413 sooth notes in natural-HOPO position; humans' shares 0.55/0.39 vs ours 0.65; part A base state agreement 0.525 vs humans' 0.741 (A-a): the largest articulation gap of the 23 songs |
| 1b | halved slots cap shred | right | wrong cause | **A** | `dropped_distinct` 30 of 2485; 977 notes already sit at the finest slot (24 ticks = 97 ms); the engine wrote too few (1-s peak 11 vs humans' 17) |
| 1c | ntl intro warps 75 -> 86.9 -> 74.3 | right | real, our bug | **A**, but the diagnosis is narrower than the cause: see 3 |
| 1d | bass slots (2,0) starve pm2's bass | right | measured choice | **A** | M6-02 +0.023 F1; pm2 bass concentration 0.185: the onsets fit no grid, the slots are not the cause |
| 2 | pm2's 140/170 BPM crater is a hallucination | wrong | wrong | **A** | beat F1 0.987-0.989 against 5 human charts over 1464 beats: a wrong 45-s crater would cost ~0.09 |
| 3 | N5 on chords by our natural rule | mechanism wrong | engine's token | **A** | `quantize._natural` needs `len(frets)==1` (451-454); the engine's `is_hopo` becomes modifier 5 on any note, chords included (`chartEventStream.mjs:139,235`); ntl's 18 N5 are all on chords, 0 on single notes |
| 3a | forced strums kill solo HOPOs: tod 118/119, pm2 669 | partly | right | **P** | tod 118/119 right. pm2: 163 N5 in all (`flips` 163), 101 of 1232 natural positions (8 %, not 54 %); Solo 2A 1 of 29 flipped (review: 26/27), Solo 3 5 of 101 (41/53); the real cluster is Solo 4A, 27 of 64. The verdict took pm2's number on trust |
| 3b | pm2 452 of 684 taps on same fret | wrong numbers | right | **P** | 445 taps, 47 on a repeat (Intro 16); sooth 6 of 161. The pattern is real on the Intro only; A-e: humans' taps on repeats 0.003-0.03 (pm2), 0.36 (sooth alt) |
| 4 | bass jackhammer, drones as 16ths | right | real, dead end v0.4 | **P** | B-b's gate hurts (precision 0.39-0.48) and 88 % of repeats are same-pitch onsets: agreed. But ntl's case (489 of 787 notes at 24 ticks = 10 notes/s on a ballad, 74 % repeats) is a *run* pattern the tested gate (per onset, 40 ms) never isolates; B's caveat says a longer held window was not tried. Re-measure one run rule (>= 6 same-lane onsets <= 110 ms apart, voiced throughout) on B's scripts before closing M7-03: hours, not days |
| 5 | fast runs on one fret | right | engine's; M8 spike | **A** | A-e: ours 0.251 vs humans 0.180 in fast runs; s01 0.63 vs 0.07, troop 0.53 vs 0.29 |
| 6 | 420 opens on pm2 | right | real; humans' share pending | **A** | A-e: pm2 open share ours 0.000 on the CPU chart vs the GPU's 420: the GPU take, not a rule; open2green +0.0014 pooled: nothing to build |
| 7 | take-0 bias 0.05 | right | right; part C | **A** | `takes.MARGIN` 0.05; sooth 17 of 22 windows have a higher scorer, 4 switched. Note the score is agreement among takes, not truth: part C is the right test |
| 8 | prune silent-stem onsets | would hurt | dead end | **A** | B-a guitar precision 0.09-0.14; drums 0.875 only at 8 onsets |
| 9 | vibrato re-triggers, sustains dropped | right | right | **A** | A-d: every repeat-removal rule lowers F1 (best -0.0024); sooth repeats 0.127 vs humans 0.19: the humans repeat more than we do. The floor in seconds (A-c) is the live part |
| 10 | drumless drift | known | dead end | **A** | B-d: sooth's stretches 0.983 (ours) vs allin1 0.76/0.92; allin1_oct +0.060 but 7 of 36 down |
| 10a | kick walls, no fill crash | mostly wrong | mostly wrong | **A** | kick precision 0.911; crash 0.348 |
| 11 | solo caps | no evidence | owner's judgement | **A** | share: no instrumental over 0.40. max_solos 4: +0.012, CI touches 0, no song moves away: cheap, harmless, owner's taste |
| 11a | rhythm/lead mixing | engine's | deferred | **A** | judgement; no stem separates them |

## 2. What both missed

1. **The owner's sooth chart runs at 160 BPM for its last 28 s.** Its SyncTrack ramps 82 -> 160 BPM over 509-516 s and stays there to 537.8 s (162 guitar onsets after 509 s); the CPU stress chart ends at 80 BPM and scores beat F1 0.985 against the humans, so the humans are at 77 there. Cause: the owner's allin1 gave 722 beats on 544.8 s against the CPU's 689 on 549.3 s (33 extra = ~26 s at double tempo), and the halved free grid follows allin1's beats wholesale. No warning fired: `tempo_check` runs in the halved fold (42-92 BPM), where 160 folds to 80, and `drift_ms` p95 16.7 s (CPU 3.7 s) is recorded but not tested. The video ended at 248 s, the check compared only the grid headline (M7-00 §8.7). Consequence: the release gate's GPU check must diff the SyncTrack and read `drift_ms`, since allin1 differs by device and the halving pass inherits its shape.
2. **The warp displaced ntl's notes:** 8 of 42 guitar onsets in 4608-8640 are off the 8th grid against 3 of 407 elsewhere; the intro's guitar is otherwise 0 off. A cheap per-stretch measure for 1c's fix.
3. **The sanitised `charts/*.report.json` still carry the work-cache folder names** (titles and hashes) in `audio.path`, `sections.source` and `parts.*.takes.sources`; the brief said home paths were removed. Scrub before anything leaves the scratchpad.
4. The intro warning "beats at 0-26 s follow the straight line" is false on a tracker-started grid: they follow allin1's smoothed beats (see 3). Say which.

## 3. The 1c fix

The real cause is `beatgrid.py:822`: with `start=` given, `line_ev is None` makes `use_tracker` true unconditionally; the base becomes the LOESS of allin1's beats (833-836) and where drum support runs out the free curve fades to that base (853-856), i.e. to allin1's wander. The orchestrator's rule (every other beat of a *click* first grid) is right in direction and does cure ntl, but:
- "click" means confident share < 0.60, so the rule flips on a threshold unrelated to the fault: sooth's first grid was free at 0.667, ntl's click at 0.498; a song at 0.61 keeps today's path. Make the choice the halved grid's own: fit the line through the halved start beats and compare evidence with the same `TRACKER_MARGIN`, as the internal tracker is compared.
- A real tempo change under a click first grid (ritardando, a drumless section) is missed by the line either way; the rule is then no worse than the unhalved grid the song would otherwise get, so it is safe, not better.
- Parity: every other line beat has two phases. ntl's allin1 gained 1.5 beats over 19-33 s, so its intro and body sit on different parities; the majority (body) parity moves the intro's lines 0.4 s from where allin1 put them. Whether that lands on the plucks only the audio says: `onset_phase` of the guitar stem over 0-35 s per candidate grid.
- Add the missing guards whichever path wins: `tempo_check` at the first grid's fold on a halved grid, and a warning on `drift_ms` p95 over, say, two beats.
- Measure (in process from kept folders, no engine, half a day, ~2 % of the week): the three halved songs with humans (sooth, s02, s04) and the halved 20-song songs, beat F1 whole-song and per B-d stretch for today's grid, every-other-line, and line-faded allin1; ntl: the tempo_check window gone, off-grid onsets in the intro, onset_phase concentration; the owner's sooth file's tail.

## 4. v0.4 priorities

- **Add** the halved-grid fix with its guards (3) in M7-07's wave-4 slot, since M7-07 is otherwise closed: a wrong grid wrecks a whole stretch for the player, the other findings nudge notes. Cost ~1 day, 3-4 %.
- **Keep** M7-02 (part A's R1/R2 are still empty in the tables; sooth is the gap), M7-05 pending part C, M7-08 if the owner runs it.
- **Reorder** the release gate: SyncTrack diff and `drift_ms` CPU vs GPU per song, before the recounts.
- **Close** M7-04 and M7-06 (owner may take max_solos 4 on taste). **Close M7-03 only after** the one run-rule re-measure above (hours).
- **Drop** nothing else; no engine setting in M7 stands.

**Verdict.** The orchestrator's verdicts are right on every diagnosis that matters (halving, the crater, the chord HOPOs' mechanism; the dead ends are measured, not argued); it over-credited two of the review's pm2 numbers (3a, 3b) and under-diagnosed 1c, whose root is the tracker-start path in beat_grid, not the click case alone. Neither saw the owner's sooth chart doubling to 160 BPM in its outro, the one finding here that should change v0.4's plan: fix and guard the halved grid's tempo shape, and make the GPU gate read it.

## The orchestrator's routing (2026-11-07)

Accepted: the corrections to 3a and 3b (the first review's pm2 counts were wrong); 2.1 confirmed on a CPU chart of the same audio file (the identical tempo map, so the audio file, not the device: the halved grid follows allin1's beats into a doubled outro); 2.3 scrubbed. Section 3 and 4 became M7-09 (the halved grid's tempo shape, with the guards), M7-03's run-rule re-measure and the GPU check's tempo-map diff (M7-00, the changes of 2026-11-07 evening). On 6: the CPU takes write no open notes and the GPU takes do, so the open-note question needs GPU takes (part D).
