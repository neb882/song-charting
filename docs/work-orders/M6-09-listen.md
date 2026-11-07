# M6-09: a chart you can hear

**Branch:** `m6-09-listen`, from `main` at cb157b2 or later. **Agent:** `sc-builder`, then `sc-reviewer`. May push its
branch to run CI. **Files:** a new `songcharter/listen.py`, `songcharter/cli.py` (a `listen` command),
`songcharter/ui/server.py` and `songcharter/ui/static/` (the Done screen's player), their tests, `docs/DESIGN.md` (a
short section), `docs/guide/windows-wsl.md` (one bullet in section 5). Nothing that charts. **Time budget:** half a
day.

*Written by the orchestrator on 2026-11-07 at the owner's request: he does not play Clone Hero, and watching a chart
scroll by (or Clone Hero's bot, which hits every note) cannot show a wrong, late, missing or extra note. Hearing the
chart over the song can.*

## What to build

1. **`songcharter/listen.py`**: from a built song folder (notes.chart, song.ini, song.ogg), render one part and level
   as sound over the song, as a stereo audio file:
   - **5-fret parts** (guitar, bass): each note a short tone at its lane's pitch (five pitches that are easy to tell
     apart, an open note a sixth, lower one), a chord its pitches together; a sustain holds its tone, quieter, to its
     end; a HOPO or tap a shorter, softer attack than a strum, so the states can be heard.
   - **Drums**: the kick a low thump, the snare a noise burst, toms short pitched tones (one per pad), cymbals a high
     noise, so a missing kick or a hi-hat pattern is audible.
   - **The mix**: the song at a lower level (default about -12 dB) under the tones, or the tones alone (`--tones-only`);
     the tones at the chart's own times (song seconds: chart time 0 is song.ogg's 0, the lead-in pad is in both), read
     through songcharter's own chart reader and tempo map. No clipping (a limiter or a fixed headroom), deterministic
     (the same folder gives the same bytes).
   - Output: OGG Vorbis, or WAV for the tests. **Never inside the Clone Hero song folder** (Clone Hero reads audio
     files there by name; an extra file must not risk it): the CLI writes where `--out` says (default: the current
     folder, `<folder name>-<part>-<level>.ogg`), the page into the job's own work folder.
2. **`songcharter listen <song folder> [--part guitar|bass|drums] [--difficulty expert|hard|medium|easy] [--out FILE]
   [--tones-only]`**, exit codes as every command's (2 for a folder without the part or level).
3. **The Done screen**: under the preview, a "Listen" control: the part (guitar, bass, drums, the ones the chart has)
   and the level, a button that renders it (a few seconds, cached per part and level in the job's work folder) and an
   HTML audio player. The server serves only files it rendered for the current job (as `/api/jobs/current/preview/`
   serves only the preview's images): no path from the request reaches the file system.
4. **Docs:** DESIGN (a short section: what each sound means), the guide's section 5 (one bullet: "Listen to the chart"
   on the Done screen, what to listen for: a note late or missing, a part playing where the song is quiet).

## Tests

Made-up charts and audio only: a note's tone starts at its chart time (the onset within 2 ms, at the right sample
rate), lanes map to their pitches (an FFT peak per lane), a chord holds its pitches, a sustain lasts to its end,
HOPOs differ from strums, drums' pads differ; `--tones-only` has no song; the same folder renders the same bytes; the
CLI's exit codes; the server renders, caches and serves only its own files (a path in the request is refused). Each
test fails when its code is broken.

## Done means

- [dev] The suite; the new tests fail when their code is broken; `songcharter listen` on a golden run's song folder
  (e.g. `$DEV/golden/gate3-new/kimochi_warui`, outside the repository) renders in seconds and sounds right (say what
  you checked: its length equals song.ogg's, the first notes' times against the chart).
- [CI] Green on the branch.
- [docs] DESIGN, the guide.

## Report

`<scratchpad>/briefs/m6-09.report.md`: the commits, what each sound is, the checks, anything uncertain.
