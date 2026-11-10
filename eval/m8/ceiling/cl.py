"""cl.py: the ceiling measurer's shared loader. Songs are labelled as M8-02's m2lib does (references and the stress
set by their public names, the 20-song set s01-s13: ids sorted, mapped in process). Reads: the human charts (notes only,
through eval/scorer's scan, i.e. scan-chart), our v0.5.0 golden charts (song.ogg, report.json, notes.chart's tempo
map), M8-02 part B's kept GPU m05 charts (B/charts/m05/<label>.notes.chart). Code from the main worktree, read-only.
Prints nothing; caches scans and alignments in <shm>/ceiling (deleted at the end)."""
import hashlib, json, os, pickle, shutil, sys
from pathlib import Path
import numpy as np
CODE = Path("<wt>/orch")
sys.path.insert(0, str(CODE))
os.environ.setdefault("SONGCHARTER_SCAN_CHART", "<wt>/base-main/tools/scan-chart/scan.cjs")
from eval import stress as ST          # noqa: E402
from eval.scorer import score as S     # noqa: E402

DEV = Path("$DEV"); G = DEV / "golden"
SCR = Path("<scratchpad>/m8")
B = SCR / "m8-02" / "B"
SHM = Path("<shm>/ceiling")
REFS = ["all_the_small_things", "creep", "drunk_drivers", "kimochi_warui", "lucretia", "take_me_out"]
STRESS = ["break", "pm2", "sooth", "troop"]
LABELS = REFS + STRESS + [f"s{i:02d}" for i in range(1, 14)]
FAST = ["creep", "pm2", "sooth", "troop", "s01", "s06", "s07", "s08", "s09", "s10"]   # part D's rate8 songs
F1_LOW = ("s02", "s04", "s06", "s12")


def _songs():
    set20 = sorted(s["id"] for s in json.loads((DEV / "eval-set20/stress/songs.json").read_text()))
    out = {}
    for s in REFS: out[s] = ("refs", s, G / "work" / s, G / "v050")
    for s in STRESS: out[s] = ("stress", s, G / "stress-work" / s, G / "v050-stress")
    for i, s in enumerate(set20, 1): out[f"s{i:02d}"] = ("set20", s, G / "set20-work" / s, G / "v050-set20")
    return out


SONGS = _songs()


def our_folder(label):
    st, sid, _, run = SONGS[label]
    summ = json.loads((run / "summary.json").read_text())
    return run / summ["songs"][sid]["folder"]


def charts(label):
    st, sid, _, _ = SONGS[label]
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
    sc = {k: sc.get(k) for k in ("resolution", "tempos", "timeSignatures", "tracks", "delay", "chart_offset")}
    p.write_bytes(pickle.dumps(sc))
    return sc


def m05_folder(label):
    """A folder holding only part B's GPU m05 notes.chart (scan-chart reads a folder)."""
    d = SHM / "m05" / label
    if not (d / "notes.chart").exists():
        d.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(B / "charts" / "m05" / f"{label}.notes.chart", d / "notes.chart")
    return d


def gtrack(sc, ins="guitar", dif="expert"):
    for t in sc.get("tracks") or []:
        if t["instrument"] == ins and t["difficulty"] == dif and t["notes"]:
            return t["notes"]
    return None


def ref_span(rsc):
    rdel, _ = S.chart_delay_ms(rsc)
    starts, ends = [], []
    for _, notes in S.tracks_by_key(rsc).items():
        starts.append(min(n["ms"] for n in notes)); ends.append(max(n["ms"] + (n.get("msLength") or 0) for n in notes))
    return rdel, ((min(starts) + rdel) / 1000.0, (max(ends) + rdel) / 1000.0)


_MEM = {}


def decode_cached(path):
    """Decoded audio, kept in this process only (no disk cache: the scratch budget)."""
    if str(path) not in _MEM:
        if len(_MEM) > 6: _MEM.clear()
        if Path(path).is_dir():   # a song folder: every audio file summed, as score.py's load_mix does for --cand
            _MEM[str(path)] = S.load_mix(str(path), S.audio_files(str(path))).astype(np.float32)
        else:
            _MEM[str(path)] = S.try_decode(str(path), []).astype(np.float32)
    return _MEM[str(path)]


def _decode_cached_disk(path):
    key = hashlib.sha1(str(path).encode()).hexdigest()
    p = SHM / "audio" / f"{key}.npy"
    if p.exists():
        return np.load(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    y = S.try_decode(str(path), [])
    np.save(p, y.astype(np.float32))
    return y.astype(np.float32)


def align_cached(ref_path, cand_path, n_win=9, max_shift_s=30.0):
    key = hashlib.sha1(f"{ref_path}|{cand_path}|{n_win}|{max_shift_s}".encode()).hexdigest()
    p = SHM / "align" / f"{key}.json"
    if p.exists():
        return json.loads(p.read_text())
    p.parent.mkdir(parents=True, exist_ok=True)
    r = S.align(decode_cached(ref_path).astype(np.float64), decode_cached(cand_path).astype(np.float64),
                n_win=n_win, max_shift_s=max_shift_s)
    p.write_text(json.dumps(r))
    return r


def r3(x):
    return None if x is None else round(float(x), 3)
