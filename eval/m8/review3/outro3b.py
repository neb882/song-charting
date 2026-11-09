"""outro3b.py: for each trimmed Expert guitar onset (outro3.json's report data) the floor (dB under the stem's P95) at which the
onset's own window (-0.05, +0.20 s) first reaches the stem level: need_db = P95 - max(levels in window). A floor above need_db
would keep the onset only if the span's edge rule also reached it (span = last frame within floor of P95 + window): reported as
the floor at which the span end first passes the onset: end_need_db = P95 - max level over all frames at or after the onset's
window start. His sooth: the stress sooth's stem at the mapped time (stress input s = (u + pad - a0)/(1+b)). Prints and writes outro3b.json."""
import sys, json
sys.path.insert(0, '<scratch>')
from lib import *
from songcharter import assemble as AS, audio as A
KEPT = {'refs': G / 'work', 'stress': G / 'stress-work', 'set20': G / 'set20-work'}
def stem(kept, name):
    for d in sorted((kept / 'stems').glob('*/')):
        if (d / 'info.json').is_file(): return d / f'{name}.wav'
def need(levels, times):
    p95 = float(np.percentile(levels, 95)); fs = AS.LEVEL_FRAME_S; w = AS.SILENT_WINDOW; out = []
    for t in times:
        i, j = max(0, int((t + w[0]) / fs)), int((t + w[1]) / fs) + 1
        seg = levels[i:j]; tail = levels[i:]
        out.append((round(p95 - float(seg.max()), 1) if len(seg) else None, round(p95 - float(tail.max()), 1) if len(tail) else None))
    return out
res = {}
for lab, st, sid in songs():
    rep = rj(RUN_[st] / sid / 'report.json') if False else rj(RUN[st] / sid / 'report.json')
    tr = rep['parts']['guitar'].get('trimmed'); 
    if not tr or not tr['onsets'].get('expert'): continue
    lv = AS.frame_levels(*A.read_wav(stem(KEPT[st] / sid, tr['stem'])))
    ends = [t for t in tr['onsets']['expert'] if t >= tr['kept'][1]]
    if ends: res[lab] = {'n': len(ends), 'need_window_db': need(lv, ends)[:3], 'min_end_need_db': min(x[1] for x in need(lv, ends))}
A4 = rj(HERE / 'align4.json'); rep = rj(Path('<shm>/soothgpu/chart/report.json')); pad = rep['lead_in']['pad_seconds']
lv = AS.frame_levels(*A.read_wav(stem(G / 'stress-work/sooth', 'guitar')))
ends = [t for t in rep['parts']['guitar']['trimmed']['onsets']['expert']]
nd = need(lv, [(u + pad - A4['a0']) / (1 + A4['b']) for u in ends])
res['his_sooth'] = {'n': len(ends), 'need_db_per_onset': nd}
for k, v in res.items(): print(k, json.dumps(v)[:400])
json.dump(res, open('<scratch>/outro3b.json', 'w'), indent=1)
