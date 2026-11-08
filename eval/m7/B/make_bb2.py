"""M7-01 B-b2 tables. Reads bb2.json, bb2_ntl.json, bb.json (humans' agreement); prints Markdown; adds "bb2" to
summary.json."""
import json, sys
import numpy as np
from pathlib import Path
H = Path(__file__).resolve().parent; sys.path.insert(0, str(H))
from stats import boot
REFS = {'all_the_small_things', 'creep', 'drunk_drivers', 'kimochi_warui', 'lucretia', 'take_me_out'}
d = json.load(open(H / 'bb2.json')); bb = json.load(open(H / 'bb.json'))
ntl = json.load(open(H / 'bb2_ntl.json')) if (H / 'bb2_ntl.json').exists() else None
agree = {s: bb[s]['humans_f1_agree'] for s in d}
RULES = list(next(iter(d.values()))['rules'])
print('\n## B-b2. The bass run rule (a run over one held pitch becomes one note)\n')
print('Rule L<n>_G<ms>: n or more consecutive same-lane single onsets of our chart, each G ms or less after the one before, '
      'whose engine pitches are within 0.5 st of the run\'s first and with the pitch track voiced within 0.5 st of it over '
      'every frame from the first onset to the last, become one note (the first kept, the rest removed; its sustain is not '
      'scored). Precision = removed onsets no human bass note has within 50 ms. Pooled F1 leaves out songs whose humans agree '
      'under 0.6 (' + ', '.join(sorted(s for s, a in agree.items() if a is not None and a < 0.6)) + ').\n')
print('| rule | songs touched | removed | precision pooled | F1@50 change [CI] all / no refs | songs down > 0.01 | refs down > 0.01 | worst song | repeat share after (ours / humans, song means) |')
print('|---|---|---|---|---|---|---|---|---|')
SUM = {}
orep = np.mean([r['repeat_share'] for r in d.values()]); hrep = np.mean([r['humans_repeat'] for r in d.values()])
for rule in RULES:
    rows = {s: r['rules'][rule] for s, r in d.items()}
    ok = [s for s in d if agree[s] is None or agree[s] >= 0.6]
    rem = sum(rows[s]['removed'] for s in d); good = sum(rows[s]['removed_no_human'] for s in d)
    ca = boot([rows[s]['f1_change'] for s in ok]); cn = boot([rows[s]['f1_change'] for s in ok if s not in REFS])
    down = [s for s in d if rows[s]['f1_change'] < -0.01]
    worst = min(d, key=lambda s: rows[s]['f1_change'])
    after = np.mean([rows[s]['repeat_share_after'] for s in d])
    t = [s for s in d if rows[s]['removed']]
    SUM[rule] = {'touched': t, 'removed': rem, 'precision': round(good / rem, 3) if rem else None, 'ci_all': ca, 'ci_norefs': cn,
                 'down': down, 'repeat_after': round(float(after), 3)}
    print(f"| {rule} | {len(t)} | {rem} | {'-' if not rem else '%.3f' % (good / rem)} | {ca} / {cn} | {', '.join(d_ for d_ in down if d_ not in REFS) or 'none'} | "
          f"{', '.join(d_ for d_ in down if d_ in REFS) or 'none'} | {worst} {rows[worst]['f1_change']:+.3f} | {after:.3f} ({orep:.3f} / {hrep:.3f}) |")
print('\nPer song (removed / precision / F1@50 change) for each rule:\n')
print('| song | repeat ours / humans | ' + ' | '.join(RULES) + ' |'); print('|---' * (2 + len(RULES)) + '|')
for s, r in d.items():
    cell = lambda x: '%d / %s / %+.3f' % (x['removed'], '-' if x['precision'] is None else '%.2f' % x['precision'], x['f1_change'])
    print(f"| {s} | {r['repeat_share']:.3f} / {r['humans_repeat']:.3f} | " + ' | '.join(cell(r['rules'][k]) for k in RULES) + ' |')
if ntl:
    print(f"\n**ntl** (the owner's ballad, our CPU chart, no human chart): {ntl['notes']} bass onsets, repeat share "
          f"{ntl['repeat_share']:.3f}, {ntl['gaps_le_110ms']} gaps of 110 ms or less; the rule merges " +
          ', '.join('%s %d' % kv for kv in ntl['merged'].items()) + ' onsets.')
    SUM['ntl'] = ntl
sm = json.load(open(H / 'summary.json')); sm['bb2'] = SUM; json.dump(sm, open(H / 'summary.json', 'w'), indent=1)
