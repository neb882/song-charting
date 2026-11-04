# M4-04 report: the local UI in WSL (server, jobs, progress, cancel)

Branch `m4-04-ui-server` (worktree `scratchpad/wt/m4-04`), from `main` at 656991d. Pushed (head f5c717b); not
merged, and `main` not merged in (the director does that).
Paths below: `S` = `/tmp/claude-0/-home-user/5307d417-c453-5e74-8f13-b43b2df06ab1/scratchpad`.

## Commits

| commit | what |
|---|---|
| 508698b | `songcharter ui`, `chart --events`, `proc.Tree`, the job and its cancel; the page; tests; hook `40-ui.sh` |
| a463e70 | one cancel at a time (the jobs lock held throughout); `Tree.kill` waits (≤ 2 s) after SIGKILL for the group to empty; two tests added after mutation testing |
| fa55ced | a closed SSE stream means a final state; a new job waits (≤ 10 s) for one whose result is out; the hook polls the state; an empty `data:` icon |
| 415e638 | the job's reader always ends the job, even when its log cannot be written (a full disk); a test that fails on the old reader |
| f5c717b | tests: made-up names only (the coordinator's new rule: real artist names and a profile-shaped path replaced) |

Each ends with the two attribution lines. No model names elsewhere.

## What changed

**`pipeline.chart(..., events=None)`** sends `plan {stages}`, `stage_start {stage, index, count, detail}` (index from
1, as the log's `[k/n]`), `take {index, count, seed}`, `fallback {stage, from, to, reason}` (every record, also those
only recorded, such as "auto" on a machine with no GPU), `warning {text}`, `stage_end {stage, seconds, cached,
detail}`. A stage that stops (an error, a preview that fails) sends no `stage_end`; the page marks such a row stopped.
`Engines.guitar(..., on_take=None)` passes it to `autochart.generate`.

**`engines.autochart.generate(..., on_take=None)`**: `on_take(index, count, seed)` before each take that runs (not one
the cache answers), index from 1 among its `seeds`. The pipeline renumbers among all the stage's seeds, so the CUDA
default's probe (1 take alone, then 3) gives take 1..4 of 4; a probe that moved to the CPU gives only "1 of 4" and then
its `fallback`.

**`cli`**: `chart --events` writes `@@songcharter <json>` lines (ASCII) to stderr; after the summary, `result {ok,
exit, folder, work, preview (the work folder's preview/ or null), summary (stdout's text)}`; before exit 2/3/130,
`error {kind, message}`, kind `input` (InputError, OSError), `tool` (ToolError, other SongcharterError), `bug`,
`interrupted`. Without `--events` nothing changes. `songcharter ui [--port N] [--no-browser] [--from-shortcut]`.

**`songcharter/proc.py`**: `start(cmd, env, cwd, stdout, stderr) -> Tree` (`start_new_session=True`, stdin from
/dev/null); `Tree.kill(timeout=5)`: SIGTERM to the group, SIGKILL after the timeout when the leader or any member still
runs, `wait()`, then up to 2 s until the group is empty (a signal lands only when the process next runs: under load
the grandchild was seen alive just after `kill` returned). Idempotent and thread-safe. Zombies count as gone
(`alive`, `group_alive` read `/proc`), since a container's PID 1 may not reap orphans.

**`songcharter/ui/`**: `server.py` (startup 1–6, guards, API), `jobs.py` (the job), `static/` (the page),
`__init__.home()` (`$SONGCHARTER_HOME`, else `~/.local/share/songcharter`, M4-03's layout).

**`pyproject.toml`**: `songcharter.ui` and `static/*.{html,js,css}` as package data. `uv lock --check` (uv 0.13.5):
`Resolved 114 packages`. A built wheel holds `songcharter/ui/static/{index.html,app.js,app.css}`.

**CI**: `packaging/ci/linux.d/40-ui.sh` (the hook contract of `linux.d/README.txt`).

**Tests**: new `tests/test_proc.py` (4), `tests/test_ui_server.py` (13), `tests/test_ui_jobs.py` (29); in
`tests/test_pipeline.py` the guitar stand-in takes `on_take`, the real-engines test checks it is passed, and three
events tests; `tests/test_engines_autochart.py` one `on_take` test.

### Decisions the order left open (each small; say if any should change)

1. **The child's stdout is merged into its stderr pipe** (`stderr=STDOUT`): one ordered stream, no second pipe left
   unread (a deadlock risk), and the summary lands in the job log too. The CLI flushes stdout before `result`.
2. **`/api/hello` also returns `"url"`** (the address this instance opened), so a second start opens the right page
   even when the first one is on the fallback address.
3. **The upload's `"tags"` are song_metadata's values** (name, artist, album, genre, year, …), and `"origin"` where
   each came from; not ffmpeg's raw tag dump, which can hold a lyrics tag (CLAUDE.md: never reproduce lyrics). The
   prefill uses the file's name as dropped (`Jörg's Söng`), not its safe stored form.
4. **The page sends every non-empty song field** (`--title=...`), so the chart gets what the page shows; the
   "Unknown" placeholders stay empty (the CLI's default). pipeline.json then says "given" for those fields.
5. **Self-check: any non-passing answer** (another token, or none) moves to the next port; after all 20, the
   fallback re-binds the first free port on 127.0.0.1 and on WSL's own address (superseded in 608c45b: see the end
   of "Review fixes"). URL opened:
   `http://localhost:<port>/` in WSL (what the check proved), `http://127.0.0.1:<port>/` elsewhere.
6. **`--port N` means that port only** (the "already running" check and the bind); out of range exits 2.
7. **A kill not ours** (the kernel's OOM killer) ends `failed` with "stopped by SIGKILL (by the system: out of
   memory, perhaps)", not `cancelled`; exit 2/3 or 0/1 without a closing event get an `error` with the log's last 8
   lines, so the SSE stream always closes.
8. **Timing races found by driving the page**: the stream waits (≤ 10 s) after its closing event until the job's
   process exits, and `POST /api/jobs` waits (≤ 10 s) for a job whose result is out, instead of a 409.
9. **Upload limit** 10^9 bytes (the project's GB unit); 411 without Content-Length; a refused small body is drained
   so the client reads the answer.
10. **`--from-shortcut`** is accepted and noted in the UI log; the "Press Enter" pause is M4-03's launcher's.
11. The page's options have no threads field (the order's list has none); the API accepts `threads`.

## Done means: the checks, with commands and last lines

### 1. The suite (dev container)

`SONGCHARTER_SCAN_CHART=/home/user/song-charting/tools/scan-chart/scan.cjs S/venv/bin/python -m pytest -q -p no:cacheprovider --basetemp=/dev/shm/pt_m4_04`

- at 508698b: `625 passed, 3 skipped in 727.56s (0:12:07)`
- at fa55ced: `626 passed, 3 skipped in 819.46s (0:13:39)` (ran partly beside the first golden run)
- at 415e638 and f5c717b: the UI tests locally (`test_ui_jobs.py test_ui_server.py test_proc.py`: 47 passed at
  415e638; jobs + server 43 passed at f5c717b), and the full suite in CI (below). Not rerun locally at f5c717b: after the golden run, M4-10's
  golden run held `tools/heavy.sh`'s lock for hours, and f5c717b changes only test fixtures since 415e638.

The named tests: `test_proc.py` (child + grandchild `sleep 60`, both dead by pid after `Tree.kill`; SIGTERM ignored
→ SIGKILL after the timeout; a leader gone by itself, its orphan still killed; zombies count as gone).
`test_ui_server.py`: `Host: evil.example` 403 (also a wrong port, no Host); POST without the header, with a foreign,
`https`, `null` or missing Origin 403 on all three POST routes; OPTIONS preflight 403 and no `Access-Control-*`
ever; `.txt` 415; 202 then 409 (stand-in runner), 400 with Options.check()'s message; SSE replays to a late client,
resumes after `Last-Event-ID`, streams with keepalives to an early one, ends with `cancelled`; the CSP (exact
string), nosniff and no-referrer on 200/403/404/415/400/SSE and on http.server's own 400; `..`, `%2e%2e`,
`..%2f`, `/static/app.js` and others 404; the self-check moves past a port where Windows answers another token,
and with every port failing allows the fallback address (127.0.0.2 here) as Host and Origin; `songcharter ui` as a
process: answers, a second start exits 0 naming it, SIGTERM stops it within 5 s. `test_ui_jobs.py`: `@@songcharter`
parsing; a stand-in that exits 1 ends `done` with `ok: false`; cancel ends `cancelled`, the stand-in's
`.<name>.x1y2.partial` gone, its grandchild dead by pid; two cancels at once give one `cancelled`; exit 2/3/0 without
a result, and SIGKILL from elsewhere, end `failed` with an error.

**Each test checked by breaking the code** (`S/m4-04/mutate.py`, 26 breaks: no new session, killpg → kill, no
SIGKILL, each guard removed, no CSP, static by path, any extension, no size limit, no 409, SSE without replay,
self-check ignored, fallback not allowed, events without the prefix, exit 1 as failed, staging kept, an OOM kill as
a cancel, no threads default, the probe's numbering restarted, no take/result/error events, events not ASCII, a
recorded-only fallback not sent, on_take for cached takes). First pass 24 of 26 caught; I added two tests (a
same-length foreign prefix; the no-GPU recorded-only fallback); then 26 of 26 (`S/m4-04/mutate.txt` and the rerun).

### 2. The clip with `--events` (one real cold chart)

`S/m4-04/clip_events.sh cold`: `songcharter chart /dev/shm/m4-04/clip.wav --out /dev/shm/m4-04/Clip --device cpu
--threads 2 --events` (clip from `packaging/ci/make_clip.py`, 30 s; `SONGCHARTER_AUTOCHART=S/eval/tools/autochart`).

```
exit 0
events: 20 {'plan': 1, 'stage_start': 8, 'stage_end': 8, 'warning': 1, 'take': 1, 'result': 1}
plan: ['decode', 'separate', 'drums', 'bass', 'sections', 'guitar', 'assemble', 'preview']
start/end pairs: 8 8 True
takes: [{'event': 'take', 'index': 1, 'count': 1, 'seed': 20260609}]
last: {'event': 'result', 'ok': True, 'exit': 0, 'folder': '/dev/shm/m4-04/Clip', 'work': '.../work/clip-c5b7ed9068d6e937', 'preview': '.../preview'}
summary equals stdout: True
check_gate: ok, /dev/shm/m4-04/Clip: gate ok, scan-chart 8.0.1 playable with 0 chart issues; Expert onsets guitar 23, bass 120, drums 119
stages: decode 0.3 s, separate 22.1 s, drums 2.2 s, bass 3.8 s, sections 2.0 s, guitar 65.7 s, assemble 4.2 s, preview 2.6 s; total 102.8 s
```

**Without `--events`, against main** (`clip_events.sh warm`: main's checkout, then this branch, same warm cache).
`main` had moved to 3402bfd by then; 656991d..3402bfd touches no `songcharter/` file (docs, `packaging/ci/test_ci.py`,
an agent file). Results:
- stdout: identical but for the stage times and the output folder's path (17 lines);
- stderr: identical but for the times and the output folder's name (17 lines); no `@@songcharter` anywhere;
- `notes.chart`, `song.ini`: byte-identical across the cold `--events` run, main's and this branch's;
  `report.json`: equal but for the output paths;
- `song.ogg` differs in 288 bytes: each Ogg page's stream serial and CRC. **Pre-existing**: two runs of main's own code
  differ in the same 288 bytes; the 36 pages' payloads are identical. Not a byte-identical check I can pass for
  `song.ogg` on any commit (see "for PROGRESS").

The byte-identity of the non-events output is also a test (`test_chart_events`, stand-in engines: every non-event
stderr line and stdout equal, times masked).

### 3. Manual: `songcharter ui --no-browser --port 8799` (`S/m4-04/ui_manual.sh`, curl)

```
guards: Host 403, Origin 403, .txt 415
upload: {"id": "c5b7ed9068d6e937", "name": "clip.wav", "bytes": 5292044, "tags": {"name": "clip", "artist": "Unknown", ...}, "origin": {"name": "file name", ...}}
job 1: done exit 0 [plan, 8 start/end pairs, a warning, result]   result ok: True, folder .../library/c5b7ed9068d6e937/Unknown - clip
job 2 (3 takes): first take event: {'event': 'take', 'index': 2, 'count': 3, 'seed': 101}
before cancel (group 23159): the chart (python -m songcharter.cli chart ...), node ac_headless.cjs, node autochart-engine.cjs
cancel answered in 0.07 s: {"job": "20261103-222644", "state": "cancelled"}
after cancel, by argv: no node, ac_headless, autochart-engine, allin1_runner, ffmpeg or songcharter.cli chart
job 2: cancelled exit -15 [..., 'take', 'cancelled'];  partial folders in the library: 0
server stopped after SIGTERM in .98 s
```
(`ps -eo pid,pgid,args` before and after are in `S/m4-04/evidence/ui-ps-*.txt`.)

**The page in headless Chromium** (not asked for; `S/m4-04/page_drive.mjs`, CDP): load, pick the clip in the file
input, keep the options (device CPU), Chart it, follow to Ready, reload (reattaches: Ready, 8 rows), Chart another
song, a 3-take job, Cancel with its confirm accepted. Screens `S/m4-04/page/{1-drop,2-options,3-progress,4-done,
5-take,6-cancelled}.png`, looked at: header "CPU mode: no NVIDIA GPU found" / "guitar on the CPU: no GPU", Details
with doctor's notes; title prefilled "clip", the others with the "Unknown" placeholder; one row per stage with ✓,
time and detail; "take 2 of 3" under Guitar; the warning listed; "Ready" with the summary; "Cancelled" with the
Guitar row ✕ "cancelled". Console: no CSP violation, no script error (only Chromium's `/favicon.ico` 404, since
fixed with an empty `data:` icon). This run found the race fixed in fa55ced (decision 8).

### 4. The golden charts

CLAUDE.md's release gate, `RERUN="--rerun guitar"` on both sides (`engines/autochart.py` changed, so golden's
staleness check needs the guitar rerun), `EXPECT=none`, `--threads 2`, the env of `S/m4-02probe/golden_env.sh`
(`EVAL_DATA`, `SONGCHARTER_GOLDEN`, `SONGCHARTER_AUTOCHART`, `SONGCHARTER_ALLIN1_PYTHON` = research/timing/venv2,
`SONGCHARTER_SCAN_CHART`).

- **Old** (main 656991d, the merge base): my first run, `python -m eval.golden run --code /dev/shm/m4-04/golden-old
  --out /dev/shm/m4-04/golden/old --threads 2 --rerun guitar` → `old exit 0 in 6252 s`, all 7 songs gate OK. The
  machine restarted at 01:29 UTC and wiped /dev/shm; as the coordinator said, the old side is that run's saved
  summary (`S/briefs/baseline/summary.main-656991d.json`: commit 656991d, rerun guitar, 7 songs), copied back.
- **New** (f5c717b, clean): `tools/heavy.sh python -m eval.golden run --out /dev/shm/m4-04/golden/new --threads 2
  --rerun guitar` → `new exit 0 in 2887 s`; every song `gate OK; ran guitar`, e.g. take_me_out "Expert F1@50 bass
  0.912, drums 0.944, guitar 0.909", all_the_small_things "guitar 0.971".
- **Diff**: `python -m eval.golden diff /dev/shm/m4-04/golden/old /dev/shm/m4-04/golden/new --expect none` →
  `diff exit 0`, `golden diff: no UNEXPECTED change`. report.md: engines asked to rerun `guitar | guitar`, engines
  that ran `guitar on 7 songs | guitar on 7 songs`; "**No UNEXPECTED change.** Parts changed as expected: 0. Every
  song's results (hashes, counts, scores) identical: yes."

Evidence (no audio): `S/m4-04/golden-evidence/` (new.log, summary.json, report.md, diff.log, the exit files).

### Personal details (the coordinator's new rule, before the final push)

`git diff 656991d...HEAD` and `git log --format=%B 656991d..HEAD` grepped for home and profile paths (`/home/`,
`/root`, `/tmp/claude`, the scratchpad, `Users\`), emails, the repository owner's name, machine names and artist
names. Found and replaced (f5c717b): real artist names in test fixtures ("AC/DC", "Mötley Crüe", a song title) and a
Windows-profile-shaped path with a made-up name (`C:\Users\Jörg\Music\...`). Now the only matches are `@pytest`
decorators; the commit messages have none but the attribution trailer; author and committer are
`Claude <noreply@anthropic.com>`. **The earlier commits 508698b–415e638 still hold those fixture strings** (no private
data: public band names and the made-up "Jörg"); I did not rewrite history (no force-push). A squash merge would keep
them out of `main`'s history, if wanted.

### [CI]

- run 41729206724 (a463e70): **failure**: the suite passed, hook 40-ui failed: it read the job's state right after
  the stream closed at `error` and got `running` (the race of decision 8).
- run 41732876363 (fa55ced): **success**, both jobs. Linux: test_ci 78 passed; suite `628 passed, 1 skipped`; hooks
  `all 3 Linux hooks passed: 10-lanes.sh 15s 20-device.sh 6s 40-ui.sh 15s`. 40-ui's lines:
  ```
  46 passed in 9.79s
  40-ui: Host evil.example: 403
  40-ui: a POST without X-Songcharter: 403
  40-ui: Origin evil.example: 403
  40-ui: a .txt upload: 415
  40-ui: the clip uploaded: 200
  40-ui: a job started on the clip: 202
  40-ui: job 20261103-224704: failed (exit 2), events ['error']
  40-ui: its end: {"event": "error", "kind": "tool", "message": "cannot chart: the guitar needs autochart's engine (...)"}
  40-ui: cancel with no job running: 409
  40-ui: ok
  ```
  The job on the clip starts (202) and, with no autochart engine on the runner, ends `failed` at the component check;
  the hook checks it reached a final state with a closing event. The real cancel at the first `take` is M4-05's.
- run 41739453686 (415e638): **success**; suite `629 passed, 1 skipped`; `all 3 Linux hooks passed`.
- run 41749744269 (f5c717b, head): **success**; suite `629 passed, 1 skipped in 219.68s`; `all 3 Linux hooks passed:
  10-lanes.sh 14s 20-device.sh 5s 40-ui.sh 14s`.

## Not done, or uncertain

- **docs/ untouched** (the order forbids it). For the director's doc pass:
  - DESIGN §4.5: "Status: none of the UI is built" → built in M4-04 (screens 1–3: drop, options, progress with cancel
    and fallbacks; guards as built: Host list, `X-Songcharter: 1` plus Origin on every non-GET, the CSP, no CORS,
    exact static names); the tempo option and chord-density slider are not on the page (the CLI has neither);
    preview/export are M4-06's.
  - DESIGN §2.0 (code status): `proc.py`, `ui/`; the CLI section and README: `songcharter ui`, `chart --events`.
  - PROGRESS: M4-04 built; `deferred`: (a) `song.ogg` is not byte-identical across runs (the Ogg stream serial,
    pre-existing; the chart files are); (b) the WSL self-check (`curl.exe`), the fallback address and
    `explorer.exe` are tested only with stand-ins here: M4-08.
- **The M4-03 coupling**: `launch.main` with no arguments should call `cli.main(["ui"])` (the shortcut passes
  `ui --from-shortcut`, which `ui` accepts). The UI reads `$SONGCHARTER_HOME`, which M4-03's `environment()` sets.
- **For M4-05's ui_guards.py**: on a warm cache the default seed's take is cached and sends no `take` event (only takes
  that run do); on a fresh install it runs. The stream now closes only once the job's state is final.
- **Not run here**: anything on WSL or Windows; a GPU (CUDA fallback banners are tested with stand-ins only).
- My first golden run overlapped my fa55ced suite run for about 13 minutes (another session's job paused, and my
  wait gate let it start before the suite grew); both passed. Its old side finished (exit 0, 6252 s, every gate OK);
  its new side was killed by the machine's restart at 01:29 UTC, 4 songs in (all 4 gate OK). The new run after the
  restart went through `tools/heavy.sh` (main's lock), against the saved old summary.
- Disk: my new use is under 10 MB (evidence and scripts in `S/m4-04/`, the worktree); `/dev/shm/m4-04` (the golden
  outputs) is deleted at the end, the clip's cache went with the restart.
- Scripts used: `S/m4-04/{clip_events.sh, ui_manual.sh, page_drive.mjs, mutate.py, golden.sh, golden_new.sh}`.

## Review fixes (1c94e60)

Review: `S/briefs/m4-04.review.md` (six findings). One commit, 1c94e60, pushed.

| finding | fix | test (fails on the old code or under the reviewer's break) |
|---|---|---|
| F1 (major) | none needed in code | `test_stopping_the_server_kills_the_running_charts_whole_tree[SIGTERM, SIGHUP, the window closes]`: the real `server.main` (a driver swaps in the stand-in chart, as the reviewer's `driver.py`), a job at its take with a grandchild, then the stop; checks exit 0, both pids dead, "cancelled (exit -15)" and "stopped" in the log. "The window closes" makes a pty the server's controlling terminal (`setsid -c`) and closes its master: a real hangup, with every console write then failing (EIO) |
| F2 | `partial_folders` uses `glob.escape(out.name)` | a cancel of "Song [Live] *?" leaves no staging; `partial_folders` finds `tempfile.mkdtemp(prefix=f".{name}.", suffix=".partial")` (assemble's own naming) for 4 names with `[` / `]`, and not another song's folder |
| F3 | a job whose `result` is out is `done` whatever its exit, in `cancel` and in `_finish`; one with its `error` out stays `failed`; no `cancelled` added | a cancel in the second after `result` (the `linger` stand-in) gives `done`, exit -15, one closing event; a chart that exits 3 after its result is `done` |
| F4 | none needed in code | `test_chart_events_when_the_gate_fails`: `result` is `{ok: false, exit: 1, folder: <out>.failed}`, its summary equals stdout, exit 1 |
| F5 | `Log` catches OSError/ValueError from the console as from the file, and then gives the console up; the default console writes unbuffered (`os.write(1, ...)`) so nothing is left for the interpreter's exit to flush onto a dead terminal; `_main`'s stop closes the servers and logs "stopped" even if the job's stop raises | the "window closes" case above (old code: exit 3) |
| F6 | none needed in code | `test_sigkill_reaches_a_member_that_outlives_sigterm_while_the_leader_dies`: only a grandchild ignores SIGTERM; kill returns -15 after the 1 s timeout, nothing of the group alive |

**Breaks, each on a fresh copy with the reviewer's `S/review_ui/mutate.py`** (`S/m4-04/review_muts.json`,
`S/m4-04/review_mutate.txt`): all 9 caught.
```
M1-no-shutdown-on-stop: CAUGHT  ['1 failed, 13 passed in 7.85s']
M2-no-sighup: CAUGHT  ['1 failed, 14 passed in 8.44s']
M3-sigkill-ignores-group: CAUGHT  ['1 failed, 53 passed in 16.17s']
M4-cancel-never-keeps-done (adapted): CAUGHT  ['1 failed, 42 passed in 12.17s']
M7-result-exit-wrong: CAUGHT  ['1 failed, 2 passed, 29 deselected in 51.41s']
M7b-result-ok-always-true: CAUGHT  ['1 failed, 2 passed, 29 deselected in 50.29s']
F2-old-code (glob not escaped): CAUGHT  ['1 failed, 44 passed in 12.56s']
F3-old-code (exit decides): CAUGHT  ['1 failed, 42 passed in 12.30s']
F5-old-code (console unguarded, buffered): CAUGHT  ['1 failed, 15 passed in 9.89s']
```
M4's original text no longer exists (the `done` branch is now `if job._has("result")`), so it is applied to the new
branch: `if False:`.

**Tests run** (outside the heavy lock, which M4-10's golden run held; stand-in engines only):
`pytest tests/test_ui_server.py tests/test_ui_jobs.py tests/test_proc.py tests/test_pipeline.py tests/test_engines_autochart.py`
→ `98 passed in 393.20s`; `tests/test_proc.py` again after a line wrap → `5 passed`. ruff (F, E, W, B): clean.

**CI** run 41764268082 on 1c94e60: success, both jobs; suite `639 passed, 1 skipped`; `all 3 Linux hooks passed:
10-lanes.sh 12s 20-device.sh 5s 40-ui.sh 17s`, 40-ui's lines as before (403, 403, 403, 415, 200, 202, the job ends
`failed` at the missing engine, 409, ok). No golden run: nothing on the chart path changed (only `ui/` and tests).

**Personal details:** the new diff and the commit message grepped as before: nothing but `@pytest` decorators.

**The fallback under WSL's mirrored networking (for M4-08; no code change, as asked).** Yes: the fallback can bind
and advertise an address another machine could reach.
- `wsl_address()` takes the first address of `hostname -I`, whatever it is; `bind()` binds it on the port, allows
  it as a Host and an Origin, and opens `http://<it>:<port>/`.
- Under NAT (the default) that is the VM's address on the host-only `vEthernet (WSL)` network: no other machine
  routes to it [inference, as the order says].
- Under mirrored networking the Linux side carries the Windows host's own interfaces, so the first address can be
  the PC's LAN address (192.168.x.y): the server would then listen on the LAN, reachable from another machine unless
  the Hyper-V firewall or Windows Firewall blocks the port [inference; the firewalls' defaults are untested here].
- The guards would not stop such a client: they are against browsers (DNS rebinding, cross-site requests). A
  program on the LAN sends `Host: <ip>:<port>`, `X-Songcharter: 1` and `Origin: http://<ip>:<port>` itself, and
  could upload files and start or cancel charts.
- When it triggers: only when the self-check fails on all 20 ports. In mirrored mode localhost is shared, so the
  check should pass; it would fail only with every port taken on Windows, or with `curl.exe` missing or failing.
  With interop off there is no check and no fallback.
- Also: with Docker inside WSL, the first `hostname -I` address can be a bridge (172.17.0.1), unreachable from
  Windows: then the fallback page would not open.
- A guard M4-08 or a later order could add: no fallback when `.wslconfig` says `networkingMode=mirrored`
  (`wsl.wslconfig()` already reads it), or only addresses in WSL's NAT range (172.16.0.0/12), else localhost only
  with the message.

**Follow-up, 608c45b (the coordinator's rule: never listen where another machine can reach).** The fallback happens
only under NAT: `fallback_address` refuses any `networkingMode` but NAT (mirrored, bridged, virtioproxy; read from
`wsl.wslconfig()`), takes the default route's source (`ip route get 1.1.1.1`'s `src`, else the kernel's choice for a
UDP socket to 1.1.1.1), not `hostname -I`'s first (Docker's bridge), and requires 172.16.0.0/12. Otherwise
`songcharter ui` listens nowhere and exits 2 with why, what to try (another port with `--port`, `wsl --shutdown`) and
the log's path. Tests: the modes refused, ten addresses in and out of range, the route source over a bridge listed
first, and the whole command (mirrored, an outside address, no address): exit 2, only 127.0.0.1 ever bound, nothing
left listening, the message. Six breaks (`S/m4-04/fallback_mutate.txt`: the mirrored rule, hostname -I, the range,
exit 0, the message without what to try, a refused fallback serving anyway): all caught. UI tests `74 passed`; CI
run 41765465113 on 608c45b: success, suite `657 passed, 1 skipped`, `40-ui: ok`, `all 3 Linux hooks passed`.
