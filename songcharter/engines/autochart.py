"""Lead guitar from dvar0/autochart's engine, run as a separate program (DESIGN.md 2.7, route B1).

autochart's engine (`engine/bin/autochart-engine.cjs`, AGPL) runs htdemucs_6s, its fine-tuned Beat This and
Fretformer 2 under onnxruntime-node. Our own job driver (`eval/tools/autochart/ac_headless.cjs`, written from reading
the app's code) writes the job the app would write and assembles the song folder; this module runs that driver once
per take, behind a process boundary, so no AGPL code is imported.

  * **Takes.** One run per seed (the engine's default seed first), Expert only: the build reduces the other levels
    and splices the takes (takes.py). All takes share one work folder, where the engine caches its separation and
    beat map per audio file, so every take after the first pays only for the transcription. `on_take` hears of each
    take before it runs (the UI's "take k of n").
  * **Input.** The gapless decode written as WAV, not the user's MP3, so the takes' times are seconds of our decode.
  * **Cache.** A take is reused when its folder holds notes.chart, the driver's summary.json of a completed run and
    our take.json, written after the run, with the same key: the input (SHA-256), the seed, the sampling settings
    and the install (`install_key`: engine/manifest.json's engineVersion, and a SHA-256 over the engine's manifest
    and catalog, which pins every model file's SHA-256, the models' manifest, onnxruntime-node's package.json and
    the driver). So an updated engine, model set or driver runs every take again, and a take without take.json (an
    older songcharter's) is run again too. A take whose transcriber did not run on the requested device is not
    reused either.
  * **Devices.** "cpu", "cuda" or "webgpu" (the engine's own names). With "cuda" the engine itself would move the
    transcriber to WebGPU whenever a WebGPU adapter answers its probe, even a software one that runs on the CPU (seen
    in WSL: 1031 s for a take that took 319 s on CUDA), so the transcriber is pinned to the requested device with the
    engine's AUTOCHART_ONNX_TRANSCRIBER_DEVICE (unless it is set already). The engine still falls back to the CPU by
    itself when a provider fails to load; the devices it used are in each take's summary.
  * **CUDA libraries.** onnxruntime-node 1.27.0's CUDA provider needs CUDA 13 (cuBLAS, cudart, NVRTC, cuFFT, cuRAND)
    and cuDNN 9, which the cu132 torch lane's wheels bring in this Python's `nvidia` package (nvidia-curand adds
    cuRAND), and the driver's libcuda (/usr/lib/wsl/lib in WSL). For "cuda" those folders (`cuda_library_path`) go
    first on the node child's LD_LIBRARY_PATH, and only there: songcharter's own torch loads its own copies. With
    that path (cu13/lib, cudnn/lib, /usr/lib/wsl/lib) the provider ran Fretformer 2's encoder in WSL on an RTX 5070:
    357 nodes on CUDA, 31 on the CPU [here, 5070 spike: M4-00b]. The path is not part of a take's
    key: it changes where the provider loads from, not the chart.
  * **A take cut short** (M5-02, DESIGN.md 2.7): the engine's decoder has a budget a job, MAX_TOKENS tokens and
    MAX_BEATS beats (the models' manifest's maxTokens and maxBeats, `budget`). A run whose summary's nTokens reached
    its maxTokens (or the manifest's, when lower) or whose nBeats reached the beat cap stopped before the end of the
    song (`cut_short`: "tokens" or "beats"). Such a take is continued: with T its chart's last note, a piece of the
    decode from B - CONTEXT (B = floor(T) - KEEP_BACK) to the end, written beside the take as
    seed_<seed>/piece_<k>/input.wav (the same samples), is one more engine job with the same seed and settings (the
    same driver call, timeout and errors; its own job folder in the shared work folder), its notes from B on
    replacing the take's (stitch.py). A piece cut short again is continued the same way, up to MAX_PIECES; one whose
    last note advances T by under ADVANCE_S ends the loop and is still stitched. The engine's own output moves to
    seed_<seed>/cut_short/, the stitched chart is seed_<seed>/notes.chart, and autochart_run/summary.json is the
    whole-song run's plus a `stitch` record (`continue_take`). A take with no note at all (T = 0) is left as it is,
    with a `stitch` record of no pieces. Every take under the budget takes exactly the path it took before.
  * **Takes v0.1 cut short** are in the cache with the same key and the lost ending: a cached take whose summary is
    cut short and has no `stitch` record is a miss (`_done`), run whole again once and continued. The key is
    unchanged, so every other cached take is still a hit.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import os
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping, Sequence

from .. import audio as A
from ..errors import ToolError

DEFAULT_SEED = 20260609          # the engine's own default seed
TEMPERATURE, TOP_P = 0.95, 0.98   # the app's "Standard" preset (the driver's defaults)
REPO_INSTALL = Path(__file__).resolve().parents[2] / "eval" / "tools" / "autochart"
TAKE = "take.json"               # in each take's folder: the key it was made with, written once the run succeeded
WSL_LIB = Path("/usr/lib/wsl/lib")  # WSL's driver libraries (libcuda.so.1), from the Windows NVIDIA driver
CUDA_LIB_DIRS = ("cu13/lib", "cudnn/lib")  # in each folder of the nvidia namespace package: CUDA 13, cuDNN 9
MAX_TOKENS, MAX_BEATS = 8192, 1280   # the engine's budget a job when the models' manifest does not say (budget)
KEEP_BACK = 1           # s: a piece's notes replace the take's from B = floor(T) - KEEP_BACK (T: the last note)
CONTEXT = 8.0           # s of the decode a piece starts before its B, for the engine's timing and decoder
MAX_PIECES = 6          # pieces a take is continued in at most
ADVANCE_S = 20.0        # a piece whose last note advances the take's by less ends the continuation
CUT = "cut_short"       # in a continued take's folder: the engine's own output of the whole-song run
ENGINE_OUTPUT = ("notes.chart", "song.ini", "song.ogg", "autochart_run")   # what the driver writes into --out


@dataclass(frozen=True)
class Install:
    node: str            # the node executable
    driver: Path         # ac_headless.cjs
    app_root: Path       # the autochart checkout (engine/ inside it)
    models: Path         # the Fretformer 2 models (fetch_models.sh)


@dataclass(frozen=True)
class Take:
    seed: int
    chart: Path          # notes.chart
    summary: dict        # the driver's autochart_run/summary.json (with its `stitch` record when continued)
    cached: bool
    seconds: float       # wall time of this run, its pieces included (0 when cached)
    cut_short: str | None = None   # "tokens" or "beats": the whole-song run was cut short by the engine's budget

    @property
    def stitch(self) -> dict | None:
        """The continuation's record (continue_take), None for a take that was not cut short."""
        return self.summary.get("stitch")

    @property
    def devices(self) -> dict | None:
        """The devices the whole-song run reports, where a piece that ran a stage on another device than the one
        asked for counts as that device for the take."""
        runs = self.summary.get("runs") or [{}]
        devices = runs[0].get("devices")
        stitch = self.summary.get("stitch") or {}
        asked = stitch.get("device")
        for piece in stitch.get("pieces") or []:
            for stage, used in (piece.get("devices") or {}).items():
                if used is not None and used != asked and (devices or {}).get(stage) in (None, asked):
                    devices = {**(devices or {}), stage: used}
        return devices


def find_install(root: Path | str | None = None, node: str | None = None) -> Install:
    """The engine install: `root` (default $SONGCHARTER_AUTOCHART, else eval/tools/autochart after its setup.sh) and
    node ($SONGCHARTER_NODE, else PATH). Raises with what is missing."""
    root = Path(root or os.environ.get("SONGCHARTER_AUTOCHART") or REPO_INSTALL)
    node = node or os.environ.get("SONGCHARTER_NODE") or shutil.which("node")
    inst = Install(node or "", root / "ac_headless.cjs", root / "src", root / "models")
    missing = []
    if not node:
        missing.append("node (install Node.js, or set SONGCHARTER_NODE)")
    if not inst.driver.is_file():
        missing.append(f"the driver {inst.driver}")
    if not (inst.app_root / "engine" / "bin" / "autochart-engine.cjs").is_file():
        missing.append(f"autochart's engine under {inst.app_root} (run setup.sh)")
    if not (inst.models / "fretformer-v2" / "manifest.json").is_file():
        missing.append(f"the Fretformer 2 models under {inst.models} (run fetch_models.sh)")
    if not (root / "node_modules" / "onnxruntime-node").is_dir():
        missing.append(f"onnxruntime-node under {root / 'node_modules'} (run npm ci there)")
    if missing:
        raise FileNotFoundError("autochart engine not ready: " + "; ".join(missing))
    return inst


def cuda_library_path() -> list[str]:
    """The folders onnxruntime-node's CUDA provider loads its libraries from: for each folder of this Python's
    `nvidia` namespace package (the torch lane's CUDA wheels), its cu13/lib and cudnn/lib where they exist, then
    /usr/lib/wsl/lib where it exists."""
    try:
        spec = importlib.util.find_spec("nvidia")
    except (ImportError, ValueError):
        spec = None
    folders = []
    for base in list(spec.submodule_search_locations or []) if spec is not None else []:
        for sub in CUDA_LIB_DIRS:
            d = Path(base) / sub
            if d.is_dir() and str(d) not in folders:
                folders.append(str(d))
    if WSL_LIB.is_dir():
        folders.append(str(WSL_LIB))
    return folders


def cuda_environment(env: Mapping[str, str]) -> dict[str, str]:
    """`env` with cuda_library_path() put first on LD_LIBRARY_PATH (unchanged when there is none): for a node child
    that loads the CUDA provider, never for this process."""
    out = dict(env)
    folders = cuda_library_path()
    if folders:
        out["LD_LIBRARY_PATH"] = ":".join(folders + [p for p in [env.get("LD_LIBRARY_PATH")] if p])
    return out


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 22), b""):
            h.update(block)
    return h.hexdigest()


def _on_device(summary: dict, device: str | None) -> bool:
    """Whether every run's transcriber used `device`, a continued take's pieces' too (summaries without devices
    count as yes)."""
    if device is None:
        return True
    runs = (summary.get("runs") or []) + ((summary.get("stitch") or {}).get("pieces") or [])
    used = [(r.get("devices") or {}).get("transcriber") for r in runs]
    return all(u in (None, device) for u in used)


def budget(install: Install) -> tuple[int, int]:
    """The engine's budget a job: (tokens, beats), the models' manifest's stages.transcriber.modelConfig maxTokens
    and maxBeats (what the engine reads), else MAX_TOKENS and MAX_BEATS."""
    try:
        manifest = json.loads((install.models / "fretformer-v2" / "manifest.json").read_text(encoding="utf-8"))
        config = manifest["stages"]["transcriber"]["modelConfig"]
    except (OSError, ValueError, KeyError, TypeError):
        config = {}

    def cap(name: str, default: int) -> int:
        value = config.get(name) if isinstance(config, dict) else None
        return int(value) if isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0 else default

    return cap("maxTokens", MAX_TOKENS), cap("maxBeats", MAX_BEATS)


def cut_short(summary: dict, caps: tuple[int, int] = (MAX_TOKENS, MAX_BEATS)) -> str | None:
    """Why the run in a driver's `summary` stopped before the end of the song, else None: "tokens" when runs[0]'s
    nTokens reached the summary's maxTokens (the driver's, by default the engine's 8192) or the engine's own budget
    (`caps`, budget()) when lower, "beats" when its nBeats reached the beat cap."""
    run = (summary.get("runs") or [{}])[0]
    tokens, beats = run.get("nTokens"), run.get("nBeats")
    limits = [x for x in (summary.get("maxTokens"), caps[0]) if isinstance(x, (int, float)) and x > 0]
    if isinstance(tokens, (int, float)) and limits and tokens >= min(limits):
        return "tokens"
    if isinstance(beats, (int, float)) and beats >= caps[1]:
        return "beats"
    return None


def install_key(install: Install) -> dict:
    """What a take depends on in the install: engine/manifest.json's engineVersion (a date-based name that may stay
    the same across commits) and a SHA-256 over the files that define the engine, the models and the job: the
    engine's manifest and catalog (the catalog pins every model file's SHA-256, which fetch_models.sh checks), the
    models' manifest, onnxruntime-node's package.json and our driver. A missing file counts as absent."""
    engine, root = install.app_root / "engine", install.driver.parent
    files = {"engine/manifest.json": engine / "manifest.json", "engine/catalog.json": engine / "catalog.json",
             "models/fretformer-v2/manifest.json": install.models / "fretformer-v2" / "manifest.json",
             "onnxruntime-node/package.json": root / "node_modules" / "onnxruntime-node" / "package.json",
             "driver": install.driver}
    h = hashlib.sha256()
    for name, path in files.items():
        data = path.read_bytes() if path.is_file() else None
        h.update(f"{name}:{-1 if data is None else len(data)}:".encode())
        h.update(data or b"")
    try:
        version = json.loads(files["engine/manifest.json"].read_text(encoding="utf-8")).get("engineVersion")
    except (OSError, ValueError, AttributeError):
        version = None
    return {"engineVersion": version, "install": h.hexdigest()}


def take_key(input_sha: str, seed: int, install: dict) -> dict:
    """A take's key (take.json): the input, the seed, the sampling settings and the install (install_key)."""
    return {"inputSha256": input_sha, "seed": seed, "difficulties": ["expert"], "temperature": TEMPERATURE,
            "topP": TOP_P, **install}


def _summary(folder: Path, key: dict) -> dict | None:
    """The driver's summary of a completed run in `folder` for the key's input, seed and settings, else None."""
    chart, summary = folder / "notes.chart", folder / "autochart_run" / "summary.json"
    if not (chart.is_file() and summary.is_file()):
        return None
    try:
        s = json.loads(summary.read_text(encoding="utf-8"))
    except ValueError:
        return None
    runs = s.get("runs") or []
    ok = (s.get("inputSha256") == key["inputSha256"] and s.get("seed") == key["seed"]
          and s.get("difficulties") == key["difficulties"] and s.get("temperature") == key["temperature"]
          and s.get("topP") == key["topP"] and runs and all(r.get("status") == "completed" for r in runs))
    return s if ok else None


def _done(folder: Path, key: dict, device: str | None = None,
          caps: tuple[int, int] = (MAX_TOKENS, MAX_BEATS)) -> dict | None:
    """The summary of a finished take in `folder` made with this key (its take.json) and, if given, with its
    transcriber on `device`, else None. A take cut short by the engine's budget (cut_short, with `caps`) that has no
    `stitch` record (one v0.1 made, with the same key) is not finished: it is run again and continued."""
    try:
        made = json.loads((folder / TAKE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    s = _summary(folder, key) if made == key else None
    if s is None or not _on_device(s, device):
        return None
    return None if "stitch" not in s and cut_short(s, caps) else s


def _last_note(chart: Path) -> float | None:
    """The onset of the last Expert guitar note of an engine's chart, in seconds of its audio (None: no note)."""
    from ..importers import read_song
    part = read_song(chart).parts.get(("guitar", "expert"))
    return part.notes[-1].time if part and part.notes else None


def _clear_continuation(folder: Path) -> None:
    """A take folder without what an earlier continuation left there (cut_short/, piece_<k>/), so a run that
    follows one that was cut off, or an older stitched take, starts from the driver's own files only."""
    for d in [folder / CUT] + sorted(folder.glob("piece_*")):
        if d.is_dir():
            shutil.rmtree(d)


def _write_piece(audio: Path, path: Path, start_s: float) -> float:
    """The decode `audio` from `start_s` (a whole sample) to its end, as a WAV of the same samples and subtype at
    `path`; its start in seconds, as the sample it starts on gives it."""
    import soundfile as sf
    info = sf.info(str(audio))
    first = min(int(round(start_s * info.samplerate)), info.frames)
    y, _ = sf.read(str(audio), start=first, dtype="float32", always_2d=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(path), y, info.samplerate, subtype=info.subtype)
    return first / info.samplerate


def _mmss(t: float) -> str:
    return f"{int(t // 60)}:{int(t % 60):02d}"


def _write_summary(path: Path, summary: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")


def continue_take(folder: Path, audio: Path, summary: dict, reason: str, device: str,
                  drive: Callable[[Path, Path, str], tuple[dict, float]],
                  caps: tuple[int, int] = (MAX_TOKENS, MAX_BEATS)) -> dict:
    """Continue the take in `folder`, whose whole-song run (`summary`, of the decode `audio`) was cut short for
    `reason`, and stitch it (the module docstring); returns its summary with the `stitch` record, written as
    autochart_run/summary.json. `drive(audio, out, what)` runs one engine job on `audio` into `out` with the take's
    seed and settings and returns its summary and wall time, or raises (`what` names the job in its errors).
    take.json is not written here: a continuation cut off leaves no take.

    The record: `cut_short` (the reason), `device` (the one asked for), `cut_at_s` (the whole-song run's last note),
    `pieces` (each piece's start_s, keep_from_s, last_note_s, nTokens, nBeats, seconds, devices, cut_short),
    `last_note_s` (the stitched take's last note) and `ended`: "end" (the last piece was not cut short), "stalled"
    (it was, but advanced the take's last note by under ADVANCE_S), "max_pieces" (MAX_PIECES pieces, the last cut
    short) or "no notes" (T = 0: no piece)."""
    from ..chart import write_chart
    from . import stitch as ST
    base_last = _last_note(folder / "notes.chart")
    record: dict = {"cut_short": reason, "device": device, "cut_at_s": base_last, "pieces": [],
                    "last_note_s": base_last}
    if base_last is None:   # no guitar at all: nothing to continue; the record makes it a hit next time
        out = {**summary, "stitch": {**record, "ended": "no notes"}}
        _write_summary(folder / "autochart_run" / "summary.json", out)
        return out
    last, ended, pieces = base_last, "max_pieces", []
    for k in range(1, MAX_PIECES + 1):
        keep_from = float(max(0, math.floor(last) - KEEP_BACK))
        piece = folder / f"piece_{k}"
        start = _write_piece(audio, piece / "input.wav", max(0.0, keep_from - CONTEXT))
        got, seconds = drive(piece / "input.wav", piece, f"piece {k} (its audio from {_mmss(start)})")
        note = _last_note(piece / "notes.chart")
        reached = last if note is None else note + start
        run = (got.get("runs") or [{}])[0]
        again = cut_short(got, caps)
        record["pieces"].append({"start_s": start, "keep_from_s": keep_from, "last_note_s": reached,
                                 "nTokens": run.get("nTokens"), "nBeats": run.get("nBeats"), "seconds": seconds,
                                 "devices": run.get("devices"), "cut_short": again})
        pieces.append((piece / "notes.chart", start, keep_from))
        if again is None:
            ended = "end"
            break
        if reached - last < ADVANCE_S:
            ended = "stalled"
            break
        last = reached
    chart = ST.stitch_files(folder / "notes.chart", pieces)
    record["last_note_s"], record["ended"] = ST.last_note_s(chart), ended
    moved = folder / CUT
    moved.mkdir()
    for name in ENGINE_OUTPUT:
        if (folder / name).exists():
            os.replace(folder / name, moved / name)
    (folder / "notes.chart").write_text(write_chart(chart), encoding="utf-8", newline="")
    out = {**summary, "stitch": record}
    _write_summary(folder / "autochart_run" / "summary.json", out)
    return out


def generate(install: Install, audio: Path | str, out: Path | str, seeds: Sequence[int] = (DEFAULT_SEED,), *,
             device: str = "cpu", work: Path | str | None = None, timeout_s: float = 3600, ffmpeg: str | None = None,
             title: str | None = None, artist: str | None = None,
             on_take: Callable[[int, int, int], None] | None = None,
             run: Callable[..., subprocess.CompletedProcess] = subprocess.run) -> list[Take]:
    """One Expert take per seed of `audio` (a WAV of the gapless decode), in out/seed_<seed>/ (a song folder:
    notes.chart, song.ini, song.ogg, autochart_run/, take.json; a take cut short by the engine's budget is
    continued and stitched there, continue_take). Takes already there with the same key (input, seed, sampling
    settings, install) are reused. For "cuda" the driver's environment has cuda_library_path() first on
    LD_LIBRARY_PATH. `on_take(index, count, seed)` is called before each take that runs, not one reused: index from 1
    among `seeds`, count len(seeds). A failed run, a continuation's piece included, raises errors.ToolError (a
    RuntimeError) with the driver's last lines."""
    audio, out = Path(audio).resolve(), Path(out).resolve()
    if not audio.is_file():
        raise FileNotFoundError(f"autochart input {audio} does not exist")
    if len(set(seeds)) != len(seeds) or not seeds:
        raise ValueError(f"seeds must be distinct and at least one, not {list(seeds)}")
    if device not in ("cpu", "cuda", "webgpu"):
        raise ValueError(f"device is cpu, cuda or webgpu, not {device!r}")
    work = Path(work).resolve() if work else out / "work"
    input_sha, installed, caps = sha256(audio), install_key(install), budget(install)
    takes = []
    for index, seed in enumerate(seeds, 1):
        folder, key = out / f"seed_{seed}", take_key(input_sha, seed, installed)
        summary = _done(folder, key, device, caps)
        if summary is not None:
            takes.append(Take(seed, folder / "notes.chart", summary, True, 0.0,
                              (summary.get("stitch") or {}).get("cut_short")))
            continue
        if on_take is not None:
            on_take(index, len(seeds), seed)
        folder.mkdir(parents=True, exist_ok=True)
        (folder / TAKE).unlink(missing_ok=True)  # a run cut off from here on leaves no hit
        _clear_continuation(folder)
        work.mkdir(parents=True, exist_ok=True)
        env = {**os.environ, "AC_SEED": str(seed), "AC_DIFFICULTIES": "expert", "AC_DEVICE": device,
               "AC_TEMPERATURE": str(TEMPERATURE), "AC_TOP_P": str(TOP_P), "AC_TIMEOUT_S": str(int(timeout_s)),
               "AC_APP_ROOT": str(install.app_root), "AC_MODELS": str(install.models),
               "AUTOCHART_FFMPEG_PATH": ffmpeg or A.ffmpeg_exe()}
        if device in ("cpu", "cuda"):
            env.setdefault("AUTOCHART_ONNX_TRANSCRIBER_DEVICE", device)
        if device == "cuda":
            env = cuda_environment(env)
        if title:
            env["AC_TITLE"] = title
        if artist:
            env["AC_ARTIST"] = artist

        def drive(source: Path, into: Path, what: str = "", seed: int = seed, env: dict = env) -> tuple[dict, float]:
            """One engine job of this take on `source` into `into`: its summary and wall time, or a ToolError
            (`what`: the piece, named after the exit code so pipeline.failure still reads it)."""
            where = f" in {what}" if what else ""
            t0 = time.perf_counter()  # reported only
            try:
                proc = run([install.node, str(install.driver), "--audio", str(source), "--out", str(into),
                            "--work", str(work)], env=env, cwd=str(install.driver.parent), capture_output=True,
                           text=True, timeout=timeout_s + 600)
            except subprocess.TimeoutExpired as e:
                raise ToolError(f"autochart seed {seed} did not finish within {e.timeout:.0f} s{where}") from e
            seconds = round(time.perf_counter() - t0, 1)
            got = _summary(into, key if source == audio else take_key(sha256(source), seed, installed))
            if proc.returncode != 0 or got is None:
                tail = "\n".join((proc.stderr or "").strip().splitlines()[-8:])
                raise ToolError(f"autochart seed {seed} failed (exit {proc.returncode}){where}:\n{tail}")
            return got, seconds

        summary, seconds = drive(audio, folder)
        reason = cut_short(summary, caps)
        if reason is not None:
            summary = continue_take(folder, audio, summary, reason, device, drive, caps)
            seconds = round(seconds + sum(p["seconds"] for p in summary["stitch"]["pieces"]), 1)
        (folder / TAKE).write_text(json.dumps(key, indent=1), encoding="utf-8")
        takes.append(Take(seed, folder / "notes.chart", summary, False, seconds, reason))
    return takes
