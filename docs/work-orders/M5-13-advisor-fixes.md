# M5-13: the advisor's two findings on v0.2.0's candidate (a v0.1 song installed twice; the update under a running server)

**Branch:** `m5-13-advisor-fixes`, from `main` at c71009f (the candidate). **Agent:** `sc-builder`, then `sc-reviewer`.
May push its branch to run CI. **Files:** `songcharter/clonehero.py` (the install into Songs), `packaging/linux/install.sh`
(and `packaging/release/build.sh` only if the template needs it), their tests (`tests/test_clonehero.py`,
`tests/test_install.py`), `packaging/ci/linux.d/75-update.sh` if the update path can show it, `docs/DESIGN.md` §4.5
and the guide (`docs/guide/windows-wsl.md`) where a rule or a step changes. **Time budget:** half a day.

*Written by the orchestrator on 2026-11-06 from the release gate's advisor (a different model) on c71009f; its report
is in the orchestrator's scratch folder and goes into the gate's report.*

## What to build

1. **A song charted under v0.1.0 is installed twice after the update** (the advisor's finding 1, reproduced on the
   test song's name). M5-06 raised the library folder name's cut from 40 to 80 characters, and `clonehero.install`
   replaces an older chart of ours only when `Songs/<the exact name>` exists. So the friend's first re-chart of a song
   with a long name installs a second folder beside v0.1.0's (the same song.ini name and artist), and Clone Hero lists
   the song twice. The install also finds and replaces an older folder of ours for the same song: v0.1.0's cut of the
   same name, or any folder in Songs that carries our marks (charter songcharter, our report.json) with the same
   artist and name; it moves it to `replaced/` as today. Never a folder without our marks; never another song's.
   Tests with made-up names: a v0.1-cut folder of ours is replaced; a person's folder with the same name and no marks
   is not touched; another song of ours with a similar name is not touched.
2. **The update while an old songcharter is running** (the advisor's finding 2, from the code). install.sh deletes
   `app/<old>` and re-syncs `runtime/env` without checking that the old server is closed, so a chart under way on the
   old page can break. Before step 6, if a songcharter server answers (`/api/hello`, the ports `songcharter ui` uses),
   stop with a clear line ("close the songcharter window first, then paste the line again") and exit before anything
   is changed. A test with a stand-in server; the install over a closed one is unchanged.

## Evaluation

- No charting change: no golden run. The suite; CI's 30-install and 75-update green.
- The privacy check before push (`eval/privacy_check.py`).

## Done means

- [dev] The suite; each new test fails when its code is broken.
- [CI] Green on the branch.
- [docs] DESIGN §4.5 (the install's replace rule, the update's running-server check); the guide's update step if
  its words change.

## Report

`<scratchpad>/briefs/m5-13.report.md`: the commits, each item's tests and breaks, the checks' last lines, the CI run.
