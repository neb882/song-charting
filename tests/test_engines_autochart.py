"""The autochart engine wrapper (songcharter.engines.autochart) with a stand-in for the driver: the command and its
environment, one shared work folder, the take cache, failures and the install check. autochart itself never runs."""
import json
import subprocess

import pytest

from songcharter.engines import autochart as AC
from songcharter.engines.autochart import DEFAULT_SEED, Install, find_install, generate


def install(tmp_path):
    root = tmp_path / "ac"
    (root / "src" / "engine" / "bin").mkdir(parents=True)
    (root / "src" / "engine" / "bin" / "autochart-engine.cjs").write_text("//", encoding="utf-8")
    (root / "models" / "fretformer-v2").mkdir(parents=True)
    (root / "models" / "fretformer-v2" / "manifest.json").write_text("{}", encoding="utf-8")
    (root / "node_modules" / "onnxruntime-node").mkdir(parents=True)
    (root / "ac_headless.cjs").write_text("//", encoding="utf-8")
    return root


class FakeDriver:
    """Writes a take the way ac_headless.cjs does, and records every call."""

    def __init__(self, fail_seed=None):
        self.calls = []
        self.fail_seed = fail_seed

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
                   "runs": [{"status": "completed", "devices": {"transcriber": env["AC_DEVICE"]}}]}
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
    assert takes[1].devices == {"transcriber": "cuda"}


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
    assert AC._done(tmp_path / "out" / "seed_2", AC.sha256(audio), 2) is None


def test_a_failed_take_raises_with_the_drivers_last_lines(tmp_path):
    inst = find_install(install(tmp_path), node="node")
    audio = tmp_path / "input.wav"
    audio.write_bytes(b"x")
    with pytest.raises(RuntimeError, match=r"(?s)seed 7 failed \(exit 1\):\n.*model crashed"):
        generate(inst, audio, tmp_path / "out", (6, 7), run=FakeDriver(fail_seed=7))
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
