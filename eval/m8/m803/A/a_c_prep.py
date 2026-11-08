"""a_c_prep.py LABEL (project venv, code v0.4.0 first on sys.path): reads the kept folder's six stem WAVs, builds songcharter.engines.sections.allin1_input
(the runner's stdin payload, int16 (4, n)) and the checkpoint paths for the model the kept folder's engine.json records; writes <shm>/m8/ac/payload.npy and
<shm>/m8/ac/job.json (checkpoints, samples, kept segments.json path). One song at a time: a_c_clean.sh removes them. Prints numbers only."""
import sys, json
from pathlib import Path
import numpy as np
sys.path[:0] = ["<shm>/m8/code-cpu", str(Path(__file__).parent)]
from songs_map import SONGS
from songcharter import audio as A
from songcharter.engines import sections as SE
label = sys.argv[1]; kept = SONGS[label][1]
eng = json.loads((kept/"sections/engine.json").read_text())
d = next(p for p in sorted((kept/"stems").glob("*/")) if (p/"info.json").is_file())
stems = {n: A.read_wav(d/f"{n}.wav")[0] for n in eng["input"]["stems"]}
pay = SE.allin1_input(stems); del stems
out = Path("<shm>/m8/ac"); out.mkdir(parents=True, exist_ok=True)
np.save(out/"payload.npy", pay)
model = eng["allin1"]["model"]
cps = [str(p) for p in SE.checkpoint_paths(model, None)]
json.dump({"label": label, "checkpoints": cps, "samples": int(pay.shape[1]), "kept_segments": str(kept/"sections/segments.json"), "model": model},
          open(out/"job.json", "w"))
print(label, pay.shape, model)
