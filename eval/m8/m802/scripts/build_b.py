"""build_b.py PHASE LABEL: M8-02 part B's arms for one song, at the v0.4.0 tag's code (<shm>/m8/code, margin.patch
applied as uncommitted files). Reads the kept folder, the three m7 CPU takes, the zip's four GPU takes and the human
charts (only through eval/stress.py's run_score). Writes B/arms/<label>.json (numbers only: picks, window scores and
onset counts, F1@50 / F1@100 per chart, seconds), B/configs/<label>.<arm>.json (the assemble configs; paths only to
the kept folder, m7-takes and the zip) and keeps the full folders of the GPU one / m05 and the CPU one / cpu_m05 arms
under <shm>/m8/keep/<arm>/<label> (song.ogg hard-linked to one copy per song). Prints one line per arm (label only).
PHASE p1: the copy route -> cpu_m05 (songcharter chart --takes 4) and its assemble.json; the route check (assemble of
that config, guitar Expert identical note for note); the GPU one and m05, the CPU one. PHASE p2: m0, m02, m10 (unless
their picks equal a built arm's), f0-f3, q05 on the GPU takes, cf0-cf3 (the CPU takes alone).
Usage: python build_b.py p1|p2 <label>"""
import json, os, shutil, subprocess, sys, time
from pathlib import Path
M = Path(__file__).resolve().parent.parent
CODE = Path("<shm>/m8/code")
sys.path.insert(0, str(CODE))
from eval import stress as S          # noqa: E402
from eval.scorer import score as SC   # noqa: E402
DEV = Path("$DEV"); G = DEV / "golden"
ZIP = M / "zip" / "gpu_results" / "takes"
PY = "<checkout>/.venv/bin/python"
REFS = ["all_the_small_things", "creep", "drunk_drivers", "kimochi_warui", "lucretia", "take_me_out"]
STRESS = ["break", "pm2", "sooth", "troop"]
SET20 = sorted(s["id"] for s in json.loads((DEV / "eval-set20/stress/songs.json").read_text()))
SONGS = {}
for s in REFS: SONGS[s] = ("refs", s, G / "work" / s, ZIP / s)
for s in STRESS: SONGS[s] = ("stress", s, G / "stress-work" / s, ZIP / "stress" / s)
for i, s in enumerate(SET20, 1): SONGS[f"s{i:02d}"] = ("set20", s, G / "set20-work" / s, ZIP / "set20" / f"s{i:02d}")
SEEDS = (101, 202, 303)
phase, label = sys.argv[1], sys.argv[2]
st, sid, kept, gpu = SONGS[label]
refs = {"refs": DEV / "eval/refs", "stress": DEV / "eval/stress", "set20": DEV / "eval-set20/stress"}[st]
song = next(s for s in S.built_songs(refs) if s["id"] == sid)
primary, inp = Path(song["folder"]), Path(song["folder"]) / "input.wav"
charts = [("primary", primary)] + [(a["label"], Path(a["folder"])) for a in song.get("alts") or []
                                   if S.scorable(Path(a["folder"]))]
(M / "B" / "arms").mkdir(parents=True, exist_ok=True); (M / "B" / "configs").mkdir(exist_ok=True)
res_path = M / "B" / "arms" / f"{label}.json"
res = json.loads(res_path.read_text()) if res_path.exists() else {"label": label, "arms": {}}
res["charts"] = [c for c, _ in charts]
SHM = Path("<shm>/m8"); KEEP = SHM / "keep"; KEEP_ARMS = ("one", "m05", "cpu_one", "cpu_m05")
os.environ["SONGCHARTER_SCAN_CHART"] = "<wt>/base-main/tools/scan-chart/scan.cjs"
env = dict(os.environ)
env["SONGCHARTER_SCAN_CHART"] = "<wt>/base-main/tools/scan-chart/scan.cjs"
env.update(EVAL_DATA=str(DEV / "eval"), SONGCHARTER_GOLDEN=str(G), SONGCHARTER_ALLIN1_PYTHON=str(DEV / "allin1/bin/python"),
           SONGCHARTER_AUTOCHART="<checkout>/eval/tools/autochart")
for v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMBA_NUM_THREADS"):
    env[v] = "2"
for v in ("SC_M7_MARGIN", "SC_M7_FORCE", "SC_M7_SILENT"):
    env.pop(v, None)


def listing(d):
    return sorted((str(p.relative_to(d)), p.stat().st_size, p.stat().st_mtime_ns, p.stat().st_ino)
                  for p in d.rglob("*") if p.is_file())


def guitar_notes(folder):
    sc = SC.scan(str(folder))
    for t in sc.get("tracks") or []:
        if t["instrument"] == "guitar" and t["difficulty"] == "expert":
            return [(n["tick"], n["type"], n["length"], tuple(n["flags"])) for n in t["notes"]]
    return []


def score(arm, out):
    scores = {}
    sdir = SHM / "scores" / label; sdir.mkdir(parents=True, exist_ok=True)
    for lab, folder in charts:
        d = S.run_score(folder, out, inp, sdir / f"{arm}.{lab}.json", windows=30.0, env=env)
        g = S.comparison(d)["parts"].get("guitar")
        scores[lab] = None if g is None else {"f1_50": g["f1_50"], "f1_100": g["f1_100"]}
    shutil.rmtree(sdir, ignore_errors=True)
    return scores


def takes_info(rep):
    t = next((p.get("takes") for p in rep.get("parts", {}).values()
              if p.get("instrument", "guitar") == "guitar" and p.get("takes")), None)
    if not t:
        return None
    return {"windows": [{"start": w["start"], "end": w["end"], "onsets": w["onsets"], "scores": w["scores"],
                         "pick": w["pick"]} for w in t["windows"]], "picked": t.get("picked"), "onsets": t.get("onsets")}


def finish(arm, out, secs, extra=None):
    rep = json.loads((out / "report.json").read_text())
    ti = takes_info(rep)
    r = {"seconds": secs, "scores": score(arm, out), "picks": [w["pick"] for w in ti["windows"]] if ti else None,
         "takes": ti, **(extra or {})}
    (SHM / "charts" / arm).mkdir(parents=True, exist_ok=True)   # every arm's notes.chart (small), for the analysis
    shutil.copy2(out / "notes.chart", SHM / "charts" / arm / f"{label}.notes.chart")
    if arm in KEEP_ARMS:
        dst = KEEP / arm / label
        if dst.exists(): shutil.rmtree(dst)
        dst.parent.mkdir(parents=True, exist_ok=True)
        ogg = KEEP / "_audio" / label / "song.ogg"
        ogg.parent.mkdir(parents=True, exist_ok=True)
        if not ogg.exists() and (out / "song.ogg").exists():
            shutil.copy2(out / "song.ogg", ogg)
        dst.mkdir()
        for f in out.iterdir():
            if f.is_file() and f.name != "song.ogg":
                shutil.copy2(f, dst / f.name)
        if ogg.exists():
            os.link(ogg, dst / "song.ogg")
    shutil.rmtree(out)
    return r


def assemble(arm, cfg, margin=None, force=None, silent=False):
    e = dict(env)
    if margin is not None: e["SC_M7_MARGIN"] = str(margin)
    if force is not None: e["SC_M7_FORCE"] = str(force)
    if silent: e["SC_M7_SILENT"] = "1"
    out = SHM / "arms" / arm / label
    if out.exists(): shutil.rmtree(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    cfg = dict(cfg, output=str(out))
    cp = M / "B" / "configs" / f"{label}.{arm}.json"
    cp.write_text(json.dumps(cfg, indent=1))
    t0 = time.time()
    p = subprocess.run([PY, "-m", "songcharter.cli", "assemble", str(cp), "--out", str(out)], cwd=str(CODE), env=e,
                       capture_output=True, text=True)
    if not (out / "notes.chart").is_file():
        raise RuntimeError(f"{arm}: assemble exit {p.returncode}: {p.stderr[-800:]}")
    return out, round(time.time() - t0, 1)


def gpu_cfg(base, takes=True, source=None):
    c = json.loads(json.dumps(base))
    for p in c["parts"]:
        if p["instrument"] == "guitar":
            p["source"] = source or str(gpu / "seed_20260609" / "notes.chart")
            if takes:
                p["takes"] = [str(gpu / f"seed_{s}" / "notes.chart") for s in SEEDS]
            else:
                p.pop("takes", None)
    return c


def picks_at(windows, m):
    out = []
    for w in windows:
        s = w["scores"]; best = max(range(len(s)), key=lambda k: (s[k], -k))
        out.append(best if s[best] > s[0] + m else 0)
    return out


arms = res["arms"]
cfg_path = M / "B" / "configs" / f"{label}.cpu_m05.json"
try:
    if phase == "p1":
        if "cpu_m05" not in arms:
            copy = G / "m8-copy" / sid
            before = listing(kept)
            try:
                if copy.exists(): shutil.rmtree(copy)
                copy.parent.mkdir(exist_ok=True)
                subprocess.run(["cp", "-al", str(kept), str(copy)], check=True)
                for seed in SEEDS:
                    subprocess.run(["cp", "-al", str(G / "m7-takes" / sid / f"seed_{seed}"), str(copy / "guitar" / f"seed_{seed}")], check=True)
                for f in [f for f in copy.rglob("*") if f.is_file() and f.stat().st_size < 5_000_000]:
                    data = f.read_bytes(); f.unlink(); f.write_bytes(data)
                out = SHM / "arms" / "cpu_m05" / label
                if out.exists(): shutil.rmtree(out)
                out.parent.mkdir(parents=True, exist_ok=True)
                t0 = time.time()
                p = subprocess.run([PY, "-m", "songcharter.cli", "chart", str(inp), "--out", str(out), "--work", str(copy),
                                    "--takes", "4", "--device", "cpu", "--no-preview", "--threads", "2", "--title", label,
                                    "--artist", "m8"], cwd=str(CODE), env=env, capture_output=True, text=True)
                secs = round(time.time() - t0, 1)
                if not (out / "notes.chart").is_file():
                    raise RuntimeError(f"cpu_m05: chart exit {p.returncode}: {p.stderr[-800:]}")
                pipe = json.loads((copy / "pipeline.json").read_text())
                stages = {s["stage"]: s.get("cached") for s in pipe.get("stages") or []}
                txt = (copy / "assemble.json").read_text()
                for seed in SEEDS:
                    txt = txt.replace(str(copy / "guitar" / f"seed_{seed}") + "/", str(G / "m7-takes" / sid / f"seed_{seed}") + "/")
                cfg = json.loads(txt)
                regen = []   # a file the tag's chart rebuilt in the copy (it differs from the kept one): kept in shm

                def repath(x):
                    if not isinstance(x, str) or not x.startswith(str(copy) + "/"):
                        return x
                    rel = Path(x).relative_to(copy)
                    k = kept / rel
                    if k.is_file() and k.read_bytes() == Path(x).read_bytes():
                        return str(k)
                    dst = SHM / "cfgfiles" / label / rel
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(x, dst)
                    regen.append(str(rel.parent.name + "/" + rel.name))
                    return str(dst)
                for p_ in cfg["parts"]:
                    p_["source"] = repath(p_["source"])
                    p_["takes"] = [repath(x) for x in p_.get("takes", [])] if "takes" in p_ else p_.pop("takes", None)
                    if p_.get("takes") is None: p_.pop("takes", None)
                cfg["stems"] = {k_: repath(v_) for k_, v_ in (cfg.get("stems") or {}).items()}
                for k_ in ("audio", "sections", "album_art", "background"):
                    if k_ in cfg: cfg[k_] = repath(cfg[k_])
                assert str(copy) not in json.dumps(cfg), "a copy path left in the config"
                res["regenerated_files"] = regen
                missing = []
                for p_ in cfg["parts"]:
                    for x in [p_["source"]] + p_.get("takes", []):
                        if not Path(x).exists(): missing.append(x)
                for x in list((cfg.get("stems") or {}).values()) + [cfg["audio"], cfg["sections"]]:
                    if isinstance(x, str) and not Path(x).exists(): missing.append(x)
                cfg_path.write_text(json.dumps(cfg, indent=1))
                ref_notes = guitar_notes(out)
                arms["cpu_m05"] = finish("cpu_m05", out, secs, {"stages_cached": stages, "missing_paths": len(missing)})
                if missing:
                    raise RuntimeError(f"config paths missing after rewrite: {len(missing)}")
            finally:
                shutil.rmtree(copy, ignore_errors=True)
                after = listing(kept)
                res["kept_unchanged_p1"] = before == after
            print(label, "cpu_m05", arms["cpu_m05"]["seconds"], "s", flush=True)
            # the route check
            cfg = json.loads(cfg_path.read_text())
            out, secs = assemble("check", cfg)
            chk = guitar_notes(out)
            res["route_check"] = {"identical": chk == ref_notes, "n_notes": len(chk), "n_ref": len(ref_notes)}
            res["route_check"]["picks_equal"] = takes_info(json.loads((out / "report.json").read_text()))["windows"] == arms["cpu_m05"]["takes"]["windows"]
            shutil.rmtree(out)
            print(label, "route check", res["route_check"], flush=True)
            if not res["route_check"]["identical"]:
                raise SystemExit(f"{label}: ROUTE CHECK FAILED")
        cfg = json.loads(cfg_path.read_text())
        before = listing(kept)
        for arm, c in (("one", gpu_cfg(cfg, takes=False)), ("m05", gpu_cfg(cfg)),
                       ("cpu_one", gpu_cfg(cfg, takes=False, source=str(kept / "guitar" / "seed_20260609" / "notes.chart")))):
            if arm in arms: continue
            out, secs = assemble(arm, c)
            arms[arm] = finish(arm, out, secs)
            print(label, arm, secs, "s", flush=True)
        res["kept_unchanged_p1b"] = before == listing(kept)
    elif phase == "p2":
        cfg = gpu_cfg(json.loads(cfg_path.read_text()))
        before = listing(kept)
        wins = arms["m05"]["takes"]["windows"]
        assert picks_at(wins, 0.05) == arms["m05"]["picks"]
        for name, m in (("m0", 0.0), ("m02", 0.02), ("m10", 0.10)):
            if name in arms: continue
            pk = picks_at(wins, m)
            same = next((a for a in ("m05", "m0", "m02", "m10") if a in arms and "same_as" not in arms[a]
                         and arms[a].get("picks") == pk), None)
            if same:
                arms[name] = {"same_as": same, "picks": pk}
            else:
                out, secs = assemble(name, cfg, margin=m)
                arms[name] = finish(name, out, secs)
                # the recorded window scores are rounded to 4 places, the build compares unrounded ones: count the
                # windows where a near-tie made the built picks differ from the computed ones (the built picks stand)
                arms[name]["picks_vs_computed_diff"] = sum(x != y for x, y in zip(pk, arms[name]["picks"]))
            print(label, name, arms[name].get("same_as") or arms[name]["seconds"], flush=True)
        for k in (0, 1, 2, 3):
            name = f"f{k}"
            if name in arms: continue
            out, secs = assemble(name, cfg, force=k)
            arms[name] = finish(name, out, secs)
            print(label, name, secs, flush=True)
        ccfg = json.loads(cfg_path.read_text())   # the CPU takes alone through the same route (L1/D1's CPU picks)
        for k in (0, 1, 2, 3):
            name = f"cf{k}"
            if name in arms: continue
            out, secs = assemble(name, ccfg, force=k)
            arms[name] = finish(name, out, secs)
            print(label, name, secs, flush=True)
        if "q05" not in arms:
            out, secs = assemble("q05", cfg, margin=0.05, silent=True)
            arms["q05"] = finish("q05", out, secs)
            arms["q05"]["same_picks_as"] = [a for a, v in arms.items() if a != "q05" and v.get("picks") == arms["q05"]["picks"]]
            print(label, "q05", secs, flush=True)
        res["kept_unchanged_p2"] = before == listing(kept)
finally:
    res_path.write_text(json.dumps(res, indent=1))
