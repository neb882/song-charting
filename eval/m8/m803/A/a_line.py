"""a_line.py: reads each kept folder's sections/engine.json (allin1 peak_rss_mb, input.duration_s) and pipeline.json sections stage
(peak_rss_mb.self, child_peak_rss_mb, min_available_ram_mb) and pipeline.json top peak_rss_mb; prints and writes A/a_line.json (labels only, 3 dp)."""
import json, sys, numpy as np
sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent))
from songs_map import SONGS
rows = {}
for lab, (st, d) in SONGS.items():
    try:
        e = json.loads((d/"sections/engine.json").read_text()); p = json.loads((d/"pipeline.json").read_text())
    except Exception as ex:
        rows[lab] = {"err": type(ex).__name__}; continue
    sec = [s for s in p["stages"] if s["stage"] == "sections"]
    sec = sec[0] if sec else {}
    rows[lab] = dict(dur=e["input"]["duration_s"], allin1_peak=e["allin1"].get("peak_rss_mb"), child=sec.get("child_peak_rss_mb"),
        parent_sec=sec.get("peak_rss_mb", {}).get("self"), minavail=sec.get("min_available_ram_mb"), cached=sec.get("cached"),
        parent_hwm=(p.get("peak_rss_mb") or {}).get("self"), sec_seconds=e["seconds"].get("total") if isinstance(e["seconds"], dict) else None)
ok = {k: v for k, v in rows.items() if "err" not in v and v.get("allin1_peak")}
x = np.array([v["dur"] for v in ok.values()]); y = np.array([v["allin1_peak"] for v in ok.values()])
b, a = np.polyfit(x, y, 1); res = y - (a + b*x)
out = {"n": len(ok), "intercept_mb": a, "slope_mb_per_s": b, "gib_per_min": b*60/1024, "res_min": res.min(), "res_max": res.max(), "rows": rows}
px = np.array([v["dur"] for v in ok.values() if v.get("parent_hwm")]); py = np.array([v["parent_hwm"] for v in ok.values() if v.get("parent_hwm")])
if len(px) > 2:
    pb, pa = np.polyfit(px, py, 1); out["parent_hwm_fit"] = {"intercept_mb": pa, "slope_mb_per_s": pb, "n": len(px), "res_min": (py-(pa+pb*px)).min(), "res_max": (py-(pa+pb*px)).max()}
sx = np.array([v["dur"] for v in ok.values() if v.get("parent_sec")]); sy = np.array([v["parent_sec"] for v in ok.values() if v.get("parent_sec")])
if len(sx) > 2:
    pb, pa = np.polyfit(sx, sy, 1); out["parent_at_sections_fit"] = {"intercept_mb": pa, "slope_mb_per_s": pb, "n": len(sx)}
def rnd(o):
    if isinstance(o, float): return round(o, 3)
    if isinstance(o, dict): return {k: rnd(v) for k, v in o.items()}
    return o
out = rnd(out); json.dump(out, open(str(__import__('pathlib').Path(__file__).parent/"a_line.json"), "w"), indent=1)
print({k: v for k, v in out.items() if k != "rows"})
for k, v in sorted(rows.items(), key=lambda kv: kv[1].get("dur", 0)): print(k, v)
