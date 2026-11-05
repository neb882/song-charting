"""Star power, drum fills and solos on synthetic parts: placement on Expert (count, shape, spacing, scoring), fill
scheduling against star power, fitting to lower difficulties after the reductions, and the checks."""
import numpy as np
import pytest

from songcharter.chart import (DRUM_ACTIVATION, ROLL, STAR_POWER, Chart, DrumHit, FretNote, Phrase, SongInfo, Track,
                               write_chart)
from songcharter.importers import read_chart
from songcharter.reduce import check_reductions, reduce_chart
from songcharter.starpower import (FILL_RULES, SOLO_RULES, FillRules, SoloRules, check_phrases, fill_crash_share,
                                   fit_chart, fit_phrases, place_fills, place_phrases, place_solos, place_star_power,
                                   schedule_drums, solo_sections, stem_confirm)
from songcharter.tempo import TempoMap

RES = 192
M = 4 * RES          # ticks per measure; at 120 BPM a measure lasts 2 s
GAP = 2 * RES        # FillRules.sp_gap_beats in ticks


def const_map(beats=1200):
    return TempoMap.from_beats(np.arange(beats) * 0.5)


def guitar(measures, first=1, sustain_at=(), empty=(), thin=()):
    """8th notes from measure `first`; a 1-beat sustain on the first note of each measure in sustain_at; nothing in
    `empty` measures and a single note in `thin` ones."""
    notes = []
    for m in range(first, first + measures):
        if m in empty:
            continue
        for j in range(1 if m in thin else 8):
            notes.append(FretNote(m * M + j * 96, ((m + j) % 5,), RES if (j == 0 and m in sustain_at) else 0))
    return Track("Expert", "Single", notes)


def drums(measures, first=1, sections=(), silent=(), crash_early=()):
    """A rock beat (kick 1 and 3, snare 2 and 4, hi-hat 8ths); a crash and kick on every section downbeat; a tom and
    snare fill in the second half of the measure before each section; nothing in `silent` measures. In crash_early
    measures the downbeat has kick and hi-hat and the crash comes an 8th before it."""
    hits = []
    starts = {s // M for s in sections}
    for m in range(first, first + measures):
        if m in silent:
            continue
        for j in range(8):
            t = m * M + j * 96
            if (m + 1) in starts and j >= 4:
                hits += [DrumHit(t, 2 + j % 3), DrumHit(t + 48, 1)]
                continue
            if m in crash_early and j == 0:
                hits += [DrumHit(t - 96, 0), DrumHit(t - 96, 4, cymbal=True)]
            if j % 4 == 0:
                hits.append(DrumHit(t, 0))
            if j % 4 == 2:
                hits.append(DrumHit(t, 1))
            if m in starts and j == 0 and m not in crash_early:
                hits.append(DrumHit(t, 4, cymbal=True))
            else:
                hits.append(DrumHit(t, 2, cymbal=True))
    hits = {(h.tick, h.pad): h for h in hits}  # one hit per pad per tick
    return Track("Expert", "Drums", sorted(hits.values(), key=lambda h: (h.tick, h.pad)))


def swap(track, drop=(), add=()):
    """The drum track without its hits at the (tick, pad) pairs in drop, plus the hits in add."""
    hits = {(h.tick, h.pad): h for h in track.notes if (h.tick, h.pad) not in set(drop)}
    hits.update({(h.tick, h.pad): h for h in add})
    return Track(track.difficulty, track.instrument, sorted(hits.values(), key=lambda h: (h.tick, h.pad)))


def crash_at(track, *measures):
    """The drum track with a green crash in place of the hi-hat on these downbeats (a kick is already there)."""
    return swap(track, drop=[(m * M, 2) for m in measures], add=[DrumHit(m * M, 4, cymbal=True) for m in measures])


def kinds(track, kind):
    return sorted((p for p in track.phrases if p.kind == kind), key=lambda p: p.tick)


def onsets(track):
    return sorted({n.tick for n in track.notes})


def sec(tm, tick):
    return tm.tick_to_sec(tick)


# ------------------------------------------------------------------------------------------------ star power

def test_star_power_count_shape_and_spacing():
    tm = const_map()
    ex = guitar(120)
    sp = place_star_power(ex, tm)
    on = onsets(ex)
    assert len(sp) == round((on[-1] - on[0]) / RES / 40)  # 476 beats -> 12
    for p in sp:
        assert p.kind == STAR_POWER
        assert p.tick in on                                  # starts on its first note
        assert (p.tick + p.length) % M == 0                  # ends on the next measure line
        assert p.length <= M and p.tick // M == (p.tick + p.length - 1) // M
        assert p.tick >= (on[0] // M + 4) * M                # not in the first 4 measures
        assert p.tick // M <= on[-1] // M - 8                 # nor in the last 8
    starts = [p.tick for p in sp]
    assert all(b - a >= 24 * RES for a, b in zip(starts, starts[1:]))
    assert sp == place_star_power(ex, tm)                   # deterministic
    first_half = sum(p.tick < (on[0] + on[-1]) / 2 for p in sp)
    assert first_half == len(sp) // 2


def test_star_power_prefers_sustains_then_section_starts():
    tm = const_map()
    ex = guitar(40, sustain_at={22})
    assert [p.tick for p in place_star_power(ex, tm, count=1)] == [22 * M]
    assert [p.tick for p in place_star_power(guitar(40), tm, [12 * M], count=1)] == [12 * M]
    # a downbeat start beats a measure whose first note comes late
    late = Track("Expert", "Single", [n for n in guitar(40).notes if not (n.tick // M != 20 and n.tick % M == 0)])
    assert [p.tick for p in place_star_power(late, tm, count=1)] == [20 * M]


def test_star_power_needs_two_onsets_and_obeys_allowed_and_bonus():
    tm = const_map()
    ex = guitar(40, thin=set(range(1, 41)) - {30})    # one note a measure, except measure 30
    assert [p.tick for p in place_star_power(ex, tm, count=3)] == [30 * M]
    ex = guitar(40)
    picked = place_star_power(ex, tm, count=1, bonus=lambda s, e: 5.0 * (s // M == 9))
    assert [p.tick for p in picked] == [9 * M]
    blocked = place_star_power(ex, tm, count=1, bonus=lambda s, e: 5.0 * (s // M == 9),
                               allowed=lambda s, e: not (8 * M <= s < 11 * M))
    assert blocked and not 8 * M <= blocked[0].tick < 11 * M


def test_short_or_empty_parts_get_no_star_power():
    tm = const_map()
    assert place_star_power(guitar(10), tm) == []
    assert place_star_power(Track("Expert", "Single", []), tm) == []
    assert place_star_power(guitar(40), tm, count=0) == []


# ------------------------------------------------------------------------------------------------ fills

SECTIONS = [m * M for m in (1, 17, 33, 49, 65, 81, 97)]


def test_fills_and_star_power_are_scheduled_apart():
    tm = const_map()
    ex = drums(112, sections=SECTIONS)
    sp, fills = schedule_drums(ex, tm, SECTIONS)
    on = set(onsets(ex))
    assert len(sp) >= 8 and len(fills) >= 6
    avail = sp[1].tick + sp[1].length
    for f in fills:
        end = f.tick + f.length
        assert f.kind == DRUM_ACTIVATION
        assert end in on                                     # ends exactly on its activation note
        assert f.tick % M == 0 and f.length == M             # the measure before a measure line
        assert f.tick >= avail                               # only once the player can have star power
        for p in sp:
            assert p.tick + p.length <= f.tick - GAP or p.tick >= end + GAP
            if p.tick + p.length <= f.tick:
                assert sec(tm, end) - sec(tm, p.tick + p.length) >= 2.0
    ends = [f.tick + f.length for f in fills]
    assert all(b - a >= 4 * M for a, b in zip(ends, ends[1:]))
    # every section change after the star power is available has its fill
    for s in SECTIONS[1:]:
        if s - M >= avail and s + 4 * M <= max(on):
            assert s in ends, s
    # once star power can be used, every gap between two phrases holds a fill
    for p, q in zip(sp[1:], sp[2:]):
        assert any(p.tick + p.length < e < q.tick for e in ends)
    assert (sp, fills) == schedule_drums(ex, tm, SECTIONS)  # deterministic
    assert not [i for i in check_phrases([Track("Expert", "Drums", ex.notes, sp + fills)], tm) if i.error]


def test_long_sections_get_more_fills():
    tm = const_map()
    ex = drums(112, sections=SECTIONS[:1])
    sp, fills = schedule_drums(ex, tm, SECTIONS[:1])
    ends = [f.tick + f.length for f in fills]
    assert fills
    starts = [sp[1].tick + sp[1].length] + ends
    assert max(b - a for a, b in zip(starts, starts[1:])) <= (FILL_RULES.period_measures + 2) * M


def test_activation_prefers_a_crash_within_an_eighth():
    tm = const_map()
    line = 9 * M
    ex = drums(20, sections=[line], crash_early={9})
    spans = [(f.tick, f.tick + f.length) for f in place_fills(ex, tm, [line], star_power=[])]
    assert (8 * M, line - 96) in spans
    assert not [s for s in spans if s[1] == line]


def test_activation_stays_on_the_line_unless_a_crash_with_a_kick_or_snare_is_near():
    tm = const_map()
    line = 9 * M
    base = drums(20, sections=[line])            # kick and green crash on the section's downbeat

    def ends(ex):
        return [f.tick + f.length for f in place_fills(ex, tm, [line], star_power=[])]

    # kick and hi-hat on the line: a lone crash an 8th later does not move the end off it
    lone = swap(base, drop=[(line, 4)], add=[DrumHit(line, 2, cymbal=True), DrumHit(line + 96, 3, cymbal=True)])
    assert line in ends(lone) and line + 96 not in ends(lone)
    # a crash on the line keeps it, even against a crash and kick an 8th later
    crash = swap(base, drop=[(line, 0)], add=[DrumHit(line + 96, 0), DrumHit(line + 96, 3, cymbal=True)])
    assert line in ends(crash) and line + 96 not in ends(crash)
    # no note on the line: a crash within an 8th before the nearer hand hits
    empty = swap(base, drop=[(line, 0), (line, 4)], add=[DrumHit(line + 96, 3, cymbal=True)])
    assert line + 96 in ends(empty)


def test_fills_every_four_measures_resume_after_a_stretch_that_allows_none():
    tm = const_map()
    ex = drums(60, sections=[9 * M], silent=set(range(17, 37)))
    ends = [f.tick + f.length for f in place_fills(ex, tm, [9 * M], star_power=[])]
    assert FILL_RULES.period_measures == 4
    # the line 4 measures after the section's fill takes one before the 20 silent measures; the next is the first
    # line after them with a measure of drums before it
    assert [e // M for e in ends] == [2, 9, 13, 38, 42, 46, 50, 54]
    # a period of 8 never tried the lines 4-7 measures after the fill
    eight = [f.tick + f.length for f in place_fills(ex, tm, [9 * M], star_power=[], rules=FillRules(period_measures=8))]
    assert not [e for e in eight if 9 * M < e < 17 * M]


def test_a_crash_line_is_preferred_among_the_lines_a_fill_may_take():
    tm = const_map()
    base = drums(40)                              # no crash anywhere
    # the period step: a crash a measure after the line where a fill is due takes it
    assert [f.tick + f.length for f in place_fills(base, tm, star_power=[])][:3] == [2 * M, 6 * M, 10 * M]
    ex = crash_at(base, 7)
    assert [f.tick + f.length for f in place_fills(ex, tm, star_power=[])][:3] == [2 * M, 7 * M, 11 * M]
    # the gap step: in a star-power gap without a fill (lines 11-16 allow one), a crash line before the earliest
    sp = [Phrase(4 * M, M, STAR_POWER), Phrase(8 * M, M, STAR_POWER), Phrase(17 * M, M, STAR_POWER)]

    def in_gap(track):
        return [f.tick + f.length for f in place_fills(track, tm, star_power=sp) if 9 * M < f.tick + f.length < 17 * M]

    assert in_gap(base) == [11 * M, 15 * M]
    assert in_gap(crash_at(base, 14)) == [14 * M]
    # a crash is never required: a part without one still gets its fills
    assert len(place_fills(base, tm, star_power=sp)) >= 6


def test_no_fill_over_silence_or_near_the_end():
    tm = const_map()
    ex = drums(30, sections=[9 * M, 28 * M], silent={8})
    ends = [f.tick + f.length for f in place_fills(ex, tm, [9 * M, 28 * M], star_power=[])]
    assert ends and not [e for e in ends if abs(e - 9 * M) <= 96 or e > 26 * M]
    # the track's own star power is used when none is given: no fill comes near it
    sp = Phrase(9 * M, M, STAR_POWER)
    ex = Track("Expert", "Drums", drums(30, sections=[9 * M]).notes, [sp])
    fills = place_fills(ex, tm, [9 * M])
    assert fills and all(f.tick >= sp.tick + sp.length + GAP for f in fills)  # and none before it is usable
    with pytest.raises(ValueError):
        place_fills(guitar(10), tm)


def sparse_drums(beats, measures=70):
    """Two snare hits a measure at the given beat positions: too thin for the usual fills."""
    return Track("Expert", "Drums", [DrumHit(m * M + round(b * RES), 1) for m in range(1, measures + 1)
                                     for b in beats])


def test_a_sparse_part_gets_looser_fills_or_no_star_power():
    tm = const_map()
    ex = sparse_drums((0, 2))                 # 8 hits in 4 measures: under the usual 16
    sp, fills = schedule_drums(ex, tm)
    assert sp and fills
    assert all(f.tick + f.length in set(onsets(ex)) for f in fills)
    assert not [i for i in check_phrases([Track("Expert", "Drums", ex.notes, sp + fills)], tm) if i.error]
    ex = sparse_drums((1.75, 2.25))          # nothing within a beat of any measure line
    assert schedule_drums(ex, tm) == ([], [])


def test_a_level_keeps_short_fills_rather_than_none():
    tm = const_map()
    ex = Track("Expert", "Drums", drums(40).notes, [Phrase(10 * M, M, STAR_POWER), Phrase(19 * M, M, DRUM_ACTIVATION)])
    lower = Track("Easy", "Drums", [DrumHit(10 * M, 1), DrumHit(19 * M + 96, 1)])
    got = kinds(fit_phrases(lower, tm, source=ex), DRUM_ACTIVATION)
    assert [(f.tick, f.length) for f in got] == [(19 * M, 96)]


def test_no_star_power_means_fills_are_kept_from_the_start():
    tm = const_map()
    ex = drums(40, sections=[9 * M])
    fills = place_fills(ex, tm, [9 * M], star_power=[])
    ends = [f.tick + f.length for f in fills]
    assert ends[0] == 2 * M and 9 * M in ends  # the first line that allows one, and the section change
    assert all(b - a >= FILL_RULES.min_gap_measures * M for a, b in zip(ends, ends[1:]))


# ------------------------------------------------------------------------------------------------ solos

def test_solos_come_from_confirmed_solo_sections():
    tm = const_map()
    ex = guitar(40)
    secs = [(1 * M, "Intro"), (9 * M, "Solo 1A"), (17 * M, "Solo 1B"), (25 * M, "Verse"), (33 * M, "Guitar Solo")]
    assert solo_sections(secs, 41 * M) == [(9 * M, 25 * M), (33 * M, 41 * M)]
    uncapped = SoloRules(max_share=1.0)
    assert place_solos(ex, tm, secs, rules=uncapped) == [(9 * M, 25 * M - 96), (33 * M, 40 * M + 7 * 96)]
    # the two are 0.60 of this song: the default share cap (0.40) keeps the first, as dense and earlier
    assert place_solos(ex, tm, secs) == [(9 * M, 25 * M - 96)]
    # a section the caller rejects is left out, and its neighbours are no longer joined
    no_1b = place_solos(ex, tm, secs, confirm=lambda a, b: a != 17 * M)
    assert no_1b == [(9 * M, 17 * M - 96), (33 * M, 40 * M + 7 * 96)]
    assert place_solos(ex, tm, [(1 * M, "Verse"), (9 * M, "Chorus")]) == []
    # too few notes or too short: no solo
    assert place_solos(guitar(40, thin=set(range(9, 17))), tm, [(9 * M, "Solo"), (17 * M, "Verse")]) == []
    assert place_solos(ex, tm, [(9 * M, "Solo"), (12 * M, "Verse")]) == []


def test_solos_on_the_sections_a_person_named():
    """names: exactly the named sections, whatever their label and whatever confirm says; the minimums still hold."""
    tm = const_map()
    ex = guitar(40)
    secs = [(1 * M, "Intro"), (9 * M, "Solo 1"), (17 * M, "Verse"), (25 * M, "Solo 2"), (33 * M, "Bridge")]
    assert solo_sections(secs, 41 * M, names=["Solo 1", "Bridge"]) == [(9 * M, 17 * M), (33 * M, 41 * M)]
    assert solo_sections(secs, 41 * M, names=["Solo 1"], confirm=lambda a, b: False) == [(9 * M, 17 * M)]
    assert solo_sections(secs, 41 * M, names=["Solo 3"]) == []
    assert place_solos(ex, tm, secs, names=["Solo 2"]) == [(25 * M, 33 * M - 96)]
    # adjacent named sections are still one solo, and a named section with too few notes gets none
    assert solo_sections(secs, 41 * M, names=["Solo 1", "Verse"]) == [(9 * M, 25 * M)]
    assert place_solos(guitar(40, thin=set(range(9, 17))), tm, secs, names=["Solo 1"]) == []
    # through place_phrases: only Expert lead guitar gets them
    chart = Chart(SongInfo("t", "a"), tm, secs, [ex, Track("Expert", "DoubleBass", list(ex.notes))])
    placed = place_phrases(chart, solos=True, solo_names=["Solo 1", "Solo 2"])
    assert [t.solos for t in placed.tracks] == [[(9 * M, 17 * M - 96), (25 * M, 33 * M - 96)], []]


def test_at_most_three_solos_with_the_most_notes():
    tm = const_map()
    ex = guitar(80, thin=set(range(41, 46)))
    secs = []
    for i, m in enumerate(range(1, 81, 8)):
        secs.append((m * M, "Solo" if i % 2 else "Verse"))
    got = place_solos(ex, tm, secs)
    assert len(got) == 3
    assert all(a // M != 41 for a, _ in got)  # the thin one (measures 41-48) is not among them


def lettered(first, lengths, name="Solo 2"):
    """Sections: an Intro at measure 1, then parts of the given lengths in measures from `first` ("Solo 2A", "Solo
    2B", ...), then an Outro."""
    secs, m = [(1 * M, "Intro")], first
    for i, n in enumerate(lengths):
        secs.append((m * M, f"{name}{chr(65 + i)}"))
        m += n
    return secs + [(m * M, "Outro")]


def spans(cands, measure=M):
    """Candidates as (first measure, measures)."""
    return [(a // measure, (b - a) // measure) for a, b in cands]


def test_a_long_solo_run_is_split_into_parts_within_the_caps():
    """Parts are grouped from the run's start while the group stays within both caps; a part over a cap on its own is
    cut at the measure line where the first cap is reached; a run within both is one candidate. Without a tempo map,
    or with a person's names, nothing is split."""
    tm = const_map()                                     # 120 BPM: a measure is 2 s
    rules = SoloRules(max_measures=32, max_seconds=1000)
    end = 300 * M

    def cands(lengths):
        return spans(solo_sections(lettered(9, lengths), end, tempo=tm, rules=rules))

    assert cands([20] * 5) == [(9, 20), (29, 20), (49, 20), (69, 20), (89, 20)]   # two would make 40
    assert cands([8] * 10) == [(9, 32), (41, 32), (73, 16)]                         # groups of four, four and two
    assert cands([50]) == [(9, 32), (41, 18)]
    assert cands([15, 15]) == [(9, 30)]
    assert cands([100]) == [(9, 32), (41, 32), (73, 32), (105, 4)]                 # the rest is cut again
    assert cands([10, 50, 10]) == [(9, 10), (19, 32), (51, 18), (69, 10)]          # the rest is its own candidate
    assert spans(solo_sections(lettered(9, [8] * 10), end, rules=rules)) == [(9, 80)]       # no tempo map
    named = [f"Solo 2{c}" for c in "ABCDEFGHIJ"]
    assert spans(solo_sections(lettered(9, [8] * 10), end, names=named, tempo=tm, rules=rules)) == [(9, 80)]
    # the default caps: 56 measures, 100 s (50 measures here)
    assert spans(solo_sections(lettered(9, [60]), end, tempo=tm)) == [(9, 50), (59, 10)]
    assert SOLO_RULES.max_measures == 56 and SOLO_RULES.max_seconds == 100 and SOLO_RULES.max_share == 0.40


def test_a_run_is_cut_at_the_seconds_cap_on_a_fast_map():
    """At 240 BPM a measure is 1 s: with max_seconds 30 a 40-measure run is cut at 30 measures although it is within
    max_measures, and two 20-measure parts are two candidates."""
    fast = TempoMap.from_beats(np.arange(1200) * 0.25)
    rules = SoloRules(max_seconds=30)
    assert rules.max_measures >= 40
    assert spans(solo_sections(lettered(9, [40]), 200 * M, tempo=fast, rules=rules)) == [(9, 30), (39, 10)]
    assert spans(solo_sections(lettered(9, [20, 20]), 200 * M, tempo=fast, rules=rules)) == [(9, 20), (29, 20)]
    assert spans(solo_sections(lettered(9, [40]), 200 * M, tempo=fast)) == [(9, 40)]   # 40 s: within the defaults


def density(per_measure, measures=100, filler=2):
    """Expert guitar from measure 1 to `measures`: `per_measure[m]` evenly spaced notes in measure m, else `filler`."""
    notes = []
    for m in range(1, measures + 1):
        n = per_measure.get(m, filler)
        notes += [FretNote(m * M + j * M // n, (j % 5,)) for j in range(n)]
    return Track("Expert", "Single", notes)


def runs_at(*runs):
    """Sections: separate solo runs (first measure, measures), a Verse between and after them."""
    secs = [(1 * M, "Intro")]
    for i, (m, n) in enumerate(runs):
        secs += [(m * M, f"Solo {i + 1}"), ((m + n) * M, f"Verse {i + 1}")]
    return secs


def test_the_densest_solos_win():
    """Ranked by Expert onsets per measure, not by onsets: the long sparse run with the most onsets loses; a tie goes
    to the earlier start; the result is sorted by start."""
    tm = const_map()
    runs = {"sparse": (11, 24, 4), "b": (41, 8, 8), "c": (55, 8, 12), "d": (69, 4, 16), "e": (79, 8, 6),
            "f": (93, 8, 8)}                      # first measure, measures, notes a measure; 6 measures apart
    ex = density({m: n for first, k, n in runs.values() for m in range(first, first + k)}, measures=110)
    secs = runs_at(*((first, k) for first, k, _ in runs.values()))
    got = place_solos(ex, tm, secs, rules=SoloRules(max_share=1.0))
    assert [a // M for a, _ in got] == [41, 55, 69]   # d (16), c (12), then b (8) before f (8)


def test_the_share_cap_skips_a_solo_and_takes_the_next_that_fits():
    """max_share 0.25 of the first..last onset's 199 s is 49.75 s: the two densest take 39.7 s, the third (23.8 s)
    would pass it and is skipped, the fourth (7.8 s) fits. The record says what was used and why; a person's names
    are neither split nor capped."""
    tm = const_map()
    runs = [(11, 10, 16), (31, 10, 14), (51, 12, 12), (71, 4, 10)]    # first measure, measures, notes a measure
    ex = density({m: n for first, k, n in runs for m in range(first, first + k)})
    secs = runs_at(*((first, k) for first, k, _ in runs))
    rules = SoloRules(max_share=0.25)
    record = {}
    got = place_solos(ex, tm, secs, rules=rules, record=record)
    assert [a // M for a, _ in got] == [11, 31, 71]
    assert record["rules"] == {"min_measures": 4, "min_onsets": 16, "max_solos": 3, "max_measures": 56,
                               "max_seconds": 100.0, "max_share": 0.25, "min_gap_measures": 4.0}
    assert record["capped"] and record["skipped_by_gap"] == []
    assert [(r["start"], r["end"], r["measures"], r["onsets"]) for r in record["solos"]] == [
        (a, b, k, k * n) for (a, b), (_, k, n) in zip(got, (runs[0], runs[1], runs[3]))]
    assert record["solos"][0]["per_measure"] == 16.0
    assert [(r["start"] // M, r["measures"], r["onsets"]) for r in record["skipped_by_share"]] == [(51, 12, 144)]
    assert place_solos(ex, tm, secs, rules=SoloRules(max_share=0.40)) == sorted(got[:2] + [
        (51 * M, 63 * M - M // 12)])                                     # 63.6 s: within 0.40 (79.6 s)
    # names: one 60-measure, 120-s run over every cap and 0.60 of the song, taken whole
    long = density({m: 8 for m in range(21, 81)})
    named = lettered(21, [20, 20, 20], "Lead ")
    tight = SoloRules(max_measures=32, max_seconds=30, max_share=0.25)
    assert place_solos(long, tm, named, rules=tight) == []                # no section named Solo
    record = {}
    got = place_solos(long, tm, named, names=["Lead A", "Lead B", "Lead C"], rules=tight, record=record)
    assert got == [(21 * M, 81 * M - 96)] and not record["capped"]
    assert record["skipped_by_share"] == record["skipped_by_gap"] == []
    # through place_phrases, on Expert lead guitar
    record = {}
    chart = Chart(SongInfo("t", "a"), tm, secs, [ex])
    assert place_phrases(chart, solos=True, solo_rules=rules, solo_record=record).tracks[0].solos == \
        place_solos(ex, tm, secs, rules=rules)
    assert len(record["solos"]) == 3 and len(record["skipped_by_share"]) == 1


def test_the_parts_of_a_split_run_never_come_back_to_back():
    """At 100 BPM (2.4 s a measure) a 34 + 8-measure run (100.8 s) is split at the seconds cap into 81.6 and 19.2 s:
    only the denser part is kept, whichever side of the other it is on. Two runs 6 measures apart are both kept, 3
    apart only the denser; a person's names are exempt."""
    tm = TempoMap.from_beats(np.arange(1200) * 0.6)

    def kept(lengths, dens, names=None, gap=None, record=None):
        if gap is None:
            secs = lettered(21, lengths, "Solo ")
            parts = [(21, lengths[0]), (21 + lengths[0], lengths[1])]
        else:   # two runs, `gap` measures of verse between them
            secs = [(1 * M, "Intro"), (21 * M, "Solo 1"), ((21 + lengths[0]) * M, "Verse"),
                    ((21 + lengths[0] + gap) * M, "Solo 2"), ((21 + lengths[0] + gap + lengths[1]) * M, "Outro")]
            parts = [(21, lengths[0]), (21 + lengths[0] + gap, lengths[1])]
        ex = density({m: n for (first, k), n in zip(parts, dens) for m in range(first, first + k)}, measures=120)
        return [(a // M, round((b - a) / M)) for a, b in place_solos(ex, tm, secs, names=names, record=record)]

    record = {}
    assert kept([34, 8], [12, 8], record=record) == [(21, 34)]        # the later part starts right after it ends
    assert [(r["start"] // M, r["measures"]) for r in record["skipped_by_gap"]] == [(55, 8)]
    assert record["skipped_by_share"] == []
    assert kept([34, 8], [8, 12]) == [(55, 8)]                         # the earlier part ends right before it starts
    assert kept([20, 20], [12, 8], gap=6) == [(21, 20), (47, 20)]
    assert kept([20, 20], [12, 8], gap=3) == [(21, 20)]
    assert kept([20, 20], [8, 12], gap=3) == [(44, 20)]
    assert kept([20, 20], [12, 8], gap=3, names=["Solo 1", "Solo 2"]) == [(21, 20), (44, 20)]


def test_stem_confirm():
    tm = const_map()
    pad = 1.0
    frame = 0.1
    vocals = np.full(1000, -20.0)
    vocals[200:400] = -70.0      # input 20-40 s: no singing
    lead = np.linspace(-40.0, -20.0, 1000)
    lead[200:260] = -5.0         # input 20-26 s: loud guitar

    def ticks(a, b):
        return round(tm.sec_to_tick(a + pad)), round(tm.sec_to_tick(b + pad))

    quiet = stem_confirm(tm, pad, frame, vocals)
    assert quiet(*ticks(20, 40)) and not quiet(*ticks(40, 60)) and not quiet(*ticks(10, 40))
    loud = stem_confirm(tm, pad, frame, vocals, lead)
    assert loud(*ticks(20, 26)) and not loud(*ticks(20, 40))
    assert not quiet(*ticks(200, 210))  # past the end of the levels


# ------------------------------------------------------------------------------------------------ lower levels

def test_fit_phrases_fits_star_power_fills_and_solos_to_the_level():
    tm = const_map()
    ex = Track("Expert", "Drums", drums(40).notes,
               [Phrase(10 * M, M, STAR_POWER), Phrase(14 * M, M, STAR_POWER), Phrase(19 * M, M, DRUM_ACTIVATION),
                Phrase(25 * M, M, DRUM_ACTIVATION), Phrase(30 * M, 2 * M, ROLL)], [(33 * M, 35 * M)])
    lower = [DrumHit(t, 1) for t in (11 * M + 96,                    # half a beat after the first phrase
                                     19 * M, 19 * M + 288,           # the first fill keeps 1.5 beats
                                     25 * M + 96, 26 * M + 96)]     # the second keeps only half a beat
    hard = fit_phrases(Track("Hard", "Drums", lower), tm, source=ex)
    sp = kinds(hard, STAR_POWER)
    assert [(p.tick, p.tick + p.length) for p in sp] == [(10 * M, 11 * M + 97)]   # stretched; the second dropped
    assert [(f.tick, f.tick + f.length) for f in kinds(hard, DRUM_ACTIVATION)] == [(19 * M, 19 * M + 288)]
    assert kinds(hard, ROLL) == [Phrase(30 * M, 2 * M, ROLL)]
    assert hard.solos == []                                                       # no note in it on this level
    assert not [i for i in check_phrases([hard], tm) if i.kind in ("emptyStarPower", "fillEnd")]


def test_fit_phrases_does_not_stretch_into_a_neighbour():
    tm = const_map()
    ex = Track("Expert", "Single", guitar(30).notes, [Phrase(10 * M, M, STAR_POWER), Phrase(11 * M, M, STAR_POWER)])
    # the only nearby note sits in the next phrase
    got = fit_phrases(Track("Hard", "Single", [FretNote(11 * M, (0,))]), tm, source=ex)
    assert [(p.tick, p.length) for p in kinds(got, STAR_POWER)] == [(11 * M, M)]


def song_chart():
    secs = [(m * M, n) for m, n in ((1, "Intro"), (17, "Verse 1"), (33, "Chorus 1"), (49, "Solo"), (65, "Verse 2"),
                                     (81, "Chorus 2"), (97, "Outro"))]
    starts = [t for t, _ in secs]
    gtr = guitar(112, sustain_at=set(range(1, 113, 3)))
    bass = Track("Expert", "DoubleBass", [FretNote(n.tick, (n.frets[0] % 4,)) for n in gtr.notes if n.tick % RES == 0])
    drum = drums(112, sections=starts)
    tool_sp = [Phrase(5 * M, M, STAR_POWER)]
    gtr = Track("Expert", "Single", gtr.notes, tool_sp + [Phrase(40 * M, M, ROLL)])
    return Chart(SongInfo("Synthetic", "Nobody"), const_map(), secs, [gtr, bass, drum])


def test_the_full_ladder_keeps_every_phrase_playable(tmp_path):
    chart = song_chart()
    placed = place_phrases(chart, solos=True)
    ex = {t.instrument: t for t in placed.tracks}
    assert Phrase(5 * M, M, STAR_POWER) not in ex["Single"].phrases          # the tool's phrase is replaced
    assert Phrase(40 * M, M, ROLL) in ex["Single"].phrases                    # other kinds are kept
    assert ex["Single"].solos and not ex["DoubleBass"].solos and not ex["Drums"].solos
    final = fit_chart(reduce_chart(placed))
    tm = final.tempo
    for inst in ("Single", "DoubleBass", "Drums"):
        trs = [t for t in final.tracks if t.instrument == inst]
        assert [t.difficulty for t in trs] == ["Expert", "Hard", "Medium", "Easy"]
        errors = [i for i in check_phrases(trs, tm) if i.error]
        assert errors == [], (inst, errors)
        assert not [i for i in check_reductions(trs, tm) if i.kind == "emptyStarPower"]
        for t in trs:
            assert kinds(t, STAR_POWER), t.name
            if t.is_drums:
                fills = kinds(t, DRUM_ACTIVATION)
                assert fills, t.name                                           # every drum level has fills
                on = set(onsets(t))
                assert all(f.tick + f.length in on for f in fills)
    # written and read back, every level keeps its phrases
    path = tmp_path / "notes.chart"
    path.write_text(write_chart(final), encoding="utf-8", newline="")
    back = read_chart(path)
    for t in final.tracks:
        inst = {"Single": "guitar", "DoubleBass": "bass", "Drums": "drums"}[t.instrument]
        part = back.parts[(inst, t.difficulty.lower())]
        assert len(part.star_power) == len(kinds(t, STAR_POWER))
        assert len(part.activation) == len(kinds(t, DRUM_ACTIVATION))
        assert len(part.solos) == len(t.solos)


def test_place_phrases_fits_lower_tracks_already_there():
    chart = song_chart()
    hard = Track("Hard", "Single", [n for n in chart.tracks[0].notes if n.tick % RES == 0])
    chart = Chart(chart.info, chart.tempo, chart.sections, chart.tracks + [hard])
    placed = place_phrases(chart)
    got = placed.track("Hard", "Single")
    assert kinds(got, STAR_POWER) and not got.solos  # solos are off by default
    assert not [i for i in check_phrases([placed.track("Expert", "Single"), got], chart.tempo) if i.error]


# ------------------------------------------------------------------------------------------------ checks

def test_check_phrases_flags_what_scan_chart_and_our_rules_reject():
    tm = const_map()
    notes = drums(40).notes
    on = set(h.tick for h in notes)
    issues = check_phrases([Track("Expert", "Drums", notes, [Phrase(10 * M, M, STAR_POWER)])], tm)
    assert [i.kind for i in issues] == ["noDrumActivationLanes"]
    bad = Track("Expert", "Drums", [h for h in notes if not 20 * M <= h.tick < 21 * M], [
        Phrase(20 * M, M, STAR_POWER),                        # empty
        Phrase(25 * M, M - 1, DRUM_ACTIVATION),               # does not end on a note
        Phrase(29 * M, M, DRUM_ACTIVATION), Phrase(30 * M, M, STAR_POWER),   # touches star power
        Phrase(35 * M, M, DRUM_ACTIVATION), Phrase(34 * M, M - RES, STAR_POWER)])  # ends a beat before it
    assert 26 * M - 1 not in on
    kinds_ = sorted((i.kind, i.error) for i in check_phrases([bad], tm))
    assert ("emptyStarPower", True) in kinds_
    assert ("fillEnd", True) in kinds_
    assert ("fillOverlapsStarPower", True) in kinds_
    assert ("fillNearStarPower", False) in kinds_
    gtr = guitar(40)
    assert [i.kind for i in check_phrases([gtr], tm)] == ["noStarPower"]
    solo = Track("Expert", "Single", gtr.notes, [Phrase(10 * M, M, STAR_POWER), Phrase(10 * M + 96, M, STAR_POWER)],
                 [(50 * M, 52 * M)])
    assert sorted(i.kind for i in check_phrases([solo], tm)) == ["emptySoloSection", "starPowerOverlap"]


def test_check_phrases_warns_when_few_fills_end_on_a_crash():
    tm = const_map()
    ex = drums(40)
    phrases = [Phrase(4 * M, M, STAR_POWER), Phrase(8 * M, M, STAR_POWER)] + \
        [Phrase(m * M, M, DRUM_ACTIVATION) for m in (12, 16, 20)]           # ending on 13, 17 and 21

    def warned(track):
        return [i for i in check_phrases([track], tm) if i.kind == "fillNoCrash"]

    hats = warned(Track("Expert", "Drums", ex.notes, phrases))
    assert len(hats) == 1 and not hats[0].error and "0.00" in hats[0].message
    assert not warned(Track("Expert", "Drums", crash_at(ex, 13, 17).notes, phrases))   # 2 of 3
    assert warned(Track("Expert", "Drums", crash_at(ex, 13).notes, phrases))           # 1 of 3
    assert not warned(Track("Hard", "Drums", ex.notes, phrases))                        # Expert only
    assert fill_crash_share(Track("Expert", "Drums", crash_at(ex, 13).notes, phrases), tm) == pytest.approx(1 / 3)
    assert fill_crash_share(ex, tm) is None


def test_rules_are_parameters():
    tm = const_map()
    ex = drums(112, sections=SECTIONS)
    sp, fills = schedule_drums(ex, tm, SECTIONS)
    _, fewer = schedule_drums(ex, tm, SECTIONS, fill_rules=FillRules(period_measures=8))
    assert len(fills) > len(fewer)
