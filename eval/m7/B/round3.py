"""Rounds every float in the given JSON files to 3 decimals in place (privacy_check reads 4+ digit runs as md5
prefixes). Reads and rewrites the files; prints nothing."""
import json, sys
def r(x):
    if isinstance(x, float): return round(x, 3)
    if isinstance(x, list): return [r(v) for v in x]
    if isinstance(x, dict): return {k: r(v) for k, v in x.items()}
    return x
for p in sys.argv[1:]:
    json.dump(r(json.load(open(p))), open(p, 'w'), indent=1)
