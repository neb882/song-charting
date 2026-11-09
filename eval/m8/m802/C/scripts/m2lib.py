"""m2lib.py: parts C and D's shared loader (M8-02, measurer M2). Reads the 23 songs' human charts (notes only, through
the v0.4.0 tag's eval/scorer/score.py scan, i.e. scan-chart), part B's kept arms (<shm>/m8/keep/<arm>/<label>),
part C's variant builds (<shm>/m8/m2/var/<arm>.<variant>/<label>) and the alignment that align.py wrote
(<shm>/m8/m2/align.json: per song and chart, the chart's delay and the lag of our song.ogg against the chart's
input.wav, as score.py computes them). Prints nothing. Songs are labelled: the references and the stress set by their
public names, the 20-song set s01-s13 (ids sorted, mapped here in process)."""
import hashlib, json, os, pickle, sys
from pathlib import Path
import numpy as np
CODE = Path("<shm>/m8/code")
sys.path.insert(0, str(CODE))
os.environ.setdefault("SONGCHARTER_SCAN_CHART", "<wt>/base-main/tools/scan-chart/scan.cjs")
from eval import stress as ST          # noqa: E402
from eval.scorer import score as S     # noqa: E402

DEV = Path("$DEV"); G = DEV / "golden"
KEEP = Path("<shm>/m8/keep"); VAR = Path("<shm>/m8/m2/var"); SHM = Path("<shm>/m8/m2")
REFS = ["all_the_small_things", "creep", "drunk_drivers", "kimochi_warui", "lucretia", "take_me_out"]
STRESS = ["break", "pm2", "sooth", "troop"]
LABELS = REFS + STRESS + [f"s{i:02d}" for i in range(1, 14)]
SLOW = ("creep", "lucretia", "sooth", "s02", "s04", "s13")   # grid under 100 BPM (the order's list)
F1_LOW = ("s02", "s04", "s06", "s12")                        # humans agree under 0.6 on guitar F1@50


def _songs():
    set20 = sorted(s["id"] for s in json.loads((DEV / "eval-set20/stress/songs.json").read_text()))
    out = {}
    for s in REFS: out[s] = ("refs", s, G / "work" / s)
    for s in STRESS: out[s] = ("stress", s, G / "stress-work" / s)
    for i, s in enumerate(set20, 1): out[f"s{i:02d}"] = ("set20", s, G / "set20-work" / s)
    return out


SONGS = _songs()


def charts(label):
    """[(k, folder)] primary first, the alts with guitar notes after (as part B scored them)."""
    st, sid, _ = SONGS[label]
    refs = {"refs": DEV / "eval/refs", "stress": DEV / "eval/stress", "set20": DEV / "eval-set20/stress"}[st]
    song = next(s for s in ST.built_songs(refs) if s["id"] == sid)
    return [("primary", Path(song["folder"]))] + [(a["label"], Path(a["folder"])) for a in song.get("alts") or []
                                                  if ST.scorable(Path(a["folder"]))]


def scan(folder):
    folder = str(folder)
    st = max(os.stat(os.path.join(folder, f)).st_mtime for f in os.listdir(folder))
    key = hashlib.sha1(f"{folder}|{st}".encode()).hexdigest()
    c = SHM / "scancache"; c.mkdir(parents=True, exist_ok=True)
    p = c / f"{key}.pkl"
    if p.exists():
        return pickle.loads(p.read_bytes())
    sc = S.scan(folder)
    sc = {k: sc.get(k) for k in ("resolution", "tempos", "tracks", "delay", "chart_offset")}
    p.write_bytes(pickle.dumps(sc))
    return sc


_AL = None


def alignment():
    global _AL
    if _AL is None:
        _AL = json.loads((SHM / "align.json").read_text())
    return _AL


def gtrack(sc, ins="guitar", dif="expert"):
    for t in sc.get("tracks") or []:
        if t["instrument"] == ins and t["difficulty"] == dif and t["notes"]:
            return t["notes"]
    return None


def _ons(sc, shift):
    notes = gtrack(sc)
    if notes is None:
        return None
    ons = S.onsets(notes, shift, "guitar")
    ms = {}
    for n in notes:
        ms[n["tick"]] = max(ms.get(n["tick"], 0), n.get("msLength") or 0)
    tick_of = {}
    for n in notes:
        tick_of.setdefault(round((n["ms"] + shift) / 1000.0, 9), n["tick"])
    for o in ons:
        o["tick"] = tick_of[round(o["t"], 9)]
        o["len_ms"] = ms[o["tick"]]
    return ons


def human(label, k):
    """A human chart's Expert guitar onsets in its own input.wav's frame (score.py's ref side) and the span."""
    a = alignment()[label][k]
    return _ons(scan(Path(a["folder"]) / "ref"), a["ref_delay_ms"]), tuple(a["span"])


def ours(folder, label, k, span=None):
    """Our chart's Expert guitar onsets in chart k's frame, cut to its span (score.py's cand side)."""
    a = alignment()[label][k]
    sc = scan(folder)
    cdel, _ = S.chart_delay_ms(sc)
    ons = _ons(sc, cdel - a["lag_ms"])
    span = span or tuple(a["span"])
    lo, hi = span[0] - S.SPAN_MARGIN, span[1] + S.SPAN_MARGIN
    return [o for o in ons if lo <= o["t"] <= hi]


def human_as_cand(label, k, kp="primary"):
    """Chart k's onsets moved into chart kp's frame (through our audio's lag against each input.wav), cut to kp's span."""
    A = alignment()[label]
    ons = _ons(scan(Path(A[k]["folder"]) / "ref"), A[k]["ref_delay_ms"] + A[k]["lag_ms"] - A[kp]["lag_ms"])
    lo, hi = A[kp]["span"][0] - S.SPAN_MARGIN, A[kp]["span"][1] + S.SPAN_MARGIN
    return [o for o in ons if lo <= o["t"] <= hi]


def arm_dir(arm, label, variant=None):
    return (VAR / f"{arm}.{variant}" / label) if variant else (KEEP / arm / label)


def pairs(ro, co, tol):
    return S.match(np.array([o["t"] for o in ro]), np.array([o["t"] for o in co]), tol)


def f1(ro, co, tol, span):
    p = pairs(ro, co, tol)
    return S.prf(len(p), len(ro), S.n_cand_eff(p, np.array([o["t"] for o in co]), span))["f1"]


def state(o):
    return S.played_state(o)


def mean(xs):
    xs = [x for x in xs if x is not None]
    return float(np.mean(xs)) if xs else None


def r3(x):
    return None if x is None else round(float(x), 3)


def boot(diffs, n=10000, seed=7):
    """Paired bootstrap over songs: the mean of per-song differences and its 95 % CI."""
    d = np.array([x for x in diffs if x is not None], dtype=float)
    if len(d) == 0:
        return None
    rng = np.random.default_rng(seed)
    m = d[rng.integers(0, len(d), (n, len(d)))].mean(axis=1)
    return {"mean": round(float(d.mean()), 3), "lo": round(float(np.percentile(m, 2.5)), 3),
            "hi": round(float(np.percentile(m, 97.5)), 3), "n": int(len(d))}


def fast_runs(t, per_s=8, min_n=8):
    """Run id per onset (-1 outside): runs of >= min_n onsets each <= 1/per_s s apart (M7-01's definition)."""
    t = np.asarray(t); n, rid, i, r = len(t), -np.ones(len(t), int), 0, 0
    while i < n:
        j = i
        while j + 1 < n and t[j + 1] - t[j] <= 1.0 / per_s + 1e-9:
            j += 1
        if j - i + 1 >= min_n:
            rid[i:j + 1] = r; r += 1
        i = j + 1
    return rid
