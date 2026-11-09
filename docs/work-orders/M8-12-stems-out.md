# M8-12: the stems as files of their own

**Branch:** `m8-12-stems-out`, from `main` after M8-04's merge (both change the options form; M8-10's queue then carries
the option per song like the others). **Agent:** `sc-builder`, then `sc-reviewer` (who also looks at the screens). May
push its branch to run CI. **Files:** `songcharter/pipeline.py` (only the export after the separate stage),
`songcharter/cli.py` (the flag), `songcharter/ui/{jobs.py,server.py}`, `songcharter/ui/static/{app.js,index.html,app.css}`,
`tests/`, `docs/guide/windows-wsl.md`, `docs/DESIGN.md` (2.2 and 4.5). **Not:** the separation itself (model, seed,
device), the chart, `song.ogg`, Clone Hero's song folder (part B is its own decision). **Time budget:** half a day to a
day. **Rough cost:** 2-3 % of a week's meter.

**Environment:** eval/README.md's step 9, and `SONGCHARTER_HEAVY_MIN_FREE_GB=1` on every heavy job (the suite, builds).

*Written by the orchestrator on 2026-11-09 from the owner's ask: the friend asked whether songcharter could give the
separated instruments as files of their own ("separating a song into its separate instrument tracks is a useful tool
in and of itself for sampling and such"), as AutoChart.eu offers.*

## Why

Every chart already separates the song: htdemucs_6s, seeded, six stems (drums, bass, guitar, piano, vocals, other) at
44.1 kHz on the input's own timeline (no lead-in), kept as WAVs in the cache's `work/stems/<key>/` (pipeline.py step 2).
They are lost to the user there: the cache is pruned at 5 GB and its folders are not his to find. Saving them where he
can use them costs no separation, only a copy and an encode.

## What to build

1. **An option, off by default:** "Also save the separated instruments (stems)" on the page's options form, and
   `songcharter chart … --stems` on the command line. On, the chart's run writes the six stems into a folder of their
   own beside the Clone Hero song folder (never inside it: Clone Hero reads `guitar.ogg`, `drums.ogg` and the like in a
   song folder as the song's own audio), named after the song folder with " (stems)". Each file is named for its
   instrument (`guitar.flac`, …).
2. **The format:** lossless, at the stems' 44.1 kHz, the input's length, no lead-in, so a stem lines up with the user's
   own file in an audio editor. FLAC (24-bit) unless the builder finds a reason for WAV; the decision and the sizes (a
   4-minute song: about 380 MB as 24-bit WAV, about half as FLAC) in DESIGN. Deterministic: the same input gives
   byte-identical files (the seeded separation; no time stamps or random serials in the files).
3. **On the page:** a finished song with stems shows "Download the stems" (a zip, stored without compression), and the
   options form says before the chart how much disk the stems take (from the song's length) and that piano and "other"
   are the least clean (htdemucs_6s's own limit).
4. **The cache:** a chart run again with the option on, after one without it, reuses the cached stems (no separation);
   the export reads them before the run's prune. A cache without them (pruned between runs) separates again, as today.
5. **Errors:** a full disk while writing the stems is an `InputError` naming the folder and the space needed, and the
   chart itself (already written) stays; a partial stems folder is removed.

## Done means

- Tests: the option on writes six files with the right names, rate and length (a short synthetic song with a stand-in
  separator, as the pipeline's tests do); off writes nothing; a cached rerun does not separate; the files are
  byte-identical across two runs; the CLI flag; the page's option and button (the stand-in server). Each new test fails
  on a break of what it covers (say which).
- The full suite once through `tools/heavy.sh`; CI green on the branch; the screens looked at in Chromium.
- One real chart of a short reference with the option on: the stems open in an audio editor's reader (ffprobe: codec,
  rate, length equal to the input's), summed they come back to within Demucs's residual of the input (say the number).

## Part B, not in this order: Clone Hero's own multitrack audio

Official Clone Hero songs ship `guitar.ogg`, `bass.ogg`, `drums.ogg`, `vocals.ogg` and `song.ogg` (the rest), and the
game mutes an instrument's track on a missed note. Writing our stems that way is a game-feel change with risks the
stems for sampling do not have (the guitar stem's bleed, the stems' sum against the mix, Clone Hero's per-track
volumes): the owner listens to one song charted both ways before an order is written.
