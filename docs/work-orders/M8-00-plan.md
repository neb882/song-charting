# M8 plan: songcharter v0.5.0, measured on the GPU's takes

*Written 2026-11-08 on branch `m8-plan` from `main` at 0938a5a (v0.4.0 at its release gate, M8-01 merged) by the
planner (docs/PIPELINE.md, Gates: a fresh agent that reads the repository and the owner's goals). The orchestrator
runs the waves; an advisor (a different model) reviews this plan before any build. Evidence tags follow DESIGN.md:
[code] read from this repository, [here] measured on the dev machine or recorded in PROGRESS or a report,
[inference], [decision] a choice made here, [owner] the owner's to make.*

## 1. What this version is

M7 measured every finding of the owner's video reviews against the human charts of 23 songs and built only what
cleared its bar (M7-02's taps, M7-06's fourth solo, M7-09's halved line, M7-10's page). Most questions closed on
**CPU takes**, and the spikes after it (docs/reports/M8-spike-contour.md, M8-spike-takescore.md) found nothing that
clears on them either. But the friend's default is **4 guitar takes on his GPU** (DESIGN 2.7, `pipeline.guitar_takes`),
and the owner's GPU charts differ from every CPU chart M7 measured [here]:
- open notes: our CPU charts' open share is 0.007 (the humans' 0.040); the GPU takes write opens (pm2's GPU chart has
  420), the CPU takes almost none (M7-01 A-e);
- same-fret repeats: pm2's are 86 % on the owner's GPU chart (the video review's count) against 0.29 at matched
  fast-run pairs of the CPU chart, where the humans' share is 0.289 (the contour spike);
- the takes: the 2026-11-02 takes experiment, on GPU takes of five of the six references (Lucretia apart), had 4
  spliced takes +0.013 F1@50 over one; M7-01 part C, on CPU takes of 23 songs, +0.004 [-0.009, +0.019].

The owner said of what M7 left, "Do what you think is best", and of the page, "I'll leave it up to you. you're the
expert" [owner]. So M8 is planned around **4 GPU takes of all 23 songs with human charts**, made on his PC by M8-01's
tooling after v0.4.0's release (a few hours of his GPU, unattended; a zip with no audio and no names), and measured
here the way M7-01 measured the CPU's. Beside that line, three pieces of work that do not wait for his GPU: a UI pass
(the second-model review's items 5-10 and the v0.4.0 gate's notes), allin1's memory on long songs (the v0.4.0 gate),
and three small CPU-side questions (the bass's unpitched onsets, the star power rate at a slow tempo, and allin1's
chunks).

**The approach is M7's:** each question is a number against the human charts, with the humans' own agreement as the
ceiling; a build starts only when its candidate clears a bar fixed in this plan before any number is seen; an order
whose candidates all fail goes to `dead_ends` with its numbers. **The version number: 0.5.0** [decision]: the GPU
charts change on purpose (if any GPU-line rule lands) and the page changes visibly.

## 2. Scope: the orders

Costs are rough: machine time on the dev machine (4 cores, CPU only, 15 GB RAM) and agent usage as a share of a
week's meter, from the sizes of M7's orders, not measured.

| order | name | one line | conditional on | size | rough cost |
|---|---|---|---|---|---|
| M8-01 | gpu-takes (merged 65f1bcc) | the owner's PC: 4 GPU takes of the 23 songs and the test song on the installed app, `gpu_results.zip` | — | his GPU 2.5-8.5 h unattended | done |
| M8-02 | [measure-gpu](M8-02-measure-gpu.md) | M7-01's take, articulation, repeat, open and contour questions on the GPU takes; per question, whether the GPU changes the CPU's answer; four parts (A the takes' shape, B the splice and a selector, C articulation, D fast runs) | the zip | 6-8 h of machine time, a day | 5-7 % (two measurers) |
| M8-03 | [measure-cpu](M8-03-measure-cpu.md) | A allin1's memory and chunked analysis; B the bass's unpitched onsets; C the star power rate at a slow tempo | — | about 3 h of machine time | 2-3 % (one measurer) |
| M8-04 | [ui-pass](M8-04-ui-pass.md) | the queue's design note first; then items 5 (no Linux path), 6 and 10 (flags to their page and to Listen, a lightbox), 7 (the Songs folder prefilled), 8 (Best or Quick), the re-estimate after the first take, the not-answering heading | — | 1.5-2 days | 5-6 % |
| M8-05 | [allin1-memory](M8-05-allin1-memory.md) | the sections' fallback said on the page, a kill for memory named, the arrays the parent need not hold freed while allin1 runs, and chunked analysis of a long song (or a skip that does not wait for the kill) | M8-03 A for its chunk and release parts; the banner is unconditional | 1 day | 3-5 % |
| M8-06 | [take-selector](M8-06-take-selector.md) | the window score or margin that picks the takes, on GPU takes | M8-02 B | 1 day | 2-4 % |
| M8-07 | [gpu-guitar](M8-07-gpu-guitar.md) | the GPU chart's guitar rules: (a) HOPO and strum from the engine's flags, (b) the sustain floor in seconds, (c) open notes, (d) same-fret repeats and the fast runs' contour; each built only if it cleared | M8-02 C | 0.5-2.5 days | 3-7 % |
| M8-08 | [bass-unpitched](M8-08-bass-unpitched.md) | a bass onset gate that reads the pitch track (B-b2's last lead) | M8-03 B | half a day | 1-2 % |
| M8-09 | [slow-star-power](M8-09-slow-star-power.md) | the star power spacing counted at a floor tempo on slow songs | M8-03 C | 2-4 hours | 1-2 % |
| M8-10 | [queue](M8-10-queue.md) | a queue of songs and a list of his charts, from M8-04's design note | the note, accepted by the orchestrator | 1.5-2 days | 5-7 % |
| M8-11 | [thin-runs](M8-11-thin-runs.md) | M7-08's engine-thinning spike on the owner's GPU, scored here; adoption only with the references' arm | M8-02 D and his GPU time [owner] | his GPU 2.5 h (+1 h); 2 h here | 1 % |

**Weighed and left out, with the reason** (the brief's candidates from `deferred`):
- **The halved grid's outro, the ratio warning made a correction** (M7-09; M5-99 "A halved grid back at the first
  grid's tempo"): **dropped from M8.** The one known case is the owner's own audio file of sooth (its last 28 s at
  160 BPM); the stress set's audio of sooth does not do it, and the only other place the warning fires, s02 at
  225-300 s, is where s02's two human charts themselves disagree by an octave. A correction (every other beat in the
  window) can be measured against no human chart we have, and on s02 it would side with one chart against the other.
  It stays a warning; M5-99 keeps it, to be reopened when a second song's report.json carries the warning (the
  orchestrator counts it in the owner's and the friend's charts at the gate).
- **Every other candidate is kept**, each behind its bar: the GPU's opens and repeats (M8-07 c, d), the take selector
  (M8-06), the engine's forced flags (M8-07 a), the halved songs' short sustains (M8-07 b: M7-01 A-c found the floor
  rarely bites CPU notes, since the engine holds few; the GPU's engine may hold more), the bass's onsets over held
  notes (M8-08), the thinning spike (M8-11).
- **Added, small:** the star power rate at a slow tempo (M8-09), the other half of M5-99's "Beat-counted rules at a
  slow tempo", still open after M7 and measurable on today's CPU charts in minutes.
- **Not in M8** (M5-99 keeps them): the meter, the ladder's calibration of the lower levels, the lead/rhythm split,
  1/32 burst slots, the one-click updater, the tempo control on the page, reading Clone Hero's own settings for the
  Songs folder (M8-04 prefills the best guess only: the settings' keys need a real PC and are personal there).

## 3. Waves, dependencies and the usage reset

The week's meter read 86 % at 19:16 UTC on 2026-11-08 (this week's limit 96 %, the owner's, never usage credits); it
resets 2026-11-09 13:00 UTC. The advisor's review of this plan (1-2 %) fits before the reset, and so does M8-03 (a
measurer, 2-3 %) if the meter is under 92 % after the advisor; the builds run in the new week. Two lines run side by
side: the **CPU line** needs nothing from the owner; the **GPU line** waits for his zip, which comes after v0.4.0's
release.

| wave | orders | files (none shared within a wave) |
|---|---|---|
| 0 (now) | the advisor on this plan; M8-03 if the meter allows (else first thing in wave 1) | none: measurers write to scratch only |
| 1 (after the reset) | **M8-04** ∥ **M8-05** (M8-05 starts when M8-03 part A has reported, a few hours in) | `songcharter/ui/*`, `docs/guide/windows-wsl.md`, `tests/test_ui_*` ∥ `songcharter/engines/sections.py`, `engines/allin1_runner.py`, `pipeline.py` (the sections stage), `device.py`, their tests |
| 2 (as slots free) | **M8-08** and **M8-09** if M8-03 cleared them (they share no file and can run together), **M8-10** after M8-04's merge and its note accepted | `engines/bass.py` ∥ `starpower.py` ∥ `songcharter/ui/*` |
| M8-02 | when the zip arrives (two measurers, no builder slot) | scratch only; builds at the v0.4.0 tag's code |
| 3 (after M8-02 reports) | **M8-06** ∥ **M8-07**, taking the first free slots ahead of M8-10 (the queue yields) | `takes.py` ∥ `quantize.py`, `assemble.py` (the guitar part's rules), `pipeline.py` (the guitar part), a new module if (d) clears |
| M8-11 | if the owner runs the spike (after M8-02 D) | scratch only; a setting's adoption is a wave-3-sized build only if the references' arm also came back |
| then | the release gate (section 9) | |

- At most two builders at once (PIPELINE). A dropped order frees its slot; the next in the table moves up where its
  files allow. A builder resumed for its review's fixes counts as one of the two; measurers do not.
- `docs/DESIGN.md` is edited by most orders, each only in its own section (4.5; 2.5 and 4.7; 2.7; 2.6 and 2.7's
  guitar rules; 2.8; 2.10), which git merges; PROGRESS and the reports are the orchestrator's.
- Every order branches from `main` after the wave before it has merged; before it starts, the orchestrator adds to
  its work order the numbers its bar reads (the candidate, its values, the songs).
- **If the zip has not come three days after v0.4.0's release**, the orchestrator asks the owner once; the CPU line
  may then go to a release on its own only with his go-ahead (recommended: wait for the GPU line, which is the
  version's point).
- Heavy jobs (golden, stress and 20-song runs, builds, allin1 runs) go through `tools/heavy.sh`, one at a time, with
  `SONGCHARTER_HEAVY_MIN_FREE_GB=1` (the disk, section 4). Every builder's and measurer's brief carries it (each
  order's Environment line): heavy.sh refuses under 5 GB without it, and `python -m eval.golden run` takes the lock
  but not the disk check.

## 4. The evaluation plan

**The songs** (23 with human charts, as in M7-01): the six references (one human chart each; the test song has none
and stays a regression guard), the stress set's four (troop, sooth, break, pm2; 2-5 charts each), the 20-song set's 13
(s01-s13: their ids sorted, as docs/reports/set20-v03.md labels them; 2-6 charts each; ids and titles private, mapped
in process as `eval/m7/C/songs.py` does). A song's value is its mean over its human charts unless the bar says the
primary; pooled, the mean over the songs with the part; a paired bootstrap over songs (10,000 resamples) gives each
difference's 95 % CI; the humans' own agreement (each other chart against the primary) is the ceiling beside every
number; a song whose humans agree under 0.6 on the measure is reported but left out of the pooled bar, and named
(on guitar F1@50: s02, s04, s06, s12; on bass: s06, s08, s10). Every pooled figure is given with and without the
references, and over all 23.

**The GPU takes** (M8-01's zip): seeds 20260609, 101, 202, 303 per song, each take's `notes.chart` as the engine wrote
it, its `take.json` (the input's SHA-256, the seed, the install) and the engine's `summary.json` (devices, tokens,
beats). The CPU's counterparts are M7-01 part C's: the kept take (20260609) in each kept folder and
`$SONGCHARTER_GOLDEN/m7-takes` (101, 202, 303). A GPU take is used only where its `inputSha256` equals the dev
machine's `input.wav` for that label and its summary says the transcriber ran on CUDA; a song that fails either is
left out and named. The GPU takes are the owner's 5070's; the friend's 4070 draws its own (the same engine and
device class, another draw): the measures are distributions over four seeds, not one chart [inference].

**The bars, fixed here before any number** (each order restates its own):

| question | measure | bar | from |
|---|---|---|---|
| the take selector or margin (M8-06) | pooled guitar Expert F1@50 against the primaries, the 19 songs whose humans agree | +0.005 over today's GPU splice (`takes.MARGIN` 0.05), CI above 0, no song down 0.01, for the primary candidates named before any number (L1 at p 0.6, D1 at its 10 % rule, q05); an exploratory one also needs the CI's lower end at +0.002; a learned score scored only on songs it was not fitted on | M7-05 |
| the engine's forced HOPO/strum flags (M8-07 a) | per-note state agreement at 100 ms, mean over charts | +0.02 pooled, CI above 0, no song down 0.03; tap precision not lower | M7-02 |
| the sustain floor in seconds, the guitar only (M8-07 b) | per-note sustain agreement at 100 ms on the slow songs (grid under 100 BPM) | +0.03 pooled on the slow songs, no song down 0.01 | M7-02 |
| open notes (M8-07 c) | exact-lane and contour (lane direction) agreement at 100 ms, mean over charts, on the songs where our GPU charts have opens | with 8 or more such songs: exact-lane +0.005 pooled with CI above 0, contour's CI lower end above -0.002, no song's exact-lane down 0.01; with fewer: +0.005 pooled, no song's exact-lane down, contour not lower on any song, and then built GPU-only as a trial the owner may veto | new, on M7-01 A-e's measures |
| same-fret repeats (M8-07 d, removal) | removal precision (no human note within 50 ms); F1@50 | precision 0.75; no song's F1@50 down 0.005; human notes removed under 0.5 % on every song | M7-04 |
| the fast runs' contour (M8-07 d, re-lane) | direction agreement on fast-run pairs (8+ onsets at most 125 ms apart) against the primaries | +0.10 pooled, CI above 0, at least 3 songs up 0.10; score.py's whole-song contour and exact lanes not lower | the contour spike |
| the bass's unpitched onsets (M8-08) | removal precision; bass F1@50 | precision 0.75; F1@50 +0.005 pooled with CI above 0 (or not lower for a gate at precision 0.9); no song down 0.01, no reference's bass down 0.01 | M7-03 |
| the star power rate at a slow tempo (M8-09) | phrases a minute and the share of Expert notes in phrases, against the humans' range per song | on every slow song with human star power, the rate moves into or toward the humans' range and away on none; no song at 100 BPM or over changes; our phrases' overlap with the humans' not lower pooled | M5-99, new |
| allin1 in chunks (M8-05) | the chunked run against the whole run: beats, downbeats, bpm, segments; the grid it gives | beat F1 at 70 ms 0.99 and downbeat F1 0.98 on every song, bpm within 1 %, segment starts F1 at 1 s 0.95 pooled and 0.90 on every song; the halving decision and grid octave identical on every song | new |
| the thinning setting (M8-11) | per 30-s window F1@100 against sooth's two charts | the fast windows (humans at 8+ notes a second) +0.10, no window down 0.02, the references' pooled F1@50 unchanged | M5-99 |

**A rule found on GPU takes and the CPU.** A rule adopted from M8-02's numbers applies on both devices unless its CPU
arm (the same rule on the CPU arms M8-02 builds at the tag, rebuilt on the branch) drops the order's floor on any
song; then it applies to GPU charts only, by the chart's configured guitar device (never per take: a CPU retry inside a
CUDA chart keeps the CUDA rule), recorded in report.json as `rules_device` and in DESIGN [decision]. One rule is
preferred; the owner may veto a device-dependent one at the gate.

**The guard on every build order** (beside its own bar):
- Golden (eval/README.md, Golden charts) against the order's merge base, `--expect` naming the parts it means to
  move, `--rerun drums,bass,sections` on both sides (the kept folders' known flags), plus any engine the order
  changes; pooled F1@50 per part and level not lower by more than 0.002, identical where the order changes only flags
  or lengths. The golden set's guitar is one CPU take: a GPU-line rule shows there only through the CPU charts, so its
  bar is re-measured on M8-02's GPU arms rebuilt on the branch (the takes are files: no GPU needed).
- The stress set and the 20-song set: a run of the merge base and one of the branch, `stress.py compare`
  "Regressions: 0" (no F1@50 against a primary down by more than 0.01). The 20-song set runs with
  `EVAL_DATA=$DEV/eval-set20 STRESS_JSON=$DEV/eval-set20/set20.json STRESS_LOCAL=$DEV/eval-set20/stress.local.json`
  and `--refs $DEV/eval-set20/stress --work $SONGCHARTER_GOLDEN/set20-work`.
- The feel report: no measure worse than the base's without a reason in the order's report.
- The bar's measure in `eval/scorer/score.py`'s feel measures (with a test) when score.py lacks it; M8-02's and
  M8-03's scripts are the reference, committed by the orchestrator under `eval/m8/`.

**Disk.** The dev machine has about 1.7 GB free on `/`, a fixed allowance. What each measurement writes:
- M8-02: the zip (about 0.1 GB at most [inference: 92 takes' charts and summaries]) unpacked in
  `<scratchpad>/m8/m8-02/zip`; every arm built into `/dev/shm/m8/` (RAM) and deleted once scored, so `/dev/shm` holds
  under 1 GB at any time; kept: numbers (a few MB) and the GPU charts of two arms (`one` and `m05`, about 15 MB).
- M8-03: allin1's chunked outputs (a few KB a song) and the bass and star power numbers; nothing in `/dev/shm` beyond
  one song's arrays while it runs.
- Builders: a worktree (about 15 MB) and their golden, stress and 20-song runs (about 45, 37 and 113 MB a side, so
  about 0.4 GB an order with its base runs: delete the base runs after the compare).
- Before wave 1, once v0.4.0 is published, the orchestrator may delete the v0.3.x runs no comparison needs any more
  (`$SONGCHARTER_GOLDEN/v031`, `gate3-*`, `set20-main`, `pm2-v02`: about 0.33 GB) and old worktrees; `base`,
  `base-main`, `stress-base*`, `v040`, `v040-stress`, `v040-set20` (v0.5.0's gate compares with these), `m7-takes` and
  the kept folders stay.

## 5. The questions on GPU takes, and what the CPU answered

M8-02 answers each row for the GPU takes and says whether the answer changed. Expected directions are [inference]
from the two GPU observations above, not numbers.

| question | the CPU's answer (M7-01, the spikes) | why the GPU may differ |
|---|---|---|
| 4 spliced takes against 1 | +0.004 [-0.009, +0.019] (19 songs) | the takes experiment's GPU takes: +0.013 on five of the references |
| the margin 0-0.10 | within +-0.004; the take score does not track the humans per window | GPU seeds may spread differently |
| a better window score | none clears (best +0.004 [-0.004, +0.013]); the oracle window's headroom +0.042 [+0.031, +0.053] | the headroom may be larger; a learned score is new |
| the HOPO mode | no mode clears; the engine's forced flags near coin flips (forced strums strummed by the humans 52 %) | the flags are the engine's, and the engine's output differs |
| taps | T2 built (taps only in fast runs) | — (re-checked: T2's precision on GPU charts) |
| the sustain floor in seconds | +0.001 on the slow songs; the engine holds few notes (share 0.072 against 0.106) | the GPU engine may hold more |
| same-fret repeats | every removal lowers F1 (the humans chart them) | pm2's 86 % on the GPU chart: if fret errors rather than extra notes, re-laning rather than removal |
| open notes | ours 0.007 against 0.040; open-to-green moves nothing | the GPU writes opens; whether where the humans do is the question |
| the fast runs' contour | no tracker beats our directions (pYIN where it steps +0.015) | our GPU directions may be far worse in fast runs, so a tracker that is right 0.81 where it steps may now win |
| fast runs' density | (M5-99, the owner's 4-take GPU chart of sooth: 47 % of the human notes found at 8-12 notes a second) | decides M8-11 |

## 6. Robustness: allin1's memory on a long song

**What happened** (the v0.4.0 gate, PROGRESS `deferred`): allin1 on the CPU took about 9 GB on a 9-minute song and
was killed for memory on this machine, so the sections fell back to librosa and the grid lost its halving test and
allin1's downbeats, with only a warning line.

**Measured here from the records** [here: each kept folder's `sections/engine.json`, allin1's own `peak_rss_mb` (VmHWM),
and `pipeline.json`'s sections stage; 24 songs from 2:55 to 9:43, CPU, 2 threads; GiB = 2^30 bytes, the records' MB
2^20]: **allin1's peak grows in a straight line with the song's length, about 0.35 GiB + 1.0 GiB a minute** (354 MB
+ 17.4 MB a second; every song within -0.23 / +0.20 GiB of the line): All the Small Things (2:55) 3.3 GiB, Creep
(4:00) 4.4, the test song (6:52) 7.3, pm2 (7:23) 8.0, sooth (9:09) 9.6, the 20-song set's longest (9:43) 10.1 GiB.
While it runs, the pipeline itself holds the mix and the six stems: its own high-water mark at the sections stage is
1.2-4.4 GiB (2.2 on the test song, 3.5 on pm2, 4.4 on the 9:43 song), so **the tree reaches about 9.5 GiB on the
test song and 11-14.5 GiB on songs of 7-10 minutes** [here, the sum of the two peaks; an upper bound, as the parent's
high-water mark may come from an earlier stage]. On the CUDA lane the host side is no smaller: the GPU smoke test's
tree peaked at 11.09 GiB during the sections for the test song [here, docs/reports/release-gate.md], against the CPU's
9.5 GiB for the same song. allin1's runner also falls back from a CUDA out-of-memory to the CPU for the whole song
[code: `allin1_runner.run`], where the line above applies.

**What the friend's PC needs** [inference from the line]: the install gives WSL Windows' RAM less 4 GB
(`.wslconfig`, PROGRESS M4's memory rule): 12 GB (11.2 GiB) on a 16 GB PC, 28 GB on a 32 GB PC; allin1 is left out
under 11 GB.
- **A 32 GB PC** (26 GiB of WSL) charts a song of up to about 15 minutes with allin1, on either lane.
- **A 16 GB PC (12 GB of WSL, 8 GB of swap)**: today's tree passes 11.2 GiB from about 7 minutes of audio on the CPU
  and on CUDA alike; from there it pages to the swap file (minutes slower) or, with other programs running, allin1
  is killed and the chart loses its halving test silently. A long song charted on his CPU fallback is the likeliest
  case. **What fixes it** (M8-05, from M8-03 part A's numbers): allin1 analysing a long song in chunks (its peak
  bounded by the chunk's length: about 4.4 GiB for 4 minutes), the pipeline freeing the arrays it does not need
  while allin1 runs, and the page saying plainly when the sections fell back and what that costs. With those, 12 GB
  of WSL is enough for any length the guitar stage itself takes [inference; M8-05 measures the guitar's own peak
  beside it].
- **WSL's default cap** (half the RAM when no `.wslconfig` is written: 8 GB on a 16 GB PC) leaves allin1 out by the
  memory rule already; doctor says so.
- The CUDA lane's own figures (allin1's VRAM and host peak against the length) come from the owner's v0.4.0 GPU check
  (section 10, his first ask): three charts, about 5 minutes of his time.

## 7. The UI pass

The owner left the page to the orchestrator [owner]. From docs/reports/m7-ui-review.md (items 5-10; 1-4, 11 and 12
were M7-10) and the v0.4.0 gate's notes, decided here [decision]:
- **M8-04 builds:** 5 (the Done screen without the Linux path; Open folder before an install), 6 with 10 (each flag
  linked to its preview page, the pages and the overview in an in-page lightbox, Listen started at the flag's time),
  7 (the Songs folder field prefilled with the best guess always), 8 (a "Best chart" / "Quick chart" choice on the
  GPU, with each one's estimate; the number of takes, the device and the preview under "More options"; Lyrics and
  Pictures folded; "Chart it" also at the top), the gate's re-estimate (the remaining time from the first take's own
  seconds, which the job's `stage_end` events carry) and its heading (the not-answering case headed "songcharter is
  not answering", the tab "Not answering").
- **M8-04's first deliverable is the queue's design note** (item 9: jobs.py runs one child at a time by design;
  M8-10's work order has the note's questions). The orchestrator accepts or narrows it; M8-10 builds what it accepts
  (recommended: the "Your charts" list and a queue of songs that waits for the running chart, one child at a time).
- **Not built:** reading Clone Hero's own settings for the Songs folder (item 7's second half): the settings' keys are
  unverified and would need the owner's or the friend's own files.

## 8. Risks

| # | risk | caught by | plan |
|---|---|---|---|
| 1 | The zip comes late or not at all | section 3's three-day rule | the CPU line runs meanwhile; no GPU-line build without M8-02 |
| 2 | The owner's 5070 takes stand in for the friend's 4070 takes | four seeds a song, distributions not single charts | the gate's GPU check re-counts the adopted rules on new GPU charts; M4-08 part B's charts when they come |
| 3 | A rule fit on GPU takes hurts the CPU fallback's charts | each order's CPU arm | the rule is device-scoped, recorded (section 4) |
| 4 | A learned take score overfits 23 songs | fitted on the other songs, scored on the held-out one | a song-held-out bar only; its features and weights frozen before scoring |
| 5 | The humans disagree on opens (alt charts 0 to 0.48 open share on one song) | the humans' spread beside every number; songs under 0.6 left out | a rule only beats today's where the humans agree |
| 6 | Chunked allin1 changes long songs' sections and grid | M8-03 A's bar on 24 songs; golden `--expect sections` | a fixed length rule, the same on every PC (never the free memory) |
| 7 | Disk (1.7 GB) or RAM (15 GB, allin1 up to 10 GB) | section 4; one heavy job at a time | builds in /dev/shm deleted per song; allin1 runs alone, waiting for its predicted peak plus 1 GiB of free RAM |
| 8 | The UI pass breaks a working page the friend uses | the reviewer's screenshot pass and the page tests | items in small commits; the gate's look on Windows |
| 9 | The privacy of the 20-song set in the zip and the reports | M8-01's guard and check_no_audio; privacy_check before each push | labels only; `set.json` checked against the dev machine's set before use |

## 9. The release gate for v0.5.0

PIPELINE's gate, in its order, plus what this version adds:
0. The version 0.5.0 (`__version__`, pyproject, uv.lock) before the gate's runs.
1. The full suite passes (CI on the candidate).
2. The golden charts against v0.4.0 (the tag, `/dev/shm/golden-old`), `--rerun drums,bass,sections` on both sides,
   `--expect` the parts M8's orders moved; `report.md` read: the pooled F1@50 per part and level not lower.
3. **Added:** the stress set and the 20-song set against v0.4.0's runs (`v040-stress`, `v040-set20`): `stress.py
   compare` "Regressions: 0"; every adopted rule's bar met again on the integrated candidate (within 0.01 of what its
   merge reported), the CPU line on these runs and the GPU line on M8-02's GPU arms rebuilt at the candidate; the
   feel report read.
4. The full review workflow over v0.4.0...candidate (`.claude/workflows/full-review.js`, with a token budget); its
   confirmed findings fixed.
5. The test song end to end with the gate ok; its preview looked at; the page's new screens seen in Chromium at
   1280x860 and 700 px, light and dark (a stand-in server on a golden folder, as M7-10's review did).
6. The advisor (a different model) reviews the release candidate.
7. **Added, the owner's GPU check** (about 1.5 hours, the release files built locally and installed over his v0.4.0
   with the guide's update line): sooth (his file), ntl, tod, pm2 (his audio) and the test song charted on his GPU
   with the defaults, with `memory=12GB` in his `.wslconfig` if he agrees (the friend's 16 GB case). The orchestrator
   reads their report.json and pipeline.json: the sections' memory figures against M8-05's line (and its banner if
   one fell back), the adopted GPU-line rules' counts against M8-02's numbers (opens, repeats, HOPO and tap shares,
   the takes' picks), the grid records and tempo maps against a CPU chart of the same files; he looks at the page on
   his Windows browser (Best or Quick, the flags and the lightbox, the re-estimate, the queue if built) and listens to
   one chart.
8. **Added, the play test:** the owner plays sooth and one ordinary song of his; the friend's play test with M4-08
   part B's charts if it has come back by then (PROGRESS `in_flight`), whose diagnostics also time the 4070 for the
   page's estimate.
9. The owner approves the release; he publishes, and the friend gets the guide's update line.

## 10. What the owner is asked for, in order

1. **At v0.4.0's gate check** (already planned: ntl, sooth and a tap song re-charted on his GPU): also send the
   sections stage's memory figures of those charts, read from each chart's `pipeline.json` by a command the
   orchestrator gives him that prints numbers only (pipeline.json holds home paths): the sections stage's
   `child_peak_rss_mb`, `peak_rss_mb.self`, `torch_peak_vram_mb`, `max_gpu_used_mb`, `min_available_ram_mb` and
   `max_swap_used_mb`, and the decode stage's samples (the length); his WSL's memory setting; and one question: does
   the friend's PC have 16 or 32 GB of RAM (M8-05's parts 3-4 are a must at 16 GB, a nicety at 32). **5 minutes.** For
   M8-05 (section 6).
2. **After v0.4.0 is published: M8-01's GPU takes** (eval/README.md, "GPU takes with the installed app"): copy the
   packages and the two lists, `eval/gpu.sh build --app refs|stress|set20`, `check --app`, `takes --app refs stress
   set20`, then send `gpu_results.zip`. **About 30 minutes of his time and 2.5-8.5 hours of his GPU, unattended**
   (the README's estimate: the references 0.5-2 h, the stress set 0.5-1.5 h, the 20-song set 1.5-5 h). Every GPU-line
   order waits on it.
3. **Optional, after M8-02 part D: the thinning spike** (M8-11, `eval/gpu.sh thin-spike` on his sooth file): **2.5
   hours of his GPU**, plus about 1 hour for the references if an arm wins. Recommended only if part D finds the GPU
   takes' fast windows thin (recall at 100 ms under 0.7 where the humans play 8 or more notes a second).
4. **Decisions, only if M8-02's numbers raise them:** (a) the 4-take default, if 4 spliced GPU takes beat one by
   under +0.005 (the cost is about 3-10 minutes a song on the friend's 4070, by the page's estimate; recommended:
   keep 4 unless the splice is no better than one take at all); (b) a device-scoped rule (decided here: allowed and
   recorded; he may veto it).
5. **v0.5.0's gate:** his GPU check (about 1.5 hours with the update), the play test (two songs), his approval and
   the release.

## 11. Decisions taken here, and their reasons

1. **The GPU line is measured before anything is built on it**, with M7-01's bars, on the owner's takes of the 23
   songs; the CPU's closed answers are reopened only where the GPU's numbers say so.
2. **M8-02 builds at the v0.4.0 tag's code**, so wave 1's merges do not move its arms; the build orders re-measure
   their bars on their branches.
3. **The halved grid's outro stays a warning** (section 2).
4. **A rule may be device-scoped** when the CPU arm says so (section 4).
5. **allin1's chunk rule reads the song's length only**, never the free memory, so a song charts the same on every PC
   (CLAUDE.md: deterministic); a skip for memory, if chunks fail their bar, reads WSL's configured memory and swap,
   fixed per PC, never the moment's free memory.
6. **The UI pass builds items 5-8 and 10 and the gate's two notes; the queue after a design note**; reading Clone
   Hero's settings is left out (section 7).
7. **Engine settings change only through M8-11's bar and its references' arm**; nothing else touches the engine.

## 12. Usage and cost

At the costs in section 2, every order built and the plan's advisor come to about 30-45 % of the new week, and the
gate (its full review workflow, the advisor, the golden, stress and 20-song runs) another 10-15 %: 40-60 % in all.
With the conditional orders that miss their bars dropped, likely 30-45 % with the gate. By wave: wave 0 (the advisor,
M8-03) 3-5 % of this week's meter, before the reset; wave 1 (M8-04, M8-05) 8-11 %; wave 2 (M8-08, M8-09, M8-10) 7-11 %;
M8-02 5-7 %; wave 3 (M8-06, M8-07) 5-11 %; M8-11 1 %. The orchestrator reads the
meter before each wave and before each builder (PIPELINE, Usage); the owner's limit is 90 % of the week from the reset
on. If the meter runs short, the order of priority is: M8-02 (the version's point), M8-05 (a silent failure on the
friend's PC), M8-04, the GPU-line builds that cleared, M8-08/M8-09, M8-10, M8-11.

## 13. Done for this version

- M8-02's and M8-03's reports committed (`docs/reports/M8-02-measure-gpu.md`, `M8-03-measure-cpu.md`; numbers only,
  s01-s13 labels), their scripts under `eval/m8/`; every build order built and merged, or closed with its numbers in
  `dead_ends`.
- Every merged order's "Done means" passes and CI is green on `main`; the release gate of section 9 holds.
- PROGRESS: M8 "built" at the gate, "done" when the friend has the release; M5-99 gains what M8 deferred.

## 14. The advisor's review (2026-11-08) and what changed

The advisor (a different model) read the plan at c3dab2b with the code its orders name and the kept folders' records
(no job run). **Verdict:** ready for wave 0 and wave 1 with three text changes (findings 4, 5 and 9); findings 1, 2,
3, 6 and 7 before M8-02 starts. Nothing changes the scope, the waves or the owner's asks; no finding needed a skeptic.
The orchestrator had findings 1-7, 9 and 11 applied, as follows:

| # | finding | what changed |
|---|---|---|
| 1 | M8-07 (b)'s floor reached the bass, which M8-02 C-c never measures | **(b) is the guitar's only** (the planner's call): the bass is our CPU rule engine, the same chart on both devices, and M7-01 A-c measured its floor on the CPU charts inside noise (300 ms: +0.016 [-0.019, +0.047]); nothing about the GPU reopens it, so no bass line goes into M8-03. M8-02 C-c, M8-07 (b) and section 4's table say so |
| 2 | the open-notes CI may rest on too few songs | under 8 songs with GPU opens the bar is the pooled +0.005 with no song's exact-lane down and the contour not lower on any song, and (c) is then built GPU-only as a trial the owner may veto (his ask 4b); the CPU charts' few opens make the rule a GPU rule in effect (M8-02 C-d, M8-07, section 4) |
| 3 | best-of-N: about 25 take candidates against one 95 % CI | M8-02 B names its primary candidates before any number (L1 at p 0.6, D1 at its 10 % rule, q05); every other one is exploratory and clears only with the CI's lower end at +0.002 as well; part C reports how many candidates each winner came from (M8-02, M8-06, section 4) |
| 4 | M8-03 A-c's whole-song reproduction must be on short songs | break (3:13) and creep (4:00); no whole run of a long song (its outputs and peak come from the kept folders' records); the advisor's line (346 MB + 17.5 MB a second on 23 kept folders) recorded beside the planner's; A-b's test song only when the free RAM allows, else break |
| 5 | M8-04's re-estimate read as if a take event carried seconds | the first take's seconds are `at` of the second take's event less the first's (jobs.py stamps every event); a 1-take chart has the guitar's `stage_end`; no `pipeline.py` change (M8-05's file in wave 1) |
| 6 | a device-scoped rule on a chart with a CPU retry | the rule follows the chart's configured guitar device, recorded as `rules_device`, never per take (M8-07, section 4) |
| 7 | M8-02 C's CPU comparison from M7-01's tables | from the tag's `cpu_m05` and CPU `one` arms that part B builds, part C's variants built on their configs too |
| 9 | the free-disk variable in every brief | every order carries an Environment line with `SONGCHARTER_HEAVY_MIN_FREE_GB=1` (section 3) |
| 11 | the owner's first ask | reads `pipeline.json`'s sections stage (its six memory fields and the length) by a print of numbers only, and asks once whether the friend's PC has 16 or 32 GB of RAM (section 10) |

Also taken, as a note (finding 10): if chunks miss their bar, M8-05's report says plainly that a 16 GB PC charts songs
over about 7 minutes without allin1. Findings 8 (the assemble route, the zip's device fields and the under-0.6 list
verified), 10 (chunking by length is the right lever; the skip's dependence on the PC's configured memory is the
install rule's own) and 12 (the usage estimate a generous upper bound) are notes that change nothing.
