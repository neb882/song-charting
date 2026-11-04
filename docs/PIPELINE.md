# How work is run

How songcharter is built with agents. CLAUDE.md has the commands and the hard rules; this file has the process.
Adopted on 2026-11-03 from Anthropic's guidance on agentic work and from the Overclock project's pipeline (sources
in `docs/PROGRESS.json`), and revised on 2026-11-04 after an advisor's review (`docs/reports/pipeline-review.md`).
Each rule's reason is in brackets, so a rule can be dropped once its reason no longer holds.

## Roles

The agent types live in `.claude/agents/`. Each definition pins its effort, its tools, its turn cap and a one-hour
prompt cache, and the harness enforces them. [A reviewer that can edit can quietly fix what it is reviewing.] The
folders a role may write to are the role's own rule, not the harness's.
- **The one-hour cache** (`experimental.cacheTtl`) is for agents that wait on jobs longer than five minutes. [A
  subagent's cache otherwise lasts five minutes, so each wait on a 13-minute suite made its next turn re-send its
  whole context.] Claude Code ignores it while the plan draws on usage credits.
- **The model** is left out of the definitions, since model names stay out of the repository: it is chosen when the
  agent is started, and a model named in the call takes precedence over the file.
- **A role file** loads when `.claude/agents/` existed at the session's start; otherwise start a general agent and
  tell it to follow the file.

| Role | Does | Effort | Model to start it on | Can edit |
|---|---|---|---|---|
| orchestrator (the main session) | writes briefs, merges, keeps PROGRESS | session's | the largest | yes |
| planner | turns a milestone into work orders | xhigh | the most capable, as a fresh agent that reads only the repository | its plan branch only |
| `sc-builder` | builds one order | xhigh | the largest | its worktree only |
| `sc-reviewer` | reviews a diff, testing the tests | high | the largest | no |
| `sc-skeptic` | tries to refute a major finding | xhigh | the largest | no |
| `sc-inspector` | facts from fresh checkouts | medium | a smaller one | no |
| `sc-measurer` | measurements and lookups | medium | a smaller one | scratch only |
| advisor | a second opinion at two gates | xhigh | a different model from the one that wrote what it reviews | no |

Never set `CLAUDE_CODE_EFFORT_LEVEL`. [It overrides every agent's own effort.]

**What enforces a rule.** In a cloud session with several repositories, Claude Code reads only the plugin keys of each
repository's `.claude/settings.json`: its permission rules and hooks don't apply there (code.claude.com/docs/en/settings,
"Settings in cloud sessions"). So a rule that must hold every time lives in code or in CI: the heavy-job lock in
`tools/heavy.sh` and `eval/golden.py`, the checks in `packaging/ci/`. The settings file's deny list on force pushes is
a backstop for single-repository and local sessions. [If something has to happen every time, Anthropic's guidance
is to enforce it rather than write it down; on 2026-11-04 two builders each ran a golden run at once, against a
written rule, because neither could see the other's.]

## Size the process to the risk

[On 2026-11-03 a full workflow of about 28 agents found 20 issues, 1 of them major. A four-lens re-review of
reviewed, merged work then found 3 real issues, none of them major.]

- **Direct:** merges, doc edits and small fixes.
- **An order** (the normal case): the lifecycle below.
- **The full workflow** (build, review lenses, a skeptic per major finding, fix): big or risky integrations only. It
  is saved as `.claude/workflows/full-review.js`, and runs once over an integrated release before its hardware test.
  It routes findings as an order's review does (step 4 below): the minor ones and the test gaps go to the fixer
  unverified.
- Before a big run, read the usage meter (`mcp__usage-meter__usage`, when that mod is loaded), and give a workflow a
  token budget.

## An order, from brief to merge

1. **The brief** is a work order in `docs/work-orders/`, or a short brief for a small job. It says:
   - the intent;
   - the files it may and may not touch;
   - the spec;
   - what done means: each check with its command, marked CI, dev container or hardware;
   - its branch and worktree;
   - a time budget, after which the builder stops and reports.

   The agent role holds the standing rules, so a brief carries only what is specific to the job. [A check that is
   not written down is judged by "looks done".]
   - A brief that sets a hard rule's limits (an owner's exception) is committed as a work order before the build.
   - When an order starts, add it to PROGRESS's `in_flight`: its branch, worktree, stage and report file. [On
     2026-11-04 two orders were building while `in_flight` was empty, and one of them carried a hard-rule exception
     that only its brief in the session's scratch folder held: a fresh session could not have picked either up.]
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
   - Update PROGRESS (the order leaves `in_flight`), and append to the later orders anything this one deferred to
     them.
   - Remove the worktree, and delete the order's scratch and `/dev/shm` folders; note `df -h /` in the merge's
     report. [The disk filled twice on 2026-11-03.] Remote branches are deleted by the owner; a session can't.

## Gates

- **A plan, before its build:** the advisor, a different model from the planner's, reviews the work orders. It
  advises; it doesn't direct, and a finding of its that changes an order's scope gets a skeptic like a review's major.
  [A mistake found in an order costs minutes; one found after a build costs hours. On 2026-11-03 it moved the GPU
  test from last to first.]
  - From M5 on, the planner is the most capable model, as a fresh agent that reads only the repository and the
    owner's goals, writes the orders and PROGRESS to a plan branch, and ends; the orchestrator runs the waves.
    [Both of M4's plans needed a full round of the advisor's corrections (11, then 12, all accepted). Planning is the
    cheap phase, and a fresh agent also tests that the repository holds everything a new session needs.]
- **A release, before the friend gets it:**
  1. The full suite passes.
  2. The golden charts show no UNEXPECTED change on the whole reference set: `eval/README.md`'s commands (Golden
     charts), run from the release's checkout with the last release checked out at `/dev/shm/golden-old` and every
     variable it names set. Read `report.md`: the pooled F1 per part, and the engines that ran.
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
- **Heavy jobs** (the full suite, a golden run, a full install, a real chart) run one at a time, as
  `tools/heavy.sh <command>`; a golden run takes the lock itself. The script waits behind another agent's job, naming
  it, and refuses to start with under 5 GB of disk free. [A golden run's guitar engine was killed for memory while two
  suites ran beside it on this 4-core, 15 GB machine.]
- **Parallel builds** only for orders whose files don't overlap, each in its own worktree, and at most two at once.
- **Stalls:** a stall is 20 minutes with no commit, no new line in the agent's output and no heavy job running. Check
  the job with `cat /dev/shm/songcharter-heavy.lock.who` and `pgrep -af 'pytest|eval.golden|songcharter.cli'`; a long
  command alone isn't one. [A verifier hung for an hour on 2026-11-03. Twice, a quiet log during a long golden run
  was a false alarm.]
- Resume from the failure instead of starting over. [A message sent while a workflow ran stopped its agents.]
- Check in at least every 55 minutes. [The prompt cache lasts about an hour; a later check-in costs far more.]
