# Handoff to a new session (2026-11-05)

The session that ran M3 and M4 ends here. Its machine restarted overnight and its scheduled check-ins were refused
("access denied"), so unattended work stalled; the owner chose to continue in a new session with this repository
alone (a single-repository session reads `.claude/settings.json`). Read CLAUDE.md, docs/PROGRESS.json and
docs/PIPELINE.md first; this note adds what only the old session knew.

## Where things stand

- **v0.1.0** is published as a pre-release. The friend is running M4-08 part B; when his diagnostics zip and notes
  arrive, read them as M4-08 says and write part B's results (docs/work-orders/M4-08-results.md has part A's).
- **M4-11** (album art and a background image) is built on branch `m4-11-art`, reviewed (no major), with its review
  fixes being made by the old session. The old session merges it into main when CI is green.
- **M5** (the next version, 0.2.0): the plan is on branch `m5-plan`, written by a planner on the most capable model,
  reviewed by an advisor on a different model, three scope changes checked by skeptics, and amended on all of them
  (docs/reports/m5-plan-review.md). The old session merges the amended plan into main when it is done.
- **Wait for the old session's message** saying both merges are done before touching `m4-11-art`, `m5-plan` or main's
  PROGRESS. Then run M5's waves as docs/work-orders/M5-00-plan.md sets them, at most two builders at once.

## The owner's decisions (2026-11-05)

Version 0.2.0; M4-11 merged first; an update notice with a Copy button rather than a one-click updater, with
pre-releases counting as new; a GPU take that fails retried on the CPU by default (its memory measured at the gate);
the stress set as below; the lyrics weights stay a first-use download; the planner's album placeholder; small
backgrounds kept as they are, not upscaled. The owner also asked that the version follow the games' conventions
(docs/reports/charting-conventions.md) and think about how a chart feels to play (docs/reports/feel.md).

## The dev machine (rebuild it first)

The old container's scratch held what the evaluation needs and none of it is in the repository (CLAUDE.md: no audio,
stems or reference charts). Rebuild it with eval/README.md, "Rebuilding the dev machine": the Python environment, the
reference set, scan-chart, autochart and its models, allin1's environment, then a golden base on main (compare it with
eval/baseline/summary.json). Run heavy jobs through tools/heavy.sh.

## The stress set (M5-09)

The new session's first message from the old one lists the human charts to fetch from Chorus Encore (by hash) and
asks the owner to upload his audio for the songs: they are not in the repository and must not be. Human charts that
carry lyrics are read only by timing scripts that print numbers (docs/work-orders/M4-10-lyrics.md); the owner's own
lyrics text for the lyrics check is uploaded by him as a file and never printed.

## Limits for unattended work (the owner's, unchanged)

No release published without the owner; no session on the owner's PC unless he asks; no force push or branch
delete; no usage credits; pause new work at 70% of the weekly usage.
