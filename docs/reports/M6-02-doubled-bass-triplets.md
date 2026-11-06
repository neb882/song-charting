# M6-02 report: the bass's triplet slots on a doubled grid

Builder, 2026-11-06. Branch `m6-02-doubled-bass-triplets`, worktree `<wt>/m6-02`, from main at f3b9ebb.

## Summary

On a doubled grid the bass now snaps to the grid's 8ths only: `DOUBLED_BASS_SLOTS` (2, 0), with no triplet slots.
Every other part and every first-grid song is unchanged.

- **Stress set:** bass F1@50 against the primaries rises, troop 0.716 -> 0.735 and pm2 0.777 -> 0.787. pm2's alt2
  falls 0.595 -> 0.588. Every other number is identical.
- **Golden charts:** identical (`--expect none`, exit 0).
- **Suite:** 1058 passed, 3 skipped.
- **CI:** green on 9b6cd38. Attempt 1 failed on a race in another order's hook, unrelated to this change: see Findings.

The measurement came first. All three rules raised both primaries and lowered alt2, so I stopped and reported. The
orchestrator then decided (2, 0): "without lowering either below today's" is read against each song's primary, which
is the stress check's yardstick.

**Hold:** the orchestrator asked for no push and no merge of origin until the history rewrite lands. The branch on
origin is at 9b6cd38, which CI checked. c76a0aa, a docs-only commit, is local only.

## Commits

| commit | what |
|---|---|
| bc85f91 | `songcharter/assemble.py`: `DOUBLED_BASS_SLOTS = (2, 0)` with its comment, `part_rules`' docstring, and `DOUBLED_LYRIC_SLOTS`' comment (it said "the same" as the bass). `tests/test_assemble.py`: a new test, and the existing doubled-grid test's slots changed to `triplet: 0`. |
| 59b65c3 | DESIGN 2.6: the measurement table, the humans' triplet shares, why alt2 falls, and the orchestrator's reading. DESIGN 2.15: its line no longer says the lyrics snap "as the bass". M5-99's doubled-bass item: the triplet half done, the offset half unsupported, the 16ths left with the burst slots. |
| 9b6cd38 | Merge of origin/main (M6-04's work order, docs only). |
| c76a0aa | M5-99: pm2's remaining gap to its first grid (0.787 against 0.800). **Local, not pushed** (the hold). |

Each commit ends with the brief's trailer lines.

## The rule and why

With 8th slots, an onset counts as off-beat from a quarter to three quarters of the beat. It "leans triplet"
whenever it lies within 25 ms of a third of the beat: that covers 100 of the off-beat zone's 150 ms at 200 BPM. So
the bass engine's 8ths, 40 to 50 ms off, were read as triplet runs. The humans chart these basses in straight 8ths
and 16ths. Measured rules, all on the doubled grid's bass only, through `part_rules`:

- **today** (2, 3): the doubled grid's 8ths and their triplets.
- **(2, 0)**: its 8ths only.
- **stricter**: (2, 3), with the triplet run test measured against the doubled grid's 16ths. That is the test the
  bass had before M5-01 coarsened its slots. It was one variant, not a sweep; it needed a new `QuantizeRules` field,
  and it was not kept.

### The table

The runs:
- Stress set, 1 CPU take, `--rerun bass`.
- Today's: main f3b9ebb, on all four songs.
- The variants: uncommitted edits run on troop and pm2.
- The chosen rule's final run: bc85f91, on all four songs. Its bass numbers equal the (2, 0) variant's exactly.

The scoring:
- Bass Expert, matched at 50 ms with score.py's own `onsets` and `match`, on the alignment score.py wrote.
- Every F1 below equals score.py's to 4 digits.
- The human charts with a bass part are troop's primary, and pm2's primary and alt2.

| bass F1@50 | today (2, 3) | **(2, 0), chosen** | stricter |
|---|---|---|---|
| troop vs its primary | 0.7161 | **0.7346** (+0.019) | 0.7236 |
| pm2 vs its primary | 0.7766 | **0.7875** (+0.011) | 0.7812 |
| pm2 vs alt2 | 0.5949 | 0.5879 (-0.007) | 0.5916 |
| our onsets (troop / pm2) | 1505 / 2057 | 1453 / 2003 | 1484 / 2035 |
| matched (troop / pm2 primary / alt2) | 1202 / 1797 / 1550 | 1214 / 1801 / 1516 | 1207 / 1799 / 1535 |
| our notes on triplet slots (troop / pm2) | 124 / 174 | 0 / 0 | 67 / 97 |
| of those unmatched (troop / pm2 primary / alt2) | 80 / 75 / 49 | — | 44 / 38 / 24 |
| matched median error, signed (troop / pm2 primary / alt2), ms | 0.84 / 4.42 / 4.46 | 0.86 / 4.30 / 4.19 | 0.84 / 4.42 / 4.45 |
| matched median error, absolute (troop / pm2 primary / alt2), ms | 1.27 / 5.97 / 7.16 | 1.15 / 5.57 / 6.07 | 1.20 / 5.79 / 6.80 |

Today's triplet notes sit a median 50.8 ms (troop) and 48.4 ms (pm2) from the nearest primary note, and 31.9 ms from
the nearest alt2 note. They match a human triplet note 0, 4 and 2 times.

**The humans' bass.** Every chart's median tempo is 200 BPM, like the doubled grid. Notes by their place in the
chart's own beat:

| chart | beat lines | 8ths | 16ths | 32nds | triplets (1/3, 1/6, 1/12, 1/24) | off-grid |
|---|---|---|---|---|---|---|
| troop primary | 830 | 717 | 304 | 1 | 0 (0.0 %) | 0 |
| pm2 primary | 1132 | 1024 | 405 | 0 | 10 (0.4 %) | 0 |
| pm2 alt2 | 994 | 696 | 1021 | 13 | 104 (3.3 %) | 326 |

**What (2, 0) changes, by the human note matched.** "Gained" means human notes matched now and not before; "lost"
the reverse.

| chart | gained | lost |
|---|---|---|
| troop primary | 18 8ths, 1 beat line | 6 16ths, 1 8th |
| pm2 primary | 26 8ths, 5 beat lines, 2 16ths | 20 16ths, 5 beat lines, 2 8ths, 2 triplets |
| pm2 alt2 | 32 8ths, 13 beat lines, 8 off-grid, 2 16ths, 1 triplet | **72 16ths**, 9 off-grid, 6 beat lines, 2 triplets, 1 8th |

Why alt2 falls:
- A triplet slot lies 25 ms from a 16th at 200 BPM, so today's triplet notes matched 16ths by accident.
- alt2 has 2.5 times the primary's 16ths (1,021 against 405). It also has 326 off-grid notes, and agrees with the
  primary at 0.710.

The doubled bass grid has had no slot for 16ths since M5-01. M5-99's item is narrowed to that gap, alongside the
burst slots.

## The checks

All heavy jobs ran through the shared lock: the golden runs take it themselves, and the suite and the scoring went
through `tools/heavy.sh`. Commands ran from `<wt>/m6-02` with the brief's environment. `$G` is
`$SONGCHARTER_GOLDEN`.

- **Suite:** `tools/heavy.sh .venv/bin/python -m pytest -q -p no:cacheprovider --basetemp=<shm>/pt-m6-02` at
  bc85f91. Result: "1058 passed, 3 skipped in 719.33s (0:11:59)".
- **The new tests and their breaks** (`-k "no_triplet_slots or bass_snaps_to_8ths"`, both pass; each break fails
  them):
  - B1, `DOUBLED_BASS_SLOTS` back to (2, 3): both fail.
  - B2, the rule on octave 1 too: both fail.
  - B3, the rule on every part on a doubled grid: both fail.
  - B4, `_quantize` ignoring the octave: the integration test fails.
  - B5, report.json's `slots` ignoring the octave: the integration test fails.
  - B6, the doubled bass keeping 16ths with no triplets, (4, 0): both fail.
- **The new test** (`test_on_a_doubled_grid_the_bass_has_no_triplet_slots`) uses a made-up engine's 8ths on a
  200 BPM map: the beat lines within 5 ms, the off-beats 40 to 50 ms early or late.
  - It checks `part_rules` for every HOPO mode: (2, 0) for the doubled bass, the quantizer's own rules for octave 1
    and for the guitar and drums.
  - With the doubled bass's rules, all 64 notes land on their 8ths and none on a triplet slot.
  - With the octave-1 bass rules or the doubled guitar's rules, the same onsets put more than 20 notes on triplet
    slots (32 here, as with today's (2, 3)).
- **Golden charts, `--expect none`:**
  - Old: `python -m eval.golden run --code <shm>/m6-02-old --out $G/m6-02-old --threads 2 --rerun bass` (a
    detached tree of f3b9ebb). Last line: "summary: .../m6-02-old/summary.json (377 s)".
  - New: the same with `--code <shm>/m6-02-new` (a detached tree of bc85f91) `--out $G/m6-02-new`. Last line:
    "(376 s)".
  - `python -m eval.golden diff $G/m6-02-old $G/m6-02-new --expect none`: exit 0, "golden diff: no UNEXPECTED
    change". The report: "Every song's results (hashes, counts, scores) identical: yes". Bass ran on all 7 songs on
    both sides, and the kept folders were made by 8ba3cbd. Pooled F1@50 is unchanged on every part and level
    (guitar Expert 0.8527, bass Expert 0.8247, drums Expert 0.9617).
- **Stress set, all four songs:**
  - Run: `python -m eval.golden run --refs $EVAL_DATA/stress --work $G/stress-work --code <shm>/m6-02-new --out $G/m6-02-new-stress --threads 2 --rerun bass`.
    Last lines:
    - troop: bass 0.735, drums 0.879, guitar 0.784.
    - sooth: bass 0.692, guitar 0.658.
    - break: guitar 0.832.
    - pm2: bass 0.787, drums 0.973, guitar 0.803.
    - 332 s.
  - Scored with `tools/heavy.sh python eval/stress.py score`: exit 0.
  - `stress.py compare $G/m6-02-old-stress $G/m6-02-new-stress` (today's, before this order): exit 0,
    "Regressions (a primary F1@50 down by more than 0.01): 0".
    - Only these rows move: troop bass primary 0.716 -> 0.735, pm2 bass primary 0.777 -> 0.787, pm2 bass alt2
      0.595 -> 0.588.
    - The summaries agree: only the bass tracks of troop and pm2 changed, and sooth and break are identical.
    - report.json shows the bass slots as `{straight: 2, triplet: 0}` and 0 triplet notes on both songs.
  - `stress.py compare eval/baseline/stress $G/m6-02-new-stress` (the committed baseline, cfc7d5d, from before M5-11
    doubled pm2's grid): exit 1, "pm2 bass: F1@50 0.800 → 0.787". This is M5-11's known trade, narrowed from -0.023
    to -0.013, and is now in M5-99.
- **Privacy:** `EVAL_DATA=<dev>/eval python3 -I eval/privacy_check.py` before each push, and again at c76a0aa:
  "264 files, 14 md5s and 37 names checked, 0 found", exit 0. The same check on this report: 0 found.
- **Hard-rule scan** of `git diff f3b9ebb...HEAD` and the branch's commit messages, before the push: no lyrics,
  audio, model names (apart from the attribution trailers) or personal details. Paths in the report use
  placeholders.
- **CI:** <repo>/actions/runs/42273701887, on head 9b6cd38.
  - Attempt 1: linux failed in Hooks at `70-release.sh` (below); its suite passed. windows passed.
  - Attempt 2 (`gh run rerun --failed`): **success**. Linux Suite: "1057 passed, 4 skipped in 347.28s". Hooks: "all
    8 Linux hooks passed: 10-lanes.sh 10s 20-device.sh 4s 30-install.sh 113s 40-ui.sh 26s 50-e2e.sh 326s
    60-results.sh 61s 70-release.sh 54s 75-update.sh 116s". windows passed (72 passed, 14 skipped).
  - An earlier run on 59b65c3 (42273626303) was cancelled when I merged main. c76a0aa (docs only, local) has not
    been through CI. It will need a run on whatever head the rewrite gives.

## Findings for the orchestrator

- **A race in `packaging/ci/linux.d/70-release.sh`, step 5, "songcharter (the page)".** Not this order's file.
  - The hook runs `curl -fsS "$address" | grep -q "<title>songcharter</title>"` under `set -euo pipefail`.
  - `grep -q` exits at the title, near the top of the page. If curl still has bytes to write, it fails with
    "Failed writing body" (exit 23), and pipefail makes that the step's failure.
  - This was attempt 1's failure. The page is the same as on main, where the step passed.
  - Fix: `curl -fsS "$address" -o a temporary file && grep -q ... a temporary file`, or drop `-q`.
  - I left it for a later order.
- `pgrep -af` prints a process's whole command line, and songcharter's chart command carries the song's title and
  artist. One early check of mine printed a stress song's title and artist into my own tool output. It was never
  written to a file, report or commit. Afterwards I used the lock's .who file and cut-down listings, as the
  orchestrator noted.

## Left, uncertain, cleanup

- **Left:** move the branch onto the rewritten history with the orchestrator's commands, push, and run CI on the new
  head. Also: the review, and copying this report into `docs/reports/`. PROGRESS is the orchestrator's.
- **Uncertain:**
  - Every stress number is from 1 take. I did not measure the bass F1's run-to-run spread; the engine is seeded,
    and the runs reproduced the gate's 0.716 and 0.777.
  - Only two doubled songs exist. A doubled song whose bass really plays 8th-note triplets of its own tempo would
    now get them on 8ths. None is in either set.
- **Cleanup:**
  - Removed: `<shm>/m6-02-old` and `<shm>/m6-02-new` (`git worktree remove`), and `<shm>/pt-m6-02`.
  - Kept for the review (about 200 MB): `$G/m6-02-{old,new}`, `$G/m6-02-{old,v20,vS,new}-stress`.
  - Scratch scripts (numbers only): `<scratchpad>/m6-02/tools/`.
  - `df -h /`: 13 GB free.

## Review fixes (orchestrator, commit 53195e3)

- **R1** (docs): DESIGN 2.6 says the 174 triplet notes were the whole rise in pm2's unmatched bass notes (+67) and
  about half its F1@50 loss (0.011 of 0.023), not all of it.
- **R2** (a test gap since M5-01): the doubled-bass rules on levels imported with `take_difficulties: "all"` have no
  test; in M5-99 (the pipeline imports Expert only).
- The repository's history was rewritten on 2026-11-06 (the owner's decision: a committed report's md5 prefixes and a
  stress song's artist removed from old commits); hashes above from before 19:40 UTC are the old ones (9b6cd38 is
  now 69164fb; c76a0aa was replayed as a927b5d). CI on 53195e3: green (run 42283128225, its second attempt; the first failed on the release hook's curl | grep -q flake, fixed on main in 2d2a94c).

## Review (sc-reviewer, 2026-11-06)


No major findings. The code change is correct and its tests guard it; two minor findings.

## Checked, no defect
- Correctness: `part_rules` gives (2, 0) only for `octave == 2 and instrument == "bass"`; report.json's `slots` reads the
  same function; `DOUBLED_LYRIC_SLOTS` still (2, 3) and `lyric_rules` untouched; `SnapGrid.from_ticks` returns early on
  `triplet == 0` (no division by zero); no other consumer of the constant. DESIGN 2.6, 2.15 and M5-99 match the code.
- Numbers: `stress.py compare` of the kept folders reproduces every F1 in the table (old->new: troop bass 0.716->0.735,
  pm2 0.777->0.787, alt2 0.595->0.588, every other row +0.000, exit 0; old->v20 equals old->new on the bass;
  old->vS 0.724 / 0.781 / 0.592). report.json slots: old/vS {2,3}, v20/new {2,0}. Triplet onsets in our charts' Expert
  bass, by tick (my own count): old troop 124, pm2 174; new 0 / 0. The F1s are consistent with the matched and onset
  counts (refs 1852 / 2571 / 3154), and the gained/lost tables sum to the matched deltas.
- Test the tests (my breaks, run on copies through heavy.sh, `-k "doubled or octave or triplet or slots or lyric_rules"`):
  quantize's `triplet == 0` guard removed -> 3 tests fail (good); `is_triplet_slot` blind at straight 2 -> green, but
  ships nothing under (2, 0); `part_rules` keyed on `from_instrument` -> green, ambiguous semantics, not a defect.

## Findings
- **R1, minor, docs/DESIGN.md:827.** The new paragraph says the 174 triplet notes were "the whole of pm2's loss against
  its primary when M5-11 doubled its grid". The result contradicts it: removing them recovers 0.011 of the 0.023, and
  M5-99 (added in the same diff) says pm2 is still 0.013 under its first grid. M5-11 measured them as the whole rise in
  unmatched notes (+67), not the whole F1 loss. Repro: `stress.py compare eval/baseline/stress <G>/m6-02-new-stress`
  (in the worktree) -> "pm2 | bass | primary | 0.800 -> 0.787 (-0.013)", exit 1.
- **R2, minor (pre-existing, M5-01), songcharter/assemble.py:1395.** Nothing tests the doubled-bass rules on levels
  imported with `take_difficulties: "all"`. Break: `rules if d == 'expert' else part_rules(part)` (lower levels get the
  octave-1 rules, triplets included) -> "21 passed, 121 deselected", green. Ships only for an assemble config with
  "all" on a doubled grid (the pipeline uses "expert"), so a later order's, if anyone's.
