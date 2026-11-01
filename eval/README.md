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

## The tools under test

| tool | code | weights | instruments |
|---|---|---|---|
| [autochart](https://github.com/dvar0/autochart) (Fretformer 2) | AGPL-3.0 | CC BY-NC-SA 4.0 | lead guitar |
| [chartgen](https://github.com/Mechazawa/chartgen) | MIT | separator weights: licence unknown | guitar, bass, drums |
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
AC_DEVICE=cuda STRUM_DEVICE=cuda eval/drive.sh     # every tool on every song, then eval/data/runs/SCORECARD.md
```

Check that each tool really ran on the GPU: the run logs name the device. autochart falls back to CPU by
itself if its CUDA provider fails to load.
