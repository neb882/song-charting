# Evaluation: existing auto-charters against human charts

Scores audio-to-chart tools against careful human charts, so decisions rest on numbers rather than impressions.
It runs three existing open-source tools, and later songcharter itself, on six reference songs:

| id | song | chart by |
|---|---|---|
| kimochi_warui | Car Seat Headrest – Kimochi Warui | InsaneOwO |
| drunk_drivers | Car Seat Headrest – Drunk Drivers / Killer Whales | IaSg14 (248 tempo markers) |
| take_me_out | Franz Ferdinand – Take Me Out | Harmonix |
| all_the_small_things | Blink-182 – All the Small Things | Harmonix |
| lucretia | Megadeth – Lucretia | Harmonix |
| creep | Radiohead – Creep | Harmonix |

The reference charts and their audio are downloaded from Chorus Encore into `eval/data/`, which is git-ignored.
They are other people's work: they are used locally for scoring only, never committed or shared. Vocal and
lyric data is stripped from the reference charts when they are built.

## What is measured (`scorer/score.py`)

The candidate's audio is aligned to the reference audio by cross-correlation. Both charts are then parsed with
scan-chart, the parser Chorus Encore uses. Per instrument and difficulty, the scorer reports:

- note-onset precision, recall and F1 at ±50 ms and ±100 ms,
- note density against the reference,
- chord, HOPO, tap and sustain shares,
- lane-direction agreement (whether the frets move up or down when the human chart's do),
- per-pad F1 for drums,
- beat F1 of the tempo map, and the downbeat F1 of its measure lines,
- scan-chart issues,
- the feel measures (`docs/reports/feel.md`): the 1-s density peak, per-note strum/HOPO/tap agreement, lane jumps,
  star power phrases per minute and the solo share, and with `--windows N` the F1@100 of every N-second window.

`scorecard.py` summarizes everything as markdown.

## Golden charts (`golden.py`)

songcharter's own charts of the reference set, built before and after a change, so that a change which moves a chart
it was not meant to touch is seen (`docs/DESIGN.md` 3.6). Run it from the root of a checkout, on Linux or WSL:

```sh
export EVAL_DATA=...            # the reference set is $EVAL_DATA/refs (default: eval/data/refs)
export SONGCHARTER_GOLDEN=...   # the kept work folders: $SONGCHARTER_GOLDEN/work (default: <user cache>/golden/work)
export SONGCHARTER_AUTOCHART=... SONGCHARTER_ALLIN1_PYTHON=...   # the installs that made the kept folders
git worktree add --detach /dev/shm/golden-old <the commit before the change>
RERUN=""      # the same for both runs, e.g. RERUN="--rerun bass": see --rerun below
EXPECT=none   # or the parts the change was meant to touch, e.g. EXPECT=bass:hard
rm -rf /dev/shm/golden/old /dev/shm/golden/new &&
python -m eval.golden run --code /dev/shm/golden-old --out /dev/shm/golden/old --threads 2 $RERUN &&
python -m eval.golden run --out /dev/shm/golden/new --threads 2 $RERUN &&
python -m eval.golden diff /dev/shm/golden/old /dev/shm/golden/new --expect $EXPECT
```

Each run must exit 0, and then the diff must exit 0; the `&&` stops at the first that does not. `run` passes the
same `SONGCHARTER_SCAN_CHART` and `SONGCHARTER_AUTOCHART` to both builds (autochart from this checkout's
`eval/tools/autochart`, and scan-chart from its `tools/scan-chart`, when they are unset). Without
`SONGCHARTER_ALLIN1_PYTHON` the sections fall back to librosa, and `run` stops (exit 2): every star power phrase and
solo would move.

- **`run`** builds each song with `songcharter chart --levels all --takes 1 --device cpu --no-preview` from the checkout
  `--code` (default: this one), and writes the song folders, `summary.json`, `logs/` and `scores/` into `--out`. For
  each song, part and difficulty, the summary has the onsets, the notes and scan-chart's track hash, read through
  `scorer/scan_notes.cjs` as Clone Hero reads the folder (the hash covers the tempo map, star power, solos, drum fills
  and every note's tick, length, type and flags). For the six songs with a human chart it also has `score.py`'s F1@50
  and F1@100 and the beat F1. Its `run` section (the times, the engines that ran, the paths) is the only part that
  differs between two runs of one commit. Exit 0 when every song was built (a failed gate is recorded), 1 when a build
  failed, 2 on bad input or environment, 3 a bug. It first clears `--out` of what an earlier run or diff left there
  (summary.json, report.md, report.json, logs/, scores/, the song folders), so a refused, failed or killed run leaves
  no summary behind; a run stops (exit 2) when an engine runs without being asked (its kept output did not answer),
  naming why.
- **The kept work folders.** The heavy stages run once per song, into `$SONGCHARTER_GOLDEN/work/<id>`. Every build
  after that runs in a work folder of its own made from the kept one (the decode and stems hard-linked, the engines'
  folders copied) and costs mostly assemble. Two runs, at once or one after the other, never write into a kept folder,
  and `run` checks this after every build. `--stems DIR` hard-links the stems from a separation cache
  (`separate.py`'s `<key>/` folders) when a kept folder is first made. To make a kept folder again, delete it. In the
  dev container (CPU, 2 threads) a kept folder took 8–18 minutes a song with the stems linked, and a build after
  that about a minute: 6.5 minutes for the seven songs.
- **`--rerun`.** The engines' caches are keyed by their inputs and settings, not by their code. When an engine's code
  changed since the kept folders were made, pass `--rerun` with that engine to both runs: a run that reruns it alone
  compares the kept commit's output with its own, which `diff` flags. For each engine not rerun, `run` checks with git
  whether the engine's files differ between the kept folders' commit and its code (`ENGINE_FILES`), warns, and `diff`
  fails: `drums` (`songcharter/engines/adtof.py`, `engines/drumlanes.py`, `beatgrid.py`, `chart.py`, `tempo.py`,
  `ini.py`), `bass` (`engines/bass.py`, `chart.py`, `tempo.py`, `timed.py`), `sections` (`engines/sections.py`,
  `engines/allin1_runner.py`, `sections.py`), `guitar` (`engines/autochart.py`; autochart's install and driver are in
  the take's own key). Everything else (the grid, quantizer, reductions, star power, assemble) runs in every build
  anyway. The kept folders are left as they are. In the dev container, rerunning drums, bass and sections added 2–4
  minutes a song to each run (24 minutes for the set) and reproduced the baseline exactly; a guitar rerun is a whole
  autochart run, its own separation included: 3.5–11 minutes a song. An engine whose kept output does not answer (its
  settings or version changed, another install, the sections backend) makes `run` stop with exit 2 unless it is rerun;
  a decode or separation that does not answer (their samples or settings changed) too: then delete the kept folders to
  make them again. A change to the separation's code alone does not show at all, because every run reads the kept
  stems.
- **`diff`** compares two summaries. `--expect` names the parts the change was meant to touch: `none`, or parts and
  `part:difficulty` pairs. A part and difficulty whose hash changed, appeared or vanished is "changed" when it is
  expected and UNEXPECTED when it is not. So is a song that is missing from either summary, whose build failed, or
  whose gate changed, and, for the runs as a whole, an engine rerun in one run only, an engine whose kept output is
  another commit's, and sections from different backends (named above the verdict). `report.md` and `report.json`
  (beside the new summary unless `--out` says otherwise) give a table per song (status, onsets old → new, F1@50 old →
  new), the F1 pooled over the songs per part and difficulty, and which engines ran. Exit 0, or 1 when anything is
  UNEXPECTED, or 2 when the summaries cannot be compared.

## Stress songs (`stress.py`)

The stress set is a repeatable check beside the golden set, on the songs that show what the reference set misses
(`docs/DESIGN.md` 3.3; `docs/work-orders/M5-09-stress-eval.md`). Each song has every human chart Chorus Encore has
of it: our chart is scored against each, and the other human charts against the first (the humans' agreement, the
ceiling of every measure). `eval/stress.json` names the songs by generic ids:

| id | slot | human charts | the primary (the one with the most parts) |
|---|---|---|---|
| troop | a 198 BPM power-metal song | 3 | guitar, bass, drums and vocals (lyric events: the lyrics check) |
| sooth | a 9-minute shred instrumental | 2 | guitar and bass |
| break | an ordinary rock song, the guard against making normal songs worse | 4 | guitar (two other charts have only a 6-fret and a rhythm part, and are listed but not scored) |
| pm2 | a second 200 BPM power-metal song, 7:20, with long solos (M5-11) | 5 | guitar, bass, drums, keys and vocals (lyric events: timing scripts only) |

The packages' md5s, titles and charters are not committed, the owner keeps the list: `$EVAL_DATA/stress.local.json`
(`refs.json`'s shape, each entry with `alts`, the other charts' `md5` and `charter`). The packages are other
people's work: downloaded into `$EVAL_DATA/sng/`, never committed.

`eval/refs/build_ref.py` takes the chart by its exact name, `notes.mid` or `notes.chart` (a `notes.mid.backup` beside
it is not one); a package with both gets `notes.mid`, the one scan-chart reads, and `build_meta.json` names the other as
`chart_not_used`. `eval/refs/strip_lyrics.py` drops the vocal tracks and lyrics events of a MIDI without reading it
into a MIDI library, so what mido refuses is accepted and every other byte is kept: a Phase Shift sysex with the
difficulty byte 0xFF (a tap or open marker for every difficulty; mido: ValueError, and `clip=True` turns it into 0x7F,
which scan-chart cannot read) and a channel event in running status straight after a sysex (mido: EOFError).

```sh
export EVAL_DATA=... SONGCHARTER_GOLDEN=...                      # as for the golden charts, and the same engines:
export SONGCHARTER_AUTOCHART=... SONGCHARTER_ALLIN1_PYTHON=... SONGCHARTER_SCAN_CHART=...
eval/build_refs.sh --set stress                                  # $EVAL_DATA/stress/<id>/ and <id>/alt/<md5>/
python -m eval.golden run --refs $EVAL_DATA/stress --work $SONGCHARTER_GOLDEN/stress-work \
    --out $SONGCHARTER_GOLDEN/stress-new --threads 2             # add --code CHECKOUT for another commit
python eval/stress.py score $SONGCHARTER_GOLDEN/stress-new       # stress_scores.json and the feel report
python eval/stress.py compare eval/baseline/stress $SONGCHARTER_GOLDEN/stress-new   # exit 1 on a regression
python eval/stress.py lyrics troop --run $SONGCHARTER_GOLDEN/stress-new            # the lyrics timing check
python eval/stress.py align break /path/to/a/file/of/the/song.mp3                  # does that file align?
```

- **`build_refs.sh --set stress`** builds the primary chart of each song into `$EVAL_DATA/stress/<id>/` as a
  reference is built (input.wav from the package's audio, the stems summed; `ref/` with vocals and lyrics stripped;
  ref_notes.json; offset_check.json), every other chart into `<id>/alt/<md5>/`, then `stress/songs.json`. A stem
  ffmpeg cannot open, or one with no samples (the power-metal primary's four 135-byte stubs), is skipped and named
  in `build_meta.json`'s `stems_skipped`. The unpacked packages are deleted once built.
- **The run** is `eval.golden`'s (the module's docstring and the section above): kept folders in
  `$SONGCHARTER_GOLDEN/stress-work`, apart from the golden set's (the default when `--refs` is a folder named
  `stress`), the heavy-job lock, `summary.json` with the onsets, hashes and the primary chart's F1s; `golden diff`
  compares two stress runs as it compares two golden runs.
- **`stress.py score RUN_DIR`** runs `scorer/score.py --windows 30` for each song: ours against every human chart,
  and each other human chart against the primary. It writes `stress_scores.json` (numbers only) and
  `stress_report.md` beside the summary, and prints the feel report (`docs/reports/feel.md`): per song, part and
  chart, F1@50 and F1@100, the notes ratio and the lowest 30-s window; the matched notes' median timing error; chord
  share and the 1-s density peak; contour agreement, the jump-size distance and big fast jumps; HOPO, tap and
  sustain shares and the per-note state agreement; star power phrases per minute and the solo share; then the beat,
  octave-tolerant beat and downbeat F1, and the notes in silence and gaps while the stem plays (report.json's
  `silent_onsets`, and `songcharter.preview`'s flags with the kept folder's stems). Repeat consistency (the feel
  note's 4) is not measured yet (M5-99).
- **`stress.py compare OLD NEW`** (stress_scores.json files or the run folders holding them) puts every number of
  ours side by side and exits 1 when any part's F1@50 against the primary chart falls by more than 0.01 or is gone:
  the stress check of `docs/work-orders/M5-00-plan.md` section 7.
- **`stress.py lyrics ID [--run RUN_DIR]`** reads the words of the primary package's lyric events in memory, charts
  the song's input.wav with them through `songcharter.pipeline` in process (1 take, CPU, no preview) into a temporary
  folder, the work folder under it too (with `--run`, a copy of that run's kept folder, so only assemble and the
  aligner run), compares the lyric timings word by word (`lyrics_timing.py`), prints the numbers and deletes the
  folder whole. No word is printed, logged or saved (`docs/work-orders/M4-10-lyrics.md`'s rule).
- **`stress.py align ID FILE`** cross-correlates a file against the song's input.wav as score.py aligns: aligned
  (exit 0) when most windows peak at 0.3 or more and the lags' MAD is under 2 ms.
- **The baseline** is `eval/baseline/stress/`: `stress.py baseline RUN_DIR eval/baseline/stress` copies the run's
  `summary.json` and `stress_scores.json` with every path cut to its last part, and checks that no md5, title,
  artist or charter of the local list is left.

**Cost** [measured on the dev machine, 4 cores, CPU, 2 threads]: the build, under a minute a chart (3 minutes for
the nine), 0.57 GB; the first run, which makes the kept folders (the separation runs in them: no separation cache
holds these songs), 67 minutes for the first three songs (23, 34 and 7 minutes a song, the guitar take most of it; pm2, added by M5-11,
28 minutes more) and 2.5 GB; a run after that
builds each song from its kept folder in 28 to 80 s (as the first run's builds did); `score`, 2 minutes. Refuse to
start a first run under 10 GB free.

**A song is added** with one entry in `eval/stress.json` (an id, its slot, its chart count, what its primary holds)
and its md5s in the local list, then `build_refs.sh --set stress` (it builds only what is missing) and a new
baseline run. Nothing of the set is committed but `stress.json` and the baseline's numbers.

## The tools under test

| tool | code | weights | instruments |
|---|---|---|---|
| [autochart](https://github.com/dvar0/autochart) (Fretformer 2) | AGPL-3.0 | CC BY-NC-SA 4.0 | lead guitar |
| [chartgen](https://github.com/Mechazawa/chartgen) | MIT | separator weights: licence unknown | lead guitar |
| [STRUM](https://github.com/opria123/strum) | MIT (stated) | MIT (stated) | guitar, bass, drums |

Each `tools/<tool>/setup.sh` installs one at a pinned commit and pinned, checksum-verified weights. Each
`tools/<tool>/run.sh <audio> <out>` writes a Clone Hero song folder and prints the CPU seconds it took.
Lyrics and vocals are switched off in every tool.

## Running it on an NVIDIA GPU (Linux or WSL2)

You need git, Node 20+, ffmpeg and [uv](https://docs.astral.sh/uv/). An RTX 50-series card needs CUDA 12.8+
PyTorch builds (`cu128`).

```sh
cd song-charting
(cd tools/scan-chart && npm ci)
uv venv eval/.venv && uv pip install --python eval/.venv/bin/python -r eval/requirements.txt
eval/build_refs.sh /path/to/test-song.mp3          # reference set, plus the test song
TORCH_INDEX=https://download.pytorch.org/whl/cu128 eval/tools/strum/setup.sh
TORCH_INDEX=https://download.pytorch.org/whl/cu128 eval/tools/chartgen/setup.sh
eval/tools/autochart/setup.sh
```

Then run it the way Overclock renders, as a job of its own that no Claude session has to babysit:

```sh
eval/gpu.sh check      # names the GPU, runs a CUDA op inside each tool, shows the memory WSL has; fails on a CPU fallback
eval/gpu.sh start      # every tool on every song, detached; finished jobs are skipped, so it resumes after any stop
eval/gpu.sh status     # the latest driver.log lines, GPU use, free memory
eval/gpu.sh takes      # 4 autochart Expert takes of every song (seeds 20260609,101,202,303; SEEDS=, SONGS= to change)
eval/gpu.sh takes stress set20   # the same for the stress and 20-song sets, one after the other (below)
eval/gpu.sh results    # eval/data/gpu_results.zip: scores, logs, the test-song charts and the takes' charts, no audio
```

`start` runs `drive.sh` in its own session (`setsid`), so closing the terminal or a crashed Claude session leaves
it running. It also raises the job's `oom_score_adj`: if memory runs out, the kernel kills the job, which resumes on
the next `start`, rather than Claude or Remote Control. Keep one Ubuntu window open while it runs, because WSL can
shut down after the last one closes. autochart falls back to CPU on its own if its CUDA provider fails to load,
and its run logs name the device it used.

### Memory

By default WSL gets half of Windows' RAM. STRUM and chartgen on a long song can need more than that, and a WSL
that runs out kills processes or stalls. Give it more in `%UserProfile%\.wslconfig` on Windows, then run
`wsl --shutdown` from PowerShell, which stops everything in WSL, and reopen Ubuntu:

```ini
[wsl2]
# your RAM minus about 8 GB for Windows (this is for 32 GB); comments go on their own lines
memory=24GB
swap=8GB
```

From Ubuntu, this writes that file without Notepad's habit of adding `.txt`:

```sh
cat > "$(wslpath "$(cd /mnt/c && cmd.exe /c 'echo %USERPROFILE%' 2>/dev/null | tr -d '\r')")/.wslconfig" <<'EOF'
[wsl2]
memory=24GB
swap=8GB
EOF
```

## GPU takes with the installed app

M8 measures 4 autochart Expert takes of every song with human charts on the owner's GPU: the six references and the
test song, the stress set's 4 (Stress songs, above), the 20-song set's 13 (`docs/reports/set20-v03.md`). The
installed songcharter makes them (`packaging/linux/install.sh`, the cu132 lane): `--app` points `eval/gpu.sh` at its
Python, Node, scan-chart, ffmpeg and autochart with its CUDA provider, so the eval tools (strum, chartgen,
`eval/tools/autochart` and their models: several GB) are not needed, and the check is autochart's only.

- **What it needs:** the app installed on the cu132 lane (`songcharter doctor`), the GPU visible (`nvidia-smi`), a
  clone of the repository, and `python3` and `curl` (Ubuntu has both). Nothing is installed. The app's Python
  (`~/.local/share/songcharter/runtime/env/bin/python`; `SONGCHARTER_HOME` names another install) has every package
  the build scripts use (numpy, soundfile, librosa; none needs mido), its runtime the `node` and scan-chart that
  `build_ref.py` runs. `ffmpeg` is Ubuntu's when it has one, else the app's (imageio-ffmpeg's), linked as
  `eval/data/bin/ffmpeg`.
- **The code:** songcharter is imported from the clone, first on `sys.path`. When this was written (M8-01, on
  0.4.0's code), `songcharter/engines/autochart.py`, the driver and the launcher were as in v0.3.1 (the app's
  version), and `uv.lock` and `pyproject.toml` differed only in the version, so a take runs as the app's would, with the app's environment (`songcharter.launch`) and,
  for CUDA, the CUDA 13 and cuDNN libraries of the app's own Python. A later clone still runs its own wrapper on the
  app's packages: `git diff v0.3.1 -- songcharter/engines/autochart.py uv.lock` shows what differs.
- **The inputs** are built as on the dev machine: `build_refs.sh` sums each primary package's stems into `input.wav`,
  so the takes are on the dev machine's kept folders' clock. On made-up Vorbis, Opus and MP3 stems, Ubuntu 24.04's
  ffmpeg 6.1.1 (the dev machine's) and the app's 9.0.2 decode to identical samples [here, one check]. Each take's
  `take.json` carries its input's SHA-256, so the orchestrator can check each `input.wav` against the dev machine's.
  The test song must be the same file as the kept folders' (its separation key is a hash of its samples).
- **The packages:** `build_refs.sh` takes each from `sng/<md5>.sng` (the md5s are `refs.json`'s and the lists') and
  downloads only a missing one, from `https://files.enchor.us/<md5>.sng`. Copy yours in under those names to skip
  the download. The 20-song set is a data folder of its own, `eval/data/set20` (`SET20_DATA` moves it), with its two
  lists, `set20.json` (the set's ids and slots) and `stress.local.json` (the md5s): the owner's, never committed.

From a fresh clone (`git clone <the repository> song-charting && cd song-charting`), or `git pull` in a release
clone (the paths are placeholders):

```sh
mkdir -p eval/data/sng eval/data/set20/sng
cp /path/to/the/packages/*.sng eval/data/sng/              # the references' and the stress set's, as <md5>.sng
cp /path/to/the/set20/packages/*.sng eval/data/set20/sng/  # the 20-song set's
cp /path/to/stress.local.json eval/data/                   # the stress set's list
cp /path/to/set20.json /path/to/the/set20/stress.local.json eval/data/set20/   # the 20-song set's two lists
eval/gpu.sh build --app refs /path/to/the-test-song.mp3    # eval/data/refs: 6 songs and the test song
eval/gpu.sh build --app stress                             # eval/data/stress: 4 songs, 14 charts
eval/gpu.sh build --app set20                              # eval/data/set20/stress: 13 songs, 50 charts
eval/gpu.sh check --app                                    # the GPU, the app's autochart with its CUDA provider, memory
eval/gpu.sh takes --app refs stress set20                  # detached, one set after the other; then the zip
eval/gpu.sh status                                         # the latest lines of runs/takes/takes.log
eval/gpu.sh results                                        # eval/data/gpu_results.zip (again, after a stop)
```

- **The build** [dev machine, CPU]: under a minute a chart, plus the downloads; the folders take about 0.4 GB
  (refs), 1.1 GB (stress) and 3.0 GB (set20), as each other human chart gets an `input.wav` too. The stress and
  20-song builds print through `takes.py --scrub`: songs by their labels, every md5 as `<md5>`.
- **The takes** go one set after the other (or one at a time: `eval/gpu.sh takes --app stress`), each set's songs
  checked first (`takes.py --dry-run`: the songs found, by label). `takes` refuses while a run is going. A run that
  stops resumes: the same command reuses every finished take. Each line of the log names the song by its label.
- **GPU time** [the owner's RTX 5070]: 4 takes of a 4-minute song take about 4-15 minutes, dense songs more (the
  9-minute shred song 36 minutes). So, at about 1 to 4 GPU minutes a minute of audio [an estimate from those, not
  measured]: the reference set (30 minutes of audio with the test song) 0.5-2 hours, the stress set (25 minutes)
  0.5-1.5 hours, the 20-song set (75 minutes) 1.5-5 hours.
- **The zip** (`eval/data/gpu_results.zip`, and a copy in Windows' Downloads folder), made at the end of a run or by
  `results`, holds structured files only: per set, each take's `notes.chart` and `song.ini` as the engine wrote them,
  its `take.json` (its key: the input's SHA-256, the seed, the install) and `summary.json` (the engine's
  `autochart_run/summary.json`: devices, tokens, beats and timings), both copied field by field (numbers, hashes and short names: no path, no
  message), and the set's `set.json` (each label's slot, chart count and length); `takes/takes.jsonl` (takes.py's
  record of each take: made, cached or failed, a failure by its exception's type) and `gpu_samples.csv` (the GPU's
  use every 5 s). No log goes in: `takes.log`, which has each failure's message, and `gpu_run.log` stay on this PC
  (`eval/gpu.sh status` shows them). The reference set's takes are under `takes/<id>/`, the others' under
  `takes/<set>/<label>/`. A 20-song song's take folder goes in under its label (s01-s13, in the order of the sorted
  ids, as `set20-v03.md` names them); the mapping, `runs/takes/set20/labels.json`, stays on this PC. In the text
  files, this PC's home folder is written `~` and the Windows profile `%USERPROFILE%` (`WINDOWS_PROFILE` names it,
  else Windows' own). Then a guard reads the finished zip, in lower case and with spaces, hyphens and underscores
  alike: a 20-song id, a title, artist or charter of the two lists (one that is a stress id, public, aside), this
  PC's user name, an md5 of the lists or 8 or more of its first digits, a Windows user folder, a `\\wsl$` path, the
  home folder or the Windows profile, in any file, and no zip is made; `check_no_audio.py` must pass too. **If the
  guard stops it, send its lines as they are:** each names a file by its label path and the kind of hit (id, title,
  artist, charter, user name, md5, path), never the name. A path the scripts print is written with `~`.

## The thin spike with the installed app (M8-11)

`eval/gpu.sh thin-spike` (`eval/spike/thin_spike.sh`) makes Expert takes of a song under four engine settings, the
"arms": `base` (temperature 0.95, the app's), `hot` (1.05), `dense5` and `dense6` (the density knob, "speed", at 5
and 6), four seeds each, with a patched copy of the app's driver (the app's own is never changed). With `--app` it runs
on the installed app's autochart, Node, Python and ffmpeg, as `takes --app` does: it needs what that section needs
(the app on the cu132 lane, the GPU, a clone), no eval tools, and no set built. From the clone (the paths are
placeholders):

```sh
cd /path/to/song-charting && git pull
eval/gpu.sh thin-spike --app "/path/to/the song.mp3"   # the check, then the spike, detached
eval/gpu.sh status                                     # the latest lines of eval/data/runs/thin_spike/thin_spike.log
eval/gpu.sh stop                                       # only if needed: the same thin-spike line carries on
```

- **The check** runs first, as `check --app` does: the GPU, the app's lane, onnxruntime-node's CUDA provider, the CUDA
  13 and cuDNN libraries. A problem stops it before anything starts. The run itself stops after a take whose
  transcriber did not run on CUDA. `ALLOW_CPU=1` skips only the check before the start, never that stop: don't set it.
- **Time:** 16 takes (4 arms x 4 seeds), about 2.5 hours of the GPU (M8-11's estimate), unattended. Keep one Ubuntu
  window open while it runs.
- **The takes** are in `eval/data/runs/thin_spike/song/<arm>/seed_<seed>/`. After a stop, the same line keeps every
  take already made as this run would make it (the same file by its SHA-256, the seed, the arm's settings, the
  transcriber on CUDA), and makes the rest; the log says why a take is made again.
- **The zip**, `eval/data/runs/thin_spike/thin_spike_results.zip`, is made at the end of the run. It holds this run's
  takes: each one's `notes.chart` as the engine wrote it, and its `autochart_run/summary.json` copied field by field
  (the settings, the devices, tokens and timings: no path, no message). There is no log and no audio in it. A guard
  then reads it back (this PC's home folder, a Windows user folder, a `\\wsl$` path, the user name), and
  `check_no_audio.py` checks it. If either stops it, no zip is made: send the lines it printed as they are.
  `(cd eval/data/runs/thin_spike && explorer.exe .)` opens the folder in Windows, to send the zip back.

**Later, the references' arm.** If an arm clears M5-99's bar, M8-11 checks it on the references before adopting it:
the same steps with `ARMS` set to the winner and `base`, on each reference's `input.wav`. `eval/gpu.sh build --app
refs` builds those (GPU takes with the installed app, above). One line runs the six (eval/refs.json's ids; not the test
song: the bar is the references' pooled F1@50), one after the other, each song's takes under its id
(`.../thin_spike/<id>/<arm>/seed_<seed>/`):

```sh
# the winner in place of dense5:speed=5
ARMS="base:T=0.95 dense5:speed=5" eval/gpu.sh thin-spike --app \
  eval/data/refs/{all_the_small_things,creep,drunk_drivers,kimochi_warui,lucretia,take_me_out}/input.wav
```

That is 8 takes a song (2 arms x 4 seeds), twice the takes of `eval/gpu.sh takes --app refs` for those six. The zip
is made again in the same place, with this run's takes only, so send the first one before starting this run.

## Rebuilding the dev machine

The golden charts (`eval/golden.py`) and the engines' development need a set of installs and data that live outside
the repository (the dev container keeps them in its scratch folder). None of it is committed, and the repo builds
all of it except the test song. This is the order to run it on a fresh Linux machine or WSL2. Times are from the
dev container (4 cores, CPU only, 2 threads per job); a step marked "unconfirmed" was not run or recorded there.
The whole rebuild is about 2 to 3 hours of machine time and about 14 GB of disk (the container's pieces: 6.1 GB
Python environment, 4.8 GB kept folders, 3.6 GB separation cache, 1.1 GB autochart, 0.5 GB references, 0.5 GB model
cache; a cpu-lane environment should be smaller, see step 3).

Pick one folder for all of it, on a disk with about 15 GB free (the kept folders hard-link the stems from the
separation cache, so keep `$DEV/sepcache` and `$DEV/golden` on one filesystem):

```sh
export DEV=/path/to/dev        # every step below uses it
```

### 1. System packages

Linux x86_64, or WSL2. Needed: `git`, `curl`, `ffmpeg` (6.x in the container; it decodes the
reference audio and writes the test song's WAV), Node 20 or newer (22.x in the container), Python 3.13 (the lock
files are for 3.13 and `requires-python` is below 3.14), and [uv](https://docs.astral.sh/uv/) at exactly 0.13.5,
which `pyproject.toml` and `packaging/allin1/pyproject.toml` pin with `required-version` (`uv self update 0.13.5`, which only works
for a uv its own installer put there, else `curl -LsSf https://astral.sh/uv/0.13.5/install.sh | sh`; the container had 0.11.32, which refuses the pin, and never used uv for its
environments). RAM: the guitar engine (autochart's Node process) peaked at 12.8 GB once, and the whole build tree at 10.1 GB on the CPU;
give WSL2 at least 16 GB (`memory=` in `.wslconfig`, above).

```sh
sudo apt-get install -y git curl ffmpeg build-essential      # build-essential: unconfirmed that anything compiles
uv --version                                                 # must print 0.13.5
node --version                                               # 20 or newer
```

### 2. The checkout and scan-chart (a minute, 0.1 GB)

```sh
git clone <the repository> song-charting && cd song-charting
(cd tools/scan-chart && npm ci)
```

`tools/scan-chart` pins scan-chart 8.0.1 in its `package-lock.json`; `SONGCHARTER_SCAN_CHART` defaults to
`tools/scan-chart/scan.cjs` when unset.

### 3. The Python environment (unconfirmed time, 6.1 GB in the container)

The supported way is CLAUDE.md's command, with the lane for the machine (`cpu` with no NVIDIA GPU, `cu126` for a
driver under 580, `cu132` for 580 or newer). Never run `uv sync` with no lane: it installs PyPI's CUDA torch.

```sh
uv sync --frozen --extra cpu --extra app --extra dev     # the venv is ./.venv; say UV_PROJECT_ENVIRONMENT=$DEV/venv for another place
```

`app` brings demucs (separation), torch (the drums engine), librosa (bass, sections fallback, preview) and
imageio-ffmpeg; `dev` brings pytest, mido and packaging, which the scorer and the suite use. The container's own
environment was not made this way: it was `python3.13 -m venv`, then `pip install` of the
project in editable mode with its extras, which pulled PyPI's CUDA 13 torch 2.15.0 (hence 6.1 GB); a cpu-lane
environment drops the `nvidia-*` wheels, which should cost about 1.5 to 2 GB (unconfirmed).

Check it: `uv run songcharter doctor` (names the device, the engines found and what is missing).

### 4. allin1's own Python (a few minutes, 0.2 GB for the cpu lane, unconfirmed)

The sections engine runs allin1 in a Python of its own, found through `SONGCHARTER_ALLIN1_PYTHON`. Without it the
sections fall back to librosa, and `eval.golden run` stops with exit 2. `packaging/allin1/` (M4-01) is now the
supported way, locked on the same lanes as the root project:

```sh
UV_PROJECT_ENVIRONMENT=$DEV/allin1 uv sync --frozen --project packaging/allin1 --extra cpu    # same lane as step 3
export SONGCHARTER_ALLIN1_PYTHON=$DEV/allin1/bin/python
```

It installs all-in-one-infer 3.1.0 and torchaudio 2.11.1 (63 packages on the cpu lane in M4-01's check). The
container's golden baseline did not use it. It used `research/timing/venv2` (127 MB), a plain venv made by hand in
an earlier session, whose recipe was not recorded in the repo or found in the session transcript: it holds
all-in-one-infer 3.1.0, demucs-infer 4.4.0, madmom-infer 0.2.0 and torchaudio 2.11.1, and a `_base.pth` that points
at the main environment's `site-packages` for torch, numpy and scipy (so it has no torch of its own). The
sections cache key hashes the package name and version, the model, its weights and the device, not the Python's
path or torch's build, so the kept folders answer with either; whether the new environment gives byte-identical
segments (a different torch build) is unconfirmed, and step 9 shows it: the sections' hashes would move.

The allin1 checkpoint (`taejunkim/allinone` on Hugging Face) downloads on first use into `~/.cache/huggingface`
and is checked against its pinned SHA-256.

### 5. The reference set (about 10 minutes, 0.5 GB, needs the network)

`eval/build_refs.sh` downloads the six reference charts as `.sng` packages from `https://files.enchor.us/<md5>.sng`
(Chorus Encore; the md5s are in `eval/refs.json`), unpacks them and builds `$EVAL_DATA/refs/<id>/` (the stems
summed into `input.wav` and `input.mp3`, the chart with vocals and lyrics stripped, `ref_notes.json`,
`offset_check.json`), then `refs/songs.json`. It runs the helper scripts with `EVAL_PY` (default
`eval/.venv/bin/python`); point that at the step 3 environment instead of making a second one. The downloads are
other people's work: they stay in `$EVAL_DATA` and are never committed.

The test song is the owner's own file, never in the repo: the owner provides it. Pass it as the argument and the
script makes `refs/test_song/` from it (a gapless 44.1 kHz stereo WAV and a copy of the file).

```sh
export EVAL_DATA=$DEV/eval
export EVAL_PY=$PWD/.venv/bin/python
eval/build_refs.sh /path/to/the-owners-test-song.mp3
ls $EVAL_DATA/refs     # seven folders: the six ids, test_song, and songs.json
```

The golden set is these seven songs (`docs/PROGRESS.json`, golden). The test song's separation key
(`13506d568d...`) is a hash of its decoded samples, so a different encode of the same song gives other keys and
the kept folders made from the container's will not answer; use the same file.

### 6. autochart (about 15 minutes, 1.1 GB)

```sh
eval/tools/autochart/setup.sh        # clones dvar0/autochart at b5a41e8e to ./src, npm ci, then fetch_models.sh
export SONGCHARTER_AUTOCHART=$PWD/eval/tools/autochart
```

`npm ci` installs onnxruntime-node 1.27.0 (502 MB; its postinstall downloads the Linux x64 binaries, including
the CUDA execution provider, so nothing extra is needed for CPU runs). `fetch_models.sh` downloads Fretformer 2
(478 MB) from Hugging Face at revision `8a88855d...` and verifies every file's size and SHA-256 against autochart's
own catalog. The weights are CC BY-NC-SA 4.0. For the GPU, the provider needs the CUDA 13 libraries including
`libcurand.so.10`, which the cu132 lane's `nvidia-curand` supplies (see `pyproject.toml`); the golden set runs on
CPU and needs none of it. Nothing else was done by hand to the container's copy that the repo does not do, except
that its `ac_headless.cjs` and `run.sh` are older copies of the repo's (they lack `AC_DEVICE` and the `EVAL_LOCK`
variable). This matters in one way: the guitar take's key hashes the driver file, so kept folders made with the
older driver do not answer to the repo's, and a fresh machine makes its own kept folders anyway.

### 7. The separation cache (about 20 minutes, 3.6 GB)

`eval.golden run --stems DIR` hard-links the six-stem Demucs output from a separation cache when it first makes a
kept folder, so the 3 to 4 minutes of separation per song are done once. Without `--stems` golden separates inside
each kept folder itself (the same result, 18 minutes slower for the set, and 3.6 GB of stems in the kept folders
only). The cache is `songcharter/separate.py`'s own: `htdemucs_6s`, seed 0, shifts 1, overlap 0.25, on the CPU,
keyed by the decoded samples. The container filled it with a ten-line script (`sepcache/prep.py`, not in the repo)
that decodes `refs/<id>/input.wav` with `audio.decode` and calls `separate(mix, cache_dir=...)` for the seven
songs, 2 torch threads. It first downloads the htdemucs_6s weights (about 0.46 GB, into `~/.cache/huggingface`)
and checks them against their pinned hashes.

```sh
mkdir -p $DEV/sepcache/cache
tools/heavy.sh .venv/bin/python - <<'EOF'
import os, torch
torch.set_num_threads(2)
from songcharter import audio as A
from songcharter.separate import separate
for sid in ["test_song", "take_me_out", "all_the_small_things", "lucretia", "creep", "kimochi_warui", "drunk_drivers"]:
    mix = A.decode(f"{os.environ['EVAL_DATA']}/refs/{sid}/input.wav")
    stems, info = separate(mix, cache_dir=os.environ["DEV"] + "/sepcache/cache")
    print(sid, info.key, info.seconds, info.cached, flush=True)
EOF
```

Per song on the container: 114 s (all_the_small_things) to 255 s (kimochi_warui), 18 minutes for the six that were
separated (the test song's was copied from an earlier cache). `tools/heavy.sh` runs it after any other heavy job
on the machine has finished. The folders are named by key; the key printed for each song must match the one
`eval.golden` computes, or it separates again and says so (`--stems` then reports "no stems for key").

### 8. The kept golden folders (cold: about 80 minutes for the set)

The first `eval.golden run` makes `$SONGCHARTER_GOLDEN/work/<id>` for each song (decode, hard-linked stems, drums,
bass, sections, the autochart guitar take, assemble): 474 to 1081 s a song, most of it the guitar take, 4.8 GB in
all. It is the baseline run as well: run it at the commit you mean to compare against.

```sh
export SONGCHARTER_GOLDEN=$DEV/golden
export SONGCHARTER_SCAN_CHART=$PWD/tools/scan-chart/scan.cjs     # or leave it unset
.venv/bin/python -m eval.golden run --out $DEV/golden/base --threads 2 --stems $DEV/sepcache/cache
```

Later runs cost about 6.5 minutes for the set (the kept folders are only read). Keep `--stems` out of them.

### 9. The environment variables

| variable | points at |
|---|---|
| `EVAL_DATA` | the folder that holds `refs/` (step 5); default `eval/data` |
| `EVAL_PY` | the Python `build_refs.sh` runs its helpers with; default `eval/.venv/bin/python` |
| `SONGCHARTER_GOLDEN` | the folder that holds `work/`, the kept folders (step 8); default the user cache's `golden/` |
| `SONGCHARTER_AUTOCHART` | the autochart install, `eval/tools/autochart` after `setup.sh` (step 6); `run` uses the checkout's when unset |
| `SONGCHARTER_ALLIN1_PYTHON` | the `python` of allin1's own environment (step 4); unset means the librosa fallback and golden exits 2 |
| `SONGCHARTER_SCAN_CHART` | `scan.cjs` of `tools/scan-chart` (step 2); unset means the checkout's |
| `STRESS_LOCAL` | the owner's list of the stress set's packages (Stress songs, above); default `$EVAL_DATA/stress.local.json` |

All the container's values pointed into its scratch folder. A rebuilt machine's golden baseline is a new baseline:
its onsets and hashes need not equal the container's, kept in `eval/baseline/summary.json` (different torch build,
different library versions), so compare a change against a base made on the same machine; the container's
summary shows how far a rebuilt machine's charts are from it. After step 8, run the
suite once as the check:

```sh
SONGCHARTER_SCAN_CHART=$PWD/tools/scan-chart/scan.cjs uv run python -m pytest -q -p no:cacheprovider --basetemp=/dev/shm/pt
```

### Not rebuildable from the repo

- The test song: the owner's own file, which the owner provides. Its separation key and every kept golden hash
  depend on that exact file.
- The reference charts: downloaded from Chorus Encore by `eval/build_refs.sh`; they need the network and the
  service staying up (the md5s are pinned, a removed file is not recoverable).
- The model weights (Demucs, allin1, ADTOF, Fretformer 2): downloaded by the code at pinned revisions and checked by
  SHA-256, so they need Hugging Face, GitHub and the network.
- The container's exact charts (step 9: `eval/baseline/summary.json` holds their hashes and F1s), and its
  `sepcache/prep.py` (the snippet in step 7 stands in for it).
- The hand-made `research/timing/venv2` (step 4): replaced by `packaging/allin1`, not reproduced.
- The stress set's package list (`$EVAL_DATA/stress.local.json`, the owner's) and the owner's own audio of the
  stress songs: the owner provides them, as for the test song.

**Rebuilt on 2026-11-05** (a new container, these steps in order, the cpu lane): the cold golden base of `main`
took 64 minutes for the seven songs, and the six references' 72 part-levels came out byte-identical to
`eval/baseline/summary.json`, so a rebuilt machine can reproduce the committed baseline exactly. The test song's
upload was another encode of the owner's file (separation key `063cc9c8...`), so its tracks differ and it has a new
baseline there. `build_refs.sh` then built only the first reference (its helpers' ffmpeg read the song list): fixed
in M5-09.
