"""tables_ia.py: the intake's and part A's tables as Markdown. Reads intake/intake.json and A/part_a.json (both
labels only); writes intake/intake.md and A/part_a.md; prints nothing.
Usage: python3 -I tables_ia.py <m8-02 folder>"""
import json
import os
import sys

M = sys.argv[1]
I = json.load(open(os.path.join(M, 'intake', 'intake.json')))
A = json.load(open(os.path.join(M, 'A', 'part_a.json')))
f3 = lambda x: '-' if x is None else ('%.3f' % x if isinstance(x, float) else str(x))

# ---- intake
L = ['| label | seeds made | device | input = dev | cut short (stitched) | tokens (4 seeds) | onsets GPU (4 seeds) | beats | '
     'length s | GPU wall s, 4 takes | wall / length | identical notes to CPU (of 4) |', '|' + '---|' * 12]
by = {}
for r in I['takes']:
    by.setdefault(r['label'], []).append(r)
tot_w = tot_l = 0.0
for lab, rs in by.items():
    ons = '/'.join('{:,}'.format(A['songs'][lab]['gpu'][str(r['seed'])]['onsets']) if lab in A['songs'] else '-' for r in rs)
    wall = sum(r['wall_s'] for r in rs)
    length = rs[0]['audio_s']
    if lab != 'test_song':
        tot_w += wall
        tot_l += length
    L.append('| %s | %d/4 | %s | %s | %s | %s | %s | %s | %.0f | %.0f | %.2f | %s |' % (
        lab, sum(r['status'] == 'made' for r in rs), ','.join(sorted({r['device'] for r in rs})),
        'yes' if all(r['input_match'] for r in rs) else 'NO',
        ','.join(sorted({str(r['cut_short']) for r in rs})) + (' (yes)' if all(r['stitched'] for r in rs) else ''),
        '/'.join(str(r['tokens']) for r in rs), ons, rs[0]['beats'], length, wall, wall / length,
        A['identical_notes_takes_per_song'].get(lab, '-')))
L.append('\nThe 23 songs: GPU wall time for 4 takes %.0f s over %.0f s of audio (%.2f s a second of audio; the first take '
         'includes Demucs and the timing stage, the other three reuse them).' % (tot_w, tot_l, tot_w / tot_l))
open(os.path.join(M, 'intake', 'intake.md'), 'w').write('\n'.join(L) + '\n')

# ---- part A
MS = [('onsets', 'Expert onsets'), ('ratio_to_primary', 'onsets / primary'), ('chord_share', 'chord share'),
      ('open_share', 'open share'), ('open_longest_run', 'longest open run'), ('repeat_share', 'same-fret repeat share'),
      ('fast_repeat_share', 'repeat share in fast runs'), ('sustain_share', 'sustain share'),
      ('forced_hopo_share', 'forced-HOPO share'), ('forced_strum_share', 'forced-strum share'), ('tap_share', 'tap share'),
      ('peak_1s', '1-s peak density'), ('fast_time_share', 'share of song in fast runs'),
      ('changes_per_onset', 'shape changes / onset'), ('chord_runs16_share', 'chord onsets in 16+ runs')]
L = []
for g, title in (('all23', 'all 23 songs'), ('no_refs17', 'the 17 without the references'), ('refs6', 'the 6 references')):
    L += ['\n**Pooled, %s** (per song: mean of its 4 takes; humans: mean over its charts; GPU minus CPU paired over '
          'songs, bootstrap 10,000, seed 7):\n' % title,
          '| measure | GPU | CPU | humans | GPU - CPU [95 % CI] | GPU - humans | CPU - humans |', '|---|---|---|---|---|---|---|']
    for k, name in MS:
        p = A['pooled'][g][k]
        b, gh, ch = p['gpu_minus_cpu'], p['gpu_minus_human'], p['cpu_minus_human']
        ci = '%+.3f [%+.3f, %+.3f] (n %d)' % (b['mean'], b['lo'], b['hi'], b['n']) if b else '-'
        L.append('| %s | %s | %s | %s | %s | %s | %s |' % (name, f3(p['gpu']), f3(p['cpu']), f3(p['human']), ci,
                                                         '%+.3f' % gh['mean'] if gh else '-', '%+.3f' % ch['mean'] if ch else '-'))
KEYS = ['onsets', 'ratio_to_primary', 'chord_share', 'open_share', 'repeat_share', 'fast_repeat_share', 'sustain_share',
        'forced_hopo_share', 'tap_share', 'peak_1s', 'fast_time_share', 'changes_per_onset', 'chord_runs16_share']
L += ['\n**Per song** (GPU / CPU / humans mean [min-max]):\n',
      '| song | charts | ' + ' | '.join(KEYS) + ' |', '|' + '---|' * (len(KEYS) + 2)]
for lab, s in A['songs'].items():
    row = []
    for k in KEYS:
        p = s['per_song'][k]
        row.append('%s / %s / %s [%s-%s]' % (f3(p['gpu']), f3(p['cpu']), f3(p['human_mean']), f3(p['human_min']), f3(p['human_max'])))
    L.append('| %s | %d | %s |' % (lab, s['n_humans'], ' | '.join(row)))
L += ['\n**Per take, shape changes per onset and onsets** (GPU / CPU, seeds 20260609, 101, 202, 303):\n',
      '| song | GPU changes/onset | CPU changes/onset | GPU onsets | CPU onsets |', '|---|---|---|---|---|']
for lab, s in A['songs'].items():
    sd = ['20260609', '101', '202', '303']
    L.append('| %s | %s | %s | %s | %s |' % (lab, ' '.join(f3(s['gpu'][x]['changes_per_onset']) for x in sd),
                                             ' '.join(f3(s['cpu'][x]['changes_per_onset']) for x in sd),
                                             ' '.join('{:,}'.format(s['gpu'][x]['onsets']) for x in sd),
                                             ' '.join('{:,}'.format(s['cpu'][x]['onsets']) for x in sd)))
open(os.path.join(M, 'A', 'part_a.md'), 'w').write('\n'.join(L) + '\n')
