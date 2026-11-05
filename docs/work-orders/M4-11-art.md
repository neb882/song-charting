# M4-11: album art and a background image in the song folder

**Branch:** `m4-11-art`, from main at ac922ee. **Agent:** `sc-builder`, then `sc-reviewer`. May push its branch to run CI;
not merged or released until the owner approves a v0.1.1 (the friend is testing v0.1.0).

## Why

The owner asked on 2026-11-05 for charts to carry art, as human charts do: a cover in Clone Hero's song list and a
picture behind the highway. songcharter writes neither today, and scan-chart reports `noAlbumArt` on every chart.

## What Clone Hero and scan-chart read

- **Album art:** `album.jpg`, `album.jpeg` or `album.png` in the song folder (scan-chart's `hasAlbumName`), which
  scan-chart wants at 512x512 (its `albumArtSize` issue otherwise).
- **Background image:** a per-song background file in the song folder. Find the exact names and extensions Clone Hero
  reads from its own documentation or its community's (the Clone Hero wiki or guides), record the source in your
  report and DESIGN, and use the plain JPEG name it documents. Note any Clone Hero setting the player must turn on
  to see song backgrounds, for the guide.
- **Not in this order:** video backgrounds (size, codecs, licences) and highway images.

## Build

1. **Album art, automatic:** the song file's embedded cover picture (an attached picture in MP3, FLAC, M4A and the
   like), read with the bundled ffmpeg or the image library already in the environment, becomes `album.jpg`:
   centre-cropped to square and resized to 512x512, re-encoded as JPEG (so no EXIF or other metadata survives).
   A file with no picture gets no album art, as now; a picture that fails to decode is a warning, never a failed chart.
2. **The person's own images, optional:** an album-art image and a background image.
   - CLI: `songcharter chart SONG --album-art FILE --background FILE`; `Options` gets the two paths.
   - The page: two optional file pickers in the options ("Album art" and "Background image"), uploaded the way the
     song is (the server's guards, size limits and `uploads/` pruning apply), and shown on the Done screen when
     present (the album art beside the song's name is enough).
   - Accept JPEG, PNG and WebP; anything else, or an image over 20 MB or too large in pixels to decode safely, is an
     InputError (exit 2) naming the limit. Re-encode every image (no metadata kept: a phone photo's EXIF can hold
     its GPS position).
   - The background is scaled down to fit 1920x1080, never up, keeping its shape, and saved under the documented
     name. A given album-art image replaces the embedded one.
3. **Determinism:** the same song file and the same images give byte-identical image files (fixed encoder settings).
4. **Records:** pipeline.json and report.json say whether album art and a background were added and where each came
   from (`embedded`, `given`, or none), with no paths outside the work folder. The diagnostics zip never takes the
   images (check that diagnostics.py refuses them, as it refuses PNGs).
5. **The rest of the chart is unchanged:** no change to notes, song.ini's chart values or the audio. The golden
   charts compare notes, so they should not move: say what you ran to show it (a golden run is needed only if a file
   in eval/golden.py's ENGINE_FILES changes).

## Tests and CI

- Tests with images made by code (no real photos): an MP3 and a FLAC with an embedded picture give a 512x512
  album.jpg; a non-square one is centre-cropped; no picture gives none; a given album-art image wins over the
  embedded one; a background larger than 1920x1080 is scaled down and a small one is not scaled up; EXIF in a given
  image does not survive; a bad or oversized file is an InputError (exit 2); two runs give byte-identical files; the
  page's upload path for both images, and the Done screen showing the album art; pipeline.json's records; the
  diagnostics zip holds neither image.
- Each new test fails when the code it covers is broken (say which break).
- CI: extend the hook that charts the clip through the page (60-results.sh) so it passes a generated background and
  checks that the song folder holds `album.jpg` (if the clip has a picture: give the CI clip one) and the
  background, and that scan-chart no longer reports `noAlbumArt` for it.

## Docs

- The guide (section 5): one short bullet on the two optional images, and the Clone Hero setting, if any, that shows
  song backgrounds.
- README (`--album-art`, `--background`), DESIGN (where the art comes from, the sizes, the source for Clone Hero's
  names), PROGRESS.

## Limits

- No change to how notes are made. Keep new dependencies to none: the environment already has an image library and
  ffmpeg; if one is truly needed, say why and keep both locks consistent.
- Time budget about 3 hours, CI included.

## Report

`<scratchpad>/briefs/m4-11.report.md`: the commits, each item above with what was done, the source for Clone Hero's
background names, each check with its last lines, and anything uncertain.
