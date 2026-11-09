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
