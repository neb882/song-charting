# M5-11: the grid's octave by note density; the backbeat recorded, no longer a veto (builder's report)

Branch `m5-11-octave-by-density`, worktree `<wt>/m5-11`, from main at cfc7d5d (M5-10's merge; the runs' merge base),
main merged in at 0836f38 (origin/main 14f3044: only the M5-10 report's CI line). Paths below: `$GOLDEN` is
`$SONGCHARTER_GOLDEN` on the dev machine, `<scratchpad>` the session's scratch folder.

## Commits

| commit | what |
|---|---|
| cdf6c36 | `grid_octave` by density alone; `BACKBEAT_MIN` gone, the ratio recorded; the tests |
| b9b5dc9 | `eval/stress.json`: `pm2`, the orchestrator's generic entry as given |
| 06b982b | `tests/test_eval_stress.py`: the set has four songs (a made-up md5 and four alts for pm2) |
| cd41c7f | `eval/baseline/stress/`: the new baseline, four songs, from the merge base's stress run, scrubbed |
| 0836f38 | merge of origin/main (the M5-10 report's CI line) |
| b66bc37 | DESIGN 2.3 step 7 (and 8.1's row), M5-99 |

`tests/test_eval_stress.py` is outside the order's file list. Adding pm2 to `eval/stress.json` broke its pinned id
list, so I asked first, and the orchestrator approved the edit as part of the order's stress.json item (its own
commit; made-up md5 and alt count only). The test still fails with pm2 dropped from the set (checked: 1 failed).

## What changed

- `songcharter/assemble.py`: `grid_octave` doubles when the pooled share of short intervals is at least
  `OCTAVE_SHARE`, the doubled tempo is at most 300 BPM and there are at least 200 onsets. The backbeat ratio is still
  computed and recorded (`octave_stats.backbeat_ratio`, `backbeat_beats`, and a doubling's reason, as before) but
  decides nothing. `BACKBEAT_MIN` and `OctaveRules.backbeat_min` are removed, and so is `backbeat_min` from
  `octave_stats.thresholds` (a report field: report.json changes shape, the charts do not). The guard, the second
  pass, the half-beat test and the quantizer are untouched.
- **`OCTAVE_SHARE` stays 0.35**, not the geometric midpoint 0.32 of 0.199 and 0.527. Margins: x1.76 over the right
  grids, x1.51 under pm2 and x1.78 under troop. Why: a false doubling puts an ordinary song's HOPO threshold, slots,
  star power and solos at twice its pulse, and the guard does not stop one (the right grids' doublings keep 0.63-0.94
  of the evidence). A missed doubling only leaves v0.1's grid. So the threshold stays nearer the songs at half tempo.
  It changes nothing on the eleven songs either way.

## Tests (tests/test_assemble.py)

- `test_the_backbeat_is_recorded_not_a_veto` (it replaces the veto test): dense notes double with the snare on the
  lines (ratio 0.01), the midpoints (100), both (1.0), no drums (None) and too few confident beats (None, 10 beats);
  it checks the exact reasons and the recorded ratio.
- `test_a_song_at_half_tempo_with_its_snare_on_the_lines_doubles`: the pm2-like case, pooled 0.526, backbeat 0.19:
  octave 2, the ratio recorded, the exact reason.
- `test_a_dense_song_on_its_right_grid_stays`: a 140 BPM song in 16ths with a bass engine's double onsets 40 ms
  apart, pooled 0.25: stays with the snare on the lines or the midpoints. The threshold: 0.34 stays, 0.36 doubles.
- `test_the_backbeat_ratio_counts_confident_beats_only`: the old test's backbeat_ratio checks, kept.
- The thresholds' dict without backbeat_min.

**Mutations** (each run on the octave tests; every one failed at least one):

| break | failed |
|---|---|
| the veto restored at 0.34 | recorded_not_a_veto, half_tempo..., dense_song_on_its_right_grid |
| a veto under 0.1 only | recorded_not_a_veto, dense_song_on_its_right_grid |
| the backbeat doubles by itself (ratio > 2) | grid_octave_doubles..., needs_enough_onsets..., dense_song_on_its_right_grid |
| `OCTAVE_SHARE` 0.32 | recorded_not_a_veto, half_tempo..., dense_song_on_its_right_grid |
| `OCTAVE_SHARE` 0.37 | the same three |
| the share test `<= share + 0.02` | dense_song_on_its_right_grid |
| the ratio not recorded | five tests, the assemble end-to-end one included |
| the backbeat dropped from the reason | recorded_not_a_veto, half_tempo... |

## The eleven-song table (DESIGN 2.3)

M5-01's ten rows, plus pm2's from the merge base's stress run. troop, sooth and break measure the same today.

| song | first grid BPM | guitar / bass / drums share | pooled | backbeat |
|---|---|---|---|---|
| troop (half tempo) | 100.01 | 0.758 / 0.449 / 0.632 | 0.623 | 0.682 |
| pm2 (half tempo) | 99.99 | 0.587 / 0.321 / 0.621 | 0.527 | 0.190 |
| the seven references | 92.34-147.62 | | 0.001-0.199 (Lucretia 0.1985) | 0.001-0.172 |
| sooth (at double) | 153.97 | 0.059 / 0.121 / 0.000 | 0.062 | 0.003 |
| break | 115.50 | 0.000 / 0.307 / 0.009 | 0.151 | 0.012 |

The guard as built: troop 0.819 -> 0.678 (0.828; DESIGN said 0.997, which was the tracker variant M5-01 did not
build, now corrected), pm2 0.744 -> 0.702 (0.943).

## Golden (the seven references, `--expect none`)

`python -m eval.golden run --code <wt>/m5-11-base --out $GOLDEN/m5-11-old --threads 2`, then the same from the
branch into `$GOLDEN/m5-11-new` (at cd41c7f; uncommitted: DESIGN.md and M5-99 only), then
`python -m eval.golden diff $GOLDEN/m5-11-old $GOLDEN/m5-11-new --expect none`: exit 0, "**No UNEXPECTED change.**
Parts changed as expected: 0. Every song's results (hashes, counts, scores) identical: yes." No engine ran
(every cache answered; kept folders from 8ba3cbd). Every reference is still on octave 1 with the table's shares.

## The stress set, merge base against the branch

Runs: `python -m eval.golden run [--code <wt>/m5-11-base] --refs $EVAL_DATA/stress --work $GOLDEN/stress-work --out
$GOLDEN/m5-11-stress-{old,new} --threads 2`: both exit 0, warm, no engine ran, so no `--rerun` was needed.
`eval/stress.py score` on each (exit 0), `eval/stress.py compare` old new: exit 1, on one regression: "pm2 bass:
F1@50 0.800 -> 0.777".

- **troop, sooth, break: every number unchanged** (F1@50, F1@100, timing, chords, peaks, contour, HOPO, state,
  SP/min, solo, beat F1, downbeat F1). troop stays doubled (200.00 BPM), and sooth and break stay on octave 1.
- **pm2** (five charts; humans = each alt against the primary):

| line | merge base -> branch | humans | verdict |
|---|---|---|---|
| grid 190-206 BPM, octave 2 | 99.99, 1 -> 199.99, 2 (guard 0.943; half-beat 0.148, not shifted) | | pass |
| guitar F1@50 >= base + 0.10, each chart | primary 0.676->0.803, alt1 0.648->0.792, alt2 0.673->0.801, alt3 0.649->0.794, alt4 0.683->0.816 | 0.923-0.973 | pass |
| guitar median timing error < 15 ms | score.py (100-ms matches): primary 70.6->12.5, alt1 18.5, alt2 10.9, alt3 39.4, alt4 30.1. 50-ms matches: primary 3.8->3.6, alt1 -1.0, alt2 3.3, alt3 7.4, alt4 27.5 | 3.5 / -1.2 / -3.8 / -27.9 (50 ms) | pass on 50-ms matches (alt4 by its own offset); score.py's measure passes only against the primary and alt2 |
| chord share < 0.10 | 0.119 -> 0.112 | 0.02-0.04 | fail (the base too) |
| bass F1@50 not below the base's | primary 0.800->0.777, alt2 0.598->0.595 | alt2 0.710 | fail |
| drums F1@50 not below the base's | primary 0.784->0.973, alt4 0.827->0.901 | alt4 0.935 | pass |
| plain beat F1 >= 0.80 | 0.397->0.598 (octave-tolerant 0.576->0.658) | 1.000 | fail (the base too) |

Reported beside them: downbeat F1 0.007->0.014 (humans 1.000); star power 2.47->4.94 a minute (humans 1.65-5.49);
our solos 205-226, 267-365, 406-432 s -> 118-137, 303-370 (capped at 56 measures, 67 s on the doubled grid),
406-432 s, a solo share of 0.33->0.26 (humans 0.12-0.35; their spans are not read, only score.py's share). Guitar
onsets 2114 -> 2934 (primary 3593), with dropped_distinct 856 -> 36 and merged 0 on both grids, so the chords are
the engine's own.

**Decision** (the orchestrator, 2026-11-06, after my stop-and-report message): the doubling is adopted despite the
failing lines, with no tuning. The guitar gains 0.13-0.15 against all five charts and the drums 0.07-0.19. The beat
F1 and chord-share lines fail on the merge base too, and only the bass falls.

### Measurement 1: the bass per 30-s window (F1@50 against the primary)

Measured with score.py's own `main`, with `window_scores` patched to add each window's F1@50 and median signed error
(a scratch wrapper, `<scratchpad>/m511_windows.py`; numbers only). Its overall F1@50 reproduces stress.py's
(0.8003 -> 0.7766).

| window start (s) | 5 | 35 | 65 | 95 | 125 | 155 | 185 | 215 | 245 | 275 | 305 | 335 | 365 | 395 | 425 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| old | 0.822 | 0.899 | 0.805 | 0.825 | 0.848 | 0.782 | 0.859 | 0.521 | 0.640 | 0.700 | 0.817 | 0.872 | 0.843 | 0.918 | 0.756 |
| new | 0.742 | 0.878 | 0.788 | 0.818 | 0.802 | 0.767 | 0.802 | 0.507 | 0.653 | 0.664 | 0.792 | 0.865 | 0.832 | 0.870 | 0.756 |

The loss is **spread across the song**, not inside the 235-300 s stretch: 13 of 15 windows are lower, and 46 of the
47 lost 50-ms matches (1844 -> 1797) fall outside the windows at 215-305 s. Matched bass notes sit 4.4 ms off on both
grids. There are two candidates, untuned. (a) On the doubled grid the bass's 16th-note phase concentration is 0.0991,
just under the quantizer's `min_concentration` 0.1, so its measured 26 ms offset is not applied; 31 ms was applied on
the first grid, at 0.26. (b) 166 bass notes take the doubled grid's triplet slots (2 before), and moved_25ms
840 -> 1025.

### Measurement 2: the timing line against the humans' spread (guitar, Expert)

| chart | ours, 100-ms median (score.py) | ours, 50-ms median | that chart against the primary (50-ms; 100-ms) | predicted ours = 3.6 - (chart vs primary) |
|---|---|---|---|---|
| primary | 12.5 | 3.6 | — | — |
| alt1 | 18.5 | -1.0 | 3.5; 2.9 | 0.1 |
| alt2 | 10.9 | 3.3 | -1.2; -1.1 | 4.7 |
| alt3 | 39.4 | 7.4 | -3.8; -4.4 | 7.4 |
| alt4 | 30.1 | 27.5 | -27.9; -27.9 | 31.4 |

- On the 50-ms matches (the ones F1@50 counts), ours against each alt is explained by that alt's own offset from the
  primary. alt4 sits 27.9 ms off the primary in 13 of its 15 windows.
- score.py's `timing_err_ms_matched100` median is not a timing measure on dense passages. Its `match` is greedy and
  maximizes the count, so a note in a run of 16ths (75 ms apart at 200 BPM) pairs with its neighbour a slot away.
  alt3's 39.4 is **not one region**: on the 100-ms measure ours against alt3 runs 25-69 ms in six windows (95-155,
  215-245, 305-335, 365-395, 425+ s) while ours against the primary is 0.7-12 ms there. On the 50-ms matches it is
  at most 13.3 ms in any window. In the same windows alt1 and alt3 match many more of our notes than the primary does
  (e.g. 164-165 against 101 at 215 s), and in 245-275, 305-335, 365-395 and 425+ s the humans themselves disagree by
  20-66 ms on the 100-ms measure.
- The merge base's "70 ms" (the order's Why) is the same artifact: its 50-ms matches were 3.8 ms off. Its loss was
  the 856 onsets the first grid's slots dropped.

### The beat F1

The doubled grid has the beat count (1,457 beats against the primary's 1,435, ratio 1.015) and a median error of
13.6 ms, but about 40 % of its beats are more than 70 ms off. The build warns of a 170 BPM stretch at 235-300 s
(and 340 BPM readings there) that the 200 BPM grid does not follow; the humans' maps have 330 tempo markers, ours
153. The drums' matched notes sit within 14 ms of the primary's in every 30-s window (100-ms medians -0.8 to
13.7 ms on the doubled grid; up to 74.6 ms on the first). I did not localize the beat errors further (score.py has no per-window
beat F1); that is the M5-99 item.

## The new baseline (eval/baseline/stress/)

`python eval/stress.py baseline $GOLDEN/m5-11-stress-old eval/baseline/stress`: "scrubbed (34 values of the local
list checked)" for both files. Then a script read the four primary md5s' first 8 characters (and the ten alts') from
the local list and counted them, with /home/, /tmp/, <shm>/ and /root/, in summary.json, stress_scores.json and
README.md: 0 found. There are no `<redacted>` markers either. The README is updated: four songs, main at cfc7d5d,
warm from the kept folders made at 8ba3cbd.

## Docs

- DESIGN 2.3 step 7: the density test; the backbeat recorded, with its history; `OCTAVE_SHARE` kept and why; the
  eleven-song table with pm2's row; the guard's ratios as built; M5-11's results, the decision and the two
  measurements. One phrase in 8.1's table row ("note density since M5-11; the backbeat recorded"), which named the
  backbeat as a test, is outside 2.3 but the same file.
- M5-99: "The octave pass's threshold and guard, provisional (M5-01, M5-11)" (two songs that need doubling, the
  20-song set); "The second power-metal song on its doubled grid (M5-11)": the bass (measurement 1 and the two
  candidates), a tempo change under a doubled grid (beat F1 0.598, `keep_line` as a suspect to measure), the
  engine's chord share, score.py's timing measure, and solos in measures on a doubled grid.
- PROGRESS.json not edited (the brief).

## Checks

- Suite: `tools/heavy.sh uv run python -m pytest -q -p no:cacheprovider --basetemp=<shm>/pt-m5-11` (code at
  0836f38, docs uncommitted): `1017 passed, 4 skipped in 711.51s (0:11:51)`.
- Octave tests alone, and the stress-set tests: passed. test_eval_stress with pm2 dropped: 1 failed, as it should.
- Golden: exit 0, no UNEXPECTED change, every song identical.
- Stress: as above; `stress.py compare` exit 1 on pm2's bass alone.
- CI: <repo>/actions/runs/42175557125 on b66bc37 (the head): **success**, linux and
  windows. Its linux log has the full suite, `1017 passed, 4 skipped in 346.28s` (the same count as the local run,
  so the new tests ran), and the linux.d hooks 10-lanes to 75-update. This order adds no hook (its checks are
  tests). An earlier run, 42173984599 on 0836f38, was cancelled by the head's run on the same ref; its windows job
  had passed.
- **Scan** of `git diff origin/main...HEAD` (the added lines) and of the commit messages: 0 of the local list's 34
  titles, artists, charters and md5s, 0 md5 prefixes, no /home/, /tmp/, <shm>/ or /root/ path, no email, and no
  model name outside the required trailer lines.

## Uncertain or left

- troop's guard margin is x1.18 (0.828 against 0.7). It is unchanged by this order, but it is the thinnest real
  doubling.
- The bass's two candidates are untested as causes (no tuning by the order's rule).
- The timing line depends on the measure: on score.py's 100-ms median it fails against alt1, alt3 and alt4.
- report.json's `octave_stats.thresholds` no longer has `backbeat_min`: nothing in the repository reads it (checked
  with grep), but an outside reader of old reports would see it gone.
- Disk at the end: 15 GB free (`df -h /`: 252G, 25G used); the four run folders are 37-45 MB each, kept for the
  reviewer.
- Scratch kept for the reviewer: the detached worktree `<wt>/m5-11-base` (cfc7d5d), `<scratchpad>/m511-win*`
  (score.py outputs), and the progress log `<scratchpad>/briefs/m5-11.progress.log`.

## Review fix (orchestrator, commit 0bea919; a test only, so no golden rerun)

- **R1** (the 0.35 boundary untested): `test_a_dense_song_on_its_right_grid_stays` now runs a share of exactly
  0.35 (`shares(175)`): it doubles ("at least"). It fails on the reviewer's break (`pooled <= rules.share`), which
  every octave test let through before. CI on 0bea919: run 42179975915, success.
- **R2** (PROGRESS's deferred M5-01 item still named `BACKBEAT_MIN` 0.34 as a threshold): fixed in PROGRESS at the
  merge.
- The reviewer's bass table (below) supports the triplet suspect over the offset one; M5-99's item says so at the
  merge.

## Review (sc-reviewer, 2026-11-06)


## Findings (2, both minor; no major)

**R1 (minor): the 0.35 boundary is untested.** songcharter/assemble.py:762 `if pooled < rules.share:`. Changing it
to `<=` (a share of exactly 0.35 then stays at octave 1, against the reason text and DESIGN's "at least") leaves
every octave test green: `-k 'octave or backbeat or half_tempo or right_grid' tests/test_assemble.py` -> `10 passed`.
test_a_dense_song_on_its_right_grid_stays tests 0.34 and 0.36 only. Exactly 0.35 does double today
(grid_octave({"guitar": shares(175)}, SLOW_GRID, None) -> octave 2, pooled 0.35, "at least 35.0%"; also with two
parts at n=140..1000). The fix is one more line in that test: shares(175) -> 2. On real songs this almost never
happens, so it is minor.

**R2 (minor): PROGRESS.json still names the veto.** docs/PROGRESS.json:205 (the deferred [M5-01] item) lists
"OCTAVE_SHARE 0.35, BACKBEAT_MIN 0.34" as the octave thresholds. The code has no BACKBEAT_MIN after this order. The
builder was told not to edit PROGRESS, so this is the orchestrator's to update when the order lands.

## Lenses with no finding

- Privacy: a script read stress.local.json (4 songs, 14 md5s, 6 titles, 4 artists, 11 charters) and counted them in
  the added lines, the 6 commit messages and the committed baseline/stress.json. It printed counts only: 0 md5s or
  md5 prefixes, 0 artists, 0 charters, 0 pm2 title/artist tokens. Its two hits were already on main: the id `break`
  (an id the owner chose) and a common word in prose. Also 0 /home, /tmp, /dev/shm or /root paths, 0 emails besides
  the trailer, and no model names besides the trailers.
- Correctness: nothing reads backbeat_min any more (code, eval, UI, preview); only historical docs mention it, plus
  R2. The diff leaves _octave_pass, the guard and the half-beat test alone. I tried 4 more mutations of my own and the
  tests caught each one: weighting by intervals, a veto on "too few confident beats", the ratio computed on half
  the beats, and a narrow veto. Golden: the 7 notes.chart files old/new are identical. Stress: troop, sooth and
  break notes.chart are identical. Their report.json octave_stats match apart from the reason text and the dropped
  threshold.
- Numbers: pm2's lines, recomputed from both runs' stress_scores.json and report.json octave_stats, match the report
  and DESIGN 2.3's tables. These include the shares, pooled 0.527, backbeat 0.1895, guard 0.9434, every F1, error,
  chord share and SP figure, the humans' ranges and the ×1.76/1.51/1.78/2.65/1.1 ratios. The committed baseline is
  the merge base's run: no non-string differences in summary.json or stress_scores.json. `stress.py compare
  eval/baseline/stress m5-11-stress-new` gives exit 1, "pm2 bass: F1@50 0.800 → 0.777", the same as old-vs-new.
- Measurement 2, spot check (ours vs alt3 guitar, new run): the 100-ms median of 39.4 reproduces. 56% of the
  100-ms pairs are more than 50 ms off, in two modes at -70..-60 and +70..+90 ms (a 16th at 200 BPM is 75 ms). The
  nearest-neighbour median is 3.5 ms and the 50-ms median 7.4. So the 39.4 comes from the greedy matcher pairing
  notes one slot apart, as the builder said.

## M5-99: the bass suspects

The numbers support (b), the triplet slots. I scored ours against the primary, bass Expert, matched at 50 ms:

- Notes on triplet slots: 2 -> 174 (my count by tick).
- Of those, unmatched: 1 -> 75. All unmatched notes: 193 -> 260 (+67), so the triplet notes account for the whole
  increase.
- The triplet notes sit a median 48.4 ms from the nearest human note, the gap between a triplet slot and a straight
  slot. Many of the matched ones are borderline at 50 ms.

(a), the offset not applied, has no support in the numbers: the matched median error is 4.3 ms on the old grid and
4.4 ms on the new one. Whether the missing offset is what pushes the late notes onto triplet slots is untested.
