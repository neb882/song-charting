"""Tables from results.json (measure.py): per song, then pooled with each song weighted once.
Human charts: intrinsic numbers over every human chart of the song; matched numbers (F1, agreement, confusion, the
rule) over the human charts whose alignment is not weak (score.py's warnings: < 3 of 9 windows at ncc >= 0.3, or MAD
> 2 ms). Usage: python -I tables.py results.json summary.json > tables.txt
"""
import collections
import json
import sys

import numpy as np

R = json.load(open(sys.argv[1]))
OUT = {}


def m(xs):
    xs = [x for x in xs if x is not None]
    return round(float(np.mean(xs)), 3) if xs else None


def good(song):
    return {k: h for k, h in song['humans'].items() if not h['alignment']['weak']}


print('== alignment (weak = score.py warns) ==')
weak = {}
for lab, s in R.items():
    w = [k for k, h in s['humans'].items() if h['alignment']['weak']]
    tw = [k for k, h in s['humans'].items() if h.get('takes_alignment', {}).get('weak')]
    weak[lab] = {'human_charts': len(s['humans']), 'weak': w, 'takes_weak': tw}
    if w or tw:
        print(lab, 'charts', len(s['humans']), 'weak:', w, 'takes-clock weak:', tw)
OUT['alignment'] = weak

print('\n== part 1: shapes, Expert guitar ==')
print('%-22s %5s %5s | %6s %6s | %5s %5s | %5s %5s | %6s %6s | %5s %5s | %5s %5s %5s' % (
    'song', 'nH', 'nOk', 'onsH', 'onsO', 'chH', 'chO', 'cpoH', 'cpoO', 'r16H', 'r16O', 'lngH', 'lngO', 'f1', 'rec', 'prec'))
P1 = {}
for lab, s in R.items():
    hs = [h['guitar'] for h in s['humans'].values() if 'guitar' in h]
    gs = [h['guitar'] for h in good(s).values() if 'guitar' in h and 'f1_50' in h['guitar']]
    o = s.get('ours_guitar_intrinsic')
    if not hs or not o:
        continue
    row = {'n_human': len(hs), 'n_aligned': len(gs),
           'human_onsets': m([h['human']['onsets'] for h in hs]), 'ours_onsets': o['onsets'],
           'human_chord_share': m([h['human']['chord_share'] for h in hs]), 'ours_chord_share': o['chord_share'],
           'human_changes_per_onset': m([h['human']['changes_per_onset'] for h in hs]),
           'ours_changes_per_onset': o['changes_per_onset'],
           'human_onsets_per_change': m([h['human']['onsets_per_change'] for h in hs]),
           'ours_onsets_per_change': o['onsets_per_change'],
           'human_runs16_share': m([h['human']['chord_onsets_in_runs_16plus_share'] for h in hs]),
           'ours_runs16_share': o['chord_onsets_in_runs_16plus_share'],
           'human_runs16_onsets': m([h['human']['chord_onsets_in_runs_16plus'] for h in hs]),
           'ours_runs16_onsets': o['chord_onsets_in_runs_16plus'],
           'human_longest': m([h['human']['longest_run_onsets'] for h in hs]),
           'human_longest_s': m([h['human']['longest_run_s'] for h in hs]),
           'ours_longest': o['longest_run_onsets'], 'ours_longest_s': o['longest_run_s'],
           'f1_50': m([g['f1_50'] for g in gs]),
           'recall': m([g['agree_all']['recall'] for g in gs]), 'precision': m([g['agree_all']['precision'] for g in gs]),
           'chords_recall': m([g['agree_chords']['recall'] for g in gs]),
           'chords_precision': m([g['agree_chords']['precision'] for g in gs]),
           'chords_pairs': m([g['agree_chords']['n_pairs'] for g in gs]),
           'human_change_rate_on_pairs': m([g['agree_all']['human_changes'] / g['agree_all']['n_pairs']
                                            for g in gs if g['agree_all']['n_pairs']]),
           'ours_change_rate_on_pairs': m([g['agree_all']['ours_changes'] / g['agree_all']['n_pairs']
                                           for g in gs if g['agree_all']['n_pairs']])}
    P1[lab] = row
    print('%-22s %5d %5d | %6.0f %6d | %5.3f %5.3f | %5.3f %5.3f | %6.3f %6.3f | %5.0f %5d | %5s %5s %5s' % (
        lab, row['n_human'], row['n_aligned'], row['human_onsets'], row['ours_onsets'], row['human_chord_share'],
        row['ours_chord_share'], row['human_changes_per_onset'], row['ours_changes_per_onset'], row['human_runs16_share'],
        row['ours_runs16_share'], row['human_longest'], row['ours_longest'], row['f1_50'], row['recall'], row['precision']))
pool1 = {k: m([r[k] for r in P1.values()]) for k in next(iter(P1.values())) if k not in ('n_human', 'n_aligned')}
pool1['songs'] = len(P1)
pool1['songs_ours_moves_less'] = sum(r['ours_changes_per_onset'] < r['human_changes_per_onset'] for r in P1.values())
pool1['songs_ours_runs16_share_higher'] = sum(r['ours_runs16_share'] > r['human_runs16_share'] for r in P1.values())
pool1['songs_ours_runs16_share_higher_by_0.1'] = sum(r['ours_runs16_share'] > r['human_runs16_share'] + 0.1 for r in P1.values())
print('pooled', json.dumps(pool1))
OUT['part1'] = {'per_song': P1, 'pooled': pool1}

print('\n== part 1: the four M7 takes (raw engine output) ==')
TK = {}
for lab, s in R.items():
    ti = s.get('takes_intrinsic') or {}
    if len(ti) < 2:
        continue
    gs = [h for h in good(s).values() if 'takes' in h and not h['takes_alignment']['weak']]
    row = {}
    for k, t in ti.items():
        row[k] = {'onsets': t['onsets'], 'chord_share': t['chord_share'], 'changes_per_onset': t['changes_per_onset'],
                  'runs16_share': t['chord_onsets_in_runs_16plus_share'], 'longest': t['longest_run_onsets'],
                  'f1_50': m([h['takes'][k]['f1_50'] for h in gs if k in h['takes']]),
                  'recall': m([h['takes'][k]['agree_all']['recall'] for h in gs if k in h['takes']])}
    cpo = [v['changes_per_onset'] for v in row.values()]
    hum = P1.get(lab, {}).get('human_changes_per_onset')
    best_move = max(row, key=lambda k: row[k]['changes_per_onset'])
    f1s = {k: v['f1_50'] for k, v in row.items() if v['f1_50'] is not None}
    best_f1 = max(f1s, key=f1s.get) if f1s else None
    TK[lab] = {'takes': row, 'cpo_min': min(cpo), 'cpo_max': max(cpo), 'cpo_spread': round(max(cpo) - min(cpo), 3),
               'human_cpo': hum, 'ours_v040_cpo': P1.get(lab, {}).get('ours_changes_per_onset'),
               'most_moving_take': best_move, 'best_f1_take': best_f1,
               'f1_of_most_moving_minus_kept': (round(row[best_move]['f1_50'] - row['kept_20260609']['f1_50'], 3)
                                                if 'kept_20260609' in row and row[best_move]['f1_50'] is not None
                                                and row['kept_20260609']['f1_50'] is not None else None),
               'closest_to_human_take': min(row, key=lambda k: abs(row[k]['changes_per_onset'] - hum)) if hum else None}
    print('%-22s cpo %s | human %s ours %s | moving=%s bestF1=%s dF1(moving-kept)=%s' % (
        lab, ' '.join('%s:%.3f/%s' % (k.replace('seed_', '').replace('kept_20260609', 'kept'), v['changes_per_onset'],
                                       v['f1_50']) for k, v in row.items()),
        hum, TK[lab]['ours_v040_cpo'], best_move, best_f1, TK[lab]['f1_of_most_moving_minus_kept']))
OUT['takes'] = {'per_song': TK, 'pooled': {
    'songs': len(TK), 'mean_cpo_spread': m([t['cpo_spread'] for t in TK.values()]),
    'mean_cpo_kept': m([t['takes'].get('kept_20260609', {}).get('changes_per_onset') for t in TK.values()]),
    'mean_cpo_max_take': m([t['cpo_max'] for t in TK.values()]),
    'mean_human_cpo': m([t['human_cpo'] for t in TK.values()]),
    'songs_most_moving_is_best_f1': sum(t['most_moving_take'] == t['best_f1_take'] for t in TK.values()),
    'mean_f1_most_moving_minus_kept': m([t['f1_of_most_moving_minus_kept'] for t in TK.values()]),
    'mean_takes_runs16': m([m([v['runs16_share'] for v in t['takes'].values()]) for t in TK.values()]),
    'mean_takes_chord_share': m([m([v['chord_share'] for v in t['takes'].values()]) for t in TK.values()])}}
print('pooled', json.dumps(OUT['takes']['pooled']))

print('\n== part 2.1: pads, Expert drums ==')
PADS = ['kick', 'snare', 'Y-cym', 'B-cym', 'G-cym', 'Y-tom', 'B-tom', 'G-tom']
cnt_h, cnt_o = collections.Counter(), collections.Counter()
conf, cym = collections.Counter(), collections.Counter()
P2 = {}
for lab, s in R.items():
    hs = [h['drums'] for h in s['humans'].values() if 'drums' in h and 'f1_50' in h['drums'] and h['drum_type'] == 1]
    gs = [h['drums'] for h in good(s).values() if 'drums' in h and 'f1_50' in h['drums'] and h['drum_type'] == 1]
    if not hs:
        continue
    dt = [h['drum_type'] for h in s['humans'].values() if 'drums' in h]
    row = {'human_drum_types': dt, 'ours_drum_type': s['ours_drum_type'], 'pads_human': {}, 'pads_ours': {}}
    for p in PADS:
        row['pads_human'][p] = m([h['human_pad_onsets'].get(p, 0) for h in hs])
        row['pads_ours'][p] = m([h['ours_pad_counts_in_span'].get(p, 0) for h in hs])
        cnt_h[p] += row['pads_human'][p]
        cnt_o[p] += row['pads_ours'][p]
    sc, scy = collections.Counter(), collections.Counter()
    for g in gs:
        for k, v in g['confusion'].items():
            sc[k] += v / len(gs)
        for k, v in g['cymbal_confusion'].items():
            scy[k] += v / len(gs)
    conf.update(sc)
    cym.update(scy)
    row['cymbal_confusion'] = {k: round(v, 1) for k, v in sorted(scy.items())}
    for c in ('Y', 'B', 'G'):
        tot = sum(v for k, v in scy.items() if k.startswith(c + '-cym>'))
        row['%s_cym_kept' % c] = round(scy.get('%s-cym>%s-cym' % (c, c), 0) / tot, 3) if tot else None
    P2[lab] = row
    print('%-22s types h%s o%s | H %s | O %s | cym keep Y %s B %s G %s' % (
        lab, dt, s['ours_drum_type'], ' '.join('%.0f' % row['pads_human'][p] for p in PADS),
        ' '.join('%.0f' % row['pads_ours'][p] for p in PADS), row['Y_cym_kept'], row['B_cym_kept'], row['G_cym_kept']))
print('pads order', PADS)
print('pooled counts human', {p: round(cnt_h[p]) for p in PADS})
print('pooled counts ours ', {p: round(cnt_o[p]) for p in PADS})
labels = PADS + ['none']
mat = [[round(conf.get('%s>%s' % (a, b), 0)) for b in labels] for a in labels]
print('confusion (rows human, cols ours), matched onsets, leftovers paired in pad order:')
print('%7s ' % '' + ' '.join('%6s' % b for b in labels))
for a, r in zip(labels, mat):
    print('%7s ' % a + ' '.join('%6d' % x for x in r))
cl = ['Y-cym', 'B-cym', 'G-cym']
cmat = [[round(cym.get('%s>%s' % (a, b), 0)) for b in cl] for a in cl]
print('cymbal confusion (one cymbal each side):')
for a, r in zip(cl, cmat):
    print('%7s ' % a + ' '.join('%6d' % x for x in r), ' row recall %.3f' % (r[cl.index(a)] / max(sum(r), 1)))
OUT['part2_pads'] = {'per_song': P2, 'pooled_counts_human': {p: round(cnt_h[p]) for p in PADS},
                     'pooled_counts_ours': {p: round(cnt_o[p]) for p in PADS},
                     'confusion_labels': labels, 'confusion': mat, 'cymbal_labels': cl, 'cymbal_confusion': cmat}

print('\n== part 2.2/2.3: regularity and the rule ==')
P3 = {}
print('%-22s %6s %6s %6s %6s | %6s | %6s %6s %6s %6s | %6s %6s %6s | %s' % (
    'song', 'repH', 'repO', 'jacH', 'jacO', 'oRwH', 'F1', 'R.6', 'R.7', 'R.8', 'rep.6', 'rep.7', 'rep.8', 'oRwH after .6/.7/.8'))
for lab, s in R.items():
    hs = [h['drums'] for h in s['humans'].values() if 'drums' in h and h['drum_type'] == 1]
    gs = [h['drums'] for h in good(s).values() if 'drums' in h and 'f1_50' in h['drums'] and h['drum_type'] == 1]
    if not hs or 'ours_drums_regularity' not in s or not gs:
        continue
    row = {'human_repeat': m([h['human_regularity']['exact_repeat_share'] for h in hs]),
           'human_jaccard': m([h['human_regularity']['mean_jaccard'] for h in hs]),
           'ours_repeat': s['ours_drums_regularity']['exact_repeat_share'],
           'ours_jaccard': s['ours_drums_regularity']['mean_jaccard'],
           'ours_repeats_where_human_repeats': m([g['ours_repeats_where_human_repeats']['share'] for g in gs]),
           'f1_50': m([g['f1_50'] for g in gs])}
    for x in ('0.6', '0.7', '0.8'):
        row['f1_R' + x] = m([g['rule'][x]['f1_50'] for g in gs])
        row['dF1_R' + x] = round(row['f1_R' + x] - row['f1_50'], 4)
        row['repeat_R' + x] = s['rule'][x]['regularity']['exact_repeat_share']
        row['changed_R' + x] = s['rule'][x]['measures_changed']
        row['ours_rwh_R' + x] = m([g['rule'][x]['ours_repeats_where_human_repeats'] for g in gs])
    P3[lab] = row
    print('%-22s %6.3f %6.3f %6.3f %6.3f | %6s | %6.3f %+6.3f %+6.3f %+6.3f | %6.3f %6.3f %6.3f | %s %s %s' % (
        lab, row['human_repeat'], row['ours_repeat'], row['human_jaccard'], row['ours_jaccard'],
        row['ours_repeats_where_human_repeats'], row['f1_50'], row['dF1_R0.6'], row['dF1_R0.7'], row['dF1_R0.8'],
        row['repeat_R0.6'], row['repeat_R0.7'], row['repeat_R0.8'], row['ours_rwh_R0.6'], row['ours_rwh_R0.7'],
        row['ours_rwh_R0.8']))
pool3 = {k: m([r[k] for r in P3.values()]) for k in next(iter(P3.values()))}
pool3['songs'] = len(P3)
for x in ('0.6', '0.7', '0.8'):
    pool3['worst_dF1_R' + x] = min(r['dF1_R' + x] for r in P3.values())
    pool3['songs_down_more_than_0.01_R' + x] = sum(r['dF1_R' + x] < -0.01 for r in P3.values())
    pool3['songs_up_R' + x] = sum(r['dF1_R' + x] > 0 for r in P3.values())
    pool3['mean_abs_gap_repeat_before'] = m([abs(r['ours_repeat'] - r['human_repeat']) for r in P3.values()])
    pool3['mean_abs_gap_repeat_R' + x] = m([abs(r['repeat_R' + x] - r['human_repeat']) for r in P3.values()])
    pool3['bar_met_R' + x] = (pool3['f1_R' + x] > pool3['f1_50'] and pool3['songs_down_more_than_0.01_R' + x] == 0
                              and pool3['mean_abs_gap_repeat_R' + x] < pool3['mean_abs_gap_repeat_before'])
print('pooled', json.dumps(pool3))
OUT['part2_regularity'] = {'per_song': P3, 'pooled': pool3}
json.dump(OUT, open(sys.argv[2], 'w'), indent=1)
