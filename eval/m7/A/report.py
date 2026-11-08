"""report.py: part A's tables. Reads ../A.json (analyze.py) and writes ../tables.md and ../A_pooled.json (pooled
figures with paired-bootstrap CIs over songs, 10,000 resamples); prints the pooled lines."""
import json, os, sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
from alib import boot, mean

HERE = Path(__file__).resolve().parent.parent
D = json.loads((HERE / os.environ.get('A_IN', 'A.json')).read_text())
SONGS = D['songs']
ARMS = D['arms']
OUTMD, OUTJ = HERE / 'tables.md', HERE / 'A_pooled.json'
md, pooled = [], {}


def f(x, n=3):
    return '-' if x is None else (f'{x:.{n}f}' if isinstance(x, float) else str(x))


def charts(s, part):
    return ((s['parts'].get(part) or {}).get('charts') or {})


def sv(s, part, key):
    return mean([c.get(key) for c in charts(s, part).values()])


def ha(s, part, key):
    return mean([h.get(key) for h in ((s['parts'].get(part) or {}).get('humans') or {}).values()])


def pool(part, key, base_key=None, hkey=None, songs=None):
    """Pooled song means: all, without the references, and without songs whose humans agree under 0.6 on hkey."""
    songs = songs or SONGS
    have = [s for s in songs if part in s['parts'] and sv(s, part, key) is not None]
    low = [s['label'] for s in have if hkey and ha(s, part, hkey) is not None and ha(s, part, hkey) < 0.6]
    groups = {'all': have, 'no_refs': [s for s in have if s['set'] != 'refs'],
              'agree>=0.6': [s for s in have if s['label'] not in low]}
    out = {'humans_under_0.6': low}
    for g, ss in groups.items():
        e = {'n': len(ss), 'mean': mean([sv(s, part, key) for s in ss])}
        if base_key:
            e['minus_' + base_key] = boot([sv(s, part, key) - sv(s, part, base_key) for s in ss
                                            if sv(s, part, base_key) is not None])
        out[g] = e
    return out


def line(name, p, base=None):
    def cell(g):
        e = p[g]
        b = e.get('minus_' + base) if base else None
        return f"{f(e['mean'])}" + (f" ({b['mean']:+.3f} [{b['lo']:+.3f}, {b['hi']:+.3f}])" if b else '') + f" n={e['n']}"
    return f"| {name} | {cell('all')} | {cell('no_refs')} | {cell('agree>=0.6')} |"


HDR = '| | all songs | without the references | without humans under 0.6 |\n|---|---|---|---|'

# ---------------------------------------------------------------- A-a
md.append('## A-a. The HOPO rule (Expert guitar; state agreement at 100 ms, song mean over its human charts)\n')
md.append('| song | octave | charts | base | A1 source | A2 natural | R1 | R2 (notes changed) | humans | HOPO share base / A1 / A2 / humans |')
md.append('|---|---|---|---|---|---|---|---|---|---|')
for s in SONGS:
    if 'guitar' not in s['parts']:
        md.append(f"| {s['label']} | {s['octave']} | - | no guitar part | | | | | | |")
        continue
    cs = charts(s, 'guitar')
    hs = [mean([c['hopo_share_ours'].get(a) for c in cs.values()]) for a in ('base', 'A1', 'A2')]
    md.append(f"| {s['label']} | {s['octave']} | {len(cs)} | " + ' | '.join(f(sv(s, 'guitar', 'state_' + a)) for a in ('base', 'A1', 'A2', 'R1'))
              + f" | {f(sv(s, 'guitar', 'state_R2'))} ({f(sv(s, 'guitar', 'r2_changed'), 0)}) | {f(ha(s, 'guitar', 'state'))} | "
              + ' / '.join(f(x) for x in hs) + f" / {f(sv(s, 'guitar', 'hopo_share_human'))} |")
md.append('\nPooled (mean over songs; in brackets the difference from base, paired bootstrap 95 % CI):\n')
md.append(HDR)
pooled['A-a'] = {}
for a in ('base', 'A1', 'A2', 'R1', 'R2'):
    p = pool('guitar', 'state_' + a, None if a == 'base' else 'state_base', 'state')
    pooled['A-a'][a] = p
    md.append(line(a, p, None if a == 'base' else 'state_base'))
pb = pool('bass', 'state_base', None, 'state')
pooled['A-a']['bass_base'] = pb
md.append(line('bass, base (every arm: bass stays "forced")', pb))
md.append(f"\nSongs whose humans agree under 0.6 on the guitar's states: {', '.join(pooled['A-a']['base']['humans_under_0.6']) or 'none'}.")
md.append('Songs off octave 1: ' + ', '.join(f"{s['label']} ({s['octave']})" for s in SONGS if (s['octave'] or 1) != 1) + '.\n')
md.append('Per song, the songs R1 touches (octave not 1):\n')
md.append('| song | octave | base | R1 = A1 | R1 - base | humans |\n|---|---|---|---|---|---|')
for s in SONGS:
    if (s['octave'] or 1) != 1 and 'guitar' in s['parts']:
        b, r = sv(s, 'guitar', 'state_base'), sv(s, 'guitar', 'state_R1')
        md.append(f"| {s['label']} | {s['octave']} | {f(b)} | {f(r)} | {f(r - b if r is not None else None, 3)} | {f(ha(s, 'guitar', 'state'))} |")
# confusion
md.append('\n**The confusion by the engine\'s flag** (matched notes, summed over every song and human chart; "forced strum": '
          'the engine strums a note our natural rule makes a HOPO, i.e. A1 strum and A2 HOPO; "forced HOPO" the reverse; '
          '"unforced": A1 and A2 agree; "tap": a tap in either):\n')
md.append('| class | notes | human strums | human HOPOs | human taps |\n|---|---|---|---|---|')
tot = {}
for s in SONGS:
    for c in charts(s, 'guitar').values():
        for k, d in (c.get('by_engine_flag') or {}).items():
            t = tot.setdefault(k, {'n': 0, 'human_strum': 0, 'human_hopo': 0, 'human_tap': 0})
            for x in t:
                t[x] += d[x]
for k in ('forced_strum', 'forced_hopo', 'unforced', 'tap'):
    if k in tot:
        t = tot[k]
        md.append(f"| {k} | {t['n']} | {t['human_strum'] / t['n']:.3f} | {t['human_hopo'] / t['n']:.3f} | {t['human_tap'] / t['n']:.3f} |")
pooled['A-a']['confusion'] = tot
md.append('\nPer song, the forced strums (notes; share the humans strum, mean over charts):\n')
md.append('| song | octave | forced strums | humans strum | forced HOPOs | humans HOPO |\n|---|---|---|---|---|---|')
for s in SONGS:
    cs = charts(s, 'guitar')
    if not cs:
        continue
    def cl(k, h):
        v = [c['by_engine_flag'].get(k) for c in cs.values() if c.get('by_engine_flag')]
        v = [x for x in v if x]
        return (f(mean([x['n'] for x in v]), 0), f(mean([x[h] / x['n'] for x in v]))) if v else ('0', '-')
    a, b = cl('forced_strum', 'human_strum'), cl('forced_hopo', 'human_hopo')
    md.append(f"| {s['label']} | {s['octave']} | {a[0]} | {a[1]} | {b[0]} | {b[1]} |")

# ---------------------------------------------------------------- A-b
md.append('\n## A-b. Taps (Expert guitar, base charts)\n')
md.append('| song | tap share ours | humans | our taps | human taps | precision | recall | T0 | T1 no taps | T2 runs >= 8 at >= 8/s |')
md.append('|---|---|---|---|---|---|---|---|---|---|')
for s in SONGS:
    if 'guitar' not in s['parts']:
        continue
    md.append(f"| {s['label']} | {f(sv(s, 'guitar', 'tap_share_ours'))} | {f(sv(s, 'guitar', 'tap_share_human'))} | "
              f"{f(sv(s, 'guitar', 'tap_n_ours'), 0)} | {f(sv(s, 'guitar', 'tap_n_human'), 0)} | {f(sv(s, 'guitar', 'tap_precision'))} | "
              f"{f(sv(s, 'guitar', 'tap_recall'))} | " + ' | '.join(f(sv(s, 'guitar', 'state_' + t)) for t in ('T0', 'T1', 'T2')) + ' |')
md.append('\n' + HDR)
pooled['A-b'] = {}
for t in ('T0', 'T1', 'T2'):
    p = pool('guitar', 'state_' + t, None if t == 'T0' else 'state_T0', 'state')
    pooled['A-b'][t] = p
    md.append(line(t, p, None if t == 'T0' else 'state_T0'))
for k in ('tap_precision', 'tap_recall', 'tap_share_ours', 'tap_share_human'):
    pooled['A-b'][k] = pool('guitar', k)
    md.append(line(k, pooled['A-b'][k]))

# ---------------------------------------------------------------- A-c
slow = [s for s in SONGS if (s['bpm'] or 999) < 100]
md.append('\n## A-c. Sustains (Expert)\n')
md.append('The slow songs (our grid under 100 BPM, report.json grid.bpm_median): '
          + ', '.join(f"{s['label']} ({s['bpm']:.1f})" for s in slow) + '.\n')
for part in ('guitar', 'bass'):
    md.append(f'\n**{part}**: sustain share (ours per arm / the humans), per-note sustain agreement at 100 ms (per arm, the humans\' own), the share of the humans\' sustains each arm\'s floor would drop\n')
    md.append('| song | BPM | share ' + ' / '.join(ARMS) + ' / humans | agreement ' + ' / '.join(ARMS) + ' / humans | dropped ' + ' / '.join(ARMS) + ' |')
    md.append('|---|---|---|---|---|')
    for s in SONGS:
        if part not in s['parts']:
            continue
        cs = charts(s, part)
        sh = ' / '.join(f(sv(s, part, 'sus_share_' + a)) for a in ARMS) + f" / {f(sv(s, part, 'sus_share_human'))}"
        ag = ' / '.join(f(sv(s, part, 'sus_agree_' + a)) for a in ARMS) + f" / {f(ha(s, part, 'sus_agree'))}"
        dr = ' / '.join(f(mean([c['human_sus_dropped_share'].get(a) for c in cs.values()])) for a in ARMS)
        md.append(f"| {s['label']}{' (slow)' if s in slow else ''} | {s['bpm']:.0f} | {sh} | {ag} | {dr} |")
    md.append('\n' + HDR)
    pooled.setdefault('A-c', {})[part] = {}
    for a in ARMS:
        p = pool(part, 'sus_agree_' + a, None if a == 'base' else 'sus_agree_base', 'sus_agree')
        ps = pool(part, 'sus_agree_' + a, None if a == 'base' else 'sus_agree_base', 'sus_agree', songs=slow)
        pooled['A-c'][part][a] = {'all': p, 'slow': ps}
        md.append(line(f'agreement {a}', p, None if a == 'base' else 'sus_agree_base'))
        md.append(line(f'agreement {a}, the slow songs', ps, None if a == 'base' else 'sus_agree_base'))
    for a in ARMS:
        p = pool(part, 'sus_share_' + a)
        pooled['A-c'][part]['share_' + a] = p
        md.append(line(f'sustain share {a}', p))
    for s in SONGS:
        for c in charts(s, part).values():
            for a in ARMS:
                c['_drop_' + a] = c['human_sus_dropped_share'].get(a)
    for a in ARMS:
        pooled['A-c'][part]['dropped_' + a] = {'all': pool(part, '_drop_' + a), 'slow': pool(part, '_drop_' + a, songs=slow)}
        md.append(line(f"humans' sustains the floor drops, {a}", pooled['A-c'][part]['dropped_' + a]['all']))
        md.append(line(f"humans' sustains the floor drops, {a}, the slow songs", pooled['A-c'][part]['dropped_' + a]['slow']))
    p = pool(part, 'sus_share_human')
    pooled['A-c'][part]['share_human'] = p
    md.append(line('sustain share, humans', p))
    md.append(f"\nSongs whose humans agree under 0.6 on {part} sustains: {', '.join(pooled['A-c'][part]['base']['all']['humans_under_0.6']) or 'none'}.")
    # human sustain lengths
    md.append(f'\nThe humans\' {part} sustain lengths (per song, mean over its charts of each chart\'s median and p10; split at 100 BPM of the human map):\n')
    md.append('| song | n under 100 | ms p50 / p10 | beats p50 / p10 | n 100 and over | ms p50 / p10 | beats p50 / p10 |\n|---|---|---|---|---|---|---|')
    for s in SONGS:
        cs = charts(s, part)
        if not cs:
            continue
        row = [s['label']]
        for k in ('slow', 'fast'):
            v = [c['human_sus_len'][k] for c in cs.values() if c['human_sus_len'][k]['n']]
            n = sum(c['human_sus_len'][k]['n'] for c in cs.values())
            if not v:
                row += [str(n), '-', '-']
                continue
            row += [str(n), f"{mean([x['ms_p50'] for x in v]):.0f} / {mean([x['ms_p10'] for x in v]):.0f}",
                    f"{mean([x['beats_p50'] for x in v]):.2f} / {mean([x['beats_p10'] for x in v]):.2f}"]
        md.append('| ' + ' | '.join(row) + ' |')

# ---------------------------------------------------------------- A-d
md.append('\n## A-d. The guitar\'s same-fret repeats (Expert guitar, base charts)\n')
md.append('| song | repeat share ours | humans (mean; min-max) | repeats | matched@50 repeats / other | unmatched | in a human sustain | unmatched gap ms p25 / p50 / p75 |')
md.append('|---|---|---|---|---|---|---|---|')
for s in SONGS:
    r = s.get('repeats')
    if not r:
        continue
    hr = [x for x in r['repeat_share_human'].values() if x is not None]
    u = r['unmatched_repeats']
    g = u['gap_ms']
    md.append(f"| {s['label']} | {f(r['repeat_share_ours'])} | {f(mean(hr))} ({f(min(hr))}-{f(max(hr))}) | {r['n_repeats']} | "
              f"{f(r['match50_repeats'])} / {f(r['match50_other'])} | {u['n']} | {u['in_human_sustain']} | "
              + (f"{g['25']:.0f} / {g['50']:.0f} / {g['75']:.0f}" if g else '-') + ' |')
rules = sorted({k for s in SONGS if s.get('repeats') for k in s['repeats']['rules']},
               key=lambda k: (int(k[3:6]), k))
md.append('\nThe candidate rules (removed: summed; precision: pooled over the removed notes, a note with no human chart\'s '
          'note within 50 ms; F1@50 change: song mean over charts, pooled with the bootstrap CI; repeat share after vs the humans\'):\n')
md.append('| rule | removed | songs touched | precision | F1@50 change (CI) | repeat share after / before / humans |\n|---|---|---|---|---|---|')
pooled['A-d'] = {}
rs = [s for s in SONGS if s.get('repeats')]
hum_rep = mean([mean(list(s['repeats']['repeat_share_human'].values())) for s in rs])
before = mean([s['repeats']['repeat_share_ours'] for s in rs])
for k in rules:
    v = [s['repeats']['rules'].get(k) for s in rs]
    v = [x for x in v if x]
    rem = sum(x['removed'] for x in v)
    prec = sum(x['precision'] * x['removed'] for x in v if x['precision'] is not None) / rem if rem else None
    b = boot([x['f1_50_change'] for x in v])
    after = mean([x['repeat_share_after'] for x in v])
    pooled['A-d'][k] = {'removed': rem, 'songs': sum(1 for x in v if x['removed']), 'precision': prec, 'f1_50_change': b,
                        'repeat_share_after': after}
    md.append(f"| {k} | {rem} | {sum(1 for x in v if x['removed'])} | {f(prec)} | {b['mean']:+.3f} [{b['lo']:+.3f}, {b['hi']:+.3f}] | "
              f"{f(after)} / {f(before)} / {f(hum_rep)} |")
md.append('\nPer song, the removals (removed / precision / F1@50 change):\n')
md.append('| song | ' + ' | '.join(rules) + ' |\n|' + '---|' * (len(rules) + 1))
for s in rs:
    md.append(f"| {s['label']} | " + ' | '.join(
        (lambda x: f"{x['removed']} / {f(x['precision'], 2)} / {x['f1_50_change']:+.3f}" if x else '-')(s['repeats']['rules'].get(k))
        for k in rules) + ' |')

# ---------------------------------------------------------------- A-e
md.append('\n## A-e. The second review\'s guitar questions (Expert guitar, base charts)\n')
md.append('Opens: share of onsets with an open note, ours and the humans\' (each chart: primary first), the longest run of '
          'consecutive opens; the open-to-green candidate as the exact-lane and contour (lane direction) agreement at 100 ms, '
          'before and after (onset F1 cannot move; states as charted).\n')
md.append('| song | open share ours (n, longest run) | humans: share (longest run) each chart | exact lanes before / after | contour before / after |')
md.append('|---|---|---|---|---|')
def ae(s, k, who='ae_ours'):
    return [c[who].get(k) for c in charts(s, 'guitar').values() if c.get(who)]
for s in SONGS:
    cs = charts(s, 'guitar')
    if not cs:
        continue
    c0 = list(cs.values())[0]['ae_ours']
    hum = ', '.join(f"{f(c['ae_human']['open_share'])} ({c['ae_human']['open_longest_run']})" for c in cs.values())
    md.append(f"| {s['label']} | {f(c0['open_share'])} ({c0['n_open']}, {c0['open_longest_run']}) | {hum} | "
              f"{f(sv(s, 'guitar', 'lane_exact_base'))} / {f(sv(s, 'guitar', 'lane_exact_open2green'))} | "
              f"{f(sv(s, 'guitar', 'lane_contour_base'))} / {f(sv(s, 'guitar', 'lane_contour_open2green'))} |")
pooled['A-e'] = {}
md.append('\n' + HDR)
for k, b in (('lane_exact_base', None), ('lane_exact_open2green', 'lane_exact_base'),
             ('lane_contour_base', None), ('lane_contour_open2green', 'lane_contour_base'), ('state_T3', 'state_T0')):
    pooled['A-e'][k] = pool('guitar', k, b, 'state' if 'state' in k else None)
    md.append(line(k, pooled['A-e'][k], b))
for s in SONGS:
    for c in charts(s, 'guitar').values():
        c['_oo'], c['_oh'] = c['ae_ours']['open_share'], c['ae_human']['open_share']
pooled['A-e']['open_share_ours'] = pool('guitar', '_oo')
pooled['A-e']['open_share_human'] = pool('guitar', '_oh')
md.append(line('open share ours', pooled['A-e']['open_share_ours']))
md.append(line('open share humans', pooled['A-e']['open_share_human']))
hd = [abs(h['ae']['open_share'] - list(charts(s, 'guitar').values())[0]['ae_human']['open_share'])
      for s in SONGS for h in ((s['parts'].get('guitar') or {}).get('humans') or {}).values() if h.get('ae')]
md.append(f"\nThe humans' own agreement on the open share: |alt - primary| mean {f(mean(hd))}, max {f(max(hd) if hd else None)} over {len(hd)} alt charts.\n")
md.append('\nTaps on same-fret repeats and repeats in fast runs (runs of at least 8 onsets at most 1/8 s apart):\n')
md.append('| song | our taps / on a repeat / share | humans\' taps on a repeat: share (taps) each chart | notes in fast runs ours | repeat share in fast runs ours / humans each | song-wide ours / humans | T0 / T3 state |')
md.append('|---|---|---|---|---|---|---|')
for s in SONGS:
    cs = charts(s, 'guitar')
    if not cs:
        continue
    o = list(cs.values())[0]['ae_ours']
    ht = ', '.join(f"{f(c['ae_human']['tap_repeat_share'])} ({c['ae_human']['n_taps']})" for c in cs.values())
    hf = ', '.join(f(c['ae_human']['fast_repeat_share']) for c in cs.values())
    hr = ', '.join(f(c['ae_human']['repeat_share']) for c in cs.values())
    md.append(f"| {s['label']} | {o['n_taps']} / {o['taps_on_repeat']} / {f(o['tap_repeat_share'])} | {ht} | {o['n_fast']} | "
              f"{f(o['fast_repeat_share'])} / {hf} | {f(o['repeat_share'])} / {hr} | {f(sv(s, 'guitar', 'state_T0'))} / {f(sv(s, 'guitar', 'state_T3'))} |")
for s in SONGS:
    for c in charts(s, 'guitar').values():
        c['_fo'], c['_fh'] = c['ae_ours']['fast_repeat_share'], c['ae_human']['fast_repeat_share']
pooled['A-e']['fast_repeat_ours'] = pool('guitar', '_fo')
pooled['A-e']['fast_repeat_human'] = pool('guitar', '_fh')
md.append('\n' + HDR)
md.append(line('repeat share in fast runs, ours', pooled['A-e']['fast_repeat_ours']))
md.append(line('repeat share in fast runs, humans', pooled['A-e']['fast_repeat_human']))

md.append('\nHOPO chords: the share of Expert guitar chords Clone Hero plays as HOPOs (forced; a chord is never a natural HOPO), ours per arm and each human chart\'s:\n')
md.append('| song | our chords | ' + ' / '.join(ARMS[:3]) + ' | humans each chart |\n|---|---|---|---|')
for s in SONGS:
    cs = charts(s, 'guitar')
    if not cs:
        continue
    c0 = list(cs.values())[0]
    md.append(f"| {s['label']} | {c0['n_chords']} | " + ' / '.join(f(c0['hopo_chord_share'].get(a)) for a in ARMS[:3])
              + ' | ' + ', '.join(f(c['hopo_chord_share_human']) for c in cs.values()) + ' |')
for s in SONGS:
    for c in charts(s, 'guitar').values():
        for a in ARMS[:3]:
            c['_hc_' + a] = c['hopo_chord_share'].get(a)
pooled['A-e']['hopo_chords'] = {a: pool('guitar', '_hc_' + a) for a in ARMS[:3]}
pooled['A-e']['hopo_chords']['human'] = pool('guitar', 'hopo_chord_share_human')
md.append('\n' + HDR)
for a in ARMS[:3]:
    md.append(line('HOPO chord share, ours ' + a, pooled['A-e']['hopo_chords'][a]))
md.append(line('HOPO chord share, humans', pooled['A-e']['hopo_chords']['human']))
hs = [[c['hopo_chord_share_human'] for c in charts(s, 'guitar').values() if c['hopo_chord_share_human'] is not None] for s in SONGS]
sp = [max(x) - min(x) for x in hs if len(x) > 1]
md.append(f"\nThe humans' spread (max - min over a song's charts): mean {f(mean(sp))}, max {f(max(sp) if sp else None)} over {len(sp)} songs with several charts.\n")

OUTMD.write_text('\n'.join(md) + '\n')
OUTJ.write_text(json.dumps(pooled, indent=1, default=float))
print('wrote', OUTMD, OUTJ)
