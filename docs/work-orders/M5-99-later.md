# M5-99: later (the version after this one)

**Nothing to build in this version.** Each item says what it would take and why it waits. Every item that can move
a chart goes through the golden charts and the stress set (M5-09).

## Fast runs thinned by the guitar engine (the owner's finding 3)

- **What is known** (PROGRESS, 2026-11-05, the shred instrumental, 4 CUDA takes): the chart's total is near the
  human charts' (2,137 Expert notes against 2,236 and 2,382), but it peaks at 11 notes a second where both humans
  reach 17, and runs at about 7 a second through 10-second stretches the humans chart at their peak; 47 % of the
  human notes found in passages at 8-12 notes a second against 92 % in the slow first two minutes. The engine is a
  black box whose sampled decoder sets the density; songcharter's stages after it only quantize.
- **The levers, all unmeasured:** the engine's descriptor knobs (the job's `knobs`, with `guidanceScale` 2 and
  `knobsActive`: a speed or density descriptor conditions the decoder; DESIGN 2.7 lists them unused); the inpaint
  model (`job.inpaint` with `regions` and 4 candidates scored at the seams: regenerate a thin window with the
  context on both sides); sampling (T 0.95 / top-p 0.98 are the app's "Standard" preset); more takes, though the
  splice chooses by agreement, which favours the thinner consensus.
- **Why it waits:** every lever needs GPU time to measure (4 takes of a 9-minute song are about an hour on the
  owner's card per setting; the dev machine is CPU-only) and a per-window score, which M5-09 adds. Fixing the
  grid's octave (M5-01) recovers the larger loss on fast songs (the power-metal song's recall 0.45 against the
  engine's own 2,085 notes); the thinning costs the shred instrumental about 0.2 of its notes in its fastest fifth.
- **The spike for M6** (the owner's GPU, `eval/gpu.sh takes`' manner): the shred instrumental with the density knob
  at two settings and T 1.05, 4 takes each, scored per 30-s window; the inpaint path on the three thinnest windows.
  Adopt a setting when the fast windows' F1@100 gains 0.10 with no window losing 0.02 and the references' pooled
  F1@50 unchanged; else record the dead end.

## From the charting-conventions report (`docs/reports/charting-conventions.md`), not taken up in this version

Its ranked gaps 1-3, 5 and 6 are M5-01, M5-02 and M5-03; part of 9 and 10 are M5-04, M5-06 and M4-11. The rest:
- **HOPO, strum and tap states independent of the octave** (gap 4, section 2f): `hopo: "forced"` leaves every
  unforced note to the natural rule on our map, so the played articulation follows our octave. The convention
  reproduces the articulation: the state on the source's own map, written with `N 5` flips. `assemble.HOPO_RULES`
  already has `"source"`; M5-01 measures both on the stress set: the HOPO shares (the humans' differ among
  themselves: 0.21, 0.51 and 0.29 on the power-metal song's three charts, 0.55 on the shred song) and the per-note
  state agreement M5-09 adds to `score.py`. DESIGN C10 chose "forced" because autochart's own map can be at the wrong
  octave too; the owner decides at the gate if the numbers are clear (M5-00 section 8), else here. A day to build
  with the bass engine's state rule in time rather than ticks. M5-01's numbers (1 CPU take, after the octave fix;
  HOPO share ours / the humans', per-note state agreement; the F1s are the same under both):

  | song, part | HOPO share: before, forced / source (humans) | state agreement: before / forced / source |
  |---|---|---|
  | power-metal guitar, 3 charts | 0.29, 0.24 / 0.25 (0.51, 0.21, 0.29) | 0.49-0.51 / 0.65-0.68 / 0.66-0.70 |
  | power-metal bass | 0.21, 0.03 / 0.17 (0.12) | 0.78 / 0.95 / 0.82 |
  | shred guitar, 2 charts | 0.34, 0.34 / 0.42 (0.55, 0.39) | 0.56, 0.66 / 0.56, 0.67 / 0.60, 0.68 |
  | shred bass | 0.11, 0.11 / 0.12 (0.12) | 0.92 / 0.91 / 0.91 |

  "source" helps the guitar a little and hurts the rule-engine bass (its states are its own 120 BPM map's), so a
  mode per part, not one switch, is the likely answer.
- **1/32 and 1/24 burst slots** (gap 2's second half): M5-01 drops a distinct note rather than make a chord of two
  onsets on one tick more than 20 ms apart, keeping the one nearest the tick, and counts the rest
  (`dropped_distinct`). The human charts themselves lose 5.4-6.4 % of the power-metal song's notes that way when
  they go through the quantizer as a perfect engine (their 37.5 ms 32nds and 50 ms sextuplets, which no 1/16 grid
  holds), so that figure is the plan working as intended, and M5-01 reports ours beside it. The finer levels would
  recover those notes: a day, with the slot priors re-measured (DESIGN 2.6). Also recorded by M5-01: `_separate`'s
  moves of 47-168 ms on the references (an onset 0.75 slot or more from its neighbour moves to the next free slot),
  for a look at whether they should drop instead. M5-01's stress run, `dropped_distinct` (and `separated`) per
  part: power-metal guitar 17 of 2,193 (0.8 %; 0), bass 316 of 1,821 (17.4 %, the engine's double onsets on the
  doubled grid's 8ths; 19), drums untouched; shred guitar 52 (2.4 %; 0), bass 81 (3.9 %; 29); rock bass 142 of 968
  (14.7 %; 11). The human charts as a perfect engine: power-metal guitar 5.4-6.4 %, shred guitar 22-24 % (on their
  own map, half our tempo), rock guitar 0.9-1.8 %. Our guitar is under the humans' figure: the engine does not
  catch the bursts yet, so finer slots wait for an engine that does.
- **Fret-quality metrics and repeat consistency** (gap 7, section 2b): exact fret agreement (16-27 %, humans 46 %
  with each other) is the wrong target. M5-09's feel report scores contour (`lane_direction_agreement`), jump sizes
  and big fast jumps against the humans, and repeat consistency (repeated-label sections' fret-sequence similarity,
  against the human chart's own) if it fits its budget; otherwise the measure is M6's with the fix: reuse one take,
  or the best riff, across repeated riffs (found by section labels and self-similarity), which needs repeat detection
  and the larger set.
- **Section names:** Rock Band's "Guitar Solo" for a solo section; it changes the names people pass to `--solos`
  ("Solo 1" on the test song). An hour, with the guide.
- **The song folder** (gap 10, section 8): `song_length` (Encore requires it, the Clone Hero wiki advises against
  setting it by hand), `diff_band` (DESIGN 2.12 plans it), report.json in the folder (an extra file Encore would
  flag; Clone Hero ignores it), the album placeholder (M5-06). An hour each, with the owner's say on report.json.
- **Lyrics** (gap 9, section 7): syllables from the aligner's character timings, so a long word does not light all at
  once; Harmonix's punctuation and capitalisation conventions. A day.
- **Drums** (section 3): the 2x-kick phase (alternate on the grid, not from the run's start), lane accuracy, roll
  lanes, accents, ghosts, the disco flip. The friend plays guitar.
- **Star power** (section 4): phrases that end on a sustain; phrases lined up across instruments for YARG's unison
  bonus.
- **Stems in the folder** (section 11 item 6): an option, not a rule; a new audio path.
- **DESIGN's contradictions** (the report's section 11, ten items): fold the resolved ones into DESIGN at the doc
  pass that follows this version (task 41's restructure), each with the report as its source.

## The grid at double the humans' tempo

The shred instrumental's grid came out at twice the human charts' tempo (octave-tolerant beat F1 0.94-0.96).
M5-01 doubles a grid that is too slow and never halves one: this version builds the doubling pass only, and the
first pass still folds into 85-185 BPM, so a pulse under 85 stays at double with its effects on the HOPO states,
the star-power count (about twice the phrases; M6-01's ceiling at 160 BPM does not reach a 154-BPM grid) and the
solo measures (M5-03 caps solos in seconds for that reason).
A halving rule needs its own statistic (the share of onsets on beat lines, the backbeat ratio M5-01 records for
every song, the HOPO shares) and a check that the natural HOPO threshold (in ticks) still reads right; measure on
the stress set first. Half a day to measure, a day to build. M5-01's statistics for the shred song on its first
grid (153.97 BPM, twice the humans'): density shares guitar 0.059, bass 0.121, drums 0.000 (pooled 0.062, the
right grids' range); backbeat ratio 0.003, the snare on the lines as at the pulse. So neither of M5-01's tests sees
a grid that is too fast, and halving needs another (the snare on every other line, the onsets on odd 8ths). HOPO
share ours 0.34 against the humans' 0.55 and 0.39; star power 3.88 phrases a minute against 2.33 and 3.23.

## Star power on a doubled grid (closed by M6-01)

The phrase rule counts beats (`starpower.py`, about one phrase per 40 beats), so a doubled grid about doubles the
phrases: the power-metal song went from 2.42 to 5.04 a minute against the humans' 3.03-4.44 (M5-01's stress run).
**M6-01:** measured on every human chart, the rate follows the beats (a count in seconds fits worse), a little under
them at 200 BPM (0.84 times); the span's beats are now counted at most at 160 BPM (DESIGN 2.10). Left: the 160 rests on
two 200-BPM power-metal songs (the 20-song set measures it again), and a grid at twice the humans' tempo under 160 BPM
(the shred song's, 154) keeps its doubled count until a halving rule (above).

## Downbeats when the kick is on every beat (M5-01's follow-up)

`beatgrid.bar_phase` puts beat 1 where the kick band most outweighs the snare band. With a kick on every beat, as on
the power-metal stress song's fast beat (the snare on every "and"), it has no margin: 0.013 on the doubled grid,
which is flagged uncertain, and downbeat F1 0.000 against all three human charts while the beats are at 1.000
(M5-01's probe, 1 CPU take). Measures, sections, star power and solos all start on the wrong beat there. A
candidate: the crash or the snare pattern over 4 bars (a crash on beat 1 after a fill, the longest kick or the bass's
note changes), measured on the stress set. Downbeat F1 is reported, not a pass line. Half a day to measure.

## The octave pass's threshold and guard, provisional (M5-01, M5-11)

Since M5-11 the octave rests on the note density alone: `OCTAVE_SHARE` = 0.35, with the doubled tempo at most 300
BPM and 200 onsets; the backbeat ratio is recorded in every report, not a test (DESIGN 2.3 step 7). The threshold
rests on two songs that need doubling, the two power-metal stress songs (pooled 0.623 and 0.527), against nine right
grids (0.001-0.199): margins x1.76 over the right grids and x1.51 under the nearer of the two. The 20-song set
measures it again, with every fast song it gains and the backbeat ratio beside it (a halving rule may want it).

`OCTAVE_EVIDENCE_MIN` = 0.7, the doubled grid's confident share against the first grid's, is provisional too. The
real doublings keep 0.828 (`troop`, x1.18 over the guard) and 0.943 (`pm2`); the second passes of nine right grids
keep 0.63-0.94, because their hats play the 8ths; a doubled grid with evidence only on the first grid's beats keeps
0.5 by construction. So the guard does not stop a false doubling, the threshold does; a guard set too high only
falls back to v0.1's grid, with a warning.

## The second power-metal song on its doubled grid (M5-11)

M5-11 doubled `pm2`'s grid (99.99 -> 199.99 BPM) and adopted it although three of the order's lines failed (DESIGN
2.3 step 7, the table; the orchestrator, 2026-11-06): the guitar gained 0.13-0.15 F1@50 against all five charts and
the drums 0.07-0.19. Each failure is its own item, numbers from M5-11's stress runs (1 CPU take, the merge base
cfc7d5d against the branch):

- **The bass on a doubled grid.** F1@50 against the primary 0.800 -> 0.777 (alt2 0.598 -> 0.595), spread over the
  song: 13 of 15 30-s windows lower, 46 of the 47 lost 50-ms matches outside the tempo change at 215-305 s; matched
  notes 4.4 ms off, as before. Candidates: the bass's 16th-note phase concentration on the doubled grid is 0.099,
  just under the quantizer's `min_concentration` 0.1, so its measured 26 ms offset is not applied (31 ms was, at
  0.26 on the first grid); and 166 notes take the doubled grid's triplet slots (`DOUBLED_BASS_SLOTS`; 2 before).
  M5-11's review counted pm2's bass by tick: 174 notes on triplet slots (2 before), 75 of them unmatched, the
  whole rise in unmatched notes (+67), a median 48 ms from the nearest human note; the matched notes are no
  further off (4.3 -> 4.4 ms), so the numbers point at the triplet slots (the doubled grid's triplets are the first
  grid's 16th-note triplets, finer than its own), not the offset. Measure both on `troop` and `pm2` before
  changing either; half a day.
  - **The triplet slots: done (M6-02).** The bass on a doubled grid has no triplet slots now (`DOUBLED_BASS_SLOTS`
    (2, 0)): bass F1@50 against the primaries 0.716 -> 0.735 (troop) and 0.777 -> 0.787 (pm2), alt2 0.595 ->
    0.588 (DESIGN 2.6). The offset half has no support either: the matched notes' signed median error is 0.9 ms
    (troop) and 4.3 ms (pm2) against the primaries, within 0.3 ms of before on every chart.
  - **Left: the bass's 16ths on a doubled grid.** The doubled bass grid's 8ths are the first grid's 16ths, and it
    has nothing finer, so a 16th-note run of the song's own tempo has nowhere to go. The humans chart 16ths there
    (troop's primary 304 of 1,852 bass notes, pm2's 405 of 2,571, its alt2 1,021 of 3,154). The triplet slots
    matched some of them by accident (a triplet slot is 25 ms from a 16th at 200 BPM): removing them lost 72 of
    alt2's 16ths and 20 of the primary's. pm2's bass is still under its first grid's (0.787 against 0.800 at
    cfc7d5d, `stress.py compare eval/baseline/stress`), troop's above M5-01's 0.716. The answer belongs with the
    burst slots above: finer slots for an engine whose onsets can be trusted at that resolution, measured on the same
    three charts.
  - **Untested: the doubled-bass rules on imported lower levels.** An assemble config that imports every level
    (`take_difficulties: "all"`) on a doubled grid would give Hard, Medium and Easy the bass rules only through
    `part_rules`; no test covers it (M6-02's review: a break giving them the octave-1 rules passes). The pipeline
    imports Expert only. A test, a few minutes.
- **A tempo change under a doubled grid.** Plain beat F1 0.397 -> 0.598 (octave-tolerant 0.658; the humans 1.000),
  downbeat F1 0.014. The grid has the beat count (1,457 beats against 1,435) and a median error of 13.6 ms, but
  about 40 % of its beats are more than 70 ms off, and the build warns of a 170 BPM stretch at 235-300 s that the
  200 BPM grid does not follow (the humans' maps have 330 tempo markers, ours 153). The second pass keeps its hinted
  line straight (`keep_line`, DESIGN 2.3 step 7), which may be what stops it following a change: measure where the
  beats are off (a beat F1 per window in score.py), then whether the tracker inside a straight stretch's bounds
  follows it. Half a day to measure.
- **The guitar's chord share**, narrowed by M6-04 (DESIGN 2.6 step 3): a chord with both neighbours under 120 ms
  is now its top note, which takes `pm2` 0.112 -> 0.065 and `troop` 0.086 -> 0.079 (the humans 0.02-0.05). What
  is left is not in fast runs: `pm2`'s chords at 140-160 ms (ours 0.10 of those onsets, the humans 0.07) and
  `troop`'s in slow passages (both neighbours 300 ms or more away: ours 0.51, the humans 0.22; 85 of its 171
  chords). The humans chord there too, so a rule needs more than speed: the stem (a chord needs simultaneous
  pitches, the feel note's measure) or the engine's own confidence. Measure against the stem first; half a day.
- **The timing measure.** score.py's `timing_err_ms_matched100` median pairs notes a 1/16 apart in dense runs (its
  greedy matching maximizes the count): on `pm2` it reads 10.9-39.4 ms where the 50-ms matches read 3.6 ms against
  the primary and that plus each chart's own offset against the others. `stress.py`'s feel report should give the
  median of the 50-ms matches (or of the nearest neighbours) beside it; an hour with its test.
- **Solos in measures on a doubled grid (closed by M6-01: no change).** M5-03's caps count measures, which halve
  in length when the grid doubles: `pm2`'s long middle solo (267-365 s on the first grid) is capped at 56 measures,
  67 s (303-370 s), and the solo share falls 0.33 -> 0.26 (the humans 0.12-0.35). M6-01 measured the humans' own: on
  both 200-BPM songs their maps are at the doubled grid's tempo and their long solos are 53-58 of those measures
  (pm2's 67-70 s at 303-373 s), which the capped solo covers by 0.96-1.00; a longer cap would pass every human chart
  (DESIGN 2.10).

## The reference set at 20 or more songs, with human-charted solos

PROGRESS `next`. M5-09 makes adding a song one entry in `stress.json` and a build; the cost on the dev machine is
10-18 minutes cold and about 1.2 GB per song (kept folder and stems), so 13 more songs are about 3 hours and 16 GB
on a machine with little room. The songs are the owner's to pick (fast, 6/8 and shuffle, drumless, long, live); for
this version he chose the two hard songs of 2026-11-05 and one ordinary rock song as the guard (M5-00 section 8).

## A one-click updater

M5-07 builds the notice (the owner's decision, 2026-11-05). A button that runs the update would need: the server starting `install.sh` detached from
itself (the install restarts WSL at its end, which kills the server), `--yes` for the licence prompt (the guide's
link must then be shown on the page), the install's log streamed to the page and kept when the window closes, the
Start-menu shortcut's rewrite (the install does it), and the page reopening on the new version. About two days,
and new ways to fail half-way that the pasted line does not have. The notice first; the updater if the friend
finds the line a nuisance.

## The tempo control on the page

M5-01 adds `grid_octave` to the assemble config. A `--grid-octave` CLI flag is an hour; a page control that
re-assembles a finished chart at x2 or /2 without running the engines again (the cache answers; only assemble and
the preview rerun) is a day, with the quick fixes of M4-99 (the downbeat and the offset nudge) beside it.

## Lyrics

- The 50 ms share: 0.45 pooled on the references, 0.68 on the power-metal song, where the humans agree 0.94 with
  each other. The 20 ms emission grid, the star tokens and the syllable spread are the places to look; M5-09's
  timing script measures it. A day to measure.
- On a doubled grid (M5-10): the words snap to its 8ths, so a word the aligner misplaces misses by an 8th; on
  the power-metal song the 250 ms share is 0.950, exactly the bar, and the 100 ms share 0.750. The aligner's
  lead (a median 20 ms early there) is the lever; it needs a second fast song with human lyrics to measure
  against (none in the sets yet). Half a day once there is one.
- Non-Latin scripts (no romanization: words spread between neighbours), and the first-use download's progress line
  on the page (the release gate's deferred item). Half a day each.

## Small things from PROGRESS's deferred list, left for later with their reason

- `song.ogg` not byte-identical between runs (the Ogg page serial): a fixed serial through ffmpeg's bitexact flags;
  an hour, with the determinism rule's wording in DESIGN 1. Not user-visible.
- autochart's engine reports no memory peak of its own; each take's `expert_job.json` says `executionProvider`
  "cpu" while it ran on CUDA: the engine's job file, not ours.
- The 24-hour pruning exemption and a "free the cache" button; the pruning race; Q26 (the grid period to ADTOF);
  the golden charts' blind spot on the separation's code; the separation cache maker as an eval script.
- The cu126 allin1 pairing untested on real hardware; the dev machine's hand-made allin1 Python.
- The lyrics weights fetched at install: decided against for this version (the owner, 2026-11-05: the install stays
  smaller, and the first-use download already resumes and retries); doctor not counting a missing torch or demucs as
  a problem.
- The CI personal-details check, stall logs, the builder-effort trial, DESIGN's split by area (the pipeline review's
  deferred findings).
- M4-08 part A's checks not run (A8-A11, A13, A16, A18-A24, Take Me Out) and M4-08a's harness: the release gate of
  this version runs the few it needs (M5-00); the rest before a later release.
- M4-99's list (native Windows, signing, the highway preview, the metronome, the quick fixes, the polish workspace,
  "Preview in Clone Hero", the weekly cu132 job, settings.ini, time estimates, a window-free start, WSL memory
  tuning) stands.
