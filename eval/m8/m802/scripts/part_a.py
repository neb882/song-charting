"""part_a.py: M8-02 part A, the takes' shape, GPU against CPU (no build).
Reads: the unpacked zip's GPU takes (takes/<ref>/seed_*, takes/stress|set20/<label>/seed_*: notes.chart, through
score.py's scan; the ExpertSingle section's N 5 / N 6 markers of OUR charts for the forced flags), the CPU takes (the
kept take $DEV/golden/<work>/<id>/guitar/seed_20260609 and $DEV/golden/m7-takes/<id>/seed_101|202|303), and the human
charts only through score.py's scan (notes and flags; primary ref/ and each alt/<k>/ref, as
eval/m8/lanes-drums/measure.py finds them). Expert guitar, notes only; whole charts (no alignment, no span cut).
Writes <out>.json (labels only, 3 decimals); prints per-song progress lines (labels only) and the pooled table.
Usage: SONGCHARTER_SCAN_CHART=<scan.cjs> python -I part_a.py <orch checkout> <$DEV> <zip/gpu_results> <out.json>"""
import json
import os
import sys

sys.path.insert(0, sys.argv[1])
from eval.scorer import score as S  # noqa: E402
import numpy as np  # noqa: E402

DEV, Z, OUT = sys.argv[2], os.path.join(sys.argv[3], 'takes'), sys.argv[4]
G = os.path.join(DEV, 'golden')
REFS = ["all_the_small_things", "creep", "drunk_drivers", "kimochi_warui", "lucretia", "take_me_out"]
STRESS = ["break", "pm2", "sooth", "troop"]
SET20 = sorted(s["id"] for s in json.load(open(os.path.join(DEV, 'eval-set20/stress/songs.json'))))
assert len(SET20) == 13
SEEDS = (20260609, 101, 202, 303)
SONGS = []   # (label, set, human song dir, kept folder, m7-takes folder, gpu folder)
for s in REFS:
    SONGS.append((s, 'refs', os.path.join(DEV, 'eval/refs', s), os.path.join(G, 'work', s), os.path.join(G, 'm7-takes', s), os.path.join(Z, s)))
for s in STRESS:
    SONGS.append((s, 'stress', os.path.join(DEV, 'eval/stress', s), os.path.join(G, 'stress-work', s), os.path.join(G, 'm7-takes', s), os.path.join(Z, 'stress', s)))
for i, s in enumerate(SET20, 1):
    lb = 's%02d' % i
    SONGS.append((lb, 'set20', os.path.join(DEV, 'eval-set20/stress', s), os.path.join(G, 'set20-work', s), os.path.join(G, 'm7-takes', s), os.path.join(Z, 'set20', lb)))
KEY = ('guitar', 'expert')
FAST_GAP, FAST_N, RUN16 = 0.125, 8, 16


def r3(x):
    return None if x is None else round(float(x), 3)


def human_folders(song_dir):   # eval/m8/lanes-drums/measure.py's
    out = [('primary', song_dir)]
    alt = os.path.join(song_dir, 'alt')
    if os.path.isdir(alt):
        for k, d in enumerate(sorted(os.listdir(alt)), 1):
            p = os.path.join(alt, d)
            if os.path.isfile(os.path.join(p, 'input.wav')) and os.path.isdir(os.path.join(p, 'ref')):
                out.append(('alt%d' % k, p))
    return out


def forced_ticks(chart_path):
    """OUR take's ExpertSingle section: the ticks with an N 5 (forced) and with an N 6 (tap) marker."""
    forced, tap, on = set(), set(), False
    with open(chart_path, encoding='utf-8-sig', errors='replace') as f:
        for line in f:
            s = line.strip()
            if s.startswith('['):
                on = s == '[ExpertSingle]'
                continue
            if on and '= N ' in s:
                tick, rest = s.split('=', 1)
                parts = rest.split()
                if parts[1] == '5':
                    forced.add(int(tick))
                elif parts[1] == '6':
                    tap.add(int(tick))
    return forced, tap


def notes_section(chart_path):
    """The SyncTrack and ExpertSingle sections' lines (for 'identical notes' between a GPU and a CPU take)."""
    keep, on = [], False
    with open(chart_path, encoding='utf-8-sig', errors='replace') as f:
        for line in f:
            s = line.strip()
            if s.startswith('['):
                on = s in ('[SyncTrack]', '[ExpertSingle]')
            if on:
                keep.append(s)
    return keep


def is_single(o):
    return len(set(o['lanes'])) == 1


def fast_mask(t):
    n, keep, i = len(t), np.zeros(len(t), bool), 0
    runs = []
    while i < n:
        j = i
        while j + 1 < n and t[j + 1] - t[j] <= FAST_GAP + 1e-9:
            j += 1
        if j - i + 1 >= FAST_N:
            keep[i:j + 1] = True
            runs.append((i, j))
        i = j + 1
    return keep, runs


def stats(ons, tick_of=None, forced=None):
    """Every part-A measure of one chart's Expert guitar onsets (score.py's onsets)."""
    n = len(ons)
    t = np.array([o['t'] for o in ons])
    single = [is_single(o) for o in ons]
    op = [(-1 in o['lanes']) for o in ons]
    run = best = 0
    for x in op:
        run = run + 1 if x else 0
        best = max(best, run)
    rep = [i for i in range(1, n) if single[i] and single[i - 1] and set(ons[i]['lanes']) == set(ons[i - 1]['lanes'])]
    fm, fruns = fast_mask(t)
    nf = int(fm.sum())
    span = float(t[-1] - t[0]) if n > 1 else 0.0
    fast_time = sum(float(t[j] - t[i]) for i, j in fruns)
    # shapes (measure.py part 1)
    shp = [frozenset(o['lanes']) for o in ons]
    runs = []
    for s in shp:
        if runs and runs[-1][0] == s:
            runs[-1][1] += 1
        else:
            runs.append([s, 1])
    ch16 = sum(r[1] for r in runs if r[1] >= RUN16 and len(r[0]) > 1)
    st = [S.played_state(o) for o in ons]
    out = {'onsets': n,
           'chord_share': r3(sum(not x for x in single) / n),
           'open_share': r3(sum(op) / n), 'open_longest_run': best,
           'repeat_share': r3(len(rep) / n),
           'fast_onsets': nf, 'fast_repeat_share': r3(sum(1 for i in rep if fm[i]) / nf) if nf else None,
           'sustain_share': r3(sum(o['len_ticks'] > 0 for o in ons) / n),
           'hopo_share': r3(st.count('hopo') / n), 'tap_share': r3(st.count('tap') / n),
           'peak_1s': S.density_peak(t, 1.0)[0],
           'fast_time_share': r3(fast_time / span) if span else None,
           'changes_per_onset': r3((len(runs) - 1) / n),
           'chord_runs16_share': r3(ch16 / n), 'chord_runs16_onsets': ch16}
    if forced is not None:
        fh = fs = 0
        for o, s in zip(ons, st):
            if tick_of[round(o['t'], 9)] in forced:
                fh += s == 'hopo'
                fs += s == 'strum'
        out['forced_hopo_share'] = r3(fh / n)
        out['forced_strum_share'] = r3(fs / n)
    return out


def take_stats(folder):
    sc = S.scan(folder)
    notes = S.tracks_by_key(sc)[KEY]
    shift = S.chart_delay_ms(sc)[0]
    ons = S.onsets(notes, shift, 'guitar')
    tick_of = {}
    for nn in notes:
        tick_of.setdefault(round((nn['ms'] + shift) / 1000.0, 9), nn['tick'])
    forced, _ = forced_ticks(os.path.join(folder, 'notes.chart'))
    return stats(ons, tick_of, forced)


MEASURES = ['onsets', 'ratio_to_primary', 'chord_share', 'open_share', 'open_longest_run', 'repeat_share',
            'fast_repeat_share', 'sustain_share', 'forced_hopo_share', 'forced_strum_share', 'tap_share', 'hopo_share',
            'peak_1s', 'fast_time_share', 'changes_per_onset', 'chord_runs16_share']


def mean(xs):
    xs = [x for x in xs if x is not None]
    return float(np.mean(xs)) if xs else None


def boot(d, n=10000, seed=7):
    d = np.array([x for x in d if x is not None], float)
    if not len(d):
        return None
    rng = np.random.default_rng(seed)
    m = d[rng.integers(0, len(d), (n, len(d)))].mean(axis=1)
    return {'mean': r3(d.mean()), 'lo': r3(np.percentile(m, 2.5)), 'hi': r3(np.percentile(m, 97.5)), 'n': int(len(d))}


res = {}
for label, st_, hsong, kept, m7, gpu in SONGS:
    print(label, flush=True)
    song = {'set': st_, 'humans': {}, 'gpu': {}, 'cpu': {}, 'identical_notes': {}}
    prim = None
    for hname, hdir in human_folders(hsong):
        rsc = S.scan(os.path.join(hdir, 'ref'))
        rtr = S.tracks_by_key(rsc)
        if KEY not in rtr:
            continue
        h = stats(S.onsets(rtr[KEY], S.chart_delay_ms(rsc)[0], 'guitar'))
        if hname == 'primary':
            prim = h['onsets']
        song['humans'][hname] = h
    for seed in SEEDS:
        g = os.path.join(gpu, 'seed_%d' % seed)
        c = os.path.join(kept, 'guitar', 'seed_%d' % seed) if seed == 20260609 else os.path.join(m7, 'seed_%d' % seed)
        song['gpu'][str(seed)] = take_stats(g)
        song['cpu'][str(seed)] = take_stats(c)
        song['identical_notes'][str(seed)] = notes_section(os.path.join(g, 'notes.chart')) == notes_section(os.path.join(c, 'notes.chart'))
    for grp in ('humans', 'gpu', 'cpu'):
        for v in song[grp].values():
            v['ratio_to_primary'] = r3(v['onsets'] / prim) if prim else None
    agg = {}
    for m in MEASURES:
        hv = [v.get(m) for v in song['humans'].values() if v.get(m) is not None]
        agg[m] = {'gpu': r3(mean(v.get(m) for v in song['gpu'].values())),
                  'cpu': r3(mean(v.get(m) for v in song['cpu'].values())),
                  'gpu_kept': song['gpu']['20260609'].get(m), 'cpu_kept': song['cpu']['20260609'].get(m),
                  'human_mean': r3(mean(hv)), 'human_min': r3(min(hv)) if hv else None, 'human_max': r3(max(hv)) if hv else None}
        g, c = agg[m]['gpu'], agg[m]['cpu']
        agg[m]['gpu_minus_cpu'] = r3(g - c) if g is not None and c is not None else None
    song['per_song'] = agg
    song['n_humans'] = len(song['humans'])
    res[label] = song

pooled = {}
GROUPS = {'all23': [s[0] for s in SONGS], 'no_refs17': [s[0] for s in SONGS if s[1] != 'refs'],
          'refs6': [s[0] for s in SONGS if s[1] == 'refs']}
for gname, labs in GROUPS.items():
    pooled[gname] = {}
    for m in MEASURES:
        ps = [res[l]['per_song'][m] for l in labs]
        pooled[gname][m] = {'gpu': r3(mean(p['gpu'] for p in ps)), 'cpu': r3(mean(p['cpu'] for p in ps)),
                            'human': r3(mean(p['human_mean'] for p in ps)),
                            'gpu_minus_cpu': boot([p['gpu_minus_cpu'] for p in ps]),
                            'gpu_minus_human': boot([(p['gpu'] - p['human_mean']) if p['gpu'] is not None and p['human_mean'] is not None else None for p in ps]),
                            'cpu_minus_human': boot([(p['cpu'] - p['human_mean']) if p['cpu'] is not None and p['human_mean'] is not None else None for p in ps])}
ident = {l: sum(res[l]['identical_notes'].values()) for l in res}
json.dump({'songs': res, 'pooled': pooled, 'identical_notes_takes_per_song': ident,
           'notes': 'whole charts, Expert guitar; per song: mean of 4 takes (GPU: zip; CPU: kept 20260609 + m7-takes 101/202/303); '
                    'human: mean/min/max over the song\'s charts; bootstrap over songs, 10000, seed 7'},
          open(OUT, 'w'), indent=1)
print('identical notes (of 4 seeds) per song:', ident)
for m in MEASURES:
    p = pooled['all23'][m]
    b = p['gpu_minus_cpu']
    print('%-20s gpu %s cpu %s human %s | gpu-cpu %s [%s, %s]' % (m, p['gpu'], p['cpu'], p['human'], b['mean'], b['lo'], b['hi']))
