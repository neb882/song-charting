"""audiolag.py LABEL...: score.py's align (fft xcorr of 1 s windows) of each alt chart's input.wav against the primary's
input.wav, for analyze.py's coarse alt shift; writes <shm>/m8t/<label>.lag.json (ms per chart). Prints one line per song."""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import *
sys.path.insert(0, str(ORCH / "eval/scorer")); sys.path.insert(0, str(ORCH))
import score as SC
from eval import stress as S
for label in sys.argv[1:]:
    st, sid, kept, cl = SONGS[label]
    song = next(s for s in S.built_songs(REFDIR[st]) if s["id"] == sid)
    prim = SC.decode(str(Path(song["folder"]) / "input.wav"))
    out = {"primary": 0.0}
    for a in song.get("alts") or []:
        if not S.scorable(Path(a["folder"])):
            continue
        x = SC.decode(str(Path(a["folder"]) / "input.wav"))
        out[a["label"]] = SC.align(x, prim, max_shift_s=30.0)["lag_ms"]
    (SHM / f"{label}.lag.json").write_text(json.dumps(out))
    print(label, {k: round(v, 1) for k, v in out.items()}, flush=True)
