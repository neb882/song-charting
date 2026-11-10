"""pipe.py ARM SEED: M8-11 step 2, one take through today's pipeline (main's assemble, as a copy in code/), 1 take,
as the friend gets it: the kept sooth folder's assemble.json with the guitar's source replaced by the take (no takes
list), assembled by `python -m songcharter.cli assemble` under tools/heavy.sh. Then the output's audio (every file
summed, as score.py's --cand does) is aligned to the reference's input.wav with score.py's align, the Expert guitar is
scored as raw.py does, and the output's audio is deleted. Writes pipe/<arm>_<seed>/ (notes.chart, song.ini,
report.json) and out/pipe/<arm>_<seed>.json."""
import json, os, shutil, subprocess, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib as L
from lib import S

arm, seed = sys.argv[1], int(sys.argv[2])
KEPT = Path("$DEV/golden") / "stress-work" / "sooth"
PY = "<checkout>/.venv/bin/python"
HEAVY = "<checkout>/tools/heavy.sh"
out = L.W811 / "pipe" / f"{arm}_{seed}"
res_p = L.W811 / "out" / "pipe" / f"{arm}_{seed}.json"
res_p.parent.mkdir(parents=True, exist_ok=True)
cfg = json.loads((KEPT / "assemble.json").read_text())
for p in cfg["parts"]:
    if p["instrument"] == "guitar":
        p["source"] = str(L.TAKES / arm / f"seed_{seed}" / "notes.chart")
        p.pop("takes", None)
cfg["output"] = str(out)
cp = L.W811 / "pipe" / f"{arm}_{seed}.assemble.json"
cp.parent.mkdir(parents=True, exist_ok=True)
cp.write_text(json.dumps(cfg, indent=1))
if out.exists():
    shutil.rmtree(out)
env = dict(os.environ, SONGCHARTER_HEAVY_MIN_FREE_GB="1", PYTHONDONTWRITEBYTECODE="1")
for v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMBA_NUM_THREADS"):
    env[v] = "2"
t0 = time.time()
p = subprocess.run([HEAVY, PY, "-m", "songcharter.cli", "assemble", str(cp), "--out", str(out)], cwd=str(L.CODE),
                   env=env, capture_output=True, text=True)
secs = round(time.time() - t0, 1)
if not (out / "notes.chart").is_file():
    sys.exit(f"{arm} {seed}: assemble exit {p.returncode}: {p.stderr[-1500:]}")
(k, prim), = [c for c in L.charts() if c[0] == "primary"]
x = S.decode(str(prim / "input.wav"))
files = S.audio_files(str(out))
c = S.load_mix(str(out), files, [])
al = S.align(x, c)
ro, span = L.human(prim)
co, sc = L.cand(out, al["lag_ms"], span)
r = L.score(ro, co, span)
rep = json.loads((out / "report.json").read_text())
r["pipe"] = {"seconds": secs, "exit": p.returncode, "lag_ms": al["lag_ms"], "lag_mad_ms": al["lag_mad_ms"],
             "good_windows": al["windows_peak_ge_0.3"], "audio_files": len(files),
             "gate_ok": (out / "notes.chart").is_file() and not str(out).endswith(".failed")}
(res_p).write_text(json.dumps(r, indent=1))
for f in files:
    (out / f).unlink()
for f in out.iterdir():
    if f.suffix.lower() in S.AUDIO_EXT or f.suffix.lower() in (".png", ".jpg", ".mp4", ".webm"):
        f.unlink()
f, s = r["fast"], r["song"]
print(arm, seed, f"{secs}s lag {al['lag_ms']:+.1f} fast rec {f['recall']:.3f} f1 {f['f1']:.3f} ratio {f['ratio']:.3f} "
      f"| song f1 {s['f1']:.3f}", flush=True)
