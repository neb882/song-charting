# Handoff (updated 2026-11-07)

The session that ran M3 and M4 ended on 2026-11-05; a new session took over that morning and ran M5 (v0.2.0); M6
(v0.3.0) was published on 2026-11-07. Read CLAUDE.md, docs/PROGRESS.json (`in_flight` says what is waiting, `deferred`
holds the known gaps) and docs/PIPELINE.md first. This note adds what only the running session knows.

## Where things stand

- **v0.1.0** is published as a pre-release; the friend is running M4-08 part B. When his diagnostics zip and notes
  arrive, read them as M4-08 says.
- **v0.2.0** was published by the owner on 2026-11-06 as a pre-release (tag v0.2.0, eb0f340; its gate:
  docs/reports/v0.2.0-gate.md), after his PC checks. **v0.2.1** (v0.2.0 with M6-08's fix, a build stuck for an hour
  on a quiet stretch) followed on 2026-11-07 (tag v0.2.1, 23389ac). Next there: the owner sends the friend v0.2.1's
  install line.
- **v0.3.0** (M6) was published by the owner on 2026-11-07 as a pre-release (tag v0.3.0, b609b40; its gate:
  docs/reports/v0.3.0-gate.md). Its three assets are byte-identical to `packaging/release/build.sh 0.3.0` at the tag.
  His GPU check passed after it (two songs: allin1 fold 0 reads as on the CPU; Q29 settled; the gate report). M6-09
  (a chart you can hear) followed as **v0.3.1** (tag v0.3.1, a5895ff, published 2026-11-07; assets byte-identical
  to the build at the tag). Releases are built from a clean clone at the tagged commit and published by the owner (the
  session's proxy refuses tag pushes).
- **M7 (v0.4.0)** is planned (docs/work-orders/M7-00-plan.md, from the owner's video reviews of his GPU charts) and
  its measurement M7-01 runs; the build orders follow it, after the weekly usage reset (2026-11-09 13:00 UTC).
- **The owner's earlier questions are settled:** the history was rewritten on 2026-11-06 to remove a report's md5
  prefixes and a stress song's artist (his decision), and the stale remote branch `m5-01-fast-grid` is gone.

## The dev machine

All of it outside the repository, in one folder beside the checkout (`<dev>`; eval/README.md, "Rebuilding the dev
machine", rebuilds it):
- `<dev>/eval`: `refs/` (the seven golden songs, the test song from the owner's MP3), `stress/` (the stress set:
  troop, sooth, break, pm2), `stress.local.json` (the owner's package list: md5s, titles, charters), `sng/`.
- `<dev>/golden`: the kept folders `work/` and `stress-work/` (main at 8ba3cbd; shared by every run: never delete),
  the gate's runs (`gate-v010`: v0.1.0 with drums, bass and guitar rerun; `gate-rc`, `gate-rc-stress`: the candidate),
  `stress-base` (M5-09's baseline, the one the gate compares with), and each order's runs.
- `<dev>/sepcache` (the separation cache), `<dev>/allin1` (allin1's Python).
- `<dev>/stress`: the owner's audio of the stress songs, a notes folder with the titles and md5s, and `private/`
  with the owner's lyrics text for the timing-only check (never printed, quoted or committed).
- `<dev>/owner_v01`: the owner's v0.1 song folders of the stress songs.
The environment variables are eval/README.md's step 9; every brief names them. Since the version is 0.3.0, a golden
or stress run against kept folders made at an earlier version needs `--rerun bass` (the bass cache key holds the
version: engines/bass.py).

## Only in the session

- **The usage meter:** `.claude/mods/usage-meter/` (its README installs it); read it before each wave. The owner's
  limit: keep working up to 90 % of the weekly usage (2026-11-06).
- **Check-ins:** the session schedules its own while agents run (PIPELINE, Long runs), and keeps a tracked local task
  running while it waits on CI (an idle container is reclaimed).
- **Before every push to main:** `EVAL_DATA=<dev>/eval python -I eval/privacy_check.py` (PIPELINE, the merge).
- **The thin-run spike (M6):** `eval/gpu.sh thin-spike AUDIO` on the owner's GPU (eval/spike/thin_spike.sh). When his
  `thin_spike_results.zip` arrives, score it per 30-s window with eval/stress.py's scorer against the shred song's
  human charts; the adoption rule is in M5-99.
- **Messages from the earlier session** arrive; replies to it were refused (a trusted device is needed): the owner
  relays.

## Limits for unattended work (the owner's, unchanged)

No release published without the owner; no session on the owner's PC unless he asks; no force push or branch
delete; no usage credits; work up to 90 % of the weekly usage (the owner, 2026-11-06).
