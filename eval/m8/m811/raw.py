"""raw.py: M8-11 step 1, the 16 raw takes (the engine's notes.chart, no pipeline) against sooth's primary human chart.
The takes were made from the reference's own input.wav (summary.json's inputSha256 is checked against it), so the lag
is 0; a shift scan on each take (F1@100 at -100..+100 ms) checks that. Writes out/raw.json (labels and numbers)."""
import hashlib, json, sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib as L
from lib import S

OUT = L.W811 / "out"; OUT.mkdir(exist_ok=True)
(k, prim), = [c for c in L.charts() if c[0] == "primary"]
inp_sha = hashlib.sha256((prim / "input.wav").read_bytes()).hexdigest()
ro, span = L.human(prim)
res = {"input_sha_matches": {}, "span": span, "n_human": len(ro), "takes": {}}
for arm in L.ARMS:
    for seed in L.SEEDS:
        d = L.TAKES / arm / f"seed_{seed}"
        sm = L.summary(d)
        res["input_sha_matches"][f"{arm}/{seed}"] = sm.pop("inputSha256") == inp_sha
        co, sc = L.cand(d, 0.0, span)
        sc_ = L.score(ro, co, span)
        rt = np.array([o["t"] for o in ro])
        shifts = {}
        for sh in range(-100, 101, 10):
            ct = np.array([o["t"] for o in co]) + sh / 1000.0
            p = S.match(rt, ct, 0.05)
            shifts[sh] = S.prf(len(p), len(rt), S.n_cand_eff(p, ct, span))["f1"]
        sc_["shift_f1_50"] = shifts
        res["takes"][f"{arm}/{seed}"] = {"summary": sm, **sc_}
        s = sc_["song"]; f = sc_["fast"]
        print(arm, seed, "fast rec %.3f f1 %.3f ratio %.3f | song f1 %.3f | best shift %d" %
              (f["recall"], f["f1"], f["ratio"], s["f1"], max(shifts, key=shifts.get)), flush=True)
(OUT / "raw.json").write_text(json.dumps(res, indent=1))
print("input sha all match:", all(res["input_sha_matches"].values()))
