# M5-09: the stress set (report)

Builder's report for `docs/work-orders/M5-09-stress-eval.md`, built on branch `m5-09-stress-eval` from `main` at
fbd9751 (after M4-11's merge), with the orchestrator's changes to the order (no titles, artists, charters or md5s
committed; the primary by the most parts; the fresh-machine fix in `build_refs.sh`; the baseline on `main` at
fbd9751; the reference set's golden run diffed against the machine's own base).

## Commits

- e74146d eval: the stress set (stress.json, build_refs.sh --set stress, stress.py) and the scorer's feel measures
- c9e7e00 tests: the stress set's build, the scorer's feel measures, stress.py and the lyrics timing check
- 30835b4 eval: the stress set's baseline (main at fbd9751), its README section and DESIGN 3.3 and 3.6
- 7276029 score.py: ffmpeg from $FFMPEG, PATH, then the imageio-ffmpeg wheel
- 54b10d3 stress.py lyrics --run: the temporary folder beside the kept folders, on their file system
- 857fff3 DESIGN 2.15: the lyrics check on the power-metal stress song

## What changed

- `eval/stress.json` (new, committed): the three songs by generic id and slot only (`troop` "a 198 BPM power-metal
  song", 3 charts; `sooth` "a 9-minute shred instrumental", 2; `break` "an ordinary rock song", 4), with what each
  primary holds. No md5, title, artist or charter.
- `$EVAL_DATA/stress.local.json` (written on the dev machine from the md5 list and the packages' song.ini by a script
  that printed nothing of them; not committed): refs.json's shape plus `alts`. `eval/README.md` names it as "not
  committed, the owner keeps the list" (`STRESS_LOCAL` overrides the path).
- `eval/stress.py` (new): `songs` (the merged set; refuses a song missing from the list, a chart count that differs,
  a malformed or repeated md5), `score`, `compare`, `align`, `lyrics`, `baseline` (the module docstring and the README
  section say what each does).
- `eval/build_refs.sh`: `--set stress` (primary into `$EVAL_DATA/stress/<id>/`, others into `<id>/alt/<md5>/`, then
  `stress/songs.json`; the unpacked packages deleted once built). **The fresh-machine bug, folded in:** the list is now
  read on fd 3, every helper call has `</dev/null`, and `build_ref.py` runs every ffmpeg with `-nostdin` and
  `stdin=DEVNULL`, so no helper can eat the list's lines (the cause: an ffmpeg reading the loop's piped stdin).
- `eval/refs/build_ref.py`: an unopenable or empty stem is skipped and named in `build_meta.json`'s `stems_skipped`
  (file, bytes, why); no usable audio is an error. `offset_check.py` no longer fails on a chart with no guitar or
  drums part; `make_songs_json.py` takes the list as an argument, keeps any instrument (the rock song's packages have
  6-fret and rhythm parts) and lists each song's alts.
- `eval/scorer/score.py`: `--windows N` (per track F1@100 and counts per N-s window over the ref span, the lowest, a
  second summary line), `density_peak_1s`, `state_agreement`, `jumps` (histogram, big fast jumps, the EMD between the
  two histograms), `downbeat_f1_70ms`, `star_power_per_min`, `solo_share`, an unopenable stem skipped with a warning
  (candidate, `--input` or input.wav), `--cand-audio FILE` (a human chart's folder, whose audio is elsewhere), and
  ffmpeg looked up as songcharter does (CI has no ffmpeg on PATH). No existing key changed: the golden summary of the
  reference set is identical (below). `eval/scorer/scan_notes.cjs` prints each track's star power and solo sections
  (new keys only; it is in `eval/`, which the order allows, though not in its list of files: say so if that matters).
- `eval/lyrics_timing.py` (new): `.chart` and `.mid` lyric events to words (word index and time only), compared by
  index; every error printed as its type. Every print reviewed: it prints one JSON line of counts and milliseconds, or
  `lyrics_timing: failed (<type>)`.
- `eval/golden.py`: no change to `run`'s logic was needed for the stress set (nothing assumed the seven ids; the test
  song is added only when `refs/test_song` exists); the kept folders default to `$SONGCHARTER_GOLDEN/stress-work`
  for a `--refs` folder named `stress`, and the docstring says how the set runs. `diff` unchanged.
- `eval/baseline/stress/` (new): `summary.json`, `stress_scores.json`, `README.md`.
- `tests/test_eval_stress.py` (new, 27 tests) and one test in `tests/test_golden.py`.
- `eval/README.md` ("Stress songs", the scorer's measures, `STRESS_LOCAL`), `docs/DESIGN.md` 3.3 (the stress set),
  3.6 (the run, the stress check, the baseline's numbers) and 2.15 (the lyrics check). PROGRESS left to the
  orchestrator, as the brief says.

## Where titles, artists, charters and md5s were kept out (the brief's change 1)

1. `eval/stress.json`: generic ids and slots only; a test asserts it holds no md5-like string and no `charter` key.
2. The local list `$EVAL_DATA/stress.local.json` holds them, outside the repository.
3. `stress_scores.json` is built with no title or md5: alt charts are labelled `alt1`, `alt2`, ... (ordered as in the
   local list: `break`'s <alt> first, so the scorable one is alt1), and it holds no path.
4. `eval/baseline/stress/summary.json`: copied by `stress.py baseline`, which cuts every absolute path to
   `<path>/<last part>` (the `run` section's code, golden, out, work, refs, stems and Python) and replaces any value of
   the local list (md5s, titles, artists, charters, as whole words) with `<redacted>`, then refuses to write if one
   is left. On the real run none needed redacting (golden's summary copies nothing from song.ini; the build's
   `--title` reaches only logs, which the summary quotes only for a failed build). The rock song's title is also its
   id, `break`, which the brief chose: that value is exempt and appears as the id.
5. A final scan of `git diff main...HEAD`, the commit messages and both baseline files for every value of the local
   list (and their words of 5+ letters and the md5s' 6-hex prefixes): no hit but the id `break` and the common words
   "three" and "orange" (in code comments).
6. The test fixtures use made-up names, md5s (`000...01`) and words.

## The set and its packages

The primary is the chart with the most parts (a counts-only script over the packages' charts: instruments with
notes, vocals, Expert guitar notes); ties by more Expert guitar notes:

| id | primary | parts | others |
|---|---|---|---|
| troop | <primary> (`.mid`) | guitar, bass, drums (4 levels each), vocals with lyrics; its guitar, rhythm, vocals and drums `.opus` are 135-byte stubs, skipped (the song's full mix is used) | <alt> (guitar, 4 levels), <alt> (guitar, Expert, carries lyrics) |
| sooth | <primary> (`.mid`) | guitar and bass, 4 levels; guitar, rhythm and song stems summed | <alt> (guitar, Expert) |
| break | <primary> (`.mid`) | guitar (443 Expert notes) and a 6-fret part; its one audio file (`guitar.opus`) is the full mix (a low-band energy share of 0.42, as the owner's file's 0.43) | <alt> (guitar 442 notes and rhythm; another edit, audio 1.19 s off), <alt> and <alt> (6-fret and rhythm only: listed as alts, not scored; their two audio files, a full mix and a near copy at 0.993 correlation, are summed) |

**The rock song's `align`** (`stress.py align break <the owner's file>` against the set's input.wav): lag +81.5 ms,
9 of 9 windows peak at 0.3 or more, the lags' MAD 0.00 ms: **ALIGNED**. The owner's file is the packages' audio
81.5 ms later, so his own chart and play test of it are comparable with the set's numbers. The song stays.

## The baseline (main at fbd9751; `stress-base`)

`python -m eval.golden run --code /dev/shm/stress-main (fbd9751) --refs $EVAL_DATA/stress --work
$SONGCHARTER_GOLDEN/stress-work --out $SONGCHARTER_GOLDEN/stress-base --threads 2 --stems <sepcache>`, then
`stress.py score`. `stress-base` existed at 14:03 UTC (progress log). Exit 0, every gate OK, 4000 s cold.

### The feel report: ours against every human chart, and the humans' agreement (Expert)

o/t: ours/theirs (for `humans` rows: that chart/the primary). Brackets: `docs/reports/feel.md`'s measure.

| song | part | chart | F1@50 | F1@100 | notes | lowest 30 s [F1@100 at] | err ms [1] | chords o/t [2] | 1-s peak o/t [2] | contour [3] | jump EMD [3] | big fast/min o/t [3] | HOPO o/t [5] | tap o/t [5] | sustain o/t [5] | state [5] | SP/min o/t [7] | solo o/t [7] |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| troop | guitar | ours vs primary | 0.614 | 0.637 | 0.70 | 0.482 at 1:04.8 | 69.3 | 0.33/0.05 | 7/27 | 0.60 | 0.38 | 0.0/27.4 | 0.29/0.51 | 0.04/0.00 | 0.04/0.04 | 0.49 | 2.42/3.43 | 0.31/0.21 |
| troop | guitar | ours vs alt1 | 0.623 | 0.644 | 0.74 | 0.527 at 4:34.7 | 66.5 | 0.33/0.04 | 7/27 | 0.60 | 0.41 | 0.0/29.7 | 0.29/0.21 | 0.04/0.21 | 0.04/0.06 | 0.51 | 2.42/3.03 | 0.31/0.25 |
| troop | guitar | ours vs alt2 | 0.632 | 0.652 | 0.69 | 0.542 at 1:02.0 | 62.3 | 0.33/0.03 | 7/27 | 0.57 | 0.46 | 0.0/42.4 | 0.29/0.29 | 0.04/0.16 | 0.04/0.05 | 0.51 | 2.42/4.44 | 0.31/0.31 |
| troop | guitar | humans: alt1 vs primary | 0.925 | 0.935 | 0.94 | 0.856 at 2:34.8 | -0.4 | 0.04/0.05 | 27/27 | 0.68 | 0.04 | 29.5/27.4 | 0.21/0.51 | 0.21/0.00 | 0.06/0.04 | 0.64 | 3.03/3.43 | 0.25/0.21 |
| troop | guitar | humans: alt2 vs primary | 0.917 | 0.926 | 1.02 | 0.763 at 0:04.8 | 8.8 | 0.03/0.05 | 27/27 | 0.71 | 0.09 | 42.4/27.4 | 0.29/0.51 | 0.16/0.00 | 0.05/0.04 | 0.68 | 4.44/3.43 | 0.31/0.21 |
| troop | bass | ours vs primary | 0.702 | 0.736 | 0.82 | 0.211 at 0:04.8 | -2.6 | 0.04/0.00 | 8/14 | 0.79 | 0.04 | 0.0/3.8 | 0.21/0.12 | 0.00/0.00 | 0.01/0.03 | 0.78 | 2.53/3.23 | 0.00/0.00 |
| troop | drums | ours vs primary | 0.851 | 0.872 | 0.90 | 0.828 at 3:34.8 | 0.1 | 0.78/0.63 | 8/14 | 0.76 | — | — | — | — | — | — | 2.43/3.24 | 0.00/0.00 |
| sooth | guitar | ours vs primary | 0.651 | 0.789 | 0.94 | 0.500 at 4:06.4 | 39.9 | 0.08/0.06 | 11/17 | 0.67 | 0.10 | 1.9/2.4 | 0.34/0.55 | 0.15/0.00 | 0.14/0.07 | 0.56 | 3.88/2.33 | 0.80/0.00 |
| sooth | guitar | ours vs alt1 | 0.765 | 0.790 | 0.93 | 0.545 at 4:02.1 | 8.3 | 0.08/0.04 | 11/16 | 0.68 | 0.12 | 1.9/2.4 | 0.34/0.39 | 0.15/0.07 | 0.14/0.14 | 0.66 | 3.88/3.23 | 0.80/0.36 |
| sooth | guitar | humans: alt1 vs primary | 0.712 | 0.934 | 1.01 | 0.868 at 3:36.4 | 48.2 | 0.04/0.06 | 16/17 | 0.79 | 0.07 | 2.4/2.4 | 0.39/0.55 | 0.07/0.00 | 0.14/0.07 | 0.74 | 3.23/2.33 | 0.36/0.00 |
| sooth | bass | ours vs primary | 0.692 | 0.734 | 1.28 | 0.536 at 2:36.4 | 27.2 | 0.01/0.00 | 11/7 | 0.74 | 0.16 | 0.0/0.0 | 0.11/0.12 | 0.00/0.00 | 0.15/0.15 | 0.92 | 3.77/2.40 | 0.00/0.00 |
| break | guitar | ours vs primary | 0.832 | 0.855 | 1.18 | 0.333 at 2:41.2 | 5.7 | 0.81/0.67 | 8/6 | 0.55 | 0.21 | 0.0/0.4 | 0.05/0.10 | 0.00/0.00 | 0.08/0.24 | 0.92 | 2.76/2.46 | 0.17/0.16 |
| break | guitar | ours vs alt1 | 0.841 | 0.850 | 1.20 | 0.355 at 2:42.4 | -4.0 | 0.81/0.64 | 8/11 | 0.55 | 0.12 | 0.0/0.0 | 0.05/0.11 | 0.00/0.00 | 0.08/0.21 | 0.93 | 2.76/2.10 | 0.17/0.15 |
| break | guitar | humans: alt1 vs primary | 0.951 | 0.972 | 0.98 | 0.932 at 1:41.2 | 9.7 | 0.64/0.67 | 11/6 | 0.94 | 0.12 | 0.0/0.4 | 0.11/0.10 | 0.00/0.00 | 0.21/0.24 | 0.99 | 2.10/2.46 | 0.15/0.16 |

### Beat lines [8] and shape [6]

| song | chart | beat F1 | octave-tolerant | downbeat F1 | lag ms |
|---|---|---|---|---|---|
| troop | ours vs primary | 0.302 | 0.399 | 0.070 | 4778.1 |
| troop | ours vs alt1 | 0.302 | 0.399 | 0.070 | 4871.9 |
| troop | ours vs alt2 | 0.301 | 0.393 | 0.064 | 7598.0 |
| troop | humans: alt1 | 1.000 | 1.000 | 1.000 | -93.7 |
| troop | humans: alt2 | 1.000 | 1.000 | 1.000 | -2819.9 |
| sooth | ours vs primary | 0.644 | 0.963 | 0.278 | 4032.9 |
| sooth | ours vs alt1 | 0.654 | 0.978 | 0.281 | 8391.8 |
| sooth | humans: alt1 | 1.000 | 1.000 | 1.000 | -4370.5 |
| break | ours vs primary | 0.994 | 0.994 | 0.988 | 3602.9 |
| break | ours vs alt1 | 1.000 | 1.000 | 1.000 | 2414.5 |
| break | humans: alt1 | 1.000 | 1.000 | 1.000 | 1188.4 |

| song | part | notes in silence | gaps (measures) | rings past a sustain | notes in silence (preview) |
|---|---|---|---|---|---|
| troop | guitar | 0 | 0 | 0 | 0 |
| troop | bass | 0 | 0 | 0 | 0 |
| troop | drums | 5 | 0 | 0 | 0 |
| sooth | guitar | 146 | 1 (9) | 0 | 0 |
| sooth | bass | 0 | 0 | 1 (1) | 0 |
| sooth | drums | 29 | 0 | 0 | 0 |
| break | guitar | 0 | 1 (2) | 1 (1) | 0 |
| break | bass | 0 | 0 | 0 | 0 |
| break | drums | 1 | 0 | 0 | 0 |
| break | alt2 | not scored: no guitar, bass or drums notes | | | |
| break | alt3 | not scored: no guitar, bass or drums notes | | | |

The `lag ms` column is the alignment of each candidate's audio to the reference's (ours carries the lead-in pad).
Bass and drums have no second human chart on any song (every alt is guitar only).

### The numbers M5-01 to M5-04 cite as "the baseline"

- **M5-01 (the power-metal song):** grid 100.0 BPM (the half of the song's 198; `report.json`'s `bpm_median`, mode
  free); guitar F1@50 0.614 / 0.623 / 0.632 against the three charts (so its pass line is 0.714 / 0.723 / 0.732; the
  humans 0.917 and 0.925 against the primary); bass 0.702, drums 0.851 (not lower); guitar timing error +69.3 / +66.5
  / +62.3 ms (bass −2.6, drums +0.1); plain beat F1 0.302 (octave-tolerant 0.399, downbeat 0.070); chord share 0.33
  (the humans 0.03–0.05); state agreement 0.49 / 0.51 / 0.51 (the humans 0.64, 0.68); star power 2.42 phrases a
  minute (the humans 3.03–4.44); 1-s density peak 7 (the humans 27). The shred instrumental: guitar 0.651 / 0.765,
  bass 0.692; the rock song: guitar 0.832 / 0.841 (not lower).
- **M5-02 (the shred instrumental):** on this 1-take CPU run the guitar does not stop early: its last Expert note is at
  536.3 s of song.ogg (532.3 s of the input; pad 4.03 s), and the last two 30-s windows score F1@100 0.78 (486–516 s
  of the ref span) and 0.65 (516–546 s). The order's "0 today" for the last 60 s does not hold on this baseline;
  whole-song F1@50 0.651 (primary) / 0.765 (alt1). **Uncertain, for the orchestrator:** M5-02's pass lines were
  written from runs where the take was cut short; on this machine's CPU take it is not.
- **M5-03 (solos):** our charts' guitar solos: troop 1 (90.9 s), sooth 3 (23.6, 248.7 and 148.7 s), break 1 (28.8
  s); solo share 0.31, 0.80 and 0.17 against the humans' 0.21–0.31, 0–0.36 and 0.15–0.16.
- **M5-04 (lyrics):** the lyrics check below.

## The lyrics check (`stress.py lyrics troop --run stress-base`)

Run once, on 2 threads, from the stress baseline's kept folder (so only assemble and the aligner ran; the aligner's
weights, 1.26 GB, downloaded on first use): **320 of 320** human words paired by index (share 1.000; 320 in our
chart); median error **7.0 ms** (signed +0.1); within 50 / 100 / 250 ms **0.681 / 0.756 / 0.953**; phrase starts
over 500 ms off: **8 of 51**; gate OK; the pipeline warned about the lyrics: **yes** (one warning, the unsure one:
median confidence 0.18, under 0.25). 207 s with the download. Nothing was left under `stress-work/.runs/`. In
DESIGN 2.15 beside the owner's 2026-11-05 counterpart (0.68 / 0.77 / 0.96, no phrase start over 500 ms, the same
warning). For M5-04's pass line ("at least 90 % within 250 ms and no warning"): 0.953 already, the warning is the
gap. No word was printed: the command prints the two lines above (numbers), its errors as their type; its stderr held
only the weights' download progress lines.

The first two attempts did not run the chart (no numbers, no words): `/usr/bin/time` was missing from my job script,
then an OSError, a cross-device hard link from the kept folder into a temporary folder on /dev/shm. Fixed in 54b10d3:
with `--run` the temporary folder goes under the kept folders' `.runs/` (same file system, named `<pid>-...` as
golden's run folders), with a test.

## Repeat consistency (the feel note's 4)

Not built: it is M5-99's (M6) with the fix. The rest of the order, the baseline and its fixes came first, and the
session's usage budget was the limit the orchestrator named. The measure needs allin1's labelled sections from the kept
folders (`sections/segments.json`), each repeated label's Expert guitar onsets aligned by onset time, and the share
of corresponding notes on the same lanes, ours against the human chart's own on the same sections.

## Costs and disk

- `df -h /` before the build: 22 GB free (12:53); after the run: 19 GB free (14:03); the 10 GB floor was checked
  before the run (21 GB free) by the chain script.
- The built set (`$EVAL_DATA/stress`): 0.57 GB, 3.3 min for the nine charts. The kept folders
  (`$SONGCHARTER_GOLDEN/stress-work`): 2.5 GB (no separation cache held these songs: separated into the kept
  folders). `stress-base`: 25 MB. The packages copied into `$EVAL_DATA/sng`: 91 MB.
- The cold run: troop 1371 s (separation 226, allin1 126, guitar take 943), sooth 2046 s (419, 205, 1277), break
  410 s (118, 88, 160); then 28–80 s a build; 4000 s in all. `score`: 110 s.

## Checks

- **The suite** (dev, `tools/heavy.sh ... pytest -q -p no:cacheprovider --basetemp=/dev/shm/pt-m509-suite`, at
  30835b4 plus the score.py change being written): `888 passed, 4 skipped in 668.43s (0:11:08)`. After the last two
  code commits, `tests/test_eval_stress.py tests/test_golden.py` with no ffmpeg on PATH (as CI): `61 passed in
  35.54s`.
- **The new tests fail when their code is broken** (a script applied each break, ran the test, restored the file; 23
  breaks, every one failed a test): the stdin fix reverted (fd 3, the helpers' `</dev/null`, `stdin=DEVNULL`: only
  the first song built); the stub-stem skip; the windows' candidate count; the density peak's window closed at both
  ends; every state a strum; fast jumps at 50 ms; time signatures ignored by the downbeats; star power per second;
  the solo share unclipped; score.py's stub skip; the humans aligned on their folder's stub audio; an unscorable alt
  scored; the compare rule at 0.02; a gone part not a regression; align always aligned; syllables not joined; the
  words printed by lyrics_timing; only the song folder deleted by the lyrics check; a word in the lyrics check's line;
  the baseline's values kept; its paths kept; the chart count not checked; and the lyrics check's folder in the
  system's temp (cross-device: the new test fails).
- **The golden run of the reference set** (the order's Evaluation, as the brief's change 5): `python -m eval.golden run
  --out <scratch> --threads 2` from this branch (c9e7e00 with uncommitted docs; songcharter unchanged from main), warm,
  345 s, every engine cached; `python -m eval.golden diff $DEV/golden/base <it> --expect none`: `golden
  diff: no UNEXPECTED change`, exit 0, "Every song's results (hashes, counts, scores) identical: yes", with the
  warning that the scorers differ (scan_notes.cjs and score.py changed; scan-chart the same). Against the container's
  committed `eval/baseline/summary.json`: the six references' 72 part-levels have the same hashes and the pooled F1s
  are equal (guitar 0.8527, bass 0.8247, drums 0.9617, beat 0.8755 at Expert); the test song's 12 part-levels all
  differ (this machine's test-song file and decode are not the container's; `eval/README.md` warns of exactly that),
  and the diff names the container run's guitar rerun.
- **The stress set built** (`tools/heavy.sh` chain, `eval/build_refs.sh --set stress`): nine `ok` lines, exit 0.
- **The baseline run**: `golden exit 0`, `summary: .../stress-base/summary.json (4000 s)`; `stress.py score`: exit 0.
- **`stress.py align break <the owner's file>`**: `lag +81.5 ms; 9/9 windows peak at 0.3 or more; lags' MAD 0.00 ms:
  ALIGNED` (exit 0).
- **The hard-rule scan** of `git diff main...HEAD` and the commit messages: no lyric (only made-up test words), no
  audio (`check_no_audio.py eval tests`: ok), no assistant model name but the required trailers, no personal path,
  user name or machine name; and the local list's values (above): only the id `break`.
- **CI**: run 42042051869 (30835b4) failed: 8 of my score.py tests, because the runner has no ffmpeg on PATH (fixed
  in 7276029: score.py finds the imageio-ffmpeg wheel as songcharter does). Run 42043899186 (7276029): **success**,
  both jobs; Linux suite `888 passed, 4 skipped in 287.28s`, the CI tools' tests `86 passed`; Windows green. Run
  42047845913 (857fff3, the branch's head): **success**, both jobs; Linux suite `889 passed, 4 skipped in 292.40s`,
  the CI tools' tests `86 passed`.
  This order adds no CI hook: its checks are suite tests, which CI runs (the 4 skips are the allin1 and LnkParse3
  ones, so the stress tests ran).

## Not done or uncertain

- **Repeat consistency** not built (above): M5-99's.
- **M5-02's baseline**: the shred instrumental's 1-take CPU chart runs to 532 s of the input and its last windows score
  0.78 and 0.65, not the order's "0 today" (that came from a run whose take was cut short). Its pass lines may need
  rewriting against this baseline.
- **The rock song's two 6-fret-and-rhythm charts** are listed as alts but not scored (score.py scores guitar, bass and
  drums); its humans' agreement is one chart (<alt>, 0.951 F1@50 against the primary).
- **No second human chart has bass or drums** on any song: the humans' ceiling is guitar's only.
- `eval/scorer/scan_notes.cjs` was changed (new keys) though the order's list of files does not name it; it is under
  `eval/`. The golden summary's `scan_notes_sha256` and `score_sha256` change, so `diff` warns that the scorers
  differ between a summary made before this order and one after.
- The local list's `slot` field holds a placeholder ("the primary: the most parts"); the committed slot is used.
- The warm cost of a stress run after the first is the first run's builds (28–80 s a song), not a measured warm run.
- `stress-base`'s summary records the tooling at e74146d (`/dev/shm/m509-tools`, since removed); the scores were made
  at the same commit. The later commits do not change score.py's numbers (the ffmpeg lookup only) or stress.py's
  scoring.
- Left on the machine: `$EVAL_DATA/stress` (0.57 GB), `$EVAL_DATA/stress.local.json`, the packages in
  `$EVAL_DATA/sng`, `$SONGCHARTER_GOLDEN/stress-work` (2.5 GB, which M5-01 reads) and `stress-base`, the lyrics weights
  in the user cache (1.2 GB). Removed: the worktrees `/dev/shm/stress-main` and `/dev/shm/m509-tools` and my
  /dev/shm scratch. `df -h /` at the end: 18 GB free.

## Review fixes

The review (no major finding) found six test gaps, R1 to R6: checks whose tests could not fail. All six are fixed as
tests in 61213d8 (`tests/test_eval_stress.py` only; no eval tool changed, so M5-01 reads the same tools). Each one
fails on the reviewer's break (its `breaks_full.py`, rerun on this worktree: all 11 CAUGHT):
- **R1** `compare-f1_100` (the rule tested on F1@100): the `scores_with()` fixture now gives F1@100 its own value
  (0.95), and a new case has only F1@100 falling (exit 0).
- **R2** `window-lowest-max` (the last window taken as the lowest): the windows test has three windows of 7 s, and the
  lowest is the middle one (F1@100 1.0, 0.0, 1.0); one last-window note 60 ms late still matches.
- **R3** `lt-phrase-over` (hard-wired 0) and `lt-mid-phrase` (note 105 only): a second phrase 600 ms late gives
  `phrase_starts_over_500ms` 1 of 2, and the generated .mid opens its second phrase on note 106. Made-up words only;
  the test still asserts that no word reaches its output.
- **R4** `jumps-chords` and `jumps-fast-le`: green, a green-orange chord, orange, then green 150 ms later and orange
  62.5 ms after it: 6 pairs, 1 big fast jump, neither the chord's pairs nor the 150-ms one counted.
- **R5** `align-mad` and `downbeat-cand-none`: a copy 0.05 % fast (20 ms of drift over 40 s) peaks in every window
  but its MAD fails the alignment; a 2/4 candidate against a 4/4 reference has recall 1.0 and precision 0.5.
- **R6** `shape-silent`, `shape-judged` and `scrub-no-check`: `shape()` on a generated song folder and stems (report.json's
  3 silent onsets, a gap from 8 s to 20 s, bass and drums not judged); the baseline refuses (exit 2, no file written)
  when the scrub misses a value.

Checks: `tests/test_eval_stress.py` 30 passed; the full suite via `tools/heavy.sh python -m pytest -q -p no:cacheprovider
--basetemp=/dev/shm/pt-m509-suite`: `892 passed, 4 skipped in 691.29s (0:11:31)`. The first push hit a GitHub server error
("fatal error in commit_refs_rules") and went through on a retry. CI run 42062280238 on 61213d8:
https://github.com/neb882/song-charting/actions/runs/42062280238: **success**, both jobs, with the Linux suite at
`892 passed, 4 skipped in 343.80s`.

## Review (sc-reviewer, 2026-11-05)

# M5-09 review (sc-reviewer)

Diff fbd9751...origin/m5-09-stress-eval (857fff3), copied to /dev/shm/review_m509 (now removed). Targeted tests in the
copy: `tests/test_eval_stress.py tests/test_golden.py`: 61 passed. Break script:
<scratchpad>/... (26 breaks; the
survivors were re-run against both whole files, breaks_full.py: "61 passed" for each).

Lens 1 (hard rules): no findings. Every print in lyrics_timing.py and in stress.py lyrics gives counts or an
exception's type. OSError and Refused messages carry paths only. The pipeline's log is captured and not printed. The
aligner's cache is work/lyrics under the temporary folder, and `<out>.failed` sits under it too. The committed files
hold no 32-hex string, no absolute path, and no title, artist or charter key or value: I grepped them for the order's
song name. My breaks "lyrics-print-e" and "lt-main-msg" were caught.

Lens 2 (correctness): no wrong result found. The measures match the order's definitions, the regression rule is
right (`b < a - 0.01` on primary F1@50, and a part that is gone counts), and the stdin fix, golden's default_work and
make_songs_json are sound. Every finding is in lens 3.

## Findings (all minor; tests that cannot fail)

- R1 minor, eval/stress.py:431: the stress check's exit-1 rule can test the wrong measure and stay green. Break
  `b["f1_50"] < a["f1_50"] - REGRESSION` -> `b["f1_100"] < a["f1_100"] - REGRESSION`: SURVIVED [61 passed]. The cause
  is that `scores_with()` in the tests sets f1_100 equal to f1_50. Fix: give the fixture different F1@100 values.
- R2 minor, eval/scorer/score.py:428 (window_scores): the selection of the lowest window is untested. Break
  `low = min(scored, key=...)` -> `low = scored[-1]`: SURVIVED [61 passed]. The test's lowest window is also its last
  window. The lowest 30-s window is a number M5-02 cites.
- R3 minor, eval/lyrics_timing.py:181: `phrase_starts_over_500ms` can be hard-wired to 0 with the tests green
  (SURVIVED [61 passed]), because the only test expects 0. The value is in the report (8 of 51) and in DESIGN 2.15.
  Ignoring the .mid phrase note 106 (`msg.note == 105`) also survived.
- R4 minor, eval/scorer/score.py:388-391 (jump_stats): the jump definition is untested. Two breaks survived
  [61 passed]: counting chords (the single-note filter replaced by `if False:`) and loosening the fast bound to
  `<= 0.2 s`. The test's notes are all single and are 62.5 ms or 500 ms apart.
- R5 minor, eval/stress.py:458 and eval/scorer/score.py:552: two parts of the gates are untested, both SURVIVED
  [61 passed]. Dropping align's `lag_mad_ms < 2` criterion passes, because the noise case already fails the peak
  test. A downbeat F1 with n_cand = matches (precision always 1) also passes.
- R6 minor, eval/stress.py:228-248 and 639-642: two parts of stress.py are untested. `shape()` (notes in silence,
  gaps and rings in the feel report's [6] table) is stubbed out in every test: `silent_onsets` forced to 0 SURVIVED.
  Removing baseline's refusal check (`if left:` -> `if False:`) also SURVIVED. Today the scrub alone keeps the
  values out, so nothing tests the check against a value the scrub misses.

Breaks that were caught: the compare alt rule, the compare bound, a song gone, a duplicate md5, a missing id, the
lyrics exception text, lyrics_timing's message, humans aligned without --cand-audio. Breaks that survived but that I
do not count as defects: tap/HOPO precedence (taps carry no hopo flag), density on co instead of co_in, a matched
pair's candidate counted in its own window, the chart delay in lyrics_check (it is 0 in the test and consistent with
score.py), build_ref's zero-sample skip.
