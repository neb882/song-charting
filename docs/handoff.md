# Handoff (updated 2026-11-06)

The session that ran M3 and M4 ended on 2026-11-05; a new session took over that morning and ran M5 (v0.2.0) to its
release gate. Read CLAUDE.md, docs/PROGRESS.json (`in_flight` says what is waiting, `deferred` holds the known gaps)
and docs/PIPELINE.md first. This note adds what only the running session knows.

## Where things stand

- **v0.1.0** is published as a pre-release; the friend is running M4-08 part B. When his diagnostics zip and notes
  arrive, read them as M4-08 says.
- **v0.2.0** is built and through the orchestrator's part of the release gate (docs/reports/v0.2.0-gate.md): every
  order merged (M4-11, M5-01 to M5-13), the full review workflow and its fixes, the golden charts and the stress check
  on the candidate, the advisor and its fixes. **Nothing is published.** What is left is the owner's: his PC checks
  and play test (the gate report's list), his decisions (its table, with recommendations), and his approval. Then the
  release is built from a clean clone at the tagged commit with `packaging/release/build.sh 0.2.0` (it refuses any
  other version) and published by the owner, as v0.1.0 was (the session's proxy refuses tag pushes).
- **The owner's open questions:** the git history (a committed report's md5 prefixes and a stress song's title and
  artist, fixed in the files, kept by the history: rewrite or leave); the stale remote branch `m5-01-fast-grid`.

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
The environment variables are eval/README.md's step 9; every brief names them. Since the version is 0.2.0, a golden
or stress run against kept folders made at 0.1.0 needs `--rerun bass` (the bass cache key holds the version).

## Only in the session

- **The usage meter:** `.claude/mods/usage-meter/` (its README installs it); read it before each wave. The owner's
  limit: pause new work at 75 % of the weekly usage, stop before 80 %.
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
delete; no usage credits; pause new work at 75 % of the weekly usage and stop before 80 %.
