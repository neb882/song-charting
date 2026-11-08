"""M7-09 measurement, one song per run: `measure.py <label> <out.json>` (label: sooth, s02, s04, ntl, owner_sim).
Reads: the kept folder's assemble.json (stems, parts, sections paths only; never its metadata), its stems (drums,
guitar or other), the guitar take's notes (ntl only), allin1's beats/downbeats (sections/segments.json), today's
report.json and score JSON (alignment, span, stretches), and the human charts' beat lines through
eval/scorer/score.py's scan (via M7-01 B's common.py; tempo maps only). owner_sim: the stress set's sooth audio with
the owner's file's halved beats (its notes.chart SyncTrack and report.json lead-in) standing in for allin1's beats.
Builds in process (beatgrid/assemble functions, no engine): the first grid, today's halved grid and candidates a0/a1
(every other first-grid beat, refined like today's), b (start line vs tracker by TRACKER_MARGIN), c (allin1's curve
faded to the line where drums give no evidence). Prints one progress line per grid (numbers only); writes JSON."""
import inspect, json, math, sys, time
from pathlib import Path
import numpy as np

REPO = Path('<wt>/orch')
BDIR = Path('<scratchpad>/m7/m7-01/B')
sys.path[:0] = [str(REPO), str(REPO / 'eval' / 'scorer'), str(BDIR)]
import common as C  # noqa: E402
C.CACHE = Path('<shm>/m709/cache'); C.CACHE.mkdir(parents=True, exist_ok=True)
S = C.S
from songcharter import assemble as AS, beatgrid as BG, audio as A  # noqa: E402

# ---- the variant beat_grid: today's source with two optional insertions -------------------------------------------
src = inspect.getsource(BG.beat_grid)
anchor_b = "    stats[\"start\"][\"tracker_confident_share\"]"
ins_b = '''    if start is not None and _VARIANT.get("v") == "b":
        _k = np.arange(len(tracker), dtype=np.float64)
        _a, _b, _ = robust_line(_k, tracker, np.ones(len(tracker)))
        _first = _a - np.floor(_a / _b) * _b
        line = _first + np.arange(int(np.floor((dur - _first) / _b)) + 1) * _b
        line_ev = local_beats(f, line)
        use_tracker = bool(trk_ev.confident.mean() >= line_ev.confident.mean() + TRACKER_MARGIN)
        stats["start"]["line_confident_share"] = round(float(line_ev.confident.mean()), 4)
        stats["start"]["line_bpm"] = round(60.0 / _b, 3)
'''
anchor_c = "        line = a + b * k\n    else:"
ins_c = '''        line = a + b * k
        if _VARIANT.get("v") == "c":
            _, _sup = loess(np.zeros(len(base)), conf, half_width=8, iterations=1)
            _d, _ = _limit_tempo_steps(line, (base - line) * np.clip(_sup / 0.5, 0, 1), MAX_TEMPO_STEP)
            base = line + _d
            ev = local_beats(f, base)
            conf = ev.confidence * ev.confident
    else:'''
assert src.count(anchor_b) == 1 and src.count(anchor_c) == 1
src = src.replace(anchor_b, ins_b + anchor_b).replace(anchor_c, ins_c).replace("def beat_grid(", "def beat_grid_v(", 1)
NS = dict(BG.__dict__); NS["_VARIANT"] = VARIANT = {}
exec(compile(src, "beat_grid_v", "exec"), NS)
beat_grid_v = NS["beat_grid_v"]

OFF = -BG.ONSET_TO_BEAT_MS / 1000.0  # beat time + OFF = onset time
TOL = S.BEAT_TOL
LO, HI = BG.BPM_RANGE
label, OUT = sys.argv[1], Path(sys.argv[2])
STRESS_SOOTH = Path('$DEV/golden/stress-work/sooth')
NTL = Path('<shm>/ntl/work')
OWNER = Path('$DEV/gpucheck030/cpu2/song')
NTL_CHART = Path('$DEV/gpucheck030/cpu4/song')


def r3(x):
    if isinstance(x, float):
        return round(x, 3) if math.isfinite(x) else None
    if isinstance(x, dict):
        return {k: r3(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [r3(v) for v in x]
    if isinstance(x, np.generic):
        return r3(x.item())
    return x


def chart_beats(folder):
    """Our chart's quarter-note times (s of the chart) from its [SyncTrack] (B lines) and Resolution only."""
    txt = (folder / 'notes.chart').read_text(errors='replace').splitlines()
    res, tempos, sec = 192, [], None
    for ln in txt:
        s = ln.strip()
        if s.startswith('['):
            sec = s; continue
        if sec == '[Song]' and s.startswith('Resolution'):
            res = int(s.split('=')[1])
        if sec == '[SyncTrack]' and '= B ' in s:
            t, v = s.split('= B ')
            tempos.append((int(t), int(v) / 1000.0))
    tempos.sort()
    last_tick = tempos[-1][0] + 400 * res
    out, ms, k = [], 0.0, 0
    ti = 0; t_ms = 0.0; prev_tick = 0
    tick = 0
    while tick <= last_tick:
        while ti + 1 < len(tempos) and tempos[ti + 1][0] <= tick:
            t_ms += (tempos[ti + 1][0] - prev_tick) * 60000.0 / (tempos[ti][1] * res); prev_tick = tempos[ti + 1][0]; ti += 1
        out.append((t_ms + (tick - prev_tick) * 60000.0 / (tempos[ti][1] * res)) / 1000.0)
        tick += res
    return np.array(out), res


# ---- inputs -----------------------------------------------------------------------------------------------------
kept = {'sooth': STRESS_SOOTH, 'owner_sim': STRESS_SOOTH, 'ntl': NTL}.get(label)
humans = None
if label in ('s02', 's04', 'sooth', 'owner_sim'):
    lab = 'sooth' if label == 'owner_sim' else label
    st, sid = next((st, sid) for l, st, sid in C.songs() if l == lab)
    P = C.paths(st, sid)
    kept = P['kept']
    rep = C.report(st, sid)
    osc = C.rj(P['score'])
    humans = C.build(lab, st, sid)
    T = rep['lead_in']['pad_seconds'] + osc['alignment']['cand_total_shift_ms'] / 1000.0  # audio -> scored timeline
    span_primary = osc['ref_span_s']
else:
    rep = json.loads((NTL_CHART / 'report.json').read_text())
    T = 0.0
cfg = AS.load_config(kept / 'assemble.json')
sr = AS.SAMPLE_RATE
mix_dur = rep['audio']['duration']
stems = {n: A.read_wav(p)[0] for n, p in cfg.stems.items() if n in ('drums', 'guitar', 'other')}
src_name = 'drums'
sec = next(n for n in AS.STEMS_FOR['guitar'] if n in stems)
grid_audio, second = stems[src_name], stems[sec]
features = BG.onset_features(grid_audio, sr)
gfeat = BG.onset_features(second, sr)
g_onsets = BG.onset_times(gfeat)
allin1 = AS._read_allin1_beats(cfg)
allin1_db = AS._read_allin1_beats(cfg, downbeats=True)
duration = mix_dur
t0 = time.time()

first = BG.beat_grid(grid_audio, sr, duration=duration, bpm=cfg.bpm, first_beat=cfg.first_beat, mode=cfg.grid_mode,
                     secondary=second, features=features)


def second_pass(bpm, bpm_range, start=None, half_beat=True, v=None):
    VARIANT.clear(); VARIANT['v'] = v
    return beat_grid_v(grid_audio, sr, duration=duration, bpm=bpm, mode=cfg.grid_mode, secondary=second,
                       features=features, bpm_range=bpm_range, half_beat=half_beat, keep_line=True, start=start)


owner = None
if label == 'owner_sim':
    ob, _ = chart_beats(OWNER)
    orep = json.loads((OWNER / 'report.json').read_text())
    ob = ob - orep['lead_in']['pad_seconds']
    ob = ob[(ob >= 0) & (ob <= orep['audio']['duration'])]
    # align the owner's file to this audio: the offset that matches most of today's halved beats under 480 s
    today0 = second_pass(first.bpm / 2, (LO / 2, HI / 2), start=np.unique(allin1) + OFF, half_beat=False)
    ref = today0.beats[today0.beats < 480]
    offs = np.arange(-12, 12, 0.005)
    hits = [len(S.match(ref, np.sort(ob + o), TOL)) for o in offs]
    off = float(offs[int(np.argmax(hits))])
    allin1 = ob + off
    allin1 = allin1[(allin1 >= 0) & (allin1 <= duration)]
    owner = {'offset_s': off, 'matched_under_480s': int(max(hits)), 'n_today_beats_under_480s': int(len(ref)),
             'owner_duration': orep['audio']['duration'], 'owner_bpm_min': orep['tempo_map']['bpm_min'],
             'owner_bpm_max': orep['tempo_map']['bpm_max'], 'owner_drift_ms': orep['grid']['drift_ms'],
             'owner_tempo_check': orep['grid']['stats'].get('tempo_check'),
             'tail_start_audio': float(orep['audio']['duration'] - 28.0 + off)}
    # the owner's own tail tempo from its grid
    tb = ob[ob >= orep['audio']['duration'] - 28.0]
    owner['owner_tail_bpm_median'] = float(60 / np.median(np.diff(tb)))

lo2, hi2 = LO / 2, HI / 2
grids, errors = {}, {}


def run(name, start, v=None):
    try:
        g = second_pass(first.bpm / 2, (lo2, hi2), start=start, half_beat=False, v=v)
        grids[name] = BG.with_downbeats(g, allin1_db if label != 'owner_sim' else None)
    except Exception as e:  # noqa: BLE001  a candidate that fails is a result
        errors[name] = f'{type(e).__name__}: {e}'
    print(label, name, 'ok' if name in grids else errors[name][:80], round(time.time() - t0), flush=True)


run('today', np.unique(allin1) + OFF)
a_par = {}
for p in (0, 1):
    cand = first.beats[p::2]
    a_par[p] = int(len(S.match(np.sort(allin1), cand, TOL)))
    run(f'a{p}', cand + OFF)
run('b', np.unique(allin1) + OFF, v='b')
run('c', np.unique(allin1) + OFF, v='c')
a_pick = max(a_par, key=a_par.get)

# ---- measures ---------------------------------------------------------------------------------------------------
def local_bpm(b):
    return 240.0 / (b[4:] - b[:-4]) if len(b) > 5 else np.array([np.nan])


def phase_R(beats_onset, ons, t0=-1, t1=1e9):
    o = ons[(ons >= t0) & (ons <= t1)]
    j = np.searchsorted(beats_onset, o) - 1
    ok = (j >= 0) & (j < len(beats_onset) - 1)
    j = j[ok]
    u = j + (o[ok] - beats_onset[j]) / (beats_onset[j + 1] - beats_onset[j])
    if not len(u):
        return None
    return {'n': int(len(u)), 'R8': float(abs(np.mean(np.exp(2j * np.pi * 2 * u)))),
            'R16': float(abs(np.mean(np.exp(2j * np.pi * 4 * u))))}


def prf_f1(ref, cand, span=None):
    ref, cand = np.sort(ref), np.sort(cand)
    if not len(ref):
        return None
    pairs = S.match(ref, cand, TOL)
    nc = S.n_cand_eff(pairs, cand, span) if span else len(cand)
    return S.prf(len(pairs), len(ref), nc)['f1']


hum = {}
if humans:
    for k, h in humans['humans'].items():
        if not h.get('tempos'):
            continue
        sp = [o[0] for p in h['parts'].values() for o in p['onsets']]
        if not sp:
            continue
        span = tuple(span_primary) if k == 'primary' else (min(sp) - 0.1, max(sp) + 0.1)
        sc = {'resolution': h['res'], 'tempos': h['tempos'], 'timeSignatures': h['timeSignatures']}
        hum[k] = dict(span=span, beats=S.beat_times(sc, span[0], span[1], h['shift_ms']),
                      down=S.downbeat_times(sc, span[0], span[1], h['shift_ms']))
strs = [s for s in rep['grid']['stats'].get('secondary', {}).get('stretches', []) if s[2] >= 16 and s[3] < 0.5] \
    if label != 'owner_sim' else []

# ntl: the guitar take's onsets rounded to each grid's nearest 16th (48 ticks): off the 8th grid when on an odd one
ntl_notes = None
if label == 'ntl':
    part = next(p for p in cfg.parts if p.instrument == 'guitar')
    song = AS._import(part)
    ntl_notes = np.array(sorted({n.time for n in song.parts[(part.from_instrument, 'expert')].notes}))


def off8(beats, notes, t0, t1):
    n = notes[(notes >= t0) & (notes < t1)]
    j = np.clip(np.searchsorted(beats, n) - 1, 0, len(beats) - 2)
    u = j + (n - beats[j]) / (beats[j + 1] - beats[j])
    slot = np.round(u * 4).astype(int)  # the nearest 16th of the halved beat (an 8th at the first grid's level)
    return int(np.sum(slot % 2 != 0)), int(len(n))


res = {'label': label, 'first': {'bpm': first.bpm, 'mode': first.mode,
                                 'confident_share': first.stats['evidence']['confident_share'],
                                 'start_grid': first.stats['start']['grid'], 'drift_ms': first.stats['drift_ms'],
                                 'tempo_check': first.stats['tempo_check'], 'n_beats': int(len(first.beats))},
       'allin1_bpm': float(60 / np.median(np.diff(np.unique(allin1)))), 'a_parity_allin1_matches': a_par,
       'a_pick': f'a{a_pick}', 'errors': errors, 'T': T, 'duration': duration,
       'report_today': {'bpm_median': rep['grid']['bpm_median'], 'beats': rep['grid']['beats'],
                        'octave': rep['grid']['octave'], 'drift_ms': rep['grid']['drift_ms'],
                        'tempo_map': [rep['tempo_map']['bpm_min'], rep['tempo_map']['bpm_max']],
                        'stretches': strs}, 'owner': owner, 'grids': {}}
if humans:
    oc = humans['ours']
    ours_chart = S.beat_times({'resolution': oc['res'], 'tempos': oc['tempos']}, -10, duration + 20, oc['shift_ms'])
    if 'today' in grids:
        tb = grids['today'].beats + T
        j = np.clip(np.searchsorted(ours_chart, tb), 1, len(ours_chart) - 1)
        d = np.minimum(np.abs(ours_chart[j] - tb), np.abs(ours_chart[j - 1] - tb))
        res['calibration'] = {'today_vs_chart_median_ms': float(np.median(d) * 1000),
                              'today_vs_chart_p95_ms': float(np.percentile(d, 95) * 1000),
                              'n_chart_beats_in_audio': int(np.sum((ours_chart >= T) & (ours_chart <= T + duration))),
                              'n_today_beats': int(len(tb))}
WIN = []
for name, g in grids.items():
    b = g.beats
    bo = b + OFF
    s1 = first.stats['evidence']['confident_share']; s2 = g.stats['evidence']['confident_share']
    lb = local_bpm(b)
    period = 60.0 / g.bpm
    dbl = np.sort(np.r_[bo, (bo[1:] + bo[:-1]) / 2])
    m = {'n_beats': int(len(b)), 'bpm_median': g.bpm, 'mode': g.mode, 'start_grid': g.stats['start']['grid'],
         'start': {k: v for k, v in g.stats['start'].items() if k not in ('source',)},
         'confident_share': s2, 'evidence_ratio': s2 / s1 if s1 else None,
         'kept_by_guard': bool(s1 and s2 / s1 >= AS.OCTAVE_RULES.evidence_min),
         'bpm_4beat': {'min': float(np.nanmin(lb)), 'p1': float(np.nanpercentile(lb, 1)),
                       'p50': float(np.nanmedian(lb)), 'p99': float(np.nanpercentile(lb, 99)),
                       'max': float(np.nanmax(lb))},
         'drift_ms': g.stats['drift_ms'], 'two_beats_ms': 2000 * period,
         'drift_guard_fires': bool(g.stats['drift_ms']['p95_abs'] > 2000 * period),
         'tempo_check_halved_fold': g.stats['tempo_check'],
         'tempo_check_first_fold': BG.missed_tempo_changes(features, dbl, BG.BPM_RANGE),
         'guitar_phase': {'whole': phase_R(bo, g_onsets), '0-35s': phase_R(bo, g_onsets, 0, 35)},
         'secondary_timed': g.stats.get('secondary', {}).get('beats_timed'),
         'downbeat_phase': g.stats['downbeats']['phase']}
    if label == 'owner_sim':
        t_tail = owner['tail_start_audio']
        tail = b[b >= t_tail]
        m['tail_bpm_median'] = float(60 / np.median(np.diff(tail))) if len(tail) > 2 else None
        m['tail_beats'] = int(len(tail))
        base = grids.get('today')
    if ntl_notes is not None:
        m['off8_19_33'] = off8(b, ntl_notes, 19, 33)
        m['off8_rest'] = [x + y for x, y in zip(off8(b, ntl_notes, 0, 19), off8(b, ntl_notes, 33, 1e9))]
        m['off8_chart_19_33'] = off8(b, ntl_notes, 19 - rep['lead_in']['pad_seconds'], 33 - rep['lead_in']['pad_seconds'])  # 19-33 s of the chart
        # the real path: lead-in, tempo map, the guitar's offset and assemble's quantizer on this grid; then the
        # notes (distinct ticks) off the 96-tick 8th grid, 19-33 s of the chart against the rest
        from songcharter.tempo import TempoMap, plan_lead_in
        lead = plan_lead_in(g.beats, g.downbeats, sr, min_lead=cfg.lead_in, duration=duration)
        tm = TempoMap.from_beats(lead.beats, bars=lead.bars, tolerance=cfg.tempo_tolerance)
        tmo = AS.offset_map(tm, lead.beats, 0.5, cfg.tempo_tolerance)
        applied, _, _ = AS._offset(part, song, tmo, lead.pad_seconds)
        trk, _ = AS._quantize(part, song, tm, lead.pad_seconds, applied, 0.5)['expert']
        ticks = np.array(sorted({n.tick for n in trk.notes}))
        secs = np.asarray(tm.ticks_to_secs(ticks), dtype=float).ravel()
        secs = secs - lead.pad_seconds  # audio time
        if name == 'today':  # the window: ticks 4608-8640 of today's chart (19-33 s of it), in audio time
            WIN.extend(float(x) - lead.pad_seconds for x in np.ravel(tm.ticks_to_secs(np.array([4608, 8640]))))
        win = (secs >= WIN[0]) & (secs < WIN[1])
        q8 = ticks % (tm.resolution // 4) != 0  # off the 48-tick grid: an 8th at the first grid's level
        m['quantized_off8'] = {'window_audio_s': WIN, '19-33s': [int(q8[win].sum()), int(win.sum())], "rest": [int(q8[~win].sum()), int((~win).sum())],
                               'pad_s': lead.pad_seconds, 'offset_ms': applied * 1000,
                               'tempo_map_bpm': [min(t.bpm for t in tm.tempos), max(t.bpm for t in tm.tempos)],
                               'markers': len(tm.tempos)}
    if hum:
        bt = b + T
        dt = b[g.downbeats] + T
        m['beat_f1'] = {k: prf_f1(h['beats'], bt[(bt >= h['span'][0] - TOL) & (bt <= h['span'][1] + TOL)], h['span'])
                        for k, h in hum.items()}
        m['downbeat_f1'] = {k: prf_f1(h['down'], dt[(dt >= h['span'][0] - TOL) & (dt <= h['span'][1] + TOL)],
                                      h['span']) for k, h in hum.items()}
        st_rows = []
        for s in strs:
            a, z = s[0] - OFF + T, s[1] - OFF + T
            row = {'t0': s[0], 't1': s[1], 'beats': s[2]}
            for k, h in hum.items():
                hin = h['beats'][(h['beats'] >= a) & (h['beats'] <= z)]
                row[k] = prf_f1(hin, bt[(bt >= a - TOL) & (bt <= z + TOL)]) if len(hin) else None
            st_rows.append(row)
        m['stretches'] = st_rows
    res['grids'][name] = m
np.savez(str(OUT.with_suffix('.npz')), first=first.beats, allin1=np.unique(allin1),
         **{f'{n}_beats': g.beats for n, g in grids.items()}, **{f'{n}_down': g.downbeats for n, g in grids.items()},
         **({'notes': ntl_notes} if ntl_notes is not None else {}), g_onsets=g_onsets)
OUT.write_text(json.dumps(r3(res), indent=1))
print(label, 'done', round(time.time() - t0), flush=True)
