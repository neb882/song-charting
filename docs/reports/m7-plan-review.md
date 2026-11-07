# The advisor on the M7 plan (m7-plan at b57cd0f), 2026-11-07

Read: CLAUDE.md, PIPELINE (Gates, Size the process), M7-00..M7-08, the review, the orchestrator's check, the planner's
brief; the code at a5895ff; the base runs' summary.json and report.json files (numbers and labels only). Checked here:
the disk (2.3 GB free on /, /dev/shm 16 GB tmpfs, 10 GB RAM free, 4 cores), the meter (weekly 77 %), the kept takes'
generation time, `cp -al` across filesystems.

## Findings (most severe first)

1. **C-b's hard-link copy into /dev/shm cannot work** — changes an order (M7-01 C-b). The kept folders are on / and
   /dev/shm is a tmpfs: `cp -al` fails with "Invalid cross-device link" (tested; coreutils 9.4). A real copy of a kept
   folder is 0.6–0.9 GB a song. Fix: hard-link the copy beside the kept folders (`$SONGCHARTER_GOLDEN/m7-copy/<id>`,
   same filesystem, no disk cost, deleted per song), or take the order's own second route (assemble in process with
   the takes and the margin). The pipeline reads takes at `<work>/guitar/seed_<seed>/` (pipeline.py 1133) and the
   key has no device beyond `_on_device`, so the copy route then works as written.

2. **Part A compares builds from two code paths** — changes an order (M7-01 part A), judgement. The base arm is not
   built: it is `v031` and `gate3-final-stress`, both run with `--rerun drums,bass,sections`, and `set20-main`, run
   with no rerun, while A1–A3 run with no rerun from kept folders made at 8ba3cbd. The README says a rerun reproduced
   the kept outputs exactly on the references, so the confound is probably nil, but the bass floor line (A-c) and
   any grid-dependent state would carry it unchecked. Build a fourth arm, base, the same way as A1–A3 (about 50 min)
   and compare the four among themselves; its scores against `v031`'s are a free check of the rerun claim, and it is
   C-b's one-take arm too. Also: `gate3-final-stress` has no `stress_scores.json` (gate3-new-stress has one, PROGRESS
   says identical); the A/B measurers must run `stress.py score` on the base they use.

3. **The "humans agree under 0.6" exclusion cannot apply to 6 of the 23 songs** — note (M7-00 §4, M7-01). The
   references have one human chart each: no ceiling, never excluded. Say so, and report each pooled bar with and
   without the single-chart songs; the stress and 20-song songs (2–6 charts) carry the ceiling.

4. **Few songs carry several bars** — note, with one change (M7-02's bar). From the base runs: grid under 100 BPM on 6
   songs (3 of them single-chart references); octave not 1 on 7 (3 halved, 4 doubled). So the sustain-floor bar
   (+0.03 "pooled on the slow songs") rests on 6 songs and R1 can differ from "forced" on 7: a 23-song bootstrap CI
   is mostly zeros there. Ask M7-01 to report R1 and the floor on their own songs with per-song values, and let
   M7-02's bar read "+0.03 on the slow songs, every slow song not down" rather than a CI. The drumless bar is fine:
   about 45 straight-line stretches on 20 songs (M7-07 needs 5 on 3).

5. **Wave 2 has a file conflict** — changes an order (M7-02, M7-03). Both list `eval/scorer/score.py` (new feel
   measures) and run in parallel. Give score.py to one order, or land every bar's measure in score.py as a small
   direct job when M7-01's scripts are committed (they are the reference anyway); M7-04 also lists it, after M7-02.

6. **Scratch on the disk is the wrong default** — note (M7-01 Disk, C-a). The disk has 2.3 GB; heavy.sh's floor is
   set to 1 GB, the order refuses under 0.5 GB, and the engine's separation of a 9-minute song is of the order of
   1 GB. A long song's scratch on disk can refuse the next queued job mid-run. Put the engine scratch in /dev/shm
   always (10 GB RAM free, the builds there are 45–115 MB a set), and keep the disk for the 40 MB of takes.

7. **Machine time is right, with about 2x slack** — note. The kept takes' `generationSeconds` sum to 1.98 h
   (references 0.27, stress 0.65, 20-song 1.05), so three seeds are 5.9 h, plus separation: C-a's 6.5 h holds; A's
   50 min an arm matches set20-main's 37 min. Serial on the lock: A (now 4 arms) 3.3 h + C-a 6.5 + C-b 2 = 12 h,
   against 24 h to the 2026-11-08 18:00 target. One heavy job runs at a time on 4 cores, so `--threads 4` for A and
   C would shorten it; the kept takes' thread count is not recorded, so treat 2 as the safe match.

8. **Usage fits, narrowly** — note. 77 % now; M7-01 4–5 %, this review about 1 %, the orchestrator's day of waiting
   the unknown: 85–87 % is believable only with tracked waiters, not polling. Read the meter before C-b and before the
   report is committed; the measurers' 87 % stop is right.

9. **One review finding is neither measured nor deferred** — note (M7-00 §6). Part 1's "Drums highway blank for 2+ s
   under audible hi-hat" is the drums engine's recall in quiet passages (B-a counts phantom drum hits, not missing
   ones). Add it to §6 as the model's, or have B-a read the drums' per-window F1 where the drum stem is quiet (the
   stress scores already have 30-s windows).

10. **The owner's asks are clear and sized** — note. D-a's "his runs/takes of 2026-11-02 with today's install key" is
    unlikely: M5-02 changed the driver after that date and the driver's hash is in the key, so expect the hour's rerun.
    Part D arrives after M7-01's deadline: say M7-05 waits for it only if it has arrived before wave 3 starts.

11. **Set20-main's commit differs from a5895ff** in pipeline.py (a docstring) and engines/sections.py (fold 0 on
    every device; the CPU already ran fold 0) — note, the plan's "charting code identical" holds in effect.

12. **Determinism and the guards are sound** — note. Every candidate is a seeded or rule-based transform of kept
    inputs; the golden `--expect`, the two compares and the per-song floors (M7-04's 0.5 % a part, M7-03's reference
    bass) are the right shape. M7-08's 2.5 vs 3.5 h for the spike differs between M7-00 and M7-08: pick one.

## Verdict

Ready to run M7-01 with changes 1 (C-b's copy on the same filesystem or in process), 2 (a built base arm; score the
stress base) and 6 (scratch in /dev/shm), and the notes 3 and 4 written into the report's format before the measurers
start. Finding 5 is for the orchestrator before wave 2. Nothing here changes an order's scope, so no skeptic is needed.

## The orchestrator's routing (2026-11-07)

All twelve applied to the orders before M7-01 starts: 1, 2 and 6 in M7-01 (the hard-link copy beside the kept folders, a built base arm and the stress base scored, the engine's scratch in /dev/shm); 3 and 4 in M7-01's rules (the references with and without, per-song reports for rules that touch few songs); 5: score.py is M7-02's alone in wave 2 (it adds the bass's two measures; M7-03 reads its bar with M7-01's script until then); 9: the drums' quiet passages in M7-01 B-a and the plan's section 6; 10: part D's hour expected, M7-05 does not wait for it; 12: the spike's GPU time 2.5 hours throughout; 7, 8 and 11 noted. No finding changed an order's scope, so no skeptic ran.
