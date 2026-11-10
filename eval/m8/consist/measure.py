"""measure.py: repeat consistency of Expert guitar across repeated sections (a second advisor's finding 2; prereg.txt
beside). Reuses M8-02's loader (m8-02/C/scripts/m2lib.py) and alignment (align.py, re-run in process on the primary
charts only, our song.ogg = the v0.4.0 golden folder's, as the chord measurer did). Reads our arms' charts (sections
from their [Events], notes through scan-chart) and the humans through the scorer's scan. Writes <out>/results.json
(labels only, 3 decimals). Prints labels and counts only.
Usage: python -I measure.py <out dir> [arm=dir ...]   (extra arms: a folder of <label>.notes.chart, e.g. cpu=...)"""
import json, os, re, runpy, shutil, sys
from pathlib import Path
SH = Path("<shm>/consist")
sys.path.insert(0, str(SH / "code"))
M8 = Path("<scratchpad>/m8")
M802 = M8 / "m8-02"
sys.path.insert(0, str(M802 / "C" / "scripts"))
import numpy as np        # noqa: E402
import m2lib as L         # noqa: E402
S = L.S
L.SHM = SH
L.KEEP = SH / "keep"
OUT = Path(sys.argv[1])
ARMS = {"one": M802 / "B" / "charts" / "one", "m05": M802 / "B" / "charts" / "m05"}
for a in sys.argv[2:]:
    k, v = a.split("=", 1)
    ARMS[k] = Path(v)
GOLD = {"refs": L.G / "v040f", "stress": L.G / "v040f-stress", "set20": L.G / "v040-set20"}
TOL = 0.050
_charts = L.charts
L.charts = lambda label: _charts(label)[:1]          # primary only


def gold_dir(label):
    st, sid, _ = L.SONGS[label]
    return GOLD[st] / sid


# ---------------------------------------------------------------- alignment (primary charts)
for label in L.LABELS:
    a = L.KEEP / "_audio" / label
    a.mkdir(parents=True, exist_ok=True)
    if not (a / "song.ogg").exists():
        os.symlink(gold_dir(label) / "song.ogg", a / "song.ogg")
runpy.run_path(str(M802 / "C" / "scripts" / "align.py"), run_name="__main__")
AL = L.alignment()


# ---------------------------------------------------------------- tempo maps
class TMap:
    def __init__(self, sc):
        self.res = sc["resolution"]
        tps = sorted(sc["tempos"], key=lambda x: x["tick"])
        self.tick = np.array([x["tick"] for x in tps], float)
        self.ms = np.array([x["msTime"] for x in tps], float)
        self.bpm = np.array([x["beatsPerMinute"] for x in tps], float)

    def t2ms(self, tick):
        k = max(int(np.searchsorted(self.tick, tick, "right")) - 1, 0)
        return self.ms[k] + (tick - self.tick[k]) * 60000.0 / (self.bpm[k] * self.res)

    def ms2t(self, ms):
        k = max(int(np.searchsorted(self.ms, ms, "right")) - 1, 0)
        return self.tick[k] + (ms - self.ms[k]) * self.bpm[k] * self.res / 60000.0


def sections(path):
    txt = Path(path).read_text(encoding="utf-8-sig")
    m = re.search(r"\[Events\]\s*\{(.*?)\}", txt, re.S)
    out = []
    for line in m.group(1).splitlines():
        mm = re.match(r'\s*(\d+)\s*=\s*E\s*"section (.*)"', line)
        if mm:
            out.append((int(mm.group(1)), mm.group(2).split()[0].lower()))
    return sorted(out)


def instances(secs, last_tick, res):
    out = []
    for i, (tk, lab) in enumerate(secs):
        end = secs[i + 1][0] if i + 1 < len(secs) else last_tick + 1
        out.append({"label": lab, "start": tk, "end": end, "beats": int(round((end - tk) / res))})
    return out


def pair_list(inst, slack):
    return [(i, j) for i in range(len(inst)) for j in range(i + 1, len(inst))
            if inst[i]["label"] == inst[j]["label"] and abs(inst[i]["beats"] - inst[j]["beats"]) <= slack
            and min(inst[i]["beats"], inst[j]["beats"]) > 0]


RULES = {"relaxed": (2, (0, -1, 1, -2, 2)), "strict": (0, (0,))}
if os.environ.get("WIDE"):     # diagnostic only: shifts up to +-WIDE beats
    _w = int(os.environ["WIDE"])
    RULES["relaxed"] = (2, tuple(sorted(range(-_w, _w + 1), key=lambda x: (abs(x), x))))


def f1_pair(A, B, tol):
    """A, B: [(offset_beats, frozenset lanes)] sorted by offset."""
    if not A and not B:
        return None
    hits = 0
    for ls in {x[1] for x in A} & {x[1] for x in B}:
        a = np.array([x[0] for x in A if x[1] == ls])
        b = np.array([x[0] for x in B if x[1] == ls])
        hits += len(S.match(a, b, tol))
    return 2 * hits / (len(A) + len(B))


def lane_pos(A, B):
    if not A and not B:
        return None
    n = min(len(A), len(B))
    return sum(A[i][1] == B[i][1] for i in range(n)) / max(len(A), len(B))


def lane_time(A, B, tol):
    p = S.match(np.array([x[0] for x in A]), np.array([x[0] for x in B]), tol)
    return (sum(A[i][1] == B[j][1] for i, j in p) / len(p)) if p else None


def score_pairs(pairs, notes_of, tol_of, inst, shifts):
    rows = []
    for i, j in pairs:
        A0, B0 = notes_of(i), notes_of(j)
        tol = tol_of(i, j)
        Lb = min(inst[i]["beats"], inst[j]["beats"])
        best = None
        for sh in shifts:
            A = [x for x in A0 if 0 <= x[0] < Lb]
            B = [(x[0] + sh, x[1]) for x in B0 if 0 <= x[0] + sh < Lb]
            f = f1_pair(A, B, tol)
            if f is not None and (best is None or f > best[0]):
                best = (f, sh, A, B)
        if best is None:
            continue
        f, sh, A, B = best
        rows.append({"i": i, "j": j, "f1": f, "shift": sh, "lane_pos": lane_pos(A, B), "lane_time": lane_time(A, B, tol),
                     "nA": len(A), "nB": len(B)})
    return rows


def summ(rows):
    if not rows:
        return {"n_pairs": 0}
    return {"n_pairs": len(rows), "shift0": sum(r["shift"] == 0 for r in rows) / len(rows), "f1": L.mean([r["f1"] for r in rows]), "lane_pos": L.mean([r["lane_pos"] for r in rows]),
            "lane_time": L.mean([r["lane_time"] for r in rows]), "n_onsets": sum(r["nA"] + r["nB"] for r in rows)}


res = {"songs": {}}
if os.environ.get("ONLY"):
    L.LABELS = os.environ["ONLY"].split(",")
def allin1_instances(label, tm, cdel):
    st, sid, work = L.SONGS[label]
    seg = json.loads((work / "sections" / "segments.json").read_text())["segments"]
    pad = json.loads((gold_dir(label) / "report.json").read_text())["lead_in"]["pad_seconds"]
    assert cdel == 0, label
    out = []
    for s, e, lab in seg:
        if lab in ("start", "end"):
            continue
        ts, te = (int(round(tm.ms2t((x + pad) * 1000.0) / tm.res)) * tm.res for x in (s, e))
        out.append({"label": lab, "start": ts, "end": te, "beats": (te - ts) // tm.res})
    return out


for label in L.LABELS:
    al = AL[label]["primary"]
    song = {"well": al["good_windows"] > 4.5 and al["lag_mad_ms"] < 2.0, "arms": {}, "human": {}}
    secs_by_arm = {}
    for arm, d in ARMS.items():
        path = d / f"{label}.notes.chart"
        if not path.exists():
            continue
        folder = SH / "charts" / arm / label
        folder.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, folder / "notes.chart")
        sc = L.scan(folder)
        tm = TMap(sc)
        cdel = S.chart_delay_ms(sc)[0]
        ons = L._ons(sc, cdel)
        secs = sections(path)
        secs_by_arm[arm] = secs
        modes = {"allin1": allin1_instances(label, tm, cdel),
                 "events": instances(secs, max(o["tick"] for o in ons), tm.res)}
        song["arms"][arm] = {}
        for (mode, inst), (rule, (slack, shifts)) in [(m, r) for m in modes.items() for r in RULES.items()]:
            pairs = pair_list(inst, slack)
            key = f"{mode}.{rule}"

            def notes_of(i, inst=inst, ons=ons, tm=tm):
                s, e = inst[i]["start"], inst[i]["end"]
                return [((o["tick"] - s) / tm.res, frozenset(o["lanes"])) for o in ons if s <= o["tick"] < e]

            def secs_len(i, inst=inst, tm=tm):
                return (tm.t2ms(inst[i]["end"]) - tm.t2ms(inst[i]["start"])) / 1000.0

            def tol_of(i, j, inst=inst):
                bps = (inst[i]["beats"] / secs_len(i) + inst[j]["beats"] / secs_len(j)) / 2
                return TOL * bps
            rows = score_pairs(pairs, notes_of, tol_of, inst, shifts)
            song["arms"][arm][key] = {"n_sections": len(inst), "pairs": len(pairs), **summ(rows),
                                       "rows": [[r["i"], r["j"], r["f1"], r["lane_pos"], r["shift"]] for r in rows],
                                       "inst_s": [[tm.t2ms(x["start"]) / 1000.0, tm.t2ms(x["end"]) / 1000.0,
                                                   x["beats"]] for x in inst],
                                       "by_label": {lab: summ([r for r in rows if inst[r["i"]]["label"] == lab])
                                                    for lab in sorted({inst[i]["label"] for i, _ in pairs})}}
            if arm != "one":
                continue
            # human on the same pairs, our bounds mapped into its frame
            ho, _ = L.human(label, "primary")
            hsc = L.scan(Path(al["folder"]) / "ref")
            htm = TMap(hsc)
            rdel = al["ref_delay_ms"]
            ht = np.array([o["t"] for o in ho])

            def hb(tick, tm=tm, cdel=cdel):              # our tick -> human frame seconds
                return (tm.t2ms(tick) + cdel - al["lag_ms"]) / 1000.0

            def hnotes(i, inst=inst, tm=tm, cdel=cdel):
                s, e = hb(inst[i]["start"]) - 0.025, hb(inst[i]["end"]) - 0.025
                # the human onset on OUR beat grid: human frame s -> our chart ms -> our fractional tick
                return [((tm.ms2t(t * 1000.0 + al["lag_ms"] - cdel) - inst[i]["start"]) / tm.res, frozenset(o["lanes"]))
                        for o, t in zip(ho, ht) if s <= t < e]
            htol = tol_of
            hrows = score_pairs(pairs, hnotes, htol, inst, shifts)
            song["human"][key] = {"pairs": len(pairs), **summ(hrows),
                                   "by_label": {lab: summ([r for r in hrows if inst[r["i"]]["label"] == lab])
                                                for lab in sorted({inst[i]["label"] for i, _ in pairs})}}
    song["same_sections"] = len({tuple(v) for v in secs_by_arm.values()}) == 1
    res["songs"][label] = song
    print(label, "pairs", {k: v["pairs"] for k, v in song["arms"]["one"].items()},
          "same_sections", song["same_sections"], flush=True)

def rd(x):
    if isinstance(x, (bool, np.bool_)):
        return bool(x)
    if isinstance(x, (int, np.integer)):
        return int(x)
    if isinstance(x, (float, np.floating)):
        return round(float(x), 3)
    if isinstance(x, dict):
        return {k: rd(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [rd(v) for v in x]
    return x


OUT.mkdir(parents=True, exist_ok=True)
(OUT / "results.json").write_text(json.dumps(rd(res), indent=1))
