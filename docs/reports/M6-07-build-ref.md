# M6-07 report: build_ref reads every package; the 20-song set's refused charts rebuilt

Branch `m6-07-build-ref`, worktree <wt>/m6-07, one commit on origin/main 8a93698 (main had not moved at the
end): `8cb9567` "build_ref reads every package: the chart by exact name, a MIDI mido refuses stripped byte for byte".
Pushed (the branch only). Songs are named by id, charts by md5 prefix. No lyric, title, artist or charter is in this
report; the diff and the commit message were scanned for them (and for audio, model names apart from the attribution
trailer, personal details and paths): nothing found, and `EVAL_DATA=$DEV/eval python3 -I
eval/privacy_check.py` exits 0 ("268 files, 14 md5s and 37 names checked, 0 found").

## Diagnosis (each refused package, unpacked into /dev/shm; classes, step and counts only)

The step that failed, in all eight: `strip_lyrics.py` (the subprocess `build_ref.py` runs), at `mido.MidiFile(path)`,
`ValueError`. None of the eight carries a backup file: each holds `notes.mid` as its only chart-like file. build_ref
picked it by exact name already, so the chart pick was not the cause.

| package | strict mido | mido clip=True | what the file holds (counts from a raw walk) |
|---|---|---|---|
| s01 <md5> | ValueError (data byte) | loads | 2 Phase Shift sysex with difficulty byte 0xFF; bytes after the last declared track |
| s05 <md5> | ValueError | loads | 10 such sysex; bytes after the last declared track |
| s07 <md5> | ValueError | loads | 2 |
| s06 <md5> (alt) | ValueError | loads | 2 |
| s08 <md5> | ValueError | loads | 6 |
| s10 <md5> (alt) | ValueError | loads | 4 |
| s11 <md5> (alt) | ValueError | loads | 2 |
| s13 <md5> | ValueError | EOFError (PART BASS track) | 10 such sysex, and 217 channel events in running status straight after a sysex |

- **The common cause**: a Phase Shift sysex `50 53 00 00 FF <type> <on/off> F7` is the tap/open marker "for every
  difficulty"; its difficulty byte is 0xFF, a data byte over 127, which mido refuses. No channel message in any of the
  eight has a data byte over 127.
- **clip=True is not a fix.** It loads seven of the eight, but it writes the byte as 0x7F, and scan-chart reads the
  sysex's byte 4 as `255 -> "all"`, else as an index into the four difficulties: 0x7F is undefined and scan-chart
  exits 1 on the saved file (all seven, checked). So the brief's first suggestion would have built charts scan-chart
  cannot read.
- **s13** is a second, different failure: midi-file (scan-chart's parser) keeps the running status across a
  sysex or meta event, as real tools write it; mido makes the sysex the running status and reads the next data byte as a
  sysex length, so the bass track runs off its chunk: EOFError, with or without clip.
- The tracks are complete in all eight (declared sizes match; the header's count is right, with extra bytes after the
  last track in two), so no truncation.
- **The four-song set's two refused pm2 alts** are not in its `stress.local.json` (the list says 5 charts, all built);
  their packages are the two orphan `.sng` files in `$EVAL_DATA/sng/`: `14cd04` (carries `notes.mid.backup` and
  `song.ini.backup` beside `notes.mid`) and `a3ce70`. Both match the pm2 primary's name and artist (normalised
  comparison; one length differs by 75 ms). Both fail the same way (strict ValueError, the 0xFF sysex): the backup file
  was not the cause there either, build_ref ignored it by exact name. Dry run of the real `build_ref.py` into /dev/shm
  (then deleted), numbers only: `14cd04` builds (notes.mid, strip dropped tracks=1 events=0, 8 stems summed, 0 skipped,
  441 s, guitar+bass+drums, 3715 Expert guitar notes); `a3ce70` builds (1 stem, 443 s, guitar only, 3868 Expert guitar
  notes). So both would build now. I left the four-song set as it is (`$EVAL_DATA=$DEV/eval` untouched).

## The fix

- `eval/refs/strip_lyrics.py`: `strip_mid` no longer reads the file into mido. It walks the MIDI event by event with
  midi-file's rules (running status kept across sysex and meta events; the header's track count bounds the tracks read;
  bytes after the last track not read) and copies every byte but (a) the tracks named PART VOCALS, HARM1-3, PART HARM*
  (the first track-name event, as mido's `track.name`), and (b) the lyrics meta events, whose delta goes to the next
  event so every other event keeps its time. The new header carries the kept tracks' count. A broken file (no MThd,
  no MTrk, running status before any status byte, an event running past its track, an unknown status byte) raises
  `ValueError` with a message that holds no chart text, instead of writing part of a chart.
  `strip_chart` (.chart) is unchanged.
- `eval/refs/build_ref.py`: `pick_chart(files)`: exact names only, `notes.mid` before `notes.chart`. A package with both
  gets `notes.mid`, because scan-chart's `scanChartFolder` orders a `.mid` before a `.chart` (checked in
  scan-chart 8.0.1's `findChartData`); `build_meta.json` then names the other as `chart_not_used`. A
  `notes.mid.backup`, `notes.old.mid`, `Notes.MID` or `song.mid` is not a chart. A package with none stops with a
  message (`SystemExit`, not an assert) before any audio work. The ref folder holds one chart file, so `scan.cjs
  --notes` (which takes `notes.chart` first by directory order) is not affected.
- `eval/README.md`, Stress songs: one paragraph on what build_ref now accepts.

Evidence the stripped file reads as the original (script over the packages, numbers only):
- The eight refused packages: scan-chart's reading of the new strip equals its reading of the original for every
  non-vocal track (notes, flags, star power, solos), tempos, sections and time signatures; `noteCounts` equal;
  tap and open counts equal (e.g. 130 taps/964 opens in s01); `hasLyrics` true -> false.
- The sixteen `notes.mid` refs already built by the mido route (the other 26 built charts are `notes.chart`): the new
  strip gives a byte-identical `ref_notes.json` for all sixteen.

## Tests (made-up bytes: tests/test_eval_stress.py, after the existing build_refs test)

Nineteen new test cases (the 20 the break runs select include the existing build_refs test); the MIDI is built by hand from bytes (a tempo track, a guitar part with a tap marker whose
difficulty byte is 0xFF, a note and then a program change in running status straight after a sysex, a lyrics event,
two vocal tracks with made-up words, bytes after the last track):
- `test_strip_mid_drops_the_vocal_tracks_and_lyrics_events_and_changes_no_other_byte` (byte-exact expected output);
- `test_strip_mid_gives_scan_chart_the_same_notes_and_taps_as_the_original` (the 0xFF marker still read as "all");
- `test_the_made_up_midi_is_one_that_mido_refuses` (guards the data: ValueError strict, EOFError with clip=True);
- `test_strip_mid_refuses_a_broken_file_instead_of_writing_part_of_it` (5 cases);
- `test_pick_chart_takes_notes_mid_or_notes_chart_by_exact_name` (5 cases, incl. both files and the backups) and
  `test_pick_chart_refuses_a_package_with_no_chart_of_those_names` (3);
- `test_build_ref_builds_a_midi_mido_refuses_and_ignores_a_backup_beside_notes_mid`,
  `test_build_ref_with_both_chart_files_takes_notes_mid_and_names_the_other`,
  `test_build_ref_without_a_chart_stops_before_the_audio_work` (the real `build_ref.py` over a made-up package).

Breaks (each applied alone, the 20 tests run, then restored; all 20 pass again):
- strip_lyrics.py back to the mido version: 9 cases fail (strip bytes, scan-chart, broken-file, both build_ref tests);
- a dropped lyrics event loses its delta: 3 fail; a sysex cancels the running status: 4 fail; a sysex becomes the
  running status (mido's way): 4 fail; vocal tracks kept: 2 fail; lyrics events kept: 2 fail; track count not
  rewritten: 2 fail; reading chunks to the end of the data (the trailing bytes): 4 fail;
- `notes.chart` preferred over `notes.mid`: 2 fail; any `notes.*` file counts as a chart: 5 fail; the unused chart not
  named in the meta: 1 fails; the chart pick moved after the audio work: 1 fails (the no-chart test).
- One break did not fail at first: "a sysex becomes the running status" passed while the running-status event after it
  had two data bytes (the sizes coincide). I added a program change (one data byte) after a sysex to the made-up
  guitar part, and that break then fails.

## Suite and CI

- Full suite, `tools/heavy.sh` with the worktree on PYTHONPATH (the shared venv's editable install points at an older
  checkout), SONGCHARTER_SCAN_CHART set: `1084 passed, 6 skipped in 683.02s`; the skips are the LnkParse3 ones and
  other environment skips, none in my tests.
- CI: `gh workflow run ci --ref m6-07-build-ref`: <repo>/actions/runs/42298957604,
  head `8cb956734ecf8d681e134feb9ec6ef6fd94c4614` (equal to the branch head), conclusion success, both jobs green.
  Linux "Suite": `1086 passed, 4 skipped in 336.54s`, none of the skips mine. No CI hook added: the change is an eval
  tool and its tests run in the suite.
- On the coordinator's message about my suite: it did run inside heavy.sh. `<shm>/songcharter-heavy.lock.who` named
  my pytest (pid 28561, taken 21:50:47Z) while the lock was mine, and the golden run (pid 28624, 19 MB resident) was
  waiting for it and took it at 22:02:12Z, after my suite ended. My detached `nohup` launches were the problem (I had
  queued the dry run, the build and the suite that way); I killed my one remaining detached queued job and ran the
  scoring as a tracked background task through heavy.sh.

## The 20-song set rebuilt (`$DEV/eval-set20/`)

The parts count (the measurer's parts.py) rerun over all 50 packages: identical to the measurer's counts.json (no
errors). With the eight packages no longer excluded, lists.py (same rule: most parts, ties more Expert guitar notes)
gives: 50 charts in 13 songs; the primary changes in five songs, a chart is added to three:

| id | charts (was) | primary (was) | primary's parts | Expert guitar notes |
|---|---|---|---|---|
| s01 | 4 (3) | <md5> (<md5>) | guitar, bass, rhythm, drums, vocals | 1539 |
| s05 | 6 (5) | <md5> (<md5>) | guitar, bass, rhythm, drums, vocals | 983 |
| s07 | 4 (3) | <md5> (<md5>) | guitar, bass, drums, vocals | 1921 |
| s08 | 6 (5) | <md5> (<md5>) | guitar, bass, rhythm, drums, vocals | 2146 |
| s13 | 2 (1) | <md5> (<md5>) | guitar, bass, drums, vocals | 777 |
| s06 | 4 (3) | <md5> (same); <md5> added as an alt | drums, bass, guitar, keys, vocals | 2288 |
| s10 | 4 (3) | <md5> (same); <md5> added | drums, bass, guitar, vocals | 1384 |
| s11 | 5 (4) | <md5> (same); <md5> added | drums, bass, guitar, vocals | 1503 |

The other five songs (s04, s02, s09, s12, s03) did not change.

How: `set20.json` and `stress.local.json` rewritten by lists.py (old copies in the scratchpad `m607/backup/`); for the
five songs whose primary changed, the old primary's built files were moved into `alt/<old md5>/` (the same files an
alt build makes, so not rebuilt), then the exact command from the brief with EVAL_PY and SONGCHARTER_SCAN_CHART set,
from the worktree: `EVAL_DATA=$DEV/eval-set20 STRESS_LOCAL=... STRESS_JSON=... tools/heavy.sh
eval/build_refs.sh --set stress`. It built the eight new charts (every other folder had its `ref_notes.json`) and
printed `ok` for all 50, no error. Each new chart: `chart_file notes.mid`, `lyric_strip dropped tracks=1 events=0`, 7-8
stems summed, 0 skipped, `hasLyrics` false, Expert guitar notes equal to the parts count's. (The build's final
make_songs_json step prints each song's title, artist and charter to stdout: do not paste a build log.)

Humans' ceiling (the measurer's measure.py, my copy `m607/measure2.py`: only what changed redone; reused entries are
the measurer's own numbers for an unchanged primary and alt, matched by md5; each alt vs the primary, Expert, F1@50
on onsets, 30 s windows):

| id | alt | beat F1 | guitar | bass | drums | missing |
|---|---|---|---|---|---|---|
| s01 | <md5> (old primary) | 0.704 | 0.969 | 0.980 | 0.984 | - |
| s01 | <md5> | 0.407 | 0.450 | - | - | bass, drums |
| s01 | <md5> | 0.173 | 0.634 | - | - | bass, drums |
| s05 | <md5> (old primary) | 0.500 | 0.406 | 0.410 | 0.871 | - |
| s05 | <md5> | 1.000 | 0.918 | 0.998 | 0.969 | - |
| s05 | <md5> | 0.967 | 0.943 | 0.999 | 0.977 | - |
| s05 | <md5> | 1.000 | 1.000 | 1.000 | - | drums |
| s05 | <md5> | 0.467 | 0.428 | - | - | bass, drums |
| s07 | <md5> (old primary) | 1.000 | 0.922 | 0.978 | 0.997 | - |
| s07 | <md5> | 0.364 | 0.679 | - | - | bass, drums |
| s07 | <md5> | 0.984 | 0.927 | - | - | bass, drums |
| s06 | <md5> (new) | 0.853 | 0.868 | 0.939 | 0.994 | - |
| s06 | <md5> | 0.856 | 0.446 | 0.271 | 0.316 | - |
| s06 | <md5> | 0.327 | 0.440 | 0.369 | - | drums |
| s08 | <md5> (old primary) | 1.000 | 0.978 | - | - | bass, drums |
| s08 | <md5> | 0.427 | 0.491 | 0.505 | - | drums |
| s08 | <md5> | 0.352 | 0.671 | - | - | bass, drums |
| s08 | <md5> | 0.437 | 0.532 | - | - | bass, drums |
| s08 | <md5> | 1.000 | 0.976 | - | - | bass, drums |
| s10 | <md5> (new) | 0.436 | 0.778 | 0.563 | 0.863 | - |
| s10 | <md5> | 0.293 | 0.408 | - | - | bass, drums |
| s10 | <md5> | 0.792 | 0.874 | - | - | bass, drums |
| s13 | <md5> (old primary) | 0.386 | 0.887 | 0.971 | 0.990 | - |
| s11 | <md5> (new) | 1.000 | 1.000 | 1.000 | 0.980 | - |
| s11 | <md5> | 0.443 | 0.630 | - | - | bass, drums |
| s11 | <md5> | 0.313 | 0.457 | - | - | bass, drums |
| s11 | (6-fret guitar only) | unscored | | | | |

- s13 now has a ceiling (two charts): the two charts' tempo maps differ (beat F1 0.386) but their parts agree
  (guitar 0.887, bass 0.971, drums 0.990). s08's primary now has bass and drums.
- Owner-audio alignment (eval/stress.py align's rule: most windows peak >= 0.3 and MAD < 2 ms), redone for the five
  songs whose primary changed (the ref input differs): none is aligned: s01 lag -2234 ms, 3/9 windows, MAD 90 ms;
  s05 -4375 ms, 7/9, MAD 50 ms; s07 -2808 ms, 0/9, MAD 38 ms; s08 +8651 ms, 8/9, MAD 39 ms; s13 -469 ms,
  5/9, MAD 76 ms. (s06, s10, s11 keep the measurer's numbers: same primary.) Raw numbers:
  `<scratchpad>/m607/measure/measure.json`.
- Two entries are not new information: s11 <md5> and s05 <md5>/<md5> score beat F1 1.0, the same chart
  uploaded twice with small differences.

Disk: eval-set20 now 4.2 GB (3.6 GB before), `/` has 8.5 GB free; /dev/shm scratch deleted.

## Not done / uncertain / noticed

- Not done: no change to `eval/lyrics_timing.py`, which reads a package's chart with strict mido (line ~79) and would
  refuse the same 0xFF-sysex MIDIs; it ran on the pm2 primary, which loads. Out of scope; worth a look before the lyrics
  check is run on another package.
- `tools/scan-chart/scan.cjs --notes` takes `notes.chart` before `notes.mid` by directory order while `scanChartFolder`
  (what Clone Hero-style tools read) prefers `.mid`; harmless for build_ref (one chart per ref folder), not for any
  other caller that scans a folder holding both.
- I did not edit PROGRESS.json, the work orders, PIPELINE or docs/reports/. The PROGRESS deferred item "[M5-09]
  build_ref fails on two packages ... a notes.mid.backup beside notes.mid ... Make build_ref ... mido clip=True" is
  resolved by this order, but with a different fix than clip=True and a different cause than the backup file (both
  stated above); the orchestrator should word that item's closure accordingly.
- Reused old-primary folders (s01, s05, s07, s08, s13) hold a `ref/notes.mid` written by the old
  mido strip; their `ref_notes.json` is byte-identical to what the new strip gives (checked for the sixteen mido-built
  `notes.mid` charts).
- `songs.json`'s alt labels (`alt1`..) follow the new list order, so a label names a different alt than in the
  measurer's report for the songs whose primary or alt list changed; compare by md5 prefix.

## Review fixes (orchestrator, commits e801e16 and 46cdf3c)

- **The build's stdout** (e801e16, found by the builder): `make_songs_json.py` printed each song's artist, title and
  charter, and the build's "ok" lines each package's md5 prefix. They now print the id and numbers only; the
  two-song build test asserts it (each old print fails it).
- **T1** (46cdf3c): one made-up file pins the strip's privacy rule (each vocal name in odd case and spacing, a name
  after another event, a second name that is vocal, EVENTS text and markers, a channel pressure with a lyric after
  it, an F7 event, an 8-byte header), byte for byte; the review's nine breaks each fail it (the channel pressure's
  only once a lyric follows it: the walk copies every byte, so a misread length shows only where it drops one). A
  track now goes when any of its name events names a vocal track (it was the first, mido's `track.name`;
  scan-chart reads the last at tick 0): over the 36 notes.mid packages of the stress, reference and 20-song sets the
  stripped files are byte-identical either way.
- **T2** (46cdf3c): the docstring says the walk fails loudly (ValueError) on a truncated event or an unterminated
  number, where midi-file reads on; no package of either set has one.
- CI on 46cdf3c: green (run 42306856010).
- In this report the 20-song set's songs are `s01`-`s13` and its packages `<md5>`: the set's ids spell its titles,
  which stay in the owner's local list until he says otherwise.

## Review (sc-reviewer, 2026-11-06; head e801e16, the change 8cb9567)

No walker defect found. One test gap (T1, proved by breaking), one minor (T2).

Lens 1 (walker): read midi-file 1.2.4 (parseTrack: no stop at EndOfTrack, running status kept across F0/F7/FF, set by
channel events only, ntrk bounds the chunks, Phase Shift sysex data bytes unchecked). A differential fuzz of 300
generated files (multi-byte deltas, running status after sysex/meta, F0/F7 events, lyrics first/last, second name events,
vocal/harm tracks with case/space variants, trailing junk): midi-file's absolute-tick events of the stripped file equal
the original's minus lyrics and vocal tracks, 0 mismatches, 329 tracks dropped. The walker is stricter than midi-file
(raises on a truncated event or an unterminated variable-length number where midi-file reads garbage), so it fails loudly
and never silently. A lyric as the very last event loses its delta (as the old code did; no event moves).
Lens 2 (privacy): first-name-event rule equals mido's track.name; vocal list, strip/upper and PART HARM* prefix are as
before; the old strip kept FF 01 text events too; none of the 24 outputs holds a vocal-named track or a lyrics event.
Not a regression: scan-chart takes a track's name at tick 0 (last known name wins), the strip the first name event, so a
track with two names could be vocals to scan-chart and kept by the strip; same as the old code.
Lens 3 (fidelity): all 24 notes.mid packages (13 primaries, 11 alts; ids s01, s02, ..., s13): the new strip
scanned gives a ref_notes.json byte-identical to the one on disk (the old route's for the unchanged songs, the rebuilt
s08 for the 8 new); scan-chart on the stripped file equals the original for every non-vocal track; only hasLyrics
(true to false) and metadataIssues (my stand-in song.ini) differ. Unpacked folders deleted.

## T1 (minor, test gap) the vocal-track rule and byte-for-byte claim are barely tested
tests/test_eval_stress.py covers only the names PART VOCALS and HARM1, no text events, no 0xD, no F7 status. Breaks in a
copy of strip_lyrics.py, then `pytest tests/test_eval_stress.py -k "strip_mid or pick_chart or mido"`: all stay green
(17 passed): drop `.upper()`; drop `.strip()`; HARM2/HARM3 removed from VOCAL_TRACKS; `startswith('PART HARM')` removed;
name check on the last name event instead of the first; name checked only at the track's start; FF 01 text events (and
FF 06 markers) dropped with the lyrics (this would erase the EVENTS track's sections); channel status 0xD treated as two
data bytes (in the first byte and in running status); status 0xF7 refused; header length ignored (head = 14).
Caught: 1-byte delta carry, ntrk not bounding, name check removed. Fix: one test file with tracks HARM2, HARM3,
"PART HARM3", " part vocals ", a text event and marker in EVENTS, 0xD and an F7 event, asserted byte for byte.
(A privacy rule that no test pins is what the strip exists for; the real packages do exercise the HARM tracks, so the
code is right today.)

## T2 (minor, doc) build_ref/README say a malformed chart is refused, but the walker also refuses what midi-file reads
A package with a truncated final event or an unterminated delta fails to build (ValueError), though scan-chart would read
it. None of the 50 does; the failure is loud. Optional: note it in the docstring.
