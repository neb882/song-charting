# M6-09: a chart you can hear (the builder's report)

Branch `m6-09-listen` (worktree `<wt>/m6-09`), from main at f780691; main merged in three times: 8e8cc51 (the order's
Release line) at 0973640; 20e067e (M6-10, v0.3.0's gate fixes; no conflict, none of this order's files) at 419640e;
a537912 (v0.3.0 published, docs only) at a01d2db, the final head. Nothing that charts changed: `listen.py` only reads a built folder through
`importers.read_song`, and `cli.py` gains a subcommand beside `chart`. No golden run, as the brief says. The version is
untouched (main's 0.3.0; the order ships in v0.3.1 after v0.3.0's tag, the coordinator's message).

## Commits

- 4ae338e M6-09: listen.py and `songcharter listen`: a chart you can hear
- 05a4260 M6-09: Listen on the Done screen
- 7360e55 M6-09 docs: DESIGN 2.17 (what each sound means) and the guide's "Listen to the chart"
- 9723d7c M6-09: the page test re-renders Listen for the next song's chart (the mutation pass's one survivor)
- 861cf57 M6-09: "Chart another song" stops the player; the older page test's stand-in DOM has the media methods
- 0973640 Merge origin/main into m6-09-listen (the order's Release line, PROGRESS)
- 578f117 M6-09: a render that cannot be written is said as such (no bug); --out expands ~ before looking for a folder
- bb43151 M6-09 docs: DESIGN 2.17's numbers from the golden song folder (peaks, lengths, onsets, time)
- 419640e Merge origin/main into m6-09-listen (M6-10: v0.3.0's gate fixes)
- a01d2db Merge origin/main into m6-09-listen (v0.3.0 published; docs only)

Each ends with the brief's two trailer lines.

## What changed

- **`songcharter/listen.py`** (new, numpy and ffmpeg only):
  - `render(folder, part, difficulty, tones_only=False, song_db=-12)` -> `Rendered` (audio (2, n) float32 at 44.1
    kHz, notes heard, notes left out, seconds, how far it was turned down). Times from `importers.read_song(folder)`
    (the folder's song.ini: tempo map, .chart Offset, song.ini delay), so the chart's 0 is song.ogg's 0; a tone starts
    on `round(time x 44100)`. Length = song.ogg's decoded length (tones-only without song.ogg: the last note's end + 2
    s); notes at or after the end are left out and counted.
  - `write(audio, path)`: OGG Vorbis q5 through ffmpeg with `-fflags +bitexact -flags +bitexact`, or 16-bit WAV
    (stdlib `wave`) for `.wav`; through `.<name>.<pid>.part` beside it, then `os.replace`. Another suffix: InputError.
  - `available(folder)`: `{part: [levels]}` with notes, in INSTRUMENTS/DIFFICULTIES order.
  - `cached(folder, cache, part, level)`: the page's; `<cache>/<part>-<level>-<16 hex>.ogg`, the hash of VERSION, part,
    level and the folder's notes.chart, notes.mid, song.ini, song.ogg (names, sizes, bytes). Older renders of that
    part and level are deleted after a new one is written.
  - `output_path(folder, out, part, level)`: `--out`, a folder in `--out` gets the default name, default
    `<cwd>/<folder name>-<part>-<level>.ogg`; any path inside the song folder (links resolved) is an InputError.
- **`songcharter/cli.py`**: `songcharter listen <folder> [--part guitar|bass|drums] [--difficulty
  expert|hard|medium|easy] [--out FILE] [--tones-only]` (`_listen`): prints the line (`listen: guitar on Expert, 1004
  notes over the song at -12 dB, 4:53`, plus left-out notes or a turn-down when there is one), the path and, in WSL,
  its Windows path. Exit 0; 2 for SongcharterError/OSError (no such folder, part or level, no song.ogg, an output in
  the song folder or not .ogg/.wav, ffmpeg failing) and argparse's bad choices; 3 a bug with its traceback; 130 Ctrl+C.
- **`songcharter/ui/server.py`**: `results()` gains `listen`: `{"parts": {...}}`, or `{"parts": {}, "why"}` when the
  chart cannot be read. `POST /api/jobs/current/listen {"part", "level"}`: part and level must be in INSTRUMENTS and
  DIFFICULTIES (else 400), the current job's `result` (ok or a failed gate: a look is what it is for) and its folder
  must exist; `listen.cached(folder, <work>/listen, ...)` under `App.listen_lock` (one render at a time); InputError
  400, ToolError/OSError 500 with why; records `App.listened = (job id, {"<part>-<level>.ogg": path})`; answers
  `{"url", "part", "level", "cached", "seconds"}`. `GET /api/jobs/current/listen/<name>`: the path only from that
  record, for the current job id; else 404. `_ranged`: one `bytes=a-b`, `a-` or `-n` range (206 with Content-Range;
  416 with `bytes */size` past the end; anything else the whole file, 200 with Accept-Ranges), so Chrome/Edge can
  seek. The module docstring lists both routes.
- **`songcharter/ui/static/`**: under the preview (after "No preview"), `#listen-box`: "Listen", a sentence on what
  the sounds are, Part and Level selects (the chart's parts, guitar first; the levels follow the part, keeping the
  level when the new part has it), the Listen button (disabled while it renders; "Making the Guitar on Expert into
  sound: a few seconds…"), then "Guitar on Expert, over the song. Listen for a tone that comes late or not at all,
  or tones where the song is quiet." and an `<audio controls>` playing `<url>?job=<job id>`. A refusal shows the
  server's message and no player; "Chart another song" and new results stop the player. CSS: `.listen-row`, `audio`.
  The CSP is unchanged (`default-src 'self'` covers media from the same origin).
- **Docs:** DESIGN §2.17 (what each sound means, timing, the mix, determinism, where files go, what is not done), a
  `listen.py` row in §2.0's table, a clause in §4.5's Status; the guide's section 5: "Listen to the chart".
- **Tests:** `tests/test_listen.py` (14 tests, new), `tests/test_ui_server.py` (+4 tests: renders/caches/serves,
  a failed gate can be listened to, an unwritable render says why, the page's control in node; the POST guard test
  covers the new POST; the older PAGE stub gains `removeAttribute`/`pause`).

## What each sound is

- **Guitar:** green C5 523 Hz, red E5 659, yellow G5 784, blue B5 988, orange D6 1175 (stacked thirds, a major ninth
  chord); open G4 392. **Bass:** the same an octave down (C4..D5, open G3). Panned green -0.4 to orange +0.4
  (constant power), open centre. A chord: its pitches together, each 1/sqrt(n).
  - The first build used C5 E5 G5 C6 E6: the chord test showed green's second harmonic at blue's pitch (an octave),
    so an octave chord fuses into one note by ear. Changed before the first commit; DESIGN says why.
- **Strum:** fundamental 0.22 with harmonics 2-4 (0.5, 0.25, 0.12, decaying faster), 1 ms raised-cosine attack,
  decay tau 0.16 s, 0.6 s long. **HOPO / tap:** 0.11, harmonic 2 at 0.2, 6 ms rise, tau 0.07 s, 0.35 s long.
  **Sustain:** the voice plus its fundamental held at 0.07 to the sustain's end, then a 40 ms release.
- **Drums:** kick a 150->52 Hz falling sine (tau 0.12 s) with a soft 200-3000 Hz click; snare 185 Hz body plus
  1.5-9 kHz noise (tau 0.07 s); toms falling pitched tones, yellow 294, blue 220, green 165 Hz; hi-hat (yellow cymbal)
  7-16 kHz noise, 0.15 s; ride (blue) 5-14 kHz noise with a 2.4 kHz ping, 0.8 s; crash (green) 3-15 kHz noise, 1.5
  s. Accent x1.3, ghost x0.45, an Expert+ kick a kick. Pads panned red -0.3 to green +0.3, kick centre. Noise from
  `default_rng([20261107, key])`, spectrum-shaped, its peaks rounded (tanh at 2.5 RMS).
- **Mix:** song x 10^(-12/20) plus the tones; past -1 dBFS the whole render is scaled to -1 dBFS once (never per
  note); the summary says by how much.

## Checks

- **The full suite** (dev container, on 0973640, the merged head before the last two commits, under the heavy-job
  lock): `SONGCHARTER_SCAN_CHART=<repo>/tools/scan-chart/scan.cjs SONGCHARTER_HEAVY_MIN_FREE_GB=1 tools/heavy.sh
  <venv python> -m pytest -q -p no:cacheprovider --basetemp=<shm>/pt-m6-09` -> `1137 passed, 6 skipped in
  799.34s (0:13:19)`, exit 0. The first run, on 7360e55, had `1 failed, 1136 passed, 6 skipped`: the older page
  test's stand-in DOM reached `stopListening` through `again()` without `removeAttribute` (fixed in 861cf57).
  After the last code commit (578f117), the affected files: `pytest tests/test_listen.py tests/test_ui_server.py
  tests/test_ui_jobs.py` -> `117 passed in 34.52s`. After merging M6-10 (419640e), this order's test files and
  the ones M6-10 changed: `pytest tests/test_listen.py tests/test_ui_server.py tests/test_engines_sections.py
  tests/test_assemble.py tests/test_beatgrid.py` -> `228 passed, 3 skipped in 202.64s`. CI ran the full suite on
  bb43151 and on the final head (below).
- **Tests of the tests** (`<scratchpad>/m6-09/mutate.py`, each break applied to a copy of the branch and its test
  file run): 61 breaks, 60 caught on the first pass; the survivor (the levels not re-rendered for a second job's
  chart) is now caught (9723d7c). Then 3 more breaks for 578f117 (OSError mapped as a bug, `~` not expanded, the
  song-folder refusal removed): all caught. The breaks, by what they cover:
  - timing: a 48 kHz start for frets, a +200 sample start for drums, `read_chart` instead of `read_song` (song.ini's
    delay lost);
  - pitches: blue as C6, the open note G5, the bass not shifted, no pan, a chord not scaled, a chord's first fret
    only;
  - sustains: none, released late (0.2 s), held as loud as the attack, ending at half its length;
  - HOPO/tap: HOPOs as strums, taps as strums, a HOPO as loud, as quick to rise, as long as a strum;
  - drums: cymbals as toms, toms one pitch, a crash as short as a hi-hat, a kick at 520 Hz, accents ignored, ghosts
    ignored, an Expert+ kick as a snare;
  - mix: the song at 0 dB, the song in tones-only, no ceiling, clipping instead of turning down, no bitexact flags,
    unseeded noise, the length from the chart, left-out notes not counted;
  - cache and CLI: a key without the folder's content, older renders kept, always rendering, any part accepted, a
    path inside the song folder allowed, the default name without the folder, `--out` folder ignored, empty levels
    listed, a bug exiting 2, `--tones-only` ignored;
  - server: any job's render served, a path built from the request (planted files in `listen/`), no ranges, a wrong
    suffix range, no 416, a range end not capped, any part string accepted, no `listen` in the results, a failed gate
    refused, renders not recorded, one render kept per job;
  - page: no part posted, no `?job=`, "Chart another song" not stopping it, the box shown without parts, the levels
    not following a new chart (the survivor, now caught), the player shown on a refusal, not played.
- **The real song folder** (`$DEV/golden/gate3-new/<song>`, read only; renders under /dev/shm, deleted after):
  `songcharter listen <folder> --part P --out <shm>/...` for each part, under the heavy-job lock:
  - guitar: exit 0 in 8.4 s, `listen: guitar on Expert, 1004 notes over the song at -12 dB, 4:53`; bass 9.0 s, 184
    notes; drums 8.2 s, 1315 hits. Each render 12904696 samples = song.ogg's 12904696 (292.62 s). Peaks 0.527, 0.443,
    0.776 (none turned down). The guitar rendered twice: the same SHA-256.
  - The first notes' times: on the unencoded tones (the render with a note minus the render without it), each of the
    first 8 notes of each part starts 0.013-0.032 ms after its chart time (the first nonzero sample of a sine started
    on the note's sample). Guitar's first notes at 6.733, 7.014, 7.294 s; bass 17.810, 18.651 s; drums 15.710 s
    (kick and a pad together), 15.990 s. On the encoded mix, the guitar's first tone shows +0.11 ms; later attacks
    measured against the song's re-encoded residual scatter by a few ms (Vorbis coding noise of the song, not the
    tones), so the unencoded figure is the one to trust.
  - Time: about 1.1 s decoding song.ogg, 0.2-1.5 s making the tones, about 4.7 s ffmpeg's Vorbis encoder.
- **The page's routes on that folder** (`<scratchpad>/m6-09/e2e.py`: a real `server.App` with a stand-in job whose
  result is that folder, the work folder under /dev/shm): results list all three parts with four levels each; POST
  guitar/bass/drums Expert -> 200, `cached: false`, 8.1/8.3/7.8 s; GET -> 200 `audio/ogg`, `Accept-Ranges: bytes`,
  4.69/4.56/4.87 MB starting `OggS`; `Range: bytes=1000000-` -> 206 with the right bytes; POST guitar again ->
  `cached: true`, 0.0 s; `listen/` holds the three `<part>-expert-<hash>.ogg`; the song folder still holds only
  notes.chart, report.json, song.ini, song.ogg.
- **Screenshot** (headless Chrome of the Done screen's markup with app.css, the control filled as the page fills it):
  `<shm>/m6-09/shot/done.png`, looked at: the heading, sentence, Part/Level side by side, the Listen button and the
  player in the page's style. It goes with the machine.
- **Not heard.** The builder cannot listen: "sounds right" rests on measurements (onsets, pitches, lengths, levels,
  no clipping). Someone should listen to one render on a real PC.
- **Privacy:** `EVAL_DATA=$DEV/eval python3 -I eval/privacy_check.py` before each push -> `privacy_check: 278 files,
  14 md5s and 37 names checked, 0 found`.
- **Scanned before the final push:** `git diff origin/main...HEAD` and the commit messages hold no lyrics, no audio
  (the tests make their audio in tmp folders), no model names apart from the trailers, and no personal details or
  machine paths (made-up "Made-Up Band", "Made-Up Song"; the golden song folder is not named in the branch). Note: the
  worktree's local `main` ref is stale (behind origin/main), so `git diff main...HEAD` shows other commits; the scan
  used origin/main.

### CI

- Run 42381733014 on 0973640: **success** (linux and windows),
  <repo>/actions/runs/42381733014. The suite there: `1139 passed, 4 skipped in
  448.37s` (the same 1143 tests as here; test_listen.py has no skip marker, and the node page tests run on the
  runner's Node 24). Hooks: `all 8 Linux hooks passed: 10-lanes.sh 14s 20-device.sh 6s 30-install.sh 145s 40-ui.sh
  29s 50-e2e.sh 390s 60-results.sh 72s 70-release.sh 57s 75-update.sh 149s`; `all 1 Windows hooks passed`.
- Run 42383984202 on bb43151: **success** (linux and windows),
  <repo>/actions/runs/42383984202. Suite `1140 passed, 4 skipped in 529.17s`;
  `all 8 Linux hooks passed`.
- Run 42386343024 on 419640e (M6-10 merged): **success** (linux and windows),
  <repo>/actions/runs/42386343024. Suite `1146 passed, 4 skipped in 541.09s (0:09:01)`; `all 8 Linux hooks passed`.
- Run 42388507540 on a01d2db (the final head: main's docs-only commits after v0.3.0's tag merged in): **success**
  (linux and windows), <repo>/actions/runs/42388507540. Suite `1146 passed, 4 skipped in 533.33s (0:08:53)`; `all 8 Linux hooks passed`.
- No hook of this order's own: the order's files do not include `packaging/ci/`, and its tests run in the suite.

## Choices the order did not spell out (for the reviewer)

1. **Lane pitches** C5 E5 G5 B5 D6 (not an octave set, see above), open G4, bass an octave down, mild panning by
   lane. The panning is an addition to "easy to tell apart".
2. **HOPO/tap "a shorter, softer attack"** read as a tone that is shorter and softer and rises more gently; taps sound
   as HOPOs (the order groups them).
3. **A sustain** = the plain note plus a held fundamental to the end, so a short sustain is never shorter than a plain
   note.
4. **Clipping:** fixed levels with headroom (a full-scale square song under 16th-note 4-fret chords stays under -1
   dBFS, tested), and a whole-render turn-down past -1 dBFS (said in the summary); no per-note limiter.
5. **`--tones-only` without song.ogg** works (the chart's end + 2 s); the mix needs song.ogg (exit 2).
6. **`--out` a folder** gets the default name in it; the same default name for tones-only and the mix.
7. **The page renders a failed-gate chart too** (its .failed folder is "for a look"); export/install still refuse it.
8. **The page's cache key** is the song folder's content (the work folder is per song and reused by a re-chart).
9. **Byte ranges** on the audio route, so the player can seek (Chrome does not seek media from a server without them).
10. **`song_db`** is a parameter of `render`, not a CLI option (the order lists the flags exactly).
11. **The guide bullet** names the page only (the friend uses the page, not the command).

## Not done, uncertain

- Not heard by a person; the levels' pleasantness over a whole song is a judgement from numbers (tones about as loud
  as the song at -12 dB in RMS, attacks above it).
- Safari/old browsers without Ogg Vorbis would not play the page's file; the friend's Windows browsers (Edge, Chrome)
  do [inference, not tried on Windows].
- Not run on Windows/WSL: the render's speed there, ffmpeg's bitexact output from the imageio-ffmpeg build.
- The same bytes hold on one machine; another ffmpeg/libvorbis version may encode differently.
- `listen_lock` (one render at a time) has no test of its own.

## Doc edits left to the orchestrator

- PROGRESS: M6-09 in/out of `in_flight`; nothing deferred by this order beyond the "Not done" list above.
- This report into `docs/reports/`.

## Review fixes

The review (`m6-09.review.report.md`, a01d2db against a537912): no major, five minors, all fixed in 19b0bee and
d3ff878 (head d3ff878). Each new test was run against its finding's break, in a copy of the branch: every break fails
its test.

- **R1 (code + test): the song folder under a name resolve() cannot see.** `listen.inside` now returns why or None,
  in two checks: the resolved path under the resolved folder (as before), then each existing parent of the output
  (the path itself first) compared with the song folder by identity, `os.path.samefile` (device and inode), which
  sees the folder in another case on a case-insensitive drive (WSL's /mnt/c) or through a bind mount. Its message
  names the alias: "<path> is inside the song folder (<parent> is the song folder under another name): Clone Hero
  reads ...". DESIGN 2.17 and the module docstring say so. Test
  `test_an_output_in_the_song_folder_is_refused_under_any_name`: a link to the song folder with `Path.resolve` made
  blind (the stand-in for drvfs's case or a bind mount, which a test on a Linux runner cannot make), `--out
  link/x.ogg` and `link/new/x.ogg` (a folder not there yet) refused with that message, and the command exits 2;
  a path elsewhere still accepted; the song folder unchanged. Break: the identity check removed (`if False:`) ->
  "DID NOT RAISE InputError".
- **R2 (test): the render lock.** `test_two_renders_of_one_part_at_once_both_answer` (test_ui_server.py): two
  threads post the same part and level at once, the render slowed by 0.5 s; both answer 200, one `cached: false`
  and one `cached: true`, one render, one file in `listen/`. Break: `with app.listen_lock:` -> `if True:` -> fails
  (both requests render; the reviewer's race showed one of them failing on the shared `.part` file).
- **R3 (test): the temporary file.** `test_a_render_that_fails_half_way_leaves_nothing_to_serve`: an encoder that
  writes half a file and raises leaves `listen/` empty (and `write` leaves neither the file nor a `.part`); the next
  `cached()` renders whole. Break: writing straight to the final name (no temp, no `os.replace`) -> the half file is
  there ("assert [...ogg] == []").
- **R4 (test): links and `..`.** The same test: `link/x.ogg`, `link` (a folder: the default name in it) and
  `here/../s/x.ogg` are refused with the resolved check's message ("is inside the song folder:", no "another
  name"). Breaks: resolve() dropped (`path.relative_to(folder)`) -> fails (the identity check still refuses, but with
  the other message, which the test tells apart); both checks dropped -> "DID NOT RAISE".
- **R5 (test): the cache key.** `test_the_pages_cache_follows_song_ini_and_song_ogg`: a song.ini given a delay, then
  a new song.ogg, each renders again (and the older render goes); asked again, it is cached. Break: hashing only
  notes.chart and notes.mid -> fails ("assert (not True)").

Checks: `pytest tests/test_listen.py tests/test_ui_server.py` -> `81 passed in 34.43s` (the other files unchanged
since the last full suite and CI). Privacy check before the push: `280 files, ... 0 found`; the branch's diff
scanned again (no machine paths, lyrics, audio or model names). CI run 42391675815 on d3ff878:
<repo>/actions/runs/42391675815, success (linux and windows): 1150 passed, 4 skipped in 534.02s (0:08:54);all 8 Linux hooks passed: 10-lanes.sh 13s 20-dev.

## The review


No major finding. The render matches what the chart says, the server holds, the bytes repeat. Four checks can be
gutted with every test still passing, and one path guard has a gap.

Lens 1 (sound vs Clone Hero): no difference found. listen.py uses TimedNote.hopo, which importers sets from the
natural rule plus forcing (scan-chart-matched), so natural HOPOs, flips, chords and taps come out as Clone Hero reads
them (breaking it to `hopo_forced or tap` fails the natural-HOPO test). Sustain ends come from sec(tick+length)
through the tempo map. Cymbal vs tom comes from the markers. Times are song seconds with Offset/delay.
songcharter never writes Expert+ kicks.
Lens 2: ranges are correct and tested. The audio GET is a lookup in a dict, and no path from it reaches the disk.
Garbage charts give InputError, so exit 2 and the results stay up. ffmpeg comes from $FFMPEG, then PATH, then
imageio-ffmpeg; missing, it gives ToolError (exit 2 / HTTP 500).
Lens 3: a real 4:03 reference folder rendered twice each for guitar and drums, with the same sha256 each time, in
7.8-8.3 s. Fine.
No charting-path file is in the diff.

### Findings

- **R1 minor**, songcharter/listen.py:378-384 `inside`: resolve() does not see through aliases it cannot resolve.
  That includes case on a case-insensitive file system (drvfs /mnt/c, the friend's Songs folder) and bind mounts.
  So `listen .../Songs/MySong --out .../songs/mysong/x.ogg` writes into the song folder. The same happens with the
  default name when the current folder is the song folder spelled in another case. Repro (bind mount as the case
  stand-in): output_path(race/s, alias/x.ogg) gives `<shm>/review_m609/alias/x.ogg` (accepted). Fix: compare
  st_dev/st_ino (os.path.samefile) of the folder with each existing parent of the output.
- **R2 minor (test)**, ui/server.py `listen_lock`: replacing `with app.listen_lock:` with `if True:` leaves 19/19
  listen tests green. It would ship a real defect. Without the lock, two concurrent cached() calls for one part and
  level (two tabs) share the same `.<name>.<pid>.part` temp file. Repro race.py, 5/5 trials: `[('ok', False), ('err',
  "FileNotFoundError: ... listen/.guitar-expert-c46b5f6cc...")]`, which the friend would see as a 500.
- **R3 minor (test)**, listen.py `write`: writing straight to the final name (no temp file, no os.replace) leaves the
  tests green (19 passed). A render that fails or is killed half-way would then leave a partial
  `<part>-<level>-<key>.ogg`, and cached() would return it as "rendered before" from then on.
- **R4 minor (test)**, listen.py `inside`: dropping resolve() (`path.relative_to(folder)`) leaves the tests green,
  and a symlink into the song folder is then accepted: `b <shm>/review_m609/link/x.ogg` (the unbroken code
  refuses it). No test uses a symlink or `..`.
- **R5 minor (test)**, listen.py `cache_key`: hashing only notes.chart and notes.mid (dropping song.ini and song.ogg)
  leaves the tests green. A re-chart that changed only song.ini's delay or song.ogg would serve the old render.

The orchestrator's routing: all five minors fixed by the builder (the "Review fixes" section above), CI green on d3ff878; merged at fa26677 for v0.3.1.
