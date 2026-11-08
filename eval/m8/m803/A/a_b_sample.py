"""a_b_sample.py LABEL: A-b. Reads the kept folder's pipeline.json (input path only, never printed), copies the kept folder without sections/
into <shm>/m8/ab/LABEL (stems symlinked read-only, decode.wav copied), runs `songcharter chart ... --no-preview --threads 2` from the v0.4.0 checkout
(cold sections stage, all else cached), samples VmRSS of the tree every 0.5 s (the parent; allin1's runner child apart) and /proc/meminfo MemAvailable,
stops 4 s after sections/segments.json appears, deletes the copy. Prints a summary (numbers only); writes A/ab_LABEL.json with the series."""
import json, os, shutil, signal, subprocess, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from songs_map import SONGS
HERE = Path(__file__).parent
label = sys.argv[1]
CODE = "<shm>/m8/code-cpu"
kept = SONGS[label][1]
pj = json.loads((kept/"pipeline.json").read_text())
inp = pj["input"]; opts = pj["options"]
dst = Path("<shm>/m8/ab")/label
if dst.exists(): shutil.rmtree(dst)
dst.mkdir(parents=True)
work = dst/"work"; work.mkdir()
for e in kept.iterdir():
    if e.name in ("sections",) or e.name.endswith(".lock"): continue
    if e.name == "stems": (work/"stems").symlink_to(e)
    elif e.is_dir(): shutil.copytree(e, work/e.name, symlinks=True)
    else: shutil.copy2(e, work/e.name)
def rd(pid, key):
    try:
        for l in open(f"/proc/{pid}/status"):
            if l.startswith(key): return int(l.split()[1])/1024
    except OSError: return None
def kids(root):
    ch = {}
    for d in os.listdir("/proc"):
        if d.isdigit():
            try: pp = int(open(f"/proc/{d}/stat").read().rsplit(")", 1)[1].split()[1])
            except OSError: continue
            ch.setdefault(pp, []).append(int(d))
    out, st = [], [root]
    while st:
        p = st.pop()
        for c in ch.get(p, []): out.append(c); st.append(c)
    return out
def avail():
    for l in open("/proc/meminfo"):
        if l.startswith("MemAvailable"): return int(l.split()[1])/1024
cmd = [f"<repo>/.venv/bin/python", "-m", "songcharter.cli", "chart", inp, "--out", str(dst/"out"), "--work", str(work),
       "--levels", "expert", "--takes", "1", "--device", "cpu", "--threads", "2", "--no-preview"]
env = dict(os.environ, PYTHONPATH=CODE, SONGCHARTER_ALLIN1_PYTHON="$DEV/allin1/bin/python", SONGCHARTER_AUTOCHART="<repo>/eval/tools/autochart", SONGCHARTER_GOLDEN="$DEV/golden")
logf = open(dst/"log.txt", "w")
t0 = time.time()
proc = subprocess.Popen(cmd, cwd=CODE, env=env, stdout=logf, stderr=subprocess.STDOUT, start_new_session=True)
series = []; done_t = None; reason = "done"
seg = work/"sections"/"segments.json"
while proc.poll() is None:
    t = time.time()-t0
    par = rd(proc.pid, "VmRSS"); parhwm = rd(proc.pid, "VmHWM")
    child = other = 0.0; chwm = 0.0; nchild = 0
    for k in kids(proc.pid):
        r = rd(k, "VmRSS")
        if r is None: continue
        try: isa = b"allin1_runner" in open(f"/proc/{k}/cmdline", "rb").read()
        except OSError: isa = False
        if isa: child += r; chwm = max(chwm, rd(k, "VmHWM") or 0); nchild += 1
        else: other += r
    a = avail()
    series.append((round(t, 1), round(par or 0, 1), round(child, 1), round(other, 1), round(a, 0)))
    if a < 900: reason = "memavail<900MB: killed"; break
    if seg.exists() and done_t is None: done_t = t
    if done_t is not None and t > done_t + 4: reason = "sections done, stopped"; break
    if t > 1500: reason = "timeout"; break
    time.sleep(0.5)
if proc.poll() is None:
    os.killpg(proc.pid, signal.SIGTERM); time.sleep(2)
    try: os.killpg(proc.pid, signal.SIGKILL)
    except OSError: pass
res_ok = (work/"sections"/"engine.json").exists()
eng = json.loads((work/"sections"/"engine.json").read_text()) if res_ok else {}
ch_phase = [s for s in series if s[2] > 0]
out = {"label": label, "reason": reason, "duration_s": eng.get("input", {}).get("duration_s"), "runner_peak_rss_mb": (eng.get("allin1") or {}).get("peak_rss_mb"),
       "runner_seconds": eng.get("seconds"), "series_t_parent_child_other_memavail": series,
       "parent_max_all": max(s[1] for s in series), "parent_max_while_child": max((s[1] for s in ch_phase), default=None),
       "parent_at_child_start": ch_phase[0][1] if ch_phase else None, "parent_min_while_child": min((s[1] for s in ch_phase), default=None),
       "child_max": max((s[2] for s in series), default=None), "tree_max_while_child": max((s[1]+s[2]+s[3] for s in ch_phase), default=None),
       "memavail_min": min(s[4] for s in series), "child_phase_s": (ch_phase[-1][0]-ch_phase[0][0]) if ch_phase else None,
       "parent_before_child_max": max((s[1] for s in series if s[2] == 0 and (not ch_phase or s[0] < ch_phase[0][0])), default=None)}
json.dump(out, open(HERE/f"ab_{label}.json", "w"))
print({k: v for k, v in out.items() if k not in ("series_t_parent_child_other_memavail", "runner_seconds")}, flush=True)
if "--keep" not in sys.argv: shutil.rmtree(dst, ignore_errors=True)
