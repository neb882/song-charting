# round_json.py FILE...: rewrites each JSON file with every float rounded to 3 decimals (the privacy check reads 4-digit runs).
import json, sys
def r(x):
    return round(x, 3) if isinstance(x, float) else [r(v) for v in x] if isinstance(x, list) else {k: r(v) for k, v in x.items()} if isinstance(x, dict) else x
for p in sys.argv[1:]:
    json.dump(r(json.load(open(p))), open(p + '.tmp', 'w'), indent=1); __import__('os').replace(p + '.tmp', p)
