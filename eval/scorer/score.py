#!/usr/bin/env python3
"""Score a candidate Clone Hero chart folder against a human reference chart.

usage:
  python score.py --ref <eval/refs/ID> --cand <candidate song folder> --input <audio file the tool was given> --out <json>

What it does
  1. Alignment. The candidate's audio (every audio file in its folder except crowd/preview, summed) is
     cross-correlated against <ref>/input.wav in ~9 one-second windows taken at the loudest spots
     (FFT normalised cross-correlation over +-max_shift s, parabolic peak fit); the median lag is used.
     lag > 0  means a sound at input.wav time t is at time t+lag in the candidate's audio.
     If the folder has no usable audio (none, silent, or < 5 s), lag = 0 and the output says so.
     The chart's own delay is applied too: song.ini `delay` (ms, higher = later notes) if non-zero,
     otherwise the .chart [Song] Offset (s); this is how YARG / scan-chart read them.
        note time in input.wav timeline = scan-chart msTime + delay - lag
  2. Both charts are parsed with scan_notes.cjs (scan-chart 8.0.1, the parser Chorus Encore uses, given the
     song.ini chart modifiers as Clone Hero would).
  3. Metrics for every (instrument, difficulty) in guitar/bass/drums that has notes in both charts, restricted
     to the time span the reference chart covers (first ref note .. last ref note end, +-100 ms):
       onset P/R/F1 at +-50 and +-100 ms (one-to-one matching by time, a chord = one onset),
       note density (onsets/s) and ratio cand/ref, chord share, HOPO share, tap share, sustain share,
       lane-direction agreement (sign of lane change) on consecutive matched onset pairs and exact-lane agreement
       on matched onsets (both with the +-100 ms matching), and for drums per-pad F1 at +-50 ms and
       cymbal-vs-tom agreement on matched yellow/blue/green hits.
     Tempo map: quarter-note beat times of both tempo maps over the ref span, beat F1 at +-70 ms and the median
     absolute error from each ref beat to the nearest candidate beat (plus an octave-tolerant F1 for information).
     Candidate scan-chart playable flag and issue counts.
  4. Writes JSON to --out and prints a one-line summary.
No lyrics, vocals or section names are read into the output.
"""
import argparse, json, os, subprocess, sys
from collections import Counter
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
SCAN = os.path.join(HERE, 'scan_notes.cjs')
AUDIO_EXT = ('.ogg', '.opus', '.mp3', '.wav', '.flac', '.m4a')
SKIP_AUDIO = ('crowd', 'preview')
SR = 22050
INSTRUMENTS = ('guitar', 'bass', 'drums')
DIFFS = ('expert', 'hard', 'medium', 'easy')
GUITAR_LANE = {'open': -1, 'green': 0, 'red': 1, 'yellow': 2, 'blue': 3, 'orange': 4}
DRUM_LANE = {'kick': 0, 'redDrum': 1, 'yellowDrum': 2, 'blueDrum': 3, 'greenDrum': 4}
PAD_NAME = {0: 'kick', 1: 'red', 2: 'yellow', 3: 'blue', 4: 'green'}
SPAN_MARGIN = 0.100
BEAT_TOL = 0.070


# ----------------------------------------------------------------------------------------------- io helpers
def scan(folder):
    p = subprocess.run(['node', SCAN, folder], capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError('scan_notes.cjs failed on %s: %s' % (folder, p.stderr[-2000:]))
    return json.loads(p.stdout)


def has_chart(folder):
    try:
        return any(f.lower().endswith(('.chart', '.mid')) for f in os.listdir(folder)
                   if os.path.isfile(os.path.join(folder, f)))
    except OSError:
        return False


def find_chart_folder(cand):
    """The candidate folder itself, or the (first, sorted) sub-folder up to 3 levels down holding a chart."""
    if has_chart(cand):
        return cand, []
    found = []
    base = cand.rstrip('/').count('/')
    for root, dirs, _ in os.walk(cand):
        dirs.sort()
        if root.rstrip('/').count('/') - base > 3:
            dirs[:] = []
            continue
        if has_chart(root):
            found.append(root)
    if not found:
        raise SystemExit('no .chart/.mid under %s' % cand)
    warn = [] if len(found) == 1 else ['several chart folders under --cand; used %s' % found[0]]
    return found[0], warn


def audio_files(folder):
    out = []
    for f in sorted(os.listdir(folder)):
        p = os.path.join(folder, f)
        if os.path.isfile(p) and f.lower().endswith(AUDIO_EXT) and os.path.splitext(f)[0].lower() not in SKIP_AUDIO:
            out.append(f)
    return out


def decode(path, sr=SR):
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-nostdin', '-i', path, '-vn', '-ac', '1', '-ar', str(sr),
                          '-f', 'f32le', '-'], capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.float32).astype(np.float64)


def load_mix(folder, files):
    sigs = [decode(os.path.join(folder, f)) for f in files]
    n = max(len(s) for s in sigs)
    mix = np.zeros(n)
    for s in sigs:
        mix[:len(s)] += s
    return mix


# ----------------------------------------------------------------------------------------------- alignment
def _movsum(x, w):
    c = np.concatenate([[0.0], np.cumsum(x)])
    return c[w:] - c[:-w]


def align(ref, cand, sr=SR, n_win=9, win_s=1.0, max_shift_s=30.0):
    """Lag (s) of cand relative to ref: a sound at ref time t is at cand time t + lag."""
    W = int(win_s * sr)
    S = int(max_shift_s * sr)
    hop = W // 4
    nfr = (len(ref) - W) // hop
    if nfr < 1:
        return None
    rms = np.array([np.sqrt(np.mean(ref[i * hop:i * hop + W] ** 2)) for i in range(nfr)])
    order = np.argsort(-rms)
    min_sep = max(5.0, len(ref) / sr / (n_win + 6)) * sr
    starts = []
    for i in order:
        s = i * hop
        if all(abs(s - t) >= min_sep for t in starts):
            starts.append(s)
        if len(starts) == n_win:
            break
    wins = []
    floor = 1e-4 * float(np.mean(cand ** 2)) * W     # local energy below -40 dB of the candidate's mean = no match
    for t0 in sorted(starts):
        r = ref[t0:t0 + W]
        lo = t0 - S
        seg = np.zeros(W + 2 * S)
        a, b = max(0, lo), min(len(cand), t0 + W + S)
        if b > a:
            seg[a - lo:b - lo] = cand[a:b]
        n = 1 << int(np.ceil(np.log2(len(seg) + W)))
        cc = np.fft.irfft(np.fft.rfft(seg, n) * np.conj(np.fft.rfft(r, n)), n)[:len(seg) - W + 1]
        le = _movsum(seg ** 2, W)
        den = np.sqrt(np.sum(r ** 2) * np.maximum(le, 1e-20))
        ncc = cc / den
        ncc[(le < floor) | (np.abs(ncc) > 1.01)] = 0      # silent stretches / numerical blow-ups
        k = int(np.argmax(ncc))
        d = 0.0
        if 0 < k < len(ncc) - 1:
            y0, y1, y2 = ncc[k - 1], ncc[k], ncc[k + 1]
            q = y0 - 2 * y1 + y2
            if q != 0:
                d = 0.5 * (y0 - y2) / q
        wins.append({'ref_time_s': round(t0 / sr, 3), 'lag_ms': round((k + d - S) / sr * 1000, 3),
                     'peak_ncc': round(float(ncc[k]), 4)})
    good = [w for w in wins if w['peak_ncc'] >= 0.3]
    use = good if len(good) >= 3 else wins
    lags = np.array([w['lag_ms'] for w in use])
    lag = float(np.median(lags))
    mad = float(np.median(np.abs(lags - lag)))
    return {'lag_ms': round(lag, 3), 'windows': wins, 'windows_used': len(use),
            'windows_peak_ge_0.3': len(good), 'lag_mad_ms': round(mad, 3)}


# ----------------------------------------------------------------------------------------------- chart helpers
def chart_delay_ms(sc):
    d = sc.get('delay') or 0
    if d:
        return float(d), 'song.ini delay'
    o = sc.get('chart_offset') or 0
    return float(o), ('chart Offset' if o else 'none')


def tracks_by_key(sc):
    out = {}
    for t in sc.get('tracks') or []:
        if t['instrument'] in INSTRUMENTS and t['difficulty'] in DIFFS and t['notes']:
            out[(t['instrument'], t['difficulty'])] = t['notes']
    return out


def onsets(notes, shift_ms, instrument):
    """Group notes by tick -> list of onset dicts sorted by time (s, in input.wav timeline)."""
    lanes_map = DRUM_LANE if instrument == 'drums' else GUITAR_LANE
    g = {}
    for n in notes:
        o = g.setdefault(n['tick'], {'t': (n['ms'] + shift_ms) / 1000.0, 'lanes': [], 'flags': set(),
                                    'len_ticks': 0, 'pads': []})
        lane = lanes_map.get(n['type'])
        if lane is None:
            continue
        o['lanes'].append(lane)
        o['flags'].update(n['flags'])
        o['len_ticks'] = max(o['len_ticks'], n.get('length') or 0)
        if instrument == 'drums':
            o['pads'].append((lane, 'cymbal' in n['flags']))
    out = [o for o in g.values() if o['lanes']]
    out.sort(key=lambda o: o['t'])
    return out


def match(r, c, tol):
    """Maximum one-to-one matching of sorted times r, c within +-tol (greedy is optimal for equal windows)."""
    pairs = []
    j, n = 0, len(c)
    for i, t in enumerate(r):
        while j < n and c[j] < t - tol:
            j += 1
        if j < n and c[j] <= t + tol:
            pairs.append((i, j))
            j += 1
    return pairs


def prf(n_match, n_ref, n_cand):
    p = n_match / n_cand if n_cand else 0.0
    r = n_match / n_ref if n_ref else 0.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    return {'precision': round(p, 4), 'recall': round(r, 4), 'f1': round(f, 4), 'matched': n_match,
            'n_ref': n_ref, 'n_cand': n_cand}


def share(ons, pred):
    return round(sum(1 for o in ons if pred(o)) / len(ons), 4) if ons else None


def ratio(a, b):
    return round(a / b, 4) if (a is not None and b) else None


def n_cand_eff(pairs, ct, span):
    """Candidate events that count for precision: matched ones, plus unmatched ones inside the ref span
    (unmatched events in the +-tolerance margin just outside the span are not counted)."""
    mj = {j for _, j in pairs}
    return len(mj) + sum(1 for j, t in enumerate(ct) if j not in mj and span[0] <= t <= span[1])


def track_metrics(ro, co, instrument, span, ref_pro, cand_pro):
    rt = np.array([o['t'] for o in ro])
    ct = np.array([o['t'] for o in co])
    span_dur = span[1] - span[0]
    m = {}
    for tol in (0.050, 0.100):
        pairs = match(rt, ct, tol)
        m['onset_%dms' % int(tol * 1000)] = prf(len(pairs), len(rt), n_cand_eff(pairs, ct, span))
    pairs = match(rt, ct, 0.100)
    if pairs:
        err = np.array([(ct[j] - rt[i]) * 1000 for i, j in pairs])
        m['timing_err_ms_matched100'] = {'median': round(float(np.median(err)), 2),
                                         'median_abs': round(float(np.median(np.abs(err))), 2)}
    co_in = [o for o in co if span[0] <= o['t'] <= span[1]]
    m['n_notes'] = {'ref': int(sum(len(o['lanes']) for o in ro)), 'cand': int(sum(len(o['lanes']) for o in co_in))}
    dr, dc = len(ro) / span_dur, len(co_in) / span_dur
    m['density_onsets_per_s'] = {'ref': round(dr, 4), 'cand': round(dc, 4), 'ratio_cand_ref': ratio(dc, dr)}
    m['chord_share'] = {'ref': share(ro, lambda o: len(set(o['lanes'])) > 1),
                        'cand': share(co, lambda o: len(set(o['lanes'])) > 1)}
    if instrument != 'drums':
        m['hopo_share'] = {'ref': share(ro, lambda o: 'hopo' in o['flags']),
                           'cand': share(co, lambda o: 'hopo' in o['flags'])}
        m['tap_share'] = {'ref': share(ro, lambda o: 'tap' in o['flags']),
                          'cand': share(co, lambda o: 'tap' in o['flags'])}
        m['sustain_share'] = {'ref': share(ro, lambda o: o['len_ticks'] > 0),
                              'cand': share(co, lambda o: o['len_ticks'] > 0)}
    # lanes, on the +-100 ms matching
    exact = [frozenset(ro[i]['lanes']) == frozenset(co[j]['lanes']) for i, j in pairs]
    m['exact_lane_agreement'] = {'value': round(float(np.mean(exact)), 4) if exact else None, 'n_matched': len(exact)}
    agree, n = 0, 0
    conf = Counter()
    for (i0, j0), (i1, j1) in zip(pairs, pairs[1:]):
        if i1 != i0 + 1:
            continue
        sr_ = int(np.sign(np.mean(ro[i1]['lanes']) - np.mean(ro[i0]['lanes'])))
        sc_ = int(np.sign(np.mean(co[j1]['lanes']) - np.mean(co[j0]['lanes'])))
        n += 1
        agree += sr_ == sc_
        conf['%+d/%+d' % (sr_, sc_)] += 1
    same = sum(v for k, v in conf.items() if k.startswith('+0/'))
    m['lane_direction_agreement'] = {'value': round(agree / n, 4) if n else None, 'n_pairs': n,
                                     'trivial_always_same_would_get': round(same / n, 4) if n else None,
                                     'confusion_ref/cand': dict(sorted(conf.items()))}
    if instrument == 'drums':
        pads = {}
        cym_all = {'agree': 0, 'n': 0}
        for lane in range(5):
            rp = np.array([o['t'] for o in ro for (l, _) in o['pads'] if l == lane])
            cp = np.array([o['t'] for o in co for (l, _) in o['pads'] if l == lane])
            rc = [cy for o in ro for (l, cy) in o['pads'] if l == lane]
            cc = [cy for o in co for (l, cy) in o['pads'] if l == lane]
            pp = match(rp, cp, 0.050)
            e = prf(len(pp), len(rp), n_cand_eff(pp, cp, span))
            if lane >= 2:
                ag = sum(rc[i] == cc[j] for i, j in pp)
                e['cymbal_tom_agreement'] = round(ag / len(pp), 4) if pp else None
                e['ref_cymbal_share'] = round(float(np.mean(rc)), 4) if rc else None
                e['cand_cymbal_share'] = round(float(np.mean(cc)), 4) if cc else None
                cym_all['agree'] += ag
                cym_all['n'] += len(pp)
            pads[PAD_NAME[lane]] = e
        m['pads_50ms'] = pads
        m['cymbal_tom_agreement_ybg'] = {
            'value': round(cym_all['agree'] / cym_all['n'], 4) if cym_all['n'] else None, 'n_matched': cym_all['n'],
            'ref_pro_drums': ref_pro, 'cand_pro_drums': cand_pro,
            'note': None if cand_pro else 'candidate is not pro drums: all its Y/B/G hits count as toms'}
    return m


def beat_times(sc, t0, t1, shift_ms):
    """Every quarter-note tick's time (s, input.wav timeline) within [t0, t1]."""
    res = sc.get('resolution')
    tempos = sc.get('tempos') or []
    if not res or not tempos:
        return np.array([])
    tempos = sorted(tempos, key=lambda x: x['tick'])
    out = []
    k = 0
    ti = 0
    while True:
        tick = k * res
        while ti + 1 < len(tempos) and tempos[ti + 1]['tick'] <= tick:
            ti += 1
        tp = tempos[ti]
        ms = tp['msTime'] + (tick - tp['tick']) * 60000.0 / (tp['beatsPerMinute'] * res)
        t = (ms + shift_ms) / 1000.0
        if t > t1:
            break
        if t >= t0:
            out.append(t)
        k += 1
        if k > 200000:
            break
    return np.array(out)


def tempo_metrics(rsc, csc, span, ref_shift, cand_shift):
    rb = beat_times(rsc, span[0], span[1], ref_shift)
    cb = beat_times(csc, span[0] - BEAT_TOL, span[1] + BEAT_TOL, cand_shift)
    out = {'n_ref_beats': int(len(rb)), 'n_cand_beats': int(len(cb)),
           'cand_tempo_markers': len(csc.get('tempos') or []), 'ref_tempo_markers': len(rsc.get('tempos') or [])}
    if not len(rb) or not len(cb):
        out['beat_f1_70ms'] = None
        return out
    pairs = match(rb, cb, BEAT_TOL)
    out['n_cand_beats'] = n_cand_eff(pairs, cb, span)
    out['beat_f1_70ms'] = prf(len(pairs), len(rb), out['n_cand_beats'])
    idx = np.clip(np.searchsorted(cb, rb), 1, len(cb) - 1) if len(cb) > 1 else np.zeros(len(rb), int)
    near = np.minimum(np.abs(cb[idx] - rb), np.abs(cb[idx - 1] - rb)) if len(cb) > 1 else np.abs(cb[0] - rb)
    out['beat_median_abs_err_ms'] = round(float(np.median(near)) * 1000, 2)
    out['beat_count_ratio_cand_ref'] = ratio(out['n_cand_beats'], len(rb))
    # for information: best F1 if the candidate's grid is at double or half the ref tempo
    variants = {'same': rb}
    if len(rb) > 1:
        mid = (rb[:-1] + rb[1:]) / 2
        variants['ref_double'] = np.sort(np.concatenate([rb, mid]))
        variants['ref_half_even'] = rb[0::2]
        variants['ref_half_odd'] = rb[1::2]
    best = max(((k, prf(len(match(v, cb, BEAT_TOL)), len(v), n_cand_eff(match(v, cb, BEAT_TOL), cb, span))['f1'])
                for k, v in variants.items()),
               key=lambda x: x[1])
    out['beat_f1_70ms_octave_tolerant'] = {'f1': best[1], 'variant': best[0]}
    return out


def issue_summary(sc):
    ci = sc.get('chartIssues') or []
    return {'playable': sc.get('playable'), 'n_chart_issues': len(ci),
            'chart_issues_by_type': dict(Counter(i.get('noteIssue') for i in ci)),
            'folder_issues': [i.get('folderIssue') for i in sc.get('folderIssues') or []],
            'metadata_issues': [i.get('metadataIssue') for i in sc.get('metadataIssues') or []],
            'parse_error': sc.get('parseError')}


# ----------------------------------------------------------------------------------------------- main
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--ref', required=True, help='eval/refs/<id> folder (input.wav + ref/)')
    ap.add_argument('--cand', required=True, help='candidate song folder (or a folder containing one)')
    ap.add_argument('--input', required=True, help='the audio file the tool was given')
    ap.add_argument('--out', required=True)
    ap.add_argument('--max-shift', type=float, default=30.0, help='alignment search range, s (default 30)')
    a = ap.parse_args(argv)
    warns = []
    ref_dir = os.path.abspath(a.ref)
    ref_wav = os.path.join(ref_dir, 'input.wav')
    cand_dir, w = find_chart_folder(os.path.abspath(a.cand))
    warns += w

    rsc = scan(os.path.join(ref_dir, 'ref'))
    csc = scan(cand_dir)
    if csc.get('parseError'):
        warns.append('candidate chart failed to parse: %s' % csc['parseError'])

    # ---- alignment
    x = decode(ref_wav)
    al = {'cand_audio_files': audio_files(cand_dir)}
    lag_ms = 0.0
    if al['cand_audio_files']:
        c = load_mix(cand_dir, al['cand_audio_files'])
        if len(c) < 5 * SR or np.sqrt(np.mean(c ** 2)) < 1e-5:
            al['method'] = 'none: candidate audio is silent or shorter than 5 s, lag assumed 0'
            warns.append(al['method'])
        else:
            r = align(x, c, max_shift_s=a.max_shift)
            al.update(r)
            al['method'] = 'fft xcorr of 1 s windows vs input.wav'
            lag_ms = r['lag_ms']
            if r['windows_peak_ge_0.3'] < 3:
                warns.append('weak audio alignment: only %d/%d windows with ncc >= 0.3'
                             % (r['windows_peak_ge_0.3'], len(r['windows'])))
            if r['lag_mad_ms'] > 2.0:
                warns.append('alignment windows disagree (MAD %.1f ms)' % r['lag_mad_ms'])
    else:
        al['method'] = 'none: candidate folder has no audio, lag assumed 0'
        warns.append(al['method'])
    al['lag_ms'] = lag_ms
    inp = os.path.abspath(a.input)
    if os.path.realpath(inp) != os.path.realpath(ref_wav) and os.path.exists(inp):
        r2 = align(x, decode(inp), max_shift_s=min(a.max_shift, 5.0))
        al['input_vs_inputwav_lag_ms'] = r2 and r2['lag_ms']
    else:
        al['input_vs_inputwav_lag_ms'] = 0.0 if os.path.exists(inp) else None
    rdel, rsrc = chart_delay_ms(rsc)
    cdel, csrc = chart_delay_ms(csc)
    al['ref_delay_ms'] = rdel
    al['ref_delay_source'] = rsrc
    al['cand_delay_ms'] = cdel
    al['cand_delay_source'] = csrc
    ref_shift = rdel
    cand_shift = cdel - lag_ms
    al['cand_total_shift_ms'] = round(cand_shift, 3)

    # ---- tracks
    rtr, ctr = tracks_by_key(rsc), tracks_by_key(csc)
    starts, ends = [], []
    for (ins, dif), notes in rtr.items():
        starts.append(min(n['ms'] for n in notes))
        ends.append(max(n['ms'] + (n.get('msLength') or 0) for n in notes))
    span = ((min(starts) + ref_shift) / 1000.0, (max(ends) + ref_shift) / 1000.0)
    lo, hi = span[0] - SPAN_MARGIN, span[1] + SPAN_MARGIN
    ref_pro = rsc.get('drumType') == 1
    cand_pro = csc.get('drumType') == 1
    if 2 in (rsc.get('drumType'), csc.get('drumType')):
        warns.append('five-lane drums present: lanes compared as kick/red/yellow/blue/green as scan-chart types them')
    tracks = {}
    for ins in INSTRUMENTS:
        for dif in DIFFS:
            k = (ins, dif)
            if k not in rtr or k not in ctr:
                continue
            ro = onsets(rtr[k], ref_shift, ins)
            co = [o for o in onsets(ctr[k], cand_shift, ins) if lo <= o['t'] <= hi]
            n_out = len(onsets(ctr[k], cand_shift, ins)) - len(co)
            tm = track_metrics(ro, co, ins, span, ref_pro, cand_pro)
            tm['cand_onsets_outside_ref_span_dropped'] = n_out
            tracks['%s/%s' % k] = tm
    missing = sorted('%s/%s' % k for k in rtr if k not in ctr)
    extra = sorted('%s/%s' % k for k in ctr if k not in rtr)
    tempo = tempo_metrics(rsc, csc, span, ref_shift, cand_shift)

    out = {
        'ref': ref_dir, 'cand': cand_dir, 'cand_arg': os.path.abspath(a.cand), 'input': inp,
        'ref_span_s': [round(span[0], 3), round(span[1], 3)],
        'alignment': al,
        'tracks': tracks,
        'ref_tracks_missing_in_cand': missing,
        'cand_tracks_not_in_ref': extra,
        'tempo_map': tempo,
        'cand_scan': issue_summary(csc),
        'cand_drum_type': csc.get('drumType'), 'ref_drum_type': rsc.get('drumType'),
        'cand_chart_file': csc.get('chartFile'),
        'notes': ['drum onsets include 2x-kick (doubleKick) notes',
                  'lane metrics use the +-100 ms onset matching; chords use the mean lane for direction',
                  'guitar lanes: open=-1, green..orange=0..4; drum lanes: kick, red, yellow, blue, green = 0..4'],
        'warnings': warns,
    }
    parts = ['%s vs %s' % (os.path.basename(ref_dir), os.path.basename(cand_dir.rstrip('/')))]
    parts.append('lag %+.1f ms%s' % (lag_ms, '' if al.get('windows') else ' (assumed)'))
    shown = set()
    for key in sorted(tracks, key=lambda s: (INSTRUMENTS.index(s.split('/')[0]), DIFFS.index(s.split('/')[1]))):
        t = tracks[key]
        if key.split('/')[0] in shown:      # one line per instrument: its hardest scored difficulty
            continue
        shown.add(key.split('/')[0])
        parts.append('%s F1@50 %.3f @100 %.3f dens x%s' % (key, t['onset_50ms']['f1'], t['onset_100ms']['f1'],
                                                         t['density_onsets_per_s']['ratio_cand_ref']))
    if tempo.get('beat_f1_70ms'):
        parts.append('beatF1 %.3f err %.1f ms' % (tempo['beat_f1_70ms']['f1'], tempo['beat_median_abs_err_ms']))
    cs = out['cand_scan']
    parts.append('playable %s, %d chart issues' % (cs['playable'], cs['n_chart_issues']))
    if missing:
        parts.append('missing %s' % ','.join(missing))
    out['summary'] = ' | '.join(parts)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)) or '.', exist_ok=True)
    with open(a.out, 'w') as f:
        json.dump(out, f, indent=1, default=float)
    print(out['summary'])
    return out


if __name__ == '__main__':
    main()
