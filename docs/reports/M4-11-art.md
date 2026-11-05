# M4-11: album art and a background image (2026-11-05)

The build's report, with its review fixes, then the review. Paths under `/tmp/claude-0/…/scratchpad` and `/dev/shm` name the building session's scratch files.

## M4-11 report: album art and a background image in the song folder

Branch `m4-11-art` (worktree `scratchpad/wt/art`), from main at ac922ee; pushed, not merged.

### Commits

- b233cf4 the work order (the orchestrator's)
- 0bb80db M4-11: album art and a background image in the song folder (the code)
- bbd7ef3 M4-11: tests and the CI hook for the album art and the background
- e690e6a M4-11 docs: DESIGN 2.16, the README, the guide's section 5 and PROGRESS
- 055cd24 M4-11: one place each for the metadata, the byte limit and the never-up rule (after the mutation pass)

### Clone Hero's background name: the source

The Clone Hero wiki, Guides and Tutorials, "Custom Content"
(wiki.clonehero.net/books/guides-and-tutorials/page/custom-content, read 2026-11-05), section "Adding Song-specific
Content": open the song's folder, "Place an image or video in the folder and name it "background" for backgrounds,
"video" for videos, or "highway" for highways"; then scan songs, go to Settings > Gameplay, and turn on "Use Song
Backgrounds" (or "Song Videos", "Song Highways"). Static backgrounds: .png, .jpg, .jpeg. The manual's "Other Custom
Content" page says backgrounds can be any size and recommends 1920x1080 or 4K. So the file is `background.jpg`, and
the guide names the setting.

**Against the orchestrator's research brief** (briefs/charting-conventions.md, section 8):
- **Where they agree:** the name `background.jpg`, the .png/.jpg/.jpeg extensions, and the setting the player turns
  on (Settings > Gameplay > "Use Song Backgrounds"). The brief also says YARG reads `bg` or `background`, which I did
  not check myself; `background.jpg` serves both games. Album art at 512x512 as .jpg matches Encore's preference too.
- **Where they differ:** Encore's guideline puts a background at 1280x720 or more. M4-11 never scales up, as the order
  says, so a small given image (800x600, say) stays under it. Clone Hero's wiki allows any size. I left this as it is;
  the report notes it for a decision.

### Each item

1. **Album art, automatic.** `songcharter/art.py`: ffmpeg's listing of the song file finds the attached pictures
   ("(attached pic)"). It takes the one marked "Cover (front)", else the first, and copies it out as stored. Pillow
   decodes it, crops the centre square and resizes it to 512x512 (Lanczos), and re-encodes it as album.jpg. No picture
   means no album art, as before. A picture that fails to decode, or is not JPEG/PNG/WebP, is a warning with no album
   art. Run on MP3 (APIC), FLAC (PICTURE) and a hand-made ID3 tag.
2. **Given images.** `--album-art FILE` and `--background FILE`, plus `Options.album_art` and `Options.background`.
   - Accepted: JPEG, PNG or WebP by content (Pillow opens only those three), at most 20 MB, at most 64 megapixels,
     and the file must decode whole. Anything else is an InputError (exit 2) that names the limit and the file by
     name only. It is raised before any audio work, and before the work folder is made or marked.
   - The background is scaled down to fit 1920x1080, never up, and keeps its shape. A given album art replaces the
     embedded one.
   - No metadata survives: each image is encoded from its pixels alone (Pillow's resize keeps a source's JPEG comment
     otherwise; I checked). The EXIF orientation is applied first. Transparency goes onto black, and 16-bit greys are
     scaled to 8 bits.
   - The page has two pickers under "Pictures (optional)". They upload through the new `POST /api/upload/image`
     (same guards, the `uploads/` folder and the 7-day pruning; 415 for a bad extension or content, 413 over 20 MB).
     The job's options carry upload ids, which the server turns into paths, so a path never comes from the page.
     "Chart it" waits while a picture uploads. The Done screen shows the album art beside the song's name (from
     `GET /api/jobs/current/art/album.jpg`, that one name only), with a line when there is a background.
3. **Determinism.** Fixed JPEG settings (quality 90, 4:2:0, baseline, no optimize). Two runs give byte-identical
   files, in the unit tests and through the pipeline.
4. **Records.**
   - pipeline.json `art` and report.json `art` hold, for each picture: added, file, from (`embedded`, `given`, or
     null), the source's format and size, and why when nothing was added.
   - The options say only whether each picture was given. The test checks that no record (pipeline.json,
     assemble.json, report.json) names the given image's folder.
   - Assemble got a `background` config key and an `art=` keyword, and `background.(png|jpg|jpeg)` joined
     OUTPUT_FILES (a later build without a background removes the old one).
   - diagnostics.py refuses .jpg, .jpeg and .webp by name, and JPEG/PNG by their first bytes.
5. **The rest is unchanged.** Through the pipeline, notes.chart and song.ini are byte-identical with and without the
   pictures (test). No file in eval/golden.py's ENGINE_FILES changed (only art.py, pipeline.py, assemble.py,
   package.py, cli.py, ui/*, diagnostics.py), so I ran no golden run.

The choices the order left open, and the smallest one I took each time:
- the 64 MP pixel limit;
- the front cover preferred among several pictures;
- transparency onto black;
- no ICC colour conversion;
- the image check repeated at upload, so the page shows why next to the picker;
- no new dependency: Pillow 13.0.0 comes with matplotlib (preview, so app). Without Pillow, a given image is a
  ToolError naming the fix, and an embedded picture is a warning. The locks are unchanged.

### Checks

- **Full suite** (heavy.sh): `860 passed, 4 skipped in 912.30s`. Most of it ran on 0bb80db+bbd7ef3, and 055cd24's
  small change landed during it. A second full run on the final code (055cd24): `860 passed, 4 skipped in 761.11s`.
- **New tests:**
  - tests/test_art.py: 16 tests, `16 passed in 53.66s`.
  - test_ui_server.py: 3 new tests (picture uploads and the job's pictures; the results' album art by its exact name;
    app.js in node, covering the pickers, the options and the Done screen).
  - test_ui_jobs.py: 1 new test and 3 bad-option cases.
  - test_diagnostics.py: extended.
- **Mutation pass** (scratchpad/m411/mutate.py): 40 breaks, each run against its tests. All are caught (39 on the first pass, the 40th after the fix below). Among them:
  - the crop removed; the album size at 500; the never-up rule, after the fix below; the background not scaled;
  - the fresh image dropped (metadata kept); the orientation dropped; any format taken; the pixel and byte limits
    removed; transparency and 16-bit handling removed;
  - the front-cover choice; the embedded picture never found; a bad embedded picture raising; the given album art
    losing;
  - the pipeline's config, warnings, options record and order; the CLI flag; OUTPUT_FILES, the art record and its
    origin; the package copy;
  - the server's kind check, the id-to-path step, the upload check, the results' art, the exact-name route, the
    upload size limit;
  - app.js's options, Done screen and "Chart it" hold; jobs.py's flags, records and type check; diagnostics' name and
    magic.

  At first 3 of the guards were duplicated, so breaking one copy went unseen: the "never up" cap, the metadata drop
  in both decode and encode, and the byte limit in both check_file and decode. 055cd24 keeps one of each, and the
  rerun of those breaks fails a test.
- **CI** (pushed run, 41954798150, https://github.com/neb882/song-charting/actions/runs/41954798150): success, linux
  and windows.
  - The hook ran: `==== hook linux.d/60-results.sh ok in 79 s`.
  - Its lines: "the background uploaded: 200", "a text file named .png: 415", the zip with album.jpg and
    background.jpg, "the pictures: album.jpg (512, 512) from the clip's own, background.jpg (1920, 1080) with no
    EXIF; scan-chart's folder issues []", "the Done screen's album art: served", "60-results: ok".
  - The suite in CI: `860 passed, 4 skipped`.
  - The final push (055cd24, run 41957278725, https://github.com/neb882/song-charting/actions/runs/41957278725):
    success, linux and windows. `860 passed, 4 skipped`; `==== hook linux.d/60-results.sh ok in 81 s`; the same
    pictures line; `all 7 Linux hooks passed`.
- **Scan**: I scanned `git diff ac922ee..HEAD` and the commit messages for lyrics, audio, model names and personal
  details. The only model names are in the required trailers. No binary files. The test pictures are made by code,
  with a made-up maker and made-up GPS values.

### Uncertain or not done

- Not looked at in Clone Hero itself: the cover in the song list, and the background with Use Song Backgrounds on.
  It goes on the next release candidate's hardware check (PROGRESS, deferred).
- The embedded picture is found by parsing ffmpeg's human-readable listing. It is stable, but not a documented
  interface. Checked on ffmpeg 6.1 (dev) and imageio-ffmpeg 7.0.2 (CI, the app).
- An M4A's covr and a WMA's picture were not tried (no test files of those formats here); ffmpeg lists both as
  attached pictures.
- Colours are not converted from an ICC profile.
- Video backgrounds and highways are out of scope.
- docs/guide's section 3 changed on main since ac922ee (the update note). My bullet is in section 5, and PROGRESS's
  addition sits mid-list, so the merge should be clean, but I have not tried it.

### Review fixes

The review (`briefs/m4-11.review.md`: no majors; m1, t1, t2) was fixed on the same branch by a second builder (the
first was lost to a machine restart), from 055cd24.

#### Commits

- 8252dbe M4-11 review fixes: a 64 MP picture's memory, and tests for palette and LA transparency (m1, t1)
- 90e691c M4-11 review fixes: the embedded picture is checked by its decode alone (t2)

#### m1: memory

- **Reproduced** at 055cd24 (fresh process, `art.prepare('a.wav', album_art=f, background=f)`, ru_maxrss): RGB 767,
  16-bit grey 1988, RGBA 1076 MiB. Stage by stage, there were four causes:
  - the 16-bit grey's float64 arrays (1.3 GB alone);
  - `exif_transpose` copying every upright image (RGB 278 -> 522 MiB);
  - `convert("RGBA")` copying an RGBA image;
  - `prepare` keeping the album art's decoded image alive while it decoded the background (522 -> 767 MiB).
- **The fix** (`songcharter/art.py`):
  - 16-bit greys (I;16, and I) are scaled by Pillow's own table, `convert("I").point([(x + 128) // 257 ...], "L")`.
    It is exact: over all 65536 values it equals the old `rint(x / 257)`, and out-of-range "I" values clip to 0
    and 255 as before. No numpy arrays are made. I used this rather than the review's uint32 arrays because it
    measured lower: the int32 version peaked at 643 MiB (Pillow's `tobytes` behind `np.asarray` builds its bytes
    twice), the table at 462 MiB. "F" stays on numpy, float32 in place; none of the three formats opens as F or I in
    Pillow 13.
  - An RGBA image is pasted onto black as it is.
  - `exif_transpose(img, in_place=True)`.
  - A `_given` helper, so each given image's decoded pixels go before the next one is decoded.
  - Not changed: LA. Pasting LA straight onto black would save 256 MB, but on random pixels it gives different bytes
    from the RGBA route, so LA keeps its copy.
- **Peaks** at 64 MP (8000x8000 images made by code; fresh process each; MiB, ru_maxrss/1024; the interpreter is
  30 of it), before -> after:

  | image | before | after |
  |---|---|---|
  | RGB PNG (the review's case 1) | 767 | 317 |
  | 16-bit grey PNG, 141 KB (case 2) | 1988 | 468 |
  | RGBA PNG (case 3) | 1076 | 584 |
  | LA PNG | 1076 | 828 |
  | palette PNG with tRNS | 891 | 645 |
  | L PNG / 1-bit PNG | 593 | 340 |
  | CMYK JPEG | 770 | 526 |
  | RGB JPEG | 768 | 317 |
  | RGBA WebP (lossless) | 1319 | 1075 |

  A WebP's `load()` alone peaks at 1000 MiB: libwebp's decoder keeps its own canvas, which Pillow's public API
  can't release.
- **The same bytes:** those 10 images, and 8 JPEGs with EXIF orientations 1 to 8, give byte-identical album.jpg and
  background.jpg before and after the fix (SHA-256 compared).
- **The figure:** "about 192 MB once decoded" is replaced:
  - art.py's docstring and MAX_PIXELS comment now say 0.3 to 0.9 GB, and 1.1 GB for a WebP;
  - DESIGN 2.16 has a new "Memory" bullet with the figures by mode, the causes and the WebP note.

  Pillow holds RGB at 4 bytes a pixel, so a 64 MP RGB image is 256 MB once decoded, not 192.

#### t1 and t2

- **t1:**
  - `test_transparency_goes_on_black_and_16_bit_greys_are_scaled` now covers RGBA, LA and a palette PNG with
    `transparency=0`. Each has a transparent half that must be (0, 0, 0) and an opaque half that must keep its colour.
  - The 16-bit part checks exact values at the rounding edges: 0, 128, 129, 32896, 65406, 65407 and 65535 give 0, 0,
    1, 128, 254, 255 and 255.
  - New `test_a_16_bit_grey_is_scaled_without_big_arrays` (tracemalloc over `decode` of a 4 MP 16-bit grey: under a
    byte a pixel).
- **t2:** dropped the `returncode == 0` check (not tested). It only kept a cut-short copy away from the decode, which
  turns it into the warning anyway. Whatever ffmpeg copies out is decoded; an empty copy is still "no picture". The
  docstring says so.

#### Checks

- **Breaks** (`scratchpad/m411fix/mutate.py`, art.py restored after each; the unit tests of test_art.py): 10 of 10
  caught.
  - Caught by the transparency test:
    - the palette tRNS branch removed (the review's t1 break);
    - "LA" removed (the review's other t1 break);
    - "RGBA" removed;
    - the 16-bit scale truncated (`x // 257`);
    - the transparency put onto white.
  - Caught by the big-arrays test:
    - the 16-bit back to float64 (055cd24's code);
    - the 16-bit as int32 arrays in place.
  - Caught by both: the 16-bit scale by 256; the 16-bit branch removed.
  - Caught by the orientation test: the in-place orientation dropped.
  - Memory-only changes give the same output, so no test can see them: the RGBA copy restored, `del i32` dropped,
    `_given` inlined.
- **Covering files** (heavy.sh; test_art, test_ui_server, test_ui_jobs, test_diagnostics, test_assemble,
  test_pipeline): `194 passed in 388.06s (0:06:28)`. This ran before the last comment-only edits to art.py; the full
  suite below ran on the final code.
- **Full suite** (heavy.sh, on 90e691c): `861 passed, 4 skipped in 484.03s (0:08:04)`.
- **CI** run 42018147971 (https://github.com/neb882/song-charting/actions/runs/42018147971): success, linux and
  windows.
  - `861 passed, 4 skipped in 383.83s`.
  - `==== hook linux.d/60-results.sh ok in 75 s`, with "60-results: the pictures: album.jpg (512, 512) from the clip's
    own, background.jpg (1920, 1080) with no EXIF; scan-chart's folder issues []".
  - `all 7 Linux hooks passed`.
- **Scan:** I scanned `git diff main...HEAD` and the branch's commit messages for lyrics, audio, model names and
  personal details. The only model names are the 7 required trailers; there are no binary files and no paths of a
  person's.

#### Left as it is (for the orchestrator)

- A 64 MP WebP still peaks at about 1.1 GB, in Pillow's WebP decoding; LA at about 0.9 GB. Both are documented. A
  lower pixel limit for WebP would be a decision, not a fix.
- The review's three notes (assemble's `background` copied as it is; the upload kept in `uploads/` for 7 days; the
  later picture answer winning) asked for no change, and none was made.

## M4-11 review: correctness and safety (branch m4-11-art, 055cd24)

Read: the work order, the report, `git diff b233cf4...m4-11-art`, the research brief's section 8. Ran test_art.py
(16 passed) and the pictures' tests in test_ui_server/test_ui_jobs/test_diagnostics on a copy, 20 mutations of my own,
and probes of odd images, embedded pictures and memory (under /dev/shm, deleted).

**No major findings.** Exit codes, the order (InputError before any work), metadata stripping, determinism, the
server's id-to-path step, the exact-name art route and the diagnostics refusals all hold.

### Minor

**m1. 16-bit grey (and RGBA) images use far more memory than the 64 MP limit allows for.** `art._rgb` turns I;16
into float64 arrays (`np.asarray(img, dtype=np.float64)`, `a / 257.0`, `np.rint`, `np.clip`), each 512 MB at 64 MP.
- Repro (fresh process, `art.prepare('a.wav', album_art=f, background=f)`, ru_maxrss): an 8000x8000 RGB PNG of
  0.2 MB peaks at 785 MB. A 16-bit grey PNG of 141 KB peaks at **2036 MB**. RGBA at 64 MP peaks at about 850 MB.
- The page server runs the same decode on every upload (`_upload_image`), so a small file costs the UI process about
  2 GB.
- DESIGN 2.16 and art.py say "about 192 MB once decoded".
- Fix: scale in integers, `(np.asarray(img).astype(np.uint32) + 128) // 257` then `astype(np.uint8)` (or float32 in
  place). Correct the 192 MB figure to the real peak.

### Test gaps

**t1. Palette or LA transparency onto black is untested.** Removing `or (img.mode == "P" and "transparency" in
img.info)` from `_rgb` leaves test_art.py green (16 passed). The same goes for dropping "LA" (only RGBA is tested). With
that branch gone, a palette PNG's transparent area takes its palette colour (white in my probe), which contradicts the
docs. Fix: add P+tRNS and LA cases to `test_transparency_goes_on_black...`.

**t2. (minor) The `returncode == 0` check in `embedded_picture` is unguarded.** `return got.stdout or None` survives
too. It is harmless, since partial output fails decode and becomes the warning. Leave it, or drop the check.

### Checked, fine (evidence)

- **Modes and formats.** CMYK, I;16, 1-bit, L/RGB with tRNS, animated WebP and APNG (first frame), and MPO all
  decode. GIF, TIFF, BMP, empty and truncated input are an InputError. Bombs: 900 MP gives "over the limit" via
  DecompressionBombError, and 81 MP is caught by the size check.
- **Metadata.** For JPEG, PNG and WebP sources with EXIF/GPS, ICC, XMP and comments, the output holds only APP0, DQT,
  SOF, DHT and SOS. The orientation is applied, and two runs give the same bytes.
- **Embedded pictures** (ffmpeg 6.1 and imageio 7.0.2):
  - an MP3 with Other + Front takes the front;
  - M4A covr works, and so does an MKA image attachment;
  - an MP4 whose only video is real gives none, and with a real video plus a cover it takes the cover;
  - a fake "Stream ... (attached pic)" line inside a tag cannot be injected (ffmpeg prints the control character as
    "?").
- **Mutations caught** (16/20; the other two survivors are equivalent):
  - in art.py: dropping the attached-pic check, the bomb catch, the 16-bit scale, the crop or the stale-file unlink;
    loosening the pixel limit or the byte limit by one; narrowing the embedded catch;
  - on the server: the kind check, the art name check, art shown unconditionally, raw ids passed through, the
    upload's decode skipped;
  - in jobs.py: the image flags, and a path leaked in as_dict;
  - pipeline.json options holding a path;
  - the JPEG magic in diagnostics.
- **Docs.** `album.jpg` and `background.jpg`, the .png/.jpg/.jpeg extensions and Settings > Gameplay > "Use Song
  Backgrounds" match brief §8 (CH wiki and YARG). The guide's bullet is in section 5. README, DESIGN 2.16 and
  PROGRESS match the code.

### Notes (no change asked)

- `songcharter assemble` with a config's `background` (new key) copies the file as it is, EXIF included, as the
  config's `album_art` always did (documented "copied as they are"). Only the chart and the page re-encode.
- The uploaded original, EXIF and all, stays in `uploads/` until the 7-day prune. Its safe file name appears in the
  job log's command line and the ui log, and so in the diagnostics bundle's logs, as a song's name already does.
- A picture re-chosen while the first is still uploading: the later answer wins, so a slow first upload can overwrite
  the second choice (app.js `uploadPicture`). This is cosmetic.
