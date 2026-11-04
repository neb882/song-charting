# M4-08a: part A automated (the harness)

**Status: not built.** The owner cancelled it on 2026-11-04 and runs part A by hand; kept for a later release
candidate. If it is built, the Ubuntu driver alone (testable in CI) is most of the value.

**Branch:** `m4-08a-harness`, from main at 8edabfd. **Agent:** `sc-builder`, then `sc-reviewer`. May push its branch
to run CI. The owner asked for it on 2026-11-04, so that part A of M4-08 (about four hours of hand work) becomes one
command and a short manual list, and every later release candidate gets the same check.

## Intent

Part A (M4-08) checks a release on the owner's RTX 5070 PC in a fresh Ubuntu-26.04 distro, as the friend will meet it.
Most of its steps are clicks on the page and commands in Ubuntu that a script can do through the page's own HTTP API
(the one `packaging/ci/linux.d/40-ui.sh` and `60-results.sh` already drive). Two scripts:

- **`packaging/hardware/m408a.ps1`**, run by the owner in an admin PowerShell on Windows: prepares Windows and the
  distro, waits while the owner pastes the install line by hand, runs the Ubuntu part, measures what only Windows can
  see, lists the manual checks, and cleans up.
- **`packaging/hardware/m408a.py`** (Python 3, standard library only), run inside the distro by the PowerShell script:
  every step that the page's API, the CLI and `/proc` can do, writing one results folder.

The install line stays a hand step on purpose: copying it from the release page and watching the window is the test
that the guide works (A3, A17).

## The owner's steps (what the work order's docs must give him, in M4-08)

1. Put the inputs in `%USERPROFILE%\Desktop\m408a\`: `test.mp3` (the test song), `b.*`, `c.*` (two songs never charted;
   any audio type the page takes), optionally `takemeout.wav` and `lyrics.txt` (his own text of the test song's
   lyrics; never committed, printed or sent).
2. In Terminal (Admin), one command that downloads `m408a.ps1` from main at a commit (raw.githubusercontent.com) and
   runs it with `-ExecutionPolicy Bypass` for that process only. Give the exact command in M4-08.
3. When the script says so, open "Ubuntu-26.04" from the Start menu and paste the install line from the release page,
   with ` --windows-ram-gb 16` added; note whether the window closes; press Enter in PowerShell.
4. Walk away. At the end, do the manual list the script prints (below), then answer its cleanup question.
5. Send the results folder it names.

## The PowerShell script (`m408a.ps1`)

Parameters: `-Release v0.1.0` (the tag under test), `-Ref <commit or branch>` (where to fetch `m408a.py`; default the
commit the script was fetched from, which the M4-08 command passes), `-Inputs <folder>` (default the Desktop folder
above), `-DryRun` (print every action and run none: no WSL, no files outside a temp folder; CI uses it), `-SkipPrep`
(the distro exists and songcharter is installed: start at the Ubuntu part, for a rerun).

In order, printing each action before it runs:
1. **Checks:** admin; `nvidia-smi.exe` answers and its driver is 580 or newer (record only "580 or newer: yes/no");
   C:'s free GB; the inputs exist (`test.mp3`, `b.*` and `c.*` required).
2. **Refusals:** a distro named `Ubuntu-26.04` already exists (`wsl -l -q`): stop and say how to remove it or rerun with
   `-SkipPrep`. Never touch another distro except through `wsl --shutdown`, and warn before it ("this stops every WSL
   distro, including any Remote Control session in WSL").
3. **.wslconfig:** if `%USERPROFILE%\.wslconfig` exists, rename it to `.wslconfig.m408a-backup` (refuse if that name is
   taken). Restore it in a `finally` at the very end (the cleanup step), whatever happened, unless the owner answers
   that he wants to keep the test's file. Then `wsl --shutdown`.
4. **The distro:** `wsl --update`; `wsl --install -d Ubuntu-26.04 --no-launch`; then a user `sctest` with no password
   and no sudo (`useradd -m -s /bin/bash`), made the default in `/etc/wsl.conf` (`[user] default=sctest`), and `wsl
   --terminate Ubuntu-26.04`. If the image's first-run setup (OOBE) gets in the way of a root command, handle it or
   stop with a clear message: say in the report what you found in Microsoft's documentation and the image.
5. **The hand step:** print the release page's URL, the exact words to add, and wait for Enter. Then check from the
   distro that `~/.local/bin/songcharter` exists and runtime.json says the install finished; if not, stop.
6. **The Ubuntu part:** start the Windows VRAM logger (`nvidia-smi.exe --query-gpu=timestamp,memory.used,memory.total,
   utilization.gpu --format=csv -l 2` into the results folder) as a background process; run `m408a.py` in the distro
   (fetched by curl from `-Ref` into `~`, with the inputs' path converted by `wslpath`), its output both on screen and
   in a log; stop the VRAM logger when it ends.
7. **A20, memory after the run:** once the distro's processes have ended (the `wsl` call returned; then `wsl
   --terminate Ubuntu-26.04` is NOT used, since the point is WSL stopping by itself), sample the `vmmemWSL` (or
   `vmmem`) process's memory every 10 s for up to 6 minutes; record when it drops below 1 GB, or that it did not.
8. **The manual list** (printed, and written into the results folder as a checklist to fill in):
   - Start menu > "songcharter": does the page open, and does its header say "GPU: NVIDIA GeForce RTX 5070 (12 GB)"
     and "guitar on the GPU", with no "WSL has 7.8 GB" or "restart WSL" note? (A5)
   - Close the songcharter window during a chart's guitar stage, then check that no `node` or `songcharter.cli` is
     left (`ps` line given) (A9: the harness only sends the signal the window sends).
   - Clone Hero: Scan Songs (the menu path as found), play the test song on Expert with lyrics on: in sync? lyrics in
     time? (A12, M4-10)
   - Optional: sleep mid-chart (A21), offline (A13), each with its steps.
   Then: "Press Enter when done."
9. **Cleanup:** copy the results folder from the distro to `%USERPROFILE%\Desktop\m408a\results-<UTC stamp>\`; ask
   (typed "yes") before `wsl --unregister Ubuntu-26.04`; restore `.wslconfig` (step 3); `wsl --shutdown`; print the
   results folder's path and what to send.

On any failure: say which step, leave the distro as it is for inspection, still restore `.wslconfig` (asking first),
and write what was collected.

## The Ubuntu driver (`m408a.py`)

Runs as `sctest` in the distro, `python3` (the image's), standard library only. Arguments: `--inputs DIR`,
`--results DIR` (default `~/m408a-results`), `--release vX.Y.Z`, `--quick` (CI: one short clip, CPU only, the steps
that need a GPU or Windows skipped and marked "skipped: not here").

1. **Loggers** for the whole run, in a background process: every 2 s WSL's available memory and swap used (`free`'s
   numbers, MB) into `mem.log`; every node process's VmRSS and VmHWM (`/proc/<pid>/status`, `pgrep -x node`) into
   `node.log`. Each line starts with the time.
2. **Checks (A4 and the release gate's items):** `songcharter doctor --json` (memory_matches_config, MemTotal, lane,
   `autochart_cuda`); `du -sh` of `~/.local/share/songcharter/runtime/uv-cache` and whether `~/.cache/uv` exists; `ss
   -ltn` shows songcharter listening on 127.0.0.1 only.
3. **The server:** start `songcharter ui --no-browser` in the background (its log kept), wait for `/api/hello`. Restart
   it the same way after the steps that stop it.
4. **The charts**, each through the API as the page does it (upload, POST /api/jobs with options, follow the events,
   then /results), each recording: the clock time, total and per-stage times, each take's device, `fallbacks`, the
   memory and VRAM peaks pipeline.json gives, and whether the Done screen's install and zip are available as soon as
   the result event arrives. In this order:
   - **A6:** test.mp3, Guitar takes 1. **A7:** the defaults (it times 3 takes: say so in the results).
   - **A19 + A18:** delete `~/.cache/songcharter/work` and `~/.cache/songcharter/ac`; start a VRAM filler holding
     2.6 GB (the friend's desktop at idle: about 9.5 GB left of 12) with the install's own torch
     (`~/.local/share/songcharter/runtime/env/bin/python`); chart with the defaults; stop the filler; copy notes.chart
     aside; delete the folders again; chart again; `cmp` the two notes.chart files. Record identical or not, and with
     the filler: any take failed or fell back to the CPU.
   - **A22:** Device CPU, Guitar takes 1; then `demucs` in that take's `autochart_run/summary.json`; compare with A7/3
     (or A6 if the cache did not answer), as M4-08 says.
   - **Lyrics** (when `lyrics.txt` exists): the defaults with the text as the job's lyrics. Record the first-use
     download's time and the Done screen's word and phrase counts. The text is read only to send it to the job and for
     the A24 check: never printed, logged or copied into results.
   - **Take Me Out** (when `takemeout.wav` exists): the defaults; copy its notes.chart into results for scoring.
   - **A8:** b.* with the defaults; cancel when the events show take 1; time to the job's end; then no `node` or
     `songcharter.cli` process left.
   - **A23:** b.* again with the defaults; when the events show take 2, start a filler that takes VRAM in 256 MB blocks
     until allocation fails (at most 12 GB) and holds it until the job ends (at most 15 minutes); record the Done
     screen's error text (it may hold paths: see Privacy); release; chart b.* again and record which takes ran.
   - **A9 (signal):** c.* with the defaults; during the guitar stage send the server the signal a closed window sends
     (SIGHUP); check that no `node` or `songcharter.cli` is left; restart the server.
   - **A10:** upload test.mp3 under the name `Déjà Vü, Test – 1.mp3`, Guitar takes 1; record that the upload, the chart
     and the folder name are right; export the zip and record its name.
   - **A11:** "Install into Clone Hero" for the lyrics chart (or the test song's latest) through the API; if the Songs
     folder is not found, record that and skip; install again: expect the replace question (409), replace, and check
     one folder of that name is left.
   - **A24 and diagnostics:** GET /api/diagnostics into results; `packaging/ci/check_no_audio.py` on it (fetched from
     `--release`'s tag); then the pasted-text check from M4-08 (three words in a row, the song's title and file name
     left out), printing only yes or no. If yes, the zip is moved out of results into a folder named
     `DO-NOT-SEND`, and the summary says so.
   - **A16, last:** write everything collected so far first. Then `songcharter uninstall` answering No (to the
     downloads and to .wslconfig), and the install line taken from the release's notes (GitHub's API) with `--yes
     --windows-ram-gb 16`; record its time, the bytes it downloaded, the count of songcharter shortcuts in the Windows
     Start menu folder, and chart test.mp3 with Guitar takes 1 from the reinstalled app. Check install.sh first: if
     this reinstall would restart WSL (killing the run), skip the restart-causing case and say why.
5. **Results:** `results.json` (every A-number, with its value, pass/fail where M4-08's pass list gives one, or
   "manual"), `summary.md` (one line each, in M4-08's terms), the logs, and the two A18 charts. Exit 0 when every
   automated pass line passed, 1 when one failed, 2 when the run could not go on (bad input, the install missing).

## Privacy and the hard rules

- Everything the harness writes for the owner to send is scrubbed before it is written: the Linux user name, the
  Windows user name, home and profile paths (replaced by `<home>`, `<profile>`), the PC's name; inputs named by their
  label (test, b, c, takemeout), never their titles or file names. The diagnostics zip is sent as it is (it is for
  the director only, never committed), but only when A24 says no.
- Lyrics: never printed, logged, compared in a way that prints words, or copied (M4-10's rule).
- No exact driver, Windows or WSL versions in what the harness writes: "580 or newer", "Windows 11", "WSL updated".
- The scripts change nothing outside the test distro, its results and `.wslconfig` (set aside and restored), and
  delete nothing but the test distro (asked) and their own temp files. No network, power or security settings.

## Tests and CI

- **The Ubuntu driver in CI:** a new hook `packaging/ci/linux.d/80-harness.sh` runs `m408a.py --quick` in the
  ubuntu:26.04 container after an install (reuse an earlier hook's install and clip if the hook layout allows; at
  most about 6 minutes added to the linux job), with a made-up lyrics.txt ("zorp blen ..."), a stand-in Songs folder
  as 60-results has, and checks results.json: every automated step present, the quick mode's skips marked, the
  privacy scrub (no container user name or home path in any file it wrote), and the A24 check's "no".
- **The PowerShell script in CI:** a `packaging/ci/windows.d/` hook parses it (PowerShell's parser, no errors) and
  runs it with `-DryRun` and a temp `-Inputs` folder: exit 0, every step printed, nothing created outside the temp
  folder, `.wslconfig` untouched.
- **Unit tests** (tests/test_harness.py) for the parts that are pure functions: the scrub, the pasted-text check, the
  install line's extraction from release notes, the event parsing (take k of n), results.json's shape.
- Each new test fails when the code it covers is broken (say which break).

## Docs

- M4-08: a section "Part A, automated (M4-08a)" before part A's steps: the owner's five steps above with the exact
  commands, and which A-numbers stay manual. Part A's hand steps stay as the fallback.
- `packaging/hardware/README.md`: what the scripts do and do not touch, their parameters, and how to rerun.
- PROGRESS: in_flight, and M4-08's next step.

## Limits

- No change to songcharter itself. If the harness finds the app cannot do something it needs through the API, say so
  in the report instead of changing the app.
- Time budget about 4 hours, CI included.

## Report

`<scratchpad>/briefs/m408a.report.md`: the commits, each section above with what was done, what could not be tested
here (everything Windows does beyond the dry run), the checks with their last lines, and anything uncertain.
