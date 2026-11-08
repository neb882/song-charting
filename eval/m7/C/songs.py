"""songs.py: the 23 songs of M7-01 part C (reads the 20-song set's songs.json for its ids, sorted: s01-s13; prints nothing): kept folder, label, set."""
import json
from pathlib import Path
G = Path("$DEV/golden")
REFS = ["all_the_small_things", "creep", "drunk_drivers", "kimochi_warui", "lucretia", "take_me_out"]
STRESS = ["break", "pm2", "sooth", "troop"]
SET20 = sorted(s["id"] for s in json.loads(Path("$DEV/eval-set20/stress/songs.json").read_text()))
SONGS = {}   # label -> (set, id, kept folder)
for s in REFS:
    SONGS[s] = ("refs", s, G / "work" / s)
for s in STRESS:
    SONGS[s] = ("stress", s, G / "stress-work" / s)
for i, s in enumerate(SET20, 1):
    SONGS[f"s{i:02d}"] = ("set20", s, G / "set20-work" / s)
TAKES = G / "m7-takes"
SEEDS = (101, 202, 303)
KEPT = 20260609
