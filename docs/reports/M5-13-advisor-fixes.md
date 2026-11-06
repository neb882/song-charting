# M5-13: the advisor's two findings on v0.2.0's candidate (builder's report)

Branch `m5-13-advisor-fixes` in `<wt>/m5-13`, from main at 4202309 (the order's commit on the candidate c71009f).
Main had not moved when the branch was pushed (`git merge-base --is-ancestor origin/main HEAD`: yes), so no merge.

## Commits

- `96aa98b` clonehero.install: our older chart of the same song under another name is the chart it replaces
- `1e491af` install.sh: not under a running songcharter; 75-update shows it
- `d521f1f` DESIGN 4.5 and the guide: the install's older chart under another name, no update under a running
  songcharter
- `10349c6` 75-update: the refused line's stop read from stderr; the whole-install test takes the guide's prompt too
  (the fix for CI's first run, below)

Files: `songcharter/clonehero.py`, `tests/test_clonehero.py`, `packaging/linux/install.sh`, `tests/test_install.py`,
`packaging/ci/linux.d/75-update.sh`, `docs/DESIGN.md` (4.5), `docs/guide/windows-wsl.md` (section 3). build.sh needed
no change (no new `@...@` value). PROGRESS, the work orders, PIPELINE and docs/reports/ untouched.

## Item 1: a song charted under v0.1.0 installed twice

**Reproduced first** (a scratch script on the candidate's clonehero.py, made-up names): Songs held v0.1.0's
`Imaginary Band Name - A Made Up Song Tit` (ours, same song.ini name and artist); installing today's
`Imaginary Band Name - A Made Up Song Title (Live)` gave `installed ..., replaced: None` and Songs held both folders.
After the change the same script gets Exists (ours) naming the v0.1.0 folder, and Songs is unchanged.

**The rule** (`clonehero.older_charts`, `song_of`, `_replace_older`; the module docstring has it in full):
- an older chart of ours of the same song is each folder at the top of Songs that is a real folder (not a link), not
  hidden (no leading dot), not songs/<the new name> itself, that `is_ours` (charter songcharter and report.json) and
  whose song.ini has the same `name` and `artist` (first line of each key; folded: NFC, without case, runs of spaces
  as one; no name, an empty name or no artist line never matches);
- "songs/<name> itself": the exact name, or a name differing only in case that `os.path.samefile` says is the same
  folder (drvfs ignores case; on ext4 such a folder is a distinct one, and is an older chart);
- they count as the existing chart. With `replace=False`: `Exists(older[0], ours=True)`, so the server's 409 and the
  page's existing words ("This song is in Clone Hero already (<its path>), from an earlier chart. Replace the older
  chart?") apply unchanged; the server and page needed no change. A same-name folder of ours still comes first, and
  a same-name folder that is not ours still refuses (Exists, not ours) whatever else is there;
- with `replace=True`: after the new chart is in place (and a same-name older one moved, as before), each is renamed
  aside (retried, as every rename) to `.<the new name>.songcharter-<8 hex>.old`, then moved to
  `replaced/<stamp>/<its own name>`. A rename Windows refuses leaves it in place with a note ("...: it stays in
  <path>, and Clone Hero lists the song twice until that folder is deleted"); a failed move leaves the `.old`, a
  leftover of the new name that the next install's `_tidy` clears. `Installed.replaced` is the first that went; the
  note names the others;
- never touched: a folder without our marks, a link, a hidden folder, another song of ours (another title, another
  artist, a v0.1.0 cut two songs share).

**Tests** (tests/test_clonehero.py, made-up names; `built()` gained `song` and `artist`, defaults as before so the
existing tests are unchanged):
- `test_a_chart_installed_under_v010s_cut_of_the_name_is_the_older_chart` (also pins that today's safe_name keeps
  the 61-character name whole and that the literal v0.1.0 cut is its 40-character prefix);
- `test_the_same_song_in_a_folder_without_our_marks_is_never_touched` [another charter, no report.json, a link to
  ours, hidden];
- `test_another_song_of_ours_is_never_touched` [another song cut to the same name, a similar title, another artist,
  no artist line, no name];
- `test_the_same_names_chart_and_older_ones_under_other_names_all_go` (same-name + v0.1.0 cut + a renamed copy whose
  song.ini differs in case and spacing);
- `test_a_name_that_differs_only_in_case_is_the_target_where_case_is_ignored`;
- `test_an_older_chart_windows_will_not_let_go_stays_with_a_note`;
- `test_an_older_chart_whose_move_fails_is_a_leftover_the_next_install_clears`.

**Breaks** (each applied alone to clonehero.py, tests/test_clonehero.py run, reverted; all 12 caught):

| break | failed |
|---|---|
| B1 no scan (`older = []`) | 4: v0.1 cut, all go, will not let go, move fails |
| B2 artist ignored | another song [another artist] |
| B3 no is_ours | no marks [another charter], [no report.json] |
| B4 links followed | no marks [a link to ours] |
| B5 hidden not skipped | no marks [hidden] |
| B6 no fold | all go |
| B7 no samefile skip | differs only in case |
| B8 no 409 for an older one | v0.1 cut |
| B10 aside under its own name | move fails (the next install no longer clears it) |
| B11 replaced/ under the new name | v0.1 cut, all go |
| B12 no note for the others | all go |
| B13 a refused rename raises | will not let go |

## Item 2: the update while an old songcharter runs

**Reproduced first** (a scratch script with tests/test_install.py's `Install` harness): a stand-in answering
`/api/hello` as songcharter on 127.0.0.1:8784, a made-up older `app/0.0.1`; install.sh exited 0 and `app/` held
only the new version. After the change: exit 2, `app/0.0.1` kept, the line below.

**The check** (`running_ui`, `refuse_if_running` in install.sh, called right before step 6's header, after the
licence prompt): for each of `UI_PORTS` (8765-8784, songcharter/ui/server.py's `PORTS`, v0.1.0's too), a GET
`/api/hello` on 127.0.0.1 through bash's `/dev/tcp` under `timeout 3` (no curl or wget needed, and the tests' stand-in
curl is not asked), with the Host header the server's guard needs. An answer with `"app": "songcharter"` stops the
install, any version (a same-version reinstall can also swap torch in step 7): exit 2, stderr

    songcharter: songcharter 0.1.0 is still running (port 8765): close the songcharter window first, then paste the line again. Nothing was changed.

The version is named only when it reads as one (`[0-9A-Za-z.+-]{1,40}`). A closed port refuses at once (20 ports in
well under a second); a port that accepts and never answers costs 3 s.

**Tests** (tests/test_install.py):
- `test_the_ports_are_songcharter_uis` (UI_PORTS == server.PORTS);
- `test_running_ui_finds_songcharters_server_and_nothing_else`: the real `songcharter.ui.server` (App + bind on a
  free port: its Host guard and JSON) is found with `__version__`; a closed port, another program's JSON and a
  listening socket that never answers are not (under 10 s with UI_TIMEOUT_S=1);
- `test_a_running_songcharter_stops_the_install_with_the_line` [0.1.0, no version, an odd version]: exit 2, the one
  line, nothing after it runs; with nothing running it returns;
- `test_an_install_over_a_running_songcharter_stops_before_it_changes_anything`: a first install, a made-up
  `app/0.0.1`, a stand-in on the first free port of 8784 down to 8765 (the real range, the last first; skips if none
  is free): exit 2 with the line, step 5 printed and no step 6, every path under the install and the launcher's
  folder identical (kind, size, mtime to the nanosecond), no new curl/uv/python call; then, the stand-in gone, the
  same command exits 0 and `app/` holds only the new version (the install over a closed one is unchanged). Every
  existing whole-install test also runs with nothing listening and passes unchanged.

**Breaks** (each alone on install.sh, the five tests above plus `test_a_release_installs_with_stand_ins`; all 8
caught):

| break | failed |
|---|---|
| C1 the call removed | whole install over a server |
| C2 the call moved after step 6's delete | whole install over a server |
| C3 a port short (8765-8783) | ports, whole install |
| C4 any answer counts | finds the server and nothing else |
| C5 version not checked | the line [odd version] |
| C6 returns instead of exit 2 | the line [3 cases], whole install |
| C7 no Host header (the real server's guard refuses) | finds the server and nothing else |
| C8 no timeout | finds the server and nothing else (the silent port hangs to the test's 60 s limit) |

The whole-install test also runs the refused install once without `--yes`, answering Enter as the guide's line does:
exit 2, stderr exactly the line, stdout ending at "Continue? [Y/n] ".

**CI** (`packaging/ci/linux.d/75-update.sh`, step 3): before the update, v0.1.0's page (`songcharter`) is started and
its address read; the new line is pasted: it must exit 2 with exactly the line above for v0.1.0 and its port as the
last line of its stderr (kept apart from stdout: with stdin a pipe the Enter after the prompt is not echoed, so in
one log the line follows "Continue? [Y/n] " on the same line), print "install.sh: OK" and no step 6, leave `app/` holding 0.1.0 alone, and fetch only install.sh from the server (once);
the old page must still answer, stop cleanly on SIGTERM and then not answer. Then the existing update runs as
before. Not run locally (it needs Docker and both release builds); CI is its run.

## Docs

- DESIGN 4.5: under "Install into Clone Hero", the same song under another name (the rule, why, what is never
  touched, the unmeasured cost); a new bullet "No update under a running songcharter" after M5-12's.
- The guide, section 3: the update bullet says that if it says songcharter is still running it changed nothing
  (close the window, paste again); a new bullet says a re-chart of a song from an older version asks to replace the
  older chart, even under another folder name.

## Checks

- **Targeted, during the build** (the candidate's environment with this worktree on PYTHONPATH, before this
  worktree's own was synced): `python -m pytest -q -p no:cacheprovider tests/test_install.py tests/test_clonehero.py`
  -> `92 passed in 28.04s`; `tests/test_updates.py tests/test_ui_server.py tests/test_clonehero.py tests/test_cache.py`
  -> `172 passed in 22.40s`; after 10349c6, the item-2 tests -> `6 passed`.
- **Breaks:** 12 of item 1 and 8 of item 2, each caught (tables above); scripts and outputs in the scratch folder
  (`m5-13/breaks1.py`, `breaks2.py`, `.out`).
- **The full suite, dev** (`tools/heavy.sh`, this worktree's `uv sync --frozen --extra cpu --extra app --extra dev`,
  `SONGCHARTER_SCAN_CHART=... .venv/bin/python -m pytest -q -p no:cacheprovider --basetemp=<shm>/pt-m5-13`), on
  10349c6's files: `1 failed, 1055 passed, 4 skipped in 727.86s (0:12:07)`. The failure is
  `tests/test_art.py::test_without_pillow_a_given_image_is_a_tool_error_and_an_embedded_one_a_warning` (got no
  warning where one was expected): code and test this branch does not touch, and test_art.py is the suite's first
  file. It did not reproduce in four runs: alone (`1 passed`), its file (`18 passed`, also with
  SONGCHARTER_SCAN_CHART set), and alone with the whole suite collected, on this branch and on the candidate c71009f
  (`1 passed, 1059 deselected` / `1 passed, 1039 deselected`); CI's suite on the same commit passed it. A flake for
  the orchestrator to note (its ffmpeg probe of the embedded picture has no timeout and no retry: a guess, not
  checked). The rerun on 10349c6, the same command through `tools/heavy.sh`: `1056 passed, 4 skipped in 678.07s (0:11:18)`, exit 0.
- **CI, run 1** <repo>/actions/runs/42206302480 on d521f1f: **failure**. Windows
  green; Linux suite green, hooks 10 to 70 green, 75-update failed at my new step's last-line check: `its last line is
  not: songcharter: songcharter 0.1.0 is still running (port 8765): ...`. The install had done the right thing (exit
  2 checked first, the line printed, before step 6); the line shared the prompt's line in the merged log. Fixed in
  10349c6.
- **CI, run 2** <repo>/actions/runs/42209741384 on 10349c6 (head SHA
  10349c65829f6baa727536093e5f863a2d8b440d): **success**, windows and linux. Linux suite `1056 passed, 4 skipped in
  505.43s`; every hook ok (30-install 155 s, 70-release 59 s, 75-update 165 s). The new step's lines:
  `Continue? [Y/n] songcharter: songcharter 0.1.0 is still running (port 8765): close the songcharter window first,
  then paste the line again. Nothing was changed.` / `refused while v0.1.0 ran on port 8765; its page stopped` /
  `75-update: the line under a running v0.1.0 fetched install.sh alone and stopped before step 6` / `75-update: ok
  (0.1.0, then 0.2.0-ci-10349c6 over it, and the notice)`.
- No golden or stress run (no charting change, as the brief says).
- Main had not moved past the branch's base at either push (`git merge-base --is-ancestor origin/main HEAD`), so
  nothing to merge in.

## Not done, or uncertain

- **The scan's cost on a large library under drvfs is unmeasured.** Each install now looks at every top-level folder
  in Songs (one stat for report.json; song.ini read only in ours). On ext4 it is nothing; over /mnt/c with thousands
  of songs it may add seconds. Worth timing in the owner's PC check (item 8), with the advisor's suggested re-chart
  and install of the test song (which also exercises this rule end to end on Windows).
- **Not matched by design:** a v0.1.0 chart whose song.ini name or artist differ from today's for the same file
  (for instance an untagged file named "Artist - Title", if v0.1.0 gave it the artist "Unknown" and today's
  from_file_name splits it). Those show in Clone Hero as two differently named entries, not the advisor's identical
  pair; matching them would need another notion of "the same song" (the source file), a decision the order did not
  make.
- `songcharter/ui/server.py`'s docstring for POST /api/jobs/current/install says the 409 comes "when that folder is
  there"; it may now name an older folder of ours under another name. Not in this order's files: one clause for a
  later edit.
- The check is a probe, not a lock: a songcharter window opened during steps 6-10 is not caught (as before). The
  probe needs bash's /dev/tcp (Ubuntu's bash has it); without it, the probe finds nothing and the install goes on as
  before.

## Privacy and hard rules

Scanned `git diff 4202309...HEAD` and the three commit messages: no lyrics, audio, model names (the trailers only),
personal details or real song names (the fixtures are made up: "Imaginary Band Name", "Another Made Up Band", "Made
Up Charter", version 0.0.1). `EVAL_DATA=$DEV/eval python3 -I eval/privacy_check.py` before the push: "258 files, 14
md5s and 37 names checked, 0 found", exit 0, before each of the two pushes; 10349c6's added lines scanned the
same way.

## Review fix (orchestrator, commit decd4d8; a test only)

- **R1** (a probe asking only the last port passed every local test): the running_ui and refusal tests put their
  server between closed ports, and the whole-install test's stand-in takes the first free port from 8765 (the
  friend's page's); the reviewer's break (`${UI_PORTS##* }`) fails 5 tests. CI on decd4d8: run 42214626081, success.

## Review (sc-reviewer, 2026-11-06)


Copy of the branch under <shm>/review_m513/ (deleted after). Targeted runs only, through tools/heavy.sh:
tests/test_clonehero.py + tests/test_install.py in the copy -> 89 passed, 1 skipped, 2 failed (the two build.sh
tests that need a git checkout; the copy is a `git archive`, so expected).

## Findings

**R1 (minor) tests/test_install.py: a probe that asks only the last of UI_PORTS passes every local test.**
Break in the copy, install.sh line 210: `for port in $UI_PORTS; do` -> `for port in ${UI_PORTS##* }; do` (only
8784 is asked). Run: `python -m pytest tests/test_install.py -k "running or ports or release_installs"` ->
`7 passed, 39 deselected`. Why it slips: `test_the_ports_are_songcharter_uis` checks the list, not the loop;
`test_running_ui_finds...` and `test_a_running_songcharter_stops...` put the server on the *last* port of their
UI_PORTS; the whole-install test starts its stand-in on 8784 first. If shipped, the friend's page on 8765 would not
be seen and the update would go ahead under it. Only CI's 75-update (v0.1.0 really on 8765) would catch it, so
CI does cover it. The fix is to put the stand-in in the whole-install test on the first free port from 8765 up
(the friend's port), or on a middle port of the list in the running_ui test.

No other findings. Checked and correct:
- clonehero: the marks (report.json, then charter), links (`is_dir(follow_symlinks=False)`), hidden folders, another
  song / another artist / no artist line / no name, a same-name folder not ours still refusing first (whatever
  else is there), case-only variants (samefile on drvfs skips them; on ext4 or a case-sensitive dir they are a
  distinct older chart, which is right), two or more older folders, a refused rename (note, folder whole), a failed
  move (a `.<new>.old` that the next `_tidy` clears). The older charts move only after the rename into place, so a
  failed copy or rename leaves them untouched. The page's 409 (ours) flow and server need no change.
- install.sh: UI_PORTS == server.PORTS; the Host header matches the server's guard; `timeout` kills the bash -c
  group (a silent port costs UI_TIMEOUT_S); another program's JSON does not match; without /dev/tcp it finds nothing
  and goes on as before (documented); exit 2 and nothing changed before step 6; with the server closed the update is
  unchanged. CI run 42209741384 shows the refusal against the real v0.1.0.

## Breaks of my own that the tests caught
clonehero: K1 the 409 for an older chart flagged not-ours; K10 older charts moved before the copy; K15 the older
409 checked before the same-name not-ours refusal; K16 case variants skipped without samefile; K18 the target itself
counted as an older chart (12 failed); K20 no case fold. install.sh: R1 above is the one that survived.
Also survived, not findings (no defect ships): K4 the last `name=` line of song.ini wins (ours never repeats a
key); K5 the older chart's 409 raised after `_tidy` (it would only tidy our own hidden leftovers first);
K19 an empty artist treated as a missing one (only stricter).
