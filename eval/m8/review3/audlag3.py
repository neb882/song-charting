"""audlag3.py: the audio lag between the stress set's sooth (our kept folder's decode.wav) and the owner's file (song.ogg of his
CPU chart folder), by the scorer's align (9 windows, normalised cross-correlation); prints per-window lags; writes audlag3.json.
Audio is read only to compute the lag; nothing else is kept."""
import sys, json
sys.path.insert(0, '<wt>/orch/eval/scorer')
import score as S
ref = S.decode('$DEV/golden/stress-work/sooth/decode.wav'); cand = S.decode('$DEV/gpucheck040/sooth/song.ogg')
print('len s', len(ref) / S.SR, len(cand) / S.SR)
r = S.align(ref, cand, n_win=12)
print(json.dumps(r)[:1500]); json.dump(r, open('<scratch>/audlag3.json', 'w'))
