"""intake.py: M8-02's intake. Reads the unpacked zip (takes/*/seed_*/take.json, summary.json; takes/takes.jsonl;
takes/<set>/set.json), the dev machine's set20.json + stress/songs.json (ids sorted, in process) and each label's
input.wav (SHA-256). Writes intake.json (labels only, floats to 3 decimals); prints a per-label table.
Usage: python3 -I intake.py <zip/gpu_results> <$DEV> <out.json>"""
import hashlib, json, os, sys
Z, DEV, OUT = sys.argv[1:4]
T = os.path.join(Z, 'takes')
REFS = ["all_the_small_things", "creep", "drunk_drivers", "kimochi_warui", "lucretia", "take_me_out"]
STRESS = ["break", "pm2", "sooth", "troop"]
SEEDS = (20260609, 101, 202, 303)
r3 = lambda x: None if x is None else round(float(x), 3)

def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()

# the 20-song set on this machine, computed as takes.py does
listed = json.load(open(os.path.join(DEV, 'eval-set20', 'set20.json')))
listed = listed['songs'] if isinstance(listed, dict) else listed
built = {s.get('id'): s.get('duration_s') for s in json.load(open(os.path.join(DEV, 'eval-set20', 'stress', 'songs.json')))}
ids = sorted(s['id'] for s in listed)
lab = {i: 's%02d' % k for k, i in enumerate(ids, 1)}
songs_py = sorted(built)   # eval/m7/C/songs.py's order
assert songs_py == ids, 'songs.py ids differ from set20.json ids'
dev_set = {lab[s['id']]: {'slot': s.get('slot'), 'charts': s.get('charts'), 'duration_s': r3(built.get(s['id']))} for s in listed}
zip_set = {s['label']: {'slot': s.get('slot'), 'charts': s.get('charts'), 'duration_s': r3(s.get('duration_s'))}
           for s in json.load(open(os.path.join(T, 'set20', 'set.json')))}
set_diff = {k: {'zip': zip_set.get(k), 'dev': dev_set.get(k)} for k in sorted(set(dev_set) | set(zip_set))
            if zip_set.get(k) != dev_set.get(k)}
# stress set.json too (ids are labels there)
sl = json.load(open(os.path.join(DEV, 'eval', 'stress', 'songs.json')))
sl = sl['songs'] if isinstance(sl, dict) else sl
dev_st = {s['id']: r3(s.get('duration_s')) for s in sl}
zip_st = {s['label']: r3(s.get('duration_s')) for s in json.load(open(os.path.join(T, 'stress', 'set.json')))}
stress_diff = {k: [zip_st.get(k), dev_st.get(k)] for k in STRESS if zip_st.get(k) != dev_st.get(k)}

rec = {}
for l in open(os.path.join(T, 'takes.jsonl')):
    d = json.loads(l)
    if d.get('event') == 'take':
        rec[(d['label'] if d['set'] != 'set20' else d['label'], d['seed'])] = d
starts = [{'set': d['set'], 'device': d.get('device'), 'seeds': d.get('seeds')} for d in map(json.loads, open(os.path.join(T, 'takes.jsonl'))) if d.get('event') == 'start']

LABELS = [(s, 'refs', os.path.join(T, s), os.path.join(DEV, 'eval/refs', s, 'input.wav')) for s in REFS + ['test_song']]
LABELS += [(s, 'stress', os.path.join(T, 'stress', s), os.path.join(DEV, 'eval/stress', s, 'input.wav')) for s in STRESS]
inv = {v: k for k, v in lab.items()}
LABELS += [(l, 'set20', os.path.join(T, 'set20', l), os.path.join(DEV, 'eval-set20/stress', inv[l], 'input.wav')) for l in sorted(inv)]
rows, flagged = [], {}
for label, st, folder, wav in LABELS:
    dsha = sha(wav) if os.path.isfile(wav) else None
    length = dev_set.get(label, {}).get('duration_s') if st == 'set20' else None
    for seed in SEEDS:
        tf = os.path.join(folder, 'seed_%d' % seed)
        r = {'label': label, 'set': st, 'seed': seed, 'present': os.path.isfile(os.path.join(tf, 'notes.chart'))}
        if os.path.isfile(os.path.join(tf, 'take.json')):
            tj = json.load(open(os.path.join(tf, 'take.json')))
            sj = json.load(open(os.path.join(tf, 'summary.json')))
            run = sj['runs'][-1]
            r.update({'input_match': tj.get('inputSha256') == dsha, 'seed_ok': tj.get('seed') == seed == sj.get('seed'),
                      'device': (run.get('devices') or {}).get('transcriber'), 'n_runs': len(sj['runs']),
                      'tokens': run.get('nTokens'), 'beats': run.get('nBeats'), 'wall_s': r3(run.get('wallSeconds')),
                      'gen_s': r3(run.get('generationSeconds')), 'audio_s': r3(run.get('audioDuration')),
                      'status_engine': run.get('status'), 'song_ini': os.path.isfile(os.path.join(tf, 'song.ini')),
                      'stitched': 'stitch' in sj})
        k = rec.get((label, seed))
        r['status'] = k.get('status') if k else None
        r['cut_short'] = k.get('cut_short') if k else None
        r['rec_seconds'] = r3(k.get('seconds')) if k else None
        r['reused'] = k.get('reused') if k else None
        rows.append(r)
    mine = [r for r in rows if r['label'] == label]
    why = []
    if any(not r.get('input_match') for r in mine): why.append('input mismatch')
    if any(r.get('device') != 'cuda' for r in mine): why.append('not cuda')
    if sum(r['present'] and r['status'] in ('made', 'cached') for r in mine) < 4: why.append('fewer than 4 takes')
    if why: flagged[label] = why
json.dump({'set20_set_json_diff': set_diff, 'stress_set_json_diff': stress_diff, 'starts': starts,
           'takes': rows, 'left_out_of_4take_arms': flagged}, open(OUT, 'w'), indent=1)
print('set20 set.json diffs:', set_diff or 'none', '| stress:', stress_diff or 'none')
print('starts:', starts)
for r in rows:
    print(r['label'], r['seed'], r['status'], r.get('device'), 'in=%s' % r.get('input_match'), 'seed=%s' % r.get('seed_ok'),
          'tok', r.get('tokens'), 'beats', r.get('beats'), 'wall', r.get('wall_s'), 'gen', r.get('gen_s'), 'audio', r.get('audio_s'),
          'cut', r['cut_short'], 'runs', r.get('n_runs'), 'stitch', r.get('stitched'), 'ini', r.get('song_ini'), 'reused', r['reused'], r.get('status_engine'))
print('left out:', flagged)
