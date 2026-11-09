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
                                "device": "auto", "takes": 4, "seed": 2}
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
    """The last seed asked for is kept (state/versions.json): with version 2 deleted in Windows after version 3 was
    asked for, the next is version 4, never version 2's seed again (break: the next seed from the library alone)."""
    assert post(lib, by_id(V1, "/again"), {})[1]["seed"] == 2
    wait_idle(lib.app)
    shutil.rmtree(lib.home / "library" / A / "v2")
    shutil.rmtree(lib.home / "library" / A / "v3")
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
const node = (tag) => ({ tag, hidden: false, textContent: "", className: "", disabled: false, children: [], value: "",
  open: false, checked: false, on: {}, href: "", title: "", replaceChildren(...c) { this.children = c; },
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
  const rows = els["charts-list"].children;
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
