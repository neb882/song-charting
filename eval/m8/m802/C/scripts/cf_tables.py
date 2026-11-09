"""cf_tables.py: reads C/cf_m05.json (cf_contour.py) and prints C-f's tables (markdown): per song and pooled."""
import json, sys
from pathlib import Path
d = json.loads((Path(__file__).resolve().parents[1] / "cf_m05.json").read_text())
print("| song | fast onsets (runs) | pairs vs primary | human up/down/same | ours up/down/same | ours | pyin | pyin_step1 | cqt | hs | humans (alt vs primary) |")
print("|" + "---|" * 11)
for r in d["rows"]:
    c = r["charts"][0]; h, o = c["human_dir"], c["ours_dir"]
    print(f"| {r['label']} | {r['n_fast_onsets']} ({r['n_runs']}) | {c['n_pairs']} | {h['up']}/{h['down']}/{h['same']} | {o['up']}/{o['down']}/{o['same']} | "
          f"{c['agree_ours']} | {c['agree_pyin']} | {c['agree_pyin_step1']} | {c['agree_cqt']} | {c['agree_hs']} | {r['ceiling_mean']} |")
for sc, P in d["pooled"].items():
    print(f"\n**{sc}** ({P['n_songs']} songs): ours {P['ours']}, the humans' own (alt vs primary) {P['ceiling']['mean']}\n")
    print("| tracker | direction agreement | minus ours [CI] | songs up 0.10 | re-lane: score.py contour (100 ms) change | exact lanes change | fast-run contour (50 ms) change |")
    print("|---|---|---|---|---|---|---|")
    f = lambda x: f"{x['mean']:+.3f} [{x['lo']:+.3f}, {x['hi']:+.3f}]"
    for v in ("pyin", "pyin_conf", "pyin_step1", "cqt", "cqt_conf", "hs", "hs_conf", "none"):
        a, R = P["agree_" + v], P["relane_" + v]
        print(f"| {v} | {a['mean']} | {f(a['vs_ours'])} | {a['songs_up_0.10']} | {f(R['contour100']['diff'])} | {f(R['exact100']['diff'])} | {f(R['contour_fast50']['diff'])} |")
