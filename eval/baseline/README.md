# The dev container's golden baseline

`summary.json` is `python -m eval.golden run`'s summary of the reference set, built in the dev container on
2026-11-03 from main at 072ed20 (every level, one guitar take, CPU, 2 threads, `--rerun guitar`). It holds, per song,
part and difficulty, the onsets, notes, scan-chart's track hash and the F1 against the human charts; no audio, charts
or lyrics. The paths in its `run` section are the container's.

The container is gone once its session ends, so this is the record of what its charts were. A rebuilt machine
(`eval/README.md`, "Rebuilding the dev machine") makes its own base and compares changes against that one: its
torch and library builds may move hashes. Diffing its base against this summary shows how far its charts are from
the container's.
