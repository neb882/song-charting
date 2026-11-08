"""hopo.py (part 2): reads our v040 Expert guitar charts (23 songs, CPU) and the GPU pm2 chart (aligned by align.json),
and the human charts' Expert guitar notes/states through lib.scan; computes state agreement today and with C1 (a HOPO
chord becomes a strum), the HOPO-chord tables; writes hopo.json (labels only); prints a line per song."""
import sys, json
from collections import Counter
sys.path.insert(0, '<scratch>')
from lib import *

def c1(co):
    return [('strum' if (state(o) == 'hopo' and is_chord(o)) else state(o)) for o in co]
def agree(ro, sts, p):
    return sum(1 for i, j in p if state(ro[i]) == sts[j]) / len(p) if p else None

def chart_stats(ro, co):
    p = pairs(ro, co, H_TOL)
    a0 = agree(ro, [state(o) for o in co], p); a1 = agree(ro, c1(co), p)
    p50 = pairs(ro, co, 0.05); pm = dict((j, i) for i, j in p50)
    cnt = Counter()
    for j, o in enumerate(co):
        if is_chord(o) and state(o) == 'hopo':
            if j not in pm: cnt['unmatched'] += 1
            else:
                h = ro[pm[j]]; cnt[('chord_' if is_chord(h) else 'single_') + state(h)] += 1
    hch = [o for o in ro if is_chord(o)]
    return {'a0': a0, 'a1': a1, 'n_pairs': len(p), 'ours_hopo_chords_in_span': sum(cnt.values()), 'at50': dict(cnt),
            'human_chords': len(hch), 'human_hopo_chords': sum(1 for o in hch if state(o) == 'hopo'),
            'human_tap_chords': sum(1 for o in hch if state(o) == 'tap')}

res = {}
for lab, st, sid in songs():
    e = entry(lab, st, sid)
    osc = scan(e['ours'])
    allo = onsets(osc, 'guitar', 0.0)
    nch = sum(is_chord(o) for o in allo); nhc = sum(is_chord(o) and state(o) == 'hopo' for o in allo)
    ntap_ch = sum(is_chord(o) and state(o) == 'tap' for o in allo)
    r = {'n_ours': len(allo), 'ours_chords': nch, 'ours_hopo_chords': nhc, 'ours_tap_chords': ntap_ch, 'charts': {}}
    for c in e['charts']:
        ro = onsets(scan(c['ref']), 'guitar', c['ref_shift'])
        co = onsets(osc, 'guitar', c['cand_shift'], c['span'])
        r['charts'][c['k']] = chart_stats(ro, co)
    # humans' agreement with the primary (M7-01's exclusion at 0.6)
    pri = e['charts'][0]; rop = onsets(scan(pri['ref']), 'guitar', pri['ref_shift'])
    hag = []
    for h in e['humans']:
        ho = onsets(scan(h['cand']), 'guitar', h['cand_shift'], h['span'])
        if rop and ho:
            hag.append(agree(rop, [state(o) for o in ho], pairs(rop, ho)))
    r['humans_agree'] = float(np.mean(hag)) if hag else None
    ch = list(r['charts'].values())
    r['a0'] = float(np.mean([x['a0'] for x in ch])); r['a1'] = float(np.mean([x['a1'] for x in ch]))
    res[lab] = r
    print(lab, 'ours chords', nch, 'hopo chords', nhc, 'a0 %.3f a1 %.3f d %+.4f' % (r['a0'], r['a1'], r['a1'] - r['a0']), 'humans_agree', None if r['humans_agree'] is None else round(r['humans_agree'], 3), flush=True)

# GPU pm2
al = rj('align.json'); gsc = scan('<shm>/pm2gpu/chart'); e = entry('pm2', 'stress', 'pm2')
g = {'charts': {}}
gall = onsets(gsc, 'guitar', 0.0)
g.update(n_ours=len(gall), ours_chords=sum(is_chord(o) for o in gall), ours_hopo_chords=sum(is_chord(o) and state(o) == 'hopo' for o in gall))
for c in e['charts']:
    ro = onsets(scan(c['ref']), 'guitar', c['ref_shift'])
    co = onsets(gsc, 'guitar', al['lag_s'] * 1000 + c['cand_shift'], c['span'])
    g['charts'][c['k']] = chart_stats(ro, co)
ch = list(g['charts'].values()); g['a0'] = float(np.mean([x['a0'] for x in ch])); g['a1'] = float(np.mean([x['a1'] for x in ch]))
res['pm2_gpu'] = g
print('pm2_gpu chords', g['ours_chords'], 'hopo chords', g['ours_hopo_chords'], 'a0 %.3f a1 %.3f' % (g['a0'], g['a1']))

# pooled over the 23 CPU songs
labs = [l for l in res if l != 'pm2_gpu']
def pool(labs, name):
    d = [res[l]['a1'] - res[l]['a0'] for l in labs]
    out = {'songs': len(labs), 'a0': round(float(np.mean([res[l]['a0'] for l in labs])), 4), 'a1': round(float(np.mean([res[l]['a1'] for l in labs])), 4), 'diff': boot(d),
           'worst_song': min(((l, round(x, 4)) for l, x in zip(labs, d)), key=lambda t: t[1]), 'songs_down': [(l, round(x, 4)) for l, x in zip(labs, d) if x < -1e-9],
           'songs_changed': sum(1 for x in d if abs(x) > 1e-9)}
    return out
keep = [l for l in labs if res[l]['humans_agree'] is None or res[l]['humans_agree'] >= 0.6]
res['_pooled'] = {'all': pool(labs, 'all'), 'agree>=0.6': pool(keep, 'k'), 'left_out': [l for l in labs if l not in keep],
                  'without_refs': pool([l for l in labs if l not in REFS], 'x')}
# the pooled HOPO-chord tables (all charts of the 23 songs, matched at 50 ms)
T = Counter(); hc = hh = 0; ours_hc = ours_ch = 0
for l in labs:
    r = res[l]; ours_hc += r['ours_hopo_chords']; ours_ch += r['ours_chords']
    for x in r['charts'].values():
        T.update(x['at50']); hc += x['human_chords']; hh += x['human_hopo_chords']
res['_pooled']['hopo_chord_table'] = dict(T); res['_pooled']['human_chord_hopo_share'] = round(hh / hc, 4); res['_pooled']['human_chords'] = hc
res['_pooled']['ours_hopo_chords'] = ours_hc; res['_pooled']['ours_chords'] = ours_ch
def rnd(x):
    if isinstance(x, float): return round(x, 4)
    if isinstance(x, dict): return {k: rnd(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)): return [rnd(v) for v in x]
    return x
json.dump(rnd(res), open('hopo.json', 'w'), indent=1)
print(json.dumps(rnd(res['_pooled']), indent=None))
