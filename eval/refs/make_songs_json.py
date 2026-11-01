"""Write <data>/refs/songs.json from the built reference folders.
usage: python -I make_songs_json.py <data>/refs"""
import json, os, sys

R = sys.argv[1]
REFS = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'refs.json')))
out = []
for entry in REFS:
    d = os.path.join(R, entry['id'])
    if not os.path.exists(os.path.join(d, 'ref_notes.json')):
        print('skipping (not built):', entry['id']); continue
    bm = json.load(open(os.path.join(d, 'build_meta.json')))
    rn = json.load(open(os.path.join(d, 'ref_notes.json')))
    oc = json.load(open(os.path.join(d, 'offset_check.json')))
    diffs = {}
    for t in rn['tracks']:
        if t['notes']:
            diffs.setdefault(t['instrument'], []).append(t['difficulty'])
    prim = 'drums' if 'drums' in oc else 'guitar'
    out.append({**entry, 'duration_s': round(bm['duration_s'], 3),
                'instruments': sorted(diffs, key=['guitar', 'bass', 'drums'].index),
                'difficulties_with_notes': diffs, 'tempo_markers': rn['tempoMarkerCount'],
                'ref_offset_check_ms': oc[prim]['median_offset_ms'], 'mix_gain': round(bm['mix_gain'], 6),
                'scan_chart_issues': len(rn['chartIssues'] or [])})
json.dump(out, open(os.path.join(R, 'songs.json'), 'w'), indent=1)
for s in out:
    print(s['id'], '|', s['artist'], '-', s['title'], '|', s['charter'], '| %.1fs' % s['duration_s'], '|', s['instruments'],
          '| tempo markers', s['tempo_markers'], '| offset check', s['ref_offset_check_ms'], 'ms')
