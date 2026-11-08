"""deltas.py: reads results.json; writes deltas.json (per song, each arm minus m05 on primary F1@50, the worst song,
the pooled figure over all 23 songs with no exclusion and its bootstrap CI) and prints them."""
import json, numpy as np
from pathlib import Path
C = Path(__file__).resolve().parent
r = json.loads((C / "results.json").read_text()); s = r["songs"]
rng = np.random.default_rng(7)
def boot(d):
    d = np.array(d); m = d[rng.integers(0, len(d), (10000, len(d)))].mean(axis=1)
    return [round(float(d.mean()), 4), round(float(np.percentile(m, 2.5)), 4), round(float(np.percentile(m, 97.5)), 4)]
out = {"per_song_vs_m05_p50": {}, "worst": {}, "all23_vs_m05_p50": {}, "all23_mean_p50": {}}
arms = ["one", "m0", "m02", "m10", "q0", "q05"]
for a in arms:
    d = {k: round(v["arms"][a]["p50"] - v["arms"]["m05"]["p50"], 4) for k, v in s.items()}
    out["per_song_vs_m05_p50"][a] = d
    out["worst"][a] = min(d.items(), key=lambda x: x[1])
    out["all23_vs_m05_p50"][a] = boot(list(d.values()))
for a in arms + ["m05"]:
    out["all23_mean_p50"][a] = round(float(np.mean([v["arms"][a]["p50"] for v in s.values()])), 4)
(C / "deltas.json").write_text(json.dumps(out, indent=1))
for a in arms:
    print(a, out["all23_vs_m05_p50"][a], "worst", out["worst"][a], "down>0.01:", [k for k, x in out["per_song_vs_m05_p50"][a].items() if x < -0.01])
print(out["all23_mean_p50"])
