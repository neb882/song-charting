# How a chart should feel to play (2026-11-05)


The owner asked that the next version think about how a chart feels while playing, not only how many notes match a
human chart. Accuracy against a human chart is a proxy; a chart can score well and still feel wrong. This note says what
"feels right" means for a Clone Hero guitar chart, how each part can be measured, and where the plan should carry it.
It builds on the conventions report (briefs/charting-conventions.md) and the 2026-11-05 findings (PROGRESS).

## What a player feels, and what breaks it

1. **"I hit it when I hear it" (sync).** Notes land on what the guitar plays. A player forgives a missing note far more
   than a note 60 ms off: an off note makes every hit feel late or early and makes the timing window feel unfair.
   The power-metal chart's guitar was 62-68 ms off its matches (bass and drums 4-5 ms): that alone makes it feel bad.
   *Measure:* the timing error of matched notes against human charts (two human charts agree within about 9 ms), and
   the guitar's error beside bass and drums in the same chart. Not against the stem's own onsets with a fixed aim: the
   onset detector sits about 22 ms after human beat lines (the advisor's calibration), so only relative use is sound.
   *Aim:* the guitar's matched-note error close to bass's and drums' (4-5 ms on the power-metal song) and to the
   human-to-human figure.
2. **"It looks like it sounds" (readability).** The highway is read as rhythm: even 16ths look evenly spaced, a run of
   single notes looks like a run, a chord appears only where a chord rings. Phantom chords (38% chords against the
   humans' 3-5%) and notes snapped onto the wrong subdivision make a part unreadable at sight.
   *Measure:* chord share against the human charts and against the stem (a chord needs simultaneous pitches); the
   spread of inter-onset intervals inside a run (an even run should come out even); notes snapped by more than a
   third of a slot. *Aim:* chord share within a few points of human charts; even runs stay even.
3. **"My hand knows where to go" (flow).** Frets follow the melody's direction, stay in a register that fits the part
   (riffs low, leads higher), and avoid jumps the hand cannot make at that speed (green to orange and back at 15 notes a
   second). Exact frets matter less: human charts agree on exact frets only half the time, but they agree on direction.
   *Measure:* contour agreement with human charts (songcharter has no guitar pitch track, so not against pitch), the
   distribution of jump sizes against human charts, and the rate of big jumps (3+ lanes) at fast intervals (under
   100 ms). *Aim:* contour agreement near human-to-human; big fast jumps no more common than in human charts.
4. **"I can learn it" (consistency).** A repeated riff or chorus is charted the same way every time, so practice pays
   off and the second chorus feels like the first. Splicing takes per section works against this: two choruses can come
   from different takes with different frets. This is the convention charters follow most strictly (copy the best
   version of a riff into its repeats).
   *Measure:* where the audio repeats (allin1's labels plus onset and chroma self-similarity), how alike the fret
   sequences are. *Aim:* repeated sections near-identical unless the guitar plays them differently.
5. **"Strum what's picked, hammer what's slurred" (articulation).** Picked parts are strums, legato parts and fast runs
   are HOPOs or taps. A wrong state costs the player: an extra strum on a HOPO breaks the combo, and a forced strum at
   18 notes a second is not playable. Today the state depends on our tempo octave.
   *Measure:* per-note strum/HOPO agreement with human charts (shares alone mislead: three human charts of one song
   have HOPO shares of 0.21, 0.51 and 0.29), and strum streams faster than the human charts of the same song strum. No
   fixed cap: humans strum that song's 16ths at 13.3 a second. *Aim:* states that agree with the humans' on the
   notes they share.
6. **"It breathes with the song" (shape).** Density rises and falls with the music: quieter verses, fuller choruses, the
   solo the hardest part, rests where the guitar rests. Notes where the guitar is silent (the shred chart had 158) or
   gaps where it plays (the 1-take solos) are felt immediately.
   *Measure:* notes per section against the stem's energy; notes in silence; gaps while the stem plays (the preview
   already flags both). *Aim:* no unexplained gaps or ghost notes; a density curve that tracks the stem.
7. **"Something to hold and whammy" (sustains and star power).** Sustains where notes ring give rest and whammy; tiny
   sustains are a chore. Star power phrases on memorable phrases, often ending on a sustain, spaced so activation lands
   in a chorus or solo. Solo markers only on real solos, so the solo bonus feels earned.
   *Measure:* sustain share and lengths against human charts, star-power phrases per minute and how many end on a
   sustain, solo share of the song. *Aim:* within the human range; solos a small share of the song.
8. **"The highway makes sense" (beat lines and lead-in).** Beat lines at the felt pulse and measure lines on the
   downbeat, so the eye can count; a lead-in of a few seconds before the first note; the chart covers the whole song.
   Half or double tempo doubles or halves the lines; a wrong downbeat puts measure lines off the bar.
   *Measure:* beat F1 against human maps without octave forgiveness; downbeat agreement; first note after at least
   2-3 s; last note near the stem's last onset.
9. **"It's hard in the right way" (difficulty fit).** Expert is the part as played, but playable by a skilled human.
   Hard comes from the music (speed, chords, runs), not from artifacts (phantom chords, jitter, wild jumps). No
   measure of its own: it is judged in the play test, and the artifacts it names are measured above.

## Where the plan should carry it

- **Evaluation (M5-09 stress-eval, and the reference set):** add a per-chart *feel report* with the measures above
  for every chart scored, compared with the human charts of the same song, so "feel" is checked alongside F1. Most
  measures need only the chart, the stems and the pitch track the pipeline already has.
- **The fast-grid order (M5-01):** its pass lines include sync (1), readability (2) and articulation (5), not just F1:
  stem offset under 10 ms, chord share near human, no strum streams over the limit.
- **A consistency order (new, or in a later wave):** repeated sections charted alike, reusing one take's notes for a
  repeat when the audio supports it (4). Measure first (M5-09) to see how inconsistent charts are today.
- **Fret flow:** contour and jump measures (3) in the evaluation now; a fix only if the measures show a gap against
  human charts.
- **A play test at the release gate:** the owner plays three songs (an ordinary rock song, a fast song, a long one) and
  the friend plays his own, each answering the same short list: in sync? readable at sight? hand flow? did repeats
  feel the same? anything unfair (overstrums, impossible jumps, ghost notes)? where (times)? A keyboard play is a
  weaker test than a guitar controller: the friend's notes count most.

## Revised after the advisor (2026-11-05)

The sync, articulation and flow measures above were corrected on the advisor's evidence: no fixed sync aim against
the stem, no fixed strum cap, contour against human charts rather than a pitch track, and difficulty fit judged only
in the play test. The repeat-consistency fix belongs to M6; its measure goes in M5-09 if there is room.
