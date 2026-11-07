# M6-03: downbeats on fast songs (builder's report)

Branch `m6-03-fast-downbeats`, worktree `<wt>/m6-03`, from main a89d6a0 (after M6-05). Main had not moved when
this report was written, so there was nothing to merge in.

## Commits

- `1c1d746` The bar phase from allin1's downbeats (M6-03): `songcharter/beatgrid.py`, `songcharter/assemble.py`,
  `songcharter/sections.py` and their tests.
- `be8b74c` DESIGN 2.3 step 4 (the measurement, the rule, the golden and stress results), step 7's and M6-05's
  pointers to this order, and the M5-99 item narrowed.

## The measurement (step 1)

**Method.** `<scratchpad>/m6-03/measure.py` rebuilds each song's grid from its kept folder's stems with the code
under test. It replays the report's octave and the second pass's start, and asserts that the beat count, phase
and margin match the run's report.json; all eleven matched. The human charts' measure lines come from
`eval/scorer/score.py`'s own functions (`scan`, `chart_delay_ms`, `downbeat_times`), with each score JSON's
alignment shift and ref span. Downbeat F1 is score.py's (±70 ms, `match`/`prf`/`n_cand_eff`). Only numbers were
printed; no chart was opened.

The runs used were M6-05's (m6-05-new, m6-05-stress-new). I measured again on the orchestrator's before runs on
main after M6-05 (main-m605 and main-m605-stress, a89d6a0). Every phase, vote and F1 was identical, pm2's
included.

**The candidates.**
- The kick's phase: today's `bar_phase`.
- The first grid's downbeats carried onto the doubled grid: each one moved to its nearest beat, and the phase most
  of them fall on.
- allin1's downbeats from `sections/segments.json`, by the same vote within a quarter beat.
- A vote of the three: two that agree, else the kick's.

For information only:
- the best of the four phases (an oracle);
- allin1's downbeats as raw times;
- allin1's bars one by one (each downbeat snapped as a bar line, split in two on a grid at twice allin1's rate).

| song (charts) | grid BPM (octave) | kick: phase, margin | allin1 votes per phase, margin | kick (today) | carried | allin1 | vote | bar by bar |
|---|---|---|---|---|---|---|---|---|
| All the Small Things (1) | 147.6 (1) | 3, 0.001 | 0/0/0/99, 1.000 | 0.980 | = | 0.980 | 0.980 | 0.985 |
| Creep (1) | 92.3 (1) | 0, 0.194 | 89/0/0/0, 1.000 | 0.972 | = | 0.972 | 0.972 | 0.989 |
| Drunk Drivers (1) | 117.0 (1) | 0, 0.000 | 103/0/0/0, 1.000 | 1.000 | = | 1.000 | 1.000 | 0.986 |
| Kimochi Warui (1) | 107.0 (1) | 2, 0.014 | 125/0/0/0, 1.000 | 0.000 | = | 1.000 | 0.000 | 0.996 |
| Lucretia (1) | 98.2 (1) | 3, 0.110 | 2/0/22/63, 0.471 | 0.660 | = | 0.660 | 0.660 | 0.927 |
| Take Me Out (1) | 105.3 (1) | 3, 0.010 | 30/0/0/77, 0.439 | 0.706 | = | 0.706 | 0.706 | 0.973 |
| test song (none) | 142.0 (1) | 0, 0.616 | 231/0/0/0, 1.000 | — | = | — | — | — |
| troop (3) | 200.0 (2) | 2, 0.013 | 121/0/0/0, 1.000 | 0.000 | 0.000 (margin 0.095) | 0.998–1.000 | 0.000 | 0.984–0.986 |
| sooth (2) | 154.0 (1) | 1, 0.040 | 77/73/0/20, 0.024 | 0.278–0.281 | = | 0.297 | 0.278–0.281 | 0.657–0.664 |
| break (2) | 115.5 (1) | 1, 0.009 | 0/85/0/0, 1.000 | 0.988–1.000 | = | 0.988–1.000 | 0.988–1.000 | 0.975–0.988 |
| pm2 (5) | 199.9 (2) | 3, 0.013 | 177/0/0/0, 1.000 | 0.000 | 0.000 (margin 0.898) | 0.978–0.985 | 0.000 | 0.980–0.986 |

"=" means the first grid is the grid, so the carried phase is the kick's. pm2's first grid had phase 0 with margin
0.100; carried by time onto the doubled grid (which starts from allin1's beats since M6-05) it lands on phase 2,
two beats off.

- allin1's phase equals the oracle on every chart (19 of 19). It is the only candidate that fixes troop and pm2.
- It also fixes Kimochi Warui (0.000 → 1.000; the kick on 1 and 3 alike, two beats off) and leaves every other
  reference and break where they were.
- The vote is useless: on octave-1 songs it is the kick's, and on the doubled songs the kick's or the carried
  phase.
- No tuning: snap windows of 0.1, 0.25 and 0.5 of a beat give the same phase on all eleven songs. The vote has no
  threshold.
- Bar by bar would gain on Lucretia and Take Me Out (their phase changes inside the song). But allin1 skips
  downbeats (bars of 5–30 beats on six songs, the test song among them), and it would take the chart out of 4/4.
  It is left to the meter (M5-99).

## The rule (step 2)

`beatgrid.downbeat_vote(beats, times)`: each time votes for its nearest beat when it lies within
`DOWNBEAT_SNAP` = 0.25 of that beat's local period. It returns the phase (index mod 4) with the most votes, the
margin ((top − next) / votes; a tie goes to the lower phase), the counts and the number voting.

`beatgrid.with_downbeats(grid, times)`:
- It returns the grid with downbeats every 4 beats from the voted phase.
- `stats.downbeats` gets phase, margin, `uncertain` (margin < `DOWNBEAT_MIN_MARGIN`, 0.15), `source: "allin1"`,
  `vote` (counts, given, voting, window) and `kick` (the kick's phase, margin and flag). The kick's scores and
  windows stay.
- With no times it returns the same grid. When none votes, it returns a copy with the kick's phase and the vote
  recorded.

`beat_grid` now records `source: "kick"`.

`sections.read_allin1_downbeats` reads the times as `read_allin1_beats` does; both now share `_read_times`.

`assemble`:
- After `_octave_pass`, `grid = with_downbeats(grid, _read_allin1_beats(cfg, downbeats=True))`, so the phase
  applies to whichever grid the octave pass returns. That includes a grid M6-06's halving would return, without
  that order having to pass anything.
- `check_inputs` reads the downbeats too, so a bad file fails before any work.
- report.json `grid.downbeat_source`.
- The uncertain warning names allin1 when it is the source.
- A new warning fires when allin1's phase overrides a sure kick phase (margin ≥ 0.15). It fires on none of the
  eleven songs: Creep and the test song have sure kicks, and allin1 agrees with both.

**Where it sits.** The order allows "assemble.py's octave pass only to carry a phase". I put the one call in the
grid stage right after the octave pass, not inside it. `_octave_pass` and its `second_pass` lambda are untouched,
so M6-06's octave-pass changes should merge cleanly, and its halved grid gets allin1's phase automatically.

## Tests (step 3)

Made-up beats, onsets and synthetic drums:
- `tests/test_beatgrid.py`:
  - `test_downbeat_vote_counts_the_beats_the_downbeats_fall_on`: phase, margin, window, local period, tie, none.
  - `test_allin1s_downbeats_set_the_bar_on_a_kick_on_every_beat`: the 198 BPM skank, kick phase flagged, allin1's
    downbeats every 8th beat two beats from the kick's guess.
  - `test_allin1s_downbeats_on_an_ordinary_song`: the rock beat with allin1 agreeing; None returns the same grid;
    downbeats half a beat off keep the kick's phase.
- `tests/test_sections.py::test_read_allin1_downbeats`.
- `tests/test_assemble.py`:
  - `test_the_bar_phase_follows_allin1s_downbeats`: two real assemble builds. One has allin1 on beat 3 against the
    sure kick on beat 1 (phase 2, the warning, the first measure line at beat 2). One has split downbeats (the
    uncertain warning with allin1's text).
  - `test_check_inputs`: the downbeats are checked.

**Breaking the code** (`<scratchpad>/m6-03/mutate.py`): 15 breaks, each caught.
- With_downbeats ignoring the times.
- The vote off by one.
- No window.
- A global period.
- The margin as a share.
- A tie going to the higher phase.
- The kick's flag kept.
- No kick record.
- assemble not applying it.
- assemble reading beats instead of downbeats.
- check_inputs skipping the downbeats.
- No disagreement warning.
- The kick's warning text.
- sections reading "beats".
- No `downbeat_source` in the report.

Each of the two song tests fails on its own break: ignoring the times and the off-by-one fail both, and no window
fails the ordinary one.

## Checks

- **Suite** (`tools/heavy.sh python -m pytest -q -p no:cacheprovider --basetemp=<shm>/pt-m6-03`, at 1c1d746):
  `1106 passed, 5 skipped in 847.28s`.
- **Golden** (`python -m eval.golden run --code <wt>/m6-03 --out $G/m6-03-new --threads 2 --rerun bass,sections`;
  diff against `$G/main-m605` with `--expect none`): exit 1, 13 UNEXPECTED.
  - **Kimochi Warui's 12 tracks.** The bar phase moved two beats, as this order intends. Expert onsets and F1@50
    are identical (guitar 0.827, bass 0.758, drums 0.977). The lower levels moved 0–6 onsets: guitar Hard
    771→770, Easy 336→335; bass Easy 110→104; drums Hard 689→697, Medium 448→449, Easy 380→381. Downbeat F1 went
    0.000 → 1.000.
  - **The other six songs are unchanged** in every hash, count and score. The test song keeps phase 0, now from
    allin1. The pooled F1 is +0.0000 on every part and level, and beat F1 is 0.8755 → 0.8755.
  - **The run-level flag:** "the new run's drums answered from the kept folders (made by 8ba3cbd), but drums's
    files differ in its code". `beatgrid.py` is in the drums engine's ENGINE_FILES. The engine
    (`engines/drumlanes.py`) imports only `estimate_tempo` and `onset_features` from it, which this diff does not
    touch. Its cache key holds that tempo estimate, and the kept output answered, so the drums output is this
    code's. Clearing the flag formally needs `--rerun drums` on both runs. I did not make my own before run, as the
    brief says; the orchestrator may want that pair.
- **Stress** (`eval.golden run --refs $EVAL_DATA/stress --work $G/stress-work --code <wt>/m6-03 --out
  $G/m6-03-stress-new --rerun bass,sections`, then `stress.py score` and `stress.py compare $G/main-m605-stress
  $G/m6-03-stress-new`): exit 0, "Regressions (a primary F1@50 down by more than 0.01): 0".
  - Every Expert F1@50, star power phrases a minute and solo share is identical against every chart.
  - Downbeat F1 against the primary: troop 0.000 → 1.000, pm2 0.000 → 0.979, sooth 0.278 → 0.297 (not lower),
    break 0.988 → 0.988.
  - **pm2's lower levels** (against the primary, main-m605-stress → branch):
    - Easy guitar 0.113 → 0.767 (it was 0.515 before M6-05), Easy bass 0.089 → 0.897 (0.559).
    - Hard guitar 0.667 → 0.667, Medium guitar 0.783 → 0.783; Hard bass 0.697 → 0.696, Medium bass 0.877 → 0.877.
    - Drums Hard 0.858 → 0.855, Medium 0.459 → 0.456, Easy 0.378 → 0.392.

    So the Easy guitar and bass came back, and past their pre-M6-05 values. The drums' Medium and Easy did not
    (0.579 and 0.553 before M6-05): their fall under M6-05 was not the bar phase.
  - **troop's lower levels**: guitar Medium 0.717 → 0.699, bass Medium 0.565 → 0.549, drums Medium 0.920 → 0.907,
    drums Easy 0.870 → 0.857, bass Easy 0.676 → 0.682, the rest equal. Against alt1, guitar Medium 0.575 → 0.564.
    The cause is unexplained; it is in DESIGN and M5-99.
  - **sooth's lower levels** are within ±0.007; its phase moved one beat on a vote with margin 0.024.
- **CI**:
  - At 1c1d746: <repo>/actions/runs/42314012695. Success: windows and linux. The
    linux Suite step ran 1107 passed, 4 skipped, and all 8 Linux hooks passed.
  - At be8b74c, the branch head: <repo>/actions/runs/42320960525. Success:
    windows and linux, head SHA be8b74c9. The linux Suite step ran 1107 passed, 4 skipped, and all 8 Linux hooks
    passed.
- **Privacy**: `EVAL_DATA=$DEV/eval python3 -I eval/privacy_check.py` before each push: 271 files, 0 found.
  I scanned `git diff origin/main...HEAD` and the commit messages for model names, paths, emails and lyrics: none
  beyond the required trailers.

## What M6-06 changes

- Only sooth's row: M6-06 halves its grid (154 → 77).
  - allin1 reads sooth at 76.9 BPM, the humans' rate; as raw times its downbeats score 0.965 and 0.997 against
    the two charts. So on a halved grid its vote should be clear.
  - The 0.297, its 0.024 margin and its lower-level deltas must be measured again after M6-06 merges.
- No other song changes (M6-06's step 1: the other ten grids are at allin1's rate).
- When main brings M6-06 in: rerun the stress set (`--rerun bass,sections`, both sides) and `measure.py` on sooth.

## Not done, or uncertain

- DESIGN outside 2.3 still describes the kick phase: 2.4's Goal 1 line ("4/4 throughout, with the bar phase from
  kick vs snare energy") and the stage overview's Meter row (§2 table, line 264). The brief allowed only 2.3.
  PROGRESS and the work orders other than M5-99 were left to the orchestrator, as the brief says.
- `songcharter/cli.py` prints "downbeat phase N (margin X)" without the source. It is outside the allowed files.
- troop's Medium levels fall by 0.013–0.018 when its bars move to the humans' phase. This is unexplained. The
  stress check reads Expert only, but the order's "every F1@50 not lower" is not met there if it means every
  level.
- The golden diff's drums flag (above). It is a file-level false positive by the reasoning given, but it is
  formally UNEXPECTED.
- The vote has no minimum count: a sections file with a single downbeat near a beat decides the phase. Real allin1
  output has one per bar.

## The orchestrator's decisions and review fixes (commit 310d91f)

- **The golden diff's drums flag is a false positive, accepted without a `--rerun drums` pair.** The review read the
  drums engine's imports: `drumlanes.py` takes only `estimate_tempo` and `onset_features` from beatgrid, `adtof.py`
  none; beatgrid.py is the only engine file that differs from the kept folders' commit, by this diff only, and
  eval/golden.py's check compares whole files. The other 12 UNEXPECTED entries are Kimochi Warui's intended change.
- **troop's Medium levels, lower, accepted.** The review found why: our Medium keeps three beats of a bar and thins
  the last; on the old phase that was the humans' beat 2, now their beat 4, which they play a little more (192
  against 175). The old phase scored higher by accident; which beat a lower level thins is the ladder's calibration
  (M5-99). pm2's lower drum levels fell under M6-05, not here (M5-99).
- **R1** (major, a test gap; no code defect, so no skeptic: the fix is a test): the stretch song's test now asserts
  allin1's phase on the doubled grid and the bars on its downbeats; the vote moved before the octave pass fails it.
- **R2**: a grid whose kick phase is not 0 keeps it when no downbeat votes (the reset to 0 fails it).
- **R3**: a one-beat case pins "1 beat(s) after the kick's beat 1" (the sign flipped fails it).
- **R4**: a split vote (margin under 0.15) whose two top phases hold a sure kick phase keeps the kick's. On the
  eleven songs the kick is sure only on Creep (0.19) and the test song (0.62), both with a vote of margin 1.000, so
  the rule changes none of them (read from the runs' report.json); a test holds it, and a split between two other
  phases still takes the vote's top phase, flagged.
- DESIGN 2.4 and the stage table say where the bar phase comes from; the summary line prints its source.
- CI on 310d91f: green (run 42325185266; the linux suite and hooks, Windows).

## Review (sc-reviewer, 2026-11-07): M6-03 review (branch m6-03-fast-downbeats, be8b74c, against a89d6a0)

Scripts and logs: `<scratchpad>/m6-03-review/` (mut.py makes each break in a copy, run.sh runs the covering tests,
run.log the results; troop.py / sub.py / ts.py the level analysis, numbers only; tie.py the tie repro).

## Findings

**R1 (major, test gap; the code is right).** `songcharter/assemble.py:1633`. No test checks that the bar phase is
applied to the grid the octave pass returns, which is what this order is for (troop, pm2). Break: apply
`with_downbeats` to the first grid before `_octave_pass` and remove the call after it. The doubled grid then keeps
the kick's phase, so troop and pm2 go back to downbeat F1 0.000. Result: **31 passed** on the covering tests
(beatgrid, sections, assemble -k downbeat/octave/doubled/allin1/...). The `stretch_song` fixture (M6-05) already
holds allin1 downbeats on a doubled grid, but `test_a_doubled_grid_follows_a_tempo_change_from_allin1s_beats` never
asserts the phase. A cheap fix: assert `downbeat_source == "allin1"` there, and the phase of `beats[::4]` on the
doubled grid.

**R2 (minor, test gap).** `songcharter/beatgrid.py` `with_downbeats`, the branch where nothing votes. Break: return
`np.arange(0, len(beats), 4)` instead of `grid.downbeats`. Result: **31 passed**. The "away" case uses the `steady`
fixture, whose kick phase is 0, so it can't tell "keep the kick's phase" from "reset to 0". Shipped, the break would
put the bars on beat 0 whenever allin1's downbeats all miss the beats. Fix: test it on a grid whose kick phase is
not 0 (e.g. `beats[2:]`, as in tie.py).

**R3 (minor, test gap).** `songcharter/assemble.py:1657`, the "N beat(s) after the kick's beat 1" warning. Break:
`(kick - phase) % 4`. Result: **31 passed**. The only offset tested is 2, which reads the same both ways, so the
warning could say 3 when the shift is 1. Fix: an on-beat-2 or on-beat-4 case.

**R4 (minor, design).** `beatgrid.downbeat_vote`/`with_downbeats`. When the vote is split between phases p and p+2
(allin1 counting bars at twice the grid's rate: a downbeat every 2 beats), the tie goes to the lower phase, even when
the kick's phase is sure. Repro (tie.py, steady fixture, grid starting 2 beats later): the kick's phase 2 with
margin 0.977 becomes vote phase 0, counts [30, 0, 29, 0], margin 0.017. The result is flagged, but the warning says
only "allin1's downbeats fall on more than one beat of the bar"; it doesn't say the kick was sure. It doesn't
happen on any of the 11 songs (the lowest margin is sooth's 0.024, and its kick is unsure too). A cheap rule: under
`DOWNBEAT_MIN_MARGIN`, keep the kick's phase when it is sure and is one of the top two.

Breaks the tests caught: dropping `not kick.uncertain` from the disagreement warning (caught by the stretch test),
and `phase % 2` for the phase (caught by `test_the_bar_phase_follows_allin1s_downbeats`).

## Lens 1, correctness: no defect found
- The vote's local period ((b[j+1]-b[j-1])/2, one-sided at the ends) follows tempo changes, and the tie rule is
  deterministic (stable argsort). 4 beats a bar is assumed throughout, as in all of v1. A 3/4 or 6/8 song gives a
  split vote, which is flagged.
- Only `grid.downbeats` carries the phase, into `plan_lead_in` and then the TempoMap. Measures, star power, solos,
  sections' snapping, reduce's metric strength and the lyrics' phrases all read that map, so they all follow it.
  Nothing between `beat_grid` and the call reads the phase. `quantize.py:49` is a docstring.
- check_inputs: a non-list, NaN, Inf or nested value is an InputError. The librosa fallback writes only `segments`
  (`engines/sections.py:649`), and "from:" returns None: the kick's phase stays. `grid.downbeat_source` is in
  report.json.
- **M6-06.** `git merge-tree --write-tree be8b74c 4b58f06` exits 1 with one conflict, in assemble.py's module
  docstring. Against the current head ef1e020, DESIGN.md conflicts too. Both are docs only. `with_downbeats` sits
  after `_octave_pass`, which returns `_halving_pass`'s grid, so the halved grid gets the vote. That grid is built
  from allin1's beats, so allin1's downbeats sit on its beats. The merged tree (markers in the docstring still
  parse) passes the 36 covering tests, M6-06's pulse test included. That test does not assert the phase.
- **No minimum vote count:** not a real risk. allin1 writes one downbeat per bar. The 11 songs have 77-231 votes,
  and 92-100 % of the downbeats given vote. One or two votes would take a song of a few seconds. Downbeats that
  mostly miss the grid vote over half the timeline (the window covers ±0.25 beat) and spread across the phases,
  so the margin flags them. A minimum (say 8 votes, or half of those given) costs nothing measured, but it would be
  one more branch to test.

## Lens 2, the numbers
- **The drums flag is a false positive; the claim holds.** `engines/drumlanes.py:103` imports only
  `estimate_tempo` and `onset_features`. `adtof.py` doesn't import beatgrid. Of ENGINE_FILES, only beatgrid.py
  differs between 8ba3cbd and be8b74c, and only by this diff (new constant, new functions, `source` in
  `beat_grid`'s stats). `eval/golden.py:450` is a file-level `git diff --quiet`, so it can't see that. No
  `--rerun drums` pair is needed.
- **troop's Medium fall is the ladder, not the phase.** Our chart and the human chart are both 4/4 at 200 BPM, so
  after the change our measures are the humans' (downbeat F1 1.000). By place in the human bar, the human Medium
  guitar has 233/175/185/192 notes on beats 1/2/3/4. Ours keeps three beats of four, and the ladder thins the
  measure's last beat. Before (phase 2) that dropped human beat 2; now it drops beat 4. Guitar Medium: 177 dropped
  on beat 4 (161 on a human note), 157 added on beat 2 (140 on one): matched 552 -> 531. Bass is the same
  (171/150 dropped, 160/132 added). Drums Medium and Easy shift their weak slot the same way. The humans' Medium is
  on the new phase; their beat 4 is just a little denser than beat 2. The old phase scored higher by accident: a
  ladder calibration item, not M6-03's.
- **pm2's drums Medium and Easy are M6-05's, not the phase's.** Phase 0 vs 3 moves them less than 0.014. At M6-05
  the grid went from 1476 to 1431 beats, onto the humans' beats. Our Medium hands then keep on-beat hits (the 1-beat
  hi-hat rule at 140 BPM and up, metric strength first): 446 dropped, mostly off-beat 8ths (334 on a human note);
  435 added on beats (175 on one). The humans' Medium drums (a subset of their Expert: 100 % of its notes are on
  Expert notes, in the primary and in alt4) sit on beat 1 (330) and the off-beat 8ths (about 200 each), and rarely
  on beats 2-4 (66-101). The old grid was half a beat off over part of the song, so its on-beat picks fell on
  human off-beats. Easy is the same.

## Lens 3, the tests
Five breaks of my own: three survived (R1-R3) and two were caught. The baseline passes 31 of 31.
