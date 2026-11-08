"""M7-01 B-c2 tables. Reads bc2.json; prints the Markdown section; adds "bc2" to summary.json (floats 3 decimals)."""
import json, sys
import numpy as np
from pathlib import Path
H = Path(__file__).resolve().parent; sys.path.insert(0, str(H))
from stats import boot
d = json.load(open(H / 'bc2.json'))['songs']
ARMS = ['n%d_s%.2f' % (n, s) for n in (3, 4, 5) for s in (0.40, 0.60)]
BASE = 'n3_s0.40'
def dist(x, sh): lo, hi = min(sh), max(sh); return max(lo - x, 0, x - hi)
print('\n## B-c2. The solo count cap (max_solos)\n')
many = {s: max(h['count'] for h in r['humans'].values()) for s, r in d.items() if max(h['count'] for h in r['humans'].values()) > 3}
print('Songs with a human chart of more than 3 solos: ' + ', '.join('%s %d' % kv for kv in many.items()) + '.\n')
print('Per song where any arm changes (count / share / cover / inside), and the human charts\' counts and shares:\n')
print('| song | humans: count share | ' + ' | '.join(ARMS) + ' |'); print('|---' * (2 + len(ARMS)) + '|')
for s, r in d.items():
    if all(r['arms'][a] == r['arms'][BASE] for a in ARMS) and s not in many: continue
    hs = '; '.join('%s %d %.3f' % (k, h['count'], h['share']) for k, h in r['humans'].items())
    cell = lambda a: '%d / %.3f / %s / %s' % (a['count'], a['share'], '-' if a['cover_human'] is None else '%.3f' % a['cover_human'], '-' if a['inside_human'] is None else '%.3f' % a['inside_human'])
    print(f"| {s} | {hs} | " + ' | '.join(cell(r['arms'][a]) for a in ARMS) + ' |')
print('\n| arm | songs that change | cover pooled (diff vs n3 0.40 [CI]) | inside pooled (diff [CI]) | toward the humans\' range | away |')
print('|---|---|---|---|---|---|')
SUM = {}
for a in ARMS:
    ch = [s for s, r in d.items() if r['arms'][a] != r['arms'][BASE]]
    hs = [s for s, r in d.items() if r['arms'][a]['cover_human'] is not None]
    ins = [s for s, r in d.items() if r['arms'][a]['inside_human'] is not None and r['arms'][BASE]['inside_human'] is not None]
    cov = float(np.mean([d[s]['arms'][a]['cover_human'] for s in hs]))
    inn = float(np.mean([d[s]['arms'][a]['inside_human'] for s in ins]))
    dc = boot([d[s]['arms'][a]['cover_human'] - d[s]['arms'][BASE]['cover_human'] for s in hs])
    di = boot([d[s]['arms'][a]['inside_human'] - d[s]['arms'][BASE]['inside_human'] for s in ins])
    tw, aw = [], []
    for s, r in d.items():
        sh = [h['share'] for h in r['humans'].values()]
        x, y = dist(r['arms'][a]['share'], sh), dist(r['arms'][BASE]['share'], sh)
        if x < y - 1e-9: tw.append(s)
        elif x > y + 1e-9: aw.append(s)
    SUM[a] = {'changed': ch, 'cover': round(cov, 3), 'inside': round(inn, 3), 'cover_diff_ci': dc, 'inside_diff_ci': di, 'toward': tw, 'away': aw}
    print(f"| {a} | {', '.join(ch) or 'none'} | {cov:.3f} ({dc}) | {inn:.3f} ({di}) | {', '.join(tw) or 'none'} | {', '.join(aw) or 'none'} |")
print('\nArm names: n<max_solos>_s<max_share>; n3_s0.40 is today. Cover = the humans\' solo time inside ours (mean over '
      'charts with solos; songs with human solos), inside = our solo time inside a chart\'s solos (mean over all charts); '
      'toward/away = the song\'s solo share nearer to or further from the range of its human charts\' shares than today.')
sm = json.load(open(H / 'summary.json')); sm['bc2'] = SUM; json.dump(sm, open(H / 'summary.json', 'w'), indent=1)
