"""End to end: a synthetic song (clicks on a beat grid) packaged, then read back by scan-chart and by
the sync check. Only synthetic audio is used in tests."""
import json
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest

from songcharter import audio as A
from songcharter.chart import STAR_POWER, Chart, DrumHit, FretNote, Phrase, SongInfo, Track
from songcharter.package import build_song_folder, zip_folder
from songcharter.tempo import TempoMap, plan_lead_in

SCAN = Path(__file__).resolve().parents[1] / "tools" / "scan-chart"
SR = A.SAMPLE_RATE


def clicks(beats, duration, sr=SR):
    y = np.zeros(int(duration * sr), dtype=np.float32)
    burst = (np.random.default_rng(0).standard_normal(400) * np.hanning(400)).astype(np.float32) * 0.5
    for t in beats:
        i = int(round(t * sr))
        if i + 400 < len(y):
            y[i:i + 400] += burst
    y += np.random.default_rng(1).standard_normal(len(y)).astype(np.float32) * 0.01  # a little noise floor
    return np.stack([y, y])


def scan(folder, notes=False):
    if not (SCAN / "node_modules" / "scan-chart").exists():
        pytest.skip("run `npm install` in tools/scan-chart")
    args = ["node", str(SCAN / "scan.cjs"), str(folder)] + (["--notes"] if notes else [])
    return json.loads(subprocess.run(args, check=True, capture_output=True, text=True).stdout)


@pytest.fixture(scope="module")
def song(tmp_path_factory):
    period = 60 / 142.0
    beats = 0.0749 + np.arange(0, 120) * period
    duration = beats[-1] + 1.0
    li = plan_lead_in(beats, list(range(0, 120, 4)), SR, min_lead=2.5, duration=duration)
    tm = TempoMap.from_beats(li.beats, li.bars)
    res = tm.resolution
    first = li.first_beat * res
    # guitar: a note on every beat, 16th HOPO runs, a chord; star power on two measures
    notes = []
    for k in range(0, 96):
        tick = first + k * res
        notes.append(FretNote(tick, ((k % 5),)))
        if k % 8 == 3:
            notes.append(FretNote(tick + res // 4, (((k + 1) % 5),)))
    notes.append(FretNote(first + 100 * res, (0, 2), length=res * 2))
    sp = [Phrase(first + 16 * res, 8 * res, STAR_POWER), Phrase(first + 48 * res, 8 * res, STAR_POWER)]
    guitar = Track("Expert", "Single", notes, sp)
    easy = Track("Easy", "Single", [FretNote(n.tick, (min(n.frets[0], 2),)) for n in notes[::4]])
    drums = Track("Expert", "Drums", [DrumHit(first + k * res, 0 if k % 2 == 0 else 1) for k in range(96)], sp)
    sections = [(first, "Intro"), (first + 32 * res, "Verse 1"), (first + 64 * res, "Chorus 1")]
    info = SongInfo("Click Song", "songcharter tests", album="Synthetic", genre="Test", year="2026",
                    charter="songcharter", preview_start_ms=5000)
    chart = Chart(info, tm, sections, [guitar, easy, drums])
    audio = clicks(beats, duration)
    out = tmp_path_factory.mktemp("pkg") / "songcharter tests - Click Song"
    result = build_song_folder(out, chart, audio, li.pad_samples, difficulty={"Single": 3, "Drums": 2})
    return result, chart, li, beats


def test_folder_contents(song):
    result, *_ = song
    assert sorted(p.name for p in result.folder.iterdir()) == ["notes.chart", "song.ini", "song.ogg"]
    assert result.sync.ok, result.sync.summary()


def test_scan_chart_accepts_it(song):
    result, *_ = song
    r = scan(result.folder)
    assert r["playable"] is True
    assert r["folderIssues"] == [{"folderIssue": "noAlbumArt", "description": r["folderIssues"][0]["description"]}]
    assert r["metadataIssues"] == []
    kinds = {i["noteIssue"] for i in r["chartIssues"]}
    # drums without activation lanes is expected here; nothing else
    assert kinds <= {"noDrumActivationLanes"}, r["chartIssues"]


def test_notes_land_on_the_detected_beats(song):
    result, chart, li, beats = song
    r = scan(result.folder, notes=True)
    g = next(t for t in r["tracks"] if t["instrument"] == "guitar" and t["difficulty"] == "expert")
    first = li.first_beat * chart.resolution
    on_beat = [n for n in g["notes"] if (n["tick"] - first) % chart.resolution == 0 and n["tick"] < first + 96 * chart.resolution]
    for n in on_beat[:96]:
        k = (n["tick"] - first) // chart.resolution
        assert abs(n["ms"] / 1000 - (beats[k] + li.pad_seconds)) < 0.002
    hopos = [n for n in g["notes"] if (n["tick"] - first) % chart.resolution == chart.resolution // 4]
    assert hopos and all("hopo" in n["flags"] for n in hopos)


def test_sync_check_catches_a_shift(tmp_path):
    y = clicks(np.arange(0.5, 9, 0.4), 10.0)
    shifted = A.pad_front(y, 100)[:, :y.shape[1]]
    lags = A.measure_offset(y, shifted)
    assert all(abs(l - 100) < 0.5 for _, l, _ in lags)
    A.encode_ogg(y, tmp_path / "x.ogg")
    assert A.verify_sync(y, tmp_path / "x.ogg").ok


def test_zip(song, tmp_path):
    result, *_ = song
    z = zip_folder(result.folder, tmp_path / "song.zip")
    import zipfile
    names = zipfile.ZipFile(z).namelist()
    assert all(n.startswith(result.folder.name + "/") for n in names) and len(names) == 3
