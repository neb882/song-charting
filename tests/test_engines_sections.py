"""The sections engine (songcharter.engines.sections) with stand-ins: a fake allin1 Python (the probe, the command,
the stems it is sent, the model choice, the CPU after a failed CUDA run, the cache, the fallback when allin1 is
missing or fails), the runner script on a fake All-In-One package (in this process, and through the real probe
with the package only on PYTHONPATH), the pinned-weight check, the naming rules, and the librosa fallback on a
synthetic song, with and without given beats. allin1 itself never runs here and its weights are never
downloaded."""
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import textwrap
import types

import numpy as np
import pytest

from songcharter.engines import sections as S
from songcharter.engines.sections import (ALLIN1_FOLDS, ALLIN1_MODELS, ALLIN1_REPO, ALLIN1_REVISION, Allin1Error,
                                          Settings, allin1_input, allin1_stem, checkpoint_paths, find_sections,
                                          name_segments)
from songcharter.errors import ToolError
from songcharter.sections import read_allin1

SR = S.SAMPLE_RATE
SEGMENTS = [[0.0, 0.5, "start"], [0.5, 4.0, "intro"], [4.0, 9.5, "verse"], [9.5, 10.0, "end"]]


def song(seconds=10.0, seed=0):
    rng = np.random.default_rng(seed)
    n = int(seconds * SR)
    stems = {name: (0.1 * rng.standard_normal((2, n))).astype(np.float32)
             for name in ("drums", "bass", "other", "vocals", "guitar", "piano")}
    return np.sum(list(stems.values()), axis=0).astype(np.float32), stems


NO_KERNEL = (b"Traceback (most recent call last):\n  ...\ntorch.AcceleratorError: CUDA error: no kernel image is "
             b"available for execution on the device\nCompile with `TORCH_USE_CUDA_DSA` to enable device-side "
             b"assertions.\n")
# the real runner's last lines when CUDA runs out of memory (its error line; the end-to-end test below checks the form)
OUT_OF_MEMORY = (b"Traceback (most recent call last):\n  ...\ntorch.OutOfMemoryError: CUDA out of memory. Tried to "
                 b"allocate 2.00 GiB. GPU 0 has a total capacity of 11.99 GiB of which 1.07 GiB is free.\n")


class FakeAllin1:
    """A Python with allin1: answers the runner's probe and run commands the way allin1_runner.py does. fail:
    "probe", "run", "cuda" (every run on cuda fails as on a GPU the torch build has no kernels for), "oom" (every run
    on cuda ends with CUDA out of memory, as the runner does) or "kill" (every run on the CPU, or on cuda with fail_on
    "cuda", ends by SIGKILL, as the OOM killer ends it). during: called while a run "runs"."""

    def __init__(self, cuda=False, fail=None, cuda_error=None, during=None, fail_on="cpu"):
        self.cuda, self.fail, self.cuda_error, self.during, self.fail_on = cuda, fail, cuda_error, during, fail_on
        self.calls, self.jobs, self.inputs = [], [], []

    def __call__(self, cmd, capture_output, timeout, cwd, text=None, input=None):
        self.calls.append(cmd)
        assert cmd[1:4] == ["-c", S.RUNNER_BOOT, str(S.RUNNER)] and capture_output and os.path.isdir(cwd)
        if cmd[4] == "probe":
            if self.fail == "probe":
                return subprocess.CompletedProcess(cmd, 1, "", "Traceback ...\nImportError: no All-In-One package\n")
            info = {"package": "all-in-one-infer", "module": "allin1_infer", "version": "3.1.0", "torch": "2.x",
                    "cuda": self.cuda, "cuda_error": self.cuda_error, "attention": "torch", "python": "3.13",
                    "platform": sys.platform}
            open(cmd[5], "w", encoding="utf-8").write(json.dumps(info))
            return subprocess.CompletedProcess(cmd, 0, "", "")
        job = json.loads(open(cmd[5], encoding="utf-8").read())
        self.jobs.append(job)
        self.inputs.append(np.frombuffer(input, dtype="<i2").reshape(4, job["samples"]))
        if self.during is not None:
            self.during()
        if self.fail == "timeout":
            raise subprocess.TimeoutExpired(cmd, timeout)
        if self.fail == "kill" and job["device"] == self.fail_on:
            return subprocess.CompletedProcess(cmd, -9, b"", b"")
        if self.fail == "run":
            return subprocess.CompletedProcess(cmd, 1, b"", b"RuntimeError: shapes do not match\n")
        if self.fail == "cuda" and job["device"] == "cuda":
            return subprocess.CompletedProcess(cmd, 1, b"", NO_KERNEL)
        if self.fail == "oom" and job["device"] == "cuda":
            return subprocess.CompletedProcess(cmd, 1, b"", OUT_OF_MEMORY)
        result = {"segments": SEGMENTS, "bpm": 120.0, "beats": [0.5, 1.0], "downbeats": [0.5], "device": job["device"],
                  "threads": job["threads"], "attention": "torch", "peak_rss_mb": 640.5,
                  "seconds": {"spectrogram": 1.0, "load": 0.1, "inference": 2.0, "total": 3.1}}
        open(job["out"], "w", encoding="utf-8").write(json.dumps(result))
        return subprocess.CompletedProcess(cmd, 0, b"", b"")


@pytest.fixture
def weights(tmp_path, monkeypatch):
    """Eight small checkpoint files with their hashes pinned in place of the real ones, and a download that serves
    them and records what it was asked for."""
    files = {}
    for i, fold in enumerate(ALLIN1_FOLDS):
        path = tmp_path / "hub" / f"fold{i}.pth"
        path.parent.mkdir(exist_ok=True)
        path.write_bytes(f"checkpoint {i}".encode())
        name = ALLIN1_FOLDS[fold][0]
        monkeypatch.setitem(ALLIN1_FOLDS, fold, (name, hashlib.sha256(path.read_bytes()).hexdigest()))
        files[name] = path
    asked = []

    def download(repo, file, revision):
        asked.append((repo, file, revision))
        return str(files[file])

    download.asked = asked
    download.files = files
    return download


def test_allin1_gets_our_stems_folded_to_its_four(tmp_path, weights):
    mix, stems = song()
    fake = FakeAllin1()
    r = find_sections(mix, stems, tmp_path / "out", Settings(python="/envs/allin1/python", threads=3), run=fake,
                      download=weights)
    assert [c[4] for c in fake.calls] == ["probe", "run"] and fake.calls[0][0] == "/envs/allin1/python"
    job, sent = fake.jobs[0], fake.inputs[0]
    assert job["device"] == "cpu" and job["threads"] == 3 and job["stems"] == ["bass", "drums", "other", "vocals"]
    assert job["checkpoints"] == [str(weights.files[ALLIN1_FOLDS["harmonix-fold0"][0]])]  # fold 0 on the CPU
    assert weights.asked == [(ALLIN1_REPO, ALLIN1_FOLDS["harmonix-fold0"][0], ALLIN1_REVISION)]
    other = stems["other"] + stems["guitar"] + stems["piano"]  # 6s's guitar and piano fold into "other"
    assert np.array_equal(sent[2], allin1_stem(other)) and np.array_equal(sent[3], allin1_stem(stems["vocals"]))
    assert np.array_equal(sent, allin1_input(stems))
    assert r.backend == "allin1" and not r.cached and r.path == tmp_path / "out" / "segments.json"
    assert [(s.start, s.label) for s in r.segments] == [(s[0], s[2]) for s in SEGMENTS]
    assert read_allin1(r.path) == r.segments  # what assemble's "sections" reads
    info = json.loads((tmp_path / "out" / "engine.json").read_text(encoding="utf-8"))
    assert info["allin1"]["model"] == "harmonix-fold0" and info["allin1"]["package"] == "all-in-one-infer"
    assert info["allin1"]["revision"] == ALLIN1_REVISION and info["input"]["other"] == ["guitar", "other", "piano"]
    assert info["settings"]["python"] == "/envs/allin1/python" and info["seconds"]["inference"] == 2.0
    assert info["allin1"]["peak_rss_mb"] == 640.5  # the runner's own peak, for the pipeline's report


def test_fold_0_runs_on_cuda_and_on_the_cpu_and_a_model_asked_for_runs_on_either(tmp_path, weights, monkeypatch):
    """model "auto" is fold 0 on every device, the ensemble on CUDA no more (M6-10: the grid's rules that read
    allin1's beats were measured on fold 0); a model asked for runs as asked on either device. The cache key
    follows the model run, not the setting: an ensemble result cached by an earlier version is not what "auto"
    reads now, nor is fold 0's once "auto" means another model."""
    mix, stems = song()
    fold0 = [str(weights.files[ALLIN1_FOLDS["harmonix-fold0"][0]])]
    ensemble = [str(weights.files[ALLIN1_FOLDS[f][0]]) for f in ALLIN1_MODELS["harmonix-all"]]
    fake = FakeAllin1(cuda=True)
    runs = [find_sections(mix, stems, tmp_path / str(i), s, run=fake, download=weights) for i, s in enumerate((
        Settings(python="py"), Settings(python="py", device="cpu"), Settings(python="py", model="harmonix-all"),
        Settings(python="py", device="cpu", model="harmonix-all")))]
    assert S.AUTO_MODEL == "harmonix-fold0"
    assert [(j["device"], j["checkpoints"]) for j in fake.jobs] == [
        ("cuda", fold0), ("cpu", fold0), ("cuda", ensemble), ("cpu", ensemble)]
    assert [r.info["allin1"]["model"] for r in runs] == ["harmonix-fold0"] * 2 + ["harmonix-all"] * 2
    assert len({r.info["key"] for r in runs}) == 4
    out = tmp_path / "one"   # the ensemble's result in the folder, then "auto" on CUDA: run again, with fold 0
    find_sections(mix, stems, out, Settings(python="py", model="harmonix-all"), run=fake, download=weights)
    auto = find_sections(mix, stems, out, Settings(python="py"), run=fake, download=weights)
    assert not auto.cached and fake.jobs[-1]["checkpoints"] == fold0 and auto.info["key"] == runs[0].info["key"]
    assert find_sections(mix, stems, out, Settings(python="py"), run=fake, download=weights).cached
    assert len(fake.jobs) == 6
    monkeypatch.setattr(S, "AUTO_MODEL", "harmonix-fold3")
    moved = find_sections(mix, stems, out, Settings(python="py"), run=fake, download=weights)
    assert not moved.cached and moved.info["allin1"]["model"] == "harmonix-fold3" and len(fake.jobs) == 7
    with pytest.raises(Allin1Error, match="no working CUDA"):
        find_sections(mix, stems, tmp_path / "x", Settings(backend="allin1", python="py", device="cuda"),
                      run=FakeAllin1(cuda=False), download=weights)


def test_a_failed_cuda_run_is_run_again_on_the_cpu_when_the_device_was_auto(tmp_path, weights):
    mix, stems = song()
    fake = FakeAllin1(cuda=True, fail="cuda")  # CUDA is there, but this torch build has no kernels for the GPU
    r = find_sections(mix, stems, tmp_path / "out", Settings(python="py"), run=fake, download=weights)
    assert [(j["device"], len(j["checkpoints"])) for j in fake.jobs] == [("cuda", 1), ("cpu", 1)]
    assert r.backend == "allin1" and r.info["allin1"]["device"] == "cpu"
    assert r.info["allin1"]["model"] == "harmonix-fold0"  # the same model, and the CPU's key
    assert r.info["key"] == find_sections(mix, stems, tmp_path / "cpu", Settings(python="py", device="cpu"),
                                          run=FakeAllin1(), download=weights).info["key"]
    fallback = "the CUDA run failed (torch.AcceleratorError: CUDA error: no kernel image is available"
    assert r.info["allin1"]["fallback"].startswith(fallback) and fallback in r.info["why"]
    again = find_sections(mix, stems, tmp_path / "out", Settings(python="py"), run=fake, download=weights)
    assert again.cached and len(fake.jobs) == 3 and fallback in again.info["why"]  # the CPU result is reused
    asked = FakeAllin1(cuda=True, fail="cuda")   # a model asked for: the CPU runs it too
    r = find_sections(mix, stems, tmp_path / "all", Settings(python="py", model="harmonix-all"), run=asked,
                      download=weights)
    assert [(j["device"], len(j["checkpoints"])) for j in asked.jobs] == [("cuda", 8), ("cpu", 8)]
    assert r.info["allin1"]["model"] == "harmonix-all"
    with pytest.raises(Allin1Error, match="no kernel image"):  # asked for cuda: no second try
        find_sections(mix, stems, tmp_path / "asked", Settings(backend="allin1", python="py", device="cuda"),
                      run=FakeAllin1(cuda=True, fail="cuda"), download=weights)
    with pytest.raises(Allin1Error, match=r"CUDA run failed \(RuntimeError: shapes .*\), and then on the CPU: allin1"):
        find_sections(mix, stems, tmp_path / "both", Settings(backend="allin1", python="py"),
                      run=FakeAllin1(cuda=True, fail="run"), download=weights)


def test_cuda_out_of_memory_is_run_again_on_the_cpu_for_auto_and_for_cuda_asked_for(tmp_path, weights, monkeypatch):
    """The runner ends a CUDA run that ran out of memory; this side runs it again on the CPU, as the runner itself
    once did, for "cuda" asked for too (any other failure raises there), and says so in the runner's old words."""
    monkeypatch.setattr(S, "MEMINFO", tmp_path / "none")   # no MemTotal: nothing is left out
    mix, stems = song()
    words = ("CUDA ran out of memory (CUDA out of memory. Tried to allocate 2.00 GiB. GPU 0 has a total capacity of "
             "11.99 GiB of which 1.07 GiB is free.); analysed on the CPU")
    for device in ("auto", "cuda"):
        fake = FakeAllin1(cuda=True, fail="oom")
        r = find_sections(mix, stems, tmp_path / device, Settings(backend="allin1", python="py", device=device),
                          run=fake, download=weights)
        assert [j["device"] for j in fake.jobs] == ["cuda", "cpu"], device
        assert r.backend == "allin1" and r.info["allin1"]["device"] == "cpu"
        assert r.info["allin1"]["fallback"] == words and r.info["why"].endswith(f"; {words}")


def test_a_cached_analysis_says_what_this_call_did_not_what_the_run_that_made_it_did(tmp_path, weights, monkeypatch):
    """The CPU's analysis is cached, never a run's fallback story (v0.5.0's review, F1), so the pipeline's record of
    the sections does not depend on what the cache held: (a) the CPU result of an auto run whose CUDA run ran out of
    memory (or whose probe found CUDA broken) answers a later CPU-asked call with no fallback; (b) a CPU-asked result
    answers an auto run's CPU retry after CUDA ran out of memory with that run's fallback, not none (which the
    pipeline would name as "its Python has no working CUDA"). engine.json says the same as the result."""
    monkeypatch.setattr(S, "MEMINFO", tmp_path / "none")
    on_disk = lambda folder: json.loads((folder / "engine.json").read_text(encoding="utf-8"))  # noqa: E731
    mix, stems = song()
    words = ("CUDA ran out of memory (CUDA out of memory. Tried to allocate 2.00 GiB. GPU 0 has a total capacity of "
             "11.99 GiB of which 1.07 GiB is free.); analysed on the CPU")
    broken = FakeAllin1(cuda=False, cuda_error="AcceleratorError: CUDA error: no kernel image is available")
    for name, first_run in (("oom", FakeAllin1(cuda=True, fail="oom")), ("broken", broken)):   # (a)
        out = tmp_path / f"a-{name}"
        first = find_sections(mix, stems, out, Settings(python="py"), run=first_run, download=weights)
        assert first.info["allin1"]["device"] == "cpu" and first.info["allin1"]["fallback"], name
        cpu = FakeAllin1(cuda=True)
        hit = find_sections(mix, stems, out, Settings(python="py", device="cpu"), run=cpu, download=weights)
        assert hit.cached and cpu.jobs == [] and hit.info["key"] == first.info["key"], name
        assert hit.info["allin1"]["fallback"] is None and hit.info["allin1"]["cuda_error"] is None, name
        assert on_disk(out) == hit.info, name
    out = tmp_path / "b"   # (b)
    made = find_sections(mix, stems, out, Settings(python="py", device="cpu"), run=FakeAllin1(cuda=True),
                         download=weights)
    assert made.info["allin1"]["fallback"] is None
    oom = FakeAllin1(cuda=True, fail="oom")
    hit = find_sections(mix, stems, out, Settings(python="py"), run=oom, download=weights)
    assert [j["device"] for j in oom.jobs] == ["cuda"] and hit.cached   # the CPU's analysis, from the cache
    assert hit.info["allin1"]["fallback"] == words and hit.info["why"].endswith(f"; {words}")
    assert hit.info["allin1"]["device"] == "cpu" and on_disk(out) == hit.info


def test_a_probe_whose_cuda_kernel_failed_means_the_cpu(tmp_path, weights):
    mix, stems = song()
    fake = FakeAllin1(cuda=False, cuda_error="AcceleratorError: CUDA error: no kernel image is available")
    r = find_sections(mix, stems, tmp_path / "out", Settings(python="py"), run=fake, download=weights)
    assert [(j["device"], len(j["checkpoints"])) for j in fake.jobs] == [("cpu", 1)]
    assert r.backend == "allin1" and r.info["allin1"]["cuda_error"].startswith("AcceleratorError")
    assert r.info["allin1"]["fallback"].startswith("CUDA does not run here (AcceleratorError")
    assert r.info["allin1"]["fallback"] in r.info["why"]
    with pytest.raises(Allin1Error, match=r"no working CUDA \(AcceleratorError"):
        find_sections(mix, stems, tmp_path / "x", Settings(backend="allin1", python="py", device="cuda"), run=fake,
                      download=weights)


def test_a_finished_run_is_reused_and_a_changed_input_or_setting_is_not(tmp_path, weights):
    mix, stems = song()
    fake = FakeAllin1()
    out = tmp_path / "out"
    first = find_sections(mix, stems, out, Settings(python="py"), run=fake, download=weights)
    again = find_sections(mix, stems, out, Settings(python="py", threads=7), run=fake, download=weights)
    assert again.cached and again.info["key"] == first.info["key"] and len(fake.jobs) == 1
    other = find_sections(mix, stems, out, Settings(python="py", model="harmonix-fold3"), run=fake, download=weights)
    assert not other.cached and other.info["key"] != first.info["key"] and len(fake.jobs) == 2
    louder = {k: (v * 1.01 if k == "drums" else v) for k, v in stems.items()}
    assert not find_sections(mix, louder, out, Settings(python="py"), run=fake, download=weights).cached
    (out / "engine.json").unlink()  # a run cut off before engine.json was written is no hit
    assert not find_sections(mix, louder, out, Settings(python="py"), run=fake, download=weights).cached
    assert len(fake.jobs) == 4


def test_a_hit_says_why_this_call_chose_its_backend(tmp_path, weights, monkeypatch):
    pytest.importorskip("librosa")
    mix, stems = song()
    monkeypatch.delenv(S.ENV_PYTHON, raising=False)
    monkeypatch.setattr(S, "ALLIN1_MODULES", ("no_such_allin1_module",))
    out = tmp_path / "out"
    on_disk = lambda folder: json.loads((folder / "engine.json").read_text(encoding="utf-8"))  # noqa: E731
    first = find_sections(mix, stems, out)
    assert not first.cached and "set SONGCHARTER_ALLIN1_PYTHON" in first.info["why"]
    # the user sets an allin1 Python, but its probe fails: the same librosa result, and the probe's error as why
    hit = find_sections(mix, stems, out, Settings(python="/envs/allin1/python"), run=FakeAllin1(fail="probe"))
    assert hit.cached and hit.backend == "librosa" and "failed its probe" in hit.info["why"]
    assert "SONGCHARTER" not in hit.info["why"] and hit.info["settings"]["python"] == "/envs/allin1/python"
    assert on_disk(out) == hit.info and hit.info["key"] == first.info["key"]
    asked = find_sections(mix, stems, out, Settings(backend="librosa"))
    assert asked.cached and asked.info["why"] == "backend librosa asked for"
    assert asked.info["settings"]["backend"] == "librosa" and on_disk(out) == asked.info
    assert asked.info["seconds"] == {"total": 0.0, "run": first.info["seconds"]}  # the run's own timings kept
    assert asked.info["librosa"] == first.info["librosa"] and asked.segments == first.segments
    # allin1: a hit from a second Python names that one
    fake = FakeAllin1()
    find_sections(mix, stems, tmp_path / "a", Settings(python="/envs/A/python"), run=fake, download=weights)
    b = find_sections(mix, stems, tmp_path / "a", Settings(python="/envs/B/python", threads=2), run=fake,
                      download=weights)
    assert b.cached and len(fake.jobs) == 1 and "/envs/B/python" in b.info["why"]
    assert b.info["settings"]["python"] == "/envs/B/python" and b.info["settings"]["threads"] == 2
    assert on_disk(tmp_path / "a") == b.info and b.info["allin1"]["threads"] == fake.jobs[0]["threads"]


@pytest.fixture
def fallback(monkeypatch):
    """The librosa fallback replaced by a stub that records why it was chosen."""
    calls = []

    def stub(mix, stems, out, s, beats, why):
        calls.append(list(why))
        return S.SectionsResult(out / "segments.json", {"backend": "librosa", "why": "; ".join(why)}, False)

    monkeypatch.setattr(S, "_librosa", stub)
    return calls


@pytest.mark.parametrize("case, reason", [
    ("unset", "SONGCHARTER_ALLIN1_PYTHON"),
    ("probe", "failed its probe"),
    ("missing", "did not run"),
    ("run", "allin1 failed .exit 1.:\nRuntimeError: shapes do not match"),
    ("weights", "not the pinned"),
    ("stems", "needs bass, drums, vocals"),
])
def test_auto_falls_back_to_librosa_and_says_why(tmp_path, weights, fallback, monkeypatch, case, reason):
    mix, stems = song(2.0)
    monkeypatch.delenv(S.ENV_PYTHON, raising=False)
    monkeypatch.setattr(S, "ALLIN1_MODULES", ("no_such_allin1_module",))  # not in this Python either
    run = FakeAllin1(fail=case if case in ("probe", "run") else None)
    python = None if case == "unset" else "py"
    if case == "missing":
        def run(cmd, **kw):
            raise FileNotFoundError(2, "No such file or directory", cmd[0])
    if case == "weights":
        weights.files[ALLIN1_FOLDS["harmonix-fold0"][0]].write_bytes(b"tampered")
    if case == "stems":
        stems = {k: v for k, v in stems.items() if k != "vocals"}
    r = find_sections(mix, stems, tmp_path / "out", Settings(python=python), run=run, download=weights)
    assert r.backend == "librosa" and len(fallback) == 1
    assert re.search(reason, fallback[0][0]), fallback[0]
    with pytest.raises(Allin1Error, match=reason):  # asked for allin1: no fallback
        find_sections(mix, stems, tmp_path / "out2", Settings(backend="allin1", python=python), run=run,
                      download=weights)


def test_allin1_failing_without_librosa_names_both(tmp_path, weights, monkeypatch):
    """allin1 set up but failing (here its probe), and librosa, the fallback, not installed: an error the user can
    act on that keeps allin1's reason, not librosa's ImportError from inside the fallback (a "bug", exit 3)."""
    mix, stems = song(2.0)
    monkeypatch.setitem(sys.modules, "librosa", None)  # not installed: importing it raises ImportError
    with pytest.raises(ToolError) as e:
        find_sections(mix, stems, tmp_path / "out", Settings(python="py"), run=FakeAllin1(fail="probe"),
                      download=weights)
    assert re.match(r"(?s)allin1 failed \(allin1's Python py failed its probe \(exit 1\).*\) and the librosa "
                    r"fallback is not installed: pip install songcharter\[sections\]$", str(e.value)), str(e.value)
    assert isinstance(e.value.__cause__, Allin1Error) and not (tmp_path / "out").exists()


def test_no_huggingface_hub_falls_back_too(tmp_path, fallback, monkeypatch):
    mix, stems = song(2.0)
    monkeypatch.setitem(sys.modules, "huggingface_hub", None)  # not installed: importing it raises ImportError
    r = find_sections(mix, stems, tmp_path / "out", Settings(python="py"), run=FakeAllin1())
    assert r.backend == "librosa" and "allin1 weights for harmonix-fold0: ModuleNotFoundError" in fallback[0][0]


def test_the_python_comes_from_the_setting_the_environment_or_this_python(monkeypatch):
    monkeypatch.setenv(S.ENV_PYTHON, "/from/env/python")
    assert S.allin1_python(Settings()) == "/from/env/python"
    assert S.allin1_python(Settings(python="/from/setting")) == "/from/setting"
    monkeypatch.delenv(S.ENV_PYTHON)
    monkeypatch.setattr(S, "ALLIN1_MODULES", ("no_such_allin1_module",))
    assert S.allin1_python(Settings()) is None
    monkeypatch.setattr(S, "ALLIN1_MODULES", ("json",))  # a module this Python has
    assert S.allin1_python(Settings()) == sys.executable


def test_pinned_weights_are_hash_checked(weights):
    paths = checkpoint_paths("harmonix-all", weights)
    assert len(paths) == 8
    assert [a[1] for a in weights.asked] == [ALLIN1_FOLDS[f][0] for f in ALLIN1_MODELS["harmonix-all"]]
    assert {a[0] for a in weights.asked} == {ALLIN1_REPO} and {a[2] for a in weights.asked} == {ALLIN1_REVISION}
    weights.files[ALLIN1_FOLDS["harmonix-fold5"][0]].write_bytes(b"evil")
    with pytest.raises(RuntimeError, match="not the pinned"):
        checkpoint_paths("harmonix-all", weights)
    with pytest.raises(ValueError, match="unknown allin1 model"):
        checkpoint_paths("harmonix-fold9", weights)


def test_the_real_pins_look_like_pins():
    assert len(ALLIN1_REVISION) == 40 and len(ALLIN1_FOLDS) == 8
    assert all(len(sha) == 64 and int(sha, 16) >= 0 for _, sha in ALLIN1_FOLDS.values())
    assert ALLIN1_MODELS["harmonix-fold0"] == ["harmonix-fold0"] and len(ALLIN1_MODELS["harmonix-all"]) == 8


def test_a_stem_is_what_madmom_reads_from_a_demucs_wav():
    y = np.array([[0.5, -0.5, 0.25, 1 / 32768, -1 / 32768], [0.5, 0.0, -0.25, 0.0, 0.0]], dtype=np.float32)
    # x 32768 and rounded per channel, then the mean truncated toward zero (madmom's integer remix)
    assert allin1_stem(y).tolist() == [16384, -8192, 0, 0, 0] and allin1_stem(y).dtype == np.int16
    loud = np.array([[2.0, -1.0], [0.0, 1.0]], dtype=np.float32)  # peaks over full scale: rescaled by 1 / 2.02
    want = np.round(loud / 2.02 * 32768).astype(np.int16).mean(axis=0).astype(np.int16)
    assert allin1_stem(loud).tolist() == want.tolist()


def test_bad_inputs(tmp_path):
    mix, stems = song(1.0)
    with pytest.raises(ValueError, match="44100 Hz"):
        find_sections(mix, stems, tmp_path, sample_rate=48000)
    with pytest.raises(ValueError, match="channels, samples"):
        find_sections(mix[0], stems, tmp_path)
    with pytest.raises(ValueError, match="stem drums"):
        find_sections(mix, {**stems, "drums": stems["drums"][:, :-1]}, tmp_path)
    for bad, match in [({"backend": "madmom"}, "backend"), ({"model": "harmonix-fold8"}, "unknown allin1 model"),
                       ({"device": "tpu"}, "device"), ({"seconds_per_segment": 0}, "positive")]:
        with pytest.raises(ValueError, match=match):
            find_sections(mix, stems, tmp_path, Settings(**bad))


# ---------------------------------------------------------------------------------------------------- the runner

FAKE_PACKAGE = {
    "omegaconf.py": """
        class OmegaConf:
            @staticmethod
            def create(d):
                return dict(d)
    """,
    "allin1_infer/__init__.py": "",
    "allin1_infer/spectrogram.py": """
        import numpy as np
        seen = []
        class Signal(np.ndarray):
            def __new__(cls, data, sample_rate=None):
                seen.append((data.dtype.str, data.shape, sample_rate, int(data[0])))
                return np.asarray(data).view(cls)
        def build_spec_processor():
            return lambda sig: np.stack([np.asarray(sig, dtype=np.float32)[::441][:10]] * 3, axis=1)
    """,
    "allin1_infer/postprocessing.py": """
        from dataclasses import dataclass
        @dataclass
        class Segment:
            start: float
            end: float
            label: str
        def postprocess_metrical_structure(logits, cfg):
            return {"beats": [0.5, 1.0], "downbeats": [0.5], "beat_positions": [1, 2]}
        def postprocess_functional_structure(logits, cfg):
            n = logits["frames"] / cfg["fps"]
            return [Segment(0.0, 0.02, "start"), Segment(0.02, n, "verse")]
        def estimate_tempo_from_beats(beats):
            return 120
    """,
    "allin1_infer/models/__init__.py": "",
    "allin1_infer/models/dinat.py": "NA_BACKEND = 'torch'\n",
    "allin1_infer/models/allinone.py": """
        loaded, rows = [], []
        class AllInOne:
            def __init__(self, cfg):
                self.cfg = cfg
            def to(self, device):
                if device == "cuda":   # a GPU with too little memory left for it
                    import torch
                    raise torch.cuda.OutOfMemoryError("CUDA out of memory. Tried to allocate 2.00 GiB")
                return self
            def load_state_dict(self, state):
                loaded.append(state)
            def eval(self):
                return self
            def __call__(self, spec):
                rows.append([int(spec[0, i, 0, 0]) for i in range(spec.shape[1])])
                return {"frames": spec.shape[2], "shape": tuple(spec.shape)}
    """,
    "allin1_infer/models/ensemble.py": """
        class Ensemble:
            def __init__(self, models):
                self.models, self.cfg = models, models[0].cfg
            def to(self, device):
                return self
            def eval(self):
                return self
            def __call__(self, spec):
                return self.models[0](spec)
    """,
}


@pytest.fixture
def fake_package(tmp_path, monkeypatch):
    root = tmp_path / "site"
    for rel, text in FAKE_PACKAGE.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(textwrap.dedent(text), encoding="utf-8")
    monkeypatch.syspath_prepend(str(root))
    for name in list(sys.modules):
        if name.startswith(("allin1_infer", "omegaconf")):
            monkeypatch.delitem(sys.modules, name)
    yield root
    for name in list(sys.modules):
        if name.startswith(("allin1_infer", "omegaconf")):
            del sys.modules[name]


def test_the_runner_on_a_fake_package(tmp_path, fake_package):
    torch = pytest.importorskip("torch")
    from songcharter.engines import allin1_runner as R
    ckpts = []
    for i in range(2):
        path = tmp_path / f"fold{i}.pth"
        torch.save({"config": {"fps": 100}, "state_dict": {"fold": i}}, path)
        ckpts.append(str(path))
    R.probe(tmp_path / "probe.json")
    probe = json.loads((tmp_path / "probe.json").read_text(encoding="utf-8"))
    assert probe["module"] == "allin1_infer" and probe["attention"] == "torch" and probe["cuda"] in (True, False)
    # each stem a constant of its own on stdin (bass 1, drums 2, other 3, vocals 4), so the names they get show
    stems = np.repeat(np.array([[1], [2], [3], [4]], dtype=np.int16), 4410, axis=1)
    job = {"samples": 4410, "stems": ["bass", "drums", "other", "vocals"], "checkpoints": ckpts, "device": "cpu",
           "threads": None, "seed": 0, "out": str(tmp_path / "result.json")}
    (tmp_path / "job.json").write_text(json.dumps(job), encoding="utf-8")
    R.run(tmp_path / "job.json", io.BytesIO(stems.astype("<i2").tobytes()))
    res = json.loads((tmp_path / "result.json").read_text(encoding="utf-8"))
    spectrogram, allinone = sys.modules["allin1_infer.spectrogram"], sys.modules["allin1_infer.models.allinone"]
    # each stem as mono int16 at 44.1 kHz, in the order allin1 stacks them (its extract_spectrograms: bass, drums,
    # other, vocals), and the model's input rows in that order too
    assert spectrogram.seen == [("<i2", (4410,), 44100, v) for v in (1, 2, 3, 4)]
    assert allinone.rows == [[1, 2, 3, 4]]
    assert allinone.loaded == [{"fold": 0}, {"fold": 1}]  # an ensemble of two
    assert res["segments"] == [[0.0, 0.02, "start"], [0.02, 0.1, "verse"]] and res["bpm"] == 120.0
    assert res["device"] == "cpu" and res["frames"] == 10 and "fallback" not in res
    assert res["peak_rss_mb"] == R.peak_rss_mb() and (res["peak_rss_mb"] is None or res["peak_rss_mb"] > 0)
    with pytest.raises(ValueError, match="int16 samples on stdin"):
        R.run(tmp_path / "job.json", io.BytesIO(b"\0" * 10))
    (tmp_path / "job.json").write_text(json.dumps({**job, "stems": job["stems"][::-1]}), encoding="utf-8")
    with pytest.raises(ValueError, match="this runner reads"):  # a caller sending another order is refused
        R.run(tmp_path / "job.json", io.BytesIO(stems.astype("<i2").tobytes()))
    assert R.main(["bogus"]) == 2
    # CUDA out of memory ends the run, with no CPU run here: the caller's CPU run is checked for memory first
    (tmp_path / "result.json").unlink()
    (tmp_path / "job.json").write_text(json.dumps({**job, "device": "cuda"}), encoding="utf-8")
    with pytest.raises(torch.cuda.OutOfMemoryError, match="CUDA out of memory"):
        R.run(tmp_path / "job.json", io.BytesIO(stems.astype("<i2").tobytes()))
    assert not (tmp_path / "result.json").exists() and allinone.rows == [[1, 2, 3, 4]]   # no model ran after it


@pytest.mark.skipif(sys.platform not in ("linux", "win32"), reason="the runner reports its peak on Linux and Windows")
def test_the_runner_reports_its_own_peak_not_its_parents():
    """The runner's peak is its own (VmHWM, PeakWorkingSetSize), not ru_maxrss: in a spawned process that starts
    from the parent's peak at the time of the spawn, so a small child of a large parent looked large."""
    big = np.ones(300 * 2 ** 20 // 8)  # 300 MB in this process before the spawn
    code = "import runpy, sys; print(runpy.run_path(sys.argv[1])['peak_rss_mb']())"
    out = subprocess.run([sys.executable, "-c", code, str(S.RUNNER)], capture_output=True, text=True, check=True)
    assert 1 < float(out.stdout) < 150, out.stdout  # a bare Python with json and the standard library
    del big


def test_the_runners_probe_runs_a_cuda_kernel(tmp_path, fake_package, monkeypatch):
    torch = pytest.importorskip("torch")
    from songcharter.engines import allin1_runner as R
    if torch.cuda.is_available():
        pytest.skip("a real GPU here")
    # is_available() true, but no kernel runs: as on a GPU this torch build has no kernels for
    monkeypatch.setattr(torch.cuda, "is_available", lambda: True)
    R.probe(tmp_path / "probe.json")
    probe = json.loads((tmp_path / "probe.json").read_text(encoding="utf-8"))
    assert probe["cuda"] is False and probe["cuda_error"] and ":" in probe["cuda_error"]


def test_the_runner_starts_under_the_allin1_pythons_own_import_rules(tmp_path, monkeypatch):
    extra, cwd, scripts = tmp_path / "extra", tmp_path / "cwd", tmp_path / "scripts"
    for d in (extra, cwd, scripts):
        d.mkdir()
    script = scripts / "show.py"
    script.write_text("import json, sys\nopen(sys.argv[1], 'w').write(json.dumps({'argv': sys.argv, 'path': sys.path, "
                      "'name': __name__}))\n", encoding="utf-8")
    monkeypatch.setenv("PYTHONPATH", str(extra))
    out = tmp_path / "out.json"
    proc = subprocess.run([sys.executable, "-c", S.RUNNER_BOOT, str(script), str(out)], cwd=cwd, capture_output=True,
                          text=True, timeout=60)
    assert proc.returncode == 0, proc.stderr
    seen = json.loads(out.read_text(encoding="utf-8"))
    assert seen["name"] == "__main__" and seen["argv"] == [str(script), str(out)]
    assert str(extra) in seen["path"]  # PYTHONPATH (and the user site) count, as for a plain `python -c`
    assert "" not in seen["path"] and str(cwd) not in seen["path"] and str(scripts) not in seen["path"]


def test_the_allin1_package_on_pythonpath_passes_the_real_probe(tmp_path, fake_package, monkeypatch):
    # what allin1_python's find_spec finds here, the runner's own Python finds too (with -I it did not)
    pytest.importorskip("torch")
    monkeypatch.delenv(S.ENV_PYTHON, raising=False)
    monkeypatch.setenv("PYTHONPATH", str(fake_package))
    python = S.allin1_python(Settings())
    assert python == sys.executable
    info = S.probe(python)
    assert info["module"] == "allin1_infer" and info["package"] == "all-in-one-infer"


def test_the_runner_builds_allin1s_own_chain_without_build_spec_processor(monkeypatch):
    from songcharter.engines import allin1_runner as R
    made = []

    def recorder(name):
        def make(*args, **kw):
            made.append((name, args, kw))
            return name
        return make

    sp = types.ModuleType("old_allin1.spectrogram")  # allin1 1.x: the chain's parts, no build_spec_processor
    sp.SequentialProcessor = lambda steps: (lambda sig: np.zeros((3, 2), np.float32))
    sp.Signal = lambda data, sample_rate: data
    for name in ("FramedSignalProcessor", "ShortTimeFourierTransformProcessor", "FilteredSpectrogramProcessor",
                 "LogarithmicSpectrogramProcessor"):
        setattr(sp, name, recorder(name))
    monkeypatch.setitem(sys.modules, "old_allin1.spectrogram", sp)
    spec = R.spectrogram("old_allin1", {s: np.zeros(10, np.int16) for s in R.STEMS})
    assert spec.shape == (4, 3, 2)
    assert made == [("FramedSignalProcessor", (), {"frame_size": 2048, "fps": 100}),
                    ("ShortTimeFourierTransformProcessor", (), {}),
                    ("FilteredSpectrogramProcessor", (), {"num_bands": 12, "fmin": 30, "fmax": 17000,
                                                          "norm_filters": True}),
                    ("LogarithmicSpectrogramProcessor", (), {"mul": 1, "add": 1})]


@pytest.mark.skipif(not os.environ.get("SONGCHARTER_ALLIN1_PYTHON"),
                    reason="no allin1 Python configured ($SONGCHARTER_ALLIN1_PYTHON)")
def test_the_configured_allin1_python_passes_its_probe():
    info = S.probe(os.environ["SONGCHARTER_ALLIN1_PYTHON"])
    assert info["package"] in ("all-in-one-infer", "allin1") and info["version"]


# ------------------------------------------------------------------------------------------------- the fallback

def test_naming_rules():
    def seg(cluster, vocals, loud=-12.0, guitar=-5.0, length=10.0):
        return {"cluster": cluster, "vocals": vocals, "loud_db": loud, "guitar_db": guitar, "start": 0.0,
                "end": length}
    feats = [seg(0, 0.0), seg(1, 0.9, -14), seg(2, 0.9, -10), seg(1, 0.8, -14), seg(2, 0.9, -10),
             seg(3, 0.7, -13, length=20), seg(4, 0.6, -13), seg(2, 0.9, -10), seg(5, 0.0, -12, guitar=-1.0),
             seg(6, 0.0, -25), seg(2, 0.9, -10), seg(0, 0.1, -15)]
    assert name_segments(feats, True) == ["intro", "verse", "chorus", "verse", "chorus", "bridge", "verse", "chorus",
                                          "solo", "break", "chorus", "outro"]
    # no vocal stem: the ends are the intro and the outro, the most repeated cluster the chorus
    plain = [seg(0, None), seg(1, None), seg(2, None), seg(1, None), seg(2, None), seg(1, None), seg(0, None)]
    assert name_segments(plain, False) == ["intro", "chorus", "verse", "chorus", "verse", "chorus", "outro"]
    # vocals from the start: no intro
    assert name_segments([seg(1, 0.9, -14), seg(2, 0.9, -10), seg(1, 0.9, -14), seg(2, 0.9, -10)], True) == [
        "verse", "chorus", "verse", "chorus"]


def synthetic_song(seed=0):
    """1 s of silence, then A B A B (16 s each, 120 BPM): A a low chord with kicks, B a high chord with hats and a
    voice; 1 s of silence at the end."""
    rng = np.random.default_rng(seed)
    t = np.arange(16 * SR) / SR
    beat = (t % 0.5) < 0.03
    a = 0.2 * sum(np.sin(2 * np.pi * f * t) for f in (110, 138.6, 164.8)) + 0.5 * beat * np.sin(2 * np.pi * 60 * t)
    b = 0.2 * sum(np.sin(2 * np.pi * f * t) for f in (392, 493.9, 587.3)) + 0.2 * beat * rng.standard_normal(len(t))
    voice = 0.3 * np.sin(2 * np.pi * 330 * t + 3 * np.sin(2 * np.pi * 5 * t))
    quiet = np.zeros(SR)
    parts = [quiet, a, b, a, b, quiet]
    vocals = np.concatenate([quiet, 0 * t, voice, 0 * t, voice, quiet])
    guitar = np.concatenate(parts)
    mix = guitar + vocals
    to2 = lambda x: np.stack([x, x]).astype(np.float32)  # noqa: E731
    return to2(mix), {"vocals": to2(vocals), "guitar": to2(guitar)}


def test_the_fallback_finds_the_sections_of_a_synthetic_song(tmp_path, monkeypatch):
    pytest.importorskip("librosa")
    mix, stems = synthetic_song()
    settings = Settings(backend="librosa", seconds_per_segment=16.0)
    r = find_sections(mix, stems, tmp_path / "one", settings)
    segs = r.segments
    assert r.backend == "librosa" and r.info["why"] == "backend librosa asked for"
    assert segs[0].label == "start" and segs[-1].label == "end" and segs[0].start == 0.0
    assert abs(segs[-1].end - mix.shape[1] / SR) < 1e-3
    assert all(a.end == b.start for a, b in zip(segs, segs[1:]))  # contiguous
    music = [s for s in segs if s.label not in ("start", "end")]
    assert abs(music[0].start - 1.0) < 0.1 and abs(music[-1].end - 65.0) < 0.1
    starts = [s.start for s in music[1:]]
    assert len(starts) == 3 and all(abs(x - y) < 1.0 for x, y in zip(starts, [17.0, 33.0, 49.0])), starts
    assert [s.label for s in music] == ["intro", "chorus", "inst", "chorus"]
    assert r.info["librosa"]["clusters"] >= 2 and r.info["librosa"]["target_segments"] == 4
    # deterministic, and cached by key
    again = find_sections(mix, stems, tmp_path / "two", settings)
    assert again.segments == segs and again.info["key"] == r.info["key"]
    monkeypatch.setattr(S, "laplacian_segments", lambda *a: pytest.fail("segmented again"))
    assert find_sections(mix, stems, tmp_path / "one", settings).cached
    with pytest.raises(pytest.fail.Exception):  # another setting is another key
        find_sections(mix, stems, tmp_path / "one", Settings(backend="librosa", seconds_per_segment=20.0))
    monkeypatch.setattr(S, "VOCALS_DB", -19.0)
    with pytest.raises(pytest.fail.Exception):  # and so is another constant
        find_sections(mix, stems, tmp_path / "one", settings)


def test_the_fallback_uses_the_given_beats_inside_the_audio(tmp_path, monkeypatch):
    pytest.importorskip("librosa")
    mix, stems = synthetic_song()
    settings = Settings(backend="librosa", seconds_per_segment=16.0)
    grid = np.arange(0.0, 65.0, 0.5)  # 120 BPM from 0 s to the end of the music
    inside = find_sections(mix, stems, tmp_path / "inside", settings, beats=grid)
    assert inside.info["librosa"]["beats"] == "given"
    starts = [s.start for s in inside.segments if s.label not in ("start", "end")][1:]
    assert len(starts) == 3 and all(abs(x - y) < 1.0 for x, y in zip(starts, [17.0, 33.0, 49.0])), starts
    # a tempo map's beats: a lead-in before 0 s and beats past the end, which are left out
    wide = np.concatenate([np.arange(-2.0, 0.0, 0.5), grid, mix.shape[1] / SR + np.arange(0.5, 4.0, 0.5)])
    lead = find_sections(mix, stems, tmp_path / "wide", settings, beats=wide)
    assert lead.segments == inside.segments and lead.info["key"] == inside.info["key"]
    monkeypatch.setattr(S, "laplacian_segments", lambda *a: pytest.fail("segmented again"))
    with pytest.raises(pytest.fail.Exception):  # other beats are another key
        find_sections(mix, stems, tmp_path / "inside", settings, beats=grid + 0.25)
    for bad, match in [(np.r_[grid[:10], np.nan, grid[10:]], "1 non-finite"), (grid.reshape(-1, 2), "1-D")]:
        with pytest.raises(ValueError, match=match):  # a NaN or a table is the caller's bug
            find_sections(mix, stems, tmp_path / "bad", settings, beats=bad)


# ------------------------------------------------------------------------------------------------ memory (M8-05)

def meminfo(tmp_path, monkeypatch, mem_mib, swap_mib=0.0):
    """/proc/meminfo saying MemTotal and SwapTotal (MemAvailable 0; neither it nor the swap counts) in place of this
    machine's."""
    path = tmp_path / "meminfo"
    path.write_text(f"MemTotal:       {round(mem_mib * 1024)} kB\nMemFree:        0 kB\nMemAvailable:   0 kB\n"
                    f"SwapTotal:      {round(swap_mib * 1024)} kB\nSwapFree:       0 kB\n")
    monkeypatch.setattr(S, "MEMINFO", path)


def test_m8_03s_lines_and_the_longest_song_that_fits():
    assert S.child_mib(60.0) == pytest.approx(354.5 + 17.443 * 60)   # A-a: about 1.02 GiB a minute
    assert S.tree_mib(60.0, False) == pytest.approx(853.5 + 20.403 * 60)   # A-b: today's tree
    assert S.tree_mib(60.0, True) == pytest.approx(853.5 + 17.703 * 60)    # the arrays let go: 162 MiB a minute less
    assert S.longest_s(S.tree_mib(500.0, True) + S.MARGIN_MIB) == pytest.approx(500.0)
    assert S.longest_s(100.0) == 0.0
    assert round(S.longest_s(11.2 * 1024) / 60, 2) == 8.84   # a 16 GB PC's 12 GB of WSL, no swap (M8-03 A-d's 9.0
    assert round(S.longest_s(10.2 * 1024) / 60, 2) == 7.88   # and 8.1 with a reserve of 1 GiB, without the residual)


def test_a_runner_ended_by_sigkill_is_named_as_most_likely_memory(tmp_path, weights, fallback, monkeypatch):
    monkeypatch.setattr(S, "MEMINFO", tmp_path / "none")   # no /proc/meminfo: nothing is left out before the run
    mix, stems = song(2.0)
    line = "allin1 was stopped, most likely for memory (a song of 0:02 needs about 0.4 GiB for it on the CPU)"
    assert S.stopped_line(2.0) == line
    r = find_sections(mix, stems, tmp_path / "out", Settings(python="py"), run=FakeAllin1(fail="kill"),
                      download=weights)
    assert r.backend == "librosa" and fallback == [[line]]
    with pytest.raises(Allin1Error, match=re.escape(line)):
        find_sections(mix, stems, tmp_path / "asked", Settings(backend="allin1", python="py"),
                      run=FakeAllin1(fail="kill"), download=weights)
    fake = FakeAllin1(cuda=True, fail="kill", fail_on="cuda")   # killed on CUDA: named, then run on the CPU
    r = find_sections(mix, stems, tmp_path / "cuda", Settings(python="py"), run=fake, download=weights)
    assert [j["device"] for j in fake.jobs] == ["cuda", "cpu"] and r.backend == "allin1"
    assert r.info["allin1"]["fallback"] == f"the CUDA run failed ({line}); analysed on the CPU"


def test_allin1_is_left_out_before_its_run_when_the_song_cannot_fit(tmp_path, weights, fallback, monkeypatch):
    """On the CPU the predicted tree with the margin is compared with MemTotal: just over, allin1 is left out before
    any run, just under it runs; neither the swap nor MemAvailable counts; with a loader (the arrays let
    go) the tree is smaller; a cached result and a run on CUDA are not checked."""
    mix, stems = song(10.0)
    edge = S.tree_mib(10.0, False) + S.MARGIN_MIB
    meminfo(tmp_path, monkeypatch, edge + 0.01)
    fake = FakeAllin1()
    r = find_sections(mix, stems, tmp_path / "fits", Settings(python="py"), run=fake, download=weights)
    assert r.backend == "allin1" and len(fake.jobs) == 1
    meminfo(tmp_path, monkeypatch, edge - 0.5, 8192)
    fake = FakeAllin1()
    r = find_sections(mix, stems, tmp_path / "over", Settings(python="py"), run=fake, download=weights)
    assert r.backend == "librosa" and fake.jobs == []
    assert re.fullmatch(r"allin1 was left out for memory \(a song of 0:10 needs about 0\.5 GiB for it on the CPU, "
                        r"2\.2 GiB with the rest of the chart and a margin; this PC has 2\.2 GiB of memory\)",
                        fallback[-1][0]), fallback[-1]
    held = S.SongArrays(mix, stems, lambda: (mix, stems))   # the arrays let go: under the edge
    assert find_sections(held, None, tmp_path / "freed", Settings(python="py"), run=fake,
                         download=weights).backend == "allin1"
    meminfo(tmp_path, monkeypatch, 100)
    hit = find_sections(mix, stems, tmp_path / "fits", Settings(python="py"), run=fake, download=weights)
    assert hit.cached and hit.backend == "allin1"
    cuda = FakeAllin1(cuda=True)
    r = find_sections(mix, stems, tmp_path / "cuda", Settings(python="py", device="cuda"), run=cuda, download=weights)
    assert r.backend == "allin1" and [j["device"] for j in cuda.jobs] == ["cuda"]


@pytest.fixture
def loadable(tmp_path, monkeypatch):
    """Fold 0 as a checkpoint the runner loads (torch's file, no tensors, so it loads for "cuda" on any machine),
    its hash pinned in place of the real one, and a download that serves it."""
    torch = pytest.importorskip("torch")
    path = tmp_path / "hub" / "fold0.pth"
    path.parent.mkdir()
    torch.save({"config": {"fps": 100}, "state_dict": {"fold": 0}}, path)
    name = ALLIN1_FOLDS["harmonix-fold0"][0]
    monkeypatch.setitem(ALLIN1_FOLDS, "harmonix-fold0", (name, hashlib.sha256(path.read_bytes()).hexdigest()))
    return lambda repo, file, revision: str(path)


@pytest.mark.parametrize("fits", [True, False], ids=["fits", "over"])
def test_cuda_out_of_memory_goes_to_a_cpu_run_in_a_fresh_process_that_is_checked_first(fits, tmp_path, fake_package,
                                                                                        loadable, fallback,
                                                                                        monkeypatch):
    """The real runner, in processes of its own, on the fake package, whose model runs out of CUDA memory (a GPU
    probe): the CUDA run ends with torch's error and no CPU run of its own, and the CPU run that follows is checked
    against MemTotal first. Under the line it runs and the result says why; over it, the librosa fallback with
    memory_skip's words and no CPU run at all (DESIGN.md 2.5, v0.5.0's gate review)."""
    mix, stems = song(2.0)
    edge = S.tree_mib(2.0, False) + S.MARGIN_MIB
    capacity = edge + 0.01 if fits else edge - 0.5
    meminfo(tmp_path, monkeypatch, capacity)
    monkeypatch.setenv("PYTHONPATH", str(fake_package))
    probe, devices, procs = FakeAllin1(cuda=True), [], []

    def run(cmd, **kw):
        if cmd[4] == "probe":
            return probe(cmd, **kw)
        devices.append(json.loads(open(cmd[5], encoding="utf-8").read())["device"])
        procs.append(subprocess.run(cmd, **kw))   # the runner as find_sections starts it
        return procs[-1]

    r = find_sections(mix, stems, tmp_path / "out", Settings(python=sys.executable), run=run, download=loadable)
    assert procs[0].returncode == 1 and re.search(rb"\ntorch\.(cuda\.)?OutOfMemoryError: CUDA out of memory",
                                                  procs[0].stderr), procs[0].stderr[-600:]
    oom = "CUDA ran out of memory (CUDA out of memory. Tried to allocate 2.00 GiB)"
    if fits:
        assert devices == ["cuda", "cpu"] and procs[1].returncode == 0, procs[1].stderr[-600:]
        assert r.backend == "allin1" and r.info["allin1"]["device"] == "cpu"
        assert [s.label for s in r.segments] == ["start", "verse"]   # the fake model's, from the CPU run
        assert r.info["allin1"]["fallback"] == f"{oom}; analysed on the CPU"
        assert r.info["why"].endswith(f"; {oom}; analysed on the CPU")
    else:
        skip = S.memory_skip(2.0, False, capacity)
        assert devices == ["cuda"] and r.backend == "librosa" and skip
        assert r.info["plain"] == skip and fallback == [[f"{oom}, and then on the CPU: {skip}"]]


def test_the_arrays_are_let_go_while_allin1_runs_and_read_again_when_needed(tmp_path, weights, monkeypatch):
    import gc
    import weakref
    mix, stems = song(2.0)
    keep = mix.copy(), {k: v.copy() for k, v in stems.items()}
    loads, alive = [], []

    def load():
        loads.append(1)
        return keep[0].copy(), {k: v.copy() for k, v in keep[1].items()}

    def counting(refs):
        def during():
            gc.collect()
            alive.append(sum(r() is not None for r in refs))
        return during

    refs = [weakref.ref(mix)] + [weakref.ref(y) for y in stems.values()]
    held = S.SongArrays(mix, stems, load)
    del mix, stems
    r = find_sections(held, None, tmp_path / "out", Settings(python="py"), run=FakeAllin1(during=counting(refs)),
                      download=weights)
    assert r.backend == "allin1" and alive == [0] and held.released and loads == []
    m, s = held.take()   # read again for the caller
    assert loads == [1] and np.array_equal(m, keep[0]) and all(np.array_equal(s[k], keep[1][k]) for k in keep[1])

    mix, stems = song(2.0)   # without a loader they stay
    refs = [weakref.ref(mix)] + [weakref.ref(y) for y in stems.values()]
    plain = S.SongArrays(mix, stems)
    del mix, stems
    find_sections(plain, None, tmp_path / "kept", Settings(python="py"), run=FakeAllin1(during=counting(refs)),
                  download=weights)
    assert alive[-1] == 7 and not plain.released

    got = []   # killed: the librosa fallback gets them read again
    monkeypatch.setattr(S, "_librosa", lambda mix, stems, out, s, beats, why: got.append((mix, stems)) or
                        S.SectionsResult(out / "segments.json", {"backend": "librosa", "why": "; ".join(why)}, False))
    held = S.SongArrays(*load(), load)
    find_sections(held, None, tmp_path / "killed", Settings(python="py"), run=FakeAllin1(fail="kill"),
                  download=weights)
    assert loads == [1, 1, 1] and np.array_equal(got[0][0], keep[0]) and np.array_equal(got[0][1]["vocals"],
                                                                                        keep[1]["vocals"])
    p = S.allin1_input(keep[1])   # the key reads the runner's bytes: the same key as the payload's own
    view = np.frombuffer(p.astype("<i2").tobytes(), dtype="<i2").reshape(p.shape)
    assert S.cache_key({"stems": view}, {"k": 1}) == S.cache_key({"stems": p}, {"k": 1})
    with pytest.raises(ValueError, match="stems come from the SongArrays"):
        find_sections(held, keep[1], tmp_path / "x", Settings(python="py"), run=FakeAllin1(), download=weights)


PAGE_INTERNALS = re.compile(r"/|\\|Error|Traceback|exit|Expired|SONGCHARTER|python|\.py|job\.json")


@pytest.mark.parametrize("case", ["timeout", "left out", "not installed", "probe", "run", "kill", "skip",
                                  "cuda then cpu", "cuda oom then cpu"])
def test_the_pages_words_for_each_cause_hold_no_path_command_or_exception(case, tmp_path, weights, fallback,
                                                                           monkeypatch):
    """The librosa result's info["plain"], the banner's words, per cause; engine.json's `why` keeps the details."""
    from songcharter import wsl
    mix, stems = song(2.0)
    monkeypatch.delenv(S.ENV_PYTHON, raising=False)
    monkeypatch.setattr(S, "ALLIN1_MODULES", ("no_such_allin1_module",))
    monkeypatch.setattr(wsl, "is_wsl", lambda: case == "left out")
    meminfo(tmp_path, monkeypatch, 100.0 if case == "skip" else 9 * 1024)   # 9 GiB: under the install's 11 GB
    python, settings = (None, Settings()) if case in ("left out", "not installed") else ("py", Settings(python="py"))
    run = {"timeout": FakeAllin1(fail="timeout"), "probe": FakeAllin1(fail="probe"), "run": FakeAllin1(fail="run"),
           "kill": FakeAllin1(fail="kill"), "cuda then cpu": FakeAllin1(cuda=True, fail="kill", fail_on="cuda"),
           "cuda oom then cpu": FakeAllin1(cuda=True, fail="oom")}.get(case, FakeAllin1())
    if case in ("cuda then cpu", "cuda oom then cpu"):
        meminfo(tmp_path, monkeypatch, 100.0)   # killed on CUDA, or out of its memory, then left out on the CPU
    r = find_sections(mix, stems, tmp_path / "out", settings, run=run, download=weights)
    want = {"timeout": S.TIMEOUT_PLAIN, "left out": S.LEFT_OUT_PLAIN, "not installed": S.NOT_INSTALLED_PLAIN,
            "probe": S.FAILED_PLAIN, "run": S.FAILED_PLAIN, "kill": S.stopped_line(2.0)}
    plain = r.info["plain"]
    assert r.backend == "librosa" and plain == want.get(case, plain)
    if case in ("skip", "cuda then cpu", "cuda oom then cpu"):
        assert plain == S.memory_skip(2.0, False, 100.0) and plain.startswith("allin1 was left out for memory")
    assert not PAGE_INTERNALS.search(plain), plain
    assert fallback[-1][0] != plain or case in ("kill", "skip")   # the details stay in `why`
