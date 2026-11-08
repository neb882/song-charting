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
| `M4-11-art.md` | album art from the song's cover and a given background image, re-encoded with no metadata; the review and its fixes |
| `rc-advisor.md` | the advisor's review of the v0.1 release candidate as a whole, from the friend's side, and the three skeptics' reproductions |
| `rc-fixes.md` | the release candidate's fixes (the guide's timings, the guitar's GPU-failure message, doctor's problems on the page, M4-08's release-first order and checks) and their review |
| `v0.3.0-gate.md` | the release gate for v0.3.0: the golden charts and stress set against v0.2.0 and on the final candidate, the full review and its fixes (M6-10), the advisor; the owner's GPU check and decisions left |
| `v0.2.0-gate.md` | the release gate for v0.2.0: the full review, the golden charts and the stress check on the candidate, the test song, the advisor; the owner's checks and decisions left |
| `release-gate.md` | the release gate for v0.1: the full review, the golden charts and the test song; the GPU smoke test on the owner's 5070; the gate's fixes and their second review |
| `charting-conventions.md` | how 5-fret charts are supposed to be made (tempo maps, notes, chords, HOPOs, sustains, star power, solos, lyrics, the song folder), with sources, and songcharter's gaps (M5) |
| `M5-01-fast-grid.md` | the grid's tempo octave doubled on dense songs, no chord of notes distinct in time, the 20 ms floors; the four decisions and the review |
| `M5-02-long-songs.md` | a guitar take cut short by the engine's token budget continued and stitched; the watchdog's headroom after the skeptic |
| `M5-03-solos.md` | solo caps in measures, seconds and share from the human charts; the densest window and the trim |
| `M5-04-lyrics-warning.md` | the lyrics' unsure warning on the share of weak words, calibrated on 14 runs (numbers only) |
| `M5-05-gpu-retry.md` | a failed CUDA take retried on the CPU, classified from the driver's FAILED line after the skeptic |
| `M5-06-names.md` | "Artist - Title" from the file name; folder names cut at a word |
| `M5-07-updates.md` | the page's update notice with a Copy button, and the update path in CI |
| `M5-08-install-polish.md` | the install's quiet lines and download names |
| `M5-09-stress-eval.md` | the stress set (generic ids, the owner's list kept outside), `eval/stress.py` and the feel measures, the baseline |
| `M5-10-doubled-lyrics.md` | the lyrics on a doubled grid snap to its 8ths (numbers only) |
| `M5-11-octave-by-density.md` | the octave by note density alone, a fourth stress song, the new four-song baseline |
| `M5-12-gate-fixes.md` | v0.2.0's release gate fixes: the version and build.sh's check, the work folder by key, a person's background, the old server; the docs and privacy fixes and `eval/privacy_check.py`; both reviews |
| `M5-13-advisor-fixes.md` | the gate advisor's two findings: an older chart of ours for the same song is the one an install replaces; no update under a running songcharter |
| `M6-01-fast-star-power-solos.md` | star power counted at most at 160 BPM on fast songs, from 34 human parts; solo caps kept; the review |
| `M6-02-doubled-bass-triplets.md` | the bass on a doubled grid snaps to its 8ths only, no triplet slots (troop's and pm2's bass F1@50 up); the review |
| `M6-03-fast-downbeats.md` | the bar phase from allin1's downbeats (troop, pm2 and Kimochi Warui right, the others unchanged); a split vote keeps a sure kick; the review and its fixes |
| `M6-04-fast-run-chords.md` | a guitar chord inside a fast run (both neighbours under 120 ms) becomes its top note, from 18 human charts; the review and its two test fixes |
| `M6-05-doubled-tempo-changes.md` | a doubled grid whose straight line misses a tempo change starts from allin1's beats doubled (pm2's beat F1 0.598 -> 0.987); its lower levels' bar phase; the review and its fixes |
| `M6-06-halving.md` | a first grid at twice allin1's beats, under the fold's floor, halved and rebuilt from them (the shred song at 77 BPM: beat F1 0.644 -> 0.985, downbeats 0.989, every F1@50 up); the quantizer's shared midpoint; the review and its fixes |
| `M6-07-build-ref.md` | build_ref reads every package: the MIDI strip walked byte by byte (Phase Shift sysex events mido refused), the chart by exact name; the 20-song set's 50 charts built (songs as s01-s13); the review and its fixes |
| `M6-08-tempo-hang.md` | a tempo estimate always ends (a build stuck for an hour on the owner's PC: a negative period's octave fold); v0.2.1 |
| `M6-10-gate-fixes.md` | v0.3.0's gate fixes: the full review's 12 minors (tests, allin1's model auto = fold 0 on every device, docs); the review |
| `M6-09-listen.md` | a chart you can hear: `songcharter listen` and the Done screen's Listen box (tones per lane and pad over the song); the review's five minors and their fixes |
| `set20-v03.md` | the 20-song set's 13 new songs on v0.3's code (songs as s01-s13): F1@50 against the primary and the humans' ceiling, the beat grid, what to do next |
| `feel.md` | how a chart should feel to play: nine parts, each with a measure, revised after the advisor (M5) |
| `m5-plan-review.md` | the advisor's review of the M5 plan and the three skeptics' verdicts |
| `m7-plan-review.md` | the advisor's review of the M7 plan (the video review's findings measured first) and how each finding was applied |
| `m7-video-review-check.md` | a second model's check of the owner's video reviews and the orchestrator's verdicts: corrections, the halved grid's tempo shape |
| `m7-ui-review.md` | a second model's review of the web UI: twelve improvements, the quick wins for v0.4 |
| `M7-01-measure.md` | M7-01: the video reviews' questions measured against the human charts of 23 songs (HOPO modes, taps, sustains, repeats, silent stems, the bass, solos, drumless stretches, drums, the take margin) |
| `M7-09-measure.md` | M7-09's measurement: three ways to build a halved grid and three guards; candidate b and the ratio warning chosen |
| `M7-02-taps-solos.md` | M7-02 and M7-06: taps only in fast runs (the rest keep their natural state), four solos; the review, the skeptic's wider fix |
| `M8-spike-contour.md` | M8's spike: pitch trackers on the guitar stem against the humans' fret direction in fast runs (none clears); the GPU charts differ from the CPU charts M7 measured |
| `M8-spike-takescore.md` | M8's spike: window scores for the take splice from the guitar stem's evidence (none clears; a per-window oracle shows +0.042 of headroom) |
| `pipeline-review.md` | an advisor's review of how work is run (2026-11-04), finding by finding, with what was done |
| `takes-experiment.md`, `takes-experiment-verifier.md` | spliced guitar takes against one take, and the verifier's corrections (which win where they differ) |
| `strumming-research.json` | the pick-noise detector for sparse guitar stretches, and why no fill was built |
