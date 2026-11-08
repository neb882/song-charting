# v0.4.0 gate: the full review's minor findings, fixed (fixer's report)

Branch `v040-review-fixes`, worktree `<wt>/v040-fix`, from main c0a49f9. Findings tests-1, install-1, docs-1 and docs-2
of the full review (base a5895ff, head c0a49f9), and fix 5 from the release advisor (sent mid-task by the
orchestrator). docs-3 (PROGRESS, handoff) is the orchestrator's and is not touched here.

## Commits

| commit | finding | files |
|---|---|---|
| 81baff7 | tests-1 | tests/test_beatgrid.py |
| fc5e391 | install-1 | songcharter/ui/estimate.py, tests/test_ui_estimate.py |
| d8b50a7 | docs-1 | songcharter/ui/estimate.py, tests/test_ui_estimate.py, docs/DESIGN.md (4.5), docs/reports/M7-10-ui.md |
| c485ea7 | docs-2 | docs/DESIGN.md (2.0 table, 2.3 step 7's halving rule), songcharter/assemble.py (a docstring) |
| 00e5056 | fix 5 | songcharter/ui/static/app.js, tests/test_ui_server.py, docs/DESIGN.md (4.5) |
| 77a5912 | merge of origin/main (8c78716: the orchestrator's PROGRESS and handoff) | docs/PROGRESS.json, docs/handoff.md (main's) |

Nothing on the charting path changes: beatgrid.py is untouched (tests-1 is a test), assemble.py's AST is identical to
main's apart from docstrings (checked by `ast.dump` with the docstrings blanked: `True`), and estimate.py and app.js
are the UI's (no chart goes through them). So no golden run and no real chart, as the brief says.

## tests-1: the line_test grid running to the song's end

**Reproduced.** In a copy of c0a49f9 in `<shm>/v040fix/repo`, with beatgrid.py:822 broken to
`line = first + np.arange(len(tracker)) * b`, the M7-09 review's selection (`tests/test_beatgrid.py
tests/test_assemble.py -k "halved_start or halv or first_tempo or back_at or allin1 or octave or pulse"`):
`31 passed, 98 deselected in 61.36s`. The review's probe (a 120-s 75 BPM click, the test's `drums()` helper, seed 11,
start beats `truth[:12] - ONSET_TO_BEAT_MS/1000`, the halving pass's arguments): main `grid: line beats: 150 last
beat: 119.59 s of 120`, broken `grid: line beats: 12 last beat: 9.19 s of 120`.

**The fix** (test only): `test_a_halved_start_over_part_of_the_song_runs_the_line_to_its_end`, that probe as a test.
It asserts the grid is the line (`stats["start"]["grid"] == "line"`, 12 start beats ending before 10 s), at 75 BPM
within 0.01, its last beat a period (0.8 s) or less from `dur`, one beat a period from the first to the end, every
true beat within 15 ms of a grid beat, and the p95 spread under 3 ms.

**Breaks** (the test file copied into the scratch copy, `-k halved_start`, 3 tests):
- main's code: `3 passed`.
- the review's break (one line beat per start beat): `1 failed, 2 passed`; the new test fails
  (`assert ((120.0 - 9.19147314331501) < 0.8)`), the drumless-wander test still passes, as the review said.
- the M7-09 review's break (`tracker[-1]` for `dur` in the same line): `2 failed, 1 passed`; the new test
  (last beat 8.39 s) and the drumless-wander test both fail.

## install-1: a tag holding "Duration: H:MM:SS"

**Reproduced** with the launcher's ffmpeg (imageio-ffmpeg's static n9.0.2), 12.5-s sines with
`-metadata comment='Duration: 01:00:00.00'`: `t.aac 12.4, t.aiff 3600.0, t.flac 3600.0, t.m4a 3600.0, t.mp3 3600.0,
t.ogg 12.5, t.opus 12.51, t.wav 3600.0, t.wma 3600.0`, and `for_job(3600.0, defaults, cuda, cuda)`: `620 2150`.
`ffmpeg -i t.mp3` prints `  Metadata:`, `    comment         : Duration: 01:00:00.00`, then
`  Duration: 00:00:12.50, start: 0.025057, bitrate: 64 kb/s`.

**The fix:** `DURATION = re.compile(r"^  Duration: *(\d+):(\d{2}):(\d{2}(?:\.\d+)?)", re.M)`, the container's own
line, which ffmpeg's dump prints indented by exactly two spaces. Better than the brief's `^\s*Duration:` with re.M:
ffmpeg prints a tag's key at four spaces, and an ID3 TXXX frame's description is its key, so a TXXX frame described
"Duration: 01:00:00.00" prints `    Duration: 01:00:00.00: x`, which `^\s*Duration:` reads (checked on a real mp3
with that key). A tag value's later lines print as `                    : ...` (checked with a two-line comment),
and Matroska's stream tags as `      DURATION        : ...` (upper case, after the line). The upload's file name is
`cache.safe_name`'s, so it cannot carry a newline into `Input #0, ..., from '...'`.

**Real files after the fix**, the launcher's ffmpeg: mp3, wav, flac, m4a, aiff, mka and the two-line and key cases
`12.5`; aac `12.4`, ogg `12.5`, opus `12.51`, wma `12.54` (their own headers); the page for the mp3: `1 2`.

**Tests** (tests/test_ui_estimate.py):
- `test_a_tag_that_holds_a_duration_is_not_the_songs_length[mp3|wav|flac|m4a]`: a 2.5-s wav from `audio.write_wav`,
  converted by the found ffmpeg with that comment tag; it checks the tag shows in ffmpeg's answer (so the case is
  real), then `duration` is 2.5 within 0.1. It passes with the dev container's system ffmpeg (6.1.1, first on PATH)
  and with `FFMPEG=` the launcher's n9.0.2 (`14 passed` for the tag and header tests); CI's runner has only
  imageio-ffmpeg.
- four stand-in answers in `test_the_header_line_is_read_whatever_comes_around_it`, in ffmpeg's own layout: a
  comment tag before the real line (12.5), a value's later line (185.0), a TXXX key (185.0), and N/A after such a
  tag (None).
- Breaks: the old pattern `8 failed, 46 passed` (the four real files and the four stand-ins); `^\s*Duration:\s*`
  with re.M `1 failed, 53 passed` (the TXXX key); the fix `54 passed`.

## docs-1: the estimate's stated evidence

**Reproduced**, recomputed from docs/reports/takes-experiment.md's "Run time" table (a script parsing its rows):
length 1.718x (412.4 s against 240 s; squared 2.95); base take 4.00x (264 / 66); later takes' mean 4.83x (191.7 /
39.7); all 4 takes 4.54x (839 / 185); Creep's own "4 / 1" 2.80. No reading of the table gives 2.8x for the pair.

**The text, corrected** in estimate.py's docstring, DESIGN 4.5 and M7-10-ui.md (marked "(corrected at the v0.4.0
gate)" there): the test song took 4.8x Creep's time a later take (192 s against 40 s, the mean of three), 4.0x the
first take and 4.5x all four (839 s against 185 s), for 1.7x the length, whose square is 2.9: faster than the
square. "At about the same notes a second" holds (3.1 against 2.9 onsets a second: the test song's base take 1277
onsets in 412 s, Creep's S1 base build 691 in 240 s). The docstring also gives the wider fit: the five ordinary
songs' later takes against their lengths fit d^1.93 (log-log slope); with the owner's three ordinary songs
(their 4-take times less 0.13 s/s for the first take, over 4) d^2.38. So the pair is steeper than the set.

**The docstring's other claims against their sources:**
- The first take's own separation and timing, "13-72 s (0.07-0.17 s a second)", computed as the first take less
  the later three's mean: Drunk Drivers 42.0 s, 0.187 s/s; Take Me Out 26.7, 0.111; All the Small Things 13.0, 0.074;
  Creep 26.3, 0.110; the test song 72.3, 0.175; Lucretia (dense) 42.3, 0.176; Kimochi Warui (dense) -26.0 (its later
  takes are slower). The seconds are right; the rates miss Drunk Drivers at the top and All the Small Things at the
  bottom of the code's 0.08-0.17.
- The preview: 11 s for the test song (412.4 s) is under PREVIEW's low end, 5 + 0.02 x 412.4 = 13.2 s; 12 s for a
  4-minute song here is inside (9.8-17 s).
- Spot-checked, inside: the GPU's other stages for the test song (A6: 88 s against 81.9-184.9 s on the 5070's
  rates), the CPU's first take (187 s of 412 s, 0.45 in 0.35-0.50), the CPU's other stages on 2 threads.

**Widened, not reworded** (the brief's choice): GUITAR_ONCE cuda (0.08, 0.17 x 1.35) -> (0.07, 0.19 x 1.35), and
PREVIEW (5 + 0.02-0.05 s/s) -> (5 + 0.01-0.05 s/s). Why: the docstring's rule is that each range is where its
measured runs fell, the change to the page is small, and the other choice would leave ranges that knowingly miss
their own runs. The PREVIEW low end comes down on the rate, not the fixed part: the two runs (11 s at 412 s, 12 s at
240 s) show almost no growth with the length.

**The page before and after** (the GPU at the 4070's rates, with the preview):

| song | 4 GPU takes | 1 GPU take | 1 CPU take |
|---|---|---|---|
| 4:00 before | 246.3-821.6 s, 4 to 14 min | 125.3-371.6 s, 2 to 7 | 367.3-618.3 s, 6 to 11 |
| 4:00 after | 241.5-828.0 s, 4 to 14 | 120.5-378.1 s, 2 to 7 | 364.9-618.3 s, 6 to 11 |
| 9:00 before | 976.5-3341.9 s, 16 to 60 | 364.1-1186.1 s, 6 to 20 | 1002.1-1894.5 s, 16 to 35 |
| 9:00 after | 965.7-3356.5 s, 16 to 60 | 353.3-1200.7 s, 5 to 21 | 996.7-1894.5 s, 16 to 35 |

The minutes change only for a 9-minute song's 1 GPU take. Whole charts: the test song's 1 GPU take, 5.05 min, now in
4.0-13.3 (was 4.1-13.1). The guide's "about 5 to 15" and "2 to 7" stand.

**Tests:** pins updated (the hand arithmetic `(246.28, 821.55)` -> `(241.48, 828.03)`, the 4-minute song's minutes
still `(4, 14)` and `(2, 7)`; GUITAR_ONCE cuda `(0.07, 0.19 x 1.35)`; the preview's part `5 + 0.01 d`), and a new
`test_the_first_takes_own_part_and_the_preview_fall_inside_their_ranges`: the five ordinary songs' first-take parts
(from the table's numbers) inside GUITAR_ONCE at the 5070's own rates, and both preview runs inside PREVIEW.
Breaks: the old GUITAR_ONCE `3 failed, 52 passed` (the arithmetic, the pin, the new test: `42.0 <= 38.25`, Drunk
Drivers); the old PREVIEW `3 failed, 52 passed` (the arithmetic, the part, the new test: `13.248 <= 11.0`).

**Is the high end unsafe for a long song?** Not on the owner's GPU; marginal on the friend's 4070 past about 10
minutes. M7-10-ui.md's 9:05 song (545 s) took 2173 s for its 4 takes on the 5070: 95 % of the guitar's high end at
the 5070's own rates (2282 s) and 71 % of the page's (the 4070's, 3067 s); its k (0.00177) is the top of the
ordinary range (0.0018). Extrapolated from that song along d^2.38 (the set with the owner's songs): the 5070's own
high end is passed from about 10.2 minutes, the page's not within 20 minutes on the 5070; a 4070 1.35x as slow
passes the page's high end from about 10.2 minutes, 1.2x as slow from about 13.7. Along d^2 (the experiment's five)
nothing passes it within 20 minutes; along the Creep/test pair's d^2.9, a 1.35x 4070 from about 9.6 minutes. The
docstring and DESIGN 4.5 now say a song much longer than 9 minutes may pass the high end on the 4070 [inference];
the constants are left (the brief allowed only the two parts above). Suggested for `deferred`: check the range
against M4-08 part B's times or the friend's first long song.

## docs-2: beat_grid(start=...) and the line test

**Reproduced** by reading: DESIGN.md:256 said "always free; raises `InputError` ...", DESIGN.md:679 and
assemble.py:1610 said beat_grid refines allin1's beats "(free mode)", while `_halving_pass` passes
`line_test=True` (assemble.py:1627) and beatgrid.py's mode choice gives click below FREE_SHARE when the line wins
(`use_tracker` false). DESIGN's M7-09 section already says so for `ntl` ("the line, click mode"). The review's own
synthetic repro was not rerun: the code path is plain from the source.

**The fix:** the table row now says free on the start beats; with `line_test` (the halving pass's) the straight line
unless they find TRACKER_MARGIN more, then click or free by FREE_SHARE (`ntl`: click, §2.3 step 7); the doubling's
start (M6-05) takes no line test and stays free. The halving rule's parenthetical and `_halving_pass`'s docstring
say the same (the docstring now names `line_test=True` in the call it describes). The doubling's own paragraph
(DESIGN.md:616, "free mode") is right and unchanged. No code change in assemble.py.

## Fix 5 (the release advisor): the page's text when songcharter does not answer

After 10 failed asks 2 s apart, `gone(true)` said as fact that the black window was closed. The new text: "songcharter
is not answering. If its black window is still open, reload this page (press F5) to follow the chart. If the window
was closed, which stops the chart, start songcharter again from the Start menu, then chart the song again: what it
had worked out is kept, so it goes faster." `gone(false)`'s text, the heading ("songcharter stopped"), the tab's
"Stopped", the lock and the rows are unchanged (no logic changed; only that string and two comments). Reload
reattaches through `attach()` on load. tests/test_ui_server.py's page test asserts the new text: with the new
app.js `1 passed`; with main's app.js and the new assertion `1 failed` (the `down` text differs); the whole file
`68 passed`. DESIGN 4.5 says why. No guide or DESIGN line quoted the old text; M7-10-ui.md (a record) is untouched.
Open question for the orchestrator: the heading still reads "songcharter stopped" and the tab "Stopped" in the
`down` case, which the new text softens but does not change; changing them was outside "the `down` text".

## Checks

- Touched test files: `tests/test_beatgrid.py tests/test_ui_estimate.py`: `102 passed in 23.22s`;
  `tests/test_ui_server.py`: `68 passed in 25.65s`.
- Full suite, `SONGCHARTER_HEAVY_MIN_FREE_GB=1 SONGCHARTER_SCAN_CHART=<wt>/base-main/tools/scan-chart/scan.cjs
  tools/heavy.sh .venv/bin/python -m pytest -q -p no:cacheprovider --basetemp=<shm>/v040fix/pt` on 00e5056:
  `1219 passed, 6 skipped in 792.19s (0:13:12)`, exit 0. (The merge after it brought in only main's PROGRESS.json
  and handoff.md.)
- A first suite run was stopped at 5 % when fix 5 arrived (its files changed under it) and restarted on the
  committed tree.
- CI: <repo>/actions/runs/42510967829 on
  77a5912649d8f0b7832fbf30d3493f668011f2b3 (the merge head): **success**, linux and windows. The linux Suite step
  `1221 passed, 4 skipped in 374.02s`; the hooks: `all 8 Linux hooks passed` (10-lanes, 20-device, 30-install,
  40-ui, 50-e2e, 60-results, 70-release, 75-update) and `all 1 Windows hooks passed` (30-shortcut). This order
  adds no hook: its checks are suite tests. The first run, on 00e5056 (42509860614), was cancelled by the
  dispatch on the merge head (the workflow's concurrency group) after its windows job passed.
- Privacy: `EVAL_DATA=$DEV/eval python3 -I eval/privacy_check.py <the 8 changed files>`: `8 files, 14 md5s and 37
  names checked, 0 found`. With `$DEV/eval-set20`: `36 found`, the same count as main's versions of the same files
  (35 in DESIGN.md and assemble.py, 1 in app.js or test_ui_server.py), and none on a line this branch changed
  (the hits' file:line against the diff's added lines: 0). The diff and the commit messages scanned for model
  names, paths, user names, emails and lyrics: nothing but the trailers (one hit on the word "lyrics" in the
  estimate's rate list, a stage name).
- No golden run, no real chart: nothing on the charting path changed (above).
- While I waited on CI (nothing of mine running but `gh`), the machine's kernel killed a process for lack of memory;
  it was not one of this order's jobs. Worth a look if the golden comparison running beside it failed.
