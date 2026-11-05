# Handoff (updated 2026-11-05 evening)

The session that ran M3 and M4 ended on 2026-11-05; a new session took over that morning and runs M5 (v0.2.0). Read
CLAUDE.md, docs/PROGRESS.json (`in_flight` says what is building, `deferred` holds the gate's notes) and
docs/PIPELINE.md first. This note adds what only the running session knows.

## Where things stand

- **v0.1.0** is published as a pre-release; the friend is running M4-08 part B. When his diagnostics zip and notes
  arrive, read them as M4-08 says.
- **M5:** wave 0 (M4-11), M5-09, M5-06, M5-05 and M5-01 are merged; M5-02 and M5-03 are building; M5-04 waits for a
  builder slot; wave 4 (M5-08, then M5-07) follows; then the release gate (M5-00 section 7). Each merge's report is
  in docs/reports/.
- **The owner's decisions today:** the stress set (three songs) with no song title, artist, charter or package md5 in
  anything committed (the list is a local file he keeps); the suite runs as `python -m pytest`; v0.2's rollout does
  not wait on his manual GPU experiment (the thin-run spike below is M6's). The release gate's checks on his PC
  (the provoked GPU failure under memory=12GB, the test song on CUDA, the play test, the art in Clone Hero) and his
  approval to publish still stand unless he says otherwise.

## The dev machine

All of it outside the repository, in one folder beside the checkout (`<dev>`; eval/README.md, "Rebuilding the dev
machine", rebuilds it):
- `<dev>/eval`: `refs/` (the seven golden songs, the test song from the owner's MP3), `stress/` (the stress set),
  `stress.local.json` (the owner's package list: md5s, titles, charters), `sng/`.
- `<dev>/golden`: `base` (main at fbd9751, cold; the six references match eval/baseline/summary.json exactly),
  `stress-base` (the stress baseline), the kept folders `work/` and `stress-work/` (shared by every order: never
  delete), and each order's runs.
- `<dev>/sepcache` (the separation cache), `<dev>/allin1` (allin1's Python).
- `<dev>/stress`: the owner's audio of the stress songs, a notes folder with the titles and md5s, and `private/`
  with the owner's lyrics text for the timing-only check (never printed, quoted or committed).
- `<dev>/owner_v01`: the owner's v0.1 song folders of the stress songs (charts and report.json; the rock song's
  chart carries lyric events: numbers-only scripts).
The environment variables are eval/README.md's step 9; every brief names them.

## Only in the session

- **The usage meter:** `.claude/mods/usage-meter/` (its README installs it); read it before each wave.
- **Check-ins:** the session schedules its own every ~50 minutes while agents run (PIPELINE, Long runs).
- **The thin-run spike (M6):** `eval/gpu.sh thin-spike AUDIO` on the owner's GPU (eval/spike/thin_spike.sh). When his
  `thin_spike_results.zip` arrives, score it per 30-s window with eval/stress.py's scorer against the shred song's
  human charts; the adoption rule is in M5-99.
- **Messages from the earlier session** arrive; replies to it were refused (a trusted device is needed): the owner
  relays.

## Limits for unattended work (the owner's, unchanged)

No release published without the owner; no session on the owner's PC unless he asks; no force push or branch
delete; no usage credits; pause new work at 70% of the weekly usage.
