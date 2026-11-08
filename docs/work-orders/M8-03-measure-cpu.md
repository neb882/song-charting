# M8-03: allin1's memory and chunks, the bass's unpitched onsets, the star power rate at a slow tempo

**Agent:** one `sc-measurer` (a smaller model), parts A, B and C in that order (B and C are in process and short; they
may run while A's allin1 jobs wait on the heavy-job lock). It writes only to `<scratchpad>/m8/m8-03/<part>/`, never to
the repository. **No branch.** The orchestrator commits the report as `docs/reports/M8-03-measure-cpu.md` and the
scripts under `eval/m8/m803/`, after PIPELINE's privacy scan. **Starts:** wave 0 if the weekly meter is under 92 % after
the plan's advisor, else first thing after the reset (2026-11-09 13:00 UTC); nothing waits on the owner. Part A
reports on its own as soon as it is done (M8-05 starts from it). **Time budget:** about 3 hours of machine time, 5
hours in all; stop and report what is done at 85 % of the weekly meter (90 % after the reset). **Rough cost:** 2-3 %
of a week's meter.

*Written by the M8 planner on 2026-11-08 from the v0.4.0 gate's allin1 note (PROGRESS `deferred`), M7-01's B-b2
addendum and M5-99's "Beat-counted rules at a slow tempo".*

## The rules of the measurement

- **Code:** `main` at the v0.4.0 tag, read only (a detached worktree in `<shm>/m8/code-cpu`); allin1's own Python is
  `$SONGCHARTER_ALLIN1_PYTHON` (eval/README.md step 9). Every allin1 run goes through `tools/heavy.sh`
  (`SONGCHARTER_HEAVY_MIN_FREE_GB=1`), one song at a time, and waits until the free RAM (MemAvailable) exceeds the run's
  predicted peak plus 1 GiB (A-a's line, the parent's share included for a run through `songcharter chart`).
- **Songs, values, CIs, privacy, disk:** as M8-02's rules (the 23 songs and the test song by label; 20-song ids mapped
  in process, never printed; numbers only; floats to 3 decimals; nothing in `/dev/shm` beyond the song in hand;
  under 0.5 GB free on `/`, stop). Today's charts are the v0.4.0 gate's runs (`$SONGCHARTER_GOLDEN/v040`,
  `v040-stress`, `v040-set20`) and the kept folders (`work`, `stress-work`, `set20-work`).

## Part A: allin1's memory, and allin1 in chunks (M8-05's bars; about 2.5 hours)

**A-a. The line** (the planner's reading, M8-00 section 6, to be re-derived by a script): each kept folder's
`sections/engine.json` (allin1's `peak_rss_mb`, `input.duration_s`) and `pipeline.json`'s sections stage
(`peak_rss_mb.self`, `child_peak_rss_mb`, `min_available_ram_mb`), 24 songs: the fit of allin1's peak against the
length (intercept, slope, the residuals' range), the parent's high-water mark against the length. The advisor reproduced it
on 23 kept folders: 346 MB + 17.5 MB a second (1.02 GiB a minute), residuals -233 / +197 MB. Four kept songs pass 7
minutes (pm2, sooth, s06, s08), so an L near 7 minutes chunks 4 of the 24; the bar's "every song" means each W is
run on the short songs too (cheap).

**A-b. The parent while allin1 runs.** The parent's high-water mark may come from an earlier stage, so sample it:
on creep (4:00) and the test song (6:52; its tree about 9.5 GiB, so only when the free RAM allows it by the rule
above, else break), one cold sections stage each (a copy of the kept folder without
`sections/`, the rest from cache; `songcharter chart ... --no-preview --threads 2`), the tree's VmRSS every 0.5 s
from `/proc` (the parent and allin1's child apart), giving the parent's RSS while the child runs and the child's
curve. From the code (`pipeline.py`'s sections stage and what follows it): the arrays the parent holds then (the mix,
the six stems, allin1's folded int16 input), the ones a later stage still reads from memory and the ones it could
read again from the work folder, and so what freeing them while allin1 runs would save, in GiB a minute of audio,
and what reloading would cost in seconds. Delete each copy after its song.

**A-c. Chunks.** In allin1's Python, in process, with `songcharter/engines/allin1_runner.py`'s own functions (its
`spectrogram` on the four folded stems as `sections.allin1_input` makes them, its `_model` for the checkpoint the
kept folders record): the whole song's spectrogram cut into windows of W seconds (W 120, 180, 240) overlapping by 30 s,
each window's frame-level outputs from the model, stitched by a linear crossfade over each overlap, then allin1's own
postprocessing (`postprocess_metrical_structure`, `postprocess_functional_structure`, `estimate_tempo_from_beats`) on
the stitched outputs. First reproduce two short songs' whole-song results in process, **break (3:13) and creep
(4:00)** (a whole run holds 3.4-4.6 GiB at that length and 10 GiB at 9:43, beside another heavy job and two builders'
suites on 15 GB: the advisor's finding 4), against the kept `sections/segments.json`: expect identical beats,
downbeats, bpm and segments; if not, say so and compare against fresh whole runs of short songs only. No whole run of
a long song: its whole-song outputs are the kept folder's, and its peak the records' (A-a's line). Per song
and W: beat F1 and downbeat F1 at 70 ms against the whole run, the bpm ratio, the segment starts' F1 at 1 s and the
labels' agreement on matched starts, the run's seconds, and the peak RSS (one W per process, its VmHWM). Then the
grid: on sooth, s02 and s04 (the halved songs) and on every song's downbeats, the grid rebuilt in process from the
chunked beats by M7-09's route (`eval/m7/m709/measure.py`: the first grid, the halving pass, `with_downbeats`): the
octave decision, the grid's beat and downbeat F1 against the humans, against the whole run's.

**A-d. What a PC needs.** From A-a to A-c: the tree's peak against the length today, with the parent's arrays freed,
and with chunks of each W; the longest song that fits 10.2 GiB (WSL's 11 GB, below which the install leaves allin1
out) and 11.2 GiB (12 GB, a 16 GB PC's) with a 1 GiB reserve, each way; and L, the length above which M8-05 would
chunk (the longest whose whole-song tree fits 10.2 GiB with the reserve, after the release).

**Bar (M8-05's chunks):** the smallest W at which, on every one of the 24 songs, beat F1 is 0.99 or more and downbeat F1
0.98 or more against the whole run, the bpm within 1 %, the segment starts' F1 at 1 s 0.95 pooled and 0.90 on every
song, and the grid's octave decision identical on every song, with its beat F1 against the humans within 0.005 of the
whole run's. **The release** (M8-05's freeing of arrays) is built if A-b shows at least 1 GiB saved for a 9-minute song
at a reload cost under 10 s.

## Part B: the bass's unpitched onsets (M8-08's bar; about 20 minutes)

M7-01's B-b2 addendum: on ntl (a ballad of the owner's), 254 onsets sit in fast same-lane runs and almost none of them
carry a pitch from the engine's tracker: the onsets there are not pitched notes. B-b's held-note gate and B-b2's run
rule were scored by HFC rank and run length, and both removed mostly real notes (precision 0.21-0.48). This part
scores a gate that reads the pitch track instead.

In process with `songcharter/engines/bass.py`'s steps on each kept bass stem (as `eval/m7/B/bb.py` and `bb2.py` did; the
v0.4.0 tag's engine): per onset, the voiced share of pYIN's frames 20-150 ms after it, whether the engine gave it a
pitch, whether it sits in a same-lane run of L or more onsets each at most G ms apart, and whether a human note
(any chart) is within 50 ms. Candidates, each dropping the onsets it names from our chart:
- **g1:** every onset with no voiced frame in its window;
- **g2:** g1 only inside a same-lane run (L 4 or 6, G 110 or 150 ms);
- **g3:** g2 only where the note before it is voiced through this onset's start (a held note).
Per candidate: removed, songs touched, precision (no human note within 50 ms), the bass F1@50 change with its CI
(s06, s08 and s10 out of the pooled figure: their humans agree under 0.6; drunk_drivers and break have no bass),
the songs and the references down by more than 0.01, the human notes removed per song, the repeat share after
against the humans'. And ntl's counts (onsets removed, runs touched) if its work folder is still on the machine
(`eval/m7/B/bb2_ntl_diag.py` names where it was); else ntl is skipped and said.

**Bar (M8-08):** removal precision 0.75; bass F1@50 +0.005 pooled with its CI above 0 (or not lower, CI's lower end
above -0.002, for a gate at precision 0.9 or more); no song down by more than 0.01, no reference's bass down by more
than 0.01; the human notes removed under 0.5 % on every song.

## Part C: the star power rate at a slow tempo (M8-09's bar; about 20 minutes)

`starpower.py` counts a phrase per 40 beats (`StarPowerRules.beats_per_phrase`) over the span from the first to the
last Expert onset, the span's beats counted at most at 160 BPM (`max_bpm`, M6-01). On a slow grid the count falls:
sooth, halved to 77 BPM, has 1.89 phrases a minute against its humans' 2.33-3.23 (M5-99).

In process, with `starpower.py`'s own placement on today's charts' notes (the v040 runs' `notes.chart` Expert guitar,
the grid as each chart's tempo map gives it): per song, our phrases a minute and the share of Expert notes inside a
phrase under today's rule and with the span counted at least at B BPM (B 100, 120: a `min_bpm` beside `max_bpm`), each
against every human chart's (from its star power phrases; scan-chart's parse); our phrases' overlap with the humans'
(the share of our phrase notes inside a human phrase, mean over charts). The slow songs (grid under 100 BPM: creep,
lucretia, sooth, s02, s04, s13) apart; every other song must come out identical (assert it).

**Bar (M8-09):** on every slow song with a human chart that has star power, the rate moves into or toward the humans'
range (min-max over its charts) and away on none; the overlap with the humans' phrases not lower pooled over the slow
songs; no song at 100 BPM or over changes.

## Done means

- [dev] `<scratchpad>/m8/m8-03/report.md`: A (the line, the parent, the chunks per W, the grid, A-d's lengths, the bar),
  B and C with their bars' verdicts; JSON per part (rounded); the scripts, each starting with what it reads and prints;
  privacy_check 0 found with `EVAL_DATA=$DEV/eval`, and with the 20-song list only the known false positive.
- [dev] The kept folders unchanged (a listing before and after A-b's copies); the copies and `<shm>/m8` removed;
  `df -h /`.

## Report

The file above and a summary of at most 1k tokens: each part's verdict against its bar, W and L for M8-05.
