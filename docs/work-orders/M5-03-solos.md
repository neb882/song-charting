# M5-03: solos on long instrumentals: a solo has a longest length and solos a largest share of the song

**Branch:** `m5-03-solos`, from `main` after wave 2 (wave 3, beside M5-04). **Agent:** `sc-builder`, then
`sc-reviewer`. May push its branch to run CI. **Files:** `songcharter/starpower.py` (the solo rules), its tests,
`songcharter/preview.py` (step 6), `docs/DESIGN.md` 2.10. Not `assemble.py` (M5-01 touched it in wave 2; nothing
here needs it), not `engines/sections.py` or `sections.py` (the labels and names stay). **Time budget:** 1 day.

*Amended 2026-11-05 after the advisor's review (finding 9): the measured caps come out loose (about 56 measures and a
share of 0.40 from the human data, and the shred song's map is at double the humans' tempo, so a measure there is
half the seconds), so a solo is capped in seconds as well; the owner sees the shred song's solo spans at the gate.*

**Conventions** (`docs/reports/charting-conventions.md`, section 5, ranked gap 6). The rules this order assumes,
marked **[conventions]** for the advisor: solo markers go on a featured lead break, not on every instrumental
passage ("not all songs have Solo sections", Clone Hero's wiki; "solo sections when appropriate", Encore); the
repository's human data has a median of 1 solo a song and a 90th percentile of 2-3 (`starpower.py`); on an
instrumental, the spans where the lead stands out (density, register) are the solos; a solo counter running for
most of a song looks wrong and makes the bonus meaningless. Rock Band names the section "Guitar Solo"; the name
stays "Solo" in this order (M5-99: it would change the names people pass to `--solos`).

## Why

On the owner's 9-minute shred instrumental (2026-11-05, `<S>/sooth/ours/report.json`) allin1 labelled most of the
song "solo": sections "Solo 1A-1C" (64-103 s) and "Solo 2A-2Z" (116-535 s). `starpower.solo_sections` joins
consecutive Solo sections into one span and `place_solos` keeps the spans with at least 16 onsets and 4 measures, up
to 3 a song, so the chart's two solo markers cover about 7 minutes of the song. On the power-metal song the Solo A-E
run is one 100-second solo (134-235 s of a 302-second song). A solo tracker over a third or two thirds of a song is
not what the friend asked for ("solo trackers on solos"). The labels themselves are allin1's and reasonable for an
instrumental: the fix is in what songcharter makes of them.

## What to build

1. **Measure human solos first** (numbers only, a script of your own, never committed, that reads solo spans through
   `eval/scorer/scan_notes.cjs` or `importers.read_chart` and prints only counts and times): on the six reference
   charts (`$EVAL_DATA/refs/<id>/ref`, two of them have solos) and the five stress charts (`$EVAL_DATA/stress/`,
   M5-09's set, merged before this order): per solo its length in seconds and in measures of the chart's own map,
   and per chart the solos' share of the span between its first and last Expert onset. Report the table. The
   stress packages have vocals: nothing of them is read but through the two readers named, and no chart is opened
   with Read, cat or grep. The advisor's probe, for orientation (measures): 8 and 32 on the references; 4, 4, 52 /
   52 / 4, 4, 15, 52 on the power-metal song's three charts; 31 and 32 on one shred chart, none on the other; the
   largest share 0.36.
2. **The rules** (`SoloRules`, with the measured defaults) [conventions: a solo is a featured lead break of a
   length human charters write, and solos are a minority of the song]:
   - `max_measures`: a solo span longer than this is split. Default 32; set it to the 95th percentile of the human
     solos' lengths in measures rounded up to a multiple of 8, never under 16 nor over 64 (the probe says about 52,
     so 56).
   - `max_seconds`: the same cap in seconds, since the measures are counted on our map and the shred song's map is
     at double the humans' tempo (halving is M5-99's), so a measure cap there means half the seconds it means on the
     human map. Default 60; set it to the 95th percentile of the human solos' lengths in seconds rounded up to the
     next 10 s, never under 30 nor over 120. A span is cut at whichever cap comes first.
   - `max_share`: the solos of a song together cover at most this share of the span between the first and last
     Expert onset. Default 0.25; set it to the largest human share rounded up to the next 0.05, never under 0.15
     (the probe says 0.40, set by the shred chart itself: that still allows about 3.6 minutes of solo markers on
     the shred song, against 7 today and one human chart's 3.2; the owner may want a tighter share for songs with
     vocals, M5-00 section 8).
   - `min_measures` 4, `min_onsets` 16 and `max_solos` 3 stay (the human median is 1, the 90th percentile 2-3).
3. **Splitting** (`solo_sections` and `place_solos`): a run of consecutive Solo sections longer than `max_measures`
   or `max_seconds` is split at the run's inner section starts (the lettered parts the sections engine made: "Solo
   2A", "Solo 2B", ...) into parts, which are grouped from the run's start into candidate spans within both caps (a
   part longer than a cap on its own is cut at the measure line where the first cap is reached; the remainder is its
   own candidate). A run within both caps is one candidate, as now.
4. **Choosing** [conventions: on an instrumental, the spans where the lead stands out]: candidates that pass
   `min_onsets` and `min_measures` are ranked by onset density (Expert onsets per measure), ties by the earlier start; they are taken in that order, at most `max_solos`, skipping any that would
   take the solos' total past `max_share` of the charted span. The result is sorted by start, as now. With `names`
   (a person's section names) nothing is split or capped: the person's choice stands, as the docstring promises.
5. **The report:** `report.json`'s `phrases.<part>.solos` stays; add `solo_rules` (the values used) and, per solo,
   its measures and onsets, and the candidates skipped by the share cap, so a reader sees why a solo is where it is.
6. **The preview draws the solos** (`preview.py`, the overview: a shaded span per solo above the guitar's row, as
   the star power is shown; PROGRESS's deferred "the preview's overview does not draw the solo spans"), so the owner
   can judge them on the overview. `preview.py` is outside the golden's engine files; one test on a generated folder.

## Tests

- `solo_sections`: parts are grouped from the run's start while the group stays within the caps, so with
  `max_measures` 32 a run of five 20-measure parts gives five candidates of 20 (two would make 40), a run of ten
  8-measure parts gives groups of four, four and two, and a single part of 50 measures gives a 32-measure candidate
  and an 18-measure one; a run of 30 measures stays one candidate; on a map at 240 BPM with `max_seconds` 30, a run
  of 40 measures (40 s) is cut at the seconds cap (30 measures) although it is within `max_measures`.
- `place_solos`: the densest candidates win; the share cap skips the third candidate when it would pass 0.25 and
  takes the next that fits; `names` bypasses all three; the existing tests pass unchanged where no run exceeds a cap.
- Each test fails when its code is broken (say which break).

## Evaluation

- **Golden** (the charting path): `--expect guitar` on the songs whose solo spans change, named in the report; every
  song's onsets per part and difficulty must be identical old → new (the `report.md` table), so the only hash
  changes come from solo spans. Say which reference solos changed and whether the human chart there has a solo.
- **The stress set:** the shred instrumental: at most 3 solos, each within `max_measures` and `max_seconds`,
  together at most `max_share` of the charted span; at least one of ours overlaps a human solo (either chart) by at
  least half of the human solo's length, if those charts have solos (the script of step 1 says). The power-metal
  song: the 134-235 s run split, the kept parts the densest, the same overlap check against its three charts. The
  report lists the resulting solo spans of both songs in minutes and seconds beside the humans': the owner looks at
  them at the gate (M5-00 section 7, step 8).
- No F1 can move (onsets unchanged): check that the stress scores are identical to a stress run of this branch's
  merge base but for the solo-related fields (M5-01 and M5-02 moved the notes since M5-09's baseline, so the
  baseline itself is not the comparison here).

## Done means

- [dev] The suite; the new tests fail when their code is broken.
- [dev] The golden diff as above; the step-1 table; the stress lines.
- [CI] Green on the branch.
- [docs] DESIGN 2.10: the three rules, the measured table and the choice; the solo evaluation's numbers stay.

## Limits

- No change to allin1's labels, the librosa fallback's naming or `sections.py`'s merge and split; no new dependency.
- The stress songs' human-chart packages have vocal tracks: read only by the two readers of step 1 and by
  `stress.py`, which print numbers; never opened. Nothing is read from the scratch folders once M5-09 has merged.

## Report

`<scratchpad>/briefs/m5-03.report.md`: the commits, the step-1 table, the rules' values and how they were set, the
golden `report.md`, the stress lines, anything uncertain.
