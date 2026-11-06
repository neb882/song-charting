"""The stress set (eval/stress.py, eval/build_refs.sh --set stress, eval/lyrics_timing.py) and the scorer's feel
measures (eval/scorer/score.py). Made-up packages, charts, summaries and scores only, with made-up words and audio
generated here: no song, chart, lyric or md5 of the real set is in the repository."""
import json
import os
import shutil
import struct
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from eval import golden as G
from eval import lyrics_timing as LT
from eval import stress as S
from eval.scorer import score as SC
from songcharter import audio as A
from songcharter.chart import STAR_POWER, Chart, FretNote, Phrase, SongInfo, Track, write_chart
from songcharter.ini import write_ini
from songcharter.tempo import Tempo, TempoMap, TimeSignature

ROOT = Path(__file__).resolve().parent.parent
WORDS = ("zorp", "blen", "dak", "quiv", "fim", "wob", "smee", "plin", "trel", "vosk")   # made up
SR = A.SAMPLE_RATE


@pytest.fixture(scope="module")
def scan_env():
    try:
        script = G.scan_chart_script()
        G.node()
    except G.Refused as e:
        pytest.skip(f"scan-chart is not here ({e})")
    return {**os.environ, "SONGCHARTER_SCAN_CHART": str(script)}


def md5(k: int) -> str:
    return f"{k:032x}"


# ------------------------------------------------------------------------------------------------ the set

def local_for(songs):
    return [{"id": s["id"], "md5": md5(10 * k + 1), "artist": "Made Up Band", "title": f"Made Up Song {k}",
             "charter": "madeupcharter", "alts": [{"md5": md5(10 * k + 2 + j), "charter": f"other{j}"}
                                                  for j in range(s["charts"] - 1)]}
            for k, s in enumerate(songs)]


def test_stress_json_parses_and_every_song_has_a_primary(tmp_path):
    songs = json.loads(S.SET_JSON.read_text(encoding="utf-8"))
    assert [s["id"] for s in songs] == ["troop", "sooth", "break", "pm2"]
    assert all(s["slot"] and s["charts"] >= 1 and s["primary"] for s in songs)
    text = S.SET_JSON.read_text(encoding="utf-8")
    assert not S.MD5.search(text) and "charter" not in text   # the md5s and charters are the owner's list's
    local = tmp_path / "local.json"
    local.write_text(json.dumps(local_for(songs)))
    merged = S.load_set(local=local)
    assert [(m["id"], m["md5"], len(m["alts"])) for m in merged] == [
        ("troop", md5(1), 2), ("sooth", md5(11), 1), ("break", md5(21), 3), ("pm2", md5(31), 4)]
    assert merged[0]["slot"] == songs[0]["slot"] and merged[0]["title"] == "Made Up Song 0"


@pytest.mark.parametrize("change, match", [("missing", "not in the local list"), ("count", "says 3 charts"),
                                           ("md5", "32 hex digits"), ("twice", "all different")])
def test_the_local_list_must_cover_the_set(tmp_path, change, match):
    songs = json.loads(S.SET_JSON.read_text(encoding="utf-8"))
    local = local_for(songs)
    if change == "missing":
        local = local[1:]
    elif change == "count":
        local[0]["alts"] = local[0]["alts"][:1]
    elif change == "md5":
        local[1]["md5"] = "not-an-md5"
    else:
        local[2]["alts"][0]["md5"] = local[2]["md5"]
    (tmp_path / "local.json").write_text(json.dumps(local))
    with pytest.raises(S.Refused, match=match):
        S.load_set(local=tmp_path / "local.json")


# ------------------------------------------------------------------------------------------------ build_refs.sh

def write_sng(path: Path, files: dict[str, bytes], meta: dict[str, str]) -> None:
    """A .sng package as eval/refs/sng_unpack.py reads it (a version, a mask, the metadata, the file index, the
    files xor-masked)."""
    mask = bytes(range(7, 23))
    head = b"SNGPKG" + struct.pack("<I", 1) + mask
    m = b"".join(struct.pack("<i", len(k.encode())) + k.encode() + struct.pack("<i", len(v.encode())) + v.encode()
                 for k, v in meta.items())
    head += struct.pack("<QQ", len(m) + 8, len(meta)) + m
    names = list(files)
    index_len = sum(1 + len(n.encode()) + 16 for n in names)
    at = len(head) + 16 + index_len + 8
    index, blobs = b"", b""
    for n in names:
        data = files[n]
        index += bytes([len(n.encode())]) + n.encode() + struct.pack("<QQ", len(data), at + len(blobs))
        i = np.arange(len(data), dtype=np.int64)
        key = np.frombuffer(mask, dtype=np.uint8)[i % 16] ^ (i & 0xFF).astype(np.uint8)
        blobs += (np.frombuffer(data, dtype=np.uint8) ^ key).tobytes()
    out = head + struct.pack("<QQ", index_len, len(names)) + index + struct.pack("<Q", len(blobs)) + blobs
    path.write_bytes(out)


def made_up_chart(words=WORDS, shift=0, step=480) -> Chart:
    """A guitar Expert part at 120 BPM and made-up lyric events, one word a beat from 4 s in two phrases."""
    notes = [FretNote(1920 + k * 480, (k % 5,)) for k in range(24)]
    lyr, tick = [], 3840 + shift
    for p in (words[:5], words[5:]):
        lyr.append((tick - 60, 2, "phrase_start"))
        for k, w in enumerate(p):
            lyr.append((tick + k * step, 3, f"lyric {w}"))
        lyr.append((tick + len(p) * step, 1, "phrase_end"))
        tick += (len(p) + 2) * step
    return Chart(SongInfo("Made Up Song", "Made Up Band", charter="madeupcharter"), TempoMap(480, [Tempo(0, 120000)]),
                 [], [Track("Expert", "Single", notes)], lyrics=lyr)


def tone(seconds: float, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    y = np.zeros(int(seconds * SR), np.float32)
    for k in range(int(seconds * 2)):        # a click every half second
        i = int(k * 0.5 * SR)
        y[i:i + 2000] += (0.3 * rng.standard_normal(min(2000, len(y) - i))).astype(np.float32)
    return np.stack([y, y])


def ogg(path: Path, y: np.ndarray) -> bytes:
    wav = path.with_suffix(".wav")
    A.write_wav(y, wav)
    subprocess.run([A.ffmpeg_exe(), "-nostdin", "-v", "error", "-y", "-i", str(wav), "-c:a", "libvorbis", str(path)],
                   check=True, stdin=subprocess.DEVNULL)
    return path.read_bytes()


def made_up_package(path: Path, tmp: Path, seed: int = 0) -> Path:
    chart = made_up_chart()
    files = {"notes.chart": write_chart(chart).encode("utf-8"), "song.ogg": ogg(tmp / f"song{seed}.ogg", tone(12, seed)),
             "drums.opus": b"\x00" * 100}   # the stub stem
    write_sng(path, files, {"name": "Made Up Song", "artist": "Made Up Band", "charter": "madeupcharter",
                            "song_length": "12000"})
    return path


@pytest.fixture
def tools_path(tmp_path):
    """PATH for build_refs.sh: an ffmpeg that first reads all of its stdin (as a helper's ffmpeg once did, eating
    the list's lines), then runs the real one; a curl that fails (nothing is downloaded); node."""
    bin_ = tmp_path / "bin"
    bin_.mkdir()
    (bin_ / "ffmpeg").write_text(f"#!/bin/sh\ncat > /dev/null\nexec '{A.ffmpeg_exe()}' \"$@\"\n")
    (bin_ / "curl").write_text("#!/bin/sh\necho 'no downloads in tests' >&2\nexit 22\n")
    for f in ("ffmpeg", "curl"):
        (bin_ / f).chmod(0o755)
    return f"{bin_}{os.pathsep}{os.path.dirname(G.node())}{os.pathsep}{os.environ.get('PATH', '')}"


def test_build_refs_builds_every_song_of_a_two_song_list_strips_the_words_and_skips_a_stub_stem(
        tmp_path, scan_env, tools_path):
    data = tmp_path / "data"
    (data / "sng").mkdir(parents=True)
    songs = [{"id": "aaa", "slot": "made up", "charts": 2}, {"id": "bbb", "slot": "made up too", "charts": 1}]
    (tmp_path / "set.json").write_text(json.dumps(songs))
    local = [{"id": "aaa", "md5": md5(1), "title": "Made Up Song", "artist": "Made Up Band", "charter": "x",
              "alts": [{"md5": md5(2), "charter": "y"}]},
             {"id": "bbb", "md5": md5(3), "title": "Made Up Song", "artist": "Made Up Band", "charter": "z"}]
    (data / "stress.local.json").write_text(json.dumps(local))
    for k in (1, 2, 3):
        made_up_package(data / "sng" / f"{md5(k)}.sng", tmp_path, seed=k)
    env = {**scan_env, "EVAL_DATA": str(data), "EVAL_PY": sys.executable, "STRESS_JSON": str(tmp_path / "set.json"),
           "PATH": tools_path}
    p = subprocess.run(["bash", str(ROOT / "eval" / "build_refs.sh"), "--set", "stress"], env=env,
                       capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=600)
    assert p.returncode == 0, p.stderr[-2000:]
    assert [line.split()[:2] for line in p.stdout.splitlines() if line.startswith("ok ")] == [
        ["ok", "aaa"], ["ok", "aaa"], ["ok", "bbb"]]
    st = data / "stress"
    for d in (st / "aaa", st / "aaa" / "alt" / md5(2), st / "bbb"):
        assert (d / "ref_notes.json").is_file() and (d / "input.wav").is_file(), d
        meta = json.loads((d / "build_meta.json").read_text())
        assert meta["stems_summed"] == ["song.ogg"]
        assert meta["stems_skipped"] == [{"file": "drums.opus", "bytes": 100, "why": "ffmpeg cannot open it"}]
        text = (d / "ref" / "notes.chart").read_text(encoding="utf-8")
        assert "lyric" not in text and "phrase_start" not in text and not any(w in text for w in WORDS)
        assert "ExpertSingle" in text
    built = json.loads((st / "songs.json").read_text())
    assert [(s["id"], [a["md5"] for a in s.get("alts", [])], s["stems_skipped"]) for s in built] == [
        ("aaa", [md5(2)], ["drums.opus"]), ("bbb", [], ["drums.opus"])]
    assert not any((data / "unpacked" / "stress").rglob("notes.chart"))   # the unpacked words are gone
    assert not any(w in p.stdout + p.stderr for w in WORDS)


# ------------------------------------------------------------------------------------------------ score.py

def song(path: Path, guitar, bass=None, tempo=None, sigs=None, phrases=(), solos=(), audio=None) -> Path:
    tm = TempoMap(480, tempo or [Tempo(0, 120000)], sigs or [TimeSignature(0, 4)])
    tracks = [Track("Expert", "Single", guitar, list(phrases), list(solos))]
    if bass:
        tracks.append(Track("Expert", "DoubleBass", bass))
    chart = Chart(SongInfo("Made Up Song", "Made Up Band", charter="test"), tm, [], tracks)
    path.mkdir(parents=True)
    (path / "notes.chart").write_text(write_chart(chart), encoding="utf-8", newline="")
    (path / "song.ini").write_text(write_ini(chart), encoding="utf-8", newline="")
    for name, data in (audio or {}).items():
        (path / name).write_bytes(data)
    return path


def ref_folder(path: Path, guitar, **kw) -> Path:
    song(path / "ref", guitar, **kw)
    A.write_wav(tone(24), path / "input.wav")
    return path


def score(tmp_path, ref_notes, cand_notes, ref_kw=None, cand_kw=None, extra=()) -> dict:
    ref = ref_folder(tmp_path / "refs" / "x", ref_notes, **(ref_kw or {}))
    cand = song(tmp_path / "cand", cand_notes, **(cand_kw or {}))
    return SC.main(["--ref", str(ref), "--cand", str(cand), "--input", str(ref / "input.wav"), "--out",
                    str(tmp_path / "out.json"), *extra])


def beats(n, start=1920, step=480, lanes=None):
    return [FretNote(start + k * step, ((lanes or [0, 1, 2, 3, 4])[k % len(lanes or [0, 1, 2, 3, 4])],))
            for k in range(n)]


def test_windows_give_each_windows_f1_and_the_lowest(tmp_path, scan_env, monkeypatch, capsys):
    monkeypatch.setenv("SONGCHARTER_SCAN_CHART", scan_env["SONGCHARTER_SCAN_CHART"])
    ref = beats(40)                                   # 2.0 s to 21.5 s, a note a beat
    # the middle window's notes (9 s to 16 s) 250 ms late, and one note of the last window 60 ms late (still matched)
    cand = [FretNote(n.tick + (240 if 8640 <= n.tick < 15360 else 58 if n.tick == 18240 else 0), n.frets) for n in ref]
    d = score(tmp_path, ref, cand, extra=["--windows", "7"])
    w = d["tracks"]["guitar/expert"]["windows_100ms"]
    assert w["window_s"] == 7 and [r["start_s"] for r in w["windows"]] == [2.0, 9.0, 16.0]
    assert [(r["f1"], r["matched"], r["n_ref"], r["n_cand"]) for r in w["windows"]] == [
        (1.0, 14, 14, 14), (0.0, 0, 14, 14), (1.0, 12, 12, 12)]
    assert w["lowest"] == {"start_s": 9.0, "f1": 0.0}   # the lowest, not the last
    printed = capsys.readouterr().out.splitlines()
    assert printed[-1] == "lowest 7-s window F1@100: guitar/expert 0.000 at 0:09.0"
    plain = score(tmp_path / "plain", ref, cand)
    assert "windows_100ms" not in plain["tracks"]["guitar/expert"] and "summary_windows" not in plain


def test_the_density_peak_counts_the_busiest_second(tmp_path, scan_env, monkeypatch):
    monkeypatch.setenv("SONGCHARTER_SCAN_CHART", scan_env["SONGCHARTER_SCAN_CHART"])
    burst = [FretNote(9600 + k * 120, (k % 3,)) for k in range(8)]     # 8 notes 125 ms apart from 10.0 s
    ref = sorted(beats(10) + burst + beats(10, start=14400), key=lambda n: n.tick)
    d = score(tmp_path, ref, beats(10))
    assert d["tracks"]["guitar/expert"]["density_peak_1s"] == {"ref": 8, "cand": 2, "ref_at_s": 10.0,
                                                                "cand_at_s": 2.0}


def test_state_agreement_compares_each_matched_notes_state(tmp_path, scan_env, monkeypatch):
    monkeypatch.setenv("SONGCHARTER_SCAN_CHART", scan_env["SONGCHARTER_SCAN_CHART"])
    ref = beats(10)                                   # a beat apart: strums
    cand = [FretNote(n.tick, n.frets, tap=k < 3) if k < 3 else FretNote(n.tick, n.frets, flip=k in (5, 6))
            for k, n in enumerate(ref)]               # three taps, two forced HOPOs
    sa = score(tmp_path, ref, cand)["tracks"]["guitar/expert"]["state_agreement"]
    assert sa == {"value": 0.5, "n_matched": 10, "confusion_ref/cand": {"strum/hopo": 2, "strum/strum": 5,
                                                                        "strum/tap": 3}}


def test_jumps_count_big_fast_jumps_and_the_distance_between_the_histograms(tmp_path, scan_env, monkeypatch):
    monkeypatch.setenv("SONGCHARTER_SCAN_CHART", scan_env["SONGCHARTER_SCAN_CHART"])
    ref = beats(9, step=60, lanes=[0, 4]) + beats(4, start=4800)      # 32nds (62.5 ms) green-orange, then 4 beats
    cand = beats(9, step=60, lanes=[0, 1]) + beats(4, start=4800)
    j = score(tmp_path, ref, cand)["tracks"]["guitar/expert"]["jumps"]
    assert j["ref"]["big_fast"] == 8 and j["cand"]["big_fast"] == 0
    assert j["ref"]["n_pairs"] == j["cand"]["n_pairs"] == 12
    assert j["ref"]["hist"][4] == round(8 / 12, 4) and j["cand"]["hist"][1] == round(11 / 12, 4)
    assert j["emd_lanes"] == pytest.approx(3 * 8 / 12, abs=1e-3)   # 8 of 12 pairs moved from 4 lanes to 1
    assert j["ref"]["big_fast_share"] == round(8 / 12, 4)


def test_a_chord_is_no_jump_and_a_jump_150_ms_apart_is_not_fast(tmp_path, scan_env, monkeypatch):
    monkeypatch.setenv("SONGCHARTER_SCAN_CHART", scan_env["SONGCHARTER_SCAN_CHART"])
    # green, a green-orange chord, orange (62.5 ms apart); green 150 ms later; orange 62.5 ms after it; four beats
    ref = [FretNote(1920, (0,)), FretNote(1980, (0, 4)), FretNote(2040, (4,)), FretNote(2184, (0,)),
           FretNote(2244, (4,))] + beats(4, start=4800)
    j = score(tmp_path, ref, ref)["tracks"]["guitar/expert"]["jumps"]["ref"]
    assert j["n_pairs"] == 6 and j["big_fast"] == 1   # neither pair with the chord, nor the 150-ms one
    assert j["hist"] == [0.0, 0.5, 0.0, 0.0, 0.5, 0.0]


def test_the_downbeat_f1_follows_the_measure_lines_not_the_beats(tmp_path, scan_env, monkeypatch):
    monkeypatch.setenv("SONGCHARTER_SCAN_CHART", scan_env["SONGCHARTER_SCAN_CHART"])
    ref = beats(32)
    same = score(tmp_path / "a", ref, ref)["tempo_map"]
    late = score(tmp_path / "b", ref, ref, cand_kw={"sigs": [TimeSignature(0, 1), TimeSignature(480, 4)]})
    assert same["downbeat_f1_70ms"]["f1"] == 1.0 and same["downbeat_f1_70ms"]["n_ref"] == 8
    t = late["tempo_map"]
    assert t["beat_f1_70ms"]["f1"] == 1.0 and t["downbeat_f1_70ms"]["f1"] == 0.0   # a bar off, every beat right
    half = score(tmp_path / "c", ref, ref, cand_kw={"sigs": [TimeSignature(0, 2)]})["tempo_map"]["downbeat_f1_70ms"]
    assert (half["recall"], half["precision"], half["n_cand"]) == (1.0, 0.5, 16)   # a line every 2 beats: as many extra


def test_star_power_per_minute_and_the_solo_share(tmp_path, scan_env, monkeypatch):
    monkeypatch.setenv("SONGCHARTER_SCAN_CHART", scan_env["SONGCHARTER_SCAN_CHART"])
    ref = beats(41)                                   # 2.0 s to 22.0 s: 20 s charted
    d = score(tmp_path, ref, ref, ref_kw={"phrases": [Phrase(1920, 960, STAR_POWER), Phrase(9600, 960, STAR_POWER)],
                                          "solos": [(11520, 11520 + 4800)]})
    t = d["tracks"]["guitar/expert"]
    assert t["star_power_per_min"] == {"ref": 6.0, "cand": 0.0}
    assert t["solo_share"]["ref"] == pytest.approx(0.25, abs=2e-4) and t["solo_share"]["cand"] == 0.0   # 5 of 20 s


def test_an_unopenable_stem_is_skipped_with_a_note(tmp_path, scan_env, monkeypatch):
    monkeypatch.setenv("SONGCHARTER_SCAN_CHART", scan_env["SONGCHARTER_SCAN_CHART"])
    good = ogg(tmp_path / "good.ogg", tone(24))
    ref = ref_folder(tmp_path / "refs" / "x", beats(20))
    cand = song(tmp_path / "cand", beats(20), audio={"drums.opus": b"\x00" * 100, "song.ogg": good})
    stub = tmp_path / "stub.opus"
    stub.write_bytes(b"\x00" * 135)
    d = SC.main(["--ref", str(ref), "--cand", str(cand), "--input", str(stub), "--out", str(tmp_path / "o.json")])
    assert "skipped drums.opus: ffmpeg cannot open it (100 bytes)" in d["warnings"]
    assert "skipped stub.opus: ffmpeg cannot open it (135 bytes)" in d["warnings"]
    assert d["alignment"]["method"].startswith("fft xcorr") and abs(d["alignment"]["lag_ms"]) < 5
    assert d["tracks"]["guitar/expert"]["onset_50ms"]["f1"] == 1.0
    only = song(tmp_path / "cand2", beats(20), audio={"drums.opus": b"\x00" * 100})
    d = SC.main(["--ref", str(ref), "--cand", str(only), "--input", str(ref / "input.wav"), "--out",
                 str(tmp_path / "o2.json")])
    assert d["alignment"]["method"] == "none: no candidate audio file could be read, lag assumed 0"


# ------------------------------------------------------------------------------------------------ stress.py score and compare

def test_shape_counts_report_jsons_silent_onsets_and_the_previews_gaps(tmp_path):
    folder = song(tmp_path / "song", beats(16, start=0))      # notes 0 s to 7.5 s, at 120 BPM
    (folder / "report.json").write_text(json.dumps({"parts": {"guitar": {"silent_onsets": {"count": 3}}},
                                                    "lead_in": {"pad_seconds": 0.0}}))
    kept = tmp_path / "kept"
    (kept / "stems" / "k").mkdir(parents=True)
    rng = np.random.default_rng(5)
    y = np.zeros(int(20 * SR), np.float32)
    for k in range(80):                                       # an attack every 250 ms for 20 s: it plays on
        i = int(k * 0.25 * SR)
        y[i:i + 2000] += (0.3 * rng.standard_normal(2000)).astype(np.float32) * np.exp(-np.arange(2000) / 400)
    for name in ("guitar", "other", "bass", "drums"):
        A.write_wav(np.stack([y, y]) if name == "guitar" else np.zeros((2, len(y)), np.float32),
                    kept / "stems" / "k" / f"{name}.wav")
    (kept / "stems" / "k" / "info.json").write_text("{}")
    got = S.shape(folder, kept)
    g = got["guitar"]
    assert g["silent_onsets"] == 3 and g["judged"] and got["bass"]["silent_onsets"] is None
    assert not got["bass"]["judged"] and not got["drums"]["judged"]   # no bass or drums part in the chart
    assert g["flags"]["gap"]["stretches"] == 1 and g["flags"]["gap"]["measures"] >= 4   # 8 s to 20 s: no notes
    assert "notes in silence" not in g["flags"]



def made_up_score(f1_50: float, alt: bool = False) -> dict:
    """score.py's JSON as stress.py reads it, made up."""
    def prf(f):
        return {"f1": f, "precision": f, "recall": f, "matched": 9, "n_ref": 10, "n_cand": 10}
    track = {"onset_50ms": prf(f1_50), "onset_100ms": prf(min(1.0, f1_50 + 0.05)), "n_notes": {"ref": 100, "cand": 80},
             "timing_err_ms_matched100": {"median": 12.5}, "chord_share": {"ref": 0.05, "cand": 0.3},
             "density_peak_1s": {"ref": 14, "cand": 17}, "lane_direction_agreement": {"value": 0.7},
             "hopo_share": {"ref": 0.2, "cand": 0.1}, "tap_share": {"ref": 0.0, "cand": 0.0},
             "sustain_share": {"ref": 0.3, "cand": 0.2}, "state_agreement": {"value": 0.8},
             "jumps": {"emd_lanes": 0.4, "ref": {"big_fast_per_min": 1.0}, "cand": {"big_fast_per_min": 3.0}},
             "star_power_per_min": {"ref": 2.0, "cand": 1.5}, "solo_share": {"ref": 0.1, "cand": 0.0},
             "windows_100ms": {"lowest": {"start_s": 270.0, "f1": 0.25}}}
    bass = {k: v for k, v in track.items()}
    return {"tracks": {"guitar/expert": track, "bass/expert": bass},
            "tempo_map": {"beat_f1_70ms": {"f1": 0.9}, "beat_f1_70ms_octave_tolerant": {"f1": 0.95},
                          "downbeat_f1_70ms": {"f1": 0.5 if alt else 0.6}},
            "alignment": {"lag_ms": 2500.0}, "ref_tracks_missing_in_cand": ["drums/expert"]}


def made_up_run(tmp_path) -> tuple[Path, Path]:
    refs = tmp_path / "stress"
    for d in ("aaa", f"aaa/alt/{md5(2)}", f"aaa/alt/{md5(3)}", "bbb"):
        (refs / d).mkdir(parents=True)
        tracks = [] if d.endswith(md5(3)) else [{"instrument": "guitar", "difficulty": "expert", "notes": [{}]}]
        (refs / d / "ref_notes.json").write_text(json.dumps({"tracks": tracks}))
    (refs / "songs.json").write_text(json.dumps([
        {"id": "aaa", "md5": md5(1), "slot": "made up", "alts": [{"md5": md5(2)}, {"md5": md5(3)}]},
        {"id": "bbb", "md5": md5(4), "slot": "made up too", "alts": []}]))
    run = tmp_path / "run"
    (run / "aaa").mkdir(parents=True)
    (run / "summary.json").write_text(json.dumps({"golden": 1, "code": {"commit": "c0ffee", "dirty": []}, "songs": {
        "aaa": {"exit": 0, "gate_ok": True, "folder": "aaa"}, "bbb": {"exit": 2, "gate_ok": None, "folder": None}},
        "run": {"refs": str(refs), "work": str(tmp_path / "work")}}))
    return run, refs


def test_score_scores_ours_against_every_chart_and_the_humans_against_the_primary(tmp_path):
    run, refs = made_up_run(tmp_path)
    calls = []

    def scorer(ref, cand, inp, out_json, cand_audio=None, windows=30, env=None):
        calls.append((ref.relative_to(tmp_path).as_posix(), cand.relative_to(tmp_path).as_posix(),
                      cand_audio and cand_audio.name, windows))
        return made_up_score(0.8 if cand.name == "aaa" else 0.9, alt="alt" in str(ref))

    scores = S.score_run(run, scorer=scorer, shaper=lambda folder, kept: {"guitar": {
        "silent_onsets": 3, "flags": {"gap": {"stretches": 2, "measures": 5}}, "judged": True}}, say=lambda s: None)
    assert calls == [("stress/aaa", "run/aaa", None, 30), (f"stress/aaa/alt/{md5(2)}", "run/aaa", None, 30),
                     ("stress/aaa", f"stress/aaa/alt/{md5(2)}/ref", "input.wav", 30)]
    a = scores["songs"]["aaa"]
    assert a["refs"] == ["primary", "alt1", "alt2"] and a["unscored"] == {"alt2": "no guitar, bass or drums notes"}
    assert list(a["ours"]) == ["primary", "alt1"] and list(a["humans"]) == ["alt1"]
    g = a["ours"]["primary"]["parts"]["guitar"]
    assert g["f1_50"] == 0.8 and g["notes_ratio"] == 0.8 and g["chord_share"] == [0.3, 0.05]
    assert g["big_fast_per_min"] == [3.0, 1.0] and g["lowest_window"] == {"start_s": 270.0, "f1": 0.25}
    assert a["humans"]["alt1"]["parts"]["guitar"]["f1_50"] == 0.9 and a["ours"]["primary"]["missing"] == ["drums/expert"]
    assert scores["songs"]["bbb"]["error"] == "no song folder: the build failed"
    text = S.render(scores)
    assert "| aaa | guitar | ours vs primary | 0.800 | 0.850 | 0.80 | 0.250 at 4:30.0 | 12.5 | 0.30/0.05 | 17/14 |" in text
    assert "| aaa | guitar | humans: alt1 vs primary | 0.900 |" in text
    assert "| aaa | guitar | 3 | 2 (5) | 0 | 0 |" in text and "| aaa | alt2 | not scored" in text
    assert "| aaa | ours vs primary | 0.900 | 0.950 | 0.600 | 2500.0 |" in text


def scores_with(f100: float = 0.95, **f1) -> dict:
    """Made-up stress scores: ours against the primary and an alt, per part F1@50 (F1@100 apart from it, `f100`)."""
    def part(f, f100=f100):
        return {"f1_50": f, "f1_100": f100, "timing_err_ms": 5.0, "chord_share": [0.1, 0.05], "lowest_window": None}
    songs = {"aaa": {"ours": {"primary": {"parts": {p: part(v) for p, v in f1.items() if v is not None},
                                         "tempo": {"beat_f1": 0.9, "downbeat_f1": 0.5}},
                              "alt1": {"parts": {"guitar": part(0.5)}, "tempo": {"beat_f1": 0.9, "downbeat_f1": 0.5}}}}}
    return {"stress": S.FORMAT, "code": {"commit": "abc"}, "songs": songs}


@pytest.mark.parametrize("new, code", [({"guitar": 0.795, "bass": 0.7}, 0), ({"guitar": 0.789, "bass": 0.7}, 1),
                                       ({"guitar": 0.9, "bass": None}, 1), ({"guitar": 0.85, "bass": 0.75}, 0),
                                       ({"guitar": 0.8, "bass": 0.7, "f100": 0.5}, 0)])   # F1@100 is not the rule
def test_compare_exits_1_when_a_primary_f1_falls_by_more_than_001(tmp_path, capsys, new, code):
    old = scores_with(guitar=0.8, bass=0.7)
    (tmp_path / "old.json").write_text(json.dumps(old))
    (tmp_path / "new.json").write_text(json.dumps(scores_with(**new)))
    assert S.main(["compare", str(tmp_path / "old.json"), str(tmp_path / "new.json")]) == code
    out = capsys.readouterr().out
    assert f"F1@50 down by more than 0.01): {code}" in out
    assert f"| aaa | guitar | primary | 0.800 → {new['guitar']:.3f} ({new['guitar'] - 0.8:+.3f})" in out
    assert f"| 0.950 → {new.get('f100', 0.95):.3f} (" in out


def test_compare_ignores_an_alt_and_refuses_what_is_not_scores(tmp_path, capsys):
    old, new = scores_with(guitar=0.8), scores_with(guitar=0.8)
    new["songs"]["aaa"]["ours"]["alt1"]["parts"]["guitar"]["f1_50"] = 0.1   # an alt is not the regression rule
    text, code, bad = S.compare_scores(old, new)
    assert code == 0 and bad == [] and "| aaa | guitar | alt1 | 0.500 → 0.100 (-0.400)" in text
    del new["songs"]["aaa"]
    assert S.compare_scores(old, new)[1] == 1
    (tmp_path / "x.json").write_text("{}")
    assert S.main(["compare", str(tmp_path / "x.json"), str(tmp_path / "x.json")]) == 2


# ------------------------------------------------------------------------------------------------ align

def test_align_finds_the_lag_of_a_shifted_copy_and_none_in_noise(tmp_path, capsys):
    rng = np.random.default_rng(3)
    y = np.repeat(rng.standard_normal(int(40 * SR / 64)), 64).astype(np.float32) * 0.2   # broadband, 40 s
    (tmp_path / "s" / "aaa").mkdir(parents=True)
    A.write_wav(np.stack([y, y]), tmp_path / "s" / "aaa" / "input.wav")
    lag = int(0.150 * SR)
    shifted = np.concatenate([np.zeros(lag, np.float32), y])
    A.write_wav(np.stack([shifted, shifted]), tmp_path / "shifted.wav")
    noise = (rng.standard_normal(len(y)) * 0.2).astype(np.float32)
    A.write_wav(np.stack([noise, noise]), tmp_path / "noise.wav")
    r = S.align_file(tmp_path / "s" / "aaa" / "input.wav", tmp_path / "shifted.wav")
    assert r["aligned"] and abs(r["lag_ms"] - 150.0) < 1.0 and r["windows_peak_ge_0.3"] == r["windows"]
    assert S.main(["align", "aaa", str(tmp_path / "shifted.wav"), "--refs", str(tmp_path / "s")]) == 0
    assert "lag +150" in capsys.readouterr().out
    drift = np.interp(np.arange(len(y)) * 1.0005, np.arange(len(y)), y).astype(np.float32)   # 0.05 % fast: 20 ms over 40 s
    A.write_wav(np.stack([drift, drift]), tmp_path / "drift.wav")
    r = S.align_file(tmp_path / "s" / "aaa" / "input.wav", tmp_path / "drift.wav")
    assert r["windows_peak_ge_0.3"] == r["windows"] and r["lag_mad_ms"] >= 2.0 and not r["aligned"]   # the MAD fails it
    r = S.align_file(tmp_path / "s" / "aaa" / "input.wav", tmp_path / "noise.wav")
    assert not r["aligned"] and r["windows_peak_ge_0.3"] < r["windows"] / 2
    assert S.main(["align", "aaa", str(tmp_path / "noise.wav"), "--refs", str(tmp_path / "s")]) == 1
    assert "NOT aligned" in capsys.readouterr().out


# ------------------------------------------------------------------------------------------------ lyrics_timing.py

def write_mid(path: Path, words, start_s=2.0, step_s=0.5) -> Path:
    """A .mid with made-up words in PART VOCALS: 120 BPM, a phrase marker (note 105) per five words."""
    import mido
    m = mido.MidiFile(ticks_per_beat=480)
    t0 = mido.MidiTrack([mido.MetaMessage("set_tempo", tempo=500000, time=0)])
    m.tracks.append(t0)
    v = mido.MidiTrack([mido.MetaMessage("track_name", name="PART VOCALS", time=0)])
    events = []
    for k, w in enumerate(words):
        tick = int(round((start_s + k * step_s) * 960))
        if k % 5 == 0:   # the first phrase on note 105, the next on 106 (Rock Band uses both)
            note = 105 if k % 10 == 0 else 106
            events += [(tick - 30, mido.Message("note_on", note=note, velocity=100)),
                       (tick + 5 * int(step_s * 960) - 60, mido.Message("note_off", note=note, velocity=0))]
        events.append((tick, mido.MetaMessage("lyrics", text=w)))
    last = 0
    for tick, msg in sorted(events, key=lambda e: e[0]):
        v.append(msg.copy(time=tick - last))
        last = tick
    m.tracks.append(v)
    m.save(path)
    return path


def test_lyrics_timing_pairs_words_by_index_and_prints_no_word(tmp_path, capsys):
    ref_chart = tmp_path / "ref.chart"
    ref_chart.write_text(write_chart(made_up_chart()), encoding="utf-8")
    # ours: the same words, the second phrase 14.6 ms late (14 ticks) and its last word 300 ms more, the first word in
    # two syllables
    cand = made_up_chart(shift=0)
    cand.lyrics = [(t + (14 if t > 7000 else 0) + (288 if "vosk" in x else 0), o, x) for t, o, x in cand.lyrics]
    cand.lyrics = [(t, o, "lyric zo=" if x == "lyric zorp" else x) for t, o, x in cand.lyrics]
    cand.lyrics.insert(2, (3840 + 120, 3, "lyric rp"))
    cand_chart = tmp_path / "cand.chart"
    cand_chart.write_text(write_chart(cand), encoding="utf-8")
    ref, ours = LT.read(ref_chart), LT.read(cand_chart)
    assert len(ref.times) == len(ours.times) == 10 and ref.phrase_first == [0, 5]
    assert ref.times[:2] == [4.0, 4.5] and ref.aligner_text() == "zorp blen dak quiv fim\nwob smee plin trel vosk\n"
    assert ours._texts[0] == "zo-rp"
    stats = LT.compare(ref, ours)
    assert stats["paired"] == 10 and stats["paired_share"] == 1.0
    assert stats["within_50ms"] == 0.9 and stats["within_250ms"] == 0.9 and stats["phrase_starts_over_500ms"] == 0
    assert stats["median_abs_ms"] == pytest.approx(14.583 / 2, abs=0.1)   # five at 0, four at 14.6, one at 314.6
    mid = write_mid(tmp_path / "ref.mid", WORDS, start_s=4.0)
    from_mid = LT.read(mid)
    assert from_mid.phrase_first == [0, 5] and from_mid.times[:3] == [4.0, 4.5, 5.0]
    assert LT.main([str(mid), str(mid), "--ref-shift-ms", "100"]) == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["paired"] == 10 and printed["median_ms"] == -100.0 and printed["within_100ms"] == 1.0
    assert LT.main([str(tmp_path / "missing.chart"), str(ref_chart)]) == 2
    out, err = capsys.readouterr()
    assert err.strip() == "lyrics_timing: failed (FileNotFoundError)"
    late = LT.Sung([t + (0.6 if k >= 5 else 0.0) for k, t in enumerate(ref.times)], list(ref.phrase_first))
    off = LT.compare(ref, late)                       # the second phrase 600 ms late: its start is over 500 ms off
    assert off["phrase_starts_over_500ms"] == 1 and off["phrase_starts_paired"] == 2 and off["within_250ms"] == 0.5
    for text in (out, err, json.dumps(stats), json.dumps(off)):
        assert not any(w in text for w in WORDS)


def test_a_slide_and_markup_are_part_of_the_word_before():
    syl = [(1.0, "zorp-", 0), (1.2, "blen", 0), (1.4, "+", 0), (1.6, "dak#", 0), (1.8, "...", 0), (2.0, "fim_wob", 1)]
    w = LT.words(syl)
    assert w.times == [1.0, 1.6, 2.0, 2.0] and w.phrase_first == [0, 2] and w._texts == ["zorpblen", "dak", "fim", "wob"]


# ------------------------------------------------------------------------------------------------ stress.py lyrics

sys.path.insert(0, str(Path(__file__).parent))


@pytest.fixture(scope="module")
def lyric_song(tmp_path_factory):
    """A made-up stress song: test_pipeline's generated song as its input.wav, a package whose chart has made-up
    words in its lyric events where the generated vocal sings."""
    from test_pipeline import write_song
    root = tmp_path_factory.mktemp("stress-lyrics")
    write_song(root / "song.flac")
    refs = root / "stress"
    (refs / "aaa").mkdir(parents=True)
    subprocess.run([A.ffmpeg_exe(), "-nostdin", "-v", "error", "-i", str(root / "song.flac"), str(refs / "aaa" / "input.wav")],
                   check=True, stdin=subprocess.DEVNULL)
    (refs / "aaa" / "ref_notes.json").write_text(json.dumps({"delay": 0, "chart_offset": 0, "tracks": []}))
    (refs / "songs.json").write_text(json.dumps([{"id": "aaa", "md5": md5(9), "alts": []}]))
    chart = made_up_chart()
    chart.lyrics = []
    for line, (start, ws) in enumerate(((17.0, WORDS[:5]), (49.0, WORDS[5:]))):
        tick = int(start * 960)
        chart.lyrics.append((tick - 60, 2, "phrase_start"))
        chart.lyrics += [(tick + k * 384, 3, f"lyric {w}") for k, w in enumerate(ws)]
        chart.lyrics.append((tick + 5 * 384, 1, "phrase_end"))
    (root / "sng").mkdir()
    write_sng(root / "sng" / f"{md5(9)}.sng", {"notes.chart": write_chart(chart).encode()}, {"name": "x"})
    return root


@pytest.mark.parametrize("gate", ["ok", "failed"])
def test_the_lyrics_check_prints_numbers_only_and_leaves_nothing(lyric_song, tmp_path, monkeypatch, capsys, gate):
    import songcharter.assemble as assemble_module
    from test_lyrics import with_lyrics
    monkeypatch.setenv("SONGCHARTER_CACHE", str(tmp_path / "cache"))
    if gate == "failed":
        real = assemble_module.verify_folder
        monkeypatch.setattr(assemble_module, "verify_folder", lambda *a, **k: real(*a, **k) + [
            assemble_module.GateIssue(None, None, "fake", "a gate error")])
    tmp = tmp_path / "t"
    tmp.mkdir()
    lines = []
    code = S.lyrics_check("aaa", lyric_song / "stress", lyric_song / "sng", tmp_root=tmp, engines=with_lyrics()(),
                          out=lines.append, threads=None)
    assert code == 0, lines
    stats = json.loads(lines[-1])
    assert stats["words_ref"] == stats["words_cand"] == stats["paired"] == 10 and stats["paired_share"] == 1.0
    assert stats["gate_ok"] is (gate == "ok") and stats["within_250ms"] is not None
    assert "gate FAILED" in lines[0] if gate == "failed" else "gate OK" in lines[0]
    assert list(tmp.iterdir()) == []             # the song folder, its .failed and the work folder all gone
    out, err = capsys.readouterr()
    for text in [out, err] + lines:
        assert not any(w in text for w in WORDS)


def test_the_lyrics_check_from_a_runs_kept_folder_works_beside_it_and_leaves_it_as_it_was(lyric_song, tmp_path,
                                                                                          monkeypatch):
    from songcharter import pipeline as P
    work = tmp_path / "work"
    kept = work / "aaa"
    (kept / "stems" / "k").mkdir(parents=True)
    (kept / "decode.wav").write_bytes(b"made up")
    (kept / "stems" / "k" / "vocals.wav").write_bytes(b"made up")
    (kept / "drums").mkdir()
    (kept / "drums" / "notes.chart").write_text("made up")
    (kept / G.KEPT).write_text(json.dumps({"golden": G.KEPT_FORMAT}))
    run = tmp_path / "run"
    run.mkdir()
    (run / "summary.json").write_text(json.dumps({"songs": {}, "run": {"work": str(work)}}))
    before, seen = G.manifest(kept), {}

    def chart(audio, out, options, **kw):
        w = Path(options.work)
        seen.update(work=w, linked=os.path.samefile(w / "decode.wav", kept / "decode.wav"),
                    copied=(w / "drums" / "notes.chart").read_text())
        raise OSError("stands in for a failed build")

    monkeypatch.setattr(P, "chart", chart)
    lines = []
    assert S.lyrics_check("aaa", lyric_song / "stress", lyric_song / "sng", run_dir=run, out=lines.append) == 2
    assert lines == ["aaa: the lyrics chart failed (OSError)"]
    assert seen["work"].parent.parent == work / G.RUNS and seen["linked"] and seen["copied"] == "made up"
    assert list((work / G.RUNS).iterdir()) == [] and G.manifest(kept) == before


def test_the_lyrics_check_says_so_for_a_song_with_no_lyrics(lyric_song, tmp_path):
    root = tmp_path / "x"
    shutil.copytree(lyric_song / "stress", root / "stress")
    (root / "sng").mkdir()
    chart = made_up_chart()
    chart.lyrics = []
    write_sng(root / "sng" / f"{md5(9)}.sng", {"notes.chart": write_chart(chart).encode()}, {"name": "x"})
    lines = []
    assert S.lyrics_check("aaa", root / "stress", root / "sng", tmp_root=tmp_path, out=lines.append) == 0
    assert lines == ["aaa: the primary chart has no lyric events (no vocals): nothing to check"]
    assert [p.name for p in tmp_path.iterdir()] == ["x"]


# ------------------------------------------------------------------------------------------------ baseline

def test_the_baseline_copy_cuts_the_paths_and_the_local_lists_values(tmp_path, monkeypatch, capsys):
    songs = json.loads(S.SET_JSON.read_text(encoding="utf-8"))
    local = local_for(songs)
    local[2]["title"] = "Break"               # a title that is a song's generic id stays: it is the id
    (tmp_path / "local.json").write_text(json.dumps(local))
    run = tmp_path / "run"
    run.mkdir()
    secret_md5 = local[0]["md5"]
    (run / "summary.json").write_text(json.dumps({"golden": 1, "songs": {"troop": {
        "error": f"$ /made/up/venv/bin/python -m songcharter.cli chart --title Made Up Song 0 ({secret_md5})"}},
        "run": {"out": "/made/up/golden/stress-base", "work": "/made/up/golden/stress-work"}}))
    (run / "stress_scores.json").write_text(json.dumps({"stress": 1, "songs": {"troop": {"lag_ms": 1.5}}}))
    assert S.main(["baseline", str(run), str(tmp_path / "out"), "--local", str(tmp_path / "local.json")]) == 0
    s = json.loads((tmp_path / "out" / "summary.json").read_text())
    assert s["run"] == {"out": "<path>/stress-base", "work": "<path>/stress-work"}
    assert s["songs"]["troop"]["error"] == "$ <path>/python -m songcharter.cli chart --title <redacted> (<redacted>)"
    text = (tmp_path / "out" / "summary.json").read_text() + (tmp_path / "out" / "stress_scores.json").read_text()
    assert "Made Up" not in text and secret_md5 not in text and "madeupcharter" not in text
    assert "Break" not in S.secrets_of(S.load_set(local=tmp_path / "local.json"))
    # a value the scrub would miss: the check refuses and writes nothing
    monkeypatch.setattr(S, "scrub", lambda obj, secrets: obj)
    assert S.main(["baseline", str(run), str(tmp_path / "out2"), "--local", str(tmp_path / "local.json")]) == 2
    assert "left after scrubbing" in capsys.readouterr().err and not (tmp_path / "out2" / "summary.json").exists()


def test_the_baseline_scrub_covers_the_alts_any_case_the_keys_and_the_leftover_paths(tmp_path, monkeypatch, capsys):
    """Each part of the scrub, which a review broke one at a time with every test still passing (M5-12): the alts'
    md5s and charters are the local list's as the primary's are; a value matches in any case; a dict's keys are
    scrubbed as its values are; and a path the scrub left under /home/, /tmp/, /dev/shm/ or /root/ stops the copy,
    as a value of the list does, with nothing written."""
    import re
    songs = json.loads(S.SET_JSON.read_text(encoding="utf-8"))
    local = local_for(songs)
    (tmp_path / "local.json").write_text(json.dumps(local))
    alts = [a for s in local for a in s["alts"]]
    assert len(alts) >= 4 and all(a["charter"] in S.secrets_of(local) and a["md5"] in S.secrets_of(local)
                                  for a in alts)
    run = tmp_path / "run"
    run.mkdir()
    (run / "summary.json").write_text(json.dumps({"golden": 1, "songs": {
        "pm2": {"alts": [f"{a['md5']} by {a['charter']}" for a in alts], "loud": "MADE UP BAND - made up SONG 3",
                "by": "MadeUpCharter"},
        alts[0]["md5"]: {"f1": 0.5}, "made up band, live": {"f1": 0.25}},
        "files": {"/made/up/run/x.json": 1}}))
    (run / "stress_scores.json").write_text(json.dumps({"stress": 1, "songs": {"pm2": {"lag_ms": 1.5}}}))
    assert S.main(["baseline", str(run), str(tmp_path / "out"), "--local", str(tmp_path / "local.json")]) == 0
    capsys.readouterr()
    s = json.loads((tmp_path / "out" / "summary.json").read_text())
    assert s["songs"]["pm2"] == {"alts": ["<redacted> by <redacted>"] * len(alts),
                                 "loud": "<redacted> - <redacted>", "by": "<redacted>"}
    assert s["songs"]["<redacted>"] == {"f1": 0.5} and s["songs"]["<redacted>, live"] == {"f1": 0.25}
    assert s["files"] == {"<path>/x.json": 1}
    text = (tmp_path / "out" / "summary.json").read_text().lower()
    assert "made up" not in text and "madeupcharter" not in text
    assert not any(a["md5"] in text or a["charter"] in text for a in alts)
    # a path the scrub did not cut (its path rule broken here): refused, nothing written
    monkeypatch.setattr(S, "PATH", re.compile(r"(?!)"))
    for i, prefix in enumerate(("/home/", "/tmp/", "/dev/shm/", "/root/")):
        (run / "summary.json").write_text(json.dumps({"golden": 1, "run": {"out": f"{prefix}made-up/stress-run"}}))
        out = tmp_path / f"refused{i}"
        assert S.main(["baseline", str(run), str(out), "--local", str(tmp_path / "local.json")]) == 2, prefix
        assert "1 value(s) of the local list or a path left after scrubbing" in capsys.readouterr().err, prefix
        assert not (out / "summary.json").exists(), prefix
