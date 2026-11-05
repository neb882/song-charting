"""The stress set: the hard songs and an ordinary rock song, each with every human chart Chorus Encore has of it, as a
repeatable check beside the golden set (docs/DESIGN.md 3.3, docs/work-orders/M5-09-stress-eval.md). Run from the root
of a checkout:

    python eval/stress.py songs [--json] [--local FILE]       the set: eval/stress.json and the owner's local list
    python eval/stress.py score RUN_DIR [--refs DIR] [--work DIR] [--windows 30]
    python eval/stress.py compare OLD NEW                      exit 1 when a primary F1@50 falls by more than 0.01
    python eval/stress.py align ID FILE [--refs DIR]           a file's audio against the song's input.wav
    python eval/stress.py lyrics ID [--run RUN_DIR] [--refs DIR] [--tmp DIR]
    python eval/stress.py baseline RUN_DIR OUT                 summary.json and stress_scores.json, scrubbed

**The set.** `eval/stress.json` (committed) names each song by a generic id and slot, how many human charts it has
and what its primary chart holds; the md5s of the packages, their titles and charters are the owner's list outside
the repository, `$EVAL_DATA/stress.local.json` (refs.json's shape, plus `alts`: the other charts' md5s and
charters), never committed. The primary chart is the one with the most parts (ties: more Expert guitar notes).
`eval/build_refs.sh --set stress` builds `$EVAL_DATA/stress/<id>/` from the primary as a reference is built, and
`<id>/alt/<md5>/` from each other chart; `python -m eval.golden run --refs $EVAL_DATA/stress --work
$SONGCHARTER_GOLDEN/stress-work --out RUN_DIR` builds and scores songcharter's charts as for the golden set.

**score** runs eval/scorer/score.py (with --windows) for each song of a run: our chart against the primary and every
other human chart, and each other chart against the primary (the humans' agreement: the ceiling of every measure).
It writes RUN_DIR/stress_scores.json (numbers only; score.py's own output in RUN_DIR/stress_scores/) and prints the
feel report (docs/reports/feel.md, the number of each measure in brackets): per song, part and human chart, F1@50
and F1@100, the notes ratio and the lowest 30-s window; the matched notes' median timing error [1]; chord share and
the 1-s density peak [2]; contour (lane direction) agreement, the jump-size distance and the big fast jumps [3];
HOPO, tap and sustain shares and the per-note state agreement [5]; notes in silence (report.json) and gaps while
the stem plays (songcharter.preview's flags with the kept folder's stems) [6]; star power phrases per minute and
the solo share [7]; the beat F1 plain and octave-tolerant and the downbeat F1 [8]. Repeat consistency [4] is not
measured here (M5-99). A human chart with no guitar, bass or drums part is listed and not scored.

**compare** puts two stress_scores.json (files or the run folders holding them) side by side: every number of
ours against the primary, old and new. Exit 1 when any part's F1@50 against the primary falls by more than 0.01 or
is gone (the stress check's regression rule), 0 otherwise, 2 when they cannot be compared.

**align** runs score.py's windowed cross-correlation of a file against the song's input.wav: aligned when most
windows peak at 0.3 or more and the lags' MAD is under 2 ms (exit 0), else exit 1.

**lyrics** gives the words of the primary package's lyric events (read in memory from $EVAL_DATA/sng/<md5>.sng) to
songcharter's pipeline in process, charts the song's input.wav into a temporary folder (the song folder and the work
folder both under it; with --run, the work folder starts as a copy of that run's kept folder, so only assemble and
the aligner run), compares the chart's lyric timings with the human chart's word by word (eval/lyrics_timing.py),
prints the numbers and deletes the temporary folder whole, a gate's <out>.failed included (with --run it is
under the kept folders' .runs/, on their file system, since the work folder hard-links their decode and stems). Under the lyrics rule
(M4-10, extended by M5-09) no word is printed, logged, saved or returned: errors are printed as their type. A song
with no lyric events says so and exits 0.

**baseline** copies a run's summary.json and stress_scores.json for eval/baseline/stress/: every absolute path is
cut to its last part, and no title, artist, charter or md5 of the local list may remain (checked).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path
from typing import Callable

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))

SET_JSON = HERE / "stress.json"
SCORE = HERE / "scorer" / "score.py"
FORMAT = 1                      # stress_scores.json's format
PARTS = ("guitar", "bass", "drums")
WINDOW_S = 30.0
REGRESSION = 0.01               # the stress check: a primary F1@50 may fall by at most this
ALIGN_PEAK, ALIGN_MAD_MS = 0.3, 2.0
MD5 = re.compile(r"[0-9a-f]{32}")
ID = re.compile(r"[a-z][a-z0-9_]*")


class Refused(Exception):
    """Bad input or environment: exit 2."""


def _say(line: str) -> None:
    print(line, file=sys.stderr, flush=True)


def read_json(path: Path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise Refused(f"cannot read {path} ({type(e).__name__})") from e


def data_dir() -> Path:
    return Path(os.environ.get("EVAL_DATA") or HERE / "data")


# ------------------------------------------------------------------------------------------------ the set

def load_set(set_json: Path = SET_JSON, local: Path | None = None) -> list[dict]:
    """The committed set's songs merged with the owner's local list: each entry is the local one (md5, title,
    charter, alts) with the committed id and slot. Refused when an id is missing from the list, its chart count
    differs, or an md5 is malformed."""
    songs = read_json(set_json)
    local = read_json(local or data_dir() / "stress.local.json")
    if not isinstance(songs, list) or not isinstance(local, list):
        raise Refused("the set and the local list are JSON lists")
    by_id = {e.get("id"): e for e in local if isinstance(e, dict)}
    out, seen = [], set()
    for s in songs:
        sid = s.get("id") if isinstance(s, dict) else None
        if not isinstance(sid, str) or not ID.fullmatch(sid) or sid in seen or not s.get("slot"):
            raise Refused(f"{set_json}: each song needs a unique lower-case id and a slot, not {s!r}")
        seen.add(sid)
        e = by_id.get(sid)
        if e is None:
            raise Refused(f"{sid} is not in the local list (the owner's md5s): add it there")
        alts = e.get("alts") or []
        md5s = [e.get("md5")] + [a.get("md5") for a in alts]
        if not all(isinstance(m, str) and MD5.fullmatch(m) for m in md5s) or len(set(md5s)) != len(md5s):
            raise Refused(f"{sid}: the local list's md5s must be 32 hex digits each, all different")
        if s.get("charts") is not None and s["charts"] != len(md5s):
            raise Refused(f"{sid}: the set says {s['charts']} charts, the local list has {len(md5s)}")
        out.append({**{k: v for k, v in e.items() if k not in ("id", "slot")}, "id": sid, "slot": s["slot"],
                    "alts": [dict(a) for a in alts]})
    return out


def cmd_songs(a) -> int:
    songs = load_set(Path(a.set) if a.set else SET_JSON, Path(a.local) if a.local else None)
    if a.json:
        print(json.dumps(songs, indent=1, ensure_ascii=False))
    else:
        for s in songs:
            print(f"{s['id']}\tprimary\t{s['md5']}\t{s['slot']}")
            for alt in s["alts"]:
                print(f"{s['id']}\talt\t{alt['md5']}")
    return 0


def built_songs(refs: Path) -> list[dict]:
    """<refs>/songs.json (build_refs.sh --set stress), each alt with its folder and label (alt1, alt2, ...)."""
    songs = read_json(refs / "songs.json")
    for s in songs:
        s["folder"] = str(refs / s["id"])
        for k, alt in enumerate(s.get("alts") or [], 1):
            alt["label"] = f"alt{k}"
            alt["folder"] = str(refs / s["id"] / "alt" / alt["md5"])
    return songs


def scorable(ref_folder: Path) -> bool:
    """Whether a built chart has notes on guitar, bass or drums (score.py's parts)."""
    try:
        rn = json.loads((Path(ref_folder) / "ref_notes.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return any(t["instrument"] in PARTS and t["notes"] for t in rn.get("tracks") or [])


# ------------------------------------------------------------------------------------------------ score

def run_score(ref: Path, cand: Path, inp: Path, out_json: Path, cand_audio: Path | None = None,
              windows: float = WINDOW_S, env: dict | None = None) -> dict:
    """score.py's JSON for one comparison."""
    args = [sys.executable, str(SCORE), "--ref", str(ref), "--cand", str(cand), "--input", str(inp), "--out",
            str(out_json), "--windows", str(windows)]
    args += ["--cand-audio", str(cand_audio)] if cand_audio else []
    p = subprocess.run(args, capture_output=True, text=True, env=env, stdin=subprocess.DEVNULL)
    if p.returncode != 0:
        raise RuntimeError(f"score.py failed on {ref} vs {cand}: {p.stderr.strip()[-1500:]}")
    return json.loads(out_json.read_text(encoding="utf-8"))


def _pair(x: dict | None, key: str = None):
    """[ours, theirs] of a {"cand", "ref"} entry."""
    x = (x or {}).get(key) if key else x
    return None if x is None else [x.get("cand"), x.get("ref")]


def feel(t: dict) -> dict:
    """The feel measures of one score.py track (ours = the candidate, theirs = the reference)."""
    nn = t.get("n_notes") or {}
    win = (t.get("windows_100ms") or {}).get("lowest")
    jumps = t.get("jumps") or {}
    out = {"f1_50": t["onset_50ms"]["f1"], "f1_100": t["onset_100ms"]["f1"],
           "onsets": [t["onset_50ms"]["n_cand"], t["onset_50ms"]["n_ref"]],
           "notes_ratio": round(nn["cand"] / nn["ref"], 4) if nn.get("ref") else None,
           "lowest_window": win,
           "timing_err_ms": (t.get("timing_err_ms_matched100") or {}).get("median"),
           "chord_share": _pair(t, "chord_share"), "density_peak_1s": _pair(t, "density_peak_1s"),
           "contour": (t.get("lane_direction_agreement") or {}).get("value"),
           "contour_trivial": (t.get("lane_direction_agreement") or {}).get("trivial_always_same_would_get"),
           "star_power_per_min": _pair(t, "star_power_per_min"), "solo_share": _pair(t, "solo_share")}
    if "hopo_share" in t:
        out.update(hopo_share=_pair(t, "hopo_share"), tap_share=_pair(t, "tap_share"),
                   sustain_share=_pair(t, "sustain_share"),
                   state_agreement=(t.get("state_agreement") or {}).get("value"),
                   jump_emd=jumps.get("emd_lanes"),
                   big_fast_per_min=[(jumps.get("cand") or {}).get("big_fast_per_min"),
                                     (jumps.get("ref") or {}).get("big_fast_per_min")])
    return out


def tempo(d: dict) -> dict:
    tm = d.get("tempo_map") or {}
    f = lambda x: (x or {}).get("f1")
    return {"beat_f1": f(tm.get("beat_f1_70ms")), "beat_f1_octave": f(tm.get("beat_f1_70ms_octave_tolerant")),
            "downbeat_f1": f(tm.get("downbeat_f1_70ms")), "lag_ms": (d.get("alignment") or {}).get("lag_ms")}


def comparison(d: dict) -> dict:
    """One score.py result as the table's numbers: the tempo map's and each part's Expert feel measures."""
    parts = {p: feel(d["tracks"][f"{p}/expert"]) for p in PARTS if f"{p}/expert" in d.get("tracks", {})}
    return {"tempo": tempo(d), "parts": parts, "missing": [k for k in d.get("ref_tracks_missing_in_cand") or []
                                                           if k.endswith("/expert")]}


def kept_stems(kept: Path) -> dict[str, Path]:
    """The stems of a kept work folder (stems/<key>/<stem>.wav; the key whose info.json is there)."""
    for d in sorted((kept / "stems").glob("*/")) if (kept / "stems").is_dir() else []:
        if (d / "info.json").is_file():
            return {p.stem: p for p in sorted(d.glob("*.wav"))}
    return {}


def shape(folder: Path, kept: Path | None) -> dict:
    """Our chart's notes in silence (report.json's silent_onsets per part) and the preview's flags with the kept
    folder's stems (gaps while the stem plays, rings past a sustain, notes in silence), counted per part."""
    report = read_json(folder / "report.json") if (folder / "report.json").is_file() else {}
    out = {p: {"silent_onsets": None, "flags": {}} for p in PARTS}
    for key, part in (report.get("parts") or {}).items():
        inst = part.get("instrument") or key
        if inst in out and isinstance(part.get("silent_onsets"), dict):
            out[inst]["silent_onsets"] = part["silent_onsets"].get("count")
    stems = kept_stems(kept) if kept else {}
    if stems:
        from songcharter import preview as PV
        pv = PV.load(folder, stems=stems)
        for f in PV.flags(pv):
            c = out.setdefault(f.instrument, {"silent_onsets": None, "flags": {}})["flags"]
            k = c.setdefault(f.kind, {"stretches": 0, "measures": 0})
            k["stretches"] += 1
            k["measures"] += f.measures
        for p in out:
            out[p]["judged"] = p in pv.envelopes
    return out


def score_run(run_dir: Path, refs: Path | None = None, work: Path | None = None, windows: float = WINDOW_S,
              env: dict | None = None, scorer: Callable[..., dict] = run_score,
              shaper: Callable[[Path, Path | None], dict] = shape, say: Callable[[str], None] = _say) -> dict:
    """stress_scores.json's content for a run (the module docstring); score.py's files in run_dir/stress_scores/."""
    summary = read_json(run_dir / "summary.json")
    run = summary.get("run") or {}
    refs = Path(refs or run.get("refs") or data_dir() / "stress")
    work = Path(work) if work else Path(run["work"]) if run.get("work") else None
    sdir = run_dir / "stress_scores"
    sdir.mkdir(exist_ok=True)
    by_id = {s["id"]: s for s in built_songs(refs)}
    songs = {}
    for sid, entry in summary["songs"].items():
        song = by_id.get(sid)
        if song is None:
            raise Refused(f"{sid} is in the run but not in {refs / 'songs.json'}")
        primary, inp = Path(song["folder"]), Path(song["folder"]) / "input.wav"
        alts = song.get("alts") or []
        res: dict = {"slot": song.get("slot"), "charts": 1 + len(alts), "gate_ok": entry.get("gate_ok"),
                     "refs": ["primary"] + [a["label"] for a in alts], "unscored": {}, "ours": {}, "humans": {}}
        songs[sid] = res
        folder = run_dir / entry["folder"] if entry.get("folder") else None
        if folder is None or not folder.is_dir():
            res["error"] = "no song folder: the build failed"
            continue
        say(f"  {sid}: ours vs primary")
        res["ours"]["primary"] = comparison(scorer(primary, folder, inp, sdir / f"{sid}.ours.primary.json",
                                                   windows=windows, env=env))
        for alt in alts:
            lab, af = alt["label"], Path(alt["folder"])
            if not scorable(af):
                res["unscored"][lab] = "no guitar, bass or drums notes"
                continue
            say(f"  {sid}: ours vs {lab}; {lab} vs primary")
            res["ours"][lab] = comparison(scorer(af, folder, inp, sdir / f"{sid}.ours.{lab}.json", windows=windows,
                                                 env=env))
            res["humans"][lab] = comparison(scorer(primary, af / "ref", inp, sdir / f"{sid}.human.{lab}.json",
                                                   cand_audio=af / "input.wav", windows=windows, env=env))
        res["shape"] = shaper(folder, work / sid if work else None)
    return {"stress": FORMAT, "about": "eval/stress.py score: our charts against every human chart of each stress "
            "song, and the other human charts against the primary (the humans' agreement), Expert; numbers only.",
            "code": summary.get("code"), "window_s": windows, "songs": songs}


def _f(x, nd=3) -> str:
    if x is None:
        return "—"
    if isinstance(x, list):
        return "/".join(_f(v, nd) for v in x)
    return f"{x:.{nd}f}" if isinstance(x, float) else str(x)


def _mmss(t) -> str:
    return "—" if t is None else f"{int(t // 60)}:{t % 60:04.1f}"


FEEL_HEAD = ("| song | part | chart | F1@50 | F1@100 | notes | lowest 30 s [F1@100 at] | err ms [1] | chords o/t [2] | "
             "1-s peak o/t [2] | contour [3] | jump EMD [3] | big fast/min o/t [3] | HOPO o/t [5] | tap o/t [5] | "
             "sustain o/t [5] | state [5] | SP/min o/t [7] | solo o/t [7] |")


def feel_row(sid: str, part: str, who: str, f: dict) -> str:
    low = f.get("lowest_window") or {}
    cells = [sid, part, who, _f(f["f1_50"]), _f(f["f1_100"]), _f(f.get("notes_ratio"), 2),
             f"{_f(low.get('f1'))} at {_mmss(low.get('start_s'))}" if low else "—", _f(f.get("timing_err_ms"), 1),
             _f(f.get("chord_share"), 2), _f(f.get("density_peak_1s")), _f(f.get("contour"), 2),
             _f(f.get("jump_emd"), 2), _f(f.get("big_fast_per_min"), 1), _f(f.get("hopo_share"), 2),
             _f(f.get("tap_share"), 2), _f(f.get("sustain_share"), 2), _f(f.get("state_agreement"), 2),
             _f(f.get("star_power_per_min"), 2), _f(f.get("solo_share"), 2)]
    return "| " + " | ".join(cells) + " |"


def render(scores: dict) -> str:
    """The feel report: a markdown table of every part and chart, then the beat lines and the shape."""
    lines = [f"# Stress set: the feel report ({(scores.get('code') or {}).get('commit') or '?'})", "",
             "Ours against each human chart (`ours vs`), and each other human chart against the primary "
             "(`humans`: the ceiling). o/t: ours/theirs (for `humans`, that chart/the primary). Expert. Brackets: "
             "docs/reports/feel.md's measure.", "", FEEL_HEAD, "|" + "---|" * (FEEL_HEAD.count("|") - 1)]
    for sid, s in scores["songs"].items():
        for part in PARTS:
            for lab, c in s.get("ours", {}).items():
                if part in c["parts"]:
                    lines.append(feel_row(sid, part, f"ours vs {lab}", c["parts"][part]))
            for lab, c in s.get("humans", {}).items():
                if part in c["parts"]:
                    lines.append(feel_row(sid, part, f"humans: {lab} vs primary", c["parts"][part]))
    lines += ["", "## Beat lines [8] and shape [6]", "",
              "| song | chart | beat F1 | octave-tolerant | downbeat F1 | lag ms |", "|---|---|---|---|---|---|"]
    for sid, s in scores["songs"].items():
        for kind, group in (("ours vs", s.get("ours", {})), ("humans:", s.get("humans", {}))):
            for lab, c in group.items():
                t = c["tempo"]
                lines.append(f"| {sid} | {kind} {lab} | {_f(t['beat_f1'])} | {_f(t['beat_f1_octave'])} | "
                             f"{_f(t['downbeat_f1'])} | {_f(t['lag_ms'], 1)} |")
    lines += ["", "| song | part | notes in silence | gaps (measures) | rings past a sustain | notes in silence "
              "(preview) |", "|---|---|---|---|---|---|"]
    for sid, s in scores["songs"].items():
        for part, x in (s.get("shape") or {}).items():
            fl = x.get("flags") or {}
            g = lambda k: f"{fl[k]['stretches']} ({fl[k]['measures']})" if k in fl else (
                "0" if x.get("judged") else "—")
            lines.append(f"| {sid} | {part} | {_f(x.get('silent_onsets'))} | {g('gap')} | "
                         f"{g('rings past its sustain')} | {g('notes in silence')} |")
        for lab, why in (s.get("unscored") or {}).items():
            lines.append(f"| {sid} | {lab} | not scored: {why} | | | |")
        if s.get("error"):
            lines.append(f"| {sid} | — | {s['error']} | | | |")
    return "\n".join(lines) + "\n"


def cmd_score(a) -> int:
    from eval import golden as G
    run_dir = Path(a.run_dir).resolve()
    env = dict(os.environ)
    env["SONGCHARTER_SCAN_CHART"] = str(G.scan_chart_script())
    G.node()
    scores = score_run(run_dir, Path(a.refs) if a.refs else None, Path(a.work) if a.work else None,
                       windows=a.windows, env=env)
    G.write_json(run_dir / "stress_scores.json", scores)
    text = render(scores)
    (run_dir / "stress_report.md").write_text(text, encoding="utf-8")
    print(text)
    return 0


# ------------------------------------------------------------------------------------------------ compare

def load_scores(path: Path) -> dict:
    file = path / "stress_scores.json" if path.is_dir() else path
    d = read_json(file)
    if not isinstance(d, dict) or d.get("stress") != FORMAT or "songs" not in d:
        raise Refused(f"{file} is not a stress_scores.json of format {FORMAT}")
    return d


COMPARED = (("F1@50", "f1_50", 3), ("F1@100", "f1_100", 3), ("lowest 30 s", "lowest_window", 3),
            ("err ms", "timing_err_ms", 1), ("chords", "chord_share", 2), ("1-s peak", "density_peak_1s", 0),
            ("contour", "contour", 2), ("jump EMD", "jump_emd", 2), ("big fast/min", "big_fast_per_min", 1),
            ("HOPO", "hopo_share", 2), ("state", "state_agreement", 2), ("SP/min", "star_power_per_min", 2),
            ("solo", "solo_share", 2))


def _ours(x):
    """Ours of a measure: the first of an [ours, theirs] pair, a window's F1, or the number."""
    if isinstance(x, list):
        return x[0]
    if isinstance(x, dict):
        return x.get("f1")
    return x


def compare_scores(old: dict, new: dict) -> tuple[str, int, list[str]]:
    """The two runs' tables side by side (ours against every human chart), and the regressions: a part whose F1@50
    against the primary fell by more than REGRESSION, or that is gone."""
    lines = [f"# Stress check: {(old.get('code') or {}).get('commit') or '?'} → "
             f"{(new.get('code') or {}).get('commit') or '?'}", "",
             "| song | part | vs | " + " | ".join(n for n, _, _ in COMPARED) + " |",
             "|---|---|---|" + "---|" * len(COMPARED)]
    bad = []
    for sid in list(old["songs"]) + [s for s in new["songs"] if s not in old["songs"]]:
        o, n = old["songs"].get(sid), new["songs"].get(sid)
        if o is None or n is None:
            bad.append(f"{sid}: only in the {'new' if o is None else 'old'} scores")
            continue
        labels = list(o.get("ours", {})) + [k for k in n.get("ours", {}) if k not in o.get("ours", {})]
        for part in PARTS:
            for lab in labels:
                a = ((o.get("ours", {}).get(lab) or {}).get("parts") or {}).get(part)
                b = ((n.get("ours", {}).get(lab) or {}).get("parts") or {}).get(part)
                if a is None and b is None:
                    continue
                cells = []
                for _, key, nd in COMPARED:
                    va, vb = _ours((a or {}).get(key)), _ours((b or {}).get(key))
                    d = "" if va is None or vb is None else f" ({vb - va:+.{max(nd, 1)}f})"
                    cells.append(f"{_f(va, nd)} → {_f(vb, nd)}{d}")
                lines.append(f"| {sid} | {part} | {lab} | " + " | ".join(cells) + " |")
                if lab == "primary":
                    if b is None:
                        bad.append(f"{sid} {part}: gone from the new chart")
                    elif a is not None and b["f1_50"] < a["f1_50"] - REGRESSION:
                        bad.append(f"{sid} {part}: F1@50 {a['f1_50']:.3f} → {b['f1_50']:.3f}")
        to, tn = (o.get("ours", {}).get("primary") or {}).get("tempo"), (n.get("ours", {}).get("primary") or {}).get("tempo")
        if to and tn:
            lines.append(f"| {sid} | beat lines | primary | beat F1 {_f(to['beat_f1'])} → {_f(tn['beat_f1'])}; "
                         f"downbeat F1 {_f(to['downbeat_f1'])} → {_f(tn['downbeat_f1'])} |" + " |" * (len(COMPARED) - 1))
    lines += ["", f"**Regressions (a primary F1@50 down by more than {REGRESSION}): {len(bad)}**"
              + (f": {'; '.join(bad)}." if bad else ".")]
    return "\n".join(lines) + "\n", 1 if bad else 0, bad


def cmd_compare(a) -> int:
    text, code, _ = compare_scores(load_scores(Path(a.old).resolve()), load_scores(Path(a.new).resolve()))
    print(text)
    return code


# ------------------------------------------------------------------------------------------------ align

def align_file(input_wav: Path, file: Path) -> dict:
    """score.py's alignment of `file` against `input_wav`, and whether it aligns (most windows peak at ALIGN_PEAK
    or more, and the lags' MAD under ALIGN_MAD_MS)."""
    from eval.scorer import score as SC
    r = SC.align(SC.decode(str(input_wav)), SC.decode(str(file)))
    if r is None:
        raise Refused(f"{input_wav} is too short to align against")
    n = len(r["windows"])
    ok = r["windows_peak_ge_0.3"] > n / 2 and r["lag_mad_ms"] < ALIGN_MAD_MS
    return {"lag_ms": r["lag_ms"], "windows": n, "windows_peak_ge_0.3": r["windows_peak_ge_0.3"],
            "lag_mad_ms": r["lag_mad_ms"], "aligned": ok}


def cmd_align(a) -> int:
    refs = Path(a.refs) if a.refs else data_dir() / "stress"
    wav = refs / a.id / "input.wav"
    if not wav.is_file():
        raise Refused(f"no {wav}: build the set first (eval/build_refs.sh --set stress)")
    r = align_file(wav, Path(a.file))
    print(f"{a.id}: lag {r['lag_ms']:+.1f} ms; {r['windows_peak_ge_0.3']}/{r['windows']} windows peak at "
          f"{ALIGN_PEAK} or more; lags' MAD {r['lag_mad_ms']:.2f} ms: "
          + ("ALIGNED" if r["aligned"] else "NOT aligned (another recording, edit or mix)"))
    return 0 if r["aligned"] else 1


# ------------------------------------------------------------------------------------------------ lyrics

def sng_files(path: Path, names: tuple[str, ...]) -> dict[str, bytes]:
    """The named files of a .sng package, in memory (eval/refs/sng_unpack.py's format)."""
    import numpy as np
    b = Path(path).read_bytes()
    if b[:6] != b"SNGPKG":
        raise Refused(f"{path} is not a .sng package")
    mask = np.frombuffer(b[10:26], dtype=np.uint8)
    p = 26
    _, count = struct.unpack_from("<QQ", b, p)
    p += 16
    for _ in range(count):
        kl = struct.unpack_from("<i", b, p)[0]
        p += 4 + kl
        vl = struct.unpack_from("<i", b, p)[0]
        p += 4 + vl
    _, count = struct.unpack_from("<QQ", b, p)
    p += 16
    out = {}
    for _ in range(count):
        nl = b[p]
        p += 1
        name = b[p:p + nl].decode()
        p += nl
        cl, ci = struct.unpack_from("<QQ", b, p)
        p += 16
        if name in names:
            i = np.arange(cl, dtype=np.int64)
            out[name] = (np.frombuffer(b[ci:ci + cl], dtype=np.uint8) ^ (mask[i % 16] ^ (i & 0xFF).astype(np.uint8))
                         ).tobytes()
    return out


def chart_delay_s(ref_folder: Path) -> float:
    """score.py's chart delay of a built reference (song.ini delay, else the .chart Offset), in seconds."""
    rn = read_json(ref_folder / "ref_notes.json")
    return float((rn.get("delay") or 0) or (rn.get("chart_offset") or 0)) / 1000.0


def lyrics_check(sid: str, refs: Path, sng_dir: Path, tmp_root: Path | None = None, run_dir: Path | None = None,
                 engines=None, threads: int | None = 2, out: Callable[[str], None] = print) -> int:
    """The lyrics check (the module docstring). Prints numbers only; 0, or 2 when it could not run."""
    from eval import golden as G
    from eval import lyrics_timing as LT
    from songcharter import pipeline as P
    song = next((s for s in built_songs(refs) if s["id"] == sid), None)
    if song is None:
        raise Refused(f"{sid} is not in {refs / 'songs.json'}")
    sng = sng_dir / f"{song['md5']}.sng"
    files = sng_files(sng, ("notes.mid", "notes.chart"))
    if not files:
        raise Refused(f"{sid}: the primary package has no notes.mid or notes.chart")
    kind = "mid" if "notes.mid" in files else "chart"
    try:
        human = LT.read(files["notes." + kind], kind)
    except Exception as e:  # noqa: BLE001  the message could quote a word
        out(f"{sid}: the human chart's lyrics could not be read ({type(e).__name__})")
        return 2
    del files
    if not human.times:
        out(f"{sid}: the primary chart has no lyric events (no vocals): nothing to check")
        return 0
    human = human.shifted(chart_delay_s(Path(song["folder"])))
    kept = before = None
    if run_dir is not None:
        work = Path((read_json(run_dir / "summary.json").get("run") or {}).get("work") or "")
        kept = work / sid
        if G.finished(kept) is None:
            raise Refused(f"{kept} is not a finished kept folder of that run")
        # the work folder hard-links the kept decode and stems, so it must be on their file system: under the kept
        # folders' own .runs/, named as golden names a run's folder (<pid>-<hex>: a golden run clears only the dead)
        tmp_root = tmp_root or work / G.RUNS
        tmp_root.mkdir(parents=True, exist_ok=True)
        if os.stat(tmp_root).st_dev != os.stat(kept).st_dev:
            raise Refused(f"--tmp {tmp_root} is not on the file system of {kept}: the work folder links its files")
    tmp = Path(tempfile.mkdtemp(prefix=f"{os.getpid()}-lyrics-", dir=str(tmp_root) if tmp_root else None))
    try:
        work_dir, song_dir = tmp / "work", tmp / "song"
        if kept is not None:
            before = G.manifest(kept)
            G.private_folder(kept, work_dir, ())
        options = P.Options(lyrics=human.aligner_text(), takes=1, device="cpu", preview=False, work=work_dir,
                            threads=threads)
        log: list[str] = []      # the pipeline's lines hold no word, but are not printed: the numbers are
        try:
            result = P.chart(Path(song["folder"]) / "input.wav", song_dir, options, engines=engines, log=log.append,
                             sampler=None)
            ours = LT.read(result.folder / "notes.chart").shifted(-result.assembled.lead.pad_seconds)
        except Exception as e:  # noqa: BLE001  never a message: it could quote the text
            out(f"{sid}: the lyrics chart failed ({type(e).__name__})")
            return 2
        stats = LT.compare(human, ours)
        warned = [w for w in result.warnings if w.lower().startswith("lyrics")]
        conf = ((result.lyrics or {}).get("confidence") or {}).get("median")
        out(f"{sid}: {stats['paired']} of {stats['words_ref']} human words paired ({_f(stats['paired_share'])}; "
            f"{stats['words_cand']} in our chart); median error {_f(stats['median_abs_ms'], 1)} ms "
            f"(signed {_f(stats['median_ms'], 1)}); within 50 / 100 / 250 ms {_f(stats['within_50ms'])} / "
            f"{_f(stats['within_100ms'])} / {_f(stats['within_250ms'])}; phrase starts over 500 ms off "
            f"{_f(stats['phrase_starts_over_500ms'])} of {_f(stats.get('phrase_starts_paired'))}; gate "
            f"{'OK' if result.ok else 'FAILED'}; the pipeline warned about the lyrics: "
            f"{'yes (%d)' % len(warned) if warned else 'no'}; median confidence {_f(conf, 2)}")
        out(json.dumps({"lyrics_check": sid, **stats, "gate_ok": result.ok, "warned": len(warned),
                        "confidence_median": conf}))
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        if kept is not None and G.manifest(kept) != before:
            raise RuntimeError(f"the kept folder {kept} changed during the lyrics check")


def cmd_lyrics(a) -> int:
    refs = Path(a.refs) if a.refs else data_dir() / "stress"
    return lyrics_check(a.id, refs, Path(a.sng) if a.sng else data_dir() / "sng", Path(a.tmp) if a.tmp else None,
                        Path(a.run).resolve() if a.run else None, threads=a.threads)


# ------------------------------------------------------------------------------------------------ baseline

PATH = re.compile(r"(?<![\w<>~.])/(?:[\w.@+-]+/)*([\w.@+-]+)")


def _secret(x: str) -> re.Pattern:
    """A value of the local list as a whole word, any case (never inside a longer run of letters and digits, such
    as a track's hash)."""
    return re.compile(r"(?<![A-Za-z0-9])" + re.escape(x) + r"(?![A-Za-z0-9])", re.IGNORECASE)


def scrub(obj, secrets: list[str]):
    """Every string with its absolute paths cut to "<path>/<last part>" and each secret replaced by "<redacted>"."""
    if isinstance(obj, dict):
        return {scrub(k, secrets): scrub(v, secrets) for k, v in obj.items()}
    if isinstance(obj, list):
        return [scrub(v, secrets) for v in obj]
    if isinstance(obj, str):
        s = PATH.sub(lambda m: "<path>/" + m.group(1), obj)
        for x in secrets:
            s = _secret(x).sub("<redacted>", s)
        return s
    return obj


def secrets_of(songs: list[dict]) -> list[str]:
    """What the local list holds that must not be committed: md5s, titles, artists and charters (but a value that is
    a song's generic id, or under 3 characters, which would match everywhere)."""
    ids = {s["id"].lower() for s in songs}
    out = set()
    for s in songs:
        for e in [s] + list(s.get("alts") or []):
            for k in ("md5", "title", "artist", "charter"):
                v = str(e.get(k) or "").strip()
                if len(v) >= 3 and v.lower() not in ids:
                    out.add(v)
    return sorted(out, key=len, reverse=True)


def cmd_baseline(a) -> int:
    run_dir, dest = Path(a.run_dir).resolve(), Path(a.out).resolve()
    songs = load_set(local=Path(a.local) if a.local else None)
    secrets = secrets_of(songs)
    dest.mkdir(parents=True, exist_ok=True)
    for name in ("summary.json", "stress_scores.json"):
        data = scrub(read_json(run_dir / name), secrets)
        text = json.dumps(data, indent=1, ensure_ascii=False) + "\n"
        left = [x for x in secrets if _secret(x).search(text)] + [p for p in ("/home/", "/tmp/", "/dev/shm/", "/root/")
                                                                   if p in text]
        if left:
            raise Refused(f"{name}: {len(left)} value(s) of the local list or a path left after scrubbing")
        (dest / name).write_text(text, encoding="utf-8")
        print(f"{dest / name}: scrubbed ({len(secrets)} values of the local list checked)")
    return 0


# ------------------------------------------------------------------------------------------------ main

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python eval/stress.py", description=__doc__.split("\n\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="command", required=True)
    s = sub.add_parser("songs", help="the set, merged with the local list")
    s.add_argument("--json", action="store_true", help="the merged list as JSON (build_refs.sh reads it)")
    s.add_argument("--local", help="the owner's list (default $EVAL_DATA/stress.local.json)")
    s.add_argument("--set", help="the set (default eval/stress.json)")
    s = sub.add_parser("score", help="score a run against every human chart; the feel report")
    s.add_argument("run_dir")
    s.add_argument("--refs", help="the built set (default: the run's --refs)")
    s.add_argument("--work", help="the kept work folders (default: the run's --work)")
    s.add_argument("--windows", type=float, default=WINDOW_S, help="the window, s (default 30)")
    s = sub.add_parser("compare", help="two stress_scores.json side by side; exit 1 on a regression")
    s.add_argument("old")
    s.add_argument("new")
    s = sub.add_parser("align", help="a file's audio against a song's input.wav")
    s.add_argument("id")
    s.add_argument("file")
    s.add_argument("--refs", help="the built set (default $EVAL_DATA/stress)")
    s = sub.add_parser("lyrics", help="the lyrics timing check on a song (numbers only)")
    s.add_argument("id")
    s.add_argument("--run", help="a stress run whose kept folder the chart starts from")
    s.add_argument("--refs", help="the built set (default $EVAL_DATA/stress)")
    s.add_argument("--sng", help="the packages (default $EVAL_DATA/sng)")
    s.add_argument("--tmp", help="where the temporary folder goes (default the system's; with --run, the kept "
                                 "folders' .runs/, on their file system)")
    s.add_argument("--threads", type=int, default=2)
    s = sub.add_parser("baseline", help="a run's summary and scores, scrubbed, for eval/baseline/stress/")
    s.add_argument("run_dir")
    s.add_argument("out")
    s.add_argument("--local", help="the owner's list (default $EVAL_DATA/stress.local.json)")
    a = ap.parse_args(argv)
    try:
        return {"songs": cmd_songs, "score": cmd_score, "compare": cmd_compare, "align": cmd_align,
                "lyrics": cmd_lyrics, "baseline": cmd_baseline}[a.command](a)
    except (Refused, OSError) as e:
        print(f"stress: error: {e}", file=sys.stderr)
        return 2
    except Exception as e:  # noqa: BLE001  a bug; for lyrics, its type only (a message could quote the text)
        if a.command == "lyrics":
            print(f"stress: internal error ({type(e).__name__})", file=sys.stderr)
        else:
            traceback.print_exc()
        return 3


if __name__ == "__main__":
    sys.exit(main())
