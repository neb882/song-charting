# M6-05: a tempo change under a doubled grid, from allin1's beats (builder's report)

Branch `m6-05-doubled-tempo-changes`, worktree `<wt>/m6-05`, from main cb48d81. Numbers only: no titles, charters,
md5s or lyrics; the stress songs by id.

## Verdict

The rule is kept. It meets every line of the order: pm2's beat F1 0.598 -> 0.987 (the measurer predicted 0.985),
its Expert F1@50 on guitar, bass and drums not lower, troop, sooth and break byte-identical (every track hash), and
the seven references identical (the golden diff `--expect none` exit 0, against main). One thing the order did not ask about needs the orchestrator's eye: **pm2's Easy and Medium levels
fall** (Easy guitar 0.515 -> 0.113, Easy bass 0.559 -> 0.093, drums Medium 0.579 -> 0.458, Easy 0.553 -> 0.378),
because its bar phase, a coin flip with a kick on every beat, landed one beat off the primary's measure lines where
it was two beats off before (details below). The stress check reads Expert only and passes; the friend plays
Expert. The downbeats on fast songs are M6-03's.

## Commits

- f3d4c03 The doubled grid starts from allin1's beats when its straight line misses a tempo change (M6-05)
- fcf5150 check_inputs reads allin1's beats; the octave pass trims them itself (behaviour-neutral: the trim moved
  into `allin1_start`'s count)
- ca79642 DESIGN 2.3 and M5-99: the rule and its measurement
- d00fe48 Merge origin/main (8a93698: M6-01's star power and M6-02's bass slots; one conflict, M5-99, resolved by
  keeping main's M6-02 bullets and this order's item)
- d32d86c DESIGN 2.3: the references' line of the table (golden against main, identical)

## What changed

- `songcharter/assemble.py`
  - `allin1_start(allin1, grid_bpm, duration)`: allin1's beats as the doubled grid's start: a midpoint added between
    each two, minus `ONSET_TO_BEAT_MS` (onset times, beat_grid's start= convention). None, with why, without beats,
    with under 8 inside the audio, or when the doubled median tempo is more than half an octave from the line's.
  - `_octave_pass(..., allin1=None, duration=inf)`: after the second pass, when its `stats["tempo_check"]` is not
    empty and `allin1_start` gives a start, `second_pass(bpm, range, start=...)` runs again and that grid is the
    doubled grid (an InputError from it keeps the line, with why). `octave_stats["second_start"]` = {grid: "line" or
    "allin1", why, and when the check warned: tempo_check (the line's windows), allin1 (count, doubled, bpm, why),
    line (the replaced grid's record)}. When the allin1 grid is kept, a warning: "the doubled grid follows allin1's
    beats: its straight line missed a tempo change at A-B s: check sync there". The guard's ratio is the used grid's
    share (pm2 0.726/0.744 = 0.976; the line's was 0.943).
  - `assemble()`: the second-pass lambda takes `start=`; allin1's beats come from the sections file
    (`_read_allin1_beats`: None for no sections, "from:", or a file without beats); `check_inputs` reads them too,
    so a malformed `beats` is an InputError before any audio work. Module docstring step 2.
- `songcharter/sections.py`: `read_allin1_beats(path)`: the `beats` list of an allin1 result (sorted, repeats
  dropped), None when absent, null or empty; not a list of finite times is an InputError.
- No change to `beatgrid.py` (its `start=` was enough), `engines/sections.py` or `pipeline.py`.
- Tests (made-up data only): `tests/test_sections.py::test_read_allin1_beats`; in `tests/test_assemble.py`:
  `test_allin1_start_...`, `test_the_octave_pass_starts_the_doubled_grid_from_allin1_...` (fake grids: used; no
  beats, another level, a failing pass, no warning: the line), `test_a_doubled_grid_follows_a_tempo_change_from_
  allin1s_beats` (a made-up 198 BPM song with 52 beats at 170 BPM at 45 s, allin1-like half-rate beats in 10 ms
  frames: stretch F1 > 0.95 with them, < 0.6 without; report and warnings), `test_allin1s_beats_change_nothing_
  when_the_doubled_grid_misses_no_tempo_change` (the steady fast song: notes.chart byte-identical with and
  without beats), and `test_check_inputs` extended. `fast_drums` takes beats (same audio as before by default).
- Docs: DESIGN 2.3 step 7 (the rule, the evidence, the lower levels, the halving side note), M5-99 (the item
  narrowed; the shred song's allin1 0.967 against our 0.643 under the halving paragraph).

## The sections stage runs before assemble on every path (checked)

`pipeline._engine_stages` runs the sections stage unconditionally (after drums and bass, before lyrics, guitar and
assemble; the plan's stage order says the same). The page runs `songcharter chart` as a subprocess
(`ui/jobs.chart_command`), the same path. A cached run (`engines.sections` cache hit, or a `--work` folder) returns
the same `segments.json`; allin1's has carried `beats` since the repository's first commit. A sections stage that
fails without the librosa fallback raises ToolError and the chart stops before assemble. The librosa fallback writes
no `beats`: nothing changes there. `songcharter assemble` with a hand-made config: whatever its sections file holds.

## Decisions the order did not make (for the reviewer)

1. **A level check** (`allin1_start`): the doubled allin1 beats are used only within half an octave of the line's
   tempo, so beats already at the doubled level are not doubled again. Not measured; it fires on no song here
   (pm2: 200.0 against 199.99). Without it, allin1 at the humans' rate would give a 400 BPM start.
2. **The guard reads the used grid's share.** The octave decision's ratio is computed on the grid the second pass
   returns, so the allin1 start can change whether a doubling is kept. On pm2 it only rises (0.943 -> 0.976). On
   the made-up test song it decides it: the line's share is too thin to keep the doubling (0.52), the allin1
   grid's is not (1.08), so the end-to-end test forces grid_octave 2 on both runs to compare the starts.
3. **A warning** when the allin1 grid is kept ("check sync there"), since the entry into a stretch stays weaker.

## Checks

- `tools/heavy.sh .venv/bin/python -m pytest -q -p no:cacheprovider --basetemp=<shm>/pt-m6-05` with
  SONGCHARTER_SCAN_CHART set: on fcf5150 "1061 passed, 4 skipped in 740.53s (0:12:20)"; on the merged head d00fe48
  "1072 passed, 4 skipped in 742.71s (0:12:22)". The new tests take about 12 s (the stretch song's two builds)
  and 6 s (the steady song's two).

### Tests of the tests (18 breaks, in a separate copy of the branch, so the golden runs were not touched)

All 18 caught (`<scratchpad>/m6-05/mutate.py`, `mutate.log`): the tempo check ignored; the warning path forced (a
crash on an empty check); no midpoints; the shift reversed; no shift; no level check; a one-octave level check; no
count check; the count ignoring the duration; the lambda dropping start; assemble not reading the beats; no
InputError catch; the allin1 grid not kept; no warning; check_inputs skipping the beats; the reader without
unique/sort, taking an empty list as beats, without the finite check.

### Stress set (cb48d81 at `<shm>/golden-old-m6-05` against the branch; `--rerun bass` both; 1 CPU take)

`python -m eval.golden run --refs $EVAL_DATA/stress --work $G/stress-work --out $G/m6-05-stress-{new,old}
--threads 2 --rerun bass` (exit 0 both), `eval/stress.py score` both, `eval/stress.py compare $G/m6-05-stress-old
$G/m6-05-stress-new`: exit 0, "**Regressions (a primary F1@50 down by more than 0.01): 0**", and "pm2 | beat lines |
primary | beat F1 0.598 -> 0.987; downbeat F1 0.014 -> 0.000".

- troop, sooth, break: every part and level's scan-chart track hash identical; beat F1 1.000, 0.644, 0.994 both.
  troop's doubled grid: `second_start` {grid: line, why: the tempo check finds no missed tempo change}; sooth and
  break: octave 1, no second pass.
- pm2: `second_start.grid` allin1, "the straight line misses a tempo change (10 tempo-check windows, 235-300 s): the
  grid starts from allin1's beats doubled: 1431 beats at 200.0 BPM"; the final grid's tempo check empty; 716 allin1
  beats. Tempo map 153 -> 150 markers, 194.9-204.7 -> 140.8-214.8 BPM (the dip is at the stretch's entry).

pm2 per part and level, F1@50 against the primary (the summaries):

| part | Expert | Hard | Medium | Easy |
|---|---|---|---|---|
| guitar | 0.803 -> 0.807 | 0.589 -> 0.667 | 0.524 -> 0.783 | 0.515 -> **0.113** |
| bass | 0.777 -> 0.785 | 0.585 -> 0.694 | 0.568 -> 0.874 | 0.559 -> **0.093** |
| drums | 0.973 -> 0.973 | 0.853 -> 0.859 | 0.579 -> **0.458** | 0.553 -> **0.378** |

Expert from the compare table: guitar F1@100 0.819 -> 0.817, timing 12.5 -> 14.2 ms, lowest 30 s 0.687 -> 0.685;
bass 0.796 -> 0.799 at 100 ms, lowest 30 s 0.526 -> 0.545; drums unchanged to 0.001.

pm2 per 10-s window (the measurer's scorer, final chart only: `<scratchpad>/m6-05/windows2.py`; 70 ms; the windows
that changed): global beat F1 0.598 -> 0.987; windows under 0.9 22 -> 4 of 45; median window error 11.5 -> 7.9 ms.

| t (s) | before F1 | err ms | after F1 | err ms |
|---|---|---|---|---|
| 0 | 0.71 | 3.4 | 0.69 | 3.9 |
| 230 | 1.01 | 9.1 | 0.85 | 12.4 |
| 240 | 0.74 | 19.1 | 0.55 | 43.6 |
| 250-280 | 0.39-0.46 | 71-77 | 0.98-1.02 | 9-12 |
| 290 | 0.06 | 141.8 | 0.97 | 2.5 |
| 300-430 | 0.00 | 147-149 | 1.00 | 3-11 |
| 440 | 0.00 | 140.9 | 0.31 | 1.1 |

troop per window: identical (beat F1 1.000; 2 windows under 0.9 both, the lead-in and the end artefacts).

**Why pm2's lower levels fall** (`<scratchpad>/m6-05/bars.py`: our measure lines moved by k of our beats against
the primary's measure lines, downbeat F1 at 70 ms): before, k = 2 gives 1.0 over 5-235 s and nothing fits after
the slip (0 for every k at 300-442 s); after, k = 1 gives 1.0 over both 5-235 s and 300-442 s. So the beats are now
right all song and the bar phase is one beat off all song, where it was two beats off for the first half. reduce.py
ranks notes by measure position: two beats off puts Easy's half-measure lines on the primary's measure lines, one
beat off puts them on its beats 2 and 4. `bar_phase`'s margin 0.125 -> 0.014 (a kick on every beat; both under
0.15, flagged). Not tuned: it is M6-03's (downbeats on fast songs). allin1's own downbeats (in the same
segments.json) are a candidate there; not measured.

### Golden (the references)

- **First pair** (cb48d81 against fcf5150/ca79642, `--rerun bass`; out `$G/m6-05-old`, `$G/m6-05-new`): both runs
  exit 0; `golden diff --expect none` exit 1 on one flag only: "the new run's sections answered from the kept
  folders (made by 8ba3cbdf590c), but sections's files differ in its code ...: pass --rerun sections to both runs"
  (`sections.py` gained `read_allin1_beats`). Its report: "Every song's results (hashes, counts, scores) identical:
  yes." Every reference: octave 1, no `second_start`, an empty tempo check, so the warning fires on none.
- **Second pair, against main after the merge** (`<shm>/golden-old-m6-05` at 8a93698 against d00fe48,
  `--rerun bass,sections`; out `$G/m6-05-old2`, `$G/m6-05-new2`): `python -m eval.golden run ... --threads 2
  --rerun bass,sections` exit 0 both (899 s, 889 s); `python -m eval.golden diff $G/m6-05-old2 $G/m6-05-new2
  --expect none`: "golden diff: no UNEXPECTED change", exit 0; report.md: "Parts changed as expected: 0. Every
  song's results (hashes, counts, scores) identical: yes."; engines that ran: bass and sections on 7 songs each.

### CI

- Run 42288505005 on fcf5150 (before the merge): success.
- Run 42294076677 on d00fe48 (the merged head; `gh workflow run ci --ref m6-05-doubled-tempo-changes`):
  <repo>/actions/runs/42294076677, conclusion success, head
  d00fe48555d6f4753e0c11354f005a7abc5416ee; jobs linux and windows success; the linux Suite step "1072 passed, 4
  skipped in 495.28s", the same count as locally. No CI hook was added (the order's checks are tests in the
  suite).

### Privacy and the hard rules

`EVAL_DATA=$DEV/eval python3 -I eval/privacy_check.py`: "265 files, 14 md5s and 37 names checked, 0 found" (exit 0)
before each push. `git diff origin/main...HEAD` and the commit messages scanned for lyrics, audio, model names
(other than the trailers) and personal details: none (no paths, names or versions; tests use made-up data).

## Not done, uncertain

- The made-up song cannot mirror pm2: on clean drums the first pass's tracker follows the stretch at the first
  level, so the doubled line is hinted at a tilted tempo (190 BPM) and off everywhere; the end-to-end test
  compares the two starts under grid_octave 2.
- One positive song (pm2). The rule is gated by the tempo check, which is empty on troop and on every song at
  octave 1, so the other songs are untouched by construction, and measured so.
- `drift_ms` in report.json is meaningless on a grid with an external start (pm2: p50 1311 ms): pre-existing for
  start=, not changed.
- The stress runs compare cb48d81 (the brief's before) with the branch before the merge (f3d4c03/fcf5150, the
  same charting code). Main gained M6-01's and M6-02's code during the build; the merged head's stress numbers
  were not rerun (their own orders measured them; neither touches the grid). The golden pair was run again against
  main itself (8a93698) after the merge.
- The stress runs used the kept sections output while `sections.py` differs from the kept commit (golden's
  engine-files check would flag it, as it did on the first golden pair). Not rerun there: the sections engine
  (`engines/sections.py`) imports only `Segment` and `read_allin1` from `sections.py`, both unchanged; the file only
  gained lines. The golden pair was rerun with `--rerun bass,sections` for a clean verdict.

## The orchestrator's decisions and review fixes (commits 8751c91, dbd8a8e)

- **pm2's Easy and Medium, lower, accepted for this order.** The review confirmed it is the bar phase, from our own
  charts over 5-230 s where both grids are right: the new measure lines sit exactly one beat after the old ones;
  Expert notes 99.6 % and Medium 99.3 % at the same times, Easy 13.8 % at the same times and 83.3 % one beat away
  (293 to 282 notes). The notes follow the measure lines; the grid does not change the lower levels by itself. The
  bar phase was wrong before too (two beats off the humans' measures), and `bar_phase` picks one phase for the whole
  song from the kick (pm2's margin 0.125 -> 0.014): M6-03 (downbeats on fast songs) is the order for it, next.
- **Decision 2, kept with a note.** The octave guard reads the grid the second pass returns, so a start from allin1
  can keep a doubling the line would have dropped (a song at the first level with a tempo change and dense notes);
  no measured song shows it: DESIGN 2.3 and M5-99 say so.
- **R1** (a test gap): the rule needing two tempo-check windows, or firing on the first grid's check, passed every
  test; the octave-pass test now has a one-window case and a first-grid-only case, each failing on its mutant.
- **R2** (a test gap): `_read_allin1_beats` on sections "from:<part>" (an imported chart's) returns None; a test
  holds it (the guard dropped, it raised FileNotFoundError).
- **R3**: main (M6-04) merged into the branch (dbd8a8e); the M5-99 conflict was two neighbouring items, both kept.
- DESIGN 2.3: beats already at the doubled level are not used at all (decision 1's wording).
- CI on dbd8a8e: green (run 42308071775; the linux suite and hooks, Windows).

## Review (sc-reviewer, 2026-11-06; head d32d86c, against 8a93698)

No major finding. The code does what the order and DESIGN 2.3 say; the numbers check out; three minor findings.

## Findings

**R1 (minor, test gap): the rule's firing condition is not pinned.** `songcharter/assemble.py:1524` `if not missed:`.
- Break `if len(missed) < 2:` (fires only on 2+ tempo-check windows): `tests/test_assemble.py tests/test_sections.py
  tests/test_pipeline.py` -> "144 passed in 495.03s". A missed change that one 20-s window catches would keep the
  line. (The unit test uses 2 windows, the stretch song many.)
- Break `missed = first's tempo_check or second's` (also fires on the first grid's check): the 36 covering tests
  (`-k "allin1 or octave or check_inputs or tempo or sections or from"`) -> "36 passed".
- Fix: a one-window case, and a case where only the first grid's check is set, in
  `test_the_octave_pass_starts_the_doubled_grid_from_allin1_...`.

**R2 (minor, test gap): the `from:` guard in `_read_allin1_beats` (assemble.py:476) is untested.** Dropping
`or cfg.sections.startswith("from:")`: the 36 covering tests pass ("36 passed"). With the break,
`_read_allin1_beats(cfg)` for `sections: "from:guitar"` -> `FileNotFoundError [Errno 2] No such file or directory:
'from:guitar'` (original: None), uncaught: `songcharter assemble` with an imported chart's sections would crash with
exit 3. `"from:"` appears in the tests only in two `parse_config` checks; no assemble run uses it (the pipeline never
writes `from:`, so only a hand-written config is exposed). Fix: one `_read_allin1_beats` assertion for `from:x`.

**R3 (minor): the merge with M6-04 (origin/m6-04-fast-run-chords, 2ac96ae) conflicts.**
`git merge-tree --write-tree d32d86c origin/m6-04-fast-run-chords` -> exit 1, "CONFLICT (content): Merge conflict in
docs/work-orders/M5-99-later.md"; `assemble.py`, `tests/test_assemble.py` and `DESIGN.md` auto-merge. Adjacent
bullets: keep this branch's "A tempo change under a doubled grid" and M6-04's "The guitar's chord share".

## Tests of the tests (my breaks, not the builder's 18)

| break | result |
|---|---|
| fire only on 2+ windows | survives (R1) |
| tempo check from either grid | survives (R1) |
| `from:` guard dropped | survives (R2) |
| shift halved (`/2000`) | caught (`test_allin1_start_...`) |

(Level bound 0.5 -> 0.95 not run: the unit test's 141 and 283 BPM cases pin it.)

## The lenses

1. Correctness: the condition, the doubling, the shift (onset = allin1 beat + 22 ms, beat_grid's `start=`
   convention), the count (same [0, duration] filter as beat_grid), the record and the warning hold. Every
   no-beats path gives None (the librosa fallback writes only `segments`; allin1's writer passes `beats`). A
   malformed `beats` is an InputError in `check_inputs`. `np.unique` keeps the start strictly increasing, so
   beat_grid's ValueError cannot fire. Decision 1: beats already at the doubled level are dropped (the line stays),
   not used undoubled. DESIGN's "so that beats already at the doubled level are not doubled again" is true, but
   reads as if they were used. Decision 2: yes, by construction. The guard then reads a grid that follows the
   change, where the line's share was low because it could not follow it, so a first-level song with a tempo
   change and dense notes could keep a wrong doubling the line would have lost. The builder's own made-up song
   shows the flip (0.52 -> 1.08). It is not seen on any measured song (references octave 1, troop's check empty).
   Not reproduced here as a wrong case.
2. The numbers: the compare log reads "pm2 ... beat F1 0.598 -> 0.987" and "Regressions ...: 0". troop, sooth and
   break notes.chart are byte-identical (`cmp`). **The lower levels' fall is the bar phase, confirmed** from our
   own charts only (`/dev/shm` script, pad-corrected, 5-230 s where both grids are right): new bar lines on old
   beats 1.000, on old bar lines +1 beat 1.000, +0/2/3 beats 0.000. Expert notes 99.6 % and Medium 99.3 % at the
   same times; Easy 13.8 % at the same times but 83.3 % one beat away, with 293 -> 282 notes. So the new grid does
   not change the lower levels by itself; the notes move with the measure lines. A song whose bar phase was right
   can lose it this way: `bar_phase` is one song-wide argmax over the kick scores, and the rule changes the beats
   of one stretch. pm2's margin fell 0.125 -> 0.014 although its first-half beats are identical. Any song where the
   rule fires with an uncertain (flagged) margin can flip either way.
3. Determinism: no new randomness. allin1's beats only seed beat_grid, which refines them onto the drums.
