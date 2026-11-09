"""Held chord shapes (Expert guitar) and drum pads / measure regularity (Expert drums), ours at v0.4.0 against every
human chart of the 23 songs, plus the M7 guitar takes. Measurement only.

Usage: python -I measure.py <a checkout with tools/scan-chart installed> <$DEV> <out.json>
The humans' charts only through the scorer's readers (scan_notes.cjs via score.scan). Labels only in the output.
"""
import bisect
import collections
import json
import os
import sys

sys.path.insert(0, sys.argv[1])
from eval.scorer import score as S  # noqa: E402
import numpy as np  # noqa: E402

DEV = sys.argv[2]
OUT = sys.argv[3]
G = os.path.join(DEV, 'golden')
REFS = ["all_the_small_things", "creep", "drunk_drivers", "kimochi_warui", "lucretia", "take_me_out"]
STRESS = ["break", "pm2", "sooth", "troop"]
SET20 = sorted(s["id"] for s in json.load(open(os.path.join(DEV, 'eval-set20/stress/songs.json'))))[:13]
SONGS = []   # (label, human song folder, our chart folder, kept folder, takes folder)
for s in REFS:
    SONGS.append((s, os.path.join(DEV, 'eval/refs', s), os.path.join(G, 'v040f', s), os.path.join(G, 'work', s),
                  os.path.join(G, 'm7-takes', s)))
for s in STRESS:
    SONGS.append((s, os.path.join(DEV, 'eval/stress', s), os.path.join(G, 'v040f-stress', s),
                  os.path.join(G, 'stress-work', s), os.path.join(G, 'm7-takes', s)))
for i, s in enumerate(SET20, 1):
    SONGS.append(('s%02d' % i, os.path.join(DEV, 'eval-set20/stress', s), os.path.join(G, 'v040-set20', s),
                  os.path.join(G, 'set20-work', s), os.path.join(G, 'm7-takes', s)))
ONLY = os.environ.get('ONLY')
if ONLY:
    SONGS = [x for x in SONGS if x[0] in ONLY.split(',')]
TOL = 0.050


def r3(x):
    return None if x is None else round(float(x), 3)


def human_folders(song_dir):
    """The primary human chart (ref/ beside input.wav) then each alt (alt/<k>/ref beside its own input.wav)."""
    out = [('primary', song_dir)]
    alt = os.path.join(song_dir, 'alt')
    if os.path.isdir(alt):
        for k, d in enumerate(sorted(os.listdir(alt)), 1):
            p = os.path.join(alt, d)
            if os.path.isfile(os.path.join(p, 'input.wav')) and os.path.isdir(os.path.join(p, 'ref')):
                out.append(('alt%d' % k, p))
    return out


def span_of(sc, shift):
    st, en = [], []
    for notes in S.tracks_by_key(sc).values():
        st.append(min(n['ms'] for n in notes))
        en.append(max(n['ms'] + (n.get('msLength') or 0) for n in notes))
    return ((min(st) + shift) / 1000.0, (max(en) + shift) / 1000.0)


def f1_50(ro, co, span):
    rt = np.array([o['t'] for o in ro])
    ct = np.array([o['t'] for o in co])
    pairs = S.match(rt, ct, TOL)
    return S.prf(len(pairs), len(rt), S.n_cand_eff(pairs, ct, span)), pairs


def in_span(co, span):
    lo, hi = span[0] - S.SPAN_MARGIN, span[1] + S.SPAN_MARGIN
    return [o for o in co if lo <= o['t'] <= hi]


# ------------------------------------------------------------------------------------------- part 1: shapes
def shape(o):
    return frozenset(o['lanes'])


def runs(ons):
    out = []
    for o in ons:
        s = shape(o)
        if out and out[-1][0] == s:
            out[-1][1] += 1
            out[-1][3] = o['t']
        else:
            out.append([s, 1, o['t'], o['t']])
    return out


def shape_stats(ons):
    if not ons:
        return None
    rs = runs(ons)
    longest = max(rs, key=lambda r: r[1])
    return {'onsets': len(ons), 'chord_share': r3(sum(len(o['lanes']) > 1 for o in ons) / len(ons)),
            'shape_changes': len(rs) - 1, 'changes_per_onset': r3((len(rs) - 1) / len(ons)),
            'onsets_per_change': r3(len(ons) / max(len(rs) - 1, 1)),
            'chord_onsets_in_runs_16plus': sum(r[1] for r in rs if r[1] >= 16 and len(r[0]) > 1),
            'chord_onsets_in_runs_16plus_share': r3(sum(r[1] for r in rs if r[1] >= 16 and len(r[0]) > 1) / len(ons)),
            'longest_run_onsets': longest[1], 'longest_run_s': r3(longest[3] - longest[2]),
            'longest_run_is_chord': len(longest[0]) > 1}


def change_agreement(ro, co, pairs, chords_only):
    """Consecutive matched pairs, adjacent in both charts: does ours change shape where the human does, and back."""
    hc = oc = both = n = 0
    for (i0, j0), (i1, j1) in zip(pairs, pairs[1:]):
        if i1 != i0 + 1 or j1 != j0 + 1:
            continue
        if chords_only and not all(len(set(o['lanes'])) > 1 for o in (ro[i0], ro[i1], co[j0], co[j1])):
            continue
        h = shape(ro[i0]) != shape(ro[i1])
        c = shape(co[j0]) != shape(co[j1])
        n += 1
        hc += h
        oc += c
        both += h and c
    return {'n_pairs': n, 'human_changes': hc, 'ours_changes': oc, 'both': both,
            'recall': r3(both / hc) if hc else None, 'precision': r3(both / oc) if oc else None}


# ------------------------------------------------------------------------------------------- part 2: drums
PADS = ['kick', 'snare', 'Y-cym', 'B-cym', 'G-cym', 'Y-tom', 'B-tom', 'G-tom']


def pad_name(lane, cym):
    if lane == 0:
        return 'kick'
    if lane == 1:
        return 'snare'
    return '%s-%s' % ('?RYBG'[lane], 'cym' if cym else 'tom')


def pad_list(o):
    return sorted({pad_name(l, c) for l, c in o['pads']}, key=PADS.index)


def pad_confusion(ro, co, pairs):
    """Within each matched onset pair: shared pads on the diagonal; the leftovers paired in pad order, the rest
    against 'none'. Plus a clean cymbal table: pairs where each side has exactly one cymbal."""
    conf = collections.Counter()
    cym = collections.Counter()
    for i, j in pairs:
        a, b = pad_list(ro[i]), pad_list(co[j])
        for p in set(a) & set(b):
            conf[(p, p)] += 1
        la, lb = [p for p in a if p not in b], [p for p in b if p not in a]
        for k in range(max(len(la), len(lb))):
            conf[(la[k] if k < len(la) else 'none', lb[k] if k < len(lb) else 'none')] += 1
        ca, cb = [p for p in a if p.endswith('cym')], [p for p in b if p.endswith('cym')]
        if len(ca) == 1 and len(cb) == 1:
            cym[(ca[0], cb[0])] += 1
    return conf, cym


def ticks_ms_fn(sc):
    res = sc['resolution']
    tempos = sorted(sc.get('tempos') or [], key=lambda x: x['tick'])
    tt = [t['tick'] for t in tempos]

    def f(tick):
        k = max(bisect.bisect_right(tt, tick) - 1, 0)
        tp = tempos[k]
        return tp['msTime'] + (tick - tp['tick']) * 60000.0 / (tp['beatsPerMinute'] * res)
    return f


def measures(sc, last_tick):
    """[(start_tick, length_ticks)] from the chart's time signatures (4/4 from 0 when none), up to last_tick."""
    res = sc['resolution']
    sigs = sorted(sc.get('timeSignatures') or [], key=lambda x: x['tick']) or [{'tick': 0, 'numerator': 4, 'denominator': 4}]
    out = []
    for k, ts in enumerate(sigs):
        step = ts['numerator'] * res * 4.0 / ts['denominator']
        stop = sigs[k + 1]['tick'] if k + 1 < len(sigs) else last_tick + 1
        tick = float(ts['tick'])
        while tick < stop and step > 0:
            out.append((tick, min(step, stop - tick) if k + 1 < len(sigs) else step))
            tick += step
    return out


def patterns(sc, notes):
    """Per measure: frozenset of (pad, position on the 1/48-measure grid); plus measure starts (ticks)."""
    last = max(n['tick'] for n in notes)
    ms = measures(sc, last)
    starts = [m[0] for m in ms]
    pats = [set() for _ in ms]
    for n in notes:
        lane = S.DRUM_LANE.get(n['type'])
        if lane is None:
            continue
        k = bisect.bisect_right(starts, n['tick']) - 1
        st, ln = ms[k]
        pos = int(round((n['tick'] - st) / ln * 48))
        if pos >= 48 and k + 1 < len(ms):
            k, pos = k + 1, 0
            st, ln = ms[k]
        pats[k].add((pad_name(lane, 'cymbal' in n['flags']), pos))
    return ms, [frozenset(p) for p in pats]


def jac(a, b):
    if not a and not b:
        return 1.0
    return len(a & b) / len(a | b)


def regularity(pats):
    rep, js = [], []
    for a, b in zip(pats, pats[1:]):
        if not a and not b:
            continue
        rep.append(a == b)
        js.append(jac(a, b))
    return {'pairs': len(rep), 'exact_repeat_share': r3(np.mean(rep)) if rep else None,
            'mean_jaccard': r3(np.mean(js)) if js else None}


def apply_rule(sc, notes, x):
    """R(x): runs of consecutive measures each at Jaccard >= x with the one before become the run's most common
    pattern (ties to the earliest); new notes' ticks on the measure's 1/48 grid, times from our own tempo map."""
    ms, pats = patterns(sc, notes)
    new = list(pats)
    k = 0
    changed = 0
    while k < len(pats):
        e = k
        while e + 1 < len(pats) and (pats[e + 1] or pats[e]) and jac(pats[e], pats[e + 1]) >= x:
            e += 1
        if e > k:
            cnt = collections.Counter(pats[k:e + 1])
            best = max(cnt.values())
            mode = next(p for p in pats[k:e + 1] if cnt[p] == best)
            for m in range(k, e + 1):
                if pats[m] != mode:
                    new[m] = mode
                    changed += 1
        k = e + 1
    tms = ticks_ms_fn(sc)
    starts = [m[0] for m in ms]
    keep = []
    for n in notes:
        k = bisect.bisect_right(starts, n['tick']) - 1
        if new[k] == pats[k]:
            keep.append(n)
    # measures that changed: regenerate from the grid (rounded positions; a measure whose last note rounded into the
    # next measure is re-read the same way, which is fine for whole-measure replacement)
    lane_type = {0: 'kick', 1: 'redDrum', 2: 'yellowDrum', 3: 'blueDrum', 4: 'greenDrum'}
    rev = {'kick': (0, False), 'snare': (1, False)}
    for L, c in (('Y', 2), ('B', 3), ('G', 4)):
        rev['%s-cym' % L] = (c, True)
        rev['%s-tom' % L] = (c, False)
    keep_set = set(id(n) for n in keep)
    for m in range(len(ms)):
        if new[m] == pats[m]:
            continue
        st, ln = ms[m]
        for pad, pos in new[m]:
            lane, cy = rev[pad]
            tick = st + pos * ln / 48.0
            keep.append({'tick': tick, 'ms': tms(tick), 'type': lane_type[lane], 'flags': ['cymbal'] if cy else [],
                         'length': 0})
    # notes that fell in a changed measure were dropped above (not in keep_set)
    del keep_set
    keep.sort(key=lambda n: n['tick'])
    return keep, [new[m] for m in range(len(ms))], changed, len(ms)


# ------------------------------------------------------------------------------------------- audio / alignment
_dec = {}


def audio(path_or_folder):
    if path_or_folder not in _dec:
        if os.path.isdir(path_or_folder):
            _dec[path_or_folder] = S.load_mix(path_or_folder, S.audio_files(path_or_folder))
        else:
            _dec[path_or_folder] = S.decode(path_or_folder)
    return _dec[path_or_folder]


def alignment(ref_wav, cand_audio):
    a = S.align(audio(ref_wav), audio(cand_audio))
    weak = a['windows_peak_ge_0.3'] < 3 or a['lag_mad_ms'] > 2.0
    return {'lag_ms': a['lag_ms'], 'windows_ge_0.3': a['windows_peak_ge_0.3'], 'of': len(a['windows']),
            'mad_ms': a['lag_mad_ms'], 'weak': weak}


# ------------------------------------------------------------------------------------------- main
res = {}
KEY_G, KEY_D = ('guitar', 'expert'), ('drums', 'expert')
for label, hsong, ours, kept, takes in SONGS:
    print(label, flush=True)
    cand, _ = S.find_chart_folder(ours)
    csc = S.scan(cand)
    ctr = S.tracks_by_key(csc)
    song = {'ours_drum_type': csc.get('drumType'), 'humans': {}}
    # takes: the three seeds and the kept take (guitar only, on the kept folder's decode.wav clock)
    take_dirs = [('seed_%d' % s, os.path.join(takes, 'seed_%d' % s)) for s in (101, 202, 303)]
    take_dirs.append(('kept_20260609', os.path.join(kept, 'guitar', 'seed_20260609')))
    take_sc = {k: S.scan(d) for k, d in take_dirs if os.path.isdir(d)}
    song['takes_intrinsic'] = {k: shape_stats(S.onsets(S.tracks_by_key(t)[KEY_G], S.chart_delay_ms(t)[0], 'guitar'))
                               for k, t in take_sc.items() if KEY_G in S.tracks_by_key(t)}
    if KEY_G in ctr:
        song['ours_guitar_intrinsic'] = shape_stats(S.onsets(ctr[KEY_G], S.chart_delay_ms(csc)[0], 'guitar'))
    if KEY_D in ctr:
        ms_, pats = patterns(csc, ctr[KEY_D])
        song['ours_drums_regularity'] = regularity(pats)
        song['ours_pad_counts'] = dict(collections.Counter(
            pad_name(S.DRUM_LANE[n['type']], 'cymbal' in n['flags']) for n in ctr[KEY_D] if n['type'] in S.DRUM_LANE))
        song['rule'] = {}
        for x in (0.6, 0.7, 0.8):
            nn, npats, ch, nm = apply_rule(csc, ctr[KEY_D], x)
            song['rule'][str(x)] = {'measures_changed': ch, 'measures': nm, 'regularity': regularity(npats),
                                    '_notes': nn, '_npats': npats}
    for hname, hdir in human_folders(hsong):
        rsc = S.scan(os.path.join(hdir, 'ref'))
        rtr = S.tracks_by_key(rsc)
        if not rtr:
            continue
        wav = os.path.join(hdir, 'input.wav')
        al = alignment(wav, cand)
        ref_shift = S.chart_delay_ms(rsc)[0]
        cand_shift = S.chart_delay_ms(csc)[0] - al['lag_ms']
        span = span_of(rsc, ref_shift)
        h = {'alignment': al, 'drum_type': rsc.get('drumType')}
        if KEY_G in rtr:
            ro = S.onsets(rtr[KEY_G], ref_shift, 'guitar')
            h['guitar'] = {'human': shape_stats(ro)}
            if KEY_G in ctr:
                co = in_span(S.onsets(ctr[KEY_G], cand_shift, 'guitar'), span)
                p, pairs = f1_50(ro, co, span)
                h['guitar']['ours_in_span'] = shape_stats(co)
                h['guitar']['f1_50'] = p['f1']
                h['guitar']['agree_all'] = change_agreement(ro, co, pairs, False)
                h['guitar']['agree_chords'] = change_agreement(ro, co, pairs, True)
            # takes against this human chart (decode.wav clock, aligned once per human chart)
            dec = os.path.join(kept, 'decode.wav')
            if take_sc and os.path.isfile(dec):
                alt_ = alignment(wav, dec)
                h['takes_alignment'] = alt_
                h['takes'] = {}
                for k, t in take_sc.items():
                    tt = S.tracks_by_key(t)
                    if KEY_G not in tt:
                        continue
                    to = in_span(S.onsets(tt[KEY_G], S.chart_delay_ms(t)[0] - alt_['lag_ms'], 'guitar'), span)
                    p, pairs = f1_50(ro, to, span)
                    h['takes'][k] = {'f1_50': p['f1'], 'agree_all': change_agreement(ro, to, pairs, False),
                                     'agree_chords': change_agreement(ro, to, pairs, True)}
        if KEY_D in rtr:
            ro = S.onsets(rtr[KEY_D], ref_shift, 'drums')
            _, hp = patterns(rsc, rtr[KEY_D])
            d = {'human_pad_counts': dict(collections.Counter(
                     pad_name(S.DRUM_LANE[n['type']], 'cymbal' in n['flags']) for n in rtr[KEY_D] if n['type'] in S.DRUM_LANE)),
                 'human_regularity': regularity(hp)}
            if KEY_D in ctr:
                co = in_span(S.onsets(ctr[KEY_D], cand_shift, 'drums'), span)
                p, pairs = f1_50(ro, co, span)
                d['f1_50'] = p['f1']
                d['ours_pad_counts_in_span'] = dict(collections.Counter(p_ for o in co for p_ in pad_list(o)))
                d['human_pad_onsets'] = dict(collections.Counter(p_ for o in ro for p_ in pad_list(o)))
                conf, cym = pad_confusion(ro, co, pairs)
                d['confusion'] = {'%s>%s' % k: v for k, v in sorted(conf.items())}
                d['cymbal_confusion'] = {'%s>%s' % k: v for k, v in sorted(cym.items())}
                # human exact repeats: does ours repeat at the same time? (measures matched by midpoint time)
                hms, _ = patterns(rsc, rtr[KEY_D])
                htms = ticks_ms_fn(rsc)
                ctms = ticks_ms_fn(csc)
                cms, cp = patterns(csc, ctr[KEY_D])
                cst = [(ctms(m[0]) + cand_shift) / 1000.0 for m in cms]

                def ours_rep_at(t, cpats):
                    k = bisect.bisect_right(cst, t) - 1
                    if k < 1 or k >= len(cpats):
                        return None
                    return cpats[k] == cpats[k - 1] and bool(cpats[k])
                hrep, rule_hrep = [], {x: [] for x in song['rule']}
                for m in range(1, len(hp)):
                    if hp[m] and hp[m] == hp[m - 1]:
                        tmid = (htms(hms[m][0] + hms[m][1] / 2) + ref_shift) / 1000.0
                        v = ours_rep_at(tmid, cp)
                        if v is not None:
                            hrep.append(v)
                        for x in song['rule']:
                            v2 = ours_rep_at(tmid, song['rule'][x]['_npats'])
                            if v2 is not None:
                                rule_hrep[x].append(v2)
                d['ours_repeats_where_human_repeats'] = {'n': len(hrep), 'share': r3(np.mean(hrep)) if hrep else None}
                d['rule'] = {}
                for x, r in song['rule'].items():
                    rco = in_span(S.onsets(r['_notes'], cand_shift, 'drums'), span)
                    rp, _ = f1_50(ro, rco, span)
                    d['rule'][x] = {'f1_50': rp['f1'], 'ours_repeats_where_human_repeats':
                                    r3(np.mean(rule_hrep[x])) if rule_hrep[x] else None}
            h['drums'] = d
        song['humans'][hname] = h
    for r in song.get('rule', {}).values():
        r.pop('_notes', None)
        r.pop('_npats', None)
    res[label] = song
json.dump(res, open(OUT, 'w'), indent=1)
