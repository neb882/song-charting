# M6-10: v0.3.0's gate fixes (the builder's report)

Branch `m6-10-gate-fixes` (worktree `<wt>/m6-10`), from origin/main 8e8cc51. The order: the 12 minor findings of
v0.3.0's release-gate review (`toFixer` in the review's result), each reproduced before its fix.

## Commits

- `c47b84b` Tests for five gaps v0.3.0's gate review found (tests-1 .. tests-5)
- `f8196d3` allin1's model "auto" is fold 0 on every device (install-1)
- `d0ca5b8` Docs corrected from the code and the measured numbers (docs-1 .. docs-6)
- `95e2cf1` DESIGN Q29: the ensemble was the default until M6-10; neither model has run on a GPU

## Per finding

Each test finding: the mutant was applied to the worktree, the existing tests that cover the code were run on it
(they pass: the gap reproduced), then the new test (it fails). Every mutant was reverted with `git checkout`.

| finding | reproduced | the fix | the break, and what fails |
|---|---|---|---|
| tests-1 | yes: with `with_downbeats` skipped for octave 0.5 (assemble.py:1752), the halved-words test passes | `test_a_song_at_twice_its_pulse_is_charted_at_the_pulse` now asserts source allin1, phase 0, not flagged, the kick's own phase flagged, and every allin1 downbeat on a measure start of the chart | the reviewer's mutant: `('kick', 1, True) == ('allin1', 0, False)` fails; with those asserts removed, the bar-tick check alone also fails (one beat off) |
| tests-2 | yes: both mutants pass the existing downbeat tests (`-k 'split_vote or downbeats or downbeat'`: 8 / 7 passed besides the new cases) | `test_a_split_vote_keeps_only_a_sure_kick_and_only_under_the_threshold`, 4 cases on a made-up 200 BPM grid: an unsure kick against a split vote (0.12), a sure kick against a clear vote (0.36), the margin at 0.15 and at 0.14 | (a) `not db["uncertain"]` dropped: case 1 fails; (b) threshold 0.5: cases 2 and 3 fail; (c) `<=` for `<`: case 3 fails |
| tests-3 | yes: `carry = delta` passes the existing strip_mid tests | `test_strip_mid_carries_the_ticks_of_lyrics_in_a_row_to_the_next_kept_event`: three lyrics in a row (80 + 120 + 0 ticks, then 220) give byte for byte the same track as no lyric (420) | `carry = delta`: fails |
| tests-4 | yes: all three print mutants at once pass the build_refs test | `test_make_songs_json_prints_ids_and_numbers_only`: the script on a made-up built folder (a built song with a built alt and an unbuilt alt, an unbuilt song), its stdout exactly, no 4-character md5 prefix, no title, artist or charter | J1 (the alt's md5 prefix), J2 (the skipping line's md5 prefix), J3 (a charter column): each fails |
| tests-5 | yes: `np.mean` passes the existing halving test | in `test_halving_test_reads_the_rate_against_allin1s_with_its_guards`: 77 BPM beats over 1-120 s and 200-319 s give halve True, 77.0 BPM, ratio 2.0 | `np.mean`: fails |
| install-1 | yes (the light part): 11 of 11 cached sections results under the golden kept folders are `harmonix-fold0` on the CPU; `sections.py:389` chose the ensemble on CUDA. The reviewer's heavy comparison (the ensemble on four stress clips) was not rerun | below | below |
| docs-1 | yes (the four places) | below | - |
| docs-2 | yes | below | - |
| docs-3 | yes: recounted from the table with a script (numbers only) | below | - |
| docs-4 | yes for handoff.md (PROGRESS is the orchestrator's) | below | - |
| docs-5 | yes | below | - |
| docs-6 | yes: 697 - 689 = 8; 60/154/24 = 16.2 ms, 60/77/24 = 32.5 ms | below | - |

### install-1

- `engines/sections.py`: `AUTO_MODEL = "harmonix-fold0"`, and `_allin1_job` takes it for model "auto" on every
  device; a model asked for wins (on CUDA, on the CPU, and on the CPU's rerun after a failed CUDA run, which keeps
  the model). The cache key holds the model run and its weights as before, so the CPU's keys and results are
  unchanged, and a GPU's cached ensemble result is no hit for "auto" (it reruns with fold 0). The module docstring,
  `Settings.model`'s comment and the fallback's description follow.
- **Downloads:** the install (`runtime.step_pipeline_models`) fetches `runtime.SECTIONS = "harmonix-all"`: the 8
  folds on every lane. Decided to keep it: the 8 are 11.2 MB (DESIGN 4.2: 1.4 MB a fold), the 7 now unused by
  default 9.8 MB, about 0.1 % of a GPU lane's downloads (install.sh budgets 15 GB with 5 GB of work folders). The
  installed app reads the hub offline (`launch.environment` sets `HF_HUB_OFFLINE=1`), so a model asked for, the
  ensemble among them, is there only if the install fetched it; and changing the install's downloads late in a gate
  touches a path verified on the friend's PC. `runtime.py` says so beside the constant. No change to install.sh
  (it names no fold) or the doctor (it checks none).
- **Tests** (`tests/test_engines_sections.py`): `test_fold_0_runs_on_cuda_and_on_the_cpu_and_a_model_asked_for_runs_on_either`
  (replaces the ensemble-on-CUDA test): fold 0 on cuda and the cpu, `harmonix-all` asked for on both, four
  distinct keys, an ensemble result in the folder is no hit for "auto" on CUDA, and with `AUTO_MODEL` patched to
  another fold the fold-0 result is no hit either. The failed-CUDA test now expects `[("cuda", 1), ("cpu", 1)]` and
  an asked-for ensemble rerun with 8 checkpoints on the CPU. Breaks, each failing:
  - B1, the old choice (ensemble on CUDA): 2 tests fail.
  - B2, an asked-for model ignored (`model = AUTO_MODEL`): 3 fail.
  - B3, the key without the model and weights: 2 fail.
  - B4, the key holding the setting ("auto") instead of the model run: the new test fails (it survived the first
    version of the test; the `AUTO_MODEL` patch was added for it).
- **DESIGN:** the stage overview (fold 0 on any device; its beats and downbeats feed the grid's octave and bar
  phase), the code table's sections row, the stage table's row 5 (the owner's fold-0 call removed from "would
  change it"), the cost table's GPU figure, 2.5's Goal 2 and decision (a new paragraph: why fold 0 on CUDA, with
  the gate review's numbers, marked as its measurement), 2.5's "would change it", the solos decision's cost (fold 0
  is the friend's now), 8.2, and **Q29** (fold 0 in the code since M6-10; "the owner approves it with the
  release"). The pipeline's solos docstring follows. "Changes from v1" (11) is left as history.

### docs

- **docs-1:** DESIGN 2.10's "Not fixed" paragraph (now: M6-06 halves the shred song, and the beat-counted rule
  places 1.89 a minute, under the humans' 2.33-3.23: the open problem is a beat-counted rule at a slow tempo), the
  max_seconds rationale ("before M6-06 halved it"), "Would change it" (slow songs in place of "a halving rule"), and
  8.1's row (halving built, the 85-92.5 BPM pulse and the beat-counted rules open; "halving" dropped from the plan
  column). The old text said 2.34; the M6-06 table says 2.33, used.
- **docs-2:** M5-99's halved-grid downbeats item now says it is measured (0.000 -> 0.989, 172 votes, margin 1.000)
  and where the vote runs (`assemble.assemble`, on the grid `_octave_pass` returns; `beat_grid` never calls it); the
  M6-03 list's shred-song line now says its bars match on the halved grid. M6-06's report, line 87, corrected the
  same way, marked "M6-10's correction".
- **docs-3:** `docs/reports/set20-v03.md`'s summary: beat F1 0.94 or more on 4 songs (s03, s04, s05, s07), near it
  s12 (0.939) and s06 (0.844), weak on 7 (both odd-meter songs, three of the four with tempo changes, two of the
  three fast ones, from the table's slot column); downbeats under 0.3 on three (s08, s11, s13), s01 at 0.314; the
  guitar gap 0.07-0.20 (5 songs), bass 0.16-0.34 (4), drums 0.03-0.13 (3), with "their beat F1 0.95 or more" as
  the agreement rule (the reviewer's). The songs stay s01-s13.
- **docs-4:** `docs/handoff.md`: updated 2026-11-07; v0.2.0 published 2026-11-06 (eb0f340) and v0.2.1 2026-11-07
  (23389ac); v0.3.0 at its gate on 85e18b0 with this order's fixes; M6-09 for v0.3.1; the owner's two earlier
  questions settled (the history rewritten; the stale remote branch `m5-01-fast-grid` is gone: `git ls-remote`);
  the bass cache key note at 0.3.0 (engines/bass.py). PROGRESS.json untouched (the orchestrator's).
- **docs-5:** DESIGN 2.4 Goal 1 (the kick's margin 0.616 and allin1's vote 231/0/0/0, margin 1.000, the margin
  report.json and the summary give since M6-03), the stage table's row 4, and the decided-once table's downbeats
  row (code today: allin1's vote, else the kick; action: the Viterbi with Goal 2). 2.3 step 4's "margin 0.58" is
  left: it is the earlier beatgrid run's measurement, cited as such.
- **docs-6:** "0-8 onsets" in DESIGN and M6-03's report (marked as a correction there); "1/24 of the halved beat,
  1/12 of the first grid's (about 32 ms at 154)" in DESIGN 2.6, M5-99 and M6-06's report.

## Checks

- **The full suite** (through `tools/heavy.sh`, `SONGCHARTER_HEAVY_MIN_FREE_GB=1`, the shared venv's `python -m pytest -q
  -p no:cacheprovider --basetemp=<shm>/pt-m6-10`, scan-chart from the base-main checkout), on the code of d0ca5b8
  (95e2cf1 changes DESIGN.md alone; no test reads it): `1126 passed, 6 skipped in 742.44s (0:12:22)`, exit 0.
- **Single files while building:** `tests/test_engines_sections.py` 28 passed, 1 skipped; each new test passed on
  the candidate and failed on its break (the table and install-1 above).

- **CI** on the head 95e2cf1: <repo>/actions/runs/42382508842, **success** (linux
  and windows). linux: "Test the CI tools" 86 passed; the Suite `1128 passed, 4 skipped in 618.58s`; the hooks
  10-lanes, 20-device, 30-install, 40-ui and 50-e2e ok. windows: 72 passed, 14 skipped; its hook 30-shortcut ok.
  This order adds no hook: its checks are suite tests, which the Suite step runs. An earlier run on d0ca5b8
  (42382367996) was cancelled by the workflow when the head's run started.

- **Privacy:** `EVAL_DATA=<dev>/eval python3 -I eval/privacy_check.py` before the push: "276 files, 14 md5s and 37
  names checked, 0 found", exit 0.
- **The diff and commit messages scanned** (`git diff origin/main...HEAD`, `git log --format=%B`): no assistant model
  names (only `CLAUDE.md` and the attribution trailers), no home or profile paths, no emails or usernames, no
  lyrics (the tests' words are the file's made-up `WORDS`), no audio.
- **Golden charts:** not run (the brief: the orchestrator reruns the golden pair). The charting path's only behaviour
  change is the sections model on CUDA; on the CPU (the golden and stress lanes) the model, key and result are the
  same, so `--expect none` is what a CPU golden run should show.

## Not done, or uncertain

- The reviewer's heavy comparison (the ensemble against fold 0 on four stress clips) was not rerun: its numbers are
  quoted in DESIGN 2.5 as the gate review's measurement.
- **Q29 was an open owner question** (DESIGN 9). The brief orders fold 0 on CUDA, and DESIGN now says the code does
  so and that the owner approves it with the release: the owner should be told this release answers Q29.
- Nothing ran on a GPU: the CUDA path is tested with the fake allin1 only, as before.

## Review (sc-reviewer, 2026-11-07, 95e2cf1) and its fixes (8149488)

No major finding. install-1's code is right; docs-3 and docs-6 check out. Two minor findings.

1. minor, docs: docs/DESIGN.md:3589 ("Solo 2 alone with the ensemble (CUDA)") and :3645 ("the ensemble the friend's CUDA runs") still say CUDA runs the ensemble. Neither line is in the diff, so the docs sweep missed them; they contradict sections.py AUTO_MODEL, pipeline.py's docstring and DESIGN 2.5/Q29. Repro: grep -n "ensemble (CUDA)\|friend's CUDA runs" docs/DESIGN.md. (:3499 is the M2-era record, fine.)
2. minor, test gap: tests/test_beatgrid.py::test_a_split_vote_keeps_only_a_sure_kick_and_only_under_the_threshold covers two of with_downbeats' three conditions. Dropping `and db["phase"] in top` (beatgrid.py:968) leaves all 4 cases green. Effect: a split vote between phases 1 and 2, with a sure kick on phase 0 that got no votes, keeps the kick's phase. Real code gives phase 2, flagged. Fix: add a case, e.g. 50 votes on beats[1::4] and 52 on beats[2::4], sure kick on 0, want 2.

- The orchestrator fixed the first minor (two DESIGN lines still saying CUDA runs the ensemble: 8149488). The second
  (a split vote between two phases neither of which is the sure kick's) is already held: with `db["phase"] in top`
  dropped, M6-03's `test_a_split_vote_keeps_a_sure_kick_phase` fails.
- **Q29** (DESIGN §9: fold 0 or the ensemble on CUDA) is answered by this order: fold 0 on every device, so the
  friend's GPU lane runs what every gate measurement read. The owner approves it with v0.3.0.
