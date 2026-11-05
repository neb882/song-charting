# song-charting

songcharter makes Clone Hero charts from a song file: guitar, bass and drums, with a tempo map, sections, star
power and solos.

```sh
songcharter chart "song.mp3" --out "Songs/Artist - Title"
```

The first song charted with it is "Beast Monster Thing (Love Isn't Love Enough)" by Car Seat Headrest.

## Status

- **The first chart is done.** v1 and v1.1 of the first song have been delivered and played.
- **The any-song pipeline is built** (`songcharter chart`, milestone M3) and runs end to end on Linux. Its parts:
  - Demucs stem separation;
  - autochart's engine for guitar, with up to four takes spliced by agreement;
  - ADTOF for drums;
  - our own rules for bass;
  - allin1 for sections;
  - our grid, reductions, star power and solos.
- **v0.1 for Windows** runs in WSL2 (M4): the friend's guide is `docs/guide/windows-wsl.md`, which
  `packaging/release/build.sh` renders into each release's notes (`GUIDE.md`). `docs/PROGRESS.json` has the
  current state; `docs/DESIGN.md` has the design and the evidence behind each choice.

## Using it

**On Windows:** follow the release's guide: set up WSL once, then paste its one line, which downloads
`install.sh`, checks its SHA-256 and runs it. On Linux, from a checkout:

```sh
pip install -e ".[separate,drums,bass,sections,preview]"
songcharter chart song.mp3 --out "Songs/Artist - Title"
```

- **Expert only by default:** `--levels all` writes every difficulty.
- **Guitar takes:** 4 on a CUDA GPU and 1 on the CPU; `--takes N` overrides.
- **A take that fails on the GPU** is run again on the CPU, once per chart, and the page says so;
  `--no-cpu-retry` turns that off.
- **Solos** go on the sections the section model labels as solos. `--solos "Solo 1,Solo 2"` names them yourself,
  and `--solos off` turns them off.
- **A preview** of how the chart fits the audio is written next to the work files: the run's summary prints its
  path. `--no-preview` turns it off.
- **Lyrics:** `--lyrics lyrics.txt` times the song's lyrics to its vocal stem and writes them into the chart, for
  Clone Hero's lyrics display. Paste them into a text file yourself, a line per phrase and a blank line between
  sections; songcharter never looks lyrics up. The aligner (`songcharter[lyrics]`, which the app includes) downloads
  its weights (1.26 GB) on first use, the installed app's included (`SONGCHARTER_OFFLINE=1` forbids it); without
  them the chart is made without lyrics, with a warning. The text goes
  into the chart and nowhere else: the reports count the words, they never hold them.
- **Title, artist and album** come from the song file's tags. With no artist tag, a file named "Artist - Title"
  (or "01 - Artist - Title") gives both; otherwise the file's name is the title. `--title`, `--artist`, `--album`,
  `--year` and `--genre` set them yourself, and the page fills its fields with what it found, for you to change.
  With no album tag, the album is "<title> - (Single)", as charters write it for a single.
- **Album art and a background:** the song file's own cover picture, when it has one, becomes the chart's album art
  (`album.jpg`, cut to a 512x512 square). `--album-art FILE` gives another one, and `--background FILE` a picture for
  behind the highway (`background.jpg`, scaled down to fit 1920x1080), which Clone Hero shows when Settings >
  Gameplay > Use Song Backgrounds is on. JPEG, PNG or WebP, up to 20 MB; every picture is re-encoded, so no EXIF (a
  photo's GPS position) is kept.
- **The work files** (the decode, the stems, each engine's output) go to a per-user cache, `~/.cache/songcharter`:
  in v0.1, which runs in WSL, that is inside Ubuntu, whose disk grows on C:. (`%LOCALAPPDATA%\songcharter` is the
  cache of a native Windows run, which v0.1 does not ship.) The cache is pruned to 5 GB, and `--work DIR` puts the
  work files elsewhere.
- **Model weights** are downloaded on first use and checked against pinned hashes.
- **The page:** `songcharter ui` opens a local page in the browser: drop a song, keep or change the options (paste
  the lyrics and choose the pictures, if you want them), watch each stage and cancel. Then look at the preview, install the song
  into Clone Hero's Songs folder or save it as a zip. `songcharter chart --events` writes the same progress as JSON
  lines for other programs.
- **When something goes wrong:** `songcharter diagnostics --out FILE.zip` (or the page's Diagnostics link) makes
  one file of logs and settings to send. It holds no audio, charts, lyrics or pictures.

## What does not live here

- **The song audio** is the artist's copyrighted recording, so it is never committed (see `.gitignore`). To play
  or rebuild a chart, put your own copy of the song in the song folder.
- **No stems, reference charts or model weights** are committed either.

## Licence

songcharter's own code is MIT (`LICENSE`), except `songcharter/engines/adtof.py`, treated as CC BY-NC-SA 4.0.
What it downloads has its own licences, some of them non-commercial (Fretformer 2, the ADTOF weights,
htdemucs_6s): `packaging/NOTICE.txt`, also at the root of each release's tarball.

## Development

```sh
pip install -e ".[dev,separate,drums,bass,sections,preview]"
(cd tools/scan-chart && npm ci)   # the offline chart check (scan-chart, as used by Chorus Encore)
SONGCHARTER_SCAN_CHART=$PWD/tools/scan-chart/scan.cjs python -m pytest -q
```

`node tools/scan-chart/scan.cjs <song folder> --notes` prints what Clone Hero will read from a song folder:
whether it is playable, any issues, and every note with its time. `CLAUDE.md` has the rules for working on the
project.

## How timing stays exact

Everything is measured against one gapless decode of the input. `song.ogg` is encoded from those same samples,
with lead-in silence in front so tick 0 is a measure line, then decoded back and checked against them window by
window. A package is only written when the offset is under one sample.
