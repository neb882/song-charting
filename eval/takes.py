"""Several autochart takes of every song of a set (Expert only): the take-ensemble experiment (DESIGN.md 2.7, Several
takes), and M8's measurements on the owner's GPU (every song with human charts).

usage: python eval/takes.py [--set refs|stress|set20] [--app] [--device cuda] [--seeds 20260609,101,202,303]
                            [--songs a,b] [--dry-run | --check | --scrub]

The sets, each song's input.wav as eval/build_refs.sh builds it (EVAL_DATA, default eval/data):
  refs (the default)  refs/<id>/ for each song of refs/songs.json, and the test song; takes in
                      runs/takes/<id>/seed_<seed>/ (as before M8)
  stress              eval/stress.json's songs in stress/<id>/ (build_refs.sh --set stress); takes in
                      runs/takes/stress/<id>/seed_<seed>/
  set20               the 20-song set, in a data folder of its own, SET20_DATA (default EVAL_DATA/set20), built as
                      the stress set is: its list set20.json (the STRESS_JSON of its build) and its songs in
                      stress/<id>/; takes in runs/takes/set20/<id>/seed_<seed>/
runs/ is always EVAL_DATA's, so eval/gpu.sh results finds every set's takes.

Labels: every line printed or logged names a song by its label, never by an id that is not one: the id for refs and
the stress set (generic ids), sNN for the 20-song set, whose ids spell titles: s01, s02, ... in the order of its sorted
ids (docs/reports/set20-v03.md's names). The take folders keep the ids: they stay on this PC. For stress and set20,
runs/takes/<set>/labels.json holds the mapping (label -> id; this PC only: eval/gpu.sh results names the zip's take
folders by it, and never zips it), and runs/takes/<set>/set.json each label's slot, chart count and length (no id),
so the orchestrator can check the labels against the dev machine's set. A path printed or logged has this PC's home
folder as ~ (a line pasted back carries no user name).

The engine: eval/tools/autochart (its setup.sh), or with --app the installed songcharter's own (runtime/autochart and
its Node, from runtime.json, with the launcher's environment: songcharter.launch), the way the app charts a song.
Run takes.py with the app's Python (runtime/env/bin/python) then: songcharter.engines.autochart puts that Python's
CUDA 13 and cuDNN wheels (the cu132 lane's) on the engine's library path for "cuda". songcharter itself is imported
from this checkout, which is first on sys.path. A song's takes share one work folder, so the takes after the first
reuse the engine's separation and beat map. Resumable: a finished take is reused (the engine's key: the input, the
seed, the settings, the install). One line per take on stdout and in runs/takes/takes.log (every set's; it stays on
this PC, with each failure's message), and one JSON record per take, run start and missing song in
runs/takes/takes.jsonl: only fields this script writes (the set, the label, the seed, made/cached/failed, seconds,
tokens, beats, the devices and reused stages as short names, a failure as its exception's type: never a message or a
path), the one log the results zip carries.

  --songs   ids or labels, comma-separated
  --dry-run the songs found and how many of their takes are made; writes nothing
  --check   the engine: its install, and for "cuda" its CUDA provider, the CUDA libraries and (--app) the app's lane
  --scrub   copies stdin to stdout with the set's ids replaced by their labels and every md5 by <md5> (the set
            builds' output, eval/gpu.sh build)
Exit 0: every take made (or the check passed); 1: a take failed (the others are still made); 2: the set cannot be
read, none of its songs has its input.wav, or the engine is not ready.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from songcharter.engines.autochart import DEFAULT_SEED, cuda_library_path, find_install, generate  # noqa: E402

SETS = ("refs", "stress", "set20")
STRESS_LIST = HERE / "stress.json"        # the stress set's committed list (generic ids)
SET20_LIST = "set20.json"                 # in SET20_DATA: the 20-song set's list (its ids spell titles)
LABELS = "labels.json"                    # in runs/takes/<set>/: label -> id, never zipped
SET_INFO = "set.json"                     # in runs/takes/<set>/: label, slot, charts, duration_s; no id
ID = re.compile(r"[a-z][a-z0-9_]*")       # eval/stress.py's ids: safe as a folder name
WORD = "A-Za-z0-9_"                       # an id is replaced where no such character is beside it
MD5 = re.compile(r"(?<![0-9a-fA-F])[0-9a-fA-F]{32}(?![0-9a-fA-F])")
CUDA_LANE = "cu132"                       # the app's lane whose CUDA 13 wheels load autochart's CUDA provider
RECORDS = "takes.jsonl"                   # in runs/takes/: the records eval/gpu.sh results zips
NAME = re.compile(r"[A-Za-z0-9_.+-]{1,40}")   # an engine's stage or device name, as a record may copy it


def shown(text: str) -> str:
    """`text` with this PC's home folder written ~."""
    home = os.path.expanduser("~")
    return re.sub(re.escape(home) + r"(?=[/\\\s'\"),:;]|\Z)", "~", text) if len(home) > 1 else text


def number(value):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def names(value):
    """A record's copy of the engine's devices ({stage: device}) or reused stages ([stage]): short names only."""
    if isinstance(value, dict):
        return {k: v for k, v in value.items() if isinstance(k, str) and isinstance(v, str) and NAME.fullmatch(k)
                and NAME.fullmatch(v)}
    if isinstance(value, list):
        return [v for v in value if isinstance(v, str) and NAME.fullmatch(v)]
    return None


class Refused(Exception):
    """The set cannot be read, or the engine is not ready: exit 2."""


@dataclass(frozen=True)
class Song:
    label: str
    id: str
    input: Path                           # input.wav
    out: Path                             # the take folders' parent: out/seed_<seed>/, the work folder out/work/
    info: dict = field(default_factory=dict)


def data_dir() -> Path:
    return Path(os.environ.get("EVAL_DATA") or HERE / "data")


def set20_dir(data: Path) -> Path:
    return Path(os.environ.get("SET20_DATA") or data / "set20")


def read_list(path: Path, what: str) -> list[dict]:
    try:
        songs = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise Refused(f"{what} {path} cannot be read ({type(e).__name__}): build the set first (eval/README.md)") from e
    if not isinstance(songs, list) or not all(isinstance(s, dict) and isinstance(s.get("id"), str) for s in songs):
        raise Refused(f"{what} {path} is not a list of songs with ids")
    return songs


def songs_of(name: str, data: Path) -> list[Song]:
    """Every song of the set `name`, in its run order, with its label, input.wav and take folders."""
    takes = data / "runs" / "takes"
    if name == "refs":
        ids = [s["id"] for s in read_list(data / "refs" / "songs.json", "the reference set's songs.json")]
        if (data / "refs" / "test_song" / "input.wav").exists():
            ids.append("test_song")
        return [Song(i, i, data / "refs" / i / "input.wav", takes / i) for i in ids]
    if name == "stress":
        listed, folder = read_list(STRESS_LIST, "the stress set's list"), data / "stress"
    elif name == "set20":
        root = set20_dir(data)
        listed, folder = read_list(root / SET20_LIST, "the 20-song set's list"), root / "stress"
    else:
        raise Refused(f"a set is one of {', '.join(SETS)}, not {name!r}")
    ids = [s["id"] for s in listed]
    for k, i in enumerate(ids, 1):   # the message never names the id: a 20-song set's spells a title
        if not ID.fullmatch(i):
            raise Refused(f"song {k} of the {name} set's list: its id is not lower-case letters, digits and _")
    if len(set(ids)) != len(ids):
        raise Refused(f"the {name} set's list has an id twice")
    try:   # the lengths, from the built set's songs.json (make_songs_json.py), when it is there
        built = {s.get("id"): s.get("duration_s") for s in read_list(folder / "songs.json", "")}
    except Refused:
        built = {}
    if name == "stress":
        labels = {i: i for i in ids}
    else:
        labels = {i: f"s{k:02d}" for k, i in enumerate(sorted(ids), 1)}
        listed = sorted(listed, key=lambda s: labels[s["id"]])
    return [Song(labels[s["id"]], s["id"], folder / s["id"] / "input.wav", takes / name / s["id"],
                 {"slot": s.get("slot"), "charts": s.get("charts"), "duration_s": built.get(s["id"])})
            for s in listed]


def scrubber(songs: list[Song], md5s: bool = False):
    """text -> text with each id that is not its song's label replaced by the label (as a whole word), and with
    `md5s` every 32-digit hex run by <md5>."""
    hidden = {s.id: s.label for s in songs if s.id != s.label}
    rx = re.compile(f"(?<![{WORD}])(" + "|".join(re.escape(i) for i in sorted(hidden, key=len, reverse=True))
                    + f")(?![{WORD}])") if hidden else None

    def scrub(text: str) -> str:
        if rx is not None:
            text = rx.sub(lambda m: hidden[m.group(1)], text)
        return MD5.sub("<md5>", text) if md5s else text
    return scrub


def write_set(folder: Path, songs: list[Song]) -> None:
    """runs/takes/<set>/labels.json (label -> id, this PC only) and set.json (no id)."""
    folder.mkdir(parents=True, exist_ok=True)
    (folder / LABELS).write_text(json.dumps({s.label: s.id for s in songs}, indent=1), encoding="utf-8")
    (folder / SET_INFO).write_text(json.dumps([{"label": s.label, **s.info} for s in songs], indent=1),
                                   encoding="utf-8")


def engine(app: bool):
    """(the autochart install the takes run on, the app's runtime.json or {}): with `app` the installed songcharter's
    (runtime.json's autochart and node), the launcher's environment put into this process's first (its Node first on
    PATH, its ffmpeg as FFMPEG, the models' home), as `songcharter` gets it; else eval/tools/autochart."""
    try:
        if not app:
            return find_install(HERE / "tools" / "autochart"), {}
        from songcharter import launch
        home = launch.home_dir()
        runtime = launch.load_runtime(home)
        if runtime is None:
            raise Refused(f"no installed songcharter at {home} (no runtime/runtime.json): install it, or set "
                          "SONGCHARTER_HOME")
        os.environ.update(launch.environment(runtime))
        return find_install(runtime.get("autochart") or home / "runtime" / "autochart",
                            node=runtime.get("node")), runtime
    except FileNotFoundError as e:
        raise Refused(str(e)) from e


def check(app: bool, device: str) -> int:
    """--check: what the takes would run on, each problem named; 0 when there is none, else 2."""
    from songcharter import __version__
    try:
        install, runtime = engine(app)
    except Refused as e:
        print(shown(f"takes: {e}"))
        return 2
    problems = []
    if app:
        print(shown(f"app: songcharter {runtime.get('songcharter')} at {runtime.get('home')}, "
                    f"the {runtime.get('lane')} lane"))
        if device == "cuda" and runtime.get("lane") != CUDA_LANE:
            problems.append(f"the app is on the {runtime.get('lane')} lane: autochart's CUDA provider needs "
                            f"{CUDA_LANE}'s CUDA 13 (a driver new enough for it; run the install line again)")
    print(shown(f"autochart: {install.driver.parent}, node {install.node}; this checkout's songcharter {__version__} "
                "runs it"))
    if device == "cuda":
        provider = sorted((install.driver.parent / "node_modules" / "onnxruntime-node").rglob(
            "libonnxruntime_providers_cuda.so*"))
        print(f"autochart's CUDA provider: {'there' if provider else 'missing'}")
        if not provider:
            problems.append("onnxruntime-node has no CUDA provider, so the takes would run on the CPU")
        libs = cuda_library_path()
        cu13 = [d for d in libs if d.endswith("cu13/lib")]
        cudnn = [d for d in libs if d.endswith("cudnn/lib")]
        wsl = ", and WSL's driver libraries" if any(d.endswith("/wsl/lib") for d in libs) else ""
        print(shown(f"CUDA libraries for it from this Python ({sys.executable}): {len(cu13)} CUDA 13 and "
                    f"{len(cudnn)} cuDNN folders{wsl}"))
        if not (cu13 and cudnn):
            problems.append("this Python has no CUDA 13 and cuDNN wheels (the app's cu132 lane brings them): run "
                            "takes.py with the app's Python, runtime/env/bin/python")
    for p in problems:
        print(f"problem: {p}")
    print("check: ok" if not problems else f"check: {len(problems)} problems")
    return 2 if problems else 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Several autochart Expert takes of every song of a set.")
    ap.add_argument("--set", default="refs", choices=SETS)
    ap.add_argument("--app", action="store_true", help="the installed songcharter's autochart and environment")
    ap.add_argument("--device", default="cuda", choices=("cpu", "cuda", "webgpu"))
    ap.add_argument("--seeds", default=f"{DEFAULT_SEED},101,202,303")
    ap.add_argument("--songs", default="", help="ids or labels, comma-separated")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="print the songs found; write nothing")
    mode.add_argument("--check", action="store_true", help="check the engine for --device")
    mode.add_argument("--scrub", action="store_true", help="stdin to stdout, the set's ids replaced by labels")
    a = ap.parse_args(argv)
    if a.check:
        return check(a.app, a.device)
    data = data_dir()
    seeds = [int(s) for s in a.seeds.split(",") if s.strip()]
    try:
        every = songs_of(a.set, data)
    except Refused as e:
        print(shown(f"takes: {e}"), file=sys.stderr)
        return 2
    if a.scrub:
        scrub = scrubber(every, md5s=True)
        for line in sys.stdin:
            sys.stdout.write(shown(scrub(line)))
            sys.stdout.flush()
        return 0
    scrub = scrubber(every)
    songs = every
    if a.songs:
        want = {s.strip() for s in a.songs.split(",") if s.strip()}
        songs = [s for s in every if s.id in want or s.label in want]
    found = [s for s in songs if s.input.is_file()]
    missing = [s for s in songs if s not in found]
    named = "" if a.set == "refs" else f"{a.set}, "
    if a.dry_run:
        for s in songs:
            made = sum((s.out / f"seed_{seed}" / "take.json").is_file() for seed in seeds)
            print(scrub(f"{s.label}: " + (f"input.wav found, {made} of {len(seeds)} takes made" if s in found
                                          else "no input.wav")))
        print(f"dry run: {named}{len(found)} songs found, {len(missing)} without input.wav, "
              f"{len(found) * len(seeds)} takes")
        return 0 if found else 2
    if not found:
        print(f"takes: {named}no song has its input.wav: build the set first (eval/README.md)", file=sys.stderr)
        return 2
    try:
        install, runtime = engine(a.app)
    except Refused as e:
        print(shown(f"takes: {e}"), file=sys.stderr)
        return 2
    out_root = data / "runs" / "takes"
    out_root.mkdir(parents=True, exist_ok=True)
    if a.set != "refs":
        write_set(out_root / a.set, every)
    failed = 0
    with open(out_root / "takes.log", "a", encoding="utf-8") as log, \
            open(out_root / RECORDS, "a", encoding="utf-8") as records:
        def say(msg: str) -> None:
            line = shown(scrub(f"{time.strftime('%H:%M:%S')} {msg}"))
            print(line, flush=True)
            log.write(line + "\n")
            log.flush()

        def record(**fields) -> None:   # only fields written here: no message, no path, no id
            records.write(json.dumps({"set": a.set, "time": time.strftime("%Y-%m-%dT%H:%M:%S"), **fields},
                                     sort_keys=True) + "\n")
            records.flush()

        app = {"songcharter": runtime.get("songcharter"), "lane": runtime.get("lane")} if a.app else None
        if app:   # which install made the takes (no path)
            say(f"app: songcharter {app['songcharter']}, the {app['lane']} lane")
        say(f"start: {named}{len(found)} songs x {len(seeds)} seeds on {a.device}")
        record(event="start", songs=len(found), seeds=seeds, device=a.device,
               app={k: v for k, v in app.items() if isinstance(v, str) and NAME.fullmatch(v)} if app else None)
        for s in missing:
            say(f"{s.label}: no input.wav, skipped (build the set: eval/README.md)")
            record(event="missing", label=s.label)
        for s in found:
            for seed in seeds:  # one call per seed, so a failure costs one take and the log shows progress
                try:
                    take = generate(install, s.input, s.out, (seed,), device=a.device)[0]
                    run = take.summary["runs"][0]
                    say(f"{s.label} seed {seed}: {'cached' if take.cached else f'{take.seconds:.0f} s'}, "
                        f"tokens {run.get('nTokens')}, devices {run.get('devices')}, reused {run.get('cachedStages')}")
                    record(event="take", label=s.label, seed=seed, status="cached" if take.cached else "made",
                           seconds=number(take.seconds), tokens=number(run.get("nTokens")),
                           beats=number(run.get("nBeats")), devices=names(take.devices),
                           reused=names(run.get("cachedStages")),
                           cut_short=take.cut_short if take.cut_short in ("tokens", "beats") else None)
                except Exception as e:  # keep going: the other takes are still worth having
                    failed += 1
                    say(f"{s.label} seed {seed}: FAILED {(str(e).splitlines() or [type(e).__name__])[0]}")
                    record(event="take", label=s.label, seed=seed, status="failed",
                           error=type(e).__name__ if NAME.fullmatch(type(e).__name__) else "Exception")
        say("ALL DONE" if not failed else f"ALL DONE, {failed} takes failed")
        record(event="done", failed=failed)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
