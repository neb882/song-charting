# songcharter

Turns a song file into a Clone Hero song folder (`songcharter chart <song> --out DIR`). It is built for the owner's
friend, who plays Guitar on Expert on a native Windows PC with an RTX 4070.

## Start here

- `docs/PROGRESS.json`: where things stand, what is next, the dead ends and the deferred findings. Read it first,
  and update it when a milestone, a decision or a dead end lands.
- `docs/PIPELINE.md`: how work is run (roles, an order's lifecycle, the gates). Read it before starting agents.
- `docs/DESIGN.md`: the design and the evidence behind each choice. It is long: read the sections you need.
- `docs/work-orders/`: one file per job; `docs/reports/`: each merged order's report.

## Commands

```sh
uv sync --frozen --extra cpu --extra app --extra dev   # or cu126 / cu132 for a GPU; uv 0.13.5 (pyproject pins it)
(cd tools/scan-chart && npm ci)
SONGCHARTER_SCAN_CHART=$PWD/tools/scan-chart/scan.cjs uv run pytest -q -p no:cacheprovider --basetemp=/dev/shm/pt
```

Without uv: `pip install -e ".[dev,separate,drums,bass,sections,preview]"`, with torch from PyTorch's cpu index first.
The friend's install is `packaging/linux/install.sh` (M4-03), and `songcharter doctor` checks a machine.

## Hard rules

- Never look up, quote or reproduce song lyrics.
- Never commit audio, stems, reference charts or model weights.
- No model names or model identifiers in code, docs or commit messages.
- No personal details: the repository is public, so its history keeps everything. That means no names, emails,
  usernames, machine names, home or Windows-profile paths, or lists of what is installed on the owner's or the
  friend's PC. Hardware facts a check needs (GPU model, driver version, RAM, VRAM) are fine. Test fixtures use made-up
  names.
- Deterministic: the same input gives a byte-identical chart (seeded separation, seeded takes).
- User-facing errors are `errors.InputError` or `errors.ToolError`. Exit codes: 0 ok, 1 the gate failed, 2 bad input
  or environment, 3 a bug, with its traceback.

## How work is run

`docs/PIPELINE.md` has the process: the agent roles, an order's path from brief to merge, the gates, and the release
gate. In short:
- size the process to the risk;
- one builder, then one reviewer who also tests the tests;
- a skeptic for a major finding that would change code;
- CI on GitHub as the inspection, and the golden charts when the charting path changes;
- an advisor from a different model before a plan's build and before a release;
- the owner approves anything that goes to the friend.
