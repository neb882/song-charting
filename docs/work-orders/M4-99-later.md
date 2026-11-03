# M4-99: later (v0.2 and on)

**Nothing to build in v0.1.** These were scoped out of v0.1 by the orchestrator, or deferred by the M4 plan. Each
line says what it would take, for the planning of v0.2. Every item that changes a chart goes through the golden
charts.

## Deferred by the scope decision

- **The interactive highway preview** (DESIGN 4.5 screen 4): notes from scan-chart's parse, `song.ogg` as the clock,
  beat and measure lines, section jumps, 0.5× and 0.75× speed, and the review flags.
  - `scan.cjs --notes` already returns every parsed note (assemble's gate uses it), so a route can serve them.
  - The page needs a canvas highway synchronised to an `<audio>` element.
  - About 2–3 days. Acceptance: notes within one frame of scan-chart's ms times (DESIGN 5, M4).
- **The metronome:** WebAudio clicks scheduled from the tempo map's beats in ms (read from `notes.chart` with
  `importers.read_chart`), against the same audio clock. Half a day once the highway exists. Acceptance: clicks and
  beat lines line up audibly and visibly.
- **The quick fixes** (DESIGN 4.5 screen 5): shift the downbeat by ±1 beat, nudge the global offset in ms, set the
  first beat.
  - Needs new assemble config keys that re-map the existing Expert notes by ticks, then recompute star power,
    activation lanes, sections, solos and the lower tiers.
  - An offset nudge also re-pads `song.ogg` and reruns `verify_sync`.
  - About 2 days with tests and a golden-chart run.
- **×2/÷2 and time-signature edits:** rerun the note stages with the tempo level forced (minutes for guitar).
  Denominators other than 4 need `tempo.py` work, which is M5's ("6/8 and odd meters"). 2+ days.
- **The polish workspace:**
  - the stems under names Clone Hero does not load, kept out of the install and the zip (critique G11);
  - a one-page Moonscraper guide;
  - a "Re-check & re-install" button that runs assemble's gate on the edited folder.

  About a day.
- **"Preview in Clone Hero":** `"Clone Hero.exe" --song <folder> --player Guitar,Expert` (documented CLI [doc,
  untested]). It needs Clone Hero's install path (asked once, like the Songs folder) and a check on the owner's PC.
  Half a day.
- **Code signing:**
  - SignPath Foundation (free for OSI-licensed open-source projects: needs M4-00 open question 2 answered with an OSI
    licence), or Azure Artifact Signing (individuals in the US or Canada; DESIGN 9, Q10);
  - then sign `setup.exe` in CI.

  The owner's decision first; then about a day of setup.
- **The weekly cu132 job:**
  - a scheduled CI job installs the real cu132 lane (2.1 GB) on the GPU-less `windows-latest`;
  - proves that torch imports, that `doctor` reports "CUDA did not run" or "no NVIDIA GPU" with the CPU chosen, and
    that the clip still charts on the CPU (DESIGN 4.6).

  Half a day. The 14 GB SSD fits the lane [doc: runner table].

## Deferred by the M4 plan

- **Clone Hero's `settings.ini`:** read its song-folder keys once M4-08 has recorded them (A9), and prefer them over
  `Documents\Clone Hero\Songs`. An hour.
- **Time estimates in the progress rows** (DESIGN 4.5): v0.1 shows elapsed times. Estimates per stage from the
  machine's own earlier `pipeline.json` files (seconds per audio second, per device). Half a day.
- **The tempo option** (auto / constant / follow the band) **and the chord-density slider** of DESIGN 4.5's
  options: the command line has neither, so they need pipeline and assemble options first (M5 territory).
- **A window-free launcher:**
  - v0.1's server runs in a console window the friend keeps open;
  - `pythonw` with a small tray icon (or a minimised window) and a "Quit" button in the page.

  A day.
- **CUDA for the guitar on native Windows:** only if WebGPU disappoints in M4-08.
  - onnxruntime-node's Windows build has no CUDA provider, so it would mean building onnxruntime-node from source
    with CUDA on Windows (MSVC, the CUDA toolkit, cuDNN), shipping that build, and fetching the CUDA and cuDNN DLLs
    from NVIDIA's redistributable wheels.
  - Several days, plus the redistribution terms to check.
- **Smart App Control instructions:** written once M4-08 has seen what SAC does on a real PC (DESIGN 4.4 step 3).
- **An update check:** the page compares its version with the latest GitHub Release (if releases are the channel)
  and links to it. Half a day.
