# M5 plan: songcharter v0.2.0, the version after the friend's v0.1.0

*Written 2026-11-05 on branch `m5-plan` from `main` at c8bd01c by the planner (docs/PIPELINE.md, Gates: a fresh
agent that reads only the repository and the owner's goals). The advisor reviews it next; the orchestrator runs the
waves. Evidence tags follow DESIGN.md: [code] read from this repository, [here] measured on the dev machine or
recorded in PROGRESS, [inference], [decision] a choice made here, [owner] a choice that is the owner's to make,
with a recommendation.*

## 1. What this version is

The owner tested v0.1.0 on hard songs on 2026-11-05 and asked for the next version to start with what he found
(PROGRESS `deferred`, `docs/work-orders/M4-08-results.md`). The friend is testing v0.1.0 meanwhile (M4-08 part B,
in flight). This version makes charts of fast, long and instrumental songs right where v0.1.0 gets them wrong, tells
the user when the guitar ended early, retries a GPU failure, adds album art and a background (M4-11, built on
`m4-11-art`), tells him when a new version is out, and clears the polish the owner saw. Everything that moves a
chart is judged on the golden charts and on a new repeatable check against human charts of the two hard songs.

**The version number: 0.2.0** [decision, the owner can overrule]. The charting path changes in four places (the
grid's tempo octave, the chord guard, the guitar continuation, the solo caps), charts of the same song change on
purpose, and the user sees new features (art, the update notice, the CPU retry). A 0.1.1 would read as a patch;
the friend's install path does not care (`app/<version>`).

## 2. Scope: the orders

| order | name | one line | size |
|---|---|---|---|
| M5-09 | [stress-eval](M5-09-stress-eval.md) | the two hard songs as a repeatable check outside the repository (their human charts from Chorus Encore, a golden-style run, scores against every human chart, per-30-s-window F1, a timing-only lyrics check), with the baseline numbers committed | 1 day |
| M5-01 | [fast-grid](M5-01-fast-grid.md) | the grid's tempo octave chosen from note density (a second `beat_grid` pass at twice the tempo, with the fold range as a parameter), and no chord made of notes distinct in time | 1.5 days |
| M5-02 | [long-songs](M5-02-long-songs.md) | a guitar take the engine cut short (8,192 tokens or 1,280 beats) is continued from where it stopped and stitched; the user is told | 2 days |
| M5-03 | [solos](M5-03-solos.md) | a solo's longest length and the solos' largest share of a song, from the human charts; the densest parts of a long "Solo" run win; the preview draws the solos | 1 day |
| M5-04 | [lyrics-warning](M5-04-lyrics-warning.md) | the "alignment is unsure" warning calibrated on the references' stems and mixes and the power-metal song, with a statistic chosen by margin | 1 day |
| M5-05 | [gpu-retry](M5-05-gpu-retry.md) | a guitar take that fails on CUDA is run again on the CPU, once per chart, recorded as a fallback (the skeptic's option b) | 1 day |
| M5-06 | [names](M5-06-names.md) | "Artist - Title" read from the file name; folder names cut at a word (the library folder up to 80); a song too short or silent refused cleanly | half a day |
| M5-08 | [install-polish](M5-08-install-polish.md) | the hub's warning, npm's warnings and the download bars silenced; a "done" line after every download; the install's closing summary before the WSL restart; torchaudio in doctor; a noise check in CI | 1 day |
| M5-07 | [updates](M5-07-updates.md) | the page's update notice with the new install line and a Copy button; the update path (0.1.0 installed, then the new line over it) tested in CI | 1.5 days |
| M4-11 | art (on `m4-11-art`) | album art and a background image; not re-planned here: it is reviewed and merged first (wave 0) | built |
| M5-99 | [later](M5-99-later.md) | what waits, with its reason: the engine thinning fast runs, the halving rule, the 20-song set, the one-click updater, the tempo control, the lyrics' 50 ms share, the small deferred items | — |

**Left out of this version, and why** (M5-99 has the detail):
- **Fast runs thinned by the engine** (the owner's finding 3): the engine's decoder sets the density; every lever
  (its descriptor knobs, its inpaint model, sampling, takes) is unmeasured and needs GPU hours per setting. M5-01
  recovers the larger loss on fast songs; M5-09's per-window scores make the M6 spike measurable.
- **The reference set at 20 or more songs:** M5-09 makes a song one entry and a build; the songs are the owner's to
  pick [owner], and 13 songs cost about 3 hours and 16 GB on the dev machine. Not needed for this version's
  decisions, which fix measured defects and are judged for regression on the seven.
- **A one-click updater:** the notice first (M5-07); the updater would need a detached install that survives the
  server's own restart, about two days.
- **The tempo control on the page**, the halving rule, the lyrics' 50 ms share, the small deferred items (M5-99).

## 3. Waves and their dependencies (at most two builders at once)

| wave | orders | why together, and what they must not touch |
|---|---|---|
| 0 | **M4-11** reviewed and merged into `main` [owner: it was held until a v0.1.1 was approved; now the next version is approved] | every later order touches its files (pipeline.py, assemble.py, server.py, app.js, jobs.py, cli.py) |
| 1 | **M5-09** ∥ **M5-01** | `eval/` and its tests ∥ `beatgrid.py`, `quantize.py`, `assemble.py`. M5-09 merges first; M5-01's final numbers use it (until then the scratch folders) |
| 2 | **M5-02** ∥ **M5-03** | `engines/autochart.py`, `engines/stitch.py`, pipeline.py's guitar-stage warnings, one line of `eval/golden.py` ∥ `starpower.py`, `preview.py` |
| 3 | **M5-04** ∥ **M5-05** | `engines/lyrics.py` and one warning line of pipeline.py ∥ pipeline.py's guitar stage, cli.py, app.js's take line. M5-04 merges first (both touch pipeline.py, in different functions) |
| 4 | **M5-06** ∥ **M5-08** | pipeline.py's metadata, cache.py, ui/jobs.py ∥ runtime.py, launch.py, device.py, install.sh, 30-install.sh |
| 5 | **M5-07** | server.py, app.js, index.html, updates.py, 75-update.sh: alone, since it reaches into the page and CI |
| then | the release gate (section 6), the advisor on the release candidate, the owner's PC, the friend | |

- Every order branches from `main` after the wave before it has merged; the orchestrator rebases a branch that
  started earlier. Parallel orders do not edit DESIGN's shared sections, PROGRESS or README beyond what their order
  names; the orchestrator folds reports in at each merge (PIPELINE).
- The golden runs (M5-01 with `--rerun drums`, M5-02 with `--rerun guitar`, the rest cheap) and the stress runs are
  heavy jobs: one at a time through `tools/heavy.sh`, which the orders' builders queue behind each other. Wave 2's
  two golden runs cost about 3 hours of machine time in all; plan the wave for it.
- Disk: the stress set adds about 3 GB (kept folders and stems). M5-09 refuses to start under 8 GB free; the
  orchestrator clears old scratch folders before wave 1 (`df -h` in each merge report, as PIPELINE asks).

## 4. The evaluation plan

Every order that changes the charting path says what the golden charts may show and what the stress check must
reach; the numbers are in the orders. In short:

| order | golden (`eval/README.md`'s commands, from the order's checkout against `main`) | the stress set (M5-09; 1 CPU take, against M5-09's baseline run of `main`) |
|---|---|---|
| M5-01 | `--rerun drums` both sides (beatgrid.py is in `ENGINE_FILES["drums"]`), `--expect none`; the chord guard may move a few notes, then named parts, no F1 lower | the power-metal song: grid 190-206 BPM, chord share < 0.10, merged < 5 %, guitar F1@50 ≥ 0.70 against each of three charts (0.58-0.59 at 4 takes today), bass and drums not lower, timing error < 25 ms, beat F1 ≥ 0.80; the shred instrumental not lower |
| M5-02 | `--rerun guitar` both sides, `--expect none`: byte-identical takes (no reference reaches the budget) | the shred instrumental: last note ≥ 530 s, the last 60 s F1@100 ≥ 0.60 (0 today), whole-song F1 not lower, no doubled or missing note at the seam; every other song one engine run |
| M5-03 | `--expect guitar` on the named songs; onsets identical everywhere (solos only) | solos ≤ 3, each ≤ the cap, together ≤ the share; an overlap with a human solo |
| M5-04 | `--expect none` (no lyrics in golden) | the lyrics check: ≥ 90 % within 250 ms and no warning on the power-metal song and two references; the full-mix runs warn |
| M5-05, M5-06 | `--expect none` (cheap runs; paths the golden never takes) | — |
| M5-07, M5-08, M5-09 | no charting path (M5-09: the golden summary identical to the baseline's hashes) | M5-09 makes the baseline |

**The quality measure against human charts** is `eval/scorer/score.py` through M5-09's `stress.py score`: F1@50
and F1@100 per part against every human chart of a song, with the humans' agreement beside it as the ceiling
(0.73 / 0.93 between the shred instrumental's two charts at 50 / 100 ms [here]), chord share, timing error, beat F1
plain and octave-tolerant, the 1-s density peak and the lowest 30-s window. The golden set's seven songs guard
against regression; the stress set shows the gain. The owner's 4-take figures of 2026-11-05 are the motivation, not
the baseline: the dev machine compares 1-take CPU charts with 1-take CPU charts.

**The release gate's golden run** compares the release candidate with v0.1.0's checkout with `--rerun
drums,guitar` on both sides (about 2 hours) and `--expect` naming the parts the version meant to move: `guitar` on
the songs M5-03 changed, and whatever M5-01's guard moved; everything else UNEXPECTED.

## 5. Risks

| # | risk | caught by | plan |
|---|---|---|---|
| 1 | The octave rule doubles a reference song's grid wrongly, or fails to double the power-metal song | M5-01's threshold table (a margin under 2x stops the order); the golden diff; the stress check | the drums' evidence at the doubled tempo must not fall by more than 0.10; a config override `grid_octave`; the halving case is left alone |
| 2 | The continuation's seam doubles or loses notes, or a piece runs forever | M5-02's seam test and the stress check; `MAX_PIECES` and the 20-s rule | the whole-song path stays byte-identical; the pieces are kept on disk for inspection |
| 3 | The CPU retry on the friend's 12 GB WSL is killed for memory beside the parent's CUDA context | the gate's hardware check (A23 under `memory=12GB`, the memory samples) | `stopped`'s advice as in v0.1; the default off for WSL if swap passes 4 GB [owner at the gate] |
| 4 | The solo caps hide a real long solo | M5-03's human-solo table sets the caps from the data; the overlap check | `names` (a person's sections) bypasses the caps |
| 5 | The update check slows startup or leaks something | M5-07: the check runs after the first page, 5-s timeout, once a day, User-Agent only; CI with a local JSON | silent on any failure; `SONGCHARTER_OFFLINE` never fetches |
| 6 | GitHub's unauthenticated API limit or a changed release layout | one request a day; the SHA256SUMS asset is build.sh's | the notice shows the release page without a line |
| 7 | The upgrade test in CI needs the v0.1.0 tag and Docker time | the hook fetches the tag itself; it reuses 70-release.sh's server | about 10 minutes more in CI; one line in ci.yml if the fetch cannot be done from the hook |
| 8 | Two heavy golden runs in wave 2 and the stress set's disk fill the dev machine | `tools/heavy.sh`'s lock and 5 GB floor; M5-09's 8 GB floor; `df -h` at every merge | the orchestrator clears old scratch before wave 1 |
| 9 | M4-11's merge conflicts with wave 1 | wave 0 first; every order branches after it | |
| 10 | The friend's part B results arrive mid-version and ask for a fix | the orchestrator reads them at any merge | a fix order joins the nearest wave; a part B failure on the install blocks the release until fixed |

## 6. The release gate for this version

PIPELINE's gate, in its order, plus what this version adds:
1. The full suite passes.
2. The golden charts against v0.1.0's checkout, `--rerun drums,guitar` both sides, `--expect` as section 4 says;
   `report.md` read: the pooled F1 per part not lower than v0.1.0's on any part.
3. **Added:** the stress check (`stress.py compare` of the baseline and the candidate): every F1@50 at least the
   baseline's − 0.01 on every song and part, and M5-01's, M5-02's and M5-03's pass lines met; the lyrics check on the
   power-metal song with no warning.
4. The full review workflow over the integrated release; its confirmed findings fixed.
5. The test song end to end with the gate ok; its preview looked at, the solos and the art included.
6. **Added:** CI green with 75-update.sh (the update path) and 30-install.sh's noise check.
7. The advisor reviews the release candidate.
8. **Added, the owner's PC** (about two hours, the real paths this version changes): the new line pasted over his
   v0.1.0 install (the update as the friend will do it; the install's last lines quiet, the summary rule); the two
   hard songs charted with the defaults and their previews looked at (the power-metal song's chord share and tempo,
   the shred instrumental's ending and solos); one provoked GPU failure during a take under `memory=12GB` (M4-08's
   A23) with the CPU retry's memory samples; the update notice seen once the release exists (or with
   `SONGCHARTER_RELEASES_URL` at a file); the diagnostics zip checked as M4-08's A24 says.
9. The owner approves the release; the friend gets the link with the guide's update line.

Part B's results, if they have arrived, are read before step 8: anything they ask for joins the fix list.

## 7. Questions for the owner

1. **The version number:** 0.2.0 (recommended, section 1) or 0.1.1. [owner]
2. **M4-11 merged into `main` as wave 0** now that the next version is approved (its order held it until "a v0.1.1
   is approved"). Recommended: yes. [owner]
3. **The update notice over a one-click updater** (M5-07 builds the notice; M5-99 says what the updater adds).
   Recommended: the notice. Also: does a pre-release count as "a new version" for the notice while songcharter is
   under 1.0 (recommended: yes, since v0.1.0 is one)? [owner]
4. **The CPU retry on by default** (M5-05; recommended: on, with the gate's memory check allowed to turn it off for
   WSL). [owner]
5. **The reference set's growth:** which songs, if any, join the stress set in this version (M5-09 takes any Chorus
   Encore md5; recommended: the two hard songs now, more in M6 when you pick them). [owner]
6. **The lyrics weights at install** (1.26 GB more to download, deferred since M4-10): still first use (recommended,
   unchanged) or at install. [owner]

## 8. Done for this version

- Every order's "Done means" passes and CI is green on `main`; the release gate of section 6 holds; M4-11's checks
  pass on the integrated version.
- PROGRESS: M5 "built" at the gate, "done" when the friend has the release and his report is read; the deferred
  items each order closes are removed, and M5-99's stay with their reasons.
