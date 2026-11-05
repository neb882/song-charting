# M5-99: later (the version after this one)

**Nothing to build in this version.** Each item says what it would take and why it waits. Every item that can move
a chart goes through the golden charts and the stress set (M5-09).

## Fast runs thinned by the guitar engine (the owner's finding 3)

- **What is known** (PROGRESS, 2026-11-05, the shred instrumental, 4 CUDA takes): the chart's total is near the
  human charts' (2,137 Expert notes against 2,236 and 2,382), but it peaks at 11 notes a second where both humans
  reach 17, and runs at about 7 a second through 10-second stretches the humans chart at their peak; 47 % of the
  human notes found in passages at 8-12 notes a second against 92 % in the slow first two minutes. The engine is a
  black box whose sampled decoder sets the density; songcharter's stages after it only quantize.
- **The levers, all unmeasured:** the engine's descriptor knobs (the job's `knobs`, with `guidanceScale` 2 and
  `knobsActive`: a speed or density descriptor conditions the decoder; DESIGN 2.7 lists them unused); the inpaint
  model (`job.inpaint` with `regions` and 4 candidates scored at the seams: regenerate a thin window with the
  context on both sides); sampling (T 0.95 / top-p 0.98 are the app's "Standard" preset); more takes, though the
  splice chooses by agreement, which favours the thinner consensus.
- **Why it waits:** every lever needs GPU time to measure (4 takes of a 9-minute song are about an hour on the
  owner's card per setting; the dev machine is CPU-only) and a per-window score, which M5-09 adds. Fixing the
  grid's octave (M5-01) recovers the larger loss on fast songs (the power-metal song's recall 0.45 against the
  engine's own 2,085 notes); the thinning costs the shred instrumental about 0.2 of its notes in its fastest fifth.
- **The spike for M6** (the owner's GPU, `eval/gpu.sh takes`' manner): the shred instrumental with the density knob
  at two settings and T 1.05, 4 takes each, scored per 30-s window; the inpaint path on the three thinnest windows.
  Adopt a setting when the fast windows' F1@100 gains 0.10 with no window losing 0.02 and the references' pooled
  F1@50 unchanged; else record the dead end.

## From the charting-conventions report (`docs/reports/charting-conventions.md`), not taken up in this version

Its ranked gaps 1-3, 5 and 6 are M5-01, M5-02 and M5-03; part of 9 and 10 are M5-04, M5-06 and M4-11. The rest:
- **HOPO, strum and tap states independent of the octave** (gap 4, section 2f): `hopo: "forced"` leaves every
  unforced note to the natural rule on our map, so the played articulation follows our octave. The convention
  reproduces the articulation: the state on the source's own map, written with `N 5` flips. `assemble.HOPO_RULES`
  already has `"source"`; M5-01 measures both on the stress set (HOPO shares against the humans' 0.51 and 0.55).
  DESIGN C10 chose "forced" because autochart's own map can be at the wrong octave too; the decision needs those
  numbers and a HOPO-agreement metric in `score.py`. Half a day to decide, a day to build with the bass engine's
  state rule in time rather than ticks.
- **1/32 and 1/24 burst slots** (gap 2's second half): M5-01 drops a distinct note rather than make a chord when its
  slot is taken, and counts it (`dropped_distinct`); over 1 % of a part's notes on the stress set means the quantizer
  needs the finer levels. A day, with the slot priors re-measured (DESIGN 2.6).
- **Fret-quality metrics and repeat consistency** (gap 7, section 2b): exact fret agreement (16-27 %, humans 46 %
  with each other) is the wrong target; score contour, same-pitch-same-fret within phrases, repeated riffs charted
  the same way, and jump sizes against the humans; then reuse one take across repeated riffs (found by section
  labels and self-similarity). The metrics are a day in `score.py`; the reuse is M6's and needs the larger set.
- **Section names:** Rock Band's "Guitar Solo" for a solo section; it changes the names people pass to `--solos`
  ("Solo 1" on the test song). An hour, with the guide.
- **The song folder** (gap 10, section 8): `song_length` (Encore requires it, the Clone Hero wiki advises against
  setting it by hand), `diff_band` (DESIGN 2.12 plans it), report.json in the folder (an extra file Encore would
  flag; Clone Hero ignores it), the album placeholder (M5-06). An hour each, with the owner's say on report.json.
- **Lyrics** (gap 9, section 7): syllables from the aligner's character timings, so a long word does not light all at
  once; Harmonix's punctuation and capitalisation conventions. A day.
- **Drums** (section 3): the 2x-kick phase (alternate on the grid, not from the run's start), lane accuracy, roll
  lanes, accents, ghosts, the disco flip. The friend plays guitar.
- **Star power** (section 4): phrases that end on a sustain; phrases lined up across instruments for YARG's unison
  bonus.
- **Stems in the folder** (section 11 item 6): an option, not a rule; a new audio path.
- **DESIGN's contradictions** (the report's section 11, ten items): fold the resolved ones into DESIGN at the doc
  pass that follows this version (task 41's restructure), each with the report as its source.

## The grid at double the humans' tempo

The shred instrumental's grid came out at twice the human charts' tempo (octave-tolerant beat F1 0.94-0.96).
M5-01 doubles a grid that is too slow and never halves one. A halving rule needs its own statistic (the share of
onsets on beat lines, the HOPO shares: ours 0.40 against the humans' 0.55 there) and a check that the natural HOPO
threshold (in ticks) still reads right; measure on the stress set first. Half a day to measure, a day to build.

## The reference set at 20 or more songs, with human-charted solos

PROGRESS `next`. M5-09 makes adding a song one entry in `stress.json` and a build; the cost on the dev machine is
10-18 minutes cold and about 1.2 GB per song (kept folder and stems), so 13 more songs are about 3 hours and 16 GB
on a machine with little room. The songs are the owner's to pick [owner] (fast, 6/8 and shuffle, drumless, long,
live); until then the stress set holds the two from 2026-11-05.

## A one-click updater

M5-07 builds the notice. A button that runs the update would need: the server starting `install.sh` detached from
itself (the install restarts WSL at its end, which kills the server), `--yes` for the licence prompt (the guide's
link must then be shown on the page), the install's log streamed to the page and kept when the window closes, the
Start-menu shortcut's rewrite (the install does it), and the page reopening on the new version. About two days,
and new ways to fail half-way that the pasted line does not have. The notice first; the updater if the friend
finds the line a nuisance.

## The tempo control on the page

M5-01 adds `grid_octave` to the assemble config. A `--grid-octave` CLI flag is an hour; a page control that
re-assembles a finished chart at x2 or /2 without running the engines again (the cache answers; only assemble and
the preview rerun) is a day, with the quick fixes of M4-99 (the downbeat and the offset nudge) beside it.

## Lyrics

- The 50 ms share: 0.45 pooled on the references, 0.68 on the power-metal song, where the humans agree 0.94 with
  each other. The 20 ms emission grid, the star tokens and the syllable spread are the places to look; M5-09's
  timing script measures it. A day to measure.
- Non-Latin scripts (no romanization: words spread between neighbours), and the first-use download's progress line
  on the page (the release gate's deferred item). Half a day each.

## Small things from PROGRESS's deferred list, left for later with their reason

- `song.ogg` not byte-identical between runs (the Ogg page serial): a fixed serial through ffmpeg's bitexact flags;
  an hour, with the determinism rule's wording in DESIGN 1. Not user-visible.
- autochart's engine reports no memory peak of its own; each take's `expert_job.json` says `executionProvider`
  "cpu" while it ran on CUDA: the engine's job file, not ours.
- The 24-hour pruning exemption and a "free the cache" button; the pruning race; Q26 (the grid period to ADTOF);
  the golden charts' blind spot on the separation's code; the separation cache maker as an eval script.
- The cu126 allin1 pairing untested on real hardware; the dev machine's hand-made allin1 Python.
- The lyrics weights fetched at install [owner: install size and time]; doctor not counting a missing torch or
  demucs as a problem.
- The CI personal-details check, stall logs, the builder-effort trial, DESIGN's split by area (the pipeline review's
  deferred findings).
- M4-08 part A's checks not run (A8-A11, A13, A16, A18-A24, Take Me Out) and M4-08a's harness: the release gate of
  this version runs the few it needs (M5-00); the rest before a later release.
- M4-99's list (native Windows, signing, the highway preview, the metronome, the quick fixes, the polish workspace,
  "Preview in Clone Hero", the weekly cu132 job, settings.ini, time estimates, a window-free start, WSL memory
  tuning) stands.
