"""M8-14: the friend's word on each chart (ui/feedback.py; GET and POST /api/jobs/<id>/feedback), its way back in the
diagnostics zip (feedback.json), the versions of a song in the library (<16 hex>/v<N>/<name>, ids
`<16 hex>:<name>:v<N>`), "Chart it differently" (POST /api/jobs/<id>/again: the next seed, into the queue) and the
replace question naming the versions. Made-up songs only; the chart program is a stand-in (CHART)."""
import hashlib
import http.client
import io
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.parse
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from songcharter import diagnostics, wsl
from songcharter.ui import feedback as FB
from songcharter.ui import jobs as J
from songcharter.ui import server as S

sys.path.insert(0, str(Path(__file__).parent))
from test_diagnostics import check_no_audio  # noqa: E402

DOCTOR = {"device": {"chosen": "cpu", "reason": "no NVIDIA GPU found"}, "gpu": None, "guitar_device": "cpu",
          "guitar_reason": "no GPU", "notes": [], "ok": True, "cpu": {"logical": 4, "threads_default": 3},
          "problems": [], "components": {}}
A, B, C = "aaaaaaaaaaaaaaaa", "bbbbbbbbbbbbbbbb", "cccccccccccccccc"
FIRST = "Made-Up Band - First Song"
DRUMS = "Made-Up Band - Drum Song"
INI = "[song]\nname = First Song\nartist = Made-Up Band\ncharter = songcharter\n"
# a chart's record of how it was made (pipeline.folder_record), made up but shaped
PIPELINE = {"seed": 0, "device": {"asked": "auto", "chosen": "cpu"},
            "takes": {"asked": 4, "planned": 4, "made": 4, "seeds": [20260609, 101, 202, 303], "devices": ["cpu"] * 4,
                      "cpu_retries": []}, "fallbacks": [{"stage": "device", "from": "cuda", "to": "cpu"}],
            "engines": {"separation": {"model": "htdemucs_6s", "revision": "3c5ee475be62", "seed": 42},
                        "guitar": {"engine": "made-up-1", "install": "c" * 12}}}
# the stand-in chart: its command line's --seed and --title, a song folder with a report.json as assemble writes it
CHART = r'''
import json, os, sys
out = sys.argv[1]
args = dict(a[2:].split("=", 1) for a in sys.argv[2:] if a.startswith("--") and "=" in a)
seed = int(args.get("seed", "0"))
def ev(**e):
    sys.stderr.write("@@songcharter " + json.dumps(e) + "\n"); sys.stderr.flush()
ev(event="plan", stages=["guitar"])
ev(event="take", index=1, count=1, seed=20260609 + seed)
os.makedirs(out, exist_ok=True)
open(os.path.join(out, "notes.chart"), "w").write("[Song]\n{\n}\n// seed %d\n" % seed)
open(os.path.join(out, "song.ini"), "w").write("[song]\nname = First Song\nartist = Made-Up Band\ncharter = songcharter\n")
json.dump({"gate": {"ok": True}, "config": {"parts": [{"instrument": "guitar"}], "levels": ["expert"],
           "metadata": {"name": "First Song", "artist": "Made-Up Band"}}, "audio": {"duration": 200.0},
           "lead_in": {"pad_seconds": 2.5}, "pipeline": {"seed": seed}}, open(os.path.join(out, "report.json"), "w"))
ev(event="result", ok=True, exit=0, folder=out, work="/w", preview=None, summary="gate: OK")
'''


def jpeg(size=(64, 48)) -> bytes:
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", size, (200, 30, 30)).save(buf, "JPEG")
    return buf.getvalue()


def report(*, seed=0, parts=("guitar", "bass", "drums"), lyrics=False, art=None, duration=245.0, ok=True,
           pipeline=True) -> dict:
    rec = {"gate": {"ok": ok}, "audio": {"duration": duration, "path": "/made/up/work/decode.wav"},
           "lead_in": {"pad_seconds": 2.5},
           "config": {"parts": [{"instrument": p, "source": f"/made/up/work/{p}/notes.chart"} for p in parts],
                      "levels": ["expert", "hard"], "solos": ["Solo 1"], "split_audio": True,
                      "metadata": {"name": "First Song", "artist": "Made-Up Band", "album": "First Song - (Single)",
                                   "genre": "Unknown", "year": "1999", "charter": "songcharter", "album_track": 3}}}
    if pipeline:
        rec["pipeline"] = {**PIPELINE, "seed": seed}
    if lyrics:
        rec["lyrics"] = {"phrases": 12, "events": 80}
    if art:
        rec["art"] = art
    return rec


def chart(home: Path, key: str, name: str, when: float, *, version: int = 1, ini: str = INI, rec: dict | None = None,
          files: dict | None = None) -> Path:
    base = home / "library" / key / (f"v{version}" if version > 1 else "")
    folder = base / name
    folder.mkdir(parents=True)
    (folder / "notes.chart").write_text("[Song]\n{\n}\n", encoding="utf-8")
    (folder / "song.ogg").write_bytes(b"OggS" + bytes(16))
    (folder / "song.ini").write_text(ini, encoding="utf-8")
    for f, data in (files or {}).items():
        (folder / f).write_bytes(data)
    (folder / "report.json").write_text(json.dumps(rec if rec is not None else report(seed=version - 1)),
                                        encoding="utf-8")
    os.utime(folder / "report.json", (when, when))
    return folder


def song_upload(home: Path, key: str = A, name: str = "First Song.wav") -> Path:
    folder = home / "uploads" / key
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "song.wav").write_bytes(b"RIFF made-up")
    (folder / "upload.json").write_text(json.dumps({"id": key, "name": name, "file": "song.wav", "bytes": 12,
                                                    "metadata": {"name": "First Song", "artist": "Made-Up Band"},
                                                    "seconds": 245.0}), encoding="utf-8")
    return folder


@pytest.fixture
def lib(tmp_path, monkeypatch):
    """A server on a made-up library: First Song (its song file still uploaded) as version 1 and version 2, a drums-only
    chart (no guitar), and a Songs folder; its charts are made by CHART."""
    monkeypatch.setattr(wsl, "is_wsl", lambda: False)
    home, root = tmp_path / "home", tmp_path / "cache"
    home.mkdir()
    (home / "doctor.json").write_text(json.dumps(DOCTOR), encoding="utf-8")
    script = tmp_path / "chart.py"
    script.write_text(CHART, encoding="utf-8")
    first = chart(home, A, FIRST, 1000)
    second = chart(home, A, FIRST, 2000, version=2)
    drums = chart(home, B, DRUMS, 500, ini=INI.replace("First Song", "Drum Song"), rec=report(parts=("drums",)))
    song_upload(home)
    commands = []

    def command(song, out, options, threads):
        cmd = J.chart_command(Path(song), out, options, threads)
        commands.append(cmd)
        return [sys.executable, str(script), str(out), *cmd[5:]]

    app = S.App(home, jobs=J.Jobs(home, command=command), log=S.Log(None, console=lambda t: None),
                report=lambda: DOCTOR, cache_root=root)
    servers = S.bind(app, [0])
    songs = tmp_path / "Songs"
    songs.mkdir()
    ctx = SimpleNamespace(app=app, port=servers[0].server_address[1], home=home, root=root, first=first,
                          second=second, drums=drums, songs=songs, commands=commands, tmp=tmp_path)
    assert post(ctx, "/api/clonehero", {"folder": str(songs)})[0] == 200
    yield ctx
    app.queue.shutdown()
    for s in servers:
        s.shutdown()
        s.server_close()


def call(port, method, path, body=None, headers=None, host=None):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=15)
    try:
        conn.request(method, path, body=body, headers={"Host": host or f"127.0.0.1:{port}", **(headers or {})})
        r = conn.getresponse()
        return r.status, r.headers, r.read()
    finally:
        conn.close()


def guarded(port):
    return {"X-Songcharter": "1", "Origin": f"http://127.0.0.1:{port}"}


def post(ctx, path, value=None, headers=None):
    status, _, body = call(ctx.port, "POST", path, b"" if value is None else json.dumps(value).encode(),
                           guarded(ctx.port) if headers is None else headers)
    return status, json.loads(body) if body else None


def get(ctx, path, host=None):
    status, _, body = call(ctx.port, "GET", path, host=host)
    return status, json.loads(body) if body else None


def by_id(chart_id: str, rest: str = "") -> str:
    return f"/api/jobs/{urllib.parse.quote(chart_id, safe='')}{rest}"


V1, V2 = f"{A}:{FIRST}", f"{A}:{FIRST}:v2"


def wait_idle(app, timeout=20.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        snap = app.queue.snapshot()
        if not any(e["state"] in ("charting", "waiting") for e in snap["entries"]):
            return snap
        time.sleep(0.05)
    raise AssertionError(app.queue.snapshot())


# ------------------------------------------------------------------------------------------------ how it played

def test_a_rating_and_spots_are_saved_by_the_charts_id(lib):
    """GET a chart's feedback (empty at first, with the song's length as Clone Hero plays it and the reasons), POST a
    rating, change it, take it back; mark spots (kept in time order, the reasons in the list's order, the note as
    written), remove one; the library lists each chart's rating and spot count (breaks: the rating or a spot not
    saved; the list without them)."""
    status, fb = get(lib, by_id(V1, "/feedback"))
    assert status == 200 and fb["chart"] == V1 and fb["rating"] is None and fb["spots"] == []
    assert fb["length"] == 247.5 and fb["note_max"] == 300   # 245 s of song and its 2.5 s lead-in
    assert [r["id"] for r in fb["reasons"]] == ["too_many_chords", "missing_notes", "extra_notes", "off_beat",
                                                "hard_to_read", "great"]
    assert [r["words"] for r in fb["reasons"]][-1] == "Great part"
    assert post(lib, by_id(V1, "/feedback"), {"rating": 4})[1]["rating"] == 4
    assert post(lib, by_id(V1, "/feedback"), {"rating": 2})[1]["rating"] == 2
    note = "  the solo's chords: way too many  "
    status, fb = post(lib, by_id(V1, "/feedback"), {"add": {"at": "2:28", "reasons": ["off_beat", "too_many_chords"],
                                                            "note": note}})
    assert status == 200 and fb["spots"] == [{"id": fb["spots"][0]["id"], "at": 148, "time": "2:28",
                                              "reasons": ["too_many_chords", "off_beat"], "note": note}]
    status, fb = post(lib, by_id(V1, "/feedback"), {"add": {"at": "0:31", "reasons": ["great"], "note": "   "}})
    assert [(s["time"], s["note"]) for s in fb["spots"]] == [("0:31", None), ("2:28", note)]
    status, fb = post(lib, by_id(V1, "/feedback"), {"add": {"at": 61, "reasons": ["missing_notes"]}})
    assert [s["time"] for s in fb["spots"]] == ["0:31", "1:01", "2:28"]
    status, fb = post(lib, by_id(V1, "/feedback"), {"remove": fb["spots"][1]["id"]})
    assert status == 200 and [s["time"] for s in fb["spots"]] == ["0:31", "2:28"]
    charts = {c["id"]: c for c in get(lib, "/api/library")[1]["charts"]}
    assert (charts[V1]["rating"], charts[V1]["spots"]) == (2, 2)
    assert (charts[V2]["rating"], charts[V2]["spots"]) == (None, 0)   # a version's own, not the first's
    assert post(lib, by_id(V1, "/feedback"), {"rating": None})[1]["rating"] is None
    assert get(lib, by_id(V1, "/feedback"))[1]["rating"] is None


@pytest.mark.parametrize("body, error", [
    ({"rating": 0}, "the rating is 1 to 5"), ({"rating": 6}, "the rating is 1 to 5"),
    ({"rating": "4"}, "the rating is 1 to 5"), ({"rating": True}, "the rating is 1 to 5"),
    ({"rating": 3.5}, "the rating is 1 to 5"),
    ({"add": {"at": "2:75", "reasons": ["great"]}}, "2:75 is not a time: write minutes and seconds, such as 2:28"),
    ({"add": {"at": "148", "reasons": ["great"]}}, "148 is not a time"),
    ({"add": {"at": "", "reasons": ["great"]}}, "nothing is not a time"),
    ({"add": {"at": "4:08", "reasons": ["great"]}}, "4:08 is after the song's end (4:07)"),
    ({"add": {"at": -3, "reasons": ["great"]}}, "the time is minutes and seconds"),
    ({"add": {"at": True, "reasons": ["great"]}}, "the time is minutes and seconds"),
    ({"add": {"at": "1:00", "reasons": []}}, "choose at least one reason for the spot"),
    ({"add": {"at": "1:00"}}, "choose at least one reason for the spot"),
    ({"add": {"at": "1:00", "reasons": ["boring"]}}, "'boring' is not a reason"),
    ({"add": {"at": "1:00", "reasons": "great"}}, "choose at least one reason"),
    ({"add": {"at": "1:00", "reasons": ["great"], "note": "x" * 301}}, "the note is 301 characters: at most 300"),
    ({"add": {"at": "1:00", "reasons": ["great"], "note": 5}}, "the note is text"),
    ({"add": "1:00"}, "a spot is a time and its reasons"),
    ({"remove": "nope"}, "no such spot"), ({"remove": None}, "no such spot"),
    ({}, "give one of rating, add or remove"), ({"rating": 3, "remove": "x"}, "give one of rating, add or remove"),
])
def test_bad_feedback_is_refused_in_plain_words(lib, body, error):
    """Each bad change is a 400 with why, and nothing is saved (breaks: a check dropped or loosened)."""
    status, answer = post(lib, by_id(V1, "/feedback"), body)
    assert status == 400 and answer["error"].startswith(error), answer
    assert not FB.path_for(lib.home, V1).exists()


def test_the_limits_and_the_song_length(lib):
    """A note of exactly 300 characters is kept; 4:07 (the song's end, lead-in counted) is taken; at most SPOTS_MAX
    spots; a chart whose length is unknown is not checked for it (breaks: an off-by-one at either limit)."""
    status, fb = post(lib, by_id(V1, "/feedback"), {"add": {"at": "4:07", "reasons": ["great"], "note": "é" * 300}})
    assert status == 200 and fb["spots"][0]["note"] == "é" * 300
    for i in range(FB.SPOTS_MAX - 1):
        assert post(lib, by_id(V1, "/feedback"), {"add": {"at": i, "reasons": ["great"]}})[0] == 200
    assert post(lib, by_id(V1, "/feedback"), {"add": {"at": 1, "reasons": ["great"]}}) == (
        400, {"error": f"this chart has {FB.SPOTS_MAX} spots marked already"})
    rec = json.loads((lib.first / "report.json").read_text())
    del rec["audio"]
    (lib.first / "report.json").write_text(json.dumps(rec))
    assert get(lib, by_id(V1, "/feedback"))[1]["length"] is None
    assert FB.parse_time("99:59", None) == 5999


def test_feedback_is_kept_with_the_chart_not_in_its_folder_and_survives_a_restart(lib):
    """The record is <home>/state/feedback/<24 hex>.json (by the chart's id, which it holds), never in the song folder
    Install copies into Clone Hero; a new server on the same home reads it; a re-chart of the same folder leaves it
    (breaks: written into the song folder; kept in memory only)."""
    post(lib, by_id(V1, "/feedback"), {"rating": 5})
    post(lib, by_id(V1, "/feedback"), {"add": {"at": "1:15", "reasons": ["hard_to_read"], "note": "busy"}})
    path = FB.path_for(lib.home, V1)
    assert path.parent == lib.home / "state" / "feedback"
    assert path.name == hashlib.sha256(V1.encode()).hexdigest()[:24] + ".json"
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["chart"] == V1 and saved["rating"] == 5 and saved["notes_sha"] == hashlib.sha256(
        (lib.first / "notes.chart").read_bytes()).hexdigest()[:16]
    assert sorted(p.name for p in lib.first.iterdir()) == ["notes.chart", "report.json", "song.ini", "song.ogg"]
    other = S.App(lib.home, jobs=J.Jobs(lib.home, command=lambda *a: pytest.fail("no chart")),
                  log=S.Log(None, console=lambda t: None), report=lambda: DOCTOR, cache_root=lib.root)
    servers = S.bind(other, [0])
    try:
        status, _, body = call(servers[0].server_address[1], "GET", by_id(V1, "/feedback"))
        fb = json.loads(body)
        assert status == 200 and fb["rating"] == 5 and [(s["time"], s["note"]) for s in fb["spots"]] == [
            ("1:15", "busy")]
    finally:
        for s in servers:
            s.shutdown()
            s.server_close()
    (lib.first / "notes.chart").write_text("[Song]\n{\n}\n// charted again\n", encoding="utf-8")
    assert json.loads(path.read_text(encoding="utf-8"))["rating"] == 5
    path.write_text("{broken", encoding="utf-8")   # a damaged record reads as none, never an error
    assert get(lib, by_id(V1, "/feedback"))[1]["rating"] is None


def test_feedback_routes_are_guarded_and_take_ids_not_paths(lib):
    """Host on the GET; Host, X-Songcharter and Origin on the POST; a path, a climb or an unknown id never reaches a
    record (breaks: the route outside _handle's guards; an id made into a path)."""
    assert get(lib, by_id(V1, "/feedback"), host=f"evil.example:{lib.port}")[0] == 403
    for headers in ({}, {"X-Songcharter": "1"}, {"Origin": f"http://127.0.0.1:{lib.port}"},
                    {"X-Songcharter": "1", "Origin": "http://evil.example"}):
        for rest, value in (("/feedback", {"rating": 3}), ("/again", {})):
            assert post(lib, by_id(V1, rest), value, headers=headers)[0] == 403, (rest, headers)
    for path in (f"/api/jobs/{A}/{urllib.parse.quote(FIRST)}/feedback", f"/api/jobs/{A}%2F..%2F{B}/feedback",
                 "/api/jobs/" + urllib.parse.quote(str(lib.first), safe="") + "/feedback"):
        assert post(lib, path, {"rating": 3})[0] == 404, path
    assert post(lib, by_id(f"{C}:{FIRST}", "/feedback"), {"rating": 3}) == (
        400, {"error": f"{FIRST}'s folder is not there any more: it was moved or deleted"})
    assert get(lib, by_id(f"{C}:{FIRST}", "/feedback"))[0] == 404
    assert post(lib, "/api/jobs/current/feedback", {"rating": 3}) == (400, {"error": "no finished chart yet"})
    assert not (lib.home / "state" / "feedback").exists() and not (lib.home / "state" / "versions.json").exists()


# ------------------------------------------------------------------------------------------------ the diagnostics

def test_the_diagnostics_zip_carries_every_charts_feedback_and_no_path(lib, tmp_path):
    """feedback.json: each chart rated or with spots (not one never rated), with its chart's report.json `pipeline`
    and whether its folder is still there (a deleted one keeps its record); no path of the machine's; the note as
    written; through the page's GET /api/diagnostics too; check_no_audio.py passes (breaks: feedback left out; a
    path in it; the pipeline not attached)."""
    post(lib, by_id(V1, "/feedback"), {"rating": 4})
    note = "chords at the bridge – too many"
    post(lib, by_id(V2, "/feedback"), {"add": {"at": "3:01", "reasons": ["too_many_chords"], "note": note}})
    post(lib, by_id(f"{B}:{DRUMS}", "/feedback"), {"rating": 3})
    post(lib, by_id(f"{B}:{DRUMS}", "/feedback"), {"rating": None})   # taken back: nothing to send
    shutil.rmtree(lib.second)   # deleted in Windows after he marked a spot on it
    out = diagnostics.bundle(lib.home, tmp_path / "d.zip", cache_root=lib.root, report=lambda: {"ok": True},
                             clonehero_info=lambda home: {"folder": None})
    z = zipfile.ZipFile(out)
    data = z.read("feedback.json")
    fb = json.loads(data)
    assert [c["chart"] for c in fb["charts"]] == [V1, V2]
    first, second = fb["charts"]
    assert first["rating"] == 4 and first["spots"] == [] and first["now"]["there"] is True
    assert first["now"]["pipeline"] == PIPELINE and first["now"]["ok"] is True and first["now"]["length"] == 247.5
    assert first["now"]["notes_sha"] == first["notes_sha"]   # the chart he rated is the one there
    assert second["spots"][0]["note"] == note and second["spots"][0]["at"] == 181
    assert second["now"] == {"there": False}
    assert fb["reasons"]["great"] == "Great part"
    text = data.decode("utf-8")
    for where in (str(lib.home), str(lib.root), str(tmp_path), str(Path.home())):
        assert where not in text, where
    assert "/" not in json.dumps(fb["charts"])   # no path at all in the charts' records
    manifest = z.read("MANIFEST.txt").decode("utf-8")
    assert "feedback.json" in manifest and "the player's own words" in manifest
    assert check_no_audio().main([str(out)]) == 0
    status, headers, body = call(lib.port, "GET", "/api/diagnostics")
    assert status == 200 and json.loads(zipfile.ZipFile(io.BytesIO(body)).read("feedback.json"))["charts"][0][
        "chart"] == V1


def test_no_feedback_json_until_a_chart_is_rated(lib, tmp_path):
    """With no rating and no spot (a record taken back included), the zip has no feedback.json, and its manifest says
    why (break: an empty file, or nothing said)."""
    post(lib, by_id(V1, "/feedback"), {"rating": 2})
    post(lib, by_id(V1, "/feedback"), {"rating": None})
    z = zipfile.ZipFile(diagnostics.bundle(lib.home, tmp_path / "d.zip", cache_root=lib.root, report=lambda: {},
                                           clonehero_info=lambda home: {}))
    assert "feedback.json" not in z.namelist()
    assert "No chart has a rating or a marked spot yet, so there is no feedback.json." in z.read(
        "MANIFEST.txt").decode("utf-8")


def test_the_diagnostics_guard_covers_the_files_it_makes(tmp_path):
    """Bundle.json goes through `refused` as a copied file does: a record over MAX_BYTES stays out, said in the
    manifest's list (break: Bundle.json writing whatever it is given)."""
    with zipfile.ZipFile(tmp_path / "z.zip", "w") as z:
        b = diagnostics.Bundle(z)
        assert b.json("small.json", {"a": 1}, "here") is True
        assert b.json("feedback.json", {"note": "x" * diagnostics.MAX_BYTES}, "the page's ratings") is False
        assert b.json("x.png", {"a": 1}, "a made-up picture name") is False
    assert [n for n, _, _ in b.added] == ["small.json"]
    assert b.left[0][0] == "the page's ratings" and b.left[0][1].endswith(f"over {diagnostics.MAX_BYTES}")
    assert b.left[1][1] == "a picture (PNG)"


def test_the_diagnostics_go_on_when_the_feedback_cannot_be_read(tmp_path, monkeypatch):
    """A bug reading the feedback records puts its error into feedback.json; the rest of the zip is made (break: the
    whole bundle failing)."""
    monkeypatch.setattr(FB, "for_diagnostics", lambda home, find: 1 / 0)
    out = diagnostics.bundle(tmp_path / "home", tmp_path / "d.zip", cache_root=tmp_path / "cache",
                             report=lambda: {}, clonehero_info=lambda home: {})
    z = zipfile.ZipFile(out)
    assert json.loads(z.read("feedback.json")) == {"error": "ZeroDivisionError: division by zero"}
    assert "MANIFEST.txt" in z.namelist()


# ------------------------------------------------------------------------------------------------ versions

def test_versions_live_beside_the_first_and_are_listed_together(lib):
    """A seed N > 0 charts into <16 hex>/v<N+1>/<name> (output_folder); the library lists a song's versions
    together, each with its version, seed and id `<hex>:<name>:v<N>`; the id finds its own folder, a v1 id with
    ":v1" or a version that is not there finds none (breaks: a version overwriting the first; the versions apart in
    the list; an id naming the wrong version)."""
    up = {"id": A, "path": "/x/song.wav", "metadata": {"name": "First Song", "artist": "Made-Up Band"}}
    assert J.output_folder(lib.home, up, J.parse_options({})) == lib.home / "library" / A / FIRST
    assert J.output_folder(lib.home, up, J.parse_options({"seed": 1})) == lib.home / "library" / A / "v2" / FIRST
    assert J.output_folder(lib.home, up, J.parse_options({"seed": 9})) == lib.home / "library" / A / "v10" / FIRST
    third = chart(lib.home, C, "Other - Third", 1500)
    charts = J.library(lib.home, None)
    assert [(c["id"], c["version"], c["seed"]) for c in charts] == [
        (V2, 2, 1), (V1, 1, 0), (f"{C}:Other - Third", 1, 0), (f"{B}:{DRUMS}", 1, 0)]
    assert J.find_chart(lib.home, V2) == lib.second and J.find_chart(lib.home, V1) == lib.first
    for bad in (f"{V1}:v1", f"{V1}:v3", f"{A}:v2", f"{A}:{FIRST}:v2:v2", f"{A}:{FIRST}:2"):
        assert J.find_chart(lib.home, bad) is None, bad
    assert J.chart_id(lib.second) == V2 and J.upload_of(lib.second) == A and J.version_of(third) == 1
    (lib.home / "library" / A / "v2" / "report.json").write_text("{}")   # a v-folder that is itself a chart: not walked
    assert J.find_chart(lib.home, V2) is None
    rec = report(seed=5)
    assert J.chart_seed(lib.first, rec) == 5 and J.chart_seed(lib.second, {}) == 1


def test_look_finds_a_versions_work_folder(lib):
    """A version's work folder is the song's (cache.by_key by its upload's 16 hex, not its v<N> folder's name): Look
    and its preview while that folder's last chart is this version (break: the key read from the version folder)."""
    from songcharter import cache
    work = lib.root / "work" / f"song-{A}"
    work.mkdir(parents=True)
    cache.mark(work, Path("song.wav"), A, None)
    (work / "pipeline.json").write_text(json.dumps({"assemble": {"folder": str(lib.second)}, "preview": {"ok": False}}))
    charts = {c["id"]: c for c in J.library(lib.home, lib.root)}
    assert charts[V2]["look"] is True and charts[V1]["look"] is False
    assert J.Charted(lib.second, lib.root).result()["work"] == str(work)


def test_the_seed_reaches_the_command_line_and_is_checked():
    """--seed=N only for a seed > 0 (the default's command line unchanged); the options' seed checked as the
    pipeline's (breaks: --seed=0 added; a bad seed let through)."""
    out = Path("/l/x")
    assert not any(a.startswith("--seed") for a in J.chart_command(Path("/s.mp3"), out, J.parse_options({}), None))
    assert "--seed=3" in J.chart_command(Path("/s.mp3"), out, J.parse_options({"seed": 3}), None)
    assert J.parse_options({"seed": 3}).as_dict()["seed"] == 3
    for bad in (-1, True, "2", 1.5, 1_000_000):
        with pytest.raises(J.InputError, match="seed is a whole number from 0 to 999999"):
            J.parse_options({"seed": bad})


def test_the_versions_install_into_one_folder_and_the_question_names_them(lib):
    """Version 2 goes into the same Clone Hero folder as version 1: its install asks to replace, naming the version
    there and its own; the replace puts it in; version 1's install then names version 2 as the one there (breaks:
    the versions in two folders; the 409 without the versions)."""
    status, answer = post(lib, by_id(V1, "/install"), {"replace": False})
    assert status == 200 and answer["installed"] == str(lib.songs / FIRST) and answer["version"] == 1
    status, answer = post(lib, by_id(V2, "/install"), {"replace": False})
    assert status == 409 and answer["ours"] and answer["folder"] == str(lib.songs / FIRST)
    assert (answer["version"], answer["installed_version"]) == (2, 1), answer
    status, answer = post(lib, by_id(V2, "/install"), {"replace": True})
    assert status == 200 and answer["version"] == 2
    assert json.loads((lib.songs / FIRST / "report.json").read_text())["pipeline"]["seed"] == 1
    assert [p.name for p in lib.songs.iterdir() if not p.name.startswith(".")] == [FIRST]
    status, answer = post(lib, by_id(V1, "/install"), {"replace": False})
    assert status == 409 and (answer["version"], answer["installed_version"]) == (1, 2)
    (lib.songs / FIRST / "report.json").unlink()   # not ours any more: no version to name
    status, answer = post(lib, by_id(V1, "/install"), {"replace": False})
    assert status == 409 and not answer["ours"] and answer["installed_version"] is None


def test_the_queues_duplicate_rule_keys_on_the_upload_and_the_seed(tmp_path):
    """A song already waiting or charting is refused only with the same seed: another seed is another version, which
    the list takes, and says which (breaks: the rule on the upload alone; the version not in the list)."""
    home = tmp_path / "home"
    jobs = J.Jobs(home, command=lambda *a: [sys.executable, "-c", "import time; time.sleep(30)"])
    q = J.Queue(jobs, home, prepare=lambda e: ({"id": e["upload"]["id"], "path": "/s.wav", "metadata": {}},
                                               J.parse_options(e["options"]), "cpu"))
    try:
        up = {"id": A, "name": "First Song.wav", "seconds": 60}
        assert q.add(up, {})[1] is not None
        with pytest.raises(J.InputError, match="already in the list: it is charting now"):
            q.add(up, {"seed": 0})
        entry, job = q.add(up, {"seed": 1})
        assert job is None and entry["state"] == "waiting"
        with pytest.raises(J.InputError, match="already in the list: it is charted in its turn"):
            q.add(up, {"seed": 1})
        assert q.add(up, {"seed": 2})[0]["state"] == "waiting"
        assert [e["version"] for e in q.snapshot()["entries"]] == [1, 2, 3]
        assert J.entry_seed({"seed": True}) == 0 and J.entry_seed(None) == 0 and J.entry_seed({"seed": 4}) == 4
    finally:
        q.shutdown()


# ------------------------------------------------------------------------------------------------ chart it differently

def test_chart_it_differently_queues_the_next_seed_with_the_charts_options(lib):
    """From version 2 (seed 1): the next seed is 2, version 3, with the options its report.json records (the parts
    charted, the levels, the solos, split audio, the song.ini's values, the device and takes asked for); the stand-in
    chart makes it in v3/ beside the others; the next press gives version 4 (breaks: the seed not moved on; the options
    not kept; a version overwritten)."""
    status, answer = post(lib, by_id(V2, "/again"), {})
    assert status == 202 and answer["state"] == "charting" and (answer["version"], answer["seed"]) == (3, 2), answer
    entry = lib.app.queue.snapshot_entries()[0]
    assert entry["options"] == {"title": "First Song", "artist": "Made-Up Band", "album": "First Song - (Single)",
                                "genre": "Unknown", "year": "1999", "instruments": ["guitar", "bass", "drums"],
                                "levels": ["expert", "hard"], "solos": ["Solo 1"], "one_audio": False,
                                "device": "auto", "takes": 4, "seed": 2, "name": FIRST}
    assert entry["upload"]["id"] == A
    wait_idle(lib.app)
    cmd = lib.commands[-1]
    assert "--seed=2" in cmd and f"--out={lib.home / 'library' / A / 'v3' / FIRST}" in cmd and "--takes=4" in cmd
    assert "--stems" not in cmd and "--one-audio" not in cmd and "--levels=expert,hard" in cmd
    charts = {c["id"]: c for c in J.library(lib.home, None)}
    assert charts[f"{A}:{FIRST}:v3"]["seed"] == 2 and (lib.first / "notes.chart").read_text() == "[Song]\n{\n}\n"
    assert post(lib, by_id(V1, "/again"), {})[1]["version"] == 4   # from version 1 too: the song's next seed
    assert json.loads((lib.home / "state" / "versions.json").read_text()) == {A: 3}
    wait_idle(lib.app)


def test_a_deleted_version_is_not_made_again(lib):
    """The last seed asked for is kept (state/versions.json): with versions 2 and 3 deleted in Windows and the list
    cleared, the next is version 4, never a deleted version's seed again (break: the next seed from the library and
    the queue alone)."""
    assert post(lib, by_id(V1, "/again"), {})[1]["seed"] == 2
    wait_idle(lib.app)
    shutil.rmtree(lib.home / "library" / A / "v2")
    shutil.rmtree(lib.home / "library" / A / "v3")
    assert post(lib, "/api/queue/clear")[0] == 200 and lib.app.queue.snapshot()["entries"] == []
    assert post(lib, by_id(V1, "/again"), {})[1]["seed"] == 3
    wait_idle(lib.app)


def test_a_song_file_no_longer_here_is_asked_for_again(lib):
    """The uploads go after 7 days: "Chart it differently" then answers 400 with drop and the song's name; a dropped
    file that is another song is refused; the same file (the same upload id) goes ahead (breaks: no drop answer; any
    file taken as the song)."""
    shutil.rmtree(lib.home / "uploads" / A)
    status, answer = post(lib, by_id(V1, "/again"), {})
    assert status == 400 and answer == {"error": "songcharter no longer has the song file of First Song: drop it "
                                                 "again to chart it differently", "drop": True, "name": "First Song"}
    song_upload(lib.home, C, "Other.wav")
    status, answer = post(lib, by_id(V1, "/again"), {"upload": C})
    assert status == 400 and answer["error"].startswith("That is not the song file First Song was charted from")
    song_upload(lib.home)   # dropped again: the same file, the same id
    status, answer = post(lib, by_id(V1, "/again"), {"upload": A})
    assert status == 202 and answer["version"] == 3, answer
    wait_idle(lib.app)


def test_chart_it_differently_needs_a_guitar_and_a_readable_report(lib):
    """A chart without a guitar part would come out the same: 400; one whose report.json does not read: 400; neither
    asks for a seed (breaks: a chart without a guitar charted again; a damaged report a 500)."""
    status, answer = post(lib, by_id(f"{B}:{DRUMS}", "/again"), {})
    assert status == 400 and answer["error"] == ("Drum Song has no guitar part: charting it again changes only the "
                                                 "guitar, so it would come out the same")
    (lib.first / "report.json").write_text("{not json")
    status, answer = post(lib, by_id(V1, "/again"), {})
    assert status == 400 and "report cannot be read" in answer["error"]
    assert post(lib, by_id(V2, "/again"), {"lyrics": 7}) == (400, {"error": "lyrics is text"})
    assert not (lib.home / "state" / "versions.json").exists()
    with pytest.raises(J.InputError, match="does not say how it was made"):
        J.rechart({"gate": {"ok": True}})


def test_the_pictures_given_come_again_and_the_lyrics_are_pasted_again(lib):
    """A chart made with a given album art and background: "Chart it differently" makes its own album.jpg and
    background.jpg image uploads again (by their upload ids, no path in the queue), an embedded album art is not
    given; pasted lyrics sent with it reach the chart as its memory file, never the queue (breaks: the pictures lost;
    an embedded one forced; lyrics kept in queue.json)."""
    art = {"album_art": {"added": True, "file": "album.jpg", "from": "given"},
           "background": {"added": True, "file": "background.jpg", "from": "given"}}
    shutil.rmtree(lib.second)
    shutil.rmtree(lib.first)
    pictured = chart(lib.home, A, FIRST, 3000, rec=report(art=art, lyrics=True),
                     files={"album.jpg": jpeg((512, 512)), "background.jpg": jpeg((320, 180))})
    status, answer = post(lib, by_id(V1, "/again"), {"lyrics": "La la la\nmade up words\n"})
    assert status == 202 and answer["state"] == "charting", answer
    entry = lib.app.queue.snapshot_entries()[0]
    for key, file, size in (("album_art", "album.jpg", 512), ("background", "background.jpg", 320)):
        image = S.read_upload(lib.home, entry["options"][key], kind="image")
        assert image["name"] == file and image["width"] == size and Path(image["path"]).read_bytes() == (
            pictured / file).read_bytes()
    wait_idle(lib.app)
    cmd = lib.commands[-1]
    assert any(a.startswith("--album-art=") and "/uploads/" in a for a in cmd)
    assert any(a.startswith("--lyrics=/dev/fd/") for a in lib.app.jobs.current.command)   # the job's own, with it
    assert lib.app.jobs.current.options.as_dict()["lyrics"] is True
    queue = (lib.home / "state" / "queue.json").read_text(encoding="utf-8")
    assert "made up words" not in queue and '"lyrics": true' in queue
    art["album_art"]["from"] = "embedded"
    (pictured / "report.json").write_text(json.dumps(report(art={"album_art": art["album_art"]})))
    post(lib, by_id(V1, "/again"), {})
    assert "album_art" not in lib.app.queue.snapshot_entries()[-1]["options"]
    wait_idle(lib.app)


def test_the_results_name_the_chart_in_the_library(lib):
    """The Done screen's results carry the chart's library id, version, guitar and lyrics (what "How did it play?"
    and "Chart it differently" need), by a chart's id and by the job that made it (break: the job's results without
    them)."""
    status, _, body = call(lib.port, "GET", by_id(V2, "/results"))
    assert status == 200 and json.loads(body)["library"] == {"id": V2, "version": 2, "guitar": True, "lyrics": False,
                                                             "rating": None, "spots": 0}
    status, answer = post(lib, by_id(V2, "/again"), {})
    assert status == 202
    wait_idle(lib.app)
    status, _, body = call(lib.port, "GET", f"/api/jobs/{answer['job']}/results")
    res = json.loads(body)
    assert res["library"] == {"id": f"{A}:{FIRST}:v3", "version": 3, "guitar": True, "lyrics": False, "rating": None,
                              "spots": 0}
    assert post(lib, f"/api/jobs/{answer['job']}/feedback", {"rating": 5})[1]["chart"] == f"{A}:{FIRST}:v3"
    assert json.loads(call(lib.port, "GET", f"/api/jobs/{answer['job']}/results")[2])["library"]["rating"] == 5


# ------------------------------------------------------------------------------------------------ the page

PAGE = r"""
const vm = require("vm"), fs = require("fs");
const els = {};
const moves = [];   // [the parent's tag, "out" or "in", the child]: what a list took out and put in
const node = (tag) => ({ tag, hidden: false, textContent: "", className: "", disabled: false, children: [], value: "",
  open: false, checked: false, on: {}, href: "", title: "", replaceChildren(...c) {
    moves.push(...this.children.map((x) => [tag, "out", x]), ...c.map((x) => [tag, "in", x])); this.children = c; },
  removeChild(x) { moves.push([tag, "out", x]); this.children.splice(this.children.indexOf(x), 1); return x; },
  insertBefore(x, ref) { if (this.children.includes(x)) this.removeChild(x);
    moves.push([tag, "in", x]); this.children.splice(ref ? this.children.indexOf(ref) : this.children.length, 0, x); return x; },
  append(...c) { this.children.push(...c); }, remove() {}, addEventListener(kind, f) { this.on[kind] = f; },
  classList: { add() {}, remove() {}, toggle() {} }, removeAttribute() {}, pause() {}, click() {},
  scrollIntoView() {}, focus() {}, select() {} });
const document = { getElementById: (id) => els[id] || (els[id] = node(id)), createElement: node, title: "songcharter",
  visibilityState: "visible", addEventListener() {}, body: node("body") };
const asked = [], confirms = [];
let answers = {};   // "METHOD path" -> [[status, body], ...] (the last one stays)
const answer = (status, value) => ({ status, json: async () => JSON.parse(JSON.stringify(value)) });
const ctx = { navigator: {}, document, window: { addEventListener() {}, confirm: (m) => { confirms.push(m); return true; } },
  encodeURIComponent, console, setInterval() {}, clearInterval() {}, setTimeout(f) { setImmediate(f); },
  sessionStorage: { setItem() {}, getItem() { return null; } }, Date,
  fetch: async (path, init) => {
    const body = init && init.body ? JSON.parse(init.body) : null;
    asked.push([init.method, path, body]);
    const list = answers[`${init.method} ${path}`];
    if (list && list.length) return answer(...(list.length > 1 ? list.shift() : list[0]));
    if (path === "/api/queue") return answer(200, { paused: null, run: 1, left: null, max: 20, entries: [] });
    if (path === "/api/library") return answer(200, { charts: [] });
    return answer(404, { error: "not here" });
  } };
vm.createContext(ctx);
vm.runInContext(fs.readFileSync(process.argv[2], "utf8"), ctx);
const settle = async () => { for (let i = 0; i < 8; i++) await new Promise((ok) => setImmediate(ok)); };
const all = (n, out = []) => { if (n && typeof n === "object") { out.push(n); (n.children || []).forEach((c) => all(c, out)); } return out; };
const find = (n, f) => all(n).find(f);
const flat = (n) => typeof n === "string" ? n : [n.textContent, ...(n.children || []).map(flat)].join(" ");
const words = (n) => flat(n).replace(/\s+/g, " ").trim();
const button = (n, label) => find(n, (x) => x.tag === "button" && x.textContent === label);
const FB = { chart: "aaaaaaaaaaaaaaaa:Made-Up Band - First Song", rating: null, spots: [], length: 247.5, note_max: 300,
  reasons: [{ id: "too_many_chords", words: "Too many chords" }, { id: "missing_notes", words: "Missing notes" },
            { id: "great", words: "Great part" }] };
const V1 = "aaaaaaaaaaaaaaaa:Made-Up Band - First Song", V2 = V1 + ":v2";
const enc = (id) => encodeURIComponent(id);
(async () => {
  const out = {};
  // Your charts: a song's two versions together, each saying which; "Chart it differently" for one with a guitar;
  // "How did it play?" folded under each chart that passed, its line with the rating and spots
  const base = { artist: "Made-Up Band", readable: true, ok: true, audio: "split", stems: false, look: false,
    upload: "aaaaaaaaaaaaaaaa", guitar: true, lyrics: false, rating: null, spots: 0, name: "First Song" };
  const listed = () => [{ ...base, id: V2, folder: "Made-Up Band - First Song", time: 1762682400, version: 2, seed: 1, rating: 4, spots: 1 },
                 { ...base, id: V1, folder: "Made-Up Band - First Song", time: 1762596000, version: 1, seed: 0, lyrics: true },
                 { ...base, id: "bbbbbbbbbbbbbbbb:Other - Drums", upload: "bbbbbbbbbbbbbbbb", name: "Drums", version: 1,
                   seed: 0, time: 1762509600, guitar: false, ok: false }];
  ctx.setCharts(listed());
  const rows = [...els["charts-list"].children];   // as first shown: the list's own children change with each read
  out.rows = rows.map((li) => ({ facts: words(find(li, (x) => x.className === "chart-facts small")),
    buttons: find(li, (x) => x.className === "queue-actions").children.map((b) => b.textContent),
    feedback: (find(li, (x) => x.className === "fold feedback") || {}).children ?
      words(find(li, (x) => x.className === "fold feedback").children[0]) : null }));
  // the box opened: read, then a rating, another, the same again (taken back), a spot and its removal
  const box = find(rows[0], (x) => x.className === "fold feedback");
  answers[`GET /api/jobs/${enc(V2)}/feedback`] = [[200, { ...FB, rating: 4, spots: [{ id: "s1", at: 148, time: "2:28",
    reasons: ["too_many_chords", "great"], note: "busy \"bridge\"" }] }]];
  box.open = true;
  box.on.toggle();
  await settle();
  const body = box.children[1];
  out.opened = { line: box.children[0].textContent, text: words(body) };
  answers[`POST /api/jobs/${enc(V2)}/feedback`] = [[200, { ...FB, rating: 5, spots: [] }]];
  button(body, "5").on.click();
  await settle();
  out.rated = { line: box.children[0].textContent, pressed: box.children[1].children[0].children
    .filter((b) => b.tag === "button").map((b) => b.className) };
  answers[`POST /api/jobs/${enc(V2)}/feedback`] = [[200, { ...FB, rating: null }]];
  button(box.children[1], "5").on.click();   // the pressed one again: taken back
  await settle();
  const form = find(box.children[1], (x) => x.className === "spot-form");
  const msg = find(box.children[1], (x) => /feedback-msg/.test(x.className));
  button(form, "Mark it").on.click();   // no time: said, nothing sent
  await settle();
  out.noTime = [msg.textContent, msg.hidden];
  find(form, (x) => x.className === "spot-at").value = "1:05";
  button(form, "Mark it").on.click();   // no reason: said, nothing sent
  await settle();
  out.noReason = msg.textContent;
  const ticks = all(form).filter((x) => x.tag === "input" && x.type === "checkbox");
  ticks[0].checked = true;
  ticks[2].checked = true;
  find(form, (x) => x.className === "spot-note-input").value = "my own words";
  answers[`POST /api/jobs/${enc(V2)}/feedback`] = [[400, { error: "1:05 is after the song's end (0:59)" }]];
  button(form, "Mark it").on.click();
  await settle();
  out.refused = [msg.textContent, msg.hidden, find(form, (x) => x.className === "spot-at").value];
  answers[`POST /api/jobs/${enc(V2)}/feedback`] = [[200, { ...FB, spots: [{ id: "s9", at: 65, time: "1:05",
    reasons: ["too_many_chords", "great"], note: "my own words" }] }]];
  button(form, "Mark it").on.click();
  await settle();
  out.marked = { line: box.children[0].textContent, spots: words(find(box.children[1], (x) => x.className === "spots")) };
  answers[`POST /api/jobs/${enc(V2)}/feedback`] = [[200, { ...FB }]];
  button(find(box.children[1], (x) => x.className === "spots"), "Remove").on.click();
  await settle();
  out.feedbackAsked = asked.filter((a) => a[1].endsWith("/feedback")).map((a) => [a[0], a[2]]);
  // "Chart it differently": straight to the queue; with lyrics, asked for them first; the song file asked for again
  answers[`POST /api/jobs/${enc(V2)}/again`] = [[202, { job: null, entry: "e1", state: "waiting", version: 3, seed: 2 }]];
  await button(rows[0], "Chart it differently").on.click();
  await settle();
  out.waits = find(rows[0], (x) => x.className === "queue-msg small").textContent;
  await button(rows[1], "Chart it differently").on.click();
  const panel = find(rows[1], (x) => x.className === "chart-again");
  out.panel = words(panel);
  find(panel, (x) => x.tag === "textarea").value = "made up line\n";
  answers[`POST /api/jobs/${enc(V1)}/again`] = [[400, { error: "songcharter no longer has the song file of First Song: drop it again to chart it differently", drop: true, name: "First Song" }]];
  button(panel, "Chart it").on.click();
  await settle();
  out.drop = { banner: els["again-drop"].hidden, text: els["again-drop-text"].textContent, screen: els["drop-screen"].hidden,
    again: vm.runInContext("JSON.stringify(state.again)", ctx) };
  answers[`POST /api/jobs/${enc(V1)}/again`] = [[202, { job: null, entry: "e2", state: "waiting", version: 4, seed: 3 }]];
  ctx.uploaded([{ id: "aaaaaaaaaaaaaaaa", name: "First Song.wav" }, { id: "cccccccccccccccc", name: "x.wav" }], []);
  await settle();
  out.two = els["drop-error"].textContent;
  ctx.uploaded([{ id: "aaaaaaaaaaaaaaaa", name: "First Song.wav" }], []);
  await settle();
  out.redrop = { banner: els["again-drop"].hidden, msg: els["drop-error"].textContent,
    again: vm.runInContext("state.again", ctx), options: els["options-screen"].hidden };
  out.againAsked = asked.filter((a) => a[1].endsWith("/again")).map((a) => [a[1], a[2]]);
  // the replace question names the versions
  out.questions = [ctx.replaceQuestion({ version: 2, installed_version: 1 }, "First Song"),
    ctx.replaceQuestion({ version: 2, installed_version: 2 }, "First Song"),
    ctx.replaceQuestion({ version: 1, installed_version: 1 }, "First Song"),
    ctx.replaceQuestion({ version: 1, installed_version: 3 }, "this song", "C:\\S\\F")];
  // the Done screen: its version, the folded box and "Chart it differently"; none of them without a library chart
  ctx.renderPlayed({ ok: true, folder: "/h/library/aaaaaaaaaaaaaaaa/v2/Made-Up Band - First Song",
    library: { id: V2, version: 2, guitar: true, lyrics: false, rating: null, spots: 0 } });
  out.done = { version: [els["done-version"].textContent, els["done-version"].hidden], played: els.played.hidden,
    parts: els.played.children.map((c) => c.className), button: !!button(els.played, "Chart it differently") };
  // a rating given in the Done screen's box: the chart's row in Your charts says it too, and the list as read
  ctx.setCharts(listed());
  const rowBox = find(els["charts-list"].children[0], (x) => x.className === "fold feedback");
  const doneBox = els.played.children[0];
  answers[`GET /api/jobs/${enc(V2)}/feedback`] = [[200, { ...FB, rating: null }]];
  doneBox.open = true;
  doneBox.on.toggle();
  await settle();
  answers[`POST /api/jobs/${enc(V2)}/feedback`] = [[200, { ...FB, rating: 2, spots: [{ id: "s3", at: 9, time: "0:09",
    reasons: ["great"], note: null }] }]];
  button(doneBox.children[1], "2").on.click();
  await settle();
  out.synced = { done: doneBox.children[0].textContent, row: rowBox.children[0].textContent,
    listed: vm.runInContext("JSON.stringify(state.charts.map((c) => [c.rating, c.spots]))", ctx),
    key: vm.runInContext("state.chartsKey === JSON.stringify(state.charts)", ctx) };
  ctx.renderPlayed({ ok: false, folder: "/h/x.failed", library: { id: V1, version: 1, guitar: true, lyrics: false } });
  out.failed = { version: els["done-version"].hidden, parts: els.played.children.map((c) => c.className) };
  ctx.renderPlayed({ ok: true, folder: "/h/x", library: null });
  out.none = [els.played.hidden, els["done-version"].hidden];
  // the queue's row says the version
  out.queueRow = words(ctx.queueRow({ id: "e", state: "waiting", name: "First Song.wav", chart: null, version: 3 }).children[0]);
  console.log(JSON.stringify(out));
})().catch((e) => { console.error(e); process.exit(1); });
"""


@pytest.mark.skipif(shutil.which("node") is None, reason="needs node")
def test_the_page_rates_marks_and_charts_it_differently(tmp_path):
    """The page (app.js in node, a stand-in DOM): "Your charts" says each version of a song, offers "Chart it
    differently" for a chart with a guitar and "How did it play?" folded under a chart that passed, its line with the
    rating and spots; opened, it reads the record, rates (the pressed one again takes it back), marks a spot (a missing
    time or reason said before sending; a refusal said, what was typed kept) and removes one; "Chart it differently"
    queues the next version, asks for the lyrics again first for a chart that had them, and for the song file when
    songcharter no longer has it, then sends the dropped file's upload, not the options form; the replace question
    names the versions; the Done screen shows the version and both controls (breaks: a control offered without its
    condition; a body sent wrong; the dropped file sent to the options)."""
    script = tmp_path / "played.cjs"
    script.write_text(PAGE, encoding="utf-8")
    app_js = tmp_path / "app.js"
    app_js.write_bytes(S.static_files()["app.js"])
    done = subprocess.run(["node", str(script), str(app_js)], capture_output=True, text=True, timeout=60,
                          env={**os.environ, "TZ": "UTC", "LANG": "en_US.UTF-8"})
    assert done.returncode == 0, done.stderr
    out = json.loads(done.stdout)
    v2, v1, drums = out["rows"]
    assert v2["facts"].startswith("version 2 · Nov 9, 2025") and v1["facts"].startswith("version 1 · Nov 8, 2025")
    assert drums["facts"].startswith("Nov 7, 2025")   # a song without versions says none
    assert v2["buttons"] == ["Install", "Open", "Chart it differently"] and drums["buttons"] == ["Open"]
    assert v2["feedback"] == "How did it play? 4 of 5, 1 spot marked" and v1["feedback"] == "How did it play?"
    assert drums["feedback"] is None
    assert out["opened"]["line"] == "How did it play? 4 of 5, 1 spot marked"
    assert "2:28 Too many chords, Great part : busy \"bridge\" Remove" in out["opened"]["text"]
    assert "Mark a spot When, as Clone Hero shows it (the song is 4:07)" in out["opened"]["text"]
    assert out["rated"]["line"] == "How did it play? 5 of 5"
    assert out["rated"]["pressed"] == ["plain small-button rate"] * 4 + ["small-button rate on"]
    assert out["noTime"] == ["Write when, as minutes and seconds: 2:28, say.", False]
    assert out["noReason"] == "Tick at least one reason."
    assert out["refused"] == ["1:05 is after the song's end (0:59)", False, "1:05"]
    assert out["marked"] == {"line": "How did it play? 1 spot marked",
                             "spots": "1:05 Too many chords, Great part : my own words Remove"}
    assert out["feedbackAsked"] == [["GET", None], ["POST", {"rating": 5}], ["POST", {"rating": None}],
                                    ["POST", {"add": {"at": "1:05", "reasons": ["too_many_chords", "great"],
                                                      "note": "my own words"}}],
                                    ["POST", {"add": {"at": "1:05", "reasons": ["too_many_chords", "great"],
                                                      "note": "my own words"}}],
                                    ["POST", {"remove": "s9"}]]
    assert out["waits"] == "Version 3 waits in the list: it is charted in its turn."
    assert out["panel"].startswith("This chart had lyrics. songcharter does not keep pasted lyrics")
    assert out["drop"]["banner"] is False and out["drop"]["screen"] is False
    assert out["drop"]["text"].startswith("To chart First Song differently, drop its song file again")
    assert json.loads(out["drop"]["again"]) == {"ref": V1, "name": "First Song", "lyrics": "made up line\n"}
    assert out["two"] == "Drop only the song file of First Song."
    assert out["redrop"]["banner"] is True and out["redrop"]["again"] is None
    assert out["redrop"]["msg"] == "Version 4 waits in the list: it is charted in its turn."
    assert out["redrop"]["options"] is not False   # the dropped file went to "Chart it differently", not the form
    enc = urllib.parse.quote
    assert out["againAsked"] == [[f"/api/jobs/{enc(V2, safe='')}/again", {}],
                                 [f"/api/jobs/{enc(V1, safe='')}/again", {"lyrics": "made up line\n"}],
                                 [f"/api/jobs/{enc(V1, safe='')}/again", {"lyrics": "made up line\n",
                                                                          "upload": A}]]
    assert out["questions"] == ["Version 1 of First Song is in Clone Hero now. Replace it with version 2?",
                                "Version 2 of First Song is in Clone Hero already, from an earlier chart. Replace it?",
                                "First Song is in Clone Hero already, from an earlier chart. Replace the older chart?",
                                "Version 3 of this song is in Clone Hero now (C:\\S\\F). Replace it with version 1?"]
    assert out["done"] == {"version": ["Version 2: this song charted differently.", False], "played": False,
                           "parts": ["fold feedback", "actions", "small", "chart-again", "small again-msg"],
                           "button": True}
    assert out["synced"]["done"] == out["synced"]["row"] == "How did it play? 2 of 5, 1 spot marked"
    assert json.loads(out["synced"]["listed"]) == [[2, 1], [None, 0], [None, 0]] and out["synced"]["key"] is True
    # (breaks: syncFeedback not called; the list as read not patched, so its next read makes the rows again)
    assert out["failed"] == {"version": True, "parts": ["actions", "small", "chart-again", "small again-msg"]}
    assert out["none"] == [True, True]
    assert out["queueRow"] == "First Song.wav (version 3)"
    html = S.static_files()["index.html"].decode()
    assert 'id="again-drop"' in html and 'id="played"' in html and 'id="done-version"' in html


# ------------------------------------------------------------------------------------------------ the review's fixes

# a stand-in chart that names the song as the pipeline does: song_metadata over the uploaded file's own path (its
# 40-character safe stem) and tags, with the command line's --title and --artist over them
NAMED = r'''
import json, os, sys
from pathlib import Path
from songcharter import pipeline as P
out, song = sys.argv[1], sys.argv[2]
args = dict(a[2:].split("=", 1) for a in sys.argv[3:] if a.startswith("--") and "=" in a)
seed = int(args.get("seed", "0"))
meta, _ = P.song_metadata(Path(song), P.read_tags(Path(song)), {"name": args.get("title"),
                                                                "artist": args.get("artist")})
def ev(**e):
    sys.stderr.write("@@songcharter " + json.dumps(e) + "\n"); sys.stderr.flush()
ev(event="plan", stages=["guitar"])
os.makedirs(out, exist_ok=True)
open(os.path.join(out, "notes.chart"), "w").write("[Song]\n{\n}\n// %d\n" % seed)
open(os.path.join(out, "song.ini"), "w").write(
    "[song]\nname = %s\nartist = %s\ncharter = songcharter\n" % (meta["name"], meta["artist"]))
json.dump({"gate": {"ok": True}, "config": {"parts": [{"instrument": "guitar"}], "levels": ["expert"],
           "solos": "labels", "split_audio": True, "metadata": meta}, "audio": {"duration": 30.0},
           "lead_in": {"pad_seconds": 2.5}, "pipeline": {"seed": seed}}, open(os.path.join(out, "report.json"), "w"))
ev(event="result", ok=True, exit=0, folder=out, work="/w", preview=None, summary="gate: OK")
'''


@pytest.fixture
def named(tmp_path, monkeypatch):
    """A server whose charts are named as the pipeline names them (NAMED), with a Songs folder."""
    monkeypatch.setattr(wsl, "is_wsl", lambda: False)
    home = tmp_path / "home"
    home.mkdir()
    (home / "doctor.json").write_text(json.dumps(DOCTOR), encoding="utf-8")
    script = tmp_path / "named.py"
    script.write_text(NAMED, encoding="utf-8")
    root = Path(__file__).resolve().parents[1]

    def command(song, out, options, threads):
        return [sys.executable, str(script), str(out), str(song), *J.chart_command(Path(song), out, options,
                                                                                   threads)[5:]]

    app = S.App(home, jobs=J.Jobs(home, command=command, env={**os.environ, "PYTHONPATH": str(root)}),
                log=S.Log(None, console=lambda t: None), report=lambda: DOCTOR, cache_root=tmp_path / "cache")
    servers = S.bind(app, [0])
    songs = tmp_path / "Songs"
    songs.mkdir()
    ctx = SimpleNamespace(app=app, port=servers[0].server_address[1], home=home, songs=songs, tmp=tmp_path)
    assert post(ctx, "/api/clonehero", {"folder": str(songs)})[0] == 200
    yield ctx
    app.queue.shutdown()
    for s in servers:
        s.shutdown()
        s.server_close()


def wav_bytes(tmp_path, tags=None) -> bytes:
    """A second of made-up sound as WAV, with these tags (ffmpeg's -metadata) when given."""
    import numpy as np
    from songcharter import audio as AU
    raw = tmp_path / "raw.wav"
    t = np.arange(AU.SAMPLE_RATE) / AU.SAMPLE_RATE
    y = (0.1 * np.sin(2 * np.pi * 220 * t)).astype(np.float32)
    AU.write_wav(np.stack([y, y]), raw)
    if not tags:
        return raw.read_bytes()
    out = tmp_path / "tagged.wav"
    meta = [x for k, v in tags.items() for x in ("-metadata", f"{k}={v}")]
    subprocess.run([AU.ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-y", "-i", str(raw), *meta, "-c", "copy",
                    str(out)], check=True)
    return out.read_bytes()


def upload_song(ctx, data: bytes, name: str) -> dict:
    status, _, body = call(ctx.port, "POST", "/api/upload", data,
                           {**guarded(ctx.port), "X-Filename": urllib.parse.quote(name)})
    assert status == 200, body
    return json.loads(body)


@pytest.mark.parametrize("name, options, tags", [
    ("Made Up Band - A Long Made Up Song Title Here.wav", {}, None),   # a several-song drop: no song fields
    ("Made Up Band - A Long Made Up Song Title Here.wav", {"title": "A Long Made Up Song Title Here",
                                                           "artist": "Made Up Band"}, None),
    ("track 07.wav", {}, {"title": "A Made Up Tagged Song", "artist": "Tagged Made Up Band"}),
])
def test_every_version_keeps_the_first_charts_folder_name(named, name, options, tags):
    """The review's F1: an untagged song with a long name, charted from a several-song drop (no title, no artist:
    version 1's folder is named from upload.json, its song.ini from the uploaded file's 40-character stem), as one
    drop with the page's fields, and a tagged file: version 2 (and version 3, through "drop the file again") lands in a
    folder of version 1's own name, with the same song.ini name and artist; installed after version 1, it asks to
    replace it in the one Clone Hero folder; the queue entry keeps the name (queue.json, so a restart too) (break: the
    version's name made again from the metadata)."""
    data = wav_bytes(named.tmp, tags)   # once: a float WAV's PEAK chunk holds the second it was written
    up = upload_song(named, data, name)
    assert post(named, "/api/jobs", {"upload": up["id"], "options": options})[0] == 202
    wait_idle(named.app)
    (v1,) = J.chart_folders(named.home)
    status, answer = post(named, by_id(J.chart_id(v1), "/again"), {})
    assert status == 202 and answer["version"] == 2, answer
    entry = named.app.queue.snapshot_entries()[-1]
    assert entry["options"]["name"] == v1.name
    assert json.loads((named.home / "state" / "queue.json").read_text())["entries"][-1]["options"]["name"] == v1.name
    wait_idle(named.app)
    v2 = v1.parent / "v2" / v1.name
    assert v2.is_dir(), [str(p.relative_to(named.home)) for p in J.chart_folders(named.home)]
    ini = [{k: v for k, v in (line.split(" = ", 1) for line in (f / "song.ini").read_text().splitlines()[1:])}
           for f in (v1, v2)]
    assert ini[0] == ini[1]   # the same song.ini name and artist: Clone Hero lists one song
    assert post(named, by_id(J.chart_id(v1), "/install"), {"replace": False})[0] == 200
    status, answer = post(named, by_id(J.chart_id(v2), "/install"), {"replace": False})
    assert status == 409 and (answer["version"], answer["installed_version"]) == (2, 1)
    assert answer["folder"] == str(named.songs / v1.name)
    shutil.rmtree(named.home / "uploads" / up["id"])   # the song file gone: dropped again, the name kept
    assert post(named, by_id(J.chart_id(v2), "/again"), {})[1]["drop"] is True
    assert upload_song(named, data, name)["id"] == up["id"]
    status, answer = post(named, by_id(J.chart_id(v2), "/again"), {"upload": up["id"]})
    assert status == 202 and answer["version"] == 3, answer
    wait_idle(named.app)
    assert (v1.parent / "v3" / v1.name).is_dir()


def test_the_name_option_is_one_path_component():
    """`name` (a version's folder name) is one path component and no version or failed folder's name; refused
    otherwise, never joined as a path (break: a separator or a climb let through)."""
    up = {"id": A, "path": "/x/s.wav", "metadata": {}}
    home = Path("/h")
    assert J.output_folder(home, up, J.parse_options({"seed": 1, "name": "Made Up - Name"})) == \
        home / "library" / A / "v2" / "Made Up - Name"
    assert J.parse_options({"name": "Ünïcode Made-Up - Song [Live]"}).name == "Ünïcode Made-Up - Song [Live]"
    for bad in ("../x", "a/b", "a\\b", "..", ".", ".hidden", "", " x", "x ", "a:b", "v2", "Song.failed", "a\x00b",
                "a\nb", "x" * 256, 7, ["x"]):
        with pytest.raises(J.InputError, match="name is a song folder's name"):
            J.parse_options({"name": bad})


def test_a_refused_press_uses_no_version_number(lib):
    """The review's F3: "Chart it differently" refused after its seed was worked out (here lyrics with no word to
    time, twice) writes no versions.json; the next accepted press is the next number in line, version 3 (break: the
    seed recorded before the queue took the song: version 5)."""
    for _ in range(2):
        status, answer = post(lib, by_id(V2, "/again"), {"lyrics": "!!!"})
        assert status == 400 and "no word" in answer["error"], answer
    assert not (lib.home / "state" / "versions.json").exists()
    assert post(lib, by_id(V2, "/again"), {})[1]["version"] == 3
    assert json.loads((lib.home / "state" / "versions.json").read_text()) == {A: 2}
    wait_idle(lib.app)


@pytest.mark.parametrize("raw", [b'{"add": {"at": 1e400, "reasons": ["great"]}}',
                                 b'{"add": {"at": Infinity, "reasons": ["great"]}}',
                                 b'{"add": {"at": NaN, "reasons": ["great"]}}',
                                 b'{"add": {"at": 99999999, "reasons": ["great"]}}',
                                 b'{"add": {"at": 1' + b'0' * 400 + b', "reasons": ["great"]}}'])
def test_a_time_that_is_no_finite_number_is_a_plain_400(lib, raw):
    """The review's F5 (a): an infinite, NaN or huge time is the plain 400 of any bad time, not a 500 (break: int()
    of an infinity); the second review's R2: so is a whole number too long for a float (break: math.isfinite on it,
    an OverflowError)."""
    status, _, body = call(lib.port, "POST", by_id(V1, "/feedback"), raw, guarded(lib.port))
    assert status == 400 and json.loads(body)["error"] == "the time is minutes and seconds, such as 2:28", body


def test_a_damaged_spot_is_left_out_and_the_rest_still_works(lib, tmp_path):
    """The review's F5 (b): a saved record whose spots hold a non-object, an `at` that is no number or no id: the
    readable spot is shown, the others left out; add, remove, the library and the zip still work (break: every add
    and remove a 500)."""
    good = {"id": "0a0b0c0d", "at": 75, "reasons": ["great"], "note": "made up"}
    path = FB.path_for(lib.home, V1)
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"chart": V1, "rating": 3, "spots": [5, "x", None, {"id": "a1", "at": "1:00",
                    "reasons": ["great"]}, {"at": 9, "reasons": ["great"]}, {"id": "b2", "at": 3, "reasons": "great"},
                    good]}), encoding="utf-8")
    status, fb = get(lib, by_id(V1, "/feedback"))
    assert status == 200 and [s["id"] for s in fb["spots"]] == ["0a0b0c0d"] and fb["rating"] == 3
    charts = {c["id"]: c for c in get(lib, "/api/library")[1]["charts"]}
    assert charts[V1]["spots"] == 1
    status, fb = post(lib, by_id(V1, "/feedback"), {"add": {"at": "0:10", "reasons": ["off_beat"]}})
    assert status == 200 and [s["time"] for s in fb["spots"]] == ["0:10", "1:15"]
    status, fb = post(lib, by_id(V1, "/feedback"), {"remove": "0a0b0c0d"})
    assert status == 200 and [s["time"] for s in fb["spots"]] == ["0:10"]
    path.write_text(json.dumps({"chart": V1, "rating": 4, "spots": [7, good]}), encoding="utf-8")
    z = zipfile.ZipFile(diagnostics.bundle(lib.home, tmp_path / "d.zip", cache_root=lib.root, report=lambda: {},
                                           clonehero_info=lambda home: {}))
    assert [{k: v for k, v in x.items() if k != "around"} for x in json.loads(z.read("feedback.json"))["charts"][0][
        "spots"]] == [good]


def test_a_saved_time_too_long_for_a_float_is_left_out(lib):
    """The second review's R2: a saved spot whose `at` is a whole number too long for a float is left out where it is
    read, as any damaged spot; the record, the library and a rating still answer 200 (break: math.isfinite on it, an
    OverflowError and a 500 that empties Your charts)."""
    good = {"id": "0a0b0c0d", "at": 75, "reasons": ["great"], "note": None}
    path = FB.path_for(lib.home, V1)
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"chart": V1, "rating": 2, "spots": [{"id": "e1", "at": 10 ** 400, "reasons": ["great"],
                                                                     "note": None}, good]}), encoding="utf-8")
    status, fb = get(lib, by_id(V1, "/feedback"))
    assert status == 200 and [s["id"] for s in fb["spots"]] == ["0a0b0c0d"] and fb["rating"] == 2
    status, listed = get(lib, "/api/library")
    assert status == 200 and {c["id"]: c for c in listed["charts"]}[V1]["spots"] == 1
    status, fb = post(lib, by_id(V1, "/feedback"), {"rating": 5})
    assert status == 200 and fb["rating"] == 5 and [s["id"] for s in fb["spots"]] == ["0a0b0c0d"]


def test_the_rechart_estimate_counts_the_guitar_when_the_rest_is_cached(lib):
    """Item 7: with the song's work folder in the cache, a re-chart's estimate is its guitar's takes and the build,
    under a whole chart's; without one, a whole chart's (break: `cached` not passed on)."""
    from songcharter import cache
    from songcharter.ui import estimate as E
    opts = J.parse_options({"takes": 4})
    whole, cached = E.for_job(245.0, opts, "cpu", "cpu"), E.for_job(245.0, opts, "cpu", "cpu", cached=True)
    assert cached["high_s"] < whole["high_s"] and cached["low_s"] < whole["low_s"]
    guitar = [E.GUITAR_ONCE["cpu"][i] * 245 + 4 * (E.TAKE_FIXED[i] + E.GUITAR_TAKE["cpu"][i] * 245 ** 2)
              for i in (0, 1)]
    parts = [E.CACHED, E.ASSEMBLE, E.PREVIEW]
    for i, key in ((0, "low_s"), (1, "high_s")):
        assert cached[key] == round(guitar[i] + sum(f[i] + r[i] * 245 for f, r in parts), 1)
    assert post(lib, by_id(V2, "/again"), {})[0] == 202
    first = lib.app.queue.snapshot_entries()[-1]["estimate"]
    wait_idle(lib.app)
    work = lib.root / "work" / f"song-{A}"
    work.mkdir(parents=True)
    cache.mark(work, Path("song.wav"), A, None)
    assert post(lib, by_id(V2, "/again"), {})[0] == 202
    second = lib.app.queue.snapshot_entries()[-1]["estimate"]
    wait_idle(lib.app)
    assert second["high_s"] < first["high_s"] and first == E.for_job(245.0, J.parse_options({"takes": 4}), "cpu",
                                                                      "cpu")


PAGE2 = PAGE.split("(async () => {")[0] + r"""
(async () => {
  const out = {};
  const base = { artist: "Made-Up Band", readable: true, ok: true, audio: "split", stems: false, look: false,
    upload: "aaaaaaaaaaaaaaaa", guitar: true, lyrics: false, rating: null, spots: 0, name: "First Song" };
  const v2 = { ...base, id: V2, folder: "Made-Up Band - First Song", time: 1762682400, version: 2, seed: 1 };
  const v1 = { ...base, id: V1, folder: "Made-Up Band - First Song", time: 1762596000, version: 1, seed: 0, lyrics: true };
  ctx.setCharts([JSON.parse(JSON.stringify(v2)), JSON.parse(JSON.stringify(v1))]);
  const rowOf = (id) => els["charts-list"].children.find((li) => vm.runInContext("state.chartRows", ctx).get(id).li === li);
  const inputs = (box) => { const f = find(box, (x) => x.className === "spot-form");
    return { at: find(f, (x) => x.className === "spot-at").value, note: find(f, (x) => x.className === "spot-note-input").value,
      ticks: all(f).filter((x) => x.type === "checkbox" && x.checked).map((x) => x.value) }; };
  const type = (box, at, ticks, note) => { const f = find(box, (x) => x.className === "spot-form");
    find(f, (x) => x.className === "spot-at").value = at;
    find(f, (x) => x.className === "spot-note-input").value = note;
    all(f).filter((x) => x.type === "checkbox").forEach((x) => { x.checked = ticks.includes(x.value); }); };
  // (a) a half-typed spot survives a rating saved, a rating refused; a spot saved clears the form
  const row2 = rowOf(V2), box2 = find(row2, (x) => x.className === "fold feedback");
  answers[`GET /api/jobs/${enc(V2)}/feedback`] = [[200, { ...FB }]];
  box2.open = true;
  box2.on.toggle();
  await settle();
  type(box2, "1:05", ["missing_notes"], "half typed, made up");
  answers[`POST /api/jobs/${enc(V2)}/feedback`] = [[200, { ...FB, rating: 3 }]];
  button(box2.children[1], "3").on.click();
  await settle();
  out.afterRating = inputs(box2);
  answers[`POST /api/jobs/${enc(V2)}/feedback`] = [[400, { error: "the rating is 1 to 5" }]];
  button(box2.children[1], "4").on.click();
  await settle();
  out.afterRefusal = inputs(box2);
  // (b) another song ends (a new chart in the list) and the other version's rating changes: this row is the same
  // element, its box open with what was typed; the changed row keeps its open box, its typed spot and its lyrics panel
  const row1 = rowOf(V1), box1 = find(row1, (x) => x.className === "fold feedback");
  answers[`GET /api/jobs/${enc(V1)}/feedback`] = [[200, { ...FB }]];
  box1.open = true;
  box1.on.toggle();
  await settle();
  type(box1, "2:10", ["great"], "the other box");
  const msg2 = find(row2, (x) => x.className === "queue-msg small");
  msg2.textContent = "Installed. In Clone Hero, open Settings > General and press Scan Songs.";
  msg2.hidden = false;
  await button(row1, "Chart it differently").on.click();   // a chart with lyrics: its panel opens, made-up words typed
  find(find(row1, (x) => x.className === "chart-again"), (x) => x.tag === "textarea").value = "zib zab\nzob\n";
  const third = { ...base, id: "cccccccccccccccc:Other - Third", upload: "cccccccccccccccc", name: "Third",
    time: 1762700000, version: 1, seed: 0 };
  // v1 rated 5 with two spots elsewhere (another window, say): its record as read again (R4)
  answers[`GET /api/jobs/${enc(V1)}/feedback`] = [[200, { ...FB, rating: 5, spots: [
    { id: "s7", at: 20, time: "0:20", reasons: ["great"], note: null },
    { id: "s8", at: 30, time: "0:30", reasons: ["great"], note: null }] }]];
  moves.length = 0;
  ctx.setCharts([third, { ...JSON.parse(JSON.stringify(v2)), rating: 3 }, { ...JSON.parse(JSON.stringify(v1)), rating: 5, spots: 2 }]);
  const lis = els["charts-list"].children;
  const new1 = rowOf(V1), newBox1 = find(new1, (x) => x.className === "fold feedback");
  const named = (li) => li === row2 ? "v2" : li === row1 ? "old v1" : li === new1 ? "new v1" : li === rowOf(third.id) ? "third" : "?";
  const pressed = (box) => box.children[1].children[0].children.filter((b) => b.tag === "button" && b.className.endsWith(" on")).map((b) => b.textContent);
  out.afterFinish = { rows: lis.length, same2: rowOf(V2) === row2, open2: box2.open, typed2: inputs(box2),
    msg2: [msg2.textContent, msg2.hidden], newRow1: new1 !== row1, sameBox1: newBox1 === box1, open1: box1.open,
    typed1: inputs(box1), lyrics: find(find(new1, (x) => x.className === "chart-again"), (x) => x.tag === "textarea").value,
    line1: box1.children[0].textContent, pressed1: pressed(box1),
    moves: moves.filter((m) => m[0] === "charts-list").map((m) => [m[1], named(m[2])]) };
  await settle();
  out.freshened = { line1: box1.children[0].textContent, pressed1: pressed(box1), typed1: inputs(box1),
    spots1: words(find(box1, (x) => x.className === "spots")) };
  // a read again with no answer leaves the box as it was shown, what is typed in it kept
  answers[`GET /api/jobs/${enc(V1)}/feedback`] = [[500, { error: "made-up failure" }]];
  ctx.setCharts([third, { ...JSON.parse(JSON.stringify(v2)), rating: 3 }, { ...JSON.parse(JSON.stringify(v1)), rating: 5, spots: 3 }]);
  await settle();
  out.unanswered = { line1: box1.children[0].textContent, typed1: find(box1, (x) => x.className === "spot-form") ?
    inputs(box1) : null, reads: asked.filter((a) => a[1] === `/api/jobs/${enc(V1)}/feedback`).length };
  const now1 = rowOf(V1);
  // a spot saved clears its form
  answers[`POST /api/jobs/${enc(V2)}/feedback`] = [[200, { ...FB, rating: 3, spots: [{ id: "s1", at: 65, time: "1:05",
    reasons: ["missing_notes"], note: "half typed, made up" }] }]];
  button(find(box2, (x) => x.className === "spot-form"), "Mark it").on.click();
  await settle();
  out.afterSaved = inputs(box2);
  // the second review's R5: a save in one of a chart's two boxes (its row's, the Done screen's) keeps what is typed
  // in the other
  ctx.renderPlayed({ ok: true, folder: "/h/library/aaaaaaaaaaaaaaaa/v2/Made-Up Band - First Song",
    library: { id: V2, version: 2, guitar: true, lyrics: false, rating: 3, spots: 1 } });
  const doneBox = els.played.children[0];
  answers[`GET /api/jobs/${enc(V2)}/feedback`] = [[200, { ...FB, rating: 3, spots: [{ id: "s1", at: 65, time: "1:05",
    reasons: ["missing_notes"], note: "half typed, made up" }] }]];
  doneBox.open = true;
  doneBox.on.toggle();
  await settle();
  type(doneBox, "0:42", ["great"], "the done box");
  answers[`POST /api/jobs/${enc(V2)}/feedback`] = [[200, { ...FB, rating: 4, spots: [{ id: "s1", at: 65, time: "1:05",
    reasons: ["missing_notes"], note: "half typed, made up" }] }]];
  button(box2.children[1], "4").on.click();
  await settle();
  out.doneKept = { typed: inputs(doneBox), line: doneBox.children[0].textContent };
  type(box2, "1:11", ["too_many_chords"], "the row box");
  answers[`POST /api/jobs/${enc(V2)}/feedback`] = [[200, { ...FB, rating: 4, spots: [{ id: "s1", at: 65, time: "1:05",
    reasons: ["missing_notes"], note: "half typed, made up" }, { id: "s2", at: 42, time: "0:42", reasons: ["great"],
    note: "the done box" }] }]];
  button(find(doneBox, (x) => x.className === "spot-form"), "Mark it").on.click();
  await settle();
  out.rowKept = { typed: inputs(box2), done: inputs(doneBox), line: box2.children[0].textContent };
  // the review's F4: a refusal keeps the pasted lyrics and says why; once taken, the panel goes
  const panel = find(now1, (x) => x.className === "chart-again");
  answers[`POST /api/jobs/${enc(V1)}/again`] = [[400, { error: "Lyrics only for a song that starts at once: made-up words." }]];
  button(panel, "Chart it").on.click();
  await settle();
  out.refusedLyrics = { text: (find(panel, (x) => x.tag === "textarea") || {}).value || null,
    msg: find(now1, (x) => x.className === "queue-msg small").textContent };
  answers[`POST /api/jobs/${enc(V1)}/again`] = [[202, { job: null, entry: "e3", state: "waiting", version: 3, seed: 2 }]];
  button(panel, "Chart it").on.click();
  await settle();
  out.taken = { panel: panel.children.length, msg: find(now1, (x) => x.className === "queue-msg small").textContent };
  out.againBodies = asked.filter((a) => a[1].endsWith("/again")).map((a) => a[2]);
  console.log(JSON.stringify(out));
})().catch((e) => { console.error(e); process.exit(1); });
"""


@pytest.mark.skipif(shutil.which("node") is None, reason="needs node")
def test_nothing_typed_is_lost(tmp_path):
    """The review's F2 and F4 (app.js in node, the page test's stand-in DOM): a half-typed spot (time, ticks, note)
    stays when a rating is saved or refused, and only a saved spot clears it; another song finishing and another
    chart's change leave a row the same element, its box open with what was typed and its message; a row whose own
    chart changed keeps its open box, typed spot and lyrics panel; a refused "Chart it differently" keeps the pasted
    lyrics and says why, an accepted one empties the panel (breaks: renderFeedback rebuilding an empty form;
    setCharts making every row again; the panel emptied before the answer)."""
    script = tmp_path / "typed.cjs"
    script.write_text(PAGE2, encoding="utf-8")
    app_js = tmp_path / "app.js"
    app_js.write_bytes(S.static_files()["app.js"])
    done = subprocess.run(["node", str(script), str(app_js)], capture_output=True, text=True, timeout=60,
                          env={**os.environ, "TZ": "UTC", "LANG": "en_US.UTF-8"})
    assert done.returncode == 0, done.stderr
    out = json.loads(done.stdout)
    typed = {"at": "1:05", "note": "half typed, made up", "ticks": ["missing_notes"]}
    assert out["afterRating"] == typed and out["afterRefusal"] == typed
    finish = out["afterFinish"]
    assert finish["rows"] == 3 and finish["same2"] is True and finish["open2"] is True and finish["typed2"] == typed
    assert finish["msg2"] == ["Installed. In Clone Hero, open Settings > General and press Scan Songs.", False]
    assert finish["newRow1"] is True and finish["sameBox1"] is True and finish["open1"] is True
    assert finish["typed1"] == {"at": "2:10", "note": "the other box", "ticks": ["great"]}
    assert finish["lyrics"] == "zib zab\nzob\n"
    # the second review's R3: only the row that went is taken out and only the new rows put in; the row that stayed
    # is never taken out of the page, which would lose the field he types in (break: replaceChildren of every row)
    assert finish["moves"] == [["out", "old v1"], ["in", "third"], ["in", "new v1"]]
    # R4: the moved box, read before, says the rating the list says now, and reads its spots again, what is typed
    # kept (breaks: the box not freshened; the spots not read again; the form cleared)
    assert finish["line1"] == "How did it play? 5 of 5" and finish["pressed1"] == ["5"]
    assert out["freshened"] == {"line1": "How did it play? 5 of 5, 2 spots marked", "pressed1": ["5"],
                                "typed1": finish["typed1"], "spots1": "0:20 Great part Remove 0:30 Great part Remove"}
    assert out["unanswered"] == {"line1": "How did it play? 5 of 5, 2 spots marked", "typed1": finish["typed1"],
                                 "reads": 3}   # (break: the box emptied for the error)
    assert out["afterSaved"] == {"at": "", "note": "", "ticks": []}
    # R5: a rating saved in the row's box keeps the Done screen's half-typed spot, and a spot saved in the Done
    # screen's box keeps the row's (break: syncFeedback rendering the other box with its form cleared)
    assert out["doneKept"] == {"typed": {"at": "0:42", "note": "the done box", "ticks": ["great"]},
                               "line": "How did it play? 4 of 5, 1 spot marked"}
    assert out["rowKept"] == {"typed": {"at": "1:11", "note": "the row box", "ticks": ["too_many_chords"]},
                              "done": {"at": "", "note": "", "ticks": []}, "line": "How did it play? 4 of 5, 2 spots marked"}
    assert out["refusedLyrics"] == {"text": "zib zab\nzob\n",
                                    "msg": "Lyrics only for a song that starts at once: made-up words."}
    assert out["taken"] == {"panel": 0, "msg": "Version 3 waits in the list: it is charted in its turn."}
    assert out["againBodies"] == [{"lyrics": "zib zab\nzob\n"}, {"lyrics": "zib zab\nzob\n"}]


PAGE3 = PAGE.split("(async () => {")[0] + r"""
(async () => {
  const out = {};
  const base = { artist: "Made-Up Band", readable: true, ok: true, audio: "split", stems: false, look: false,
    upload: "aaaaaaaaaaaaaaaa", guitar: true, lyrics: true, rating: null, spots: 0, name: "First Song" };
  const v1 = { ...base, id: V1, folder: "Made-Up Band - First Song", time: 1762596000, version: 1, seed: 0 };
  const rowOf = (id) => vm.runInContext("state.chartRows", ctx).get(id).li;
  const own = (li) => button(find(li, (x) => x.className === "queue-actions"), "Chart it differently");
  let gate = null, release = null;   // /again held until released
  const hold = () => { gate = new Promise((ok) => { release = ok; }); };
  const fetched = ctx.fetch;
  const sent = [];   // the /again requests sent, held or not
  ctx.fetch = async (path, init) => {
    if (path.endsWith("/again")) sent.push(JSON.parse(init.body));
    if (path.endsWith("/again") && gate) { await gate; gate = null; }
    return fetched(path, init); };
  const agains = () => [...sent];
  ctx.setCharts([JSON.parse(JSON.stringify(v1))]);
  const row1 = rowOf(V1);
  await own(row1).on.click();   // a chart that had lyrics: the panel
  // the row made again (rated elsewhere) with its panel open: the panel's presses disable the new row's button
  ctx.setCharts([{ ...JSON.parse(JSON.stringify(v1)), rating: 2 }]);
  const row2 = rowOf(V1), panel = find(row2, (x) => x.className === "chart-again");
  find(panel, (x) => x.tag === "textarea").value = "zib zab\n";
  answers[`POST /api/jobs/${enc(V1)}/again`] = [[400, { error: "A made-up refusal." }]];
  hold();
  button(panel, "Without lyrics").on.click();
  button(panel, "Without lyrics").on.click();   // a double click, and "Chart it" too, while the first is out
  button(panel, "Chart it").on.click();
  await settle();
  const states = (li) => [button(panel, "Chart it").disabled, button(panel, "Without lyrics").disabled, own(li).disabled];
  out.held = { sent: agains().length, newRow: row2 !== row1, disabled: states(row2), oldRow: own(row1).disabled };
  // made again once more while the request is out: its new button waits too
  ctx.setCharts([{ ...JSON.parse(JSON.stringify(v1)), rating: 3 }]);
  const row3 = rowOf(V1);
  out.remadeDuring = own(row3).disabled;
  release();
  await settle();
  out.refused = { sent: agains().length, disabled: states(row3), msg: find(row3, (x) => x.className === "queue-msg small").textContent,
    lyrics: find(panel, (x) => x.tag === "textarea").value };
  // taken: two presses on "Chart it", one request; the panel goes
  answers[`POST /api/jobs/${enc(V1)}/again`] = [[202, { job: null, entry: "e2", state: "waiting", version: 2, seed: 1 }]];
  hold();
  button(panel, "Chart it").on.click();
  button(panel, "Chart it").on.click();
  await settle();
  out.heldAgain = agains().length;
  release();
  await settle();
  out.taken = { bodies: agains(), panel: panel.children.length, msg: find(row3, (x) => x.className === "queue-msg small").textContent };
  // the Done screen, as the skeptic found it: a double click on "Without lyrics", one request
  ctx.renderPlayed({ ok: true, folder: "/h/library/aaaaaaaaaaaaaaaa/Made-Up Band - First Song",
    library: { id: V1, version: 1, guitar: true, lyrics: true, rating: null, spots: 0 } });
  const done = els.played;
  await button(done, "Chart it differently").on.click();
  const donePanel = find(done, (x) => x.className === "chart-again");
  answers[`POST /api/jobs/${enc(V1)}/again`] = [[202, { job: null, entry: "e3", state: "waiting", version: 3, seed: 2 }]];
  hold();
  button(donePanel, "Without lyrics").on.click();
  button(donePanel, "Without lyrics").on.click();
  await settle();
  out.done = { sent: agains().length - 2, disabled: [button(donePanel, "Without lyrics").disabled, button(done, "Chart it differently").disabled] };
  release();
  await settle();
  out.doneTaken = { sent: agains().length - 2, enabled: !button(done, "Chart it differently").disabled,
    msg: find(done, (x) => x.className === "small again-msg").textContent };
  console.log(JSON.stringify(out));
})().catch((e) => { console.error(e); process.exit(1); });
"""


@pytest.mark.skipif(shutil.which("node") is None, reason="needs node")
def test_one_press_one_version(tmp_path):
    """The second review's R1 (app.js in node, the page test's stand-in DOM): while a "Chart it differently" request is
    out, a second press on the lyrics panel's "Without lyrics" or "Chart it" sends nothing (they queued a second
    version), and the panel's two buttons and the row's button now are disabled: in a row made again with its panel
    open, the new row's button, not the old one its panel's presses were made with, and in a row made again during the
    request, its new button too; a refusal enables them again and keeps the lyrics; a 202 empties the panel; the Done
    screen's panel the same (breaks: no flag; the old row's button disabled; a row made during it enabled; the flag left
    on after a refusal)."""
    script = tmp_path / "once.cjs"
    script.write_text(PAGE3, encoding="utf-8")
    app_js = tmp_path / "app.js"
    app_js.write_bytes(S.static_files()["app.js"])
    done = subprocess.run(["node", str(script), str(app_js)], capture_output=True, text=True, timeout=60,
                          env={**os.environ, "TZ": "UTC", "LANG": "en_US.UTF-8"})
    assert done.returncode == 0, done.stderr
    out = json.loads(done.stdout)
    assert out["held"] == {"sent": 1, "newRow": True, "disabled": [True, True, True], "oldRow": False}
    assert out["remadeDuring"] is True
    assert out["refused"] == {"sent": 1, "disabled": [False, False, False], "msg": "A made-up refusal.",
                              "lyrics": "zib zab\n"}
    assert out["heldAgain"] == 2
    assert out["taken"] == {"bodies": [{}, {"lyrics": "zib zab\n"}], "panel": 0,
                            "msg": "Version 2 waits in the list: it is charted in its turn."}
    assert out["done"] == {"sent": 1, "disabled": [True, True]}
    assert out["doneTaken"] == {"sent": 1, "enabled": True,
                                "msg": "Version 3 waits in the list: it is charted in its turn."}


# ------------------------------------------------------------------------------------------------ the advisor's fixes

def notes_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:16]


def test_a_rating_stays_with_the_chart_it_was_given_to(lib, tmp_path):
    """The advisor's 1 at v0.5.0's gate: version 1 rated 5 with a spot, then charted again into its own folder (a plain
    chart with other options: another notes.chart there). Its feedback, the library's row and the results say none
    yet, with the earlier chart's rating and spot count for the page's line, and a read writes nothing; the first
    change starts the chart's own record and keeps the earlier one in `earlier` (its notes_sha and updated), which
    the zip carries; charted back to the first chart, its own rating and spot are its again; at most EARLIER_MAX
    earlier ones, the newest first (breaks: the record read by the chart's id alone; the earlier one dropped; the
    library's counts the old chart's; the chart charted back not given its own; no cap)."""
    post(lib, by_id(V1, "/feedback"), {"rating": 5})
    post(lib, by_id(V1, "/feedback"), {"add": {"at": "1:15", "reasons": ["great"], "note": "made up"}})
    first = (lib.first / "notes.chart").read_bytes()
    path = FB.path_for(lib.home, V1)
    (lib.first / "notes.chart").write_text("[Song]\n{\n}\n// charted again with other options\n", encoding="utf-8")
    other = notes_hex((lib.first / "notes.chart").read_bytes())
    status, fb = get(lib, by_id(V1, "/feedback"))
    assert status == 200 and (fb["rating"], fb["spots"], fb["earlier"]) == (None, [], {"rating": 5, "spots": 1})
    charts = {c["id"]: c for c in get(lib, "/api/library")[1]["charts"]}
    assert (charts[V1]["rating"], charts[V1]["spots"]) == (None, 0)
    library = json.loads(call(lib.port, "GET", by_id(V1, "/results"))[2])["library"]
    assert (library["rating"], library["spots"]) == (None, 0)
    assert json.loads(path.read_text(encoding="utf-8"))["rating"] == 5   # read, not written

    def sent(name):
        z = zipfile.ZipFile(diagnostics.bundle(lib.home, tmp_path / name, cache_root=lib.root, report=lambda: {},
                                               clonehero_info=lambda home: {}))
        return next(c for c in json.loads(z.read("feedback.json"))["charts"] if c["chart"] == V1)

    before = sent("before.zip")   # the zip says it so too, before any change
    assert (before["rating"], before["spots"], before["earlier"][0]["rating"]) == (None, [], 5)
    status, fb = post(lib, by_id(V1, "/feedback"), {"rating": 3})
    assert status == 200 and (fb["rating"], fb["spots"], fb["earlier"]) == (3, [], None)
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert (saved["rating"], saved["spots"], saved["notes_sha"]) == (3, [], other)
    (gone,) = saved["earlier"]
    assert (gone["rating"], gone["notes_sha"], [s["note"] for s in gone["spots"]]) == (5, notes_hex(first), ["made up"])
    assert isinstance(gone["updated"], float)
    after = sent("after.zip")
    assert after["rating"] == 3 and after["earlier"][0]["rating"] == 5 and after["earlier"][0]["notes_sha"] == notes_hex(
        first) and after["now"]["notes_sha"] == after["notes_sha"] == other
    (lib.first / "notes.chart").write_bytes(first)   # charted back with the first options: the chart he rated 5
    status, fb = get(lib, by_id(V1, "/feedback"))
    assert (fb["rating"], [s["time"] for s in fb["spots"]], fb["earlier"]) == (5, ["1:15"], None)
    charts = {c["id"]: c for c in get(lib, "/api/library")[1]["charts"]}
    assert (charts[V1]["rating"], charts[V1]["spots"]) == (5, 1)
    assert post(lib, by_id(V1, "/feedback"), {"rating": 4})[1]["spots"][0]["note"] == "made up"
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert [(e["rating"], e["notes_sha"]) for e in saved["earlier"]] == [(3, other)]
    for i in range(FB.EARLIER_MAX + 2):   # charted again and rated, time after time: the newest kept
        (lib.first / "notes.chart").write_text(f"[Song]\n{{\n}}\n// again {i}\n", encoding="utf-8")
        assert post(lib, by_id(V1, "/feedback"), {"rating": 1 + i % 5})[0] == 200
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert len(saved["earlier"]) == FB.EARLIER_MAX and saved["rating"] == 1 + (FB.EARLIER_MAX + 1) % 5
    assert saved["earlier"][0]["notes_sha"] == notes_hex(f"[Song]\n{{\n}}\n// again {FB.EARLIER_MAX}\n".encode())
    assert post(lib, by_id(V1, "/feedback"), {"rating": None})[1]["earlier"] == {"rating": 1 + FB.EARLIER_MAX % 5,
                                                                              "spots": 0}
    assert len(sent("taken back.zip")["earlier"]) == FB.EARLIER_MAX   # this chart's taken back: the earlier sent


PAGE4 = PAGE.split("(async () => {")[0] + r"""
(async () => {
  const out = {};
  const base = { artist: "Made-Up Band", readable: true, ok: true, audio: "split", stems: false, look: false,
    upload: "aaaaaaaaaaaaaaaa", guitar: true, lyrics: false, rating: null, spots: 0, name: "First Song" };
  ctx.setCharts([{ ...base, id: V1, folder: "Made-Up Band - First Song", time: 1762596000, version: 1, seed: 0 }]);
  const box = find(els["charts-list"].children[0], (x) => x.className === "fold feedback");
  answers[`GET /api/jobs/${enc(V1)}/feedback`] = [[200, { ...FB, earlier: { rating: 5, spots: 2 } }]];
  box.open = true;
  box.on.toggle();
  await settle();
  const pressed = () => box.children[1].children[0].children.filter((b) => b.tag === "button" && b.className.endsWith(" on")).length;
  out.opened = { line: box.children[0].textContent, pressed: pressed(),
    spots: find(box.children[1], (x) => x.className === "spots").hidden };
  answers[`POST /api/jobs/${enc(V1)}/feedback`] = [[200, { ...FB, rating: 4, earlier: null }]];
  button(box.children[1], "4").on.click();
  await settle();
  out.rated = { line: box.children[0].textContent, pressed: pressed() };
  out.lines = [ctx.feedbackLine({ rating: null, spots: [], earlier: { rating: 3, spots: 0 } }),
    ctx.feedbackLine({ rating: null, spots: [], earlier: { rating: null, spots: 1 } }),
    ctx.feedbackLine({ rating: 2, spots: [], earlier: { rating: 5, spots: 0 } }), ctx.feedbackLine({ rating: null, spots: 0 })];
  console.log(JSON.stringify(out));
})().catch((e) => { console.error(e); process.exit(1); });
"""


@pytest.mark.skipif(shutil.which("node") is None, reason="needs node")
def test_the_box_says_he_rated_an_earlier_chart(tmp_path):
    """The advisor's 1 (app.js in node, the page test's stand-in DOM): a box whose record is an earlier chart's says
    so in its line, in plain words, with no rating pressed and no spot listed; rated, its line is the chart's own
    (breaks: the earlier rating shown as this chart's; the line not saying it)."""
    script = tmp_path / "earlier.cjs"
    script.write_text(PAGE4, encoding="utf-8")
    app_js = tmp_path / "app.js"
    app_js.write_bytes(S.static_files()["app.js"])
    done = subprocess.run(["node", str(script), str(app_js)], capture_output=True, text=True, timeout=60,
                          env={**os.environ, "TZ": "UTC", "LANG": "en_US.UTF-8"})
    assert done.returncode == 0, done.stderr
    out = json.loads(done.stdout)
    assert out["opened"] == {"line": "You rated an earlier chart of this song 5 of 5, with 2 spots marked. How does "
                                     "this one play?", "pressed": 0, "spots": True}
    assert out["rated"] == {"line": "How did it play? 4 of 5", "pressed": 1}
    assert out["lines"] == ["You rated an earlier chart of this song 3 of 5. How does this one play?",
                            "You marked 1 spot on an earlier chart of this song. How does this one play?",
                            "How did it play? 2 of 5", "How did it play?"]


def held_charts(lib, monkeypatch):
    """Each chart of `lib` held until its gate file is there (<tmp>/go_<its seed>), and its process left running for
    1.5 s after its result when <tmp>/linger_<its seed> is there: (the gate's path, the linger's) for a seed."""
    command = lib.app.jobs.command

    def held(song, out, options, threads):
        cmd = command(song, out, options, threads)
        gate, linger = str(lib.tmp / f"go_{options.seed}"), str(lib.tmp / f"linger_{options.seed}")
        wait = (f"import os, subprocess, sys, time\nwhile not os.path.exists({gate!r}): time.sleep(0.02)\n"
                "code = subprocess.call([sys.executable] + sys.argv[1:])\n"
                f"time.sleep(1.5 if os.path.exists({linger!r}) else 0)\nsys.exit(code)")
        return [cmd[0], "-c", wait, *cmd[1:]]

    monkeypatch.setattr(lib.app.jobs, "command", held)
    return lambda seed: lib.tmp / f"go_{seed}", lambda seed: lib.tmp / f"linger_{seed}"


def test_one_version_of_a_song_at_a_time(lib, monkeypatch):
    """The advisor's 2 at v0.5.0's gate: while a version of a song (seed above 0) waits or charts, "Chart it
    differently" on any of its charts is refused (409) in plain words, using no seed; a plain chart of the song in the
    list is no version and does not stop it; once the version is charted, the next press gives the next version
    (breaks: no refusal, as two presses 150 ms apart queued two versions; the rule on the upload alone; a seed used
    by the refusal; a version whose chart is out still refused)."""
    gate, linger = held_charts(lib, monkeypatch)
    assert post(lib, "/api/jobs", {"upload": A, "options": {}})[0] == 202   # a plain chart of the song, charting
    status, answer = post(lib, by_id(V2, "/again"), {})
    assert status == 202 and (answer["version"], answer["state"]) == (3, "waiting"), answer
    for ref in (V1, V2):   # from any of the song's charts
        assert post(lib, by_id(ref, "/again"), {}) == (409, {"error": (
            "Version 3 of this song is already in the list: when it is charted, you can chart it differently again.")})
    assert json.loads((lib.home / "state" / "versions.json").read_text()) == {A: 2}
    gate(0).touch()   # the plain chart ends; version 3 charts
    deadline = time.monotonic() + 20
    while not any(e["version"] == 3 and e["state"] == "charting" for e in lib.app.queue.snapshot()["entries"]):
        assert time.monotonic() < deadline, lib.app.queue.snapshot()
        time.sleep(0.05)
    assert post(lib, by_id(V1, "/again"), {}) == (409, {"error": (
        "Version 3 of this song is charting now: when it is charted, you can chart it differently again.")})
    linger(2).touch()
    gate(2).touch()   # version 3's chart is out, its process still exiting: charted, so the next press is taken
    while lib.app.jobs.current.result() is None:
        assert time.monotonic() < deadline + 20 and lib.app.jobs.current.state == "running"
        time.sleep(0.02)
    gate(3).touch()
    status, answer = post(lib, by_id(V1, "/again"), {})
    assert status == 202 and answer["version"] == 4, answer
    wait_idle(lib.app)
    gate(4).touch()
    assert post(lib, by_id(V2, "/again"), {})[1]["version"] == 5
    assert json.loads((lib.home / "state" / "versions.json").read_text()) == {A: 4}
    wait_idle(lib.app)


PAGE5 = PAGE.split("(async () => {")[0] + r"""
(async () => {
  const out = {};
  const base = { artist: "Made-Up Band", readable: true, ok: true, audio: "split", stems: false, look: false,
    upload: "aaaaaaaaaaaaaaaa", guitar: true, lyrics: true, rating: null, spots: 0, name: "First Song" };
  ctx.setCharts([{ ...base, id: V1, folder: "Made-Up Band - First Song", time: 1762596000, version: 1, seed: 0 }]);
  const row = els["charts-list"].children[0];
  const words409 = "Version 3 of this song is already in the list: when it is charted, you can chart it differently again.";
  answers[`POST /api/jobs/${enc(V1)}/again`] = [[409, { error: words409 }]];
  await button(find(row, (x) => x.className === "queue-actions"), "Chart it differently").on.click();
  const panel = find(row, (x) => x.className === "chart-again");
  find(panel, (x) => x.tag === "textarea").value = "zib zab\n";
  button(panel, "Chart it").on.click();
  await settle();
  out.row = { msg: find(row, (x) => x.className === "queue-msg small").textContent,
    lyrics: find(panel, (x) => x.tag === "textarea").value };
  ctx.renderPlayed({ ok: true, folder: "/h/library/aaaaaaaaaaaaaaaa/Made-Up Band - First Song",
    library: { id: V1, version: 1, guitar: true, lyrics: false, rating: null, spots: 0 } });
  await button(els.played, "Chart it differently").on.click();
  await settle();
  out.done = find(els.played, (x) => x.className === "small again-msg").textContent;
  console.log(JSON.stringify(out));
})().catch((e) => { console.error(e); process.exit(1); });
"""


@pytest.mark.skipif(shutil.which("node") is None, reason="needs node")
def test_the_page_says_a_version_is_in_the_list(tmp_path):
    """The advisor's 2 on the page (app.js in node, the page test's stand-in DOM): the 409's words in the row's
    message line, the pasted lyrics kept in the panel (F4), and in the Done screen's line (break: the refusal not
    said, or the panel emptied)."""
    script = tmp_path / "busy.cjs"
    script.write_text(PAGE5, encoding="utf-8")
    app_js = tmp_path / "app.js"
    app_js.write_bytes(S.static_files()["app.js"])
    done = subprocess.run(["node", str(script), str(app_js)], capture_output=True, text=True, timeout=60,
                          env={**os.environ, "TZ": "UTC", "LANG": "en_US.UTF-8"})
    assert done.returncode == 0, done.stderr
    out = json.loads(done.stdout)
    words = "Version 3 of this song is already in the list: when it is charted, you can chart it differently again."
    assert out == {"row": {"msg": words, "lyrics": "zib zab\n"}, "done": words}



# a made-up chart: 120 BPM (384 ticks a second at 192) to tick 4608 (12 s), then 60 BPM (192 a second); a section
# name and lyric events of made-up words that must never reach the zip; Expert guitar: a strummed chord at 4 s, a
# natural HOPO 64 ticks on, a tap, an open sustained 192 ticks at 6 s, one note at 17 s, one at 40 s and 30 at 60 s
NOTES = """[Song]\r\n{\r\n  Name = "Zibzab Song"\r\n  Offset = 0\r\n  Resolution = 192\r\n}\r\n[SyncTrack]\r\n{\r
  0 = TS 4\r\n  0 = B 120000\r\n  4608 = B 60000\r\n}\r\n[Events]\r\n{\r\n  0 = E "section Zibzab Part"\r
  1536 = E "phrase_start"\r\n  1536 = E "lyric Zobble"\r\n}\r\n[ExpertSingle]\r\n{\r\n  1536 = N 0 0\r
  1536 = N 2 0\r\n  1600 = N 1 0\r\n  1792 = N 3 0\r\n  1792 = N 6 0\r\n  2304 = N 7 192\r\n  5568 = N 4 0\r
  9984 = N 0 0\r\n""" + "".join(f"  {13824 + 6 * k} = N {k % 5} 0\r\n" for k in range(30)) + "}\r\n"


def test_the_zip_carries_the_guitar_notes_around_each_spot(lib, tmp_path, monkeypatch):
    """The advisor's 3 at v0.5.0's gate: each spot of the chart rated has `around` in feedback.json: the Expert guitar's
    notes from 10 s before it to 10 s after, as numbers (seconds on the spot's clock, tick, frets, open, strum, HOPO
    or tap, sustain in ticks) read as Clone Hero plays them, with the resolution and the tempo markers there (the one
    in force at its start first); no word of the chart (its section, its lyrics, its name); the nearest AROUND_NOTES a
    spot and AROUND_TOTAL a file, said; a chart that does not read, one with no Expert guitar, and spots of another
    notes.chart than the one there: no notes, and why; notes.chart itself still refused (breaks: no notes; another
    clock; the kinds or the sustain wrong; the tempo in force left out; a word of the chart sent; no cap)."""
    (lib.first / "notes.chart").write_text(NOTES, encoding="utf-8", newline="")
    post(lib, by_id(V1, "/feedback"), {"add": {"at": "0:10", "reasons": ["off_beat"]}})
    post(lib, by_id(V1, "/feedback"), {"add": {"at": "0:40", "reasons": ["great"]}})
    post(lib, by_id(V1, "/feedback"), {"add": {"at": "1:00", "reasons": ["too_many_chords"]}})
    post(lib, by_id(V2, "/feedback"), {"add": {"at": "0:05", "reasons": ["great"]}})   # its notes.chart: no chart

    def zipped(name):
        z = zipfile.ZipFile(diagnostics.bundle(lib.home, tmp_path / name, cache_root=lib.root, report=lambda: {},
                                               clonehero_info=lambda home: {}))
        assert "feedback.json" in z.namelist() and not any(n.endswith(".chart") for n in z.namelist())
        return z.read("feedback.json").decode("utf-8"), {c["chart"]: c for c in json.loads(z.read("feedback.json"))[
            "charts"]}

    text, charts = zipped("d.zip")
    ten, forty, sixty = (x["around"] for x in charts[V1]["spots"])
    assert (ten["from_s"], ten["to_s"], ten["resolution"], ten["left_out"]) == (0.0, 20, 192, 0)
    assert ten["tempos"] == [{"tick": 0, "bpm": 120.0, "s": 0.0}, {"tick": 4608, "bpm": 60.0, "s": 12.0}]
    assert ten["notes"] == [
        {"s": 4.0, "tick": 1536, "frets": [0, 2], "open": False, "kind": "strum", "sustain": 0},
        {"s": 4.167, "tick": 1600, "frets": [1], "open": False, "kind": "hopo", "sustain": 0},
        {"s": 4.667, "tick": 1792, "frets": [3], "open": False, "kind": "tap", "sustain": 0},
        {"s": 6.0, "tick": 2304, "frets": [], "open": True, "kind": "strum", "sustain": 192},
        {"s": 17.0, "tick": 5568, "frets": [4], "open": False, "kind": "strum", "sustain": 0}]
    assert forty["tempos"] == [{"tick": 4608, "bpm": 60.0, "s": 12.0}]   # in force from before the window
    assert [(n["s"], n["tick"]) for n in forty["notes"]] == [(40.0, 9984)]
    assert len(sixty["notes"]) == 30 and sixty["notes"][0] == {"s": 60.0, "tick": 13824, "frets": [0], "open": False,
                                                                "kind": "strum", "sustain": 0}
    assert charts[V2]["spots"][0]["around"] == {"why": "its notes.chart could not be read as a chart (InputError)"}
    for word in ("Zibzab", "Zobble", "lyric", "phrase", "section", "/"):
        assert word not in json.dumps(charts), word
    assert "Zibzab" not in text and "Zobble" not in text
    monkeypatch.setattr(FB, "AROUND_NOTES", 12)   # the cap a spot: the nearest kept
    monkeypatch.setattr(FB, "AROUND_TOTAL", 5 + 1 + 12)
    _, charts = zipped("capped.zip")
    ten, forty, sixty = (x["around"] for x in charts[V1]["spots"])
    assert len(ten["notes"]) == 5 and len(forty["notes"]) == 1
    assert sixty["left_out"] == 18 and sixty["why"] == "at most 12 notes a spot: the nearest kept"
    assert [n["tick"] for n in sixty["notes"]] == [13824 + 6 * k for k in range(12)]   # 1:00 is the first note
    monkeypatch.setattr(FB, "AROUND_TOTAL", 5 + 1 + 4)
    _, charts = zipped("total.zip")
    sixty = charts[V1]["spots"][2]["around"]
    assert (len(sixty["notes"]), sixty["left_out"], sixty["why"]) == (4, 26, "at most 10 notes in this file, reached")
    drums = f"{B}:{DRUMS}"   # a chart with no Expert guitar
    (lib.drums / "notes.chart").write_text(NOTES.split("[ExpertSingle]")[0], encoding="utf-8", newline="")
    post(lib, by_id(drums, "/feedback"), {"add": {"at": "0:05", "reasons": ["great"]}})
    assert zipped("none.zip")[1][drums]["spots"][0]["around"] == {"why": "the chart has no Expert guitar part"}
    (lib.first / "notes.chart").unlink()   # the spots of a notes.chart no longer there
    assert zipped("gone.zip")[1][V1]["spots"][0]["around"] == {
        "why": "these spots were marked on another notes.chart than the one there now"}
    assert diagnostics.refused("notes.chart") == "a chart (notes.chart holds the lyrics)"


def test_a_full_files_notes_stay_under_the_zips_limit(tmp_path):
    """AROUND_TOTAL notes as feedback.json writes them, each spot's window full, stay well under diagnostics' MAX_BYTES
    (break: a cap that lets the file grow past what the zip takes)."""
    note = {"s": 123.456, "tick": 123456, "frets": [0, 2, 4], "open": False, "kind": "strum", "sustain": 1920}
    spot = {"id": "0a0b0c0d", "at": 130, "reasons": ["too_many_chords", "off_beat"], "note": "x" * FB.NOTE_MAX,
            "around": {"from_s": 120, "to_s": 140, "resolution": 192, "tempos": [{"tick": 0, "bpm": 120.0, "s": 0.0}],
                       "notes": [note] * FB.AROUND_NOTES, "left_out": 0}}
    spots = FB.AROUND_TOTAL // FB.AROUND_NOTES
    data = {"charts": [{"chart": f"{A}:{FIRST}", "rating": 3, "spots": [spot] * spots, "now": {"pipeline": PIPELINE}}]}
    size = len(json.dumps(data, indent=1, ensure_ascii=False).encode("utf-8"))
    assert size < diagnostics.MAX_BYTES * 0.6, size
