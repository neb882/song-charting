# M8-14: the friend's feedback and "Chart it differently"

**Branch:** `m8-14-feedback`, from `main` after the v0.5.0 review fixes (e792d8a). **Agent:** `sc-builder`, then `sc-reviewer`; the fixes read by the orchestrator and a second `sc-reviewer`, its major finding checked by `sc-skeptic`. May push its branch to run CI. **Report:** docs/reports/M8-14-feedback.md.

## Why

Two advisors (different models, 2026-11-09) found the same gap. The project's success measure is whether the friend
enjoys playing the charts. Its evidence is one sentence of his from 2026-11-03, while five releases went out. Every
quality decision since has rested on agreement with human charts, which cannot see chords, fretting or repeats.

The owner approved two changes:
- the friend rates his charts and marks bad spots, and the ratings travel back in the diagnostics zip;
- CLAUDE.md's determinism rule becomes "reproducible with the recorded configuration (seeds, device, ...); a seed the
  user asks for is configuration". That makes room for "Chart it differently": a re-roll of a chart he doesn't like.

Both go into v0.5.0. The friend is not technical, on Windows with WSL, and the page is his whole interface: plain
words, nothing that looks broken, nothing lost.

## What to build

1. **Rating and bad spots, on the Done screen and on each row of "Your charts" (M8-13):**
   - "How did it play?" with 1 to 5. Optional and changeable.
   - "Mark a bad spot": a time (m:ss, checked against the song's length) and one or more reasons:
     - too many chords;
     - missing notes;
     - extra notes;
     - off the beat;
     - hard to read;
     - great part (praise is data too).
     Add an optional short note (plain text, at most 300 characters), and allow several spots per chart.
   - Keep it small and quiet on the page: one line until he opens it.
   - **Where it is saved:** with the chart, not inside the song folder, because that folder is copied into Clone Hero.
     For example `<home>/state/feedback/<chart id>.json`, keyed by the library's chart id. It survives a restart, and
     a re-chart does not overwrite it.
   - **Routes:** behind the same guards as `/api/jobs` (Host, Origin, `X-Songcharter`), with ids not paths, and the
     inputs validated (rating 1-5, times within the song, reasons from the list, note length).
2. **Into the diagnostics zip** (wherever it is made today; find it):
   - every chart's feedback;
   - each rated chart's report.json `pipeline` field (seeds, takes, devices, fallbacks: M8's fixes added it), so a bad
     spot can be reproduced here;
   - no paths, no user name.
   - The zip's guard (find what checks it) covers the new files. The note is the friend's own text and travels as he
     wrote it; say so in the guide.
3. **"Chart it differently", on the Done screen and on each row of "Your charts":**
   - It charts the same song again with the next seed for its guitar take or takes. Quick has 1 take, so the take's
     seed moves on; Best moves each of its 4 seeds. Bass, drums and sections are unchanged, from the cache.
   - The seed is configuration: recorded in report.json, in the take cache's key (check it is already), and in the
     queue entry.
   - **The recorded configuration:** CLAUDE.md's rule now reads "Reproducible: the same input with the same recorded
     configuration (seeds, device, engine versions, fallbacks; recorded in report.json's `pipeline` field) gives a
     byte-identical notes.chart on that machine." The review fixes already put the device, the takes, each take's
     device and the fallbacks in that field.
     - Add the seeds (each take's).
     - Add the engines' versions: the same identities the cache keys hash (autochart's driver and model manifest, the
       separation and drum models, allin1), as short hashes or version strings, with no paths.
     - The first seed's chart stays byte-identical. Say whether report.json itself is byte-identical run to run.
   - The new chart is a new library entry, a version 2, 3 and so on, beside the first. Nothing is overwritten.
     "Your charts" shows them together, with the version, the date and its rating.
   - **Installing:** the versions install to the same Clone Hero folder, so only one is in the game at a time. The
     replace question (409) says which version is installed and asks to replace it.
   - **The audio:** if the song's audio is no longer at hand (check where uploads and the work cache keep it), the
     page asks him to drop the file again, with this chart's options kept.
   - **The queue:** a re-chart goes into the list like any song. The duplicate refusal (M8's review fixes) keys on
     the upload and the seed, so a re-chart is not refused as a duplicate.
   - **The CLI:** `--seed N` (or the existing option, if one exists), so the same chart can be reproduced here.
4. **Docs:**
   - **The guide** (docs/guide/windows-wsl.md): how to rate, mark a spot, and chart it differently, and that ratings
     go back in the diagnostics zip.
   - **DESIGN 4.5:** the routes and files.
   - **DESIGN 2.7:** the seed as configuration, under the reproducibility rule.

## Rules

- **Determinism:** the default chart (the first seed) is byte-identical to today's. The golden charts must not move.
- **Errors:** user-facing errors are InputError or ToolError; the page shows plain words.
- **Branch** `m8-14-feedback` from origin/main **after** the v0.5.0 review fixes merge. The orchestrator tells you the
  commit. Use its own worktree. Small commits.
  - **Files:** songcharter/ui/* (jobs.py, server.py, static/*), songcharter/pipeline.py and cli.py (the seed only),
    the diagnostics code, tests/test_ui_*.py and any new tests, docs/guide/windows-wsl.md, docs/DESIGN.md 2.7 and 4.5.
  - **Not:** the engines, and docs/PROGRESS.json.
  - Push and start CI; don't merge.

## Checks

- **Tests** for each part: the routes and their guards, validation, saving and surviving a restart, the zip carrying
  feedback and no path, versions side by side, the replace question naming the version, the seed in report.json and
  the key, the default seed unchanged, the queue's duplicate rule. Use `PYTHONDONTWRITEBYTECODE=1` and no
  `__pycache__`. Run the affected test files; CI runs the suite. Say which test covers each part. A reviewer will break
  them.
- **Screens:** the stand-in server and scripts in
  `<scratchpad>`/m8/m810-screens/, copied into
  /dev/shm/m814/, with made-up songs. Chromium at 1280x860 and 700 px, light and dark, deviceScaleFactor 1, showing
  the Done screen and Your charts with the rating, a bad spot and two versions. Look at the shots, then delete them and
  the folder.
- **No golden run here.** The orchestrator runs it, and the first seed must leave the charts unchanged.
- **This machine:** CPU only, 15.7 GB RAM, about 1.1 GB free on /. Keep /dev/shm/m814 under 1 GB. Python: the shared venv's, from the
  worktree.

## Privacy, usage, report

- **Privacy:**
  - Never open a package (.sng), a reference chart, a vocal track, the stress set or the owner's own songs.
  - Never print or save a lyric, or a stress or 20-song title, artist, charter, md5 or 20-song id.
  - No home path or user name, and no `pgrep -af`.
  - No AI model names in code, docs or commits apart from the trailers.
  - Run both privacy checks on your changed files before each push:
    - `EVAL_DATA=<the eval data> python3 -I eval/privacy_check.py <files>`;
    - the same with `EVAL_DATA=<the 20-song set's data>`, counting hits only and comparing them with main's.
- **Usage:** read `mcp__usage-meter__usage` before each part. At 85 % weekly: commit, push, write where you stopped,
  return.
- **Report:** `<scratchpad>`/m8/m8-14.report.md,
  with the commits, the checks, what the screens showed and the interpretations to check. Return in under 700 tokens
  with the head and the CI run. Commits end with the session's attribution trailer.
