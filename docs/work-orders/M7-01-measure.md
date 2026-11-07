# M7-01: the video review's questions, measured against the human charts

**Agents:** `sc-measurer` (a smaller model), one per part: A and B at once, C beside them (its take generation
queued on the heavy-job lock), D when the owner's files arrive. They write only to the scratch folder the brief
names (`<scratchpad>/m7/m7-01/<part>/`), never to the repository. **No branch.** The orchestrator commits the merged
report as `docs/reports/M7-01-measure.md` and the scripts the build orders' bars read under `eval/m7/`, after
PIPELINE's privacy scan. **Time budget:** done by 2026-11-08 18:00 UTC (the weekly meter resets 2026-11-09 13:00);
each measurer stops and reports what it has when the weekly meter reaches 87 %.

*Written by the M7 planner on 2026-11-07 from the video review, the orchestrator's check of it (M7-00 section 1) and
the owner's go-ahead: measure each finding against the humans first, build only what beats today's rules.*

## Why

The review's counts are right and two of its diagnoses wrong (M7-00 section 1); its fixes are untested. Each
question below is one a rule of ours can change. The answer is a number against the human charts on every song that
has one, with the humans' own agreement beside it, so a build order (M7-02 to M7-07) can say whether its candidate
beats today's rule.

## The songs, the data and the rules of the measurement

- **23 songs:** the six references (`$EVAL_DATA/refs`, `EVAL_DATA=$DEV/eval`; kept folders
  `$SONGCHARTER_GOLDEN/work`), the stress set's four (`$EVAL_DATA/stress`, kept folders `stress-work`), the 20-song
  set's 13 (`$DEV/eval-set20/stress`, kept folders `set20-work`, with `STRESS_JSON=$DEV/eval-set20/set20.json
  STRESS_LOCAL=$DEV/eval-set20/stress.local.json`). The environment is eval/README.md's step 9 (`$DEV/gate3-final.sh`
  and `$DEV/set20-run.sh` show it), with `SONGCHARTER_HEAVY_MIN_FREE_GB=1`.
- **Today's charts** (the base arm, charting code identical to a5895ff's): the references `$SONGCHARTER_GOLDEN/v031`
  (the v0.3.1 golden run, identical to v0.3.0's), the stress set `gate3-final-stress`, the 20-song set
  `set20-main`. Their `stress_scores.json` and `scores/` already hold F1, the HOPO, tap and sustain shares and the
  per-note state agreement (`score.py`'s `state_agreement`, matched at 100 ms); `gate3-final-stress` has no
  `stress_scores.json`: score it (`stress.py score`) before using it.
- **The base arm is built like the others** (the plan's advisor, 2026-11-07): those runs were made with `--rerun
  drums,bass,sections` (set20-main without), while A1-A3 run without a rerun from the folders kept at 8ba3cbd, so a
  difference between the two code paths would read as an arm's effect. Build `base` as part A builds A1-A3 (main
  unpatched, about 50 minutes), compare it with the runs above (expect identical: say if not), and use it as every
  arm's base and as part C's one-take arm.
- **A song's value** is its mean over its human charts (F1: the primary as well); **pooled**, the mean over the
  songs with the part; the humans' own agreement (each other chart against the primary) beside each number; a song
  whose humans agree under 0.6 on a measure is reported and left out of its pooled figure, named. The six
  references have one human chart each, so that rule cannot reach them: report every pooled figure with and without
  them. A paired bootstrap over songs (10,000 resamples) gives each difference's 95 % CI.
- **A rule that touches few songs** (a grid under 100 BPM: 6 songs, 3 of them single-chart; an octave other than 1:
  7 songs, 3 halved and 4 doubled) is reported per song on the songs it touches, beside the pooled figure: a 23-song
  CI over mostly unchanged songs says little.
- **Privacy:** numbers only. Never print, save or report a lyric, a chart's events or text, a title, an artist, a
  charter or an md5; the stress songs are troop, sooth, break, pm2, the 20-song ones s01-s13 (their ids sorted, as
  `docs/reports/set20-v03.md` labels them) in everything the report and the JSON hold. A song's vocal track and lyric
  events are never read: whether a song is an instrumental comes from our `report.json`'s vocals stem level.
  Process listings are cut to 80 characters (a process's arguments can hold a title).
- **Disk** (about 2 GB free, a fixed allowance): builds go to `/dev/shm/m7/` (RAM; 9 GB free) and are deleted once
  scored, keeping `summary.json`, `stress_scores.json` and `scores/` in the scratch folder (a few MB an arm); the
  patched checkouts are git worktrees in `/dev/shm/m7/code-<arm>` (6 MB each). Part C's takes: below. Refuse to
  start a job with under 0.5 GB free; `df -h /` in the report.

## Part A: articulation, sustains and the guitar's repeats

**Three builds** of all 23 songs, each from a patched checkout of `main` (an uncommitted patch in a worktree; never
pushed), run as eval.golden runs over the three sets (`--code`, `--out /dev/shm/m7/<arm>-<set>`, `--threads 2`; no
`--rerun`: the patches touch no engine file; the drums flag from the kept folders' commit is the known false
positive) and scored with `stress.py score` (the references: golden's own `scores/`). Each arm carries one HOPO mode
and one sustain floor: states do not read lengths and the sustain measures do not read states, so each is reported
alone.

| arm | guitar `hopo` (pipeline.py's guitar part) | the Expert and Hard sustain floor |
|---|---|---|
| base | "forced" (today) | max(200 ms, 0.75 beat) (today) |
| A1 | "source" | max(200 ms, min(0.75 beat, 300 ms)) |
| A2 | "natural" | max(200 ms, min(0.75 beat, 400 ms)) |
| A3 | "forced" | max(200 ms, min(0.75 beat, 500 ms)) |

The floor's cap applies to the guitar and the bass alike (`quantize.sustain_kept`); report each part. Machine time:
about 50 minutes an arm (references 7, stress 5, 20-song set about 37), 3.3 hours in all with the base arm.

**A-a. The HOPO rule.** Per song and part (guitar; bass on one line), against every human chart: the per-note state
agreement under base, A1 and A2, and under two rules computed per note from those builds, with no build of their own:
- **R1, the octave rule:** "source" on a song whose grid's octave is not 1 (halved or doubled: `report.json`'s
  `grid.octave`), "forced" elsewhere (the review's case: on a halved grid the engine's unforced picked 8ths become
  natural HOPOs);
- **R2, no forced strums in fast runs:** "forced", except that a strum the engine forced on a note our natural rule
  makes a HOPO (gap at most 65/192 of a beat, another lane) takes the natural state (tod's solo).
Also the confusion of states on the matched notes, split by the engine's flag (forced strum, forced HOPO, unforced):
of the notes the engine forced to strum against our natural rule, the share each human chart strums; the same for
forced HOPOs; the HOPO share ours and the humans'. Report the song's grid octave beside it.

**A-b. Taps.** From the base charts (no build): our tap share and the humans'; tap precision (our taps the human
chart taps, at 100 ms) and recall; the state agreement under T0 (today, the engine's taps kept), T1 (no taps: each
becomes a HOPO) and T2 (a tap kept only inside a run of at least 8 notes at 8 or more a second, the review's rule).

**A-c. Sustains.** Per song and part: the sustain share ours (base, A1-A3) and the humans'; the per-note sustain
agreement on the matched notes (both held or both not, at 100 ms); the humans' sustain lengths in ms and in beats of
their own map (median and p10), split at 100 BPM of their map; the share of the humans' sustains our floor would drop
if it judged their notes (each arm's floor, at our grid's tempo). "The slow songs" are those whose grid is under 100
BPM (`report.json`'s tempo), named in the report.

**A-d. The guitar's same-fret repeats.** From the base charts (no build): the repeat share (single notes whose
previous onset is a single note on the same lane) ours and each human chart's; our repeats' match rate at 50 ms
against any human chart, beside our other notes'; the unmatched repeats' gaps (ms) and how many fall inside a human
sustain. Two candidate rules, simulated on the base charts:
- **(a) by gap:** a repeat at least G ms after the previous note (G 150, 200, 250) merges into that note's sustain;
- **(b) by the stem:** the same, only where the guitar stem's onset strength (librosa's `onset_strength` on the kept
  stem) at the repeat is under the song's p-th percentile (p 25, 50).
For each: the notes removed per song, the removal precision (the share no human chart has within 50 ms), the F1@50
change, and the repeat share after against the humans'.

## Part B: silent stems, the bass, solos and drumless stretches

Scripts over the kept folders, today's charts and their report.json files (no build); machine time about an hour.

**B-a. Notes over a silent stem.** Per part (guitar, bass, drums) and song: the human notes (each chart, on input
seconds: the score's lag, offset_check.json's delay) whose window (-0.05, +0.20 s) never comes within D dB of the
part's stem's P95, with `assemble.silent_onsets` on the stem levels assemble computes (`LEVEL_FRAME_S`), D 25
(`SILENT_DB`, today's warning), 30 and 35: count and share of their notes. Ours: `report.json`'s `silent_onsets` (and
the same test at 30 and 35) and the share no human chart has within 50 ms. Candidates: remove (i) every silent onset,
(ii) only those inside a stretch of at least 1 s where the stem stays silent, at each D: the notes removed, the
removal precision, the human notes the same rule would have removed (per song, not pooled), the F1@50 change. Also, for the drums: the per-window F1 (a section's windows) where the drum stem is quiet against the rest of the song (the review's drums blank under an audible hi-hat), numbers only.

**B-b. The bass.** Per song: the same-lane repeat share and the lane spread (each lane's share; the largest lane's
share) ours and the humans'; the humans' open notes (share); the notes ratio (ours over the primary's); our repeats'
match rate at 50 ms against our other notes'. **The cause:** run `engines/bass.py`'s steps in process on the kept
bass stem (onsets, each note's pYIN pitch, the lane map; 10-25 s a song), and for our consecutive same-lane pairs
say whether the pitch is the same (within half a semitone) or changed by a semitone or more (the map kept a change on
one lane); for same-pitch repeats, whether the pitch track stays voiced on that pitch through the onset (the previous
note still sounding: an onset on a held note) and the onset's HFC rise against the song's distribution; of all pitch
changes of a semitone or more, the share that keep their lane. Two candidates, simulated:
- **(a) a gate on held notes:** drop an onset whose pitch equals the previous note's while the pitch track stays
  voiced through it, unless its HFC rise is in the song's top X % (X from the data): notes removed, removal
  precision, F1@50 change, the repeat share after;
- **(b) the map:** a pitch change of a semitone or more always changes the lane where the window's lanes allow: the
  contour (`lane_direction_agreement`) on the matched notes and the repeat share after.

**B-c. Solos.** Per song: an instrumental or not (our `report.json`'s vocals stem level; say the threshold and the
songs on each side); per human chart, its solos (count, measures of its own map, seconds) and their share of the
first..last Expert onset (as M5-03's step 1, `importers.read_song`); ours from the base run's `report.json`
(`solo_details`, `solos_trimmed_by_share`); the overlap: the share of the humans' solo time our solos cover, and of
ours inside a human solo. Then the solo choice re-run in process (`starpower`'s, on the base run's Expert notes and
sections, as M5-03 did) with `max_share` at 0.40 (today), at the 23 songs' largest human share rounded up to the next
0.05 (M5-03's rule), and at the review's 0.75 for instrumentals only: our share and the overlap for each.

**B-d. Drumless stretches.** Per song: the base run's "follow the straight line" warnings (count, seconds, the
song's share); inside each stretch the beat F1 of our beats against each human chart's beat lines (their tempo map,
on input seconds; score.py's beat tolerance) against the rest of the song; and the beat F1 there of three candidate
sources: allin1's beats (the kept sections folder), a beat track on the bass stem's onset envelope, and one on the
guitar stem's band under 350 Hz (the review's). Per stretch and pooled; a stretch with no human beat lines is said so.

## Part C: the take margin

**C-a. Takes.** For every song with a human guitar chart: seeds 101, 202 and 303 (`pipeline.take_seeds(4)`) beside
the kept take (seed 20260609), with `songcharter.engines.autochart.generate(install, <kept folder>/decode.wav, out,
seeds, device="cpu", work=<scratch>)` and 2 threads, one `tools/heavy.sh` job per song so part A's builds interleave,
the cheapest songs first (by the kept take's `generationSeconds`), sooth, troop and pm2 last. Out:
`$SONGCHARTER_GOLDEN/m7-takes/<id>/seed_<seed>/` (each take's `song.ogg` deleted: about 0.5 MB a take, 40 MB in all);
the engine's scratch (its separation and beat map, made once a song) always in `/dev/shm` (a 9-minute song's
separation is about 1 GB: on a disk with about 2 GB free it could make tools/heavy.sh refuse the next queued job),
deleted after each song, its size measured on the first song; a song waits until 6 GB of RAM is free. Check that each new take's `inputSha256` equals the kept take's. Resumable (a finished take is reused);
progress to a log with a DONE line, watched by a tracked waiter (PIPELINE, Long runs). Machine time: about 6.5 hours
(three times the kept takes' generation, 5.7 hours: the references 0.6, the stress set 2.0, the 20-song set 3.2;
plus the engine's separation and beat map once a song, 0.8) [here: the kept takes' summaries].

**C-b. The splice arms.** For each song, Expert guitar built from the four takes at `takes.MARGIN` 0, 0.02, 0.05
(today), 0.10, and the one-take chart (today's CPU default, the base arm); each single take scored alone (the oracle,
reported only). Build them the simplest faithful way and say which: a copy of the kept folder by hard links on the same
file system (`cp -al` to `$SONGCHARTER_GOLDEN/m7-copy/<id>`, beside the kept folders, never into a kept folder, deleted
after each song: `/dev/shm` is another file system, where `cp -al` fails and a real copy is 0.6-0.9 GB a song), with
the three takes added under `guitar/seed_<seed>/`, built with `songcharter
chart <its input.wav> --work <the copy> --takes 4 --device cpu --no-preview` (Expert only, the default) from a patched
checkout whose MARGIN reads an environment variable, or `assemble` in process with the part's takes and the margin
set. An arm whose windows pick what another's pick is not
rebuilt. Machine time: about 2 hours.

**C-c. The numbers.** Per song and arm: guitar Expert F1@50 and F1@100 against the primary and the mean over its
charts; the windows each margin switches (with the chosen take's onsets and the humans' onsets in the window); the
seams; pooled, and each margin minus 0.05 with its CI. If even the 0 arm leaves windows where a take with more
human-matched onsets loses, add one arm: the take score with each take's silent onsets (part B's test at 25 dB)
counted as unmatched (the review's fix #3.1).

## Part D: the owner's GPU arms (optional, the owner's time)

- **D-a. GPU takes of the six references:** `eval/gpu.sh takes` on his PC (eval/README.md, Running it on an NVIDIA
  GPU; about an hour), or, if his `runs/takes/` of 2026-11-02 still carries today's install key (take.json's
  `install`), `eval/gpu.sh results` alone. The zip holds no audio. The measurer checks the takes are on the kept
  folders' clock (most of the default seed's GPU onsets within 50 ms of the kept CPU take's) and repeats C-b and C-c
  with them: the GPU arm.
- **D-b. The thinning spike** on his sooth file: M7-08.

## What each build order's bar reads

| order | its bar reads (from this measurement) |
|---|---|
| M7-02 | A-a's state agreement by rule, A-b's tap numbers, A-c's sustain agreement on the slow songs |
| M7-03 | B-b's cause and its candidates' numbers |
| M7-04 | B-a's removals (silence) and A-d's (repeats) |
| M7-05 | C-c (and D-a's GPU arm) |
| M7-06 | B-c |
| M7-07 | B-d |

The report ends with one line per order: **its candidate clears the bar** (which, with the numbers) or **none does**.

## Done means

- [dev] Every part's numbers for every song it could measure, or the reason it could not (named: a song without the
  part, a take that failed); the bootstrap CIs; each candidate against its order's bar (the build orders' "Bar").
- [dev] `<scratchpad>/m7/m7-01.report.md` (the four parts merged, each measurer's file under
  `<scratchpad>/m7/m7-01/<part>/`), and the scripts listed with what each reads and prints. A check by the
  orchestrator before it is committed: `EVAL_DATA=$DEV/eval python3 -I eval/privacy_check.py <report>` and the same
  with `EVAL_DATA=$DEV/eval-set20` (exit 0; "tool" is a known false positive).
- [dev] `df -h /` at the end; `/dev/shm/m7` removed; the takes kept in `$SONGCHARTER_GOLDEN/m7-takes` for M7-05's
  review.

## Report

`<scratchpad>/m7/m7-01.report.md`: per part the tables above, the arms' and candidates' numbers, the songs left out
and why, the machine time and the disk used. Each measurer returns about 1,000 words with its file's path.
