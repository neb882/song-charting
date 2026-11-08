"""gen_one.py LABEL: generates seeds 101/202/303 of one song's Expert guitar (autochart.generate, CPU) from its kept
folder's decode.wav into $SONGCHARTER_GOLDEN/m7-takes/<id>/seed_<seed>/, engine scratch in <shm>/m7/C-work/<label>
(deleted after; its size printed). Prints one line per take: label, seed, seconds, tokens, cut_short, sha check."""
import json, os, shutil, subprocess, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from songs import SONGS, TAKES, SEEDS
from songcharter.engines.autochart import find_install, generate
label = sys.argv[1]
_, sid, kept = SONGS[label]
install = find_install(os.environ["SONGCHARTER_AUTOCHART"])
work = f"<shm>/m7/C-work/{label}"
out = TAKES / sid
kept_sha = json.loads((kept / "guitar/seed_20260609/autochart_run/summary.json").read_text())["inputSha256"]
try:
    for seed in SEEDS:
        t0 = time.time()
        take = generate(install, kept / "decode.wav", out, (seed,), device="cpu", work=work)[0]
        sha = take.summary.get("inputSha256")
        ogg = take.chart.parent / "song.ogg"
        if ogg.exists():
            ogg.unlink()
        r = take.summary["runs"][0]
        print(f"{label} seed {seed}: {'cached' if take.cached else f'{take.seconds:.0f} s'} tokens {r.get('nTokens')} "
              f"cut_short {take.cut_short} sha_ok {sha == kept_sha} wall {time.time() - t0:.0f}", flush=True)
finally:
    if os.path.isdir(work):
        size = subprocess.run(["du", "-sm", work], capture_output=True, text=True).stdout.split()[0]
        print(f"{label} scratch {size} MB", flush=True)
        shutil.rmtree(work)
