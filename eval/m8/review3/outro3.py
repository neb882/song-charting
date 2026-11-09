"""outro3.py (part 3): per song (23 + the owner's sooth), the Expert guitar onsets that parts.guitar.trimmed dropped (report.json,
input seconds), the humans' Expert guitar onsets (scan-chart notes through lib; each human chart's frame = input s + pad +
cand_shift), the trimmed onsets' precision (a human onset within 50 ms), and the trim's floor at 40 dB: active_span recomputed
in process on the kept folder's stem (frame_levels at 0.1 s as assemble does; asserted equal to the report's kept span at 30 dB
within 0.011 s) and the trimmed onsets that fall inside the 40 dB span (brought back) with their precision. His sooth: no stem of
his run is kept, so the stress sooth's kept stem is used, its time mapped by align4 (his ogg time = stress input + lag, see
lib.his_map): the 30 dB span from that stem is compared with his report's kept span (a check, not an assert). Writes outro3.json."""
import sys, json
sys.path.insert(0, '<scratch>')
from lib import *
from songcharter import assemble as AS, audio as A
KEPT = {'refs': G / 'work', 'stress': G / 'stress-work', 'set20': G / 'set20-work'}
OUT = '<scratch>/outro3.json'
def kept_stem(kept, name):
    for d in sorted((kept / 'stems').glob('*/')):
        if (d / 'info.json').is_file():
            return d / f'{name}.wav'
def span_levels(path):
    y, sr = A.read_wav(path); return AS.frame_levels(y, sr)
def prec(times, htimes, tol=0.05):
    if not len(times): return None
    ht = np.sort(np.asarray(htimes)); idx = np.clip(np.searchsorted(ht, times), 1, len(ht) - 1)
    d = np.minimum(abs(ht[idx] - times), abs(ht[idx - 1] - times)); return float(np.mean(d <= tol))
def evaluate(lab, rep, charts, levels, to_human_in):
    """to_human_in(in_seconds, chart) -> that time in the chart's frame."""
    tr = rep['parts']['guitar']['trimmed']; kept = tr['kept']; rem = tr['onsets'].get('expert', [])
    s30 = AS.active_span(levels); s40 = AS.active_span(levels, floor_db=40.0)
    row = {'stem': tr['stem'], 'kept30_report': kept, 'span30_here': [round(s30[0], 3), round(s30[1], 3)],
           'span40': [round(s40[0], 3), round(s40[1], 3)], 'n_trimmed': len(rem),
           'trimmed_end': [t for t in rem if t >= kept[1]], 'trimmed_start': [t for t in rem if t < kept[0]]}
    row['n_end'], row['n_start'] = len(row['trimmed_end']), len(row['trimmed_start'])
    row['end_seconds'] = round(row['trimmed_end'][-1] - row['trimmed_end'][0], 2) if row['trimmed_end'] else 0.0
    back = [t for t in rem if s40[0] <= t < s40[1]]; row['back40'] = back; row['n_back40'] = len(back)
    row['back40_end'] = [t for t in back if t >= kept[1]]
    per = []
    for c in charts:
        ho = onsets(scan(c['ref']), 'guitar', c['ref_shift'])
        ht = np.array([o['t'] for o in ho]) if ho else np.array([])
        r = {'k': c['k'], 'human_last': None, 'n_h': len(ht)}
        if len(ht):
            r['human_last_in'] = round(float(ht[-1] - to_human_in(0.0, c)), 3)
            for nm, lst in (('trim_end', row['trimmed_end']), ('trim_start', row['trimmed_start']), ('back40', back), ('back40_end', row['back40_end'])):
                tt = np.array([to_human_in(t, c) for t in lst])
                r[nm + '_prec'] = prec(tt, ht); r[nm + '_hits'] = int(round((r[nm + '_prec'] or 0) * len(tt)))
            r['trim_all_prec'] = prec(np.array([to_human_in(t, c) for t in rem]), ht)
        per.append(r)
    row['charts'] = per
    return row
res = {}
for lab, st, sid in songs():
    e = entry(lab, st, sid); rep = rj(e['ours'] / 'report.json'); pad = rep['lead_in']['pad_seconds']
    tr = rep['parts']['guitar'].get('trimmed')
    if not tr:
        res[lab] = {'no_trim_record': True}; print(lab, 'no trim record'); continue
    levels = span_levels(kept_stem(KEPT[st] / sid, tr['stem']))
    row = evaluate(lab, rep, e['charts'], levels, lambda t, c, pad=pad: t + pad + c['cand_shift'] / 1000.0)
    k, h = row['kept30_report'], row['span30_here']
    assert abs(k[0] - h[0]) < 0.011 and abs(k[1] - h[1]) < 0.011, (lab, k, h)
    res[lab] = row
    print(lab, 'trimmed', row['n_trimmed'], 'end', row['n_end'], 'start', row['n_start'], 'back40', row['n_back40'], flush=True)
# his sooth
rep = rj(Path('<shm>/soothgpu/chart/report.json')); e = entry('sooth', 'stress', 'sooth'); pad_h = rep['lead_in']['pad_seconds']
lv = span_levels(kept_stem(G / 'stress-work/sooth', 'guitar'))
s_pad = rj(G / 'v040-stress/sooth/report.json')['lead_in']['pad_seconds']; A4 = rj(HERE / 'align4.json')
# his input seconds u -> stress input seconds: ogg time = u + pad_h = s_in + a0 + b s_in
to_s_in = lambda u: (u + pad_h - A4['a0']) / (1 + A4['b'])
frm_s_in = lambda s: s * (1 + A4['b']) + A4['a0'] - pad_h      # stress input -> his input
mp = his_map()
tr = rep['parts']['guitar']['trimmed']
lv_his = lv    # levels indexed by stress input time
# span (stress input s) -> his input s; the onsets (his input) -> stress human frame via his_map(chart s = u + pad_h)
def to_human(u, c): return float(mp(u + pad_h)) + c['cand_shift'] / 1000.0
row = evaluate('his_sooth', rep, e['charts'], lv, to_human)
# the spans from the stress stem are in stress input seconds: convert to his input seconds, redo the 40 dB membership in his time
s30, s40 = AS.active_span(lv), AS.active_span(lv, floor_db=40.0)
row['span30_his_time'] = [round(frm_s_in(s30[0]), 3), round(frm_s_in(s30[1]), 3)]; row['span40_his_time'] = [round(frm_s_in(s40[0]), 3), round(frm_s_in(s40[1]), 3)]
rem = rep['parts']['guitar']['trimmed']['onsets']['expert']
back = [t for t in rem if row['span40_his_time'][0] <= t < row['span40_his_time'][1]]
row['back40'], row['n_back40'] = back, len(back); row['back40_end'] = [t for t in back if t >= tr['kept'][1]]
for r in row['charts']:
    c = next(c for c in e['charts'] if c['k'] == r['k']); ht = np.array([o['t'] for o in onsets(scan(c['ref']), 'guitar', c['ref_shift'])])
    for nm, lst in (('back40', back), ('back40_end', row['back40_end'])):
        r[nm + '_prec'] = prec(np.array([to_human(t, c) for t in lst]), ht); r[nm + '_hits'] = int(round((r[nm + '_prec'] or 0) * len(lst)))
res['his_sooth'] = row
print('his_sooth', 'trimmed', row['n_trimmed'], 'end', row['n_end'], 'span30 his time', row['span30_his_time'], 'report kept', tr['kept'], 'back40', row['n_back40'])
def rnd(x):
    if isinstance(x, float): return round(x, 3)
    if isinstance(x, dict): return {k: rnd(v) for k, v in x.items()}
    if isinstance(x, list): return [rnd(v) for v in x]
    return x
json.dump(rnd(res), open(OUT, 'w'), indent=1)
