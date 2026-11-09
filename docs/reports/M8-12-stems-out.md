# M8-12: the stems as files of their own, and Clone Hero's multitrack audio (builder's report)

*Merged 2026-11-09 at df71e82 (branch head 3005a28; CI run 42590187310 green on Linux and Windows, all nine hooks; the
full suite 1348 passed; the golden references rerun after the review's fixes: notes.chart and song.ini byte-identical
on all seven, every score and gate unchanged, only the audio split). The owner's decision: "make the muting default,
but optional". The review: two `sc-reviewer`s on head e62c49d, one lens each, eight minor findings and no major one.
Lens A (the audio, the gate, the package): A1 the sum check and the per-file length check each breakable with the
tests green; A2 a split file more than 100 ms late passing the per-file check; A3 a stranger's multitrack folder
accepted as `--out` and its audio replaced; A4 preview.ogg and crowd.ogg kept out of the music untested. Lens U (the
export, the page, the queue): U1 a full disk while saving the stems failing the whole chart after it was built; U2 and
U3 the foreign-files refusal and the cancel cleanup's escaping untested; U4 every "Download the stems" leaving a
190 MB copy behind. All fixed (below). The play test of the drop-out on a miss is the release gate's.*

Branch `m8-12-stems-out` (worktree `<wt>/m8-12`), from main at 5ce2b06. Built 2026-11-09 by `sc-builder`.

## Commits

- 1859f37 M8-12 part B: Clone Hero's multitrack audio in the song folder
- 3677877 M8-12 part A: the stems saved as FLAC beside the song folder; --stems, --one-audio
- e42db60 M8-12: the page's Audio options and "Download the stems"
- ce28784 M8-12: test_chart_events expects the result event's stems (null without --stems)
- 7a1d36a M8-12: a split file is out of sync only when a lag correlates clearly better than none
- e62c49d M8-12 docs: DESIGN 2.2, 2.13 (with creep's numbers), 4.5; the friend's guide; PROGRESS's in_flight entry

## What was built

**Part B (on by default).** `package.build_song_folder(split=...)` writes `guitar.ogg`, `bass.ogg`, `drums.ogg` from
the stems of the parts charted and `song.ogg` = the decode less those stems (residual, vocals, piano, other stay in
it), each with the same pad, length, rate and Vorbis quality. assemble's config key `split_audio` (default false, so
`songcharter assemble` and its tests are unchanged); the pipeline sets it to `not one_audio`. A part not charted gets
no file (a warning if a charted part has no stem). report.json: `audio_files`, `sync.of`, `sync.files`.
- Sync: the decoded files summed against the padded decode, the same rule as one song.ogg's; each split file against
  its own samples: its length, and no window "shifted" (a lag of 1+ samples at correlation >= 0.9 that is also 0.05
  better than the same window at lag 0). The margin came from the screens' stand-in: a pure sine stem read as "4410
  samples off" (a period away correlates as well as no lag), which would have failed a real chart with a steady tonal
  stem. Tested both ways.
- The gate's audio rule is now scan-chart's (`assemble.audio_file_issues`): each audio file a name Clone Hero reads,
  no name twice, one of them the song's music. The old rule (exactly one audio file) failed a split folder.
- Every .ogg written through `audio.encode_ogg` gets `-fflags +bitexact -flags:a +bitexact` (the Ogg serial was
  random run to run); listen.py's renders had these flags already.
- Readers: `audio.song_audio_files` / `decode_song_audio` (the names Clone Hero reads, preview and crowd aside).
  Listen renders over the files summed and its cache key hashes every audio file; the preview's end of audio is the
  longest file. eval/scorer already sums a folder's audio (`load_mix`); checked, unchanged. `check_gate.py` needs
  song.ogg, which a split folder still has; unchanged. The install copies every file (`copy_contents`); CI's hook
  checks the installed folder holds the split files.
- `--one-audio` and the page's "One audio file: the music does not drop out on a miss" write today's single file;
  `OUTPUT_FILES` now lists guitar/bass/drums.ogg, so a one-file build over a split one removes them (tested).

**Part A (off by default).** `--stems` / the page's "Also save the separated instruments (stems)": a "stems" stage
after assemble (before the preview and the cache's prune) reads the separation cache's six WAVs and writes 24-bit
FLAC (`audio.write_flac`: soundfile into memory, written as one file, clipped to +-1) into `"<song folder> (stems)"`
beside the song folder, through a hidden `.partial` staging folder that replaces it at the end.
- Refused before any audio work: a stems folder holding anything but our six .flac (`check_stems_folder`).
- Too little free space for the estimate (`stems_bytes`: 24-bit PCM x STEMS_FLAC_SHARE 0.5) or ENOSPC/EDQUOT while
  writing: an InputError naming the folder and the MB needed; the staging folder removed; the chart stays. (Exit 2,
  per the order: the run's result is the error, so the page shows the error rather than the Done screen.)
- The result event and the summary name the stems folder; pipeline.json `stems` {folder, files, bytes, seconds}.
- A cancel deletes the stems' staging folder too (`jobs.partial_folders`).
- The stems are written whether or not the gate passed (they do not depend on the chart), named after the output
  folder, not `.failed`.

**The page.** An "Audio" fieldset under Guitar (not folded) with both options and plain lines; the stems line gives
the disk for the song's length (0.79 MB/s: "About 191 MB of disk for this song" at 4:00; the songs' sum in the shared
form; "about 190 MB for a 4-minute song" when a length is unknown). Both options are per song (`ChartOptions`, the
command's flags, queue.json keeps them; tested). Done screen: "The instruments" (outside "Play it", so a failed check
still offers them) with count, size, folder name and "Download the stems" -> `POST /api/jobs/<ref>/export/stems`
(clonehero.export_zip of the stems folder: `<name> (stems).zip`, ZIP_STORED), 400 with why when none or gone. The
progress shows "Save the stems". The zip line now says "the song's sound" instead of "song.ogg".

## Checks

- **Full suite** (`tools/heavy.sh`, `--basetemp=<shm>/m812/suite`): `1 failed, 1340 passed, 6 skipped in
  1304.69s`; the one failure was `test_chart_events` expecting the result event without the new `stems` key, fixed in
  ce28784 (one line of the test). Not rerun whole afterwards (budget); the targeted reruns of test_stems_out.py and
  test_package.py after 7a1d36a: `14 passed, 2 skipped`; CI's suite runs the whole of it.
- **Tests that fail on a break** (all 17 checked by a script that breaks the code, runs the covering test, restores):
  no bitexact flags -> byte-identical test fails; song.ogg the whole mix -> split/sum test; stems written into the
  song folder -> stems test; staging kept on a full disk -> full-disk test; no stems-folder check -> refused test;
  --stems not passed by the CLI -> flags test; the old one-audio-file rule -> gate rule test; Listen on song.ogg alone
  -> Listen test; no per-file check -> out-of-sync test; any confident lag taken for a shift -> out-of-sync test (the
  tone); --stems left off the job's command -> jobs test; the queue dropping `stems` -> queue test; results without
  the stems -> download test; the stems route zipping the song folder -> download test; the page leaving stems out of
  the options -> page test; the button asking for the song's zip -> page test. Each: "FAILS (good)".
- **Real chart of creep** (kept folder copied to /dev/shm, CPU, `--takes 1 --no-preview`, through heavy.sh; three
  runs: split + stems, one audio, split + stems again):
  - stems (ffprobe): six `flac`, 44100 Hz, 2 ch, 24-bit, 10,584,012 samples each = input.wav's 10,584,012 (240.000 s);
    sizes bass 26.7, drums 43.2, guitar 35.3, other 22.3, piano 26.2, vocals 34.2 MB (188 MB; the estimate 190 MB).
  - the four .ogg: `vorbis`, 44100 Hz, 2 ch, 10,695,286 samples each (input + pad 111,274); bass 4.1, drums 6.2,
    guitar 4.9, song 5.4 MB; the one-file song.ogg 6.1 MB, same length.
  - summed vs the one-file song.ogg: -19.26 dB below the mix (two lossy encodes apart). Against the padded decode:
    the four summed -21.94 dB, the one file -20.96 dB (Vorbis's waveform error; the split adds none).
  - six stems summed vs the decode: -22.06 dB (htdemucs_6s's residual; it stays in song.ogg). song.ogg (the rest) is
    5.74 dB under the one file.
  - report.json sync (split): "sync OK: worst offset 0.00 samples over 9 windows, lowest correlation 0.997, length
    difference 0 samples"; per file 9 windows, length difference 0.
  - scan-chart on the split folder: playable True, folder issues ['noAlbumArt'] (none about audio).
  - byte-identical across two runs: True (every .ogg, notes.chart, song.ini and the six FLACs).
  - gate OK on all three; stages: assemble 35.1 s split (17.1 s one file), stems 4.3 s.
- **Golden charts**: `python -m eval.golden run --out $DEV/golden/m812 --threads 2 --rerun drums,bass,sections`
  (v040f's own reruns, which its summary records; a first run without them stopped at once: "bass ran without being
  asked", since the bass engine's cache key holds songcharter's version and the kept folders are 8ba3cbdf590c's),
  with EVAL_DATA, SONGCHARTER_GOLDEN, SONGCHARTER_AUTOCHART and SONGCHARTER_ALLIN1_PYTHON set; 7 songs, 1136 s, exit
  0. `python -m eval.golden diff $DEV/golden/v040f $DEV/golden/m812 --expect none`: "golden diff: no UNEXPECTED
  change"; "Parts changed as expected: 0. Every song's results (hashes, counts, scores) identical: yes"; pooled F1@50
  all +0.0000 (guitar expert 0.8527, bass expert 0.8247, drums expert 0.9617, beat F1 0.8755). The scorer sums a
  folder's audio files (`eval/scorer/score.py` load_mix, checked) and the alignment's lag is identical on all six
  references (e.g. 4411.791, 4039.161, 3738.844 ms on the first three). Each change, every one of the 7 songs:
  notes.chart and song.ini byte-identical; the audio was song.ogg alone and is now song.ogg (the rest) with
  guitar.ogg, bass.ogg and drums.ogg. The run's 28 audio files were deleted after the diff (its notes.chart,
  report.json, logs and summary kept: 1.9 MB); the diff's report is beside it as m812.diff.report.md. `df -h /` 1.5 GB
  free after.
- **Screens** (Chromium via playwright, the real App/Jobs/Queue with a stand-in chart, made-up names, 1280x860 and
  700 px, light and dark, deviceScaleFactor 1; looked at, then deleted): options in all four show the Audio box
  ("About 10 MB of disk for this song." for the 12-s made-up song), no horizontal overflow; a chart with stems:
  stages end with "Save the stems 3 s", Done screen "Ready" with "The instruments: 6 instruments as lossless files
  (1 MB), in the folder "Made-Up Band - Test Song (stems)" beside the song's ..." and "Download the stems"; the
  download is "Made-Up Band - Test Song (stems).zip", six .flac stored; Listen on the split folder plays ("Guitar on
  Expert, over the song ..."); the Done screen at 700 dark, 1280 dark, 700 light shows the stems box, no overflow; a
  second song with "One audio file" ran with --one-audio, no stems box; queue.json kept each song's options. No
  console errors.
- **Privacy**: both checks on every changed file before each push: `$DEV/eval` 0 found; `$DEV/eval-set20` per-file
  hit counts equal to main's (assemble 6, audio 2, cli 5, jobs 3, test_pipeline 8, test_ui_jobs 2, test_ui_server 2;
  the new test file 0; PROGRESS 1), but DESIGN.md 30 against 29: the one new hit is the known false positive "tool",
  in the friend's own words quoted in 2.2 ("a useful tool in and of itself for sampling", as in the work order).
- **The branch's scan** (CLAUDE.md's hard rules, `git diff origin/main...HEAD` and the commit messages): no audio file,
  no lyric, no model name but the commit trailers, no home or Windows-profile path (the screens' and tests' names are
  made up).
- **CI**: <repo>/actions/runs/42583936606 on the head e62c49d (workflow_dispatch):
  success, linux and windows. Every Linux hook ok (10-lanes, 20-device, 30-install, 40-ui, 50-e2e, 60-results,
  70-release, 75-update) and windows.d/30-shortcut.ps1. 60-results' own lines: "the zip downloaded: [... bass.ogg,
  drums.ogg, notes.chart, report.json, song.ini, song.ogg ...]", "the stems downloaded: Test Artist - Test Clip
  (stems).zip, 6 FLACs of 1323000 frames each, 22512737 bytes", the install holding album.jpg, background.jpg,
  bass.ogg, drums.ogg, notes.chart, report.json, song.ini, song.ogg, scan-chart's folder issues []. Two earlier runs
  failed: 42577986885 (the suite: test_chart_events, fixed in ce28784) and 42580869178 at ce28784 (30-install's real
  chart of the CI clip: "guitar.ogg is out of sync with the chart: 4286.02 samples off", the tonal-stem false lag
  fixed in 7a1d36a; the same cause as the screens' stand-in). Neither was the deferred 504.

## Interpretations to check

1. The stems are written when the gate fails too (named after the output folder, not `.failed`), and "Download the
   stems" works for a failed chart: they do not depend on the chart.
2. A full disk while writing the stems is exit 2 (InputError), as the order says, so the page shows an error, not the
   Done screen, although the chart is in place. Making it a warning instead would keep Install on the page.
3. The per-file sync check is a guard against a shift in one file; the margin rule (0.05 better than no lag) replaces
   a plain "any confident lag" rule that failed a steady tone. With one encoder and identical lengths a single-file
   shift is not expected; the sum check is today's rule.
4. Files outside the order's list touched because the change needs them: `songcharter/audio.py` (bitexact, readers,
   FLAC), `songcharter/package.py` (the writer of song.ogg), `songcharter/listen.py` (a reader), and CI's
   `packaging/ci/linux.d/60-results.sh` (its expected file lists; it now also asks for the stems and downloads them).
5. The Audio box is unfolded (not under "More options"): the friend asked for the stems, and the drop-out is a
   choice he may want to see.
6. FLAC from the stems' float32 is clipped to +-1 before the 24-bit cast; no sample of creep's stems exceeded it.

## Review fixes (two lenses, eight minor findings; commits be52b55, 93dbd15, 3005a28)

- **A1** (two breaks left the tests green): new parametrized test `test_package_refuses_song_ogg_late_a_short_file_and_
  a_shift_past_the_search`: song.ogg's decode 50 ms late fails the sum check ("the song's audio files together are out
  of sync"), guitar.ogg's decode 100 samples short fails the length check ("-100 samples long").
- **A2** (a shift past the +-100 ms search passed): `package._shifted` now also fails a loud window (within 30 dB of the
  loudest measured) that correlates under 0.9 at lag 0 ("more than 100 ms off (correlation x at no lag)"); the margin
  rule for a lag of 1+ samples stays, so a steady tone still passes. Evidence before the change: every split file of
  the seven golden songs' kept stems (guitar, bass, drums encoded and decoded as the build does) correlates 0.992 to
  1.000 at lag 0 in every measured window, those windows within 7 dB of the loudest. Tested: guitar.ogg 200 ms late
  fails.
- **A3**: guitar.ogg, bass.ogg and drums.ogg are a build's own only where its report.json's `audio_files` lists them
  (`assemble._ours`, `SPLIT_AUDIO`), as M5-12 does for a background. Tested: a stranger's multitrack folder is refused
  (and with a report.json that lists no audio files), ours with the list is accepted.
- **A4**: test that preview.ogg and crowd.ogg are left out of `song_audio_files` and `decode_song_audio`.
- **U1**: `stems_room` checks the room right after the decode (an InputError, exit 2, before separation and the
  engines); a disk that fills during the export (NoRoom, an InputError subclass) is now a warning: the run ends as the
  gate says (exit 0 on a passing chart), the result's `stems` is null, pipeline.json's `stems` is {"saved": false,
  "why": STEMS_NO_ROOM (plain words: "The disk ran out of room while the separated instruments were being saved (they
  need about N MB), so they were not saved. The chart is not affected. ..."), "error"}, the results API gives
  `stems: {"why"}` and the Done screen shows the line without the button. Tested both (the early refusal before any
  separation; the full disk with chart ok and the stems stage ending "not saved").
- **U2**: test with "my mix.flac" and a subfolder in "<song> (stems)" (both refused); an earlier export's own drums.flac
  is accepted.
- **U3**: the partial-folders test now uses "Ann - T [Live]" (and a decoy that an unescaped glob would match).
- **U4**: a stems zip is deleted from exports/ after its GET has sent it, and POST /export/stems first removes any other
  stems zip never fetched; the song's own zip stays. Tested: nothing is left after the download (a second GET 404s),
  another song's stale stems zip is removed by the next POST.
- **Breaks**: 12 more, one per fix (sum compared with itself; length test dropped; a window under 0.9 skipped; the
  margin dropped (the tone); split files ours always; preview and crowd as music; room checked only at the export;
  the full disk raised again; any .flac ours; no glob.escape for the stems' name; the stems zip kept; the why not
  shown): each "FAILS (good)".
- **PROGRESS.json**: reverted on the branch to main's (3005a28). What I had changed, for the orchestrator to carry over:
  only the M8-12 in_flight entry's "stage", set to "built 2026-11-09 on branch m8-12-stems-out (worktree <wt>/m8-12):
  part A (--stems, the six stems as 24-bit FLAC in "<song> (stems)" beside the song folder, the page's option and
  "Download the stems"), part B (guitar.ogg, bass.ogg, drums.ogg and song.ogg the rest by default, --one-audio for one
  file, the Ogg serial fixed), the docs; the golden charts against v040f (--rerun drums,bass,sections, as v040f): no
  UNEXPECTED change, every notes.chart and song.ini byte-identical, scores and the alignment's lag identical, only the
  audio split; the builder's report <scratchpad>/m8/m8-12.report.md".
- **Checks after the fixes**: the full suite through heavy.sh, `1348 passed, 6 skipped in 1320.71s`. The golden refs again
  (A2 changed the check), the same reruns, into $DEV/golden/m812b: exit 0; `golden diff ... v040f m812b --expect none`:
  "no UNEXPECTED change", every gate OK -> OK, "Every song's results (hashes, counts, scores) identical: yes"; all 7
  songs' notes.chart and song.ini byte-identical, each with the four .ogg. Its 28 audio files deleted (1.9 MB left),
  the diff's report beside it as m812b.diff.report.md; `df -h /` 1.5 GB free. CI:
  <repo>/actions/runs/42590187310 on the head 3005a28, success (linux and windows;
  every hook ok, 60-results "the stems downloaded: ... 6 FLACs of 1323000 frames each"); the run started on 93dbd15
  (42590121663) was cancelled when the PROGRESS revert went up. Both privacy checks on the changed files: 0 found;
  set20 per-file counts unchanged (DESIGN 30 with the known "tool", assemble 6, test_ui_jobs 2, test_ui_server 2).
