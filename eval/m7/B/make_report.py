"""M7-01 part B: the tables. Reads ba_raw.json, bb.json, bc.json, bd.json (this folder); prints the report's tables
as Markdown and writes summary.json (the pooled numbers and CIs)."""
import json, sys
import numpy as np
from pathlib import Path
H = Path(__file__).resolve().parent
sys.path.insert(0, str(H))
from stats import boot
REFS = {'all_the_small_things', 'creep', 'drunk_drivers', 'kimochi_warui', 'lucretia', 'take_me_out'}
ba = json.load(open(H / 'ba.json')); bb = json.load(open(H / 'bb.json'))
bc = json.load(open(H / 'bc.json')); bd = json.load(open(H / 'bd.json'))
SUM = {}
f = lambda x, n=3: '-' if x is None else (('%.' + str(n) + 'f') % x)

def pool(rows, key_ok=lambda s: True):
    """with refs / without refs, songs whose humans agree under 0.6 left out."""
    out = {}
    for name, filt in (('all', lambda s: True), ('no_refs', lambda s: s not in REFS)):
        out[name] = [v for s, a, v in rows if filt(s) and (a is None or a >= 0.6) and key_ok(s)]
    return out

print('## B-a. Notes over a silent stem\n')
print('Human notes in silence (each chart; count / share of its Expert notes), per D:\n')
print('| song | part | stem | humans agree F1@50 | D25 | D30 | D35 | ours silent D25 (report.json) |')
print('|---|---|---|---|---|---|---|---|')
for s, v in ba.items():
    for p in ('guitar', 'bass', 'drums'):
        if p not in v: continue
        r = v[p]
        cell = lambda d: '; '.join('%s %d/%.3f' % (k, x[0], x[1]) for k, x in r['human_silent_' + d].items())
        print(f"| {s} | {p} | {r['stem']} | {f(r['humans_f1_agree'])} | {cell('25')} | {cell('30')} | {cell('35')} | {r['report_silent_count']} |")
SUM['ba'] = {}
for p in ('guitar', 'bass', 'drums'):
    print(f'\n**{p}**: candidates (removed onsets; removal precision = share no human chart has within 50 ms; the human '
          'notes the same rule removes, the largest share over the song\'s charts; F1@50 change, mean over charts)\n')
    print('| rule | D | songs touched | removed | precision pooled | songs with human removal >= 0.5 % | F1@50 change pooled [95 % CI] (all / no refs) | worst song F1 change |')
    print('|---|---|---|---|---|---|---|---|')
    for rule in ('i', 'ii'):
        for d in ('25', '30', '35'):
            rows = [(s, v[p]['humans_f1_agree'], v[p][f'rule_{rule}_{d}']) for s, v in ba.items() if p in v]
            P = pool(rows)
            rem = sum(x['removed'] for x in P['all']); good = sum(x['removed_no_human'] for x in P['all'])
            touched = [s for s, a, x in rows if x['removed']]
            hum = [s for s, a, x in rows if x['human_removed_max_share'] >= 0.005]
            ca = boot([x['f1_change'] for x in P['all']]); cn = boot([x['f1_change'] for x in P['no_refs']])
            worst = min(rows, key=lambda t: t[2]['f1_change'])
            left = [s for s, a, x in rows if a is not None and a < 0.6]
            SUM['ba'][f'{p}_{rule}_{d}'] = {'removed': rem, 'precision': round(good / rem, 4) if rem else None, 'f1_ci_all': ca,
                                           'f1_ci_norefs': cn, 'human_ge_0.5pct': hum, 'left_out_agree_lt_0.6': left}
            print(f"| {rule} | {d} | {len(touched)} | {rem} | {f(good / rem if rem else None)} | {len(hum)}: {', '.join(hum)} | "
                  f"{ca} / {cn} | {worst[0]} {worst[2]['f1_change']:+.4f} |")
    left = sorted({s for s, v in ba.items() if p in v and v[p]['humans_f1_agree'] is not None and v[p]['humans_f1_agree'] < 0.6})
    print(f'\nLeft out of the pooled F1 (humans agree under 0.6 on {p} F1@50): {", ".join(left) or "none"}.')
print('\nPer song (rule i, D 25; removed / precision / largest human share removed / F1 change), where anything is removed:\n')
print('| song | part | removed | precision | human removed (max share) | F1@50 change | rule ii D25 removed / precision / F1 change |')
print('|---|---|---|---|---|---|---|')
for s, v in ba.items():
    for p in ('guitar', 'bass', 'drums'):
        if p in v and (v[p]['rule_i_25']['removed'] or v[p]['rule_i_35']['removed']):
            a, b = v[p]['rule_i_25'], v[p]['rule_ii_25']
            print(f"| {s} | {p} | {a['removed']} | {f(a['precision'])} | {a['human_removed_max_share']:.4f} | {a['f1_change']:+.4f} | {b['removed']} / {f(b['precision'])} / {b['f1_change']:+.4f} |")
print('\nDrums in quiet sections (our sections; quiet = the drum stem\'s section loudness 10 dB or more under the song\'s median section):\n')
print('| song | quiet sections | their seconds | ours onsets/s | humans onsets/s | F1@50 there | F1@50 elsewhere (section mean) |')
print('|---|---|---|---|---|---|---|')
qa, qr = [], []
for s, v in ba.items():
    rows = v.get('drum_sections')
    if not rows: continue
    q = [r for r in rows if r['quiet']]; o = [r for r in rows if not r['quiet'] and r['f1_50'] is not None]
    if not q: continue
    fq = [r['f1_50'] for r in q if r['f1_50'] is not None]
    secs = sum(r['end'] - r['start'] for r in q)
    w = lambda k: sum(r[k] * (r['end'] - r['start']) for r in q) / secs
    print(f"| {s} | {len(q)} | {secs:.0f} | {w('ours_per_s'):.2f} | {w('human_per_s'):.2f} | {f(np.mean(fq) if fq else None)} | {f(np.mean([r['f1_50'] for r in o]) if o else None)} |")
    if fq and o: qa.append(float(np.mean(fq))); qr.append(float(np.mean([r['f1_50'] for r in o])))
SUM['ba']['drums_quiet_sections'] = {'songs': len(qa), 'f1_quiet_mean': round(float(np.mean(qa)), 4) if qa else None,
                                     'f1_rest_mean': round(float(np.mean(qr)), 4) if qr else None}

print('\n## B-b. The bass\n')
print('| song | charts | humans agree F1@50 | repeat share ours / humans (mean, range) | largest lane ours / humans | humans open share | notes ratio | repeat match@50 / other | F1@50 |')
print('|---|---|---|---|---|---|---|---|---|')
for s, r in bb.items():
    hr = [h['repeat_share'] for h in r['humans'].values()]; hl = [h['largest'] for h in r['humans'].values()]
    ho = [h['open'] for h in r['humans'].values()]
    print(f"| {s} | {len(hr)} | {f(r['humans_f1_agree'])} | {r['ours']['repeat_share']:.3f} / {np.mean(hr):.3f} ({min(hr):.3f}-{max(hr):.3f}) | "
          f"{r['ours']['largest']:.3f} / {np.mean(hl):.3f} | {np.mean(ho):.3f} | {r['notes_ratio_primary']:.3f} | {f(r['repeat_match50'])} / {f(r['other_match50'])} | {r['f1_50']:.3f} |")
print('\nLane spread (lanes 0-4 share of single notes), ours and the humans\' mean:\n')
print('| song | ours | humans |'); print('|---|---|---|')
for s, r in bb.items():
    hm = np.mean([h['lanes'] for h in r['humans'].values()], axis=0)
    print(f"| {s} | {' '.join('%.2f' % x for x in r['ours']['lanes'])} | {' '.join('%.2f' % x for x in hm)} |")
print('\n**The cause** (the engine re-run in process; our consecutive same-lane single notes, by the engine\'s pitches):\n')
print('| song | same-lane pairs: same pitch / changed >= 1 st / 0.5-1 st / unknown | same-pitch held through the onset | held: median HFC rank | pitch changes >= 1 st | share keeping the lane |')
print('|---|---|---|---|---|---|')
tot = {'same_pitch': 0, 'changed_ge1': 0, 'between': 0, 'unknown': 0}; held = 0; ch = 0; kl = 0
for s, r in bb.items():
    c = r['our_repeats_by_pitch']
    for k in tot: tot[k] += c[k]
    held += r['same_pitch_repeats_held']; ch += r['pitch_changes_ge1']; kl += (r['pitch_changes_keep_lane_share'] or 0) * r['pitch_changes_ge1']
    print(f"| {s} | {c['same_pitch']} / {c['changed_ge1']} / {c['between']} / {c['unknown']} | {r['same_pitch_repeats_held']} | {f(r['held_hfc_rank_p50'], 2)} | {r['pitch_changes_ge1']} | {f(r['pitch_changes_keep_lane_share'])} |")
SUM['bb'] = {'pairs': tot, 'same_pitch_held': held, 'pitch_changes_ge1': ch, 'keep_lane_share': round(kl / ch, 4) if ch else None}
print(f"| all | {tot['same_pitch']} / {tot['changed_ge1']} / {tot['between']} / {tot['unknown']} | {held} | | {ch} | {f(kl / ch if ch else None)} |")
print('\n**(a) the gate on held notes** (X: an onset in the song\'s top X % of HFC rises is kept):\n')
print('| X | removed | precision pooled | F1@50 change pooled [CI] (all / no refs) | songs down > 0.01 | refs down > 0.01 | repeat share after (song mean) vs ours / humans |')
print('|---|---|---|---|---|---|---|')
agree = {s: r['humans_f1_agree'] for s, r in bb.items()}
hrep = np.mean([np.mean([h['repeat_share'] for h in r['humans'].values()]) for r in bb.values()])
orep = np.mean([r['ours']['repeat_share'] for r in bb.values()])
SUM['bb']['gate'] = {}
for X in ('0', '10', '25', '50'):
    rows = [(s, agree[s], r['gate_a'][X]) for s, r in bb.items()]
    P = pool(rows)
    rem = sum(x['removed'] for x in P['all']); good = sum(round(x['removed'] * (x['precision'] or 0)) for x in P['all'])
    ca = boot([x['f1_change'] for x in P['all']]); cn = boot([x['f1_change'] for x in P['no_refs']])
    down = [s for s, a, x in rows if x['f1_change'] < -0.01]
    after = np.mean([x['repeat_share_after'] for s, a, x in rows])
    SUM['bb']['gate'][X] = {'removed': rem, 'precision': round(good / rem, 4) if rem else None, 'ci_all': ca, 'ci_norefs': cn, 'down': down}
    print(f"| {X} | {rem} | {f(good / rem if rem else None)} | {ca} / {cn} | {', '.join(down) or 'none'} | {', '.join(d for d in down if d in REFS) or 'none'} | {after:.3f} vs {orep:.3f} / {hrep:.3f} |")
print('\n**(b) the map** (a pitch change of a semitone or more always changes the lane):\n')
print('| song | lanes changed | contour before | after | repeat share after |'); print('|---|---|---|---|---|')
rows = []
for s, r in bb.items():
    m = r['map_b']
    print(f"| {s} | {m['lanes_changed']} | {f(m['contour_before'])} | {f(m['contour_after'])} | {m['repeat_share_after']:.3f} |")
    if m['contour_before'] is not None: rows.append((s, agree[s], m['contour_after'] - m['contour_before']))
P = pool(rows)
SUM['bb']['map'] = {'contour_ci_all': boot(P['all']), 'contour_ci_norefs': boot(P['no_refs']),
                    'repeat_after': round(float(np.mean([r['map_b']['repeat_share_after'] for r in bb.values()])), 4)}
print(f"\nContour change pooled [CI]: {SUM['bb']['map']['contour_ci_all']} (all), {SUM['bb']['map']['contour_ci_norefs']} (no refs); repeat share after {SUM['bb']['map']['repeat_after']:.3f} (ours {orep:.3f}, humans {hrep:.3f}).")
left = sorted(s for s, a in agree.items() if a is not None and a < 0.6)
print(f'Left out of the pooled figures (humans agree under 0.6 on bass F1@50): {", ".join(left) or "none"}.')

print('\n## B-c. Solos\n')
songs = bc['songs']
inst = [s for s, r in songs.items() if r['instrumental']]
print(f"Instrumental: our report.json's vocals stem level under {bc['instrumental_db']} dB: {', '.join(inst)} "
      f"({', '.join('%s %.1f' % (s, songs[s]['vocals_level_db']) for s in inst)} dB); every other song is at -16.0 dB or louder.")
print(f"Largest human solo share: {bc['largest_human_share']:.3f}, so the M5-03 cap would be {bc['cap_from_humans']:.2f}.\n")
print('| song | vocals dB | human charts: solos (measures/s) and share | ours (report): count, share, trimmed/skipped by share | cover humans | ours inside |')
print('|---|---|---|---|---|---|')
for s, r in songs.items():
    hs = '; '.join('%s %s %.3f' % (k, ','.join('%g/%g' % tuple(x) for x in h['solos']) or 'none', h['share']) for k, h in r['humans'].items())
    o = r['ours_report']; a = r['arms']['0.40']
    print(f"| {s} | {r['vocals_level_db']:.1f} | {hs} | {o['count']}, {o['share']:.3f}, {o['trimmed_by_share']}/{o['skipped_by_share']} | {f(a['cover_human'])} | {f(a['inside_human'])} |")
over = [(s, k, h['share']) for s, r in songs.items() for k, h in r['humans'].items() if h['share'] > 0.40]
print(f"\nHuman charts over 0.40: {len(over)} on {len({s for s, _, _ in over})} songs: {', '.join('%s %s %.3f' % x for x in over)}.\n")
print('| arm | songs that change | our share (song mean) | cover humans pooled (songs with human solos) | ours inside pooled | songs whose share leaves its humans\' range or moves away |')
print('|---|---|---|---|---|---|')
SUM['bc'] = {'over_040': over, 'instrumentals': inst, 'arms': {}}
for arm in songs[next(iter(songs))]['arms']:
    ch = [s for s, r in songs.items() if r['arms'][arm]['share'] != r['arms']['0.40']['share']]
    hs = [s for s, r in songs.items() if r['arms'][arm]['cover_human'] is not None]
    cov = np.mean([songs[s]['arms'][arm]['cover_human'] for s in hs])
    ins = [r['arms'][arm]['inside_human'] for r in songs.values() if r['arms'][arm]['inside_human'] is not None]
    bad = []
    for s, r in songs.items():
        sh = [h['share'] for h in r['humans'].values()]; lo, hi = min(sh), max(sh)
        d = lambda x: max(lo - x, 0, x - hi)
        if d(r['arms'][arm]['share']) > d(r['arms']['0.40']['share']) + 1e-9: bad.append(s)
    dc = boot([songs[s]['arms'][arm]['cover_human'] - songs[s]['arms']['0.40']['cover_human'] for s in hs])
    di = boot([r['arms'][arm]['inside_human'] - r['arms']['0.40']['inside_human'] for r in songs.values() if r['arms'][arm]['inside_human'] is not None])
    SUM['bc']['arms'][arm] = {'changed': ch, 'cover': round(float(cov), 4), 'inside': round(float(np.mean(ins)), 4),
                              'cover_diff_ci': dc, 'inside_diff_ci': di, 'moves_away': bad}
    print(f"| {arm} | {', '.join(ch) or 'none'} | {np.mean([r['arms'][arm]['share'] for r in songs.values()]):.3f} | {cov:.4f} (diff {dc}) | {np.mean(ins):.4f} (diff {di}) | {', '.join(bad) or 'none'} |")
out_range = [s for s, r in songs.items() if not (min(h['share'] for h in r['humans'].values()) - 1e-9 <= r['arms']['0.40']['share'] <= max(h['share'] for h in r['humans'].values()) + 1e-9)]
print(f"\nToday (0.40), songs whose solo share is outside their humans' range: {len(out_range)}: {', '.join(out_range)}.")
SUM['bc']['outside_range_today'] = out_range

print('\n## B-d. Drumless stretches\n')
print('| song | octave | stretches | seconds | share | whole-song beat F1 (chart mean) | rest of song |')
print('|---|---|---|---|---|---|---|')
for s, r in bd.items():
    w = [v for v in r['whole_song_f1'].values() if v is not None]; rr = [v for v in (r.get('rest_f1') or {}).values() if v is not None]
    print(f"| {s} | {r['octave']} | {r['n_stretches']} | {r['seconds']} | {r['share']:.3f} | {f(np.mean(w) if w else None)} | {f(np.mean(rr) if rr else None)} |")
print('\nPer stretch: beat F1 against the human beat lines (mean over the charts that have beat lines there):\n')
M = ('ours', 'allin1', 'allin1_oct', 'bass_env', 'bass_env_oct', 'guitar_low', 'guitar_low_oct')
print('| song | stretch (s) | beats | timed | ' + ' | '.join(M) + ' |'); print('|---' * (4 + len(M)) + '|')
st_rows = []
for s, r in bd.items():
    for x in r['stretches']:
        if x['mean'] is None:
            print(f"| {s} | {x['t0']}-{x['t1']} | {x['beats']} | {x['timed']} | " + ' | '.join(['no human beat lines'] + [''] * (len(M) - 1)) + ' |')
            continue
        print(f"| {s} | {x['t0']}-{x['t1']} | {x['beats']} | {x['timed']} | " + ' | '.join(f(x['mean'][m]) for m in M) + ' |')
        st_rows.append((s, x['mean']))
SUM['bd'] = {'stretches_with_humans': len(st_rows), 'songs': len({s for s, _ in st_rows}), 'cands': {}}
print('\n| candidate | mean over stretches (ours) | difference [CI over songs] | stretches down > 0.05 |'); print('|---|---|---|---|')
for m in M[1:]:
    d = [x[m] - x['ours'] for _, x in st_rows]
    bys = {}
    for s, x in st_rows: bys.setdefault(s, []).append(x[m] - x['ours'])
    ci = boot([np.mean(v) for v in bys.values()])
    down = sum(1 for v in d if v < -0.05)
    SUM['bd']['cands'][m] = {'mean': round(float(np.mean([x[m] for _, x in st_rows])), 4), 'diff_stretch_mean': round(float(np.mean(d)), 4), 'ci_songs': ci, 'down_005': down}
    print(f"| {m} | {np.mean([x[m] for _, x in st_rows]):.3f} ({np.mean([x['ours'] for _, x in st_rows]):.3f}) | {np.mean(d):+.3f} {ci} | {down} of {len(d)} |")
json.dump(SUM, open(H / 'summary.json', 'w'), indent=1, default=str)
