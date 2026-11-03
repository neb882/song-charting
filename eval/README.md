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
