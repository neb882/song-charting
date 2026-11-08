# M8-01: GPU takes of every measured song, on the owner's installed app (builder's report)

Branch `m8-01-gpu-takes`, worktree `<wt>/m8-01`, from main at b319819. Not merged. Files touched: `eval/takes.py`,
`eval/gpu.sh`, `eval/README.md`, `tests/test_eval_takes.py` (new). No other order's file; docs (PROGRESS, DESIGN)
left to the orchestrator.

The scope grew mid-build (the orchestrator's message, from the owner's PC): his Ubuntu was reinstalled, so he has a
release clone and the installed app (v0.3.1, cu132) but no eval/tools or eval/data. Takes must run on the app's
runtime, the inputs be built there, and eval/README.md carry "GPU takes with the installed app". All of it is in.

## Commits (head b57392d, pushed)

- 718b03e eval/takes.py: takes of the stress and 20-song sets, by label, on the installed app
- fa59e93 eval/gpu.sh: takes [SET ...] and build on the installed app; the zip by label, checked for audio
- e2cac3a tests: eval/takes.py and eval/gpu.sh's takes, build and results on made-up sets
- 1cc329c eval/README.md: GPU takes with the installed app, for every measured song
- b57392d Merge main into m8-01-gpu-takes (M7-02 and M7-06: songcharter/ and docs, none of this order's files)

## What changed

### eval/takes.py
- `--set refs|stress|set20` (default refs, unchanged: `refs/songs.json` plus the test song, takes in
  `runs/takes/<id>/seed_<seed>/`, the same log lines).
- stress: ids from `eval/stress.json`, inputs `$EVAL_DATA/stress/<id>/input.wav`, takes in
  `runs/takes/stress/<id>/seed_<seed>/`.
- set20: a data folder of its own, `SET20_DATA` (default `$EVAL_DATA/set20`), as the 20-song set is built (its
  `set20.json`, the STRESS_JSON of its build, and `stress/<id>/input.wav`); takes in `runs/takes/set20/<id>/...`.
  On the dev machine that folder is `$DEV/eval-set20`.
- Labels: refs and stress by id; set20 as sNN in the order of the sorted ids. Checked on the dev machine without
  printing an id: sorted ids give exactly set20-v03.md's slot and chart-count columns for s01-s13. Every printed and
  logged line goes through a whole-word id-to-label scrub (an error message naming a path included).
  `runs/takes/<set>/labels.json` (label -> id) stays on the PC; `set.json` (label, slot, charts, length; no id) goes
  in the zip so the labels can be checked against the dev machine's set.
- Missing input.wav: one line per song, skipped. Exit 0 / 1 (a take failed, the rest still made) / 2 (the set
  unreadable, no song found, the engine not ready). A list id that is not `[a-z][a-z0-9_]*` or appears twice is
  refused, never named.
- `--app`: the installed songcharter's autochart and Node from its `runtime.json` (songcharter.launch's home_dir and
  load_runtime), with the launcher's environment put into the process (FFMPEG, Node first on PATH, HF home), so
  generate(..., device="cuda") runs the app's CUDA autochart with the CUDA 13 and cuDNN wheels of the Python running
  it (the app's, run by gpu.sh). songcharter is imported from the clone (first on sys.path); `git diff v0.3.1 HEAD`
  of engines/autochart.py, eval/tools/autochart/, launch.py, audio.py, errors.py, importers.py, cache.py, uv.lock,
  pyproject.toml and packaging/autochart/ is empty, so the clone's wrapper is the app's. In app mode the log gets one
  line `app: songcharter <v>, the <lane> lane` (no path).
- `--check` (the engine for `--device`; with `--app` also the lane: cu132 needed, as cu126 cannot load the provider),
  `--dry-run` (the songs found by label and how many takes have a take.json; writes nothing), `--scrub` (stdin to
  stdout, the set's ids as labels and every 32-hex md5 as `<md5>`).

### eval/gpu.sh
- `takes [SET ...]`: validates the sets, checks, lists each set's songs (takes.py --dry-run, labels only; a set with
  none stops it), then one detached run of takes.py per set in turn, then `results`. Samples the GPU into
  gpu_samples.csv during takes.
- `--app` (or SONGCHARTER_APP=1) for check, takes and build: `app_env` reads runtime.json with the app's Python and
  sets EVAL_PY (unless set), Node first on PATH, SONGCHARTER_SCAN_CHART, and `ffmpeg` (the system's if on PATH, else
  the app's imageio-ffmpeg linked as `$DATA/bin/ffmpeg`). The app check is GPU, `takes.py --app --check --device
  cuda`, memory, and the refs set only when refs is asked for. `start --app` is refused (drive.sh needs the eval tools).
  In app mode `_takes` does not set the old cuda_libs LD_LIBRARY_PATH.
- `build SET [TEST_SONG]`: build_refs.sh for refs (with the test song), stress, or set20 (EVAL_DATA, STRESS_JSON,
  STRESS_LOCAL set to SET20_DATA's); the stress and set20 output piped through takes.py --scrub.
- `results`: the refs' patterns as before plus take.json; stress and set20 take folders zipped under their labels
  from labels.json (a song folder it does not name is left out and counted); in every zipped file each 20-song id is
  replaced by its label (whole word), $HOME by `~`, the Windows profile (and its JSON-escaped and /mnt/c forms) by
  `%USERPROFILE%`; a guard re-reads the zip and refuses it if an id is left; then check_no_audio.py on the zip, which
  must pass or no zip is made; an old zip is removed first, so a failure leaves none. The "copied to" line no longer
  prints the Windows profile path.

### eval/README.md
- "GPU takes with the installed app": what it needs (the app on cu132, nvidia-smi, a clone, python3, curl; nothing
  installed), why the clone's code is the app's, why the inputs are on the dev machine's clock, how packages are
  found (`sng/<md5>.sng`, else downloaded from files.enchor.us), the 20-song set's folder and its two lists, the exact
  steps (placeholders for his paths), build sizes, GPU time, what the zip holds.

## The inputs on his PC (the orchestrator's question 2)

- **Script:** `eval/build_refs.sh` (through `eval/gpu.sh build --app SET`). It needs Python with numpy, soundfile and
  librosa (sng_unpack, build_ref, offset_check; strip_lyrics and make_songs_json are stdlib; mido is not imported by
  any build helper), `ffmpeg` and `node` by name on PATH, scan-chart (SONGCHARTER_SCAN_CHART), curl for a missing
  package.
- **The app's runtime has all of it:** its env has numpy, soundfile, librosa (the bass/sections/preview extras),
  imageio-ffmpeg; its runtime has Node 24.19.0 and scan-chart. So build_refs.sh runs with the app's Python as EVAL_PY
  and nothing to install. Proven here with this machine's .venv standing in for the app env (it is a superset: the
  dev extra adds mido and pytest) in `test_build_app_set20_builds_on_the_apps_tools_and_prints_labels_only`: a made-up
  package built through a fake app's runtime.json, its logging python and node wrappers both used.
- **The clock:** golden charts each song's `input.wav` (eval/golden.py), which build_ref.py makes by summing the
  primary package's stems; the dev machine used Ubuntu's ffmpeg 6.1.1, the app ships imageio-ffmpeg 9.0.2. On made-up
  Vorbis, Opus and MP3 stems (12 s, stereo, 44.1 kHz), the two decode to identical float samples and identical PCM16,
  same lengths [one check, this machine]. Each zipped take.json carries the input's SHA-256, so the orchestrator can
  compare with sha256 of the dev machine's input.wav per label.

## Checks

- **New tests** `tests/test_eval_takes.py`, 22 tests: through `tools/heavy.sh`, `22 passed in 3.83s`; after the
  merge with the engine and privacy tests, `51 passed in 4.75s`.
- **eval's own tests** (`test_eval_takes, test_eval_stress, test_golden, test_privacy_check, test_engines_autochart,
  test_takes`) through heavy.sh: `149 passed in 47.99s`.
- **Full suite** on 1cc329c through heavy.sh (`SONGCHARTER_HEAVY_MIN_FREE_GB=1`, 2 GB free on /): `1170 passed, 6
  skipped in 752.90s (0:12:32)`.
- **CI** on the merged head b57392d: <repo>/actions/runs/42500995335, success
  (linux and windows). The suite there: `1178 passed, 4 skipped in 599.35s`, which with the 4 skips (allin1,
  LnkParse3 x3; none of this order's) is the 1182 tests collected on the merged tree, so all 22 new tests ran. The
  earlier run 42499851587 (on 1cc329c) was cancelled by the second dispatch on the same branch. No CI hook added
  (the brief allowed only these four files); the tests run in CI's suite.
- **Tests of the tests:** 27 breaks, each applied to the worktree's code, the test file run, the file restored.
  25 caught at once. "App's Node not on PATH" was missed (the system node hid it): the build test now gives the fake
  app a logging node wrapper and asserts scan-chart ran through it; caught on the rerun. "Zip paths without labels"
  alone is not caught, since every member name is scrubbed too; with the name scrub also removed, the guard refuses
  the zip ("15 files still hold an id that is not a label: no zip made") and the test fails. Breaking only the guard
  is not caught either (the scrub upstream makes it redundant).
- **Dry run on the real sets** (EVAL_DATA=$DEV/eval, SET20_DATA=$DEV/eval-set20, `takes.py --dry-run`, every output
  through a filter that masks any 20-song id or md5, case-insensitive, anywhere in a word): refs 7 songs found (6 and
  the test song), stress 4, set20 13 (s01-s13), 0 without input.wav; 28, 16, 52 takes. The filter's only hits were
  inside "DONE" (it matches inside words; the scripts' scrub is whole-word and case-sensitive).
- **Faked engine on the real sets** (scratch EVAL_DATA linking the real refs/ and stress/, a stand-in generate that
  reads no audio, writes the driver's files with the input's absolute path in summary.json, and fails seed 303 with
  the input path in its message), then `gpu.sh results`: 102 log lines, every set20 line by label, FAILED lines' paths
  with the label; zip 291 members (refs 7x3, stress 4x3, set20 13x3 takes of 4 files, two set.json, takes.log),
  `check_no_audio: ok`, no song.ogg, no labels.json, 0 whole-word ids in names and contents; with HOME set to the
  data's parent, 0 home paths left (`~/.../stress/s01/input.wav`).
- **Collision check:** all 13 20-song ids are one word (shortest 3 letters); 0 whole-word occurrences, in any case,
  in 92 real engine files (notes.chart, song.ini, take.json, autochart_run/*.json) of the golden and stress kept
  folders, so the zip's scrub changes nothing in engine output.
- **ffmpeg check:** made-up 12 s stereo stems as Vorbis, Opus and MP3; decoded with ffmpeg 6.1.1 and imageio's 9.0.2:
  identical samples, identical lengths (529200), identical PCM16.
- **Privacy:** `EVAL_DATA=$DEV/eval python3 -I eval/privacy_check.py` on the four files: 0 found. With
  `EVAL_DATA=$DEV/eval-set20`: 15 hits, every one the common word the brief names as the known false positive, all on lines main
  already has in gpu.sh and README.md; the test file's two were renamed away. Diff and commit messages scanned: no
  lyric, audio, model name (the one "Opus" is the codec), personal detail, home path or repository owner; commit
  messages carry only the trailers.
- `df -h /`: 1.9G free (96 %). <shm>/m8-01 cut to 1.6 MB (logs, the faked data, the scratch scripts).

## Not done, or uncertain

- **No app here:** app mode is tested against a made-up runtime.json and install; the first real check is his
  `eval/gpu.sh check --app`. Nothing ran on a GPU; no engine ran at all.
- **His packages' names:** build_refs.sh finds a package only as `sng/<md5>.sng`, else downloads it from
  files.enchor.us. Whether his own files are named by md5 is unknown (the README says to copy them in under those
  names, or let the script download).
- **The 20-song set's two lists** (set20.json, stress.local.json) must reach his PC (`eval/data/set20/`); they hold
  titles and md5s and cannot be committed. Labels follow the sorted ids of his set20.json: if his list differs from
  the dev machine's 13, the sNN shift. The zip's `takes/set20/set.json` (slot, charts, length per label) lets the
  orchestrator check before using them, and each take.json's inputSha256 can be compared with the dev input.wav.
- **GPU time** in the README is derived from the owner's figures in the brief (1 to 4 GPU minutes a minute of audio),
  not measured. The engine's work folders' disk use per song is unmeasured.
- **A 20-song id that is a common word** would also be replaced in a zipped log line (harmless, labels only). Engine
  output had no such word (above).
- **privacy_check.py prints a hit's song id**: for the 20-song set that is an id that spells a title (it printed one
  to this session's terminal on that false positive; not saved anywhere). The orchestrator may want it to
  print a label instead for that set.
- **Docs:** PROGRESS.json, DESIGN.md and the work orders not touched (the brief's file list); eval/REPORT.md still
  describes `gpu.sh results` in one line.

## Review fixes (the review of b57392d: R1 major, R2-R4 minor)

Commits on top of b57392d: the fix commit (structured zip, independent guard, WINDOWS_PROFILE, `~`,
the tests), a merge of main (M7-09, M7-10, the 0.4.0 version bump; none of this order's files), and a README line
restating the engine path against v0.3.1 on 0.4.0's code (engines/autochart.py, the driver and the launcher
unchanged; uv.lock and pyproject.toml differ only in the version). CI on 1889360 (run 42506400693) failed 6 tests: on the runner the temp folders are under $HOME, so `shown()` wrote them `~` and 6 in-process asserts expected the raw path; fixed in 7000dfe (the asserts expect `T.shown(...)`; `--scrub` now writes the home folder `~` too, as R4 asks), and the file passes with HOME=/root and with HOME above the temp folder (36 and 36).

- **R1 (tests):** `gpu.sh check --app` and `gpu.sh takes --app` now run in tests, on a made-up PC: HOME, the app
  where install.sh puts it (its Python this one, with a made-up `nvidia` wheel folder on PYTHONPATH holding
  cu13/lib and/or cudnn/lib), a stand-in nvidia-smi. check: ready app exits 0; cu126 lane, cuDNN without CUDA 13,
  the reference set not built: each exits 1 with its problem. takes: cu126, refs not built, a set listed but with
  no input.wav: each refuses, exit 1, and nothing detaches (no runs/ folder). The in-process check also gained the
  cuDNN-only case.
- **R2 (privacy):** the zip carries structured files only: each take's notes.chart and song.ini as the engine wrote
  them; take.json and autochart_run/summary.json copied field by field (numbers, 64-hex hashes, short names of
  `[A-Za-z0-9_.+ -]{1,40}`: no path, no message; the summary's `input`, `ffmpeg`, `jobDir`, `error` and the other
  autochart_run JSONs are gone; M7's scripts read only `inputSha256`, kept); set.json; and `takes/takes.jsonl`, a
  record takes.py writes per take, run start, missing song and run end (a failure as its exception's type only).
  No log: takes.log (with each failure's message) and gpu_run.log stay on the PC; drive.sh's logs are out too, its
  scores and test-song charts kept. The guard is separate from the scrub: it reads the finished zip back, lowercases
  each member's name and text, and stops the zip on a 20-song id as a whole word, an md5 (primary or alt) of the
  stress or 20-song local list, or the home folder or any form of the Windows profile; it names the member by its
  label path with ids masked. Tested with the made-up common-word id `run` (no "run" as a word anywhere in a normal
  zip, "runs" and "autochart_run" not matching; a "Run" planted in a chart stops it), a planted md5, the home
  folder in upper case (which the case-sensitive scrub misses).
- **R3:** `WINDOWS_PROFILE` overrides the profile (else cmd.exe's); without wslpath its /mnt/c form is computed.
  Tested: `C:\Users\Made Up\...`, its JSON-escaped form and `/mnt/c/Users/Made Up/...` become `%USERPROFILE%`; a
  lower-case form stops the zip at the guard.
- **R4:** takes.py prints every path through `shown()` (home as `~`): the check's lines (app home, autochart, node,
  `sys.executable`), the refusals, the log lines. gpu.sh's `tilde` covers app_env's refusal, the setup hints, the
  CUDA library line, the tail hints, `status`'s log tails, the "did not start" tails, the zip's line, and
  check_no_audio now runs on the relative `gpu_results.zip.part`. Tested: no fake-HOME string in `check --app`'s
  output, in each refusal, in `results`' output.
- **Breaks (each on the worktree, the test file run, the file restored), 17 of 17 caught:** B1 (`and` -> `or`), B2
  (`|| bad=1` -> `|| true`), B3 (the dry-run gate off), B6 (the app refs check off), B7 (no /mnt/c form); the
  guard's id, md5 and path checks each off, and the guard case-sensitive; the summary zipped as is; gpu_run.log back
  in; no home scrub in text; WINDOWS_PROFILE ignored; takes.py's `shown` off; gpu.sh's `tilde` off;
  check_no_audio on the full path; a record carrying the exception's message.
- **Checks:** tests/test_eval_takes.py 36 passed (6.86 s); after the merge with the engine and privacy tests, 65
  passed. Privacy: 0 found against the stress list; against the 20-song list 15, each the common false-positive
  word on lines main already has (the summary's field of that name is no longer copied, so the fix adds none). Diff
  and messages scanned: no lyric, audio, model name, personal detail, home path.
- **Left:** the guard would also stop a zip whose drive.sh scores (SCORECARD.md, score.txt; refs only, never on his
  new PC, which has no eval tools) held the common-word id as a word; it says which member. A home folder that is a
  prefix of another folder in a file (`<made-up home>` and `<made-up home 2>`) stops the zip too (fail-safe).
- **CI** on 7000dfe: <repo>/actions/runs/42507474861, success (linux, windows); the suite 1247 passed, 4 skipped in 628.95s (0:10:28), none of the skips this order's.

## Re-check fixes (the privacy re-check of 7000dfe: F1, F2)

Commits on top of 7000dfe: the re-check fix commit (guard, tests, README line) and a merge of main (docs only).
Head 7a76d42.

- **F2, the guard on its own strings:** on each member's name and text, in lower case and once more with runs of
  spaces, hyphens and underscores read as one space, it stops on:
  - **id / title / artist / charter:** a 20-song id, or a title, artist or charter (primary and alts) of the stress
    or 20-song local list, as a whole word. Names under 3 characters are not checked; a name equal to a stress id
    or a label is public (eval/stress.json) and not checked, as privacy_check.py skips a song's id.
  - **user name:** $USER, and the home folder's last part, as a whole word.
  - **md5:** an md5 of either list (primary or alt), or a hex run of 8-32 digits that starts one.
  - **path:** `/mnt/[a-z]/users/`, `[a-z]:[\/]+users[\/]`, `[\/]{2,}wsl$` or `wsl.localhost`, the home folder,
    the Windows profile in its three forms.

  A stop prints `<member>: <kinds>`, the member by its label path, any name inside it masked as `<kind>`, never the
  text; the header says the lines hold no name and can be sent as they are, and the README says so. The engine
  summary now goes in as `seed_<s>/summary.json` (was `autochart_run/summary.json`), since "autochart_run" reads as
  "autochart run" and would stop every zip for an id that is "run".
- **F1 and F2 tests:** 23 planted cases, each made up, each stopping the zip with its kind: an id in another case,
  with spaces, with a hyphen; a title as one word of an underscored run and in another spacing; stress and 20-song
  artists and alt charters; a 20-song primary md5, an alt md5 in upper case, a stress primary md5, 12 digits that
  start a stress alt's md5; `/mnt/c/users/...` with no profile known, `C:/Users/...`, an escaped `e:\\users`,
  `\\wsl$` and `\\wsl.localhost`; the lower-case `/mnt/d/...` and escaped forms of a profile outside Users (so only
  the profile's own forms catch them); the home folder in upper case; $USER; the home folder's last part. Also: a
  name in a member's own path is masked in the stop; a title equal to its public stress id does not stop; the
  common-word id `run` leaves a normal zip alone and stops on a planted "Run". Each stop's printed lines are checked
  to hold none of the lists' titles, artists or md5 prefixes.
- **Breaks, 19 of 19 caught:** the re-check's Bd (primary md5s out), Be (the stress list ignored), Bb (the /mnt
  profile form out), Bc (the escaped form out of the guard); each of the three path patterns; $USER; the home
  folder's last part; the md5 prefix; titles; artists; charters; ids; the space/hyphen/underscore folding; the
  guard case-sensitive; public stress ids checked; names in a member's path unmasked; the summary back under
  autochart_run/.
- **The real lists, counts only:** a realistic zip (the faked run over the real sets, every take's files replaced
  by real engine output from the golden kept folders, named as takes.py's are: name `input`, artist
  `Unknown Artist`) passed the new guard with the real lists: 290 files. Before the public-id exemption it
  stopped on the stress set: one stress song's title (and its alts' titles) equals its committed stress id. Risk of
  a false stop on the 20-song set, from the lists (after normalizing; checked names only):
  - 20-song ids: 13, all one word; 1 occurs as a whole word in the repository's code and docs.
  - 20-song titles: 13 checked, 4 one word, 1 in the repository's text.
  - 20-song artists: 11 checked, 7 one word, 2 in the repository's text.
  - 20-song charters: 22 checked, 18 one word, 2 in the repository's text; 1 under 3 characters, not checked.
  - stress: titles 4 checked (1 one word, 0 in the text), artists 3 (2 one word, 0), charters 11 (10 one word, 1
    in the text; 1 under 3 characters, not checked).
  None of them occurs in the realistic zip; a false stop needs such a word in an engine chart or song.ini or in
  the structured fields, and the stop line says which file and which kind.
- **Checks:** tests/test_eval_takes.py 58 passed with HOME=/root and with HOME above the temp folder. Privacy: 0
  found against the stress list; 15 against the 20-song list, all the known common false-positive word on lines main
  has (the test file's made-up names match none). CI: below.
- **CI** on 7a76d42: <repo>/actions/runs/42511129576, success (linux, windows).

---

## M8-01 review (b57392d): privacy, app mode, README, tests of the tests

Copies in <shm>/review_m801 (deleted). tests/test_eval_takes.py on the copy: 21 passed, 1 skipped (scan-chart);
22 passed with SONGCHARTER_SCAN_CHART set. No engine run. No id, title or md5 printed (counts and labels only).

### R1 (major): `eval/gpu.sh takes`/`check`'s gates in app mode can be removed with every test green
eval/gpu.sh:112 (`takes.py --app --check ... || bad=1`), :222 (an empty set's dry run stops `takes`), :114 (refs
must be built). Only `_takes` (the detached half) is tested; `takes` and `check --app` never run in a test.
Breaks on a copy, test file run each time (all 22 pass):
- B2 `|| bad=1` -> `|| true`: with a made-up cu126 app (fake nvidia-smi), `gpu.sh check --app` prints
  "check: 2 problems" and exits 0 (original: exit 1). `takes --app` would then start an unattended run on an
  install whose CUDA provider cannot load.
- B3 the dry-run `|| { ...; exit 1; }` -> `|| true`: a set with no song is detached anyway.
- B6 the refs check -> `true`.
- B1 (takes.py:166) `if not (cu13 and cudnn)` -> `or`: a Python with cuDNN but no CUDA 13 passes the check (the
  test only covers libs=[]).
Caught, for contrast: B4 (content scrub and guard both off), B5 (check_no_audio's result ignored).

### R2 (minor): a 20-song id that is a common word is recoverable from the zip
gpu.sh results' scrub (and the guard, which reapplies the same regex, so it can never fire) replaces the word
everywhere in zipped text; the text around it is the repository's own, so the id reads back by diffing.
Repro (made-up id `run`): labels.json {"s01":"run"}, gpu_run.log "takes run started (sets: set20, ...)";
`gpu.sh results` -> zip's gpu_run.log: `takes s01 started (sets: set20, the installed app)`. The real set has 1 id
(3 letters) that is a common English word found in gpu.sh's messages, autochart.py, launch.py and errors.py (counts
only). No line the scripts or the engine write into the zip today holds it (checked), but any Python warning or
traceback in gpu_run.log likely would. Fix: do not scrub inside free text for such ids, or refuse/flag ids that are
dictionary-ish words in the scripts' vocabulary, and make the guard independent (case-insensitive ids, md5s).

### R3 (minor): the Windows-profile scrub has no test and cannot be reached in CI
gpu.sh:310-311 needs /mnt/c and cmd.exe. Dropping `(winp, "%USERPROFILE%")` (B7), or all three Windows entries,
leaves the tests green. A data folder or clone under /mnt/c/Users/<name> would then put the Windows user name in
every summary.json. Make the profile an env override (e.g. a variable the test sets) and test it.

### R4 (minor): the home path reaches the terminal (the lines he'd paste when something fails)
`gpu.sh check --app` prints it 3 times (takes.py:157 `at {home}`, :165 the autochart folder, :176
`sys.executable`); the Refused messages (`takes: the 20-song set's list <HOME>/data/set20/set20.json cannot be
read`), app_env's "no installed songcharter at $APP_HOME", `takes`' "tail -f $RUNS/takes/takes.log" and
check_no_audio's "(<HOME>/.../gpu_results.zip.part)" do too. Repro: fake app under HOME=<T>/h,
`gpu.sh check --app | grep -c <T>` -> 3. The zip itself is clean (scrubbed to ~). Print `~`-relative paths.

### Checked, no finding
Zip members by label; ids replaced whole-word in names and contents; set.json slots are set20-v03.md's generic
slots; take.json has the input SHA-256 and the engine install hash only; FAILED lines keep only the exception's
first line (scrubbed); node's stderr is captured, not passed through; check_no_audio runs on the .part zip; no md5
reaches the zip (only build output, scrubbed); `--set refs` paths and lines unchanged; resume via take.json key.

---

## M8-01 re-check (7000dfe): privacy of what leaves the owner's PC

Copy: <shm>/recheck_m801 (git archive of 7000dfe; deleted). Worktree untouched. tests/test_eval_takes.py on the
copy: 35 passed, 1 skipped (scan-chart). No engine run. Probes used made-up names only; no real id, title or md5 printed.

### Verdict on R1-R4: fixed as claimed
- R1: B2 (`|| bad=1` -> `|| true`) 3 tests fail, B3 (dry-run gate off) 1 fails, B6 (refs check off) 2 fail.
- R2: zip is structured. take.json and summary.json are copied field by field. The name fields allow
  `[A-Za-z0-9_.+ -]{1,40}` and hold only engine stage, status and device names. `input`/`ffmpeg`/`jobDir`/`error`
  are dropped. takes.jsonl stores the label, numbers, short names and the exception's type. set.json stores
  label/slot/charts/duration. gpu_samples.csv holds no GPU name or driver. No log goes in the zip.
  Engine metadata: stress/set20 input.wav is written by build_ref.py through soundfile (no tags). The driver writes
  name=`input` (the WAV's basename), artist `Unknown Artist`, charter `Autochart`. So no title, path or tag
  reaches song.ini or [Song]. Common-word id: no content scrub now, and the guard is whole-word and lower-case.
- R3: WINDOWS_PROFILE works and is tested (dropping all Windows handling fails 1 test).
- R4: tilde off -> 2 fail; shown() off -> 8 fail. Every gpu.sh echo with a path goes through tilde
  (grep: none left).

### Findings

### F1 (minor): parts of the guard can be removed with every test green
eval/gpu.sh:432-439. Breaks on the copy, test file run after each:
- Bd: primary md5s dropped from the guard (`[song.get("md5")] +` removed): 35 passed.
- Be: the stress list ignored (`for path in lists[1:]`): 35 passed.
- Bb: /mnt form of the profile dropped from `lowered`: 35 passed.
- Bc: JSON-escaped `C:\\Users\\...` form dropped from `lowered`: 35 passed.
(Contrast: guard on home only, Windows profile dropped: 1 fails.)
The guard test plants only an alt md5 of the set20 list and a lower-case `c:\users\...`.
Fix: plant a primary md5, one from $DATA/stress.local.json, and lower-case /mnt/c/... and escaped forms.

### F2 (minor): the guard's path check is not independent of the scrub; it misses other forms
eval/gpu.sh:426, 439: `lowered` is the scrub's own `places` (home, win, escaped win, winp). Probe: three_sets
fixture, planted in a set20 take's song.ini, `gpu.sh results` under a made-up HOME. Each one made the zip (exit 0):
- `/mnt/c/Users/Madeupname/...` with no cmd.exe answer and no WINDOWS_PROFILE: no Windows check at all.
- `C:/Users/Madeupname/...` with WINDOWS_PROFILE=`C:\Users\Madeupname`.
- `\\wsl$\Ubuntu\<home with backslashes>\x` and `\\wsl.localhost\...` forms.
- the user name alone (`charter = Madeupname`), a 12-hex md5 prefix.
- a title in another form than its id (`Quimby Flux`, `quimby-flux` for id quimby_flux), `zorblat_live`.
None of these has a writer today (see R2 above: engine output is fixed text, JSONs structured).
This is residual risk, not a leak. Cheap hardening: pattern stops for `/mnt/[a-z]/users/[^/]+`,
`[a-z]:[\\/]+users[\\/]`, and `\\wsl`. Also stop on the title/artist/charter fields of the local lists,
which the guard already reads for the md5s.

### Not a finding / notes
- `check` prints nvidia-smi's driver_version and memory to the terminal (gpu.sh:110). This is on main
  already, not this order's change, and identifies no person.
- Python tracebacks (for example a runtime.json that is a list -> AttributeError in check) would print the
  clone's path. Corrupt install only; not pursued.
- Not checked: whether the real common-word id matches a word in a real engine chart. That would stop the zip
  (fail-safe), not leak, and there are no real takes here.
