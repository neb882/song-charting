# The stress set's baseline

`summary.json` is `python -m eval.golden run`'s summary of the stress set (`eval/stress.json`, `eval/README.md`
"Stress songs"), built on the dev machine on 2026-11-05 from `main` at fbd9751 (wave 1's `main`, after M4-11):
every level, one guitar take, CPU, 2 threads, the kept folders made cold. `stress_scores.json` is `eval/stress.py
score`'s scoring of that run: our charts against every human chart of each song, and the other human charts against
the primary, with the feel measures. Both hold counts, hashes and scores only: no audio, chart or lyric, and no
md5, title, artist or charter of the packages (`eval/stress.py baseline` cut every path to its last part and checked
that none of the local list's values is left).

The stress check of a later change is `python eval/stress.py compare eval/baseline/stress <its run>`: exit 1 when a
part's F1@50 against the primary chart falls by more than 0.01. From wave 3 on, an order compares with a stress run
of its own merge base, kept beside `stress-base`, not with this one. A rebuilt machine makes its own baseline, as for
the golden set: its torch and library builds may move hashes.
