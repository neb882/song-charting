# M8-12: the stems as files of their own, and Clone Hero's multitrack audio

**Branch:** `m8-12-stems-out`, from `main` after M8-04's merge (both change the options form; M8-10's queue then carries
the options per song like the others). **Agent:** `sc-builder`, then `sc-reviewer` (who also looks at the screens). May
push its branch to run CI. **Files:** `songcharter/pipeline.py` (the export after the separate stage), `songcharter/assemble.py`
(the song folder's audio files, part B), `songcharter/preview.py` and whatever else reads `song.ogg` (part B, item 3),
`songcharter/cli.py` (the flags), `songcharter/ui/{jobs.py,server.py}`, `songcharter/ui/static/{app.js,index.html,app.css}`,
`tests/`, `docs/guide/windows-wsl.md`, `docs/DESIGN.md` (2.2, the audio's section and 4.5). **Not:** the separation
itself (model, seed, device), the notes. **Time budget:** one to one and a half days. **Rough cost:** 3-5 % of a week's
meter.

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

## Part B: Clone Hero's multitrack audio, on by default

Official Clone Hero songs ship `guitar.ogg`, `bass.ogg`, `drums.ogg` and `song.ogg` (the rest), and the game mutes the
instrument's own track on a missed note. The owner's second tester, a drummer, on it (2026-11-09): "makes it feel much
more like you're playing bc if you stop that track stops"; "a lot of people naturally like that".

1. **The song folder's audio:** `guitar.ogg`, `bass.ogg` and `drums.ogg` from the stems, and `song.ogg` the mix less
   those three (so the separation's residual stays in `song.ogg`): played together they sum to today's single
   `song.ogg` within the encoder's noise, so a player who misses nothing hears what he hears today. Vocals, piano and
   "other" stay in `song.ogg` (no part we chart mutes them). The same lead-in pad, length, rate and encoder settings
   for each file; a part we do not chart (none today) gets no file of its own.
2. **One audio file instead:** an option ("One audio file: the music does not drop out on a miss") and
   `--one-audio`, which writes today's single `song.ogg`.
3. **Everything that reads `song.ogg` reads the folder's audio summed:** the page's Listen and the preview, the gate's
   checks, scan-chart's audio list, eval/scorer (check it already sums a folder's audio files), the install's copy.
4. **Done means (part B):** the four files summed against the single-file chart of the same song (the difference in
   dB below the mix, say the number); scan-chart lists the four; byte-identical across two runs (the Ogg stream serial
   fixed: today's `song.ogg` differs run to run in its serial only, the GPU smoke test's finding); the tests as part A's.
   The release gate's play test plays one song with a few notes missed on purpose and says how the drop-out sounds
   (the guitar stem's bleed stays audible in `song.ogg`; whether that is acceptable is the owner's call there).
