# songcharter

Turns a song file into a Clone Hero song folder (`songcharter chart <song> --out DIR`). It is built for the owner's
friend, who plays Guitar on Expert on a native Windows PC with an RTX 4070.

## Start here

- `docs/PROGRESS.json`: where things stand, what is next, the dead ends and the deferred findings. Read it first,
  and update it when a milestone, a decision or a dead end lands.
- `docs/DESIGN.md`: the design and the evidence behind each choice. It is long: read the sections you need.

## Commands

```sh
pip install -e ".[dev,separate,drums,bass,sections,preview]"
(cd tools/scan-chart && npm ci)
SONGCHARTER_SCAN_CHART=$PWD/tools/scan-chart/scan.cjs python -m pytest -q -p no:cacheprovider --basetemp=/dev/shm/pt
```

## Hard rules

- Never look up, quote or reproduce song lyrics.
- Never commit audio, stems, reference charts or model weights.
- No model names or model identifiers in code, docs or commit messages.
- Deterministic: the same input gives a byte-identical chart (seeded separation, seeded takes).
- User-facing errors are `errors.InputError` or `errors.ToolError`. Exit codes: 0 ok, 1 the gate failed, 2 bad input
  or environment, 3 a bug, with its traceback.

## How work is run

Adopted on 2026-11-03 from Anthropic's guidance on agentic work (sources in `docs/PROGRESS.json`).

- **Size the process to the risk.**
  - Do merges, doc edits and small fixes directly.
  - An ordinary change gets one builder plus one fresh reviewer.
  - The full workflow (build, review lenses, verify, fix) is for big or risky work only: the Windows release, a new
    engine.
  - Before a big run, read the usage meter (`mcp__usage-meter__usage`, when that mod is loaded) and give the
    workflow a token budget.
- **Every brief says what done means:** the check to pass, the evidence to return (commands and their output), and
  what the agent may touch (its worktree or branch). Nobody pushes unless the brief says so.
- **Reviewers report correctness only and skip style.**
  - Major findings get an adversarial verifier.
  - The fixer reproduces each minor finding itself, fixes the cheap ones, and lists the rest under `deferred` in
    `docs/PROGRESS.json`.
- **Effort per stage:** builders and verifiers at xhigh. Docs, measurements and lookups at medium, or on Sonnet.
- **Short reports:** agents write the full detail to a file and return about 1–2k tokens, with the file's path.
- **Long runs:**
  - Commit at milestones.
  - Treat 20 minutes with no agent activity as a stall.
  - Resume from the failure instead of starting over.
- **The owner approves anything that goes to the friend** before it is sent.
