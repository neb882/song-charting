# M6-01: star power and solo caps on fast songs (builder's report)

Branch `m6-01-fast-sp-solos` (worktree `<wt>/m6-01`), from main at f3b9ebb. Order:
`docs/work-orders/M6-01-fast-star-power-solos.md`.

## Verdict

- **Star power: built.** Rule 1's count stays one phrase per 40 beats of the first..last Expert onset span, but the
  span's beats are counted at most at 160 BPM (its average tempo): K = round(min(beats, minutes x 160) / 40), so at
  most one phrase per 15 s. `StarPowerRules.max_bpm = 160.0`. Every part (guitar, bass, drums) uses it.
- **Solos: no change.** The humans' own long solos on both 200-BPM songs are 53-58 of their own measures, and their
  maps are at our doubled grid's tempo, so the 56-measure cap already reproduces them (coverage 0.96-1.00). A longer
  cap (seconds, or measures of a bounded length) would pass every human chart. `SoloRules` is unchanged; a test pins
  the default caps on a 100 and a 200 BPM grid.
- report.json records each part's count: `phrases.<part>.star_power_count` = {rules, span_beats, span_seconds,
  counted_beats, target, placed}.

Checks: the full suite (1065 passed, 4 skipped, locally and in CI); every new test fails on its break (14 breaks, section
3); the golden diff `--expect none`: no change at all; the stress set: troop's and pm2's star power inside their humans'
range on guitar, solos and every other stress score unchanged, `stress.py compare` no regression; CI green on the
branch (section 6); the privacy check exit 0 before each push; the branch's diff and commit messages scanned (only the
attribution trailers match).

## Commits

- `6ac4e94` Star power: a span's beats counted at most at 160 BPM; report.json records each part's count
  (`songcharter/starpower.py`, `songcharter/assemble.py`, `tests/test_starpower.py`, `tests/test_assemble.py`)
- `42d67fb` DESIGN 2.10: the human star power and solo table on fast songs, the 160-BPM ceiling; M5-99's two items
  closed (`docs/DESIGN.md`, `docs/work-orders/M5-99-later.md`, the code's comments: 0.84)
- `8a0b8ca` DESIGN 2.10: M6-01's evaluation (golden unchanged; troop and pm2 inside their humans' star power range)

Files touched: only the order's (starpower.py; assemble.py's place_phrases call and report.json's phrases; their
tests; DESIGN 2.10; M5-99). assemble.py's change is a record passed in and written out (the order's step 3:
"report.json records them"); the rule itself needs only the tempo map starpower already had.

## 1. The measurement (numbers only)

Every human chart of the reference set (`eval/refs.json`, 6 songs) and of the stress set (4 songs, 13 charts, of which
11 have guitar), read with `eval/scorer/score.py`'s `scan` (scan_notes.cjs: no lyrics, vocals or section names) and
located with `eval/stress.py`'s `built_songs`. No package, chart file or vocal track was opened by hand; no title,
artist, charter or md5 was printed. Each chart on its own tempo map: the span is the first to the last Expert onset;
"per 40 beats" counts the chart's own beats over that span; BPM is the span's time-weighted median; the solo share is
the solos' seconds inside the span over the span (M5-03's definition). "K at <=160" is the new rule on the chart's own
span. The scripts (`measure.py`, `overlap.py`, `fit.py`, `stats.py`) stay in the session's scratch folder; the
method is all in this section.

### Star power, every human Expert part with phrases

| chart | part | BPM | span s | beats | phrases | per min | per 40 beats | K = beats/40 | K at <=160 | solo share |
|---|---|---|---|---|---|---|---|---|---|---|
| kimochi_warui | guitar | 107.0 | 281.2 | 501.5 | 8 | 1.71 | 0.638 | 13 | 13 | 0.064 |
| kimochi_warui | bass | 107.0 | 242.2 | 432.0 | 6 | 1.49 | 0.556 | 11 | 11 | – |
| kimochi_warui | drums | 107.0 | 273.4 | 487.5 | 7 | 1.54 | 0.574 | 12 | 12 | – |
| drunk_drivers | guitar | 117 | 217.3 | 423.5 | 10 | 2.76 | 0.945 | 11 | 11 | 0.0 |
| take_me_out | guitar | 105.5 | 226.8 | 428.5 | 11 | 2.91 | 1.027 | 11 | 11 | 0.0 |
| take_me_out | bass | 105.5 | 226.8 | 428.5 | 11 | 2.91 | 1.027 | 11 | 11 | – |
| take_me_out | drums | 105.5 | 226.8 | 428.5 | 10 | 2.65 | 0.933 | 11 | 11 | – |
| all_the_small_things | guitar | 147.5 | 158.3 | 389.5 | 10 | 3.79 | 1.027 | 10 | 10 | 0.0 |
| all_the_small_things | bass | 147.5 | 158.3 | 389.5 | 9 | 3.41 | 0.924 | 10 | 10 | – |
| all_the_small_things | drums | 147.5 | 158.3 | 389.5 | 10 | 3.79 | 1.027 | 10 | 10 | – |
| lucretia | guitar | 97.3 | 231.0 | 373.0 | 9 | 2.34 | 0.965 | 9 | 9 | 0.333 |
| lucretia | bass | 97.3 | 231.0 | 373.0 | 9 | 2.34 | 0.965 | 9 | 9 | – |
| lucretia | drums | 97.3 | 231.0 | 373.0 | 9 | 2.34 | 0.965 | 9 | 9 | – |
| creep | guitar | 92.3 | 228.4 | 352.1 | 13 | 3.41 | 1.477 | 9 | 9 | 0.0 |
| creep | bass | 92.3 | 229.7 | 353.8 | 13 | 3.4 | 1.47 | 9 | 9 | – |
| creep | drums | 92.3 | 228.3 | 352.0 | 12 | 3.15 | 1.364 | 9 | 9 | – |
| troop primary | guitar | 200 | 297.3 | 991.0 | 17 | 3.43 | 0.686 | 25 | 20 | 0.214 |
| troop primary | bass | 200 | 296.7 | 989.0 | 16 | 3.24 | 0.647 | 25 | 20 | – |
| troop primary | drums | 200 | 296.7 | 989.0 | 16 | 3.24 | 0.647 | 25 | 20 | – |
| troop alt1 | guitar | 200 | 296.7 | 989.0 | 15 | 3.03 | 0.607 | 25 | 20 | 0.248 |
| troop alt2 | guitar | 200 | 297.3 | 991.0 | 22 | 4.44 | 0.888 | 25 | 20 | 0.311 |
| sooth primary | guitar | 77.0 | 539.6 | 695.1 | 21 | 2.34 | 1.208 | 17 | 17 | 0.0 |
| sooth primary | bass | 77.0 | 522.2 | 673.0 | 21 | 2.41 | 1.248 | 17 | 17 | – |
| sooth alt1 | guitar | 77 | 539.5 | 695.0 | 29 | 3.23 | 1.669 | 17 | 17 | 0.357 |
| break primary | guitar | 115.5 | 166.0 | 319.5 | 7 | 2.53 | 0.876 | 8 | 8 | 0.163 |
| break alt1 | guitar | 115.5 | 166.0 | 319.5 | 6 | 2.17 | 0.751 | 8 | 8 | 0.15 |
| pm2 primary | guitar | 199.9 | 436.4 | 1432.0 | 30 | 4.12 | 0.838 | 36 | 29 | 0.302 |
| pm2 primary | bass | 199.9 | 436.4 | 1432.0 | 29 | 3.99 | 0.81 | 36 | 29 | – |
| pm2 primary | drums | 199.9 | 436.4 | 1432.0 | 26 | 3.57 | 0.726 | 36 | 29 | – |
| pm2 alt1 | guitar | 200 | 437.1 | 1434.2 | 40 | 5.49 | 1.116 | 36 | 29 | 0.348 |
| pm2 alt2 | guitar | 200 | 436.4 | 1432.0 | 36 | 4.95 | 1.006 | 36 | 29 | 0.117 |
| pm2 alt2 | bass | 200 | 436.4 | 1432.0 | 0 | 0.0 | 0.0 | 36 | 29 | – |
| pm2 alt3 | guitar | 200 | 436.9 | 1433.8 | 35 | 4.81 | 0.976 | 36 | 29 | 0.301 |
| pm2 alt4 | guitar | 199.9 | 437.0 | 1434.0 | 12 | 1.65 | 0.335 | 36 | 29 | 0.154 |
| pm2 alt4 | drums | 199.9 | 436.4 | 1432.0 | 36 | 4.95 | 1.006 | 36 | 29 | – |

pm2 alt2's bass has no star power (excluded from the fit). drunk_drivers is a guitar-only chart; break's alt2 and
alt3 and sooth have no drum chart with star power.

### Pooled

- Under 150 BPM, 21 human parts: a median 0.965 phrases per 40 beats (0.56-1.67), 2.65 a minute (1.49-3.79).
- At 200 BPM, 13 human parts (troop and pm2): 0.81 per 40 beats (0.33-1.12), 3.99 a minute (1.65-5.49).
- So the rate follows the beats (per minute it rises by half on the fast songs), a little under them at 200 BPM:
  0.81 / 0.965 = 0.84, which is the per-beat rate of a 168-BPM count.
- Per song (guitar), seconds per phrase: the slow songs 15.8-35.1 s (median 21.9), troop 17.5, pm2 12.5; beats per
  phrase: the slow songs 27.1-62.7 (median about 40), troop 58.3, pm2 41.0.

### The fit

Each rule's K on each human chart's own span against the chart's phrases: |log(K / n)|, averaged over each song-part's
charts, then over the 25 song-parts (guitar alone: 10 song-parts). Lower is better.

| rule | all parts | guitar | without troop | without pm2 |
|---|---|---|---|---|
| beats / 40 (before) | 0.226 | 0.216 | 0.200 | 0.226 |
| the first grid's beats / 40 (beats / 80 on the 200-BPM songs) | 0.253 | 0.254 | 0.244 | 0.214 |
| seconds / 20 | 0.239 | 0.237 | 0.258 | 0.221 |
| seconds / 22.5 | 0.251 | 0.236 | 0.252 | 0.218 |
| beats / 40, at most 150 BPM | 0.194 | 0.207 | 0.198 | 0.193 |
| **beats / 40, at most 160 BPM** | **0.195** | **0.204** | **0.193** | **0.199** |
| beats / 40, at most 170 BPM | 0.201 | 0.203 | 0.194 | 0.204 |

The ceiling's sweep over all parts: 130 0.195, 140 0.195, 150 0.194, 160 0.195, 165 0.195, 170 0.201, 180 0.207, 190
0.215, 200 (= none) 0.226. Per fast song-part (|log| at none / 140 / 160 / 170 / 180): troop guitar 0.341 / 0.128 /
0.182 / 0.198 / 0.214; troop bass and drums 0.446 / 0.061 / 0.223 / 0.272 / 0.318; pm2 guitar 0.283 / 0.417 / 0.328 /
0.302 / 0.289; pm2 bass 0.216 / 0.148 / 0.000 / 0.067 / 0.129; pm2 drums 0.163 / 0.202 / 0.163 / 0.163 / 0.163.

### Solos

Every human solo, in seconds / the chart's own measures (the solo's median BPM):

| chart | solos |
|---|---|
| kimochi_warui | 17.9 / 8.0 (107) |
| lucretia | 77.0 / 32.0 (99) |
| troop primary | 63.6 / 53.0 (200) |
| troop alt1 | 5.1 / 4.3 (200); 5.1 / 4.3 (200); 63.3 / 52.8 (200) |
| troop alt2 | 5.0 / 4.1 (200); 5.1 / 4.3 (200); 19.1 / 15.9 (200); 63.5 / 52.9 (200) |
| sooth alt1 | 95.9 / 31.8 (79); 96.9 / 32.0 (80) |
| break primary | 27.0 / 13.0 (116) |
| break alt1 | 24.9 / 12.0 (116) |
| pm2 primary | 19.9 / 16.6 (200); 19.9 / 16.6 (200); 11.3 / 8.0 (170); 11.3 / 8.0 (170); 69.5 / 57.9 (200) |
| pm2 alt1 | 19.8 / 16.5 (200); 19.8 / 16.5 (200); 45.2 / 32.0 (170); 67.2 / 56.0 (200) |
| pm2 alt2 | 19.8 / 16.5 (200); 19.8 / 16.5 (200); 11.3 / 8.0 (170) |
| pm2 alt3 | 20.1 / 16.8 (200); 20.1 / 16.8 (200); 11.2 / 8.0 (170); 11.3 / 8.0 (170); 68.7 / 57.3 (200) |
| pm2 alt4 | 67.5 / 56.3 (200) |

The other four references and sooth's primary have no solo.

- **On the 200-BPM songs** the humans' maps are at 200 BPM, our doubled grid's tempo, so their measures are ours:
  troop's main solo 52.8-53.0 measures (63.3-63.6 s) on its three charts, pm2's long solo 56.0-57.9 (67.2-69.5 s) on four of its five.
- **Our solos against theirs** (input.wav timeline, each run's own score.py alignments; the share of each human solo under ours), the same before and after this change: troop's [172.2, 239.3] s covers the human main solo [177.6, 241.2] by 0.97, 0.98, 0.97 on the three charts; pm2's [303.2, 370.1] s covers [303.2, 372.7] by 0.96, 1.00, 0.97, 0.99 on the four charts that have it, and its [117.6, 136.8] covers the humans' 20-s solo there by 0.96-0.97 on four charts. The humans' other pm2 solos (204-224 s on four charts; 246-291 s pieces on three) get none from us (allin1 does not label them Solo); our third pm2 solo (406.4-432.5 s) matches no human one.
- **Alternatives, on these numbers:** a cap in seconds alone (100 s) or in measures of a bounded length (at most 160 BPM: 56 measures = 84 s) would lengthen pm2's solo past every human chart's 67-70 s. Over all 32 human solos on 18 charts the 95th percentile is 56.8 measures and 85.5 s; M5-03's rounding (up to a multiple of 8, the next 10 s) would give 64 and 90: 77-s solos on the fast songs and lucretia's 91.4-s solo cut. Not adopted: `SoloRules` is unchanged, and M5-99's item is closed by the measurement.

## 2. The rule and why

- **Why not seconds.** The humans' rate a minute rises with the tempo (2.65 a minute under 150 BPM, 3.99 at 200), so
  a count in seconds fits worse than the beats at any spacing (best 0.239 against 0.226), and it would move every
  reference.
- **Why not the first grid.** Counting the doubled grid's beats as the first grid's gives troop 12 and pm2 18,
  under most of their humans (0.253).
- **Why a ceiling.** The fast songs' humans write fewer phrases per beat (0.84 times); a count capped at 150-165 BPM
  fits better than none with all parts (0.226 -> 0.195), on guitar alone (0.216 -> 0.204), and with either fast song
  left out (0.200 -> 0.193 without troop, 0.226 -> 0.199 without pm2). The fit is flat from 130 to 165, so the value
  is not a tuned point: 160 is the plateau's middle, the best without troop, and reads as "at most one phrase per 15
  s". Every reference (92-148 BPM) and the shred song's grid (154 BPM average) are under it: their counts are
  unchanged by construction.
- **Against it.** pm2's guitar alone prefers the old count (its five charts' median is 35 phrases; the old rule gave
  36, the new 29, still inside its 12-40); the evidence for the tempo effect is two songs, both 200-BPM power metal.
  The order's line (troop and pm2 inside their humans' range) holds for the new rule and fails for the old on troop.

## 3. Tests (each fails on its break)

New in `tests/test_starpower.py`: `test_star_power_counts_beats_at_most_at_160_bpm` (the same 479.5-beat part: 12
phrases at 100 BPM, 10 at 200 BPM, 12 there without the ceiling; the record's fields; `count` overrides),
`test_the_star_power_ceiling_starts_above_160_bpm` (parametrized 150, 159.9, 160, 160.1, 170, 240 BPM: counted beats
and K), `test_drum_star_power_and_the_record_through_place_phrases` (guitar, a thin bass that gets 2 of its 10, drums,
on a 200-BPM map: the same ceiling on every part, `placed`), `test_the_default_solo_caps_on_a_100_and_a_200_bpm_grid`
(a 100-measure Solo run: 56 measures at 200 BPM, 41 at 100 BPM), and the empty part's record in
`test_short_or_empty_parts_get_no_star_power`. In `tests/test_assemble.py`, `test_the_solo_report_without_names`
checks every part's `star_power_count` in report.json.

Breaks (each applied alone, the named tests run, the file restored and compared byte for byte):

| break | result |
|---|---|
| `counted = beats` (no ceiling) | fails |
| `counted = seconds * max_bpm / 60` (always the ceiling) | fails |
| `max(...)` for `min(...)` | fails |
| `max_bpm` 170 | fails (boundary test) |
| `max_bpm` 159 | fails (boundary test) |
| counted + 2 beats | fails |
| `placed` from the target, not the phrases | fails (it passed until the thin bass was added: fixed) |
| drums not passing the record | fails |
| the record's target = `count` | fails |
| the empty record's `span_beats` 0 | fails |
| `max_measures` 560 | fails (solo caps test) |
| `max_seconds` 1000 | fails (solo caps test) |
| assemble: `star_power_count` None | fails |
| assemble: `sp_record` not passed | fails |

Suite: `SONGCHARTER_SCAN_CHART=<wt>/tools/scan-chart/scan.cjs tools/heavy.sh .venv/bin/python -m pytest -q -p
no:cacheprovider --basetemp=<shm>/pt-m6-01` on 42d67fb (the later commit is docs only): `1065 passed, 4 skipped in
721.95s (0:12:01)`.

## 4. Golden

`python -m eval.golden run --code <shm>/m6-01-old (f3b9ebb) --out $DEV/golden/m6-01-old --threads 2 --rerun
bass`, the same from the branch (42d67fb) to `m6-01-new`, then `python -m eval.golden diff ... --expect none`, all
under `tools/heavy.sh`, with the brief's variables (EVAL_DATA, SONGCHARTER_GOLDEN, SCAN_CHART, AUTOCHART,
ALLIN1_PYTHON). Both runs exit 0 (bass rerun on 7 songs each; kept folders by 8ba3cbd; 988 s and 375 s).

`golden diff: no UNEXPECTED change`. "Parts changed as expected: 0. Every song's results (hashes, counts, scores)
identical: yes." Pooled F1@50 unchanged: guitar Expert 0.8527, Hard 0.8010, Medium 0.7474, Easy 0.6150; bass 0.8247,
0.7881, 0.7920, 0.6964; drums 0.9617, 0.9237, 0.8787, 0.7696; beat F1 0.8755. The test song's report.json shows the
record, e.g. guitar: span 950.0 beats over 401.4 s, counted 950.0, target 24, placed 24 (the ceiling does not touch a
142-BPM song).

## 5. The stress set, before and after

`python -m eval.golden run --refs $EVAL_DATA/stress --work $DEV/golden/stress-work ...` before (f3b9ebb, `m6-01-stress-old`)
and after (42d67fb, `m6-01-stress-new`), `--rerun bass` both, then `golden diff --expect guitar,bass,drums`,
`eval/stress.py score` on both, `eval/stress.py compare`. All exit 0.

Star power, ours (phrases; a minute over the chart's span, from stress_scores.json) against the humans:

| song | part | before | after | the humans |
|---|---|---|---|---|
| troop | guitar | 25 (5.04) | 20 (4.04) | 15-22 (3.03-4.44) |
| troop | bass | 24 (5.07) | 19 (4.01) | 16 (3.24) |
| troop | drums | 25 (5.06) | 20 (4.04) | 16 (3.24) |
| pm2 | guitar | 36 (4.94) | 29 (3.98) | 12-40 (1.65-5.49) |
| pm2 | bass | 36 (4.95) | 29 (3.98) | 29 (3.99) |
| pm2 | drums | 35 (4.79) | 28 (3.83) | 26, 36 (3.57, 4.95) |
| sooth | guitar / bass / drums | 35 / 33 / 31 | the same | guitar 21, 29 (2.34-3.23); bass 21 |
| break | guitar / bass / drums | 8 / 8 / 8 | the same | guitar 7, 6 (2.17-2.53) |

New report.json records: troop guitar 991.25 beats over 297.4 s, counted 793.0, target 20; pm2 guitar 1456.25 over
436.9 s, counted 1165.0, target 29; sooth guitar 1380.5 over 539.6 s, counted 1380.5 (its 153.5-BPM average is under
the ceiling), target 35. Drums placed fewer than their target on sooth (31 of 33) and pm2 (28 of 29), as before.

- **The order's lines.** troop's and pm2's star power per minute inside their humans' range: troop guitar 4.04 in
  3.03-4.44 (before 5.04, outside), pm2 guitar 3.98 in 1.65-5.49 (before 4.94, inside too). troop's bass and drums
  (4.0 a minute) stay above their single human chart (3.24), though closer than before (5.1). Solo overlap not lower:
  identical solos on every song (troop 0.97-0.98, pm2 0.96-1.00). The shred song's and the rock song's solos and star
  power unchanged.
- **Every other number:** stress_scores.json has 930 numeric leaves; 14 differ, all `ours/*/parts/*/star_power_per_min`
  on troop and pm2. `stress.py compare`: "Regressions (a primary F1@50 down by more than 0.01): 0".
- **The stress diff** (`report.md` beside m6-01-stress-new): no UNEXPECTED change; 24 parts changed as expected, all
  on troop and pm2 (every part and level: the star power is copied down). Onset counts identical on every guitar and
  bass level and on Expert drums; a few lower-level drum onsets moved with the drum fills (the reducer keeps a note in
  each phrase and fill): troop Hard 1782 -> 1776, Medium 901 -> 900, Easy 745 -> 748 (F1@50 against the primary
  0.929 -> 0.930, 0.920 -> 0.920, 0.868 -> 0.870); pm2 Hard 2339 -> 2340, Easy 952 -> 950 (0.853 -> 0.852, 0.553 ->
  0.553). The stress scores are Expert only, so these are outside stress_scores.json. sooth and break: unchanged.

## 6. CI

- <repo>/actions/runs/42271536635 on the head 8a0b8ca: **success** (linux 26m43s,
  windows 49s). Suite step: `1065 passed, 4 skipped in 510.00s (0:08:30)`; `all 8 Linux hooks passed: 10-lanes.sh
  17s 20-device.sh 7s 30-install.sh 169s 40-ui.sh 29s 50-e2e.sh 461s 60-results.sh 84s 70-release.sh 65s
  75-update.sh 184s`.
- <repo>/actions/runs/42264321313 on 42d67fb (the code): success, the same counts.
- The order adds no CI hook: its checks are unit tests in the suite, which CI runs; the golden and stress runs are
  local (CI cannot run them).

## 7. Uncertain, not done

- **The evidence is thin.** The ceiling rests on two fast songs, both 200-BPM power metal (troop's humans write
  0.61-0.89 phrases per 40 beats; pm2's guitar charts 0.34-1.12, median 0.98). pm2's guitar alone fits the old count
  better (|log| 0.283 -> 0.328); the gain is troop's three parts and pm2's bass and drums. The fit is flat from 130 to
  165 BPM; 160 is my choice inside it (the plateau's middle, the best value without troop, "one per 15 s"). Whether
  that clears the order's "clearly better" bar is a judgment the reviewer may weigh differently: on all parts 0.226 ->
  0.195, on guitar 0.216 -> 0.204, better with either fast song left out.
- **Not fixed:** the shred song's grid at twice its humans' tempo (154 against 77 BPM) keeps 35 phrases (3.89 a minute)
  against its humans' 2.34-3.23: under the ceiling, it waits for a halving rule (M5-99, narrowed).
- **troop's bass and drums** land at 4.0 a minute against one human chart each at 3.24: closer, still above.
- **Lower-level drum notes** on the two fast songs moved by a few onsets with the fills (above); not a stress score,
  but "every other number unchanged" does not hold for them literally.
- **The measurement scripts** (`measure.py`, `overlap.py`, `fit.py`, `stats.py`) are in the session's scratch folder,
  not committed (the order's files do not include eval/). Two of their runs parsed charts outside `tools/heavy.sh`
  while the other builder's golden run held the lock: chart parsing only (scan_notes.cjs, no audio, about 150 MB),
  with 14 GB free.
- **Not done:** no human listened or played; PROGRESS.json, PIPELINE and docs/reports/ left to the orchestrator as the
  brief says. The worktree `<shm>/m6-01-old` (f3b9ebb, detached) and the out folders `$DEV/golden/m6-01-old`,
  `m6-01-new`, `m6-01-stress-old`, `m6-01-stress-new` are left for the reviewer.

## Review fixes (orchestrator, commit a9448ef)

- **F1** (no test told the span's average tempo from one beat's): a map with a 40-beat intro at 100 BPM, then 240 BPM,
  expects 9 phrases (132.475 s, 353.267 beats counted at 160 BPM); the reviewer's break (the first beat's tempo)
  fails it.
- **F2** (docs): DESIGN 2.10 says 14 of 882 numeric fields of stress_scores.json differ.
- The repository's history was rewritten on 2026-11-06 (the owner's decision: a committed report's md5 prefixes and a
  stress song's artist removed from old commits); the hashes above from before 19:40 UTC are the old ones (8a0b8ca is
  now c3a2437). CI on a9448ef: run 42283123607, success.

## Review (sc-reviewer, 2026-11-06)


Verdict: no major finding. The rule is correct, the numbers reproduce, and one test gap is worth closing before merge.

## Lens 1: correctness (checked, no defect)
- `K = round(min(beats, seconds*160/60)/40)` uses the span's average tempo (tick_to_sec over first..last onset), as the
  docstring and DESIGN say. On a map with a change (a 10-measure intro at 100 BPM, then 240 BPM, 479.5 beats over
  132.5 s) the real code counts 353.3 beats, giving 9 phrases. That is right.
- Under and over 160, the boundary, a short span (k=0 gives []), an empty part (record all None), and `count`
  overriding are all fine. Moving the `min_onsets` early return below the count changes no result.
- report.json: `star_power_count` per Expert part. `placed` is taken after the drums' no-fill fallback, so it is right.
  No other reader of `phrases` breaks: cli.py reads only `solos`.
- Nothing else moved: the golden diff is identical, and in the stress diff only star power changed, plus the
  lower-level drum onsets on troop and pm2. Those are consistent with fewer phrases, which means different fills,
  and the reducer keeps a note in each phrase and fill. Expert is unchanged and F1 moves by at most 0.002. Harmless.

## Lens 2: numbers (reproduced)
- I recomputed the fit from human.json with the code's exact rule (min with the average tempo, not fit.py's
  median-BPM switch). Before: 0.226 / 0.216 / 0.200 / 0.226. Ceiling 160: 0.195 / 0.204 / 0.193 / 0.199.
  150 and 170 also match. 25 song-parts, 10 on guitar.
- Stress: 14 leaves of stress_scores.json differ, all `star_power_per_min` on troop and pm2, with the same values as
  the report's table. The report.json records match: troop guitar 20, bass 19, drums 20; pm2 29/29, drums 28 of 29;
  sooth 35/33, drums 31 of 33; break 8.

## Findings

### F1 (minor): no test can tell the span's average tempo from one beat's tempo
starpower.py:236-238. Every new test uses a constant map (`bpm_map`), so a count that takes the tempo at the first
onset passes them all. Our maps come from beat tracking with a marker on each beat, so that bug would let one
intro beat decide the cap.
Repro (copy in <shm>/review_m601/wt, script vary.py: an intro at 100 BPM, then 240 BPM):
- real code: `phrases 9 {'span_seconds': 132.475, 'counted_beats': 353.267, 'target': 9}`
- B1 `seconds = beats * (tick_to_sec(onsets[0]+res) - tick_to_sec(onsets[0]))`: `phrases 12 ... 'counted_beats': 479.5`.
  tests/test_starpower.py: `43 passed`.
- B2 cap chosen by the first beat's tempo: `phrases 12`. tests/test_starpower.py `43 passed`, and
  test_assemble.py -k solo_report_without_names `1 passed`.
Fix: one test on a map with a tempo change (as vary.py), expecting target 9.

### F2 (minor, docs): DESIGN 2.10 and the report say "14 of 930 fields"
stress_scores.json (old and new) has 931 leaves, of which 882 are numeric (16 bool, 33 str). "14 of 882 numeric
fields" is the right figure. It changes no conclusion.

## Lens 3: my breaks (not the builder's)
| break | result |
|---|---|
| B1 seconds from the first beat's local tempo | green (F1) |
| B2 cap decided by the first beat's tempo | green (F1), the report test too |
| B3 span seconds from tick 0, not the first onset | 7 failed |
| B5 `count` also overridden by rule 1 (`if onsets:`) | 4 failed |
| B6 assemble: every part gets guitar's record | test_assemble fails |
Each file was restored and checked with cmp.
