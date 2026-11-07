"""Sections: synthetic allin1 segments and imported section lists placed on measure lines (snapping, merges of short
segments, Clone Hero naming, optional splits, other meters)."""
import json

import numpy as np
import pytest

from songcharter.errors import InputError
from songcharter.sections import (Segment, clean_name, label_name, read_allin1, read_allin1_beats,
                                  read_allin1_downbeats, sections_from_chart, sections_from_segments)
from songcharter.tempo import TempoMap

RES = 192
M = 4 * RES   # ticks per 4/4 measure
PAD = 1.0     # seconds of lead-in: input second t sits at t + PAD on the map


def const_map(bpm=120.0, beats=600, bars=None):
    """120 BPM: a beat is 0.5 s and a 4/4 measure 2 s, so input second t is map second t + PAD."""
    return TempoMap.from_beats(np.arange(beats) * 60 / bpm, bars=bars)


def seg(start, end, label):
    return Segment(start, end, label)


def at_measure(m, s=0.0):
    """Input second of measure m's start on const_map, plus s seconds."""
    return 2.0 * m - PAD + s


def test_read_allin1_lists_and_objects(tmp_path):
    a = tmp_path / "a.json"
    b = tmp_path / "b.json"
    a.write_text(json.dumps({"bpm": 120, "segments": [[4.0, 9.0, "Verse"], [0.0, 4.0, "intro"]]}))
    b.write_text(json.dumps({"segments": [{"start": 0.0, "end": 4.0, "label": "intro"},
                                          {"start": 4.0, "end": 9.0, "label": "verse"}]}))
    want = [Segment(0.0, 4.0, "intro"), Segment(4.0, 9.0, "verse")]
    assert read_allin1(a) == want
    assert read_allin1(b) == want
    c = tmp_path / "c.json"  # saved by an editor that writes a BOM
    c.write_text("﻿" + b.read_text(), encoding="utf-8")
    assert read_allin1(c) == want
    for data, message in (({"sections": []}, "no 'segments' list"), ([], "no 'segments' list"),
                          ({"segments": [[0.0, 4.0]]}, "segment 0"), ({"segments": [{"start": 0.0}]}, "segment 0"),
                          ({"segments": [[0.0, "x", "intro"]]}, "segment 0")):
        c.write_text(json.dumps(data), encoding="utf-8")
        with pytest.raises(ValueError, match=message):
            read_allin1(c)


def test_read_allin1_beats(tmp_path):
    """allin1's beats when the result holds them (sorted, repeats dropped), None when it holds none: the librosa
    fallback writes only segments, and an empty or null list is none. Anything else is a bad input."""
    p = tmp_path / "segments.json"
    segments = [[0.0, 4.0, "intro"]]
    p.write_text(json.dumps({"segments": segments, "bpm": 100, "beats": [0.6, 0.0, 1.2, 0.6, 1.8],
                             "downbeats": [0.0]}), encoding="utf-8")
    assert read_allin1_beats(p).tolist() == [0.0, 0.6, 1.2, 1.8]
    for none in ({"segments": segments}, {"segments": segments, "beats": []}, {"segments": segments, "beats": None}):
        p.write_text(json.dumps(none), encoding="utf-8")
        assert read_allin1_beats(p) is None
    for bad in (["x", 1.0], [[0.0, 1.0], [2.0, 3.0]], 3.0, "0.5"):
        p.write_text(json.dumps({"segments": segments, "beats": bad}), encoding="utf-8")
        with pytest.raises(InputError, match="'beats' is not a list of"):
            read_allin1_beats(p)
    p.write_text('{"segments": [], "beats": [0.0, NaN]}', encoding="utf-8")
    with pytest.raises(InputError, match="finite"):
        read_allin1_beats(p)


def test_read_allin1_downbeats(tmp_path):
    """allin1's downbeats, read as its beats are: sorted, repeats dropped, None when there are none (the librosa
    fallback), anything but a list of finite times a bad input."""
    p = tmp_path / "segments.json"
    segments = [[0.0, 4.0, "intro"]]
    p.write_text(json.dumps({"segments": segments, "beats": [0.0, 0.6], "downbeats": [2.4, 0.0, 2.4]}),
                 encoding="utf-8")
    assert read_allin1_downbeats(p).tolist() == [0.0, 2.4] and read_allin1_beats(p).tolist() == [0.0, 0.6]
    for none in ({"segments": segments, "beats": [0.0]}, {"segments": segments, "downbeats": []},
                 {"segments": segments, "downbeats": None}):
        p.write_text(json.dumps(none), encoding="utf-8")
        assert read_allin1_downbeats(p) is None
    for bad in (["x", 1.0], [[0.0, 1.0]], 3.0):
        p.write_text(json.dumps({"segments": segments, "downbeats": bad}), encoding="utf-8")
        with pytest.raises(InputError, match="'downbeats' is not a list of"):
            read_allin1_downbeats(p)
    p.write_text('{"segments": [], "downbeats": [Infinity]}', encoding="utf-8")
    with pytest.raises(InputError, match="'downbeats' is not a list of finite times"):
        read_allin1_downbeats(p)


def test_starts_snap_to_the_nearest_measure_and_silence_is_dropped():
    tm = const_map()
    segs = [seg(0.0, 0.3, "start"), seg(0.3, at_measure(5, 0.4), "intro"),
            seg(at_measure(5, 0.4), at_measure(13, -0.7), "verse"),
            seg(at_measure(13, -0.7), at_measure(21), "chorus"), seg(at_measure(21), at_measure(23), "end")]
    out = sections_from_segments(segs, tm, PAD)
    # intro at map 1.3 s: measure 1 (2.0 s) is nearer than measure 0
    assert out == [(1 * M, "Intro"), (5 * M, "Verse"), (13 * M, "Chorus")]


def test_a_tie_snaps_to_the_earlier_measure():
    tm = const_map()
    out = sections_from_segments([seg(at_measure(3), at_measure(8, 1.0), "verse"),
                                  seg(at_measure(8, 1.0), at_measure(16), "chorus")], tm, PAD)
    assert out == [(3 * M, "Verse"), (8 * M, "Chorus")]


def test_repeated_labels_are_numbered_and_runs_get_part_letters():
    tm = const_map()
    labels = ["intro", "verse", "chorus", "verse", "chorus", "chorus", "inst", "solo", "outro"]
    segs = [seg(at_measure(1 + 4 * i), at_measure(5 + 4 * i), lab) for i, lab in enumerate(labels)]
    names = [n for _, n in sections_from_segments(segs, tm, PAD)]
    assert names == ["Intro", "Verse 1", "Chorus 1", "Verse 2", "Chorus 2A", "Chorus 2B", "Instrumental", "Solo",
                     "Outro"]


def test_a_run_of_one_label_gets_letters_without_a_number():
    tm = const_map()
    segs = [seg(at_measure(1), at_measure(9), "intro"), seg(at_measure(9), at_measure(17), "intro"),
            seg(at_measure(17), at_measure(25), "verse")]
    assert [n for _, n in sections_from_segments(segs, tm, PAD)] == ["Intro A", "Intro B", "Verse"]


def test_short_segments_merge_into_the_one_before():
    tm = const_map()
    segs = [seg(at_measure(1), at_measure(9), "verse"), seg(at_measure(9), at_measure(10), "break"),  # 1 measure
            seg(at_measure(10), at_measure(18), "chorus")]
    assert sections_from_segments(segs, tm, PAD) == [(1 * M, "Verse"), (10 * M, "Chorus")]


def test_a_short_first_segment_merges_into_the_next():
    tm = const_map()
    segs = [seg(at_measure(1), at_measure(2), "intro"), seg(at_measure(2), at_measure(10), "verse"),
            seg(at_measure(10), at_measure(18), "chorus")]
    assert sections_from_segments(segs, tm, PAD) == [(1 * M, "Verse"), (10 * M, "Chorus")]


def test_starts_that_snap_together_leave_one_section():
    tm = const_map()
    segs = [seg(at_measure(1), at_measure(9, -0.3), "verse"), seg(at_measure(9, -0.3), at_measure(9, 0.3), "break"),
            seg(at_measure(9, 0.3), at_measure(17), "chorus")]
    assert sections_from_segments(segs, tm, PAD) == [(1 * M, "Verse"), (9 * M, "Chorus")]


def test_a_short_last_segment_merges_into_the_one_before():
    tm = const_map()
    segs = [seg(at_measure(1), at_measure(9), "verse"), seg(at_measure(9), at_measure(17), "chorus"),
            seg(at_measure(17), at_measure(18), "outro")]
    assert sections_from_segments(segs, tm, PAD) == [(1 * M, "Verse"), (9 * M, "Chorus")]


def test_min_measures_is_a_parameter():
    tm = const_map()
    segs = [seg(at_measure(1), at_measure(4), "verse"), seg(at_measure(4), at_measure(12), "chorus")]
    assert len(sections_from_segments(segs, tm, PAD)) == 2
    assert sections_from_segments(segs, tm, PAD, min_measures=4) == [(1 * M, "Chorus")]


def test_long_segments_split_on_request():
    tm = const_map()
    segs = [seg(at_measure(1), at_measure(21), "verse"), seg(at_measure(21), at_measure(29), "chorus"),
            seg(at_measure(29), at_measure(47), "verse")]
    assert [n for _, n in sections_from_segments(segs, tm, PAD)] == ["Verse 1", "Chorus", "Verse 2"]
    out = sections_from_segments(segs, tm, PAD, split_over=16, split_into=8)
    # 20 measures -> 2 parts of 10; 18 -> 2 parts of 9
    assert out == [(1 * M, "Verse 1A"), (11 * M, "Verse 1B"), (21 * M, "Chorus"), (29 * M, "Verse 2A"),
                   (38 * M, "Verse 2B")]


def test_a_run_of_one_label_splits_as_one_segment():
    """DESIGN.md 2.5 merges a run of one label, then splits it: a verse of 18 + 10 measures is four parts of 7, not
    9/9/10; an intro of 8 + 6 is one section."""
    tm = const_map()
    segs = [seg(at_measure(1), at_measure(9), "intro"), seg(at_measure(9), at_measure(15), "intro"),
            seg(at_measure(15), at_measure(33), "verse"), seg(at_measure(33), at_measure(43), "verse"),
            seg(at_measure(43), at_measure(51), "chorus")]
    assert [n for _, n in sections_from_segments(segs, tm, PAD)] == ["Intro A", "Intro B", "Verse A", "Verse B",
                                                                     "Chorus"]
    out = sections_from_segments(segs, tm, PAD, split_over=16, split_into=8)
    assert out == [(1 * M, "Intro"), (15 * M, "Verse A"), (22 * M, "Verse B"), (29 * M, "Verse C"),
                   (36 * M, "Verse D"), (43 * M, "Chorus")]


def test_sections_follow_the_meter():
    tm = const_map(bars=[(0, 3)])  # 3/4: a measure is 1.5 s
    segs = [seg(1.5 * 2 - PAD, 1.5 * 10 - PAD + 0.2, "verse"), seg(1.5 * 10 - PAD + 0.2, 1.5 * 20 - PAD, "chorus")]
    assert sections_from_segments(segs, tm, PAD) == [(2 * 3 * RES, "Verse"), (10 * 3 * RES, "Chorus")]


def test_no_music_means_no_sections():
    assert sections_from_segments([seg(0.0, 3.0, "start"), seg(3.0, 4.0, "end")], const_map(), PAD) == []


def test_label_and_clean_names():
    assert label_name("inst") == "Instrumental"
    assert label_name("Chorus") == "Chorus"
    assert label_name("pre_chorus") == "Pre Chorus"
    assert clean_name("verse_1") == "Verse 1"
    assert clean_name("chorus_2a") == "Chorus 2A"
    assert clean_name("  gtr   solo ") == "Gtr Solo"
    assert clean_name("Section 3") == "Section 3"
    assert clean_name("BRIDGE") == "BRIDGE"


def test_imported_sections_are_snapped_merged_and_cleaned():
    tm = const_map()
    imported = [(at_measure(9, 0.2), "chorus_1"), (at_measure(1, -0.1), "intro"), (at_measure(5), "verse_1"),
                (at_measure(8, 0.3), "verse_1b"), (at_measure(17), "Section 3")]
    out = sections_from_chart(imported, tm, PAD, end=at_measure(25))
    # verse_1b, one measure before chorus_1, merges into verse_1
    assert out == [(1 * M, "Intro"), (5 * M, "Verse 1"), (9 * M, "Chorus 1"), (17 * M, "Section 3")]
    # a short section merges into the one before it, whatever the names
    close = [(at_measure(1), "intro"), (at_measure(5), "verse_1"), (at_measure(6), "verse_1b"), (at_measure(9), "x")]
    assert sections_from_chart(close, tm, PAD) == [(1 * M, "Intro"), (6 * M, "Verse 1B"), (9 * M, "X")]
    # without the song's end the last section is kept, however short
    tail = [(at_measure(1), "verse"), (at_measure(9), "outro")]
    assert sections_from_chart(tail, tm, PAD) == [(1 * M, "Verse"), (9 * M, "Outro")]
    assert sections_from_chart(tail, tm, PAD, end=at_measure(10)) == [(1 * M, "Verse")]
    assert sections_from_chart([], tm, PAD) == []
