# M5-12: v0.2.0's release gate fixes (the full review's code findings)

**Branch:** `m5-12-gate-fixes`, from `main` at 77c3c8e (the candidate the review read). **Agent:** `sc-builder`, then
`sc-reviewer`. May push its branch to run CI. **Files:** `songcharter/__init__.py`, `pyproject.toml`, `uv.lock`,
`packaging/release/build.sh`, `packaging/ci/*` only as the version check needs, `songcharter/cache.py`,
`songcharter/pipeline.py` (the work folder lookup), `songcharter/assemble.py` (`OUTPUT_FILES`, `_foreign`, `_install`;
`_octave_pass` itself untouched), `songcharter/ui/server.py` and `songcharter/ui/static/app.js` (the running-instance check
and the notice's words), their tests, `eval/stress.py` only if a scrub test shows a real gap, `tests/test_eval_stress.py`.
**Time budget:** a day.

*Written by the orchestrator on 2026-11-06 from the full review workflow over v0.1.0...77c3c8e (four lenses, a
skeptic per major finding; the findings' text is in the orchestrator's scratch folder and its report). The docs
findings are fixed on a branch of their own.*

## What to build

1. **The version (confirmed major, three lenses).** The candidate says 0.1.0 (`songcharter/__init__.py`,
   `pyproject.toml`, `uv.lock`), so a v0.2.0 built from it shows the friend "0.2.0 is out (you have 0.1.0)" on every
   start after updating, and pasting the line reinstalls the same build. Bump all three to 0.2.0 (`uv lock`, then
   `uv lock --check` as 10-lanes.sh runs it). `build.sh <version>` refuses (exit 2, a clear message) a version whose
   dotted-integer part differs from HEAD's `__version__` or pyproject's version; CI's `<version>-ci-<sha>` builds
   stay allowed. Check the CI hooks that hard-code `0.1.0-ci-<sha>` (50-e2e.sh, 70-release.sh) and 75-update.sh's
   old side (the update path from an older install must still be tested: an older version than HEAD's). A test that
   fails when the check is removed.
2. **The work folder after M5-06's name change** (correct-2, install-2). `cache.work_folder` names the folder from
   `safe_name(stem)`, which M5-06 changed for stems over 40 units, so a v0.1 song's cache (separation, sections, the
   guitar takes) is not found on its first re-chart after the update: on the friend's GPU about 15 minutes of takes
   for a 7-minute song, and the old folder stays on disk. On a miss, reuse an existing `work/*-<key>` whose marker
   holds that key (the same file), before making the new name; the page's upload name the same way if it matters to
   the lookup. Tests with made-up names: a v0.1-style folder is found and reused; a folder with the same suffix but
   another key is not; no folder: today's name.
3. **A person's own background** (install-3). M4-11 put `background.png/.jpg/.jpeg` in `OUTPUT_FILES`, so a re-chart
   into a folder songcharter made now deletes a background.* the person put there (v0.1.0 refused with "holds what a
   build does not write"). A background.* counts as ours only when the previous build recorded writing it (its
   report.json, or another record the build already keeps); otherwise it is foreign as before (v0.1.0's refusal). A
   test: a person's background.png in an earlier build's folder makes the build refuse and survives; one our build
   wrote is replaced or removed as today.
4. **The running old server after an update** (install-4). The notice says "close this window", which reads as the
   browser; and `songcharter ui` reuses any running instance whose `/api/hello` says `songcharter`, so after the
   update the Start-menu launch reopens the old version's page (still showing the notice). Word the notice as the
   guide does ("close the songcharter window"); and when the running instance's version differs from this launch's,
   don't reuse it: stop it if the server already has a way to be stopped, else say plainly that the old window must
   be closed (exit 2, `InputError`). Tests with a stand-in old instance.
5. **Test gaps** (tests-4, tests-3): a unit test of `_octave_pass` when the second pass raises `InputError` (auto keeps
   the first grid with the tempo warning; forced `grid_octave 2` raises an `InputError`, never an AttributeError);
   the stress baseline scrub's test covers the alts' md5s and charters, case, dict keys and the leftover-path check
   (the reviewer's four breaks each fail a test).

## Evaluation

- **Golden:** item 2 changes only where a work folder is found and item 3 only the output folder's check, so the
  orchestrator reruns the candidate's golden charts against v0.1.0's after the merge (the gate's run): every chart
  identical to the 77c3c8e candidate's. Your check: `--expect none` of 77c3c8e against your branch on two songs
  (`--songs kimochi_warui,take_me_out`), warm.
- **The update path:** CI's 75-update.sh green; and by hand in a temporary HOME: a v0.1-style work folder for a
  made-up long stem is reused by a chart of the same file (the log shows no engine ran).

## Done means

- [dev] The suite; each new test fails when its code is broken; the two-song golden diff exit 0.
- [CI] Green on the branch, with build.sh's check and the update path.
- [docs] DESIGN where a rule changed (the work folder lookup, the background rule, the running-instance check); the
  README's update section if its words change.

## Limits

- No change to charting. No new dependency. Nothing about the stress set's songs in anything committed.

## Report

`<scratchpad>/briefs/m5-12.report.md`: the commits, each item's tests and breaks, the checks' last lines, the CI run.
