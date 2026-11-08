"""M7-01 part B shared loader. Reads: the run folders' summary.json/score JSONs (lags, delays), our charts and the
human charts through eval/scorer/score.py's scan (notes, tempo map, solos only), the kept folders' stems and
report.json. Prints nothing; caches numbers per song (labels only, no titles) in <shm>/m7/B/cache."""
import json, os, sys
from pathlib import Path
import numpy as np
REPO = Path('<wt>/orch')
sys.path[:0] = [str(REPO), str(REPO / 'eval' / 'scorer')]
import score as S  # noqa
G = Path('$DEV/golden'); DEV = Path('$DEV')
CACHE = Path('<shm>/m7/B/cache')
PARTS = ('guitar', 'bass', 'drums')
REFS = ['all_the_small_things', 'creep', 'drunk_drivers', 'kimochi_warui', 'lucretia', 'take_me_out']
STRESS = ['troop', 'sooth', 'break', 'pm2']


def rj(p):
    return json.loads(Path(p).read_text())


def songs():
    """[(label, set, private_id)] for the 23 songs; private ids are never written out."""
    out = [(i, 'refs', i) for i in REFS] + [(i, 'stress', i) for i in STRESS]
    s20 = sorted(rj(G / 'set20-main/summary.json')['songs'])
    out += [('s%02d' % (k + 1), 'set20', sid) for k, sid in enumerate(s20)]
    return out


def paths(st, sid):
    if st == 'refs':
        return dict(refdir=DEV / 'eval/refs' / sid, run=G / 'v031', score=G / 'v031/scores' / f'{sid}.score.json',
                    kept=G / 'work' / sid, alts=[], human=None)
    if st == 'stress':
        refs = DEV / 'eval/stress'
        song = next(s for s in rj(refs / 'songs.json') if s['id'] == sid)
        alts = [(f'alt{k}', refs / sid / 'alt' / a['md5']) for k, a in enumerate(song.get('alts') or [], 1)]
        return dict(refdir=refs / sid, run=G / 'gate3-final-stress', score=G / 'gate3-final-stress/scores' / f'{sid}.score.json',
                    kept=G / 'stress-work' / sid, alts=alts, human=G / 'gate3-new-stress/stress_scores')
    refs = DEV / 'eval-set20/stress'
    song = next(s for s in rj(refs / 'songs.json') if s['id'] == sid)
    alts = [(f'alt{k}', refs / sid / 'alt' / a['md5']) for k, a in enumerate(song.get('alts') or [], 1)]
    return dict(refdir=refs / sid, run=G / 'set20-main', score=G / 'set20-main/stress_scores' / f'{sid}.ours.primary.json',
                kept=G / 'set20-work' / sid, alts=alts, human=G / 'set20-main/stress_scores')


def chart_rec(sc, shift_ms):
    tr = S.tracks_by_key(sc)
    ph = S.phrases_by_key(sc)
    rec = {'shift_ms': shift_ms, 'parts': {}, 'res': sc.get('resolution'), 'tempos': sc.get('tempos'),
           'timeSignatures': sc.get('timeSignatures')}
    for p in PARTS:
        k = (p, 'expert')
        if k not in tr:
            continue
        ons = S.onsets(tr[k], shift_ms, p)
        lens = {}
        for n in tr[k]:
            lens[n['tick']] = max(lens.get(n['tick'], 0), n.get('msLength') or 0)
        rows = []
        g = {}
        for n in tr[k]:
            g.setdefault(n['tick'], []).append(n)
        for o in ons:
            pass
        ticks = sorted(g, key=lambda t: g[t][0]['ms'])
        for tk in ticks:
            ns = g[tk]
            lm = S.DRUM_LANE if p == 'drums' else S.GUITAR_LANE
            lanes = sorted({lm[n['type']] for n in ns if n['type'] in lm})
            if not lanes:
                continue
            fl = sorted(set().union(*[set(n['flags']) for n in ns]))
            rows.append([round((ns[0]['ms'] + shift_ms) / 1000, 4), lanes, fl, round(lens[tk] / 1000, 4), tk])
        rows.sort(key=lambda r: r[0])
        sol = [[round((x['ms'] + shift_ms) / 1000, 4), round((x['ms'] + x['msLength'] + shift_ms) / 1000, 4),
                x['tick'], x['length']] for x in (ph.get(k) or {}).get('solos', [])]
        rec['parts'][p] = {'onsets': rows, 'solos': sol}
    return rec


def build(label, st, sid):
    out = CACHE / f'{label}.json'
    if out.exists():
        return rj(out)
    P = paths(st, sid)
    osc = rj(P['score'])
    al = osc['alignment']
    rec = {'label': label, 'set': st, 'span': osc['ref_span_s'], 'humans': {}}
    rsc = S.scan(str(P['refdir'] / 'ref'))
    rec['humans']['primary'] = chart_rec(rsc, al['ref_delay_ms'])
    for lab, af in P['alts']:
        hj = P['human'] / f'{sid}.human.{lab}.json'
        if not hj.exists():
            continue
        h = rj(hj)
        rec['humans'][lab] = chart_rec(S.scan(str(af / 'ref')), h['alignment']['cand_total_shift_ms'])
        rec['humans'][lab]['lag_ms'] = h['alignment']['lag_ms']
    summ = rj(P['run'] / 'summary.json')['songs'][sid]
    folder = P['run'] / summ['folder']
    rec['ours'] = chart_rec(S.scan(str(folder)), al['cand_total_shift_ms'])
    out.write_text(json.dumps(rec))
    return rec


def report(st, sid):
    P = paths(st, sid)
    return rj(P['run'] / rj(P['run'] / 'summary.json')['songs'][sid]['folder'] / 'report.json')


def stems(st, sid):
    return S_kept(paths(st, sid)['kept'])


def S_kept(kept):
    for d in sorted((kept / 'stems').glob('*/')):
        if (d / 'info.json').is_file():
            return {p.stem: p for p in sorted(d.glob('*.wav'))}
    return {}


def levels(st, sid, names=None):
    """assemble.frame_levels of each kept stem (LEVEL_FRAME_S), cached as .npy in /dev/shm."""
    from songcharter import assemble as AS, audio as A
    out = {}
    for name, p in stems(st, sid).items():
        if names and name not in names:
            continue
        import hashlib; c = CACHE / ('lv-' + hashlib.sha1(str(p).encode()).hexdigest()[:10] + f'-{name}.npy')
        if c.exists():
            out[name] = np.load(c)
            continue
        y, sr = A.read_wav(p)
        lv = AS.frame_levels(y, sr)
        np.save(c, lv)
        out[name] = lv
    return out


if __name__ == '__main__':
    for lab, st, sid in songs():
        r = build(lab, st, sid)
        print(lab, len(r['humans']), {p: len(v['onsets']) for p, v in r['ours']['parts'].items()}, flush=True)
