"""build_song.py LABEL: part C-b for one song. Reads the kept folder, the three m7 takes and the human charts (through
eval/stress.py's scorer only); hard-links the kept folder to $SONGCHARTER_GOLDEN/m7-copy/<id> with the takes added,
builds Expert guitar with `songcharter chart --takes 4` from <shm>/m7/code-C (takes.py patched: SC_M7_MARGIN,
SC_M7_FORCE) at margins 0, 0.02, 0.05, 0.10 (an arm whose window picks equal a built arm's is not rebuilt) and the
oracle arms f0-f3 and the silent-onset arms q0, q05 (SC_M7_SILENT: each take's onsets silent at 25 dB count as unmatched in the take score) (every window from take 1, 2, 3 or 4; f0 is the one-take chart through the splice path), scores each against every human chart, and writes arms/<label>.json
(numbers only) plus each arm's report.json and notes.chart under arms/<label>/. Prints one line per arm."""
import json, os, shutil, subprocess, sys, time
from pathlib import Path
C = Path(__file__).resolve().parent
sys.path.insert(0, str(C))
from songs import SONGS, TAKES, SEEDS, G
CODE = Path("<shm>/m7/code-C")
sys.path.insert(0, str(CODE))
from eval import stress as S
PY = "<checkout>/.venv/bin/python"
label = sys.argv[1]
st, sid, kept = SONGS[label]
refs = {"refs": Path("$DEV/eval/refs"), "stress": Path("$DEV/eval/stress"),
        "set20": Path("$DEV/eval-set20/stress")}[st]
song = next(s for s in S.built_songs(refs) if s["id"] == sid)
primary, inp = Path(song["folder"]), Path(song["folder"]) / "input.wav"
charts = [("primary", primary)] + [(a["label"], Path(a["folder"])) for a in song.get("alts") or []
                                   if S.scorable(Path(a["folder"]))]
out_dir = C / "arms" / label
out_dir.mkdir(parents=True, exist_ok=True)
res_path = C / "arms" / f"{label}.json"
res = json.loads(res_path.read_text()) if res_path.exists() else {"label": label, "arms": {}}

def listing(d):
    return sorted((str(p.relative_to(d)), p.stat().st_size, p.stat().st_mtime_ns, p.stat().st_ino)
                  for p in d.rglob("*") if p.is_file())

copy = G / "m7-copy" / sid
before = listing(kept)
if copy.exists():
    shutil.rmtree(copy)
copy.parent.mkdir(exist_ok=True)
subprocess.run(["cp", "-al", str(kept), str(copy)], check=True)
for seed in SEEDS:
    subprocess.run(["cp", "-al", str(TAKES / sid / f"seed_{seed}"), str(copy / "guitar" / f"seed_{seed}")], check=True)
for f in [f for f in copy.rglob("*") if f.is_file() and f.stat().st_size < 5_000_000]:
    data = f.read_bytes(); f.unlink(); f.write_bytes(data)   # small files real copies: an in-place write never reaches kept
env = dict(os.environ)
env["SONGCHARTER_SCAN_CHART"] = "<wt>/base-main/tools/scan-chart/scan.cjs"
for v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMBA_NUM_THREADS"):
    env[v] = "2"

def build(arm, margin=None, force=None, silent=False):
    e = dict(env)
    e.pop("SC_M7_MARGIN", None); e.pop("SC_M7_FORCE", None)
    if margin is not None: e["SC_M7_MARGIN"] = str(margin)
    if force is not None: e["SC_M7_FORCE"] = str(force)
    e.pop("SC_M7_SILENT", None)
    if silent: e["SC_M7_SILENT"] = "1"
    out = Path(f"<shm>/m7/C-arms/{label}/{arm}")
    if out.exists(): shutil.rmtree(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    p = subprocess.run([PY, "-m", "songcharter.cli", "chart", str(inp), "--out", str(out), "--work", str(copy),
                        "--takes", "4", "--device", "cpu", "--no-preview", "--threads", "2", "--title", label,
                        "--artist", "m7"], cwd=str(CODE), env=e, capture_output=True, text=True)
    secs = round(time.time() - t0, 1)
    if not (out / "notes.chart").is_file():
        raise RuntimeError(f"{arm}: chart exit {p.returncode}: {p.stderr[-800:]}")
    rep = json.loads((out / "report.json").read_text())
    shutil.copy(out / "report.json", out_dir / f"{arm}.report.json")
    shutil.copy(out / "notes.chart", out_dir / f"{arm}.notes.chart")
    pipe = json.loads((copy / "pipeline.json").read_text()) if (copy / "pipeline.json").exists() else {}
    stages = {s["stage"]: s.get("cached") for s in pipe.get("stages") or []}
    scores = {}
    sdir = Path(f"<shm>/m7/C-arms/{label}/scores"); sdir.mkdir(exist_ok=True)
    for lab, folder in charts:
        d = S.run_score(folder, out, inp, sdir / f"{arm}.{lab}.json", windows=30.0, env=env)
        g = S.comparison(d)["parts"].get("guitar")
        scores[lab] = None if g is None else {"f1_50": g["f1_50"], "f1_100": g["f1_100"]}
    takes = next((p.get("takes") for p in rep.get("parts", {}).values()
                  if p.get("instrument", "guitar") == "guitar" and p.get("takes")), None)
    shutil.rmtree(out)
    return {"exit": p.returncode, "seconds": secs, "stages_cached": stages, "scores": scores,
            "picks": [w["pick"] for w in (takes or {}).get("windows", [])], "takes": takes}

def picks_at(windows, m):
    out = []
    for w in windows:
        s = w["scores"]; best = max(range(len(s)), key=lambda k: (s[k], -k))
        out.append(best if s[best] > s[0] + m else 0)
    return out

try:
    arms = res["arms"]
    if "m0" not in arms:
        arms["m0"] = build("m0", 0.0); print(label, "m0", arms["m0"]["seconds"], "s", flush=True)
    wins = arms["m0"]["takes"]["windows"]
    for name, m in (("m02", 0.02), ("m05", 0.05), ("m10", 0.10)):
        if name in arms: continue
        pk = picks_at(wins, m)
        same = next((a for a, v in arms.items() if not a.startswith("f") and v.get("picks") == pk and "same_as" not in v), None)
        if same:
            arms[name] = {"same_as": same, "picks": pk}
        else:
            arms[name] = build(name, m)
            assert arms[name]["picks"] == pk, (name, pk, arms[name]["picks"])
        print(label, name, arms[name].get("same_as") or arms[name]["seconds"], flush=True)
    for k in (0, 1, 2, 3):
        name = f"f{k}"
        if name not in arms:
            arms[name] = build(name, force=k); print(label, name, arms[name]["seconds"], "s", flush=True)
    for name, m in (("q0", 0.0), ("q05", 0.05)):   # the silent-onset arms: a take's silent onsets count as unmatched
        if name not in arms:
            arms[name] = build(name, m, silent=True)
            arms[name]["same_picks_as"] = [a for a, v in arms.items() if a != name and v.get("picks") == arms[name]["picks"]]
            print(label, name, arms[name]["seconds"], "s", flush=True)
    res["windows"] = wins
    res["charts"] = [lab for lab, _ in charts]
finally:
    res_path.write_text(json.dumps(res, indent=1))
    shutil.rmtree(copy, ignore_errors=True)
    after = listing(kept)
    print(label, "kept folder unchanged:", before == after, flush=True)
    if before != after:
        (C / f"KEPT_CHANGED.{label}").write_text("changed")
