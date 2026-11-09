"""outro3_tab.py: reads outro3.json; prints per-song rows and the bar's pooled lines."""
import json, numpy as np
R = json.load(open('<scratch>/outro3.json'))
print('song | trimmed (end/start) | end span s | kept30 | span40 | per human chart: last note (in s) / precision of trimmed-end onsets @50ms')
for lab, r in R.items():
    if r.get('no_trim_record') or not r['n_trimmed']:
        print(lab, '| none (kept30 %s span40 %s)' % (r.get('kept30_report'), r.get('span40'))); continue
    ch = '; '.join('%s last %s p_end %s p_start %s' % (c['k'], c.get('human_last_in'), None if c.get('trim_end_prec') is None else round(c['trim_end_prec'], 2), None if c.get('trim_start_prec') is None else round(c['trim_start_prec'], 2)) for c in r['charts'])
    print(lab, '|', r['n_end'], '/', r['n_start'], '|', r['end_seconds'], '| kept30', r['kept30_report'], '| span40', r['span40'], '| back40', r['n_back40'], '|', ch)
    if r['trimmed_end']: print('     trimmed-end times', r['trimmed_end'][:3], '...', r['trimmed_end'][-2:])
tot_end = sum(r.get('n_end', 0) for r in R.values()); tot_start = sum(r.get('n_start', 0) for r in R.values())
hit = tot = 0
for lab, r in R.items():
    for nm in ('trim_end',):
        ps = [c[nm + '_prec'] for c in r.get('charts', []) if c.get(nm + '_prec') is not None]
        if ps and r['n_end']: tot += r['n_end']; hit += np.mean(ps) * r['n_end']
print('trimmed end onsets', tot_end, 'start', tot_start, 'pooled precision of end trims (mean over charts, weighted by count) %.3f' % (hit / tot if tot else float('nan')))
print('songs with back40>0:', [l for l, r in R.items() if r.get('n_back40')])
