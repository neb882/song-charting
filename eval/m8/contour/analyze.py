"""analyze.py: reads the songs (clib.songs(): our Expert guitar, the human charts' notes) and <shm>/m8c/pitch/*.json
(pitch.py); measures fast-run direction agreement (ours today, each tracker, each tracker where confident, the humans'
own agreement) and a re-laning candidate per tracker; writes results.json beside this script and prints the tables
(markdown) to stdout."""
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import clib  # noqa: E402
from clib import S, mlane, boot  # noqa: E402

PITCH = '<shm>/m8c/pitch'
TRACKERS = ('pyin', 'cqt', 'hs')
DEAD = 0.5          # semitones: a smaller pitch change is "same"
VARIANTS = [f'{t}{c}' for t in TRACKERS for c in ('', '_conf')] + ['pyin_step1', 'none']   # pyin_step1: pYIN only where it moves >= 1 semitone; none: the re-laning with our own directions (control)


def r3(x):
    return None if x is None else round(float(x), 3)


def sgn(x):
    return int(np.sign(x))


def tracker_dirs(co, P):
    """{variant: {j: direction from onset j-1 to j}} for fast-run onsets j whose predecessor is in the same run.
    '<t>' has every pair where both pitches exist; '<t>_conf' only where both are confident: both confidences at or above the
    song's median (pYIN: the mean voiced probability over the window, which is low on these stems, mostly under 0.3;
    CQT peaks: the peak/mean ratio of the window's spectrum)."""
    pos = {j: n for n, j in enumerate(P['idx'])}
    run = dict(zip(P['idx'], P['run']))
    med = {t: np.nanmedian([v for v in P[t + '_conf'] if v is not None] or [np.nan]) for t in TRACKERS}
    out = {v: {} for v in VARIANTS}
    for j in P['idx']:
        if j - 1 not in run or run[j - 1] != run[j]:
            continue
        a, b = pos[j - 1], pos[j]
        for t in TRACKERS:
            pa, pb = P[t][a], P[t][b]
            if pa is None or pb is None:
                continue
            d = pb - pa
            dd = 0 if abs(d) < DEAD else sgn(d)
            out[t][j] = dd
            if t == 'pyin' and abs(d) >= 1.0:
                out['pyin_step1'][j] = sgn(d)
            ca, cb = P[t + '_conf'][a], P[t + '_conf'][b]
            ok = ca >= med[t] and cb >= med[t]
            if ok:
                out[t + '_conf'][j] = dd
    return out


def fast_pairs(ro, co, rid):
    """Our consecutive fast-run onsets (j-1, j) in one run, both matched at 50 ms to consecutive notes of this chart:
    {j: (i-1, i)}."""
    m = {j: i for i, j in S.match(np.array([o['t'] for o in ro]), np.array([o['t'] for o in co]), clib.TOL)}
    out = {}
    for j in range(1, len(co)):
        if rid[j] >= 0 and rid[j - 1] == rid[j] and j in m and j - 1 in m and m[j] == m[j - 1] + 1:
            out[j] = (m[j - 1], m[j])
    return out


def hdir(ro, i0, i1):
    return sgn(mlane(ro[i1]) - mlane(ro[i0]))


def relane(co, rid, td):
    """Our onsets with single notes in fast runs re-laned: the run's first note kept; each next single note moves one
    lane in the tracker's direction from the previous (re-laned) note, our own direction where the tracker has none;
    clamped to 0-4. Chords and opens keep their lanes."""
    new = [dict(o, lanes=list(o['lanes'])) for o in co]
    prev = None
    for j in range(len(co)):
        if rid[j] < 0:
            prev = None
            continue
        if prev is None or rid[j - 1] != rid[j]:
            prev = mlane(new[j])
            continue
        o = co[j]
        if len(o['lanes']) == 1 and o['lanes'][0] >= 0:
            d = td.get(j, sgn(mlane(co[j]) - mlane(co[j - 1])))
            new[j]['lanes'] = [int(np.clip(round(prev) + d, 0, 4))]
        prev = mlane(new[j])
    return new


def contour_scorepy(ro, co, tol=0.100, only=None):
    """score.py's lane_direction_agreement (consecutive matched reference onsets, chords by mean lane) and its exact
    lane agreement; `only` (a set of our onset indices) keeps pairs whose both our onsets are in it."""
    pairs = S.match(np.array([o['t'] for o in ro]), np.array([o['t'] for o in co]), tol)
    ex = [frozenset(ro[i]['lanes']) == frozenset(co[j]['lanes']) for i, j in pairs if only is None or j in only]
    ag = n = 0
    for (i0, j0), (i1, j1) in zip(pairs, pairs[1:]):
        if i1 != i0 + 1 or (only is not None and not (j0 in only and j1 in only)):
            continue
        n += 1
        ag += sgn(mlane(ro[i1]) - mlane(ro[i0])) == sgn(mlane(co[j1]) - mlane(co[j0]))
    return (ag / n if n else None), (float(np.mean(ex)) if ex else None), n


def f1_50(ro, co, span):
    rt, ct = np.array([o['t'] for o in ro]), np.array([o['t'] for o in co])
    p = S.match(rt, ct, clib.TOL)
    return S.prf(len(p), len(rt), S.n_cand_eff(p, ct, span))['f1']


def song_rows(s, P):
    co = s['ours']
    t = np.array([o['t'] for o in co])
    rid = clib.fast_runs(t)
    fast = set(np.where(rid >= 0)[0].tolist())
    td = tracker_dirs(co, P)
    row = {'label': s['label'], 'set': s['set'], 'stem': s['stem_kind'], 'n_fast_onsets': len(fast),
           'n_runs': int(rid.max() + 1), 'n_charts': len(s['humans']), 'clock': P['clock']}
    row['fast_single_share'] = r3(np.mean([len(co[j]['lanes']) == 1 for j in fast]))
    row['coverage'] = {t_: r3(len(td[t_]) / max(1, sum(1 for j in fast if j - 1 in fast and rid[j - 1] == rid[j])))
                       for t_ in VARIANTS}
    # 1-3: directions against each chart; the primary first
    per_chart = []
    fp_prim = None
    for h in s['humans']:
        ro = h['ons']
        fp = fast_pairs(ro, co, rid)
        if h['k'] == 'primary':
            fp_prim = (ro, fp)
        hd = {j: hdir(ro, *ii) for j, ii in fp.items()}
        od = {j: sgn(mlane(co[j]) - mlane(co[j - 1])) for j in fp}
        c = {'k': h['k'], 'n_pairs': len(fp)}
        if fp:
            c['human_dir'] = {k: r3(np.mean([v == x for v in hd.values()])) for k, x in (('up', 1), ('down', -1), ('same', 0))}
            c['ours_dir'] = {k: r3(np.mean([v == x for v in od.values()])) for k, x in (('up', 1), ('down', -1), ('same', 0))}
            c['agree_ours'] = r3(np.mean([od[j] == hd[j] for j in fp]))
            for v in VARIANTS:
                # fallback: our own direction where the tracker has none
                c['agree_' + v] = r3(np.mean([td[v].get(j, od[j]) == hd[j] for j in fp]))
                sub = [j for j in fp if j in td[v]]
                c['sub_' + v] = {'n': len(sub), 'tracker': r3(np.mean([td[v][j] == hd[j] for j in sub])) if sub else None,
                                 'ours': r3(np.mean([od[j] == hd[j] for j in sub])) if sub else None}
        # 4: re-laning, against this chart
        f1 = f1_50(ro, co, s['span'])
        cs, ex, _ = contour_scorepy(ro, co)
        cf, exf, _ = contour_scorepy(ro, co, tol=clib.TOL, only=fast)
        c['today'] = {'contour100': r3(cs), 'exact100': r3(ex), 'contour_fast50': r3(cf), 'exact_fast50': r3(exf), 'f1_50': r3(f1)}
        c['relane'] = {}
        for v in VARIANTS:
            nc = relane(co, rid, td[v])
            cs2, ex2, _ = contour_scorepy(ro, nc)
            cf2, exf2, _ = contour_scorepy(ro, nc, tol=clib.TOL, only=fast)
            f12 = f1_50(ro, nc, s['span'])
            c['relane'][v] = {'contour100': r3(cs2), 'exact100': r3(ex2), 'contour_fast50': r3(cf2),
                              'exact_fast50': r3(exf2), 'f1_50': r3(f12), 'n_moved': sum(nc[j]['lanes'] != co[j]['lanes'] for j in fast)}
        per_chart.append(c)
    row['charts'] = per_chart
    row['check_scorepy_primary'] = {'here': per_chart[0]['today']['contour100'], 'score_json': s['score_py']['contour'],
                                    'exact_here': per_chart[0]['today']['exact100'], 'exact_json': s['score_py']['exact']}
    # the ceiling: each other chart against the primary, on our fast-run pairs matched (50 ms, consecutive) in both
    ro_p, fp_p = fp_prim
    ceil = []
    for h in s['humans'][1:]:
        fa = fast_pairs(h['ons'], co, rid)
        both = [j for j in fp_p if j in fa]
        if both:
            ceil.append({'k': h['k'], 'n': len(both),
                         'alt_vs_primary': r3(np.mean([hdir(h['ons'], *fa[j]) == hdir(ro_p, *fp_p[j]) for j in both])),
                         'ours_vs_primary_same_pairs': r3(np.mean([sgn(mlane(co[j]) - mlane(co[j - 1])) == hdir(ro_p, *fp_p[j]) for j in both]))})
    row['ceiling'] = ceil
    row['ceiling_mean'] = r3(np.mean([c['alt_vs_primary'] for c in ceil])) if ceil else None
    return row


def mean_over_charts(row, f):
    xs = [f(c) for c in row['charts'] if c['n_pairs']]
    xs = [x for x in xs if x is not None]
    return float(np.mean(xs)) if xs else None


def main():
    rows = []
    for s in clib.songs():
        p = os.path.join(PITCH, s['label'] + '.json')
        if os.path.exists(p):
            rows.append(song_rows(s, json.load(open(p))))
    rows = [r for r in rows if r['charts'][0]['n_pairs']]
    pooled = {}
    for scope, get in (('primary', lambda r, f: f(r['charts'][0])), ('all_charts', mean_over_charts)):
        P = pooled[scope] = {}
        base = [get(r, lambda c: c.get('agree_ours')) for r in rows]
        P['ours'] = r3(np.mean(base))
        P['n_songs'] = len(rows)
        for v in VARIANTS:
            vals = [get(r, lambda c, v=v: c.get('agree_' + v)) for r in rows]
            P['agree_' + v] = {'mean': r3(np.mean(vals)), 'vs_ours': boot([a - b for a, b in zip(vals, base)]),
                               'songs_up_0.10': sum(a - b >= 0.10 for a, b in zip(vals, base))}
            st = [get(r, lambda c, v=v: c['sub_' + v]['tracker']) for r in rows]
            so = [get(r, lambda c, v=v: c['sub_' + v]['ours']) for r in rows]
            ok = [(a, b) for a, b in zip(st, so) if a is not None and b is not None]
            P['sub_' + v] = {'n_songs': len(ok), 'tracker': r3(np.mean([a for a, _ in ok])) if ok else None,
                             'ours': r3(np.mean([b for _, b in ok])) if ok else None,
                             'diff': boot([a - b for a, b in ok])}
            # re-laning
            R = {}
            for m in ('contour_fast50', 'contour100', 'exact100', 'exact_fast50', 'f1_50'):
                b0 = [get(r, lambda c, m=m: c['today'][m]) for r in rows]
                b1 = [get(r, lambda c, m=m, v=v: c['relane'][v][m]) for r in rows]
                ok = [(a, b) for a, b in zip(b1, b0) if a is not None and b is not None]
                R[m] = {'today': r3(np.mean([b for _, b in ok])), 'relane': r3(np.mean([a for a, _ in ok])),
                        'diff': boot([a - b for a, b in ok]), 'worst_song_diff': r3(min(a - b for a, b in ok))}
            P['relane_' + v] = R
        ce = [r['ceiling_mean'] for r in rows if r['ceiling_mean'] is not None]
        P['ceiling'] = {'mean': r3(np.mean(ce)) if ce else None, 'n_songs': len(ce)}
    json.dump({'rows': rows, 'pooled': pooled, 'settings': {'tol_s': clib.TOL, 'deadband_semitones': DEAD}},
              open(os.path.join(HERE, 'results.json'), 'w'), indent=1)
    # tables
    print('| song | stem | fast onsets (runs) | pairs vs primary | human up/down/same | ours up/down/same | ours | pyin | cqt | hs | pyin conf (n; ours same) | cqt conf (n; ours same) | hs conf (n; ours same) | humans (alt vs primary) | clock 0/+25/+50 ms |')
    print('|' + '---|' * 15)
    for r in rows:
        c = r['charts'][0]
        hd, od = c['human_dir'], c['ours_dir']
        sub = lambda v: f"{c['sub_' + v]['tracker']} ({c['sub_' + v]['n']}; {c['sub_' + v]['ours']})"
        print(f"| {r['label']} | {r['stem']} | {r['n_fast_onsets']} ({r['n_runs']}) | {c['n_pairs']} | {hd['up']}/{hd['down']}/{hd['same']} | "
              f"{od['up']}/{od['down']}/{od['same']} | {c['agree_ours']} | {c['agree_pyin']} | {c['agree_cqt']} | {c['agree_hs']} | "
              f"{sub('pyin_conf')} | {sub('cqt_conf')} | {sub('hs_conf')} | {r['ceiling_mean']} | {r['clock']['0']}/{r['clock']['25']}/{r['clock']['50']} |")
    print()
    for scope, P in pooled.items():
        print(f"**{scope}** n={P['n_songs']}: ours {P['ours']}, humans' ceiling {P['ceiling']}")
        print('| variant | agreement (fallback ours) | minus ours [CI] | songs >= +0.10 | confident subset: tracker / ours (songs) [diff CI] |')
        print('|---|---|---|---|---|')
        for v in VARIANTS:
            a, sb = P['agree_' + v], P['sub_' + v]
            d = a['vs_ours']
            dd = sb['diff'] or {'mean': 0.0, 'lo': 0.0, 'hi': 0.0}
            print(f"| {v} | {a['mean']} | {d['mean']:+.3f} [{d['lo']:+.3f}, {d['hi']:+.3f}] | {a['songs_up_0.10']} | "
                  f"{sb['tracker']} / {sb['ours']} ({sb['n_songs']}) [{dd['mean']:+.3f} [{dd['lo']:+.3f}, {dd['hi']:+.3f}]] |")
        print()
        print('| re-laned by | contour fast 50 ms | contour score.py (100 ms) | exact lanes (100 ms) | exact lanes fast | F1@50 | worst song exact diff |')
        print('|---|---|---|---|---|---|---|')
        for v in VARIANTS:
            R = P['relane_' + v]
            cell = lambda m: f"{R[m]['today']} -> {R[m]['relane']} ({R[m]['diff']['mean']:+.3f} [{R[m]['diff']['lo']:+.3f}, {R[m]['diff']['hi']:+.3f}])"
            print(f"| {v} | {cell('contour_fast50')} | {cell('contour100')} | {cell('exact100')} | {cell('exact_fast50')} | "
                  f"{R['f1_50']['today']} -> {R['f1_50']['relane']} | {R['exact100']['worst_song_diff']} |")
        print()
    print('| song | re-laned by | contour fast 50 | exact 100 | notes moved | (primary chart) |')
    print('|---|---|---|---|---|---|')
    for r in rows:
        c = r['charts'][0]
        for v in VARIANTS:
            x = c['relane'][v]
            print(f"| {r['label']} | {v} | {c['today']['contour_fast50']} -> {x['contour_fast50']} | {c['today']['exact100']} -> {x['exact100']} | {x['n_moved']} | |")
    print()
    print('score.py check (primary, contour / exact, here vs score json):',
          [(r['label'], r['check_scorepy_primary']) for r in rows])


if __name__ == '__main__':
    main()
