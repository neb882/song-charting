"""common.py: paths and the song labels (reads the reference set's and the 20-song set's songs.json for their ids; prints nothing). The
reference songs are labelled r01-r06 here (sorted by id), the 20-song set s01-s13 as in M7-01 part C."""
import json, os, sys
from pathlib import Path
DEV = Path(os.environ["M8T_DEV"])            # the dev folder (golden, eval, eval-set20)
ORCH = Path(os.environ["M8T_ORCH"])          # the main checkout (read only)
PARTC = Path(os.environ["M8T_PARTC"])        # M7-01 part C's scratch folder
SHM = Path("<shm>/m8t")
OUT = Path(__file__).resolve().parent
G = DEV / "golden"
REFS = sorted(s["id"] for s in json.loads((DEV / "eval/refs/songs.json").read_text()))   # the six reference songs
STRESS = ["break", "pm2", "sooth", "troop"]
SONGS = {}   # label -> (set, id, kept folder, part C label)
for i, s in enumerate(REFS, 1):
    SONGS[f"r{i:02d}"] = ("refs", s, G / "work" / s, s)
for s in STRESS:
    SONGS[s] = ("stress", s, G / "stress-work" / s, s)
_set20 = sorted(s["id"] for s in json.loads((DEV / "eval-set20/stress/songs.json").read_text()))
for i, s in enumerate(_set20, 1):
    SONGS[f"s{i:02d}"] = ("set20", s, G / "set20-work" / s, f"s{i:02d}")
REFDIR = {"refs": DEV / "eval/refs", "stress": DEV / "eval/stress", "set20": DEV / "eval-set20/stress"}
