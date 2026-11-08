"""M7-09 tables: reads <shm>/m709/out/{sooth,s02,s04,ntl,owner_sim}.json (measure.py's) and drift_guard.json;
prints markdown tables (numbers and labels only) and copies the JSON next to this script as results.json."""
import json
from pathlib import Path
OUT = Path('<shm>/m709/out'); HERE = Path(__file__).parent
CANDS = ['today', 'a0', 'a1', 'b', 'c']
R = {l: json.loads((OUT / f'{l}.json').read_text()) for l in ('sooth', 's02', 's04', 'ntl', 'owner_sim')
     if (OUT / f'{l}.json').exists()}
(HERE / 'results.json').write_text(json.dumps(R, indent=1))
f = lambda x: '-' if x is None else (f'{x:.3f}' if isinstance(x, float) else str(x))  # noqa: E731

for l, r in R.items():
    print(f"\n### {l}\n\nfirst grid {r['first']['bpm']:.2f} BPM, {r['first']['mode']} ({r['first']['start_grid']}), "
          f"share {r['first']['confident_share']}; allin1 {r['allin1_bpm']:.2f} BPM; a parity matches to allin1 "
          f"{r['a_parity_allin1_matches']} -> {r['a_pick']}; errors {r['errors'] or 'none'}; calibration "
          f"{r.get('calibration')}\n")
    hk = sorted({k for g in r['grids'].values() for k in (g.get('beat_f1') or {})})
    head = ['grid', 'start', 'mode', 'ev ratio', 'BPM p1-p50-p99 (min-max)', 'drift p95 ms (2 beats)', 'tc halved',
            'tc first fold', 'gtr R8 whole / 0-35s'] + [f'beat F1 {k}' for k in hk] + [f'downbeat F1 {k}' for k in hk]
    print('| ' + ' | '.join(head) + ' |\n|' + '---|' * len(head))
    for n in CANDS:
        g = r['grids'].get(n)
        if not g:
            continue
        b = g['bpm_4beat']
        gp = g['guitar_phase']
        row = [n, g['start_grid'], g['mode'], f(g['evidence_ratio']),
               f"{b['p1']:.1f}-{b['p50']:.1f}-{b['p99']:.1f} ({b['min']:.1f}-{b['max']:.1f})",
               f"{g['drift_ms']['p95_abs']:.0f} ({g['two_beats_ms']:.0f}){' FIRES' if g['drift_guard_fires'] else ''}",
               str(len(g['tempo_check_halved_fold'])),
               '; '.join(f'{a:.0f}-{z:.0f}s {w:.0f}/{gb:.0f}' for a, z, w, gb in g['tempo_check_first_fold']) or '0',
               ' / '.join(f"{gp[w]['R8']:.3f}" if gp[w] else '-' for w in ('whole', '0-35s'))]
        row += [f((g.get('beat_f1') or {}).get(k)) for k in hk] + [f((g.get('downbeat_f1') or {}).get(k)) for k in hk]
        print('| ' + ' | '.join(row) + ' |')
    st = r['grids']['today'].get('stretches') or []
    if st:
        print('\nper straight-line stretch (today\'s report stretches, >= 16 beats, under half timed), beat F1:\n')
        print('| grid | ' + ' | '.join(f"{s['t0']:.0f}-{s['t1']:.0f}s ({s['beats']}) {k}" for s in st for k in hk) + ' |')
        print('|---|' + '---|' * (len(st) * len(hk)))
        for n in CANDS:
            g = r['grids'].get(n)
            if g:
                print(f'| {n} | ' + ' | '.join(f(s.get(k)) for s in g['stretches'] for k in hk) + ' |')
    if l == 'ntl':
        print('\nntl guitar notes off the 48-tick grid after the real quantizer (window = ticks 4608-8640 of '
              "today's chart, in audio time):\n\n| grid | 19-33 s | rest | tempo map BPM | markers |\n|---|---|---|---|---|")
        for n in CANDS:
            q = r['grids'][n]['quantized_off8']
            print(f"| {n} | {q['19-33s'][0]} of {q['19-33s'][1]} | {q['rest'][0]} of {q['rest'][1]} | "
                  f"{q['tempo_map_bpm'][0]:.1f}-{q['tempo_map_bpm'][1]:.1f} | {q['markers']} |")
    if l == 'owner_sim':
        o = r['owner']
        print(f"\nowner file: offset {o['offset_s']} s, {o['matched_under_480s']} of {o['n_today_beats_under_480s']} "
              f"beats matched; its tail {o['owner_tail_bpm_median']:.1f} BPM; its tempo map "
              f"{o['owner_bpm_min']}-{o['owner_bpm_max']}\n\n| grid | tail BPM (last 28 s) | tail beats |\n|---|---|---|")
        for n in CANDS:
            g = r['grids'].get(n)
            if g:
                print(f"| {n} | {f(g['tail_bpm_median'])} | {g['tail_beats']} |")
