"""Golden charts: the reference set built before and after a change, so a change that moves a chart it was not meant
to touch is seen (DESIGN.md 3.6). Run from the root of a checkout (Linux or WSL):

    python -m eval.golden run --out DIR [--code CHECKOUT] [--rerun drums,bass,sections,guitar] [--songs id,id]
                              [--refs DIR] [--work DIR] [--stems DIR] [--threads N]
    python -m eval.golden diff OLD NEW --expect PARTS [--out DIR]

**run** builds every song of the reference set with `songcharter chart` from the checkout `--code` (default: this
one): every level (--levels all), one guitar take, no preview, on the CPU. It writes the song folders to <out>/<id>/
(<id>.failed when the gate fails) and <out>/summary.json:
  * `songs`: for each song, its build's exit status and gate, and for each part and difficulty the number of onsets
    (a chord is one), of notes and the track's hash as Clone Hero reads the folder (scan-chart through
    eval/scorer/scan_notes.cjs: its calculateTrackHash, which covers the tempo map, the star power, solos and drum
    fills and every note's tick, length, type and flags); for the songs with a human chart, eval/scorer/score.py's
    F1@50 and F1@100 of every part and difficulty both charts have, and the beat F1;
  * `code` and `options`: the commit that built the charts (and the tracked files it had changed) and how;
  * `run`: everything else, which differs from run to run: the time per song and per stage, the engines that ran,
    the paths. Two runs of one commit give the same summary but for `run`.
Logs go to <out>/logs/, score.py's full output to <out>/scores/.

  * **The kept work folders.** The heavy stages run once per song, into <work>/<id> (a `songcharter chart --work`
    folder kept outside the repository; default $SONGCHARTER_GOLDEN/work, else <user cache>/golden/work), when a run
    first finds it missing or
    unfinished ("cold"). Its stems are first hard-linked (never copied) from `--stems`, a separation cache of
    separate.py (<key>/<stem>.wav and info.json), when that holds the stems of this decode under the key the build
    will look for; else the build separates. autochart's scratch folder goes once the take is built (the take stays
    cached by its take.json). golden.json, written last, marks the folder finished.
  * **Each build has a work folder of its own,** <work>/.runs/<run>/<id>, made from the kept one: the decode and the
    stems hard-linked (the build only reads them), every engine's folder copied (an engine whose cache misses writes
    its files in place, which must never reach the kept ones). So two runs, from one checkout or two, at once or one
    after the other, never write into a kept folder; a lock per song orders them while a kept folder is made or read.
    Every file of the kept folder is checked unchanged after the build (an error otherwise), and the run's folder is
    deleted. The build's per-user cache is an empty folder of the run's, so its pruning touches nothing.
  * **--rerun** runs the named engines again for this run (their folders are left out of the run's folder), because
    the engines' caches are keyed by their inputs and settings, not by their code: a change to an engine's code shows
    only with it. The kept folders stay as they are. An engine whose kept cache does not answer (this commit changed
    its inputs or settings) also runs, in the run's folder, and `run` says so.
  * Exit status: 0 every song built (a failed gate is recorded, not an error); 1 a song's build failed or a kept
    folder changed; 2 bad input or environment (a missing reference set, scan-chart or node, an output folder in use).

**diff** compares two summaries (files, or the folders holding them). `--expect` names the parts the change was
meant to touch: `guitar`, `bass:hard`, ... (comma-separated), or `none`. A part and difficulty whose hash changed (or
that appeared or vanished, or whose song's chart delay changed) is "changed" when expected, else UNEXPECTED; so is a
song missing from either, or whose build's exit status or gate changed. Writes report.md and report.json (default:
beside NEW's summary): a table per song (status, onsets old -> new, F1@50 old -> new) and the F1 pooled over the
songs per part and difficulty (2 x matched onsets over reference plus candidate onsets). Exit 0, or 1 when anything
is UNEXPECTED, 2 when the summaries cannot be compared.
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import inspect
import json
import os
import shutil
import subprocess
import sys
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterator

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))

FORMAT = 1                                  # summary.json's format: bump it when a field's meaning changes
KEPT_FORMAT = 1                             # a kept folder's layout (its KEPT marker): bump it to make them again
PARTS = ("guitar", "bass", "drums")
LEVELS = ("expert", "hard", "medium", "easy")
ENGINES = ("drums", "bass", "sections", "guitar")   # what --rerun may name
TEST_SONG = "test_song"                     # the reference set's song with no human chart
KEPT = "golden.json"                        # in a kept work folder: it is finished, and who made it
RUNS = ".runs"                              # <work>/.runs/<run>/: each run's own work folders
SCAN_NOTES = HERE / "scorer" / "scan_notes.cjs"
SCORE = HERE / "scorer" / "score.py"
THREAD_VARS = ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMBA_NUM_THREADS")


class Refused(Exception):
    """Bad input or environment: exit 2."""


# ------------------------------------------------------------------------------------------------ the reference set

@dataclass(frozen=True)
class Song:
    id: str
    folder: Path       # <refs>/<id>: input.wav, and ref/ (the human chart) where there is one
    title: str
    artist: str
    has_ref: bool

    @property
    def input(self) -> Path:
        return self.folder / "input.wav"


def reference_set(refs: Path, only: tuple[str, ...] = ()) -> list[Song]:
    """The songs of refs/songs.json (those with a human chart), then the test song when refs/test_song/input.wav
    exists; only the ids in `only` when given."""
    try:
        listed = json.loads((refs / "songs.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise Refused(f"no reference set in {refs} ({type(e).__name__}: {e}): give --refs, or set EVAL_DATA") from e
    songs = [Song(s["id"], refs / s["id"], s.get("title") or s["id"], s.get("artist") or "Unknown",
                  (refs / s["id"] / "ref").is_dir()) for s in listed]
    if (refs / TEST_SONG / "input.wav").is_file():
        songs.append(Song(TEST_SONG, refs / TEST_SONG, TEST_SONG, "Unknown", False))
    if only:
        unknown = sorted(set(only) - {s.id for s in songs})
        if unknown:
            raise Refused(f"not in the reference set: {', '.join(unknown)}")
        songs = [s for s in songs if s.id in only]
    missing = [str(s.input) for s in songs if not s.input.is_file()]
    if missing:
        raise Refused(f"missing: {', '.join(missing)}")
    return songs


def checkout(code: Path) -> dict:
    """The checkout's commit, branch and the tracked files it has changed (git's view; None outside git)."""
    def git(*args: str) -> str | None:
        p = subprocess.run(["git", "-C", str(code), *args], capture_output=True, text=True)
        return p.stdout.strip() if p.returncode == 0 else None
    status = git("status", "--porcelain", "--untracked-files=no")
    return {"commit": git("rev-parse", "HEAD"), "branch": git("rev-parse", "--abbrev-ref", "HEAD"),
            "dirty": [line[3:] for line in status.splitlines()] if status else []}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ------------------------------------------------------------------------------------------------ files and locks

@contextmanager
def locked(path: Path, wait: bool = True) -> Iterator[None]:
    """An exclusive lock on the file `path` (made if missing) while the block runs; with wait False, Refused when
    another process holds it."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a+") as f:
        try:
            fcntl.flock(f, fcntl.LOCK_EX | (0 if wait else fcntl.LOCK_NB))
        except BlockingIOError as e:
            raise Refused(f"{path} is locked: another run is using this output folder") from e
        try:
            yield
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def manifest(folder: Path) -> dict[str, tuple[int, int, int]]:
    """Every file under `folder`: relative path -> (size, mtime in ns, inode). Any write or replacement shows."""
    out = {}
    for p in sorted(folder.rglob("*")):
        if p.is_file() and not p.is_symlink():
            st = p.stat()
            out[p.relative_to(folder).as_posix()] = (st.st_size, st.st_mtime_ns, st.st_ino)
    return out


def write_json(path: Path, data) -> None:
    part = path.with_name(path.name + ".part")
    part.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(part, path)


def read_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


# ------------------------------------------------------------------------------------------------ the kept folders

def seed_stems(song: Song, kept: Path, stems: Path) -> dict:
    """Hard-link the stems of this song's decode from the separation cache `stems` into kept/stems/<key>/, the folder
    the build's separation looks in, when `stems` has them under the key the build will compute (separate.py's
    cache_key of the decode with separate()'s defaults) and every stem there is whole. What was done, and why not."""
    import soundfile as sf

    from songcharter import audio as A
    from songcharter import separate as SEP
    mix = A.decode(song.input)
    p = inspect.signature(SEP.separate).parameters
    model = p["model"].default
    key = SEP.cache_key(mix, model, SEP.MODELS[model].revision, p["seed"].default, p["shifts"].default,
                        p["overlap"].default)
    frames, src, dst = mix.shape[1], stems / key, kept / "stems" / key
    del mix
    info = read_json(src / "info.json")
    if not info or not info.get("stems"):
        return {"key": key, "linked": [], "why": f"no stems for key {key} in {stems}"}
    names = list(info["stems"])
    for n in names:
        f = src / f"{n}.wav"
        if not f.is_file() or sf.info(str(f)).frames != frames:
            return {"key": key, "linked": [], "why": f"{f} is missing or not as long as the decode"}
    dst.mkdir(parents=True, exist_ok=True)
    (dst / "info.json").unlink(missing_ok=True)
    for n in names:
        target = dst / f"{n}.wav"
        if target.exists() and os.path.samefile(target, src / f"{n}.wav"):
            continue
        target.unlink(missing_ok=True)
        try:
            os.link(src / f"{n}.wav", target)
        except OSError as e:  # another file system: a copy would cost the disk the links save
            raise Refused(f"cannot hard-link {src / f'{n}.wav'} into {dst} ({e}): keep --work on the file system of "
                          f"--stems, or leave --stems out") from e
    shutil.copyfile(src / "info.json", dst / "info.json")  # last: separate() takes info.json as the hit
    return {"key": key, "linked": names, "from": str(src)}


def finished(kept: Path) -> dict | None:
    """The kept folder's KEPT marker when it is finished (the marker and the decode there), else None."""
    m = read_json(kept / KEPT)
    return m if m is not None and m.get("golden") == KEPT_FORMAT and (kept / "decode.wav").is_file() else None


def private_folder(kept: Path, folder: Path, rerun: tuple[str, ...]) -> None:
    """The build's own work folder, from the kept one: the decode and the stems (WAV) hard-linked, which the build
    only reads; the rest copied, every engine's folder but those to rerun and autochart's scratch folder."""
    folder.mkdir(parents=True)
    for p in sorted(kept.iterdir()):
        if p.name in (KEPT, "pipeline.json", "assemble.json") or p.name in rerun or p.name.startswith("."):
            continue
        if p.is_dir():
            if p.name == "stems":
                for src in sorted(p.rglob("*")):
                    dst = folder / "stems" / src.relative_to(p)
                    if src.is_dir():
                        dst.mkdir(parents=True, exist_ok=True)
                    elif src.suffix == ".wav":
                        os.link(src, dst)
                    else:
                        shutil.copy2(src, dst)
            else:
                shutil.copytree(p, folder / p.name,
                                ignore=lambda d, names: ["work"] if Path(d).name == "guitar" else [])
        elif p.name == "decode.wav":
            os.link(p, folder / p.name)
        else:
            shutil.copy2(p, folder / p.name)


# ------------------------------------------------------------------------------------------------ scan and score

def node() -> str:
    exe = os.environ.get("SONGCHARTER_NODE") or shutil.which("node")
    if not exe:
        raise Refused("node is not on PATH (or set SONGCHARTER_NODE): scan-chart runs under it")
    return exe


def scan_chart_script() -> Path:
    """The scan.cjs whose folder holds scan-chart: $SONGCHARTER_SCAN_CHART, else this checkout's tools/scan-chart."""
    script = Path(os.environ.get("SONGCHARTER_SCAN_CHART") or ROOT / "tools" / "scan-chart" / "scan.cjs").resolve()
    if not (script.parent / "node_modules" / "scan-chart").is_dir():
        raise Refused(f"scan-chart is not installed beside {script}: run `npm ci` in tools/scan-chart, or set "
                      "SONGCHARTER_SCAN_CHART to a scan.cjs that has it")
    return script


def scan(folder: Path, env: dict | None = None) -> dict:
    """scan_notes.cjs's reading of a song folder (scan-chart, as Clone Hero reads it)."""
    p = subprocess.run([node(), str(SCAN_NOTES), str(folder)], capture_output=True, text=True, env=env)
    if p.returncode != 0:
        raise RuntimeError(f"scan_notes.cjs failed on {folder}: {p.stderr.strip()[-2000:]}")
    return json.loads(p.stdout)


def parts(scanned: dict) -> dict[str, dict[str, dict]]:
    """part -> difficulty -> onsets (distinct ticks: a chord is one), notes and the track's hash, for every guitar,
    bass and drums track that has notes."""
    out: dict[str, dict[str, dict]] = {}
    for t in scanned.get("tracks") or []:
        if t["instrument"] in PARTS and t["difficulty"] in LEVELS and t["notes"]:
            out.setdefault(t["instrument"], {})[t["difficulty"]] = {
                "onsets": len({n["tick"] for n in t["notes"]}), "notes": len(t["notes"]), "hash": t["hash"]}
    return {p: {d: out[p][d] for d in LEVELS if d in out[p]} for p in PARTS if p in out}


def song_entry(scanned: dict) -> dict:
    """What a song's scan holds besides its parts: the chart's delay (song.ini delay, else the chart's Offset, as
    score.py applies them), whether it is playable and its scan-chart issues."""
    return {"delay": scanned.get("delay") or 0, "chart_offset": scanned.get("chart_offset") or 0,
            "playable": scanned.get("playable"), "chart_issues": len(scanned.get("chartIssues") or []),
            "parse_error": scanned.get("parseError"), "parts": parts(scanned)}


def _prf(d: dict) -> dict:
    return {k: d[k] for k in ("f1", "precision", "recall", "matched", "n_ref", "n_cand")}


def score(song: Song, folder: Path, out_json: Path, env: dict | None = None) -> dict:
    """score.py against the song's human chart: F1@50 and F1@100 per part and difficulty both charts have, the beat
    F1 and the audio alignment's lag."""
    p = subprocess.run([sys.executable, str(SCORE), "--ref", str(song.folder), "--cand", str(folder), "--input",
                        str(song.input), "--out", str(out_json)], capture_output=True, text=True, env=env)
    if p.returncode != 0:
        raise RuntimeError(f"score.py failed on {song.id}: {p.stderr.strip()[-2000:]}")
    d = json.loads(out_json.read_text(encoding="utf-8"))
    tracks: dict[str, dict[str, dict]] = {}
    for key, t in sorted(d["tracks"].items()):
        part, level = key.split("/")
        tracks.setdefault(part, {})[level] = {"f1_50": _prf(t["onset_50ms"]), "f1_100": _prf(t["onset_100ms"])}
    beat = (d.get("tempo_map") or {}).get("beat_f1_70ms")
    return {"tracks": tracks, "beat_f1": _prf(beat) if beat else None, "lag_ms": d["alignment"]["lag_ms"],
            "warnings": d.get("warnings") or []}


# ------------------------------------------------------------------------------------------------ run

@dataclass
class Context:
    """One run's settings, and the three steps tests stand in for: the build (`chart`: songcharter chart's argv
    after the Python, the environment, a log; its exit status), `scan` and `score`."""
    out: Path
    work: Path
    code: Path
    refs: Path
    stems: Path | None = None
    rerun: tuple[str, ...] = ()
    threads: int | None = None
    env: dict = field(default_factory=dict)
    runs: Path | None = None     # <work>/.runs/<this run>
    say: Callable[[str], None] = lambda line: print(line, file=sys.stderr, flush=True)
    chart: Callable[..., int] | None = None
    scan: Callable[..., dict] = scan
    score: Callable[..., dict] = score

    def build(self, args: list[str], log: Path) -> int:
        if self.chart is not None:
            return self.chart(args, self.env, log)
        with open(log, "a", encoding="utf-8") as f:
            f.write(f"$ {sys.executable} {' '.join(args)}\n")
            f.flush()
            return subprocess.run([sys.executable, *args], cwd=str(self.code), env=self.env, stdout=f,
                                  stderr=subprocess.STDOUT).returncode


def chart_args(song: Song, out: Path, work: Path, every_level: bool, threads: int | None) -> list[str]:
    """`songcharter chart` for golden: one take, no preview, the CPU, and every level for the summary's builds."""
    args = ["-m", "songcharter.cli", "chart", str(song.input), "--out", str(out), "--work", str(work),
            "--takes", "1", "--device", "cpu", "--no-preview", "--title", song.title, "--artist", song.artist]
    args += ["--levels", "all"] if every_level else []
    args += ["--threads", str(threads)] if threads else []
    return args


def _stages(pipeline: dict | None) -> list[dict]:
    return [{"stage": s["stage"], "seconds": s["seconds"], "cached": s["cached"]}
            for s in (pipeline or {}).get("stages") or []]


def _ran(stages: list[dict]) -> list[str]:
    """The heavy stages that ran rather than answering from their cache."""
    return [s["stage"] for s in stages if s["stage"] in ("decode", "separate", *ENGINES) and not s["cached"]]


def _tail(log: Path, n: int = 6) -> str:
    try:
        return "\n".join(log.read_text(encoding="utf-8", errors="replace").strip().splitlines()[-n:])
    except OSError:
        return ""


def prepare(song: Song, kept: Path, ctx: Context, log: Path) -> dict:
    """Make the kept folder of a song: stems from --stems where they fit, then a build into it (Expert only, its
    output thrown away), autochart's scratch folder deleted, the KEPT marker written last. The caller holds the
    song's lock."""
    t0 = time.perf_counter()
    kept.mkdir(parents=True, exist_ok=True)
    (kept / KEPT).unlink(missing_ok=True)
    seeded = seed_stems(song, kept, ctx.stems) if ctx.stems else None
    if seeded is not None:
        ctx.say(f"  {song.id}: stems " + (f"hard-linked from {seeded['from']}" if seeded["linked"]
                                          else f"not seeded ({seeded['why']}): the build separates"))
    out = ctx.runs / f"prepare-{song.id}"
    code = ctx.build(chart_args(song, out, kept, False, ctx.threads), log)
    for f in (out, out.with_name(out.name + ".failed")):
        shutil.rmtree(f, ignore_errors=True)
    if code not in (0, 1):
        raise RuntimeError(f"{song.id}: songcharter chart exited {code} making the kept folder {kept} (see {log}):\n"
                           f"{_tail(log)}")
    stages = _stages(read_json(kept / "pipeline.json"))
    scratch = kept / "guitar" / "work"
    if scratch.is_dir():
        shutil.rmtree(scratch)
    marker = {"golden": KEPT_FORMAT, "song": song.id, "code": checkout(ctx.code),
              "at": time.strftime("%Y-%m-%dT%H:%M:%S"), "seconds": round(time.perf_counter() - t0, 1),
              "stems": seeded, "stages": stages}
    write_json(kept / KEPT, marker)
    return marker


def build_song(song: Song, ctx: Context, logs: Path) -> tuple[dict, dict]:
    """Build one song into ctx.out/<id> from its own work folder, then scan and score it: (its `songs` entry, its
    `run` entry)."""
    t0 = time.perf_counter()
    kept, log = ctx.work / song.id, logs / f"{song.id}.log"
    log.unlink(missing_ok=True)
    timing: dict = {"cold": None}
    with locked(ctx.work / f"{song.id}.lock"):
        marker = finished(kept)
        if marker is None:
            ctx.say(f"  {song.id}: no finished kept folder in {kept}: making it (the heavy stages run)")
            marker = timing["cold"] = prepare(song, kept, ctx, log)
        private = ctx.runs / song.id
        private_folder(kept, private, ctx.rerun)
        before = manifest(kept)
    out = ctx.out / song.id
    failed = out.with_name(out.name + ".failed")
    for f in (out, failed):
        shutil.rmtree(f, ignore_errors=True)
    t1 = time.perf_counter()
    code = ctx.build(chart_args(song, out, private, True, ctx.threads), log)
    timing["build_seconds"] = round(time.perf_counter() - t1, 1)
    pipeline = read_json(private / "pipeline.json")
    if pipeline is not None:
        write_json(logs / f"{song.id}.pipeline.json", pipeline)
    stages = _stages(pipeline)
    ran = _ran(stages)
    timing.update(stages=stages, ran=ran, unasked=[e for e in ran if e not in ctx.rerun],
                  kept_from=(marker.get("code") or {}).get("commit"), kept_at=marker.get("at"))
    after = manifest(kept)
    if after != before:
        changed = sorted(k for k in set(before) | set(after) if before.get(k) != after.get(k))
        raise RuntimeError(f"{song.id}: the kept folder {kept} changed during the build: {', '.join(changed[:8])}")
    shutil.rmtree(private)
    entry: dict = {"has_ref": song.has_ref, "exit": code, "gate_ok": None, "folder": None}
    folder = out if out.is_dir() else failed if failed.is_dir() else None
    if code in (0, 1) and folder is not None:
        entry.update(gate_ok=code == 0, folder=folder.name)
        t1 = time.perf_counter()
        entry.update(song_entry(ctx.scan(folder, ctx.env)))
        timing["scan_seconds"] = round(time.perf_counter() - t1, 1)
        if song.has_ref:
            t1 = time.perf_counter()
            (ctx.out / "scores").mkdir(exist_ok=True)
            got = ctx.score(song, folder, ctx.out / "scores" / f"{song.id}.score.json", ctx.env)
            entry.update(scores=got["tracks"], beat_f1=got["beat_f1"], lag_ms=got["lag_ms"])
            timing["score_seconds"] = round(time.perf_counter() - t1, 1)
    else:
        entry["error"] = _tail(log)
    timing["seconds"] = round(time.perf_counter() - t0, 1)
    return entry, timing


def _clear_stale_runs(runs: Path) -> None:
    """Remove the run folders a killed run left (<pid>-<hex>, its process gone)."""
    for d in sorted(runs.iterdir()) if runs.is_dir() else []:
        try:
            os.kill(int(d.name.split("-")[0]), 0)
        except (ValueError, ProcessLookupError):
            shutil.rmtree(d, ignore_errors=True)
        except PermissionError:  # alive, another user's
            pass


def _apart(a: Path, b: Path) -> bool:
    return a != b and a not in b.parents and b not in a.parents


def run(songs: list[Song], ctx: Context) -> tuple[dict, int]:
    """Build, scan and score every song (the module docstring): the summary, and the exit status."""
    for a, b, what in ((ctx.out, ctx.work, "--work"), (ctx.out, ctx.refs, "--refs"), (ctx.out, ctx.code, "--code")):
        if not _apart(a.resolve(), b.resolve()):
            raise Refused(f"--out {ctx.out} and {what} {b} must be apart, neither inside the other")
    ctx.out.mkdir(parents=True, exist_ok=True)
    logs = ctx.out / "logs"
    with locked(ctx.out / ".golden.lock", wait=False):
        logs.mkdir(exist_ok=True)
        ctx.work.mkdir(parents=True, exist_ok=True)
        _clear_stale_runs(ctx.work / RUNS)
        ctx.runs = ctx.work / RUNS / f"{os.getpid()}-{uuid.uuid4().hex[:8]}"
        ctx.runs.mkdir(parents=True)
        ctx.env["SONGCHARTER_CACHE"] = str(ctx.runs / "cache")  # an empty cache: the build prunes nothing
        started, t0 = time.strftime("%Y-%m-%dT%H:%M:%S"), time.perf_counter()
        code, tool = checkout(ctx.code), checkout(ROOT)  # as the run starts
        results, timings, failures = {}, {}, 0
        try:
            for i, song in enumerate(songs, 1):
                ctx.say(f"[{i}/{len(songs)}] {song.id}")
                try:
                    results[song.id], timings[song.id] = build_song(song, ctx, logs)
                except RuntimeError as e:
                    failures += 1
                    results[song.id] = {"has_ref": song.has_ref, "exit": None, "gate_ok": None, "folder": None,
                                        "error": str(e)}
                    timings[song.id] = {"error": str(e)}
                    ctx.say(f"  {song.id}: FAILED: {e}")
                    continue
                r, t = results[song.id], timings[song.id]
                failures += r["exit"] not in (0, 1)
                ctx.say(f"  {song.id}: {_line(r, t)}")
        finally:
            shutil.rmtree(ctx.runs, ignore_errors=True)
        summary = {
            "golden": FORMAT,
            "about": "python -m eval.golden run (eval/golden.py). Everything but `run` is the same for two runs of "
                     "one commit.",
            "code": {"commit": code["commit"], "dirty": code["dirty"]},
            "options": {"levels": "all", "takes": 1, "device": "cpu", "preview": False, "rerun": list(ctx.rerun),
                        "songs": [s.id for s in songs]},
            "tools": {"scan_chart": _scan_chart_version(), "scan_notes_sha256": sha256(SCAN_NOTES),
                      "score_sha256": sha256(SCORE)},
            "songs": results,
            "run": {"code": {"path": str(ctx.code), "branch": code["branch"]}, "golden": {"path": str(ROOT),
                    **tool}, "out": str(ctx.out), "work": str(ctx.work), "refs": str(ctx.refs),
                    "stems": str(ctx.stems) if ctx.stems else None, "threads": ctx.threads,
                    "python": sys.executable, "started": started, "finished": time.strftime("%Y-%m-%dT%H:%M:%S"),
                    "seconds": round(time.perf_counter() - t0, 1), "songs": timings},
        }
        write_json(ctx.out / "summary.json", summary)
    return summary, 1 if failures else 0


def _line(r: dict, t: dict) -> str:
    cold = t.get("cold")
    head = (f"cold: kept folder made in {cold['seconds']:.0f} s, then " if cold else "warm: ")
    gate = {0: "gate OK", 1: "gate FAILED"}.get(r["exit"], f"exit {r['exit']}")
    ran = f"; ran {', '.join(t['ran'])}" if t.get("ran") else "; every engine cached"
    unasked = f" (NOT asked: {', '.join(t['unasked'])})" if t.get("unasked") else ""
    f1 = ""
    if r.get("scores"):
        f1 = "; Expert F1@50 " + ", ".join(f"{p} {lv['expert']['f1_50']['f1']:.3f}" for p, lv in r["scores"].items()
                                          if "expert" in lv)
    return f"{head}built in {t.get('build_seconds', 0):.0f} s, {gate}{ran}{unasked}{f1}; {t['seconds']:.0f} s in all"


def _scan_chart_version() -> str | None:
    try:
        pkg = read_json(scan_chart_script().parent / "node_modules" / "scan-chart" / "package.json")
    except Refused:
        return None
    return pkg.get("version") if pkg else None


def _words(text: str) -> tuple[str, ...]:
    return tuple(w.strip().lower() for w in text.split(",") if w.strip())


def cmd_run(a: argparse.Namespace) -> int:
    from songcharter import cache
    refs = Path(a.refs or Path(os.environ.get("EVAL_DATA") or HERE / "data") / "refs").resolve()
    rerun = _words(a.rerun or "")
    unknown = [e for e in rerun if e not in ENGINES]
    if unknown:
        raise Refused(f"--rerun takes {', '.join(ENGINES)}, not {', '.join(unknown)}")
    code = Path(a.code or ROOT).resolve()
    if not (code / "songcharter" / "cli.py").is_file():
        raise Refused(f"--code {code} is not a songcharter checkout")
    stems = Path(a.stems).resolve() if a.stems else None
    if stems is not None and not stems.is_dir():
        raise Refused(f"--stems {stems} is not a folder")
    songs = reference_set(refs, _words(a.songs or ""))
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join([str(code)] + [p for p in [env.get("PYTHONPATH")] if p])
    env["SONGCHARTER_SCAN_CHART"] = str(scan_chart_script())  # one scan-chart for the gate, scan and score
    env.setdefault("SONGCHARTER_AUTOCHART", str(ROOT / "eval" / "tools" / "autochart"))  # one install for both runs
    for v in THREAD_VARS if a.threads else ():
        env.setdefault(v, str(a.threads))
    node()
    probe = subprocess.run([sys.executable, "-c", "import songcharter; print(songcharter.__file__)"], cwd=str(code),
                           env=env, capture_output=True, text=True)
    if probe.returncode != 0 or code not in Path(probe.stdout.strip()).resolve().parents:
        raise Refused(f"the build would not import songcharter from {code} ({probe.stdout.strip() or probe.stderr})")
    golden = os.environ.get("SONGCHARTER_GOLDEN")
    work = Path(a.work or (Path(golden) if golden else cache.user_cache() / "golden") / "work").resolve()
    ctx = Context(out=Path(a.out).resolve(), work=work, code=code, refs=refs, stems=stems, rerun=rerun,
                  threads=a.threads, env=env)
    head = checkout(code)
    ctx.say(f"golden run: {len(songs)} songs from {code} ({(head['commit'] or '?')[:12]}"
            f"{', with changes' if head['dirty'] else ''}); rerun {', '.join(rerun) or 'none'}; kept folders in {work}")
    summary, status = run(songs, ctx)
    ctx.say(f"summary: {ctx.out / 'summary.json'} ({summary['run']['seconds']:.0f} s)")
    return status


# ------------------------------------------------------------------------------------------------ diff

def parse_expect(text: str) -> frozenset[tuple[str, str | None]]:
    """--expect: "none", or parts and part:difficulty pairs, comma-separated: {(part, difficulty or None)}."""
    words = _words(text)
    if words == ("none",):
        return frozenset()
    if not words:
        raise Refused(f"--expect is none, or parts and part:difficulty pairs such as guitar,bass:hard, not {text!r}")
    out = set()
    for w in words:
        part, _, level = w.partition(":")
        if part not in PARTS or (level and level not in LEVELS):
            raise Refused(f"--expect: {w!r} is not a part ({', '.join(PARTS)}) with an optional difficulty "
                          f"({', '.join(LEVELS)})")
        out.add((part, level or None))
    return frozenset(out)


def expected(expect: frozenset[tuple[str, str | None]], part: str, level: str) -> bool:
    return (part, None) in expect or (part, level) in expect


def load_summary(path: Path) -> tuple[dict, Path]:
    file = path / "summary.json" if path.is_dir() else path
    data = read_json(file)
    if not isinstance(data, dict) or "songs" not in data:
        raise Refused(f"{file} is not a golden summary")
    if data.get("golden") != FORMAT:
        raise Refused(f"{file} is format {data.get('golden')}, not {FORMAT}: build it again with this golden.py")
    return data, file


def _f1(entry: dict | None, part: str, level: str) -> dict | None:
    return (((entry or {}).get("scores") or {}).get(part) or {}).get(level, {}).get("f1_50")


def _pool(prfs: list[dict]) -> float | None:
    m, r, c = (sum(p[k] for p in prfs) for k in ("matched", "n_ref", "n_cand"))
    return 2 * m / (r + c) if r + c else None


def results(summary: dict) -> str:
    """The summary without its `run` section, canonical: two runs of one commit give the same text."""
    return json.dumps({k: v for k, v in summary.items() if k != "run"}, sort_keys=True)


def compare(old: dict, new: dict, expect: frozenset[tuple[str, str | None]]) -> dict:
    """The diff (the module docstring): per song its rows and song-level findings, the pooled F1, what is
    UNEXPECTED."""
    order = list(old["songs"]) + [s for s in new["songs"] if s not in old["songs"]]
    songs, unexpected = [], []
    touched: set[tuple[str, str]] = set()
    for sid in order:
        o, n = old["songs"].get(sid), new["songs"].get(sid)
        song: dict = {"id": sid, "findings": [], "rows": [],
                      "gate": [None if o is None else o.get("gate_ok"), None if n is None else n.get("gate_ok")],
                      "beat_f1": [((x or {}).get("beat_f1") or {}).get("f1") for x in (o, n)]}
        songs.append(song)

        def find(text: str, bad: bool = True) -> None:
            song["findings"].append({"text": text, "unexpected": bad})
            if bad:
                unexpected.append(f"{sid}: {text}")

        if o is None or n is None:
            find(f"only in the {'new' if o is None else 'old'} summary")
            continue
        if (o.get("exit"), o.get("gate_ok")) != (n.get("exit"), n.get("gate_ok")):
            find(f"the build changed: exit {o.get('exit')} -> {n.get('exit')}, gate {_gate(o.get('gate_ok'))} -> "
                 f"{_gate(n.get('gate_ok'))}")
        elif o.get("exit") not in (0, 1):
            find(f"not compared: the build failed in both runs (exit {o.get('exit')})")
        moved = (o.get("delay"), o.get("chart_offset")) != (n.get("delay"), n.get("chart_offset"))
        if moved:
            find(f"the chart's delay changed ({o.get('delay')} / {o.get('chart_offset')} -> {n.get('delay')} / "
                 f"{n.get('chart_offset')}): every part moves", bad=False)
        for part in PARTS:
            for level in LEVELS:
                a = ((o.get("parts") or {}).get(part) or {}).get(level)
                b = ((n.get("parts") or {}).get(part) or {}).get(level)
                if a is None and b is None:
                    continue
                changed = moved or a is None or b is None or a["hash"] != b["hash"]
                status = "unchanged" if not changed else "changed" if expected(expect, part, level) else "UNEXPECTED"
                fa, fb = _f1(o, part, level), _f1(n, part, level)
                song["rows"].append({"part": part, "level": level, "status": status,
                                     "onsets": [a and a["onsets"], b and b["onsets"]],
                                     "f1_50": [fa and fa["f1"], fb and fb["f1"]],
                                     "hash": [a and a["hash"], b and b["hash"]],
                                     "note": "only in the new build" if a is None else "only in the old build"
                                     if b is None else None})
                if changed:
                    touched.add((part, level))
                if status == "UNEXPECTED":
                    unexpected.append(f"{sid}: {part} {level}")
    pooled = []
    for part in PARTS:
        for level in LEVELS:
            both = [(_f1(old["songs"][s], part, level), _f1(new["songs"][s], part, level)) for s in order
                    if s in old["songs"] and s in new["songs"]]
            both = [(a, b) for a, b in both if a and b]
            if both:
                po, pn = _pool([a for a, _ in both]), _pool([b for _, b in both])
                pooled.append({"part": part, "level": level, "songs": len(both), "old": po, "new": pn,
                               "change": None if po is None or pn is None else pn - po})
    beats = [(old["songs"][s].get("beat_f1"), new["songs"][s].get("beat_f1")) for s in order
             if s in old["songs"] and s in new["songs"]]
    beats = [(a, b) for a, b in beats if a and b]
    if beats:
        po, pn = _pool([a for a, _ in beats]), _pool([b for _, b in beats])
        pooled.append({"part": "beat F1", "level": None, "songs": len(beats), "old": po, "new": pn,
                       "change": None if po is None or pn is None else pn - po})
    quiet = sorted(f"{p}:{lv}" if lv else p for p, lv in expect
                   if not any(tp == p and (lv is None or tl == lv) for tp, tl in touched))
    return {"golden": FORMAT, "expect": sorted(f"{p}:{lv}" if lv else p for p, lv in expect) or ["none"],
            "unexpected": unexpected, "exit": 1 if unexpected else 0,
            "identical": json.dumps(old["songs"], sort_keys=True) == json.dumps(new["songs"], sort_keys=True),
            "expected_but_unchanged": quiet, "pooled": pooled, "songs": songs,
            "tools_differ": old.get("tools") != new.get("tools")}


def _gate(ok) -> str:
    return "OK" if ok else "FAILED" if ok is False else "none"


def _num(x, nd: int = 3) -> str:
    return "—" if x is None else f"{x:.{nd}f}" if isinstance(x, float) else str(x)


def _pair(a, b, nd: int = 3) -> str:
    return f"{_num(a, nd)} → {_num(b, nd)}"


def _side(s: dict) -> dict:
    run_ = s.get("run") or {}
    timings = run_.get("songs") or {}
    ran: dict[str, int] = {}
    made: dict[str, int] = {}
    for t in timings.values():
        for e in t.get("ran") or []:
            ran[e] = ran.get(e, 0) + 1
        if t.get("kept_from"):
            made[t["kept_from"][:12]] = made.get(t["kept_from"][:12], 0) + 1
    return {"commit": (s.get("code") or {}).get("commit"), "dirty": (s.get("code") or {}).get("dirty") or [],
            "branch": (run_.get("code") or {}).get("branch"), "rerun": (s.get("options") or {}).get("rerun") or [],
            "ran": ran, "kept_from": made, "cold": sorted(k for k, t in timings.items() if t.get("cold")),
            "started": run_.get("started"),
            "seconds": run_.get("seconds")}


def render(report: dict, old_file: Path, new_file: Path) -> str:
    """report.md."""
    o, n = report["old"], report["new"]

    def commit(x):
        c = (x["commit"] or "?")[:12]
        return f"`{c}`" + (f" ({x['branch']})" if x["branch"] else "") + (" with changes" if x["dirty"] else "")

    def made(x):
        return ", ".join(f"`{c}` ({k} song{'s' * (k > 1)})" for c, k in x["kept_from"].items()) or "—"

    def engines(x):
        if not x["ran"]:
            return "none (every engine's cache answered)"
        return ", ".join(f"{e} on {k} song{'s' * (k > 1)}" for e, k in x["ran"].items())

    lines = [f"# Golden charts: {commit(o)} → {commit(n)}", "",
             "| | old | new |", "|---|---|---|",
             f"| summary | `{old_file}` | `{new_file}` |",
             f"| commit | {commit(o)} | {commit(n)} |",
             f"| engines asked to rerun | {', '.join(o['rerun']) or 'none'} | {', '.join(n['rerun']) or 'none'} |",
             f"| engines that ran | {engines(o)} | {engines(n)} |",
             f"| kept folders made in this run (cold) | {', '.join(o['cold']) or 'none'} | "
             f"{', '.join(n['cold']) or 'none'} |",
             f"| kept folders made by | {made(o)} | {made(n)} |",
             f"| started, seconds | {o['started'] or '—'}, {_num(o['seconds'], 0)} | {n['started'] or '—'}, "
             f"{_num(n['seconds'], 0)} |",
             "", f"Expected to change: {', '.join(report['expect'])}.", ""]
    if report["unexpected"]:
        lines.append(f"**UNEXPECTED: {len(report['unexpected'])}** ({'; '.join(report['unexpected'][:12])}"
                     f"{'; ...' if len(report['unexpected']) > 12 else ''}).")
    else:
        lines.append("**No UNEXPECTED change.**")
    changed = sum(r["status"] == "changed" for s in report["songs"] for r in s["rows"])
    lines.append(f"Parts changed as expected: {changed}. Every song's results (hashes, counts, scores) identical: "
                 f"{'yes' if report['identical'] else 'no'}.")
    if report["expected_but_unchanged"]:
        lines.append(f"Expected but unchanged on every song: {', '.join(report['expected_but_unchanged'])}.")
    if report["tools_differ"]:
        lines.append("Warning: the two summaries were made with different scorers (scan-chart, scan_notes.cjs or "
                     "score.py): hashes and F1 may differ for that reason alone.")
    lines += ["", "## F1@50 pooled over the songs with a human chart", "",
              "| part | level | songs | old | new | change |", "|---|---|---|---|---|---|"]
    for p in report["pooled"]:
        ch = "—" if p["change"] is None else f"{p['change']:+.4f}"
        lines.append(f"| {p['part']} | {p['level'] or ''} | {p['songs']} | {_num(p['old'], 4)} | {_num(p['new'], 4)} | "
                     f"{ch} |")
    lines += ["", "## Per song"]
    for s in report["songs"]:
        lines += ["", f"### {s['id']}", "",
                  f"Gate {_gate(s['gate'][0])} → {_gate(s['gate'][1])}; beat F1 {_pair(*s['beat_f1'])}."]
        lines += [f"**UNEXPECTED: {f['text']}.**" if f["unexpected"] else f"{f['text'][0].upper()}{f['text'][1:]}."
                  for f in s["findings"]]
        if s["rows"]:
            lines += ["", "| part | level | status | onsets | F1@50 |", "|---|---|---|---|---|"]
            for r in s["rows"]:
                status = f"**{r['status']}**" if r["status"] == "UNEXPECTED" else r["status"]
                note = f" ({r['note']})" if r["note"] else ""
                lines.append(f"| {r['part']} | {r['level']} | {status}{note} | {_pair(*r['onsets'])} | "
                             f"{_pair(*r['f1_50'])} |")
    return "\n".join(lines) + "\n"


def cmd_diff(a: argparse.Namespace) -> int:
    expect = parse_expect(a.expect)
    old, old_file = load_summary(Path(a.old).resolve())
    new, new_file = load_summary(Path(a.new).resolve())
    report = compare(old, new, expect)
    report.update(old={**_side(old), "summary": str(old_file)}, new={**_side(new), "summary": str(new_file)})
    out = Path(a.out).resolve() if a.out else new_file.parent
    out.mkdir(parents=True, exist_ok=True)
    write_json(out / "report.json", report)
    (out / "report.md").write_text(render(report, old_file, new_file), encoding="utf-8")
    bad = report["unexpected"]
    verdict = (f"UNEXPECTED: {len(bad)} ({'; '.join(bad[:6])}{'; ...' if len(bad) > 6 else ''})" if bad
               else "no UNEXPECTED change")
    print(f"golden diff: {verdict}; report: {out / 'report.md'}")
    return report["exit"]


# ------------------------------------------------------------------------------------------------ main

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m eval.golden", description=__doc__.split("\n\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="command", required=True)
    r = sub.add_parser("run", help="build the reference set and write <out>/summary.json")
    r.add_argument("--out", required=True, help="the folder for the song folders, summary.json, logs/ and scores/")
    r.add_argument("--code", help="the songcharter checkout that builds the charts (default: this one)")
    r.add_argument("--refs", help="the reference set (default: $EVAL_DATA/refs, else eval/data/refs)")
    r.add_argument("--work", help="the kept work folders, outside the repository (default: $SONGCHARTER_GOLDEN/work, "
                                  "else <user cache>/golden/work)")
    r.add_argument("--stems", help="a separation cache (separate.py's <key>/ folders) to hard-link stems from when a "
                                   "kept folder is made")
    r.add_argument("--rerun", metavar="ENGINES", help=f"engines to run again for this run ({','.join(ENGINES)})")
    r.add_argument("--songs", metavar="IDS", help="only these songs (comma-separated ids)")
    r.add_argument("--threads", type=int, metavar="N", help="threads for the models and BLAS (default: theirs)")
    d = sub.add_parser("diff", help="compare two summaries and write report.md and report.json")
    d.add_argument("old", help="the old summary.json, or its folder")
    d.add_argument("new", help="the new summary.json, or its folder")
    d.add_argument("--expect", required=True, metavar="PARTS",
                   help="the parts the change was meant to touch: none, or guitar, bass:hard, ... comma-separated")
    d.add_argument("--out", help="where report.md and report.json go (default: beside the new summary)")
    a = ap.parse_args(argv)
    try:
        return cmd_run(a) if a.command == "run" else cmd_diff(a)
    except Refused as e:
        print(f"golden: error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
