"""analyze.py: part A's numbers (A-a states, A-b taps, A-c sustains, A-d repeats). Reads the arms' kept builds
(<shm>/m7-Akeep/<arm>/<set>), the human charts their scores point to and (A-d b) the kept guitar stems; writes
../A.json (per song, chart and arm; labels only) and prints a few progress lines, no names."""
import json, sys, glob, os
from pathlib import Path
import numpy as np
import alib
from alib import onsets, pairs, f1, state, mean, boot, scan

ARMS = [a for a in ('base', 'A1', 'A2', 'A3') if all((alib.KEEP / a / s / 'DONE').exists() for s in ('refs', 'stress', 'set20'))]
SETS = tuple(os.environ.get('A_SETS', 'refs,stress,set20').split(','))
if os.environ.get('A_TEST'):   # a test on the earlier runs laid out as arm 'prior' (mkprior.sh), as the base arm
    ARMS = ['base']
CAP = {'base': None, 'A1': 300.0, 'A2': 400.0, 'A3': 500.0}
OUT = Path(__file__).resolve().parent.parent / os.environ.get('A_OUT', 'A.json')
GAPS, PCTS = (150, 200, 250), (25, 50)
H_TOL = 0.100


def floor_ms(beat_ms, arm):
    c = CAP[arm]
    return max(200.0, 0.75 * beat_ms if c is None else min(0.75 * beat_ms, c))


def align_arms(cos):
    """The arms' onset lists, index-aligned to base's (by time within 1 ms); counts mismatches."""
    base = cos['base']
    out, bad = {'base': base}, 0
    bt = np.array([o['t'] for o in base])
    for a, co in cos.items():
        if a == 'base':
            continue
        if len(co) == len(base) and np.allclose([o['t'] for o in co], bt, atol=1e-3):
            out[a] = co
            continue
        m = {}
        for o in co:
            k = int(np.argmin(np.abs(bt - o['t'])))
            if abs(bt[k] - o['t']) < 1e-3:
                m[k] = o
        bad += len(base) - len(m)
        out[a] = [m.get(i, base[i]) for i in range(len(base))]
    return out, bad


def is_single(o):
    return len(o['lanes']) == 1


def repeats(co):
    """Indices of single notes whose previous onset is the same single note."""
    return [i for i in range(1, len(co)) if is_single(co[i]) and is_single(co[i - 1]) and co[i]['lanes'] == co[i - 1]['lanes']]


def rshare(co):
    return round(len(repeats(co)) / len(co), 4) if co else None


def stem_strength(work):
    import librosa
    c = sorted(glob.glob(os.path.join(work, 'stems', '*', 'guitar.wav')), key=os.path.getmtime)
    if not c:
        return None
    y, sr = librosa.load(c[-1], sr=22050, mono=True)
    env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=512)
    return env, sr / 512.0


def env_at(env, fps, t):
    """The envelope's peak over [t, t + 60 ms]: the stem's onset strength peaks 25-50 ms after our onsets (the clock
    check in A.json)."""
    a, b = int(round(t * fps)), int(round((t + 0.06) * fps))
    a, b = max(0, min(len(env) - 1, a)), max(0, min(len(env) - 1, b))
    return float(env[a:b + 1].max())


def tapstates(co, rule):
    out = []
    for i, o in enumerate(co):
        s = state(o)
        if s == 'tap' and rule == 'T1':
            s = 'hopo'
        out.append(s)
    if rule == 'T2':
        t = np.array([o['t'] for o in co])
        n = len(t)
        keep = np.zeros(n, bool)
        i = 0
        while i < n:      # runs of onsets at most 1/8 s apart (8 a second or more)
            j = i
            while j + 1 < n and t[j + 1] - t[j] <= 0.125 + 1e-9:
                j += 1
            if j - i + 1 >= 8:
                keep[i:j + 1] = True
            i = j + 1
        out = [('hopo' if (s == 'tap' and not keep[k]) else s) for k, s in enumerate(out)]
    return out


def fast_runs(co, per_s=8, min_n=8):
    """A boolean per onset: inside a run of at least min_n onsets at most 1/per_s s apart."""
    t = np.array([o['t'] for o in co])
    n, keep, i = len(t), np.zeros(len(t), bool), 0
    while i < n:
        j = i
        while j + 1 < n and t[j + 1] - t[j] <= 1.0 / per_s + 1e-9:
            j += 1
        if j - i + 1 >= min_n:
            keep[i:j + 1] = True
        i = j + 1
    return keep


def ae_stats(ons, sts=None):
    """A-e on one chart's onsets: open share, longest open run, taps on same-fret repeats, repeats in fast runs."""
    sts = sts or [state(o) for o in ons]
    op = [(-1 in o['lanes']) for o in ons]
    run = best = 0
    for x in op:
        run = run + 1 if x else 0
        best = max(best, run)
    rep = set(repeats(ons))
    taps = [k for k, s in enumerate(sts) if s == 'tap']
    fr = fast_runs(ons)
    nf = int(fr.sum())
    return {'open_share': round(sum(op) / len(ons), 4) if ons else None, 'n_open': int(sum(op)), 'open_longest_run': best,
            'n_taps': len(taps), 'taps_on_repeat': sum(1 for k in taps if k in rep),
            'tap_repeat_share': round(sum(1 for k in taps if k in rep) / len(taps), 4) if taps else None,
            'n_fast': nf, 'fast_repeat_share': round(sum(1 for k in rep if fr[k]) / nf, 4) if nf else None,
            'repeat_share': round(len(rep) / len(ons), 4) if ons else None}


def lanes_m(ro, co, span):
    m = alib.S.track_metrics(ro, co, 'guitar', span, False, False)
    return m['exact_lane_agreement']['value'], m['lane_direction_agreement']['value']


def agree(ro, sts, p):
    return round(sum(1 for i, j in p if state(ro[i]) == sts[j]) / len(p), 4) if p else None


def held(o):
    return o['len_ticks'] > 0


def sus_agree(ro, co, p):
    return round(sum(1 for i, j in p if held(ro[i]) == held(co[j])) / len(p), 4) if p else None


def song_rows(s, arms_dirs):
    cand = {a: scan(os.path.join(d, 'songs', s['label'])) for a, d in arms_dirs.items()}
    row = {'label': s['label'], 'set': s['set'], 'octave': s['octave'], 'bpm': s['bpm'],
           'n_charts': len(s['charts']), 'parts': {}}
    for part in ('guitar', 'bass'):
        P = {'charts': {}, 'humans': {}}
        for c in s['charts']:
            ro = onsets(scan(c['ref']), part, c['ref_shift'])
            if not ro:
                continue
            cos, bad = align_arms({a: onsets(cand[a], part, c['cand_shift'], c['span']) or [] for a in arms_dirs})
            co = cos['base']
            p = pairs(ro, co, H_TOL)
            rsc = scan(c['ref'])
            R = {'n_human': len(ro), 'n_ours': len(co), 'n_matched100': len(p), 'arm_onset_mismatch': bad}
            sts = {a: [state(o) for o in cos[a]] for a in cos}
            # A-a
            for a in sts:
                R[f'state_{a}'] = agree(ro, sts[a], p)
            if 'A1' in sts and part == 'guitar':
                R['state_R1'] = R['state_A1'] if (s['octave'] or 1) != 1 else R['state_base']
            if 'A2' in sts:
                r2 = [('hopo' if (sb == 'strum' and sn == 'hopo') else sb) for sb, sn in zip(sts['base'], sts['A2'])]
                R['state_R2'] = agree(ro, r2, p)
                R['r2_changed'] = sum(1 for x, y in zip(r2, sts['base']) if x != y)
            if 'A1' in sts and 'A2' in sts:
                cls = {}
                for i, j in p:
                    a1, a2 = sts['A1'][j], sts['A2'][j]
                    k = 'forced_strum' if (a1, a2) == ('strum', 'hopo') else 'forced_hopo' if (a1, a2) == ('hopo', 'strum') \
                        else 'tap' if 'tap' in (a1, a2) else 'unforced'
                    d = cls.setdefault(k, {'n': 0, 'human_strum': 0, 'human_hopo': 0, 'human_tap': 0})
                    d['n'] += 1
                    d['human_' + state(ro[i])] += 1
                R['by_engine_flag'] = cls
            R['hopo_share_ours'] = {a: round(sum(1 for x in sts[a] if x == 'hopo') / len(co), 4) if co else None for a in sts}
            R['hopo_share_human'] = round(sum(1 for o in ro if state(o) == 'hopo') / len(ro), 4)
            # A-b (base)
            R['tap_share_ours'] = round(sum(1 for x in sts['base'] if x == 'tap') / len(co), 4) if co else None
            R['tap_share_human'] = round(sum(1 for o in ro if state(o) == 'tap') / len(ro), 4)
            ours_tap = [j for j in range(len(co)) if sts['base'][j] == 'tap']
            hum_tap = [i for i in range(len(ro)) if state(ro[i]) == 'tap']
            pm = dict((j, i) for i, j in p)
            pi = dict(p)
            R['tap_n_ours'], R['tap_n_human'] = len(ours_tap), len(hum_tap)
            R['tap_precision'] = round(sum(1 for j in ours_tap if j in pm and state(ro[pm[j]]) == 'tap') / len(ours_tap), 4) if ours_tap else None
            R['tap_recall'] = round(sum(1 for i in hum_tap if i in pi and sts['base'][pi[i]] == 'tap') / len(hum_tap), 4) if hum_tap else None
            for T in ('T0', 'T1', 'T2'):
                R[f'state_{T}'] = agree(ro, tapstates(co, T), p)
            # A-c
            for a in cos:
                R[f'sus_share_{a}'] = round(sum(1 for o in cos[a] if held(o)) / len(co), 4) if co else None
                R[f'sus_agree_{a}'] = sus_agree(ro, cos[a], p)
            R['sus_share_human'] = round(sum(1 for o in ro if held(o)) / len(ro), 4)
            hs = [o for o in ro if held(o)]
            res = rsc['resolution']
            L = {'slow': [], 'fast': []}
            drop = {a: 0 for a in CAP}
            for o in hs:
                hb = alib.bpm_at(rsc, o['t'] * 1000 - c['ref_shift'])
                L['slow' if hb < 100 else 'fast'].append((o['len_ms'], o['len_ticks'] / res))
                ob = alib.bpm_at(cand['base'], o['t'] * 1000 - c['cand_shift'])
                for a in CAP:
                    drop[a] += o['len_ms'] < floor_ms(60000.0 / ob, a) - 1e-6
            R['human_sus_len'] = {k: ({'n': len(v), 'ms_p50': round(float(np.median([x[0] for x in v])), 1),
                                       'ms_p10': round(float(np.percentile([x[0] for x in v], 10)), 1),
                                       'beats_p50': round(float(np.median([x[1] for x in v])), 3),
                                       'beats_p10': round(float(np.percentile([x[1] for x in v], 10)), 3)} if v else {'n': 0})
                                  for k, v in L.items()}
            R['human_sus_dropped_share'] = {a: round(drop[a] / len(hs), 4) if hs else None for a in CAP}
            if part == 'guitar':   # A-e (base; the HOPO chords per arm)
                ch = [j for j, o in enumerate(co) if len(set(o['lanes'])) > 1]
                R['n_chords'] = len(ch)
                R['hopo_chord_share'] = {a: round(sum(1 for j in ch if sts[a][j] == 'hopo') / len(ch), 4) if ch else None for a in sts}
                hc = [o for o in ro if len(set(o['lanes'])) > 1]
                R['hopo_chord_share_human'] = round(sum(1 for o in hc if state(o) == 'hopo') / len(hc), 4) if hc else None
                R['ae_ours'], R['ae_human'] = ae_stats(co, sts['base']), ae_stats(ro)
                g = [dict(o, lanes=[0 if l == -1 else l for l in o['lanes']]) for o in co]
                R['lane_exact_base'], R['lane_contour_base'] = lanes_m(ro, co, c['span'])
                R['lane_exact_open2green'], R['lane_contour_open2green'] = lanes_m(ro, g, c['span'])
                # T3: no tap on a same-fret repeat (it becomes a strum: the natural rule never HOPOs a repeat)
                rp = set(repeats(co))
                R['state_T3'] = agree(ro, [('strum' if (s == 'tap' and k in rp) else s) for k, s in enumerate(sts['base'])], p)
            R['_ro'], R['_co'], R['_span'] = ro, co, c['span']
            P['charts'][c['k']] = R
        for h in s['humans']:
            ro = onsets(scan(h['ref']), part, h['ref_shift'])
            ho = onsets(scan(h['cand_dir']), part, h['cand_shift'], h['span'])
            if not ro or not ho:
                continue
            p = pairs(ro, ho, H_TOL)
            hst = [state(o) for o in ho]
            P['humans'][h['k']] = {'state': agree(ro, hst, p), 'sus_agree': sus_agree(ro, ho, p), 'ae': ae_stats(ho) if part == 'guitar' else None,
                                   'f1_50': f1(ro, ho, 0.05, h['span'])}
        if P['charts']:
            row['parts'][part] = P
    if 'guitar' in row['parts']:
        row['repeats'] = repeat_rules(s, row['parts']['guitar']['charts'])
    for part in row['parts'].values():
        for R in part['charts'].values():
            for k in ('_ro', '_co', '_span'):
                R.pop(k, None)
    return row


def repeat_rules(s, charts):
    ks = list(charts)
    co = charts[ks[0]]['_co']   # our onsets are the same for every chart up to the chart's shift: use each its own
    out = {'repeat_share_ours': rshare(co), 'repeat_share_human': {k: rshare(charts[k]['_ro']) for k in ks}}
    # matched at 50 ms against any human chart (on each chart's own shift; our onsets in index order are the same list
    # up to the span filter, so they are keyed by our chart tick)
    any_match, near50, in_sus = {}, {}, {}
    for k in ks:
        ro, cok = charts[k]['_ro'], charts[k]['_co']
        rt = np.array([o['t'] for o in ro])
        for i, j in pairs(ro, cok, 0.05):
            any_match[cok[j]['tick']] = True
        for o in cok:
            if len(rt) and np.min(np.abs(rt - o['t'])) <= 0.05 + 1e-9:
                near50[o['tick']] = True
            if any(r['len_ms'] > 0 and r['t'] < o['t'] < r['t'] + r['len_ms'] / 1000.0 for r in ro if abs(r['t'] - o['t']) < 30):
                in_sus[o['tick']] = True
    rep = repeats(co)
    reps = set(rep)
    out['n_ours'] = len(co)
    out['n_repeats'] = len(rep)
    out['match50_repeats'] = round(sum(1 for i in rep if any_match.get(co[i]['tick'])) / len(rep), 4) if rep else None
    oth = [i for i in range(len(co)) if i not in reps]
    out['match50_other'] = round(sum(1 for i in oth if any_match.get(co[i]['tick'])) / len(oth), 4) if oth else None
    un = [i for i in rep if not any_match.get(co[i]['tick'])]
    gaps = [1000 * (co[i]['t'] - co[i - 1]['t']) for i in un]
    out['unmatched_repeats'] = {'n': len(un), 'in_human_sustain': sum(1 for i in un if in_sus.get(co[i]['tick'])),
                                'gap_ms': ({q: round(float(np.percentile(gaps, q)), 1) for q in (10, 25, 50, 75, 90)} if gaps else None)}
    st = stem_strength(s['work'])
    if st is not None:
        env, fps = st
        val = {i: env_at(env, fps, co[i]['t']) for i in range(len(co))}
        allv = np.array(list(val.values()))
        # the stem's clock: mean strength at our onsets, shifted
        out['stem_clock_check'] = {str(d): round(float(np.mean([env_at(env, fps, o['t'] + d / 1000) for o in co])), 3)
                                   for d in (-100, -50, -25, 0, 25, 50, 100)}
    f1_before = {k: f1(charts[k]['_ro'], charts[k]['_co'], 0.05, charts[k]['_span']) for k in ks}
    out['f1_50_before'] = mean(f1_before.values())
    cands = {}
    for G in GAPS:
        cands[f'gap{G}'] = [i for i in rep if 1000 * (co[i]['t'] - co[i - 1]['t']) >= G - 1e-6]
        if st is not None:
            for pc in PCTS:
                thr = float(np.percentile(allv, pc))
                cands[f'gap{G}_stem_p{pc}'] = [i for i in cands[f'gap{G}'] if val[i] < thr]
    R = {}
    for name, rem in cands.items():
        rt = {co[i]['tick'] for i in rem}
        after = {}
        for k in ks:
            cok = [o for o in charts[k]['_co'] if o['tick'] not in rt]
            after[k] = f1(charts[k]['_ro'], cok, 0.05, charts[k]['_span'])
        rest = [o for o in co if o['tick'] not in rt]
        R[name] = {'removed': len(rem), 'precision': round(sum(1 for i in rem if not near50.get(co[i]['tick'])) / len(rem), 4) if rem else None,
                   'f1_50_change': round(mean(after.values()) - out['f1_50_before'], 4),
                   'repeat_share_after': rshare(rest)}
    out['rules'] = R
    return out


def main():
    if 'base' not in ARMS:
        sys.exit('the base arm is not built yet')
    res = {'arms': ARMS, 'songs': []}
    for st in SETS:
        dirs = {a: str(alib.KEEP / (os.environ.get('A_TEST') or a) / st) for a in ARMS}
        for s in alib.songs(dirs['base'], st):
            res['songs'].append(song_rows(s, dirs))
            print('done', s['label'], flush=True)
    OUT.write_text(json.dumps(res, indent=1))
    print('wrote', OUT)


if __name__ == '__main__':
    main()
