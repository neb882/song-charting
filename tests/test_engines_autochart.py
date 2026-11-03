"""The autochart engine wrapper (songcharter.engines.autochart) with a stand-in for the driver: the command and its
environment (the CUDA library path for "cuda"), one shared work folder, the take cache and its key (the input, the
seed and the install), failures and the install check. autochart itself never runs."""
import json
import subprocess
import sys

import pytest

from songcharter.engines import autochart as AC
from songcharter.engines.autochart import DEFAULT_SEED, Install, find_install, generate
from songcharter.errors import ToolError

ENGINE_VERSION = "2026.06.16-cross-platform-runtime"


def install(tmp_path):
    root = tmp_path / "ac"
    (root / "src" / "engine" / "bin").mkdir(parents=True)
    (root / "src" / "engine" / "bin" / "autochart-engine.cjs").write_text("//", encoding="utf-8")
    (root / "src" / "engine" / "manifest.json").write_text(json.dumps({"engineVersion": ENGINE_VERSION}),
                                                           encoding="utf-8")
    (root / "src" / "engine" / "catalog.json").write_text('{"components": []}', encoding="utf-8")
    (root / "models" / "fretformer-v2").mkdir(parents=True)
    (root / "models" / "fretformer-v2" / "manifest.json").write_text("{}", encoding="utf-8")
    (root / "node_modules" / "onnxruntime-node").mkdir(parents=True)
    (root / "ac_headless.cjs").write_text("//", encoding="utf-8")
    return root


class FakeDriver:
    """Writes a take the way ac_headless.cjs does, and records every call."""

    def __init__(self, fail_seed=None, transcriber=None):
        self.calls = []
        self.fail_seed = fail_seed
        self.transcriber = transcriber  # the device the engine ends up using, if not the one asked for

    def __call__(self, cmd, env, cwd, capture_output, text, timeout):
        self.calls.append((cmd, env, cwd))
        audio, out = cmd[cmd.index("--audio") + 1], cmd[cmd.index("--out") + 1]
        seed = int(env["AC_SEED"])
        if seed == self.fail_seed:
            return subprocess.CompletedProcess(cmd, 1, "", "[autochart] expert: engine job\nError: model crashed\n")
        from pathlib import Path
        folder = Path(out)
        (folder / "autochart_run").mkdir(parents=True, exist_ok=True)
        (folder / "notes.chart").write_text(f"[Song]\n{{\n}}\n// seed {seed}\n", encoding="utf-8")
        summary = {"inputSha256": AC.sha256(Path(audio)), "seed": seed, "difficulties": ["expert"],
                   "temperature": float(env["AC_TEMPERATURE"]), "topP": float(env["AC_TOP_P"]),
                   "runs": [{"status": "completed",
                             "devices": {"transcriber": self.transcriber or env["AC_DEVICE"]}}]}
        (folder / "autochart_run" / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
        return subprocess.CompletedProcess(cmd, 0, "", "")


def test_one_take_per_seed_on_a_shared_work_folder(tmp_path):
    inst = find_install(install(tmp_path), node="/usr/bin/node")
    audio = tmp_path / "input.wav"
    audio.write_bytes(b"RIFF....WAVE")
    drv = FakeDriver()
    takes = generate(inst, audio, tmp_path / "out", (DEFAULT_SEED, 101, 202), device="cuda", ffmpeg="/opt/ffmpeg",
                     title="Song", artist="Band", run=drv)
    assert [t.seed for t in takes] == [DEFAULT_SEED, 101, 202] and not any(t.cached for t in takes)
    assert [t.chart for t in takes] == [tmp_path / "out" / f"seed_{s}" / "notes.chart" for s in (DEFAULT_SEED, 101, 202)]
    works = {c[0][c[0].index("--work") + 1] for c in drv.calls}
    assert works == {str(tmp_path / "out" / "work")}  # the engine's separation and beat map are cached there
    cmd, env, cwd = drv.calls[0]
    assert cmd[:2] == ["/usr/bin/node", str(inst.driver)] and cwd == str(inst.driver.parent)
    assert env["AC_DIFFICULTIES"] == "expert" and env["AC_DEVICE"] == "cuda" and env["AUTOCHART_FFMPEG_PATH"] == "/opt/ffmpeg"
    assert env["AC_APP_ROOT"] == str(inst.app_root) and env["AC_MODELS"] == str(inst.models)
    assert env["AC_TITLE"] == "Song" and env["AC_ARTIST"] == "Band"
    assert env["AUTOCHART_ONNX_TRANSCRIBER_DEVICE"] == "cuda"  # not the engine's WebGPU preference
    assert takes[1].devices == {"transcriber": "cuda"}


def test_a_take_made_on_another_device_is_made_again(tmp_path):
    """The engine falls back by itself (CUDA libraries missing, a WebGPU adapter that runs on the CPU): such a take
    is kept and reported, but the next run on the requested device makes it again."""
    inst = find_install(install(tmp_path), node="node")
    audio = tmp_path / "input.wav"
    audio.write_bytes(b"x")
    drv = FakeDriver(transcriber="webgpu")
    first = generate(inst, audio, tmp_path / "out", (1,), device="cuda", run=drv)
    assert first[0].devices == {"transcriber": "webgpu"} and not first[0].cached
    again = generate(inst, audio, tmp_path / "out", (1,), device="cuda", run=FakeDriver())
    assert not again[0].cached and again[0].devices == {"transcriber": "cuda"}
    assert generate(inst, audio, tmp_path / "out", (1,), device="cuda", run=FakeDriver())[0].cached
    # an override set by the caller wins, and webgpu (or none) is left to the engine
    env_drv = FakeDriver()
    generate(inst, audio, tmp_path / "w", (2,), device="webgpu", run=env_drv)
    assert "AUTOCHART_ONNX_TRANSCRIBER_DEVICE" not in env_drv.calls[0][1] or \
        env_drv.calls[0][1]["AUTOCHART_ONNX_TRANSCRIBER_DEVICE"] == AC.os.environ.get("AUTOCHART_ONNX_TRANSCRIBER_DEVICE")


def test_finished_takes_are_reused_and_a_changed_input_is_not(tmp_path):
    inst = find_install(install(tmp_path), node="node")
    audio = tmp_path / "input.wav"
    audio.write_bytes(b"one")
    drv = FakeDriver()
    generate(inst, audio, tmp_path / "out", (1, 2), run=drv)
    assert len(drv.calls) == 2
    again = generate(inst, audio, tmp_path / "out", (2, 1, 3), run=drv)
    assert [t.cached for t in again] == [True, True, False] and len(drv.calls) == 3 and again[0].seconds == 0.0
    audio.write_bytes(b"two")  # another song (or another decode): every take runs again
    fresh = generate(inst, audio, tmp_path / "out", (1,), run=drv)
    assert not fresh[0].cached and len(drv.calls) == 4
    # a take cut off before its summary was written is not reused
    (tmp_path / "out" / "seed_2" / "autochart_run" / "summary.json").unlink()
    assert AC._done(tmp_path / "out" / "seed_2", AC.take_key(AC.sha256(audio), 2, AC.install_key(inst))) is None


def test_a_take_is_keyed_by_the_install_too(tmp_path):
    """A take made by another engine, model set or driver is not reused (a re-run after an update would otherwise
    build from the old engine's notes, or splice takes of two engines), and neither is one without take.json."""
    root = install(tmp_path)
    inst = find_install(root, node="node")
    audio, out = tmp_path / "input.wav", tmp_path / "out"
    audio.write_bytes(b"one")
    drv = FakeDriver()
    generate(inst, audio, out, (1, 2), run=drv)
    made = json.loads((out / "seed_1" / AC.TAKE).read_text(encoding="utf-8"))
    assert made == AC.take_key(AC.sha256(audio), 1, AC.install_key(inst)) and made["engineVersion"] == ENGINE_VERSION
    assert [t.cached for t in generate(inst, audio, out, (1, 2), run=drv)] == [True, True] and len(drv.calls) == 2
    updates = [(root / "src" / "engine" / "manifest.json", json.dumps({"engineVersion": "2027.02.01-new-engine"})),
               (root / "src" / "engine" / "catalog.json", '{"components": [{"id": "fretformer-2-onnx"}]}'),
               (root / "models" / "fretformer-v2" / "manifest.json", '{"revision": "new"}'),
               (root / "node_modules" / "onnxruntime-node" / "package.json", '{"version": "1.99.0"}'),
               (root / "ac_headless.cjs", "// driver B")]
    for path, text in updates:
        path.write_text(text, encoding="utf-8")
        calls = len(drv.calls)
        takes = generate(inst, audio, out, (1, 2, 3), run=drv)  # none mixed in from before the update
        assert [t.cached for t in takes] == [False] * 3 and len(drv.calls) == calls + 3, path
    made = json.loads((out / "seed_3" / AC.TAKE).read_text(encoding="utf-8"))
    assert made["engineVersion"] == "2027.02.01-new-engine"
    (out / "seed_1" / AC.TAKE).unlink()  # a take from before take.json (an older songcharter): run again
    assert [t.cached for t in generate(inst, audio, out, (1, 2), run=drv)] == [False, True]


def test_a_failed_take_raises_with_the_drivers_last_lines(tmp_path):
    inst = find_install(install(tmp_path), node="node")
    audio = tmp_path / "input.wav"
    audio.write_bytes(b"x")
    with pytest.raises(ToolError, match=r"(?s)seed 7 failed \(exit 1\):\n.*model crashed"):
        generate(inst, audio, tmp_path / "out", (6, 7), run=FakeDriver(fail_seed=7))
    assert not (tmp_path / "out" / "seed_7" / AC.TAKE).exists() and (tmp_path / "out" / "seed_6" / AC.TAKE).is_file()

    def slow(cmd, **kw):
        raise subprocess.TimeoutExpired(cmd, kw["timeout"])

    with pytest.raises(ToolError, match="seed 8 did not finish within 4200 s"):  # a user-facing error, not a bug
        generate(inst, audio, tmp_path / "out", (8,), timeout_s=3600, run=slow)
    with pytest.raises(ValueError, match="distinct"):
        generate(inst, audio, tmp_path / "out", (6, 6), run=FakeDriver())
    with pytest.raises(ValueError, match="device"):
        generate(inst, audio, tmp_path / "out", (6,), device="tpu", run=FakeDriver())
    with pytest.raises(FileNotFoundError, match="does not exist"):
        generate(inst, tmp_path / "missing.wav", tmp_path / "out", run=FakeDriver())


def test_the_install_check_names_what_is_missing(tmp_path, monkeypatch):
    root = install(tmp_path)
    assert isinstance(find_install(root, node="node"), Install)
    (root / "models" / "fretformer-v2" / "manifest.json").unlink()
    (root / "node_modules" / "onnxruntime-node").rmdir()
    with pytest.raises(FileNotFoundError) as e:
        find_install(root, node="node")
    assert "fetch_models.sh" in str(e.value) and "npm ci" in str(e.value) and "setup.sh" not in str(e.value)
    monkeypatch.setenv("SONGCHARTER_AUTOCHART", str(tmp_path / "nowhere"))
    monkeypatch.setattr(AC.shutil, "which", lambda name: None)
    monkeypatch.delenv("SONGCHARTER_NODE", raising=False)
    with pytest.raises(FileNotFoundError, match="node .install Node.js"):
        find_install()


def fake_nvidia(tmp_path, monkeypatch, wsl: bool = True):
    """A site-packages folder holding the nvidia namespace package's CUDA 13 and cuDNN folders (as the cu132 lane's
    wheels lay them out) first on sys.path, and WSL's driver folder (or none)."""
    site = tmp_path / "site-packages"
    for sub in ("cu13/lib", "cudnn/lib", "cusparselt/lib"):
        (site / "nvidia" / sub).mkdir(parents=True)
    monkeypatch.syspath_prepend(str(site))
    monkeypatch.delitem(sys.modules, "nvidia", raising=False)
    (tmp_path / "wsl-lib").mkdir()
    monkeypatch.setattr(AC, "WSL_LIB", tmp_path / ("wsl-lib" if wsl else "no-wsl-lib"))
    return site / "nvidia"


def test_the_cuda_library_path(tmp_path, monkeypatch):
    """cu13/lib and cudnn/lib of every folder of the nvidia package (ours first, as it is first on sys.path), then
    WSL's driver libraries when that folder exists; no other nvidia folder."""
    nvidia = fake_nvidia(tmp_path, monkeypatch)
    path = AC.cuda_library_path()
    assert path[:2] == [str(nvidia / "cu13" / "lib"), str(nvidia / "cudnn" / "lib")]
    assert path[-1] == str(tmp_path / "wsl-lib") and not any("cusparselt" in p for p in path)
    monkeypatch.setattr(AC, "WSL_LIB", tmp_path / "nowhere")
    assert str(tmp_path / "wsl-lib") not in AC.cuda_library_path()
    monkeypatch.setattr(AC.importlib.util, "find_spec", lambda name: None)  # no nvidia package at all (the cpu lane)
    assert AC.cuda_library_path() == []


def test_the_cuda_take_gets_the_library_path_and_the_cpu_take_does_not(tmp_path, monkeypatch):
    """For "cuda" the driver's LD_LIBRARY_PATH starts with the CUDA 13 folders and keeps what was set; for "cpu" it is
    left as it was. This process's own LD_LIBRARY_PATH never changes, and neither does the take's key."""
    nvidia = fake_nvidia(tmp_path, monkeypatch)
    monkeypatch.setenv("LD_LIBRARY_PATH", "/opt/mine")
    inst = find_install(install(tmp_path), node="node")
    audio = tmp_path / "input.wav"
    audio.write_bytes(b"x")
    drv = FakeDriver()
    generate(inst, audio, tmp_path / "gpu", (1,), device="cuda", run=drv)
    generate(inst, audio, tmp_path / "cpu", (1,), device="cpu", run=drv)
    cuda_env, cpu_env = drv.calls[0][1], drv.calls[1][1]
    folders = AC.cuda_library_path()   # ours, then this Python's own nvidia folders when it has them, then WSL's
    assert folders[:2] == [str(nvidia / "cu13" / "lib"), str(nvidia / "cudnn" / "lib")]
    assert cuda_env["LD_LIBRARY_PATH"].split(":") == folders + ["/opt/mine"] and folders[-1] == str(tmp_path / "wsl-lib")
    assert cpu_env["LD_LIBRARY_PATH"] == "/opt/mine" and AC.os.environ["LD_LIBRARY_PATH"] == "/opt/mine"
    key = AC.take_key(AC.sha256(audio), 1, AC.install_key(inst))
    assert json.loads((tmp_path / "gpu" / "seed_1" / AC.TAKE).read_text(encoding="utf-8")) == key
    monkeypatch.delenv("LD_LIBRARY_PATH")
    generate(inst, audio, tmp_path / "gpu2", (1,), device="cuda", run=drv)
    assert drv.calls[2][1]["LD_LIBRARY_PATH"] == ":".join(folders)
    generate(inst, audio, tmp_path / "cpu2", (1,), device="cpu", run=drv)
    assert "LD_LIBRARY_PATH" not in drv.calls[3][1]
