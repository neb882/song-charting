# AutoChart.eu against songcharter on take_me_out, and a half-beat grid slip on another master (2026-11-09)

The owner charted Take Me Out (a reference: its Harmonix chart is the human chart) with AutoChart.eu, a web service
launched in October 2026 (full band; its report names "autochart 0.3.0"), and with songcharter v0.4.0 on his GPU, both
from his own MP3 of the studio recording (another master than the reference's audio: the scorer's audio alignment is
weak, ncc under 0.3, and the two run 1,250 ppm apart in speed). Nothing of their chart, his MP3 or our charts of it is
kept in the repository.

**Alignment.** Each chart's audio was pinned to his MP3 exactly (AutoChart.eu's files start 4.895 s after it, ours
3.274 s, our lead-in; 9 of 9 windows, MAD 0); the MP3 to the reference by a line fitted on 30-s windows of the Expert
onsets (eval/m8/compare/warp_score.py, the scorer's own functions): fitted on either chart, the two lines agree within
3 ms over the song, so the comparison does not depend on whose chart set it.

**Scores against the Harmonix chart (Expert):**

| | AutoChart.eu | songcharter v0.4.0 (his MP3) | songcharter at the gate (the reference's audio) |
|---|---|---|---|
| guitar F1@50 / @100 | 0.923 / 0.924 | 0.853 / 0.881 | 0.909 |
| bass F1@50 / @100 | 0.973 / 0.974 | 0.858 / 0.899 | 0.912 |
| drums F1@50 / @100 | 0.996 / 0.997 | 0.925 / 0.959 | 0.944 |
| beat F1 at 70 ms (in the song) | 0.993 | 0.539 | 0.962 |
| guitar lane direction / exact lane | 0.849 / 0.366 | 0.643 / 0.187 | |
| bass lane direction / exact lane | 0.944 / 0.786 | 0.838 / 0.405 | |

**Reading it.** AutoChart.eu wins every measure here. The song is a poor fair test of it: Take Me Out shipped as an
official Rock Band song, and its bass agrees with Harmonix's exact lane on 79 % of matched notes and its drums at 0.996
F1@50, where lanes are the charter's choice, not the audio's; its section names follow Rock Band's style. A song with a
community chart and no official one (kimochi_warui) is the fairer test.

**The half-beat slip (ours, a defect).** On his MP3 our grid sits half a beat off for stretches after the tempo change
(median offset against the Harmonix beats per 30-s window: -13, -14, +231, +276, -6, +275, -6, -16 ms, the beat 576 ms
after 60 s), so the beat lines fall on the off-beat there; on the reference's audio the same song's grid is right (beat
F1 0.962, 7.75 ms). His MP3 charted on the CPU at v0.4.0 gives the identical grid (free mode on the drums' tracker,
start "tracker" 0.512 / 0.843, 105 markers, allin1's downbeats at phase 0): the master, not the GPU. The notes mostly
land (onsets are placed by time), but measure lines, the reductions and star power follow the grid. For M8: a test case
on this machine (his MP3 stays with the session's uploads, never committed).

## kimochi_warui, the fairer test (2026-11-09)

A reference with only a community chart (no official game's). The owner's MP3 is the reference's own master here
(the scorer's audio alignment strong in 9 of 9 windows, MAD 0, the same lag at the start and the end), so the standard
scorer runs unchanged: AutoChart.eu's audio is his MP3 exactly, ours his MP3 after our 4.49-s lead-in.

| Expert | AutoChart.eu | songcharter v0.4.0 (his MP3, GPU) | songcharter at the gate (CPU) |
|---|---|---|---|
| guitar F1@50 (P / R) | 0.674 (0.884 / 0.545) | **0.789** (0.791 / 0.788) | **0.827** |
| guitar density against the human's | 0.62 | 1.00 | |
| guitar lane direction / state agreement | 0.656 / 0.715 | 0.554 / 0.661 | 0.717 / 0.756 |
| bass F1@50 (P / R) | **0.918** (0.848 / 1.000) | 0.710 (0.642 / 0.795) | 0.758 |
| bass density against the human's | 1.18 | 1.24 | |
| drums F1@50 | 0.985 | 0.981 | 0.977 |
| beat / downbeat F1 at 70 ms | 1.000 / 1.000 | 1.000 / 1.000 | 1.000 / 1.000 |
| scan-chart issues | 139 (106 badSustainGap, 33 difficultyForbiddenNote) | 0 | 0 |

**Reading it.** Without a known chart behind it, AutoChart.eu's guitar charts six notes in ten of the human's (precision
high, recall 0.55); ours charts the right density with balanced precision and recall, and wins guitar F1 by 0.12-0.15.
Its bass is clearly better than ours: every human bass note found (recall 1.000) at precision 0.85, where our rule
engine writes 24 % too many and misses a fifth. Drums and beats are a tie. One song, so a direction, not a verdict:
the bass is where a better engine pays (M8: the bass engine against a learned transcriber, e.g. on the stress and
20-song sets' human bass charts).

## The owner's video review of the two kimochi_warui charts, checked against the human chart (2026-11-09)

The review judged ours by the guitar stem's level and its own viewing; the human chart says otherwise on most claims
(the scorer, 18-s windows, the reference's timeline less its 2.33-s lag):

- **"Chord spam over a silent guitar stem":** the human chart's guitar is 68 % chords (ours 77 %, AutoChart.eu's 5 %),
  and in the sections the review names, our onsets match the human's: 18-36 s F1 0.98, 72-90 s 0.93, 198-216 s 0.95,
  216-252 s 0.99-1.00 (AutoChart.eu 0.49-0.90 there). The human charter put the synth parts on the guitar track, as our
  engine did; removing notes over the "silent" guitar stem would cut our best sections (as M7-01 measured: the humans
  chart them). Ours over-charts 36-72 s and 108-126 s (F1 0.43-0.52, theirs 0.64-0.85), and our lanes are weaker (lane
  direction 0.55 against 0.66).
- **"The take scorer's bug" (scores equal in pairs):** the arithmetic is right. A take's score is its mean F1 against the
  other three; when the takes split into two pairs that agree within and not across, each pair's members score alike
  (the intro: 36 and 1 onsets, F1 2/37 shared, 0.054 / 3 = 0.018, both). Ties go to the lower index. It is the known
  limit (the score does not track the humans: M7-01 part C, docs/reports/M8-spike-takescore.md), M8-02 B's and M8-06's.
- **"No green crash":** the human chart has 4 green notes in the song; AutoChart.eu's 29 (F1 0.12) and our 42 (F1 0.04)
  both miss it; cymbal or tom on yellow, blue and green agree 0.994 and 0.979. Its snare is better than ours (red F1 0.98
  against 0.88); both write far more hi-hats than the human (yellow 513 and 634 against 216).
- **Lyrics:** a backing line inside a lead line's phrase is one phrase on our side; noted for the lyrics, not measured.

## Chord shapes held: the owner's follow-up on kimochi_warui, checked (2026-11-09)

The follow-up named our chart's long runs of one chord shape where the song's chords move. Measured on his v0.4.0 GPU
chart against the human chart (the scorer's readers and alignment: lag MAD 0 over 9 windows, guitar F1@50 0.789 as
above; `eval/m8/compare/held_shapes.py`; times on his MP3):

| Expert guitar | ours: onsets, shapes, shape changes | the human's: onsets, shapes, shape changes (longest run) |
|---|---|---|
| 17.9-35.6 s (a verse) | 61, 1 (G+R), 0 | 63, 3, 7 (13 onsets) |
| 196.3-215.0 s (the break) | 65, 1 (Y+B), 0 | 67, 6, 7 (45 onsets, 12.3 s, mostly G+Y) |
| 223.2-264.4 s (the last choruses) | 148, 1 (G+R), 0 | 147, 9, 72 (16 onsets; 57 % chords) |
| the whole song | 764, 109 changes (one in 7.0 onsets) | 767, 291 changes (one in 2.6 onsets) |

The claim holds: ours keeps one shape for 18, 19 and 41 seconds where the human moves every few seconds. A held shape
is not wrong by itself (the human holds G+Y for 92 onsets at 95.4-120.9 s, and for 45 in the break); ours holds through
the sections where the human moves. No code of ours picks a chord's lanes (the quantizer only caps a chord's size and
moves lanes above the top lane down): the shapes are the transcriber's, on the take the selector picked, and whether
the other takes move is not known (the chart keeps one take). So the GPU takes fix it only if a take that moves exists
and the selector picks it. A direction for M8 or M9, measured before built: shape changes per onset and lane direction
on the sets' human charts, then a pass that moves a held shape where the stem's harmony changes.

**Across the 23 songs (docs/reports/M8-lanes-drums.md, the v0.4.0 CPU charts):** not the engine's habit. Ours changes
shape 0.627 times per onset against the humans' 0.697, long chord holds no more often than theirs, and on
kimochi_warui's CPU chart one change in 3.1 onsets (the human's 2.6). The held sections above are the owner's GPU
chart's: M8-02 part A measures the shape changes on the GPU takes.
