# song-charting

Tools and charts for making Clone Hero charts from audio.

First song: "Love Isn't Love Enough" by Beast Monster Thing.

## What lives here

- The charting pipeline (stem separation, tempo map, note extraction, chart writer).
- The finished chart files (`notes.chart`, `song.ini`).

## What does not

The song audio. It is the artist's copyrighted recording, so it is never committed
(see `.gitignore`). To play or rebuild a chart, put your own copy of the song in the
song folder.

## Status

The core is in place and tested: the tempo map, the `.chart` and `song.ini` writers, and song
folder packaging with an audio sync check. The analysis stages (stems, beats, notes, drums) come next.

## Development

```sh
pip install -e ".[dev]"
(cd tools/scan-chart && npm ci)   # the offline chart check (scan-chart, as used by Chorus Encore)
pytest
```

`node tools/scan-chart/scan.cjs <song folder> --notes` prints what Clone Hero will read from a
song folder: whether it is playable, any issues, and every note with its time.

## How timing stays exact

Everything is measured against one gapless decode of the input. `song.ogg` is encoded from those
same samples, with lead-in silence in front so tick 0 is a measure line, then decoded back and
checked against them window by window. A package is only written when the offset is under one
sample.
