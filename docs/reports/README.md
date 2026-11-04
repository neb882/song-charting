# Reports

Each merged order's full report, and the research reports DESIGN.md cites, kept so the evidence can be re-checked
later (`docs/PIPELINE.md`, the merge step). A report is copied here at its order's merge, after a scan for personal
details and lyrics.

Paths in a report that start with `/tmp/claude-0/…/scratchpad` or `/dev/shm` name the building session's own
scratch files: they were never in the repository and no longer exist. Commit hashes refer to the branch as it was
built; a merge commit on main names the result.

| report | what |
|---|---|
| `golden-charts.md` | `eval/golden.py`: the baseline, determinism, a deliberate change caught, and the fixes after review |
| `M4-00-plan.md` | the M4 planning job: the native-Windows research, then the WSL2 re-plan and its sources |
| `M4-01-lanes.md` | the torch lanes and allin1's locked project, and the torchaudio decision |
| `M4-02-device.md` | `doctor`, the device checks and the memory sampler; the golden run that moved no chart |
| `M4-03-install.md` | the WSL install line, the shortcut and the uninstall, and the review fixes |
| `M4-05a-ci-skeleton.md` | the CI workflow and its hook runners |
| `pipeline-review.md` | an advisor's review of how work is run (2026-11-04), finding by finding, with what was done |
| `takes-experiment.md`, `takes-experiment-verifier.md` | spliced guitar takes against one take, and the verifier's corrections (which win where they differ) |
| `strumming-research.json` | the pick-noise detector for sparse guitar stretches, and why no fill was built |
