"""round_json.py FILE...: rewrites each JSON file with every float rounded to 3 decimals (the order's privacy rule);
prints nothing."""
import json, sys
def rnd(x):
    if isinstance(x, float): return round(x, 3)
    if isinstance(x, dict): return {k: rnd(v) for k, v in x.items()}
    if isinstance(x, list): return [rnd(v) for v in x]
    return x
for f in sys.argv[1:]:
    d = json.load(open(f)); open(f, "w").write(json.dumps(rnd(d), indent=1))
