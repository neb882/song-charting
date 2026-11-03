"""Several autochart takes of every song (Expert only), for the take-ensemble experiment (DESIGN.md 2.7, Several
takes): does splicing takes by their agreement beat one take, against the human charts?

usage: python eval/takes.py [--device cuda] [--seeds 20260609,101,202,303] [--songs id,id]
Reads EVAL_DATA (default eval/data): refs/<id>/input.wav for each song in refs/songs.json and the test song. Writes
runs/takes/<id>/seed_<seed>/ through songcharter.engines.autochart (all of a song's takes share one work folder, so
takes after the first reuse the engine's separation and beat map). Resumable: finished takes are reused. One line
per take on stdout, and runs/takes/takes.log.
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from songcharter.engines.autochart import DEFAULT_SEED, find_install, generate  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--device", default="cuda", choices=("cpu", "cuda", "webgpu"))
ap.add_argument("--seeds", default=f"{DEFAULT_SEED},101,202,303")
ap.add_argument("--songs", default="")
a = ap.parse_args()
data = Path(os.environ.get("EVAL_DATA", HERE / "data"))
seeds = [int(s) for s in a.seeds.split(",") if s.strip()]
songs = [s["id"] for s in json.loads((data / "refs" / "songs.json").read_text(encoding="utf-8"))]
if (data / "refs" / "test_song" / "input.wav").exists():
    songs.append("test_song")
if a.songs:
    songs = [s for s in songs if s in a.songs.split(",")]
install = find_install(HERE / "tools" / "autochart")
out_root = data / "runs" / "takes"
out_root.mkdir(parents=True, exist_ok=True)
log = open(out_root / "takes.log", "a", encoding="utf-8")


def say(msg):
    line = f"{time.strftime('%H:%M:%S')} {msg}"
    print(line, flush=True)
    log.write(line + "\n")
    log.flush()


say(f"start: {len(songs)} songs x {len(seeds)} seeds on {a.device}")
for sid in songs:
    for seed in seeds:  # one call per seed, so a failure costs one take and the log shows progress
        try:
            take = generate(install, data / "refs" / sid / "input.wav", out_root / sid, (seed,), device=a.device)[0]
            run = take.summary["runs"][0]
            say(f"{sid} seed {seed}: {'cached' if take.cached else f'{take.seconds:.0f} s'}, tokens {run.get('nTokens')}, "
                f"devices {run.get('devices')}, reused {run.get('cachedStages')}")
        except Exception as e:  # keep going: the other takes are still worth having
            say(f"{sid} seed {seed}: FAILED {str(e).splitlines()[0]}")
say("ALL DONE")
