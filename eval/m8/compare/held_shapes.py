"""Chord shapes held: ours (v0.4.0, the owner's GPU chart) against the human chart of kimochi_warui, Expert guitar.

The human chart only through the scorer's readers (notes: tick, ms, lanes). Usage:
  python -I eval/m8/compare/held_shapes.py <a checkout with tools/scan-chart installed> <the reference's kept folder> <our chart folder>
The review's spans are in our notes.chart's ticks (resolution 192); times are on the reference's input.wav.
"""
import collections
import json
import os
import sys

sys.path.insert(0, sys.argv[1])
from eval.scorer import score as S  # noqa: E402

ref_dir, ours_dir = sys.argv[2], sys.argv[3]
cand, _ = S.find_chart_folder(ours_dir)
rsc, csc = S.scan(os.path.join(ref_dir, 'ref')), S.scan(cand)

x = S.decode(os.path.join(ref_dir, 'input.wav'))
c = S.load_mix(cand, S.audio_files(cand))
al = S.align(x, c)
ref_shift = S.chart_delay_ms(rsc)[0]
cand_shift = S.chart_delay_ms(csc)[0] - al['lag_ms']

key = ('guitar', 'expert')
rnotes, cnotes = S.tracks_by_key(rsc)[key], S.tracks_by_key(csc)[key]
ro, co = S.onsets(rnotes, ref_shift, 'guitar'), S.onsets(cnotes, cand_shift, 'guitar')
pairs = S.match([o['t'] for o in ro], [o['t'] for o in co], 0.050)
f1 = S.prf(len(pairs), len(ro), len(co))['f1']

# our chart's ticks (the review's spans are in our notes.chart's ticks)
ctick = {}
for n in cnotes:
    ctick.setdefault(n['tick'], (n['ms'] + cand_shift) / 1000.0)


def shape(o):
    return '+'.join('GRYBO'[l] if l >= 0 else 'open' for l in sorted(set(o['lanes'])))


def runs(ons):
    """Maximal runs of consecutive onsets with the same shape: (shape, count, t0, t1)."""
    out = []
    for o in ons:
        s = shape(o)
        if out and out[-1][0] == s:
            out[-1][1] += 1
            out[-1][3] = o['t']
        else:
            out.append([s, 1, o['t'], o['t']])
    return out


def describe(ons, t0, t1):
    w = [o for o in ons if t0 - 1e-6 <= o['t'] <= t1 + 1e-6]
    if not w:
        return {'onsets': 0}
    rs = runs(w)
    chords = [o for o in w if len(set(o['lanes'])) > 1]
    top = collections.Counter(shape(o) for o in w).most_common(4)
    longest = max(rs, key=lambda r: r[1])
    return {'onsets': len(w), 'chord_share': round(len(chords) / len(w), 3),
            'distinct_shapes': len({shape(o) for o in w}), 'shape_changes': len(rs) - 1,
            'changes_per_10s': round((len(rs) - 1) / max(t1 - t0, 1e-6) * 10, 2),
            'longest_run': {'shape': longest[0], 'onsets': longest[1],
                            'seconds': round(longest[3] - longest[2], 3)},
            'top_shapes': top}


SPANS = {'verse 1A (ticks 7680-13728)': (7680, 13728), 'break (ticks 68736-75168)': (68736, 75168),
         'chorus 4A/4B (ticks 77952-92064)': (77952, 92064)}
out = {'alignment': {'lag_ms': al['lag_ms'], 'mad_ms': al.get('lag_mad_ms'), 'windows_used': al['windows_used'],
                     'guitar_expert_f1_50': f1},
       'resolution': csc.get('resolution'), 'spans': {}}
for name, (a, b) in SPANS.items():
    ts = [t for k, t in ctick.items() if a <= k <= b]
    t0, t1 = min(ts), max(ts)
    out['spans'][name] = {'seconds': [round(t0, 3), round(t1, 3)],
                          'ours': describe(co, t0, t1), 'human': describe(ro, t0, t1)}


def whole(ons):
    rs = runs(ons)
    long16 = sum(r[1] for r in rs if r[1] >= 16 and '+' in r[0])
    top = sorted(rs, key=lambda r: -r[1])[:5]
    return {'onsets': len(ons), 'shape_changes': len(rs) - 1,
            'onsets_per_shape_change': round(len(ons) / max(len(rs) - 1, 1), 2),
            'chord_onsets_in_same_shape_runs_of_16_plus': long16,
            'longest_runs': [{'shape': r[0], 'onsets': r[1], 't': [round(r[2], 2), round(r[3], 2)]} for r in top]}


out['whole_song'] = {'ours': whole(co), 'human': whole(ro)}
print(json.dumps(out, indent=1))
