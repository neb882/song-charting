"""The install's second half (songcharter.runtime): fetch against a local HTTP server (resuming a .part, a dropped
connection, a server that ignores Range, the 50 MB lines, a wrong SHA-256, SONGCHARTER_OFFLINE), the engine-list
check, the zip's extraction, the steps against stand-ins (Node from a local tarball, autochart's archive from a local
server, the models, npm's stamp, the CUDA provider), runtime.json written last, `check`, and the failure line."""
import hashlib
import io
import json
import os
import subprocess
import sys
import tarfile
import threading
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from songcharter import runtime as R

MB = 10 ** 6


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class Server:
    """Serves `files` ({path: bytes}) on 127.0.0.1, with Range; `drop` (path -> bytes) closes the first response
    after that many bytes; `no_range` ignores Range. `requests` records (path, Range header)."""

    def __init__(self):
        self.files, self.drop, self.no_range, self.requests = {}, {}, set(), []
        server = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                server.requests.append((self.path, self.headers.get("Range")))
                data = server.files.get(self.path)
                if data is None:
                    self.send_error(404)
                    return
                start = 0
                rng = self.headers.get("Range")
                if rng and self.path not in server.no_range:
                    start = int(rng.split("=")[1].split("-")[0])
                    if start >= len(data):
                        self.send_error(416)
                        return
                    self.send_response(206)
                    self.send_header("Content-Range", f"bytes {start}-{len(data) - 1}/{len(data)}")
                else:
                    self.send_response(200)
                self.send_header("Content-Length", str(len(data) - start))
                self.end_headers()
                body = data[start:]
                cut = server.drop.pop(self.path, None)
                if cut is not None:
                    self.wfile.write(body[:cut])
                    self.wfile.flush()
                    self.close_connection = True
                    return
                for i in range(0, len(body), 1 << 20):
                    self.wfile.write(body[i:i + (1 << 20)])

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.httpd.server_address[1]}"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()


@pytest.fixture
def server():
    s = Server()
    yield s
    s.httpd.shutdown()


@pytest.fixture(autouse=True)
def online(monkeypatch):
    monkeypatch.delenv("SONGCHARTER_OFFLINE", raising=False)


def fetch(url, dest, digest, size=None, said=None):
    return R.fetch(url, dest, digest, size, say=(said if said is not None else []).append, pause=lambda s: None)


# ------------------------------------------------------------------------------------------------ fetch

def test_fetch_resumes_a_part_file(server, tmp_path):
    data = bytes(range(256)) * 12_000   # about 3 MB
    server.files["/f.bin"] = data
    dest = tmp_path / "f.bin"
    (tmp_path / "f.bin.part").write_bytes(data[:1_000_000])
    said = []
    assert fetch(server.url + "/f.bin", dest, sha(data), len(data), said) == dest
    assert dest.read_bytes() == data and not (tmp_path / "f.bin.part").exists()
    assert server.requests == [("/f.bin", "bytes=1000000-")]
    assert said[0] == "fetch f.bin: resuming at 1 of 3 MB" and said[-1] == "fetch f.bin: done, 3 MB"
    assert fetch(server.url + "/f.bin", dest, sha(data), len(data)) == dest and len(server.requests) == 1   # kept


def test_fetch_resumes_after_a_dropped_connection_and_restarts_without_range(server, tmp_path):
    data = os.urandom(2_500_000)
    server.files["/a"] = server.files["/b"] = data
    server.drop["/a"] = 700_000
    said = []
    fetch(server.url + "/a", tmp_path / "a", sha(data), len(data), said)
    assert (tmp_path / "a").read_bytes() == data
    assert server.requests == [("/a", None), ("/a", "bytes=700000-")]
    assert any("the connection closed at 700000 of 2500000 bytes; trying again" in s for s in said), said
    server.no_range.add("/b")   # a server that ignores Range sends the whole file: the .part starts over
    (tmp_path / "b.part").write_bytes(b"x" * 1000)
    fetch(server.url + "/b", tmp_path / "b", sha(data), len(data))
    assert (tmp_path / "b").read_bytes() == data


def test_fetch_prints_a_line_every_50_mb(server, tmp_path):
    data = bytes(120 * MB)
    server.files["/big"] = data
    said = []
    fetch(server.url + "/big", tmp_path / "big", sha(data), len(data), said)
    assert said[0] == "fetch big: 120 MB" and said[-1] == "fetch big: done, 120 MB"
    progress = said[1:-1]
    assert [s.split(",")[0] for s in progress] == ["fetch big: 50 of 120 MB", "fetch big: 100 of 120 MB"]
    assert all(s.endswith(" MB/s") for s in progress), progress


def test_fetch_refuses_a_wrong_sha256_and_a_404(server, tmp_path):
    server.files["/f"] = b"the real bytes"
    with pytest.raises(R.StepFailed, match="has SHA-256 .* not the pinned 00"):
        fetch(server.url + "/f", tmp_path / "f", "00" * 32)
    assert list(tmp_path.iterdir()) == []   # neither the file nor its .part
    with pytest.raises(R.StepFailed, match="HTTP 404"):
        fetch(server.url + "/missing", tmp_path / "m", None)
    assert len(server.requests) == 2   # a 404 is not asked again
    with pytest.raises(R.StepFailed, match=r"could not download .* \(3 tries\)"):
        fetch("http://127.0.0.1:9/nothing-listens", tmp_path / "n", None)


def test_fetch_refuses_to_download_offline(server, tmp_path, monkeypatch):
    data = b"model"
    server.files["/m"] = data
    monkeypatch.setenv("SONGCHARTER_OFFLINE", "1")
    with pytest.raises(R.StepFailed, match="SONGCHARTER_OFFLINE=1 forbids downloading it"):
        fetch(server.url + "/m", tmp_path / "m", sha(data))
    assert server.requests == []
    (tmp_path / "m").write_bytes(data)   # one already there and right is fine offline
    assert fetch(server.url + "/m", tmp_path / "m", sha(data)) == tmp_path / "m" and server.requests == []


# ------------------------------------------------------------------------------------------------ the engine list

def make_tree(root: Path, files: dict[str, bytes]) -> dict[str, tuple[str, int]]:
    for rel, data in files.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_bytes(data)
    return {rel: (sha(data), len(data)) for rel, data in files.items()}


def listing(entries: dict[str, tuple[str, int]]) -> str:
    return "# autochart <commit>: <sha256>  <size>  <path>\n" + "".join(
        f"{s}  {n}  {rel}\n" for rel, (s, n) in sorted(entries.items()))


def test_the_engine_list_check_refuses_a_changed_a_missing_and_an_extra_file(tmp_path):
    root = tmp_path / "src"
    files = {"engine/bin/autochart-engine.cjs": b"engine", "engine/catalog.json": b"{}", "a name with spaces.md": b"x"}
    expected = make_tree(root, files)
    (tmp_path / "list").write_text(listing(expected), encoding="utf-8")
    assert R.read_list(tmp_path / "list") == expected
    assert R.check_tree(root, expected) == []
    (root / "engine" / "catalog.json").write_bytes(b"[]")            # same size, other bytes
    (root / "a name with spaces.md").write_bytes(b"xy")              # another size
    (root / "engine" / "bin" / "autochart-engine.cjs").unlink()      # missing
    (root / "engine" / "extra.js").write_bytes(b"")                  # extra
    (root / "link").symlink_to(root / "engine")                      # a symlink is extra too
    assert R.check_tree(root, expected) == [
        "missing: engine/bin/autochart-engine.cjs", "changed: engine/catalog.json (another SHA-256)",
        "changed: a name with spaces.md (2 bytes, not 1)", "extra: engine/extra.js", "extra: link"]


def zip_of(files: dict[str, bytes], top: str = "autochart-" + R.AUTOCHART_COMMIT) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr(top + "/", b"")
        for rel, data in files.items():
            z.writestr(f"{top}/{rel}", data)
    return buf.getvalue()


def test_extract_zip_drops_the_top_folder_and_refuses_unsafe_paths(tmp_path):
    (tmp_path / "ok.zip").write_bytes(zip_of({"engine/x.js": b"x", "README.md": b"r"}))
    R.extract_zip(tmp_path / "ok.zip", tmp_path / "out")
    assert (tmp_path / "out" / "engine" / "x.js").read_bytes() == b"x" and (tmp_path / "out" / "README.md").is_file()
    (tmp_path / "bad.zip").write_bytes(zip_of({"../../evil": b"!"}))
    with pytest.raises(R.StepFailed, match="unsafe path"):
        R.extract_zip(tmp_path / "bad.zip", tmp_path / "bad")
    assert not (tmp_path / "evil").exists()


# ------------------------------------------------------------------------------------------------ the steps

@pytest.fixture
def app(tmp_path):
    """An app folder (the release tarball's) with the files the steps copy, and a Setup on the cpu lane whose
    subprocess runs are recorded."""
    a = tmp_path / "app"
    for rel, data in {"tools/scan-chart/scan.cjs": b"scan", "tools/scan-chart/package.json": b"{}",
                      "tools/scan-chart/package-lock.json": b"{\"lock\": 1}",
                      "eval/tools/autochart/ac_headless.cjs": b"driver", "eval/tools/autochart/package.json": b"{}",
                      "eval/tools/autochart/package-lock.json": b"{\"lock\": 2}"}.items():
        (a / rel).parent.mkdir(parents=True, exist_ok=True)
        (a / rel).write_bytes(data)
    return a


def setup_for(tmp_path, app, lane="cpu", runs=None, download=True):
    def run(cmd, **kw):
        runs.append([str(c) for c in cmd])
        if "ci" in cmd:   # npm ci: the folder's node_modules
            nm = Path(kw["cwd"]) / "node_modules"
            for pkg in ("scan-chart", "onnxruntime-node"):
                (nm / pkg).mkdir(parents=True, exist_ok=True)
                (nm / pkg / "package.json").write_text("{}", encoding="utf-8")
        return subprocess.CompletedProcess(cmd, 0, "", "")

    return R.Setup(tmp_path / "home", app, lane, "test", download=download, say=lambda s: None,
                   run=run if runs is not None else subprocess.run)


def node_tarball(version: str) -> bytes:
    """A stand-in for nodejs.org's tarball: bin/node, a script that prints its version, and the npm symlink."""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as t:
        script = f"#!/bin/sh\necho v{version}\n".encode()
        info = tarfile.TarInfo(f"node-v{R.NODE_VERSION}-linux-x64/bin/node")
        info.size, info.mode = len(script), 0o755
        t.addfile(info, io.BytesIO(script))
        link = tarfile.TarInfo(f"node-v{R.NODE_VERSION}-linux-x64/bin/npm")
        link.type, link.linkname = tarfile.SYMTYPE, "../lib/node_modules/npm/bin/npm-cli.js"
        t.addfile(link)
    return buf.getvalue()


def test_step_node_installs_and_verifies(server, tmp_path, app, monkeypatch):
    data = node_tarball(R.NODE_VERSION)
    server.files["/node.tar.gz"] = data
    monkeypatch.setattr(R, "NODE_URL", server.url + "/node.tar.gz")
    monkeypatch.setattr(R, "NODE_SHA256", sha(data))
    monkeypatch.setattr(R, "NODE_SIZE", len(data))
    s = setup_for(tmp_path, app)
    R.step_node(s)
    assert subprocess.run([str(s.node), "--version"], capture_output=True, text=True).stdout.strip() == "v24.19.0"
    assert (s.runtime / "node" / "bin" / "npm").is_symlink() and not (s.runtime / "node.part").exists()
    assert list(s.downloads.iterdir()) == []   # the tarball goes once it is unpacked
    R.step_node(s)   # there and right: no download
    assert len(server.requests) == 1
    data = node_tarball("23.0.0")   # a tarball whose node prints another version is refused
    server.files["/node.tar.gz"] = data
    monkeypatch.setattr(R, "NODE_SHA256", sha(data))
    monkeypatch.setattr(R, "NODE_SIZE", len(data))
    R._rmtree(s.runtime / "node")
    with pytest.raises(R.StepFailed, match="printed 'v23.0.0', not v24.19.0"):
        R.step_node(s)


def test_npm_ci_runs_once_per_lock(tmp_path, app):
    runs = []
    s = setup_for(tmp_path, app, runs=runs)
    R.step_scan_chart(s)
    folder = s.runtime / "scan-chart"
    assert (folder / "scan.cjs").read_bytes() == b"scan" and len(runs) == 1
    assert runs[0][2:] == ["ci", "--omit=dev", "--ignore-scripts", "--no-audit", "--no-fund"]
    R.step_scan_chart(s)
    assert len(runs) == 1   # its stamp says it was done for this lock
    (app / "tools" / "scan-chart" / "package-lock.json").write_bytes(b"{\"lock\": 3}")
    R.step_scan_chart(s)
    assert len(runs) == 2 and (folder / "package-lock.json").read_bytes() == b"{\"lock\": 3}"
    s.download = False   # `check` with a stand-in that would run npm: refused instead
    (folder / R.STAMP).unlink()
    with pytest.raises(R.StepFailed, match="scan-chart's packages is missing"):
        R.step_scan_chart(s)
    assert len(runs) == 2


def test_step_autochart_checks_every_file_of_the_archive(server, tmp_path, app, monkeypatch):
    files = {"engine/bin/autochart-engine.cjs": b"engine", "engine/catalog.json": b"{}"}
    expected = {rel: (sha(d), len(d)) for rel, d in files.items()}
    (app / "packaging" / "autochart").mkdir(parents=True)
    (app / R.ENGINE_LIST).write_text(listing(expected), encoding="utf-8")
    server.files["/ac.zip"] = zip_of({**files, "engine/catalog.json": b"[]"})   # one file changed
    monkeypatch.setenv("SONGCHARTER_AUTOCHART_URL", server.url + "/ac.zip")
    runs = []
    s = setup_for(tmp_path, app, runs=runs)
    with pytest.raises(R.StepFailed, match=r"differs from .*: 1 files, changed: engine/catalog.json"):
        R.step_autochart(s)
    assert not (s.autochart / "src").exists() and runs == []
    server.files["/ac.zip"] = zip_of(files)
    R.step_autochart(s)
    assert R.check_tree(s.autochart / "src", expected) == [] and not (s.autochart / "src.part").exists()
    assert (s.autochart / "ac_headless.cjs").read_bytes() == b"driver" and len(runs) == 1   # npm ci
    assert list(s.downloads.iterdir()) == []
    R.step_autochart(s)
    assert len(server.requests) == 2 and len(runs) == 1   # verified, nothing fetched or run again


def test_the_cuda_provider_by_lane(tmp_path, app, monkeypatch):
    """A GPU lane runs onnxruntime-node's installer when the two libraries are not as pinned, and checks what it
    wrote; the cpu lane removes them (and the installer's third file)."""
    good = {"libonnxruntime_providers_cuda.so": b"cuda", "libonnxruntime_providers_shared.so": b"shared"}
    monkeypatch.setattr(R, "PROVIDER", {"libonnxruntime_providers_cuda.so": (sha(b"cuda"), 4),
                                        "libonnxruntime_providers_shared.so": (sha(b"shared"), None)})
    writes = {"files": good}
    runs = []
    s = setup_for(tmp_path, app, lane="cu132", runs=runs)
    folder = s.autochart / R.ORT_BIN

    def run(cmd, **kw):
        runs.append(cmd)
        folder.mkdir(parents=True, exist_ok=True)
        for name, data in writes["files"].items():
            (folder / name).write_bytes(data)
        (folder / "libonnxruntime_providers_tensorrt.so").write_bytes(b"trt")
        return subprocess.CompletedProcess(cmd, 0)

    s.run = run
    R.step_provider(s)
    assert runs[0][1:] == [R.ORT_INSTALL, "--onnxruntime-node-install=cuda12"] and R.provider_ok(s)
    R.step_provider(s)
    assert len(runs) == 1
    (folder / "libonnxruntime_providers_cuda.so").write_bytes(b"CUDA")
    writes["files"] = {**good, "libonnxruntime_providers_cuda.so": b"CUDA"}
    with pytest.raises(R.StepFailed, match="the CUDA provider's libonnxruntime_providers_cuda.so from NuGet is"):
        R.step_provider(s)
    s.lane = "cpu"
    R.step_provider(s)
    assert sorted(p.name for p in folder.iterdir()) == []


def test_step_models(server, tmp_path, app, monkeypatch):
    """Each remote file from the hub by its size and SHA-256, each bundled licence copied from the engine; a rerun
    downloads nothing."""
    weights, licence = os.urandom(3000), b"CC BY-NC-SA 4.0"
    s = setup_for(tmp_path, app)
    engine = s.autochart / "src" / "engine"
    (engine / "licenses").mkdir(parents=True)
    (engine / "licenses" / "l.txt").write_bytes(licence)
    catalog = {"components": [{"id": "other", "files": []}, {"id": R.MODELS_COMPONENT, "files": [
        {"path": "fretformer-v2/manifest.json", "size": 2, "sha256": sha(b"{}"), "source": "remote"},
        {"path": "fretformer-v2/encoder.onnx", "size": len(weights), "sha256": sha(weights), "source": "remote"},
        {"path": "licenses/l.txt", "size": len(licence), "sha256": sha(licence), "source": "bundled-license"}]}]}
    (engine / "catalog.json").write_text(json.dumps(catalog), encoding="utf-8")
    server.files.update({"/fretformer-v2/manifest.json": b"{}", "/fretformer-v2/encoder.onnx": weights})
    monkeypatch.setattr(R, "MODELS_URL", server.url)
    R.step_models(s)
    models = s.autochart / "models"
    assert (models / "fretformer-v2" / "encoder.onnx").read_bytes() == weights
    assert (models / "licenses" / "l.txt").read_bytes() == licence
    R.step_models(s)
    assert len(server.requests) == 2
    (models / "fretformer-v2" / "encoder.onnx").write_bytes(b"broken")
    s.download = False
    with pytest.raises(R.StepFailed, match="fretformer-v2/encoder.onnx is missing or not as pinned"):
        R.step_models(s)


# ------------------------------------------------------------------------------------------------ runtime.json

def test_runtime_json_is_written_last(tmp_path, app, monkeypatch):
    """Every step runs before runtime.json is written; a step that fails leaves the old runtime.json as it was and
    names itself; then doctor runs."""
    s = setup_for(tmp_path, app)
    path = R.runtime_file(s.home)
    path.parent.mkdir(parents=True)
    path.write_text('{"old": true}', encoding="utf-8")
    seen = []

    def step(name, fail=False):
        def fn(s):
            seen.append((name, path.read_text(encoding="utf-8")))
            if fail:
                raise R.StepFailed("no network")
        return name, fn

    monkeypatch.setattr(R, "doctor", lambda home, say: seen.append(("doctor", path.read_text(encoding="utf-8"))) or 1)
    with pytest.raises(R.StepFailed) as e:
        R.setup(s, [step("node"), step("autochart", fail=True), step("models")])
    assert e.value.step == "autochart" and [n for n, _ in seen] == ["node", "autochart"]
    assert path.read_text(encoding="utf-8") == '{"old": true}'
    seen.clear()
    assert R.setup(s, [step("node"), step("models")]) == 1   # doctor's answer
    assert [n for n, _ in seen] == ["node", "models", "doctor"]
    assert all(text == '{"old": true}' for n, text in seen[:2]) and seen[2][1] != '{"old": true}'
    r = json.loads(path.read_text(encoding="utf-8"))
    assert list(r["steps"]) == ["node", "models"] and r["models_complete"] is True and r["lane"] == "cpu"
    assert r["allin1_python"] is None and r["node"] == str(s.runtime / "node" / "bin" / "node")
    assert r["python"] == sys.executable and r["hf_home"].endswith("songcharter/models/hf")


def test_set_allin1(tmp_path):
    home = tmp_path
    (home / "runtime" / "allin1" / "bin").mkdir(parents=True)
    python = home / "runtime" / "allin1" / "bin" / "python"
    python.write_text("", encoding="utf-8")
    R._write_json(R.runtime_file(home), {"allin1_python": str(python), "lane": "cpu"})
    assert R.set_allin1(home, False) is True and R.set_allin1(home, False) is False
    assert json.loads(R.runtime_file(home).read_text(encoding="utf-8")) == {"allin1_python": None, "lane": "cpu"}
    assert R.set_allin1(home, True) is True
    assert json.loads(R.runtime_file(home).read_text(encoding="utf-8"))["allin1_python"] == str(python)


def test_check_says_each_step_and_the_failure_line(tmp_path, app, capsys):
    said = []
    assert R.check(tmp_path / "home", said.append) == 2 and "runtime.json is missing" in said[0]
    (tmp_path / "home" / "runtime").mkdir(parents=True)
    R._write_json(R.runtime_file(tmp_path / "home"), {"app": str(app), "lane": "cpu", "lane_reason": "x"})

    def bad(s):
        assert s.download is False
        raise R.StepFailed("models/x is missing or not as pinned")

    said.clear()
    assert R.check(tmp_path / "home", said.append, [("node", lambda s: None), ("models", bad)]) == 2
    assert said == ["node: ok", "models: FAILED: models/x is missing or not as pinned",
                    "check: 1 step failed: run the install line again"]
    # setup refuses with no lane (uv sync with none installs PyPI's CUDA torch: install.sh refuses too)
    assert R.main(["setup", "--home", str(tmp_path / "h"), "--app", str(app), "--lane", ""]) == 2
    assert capsys.readouterr().err == ("songcharter: setup failed: no torch lane is chosen (''): it is one of cpu, "
                                       "cu126, cu132. Run the same command again to continue.\n")
