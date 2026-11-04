# songcharter design document

*Version 2, 2026-11-02, revised the same day after two checkers' reviews (fidelity and feasibility). Version 1 was the design lead's synthesis of nine research reports. This version applies three later inputs: a critic's review of v1; a comparison of three existing auto-charters (autochart, chartgen, STRUM) on six human-charted songs and on the test song; and a whole-song ADTOF vs STRUM drum test. It also reads the code being written tonight and the checks its builders ran on it. Where the critique and v1 disagree, the critique wins unless newer evidence says otherwise. A choice that no source decides is tagged [decision]. Nobody has listened to any output or played any chart. Nothing has run on Windows or on an RTX 4070.*

*Updated later the same day to match the code that landed on `main` at commit e0e4b7e, after a review of the first
build (six reviewers, two verifiers per finding, fixers per file). The changes are listed at the end of §11. Nobody
has played the first chart yet.*

*Updated again on 2026-11-02 after the Goal 2 engines (drums, bass, sections; each built on a branch, reviewed and
fixed) were merged into `main` and the pipeline (`songcharter chart`, M3) was written and run end to end on the test
song and on Take Me Out. The engines' own measurements are tagged [here, drums engine run], [here, bass engine run]
and [here, sections engine run]; the end-to-end runs [here, pipeline run]. The changes are listed at the end of §11.*

*Updated on 2026-11-03 after a review of the integrated pipeline (errors and exit codes, devices, caches, memory
records, test coverage); the fixes are listed at the end of §11.*

*Updated again on 2026-11-03 for the pipeline's defaults (branch `pipeline-defaults`): Expert only, solos on the
sections named Solo (or by name), guitar takes by device, the preview, the work folder in the per-user cache (§9 Q30)
and the clip at the end of the audio; with three research results: the takes experiment and the strumming detector
(§2.7) and the solo evaluation (§2.10). Listed at the end of §11, with the fixes after that branch's review.*

*Updated on 2026-11-03 for the golden charts (branch `golden`, `eval/golden.py`, §3.6): the reference set built
before and after a change, every part's track hash compared.*

**Evidence tags:**
- **[here]**: measured by this project in the Linux dev container (4 CPUs, no GPU).
- **[here, 5070]**: measured on the owner's RTX 5070 under WSL2 (`eval/gpu.sh`).
- **[doc]**: taken from documentation, a paper, a model card or a leaderboard.
- **[est.]**: an estimate.
- **[untested]**: nobody has tried it.
- **[inference]**: reasoned from measurements, not measured itself.
- **[decision]**: a choice made in this document on judgement; no source decides it.
- **[code]**: read from this repository on 2026-11-02: at about 03:30 from branch `first-chart` at commit 6094e49 plus
  uncommitted work; statements updated after the first-chart review read `main` at commit e0e4b7e (§2.0); those
  about the engines and the pipeline read `main` after the engine merge and the pipeline commit.

**Evidence documents.** Each measurement is attributed to the document that made it. Apart from the comparison (`eval/REPORT.md`), these documents were written outside the repository on 2026-11-02 and are not committed. A script named without a repo path belongs to them.

| name | what it is |
|---|---|
| v1 | design v1 and its nine research reports (format, existing tools, auto-tools, timing, separation, transcription, conventions, evaluation, packaging) |
| critique | a review of v1: 12 errors (E1–E12) and 16 gaps (G1–G16), several of them re-measured (`ff_step_bench.py`, `reduce_sim.py`, `lagcheck.py`, `pyin_time.py`) |
| comparison | `eval/REPORT.md` in this repo: autochart, chartgen and STRUM, run on the 5070 and scored with `eval/scorer/score.py` against six human charts. Four audits come with it: test-song guitar, test-song drums and bass, reference-set claims, practicality. |
| ADTOF test | ADTOF and STRUM drums on whole reference songs, scored with `eval/scorer/score.py` (`run_adtof_refs.py`, `fuse.py`) |
| build checks | checks run tonight by the job writing the modules, on work-in-progress code, not reviewed: **beatgrid run** (`beatgrid` on the test song's drum stem and on four Harmonix references' original drum stems: `final_run.txt`, `refs_check_*.json`); **importer check** (`importers` against scan-chart on the three test-song folders: `importers_check/report.json`); **quantizer check** (`quantize` on the test-song outputs over a rigid 142.0009 BPM grid and over a grid made from the guitar audit's local drum beats moved 16 ms early: `quantize_check/run1.txt`, `result.json`). They are not among the brief's inputs. |
| review | the first-chart review of the test-song build: six reviewers, two verifiers per finding, fixers per file |
| takes | four autochart Expert takes of the test song (GPU take; CPU seeds 101, 202, 303), spliced for the v1 chart |
| engine runs | the Goal 2 engines' builders' measurements on the five references and the test song, with the shared seeded htdemucs_6s stems, scored with `eval/scorer/score.py`, and the reviews of each engine (**drums engine run**, **bass engine run**, **sections engine run**) |
| pipeline run | `songcharter chart` end to end in the dev container (CPU, 2 torch threads): the test song's MP3 and Take Me Out's `input.wav`, timed per stage with the peak RSS sampled; scored against the v1 chart and the human chart |
| takes experiment | four autochart Expert takes (seed 20260609 and 101, 202, 303, made on the 5070) of each of the six references, built through assemble one by one and spliced, scored with `score.py` against the human charts; a verifier re-checked it and corrected two points (§2.7) |
| strumming research | a detector of under-charted strumming from the guitar stem's pick noise, scored on the six references with leave-one-song-out tuning; a verifier reproduced it and corrected it (§2.7) |
| solo evaluation | every solo rule (off, labels, stems, the stem test on every section, their union and intersection) through `starpower.place_solos` on pipeline-shaped builds of the six references and the test song, on fold-0, ensemble and librosa sections, against the human solos and the two the friend confirmed (§2.10) |
| defaults review | the review of branch `pipeline-defaults` (options, cache, tests, docs), each finding reproduced by a verifier: among them a real autochart take traced with strace, a prune that fails partway with NTFS's name order imitated, and two real runs racing a prune |
| pipeline-defaults runs | `songcharter chart` with branch `pipeline-defaults`'s defaults in the dev container: Take Me Out and the test song on copies of their warm work folders, two 35-s cuts of Take Me Out (one with the work folder in the cache), and the clip's before-and-after on the excerpt that failed (§5, M3) |
| golden runs | `python -m eval.golden` in the dev container (CPU, 2 threads): the baseline of `main` at 11615e2 on the seven songs, two warm runs of it, a deliberate one-line change to the bass Hard reduction on a scratch branch, and `main` and that change built at the same time (§3.6) |

---

## 1. Bottom line

songcharter is a free, local tool. A song file goes in (MP3 or anything ffmpeg reads). A Clone Hero song folder comes out (`notes.chart`, `song.ini`, `song.ogg`), checked by scan-chart 8.0.1. The folder has lead guitar, bass and pro drums, plus star power, drum activation lanes, sections and solos: on Expert alone by default, as the friend asked after v1 (he plays Guitar on Expert), and on all four difficulties when asked (`--levels all`). There are two goals:

| | Goal 1: the test song, for the friend, soon | Goal 2: the any-song tool |
|---|---|---|
| What | A good chart of Car Seat Headrest, "Beast Monster Thing (Love Isn't Love Enough)", the streaming master (the MP3 container reports 412.395 s; the gapless decode is 412.363 s) | `songcharter`: any song file in, a song folder out, on the friend's Windows PC with an RTX 4070, used by a non-technical person |
| Gate first | Ask which instrument(s) the friend plays and whether they will play from the same MP3 (§9 Q1, Q5). The v1 chart was built for all three instruments before the answer, so the answer now decides which of M1a's rows are judged first (§5). Answered after v1: Guitar, on Expert; v1.1 is Expert only, with solos on the two he confirmed (§9 Q1). | — |
| Route | **Merge build** for the friend's instrument(s): import autochart's guitar and STRUM's drums and bass (both already ran on the 5070), re-time them onto our own beat grid, add our own tiers, star power, sustains and sections, pass the gate (§2.13), then a playtest. | **Option B, provisionally:** the best component per stage plus our own scaffolding. The guitar engine route and the licence shape wait on the owner (§9). |
| Why this order | The comparison put the autochart app plus a Moonscraper pass (A′) first for guitar, and STRUM's chart with one global shift first for drums and bass; it allowed the merge only as a time-boxed step if that quick route failed the playtest (comparison §1, §7.1, §7.4). This version reverses that order [decision]. Reasons: A′ needs our star power, sustain trimming, a fix for the two half-tempo stretches and lower tiers anyway, and the importers (exact against scan-chart [here, importer check]) and the quantizer now exist (§2.0). | — |
| New model runs | For guitar: done for the v1 chart, three CPU seeds beside the GPU take, spliced per section (§2.7). None for drums or bass. | All stages |
| Fallback | The comparison's quick routes: the autochart app plus a Moonscraper pass (guitar); STRUM's chart with one global shift (drums, bass) | — |

**One architecture for both goals.** Every note source returns a `TimedSong` (`songcharter/timed.py`) in seconds of the single gapless decode. Only the quantizer turns times into ticks of our `TempoMap`, so no note is ever timed by another tool's tempo map. Imported charts plug in this way today (`songcharter/importers.py` [code]); our Fretformer driver, rules, ADTOF and STRUM onsets are designed to [untested]. Confidence: high.

**The Goal 2 pipeline:**
1. Decode the file once with ffmpeg (gapless). On Windows, always use the bundled ffmpeg.
2. Separate stems with Demucs `htdemucs_6s`, in one pass that every stage shares, with its random shift seeded (§2). BS-RoFormer SW is not in this version.
3. Build the beat grid. Beat This! `final0`, plus a level fold and v1's DP decoder, proposes beats. `songcharter.beatgrid` refines them on drum-stem onsets (bass or guitar onsets when there are no drums) and picks free or click mode; on this path both need code changes (§2.3). The downbeat/meter Viterbi sets the bar lines (§2.4). Then `plan_lead_in` → `TempoMap.from_beats`.
4. Chart the instruments:
   - **drums:** ADTOF onsets and kicks with a new lane mapper (provisional [decision]); STRUM is the lane benchmark and is never shipped (§2.9);
   - **bass:** our rule engine; STRUM onsets re-laned by pYIN are scored as a benchmark only (§2.8);
   - **lead guitar:** Fretformer 2 Expert through our own onnxruntime driver (B2), through autochart's engine behind a process boundary (B1), or by building on autochart (D): **B1, decided** by the owner (§9 Q3).
5. Quantize every source onto our grid. Derive the lower tiers with our nested reducer. Add activation lanes, star power, solos, sections and difficulty ratings. Gate the result with the sync check, scan-chart, a self-check and Encore's rules.

**As built** (`songcharter chart <file> --out <dir>`: `pipeline.py` [code]): steps 1, 2, 4 and 5, with step 3 as
Goal 1 builds it (`beatgrid` on the drum stem with the guitar stem second, no Beat This start; assemble). The engines
are ADTOF with drummap2's lanes (drums), our rules (bass), autochart's engine (guitar: by default 4 takes when it
runs on CUDA, 1 on the CPU) and allin1 or librosa (sections), each cached in the song's work folder in the per-user
cache (`%LOCALAPPDATA%\songcharter\work`, pruned to 5 GB; §2); then assemble builds and gates the folder (Expert only
by default, solos on the sections named Solo), and a preview of it (an overview and a page a minute, PNG) goes into
the work folder (§2.0). It ran end to end on the test song's MP3 in 12.7 min on the dev container's CPU and passed
the gate (§5, M3) [here, pipeline run].

**Expected quality:**

| part | best measured so far | caveat |
|---|---|---|
| tempo | On the guitar audit's yardstick (the test song's 800 local drum beats, rising-edge picker), p95 \|dev\|: rigid 142.0009 BPM line 47.9 ms, STRUM's line 34.7 ms, `beatgrid` free 50.7 ms with a median of −16.6 ms, inside the human −14 to −18 ms [here, guitar audit; here, beatgrid run]. On four Harmonix references `beatgrid` (no Beat This start) puts 1.00 / 0.986 / 1.00 / 0.26 of its beats within 70 ms of a human beat (All the Small Things, Take Me Out, Creep, Lucretia) [here, beatgrid run; Take Me Out after the local tempo periods of §2.3: here, review]. | Not yet scored with `score.py`'s beat F1. Its kick-on-1 bar phase was wrong on 2 of the 4 references (both flagged uncertain). v1's prototype figure (median 5.9 / p95 8.3 ms) is a residual of matched onsets in v1's convention and is not comparable (§2.3). autochart's beat F1 on the six references averages 0.87, Lucretia 0.29 [here, 5070]. |
| lead guitar | autochart Expert F1@50 0.86; it wins 6 of 6 songs [here, 5070] | On the two Car Seat Headrest community charts it scores 0.81 and 0.78, against 0.86 and 0.77 for an 8th-note grid laid on the human tempo map. Its edge there is lane direction (0.72 vs a trivial 0.62; 0.58 vs 0.39), and its κ is only 0.37–0.39. Our own driver (Engine A) has never been scored. Through our pipeline (B1, 1 CPU take, our grid and quantizer) Take Me Out scores 0.909, against autochart's own GPU chart at 0.880 [here, pipeline run; one song]. |
| drums | ADTOF on whole songs: F1@50 0.967 (pad-blind), kick F1 0.986 (5-song mean) [here, ADTOF test]; the built engine after our quantizer 0.962, kick 0.980 [here, drums engine run] | After offset removal the onset gap to STRUM is about 0.005, not the 0.04 its lateness costs: STRUM's CPU charts of 3 songs go from 0.938 to 0.956 through our quantizer, against ADTOF's 0.961 there, and STRUM's kicks are ahead (0.988 against 0.977) [here, drums engine run]. Exact lane agreement 0.586, against STRUM's 0.687. No lane mapper on ADTOF reaches STRUM yet. |
| bass | our rule engine after our quantizer: F1@50 0.80, lane direction 0.78 vs a trivial 0.54, lane-direction κ 0.61 (5-song means) [here, bass engine run] | Like for like (STRUM through the same quantizer, the 3 songs with a STRUM folder here): ours 0.80 vs STRUM 0.75, κ 0.69 vs 0.29. STRUM leads on All the Small Things (0.90 vs 0.74), where we over-chart: precision 0.60, 1.59× the human density (Creep 1.72×). STRUM's folders as scored, late and on its own grid: 0.59. Quantizer merges write chords (Expert share up to 0.074). Kimochi Warui is in v1's development excerpts; the four Harmonix songs are not. |
| lower tiers | nested by construction (`reduce.py` [code]) | How human they feel is unmeasured. v1's Hard rule kept 97–100 % of Expert [here, critique]; this version thins Hard (§2.11). |

So expect a playable, in-sync, complete chart that still needs a polish pass in Moonscraper: guitar frets and chords first, then drum hand lanes and bass lanes.

**Run time, 7-minute song, one guitar take** (estimates are sums of the per-stage figures in §2):

| PC | guitar route | estimate | basis |
|---|---|---|---|
| RTX 4070 | B2 (our driver on the CPU execution provider) | about 3–7 min [est.]; target ≤ 8 min | decoding 107–204 s per take on 3 threads [here, critique]; 6s on GPU 10–20 s [est., untested]; ADTOF 13–30 s, pYIN 20–50 s [here]; sections about 1–2 min (all-in-one-infer fold 0, CPU, 2 threads) [here, sections engine run] or seconds (ensemble, GPU) [doc] |
| RTX 4070 | B1 (autochart's engine) | about 5–7 min [est.] | its Expert job took 228.8 s on the 5070, its own htdemucs_6s pass included, so separation runs twice [here, 5070]; plus our other stages as above |
| CPU-only desktop | B2 only | about 5–10 min [est.] | the same stages on the CPU: 6s 143 s for the test song on 3 threads [here, ADTOF test]; Beat This 34–45 s on 2 threads [here, v1] |
| CPU-only desktop | B1 | over 10 min [est.] | autochart's Expert job alone took 426 s on the dev CPU [here] |
| dev container (4 shared vCPUs, 2 torch threads), measured | B1, 1 take | **12.7 min** for the 6:52 test song; 6.8 min for the 4:01 Take Me Out | `songcharter chart` end to end: decode 4 s, separation 169 s, drums 20 s, bass 21 s, sections 119 s, guitar 404 s (autochart's own separation included), build and gate 23 s; a re-run with every cache warm 41 s [here, pipeline run]. Peak RSS: §5, M3. |

- Each extra take adds about 1.5–3 min (B2) [est., critique] or one more autochart transcription (B1): the three
  extra takes of CUDA's default 4 added 5.75 min a song on the 5070 (3.41× the guitar stage) [here, takes
  experiment], and one more on the dev CPU took 217 s for the test song [here, pipeline run] (§2.7).
- Beat This on the 4070 and packaging (ogg encode, decode-back, scan-chart) are [untested].
- A GPU barely speeds up Fretformer decoding (§2.7). STRUM takes tens of minutes on a CPU [here], one reason it is never shipped (§2.9).

**Licence (not legal advice).** The Fretformer 2 weights are CC BY-NC-SA 4.0. The ADTOF weights are CC BY-NC-SA 4.0 by inheritance from the upstream ADTOF repository; the host of the `.pth` states no licence. The htdemucs_6s weights are treated as non-commercial. So the shipped tool is free and non-commercial in practice. No fully open route exists today: even a rules-only route needs stems, and no separator with a permissive weight licence was found (§4.2).

---

## 2. Pipeline, stage by stage

```
input file ──ffmpeg (bundled), gapless──► mix: 44.1 kHz stereo float32
 ├─ separation: htdemucs_6s, one shared pass, random shift seeded ─► stems, cached as float32
 │        (cache key: mix sha256, model sha256, shifts, overlap, seed, code version); median-lag gate (≤ 2 samples)
 ├─ Beat This final0 ─► fold to [85,185) BPM + v1's DP ─► beatgrid: refine on drum onsets (else bass/guitar)
 │        ─► free / click (+ free islands) ─► downbeat Viterbi ✕ kick-phase flag
 │        ─► plan_lead_in ─► TempoMap.from_beats(tolerance=0.003)
 ├─ sections: allin1 fed our stems (ensemble on GPU, fold 0 on CPU) or librosa ─► bar-snapped, numbered names
 ├─ note sources, each returning a TimedSong in seconds of the unpadded decode:
 │     drums:  ADTOF (BD/SD/TT from stem, HH/CY from mix) ─► lane mapper ─► collision resolution
 │     bass:   HFC onsets + pYIN rank frets              (STRUM onsets + pYIN re-lane: benchmark only)
 │     guitar: Fretformer 2 Expert, 1 seeded take, tokens cached               (engine route open)
 │     Goal 1: imported autochart (guitar) and STRUM (drums, bass) charts
 ├─ quantizer: remove each source's offset ─► 1/16 + 1/12 slots ─► HOPO intent ─► minimum spacing
 ├─ clip every level to song.ogg's end ─► drum activation lanes ─► star power and solos (Expert) ─► reducer (H/M/E, nested; star power and solos kept non-empty; only when asked) ─► diff_* ratings
 ├─ notes.chart + song.ini + song.ogg ─► verify_sync ─► scan-chart ─► self-check ─► Encore rules ─► folder / zip / install
 └─ preview of the built folder (overview and pages, PNG) ─► the work folder's preview/
```

**Cross-cutting rules:**
- **One timeline.** Every analysis reads the single gapless decode. Never pass the MP3 path to a separator or a tool.
- **Two clocks, named.** `TimedSong` seconds are on the unpadded decode. `TempoMap` ticks are on the padded timeline (`LeadIn.pad_seconds` of silence in front; `plan_lead_in`). Input seconds + `lead.pad_seconds` = map seconds. Convert to ticks only through the quantizer or one shared helper; this covers sections, solos, star power, activation lanes and `preview_start_time` as well as notes (`quantize.py` already follows it [code]).
- **One boundary.** Sources hand over seconds (`TimedSong`), and only the quantizer writes ticks. A source that is already on our grid (Engine A, §2.7) still goes through it, with its exact ticks kept.
- **Stem cache.** Stems are cached as float32 (WAV or NPY) under `%LOCALAPPDATA%\songcharter\cache\<key>`, not as FLAC: the decode exceeds full scale (critique E12; §2.1). The key is (mix sha256, model sha256, shifts, overlap, seed, code version); a key of the mix alone would reuse stale stems after a model or parameter change. As built, the stems sit in the song's work folder (below), in `stems\<separation key>`.
- **Work folder** (§9 Q30, decided; `cache.py` [code]). Every cache of a song (the decode, the stems, each engine's
  folder, the assemble config, `pipeline.json` and the preview) sits in one work folder in the per-user cache:
  - **Where:** `<cache>\work\<name>-<key>`, `<cache>` being `%LOCALAPPDATA%\songcharter` on Windows and
    `$XDG_CACHE_HOME/songcharter` or `~/.cache/songcharter` elsewhere; `$SONGCHARTER_CACHE` moves the work folders
    (not the weights, which stay in `<cache>\models`, §4.2). Never beside the output: with `--out` in Clone Hero's
    Songs folder, Clone Hero would list autochart's takes, whole song folders, as songs [inference].
  - **Keying:** `<key>` is the first 16 hex characters of the song file's SHA-256, so the same file reuses its caches
    whatever the output; `<name>` is the file's stem made safe for Windows (ASCII-folded where it can be, no reserved
    characters or device names, at most 40 UTF-16 units), for a person to tell the folders apart. A renamed copy gets
    a folder of its own.
  - **autochart's scratch folder** (its engine cache and jobs) is `<cache>\ac\<first 8 hex of the key>`, apart:
    the files its own layout leaves reach 188 characters below it on Windows, so inside the work folder its deepest
    file would be 319 characters with `C:\Users\<20 characters>\AppData\Local` and a 40-character name, past
    Windows' 259; here it is 256, with 3 to spare, and the work folder's deepest (a take's report) 182 [code:
    `tests/test_cache.py`]. autochart writes each of those files through a staging file beside it,
    `.<name>.tmp-<pid>-<uuid>` (`fileSafety.cjs` `writeVerifiedAtomic`), 47 characters longer plus the pid's digits:
    235 below the scratch folder in a real take (the mel tables', pid 6477) [here, defaults review: a traced take],
    241 with a 10-digit pid, so 309 with that profile and 290 even with `C:\Users\X`, past 259 on every profile.
    Only Node writes them, and Node's `fs` takes Windows paths in their `\\?\` form [doc; untested on Windows]; a
    run killed while one is written leaves it behind, so pruning deletes with that form too (`cache.long_path`)
    [untested on Windows].
  - **Pruning,** after each run that finishes: the least recently used work folders go, each with its scratch folder,
    until the rest total at most 5 GB (10⁹ bytes; `$SONGCHARTER_CACHE_GB`). Only folders with our marker
    (`songcharter-work.json`, written when a run starts) count; never the run's own, one used in the last 24 hours,
    or one a `--work` run has used (then it is the person's, and stays so). A folder that goes is first moved whole
    into `<cache>\trash` in one rename (its scratch folder before it) and only then deleted there, so no run meets a
    folder half deleted: a run trusts the caches it finds, and a work folder deleted in name order up to a stem in
    use left a stems `info.json` beside missing stems, which failed every later chart of that song as a bug [here,
    defaults review]. Its marker is read again just before the move (a run may have started on that song since the
    scan) and once more after it, and a run that marked it in between gets it back. A folder that cannot be moved
    (on Windows a file in it in use, or a console in it [inference]) stays whole, with a warning, and the next run
    tries again; what cannot be deleted in the trash stays there, with a warning, and the next prune deletes it
    first. The trash is ours only with its `songcharter-trash.json` in it. Separation is safe on its own too: a
    stems folder whose `info.json` lists a stem that is missing or does not read is separated again (§2.2). Sizes:
    the test song (6:52) 1.19 GB, Take Me Out (4:01) 696 MB, a 35-s excerpt 101 MB [here, pipeline-defaults runs],
    so 5 GB holds four to seven songs [inference].
  - `--work DIR` puts the work folder anywhere, with autochart's scratch inside it, as before.
- **Determinism.** Seeds are fixed and nothing depends on the wall clock. Two CPU runs must give a byte-identical `notes.chart`.
  - Demucs's default `shifts=1` draws a random time shift from Python's global `random` (demucs 4.1.0: `apply.py` line 245, `api.py` line 59); the ADTOF test called `apply_model(..., shifts=1)` [here]. So two fresh separations differ unless `random` (and torch) is seeded right before each separation, or `shifts=0` is used. Record the choice in `doctor.json`. M1 is safe only because it reuses cached stems.
  - The chosen guitar take's tokens and seed are cached with the stems and in the polish workspace, and re-runs reuse them unless the user asks to regenerate. Determinism is promised only on the same machine and device: one flipped token changes the whole rest of a take (critique G6).
- **GPU memory.** Free GPU memory between stages. Log peak VRAM per stage in `doctor.json` and in the UI. Tell the user about any CPU fallback (critique G15).
- **Silence.** A part loses its onsets before its stem first plays and after it last plays (`assemble.active_span`,
  §2.8) [code]. Onsets in a silence inside the song are only reported: the critique's "no notes inside silences longer
  than about 4 s" (G9) is untested and open (§9, Q23).
- **Absent parts.** A part whose stem never shows activity is omitted, together with its `diff_*` key (critique G3; `ini.py` already writes keys only for charted instruments [code]). Thresholds come from the stress set (§5, M5) [untested]. As built, the pipeline leaves out a part whose engine finds no note, with a warning; a part with a few notes in a silent stem is still charted [code].

### 2.0 Code status [code]

| module | state on `main` (2026-11-02): at commit e0e4b7e after the first-chart review; `separate.py`, the engines and `pipeline.py` as merged since |
|---|---|
| `audio.py` | `decode`, `encode_ogg`, `measure_offset`, `verify_sync`. `ffmpeg_exe()` tries `$FFMPEG`, then PATH, then the imageio-ffmpeg wheel (lines 27–36). An ffmpeg failure is an `InputError` (decode) or a `ToolError` (encode) that quotes ffmpeg's last line. |
| `errors.py` | `SongcharterError`, an error the user can act on, in two kinds: `InputError` (also a `ValueError`: a bad input, config or option, a chart that does not parse, an output folder with foreign files, a song with nothing to chart or no drum evidence for the grid) and `ToolError` (also a `RuntimeError`: a missing or failing component, a weight file off its pinned SHA-256, autochart failing or timing out, song.ogg out of sync). The command line exits 2 for these and for an `OSError`; any other exception, numpy's and torch's own `ValueError` and `RuntimeError` included, is a bug (exit 3). |
| `tempo.py` | `TempoMap.from_beats` (default tolerance 0.002; writes only x/4 time signatures), `plan_lead_in` (`LeadIn.first_beat` is the index of the first downbeat after the extrapolated lead-in). |
| `chart.py`, `ini.py`, `package.py` | The `.chart` and `song.ini` writers; `build_song_folder` (refuses a package whose sync is off by 1 sample or more); `zip_folder`. `ini.py` writes `diff_guitar`, `diff_guitar_coop`, `diff_bass`, `diff_rhythm`, `diff_drums`, `diff_keys` and `diff_drums_real`; it has no band key. |
| `timed.py` | The `TimedSong` contract; `TimedNote.hopo` carries the source's HOPO intent and `TimedNote.hopo_forced` whether the source forced it. `TimedSong.beats` is read by `quantize.odd_32nds`; the "for diagnostics only" note is gone. |
| `beatgrid.py` | The grid of §2.3: an internal Ellis-style DP tracker (`track_beats`, `TRACKER_MARGIN`) on local 20-s tempo periods (`local_periods`), a check for missed tempo changes (`stats["tempo_check"]`), an opt-in second stem for beats without drum evidence (`secondary=`, `onset_phase`) and a flag for uncertain downbeats (margin < 0.15). |
| `importers.py` | `read_chart`, `read_mid`, `read_song`, `read_ini_modifiers`, following scan-chart's rules (HOPO thresholds and forcing, sustain cut-off, cymbal and tom markers, phrase overlaps); `hopo_forced` marks the notes the source forced. The parser-equivalence check passed, as a scratchpad script rather than a repo test: autochart 4, chartgen 4 and STRUM 12 tracks; worst onset difference 2.9·10⁻¹¹ ms; 0 flag, lane or sustain mismatches; sections and solos equal; STRUM's beats start at 0.0697 s with `time_offset=0.0697` [here, importer check]. |
| `quantize.py` | Offset estimate per instrument; 1/16 plus 1/12 slots only, with a 1/32-grid source's odd 1/32s sent to the coarser slot (`odd_32nds`, §2.6); merge, separation and minimum spacing; per-difficulty chord limits; sustain rules (Easy floor 2 beats); HOPO policies (`source_hopo`, `forced_only`; §2.6 step 4); drums: one hit per pad per tick, a tom that collides with a cymbal moves to a free tom pad or is dropped; spans snapped and kept non-empty; taps kept. `QuantizeReport` counts the notes moved more than 25 ms (`moved_25ms`), information only. |
| `reduce.py` | Nested Hard/Medium/Easy for 5-fret and drums; minimum gaps from time floors (no Standard/Dense preset); a thinning ladder; a below-Expert HOPO rule; Easy sustain floor 1.25 beats (2 for bass); star-power and solo coverage; `check_reductions` (5-fret Hard ≥ 0.90 of Expert onsets is an error). |
| `starpower.py` | Star power, drum activation lanes (at section changes, in star-power gaps, then every 4 measures) and solos (on the "Solo" sections, or those of them a caller's test confirms, e.g. `stem_confirm`, or exactly the sections a person names; none unless asked), placed on Expert and fitted to every level (`fit_chart`); `check_phrases` (scan-chart's phrase checks, our rules, a `fillNoCrash` warning) (§2.10). |
| `sections.py` | allin1 segments, or an imported chart's sections, on measure starts: merged, split and named (§2.5). |
| `separate.py` | `separate`: one Demucs pass on the decoded array (htdemucs_6s by default, htdemucs_ft for M2), weights at a pinned Hugging Face revision with every file's SHA-256 checked, `random` and torch seeded right before the call; device auto takes CUDA only when a CUDA kernel runs (`cuda_works`: `is_available()` is also true on a GPU the torch build has no kernels for), else the CPU (reported); CUDA out of memory retried on the CPU (reported); a float32 WAV stem cache keyed by the samples and settings, a hit only when every stem its `info.json` lists is there and reads (§2.2). Optional dependency `songcharter[separate]`. |
| `engines/autochart.py` | Lead guitar by route B1 (§2.7, decided in §9 Q3): our job driver `eval/tools/autochart/ac_headless.cjs` runs autochart's engine once per seed, Expert only, behind a process boundary (no AGPL code is imported). `generate(install, audio, out, seeds)` writes one song folder per take (`seed_<seed>/`), reused when its `take.json`, written after the run, matches: the input's SHA-256, the seed, the sampling settings, the difficulty and the install (`engine/manifest.json`'s engineVersion and a SHA-256 over the engine's manifest and catalog, the models' manifest, onnxruntime-node's `package.json` and the driver), so an updated engine, model set or driver runs every take again; the takes share one engine work folder, so takes after the first pay only for the transcription. `find_install` names whatever is missing (node, the engine, the models, onnxruntime-node). |
| `engines/adtof.py`, `engines/drumlanes.py` | The drums engine of §2.9 (Goal 2). `adtof.generate(mix, drums, out, settings)` runs ADTOF's Frame_RNN, our own PyTorch module and a separate component treated as BY-NC-SA, on the drum stem and on the mix. The weights come from xavriley/ADTOF-pytorch at commit 85c192e7, are checked against their SHA-256, are downloaded on first use to `models_dir()/adtof/` and are loaded with `weights_only=True`. drumlanes.py holds the fusion, the G3 hat gate, drummap2's lanes, the two-hands and shared-pad rules and the 2x kicks. The output is notes.chart (Expert only, 120 BPM at resolution 480), song.ini (pro_drums = True) and engine.json, cached by a key of the samples, the weights, the settings and the beat period used (beatgrid's tempo estimate of the mix unless `beat_s` is given, so a hit still estimates it: a few seconds). The activations are cached apart (`activations.npz`), so a change to the lane settings alone does not rerun the model. Optional dependency `songcharter[drums]`. |
| `engines/bass.py` | The bass rule engine of §2.8: HFC onsets on the bass stem (delta 0.07), the leakage gate of §2.2 (stem within 30 dB of the mix from 50 ms before to 200 ms after the onset), `librosa.pyin` at 22.05 kHz (fmin 30, fmax 400, frame 2048, hop 220) in 30-s chunks, v1's `map_v2` lanes (identical to the prototype), sustains where the pitch track holds the note. `generate(mix, bass, out)` writes `notes.chart` (Expert bass on a constant 120 BPM map at resolution 480) and `engine.json`; the folder is reused when its key (samples, settings, rules and library versions) and chart match. Optional dependency `songcharter[bass]` (librosa). |
| `engines/sections.py`, `engines/allin1_runner.py` | `find_sections(mix, stems, out, settings)`: `out/segments.json` (allin1 format: what `sections.read_allin1` and assemble's `"sections"` read) and `out/engine.json` (backend, why, versions, timings, key), cached by a key of the samples the backend read and every setting; a hit rewrites engine.json's why and settings for the call that hit. `backend="auto"`: allin1 when a Python with it is configured (`$SONGCHARTER_ALLIN1_PYTHON`, or this one) and its probe and run succeed, else the librosa fallback, with the reason recorded. allin1 runs as `allin1_runner.py` in that Python under its own import rules (user site and PYTHONPATH count), all-in-one-infer first, else allin1 1.x, fed our stems folded to its four, as int16 on stdin: no second separation, no stem files. Fold 0 on the CPU, the 8-fold ensemble on CUDA. The probe runs a CUDA kernel; with device auto, a failed CUDA run is redone with fold 0 on the CPU. Checkpoints from `taejunkim/allinone` @379e5fd0, SHA-256 checked. The fallback's `beats=` drops times outside the audio. allin1 failing with librosa absent is a `ToolError` that names both. The runner reports its own peak RSS (VmHWM on Linux, PeakWorkingSetSize on Windows), kept in engine.json. Optional dependency `songcharter[sections]` (librosa). |
| `cache.py` | The per-user cache (§2, work folder; §9 Q30): `%LOCALAPPDATA%\songcharter` on Windows, `$XDG_CACHE_HOME/songcharter` or `~/.cache/songcharter` elsewhere (`user_cache`, shared with ADTOF's `models_dir()`, whose paths and `$SONGCHARTER_MODELS` are unchanged); `$SONGCHARTER_CACHE` moves the work folders only. A song's work folder is `<cache>/work/<name>-<key>`: the key is the first 16 hex characters of the song file's SHA-256, the name its stem made safe for Windows (ASCII-folded where it can be, no reserved characters or device names, no trailing dots or spaces, at most 40 UTF-16 units). autochart's scratch folder is `<cache>/ac/<8 hex>`: the files its own layout leaves reach 188 characters below it on Windows, so inside the work folder its deepest file would be 319 characters with `C:\Users\<20 characters>\AppData\Local` and a 40-character name, and here it is 256 (the work folder's deepest, a take's report, 182); autochart's staging files beside them go past 259 on every profile (`DEEPEST["staging"]`: 309 with that profile), which only Node writes, and pruning deletes in Windows' `\\?\` form (`long_path`). After each run that finishes, the least recently used work folders (with our marker, `songcharter-work.json`, written when a run starts) go, with their scratch folders, until the rest fit 5 GB (`$SONGCHARTER_CACHE_GB`); never the run's own, one used in the last 24 hours or one a `--work` run used (pinned in its marker, which later default runs keep, with its scratch folder). Each goes whole into `<cache>/trash` in one rename, scratch folder first, its marker read again before and after the move (a run that marked it in between gets it back), and is deleted there; a folder that cannot be moved stays whole, and what cannot be deleted in the trash waits for the next prune, each with a warning; a `trash` folder without our `songcharter-trash.json` is left alone. |
| `pipeline.py` | M3's pipeline (§1, `songcharter chart`): one decode, written as a float32 WAV into the work folder (the song's folder in the per-user cache, pruned after each run, §2; or `--work`) (autochart's input and assemble's audio, rewritten only when the samples change); one seeded separation cached there; the drums, bass, sections and guitar engines, each in a folder of the work folder that is its cache; then an assemble config (`work/assemble.json`) and assemble's build and gate, writing Expert only unless `levels` asks for more (the friend's v1 feedback: only Expert is needed unless he asks), with solos by assemble's rule (`solos`: "labels" by default, every section named Solo, chosen on the solo evaluation of §2.10; "stems", "off" or a list of section names; only when the guitar is charted, and "stems" or names without the guitar are refused, as more than one take is). Guitar: autochart's default seed, and for `takes` N ≥ 3 seeds 101, 202, … spliced by takes.py (a take that repeats another's notes is left out); `takes` None (the default) is 4 when the guitar stage runs on CUDA and 1 otherwise (`guitar_takes`, §2.7), the first CUDA take run alone first so that a transcriber autochart moved off CUDA by itself leaves that take alone (warned); `pipeline.json`'s `takes` says how many, whether by default, and why. A part whose engine finds no note is left out (§2, absent parts). After assemble, the preview (`preview.py`) of the folder it wrote, the song folder or its `.failed`, goes into `work/preview/` (overview.png, page_NN.png), judged against the work folder's six stems, when matplotlib and librosa import; their absence or a preview that fails is one warning and never changes the exit code (`--no-preview` turns it off), and so is a Ctrl+C during the preview or the pruning after it (the build is in place by then); `pipeline.json`'s `preview` holds its flags, and the CLI summary prints the overview's path, the work folder's size and autochart's scratch folder when the run made one. Metadata: the file's tags (ffmpeg's ffmetadata output, the container's, then the first audio stream's), the caller's values on top, and "Unknown" placeholders (scan-chart counts its own "Unknown Artist" defaults as missing). A missing component (ffmpeg, torch and demucs, librosa for bass, librosa for sections, allin1 or not, since it is allin1's fallback, autochart's install, CUDA asked for but absent or running no kernel in songcharter's torch) is named with its fix before any audio work, and so is an output folder (or its `.failed`) holding foreign files. Device auto is CUDA only when a CUDA kernel runs (`separate.cuda_works`), else the CPU for every model, with a warning. The sections engine is asked for auto when CUDA is asked for: allin1 runs in a Python of its own whose CUDA nothing checks up front, so it takes CUDA when that Python has it and the CPU (warned) when not. `work/pipeline.json` records each stage's wall time, cache use, device, fallback and the process's own peak RSS (not its children's: a child's `ru_maxrss` starts from its parent's peak when it was spawned), allin1's runner's own peak, and for a run that raised, the error and its traceback. The heavy stages are the methods of `Engines`, so tests stand in for them. |
| `takes.py` | `splice`: a part's Expert from several runs of its source, chosen per section by the takes' agreement (§2.7, Several takes); assemble's part key `takes`. |
| `assemble.py` | One JSON config to a gated song folder: decode, stem-lag check, grid with a second stem (§2.3), parts imported, offset-corrected and quantized, edges trimmed (§2.8), every taken level clipped 1 ms inside song.ogg's end (`clip_to_audio`, §2.13), sections, phrases, reductions, ratings (§2.12), `build_song_folder` into a staging folder, then the gate with scan-chart 8.0.1 itself (§2.13) and `report.json`. A build the gate fails goes to `<output>.failed`. `check_output` (the output folder and its `.failed` hold only what a build writes) also runs in the pipeline before any audio work. |
| `cli.py` | `songcharter chart <song file> --out DIR [--work DIR] [--instruments guitar,bass,drums] [--levels expert\|all\|LIST] [--solos labels\|stems\|off\|"NAME,NAME"] [--takes N] [--device auto\|cpu\|cuda] [--threads N] [--no-preview] [--title\|--artist\|--album\|--year\|--genre TEXT]` (pipeline.py; the work folder defaults to the song's folder in the per-user cache, `cache.py`, and `--work DIR` puts it anywhere, with autochart's scratch inside it as before) and `songcharter assemble <config.json> [--out DIR]`. Both: exit 0: the gate passed; 1: it failed (the build is in `<output>.failed`); 2: a bad config, input, option or tool (a missing component named with its fix), a failing component, or song.ogg out of sync (nothing written): an `errors.SongcharterError` or an `OSError`, one line; 3: any other exception, a bug (traceback printed, and kept in `pipeline.json` for `chart`); 130: interrupted before the build was in place (for `chart`, a Ctrl+C during the preview or the pruning after the build stops only that stage, with a warning, and the exit status is the gate's). `chart` prints a line on stderr when each stage starts and ends, with its wall time, and the build summary and stage times on stdout. |
| `ui/` (`server.py`, `jobs.py`, `static/`) | `songcharter ui` (M4-04, §4.5): a standard-library server on 127.0.0.1 with its guards (the Hosts 127.0.0.1 and localhost, `X-Songcharter: 1` and a same-origin `Origin` on every POST, uploads by name, size and type), a vanilla-JS page, and one job at a time: `songcharter chart --events` in a process group of its own, its events replayed over SSE, cancel killing the group. Under WSL it checks the page from Windows (`curl.exe`) and falls back only to WSL's NAT address (the default route's source, inside 172.16.0.0/12, never under mirrored or other networking modes); else it stops with exit 2. Stopping the server (SIGTERM, SIGHUP, the window closing) kills a running job. |
| `proc.py` | `Tree`: a child in a session and process group of its own, killed whole (SIGTERM, then SIGKILL after 1 s for any member left, waiting until the group is empty). |
| tests | 479 tests on branch `pipeline-defaults` (476 pass and 3 skip in its worktree: the allin1 test without `$SONGCHARTER_ALLIN1_PYTHON`, and test_package's two scan-chart tests, which look for `tools/scan-chart/node_modules` in the checkout itself and pass with it [here]); `tests/conftest.py` points `$SONGCHARTER_CACHE` at a temporary folder for the whole session, so no test writes to the real per-user cache. Before this branch (`main` at 7172d80), 428 tests: tempo 8, chart 5, package 6, beatgrid 26, importers 21, quantize 45, reduce 113, starpower 25, sections 16, separate 7, takes 11, assemble and the CLI 42, preview 22, the four engines (autochart 6, ADTOF 15, bass 14, sections 29) and the pipeline (17, with stand-ins for the heavy stages, which check the exact arrays they get, and the CLI end to end on a synthetic song); 427 pass and 1 skips without `$SONGCHARTER_ALLIN1_PYTHON` (it passes with it set). The branch adds 51: cache 38, pipeline 9, assemble 3, separate 1; the scan-chart tests skip when `tools/scan-chart`'s node_modules are absent [here]. A passing test's temporary folders are deleted at once (`tmp_path_retention_policy = "failed"`): `tests/test_pipeline.py` peaks at about 320 MB of them and leaves none, where it used to leave about 470 MB per run, three runs kept [here]. |

**Design and code, decided once.** Each difference is decided here; code changes are §5.6 tasks.

| topic | this design | code today | action |
|---|---|---|---|
| snap grid | 1/16 + 1/12 (§2.6) | same | none |
| tempo-level HOPO exception | kept (§2.6 step 4): on the rigid grid, 11 of the 28 flips the quantizer writes on autochart's Expert fall inside its two half-tempo stretches, which hold 106 of its notes [here, quantizer check] | not as designed: assemble's default `hopo: "forced"` keeps only the states the source forced (§2.6 step 4); `timed.py`'s docstring is fixed | open: add the beat-period rule, or keep `forced` in its place; M2's HOPO κ decides |
| chord limits | `quantize.py` applies the limits of whichever difficulty it receives; in the pipeline only Expert comes from a source, and the reducer builds the rest | same | none |
| drum collisions | the cymbal stays; the tom moves to a free tom pad (yellow first), else it is dropped and counted (§2.9) | same | report the dropped count (M1) |
| Hard threshold | error at 5-fret Hard ≥ 0.90 of Expert onsets (critique E3) | same | none |
| Easy sustain floor | 1.25 beats, 2 beats on bass (`reduce.py`) | `quantize.py` 2.0; `reduce.py` 1.25 / 2.0 | align `quantize.py` |
| HOPOs below Expert | `reduce.py`'s rule (§2.11 step 9) | same | none |
| lower-tier density | `reduce.py`'s time floors (§2.11 step 2) | same | none |
| +8 inside star power | dropped; the coverage step keeps phrases non-empty [decision] | absent | none |
| taps | none (§2.6) | `quantize.py` keeps Expert taps (`QuantizeRules.taps = True`); `reduce.py` drops them below Expert | set `taps=False` for Goal 1, or adopt Expert taps after M2 [decision] |
| Engine A ticks | through the quantizer with an "already on our grid" flag (§2.7) | absent | add with Engine A (M2) |
| `diff_band` | written (§2.12) | not writable | add a band rating to `write_ini` and `build_song_folder` |
| `beat_grid(start=...)` | click/free tests on that path; low evidence returns the start beats flagged (§2.3) | always free; raises `InputError` (a `ValueError`) on low evidence | §2.3 step 6 |
| downbeats | the Viterbi decides (§2.4) | kick phase only | add a downbeats input |

### Stage overview

| # | stage | Goal 1 | Goal 2 | confidence (G1 / G2) | would change it |
|---|---|---|---|---|---|
| 1 | Decode (§2.1) | one gapless decode is the only timeline; chart the friend's exact file | same; pin the bundled ffmpeg on Windows | high | a decoder disagreement on the friend's file |
| 2 | Separation (§2.2) | reuse the existing ft and 6s stems (lag 0) | htdemucs_6s, one shared pass, shift seeded; weights treated as non-commercial | high (default), medium (licence) | the owner opts into SW; the M2 stem comparison; a permissively licensed separator |
| 3 | Beat grid (§2.3) | `beatgrid` on the drum stem; it chose free mode | Beat This proposes, `beatgrid` refines (code changes needed) | medium-low / low | beat F1 with `score.py` on the references (§5.6, task 2); the detector offset on the test song (M1a) |
| 4 | Meter (§2.4) | 4/4, kick on beat 1 (margin 0.58) | Viterbi x/4 decides; the kick phase and `beatgrid`'s uncertainty flag drive review; 6/8 later | high / low | a listening check; downbeat F on songs with time-signature changes |
| 5 | Sections (§2.5) | allin1's segments (v1's fold-0 result), merged and split per run: 26 sections | allin1 by default (fold 0 on the CPU, the ensemble on CUDA), librosa as the fallback [here, M2 row 7] | low / medium-low | section scores on more references; the owner's call on fold 0 for CUDA; the friend's feedback |
| 6 | Quantizer (§2.6) | remove offsets, snap to 1/16 + 1/12 (a 1/32-grid source's odd 1/32s to the coarser slot), keep the HOPO states the source forced | same | medium | snapping moves > 2 % of onsets by > 25 ms; HOPO κ in M2 |
| 7 | Lead guitar (§2.7) | four autochart Expert takes, imported and spliced per section by agreement between takes | autochart's engine as a separate program (B1, decided §9 Q3; built: `engines/autochart.py`); by default 4 takes spliced on CUDA, 1 on the CPU; `--takes N` (1, or N ≥ 3) on any device | medium / low | B1's seed spread over ≥ 3 seeds on the references; the friend's playtest |
| 8 | Bass (§2.8) | STRUM onsets, offset removed by the quantizer, re-laned by pYIN | our rules (built: `engines/bass.py`), scored on 5 references; STRUM a benchmark only | low / medium-low | more references; the friend asking for bass (§9 Q1 answered: he plays Guitar) |
| 9 | Drums (§2.9) | STRUM lanes, re-timed; ADTOF kicks only after a de-duplicated fusion re-test | ADTOF onsets and kicks with drummap2's lanes (built: `engines/adtof.py`), a better lane mapper still to come (provisional [decision]); STRUM is the lane benchmark, never shipped | medium / medium-low | a mapper that misses the drum-lane rule of §3.2; the owner choosing a shipped-STRUM route (§9 Q14) |
| 10 | Star power, solos, activation lanes (§2.10) | v1's rules with the critique's fixes; lanes first; v1.1: solos by name on the two sections the friend confirmed ("Solo 1", "Solo 2") | same; solos on every section allin1 labels Solo (the solo evaluation) | low-medium | M2 counts; the playtest; the owner's choice on fills; more human solos to score against |
| 11 | Reductions (§2.11) | our nested reducer (`reduce.py`): time-floor gaps, a thinning ladder; v1.1: Expert only | same, when asked: Expert only by default | medium | ours losing to autochart's tiers beyond run-to-run spread |
| 12 | Difficulty rating (§2.12) | v1's linear models, checked by hand | same, shown as editable values | low-medium | bias against Encore references |
| 13 | Output and validation (§2.13) | existing writers; sync → scan-chart → self-check → Encore rules | same, per track and difficulty | high | a playtest showing the gate is wrong |
| 14 | Packaging and UI (§4) | a folder plus a zip, copied into Clone Hero | installer and local UI after the Windows spike; native or WSL is the owner's call | medium / low | the owner picks D or accepts WSL; the spike's findings |
| 15 | Evaluation (§3) | reference-free proxies against the source tools, with tolerances | harness, non-regression gates, a larger and newer reference set | high (method) | Encore access |

### 2.1 Decode
- **Method:** `songcharter.audio.decode` produces gapless 44.1 kHz stereo float32 that honours the LAME header. Stems are separated from that decoded array, never from the file. `build_song_folder` encodes `song.ogg` (libvorbis q7) from the same samples after the lead-in pad, decodes it back and requires `verify_sync` < 1 sample. All of this exists [code].
- **Changes:**
  - On Windows, use the bundled ffmpeg and ignore PATH. Today `ffmpeg_exe()` tries `$FFMPEG`, then PATH, then the wheel, so a stray ffmpeg on the friend's PATH would win (critique E12) [code].
  - Generate on, or verify sync against, the exact file the friend will play (comparison).
- **Why one decode:**
  - The test MP3 has a 1105-sample (25.06 ms) encoder delay; ffprobe reports `start_time=0.025057` [here].
  - The shared `htdemucs_6s` stems, separated from the MP3, are exactly 1105 samples late, while the `ft` stems have lag 0 [here; found by two researchers and re-checked by the critique].
  - In the ADTOF test, all six 6s drum stems separated from the decoded array had a median lag of 0.00 samples, and sync was OK on all six song folders [here].
- **Headroom:** the decoded mix peaks at 1.123, with 470 samples above 1.0. `encode_ogg` clips to ±1, and an integer FLAC stem cache would clip too (critique E12) [here]. Hence the float32 stem cache. `eval/build_refs.sh` (line 31) also writes the test song's `input.wav` as `pcm_s16le` with ffmpeg from PATH, which clips those samples; the local copy is float32 [code; here]. Fix it in the harness (§3.4).
- **Fallback:** none needed; an unreadable file gets a plain error.
- **Cost:** CPU only, a few seconds.
- **Confidence:** high. **Would change it:** the friend's copy differing from ours (for example the 2014 Bandcamp version at 6:49), or a decode path that ignores the LAME header.

### 2.2 Separation
- **Goal 2 default:** demucs 4.1.0 `htdemucs_6s` through `demucs.api`, on the decoded array, in one pass shared by every stage, with `random` and torch seeded right before the call or `shifts=0` (§2, determinism).
  - Weights: HF `adefossez/HTDemucs-6s` @`3c5ee475…`, 54.9 MB, SHA-256 pinned. Stems: drums, bass, guitar, piano, vocals, other.
  - Downloaded at first run from the pinned revision with a hash check, never bundled (§4.2).
- **Stem-lag gate** (replaces v1's "refuse any lag ≠ 0", which would reject good stems; critique E6):
  - median lag |lag| ≤ 2 samples;
  - correlation floor about 0.15;
  - skip stems quieter than about −30 dB;
  - on failure, warn and re-separate.
  - Basis [here, critique `lagcheck.py`]: 6s drums and guitar lag exactly 1105 samples; ft and bass stems lag −0.6 to +1.4 samples; 6s piano (−31 dB) has outlier windows; median correlations run 0.03–0.77 for all stems.
- **Built** (`songcharter/separate.py` [code]): the default above, with the pinned revision `3c5ee475` and both
  files' SHA-256 checked on every load. On the test song, on the dev container's CPU: 138.5 s; every stem's median lag
  against the mix within 0.1 sample (drums 0.001, bass −0.099, guitar 0.001, other 0.061, vocals −0.005; piano at
  −31.9 dB not checked); two runs on a 30-s excerpt bit-identical [here, separation run]. Its cache folder's
  `info.json` is written last and is the hit, only when every stem it lists is there and reads: a folder half
  deleted or half written is separated again, never an error (a run used to fail as a bug, exit 3, on a stem a
  partial prune had deleted [here, defaults review]) [code; tested with the unit-test model].
- **Goal 1:** no new separation. Reuse the `ft` stems (lag 0) and the ADTOF test's 6s drum stems (lag 0).
- **Leakage gate** (kept from v1, untested): a note candidate from a stem needs the stem within 30 dB of the mix in that window. It is motivated by the 6s stems' −34 dB leakage in the test song's intro.
- **BS-RoFormer SW is not in this version.** It has the best stems, but its weights have no licence, their origin is disputed, and it costs 8–14 min on a 6–8-core CPU [est.] (20–25 min in the dev container [here]). The owner may override (§9).

  | measure [here unless noted] | SW | htdemucs_6s | htdemucs_ft |
  |---|---|---|---|
  | guitar SDR, 2 Harmonix ground-truth songs | 8.39 | 7.21 | 7.53 ("other") |
  | bass SDR / drums SDR | 11.47 / 9.00 | 10.96 / 7.83 | 11.07 / 8.12 |
  | bass onset F1 against the chart | 0.887–0.904 | 0.808 | 0.845 |
  | drum bleed in the guitar stem, test song | 0.04–0.09 | 0.21–0.29 | 0.24–0.28 |
  | test-song intro leakage, drums / bass | −73 / −98 dB | −34 / −34 dB | −38 / −38 dB |

- **Candidates for the M2 stem comparison:** `htdemucs_ft` (lag 0) and the pruned Mega 53-stem model (M2/M5). **Not in this version:** MDX23C DrumSep (CPU RTF 2.8, unclear licence [here, v1]); a local lead/rhythm guitar split (none exists; MVSEP's is online only [v1]).
- **allin1 takes our stems** (§2.5): the sections engine folds the 6s stems to allin1's four (guitar + piano + other → "other") and hands them over in memory, so there is no second pass [code; here, sections engine run].
- **Evidence for the default:**
  - autochart and STRUM both run htdemucs_6s (comparison).
  - 6s took 60–101 s per reference song and 143 s for the 6:52 test song on 3 CPU threads [here, ADTOF test], i.e. RTF 0.33–0.36 (v1 measured 0.38 on 4 vCPUs).
  - On an RTX 4070: about 10–20 s per song [est., untested].
- **Fallback:** CUDA out of memory → retry on the CPU, and tell the user (critique G15).
- **Confidence:** high for the default, medium for the licence reading. **Would change it:**
  - the owner opting into SW;
  - the M2 stem comparison showing ft or SW moving drum-lane or bass F1 by ≥ 0.03, with a CI that excludes 0;
  - a separator with a permissive weight licence appearing (none was found).

### 2.3 Beat grid and tempo map
**Goal 1:** `songcharter.beatgrid.beat_grid` on the test song's drum stem, as written [code]:
1. **Start line.** Use the hints (142.0009 BPM, first beat near 0.047–0.050 s) or the onset envelope's
   autocorrelation, folded into [85, 185) BPM, with a comb-fitted phase. `beat_grid` also runs an internal Ellis-style
   DP tracker on the same envelope (`track_beats`). Its beats become the start grid when they find at least 10
   percentage points more confident evidence than the line (`TRACKER_MARGIN`). On the test song the line won, with or
   without hints (0.66 vs 0.67 confident) [here, beatgrid run].
   - **Local periods.** The tracker uses the line's period, except in 20-s windows (every 5 s) whose own
     autocorrelation tempo clearly differs: by more than 10 %, with a score at least 0.5 above the line's period there
     (`local_periods`, `LOCAL_TEMPO_MARGIN`). A neighbouring window within 5 % of a kept one joins on any positive
     margin. A song with no such window decodes exactly as before [code]. The 0.5 margin was chosen on Take Me Out
     against Lucretia: 0.35 admitted Lucretia's wrong 127 BPM windows. This is a per-window autocorrelation, not v1's
     local-period DP, which a verifier showed is circular on this path [here, review].
   - **Tempo check.** `stats["tempo_check"]` lists the windows whose tempo the final grid still misses
     (`missed_tempo_changes`), and assemble warns about each [code]. It flagged 8 windows in 0–55 s on Take Me Out's
     old grid and none on any new grid [here, review].
   - Take Me Out's share of beats within 70 ms of a human beat is now 0.984 / 0.986 (6s / original stems), up from
     0.846 / 0.836; its 0–45 s intro goes from 0.31–0.35 to 1.00 per 15-s window. All the Small Things, Creep,
     Lucretia, Kimochi Warui and the test song (with assemble's hints) are bit-identical [here, review].
2. **Local beats.** For each grid beat, take the strongest envelope peak within ±60 ms, refined by a parabola, with a confidence.
3. **Mode.**
   - **Free** when ≥ 60 % of beats have confident evidence (`FREE_SHARE`): LOESS over ±4 beats, beat-to-beat period
     change ≤ 2 %. Beats without drum evidence (the drumless intro, 0–42.7 s) follow a second stem (guitar, else
     other) where its onsets hold a clear 8th/16th phase, calibrated on the same song; elsewhere they stay on the line.
   - **Click** otherwise.
   - The test song came out free: 648 of 976 beats (0.66) confident [here, beatgrid run].
   - **Second stem** [code]. `beat_grid(secondary=...)` is opt-in; assemble passes `grid_secondary` (the guitar stem,
     else other; none when the grid comes from the mix; `"mix"` on request). It is kept conservative:
     - it times only beats with drum support < 0.5; drum-supported beats keep the drums' curve;
     - only where its onsets within ±4 beats show a clear 8th-level phase (at least 8 onsets, score ≥ 0.4, 8th-level
       score ≥ 0.3);
     - only from a stem that follows the drums where both play: its lag is calibrated on the same song over at least
       32 drum-supported beats, with a mean score ≥ 0.2 there (onsets at random times score 0.03–0.05, real stems
       0.39–0.76), so `ONSET_TO_BEAT_MS` is not recalibrated per stem;
     - the shift is capped at ±3/16 beat (±79 ms at 142 BPM). The cap and the 8th-level score were added after a
       16th-aliased −104 ms shift at 160.6–161.9 s [here, review];
     - otherwise the beat stays on the line. assemble warns about every stretch of 16 or more beats that neither the
       drums nor the second stem time (`GRID_LINE_BEATS`).
   - On the test song (the ft "other" stem), guitar P@50 goes from 0.689 to 0.835 in the intro, from 0.522 to 0.616 in
     the drumless stretches (the source scores 0.691 there) and from 0.557 to 0.578 over the song; 2 of 700
     drum-supported beats moved, by at most 0.3 ms. The mix scored better in the intro (P@50 0.913), but part of that
     gain looks like a convention shift that happens to match autochart's later placement there, and it was worse at
     272–304 s; it stays available as `grid_secondary="mix"`. Bass timed nothing in the intro [here, review].
   - The fix matters most for guitar, which has 233 notes in those stretches, against 39 for bass and 18 for drums.
     Not measured: `score.py`'s beat F1, any Beat This start, Drunk Drivers; nobody has listened to it [here, review].
4. **Bar phase.** The phase that puts the most kick (40–160 Hz against the snare's 150–400 Hz) on beat 1. A margin below 0.15 is flagged (`DOWNBEAT_MIN_MARGIN`) [code]. On the test song: phase 0, margin 0.58, no 16-bar window disagreeing [here, beatgrid run].
5. **Phase convention.** Beats move −22 ms from the envelope peaks (`ONSET_TO_BEAT_MS`), calibrated on the drum stems of All the Small Things and Take Me Out (§2.14, C8).
6. **Hand-off:** `plan_lead_in(min_lead=2.5)` → `TempoMap.from_beats(tolerance=0.003)`; the code default is 0.002.
   - Markers at 0.003: 81 in free mode and 1 in click mode on the test song; 67–104 on four references whose human
     maps have 92–129 [here, beatgrid run]. The v1 chart, with the second stem: 122 [here, review].
   - v1 at 0.005: click songs get 1 marker with a maximum rounding error of 1.07 ms over 970 beats; IaSg14's 851-marker chart got 112 markers against 202 at 0.002 [here, v1].
   - Marker count is cosmetic: a few ms of jitter does not move notes [here, comparison claims audit].
- **Cost:** onset features 4.4 s for the test song's drum stem; `beat_grid` itself 0.6–1.1 s [here, beatgrid run].

**Whole-song runs tonight** [here, beatgrid run].

Test song, against the guitar audit's 800 local drum beats (rising-edge picker, found within ±60 ms of the rigid grid):

| grid | markers at 0.003 | median signed (ms) | p95 \|dev\| (ms) | p95 \|dev − median\| (ms) |
|---|---|---|---|---|
| `beatgrid` free (chosen) | 81 | −16.6 | 50.7 | 44.6 |
| `beatgrid` click (forced) | 1 | −16.6 | 57.6 | 43.7 |
| STRUM's line [here, guitar audit] | 1 | +14.5 | 34.7 | not computed |
| rigid 142.0009 BPM line [here, guitar audit] | — | −6.7 | 47.9 | not computed |
| human maps, two references (calibration) [here, guitar audit] | — | −14 to −18 | 31.9–33.4 | not computed |

- `beatgrid` meets the human median, but its p95 |dev| is above both straight lines. p95 |dev| mixes offset and spread, so M1 scores spread about the median.
- How much of the spread comes from the two detectors disagreeing (the audit's rising-edge picker against `beatgrid`'s envelope peaks) is unmeasured.
- The v1-style drift test would have called this song click (drift p95 22.2 ms against its 30 ms threshold) [here, beatgrid run].

Four Harmonix references: summed original drum stems, no hints, no Beat This start. On all four the internal tracker won the start ("no straight line fits"), so the mode is free.

| song | our beats within 70 ms of a human beat | median ours − human (ms) | p95 \|dev\| (ms) | our downbeats within 70 ms of a human bar line | bar-phase margin | markers (human) |
|---|---|---|---|---|---|---|
| All the Small Things | 1.00 | +3.0 | 12.4 | 0.00 | 0.013 | 67 (94) |
| Take Me Out | 0.836 | −3.0 | 145.4 | 0.03 | 0.0026 | 83 (108) |
| Creep | 0.997 | −0.4 | 19.8 | 0.99 | 0.263 | 87 (129) |
| Lucretia | 0.263 | +2.5 | 306.7 | 0.66 | 0.076 | 104 (92) |

- The share within 70 ms is not `score.py`'s beat F1, and a grid at half tempo would still score 1.0 on it.
- The −22 ms offset was calibrated on All the Small Things and Take Me Out, so their medians are in-sample; Creep's is not.
- Kick-on-1 bar phase failed on 2 of 4 (All the Small Things, Take Me Out). Both margins are far below 0.15, so both were flagged uncertain, as was Lucretia's [code]. The flag, not the kick phase, must drive review (§2.4).
- Take Me Out's 0.836 came from its 142 BPM intro, gridded at 104 BPM by one global period. With the local periods
  (step 1) it is 0.986, within 0.02 of autochart's beat F1 there (0.99); the share is still not `score.py`'s beat F1
  [here, review].
- The other three rows are bit-identical after the review [here, review].

**Goal 2:** Beat This! proposes and `beatgrid` refines.
1. **Activations.** Beat This! 1.1.0 `final0` (MIT, 81 MB) on the whole mix, giving 50 fps beat and downbeat logits. Use CUDA with float16 if available; on CPU, process 40 s windows.
2. **Peaks.** A logit > 0 that is the maximum within ±3 frames, refined to sub-frame time with a parabola.
3. **One metrical level.** Fold inter-beat intervals to the octave of the median, then into [85, 185) BPM. The natural-HOPO threshold is in ticks (65/192 of a beat), so a 71 BPM map turns 142 BPM 8ths into HOPOs [here]. The UI offers ×2 and ÷2.
4. **Octave control** (comparison): one global metrical level, and rejection of runs at half or double the global period, measured against the global period. A 9-beat local median of raw intervals, which is what autochart compares against, fails inside long runs. The downbeat is not set here: the Viterbi owns it (§2.4).
5. **DP decoder:** v1's, the one behind the F 0.989 below.
   - Score = activation − 100·log2(gap / local period)²; predecessors searched 0.6–1.6 periods back; edges with activation < 0.2 trimmed.
   - Local period: a 9-interval median filter over intervals already folded to the global octave (step 3), interpolated to every frame. Folding first keeps a half-tempo run's intervals at the global period, which avoids the failure in step 4.
   - `beatgrid.track_beats` is a different decoder: −100·ln(gap / period)², predecessors 0.5–2 periods back, one
     global period or one per frame from `local_periods` (Goal 1, step 1) [code]. Since log2² ≈ 2.08·ln², its penalty
     is about half of v1's. It runs today only on the onset envelope; on Beat This activations it is [untested], and M2
     can compare the two.
6. **Refine** with `beat_grid(start=...)` [code], after three changes [untested]:
   - With `start=`, `beat_grid` fits no straight line and always returns free mode (`use_tracker` is true), so step 7 cannot run. After refining, fit `robust_line` to the refined beats and run step 7's tests on both paths.
   - With too little evidence (a drumless song, a weak bass or guitar stem) it raises `InputError` (a `ValueError`). Return the start beats unrefined with a "low-evidence" flag instead.
   - Refining on bass or guitar onsets when there are no drums (critique G3) is the caller's choice of stem today (the module docstring says "or the mix"), and `ONSET_TO_BEAT_MS` (−22 ms) was calibrated on drum-stem envelope peaks only. Calibrate it for bass and guitar onsets, or disable it there.
     Inside a song that has drums, drumless beats already follow a second stem calibrated on the same song (Goal 1,
     step 3), so this concerns only songs with no drums at all.
7. **Click or free** (needs step 6's first change).
   - Free when ≥ 60 % of beats have confident drum evidence.
   - Otherwise click, but only after also checking the maximum residual and the longest run of residuals, and allowing free islands inside click mode, which are flagged in the UI (critique G4).
   - The user can override.
   - Free islands are not in `beatgrid` yet [untested].
8. **Fallbacks:** the `small0` checkpoint only behind a "fast" switch (it went to half tempo on every test-song excerpt [here]); manual BPM and ×2/÷2; low-activation regions flagged for review.
- **Cost:** Beat This on CPU 34–45 s per song on 2 threads [here, v1]; on GPU a few seconds [doc]; post-processing about 1.3 s [here, v1]. On the 4070 [untested].

**Not chosen:**
- v1's p95-drift test (click if p95 ≤ 30 ms). The test song passes it at 22–23 ms, yet a straight line misses its drummer (evidence below). `beatgrid` still reports it as `stats["drift_ms"]` [code].
- One tempo marker (STRUM).
- autochart's fine-tuned Beat This.
- librosa `beat_track` (chartgen's choice; F 0.35–1.0, frequent off-beat locks [here]).
- madmom or BeatNet (no Windows wheel; numba pin). allin1 pulls madmom-infer instead, a py3-none-any wheel (§4.3).

**Evidence:**
- **v1's prototype** [here, v1]: test song median 5.9 ms, p95 8.3 ms, 1 marker at 142.0009 BPM. These are residuals of drum-stem onsets matched inside shrinking 45 / 30 / 20 ms windows, in v1's convention (grid on the drum attacks, no offset) [inference from `tempomap_proto.py`], so they are not comparable with the audit yardstick above or with M1. Also: Kimochi Warui at the chart's exact 106.999 BPM; IaSg14's 851-marker chart in free mode at F 0.999, median 11.0 ms; level fold + DP F 0.989 vs 0.725 for Beat This + madmom DBN on the test song.
- **The tools on the six references** [here, 5070]:

  | tool | markers (human mean 112) | beat F1 mean | per song: Kimochi, Drunk Drivers, Take Me Out, All the Small Things, Lucretia, Creep |
  |---|---|---|---|
  | autochart | 337 | 0.87 | 0.99, 1.00, 0.99, 0.97, 0.29, 0.97 |
  | chartgen | 55 | 0.77 | 0.91, 0.77, 0.83, 0.97, 0.27, 0.86 |
  | STRUM | 1 | 0.46 | 1.00, 1.00, 0.12, 0.27, 0.26, 0.09 |

  Lucretia's human chart has 18 time-signature events, i.e. 17 changes, including eight 15/16 bars that x/4 meters cannot represent [here]. It is an outlier for every tool and is reported separately.
- **The tools on the test song,** against the 800 local drum beats found within ±60 ms of the rigid grid [here, guitar audit]:

  | grid | median signed (ms) | p95 \|dev\| (ms) | beats > ¼ beat off | bar line |
  |---|---|---|---|---|
  | autochart (668 markers) | −15.6 | 128.0 | 43 (half tempo at 67.2–89.6 s and 218.5–230.3 s) | on the snare from 90 s |
  | chartgen (81) | +33.1 | 163.5 | 60 (off-beat at 319.1–339.8 s) | one beat before the kick |
  | STRUM (1) | +14.5 | 34.7 | 0 | on the kick |
  | rigid 142.0009 BPM grid | −6.7 | 47.9 | 0 | on the kick |
  | human maps on two references (calibration) | −14 to −18 | 31.9–33.4 | — | kick on beat 1 |

- **Phase conventions agree once the detector is named.**
  - Human maps sit 18.2 and 13.5 ms before rising-edge drum onsets [here, guitar audit].
  - They sit 24.1 and 20.4 ms before `beatgrid`'s envelope peaks (same two songs; `beatgrid.py` docstring; not re-checked) [here].
  - ADTOF hits sit −1.5 to −6.8 ms from Harmonix human notes on 4 songs [here, ADTOF test].
  - `beatgrid`'s median offset to the human beats is −3.0 to +3.0 ms on three references (two of them in-sample) [here, beatgrid run].
- **What matters for notes:** the metrical level, not marker count or a few ms of jitter [here, claims audit].

**Confidence:** Goal 1 medium-low: the method fits a constant-tempo 4/4 song and meets the human median, but its p95
spread on the audit yardstick is above both straight lines, and no `score.py` score exists. Goal 2 low: no Beat This
start has been tried, the bar phase failed on 2 of 4 references, and Lucretia has long stretches off the human beats
(Take Me Out's were fixed by the local periods).

**Would change it:**
- `beatgrid` beat F1@70 more than 0.02 below autochart's on any reference (Lucretia reported separately); Take Me
  Out's share within 70 ms is now 0.986 (step 1), so it no longer suggests this;
- median(beat − nearest ADTOF kick or snare) outside +1.5 to +6.8 ms ± 5 ms (§5.6, task 2);
- the detector-offset measurement (M1a) showing that the spread belongs to the yardstick, not to the grid;
- free maps causing trouble in the Moonscraper polish or the playtest.

### 2.4 Meter
- **Goal 1:** 4/4 throughout, with the bar phase from kick vs snare energy (`beatgrid.bar_phase`): phase 0, margin 0.58 on the test song [here, beatgrid run].
- **Goal 2:** v1's downbeat/meter Viterbi on Beat This downbeat logits **decides** the bar lines; the kick phase only cross-checks [decision].
  - States: (meter 2–7, position in bar). Per-bar −log prior {4: 0, 3: 1.5, 2: 4, 6: 4, 5: 5, 7: 5}; meter-change cost 12.
  - x/4 only in this version. Time signatures are placed at beat indices, so `misalignedTimeSignature` cannot happen [here, critique verdict].
  - Flag "check time signature" when the Viterbi and the kick phase disagree, when `beatgrid` flags its bar phase uncertain (margin < 0.15), when the downbeat contrast is low, or when the 28-beat comb test finds sustained non-4/4 meter.
  - Why the kick phase cannot decide alone: tonight it put the bar lines off the human ones on All the Small Things (0.00 match) and Take Me Out (0.03), both with margins far below 0.15 (§2.3) [here, beatgrid run].
  - Code: `beat_grid` hard-codes 4/4 downbeats from the kick phase and takes no external downbeats [code]. Add a downbeats/meter input, or replace `grid.downbeats` after the Viterbi.
  - The ternary-level test and 6/8 and 12/8 signatures come in M5 (§8). They also need `tempo.py` changes: `TempoMap.from_beats` writes only x/4 signatures [code].
- **Evidence:**
  - test song: 242 bars of 4/4, downbeat on beat 0 [here, v1];
  - from 60 s on, 87–98 % of kick-band energy falls on grid phase 0 and 63–78 % of snare-band energy on phase 2 [here, guitar audit];
  - STRUM's bar lines sit on the kick, autochart's on the snare from 90 s;
  - downbeat F is 0.99–1.00 on 4/4 songs and 0.45–0.67 on Money (7/4); the comb test got 33 of 59 7/4 windows right [here, v1];
  - kick-on-1 on four Harmonix references: downbeat match 0.00, 0.03, 0.99, 0.66 (All the Small Things, Take Me Out, Creep, Lucretia) [here, beatgrid run].
- **Fallback:** 4/4 throughout; the user edits time signatures in the UI.
- **Confidence:** high for Goal 1, low for odd and compound meters. **Would change it:** a non-4/4 bar heard in the test song; downbeat F on the M2 references with time-signature changes (Lucretia has 17) falling well below the 4/4 songs'.

### 2.5 Sections
- **Goal 1, as built:**
  - The test song's sections come from allin1's segments (v1's fold-0 result) through
    `sections.sections_from_segments` and the naming rules below: 26 sections, inside v1's target of 20–30 after
    splitting [code; here, v1; here, review].
  - An imported chart's sections (`sections: "from:<part>"`, e.g. autochart's 10 names: Intro 1, Verse 1–4, Chorus 1,
    Bridge 1, Section 1–2, Instrumental 1) are snapped and merged under 4 measures the same way, but not split:
    `sections_from_chart` takes no `split_over` or `split_into` yet [code].
  - The earlier plan, the boundaries where autochart and STRUM agree (about 43–44, 90–91, 110–112, 167 and 207–208 s)
    [here, guitar audit], is not implemented.
  - autochart's names include no Solo. Its solos are `E solo` spans, which assemble drops; ours replace them (§2.10).
- **Goal 2:** allin1 through all-in-one-infer 3.1.0 (or the original allin1 1.x), with librosa as the fallback.
  - **Built** (`engines/sections.py` [code]). allin1 runs in its own Python (`$SONGCHARTER_ALLIN1_PYTHON`, or
    songcharter's own Python when it has the package; user-site and PYTHONPATH installs count), through
    all-in-one-infer 3.1.0 or the original allin1 1.x, behind a process boundary. Fold 0 on the CPU, the
    `harmonix-all` ensemble on CUDA. Otherwise the librosa fallback, with the reason recorded in `engine.json`.
    - CUDA: the probe runs a CUDA kernel (`is_available()` is also true on a GPU the torch build has no kernels for).
      Out of memory is retried on the CPU. With device auto, any other failed CUDA run is redone with fold 0 on the
      CPU, and engine.json records the fallback [code; untested on a GPU]. The pipeline asks for auto also when the
      user asks for CUDA, since allin1's own Python may have none, and warns when allin1 then ran on the CPU [code].
  - It is fed our cached stems, folded from 6s, as the int16 arrays allin1 reads from Demucs-written WAVs.
    `allin1.analyze()` is not called, so `keep_byproducts` no longer matters.
  - all-in-one-infer 3.1.0 and allin1 1.1.0 (with v1's pure-PyTorch NATTEN shim) gave byte-identical fold-0
    segments, beats and downbeats on the test song and Take Me Out [here, sections engine run].
  - 6s-folded vs ft stems on the test song, fold 0, against v1's ft-stem result: boundary F 0.865 at ±1 s and ±3 s,
    labels agree on 0.770 of the time [here, sections engine run]. The same ft stems through the engine: F 0.895,
    labels 0.925. The rest is the ft "other" stem (peak 1.115) being rescaled about 1 dB, as Demucs's own WAVs would
    be: allin1 is that sensitive to stem level [here, sections engine run].
  - **M2 row 7, measured** [here, sections engine run]. Five references with human sections (Kimochi Warui's chart
    has none). Boundaries snapped by assemble's rules to the reference tempo map; boundary F at ±1 s / ±3 s:
    - fold 0: 0.626 / 0.718
    - ensemble: 0.592 / 0.714
    - librosa: 0.455 / 0.524
    - Before the rules, F at ±3 s: fold 0 0.707, ensemble 0.757, librosa 0.510.
    - Sections after the rules: fold 0 52, ensemble 56, librosa 62; the human charts have 61.
    - fold 0 − librosa: +0.20 at ±3 s (95 % bootstrap over the 5 songs [+0.03, +0.37]).
    - ensemble − fold 0: −0.004 [−0.07, +0.05]. The ensemble buys nothing measurable here.
    - Lucretia is in the Harmonix Set, so it is in fold 0's training data. Without it: fold 0 0.600 / 0.716,
      librosa 0.372 / 0.459.
  - **Decision:** allin1 by default (fold 0 on the CPU, the ensemble on CUDA, as planned), librosa only as the
    fallback. **Open (owner, §9 Q29):** whether CUDA should use fold 0 too. After the rules, the ensemble measured no
    gain over fold 0 (−0.004 at ±3 s, CI [−0.07, +0.05]; −0.034 at ±1 s, CI [−0.14, +0.06]). Its raw boundaries are
    slightly better (+0.05 at ±3 s, CI [+0.006, +0.096]). The CUDA path is untested.
  - **In the pipeline** [here, pipeline run]: all-in-one-infer fold 0 gave the same segments as the sections engine
    run on both songs, so 27 sections on the test song and 12 on Take Me Out after the rules. Its runner peaked at
    7.8 GB RSS on the test song and 4.8 GB on Take Me Out, the largest process of the pipeline (§7).
- **Naming rules** (v1's, as `sections.py` implements them) [code]:
  - drop allin1's "start" and "end"; snap each segment start to the nearest measure start (ties to the earlier one);
  - merge a segment under 4 measures into the one before it (the first into the one after it), shortest first
    (`SECTION_MIN_MEASURES`);
  - merge, then split, per run: consecutive segments with one label form one run, and a run over 16 measures splits at
    even measure positions into round(length / 8) parts (`SECTION_SPLIT_OVER`, `SECTION_SPLIT_INTO`; a verse of 18 + 10
    measures becomes four parts of 7). Human median section length is 12–17 s;
  - name in Title Case ("inst" as "Instrumental"): a label that occurs more than once is numbered ("Verse 2"), one that
    occurs once is not ("Bridge"), and the parts of one run are lettered ("Intro A", "Solo 3B"); write as
    `E "section …"`.
- **librosa fallback** (built, numpy/scipy/librosa only): Laplacian segmentation on beat-synchronous CQT and MFCC.
  The cluster count is the one whose segments, after those under 16 beats merge, come closest to one per 25 s of
  music; 15 and 20 s scored worse (in-sample). `beats=` takes a beat list (times outside the audio are dropped); the
  pipeline passes none, so librosa's own tracker runs [code].
  - Names: no vocals (vocal stem below −20 dB against the mix) at the ends gives Intro and Outro. Elsewhere no vocals
    gives Solo when the guitar stem is ≥ 2 dB above its median, Break when the mix is ≥ 6 dB under its median, else
    Instrumental.
  - Of the clusters with vocals, the loudest one that repeats is the Chorus, a single one between choruses the Bridge,
    the rest verses.
  - Label agreement with the human names: 0.475 (fold 0: 0.615). The naming is untested.
  - Assemble's merge-then-split erases its boundaries between consecutive segments with one label (Take Me Out: F at
    ±3 s 0.571 raw, 0.385 after the rules) [here, sections engine run].
- **Evidence:**
  - The published All-In-One figures (0.740 / 0.596 / 0.730: accuracy, boundary F@0.5 s, F@3 s) are for the 8-fold ensemble, in-domain on Harmonix [doc] (critique E7). A single fold should do worse.
  - SongFormer publishes 0.807 / 0.696 / 0.780 [doc].
  - v1, one song: librosa scored F@3 s 0.80 (k = 8) and 0.70 (automatic k) against IaSg14's 24 sections [here, v1].
    On the five M2 references the built fallback scores 0.524 after the rules (above).
  - v1: allin1 and librosa agree only at F 0.65 on the test song [here, v1].
- **Cost** [here, sections engine run; 2 threads, dev container]:
  - all-in-one-infer fold 0: 54–79 s per reference song, 107 s for the test song (inside the pipeline run: 118.7 s
    for the test song, 70.2 s for Take Me Out [here, pipeline run]).
  - allin1 1.1.0 + shim: 22 s (Take Me Out) and 37 s (test song). all-in-one-infer's attention and madmom-infer are
    about 3x slower.
  - Ensemble on the CPU (allin1 1.1.0): 63–148 s.
  - librosa: 2–8 s.
  - On GPU, the ensemble processed 10 songs (33 min of audio) in 73 s on an RTX 4090 [doc].
- **Confidence:** medium-low (5 references, n = 5 bootstrap, Lucretia in allin1's training data). **Would change
  it:** section scores on the M2 row-8 set; the friend's feedback in practice mode; the ensemble on GPU disagreeing
  with fold 0; the 6s-vs-ft comparison on more songs than the test song (F 0.865 there).

### 2.6 Grid snapping (the quantizer)
The quantizer is the only place where seconds become ticks (Resolution 192). It exists as `quantize.py` [code]; this section is its design, and §2.0 lists where the code still differs.

1. **Remove each source's offset first.**
   - STRUM: add back its audio trim, read per song from STRUM's log or meta (`phase_offset_ms`: 69.7 ms on the test song, 300.1 ms on Take Me Out) and passed to the importer as `time_offset` [here, 5070 logs]. That the trim causes STRUM's lateness is an inference (comparison).
   - Then the quantizer removes each instrument's offset measured against our grid (`estimate_offset`, from the circular mean of note phases, applied when the phases make it certain) [code]. On the test song [here, quantizer check]:

     | source | offset vs a grid from the audit's local drum beats (−16 ms) | offset vs the rigid line |
     |---|---|---|
     | STRUM drums | +32.3 ms | +21.0 ms |
     | STRUM bass | +35.0 ms | +20.5 ms |
     | ADTOF drums | +3.3 ms | −8.2 ms |
     | autochart guitar | +0.8 ms | −9.2 ms |

   - The audits' +33.9 ms (drums) and +22.6 ms (bass) against their proxies are diagnostics only; the applied value is the quantizer's estimate against our own grid.
   - Hits then snap to the beat slot they belong to, and the final timing follows our grid's convention.
2. **Grid per beat** (the code's):
   - every beat is straight (1/16 slots) or triplet (1/12 slots: 8th-note triplets); a beat goes triplet only inside a run of notes that fits triplets clearly better;
   - a note snaps to the nearer slot, with a cost weighted by log-priors from the Harmonix Expert grid mix (1/4 41 %, 1/8 33 %, 1/16 17 %, 1/12 5.3 %) [here, v1], so the coarser line wins near the midpoint;
   - straight and triplet mix within a beat in only 1.4 % of Harmonix beats [here, v1];
   - v1's 1/32 and 1/24 burst grids are not used: drums snap to 1/16 plus triplets, the sources barely write them, and
     a 1/32 level would keep the rounding of a source on a 1/32 grid. Spacing is not the reason: a 1/32 is under the
     55 ms HOPO spacing only above 136 BPM (80 ms strums: 94 BPM), a 1/24 above 182 BPM (125) [code]. Whether they
     come back for imported sources is open (§9, Q16);
   - a note on an odd 1/32 of a source on a 1/32 grid takes the coarser of its two slots when within 1/4 slot of their
     midpoint and the source has no onset on that coarser line (`odd_32nds`). A source counts as on a 1/32 grid when at
     least 95 % of its onsets lie within 0.05 of a 1/32 of its own 1/32 lines (STRUM 0.97–1.00; autochart 0.92–1.00;
     ADTOF 0.11–0.12, chance). On the test song STRUM drums go from 32 to 15 notes a 16th off the stem's hit [code].
3. **Clean up.** Merge onsets on the same tick (the union of their frets), then apply the difficulty's chord limits. Onsets at least ¾ of a slot apart are not merged: one moves to its free neighbouring slot. An onset closer to the previous one than the minimum spacing (strums 80 ms, HOPOs and taps 55 ms) is dropped, so `brokenNote` (≤ 15 ms) cannot occur.
   - A merge takes the union of frets, so a single-note source gains chords: on the bass engine 69–172 onsets per
     song merged on All the Small Things, Lucretia and Creep (Expert chord share after quantizing up to 0.074). The
     human bass charts: 0 on Take Me Out, Lucretia, Creep and Kimochi Warui; 0.41 on All the Small Things Expert and
     0.42 on Hard (two-lane shapes G+Y, B+O, Y+O, mostly in the second half), 0 on its Medium and Easy [here, bass
     engine run]. Open (§9 Q27).
4. **HOPOs.**
   - Keep the source's HOPO/strum intent (`TimedNote.hopo`). Where it disagrees with the natural rule on our grid, write an `N 5` flip (critique G1).
   - **Exception:** wherever the source's local beat period differs from ours by ≥ 1.5×, treat the intent as unknown (`hopo=None`) and let the natural rule decide. autochart's 71 BPM stretches are the case: there its 8ths were natural HOPOs on a wrong grid [inference from the claims audit]. On the rigid grid, 11 of the 28 flips the quantizer writes on autochart's Expert fall inside its two half-tempo stretches, which hold 106 of its notes [here, quantizer check].
   - **In the code, a different rule** [code]. The beat-period comparison is not implemented. Instead assemble's
     default `hopo: "forced"` (`QuantizeRules.forced_only`) reproduces only the states the source forced
     (`TimedNote.hopo_forced`: a `.chart` `N 5`, a `.mid` forced HOPO or strum); every other note follows the natural
     rule on our grid, so a natural HOPO that only the source's wrong tempo map made (8ths on a half-tempo map) does not
     become a forced one. `"source"` reproduces every state, `"natural"` none. Which rule stays is open (§2.0).
   - Rule-based engines give `hopo=None`, and natural rules apply. Neither forced HOPOs nor attack strength is predictable from audio (AUC 0.48–0.53 [here, v1]), so a rule engine cannot supply intent; a forced-strum rule for rule engines is M5 (§8).
   - An imported rule-engine chart reads back with the natural HOPO states of its own 120 BPM map; use `hopo:
     "forced"` (the pipeline does) or `"natural"` for it, never `"source"` [here, bass engine run].
5. **Sources already on our grid** (Engine A, §2.7): a per-source flag keeps exact ticks and still runs spacing, chord, sustain and HOPO rules [untested; not in `quantize.py`].
6. **Drums:** one hit per pad per tick; cymbal/tom collisions as in §2.9; at most two hand pads per tick; 2x kick on Expert only.
7. **No taps** in this version (`quantize.py` keeps Expert taps today; §2.0).

- **Not chosen:**
  - v1's "natural HOPOs only, drop every `N 5`": autochart's HOPO κ against humans is 0.77 (Drunk Drivers) and 0.74 (Take Me Out), and natural-only rules cannot force a strum (critique G1).
  - Keeping a source's ticks and tempo map: autochart's map has 668 markers and two half-tempo stretches [here].
- **Evidence:**
  - about 95 % of human guitar and bass notes sit on 8th positions [here, v1];
  - the natural-HOPO threshold in `.chart` is ≤ 65 ticks at Resolution 192 [here; scan-chart];
  - STRUM's 26 off-grid drum notes in 13 pairs produced a `brokenNote` [here, drums/bass audit];
  - on the rigid grid, autochart's Expert keeps 95 of the source's 96 HOPO states, with 28 flips [here, quantizer check].
- **Confidence:** medium. The architecture is solid; the parameters are unmeasured. **Would change it:** re-quantization moving more than 2 % of source onsets by more than 25 ms (an M1 check); M2 HOPO κ lower for "source intent" than for "natural only".

### 2.7 Lead guitar (5-fret)

#### Goal 1: autochart takes, imported (if the friend plays guitar)
- **Source:** the autochart (Fretformer 2) Expert output from the 5070 run, read with `importers.read_chart`. No autochart code is imported.
- **Takes:** the v1 chart uses four: the GPU take plus CPU seeds 101, 202 and 303, made with `AC_SEED`
  (`eval/tools/autochart/ac_headless.cjs`) and spliced per section (Several takes, below).
  - Cost per seed: about 3.2 min of decoding (3.8 min per job) on the 5070 [here, 5070], or about 7 min per Expert job on the dev container's CPU [here].
  - The earlier CPU take used the same seed (20260609) as the GPU take: 14 of 18 scored song × difficulty pairs came out identical, so it is not an independent take [here].
- **Choose per section:** gross-failure checks first (coverage of active 1-bar windows; density against other-stem onsets), then by ear.
  For the v1 chart the choice was made by agreement between takes (below), not yet by ear.
- **Replace 341–399 s.** In the 57.5 s from 341.5 s, the GPU take has 98 notes against 230 other-stem onsets. Before 340 s it has 1,029 notes against 1,176 onsets [here]. Use a new seed's take there if it passes the checks; otherwise regenerate the window with the autochart app's inpaint (the hand fallback).
  In the v1 chart the seeds' takes replace it (below).
- **Chords:** keep autochart's Expert chords, except invalid ones and chords of 4 or more notes.
- **Ours, not autochart's:** quantizer and HOPO handling (§2.6), sustain rules (below), tiers (§2.11), star power and solos (§2.10). Its lower tiers are not nested (only 74 % of Hard's onsets occur in Expert) and would triple its run time (652.8 s vs 228.8 s on the test song) [here, 5070].

#### Several takes (the v1 chart of the test song)
What was done for the test song's v1 chart, first as a script and then as code: `songcharter/takes.py`, used by a
part's `takes` key in the assemble config [here, takes].
- **Takes.** autochart ran four times on the test song: the GPU take plus CPU seeds 101, 202 and 303, Expert only.
  All four takes share one tempo map (identical `[SyncTrack]`), so they splice at tick level.
- **Choice per section** (the 26 sections of the built chart):
  - each take is scored by its mean F1 at 50 ms against the other three takes, where a match must also agree on
    single note against chord;
  - the original (GPU) take stays unless another beats it by 0.05; then the best-scoring take is used;
  - sustains are clipped where the take changes;
  - notes after the guitar's fade-out are dropped: the last 0.1 s frame of the "other" stem within 25 dB of its P95
    (assemble's `SILENT_DB`; the ft stems have no guitar stem).
- **Results:**
  - Over the whole song the original take was the least central: mean F1 to the others 0.77, against 0.80–0.83 for
    the seeds.
  - In 5:41–6:39 (340–400 s) the three seeds agreed with each other at F1 0.73–0.84, while the original agreed with
    them at 0.55–0.60 and had half their onsets (104 against 176–226). So the original was dropping notes there.
  - 17 of 26 sections took a seed. The spliced Expert has 1201 onsets (original 1137) and a chord share of 0.64
    (original 0.44; the seeds 0.53–0.72).
- **The audio barely separates the takes.** The "other"-stem onset proxy moves only from 0.243 to 0.256 within
  50 ms, because the stem's onsets are smeared in the loud sections. The choice rests on agreement between takes, not
  on the audio.
- **In the code** (`takes.splice`): the same rule on the sections assemble builds (now built before the parts), on
  any part with `take_difficulties: "expert"` and two or more takes (one hit against several on drums). The fade-out
  cut is not part of it: the end is left to assemble's edge trimming (§2.8, 30 dB), which on the test song keeps 3
  more onsets in the fade than the script did (1204 against 1201; reported as onsets in silence). On the test song
  it reproduces all 26 of the script's picks. report.json lists every window's scores and pick under
  `parts.<name>.takes`.
- **Rules added by a review of the code** (each with a test):
  - takes that all leave a window empty agree fully, so two silent runs outvote one that writes notes there;
  - a sustain is cut 60 ms before the next window whose notes come from another take; a window that take leaves
    empty (a break no take plays in) does not count, so a chord can ring over it;
  - the offset is measured on the source's Expert before splicing, and the windows are cut on the takes' clock
    (section start plus that offset);
  - a run listed twice, a take with the same Expert notes as another run, and an output folder that is one of the
    takes are refused.
- **Plan:** for Goal 2, run autochart several times when time allows (about 3.2 min per seed on the 5070). Measured
  since on the references, below.

#### Several takes for Goal 2: the takes experiment
The base take (seed 20260609) and seeds 101, 202 and 303, GPU takes from the 5070, each song's Expert guitar built
through assemble alone (6s drum and guitar stems, `hopo` "forced") and spliced by `takes.splice` on allin1's fold-0
sections, scored with `score.py` against the six human charts [here, takes experiment].
- **4 takes beat 1, by a little.** Spliced (SPL-A) minus the base alone: **+0.013 Expert F1@50** on the five songs
  without Lucretia, per song +0.000 to +0.027 with no loss. Lucretia is reported apart, as §3.2 asks: our grid's
  beat F1 there is 0.261 (4/4 throughout against the human chart's 17 time-signature changes), and splicing lost
  −0.016 there, all in two verse windows where two takes sharing an omission outvoted the base. All six: +0.009.
  - Percentile bootstrap 95 % CI [+0.003, +0.024], anti-conservative over five values; the t-interval includes 0
    ([−0.002, +0.029], recomputed here from the experiment's per-song differences); Wilcoxon p 0.125, the smallest four non-zero
    differences can give (Creep's is exactly 0).
  - **The gain is mostly precision:** precision@50 +0.028, recall@50 −0.003. In the windows that took another take,
    our onsets fell from 935 to 792 for almost the same matches (740 → 732): the replaced windows are ones where the
    base wrote too many notes.
  - With each seed as the base in turn the splice beats its own base by +0.033 [+0.005, +0.069] (14 of 20 song × base
    pairs better, the worst −0.019), and the spread across bases falls from 0.080 to 0.025: the value is protection
    against a bad draw (Kimochi Warui's 0.600 take becomes 0.804 spliced).
  - The windows hardly matter: human sections beat allin1's by +0.004, plain 8-measure windows by +0.0055.
- **How many takes** (corrected by the experiment's verifier): **3 takes give about +0.006 to +0.0105 over one, not
  worse than one** (REPORT.md had −0.017): +0.006 [−0.014, +0.025] with the default base (median +0.003), +0.0105
  [−0.0005, +0.023] over all 12 base × pair combinations (32 better, 20 worse, 8 equal of 60; worst −0.099). **4 takes
  beat 3** with the same base by +0.022 [+0.001, +0.055] (median +0.008, carried by Kimochi Warui), so 3 is the
  riskier choice. 2 takes do nothing: assemble refuses them and `splice` returns the base.
- **Cost on the owner's GPU** (RTX 5070): 4 takes are **3.41×** the guitar stage (1001 s for one take over seven
  songs, 3414 s for four; 2.3–4.4× per song), **+5.75 min a song** on average (1.6–11.4). CPU times were not
  measured in the experiment; on the dev container one more take is one more transcription, 217 s for the test song
  (§5, M3), so three more would add about 11 min there [inference].
- **Decision** (`pipeline.guitar_takes`) [decision, on this evidence]: **4 takes when the guitar stage runs on CUDA,
  1 on the CPU, never 2 or 3 by default; `--takes N` (1, or 3 or more) overrides on any device.** The first CUDA take
  runs alone first: when its summary shows the transcriber off CUDA (autochart fell back by itself), the run warns
  and uses that take alone, rather than three more CPU transcriptions. `pipeline.json`'s `takes` records how many,
  whether by default, and why.
- Three of the experiment's Creep builds failed the gate on `noteAfterAudio` (seed 303's last chord rings past the
  audio's end); assemble now clips it (§2.13).

#### Under-charted strumming: a detector, no fill
The friend found a sparse stretch in the test song around 2:32–2:35 of the original song (his clarification; an
earlier message gave 2:27–2:29 and was withdrawn). The research tried
to detect, from the guitar's pick noise, where our chart is too sparse, and to fill it with 8th or 16th notes
[here, strumming research].
- **Detector:** the 6s guitar stem's 2–7 kHz band energy (a "dominance" control keeps only the cells where the
  guitar stem is louder than the drum stem, against hi-hat bleed), its beat-locked modulation over 2-measure windows
  of our grid: the 8th-rate ratio r2 and the 16th-rate r4 against the window's median, a threshold T = 20 fixed in
  advance; a window is flagged when it is active, pulses at the 8th or 16th rate, and our chart has under half the
  onsets that rate implies. Scored against the six human charts (with our SPL-A chart as "ours").
- **It failed:**
  - **held-out precision 0.22 (6/27)**, leave one song out (the human has at least 4 more onsets per 8 beats than
    ours); a priori 0.27 (6/22);
  - **an audio-free baseline does as well:** flagging every window where our chart has under 1 onset per beat gives
    0.26 (10/39), with higher recall (10 of 41 under-charted windows found, against 6);
  - **16th-note detection 0/22**; in flagged windows the human charts the detected rate in 1 of 27 held out;
  - our chart's own onsets per beat predict the human 8ths better (AUC 0.62–0.99) than the audio feature (0.69–0.81,
    0.40 on Kimochi Warui); only 6 of 269 windows on five songs are clearly under-charted.
  - The friend's times read on the chart's clock (input + 3.342 s) are input 148.8–152.2 s (2:32.1–2:35.5 there):
    r2 17, not flagged at T = 20; at T = 10 it is. Read on the recording's own clock, input 152.2–155.5 s, the
    window has r1 59, r2 1.7 and r4 2.0, below both T tried (10 and 20) [here, strumming research's stored
    features]. Which clock he used is not known; the verdict below holds either way.
- **No fill was built**, and nothing in songcharter changed: the research stopped, as planned, once the detector
  proved unable to drive a chart change.
- **The verifier's corrections** (the numbers reproduce exactly on all seven songs; the verdict holds):
  - in the friend's window the guitar band **pulses mainly at the beat rate** (r1 59 against r2 17; in the drumless
    152.2–165.7 s after it r1 53–68, r2 1.7–10), while our chart has **2–5 onsets per 8 beats** across 148.8–165.7 s,
    below quarter-note density: **an 8th-note fill is not the remedy**, nor a lower T;
  - **under-charting at the beat rate was not tested**, and the references cannot test it (11 active 2-measure
    windows with fewer than 0.5 onsets per beat);
  - **the hi-hat control is not neutral:** it cuts notches at hi-hat hits (4–11 dB), it alone makes the test-song
    flag at 2:05.1–2:08.4 (r2 14.8 → 55.7), and 12 of the 22 a priori reference flags have the guitar and drum pulses
    in opposite phase;
  - **the false-alarm rate at T = 20 is about 0.26–0.29** (in active windows where the human charts almost nothing),
    not the 1 % its odd-bin null suggested;
  - also: 3 of the 6 hits are 16th-rate flags in Take Me Out's body; the 1-measure held-out result is 59 flags,
    precision 0.22, recall 0.14; a Hann taper drops 3 of the test song's 10 flags at T = 20.
- **Would reopen it:** someone marking by ear which test-song stretches are under-charted, and whether by missing
  beats or late notes; ground truth of what the guitar plays (multitracks or verified tabs); 20–25 more strummed
  songs with human Expert guitar; a beat-rate rule with its threshold fixed in advance.

#### Goal 2: the engine route (B1, decided in §9 Q3)

| route | what | for | against |
|---|---|---|---|
| **B1** | autochart's engine as a separate program (`autochart-engine.cjs generate --job`) | measured (the numbers below are its numbers) | We would ship AGPL code, with its source obligations (plus FFmpeg's LGPL). It always runs its own htdemucs_6s, so separation runs twice. An internal job contract, not a released CLI. Our tempo map only through `source_chart_sync`, quality unmeasured. Needs Node 24 + onnxruntime-node [here, practicality audit], beside scan-chart's Node 22 (§4.3). Our job.json driver `ac_headless.cjs` was modelled on reading the app's code ("This file is our own code") and needs a provenance record like G13's if B1 ships. |
| **B2** | our own onnxruntime driver for the Fretformer 2 weights (v1's Engine A) | no AGPL code; our stems and beats; tokens can be cached | unmeasured on any whole song |
| **D** | build on autochart (fork or upstream) | it already has a UI, takes, editing, inpaint and export | songcharter becomes AGPL; drums and bass would need a second runtime or a port (unverified) |

- **Provisional plan:** build B2 behind the `TimedSong` interface and benchmark it against B1 in M2, over ≥ 3 seeds per song. Adopt B2 under the guitar rule of §3.2:
  - its mean F1@50 ≥ autochart's mean − 0.035;
  - its mean lane direction ≥ autochart's − 0.05;
  - on every song, F1@50 ≥ autochart's on that song − max(0.035, the measured seed spread).

  Otherwise use B1 or D. B1 vs B2 vs D is the owner's call (§9 Q3).
- **Takes:** seeded, with its tokens cached for re-runs (critique G6); several when time allows. As built, 4 on CUDA
  and 1 on the CPU by default (the takes experiment, above).
- **As built** (B1, decided in §9 Q3; `engines/autochart.py` [code]): `songcharter chart` runs the engine's default
  seed (20260609), and for 4 takes on CUDA by default, or `--takes N` (N ≥ 3: a splice needs three runs) on any
  device, seeds 101, 202, …, spliced per section by takes.py; a take that repeats another's notes is left out. The engine's tokens are not cached,
  but each finished take is (its folder, keyed by the input's SHA-256, the seed and the sampling settings). On the
  dev container's CPU the test song's take took 403.5 s, its own htdemucs_6s pass included, inside a 12.7-min run
  [here, pipeline run]; it is not the GPU take of the same seed (Expert F1@50 0.799 between them, exact lanes
  0.304; that run read the 16-bit `input.wav` that `build_refs.sh` writes [inference], this one our float32
  decode).
- **Engine B (rules)** is not built for Goal 1. It is the M5 fallback only if non-commercial weights are rejected. Even then it is not free of NC weights while it reads htdemucs_6s stems (§4.2).

#### Engine A (B2) method, v1's design corrected
1. **Model:** the HF `Dvaro/autochart-models` pack at `8a88855d…` (Fretformer 2, about 0.5 GB, SHA-256s matched). It is run by our Python driver, which follows only the pack's `manifest.json`. Keep a written record of that, because the prototype's author had cloned the AGPL repo (critique G13).
2. **Inputs:**
   - the 6s stems in the manifest's channel layout (piano folded into "other"), all from the same decode, with shared-dB normalisation;
   - 32 mel frames per beat from our tempo map's beats, starting at the extrapolated lead-in beats so that pickups before the first downbeat can be charted (critique G5) [untested].
   - v1's excerpt runs fed `mix.wav` together with 1105-sample-late stems and must be re-run aligned (critique E5).
3. **Decoding:** token by token with a KV cache.
   - **Sampling settings:** default to autochart's T 0.95 / top-p 0.98, the settings behind every measured autochart number and the app's "Standard" preset (`ac_headless.cjs`) [decision]. v1's T 0.9 / top-p 0.95 is benchmarked against it in M2.
   - **End-of-stream guard:** a request for another beat after the last one counts as end-of-stream (2 of 14 runs ran away without it [here]).
   - **Windows:** split at section boundaries into windows of at most min(1280 beats, about 7000 expected tokens), with tokens estimated from onset density; warn near the 8192-token cap (critique E2) [untested].
4. **Ticks through the quantizer.** Model slot j (48 per beat) of beat i belongs at tick `(first + i)·192 + 4·j`, where `first` is the index in `lead.beats` of the first beat fed to the model (the extrapolated lead-in beats included). Engine A emits a `TimedSong` with time = `tm.tick_to_sec((first + i)·192 + 4·j) − pad_seconds`, and the quantizer takes it with the "already on our grid" flag (§2.6 step 5): exact ticks are kept, so the model's 1/24 and 1/32 positions survive the 1/16 + 1/12 grid, and spacing, chord, sustain and HOPO rules still run [untested].
5. **Checks** (design proposals, tuned in M2):
   - scan-chart playable;
   - chord share in [0.15, 0.75];
   - same-fret-repeat share ≤ 0.6;
   - notes/s within 0.6–1.4× the active 8th slots;
   - coverage of active 1-bar windows.
   - With several takes, choose per section by these checks. v1's repeat-consistency selector is dropped, because it rewards loops (critique G5). A section that fails is flagged for review (§8).
6. **Post-process:** keep the model's HOPO/strum intent (§2.6); drop taps; apply the chord limits below and our sustain rules; keep open notes on Expert only.
7. **Scope:** only Expert comes from the model; the lower tiers come from our reducer (§2.11).
8. **Execution provider:** the CPU by default (v1: it avoids mixing CUDA DLLs). autochart's decoder is barely faster on CUDA, so a CUDA or DirectML provider with IO binding (keeping the KV cache on the GPU; critique E1; v1 listed DirectML as an M5 option) is an M2 benchmark item, not a plan [untested].

- **CPU-only, guitar-only mode:** Fretformer 2 Lite reads the mix and needs no separation (P 0.89–0.91, R 0.70–0.73 against guitar-stem onsets on an excerpt [here]).
- **Engine B** (v1, for reference): an active-8th-slot rule plus an optional logistic-regression slot classifier, CQT/pYIN pitch, and a rank-based fret map (`map_v2`, a re-implementation of midi-ch's idea; the GPL code is not copied). Its evidence was measured on the oracle grid on excerpts: 8ths-while-active F 0.816, LR 0.893, lane κ 0.20 [here].

#### Chords, HOPOs, opens and sustains
- **Chords:** audio gives no chord signal (chord AUC 0.01–0.45 with sign flips [here]), so chords are style rules or the model's.
  - Goal 2 Expert limits (v1): shapes adjacent, skip-one or span-3; no G+O; 3-note chords ≤ 5 % and never with both G and O; no 4- or 5-note chords; muted chugs become single notes.
  - Same-EP human charts use 68–69 % chords, so the UI has a chord-density slider.
- **HOPOs:** §2.6. **Taps:** none. **Opens:** Expert only, and only if the model emits them.
- **Sustains:**
  - Sustain if the gap to the next note is ≥ 0.75 beat. End a gap before the next note: max(85 ms, 1/16 note) on Expert and Hard, 1/8 on Medium, 1/4 on Easy.
  - Drop sustains shorter than **max(200 ms, 0.75 beat)** on Expert and Hard (critique E9: CAT/RBN set 3/16 at 71–160 BPM, and Harmonix's shortest Expert sustains are 0.625–0.75 beat).
  - Imported and model sustains are clamped to these limits. autochart's sustains end less than 40 ms before the next note in 27–31 % of cases on the test-song takes, and `badSustainGap` fires 29–336 times per reference song [here].
  - M2 compares the source's sustains with the 0.75-beat rule (v1: that rule reproduces Harmonix sustains with F 0.95–0.99 [here]).

#### Evidence

| engine | Expert F1@50 | note |
|---|---|---|
| autochart | 0.86 (6 songs) | wins 6 of 6; paired +0.283 [0.199, 0.350] over chartgen and +0.266 [0.193, 0.373] over STRUM [here, 5070]. Car Seat Headrest community charts: 0.81 / 0.78, against an 8th-note grid on the human map at 0.86 / 0.77. Mean lane-direction κ 0.465, but 0.37 / 0.39 on those two songs; exact-lane agreement 0.07–0.41. |
| chartgen | 0.57 | ceiling 0.711 at ±100 ms; about 0.64 after removing its lag [est.] |
| STRUM guitar | 0.59 | 0.30 on Kimochi Warui; lanes no better than the trivial baseline |
| Engine B rules | 0.816–0.893 slot F | oracle grid, excerpts |
| Engine A (B2) | — | never scored (critique E5) |

- **Run time (critique E1, confirmed on the 5070):**
  - The test song's Expert job decoded 3531 tokens in 189.3 s on CUDA; the whole job took 228.8 s [here, 5070].
  - Decoding ran at 12.3–40.7 tokens/s on CUDA against 10.1–35.2 on the dev container's CPU [here, 5070; here].
  - The critique's decoder benchmark gives about 8.6 + 0.0079·L ms per step (L = context length) on 3 threads, i.e. 107–204 s per take for the test song [here].
  - Three takes of autochart's engine cost about 9.5–11.4 min [here, 5070].
- **Caps:** 1,280 beats and 8,192 tokens [doc, manifest]. Dense songs hit the token cap first: Lucretia used 9.0 tokens/beat, so about 910 beats. The test song used 3,531 tokens over 933 beats [here, 5070].
- **Faults to scaffold** [here, 5070]: no star-power token; `badSustainGap`; lower tiers not nested.
- **Seed variance:** chord share 15–90 % across seeds [here, v1]; 239 vs 166 Expert onsets in 120–180 s between two takes [here].

- **Confidence:** Goal 1 medium; Goal 2 low.
- **Would change it:**
  - the owner rejecting non-commercial weights (then rules or a Basic Pitch route, both unmeasured, and neither free of NC weights while they use htdemucs_6s stems);
  - the owner choosing D or B1;
  - the B2 vs B1 benchmark above;
  - the level-mismatch test (critique G5) showing that our ×1 level hurts the model.

### 2.8 Bass (5-fret)
- **Goal 1** (if the friend plays bass, or in M1b):
  - Take STRUM's bass onsets, read with the per-song trim (§2.6), as the timing baseline. The quantizer removes the offset it measures against our grid (+35.0 ms on the grid from the audit's local drum beats [here, quantizer check]); the audit's +22.6 ms against its proxy, about 16 ms later than a human, is a diagnostic only.
  - Re-lane them from pYIN pitch on the bass stem with v1's rank/contour mapping.
  - Drop notes after 402.4 s, where the stem is silent. As built, assemble removes from every taken level each onset
    that lies wholly before the stem's first frame within 30 dB of its P95, or wholly after its last (`active_span`,
    `TRIM_DB`; a stricter floor than the 25 dB silence warning, so a quiet intro or fade-out keeps its notes). Nothing
    is trimmed if Expert would lose every note, and a part's `trim_silence` turns it off [code]. On the test song this
    removes the 2 trailing bass notes (402.503 and 405.038 s); 25 and 30 dB give the same trim. Onsets in a silence
    inside the song are only warned about (§9, Q23) [here, review].
  - Fill held notes the stem plays but STRUM missed (16 gaps of ≥ 2 s) with v1's HFC onset rule [untested].
- **Goal 2:**
  - Our rule engine is the product engine. Score it on the 5 bass references (F1@50 after offset removal, lane-direction κ), with STRUM onsets plus pYIN re-lane scored beside it as a benchmark only.
  - **STRUM is never shipped in Goal 2.** It has no LICENSE file and no installer; basic-pitch's TensorFlow pin has no wheel for Python 3.12, while the bootstrap installs CPython 3.13; it has 18 unsafe `torch.load` calls [here, practicality audit]; it used 174–1,189 CPU-s per audio minute [here]. If STRUM's bass wins M2, the next step is to match its gain with our own onset stage. Any shipped-STRUM route (a separate environment or WSL, after a LICENSE) is an owner decision (§9 Q14).
  - **The rule engine (v1):**
    - HFC onset envelope on the bass stem, `librosa.util.peak_pick` (delta 0.05–0.07), snapped per §2.6;
    - `librosa.pyin` (fmin 30, fmax 400), median 20–150 ms after the onset;
    - `map_v2` per phrase window, register per section, no chords, no open notes.
  - **As built** (`songcharter/engines/bass.py` [code]): the three rules above with delta 0.07, onsets at least 60 ms
    apart and not snapped (the quantizer snaps them); pYIN on the stem resampled to 22.05 kHz (frame 2048 holds two
    periods of 30 Hz there), hop 220, in 30-s chunks with 1 s overlap; the note's pitch is the median of the voiced
    frames 20–150 ms after its onset; the leakage gate of §2.2 over −50 to +200 ms; `map_v2` as the prototype code
    (12-note windows in phrases split at 1.5-s gaps), not v1's prose version; register per section not built (the
    engine has no sections). Sustains where the pitch track holds the note's pitch (±1 semitone, octave errors
    allowed, the stem within 30 dB of the mix, dropouts to 35 ms bridged), at least 200 ms, ending 85 ms before the
    next note at the latest [decision; §9 Q28]. No HOPO flags. Output: `notes.chart` on a constant 120 BPM map plus
    `engine.json`, read with `read_song` at offset 0.
  - **Cost:** 9.5–24 s per song on the dev CPU, pYIN 80–85 % of it [here, bass engine run]; 21.1 s for the test
    song in the pipeline run [here, pipeline run].
  - **pYIN cost:** budget 20–50 s per song, or run it only around onsets (critique E10). It measured 1.5 s per 30 s at the default hop, about 21 s for the test song [here]. At 44.1 kHz, fmin 30 needs frame_length ≥ 2941.
  - **Fallback:** torchcrepe-tiny (contour 0.989 on Kimochi Warui, slower [here]).
- **Evidence:**
  - **STRUM:**
    - on the references, F1@50 0.59 and lane direction 0.57 against a trivial 0.53 (κ 0.21) [here, 5070; κ here, bass engine run];
    - on the test song [here, drums/bass audit]: combined proxy F1 0.476 / 0.635; its lane follows pitch on only 0.331 of pitch changes (the human chart on Take Me Out: 0.815); 54 of 309 active seconds have no note; its Easy has 0.024 of Expert's onsets.
  - **One global offset** lifts STRUM bass from 0.611 to 0.732 (+20 ms, 3 CPU-run songs) [here].
  - **Our rules on whole songs** [here, bass engine run; 6s stems; Expert]: raw on the constant map F1@50 0.722,
    F1@100 0.779, lane direction 0.752 (trivial 0.541), exact lane 0.357; after our quantizer F1@50 0.800 (Take Me
    Out 0.912, All the Small Things 0.735, Lucretia 0.912, Creep 0.689, Kimochi Warui 0.752), F1@100 0.811, lane
    direction 0.781 (trivial 0.542), exact lane 0.356, density 1.30×, sustain share 0.18 (human 0.20, per song far
    apart). The quantizer's merges write chords (Creep 0.074, Lucretia 0.045). The leakage gate removed 2 onsets in
    five songs. delta 0.05 is worse (quantized 0.776). v1's 0.863 was oracle-grid on its own development excerpts
    (Kimochi Warui and Foo Fighters' "Breakout"). pYIN contour agreement is 0.97–1.00 on 3 of 4 excerpts [here, v1];
    basic-pitch's is 0.65–0.74.
    - Lane-direction κ (unweighted Cohen's κ over {−1, 0, +1} from score.py's confusion matrix, ±100 ms matching on
      consecutive reference onsets: the recipe behind autochart's 0.465; the always-same baseline has κ 0), after
      our quantizer: 0.733 / 0.532 / 0.571 / 0.427 / 0.798 (Take Me Out / All the Small Things / Lucretia / Creep /
      Kimochi Warui), mean 0.612; raw, mean 0.561; STRUM as scored 0.409 / 0.221 / 0.098 / 0.160 / 0.180, mean
      0.214. κ is well above chance on all 5 (All the Small Things 0.53, 95 % CI 0.46–0.60), although agreement there
      (0.827) is under the always-same 0.845, because 84.5 % of that reference's pairs repeat the lane.
  - **Against STRUM, like for like** [here, bass engine run]: STRUM's `notes.mid` through exactly the engine's
    assemble config (bass only, offset auto, hopo forced, 6s bass and drums stems, its phase offset as time shift),
    on the 3 songs with a STRUM folder here:

    | | Take Me Out | All the Small Things | Kimochi Warui | mean |
    |---|---|---|---|---|
    | ours, after our quantizer, F1@50 | 0.912 | 0.735 | 0.752 | 0.800 |
    | STRUM through the same quantizer | 0.848 | 0.897 | 0.519 | 0.755 |
    | STRUM, its own median removed | 0.782 | 0.886 | 0.361 | 0.676 |
    | STRUM's folders as scored | 0.665 | 0.805 | 0.361 | 0.611 |
    | κ, ours | 0.733 | 0.532 | 0.798 | 0.688 |
    | κ, STRUM through the same quantizer | 0.451 | 0.162 | 0.266 | 0.293 |

    - The quantizer applied +33.4 / +25.1 / 0 ms to STRUM (0: Kimochi Warui's estimate was untrusted) and +19.7 /
      +23.6 / +14.3 ms to ours.
    - Lucretia and Creep only have GPU score files here. STRUM's F1@100 there (0.883 / 0.571) is under our quantized
      F1@50 (0.912 / 0.689), and on the 3 measured songs STRUM's quantized F1@50 never exceeded its F1@100, so we
      probably lead on both [inference].
    - All the Small Things is STRUM's: we over-chart it (precision 0.598, 1068 onsets against the human 670).
  - **Test song:** 820 onsets, last at 401.7 s; its lane follows pitch on 0.679 of pitch changes (STRUM 0.331, the v1
    chart 0.330) and leaves 32 of 309 active seconds empty (STRUM 54) [here, the drums/bass audit's checks re-run in
    the bass engine run]. The v1 chart's bass has STRUM's lanes unchanged (exact lane agreement 1.0): the Goal 1 pYIN
    re-lane was not applied.
- **Confidence:** medium-low (measured on 5 songs, 4 held out). **Would change it:** more references; the friend playing bass (which raises the priority); pYIN octave errors lowering lane direction.

### 2.9 Drums (4-lane pro)
**Goal 1** (if the friend plays drums, or in M1b):
- Use STRUM's drums for the lanes (pads and cymbal flags).
- Re-time them: add back the per-song trim (69.7 ms on the test song), let the quantizer remove the offset it measures against our grid (+32.3 ms on the grid from the audit's local drum beats [here, quantizer check]; the audit's ≈ +34 ms against its proxy is a diagnostic), quantize. This also clears the 26 off-grid notes.
- Add our own tiers (Easy keeps cymbals), star power and fills.
- **ADTOF's existing test-song chart** is an available input: 1,595 notes from 1,185 hits on the 6s drum stem, stem lag 0, sync OK [here, ADTOF test]; the quantizer measures its offset at +3.3 ms [here, quantizer check]. Check it against the audit's 71 missed kick-like onsets.
- Merge in ADTOF kicks only if the fusion test, re-run with de-duplication per grid slot, gives kick F1 ≥ STRUM's on the 3 references (§2.14, C4).

**Goal 2:** ADTOF is the provisional product engine for onsets and kicks, on condition of a lane mapper better than v1's `drummap2` [decision: the ADTOF test calls ADTOF "worth keeping as a candidate" and names the lane mapper as the experiment to run before choosing]. STRUM stays the lane benchmark and the Goal 1 source; it is never shipped in Goal 2 (reasons in §2.8).
- **Model:** ADTOF Frame_RNN through our pure-PyTorch re-implementation (73 lines; no madmom, TensorFlow or torchaudio), written from reading `xavriley/ADTOF-pytorch`. Weights: the 3.6 MB `.pth` hosted there, loaded with `weights_only=True`. Pinned: commit 85c192e78f716ea0b111cc8a5ee4a8f6a3a4f8a9, 3,617,805 bytes, SHA-256 1bc986e5…17320. Built (`engines/adtof.py`): on the ADTOF test's own stems and librosa tempo, with the hat gate (G3) and 2x kicks off, its notes.chart equals that test's on all six songs apart from the [Song] header's name, artist and charter; scores identical to its table [here, drums engine run]. With the default 2x kicks, Lucretia's four fastest kicks become 2x kicks (N 32). Its host states no licence; the CC BY-NC-SA 4.0 label is inherited from upstream ADTOF, whose whole repository, code included, is BY-NC-SA [doc]. The port's code licence is uncertain (§4.2).
- **Fusion:**
  - kick (BD), snare (SD) and toms (TT) from the drum stem; hi-hat (HH) and cymbals (CY) from the mix. Reason: Demucs drum stems can delete the ride (CY F 0.16 on the stem vs 0.96 on the mix), while the mix adds false kicks (54 vs 26 on a test-song excerpt) [here, v1];
  - peak thresholds BD, SD, TT, HH, CY = [0.22, 0.24, 0.32, 0.22, 0.30];
  - peaks: a variant of madmom's NotePeakPickingProcessor at ADTOF's settings (the same threshold test; the maximum
    of the activation minus its moving average, and the strongest of a chain), so about 5.6 % of peaks come one frame
    (10 ms) earlier than madmom's, with no measurable change in score [here, drums engine run];
  - merge: peaks less than 30 ms (two frames) after a hit's first peak join it; no constant offset (the quantizer
    measured +0.5, +1.5, 0.0, 0.0 and −6.4 ms on the five references [here, drums engine run]);
  - G3, as built: a mix HH or CY peak is kept where the drum stem plays around it: the stem's power over ±0.5 s,
    every band, within 40 dB of the mix's. On the five references this removed 2 false hats (Take Me Out's intro,
    stem at −81 dB) and 4 real rides (Creep 192–201 s, where the stem lost the ride). Effect: F1@50 +0.001 and
    −0.003, mean −0.0004. It removed none on the test song. Reading the plan's "that window" as the hit's own window
    (the stem's highs from 2 kHz, −10 to +30 ms, 30 dB) removed 289 of the test song's 1144 mix hats, all in drummed
    passages (200–260 s and 300–400 s, where the drums/bass audit found STRUM's dropped hi-hat 8ths). In drumless
    stretches (stem 25 dB under its P95 for 2 s or more) the wide reading passes 6–9 % of frames (Lucretia 42 %).
    ADTOF fired 0–3 mix hats per song inside them. A drumless song has not been tested (§9 Q24) [here, drums engine
    run].
- **Lane mapping (`drummap2`, the baseline to beat):**

  | ADTOF class | gem |
  |---|---|
  | BD | kick `N 0` |
  | SD | red `N 1` |
  | HH | yellow cymbal `N 2` + `N 66` |
  | CY in a regular run (≥ 4 hits within ±2 beats) | blue cymbal `N 3` + `N 67` |
  | CY otherwise | green cymbal `N 4` + `N 68` |
  | TT | toms by pitch cluster (dominant 60–400 Hz peak, 1–3 clusters): lowest → green, highest → yellow, middle → blue |

  - At most 2 hand pads per hit.
  - `N 32` (2x kick) only on Expert, when kicks exceed about 6/s.
  - No accents or ghosts. All lengths 0. `pro_drums = True`.
  - Ride or crash counts beats of the mix's tempo from `beatgrid.estimate_tempo` (85–185 BPM), not librosa's. Mean
    lane −0.0009, green −0.013, blue +0.007; All the Small Things green −0.060 (148.4 against 152.0 BPM); Lucretia
    lane +0.006 (98.2 against 129.2 BPM) [here, drums engine run]. The rule is that sensitive to the beat period
    (§9 Q26).
  - 2x kick, as built: a run of more than 6 kicks, each less than 1/6 s after the one before, makes every kick less
    than 1/6 s after the run's last single-pedal kick a 2x kick. On the human Lucretia chart's kicks (one fast run of
    8 sextuplet kicks, 4 marked 2x) the rule also marks 4, but 0 of 4 match: by construction it keeps the run's first
    fast kick single, so here it marks the human's single kicks, including the on-beat kick at beat 366. The
    engine's 4 2x kicks are in that same rule phase. Choosing the phase is open (M2). No other reference has 2x
    kicks, and the rule marks none of Creep's 69 short fast gaps [here, drums engine run].
- **Lane mapper work (M2):** a better rule-based mapper on ADTOF's activations. A learned classifier comes in M5 and needs the owner's consent for training data. The known failure: on Take Me Out ADTOF's lanes agree with the human chart only 0.283 of the time, because it puts many snare hits on yellow (840 yellow candidates against 348 in the human chart) [here, ADTOF test].
- **Collisions** (critique G7): `.chart` cannot hold a cymbal and a tom on the same pad and tick. The cymbal stays; the tom moves to a free tom pad (yellow first, as Rock Band does), or is dropped when none is free (`quantize.py`, `reduce.py`) [code]. RBN's other option, moving the crash to green, is not implemented. M1 reports the dropped count. The Kimochi Warui ADTOF run dropped 89 same-pad collisions [here, ADTOF test]. The ADTOF engine resolves them itself as the ADTOF test did: the tom is dropped (Kimochi Warui: 82), so `quantize.py`'s move to a free tom pad never applies to it (§9 Q25) [here, drums engine run].
- **Cost:** ADTOF itself takes 13–30 s per song on 3 threads (the ADTOF test's totals minus separation) [here]. The engine on 2 threads: 12.7–17.0 s per reference with the model run, 26.5 s for the test song, 7.6 s with its activations cached [here, drums engine run]; 20.3 s for the test song inside the pipeline run [here, pipeline run].

**Evidence, whole songs, 5 references, `score.py`** [here, ADTOF test; STRUM from the 5070 run]:

| | F1@50 (pad-blind) | F1@100 (pad-blind) | kick | red | yellow | blue | green | exact lane agreement |
|---|---|---|---|---|---|---|---|---|
| ADTOF | **0.967** | **0.967** | **0.986** | 0.854 | 0.705 | 0.522 | 0.405 | 0.585 |
| STRUM (GPU) | 0.897 | 0.941 | 0.938 | 0.873 | 0.729 | 0.552 | 0.400 | **0.687** |
| ADTOF engine (seeded 6s stems) [here, drums engine run] | 0.967 | 0.967 | 0.986 | 0.855 | 0.707 | 0.529 | 0.397 | 0.585 |
| ADTOF engine after our quantizer [here, drums engine run] | 0.962 | 0.967 | 0.980 | 0.846 | 0.705 | 0.529 | 0.388 | 0.586 |

- **Not like for like.** ADTOF's charts were written unquantized (a constant 120 BPM map at resolution 480, 1 tick ≈ 1.04 ms); STRUM's are snapped to its own grid and run late, losing about 0.04 to lateness (0.897 at ±50 ms, 0.941 at ±100 ms). After our quantizer [here, drums engine run]: ADTOF F1@50 0.967 → 0.962. Lucretia 0.988 → 0.968 on a grid with beat F1 0.26; F1@100 0.986. Lane agreement unchanged. STRUM's CPU charts (Take Me Out, Kimochi Warui, All the Small Things) go from 0.938 to 0.956, with kicks 0.979 → 0.988 and lane 0.628 → 0.636. On those three songs ADTOF gets 0.961, kicks 0.977, lane 0.385. So after offset removal the onset gap is about 0.005, not ≤ 0.026, and STRUM's kicks are ahead. STRUM's GPU charts of the references are not in the dev container, so they were not re-scored.
- **Metrics:** onset F1 in `score.py` is pad-blind (all pads at one tick form one onset). Exact lane agreement requires the whole pad set of a matched onset to be identical, ignoring cymbal flags [code]. Per-pad columns are per-pad F1@50.
- **Per song F1@50,** ADTOF / STRUM: Take Me Out 0.947 / 0.846; Kimochi Warui 0.978 / 0.985; All the Small Things 0.961 / 0.886; Lucretia 0.988 / 0.880; Creep 0.961 / 0.889. ADTOF's kick F1 on Take Me Out is 0.981.
- **ADTOF timing** against the human charts: −1.5 to −6.8 ms on the four Harmonix songs, −28.0 ms on Kimochi Warui (a chart about 22–25 ms late [here, v1]).
- **Fusion attempts** (3 songs with STRUM CPU output) [here, ADTOF test]:
  - ADTOF times with STRUM's hand lanes lowered lane agreement to 0.489 / 0.550 / 0.496 (STRUM CPU alone: 0.673 / 0.697 / 0.514).
  - STRUM plus ADTOF's extra kicks lowered Take Me Out F1 from 0.933 to 0.887 and kick F1 from 0.982 to 0.892.
- **STRUM run to run:** CPU and GPU runs differ on the same song (Take Me Out: CPU 0.933 at +3.8 ms, GPU 0.846 at −19.9 ms; cause unknown).
- **STRUM on the test song** [here, drums/bass audit]:
  - all-hit proxy P / R / F1 0.951 / 0.843 / 0.893;
  - +33.9 ms against the proxy (by region +38.0, +18.9, +23.1 ms; the human on Take Me Out sits at +8.75);
  - 71 kick-like onsets with no kick or snare charted;
  - hi-hat 8ths dropped in 240–260 s and 310–340 s;
  - ladder X / H / M / E 1238 / 1220 / 860 / 398 with 0 cymbals on Easy (human: 0.853 / 0.648 / 0.534 of Expert, with 34–59 % cymbals on Easy).
- **Practicality** [here, practicality audit]: STRUM used 174–1,189 CPU-s per audio minute in the dev container. Two runs died in a WSL VM reported at about 15.5 GB [reported in the practicality brief; not logged]; STRUM's peak RSS is unmeasured. It has no installer, 18 unsafe `torch.load` calls, loads only 5 of its 7 ensemble models, and has no LICENSE file.
- **v1's excerpt figure** (pro-lane F 0.844) is partly a tuning-set number. On same-song held-out excerpts it is 0.813 (critique E4). Pro-lane F is v1's metric; `score.py` does not compute it.
- **Training overlap is possible for both tools:** ADTOF trained on Rhythm Gaming World custom charts [doc]; STRUM's drums probably trained on 3 of the Harmonix references [here, claims audit].

- **Confidence:** Goal 1 medium; Goal 2 medium-low.
- **Would change it:**
  - A lane mapper on ADTOF's activations that misses the drum-lane rule of §3.2 (mean exact lane agreement ≥ STRUM's mean − 0.02, and on every song ≥ STRUM's on that song − 0.05) without losing more than 0.01 F1@50. Then we train our own, or the owner decides on a shipped-STRUM route (§9 Q14).
  - The de-duplicated fusion still lowering kick F1. Then Goal 1 keeps STRUM's kicks only.

### 2.10 Star power, solos and drum activation lanes
**Guitar and bass star power** (v1's rules):
1. **How many:** K = round(total beats / 40), about 24 for the test song. Humans chart 11 (Harmonix) to 14 (customs) phrases per song [here, v1]; on 175–288 s references that rate is consistent with beats/40 [est.].
2. **Shape:** one measure, starting on its first note (92–98 % of human phrases start on a note). `S 2` covers [T, T + len).
3. **Exclusions:** none in the first 4 measures after the first note or in the last 8 measures.
4. **Score per measure:** +2 contains a sustain; +2 first measure of a section; +1 lead-like (guitar loud, vocal stem quiet). A candidate needs at least 2 Expert notes.
5. **Placement:** split the song into K equal windows and take the best measure in each, at least 24 beats apart.
6. **All difficulties:** copy the phrases to every difficulty. The reducer guarantees ≥ 1 note per phrase on every track and difficulty, so `emptyStarPower` = 0.

**Drums: activation lanes first, then star power** (critique G16, E11):
1. **Activation lanes (`S 64`):**
   - one measure long, ending on its activation note on a measure line; placed at section changes first, then in every
     star-power gap, then wherever 4 measures pass without one (`period_measures`); at least 4 measures apart; none in
     the last bars [code];
   - **crash ending:** a preference, never a requirement. A crash line wins only among the lines a fill may take, and
     `check_phrases` warns (`fillNoCrash`, Expert only) when fewer than half of the Expert fills end on a crash (the
     four Harmonix test references: 0.63–1.00). A hard rule would cost the ADTOF build nearly all its fills, and then
     its drum star power, since ADTOF writes the test song's crashes as hi-hats [code; here, review];
   - **target count:** about one every 4 measures of drumming (Harmonix test references: median gap 4, 5.0–8.7 fills a
     minute; 19–24 on 3–4 minute songs) [decision, in the review: the target is per minute of drumming, which keeps
     the chart closest to the human charters; YARG's generator also steps 4 measures]. The phrases fix's rebuilds of
     the test song got 32 / 29 fills (STRUM / ADTOF drums) on 6:52, 5.4 / 4.9 a minute, at the low end of the Harmonix
     rate [here, review];
   - written on **every drum difficulty**, each ending on a note that exists on that difficulty. scan-chart checks `noDrumActivationLanes` per track, and only when that track has star power, more than 50 notes and more than 60 s [here, critique].
2. **Star power in the gaps:** never overlapping, touching or immediately following a lane. Drums may get fewer phrases than guitar (Encore does not require drum star power; scan-chart skips `noStarPower` on drums).
3. **Unit-test the scheduler** on the test song's 242 bars.

- **Evidence:** human charts have 89 activation lanes across 5 songs (3, 24, 23, 20, 19), mostly 4 beats long; 2 overlap a star-power phrase (1 lies fully inside) [here, comparison]. v1 cites a Harmonix median of 26 per song. STRUM's 8 lanes all sit inside its star power, which reflects how they were placed, not the music.

**Solos** (guitar only; the friend asked for solo trackers, Clone Hero's hit percentage on a solo section):
- **Candidates:** an allin1 "solo" section, or at least 8 bars where the vocal stem is below −30 dB (relative to its P95) while the guitar stem is at or above its P75 [thresholds never tuned; here, solo evaluation]. Only the first is built. assemble's `solos: "stems"` tests the stems on the "Solo" sections alone (`solo_sections` skips every other section before the test runs), so it is the label and the stem test together; the 8-bar stem rule was never built [code; here, solo evaluation].
- **Goal 1:** start from autochart's Expert solo spans (67.9 s for 8.2 s; 218.1 s for 40.6 s) [here, guitar audit]. They begin near where its half-tempo stretches begin (67.2–89.6 s and 218.5–230.3 s), so keep them only after a listening check.
  As built, assemble drops the tools' solos. "stems" placed none on the test song: the vocals stem is active in 56 %
  and 95 % of allin1's first two "solo" sections on v1's ft stems, and in two of the three parts of the third. v1.1
  puts them by name on the two the friend confirmed (`solos: ["Solo 1", "Solo 2"]`, names allin1's own label gave
  them): [167.347, 194.217] and [234.967, 258.42] s [code; here, solo evaluation].
- **Goal 2, the solo evaluation** [here, solo evaluation]. Each rule through `place_solos` on pipeline-shaped builds
  (the five stems the pipeline hands assemble, lead-in 2.5 s, the GPU take seed 20260609, Expert only), against the
  human solos of the six references: Kimochi Warui [249.083, 267.028] and Lucretia [140.725, 217.742] s; the other
  four have none. "Found" is at least 50 % of the human span covered; a false solo overlaps no human solo; note
  recall and precision count the human chart's Expert onsets (576 inside human solos). Pooled, placed spans:

  | sections | rule | human solos found | false / predicted | note recall | note precision | predicted s |
  |---|---|---|---|---|---|---|
  | fold 0 | off | 0/2 | 0/0 | 0.000 | – | 0 |
  | fold 0 | **labels** | 1/2 | 2/3 | 0.889 (512/576) | 0.646 (512/792) | 124.6 |
  | fold 0 | stems (= label and stem test) | 1/2 | 1/2 | 0.889 | 0.906 (512/565) | 90.3 |
  | fold 0 | stem test on every section | 1/2 | 3/4 | 0.889 | 0.735 (512/697) | 122.1 |
  | fold 0 | union (label or stem test) | 1/2 | 4/5 | 0.889 | 0.554 (512/924) | 156.3 |
  | ensemble | labels | 1/2 | 4/5 | 0.889 | 0.533 (512/960) | 168.4 |
  | ensemble | stems | 1/2 | 1/2 | 0.889 | 0.906 (512/565) | 90.3 |
  | ensemble | stem test on every section | 1/2 | 4/5 | 0.889 | 0.714 (512/717) | 126.8 |
  | ensemble | union | 1/2 | 7/8 | 0.889 | 0.460 (512/1112) | 204.9 |
  | librosa | labels = stems | 1/2 | 1/2 | 0.889 | 0.939 (512/545) | 83.2 |
  | librosa | stem test on every section = union | 1/2 | 6/7 | 0.889 | 0.630 (512/813) | 147.9 |

  - Every rule but "off" finds Lucretia's solo and none finds Kimochi Warui's (every allin1 run calls it a chorus),
    so only the false solos separate them. On fold 0, "labels" adds Creep 171.1–186.3 s (inside the human bridge) to
    the one false solo "stems" also makes (Take Me Out 191.5–205.0 s, the human chart's main_riff_4), and runs 19 s
    past Lucretia's solo (to 236.7 s; precision there 0.859 against 0.998).
  - **The test song reverses them.** On the pipeline's own sections (fold 0 on the 6s stems) "labels" places
    [167.346, 180.709], [234.966, 258.419] and [317.782, 368.275] s: all of Solo 2 and the first 13.4 of Solo 1's
    26.9 s (0.497, just under the 50 % rule; allin1 calls 180.94–194.41 a chorus there), plus a third span, Solo 3,
    that nobody has confirmed either way. On v1.1's sections it reproduces both delivered solos exactly, plus Solo 3
    (317.8–381.8 s). "stems" and the stem test place none on any sections source, as the end-to-end run's report.json
    did: Solo 1's vocals share is 0.561 (lead 0.286) and Solo 2's 0.863 (lead 0.611), where the test passes at most
    0.25 and at least 0.5 (Kimochi Warui's human solo: 0.905 and 0.19; Lucretia's 0.012 and 0.779).
  - Through the pipeline itself (the defaults, the CPU take, the same fold-0 sections) the test song got these three:
    [167.346, 180.709], [234.966, 258.419] and [317.782, 361.726] s, the third ending on the CPU take's last onset in
    Solo 3D [here, pipeline-defaults runs; §5 M3].
  - The ensemble (what CUDA runs) misses Solo 1 entirely (it calls it Chorus 2B) and places [234.966, 258.419] and
    [304.256, 385.176]; librosa misses both. "union" equals "labels" on the test song and gains no solo anywhere;
    "intersection" equals "stems" on all seven songs and three sections sources.
- **Decision** (`pipeline.Options.solos`, `--solos`) [decision, on this evidence]: **"labels" by default**: every
  section allin1 labels Solo, within the placement rules below. The friend asked for trackers, and a missed solo costs
  him one where a false one is a tracker he can ignore. The cost depends on the sections allin1 gives. On fold 0
  (the CPU): 2 false solos against the stems' 1 in six songs, one extra false tracker every six songs, for trackers
  on all of Solo 2 and half of Solo 1 on the one song he plays. On the ensemble, which his CUDA PC would run (allin1
  on Windows is untested): 4 against 1, one extra about every two songs, and Solo 2 alone on the test song, Solo 1
  missed (§9 Q29; the ensemble measured as allin1 1.1.0 on the CPU). Even so "labels" gives
  that song a tracker where "stems" gives none. A list of names (`--solos "Solo 1,Solo 2"`) overrides it; "stems"
  and "off" remain, and both "stems" and names need the guitar charted (refused without it, like `--takes`).
  assemble's own default stays "off". No new mode was needed: the union would only add false solos.
- **The evidence is weak:** 2 human solos in 6 songs; Lucretia is in allin1's Harmonix training data, so the label's
  one success on the references is in-sample, and out of sample no rule finds the remaining solo. The case for
  "labels" rests on one song whose two solos the friend confirmed but nobody charted, and Solo 1's 0.497 is
  borderline. The ensemble runs were allin1 1.1.0 on the CPU, not all-in-one-infer on CUDA; the stem thresholds were
  never tuned; nobody listened to whether the busy vocals stem is singing or guitar bleed; the 6s stems give Solo 2
  0.863 where v1's ft stems gave 95 %.
- **Placement:** `E solo` on the first note, `E soloend` on the last (inclusive). No back-to-back solos; expect 1–3 per song.
- **Difficulties:** solos are written on every guitar difficulty. The reducer copies them down and keeps at least one note in each solo on every level (`reduce.py`) [code], so scan-chart's `emptySoloSection`, which it checks on every track, cannot fire.

- **Not chosen:** imported star power (autochart has none; STRUM's 8 phrases placed on the densest Expert windows come out empty on Easy); chartgen's 19 phrases.
- **Confidence:** low-medium: the rules now run on the test song (`starpower.py`), but nobody has played the result.
- **Would change it:** M2 counts and coverage against Encore references; the playtest; the owner choosing to omit fills (then `noDrumActivationLanes` needs a gate exemption). For solos: references with more human solos, outside allin1's training data; the friend saying whether the test song's third "solo" (317.8 s on) is one.

### 2.11 Difficulty reductions
Each level is built from the one above, so the tiers are nested by construction. `reduce.py` implements this [code]; it re-implements the ideas of Onyx and the RBN authoring guide (GPL; no code copied). autochart's own tiers are not used: they are not nested, and they triple its run time [here, 5070].

**Expert only by default** (`songcharter chart`; `pipeline.Options.levels` = `("expert",)`) [decision, on the friend's
feedback on v1: he plays Guitar on Expert, and the charts need only Expert unless he asks]. `--levels all`, or a list
that includes expert (`--levels expert,hard`), writes the others, each reduced from the level above as below; a list
without expert is refused (exit 2). assemble's `levels` defaults to all four. Star power, solos and fills are still
placed on Expert; song.ini keeps every `diff_*` rating, and the CLI summary labels its counts by the levels written
(`guitar: onsets E 868`). The clip at the audio's end (§2.13) runs before the reductions, so a lower level never ends
later than Expert.

**Guitar and bass,** in this order:
1. **Priority per onset:** +4 sustained, +2 on a measure line, +1 on the level grid (0.5 / 1 / 2 beats for Hard / Medium / Easy); then metric strength, then earlier [code]. v1's +8 inside star power is dropped: step 4 keeps star power non-empty instead [decision].
2. **Greedy keep with a time floor:** the minimum gap is the finest of the level's steps that lasts at least a floor at the song's tempo: Hard 1/16, 1/12, 1/8 or 1/4 note with 160 ms; Medium 1/8, 1/4 or 1/2 with 300 ms; Easy 1/4, 1/2 or 1/1 with 500 ms [code]. At 142 BPM this equals v1's "Standard" (0.5 / 1 / 2 beats); at 90 BPM Hard can keep 16ths, which step 9 force-strums. There is no "Dense" preset (§9 Q8).
3. **Hard thinning by subdivision** (critique E3). With 0.5-beat padding, v1's rule kept 97–100 % of Expert on Hard for 8th-note parts [here, critique `reduce_sim.py`]. So a ladder drops whole position classes, finest first (finer than 16ths; 16ths and 8th triplets; the measure's last 8th; the first half's last 8th; the other 8ths; then beats), and only "sandwiched" onsets, toward target shares of Expert onsets: Hard 0.78, Medium 0.50, Easy 0.30 (ceilings 0.80 / 0.58 / 0.36; floors 0.55 / 0.33 / 0.20) [code]. Bass has its own targets (Q19, decided): Hard 0.86, Medium 0.60, Easy 0.45 (ceilings 0.88 / 0.66 / 0.50; floors 0.62 / 0.40 / 0.25; Hard's limit 0.90 keeps it under the `hardNotThinned` error). On the four Harmonix references bass F1 goes Hard 0.872 → 0.891, Medium 0.840 → 0.898, Easy 0.779 → 0.821, guitar is unchanged; the test song's bass does not change, because each level's time floor binds before the ladder there (at 142 BPM Medium keeps at most quarters) [here, Q18/Q19 run]. Basis: Harmonix keeps about 94 % of on-beat notes, 79 % of off-beat 8ths and 31 % of 16ths on Hard [here, critique]; RBN drops every 4th 8th at ≥ 160 BPM [doc].
4. **Star-power and solo coverage:** if a phrase or solo has no note on this level, its strongest upper-level onset comes back and whatever crowds it goes.
5. **Re-limit lanes** (Medium GRYB, Easy GRY) by one contour-preserving Viterbi pass: each note stays near its Expert lane scaled onto the level's lanes, the direction of movement is kept, and fast jumps (Hard: more than 3 lanes within a beat; Medium and Easy: more than 2 within two beats) cost 2 per extra lane [code].
6. **Then simplify chords** against that lane set (critique G8: doing it the other way round can re-create a forbidden G+B):
   - Hard: 3-note → {lowest, highest}; G+O → G+B.
   - Medium: only GR, RY, YB, GY or RB.
   - Easy: lowest note only.
7. **Sustains:** keep the upper level's length, trimmed to end a gap before the next kept onset (Hard max(1/16 note, 85 ms), Medium 1/8, Easy 1/4 note). Drop sustains shorter than max(200 ms, 0.75 beat) on Hard, 1 beat on Medium, 1.25 beats on Easy and 2 beats on Easy bass (`reduce.py`: "the Harmonix p5 shortest sustains" [code; not re-checked]). `quantize.py`'s Easy floor (2 beats) is aligned to this (§2.0).
8. **Flags:** no taps below Expert; open notes become green below Expert.
9. **HOPOs below Expert** (`reduce.py` rule 5 [code]):
   - Medium and Easy strum everything: natural HOPOs are force-strummed with `N 5`.
   - On Hard a note stays a HOPO only when it is a natural HOPO on the Hard notes, Expert plays it as a HOPO or tap, and the Hard note before it is the Expert note before it (the same legato pair). Every other natural HOPO is force-strummed.
   - No HOPO is ever forced on (Harmonix Hard: 1.7 % HOPOs).
10. **Validate and repair:**
    - scan-chart's forbidden notes: Hard no G+O; Medium no orange and no G+B; Easy no blue or orange;
    - every lower onset is an onset one level up (±5 ms);
    - each level differs from the one above.

    scan-chart's `difficultyNotReduced` only compares whole-track hashes, so it misses a Hard that is nearly Expert [here, critique]. Ratio checks therefore apply (§2.14, C11; `reduce.check_reductions` [code]):
    - **error:** a 5-fret Hard (guitar or bass) at ≥ 0.90 of Expert's onsets (critique E3);
    - **warnings:** Hard outside 0.63–0.90, Medium outside 0.36–0.65, Easy outside 0.23–0.49.

    Harmonix averages 0.75 / 0.47 / 0.28. Human guitar ladders run Easy 0.23–0.49, Medium 0.36–0.52, Hard 0.63–1.0; a human Hard can equal Expert (All the Small Things, 680 / 680), and whether that part is 8th-dominated is unverified [here, guitar audit]. Human bass ladders average 0.889 / 0.609 / 0.453 [here, drums/bass audit], so the human bass Hard sits just under the 0.90 error. An earlier draft's carve-out (fail only on 8th-dominated parts at ≥ 0.95) is dropped: no source supports it, and it was not checked against All the Small Things. Tuned in M2.

**Drums:**
1. **Collisions first** (§2.9).
2. **Snares:** padding 0.5 beat on Hard and Medium, 1 beat on Easy [code]. The human Medium of All the Small Things
   plays snare 8ths (24 pairs outside lanes) [here, review].
3. **Hand pads:** padding 0.5 beat on Hard; on Medium, a hit with the hi-hat or ride keeps 1 beat at ≥ 140 BPM;
   outside activation lanes so does a hit with a tom or crash (the right hand on a tom: All the Small Things'
   choruses). On Easy at ≤ 120 BPM, a hit of only hi-hat or ride may sit 0.5 beat from another hand hit; snares stay 1
   beat apart (Harmonix Easy keeps the off-beat ride at those tempos). RBN forbids right-hand 8ths on Medium at
   ≥ 140 BPM, and the test song is at 142 (critique G7).
   - The 120 BPM boundary (half a beat is then at least 250 ms) is judged on the local tempo of both hits [code]. The
     human Easy tiers of Lucretia and Creep have 77–79 % of their hand gaps under 1 beat. The finding's own fix
     scored higher (F1 0.818) but halved Easy snare spacing, against step 2 [here, review].
   - Crashes count as right-hand hits along with toms: a toms-only version scored All the Small Things' Medium 0.911,
     against 0.932. The hi-hat and ride rule holds inside lanes too [here, review].
4. **Kit:**
   - collapse double cymbals to one; crashes go on green on Hard and below;
   - collapse two toms to one on Medium and below;
   - no kicks inside fills below Expert.
5. **Kicks:** padding 1/2 beat on Hard (8th-note kicks, as all four Harmonix test Hards have; Q18, decided), 2 beats otherwise. On the four Harmonix references drums Hard F1 goes 0.918 → 0.944. On the test song Hard gains 6 kicks, and the ladder then also takes the measure's last 8th (96 hi-hats and 11 rides): drums Hard 0.893 → 0.81 of Expert, the Harmonix range [here, Q18/Q19 run]. On Medium a kick stays only with zero or one hand gem.
6. **Hard:** no 3-limb hits, no 2x kick.
7. **Easy:**
   - never a kick paired with a pad;
   - each section is kick/snare (quiet sections) or hands-only (loud sections, judged by the song's median RMS);
   - Easy must contain cymbals.
8. **Star power coverage and `S 64` lanes per difficulty** (§2.10).
9. **Targets:** `reduce.py`'s ladder aims at Hard 0.85, Medium 0.61, Easy 0.50 of Expert hits (ceilings 0.87 / 0.70 / 0.55) and warns outside Hard 0.62–0.98, Medium 0.39–0.85, Easy 0.30–0.71 (Harmonix p10–p90) [code]. Harmonix: Expert kicks kept 58 / 33 / 12 %; note groups 0.81 / 0.61 / 0.50 of Expert [here]. Human drum ladders: Hard 0.853, Medium 0.648, Easy 0.534 [here, drums/bass audit].

- **Evidence:**
  - autochart's separate tier generations score F1 0.86 / 0.81 / 0.79 on the 4 Harmonix songs, which may be in its training data [here, 5070];
  - STRUM's two stacked reduction passes leave Easy at 0.003–0.077 of Expert [here].
- **Confidence:** medium. Nesting and validity are certain; how human the result feels is unmeasured.
- **Would change it:** our tiers' F1 more than 0.05 below autochart's on the 4 Harmonix songs over several takes (then try model-generated tiers filtered for nesting); the owner asking for a denser option (§9 Q8).

### 2.12 Difficulty rating (`diff_*`, 0–6)
- **Guitar** (10-fold CV MAE 0.77, 86 % within ±1 on Harmonix [here]):
  `−2.49 + 0.278·avgNPS + 0.105·maxNPS1s + 0.268·maxNPS10s + 2.04·move + 2.01·hopo + 0.73·chord`
- **Bass:** `−0.79 + 0.343·avgNPS + 0.306·maxNPS1s`
- **Drums:** `−0.63 + 0.325·avgNPS + 0.178·maxNPS1s` (81–83 % within ±1 [here]). The value goes to both `diff_drums` and `diff_drums_real`.
- **Rules:**
  - Round and clip to 0–6. Write values only for charted parts (`ini.py` does this [code]).
  - `diff_band` is the rounded mean of the charted parts (our own heuristic). `ini.py` has no band key today [code]: add a band rating to `write_ini` and pass it through `build_song_folder` (§5.6). Until then `diff_band` is not written.
  - Goal 1: check by hand; expect about 3 for guitar. Goal 2: show the values as editable suggestions.
- **Confidence:** low-medium (r = 0.45 on customs). **Would change it:** systematic bias against Encore references.

### 2.13 Output and validation
- **Writers:** the existing `chart.write_chart`, `ini.write_ini` and `package.build_song_folder` [code].
  - Resolution 192; ` = ` with single spaces; sections in the order [Song], [SyncTrack], [Events], then the tracks; ticks ascending.
  - `Offset = 0`, `MusicStream = "song.ogg"`, quoted global events, no `end` event.
- **Audio:** the Clone Hero folder holds only `song.ogg`, the full mix. Separated stems are never shipped there, because Clone Hero would play the parts twice.
- **Gate,** in this order, on the final folder including `song.ogg` (scan-chart reports `playable=false` when there is no audio [here]):
  1. `verify_sync` < 1 sample.
  2. scan-chart 8.0.1 (`node tools/scan-chart/scan.cjs <folder> --notes`): playable, and 0 chart issues except `noAlbumArt`.
  3. Self-check: scan-chart's parsed notes match what we wrote (count, ms ±1, HOPO/tap/cymbal flags).
  4. Encore rules: sustains ≥ 200 ms; sustain gaps ≥ 60 ms (target 85 ms); first note ≥ 2 s (`min_lead = 2.5 s` covers this and scan-chart's leading-silence check).
- **Checked per track and difficulty:** `emptyStarPower`, `emptySoloSection`, and `noDrumActivationLanes` on every drum difficulty.
- **As built** (`assemble.verify_folder`) [code]:
  - scan-chart 8.0.1 runs whenever node and `tools/scan-chart`'s `node_modules` are found. Every chart issue it
    reports is an error, `isDefaultBPM` included. Where it reports the same (track, kind) as our own checks, ours is
    dropped; our stricter Encore issues stay. The self-check runs on scan-chart's parse and on our read-back.
  - Without node or `node_modules`, the gate warns `scanChartNotRun` and the Python re-implementation of scan-chart's
    rules (`scan_rules`) decides. `verify_folder(scan_chart=True)` makes that an error, but the CLI has no flag for
    it. §4.3 ships a pinned Node 22, so the friend's install runs the real scan-chart.
  - The build is written into a staging folder and gated there. A passing build replaces the output folder. A failing
    one goes to `<output>.failed`, and `<output>` keeps the last good build; Clone Hero can still list a `.failed`
    folder inside its Songs folder. A build that raises writes nothing.
  - An output folder that holds anything the tool does not write is refused (exit 2) rather than cleaned, so an
    `--out` that points at Clone Hero's Songs folder is safe. Dotfiles, `Thumbs.db` and `desktop.ini` are tolerated.
  - song.ini needs album, genre and year (charter defaults to "songcharter"); the config's numbers must be JSON
    numbers.
  - **The end of the audio.** `noteAfterAudio` is our own rule, not scan-chart's. scan-chart 8.0.1 measures no audio:
    its `scanAudio` (`node_modules/scan-chart/src/audio/audio-scanner.ts:8-29`) returns `audioLength: null` (lines
    14 and 28) with the fingerprint code commented out (17–26), and `noteAfterAudio` appears nowhere in its `src` or
    `dist` [code, read in `tools/scan-chart`]. The rule is `scan_rules`'s (`songcharter/assemble.py:736-739`): it fails
    a track whose last onset or sustain end, read back from notes.chart, lies after song.ogg's length, the decode's
    samples plus the lead-in pad over 44.1 kHz (song.ogg's intended length; its decode-back length differed by 0
    samples in every report checked). It runs whether or not scan-chart does.
  - **The clip** (`clip_to_audio`, `songcharter/assemble.py:609`, called on every part at line 1347 after quantizing
    and trimming): with a margin of 1 ms (`CLIP_MARGIN_S` = `SELF_CHECK_S`: the self-check already fails a read-back
    time more than 1 ms from ours, so a note ending 1 ms early by our map cannot trip the rule), a note starting in
    the last 1 ms or later is dropped, a sustain running later ends on the last tick before that point, and one left
    under its level's shortest sustain (the quantizer's `sustain_kept`) becomes a plain note. Every taken level is
    clipped; the lower levels are reduced from the clipped Expert, and phrases are placed after the clip (star-power,
    solo and fill spans are not clipped: neither scan-chart nor our rule checks them). The counts per part and level
    are in report.json (`parts.<name>.clipped`) and the CLI summary's part line.
  - **Before and after** [here, pipeline-defaults runs]: the 35-s excerpt that failed M3's smoke run, rebuilt by
    `songcharter assemble` from its config with real scan-chart, exited 1 with four `noteAfterAudio` errors (guitar on
    every level: "a note at 42.146 s, after song.ogg ends (37.775 s)", autochart's sustain 4.4 s past the end) while
    scan-chart found it playable with 0 chart issues; after the clip it exits 0, 1 Expert guitar sustain clipped,
    every guitar level ending 1.34 ms before song.ogg. A new 35-s cut of Take Me Out (197–232 s) inside a long
    sustain: 1 Expert sustain clipped, the guitar ending 1.78 ms before song.ogg, gate OK. Three takes-experiment
    builds of Creep had failed the same way (seed 303's last chord) [here, takes experiment].
- **Sustain floor:** max(200 ms, 0.75 beat) on Expert and Hard (§2.7).
- **song.ini for Goal 1:** name "Beast Monster Thing (Love Isn't Love Enough)", artist "Car Seat Headrest" (§6). `README.md` still names the artist as "Beast Monster Thing" and must be fixed [code].
- **Evidence:** 27–31 % of autochart's test-song sustains end less than 40 ms before the next note [here]. How Clone Hero itself treats `badSustainGap` is unverified.
  The v1 chart of the test song passes the gate, and scan-chart 8.0.1 finds it playable with 0 chart issues (§5, M1a).
- **Confidence:** high. **Would change it:** a playtest in Clone Hero or YARG showing that the gate rejects something harmless or misses a real problem.

### 2.14 Contradictions and conflicts resolved

**Kept from v1:**

| topic | resolution |
|---|---|
| test-song first beat | ≈ 0.047–0.050 s (onset fit 0.0468 s at 142.0009 BPM). The 0.075 s figure came from the 1105-sample-late 6s stems. Nothing is hard-coded. |
| test-song tempo | 142.00 BPM. Songsterr's 72 is half-time notation; librosa's 143.6 is a coarse estimate. |
| Encore reachability | reachable |
| leading silence | `min_lead = 2.5 s` satisfies scan-chart (1000 ms in code, 2000 ms in its message) and Encore (2000 ms) |
| orange on Medium, blue on Easy | follow scan-chart, i.e. Clone Hero |
| Beat This phase bias | −35 to −40 ms came from crude decoding; the timing pipeline gives −10 to +3 ms |
| reference timing | calibrate each reference's offset before scoring (Kimochi Warui is about 22–25 ms late) |
| song version | our file is the streaming master (container 412.395 s; Spotify 412,394 ms; gapless decode 412.363 s), not the 2014 Bandcamp version |

**Resolved in this version** (the basis of each resolution is tagged):

| # | topic | positions | resolution |
|---|---|---|---|
| C1 | guitar engine route | v1: own driver, 3 takes, gates. Comparison: autochart's engine behind a process boundary (B), or build on autochart (D); for Goal 1, the autochart app plus Moonscraper (A′). | Goal 1 imports autochart's output (no code) and re-times it [decision; §1 gives the reasons for reversing A′]. Goal 2 builds the driver behind `TimedSong` and benchmarks it against autochart's engine over ≥ 3 seeds (comparison §7.2b). B1 vs B2 vs D is the owner's call (comparison §7.1; §9 Q3). |
| C2 | Fretformer run time | v1: "a few minutes on a 4070", 1–3 min of decoding. Critique: 2–3.5 min per take on CPU; 3 takes 5–10 min. | The critique is confirmed by the 5070 log (3531 tokens in 189.3 s; 228.8 s for the job; GPU barely helps) [here, 5070]. Default to 1 take; restated targets per route (§1, M4). |
| C3 | drum engine | v1: ADTOF fusion (lane F 0.844 on excerpts). Comparison: STRUM. ADTOF test: ADTOF better on pad-blind onsets (0.967 vs 0.897) and kicks (0.986 vs 0.938, 5-song means), STRUM better on lanes (0.687 vs 0.585). | Goal 1: STRUM lanes, re-timed (ADTOF test conclusion). Goal 2: ADTOF plus a new lane mapper that must meet the drum-lane rule of §3.2 [decision: the ADTOF test calls ADTOF a candidate]. The onset and kick advantage compares unquantized ADTOF with late, snapped STRUM; re-score both after the quantizer [inference]. STRUM is never shipped in Goal 2 (practicality audit). |
| C4 | "adding ADTOF kicks hurt" | STRUM plus ADTOF kicks lowered Take Me Out kick F1 from 0.982 to 0.892, yet ADTOF's own kick F1 is 0.986 (5-song mean; 0.981 on Take Me Out). | The fused Take Me Out chart has 65 kick pairs 30–40 ms apart; All the Small Things has 26 pairs within 40 ms; Kimochi Warui, a constant-tempo song, has 0 [here, counted from the ADTOF test's fused charts]. The fusion matched kicks with a 30 ms tolerance (`fuse.py`) against STRUM's grid-snapped times on drifting songs, so the drop is plausibly duplicates, not wrong ADTOF kicks [inference]. Re-test with de-duplication per grid slot before deciding. |
| C5 | bass | v1: rules (onset F 0.863). Comparison: STRUM as a baseline only. Critique: 0.863 is oracle-grid, same songs. | Goal 1: STRUM onsets + pYIN re-lane (comparison §7.4). Goal 2: our rules; STRUM is scored as a benchmark only and never shipped (practicality audit). |
| C6 | tempo source | v1: Beat This + post-processing. `beatgrid`: drum-onset refinement with Beat This as an optional `start=`. | Both: Beat This proposes, drum onsets refine (Goal 2) (comparison §7.2). Goal 1 needs only `beatgrid`. |
| C7 | click vs free | v1: click if p95 drift ≤ 30 ms. `beatgrid`: free at ≥ 60 % evidence. Critique: p95 hides rubato. | Free at ≥ 60 % evidence; otherwise click after the max and longest-run checks (critique G4; `beatgrid`). On Goal 2's `start=` path these tests need code (§2.3). The rigid line's p95 against the drum beats (47.9 ms) is above the human maps' (31.9–33.4 ms) [here, guitar audit]. |
| C8 | phase offset | v1: no constant offset. Comparison: 14–18 ms. `beatgrid`: −22 ms. ADTOF: −1.5 to −6.8 ms against humans. | The offset belongs to the detector, and the numbers agree (guitar audit; `beatgrid` docstring). Keep −22 ms with `beatgrid`'s envelope, for drum stems only. Cross-check: median(beat − nearest ADTOF kick or snare) within +1.5 to +6.8 ms ± 5 ms (§5.6, task 2). Tonight `beatgrid` sat −3.0 to +3.0 ms from the human beats on three references, two of them in-sample [here, beatgrid run]. |
| C9 | Demucs weight licence | Demucs README: "not clear", "likely" CC BY-NC. autochart's notices: MIT. | The most restrictive reading: non-commercial (comparison §7.3). |
| C10 | HOPO and forced flags | v1: natural HOPOs only. Critique: keep the model's flags. `timed.py` carries the source's intent. | Keep the intent (critique G1), except where the source's tempo level was wrong (§2.6) [inference; 11 of autochart's 28 Expert flips fall in its half-tempo stretches, here, quantizer check]. Not in `quantize.py` yet. |
| C11 | Hard reduction | Critique: Hard ≥ 0.9 of Expert is an M1 failure. Guitar audit: a human Hard can equal Expert. An earlier draft: fail only on 8th-dominated parts at ≥ 0.95 (no traceable source). | Thin by subdivision (critique E3; `reduce.py`'s ladder). Error at Hard ≥ 0.90 of Expert onsets on every 5-fret part (critique E3; `reduce.py`); warn outside 0.63–0.90; tune in M2. The check is on our reducer's output; the human 680 / 680 Hard shows that a human-like chart could still trip it. |
| C12 | sustain floor | v1: 0.5 beat. Critique: 0.75 beat. | max(200 ms, 0.75 beat) on Expert and Hard (critique E9). |
| C13 | quality claims | v1: drums "good" at 0.844; Engine A κ 0.465. Critique: 0.813 held-out; Engine A unmeasured. | The critique's view. Keep the metrics apart: v1's pro-lane F (0.844 on excerpts, 0.813 held-out) is not `score.py`'s exact lane agreement (the whole pad set must match; cymbal flags ignored), on which ADTOF with `drummap2` gets 0.585 and STRUM 0.687 on whole songs [here, ADTOF test]. Engine A stays unmeasured until M2. |
| C14 | stem-lag gate, pYIN time, determinism, FLAC cache, ffmpeg PATH | v1 vs critique | The critique's position on all five (E6, E10, G6, E12). The ADTOF test's lag-0 stems pass the new gate. Determinism also needs Demucs's random shift seeded (§2). |
| C15 | lower tiers | Comparison: autochart's tiers are the most human-like measured. v1: our reducer. | Ours (nested by construction; `reduce.py`); compare in M2 (comparison §7.2). |
| C16 | milestone order | v1: CLI → harness → UI → Windows → quality. Comparison: Windows spike → evidence → pipeline → … | §5: Goal 1 for the friend's instrument(s) plus the Windows spike first, then evidence, then the pipeline (comparison §7.4–7.5). |
| C17 | artist and title | README vs v1 | Car Seat Headrest, "Beast Monster Thing (Love Isn't Love Enough)"; fix the README (comparison §8). |

---

## 3. Evaluation plan

### 3.1 Metrics
The scorecard puts gates first, then a profile per instrument. There is no composite score.
- **Gates:** alignment valid; scan-chart playable with 0 note-level issues; |grid phase| ≤ 10 ms; difficulty rules respected.
- **Tempo:**
  - headline: reference notes on the candidate grid within 10 ms (1/4 and 1/3 subdivisions, chance level per song);
  - also beat F1@70, downbeat F, CMLt/AMLt, and runs at half or double tempo.
  - Beat F1 alone is too lenient: a constant tempo replacing a drifting map keeps onset F 1.0 and gets beat F 0.444, while notes-on-grid falls to 0.424 [here].
  - On the test song (no human map): beat lines against local drum beats, as median signed and p95 about the median, so spread and offset are reported apart.
- **Onsets:**
  - F1@50 and F1@100, F@25, global offset, F after offset removal, alias ratio, always shown next to the floors (onsets on the mix; an 8th-note grid on the human map).
  - F1 is blind to lanes and to offsets under 50 ms: shifting every note +30 ms keeps F1@50 at 1.000, random lanes keep F1 at 1.000, and a metronome on every 8th scores 0.718 [here].
- **Drums:** onset F1 is pad-blind; per-pad F1 with disco flips resolved; exact lane agreement (`score.py`: the full pad set of a matched onset must be identical; cymbal flags ignored); macro F.
- **Frets:**
  - lane-direction κ and local Spearman over 8-onset windows;
  - repeat-vs-change F, chord κ, chord-size MAE, lane-histogram EMD;
  - HOPO κ, sustain F, sustain-end error.
- **Density:** ratio; 4 s window correlation; p95 notes-per-second ratio.
- **Difficulty sanity:** monotone counts; nesting (±5 ms); lane and chord rules; the ratio checks of §2.11.
- **Separation** (development only, on songs with real stems): SDR, drum bleed, quiet-passage leakage. Not onset F against chart notes, which rewards drum bleed (the true guitar stem scores 0.55 and the raw mix 0.74 [here]).
- **Test song (no human chart):** reference-free proxies only:
  - timing offsets, precision and slot-AUC against stem onsets, coverage of active windows, beat lines against local drum beats, bar phase, ladders, chart issues;
  - not onset F1 against the audio: a blind 8th-note grid scores at least as high as the human chart on the mix in 5 of 6 references [here, guitar audit];
  - two detector conventions are in use (the guitar audit's rising-edge picker; the drums/bass audit's band-flux proxy), and their offset to each other on the test song is unmeasured (M1a);
  - the M1 check script re-runs these (§5.6, task 3).
- **Cost:** CPU and GPU seconds per audio minute; peak RAM and VRAM.

### 3.2 How results gate decisions
- **One set of per-song rules,** used by §2.7, §2.9, C3 and M3. Tolerances are at least the observed run-to-run spread [here, 5070 vs CPU]: autochart Expert 0.035; one autochart Medium moved 0.151; STRUM drums 0.087.

  | what | rule |
  |---|---|
  | guitar (sampled engines) | over ≥ 3 seeds per song: on every song F1@50 ≥ the best tool on that song − max(0.035, the measured seed spread); mean F1@50 ≥ the best tool's mean − 0.035; mean lane direction ≥ its mean − 0.05 |
  | drum onsets | on every song F1@50 ≥ ADTOF's on that song − 0.02 (a deterministic baseline) |
  | drum lanes | mean exact lane agreement ≥ STRUM's mean − 0.02, and on every song ≥ STRUM's on that song − 0.05 (STRUM's per-song CPU values run 0.514–0.697, its GPU mean is 0.687 [here, ADTOF test]) |
  | beat grid | beat F1 ≥ autochart's per song − 0.02, Lucretia separate, and no half- or double-tempo runs |
  | any other change (M5) | a paired per-song difference with a 10k bootstrap CI (songs resampled) and a Wilcoxon test; adopt only with a CI excluding 0 and no per-song regression larger than max(0.05, the run-to-run spread) |

- **Absolute F1 targets are information only** until the set is large enough. A 0.05 difference between tool pairs needs 36, 51 or 151 songs (paired SDs 0.106, 0.127, 0.219) [here, comparison]. v1's paired SDs between detector variants (0.043–0.082) need 37–132 songs to resolve 0.02 [here].
- **Sampled engines** are judged over ≥ 3 seeds per song.
- **Lucretia** is reported separately from every mean.

v1's absolute targets, kept as information only:

| metric | v1 target |
|---|---|
| note-level scan-chart issues | 0 on every reference (this one stays a gate) |
| reference notes on the candidate grid at 10 ms | ≥ 0.9 on click songs |
| guitar F1@50 | above the 8th-grid floor on every song; mean ≥ 0.85 (Harmonix-inflated; autochart's Car Seat Headrest mean is 0.795) |
| guitar direction κ | ≥ 0.4 |
| bass F1@50 | ≥ 0.85 |
| drums pro-lane F ≥ 0.80 | dropped: v1's metric, which `score.py` does not compute; the drum-lane rule above uses exact lane agreement |

### 3.3 Reference set (Chorus Encore)
- **Today:** six references in `eval/refs.json`:
  - Kimochi Warui (InsaneOwO; guitar, bass, drums; Expert only);
  - Drunk Drivers / Killer Whales (IaSg14; guitar only, 248 markers);
  - Take Me Out, All the Small Things, Lucretia and Creep (Harmonix; all four difficulties).

  Guitar is scored on 6 songs, bass and drums on 5, lower difficulties on the 4 Harmonix songs. The research job also downloaded Shadowplay, Ya (No) Se Que Hacer and Fondue los Muertos; they are not in the harness yet.
- **Target:** ≥ 20 songs in M2, with a plan to reach about 50.
  - Split: development, a frozen test set (fixed by SHA-256, used only at milestones, every use logged), and a stress set (§5, M5).
  - The test song has no ground truth. It is judged by gates, proxies, a playtest and optionally the Songsterr tab (§9).
- **Contamination** (critique G12):
  - Grow the set with community charts from after Fretformer 2's release (September 2026) and outside ADTOF's custom-chart training data. Encore exposes `modifiedTime`, not a first-upload date, so the cutoff is: `modifiedTime` ≥ 2026-10-01 and no earlier chart in the same `versionGroupId` (an approximation of "first uploaded after 2026-10"), with a cap on songs per charter.
  - Count so far: the cached pool (3,651 rows from a `modifiedAfter=2026-07-01`, `hasIssues=false` query) has 873 charts with `modifiedTime` ≥ 2026-10. Of these, 68 have guitar, bass and drums on all four difficulties, are 150–330 s long and have no chart, metadata or folder issues; they come from 9 charters, and 7 are `drumsReviewed` [here, counted for the review of this document; the pool may be incomplete]. So ≥ 20 songs is reachable, but charter diversity is thin. Report the eligible count before fixing the M2 target.
  - Harmonix charts are development-only: STRUM's guitar training split contains the exact Harmonix charts of 4 references (note counts 896, 680, 1377, 881), and Lucretia is in the Harmonix Set that Beat This trains on. It is also in allin1's training data (0165_lucretia: fold 7 by allin1's fold rule, so in fold 0's training split and in 6 of the ensemble's 8) [here, sections engine run]. Report Lucretia's section scores separately. Kimochi Warui's reference chart has no sections.
  - Keep any slot-classifier training data disjoint from the development and test sets.
  - Set targets separately for the community split.
- **Selection** (v1): full-band charts with all 4 difficulties and no chart, metadata or folder issues; 150–330 s long; ≥ 25 % indie or lo-fi rock; about one third each free tempo, click and mixed; prefer `drumsReviewed:true`; one chart per song.
- **Screens:**
  - Calibrate each reference's offset; correct or exclude any more than about 10 ms from the panel median.
  - **Copies:** onset agreement cannot reveal copying, because accurate independent charts agree on onsets. Screen by lane, chord and HOPO κ (for example, all ≥ 0.9 means a copy) (critique E8).
  - The Neversoft/Beenox Guitar Hero charts serve as a tentative independent human ceiling: guitar onset F 0.95–0.997, direction κ 0.77–0.86 (medium confidence; the Encore uploads could be conversions) [here].
- **Etiquette:**
  - At most 1 request per second, with a cache and a User-Agent; probe .sng headers with Range requests.
  - Commit only a manifest (ids and hashes); keep data in git-ignored `eval/data/` or outside the repo.
  - Never commit audio, charts or derived note data, and strip vocals and lyrics when references are built (`eval/refs/strip_lyrics.py`).
  - Credit charters by name. Ask the Encore team before scaling up (§9).

### 3.4 Harness
- **Exists** [code]:
  - `eval/scorer/score.py` (scan-chart parse through `eval/scorer/scan_notes.cjs`; onset P/R/F1 at ±50 and ±100 ms, density, chord/HOPO/tap/sustain shares, lane direction, exact lane agreement, drum per-pad F1, beat F1, scan-chart issues);
  - `eval/scorecard.py`; `eval/drive.sh`; `eval/gpu.sh` (check, start, status, results); `eval/build_refs.sh`; per-tool `setup.sh` and `run.sh` under `eval/tools/`;
  - `eval/golden.py`, the golden charts: songcharter's own charts of the reference set before and after a change (§3.6);
  - `eval/refs/` (`build_ref.py`, `offset_check.py`, `sng_unpack.py`, `strip_lyrics.py`).
- **Fixes the harness still needs** (found with data in v1 or in this review; none is in the files yet [code]):
  - un-flip Harmonix disco sections in both charts (19 % of Take Me Out's drums are disco-flagged; without the fix a correct chart scores class F 0.604);
  - drift-aware alignment (offset plus clock ratio), with weak alignments marked invalid;
  - F@25, global offset and grid phase;
  - scan-chart issues split into gate, note-level and feature gaps;
  - a missing part counts as 0;
  - hashes of the scorer, references and inputs in every result;
  - `build_refs.sh` writes the test song as `pcm_s16le` with ffmpeg from PATH, which clips its 470 samples above full scale: write float32 with a pinned ffmpeg (§2.1).
- **Planned commands** (v1):
  ```
  songcharter-eval fetch    --manifest eval/refs.json          # download, verify sha256, build refs, offset check
  songcharter-eval run      --set dev --name <git-sha> [--device cuda|cpu] [--seeds 3]
  songcharter-eval score    --name <git-sha>                   # fixed score.py + extra metrics; all hashes recorded
  songcharter-eval card     --name <git-sha> --baseline <prev> # gates → profile → paired diffs + bootstrap CI
  songcharter-eval selftest                                    # corruption suite; fails if a metric stops responding
  songcharter-eval test     --name <git-sha> --frozen          # frozen test set; appends to TESTLOG.md
  ```
- **Prototypes to port** (v1's evaluation scripts, not in the repo): `run_suite.py`, `metrics_plus.py`, `baselines.py`, `scorecard.py`, `hh_align.py`, `encore.py`. Also the ADTOF test's `run_adtof_refs.py` and `fuse.py`, the importer check's `validate.py` (as a repo test), and the audits' reference-free checks (§5.6, task 3).
- **Degraded inputs** (critique G10): add 128 kbps AAC, 16 kHz low-pass and −14 LUFS limiter versions of the development references, and report each metric's drop (M5).
- **Where it runs:** Linux or WSL2. Scoring is CPU-only, about 10 CPU-s per song [here].

### 3.5 Baseline numbers found

| what | number | source |
|---|---|---|
| floor: librosa onsets on the mix, F1@50 | guitar 0.567 (9 songs); bass 0.499; drums 0.650 | [here, v1] |
| floor: a note on every 8th of the human map | guitar 0.718, bass 0.688, drums 0.813; on the two Car Seat Headrest refs 0.86 / 0.77 | [here, v1; comparison] |
| autochart guitar, Expert | F1@50 0.86 (6/6 wins); lane direction 0.70 vs trivial 0.45; mean direction κ 0.465 (0.37 / 0.39 on Car Seat Headrest) | [here, 5070] |
| chartgen guitar | 0.57 (ceiling 0.711; about 0.64 after offset removal [est.]) | [here, 5070] |
| STRUM guitar / bass / drums | 0.59 / 0.59 / 0.90 (drums pad-blind, snapped and late) | [here, 5070] |
| ADTOF drums, whole songs | F1@50 0.967 (pad-blind, unquantized); kick 0.986 (5-song mean); exact lane agreement 0.585 (STRUM 0.687); after our quantizer 0.962 (STRUM CPU, 3 songs: 0.956) | [here, ADTOF test; here, drums engine run] |
| ADTOF fusion, v1 excerpts | pro-lane F 0.844; 0.813 on held-out excerpts of the same songs (v1's metric, not `score.py`'s) | [here, v1; critique E4] |
| beat F1, tools | autochart 0.87, chartgen 0.77, STRUM 0.46 (Lucretia 0.26–0.29 for all) | [here, 5070] |
| `beatgrid`, whole songs | test song: median −16.6 ms, p95 \|dev\| 50.7 ms, p95 about the median 44.6 ms (free); four references: 1.00 / 0.84 / 1.00 / 0.26 of beats within 70 ms of a human beat (Take Me Out 0.986 with the local periods of §2.3); downbeat match 0.00 / 0.03 / 0.99 / 0.66 | [here, beatgrid run; here, review] |
| v1 tempo prototype | test song 5.9 / 8.3 ms median / p95, a residual of matched onsets in v1's convention (not comparable with the row above); IaSg14 F 0.999 at 11.0 ms; Kimochi Warui's exact BPM | [here, v1] |
| bass rules | onset F 0.863 (oracle grid, same songs); pYIN contour 0.97–1.00 on 3 of 4 excerpts | [here, v1] |
| bass rule engine, whole songs | after our quantizer F1@50 0.800, lane direction 0.781 vs trivial 0.542, κ 0.612 (5 songs); raw 0.722, κ 0.561; STRUM through the same quantizer 0.755 vs ours 0.800, κ 0.29 vs 0.69 (3 songs) | [here, bass engine run] |
| guitar slot rules | 8ths-while-active 0.816; LR 0.893 (oracle grid, excerpts) | [here, v1] |
| human ceiling | community copies 0.943–0.997 (not independent); Neversoft charts, tentative: onset F 0.95–0.997, direction κ 0.77–0.86 | [here, v1; critique E8] |
| sections | 5 references, boundary F at ±1 s / ±3 s after assemble's rules: allin1 fold 0 0.626 / 0.718, ensemble 0.592 / 0.714, librosa fallback 0.455 / 0.524 (labels 0.615 / 0.589 / 0.475); v1, one song: librosa F@3 s 0.80 / 0.70 against IaSg14; All-In-One ensemble 0.730 on Harmonix (in-domain) | [here, M2 row 7] / [here, v1] / [doc] |
| literature | STRUM paper: drums F1 0.838, guitar 0.651, bass 0.694 at ±100 ms | [doc, arXiv 2605.12135] |
| `songcharter chart`, Take Me Out (1 song, 1 CPU guitar take) | Expert F1@50 guitar 0.909, bass 0.912, drums 0.944 (kick 0.976, exact lanes 0.285); beat F1 0.962; scan-chart 0 issues | [here, pipeline run] |

### 3.6 Golden charts (`eval/golden.py`)
- **Why.** A change can move charts it was not meant to touch, and neither the unit tests nor a reviewer reading the
  diff sees that. The Overclock project caught such regressions with golden frames: fixed outputs rendered before and
  after a change, any change outside the expected ranges flagged. Here the outputs are the reference set's charts. A
  build is byte-identical for one input and the engines cache their outputs, so after a song's first build each one
  costs mostly assemble [code].
- **What is compared** [code]:
  - the seven songs of §3.3 (the six references and the test song), each built by `songcharter chart` with every
    level, one guitar take, no preview, on the CPU;
  - per song, part and difficulty: the onsets (a chord is one), the notes, and scan-chart's `calculateTrackHash`,
    Chorus Encore's hash of a track (resolution, tempo map, time signatures, star power, solos, flex lanes, drum fills,
    every note's tick, length, type and flags), taken on the parse `scan_notes.cjs` makes with song.ini's modifiers,
    so as Clone Hero reads the folder. The chart's delay (song.ini `delay`, the `.chart` Offset), which the hash
    leaves out, is compared beside it;
  - for the six human-charted songs, `score.py`'s F1@50 and F1@100 per part and difficulty, and the beat F1.
- **`diff OLD NEW --expect PARTS`.** A part and difficulty whose hash changed (or that appeared or vanished) is
  "changed" when `--expect` names it and UNEXPECTED when not; a song missing from either summary, whose build failed
  or whose gate changed is UNEXPECTED whatever is expected. F1 is pooled per part and difficulty as
  2 × matched ÷ (reference + candidate onsets) over the songs. Exit 0, or 1 when anything is UNEXPECTED.
- **Kept folders and the build's own folder** [decision]. The heavy stages run once per song into a kept
  `songcharter chart --work` folder outside the repository, its stems hard-linked from a separation cache where the
  key fits, autochart's scratch folder deleted once the take is built. Every build then runs in a folder of its own:
  the decode and the stems hard-linked (only read), every engine's folder copied, because an engine whose cache
  misses writes its files in place (`engine.json` by `write_text`, the stems by soundfile), which through a hard link
  would reach the kept file. Every kept file's size, time and inode are checked after each build, a lock per song
  orders the runs while a kept folder is made or read, and the build's per-user cache is an empty folder, so its
  pruning touches nothing.
- **Not keyed by code.** The engines' caches are keyed by their inputs and settings, not their code, so an engine's
  code change shows only with `--rerun` (drums, bass, sections, guitar) on both runs, which runs it again in each
  build's own folder and leaves the kept one. Rerun in one run only, it compares the kept commit's output with that
  run's own, and `diff` fails, naming the engine and the kept commit. For every engine not rerun, `run` asks git
  whether its files (`ENGINE_FILES`) differ between the kept folders' commit and its code, warns, and `diff` fails. An
  engine that runs without being asked (its kept output did not answer: new settings or version, another autochart
  install, the librosa fallback when `SONGCHARTER_ALLIN1_PYTHON` is unset) stops the run with exit 2 and says which
  variable or option. The separation is never run again: a change to its code does not show.
- **No stale summary.** `run` locks its output folder and clears what an earlier run or diff left there before any
  check, so a run that is refused, fails or is killed leaves no summary for a diff to pass on; the gate's commands are
  chained with `&&` from a `rm -rf` of both output folders. Bad input exits 2, a bug 3 (never 1, which is a failed
  build or an UNEXPECTED diff).
- **Runs** [here, golden runs]:
  - **The baseline**, `main` at 11615e2 on the seven songs: every gate OK; Expert F1@50 pooled over the songs guitar
    0.853 (6 songs), bass 0.825 (5), drums 0.962 (5), beat F1 0.876 (6); Take Me Out's guitar 0.909, bass 0.912,
    drums 0.944, as in §3.5.
  - **Cold** (a kept folder made, the stems hard-linked from the seeded separation cache, so no separation ran): 474 s
    (Drunk Drivers, 3:45) to 1081 s (the test song, 6:52) a song, 80 min for the set; autochart's take is 253–650 s of
    it, allin1 105–188 s. **Warm:** 44–76 s a song: assemble with its gate 19–42 s, the cache checks 13–30 s (the
    sections engine's allin1 probe 6–10 s of it), score.py 6–8 s; 6.5 min for the set.
  - **Determinism:** two warm runs of `main` gave identical summaries but for their `run` sections, and so did the cold
    baseline; `diff --expect none` exits 0 on each pair.
  - **A deliberate change** on a scratch branch, one line in `_reduce_frets`'s HOPO step: every bass Hard note a HOPO
    (Take Me Out's bass Hard went from 0 to 540 HOPOs of 540). `--expect bass:hard` exits 0 with bass Hard changed on
    all seven songs and the other 77 part-levels unchanged; `--expect guitar` exits 1 with those seven UNEXPECTED. The
    pooled F1 did not move: onset F1 does not see HOPOs.
  - **Two checkouts at once:** `main` (built through `--code`) and the change (built by its own checkout's
    `golden.py`) ran at the same time, 399 s each, and each matched its own run made alone; the kept folders' 217
    files had the same size, time, inode, link count and SHA-256 before and after, and no run folder was left.
  - **`--rerun` with the real engines:** drums, bass and sections run again on the seven songs reproduced the
    baseline exactly (24 min for the set); so did the guitar on All the Small Things (its take 211 s, autochart's own
    separation included). The kept folders were unchanged both times.
  - **Disk:** 0.71 GB in all, nearly all of it the kept decodes (59–139 MB a song); the stems are links to the
    separation cache.
- **Limits:** Linux or WSL only (`fcntl` locks, hard links). One CPU take: the CUDA default of 4 spliced takes is not
  covered. The kept engine outputs are the code of whichever commit made them; a change to an engine's code without
  `--rerun` compares that old output on both sides, which `report.md` shows as "kept folders made by".
- **Confidence:** high for what it compares. **Would change it:** a change the hashes miss that a playtest finds
  (song.ini values, the audio, section names are not compared).

---

## 4. Packaging and UI

### 4.1 Goal 1 delivery
- A song folder (`notes.chart`, `song.ini`, `song.ogg`) and a zip of it (`package.zip_folder`), copied into Clone Hero's Songs folder, then "Settings > General > Scan Songs". No installer.
- `song.ogg` is made from a copyrighted recording, so sending it is distribution. Prefer that the friend uses their own copy, and generate on, or verify sync against, the exact file they will play (comparison).

### 4.2 Weights and licences (not legal advice)

| component | code | weights / data | decision |
|---|---|---|---|
| songcharter | MIT (intended) | — | MIT, with a BY-NC-SA carve-out for the ADTOF port if it counts as adapted material (below); becomes AGPL only if the owner chooses option D |
| htdemucs_6s | MIT | "not clear", "likely" CC BY-NC (the Demucs README, lines 321–325) vs MIT (autochart's third-party notices) [doc] | Treat as non-commercial. Download at first run, pinned and hash-checked; never bundle. |
| Beat This! final0 | MIT | MIT | may be bundled or mirrored |
| Fretformer 2 (+ Lite) | autochart's engine is AGPL. B2 uses no AGPL code; B1 ships the AGPL engine with its source obligations (plus FFmpeg's LGPL); D makes songcharter AGPL. | CC BY-NC-SA 4.0 | Download separately. Keep the written record that our driver follows only `manifest.json` (critique G13). Any mirror stays BY-NC-SA with attribution. If B1 ships, extend the provenance record to `eval/tools/autochart/ac_headless.cjs`. |
| ADTOF Frame_RNN | our 73-line PyTorch port, written from reading `xavriley/ADTOF-pytorch`, which states no licence anywhere (README, pyproject) [doc]; upstream ADTOF's whole repository, code included, is CC BY-NC-SA 4.0 (its LICENSE and README lines 7–8) [doc]. So the port's code licence is uncertain: it derives from reading an unlicensed port of BY-NC-SA code. | the `.pth`: BY-NC-SA by inheritance from ADTOF [doc]; its host states none. Trained on custom charts. | Download the weights separately. Keep the port as a separate module treated as BY-NC-SA, or write a provenance record as for G13. Ask xavriley to add a licence (§9 Q15). |
| STRUM | "MIT" only in its README, pyproject and HF tag; no LICENSE file in its git history | "MIT" tag; 91 % of its guitar training songs come from commercial games | Goal 1 uses only the chart STRUM already produced. Goal 2 uses STRUM only as a benchmark; nothing of STRUM is vendored or shipped (§2.8; §9 Q14). |
| BS-RoFormer SW | MIT (bs_roformer code) | no licence; disputed origin | not in this version |
| allin1 | MIT (code) | tagged MIT on the hub (`taejunkim/allinone`) [doc]; trained on the Harmonix Set | download at first run, pinned (@379e5fd0) and hash-checked; never bundled |
| chartgen's separator | — | "license: unknown" | never |
| Node, scan-chart, node_modules | various | — | write a NOTICE / attribution file (critique G13) |

**Consequences:**
- No fully open route exists. Even a rules-only route (Engine B, or a Basic Pitch route) needs stems, and no separator with an unambiguous permissive weight licence was found.
- If the owner rejects non-commercial weights, Goal 2 has no measured-good engine today for guitar or drums.
- AGPL §13 applies if autochart's engine is ever served to others over a network (practicality audit).

**Weight downloads:**
- Cache: `%LOCALAPPDATA%\songcharter\models\<model>\<file>`. As built, the ADTOF weights live in `models_dir()/adtof/`: `$SONGCHARTER_MODELS`, else `%LOCALAPPDATA%\songcharter\models`, else `~/.cache/songcharter/models` [code]. The htdemucs_6s and allin1 files go through the Hugging Face hub's own cache, pinned to a revision and hash-checked [code].
- `models.json` pins each URL to a commit, with size and SHA-256.
- The downloader uses a `.part` file, HTTP Range resume, retries, a SHA-256 check and an atomic rename, and honours `SONGCHARTER_OFFLINE=1` (resume and offline loading were tested [here, v1]). Built for ADTOF: the `.part` download, retries, the SHA-256 check, the atomic rename and `SONGCHARTER_OFFLINE=1`; Range resume is not built [code].
- A one-time "Model licences" screen lists every licence and attribution.
- The default first-song download is about 0.7 GB plus allin1 [est., v1].

| model | use | host (pin) | size |
|---|---|---|---|
| htdemucs_6s | stems | HF `adefossez/HTDemucs-6s` @3c5ee475 | 54.9 MB |
| Beat This final0 | beats | cloud.cp.jku.at via beat-this 1.1.0; mirror allowed | 81 MB |
| allin1 | sections | HF `taejunkim/allinone` @379e5fd0 | 1.4 MB per fold (fold 0); 11.2 MB for the 8-fold ensemble |
| ADTOF Frame_RNN | drums | `xavriley/ADTOF-pytorch` @85c192e7 (raw.githubusercontent.com), SHA-256 1bc986e5…17320 | 3.6 MB |
| Fretformer 2 (+ Lite) | guitar | HF `Dvaro/autochart-models` @8a88855d | ~0.5 GB |

### 4.3 Windows install (Goal 2, built only after M1's Windows spike)
**Superseded for v0.1:** the owner chose WSL2 (§9 Q4, 2026-11-03), so v0.1's install is
`docs/work-orders/M4-03-install.md`; this native plan is kept for M4-99, as written before that decision. If native:
- **Shape:** one per-user Inno Setup `setup.exe` (no admin rights) wrapping a uv bootstrap, also shipped as a portable zip.
  - Contents: app source, a pinned `uv.exe`, `bootstrap.ps1` (PowerShell 5.1, ASCII only), `songcharter.cmd`, and `tools/scan-chart` with its `node_modules`.
- **First launch** (`bootstrap.ps1`):
  1. Install a uv-managed CPython 3.13.
  2. Run `nvidia-smi --query-gpu=name,driver_version,memory.total,compute_cap`.
  3. Pick a lane:

     | lane | when | torch | download [here, v1; predates the final dependency set] |
     |---|---|---|---|
     | `cu132` | NVIDIA sm_75+ and driver ≥ 580 (RTX 4070 = sm_89) | 2.15.0+cu132 | ~2.1 GB (3.1 GB unpacked) |
     | `cu126` | driver 528–579, or GTX 9xx/10xx | 2.14.1+cu126 | ~2.6 GB |
     | `cpu` | no NVIDIA GPU, or driver < 528 | 2.15.0+cpu | 127 MB (whole lane ≈ 717 MB on disk) |

  4. `uv sync --frozen --extra <lane>` against the committed `uv.lock`.
  5. Fetch a pinned Node 22 for scan-chart (Node must ship; v1 found the gap). Route B1 also needs Node 24 for autochart's engine [here, practicality audit].
  6. Write `doctor.json`, including the Demucs seed/shift choice and peak VRAM per stage once the tool has run.
- **Re-lock and re-measure** with the real dependency set (critique G14). The measured 80-package lock and 717 MB CPU lane predate beat-this, all-in-one-infer (which pulls hydra-core, omegaconf, matplotlib, demucs-infer and madmom-infer), torchaudio, onnxruntime and librosa. Windows resolution, disk size and Defender scan time are therefore unknown.
  - all-in-one-infer 3.1.0, madmom-infer 0.2.0 and demucs-infer 4.4.0 are pure-Python wheels (py3-none-any, no
    compiled files) [here, read from the installed wheels in the sections engine run]. all-in-one-infer 3.1.0 imports
    torchaudio at the top level (`allin1_infer.stems`) but declares it only in its `natten` extra. So the allin1
    environment must list torchaudio itself (`pip install all-in-one-infer torchaudio`; torchaudio has Windows wheels
    on PyPI [doc]); without it the probe fails and `auto` falls back to librosa [here, sections engine run]. When M4
    locks that environment, torchaudio goes in explicitly. The other dependencies (torch, numpy, scipy, librosa,
    soundfile, hydra-core, omegaconf, matplotlib, huggingface_hub, einops, julius, pyyaml, tqdm) all ship for Windows
    [inference]. NATTEN is only an optional extra (Linux, CUDA, torch < 2.8). Not yet installed on Windows
    [untested]. A non-venv Python with `pip install --user` packages (the Microsoft Store Python, or an all-users
    python.org install) also works, because the runner keeps that Python's user site and PYTHONPATH [code].
  - The original allin1 1.1.0 is not a native-Windows route:
    - it imports NATTEN's natten*d{qk,qkrpb,av} ops, which exist only in NATTEN 0.17.4 and older (0.17.5 dropped
      them; there is no 0.18 or 0.19; 0.20 removed that API and CPU support) [here, NATTEN v0.17.4 and v0.17.5
      sources], and NATTEN has to be built from source on Windows (allin1's README);
    - it needs madmom, built from git (a Cython build, so MSVC build tools);
    - v1's pure-PyTorch shim replaces NATTEN, but it is an unreviewed local file.
  - The engines and the pipeline avoid fork-only multiprocessing, temporary stem files and shell commands [code].
- **The cache and the install share a root** [code]. The per-user cache (§2, work folder) is
  `%LOCALAPPDATA%\songcharter` with `work\`, `ac\`, `trash\` and `models\` in it, the root §4.4 installs to. So
  [decision] the install keeps to folders of its own beside them, the uninstaller asks before deleting `work\`,
  `ac\` and `trash\` as it does for the models, and the disk check counts the work folders' 5 GB budget
  (`$SONGCHARTER_CACHE_GB`) on top of the lane and the weights. A profile folder name over 23 characters in
  `C:\Users\<name>\AppData\Local` (Windows can add a suffix such as `.DESKTOP-ABC1234`, 16 characters, to a name),
  or a deeper `$SONGCHARTER_CACHE`, takes the deepest file autochart leaves in its scratch folder (256 characters
  with a 20-character name) past 259 [inference]; nothing checks that yet [code]. autochart's staging files there
  are past 259 on every profile (§2, work folder); only Node writes them, and pruning deletes in the `\\?\` form,
  neither tried on Windows.
- **Device check** (`device.py`):
  - CUDA arch check against `torch.cuda.get_arch_list()` and a matmul smoke test;
  - a CPU fallback that is always shown to the user with its reason;
  - free GPU memory between stages;
  - `torch.set_num_threads(cores − 1)` on CPU.
- **Rejected:** PyInstaller/Nuitka (4 GB onefile limit, Defender false positives), an embedded-Python zip, conda-pack (win-64 torch stuck at 2.9.1), Docker, and Pinokio (a possible second channel later).

### 4.4 First-run flow
1. Download `songcharter-setup.exe`. If it is unsigned, SmartScreen asks once ("More info > Run anyway").
2. Install to `%LOCALAPPDATA%\songcharter` with Start Menu and desktop shortcuts.
3. The bootstrap reports the GPU and lane, checks free disk, and detects Smart App Control. SAC blocks an unsigned `python.exe` with no per-app exception [doc, untested], so the tool shows step-by-step instructions, written after the spike.
4. `uv sync` runs with progress bars; an interrupted download resumes.
5. The browser opens `http://127.0.0.1:8765/`; the header shows "GPU: RTX 4070 (12 GB)" or "CPU mode: <reason>".
6. On the first song, a one-time model download runs with a progress bar. Each song gets a work folder in
   `%LOCALAPPDATA%\songcharter\work\<name>-<key>`, keyed by the file's SHA-256, so charting the same file again
   reuses its stems and engine outputs (a warm re-run of the test song took 41 s on the dev CPU, §5 M3); the least
   recently used go once the work folders pass 5 GB (§2, work folder). Nothing is written beside the output but the
   song folder (or its `.failed`).
7. Later launches work offline. Updates re-run the installer. Uninstall asks before deleting models and the work folders, and never touches Clone Hero songs.

### 4.5 UI flow
A stdlib `ThreadingHTTPServer` on 127.0.0.1 serves a vanilla-JS page (no CDN; CSP `default-src 'self'`).
- **Guards:** only the Hosts 127.0.0.1 and localhost; POSTs need `X-Songcharter: 1` and a same-origin `Origin`; uploads go as a raw body; progress comes over SSE. The guards were tested with curl [here, v1].
- **Built in M4-04** [code]: the server, the guards and screens 1 to 3 (drop, options, progress with cancel), with `chart --events` as the job's protocol (§2.0, `ui/`). The preview, export and diagnostics are M4-06.
- **Screens:**
  1. **Drop a file.** Metadata comes from the tags and is editable.
  2. **Options:**
     - instruments;
     - difficulties (Expert by default, §2.11);
     - solos (the sections named Solo by default, or the sections the player picks; §2.10);
     - guitar takes (by default 4 on CUDA, 1 on the CPU);
     - tempo (auto / constant / follow the band);
     - chord-density slider.
  3. **Progress:** one bar per stage with time estimates and a cancel button. Any CPU fallback is shown here.
  4. **Preview** (highway):
     - notes from scan-chart's parse, so the preview shows what Clone Hero reads;
     - `song.ogg` as the clock;
     - beat and measure lines; section jumps; 0.5× and 0.75× speed; a WebAudio metronome;
     - flags for review (odd meter, uncertain bar phase, low-confidence beats, free islands, guitar sections that failed their checks).
     - As built, `songcharter chart` writes a static preview after every build (`preview.py`: an overview of every
       part against its stem, tempo, sections and star power, and a page a minute, PNG) into the work folder's
       `preview/`, with its flags in `pipeline.json` and the overview's path in the summary [code].
  5. **Quick fixes** (critique G11): shift the downbeat by ±1 beat, nudge the global offset in ms, set the first beat.
     - These re-map the existing Expert notes by ticks without regenerating them.
     - Star power, activation lanes, sections, solos and the lower tiers depend on bar lines, so they are recomputed (seconds, not minutes [est.]).
     - An offset nudge also re-pads `song.ogg` and re-runs `verify_sync`.
     - ×2/÷2 and time-signature edits still re-run the note stages (minutes for guitar).
  6. **Export:**
     - `.zip`, with a note that it contains audio made from the recording and that sharing it is distribution;
     - **Install into Clone Hero:** find the songs folder (`settings.ini`, `Documents\Clone Hero` via `SHGetKnownFolderPath`, or a portable `PlayerData`), copy to a temp folder, rename, then tell the user to "Scan Songs". Offer the zip if Defender's Controlled Folder Access blocks the write.
     - **Preview in Clone Hero:** `"Clone Hero.exe" --song <folder> --player Guitar,Expert` (documented CLI [doc, untested]).
     - **Open polish workspace:** the stems under non-reserved names (not `guitar.ogg`, `bass.ogg`, `drums.ogg` or any other name Clone Hero loads), kept out of the install and the zip (critique G11), plus a one-page Moonscraper guide and a "Re-check & re-install" button.
     - **Diagnostics bundle:** logs and `doctor.json`, with no audio (critique G11).
- **Status:** none of the UI is built [untested].

### 4.6 CI (with the Windows build)
- **Linux:** pytest; `uv lock --check`; an end-to-end CPU chart of a self-made 20 s clip (never copyrighted audio) followed by scan-chart; the evaluation selftest on synthetic charts.
- **`windows-latest`:** a dry run of every lane; ISCC build and portable zip; silent per-user install; first run on the CPU lane under PowerShell 5.1; `Test-Bootstrap.ps1` with a fake `nvidia-smi`; the clip chart and scan-chart check; the Host/Origin guard check; a clean silent uninstall.
- **Weekly:** install the real cu132 lane on the GPU-less runner and prove it imports and falls back to the CPU (v1).
- **Signing:** SignPath Foundation (free for OSI projects) or Azure Artifact Signing (individuals in the US or Canada); otherwise unsigned with a one-time SmartScreen click (§9).

### 4.7 The owner's PC (RTX 5070, WSL2)
- The comparison ran here: `eval/gpu.sh check|start|status|results` (see `eval/README.md`).
- Give WSL enough memory in `%UserProfile%\.wslconfig`. WSL defaults to half of Windows' RAM. Two STRUM runs died in a VM reported at about 15.5 GB, and one finished at a reported 24 GB [reported in the practicality brief; not logged]. STRUM's peak RSS is unmeasured.
- CUDA in WSL2 needs only the Windows driver [doc].
- Test the native installer on the Windows side before giving it to the friend.

---

## 5. Milestones

Tolerances come from the measured spreads: autochart run to run up to 0.035 on Expert (0.151 on one Medium), STRUM drums 0.087 [here]. Proxy deltas allow 0.02, because the merge build re-times the same notes on the same audio. In the tables, **(W)** marks a warning: reported, not failing.

### M1a: Goal 1 for the friend's instrument(s), plus a Windows spike on the friend's PC
**Scope:**
- **Gate first:** Q1 (which instrument(s)) and Q5 (the same MP3?) are answered before the playtest. The v1 chart was
  built for all three instruments without waiting for Q1 (status below).
- The merge build, for the friend's instrument(s) only, from existing outputs: the 5070 run's autochart and STRUM test-song folders (`eval/gpu.sh results`), the `htdemucs_ft` stems, and ADTOF's test-song chart (for the kick check). `beatgrid` builds the map from the drum stem; the guitar audit's 800 local drum beats are used only as a yardstick, never to build the grid.
- Guitar only: done for the v1 chart with three CPU seeds beside the GPU take, spliced per section (§2.7, Several
  takes).
- **Before fixing the tempo-median and drum-timing rows:** measure, on the test song, the offset between the guitar audit's rising-edge picker (tempo rows) and the drums/bass audit's band-flux proxy (drum timing rows). Drum notes snap onto the grid, so both rows can hold only if that offset matches the calibrations'. On Take Me Out the two calibrations differ by about 22 ms (humans 13.5 ms before rising-edge onsets; +8.75 ms after the proxy) [inference]; on the test song it is unmeasured.
- A playtest on the friend's PC. While there: `nvidia-smi`, RAM, an autochart app install, and SmartScreen and Smart App Control behaviour.

**Status: delivered and played.** v1 was played by the friend; v1.1 followed his feedback.
- The v1 chart of the test song was delivered with all three instruments: guitar from the spliced autochart takes
  (§2.7), bass and drums from STRUM, all re-timed onto our grid. A second folder, the same but with ADTOF's drums,
  was built beside it.
- It passes the gate, and scan-chart 8.0.1 finds it playable with 0 chart issues (§2.13).
- The friend played v1 (Guitar, on Expert; §9 Q1): "Everything played pretty well". He asked for Expert only unless
  asked otherwise, and for solo trackers on the two solos. v1.1 (Expert only, guitar solos on Solo 1 and Solo 2,
  Expert notes identical to v1) was delivered after that. He also named a sparse stretch around 2:32–2:35 of the
  recording, then said to disregard it; the strumming research on it is in §2.7.
- Still open in M1a: the Windows spike on the friend's PC (above).

**Acceptance (test song).** "Source" means the autochart GPU take for guitar and STRUM's GPU output for drums and bass, measured with the audits' methods. Rows apply to the friend's instrument(s); "all" rows always apply.

| area | applies to | check | pass |
|---|---|---|---|
| gates | all | scan-chart on the final folder | playable; 0 chart issues except `noAlbumArt`; 0 `emptyStarPower` and 0 `emptySoloSection` on any track or difficulty |
| | all | sync | `verify_sync` < 1 sample |
| | all | determinism | two CPU runs on the cached stems give a byte-identical `notes.chart` |
| | all | nesting | every lower onset is an onset one level up (±5 ms) |
| | all | tests | the existing tests pass, and new unit tests cover tick mapping, snapping and the reducer rules (v1) |
| tempo | all | beats more than ¼ beat from the local drum beats, 42.7–401 s | 0 (autochart 43, STRUM 0) |
| | all | beat lines vs the local drum beats, median signed | within the human −14 to −18 ms (the guitar audit's rising-edge picker) ± 5 ms; `beatgrid` tonight −16.6 ms. Provisional until the detector offset is measured. |
| | all | beat lines vs the local drum beats, spread | p95 \|dev − median\| ≤ 45 ms, i.e. no worse than tonight's grid (free 44.6, click 43.7) [decision]; p95 \|dev\| reported beside it (tonight 50.7; STRUM's line 34.7; the rigid line 47.9) |
| | all | bar lines | kick phase (0) throughout 60–400 s |
| guitar, Expert | guitar | onsets kept by re-quantization | ≥ 98 % of the chosen take's onsets; none moved > 25 ms outside the two half-tempo stretches |
| | guitar | HOPO flips inside 67.2–89.6 s and 218.5–230.3 s | none written from autochart's intent there (the tempo-level rule, §2.6; today 11 of 28 flips sit there) |
| | guitar | other-stem P@50 / slot-AUC | ≥ 0.591 − 0.02 / ≥ 0.705 − 0.02 |
| | guitar | note offset vs other-stem onsets | within the human −7.8 to −20.3 ms, ± 5 ms (source −28.7 ms) |
| | guitar | missed active audio (1-bar windows) | ≤ 28.7 s (no regression); target ≤ 10.1 s (STRUM's), with 341–399 s fixed |
| | guitar | ladder | Hard < 0.90 of Expert (error); Medium 0.36–0.65 and Easy 0.23–0.49 (W) |
| drums, Expert | drums | all-hit proxy F1@50 / precision | ≥ 0.893 − 0.02 / ≥ 0.951 − 0.02 |
| | drums | timing vs proxy | from +33.9 ms to the human +8.75 ± 10 ms (a one-song calibration). Provisional until the detector offset is measured. |
| | drums | missed kick-like onsets | ≤ 71 (no regression); ADTOF's test-song chart checked against them |
| | drums | off-grid notes / `brokenNote` | 0 / 0 |
| | drums | tom/cymbal collisions | dropped toms counted (W) |
| | drums | ladder | Hard ≤ 0.90 of Expert (source 0.985; human 0.853); Medium 0.39–0.85 and Easy 0.30–0.71 (W), reported against the human 0.648 / 0.534; Easy has cymbals |
| | drums | Medium hand pads | no right-hand 8ths (hi-hat or ride hits ≥ 1 beat apart) at ≥ 140 BPM; the test song is at 142 (critique G7) |
| bass, Expert | bass | combined proxy F1@50 | ≥ 0.476 − 0.02 |
| | bass | lane follows pitch, on pitch changes | ≥ 0.331 (no regression); target ≥ 0.6 (human 0.815) |
| | bass | coverage | 0 notes after 402.4 s; no more than 16 gaps of ≥ 2 s while the stem is active |
| | bass | ladder | Hard < 0.90 of Expert (error; the human bass Hard is 0.889); Hard / Medium / Easy reported against the human bass 0.889 / 0.609 / 0.453 (W); source Easy 0.024 |
| song | all | metadata | correct name and artist; 20–30 sections at bar lines; solos on every guitar difficulty, only where confirmed by ear |
| play | all | the friend's playtest on their difficulty | no "out of sync" or "unplayable" passage; a written list of the worst 3 passages |
| spike | — | the friend's PC | GPU, driver, compute capability and RAM recorded; autochart app wall time and peak memory for one Expert take; Smart App Control state |

### M1b: the test song's other instruments
**Scope:** the instruments M1a left out, on the same build. **Acceptance:** the rows of the M1a table for those instruments.

### M2: Evidence before gates (Linux or WSL)
**Scope,** in this order. Each row is conditional on the owner's answers; efforts are rough estimates.

| order | item | needs | effort [est.] |
|---|---|---|---|
| 1 | the scorer fixes (§3.4), including `build_refs.sh` | — | small |
| 2 | `beatgrid` validation with `score.py` on the six references, with and without a Beat This start, and v1's tempo prototype beside it (§5.6, task 2) | — | small |
| 3 | the engine for the friend's instrument: **guitar** Engine A (B2) vs autochart's engine (B1) over 3 seeds, with the ×1 vs ×2 level test, 1 knob-conditioned take vs seeded takes (critique G5), and v1's T 0.9 / top-p 0.95 vs the default; **drums** ADTOF plus a new lane mapper vs STRUM (a benchmark), both re-scored after the quantizer; **bass** the rules on whole songs vs STRUM plus re-lane (a benchmark) | Q1; Q2 = yes for guitar and drums | guitar medium to large (a new onnxruntime driver); drums medium; bass small to medium |
| 4 | the same for the other instruments | Q2 | as above |
| 5 | our reducer vs autochart's tiers | — | small (`reduce.py` exists) |
| 6 | 6s vs ft stems | Q2 (moot if NC weights are rejected: both are Demucs weights) | small |
| 7 | allin1 (fold 0 and ensemble, on our 6s-folded stems vs the ft-stem result) vs librosa, against Encore section labels: done on 5 references (§2.5); repeat on the row-8 set | — | small to medium |
| 8 | the reference set: ≥ 20 eligible songs under §3.3's cutoff | Q13 to scale up | medium |

If Q2 rejects non-commercial weights, the B2, B1 and ADTOF work in rows 3–4 and row 6 is moot; Goal 2 then needs a rules route and a separator with a permissive licence, which none of the sources found.

**Acceptance:**
- the self-test corruption suite moves each metric as expected (+30 ms shift, ±20 ms jitter, random lanes, half the notes, constant tempo, self);
- every reference has a calibrated offset;
- per-song seed spreads are known;
- every row of the §2 overview is updated with paired per-song differences and a bootstrap CI;
- Lucretia is reported separately;
- the reference manifest lists ≥ 20 songs meeting §3.3's cutoff (`modifiedTime` ≥ 2026-10-01, no earlier chart in the same `versionGroupId`, capped per charter), with the eligible count reported, and a plan to reach about 50.

### M3: Pipeline v0.1, any song, command line (Linux or WSL)
**Scope:** `songcharter chart <file> --out <dir>` (built: `pipeline.py` and `cli.py`, §2.0). It
covers the shared separation, the beat grid, the engines chosen in M2, the scaffolding and the gate.

**Acceptance (per reference song, per instrument), under the rules of §3.2:**
- guitar: per song F1@50 ≥ the best tool on that song − max(0.035, the measured seed spread) over ≥ 3 seeds, plus the mean rules;
- drum onsets: per song F1@50 ≥ ADTOF's − 0.02;
- drum lanes, if the new mapper is adopted: mean exact lane agreement ≥ STRUM's mean − 0.02, and per song ≥ STRUM's on that song − 0.05;
- beat F1 ≥ autochart's per song − 0.02, Lucretia separate, and no half- or double-tempo runs;
- 0 note-level scan-chart issues; nested tiers; 0 `emptyStarPower`; 0 `emptySoloSection`;
- two CPU runs byte-identical from a fresh separation (Demucs seeded or `shifts=0`, §2);
- the test song still passes M1a's gate, tempo, bar-line, drum timing, off-grid, ladder, coverage and metadata rows (not the rows measured against an imported source, such as "≥ 98 % of the chosen take's onsets");
- the existing tests pass, and new tests cover the CLI end to end;
- wall time and peak RAM logged.

**Status: built and run end to end** [here, pipeline run]. In the dev container (CPU, 2 torch threads, 1 guitar take,
allin1 through all-in-one-infer 3.1.0 in its own Python) on the test song's MP3 and on Take Me Out's `input.wav`, the
one reference run so far. The acceptance list, checked once on one song where it asks for every reference:
- guitar, Take Me Out, 1 seed: Expert F1@50 0.909, above the best tool's 0.880 (autochart's own GPU chart; chartgen
  0.591, STRUM 0.678), so the per-song rule holds on this song; lane direction 0.667 (trivial 0.408), exact lanes
  0.150. The seed spread (≥ 3 seeds) is not measured. Its lower
  tiers, from our reducer, trail autochart's own: Hard / Medium / Easy 0.818 / 0.722 / 0.523 against 0.876 / 0.881 /
  0.725;
- drum onsets: 0.944 against ADTOF's 0.947 (−0.003; the rule allows −0.02), kick 0.976 (ADTOF 0.981);
- drum lanes: exact lane agreement 0.285 against STRUM's 0.667; no new mapper is adopted yet, so the rule waits;
- beat F1 0.962 against autochart's 0.990, so 0.008 short of the rule's −0.02 (median error 7.8 against 15.0 ms;
  442 beats against the human 442, no half- or double-tempo run). The bar phase was flagged uncertain (margin 0.01):
  0.69 of our bar lines are within 70 ms of a human bar line, all the misses in 0–54 s and after 234 s (0.96 sit on a
  human beat);
- scan-chart 8.0.1: playable, 0 chart issues on both songs, no metadata issue; the reducer's checks pass (nested
  tiers); 0 `emptyStarPower`, 0 `emptySoloSection`;
- two CPU runs from a fresh separation (Take Me Out, two work folders, 2 threads each): the decode, all six stems and
  every engine's output are sample- or byte-identical, and so are the final `notes.chart` and `song.ini` (the WAV files
  differ only in the timestamp libsndfile writes into their PEAK chunk). The stems are not bit-identical to the shared
  stems of the same cache key made by another job (thread count not recorded): up to 1.5·10⁻⁶ apart, about 125 dB
  under the signal; every engine's chart from them came out byte-identical to the engine builders' runs on both songs;
- the test song still passes the gate (scan-chart playable, 0 chart issues, sync worst 0.00 samples, 27 sections,
  24 / 20 / 21 star-power phrases on guitar / bass / drums and 25 fills); M1a's other rows were not re-run;
- the existing tests pass; `tests/test_pipeline.py` covers the pipeline with stand-ins for the heavy stages and the
  CLI end to end on a synthetic song;
- wall time is logged per stage in `work/pipeline.json`, with songcharter's own peak RSS and, since the review of the
  integrated pipeline, allin1's runner's own peak; the peaks below come from a sampler of the process tree's RSS:

  | song | decode | separate | drums | bass | sections | guitar | build and gate | total | peak RSS |
  |---|---|---|---|---|---|---|---|---|---|
  | test song (6:52, MP3) | 3.7 s | 169.1 s | 20.3 s | 21.1 s | 118.7 s | 403.5 s | 23.1 s | 759 s (12.7 min) | songcharter 3.6 GB (separation); allin1's runner 7.8 GB; the process tree 10.1 GB, during sections; autochart's engine not sampled |
  | Take Me Out (4:01, WAV) | 1.6 s | 99.6 s | 10.9 s | 12.4 s | 70.2 s | 196.1 s | 15.4 s | 406 s (6.8 min) | songcharter 2.5 GB; allin1's runner 4.8 GB; autochart's engine 4.6 GB; the tree 6.6 GB, during sections |

  A re-run of the test song with every cache warm took 41 s: the decode and its hash, reading the stems, the ADTOF
  engine's tempo estimate (4 s), the allin1 probe (6 s) and the build (23 s).
- after the review of the integrated pipeline (§11) the test song was charted again into a copy of its work folder
  with the shared seeded stems in place (no separation ran). The drums, bass and sections engines ran again (those
  stems differ from the run's own by up to 1.5·10⁻⁶) and the guitar take ran once more (it had no `take.json` yet;
  autochart's separation and beat map were cached, so 217 s of transcription). Every engine's chart, the segments,
  the take and the final `notes.chart` came out byte-identical to the run above, and the gate passed again: 6.9 min
  in all. `pipeline.json` recorded allin1's runner at 7929 MB, which the tree sampler confirms (7924 MB), and no
  children figure; on the warm re-run (42 s, every stage cached) the old record had shown a 2.2 GB "child" for the
  sections and the guitar, where the only child was allin1's probe at 0.6 GB [here, pipeline run].

**With the pipeline's defaults** (branch `pipeline-defaults`: Expert only, solos by the label, takes by device, the
preview, the work folder in the cache, the clip) [here, pipeline-defaults runs; dev container, CPU, 2 torch
threads, so 1 guitar take by default; allin1 fold 0 through all-in-one-infer 3.1.0]:

| run | exit, gate | wall | what it shows |
|---|---|---|---|
| Take Me Out, defaults (solos still "stems"), `--work` its warm M3 folder | 0; OK, scan-chart 0 chart issues | 300 s | Expert only (`onsets E 868`); 1 take, `pipeline.json` recording why; the guitar take ran again (234 s; every other engine cached); preview 5 pages, nothing flagged; 1 solo, 191.5–205.0 s |
| Take Me Out, the final defaults ("labels"), a copy of that folder | 0; OK, 0 chart issues | 60.9 s | every engine cached: assemble 19.3 s, preview 18.2 s; the same 1 solo on allin1's "Solo" (191.5–205.0 s; the human chart's main_riff_4, a false tracker); nothing clipped; work folder 696 MB; peak RSS of the process tree 1.8 GB |
| a 35-s excerpt (95–130 s), `--work` in /dev/shm | 0; OK, 0 chart issues | 162 s | nothing ran past the end (clip counts 0); preview 1 page, 1 gap flagged |
| a 35-s cut (197–232 s) inside a long guitar sustain | 0; OK | 129 s | 1 Expert sustain clipped, the guitar ending 1.78 ms before song.ogg (checked on the folder) |
| the 95–130 s excerpt, work folder by default | 0; OK | 128 s | `work/tmo_excerpt-d1004c46f2e46f3c` in the cache (the key matches the file's SHA-256), 101 MB with `ac/d1004c46`; deepest paths 63 characters below the work folder and 226 below the scratch folder (on Linux autochart's stem folder name is 70 characters, against 32 on Windows) |
| the M3 smoke excerpt's config through `songcharter assemble`, before and after the clip | 1, then 0 | – | §2.13: four `noteAfterAudio` errors before, 1 sustain clipped after |
| the test song's MP3, the final defaults, a copy of its M3 work folder whose stems had been deleted | 0; OK, scan-chart 0 chart issues, 4 warnings (`fillNoCrash` 1, `noFillBeforeStarPower` 3) | 951 s (15.9 min) | separation 322.8 s, drums 28.2, bass 30.8, sections 168.5 and guitar 330.4 s all ran again (their caches were keyed by other stems), on a machine shared with other jobs (M3's run: 169 and 404 s). Every engine's output and the Expert notes of all three parts came out identical to M3's (guitar 1113, bass 789, drums 1590 notes; 24 / 20 / 21 star-power phrases, 25 fills), and the 27 sections too; Expert only. **3 solos:** [167.346, 180.709], [234.966, 258.419] and [317.782, 361.726] s (Solo 1's first half, all of Solo 2, and Solo 3A–3D, unconfirmed), as the solo evaluation predicted on these sections (its third ended at 368.275 s on the GPU take). Preview 7 pages, 6 flags (5 guitar gaps in 4:47–6:17 song time, where the CPU take is sparse, and 1 bass sustain); nothing clipped; work folder 1.19 GB; peak RSS of the tree 10.1 GB (allin1's runner 7.8 GB), as in M3 |

Take Me Out, Expert, scored with `score.py` against the human chart [here, pipeline run; tools: here, 5070; ADTOF: here,
ADTOF test]:

| | guitar F1@50 | bass F1@50 | drums F1@50 | drums kick | drums exact lanes | beat F1 | scan-chart issues |
|---|---|---|---|---|---|---|---|
| `songcharter chart` (CPU) | **0.909** | **0.912** | 0.944 | 0.976 | 0.285 | 0.962 | 0 |
| autochart (GPU) | 0.880 | — | — | — | — | **0.990** | 34 |
| chartgen (GPU) | 0.591 | — | — | — | — | 0.830 | 0 |
| STRUM (GPU) | 0.678 | 0.663 | 0.846 | 0.873 | **0.667** | 0.120 | 28 |
| ADTOF test (unquantized) | — | — | **0.947** | **0.981** | 0.283 | 0.272 | 3 |

- Lane direction (trivial in brackets): guitar 0.667 (0.408) against autochart's 0.622 (0.432); bass 0.871 (0.700)
  against STRUM's 0.748 (0.719). Timing (ours − human, median): guitar −4.8, bass −4.7, drums −3.8 ms.
- Lower tiers, F1@50 Hard / Medium / Easy: bass 0.861 / 0.825 / 0.764 (STRUM 0.500 / 0.285 / 0.000); drums 0.968 /
  0.858 / 0.680 (STRUM 0.770 / 0.681 / 0.619).
- The bass and drums numbers equal the engines' own after-quantizer runs (bass 0.912, drums 0.944 [here, bass and
  drums engine runs]): the pipeline's engine charts are byte-identical to theirs.
- Against the test song's delivered v1 chart (guitar spliced from four autochart takes, STRUM bass and drums), Expert
  F1@50 after removing the median offset: guitar 0.844 (exact lanes 0.182), bass 0.710 (0.282), drums 0.924 (0.794).
  Onsets Expert / Hard / Medium / Easy, ours against v1: guitar 1113 / 874 / 512 / 346 against 1201 / 950 / 584 / 391;
  bass 789 / 613 / 437 / 228 against 658 / 551 / 374 / 234; drums 1176 / 961 / 715 / 601 against 1217 / 1087 / 710 /
  617. Nobody has listened to or played either.

### M4: A release the friend can use (Windows, or WSL if the owner accepts it)
**Superseded:** the route is WSL2 (§9 Q4); M4's plan, scope and acceptance are `docs/work-orders/M4-00-plan.md`.
What follows is the plan for the native route, kept for M4-99.

**Scope:** the local UI (§4.5) and the installer (§4.3).

**Acceptance on the friend's 4070 PC:**
- it installs and runs without help;
- a 7-min song with 1 guitar take finishes in ≤ 8 min. Estimates behind that target [est.]:
  - B2: 6s on GPU 10–20 s [est.]; decoding 107–204 s per take on 3 threads [here, critique]; ADTOF 13–30 s [here]; pYIN 20–50 s [here]; sections and packaging; about 3–7 min;
  - B1: autochart's Expert job 228.8 s, its own separation included [here, 5070], plus the rest; about 5–7 min;
  - Beat This on the 4070 and packaging are [untested];
- peak RAM within the PC's RAM minus 4 GB [est. margin]; VRAM within the card's memory;
- the work folders (§2, work folder) on the friend's profile: the deepest file a run leaves under 260 characters
  (256 with a 20-character user name and a 40-character song name, 3 to spare [code]), and autochart's staging
  files, which are longer on every profile (309 with that name), written by Node without an error; a re-run of the
  same file reusing its folder; pruning to 5 GB with a file in use giving one warning, not a failure, and leaving
  that folder whole (a folder with a file in use in it is expected not to move [inference]; tested only with
  stand-ins that raise `PermissionError` [code]), and deleting a scratch folder that holds a staging file; with the default 4 takes on CUDA, the time target above counts 1 take, so the
  4-take run is timed too (+5.75 min a song on the 5070, §2.7);
- any CPU fallback is shown to the user;
- the test-song output passes M3's non-regression checks against the Linux build (not bytewise: GPU stems and flipped tokens differ);
- the song plays in Clone Hero after a rescan;
- **UI** (v1's M3 acceptance, carried over):
  - the full drop → options → progress → preview → zip / install / workspace flow works on the test song and the clip;
  - preview notes line up with scan-chart's ms times to within one frame;
  - the metronome and beat lines line up audibly and visibly;
  - ×2/÷2 and time-signature edits re-run correctly; the quick fixes recompute star power, lanes, sections, solos and tiers;
  - cancel works;
  - Host/Origin guards return 403; unsupported upload types get 415; a duplicate install gets 409; an unknown folder is refused;
  - fully offline once models are cached.

### M5: Quality iteration
**Scope:**
- a learned or improved drum lane classifier (training data needs the owner's consent);
- bass;
- 6/8 and odd meters, including `tempo.py` time-signature denominators other than 4;
- quick tempo fixes in the UI;
- the stress set: songs above 185 BPM, 6/8 and shuffles, drumless, long (12–15 min) or with long silences, degraded rips (critique G1–G3, G9, G10);
- polish-time logging;
- the per-section regeneration of failed guitar windows (§8).

**Acceptance:**
- each adopted change has a paired development-set gain with a CI excluding 0, and no per-song regression larger than max(0.05, the run-to-run spread);
- it is confirmed once on the frozen test set;
- stress songs pass the gates or are flagged for review, with no crash.

### 5.6 The first three engineering tasks
**Status after the first-chart review** (`main` at e0e4b7e; §2.0): done are the commits, the reducer's tests, the
star-power, solo and section modules, assembly with the scan-chart gate, and the CLI's `assemble` command. Still
open below: the importer check as a repo test, the `start=` changes, the tempo-level HOPO rule, the Easy sustain floor
in `quantize.py`, taps, the band rating and `eval/m1_check.py`.

1. **Importers and the code already written.**
   - Done: `importers.read_chart`, `read_mid` and `read_song` exist (uncommitted), and the parser-equivalence check passed: on the three test-song folders, note times equal scan-chart's `msTime` (worst difference 2.9·10⁻¹¹ ms; 0 flag, lane or sustain mismatches) [here, importer check]. It is a scratchpad script, not yet a repo test.
   - To do: make that check a repo test (fixtures outside the repo, skipped when absent). Commit `importers.py`, `quantize.py`, `reduce.py`, `tests/test_importers.py`, `tests/test_quantize.py`, `tests/test_beatgrid.py` and the `beatgrid.py` changes.
   - Read STRUM's folder with `time_offset` taken from its log's `phase_offset_ms` (0.0697 s on the test song, 0.3001 s on Take Me Out), not a constant.
2. **Validate `beatgrid` on whole songs.** Tonight's runs did part of it (§2.3). Remaining:
   - beat F1@70 and median error against the human maps with `score.py`'s tempo metrics, on all six references, with and without a Beat This start;
   - the median of (beat − nearest ADTOF kick or snare): ADTOF minus human is −1.5 to −6.8 ms on the four Harmonix songs, so the target is +1.5 to +6.8 ms ± 5 ms, Kimochi Warui excluded;
   - on the test song, the offset between the two audits' detectors (M1a);
   - the `start=` changes of §2.3 step 6.
   - Done when §2.3's click/free and phase decisions are confirmed or revised.
3. **Quantizer, reducer, assembly and an M1 check script.**
   - `quantize.py` exists. Add the tempo-level HOPO rule (compare `TimedSong.beats` with ours), change `timed.py`'s "for diagnostics only", align the Easy sustain floor with `reduce.py`, and settle taps (§2.0).
   - `reduce.py` exists; add its tests.
   - Write the star-power, solo and section modules; add a band rating to `ini.write_ini` and `build_song_folder`; then `build_song_folder` and scan-chart.
   - `eval/m1_check.py`: re-runs the audits' reference-free checks on our folder (guitar: beat lines, onsets and slot-AUC, coverage, playability, HOPO flips in the half-tempo stretches; drums and bass: timing, lane direction, ladders, pitch changes, dropped toms) and prints source vs ours against the M1 tolerances.
   - Done when the M1 table fills itself.

**Next after these:** re-run the ADTOF/STRUM kick fusion with de-duplication per grid slot (decides C4), and, for guitar, generate the seeds with `AC_SEED`.

---

## 6. Notes for the first song

### song.ini values

| key | value |
|---|---|
| `name` | Beast Monster Thing (Love Isn't Love Enough) |
| `artist` | Car Seat Headrest |
| `album` | How to Leave Town |
| `album_track` | 2 |
| `year` | 2014 |
| `genre` | Indie Rock (matches the existing Car Seat Headrest charts) |
| `charter` | the owner's choice (§9) |
| `diff_guitar`, `diff_bass`, `diff_drums`, `diff_drums_real` | from §2.12, charted parts only; expect about 3 for guitar (the same-EP human chart averages 3.2 notes/s, max 10) |
| `diff_band` | from §2.12, once `ini.py` can write it |
| `pro_drums` | True |
| `preview_start_time` | the first chorus start in ms on the padded timeline (input seconds + `pad_seconds`, §2) |
| `loading_phrase` | optional, e.g. "Auto-generated by songcharter" |

Omit `delay`, `song_length`, `hopo_frequency`, `eighthnote_hopo` and `sustain_cutoff_threshold` (`ini.py` already does). Never write "Unknown Album".

### Facts
- **File:**
  - The streaming master: the MP3 container reports 412.395 s; the gapless decode is 412.363 s [here].
  - MP3 encoder delay 1105 samples (25.06 ms).
  - Audible from t = 0.
  - The mix decays over 401–405.5 s, falls below −41 dB from 406 s and is digital silence from 410 s [here].
- **Tempo:**
  - About 142.00 BPM (rigid fit 142.0009); first beat ≈ 0.047–0.050 s; about 975 beats, about 242 bars of 4/4, downbeat on beat 0 [here].
  - The drummer wanders about ±20–30 ms around the rigid grid. 800 of 976 grid beats have a drum onset within ±60 ms, and the rigid grid's p95 deviation from them is 47.9 ms, against 31.9–33.4 ms for human maps on two references [here].
  - `beatgrid` chose free mode (0.66 of beats confident; 81 markers at tolerance 0.003) [here, beatgrid run].
- **Entries and ends** [here]:
  - no drums or bass in the intro; the drums enter at 42.70 s and the bass at about 43.78 s;
  - the bass stem is silent from about 402.4 s and the drum stem from about 403 s;
  - the other stem is active until 405.7 s.
- **Bar phase:** from 60 s on, the kick sits on grid phase 0 and the snare on phase 2 [here].
- **Guitar:** mostly 8th-note strumming (83 % of guitar-stem onsets within 25 ms of an 8th) [here].
- **Existing tool outputs** [here, 5070, unless noted]:
  - **autochart Expert:** 1,139 onsets, first note 3.42 s, last 400.85 s; half tempo at 67.2–89.6 s and 218.5–230.3 s; Expert solos at 67.9 s and 218.1 s; 10 named sections; no star power; thin 341–399 s.
  - **STRUM:** one marker at 142.000071 BPM; audio trimmed by 69.7 ms (`phase_offset_ms` in its log; 300.1 ms on Take Me Out, so read it per song).
    - Drums: 1,238 Expert hits from 42.746 s to 401.21 s, +33.9 ms against the proxy, 26 off-grid notes, 71 missed kick-like onsets.
    - Bass: 661 onsets, +22.6 ms, 16 gaps of ≥ 2 s, last note 405.02 s in silence.
  - **ADTOF:** 1,595 notes from 1,185 hits on the 6s drum stem, stem lag 0, sync OK [here, ADTOF test].
- **Sections:** autochart and STRUM agree near 43–44, 90–91, 110–112, 167 and 207–208 s.
  - autochart's names: Intro 1, Verse 1–4, Chorus 1, Bridge 1, Section 1–2, Instrumental 1.
  - v1's allin1 prototype found 16 sections, including four "Solo" labels (Solo 1, Solo 2, Solo 3a, Solo 3b). None is verified by ear.
- **Key and tuning:** key D (Ultimate Guitar), E standard (Songsterr).
- **Style references:**
  - IaSg14's same-EP "I Want You to Know…" (guitar only, 851 markers, 24 sections).
  - InsaneOwO's "Kimochi Warui", which sits about 22–25 ms late; ADTOF's −28.0 ms against it is consistent with that.
  - Human Expert charts of two other Car Seat Headrest songs run 2.73–3.18 notes/s with 68–69 % chords, so our default chord density will read lighter than they do.

### Quirks
- `work/stems/htdemucs_6s/song/*` were separated from the MP3 and are 1105 samples late. Use the ft stems or the ADTOF test's 6s drum stem (both lag 0), or shift the old 6s stems by −1105 samples.
- allin1 deletes stems unless `keep_byproducts=True`.
- Trackers flip between 142 and 71 BPM in this song; autochart did exactly that in two stretches.
- ADTOF on the mix finds false kicks here (54 vs 26 on the stem in a v1 excerpt), hence the fusion.
- The song fits Fretformer's caps (autochart: 933 beats, 3,531 of 8,192 tokens).
- scan-chart reports `playable=false` on a folder without audio; always gate the final folder.
- Lyrics and vocals are out of scope.

---

## 7. Risks and honest quality expectations

- **Guitar frets are the weakest part.**
  - No audio method predicts human lane choices well. autochart's mean direction κ is 0.465, but 0.37–0.39 on the Car Seat Headrest references, and its exact-lane agreement is 0.07–0.41. Rules reach κ 0.20.
  - On those two songs autochart is no better than an 8th-note grid on onsets.
  - Expect correct rhythm with plausible, consistent frets that a charter will change.
- **Our own guitar engine is unmeasured.** Every guitar number belongs to the autochart app (critique E5). If B2 loses to B1 in M2, Goal 2 depends on an AGPL engine run as a separate program, or on option D.
- **Drum lanes.** No ADTOF lane mapper reaches STRUM's 0.687 yet, and STRUM cannot ship. Green (0.40) and blue (0.52–0.55) are weak for both tools; ride vs crash is unreliable when the crash is ridden. The onset advantage of ADTOF over STRUM may shrink once STRUM's lateness is removed [inference].
- **Bass lanes** barely follow pitch in STRUM (0.331 on pitch changes), and our re-laning is untested.
- **Polish is expected.** No measured polish time exists; M5 logs it.
- **Tempo.** `beatgrid` has whole-song runs but no `score.py` beat F1. On the test song its p95 spread on the audit
  yardstick is above STRUM's straight line. On four references its kick-on-1 bar phase failed on 2, and Lucretia has
  long stretches off the human beats (0.26 within 70 ms; Take Me Out rose from 0.84 to 0.986 with the local periods).
  Its Beat This path is untested and needs code changes. Odd meters are weak (downbeat F 0.45–0.67 on 7/4). Rubato,
  fermatas, silent breaks and free islands are untested.
- **Licences:** Fretformer weights are CC BY-NC-SA 4.0; ADTOF's are BY-NC-SA by inheritance, and our port's code licence is uncertain; the Demucs weights are treated as non-commercial; STRUM's licence rests on a badge; SW has no licence. The tool stays free and non-commercial with attribution (§4.2). Not legal advice.
- **Training overlap inflates reference scores:** certain for STRUM guitar on 4 songs, probable for STRUM drums on 3, possible for ADTOF (custom charts) and autochart (undocumented).
- **Single points of failure:**
  - autochart has one maintainer, changes fast (148 commits in 30 days) and has only an internal job contract;
  - STRUM has been idle for 175 days;
  - the Beat This weights sit on a university server;
  - SW's original host is gone.
  - Mitigation: pin every file by hash, and mirror where the licence allows.
- **Nothing ran on Windows or on an RTX 4070.** Unverified: GPU speeds and VRAM, host RAM for any tool, PowerShell 5.1 behaviour, Inno Setup, WSL localhost forwarding (if WSL becomes the friend's route), Smart App Control, and autochart's GPU selection on Windows (a Windows Server CI runner timed out on the display adapter and used the CPU [doc]). The M1 spike, CI and M4 exist to catch these.
- **Host RAM.** STRUM's peak RSS is unmeasured; two runs died in a WSL VM reported at about 15.5 GB [reported in the practicality brief; not logged]. A 15-min song's six float32 stems alone take about 1.9 GB [here, critique]. Our pipeline peaked at 10.1 GB for its process tree on the 6:52 test song: allin1's runner 7.8 GB (all-in-one-infer, fold 0, CPU) while songcharter held 2.4 GB of audio, after 3.6 GB in the separation; 6.6 GB on the 4:01 Take Me Out, where autochart's engine reached 4.6 GB [here, pipeline run]. allin1 is the stage to shrink before M4 (a friend's PC with 16 GB has little margin on a long song) [inference].
- **Extra separation passes.** B1 always runs its own htdemucs_6s; it is not in the CPU estimates. allin1 takes our stems (§2.5).
- **Determinism across devices:** a GPU and a CPU, or two thread counts, can give a completely different guitar take; only cached tokens make re-runs reproducible. Fresh Demucs separations differ unless seeded (§2).
- **Evaluation validity:**
  - chart ground truth is good to about 15 ms;
  - F1 is fooled by the grid prior and by offsets;
  - six songs resolve only large gaps (0.05 needs 36, 51 or 151 songs, by tool pair);
  - the independent human ceiling is tentative;
  - the test-song proxies use two detectors whose offset to each other is unmeasured.
- **Clone Hero behaviour is unverified:** its hit window (often quoted as about ±70 ms), its treatment of `badSustainGap`, and fills inside star power.

---

## 8. Known limitations

### 8.1 Gaps not fully handled, and the plan for each

| gap | what happens today | plan |
|---|---|---|
| Songs above 185 BPM; picked 16ths (critique G1) | The level fold halves the tempo. Model sources keep their HOPO/strum intent (§2.6), but rule engines (`hopo=None`) turn 8th strums at a halved level into natural HOPOs. | M5: choose the metrical level together with note density (prefer the level where typical strums are ≥ 96 ticks apart); a forced-strum rule for rule engines; HOPO κ, natural vs source intent, in M2. |
| Compound meters and shuffles (G2) | Only octave moves, x/4 only (`TempoMap.from_beats` writes denominator 4); a 6/8 ballad's 16ths land 64 ticks apart. | M5: ternary-level test (inter-beat-interval ratios near 1.5), `TS 6 3` / `TS 12 3` and denominators in `tempo.py`; 6/8 and shuffle songs in the stress set. Until then, flag "check time signature". |
| Drumless songs (G3) | Designed (refine on bass/guitar onsets; a low-evidence flag instead of `beat_grid`'s `ValueError`; gate ADTOF mix hits by stem energy; omit absent parts). Built: the ADTOF engine's hat gate (G3, §2.9; untested on a drumless song), and the pipeline leaves out a part whose engine finds no note [code]. The rest is unimplemented and without thresholds. Inside a drummed song, drumless beats now follow a second stem calibrated on the same song (§2.3); a song with no drums at all still cannot calibrate the second stem. The −22 ms phase offset is calibrated on drums only. | Implement in M3; calibrate the offset for bass and guitar onsets; set thresholds on drumless stress songs in M5. |
| Fretformer driving (G5) | Level mismatch with autochart's grid untested; descriptor knobs (chords, HOPOs, speed) and the Fill-in model unused; a section that fails its checks is only flagged. | M2: ×1 vs ×2 level test, and 1 knob-conditioned take vs seeded takes. M5: regenerate failed windows. |
| Long songs, hidden tracks, long silences (G9) | Token-cap windowing is untested; the DP decoder carries beats through silence; `decode()` buffers the whole song through stdout. | Onsets outside a stem's activity are removed (§2.8); mid-song silences are open (§9, Q23); split long songs at silences or sections; a 12–15 min stress song with measured peak RAM (M5; M3 measured 10.1 GB for the process tree on the 6:52 test song, 7.8 GB of it allin1's runner). |
| Degraded rips and live recordings (G10) | Never measured. | Degraded versions of the references in the harness; live songs in the stress set (M5). |
| Packaging figures (G14) | The lock and sizes predate the final model set. madmom-infer and all-in-one-infer: wheel tags read (py3-none-any), Windows install untested; all-in-one-infer needs torchaudio listed explicitly (§4.3). | Re-lock and re-measure in M4. |
| ADTOF port provenance | Written from reading an unlicensed port of BY-NC-SA code; no provenance record. | A separate module treated as BY-NC-SA, or a G13-style record; ask xavriley for a licence (§4.2). |

The other critique gaps are designed in this version: G4 (§2.3, code change pending), G6 (§2), G7 (§2.9, §2.11), G8 (§2.11), G11 (§4.5), G12 (§3.3), G13 (§4.2), G15 (§2, §4.3), G16 (§2.10).

### 8.2 Unmeasured
- **Engine A (B2):** quality and speed on any whole song.
- **The pipeline:** on the other references (one so far, Take Me Out), with ≥ 3 guitar seeds, on a GPU and on
  Windows; a drumless, a long and a degraded song (M5's stress set).
- **Tempo:**
  - `beatgrid` beat F1 with `score.py` on the references (tonight's runs measured only the share of beats within 70 ms, on four songs; through the pipeline, Take Me Out alone: 0.962 [here, pipeline run]);
  - `beatgrid` with a Beat This start, and `track_beats` on Beat This activations;
  - v1's tempo prototype on the six references with `score.py`;
  - the offset between the guitar audit's and the drums/bass audit's detectors on the test song.
- **Drums and bass:**
  - pYIN re-laning of STRUM's bass;
  - any ADTOF lane mapper better than `drummap2`;
  - STRUM's GPU drum and bass charts of the references after our quantizer (its CPU charts of 3 songs were
    re-scored, §2.8, §2.9);
  - the de-duplicated drum fusion.
- **Scaffolding:** the star-power, fill and reducer rules on a real song checked by a person (the first-chart review
  checked them on the test song, but nobody has played the result); the allin1 ensemble on GPU (and any CUDA run of
  allin1); section quality beyond 5 references (4 of them unseen by allin1); 6s-folded vs ft stems beyond the test
  song.
- **Windows and hardware:**
  - any Windows run; RTX 4070 speed and VRAM; host RAM on the friend's PC (the pipeline's peak on the dev CPU:
    §5, M3), STRUM's peak RSS; the friend's RAM;
  - Smart App Control behaviour;
  - autochart's GPU memory; the 4-take CUDA default, its first-take-alone check and its time through the pipeline
    (only stand-ins ran it);
  - the work folders on Windows: path lengths on a real profile, and pruning that meets a file in use (a stand-in
    `PermissionError` only);
  - Beat This and packaging time on the 4070.
- **Clone Hero behaviour:** its hit window, `badSustainGap`, and fills inside star power.
- **Variance and references:** seed variance on the references (only same-seed GPU and CPU pairs exist); the independent human ceiling.
- **Inputs:** degraded rips and live recordings.
- **Listening and play:** nobody has listened to any output or played any chart.
- **Solos and strumming:** solo rules against more than 2 human solos; whether the test song's third "solo" is one;
  under-charting at the beat rate in the friend's sparse stretch (§2.7, §2.10).
- **Tests:** the repo's 472 tests ran for the pipeline's defaults: 469 pass, 3 skip (§2.0) [here].

---

## 9. Open decisions for the owner

| # | question | what it decides |
|---|---|---|
| 1 | **Which instrument(s) does the friend play?** **Answered: Guitar, on Expert** (his feedback on v1, which also asked for Expert only unless he asks for more, and for solo trackers; v1.1 and the pipeline's defaults follow it: §2.10, §2.11). | Which of M1a's rows are judged first (the v1 chart holds all three instruments, so whichever he plays can be playtested now; §5), the M2 order, and the priority of bass (§2.8). Blocks the most. |
| 2 | **Are non-commercial weights acceptable** (Fretformer 2, ADTOF; htdemucs_6s read as NC)? **Decided: yes** (the owner, 2026-11-02): the tool stays free and is never sold. | Whether Goal 2 has a measured-good route at all, and whether M2's engine work is needed. If not, guitar and drums have no measured engine today, and a rules route still needs a permissively licensed separator, which none of the sources found. Blocks the most. |
| 3 | **Decided: B1** (the owner, 2026-11-02). Which guitar route? **B2** (our own driver; songcharter stays MIT and uses no AGPL code), **B1** (autochart's engine as a separate program; we ship AGPL code with its source obligations, plus FFmpeg's LGPL), or **D** (build on autochart; songcharter becomes AGPL)? | §2.7, §4.2 |
| 4 | Must the friend's tool be native Windows, or is WSL2 acceptable? **Decided: WSL2** (the owner, 2026-11-03), after native Windows on 2026-11-02: the friend's PC has Smart App Control on, which blocks unsigned DLLs and Python modules. | §4.3, M4 |
| 5 | Will the friend play from the same MP3 file we chart? | M1a's gate; §2.1; otherwise verify sync against their copy |
| 6 | Should drum fills be charted (they need a fill detector) or omitted (then `noDrumActivationLanes` needs a gate exemption)? | §2.10, §2.13 |
| 7 | Should the provenance-unknown BS-RoFormer SW ever be offered as an opt-in download? | §2.2 |
| 8 | Lower-difficulty density: is the time-floor default (Harmonix-like at 142 BPM) enough, or should a denser, customs-like option be built? | §2.11 |
| 9 | Buy one month of Songsterr Plus ($9.99) for the hand-made tab of the test song, as a near-ground truth? | §3.3 |
| 10 | Will the repo be public and OSI-licensed (free SignPath signing), or private? Is the owner in the US or Canada (Azure Artifact Signing)? | §4.6 |
| 11 | Keep the `cu126` lane, or replace it with CPU plus an "update your driver" message? | §4.3 |
| 12 | What goes in `charter`? | §6 |
| 13 | May we email the Encore team and grow the reference set to about 50 songs? May community charts ever be used to train our models (M5)? | §3.3, M5 |
| 14 | Should we ask STRUM's author to add a LICENSE file? By default STRUM is a benchmark only; any shipped-STRUM route (a separate environment or WSL, after a LICENSE) is the owner's decision. | §2.8, §2.9, §4.2 |
| 15 | May we ask xavriley to add a licence to ADTOF-pytorch, and keep our ADTOF port as a separate module treated as BY-NC-SA? | §2.9, §4.2 |

**Open after the first-chart review** [here, review]. Each question comes from a review finding that survived
verification. "Contested" marks one that a verifier argued against; the fixer then re-checked which side held.

*Grid and quantizer*
- **Q16. Should the 1/24 and 1/32 grids come back for imported sources?** Contested; the refutation held, though
  the finding was right that minimum spacing is no reason to leave them out (§2.6). Keep them out (today): the tool
  sources barely write them (autochart on the test song: three 1/32s and no 1/24; STRUM cannot write 1/24), the test
  song would change by 1 note, and an ungated 1/32 level would keep STRUM's odd-1/32 rounding
  (§2.6). Bring them back: the human references use them (Creep 163 onsets on 1/24 positions, Lucretia 33 on 1/24 and
  109 on 1/32, Drunk Drivers 13), and without them Creep guitar loses 162 of 881 onsets; but those losses were measured
  with human charts as inputs, which are never quantizer inputs. **Recommendation:** keep them out; reopen when a
  source that writes them becomes an input (Engine A keeps its exact ticks anyway, §2.7).
- **Q17. M1's "more than 2 % of onsets moved by more than 25 ms": a gate error, a warning, or an M1 check only? And
  should spans where the source's beat period differs from ours by 1.5× or more be left out of the count?**
  Contested; the refutation held: §2.13's gate lists sync, scan-chart, the self-check and Encore's rules; the figure is
  §2.6's "would change it" trigger and an M1 check for `eval/m1_check.py`; and a warning would fire on every STRUM
  build, where moving STRUM's notes off its 1/32 rounding is what §2.6 asks for. Today each part's count goes to
  `report.json` (`moved_25ms`), information only. On the test song the second stem cut guitar onsets moved > 25 ms
  from 123 to 85 (80 outside the half-tempo stretches; 2 % is about 23), and autochart sits about 10 ms later against
  the audio in drumless stretches than elsewhere (−21.1 against −31.7 ms), so a count against autochart cannot reach
  zero. **Recommendation:** keep it out of the gate; `eval/m1_check.py` reports it per part, without the half-tempo
  spans.

*Reductions*
- **Q18. Drums Hard: kicks 1 beat apart (§2.11 drums step 5), or 8th-note kicks, as all four Harmonix Hards have (All
  the Small Things at 147.5 BPM included)?** Today Hard keeps half of Expert's kicks (human 0.745) and never reaches
  its 0.85 target. With 8th-note kicks: Hard F1 0.918 → 0.944 on the 4 Harmonix songs (both verifiers), and +6 kicks
  (STRUM) and +9 (ADTOF) on the test song, with no errors. Against: Take Me Out's human Hard has almost no sub-beat
  kicks, and Kimochi Warui's Hard would keep 0.984 of Expert's kicks. **Recommendation:** allow them. **Decided:
  allowed** (the owner, 2026-11-02; §2.11 drums step 5).
- **Q19. Should bass get ladder targets of its own?** Bass uses the guitar targets (0.78 / 0.50 / 0.30); human bass
  ladders average 0.889 / 0.609 / 0.453 (§2.11). The verifiers' what-if with denser bass targets: bass F1 Hard 0.872 →
  0.891, Medium 0.840 → 0.898, Easy 0.779 → 0.821; the test song's bass does not change (0.836 / 0.565 / 0.355 either
  way). A bass Hard must stay under the 0.90 `hardNotThinned` error, which 2 of the 4 human bass Hards reach. Also
  open: should bass Medium drop chords, and should the 2-beat Easy bass sustain floor come down? **Recommendation:**
  bass targets of their own, with Hard kept under 0.90; tune in M2. **Decided: bass targets of their own** (the owner,
  2026-11-02; §2.11 step 3). Bass Medium chords and the Easy bass sustain floor stay open for M2.
- **Q20. Easy drums: what decides a section's mode?** Contested; the refutation held. Today a section at or above the
  song's median drum-stem loudness is a two-hand beat and a quieter one a kick/snare beat (§2.11 drums step 7). The
  finding: that matches the human choice in 20 of 36 sections, and removed every kick from 10 of the test song's 19
  sections at the time. Against an Expert-groove rule: it is fitted in-sample, gets 4 of 10 Take Me Out sections right
  (loudness 6), and on the test song (1009 of 1194 non-snare hand gems are yellow) it would make nearly every section
  kick/snare, against "Easy must contain cymbals". A label-based rule needs section names in `reduce` and is also
  in-sample. **Recommendation:** keep loudness; test a loudness margin on held-out references in M2.
- **Q21. 5-fret time floors (Hard 160, Medium 300, Easy 500 ms; §2.11 step 2; see Q8): follow the human p5 gaps? And
  may the ladder apply a class partially or per section?** Contested; the refutation held against the proposed fix.
  The finding: the floors sit above the shortest Harmonix gaps, and whole-class thinning cannot land on the target.
  Against: 160 ms is about the mean human p5 Hard gap (162.75 ms guitar, 163.5 ms bass); a 140 ms Hard floor picks
  the 1/12-note step at 142 BPM and cuts the test song's bass Hard from 0.836 to 0.724; a 390 ms Easy floor drops Take
  Me Out's guitar Easy F1 from 0.736 to 0.582; a 150 ms floor gains on one song only (Lucretia); the partial-class
  ladder was never measured. **Recommendation:** keep 160 / 300 / 500 ms; measure a partial or per-section ladder in M2.

*Fills*
- **Q22. Should a crash be a hard rule for fills?** Today it is a preference, and `fillNoCrash` warns below half
  (§2.10). As a hard rule the ADTOF build loses nearly all its fills, and then its drum star power
  (`noDrumActivationLanes`): ADTOF writes the test song's crashes as hi-hats (3 green cymbals in its Expert), so 0.03
  of its fills end on a labelled crash, against 0.34 for STRUM (the Harmonix test references: 0.63–1.00).
  **Recommendation:** keep it a preference, and fix crash labels in the drum lane mapper (M2).

*Silence*
- **Q23. Onsets in a silence inside the song: remove them, and from what length?** The edges are decided: onsets
  before a stem first plays or after it last plays are removed (§2.8). Inside the song they are only warned about.
  Options: remove those inside a stem silence of at least N s (the critique's "about 4 s", untested), or none, with a
  per-part cut-off key. Measured so far: only the edge rule on the test song (2 trailing bass notes; 25 and 30 dB give
  the same trim). **Recommendation:** keep warnings until the stress set (M5) sets N.

**Open after the engine builds** [here, drums, bass and sections engine runs]. Each comes from a builder's report or
a review of its engine.

*Drums*
- **Q24. G3's reading: is the wide "the stem plays around it" gate (±0.5 s, 40 dB) right, or should a hit need the
  stem's own hat?** The per-hit reading costs the test song a quarter of its hats (289 of 1144, all in drummed
  passages; §2.9). **Recommendation:** the wide gate, plus the absent-part rule for wholly drumless songs; test both
  on a drumless song in the stress set (M5).
- **Q25. Should the ADTOF engine move a colliding tom to a free tom pad, as `quantize.py` does, instead of dropping
  it** (Kimochi Warui: 82)? It belongs to the M2 lane-mapper experiment.
- **Q26. Should the build's own grid period reach the ADTOF engine as `beat_s`?** Ride or crash moves green F1 by up
  to 0.06 with a 2.4 % tempo change (§2.9). Not wired: the pipeline runs the engine before assemble builds the grid,
  so this needs the grid built before the engines. Open; measure in M2.

*Bass*
- **Q27. A merge in a single-note part:** keep the union of frets (today: chords on bass, against §2.8's "no chords"),
  or keep one note (the earlier onset's lane) for parts whose source writes no chords? Needs a part flag in assemble
  and a quantize rule. **Recommendation:** keep one note; re-score the five references. The engine writes single
  notes by design, so a single-note flag would only remove quantizer merges. It does not make "bass has no chords"
  true: one of the five human references charts about 41 % of its Expert and Hard bass onsets as chords, so no chords
  is a style choice, not what the references show. Matching those chords would need real chord detection, outside
  this engine.
- **Q28. Bass sustains:** the pitch-hold rule gives a sustain share 0.18 after quantizing against the human 0.20, but
  per song 0.27 vs 0.10 (Take Me Out) and 0.11 vs 0.43 (Creep). Keep it, or apply v1's gap rule (sustain when the gap
  to the next note is ≥ 0.75 beat) in the quantizer for rule sources? M2.

*Sections*
- **Q29. allin1 on CUDA: the 8-fold ensemble (the code's default) or fold 0?** After the rules the ensemble measured
  no gain over fold 0 (−0.004 at ±3 s, CI [−0.07, +0.05]); its raw boundaries are slightly better (+0.05, CI
  [+0.006, +0.096]); the CUDA path is untested (§2.5). The solo evaluation adds one song's evidence for fold 0: with
  the solos default ("labels") the ensemble misses the test song's Solo 1 entirely (it calls it Chorus 2B) and makes
  4 false solos on the references against fold 0's 2 (§2.10) [here, solo evaluation; the ensemble as allin1 1.1.0 on
  the CPU]. No recommendation until it has run on a GPU.

*Pipeline* [here, pipeline run]
- **Q30. Where does the pipeline's work folder belong?** **Answered** (the owner: "do what you think is best"): in
  the per-user cache, one folder per song file, `%LOCALAPPDATA%\songcharter\work\<name>-<key>` keyed by the first 16
  hex characters of the file's SHA-256 (not by the decode: a key the pipeline has before it decodes), autochart's
  scratch apart in `%LOCALAPPDATA%\songcharter\ac\<8 hex>` for Windows' path limit, the least recently used pruned
  after each run to 5 GB, and `--work` kept for the command line (`cache.py`; §2, work folder). The question as it
  stood: it defaulted to `<out>.work` beside the output, as M3 asked. It holds the decode, the stems (0.8 GB for the
  test song) and every engine's folder, and autochart's takes are complete song folders (`notes.chart`, `song.ini`,
  `song.ogg`); the ADTOF folder holds a chart and an ini. With the output inside Clone Hero's Songs folder, Clone Hero
  would list them as songs [inference; untested in Clone Hero].

Decided by the code since the review, and recorded in their sections: the second-stem grid and the local tempo
periods (§2.3), the odd-1/32 rule (§2.6), the Medium tom/crash and slow-Easy hi-hat rules (§2.11), fills every 4
measures (§2.10), the edge trimming (§2.8), and scan-chart in the gate with the `<output>.failed` folder (§2.13).

**Information to collect at the M1 spike:** `nvidia-smi --query-gpu=name,driver_version,compute_cap --format=csv` on the friend's PC; its RAM; the Smart App Control state.

---

## 10. Sources

**Format and validation**
- Clone Hero wiki: https://wiki.clonehero.net/books/clone-hero-manual/page/adding-custom-songs, https://wiki.clonehero.net/books/guides-and-tutorials/page/songini-guide, https://wiki.clonehero.net/books/clone-hero-manual/page/chart-previews-via-the-command-line
- GuitarGame_ChartFormats (.chart): https://github.com/TheNathannator/GuitarGame_ChartFormats
- scan-chart: https://github.com/Geomitron/scan-chart (npm 8.0.1; vendored in `tools/scan-chart`)
- YARG.Core: https://github.com/YARC-Official/YARG.Core
- Moonscraper: https://github.com/FireFox2000000/Moonscraper-Chart-Editor
- SNG format: https://github.com/mdsitton/SngFileFormat

**Charting conventions**
- Encore guidelines: https://docs.google.com/document/d/1XrLKnpL0xawaC90M4lLnhqhExwXM_3JpJnzNqlB_agM
- CSC: https://customsongscentral.com/monthly-pack-submission-guidelines/, https://customsongscentral.com/diff-guitar/
- RBN/C3 rules (Customs Book): https://rhythmgamingworld.com/?p=605284
- Onyx: https://github.com/mtolly/onyx
- midi-ch: https://github.com/EFHIII/midi-ch

**Test song and references**
- https://en.wikipedia.org/wiki/How_to_Leave_Town
- https://open.spotify.com/track/6n3Axk0f9yRo3v6PNolCbk
- https://musicbrainz.org/recording/fbead628-396a-4ad5-9fb6-131b01eef2de
- Songsterr tab: https://www.songsterr.com/a/wsa/car-seat-headrest-beast-monster-thing-love-isnt-love-enough-tab-s597991
- Encore: https://api.enchor.us/search/advanced, https://files.enchor.us/
- Encore request body reference: https://github.com/elicwhite/spotify-clonehero

**Timing and sections**
- Beat This!: https://github.com/CPJKU/beat_this, https://arxiv.org/abs/2407.21658
- all-in-one: https://github.com/mir-aidj/all-in-one; all-in-one-infer: https://pypi.org/project/all-in-one-infer/
- madmom-infer: https://pypi.org/project/madmom-infer/
- SongFormer: https://github.com/aslp-lab/songformer
- librosa: https://librosa.org; mir_eval: https://github.com/craffel/mir_eval

**Separation**
- Demucs (README lines 321–325 on the weight licence): https://github.com/adefossez/demucs
- MVSEP leaderboards: https://mvsep.com/quality_checker/leaderboard/guitar/?sort=guitar
- SW provenance discussion: https://github.com/ZFTurbo/Music-Source-Separation-Training/issues/248
- Mega 53-stem release: https://github.com/ZFTurbo/Music-Source-Separation-Training/releases/tag/v1.0.21
- python-audio-separator: https://github.com/nomadkaraoke/python-audio-separator

**Transcription and auto-charting**
- autochart / Fretformer 2: https://github.com/dvar0/autochart (pinned `b5a41e8` in `eval/tools/autochart/setup.sh`), https://huggingface.co/Dvaro/autochart-models
- STRUM: https://github.com/opria123/strum (pinned `9f420cb`), https://arxiv.org/abs/2605.12135
- chartgen: https://github.com/Mechazawa/chartgen (pinned `383d50c`)
- ADTOF: https://github.com/MZehren/ADTOF (CC BY-NC-SA 4.0, code included), https://github.com/xavriley/ADTOF-pytorch (no licence stated)
- ADT_STR: https://huggingface.co/Pierfrancesco/adt-str
- basic-pitch: https://github.com/spotify/basic-pitch

**Evaluation**
- ChartGenEval: https://arxiv.org/abs/2607.12857
- Harmonix Set: https://github.com/urinieto/harmonixset

**Packaging**
- PyTorch release notes and wheels: https://raw.githubusercontent.com/pytorch/pytorch/main/RELEASE.md, https://download.pytorch.org/whl/torch/
- CUDA release notes: https://docs.nvidia.com/cuda/cuda-toolkit-release-notes/index.html; CUDA on WSL: https://docs.nvidia.com/cuda/wsl-user-guide
- uv: https://github.com/astral-sh/uv, https://docs.astral.sh/uv/guides/integration/pytorch/
- Inno Setup: https://jrsoftware.org/isinfo.php
- Code signing: https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/code-signing-options, https://signpath.org/terms

**In this repository**
- `songcharter/`: `audio.py`, `tempo.py`, `chart.py`, `ini.py`, `package.py`, `timed.py`, `beatgrid.py`, `importers.py`,
  `quantize.py`, `reduce.py`, `starpower.py`, `sections.py`, `separate.py`, `takes.py`, `assemble.py`, `pipeline.py`,
  `cli.py`; `engines/`: `autochart.py`, `adtof.py`, `drumlanes.py`, `bass.py`, `sections.py`, `allin1_runner.py`
- `tests/`: `test_tempo.py`, `test_chart.py`, `test_package.py`, `test_beatgrid.py`, `test_importers.py`,
  `test_quantize.py`, `test_reduce.py`, `test_starpower.py`, `test_sections.py`, `test_separate.py`, `test_takes.py`,
  `test_assemble.py`, `test_engines_autochart.py`, `test_engines_adtof.py`, `test_engines_bass.py`,
  `test_engines_sections.py`, `test_pipeline.py`
- `eval/`: `scorer/score.py`, `scorer/scan_notes.cjs`, `scorecard.py`, `drive.sh`, `gpu.sh`, `build_refs.sh`, `refs.json`, `refs/`, `tools/{autochart,chartgen,strum}/` (including `tools/autochart/ac_headless.cjs`)
- `tools/scan-chart/scan.cjs`

**Research documents** (outside the repository; see the table at the top): v1 and its nine research reports with their prototypes (`tempomap_proto.py`, `adtof.py`, `drummap2.py`, `fretmap2.py`, `fretformer_driver.py`, `separation.py`, `sections_proto.py`); the critique and its scripts; the comparison report and its four audits; the ADTOF test; the build checks (beatgrid run, importer check, quantizer check).

---

## 11. Changes from v1

| area | v1 | v2 | why |
|---|---|---|---|
| scope | one tool | two goals; Goal 1 is a merge build of existing tool outputs, gated on which instrument the friend plays | [decision], reversing the comparison's quick route A′ (§1 gives the reasons); comparison §7.1 and §7.4 for the two goals and the gate |
| architecture | stages write ticks | every source returns a `TimedSong` in seconds; only the quantizer writes ticks; two named clocks (unpadded seconds, padded ticks) | `timed.py`; `quantize.py`; no note timed by another tool's map |
| ffmpeg | wheel on Windows | bundled ffmpeg pinned, PATH ignored | critique E12; `audio.py` 27–36 |
| stem cache | FLAC, keyed by the mix | float32 WAV/NPY, keyed by mix, model, parameters, seed and code version | the decode peaks at 1.123 (E12); stale stems after a model change |
| determinism | fixed seeds | plus Demucs's random shift seeded or `shifts=0` | demucs 4.1.0 `apply.py` line 245 [here] |
| stem-lag gate | refuse any lag ≠ 0 | median \|lag\| ≤ 2 samples, correlation floor, skip quiet stems, warn and re-separate | E6 |
| SW | opt-in | not in this version | no licence, disputed origin, CPU cost |
| Demucs weights | "not clear" | treated as non-commercial; downloaded at first run, never bundled | Demucs README vs autochart's notices (C9) |
| tempo | Beat This + level fold + DP + p95 mode test + LOESS | Beat This proposes, `beatgrid` refines on drum (or bass/guitar) onsets; free at ≥ 60 % evidence; max and longest-run checks; free islands; octave control; `tolerance=0.003`; `start=` path needs code changes | C6, C7, G3, G4; the test song's drummer misses a straight line; `beatgrid.py` |
| grid phase | no constant offset | the offset belongs to the detector: −22 ms from `beatgrid`'s envelope peaks, drum stems only | C8 |
| meter | Viterbi x/4 | the Viterbi decides; the kick phase and `beatgrid`'s uncertainty flag drive review; 6/8 in M5 with `tempo.py` denominators | G2; kick-on-1 wrong on 2 of 4 references [here, beatgrid run] |
| sections | fold 0, cited at 0.740 / 0.596 / 0.730 | that figure is the 8-fold ensemble, in-domain; ensemble on GPU, fold 0 on CPU, chosen in M2; Goal 1 from the tools' agreement; 20–30 sections kept | E7 |
| snap grid | straight {1/8, 1/16, 1/32} and triplet {1/12, 1/24} families | 1/16 + 1/12 only, a 1/32-grid source's odd 1/32s to the coarser slot; Engine A keeps its exact ticks through a flag | `quantize.py` (drums snap to 1/16 plus triplets, the sources barely write 1/32s or 1/24s, and a 1/32 level would keep a 1/32-grid source's rounding; spacing is not the reason: a 1/32 is under the 55 ms HOPO spacing only above 136 BPM) |
| HOPOs | natural only, drop every `N 5` | keep the source's intent and write `N 5` flips; unknown where the source's tempo level was wrong (to add to `quantize.py`); below Expert, `reduce.py`'s strum rule | G1, C10; quantizer check |
| guitar engine | Engine A default, justified by autochart's numbers; 3 takes; repeat-consistency selector | Engine A unmeasured; B1 / B2 / D open, benchmarked over ≥ 3 seeds; 1 take by default with cached tokens; token-cap windows; pickups fed; autochart's sampling settings by default | E1, E2, E5, G5, G6, C1 |
| guitar run time | "a few minutes on a 4070"; ≤ 5 min target | about 3.2 min of decoding per take on the 5070, GPU barely helps; target ≤ 8 min, estimated per route (B2 about 3–7, B1 about 5–7) | E1, C2 |
| bass | rules by default (0.863) | Goal 1 STRUM + pYIN; Goal 2 our rules, STRUM a benchmark only; pYIN budget 20–50 s | E4, E10, C5; practicality audit |
| drums | ADTOF fusion "good" (0.844) | whole songs: ADTOF better pad-blind onsets and kicks (not like for like), STRUM better lanes; Goal 1 STRUM; Goal 2 ADTOF plus a new lane mapper, STRUM never shipped; collisions resolved by moving or dropping the tom; 0.813 held-out | E4, ADTOF test, C3, C4, C13, G7 |
| star power and fills | activation lanes per song | `S 64` on every drum difficulty with a target count; lanes first, then star power; drums may get fewer phrases; solos on every guitar difficulty | E11, G16 |
| reductions | greedy padding with Standard/Dense presets and +8 inside star power (Hard kept 97–100 %) | time-floor gaps; a thinning ladder; lanes re-limited before chords; drum hand-pad padding; drum SP coverage; error at Hard ≥ 0.90 of Expert, warning bands | E3, G7, G8, C11; `reduce.py` |
| sustain floor | max(200 ms, 0.5 beat) | max(200 ms, 0.75 beat) on Expert and Hard; Easy 1.25 beats (2 on bass) | E9, C12; `reduce.py` |
| evaluation | absolute M2 targets | one set of per-song non-regression rules with run-to-run tolerances; absolute targets as information until 36, 51 or 151 songs (by tool pair); ≥ 3 seeds; Lucretia separate; post-2026-10 charts by `modifiedTime` and `versionGroupId`; copies screened by κ; Neversoft as a tentative ceiling | comparison; G12; E8 |
| milestones | CLI → harness → UI → Windows → quality | Goal 1 for the friend's instrument(s) + Windows spike (M1a), other instruments (M1b) → evidence (ordered and conditional on the owner) → pipeline → release (with v1's UI checks) → quality | C16; comparison §7.5 |
| packaging | installer in M4 regardless | after the spike; native vs WSL is the owner's call; re-lock with a Windows-wheel check; GPU memory freed and fallbacks shown; non-reserved workspace names; quick fixes that recompute bar-line features; Smart App Control steps; diagnostics; NOTICE; Node per route | G11, G13, G14, G15; practicality audit |
| STRUM licence | "MIT, untested" | "MIT" has no LICENSE file behind it; nothing of STRUM is vendored or shipped | practicality audit |
| ADTOF licence | weights CC BY-NC-SA 4.0 | weights BY-NC-SA by inheritance (host states none); the port's code licence uncertain | ADTOF and ADTOF-pytorch repositories [doc] |
| test-song facts | from excerpts | drum and bass entries and ends, tool outputs and their faults, section agreement, `beatgrid`'s whole-song result, decode length 412.363 s | comparison audits; build checks |
| new sections | — | code status and design-vs-code decisions (§2.0), how results gate decisions (§3.2), first engineering tasks (§5.6), known limitations (§8) | the brief; the checkers' reviews |
| paths | scratchpad paths | repo files or named research documents only | repo-ready |

**Kept out of v2 on purpose:** v1's +8 star-power priority (replaced by the coverage step), the Standard/Dense
presets (replaced by time floors), the 1/32 and 1/24 grids (the sources barely write them, and a 1/32 level would keep
a 1/32-grid source's rounding; open for imported sources, §9 Q16), kick-locked downbeats for Goal 2 (the Viterbi
decides), and the p95-drift click test (critique G4).

**Changes after the first-chart review** (`main` at e0e4b7e):
- **Beat grid:** the internal tracker follows local 20-s tempo periods, and `stats["tempo_check"]` flags missed
  changes (Take Me Out within 70 ms: 0.836 → 0.986). Drumless beats of a drummed song follow a second stem calibrated
  on the same song (§2.3).
- **Quantizer:** the 1/32 and 1/24 rationale is corrected (spacing is not the reason); a 1/32-grid source's odd 1/32s
  go to the coarser slot; assemble keeps only a source's forced HOPO states by default; notes moved more than 25 ms
  are counted, information only (§2.6).
- **Reductions:** on Medium at ≥ 140 BPM a tom or crash outside activation lanes keeps 1 beat, like the hi-hat; on
  Easy at ≤ 120 BPM a hit of only hi-hat or ride may sit half a beat from another hand hit (§2.11).
- **Fills:** one every 4 measures of drumming; a crash is a preference, with a `fillNoCrash` warning (§2.10).
- **Sections:** merge, then split, per run of one label; 26 on the test song (§2.5).
- **Assembly and gate:** onsets outside a stem's activity are trimmed (§2.8); real scan-chart 8.0.1 gates every build
  where node is present; a failed build goes to `<output>.failed`; an output folder with foreign files is refused;
  stricter config checks; CLI exit codes 0–3 (§2.0, §2.13).
- **Guitar:** the v1 chart's guitar is spliced from four autochart takes by per-section agreement (§2.7).
- **Owner questions:** eight new ones from the review (§9, Q16–Q23).

**Changes after the engine merge and the pipeline** (`main` after the merges of `engine-drums`, `engine-bass` and
`engine-sections`, and the pipeline commit):
- **Engines:** `engines/adtof.py` and `engines/drumlanes.py` (drums: ADTOF's Frame_RNN as our own PyTorch module, the
  fusion with the G3 hat gate read as the wide gate, drummap2's lanes, 2x kicks; it reproduces the ADTOF test's
  charts and scores; after our quantizer 0.962), `engines/bass.py` (the bass rules on whole songs: after our
  quantizer F1@50 0.800, κ 0.612), `engines/sections.py` and `engines/allin1_runner.py` (allin1 in its own Python,
  fed our stems, or librosa; fold 0 0.718 against librosa 0.524 at ±3 s on five references) (§2.0, §2.5, §2.8, §2.9).
- **Pipeline:** `songcharter chart <file> --out <dir>` (`pipeline.py`), M3's scope, run end to end on the test song
  (12.7 min on the dev CPU, gate OK) and on Take Me Out (Expert F1@50 guitar 0.909, bass 0.912, drums 0.944; beat F1
  0.962) (§1, §5 M3).
- **Decided by the builds:** allin1 takes our stems, so there is no extra separation for sections (§2.2, §7); allin1's
  weights are tagged MIT and pinned (§4.2); all-in-one-infer installs from pure-Python wheels but needs torchaudio
  listed (§4.3).
- **Owner questions:** seven new ones (§9, Q24–Q30).

**Changes after the review of the integrated pipeline** (`main` after 54b063e):
- **Errors and exit codes:** the errors a user can act on are `errors.InputError` and `errors.ToolError` (also a
  `ValueError` and a `RuntimeError`). Exit 2 is these and `OSError`, so numpy's or torch's own `ValueError` or
  `RuntimeError` inside an engine is a bug (exit 3, traceback printed) instead of "bad input" with one line;
  `pipeline.json` keeps every error's traceback. A timed-out autochart run is a `ToolError`. The beat grid's tempo
  estimate no longer fails on audio under a second (numpy's `mode="same"` returns the kernel's length) (§2.0).
- **Devices:** device auto takes CUDA only when a CUDA kernel runs, for separation, ADTOF and autochart alike, so a
  GPU the torch build has no kernels for gives a CPU run with a warning instead of a failure at separation;
  `--device cuda` is checked the same way before any audio work. For `--device cuda` allin1 is asked for auto, so an
  allin1 Python without CUDA runs allin1 on the CPU (warned) rather than the librosa fallback (§2.0, §2.5).
- **Sections need librosa** whether allin1 is set up or not: it is allin1's fallback. allin1 failing without librosa
  is an error naming both, not librosa's ImportError from inside the fallback (§2.0).
- **Guitar takes** are keyed by the install too (`take.json`), so an updated engine, model set or driver runs them
  again; a take from before this change runs once more (§2.0).
- **Memory record:** `pipeline.json` no longer reports `RUSAGE_CHILDREN`, which is never below songcharter's own peak
  at the spawn (the test song's warm re-run recorded a 2.2 GB "child" where the only child, allin1's probe, peaked at
  0.6 GB); allin1's runner reports its own peak (§2.0).
- **Tests:** the pipeline's stand-ins check the exact arrays each engine gets and key their stems by the mix; new
  tests chart a second song into the same folders, leave out a repeated take with `--takes 4`, pass `--device cuda`,
  meet CUDA that does not run and a busy `<out>.failed`, and raise numpy's and torch's errors and a failing
  component. Each of 25 mutations that undo a fix or slip a wire (the review's seven survivors among them) fails a
  test [here]. A passing test's temporary folders are deleted at once (§2.0).
- **End to end:** the test song charted again gives byte-identical engine charts, take and `notes.chart`, and passes
  the gate (§5, M3).

**Changes for the pipeline's defaults** (branch `pipeline-defaults`, on `main` at 7172d80):
- **The end of the audio:** `noteAfterAudio` is our own gate rule (scan-chart 8.0.1 measures no audio). assemble now
  clips every taken level 1 ms inside song.ogg's end (`clip_to_audio`), with the counts in report.json; the 35-s
  excerpt that failed it passes, and so does a new 35-s cut of Take Me Out inside a long guitar sustain (1 Expert
  sustain clipped, guitar ending 1.8 ms before song.ogg) [here] (§2.13).
- **Levels:** Expert only by default, on the friend's feedback (§9 Q1 answered); `--levels expert|all|LIST` (§2.11).
- **Solos:** `--solos labels|stems|off` or section names, `--solos "Solo 1,Solo 2"`. The default is **"labels"**,
  every section allin1 labels Solo, from the solo evaluation: "stems" (the label and the stem test together) placed
  no solo on the test song, rejecting both solos the friend confirmed (vocals shares 0.561 and 0.863), where "labels"
  covers Solo 2 and half of Solo 1 with fold-0 sections (the CPU) and Solo 2 alone with the ensemble (CUDA); on the
  six references both find 1 of 2 human solos, "labels" with 2 false solos to 1 on fold 0 and 4 to 1 on the
  ensemble. No new mode: the union of the two only adds false solos (§2.10).
- **Guitar takes:** 4 by default when the guitar stage runs on CUDA, 1 on the CPU; the first CUDA take alone first,
  that take alone when autochart moved its transcriber off CUDA; `--takes N` as asked on any device. The takes
  experiment behind it is in §2.7, with its verifier's two corrections (3 takes give +0.006 to +0.0105 over one, not
  less; 4 beat 3); `guitar_takes`'s docstring no longer says 3 takes score below 1.
- **Strumming:** the under-charted-strumming detector failed (held-out precision 0.22, no better than an audio-free
  rule, 16ths 0/22) and no fill was built; in the friend's sparse stretch the guitar pulses at the beat rate (§2.7).
- **Preview:** written into `work/preview/` after every build, when matplotlib and librosa import; it never changes
  the exit code; `--no-preview` (§2.0).
- **Work folder (§9 Q30, answered):** `<cache>/work/<name>-<key>` in the per-user cache, autochart's scratch in
  `<cache>/ac/<8 hex>` to keep the files it leaves under Windows' 260 characters (not its staging files, which only
  Node writes), the least recently used pruned to 5 GB; `--work` as before
  (`cache.py`; §2, work folder). A fix on review: a default run on a folder a `--work` run had pinned unpinned it,
  and the `--work` run dropped its scratch folder from the marker; both now keep what the marker held (tested).
- **Summary:** the CLI's guitar line says where the solos went (`, 3 solos (167.3-180.7, ...) s` or `, no solo`).
- **Runs** [here, pipeline-defaults runs; §5 M3]: Take Me Out with the defaults on its warm work folder (exit 0,
  Expert only, 1 take with its reason recorded, gate OK, preview 5 pages, nothing flagged; 300 s, the guitar take
  ran again), then with the final defaults on a copy (61 s, every engine cached, 1 solo at 191.5–205.0 s, a false
  one); a 35-s excerpt (gate OK, nothing to clip), a 35-s cut inside a sustain (1 clipped, 1.78 ms before the end)
  and the excerpt with the work folder in the cache (`work/tmo_excerpt-d1004c46f2e46f3c`, 101 MB with its
  scratch); the test song with the final defaults (exit 0, gate OK, Expert notes identical to M3's, 3 solos:
  167.3–180.7, 235.0–258.4 and 317.8–361.7 s; 15.9 min with separation and every engine run again).
- **Tests:** 39 mutations of the new code (the clip, levels, solos, takes, the preview, the cache, the pruning), each
  failing a test [here]; then tests for the solos default through the CLI (a sung "solo" section gets a solo, and
  none with "stems"), the summary's solo line, and a pinned folder staying pinned with its scratch folder; the CLI
  default back to "stems", the pin dropped and the scratch dropped each fail a test [here].


**Fixes after the review of `pipeline-defaults`** [here, defaults review; each finding reproduced by a verifier]:
- **Ctrl+C after the build:** a Ctrl+C during the preview or the pruning, after assemble had put the build in place,
  exited 130 ("interrupted", the output "as it was"), lost the summary (and with it the `.failed` path) and skipped
  the pruning. Now it stops only that stage, with a warning ("no preview: interrupted", "the cache ... was not
  pruned (interrupted)"), and the run ends 0 or 1 as the gate says, with its summary; 130 now means interrupted
  before the build was in place (§2.0, cli).
- **Solos without the guitar:** `--solos stems` or section names with `--instruments drums,bass` were dropped
  without a word; they are refused (exit 2) as `--takes 3` is. The default "labels" and "off" stay silent.
- **The summary's scratch folder:** named only when the run made it (a run without the guitar makes none); the
  marker and `pipeline.json` keep its path, so a later guitar run's folder is still found by the pruning.
- **A prune that stops partway** (a file in use, a Ctrl+C) deleted a work folder file by file and could leave a
  stems `info.json` beside missing stems, which every later chart of that song then failed as a bug (exit 3). Each
  folder now goes whole into `<cache>/trash` in one rename before it is deleted, what is left there goes with the
  next prune, and the separation cache counts a folder with a missing or unreadable stem as a miss (§2, work
  folder; §2.2). Verified with the stand-in engines and the real separation cache code, NTFS's name order imitated
  and the file in use emulated both ways (its unlink failing; its folder's rename failing, as on Windows): every
  re-chart exits 0 [here]. The rmdir-only failure (the marker already gone, the folder never retried) is gone with
  it: the empty folder waits in the trash.
- **A run that starts while a prune deletes:** the marker is read again before each move and after it, so a run
  that marked its folder after the scan keeps it; two real processes, B marking while A deletes an older folder
  and just before A moves B's, both gave B exit 0 with its folder whole [here]. Left open: a run whose folder is
  moved between its `mkdir` and its first marker write (microseconds) still fails, exit 2.
- **Path lengths:** `cache.DEEPEST` and its test now include autochart's staging files, past 259 on every profile
  (309 with a 20-character profile name), which only Node writes; pruning deletes in Windows' `\\?\` form
  (`cache.long_path`). Neither is tried on Windows.
- **The solos decision's cost** is given per sections source: one extra false tracker every six songs on fold 0,
  about every two on the ensemble the friend's CUDA runs, which also misses Solo 1 (§2.10, §9 Q29); the pipeline's
  docstring and the summary above say which sections they mean.
- **Docs:** M1a's status and the stage overview's bass row no longer call Q1 open; the strumming section quotes the
  friend's 2:32–2:35 and gives the window on both clocks; `stem_confirm`'s thresholds are "never tuned", not
  "untested"; the `--work` help and the pipeline's docstring name `$XDG_CACHE_HOME`; the tests row counts main's
  428 tests.
- **Tests,** each failing without its fix (19 mutations, every one failing a test [here]): Ctrl+C in the preview
  and in the pruning (exit 0 and 1); a prune that raises `PermissionError` (exit 0, one warning); solos without the
  guitar refused; the summary without a scratch folder; the stand-in guitar keeping 3 MB in its scratch folder, so
  the work folder's size must count it, and devices shaped like autochart's real summary (`demucs` and `timing`
  None) with three probe cases (demucs on the CPU, no devices, empty devices: 4 takes each); a matplotlib that
  raises a non-`ImportError` on import (one warning, exit 0); the clip clause of the summary's part line; refused
  runs on a song new to the cache making no folder there (the `<out>.work` checks, which could not fail, removed);
  the prune's move, re-reads, trash and sweep; a separation cache with a stem missing or cut short; the home
  folder test setting `USERPROFILE`, which Windows' `Path.home()` reads instead of `HOME` (it failed under
  Windows' lookup, emulated, and passes with it) [here].

**Golden charts** (branch `golden`, on `main` at 11615e2) [here, golden runs]:
- `eval/golden.py` (`run`, `diff`) and `tests/test_golden.py`; `eval/scorer/scan_notes.cjs` prints each track's
  `calculateTrackHash` and finds scan-chart beside `$SONGCHARTER_SCAN_CHART` (§3.6).
- The release gate (`CLAUDE.md`) and the inspector (`.claude/agents/sc-inspector.md`) name the commands;
  `eval/README.md` says how to run them.
- Tests: the hash (the same notes give the same hash; one changed fret, tick, sustain or star-power phrase changes
  that track's hash only), `--expect`, the diff's statuses, tables and exit codes, and `run`'s kept and private
  folders with stand-ins for the build, scan and scorer (two runs at once, a build writing into a linked stem
  caught). 35 mutations of `golden.py` and one of `scan_notes.cjs` (a constant hash), each failing a test.

**Fixes after the review of `golden`** (four findings; a skeptic reproduced both majors):
- **G1:** the gate reran engines in the new run only, so the old side's came from the kept folders' commit while the
  summary named the old commit: a reverted bass change passed as "identical". Now `--rerun` goes to both runs (the
  gate, the inspector and eval/README say so, with the cost), `diff` fails when the two runs reran different engines
  or when an engine not rerun no longer matches the kept folders' code (`run` checks it with git), and names the
  engine and the kept commit above the verdict (§3.6).
- **G2:** a refused, failed or killed run left the earlier `summary.json` in `--out`, which a diff could pass. `run`
  now clears the folder first, and the gate's commands are chained with `&&` after a `rm -rf`.
- **G3:** without `SONGCHARTER_ALLIN1_PYTHON` the sections fell back to librosa unasked and every part's hash moved
  against the baseline. An engine that runs without being asked now stops the run (exit 2), naming the variable, and
  `diff` fails on sections from different backends.
- **G4:** bad input that is not one of golden's own refusals (an `--out` that is a file) exits 2, and a bug 3.
- Tests: each fix has one that fails without it (16 mutations of the fixes, each failing a test) [here].
