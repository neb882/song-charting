"""p1_ceiling.py: part 1, the quantizer's ceiling. For each of part D's 10 rate8 songs and each human chart with Expert
guitar notes: the chart's onsets are moved into our audio's frame (score.py's constant lag of our song.ogg against
the chart's input.wav, a_align.py's ours9), put through songcharter.quantize.quantize_part with the guitar's rules on
our grid (our chart's tempo map, lead-in pad and grid octave; the offset measured and applied as assemble._offset does,
on assemble.offset_map), moved back, and matched at 100 ms (score.py's match) to the unquantized onsets. Recall in
part D's fast windows (score.py's 30-s windows over the chart's span, a window fast when the chart plays 8 or more
notes a second over it) and outside them; per chart, per song (mean over charts, as part D) and pooled (song mean and
note-pooled). Variants patch the quantizer in memory only: inside a fast run (quantize.fast_runs, 8 onsets each at most
0.125 s apart) a non-triplet beat gets 6 or 8 straight slots (x2 on a halved grid). Writes <shm>/ceiling/p1.json
(labels and numbers only)."""
import dataclasses, json, re, sys
from dataclasses import replace
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
import cl
from cl import S
from songcharter import quantize as Q, assemble as A
from songcharter.tempo import Tempo, TempoMap, TimeSignature
from songcharter.timed import TimedNote, TimedPart
from songcharter.chart import OPEN

W = 30.0
LANE = {"green": 0, "red": 1, "yellow": 2, "blue": 3, "orange": 4, "open": OPEN}


def tempo_map(chart_path):
    t = Path(chart_path).read_text(encoding="utf-8-sig")
    res = int(re.search(r"Resolution\s*=\s*(\d+)", t).group(1))
    body = re.search(r"\[SyncTrack\]\s*\{(.*?)\}", t, re.S).group(1)
    tempos, tss = [], []
    for tick, kind, rest in re.findall(r"(\d+)\s*=\s*(B|TS)\s+([\d ]+)", body):
        v = [int(x) for x in rest.split()]
        if kind == "B": tempos.append(Tempo(int(tick), v[0]))
        else: tss.append(TimeSignature(int(tick), v[0], 2 ** v[1] if len(v) > 1 else 4))
    return TempoMap(res, tempos, tss or [TimeSignature(0, 4)])


@dataclasses.dataclass(frozen=True)
class RunGrid(Q.SnapGrid):
    run_beats: frozenset = frozenset()
    run_n: int = 0

    def _slots(self, tick):
        res = self.tempo_map.resolution
        j = self.beat_of(tick)
        n = self.triplet if j in self.triplet_beats else (self.run_n if j in self.run_beats else self.straight)
        return j, n, (tick - j * res) * n / res


_orig_from_ticks = Q.SnapGrid.from_ticks.__func__
PATCH = {"run_n": 0, "times": None}


def _patched(cls, ticks, tm, rules=Q.RULES):
    g = _orig_from_ticks(Q.SnapGrid, ticks, tm, rules)
    if not PATCH["run_n"]:
        return g
    x = np.asarray(ticks, dtype=np.float64)
    secs = tm.ticks_to_secs(x)
    fast = Q.fast_runs(list(secs), Q.TAP_RUN, Q.TAP_RUN_GAP_S)
    beats = frozenset(g.beat_of(v) for v, f in zip(x, fast) if f) - g.triplet_beats
    return RunGrid(g.tempo_map, g.straight, g.triplet, g.triplet_beats, g.sigma_s, g.reach, beats, PATCH["run_n"])


Q.SnapGrid.from_ticks = classmethod(_patched)


def our_grid(label):
    f = cl.our_folder(label)
    rep = json.loads((f / "report.json").read_text())
    tm = tempo_map(f / "notes.chart")
    pad = rep["lead_in"]["pad_seconds"]
    octave = rep["grid"]["octave"]
    return tm, pad, octave


def timed_notes(notes, shift_s):
    """scan-chart notes -> TimedNotes (one per tick, frets the union), in our input's seconds."""
    g = {}
    for n in notes:
        lane = LANE.get(n["type"])
        if lane is None: continue
        o = g.setdefault(n["tick"], {"t": n["ms"] / 1000.0 + shift_s, "frets": set(), "len": 0.0, "tap": False})
        o["frets"].add(lane); o["len"] = max(o["len"], (n.get("msLength") or 0) / 1000.0)
        o["tap"] = o["tap"] or "tap" in (n.get("flags") or [])
    out = []
    for o in sorted(g.values(), key=lambda o: o["t"]):
        fr = (OPEN,) if OPEN in o["frets"] else tuple(sorted(o["frets"]))
        out.append(TimedNote(o["t"], fr, o["t"] + o["len"] if o["len"] > 0 else None, None, o["tap"]))
    return out


def quantized_times(label, tm, pad, octave, notes_in, variant):
    rules = A.HOPO_RULES["forced"]
    if octave == 0.5: rules = A._halved_slots(rules)
    rules = replace(rules, run_chord_s=A.RUN_CHORD_S)
    beats = tm.ticks_to_secs(np.arange(0, tm.sec_to_tick(max(n.time for n in notes_in) + pad + 10) // tm.resolution + 2)
                             * tm.resolution)
    tm_off = A.offset_map(tm, beats, octave)
    times = [n.time for n in notes_in]
    m, c = Q.estimate_offset(times, tm_off, pad)
    off = m if Q.RULES.applies(m, c, len(set(times))) else 0.0
    PATCH["run_n"] = 0 if variant == "base" else int(variant) * (2 if octave == 0.5 else 1)
    track, rep = Q.quantize_part(TimedPart("guitar", "expert", notes_in), tm, pad, off, rules)
    PATCH["run_n"] = 0
    return np.array(sorted({tm.tick_to_sec(n.tick) for n in track.notes})), off, rep


def windows(rt, qt, span):
    p = S.match(rt, qt, 0.100)
    ws = S.window_scores(rt, qt, p, span, W)["windows"]
    out = []
    for w in ws:
        a = w["start_s"]; b = min(a + W, span[1]); ln = max(b - a, 1e-6)
        out.append({"start": a, "n": w["n_ref"], "matched": w["matched"], "fast": w["n_ref"] / ln >= 8.0})
    return out


def main():
    AL = json.loads((cl.SHM / "align.json").read_text())
    res = {}
    for label in cl.FAST:
        tm, pad, octave = our_grid(label)
        row = {"octave": octave, "charts": {}}
        for k, folder in cl.charts(label):
            rsc = cl.scan(folder / "ref")
            notes = cl.gtrack(rsc)
            if not notes: continue
            a = AL[label][k]
            rdel, span = a["ref_delay_ms"], a["span"]
            lag = a["ours9"]["lag_ms"] / 1000.0
            ro = S.onsets(notes, rdel, "guitar")
            rt = np.array([o["t"] for o in ro])
            # chart frame t -> our song.ogg u = t + lag -> our input seconds u - pad
            tn = timed_notes(notes, rdel / 1000.0 + lag - pad)
            ch = {}
            for v in ("base", "6", "8"):
                q, off, rep = quantized_times(label, tm, pad, octave, tn, v)
                qt = np.sort(q - lag)      # back to the chart's frame
                ws = windows(rt, qt, span)
                f = [w for w in ws if w["fast"]]; s = [w for w in ws if not w["fast"]]
                ch[v] = {"offset_ms": round(off * 1000, 3), "notes_out": rep.notes_out, "n_in": len(tn),
                         "dropped": rep.dropped + rep.dropped_distinct, "merged": rep.merged,
                         "fast_windows": len(f), "fast_n": sum(w["n"] for w in f), "fast_m": sum(w["matched"] for w in f),
                         "out_n": sum(w["n"] for w in s), "out_m": sum(w["matched"] for w in s)}
            row["charts"][k] = ch
            print(label, k, {v: (ch[v]["fast_m"], ch[v]["fast_n"], ch[v]["out_m"], ch[v]["out_n"]) for v in ch}, flush=True)
        res[label] = row
    (cl.SHM / "p1.json").write_text(json.dumps(res))


if __name__ == "__main__":
    main()
