"""a_c_run.py W OUTJSON (allin1's Python, one W per process): W=0 is the whole song (the runner's own path), W>0 cuts the whole song's spectrogram into windows
of W s overlapping by 30 s, runs the model on each window, stitches the frame-level logits (beat, downbeat, section, function) by a linear crossfade over each
overlap, then allin1's own postprocessing (postprocess_metrical_structure, postprocess_functional_structure, estimate_tempo_from_beats).
Reads <shm>/m8/ac/{payload.npy,job.json} (a_c_prep.py) and songcharter/engines/allin1_runner.py (spectrogram, _model, peak_rss_mb) at the v0.4.0 checkout.
Writes OUTJSON: beats, downbeats, bpm, segments, seconds, VmHWM, window count; threads 2, seed 0 as the kept runs. Prints one line of numbers."""
import sys, json, time, importlib.util, importlib
import numpy as np, torch
W = float(sys.argv[1]); OUT = sys.argv[2]
spec_ = importlib.util.spec_from_file_location("allin1_runner", "<shm>/m8/code-cpu/songcharter/engines/allin1_runner.py")
R = importlib.util.module_from_spec(spec_); spec_.loader.exec_module(R)
job = json.load(open("<shm>/m8/ac/job.json")); pay = np.load("<shm>/m8/ac/payload.npy")
torch.set_num_threads(2); torch.manual_seed(0)
module, dist = R.load_package()
t0 = time.perf_counter()
spec = R.spectrogram(module, dict(zip(R.STEMS, pay))); del pay
t_spec = time.perf_counter()-t0
hw_spec = R.peak_rss_mb()
post = importlib.import_module(module+".postprocessing"); typ = importlib.import_module(module+".typings")
model = R._model(module, job["checkpoints"], "cpu"); cfg = model.cfg; fps = int(cfg.fps)
hw_model = R.peak_rss_mb(); T = spec.shape[1]
def fwd(a, b):
    with torch.no_grad():
        o = model(torch.from_numpy(np.ascontiguousarray(spec[:, a:b])).unsqueeze(0))
    return {k: getattr(o, k).detach().clone() for k in ("logits_beat", "logits_downbeat", "logits_section", "logits_function")}
t1 = time.perf_counter()
if W == 0:
    L = fwd(0, T); nwin = 1
else:
    win = int(round(W*fps)); ov = 30*fps; step = win-ov
    starts = []; s = 0
    while True:
        starts.append(s)
        if s+win >= T: break
        s += step
    nwin = len(starts); L = None; prev_end = 0
    for s in starts:
        e = min(s+win, T); o = fwd(s, e)
        if L is None:
            L = {k: torch.zeros(*v.shape[:-1], T) for k, v in o.items()}
            wsum = torch.zeros(T)
        for k, v in o.items():
            assert v.shape[-1] == e-s, (k, v.shape, e-s)
        # weight: ramp up over the overlap with the previous window, ramp down over the overlap with the next; 1 elsewhere
        w = torch.ones(e-s)
        if s > 0:
            n = min(prev_end-s, e-s)
            if n > 0: w[:n] = torch.linspace(0, 1, n+2)[1:-1]   # strictly inside (0,1)
        nxt = [x for x in starts if x > s]
        if nxt:
            n = min(e-nxt[0], e-s)
            if n > 0: w[(e-s)-n:] = torch.minimum(w[(e-s)-n:], torch.linspace(1, 0, n+2)[1:-1])
        for k, v in o.items(): L[k][..., s:e] += v*w
        wsum[s:e] += w; prev_end = e
        del o
    for k in L: L[k] = L[k]/wsum
t_inf = time.perf_counter()-t1
hw_inf = R.peak_rss_mb()
out = typ.AllInOneOutput(**L)
with torch.no_grad():
    t2 = time.perf_counter(); met = post.postprocess_metrical_structure(out, cfg); t_met = time.perf_counter()-t2; hw_met = R.peak_rss_mb()
    seg = post.postprocess_functional_structure(out, cfg)
bpm = post.estimate_tempo_from_beats(met["beats"])
res = {"W": W, "windows": nwin, "frames": T, "beats": [float(b) for b in met["beats"]], "downbeats": [float(b) for b in met["downbeats"]],
       "bpm": None if bpm is None else float(bpm), "segments": [[float(s.start), float(s.end), str(s.label)] for s in seg],
       "seconds": {"spectrogram": round(t_spec, 2), "inference": round(t_inf, 2), "metrical_post": round(t_met, 2), "total": round(time.perf_counter()-t0, 2)}, "vmhwm_mb": R.peak_rss_mb(), "vmhwm_after_spectrogram_mb": hw_spec, "vmhwm_after_model_load_mb": hw_model, "vmhwm_after_inference_mb": hw_inf, "vmhwm_after_metrical_mb": hw_met}
json.dump(res, open(OUT, "w"))
print(W, nwin, T, res["seconds"], res["vmhwm_mb"], len(res["beats"]), len(res["segments"]), flush=True)
