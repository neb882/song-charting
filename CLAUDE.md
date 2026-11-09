# songcharter

Turns a song file into a Clone Hero song folder (`songcharter chart <song> --out DIR`). It is built for the owner's
friend, who plays Guitar on Expert on a Windows PC with an RTX 4070; v0.1 runs there in WSL2.

## Start here

- `docs/PROGRESS.json`: where things stand, what is next, the dead ends and the deferred findings. The orchestrator
  reads it at the start and updates it when a milestone, a decision or a dead end lands; a builder reads it only when
  its brief says so.
- `docs/PIPELINE.md`: how work is run (roles, an order's lifecycle, the gates): the orchestrator's. Read it before
  starting agents.
- `docs/DESIGN.md`: the design and the evidence behind each choice. It is long: read the sections you need.
- `docs/work-orders/`: one file per job; `docs/reports/`: each merged order's report.

## Commands

```sh
uv sync --frozen --extra cpu --extra app --extra dev   # or cu126 / cu132 for a GPU; uv 0.13.5 (pyproject pins it)
(cd tools/scan-chart && npm ci)
SONGCHARTER_SCAN_CHART=$PWD/tools/scan-chart/scan.cjs uv run python -m pytest -q -p no:cacheprovider --basetemp=/dev/shm/pt
```

`python -m pytest`, not `pytest`: the tests import `eval`, which only the module form puts on the path (CI runs it so).
If `uv --version` is not 0.13.5 and `uv self update` refuses (uv not installed by its own installer), use the
installer for that version: `curl -LsSf https://astral.sh/uv/0.13.5/install.sh | sh`.

Without uv: `pip install -e ".[dev,separate,drums,bass,sections,preview]"`, with torch from PyTorch's cpu index first.
The friend's install is `packaging/linux/install.sh` (M4-03), and `songcharter doctor` checks a machine.

On a dev machine that agents share, run every heavy job (the full suite, a golden run, an install, a real chart) as
`tools/heavy.sh <command>`: it queues them on one lock, so two never run at once. `python -m eval.golden run` takes
the lock itself.

## Hard rules

- Never look up, quote or reproduce song lyrics. The one exception, scripts reading the reference charts' lyric events
  for timing only, has its limits in `docs/work-orders/M4-10-lyrics.md`.
- Never commit audio, stems, reference charts or model weights.
- No names or identifiers of the AI assistant models that build songcharter in code, docs or commit messages, apart
  from the attribution trailer the session's instructions require on each commit. The machine-learning models
  songcharter runs (Demucs, Fretformer 2, wav2vec 2.0, ...) are named wherever needed.
- No personal details: the repository is public, so its history keeps everything. That means no names, emails,
  usernames, machine names, or home, Windows-profile or folder paths, and nothing about the owner's or the friend's PC
  beyond what a check needs, written as the requirement: the GPU model and its VRAM, the RAM, a driver "new enough for"
  a lane, Smart App Control on. No exact driver, Windows or WSL versions of their PCs, and nothing installed on them.
  Test fixtures use made-up names, paths and versions.
- Deterministic: the same input gives a byte-identical chart (seeded separation, seeded takes).
- User-facing errors are `errors.InputError` or `errors.ToolError`. Exit codes: 0 ok, 1 the gate failed, 2 bad input
  or environment, 3 a bug, with its traceback.

## How work is run

`docs/PIPELINE.md` has the process: the agent roles, an order's path from brief to merge, the gates, and the release
gate. In short:
- size the process to the risk;
- one builder, who runs the affected tests and says which test covers each change, then one reviewer who also tests
  the tests by breaking them;
- a skeptic for a major finding that would change code;
- CI on GitHub on every branch as the inspection (the full suite, green before a merge), and the golden charts when
  the charting path changes;
- an advisor from a different model before a plan's build and before a measurement report's results are closed (at a
  release, only with the full review);
- bars fixed before the numbers, with one primary measure each;
- a friend release when the friend has played the last one, or for a fix he waits on; between them, main carries
  internal candidates;
- the owner approves anything that goes to the friend.
