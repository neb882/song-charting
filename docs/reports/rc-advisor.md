# The advisor on the release candidate, and the skeptics, 2026-11-04

The release gate's fifth check: an advisor on a different, more capable model read the v0.1 release candidate (main
at 2ab1f34, before the history rewrite) as a whole, from the friend's side, read-only. Its three findings that would
change code each went to a skeptic, who reproduced it; the rest were checked against the files by the orchestrator.
What was done with each is in `rc-fixes.md`. Details of the owner's and the friend's PCs are given only as the
requirements a check needs, as CLAUDE.md asks.

## The advisor on the release candidate (v0.1 for WSL), 2026-11-04

Read-only, on main at 2ab1f34. Read: CLAUDE.md, PROGRESS.json, PIPELINE.md (Gates), release-gate.md, M4-00-plan.md,
M4-08-hardware.md, M4-07's order and report, M4-10's rule, the guide, README, NOTICE.txt, install.sh, build.sh,
wslsetup.py, winshortcut.py, wsl.py, launch.py, runtime.py, device.py, clonehero.py, diagnostics.py, cli.py,
ui/server.py, ui/jobs.py, ui/static/{index.html,app.js}, engines/autochart.py, the guitar, sections and lyrics
stages of pipeline.py, the allin1 failure path of engines/sections.py, separate.py's device handling, CI's
30-install.sh and the head of 50-e2e.sh, the test names of test_install/test_wslsetup/test_winshortcut, DESIGN 4.7
and 5/M4, and autochart's engine source in the dev scratch (sessionLoader.cjs, the entry's fallback callback).
Probes (deleted after): install.sh's `choose_lane` with a stand-in nvidia-smi printing the friend's GPU; `wslsetup.plan`
on 15.4, 15.9, 16 and 31.8 GiB; a grep of the page and server for doctor's `problems`; a scan of the repository for
emails, profile paths and home paths; `git log` authorship.

Severity scale: **blocks M4-08** / **blocks the friend's release** / **should fix before the friend** / **note**.
"[reasoned]" marks what I reasoned about and did not run or verify.

### Findings, ranked

#### 1. A CUDA failure inside a guitar take ends the chart, 5-15 minutes in, with nothing to try — should fix before the friend, and an M4-08 check

- **Evidence.** `pipeline.py` guitar stage (lines 798-840) calls `engines.guitar` → `autochart.generate`, which raises
  `ToolError("autochart seed N failed (exit X): <tail>")` on any non-zero exit (`engines/autochart.py:254-256`); nothing
  catches it, so the chart exits 2 and the page shows "It did not finish" with the driver's last lines. The engine's
  own CPU fallback covers session *creation* only: `sessionLoader.cjs` `createSession` wraps `InferenceSession.create`
  in try/catch and latches to the CPU; `runSession` is `session.run(inputs)` with no catch. The separation, by
  contrast, retries on the CPU after `torch.cuda.OutOfMemoryError` (`separate.py:198-202`); the guitar has no such
  path, and the pipeline's "first take alone" probe (lines 806-823) only reads which device the engine *chose*.
- **Why it matters to the friend.** His 4070 has 12,282 MiB, with about 2.6 GB taken by desktop apps at idle
  (M4-08, "Added at M4-01"), so about 9.5 GB free; the smoke test's whole-system VRAM peak was 8,987 MiB *during the
  takes* on a card where the owner's desktop use is unknown. A browser with hardware acceleration or another
  launcher left open takes more. A run-time allocation failure in take 2 or 3 throws away 5-15 minutes and leaves him
  with an error that names a seed and node lines. Nothing says "set Device to CPU and Guitar takes to 1, or close the
  programs using the GPU". [Whether cudaMalloc fails or Windows pages other apps' VRAM out under WSL's dxgkrnl path:
  reasoned, not checked.]
- **Smallest fix.** In the guitar stage, when `gdev == "cuda"` and `engines.guitar` raises `ToolError`, re-raise with
  one sentence appended: "the guitar's GPU run failed: try again with Device: CPU and Guitar takes: 1, or close other
  programs that use the GPU" (no chart changes, no golden rerun). The better fix, a retry of that take on the CPU
  recorded as a fallback, touches the charting path and can wait for v0.1.1.
- **M4-08.** Record `nvidia-smi` (Windows) *before* each chart and the peak during it, once with a browser and a chat app
  open as the friend has them; and once provoke the failure (a VRAM-filling program during the takes) to see what the
  page says and that the next chart works.

#### 2. Nothing tells the friend how long a chart takes, and the 4-take default on his card is a 20-25 minute wait — should fix before the friend (guide text; a decision)

- **Evidence.** The guide (§5) says nothing about time or about the "Guitar takes" box; its only hint is "Windows has
  about 4 GB left for a few minutes". The smoke test: 959 s cold for the 412 s test song on a 5070 (the guitar 854 s,
  4 takes at 177-217 s each). The M4-08 rule "if 4 takes add more than 12 min to the guitar stage, the default goes
  to 1" was already at 10.7 min on the 5070 (854 − 213 s); a 4070 needs to be only 1.12× slower to cross it, and the
  rule is judged in part A on the 5070, so it can never trip where it matters. `guitar_takes` still tells the user
  "for 3.41x the guitar stage's time" (`pipeline.py:239`), the superseded figure (PROGRESS: 3.9×).
- **Why it matters.** He will chart a song, see "Guitar · take 1 of 4" tick past ten minutes, and either cancel (the
  work is kept, but he does not know that until he does) or assume it hung. Part B asks him to chart "once with Guitar
  takes: 1", which he cannot find from the guide.
- **Smallest fix.** One paragraph in §5: "With the defaults a 4-minute song takes about 15-25 minutes on a 4070 (the
  screen shows 'take 1 of 4'); for a quick chart, set *Guitar takes* to 1 in the options: about 5-8 minutes." Decide
  the default from the 4070's expected numbers now (scale the 5070's times by a known ratio, or wait for part B and
  plan v0.1.1 with 1 take), and fix the 3.41× text. The page could also show "(about N min)" beside the takes box
  later.

#### 3. Part A never runs the install line the friend will run — blocks the friend's release until someone has (an M4-08 ordering fix, no code)

- **Evidence.** M4-08 step 5: "Before the pre-release exists: `bash install.sh --from <folder>`"; step 18 pastes "the
  install line again" but the pre-release still does not exist then; M4-07: "The pre-release (done at M4-08, after
  part A passes)". A draft release's asset URLs are not public, so `--from` is the only option until it is published.
  So the GitHub download, the `sha256sum -c` line, the redirect through `objects.githubusercontent.com`, the
  licence prompt's NOTICE link at `blob/v<version>/` and the match between the pasted notes and the uploaded assets
  are first exercised by the friend. CI's 70-release.sh runs the line against a local server, which proves the
  script, not the release.
- **Also.** The build is `git archive HEAD`; M4-07's recipe tags "main's commit" and builds from the working tree, so
  nothing pins the tarball to the tagged tree. And M4-08 names `0.1.0-rc1` while `__version__` is `0.1.0`: doctor and
  diagnostics would print 0.1.0, the install and the app folder 0.1.0-rc1 (`app/0.1.0-rc1`).
- **Smallest fix.** Reorder: tag `v0.1.0`, `git checkout v0.1.0`, `build.sh 0.1.0 dist`, publish the pre-release (it
  is a pre-release on a repository only the friend is sent to), *then* run part A with the guide's line exactly as the
  release page shows it. If part A fails, delete the release and the tag, fix, publish again. Keep one version string
  (build `0.1.0`; GitHub's pre-release flag is the "rc"). Add **A17**: "the guide's line, copied from the release
  page, installs in a fresh distro; the licence prompt's link opens."

#### 4. The guide does not say what to do with memory after a chart, nor that the PC may sleep during one — should fix before the friend (guide text)

- **Evidence.** The install writes `memory=12GB` on a 16 GB PC (`wslsetup.plan`, probed: 15.4/15.9/16 GiB → 12).
  WSL2 keeps what it has taken until the distro and VM stop; `autoMemoryReclaim` is off by default and the install
  does not set it [reasoned from WSL's documentation; not checked]. The guide (§4) says "keep it open while you use
  songcharter", and (§5) "Chart first, play after", but not that closing the window is what gives Windows the memory
  back. A 20-minute chart with Windows at 4 GB is also long enough for a desktop's sleep timer; nothing in WSL keeps
  the PC awake [reasoned].
- **Smallest fix.** Two guide lines: "When the song is in Clone Hero, close the songcharter window before you play:
  WSL gives the memory back within a minute" and "A chart takes long enough for the PC to go to sleep; keep it awake
  (set Sleep to Never for the evening)". M4-08 A: after a chart, close the window and watch *Vmmem* in Task Manager;
  let the PC sleep once mid-chart and wake it: does the job finish, and is the clock right (the guide's §6 case)?

#### 5. "The same input gives a byte-identical chart" is unverified on the friend's path — note, with an M4-08 check

- **Evidence.** The golden charts run 1 CPU take (PROGRESS deferred); the smoke test's warm rerun reused the cached
  takes (37 s), so two cold 4-take CUDA charts of one song have never been compared; song.ogg already differs in its
  Ogg serial (deferred). CUDA kernels in cuBLAS/cuDNN are not bit-reproducible by default, and sampled decoding at
  temperature 0.95 amplifies any logit change [reasoned].
- **Fix.** M4-08 A: chart the test song twice with its work folder deleted between (`~/.cache/songcharter/work/…`),
  and `diff notes.chart`. If they differ, say so in DESIGN and PROGRESS: the rule holds on the CPU, and CUDA takes
  vary. Not a defect for the friend; a false claim in the repository otherwise.

#### 6. The page never shows doctor's *problems* — note, worth ten lines

- **Evidence.** `ui/server.py` `status()` (lines 263-268) returns `device, gpu, guitar_device, guitar_reason, notes,
  ok, source, error`; `app.js` `renderStatus` renders `notes` only; no `problems` anywhere in the page or in `status()`
  (grep). The problems are: ffmpeg/scan-chart/autochart missing, under 6 GB free in WSL or on C:, WSL under 8 GB.
  The realistic one is C: filling: the vhdx grows, `cache.py` prunes `work/` to 5 GB but `library/<id>/`, `exports/`,
  `replaced/` and `uploads/` (7 days) are never pruned (no "library" in cache.py).
- **Fix.** Return `problems` from `status()` and render them in red above the notes. Until then, a full disk shows up
  as an exit-2 OSError in the Done screen, which is readable.

#### 7. The install's last lines can say "doctor: 1 problem" and exit 1 five seconds before the restart that cures it — note

- **Evidence.** Step 8's doctor runs under the pre-install WSL memory (WSL's default is half of Windows' RAM); the
  closing summary is printed from that doctor.json (deferred), and so is `exit "$code"` (install.sh:396). With
  `MIN_WSL_MEMORY` at 8e9 bytes and MemTotal a few percent under the configured size, a PC reporting 15.4 GiB gives
  MemTotal ≈ 8.0e9: a coin toss (probed: 7.7 GiB → 8.02e9, just over). On the losing side the friend reads "problem:
  WSL has 7.4 GB of memory, under 8 GB: set memory in .wslconfig (the install writes it), then restart WSL" and
  "doctor: 1 problem", then the window closes. Self-explaining, but it is the last thing he sees.
- **Fix.** None needed for v0.1; M4-08 B should record the install's last lines from the friend's zip. Later: when
  step 9 wrote the file, drop that one problem from the summary and the exit code.

#### 8. Personal details: the results document, and commit authorship — note

- The repository scan found nothing of the owner's or the friend's: the only profile and home paths are test fixtures
  (`C:\Users\J…`, `/home/ann/`), docstring examples, CI's made-up `friend`, and third-party metadata under
  `tools/scan-chart/node_modules`, which is git-ignored (0 tracked files). No email addresses in tracked files.
- The diagnostics zips M4-08 reads carry the Linux user name (`python.executable`), the Windows profile path
  (`wsl.documents`, the Songs folder in `ui.json`), song titles and file names. M4-08's "Done means" should say that
  `M4-08-results.md` quotes none of those: hardware facts, times and sizes only.
- Every commit's author field names the assistant that built it (190 of 190 commits), not a person: the same
  information the trailer carries, in another field. If the rule means "the trailer and nothing else", this is an
  existing deviation the owner has evidently accepted; it cannot be changed without rewriting public history.

#### 9. Guide, docs and messages: small disagreements — note

- doctor and the server say "wsl --shutdown in PowerShell"; the guide says "in Terminal (right-click Start)". Both
  work; one wording would be kinder.
- PROGRESS's deferred list says NOTICE needs torchaudio and the wav2vec weights; NOTICE.txt already has both blocks
  (lines 43-46, 128-134): a stale deferred item.
- `guitar_takes`' reason text: "3.41x" (finding 2).
- README's "`%LOCALAPPDATA%\songcharter` on Windows" describes the native route, not v0.1; harmless.
- The guide's "about 4 GB left for a few minutes" understates (15-25 minutes with the defaults; finding 2).
- The lyrics stage's detail is "N words aligned to the vocal stem on cuda" while the first song with lyrics downloads
  1.26 GB inside that stage (deferred: no progress on the page): at 25 Mbit/s that is about 7 minutes of a ticking
  timer. One line in the stage detail ("downloading the aligner, 1.26 GB, once") would do.
- The 8 GB swap file grows on C: when used; the install's disk check (15 GB) does not count it; the guide's 20 GB
  figure probably covers it. Fine, but say so when M4-08 measures C:.

#### 10. Claims nothing has tested — note (most are already in M4-08's lists; these are the ones I did not find there)

- "In Clone Hero: Settings > General > Scan Songs" (guide §5, and the page's install message): the game's menu path
  is not verified anywhere; A12 will show it.
- "Open the Start menu, type songcharter and press Enter": the Start menu's search must have indexed a `.lnk`
  written through drvfs; pressing Enter on a search with no match opens a web search [reasoned]. The fallback is in
  the guide. A5 covers it.
- "the window closes" at the restart (§3): Windows Terminal's default closeOnExit keeps a tab open with "[process
  exited with code …]" when the process did not exit cleanly, and `wsl --shutdown` from inside is not a clean exit
  [reasoned]. Harmless; the sentence may just be untrue. A3 covers it.
- `wsl --update` then `wsl --install` on a PC with **no WSL at all**: the owner's PC already has WSL, so part A
  cannot test the inbox stub's behaviour; the friend is the first. Recoverable (the guide's error notes).
- Other software with kernel drivers beside the hypervisor: unknowable until part B; recorded there.
- `Get-CimInstance` under Smart App Control's constrained PowerShell: if it fails, `windows_ram_bytes` falls back to
  twice WSL's MemTotal, which gives 12GB on a 16 GB PC anyway (wsl.py:306-320). Robust by design.
- An upgrade (0.1.0 → 0.1.1's line) is tested nowhere: CI installs one version; `install.sh` removes the other
  `app/*` folders and rebuilds the wheel (setuptools from the cache or the network). Before v0.1.1, add a second
  build to 70-release.sh and run the new line over the old install.

#### 11. M4-08 itself — what to add, change or drop

Order and criteria are mostly right: install → doctor → 1 take → 4 takes → Take Me Out → cancel → close window →
non-ASCII → Clone Hero → offline → fallback address → settings.ini → diagnostics → uninstall/reinstall is the
friend's order, and the pass list names the things that matter (cu132, every take on cuda, no OOM, no process left,
the song plays). Suggested changes:

- **Reorder** (finding 3): publish the pre-release first; A17 runs the guide's line from the release page.
- **Add A18** (finding 5): two cold charts of the test song, `diff notes.chart`.
- **Add to A6/A7** (finding 1): `nvidia-smi` on Windows before each chart and the peak during it, with a browser and
  a chat app open; one provoked GPU failure during the takes, and what the page says.
- **Add to step 6** (finding 4): after a chart, close the window and watch Vmmem; one sleep mid-chart.
- **Add a criterion**: the page's diagnostics zip passes `check_no_audio.py` and, after the lyrics chart, holds no
  pasted word (grep the zip's members for one word of the owner's text, by hand, and report only yes/no).
- **Add a criterion**: after uninstall-No and the reinstall, the page starts from the shortcut and charts (A16 only
  checks the download size and the shortcut count).
- **A7's timing**: the 4-take run after A6 reuses the cached first take, so A7 measures 3 takes; that is exactly the
  "added" time the rule needs, but say so in the results so nobody reads it as a 4-take cold time.
- **Judge the 4-take rule for the 4070, not the 5070** (finding 2): either scale A7's time, or make part B's 4-take
  time the decision and plan the change for v0.1.1.
- **Part B's brief to the friend** must name where "Guitar takes" is (the options page, under Guitar), since the
  guide does not; and ask for the zip after the last chart (it holds only the newest 5 work folders and 10 logs).
- **Make optional if time runs short**: step 19 (the 22.04 install-only variant: the guide runs `wsl --update`, and
  CI reports 22.04 already) and step 15 (localhostForwarding off: a configuration the friend's fresh PC will not
  have). Keep step 3 (SAC on) if the switch allows: it is the one check nothing else can make.
- **Results doc**: no names, user names or profile paths from the zips (finding 8).

### What is fine (looked at and judged sound)

- **The lane for the friend's GPU**: probed `choose_lane` with "NVIDIA GeForce RTX 4070, <the friend's driver>, 8.9" → `cu132`,
  "driver <version>, compute capability 8.9", no warning. The 528/580 thresholds and the sm_120-under-580 case read
  right; a GPU out of reach on a GPU-lane install refuses the silent move to cpu.
- **The memory rule**: probed 15.4, 15.9 and 16 GiB → `write memory=12GB`, allin1 kept; 31.8 GiB → 28GB. CRLF for a
  new file, a backup of an existing one, only `memory` changed when asking, refusal under 8 GB, allin1 left out under
  11 GB. The docs (wslsetup's docstring, DESIGN 4.7, PROGRESS) agree with the code.
- **install.sh**: rerunnable at every step (CI kills it mid-sync and reruns), downloads through `.part` with resume
  and SHA-256, the licence prompt names a file that exists (the release's URL on a first install), uv's cache kept
  inside `runtime/`, the helper's exit codes mapped to one failure line, `exit 2` on failure and `1` on No or doctor
  problems: consistent with the exit-code rule. Its messages match the guide's wording (Continue? [Y/n]; "install.sh:
  OK/FAILED"; the two lane warnings and what to do; the restart line; the uninstall's prompts and the unregister line).
- **build.sh**: everything from HEAD (tarball, install.sh, the guide), uncommitted changes named, uv's published hash
  compared with the pin, no `@…@` or `{{…}}` left, SHA256SUMS; 70-release.sh runs the guide's line against a local
  server, including the tampered-file case.
- **The launcher**: `HF_HUB_OFFLINE=1` only once models are complete, no `SONGCHARTER_OFFLINE` (the gate's fix),
  `-P`/`PYTHONSAFEPATH`, Node first on PATH, `--from-shortcut` waits for Enter on any non-zero exit.
- **The shortcut**: a `.lnk` with no Mark of the Web whose target is `cmd.exe /c "wsl.exe -d <distro> --cd ~ -e
  <launcher> ui --from-shortcut || pause"`; cmd's quote rule strips the outer pair because `|` is inside them
  [reasoned]; `|| pause` keeps the window when wsl.exe itself fails; the distro name and launcher path are
  whitelisted (`SAFE`) and the fallback is said otherwise; a reinstall overwrites through `.part` and `os.replace`.
- **The server**: 127.0.0.1 only, Host and Origin guards, CSP, static files by exact name; the Windows self-check
  with an instance token; the fallback only under NAT and only on WSL's own 172.16/12 address, never a LAN address;
  SIGHUP/SIGTERM stop it and kill the job's process group; "already running" opens the existing page.
- **The job**: a process group, cancel = TERM then KILL, an OOM-killed child becomes "the chart was stopped by
  SIGKILL (by the system: out of memory, perhaps)" with the log's tail; the lyrics travel by memfd and never into a
  record; the Done screen takes the chart as soon as `result` is out (the gate's fix).
- **The sections' memory path**: a runner killed on CUDA is retried on the CPU, then falls back to librosa with a
  warning (`engines/sections.py:374-384`, backend auto); the separation retries on the CPU after a CUDA OOM.
- **Clone Hero's folder**: Documents from the registry (OneDrive followed), a typed path checked by a write probe,
  copy to a dot-folder then rename with retries, replace only our own charts, the older one moved out, leftovers tidied,
  the zip offered when blocked, "Open folder" through explorer.exe.
- **Diagnostics**: picks named files only, refuses audio by extension and magic, notes.chart, PNGs and files over
  5 MB, writes a manifest of what went in and what was left out; the page's link saves to Downloads.
- **NOTICE.txt** matches M4-07's verification table (each licence checked on the package); the non-commercial
  models are named up front; the README's licence paragraph agrees.
- **The lyrics rule** in the code and CI: no word in any record, log, event or answer; e2e asserts it.
- **doctor's wording** of the CPU reasons and the "paste the install line again" note, and that an install asked for
  `--lane cpu` does not get it.
- **The guide** reads in the friend's order with every term glossed; its Ubuntu commands are the ones CI runs.

### Not checked

The CI hooks beyond 30-install.sh and 50-e2e.sh's header; the Windows CI job; the tests' bodies (names only);
DESIGN.md beyond 4.7 and 5/M4; `eval/gpu.sh`; the ORT CUDA arena's growth (why the takes peak at 9 GB); WSL's
memory reclaim and Windows Terminal's close-on-exit behaviour (reasoned); Clone Hero's menus; the `wsl --update`
stub on a PC with no WSL; other kernel drivers. No test suite, golden run, install or real chart was run.

## The skeptics

### Skeptic: the advisor's RC finding #1 (a CUDA failure inside a guitar take)

main at 2ab1f34. Verdict: **partly confirmed.** The mechanics are exactly as the advisor says, and I reproduced them
through the real CLI and the UI's job path with a stub engine. Three things are weaker than stated. How likely the
trigger is has not been measured. A failure costs less than "5-15 minutes lost", because everything finished is kept.
And the advisor's suggested hint gives advice that is partly wrong.

#### 1. The evidence, piece by piece

| Claim | At 2ab1f34 | Where |
|---|---|---|
| A take's non-zero exit raises ToolError | true | `songcharter/engines/autochart.py:254-256`: `if proc.returncode != 0 or summary is None:` raises `ToolError("autochart seed {seed} failed (exit N):\n<last 8 stderr lines>")`; a timeout raises ToolError at :250-251 |
| Nothing in the guitar stage catches it | true | `songcharter/pipeline.py:797-846` has no try. `chart()`'s `except BaseException` (:706-709) only records it in pipeline.json and re-raises; the CLI turns it into exit 2 (`cli.py:353`) |
| autochart's CPU fallback covers loading only | true | `src/engine/lib/onnx/sessionLoader.cjs:227-244`: try/catch around `ort.InferenceSession.create` latches CUDA off and loads on the CPU. `runSession` (:266-268) is a bare `return session.run(inputs)`, and so is `runtime.mjs:37-39`, the one the stages import. No stage (demucsSeparate, beatDetect, transcribe, inpaint) catches a run error |
| How a `session.run` failure surfaces | an exception, then exit 1 | it rejects into `generateOnnx`'s catch (`bin/autochart-engine.cjs:1382`), which gives a result with status "failed" and finishes with code 1 (:1668-1673). The driver then fails with `engine failed (exit 1) <stage> <error>` and exits 1 (`eval/tools/autochart/ac_headless.cjs:229,283`). A native crash (a signal) takes the same path: the driver's fail() exits 1. There is no retry anywhere |
| The separation retries on the CPU after a CUDA OOM, the guitar does not | true | `separate.py:198-204`. allin1 also redoes a failed CUDA run on the CPU under "auto" (`engines/sections.py:375-383`). The guitar is the only GPU stage with no run-time fallback |

Note: the scratch copy of `ac_headless.cjs` is older than the repository's. It hard-codes `"cpu"` devices; the
repository's reads `AC_DEVICE` (`eval/tools/autochart/ac_headless.cjs:27,211`).

#### 2. The reproduction (no GPU)

Probe in /dev/shm/skeptic_rc1, now deleted:
- a stub autochart install (`SONGCHARTER_AUTOCHART`) whose `ac_headless.cjs` writes a valid take (notes.chart, a
  summary.json with matching key fields, devices) for every seed except `FAIL_SEED`;
- for that seed, it prints the real driver's log shape and ends with an onnxruntime BFC-arena "Failed to allocate
  memory for requested buffer" line (my imitation; the real text was not seen on a GPU), then exits 1;
- the tests' stand-in engines (tests/test_pipeline.py `standins(auto="cuda")`) for the other stages, injected with a
  `sitecustomize.py`, with the **real** `Engines.guitar` → `autochart.generate`;
- the friend's defaults: device auto → cuda, takes default (4, the first one alone first).

**CLI** (`python -m songcharter.cli chart "Click Song.flac" --out outA --events`, take 2 of 4 failing):
- `exit 2` in 2.4 s. Take events (1,4) and (2,4); no fallback event.
- stderr: `[6/8] guitar: autochart, 4 takes (seeds 20260609, 101, 202, 303) on cuda, the first alone first`, then
  `songcharter: error: autochart seed 101 failed (exit 1):` and the driver's last 7 lines.
- error event: `{"event": "error", "kind": "tool", "message": "autochart seed 101 failed (exit 1):\n[autochart] ...FAILED: expert: engine failed (exit 1) transcription Non-zero status code ... Failed to allocate memory ..."}`.
- pipeline.json: `error: "ToolError: autochart seed 101 failed ..."`, `fallbacks: []`, no `takes` record.

**UI job path** (`ui.jobs.Jobs(home, env=...).start(upload, {}, auto_device="cuda")`, take 3 of 4 failing):
- command `... -m songcharter.cli chart ... --events --device=auto`; state `failed`, returncode 2; takes (1,4) (2,4)
  (3,4).
- The error event reaches the page unchanged. app.js:297-300 calls `finish("It did not finish", ev.message, null)`;
  `#done-text` is a `<p>` set through textContent with no `pre-wrap` (app.css only gives that to `.error`, `pre`,
  `#install-text`). So the page shows **"It did not finish"** above one paragraph of run-together engine log:
  `autochart seed 202 failed (exit 1): [autochart] expert: engine job /…/job.json [autochart] expert 0.4s stage queued
  completed … FAILED: expert: engine failed (exit 1) transcription Non-zero status code returned while running MatMul
  node … Failed to allocate memory for requested buffer of size 268435456`. Nothing names the GPU in plain words or
  says what to try. Confirmed.

#### 3. What already softens it

- **Everything finished is kept.** Rerun with the same settings after the failure (FAIL_SEED off): exit 0. The stub
  ran only seeds 101, 202 and 303; take 1 and every earlier stage came from the cache. Each take's take.json is
  written on success, so a failure costs the failed take's partial run, not the 5-15 minutes before it.
- **"Guitar takes: 1" on the same device finishes in seconds.** After a take-2 failure, `--takes 1` with device
  auto/cuda gave exit 0 in 6.5 s with no take run (`guitar: 1 take ... (cached)`): the CUDA take 1 is reused.
- **"Device: CPU" costs more and changes more.** After a take-2 failure, `--device cpu` reran take 1 on the CPU
  (stub saw `AC_DEVICE=cpu`, transcriber cpu). `_done(..., device)` refuses the CUDA take. allin1's cache key holds
  the device and the model (harmonix-all on cuda, fold0 on the CPU), so the sections would rerun on the CPU too, with
  a different model. The stems (separate's key has no device) and the drums would be reused.
- **The guide** has "Don't run games then" (docs/guide/windows-wsl.md:60) and the Diagnostics link (:74). Nothing
  covers a failed GPU run. PROGRESS's deferred list does not have this gap; M4-08 only asks to record "whether any
  take fell back to the CPU".
- **The likelihood is unmeasured.** 8,987 MiB is nvidia-smi's whole-GPU `memory.used` (device.py:125) on the owner's
  5070. That includes the owner's desktop and songcharter's own torch context, so the engine's own need is lower by
  an unknown baseline. The friend has about 9.5 GB free at idle. Takes 2-4 run only the transcription (autochart's
  Demucs and beat map come from its engine cache), so if the peak was take 1's Demucs, a failure "in take 2"
  needs something else to take VRAM mid-run: a browser, a game, Clone Hero. That is plausible on his PC but not
  shown. Not verified either way: whether the Windows driver's sysmem fallback applies under WSL2, and whether
  onnxruntime's arena backs off and recovers. A failure in take 1 has the same outcome.

#### 4. The fixes

**(a) The hint.** This is cheap and safe. Put it in pipeline.py's guitar stage, not autochart.py:
ENGINE_FILES["guitar"] is only `songcharter/engines/autochart.py` (eval/golden.py:98), so a pipeline.py change does
not mark the golden charts as changed. Fix the wording first. "Device: CPU and Guitar takes: 1" together throws away
the finished GPU take and redoes the guitar and the sections on the CPU. Better: *"The guitar's GPU run failed in take
k of n; the takes that finished are kept. Close programs that use the GPU (games, Clone Hero, video) and chart it
again, or set Guitar takes to 1 (it uses the first take if it finished: seconds). If it fails again, set Device to
CPU."* Keep the engine's lines below it. Also give `#done-text` `white-space: pre-wrap`, so the hint and the log
stay apart. Test it with `standins(bug="guitar", error=ToolError(...))` and device cuda.

**(b) A CPU retry.** This is feasible: `autochart.generate(device="cpu")` is per call and sets `AC_DEVICE=cpu`,
`AUTOCHART_ONNX_TRANSCRIBER_DEVICE=cpu` and no CUDA LD_LIBRARY_PATH (stub saw all three). pipeline.py would run the
remaining seeds one call at a time and catch ToolError on cuda. Finished takes are cache hits, so per-seed calls
cost nothing. It would then rerun the failed seed with `engines.guitar(..., [seed], "cpu")`.
- **Time:** one CPU take after the first is about 217 s for the 6:52 song on the dev container
  (pipeline.py:234). A 5070 take was about 177-217 s, so retrying one take costs about one more take (the friend's
  CPU is not measured). Retrying all remaining takes on the CPU costs up to about 3 × 3.6 min.
- **Record:** a `fallback` entry {stage guitar, from cuda, to cpu, reason "take seed_N: the CUDA run failed (<first
  line>); run on the CPU"} with a warning (the page's banner), and per-take devices in `record["takes"]`. The next
  CUDA run would not reuse the CPU take (the existing rule in `_done`).
- **Golden:** no golden impact if it stays in pipeline.py. The golden runs on the CPU and never takes this path.
- **Risks:** a broad catch would also retry timeouts and non-CUDA failures. And it would put a CPU node engine,
  beside the parent's CUDA context, inside the friend's 12 GB WSL. That path is untested there, and M4-08 noted
  autochart's engine killed at 12.8 GB once.

**For v0.1, I would build (a) only**, with the corrected wording and the pre-wrap. It turns a dead end into a
seconds-long recovery, needs no GPU to test, and changes no charting code. Do (b) in v0.1.1, once M4-08 has
measured the friend's free VRAM and per-take peaks. My severity: medium (a UX dead end on a plausible but unmeasured
failure), not a blocker. It is worth the small change before the friend.

### Skeptic on the advisor's #6 (the page never shows doctor's problems), main at 2ab1f34

**Verdict: partly confirmed.** The core claim holds, and is slightly worse than stated: the page never shows
doctor's problems, and `ok: false` changes nothing on it. Even with the advisor's fix, a running server would not
notice the disk filling, because the refresh is cached for each version of doctor.json. The supporting story is
overstated and partly wrong. uploads/ *is* pruned. exports/ holds one zip per song name, overwritten. The folders that
are never pruned grow by about 6-9 MB a song, which does not plausibly fill a disk. What fills C: is the work cache
(pruned, but about 100 times bigger per song) and the WSL disk image it grows. Severity: minor. It is cheap to fix and
worth doing before v0.1.

#### 1. Each piece at 2ab1f34

| Claim | At 2ab1f34 | Evidence |
|---|---|---|
| status() returns device, gpu, guitar_device, guitar_reason, notes, ok, source, error, and no `problems` | **true** | songcharter/ui/server.py:259-268 (keys at 263-264) |
| renderStatus renders `notes` only | **true**: machine, guitar, and notes in a collapsed `<details>` | songcharter/ui/static/app.js:55-74; index.html:12-20 |
| nothing in the page mentions problems | **true**: the served app.js has no `problems` and never reads `st.ok`; `#chart.disabled` is set only while its POST runs (app.js:190/204) | grep over the served files |
| doctor's problems: ffmpeg, scan-chart or autochart missing, under 6 GB free in WSL or on C:, WSL under 8 GB | **true** | songcharter/device.py:514-534 (problems), 536-568 (notes) |
| App.doctor and device.refresh re-measure the disk | **true, but only once per doctor.json version**, so once for each server process in practice | server.py:241-249 (`_fresh` keyed on mtime and size); device.py:616-642 |
| cache.py prunes work/ to 5 GB | **true**, with exceptions: work folders used in the last 24 h are never pruned (RECENT_S), nor --work folders; ac/ scratch counts toward the budget | cache.py:36-48, 72-73, 253-255 |
| library/, exports/, replaced/, uploads/ never pruned | **3 of 4.** uploads/ is pruned: anything older than 7 days goes when the server starts (server.py:297-317, 984-986; specified in M4-04 line 111). library/, exports/ and replaced/ are never pruned. | |
| a full disk shows up only as an exit-2 OSError on the Done screen | **mostly true** (see section 3) | cli.py:353-355; ui/jobs.py:370-397 |

Is it intended? M4-04's spec asks for exactly what was built: status has "device, gpu, guitar device and reason,
notes, ok" (M4-04-ui-server.md:103-104), and the header shows "the doctor's notes under 'Details'" (140-143). So this
is a gap in the spec, not a coding slip. Nothing documents leaving problems out on purpose, so it stands as a real
gap.

Context the finding leaves out: the chart already checks two of the component problems before any audio work.
ffmpeg and autochart missing name their fix (pipeline.py:350-367). A missing scan-chart falls back to the stand-in
with a warning from the gate (assemble.py:55). So the problems only doctor would report are low disk and low WSL
memory. The installer does print the problems once, at install time (packaging/linux/install.sh:371-377).

#### 2. Reproduction (through the real server)

`/dev/shm/skeptic_rc6/probe.py`, run from the repository root with the dev Python. It writes a doctor.json from
install time (RTX 4070, 50 GB free in WSL, 90 GB free on C:, components ok, problems []) and starts `S.App` +
`S.bind(app, [0])` with a stand-in jobs command, as tests/test_ui_server.py does. It patches `device._free_mb`, which
is what `device.refresh` calls to measure the disk, then makes GET /api/status, /app.js and / over HTTP. Output:

```
[plenty] GET /api/status -> 200
  keys: ['device', 'error', 'gpu', 'guitar_device', 'guitar_reason', 'job', 'notes', 'ok', 'source']
  ok: True   'problems' in answer: False
[low_disk] GET /api/status -> 200      (free disk 3000 MB, refresh cache cleared = a server started after C: filled)
  keys: ['device', 'error', 'gpu', 'guitar_device', 'guitar_reason', 'job', 'notes', 'ok', 'source']
  ok: False  'problems' in answer: False
  device.refresh's own problems for this: ['only 2.9 GB free in WSL (/root): a chart needs 6 GB',
                                           "only 2.9 GB free on C:, where WSL's disk grows: a chart needs 6 GB"]
```

The served app.js's own `renderStatus` was then run in Node (vm context with a stub DOM,
`/dev/shm/skeptic_rc6/render.cjs`) on both answers. The output is the same for both:

```
status_plenty.json (ok=true):   #machine "GPU: NVIDIA GeForce RTX 4070 (12 GB)"  #guitar "guitar on the GPU"
                                #notes [the one note]   touched: details, guitar, machine, notes
status_low_disk.json (ok=false): the same, character for character
```

`ok: false` alone changes nothing: no banner, no disabled button, and no element is touched that was not touched
before.

**Staleness** (`/dev/shm/skeptic_rc6/stale.py`): one server, 50 GB free, then 2 GB free without restarting. Output:
`server start, 50 GB free: ok = True` / `same server, disk now 2 GB free (a page reload): ok = True`. The refresh is
computed once per doctor.json version (server.py:243-249), and the server stays up across every chart of a session.
So the advisor's "return problems" alone would show the disk as it was when the server started, not as C: fills
during the session.

**What the friend sees at a full disk** (upload probed, chart path from the code):
- An upload when the disk is full (server.py's `open` for the .part file patched to raise ENOSPC):
  `POST /api/upload -> 500 {"error": "internal error: OSError: [Errno 28] No space left on device"}`. The drop
  screen shows that text (app.js:105-106). The server logs it as a bug with a traceback (server.py:426-431).
- During a chart, an OSError in the pipeline gives exit 2 with `[Errno 28] No space left on device: '<path>'`
  (cli.py:353-355). The job becomes `failed` and the Done screen shows "It did not finish" and that message.
  Inside ffmpeg or torch the error may surface differently (a ToolError, or exit 3 "bug"). Not reproduced: no real
  chart was run.

#### 3. The growth that is never pruned, per charted song

A real built folder on this machine (a 6:55 song): notes.chart 106 KB, report.json 23 KB, song.ini 228 B, song.ogg
9.2 MB (Vorbis q7, 177 kb/s, so about 1.3 MB a minute). In all **9.3 MB, about 5-6 MB for a 4-minute song.**

| Folder | What stays | Size | Bound |
|---|---|---|---|
| library/<id>/<artist - title>/ | the built song folder (plus `.failed` beside it when the gate failed) | about 1.3 MB/min of audio | one per upload and title; charting the same file and title again rebuilds in place |
| exports/<name>.zip | a zip of that folder (Vorbis does not compress further) | about the same | **one per song name, overwritten** (clonehero.py:386-390) |
| replaced/<stamp>/<name>/ | the older chart, each time an install replaces one | about the same, per replace | grows with each replace |
| uploads/<id>/ | the original file (MP3 5-10 MB, WAV or FLAC 30-60 MB) | the source's size | **pruned after 7 days at server start** |
| work/ + ac/ (pruned) | decode.wav (59-139 MB), 6 stems, engines, takes | **0.7-1.2 GB a song** (DESIGN.md:1910, 1915) | 5 GB, but nothing used in the last 24 h goes |

Normal use, say 100 songs over some months, each exported once and replaced once: about 1.5-2.5 GB in the unpruned
folders. That is not plausible as what fills a gaming PC's C:. What does fill it is the work cache. One evening of
10 songs is about 7-12 GB in work/ and ac/, none of it prunable until 24 h later. On top of that, WSL's ext4.vhdx
grows to hold it and does not shrink by itself when files are deleted inside it [doc: Microsoft's WSL disk-space
page; not verified here]. So C:'s free space follows the peak of the cache plus the install, not the library. That
makes the doctor problem "only N GB free on C:" exactly the warning that matters, and it is the one the page hides
(and measures only once per server).

#### 4. The fix

The advisor's ten lines are right in direction but not enough alone, because of the staleness. What I would build
for v0.1, about 20 lines plus a test:

1. **server.py `status()`**: add `"problems"` to the key tuple. In `App.doctor`, re-measure the disk on every call:
   `shutil.disk_usage` is microseconds, and `device.findings` is pure. Keep the full `device.refresh`, whose
   `wsl.wslconfig()` goes through cmd.exe, cached per doctor.json version as now. For example, a
   `device.refresh_disk(r)` that replaces `disk` and recomputes problems, notes and ok, applied on top of `_fresh[1]`.
2. **index.html / app.js**: `<ul id="problems" class="error" hidden>` in the header above Details, and in
   renderStatus `problems.replaceChildren(...(st.problems||[]).map(p => make("li", null, p)))`, hidden when empty.
   Don't disable "Chart it" on `ok: false`. A memory or disk problem is a warning, and a short song may still fit.
3. **server.py `_upload`**: catch `OSError` with `errno.ENOSPC`, then `Refused(507, "the disk is full: free space on
   C: (songcharter's work cache is in ~/.cache/songcharter/work) and try again")`. That replaces a 500 logged as a
   bug.
4. A test in tests/test_ui_server.py: doctor.json with plenty of disk, `_free_mb` patched low, `/api/status` has the
   two problems and `ok: false`, on the same App with no restart.

**Not for v0.1:** pruning library/, exports/ or replaced/ (they are the friend's charts, and small), and a size in the
header. Record in PROGRESS's deferred list: the 24-hour exemption lets work/ go well past 5 GB in a busy session, and
a "songcharter uses N GB (cache M GB)" line or a "free the cache" button could come later. The uninstaller already
reports these sizes (launch.py:194-200).

#### Probes

`/dev/shm/skeptic_rc6/{probe.py, render.cjs, stale.py}`. All were deleted after the run. No suite, golden run,
install or real chart was run, and the repository was not edited.

### Skeptic: the advisor's #7 (the install's closing "doctor: 1 problem" before the WSL restart)

Verdict: **partly confirmed. It is real, but only a note.** The mechanism reproduces: a step-8 doctor.json with the
memory problem gives the closing summary "problem: WSL has 7.4 GB ..." and "doctor: 1 problem", and install.sh's
code is 1, even though step 9 has just written memory=12GB and the restart comes next. Three details of the finding
do not hold:
(a) the exit comes *after* `wsl.exe --shutdown`, not before it, and the friend never sees it;
(b) the advisor's 15.4 GiB PC is most likely just over the line, so it is not a coin toss. The problem is certain
    only on PCs that report about 15.2 GiB or less;
(c) the problem line names the cure that the install's last line then carries out.
Nothing after step 8 is skipped or changed. Fixing it is not needed for v0.1.

#### 1. The order at the end of install.sh (main at 2ab1f34)

- install.sh:343-351, step 8: `helper ... runtime setup` returns 0 or 1. `code=$helper_code` is kept. A 1 stops the
  install only when doctor.json is not this run's (its mtime).
- install.sh:353-361, step 9: wslsetup apply writes .wslconfig and the shortcut, and touches `$flag` when .wslconfig
  changed (wslsetup.py:302-304).
- install.sh:363-370, step 10: the launcher and install.done.
- install.sh:371-378: the summary. It is `device.summary` of doctor.json **as step 8 wrote it**, then "doctor: OK" or
  "doctor: N problem(s)".
- install.sh:381-388: "is installed", the lane warning and "Start it from the Start menu".
- install.sh:389-394: when the flag is set, "WSL restarts now so the new memory setting takes effect. Then start
  songcharter from the Start menu.", then `sleep 5`, then `win_cmd /c wsl.exe --shutdown`. install.sh itself runs the
  restart.
- install.sh:395-396: `exit "$code"`, after the shutdown. On a real PC the VM is gone by then. The guide's line
  (`... && bash install.sh`, guide:35) prints no exit code anyway.
- A code of 1 skips or changes nothing: the shortcut, the launcher, install.done and the restart all happen. The
  probe below shows this, and tests/test_install.py:492-504 covers the problems-only path.
- There is no "install.sh: OK" line at the end. That line is sha256sum's check *before* the install runs (guide:38).
- The guide never says what to do with an install that ends with a problem. Its only line on the ending is guide:49:
  "At the end, it sets how much memory WSL may use and restarts WSL, and the window closes."
- After the restart, the page's header does not use the stale file. It uses `device.refresh` (ui/server.py:230-248,
  device.py:616-642).

#### 2. The memory arithmetic

- **Measured, from WSL's source** (microsoft/WSL master, src/windows/common/WslCoreConfig.cpp:308-317, fetched here):
  `GlobalMemoryStatusEx`, `MaximumMemorySizeBytes = memInfo.ullTotalPhys; if (MemorySizeBytes == 0) MemorySizeBytes =
  MaximumMemorySizeBytes / 2;`. So the VM gets half of the *reported* (usable) RAM, not the installed RAM. The default
  swap is a quarter of that, rounded up to a whole GB. A 64 MiB swiotlb is added only with virtio devices
  (helpers.cpp:812-824).
- **Reasoned:** Win32_ComputerSystem.TotalPhysicalMemory (wsl.py:306-320) reports the same usable figure as
  ullTotalPhys. Not checked here: no Windows.
- **Measured on this container's VM (not WSL):** MemTotal 16,477,348 kB against 16,776,831 kB of e820-usable RAM is
  98.21%, so 1.79% goes to the kernel. Most of that is the struct-page array, 64 B per 4 KiB = 1.5625% at any size.
- **Reasoned for WSL's kernel:** the overhead is 1.8-2.2%, or about 3.0% if the kernel's own 64 MiB swiotlb is
  allocated. No WSL here to measure.

| Windows reports | VM (half) | MemTotal at 1.8% / 2.2% / 3.0% | overhead needed to go under 8e9 |
|---|---|---|---|
| 15.4 GiB | 8.268e9 | 8.119 / 8.086 / 8.020 e9 | 3.24% |
| 15.9 GiB | 8.536e9 | 8.383 / 8.348 / 8.280 e9 | 6.28% |
| 16.0 GiB | 8.590e9 | 8.435 / 8.401 / 8.332 e9 | 6.87% |

- 15.9 and 16.0 GiB are safely over. 15.4 GiB is over by 20-120 MB: a thin margin, but not a coin toss (the advisor's
  8.02e9 assumes the high 3% overhead).
- MemTotal goes under 8e9 when Windows reports under 15.17 GiB at 1.8% overhead, 15.24 at 2.2%, or 15.36 at 3.0%.
- So a 16 GB PC with about 1 GB of integrated-graphics memory reserved (reporting 15.0-15.2 GiB) hits it for sure.
- The friend's RAM is "16-32 GB" (PROGRESS.json:6), with an RTX 4070 desktop card. At 32 GB nothing happens. At 16 GB
  it depends on whether an integrated GPU reserves memory. Unknown.
- **Other doctor problems true only before the restart: none.** findings() has problems only for components, free
  disk and WSL's memory (device.py:519-534).
- The *notes* are stale on every PC, including on the winning side:
  - "allin1 is left out" (device.py:552-554);
  - the summary's "no .wslconfig", printed just after step 9's ".wslconfig: wrote memory=12GB".
  These are the already-deferred stale-summary item (release-gate.md:211-219 and 257, PROGRESS.json:147).

#### 3. Reproduction

The probe is under /dev/shm/skeptic_rc7/probe (now deleted). It does the following:
- the filled install.sh, built with tests/test_install.py's `Install(wsl=True)` and its stand-ins (curl, uv, cmd.exe);
- the environment's python stand-in sends the summary's heredoc to the real `songcharter.device`;
- `runtime setup` writes runtime.json and a doctor.json whose problems and notes come from the real
  `device.findings`: WSL, interop, no .wslconfig, Windows RAM 15.4 GiB, RTX 4070, cu132, and MemTotal $MEMTOTAL_MB;
- `wslsetup apply` is the real `wslsetup.main`, with `windows_side` pointed at temporary folders;
- `bash install.sh --from dist --lane cu132 --yes --windows-ram-gb 15.4`.

Losing side (`probe.py runA 7618 15.4`; 7618 MB = 7,988,051,968 bytes):

```
== [8/10] Node, scan-chart, autochart and the models
doctor: 1 problem (in .../doctor.json)
== [9/10] The Windows side: WSL's memory and the Start-menu shortcut
.wslconfig: wrote memory=12GB and swap=8GB in C:\Users\player\.wslconfig (Windows has 16 GB of RAM)
Start menu: songcharter (.../songcharter.lnk)
== [10/10] The launcher
...
WSL: Ubuntu-26.04 on Windows 10.0.26200.7000, interop on; Windows RAM 15.4 GB; no .wslconfig
RAM: 7.4 GB, 6.6 GB available; swap 0.0 of 3.8 GB used
...
problem: WSL has 7.4 GB of memory, under 8 GB: set memory in %UserProfile%\.wslconfig (the install writes it), then restart WSL (wsl --shutdown)
note: WSL has 7.4 GB of memory, under 11 GB: allin1 is left out to save memory (the sections use the librosa fallback)
doctor: 1 problem

songcharter 0.0.0-test is installed (lane cu132: asked for with --lane cu132).
Start it from the Start menu (songcharter), or type songcharter in Ubuntu.
WSL restarts now so the new memory setting takes effect. Then start songcharter from the Start menu.
--- exit code: 1
--- cmd.log (last): '/d /c wsl.exe --shutdown'     (called before the exit)
--- .wslconfig: [wsl2] memory=12GB swap=8GB; shortcut written; launcher and install.done there
```

- Winning side (`runB 7660 15.4`, 8.03e9 bytes): "doctor: OK", exit 0. The same stale "no .wslconfig" and allin1
  note remain.
- After the restart (`device.refresh` on runA's doctor.json, with MemTotal 11.66 GiB and .wslconfig at 12GB): ok True,
  no problems, no notes, memory in force. The page is clean.

Not checked here:
- whether the Ubuntu window really closes on `wsl --shutdown`, or (in Windows Terminal) stays open on
  "[process exited with code ...]". That code would be wsl.exe's, not install.sh's;
- WSL's real MemTotal for a given memory size.

#### 4. Judgement and fix

- **A note, not a v0.1 fix.**
  - What the friend reads is self-consistent. The problem says "set memory in .wslconfig (the install writes it),
    then restart WSL". Five lines up, step 9 says it wrote memory=12GB. The last line says WSL restarts now for the new
    memory, then to start songcharter from the Start menu.
  - The exit code is never seen.
  - Nothing is skipped.
  - The page after the restart re-measures and shows no problem.
  - On the likely PCs (15.9-16.0 GiB reported), and on the advisor's 15.4 GiB PC at plausible overheads, the problem
    does not appear at all.
  - The worst case is a worried message to the owner. That is the same class as the stale notes the release gate
    already deferred.
- **If it is fixed later, the smallest fix:** in install.sh:371-378, when `$flag` exists, have the heredoc drop the
  WSL-memory problem and the two memory notes from what it prints. Then end with "WSL's memory is measured again
  after the restart", and set `code` from the problems that remain (the heredoc exits 1 or 0).
- **What it must not hide:**
  - disk and component problems;
  - the memory problem when no restart follows: .wslconfig kept, the person answered No, or a rerun after an
    interrupted restart, where "kept" sets no flag and the problem is the true next step;
  - plain Linux and CI, which have no flag and are unchanged.

