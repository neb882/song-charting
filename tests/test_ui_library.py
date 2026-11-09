"""M8-13, "Your charts": every chart in the library on the page (jobs.library, GET /api/library, the routes by a
chart's id, the page's list). Made-up names only."""
import http.client
import json
import os
import shutil
import urllib.parse
from pathlib import Path
from types import SimpleNamespace

import pytest

from songcharter import cache, package, pipeline, wsl
from songcharter.ui import jobs as J
from songcharter.ui import server as S

DOCTOR = {"device": {"chosen": "cpu", "reason": "no NVIDIA GPU found"}, "gpu": None, "guitar_device": "cpu",
          "guitar_reason": "no GPU", "notes": [], "ok": True, "cpu": {"logical": 4, "threads_default": 3},
          "problems": [], "components": {}}
A, B, C, D = "aaaaaaaaaaaaaaaa", "bbbbbbbbbbbbbbbb", "cccccccccccccccc", "dddddddddddddddd"
FIRST = "Made-Up Band - First Song"
SECOND = "Other Made-Up Band - Second Song.failed"
DAMAGED = "Made-Up Band - Damaged"
OLD = "Made-Up Band - Old Song"
SPLIT = ("song.ogg", "guitar.ogg", "bass.ogg", "drums.ogg")


def chart(home, key, name, when, *, ok=True, files=("song.ogg",), audio_files=None, ini=None, report=None):
    folder = home / "library" / key / name
    folder.mkdir(parents=True)
    for f in files:
        (folder / f).write_bytes(b"OggS" + bytes(16))
    (folder / "notes.chart").write_text("[Song]\n{\n}\n", encoding="utf-8")
    if ini is not None:
        (folder / "song.ini").write_text(ini, encoding="utf-8")
    rec = {"gate": {"ok": ok}, **({"audio_files": list(audio_files)} if audio_files is not None else {})}
    (folder / "report.json").write_text(report if report is not None else json.dumps(rec), encoding="utf-8")
    os.utime(folder / "report.json", (when, when))
    return folder


def work(root, key, made: Path, preview=True):
    """A work folder for the song with this key whose pipeline.json says its last chart is `made`."""
    folder = root / "work" / f"song-{key}"
    folder.mkdir(parents=True)
    cache.mark(folder, Path("song.wav"), key, None)
    if preview:
        (folder / "preview").mkdir()
        (folder / "preview" / "overview.png").write_bytes(b"\x89PNG\r\n\x1a\nmade-up")
    (folder / "pipeline.json").write_text(json.dumps({"assemble": {"folder": str(made), "ok": True},
                                                      "preview": {"ok": preview, "flags": [], "remarks": []}}),
                                          encoding="utf-8")
    return folder


def made_up_library(home: Path, root: Path) -> SimpleNamespace:
    """Four charts (a split one with its stems and its work folder, a failed one-file one with its stems, one whose
    report.json is damaged, an older one whose work folder a later chart of the song took) and four folders that are not charts."""
    first = chart(home, A, FIRST, 1000, files=SPLIT, audio_files=SPLIT,
                  ini="[song]\nname = First Song\nartist = Made-Up Band\ncharter = songcharter\n")
    stems = first.with_name(FIRST + " (stems)")
    stems.mkdir()
    for s in ("drums", "bass", "guitar", "piano", "vocals", "other"):
        (stems / f"{s}.flac").write_bytes(b"fLaC" + s.encode())
    second = chart(home, B, SECOND, 3000, ok=False, audio_files=["song.ogg"],
                   ini="[Song]\nName = Second Song\nArtist = Other Made-Up Band\n")
    failed_stems = home / "library" / B / (SECOND[:-len(".failed")] + " (stems)")   # pipeline.stems_folder(out)
    failed_stems.mkdir()
    (failed_stems / "drums.flac").write_bytes(b"fLaC")
    damaged = chart(home, C, DAMAGED, 2000, report="{not json")
    old = chart(home, D, OLD, 500)   # before M8-12: no audio_files, song.ogg alone
    (home / "library" / C / "No Report").mkdir()   # not a chart: no report.json
    hidden = home / "library" / A / f".{FIRST}.x1y2.partial"   # assemble's staging
    hidden.mkdir()
    (hidden / "report.json").write_text("{}", encoding="utf-8")
    (home / "library" / "not-an-upload" / "Some Song").mkdir(parents=True)
    (home / "library" / "not-an-upload" / "Some Song" / "report.json").write_text("{}", encoding="utf-8")
    work(root, A, first)
    work(root, D, old.with_name(OLD + " (live)"))   # a later chart of the same song, with other options
    return SimpleNamespace(first=first, second=second, damaged=damaged, old=old, stems=stems)


def test_the_library_lists_every_chart_newest_first(tmp_path):
    """jobs.library: the folders holding a report.json, newest first (report.json's time), each with its song.ini's
    name and artist, the verdict, the audio, the stems and Look; a damaged report.json listed as unreadable; not the
    stems folder, a folder without report.json, assemble's staging or a folder outside an upload's 16 hex (breaks:
    the order reversed or by name; the report.json filter or the hidden one dropped; an unreadable one skipped; the
    audio, stems or Look not read; Look offered for a work folder another chart of the song has taken)."""
    home, root = tmp_path / "home", tmp_path / "cache"
    lib = made_up_library(home, root)
    charts = J.library(home, root)
    assert [c["id"] for c in charts] == [f"{B}:{SECOND}", f"{C}:{DAMAGED}", f"{A}:{FIRST}", f"{D}:{OLD}"]
    assert [c["time"] for c in charts] == [3000, 2000, 1000, 500]
    by = {c["folder"]: {k: v for k, v in c.items() if k not in ("id", "time")} for c in charts}
    assert by[FIRST] == {"folder": FIRST, "name": "First Song", "artist": "Made-Up Band", "readable": True, "ok": True,
                         "audio": "split", "stems": True, "look": True}
    assert by[SECOND] == {"folder": SECOND, "name": "Second Song", "artist": "Other Made-Up Band", "readable": True,
                          "ok": False, "audio": "one", "stems": True, "look": False}
    assert by[DAMAGED] == {"folder": DAMAGED, "name": DAMAGED, "artist": None, "readable": False, "ok": False,
                           "audio": "one", "stems": False, "look": False}
    assert by[OLD] == {"folder": OLD, "name": OLD, "artist": None, "readable": True, "ok": True, "audio": "one",
                       "stems": False, "look": False}
    assert J.library(home, None)[2]["look"] is False   # no cache: no Look
    shutil.rmtree(root / "work" / f"song-{A}")   # the cache pruned it: no Look, the chart stays listed
    assert [c["look"] for c in J.library(home, root)] == [False] * 4
    assert [c["stems"] for c in J.library(home, root)] == [True, False, True, False]
    (lib.old / "guitar.ogg").write_bytes(b"OggS")   # an earlier build's split files, by what is there
    assert J.read_chart(lib.old, root)["audio"] == "split"
    assert J.library(tmp_path / "nobody", root) == []


def test_the_librarys_names_are_the_pipelines():
    """The library's suffixes and split files are the pipeline's own (jobs.py does not import it: the child's)."""
    assert J.STEMS_SUFFIX == pipeline.STEMS_SUFFIX
    assert J.SPLIT_FILES == tuple(f"{p}.ogg" for p in package.SPLIT_PARTS)
    assert pipeline.failed_folder(Path("x/Song")).name == "Song" + J.FAILED


def test_a_chart_is_found_by_its_id_among_the_librarys_folders_only(tmp_path):
    """find_chart: the id names a folder the library holds; anything else (a path, a climb, the stems folder, a
    folder without report.json, staging, an unknown upload, not text) is None (break: the id joined into a path)."""
    home, root = tmp_path / "home", tmp_path / "cache"
    lib = made_up_library(home, root)
    assert J.find_chart(home, f"{A}:{FIRST}") == lib.first
    assert J.find_chart(home, f"{B}:{SECOND}") == lib.second
    for bad in (str(lib.first), f"{A}:../{B}/{SECOND}", f"{A}:{FIRST} (stems)", f"{C}:No Report",
                f"{A}:.{FIRST}.x1y2.partial", f"{'e' * 16}:{FIRST}", f"{A}/{FIRST}", f"{A}:", None, 7,
                f"{A.upper()}:{FIRST}"):
        assert J.find_chart(home, bad) is None, bad


@pytest.fixture
def library_server(tmp_path, monkeypatch):
    """A server on a made-up library (not in WSL), with a Songs folder; its jobs never run."""
    monkeypatch.setattr(wsl, "is_wsl", lambda: False)
    home, root = tmp_path / "home", tmp_path / "cache"
    lib = made_up_library(home, root)
    (home / "doctor.json").write_text(json.dumps(DOCTOR), encoding="utf-8")
    jobs = J.Jobs(home, command=lambda *a: pytest.fail("no chart runs here"))
    app = S.App(home, jobs=jobs, log=S.Log(None, console=lambda t: None), report=lambda: DOCTOR, cache_root=root)
    servers = S.bind(app, [0])
    songs = tmp_path / "Songs"
    songs.mkdir()
    ctx = SimpleNamespace(app=app, port=servers[0].server_address[1], home=home, lib=lib, songs=songs)
    assert post(ctx, "/api/clonehero", {"folder": str(songs)})[0] == 200
    yield ctx
    jobs.shutdown()
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


def get(ctx, path):
    status, headers, body = call(ctx.port, "GET", path)
    return status, headers, body


def by_id(chart_id: str, rest: str = "") -> str:
    return f"/api/jobs/{urllib.parse.quote(chart_id, safe='')}{rest}"


def test_the_list_install_and_its_409_by_a_charts_id(library_server):
    """GET /api/library lists the charts; Install by a chart's id puts it into the Songs folder, a second asks to
    replace (409, ours), the replace goes through; a failed one, an unknown id and a path are refused (breaks: the
    route not given the library's ids; the 409 lost; a failed chart installed)."""
    ctx = library_server
    status, _, body = get(ctx, "/api/library")
    charts = json.loads(body)["charts"]
    assert status == 200 and [c["folder"] for c in charts] == [SECOND, DAMAGED, FIRST, OLD]
    first = f"{A}:{FIRST}"
    status, answer = post(ctx, by_id(first, "/install"), {"replace": False})
    assert status == 200 and answer["installed"] == str(ctx.songs / FIRST), answer
    assert (ctx.songs / FIRST / "report.json").is_file()
    status, answer = post(ctx, by_id(first, "/install"), {"replace": False})
    assert status == 409 and answer["exists"] is True and answer["ours"] is True, answer
    status, answer = post(ctx, by_id(first, "/install"), {"replace": True})
    assert status == 200 and answer["replaced"], answer
    status, answer = post(ctx, by_id(f"{B}:{SECOND}", "/install"), {"replace": False})
    assert status == 400 and "did not pass its check" in answer["error"]
    assert post(ctx, by_id(f"{C}:{DAMAGED}", "/install"), {"replace": False})[0] == 400   # can't be read: no Install
    for bad in (f"{'e' * 16}:{FIRST}", f"{A}:{FIRST} (stems)"):
        assert post(ctx, by_id(bad, "/install"), {"replace": False}) == (400, {"error": "no finished chart yet"}), bad
    for path in (f"/api/jobs/{A}/{urllib.parse.quote(FIRST)}/install", f"/api/jobs/{A}%2F..%2F{B}/install",
                 "/api/jobs/" + urllib.parse.quote(str(ctx.lib.first), safe="") + "/install"):
        assert post(ctx, path, {"replace": False})[0] == 404, path
    assert sorted(p.name for p in ctx.songs.iterdir() if not p.name.startswith(".")) == [FIRST]
    assert ctx.lib.first.is_dir() and ctx.lib.second.is_dir()   # nothing deleted from the library


def test_open_by_a_charts_id_and_never_a_path(library_server, monkeypatch):
    """POST /api/open {"what": "built", "job": <a chart's id>} opens that folder, a failed one too; a path, a climb
    or an unknown id is refused, and nothing is opened (breaks: the id not looked up; a path or junk falling back)."""
    ctx = library_server
    opened = []
    monkeypatch.setattr(wsl, "open_url", lambda url: opened.append(url) or True)
    status, answer = post(ctx, "/api/open", {"what": "built", "job": f"{A}:{FIRST}"})
    assert status == 200 and answer["path"] == str(ctx.lib.first)
    status, answer = post(ctx, "/api/open", {"what": "built", "job": f"{B}:{SECOND}"})
    assert status == 200 and answer["path"] == str(ctx.lib.second)
    for bad in (str(ctx.lib.first), f"{A}:../{B}/{SECOND}", "../x", ["x"]):
        assert post(ctx, "/api/open", {"what": "built", "job": bad}) == (
            400, {"error": "job is a chart's id: no such chart"}), bad
    for unknown in (f"{'e' * 16}:{FIRST}", f"{C}:No Report", "20000101-000000"):
        assert post(ctx, "/api/open", {"what": "built", "job": unknown}) == (
            400, {"error": "no finished chart yet"}), unknown


def test_the_stems_and_look_by_a_charts_id(library_server):
    """Download the stems by a chart's id (its " (stems)" folder beside it), none without; Look: the chart's snapshot
    with its result, its results with the preview while its work folder is in the cache (URLs by its id), and none
    for one whose work folder is gone or another chart's (breaks: the stems not found beside the folder; the preview
    of a chart without its own work folder; the results' URLs not naming the chart)."""
    ctx = library_server
    first = f"{A}:{FIRST}"
    status, answer = post(ctx, by_id(first, "/export/stems"))
    assert status == 200 and answer["name"] == FIRST + " (stems).zip", answer
    status, headers, body = get(ctx, answer["url"])
    assert status == 200 and body[:2] == b"PK"
    assert post(ctx, by_id(f"{D}:{OLD}", "/export/stems")) == (400, {"error": "this chart was made without the stems"})
    status, answer = post(ctx, by_id(f"{B}:{SECOND}", "/export/stems"))   # a failed gate's too, as M8-12's
    assert status == 200 and answer["name"] == "Other Made-Up Band - Second Song (stems).zip", answer
    status, _, body = get(ctx, by_id(first))
    snap = json.loads(body)
    assert status == 200 and snap["job"] == first and snap["library"] is True
    assert snap["events"] == [{"event": "result", "ok": True, "exit": 0, "folder": str(ctx.lib.first),
                               "work": str(ctx.home.parent / "cache" / "work" / f"song-{A}"),
                               "preview": str(ctx.home.parent / "cache" / "work" / f"song-{A}" / "preview"),
                               "stems": str(ctx.lib.stems), "summary": None}]
    status, _, body = get(ctx, by_id(first, "/results"))
    res = json.loads(body)
    assert status == 200 and res["job"] == first and res["installable"] and res["name"] == FIRST
    assert res["preview"]["overview"] == by_id(first, "/preview/overview.png")
    status, headers, body = get(ctx, res["preview"]["overview"])
    assert status == 200 and body.endswith(b"made-up")
    assert res["stems"]["name"] == FIRST + " (stems)" and len(res["stems"]["files"]) == 6
    old = f"{D}:{OLD}"
    res = json.loads(get(ctx, by_id(old, "/results"))[2])
    assert res["job"] == old and res["preview"] == {"why": "the run left no record of it"} and res["installable"]
    assert json.loads(get(ctx, by_id(old))[2])["events"][0]["work"] is None
    assert post(ctx, by_id(old, "/listen"), {"part": "guitar", "level": "expert"}) == (
        400, {"error": "no finished chart yet"})
    assert get(ctx, by_id(old, "/preview/overview.png"))[0] == 404
    assert get(ctx, by_id(f"{'e' * 16}:{OLD}"))[0] == 404


def test_your_charts_routes_are_guarded(library_server, monkeypatch):
    """GET /api/library answers only as 127.0.0.1 or localhost; every POST by a chart's id needs the page's header and
    origin, as /api/jobs does (break: a route by id outside _handle's guards)."""
    ctx = library_server
    opened = []
    monkeypatch.setattr(wsl, "open_url", lambda url: opened.append(url) or True)
    assert call(ctx.port, "GET", "/api/library", host=f"evil.example:{ctx.port}")[0] == 403
    assert call(ctx.port, "GET", by_id(f"{A}:{FIRST}", "/results"), host=f"evil.example:{ctx.port}")[0] == 403
    first = f"{A}:{FIRST}"
    for headers in ({}, {"X-Songcharter": "1"}, {"Origin": f"http://127.0.0.1:{ctx.port}"},
                    {"X-Songcharter": "1", "Origin": "http://evil.example"}):
        for path, value in ((by_id(first, "/install"), {"replace": True}), (by_id(first, "/export/stems"), None),
                            (by_id(first, "/export/zip"), None), ("/api/open", {"what": "built", "job": first}),
                            (by_id(first, "/listen"), {"part": "guitar", "level": "expert"})):
            assert post(ctx, path, value, headers=headers)[0] == 403, (path, headers)
    assert opened == [] and not list(ctx.songs.iterdir()) and not (ctx.home / "exports").exists()
