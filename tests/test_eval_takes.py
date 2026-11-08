"""eval/takes.py (GPU takes of a set's songs: refs, stress, set20, on eval/tools or the installed app) and eval/gpu.sh's
takes, build and results. Made-up sets in a temporary folder, a stand-in for the engine's driver under the real
songcharter.engines.autochart.generate (so a take is reused as it really is), made-up packages: the engine never
runs, and no id, title or md5 of a real set is here. The 20-song set's made-up ids stand in for ids that spell titles:
none may appear in a printed line, a log or the results zip."""
import io
import json
import os
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from eval import takes as T
from songcharter.engines import autochart as AC

ROOT = Path(__file__).resolve().parent.parent
GPU = ROOT / "eval" / "gpu.sh"
SET20_IDS = ["zorblat", "quimby_flux", "a_made_up_title"]   # sorted: a_made_up_title s01, quimby_flux s02, zorblat s03
LABEL = {"a_made_up_title": "s01", "quimby_flux": "s02", "zorblat": "s03"}
bash = pytest.mark.skipif(shutil.which("bash") is None or sys.platform == "win32", reason="gpu.sh needs bash")


def md5(k: int) -> str:
    return f"{k:032x}"


def ac_root(path: Path) -> Path:
    """An autochart install as find_install wants it (the engine itself is the stand-in below)."""
    (path / "src" / "engine" / "bin").mkdir(parents=True)
    (path / "src" / "engine" / "bin" / "autochart-engine.cjs").write_text("//", encoding="utf-8")
    (path / "src" / "engine" / "manifest.json").write_text('{"engineVersion": "made-up"}', encoding="utf-8")
    (path / "models" / "fretformer-v2").mkdir(parents=True)
    (path / "models" / "fretformer-v2" / "manifest.json").write_text("{}", encoding="utf-8")
    (path / "node_modules" / "onnxruntime-node").mkdir(parents=True)
    (path / "ac_headless.cjs").write_text("//", encoding="utf-8")
    return path


class Driver:
    """Writes a take as ac_headless.cjs does, a song.ogg stand-in too, with the input's and the work folder's
    absolute paths in its JSON as the real driver writes them; records every call."""

    def __init__(self, fail_seed=None):
        self.calls = []
        self.fail_seed = fail_seed

    def __call__(self, cmd, env, cwd, capture_output, text, timeout):
        self.calls.append((cmd, env))
        audio, out, work = (cmd[cmd.index(k) + 1] for k in ("--audio", "--out", "--work"))
        seed = int(env["AC_SEED"])
        if seed == self.fail_seed:
            return subprocess.CompletedProcess(cmd, 1, "", f"Error: cannot decode {audio}\n")
        folder = Path(out)
        (folder / "autochart_run").mkdir(parents=True, exist_ok=True)
        (folder / "notes.chart").write_text(f'[Song]\n{{\n  Name = "input"\n}}\n// seed {seed}\n', encoding="utf-8")
        (folder / "song.ini").write_text("[song]\nname = input\n", encoding="utf-8")
        (folder / "song.ogg").write_bytes(b"OggS" + bytes(60))
        summary = {"inputSha256": AC.sha256(Path(audio)), "seed": seed, "difficulties": ["expert"],
                   "temperature": float(env["AC_TEMPERATURE"]), "topP": float(env["AC_TOP_P"]), "audio": audio,
                   "runs": [{"status": "completed", "nTokens": 7, "cachedStages": ["demucs"],
                             "devices": {"transcriber": env["AC_DEVICE"]}}]}
        (folder / "autochart_run" / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
        (folder / "autochart_run" / "expert_job.json").write_text(json.dumps({"cacheDir": f"{work}/engine-cache"}),
                                                                 encoding="utf-8")
        return subprocess.CompletedProcess(cmd, 0, "", "")


@pytest.fixture
def engine(tmp_path, monkeypatch):
    """The real generate with the stand-in driver; find_install on a made-up install (outside --app)."""
    drv = Driver()
    root = ac_root(tmp_path / "ac")
    monkeypatch.setattr(T, "generate", lambda inst, audio, out, seeds, device: AC.generate(
        inst, audio, out, seeds, device=device, ffmpeg="/made/up/ffmpeg", run=drv))
    monkeypatch.setattr(T, "find_install", lambda path, node=None: AC.find_install(root, node=node or "/made/up/node"))
    return drv


def wav(path: Path, k: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"RIFF" + k.to_bytes(4, "little") + b"WAVEmade up")


def refs(data: Path, ids=("aaa", "bbb"), test_song=True) -> None:
    (data / "refs").mkdir(parents=True, exist_ok=True)
    (data / "refs" / "songs.json").write_text(json.dumps([{"id": i, "md5": md5(k)} for k, i in enumerate(ids)]))
    for k, i in enumerate(ids):
        wav(data / "refs" / i / "input.wav", k)
    if test_song:
        wav(data / "refs" / "test_song" / "input.wav", 99)


def stress(data: Path, tmp_path: Path, monkeypatch, ids=("ttt", "sss", "ccc"), built=("ttt", "sss")) -> None:
    listed = [{"id": i, "slot": f"made-up slot {k}", "charts": k + 1, "primary": "guitar"} for k, i in enumerate(ids)]
    (tmp_path / "stress.json").write_text(json.dumps(listed))
    monkeypatch.setattr(T, "STRESS_LIST", tmp_path / "stress.json")
    for k, i in enumerate(built):
        wav(data / "stress" / i / "input.wav", 10 + k)
    (data / "stress" / "songs.json").write_text(json.dumps([{"id": i, "duration_s": 60.0 + k}
                                                            for k, i in enumerate(built)]))


def set20(root: Path, ids=SET20_IDS) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "set20.json").write_text(json.dumps([{"id": i, "slot": f"made-up slot {k}", "charts": 2, "primary": "x"}
                                                 for k, i in enumerate(ids)]))
    for k, i in enumerate(ids):
        wav(root / "stress" / i / "input.wav", 20 + k)
    (root / "stress" / "songs.json").write_text(json.dumps([{"id": i, "duration_s": 100.0 + k}
                                                            for k, i in enumerate(ids)]))


@pytest.fixture
def data(tmp_path, monkeypatch):
    d = tmp_path / "data"
    d.mkdir()
    monkeypatch.setenv("EVAL_DATA", str(d))
    monkeypatch.delenv("SET20_DATA", raising=False)
    return d


def log_lines(data: Path) -> list[str]:
    """runs/takes/takes.log without its times."""
    return [line.split(" ", 1)[1] for line in (data / "runs" / "takes" / "takes.log").read_text().splitlines()]


def no_id(text: str) -> bool:
    return not any(i in text for i in SET20_IDS)


# ------------------------------------------------------------------------------------------------ takes.py

def test_refs_is_the_default_and_keeps_its_paths_and_lines(data, engine, capsys):
    refs(data)
    assert T.main(["--device", "cpu", "--seeds", "1,2"]) == 0
    takes = data / "runs" / "takes"
    for sid in ("aaa", "bbb", "test_song"):
        for seed in (1, 2):
            assert (takes / sid / f"seed_{seed}" / "notes.chart").is_file()
    assert {c[0][c[0].index("--work") + 1] for c in engine.calls} == {str(takes / s / "work")
                                                                     for s in ("aaa", "bbb", "test_song")}
    assert log_lines(data) == ["start: 3 songs x 2 seeds on cpu"] + [
        f"{s} seed {seed}: 0 s, tokens 7, devices {{'transcriber': 'cpu'}}, reused ['demucs']"
        for s in ("aaa", "bbb", "test_song") for seed in (1, 2)] + ["ALL DONE"]
    assert [line.split(" ", 1)[1] for line in capsys.readouterr().out.splitlines()] == log_lines(data)
    assert not (takes / "refs").exists() and not list(takes.rglob("labels.json"))


def test_the_stress_set_comes_from_its_list_and_data_stress(data, tmp_path, engine, monkeypatch):
    stress(data, tmp_path, monkeypatch)
    assert T.main(["--set", "stress", "--device", "cpu", "--seeds", "1"]) == 0
    st = data / "runs" / "takes" / "stress"
    assert sorted(p.parent.parent.name for p in st.glob("*/seed_1/notes.chart")) == ["sss", "ttt"]
    assert [c[0][c[0].index("--audio") + 1] for c in engine.calls] == [str(data / "stress" / i / "input.wav")
                                                                     for i in ("ttt", "sss")]
    assert log_lines(data)[0] == "start: stress, 2 songs x 1 seeds on cpu"
    assert "ccc: no input.wav, skipped (build the set: eval/README.md)" in log_lines(data)
    assert json.loads((st / "labels.json").read_text()) == {"ttt": "ttt", "sss": "sss", "ccc": "ccc"}
    assert json.loads((st / "set.json").read_text()) == [
        {"label": "ttt", "slot": "made-up slot 0", "charts": 1, "duration_s": 60.0},
        {"label": "sss", "slot": "made-up slot 1", "charts": 2, "duration_s": 61.0},
        {"label": "ccc", "slot": "made-up slot 2", "charts": 3, "duration_s": None}]


def test_the_20_song_set_is_named_by_its_labels_in_every_line(data, tmp_path, engine, monkeypatch, capsys):
    root = tmp_path / "s20"
    set20(root)
    monkeypatch.setenv("SET20_DATA", str(root))
    real = T.generate

    def failing(inst, audio, out, seeds, device):   # an error that names the input's path
        if seeds == (2,) and "quimby_flux" in str(audio):
            raise RuntimeError(f"cannot read {audio}\nmore")
        return real(inst, audio, out, seeds, device)
    monkeypatch.setattr(T, "generate", failing)
    assert T.main(["--set", "set20", "--device", "cpu", "--seeds", "1,2"]) == 1
    out = capsys.readouterr().out
    log = (data / "runs" / "takes" / "takes.log").read_text()
    assert no_id(out) and no_id(log)
    lines = log_lines(data)
    assert lines[0] == "start: set20, 3 songs x 2 seeds on cpu" and lines[-1] == "ALL DONE, 1 takes failed"
    assert [line.split(" ")[0] for line in lines[1:-1]] == ["s01", "s01", "s02", "s02", "s03", "s03"]
    assert lines[4] == f"s02 seed 2: FAILED cannot read {root / 'stress' / 's02' / 'input.wav'}"
    # the take folders keep the ids (on this PC); the mapping and the set's facts beside them
    st = data / "runs" / "takes" / "set20"
    assert (st / "zorblat" / "seed_1" / "notes.chart").is_file() and not (st / "s03").exists()
    assert json.loads((st / "labels.json").read_text()) == {v: k for k, v in LABEL.items()}
    info = (st / "set.json").read_text()
    assert no_id(info) and [s["label"] for s in json.loads(info)] == ["s01", "s02", "s03"]
    assert json.loads(info)[2] == {"label": "s03", "slot": "made-up slot 0", "charts": 2, "duration_s": 100.0}


def test_a_finished_take_is_reused_and_only_a_missing_one_runs(data, tmp_path, engine, monkeypatch):
    stress(data, tmp_path, monkeypatch, ids=("ttt",), built=("ttt",))
    args = ["--set", "stress", "--device", "cpu", "--seeds", "1,2"]
    assert T.main(args) == 0 and len(engine.calls) == 2
    assert T.main(args) == 0 and len(engine.calls) == 2
    assert log_lines(data)[-3:] == [f"ttt seed {s}: cached, tokens 7, devices {{'transcriber': 'cpu'}}, reused "
                                    "['demucs']" for s in (1, 2)] + ["ALL DONE"]
    (data / "runs" / "takes" / "stress" / "ttt" / "seed_2" / "take.json").unlink()   # a take cut off
    assert T.main(args) == 0 and len(engine.calls) == 3 and engine.calls[-1][1]["AC_SEED"] == "2"


def test_songs_takes_labels_and_a_dry_run_writes_nothing(data, tmp_path, engine, monkeypatch, capsys):
    root = tmp_path / "s20"
    set20(root)
    monkeypatch.setenv("SET20_DATA", str(root))
    assert T.main(["--set", "set20", "--dry-run", "--seeds", "1,2"]) == 0
    assert capsys.readouterr().out.splitlines() == [f"s0{k}: input.wav found, 0 of 2 takes made" for k in (1, 2, 3)] + [
        "dry run: set20, 3 songs found, 0 without input.wav, 6 takes"]
    assert not (data / "runs").exists() and not engine.calls
    assert T.main(["--set", "set20", "--songs", "s02", "--device", "cpu", "--seeds", "1"]) == 0
    assert [c[0][c[0].index("--audio") + 1] for c in engine.calls] == [str(root / "stress" / "quimby_flux" / "input.wav")]
    (root / "stress" / "zorblat" / "input.wav").unlink()
    assert T.main(["--set", "set20", "--dry-run", "--seeds", "1"]) == 0
    out = capsys.readouterr().out
    assert "s02: input.wav found, 1 of 1 takes made" in out and "s03: no input.wav" in out and no_id(out)
    assert T.main(["--set", "set20", "--dry-run", "--songs", "zorblat"]) == 2   # nothing to take


@pytest.mark.parametrize("entries, match", [
    (None, "the 20-song set's list .* cannot be read"),
    ([{"id": "Has Spaces"}], "song 1 of the set20 set's list: its id is not"),
    ([{"id": "abc"}, {"id": "abc"}], "has an id twice"),
])
def test_a_list_that_cannot_be_read_exits_2_and_names_no_id(data, tmp_path, monkeypatch, capsys, entries, match):
    root = tmp_path / "s20"
    root.mkdir()
    if entries is not None:
        (root / "set20.json").write_text(json.dumps(entries))
    monkeypatch.setenv("SET20_DATA", str(root))
    assert T.main(["--set", "set20", "--dry-run"]) == 2
    err = capsys.readouterr().err
    assert re.search(match, err) and "Has Spaces" not in err


def test_scrub_puts_labels_for_ids_and_hides_md5s(data, tmp_path, monkeypatch, capsys):
    root = tmp_path / "s20"
    set20(root)
    monkeypatch.setenv("SET20_DATA", str(root))
    text = f"ok zorblat primary\nok quimby_flux alt\n{root}/stress/a_made_up_title/alt/{md5(5)}/x zorblatx\n"
    monkeypatch.setattr(sys, "stdin", io.StringIO(text))
    assert T.main(["--set", "set20", "--scrub"]) == 0
    assert capsys.readouterr().out == f"ok s03 primary\nok s02 alt\n{root}/stress/s01/alt/<md5>/x zorblatx\n"


# ------------------------------------------------------------------------------------------------ --app

def app_home(tmp_path: Path, lane="cu132", provider=True, python=None) -> Path:
    """An installed songcharter as runtime.json describes it: its autochart (made up), Node and ffmpeg (paths)."""
    home = tmp_path / "app"
    root = ac_root(home / "runtime" / "autochart")
    if provider:
        d = root / "node_modules" / "onnxruntime-node" / "bin" / "napi-v6" / "linux" / "x64"
        d.mkdir(parents=True)
        (d / "libonnxruntime_providers_cuda.so").write_bytes(b"made up")
    record = {"version": 1, "songcharter": "0.3.1", "home": str(home), "lane": lane, "python": python or "",
              "node": "/made/up/app/node/bin/node", "autochart": str(root), "scan_chart": "/made/up/scan.cjs",
              "ffmpeg": "/made/up/app/ffmpeg", "hf_home": str(home / "hf"), "models_complete": True}
    (home / "runtime" / "runtime.json").write_text(json.dumps(record))
    return home


@pytest.fixture
def app_env(tmp_path, monkeypatch):
    """os.environ as a copy (the app's environment goes into it), and the cu132 lane's library folders."""
    monkeypatch.setattr(os, "environ", dict(os.environ))
    monkeypatch.delenv("FFMPEG", raising=False)
    monkeypatch.delenv("SONGCHARTER_AUTOCHART", raising=False)
    monkeypatch.delenv("SONGCHARTER_NODE", raising=False)
    libs = ["/made/up/nvidia/cu13/lib", "/made/up/nvidia/cudnn/lib"]
    monkeypatch.setattr(AC, "cuda_library_path", lambda: libs)
    monkeypatch.setattr(T, "cuda_library_path", lambda: libs)
    return libs


def test_app_takes_run_on_the_apps_autochart_node_ffmpeg_and_cuda_libraries(data, tmp_path, monkeypatch, app_env):
    refs(data, ids=("aaa",), test_song=False)
    home = app_home(tmp_path)
    monkeypatch.setenv("SONGCHARTER_HOME", str(home))
    drv = Driver()
    monkeypatch.setattr(T, "generate", lambda inst, audio, out, seeds, device: AC.generate(
        inst, audio, out, seeds, device=device, run=drv))
    assert T.main(["--app", "--seeds", "1"]) == 0
    cmd, env = drv.calls[0]
    assert cmd[:2] == ["/made/up/app/node/bin/node", str(home / "runtime" / "autochart" / "ac_headless.cjs")]
    assert env["AUTOCHART_FFMPEG_PATH"] == "/made/up/app/ffmpeg" and env["AC_DEVICE"] == "cuda"
    assert env["LD_LIBRARY_PATH"].split(":")[:2] == app_env
    assert env["SONGCHARTER_HOME"] == str(home) and env["PATH"].startswith("/made/up/app/node/bin:")
    assert log_lines(data)[:2] == ["app: songcharter 0.3.1, the cu132 lane", "start: 1 songs x 1 seeds on cuda"]
    assert str(home) not in (data / "runs" / "takes" / "takes.log").read_text()


@pytest.mark.parametrize("change, problem", [
    ({}, None),
    ({"lane": "cu126"}, "the app is on the cu126 lane"),
    ({"provider": False}, "onnxruntime-node has no CUDA provider"),
    ({"libs": []}, "this Python has no CUDA 13 and cuDNN wheels"),
])
def test_the_app_check_names_each_problem(tmp_path, monkeypatch, app_env, capsys, change, problem):
    home = app_home(tmp_path, lane=change.get("lane", "cu132"), provider=change.get("provider", True))
    monkeypatch.setenv("SONGCHARTER_HOME", str(home))
    if "libs" in change:
        monkeypatch.setattr(T, "cuda_library_path", lambda: change["libs"])
    code = T.main(["--app", "--check", "--device", "cuda"])
    out = capsys.readouterr().out
    assert out.startswith(f"app: songcharter 0.3.1 at {home}, the {change.get('lane', 'cu132')} lane\n")
    if problem is None:
        assert code == 0 and out.endswith("check: ok\n") and "CUDA provider: there" in out
    else:
        assert code == 2 and f"problem: {problem}" in out and out.endswith("check: 1 problems\n")


def test_app_mode_without_an_install_exits_2(data, tmp_path, monkeypatch, app_env, capsys):
    refs(data, ids=("aaa",), test_song=False)
    monkeypatch.setenv("SONGCHARTER_HOME", str(tmp_path / "none"))
    assert T.main(["--app", "--check"]) == 2
    assert "no installed songcharter at" in capsys.readouterr().out
    assert T.main(["--app", "--seeds", "1"]) == 2 and not (data / "runs").exists()


# ------------------------------------------------------------------------------------------------ gpu.sh

def gpu(args, env, timeout=600):
    env = {k: v for k, v in env.items() if k not in ("SEEDS", "SONGS")}
    return subprocess.run([shutil.which("bash") or "bash", str(GPU), *args], env=env, capture_output=True, text=True,
                          stdin=subprocess.DEVNULL, timeout=timeout)


@bash
def test_gpu_takes_refuses_a_set_it_does_not_know(tmp_path):
    p = gpu(["takes", "refs", "nope"], {**os.environ, "EVAL_DATA": str(tmp_path / "d")})
    assert p.returncode == 2 and "a set is refs, stress or set20, not 'nope'" in p.stdout
    assert not (tmp_path / "d").exists()


@bash
@pytest.mark.parametrize("app", [False, True])
def test_gpu_takes_run_passes_each_set_and_the_app_through(tmp_path, app):
    """_takes, the detached half of `takes`: takes.py once per set, in order, with --app in app mode (run with the
    app's Python), then the zip."""
    data, home = tmp_path / "d", app_home(tmp_path)
    (data / "runs").mkdir(parents=True)
    stub = tmp_path / "python"
    stub.write_text(f"#!/bin/sh\necho \"$0 $*\" >> '{tmp_path / 'calls.txt'}'\n")
    stub.chmod(0o755)
    env = {**os.environ, "EVAL_DATA": str(data), "SONGCHARTER_HOME": str(home), "SONGCHARTER_APP": "1" if app else "0"}
    if app:
        py = home / "runtime" / "env" / "bin" / "python"
        py.parent.mkdir(parents=True)
        shutil.copy(stub, py)
        env.pop("EVAL_PY", None)
    else:
        env["EVAL_PY"] = str(stub)
    p = gpu(["_takes", "stress", "set20"], env)
    assert p.returncode == 0, p.stdout + p.stderr
    calls = [c for c in (tmp_path / "calls.txt").read_text().splitlines() if "takes.py" in c]
    flag = " --app" if app else ""
    assert [c.split("takes.py ", 1)[1] for c in calls] == [f"--set stress{flag} --device cuda",
                                                           f"--set set20{flag} --device cuda"]
    assert calls[0].startswith(str(py if app else stub))
    assert (data / "gpu_results.zip").is_file() and not (data / "runs" / "gpu_run.pid").exists()


@pytest.fixture
def three_sets(data, tmp_path, engine, monkeypatch):
    """Takes of a made-up reference set, stress set and 20-song set (the stand-in engine), under a made-up home."""
    refs(data, ids=("aaa",), test_song=False)
    stress(data, tmp_path, monkeypatch, ids=("ttt",), built=("ttt",))
    root = data / "set20"
    set20(root)
    for args in (["--set", "refs"], ["--set", "stress"], ["--set", "set20"]):
        assert T.main([*args, "--device", "cpu", "--seeds", "1"]) == 0
    (data / "runs" / "takes" / "set20" / "stray" / "seed_1").mkdir(parents=True)   # a folder labels.json does not name
    (data / "runs" / "takes" / "set20" / "stray" / "seed_1" / "notes.chart").write_text("x")
    (data / "runs" / "gpu_run.log").write_text(f"made up line {data}/runs/takes/set20/zorblat/work\n")
    return data


@bash
def test_results_zips_every_sets_takes_by_label_with_no_audio_and_no_id(three_sets, tmp_path):
    data = three_sets
    p = gpu(["results"], {**os.environ, "EVAL_DATA": str(data), "HOME": str(tmp_path)})
    assert p.returncode == 0, p.stdout + p.stderr
    assert "check_no_audio: ok" in p.stdout and "1 song folders left out" in p.stdout and no_id(p.stdout)
    z = zipfile.ZipFile(data / "gpu_results.zip")
    names = z.namelist()
    take = ["notes.chart", "song.ini", "take.json", "autochart_run/expert_job.json", "autochart_run/summary.json"]
    assert sorted(names) == sorted(
        ["gpu_results/gpu_run.log", "gpu_results/takes/takes.log", "gpu_results/takes/stress/set.json",
         "gpu_results/takes/set20/set.json"]
        + [f"gpu_results/takes/aaa/seed_1/{f}" for f in take] + [f"gpu_results/takes/stress/ttt/seed_1/{f}" for f in take]
        + [f"gpu_results/takes/set20/{lab}/seed_1/{f}" for lab in ("s01", "s02", "s03") for f in take])
    for n in names:
        text = z.read(n).decode()
        assert no_id(n) and no_id(text), n
        assert str(tmp_path) not in text, n   # the home folder is ~
    summary = json.loads(z.read("gpu_results/takes/set20/s03/seed_1/autochart_run/summary.json"))
    assert summary["audio"] == "~/data/set20/stress/s03/input.wav"
    assert json.loads(z.read("gpu_results/takes/set20/s03/seed_1/autochart_run/expert_job.json")) == {
        "cacheDir": "~/data/runs/takes/set20/s03/work/engine-cache"}
    assert z.read("gpu_results/gpu_run.log").decode() == "made up line ~/data/runs/takes/set20/s03/work\n"
    assert z.read("gpu_results/takes/aaa/seed_1/notes.chart") == (
        data / "runs" / "takes" / "aaa" / "seed_1" / "notes.chart").read_bytes()


@bash
def test_results_makes_no_zip_that_would_hold_audio(three_sets, tmp_path):
    data = three_sets
    (data / "gpu_results.zip").write_bytes(b"an old zip")
    (data / "runs" / "takes" / "set20" / "zorblat" / "seed_1" / "notes.chart").write_bytes(b"RIFF\x00\x00WAVEfmt ")
    p = gpu(["results"], {**os.environ, "EVAL_DATA": str(data), "HOME": str(tmp_path)})
    assert p.returncode != 0 and "no zip made" in p.stdout
    assert not (data / "gpu_results.zip").exists() and not (data / "gpu_results.zip.part").exists()
    assert "set20/s03/seed_1/notes.chart" in p.stdout and no_id(p.stdout)


def app_python(home: Path, log: Path) -> Path:
    """The app's runtime/env/bin/python: this Python, each call logged."""
    py = home / "runtime" / "env" / "bin" / "python"
    py.parent.mkdir(parents=True)
    py.write_text(f"#!/bin/sh\necho \"$*\" >> '{log}'\nexec '{sys.executable}' \"$@\"\n")
    py.chmod(0o755)
    return py


@bash
def test_build_app_set20_builds_on_the_apps_tools_and_prints_labels_only(tmp_path):
    from eval import golden as G
    from songcharter import audio as A
    from test_eval_stress import made_up_package
    try:
        scan, node = G.scan_chart_script(), G.node()
    except G.Refused as e:
        pytest.skip(f"scan-chart is not here ({e})")
    home = app_home(tmp_path)
    app_node = home / "runtime" / "node" / "bin" / "node"   # the app's Node: the real one, each call logged
    app_node.parent.mkdir(parents=True)
    app_node.write_text(f"#!/bin/sh\necho \"$*\" >> '{tmp_path / 'node-calls.txt'}'\nexec '{node}' \"$@\"\n")
    app_node.chmod(0o755)
    record = json.loads((home / "runtime" / "runtime.json").read_text())
    record.update(node=str(app_node), scan_chart=str(scan), ffmpeg=A.ffmpeg_exe())
    (home / "runtime" / "runtime.json").write_text(json.dumps(record))
    calls = tmp_path / "py-calls.txt"
    app_python(home, calls)
    data, s20 = tmp_path / "data", tmp_path / "data" / "set20"
    (s20 / "sng").mkdir(parents=True)
    (s20 / "set20.json").write_text(json.dumps([{"id": "zorblat", "slot": "made up", "charts": 1}]))
    (s20 / "stress.local.json").write_text(json.dumps([{"id": "zorblat", "md5": md5(7), "title": "Made Up Song",
                                                        "artist": "Made Up Band", "charter": "madeupcharter"}]))
    made_up_package(s20 / "sng" / f"{md5(7)}.sng", tmp_path)
    bin_ = tmp_path / "bin"
    bin_.mkdir()
    (bin_ / "curl").write_text("#!/bin/sh\necho 'no downloads in tests' >&2\nexit 22\n")
    (bin_ / "curl").chmod(0o755)
    env = {k: v for k, v in os.environ.items() if k not in ("EVAL_PY", "SONGCHARTER_SCAN_CHART", "SET20_DATA")}
    env.update(EVAL_DATA=str(data), SONGCHARTER_HOME=str(home), PATH=f"{bin_}{os.pathsep}{env['PATH']}")
    p = gpu(["build", "--app", "set20"], env)
    assert p.returncode == 0, p.stdout[-3000:]
    assert "ok s01 primary" in p.stdout and no_id(p.stdout) and md5(7) not in p.stdout and "Made Up" not in p.stdout
    built = s20 / "stress" / "zorblat"
    assert (built / "input.wav").is_file() and (built / "ref_notes.json").is_file()
    assert any("build_ref.py" in c for c in calls.read_text().splitlines())   # the app's Python ran the helpers
    assert str(scan) in (tmp_path / "node-calls.txt").read_text()            # and the app's Node, scan-chart


@bash
def test_app_env_links_the_apps_ffmpeg_when_there_is_none_on_path(tmp_path):
    home = app_home(tmp_path)
    app_python(home, tmp_path / "calls.txt")
    bin_ = tmp_path / "bin"   # a PATH with no ffmpeg: only what gpu.sh runs before `build` refuses the set
    bin_.mkdir()
    for cmd in ("dirname", "mkdir", "ln"):
        (bin_ / cmd).symlink_to(shutil.which(cmd))
    data = tmp_path / "data"
    p = gpu(["build", "--app", "nope"], {"PATH": str(bin_), "HOME": str(tmp_path), "EVAL_DATA": str(data),
                                         "SONGCHARTER_HOME": str(home)})
    assert p.returncode == 2 and "usage: eval/gpu.sh build" in p.stdout, p.stdout + p.stderr
    assert os.readlink(data / "bin" / "ffmpeg") == "/made/up/app/ffmpeg"
