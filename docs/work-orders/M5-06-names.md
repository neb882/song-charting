# M5-06: "Artist - Title" from the file name, and song folder names cut at a word

**Branch:** `m5-06-names`, from `main` after M4-11's merge (wave 1, beside M5-09; M5-05 follows in the same builder
slot). **Agent:** `sc-builder`, then `sc-reviewer`. May push its branch to run CI. **Files:** `songcharter/pipeline.py` (`song_metadata` and the
metadata constants only), `songcharter/cache.py` (`safe_name`), `songcharter/ui/jobs.py` (`output_folder`),
`songcharter/ui/server.py` (the upload answer, only if it needs the new origin), `songcharter/ui/static/app.js`
(`fillOptions`, only if the placeholder logic needs it), their tests, `docs/DESIGN.md` 2.13 and the README.
**Time budget:** half a day.

## Why

Seen by the owner in M4-08 part A: an MP3 with no artist tag charts as "Unknown", although its file name reads
"Artist - Title"; and the song folder's name is cut at 40 characters in the middle of a word (`cache.safe_name`,
`NAME_MAX`), the preview's title with it (it shows the folder's name). The page already has Title and Artist fields
in the options, filled from the tags and left empty with an "Unknown" placeholder when nothing is known
(`app.js` `fillOptions`); what it lacks is the guess from the file name.

## What to build

1. **The file name** (`pipeline.song_metadata`): when no tag gives the artist and the file's stem matches
   `[<track number><sep>]<artist><sep><title>`, where `<sep>` is a hyphen, en dash or em dash with spaces on both
   sides and the optional track number is one to three digits followed by a space, a dot or a separator, then
   `artist` is the part before the first separator and `title` the part after the last one, both with their origin
   `"file name"`; a tagged title still wins over the file name's title, and a tagged artist over its artist. A stem
   with no separator keeps today's rule (the stem is the title). A part that is blank after trimming does not count
   (the stem "- Title" gives no artist).
   - `report["metadata_from"]`, pipeline.json and the upload answer (`/api/upload`'s `origin`) carry `"file name"`
     as they carry `"tag <name>"` today, so the page prefills the guessed artist and title (it prefills any origin but
     `"default"`), editable before the chart.
2. **Folder names at a word** (`cache.safe_name`): when the cut at `limit` falls inside a word, cut back to the last
   space before it if that leaves at least `limit - 12` code units; otherwise cut as today. Trailing spaces and dots
   go as today. The work folder keeps `NAME_MAX` 40 (autochart's deep cache paths under Windows' 260 characters:
   cache.py's docstring). The library folder (`ui/jobs.output_folder`, the name the friend sees in Clone Hero's Songs
   folder and on the Done screen) gets `LIBRARY_NAME_MAX` = 80: the longest path it makes on the Windows side
   (`Documents\Clone Hero\Songs\<name>\notes.chart` under a profile) stays well under 260. The preview's title follows
   the folder's name and needs no change.
3. **The autochart job's metadata** (`AC_TITLE`, `AC_ARTIST`) follows `meta`, as today: nothing to do but check.
4. **The album placeholder** [conventions: Encore's song.ini rule gives a single the album "<Name> - (Single)";
   `docs/reports/charting-conventions.md` section 8] [decided by the owner, 2026-11-05: the recommendation, with
   that source]: when no tag
   gives the album, song.ini's `album` is `"<the song's name> - (Single)"` with origin `"default"`, instead of
   "Unknown"; the page's Album field shows it as its placeholder, as it shows the other defaults. Genre and year keep
   "Unknown" (no convention names a better placeholder). `song_length`, `diff_band` and report.json in the folder
   are M5-99's.
5. **A song too short or silent is refused cleanly** (PROGRESS deferred: a 1 s, 4 s or silent song exits 3 when the
   librosa sections fallback raises): after the decode, a song under `MIN_SONG_S` = 10 s, or whose peak is under
   -60 dBFS, raises an InputError naming the length or the silence (exit 2) before the separation. One test each
   through `chart()` with standins and one through the CLI's exit code.

## Tests

- `song_metadata`: "Artist - Title", "01 - Artist - Title", "01. Artist – Title" (en dash), "Artist - Album - Title"
  (artist first, title last), "Title" (no separator: title only, artist default), a tagged artist wins, a tagged
  title with a file-name artist, "- Title" (no artist), the origins.
- `safe_name`: a cut inside a word moves to the last space within 12 units; a 60-unit word is cut hard; the limit
  parameter; the existing tests unchanged.
- `output_folder` with a long artist and title: the name within 80 and cut at a word.
- `/api/upload` on a file named "Artist - Title.mp3" with no tags: `tags.artist` and `origin.artist == "file name"`;
  the page's `fillOptions` prefills it (the existing page test's pattern).
- Each test fails when its code is broken (say which break).

## Evaluation

- **Golden:** `pipeline.py`'s metadata only; the reference files are `input.wav` (no separator), and golden compares
  notes, not song.ini: `--expect none` (the cheap run).

## Done means

- [dev] The suite; the new tests fail when their code is broken.
- [dev] The golden diff, exit 0.
- [CI] Green on the branch (60-results.sh charts the clip through the page: name the CI clip "Test Artist - Test
  Clip.wav" there only if the hook's checks on the song.ini values still hold; otherwise leave the clip's name).
- [docs] DESIGN 2.13 (the file-name rule, the two limits), README (the metadata paragraph).

## Limits

- No new option. No change to the tags' precedence or to Clone Hero's install path handling (`clonehero.py`).

## Report

`<scratchpad>/briefs/m5-06.report.md`: the commits, each check's last lines, the golden verdict, anything uncertain.
