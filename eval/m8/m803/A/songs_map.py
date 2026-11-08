"""songs_map.py: label -> (set, kept folder Path), 20-song ids mapped to s01..s13 in process (sorted ids). Reads set20 songs.json ids only; prints nothing."""
import json
from pathlib import Path
G = Path("$DEV/golden")
REFS = ["all_the_small_things", "creep", "drunk_drivers", "kimochi_warui", "lucretia", "take_me_out"]
STRESS = ["break", "pm2", "sooth", "troop"]
SET20 = sorted(s["id"] for s in json.loads(Path("$DEV/eval-set20/stress/songs.json").read_text()))
SONGS = {}
for s in REFS: SONGS[s] = ("refs", G/"work"/s)
for s in STRESS: SONGS[s] = ("stress", G/"stress-work"/s)
for i, s in enumerate(SET20, 1): SONGS[f"s{i:02d}"] = ("set20", G/"set20-work"/s)
SONGS["test_song"] = ("test", G/"work"/"test_song")
