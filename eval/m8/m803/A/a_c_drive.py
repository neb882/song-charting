"""a_c_drive.py [labels...]: for each song (shortest first) runs a_c_prep.py, then a_c_run.py for W 0 (break and creep only) 120 180 240, one process per job, each through
tools/heavy.sh (SONGCHARTER_HEAVY_MIN_FREE_GB=1) after MemAvailable exceeds the job's predicted peak (354 MB + 17.44 MB/s of min(W, song) + 600 MB) + 1 GiB; removes
<shm>/m8/ac after each song. Skips outputs that exist. Prints numbers per job (labels s01.. only)."""
import json, os, subprocess, sys, time
from pathlib import Path
HERE = Path(__file__).parent; sys.path.insert(0, str(HERE))
from songs_map import SONGS
lines = json.load(open(HERE/"a_line.json"))["rows"]
labels = sys.argv[1:] or sorted((l for l in SONGS if lines[l].get("dur")), key=lambda l: lines[l]["dur"])
env = dict(os.environ, SONGCHARTER_HEAVY_MIN_FREE_GB="1")
HV = "<wt>/orch/tools/heavy.sh"
def avail():
    for l in open("/proc/meminfo"):
        if l.startswith("MemAvailable"): return int(l.split()[1])/1024
for lab in labels:
    dur = lines[lab]["dur"]
    Ws = ([0] if lab in ("break", "creep") else []) + [120, 180, 240]
    todo = [W for W in Ws if not (HERE/"chunks"/f"{lab}_W{int(W)}.json").exists()]
    if not todo: continue
    subprocess.run([HV, "<repo>/.venv/bin/python", str(HERE/"a_c_prep.py"), lab], env=env, check=True, capture_output=True)
    for W in todo:
        need = 354 + 17.44*(dur if W == 0 else min(W, dur)) + 600 + 1024
        while avail() < need: time.sleep(20)
        r = subprocess.run([HV, "$DEV/allin1/bin/python", str(HERE/"a_c_run.py"), str(W), str(HERE/"chunks"/f"{lab}_W{int(W)}.json")], env=env, capture_output=True, text=True)
        print(lab, "W", W, "rc", r.returncode, r.stdout.strip()[-200:], (r.stderr.strip()[-200:] if r.returncode else ""), flush=True)
    subprocess.run([str(HERE/"a_c_clean.sh")])
