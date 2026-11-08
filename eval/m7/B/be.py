"""M7-01 B-e, Expert drums: kicks and fill endings. Reads each chart's Expert drums through drums_scan.cjs (scan-chart),
the note cache's time shifts (common.py), our report.json (sections, fill_crash_share); writes be.json, prints a check
line per song (numbers only)."""
import json, sys, bisect, subprocess
import numpy as np
from common import songs, build, paths, report, rj, S
SCAN = str(__import__('pathlib').Path(__file__).resolve().parent / 'drums_scan.cjs')
TOL = 0.05

def scan(folder):
    return json.loads(subprocess.run(['node', SCAN, str(folder)], capture_output=True, text=True, check=True).stdout)

class Chart:
    def __init__(self, d, shift_ms):
        self.d, self.res = d, d['resolution']; self.shift = shift_ms
        self.tp = sorted(d['tempos'], key=lambda x: x['tick'])
        g = {}
        for n in d.get('notes') or []:
            g.setdefault(n['tick'], []).append(n)
        self.ticks = sorted(g); self.g = g
        self.t = np.array([self.sec(k) for k in self.ticks])
        self.pro = d.get('drumType') == 1
        self.cym = {p: sorted(n['tick'] for n in d.get('notes') or [] if 'cymbal' in n['flags'] and n['type'] == T[p]) for p in (2, 3, 4)}
        self.fills = [f for f in d.get('fills') or [] if not f['isCoda']]
        self.db = S.downbeat_times({'resolution': self.res, 'tempos': self.tp, 'timeSignatures': d['timeSignatures']}, -10, 1e5, shift_ms)
    def sec(self, tick):
        tp = next((x for x in reversed(self.tp) if x['tick'] <= tick), self.tp[0])
        return (tp['msTime'] + (tick - tp['tick']) * 60000.0 / (tp['beatsPerMinute'] * self.res) + self.shift) / 1000
    def is_crash(self, n):   # starpower._Fills._crash
        if 'cymbal' not in n['flags']: return False
        p = {v: k for k, v in T.items()}.get(n['type'])
        if p == 4: return True
        if p not in (2, 3): return False
        run = self.cym[p]; sp = 2 * self.res
        return bisect.bisect_right(run, n['tick'] + sp) - bisect.bisect_left(run, n['tick'] - sp) - 1 < 3
    def crash_at(self, tick): return any(self.is_crash(n) for n in self.g.get(tick, []))
    def crash_near(self, t, tol=TOL, any_cym=False):
        i0, i1 = np.searchsorted(self.t, t - tol), np.searchsorted(self.t, t + tol, 'right')
        return any((('cymbal' in n['flags']) if any_cym else self.is_crash(n)) for k in self.ticks[i0:i1] for n in self.g[k])
T = {0: 'kick', 1: 'redDrum', 2: 'yellowDrum', 3: 'blueDrum', 4: 'greenDrum'}

def kicks(c, span):
    """kick onset times, double-kick flags, bare flags, 16th-run flags (>= 4 kicks, gaps <= a 16th), inside span."""
    rows = []
    for k, t in zip(c.ticks, c.t):
        if not (span[0] - .1 <= t <= span[1] + .1): continue
        ns = c.g[k]; kk = [n for n in ns if n['type'] == 'kick']
        rows.append((t, k, bool(kk), bool(kk) and len(ns) == len(kk), any('doubleKick' in n['flags'] for n in kk)))
    kt = [(t, k, bare, dbl) for t, k, isk, bare, dbl in rows if isk]
    run = np.zeros(len(kt), bool); s = c.res / 4 + 1
    i = 0
    while i < len(kt):
        j = i
        while j + 1 < len(kt) and kt[j + 1][1] - kt[j][1] <= s: j += 1
        if j - i + 1 >= 4: run[i:j + 1] = True
        i = j + 1
    return rows, np.array([x[0] for x in kt]), np.array([x[3] for x in kt], bool), run

def feel(c, span):
    rows, kt, dbl, run = kicks(c, span)
    dur = span[1] - span[0]
    dens = max((np.searchsorted(kt, x + 10) - i for i, x in enumerate(kt)), default=0) / 10
    return {'kicks_per_s': len(kt) / dur, 'kicks_per_s_peak10': dens, 'kick_share': np.mean([r[2] for r in rows]),
            'bare_kick_share': np.mean([r[3] for r in rows]), 'double_kick_share': float(dbl.mean()) if len(dbl) else 0.0,
            'kick_16th_run_share': float(run.mean()) if len(run) else 0.0, 'n_onsets': len(rows)}, kt, dbl, run

def main():
    res = {}
    for lab, st, sid in songs():
        c = build(lab, st, sid); P = paths(st, sid); rep = report(st, sid)
        folder = P['run'] / rj(P['run'] / 'summary.json')['songs'][sid]['folder']
        ours = Chart(scan(folder), c['ours']['shift_ms'])
        hum = {}
        alts = dict(P['alts'])
        for k, h in c['humans'].items():
            if 'drums' not in h['parts']: continue
            hum[k] = Chart(scan((P['refdir'] if k == 'primary' else alts[k]) / 'ref'), h['shift_ms'])
        if not hum or not ours.ticks: continue
        r = {'charts': len(hum), 'humans': {}}
        near_all = np.zeros(0)
        okt = None
        for k, h in hum.items():
            sp = (h.t[0], h.t[-1])
            hf, hkt, hdbl, _ = feel(h, sp)
            of, okt_k, odbl_k, orun_k = feel(ours, sp)
            pr = len(S.match(np.sort(hkt), okt_k, TOL))
            pr_nd = len(S.match(np.sort(hkt[~hdbl]), okt_k[~odbl_k], TOL))
            r['humans'][k] = {**hf, 'pro': h.pro, 'ours_on_its_span': of,
                              'kick_precision': pr / len(okt_k) if len(okt_k) else None, 'kick_recall': pr / len(hkt) if len(hkt) else None,
                              'kick_precision_no2x': pr_nd / max((~odbl_k).sum(), 1), 'kick_recall_no2x': pr_nd / max((~hdbl).sum(), 1)}
        # ours song-wide over the primary's span (the score's span)
        psp = (hum[next(iter(hum))].t[0], hum[next(iter(hum))].t[-1])
        of, okt, odbl, orun = feel(ours, psp)
        r['ours'] = of
        hk = [np.sort(feel(h, (h.t[0], h.t[-1]))[1]) for h in hum.values()]
        from stats import near_any
        um = ~near_any(okt, hk, TOL)
        r['ours_unmatched_kicks'] = int(um.sum()); r['ours_kicks'] = len(okt)
        r['unmatched_in_16th_runs'] = float((um & orun).sum() / um.sum()) if um.sum() else None
        r['matched_in_16th_runs'] = float((~um & orun).sum() / (~um).sum()) if (~um).sum() else None
        r['unmatched_2x_share'] = float((um & odbl).sum() / um.sum()) if um.sum() else None
        # fills
        oc = [ours.crash_at(f['tick'] + f['length']) for f in ours.fills]
        r['ours_fills'] = len(oc); r['ours_fill_crash_share'] = float(np.mean(oc)) if oc else None
        r['report_fill_crash_share'] = (rep['phrases'].get('drums') or {}).get('fill_crash_share')
        pro = {k: h for k, h in hum.items() if h.pro}
        r['humans_fill'] = {k: {'fills': len(h.fills), 'crash_share': float(np.mean([h.crash_at(f['tick'] + f['length']) for f in h.fills])) if h.fills else None} for k, h in pro.items()}
        # the humans' crash at our sections' starts (nearest of their downbeats within 100 ms)
        secs = [s[0] for s in rep['sections']['list']]
        hs = {}
        for k, h in pro.items():
            v = []
            for t in secs:
                if not (h.t[0] + 0.5 < t < h.t[-1]): continue
                i = np.argmin(np.abs(h.db - t)) if len(h.db) else None
                if i is None or abs(h.db[i] - t) > 0.1: continue
                v.append(h.crash_near(h.db[i]))
            hs[k] = float(np.mean(v)) if v else None
        r['humans_crash_at_section_start'] = hs
        # candidate: a crash added at the end of each of our fills that has none; precision = a pro human chart has a crash
        # (or any cymbal) within 50 ms there
        add = [ours.sec(f['tick'] + f['length']) for f, x in zip(ours.fills, oc) if not x]
        inspan = [t for t in add if any(h.t[0] <= t <= h.t[-1] for h in pro.values())]
        r['add_crash'] = {'n': len(add), 'judged': len(inspan),
                          'precision_crash': float(np.mean([any(h.crash_near(t) for h in pro.values()) for t in inspan])) if inspan else None,
                          'precision_cymbal': float(np.mean([any(h.crash_near(t, any_cym=True) for h in pro.values()) for t in inspan])) if inspan else None,
                          'any_onset_there': float(np.mean([any(np.min(np.abs(h.t - t)) <= TOL for h in pro.values()) for t in inspan])) if inspan else None}
        # where do our fills end: at a human fill end / a human downbeat
        r['ours_fill_end_on_human_downbeat'] = float(np.mean([any(len(h.db) and np.min(np.abs(h.db - ours.sec(f['tick'] + f['length']))) <= TOL for h in hum.values()) for f in ours.fills])) if ours.fills else None
        res[lab] = r
        print(lab, len(hum), round(r['ours']['bare_kick_share'], 3), r['ours_fill_crash_share'], r['report_fill_crash_share'], flush=True)
    json.dump(res, open(sys.argv[1], 'w'), indent=1, default=float)


if __name__ == '__main__':
    main()
