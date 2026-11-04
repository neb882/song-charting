# Reports

Each merged order's full report, and the research reports DESIGN.md cites, kept so the evidence can be re-checked
later (`docs/PIPELINE.md`, the merge step). A report is copied here at its order's merge, after a scan for personal
details and lyrics.

Paths in a report that start with `/tmp/claude-0/…/scratchpad` or `/dev/shm` name the building session's own
scratch files: they were never in the repository and no longer exist. Commit hashes refer to the branch as it was
built; a merge commit on main names the result. On 2026-11-04 the history was rewritten to remove details of the
owner's and the friend's PCs, which changed every commit's hash: the hashes in these files were mapped to the new
ones then, but the CI runs they link still name the old ones.

| report | what |
|---|---|
| `golden-charts.md` | `eval/golden.py`: the baseline, determinism, a deliberate change caught, and the fixes after review |
| `M4-00-plan.md` | the M4 planning job: the native-Windows research, then the WSL2 re-plan and its sources |
| `M4-01-lanes.md` | the torch lanes and allin1's locked project, and the torchaudio decision |
| `M4-02-device.md` | `doctor`, the device checks and the memory sampler; the golden run that moved no chart |
| `M4-03-install.md` | the WSL install line, the shortcut and the uninstall, and the review fixes |
| `M4-04-ui-server.md` | `songcharter ui`, `chart --events` and cancel; the review's six fixes and the LAN fallback closed |
| `M4-05-ci.md` | CI end to end in Ubuntu 26.04: the install killed and resumed, doctor, a chart, the page and a cancel, offline, both uninstalls; the review's fixes and the figures |
| `M4-05a-ci-skeleton.md` | the CI workflow and its hook runners |
| `M4-06-ui-results.md` | the Done screen, the install into Clone Hero's Songs folder, diagnostics and the lyrics box; the review's fixes |
| `M4-07-release.md` | the friend's guide, NOTICE.txt with each licence checked at its source, the release build and its CI check; the review's fixes |
| `M4-10-lyrics.md` | lyrics from pasted text: five aligners measured on the references (timings only), the build, and the review's fixes |
| `rc-advisor.md` | the advisor's review of the v0.1 release candidate as a whole, from the friend's side, and the three skeptics' reproductions |
| `rc-fixes.md` | the release candidate's fixes (the guide's timings, the guitar's GPU-failure message, doctor's problems on the page, M4-08's release-first order and checks) and their review |
| `release-gate.md` | the release gate for v0.1: the full review, the golden charts and the test song; the GPU smoke test on the owner's 5070; the gate's fixes and their second review |
| `pipeline-review.md` | an advisor's review of how work is run (2026-11-04), finding by finding, with what was done |
| `takes-experiment.md`, `takes-experiment-verifier.md` | spliced guitar takes against one take, and the verifier's corrections (which win where they differ) |
| `strumming-research.json` | the pick-noise detector for sparse guitar stretches, and why no fill was built |
