# M4-99: later (v0.2 and on)

**Nothing to build in v0.1.** Each line says what the item would take. Every item that can move a chart goes through
the golden charts.

## Native Windows

- **A native Windows release.** The native plan is in this branch's history (commit f9f9377, `docs/work-orders/`
  there), and its findings are in M4-00's appendix:
  - Inno Setup, `bootstrap.ps1`, the per-file autochart check, Windows lanes;
  - the guitar on WebGPU, with a WebGPU spike first;
  - Job Objects for cancel, MAX_PATH handling, Windows CI.
  - **It is blocked on the friend's PC by Smart App Control:** every unsigned DLL, Python module and script must be
    signed or known to Microsoft's cloud.
  - So it needs code signing first (below) and a check of what remains unsigned in the third-party wheels.
  - Several days, after signing.
- **CUDA for the guitar on native Windows:** onnxruntime-node's Windows build has no CUDA provider, so it would mean
  building onnxruntime-node from source with CUDA (MSVC, the CUDA toolkit), shipping it, and fetching NVIDIA's DLLs.
  Only if WebGPU disappoints.
- **Code signing:** SignPath Foundation (free for OSI-licensed projects; songcharter is MIT now), or Azure Artifact
  Signing (DESIGN 9, Q10). The owner decides; then about a day of CI setup. On its own it does not unblock Smart App
  Control: third-party unsigned files remain.

## Deferred by the scope decision

- **The interactive highway preview:**
  - notes from scan-chart's parse (`scan.cjs --notes`), `song.ogg` as the clock, beat and measure lines, section
    jumps, 0.5× and 0.75×, the review flags;
  - a canvas highway driven by an `<audio>` element;
  - 2–3 days. Acceptance: notes within one frame of scan-chart's ms times.
- **The metronome:** WebAudio clicks from the tempo map's beats (`importers.read_chart`) on the same audio clock. Half
  a day after the highway.
- **The quick fixes:** downbeat ±1 beat, the global offset in ms, the first beat.
  - New assemble config keys re-map the Expert notes by ticks and recompute star power, activation lanes, sections,
    solos and the lower tiers.
  - An offset nudge re-pads `song.ogg` and reruns `verify_sync`.
  - About 2 days with tests and a golden-chart run.
- **×2/÷2 and time-signature edits:** rerun the note stages with the tempo level forced. Denominators other than 4 are
  M5's `tempo.py` work. 2+ days.
- **The polish workspace:**
  - stems under names Clone Hero does not load, kept out of the install and the zip;
  - a Moonscraper guide;
  - "Re-check & re-install".

  About a day.
- **"Preview in Clone Hero":** from WSL, `Clone Hero.exe --song <Windows path> --player Guitar,Expert` through
  interop (documented CLI [doc, untested]). Needs Clone Hero's path, asked once. Half a day.
- **The weekly cu132 job:**
  - on `ubuntu-latest`, install the real cu132 lane (3.2 GB) and its CUDA provider;
  - prove that torch imports and the guitar's CUDA provider loads its libraries;
  - `doctor` reports no GPU with the CPU chosen.

  Half a day.

## Deferred by the M4 plan

- **Clone Hero's `settings.ini`:** read its song-folder keys once M4-08 has recorded them (A11). An hour.
- **Time estimates per stage** from the machine's earlier `pipeline.json` files: v0.1 shows elapsed times. Half a day.
- **The tempo option and the chord-density slider** of DESIGN 4.5: the command line has neither yet (M5).
- **A window-free start:**
  - v0.1 keeps a console window open;
  - a tray-style launcher, or a "Quit" button and a server that stops after the page has been closed a while.

  A day.
- **Updates:** a new release reinstalls with the same line, and the downloads are reused. An in-page "a new version
  is out" check against GitHub's releases. Half a day.
- **WSL memory tuning:** if M4-08 shows swap in use, `autoMemoryReclaim` and a per-stage memory guard.
