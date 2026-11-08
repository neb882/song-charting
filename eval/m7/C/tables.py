"""tables.py: reads results.json and deltas.json; prints the report's markdown tables (numbers only, songs by label)."""
import json
from pathlib import Path
C = Path(__file__).resolve().parent
r = json.loads((C / "results.json").read_text()); d = json.loads((C / "deltas.json").read_text()); s = r["songs"]
A = ["one", "m0", "m02", "m05", "m10", "q0", "q05"]
f = lambda x: f"{x:.3f}"
print("### C-c per song: guitar Expert F1@50, against the primary / the mean over the song's human charts\n")
print("| song | set | charts | humans | " + " | ".join(A) + " | takes alone f0/f1/f2/f3 (mean) |")
print("|---|---|---|---|" + "---|" * len(A) + "---|")
for k, v in s.items():
    a = v["arms"]
    print(f"| {k} | {v['set']} | {v['charts']} | {v['humans_f1_50'] if v['humans_f1_50'] is not None else '—'} | " +
          " | ".join(f"{f(a[x]['p50'])} / {f(a[x]['mean50'])}" for x in A) + " | " +
          "/".join(f(a[x]["mean50"]) for x in ("f0", "f1", "f2", "f3")) + " |")
print("\n### C-c per song: F1@100 against the primary / the mean\n")
print("| song | " + " | ".join(A) + " |"); print("|---|" + "---|" * len(A))
for k, v in s.items():
    a = v["arms"]; print(f"| {k} | " + " | ".join(f"{f(a[x]['p100'])} / {f(a[x]['mean100'])}" for x in A) + " |")
print("\n### Windows and seams per song (m0/m02/m05/m10/q0/q05)\n")
M = ["m0", "m02", "m05", "m10", "q0", "q05"]
print("| song | windows (with human notes) | switched from the kept take | seams | windows that differ from m05 (m0/m02/m10/q0/q05) | windows where the picked take's F1 vs the primary is below the best take's by > 0.05 |")
print("|---|---|---|---|---|---|")
for k, v in s.items():
    sw = "/".join(str(v["switched"].get(m, "—")) for m in M if m in v["switched"])
    se = "/".join(str(v["seams"].get(m, "—")) for m in M if m in v["seams"])
    df = "/".join(str(len(v["differs_from_m05"][m])) for m in ("m0", "m02", "m10", "q0", "q05") if m in v["differs_from_m05"])
    lo = "/".join(str(v["loses_by_f1_0.05"][m]) for m in M)
    print(f"| {k} | {v['windows']} ({v['windows_with_humans']}) | {sw} | {se} | {df} | {lo} |")
tot = lambda key, m: sum(v[key][m] for v in s.values())
print("\nTotals over the 23 songs: windows " + str(sum(v["windows"] for v in s.values())) +
      "; switched " + ", ".join(f"{m} {tot('switched', m)}" for m in M) +
      "; seams " + ", ".join(f"{m} {tot('seams', m)}" for m in M) +
      "; picked take below the best by > 0.05 F1 " + ", ".join(f"{m} {tot('loses_by_f1_0.05', m)}" for m in M) +
      "; by any F1 " + ", ".join(f"{m} {tot('loses_by_f1', m)}" for m in M) +
      "; m0 windows where another take has more matched onsets: " + str(sum(len(v['m0_loses_to_better_take']) for v in s.values())))
print("\n### Pooled\n")
for g, p in r["pooled"].items():
    print(f"**{g}** ({p['n']} songs)\n")
    print("| measure | " + " | ".join(A) + " | best take per song (oracle) | mean of the 4 takes |")
    print("|---|" + "---|" * (len(A) + 2))
    for meas in ("p50", "p100", "mean50", "mean100"):
        x = p[meas]
        print(f"| {meas} | " + " | ".join(f(x[a]) for a in A) + f" | {f(x['oracle_best_take_per_song'])} | {f(x['oracle_mean_of_takes'])} |")
    print("\nEach arm minus m05 (diff [95 % CI], paired bootstrap over songs, 10,000 resamples):\n")
    print("| measure | " + " | ".join(a for a in A if a != "m05") + " |"); print("|---|" + "---|" * (len(A) - 1))
    for meas in ("p50", "p100", "mean50", "mean100"):
        x = p[meas]["vs_m05"]
        print(f"| {meas} | " + " | ".join(f"{x[a]['diff']:+.4f} [{x[a]['ci'][0]:+.4f}, {x[a]['ci'][1]:+.4f}]" for a in A if a != "m05") + " |")
    print("\nEach splice arm minus the one-take chart:\n")
    print("| measure | " + " | ".join(a for a in A if a != "one") + " |"); print("|---|" + "---|" * (len(A) - 1))
    for meas in ("p50", "mean50"):
        x = p[meas]["vs_one"]
        print(f"| {meas} | " + " | ".join(f"{x[a]['diff']:+.4f} [{x[a]['ci'][0]:+.4f}, {x[a]['ci'][1]:+.4f}]" for a in A if a != "one") + " |")
    print()
print("**All 23 songs, no exclusion** (primary F1@50, arm minus m05): " + "; ".join(
    f"{a} {x[0]:+.4f} [{x[1]:+.4f}, {x[2]:+.4f}], worst song {d['worst'][a][0]} {d['worst'][a][1]:+.4f}"
    for a, x in d["all23_vs_m05_p50"].items()))
