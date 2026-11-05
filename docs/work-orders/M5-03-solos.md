# M5-03: solos on long instrumentals: a solo has a longest length and solos a largest share of the song

**Branch:** `m5-03-solos`, from `main` after wave 1 (wave 2, beside M5-02). **Agent:** `sc-builder`, then
`sc-reviewer`. May push its branch to run CI. **Files:** `songcharter/starpower.py` (the solo rules), its tests,
`docs/DESIGN.md` 2.10. Not `assemble.py` (M5-01 touched it in wave 1; nothing here needs it), not `engines/sections.py`
or `sections.py` (the labels and names stay). **Time budget:** 1 day.

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
   charts (`$EVAL_DATA/refs/<id>/ref`, two of them have solos) and the five stress charts (M5-09's set, else the
   scratch folders `<S>/sooth/human_*` and `<S>/troop/human_*`): per solo its length in seconds and in measures of
   the chart's own map, and per chart the solos' share of the span between its first and last Expert onset. Report
   the table. Do not open any chart's [Events] or vocal track with Read, cat or grep (the stress charts have
   vocals).
2. **The rules** (`SoloRules`, with the measured defaults):
   - `max_measures`: a solo span longer than this is split. Default 32; set it to the 95th percentile of the human
     solos' lengths in measures rounded up to a multiple of 8, never under 16 nor over 64.
   - `max_share`: the solos of a song together cover at most this share of the span between the first and last
     Expert onset. Default 0.25; set it to the largest human share rounded up to the next 0.05, never under 0.15.
   - `min_measures` 4, `min_onsets` 16 and `max_solos` 3 stay.
3. **Splitting** (`solo_sections` and `place_solos`): a run of consecutive Solo sections longer than `max_measures` is
   split at the run's inner section starts (the lettered parts the sections engine made: "Solo 2A", "Solo 2B", ...)
   into parts, which are grouped from the run's start into candidate spans of at most `max_measures` each (a part
   longer than the cap on its own is cut at the measure line `max_measures` after its start; the remainder is its
   own candidate). A run within the cap is one candidate, as now.
4. **Choosing:** candidates that pass `min_onsets` and `min_measures` are ranked by onset density (Expert onsets per
   measure), ties by the earlier start; they are taken in that order, at most `max_solos`, skipping any that would
   take the solos' total past `max_share` of the charted span. The result is sorted by start, as now. With `names`
   (a person's section names) nothing is split or capped: the person's choice stands, as the docstring promises.
5. **The report:** `report.json`'s `phrases.<part>.solos` stays; add `solo_rules` (the values used) and, per solo,
   its measures and onsets, and the candidates skipped by the share cap, so a reader sees why a solo is where it is.
6. **The preview draws the solos** (`preview.py`, the overview: a shaded span per solo above the guitar's row, as
   the star power is shown; PROGRESS's deferred "the preview's overview does not draw the solo spans"), so the owner
   can judge them on the overview. `preview.py` is outside the golden's engine files; one test on a generated folder.

## Tests

- `solo_sections`: parts are grouped from the run's start while the group stays within the cap, so with
  `max_measures` 32 a run of five 20-measure parts gives five candidates of 20 (two would make 40), a run of ten
  8-measure parts gives groups of four, four and two, and a single part of 50 measures gives a 32-measure candidate
  and an 18-measure one; a run of 30 measures stays one candidate.
- `place_solos`: the densest candidates win; the share cap skips the third candidate when it would pass 0.25 and
  takes the next that fits; `names` bypasses both; the existing tests pass unchanged where no run exceeds the cap.
- Each test fails when its code is broken (say which break).

## Evaluation

- **Golden** (the charting path): `--expect guitar` on the songs whose solo spans change, named in the report; every
  song's onsets per part and difficulty must be identical old → new (the `report.md` table), so the only hash
  changes come from solo spans. Say which reference solos changed and whether the human chart there has a solo.
- **The stress set:** the shred instrumental: at most 3 solos, each at most `max_measures`, together at most
  `max_share` of the charted span; at least one of ours overlaps a human solo (either chart) by at least half of the
  human solo's length, if those charts have solos (the script of step 1 says). The power-metal song: the 134-235 s
  run split, the kept parts the densest, the same overlap check against its three charts.
- No F1 can move (onsets unchanged): check that the stress scores are identical but for the solo-related fields.

## Done means

- [dev] The suite; the new tests fail when their code is broken.
- [dev] The golden diff as above; the step-1 table; the stress lines.
- [CI] Green on the branch.
- [docs] DESIGN 2.10: the two rules, the measured table and the choice; the solo evaluation's numbers stay.

## Limits

- No change to allin1's labels, the librosa fallback's naming or `sections.py`'s merge and split; no new dependency.

## Report

`<scratchpad>/briefs/m5-03.report.md`: the commits, the step-1 table, the rules' values and how they were set, the
golden `report.md`, the stress lines, anything uncertain.
