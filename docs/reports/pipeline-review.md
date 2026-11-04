# Pipeline review, 2026-11-04

An advisor on a different, more capable model reviewed how songcharter is built with agents: `CLAUDE.md`,
`docs/PIPELINE.md`, `.claude/agents/`, `.claude/workflows/full-review.js`, `docs/PROGRESS.json` and the session's
process log, against Anthropic's published guidance. It was read-only. Twelve findings, most important first, each
with what was done. Model names are left out, as the repository's rules require.

| # | Finding | Done |
|---|---|---|
| 1 | "One heavy job at a time" was prose, and was being broken: two builders each ran a golden run at once (load 4 on 4 cores, 13 of 15 GB used, no swap), because neither could see the other's. Anthropic: what has to happen every time belongs in a hook, a deny rule or a setting, not in prose. | `tools/heavy.sh` queues heavy jobs on one lock, waits naming the holder, and refuses under 5 GB free; `eval/golden.py`'s `run` takes the lock itself; at most two parallel builders. A hook would not have worked here: a cloud session with several repositories doesn't load a repository's hooks or permission rules (finding added to PIPELINE.md, "What enforces a rule"). `tests/test_heavy.py`: 11 tests, and each of 11 breaks of the code fails one. |
| 2 | A hard rule's exception and the in-flight state lived only in the session's scratch folder: M4-10's brief (the lyrics exception) was not a work order, `in_flight` was empty while two orders built, and `next` and the M4 status were stale. | `docs/work-orders/M4-10-lyrics.md` committed with the exception verbatim, and CLAUDE.md's rule points to it; PIPELINE: `in_flight` is updated when an order starts, and a brief that sets a hard rule's limits is committed first; PROGRESS brought up to date. |
| 3 | The dev machine (the reference set, the kept golden folders, the stems, the installs) could not be rebuilt from the repository, and the container is ephemeral. | A measurer wrote the recipe: `eval/README.md`, "Rebuilding the dev machine", with each step's time and disk and the unconfirmed steps marked; `eval/baseline/summary.json` keeps the container's golden summary. Two pieces made by hand are in PROGRESS's deferred list. |
| 4 | Subagents get a five-minute prompt cache even on a subscription, so each wait on a 13-minute suite made the next turn re-send the whole context. | `experimental.cacheTtl: 1h` in every role (ignored while the plan draws on usage credits). The suggested trial of a builder at high effort instead of xhigh is deferred. |
| 5 | The rule against model names contradicted the commit trailer, and kept cheaper models for the inspector and measurer up to memory. | The rule now names the attribution trailer as its one exception. Declined: model aliases in the agent files, since model identifiers stay out of the repository; the orchestrator names the model when it starts an agent. |
| 6 | The scan for personal details and lyrics before a push is a builder's prose step, in a public repository whose history keeps everything. | Deferred to an order: a CI check like `check_no_audio.py`. The names it should look for can't be written in the repository; they go in a CI secret or a file outside it. |
| 7 | A planner on the most capable model at milestone boundaries is justified (both of M4's plans needed a full round of corrections); an orchestrator on it is not. | PIPELINE: from M5, the planner is the most capable model as a fresh agent that reads only the repository; the plan's advisor is a different model from the planner's; an advisor's finding that changes scope gets a skeptic. |
| 8 | `full-review.js` sent every finding to a skeptic, against PIPELINE's routing (majors to a skeptic, test gaps and minor ones to the fixer); skeptics had refuted about 2 of 23 findings. | The workflow routes as PIPELINE does and returns the fixer's list; checked with stub agents. A dry run on a small diff comes before the release gate (PROGRESS, next). |
| 9 | Stalls were judged by eye. | PIPELINE's stall check names the lock's holder file and a `pgrep`; a brief has a time budget. Progress logs with a DONE marker are deferred. |
| 10 | The disk had no floor and no cleanup step (it filled twice). | `tools/heavy.sh` refuses under 5 GB free; a merge deletes the order's scratch and `/dev/shm` folders and notes `df -h /`. The old scratch folders are listed for removal in PROGRESS. |
| 11 | DESIGN.md is stale where it matters (the native-Windows route, a day after the switch to WSL2) and too big for an agent to read whole. | The superseded native plan is marked at §4.3, M4 and Q4. The split into `docs/design/` is deferred to M4-07's doc pass. |
| 12 | Smaller gaps: PIPELINE claimed the harness enforces each role's folders; the golden recipe existed in three copies with different paths. | PIPELINE says what the harness enforces (tools, effort, turns) and what is the role's rule; `eval/README.md` is the one copy of the golden commands. Some work orders' headers still name an inspector where CI now inspects: left as they are. |

Kept unchanged, by the advisor's reading: CLAUDE.md as commands and hard rules only; PIPELINE.md's bracketed
reasons; one builder, one reviewer who tests the tests, a skeptic for majors only; work orders with "Done means" checks
tagged dev, CI or hardware; CI hooks per order; reports committed at merge; short returns with the detail in a file;
the 55-minute check-in; `--threads 2`; the deny list on force pushes; the advisor gates.

The same night the machine restarted mid-run (about 01:29 UTC): `/dev/shm` and every process went, including the two
golden checks; the worktrees, commits and scratch folder survived. One check's finished old side had been copied to
scratch first, so only its new side was rerun.
