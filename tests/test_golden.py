"""eval/golden.py: the track hash, --expect, the diff's statuses, tables and exit codes, and run's kept and private
work folders (with stand-ins for the build, the scan and the scorer). Synthetic song folders and summaries only: no
audio, reference charts or stems in the repository (the one WAV is a second of sine written into a test folder)."""
import json
import os
import threading
import time
from pathlib import Path

import numpy as np
import pytest

from eval import golden as G
from songcharter import audio as A
from songcharter.chart import STAR_POWER, Chart, FretNote, Phrase, SongInfo, Track, write_chart
from songcharter.ini import write_ini
from songcharter.tempo import Tempo, TempoMap


# ------------------------------------------------------------------------------------------------ the hash

@pytest.fixture(scope="module")
def scan_env():
    try:
        script = G.scan_chart_script()
        G.node()
    except G.Refused as e:
        pytest.skip(f"scan-chart is not here ({e})")
    return {**os.environ, "SONGCHARTER_SCAN_CHART": str(script)}


def _notes(n, step=480, start=1920):
    return [FretNote(start + k * step, (k % 5,)) for k in range(n)]


def song_folder(path: Path, guitar=None, hard=None, bass=None, phrases=()) -> Path:
    """A song folder of notes.chart and song.ini (no audio): guitar Expert and Hard, bass Expert."""
    guitar = _notes(8) if guitar is None else guitar
    hard = _notes(8, step=960) if hard is None else hard
    bass = _notes(6, step=640) if bass is None else bass
    tracks = [Track("Expert", "Single", guitar, list(phrases)), Track("Hard", "Single", hard),
              Track("Expert", "DoubleBass", bass)]
    chart = Chart(SongInfo("Golden", "Tests", charter="songcharter"), TempoMap(480, [Tempo(0, 120000)]), [], tracks)
    path.mkdir(parents=True)
    (path / "notes.chart").write_text(write_chart(chart), encoding="utf-8", newline="")
    (path / "song.ini").write_text(write_ini(chart), encoding="utf-8", newline="")
    return path


def hashes(folder, env):
    return {(p, d): e["hash"] for p, lv in G.parts(G.scan(folder, env)).items() for d, e in lv.items()}


def test_the_same_notes_give_the_same_hash(tmp_path, scan_env):
    a = G.song_entry(G.scan(song_folder(tmp_path / "a"), scan_env))
    b = G.song_entry(G.scan(song_folder(tmp_path / "b"), scan_env))
    assert a == b
    assert set(a["parts"]) == {"guitar", "bass"} and list(a["parts"]["guitar"]) == ["expert", "hard"]
    assert a["parts"]["guitar"]["expert"]["onsets"] == 8 and len(a["parts"]["guitar"]["expert"]["hash"]) > 20


@pytest.mark.parametrize("change", ["fret", "tick", "sustain", "star power"])
def test_one_changed_note_changes_its_tracks_hash_only(tmp_path, scan_env, change):
    base = hashes(song_folder(tmp_path / "base"), scan_env)
    notes = _notes(8)
    phrases = ()
    if change == "fret":
        notes[3] = FretNote(notes[3].tick, (4,))
    elif change == "tick":
        notes[3] = FretNote(notes[3].tick + 120, notes[3].frets)
    elif change == "sustain":
        notes[3] = FretNote(notes[3].tick, notes[3].frets, length=240)
    else:
        phrases = (Phrase(notes[2].tick, 960, STAR_POWER),)
    got = hashes(song_folder(tmp_path / "changed", guitar=notes, phrases=phrases), scan_env)
    assert got.keys() == base.keys()
    assert [k for k in base if got[k] != base[k]] == [("guitar", "expert")]


def test_a_chord_is_one_onset(tmp_path, scan_env):
    notes = _notes(4) + [FretNote(1920, (2,))]  # a second fret on the first note: a chord
    e = G.parts(G.scan(song_folder(tmp_path / "chord", guitar=notes), scan_env))["guitar"]["expert"]
    assert (e["onsets"], e["notes"]) == (4, 5)


def test_parts_keeps_the_three_parts_with_notes_in_order():
    scanned = {"tracks": [
        {"instrument": "drums", "difficulty": "hard", "hash": "d", "notes": [{"tick": 0}]},
        {"instrument": "keys", "difficulty": "expert", "hash": "k", "notes": [{"tick": 0}]},
        {"instrument": "bass", "difficulty": "expert", "hash": "b", "notes": []},
        {"instrument": "guitar", "difficulty": "easy", "hash": "ge", "notes": [{"tick": 0}, {"tick": 0}, {"tick": 9}]},
        {"instrument": "guitar", "difficulty": "expert", "hash": "gx", "notes": [{"tick": 5}]}]}
    got = G.parts(scanned)
    assert list(got) == ["guitar", "drums"] and list(got["guitar"]) == ["expert", "easy"]
    assert got["guitar"]["easy"] == {"onsets": 2, "notes": 3, "hash": "ge"}


# ------------------------------------------------------------------------------------------------ --expect

def test_expect_parses_parts_and_difficulties():
    assert G.parse_expect("none") == frozenset()
    assert G.parse_expect(" Guitar, bass:Hard ") == {("guitar", None), ("bass", "hard")}
    for bad in ("", "none,guitar", "keys", "bass:expertplus", ","):
        with pytest.raises(G.Refused):
            G.parse_expect(bad)


def test_expected_matches_a_part_on_every_level_and_a_pair_on_its_own():
    e = G.parse_expect("guitar,bass:hard")
    assert all(G.expected(e, "guitar", d) for d in G.LEVELS)
    assert G.expected(e, "bass", "hard")
    assert not any(G.expected(e, "bass", d) for d in ("expert", "medium", "easy"))
    assert not G.expected(e, "drums", "hard")
    assert not G.expected(G.parse_expect("none"), "guitar", "expert")


# ------------------------------------------------------------------------------------------------ diff

def prf(m, r, c):
    return {"f1": round(2 * m / (r + c), 4), "precision": round(m / c, 4), "recall": round(m / r, 4), "matched": m,
            "n_ref": r, "n_cand": c}


def entry(bass_hard=("h", 540), f1=(80, 100, 100), exit=0, delay=0, ref=True):
    """A song's summary entry: guitar Expert, bass Expert and Hard (hash and onsets of bass Hard given)."""
    e = {"has_ref": ref, "exit": exit, "gate_ok": {0: True, 1: False}.get(exit), "folder": "x", "delay": delay,
         "chart_offset": 0, "playable": True, "chart_issues": 0,
         "parts": {"guitar": {"expert": {"onsets": 868, "notes": 900, "hash": "g"}},
                   "bass": {"expert": {"onsets": 645, "notes": 645, "hash": "b"}}}}
    if bass_hard:
        e["parts"]["bass"]["hard"] = {"onsets": bass_hard[1], "notes": bass_hard[1], "hash": bass_hard[0]}
    if exit not in (0, 1):
        e["parts"] = {}
    if ref:
        e["scores"] = {"guitar": {"expert": {"f1_50": prf(*f1), "f1_100": prf(*f1)}}}
        if bass_hard:
            e["scores"]["bass"] = {"hard": {"f1_50": prf(40, 50, 60), "f1_100": prf(40, 50, 60)}}
        e["beat_f1"] = prf(90, 100, 100)
    return e


def summary(songs, commit="a" * 40, rerun=(), ran=None):
    return {"golden": G.FORMAT, "code": {"commit": commit, "dirty": []}, "options": {"rerun": list(rerun)},
            "tools": {"scan_chart": "8.0.1"}, "songs": songs,
            "run": {"started": "2026-11-03T12:00:00", "seconds": 60.0, "code": {"branch": "main"},
                    "songs": {s: {"ran": list(ran or []), "cold": None} for s in songs}}}


def diff(tmp_path, old, new, expect, *extra):
    (tmp_path / "old").mkdir(exist_ok=True)
    (tmp_path / "new").mkdir(exist_ok=True)
    (tmp_path / "old" / "summary.json").write_text(json.dumps(old))
    (tmp_path / "new" / "summary.json").write_text(json.dumps(new))
    code = G.main(["diff", str(tmp_path / "old"), str(tmp_path / "new"), "--expect", expect, *extra])
    out = tmp_path / "new"
    md = (out / "report.md").read_text() if (out / "report.md").exists() else None
    js = json.loads((out / "report.json").read_text()) if (out / "report.json").exists() else None
    return code, md, js


def test_identical_summaries_exit_0_with_every_part_unchanged(tmp_path):
    s = summary({"a": entry(), "t": entry(ref=False)})
    code, md, js = diff(tmp_path, s, s, "none")
    assert code == 0 and js["unexpected"] == [] and js["identical"]
    assert {r["status"] for x in js["songs"] for r in x["rows"]} == {"unchanged"}
    assert "**No UNEXPECTED change.**" in md and "identical: yes" in md
    assert "| guitar | expert | unchanged | 868 → 868 | 0.800 → 0.800 |" in md
    assert "| bass | hard | unchanged | 540 → 540 | 0.727 → 0.727 |" in md
    assert "| guitar | expert | unchanged | 868 → 868 | — → — |" in md  # the test song: no scores


def test_an_expected_change_exits_0_and_an_unexpected_one_exits_1(tmp_path):
    old = summary({"a": entry()})
    new = summary({"a": entry(bass_hard=("h2", 530))}, commit="b" * 40, rerun=("bass",), ran=["bass"])
    code, md, js = diff(tmp_path, old, new, "bass:hard")
    assert code == 0 and js["exit"] == 0 and js["unexpected"] == [] and not js["identical"]
    rows = {(r["part"], r["level"]): r for r in js["songs"][0]["rows"]}
    assert rows["bass", "hard"]["status"] == "changed" and rows["bass", "hard"]["onsets"] == [540, 530]
    assert rows["bass", "hard"]["hash"] == ["h", "h2"]
    assert {k: r["status"] for k, r in rows.items() if k != ("bass", "hard")} == {
        ("guitar", "expert"): "unchanged", ("bass", "expert"): "unchanged"}
    assert "| bass | hard | changed | 540 → 530 | 0.727 → 0.727 |" in md
    assert "| engines that ran | none (every engine's cache answered) | bass on 1 song |" in md
    assert "| engines asked to rerun | none | bass |" in md

    code, md, js = diff(tmp_path, old, new, "guitar")
    assert code == 1 and js["unexpected"] == ["a: bass hard"]
    assert "| bass | hard | **UNEXPECTED** | 540 → 530 | 0.727 → 0.727 |" in md
    assert "**UNEXPECTED: 1** (a: bass hard)." in md
    assert js["expected_but_unchanged"] == ["guitar"] and "Expected but unchanged on every song: guitar." in md
    assert diff(tmp_path, old, new, "none")[0] == 1
    assert diff(tmp_path, old, new, "bass")[0] == 0
    assert diff(tmp_path, old, new, "bass:expert")[0] == 1


def test_pooled_f1_is_over_every_songs_onsets(tmp_path):
    old = summary({"a": entry(f1=(80, 100, 100)), "b": entry(f1=(40, 50, 60)), "t": entry(ref=False)})
    new = summary({"a": entry(f1=(90, 100, 100)), "b": entry(f1=(40, 50, 60)), "t": entry(ref=False)})
    code, md, js = diff(tmp_path, old, new, "guitar")
    pooled = {(p["part"], p["level"]): p for p in js["pooled"]}
    g = pooled["guitar", "expert"]
    assert g["songs"] == 2
    assert g["old"] == pytest.approx(2 * 120 / 310) and g["new"] == pytest.approx(2 * 130 / 310)
    assert g["change"] == pytest.approx(20 / 310)
    assert pooled["beat F1", None]["old"] == pytest.approx(0.9)
    assert "| guitar | expert | 2 | 0.7742 | 0.8387 | +0.0645 |" in md
    assert "| beat F1 |  | 2 | 0.9000 | 0.9000 | +0.0000 |" in md
    assert code == 0  # the F1 moved, the hashes did not


def test_song_level_changes_are_unexpected_whatever_is_expected(tmp_path):
    every = "guitar,bass,drums"
    base = summary({"a": entry(), "b": entry()})
    code, md, js = diff(tmp_path, base, summary({"a": entry()}), every)
    assert code == 1 and js["unexpected"] == ["b: only in the old summary"]
    assert "**UNEXPECTED: only in the old summary.**" in md
    code, _, js = diff(tmp_path, base, summary({"a": entry(), "b": entry(exit=1)}), every)
    assert code == 1 and js["unexpected"] == ["b: the build changed: exit 0 -> 1, gate OK -> FAILED"]
    broken = summary({"a": entry(), "b": entry(exit=3)})
    code, _, js = diff(tmp_path, broken, broken, every)
    assert code == 1 and js["unexpected"] == ["b: not compared: the build failed in both runs (exit 3)"]


def test_a_delay_change_moves_every_part_and_a_new_part_is_a_change(tmp_path):
    old = summary({"a": entry()})
    code, md, js = diff(tmp_path, old, summary({"a": entry(delay=25)}), "bass")
    assert code == 1 and js["unexpected"] == ["a: guitar expert"]
    assert "The chart's delay changed (0 / 0 -> 25 / 0): every part moves." in md
    code, md, js = diff(tmp_path, summary({"a": entry(bass_hard=None)}), old, "guitar")
    assert code == 1 and js["unexpected"] == ["a: bass hard"]
    assert "| bass | hard | **UNEXPECTED** (only in the new build) | — → 540 | — → 0.727 |" in md


def test_diff_refuses_what_it_cannot_compare(tmp_path, capsys):
    s = summary({"a": entry()})
    assert diff(tmp_path, s, s, "keys")[0] == 2
    assert diff(tmp_path, s, {**s, "golden": G.FORMAT + 1}, "none")[0] == 2
    assert G.main(["diff", str(tmp_path / "nowhere"), str(tmp_path / "new"), "--expect", "none"]) == 2
    assert "not a golden summary" in capsys.readouterr().err


def test_report_goes_where_asked(tmp_path):
    s = summary({"a": entry()})
    code, _, _ = diff(tmp_path, s, s, "none", "--out", str(tmp_path / "elsewhere"))
    assert code == 0 and (tmp_path / "elsewhere" / "report.md").is_file()
    assert (tmp_path / "elsewhere" / "report.json").is_file()


# ------------------------------------------------------------------------------------------------ run

class FakeChart:
    """`songcharter chart` standing in: each heavy stage writes its file into --work unless it is there (a cache
    hit), pipeline.json says which ran, and --out gets a notes.chart made of what the stages wrote. `inplace`, a
    relative path, is appended to in the work folder on each build that is not a kept folder's (a stage writing in
    place)."""

    FILES = {"decode": "decode.wav", "separate": "stems/k/guitar.wav", "drums": "drums/notes.chart",
             "bass": "bass/notes.chart", "sections": "sections/segments.json", "guitar": "guitar/seed_1/notes.chart"}

    def __init__(self, inplace=None, delay=0.0):
        self.calls, self.inplace, self.delay, self.lock = [], inplace, delay, threading.Lock()

    def __call__(self, args, env, log):
        work, out = Path(args[args.index("--work") + 1]), Path(args[args.index("--out") + 1])
        kept = G.RUNS not in work.parts
        with self.lock:  # what it was, where its per-user cache was, its levels, and the run folder's other folders
            self.calls.append(("kept" if kept else "private", work.name, env.get("SONGCHARTER_CACHE"),
                               args[args.index("--levels") + 1] if "--levels" in args else "expert",
                               sorted(p.name for p in work.parent.iterdir() if p != work and p.name != "cache")))
        time.sleep(self.delay)
        stages = []
        for stage, rel in self.FILES.items():
            f = work / rel
            cached = f.is_file()
            if not cached:
                f.parent.mkdir(parents=True, exist_ok=True)
                f.write_text(f"{stage} of {args[3]}\n")
            stages.append({"stage": stage, "seconds": 0.0, "cached": cached})
        (work / "guitar" / "work").mkdir(exist_ok=True)
        (work / "guitar" / "work" / "scratch.bin").write_bytes(b"autochart")
        if self.inplace and not kept:
            with open(work / self.inplace, "a") as f:
                f.write("written in place\n")
        (work / "pipeline.json").write_text(json.dumps({"stages": stages}))
        out.mkdir(parents=True)
        text = "".join((work / rel).read_text() for rel in self.FILES.values())
        (out / "notes.chart").write_text(text + ("all levels\n" if "--levels" in args else ""))
        return 0


def fake_scan(folder, env):
    text = (Path(folder) / "notes.chart").read_text()
    return {"delay": 0, "chart_offset": 0, "playable": True, "chartIssues": [], "tracks": [
        {"instrument": "guitar", "difficulty": "expert", "hash": G.hashlib.sha256(text.encode()).hexdigest(),
         "notes": [{"tick": 0}, {"tick": 0}, {"tick": 480}]}]}


def fake_score(song, folder, out_json, env):
    return {"tracks": {"guitar": {"expert": {"f1_50": prf(8, 10, 10), "f1_100": prf(9, 10, 10)}}},
            "beat_f1": prf(9, 10, 10), "lag_ms": 0.0}


@pytest.fixture
def refs(tmp_path):
    root = tmp_path / "refs"
    for sid in ("song_a", G.TEST_SONG):
        (root / sid).mkdir(parents=True)
        (root / sid / "input.wav").write_bytes(b"not audio: the build is a stand-in")
    (root / "song_a" / "ref").mkdir()
    (root / "songs.json").write_text(json.dumps([{"id": "song_a", "title": "Song A", "artist": "Band"}]))
    return root


def context(tmp_path, refs, out="out", chart=None, **kw):
    return G.Context(out=tmp_path / out, work=tmp_path / "work", code=tmp_path / "code", refs=refs,
                     chart=chart or FakeChart(), scan=fake_scan, score=fake_score, say=lambda line: None, **kw)


def kept_state(work):
    return {sid: G.manifest(work / sid) for sid in ("song_a", G.TEST_SONG)}


def test_run_makes_each_kept_folder_once_and_never_writes_into_it(tmp_path, refs):
    songs = G.reference_set(refs)
    assert [(s.id, s.has_ref, s.title) for s in songs] == [("song_a", True, "Song A"),
                                                           (G.TEST_SONG, False, "test_song")]
    chart = FakeChart()
    first, code = G.run(songs, context(tmp_path, refs, chart=chart, env={"SONGCHARTER_CACHE": str(tmp_path / "mine")}))
    assert code == 0
    work = tmp_path / "work"
    for sid in ("song_a", G.TEST_SONG):
        t = first["run"]["songs"][sid]
        assert t["cold"] is not None and t["ran"] == [] and t["unasked"] == []
        assert (work / sid / G.KEPT).is_file() and not (work / sid / "guitar" / "work").exists()  # scratch gone
    kept = kept_state(work)
    second, code = G.run(songs, context(tmp_path, refs, out="out2", chart=chart))
    third, _ = G.run(songs, context(tmp_path, refs, out="out3", chart=chart, rerun=("bass",)))
    assert code == 0 and kept_state(work) == kept
    assert [c[0] for c in chart.calls] == ["kept", "private", "kept", "private"] + ["private"] * 4
    assert all(c[2] and G.RUNS in c[2] for c in chart.calls)  # the build's own empty per-user cache, never mine
    assert [c[3] for c in chart.calls[:4]] == ["expert", "all", "expert", "all"]  # a kept folder's build: Expert
    assert [c[4] for c in chart.calls if c[0] == "private"] == [[]] * 6  # one song's build folder at a time
    assert all(second["run"]["songs"][s]["cold"] is None and second["run"]["songs"][s]["ran"] == [] for s in kept)
    assert all(third["run"]["songs"][s]["ran"] == ["bass"] and third["run"]["songs"][s]["unasked"] == [] for s in kept)
    assert G.results(first) == G.results(second)
    assert first["songs"] == third["songs"] and third["options"]["rerun"] == ["bass"]
    assert list((work / G.RUNS).iterdir()) == []
    a = first["songs"]["song_a"]
    assert a["exit"] == 0 and a["gate_ok"] and a["folder"] == "song_a" and a["scores"]["guitar"]["expert"]["f1_50"]
    assert a["parts"]["guitar"]["expert"]["onsets"] == 2 and "scores" not in first["songs"][G.TEST_SONG]
    on_disk = json.loads((tmp_path / "out" / "summary.json").read_text())
    assert G.results(on_disk) == G.results(first)
    assert (tmp_path / "out" / "logs" / "song_a.pipeline.json").is_file()


def test_the_build_folder_links_the_stems_and_copies_the_engines(tmp_path, refs):
    G.run(G.reference_set(refs, ("song_a",)), context(tmp_path, refs))
    kept, private = tmp_path / "work" / "song_a", tmp_path / "private"
    G.private_folder(kept, private, ("guitar",))
    assert os.path.samefile(private / "decode.wav", kept / "decode.wav")
    assert os.path.samefile(private / "stems" / "k" / "guitar.wav", kept / "stems" / "k" / "guitar.wav")
    assert (private / "bass" / "notes.chart").read_text() == (kept / "bass" / "notes.chart").read_text()
    assert not os.path.samefile(private / "bass" / "notes.chart", kept / "bass" / "notes.chart")
    assert not (private / "guitar").exists() and not (private / G.KEPT).exists()


def test_a_build_that_writes_into_a_copied_engine_folder_leaves_the_kept_one(tmp_path, refs):
    songs = G.reference_set(refs, ("song_a",))
    G.run(songs, context(tmp_path, refs))
    kept = kept_state(tmp_path / "work")
    summary, code = G.run(songs, context(tmp_path, refs, out="out2", chart=FakeChart(inplace="drums/notes.chart")))
    assert code == 0 and kept_state(tmp_path / "work") == kept


def test_a_build_that_writes_into_a_linked_stem_is_caught(tmp_path, refs):
    songs = G.reference_set(refs, ("song_a",))
    G.run(songs, context(tmp_path, refs))
    summary, code = G.run(songs, context(tmp_path, refs, out="out2", chart=FakeChart(inplace="stems/k/guitar.wav")))
    assert code == 1 and "the kept folder" in summary["songs"]["song_a"]["error"]
    assert "stems/k/guitar.wav" in summary["songs"]["song_a"]["error"]
    assert list((tmp_path / "work" / G.RUNS).iterdir()) == []


def test_two_runs_at_once_make_a_kept_folder_once(tmp_path, refs):
    songs = G.reference_set(refs)
    chart, got = FakeChart(delay=0.3), {}

    def go(name):
        got[name] = G.run(songs, context(tmp_path, refs, out=name, chart=chart))

    threads = [threading.Thread(target=go, args=(n,)) for n in ("x", "y")]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert got["x"][1] == got["y"][1] == 0
    assert sorted(c[0] for c in chart.calls) == ["kept", "kept", "private", "private", "private", "private"]
    assert G.results(got["x"][0]) == G.results(got["y"][0])
    colds = [s for name in "xy" for s, t in got[name][0]["run"]["songs"].items() if t["cold"]]
    assert sorted(colds) == ["song_a", G.TEST_SONG]


def test_run_refuses_an_output_in_use_or_inside_the_work_folder(tmp_path, refs):
    songs = G.reference_set(refs)
    with G.locked(tmp_path / "out" / ".golden.lock"):
        with pytest.raises(G.Refused, match="another run"):
            G.run(songs, context(tmp_path, refs))
    with pytest.raises(G.Refused, match="apart"):
        G.run(songs, context(tmp_path, refs, out="work/out"))
    with pytest.raises(G.Refused, match="not in the reference set"):
        G.reference_set(refs, ("nope",))


def test_checkout_names_the_commit_and_the_changed_files(tmp_path):
    import subprocess
    repo = tmp_path / "repo"
    (repo / ".claude").mkdir(parents=True)
    for f in (".claude/a.md", "b.py"):
        (repo / f).write_text("x\n")
    git = ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t"]
    subprocess.run(git[:3] + ["init", "-q"], check=True)
    subprocess.run(git + ["add", "."], check=True)
    subprocess.run(git + ["commit", "-qm", "c"], check=True)
    head = subprocess.run(git[:3] + ["rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    assert G.checkout(repo) == {"commit": head, "branch": G.checkout(repo)["branch"], "dirty": []}
    (repo / ".claude" / "a.md").write_text("y\n")
    (repo / "new.txt").write_text("untracked\n")
    assert G.checkout(repo)["dirty"] == [".claude/a.md"]
    assert G.checkout(tmp_path / "not-git") == {"commit": None, "branch": None, "dirty": []}


def test_stems_are_hard_linked_from_a_separation_cache_when_the_key_fits(tmp_path):
    from songcharter import separate as SEP
    folder = tmp_path / "refs" / "s"
    folder.mkdir(parents=True)
    t = np.arange(A.SAMPLE_RATE) / A.SAMPLE_RATE
    A.write_wav(np.stack([np.sin(2 * np.pi * 220 * t)] * 2).astype(np.float32) * 0.3, folder / "input.wav")
    mix = A.decode(folder / "input.wav")
    key = SEP.cache_key(mix, "htdemucs_6s", SEP.MODELS["htdemucs_6s"].revision, 0, 1, 0.25)
    cache = tmp_path / "sepcache"
    (cache / key).mkdir(parents=True)
    for s in ("drums", "bass"):
        A.write_wav(np.zeros_like(mix), cache / key / f"{s}.wav")
    (cache / key / "info.json").write_text(json.dumps({"stems": ["drums", "bass"], "info": {}}))
    song = G.Song("s", folder, "s", "x", False)
    got = G.seed_stems(song, tmp_path / "kept", cache)
    assert got["key"] == key and got["linked"] == ["drums", "bass"]
    for s in ("drums", "bass"):
        assert os.path.samefile(tmp_path / "kept" / "stems" / key / f"{s}.wav", cache / key / f"{s}.wav")
    assert (tmp_path / "kept" / "stems" / key / "info.json").read_text() == (cache / key / "info.json").read_text()
    assert G.seed_stems(song, tmp_path / "kept", cache)["linked"] == ["drums", "bass"]  # again: nothing to do
    A.write_wav(np.zeros((2, 100), dtype=np.float32), cache / key / "bass.wav")  # not as long as the decode
    short = G.seed_stems(song, tmp_path / "kept2", cache)
    assert short["linked"] == [] and "not as long" in short["why"]
    assert G.seed_stems(song, tmp_path / "kept3", tmp_path / "empty")["linked"] == []
