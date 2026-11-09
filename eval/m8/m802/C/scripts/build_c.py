"""build_c.py LABEL...: M8-02 part C's variant arms. Reads part B's assemble configs (B/configs/<label>.<arm>.json for
the GPU m05, CPU m05 and CPU one arms) and builds, with the v0.4.0 tag's code copied to <shm>/m8/m2/code (one
uncommitted patch: quantize.sustain_kept's guitar/bass Expert and Hard floor max(200 ms, min(0.75 beat, cap)) when
SC_M8_CAP is set), three variants per arm as M7-01 part A did: V1 hopo "source" + cap 300 ms, V2 "natural" + 400 ms,
V3 "forced" (today) + 500 ms; plus V0 (no change) for the check that the copy reproduces part B's chart. Keeps each
build's notes.chart, song.ini and report.json under <shm>/m8/m2/var/<arm>.<variant>/<label>/ and deletes the rest.
Prints one line per build (label, arm, variant, seconds)."""
import json, os, shutil, subprocess, sys, time
from pathlib import Path
M = Path(__file__).resolve().parents[2]
CODE = Path("<shm>/m8/m2/code"); VAR = Path("<shm>/m8/m2/var")
PY = "<checkout>/.venv/bin/python"
VARIANTS = {"V1": ("source", 300), "V2": ("natural", 400), "V3": ("forced", 500)}
ARMS = ("m05", "cpu_m05", "cpu_one")
env = dict(os.environ)
env.update(SONGCHARTER_SCAN_CHART="<wt>/base-main/tools/scan-chart/scan.cjs")
for v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMBA_NUM_THREADS"):
    env[v] = "2"
for v in ("SC_M7_MARGIN", "SC_M7_FORCE", "SC_M7_SILENT", "SC_M8_CAP"):
    env.pop(v, None)


def build(label, arm, vname, hopo, cap):
    dst = VAR / f"{arm}.{vname}" / label
    if (dst / "notes.chart").is_file():
        return
    cfg = json.loads((M / "B" / "configs" / f"{label}.{arm}.json").read_text())
    for p in cfg["parts"]:
        if p["instrument"] == "guitar" and hopo:
            p["hopo"] = hopo
    out = Path("<shm>/m8/m2/tmp") / label
    if out.exists(): shutil.rmtree(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    cfg["output"] = str(out)
    cp = Path("<shm>/m8/m2/cfg") / f"{label}.{arm}.{vname}.json"
    cp.parent.mkdir(parents=True, exist_ok=True); cp.write_text(json.dumps(cfg))
    e = dict(env)
    if cap: e["SC_M8_CAP"] = str(cap / 1000.0)
    t0 = time.time()
    p = subprocess.run([PY, "-m", "songcharter.cli", "assemble", str(cp), "--out", str(out)], cwd=str(CODE), env=e,
                       capture_output=True, text=True)
    if not (out / "notes.chart").is_file():
        raise RuntimeError(f"{label} {arm} {vname}: exit {p.returncode}: {p.stderr[-600:]}")
    dst.mkdir(parents=True, exist_ok=True)
    for f in ("notes.chart", "song.ini", "report.json"):
        if (out / f).exists(): shutil.copy2(out / f, dst / f)
    shutil.rmtree(out); cp.unlink()
    print(label, arm, vname, round(time.time() - t0, 1), flush=True)


for label in sys.argv[1:]:
    if label == "--check":
        continue
    if "--check" in sys.argv:
        build(label, "m05", "V0", None, None)
        continue
    for arm in ARMS:
        for vname, (hopo, cap) in VARIANTS.items():
            build(label, arm, vname, hopo, cap)
