"""songcharter.diagnostics and `songcharter diagnostics`: the bundle holds the settings, the newest logs and the newest
work folders' reports, and never audio (by name or by its first bytes), a chart, a picture, a stem or a file over
5 MB; nor a word of lyrics a person pasted. packaging/ci/check_no_audio.py passes on it unpacked."""
import importlib.util
import json
import os
import subprocess
import sys
import time
import zipfile
from pathlib import Path

import pytest

from songcharter import cache, cli
from songcharter import diagnostics as D
from songcharter.pipeline import Options, chart

ROOT = Path(__file__).resolve().parents[1]
CHECK = ROOT / "packaging" / "ci" / "check_no_audio.py"
WAV_HEAD = b"RIFF\x24\x00\x00\x00WAVEfmt "
DOCUMENTS = {"registry": "%USERPROFILE%\\Documents", "windows": "C:\\Users\\J\u251c\u2562rg\\Documents",   # mojibake
             "linux": None}


def check_no_audio():
    spec = importlib.util.spec_from_file_location("check_no_audio", CHECK)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write(path: Path, data: bytes | str, age: float = 0.0) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data.encode("utf-8") if isinstance(data, str) else data)
    if age:
        t = time.time() - age
        os.utime(path, (t, t))
    return path


def work_folder(root: Path, name: str, used: float, built: Path) -> Path:
    """A work folder as a chart leaves it: the reports, and the audio, stems and previews never to be bundled."""
    w = root / "work" / f"{name}-{'0' * 16}"
    write(w / cache.MARKER, json.dumps({"songcharter": "0.1.0", "used": used, "input": "/x/song.mp3"}))
    write(w / "pipeline.json", json.dumps({"assemble": {"folder": str(built), "ok": True},
                                           "preview": {"ok": True, "flags": ["guitar: gap 0:12.0-0:16.0 (2 measures)"],
                                                       "flags_by_kind": {"gap": 1}, "remarks": [],
                                                       "traceback": "not this"},
                                           "fallbacks": [{"stage": "separate", "to": "cpu"}]}))
    write(w / "assemble.json", json.dumps({"output": str(built)}))
    write(w / "decode.wav", WAV_HEAD + b"\0" * 64)
    write(w / "stems" / "abc" / "vocals.wav", WAV_HEAD + b"\0" * 64)
    write(w / "preview" / "overview.png", b"\x89PNG\r\n\x1a\n")
    write(built / "report.json", json.dumps({"gate": {"ok": True}, "name": name}))
    write(built / "notes.chart", '[Events]\r\n{\r\n  0 = E "lyric zorp"\r\n}\r\n')
    write(built / "song.ogg", b"OggS" + b"\0" * 64)
    return w


@pytest.fixture
def home(tmp_path):
    """A home and a cache with everything the bundle may and may not take."""
    h = tmp_path / "home"
    write(h / "doctor.json", json.dumps({"ok": True, "wsl": {"documents": DOCUMENTS}}))
    write(h / "runtime" / "runtime.json", json.dumps({"lane": "cpu"}))
    write(h / "ui.json", json.dumps({"clone_hero_songs": "/mnt/c/Songs"}))
    write(h / "logs" / "renamed.log", WAV_HEAD + b"\0" * 64, age=50)         # a WAV with a log's name: the newest
    write(h / "logs" / "big.log", b"x" * (6 * 10 ** 6), age=60)              # 6 MB
    for i in range(9):                                        # job-00 is the third newest, job-08 the 11th
        write(h / "logs" / f"job-{i:02d}.log", f"log {i}\n", age=100 + i * 10)
    write(h / "logs" / "oldest.log", "too old\n", age=10_000)                # the 12th
    write(h / "logs" / "shot.png", b"\x89PNG\r\n\x1a\n")
    write(h / "logs" / "song.ogg", b"OggS")
    write(h / "uploads" / ("0" * 16) / "song.wav", WAV_HEAD)
    root = tmp_path / "cache"
    for i in range(6):                                        # w5 is the newest; w0 is the sixth, left out
        work_folder(root, f"w{i}", 1_000 + i, h / "library" / str(i) / f"Song {i}")
    return h, root


def bundle(h, root, tmp_path, **kw) -> zipfile.ZipFile:
    kw.setdefault("report", lambda: {"ok": True, "now": True})
    kw.setdefault("clonehero_info", lambda home: {"folder": "/mnt/c/Songs", "windows_path": "C:\\Songs",
                                                  "source": "saved", "under_onedrive": False, "guess": None})
    out = D.bundle(h, tmp_path / "out" / "d.zip", cache_root=root, **kw)
    assert out == tmp_path / "out" / "d.zip" and [p.name for p in out.parent.iterdir()] == ["d.zip"]
    return zipfile.ZipFile(out)


def test_the_bundle_holds_the_reports_and_never_audio(home, tmp_path):
    h, root = home
    z = bundle(h, root, tmp_path)
    names = sorted(z.namelist())
    logs = sorted(f"logs/job-{i:02d}.log" for i in range(8))   # with renamed.log and big.log, the newest 10
    works = [f"work/w{i}-{'0' * 16}/{f}" for i in range(1, 6)
             for f in ("assemble.json", "pipeline.json", "preview.json", "report.json", cache.MARKER)]
    assert names == sorted(["MANIFEST.txt", "clonehero.json", "doctor-now.json", "doctor.json", "runtime/runtime.json",
                            "ui.json", *logs, *works])
    for name in names:
        data = z.read(name)
        assert len(data) <= D.MAX_BYTES and not data.startswith((b"RIFF", b"OggS", b"\x89PNG"))
        assert b"lyric" not in data, name   # no chart
    assert json.loads(z.read("doctor-now.json")) == {"ok": True, "now": True}
    ch = json.loads(z.read("clonehero.json"))
    assert ch == {"folder": "/mnt/c/Songs", "windows_path": "C:\\Songs", "source": "saved", "under_onedrive": False,
                  "documents": DOCUMENTS}
    assert json.loads(z.read(f"work/w5-{'0' * 16}/preview.json")) == {
        "ok": True, "flags": ["guitar: gap 0:12.0-0:16.0 (2 measures)"], "flags_by_kind": {"gap": 1}, "remarks": []}
    assert json.loads(z.read(f"work/w5-{'0' * 16}/report.json"))["name"] == "w5"
    manifest = z.read("MANIFEST.txt").decode("utf-8")
    assert f"home: {h}" in manifest and f"cache: {root}" in manifest
    assert f"{h / 'logs' / 'renamed.log'}: audio: it starts with a RIFF header (WAV)" in manifest
    assert f"{h / 'logs' / 'big.log'}: 6000000 bytes, over 5000000" in manifest
    listed = manifest.split("\nNever in this file")[0]
    for never in ("job-08.log", "oldest.log", "shot.png", "song.ogg", "w0-", "uploads", "notes.chart", "stems"):
        assert never not in listed, never   # never picked, so never even looked at
    # check_no_audio.py on it, unpacked and as the zip it is
    unpacked = tmp_path / "unpacked"
    z.extractall(unpacked)
    for target in (unpacked, tmp_path / "out" / "d.zip"):
        run = subprocess.run([sys.executable, str(CHECK), str(target)], capture_output=True, text=True)
        assert run.returncode == 0, run.stdout + run.stderr


def test_never_by_name_size_or_first_bytes():
    for name in ("a.WAV", "b.ogg", "c.flac", "d.mp3", "e.m4a", "f.opus", "g.aac", "h.wma", "i.aif", "j.aiff",
                 "notes.chart", "Notes.Chart", "x.chart", "y.mid", "overview.png"):
        assert D.refused(name) is not None, name
    assert D.refused("x.log", size=D.MAX_BYTES + 1) and D.refused("x.log", size=D.MAX_BYTES) is None
    for head in (WAV_HEAD, b"OggS", b"ID3\x04", b"fLaC", b"\x1a\x45\xdf\xa3", b"FORM\0\0\0\0AIFF",
                 b"\0\0\0\x20ftypM4A ", b"\xff\xfb\x90", b"\xff\xfe{\0"):
        assert D.refused("x.json", head) is not None, head
    assert D.refused("x.json", b'{"ok": true}') is None and D.refused("x.log", b"") is None


def test_the_audio_test_is_check_no_audios():
    ci = check_no_audio()
    assert D.AUDIO_EXTENSIONS == ci.AUDIO_EXTENSIONS and D.MAGIC == ci.MAGIC
    for head in (WAV_HEAD, b"OggS", b"FORM\0\0\0\0AIFC", b"\0\0\0\x18ftypisom", b"\xff\xf1", b"\xff\xfe", b"{}",
                 b"\xff\x00", b"PK\x03\x04"):
        assert (D.magic_reason(head) is None) == (ci.magic_reason(head) is None), head


def test_a_failing_report_and_an_empty_home(tmp_path):
    z = bundle(tmp_path / "nothing", tmp_path / "no-cache", tmp_path, report=lambda: 1 / 0,
               clonehero_info=lambda home: {"folder": None})
    assert sorted(z.namelist()) == ["MANIFEST.txt", "clonehero.json", "doctor-now.json"]
    assert json.loads(z.read("doctor-now.json")) == {"error": "ZeroDivisionError: division by zero"}
    assert json.loads(z.read("clonehero.json")) == {"folder": None, "documents": None}
    assert "left out (why):\n  nothing" in z.read("MANIFEST.txt").decode()


def test_songcharter_diagnostics(home, tmp_path, monkeypatch, capsys):
    h, root = home
    monkeypatch.setenv("SONGCHARTER_HOME", str(h))
    monkeypatch.setenv("SONGCHARTER_CACHE", str(root))
    monkeypatch.setattr(D, "_quick_report", lambda: {"ok": True, "quick": True})
    from songcharter import wsl
    monkeypatch.setattr(wsl, "is_wsl", lambda: False)
    out = tmp_path / "d" / "bundle.zip"
    assert cli.main(["diagnostics", "--out", str(out)]) == 0
    printed = capsys.readouterr().out
    assert f"diagnostics: {out}" in printed and "no audio" in printed and "in Windows" not in printed
    with zipfile.ZipFile(out) as z:
        assert json.loads(z.read("doctor-now.json")) == {"ok": True, "quick": True}
        assert f"work/w5-{'0' * 16}/pipeline.json" in z.namelist()
    # in WSL it also prints the Windows path
    monkeypatch.setattr(wsl, "is_wsl", lambda: True)
    monkeypatch.setattr(wsl, "distro", lambda: "Ubuntu")
    monkeypatch.setattr(wsl, "onedrive_roots", lambda: [])
    monkeypatch.setattr(wsl, "shell_folder", lambda name: None)
    assert cli.main(["diagnostics", "--out", str(out)]) == 0
    assert "in Windows: \\\\wsl.localhost\\Ubuntu" + str(out).replace("/", "\\") in capsys.readouterr().out
    # a place it cannot write: exit 2, one line
    (tmp_path / "file").write_text("x")
    assert cli.main(["diagnostics", "--out", str(tmp_path / "file" / "d.zip")]) == 2
    assert capsys.readouterr().err.startswith("songcharter: error: cannot write")


# ------------------------------------------------------------------------------------------------ the lyrics

sys.path.insert(0, str(Path(__file__).parent))
from test_lyrics import TEXT, WORDS, with_lyrics  # noqa: E402
from test_pipeline import write_song  # noqa: E402


def test_no_pasted_word_reaches_the_bundle(tmp_path, monkeypatch):
    """A chart with lyrics (test_pipeline's stand-in engines, the real lyrics stage around a stand-in aligner, the
    real assemble), as the UI makes it: the bundle of its home and cache holds pipeline.json, assemble.json and
    report.json, which count the lyrics, and not one of their words."""
    h, root = tmp_path / "home", tmp_path / "cache"
    monkeypatch.setenv("SONGCHARTER_CACHE", str(root))
    write_song(tmp_path / "song.flac")
    out = h / "library" / "0123456789abcdef" / "Fixture Band - Song"
    result = chart(tmp_path / "song.flac", out, Options(takes=1, lyrics=TEXT, preview=False),
                   engines=with_lyrics()(), log=lambda line: None, sampler=None)
    assert result.ok and result.lyrics["added"]
    assert any(w.encode() in (out / "notes.chart").read_bytes() for w in WORDS)   # the chart has them
    write(h / "logs" / "job-20261104-101010.log", f"songcharter ui job x: python -m songcharter.cli chart song.flac "
                                                  f"--out={out} --events --lyrics=/dev/fd/5\n")
    z = bundle(h, root, tmp_path)
    work = f"work/{result.work.name}"
    assert {f"{work}/pipeline.json", f"{work}/assemble.json", f"{work}/report.json"} <= set(z.namelist())
    assert json.loads(z.read(f"{work}/pipeline.json"))["lyrics"]["words"] == 14
    for name in z.namelist():
        data = z.read(name)
        assert not any(w.encode() in data for w in WORDS), name
