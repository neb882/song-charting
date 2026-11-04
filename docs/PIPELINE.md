# How work is run

How songcharter is built with agents. CLAUDE.md has the commands and the hard rules; this file has the process.
Adopted on 2026-11-03 from Anthropic's guidance on agentic work and from the Overclock project's pipeline (sources
in `docs/PROGRESS.json`). Each rule's reason is in brackets, so a rule can be dropped once its reason no longer
holds.

## Roles

The agent types live in `.claude/agents/`. Each definition pins its effort, its tools and its turn cap, and the
harness enforces those limits. [A reviewer that can edit can quietly fix what it is reviewing.] The definitions
leave the model out, since model names stay out of the repository: the model is chosen when the agent is started,
and a model named in the call takes precedence over the file.

| Role | Does | Effort | Model to start it on | Can edit |
|---|---|---|---|---|
| orchestrator (the main session) | writes briefs, merges, keeps PROGRESS | session's | the largest | yes |
| planner | turns a milestone into work orders | xhigh | the largest | its plan branch only |
| `sc-builder` | builds one order | xhigh | the largest | its worktree only |
| `sc-reviewer` | reviews a diff, testing the tests | high | the largest | no |
| `sc-skeptic` | tries to refute a major finding | xhigh | the largest | no |
| `sc-inspector` | facts from fresh checkouts | medium | a smaller one | no |
| `sc-measurer` | measurements and lookups | medium | a smaller one | scratch only |
| advisor | a second opinion from a different model at two gates | xhigh | a different model | no |

Never set `CLAUDE_CODE_EFFORT_LEVEL`. [It overrides every agent's own effort.]

## Size the process to the risk

[On 2026-11-03 a full workflow of about 28 agents found 20 issues, 1 of them major. A four-lens re-review of
reviewed, merged work then found 3 real issues, none of them major.]

- **Direct:** merges, doc edits and small fixes.
- **An order** (the normal case): the lifecycle below.
- **The full workflow** (build, review lenses, verify, fix): big or risky integrations only. It is saved as
  `.claude/workflows/full-review.js`, and runs once over an integrated release before its hardware test.
- Before a big run, read the usage meter (`mcp__usage-meter__usage`, when that mod is loaded), and give a workflow a
  token budget.

## An order, from brief to merge

1. **The brief** is a work order in `docs/work-orders/`, or a short brief for a small job. It says:
   - the intent;
   - the files it may and may not touch;
   - the spec;
   - what done means: each check with its command, marked CI, dev container or hardware;
   - its branch and worktree.

   The agent role holds the standing rules, so a brief carries only what is specific to the job. [A check that is
   not written down is judged by "looks done".]
2. **`sc-builder`** builds in its own worktree.
   - It checks its own tests by breaking the code they cover.
   - It runs the golden charts when the change touches the charting path.
   - It pushes its branch to run CI, and writes its full report to a file.
3. **`sc-reviewer`** reviews the diff for correctness only, and tests the tests: it breaks each new check a few ways.
   [A reviewer asked to find problems always finds something; on 2026-11-03, two of three findings that slipped past
   single reviewers were checks whose own tests could be gutted unnoticed.]
4. **Findings:**
   - **A major finding that would change code** goes to `sc-skeptic` first. [On 2026-11-03 a skeptic refuted a
     "major" Windows crash that would have cost a pointless fix.]
   - **A test gap the reviewer proved by breaking the code** goes straight to the fixer: the fix is the test, which
     is never wasted.
   - **Minor findings:** the fixer reproduces each one, fixes the cheap ones, and lists the rest under `deferred` in
     PROGRESS.
   - **The fixer** is the order's builder, resumed with its context.
5. **The inspection** is CI on GitHub: a fresh checkout on a clean runner, reporting pass or fail. Read its log to
   make sure the order's own hook ran and wasn't skipped. Golden charts run locally, by the builder or by
   `sc-inspector`, when the charting path changed, since CI can't run them.
6. **The merge** is `--no-ff`, with a message that says what the order did and how it was checked. Then:
   - **The report:** copy the builder's report into `docs/reports/<order>.md`, after scanning it for personal details
     and lyrics. [Reports left in the session's scratch folder vanish with the container; DESIGN.md once cited
     evidence nobody could re-check.]
   - Update PROGRESS, and append to the later orders anything this one deferred to them.
   - Remove the worktree. Remote branches are deleted by the owner; a session can't.

## Gates

- **A plan, before its build:** the advisor, a different model, reviews the work orders. It advises; it doesn't
  direct. [A mistake found in an order costs minutes; one found after a build costs hours. On 2026-11-03 it moved
  the GPU test from last to first.]
- **A release, before the friend gets it:**
  1. The full suite passes.
  2. The golden charts show no UNEXPECTED change on the whole reference set. Run them from the release's checkout,
     with the last release checked out at `/dev/shm/golden-old` (`git worktree add --detach /dev/shm/golden-old
     <commit>`). Set these as `eval/README.md` says:
     - `EVAL_DATA`, `SONGCHARTER_GOLDEN` and `SONGCHARTER_AUTOCHART`;
     - `SONGCHARTER_ALLIN1_PYTHON` (without it the sections fall back to librosa, and `run` stops with exit 2);
     - `SONGCHARTER_SCAN_CHART`, where `tools/scan-chart` has no `node_modules`.
     ```sh
     RERUN=""      # the same for both runs, e.g. RERUN="--rerun bass": engines changed since the kept folders
     EXPECT=none   # or the parts the release changes, e.g. EXPECT=guitar,bass:hard
     rm -rf /dev/shm/golden/old /dev/shm/golden/new &&
     python -m eval.golden run --code /dev/shm/golden-old --out /dev/shm/golden/old --threads 2 $RERUN &&
     python -m eval.golden run --out /dev/shm/golden/new --threads 2 $RERUN &&
     python -m eval.golden diff /dev/shm/golden/old /dev/shm/golden/new --expect $EXPECT
     ```
     - Each run must exit 0, and then the diff must exit 0; the `&&` stops at the first that doesn't.
     - A run takes about 6.5 min. `--rerun` adds to each of the two runs, per song, about half a minute for drums or
       bass, 1.5–3 min for sections and 3.5–11 min for the guitar.
     - A run warns, and the diff fails, when an engine's code changed since the kept folders were made and that
       engine was not rerun in both.
     - Read `report.md`: the pooled F1 per part, and the engines that ran.
  3. The full review workflow has run over the integrated release, and its confirmed findings are fixed.
  4. The test song runs end to end with the gate ok, and someone has looked at its preview.
  5. The advisor reviews the release candidate.
  6. The owner approves the release.

  [The Overclock project's per-change checks missed a flashing chorus that only a whole-film check caught.]

## Briefs and reports

- **Reports:** an agent writes its full detail to a file and returns about 1–2k tokens, with the file's path.
  [Reports of 5–10k tokens filled the orchestrating session's context and forced a compaction.]
- **Every brief also gives:**
  - the session's paths (Python, scratch);
  - the commit trailer lines the session's instructions name;
  - the disk and memory budget when other agents run at the same time.

## Long runs

- Commit at milestones.
- **Stalls:** treat 20 minutes with no commit, no log line and no running job as a stall; a long command alone isn't
  one. [A verifier hung for an hour on 2026-11-03. Twice, a quiet log during a long golden run was a false alarm.]
- Resume from the failure instead of starting over. [A message sent while a workflow ran stopped its agents.]
- Check in at least every 55 minutes. [The prompt cache lasts about an hour; a later check-in costs far more.]
- **Parallel builds** only for jobs whose files don't overlap, each in its own worktree, and never two heavy jobs (a
  full install, the suite, a golden run) at once on this 4-core, 15 GB machine. [A golden run's guitar engine was
  killed for memory while two suites ran beside it.]
