"""mksongs.py: writes $M8_SHM/m8c/songs.pkl (clib.songs()); prints the labels with a fast run and their stem kind."""
import os, pickle, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import clib
ss = clib.songs()
pickle.dump(ss, open(os.path.join(os.environ['M8_SHM'], 'm8c', 'songs.pkl'), 'wb'))
for s in ss:
    t = np.array([o['t'] for o in s['ours']])
    rid = clib.fast_runs(t)
    if (rid >= 0).any():
        print(s['label'], s['stem_kind'], int((rid >= 0).sum()), len(s['humans']))
print('songs', len(ss))
