"""Where a chart runs, and why: the GPU, CUDA in torch and in autochart's onnxruntime-node, memory, disk and the
components, for `songcharter doctor` (its doctor.json is read by the install, the UI and the diagnostics), and the
pipeline's memory sampler (M4-02).

    device.choose_device("auto")         # ("cuda", None), or ("cpu", "no NVIDIA GPU found")
    device.guitar_device("cuda", True)   # ("cuda", None): autochart's CUDA provider loaded too
    device.report()                      # doctor.json's content; device.summary(report): a line per item

  * **Two devices.** torch's (separation, drums, allin1's own Python) and the guitar's: autochart's engine runs under
    onnxruntime-node, whose Linux CUDA provider needs CUDA 13 libraries, which only the cu132 lane's wheels bring (and
    a 580 or newer driver). So the guitar can be on the CPU while torch is on the GPU, each with its reason.
  * **The device "auto" takes** (`choose_device`) is the pipeline's (Engines.device calls it): CUDA only when a CUDA
    kernel runs (separate.cuda_works), else the CPU with one sentence for why: asked for, no GPU at all, a torch with
    no CUDA (the cpu lane), CUDA that did not run on the GPU nvidia-smi names (and the error), or an nvidia-smi that
    is there but fails (WSL's comes with the Windows driver, so a GPU is there: "Failed to initialize NVML: GPU access
    blocked by the operating system" after a driver or Windows update, or a timeout). Only a missing nvidia-smi, or
    one that lists no GPU, means no GPU.
  * **Sizes.** The report gives MB (2^20 bytes). The limits (6 GB free, 8 and 11 GB of WSL memory, 16 GB of Windows
    RAM) are in units of 10^9 bytes, which leaves room for the few percent firmware and the kernel keep: a 16 GB PC
    reports about 15.9 GB of RAM, and WSL with memory=8GB about 7.8 GB.
  * **Read-only.** Nothing here installs, downloads or changes anything; the Windows side goes through wsl.py.
"""
from __future__ import annotations

import importlib.metadata
import importlib.util
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, Callable, NamedTuple

ASKED_CPU = "asked for the CPU"
NO_GPU = "no NVIDIA GPU found"
CPU_LANE = "this install's torch has no CUDA (the cpu lane)"
NO_TORCH = "torch is not installed"
SMI_FAILED = "nvidia-smi failed, so CUDA cannot run"   # nvidia-smi is there but fails: a GPU it cannot reach
SMI_MISSING = "nvidia-smi not found"
SMI_NO_GPU = "nvidia-smi listed no GPU"
GUITAR_NO_GPU = "no GPU"
ASKED_LANE = "asked for with --lane"   # how runtime.json's lane_reason begins when the install was asked for a lane
                                       # (install.sh's choose_lane: "asked for with --lane cpu")
GUITAR_CU126 = ("the cu126 lane: onnxruntime-node needs CUDA 13, so a 580 or newer driver. Then paste the install line "
                "again: it switches to the GPU build (about 3 GB)")
WSL_NVIDIA_SMI = Path("/usr/lib/wsl/lib/nvidia-smi")   # WSL's, from the Windows driver [doc: NVIDIA's WSL guide]
MEMINFO = Path("/proc/meminfo")
SMI_QUERY = "name,driver_version,memory.total,compute_cap"
SMI_TIMEOUT_S = 15.0
PROVIDER_TIMEOUT_S = 120.0
GB = 10 ** 9                 # the limits' unit (module docstring)
MIN_FREE = 6 * GB            # free disk in WSL and on C:, below which `ok` is false
MIN_WSL_MEMORY = 8 * GB      # WSL's memory below which `ok` is false
ALLIN1_MEMORY = 11 * GB      # WSL's memory below which the install leaves allin1 out (M4-03's memory rule)
MIN_WINDOWS_RAM = 16 * GB    # Windows' RAM below which a note says so
MATCH = 0.10                 # WSL's MemTotal within 10 % of .wslconfig's memory: the setting is in force
MB = 2 ** 20
# one onnxruntime-node session asking for the CUDA provider; ORT's verbose log (stderr) says where its nodes went
PROVIDER_PROBE = r"""
const ort = require(process.argv[1]);
ort.InferenceSession.create(process.argv[2], { executionProviders: ["cuda"], logSeverityLevel: 0, logVerbosityLevel: 0 })
  .then(() => console.log(JSON.stringify({ ok: true })))
  .catch((e) => { console.log(JSON.stringify({ ok: false, error: String((e && e.message) || e).split("\n")[0] }));
                  process.exit(1); });
"""
PLACED = re.compile(r"(?:All nodes|Node\(s\)) placed on \[([A-Za-z]+)\]\. Number of nodes: (\d+)")
LOAD_ERROR = re.compile(r"Failed to load library \S+ with error: ([^\n\x1b]+)")


# ------------------------------------------------------------------------------------------------ the GPU and torch

def nvidia_smi_path() -> str | None:
    """nvidia-smi from PATH, else WSL's /usr/lib/wsl/lib/nvidia-smi, else None."""
    found = shutil.which("nvidia-smi")
    if found:
        return found
    return str(WSL_NVIDIA_SMI) if WSL_NVIDIA_SMI.is_file() else None


def _smi(fields: str) -> tuple[list[str] | None, str | None]:
    """nvidia-smi's first GPU line for the fields (csv, no header, no units) split at commas, or (None, why)."""
    exe = nvidia_smi_path()
    if exe is None:
        return None, SMI_MISSING
    try:
        proc = subprocess.run([exe, f"--query-gpu={fields}", "--format=csv,noheader,nounits"], capture_output=True,
                              text=True, timeout=SMI_TIMEOUT_S, stdin=subprocess.DEVNULL)
    except (OSError, subprocess.SubprocessError) as e:
        return None, f"nvidia-smi did not run ({type(e).__name__}: {e})"
    if proc.returncode != 0:
        tail = " ".join((proc.stderr or proc.stdout or "").split())[:200]
        return None, f"nvidia-smi failed (exit {proc.returncode}){': ' + tail if tail else ''}"
    lines = [line for line in (proc.stdout or "").splitlines() if line.strip()]
    if not lines:
        return None, SMI_NO_GPU
    return [x.strip() for x in lines[0].split(",")], None


def _number(text: str) -> float | None:
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def nvidia_smi() -> tuple[dict | None, str | None]:
    """The first NVIDIA GPU as nvidia-smi names it: ({"name", "driver", "vram_mb", "compute_cap"}, None), or
    (None, why)."""
    got, why = _smi(SMI_QUERY)
    if got is None:
        return None, why
    if len(got) < 4 or not got[0]:
        return None, f"nvidia-smi printed {', '.join(got)!r}, not {SMI_QUERY}"
    vram = _number(got[2])
    return {"name": got[0], "driver": got[1] or None, "vram_mb": None if vram is None else int(vram),
            "compute_cap": got[3] or None}, None


def gpu_used_mb() -> int | None:
    """The first GPU's memory in use, whole system (nvidia-smi's memory.used), in MB; None without nvidia-smi."""
    got, _ = _smi("memory.used")
    value = _number(got[0]) if got else None
    return None if value is None else int(value)


def _first_line(e: BaseException) -> str:
    return f"{type(e).__name__}: {(str(e).strip().splitlines() or [''])[0][:200]}"


def torch_report(full: bool = True) -> dict:
    """torch here: {"installed", "version", "cuda" (torch.version.cuda: None on the cpu lane), "cuda_works" and
    "cuda_error" (separate.cuda_works), "arch_list", "device_name", "capability", "matmul"}. `full` also runs a
    512x512 matmul on CUDA when a kernel runs: {"ok", "seconds"} or {"ok": False, "error"}."""
    try:
        import torch
    except Exception as e:  # noqa: BLE001  absent or broken: either way no torch to run on
        return {"installed": False, "error": _first_line(e), "cuda": None, "cuda_works": False, "cuda_error": None}
    from .separate import cuda_works
    works, error = cuda_works()
    out: dict[str, Any] = {"installed": True, "version": torch.__version__, "cuda": torch.version.cuda,
                           "cuda_works": works, "cuda_error": error, "arch_list": [], "device_name": None,
                           "capability": None, "matmul": None}
    try:
        if torch.cuda.is_available():
            out["arch_list"] = list(torch.cuda.get_arch_list())
            out["device_name"] = torch.cuda.get_device_name(0)
            major, minor = torch.cuda.get_device_capability(0)
            out["capability"] = f"sm_{major}{minor}"
    except Exception:  # noqa: BLE001  details only: what cuda_works found decides
        pass
    if works and full:
        t0 = time.perf_counter()
        try:
            x = torch.ones(512, 512, device="cuda")
            (x @ x).sum().item()
            out["matmul"] = {"ok": True, "seconds": round(time.perf_counter() - t0, 3)}
        except Exception as e:  # noqa: BLE001
            out["matmul"] = {"ok": False, "error": _first_line(e)}
    return out


def _unavailable_why() -> str:
    """Why torch's CUDA is not available on a GPU nvidia-smi sees (a driver too old for this CUDA, say)."""
    try:
        import torch
        torch.cuda.init()
    except Exception as e:  # noqa: BLE001  its message is the answer
        return _first_line(e)
    return "torch.cuda.is_available() is false"


class Choice(NamedTuple):
    device: str               # "cuda" or "cpu"
    reason: str | None        # why the CPU (one sentence), None for CUDA
    error: str | None         # the CUDA error when CUDA is there but did not run, else None


def _decide(asked: str, torch_info: dict, gpu: dict | None, gpu_error: str | None = None) -> Choice:
    """The device for `asked` from torch's report, nvidia-smi's GPU and, when it has none, why (nvidia_smi())."""
    if asked == "cpu":
        return Choice("cpu", ASKED_CPU, None)
    if asked == "cuda":   # asked for: Engines.missing has named a CUDA that does not run
        return Choice("cuda", None, None)
    if not torch_info.get("installed"):
        return Choice("cpu", NO_TORCH, None)
    if torch_info.get("cuda_works"):
        return Choice("cuda", None, None)
    error = torch_info.get("cuda_error")
    if error is None:   # CUDA not available at all: no GPU, the cpu lane, or a driver this torch cannot use
        if gpu is None and gpu_error not in (None, SMI_MISSING, SMI_NO_GPU):   # a GPU nvidia-smi cannot reach
            return Choice("cpu", f"{SMI_FAILED}: {gpu_error}", gpu_error)
        if torch_info.get("cuda") is None:
            return Choice("cpu", NO_GPU if gpu is None else CPU_LANE, None)
        if gpu is None:
            return Choice("cpu", NO_GPU, None)
        error = _unavailable_why()
    name = (gpu or {}).get("name") or torch_info.get("device_name") or "the GPU"
    return Choice("cpu", f"CUDA did not run on {name}: {error}", error)


def choose(asked: str) -> Choice:
    """choose_device's answer with the CUDA error itself (for the pipeline's warning)."""
    if asked not in ("auto", "cpu", "cuda"):
        raise ValueError(f"device is auto, cpu or cuda, not {asked!r}")
    if asked != "auto":
        return _decide(asked, {}, None)
    t = torch_report(full=False)
    gpu, gpu_error = (None, None) if t.get("cuda_works") else nvidia_smi()
    return _decide(asked, t, gpu, gpu_error)


def choose_device(asked: str) -> tuple[str, str | None]:
    """The torch device for `asked` ("auto", "cpu", "cuda"), as the pipeline takes it, and for the CPU the reason:
    "asked for the CPU", "no NVIDIA GPU found", "this install's torch has no CUDA (the cpu lane)", "CUDA did not
    run on <name>: <error>" or "nvidia-smi failed, so CUDA cannot run: <its error>". "auto" is CUDA only when a CUDA
    kernel runs here (separate.cuda_works)."""
    c = choose(asked)
    return c.device, c.reason


def guitar_device(torch_device: str, autochart_ok: bool | None, detail: str | None = None, *,
                  torch_cuda: str | None = None) -> tuple[str, str | None]:
    """Where autochart's transcriber runs: "cuda" when torch runs on CUDA (`torch_device`) and onnxruntime-node's
    CUDA provider loaded (`autochart_ok`, `detail`: autochart_cuda's answer), else "cpu" with why: "no GPU", the cu126
    lane (`torch_cuda` 12.x: the provider needs CUDA 13), or "the CUDA provider did not load: <detail>". A provider not
    checked (`autochart_ok` None: doctor --quick) counts as loading, as the pipeline tries CUDA and falls back by
    itself."""
    if torch_device != "cuda":
        return "cpu", GUITAR_NO_GPU
    if autochart_ok:
        return "cuda", None
    if (torch_cuda or "").startswith("12."):
        return "cpu", GUITAR_CU126
    if autochart_ok is None:
        return "cuda", None
    return "cpu", f"the CUDA provider did not load: {detail or 'no detail'}"


def autochart_cuda(install, *, run: Callable[..., subprocess.CompletedProcess] = subprocess.run,
                   timeout_s: float = PROVIDER_TIMEOUT_S) -> tuple[bool, str]:
    """Whether onnxruntime-node's CUDA provider loads for autochart's engine (`install`: engines.autochart.Install):
    one session with executionProviders ["cuda"] on the smallest .onnx file in the Fretformer 2 models, in a node
    child whose LD_LIBRARY_PATH starts with engines.autochart.cuda_library_path(), as a guitar take's has. (ok,
    detail): ok when ORT placed a node on CUDA; the detail names the providers it got, or why it did not load."""
    from .engines.autochart import cuda_environment
    folder = Path(install.models) / "fretformer-v2"
    try:
        models = sorted(folder.glob("*.onnx"), key=lambda p: (p.stat().st_size, p.name))
    except OSError:
        models = []
    if not models:
        return False, f"no .onnx model in {folder}"
    root = Path(install.driver).parent
    try:
        proc = run([install.node, "-e", PROVIDER_PROBE, "--", str(root / "node_modules" / "onnxruntime-node"),
                    str(models[0])], env=cuda_environment(os.environ), cwd=str(root), capture_output=True,
                   text=True, timeout=timeout_s)
    except subprocess.TimeoutExpired:
        return False, f"the check did not finish within {timeout_s:.0f} s"
    except OSError as e:
        return False, f"node did not run ({type(e).__name__}: {e})"
    err = re.sub(r"\x1b\[[0-9;]*m", "", proc.stderr or "")
    placed: dict[str, int] = {}
    for provider, n in PLACED.findall(err):
        placed[provider] = placed.get(provider, 0) + int(n)
    shown = ", ".join(f"{p} {n} nodes" for p, n in placed.items())
    if placed.get("CUDAExecutionProvider"):
        return True, f"{shown} ({models[0].name})"
    try:
        said = json.loads((proc.stdout or "").strip().splitlines()[-1])
    except (ValueError, IndexError):
        said = {}
    load = LOAD_ERROR.search(err)
    if load:
        return False, load.group(1).strip()
    if said.get("ok"):
        return False, f"the session got {shown or 'no provider it named'}, not CUDA ({models[0].name})"
    return False, said.get("error") or f"node exited {proc.returncode}: {' '.join(err.split())[-200:]}"


# ------------------------------------------------------------------------------------------------ the machine

def default_threads() -> int:
    """The UI's thread count on the CPU: all logical cores but one (the command line keeps the libraries' own
    default, so no chart moves)."""
    return max(1, (os.cpu_count() or 1) - 1)


def memory() -> dict | None:
    """MemTotal, MemAvailable, SwapTotal and SwapFree from /proc/meminfo in MB ({"total_mb", "available_mb",
    "swap_total_mb", "swap_free_mb"}); None where there is no /proc/meminfo."""
    try:
        text = MEMINFO.read_text(encoding="ascii", errors="replace")
    except OSError:
        return None
    kb = {}
    for line in text.splitlines():
        key, _, rest = line.partition(":")
        parts = rest.split()
        if parts and parts[0].isdigit():
            kb[key.strip()] = int(parts[0])
    mb = {k: (kb[k] // 1024 if k in kb else None) for k in ("MemTotal", "MemAvailable", "SwapTotal", "SwapFree")}
    return {"total_mb": mb["MemTotal"], "available_mb": mb["MemAvailable"], "swap_total_mb": mb["SwapTotal"],
            "swap_free_mb": mb["SwapFree"]}


def _free_mb(path: Path) -> int | None:
    try:
        return shutil.disk_usage(path).free // MB
    except OSError:
        return None


class Sampler:
    """Samples the whole system's memory (children included) on a daemon thread: /proc/meminfo every `every` s and,
    when nvidia-smi exists, the GPU's memory in use every `gpu_every` s. Each stage (`begin`, then `end`, which
    returns its record) keeps min_available_ram_mb, max_swap_used_mb and max_gpu_used_mb (None for what was not
    sampled). A sample is taken as each stage begins and ends, so even a short stage has one. A sample counts for the
    stage that was running when it started: one whose stage ended while it read (nvidia-smi can take a second in
    WSL) is dropped, never credited to the next stage."""

    def __init__(self, every: float = 1.0, gpu_every: float = 2.0, read_memory: Callable[[], dict | None] = memory,
                 read_gpu: Callable[[], int | None] | None = None):
        self.every = every
        self.gpu_ratio = max(1, round(gpu_every / every))
        self.read_memory = read_memory
        self.read_gpu = read_gpu if read_gpu is not None else (gpu_used_mb if nvidia_smi_path() else None)
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._stage: str | None = None
        self._generation = 0   # one more for each stage that begins or ends: a sample from an older one is dropped
        self._stats: dict[str, dict] = {}

    def start(self) -> None:
        self._thread = threading.Thread(target=self._loop, name="songcharter-sampler", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=10)

    def begin(self, stage: str) -> None:
        with self._lock:
            self._stage = stage
            self._generation += 1
            self._stats[stage] = {"min_available_ram_mb": None, "max_swap_used_mb": None, "max_gpu_used_mb": None}
        self._sample(gpu=False)

    def end(self, stage: str) -> dict:
        self._sample(gpu=False)
        with self._lock:
            if self._stage == stage:
                self._stage = None
                self._generation += 1
            return dict(self._stats.get(stage) or {"min_available_ram_mb": None, "max_swap_used_mb": None,
                                                     "max_gpu_used_mb": None})

    def _sample(self, gpu: bool) -> None:
        with self._lock:   # the stage this sample is for, noted before the (slow) reads
            stage, generation = self._stage, self._generation
        if stage is None:
            return
        try:
            m = self.read_memory()
            g = self.read_gpu() if gpu and self.read_gpu is not None else None
        except Exception:  # noqa: BLE001  a sample that fails is skipped: it only informs
            return
        with self._lock:
            s = self._stats.get(stage)
            if s is None or self._generation != generation:   # its stage ended while it read: dropped
                return
            if m and m.get("available_mb") is not None:
                low = s["min_available_ram_mb"]
                s["min_available_ram_mb"] = m["available_mb"] if low is None else min(low, m["available_mb"])
            if m and m.get("swap_total_mb") is not None and m.get("swap_free_mb") is not None:
                used, high = m["swap_total_mb"] - m["swap_free_mb"], s["max_swap_used_mb"]
                s["max_swap_used_mb"] = used if high is None else max(high, used)
            if g is not None:
                high = s["max_gpu_used_mb"]
                s["max_gpu_used_mb"] = g if high is None else max(high, g)

    def _loop(self) -> None:
        n = 0
        while not self._stop.wait(self.every):
            n += 1
            self._sample(gpu=n % self.gpu_ratio == 0)


# ------------------------------------------------------------------------------------------------ the components

def _version(dist: str) -> str | None:
    try:
        return importlib.metadata.version(dist)
    except importlib.metadata.PackageNotFoundError:
        return None


def _module(name: str, dist: str | None = None) -> dict:
    try:
        found = importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        found = False
    return {"ok": found, "version": _version(dist or name) if found else None}


def _ffmpeg() -> dict:
    from . import audio
    from .errors import ToolError
    try:
        exe = audio.ffmpeg_exe()
        proc = subprocess.run([exe, "-hide_banner", "-version"], capture_output=True, text=True, timeout=30,
                              stdin=subprocess.DEVNULL)
    except (ToolError, OSError, subprocess.SubprocessError) as e:
        return {"ok": False, "error": str(e)}
    if proc.returncode != 0:
        return {"ok": False, "path": exe, "error": f"{exe} -version exited {proc.returncode}"}
    first = (proc.stdout or "").splitlines()[0] if proc.stdout else ""
    m = re.match(r"ffmpeg version (\S+)", first)
    return {"ok": True, "path": exe, "version": m.group(1) if m else None}


def _node() -> dict:
    exe = os.environ.get("SONGCHARTER_NODE") or shutil.which("node")
    if not exe:
        return {"ok": False, "error": "node not found (install Node.js, or set SONGCHARTER_NODE)"}
    try:
        proc = subprocess.run([exe, "--version"], capture_output=True, text=True, timeout=30, stdin=subprocess.DEVNULL)
    except (OSError, subprocess.SubprocessError) as e:
        return {"ok": False, "path": exe, "error": f"{exe} did not run ({type(e).__name__}: {e})"}
    if proc.returncode != 0:
        return {"ok": False, "path": exe, "error": f"{exe} --version exited {proc.returncode}"}
    return {"ok": True, "path": exe, "version": (proc.stdout or "").strip() or None}


def _scan_chart() -> dict:
    from .assemble import find_scan_chart
    command, version = find_scan_chart()
    if command is None:
        return {"ok": False, "error": version}
    return {"ok": True, "path": command[-1], "version": version}


def _allin1() -> dict:
    from .engines import sections
    python = sections.allin1_python(sections.Settings())
    if python is None:
        return {"ok": False, "python": None, "error": f"no allin1 Python (set {sections.ENV_PYTHON})"}
    try:
        probe = sections.probe(python)   # its "python" is that Python's version
        return {**probe, "ok": True, "python": python, "python_version": probe.get("python")}
    except (sections.Allin1Error, OSError, ValueError) as e:
        return {"ok": False, "python": python, "error": str(e).splitlines()[0] if str(e) else type(e).__name__}


def components(full: bool = True) -> dict:
    """What a chart needs, each {"ok", ...}: ffmpeg, node, scan_chart, autochart (and, with `full`, autochart_cuda:
    autochart_cuda(), and allin1: its Python's probe), demucs, librosa, matplotlib, torchaudio (the lyrics aligner's,
    from this Python's environment: M5-08)."""
    from .engines import autochart
    out = {"ffmpeg": _ffmpeg(), "node": _node(), "scan_chart": _scan_chart()}
    install = None
    try:
        install = autochart.find_install()
        out["autochart"] = {"ok": True, "root": str(install.driver.parent),
                            "engine_version": autochart.install_key(install).get("engineVersion")}
    except FileNotFoundError as e:
        out["autochart"] = {"ok": False, "error": str(e).removeprefix("autochart engine not ready: ")}
    if full:
        if install is None:
            out["autochart_cuda"] = {"ok": False, "detail": "autochart's engine is not installed"}
        else:
            ok, detail = autochart_cuda(install)
            out["autochart_cuda"] = {"ok": ok, "detail": detail}
        out["allin1"] = _allin1()
    out.update(demucs=_module("demucs"), librosa=_module("librosa"), matplotlib=_module("matplotlib"),
               torchaudio=_module("torchaudio"))
    return out


# ------------------------------------------------------------------------------------------------ the report

def memory_matches(total_mb: int | None, memory_bytes: int | None) -> bool | None:
    """Whether WSL's MemTotal is within 10 % of .wslconfig's memory, so that setting is in force (WSL was restarted
    since it was written); None when either is unknown."""
    if not (total_mb and memory_bytes):
        return None
    return abs(total_mb * MB - memory_bytes) <= MATCH * memory_bytes


def _wsl(ram: dict | None) -> dict:
    from . import wsl
    interop = wsl.interop_ok()
    config = wsl.wslconfig() if interop else {"path": None, "exists": False, **wsl.parse_wslconfig("")}
    ram_bytes = wsl.windows_ram_bytes(config) if interop else None
    raw = wsl.registry_shell_folder("Personal") if interop else None
    expanded = wsl.expand(raw) if raw else None
    linux = wsl.to_linux(expanded) if expanded else None
    return {"distro": wsl.distro(), "windows_build": wsl.windows_build() if interop else None, "interop": interop,
            "windows_ram_mb": None if ram_bytes is None else ram_bytes // MB, "wslconfig": config,
            "memory_matches_config": memory_matches((ram or {}).get("total_mb"), config.get("memory_bytes")),
            "documents": {"registry": raw, "windows": expanded,
                          "linux": str(linux) if linux is not None and linux.is_dir() else None}}


def _gb(mb: float | None) -> str:
    return "?" if mb is None else f"{mb / 1024:.1f}"


def findings(r: dict, allin1_python: str | None = None) -> tuple[list[str], list[str]]:
    """doctor's problems (each makes `ok` false) and notes (shown, not failing) for a report `r` (report()'s, but for
    these). `allin1_python`: whether an allin1 Python is configured, for a report without allin1's probe (--quick)."""
    problems, notes = [], []
    comps = r.get("components") or {}
    for key, text in (("ffmpeg", "{}"), ("scan_chart", "scan-chart cannot run: {}"),
                      ("autochart", "autochart's engine is not ready ({}): set SONGCHARTER_AUTOCHART to its install")):
        c = comps.get(key)
        if c is not None and not c.get("ok"):
            problems.append(text.format(c.get("error") or "not found"))
    disk = r.get("disk") or {}
    for key, where in (("home_free_mb", f"in WSL ({Path.home()})" if r.get("wsl") else f"in {Path.home()}"),
                       ("windows_c_free_mb", "on C:, where WSL's disk grows")):
        free = disk.get(key)
        if free is not None and free * MB < MIN_FREE:
            problems.append(f"only {_gb(free)} GB free {where}: a chart needs {MIN_FREE // GB} GB")
    w = r.get("wsl")
    total = (r.get("ram") or {}).get("total_mb")
    if w and total is not None and total * MB < MIN_WSL_MEMORY:
        problems.append(f"WSL has {_gb(total)} GB of memory, under {MIN_WSL_MEMORY // GB} GB: set memory in "
                        "%UserProfile%\\.wslconfig (the install writes it), then restart WSL: in Terminal "
                        "(right-click Start), type wsl --shutdown, then open Ubuntu again")

    dev = r.get("device") or {}
    if dev.get("chosen") == "cpu":
        notes.append(f"CPU mode: {dev.get('reason')}")
    asked = str((r.get("install") or {}).get("lane_reason") or "").startswith(ASKED_LANE)   # --lane cpu, on purpose
    if dev.get("reason") == CPU_LANE and r.get("gpu") and not asked:   # installed with no GPU in reach, say
        notes.append(f"{r['gpu'].get('name') or 'an NVIDIA GPU'} answers now, but this install has the CPU build: "
                     "paste the install line again, which picks the lane again (the GPU build needs NVIDIA driver "
                     "528 or newer, the guitar on the GPU 580)")
    if r.get("guitar_device") == "cpu":
        notes.append(f"the guitar runs on the CPU: {r.get('guitar_reason')}")
    a = comps.get("allin1")
    if a is not None and not a.get("ok"):
        notes.append(f"allin1 is not available ({a.get('error')}): the sections use the librosa fallback")
    elif a is None and allin1_python is None:
        notes.append("no allin1 Python is configured: the sections use the librosa fallback")
    elif total is not None and dev.get("chosen") != "cuda" and not (w and total * MB < ALLIN1_MEMORY):
        from .engines import sections   # the skip's own rule (M8-05): MemTotal, not swap nor what is free now
        longest = sections.longest_s(total)
        notes.append(f"allin1 analyses songs up to about {int(longest // 60)}:{int(longest % 60):02d} on the CPU "
                     f"with this PC's {total / 1024:.1f} GiB of memory; a longer song gets the librosa "
                     "sections (the bar lines and the tempo's halving test from a simpler analysis)")
    if w:
        if total is not None and total * MB < ALLIN1_MEMORY:
            notes.append(f"WSL has {_gb(total)} GB of memory, under {ALLIN1_MEMORY // GB} GB: allin1 is left out to "
                         "save memory (the sections use the librosa fallback)")
        config = w.get("wslconfig") or {}
        if w.get("memory_matches_config") is False:
            notes.append(f"WSL has {_gb(total)} GB of memory, but .wslconfig asks for "
                         f"{_gb((config.get('memory_bytes') or 0) / MB)} GB: restart WSL. In Terminal "
                         "(right-click Start), type wsl --shutdown, then open Ubuntu again")
        if not w.get("interop"):
            notes.append("Windows interop is off (cmd.exe does not run): no browser opens by itself, the Songs folder "
                         "is not found by itself, and there is no Start-menu shortcut")
        if config.get("localhost_forwarding") is False and (config.get("networking_mode") or "").lower() != "mirrored":
            notes.append("localhostForwarding is off in .wslconfig: the page opens on WSL's own address")
        ram = w.get("windows_ram_mb")
        if ram is not None and ram * MB < MIN_WINDOWS_RAM:
            notes.append(f"Windows has {_gb(ram)} GB of RAM, under {MIN_WINDOWS_RAM // GB} GB")
    return problems, notes


def report(full: bool = True) -> dict:
    """doctor.json: the machine, the GPU, torch, the device "auto" takes and the guitar's, memory, disk, the
    components, then the problems (each makes `ok` false) and the notes. `full` (doctor without --quick) also runs
    the matmul, autochart's CUDA provider check and allin1's probe."""
    from . import __version__, wsl
    ram = memory()
    gpu, gpu_error = nvidia_smi()
    t = torch_report(full)
    chosen = _decide("auto", t, gpu, gpu_error)
    comps = components(full)
    ac = comps.get("autochart_cuda")
    gdev, greason = guitar_device(chosen.device, ac["ok"] if ac else None, ac.get("detail") if ac else None,
                                  torch_cuda=t.get("cuda"))
    in_wsl = wsl.is_wsl()
    r: dict[str, Any] = {
        "songcharter": __version__, "written": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "platform": platform.platform(),
        "python": {"version": platform.python_version(), "executable": sys.executable},
        "wsl": _wsl(ram) if in_wsl else None,
        "gpu": gpu, "gpu_error": gpu_error, "torch": t, "device": {"chosen": chosen.device, "reason": chosen.reason},
        "guitar_device": gdev, "guitar_reason": greason,
        "cpu": {"logical": os.cpu_count(), "threads_default": default_threads()}, "ram": ram,
        "disk": {"home_free_mb": _free_mb(Path.home()),
                 "windows_c_free_mb": _free_mb(wsl.MNT_C) if in_wsl and wsl.MNT_C.is_dir() else None},
        "components": comps, "install": _install(),
    }
    allin1 = None
    if not full:
        from .engines import sections
        allin1 = sections.allin1_python(sections.Settings())
    r["problems"], r["notes"] = findings(r, allin1)
    r["ok"] = not r["problems"]
    return r


def _install() -> dict | None:
    """The install's lane and why ({"lane", "lane_reason"}, from runtime.json under $SONGCHARTER_HOME, which the
    launcher sets), else None (not run from an install)."""
    home = os.environ.get("SONGCHARTER_HOME")
    try:
        rt = json.loads((Path(home) / "runtime" / "runtime.json").read_text(encoding="utf-8")) if home else None
    except (OSError, ValueError):
        return None
    return {"lane": rt.get("lane"), "lane_reason": rt.get("lane_reason")} if isinstance(rt, dict) else None


def refresh(r: dict) -> dict:
    """A report doctor wrote earlier (doctor.json: one with `ram`) with what changes without a reinstall measured
    again: the memory, the free disk and, in WSL with interop, .wslconfig (so whether its memory is in force), then
    its problems, notes and `ok` made again from them; the GPU, torch and the components stay as they were. The
    install writes doctor.json before its last step sets WSL's memory, which applies only once WSL restarts, so the
    page's header shows this (the release gate's finding: it kept the install's "WSL has 7.8 GB of memory, under 11
    GB: allin1 is left out" for good). Any other report comes back as it is."""
    if not isinstance(r, dict) or not isinstance(r.get("ram"), dict):
        return r
    from . import wsl
    ram = memory()
    out = {**r, "ram": ram, "disk": _disk_now(r.get("disk") or {})}
    w = r.get("wsl")
    if isinstance(w, dict):
        config = wsl.wslconfig() if w.get("interop") else (w.get("wslconfig") or {})
        out["wsl"] = {**w, "wslconfig": config,
                      "memory_matches_config": memory_matches((ram or {}).get("total_mb"), config.get("memory_bytes"))}
    allin1 = None
    if "allin1" not in (r.get("components") or {}):   # a quick report: whether an allin1 Python is configured
        from .engines import sections
        allin1 = sections.allin1_python(sections.Settings())
    out["problems"], out["notes"] = findings(out, allin1)
    out["ok"] = not out["problems"]
    return out


def _disk_now(disk: dict) -> dict:
    """A report's `disk` with the free space measured again: in the home folder, and on C: when it was measured."""
    from . import wsl
    out = {**disk, "home_free_mb": _free_mb(Path.home())}
    if out.get("windows_c_free_mb") is not None:
        out["windows_c_free_mb"] = _free_mb(wsl.MNT_C)
    return out


def refresh_disk(r: dict) -> dict:
    """A report (refresh()'s) with only its free disk measured again, and its problems and `ok` made again from it
    (its notes do not depend on the disk). Cheap (two statvfs calls, no cmd.exe or PowerShell), so the page's header
    runs it on every status: a session of charts fills the disk, through the work cache and the WSL disk it grows on
    C:, while the server stays up (the advisor's finding 6 on the release candidate). A report with no `disk` comes
    back as it is."""
    if not isinstance(r, dict) or not isinstance(r.get("disk"), dict):
        return r
    out = {**r, "disk": _disk_now(r["disk"])}
    out["problems"] = findings(out)[0]
    out["ok"] = not out["problems"]
    return out


def summary(r: dict) -> list[str]:
    """doctor's lines for a report: one per item, then the problems and the notes (not the verdict)."""
    lines = [f"songcharter {r.get('songcharter')}, Python {r['python']['version']} ({r['python']['executable']}), "
             f"{r.get('platform')}"]
    w = r.get("wsl")
    if w:
        c = w.get("wslconfig") or {}
        mem = c.get("memory_bytes")
        cfg = ("no .wslconfig" if not c.get("exists") else
               f".wslconfig memory {_gb(mem / MB)} GB" if mem else ".wslconfig sets no memory")
        match = {True: ": in force", False: ": not in force"}.get(w.get("memory_matches_config"), "")
        lines.append(f"WSL: {w.get('distro') or '?'} on Windows {w.get('windows_build') or '?'}, interop "
                     f"{'on' if w.get('interop') else 'off'}; Windows RAM {_gb(w.get('windows_ram_mb'))} GB; "
                     f"{cfg}{match}")
        d = w.get("documents") or {}
        lines.append(f"Documents: {d.get('windows') or '?'} ({d.get('linux') or 'not found from WSL'})")
    else:
        lines.append("WSL: no")
    g = r.get("gpu")
    lines.append(f"GPU: {g['name']} ({_gb(g.get('vram_mb'))} GB), driver {g.get('driver')}, compute capability "
                 f"{g.get('compute_cap')}" if g else f"GPU: none ({r.get('gpu_error')})")
    t = r.get("torch") or {}
    if not t.get("installed"):
        lines.append(f"torch: not installed ({t.get('error')})")
    else:
        cuda = ("no CUDA (a CPU build)" if t.get("cuda") is None else
                f"CUDA {t['cuda']}: a kernel runs" if t.get("cuda_works") else
                f"CUDA {t['cuda']}: does not run{' (' + t['cuda_error'] + ')' if t.get('cuda_error') else ''}")
        m = t.get("matmul")
        mm = "" if not m else ", matmul ok" if m.get("ok") else f", matmul failed ({m.get('error')})"
        lines.append(f"torch: {t.get('version')}, {cuda}{mm}")
    dev = r.get("device") or {}
    lines.append("device: GPU (cuda)" if dev.get("chosen") == "cuda" else f"device: CPU mode: {dev.get('reason')}")
    comps = r.get("components") or {}
    ac = comps.get("autochart_cuda")
    if r.get("guitar_device") == "cuda":
        lines.append("guitar: on the GPU" + ("" if ac else " (the CUDA provider not checked: --quick)"))
    else:
        lines.append(f"guitar: on the CPU: {r.get('guitar_reason')}")
    cpu, ram, disk = r.get("cpu") or {}, r.get("ram") or {}, r.get("disk") or {}
    lines.append(f"CPU: {cpu.get('logical')} logical cores; the UI's default {cpu.get('threads_default')} threads")
    if ram:
        swap = (None if ram.get("swap_total_mb") is None or ram.get("swap_free_mb") is None
                else ram["swap_total_mb"] - ram["swap_free_mb"])
        lines.append(f"RAM: {_gb(ram.get('total_mb'))} GB, {_gb(ram.get('available_mb'))} GB available; swap "
                     f"{_gb(swap)} of {_gb(ram.get('swap_total_mb'))} GB used")
    c_free = disk.get("windows_c_free_mb")
    lines.append(f"disk: {_gb(disk.get('home_free_mb'))} GB free in {Path.home()}"
                 + (f"; {_gb(c_free)} GB free on C:" if c_free is not None else ""))
    names = {"ffmpeg": "ffmpeg", "node": "node", "scan_chart": "scan-chart", "autochart": "autochart",
             "autochart_cuda": "autochart's CUDA provider", "allin1": "allin1", "demucs": "demucs",
             "librosa": "librosa", "matplotlib": "matplotlib", "torchaudio": "torchaudio"}
    for key, c in comps.items():
        if key == "autochart_cuda" and not c.get("ok") and dev.get("chosen") != "cuda":
            text = f"not needed: the guitar runs on the CPU ({dev.get('reason')})"   # its load error would read as one
        elif key == "autochart_cuda":
            text = f"{'loads' if c.get('ok') else 'does not load'}: {c.get('detail')}"
        elif key == "allin1" and c.get("ok"):
            text = (f"ok, {c.get('package')} {c.get('version')}, CUDA {'runs' if c.get('cuda') else 'does not run'} "
                    f"({c.get('python')})")
        elif c.get("ok"):
            detail = ", ".join(str(c[k]) for k in ("version", "engine_version") if c.get(k))
            where = c.get("path") or c.get("root")
            text = "ok" + (f", {detail}" if detail else "") + (f" ({where})" if where else "")
        else:
            text = f"missing: {c.get('error') or 'not installed'}"
        lines.append(f"{names.get(key, key)}: {text}")
    lines += [f"problem: {p}" for p in r.get("problems") or []]
    lines += [f"note: {n}" for n in r.get("notes") or []]
    return lines
