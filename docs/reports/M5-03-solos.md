# M5-03: solos on long instrumentals (builder's report)

Branch `m5-03-solos` from main at 1ed6839; worktree `wt/m5-03`. Order: `docs/work-orders/M5-03-solos.md`.

## Commits

(filled at the end)

## What changed

- `songcharter/starpower.py`
  - `SoloRules` gains `max_measures` 56, `max_seconds` 100.0 and `max_share` 0.40 (set from step 1, below); `min_measures`
    4, `min_onsets` 16 and `max_solos` 3 stay.
  - `solo_sections(..., tempo=None, rules=SOLO_RULES)`: consecutive Solo sections are one run as before; with `tempo`
    (and no `names`), a run over either cap is split by `_Caps.split`: its parts (the sections in it) grouped from the
    run's start while the group stays within both caps; a part over a cap on its own cut by `_Caps.cut` at the
    measure line where the first cap is reached, the rest its own candidate (cut again while over a cap). A run within
    both caps is one candidate. Without `tempo`, or with `names`, nothing is split (the old behaviour and signature).
  - `place_solos(..., record=None)`: candidates with the minimums, ranked by Expert onsets per measure (ties to the
    earlier start), taken up to `max_solos`, skipping any whose seconds (first to last onset) would take the total
    past `max_share` of the first..last Expert onset's; sorted by start. `names`: no split, no share cap (the
    minimums and the 3-solo cap still apply, as the docstring promised). `record` gets `rules` (asdict of SoloRules),
    `capped` (False with names), `solos` and `skipped_by_share` (each: start and end ticks, measures, onsets,
    `per_measure`).
  - `place_phrases(..., solo_record=None)` passes it to `place_solos` for Expert lead guitar.
  - The module docstring's solo paragraph describes the splitting and the choice.
- `songcharter/assemble.py` (approved by the orchestrator mid-build; the order's Files line excluded it only to avoid
  M5-01's overlap): line 1614 `solo_record: dict = {}`; line 1617 passes `solo_record=solo_record` to
  `place_phrases`; lines 1705-1711 add to `report["phrases"]["guitar"]`, when solos were placed: `solo_rules` (the
  values and `capped`), `solo_details` and `solos_skipped_by_share` (each row's start and end converted to song
  seconds with `_in_s`, as the solos are). `phrases.guitar.solos` is unchanged. Nothing else in assemble.py changed.
- `songcharter/preview.py`: the overview draws a green band (`SOLO_COLOR`) per solo in its row (axes 0.84-0.91),
  under the star power's cyan band (now `SP_COLOR`, same colour); the title's legend and the docstring say so.
- `docs/DESIGN.md` 2.10: the "Length and share (M5-03)" bullet: the three rules, the measured table, the choice, the
  report fields; the solo evaluation's numbers are untouched.

## Commits (branch m5-03-solos, pushed)

- 2dc7746 Solos: a longest length and a largest share of the song (starpower.py, assemble.py wiring, their tests)
- bf37abb The preview's overview draws the solos
- 044cf78 DESIGN 2.10: a solo's longest length and the solos' largest share

## Step 1: human solos (numbers only; `importers.read_song`, scratch script, never committed)

| chart | solos: measures of its own map (s) | share of first..last Expert onset |
|---|---|---|
| refs: all_the_small_things, creep, drunk_drivers, take_me_out | none | 0 |
| ref kimochi_warui | 8.0 (17.9) | 0.064 |
| ref lucretia | 32.0 (77.0) | 0.333 |
| troop primary | 53.0 (63.6) | 0.214 |
| troop alt 1 | 4.3 (5.1), 4.3 (5.1), 52.8 (63.3) | 0.248 |
| troop alt 2 | 4.1 (5.0), 4.3 (5.1), 15.9 (19.1), 52.9 (63.5) | 0.311 |
| sooth primary | none | 0 |
| sooth alt | 31.8 (95.9), 32.0 (96.9) | 0.357 |
| break primary | 13.0 (27.0) | 0.163 |
| break lead alt | 12.0 (24.9) | 0.150 |

(break's other two charts have no Expert guitar.) The order's 11 charts: 12 solos; with break 13 charts, 14 solos.
Either way: p95 length 52.9 measures and 96.4 s (96.3 with break), largest share 0.357, median 1 solo a chart.
Matches the advisor's probe.

## The rules' values

- max_measures 56: p95 52.9 rounded up to a multiple of 8 (16-64).
- max_seconds 100: p95 96.4 s rounded up to the next 10 s (30-120).
- max_share 0.40: 0.357 rounded up to the next 0.05 (at least 0.15).

## Tests, and breaking the code

New: test_a_long_solo_run_is_split_into_parts_within_the_caps, test_a_run_is_cut_at_the_seconds_cap_on_a_fast_map,
test_the_densest_solos_win, test_the_share_cap_skips_a_solo_and_takes_the_next_that_fits (test_starpower.py);
test_the_overview_draws_the_solos (test_preview.py); report assertions in test_assemble.py's
test_expert_only_and_solos_on_named_sections. Existing test changed: test_solos_come_from_confirmed_solo_sections, whose
synthetic song is 60% solo: its first assertion now passes `SoloRules(max_share=1.0)` (assertion unchanged), plus a
new line that the default cap keeps only the first solo. All other existing tests unchanged.

22 breaks, each run against the tests (scratch script), all caught: no grouping; no split; no cut; one cut only;
remainder grouped with the next part; no seconds cap; no measures cap; names split too; rank by onsets; ties to the
later start; no share cap; share cap stops instead of skipping; share cap on names too; share in ticks; record not
filled; place_phrases drops the record; defaults moved; assemble: no solo report / ticks not converted / capped
dropped; preview: no bands / bands over the star power's.

## Checks run

- Targeted tests (main venv, PYTHONPATH=worktree): tests/test_starpower.py 29 passed; tests/test_preview.py 23 passed;
  the assemble named-solos test passed.
- CI run 42085779949 (workflow_dispatch on bf37abb): success, linux and windows. Linux suite "953 passed, 4 skipped"
  (main's run at 2399a9b: 948, so the 5 new tests ran). No CI hook added: nothing beyond the suite to check.
- NOT RUN: the local full suite, the golden diff, the stress runs. See "Not done".

## Owner's v0.1 charts (optional context, numbers only, new rules on their notes and sections)

- troop (our map 100 BPM, the humans' 198): v0.1 one solo 2:18.3-3:58.9 (101 s), share 0.34. New: 2:18.3-3:39.7 (81 s,
  34 m) and 3:39.8-3:58.9 (19 s, 8 m), back to back, share 0.34. The run is just over the 100-s cap, so it splits but
  both parts are kept. Human solos are 2:57.5-4:01 (all three charts); the overlap is 0.67 of the primary's.
- sooth (our map 154 BPM, the humans' 80): v0.1 1:08.7-1:45.1 and 1:59.9-8:22.0, share 0.84. New: 3:17.4-4:45.8 (88 s, 56 m)
  and 4:45.9-6:06.4 (81 s, 49 m), back to back, share 0.34. Four candidates were skipped by the share cap. The alt
  chart's human solos are 4:30-6:06 (fully covered) and 6:56-8:33 (not covered).
- break: unchanged, 1:50.1-2:18.8.

## Uncertain, and for the owner

1. Back-to-back solos: both parts of a split run can be taken (the order does not forbid it). On troop that keeps the
   same 101 s of markers as two adjacent solos, so the coverage does not change. If that is unwanted, the options are
   a gap rule, or not taking two parts of one run, or a tighter share. That is a decision, not built.
2. songcharter/pipeline.py:73's docstring lists place_solos' rules as "16 Expert onsets, 4 measures, at most 3 a song".
   It is still true but no longer complete. Left alone because it is M5-02's file; add "and the caps on length and
   share" after the merge.
3. The share counts each solo from its first onset to its last, against the first..last Expert onset (seconds).

## Not done (the handback was called for before they ran)

The local suite, the golden diff (base: /dev/shm/m503-base, a detached worktree at 1ed6839) and the stress runs (merge
base against branch, stress diff, stress.py score and compare). They are queued as one detached chain, started at
19:00 UTC: scratch m503/scripts/chain.sh, log m503/chain.log, step logs m503/logs/. It waits behind M5-02's golden
run, which held the lock from 18:23. Its outputs go to $DEV/golden/m5-03-{old,new,stress-old,stress-new}.
scratch m503/scripts/stress_lines.py (OLD NEW human_solos.json) prints the stress lines and every stress_scores
field that differs. The first install attempt was queued behind the lock for 30 minutes, hit the background-task
limit and was killed; the chain reruns it. DESIGN 2.10 still needs the golden and stress numbers once they exist.

Scan: git diff main...HEAD and the commit messages were scanned for lyrics, audio, model names and personal details;
none found. The "lyric" matches are assemble's existing `lyrics` parameter in hunk headers.

## Update after the orchestrator's decisions (2026-11-05, 19:06 UTC)

- The first chain was stopped cleanly: its process group was killed while its suite held the lock, and the lock went
  straight to M5-02's stress run. Nothing stale was left, and its /dev/shm temp folders were removed.
- The gap rule, commit 2669be5 (pushed):
  - `SoloRules.min_gap_measures = 4.0`. While choosing (densest first), a candidate is skipped when it starts within
    4 measures after a kept solo's end, or ends within 4 measures before a kept solo's start (`_Caps.near`, measured
    in fractional measures with `_Caps.position`). Named sections are exempt.
  - The record gains `skipped_by_gap`. assemble.py's report block gains `solos_skipped_by_gap` (one more line in
    the same lines 1705-1712).
- New test `test_the_parts_of_a_split_run_never_come_back_to_back`, on a 100-BPM map:
  - a 34 + 8-measure run (100.8 s) is split at the seconds cap, and only the denser part is kept, whether it comes
    first or second;
  - two runs 6 measures apart are both kept;
  - two runs 3 measures apart keep only the denser one;
  - named sections are exempt.
- `test_the_densest_solos_win`: the runs were moved 6 measures apart (they had been 2 apart, which the gap rule now
  skips). The expected picks did not change.
- Breaks, now 29 in all and every one caught (scratch m503/mutate2.log). The new ones: no gap rule; the gap after a
  kept solo only; the gap before only; names gapped too; the gap counted in whole measures; gap-skipped candidates
  not recorded; assemble drops the gap list.
- Targeted tests: test_starpower.py, test_preview.py and the named-solos assemble test: 54 passed.
- DESIGN 2.10 records the gap rule and the owner's-charts numbers before and after (input seconds):
  - troop: 2:14.4-3:55.1 (share 0.34) becomes 2:14.4-3:35.9 (81 s, share 0.27). The 19-s rest is skipped by the gap.
    The kept part covers 0.60-0.65 of the human solo.
  - sooth: 1:04.8-1:41.2 and 1:56.0-8:18.1 (share 0.84) become 1:04.8-1:41.2, 4:42.0-6:02.5 and 7:29.2-8:18.1 (share
    0.33). Two candidates were skipped by the gap and one by the share. The three cover 0.84 and 0.50 of the alt
    chart's two human solos.
  - break: unchanged.
- CI on 2669be5: run 42090736009 was started; its result was not read before this handback.
- The chain was restarted at 19:06 UTC and was waiting for the lock behind M5-02's stress run at handback (see the
  final message for what is still running).

## Update 2: the densest window (orchestrator's decision, 2026-11-05, 22:23 UTC, commit 17055a6)

- Why: the first chain2 stress run gave troop one solo, 3:31.8-3:59.3 (27.5 s, 23 measures), overlapping the primary's
  human solo by 0.43, under the order's half. Grouping from the run's start had left a dense tail, and the gap rule
  then dropped the larger part beside it. Earlier lines of that run, saved in scratch m503/run1/stress_lines.txt:
  - troop: old 2:28.2-3:59.3 (0.97, 0.98, 1.00 of the three charts' main solo); new 0.43, 0.43, 0.42.
  - sooth: old share 0.80 (1.00, 1.00); new share 0.30, 4:57.5-6:11.1 and 7:50.1-8:52.3 (0.72, 0.44).
  - break: unchanged, 1:46.5-2:15.4 (0.76, 0.78).
  - golden and stress diffs exit 0; stress_scores differ only in solo_share.
- The change: `_Caps.split(a, b, onsets)` returns the run when it is within both caps. Otherwise it returns the
  run's densest window (`_Caps.window`) and splits the rest on either side the same way, recursively.
  - The window runs from a measure line (or the run's start) to a measure line (or the run's end), within both caps,
    with the most Expert onsets, ties to the earlier start. It is found with two pointers and is at least one measure
    long.
  - `solo_sections` takes `onsets`. Section starts inside a run no longer matter.
  - The gap rule and the share cap are unchanged.
- Tests:
  - `test_a_long_solo_run_is_split_around_its_densest_window`: on even notes the window is the earliest; the rest is
    split again; every bound is on a measure line; every piece is within both caps; no tempo map or names: no split.
  - `test_a_long_run_keeps_its_densest_window` (troop-like): 200 BPM, a 76-measure, 91-s run in four lettered parts,
    the dense 53 measures at 41-93. Candidates are (21, 17), (38, 56) and (94, 3); the solo is the 56-measure window
    38-94; the 17 measures before it are skipped by the gap.
  - The seconds-cap test now ignores parts.
  - The gap test was rebuilt on window plus rest, on both sides, with the share cap off.
- Breaks: 32, all caught (scratch m503/mutate4.log). The window's breaks: from the run's start only (grouping from
  the start); sliding on onsets (not measure-aligned); ties to the later start; fewest onsets; rest not split again;
  rest dropped; window one measure short.
- A trap found and fixed: the break script had left a stale .pyc. The "defaults moved" break (56 to 64) has the same
  size and was restored within the same second, so Python kept the mutated bytecode. That showed in an owner-chart
  run as 61- and 64-measure candidates. Bytecode was purged; the script now clears `__pycache__` around every break
  and writes none; all 32 breaks re-ran clean. chain2's first run used max_measures 56 (its report.json solo_rules
  say so), so it was not affected.
- Targeted tests: 55 passed (starpower, preview, the named-solos assemble test).
- Owner's v0.1 charts with the window (in DESIGN 2.10):
  - troop: 2:14.4-3:52.7 (98 s, share 0.33), 0.87 of the human solo.
  - sooth: 4:17.1-5:49.2 and 6:52.4-8:16.6 (share 0.35), 0.82 and 0.83 of the alt chart's two solos.
  - break: unchanged.
- DESIGN 2.10: rule 1 now describes the window and the decision's reason; the owner-chart paragraph is updated.

## Golden, chain2 on 17055a6 (22:23-22:35 UTC)

- golden-old exit 0, golden-new exit 0, golden-diff `--expect guitar` exit 0: "No UNEXPECTED change", 4 parts changed
  as expected.
- Pooled guitar F1@50 identical: expert 0.8527, hard 0.8010, medium 0.7474, easy 0.6150. Every song's onsets and F1
  are identical old to new.
- The only changes are lucretia's guitar at all four levels. Its human chart has a solo (140.7-217.7 s).
- **Finding:** lucretia's one solo, 140.726-236.683 s (96 s), is within both length caps but is now skipped by the
  share cap. The span is about 231 s, so 0.40 allows 92.4 s. The new chart has no solo on the one reference where
  the label found the human solo. The previous chain2 run (grouping) showed the same change (scratch
  m503/run1/golden_report.md), so this comes from the share cap as the order specified, not from the window.
  Options for the orchestrator:
  - (a) when a candidate alone is over the remaining budget, take its densest window within the budget (about 92 s
    here, still covering most of the human solo) instead of skipping it;
  - (b) apply the share cap only to the solos after the first;
  - (c) a looser share.
  Not built: it is a decision.

## Stress, chain2 on 17055a6

- stress-old exit 0 (22:40:45), stress-new exit 0 (22:55:05), stress-diff `--expect guitar` exit 0: "No UNEXPECTED
  change", 8 parts changed as expected. Lines from scratch m503/stress_lines2.txt (old -> new):
  - troop: 2:28.2-3:59.3 (91.1 s, share 0.31) -> 2:52.2-3:59.3 (56 measures, 67.1 s, 12.5 onsets/measure, share
    0.23); 2:28.2-2:52.1 (20 measures) skipped by the gap. Overlap with the human solo: primary 0.97, alt 1 0.98,
    alt 2 1.00 (needs at least 0.5: passes). At most 3 solos, within both caps and the share: passes.
  - sooth: 1:11.2-1:34.8, 2:02.4-6:11.1, 6:23.6-8:52.3 (share 0.80) -> 2:02.4-2:40.6 (24 m, 38.2 s),
    4:25.7-5:53.0 (56 m, 87.3 s), 7:22.7-8:46.0 (56 m, 83.4 s), share 0.397. 6:23.6-7:21.9 skipped by the gap,
    2:40.8-4:09.3 by the share. Overlap with the alt chart's human solos 4:30.3-6:06.2: 0.86; 6:56.1-8:33.0: 0.73.
    Passes all four checks.
  - break: unchanged, 1:46.5-2:15.4 (share 0.17); overlap 0.76 (primary) and 0.78 (alt).
- DESIGN 2.10 gets the golden and stress lines (the "Evaluation" paragraph); still uncommitted until the scores are in.

## Final state (23:10 UTC)

- chain2 finished: golden-old/new/diff, stress-old/new/diff, score-old/new and stress-compare all exited 0. Compare:
  "Regressions (a primary F1@50 down by more than 0.01): 0".
- stress_scores.json: 5 of 483 fields differ, all solo_share:
  - sooth primary and alt1: 0.8005 -> 0.3971;
  - troop primary, alt1 and alt2: 0.3064 -> 0.2257.
- CI on 17055a6 (run 42121028479): success. df47a22 (DESIGN only) was pushed without a CI run.
- Commits: 2dc7746, bf37abb, 044cf78, 2669be5, 17055a6, df47a22 (DESIGN 2.10's results).
- Open: Lucretia's solo is lost to the share cap (see "Golden, chain2"). The base worktree /dev/shm/m503-base is kept
  for a rerun if that is changed; remove it at the merge. df -h /: 17 GB free.
- Scan: the diff against main and the commit messages were rescanned; nothing forbidden ("F1@50" was the only "@").

## Update 3: the share trim (option (a)), the merge, suite and CI (23:30 UTC)

- Merged origin/main into the branch (6e75281: M5-02, M5-04, M5-05 and M5-08's PROGRESS). No dependency changes.
- d88a6c9: a candidate that would take the solos past max_share is cut by `_trim` to its densest measure-aligned
  window (`_Caps.window` with max_seconds set to the budget left), or skipped when that window lacks the minimums.
  - The record gets `trimmed_by_share` (the candidates as they were), and report.json gets
    `phrases.guitar.solos_trimmed_by_share` (one more line in assemble.py's block).
  - pipeline.py:73's docstring names the new rules.
  - DESIGN 2.10: the cut in the choice paragraph, Lucretia's case, and the report field.
- Tests:
  - `test_a_song_never_loses_its_only_solo_to_the_share_cap` (a 48-measure, 96-s run against a 95.6-s budget keeps
    a 47-measure window, start measure-aligned, within the budget);
  - `test_the_share_cap_trims_or_skips_a_solo_and_takes_the_next_that_fits` (budget left 7.5 s: the third's window
    is under the minimums and skipped, the fourth fits; at 0.25 the third is trimmed to 5 measures; at 0.40 all fit).
- 38 breaks, all caught (scratch m503/mutate5.log, plus the re-pointed stop-instead-of-skip break). The trim's
  breaks: skip as before; the window not measure-aligned; the window over the budget; the minimums not checked;
  trimmed not recorded; assemble drops the list.
- Targeted tests: 56 passed. Full suite through tools/heavy.sh: 978 passed, 4 skipped (11:06).
- CI 42128089626 on d88a6c9: success, linux and windows; linux suite 978 passed, 4 skipped.
- /dev/shm/m503-base removed. Golden and stress were not run, as instructed: they wait for the orchestrator's
  rebuild of the kept folders at main, then chain2 runs warm, with old = main's rebuilt base and new = this branch.

## Chain3: the warm run against main's rebuilt base (8ba3cbd), on d88a6c9

Every step exited 0: golden-new, golden-diff, stress-new, stress-diff, score-new, compare (0 regressions) and
stress-lines (scratch m503/chain3.log, logs3/).
- Golden: no UNEXPECTED change; only Lucretia's guitar moved; onsets and F1 identical (pooled guitar F1@50 0.8527,
  0.8010, 0.7474, 0.6150). Lucretia's solo was 140.7-236.7 s in the base (the share skip came from this branch; base
  main had placed it) and is now 140.7-232.2 s: 38 measures and 508 onsets, cut from the 40-measure, 531-onset
  candidate. Its human solo is 140.7-217.7 s.
- Stress:
  - troop: 2:52.2-3:59.3 (share 0.23), overlapping 0.97, 0.98 and 1.00 of the human solo; 2:28.2-2:52.1 skipped by
    the gap.
  - sooth: 3:01.3-3:45.3 (the 2:40.8-4:09.3 candidate cut to fit), 4:25.7-5:53.0 and 7:22.7-8:46.0, share 0.398;
    overlaps 0.86 and 0.73.
  - break: unchanged (0.76, 0.78).
  - stress_scores: 5 of 481 fields differ, all solo_share (sooth 0.7971 -> 0.3978, troop 0.3064 -> 0.2257).

## Review fixes (commit 66e5e87; tests and docs only, no code change, so no golden rerun)

- F1: `test_the_rest_before_a_window_at_the_run_end_is_split_again`. A 150-measure run with its densest 50 at the
  end gives candidates (9, 50), (59, 50) and (109, 50). The break `[(a, s)] if s > a else []` fails it.
- F2: `test_a_trimmed_window_under_16_onsets_is_skipped`. 10 s left: the sparse third would be cut to 5 measures
  with 10 onsets, so it is skipped. Removing `len(inside) < rules.min_onsets or` fails it.
- F3: `test_the_solo_report_without_names` (test_assemble.py), a labels build with two solo runs over the share.
  The first run is trimmed to its window and the second is skipped by the share. report.json's trimmed, skipped and
  detail rows are checked in song seconds. The `list(solo_record[k])` break fails it, for each of the three lists.
- N1: DESIGN 2.10's Evaluation paragraph now gives chain3's numbers, Lucretia's included.
- Breaks run: 5, all caught (scratch m503/scripts/mutate_review.py).
- Targeted tests: starpower 34 passed; the two assemble solo tests passed.
- Full suite through tools/heavy.sh (a tracked background task): 981 passed, 4 skipped (11:36).
- CI 42158082353 on 66e5e87: success, linux and windows; linux suite 981 passed, 4 skipped.
- Rescanned the diff against main and the commit messages: nothing forbidden.

## Review (sc-reviewer, 2026-11-06)

# M5-03 review (sc-reviewer, 2026-11-06): 0 major, 3 minor, one docs note

(Saved by the orchestrator from the reviewer's reply.) 27 breaks in a copy, 22 caught.

- **F1 (test gap), starpower.py:513:** the left side of a split run is never split again unnoticed: replacing
  `self.split(a, s, onsets) if s > a else []` with `[(a, s)] if s > a else []` passes (32 passed). On a 150-measure run
  whose densest 50 measures are at the end, the break ships a 190-s solo over both caps. A test with the dense part at
  the run's end and an over-cap rest before it catches it.
- **F2 (test gap), starpower.py:618:** `_trim` without its 16-onset check passes: the trim tests only fail the
  4-measure minimum. With SoloRules(max_share=0.25) and a sparse run of 8 onsets, the break keeps a solo under the
  minimum.
- **F3 (test gap), assemble.py:1711-1713:** the three skipped/trimmed lists' tick-to-seconds conversion is untested
  (the only assemble test uses named sections, where all three are empty): an assemble test without names and with
  one candidate skipped catches it.
- **N1 (docs):** DESIGN 2.10's Evaluation paragraph still says Lucretia's trimmed-solo numbers are "to come": the warm
  golden run $DEV/golden/m5-03-new2 has them (base-main 140.7-236.7 s skipped -> 140.7-232.2 s trimmed, 40
  measures, 531 onsets; the human solo 140.7-217.7 s).
- Not reported (no shipped effect): the `room <= 0` early return, `not caps.within` in _trim, `<` vs `<=` at exactly
  4.0 measures, the untrimmed length in the share total.
- Checked: the window search (two pointers, ties to the earlier start, the recursion terminates), the gap on both
  sides, the share budget over the first-to-last Expert onset span, named sections exempt (the 3-solo cap for names now
  ranks by density, harmless), determinism, the preview band, pipeline.py's docstring, DESIGN 2.10's rules.
