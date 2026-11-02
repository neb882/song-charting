# songcharter: three auto-charters compared, and what to build next

2026-11-02. This report compares autochart, chartgen and STRUM. They were scored against six human-charted songs and run on the test song (Car Seat Headrest, "Beast Monster Thing (Love Isn't Love Enough)", 6:52). It also covers a whole-song test of the ADTOF drum model against STRUM (§3.6). It was revised the same day after two checkers' reviews (Review log at the end). It was written from the runs' scores, logs and charts, the audits' scripts and the tools' source. No audio was listened to, and no chart was play-tested.

## Sources and evidence

Evidence kinds, as in the design document:
- **[here]**: measured in this project's runs. Every number with a source tag below is [here] unless marked otherwise.
- **[doc]**: documentation, a README or a paper.
- **[est.]**: an estimate.
- **[untested]**: nobody has tried it.

**What is committed.** The harness is in this repo. Its outputs are not. The raw run outputs, the audits and the ADTOF test all derive from copyrighted recordings and from other people's charts, so they stay local, like `eval/data/` (see `eval/README.md` and `.gitignore`). A file name inside a tag (e.g. [RC a_paired.json]) names a file in that local audit.

**To reproduce the tool runs and scores** (Linux or WSL2; details in `eval/README.md`):

```sh
eval/build_refs.sh /path/to/test-song.mp3   # reference songs and charts from Chorus Encore into eval/data/ (git-ignored)
eval/tools/<tool>/setup.sh                  # autochart, chartgen, STRUM at pinned commits, checksum-verified weights
eval/gpu.sh check                           # GPU, CUDA inside each tool, memory WSL sees
eval/gpu.sh start                           # eval/drive.sh detached: every tool on every song, each scored by eval/scorer/score.py
eval/gpu.sh results                         # eval/data/gpu_results.zip: scores, logs, test-song charts, no audio
python -I eval/scorecard.py eval/data       # the scorecard (drive.sh also writes eval/data/runs/SCORECARD.md)
```

The CPU runs used `eval/drive.sh` directly (its devices default to CPU). The audits and the ADTOF test used scripts that are not in this repo.

| tag | what | where |
|---|---|---|
| [SC] | GPU-run scorecard against the human charts | `eval/data/runs/SCORECARD.md` (`eval/scorecard.py`) and `eval/data/runs/<tool>/<song>.score.json` (`eval/scorer/score.py`); local only |
| [DL] | GPU-run timings and logs | `eval/data/runs/driver.log`, `gpu_run.log`, `<tool>/<song>.log` (`eval/gpu.sh`, `eval/drive.sh`); local only |
| [G] | audit: test-song lead guitar, all three tools | local only |
| [DB] | audit: test-song drums and bass (STRUM) | local only |
| [RC] | audit: reference-set claims (paired statistics, re-matching, training sets, song tails) | local only |
| [P] | audit: practicality (timing, memory, install, licence) | local only |
| [R] | first draft's scripts (`extra_scores`, `ac_takes`, `climax_windows`) | local only |
| [CN] | numbers checker's scripts (`c*.py` / `.json`) | local only |
| [RV] | this revision's scripts (`v1_scores`: scores re-read from the GPU and CPU score files; `v2_nesting`; `v3_groups`) | local only |
| [AD] | ADTOF vs STRUM drum test (§3.6) | scored with `eval/scorer/score.py`; scripts, `run.log` and `runs/<song>/score.json` local only |
| [D] | design document v1 (synthesis of nine research reports, same day) | local only, not in this repo; cited by section |
| [CR] | a critic's review of [D] (12 errors, 16 gaps) | local only; where [CR] and [D] disagree, [CR] is followed |
| [AC] | autochart docs | upstream `dvar0/autochart` at `b5a41e8` (`README.md`, `docs/engine-integration.md`, `docs/testing-status.md`), cloned by `eval/tools/autochart/setup.sh`; model pack `manifest.json` (HF `Dvaro/autochart-models` @`8a88855d`, fetched by `eval/tools/autochart/fetch_models.sh`) [doc] |
| [refs] | reference-set metadata | `eval/refs.json` (ids, md5, charters; committed) and `eval/data/refs/songs.json` (lengths, parts, tempo markers; built locally by `eval/build_refs.sh`) |

---

## 1. Bottom line

1. **No single tool gives a full band chart.**
   - autochart charts lead guitar best: Expert F1@50 0.86, against 0.57 for chartgen and 0.59 for STRUM, and it wins 6 of 6 songs.
   - STRUM is the only drum charter of the three. Its onset timing is good (0.90, a pad-blind score); its kick patterns and toms are weak.
   - No tool charts bass well (STRUM 0.59). [SC][RC a_paired.json]
   - ADTOF, tested separately on the five drum references, finds drum onsets and kicks better than STRUM (F1@50 0.97 vs 0.90; kick 0.99 vs 0.94). It assigns hand pads worse (exact lane agreement 0.59 vs 0.69), and that gap comes from 2 of the 5 songs [AD].
2. **The guitar lead is smaller where it matters.** 4 of the 6 references are Harmonix charts that are in STRUM's training set and may be in autochart's. On the two community-charted Car Seat Headrest songs, autochart scores 0.81 and 0.78 on onsets. An 8th-note grid laid on the human tempo map scores 0.86 and 0.77, so autochart does no better there; its edge is fret direction (§3.5). [RV v3_groups.json]
3. **Two goals, two answers.**
   - *Goal 1, this song for this friend, now:* first ask which instrument(s) the friend plays.
     - Lead guitar: use the autochart app as it is (A′). Generate 2–3 Expert takes, inpaint or regenerate 341–399 s, do a short Moonscraper pass (star power, sustains, 67–90 s and 218–231 s), then playtest.
     - Drums or bass: ship STRUM's chart with one global shift (the ADTOF test also points to STRUM's lanes as the better start), or do a time-boxed merge (§7.4).
   - *Goal 2, the any-MP3 tool:* option B (best model per instrument plus our own scaffolding) stays the provisional direction.
     - Drums now have whole-song evidence but no winner: ADTOF for onsets and kicks, STRUM for lanes (§3.6).
     - Bass and tempo stay open until the [D] prototypes are scored on the same songs.
     - The licence shape waits on the owner (item 5, §7.1–7.3).
4. **14 of the 23 quality faults tagged in §6 are scaffolding** (tempo maps, grids, tiers, star power, sustains, fills). We can build and check those with scan-chart and the audits.
   - The faults that most affect play sit in the models: guitar frets and chords, autochart's thin final minute, missed kicks, and bass lanes that ignore pitch.
   - F1 cannot see lanes or offsets under 50 ms, so those need lane direction, the audits and playtests.
5. **Licence (not legal advice).**
   - autochart's code is AGPL, and its weights are CC BY-NC-SA. ADTOF's weights are CC BY-NC-SA too [D §4.2; doc].
   - The Demucs author calls the Demucs weights' licence "not clear" and says htdemucs_6s "likely" falls under CC BY-NC. Every route here uses htdemucs_6s.
   - So the shipped tool will in practice be free and non-commercial, whatever songcharter's own code licence. The owner should accept that explicitly.
   - STRUM's "MIT" has no LICENSE file, and 91% of its guitar training songs come from commercial games. [P][RC e_trainsets.json][§7.3]
6. **Do not train models (C), and do not gate on F1 thresholds, yet.**
   - Detecting a 0.05 difference needs 36–151 songs, depending on the tool pair.
   - One autochart song×difficulty moved by 0.15 between two runs.
   - Grow the reference set first, with community charts and charts that post-date both tools. [CN c6_power.json][RV v3_groups.json]

---

## 2. What was tested

### 2.1 Reference songs [refs]

| id | song | charter | length | instruments in the human chart | difficulties | tempo markers |
|---|---|---|---|---|---|---|
| kimochi_warui | Car Seat Headrest – Kimochi Warui | InsaneOwO | 288 s | guitar, bass, pro drums | Expert only | 2 |
| drunk_drivers | Car Seat Headrest – Drunk Drivers / Killer Whales | IaSg14 | 225 s | guitar | Expert only | 248 |
| take_me_out | Franz Ferdinand – Take Me Out | Harmonix | 241 s | guitar, bass, pro drums | all 4 | 108 |
| all_the_small_things | Blink-182 – All the Small Things | Harmonix | 175 s | guitar, bass, pro drums | all 4 | 94 |
| lucretia | Megadeth – Lucretia | Harmonix | 240 s | guitar, bass, pro drums | all 4 | 92 |
| creep | Radiohead – Creep | Harmonix | 240 s | guitar, bass, pro drums | all 4 | 129 |

So guitar is scored on 6 songs, and bass and drums on 5. Lower difficulties are scored only on the 4 Harmonix songs [R extra_scores.json, `lower._songs`]. The reference charts and their audio are used locally for scoring only (`eval/README.md`).

The test song has no human chart. Its facts come from the project brief and [D §6]:
- constant 142.0009 BPM;
- first beat at about 0.050 s;
- a live drummer wandering ±20–30 ms (p95 drift 23.3 ms);
- 412.4 s long.

### 2.2 Tools

| tool | source and commit | inside | instruments |
|---|---|---|---|
| autochart ("Fretformer 2") | dvar0/autochart `b5a41e8` (2026-10-31, v0.1.0+148). Engine `2026.06.16-cross-platform-runtime`, generator `autochart.fretformer.v2-onnx` [DL autochart/*.log] | htdemucs_6s, then a fine-tuned Beat This, then the Fretformer 2 transformer (ONNX). Sampled decoding: T 0.95, top_p 0.98, seed 20260609. **Each difficulty is a separate generation.** | lead guitar |
| chartgen | Mechazawa/chartgen `383d50c` (2026-09-17, v1.0.0+7) | BS-RoFormer separation, librosa `beat_track`, Basic Pitch, then rules for lanes, tiers and star power. Lyrics off. | lead guitar (by design) |
| STRUM | opria123/strum `9f420cb` (2026-05-10, pyproject 0.1.0) | htdemucs_6s separation (`src/preprocessing/separation.py`) and a two-stage neural drum transcriber (5 of 7 ensemble models load as published). Guitar and bass use "neural onset detection with rule-based fret mapping" (README) [doc]. | guitar, bass, pro drums |

The commits are pinned in `eval/tools/*/setup.sh` and match the clones the audits read.

### 2.3 Hardware

- **GPU run.** An RTX 5070 under WSL2. The card model is the owner's report; the logs record only `devices: cuda` [DL gpu_run.log].
- **STRUM memory (reported, not logged).**
  - Two STRUM runs on the test song were interrupted: the log has two `START strum test_song` lines with no END, then "RESUMED after container restart" [DL].
  - The owner reports that the WSL VM had about 15.5 GB at the time and that the run finished once it had 24 GB. No file records RAM, a peak or the cause.
  - 15.5 GB is about WSL's default (half of a 32 GB PC), and the driver shared the VM. So this shows that the VM ran out, not what STRUM alone needs.
  - STRUM's peak RSS is unmeasured.
- **Earlier CPU runs.** These ran in a 4-CPU sandbox shared with another job: autochart on all 6 songs plus the test song, STRUM on 4 songs, chartgen on none [P timing.json].

### 2.4 Metrics, and what they cannot see

- **Note matching** (`eval/scorer/score.py`):
  - onset F1 at ±50 ms and ±100 ms;
  - density relative to the human chart;
  - timing median (candidate minus human, ms);
  - lane direction (does the fret move the way the human's does);
  - drum per-pad F1;
  - tempo-map beat F1 at ±70 ms;
  - scan-chart issues.

  Drum onset F1 is pad-blind: all pads at one tick form one onset.
- **Blind spots.** F1 ignores lanes completely: random lanes still score F1 1.000. It also ignores constant offsets and jitter under 50 ms: shifting every note +30 ms still scores 1.000. Only the timing median sees an offset [RC f_research.json].
- **Statistical power of 6 songs.**
  - The paired SD of guitar F1@50 is 0.106 (autochart − chartgen), 0.127 (autochart − STRUM) and 0.219 (STRUM − chartgen). Detecting a 0.05 difference with 80% power needs 36, 51 and 151 songs [RC a_paired.json; CN c6_power.json].
  - The research job's 0.122 → 47 songs is for two baseline onset detectors, not for a tool pair (research evaluation analysis, local only).
  - Six songs resolve only large gaps, such as autochart's lead of about 0.27.
- **Training overlap.**
  - **STRUM guitar.** Its guitar training split contains the very Harmonix charts of 4 reference songs: the note counts match exactly (896, 680, 1377, 881). Its guitar manifest has 4,089 songs. Of these, 3,732 (91%) come from commercial games (Rock Band 2,169, RockBand4 755, Guitar Hero 407, Fortnite Festival 401), and 3,814 have isolated guitar audio. C3 (309) and Custom (48) are community [RC e_trainsets.json].
  - **STRUM drums.** take_me_out, all_the_small_things and Lucretia were probably in training (not documented), since its holdout inventory paths sit under Guitar Hero and Rock Band game folders. Creep was held out [RC].
  - **autochart.** Its training data is undocumented [RC e_trainsets.json].
  - **Effect.** Both learned tools drop on the two community-charted songs; the rule-based chartgen does not. Mean F1@50, Harmonix vs Car Seat Headrest: autochart 0.887 vs 0.795, STRUM 0.681 vs 0.409, chartgen 0.561 vs 0.597 [RV v3_groups.json]. This fits training overlap but does not prove it (n = 2; charting style differs too).
- **Takes are not independent.** The GPU and CPU autochart runs used the same seed (20260609), and 14 of 18 scored song×difficulty pairs are identical [RC; RV v3_groups.json]. Seed variance on the references is unmeasured; [D §2.7] saw chord share range from 15% to 90% across seeds.
- **Audio provenance.** The GPU machine rebuilt every `input.wav`, and the hashes differ from the local files. Alignment lag was measured at 0.0 ms, and 19 of 28 autochart jobs gave identical token counts, so the audio is probably the same. This is unverified [RC].

---

## 3. Results on the reference set

### 3.1 Expert, per instrument [SC]

| instrument | tool | songs | F1 ±50 | F1 ±100 | timing median (ms) | density ×human | lane direction (trivial "always same") |
|---|---|---|---|---|---|---|---|
| guitar | **autochart** | 6 | **0.86** | **0.87** | −8.4 | 1.05 | **0.70** (0.45) |
| guitar | chartgen | 6 | 0.57 | 0.71 | +27.7 | 1.18 | 0.42 (0.45) |
| guitar | STRUM | 6 | 0.59 | 0.74 | +15.5 | 0.86 | 0.46 (0.48) |
| bass | STRUM | 5 | 0.59 | 0.75 | +20.7 | 1.26 | 0.57 (0.53) |
| drums | STRUM | 5 | **0.90** | 0.94 | −8.5 | 1.07 | 0.81 (0.21) |

**Guitar ranking.**
- The paired difference autochart − chartgen is +0.283 (bootstrap 95% CI 0.199–0.350), and autochart − STRUM is +0.266 (0.193–0.373).
- chartgen and STRUM cannot be told apart: +0.017, CI −0.165 to 0.126 [RC a_paired.json]. The bootstrap resamples songs only, not takes.
- Lane direction: chartgen and STRUM move their frets no better than the trivial "always same" baseline. Random lanes score 0.25–0.40 [RC f_research.json].

**The gap between ±50 and ±100: for STRUM mostly lateness (67–80%), for chartgen about half [est.].**
- **chartgen** quantizes to a librosa grid that runs late: its median signed error is positive on all 6 songs (+14 to +42 ms).
  - One shift cannot lift it past its F1@100 of 0.711.
  - A proxy estimate puts the shifted score at about 0.64 (range 0.61–0.68), which recovers about 51% of its 0.14 gap. This is an estimate, not a measurement [RC d_recovery.json].
- **STRUM** (CPU-run charts: guitar 4 songs, bass 3): one global offset lifts guitar from 0.566 to 0.657 (+28 ms late) and bass from 0.611 to 0.732 (+20 ms) [RC rematch.json `global`].

**STRUM drums per pad**, F1@50 averaged over 5 songs [R extra_scores.json]:
- kick 0.938, red 0.873, yellow 0.729, blue 0.552, green 0.400;
- cymbal/tom agreement on Y/B/G 0.923.

Toms and crashes are the weak part. STRUM's tom/cymbal classifier and its 6-stem drum separation are not published [P].

### 3.2 Lower difficulties (4 Harmonix songs; F1@50 / density ×human) [SC]

| tool | instrument | Hard | Medium | Easy |
|---|---|---|---|---|
| autochart | guitar | 0.86 / 0.96 | 0.81 / 1.11 | 0.79 / 0.97 |
| chartgen | guitar | 0.51 / 1.01 | 0.45 / 1.23 | 0.42 / 1.12 |
| STRUM | guitar | 0.48 / 0.80 | 0.28 / 0.60 | **0.02 / 0.03** |
| STRUM | bass | 0.49 / 1.05 | 0.29 / 0.83 | **0.01 / 0.04** |
| STRUM | drums | 0.82 / 1.23 | 0.69 / 1.46 | 0.65 / 0.98 |

- **autochart's separate per-difficulty generations are the most human-like lower tiers measured.** That is on 4 songs that may be in its training data. They are not nested:
  - on the test song, only 74% of Hard's onsets occur in Expert (onset counts 1,138 vs 1,139; Hard has more chord notes) [RV v2_nesting.json];
  - on drunk_drivers (CPU run), Expert has fewer onsets than Hard (611 vs 626) [G s9_autochart_ladders.json].
- **STRUM's Easy is nearly empty** because two reduction passes stack (see §6). Its guitar and bass Easy/Expert onset ratio is 0.003–0.077 (CPU runs, 4 songs) [RC e_strum_checks.json].

### 3.3 Tempo maps [SC][R extra_scores.json]

| tool | markers (human mean 112) | beat F1 mean | octave-tolerant | per song: kimochi, drunk, TMO, ATST, Lucretia, Creep |
|---|---|---|---|---|
| autochart | 337 | 0.87 | 0.90 | 0.99, 1.00, 0.99, 0.97, 0.29, 0.97 |
| chartgen | 55 | 0.77 | 0.79 | 0.91, 0.77, 0.83, 0.97, 0.27, 0.86 |
| STRUM | 1 | 0.46 | 0.58 | 1.00, 1.00, 0.12, 0.27, 0.26, 0.09 |

- **STRUM writes one tempo for the whole song.**
  - That is fine on steady-tempo songs (1.00) and fails on the four live-drift Harmonix songs (0.09–0.27).
  - Even a chart with perfect notes and a constant tempo scores 0.25–0.27 on drifting songs (Lucretia, Take Me Out and one non-reference song) [RC f_research.json `c_tempo_const`].
- **autochart's many markers carry a few ms of jitter** (median 0.7–3.3 ms), which does not matter for notes [RC c_tempo.json]. What does matter is when it picks the wrong metrical level; see the test song, §4.1.
- **Lucretia is an outlier for every tool.**
  - Beat F1 is 0.26–0.29, with 1.10–1.36 times the human's beat count [SC].
  - The human map and all three tools disagree on the metrical level there.
  - Read it as a property of that reference, not as a tool ranking, and report it separately from any mean.

### 3.4 Chart issues (scan-chart, Expert rows of [SC])

| tool | playable | issues per song | what they are |
|---|---|---|---|
| autochart | 6/6 | 107 | Mostly `badSustainGap` (sustains that end under 40 ms before the next note), 29–336 per song. Plus 4× `noStarPower`, because the model has no star-power token. |
| chartgen | 6/6 | 6 | `badSustainGap` 0–12; `babySustain` 8 on Lucretia |
| STRUM | 6/6 | 20 | `emptyStarPower` 11–16 on every song (phrases with no notes on Easy); `brokenNote` 6–8 and `smallLeadingSilence` 3–7, each on 3 songs |

### 3.5 Per-song outliers (Expert F1@50) [SC][RC]

| song | autochart gtr | chartgen gtr | STRUM gtr | STRUM bass | STRUM drums | note |
|---|---|---|---|---|---|---|
| kimochi_warui | 0.81 | 0.72 | **0.30** | **0.38** | **0.98** | STRUM's guitar density is 0.23× and its bass 0.46×: a gross failure on guitar and bass. Its drums score best on this song. |
| drunk_drivers | 0.78 | **0.47** | 0.52 | – | – | chartgen over-charts (density 1.72×) |
| take_me_out | 0.88 | 0.59 | 0.68 | 0.66 | 0.85 | STRUM drums: GPU 0.846 vs CPU 0.933, timing −19.9 vs +3.8 ms, with the same `phase_offset_ms` (300.1) in both logs; cause unknown. autochart: GPU 0.880 vs CPU 0.914 with the same seed. |
| all_the_small_things | **0.97** | 0.58 | 0.73 | 0.79 | 0.89 | |
| lucretia | 0.89 | 0.53 | 0.65 | 0.72 | 0.88 | beat F1 0.26–0.29 for all tools |
| creep | 0.81 | 0.54 | 0.66 | **0.38** | 0.89 | STRUM bass density 2.12×. Creep was held out of STRUM's drum training, and its drum score matches the probably-trained songs, so no drum inflation is visible. |

**The Car Seat Headrest pair** (community charts, the closest to the test song).
- autochart scores 0.81 and 0.78. An 8th-note grid laid on the human tempo map (an oracle baseline from the research job) scores 0.86 and 0.77. So on onsets autochart shows no skill beyond a metronome there.
- Its edge there is lane direction: 0.72 vs a trivial 0.62, and 0.58 vs 0.39.
- On the four Harmonix songs it beats the same grid by 0.06–0.31 [RV v3_groups.json; research grid8_oracle scores, local only].
- Creep (Harmonix, 0.809) scores as low as Kimochi Warui (0.813), so 6 songs cannot separate an artist effect. Treat the Harmonix numbers as possibly inflated for both learned tools.

### 3.6 Drums: ADTOF vs STRUM on whole songs [AD]

ADTOF is the drum model that [D §1, §2.9] chose from excerpts. This test scored it with `eval/scorer/score.py` on the five whole drum references, against the same human charts as STRUM.

**Method.**
1. htdemucs_6s on each song's gapless `input.wav`. Every drum stem was lag-checked: 0.00 samples.
2. ADTOF (the research job's PyTorch port, local only) on the mix and on the drum stem.
3. The research's fusion and lane mapping:
   - kick, snare and toms come from the stem; hi-hat and cymbals come from the mix;
   - `drummap2` assigns lanes, with toms by pitch cluster and `hh_cy='stronger'`.
4. An Expert-only drums chart on a constant 120 BPM map at resolution 480 (1 tick = 1.04 ms), written and packaged with `songcharter.chart` and `songcharter.package` (sync verified).

It ran on a CPU sandbox with 3 threads: 73–122 s per reference song and 173 s for the test song, of which separation took 60–143 s [AD run.log]. STRUM figures are from the GPU run [SC] unless marked CPU. "Exact lane agreement" means the same pad on matched hits; it is not §3.1's lane direction.

| song | F1@50 ADTOF / STRUM | F1@100 ADTOF / STRUM | density ×human | timing median, ms | exact lane agreement |
|---|---|---|---|---|---|
| take_me_out | 0.947 / 0.846 | 0.947 / 0.952 | 0.93 / 1.01 | −4.5 / −19.9 | 0.283 / 0.667 |
| kimochi_warui | 0.978 / 0.985 | 0.978 / 0.985 | 0.98 / 1.01 | −28.0 / −8.3 | 0.381 / 0.695 |
| all_the_small_things | 0.961 / 0.886 | 0.961 / 0.892 | 0.95 / 1.24 | −1.5 / −1.7 | 0.496 / 0.502 |
| lucretia | 0.988 / 0.880 | 0.988 / 0.953 | 0.98 / 1.07 | −2.2 / −14.5 | 0.845 / 0.772 |
| creep | 0.961 / 0.889 | 0.962 / 0.924 | 0.95 / 1.04 | −6.8 / +1.7 | 0.920 / 0.796 |
| **mean** | **0.967** / 0.897 | **0.967** / 0.941 | | | 0.585 / **0.687** |

| per pad, F1@50, mean of 5 | kick | red | yellow | blue | green |
|---|---|---|---|---|---|
| ADTOF | **0.986** | 0.854 | 0.705 | 0.522 | 0.405 |
| STRUM (GPU) | 0.938 | **0.873** | **0.729** | **0.552** | 0.400 |

- **ADTOF places hits better.**
  - Its F1@50 equals its F1@100 to within 0.001, and its kicks are better.
  - STRUM loses 0.044 between ±100 and ±50 ms. That loss is timing error, not lateness: STRUM's medians here run from −19.9 to +1.7 ms, and it loses most on the two songs where it is earliest (take_me_out, Lucretia).
  - ADTOF's medians are −1.5 to −6.8 ms on the four Harmonix songs. Its −28.0 ms on kimochi_warui fits [D]'s finding that this chart sits about 22–25 ms late [D §3.2, §6].
- **STRUM assigns hand pads better on average, but the gap comes from two songs.** ADTOF agrees more on Lucretia and Creep and ties on All the Small Things [AD score.json].
  - take_me_out: ADTOF charts 840 yellow, 0 blue and 207 red. The human chart has 348, 231 and 315. So the ride lands on yellow as well as some snares (an inference from the counts).
  - `score.py` does not yet resolve Harmonix disco flips, and 19% of Take Me Out's drum notes are disco-flagged [D §3.3]. That song's lane figures are therefore suspect for both tools; how much this matters is untested.
  - kimochi_warui: ADTOF charts 632 yellow against the human 216.
- **Fusion tests** (3 songs with STRUM CPU outputs):

  | song | STRUM CPU F1@50 / lane | ADTOF times + STRUM hand lanes, F1@50 / lane | STRUM + ADTOF's extra kicks, F1@50 / kick F1 / lane |
  |---|---|---|---|
  | take_me_out | 0.933 / 0.673 | 0.947 / 0.489 | 0.887 / 0.892 / 0.645 |
  | kimochi_warui | 0.983 / 0.697 | 0.978 / 0.550 | 0.981 / 0.980 / 0.695 |
  | all_the_small_things | 0.897 / 0.514 | 0.961 / 0.496 | 0.886 / 0.954 / 0.507 |

  - Neither combination improves lanes.
  - Adding the ADTOF kicks that STRUM lacks hurts, because those kicks are mostly not in the human charts (take_me_out kick F1 0.982 → 0.892).
  - STRUM's CPU and GPU runs differ on the same song (take_me_out: CPU 0.933 / +3.8 ms, GPU 0.846 / −19.9 ms), as in §3.5.
- **Conclusion for now.**
  - The first chart of the test song keeps STRUM's drums, with their constant offset removed by the quantizer, because their lanes are better.
  - ADTOF stays the main candidate for the product. Its onsets and kicks are better, and its gap is in the lane mapping (`drummap2`), not in onset detection.
  - Before choosing the drum engine, run a learned or better rule-based lane classifier on ADTOF's activations.
- **Caveats.**
  - 5 songs (4 Harmonix, 1 community).
  - Training overlap is possible for both. STRUM's guitar training is 91% commercial-game charts (§2.4). ADTOF was trained on custom charts from Rhythm Gaming World (359 h) [CR, from the ADTOF README; doc].
  - Lanes are scored without disco resolution.
  - ADTOF also charted the test song; that chart was not audited.
  - No listening test.

---

## 4. Results on the test song (reference-free proxies)

The test song has no human chart, so everything here compares the charts with the audio and the Demucs stems. Each proxy was calibrated on reference songs where possible.

**What the proxies cannot do.** The guitar onset-F1 proxy cannot rank charts that are roughly right.
- A blind 8th-note metronome scores at least as high as the human chart on the mix in 5 of 6 reference songs.
- On the test song it beats all three tools on the other stem (0.582 vs 0.517–0.561) [G; CN c3_guitar_proxy.json].
- The trustworthy signals are timing offsets, precision, slot-AUC and gross failures (coverage gaps, tempo errors) [G].

### 4.1 Lead guitar, all three tools [G]

| | autochart | chartgen | STRUM | human-like level (calibration) |
|---|---|---|---|---|
| tempo markers | 668 | 81 | 1 | – |
| beat lines minus local drum beats, median signed / p95 \|dev\| (ms) | −15.6 / 128.0 | +33.1 / 163.5 | +14.5 / 34.7 | −14 to −18, from 2 songs (s3b_beat_calibration.json) |
| beat errors | **half tempo** at 67.2–89.6 s and 218.5–230.3 s | **off-beat** at 319.1–339.8 s (about 170 ms early) | none | – |
| bar lines (grid phase of the downbeat, s3b) | phase 0 to 60 s (before the drums enter at 42.7 s, this is the extrapolated grid), mixed 60–90 s, phase 2 (snare) from 90 s | one beat before the kick to 330 s, then mostly on the snare | on the kick | kick on beat 1 |
| other-stem P@50 / slot-AUC | **0.591 / 0.705** | 0.501 / 0.649 | 0.531 / 0.621 | 0.625–0.846 / 0.749–0.891 on real guitar stems; blind 8ths 0.509 / 0.593 |
| note offset vs other-stem onsets (ms) | −28.7 | +9.2 | +10.3 | −7.8 to −20.3 |
| Expert onsets, first / last note (song ends 412.36 s) | 1,139, 3.42 / **400.85 s** | 1,785, 0.07 / 409.09 s | 1,640, 3.56 / 401.27 s | stem active until 405.7 s |
| missed active audio (1-bar windows) | 28.7 s | 0 | 10.1 s | – |
| ladder, onsets E / M / H / X | 540 / 727 / 1138 / 1139 (not nested) | 731 / 1035 / 1445 / 1785 | **46** / 514 / 1076 / 1640 | as a fraction of Expert: 0.23–0.49 / 0.36–0.52 / 0.63–1.0 |
| star power | **none** | 19 phrases, 63.8 s | 8 phrases (4 empty on Easy) | – |
| sections / solos | 10 named / 2 (Expert) | 12 generic / 1 | 10 named / 0 | – |

- **Timing.**
  - On the mix, against the human median of 6 songs (−15.6 ms), autochart sits 8 ms earlier, and chartgen and STRUM sit 32 and 28 ms later.
  - On the other stem, against the human guitar-stem median of 4 songs (−14.4 ms), the figures are −14, +24 and +25 ms [CN c3_guitar_proxy.json].
  - The direction matches the reference-set medians (−8.4 / +27.7 / +15.5 ms). STRUM is later here than on the references.
- **Placement.**
  - autochart has the highest precision and slot-AUC on both the other stem and the mix.
  - chartgen and STRUM are close to a blind 8th-note grid. STRUM is mostly straight 8ths: 71 of 123 two-bar windows hold exactly 16 onsets.
- **autochart's final minute is thin.**
  - In the 57.5 s from 341.5 s, the other stem has 230 detected onsets. autochart Expert has 98 notes there, chartgen 332 and STRUM 258 [R climax_windows.json]. Before 340 s, autochart has 1,029 notes against 1,176 onsets.
  - The earlier CPU take with the same seed is also thin there: 88 onsets in 340–400 s, against 104 in the GPU take. Its Hard take has only 22 [R ac_takes.json].
  - Takes also differ elsewhere: 239 vs 166 Expert onsets in 120–180 s [R ac_takes.json]. A single take is not representative.
- **The Expert end at 400.85 s is not a cap.**
  - No job was killed, and the most tokens any job used was 3,906 of 8,192 [CN c2_timing.json].
  - Other takes chart 13–21 notes (1.1–1.8% of Expert) in 401–406 s. There the other stem fades from about −20 to −33 dB and still holds 29 librosa onsets [CN c5_ac_takes.json; RC b_tail2.json, b_tail3.json].
- **For a listening check:** both of autochart's half-tempo stretches begin where its Expert solos begin (67.9 s and 218.1 s). They are probably musically distinct passages, but nobody has listened.

### 4.2 Drums: STRUM only [DB]

**Calibration first** (take_me_out, the one song with real multitrack stems). The drum-onset proxy scores the human chart at F1 0.876 on the real drum stems, and STRUM's CPU chart at 0.813 (0.932 directly against the human chart) [DB calib_drums.json].

| measure | STRUM | reference point |
|---|---|---|
| all hits vs drums stem, P / R / F1 @50 | **0.951 / 0.843 / 0.893** | Threshold ×0.5 to ×2 gives F1 0.79–0.93. 1,140 of the 1,238 Expert hits carry a cymbal. |
| kick recall | 0.35 raw, 0.50 once snare bleed is removed | – |
| kick-like onsets with no kick or snare charted | **71** | human chart on take_me_out: 0; STRUM CPU there: 12 (with "no kick" alone: 120 / 1 / 13) [DB class_lookalike.json] |
| timing, STRUM minus proxy (raw) | **+33.9 ms** (by region: 45–165 s +38.0, 165–215 s +18.9, 215–401 s +23.1) | The human chart on take_me_out is +8.75, so STRUM is about 25 ms late against that one-song convention (about +29 / +10 / +14 by region). On the references, STRUM drums were −8.5 ms [SC]. Blaming the 69.7 ms phase estimate is an inference: on take_me_out the GPU and CPU runs share a phase offset yet differ by 24 ms. |
| groove | 149 of 209 kicks on beat 1, 174 of 209 snares on beat 3; drops hi-hat 8ths in 240–260 s and 310–340 s (recall 0.54 and 0.68) | – |
| coverage | First hit at 42.746 s, which is the drum entry (the stem is silent before 42.70 s). Last hit 401.21 s. | no missed intro |
| ladder, onsets X / H / M / E | 1238 / 1220 / 860 / 398; **Hard = 0.985 of Expert; Easy has 0 cymbals** | human: 0.85 / 0.65 / 0.53 of Expert; 34–59% cymbals on Easy |
| star power / fills | 8 phrases, none after 230.4 s. 8 activation lanes of 2 beats, **all inside star-power phrases.** | human refs: 2 of 89 lanes overlap a star-power phrase (1 lies fully inside) [CN c8_misc.json] |
| issues | 26 off-grid notes in 13 pairs; scan-chart flags one of them (`brokenNote` at 03:09.13) | – |

### 4.3 Bass: STRUM only [DB]

| measure | STRUM test song | STRUM CPU, take_me_out | human, take_me_out |
|---|---|---|---|
| combined proxy F1 @50 / @100 | **0.476 / 0.635** | 0.578 / 0.773 | 0.835 / 0.864 |
| pitch-change coverage @100 | 0.661 | 0.808 | 0.781 |
| lane follows pitch, on pitch changes | **0.331** (59% of pitch changes keep the same lane) | 0.414 | 0.815 |
| timing vs proxy | +22.6 ms, about 16 ms later than human | +20.6 | +6.2 |
| gaps | 54 of 309 active seconds have no note; 16 gaps of 2 s or more, e.g. 300.0–303.4 s | – | – |
| ladder, onsets X / H / M / E | 661 / 455 / 269 / **16**; 7 of 8 star-power phrases empty on Easy | – | 0.89 / 0.61 / 0.45 of Expert |

**Caveats.**
- These proxies were calibrated on one song with clean multitrack stems; the test song uses Demucs stems.
- The flux proxy over-counts inside long bass notes on this song.
- pYIN can make octave errors [DB].

---

## 5. Speed, hardware and install

### 5.1 Measured speed (RTX 5070, WSL2) [P timing.json][DL]

| | s per audio minute (6 refs, mean, range) | test song 6:52 |
|---|---|---|
| autochart, all 4 difficulties | 87.6 (36.6–130.3) | 652.8 s |
| autochart, Expert only | 44.8 | 228.8 s |
| chartgen | 12.9 (12.1–13.4) | 82.7 s |
| STRUM (guitar, bass and drums) | 12.9 (10.7–21.2) | 87.3 s |

- **autochart is slow because it decodes token by token, not because of the GPU.**
  - Expert decoded at 12.3–40.7 tokens/s on CUDA and at 10.1–35.2 on the shared sandbox CPU.
  - The design critique benchmarked the Fretformer decoder step on 3 CPU threads: about 8.6 + 0.0079·L ms per token at context length L. So long songs cost more than linearly [CR].
- **Each autochart difficulty is a separate run.** Using only autochart's Expert and making the lower tiers ourselves cuts its cost on the test song from 652.8 s to 228.8 s.
- **Rough budget for option B on the test song.**
  - One autochart Expert take (228.8 s) plus STRUM (87.3 s) is about 5.3 min of measured tool time.
  - Three Expert takes (§7.6) cost 3 × 189–229 s ≈ 9.5–11.4 min of autochart alone. Whether later takes reuse its separation is unmeasured.
  - autochart always runs its own htdemucs_6s and cannot take our stems, so separation runs twice.
  - Keeping autochart's own lower tiers makes one take about 12.3 min.
  - Our own stages and the 4070's speed are unmeasured.
- **Memory.**
  - GPU: chartgen peaks at 4.3–5.7 GiB (4.6–6.2 GB) above the desktop's share, and STRUM at 4.4 GiB (4.7 GB) on the test song. autochart was not sampled [P; CN c2_timing.json].
  - RAM: unmeasured for every tool. Two STRUM runs died in a WSL VM reported at about 15.5 GB, and one finished at a reported 24 GB (§2.3).

### 5.2 The friend's Windows PC (RTX 4070): none of it tested on Windows [P]

| tool | install for a non-technical user | GPU path on Windows |
|---|---|---|
| autochart | **Easiest.** A native `.exe` installer or a portable `.zip`. It is unsigned, so SmartScreen asks "Run anyway". It downloads 952 MB at first launch and needs no Python. There is also a browser version at app.autochart.org (not tried). [doc] | ONNX Runtime: WebGPU by default, CUDA as an option |
| chartgen | Doable. Double-click `install.bat`: it installs Python 3.13 and torch for CUDA 12.6 (fine for a 40-series card; a 50-series card needs cu128) and downloads about 3 GB. Turn lyrics off: they download 1.7 GB and send the artist and title to lrclib.net. [doc] | PyTorch CUDA |
| STRUM | **Not for a non-technical user.** No installer, no GUI, no Windows notes. 1.7 GB of weights to lay out by hand. A TensorFlow pin breaks on Python 3.12. The realistic route is WSL2. | PyTorch CUDA 12.8 |

- **4070 memory.** A desktop RTX 4070 has 12 GB and a laptop one 8 GB (general knowledge, not measured). The GPU peaks measured above fit either.
- **Host RAM is a risk, not a measurement.** STRUM's own peak is unknown (§2.3), and so is the friend's RAM.
- **Python on Windows.** [D §7] notes that Smart App Control blocks an unsigned `python.exe` with no per-app exception [untested]. That affects chartgen, STRUM and any Python stage of songcharter.
- **Speed.** The 4070 was not measured. autochart's decoding is barely GPU-bound, so expect similar times there [est.].

### 5.3 CPU-only fallback [P][AD]

| tool | measured | for the 6:52 test song |
|---|---|---|
| autochart (4-CPU shared sandbox) | Expert only: 69.9 s per audio minute (mean). All four difficulties: 214–559 CPU-s per audio minute. | Expert 426 s; all four 885.5 s |
| STRUM (4-CPU shared sandbox) | 174–1,189 CPU-s per audio minute (4 songs); wall time cannot be separated from lock waits | 20–136 CPU-minutes (computed from the per-minute range) |
| chartgen (4-CPU shared sandbox) | A 30 s clip was killed after 585 s (exit 137). The README claims about 20 min for a 4-min song [doc, unverified]. | not verified |
| ADTOF drums (fusion, htdemucs_6s included; 3 threads; §3.6) | 73–122 s wall per reference song, of which separation took 60–143 s [AD run.log] | 173 s |

A CPU fallback is feasible for autochart's Expert and for ADTOF drums. STRUM's drums on CPU will take tens of minutes for a long song, and its wall time on a normal PC is unmeasured.

---

## 6. Each tool

Failure modes are tagged **[S]** (scaffolding we can replace: tempo, grid, tiers, star power, sustains, fills, sections) or **[M]** (the note model itself). Speed, install, licence and activity are not tagged.

| | autochart | chartgen | STRUM |
|---|---|---|---|
| **Strengths** | Best guitar notes by far (0.86, 6/6 wins), though not above an 8th-grid oracle on the two community-charted songs. Best placement proxies and human-like timing on the test song. Human-like lower tiers on the 4 Harmonix songs. Named sections and solos. The easiest Windows install. The app already compares takes, edits notes, inpaints chosen bars and fills in missing difficulties [AC README, model card]. A headless job interface that can take an external tempo map (`source_chart_sync`); it is an internal Electron-to-engine contract, not a released CLI (§7.3). Active: 148 commits in the last 30 days. | A complete, consistent package: nested ladder, star power, solos, taps. Plain Python functions per stage, so swapping in an external tempo map is one call. MIT code. Fast: 12.9 s per audio minute. | The only drum and bass charter of the three. Good drum onset timing (0.90 pad-blind; on the test song, precision 0.95 and the right entry and end). Its single tempo marker is right for steady-tempo songs. Fast: 12.9 s per audio minute. The drum stage can run alone on a drum stem. |
| **Failure modes** | [S] Picks the wrong metrical level in places (half tempo at 67–90 s and 219–230 s on the test song). [S] Bar lines on the snare from 90 s. [S] No star power (the model cannot produce it). [S] Sustains run into the next note (`badSustainGap`). [M] Sampled decoding, so takes differ (take_me_out 0.880 vs 0.914 even with the same seed). [S] Difficulties are not nested. [M] Thin final minute on the test song. [M] Per-job limits of 1,280 beats and 8,192 tokens [AC manifest]. Dense songs hit the token cap first: Lucretia Expert used 9.0 tokens/beat, so about 910 beats [CN c2_timing.json]. Slow: 95 s per audio minute for all four tiers on the test song. | [S] Notes are late (+27.7 ms mean on the references), quantized to a late librosa grid. [M] F1@50 only 0.57 (ceiling 0.71). [S] Off-beat grid at 319–340 s. [S] Bar lines one beat before the kick. [M] Over-charts (1.18× density; 1.72× on drunk_drivers). [S] Generic section names. Separator weights of unknown licence. Main branch idle since 2026-09-17. | [M] Weak guitar (0.59) and bass (0.59); fails outright on kimochi_warui guitar (0.30). [M] Bass lanes barely follow pitch. [S] Two stacked reduction passes leave Easy nearly empty. [S] Drums: Hard ≈ Expert, and Easy has no cymbals. [S] Star power placed on Expert only, then emptied on Easy. [S] Fills tied to star power, not to the music. [S] One tempo marker, so it fails on drifting songs. [M] Simplified kick patterns. [M] Weak toms (green 0.40). Two runs on the 7-min song died in a WSL VM reported at about 15.5 GB (unlogged). No installer. 18 unsafe `torch.load` calls. Idle for 175 days. |
| **Licence** [P] | Code AGPL-3.0-or-later. Fretformer weights CC BY-NC-SA 4.0 (non-commercial, share-alike). Bundled Demucs: code MIT, htdemucs_6s weights "not clear", likely CC BY-NC per its author. Beat This MIT. Training data not stated. | Code MIT (LICENSE file). Separator checkpoint "license: unknown". Basic Pitch Apache-2.0. | "MIT" in the README, pyproject and HF tag, but **no LICENSE file in its git history**. Guitar weights trained mostly on commercial game charts with isolated stems (91%, §2.4). Drums are probably similar, though the README says "~5,000 human-authored pro drum charts from the Clone Hero community". htdemucs_6s as above. |

Count: 14 [S] and 9 [M] (autochart 5/3, chartgen 4/2, STRUM 5/4).

---

## 7. Recommendation

### 7.1 The options

| option | goal | quality now | effort [est.] | licence | verdict |
|---|---|---|---|---|---|
| (A) one tool as-is | 2 | autochart: guitar only, no star power. STRUM: all instruments, but guitar and bass at 0.59 and Easy broken. chartgen: guitar at 0.57. | none | depends on the tool | **Fails for Goal 2:** no tool covers guitar, bass and drums well. |
| (A′) autochart app plus a manual polish pass | 1 | guitar ≈ autochart (best measured), with our star power and sustains and a check of its two half-tempo stretches | small: takes, inpaint, a Moonscraper pass, a playtest | personal, non-commercial use; see §7.3 on audio | **Recommended for Goal 1** if the friend plays guitar. |
| (B) pipeline: best model per instrument plus our scaffolding | 2 | guitar ≈ autochart; drums ≈ STRUM or ADTOF (§3.6); bass ≥ STRUM; tempo, tiers and star power by our rules | medium to large: new tempo, re-timing, tier, star-power and adapter stages; two runtimes (Node + onnxruntime for autochart, PyTorch for STRUM); a Windows installer. Already in `songcharter/`: the chart writer, TempoMap builder, lead-in planner, sync check and packaging (tests not run for this report). In progress at the time of writing: a drum-stem beat grid (`beatgrid.py`) and the seconds-based note model for importers (`timed.py`). | an MIT core is possible, but the product is non-commercial in practice (§7.3) | **Provisional for Goal 2**, pending §7.2b and the owner's licence answer. |
| (C) train our own models | 2 | unknown; no data or baseline of our own | large: dataset, training compute, ML work | clean code, but no licensed chart corpus exists | Not now. Revisit for bass after the reference set grows. |
| (D) extend autochart upstream, or fork it (AGPL) | 2 | as B for guitar; drums and bass would be added to an app that already has the UI, takes, editing, inpaint and export | medium, uncosted: needs upstream cooperation or a fork; STRUM's PyTorch drum stage would still need a second runtime or a port [untested] | AGPL plus CC BY-NC-SA: loses little if non-commercial is accepted anyway | **Cost it against B** once the owner answers on licence. |

Progress for B and D can be measured with the scorer (all instruments and tiers) plus the reference-free audits. With 6 songs that measurement is only coarse (§2.4).

### 7.2 Per instrument (Goal 2): where to start and what we add

| instrument | start from | what songcharter adds |
|---|---|---|
| Lead guitar | **autochart Fretformer 2**, Expert, as a separate process. Keep its own Hard/Medium/Easy only if they beat our reduction on the Harmonix songs, judged over several takes; today they score 0.86 / 0.81 / 0.79. | Our tempo map: re-quantize its note times onto our map, and also test feeding our map in through `source_chart_sync`, whose quality is unmeasured. Sustain trimming (≥40 ms gap). Star power. Nesting checks (Hard ≤ Expert). Re-generation (inpaint) of thin passages. Windowing for songs over the beat or token cap. A fallback without the NC Fretformer weights: chartgen's Basic Pitch route with Demucs in place of its unknown-licence separator. Its quality with Demucs is unmeasured, and it is not licence-clean, since the Demucs weights' licence is unclear. |
| Drums | **Not chosen yet.** ADTOF has the better onsets and kicks, STRUM the better lanes (§3.6). The test song starts from STRUM's drums. For the product, try a lane classifier on ADTOF's activations, then re-score both with `eval/scorer/score.py` once it resolves disco flips. | One global timing offset first, then a playtest. Per-hit snapping to drum-stem onsets only if regional drift is shown to matter and is calibrated on more than one song. Quantize to our map. Reduce to Hard/Medium/Easy following Clone Hero/Rock Band practice (Easy keeps kick, snare and the main cymbal). Fills where the music has fills. Star power. Later: missed syncopated kicks and tom quality (green pad F1 0.40 for both models). |
| Bass | **STRUM bass onsets as a baseline only** | Re-laning from pitch (pYIN on the bass stem), a timing shift, filling of uncovered held notes, our reduction. Score the [D] rule-based bass engine against it on the 5 bass references and keep the better one. On take_me_out a stem-onset detector matched the human bass chart at F1 0.84 [DB], but it was tuned on that very song and its clean stem, so this is a hint, not evidence. |
| Tempo map (all) | Beat This (MIT; autochart already uses a fine-tuned copy) with [D]'s level fold and DP decoder, or the drum stem (a first drum-stem grid is in `songcharter/beatgrid.py`, unscored) | **Octave and phase control:** pick one global metrical level, and reject runs at half or double that period, judged against the global period. (autochart compares against a 9-beat local median, which fails inside long runs.) Lock beat 1 to the kick. Refine each beat to drum-stem onsets, then apply the calibrated beat-line convention. That constant depends on the onset detector: 14–18 ms (2 songs) with the audit's rising-edge picker, and 20.4–24.1 ms with envelope peaks, which is why `beatgrid.py` uses −22 ms [here, `songcharter/beatgrid.py` docstring]. Then `TempoMap.from_beats` and `plan_lead_in`. Marker count is cosmetic, and a few ms of jitter does not matter [RC c_tempo.json]. |
| Song-level | – | Sections (named sections where models agree; later our own structure analysis). Solos. `song.ini` with the correct artist and title and a note that the chart is AI-generated. Packaging with sync verification (exists). A scan-chart gate: no `emptyStarPower`, `brokenNote`, `noStarPower` or `badSustainGap`. Lower tiers: compare our reducer with existing generators (EasyChartGenerator; Onyx and midi-ch are GPL, so only as separate programs or as references) [D]. |

### 7.2b Reconciling with the design document ([D], with the critique [CR])

The two documents disagree on several stages. [D]'s figures come from excerpts and its own harness; only ADTOF has since been scored with `score.py` on full songs (§3.6).

| stage | [D] (corrected by [CR] where they differ) | this report | how to decide |
|---|---|---|---|
| separation | htdemucs_6s; BS-RoFormer SW opt-in | htdemucs_6s shared pass | same; both face the unclear weight licence |
| tempo | Beat This `final0` + level fold + DP; grid vs drum-stem onsets 5.9 ms median on the test song [D §2.3, §3.4, §5 M1]. [CR]: drumless passages (the tracker was about 30 ms late on the test-song intro) and rubato are not handled. | Beat This or drum stem + octave/phase control | the same idea; score the prototype's beats on the 6 references (beat F1, with Lucretia separately) |
| guitar | Fretformer 2 weights through our own onnxruntime driver (no AGPL code), 3 seeded takes, a take selector. [CR]: this "Engine A" has never been scored (its κ and F1 evidence belongs to the autochart app; the excerpt runs fed misaligned stems), and a CPU take costs about 2–3.5 min [est., from a decoder benchmark]. | autochart engine as a separate process | The driver avoids AGPL and double separation and takes our stems and beats, but the NC weights remain. Compare on the references over several seeds. |
| drums | ADTOF, mix + stem fusion. [D §2.9] gives pro-lane F 0.844 as the mean of 5 excerpts. [CR]: thresholds were tuned on 2 of those excerpts and all 5 come from 2 songs, so the held-out figure is 0.813 and generalisation was unmeasured. STRUM was only an M5 candidate. | STRUM's drum stage | Now measured on whole songs (§3.6): onset F1@50 0.967 vs 0.897, exact lane agreement 0.585 vs 0.687. Decide after the lane-classifier experiment. |
| bass | rule-based engine (HFC onsets + pYIN + rank frets), onset F 0.863 on Demucs stems. [CR]: a same-song excerpt figure, snapped to the oracle (chart) grid. | STRUM as baseline, own DSP prototype | score both on the 5 bass references |
| tiers | Onyx-style deterministic reductions (re-implemented; GPL code not copied). [CR]: the planned Standard padding keeps 97–100% of Expert onsets on Hard for 8th-note parts, and scan-chart's `difficultyNotReduced` only catches identical tracks, so Hard needs thinning toward about 0.75–0.8 of Expert. | our reduction | same, with a Hard/Expert ratio check (Harmonix Hard 0.75 [D §2.11]) |
| packaging | Windows installer with uv and a PyTorch build picked from `nvidia-smi` | M6 Windows build | [D]'s plan is more detailed; adopt it |

### 7.3 Licensing (not legal advice) [P]

- **Code licences.** Our code (MIT), Demucs code (MIT), Beat This (MIT, code and checkpoint) and Basic Pitch (Apache-2.0; ship its LICENSE and NOTICE) can all be combined under MIT, keeping their notices.
- **Weight licences are the binding ones.**
  - Fretformer weights: CC BY-NC-SA 4.0.
  - ADTOF weights (`xavriley/ADTOF-pytorch`): CC BY-NC-SA 4.0 [D §2.9, §4.2; doc]. They were trained on third-party custom charts [CR; doc].
  - Demucs weights: the author writes that their licence "is not clear" and that htdemucs_6s, trained only on Meta's internal data, "likely" falls under CC BY-NC [doc: Demucs README, github.com/adefossez/demucs; local copy lines 321–325]. autochart's README calls them MIT; the Demucs README is the author's own statement [CR]. autochart, STRUM and our shared pass all use htdemucs_6s.
  - STRUM weights: tagged MIT, but there is no LICENSE file, and they were trained on commercial game content (§2.4). Treat them as provenance-encumbered whatever the tag says, and fetch them at run time rather than vendoring them.
  - chartgen's separator: "license: unknown". Do not bundle it.
  - This evaluation found no separator with an explicitly permissive weight licence, so there is no "fully open" route yet.
- **Consequence.**
  - The shipped tool is in practice free and non-commercial: no paid tier, no ads. The owner should accept that explicitly.
  - If it is accepted, an MIT core buys little over an AGPL design (option D) and still costs the process boundary: two runtimes, no shared stems, no control of autochart's tempo stage.
  - An MIT core keeps the option of swapping the NC parts out later.
- **autochart, if kept as a separate program (B).**
  - Never import or port its code; doing so would make all of songcharter AGPL.
  - Its job/result contract is an internal Electron-to-engine interface ("Keep this job/result shape … stable", `docs/engine-integration.md`), and only the app is released [AC]. So we would build, host and update the engine ourselves (Node 24, onnxruntime-node, an FFmpeg build). That means AGPL source obligations plus FFmpeg's LGPL. The alternatives are to drive the user-installed app or to propose a supported CLI upstream.
  - Its v0.1.0 release check on a Windows Server CI runner reported a display-adapter timeout and selected CPU [AC testing-status.md]. GPU selection on the 4070 is untested.
  - Pin revisions, check hashes, and show the attribution text.
- **Audio.**
  - A song folder carries a `song.ogg` made from a copyrighted recording, so sending it to the friend is distribution. chartgen's README says "keep it local", and this repo never commits audio (`.gitignore`).
  - Prefer that the friend uses their own copy, and generate on (or verify sync against) the exact file they will play: decode paths can differ by the MP3 encoder delay, which is 1105 samples (25 ms) on the test MP3 [D §2.1].

### 7.4 Goal 1: the friend's test song

0. **Ask first:** which instrument(s) does the friend play, and will they play from the same MP3 file?
1. **Lead guitar (A′, recommended).**
   - In the autochart app: generate 2–3 Expert takes and pick one. Inpaint or regenerate 341–399 s, where the GPU take has 98 notes against 230 stem onsets [R climax_windows.json].
   - Moonscraper pass:
     - add star power (autochart has none);
     - trim sustains to leave ≥40 ms gaps (`badSustainGap`);
     - check the half-tempo beat lines at 67–90 s and 218–231 s;
     - check the lower tiers (they are not nested; the app can regenerate them).
   - Package with the friend's exact audio file, run `node tools/scan-chart/scan.cjs <folder> --notes`, then playtest on the 4070 PC.
2. **Drums or bass, if wanted.**
   - **Quick route:** STRUM's test-song chart as it is, mapped back to the original audio (input time = chart time + 69.7 ms), with one global shift for its lateness. The shift is about 25 ms, from a one-song calibration; confirm it by playtest. Its Easy tiers are known to be broken. The ADTOF test (§3.6) also favours STRUM's drum lanes for now.
   - **Time-boxed merge**, only if the quick route fails the playtest.
     - Inputs, all local only: the GPU run's autochart and STRUM test-song charts (bundled by `eval/gpu.sh results`), the htdemucs_ft stems, and the 800 local drum beats from the guitar audit [G s3_local_beats].
     - Each step below is new code, and none is estimated. The first pieces, `songcharter/timed.py` and `songcharter/beatgrid.py`, are in progress.
     - Steps:
       - Build one tempo map from the drum beats, with beat 1 on the kick, using `TempoMap.from_beats` and `plan_lead_in`. 800 of the 976 beats were found within ±60 ms of the rigid grid; fill the 176 missing ones from the grid, the drumless intro before 42.7 s included.
       - Re-quantize autochart's guitar onto it. This removes the half-tempo beat lines and the snare-phase bar lines.
       - Apply one global shift to STRUM's drums and bass, then quantize. Clear the 26 off-grid drum notes, drop the bass notes after 402.4 s (where the stem is silent), and re-lane the bass by pYIN pitch.
       - Rebuild the drum and bass tiers (keep cymbals on Easy), add star power checked non-empty on every tier, and drop STRUM's fills.
       - Add sections where autochart and STRUM agree (about 43–44, 90–91, 110–112, 167 and 207–208 s).
       - Package with `build_song_folder` (sync check under one sample) and the correct `song.ini`. Check that scan-chart is clean, re-run the audits' reference-free checks, and report the offsets.
3. **Use the playtest's feedback** to decide how much of B is worth building.

### 7.5 Milestones for Goal 2

Effort is an estimate [est.].

| # | milestone | done when |
|---|---|---|
| M1 | **Windows spike on the 4070 PC** (small). Install the autochart app; run STRUM's drum stage (native or WSL2); check SmartScreen and Smart App Control. | Peak RAM (RSS, e.g. `/usr/bin/time -v` in WSL), VRAM and wall time are measured on the test song, and the friend's RAM is known. |
| M2 | **Evidence before gates** (medium). Grow the reference set (local use only) with community charts first uploaded after each model's release (Fretformer 2 was released in September 2026 [CR]). Run 3–5 autochart seeds per song. Make `score.py` resolve disco flips [D §3.3]. Try a lane classifier on ADTOF's activations. Score the [D] tempo and bass prototypes with `score.py` on the same full songs. | The per-song seed spread is known; a component is chosen per stage (§7.2b); the set grows towards about 50 songs for 0.05-level comparisons. |
| M3 | **Pipeline v0.1, any MP3** (medium to large). Shared Demucs pass, tempo stage, adapters, re-timing, packaging, scan-chart gate. | No regression per song against the best single tool, judged over several takes, with per-song tolerances at least the run-to-run spread seen so far (up to 0.035 on autochart Expert, 0.151 on one Medium, 0.087 on STRUM drums [RV v3_groups.json]). Beat F1 reported without Lucretia, and no half- or double-tempo runs on the others. 0 `emptyStarPower`. |
| M4 | **Our own tiers, star power, fills, sections** (medium). | Nested tiers at human-like ladder ratios (Hard clearly below Expert; [CR] proposes failing at ≥ 0.9 of Expert onsets), no empty Easy, scan-chart clean. Claims of "better than STRUM or autochart" only on M2's larger set. |
| M5 | **Bass** (medium). Pitch-following lanes, recovery of held notes. | Lane direction clearly above the trivial baseline, and F1@50 at least STRUM's, on M2's set. |
| M6 | **Windows build for the friend** (large). Installer, first-run downloads with hashes, a CPU fallback. | It installs on the 4070 PC without help, with peak RAM within that PC's limit and timings measured there. Only after M2's set exists, decide whether C is worth it for any instrument (bass is the likely one). |

### 7.6 Risks

| risk | what to do |
|---|---|
| Non-commercial in practice: Fretformer and ADTOF weights CC BY-NC-SA, Demucs weights unclear (htdemucs_6s likely NC), STRUM weights trained on commercial game content | The owner decides explicitly (§8). Fetch weights at run time. Do not call any route "fully open". |
| autochart changes fast (148 commits in 30 days), its job interface is internal, and its takes vary run to run | Pin the commit and model revision. Consider several takes per song, choosing per section by the precision proxy. That proxy is weak (Spearman 0.515 with true F1, p = 0.13), so treat this as an experiment. |
| Reference scores inflated by training overlap: certain for STRUM guitar on 4 songs, probable for STRUM drums on 3, unknown for autochart, possible for ADTOF (trained on custom charts) | Add references that post-date the tools or are clearly outside their training (M2). |
| STRUM: no LICENSE file, only 5 of 7 ensemble models load, unpublished tom/cymbal and drumsep models, idle for 175 days, unsafe pickle loads | Ask the author. Force `weights_only=True`. Isolate its drum stage behind our own interface so it can be replaced; ADTOF is the first candidate, and its gap is lane mapping (§3.6). |
| Host RAM on long songs (STRUM's peak unmeasured) | Measure it in M1; chunk the audio if needed. |
| `source_chart_sync` quality unknown; Clone Hero's handling of fills and `badSustainGap` unknown | Measure in M3/M4; playtest. |
| Lane scores on Harmonix references with disco sections (`score.py` does not resolve them) | Fix in M2 before choosing the drum engine. |
| A 6-song evaluation | M2 |

---

## 8. Caveats and open questions

- **Test-song numbers are proxies**, not ground truth. They were calibrated on 1–6 reference songs, mostly with clean multitrack stems; the test song uses Demucs htdemucs_ft stems. Nobody listened to the audio or played any chart.
- **chartgen's corrected guitar score** is a bound (0.711) plus an estimate (about 0.64). Its reference-song charts were not in the GPU bundle, and no CPU run exists [RC].
- **The calibration constants are small-sample.**
  - The 14–18 ms beat-line convention comes from 2 songs and is specific to the detector (§7.2).
  - The drum (+8.75 ms) and bass (+6.2 ms) human-minus-proxy offsets come from take_me_out only.
- **autochart is sampled, and its two runs are not independent.** Both used seed 20260609. Its test-song ladder, end point and final-minute density change between takes, so judge it on several seeds.
- **STRUM's run mode.** The GPU run's mode (as shipped vs fixed) is not recorded. `eval/drive.sh` defaults to `STRUM_MODE=as_shipped`, and `eval/gpu.sh` does not set it, so the run was probably as shipped unless the environment overrode it. Both runs loaded 5 of 7 ensemble models.
- **Not tested:**
  - any native Windows install;
  - the RTX 4070's speed;
  - autochart's GPU memory;
  - any tool's host RAM, and the friend's RAM;
  - chartgen's CPU speed;
  - ADTOF on a GPU or on Windows, and ADTOF's test-song chart;
  - the [D] tempo and bass prototypes on these full songs;
  - in-game handling of activation lanes inside star-power phrases, and of `badSustainGap`.
- **Song metadata.** `README.md` names the first song as "Love Isn't Love Enough" by "Beast Monster Thing". The correct metadata is Car Seat Headrest, "Beast Monster Thing (Love Isn't Love Enough)" [D §2.14]. Fix the README before writing `song.ini`.
- **Open questions for the owner:**
  - Which instrument(s) does the friend play, and will they play from the same MP3 file?
  - Is a non-commercial songcharter acceptable (autochart's and ADTOF's weights, and likely htdemucs_6s)? If so, is AGPL (option D) acceptable too?
  - Should the friend's tool be a native Windows app, or is WSL2 acceptable?
  - How much RAM does the friend's PC have?
  - Should drum fills be charted (they need a fill detector) or left out?

---

## Review log

Each issue was checked against its sources before anything was changed. The checkers reviewed the first draft, which is byte-identical to the report file that was then saved, so their locations apply. Two extra fixes turned up while verifying:
- autochart's all-tier mean is 87.6, not 87.5 s per audio minute (exact 87.56);
- the drunk_drivers ladder (611 vs 626) is from the CPU run.

Rows 38–42 record the changes made for this repo version.

| # | checker | issue | verdict | reason / change |
|---|---|---|---|---|
| 1 | numbers | report file not written | applied | The revision was saved as the report; this file derives from it. |
| 2 | numbers | 15.5 GB / 24 GB unlogged | applied | No log records RAM; the figures come from the owner's report. Reworded as reported, with cause and peak unmeasured (§2.3, §5, §6, §7.5–7.6). |
| 3 | numbers | "the two lowest are the two CSH songs" is false | applied | 0.7768 DD, 0.8092 Creep, 0.8126 KW. The inference was replaced by the CSH-pair paragraph (§3.5). |
| 4 | numbers | badSustainGap range | applied | 29–336. |
| 5 | numbers | Lucretia beat F1 range | applied | 0.26–0.29 (§3.3, §3.5). |
| 6 | numbers | 3 of 89 lanes | applied | 2 overlap, 1 of them inside. |
| 7 | numbers | mixed kick definitions | applied | 71 / 0 / 12 (no kick or snare), with 120 / 1 / 13 noted. |
| 8 | numbers | 13–21 are chart onsets, not audio | applied | Reworded; b_tail3 has 29 other-stem onsets in 401–406 s. |
| 9 | numbers | offset-lift numbers mis-tagged | applied | Tagged rematch.json `global`, CPU runs, 4 / 3 songs. |
| 10 | numbers | gap "mostly lateness" | applied | 67–80% for STRUM, about 51% for chartgen (estimate). |
| 11 | numbers | SD 0.122 is a detector pair | applied | Tool-pair SDs 0.106 / 0.127 / 0.219 → 36 / 51 / 151 songs; 0.122 attributed to the research analysis. |
| 12 | numbers | MiB reported as GB | applied | 4.3–5.7 GiB (4.6–6.2 GB); 4.4 GiB (4.7 GB). |
| 13 | numbers | timing source unstated | applied | Both the mix and the other-stem figures are given. |
| 14 | numbers | chartgen range | applied | 12.1–13.4; 12.0 was the test song. |
| 15 | numbers | STRUM ratio / issue counts | applied | Ratio labelled CPU runs, 4 songs; smallLeadingSilence 3–7 and brokenNote 6–8, each on 3 songs. |
| 16 | numbers | 13 pairs vs scan-chart | applied | scan.json has one `brokenNote`. |
| 17 | numbers | nesting evidence | applied | Recount (v2_nesting.json): 74.3% of Hard onsets are in Expert. |
| 18 | numbers | bar-line phases | applied | s3b phases confirmed, including chartgen's move to phase 2 from 330 s. |
| 19 | numbers | constant-tempo songs | applied | Lucretia, Take Me Out, shadowplay. |
| 20 | numbers | phase cause; raw regional offsets | applied | Same 300.1 ms phase in both take_me_out logs, yet 24 ms apart. The cause is labelled an inference, and the regions are given raw and adjusted. |
| 21 | reasoning | answers the tool question, not the friend's | applied | Split into Goal 1 (A′, instrument question first) and Goal 2 (§1, §7.1, §7.4). The app features are confirmed in autochart's README and model card. |
| 22 | reasoning | Demucs weights treated as MIT | applied | The Demucs README (lines 321–325 of the local copy) confirms the problem. Code and weight licences are now separate, "fully open" is dropped, and an owner decision is added. |
| 23 | reasoning | STRUM provenance mis-described | applied | 3,732 of 4,089 guitar songs come from commercial games; the holdout paths sit under game folders. |
| 24 | reasoning | contamination; 8th-grid oracle | applied | grid8 0.862 / 0.773 vs autochart 0.813 / 0.777. Harmonix numbers labelled possibly inflated; F1 gates deferred. |
| 25 | reasoning | missing alternatives; DESIGN.md not reconciled | applied | Option D and §7.2b added; ADTOF and the design prototypes to be scored in M2. No scoring was run at the time (ADTOF has since been scored: row 39). |
| 26 | reasoning | gates inside noise; risky order | applied | Windows spike first, evidence second, non-regression gates, Lucretia separate, coarse efforts (estimates). |
| 27 | reasoning | "stable headless CLI" | applied, one detail corrected | The contract is internal and only the app is released. The CPU fallback happened on a Windows Server CI runner, so "silently on Windows" overstated it. |
| 28 | reasoning | 8,192-token cap omitted | applied | From the manifest; Lucretia at 9.0 tokens/beat → about 910 beats. |
| 29 | reasoning | inference factually wrong | applied | Same fix as #3. |
| 30 | reasoning | "a good drum charter (0.90)" | applied | The F1 is pad-blind, and 1,140 of 1,238 hits carry a cymbal. The wording is now "onset timing good, kicks and toms weak". ADTOF comparison planned for M2 (since done, §3.6). |
| 31 | reasoning | 15.5 GB unsourced | applied | Same fix as #2; peak RSS to be measured in M1. |
| 32 | reasoning | per-hit re-timing over-justified | applied | One global offset first, then a playtest; the +9 ms target dropped. |
| 33 | reasoning | budget omits takes and double separation | applied | 3 takes ≈ 9.5–11.4 min; double separation and the unmeasured 4070 noted. |
| 34 | reasoning | GPU/CPU same seed | applied | 14 of 18 identical; multi-seed runs in M2. |
| 35 | reasoning | "most faults are scaffolding" unquantified | applied | Failure modes tagged in §6: 14 [S] and 9 [M]; the model-side metrics named in §1 item 4. |
| 36 | reasoning | audio distribution and sync | applied | Note added in §7.3, plus a question in §8. |
| 37 | reasoning | canonical file missing | applied | Diffed: identical to the reviewed copy. |
| 38 | repo version | local working paths | applied | Replaced by the harness commands and repo files. Audit outputs, the design document and its critique are marked local only, because they derive from copyrighted songs and other people's charts. |
| 39 | repo version | ADTOF unscored | applied | §3.6 added from the ADTOF whole-song test. §1, §5.3, §7.1–7.6 and §8 updated to match. |
| 40 | repo version | ADTOF summary: STRUM's ±50/±100 gap called "lateness" | corrected | STRUM's drum medians on these songs run −19.9 to +1.7 ms, mostly early; the gap is timing error. |
| 41 | repo version | ADTOF summary: "snare hits on yellow" on take_me_out | qualified | The per-pad counts show the missing blue (ride) as well. The disco-flip caveat and the per-song lane split (the gap comes from 2 of 5 songs) were added from the score files. |
| 42 | repo version | §7.2b quoted design-doc figures that the critique corrects | applied | Drums 0.844 → 0.813 held-out (same 2 songs); bass 0.863 is same-song on the oracle grid; Engine A is unscored; Standard padding leaves Hard ≈ Expert. |
