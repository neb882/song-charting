"""M7-01 B-e tables. Reads be.json and be_cand.json; prints the Markdown section; adds "be" to summary.json."""
import json, sys
import numpy as np
from pathlib import Path
H = Path(__file__).resolve().parent; sys.path.insert(0, str(H))
from stats import boot
d = json.load(open(H / 'be.json')); cd = json.load(open(H / 'be_cand.json'))
K = [('kicks_per_s', 'kicks/s'), ('kicks_per_s_peak10', 'densest 10 s, kicks/s'), ('kick_share', 'kick share'),
     ('bare_kick_share', 'bare-kick share'), ('double_kick_share', '2x share')]
SUM = {'outside': {}}
print('\n## B-e. Expert drums: kicks and fill endings\n')
print('20 songs have a human drum chart (drunk_drivers, sooth and break have none); pm2 2 charts, s05 4, s06 3, the rest 1-2. '
      'Ours = today\'s CPU charts (pm2 included: the review\'s GPU chart was not measured). Each human chart over its own span; '
      'ours over the primary\'s. `*` = ours outside the humans\' range.\n')
print('| song | charts | ' + ' | '.join(n for _, n in K) + ' | kick P / R @50 (2x out: P / R) | our unmatched kicks: n of all, in 16th runs (matched: in runs), 2x |')
print('|---' * (3 + len(K)) + '|')
for s, r in d.items():
    hs = list(r['humans'].values()); cells = []
    for k, _ in K:
        v = [h[k] for h in hs]; o = r['ours'][k]; out = o > max(v) + 1e-9 or o < min(v) - 1e-9
        SUM['outside'].setdefault(k, []).append(s) if out else None
        cells.append('%.2f [%.2f-%.2f]%s' % (o, min(v), max(v), '*' if out else ''))
    m = lambda k: np.mean([h[k] for h in hs if h[k] is not None])
    um = r['ours_unmatched_kicks']
    print(f"| {s} | {len(hs)} | " + ' | '.join(cells) + f" | {m('kick_precision'):.3f} / {m('kick_recall'):.3f} ({m('kick_precision_no2x'):.3f} / {m('kick_recall_no2x'):.3f}) | "
          f"{um} of {r['ours_kicks']}, {'-' if r['unmatched_in_16th_runs'] is None else '%.2f' % r['unmatched_in_16th_runs']} ({'-' if r['matched_in_16th_runs'] is None else '%.2f' % r['matched_in_16th_runs']}), {'-' if r['unmatched_2x_share'] is None else '%.2f' % r['unmatched_2x_share']} |")
for k, n in K:
    print(f"- {n}: ours outside the humans' range on {len(SUM['outside'].get(k, []))} of {len(d)} songs"
          + (f" (above on {sum(1 for s in SUM['outside'].get(k, []) if d[s]['ours'][k] > max(h[k] for h in d[s]['humans'].values()))})" ))
P = [np.mean([h['kick_precision'] for h in r['humans'].values()]) for r in d.values()]
um = sum(r['ours_unmatched_kicks'] for r in d.values()); al = sum(r['ours_kicks'] for r in d.values())
SUM['kick_precision_song_mean'] = round(float(np.mean(P)), 3); SUM['unmatched_kicks'] = [um, al]
top = sorted(d, key=lambda s: -d[s]['ours_unmatched_kicks'])[:3]
print(f"- Kick precision, song mean {np.mean(P):.3f}; our kicks no human chart has within 50 ms: {um} of {al}, "
      f"{', '.join('%s %d' % (s, d[s]['ours_unmatched_kicks']) for s in top)} the most.\n")
print('**Fill endings** (our fills = the chart\'s drum fill phrases, = report.json\'s fills; "crash" = starpower\'s test: a green '
      'cymbal, or a yellow or blue one with fewer than 3 others on its pad within 2 beats; humans: pro-drums charts only):\n')
print('| song | our fills, crash share (report.json) | human charts: fills, crash share | humans: crash on our section starts | added crash: n, judged, a human crash there / any cymbal / any onset |')
print('|---|---|---|---|---|')
low = []; prec = []; precy = []
for s, r in d.items():
    hf = '; '.join('%s %d %s' % (k, v['fills'], '-' if v['crash_share'] is None else '%.2f' % v['crash_share']) for k, v in r['humans_fill'].items()) or 'no pro chart'
    hss = '; '.join('%s %s' % (k, '-' if v is None else '%.2f' % v) for k, v in r['humans_crash_at_section_start'].items()) or '-'
    a = r['add_crash']; f2 = lambda x: '-' if x is None else '%.2f' % x
    hv = [v['crash_share'] for v in r['humans_fill'].values() if v['crash_share'] is not None]
    if hv and r['ours_fill_crash_share'] is not None and r['ours_fill_crash_share'] < min(hv) - 1e-9: low.append(s)
    if a['judged']: prec.append((a['judged'], a['precision_crash'], a['precision_cymbal']))
    print(f"| {s} | {r['ours_fills']}, {f2(r['ours_fill_crash_share'])} ({f2(r['report_fill_crash_share'])}) | {hf} | {hss} | {a['n']}, {a['judged']}, {f2(a['precision_crash'])} / {f2(a['precision_cymbal'])} / {f2(a['any_onset_there'])} |")
n = sum(p[0] for p in prec)
pc = sum(p[0] * p[1] for p in prec) / n; py = sum(p[0] * p[2] for p in prec) / n
SUM['fill_crash_below_humans'] = low; SUM['add_crash_precision'] = {'judged': n, 'crash': round(pc, 3), 'any_cymbal': round(py, 3)}
print(f"\nOur fill crash share is under every human chart's on {len(low)} songs: {', '.join(low)}.")
print(f"\n**Candidate C (a crash added at the end of each of our fills that has none):** {n} added crashes judged (inside a pro "
      f"human chart's span; s08's only drum chart is not pro), pooled precision {pc:.3f} against the humans' crash test, "
      f"{py:.3f} against any cymbal. A note is there on our chart already at almost every fill end, so onset F1@50 does not "
      "change; only the pad/cymbal agreement would.\n")
print('**Candidates K (kicks thinned in runs of 16th-note kicks)**, no build: K<N> removes every second kick of a run of 4+ '
      'kicks at gaps of a 16th or less whose rate is N kicks a second or more; K2x removes the runs\' double-kick (Expert+) '
      'kicks instead. Removal precision = removed kicks with no human kick within 50 ms (pooled by count).\n')
print('| rule | songs touched | kicks removed | precision pooled | drums onset F1@50 change [CI] | kick F1@50 change [CI] | per song (removed, precision, onset F1 change) |')
print('|---|---|---|---|---|---|---|')
SUM['kick_rules'] = {}
for rule in ('K8', 'K10', 'K12', 'K2x'):
    rows = {s: r[rule] for s, r in cd.items()}
    t = [s for s, x in rows.items() if x['kicks_removed']]
    rem = sum(x['kicks_removed'] for x in rows.values()); good = sum(x['kicks_removed'] * (x['precision'] or 0) for x in rows.values())
    co = boot([x['onset_f1_change'] for x in rows.values()]); ck = boot([x['kick_f1_change'] for x in rows.values()])
    SUM['kick_rules'][rule] = {'touched': t, 'removed': rem, 'precision': round(good / rem, 3) if rem else None, 'onset_ci': co, 'kick_ci': ck}
    per = '; '.join('%s %d %.2f %+.3f' % (s, rows[s]['kicks_removed'], rows[s]['precision'], rows[s]['onset_f1_change']) for s in t)
    print(f"| {rule} | {len(t)} | {rem} | {'-' if not rem else '%.3f' % (good / rem)} | {co} | {ck} | {per} |")
sm = json.load(open(H / 'summary.json')); sm['be'] = SUM; json.dump(sm, open(H / 'summary.json', 'w'), indent=1)
