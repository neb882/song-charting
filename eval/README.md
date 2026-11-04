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
- beat F1 of the tempo map,
- scan-chart issues.

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
which `pyproject.toml` and `packaging/allin1/pyproject.toml` pin with `required-version` (`uv self update 0.13.5`
or the installer for that version; the container had 0.11.32, which refuses the pin, and never used uv for its
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

All the container's values pointed into its scratch folder. A rebuilt machine's golden baseline is a new baseline:
its onsets and hashes need not equal the container's, kept in `eval/baseline/summary.json` (different torch build,
different library versions), so compare a change against a base made on the same machine; the container's
summary shows how far a rebuilt machine's charts are from it. After step 8, run the
suite once as the check:

```sh
SONGCHARTER_SCAN_CHART=$PWD/tools/scan-chart/scan.cjs uv run pytest -q -p no:cacheprovider --basetemp=/dev/shm/pt
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
