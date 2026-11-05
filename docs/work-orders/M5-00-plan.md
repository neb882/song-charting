# M5 plan: songcharter v0.2.0, the version after the friend's v0.1.0

*Written 2026-11-05 on branch `m5-plan` from `main` at c8bd01c by the planner (docs/PIPELINE.md, Gates: a fresh
agent that reads only the repository and the owner's goals). Amended the same day, by a second planner, after the
advisor's review (eleven findings and a reading of the feel note; two skeptics confirmed its findings 1 and 7 and a
third partly confirmed finding 2: the amendments are marked in each order) and after the owner's decisions on the
open questions (section 8). The orchestrator runs the waves. Evidence tags follow DESIGN.md: [code] read from this
repository, [here] measured on the dev machine or recorded in PROGRESS, [inference], [decision] a choice made here,
[owner] a choice that is the owner's to make, with a recommendation.*

## 1. What this version is

The owner tested v0.1.0 on hard songs on 2026-11-05 and asked for the next version to start with what he found
(PROGRESS `deferred`, `docs/work-orders/M4-08-results.md`). The friend is testing v0.1.0 meanwhile (M4-08 part B,
in flight). This version makes charts of fast, long and instrumental songs right where v0.1.0 gets them wrong, tells
the user when the guitar ended early, retries a GPU failure, adds album art and a background (M4-11, built on
`m4-11-art`), tells him when a new version is out, and clears the polish the owner saw. Everything that moves a
chart is judged on the golden charts and on a new repeatable check against human charts of the two hard songs and
one ordinary rock song, which carries the feel measures of section 5 beside F1.

**The conventions.** The owner asked that this version rest on how charts are supposed to be made. A research brief
on the community's charting conventions and songcharter's gaps against them was written for this plan
(`<scratchpad>/briefs/charting-conventions.md`, 2026-11-05; the orchestrator commits it as
`docs/reports/charting-conventions.md` in wave 0, with the feel note as `docs/reports/feel.md`, after PIPELINE's
scan for personal details and lyrics, since a report left in the scratch folder vanishes with the container). Where
an order's choice follows a convention, the order states the rule it assumes and marks it **[conventions]**, so the
advisor can check it against the report. Its ranked gaps map onto the orders as follows: 1 (the tempo octave is the
musical pulse, 40-300 BPM: this version builds the doubling half of it), 2 (no chord of notes distinct in time) and
3 (the spacing floors) are M5-01; 5 (the lost ending) is M5-02; 6 (solos on featured lead breaks) is M5-03; 9 is
partly M5-04 (the 50 ms share re-measured on the right grid) and 10 partly M5-06 (the album placeholder) and M4-11
(`background.jpg` and the Clone Hero setting the guide must name: the reviewer checks M4-11 against the report's
section 8); 4 (HOPO states independent of the octave; M5-01 measures it, M5-09 scores it), 7 (fret-quality metrics
and repeat consistency: M5-09 measures, M6 fixes), 8 (the engine's density) and the rest of 9 and 10 are in M5-99
with their reasons. The report's section 11 lists ten places where DESIGN contradicts the conventions; the orders
above resolve five (2.3's fold, 2.6's spacing and merging, 2.10's solos) and the doc pass after this version folds
the rest in.

**The version number: 0.2.0** [decided by the owner, section 8]. The charting path changes in four places (the
grid's tempo octave, the chord guard, the guitar continuation, the solo caps), charts of the same song change on
purpose, and the user sees new features (art, the update notice, the CPU retry). A 0.1.1 would read as a patch;
the friend's install path does not care (`app/<version>`).

## 2. Scope: the orders

| order | name | one line | size |
|---|---|---|---|
| M5-09 | [stress-eval](M5-09-stress-eval.md) | the two hard songs and an ordinary rock song as a repeatable check outside the repository (their human charts from Chorus Encore, a golden-style run, scores against every human chart with the feel measures, per-30-s-window F1, a timing-only lyrics check), with the baseline numbers committed | 1.5 days |
| M5-01 | [fast-grid](M5-01-fast-grid.md) | the grid's tempo octave as the musical pulse, judged by note density and the backbeat (a second `beat_grid` pass at twice the tempo, with the fold range as a parameter; doubling only); no chord made of notes distinct in time (the farther onset dropped, never moved); the spacing floors at 20 ms; HOPO states measured [conventions] | 2 days |
| M5-02 | [long-songs](M5-02-long-songs.md) | a guitar take the engine cut short (8,192 tokens or 1,280 beats) is continued from where it stopped and stitched, a cached v0.1 take too; the user is told | 2 days |
| M5-03 | [solos](M5-03-solos.md) | a solo's longest length in measures and in seconds, and the solos' largest share of a song, from the human charts; the densest parts of a long "Solo" run win; the preview draws the solos | 1 day |
| M5-04 | [lyrics-warning](M5-04-lyrics-warning.md) | the "alignment is unsure" warning calibrated on the references' stems and mixes and the power-metal song, with a statistic chosen by margin against the timing ground truth | 1 day |
| M5-05 | [gpu-retry](M5-05-gpu-retry.md) | a guitar take that fails on CUDA is run again on the CPU, once per chart, recorded as a fallback (the skeptic's option b) | 1 day |
| M5-06 | [names](M5-06-names.md) | "Artist - Title" read from the file name; folder names cut at a word (the library folder up to 80); a song too short or silent refused cleanly | half a day |
| M5-08 | [install-polish](M5-08-install-polish.md) | the hub's warning, npm's warnings and the download bars silenced; a "done" line after every download; the install's closing summary before the WSL restart; torchaudio in doctor; a noise check in CI | 1 day |
| M5-07 | [updates](M5-07-updates.md) | the page's update notice with the new install line and a Copy button; the update path (0.1.0 installed, then the new line over it) tested in CI | 1.5 days |
| M4-11 | art (on `m4-11-art`) | album art and a background image; not re-planned here: it is reviewed and merged first (wave 0) | built |
| M5-99 | [later](M5-99-later.md) | what waits, with its reason: the engine thinning fast runs, the halving rule, the burst slots, the repeat-consistency fix, the 20-song set, the one-click updater, the tempo control, the lyrics' 50 ms share, the small deferred items | — |

**Left out of this version, and why** (M5-99 has the detail):
- **Fast runs thinned by the engine** (the owner's finding 3): the engine's decoder sets the density; every lever
  (its descriptor knobs, its inpaint model, sampling, takes) is unmeasured and needs GPU hours per setting. M5-01
  recovers the larger loss on fast songs; M5-09's per-window scores make the M6 spike measurable.
- **The reference set at 20 or more songs:** M5-09 makes a song one entry and a build; the songs are the owner's to
  pick, and 13 songs cost about 3 hours and 16 GB on the dev machine. For this version the owner chose three
  (section 8); the decisions it makes fix measured defects and are judged for regression on the seven golden songs
  and the ordinary rock song.
- **A one-click updater:** the notice first (M5-07, decided); the updater would need a detached install that survives
  the server's own restart, about two days.
- **The halving rule** (a pulse under 85 BPM stays at double: M5-01 records the backbeat ratio the rule needs), the
  **1/32 and 1/24 burst slots** (M5-01 counts what they would recover), the **repeat-consistency fix** (M5-09 measures
  it if it fits), the tempo control on the page, the lyrics' 50 ms share, the small deferred items (M5-99).

## 3. Waves and their dependencies (at most two builders at once)

The first plan put M5-01 beside M5-09 in wave 1. The advisor showed that M5-01's octave threshold needs the stress
songs' engine charts, which exist only once M5-09's baseline run has made them (the scratch folders hold the owner's
charts after the merge, and their sources are paths on his PC). So M5-01 starts when that run exists, and the second
builder slot carries two orders that need nothing of M5-09 meanwhile.

| wave | orders | why together, and what they must not touch |
|---|---|---|
| 0 | **M4-11** reviewed (against the conventions report's section 8 too) and merged into `main` once its review fixes pass CI [decided]; the conventions report and the feel note committed to `docs/reports/` | every later order touches M4-11's files (pipeline.py, assemble.py, server.py, app.js, jobs.py, cli.py); every order cites the report, and M5-09's feel report cites the note |
| 1 | **M5-09** ∥ **M5-06**, then **M5-05** in the same slot | `eval/` and its tests ∥ pipeline.py's metadata, cache.py, ui/jobs.py (M5-06), then pipeline.py's guitar stage, cli.py, app.js's take line (M5-05, after M5-06's merge). M5-09's builder runs the baseline first and reports when `stress-base` exists; M5-09 merges before wave 2 |
| 2 | **M5-01** ∥ **M5-02** | `beatgrid.py`, `quantize.py`, `assemble.py` ∥ `engines/autochart.py`, `engines/stitch.py`, pipeline.py's guitar-stage warnings (in M5-05's per-seed loop), one line of `eval/golden.py`. M5-01 may start as soon as `stress-base` exists and a slot is free, reading `stress.py` from M5-09's branch until it merges; M5-02 starts after M5-05 has merged. Both compare with the baseline |
| 3 | **M5-03** ∥ **M5-04** | `starpower.py`, `preview.py` ∥ `engines/lyrics.py` and one warning line of pipeline.py's `_lyrics_stage`. Both need M5-01 merged (M5-03 must not touch assemble.py; M5-04 re-measures the 50 ms share on the new grid) and compare with a stress run of their own merge base, not the baseline |
| 4 | **M5-08** ∥ **M5-07** | runtime.py, launch.py, device.py, install.sh, 30-install.sh ∥ server.py, app.js, index.html, updates.py, 75-update.sh. M5-08 merges first (both may set the launcher's environment; M5-07's CI then runs the noise check too) |
| then | the release gate (section 7), the advisor on the release candidate, the owner's PC and the play test, the friend | |

- Every order branches from `main` after the wave before it has merged; the orchestrator rebases a branch that
  started earlier. Parallel orders do not edit DESIGN's shared sections, PROGRESS or README beyond what their order
  names; the orchestrator folds reports in at each merge (PIPELINE).
- The golden runs (M5-01 with `--rerun drums`, M5-02 with `--rerun guitar`, the rest cheap) and the stress runs are
  heavy jobs: one at a time through `tools/heavy.sh`, which the orders' builders queue behind each other. Wave 2's
  two golden reruns and two stress runs cost about 4 hours of machine time in all; plan the wave for it.
- Disk: the stress set adds about 4.5 GB for three songs (kept folders and stems). M5-09 refuses to start under
  10 GB free; the orchestrator clears old scratch folders before wave 1 (`df -h` in each merge report, as PIPELINE
  asks).

## 4. The evaluation plan

Every order that changes the charting path says what the golden charts may show and what the stress check must
reach; the numbers are in the orders. In short:

| order | golden (`eval/README.md`'s commands, from the order's checkout against `main`) | the stress set (M5-09; 1 CPU take, against M5-09's baseline run of `main`, or a run of the order's merge base from wave 3 on) |
|---|---|---|
| M5-01 | `--rerun drums` both sides (beatgrid.py is in `ENGINE_FILES["drums"]`); every reference grid bit-identical (octave 1); the chord rule changes some references (118 same-tick pairs over 20 ms apart, now dropped, not merged; the 20 ms floors change nothing there): named parts, no F1@50 down by more than 0.005 | the power-metal song: grid 190-206 BPM, chord share < 0.10, merged < 5 %, dropped < 0.5 %, dropped_distinct at most the human charts' own figure plus two points (about 8.5 %), guitar F1@50 ≥ the baseline's + 0.10 against each of three charts (the owner's 4-take 0.58-0.59, the humans' 0.92 reported beside it), bass and drums not lower, timing error < 15 ms, plain beat F1 ≥ 0.80 [conventions: scored without octave tolerance], state agreement not lower under the shipped mode; the shred instrumental and the rock song not lower; star-power phrases per minute reported |
| M5-02 | `--rerun guitar` both sides, `--expect none`: byte-identical takes (no reference reaches the budget) | the shred instrumental: last note ≥ 530 s, the last 60 s F1@100 ≥ 0.60 (0 today), whole-song F1 not lower, no doubled or missing note at the seam; every other song one engine run; a cached cut-short take continued (a test) |
| M5-03 | `--expect guitar` on the named songs; onsets identical everywhere (solos only) | solos ≤ 3, each within the measure and the seconds cap, together ≤ the share; an overlap with a human solo; the spans listed for the owner |
| M5-04 | `--expect none` (no lyrics in golden) | the lyrics check: ≥ 90 % within 250 ms and no warning on the power-metal song and two references; the full-mix runs (bad by timing) warn |
| M5-05, M5-06 | `--expect none` (cheap runs; paths the golden never takes) | — |
| M5-07, M5-08, M5-09 | no charting path (M5-09: the golden summary identical to the baseline's hashes) | M5-09 makes the baseline |

**The quality measure against human charts** is `eval/scorer/score.py` through M5-09's `stress.py score`: F1@50
and F1@100 per part against every human chart of a song, with the humans' agreement beside it as the ceiling
(0.73 / 0.93 between the shred instrumental's two charts at 50 / 100 ms, 0.917-0.922 at 50 ms among the power-metal
song's three [here]), and the feel measures of section 5: timing error, chord share, contour, jumps, the HOPO, tap
and sustain shares, per-note state agreement, notes in silence and gaps, star-power phrases per minute, solo share,
beat and downbeat F1, the 1-s density peak and the lowest 30-s window. The golden set's seven songs and the stress
set's rock song guard against regression; the two hard songs show the gain. The owner's 4-take figures of 2026-11-05
are the motivation, not the baseline: the dev machine compares 1-take CPU charts with 1-take CPU charts, and every
pass line that was an absolute number from those figures is now the baseline plus a stated gain.

**The release gate's golden run** compares the release candidate with v0.1.0's checkout with `--rerun
drums,guitar` on both sides (about 2 hours) and `--expect` naming the parts the version meant to move: `guitar` on
the songs M5-03 changed, and whatever M5-01's chord rule moved; everything else UNEXPECTED.

## 5. How a chart should feel

Accuracy against a human chart is a proxy: a chart can score well and still feel wrong. The orchestrator's feel
note (`docs/reports/feel.md` from wave 0; written 2026-11-05 and revised after the advisor's corrections) says what
"feels right" means for a Clone Hero guitar chart in nine parts, how each is measured and where the plan carries it.
The plan carries it in three places: M5-09's feel report (the measures, beside F1, for every chart scored, with the
human charts' agreement with each other as the ceiling), M5-01's pass lines (sync, readability and articulation,
in the sound forms below) and the play test at the gate (section 7).

| # | what the player feels | measured by (M5-09 unless said) | aim |
|---|---|---|---|
| 1 | sync: notes land on what the guitar plays; a note 60 ms off feels worse than a missing one | the matched notes' median timing error against the human charts, the guitar's beside bass's and drums'; `QuantizeReport`'s snap errors. Not against the stem's own onsets with a fixed aim (the onset envelope sits about 22 ms after human beat lines, and two human charts of one song can sit 47 ms apart) | M5-01: guitar under 15 ms (the humans agree at about 9 ms; bass and drums 1-5 ms) |
| 2 | readability: even 16ths look even, a run looks like a run, a chord only where a chord rings | chord share against the human charts; the 1-s density peak; notes snapped by more than a third of a slot (`moved_25ms`) | M5-01: chord share under 0.10 and moving toward the humans' 0.03-0.05 |
| 3 | flow: frets follow the melody's direction, no jumps the hand cannot make at speed | contour agreement (`lane_direction_agreement`; 0.71-0.79 between humans) and the jump-size distribution against the human charts, the rate of 3+-lane jumps under 100 ms. Not against a pitch track: songcharter has none | near the humans' own; a fix only if the measures show a gap (M6) |
| 4 | learnability: a repeated riff is charted the same way each time | repeated-label sections' fret-sequence similarity, against the human chart's own (M5-09 if it fits, else M6) | the fix (one take reused across repeats) is M6's: measure first |
| 5 | articulation: strum what is picked, hammer what is slurred; a wrong state breaks the combo | per-note strum/HOPO/tap agreement on the matched notes (shares alone mislead: one song's three human charts have HOPO shares of 0.21, 0.51 and 0.29); no fixed strum-rate cap (the humans strum the power-metal song's 16ths at 13.3 a second) | M5-01: reported under `forced` and `source`, not lower than the baseline under the shipped mode; the mode decision at the gate if the numbers are clear |
| 6 | shape: density rises and falls with the music; no notes where the guitar is silent, no gaps where it plays | notes in silence (`silent_onsets`) and gaps while the stem plays (`preview.flags`); the density curve against the stem's energy is later | no unexplained gaps or ghost notes |
| 7 | sustains and star power: something to hold and whammy; phrases on memorable lines; solo markers only on real solos | sustain share, star-power phrases per minute (they about double on a doubled grid: M5-01 reports them), solo share (M5-03 caps it) | within the human range; solos a small share |
| 8 | the highway makes sense: beat lines at the felt pulse, measure lines on the downbeat, a lead-in, the whole song covered | beat F1 without octave forgiveness, downbeat F1, first note after 2-3 s, last note near the stem's last onset (M5-02) | M5-01: plain beat F1 ≥ 0.80 |
| 9 | hard in the right way: hard from the music, not from artifacts | no measure of its own: the play test; the artifacts it names are measured above | the owner's and the friend's notes |

## 6. Risks

| # | risk | caught by | plan |
|---|---|---|---|
| 1 | The octave rule doubles a reference song's grid wrongly, or fails to double the power-metal song | M5-01's threshold table (a margin under 2x stops the order); the golden diff; the stress check | the guard set from both grids' evidence on every song, with a stop if it vetoes the power-metal song; a config override `grid_octave`; the halving case is left alone |
| 2 | The octave threshold rests on one positive example (the power-metal song) | M5-01's report says so | the rock song and the references bound the other side; M6's larger set adds examples |
| 3 | The continuation's seam doubles or loses notes, or a piece runs forever | M5-02's seam test and the stress check; `MAX_PIECES` and the 20-s rule | the whole-song path stays byte-identical; the pieces are kept on disk for inspection |
| 4 | The CPU retry on the friend's 12 GB WSL is killed for memory beside the parent's CUDA context | the gate's hardware check (A23 under `memory=12GB`, the memory samples) | `stopped`'s advice as in v0.1; the default off for WSL if swap passes 4 GB [owner at the gate] |
| 5 | The solo caps hide a real long solo, or still allow too much on the shred song | M5-03's human-solo table sets the caps from the data; the seconds cap; the overlap check; the owner sees the spans at the gate | `names` (a person's sections) bypasses the caps |
| 6 | The update check slows startup or leaks something | M5-07: the check runs after the first page, 5-s timeout, once a day, User-Agent only; CI with a local JSON | silent on any failure; `SONGCHARTER_OFFLINE` never fetches |
| 7 | GitHub's unauthenticated API limit or a changed release layout | one request a day; the SHA256SUMS asset is build.sh's | the notice shows the release page without a line |
| 8 | The upgrade test in CI needs the v0.1.0 tag and Docker time | the hook fetches the tag itself; it reuses 70-release.sh's server | about 10 minutes more in CI; one line in ci.yml if the fetch cannot be done from the hook |
| 9 | Two heavy golden reruns in wave 2 and the stress set's disk fill the dev machine | `tools/heavy.sh`'s lock and 5 GB floor; M5-09's 10 GB floor; `df -h` at every merge | the orchestrator clears old scratch before wave 1 |
| 10 | M4-11's merge conflicts with wave 1 | wave 0 first; every order branches after it | |
| 11 | The friend's part B results arrive mid-version and ask for a fix | the orchestrator reads them at any merge | a fix order joins the nearest wave; a part B failure on the install blocks the release until fixed |
| 12 | The rock song's packages lack usable audio, or the owner's file of it is a cover | M5-09's build and its `align` check | the song stays on the package's audio when only the owner's file differs; it is dropped, and said so, only when no package has usable audio |

## 7. The release gate for this version

PIPELINE's gate, in its order, plus what this version adds:
1. The full suite passes.
2. The golden charts against v0.1.0's checkout, `--rerun drums,guitar` both sides, `--expect` as section 4 says;
   `report.md` read: the pooled F1 per part not lower than v0.1.0's on any part.
3. **Added:** the stress check (`stress.py compare` of the baseline and the candidate): every F1@50 at least the
   baseline's − 0.01 on every song and part, the rock song included (the guard against making normal songs worse),
   and M5-01's, M5-02's and M5-03's pass lines met; the feel report read beside it (no measure of section 5 worse
   than the baseline's without a reason the merge report gave); the lyrics check on the power-metal song with no
   warning.
4. The full review workflow over the integrated release; its confirmed findings fixed.
5. The test song end to end with the gate ok; its preview looked at, the solos and the art included.
6. **Added:** CI green with 75-update.sh (the update path) and 30-install.sh's noise check.
7. The advisor reviews the release candidate.
8. **Added, the owner's PC** (about two hours, the real paths this version changes): the new line pasted over his
   v0.1.0 install (the update as the friend will do it; the install's last lines quiet, the summary rule); the two
   hard songs charted with the defaults and their previews looked at (the power-metal song's chord share and tempo,
   the shred instrumental's ending and solos, the solo spans M5-03 listed); one provoked GPU failure during a take
   under `memory=12GB` (M4-08's A23) with the CPU retry's memory samples; the update notice seen once the release
   exists (or with `SONGCHARTER_RELEASES_URL` at a file); the diagnostics zip checked as M4-08's A24 says.
9. **Added, the play test** (the feel note; about 45 minutes): the owner plays three songs in Clone Hero, charted by
   the candidate with the defaults: the ordinary rock song (his own file of it when M5-09's `align` check passed,
   else a reference), the power-metal song and the shred instrumental. For each he answers the feel note's short
   list with times: in sync? readable at sight? does the hand flow? did repeats feel the same? anything unfair
   (overstrums, impossible jumps, ghost notes), and where? The friend plays his own songs with the same list once he
   has the release; his notes count most, since he plays with a guitar controller and the owner on a keyboard. A
   "no" with a time goes to a fix order or to M5-99 with its reason, the owner's call.
10. The owner approves the release; the friend gets the link with the guide's update line.

Part B's results, if they have arrived, are read before step 8: anything they ask for joins the fix list.

## 8. Decisions, and what is left for the gate

The owner left the plan's open questions to the orchestrator on 2026-11-05 ("do what you think is best"); each is
decided here with its reason, and the orders carry the decision.

1. **The version number is 0.2.0:** new features and changes to how charts are made, not a fix release.
2. **M4-11 merges now, as wave 0,** once its review fixes pass CI (its order had held it until "a v0.1.1 is
   approved"; the next version is approved).
3. **The update notice with a Copy button, not a one-click updater** (M5-07; M5-99 says what the updater would
   add); **a pre-release counts as a new release,** since the friend is on one.
4. **The CPU retry of a failed GPU take is on by default,** recorded as a fallback (M5-05); the gate measures its
   memory under `memory=12GB` on the owner's PC and can turn it off for WSL.
5. **The stress set is three songs:** the shred instrumental, the power-metal song, and an ordinary rock song with
   human charts (four guitar charts on Chorus Encore, no lyrics) as the guard against
   making normal songs worse. The owner charted it in v0.1 from his own file; M5-09 checks that his file aligns with
   the human charts' audio (it may be a cover) and reports the result. The seven reference songs stay the golden set.
6. **The lyrics aligner's weights stay a first-use download:** the install stays smaller, and the download already
   resumes and retries.
7. **The album placeholder is "<the song's name> - (Single)"** when the file has no album tag (M5-06): Encore's
   song.ini rule, the conventions report's section 8.
8. **A background smaller than 1280x720 is kept as it is, not upscaled** (M4-11's open question: Encore's guideline
   is 1280x720 or more): Clone Hero scales it to the screen, and upscaling only blurs it.

Left for the gate, with the numbers in hand [owner]:
- **The solo share for songs with vocals** (M5-03's `max_share`, set by the shred chart at about 0.40): the owner
  sees the resulting spans of both hard songs and may want a tighter share where a voice carries the song.
- **The HOPO mode** (`forced`, today's, or `source`): M5-01 reports the HOPO shares and the per-note state agreement
  under both against every human chart; if the numbers are clear, the owner decides at the gate, else M6 (M5-99).
- **The CPU retry's default for WSL** if the gate's memory check shows swap over 4 GB during a retry (M5-05).

## 9. Done for this version

- Every order's "Done means" passes and CI is green on `main`; the release gate of section 7 holds; M4-11's checks
  pass on the integrated version.
- PROGRESS: M5 "built" at the gate, "done" when the friend has the release and his report is read; the deferred
  items each order closes are removed, and M5-99's stay with their reasons.
