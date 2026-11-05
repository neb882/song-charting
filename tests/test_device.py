"""Where a chart runs (songcharter.device) and `songcharter doctor`: the device "auto" takes and the guitar's, each CPU
outcome with its sentence; nvidia-smi parsed (a stand-in on PATH); autochart's CUDA provider check against stand-in
node output; memory, the sampler, doctor's problems and notes (WSL's memory against .wslconfig), the report and the
command line. No GPU is needed."""
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

from songcharter import device as D
from songcharter.cli import main

RTX = {"name": "NVIDIA GeForce RTX 4070", "driver": "581.57", "vram_mb": 12282, "compute_cap": "8.9"}
NO_SMI = (None, "nvidia-smi not found")


def torch_info(cuda="13.2", works=False, error=None, installed=True):
    return {"installed": installed, "cuda": cuda, "cuda_works": works, "cuda_error": error, "device_name": None}


@pytest.fixture
def machine(monkeypatch):
    """choose_device's facts, set by the test: torch's report and nvidia-smi's GPU."""
    facts = {"torch": torch_info(), "gpu": NO_SMI}
    monkeypatch.setattr(D, "torch_report", lambda full=True: facts["torch"])
    monkeypatch.setattr(D, "nvidia_smi", lambda: facts["gpu"])
    return facts


def test_choose_device_gives_a_reason_for_every_cpu_outcome(machine, monkeypatch):
    assert D.choose_device("cpu") == ("cpu", "asked for the CPU")
    assert D.choose_device("cuda") == ("cuda", None)   # asked for: the pipeline has checked it runs
    assert D.choose_device("auto") == ("cpu", "no NVIDIA GPU found")   # a CUDA build, no GPU (this dev container)
    machine["torch"] = torch_info(cuda=None)
    assert D.choose_device("auto") == ("cpu", "no NVIDIA GPU found")   # the cpu lane, no GPU
    machine["gpu"] = (RTX, None)
    assert D.choose_device("auto") == ("cpu", "this install's torch has no CUDA (the cpu lane)")
    machine["torch"] = torch_info(error="AcceleratorError: CUDA error: no kernel image is available")
    assert D.choose("auto") == ("cpu", "CUDA did not run on NVIDIA GeForce RTX 4070: AcceleratorError: CUDA error: "
                                       "no kernel image is available", "AcceleratorError: CUDA error: no kernel image "
                                                                       "is available")
    machine["torch"] = torch_info()   # CUDA in torch, a GPU, but not available: torch.cuda.init says why
    monkeypatch.setattr(D, "_unavailable_why", lambda: "RuntimeError: The NVIDIA driver on your system is too old")
    assert D.choose_device("auto") == ("cpu", "CUDA did not run on NVIDIA GeForce RTX 4070: RuntimeError: The NVIDIA "
                                              "driver on your system is too old")
    machine["torch"] = torch_info(works=True)
    assert D.choose_device("auto") == ("cuda", None)
    machine["torch"] = torch_info(installed=False)
    assert D.choose_device("auto") == ("cpu", "torch is not installed")
    with pytest.raises(ValueError, match="device is auto, cpu or cuda"):
        D.choose_device("tpu")


def test_choose_device_with_the_real_torch(monkeypatch):
    """The real torch_report: with CUDA not available and no nvidia-smi, "no NVIDIA GPU found" on any torch build."""
    torch = pytest.importorskip("torch")
    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    monkeypatch.setattr(D, "nvidia_smi", lambda: NO_SMI)
    assert D.choose_device("auto") == ("cpu", "no NVIDIA GPU found")
    t = D.torch_report(full=True)
    assert t["installed"] and t["version"] == torch.__version__ and t["cuda"] == torch.version.cuda
    assert not t["cuda_works"] and t["matmul"] is None and t["arch_list"] == []


def test_guitar_device_gives_a_reason_for_every_cpu_outcome():
    assert D.guitar_device("cuda", True, "CUDAExecutionProvider 357 nodes") == ("cuda", None)
    assert D.guitar_device("cpu", True) == ("cpu", "no GPU")
    assert D.guitar_device("cpu", None) == ("cpu", "no GPU")
    lane = D.guitar_device("cuda", False, "libcublas.so.13: cannot open shared object file", torch_cuda="12.6")
    assert lane == ("cpu", "the cu126 lane: onnxruntime-node needs CUDA 13, so a 580 or newer driver. Then paste the "
                           "install line again: it switches to the GPU build (about 3 GB)")
    assert D.guitar_device("cuda", None, torch_cuda="12.6")[0] == "cpu"   # known without the check
    assert D.guitar_device("cuda", False, "libcurand.so.10: cannot open shared object file", torch_cuda="13.2") == (
        "cpu", "the CUDA provider did not load: libcurand.so.10: cannot open shared object file")
    assert D.guitar_device("cuda", None, torch_cuda="13.2") == ("cuda", None)   # --quick: not checked
    assert D.guitar_device("cuda", True, torch_cuda="12.6") == ("cuda", None)   # CUDA 13 found anyway


def fake_smi(tmp_path, monkeypatch, body: str) -> None:
    folder = tmp_path / "smi"
    folder.mkdir(exist_ok=True)
    (folder / "nvidia-smi").write_text(f"#!/bin/sh\n{body}\n", encoding="ascii")
    (folder / "nvidia-smi").chmod(0o755)
    monkeypatch.setenv("PATH", f"{folder}{os.pathsep}{os.environ['PATH']}")


def test_nvidia_smi(tmp_path, monkeypatch):
    """The CI's stand-in line parsed; WSL's own nvidia-smi when PATH has none; a failure and an empty answer
    named."""
    monkeypatch.setattr(D, "WSL_NVIDIA_SMI", tmp_path / "wsl" / "nvidia-smi")
    monkeypatch.setenv("PATH", str(tmp_path / "nothing"))
    assert D.nvidia_smi() == (None, "nvidia-smi not found") and D.gpu_used_mb() is None
    (tmp_path / "wsl").mkdir()
    (tmp_path / "wsl" / "nvidia-smi").write_text('#!/bin/sh\necho "NVIDIA GeForce RTX 5070, 599.10, 12227, 12.0"\n')
    (tmp_path / "wsl" / "nvidia-smi").chmod(0o755)
    assert D.nvidia_smi() == ({"name": "NVIDIA GeForce RTX 5070", "driver": "599.10", "vram_mb": 12227,
                               "compute_cap": "12.0"}, None)
    fake_smi(tmp_path, monkeypatch, 'case "$1" in --query-gpu=memory.used) echo 3071;; '
                                    '*) echo "NVIDIA GeForce RTX 4070, 581.57, 12282, 8.9";; esac')
    assert D.nvidia_smi() == (RTX, None) and D.gpu_used_mb() == 3071
    fake_smi(tmp_path, monkeypatch, 'echo "NVIDIA-SMI has failed because it could not communicate with the NVIDIA '
                                    'driver." >&2; exit 9')
    assert D.nvidia_smi() == (None, "nvidia-smi failed (exit 9): NVIDIA-SMI has failed because it could not "
                                    "communicate with the NVIDIA driver.")
    fake_smi(tmp_path, monkeypatch, "exit 0")
    assert D.nvidia_smi() == (None, "nvidia-smi listed no GPU")


BLOCKED = ('echo "Failed to initialize NVML: GPU access blocked by the operating system"; exit 255')
FAILED = ("nvidia-smi failed, so CUDA cannot run: nvidia-smi failed (exit 255): Failed to initialize NVML: GPU access "
          "blocked by the operating system")


def test_an_nvidia_smi_that_fails_is_a_gpu_out_of_reach(tmp_path, monkeypatch):
    """An nvidia-smi that is there but fails (WSL's, after a driver or Windows update: exit 255, "GPU access blocked
    by the operating system"; or one that hangs) means a GPU CUDA cannot reach, not no GPU, on either lane; only a
    missing nvidia-smi or one that lists no GPU is "no NVIDIA GPU found"."""
    monkeypatch.setattr(D, "WSL_NVIDIA_SMI", tmp_path / "none")
    facts = {"torch": torch_info()}
    monkeypatch.setattr(D, "torch_report", lambda full=True: facts["torch"])
    real_path = D.nvidia_smi_path
    for cuda in ("13.2", None):   # a CUDA build that finds no usable GPU, and the cpu lane
        facts["torch"] = torch_info(cuda=cuda)
        monkeypatch.setattr(D, "nvidia_smi_path", real_path)
        monkeypatch.setattr(D, "SMI_TIMEOUT_S", 15.0)
        fake_smi(tmp_path, monkeypatch, BLOCKED)
        assert D.choose("auto") == ("cpu", FAILED, "nvidia-smi failed (exit 255): Failed to initialize NVML: GPU "
                                                   "access blocked by the operating system"), cuda
        fake_smi(tmp_path, monkeypatch, "exec sleep 5")
        monkeypatch.setattr(D, "SMI_TIMEOUT_S", 0.2)
        reason = D.choose_device("auto")[1]
        assert reason.startswith("nvidia-smi failed, so CUDA cannot run: nvidia-smi did not run (TimeoutExpired"), reason
        fake_smi(tmp_path, monkeypatch, "exit 0")   # it lists no GPU
        assert D.choose_device("auto") == ("cpu", "no NVIDIA GPU found"), cuda
        monkeypatch.setattr(D, "nvidia_smi_path", lambda: None)   # none at all
        assert D.choose_device("auto") == ("cpu", "no NVIDIA GPU found"), cuda


def test_doctor_gives_the_same_reason(tmp_path, monkeypatch):
    """report() hands nvidia-smi's failure to the device choice too: doctor's device line, its note and doctor.json
    say what choose_device says."""
    torch = pytest.importorskip("torch")
    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    monkeypatch.setattr(D, "WSL_NVIDIA_SMI", tmp_path / "none")
    fake_smi(tmp_path, monkeypatch, BLOCKED)
    monkeypatch.setattr(D, "components", lambda full=True: {})
    r = D.report(full=False)
    assert r["gpu"] is None and r["gpu_error"] == ("nvidia-smi failed (exit 255): Failed to initialize NVML: GPU access "
                                                   "blocked by the operating system")
    assert r["device"] == {"chosen": "cpu", "reason": FAILED} and f"CPU mode: {FAILED}" in r["notes"]
    assert f"device: CPU mode: {FAILED}" in D.summary(r)


def provider_install(tmp_path):
    models = tmp_path / "ac" / "models" / "fretformer-v2"
    models.mkdir(parents=True)
    for name, size in (("encoder_fp32.onnx", 900), ("beat_this_mel_fp32.onnx", 40), ("decoder_step_fp32.onnx", 500)):
        (models / name).write_bytes(b"\0" * size)
    return NS(node="/usr/bin/node", driver=tmp_path / "ac" / "ac_headless.cjs", models=tmp_path / "ac" / "models")


def test_the_autochart_cuda_check(tmp_path, monkeypatch):
    """One session on the smallest model with the CUDA library path, read from ORT's own placement log: ok with a
    node on CUDA; a provider that does not load names the missing library; a session that ran on the CPU alone is
    not ok."""
    inst = provider_install(tmp_path)
    monkeypatch.setattr(D, "PROVIDER_TIMEOUT_S", 120.0)
    import songcharter.engines.autochart as AC
    monkeypatch.setattr(AC, "cuda_library_path", lambda: ["/venv/nvidia/cu13/lib", "/usr/lib/wsl/lib"])
    monkeypatch.setenv("LD_LIBRARY_PATH", "/opt/mine")
    seen = {}

    def answer(stdout, stderr, code=0):
        def run(cmd, env, cwd, capture_output, text, timeout):
            seen.update(cmd=cmd, env=env, cwd=cwd, timeout=timeout)
            return subprocess.CompletedProcess(cmd, code, stdout, stderr)
        return run

    log = ("\x1b[0;36m2026-11-03 [V:onnxruntime:, session_state.cc:1347 VerifyEachNodeIsAssignedToAnEp] Node "
           "placements\x1b[m\n [V:onnxruntime:] Node(s) placed on [CUDAExecutionProvider]. Number of nodes: 9\n"
           " [V:onnxruntime:] Node(s) placed on [CPUExecutionProvider]. Number of nodes: 8\n")
    ok, detail = D.autochart_cuda(inst, run=answer('{"ok":true}\n', log))
    assert ok and detail == "CUDAExecutionProvider 9 nodes, CPUExecutionProvider 8 nodes (beat_this_mel_fp32.onnx)"
    assert seen["cmd"][:3] == ["/usr/bin/node", "-e", D.PROVIDER_PROBE]
    assert seen["cmd"][3:] == ["--", str(tmp_path / "ac" / "node_modules" / "onnxruntime-node"),
                               str(inst.models / "fretformer-v2" / "beat_this_mel_fp32.onnx")]
    assert seen["env"]["LD_LIBRARY_PATH"] == "/venv/nvidia/cu13/lib:/usr/lib/wsl/lib:/opt/mine"
    assert seen["cwd"] == str(tmp_path / "ac") and seen["timeout"] == 120.0
    failed = ("\x1b[1;31m2026-11-03 [E:onnxruntime:onnxruntime-node, provider_bridge_ort.cc:2146 Create] ... FAIL : "
              "Failed to load library /x/libonnxruntime_providers_cuda.so with error: libcurand.so.10: cannot open "
              "shared object file: No such file or directory\x1b[m\n")
    out = '{"ok":false,"error":"OrtSessionOptionsAppendExecutionProvider_Cuda: Failed to load shared library"}\n'
    assert D.autochart_cuda(inst, run=answer(out, failed, 1)) == (
        False, "libcurand.so.10: cannot open shared object file: No such file or directory")
    assert D.autochart_cuda(inst, run=answer(out, "", 1)) == (
        False, "OrtSessionOptionsAppendExecutionProvider_Cuda: Failed to load shared library")
    cpu = " Node(s) placed on [CPUExecutionProvider]. Number of nodes: 17\n"
    assert D.autochart_cuda(inst, run=answer('{"ok":true}\n', cpu)) == (
        False, "the session got CPUExecutionProvider 17 nodes, not CUDA (beat_this_mel_fp32.onnx)")

    def slow(cmd, **kw):
        raise subprocess.TimeoutExpired(cmd, kw["timeout"])

    assert D.autochart_cuda(inst, run=slow) == (False, "the check did not finish within 120 s")
    for f in (inst.models / "fretformer-v2").glob("*.onnx"):
        f.unlink()
    assert D.autochart_cuda(inst, run=answer("", ""))[0] is False


def test_memory_and_threads(tmp_path, monkeypatch):
    meminfo = tmp_path / "meminfo"
    meminfo.write_text("MemTotal:       16477184 kB\nMemFree:  1000 kB\nMemAvailable:   11534336 kB\n"
                       "SwapTotal:       8388608 kB\nSwapFree:        8126464 kB\n", encoding="ascii")
    monkeypatch.setattr(D, "MEMINFO", meminfo)
    assert D.memory() == {"total_mb": 16091, "available_mb": 11264, "swap_total_mb": 8192, "swap_free_mb": 7936}
    monkeypatch.setattr(D, "MEMINFO", tmp_path / "none")
    assert D.memory() is None
    monkeypatch.setattr(D.os, "cpu_count", lambda: 16)
    assert D.default_threads() == 15
    monkeypatch.setattr(D.os, "cpu_count", lambda: None)
    assert D.default_threads() == 1


def test_the_sampler_keeps_each_stages_extremes():
    """The thread samples memory every tick and the GPU every second tick, a sample also as each stage begins and
    ends; each stage keeps its lowest available RAM and its highest swap and GPU use; stop ends the thread."""
    avail = iter([9000, 8000, 3000, 7000] + [6000] * 1000)
    lock = threading.Lock()

    def read_memory():
        with lock:
            return {"available_mb": next(avail), "swap_total_mb": 8192, "swap_free_mb": 8000}

    gpu = []

    def read_gpu():
        gpu.append(1)
        return 2000 + 100 * len(gpu)

    s = D.Sampler(every=0.01, gpu_every=0.02, read_memory=read_memory, read_gpu=read_gpu)
    s.begin("separate")   # before start: the sample of its beginning
    s.start()
    deadline = time.time() + 10
    while len(gpu) < 2 and time.time() < deadline:
        time.sleep(0.01)
    got = s.end("separate")
    s.stop()
    assert not s._thread.is_alive()
    assert got["min_available_ram_mb"] == 3000 and got["max_swap_used_mb"] == 192 and got["max_gpu_used_mb"] >= 2200
    assert s.end("never begun") == {"min_available_ram_mb": None, "max_swap_used_mb": None, "max_gpu_used_mb": None}
    quiet = D.Sampler(read_memory=lambda: None, read_gpu=None)   # no /proc/meminfo, no nvidia-smi
    quiet.begin("decode")
    assert quiet.end("decode") == {"min_available_ram_mb": None, "max_swap_used_mb": None, "max_gpu_used_mb": None}


def test_a_slow_sample_is_not_credited_to_the_next_stage():
    """A GPU read that is still running when its stage ends (nvidia-smi can take up to a second in WSL) is dropped,
    not credited to the stage that began meanwhile: separation's 9000 MB must not become the drums' peak, nor that of
    a stage of the same name begun again."""

    def run(first: str, then: str) -> tuple[dict, dict, list]:
        vram = {"mb": 9000}
        reading, go = threading.Event(), threading.Event()
        reads = []

        def read_gpu():
            value = vram["mb"]   # taken now, returned late
            reading.set()
            go.wait(10)
            reads.append(value)
            return value

        s = D.Sampler(every=0.01, gpu_every=0.01, read_memory=lambda: None, read_gpu=read_gpu)
        s.begin(first)
        s.start()
        try:
            assert reading.wait(10)   # the thread holds the first stage's 9000 MB, not yet recorded
            vram["mb"] = 500
            before = s.end(first)
            s.begin(then)
            go.set()
            deadline = time.time() + 10
            while len(reads) < 3 and time.time() < deadline:   # the late read, then two of the next stage's own
                time.sleep(0.01)
            after = s.end(then)
        finally:
            go.set()
            s.stop()
        return before, after, reads

    for first, then in (("separate", "drums"), ("separate", "separate")):
        before, after, reads = run(first, then)
        assert reads[0] == 9000 and len(reads) >= 3, (first, then)
        assert before["max_gpu_used_mb"] is None, (first, then)   # its only GPU read came back after it ended
        assert after["max_gpu_used_mb"] == 500, (first, then)


def base_report(**over):
    """A report as report() makes it, of a machine with nothing wrong (not in WSL)."""
    r = {"wsl": None, "device": {"chosen": "cuda", "reason": None}, "guitar_device": "cuda", "guitar_reason": None,
         "ram": {"total_mb": 16000, "available_mb": 12000, "swap_total_mb": 8192, "swap_free_mb": 8192},
         "disk": {"home_free_mb": 50000, "windows_c_free_mb": None},
         "components": {k: {"ok": True} for k in ("ffmpeg", "node", "scan_chart", "autochart", "autochart_cuda",
                                                  "allin1", "demucs", "librosa", "matplotlib")}}
    r.update(over)
    return r


def wsl_part(memory_gb=12, total_mb=11776, **over):
    asked = None if memory_gb is None else memory_gb * 2 ** 30
    w = {"distro": "Ubuntu-26.04", "windows_build": "10.0.26100.1000", "interop": True, "windows_ram_mb": 16236,
         "wslconfig": {"path": "C:\\Users\\Jörg\\.wslconfig", "exists": True, "memory_bytes": asked,
                       "swap_bytes": 8 * 2 ** 30, "localhost_forwarding": None, "networking_mode": None},
         "memory_matches_config": D.memory_matches(total_mb, asked),
         "documents": {"registry": "%USERPROFILE%\\Documents", "windows": "C:\\Users\\Jörg\\Documents",
                       "linux": "/mnt/c/Users/Jörg/Documents"}}
    w.update(over)
    return w


def test_a_gpu_that_answers_on_a_cpu_lane_install_says_to_rerun_the_install():
    """A first install while nvidia-smi failed (GPU access blocked after a Windows update) took the cpu lane; once the
    GPU answers, doctor says so and what to do (the release gate's finding: it said only "no GPU")."""
    r = base_report(device={"chosen": "cpu", "reason": D.CPU_LANE}, guitar_device="cpu", guitar_reason="no GPU",
                    gpu=RTX)
    _, notes = D.findings(r)
    assert notes[:2] == ["CPU mode: this install's torch has no CUDA (the cpu lane)",
                         "NVIDIA GeForce RTX 4070 answers now, but this install has the CPU build: paste the install "
                         "line again, which picks the lane again (the GPU build needs NVIDIA driver 528 or newer, the "
                         "guitar on the GPU 580)"]
    for reason, gpu in ((D.CPU_LANE, None), (D.ASKED_CPU, RTX), (D.NO_GPU, None)):
        _, notes = D.findings(base_report(device={"chosen": "cpu", "reason": reason}, gpu=gpu))
        assert not any("answers now" in n for n in notes), (reason, notes)
    # installed with --lane cpu on purpose: pasting the install line again would move it to the GPU build, so no note
    # (the review of the gate fixes); the lane asked for comes from runtime.json's lane_reason, as install.sh writes it
    asked = {"lane": "cpu", "lane_reason": "asked for with --lane cpu"}
    _, notes = D.findings({**r, "install": asked})
    assert not any("answers now" in n for n in notes), notes
    _, notes = D.findings({**r, "install": {"lane": "cpu", "lane_reason": "nvidia-smi failed, so CUDA cannot run: x"}})
    assert any("answers now" in n for n in notes), notes


def test_the_report_reads_the_installs_lane(tmp_path, monkeypatch):
    """doctor's `install`: runtime.json's lane and lane_reason under $SONGCHARTER_HOME (the launcher's), else None."""
    monkeypatch.delenv("SONGCHARTER_HOME", raising=False)
    assert D._install() is None
    monkeypatch.setenv("SONGCHARTER_HOME", str(tmp_path))
    assert D._install() is None   # no runtime.json
    (tmp_path / "runtime").mkdir()
    (tmp_path / "runtime" / "runtime.json").write_text(json.dumps({"lane": "cpu", "lane_reason": "asked for with "
                                                                   "--lane cpu", "home": "/h"}), encoding="utf-8")
    assert D._install() == {"lane": "cpu", "lane_reason": "asked for with --lane cpu"}
    (tmp_path / "runtime" / "runtime.json").write_text("{", encoding="utf-8")
    assert D._install() is None


def test_wsl_memory_against_wslconfig():
    """11.5 GB in WSL with .wslconfig at 12 GB: the setting is in force, nothing to say. 7.8 GB with 12 GB asked
    for: WSL was not restarted since (a restart note), and under 11 GB, so allin1 stays out."""
    r = base_report(wsl=wsl_part(12, 11776), ram={"total_mb": 11776})
    assert D.findings(r) == ([], [])
    assert r["wsl"]["memory_matches_config"] is True
    r = base_report(wsl=wsl_part(12, 7987), ram={"total_mb": 7987})
    problems, notes = D.findings(r)
    assert problems == [] and r["wsl"]["memory_matches_config"] is False
    assert notes == ["WSL has 7.8 GB of memory, under 11 GB: allin1 is left out to save memory (the sections use the "
                     "librosa fallback)",
                     "WSL has 7.8 GB of memory, but .wslconfig asks for 12.0 GB: restart WSL. In Terminal "
                     "(right-click Start), type wsl --shutdown, then open Ubuntu again"]
    assert D.memory_matches(7987, None) is None and D.memory_matches(None, 2 ** 30) is None
    # WSL's memory=8GB shows about 7.8 GB, which is not under the 8 GB limit (units of 10^9 bytes); 7 GB is
    problems, _ = D.findings(base_report(wsl=wsl_part(None, 6900), ram={"total_mb": 6900}))
    assert problems == ["WSL has 6.7 GB of memory, under 8 GB: set memory in %UserProfile%\\.wslconfig (the install "
                        "writes it), then restart WSL: in Terminal (right-click Start), type wsl --shutdown, then "
                        "open Ubuntu again"]


def test_problems_and_notes():
    r = base_report(components={"ffmpeg": {"ok": False, "error": "ffmpeg not found: install it or `pip install "
                                                                 "imageio-ffmpeg`"},
                                "scan_chart": {"ok": False, "error": "node is not on PATH"},
                                "autochart": {"ok": False, "error": "node (install Node.js, or set SONGCHARTER_NODE)"},
                                "allin1": {"ok": False, "error": "no allin1 Python (set SONGCHARTER_ALLIN1_PYTHON)"}},
                    disk={"home_free_mb": 5000, "windows_c_free_mb": 5500},
                    device={"chosen": "cpu", "reason": D.CPU_LANE}, guitar_device="cpu", guitar_reason="no GPU")
    r["wsl"] = wsl_part(interop=False, windows_ram_mb=12000,
                        wslconfig={"path": "x", "exists": True, "memory_bytes": None, "swap_bytes": None,
                                   "localhost_forwarding": False, "networking_mode": None})
    r["ram"] = {"total_mb": 11776}
    problems, notes = D.findings(r)
    assert problems == [
        "ffmpeg not found: install it or `pip install imageio-ffmpeg`",
        "scan-chart cannot run: node is not on PATH",
        "autochart's engine is not ready (node (install Node.js, or set SONGCHARTER_NODE)): set SONGCHARTER_AUTOCHART "
        "to its install",
        f"only 4.9 GB free in WSL ({Path.home()}): a chart needs 6 GB",
        "only 5.4 GB free on C:, where WSL's disk grows: a chart needs 6 GB"]
    assert notes == [
        "CPU mode: this install's torch has no CUDA (the cpu lane)",
        "the guitar runs on the CPU: no GPU",
        "allin1 is not available (no allin1 Python (set SONGCHARTER_ALLIN1_PYTHON)): the sections use the librosa "
        "fallback",
        "Windows interop is off (cmd.exe does not run): no browser opens by itself, the Songs folder is not found by "
        "itself, and there is no Start-menu shortcut",
        "localhostForwarding is off in .wslconfig: the page opens on WSL's own address",
        "Windows has 11.7 GB of RAM, under 16 GB"]
    # mirrored networking shares localhost, so forwarding does not matter; 5800 MB (6.08 x 10^9 bytes) is not under 6 GB
    r["wsl"]["wslconfig"]["networking_mode"] = "mirrored"
    r["disk"] = {"home_free_mb": 5800, "windows_c_free_mb": None}
    problems, notes = D.findings(r)
    assert not any("localhostForwarding" in n for n in notes) and not any("free" in p for p in problems)
    # --quick: no allin1 probe, so the note comes from whether an allin1 Python is configured at all
    r = base_report()
    del r["components"]["allin1"]
    assert D.findings(r, allin1_python="/opt/allin1/bin/python") == ([], [])
    assert D.findings(r)[1] == ["no allin1 Python is configured: the sections use the librosa fallback"]


def test_the_report_runs_here(monkeypatch, tmp_path):
    """report() on this machine with the checks that need a GPU or a network answered by stand-ins: every key
    doctor.json promises, JSON as written, and `ok` exactly when there is no problem."""
    monkeypatch.setattr(D, "autochart_cuda", lambda install: (False, "libcurand.so.10: cannot open shared object"))
    monkeypatch.setattr(D, "_allin1", lambda: {"ok": False, "python": None, "error": "no allin1 Python"})
    monkeypatch.setattr(D, "nvidia_smi", lambda: NO_SMI)
    for full in (False, True):
        r = D.report(full=full)
        assert set(r) == {"songcharter", "written", "platform", "python", "wsl", "gpu", "gpu_error", "torch", "device",
                          "guitar_device", "guitar_reason", "cpu", "ram", "disk", "components", "install",
                          "problems", "notes", "ok"}
        assert set(r["components"]) == {"ffmpeg", "node", "scan_chart", "autochart", "demucs", "librosa",
                                        "matplotlib", "torchaudio"} | ({"autochart_cuda", "allin1"} if full else set())
        assert r["ok"] == (not r["problems"]) and json.loads(json.dumps(r)) == r
        assert r["gpu"] is None and r["gpu_error"] == "nvidia-smi not found"
        assert set(r["device"]) == {"chosen", "reason"} and set(r["disk"]) == {"home_free_mb", "windows_c_free_mb"}
        assert r["cpu"] == {"logical": os.cpu_count(), "threads_default": D.default_threads()}
        assert "\n".join(D.summary(r))   # a line per item; the command line prints them


def doctor_report(ok=True):
    r = base_report()
    r.update(songcharter="0.1.0", written="2026-11-03T18:00:00+0000", platform="Linux", gpu=RTX, gpu_error=None,
             python={"version": "3.13.18", "executable": sys.executable},
             torch={"installed": True, "version": "2.15.0+cu132", "cuda": "13.2", "cuda_works": True,
                    "cuda_error": None, "matmul": {"ok": True, "seconds": 0.01}},
             cpu={"logical": 16, "threads_default": 15}, problems=[] if ok else ["only 4.9 GB free in /home/x"],
             notes=["Windows has 11.7 GB of RAM, under 16 GB"], ok=ok)
    r["components"]["autochart_cuda"] = {"ok": True, "detail": "CUDAExecutionProvider 357 nodes"}
    return r


def test_the_doctor_command(tmp_path, monkeypatch, capsys):
    """A line per item, the verdict last; --json writes the report; exit 0 with no problem, 1 with problems, 2 for
    bad usage or a report that cannot be written, 3 for a bug; --quick asks for the quick report."""
    asked = []
    monkeypatch.setattr(D, "report", lambda full=True: asked.append(full) or doctor_report())
    assert main(["doctor", "--json", str(tmp_path / "out" / "doctor.json")]) == 0
    out = capsys.readouterr().out.splitlines()
    assert out[-1] == "doctor: OK" and "GPU: NVIDIA GeForce RTX 4070 (12.0 GB), driver 581.57, compute capability 8.9" \
        in out and "device: GPU (cuda)" in out and "guitar: on the GPU" in out
    assert "note: Windows has 11.7 GB of RAM, under 16 GB" in out
    assert json.loads((tmp_path / "out" / "doctor.json").read_text(encoding="utf-8")) == doctor_report() | {
        "written": "2026-11-03T18:00:00+0000"}
    assert not (tmp_path / "out" / "doctor.json.part").exists()
    assert main(["doctor", "--quick"]) == 0 and asked == [True, False]
    capsys.readouterr()
    monkeypatch.setattr(D, "report", lambda full=True: doctor_report(ok=False))
    assert main(["doctor"]) == 1
    out = capsys.readouterr().out.splitlines()
    assert out[-2:] == ["note: Windows has 11.7 GB of RAM, under 16 GB", "doctor: 1 problem"]
    assert "problem: only 4.9 GB free in /home/x" in out
    (tmp_path / "file").write_text("x")
    assert main(["doctor", "--json", str(tmp_path / "file" / "doctor.json")]) == 2
    assert "songcharter: error: cannot write" in capsys.readouterr().err
    with pytest.raises(SystemExit) as e:
        main(["doctor", "--bogus"])
    assert e.value.code == 2

    def bug(full=True):
        raise KeyError("a bug")

    monkeypatch.setattr(D, "report", bug)
    assert main(["doctor"]) == 3
    assert "KeyError: 'a bug'" in capsys.readouterr().err


@pytest.mark.parametrize("present", [True, False])
def test_doctor_lists_torchaudio(monkeypatch, present):
    """M5-08 (M4-10's deferred item): torchaudio, which the lyrics aligner needs and NOTICE.txt lists, is among
    doctor's components, its version from this Python's environment (the main one, from the launcher); missing, it
    is said as missing, and is not a problem (the lyrics are optional)."""
    import importlib.metadata
    import importlib.util
    find, version = importlib.util.find_spec, importlib.metadata.version

    def find_spec(name, *a, **kw):
        if name == "torchaudio":
            return find("json") if present else None   # any spec: _module asks only whether there is one
        return find(name, *a, **kw)

    def metadata_version(dist):
        if dist == "torchaudio":
            if not present:
                raise importlib.metadata.PackageNotFoundError(dist)
            return "2.11.1+cpu"
        return version(dist)

    monkeypatch.setattr(importlib.util, "find_spec", find_spec)
    monkeypatch.setattr(importlib.metadata, "version", metadata_version)
    comps = D.components(full=False)
    assert comps["torchaudio"] == ({"ok": True, "version": "2.11.1+cpu"} if present else {"ok": False, "version": None})
    r = base_report()
    r["components"]["torchaudio"] = comps["torchaudio"]
    assert D.findings(r) == ([], [])
    r.update(songcharter="0.1.0", platform="Linux", python={"version": "3.13.17", "executable": "py"}, gpu=None,
             gpu_error="nvidia-smi not found", torch={}, cpu={})
    want = "torchaudio: ok, 2.11.1+cpu" if present else "torchaudio: missing: not installed"
    assert [line for line in D.summary(r) if line.startswith("torchaudio")] == [want]


def test_doctor_says_the_cuda_provider_is_not_needed_when_the_guitar_runs_on_the_cpu():
    """On the cpu lane (or with no GPU) the provider's load error is expected: doctor says it is not needed, so the
    friend reads no error; with the GPU chosen, a provider that does not load is shown as it is."""
    failed = {"ok": False, "detail": "libcurand.so.10: cannot open shared object file"}
    r = {"songcharter": "0", "python": {"version": "3.13", "executable": "py"}, "torch": {}, "components":
         {"autochart_cuda": failed}, "device": {"chosen": "cpu", "reason": "no NVIDIA GPU found"},
         "guitar_device": "cpu", "guitar_reason": "no GPU"}
    lines = D.summary(r)
    assert "autochart's CUDA provider: not needed: the guitar runs on the CPU (no NVIDIA GPU found)" in lines
    assert not any("does not load" in line for line in lines)
    r["device"], r["guitar_device"] = {"chosen": "cuda", "reason": "a GPU"}, "cpu"
    assert ("autochart's CUDA provider: does not load: libcurand.so.10: cannot open shared object file"
            in D.summary(r))
