"""M8-13, "Your charts": every chart in the library on the page (jobs.library, GET /api/library, the routes by a
chart's id, the page's list). Made-up names only."""
import http.client
import json
import os
import shutil
import subprocess
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


PAGE = r"""
const vm = require("vm"), fs = require("fs");
const els = new Proxy({}, { get: (t, k) => t[k] || (t[k] = node(k)) });
const node = (tag) => ({ tag, hidden: false, textContent: "", className: "", disabled: false, children: [], value: "",
  open: false, on: {}, href: "", download: null, replaceChildren(...c) { this.children = c; },
  append(...c) { this.children.push(...c); }, remove() {}, addEventListener(kind, f) { this.on[kind] = f; },
  classList: { add() {}, remove() {}, toggle() {} }, removeAttribute() {}, pause() {}, click() { clicked.push(this.href); },
  scrollIntoView() { scrolled.push(this.tag); } });
const document = { getElementById: (id) => els[id] || (els[id] = node(id)), createElement: node, title: "songcharter",
  visibilityState: "visible", addEventListener() {}, body: node("body") };
const clicked = [], scrolled = [], asked = [], confirms = [];
let installs = [];   // the answers to the next installs
const charts = [
  { id: "bbbbbbbbbbbbbbbb:Other Made-Up Band - Second Song.failed", folder: "Other Made-Up Band - Second Song.failed",
    name: "Second Song", artist: "Other Made-Up Band", time: 1762682400, readable: true, ok: false, audio: "one",
    stems: false, look: false },
  { id: "cccccccccccccccc:Made-Up Band - Damaged", folder: "Made-Up Band - Damaged", name: "Made-Up Band - Damaged",
    artist: null, time: 1762596000, readable: false, ok: false, audio: "one", stems: false, look: false },
  { id: "aaaaaaaaaaaaaaaa:Made-Up Band - First Song", folder: "Made-Up Band - First Song", name: "First Song",
    artist: "Made-Up Band", time: 1762509600, readable: true, ok: true, audio: "split", stems: true, look: true },
];
const answer = (status, value) => ({ status, json: async () => JSON.parse(JSON.stringify(value)) });
const ctx = { document, window: { addEventListener() {}, confirm: (m) => { confirms.push(m); return true; } },
  encodeURIComponent, console, setInterval() {}, clearInterval() {}, setTimeout(f) { setImmediate(f); },
  sessionStorage: { setItem() {}, getItem() { return null; } }, Date,
  fetch: async (path, init) => {
    const body = init && init.body ? JSON.parse(init.body) : null;
    asked.push([init.method, path, body]);
    if (path === "/api/library") return answer(200, { charts });
    if (path.endsWith("/install")) return answer(...installs.shift());
    if (path === "/api/open") return answer(200, { opened: false, path: "/h/x", windows_path: "C:\\made\\up" });
    if (path.endsWith("/export/stems")) return answer(200, { url: "/api/exports/F%20(stems).zip", name: "F (stems).zip" });
    if (path.endsWith("/results")) return answer(200, { job: charts[2].id, installable: false, preview: { why: "x" },
      art: null, lyrics: null, listen: null, folder: "/h/library/a/Made-Up Band - First Song", stems: null });
    if (path.startsWith("/api/jobs/")) return answer(200, { job: charts[2].id, state: "done", library: true,
      events: [{ event: "result", ok: true, folder: "/h/library/a/Made-Up Band - First Song", summary: null }] });
    return answer(404, {});
  } };
vm.createContext(ctx);
vm.runInContext(fs.readFileSync(process.argv[2], "utf8"), ctx);
const flat = (n) => typeof n === "string" ? n : [n.textContent, ...(n.children || []).map(flat)].join(" ");
const row = (li) => ({ cls: li.className, text: li.children.filter((c) => typeof c === "string" || !c.className.startsWith("queue-")
  || c.className === "queue-name" || c.className === "queue-state").map(flat).join(" ").replace(/\s+/g, " ").trim(),
  buttons: li.children.find((c) => c.className === "queue-actions").children.map((b) => b.textContent) });
const button = (li, label) => li.children.find((c) => c.className === "queue-actions").children
  .find((b) => b.textContent === label);
const msgOf = (li) => li.children.find((c) => c.className === "queue-msg small");
const settle = () => new Promise((ok) => setImmediate(ok));
(async () => {
  const out = {};
  els["options-screen"].hidden = true;
  await ctx.refreshCharts();
  const rows = els["charts-list"].children;
  out.list = { title: els["charts-title"].textContent, open: els["charts-fold"].open, box: els["charts-box"].hidden,
    lost: els["charts-lost"].hidden, done: [els["to-charts"].hidden, els["to-charts"].textContent],
    queue: [els["queue-charts"].hidden, els["queue-charts"].textContent], rows: rows.map(row) };
  ctx.show("options-screen");
  out.form = els["charts-box"].hidden;
  ctx.show("drop-screen");
  out.start = els["charts-box"].hidden;
  installs = [[409, { error: "x", exists: true, ours: true }], [200, { installed: "/s" }]];
  button(rows[2], "Install").on.click();
  for (let i = 0; i < 6; i++) await settle();
  out.install = { confirms: confirms.slice(), msg: msgOf(rows[2]).textContent };
  installs = [[403, { blocked: true, zip_url: "/api/exports/F.zip" }]];
  await ctx.installFrom({ job: charts[2].id, chart: "First Song", look: false }, msgOf(rows[1]));
  out.blocked = { text: msgOf(rows[1]).textContent, link: msgOf(rows[1]).children.map((a) => [a.textContent, a.href]) };
  installs = [[400, { error: "no Clone Hero Songs folder is known: give it first" }]];
  await ctx.installFrom({ job: charts[2].id, chart: "First Song", look: false }, msgOf(rows[1]));
  out.nosongs = msgOf(rows[1]).textContent;
  await button(rows[0], "Open").on.click();
  out.open = msgOf(rows[0]).textContent;
  await button(rows[2], "Download the stems").on.click();
  out.stems = msgOf(rows[2]).textContent;
  await button(rows[2], "Look").on.click();
  for (let i = 0; i < 6; i++) await settle();
  out.look = { title: els["done-title"].textContent, shown: vm.runInContext("state.shown", ctx) };
  out.asked = asked.filter((a) => a[0] === "POST" || a[1].startsWith("/api/jobs/"));
  out.clicked = clicked;
  els["charts-fold"].open = false;
  ctx.toCharts();
  out.to = { open: els["charts-fold"].open, scrolled };
  vm.runInContext("state.charts = null; state.chartsKey = null", ctx);
  ctx.setCharts(Array.from({ length: 7 }, (_, i) => ({ ...charts[2], id: `${charts[2].id} ${i}` })));
  out.long = { open: els["charts-fold"].open, title: els["charts-title"].textContent };
  els["charts-fold"].open = true;   // his own: kept when the list is read again
  ctx.setCharts(Array.from({ length: 8 }, (_, i) => ({ ...charts[2], id: `${charts[2].id} ${i}` })));
  out.kept = els["charts-fold"].open;
  ctx.setCharts([]);
  out.empty = [els["charts-box"].hidden, els["to-charts"].hidden, els["queue-charts"].hidden];
  const reads = () => asked.filter((a) => a[1] === "/api/library").length;
  const before = reads();
  const q = (state) => ({ paused: null, run: 1, left: null, entries: [{ id: "e1", run: 1, name: "s.mp3", chart: null,
    state, job: "j1", estimate: null, error: null }] });
  ctx.setQueue(q("charting"));
  ctx.setQueue(q("charting"));   // no change: not read again
  ctx.setQueue(q("ready"));      // the song ended: its chart is in the library
  await settle();
  out.reads = reads() - before;
  console.log(JSON.stringify(out));
})().catch((e) => { console.error(e); process.exit(1); });
"""


@pytest.mark.skipif(shutil.which("node") is None, reason="needs node")
def test_the_page_lists_your_charts(tmp_path):
    """The page (app.js in node, a stand-in DOM): "Your charts (n)" open while short, folded when long (his own fold
    kept after), hidden over the options and with no chart; each row with its name, artist, verdict, date, audio and
    stems, Install only for a chart that passed, Download the stems only with them, Look only with its work folder,
    and the line that nothing is lost; Install asks before replacing, Open, the stems' zip and Look by the chart's id
    (breaks: a row's button offered without its condition; the fold not folding; the ids not encoded; the 409's
    question lost; Look not offered by id)."""
    files = S.static_files()
    script = tmp_path / "charts.cjs"
    script.write_text(PAGE, encoding="utf-8")
    app_js = tmp_path / "app.js"
    app_js.write_bytes(files["app.js"])
    done = subprocess.run(["node", str(script), str(app_js)], capture_output=True, text=True, timeout=60,
                          env={**os.environ, "TZ": "UTC", "LANG": "en_US.UTF-8"})
    assert done.returncode == 0, done.stderr
    out = json.loads(done.stdout)
    lst = out["list"]
    assert lst["title"] == "Your charts (3)" and lst["open"] is True and lst["box"] is False and lst["lost"] is False
    assert lst["done"] == [False, "Your charts (3)"] and lst["queue"] == [False, "Your charts (3)"]
    second, damaged, first = lst["rows"]
    assert second["cls"] == "check_failed" and second["buttons"] == ["Open"]
    assert second["text"].startswith("Second Song Other Made-Up Band Did not pass its check: kept for a look, not for "
                                     "Clone Hero Nov 9, 2025, 10:00 AM")
    assert second["text"].endswith("· one audio file")
    assert damaged["cls"] == "unreadable" and damaged["buttons"] == ["Open"]
    assert damaged["text"].startswith("Made-Up Band - Damaged Can't be read Nov 8, 2025, 10:00 AM")
    assert "audio" not in damaged["text"]
    assert first["cls"] == "ready" and first["buttons"] == ["Install", "Open", "Download the stems", "Look"]
    assert first["text"].startswith("First Song Made-Up Band Passed its check Nov 7, 2025, 10:00 AM")
    assert first["text"].endswith("· a sound file per instrument · stems saved")
    assert out["form"] is True and out["start"] is False
    assert out["install"] == {"confirms": ["First Song is in Clone Hero already, from an earlier chart. Replace the "
                                           "older chart?"],
                              "msg": "Installed. In Clone Hero, open Settings > General and press Scan Songs."}
    assert out["blocked"]["text"].startswith("Windows did not let songcharter finish writing into the Songs folder: "
                                             "try again in a moment, or save the zip")
    assert out["blocked"]["link"] == [["Save the zip", "/api/exports/F.zip"]]
    assert "Look" not in out["nosongs"] and "Done screen" in out["nosongs"]
    assert out["open"] == "Open it yourself: C:\\made\\up"
    assert out["stems"].startswith("The zip is F (stems).zip")
    assert out["look"] == {"title": "Ready", "shown": "aaaaaaaaaaaaaaaa:Made-Up Band - First Song"}
    enc = "aaaaaaaaaaaaaaaa%3AMade-Up%20Band%20-%20First%20Song"
    assert out["asked"] == [
        ["POST", f"/api/jobs/{enc}/install", {"replace": False}],
        ["POST", f"/api/jobs/{enc}/install", {"replace": True}],
        ["POST", f"/api/jobs/{enc}/install", {"replace": False}],
        ["POST", f"/api/jobs/{enc}/install", {"replace": False}],
        ["POST", "/api/open", {"what": "built", "job": "bbbbbbbbbbbbbbbb:Other Made-Up Band - Second Song.failed"}],
        ["POST", f"/api/jobs/{enc}/export/stems", None],
        ["GET", f"/api/jobs/{enc}", None],
        ["GET", f"/api/jobs/{enc}/results", None]]
    assert out["clicked"] == ["/api/exports/F%20(stems).zip"]
    assert out["to"]["open"] is True and out["to"]["scrolled"][-1] == "charts-box"   # after Look's done-screen
    assert out["long"] == {"open": False, "title": "Your charts (7)"} and out["kept"] is True
    assert out["empty"] == [True, True, True]
    assert out["reads"] == 1   # the song's end; not the first list (start reads it) nor the same list again
    # (break: renderQueue not reading it, or reading it on every refresh)
    html = files["index.html"].decode()
    assert html.index('id="queue-box"') < html.index('id="done-screen"') < html.index('id="charts-box"')
    assert '<summary id="charts-title">Your charts</summary>' in html
    assert "Nothing is deleted from here." in html
