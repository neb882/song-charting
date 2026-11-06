# M5-10: on a doubled grid, the lyrics snap one slot level coarser (builder's report)

Branch `m5-10-doubled-lyrics` (worktree `<wt>/m5-10`), from main at 3444428 (after M5-03's merge), main brought in
by a merge at the end. The lyrics rule held throughout. No word of any lyric was printed, logged, saved, committed or
returned. The human charts' words were read in memory from the packages (`eval/stress.py lyrics`, and
`eval/lyrics_timing.py` in my check script). The owner's pasted text was read only inside the process that passed it
to `pipeline.chart(..., Options(lyrics=text))`, and was paired with the human chart's words by their text, in memory.
Songs are named by their ids below.

## Commits

- `1e5a918` On a doubled grid the lyrics snap one slot level coarser (M5-10): `songcharter/assemble.py`,
  `tests/test_assemble.py`, `tests/test_lyrics.py`
- `1505fa7` DESIGN 2.15: the lyrics on a doubled grid snap to its 8ths, with M5-04's numbers and this order's
- `957c84e` Lyrics test: a docstring reworded (a common English word the lyrics scan matched)
- `704f401` Merge origin/main into m5-10-doubled-lyrics (M5-11's work order, docs only)

## What changed

- **`assemble.py`:**
  - A new constant, `DOUBLED_LYRIC_SLOTS = (2, 3)`. It has the bass's values, and a comment says why the lyrics
    need it.
  - A new function, `lyric_rules(octave)`. On octave 2 it returns `replace(RULES, straight=2, triplet=3)`: the doubled
    grid's 8ths and their triplets, which are the first grid's 16ths and its triplets. On octave 1 it returns `RULES`
    itself, so nothing changes there. It takes no part and has no instrument check.
  - `assemble()` passes `rules=lyric_rules(octave)` to `L.place`.
  - `report["lyrics"]` gains `slots: {straight, triplet}`. That record also reaches pipeline.json's
    `lyrics.chart`, and it holds numbers only.
  - The module docstring says the same.
- **`lyrics.py`:** unchanged. `place` already took `rules`.
- **Tests (made-up words only):**
  - `test_lyrics.py::test_on_a_doubled_grid_a_word_snaps_one_slot_level_coarser`, on a 200 BPM map. Four words are
    sung 50 ms before beats. With `lyric_rules(2)` they land on the beat ticks (snap 50 ms, none moved). With
    `lyric_rules(1)` they land a 1/16 (48 ticks) early. Also checked: `lyric_rules(1) == RULES`, and the doubled
    rules differ from `RULES` only in `straight`.
  - `test_assemble.py::test_on_a_doubled_grid_the_lyrics_snap_to_8ths`, on the 198 BPM fixture song (M5-01's
    `fast_song`), which the octave pass doubles. Six made-up words are sung 50 ms before beats. Every lyric tick is
    on a beat line, within 12 ms of the beat's seconds, and `report["lyrics"]["slots"] == {2, 3}`. With
    `grid_octave: 1` forced, the octave is 1 and the slots are `{4, 3}`.
- **`docs/DESIGN.md` 2.15:**
  - The "On the chart" paragraph mentions the doubled grid's 8ths.
  - M5-04's paragraph now points to the new one.
  - A new paragraph, "On a doubled grid, the lyrics' 8ths", has the table below and the mechanism.
- PROGRESS.json was not edited, as the brief asked.

## The lyrics checks (numbers only)

Each check was run before (a detached worktree of main at 3444428, `<shm>/m510-main`) and after (this branch).
The troop checks start from the stress baseline's kept folder (`--run $DEV/golden/stress-base-main`). The two
references start from this order's golden runs' kept folder. All ran on CPU with 2 threads, through
`tools/heavy.sh`, in one resumable chain (`<scratchpad>/m510/chain.sh`).

**troop (the power-metal song), `eval/stress.py lyrics troop --run $DEV/golden/stress-base-main`:**

| run | paired | median error (signed) | within 50 / 100 / 250 ms | phrase starts > 500 ms | gate | warned | median confidence |
|---|---|---|---|---|---|---|---|
| main | 320 of 320 | 67.3 ms (+0.5) | 0.463 / 0.856 / 0.953 | 8 of 51 | OK | no | 0.18 |
| this branch | 320 of 320 | **3.4 ms** (+1.6) | **0.688** / 0.750 / **0.950** | 8 of 51 | OK | no | 0.18 |

The order's bar is met: a median under 15 ms (3.4), at least 0.65 within 50 ms (0.688), at least 0.95 within 250 ms
(0.950, i.e. 304 of 320 words), and no unsure warning. M5-09's old-grid figures were 7 ms and 0.681 / 0.756 / 0.953.

**The same song through my check script** (`<scratchpad>/m510/owner_check.py CODE troop SOURCE RUN`). It shows the
signed error percentiles, the octave, the slots and the SyncTrack's hash. Paired by index for the human text, and by
text for the owner's:

| text, code | paired | median | within 50 / 100 / 250 ms | signed p10 / 25 / 50 / 75 / 90 ms | phrase starts > 500 ms | warned (weak share) | octave | SyncTrack |
|---|---|---|---|---|---|---|---|---|
| the human chart's, main | 320 | 67.3 ms | 0.463 / 0.856 / 0.953 | -75.1 / -72.2 / +0.5 / +7.9 / +98.6 | 8 of 51 | no | 2 | fdec6620dab6 |
| the human chart's, this branch | 320 | 3.4 ms | 0.688 / 0.750 / 0.950 | -96.1 / -0.6 / +1.6 / +5.9 / +151.6 | 8 of 51 | no (0.084) | 2 | fdec6620dab6 |
| the owner's pasted text, main | 302 (0.944 of the human's, 0.984 of ours) | 65.4 ms | 0.467 / 0.858 / 0.967 | -75.1 / -72.2 / +0.5 / +9.9 / +103.8 | 2 of 43 | no (0.088) | 2 | fdec6620dab6 |
| the owner's pasted text, this branch | 302 (0.944 / 0.984) | **3.2 ms** | **0.689** / 0.752 / 0.964 | -88.9 / -0.6 / +1.5 / +5.7 / +150.9 | 2 of 43 | no (0.088) | 2 | fdec6620dab6 |

- On this branch the lyrics' `slots` were `{straight: 2, triplet: 3}` in both runs. Each run moved 1 syllable to
  the next slot, and the snap's maximum was 132.8 ms (the moved one).
  - The human text: 320 syllables, 51 phrases, 17 triplet beats, a median snap of 37.6 ms.
  - The owner's text: 307 syllables, 53 phrases (1 split at a rest), 16 triplet beats, a median snap of 36.8 ms.
- The SyncTrack is the same in all four runs, so only the lyrics moved.
- The middle half of the words now sits within 6 ms of the human's. The tails widened: a word the aligner misplaced
  by a slot now lands an 8th (150 ms) off instead of a 16th (75 ms). That is why the 100 ms share falls by 0.106 and
  the 250 ms share by one word.
- The weak-word share does not depend on the grid, and the warning stays off.

**The references (octave 1), `eval/stress.py lyrics ID --refs $EVAL_DATA/refs --run $DEV/golden/m5-10-{old,new}`:**

| song | main | this branch |
|---|---|---|
| take_me_out | 231 of 231; 37.6 ms; 0.567 / 0.684 / 0.870; 2 of 42; OK; no warning | identical |
| kimochi_warui | 273 of 273; 110.3 ms; 0.289 / 0.289 / 0.850; 0 of 41; OK; no warning | identical |

All seven golden songs chart on octave 1 (each `report.json`'s `grid.octave`), so `lyric_rules(1)` is `RULES` for
every reference.

## Checks

- **The suite:** `tools/heavy.sh` ran
  `.venv/bin/python -m pytest -q -p no:cacheprovider --basetemp=<shm>/pt-m5-10`, with SONGCHARTER_SCAN_CHART set,
  on 1e5a918. Last line: `1014 passed, 3 skipped in 707.54s (0:11:47)`.
  - After the docstring commit, the three affected tests were rerun: `3 passed in 5.75s`.
- **The new tests, broken seven ways** (`<scratchpad>/m510/breaks.py`: one edit at a time, the two new tests run,
  then the file restored; `git diff` afterwards showed only the intended change). Every break failed at least one
  test:
  - A, octave ignored in assemble (`lyric_rules(1)`): 1 failed (the assemble test).
  - B, the bass rule's instrument check copied (`if octave == 2 and "vocals" == "bass"`, so the lyrics never get
    it): 2 failed.
  - C, coarse on octave 1 too: 2 failed.
  - D, the report records the default slots: 1 failed (assemble).
  - E, `place` ignores the rules it is given: 2 failed.
  - F, `DOUBLED_LYRIC_SLOTS = (4, 3)`: 2 failed.
  - G, the rules not passed to `place` (the report's slots still right): 1 failed (assemble). This shows the tick
    assertion works apart from the slots record.
- **Golden** (`--expect none`, warm, no `--rerun`; EVAL_DATA, SONGCHARTER_GOLDEN, SONGCHARTER_SCAN_CHART,
  SONGCHARTER_AUTOCHART and SONGCHARTER_ALLIN1_PYTHON set as the brief says):
  - `python -m eval.golden run --code <shm>/m510-main --out $DEV/golden/m5-10-old --threads 2`: exit 0,
    `summary: .../m5-10-old/summary.json (316 s)`.
  - `python -m eval.golden run --out $DEV/golden/m5-10-new --threads 2`: exit 0, `summary: .../m5-10-new/summary.json
    (264 s)`.
  - `python -m eval.golden diff $DEV/golden/m5-10-old $DEV/golden/m5-10-new --expect none`: exit 0, `golden diff: no
    UNEXPECTED change`. Every pooled F1@50 row was +0.0000 (guitar Expert 0.8527, bass Expert 0.8247, drums Expert
    0.9617, ...).
- **CI:** run 42166638206 (`<repo>/actions/runs/42166638206`) on the branch's head 704f401 (the merge of main): **success**. linux 24 m 48 s: the suite `1013 passed, 4 skipped in 462.66s`, the same 1017 tests as locally, one more skipped on the runner; `all 8 Linux hooks passed` (10-lanes, 20-device, 30-install, 40-ui, 50-e2e, 60-results, 70-release, 75-update). windows 47 s, success. An earlier run on 957c84e (42166590628) was cancelled when main was merged in.
- No CI hook was added: the order's checks are unit tests in the suite.

## The scans

- **Lyrics.** `<scratchpad>/m510/scan.py` is M5-04's scan pointed at this worktree. It reads in memory the lyric
  events of the six references' packages and troop's: 252 lines, 53 distinctive words, 722 three-word runs, with the
  ids and title words left out. It prints counts and line numbers only.
  - It ran over `git diff origin/main...HEAD`, the commit messages, the whole scratch folder `<scratchpad>/m510`
    (scripts and logs) and the progress log.
  - The first run found 1 hit: a common English word in a test docstring. I reworded it (`957c84e`). The rescan
    found 0 hits.
  - The scan didn't read the owner's text: the brief allows reading it only in the charting process.
  - This report was scanned too before handing over: 0 hits.
- **Model names and personal details.** A grep over the diff and the commit messages, trailer lines left out, found
  no match. It looked for assistant-model names, `/home/`, `/tmp/`, `/dev/shm`, email-like strings, 32-hex hashes and
  the owner's file name.
- **Built charts deleted.** Every chart with lyrics was built in a temporary folder under the kept folders' `.runs/`,
  with its work folder and any `<out>.failed` beside it, and deleted whole.
  - My script's four runs each printed `temporary folder deleted: True`. `stress.py lyrics` deletes its own six.
  - `$DEV/golden/work/.runs` and `$DEV/golden/stress-work/.runs` are empty.
  - The golden runs were built without lyrics.
  - The scratch logs hold numbers, ids and the pipeline's numeric confidence only. No pipeline log line was printed
    or saved.

## Not done, uncertain, for the orchestrator

- **The 100 ms share on troop** fell from 0.856 to 0.750. It is M5-09's old-grid figure (0.756), but it is a real
  trade: the misplaced words now miss by an 8th, not a 16th. The order's bar doesn't include it. Correcting the
  aligner's lead (median -20 ms on this song's stem) would let the 16ths come back, but it needs more fast songs with
  human lyrics to measure against (M5-99).
- **One fast song.** The remedy is measured on one doubled song, troop. A fast song whose singer really sings 16ths
  would lose them to the next 8th. Each one is counted in `moved_to_next_slot`, which troop's text moved only once.
- **Left in place for the reviewer:**
  - `<shm>/m510-main` (detached at 3444428): remove it at the merge (`git worktree remove`).
  - `$DEV/golden/m5-10-old` and `m5-10-new`: no lyrics in them.
- `df -h /`: 15 GB free.

## Review fixes (orchestrator, commit 16d3ab5; tests, comments and docs only, so no golden rerun)

- **F1** (a rejected doubling untested): `test_on_a_doubled_grid_the_lyrics_snap_to_8ths` now runs the fast song with
  a guard the doubled grid cannot meet (`evidence_min` 2.0): the first grid stays, the second pass is recorded, and
  the lyrics keep the first grid's slots {4, 3}. It fails on the reviewer's break R2 (the slots chosen by whether a
  second pass ran).
- **F2** (no word on a doubled grid's triplet slot): the same test sings six made-up words in triplets on the
  doubled grid (beats 20 and 21 in thirds); they land on the triplet slots, four of them off the 8ths. A new
  `test_lyrics.py` test does the same through `place` with `lyric_rules(2)`. They fail on R6 (`place` given
  triplet 0 while the report says 3) and on triplet 0 in `lyric_rules`.
- **F3** (wording): the doubled grid's triplets are the first grid's 16th-note triplets, a finer superset of its
  8th-note triplets, not the same slots: `DOUBLED_BASS_SLOTS`'s comment, `lyric_rules`'s docstring, DESIGN 2.6 and
  2.15 reworded.
- `tests/test_assemble.py` and `tests/test_lyrics.py`: 88 passed. CI on 16d3ab5: below.
- The reviewer's two M5-99 items (the 250 ms bar met with no margin on troop, the aligner's early lead; a second
  fast song with human lyrics) are in M5-99.

## Review (sc-reviewer, 2026-11-06)


## Lens 1, the lyrics rule: clean
- I read the builder's scripts (owner_check.py, chain.sh, setup.sh, breaks.py, scan.py). The pipeline log is collected
  in memory and dropped, errors print as their type only, and only numeric records are printed. The pasted text is read
  only inside the charting process.
- I re-ran the builder's scan (counts only) over the diff and commit messages, the report, the progress log and
  scratch m510/: 40 inputs, 0 hits.
- Second check of my own, which also covers the owner's text, which that scan cannot read: every alphabetic token
  in the 15 logs that is not in the code's own vocabulary. The only leftovers are hex runs of the SyncTrack hash and
  identifiers from the builder's scripts. Nothing else.
- stress-work/.runs and work/.runs are empty, and no /tmp entry is from the run. The tests use made-up words.

## Lens 2, correctness
- `lyric_rules(1)` is `RULES` itself, and `(2)` changes only straight to 2.
- `place` uses the rules for every snap and for next_slot.
- assemble passes the final `octave` from _octave_pass, which is never reassigned. The report's slots come from the same
  `rules` object.
- pipeline.json gets them through lyrics.chart.
- The DESIGN figures match the report. 0.856-0.750=0.106, and 1/320=0.003.
- My breaks (copy at <shm>/review_m510, now deleted):
  - Caught: triplet 6; triplet 0 (but only by the attribute assert); octave from octave_stats["octave"]; collisions not
    moved (an old test).
  - Green: R2 and R6, below.

### F1 (minor): assemble.py:1658 / test_assemble.py:1420. The kept-versus-wanted octave is untested
Break R2: `rules = lyric_rules(2 if octave_stats.get('second') else 1)`. A rejected doubling then gets the doubled
grid's slots on a first grid, which puts the lyrics on 8ths at about 100 BPM. Both new tests stay green, because they
cover only the auto-doubled and the forced-1 cases.

My test (fast_song with OCTAVE_RULES.evidence_min=2.0 plus 3 made-up words; it asserts octave 1, "second" tried, slots
{4,3}):
- Passes on the branch: `1 passed in 3.21s`.
- Under R2: `FAILED tests/test_review_m510.py::test_rejected_doubling_keeps_first_grid_lyric_slots`, and `1 failed, 2
  passed` with the builder's two tests.

Fix: add this case to test_on_a_doubled_grid_the_lyrics_snap_to_8ths. The 1380 test's monkeypatch shows how.

### F2 (minor): the doubled grid's lyric triplets are never exercised
Break R6: `place` gets `replace(RULES, straight=2, triplet=0)` on octave 2, while the report still says triplet 3.
Result: `2 passed`.

R4 (triplet=0 in lyric_rules) is caught only by `doubled.triplet == 3`. No test places a syllable on a triplet slot of
the doubled grid.

### F3 (minor, docs): DESIGN.md 2.15 (new paragraph) and assemble.py:678-680, 1347-1351
The docs say the doubled grid's "8ths and their triplets, which are the first grid's 16ths and its triplets: so the words
keep the slots the first grid gave them". That holds for the straight slots only.
- triplet=3 per doubled beat is 6 per first-grid beat, which is the first grid's 16th triplets. At 200 BPM that is
  100 ms, against the 200 ms 8th triplets that `RULES` gave the first grid.
- The doubled triplet slots are a finer superset of the first grid's, not the same slots. The same wording is on
  DOUBLED_BASS_SLOTS.

Fix: reword it as "the first grid's 16ths, and 16th-note triplets".

## Lens 3, the uncertain items: neither blocks the merge; both go to M5-99
- 100 ms share 0.856 -> 0.750. Every bar in the order is met, and this is M5-09's old-grid figure back (0.756). It is
  the price of the mechanism: a misplaced word now misses by an 8th. Note for M5-99: the 250 ms bar is met with no
  margin (304/320 = 0.950), so one more word lost fails it. The aligner-lead correction belongs there too.
- One doubled song. The 8ths on a doubled grid are the 16ths the lyrics had before M5-01, so this is no loss against
  pre-M5-01 charts, and `moved_to_next_slot` counts each collision. M5-99: a second fast song with human lyrics when one
  exists.
