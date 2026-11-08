# eval/m7: M7-01's measurement scripts

The scripts of M7-01's three parts (docs/reports/M7-01-measure.md), as the measurers ran them on 2026-11-07/08, kept
so a build order's bar can be measured the same way. Paths are placeholders (`$DEV` the dev machine's data folder,
`<scratchpad>` the measurer's output folder, `<wt>` and `<checkout>` worktrees, `<shm>` /dev/shm): set them before
running. Each script's first lines say what it reads and prints. They print numbers only: never a title, an artist,
a charter, an md5 or a lyric (the 20-song set's songs are s01-s13, read from its own list at run time).

- `A/`: part A (HOPO modes, taps, sustains, repeats, open notes): `patch_arm.py` patches a worktree per arm,
  `run_arm.sh`/`gr.sh` build and score an arm, `analyze.py` and `report.py` the tables.
- `B/`: part B (silent stems, the bass, solos, drumless stretches, drums): `common.py` loads the notes, one script per
  question (`ba.py` .. `be_cand.py`), `make_report.py` the tables.
- `C/`: part C (the take margin): `gen_one.py`/`gen_all.sh` the CPU takes, `margin.patch` and `build_song.py` the
  splice arms, `windows.py`, `analyze.py`, `deltas.py` and `tables.py` the numbers.
