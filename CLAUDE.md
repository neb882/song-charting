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

Adopted on 2026-11-03 from Anthropic's guidance on agentic work and from the Overclock project's pipeline (sources
in `docs/PROGRESS.json`). Each rule's reason is in brackets, so a rule can be dropped once its reason no longer
holds.

- **Size the process to the risk.** [On 2026-11-03 a full workflow of about 28 agents found 20 issues, 1 of them
  major.]
  - Do merges, doc edits and small fixes directly.
  - An ordinary change gets `sc-builder`, then `sc-reviewer` and `sc-inspector`.
  - The full workflow (build, review lenses, verify, fix) is for big or risky work only: the Windows release, a new
    engine.
  - Before a big run, read the usage meter (`mcp__usage-meter__usage`, when that mod is loaded) and give the
    workflow a token budget.
- **Agent types** in `.claude/agents/` pin each stage's effort, tools and turn cap. The harness enforces the limits:
  the reviewer and the skeptic cannot edit files. [A reviewer that can edit can quietly fix what it is reviewing.]
  - `sc-builder` builds (xhigh); `sc-reviewer` reviews a diff (high); `sc-skeptic` tries to refute a major finding
    (xhigh); `sc-inspector` compares a commit against the one before it from fresh checkouts (medium);
    `sc-measurer` runs measurements (medium).
  - Choose the model when starting an agent: the largest for builders and skeptics, a smaller one for the inspector
    and measurements. The definitions leave the model out, since model names stay out of the repository, and a
    model named in the call takes precedence over the file.
  - Never set `CLAUDE_CODE_EFFORT_LEVEL`. [It overrides every agent's own effort.]
- **Every brief says what done means:** the check to pass, the evidence to return (commands and their output), and
  what the agent may touch (its worktree or branch). Nobody pushes unless the brief says so. [A check that is not
  written down is judged by "looks done".]
- **Reviewers report correctness only and skip style.** [A reviewer asked to find problems always finds something.]
  - Major findings go to `sc-skeptic` before anyone fixes them. [On 2026-11-03 a skeptic refuted a "major" Windows
    crash that would have cost a pointless fix.]
  - The fixer reproduces each minor finding itself, fixes the cheap ones, and lists the rest under `deferred` in
    `docs/PROGRESS.json`.
- **Short reports:** agents write the full detail to a file and return about 1–2k tokens, with the file's path.
  [Reports of 5–10k tokens filled the orchestrating session's context and forced a compaction.]
- **Long runs:**
  - Commit at milestones.
  - Treat 20 minutes with no agent activity as a stall. [A verifier hung for an hour on 2026-11-03.]
  - Resume from the failure instead of starting over. [A message sent while a workflow ran stopped its agents.]
  - Check in at least every 55 minutes. [The prompt cache lasts about an hour; a later check-in costs far more.]
- **Parallel builds only for jobs whose files do not overlap,** each in its own worktree. [Jobs that share files
  conflict when merged.]

## Release gate

Before anything goes to the friend [the Overclock project's per-change checks missed a flashing chorus that only a
whole-film check caught]:

1. The full suite passes.
2. The golden charts show no UNEXPECTED change on the whole reference set. Run from the release's checkout, with
   the last release checked out at `/dev/shm/golden-old` (`git worktree add --detach /dev/shm/golden-old <commit>`),
   and these set as `eval/README.md` says: `EVAL_DATA`, `SONGCHARTER_GOLDEN`, `SONGCHARTER_AUTOCHART`,
   `SONGCHARTER_ALLIN1_PYTHON` (without it the sections fall back to librosa, and `run` stops with exit 2), and
   `SONGCHARTER_SCAN_CHART` where `tools/scan-chart` has no `node_modules`:
   ```sh
   RERUN=""      # the same for both runs, e.g. RERUN="--rerun bass": engines changed since the kept folders
   EXPECT=none   # or the parts the release changes, e.g. EXPECT=guitar,bass:hard
   rm -rf /dev/shm/golden/old /dev/shm/golden/new &&
   python -m eval.golden run --code /dev/shm/golden-old --out /dev/shm/golden/old --threads 2 $RERUN &&
   python -m eval.golden run --out /dev/shm/golden/new --threads 2 $RERUN &&
   python -m eval.golden diff /dev/shm/golden/old /dev/shm/golden/new --expect $EXPECT
   ```
   Each run must exit 0, and then the diff must exit 0 (the `&&` stops at the first that does not). A run takes
   about 6.5 min. `--rerun` adds to each of the two runs, per song, about half a minute for drums or bass, 1.5–3 min
   for sections and 3.5–11 min for the guitar. A run warns, and the diff fails, when an engine's code changed since
   the kept folders were made and that engine was not rerun in both. Read `report.md`: the pooled F1 per part, and the
   engines that ran.
3. The test song runs end to end with the gate ok, and its preview has been looked at.
4. The owner approves the release.
