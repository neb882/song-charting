"""s_summary.py: the tables. Reads <shm>/ceiling/{p1,p2,align}.json and part D's d.json (its m05 recall per song,
for the side-by-side); prints markdown (labels and numbers only, floats to 3 decimals, counts with a thousands comma)."""
import json, sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
import cl

P1 = json.loads((cl.SHM / "p1.json").read_text()); P2 = json.loads((cl.SHM / "p2.json").read_text())
AL = json.loads((cl.SHM / "align.json").read_text())
D = json.loads((cl.SCR / "m8-02/D/d.json").read_text())["summary"]["rate8_all"]["songs"]
ok = lambda l, k: AL[l][k]["ours9"]["windows_peak_ge_0.3"] > 4.5 and AL[l][k]["ours9"]["lag_mad_ms"] < 2.0
f3 = lambda x: "-" if x is None else f"{x:.3f}"
c = lambda n: f"{n:,}"


def p1_table(sel, title):
    print(f"\n**{title}**\n")
    print("| song | grid octave | charts | fast-window notes | ceiling fast (base / 6 / 8 slots) | ceiling outside (base / 6 / 8) | D m05 recall fast | D / ceiling |")
    print("|---|---|---|---|---|---|---|---|")
    pooled = {v: [0, 0, 0, 0] for v in ("base", "6", "8")}; songmean = {v: [] for v in pooled}; dm = []
    for l in cl.FAST:
        ch = {k: v for k, v in P1[l]["charts"].items() if sel(l, k)}
        fch = {k: v for k, v in ch.items() if v["base"]["fast_n"]}
        if not fch: continue
        rf = {v: float(np.mean([x[v]["fast_m"] / x[v]["fast_n"] for x in fch.values()])) for v in pooled}
        ro = {v: float(np.mean([x[v]["out_m"] / x[v]["out_n"] for x in ch.values() if x[v]["out_n"]])) for v in pooled}
        for v in pooled:
            songmean[v].append(rf[v])
            for x in ch.values():
                pooled[v][0] += x[v]["fast_m"]; pooled[v][1] += x[v]["fast_n"]; pooled[v][2] += x[v]["out_m"]; pooled[v][3] += x[v]["out_n"]
        d = D[l]["m05"]["recall"] if sel is ALL else None
        if d is not None: dm.append(d)
        print(f"| {l} | {P1[l]['octave']} | {len(fch)} | {c(sum(x['base']['fast_n'] for x in fch.values()))} | "
              f"{' / '.join(f3(rf[v]) for v in pooled)} | {' / '.join(f3(ro[v]) for v in pooled)} | {f3(d)} | "
              f"{f3(d / rf['base']) if d is not None else '-'} |")
    print()
    for v in pooled:
        print(f"- {v}: song mean fast {f3(np.mean(songmean[v]))} ({len(songmean[v])} songs); note-pooled fast "
              f"{f3(pooled[v][0] / pooled[v][1])} ({c(pooled[v][1])} notes); note-pooled outside {f3(pooled[v][2] / pooled[v][3])} ({c(pooled[v][3])} notes)")
    if dm:
        print(f"- part D's GPU m05 recall, same songs: song mean {f3(np.mean(dm))}")


ALL = lambda l, k: True
p1_table(ALL, "Part 1: recall@100 of the quantized human chart against itself, every chart (part D's rule)")
p1_table(ok, "Part 1, well-aligned charts only (part D's aligned set)")

# ---- part 2
print("\n**Part 2: the 25 badly aligned charts (part D's flag), class from the 40-window fit (9-window fit beside)**\n")
print("| song | chart | class (40 win) | good windows | slope ppm | share within 20 ms of the line | 9-win class | humans' pair class | F1@50 m05 const / line | humans' F1@50 const / line |")
print("|---|---|---|---|---|---|---|---|---|---|")
counts = {}
for l, row in P2.items():
    for k, e in row.items():
        if k == "primary" or ok(l, k): continue
        o = e["ours40"]; counts[o["class"]] = counts.get(o["class"], 0) + 1
        print(f"| {l} | {k} | {o['class']} ({o['why']}) | {o['n_good']} of {o['n_windows']} | "
              f"{'%.0f' % o['ppm'] if 'ppm' in o and abs(o['ppm']) < 1e5 else '-'} | {f3(o.get('line_within'))} | {e['ours9']['class']} | "
              f"{e['hum40']['class']} | {f3(e.get('f1_50_const'))} / {f3(e.get('f1_50_line'))} | "
              f"{f3(e.get('hum_f1_50_const'))} / {f3(e.get('hum_f1_50_line'))} |")
print(f"\n- counts (40-window class): {counts}")
oc = {}
for l, row in P2.items():
    for k, e in row.items():
        if k != "primary" and ok(l, k): oc[e["ours40"]["class"]] = oc.get(e["ours40"]["class"], 0) + 1
print(f"- the {sum(oc.values())} well-aligned alternative charts beside them: {oc}; primaries: "
      f"{dict((x, sum(1 for l in P2 if P2[l]['primary']['ours40']['class'] == x)) for x in ('constant', 'drift', 'edit', 'unclear'))}")

print("\n**Humans' agreement (guitar Expert F1@50, alternative against primary, mean over a song's alternatives)**\n")
print("| song | alternatives | constant lag | lag line for the drift pairs | under 0.6 const / line |")
print("|---|---|---|---|---|")
for l, row in P2.items():
    alts = [e for k, e in row.items() if k != "primary" and e.get("hum_f1_50_const") is not None]
    if not alts: continue
    a = float(np.mean([e["hum_f1_50_const"] for e in alts]))
    b = float(np.mean([e.get("hum_f1_50_line", e["hum_f1_50_const"]) for e in alts]))
    print(f"| {l}{' (excluded)' if l in cl.F1_LOW else ''} | {len(alts)} | {f3(a)} | {f3(b)} | {'yes' if a < 0.6 else 'no'} / {'yes' if b < 0.6 else 'no'} |")

print("\n**Part D's rate8 recall@100, GPU m05, constant lag against the lag line for the drift charts**\n")
print("| song | recall const (D's rule) | recall line | part D's |")
print("|---|---|---|---|")
sm = {"c": [], "l": []}; nt = {"c": [0, 0], "l": [0, 0]}
for l in cl.FAST:
    rc, rl = [], []
    for k, e in P2[l].items():
        if not e.get("rate8_const"): continue
        n, m, _ = e["rate8_const"]; rc.append(m / n); nt["c"][0] += m; nt["c"][1] += n
        n2, m2, _ = e.get("rate8_line") or e["rate8_const"]; rl.append(m2 / n2); nt["l"][0] += m2; nt["l"][1] += n2
    sm["c"].append(np.mean(rc)); sm["l"].append(np.mean(rl))
    print(f"| {l} | {f3(np.mean(rc))} | {f3(np.mean(rl))} | {f3(D[l]['m05']['recall'])} |")
print(f"\n- song mean: const {f3(np.mean(sm['c']))}, line {f3(np.mean(sm['l']))}; note-pooled: const "
      f"{f3(nt['c'][0] / nt['c'][1])}, line {f3(nt['l'][0] / nt['l'][1])}; songs under 0.6: const "
      f"{sum(x < 0.6 for x in sm['c'])}, line {sum(x < 0.6 for x in sm['l'])}")
