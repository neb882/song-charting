"""Write <data>/<set>/songs.json from the built folders of a set.
usage: python -I make_songs_json.py <data>/refs [list.json]
The list is refs.json (the default) or the stress set's merged list (stress.py songs --json), whose entries also
name their other human charts (`alts`), built in <data>/stress/<id>/alt/<md5>/."""
import json, os, sys

R = sys.argv[1]
LIST = sys.argv[2] if len(sys.argv) > 2 else os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'refs.json')
REFS = json.load(open(LIST))
KNOWN = ['guitar', 'bass', 'drums']


def built(d, entry):
    bm = json.load(open(os.path.join(d, 'build_meta.json')))
    rn = json.load(open(os.path.join(d, 'ref_notes.json')))
    oc = json.load(open(os.path.join(d, 'offset_check.json')))
    diffs = {}
    for t in rn.get('tracks') or []:
        if t['notes']:
            diffs.setdefault(t['instrument'], []).append(t['difficulty'])
    prim = 'drums' if 'drums' in oc else 'guitar'
    return {**entry, 'duration_s': round(bm['duration_s'], 3),
            'instruments': sorted(diffs, key=lambda i: (KNOWN.index(i) if i in KNOWN else len(KNOWN), i)),
            'difficulties_with_notes': diffs, 'tempo_markers': rn['tempoMarkerCount'],
            'ref_offset_check_ms': (oc.get(prim) or {}).get('median_offset_ms'), 'mix_gain': round(bm['mix_gain'], 6),
            'stems_skipped': [s['file'] for s in bm.get('stems_skipped') or []],
            'scan_chart_issues': len(rn['chartIssues'] or [])}


out = []
for entry in REFS:
    d = os.path.join(R, entry['id'])
    if not os.path.exists(os.path.join(d, 'ref_notes.json')):
        print('skipping (not built):', entry['id']); continue
    s = built(d, {k: v for k, v in entry.items() if k != 'alts'})
    if 'alts' in entry:
        s['alts'] = []
        for alt in entry['alts']:
            a = os.path.join(d, 'alt', alt['md5'])
            if not os.path.exists(os.path.join(a, 'ref_notes.json')):
                print('skipping (not built): %s alt %s' % (entry['id'], alt['md5'][:6])); continue
            s['alts'].append(built(a, alt))
    out.append(s)
json.dump(out, open(os.path.join(R, 'songs.json'), 'w'), indent=1)
for s in out:
    print(s['id'], '|', s.get('artist'), '-', s.get('title'), '|', s.get('charter'), '| %.1fs' % s['duration_s'],
          '|', s['instruments'], '| tempo markers', s['tempo_markers'], '| offset check', s['ref_offset_check_ms'], 'ms'
          + ''.join(' | alt %s: %s' % (a['md5'][:6], a['instruments']) for a in s.get('alts') or []))
