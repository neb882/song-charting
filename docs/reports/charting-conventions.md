# Charting conventions for 5-fret games, and where songcharter differs (2026-11-05)

A research pass for M5, read-only, on the owner's request that the next version rest on how charts for these games are supposed to be made. Paths under `/tmp/claude-0/…/scratchpad` name the session's own scratch files.


*Research brief for the M5 plan, 2026-11-05. The repository was only read. No song's lyrics were looked up or quoted.*

## How to read this

The tags below say how strong each statement is.

- **Enforced by the game**: Clone Hero or YARG plays the chart differently because of it. This is from their docs or source.
- **Lint**: scan-chart 8.0.1 flags it, or Chorus Encore requires it. The game itself does not care.
- **Convention**: charters follow it by taste. Encore's reviewers and players judge it.
- **[recall]**: I know it from the community but could not re-read a primary source in this session. It is a lead for the planner to check, not evidence.

**Priority** means:

- **high**: it hurts play, or looks wrong to any player;
- **medium**: a careful player notices it;
- **low**: polish.

### Sources I read

- **GuitarGame_ChartFormats** (GGCF), the community's format reference. Site: https://thenathannator.github.io/GuitarGame_ChartFormats/ (cloned from https://github.com/TheNathannator/GuitarGame_ChartFormats). Page paths are given as `GGCF <page>`.
- **scan-chart 8.0.1 source**, in `tools/scan-chart/node_modules/scan-chart/src/`. Upstream: https://github.com/Geomitron/scan-chart
- **YARG.Core source**: https://github.com/YARC-Official/YARG.Core
- **The Clone Hero wiki** (CH wiki):
  - https://wiki.clonehero.net/books/clone-hero-manual/page/how-to-play
  - https://wiki.clonehero.net/books/general-info/page/dictionary
  - https://wiki.clonehero.net/books/guides-and-tutorials/page/custom-content
  - https://wiki.clonehero.net/books/guides-and-tutorials/page/songini-guide
- **Chorus Encore Application Guidelines** (Encore): https://guidelines.enchor.us/, which opens https://docs.google.com/document/d/1XrLKnpL0xawaC90M4lLnhqhExwXM_3JpJnzNqlB_agM
- **Custom Songs Central's diff_guitar rubric** (CSC): https://customsongscentral.com/diff-guitar/
- **Editor on Fire's manual and tutorials** (EOF): https://github.com/raynebc/editor-on-fire, files `bin/manual/functions.htm`, `bin/tutorial/index.htm` and `bin/vocaltutorial/index.htm`
- **midi-ch's checks**: https://github.com/EFHIII/midi-ch (README)
- **FireFox's .chart specification**: https://docs.google.com/document/d/1v2v0U-9HQ5qHeccpExDOLJ5CMPZZ3QytPmAG5WF0Kzs

### Sources I could not reach, and what that leaves unchecked

- **The Rock Band Network docs.** `docs.c3universe.com/rbndocs` does not resolve, and c3universe.com answers 404 or 500.
- **RhythmGamingWorld's forums.** They were removed and every topic URL answers 404.
- **Older forums and wikis.** fretsonfire.org and the YARG wiki are behind JavaScript challenges.
- **Reddit.** It is blocked for scripts.

So the Harmonix and RBN authoring rules here reach me second-hand, through GGCF (which cites the C3 docs), EOF (which implements Magma's checks) and search summaries. And nothing below on what players complain about comes from a player forum. Section 9 says what that section rests on instead.

---

## 1. Tempo maps

### What the map controls in play (enforced by the game)

The tempo map does far more than draw beat lines:

- **The natural-HOPO threshold is counted in ticks.**
  - In .chart it is `floor(65/192 × resolution)`, which is 65 ticks at 192 (GGCF `chart-format/Tracks/5-Fret-Guitar`; scan-chart `chart/notes-parser.ts:427-431`; YARG.Core `MoonscraperChartParser/IO/Chart/ChartReader.cs:164-171`).
  - In .mid it is `resolution/3 + 1` (GGCF `mid-format/Tracks/5-Fret-Guitar`).
  - So notes about a third of a beat apart or closer become natural HOPOs. A wrong tempo octave changes which notes do.
- **Star power lasts a number of measures.** A half meter lasts 4 measures (CH wiki, how-to-play and dictionary). Both the measure length and the time signature therefore set how long star power lasts in seconds.
- **Sustains score 25 points per beat** of the map (CH wiki, dictionary).
- **In .mid, sustains of 1/12 step or less are cut off** (GGCF; scan-chart `notes-parser.ts:191-209`). This is not the case in .chart.
- Beat lines, practice-mode sections and practice speed all use the map.

### Conventions and rules

- **Map first, then chart.** The map follows the song's musical pulse, the beat a musician counts. Beats are lined up on the audio, with anchors every measure or two (EOF tutorial, "Creating a Tempo Map"). It is one map for the song, not one per instrument (convention; a forum summary agrees).
- **Tempo range.** RBN's Magma compiler refuses tempos under 40 or over 300 BPM. EOF has a "Fix tempo for RBN" command for exactly this (EOF manual, "Double BPM" / "Halve BPM"). So songs of 200 BPM or more are charted at their real tempo. No source suggests folding the tempo into a fixed range.
- **Deliberate doubling or halving exists but has costs.** EOF's halving note says it makes notes "more prone to appearing as HOPO notes". A forum summary says tools such as CAT then trim sustains wrongly (secondary). This is convention, not rule.
- **Time signatures follow the song's meter.** In .chart they are written `TS n [log2 d]` (FireFox spec; GGCF).
- **Encore requires the chart to be "tempo-mapped and … in sync"** (lint, judged by a reviewer).
- **scan-chart flags `isDefaultBPM`**: a single 120 BPM marker with a single 4/4 (lint).

### What songcharter does

- `beatgrid.py:54` folds the tempo into `BPM_RANGE = (85.0, 185.0)`. The comment gives the reason: CH's HOPO threshold is in ticks (DESIGN §2.3 step 3; §8.1 lists songs over 185 BPM as a known gap).
- The meter is x/4 only (`tempo.py:136-184`; DESIGN §2.4).
- The owner's runs (PROGRESS `deferred`):
  - a 198 BPM song came out at 100 BPM, its beats 150 ms off even when doubled;
  - the shred instrumental came out at double the humans' tempo.

### The gap

The fold contradicts the convention: musical tempo, anywhere in 40–300 BPM. Everything songcharter measures in ticks or beats scales with the octave:

- the HOPO threshold (`quantize.py:90`);
- the 1/16 + 1/12 snap grid (`quantize.py:99-100`). At half tempo a real 16th falls between two slots, so fast runs merge (section 2c);
- the sustain floors of 0.75 beat and the 1/16 gap (`quantize.py:81-84`);
- star-power count, length and spacing (`starpower.py:100-106`);
- fills every 4 measures;
- the section rules: merge under 4 measures, split over 16 (`assemble.py:137-139`);
- the solo minimum of 4 measures;
- the 1/16 snap of lyric syllables, which is about 150 ms at a 99 BPM map.

**Priority: high.**

Suggested direction:

- Choose the octave whose beat is the musical pulse, using two tests:
  - the backbeat: the snare on beats 2 and 4;
  - most notes on 8th or 16th positions. Human guitar and bass sit about 95 % on 8ths (DESIGN §2.6 evidence).
- Allow 40–300 BPM.
- Keep one octave per section unless the music really changes.
- Score the octave choice with beat F1 against the human maps, without octave tolerance.

---

## 2. Expert guitar and bass

### 2a. How much of what is played gets charted

**Convention.**

- Expert is a literal transcription of the part. This is the RB creator spec, quoted second-hand on the FoF forum "LAWS of guitar authoring" (https://www.fretsonfire.org/forums/viewtopic.php?p=462288).
- The CH wiki defines an *overchart* (more notes than can be heard, or harder patterns) and an *underchart* (notes omitted, patterns simplified) as faults (dictionary).
- Encore: "Notes are placed accurately based on their timing and relative pitch … balances accuracy, playability, and readability" (convention, judged by a reviewer).

**What songcharter does.** Expert comes from the engine. In the shred song it peaks at 11 notes/s where both human charts reach 17, and its four takes all stop at 498.6 s of 544.8 s: the decoder's 8,192-token budget runs out (PROGRESS `deferred`). autochart's own README warns that "very long or fast songs can hit the model's limit, and the last part may come out empty".

**Gaps.**

- The missing ending is **high**: notes stop while the guitar plays, and the user is not told.
- Thinning of fast runs is **high**. Part of it is songcharter's own spacing rule, not the engine (section 2g).

### 2b. Fret mapping

**Convention** (all of it; Encore's reviewers judge it):

- **Relative pitch, i.e. contour.** A higher note goes on a higher fret and a lower note on a lower fret. midi-ch flags `Bad_Too_Low` and `Bad_Too_High`.
- **The same pitch in a phrase gets the same fret.** midi-ch flags `Bad_Different_Fret`, and an "Ignore Gap" lets the mapping reset after a rest.
- **A repeated riff is charted the same way each time.** EOF's tutorial teaches copy and paste: "many songs have riffs … which repeat … copy the notes … instead of re-fretting them".
- **Range.** A section's register fits the music: low riffs low, leads high.
- **Playability.** Avoid jumps the hand cannot make at that speed. This is folded into Encore's "playability, and readability".

**What songcharter does.**

- The frets are autochart's.
- Takes are spliced per section by agreement (`takes.py`), so two choruses can come from different takes, with different frets.
- Nothing checks contour, same-pitch consistency or repeat consistency on Expert. `reduce.py`'s contour-preserving lane pass applies only below Expert.
- The yardstick is exact fret agreement: 16–27 %, where human charts agree with each other about 46 %.

**Gaps.**

- **The metric is the wrong target** (medium-high). Human charts disagree on exact frets half the time. Score instead:
  - contour agreement (direction κ);
  - same-pitch-same-fret consistency within phrases;
  - consistency of repeated riffs;
  - the distribution of jump sizes against human charts.
- **No repeat consistency** (medium). The charter's practice is to copy the best version of a repeated riff into its repeats. songcharter could:
  - find the repeats from section labels and chroma or onset self-similarity;
  - reuse one take's notes for all of them, re-timed;
  - accept that only when audio onsets support it.

### 2c. Chords

**Rules.**

- 5-note chords are `invalidChord` (lint: scan-chart `chart/chart-scanner.ts:412-417`).
- Forbidden notes (lint, scan-chart `chart-scanner.ts:393-410`):
  - Hard: G+O;
  - Medium: orange, and G+B;
  - Easy: blue and orange.
- In Clone Hero, strummed chords cannot be anchored; HOPO and tap chords can (CH wiki dictionary). The game enforces this.

**Convention.**

- Chords go where the guitarist plays them: power chords as adjacent or skip-one shapes, 3-note chords sparingly.
- A run of single notes is never written as a chord.
- 4-note chords are legal but rare.

**What songcharter does.** Onsets that land on one tick merge into the union of their frets (`quantize.py:566-569`). `_separate` (`quantize.py:516-548`, with every fret on one lane at `:455`) splits a crowded tick only once, and only into a free neighbouring slot. On the half-tempo grid it merged 740 of 2,085 guitar notes, and the chart came out 38 % chords where humans have 3–5 % (PROGRESS). Expert also caps chords at 3 notes (`quantize.py:73-78`).

**Gap: high.**

- Never merge onsets that are distinct in time (for example more than about 20 ms apart, or more than a third of a slot) into a chord.
- If the grid cannot hold them, either the octave is wrong (section 1) or a finer slot is needed: 1/32 or 1/24 for bursts.
- Dropping such a note is better than making a chord.

### 2d. Open notes

**Rule** (the game, and the format; GGCF; CH wiki how-to-play):

- `N 7` in .chart.
- An open note cannot share a chord with frets in a strum, though Clone Hero v1.1 and later has open-note chords.
- scan-chart's `brokenNote` skips pairs of an open and a non-open note.

**Convention.** Clone Hero customs use opens for low open-string chugs (GH5 style). Rock Band charts have none. Encore treats "open notes" as a variant worth a title tag, so opens are a style choice.

**What songcharter does.** Opens appear only if autochart emits them, on Expert only. The bass engine writes none.

**Gap: low.** Leave it.

### 2e. Sustains

**Rules.**

- .chart keeps a sustain of any length. .mid cuts sustains of 1/12 step or less (enforced; GGCF; scan-chart `notes-parser.ts:191-209`).
- scan-chart (lint, `chart-scanner.ts:15-16, 483-515`):
  - `babySustain`: under 100 ms;
  - `badSustainGap`: under 40 ms.
- Encore (lint): no sustain under 200 ms; sustain gaps of 60 ms or more, 70–85 ms recommended.

**Convention.**

- Sustain notes that ring audibly; do not sustain every 8th.
- End the sustain at the audible decay, or a gap before the next note.
- Sustains inside star power give the player something to whammy.

**What songcharter does.**

- A sustain is kept if it is at least max(200 ms, 0.75 beat), and it ends at least max(85 ms, a 1/16) before the next note (`quantize.py:81-84, 403-407`; DESIGN §2.7). That meets Encore's numbers.
- The thresholds are in beats, so they move with the octave. On a half-tempo map, sustains up to 1.5 real beats long are dropped.

**Gap: low** once the tempo is fixed.

### 2f. HOPOs and taps

**Rules** (the game):

- **The natural HOPO.** A single note, within the threshold of the previous note, not on the previous note's fret, and not a chord. .mid adds one exception: a note that is part of the chord just before it (GGCF; scan-chart `notes-parser.ts:455-468`).
- **Forcing.** `N 5` flips the natural state in .chart. In .mid, notes 101 and 102 force HOPO and strum on Expert.
- **Taps.** `N 6`, .mid note 104, or the tap SysEx. A tap can be hit without a combo (CH wiki).
- **Getting it wrong costs the player.**
  - An overstrum breaks the combo and ends the current star-power phrase (CH wiki how-to-play).
  - Pressing wrong frets while a HOPO or tap is in the hit window drains the ghost meter (dictionary).

**song.ini HOPO tags: the sources disagree.**

- GGCF says `hopo_frequency` and `eighthnote_hopo` change the threshold.
- scan-chart's docs (`interfaces.ts:83-86`) say they apply to .mid only.
- Encore forbids them.

So do not use them.

**Convention.**

- Use HOPOs where the guitarist plays legato (hammer-ons, pull-offs, slurred runs) and in fast runs that cannot be strummed.
- Force a strum where the part is picked but falls inside the threshold. Picked 16ths in metal are often kept strummed.
- Use taps for tapped passages.

**What songcharter does.**

- `hopo: "forced"` (`assemble.py:171`; `quantize.py:571-575`) keeps only the states the source forced. Every other note takes the natural state on *our* map.
- Taps are kept (`QuantizeRules.taps = True`, `quantize.py:116`), although DESIGN §2.6 step 7 says "no taps" (DESIGN §2.0 records the mismatch).

**Gap: medium-high.**

- The played state of a note depends on our octave:
  - on a double-time map, real 16th runs fall outside the threshold and become strums;
  - on a half-time map, 8th strums become HOPOs.
- The convention cares about the articulation the player performs. So:
  - work out each note's strum, HOPO or tap state on the source's own map;
  - write it on ours with `N 5` flips wherever our natural state differs. That is octave-independent.
- The rule engines (bass) need a state rule based on time, not ticks.
- Keeping taps matches the convention; fix DESIGN.

### 2g. Speed limits and fast passages

**Rules.**

- The only spacing check anywhere is scan-chart's `brokenNote`: two notes 15 ms apart or less (lint, `chart-scanner.ts:464-480`).
- Rock Band and GH snap .mid notes within 10 ticks into a chord (GGCF).
- Trill and tremolo lanes (.mid notes 127 and 126) make trills and tremolo strumming that cannot be made out lenient to play. They apply to Expert, and to Hard at velocity 41–50 (GGCF `mid-format`). The .chart format has no equivalent for guitar.

**Convention.**

- Fast alternate strumming is kept strummed. CSC's rating 6 describes "breakneck alt-strumming speeds".
- Faster legato is written as HOPOs or taps.
- Tremolo and trill lanes are used where notes cannot be made out.
- Two human charts of the shred song reach 17 notes/s, about 59 ms between notes.

**What songcharter does.** It drops any onset closer to the previous one than 80 ms before a strum, or 55 ms before a HOPO or tap (`quantize.py:91-92, 576-578`). DESIGN §2.6 step 3 justifies this as avoiding `brokenNote`, which is only 15 ms. Strummed 16ths above 187.5 BPM are therefore deleted, and so are strummed runs at 17 notes/s.

**Gap: high on fast songs.**

- Set the floor from data: the shortest gaps between onsets in human charts (for example their 1st percentile, by strum or HOPO state).
- Keep it above 15 ms.
- `QuantizeReport.dropped` in report.json counts the notes this rule dropped. Check it on the two fast songs first.

---

## 3. Drums (pro, 4-lane)

The friend plays guitar, so drums rank lower overall.

### Rules from the format and the game

From GGCF `chart-format/Tracks/Drums` and `mid-format/Tracks/Drums`:

- In .chart a pad is a tom by default. Cymbal markers are `N 66/67/68`. Red is always a tom, and a pad cannot be a cymbal and a tom on the same tick.
- `pro_drums = True` forces pro parsing. Encore says to set it only if the game cannot tell the drum type from the chart, and with cymbal markers present it can, so writing it is harmless.
- **2x kick** (`N 32`) is for kicks faster than about 5–6 a second. The 2x kicks *alternate* with normal ones, so a player with one pedal can still play the part. scan-chart forbids 2x kicks below Expert.
- **Activation lane** `S 64`. Unlike other phrases it includes its last tick, and the note at its end is the activation note. YARG generates lanes when a chart has none (YARG.Core `Chart/SongChart.AutoGeneration.cs:117-170`). scan-chart flags `noDrumActivationLanes` when a track has star power, more than 50 notes and more than 60 s.
- **Roll lanes** `S 65/66`, for rolls and cymbal swells, not kicks.
- **Accents and ghosts** are optional bonus points (CH wiki).
- **Disco flip** (`mix_<d>_drums<n>d`) is for open-handed parts.
- On Easy, a kick may not share a hit with two pads (lint).

### Convention ([recall], consistent with GGCF's tables)

- hi-hat on yellow cymbal, ride on blue cymbal, crash on green (a second crash on blue);
- toms from high to low on yellow, blue, green.

Encore does not require drum star power.

### What songcharter does

- `drummap2`:
  - hi-hat goes to yellow cymbal;
  - a cymbal in a regular run goes to blue cymbal, otherwise to green;
  - toms go by pitch cluster.
- 2x kick (`engines/drumlanes.py:25-30, 178-195`): in a run of more than 6 kicks each under 1/6 s apart, a kick less than 1/6 s after the last single kick becomes 2x. The phase follows where the run starts, not the beat. At 16ths of 200 BPM that marks two kicks in three as 2x, not every other one.
- No roll lanes, accents, ghosts or disco flip.
- Fills are placed (`starpower.py:25-59`).
- Exact-lane agreement is 0.285–0.585, against STRUM's 0.667–0.687. The main confusion is snare written as hi-hat.

### Gaps

- **Lane accuracy: medium.**
- **2x kick: low-medium.** Alternate on the grid: single on the beat or 8th, 2x on the 16th between.
- **Roll lanes, accents, ghosts, disco flip: low.**

---

## 4. Star power

### Rules from the game

From the CH wiki how-to-play and dictionary:

- Hitting every note of a phrase adds 1/4 of the meter, and whammying a sustain inside a phrase adds more.
- Star power can be activated at half a meter, which lasts 4 measures.
- An overstrum cancels the phrase.
- YARG gives a unison bonus for star-power phrases on two or more instruments at the same position, within a 16th (YARG.Core `Engine/EngineManager.UnisonEvent.cs:232-240`).
- scan-chart flags `noStarPower` (non-drum tracks with more than 50 notes and more than 60 s) and `emptyStarPower`.
- Encore wants star power "when appropriate", and not on drums.

### Convention

- Put phrases on coherent musical units (a riff, a lick, a held note), often ending on a sustain so there is something to whammy.
- Space them so the meter can be used; none right at the start.
- In Rock Band they are often lined up across instruments, for the unison bonus [recall].
- The repository's own Harmonix counts (DESIGN §2.10; `starpower.py:11-21`):
  - about one phrase per 41 beats, median 11 a song;
  - 92–98 % start on a note;
  - a median of 8 measures between phrases.

### What songcharter does

- K = round(span / 40 beats) phrases, each one measure long and starting on the measure's first onset (`starpower.py:9-23, 100-106`).
- Starts are at least 24 beats apart.
- A measure scores +2 if a sustain starts in it.
- Each instrument is placed independently, so there are no unisons.

### Gaps

- **Count, length and spacing are counted in beats** (medium). An octave error doubles or halves them: the shred song's double-time map gives twice as many half-length phrases. This is mostly fixed by section 1.
- **Prefer a phrase that ends on a sustain** (low).
- **Line phrases up across guitar, bass and drums for YARG band play** (low).

---

## 5. Solos and sections

### Solos

**Rules** (GGCF; CH wiki; scan-chart `emptySoloSection`):

- In .chart a solo is `E solo` / `E soloend`, and the end tick is inclusive. In .mid it is note 103, and with no note 116 in the chart, 103 is read as star power for GH1/2 compatibility (`multiplier_note`).
- The game shows the share of notes hit, and pays 100 points per note at 100 %, nothing at 50 % or below.

**Convention.**

- Solo markers go on a featured lead break, not on every instrumental passage. "Not all songs have Solo sections" (CH wiki); Encore says "solo sections when appropriate".
- The repository's human data: median 1 solo a song, 90th percentile 2–3 (`starpower.py:67-68`).

**What songcharter does.**

- Every section allin1 labels Solo becomes a solo (pipeline default "labels").
- Adjacent ones are joined, with no length cap. The minimums are 4 measures and 16 onsets, and at most 3 solos are kept, those with the most onsets (`starpower.py:432-476, 123-127`).
- On the shred instrumental, solo markers covered about 7 minutes.

**Gap: medium-high.** A solo counter running for most of a song looks wrong and makes the bonus meaningless.

- Cap a solo's length and its share of the song, and split long joined runs at section boundaries.
- On instrumentals, keep only the spans where the lead stands out (density or register peaks).
- Measure the rule on references with human solos. PROGRESS already asks for 20 or more references.

### Sections

**Rules and lint.**

- `[section <name>]` or `[prc_<name>]` events are used by practice mode and the post-game summary (GGCF `mid-format/Tracks/Global-Events`).
- YARG auto-generates ten "0%–10%"-style sections when a chart has none (`SongChart.AutoGeneration.cs:16-60`).
- scan-chart flags `noSections`.

**Convention.**

- Name sections musically: Intro, Verse 1, Pre-Chorus, Chorus 2, Guitar Solo, Bridge, Breakdown, Outro. Rock Band's list is in GGCF `Implementation-Specific/Rock-Band/MIDI-Tracks/Practice-Sections`, sourced from the C3 docs.
- Make them short enough to practise.

**What songcharter does.** allin1 labels in Title Case, numbered or lettered, merged under 4 measures and split over 16 (`sections.py`; DESIGN §2.5).

**Gap: low.** Write "Guitar Solo" (Rock Band's name). The measure-based rules follow the octave.

---

## 6. Lower difficulties (brief)

**Rules** (scan-chart lint): the forbidden notes in section 2c; no 2x kicks below Expert; on Easy, no kick with two pads.

**Convention.** The Harmonix and RBN reductions:

- each level is nested in the one above, fewer lanes lower down, simpler chords;
- in Rock Band, HOPOs only on Hard and Expert [recall].

`reduce.py` implements these ideas (DESIGN §2.11). Songcharter writes Expert only by default.

**Gap: low.** Leave it until the friend asks.

---

## 7. Lyrics and vocals

### The format, and what each game shows

- Lyrics live in .chart's [Events] as `phrase_start`, `lyric <syllable>` and `phrase_end` (GGCF `chart-format/Tracks/Lyrics`).
- **Markup:**
  - `-` joins the next syllable; `=` joins it and shows a hyphen;
  - `+` is a pitch slide;
  - `#`, `^` and `*` mark notes as non-pitched (talkies);
  - `%` is a range shift;
  - `$` hides harmony syllables;
  - `/` splits a static phrase;
  - `§` ties two syllables into one;
  - `_` is a space;
  - `<>` holds actions or rich text.
- .chart carries no pitched vocals, so a .chart song has lyrics only. Pitched vocals and harmonies need .mid PART VOCALS or HARM1–3 (GGCF `mid-format/Tracks/Vocals`).
- **Clone Hero** shows the current phrase and highlights each syllable as it is sung.
- **YARG adds** (YARG.Core):
  - vocals and harmony gameplay from pitched notes;
  - static or scrolling lyrics, with lyric and range shifts;
  - censoring of explicit lyrics;
  - lip-sync generated from lyrics (`SongChart.AutoGeneration.cs:588-645`);
  - static-lyric gap thresholds of 0.4 s and 1 s (`Utility/StaticLyricConstants.cs`).

### Convention (Harmonix's, as EOF's vocals tutorial records it)

- One lyric per syllable, with a trailing `-` on every syllable of a word but the last.
- `=` where a hyphen should show.
- No punctuation except `!`, `?`, periods in abbreviations, and apostrophes.
- The first lyric of each phrase capitalised.
- Phrases are the sung lines.

### What songcharter does

From `lyrics.py:13-21, 45-47` and DESIGN §2.15:

- A pasted line is one phrase, split at rests over 3 s.
- Words are never split into syllables. The exception is a hyphen the person typed, which is written as `=` and shows in the game.
- Punctuation is shown as typed.
- Syllables are snapped to the note grid.

How it measured on the 198 BPM song (PROGRESS): 68 % of words within 50 ms, where human charts agree with each other at 94 %, and 96 % within 250 ms.

### Gaps

- **Precision at 50 ms: medium-low.** Part of it is likely the half-tempo grid: a 1/16 slot of the 99 BPM map is about 150 ms, so snapping alone can move a syllable 75 ms. This is fixed by section 1. Then re-measure.
- **No syllables: medium-low.** A long word highlights all at once. The aligner already has character-level timings, so syllables could be cut by hyphenation and timed from the characters.
- **Punctuation and capitalisation conventions: low.**
- Pitched vocals: leave for later.

---

## 8. The song folder

### What the games read, and what the lints check

**Clone Hero (CH wiki, custom-content):**

- Song files named `background`, `video` and `highway`:
  - images in .png, .jpg or .jpeg;
  - video in .mp4 (x264), .avi, .webm (VP8), .ogv or .mpeg. Linux plays only .webm (VP8) and .ogv.
- **The player has to turn on "Use Song Backgrounds", "Song Videos" or "Song Highways" in Settings > Gameplay.**

**YARG** (YARG.Core `Song/Entries/SongEntry.cs:46-58`) reads:

- images named `bg` or `background`;
- `video` as .mp4, .mov, .webm or .mkv.

**scan-chart:**

- Album art is `album.jpg`, `album.jpeg` or `album.png`, at 500x500 or 512x512 (`image/image-scanner.ts:55`; `utils.ts:133-135`).
- Video in mp4, avi or mpeg is flagged `badVideo` (`utils.ts:138-148`).
- Audio file names come from a fixed list (`utils.ts:108-128`).
- The ini must hold name, artist, album, genre, year and charter (`ini/ini-scanner.ts:88`).

**Encore:**

- Images: `album` at 512x512, .jpg preferred. Backgrounds are named `background…`, at least 1280x720, and Clone Hero cycles through them alphabetically.
- Video: `video.webm` in VP8, not VP9. Movies are not allowed.
- Audio: .opus at 80 kbps preferred; .ogg at 192–320 kbps.
- Offset = 0 in notes.chart.
- The first note at least 2 s in, or two measures of the opening tempo.
- No files the games do not recognise.
- song.ini:
  - the tags in Encore's order;
  - no blank values and no -1;
  - Title Case;
  - a single takes the album "<Name> - (Single)";
  - one genre, as specific as possible;
  - `song_length` required;
  - `diff_*` from 0 to 6, extendable to 10;
  - `delay`, `hopo_frequency`, `eighthnote_hopo`, `multiplier_note`, `frets`, `track` and `end_events` forbidden.

**Where the sources disagree:**

- **song_length.** The CH wiki says entering it manually "is not recommended"; Encore requires it.
- **Leading silence.** scan-chart's `smallLeadingSilence` fires at 1000 ms in its code (`chart-scanner.ts:14`), but its message and Encore say 2000 ms.
- **Preview.** It lasts 30 s from `preview_start_time` (CH wiki).
- **Stems.** They let the games act on the audio of one part. In CH, the whammy distorts that part's audio "in songs that have separate audio files for instruments" (dictionary).

### What songcharter writes

- notes.chart, song.ini, song.ogg (libvorbis q7, about 224 kbps, inside Encore's .ogg range) and report.json (`assemble.py:156-158`).
- **song.ini** (`ini.py`):
  - name, artist, album, genre, year, charter, album_track, `diff_*` (3 when no rating is given, `:39`), `diff_drums_real`, pro_drums, preview_start_time and loading_phrase;
  - no `diff_band` and no `song_length` (`ini.py:3-5`; DESIGN §6);
  - "Unknown" placeholders when the file has no tags.
- **Preview:** the first chorus (`assemble.py:1450-1452`).
- **Art:** none yet. M4-11, on branch `m4-11-art`, plans `album.jpg` at 512x512 and a background image.

### Gaps (all low unless noted)

- **M4-11 naming: low-medium.** Name the background `background.jpg`: Clone Hero and YARG both read it. Tell the friend to turn on "Use Song Backgrounds", or he will never see it.
- **`song_length`.** Decide between Encore and the CH wiki. For a friend's private folder, omitting it is fine.
- **`diff_band`** is not written, although DESIGN §2.12 plans it.
- **report.json** is an extra file the games do not recognise. Clone Hero ignores it, but Encore's guidelines would flag it.
- **Album placeholder.** Instead of "Unknown", write "<Name> - (Single)" when there is no album.
- **Stems** (section 10): optional, later.

---

## 9. What players judge a chart by

The player forums were not reachable (see "Sources I could not reach" above). This section therefore rests on three things: Encore's review criteria, the CH wiki's own definitions, and the gameplay mechanics above. It is not a survey of player complaints.

- **Sync.**
  - Notes must fall where they are heard. YARG's default hit window is 0.14 s in total, ±70 ms (YARG.Core `Game/Presets/EnginePreset.Instruments.cs:29-30, 120-126`). I did not find Clone Hero's.
  - The beat lines must match the music, since the tempo map drives HOPOs and star power.
  - songcharter's sync is good (matched notes within 10 ms), but its octave is wrong on fast songs.
- **Readability.** Patterns should look like what is heard: no chords where single notes are heard, and consistent frets for the same notes and repeated riffs (sections 2b and 2c).
- **Playability.** The right strum and HOPO states, because overstrums break the combo and ghosting drains the ghost meter. No jumps that cannot be made.
- **Completeness.** No missing passages and no lost ending: neither an underchart nor an overchart (CH wiki).
- **Polish.** Sections, star power where it can be used, solos only on solos, metadata, art and a sensible `diff_guitar` (CSC's rubric).

The owner's findings fall into exactly these categories:

- a wrong tempo octave;
- chord spam from merging;
- an underchart of fast runs;
- a lost ending;
- solo markers spread over a whole song.

---

## 10. Ranked gaps for the next version

1. **Tempo octave = the musical pulse** (section 1), with 40–300 BPM allowed and a backbeat and subdivision test. It is the root of the half-tempo merging, the octave-dependent HOPO states, the star-power, sustain and section scaling, and probably part of the lyric imprecision. Score it with beat F1, *without* octave tolerance, against the human maps.
2. **Never merge time-distinct onsets into a chord** (section 2c, `quantize.py:516-569`). Add 1/32 and 1/24 slots for bursts, or drop the note before making a chord. This is needed even with the right tempo.
3. **Lower the spacing floors of 80 ms (strum) and 55 ms (HOPO)** (section 2g, `quantize.py:91-92, 576-578`) to just above `brokenNote`, guided by the gaps in human charts. Check `QuantizeReport.dropped` on the two fast songs first.
4. **HOPO, strum and tap states independent of the octave** (section 2f). Reproduce the source's played state with `N 5` flips. The bass engine needs a state rule based on time.
5. **The guitar ending lost to the token cap** (section 2a). Chunked transcription with overlap and stitching, and at least a warning (PROGRESS).
6. **Solo markers on featured lead breaks only** (section 5). Cap the length and the share of the song, and split joined runs.
7. **Fret-quality metrics and repeat consistency** (section 2b). Measure contour, same-pitch consistency and repeat consistency instead of exact frets, and reuse one take across repeated riffs.
8. **Re-measure what the fixes above leave of fast-run thinning** (section 2a), then work on the engine's density (takes, descriptor knobs).
9. **Lyrics** (section 7): syllables from the aligner's character timings, Harmonix's punctuation conventions, and the 50 ms share re-measured after fix 1.
10. **Folder polish** (section 8): `background.jpg` plus the Clone Hero setting in the guide (M4-11), a `song_length` decision, `diff_band`, "- (Single)" for the album, and whether report.json stays in the folder.

### Leave for later, and why

- **Trill and tremolo lanes.** They exist only in .mid, so they need a format change.
- **Drum roll lanes, accents, ghosts, disco flip, the 2x-kick phase, drum lane accuracy.** The friend plays guitar.
- **Tuning the lower difficulties.** Expert is the only level used by default.
- **YARG unison phrases.** They matter only for band play.
- **Stems for miss feedback and whammy.** Separation artifacts would be heard, and it is a new audio path.
- **Non-x/4 meters** (6/8, 7/4). They need `tempo.py` and the meter detector. Do them after the octave, if the larger reference set shows them often.
- **Opens on bass.** A style choice.
- **Pitched vocals.** They need pitch transcription and .mid.

---

## 11. Where this contradicts songcharter's current design (DESIGN.md)

1. **§2.3 step 3 and `beatgrid.BPM_RANGE` (85–185).** The fold has no basis in charting practice: charters chart the musical tempo, and Magma allows 40–300. The design uses the tempo octave to make the tick-based HOPO rule come out right. Charters do the opposite: they choose the musical tempo and then force the HOPO states. §8.1 treats songs over 185 BPM as an edge case to patch. It is a design error that also affects songs under 85 BPM and every rule measured in beats.
2. **§2.6 step 3, the minimum spacing of 80 ms (strum) and 55 ms (HOPO).** It was justified by `brokenNote`, which fires at 15 ms. Nothing in the games or the lints requires more, and the rule deletes real fast notes.
3. **§2.6 step 3, merging same-tick onsets into the union of their frets.** The claim that "two 16ths never become a chord" holds only while a free neighbouring slot exists. By convention, chords are only notes that sound together.
4. **§2.6 step 4 and §2.14 C10, `hopo: "forced"`.** Leaving the unforced notes to the natural rule on our grid makes the played articulation depend on our tempo octave. The convention is to reproduce the articulation.
5. **§2.10, solos by default on every section labelled Solo, joined, with no length cap.** By convention, solos are featured lead breaks; a 7-minute solo is not one.
6. **§2.13, "separated stems are never shipped … Clone Hero would play the parts twice".** This is true only if song.ogg stays the full mix. With song.ogg as the mix minus a stem plus that stem, nothing doubles. Stems are a standard folder feature, so this is an option rather than a rule (low).
7. **§6 and `ini.py`, omitting `song_length`.** This agrees with the CH wiki but goes against Encore, which requires it.
8. **§2.6 step 7 and §2.7 step 6, "no taps".** The code keeps taps, and taps are a legitimate Expert feature. Update the design, not the code.
9. **§2.7 chords, "no 4-note chords on Expert".** This is stricter than any rule: only 5-note chords are invalid. 4-note chords are rare in human charts, so this is low.
10. **§2.9, the 2x-kick rule.** The format's convention is to alternate normal and 2x kicks. The rule's phase follows the run's start instead.

---

### Note on method

- The cloned sources are in the scratchpad's `research/` folder: GGCF, YARG.Core, EOF and midi-ch. The web pages are saved as text under `research/web/`.
- Every songcharter line reference was read on `main` at `c8bd01c`.
