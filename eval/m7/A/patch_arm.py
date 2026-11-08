# patch_arm.py CHECKOUT ARM: reads the checkout's pipeline.py and quantize.py, writes part A's patch for ARM (base: none).
import sys, re
from pathlib import Path
code, arm = Path(sys.argv[1]), sys.argv[2]
cfg = {"base": None, "A1": ("source", 0.300), "A2": ("natural", 0.400), "A3": ("forced", 0.500)}[arm]
if cfg:
    hopo, cap = cfg
    p = code / "songcharter/pipeline.py"; t = p.read_text()
    old = '"instrument": "guitar", "source": str(runs[0].path), "hopo": "forced"}'
    assert t.count(old) == 1; p.write_text(t.replace(old, old.replace('"hopo": "forced"', f'"hopo": "{hopo}"')))
    q = code / "songcharter/quantize.py"; t = q.read_text()
    old = ("    return (end - tick >= SUSTAIN_MIN_BEATS[difficulty] * tm.resolution\n"
           "            and tm.tick_to_sec(end) - tm.tick_to_sec(tick) >= SUSTAIN_MIN_S - 1e-9)\n")
    new = ("    secs = tm.tick_to_sec(end) - tm.tick_to_sec(tick)\n"
           "    beats_ok = end - tick >= SUSTAIN_MIN_BEATS[difficulty] * tm.resolution\n"
           f"    if difficulty in ('expert', 'hard'):\n        beats_ok = beats_ok or secs >= {cap} - 1e-9  # M7-01 arm {arm}\n"
           "    return beats_ok and secs >= SUSTAIN_MIN_S - 1e-9\n")
    assert t.count(old) == 1; q.write_text(t.replace(old, new))
print("patched", arm, cfg)
