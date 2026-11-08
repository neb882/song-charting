# M7 plan: songcharter v0.4.0, the video review's findings measured against the human charts

*Written 2026-11-07 on branch `m7-plan` from `main` at 4d3f73f (v0.3.1 and its GPU check) by the planner
(docs/PIPELINE.md, Gates: a fresh agent that reads the repository and the owner's goals). The orchestrator runs the
waves; an advisor (a different model) reviews this plan before M7-01 starts. Evidence tags follow DESIGN.md: [code]
read from this repository, [here] measured on the dev machine or recorded in PROGRESS or a report, [review] the video
review's claim, [check] the orchestrator's check of it, [inference], [decision] a choice made here, [owner] the
owner's to make.*

## 1. What this version is

v0.3.0 is published (v0.3.1 adds the listen tool). The owner recorded his GPU chart of the shred instrumental of the
stress set (`sooth`, halved to 77 BPM by M6-06) in Clone Hero, and had another vendor's video model review the
recording with the chart, its report.json and a second song of his (`tod`: a 99 BPM rock song of the owner's, in
no set, with no human chart). The review lists eight "root causes" with fixes. The orchestrator checked each claim
against the code at a5895ff and the two charts' note tracks [check]:

| # | the review's claim | the check | what M7 does |
|---|---|---|---|
| 1 | the halving to 77 BPM is the bug; keep 154 and unlock finer slots | **wrong diagnosis.** Both human charts of sooth are at 77 BPM, and the halving took its beat F1 0.644 -> 0.985 (M6-06). Clone Hero's note speed does not depend on the BPM. The quantizer dropped 30 of 2,485 guitar notes (`dropped_distinct`), so the slots do not thin the runs: the engine wrote 2,431 onsets | keep the halving; no slot change (M5-99's burst slots stand: they would recover at most those 30 notes). Its side effect on the HOPOs is real: #2 |
| 2 | HOPO flags: tod's solo 16ths force-strummed (118 of 119 natural HOPOs flipped); sooth's picked 8ths turned HOPO (1,425 kept, 65 strums flipped to HOPO, 161 taps) | **right** (recounted identically). `hopo: "forced"` keeps only what the engine forced and leaves the rest to the natural rule on our grid; on a halved grid the true tempo's 8ths fall under the 65-tick threshold. v0.2.0's numbers: guitar state agreement 0.65-0.68 forced, 0.66-0.70 source (troop); sooth HOPO share 0.65 against the humans' 0.55 and 0.39 | measure every mode and two candidate rules against the humans (M7-01), build the winner (M7-02) |
| 3 | take 0 wins unless another beats it by about 0.055 | **right**: `takes.MARGIN` 0.05, set when take 0 was the GPU take and the other seeds CPU takes; today all four run on one device. On the owner's sooth chart 18 of 22 windows kept take 0. Never measured against humans | measure margins against the humans on 4-take charts (M7-01 part C), then M7-05 |
| 4 | sustains dropped, vibrato charted as same-fret repeats | **right**: sooth guitar 103 of 2,413 onsets sustained, 361 sustains dropped, 362 same-fret single-note repeats (0.15); tod 129 of 413, repeats 0.08. The 0.75-beat floor is 584 ms at 77 BPM (M5-99) | measure our shares against the humans' and a candidate rule each (M7-01), then M7-02 (the floor) and M7-04 (the repeats) |
| 5 | the bass jackhammers one fret | **right**: sooth bass same-fret repeats 1,759 of 2,368 (0.74), tod 360 of 652 (0.55). The bass is our rule engine (HFC onsets, pYIN pitch, rank map), not a model. The humans' shares are unmeasured | measure the humans' shares and the cause (M7-01 part B), then M7-03 |
| 6 | onsets over a silent stem are only reported | **right, by design until now** (Q23): edges trimmed, inside only warned (sooth guitar 160) | count the human notes we would call silent (M7-01 part B), then M7-04 |
| 7 | drumless stretches drift | **right, known**: three "straight line" warnings on sooth (0-13, 168-190, 365-388 s) | measure how often and how far off against the humans' beats, and a second evidence source (M7-01 part B), then M7-07 |
| 8 | the solo cap cuts an instrumental's solo; rhythm and lead mixed | the cap is **right** (`max_share` 0.40, the owner's v0.2.0 decision "revisit with the 20-song set"; sooth's 31-measure solo cut to 5); the mixing is the engine's | the humans' solo shares on every song, instrumentals apart (M7-01 part B), then M7-06; the mixing is deferred (section 6) |

**The approach** (the owner, 2026-11-07, "yeah lets do it", on the orchestrator's proposal): measure each finding
against the human charts first, on every song that has one, and build only the changes that beat today's rules there.
The review's counts are right, two of its diagnoses are wrong, and its fixes are untested proposals: none is adopted
on its own word. A rule that reads well and does not beat today's against the humans goes to `dead_ends`.

**The version number: 0.4.0** [owner: his M7 goal of 2026-11-07]. Charts of the same song change on purpose (HOPO
and tap states, sustains, possibly onsets on silent stems, the bass), which the friend will feel.

## 2. Scope: the orders

Every build order is **conditional**: it starts only when M7-01's numbers show a candidate that clears the order's
bar, and builds only that candidate. An order whose candidates all fail is closed with its numbers in `dead_ends`
(the orchestrator, when it commits M7-01's report). Costs are rough: machine time on the dev machine (4 cores, CPU
only) and agent usage as a share of a week's meter, from the size of earlier orders, not measured.

| order | name | one line | conditional on | size | rough cost |
|---|---|---|---|---|---|
| M7-01 | [measure](M7-01-measure.md) | every question the review raised that a rule of ours can change, against the human charts of 23 songs; numbers only; four parts (A articulation, B stems, bass, solos and grid, C takes, D the owner's GPU arms) | — | about 12 hours of machine time (A 2.5, B 1, C 8.5), within a day | 4-5 % of the week (three measurers on a smaller model), before the reset |
| M7-02 | [articulation](M7-02-articulation.md) | the guitar's HOPO and tap states by the rule that agrees best with the humans; the sustain floor in seconds at a slow tempo | part A: a HOPO/tap rule +0.02 state agreement; a floor +0.03 sustain agreement on the slow songs | 1 day | 4-6 % |
| M7-03 | [bass](M7-03-bass.md) | the bass engine's onsets on a held note, or its lane map, whichever part B finds causes the repeats | part B: the cause measured and a candidate that holds bass F1@50 and moves the repeat share toward the humans | 1-1.5 days | 4-6 % |
| M7-04 | [stem-evidence](M7-04-stem-evidence.md) | onsets the stem does not support: notes inside a silent stem removed; same-fret repeats with no attack merged into a sustain | part B (silence) and A (repeats): removals at least 80 % (silence) or 75 % (repeats) unmatched by every human chart | 1 day | 3-4 % |
| M7-05 | [take-margin](M7-05-take-margin.md) | `takes.MARGIN` set from the 4-take charts against the humans | part C: a margin +0.005 pooled F1@50 with its CI above 0 | 2 hours | 1-2 % |
| M7-06 | [instrumental-solos](M7-06-instrumental-solos.md) | the solos' share cap from the 23 songs' humans, for every song or for instrumentals | part B: the humans' shares on at least two songs over 0.40, and our spans' overlap with theirs up | half a day | 2 % |
| M7-07 | [drumless-sync](M7-07-drumless-sync.md) | a second evidence source for the beats in a drumless stretch instead of the straight line | part B: the straight line measurably off in those stretches and a source 0.05 beat F1 better there | 1-1.5 days | 4-6 % |
| M7-08 | [thin-runs](M7-08-thin-runs.md) | the engine-thinning spike (M5-99) on the owner's GPU, scored here; measurement only, the setting's adoption is M8's | the owner's GPU time [owner] | his GPU about 2.5 hours unattended; 2 hours here | 1 % |

**Left out of this version, and why:**
- **The review's fix #1** (no halving, finer slots at true tempo): refuted by the check above; nothing to build.
- **The engine writing too few notes in fast runs, and rhythm and lead mixed in one part:** the model's, not ours
  (section 6). M7-08 measures the one lever we have; adoption waits for M8.
- **The review's take-score variants** (penalize silent onsets and same-fret repeats in the take score, reward
  recall in fast passages): measured in part C only if the margin arms leave a gap (M7-01 says when); otherwise
  M5-99.
- **The review's lead-over-rhythm priority** and **its bass "section-relative pitch-to-fret map with open notes":**
  the first needs a lead/rhythm split no stem gives; the second is one of part B's two candidates (the lane map) but
  open notes are a charting choice the humans' bass charts would have to show first (part B counts their opens).
- M5-99's other items (the meter, the ladder's calibration, a tempo change at the first grid's level, lyrics) stand.

## 3. Waves, dependencies and the usage reset

The week's meter is at about 78 % (the owner's limit 90 %, never usage credits; it resets 2026-11-09 13:00 UTC).
M7-01 and the advisor's review of this plan fit before the reset; the builds follow it.

| wave | orders | why together, and what they must not touch |
|---|---|---|
| 0 | the advisor reviews this plan; the orchestrator frees the dev disk (section 4, Disk) | the bars below are M7-01's definitions: a wrong one costs a build |
| 1 | **M7-01** parts A and B (two measurers at once: they only read the kept folders, A's builds go through the heavy-job lock), part C's takes (one heavy job per song, queued behind A's builds), and part D if the owner runs it | no builder; nothing in the repository changes. Target: done by 2026-11-08 evening, before the reset |
| 2 | **M7-02** ∥ **M7-03** | `quantize.py`, `assemble.py`'s HOPO rules and part rules, `pipeline.py`'s guitar part ∥ `engines/bass.py` only |
| 3 | **M7-04** ∥ **M7-05**, then **M7-06** in the same slot | `assemble.py`'s stem stage (after M7-02's merge) ∥ `takes.py`, then `starpower.py` |
| 4 | **M7-07** | `beatgrid.py`, `assemble.py`'s grid stage (after M7-04's merge) |
| then | the release gate (section 8) | |

- At most two builders at once (PIPELINE). A dropped order frees its slot: the next order in the table moves up
  where its files allow (M7-07 may join wave 3's second slot if M7-04 is dropped).
- Every order branches from `main` after the wave before it has merged; before it starts, the orchestrator adds to
  its work order the M7-01 numbers its bar reads (the candidate, its values, the songs).
- Heavy jobs (golden, stress and 20-song runs, the takes) go through `tools/heavy.sh`, one at a time; the dev
  machine's disk floor needs `SONGCHARTER_HEAVY_MIN_FREE_GB=1` (section 4).

## 4. The evaluation plan

**The songs** (23 with human charts): the six references of the golden set (one human chart each; the test song has
none and stays a regression guard), the four stress songs (troop, sooth, break, pm2; 2-5 human charts each), and the
20-song set's 13 new songs (`$DEV/eval-set20`, 2-6 charts each; labelled s01-s13 in anything committed: their ids
sorted, as `docs/reports/set20-v03.md` labels them; their ids and titles stay private). A song's value on a measure
is its mean over its human charts unless the measure says the primary; the pooled value is the mean over the songs
that have the part. The humans' own agreement (each other chart against the primary) is the ceiling beside every
number. A song whose humans agree under 0.6 on the measure is reported but left out of the pooled bar, and named.
Noise: a paired bootstrap over songs (10,000 resamples), 95 % CI.

**The guard on every build order** (beside its own bar):
- Golden (`eval/README.md`, Golden charts) against the order's merge base, `--expect` naming the parts it means to
  move; pooled F1@50 per part and level not lower by more than 0.002, and identical where the order only changes
  flags or lengths. The kept folders were made at 8ba3cbd, so every golden pair runs `--rerun drums,bass,sections`
  on both sides (PROGRESS `deferred`, "[gate]"), plus any engine the order changes.
- The stress set and the 20-song set: a run of the order's merge base and one of the branch, `stress.py compare`
  "Regressions: 0" on both (no F1@50 against a primary down by more than 0.01). The 20-song set runs with
  `EVAL_DATA=$DEV/eval-set20 STRESS_JSON=$DEV/eval-set20/set20.json STRESS_LOCAL=$DEV/eval-set20/stress.local.json`
  and `--refs $DEV/eval-set20/stress --work $SONGCHARTER_GOLDEN/set20-work` (`$DEV/set20-run.sh` shows them).
- The feel report: no measure worse than the base's without a reason in the order's report.
- Its bar's measure added to `eval/scorer/score.py`'s feel measures (with a test) when score.py lacks it, so every
  later `stress.py score` reports it; M7-01's script is the reference.

| order | golden | stress and 20-song sets | its own bar (M7-01's measure, on the branch's runs) |
|---|---|---|---|
| M7-02 | `--expect guitar` (and `bass` if the floor reaches it); onsets and F1 identical | 0 regressions; F1 identical | guitar state agreement +0.02 pooled, CI above 0, no song down 0.03; tap precision not lower; sustain agreement +0.03 on the slow songs, no song down 0.01 |
| M7-03 | `--expect bass` (bass.py is the bass engine's: the rerun above covers it) | 0 regressions | bass F1@50 pooled not lower (+0.005 for an onset rule); repeat share toward the humans'; contour +0.02 for a map rule |
| M7-04 | `--expect` the parts it removes notes from | 0 regressions | removal precision (silence 0.80, repeats 0.75); human notes removed under 0.5 % a part on every song; F1@50 not lower on any song by 0.005 |
| M7-05 | `--expect none` (1 take) | — (1 take) | part C's numbers; the 4-take tests |
| M7-06 | `--expect guitar` where solos move; onsets identical | 0 regressions | solo overlap with the humans' up pooled; every song's share within its humans' range |
| M7-07 | `--expect` the songs with a straight-line stretch (beatgrid.py is in the drums engine's files) | 0 regressions; beat F1 not lower on any song | beat F1 inside the stretches +0.05 pooled, no stretch down 0.05 |

**Disk.** The dev machine has about 2 GB free, a fixed allowance. M7-01 writes its builds to `/dev/shm` (RAM, 9 GB
free) and keeps only numbers; the takes keep their charts and summaries (about 40 MB in all) with each song's
engine scratch deleted after its takes (M7-01, Disk). Before wave 1 the orchestrator may delete the old run folders
that no comparison needs (`$SONGCHARTER_GOLDEN/gate-rc*`, `gate3-old*`, `m6-06-*`, `main-m605*`: about 0.3 GB);
`base`, `base-main`, `gate3-final`, `gate3-final-stress`, `set20-main` and `stress-base*` stay (the baselines and
v0.3.0's runs).

## 5. How a chart should feel: the review against the feel note

The review is the feel note's play test (`docs/reports/feel.md`) done by a viewer, with times. Its findings fall on
four of the note's nine parts, and M7-01 measures each the way the note says:

| feel part | the review's finding | measured by (M7-01) | aim |
|---|---|---|---|
| 5 articulation | picked 8ths as HOPOs on a halved grid; solo 16ths force-strummed; taps in bursts | per-note state agreement against every human chart, by mode and by the engine's forced flags; tap precision and recall | the humans' own agreement (0.64-0.99 on the stress and 20-song sets [here]) |
| 7 sustains | sustains dropped at 77 BPM; vibrato as repeats | sustain share and per-note sustain agreement; the humans' sustain lengths in ms at each tempo; same-fret repeat share and the repeats' match rate | within the humans' range on the slow songs |
| 6 shape | notes over a silent stem; phantom drum hits in a drumless stretch | the human notes inside our "silent" call, per part; our silent onsets' match rate | no ghost notes, no human note lost |
| 8 the highway | beat lines drift in drumless stretches | beat F1 against the humans' beats inside each straight-line stretch | the stretches as good as the rest |
| 7 (solos), 3 flow | an instrumental's solo cut short; the bass on one fret | the humans' solo shares and our overlap with them; the bass's repeat share and fret spread against the humans' | inside the humans' range |

## 6. What the review found that is the model's, not ours

- **Fast runs thinned.** The review counts a 4.9 notes-a-second trickle where the guitar plays 12-16, and blames
  the halved grid. The quantizer dropped 30 of 2,485 notes, so the engine (Fretformer 2) wrote too few: M5-99's
  "Fast runs thinned by the guitar engine" (2026-11-05: peaks of 11 a second where both humans reach 17). The one
  lever is the engine's own settings (its density knob, its temperature), each needing GPU hours to measure.
  **M7 does:** M7-08, the spike that is ready since M6 (`eval/spike/thin_spike.sh`, `eval/gpu.sh thin-spike`), on
  the owner's GPU if he offers the time, scored here per 30-s window against sooth's two human charts. **M7 does
  not build** a setting: it changes every take's key and every song's density, so it needs the references charted
  on the GPU with the winning setting too, and the driver it patches ships with the install. Its adoption is M8's,
  with M5-99's bar (the fast windows' F1@100 +0.10, no window down 0.02, the references' pooled F1@50 unchanged).
- **Rhythm and lead mixed in one part.** The engine writes one guitar part from htdemucs_6s's one guitar stem, and
  takes it from whichever line it hears; songcharter has no lead-only stem and no rule that could choose the lead.
  The human charts of such songs mix the two too (the review's "jarring" is the viewer's taste, not measured).
  **Deferred** (M5-99 gains it): a lead/rhythm split would need a stem model that separates them or a pitch-register
  rule, and a measure (the humans' chords against single notes in such passages) nobody has made.
- **The drums blank under an audible hi-hat** (the review's Part 1, 1b: the drum engine's recall in quiet
  passages). M7-01's B-a reports the drums' per-window F1 where the drum stem is quiet, numbers only; a change is
  the drum engine's and M5-99's unless those numbers single out a rule of ours (the silent-edge trim, a level floor).
- **The take score's bias toward fewer notes** (the review's fix #3.3) is half the model's: the splice prefers the
  takes that agree, and the engine's takes agree most where they all write little. Part C reports, per window, the
  onsets of the chosen take against the humans' count; a recall term in the score is M5-99's unless part C shows the
  margin alone leaves the gap.

## 7. Risks

| # | risk | caught by | plan |
|---|---|---|---|
| 1 | A rule tuned on sooth and tod alone | every bar is pooled over 23 songs, with sooth and the slow songs reported apart | no constant is set from one song; M7-01 says how many songs carry each number |
| 2 | The human charts disagree among themselves on states and sustains (the power-metal song's three HOPO shares 0.21-0.51) | the humans' own agreement beside every number; songs under 0.6 left out of the pooled bar | a rule only beats today's where the humans agree |
| 3 | CPU takes stand in for the friend's GPU takes in the margin test | part C's question is the margin between takes of one device, which both have; part D's GPU arm on the references | the GPU arm must not reverse the sign; the owner's GPU check at the gate reads the new picks |
| 4 | M7-01 runs past the usage reset or the disk | the meter before each part, the measurers' budgets; `/dev/shm` for builds, the takes' scratch deleted per song | part C is resumable per song: what has finished by the budget is reported, the rest marked |
| 5 | A HOPO change makes every song play differently for the friend | the play test at the gate, the owner's approval | the mode is per part, recorded in report.json; `hopo` stays a part config key |
| 6 | Removing onsets over a silent stem removes a quiet real part (a clean intro under a loud song) | part B's count of the human notes there, per part and per song | the bar's 0.5 % a part on every song, not pooled |
| 7 | The bass fix moves the five references' bass, the engine's tuned songs | golden `--rerun bass`, the references' bass F1 | the order stops if a reference's bass falls 0.01 |
| 8 | A heavy measurement job blocks a builder's runs, or the reverse | `tools/heavy.sh`, part C one job per song | builds start after M7-01 in any case |

## 8. The release gate for v0.4.0

PIPELINE's gate, in its order, plus what this version adds:
0. The version 0.4.0 (`__version__`, pyproject, uv.lock) before the gate's runs.
1. The full suite passes (CI on the candidate).
2. The golden charts against v0.3.1 (a5895ff, `/dev/shm/golden-old`), `--rerun drums,bass,sections` both sides (or
   kept folders remade cold at the candidate, if the disk allows), `--expect` the parts M7's orders moved;
   `report.md` read: the pooled F1@50 per part and level not lower than v0.3.1's.
3. **Added:** the stress set and the 20-song set against v0.3.1 (`stress.py compare`: "Regressions: 0"), and every
   adopted rule's bar met again on the integrated candidate by M7-01's measures (within 0.01 of what its merge
   reported); the feel report read.
4. The full review workflow over v0.3.1...candidate (`.claude/workflows/full-review.js`, with a token budget); its
   confirmed findings fixed.
5. The test song end to end with the gate ok; its preview looked at.
6. The advisor (a different model) reviews the release candidate.
7. **Added, the owner's GPU check** (about an hour, from the release files built locally and installed with
   `install.sh --from`): sooth (his file), tod and the test song re-charted on his GPU with the defaults (4 takes);
   their `report.json` grid records against the CPU's (sooth octave 0.5 at 77.0 BPM, halving ratio about 2.00; the
   test song octave 1 at 142.0 BPM; tod octave 1 at about 99.2 BPM, from his v0.3.0 GPU chart); the orchestrator
   recounts on his new charts what the check counted on the old (natural-HOPO positions flipped, taps, sustains,
   same-fret repeats on guitar and bass, silent onsets, the solo spans, the takes' picks) and puts the two side by
   side; he listens to one of them with v0.3.1's listen tool (`songcharter listen`, or the Done screen's Listen box).
8. **Added, the play test** (the feel note's short list, with times): the owner plays sooth and tod in Clone Hero,
   and may record them for the video model again; any of its claims is checked as the orchestrator checked the
   first review before it becomes an order.
9. The owner approves the release; the friend gets the link with the guide's update line.

## 9. Decisions, and what is left for the owner

Decided here [decision]:
1. **The halving stays.** Both human charts of sooth are at 77 BPM; the review's fix #1 would undo M6-06's measured
   gain.
2. **No rule from the review is adopted on its own word**; each is a candidate in M7-01 beside today's rule and any
   variant the measurer can state as simply.
3. **M7-01 before the builds and the reset**; each build only for the candidate that cleared its bar.
4. **The takes for the margin test come from the CPU on the dev machine** (seeds 101, 202 and 303 beside each
   song's kept take, the pipeline's seeds), with the owner's GPU takes of the six references as a second arm (part
   D) if he runs them: CPU takes need no hand-over, cover all 23 songs and match the kept takes' device.
5. **Engine settings are not changed in M7** (section 6).

Left for the owner [owner], with the recommendation:
- **Part D, his GPU time** (eval/gpu.sh on his PC; nothing else needed from him): (a) 4 takes of the six references
  (`eval/gpu.sh takes`, about an hour, as on 2026-11-02; the takes of that day are unlikely to match today's install
  key, since M5-02 changed the driver whose hash is in it: expect the hour), recommended; (b) the thinning spike on his
  sooth file (`eval/gpu.sh thin-spike`, about 2.5 hours unattended, M7-08), optional.
- **The HOPO mode, if M7-01's numbers are mixed** (a rule better on halved and doubled songs only): recommended, the
  per-octave rule M7-02 describes, if it clears the bar on those songs and leaves the rest unchanged.
- **The solo share on instrumentals:** recommended unchanged unless part B shows at least two human charts of two
  instrumentals over 0.40 (sooth's are 0 and 0.357).
- **The release:** his GPU check and play test (section 8), then his approval, as always.

## 10. Done for this version

- M7-01's report committed (`docs/reports/M7-01-measure.md`, numbers only, s01-s13 labels) with its scripts under
  `eval/m7/`; every build order built and merged, or closed with its numbers in `dead_ends`.
- Every merged order's "Done means" passes and CI is green on `main`; the release gate of section 8 holds.
- PROGRESS: M7 "built" at the gate, "done" when the friend has the release; M5-99 gains what M7 deferred.

## 11. Changes, 2026-11-07 evening (the orchestrator, the owner's "I'll leave it up to you")

From M7-01 part B (`docs/reports/M7-01-measure.md` when committed), a third video review (a 150 BPM rock ballad of
the owner's, ntl, on v0.3.1) and two second-model reviews (`docs/reports/m7-video-review-check.md`,
`docs/reports/m7-ui-review.md`):

- **New: M7-09, the halved grid's tempo shape** (wave 4, in M7-07's slot; M7-07 is closed by part B-d). The
  halved grid starts from allin1's beats (`beat_grid(start=...)`, beatgrid.py's tracker-start path) and follows them
  where the drums give no evidence: ntl's drumless intro warps 75 -> 86.9 -> 74.3 BPM (about 1.5 beats too many at
  19-33 s; the same tempo map on the owner's GPU and on this machine's CPU), and the owner's audio file of sooth runs
  at 160 BPM for its last 28 s where both human charts stay at 77 (the same on CPU and GPU for that file; the stress
  set's audio does not do it). No warning fired: `tempo_check` runs in the halved fold, and `drift_ms` is recorded,
  not tested. **First a measurement** (an sc-measurer, in process from kept folders and ntl's work folder, no engine,
  about half a day, ~2 %): on every halved song (sooth, the 20-song set's two, ntl), today's halved grid against (a)
  every other beat of the first grid's line, its parity from allin1's beats, (b) the halved start's line against the
  tracker by the same `TRACKER_MARGIN` evidence test the first pass uses, (c) allin1's curve faded to the line where
  the drums give no evidence: beat F1 against the humans whole-song and per straight-line stretch, ntl's off-grid
  intro onsets (8 of 42 today against 3 of 407 elsewhere) and the guitar stem's onset phase over 0-35 s. **Then the
  build**, whichever candidate clears (no halved song's beat F1 down 0.01, ntl's intro onsets on the grid), with two
  guards whatever wins: `tempo_check` at the first grid's fold on a halved grid, and a warning when `drift_ms` p95
  passes about two beats. About a day, 3-4 %.
- **New: M7-10, the web UI's quick wins** (any wave; nothing that charts; `songcharter/ui/` and the guide only):
  the second-model review's items 1 (the Done screen's result above the fold: the stages folded, the page scrolled to
  it, the tab title), 2 ("Install into Clone Hero" first under "Ready"), 3 (the time estimate DESIGN 4.5 promised,
  from the song's length, the takes and the device, against the golden and the owner's runs), 4 (a screen wake lock
  while a job runs and the sentence that he may close the tab), 11 (the drop zone's keyboard) and 12 (the update box
  hidden while a job runs). About a day, 3-4 %. Item 8 (a quick/best choice) and 5-7, 9-10 wait for a UI pass after
  v0.4 (M5-99).
- **M7-06 becomes `max_solos` 4** (part B-c2: pm2 and s06 gain a fourth solo, coverage +0.012, no song moves away
  from its humans' range; `max_share` stays 0.40): an hour, with the golden expectation for those two songs.
- **M7-03 stays open until one more rule is measured** (the second model's 4): a run rule for held notes (6 or more
  same-lane onsets 110 ms or less apart over one voiced pitch: one sustained note), on part B's scripts, a few hours;
  closed if it misses M7-03's bar.
- **M7-04 is closed** (B-a: removing notes over a silent stem would remove human notes; A-d: every repeat-removal
  rule lowers F1). The sustain floor in seconds stays M7-02's.
- **Open notes on guitar** come from the GPU takes (the CPU takes write none): the question needs part D's GPU takes
  of the references; until then nothing is built for them.
- **The release gate's GPU check** (section 8) compares each re-charted song's whole tempo map and `drift_ms` with a
  CPU chart of the same audio file, not only the grid's headline numbers.

## 12. After M7-01 (2026-11-08)

M7-01's report (docs/reports/M7-01-measure.md) closed M7-04, M7-05 and M7-07 and the HOPO and sustain halves of
M7-02. **M7-02 becomes the tap rule alone:** a tap is kept only in a run of 8 or more notes at 8 or more a second
(T2: on the 8 songs with our taps, +0.000 to +0.044 each, none down; our taps match a human tap 6 % of the time),
about half a day. With section 11, v0.4's builds are M7-02 (taps), M7-03 if its run rule clears, M7-06
(`max_solos` 4), M7-09 (the halved grid's tempo shape, after its measurement) and M7-10 (the UI's quick wins).

**M7-09's measurement** (docs/reports/M7-09-measure.md, 2026-11-08): candidate b (the straight line kept by the
`TRACKER_MARGIN` evidence test) changes nothing on the halved songs with human charts and fixes ntl's intro; the ratio
warning (a halved window back at the first grid's tempo) flags the owner's sooth file's outro. M7-09 builds those two;
its scripts are in eval/m7/m709/.

**M7-03 is closed** (B-b2, docs/reports/M7-01-measure.md's addendum: the run rule removes mostly real notes, precision
0.21-0.46). v0.4 builds M7-02 (taps), M7-06 (`max_solos` 4), M7-09 (candidate b and the ratio warning) and M7-10 (the
UI's quick wins).
