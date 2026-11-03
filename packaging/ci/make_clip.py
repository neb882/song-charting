#!/usr/bin/env python3
"""make_clip.py: a synthetic rock clip for CI, made by code from nothing, so no recording (and no one's copyrighted
audio) is ever needed: drums, bass, distorted power chords from bar 3 and a hummed line from bar 5, 120 BPM, 4/4,
I-V-vi-IV in E.

    python packaging/ci/make_clip.py OUT.wav [SECONDS]      # default 30

Writes a 44.1-kHz stereo 16-bit WAV, peak-normalized to 0.8. Deterministic (seeded noise): the same SECONDS give the
same bytes. run-hooks.sh writes it to $CI_CLIP before the first Linux hook. It needs numpy and soundfile, which
songcharter itself depends on.

In the planning run, `songcharter chart` charted the 30-s clip end to end on the CPU in 144 s: gate ok, scan-chart
playable with 0 chart issues, and Expert onsets guitar 23, bass 120, drums 119 (check_gate.py checks a folder that
way).
"""
import sys

import numpy as np
import soundfile as sf

if len(sys.argv) not in (2, 3):
    sys.exit("usage: make_clip.py OUT.wav [SECONDS]")
SR, BPM = 44100, 120.0
seconds = float(sys.argv[2]) if len(sys.argv) > 2 else 30.0
if not seconds >= 2:                         # one bar at least: a clip with no bar is silence
    sys.exit(f"make_clip.py: SECONDS must be 2 or more, not {sys.argv[2]}")
n = int(SR * seconds)
beat = 60.0 / BPM
rng = np.random.default_rng(20261103)
mix_l, mix_r = np.zeros(n), np.zeros(n)


def add(sig, t0, gain=1.0, pan=0.0):
    i = int(t0 * SR)
    if i >= n:
        return
    sig = sig[: n - i] * gain
    mix_l[i:i + len(sig)] += sig * (1 - max(pan, 0))
    mix_r[i:i + len(sig)] += sig * (1 + min(pan, 0))


def env(length, decay):
    t = np.arange(int(length * SR)) / SR
    return np.exp(-t / decay), t


def kick():
    e, t = env(0.35, 0.08)
    f = 50 + 70 * np.exp(-t / 0.03)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * e


def snare():
    e, t = env(0.25, 0.06)
    noise = rng.standard_normal(len(t))
    return (0.6 * noise + 0.5 * np.sin(2 * np.pi * 190 * t)) * e


def hat():
    e, t = env(0.06, 0.012)
    noise = np.diff(rng.standard_normal(len(t) + 1))   # crude high-pass
    return noise * e


def saw(freq, length, decay=0.5):
    e, t = env(length, decay)
    return (2 * ((t * freq) % 1.0) - 1) * e


# I-V-vi-IV in E, a bar each: roots (bass octave)
roots = [82.41, 61.74, 69.30, 55.00]
bars = int(seconds / (4 * beat))
for b in range(bars):
    t_bar = b * 4 * beat
    root = roots[b % 4]
    for k in range(8):                       # eighths
        t = t_bar + k * beat / 2
        add(hat(), t, 0.25, 0.3)
        add(saw(root, beat / 2 * 0.9, 0.15), t, 0.35, 0.0)          # bass
        if b >= 2:                                                  # guitar enters at bar 3: power chords
            ch = sum(saw(root * 2 * r, beat / 2 * 0.95, 0.3) for r in (1.0, 1.498, 2.0))
            add(np.tanh(3 * ch) * 0.5, t, 0.4, -0.3)
    for k in (0, 2):
        add(kick(), t_bar + k * beat, 0.9)
    for k in (1, 3):
        add(snare(), t_bar + k * beat, 0.6)
    if b >= 4 and b % 2 == 0:                # a hummed line every other bar from bar 5
        tt = np.arange(int(4 * beat * SR)) / SR
        f = root * 4 * (1 + 0.01 * np.sin(2 * np.pi * 5 * tt))
        add(0.15 * np.sin(2 * np.pi * np.cumsum(f) / SR) * np.minimum(1, tt * 4), t_bar, 1.0, 0.1)
y = np.stack([mix_l, mix_r], axis=1)
y *= 0.8 / np.max(np.abs(y))
sf.write(sys.argv[1], y.astype(np.float32), SR, subtype="PCM_16")
print(sys.argv[1], f"{seconds:.1f} s")
