# M8 spike: can a pitch tracker recover the fret contour of fast runs? (2026-11-08)

A measurer, in process on main's CPU charts (v031, gate3-final-stress, set20-main), at our Expert guitar onsets in
fast runs (M7-01's definition: 8 or more onsets each at most 0.125 s apart), matched within 50 ms to consecutive
human notes; trackers on the kept guitar stem: pYIN (70-1400 Hz, the median of voiced frames after the onset), a CQT
peak (36 bins an octave), a harmonic-summed CQT peak; no ML pitch tracker is importable in the shared venv (torchcrepe,
crepe, basic_pitch, penn, torchfcpe, pesto, nnAudio, onnxruntime, tensorflow, essentia and madmom checked), so none
was measured. Only 10 of the 23 songs have a fast run in our chart (pm2, sooth, troop, s01, s02, s04, s06, s07, s10,
s12; no reference).

**Verdict: no tracker clears the bar** (+0.10 direction agreement, CI above 0, on 3 songs). The best, pYIN used only
where it steps a semitone or more, +0.015 [-0.023, +0.056] against the primaries (ours 0.593). Where pYIN does step and
the human moves, its sign is right 0.81 of the time (178 pairs; ours 0.64), but it steps on 2-39 % of pairs (pm2 3 %):
its smoothing and windows longer than 60-125 ms notes, and low voicing on distorted stems. CQT peaks are right 0.59 on
the humans' moves (they jump between harmonics). The humans agree with each other 0.821 (pair-weighted) against our
0.592: a gap of about 0.23 that no tracker closes. Re-laning (one lane per step, clamped) lowers the contour even with
our own directions (-0.046), so the step rule, not the tracker, costs it.

**The premise is weaker on CPU charts than on the owner's GPU chart:** at matched fast-run pairs our "same" share is
0.293 on pm2 (the humans' 0.289); the 86 % same-fret repeats the video review counted were the owner's GPU chart (4
GPU takes). With the open notes (the GPU takes write them, the CPU takes do not, M7-01 A-e), the friend's GPU charts
differ from the CPU charts every M7 measurement used: M8 should measure on GPU takes of the sets (the owner's GPU).

Not tried: an ML tracker (an install outside the shared venv), frame-wise or unsmoothed tracking, a lane-range fit per
run. Scripts: eval/m8/contour/. The measurer's tables follow.

---

| song | stem | fast onsets (runs) | pairs vs primary | human up/down/same | ours up/down/same | ours | pyin | cqt | hs | pyin conf (n; ours same) | cqt conf (n; ours same) | hs conf (n; ours same) | humans (alt vs primary) | clock 0/+25/+50 ms |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| pm2 | guitar | 1553 (56) | 1236 | 0.366/0.345/0.289 | 0.362/0.345/0.293 | 0.589 | 0.589 | 0.461 | 0.437 | 0.487 (226; 0.487) | 0.541 (370; 0.519) | 0.468 (346; 0.5) | 0.856 | 0.614/0.631/0.748 |
| sooth | guitar | 442 (25) | 138 | 0.413/0.406/0.181 | 0.5/0.464/0.036 | 0.457 | 0.5 | 0.464 | 0.399 | 0.69 (29; 0.448) | 0.462 (52; 0.481) | 0.537 (41; 0.488) | 0.605 | 0.689/0.683/0.684 |
| troop | guitar | 1408 (53) | 963 | 0.312/0.307/0.381 | 0.222/0.251/0.526 | 0.582 | 0.563 | 0.457 | 0.538 | 0.633 (395; 0.678) | 0.511 (323; 0.669) | 0.651 (358; 0.712) | 0.826 | 0.62/0.705/0.61 |
| s01 | guitar | 211 (13) | 56 | 0.214/0.268/0.518 | 0.214/0.161/0.625 | 0.643 | 0.536 | 0.482 | 0.518 | 0.565 (23; 0.826) | 0.682 (22; 0.773) | 0.647 (17; 0.824) | 0.5 | 0.726/0.581/0.688 |
| s02 | guitar | 35 (2) | 15 | 0.533/0.467/0.0 | 0.533/0.467/0.0 | 0.333 | 0.467 | 0.2 | 0.667 | 0.2 (5; 0.2) | 0.2 (5; 0.2) | 0.25 (4; 0.25) | 0.5 | 0.817/0.754/0.729 |
| s04 | guitar | 32 (2) | 9 | 0.444/0.556/0.0 | 0.444/0.556/0.0 | 0.778 | 0.778 | 0.333 | 0.444 | 0.714 (7; 0.714) | 0.5 (4; 0.75) | 0.571 (7; 0.714) | 0.0 | 0.728/0.697/0.722 |
| s06 | guitar | 343 (10) | 284 | 0.349/0.644/0.007 | 0.419/0.577/0.004 | 0.694 | 0.704 | 0.623 | 0.739 | 0.791 (43; 0.744) | 0.708 (72; 0.75) | 0.908 (76; 0.737) | 0.712 | 0.773/0.835/0.641 |
| s07 | guitar | 556 (31) | 388 | 0.464/0.477/0.059 | 0.492/0.433/0.075 | 0.495 | 0.497 | 0.441 | 0.392 | 0.553 (85; 0.541) | 0.472 (123; 0.667) | 0.333 (129; 0.62) | 0.729 | 0.583/0.678/0.688 |
| s10 | guitar | 193 (7) | 100 | 0.02/0.07/0.91 | 0.08/0.04/0.88 | 0.84 | 0.74 | 0.55 | 0.57 | 0.702 (84; 0.821) | 0.833 (30; 0.8) | 0.784 (37; 0.757) | 0.426 | 0.568/0.533/0.516 |
| s12 | guitar | 175 (8) | 90 | 0.422/0.433/0.144 | 0.411/0.511/0.078 | 0.522 | 0.378 | 0.333 | 0.333 | 0.056 (18; 0.778) | 0.273 (33; 0.485) | 0.278 (36; 0.528) | 0.455 | 0.667/0.749/0.701 |

**primary** n=10: ours 0.593, humans' ceiling {'mean': 0.561, 'n_songs': 10}
| variant | agreement (fallback ours) | minus ours [CI] | songs >= +0.10 | confident subset: tracker / ours (songs) [diff CI] |
|---|---|---|---|---|
| pyin | 0.575 | -0.018 [-0.066, +0.031] | 1 | 0.551 / 0.631 (10) [-0.080 [-0.252, +0.045]] |
| pyin_conf | 0.562 | -0.031 [-0.071, +0.003] | 0 | 0.539 / 0.624 (10) [-0.085 [-0.256, +0.044]] |
| cqt | 0.434 | -0.159 [-0.240, -0.091] | 0 | 0.434 / 0.593 (10) [-0.159 [-0.240, -0.091]] |
| cqt_conf | 0.559 | -0.034 [-0.059, -0.012] | 0 | 0.518 / 0.609 (10) [-0.091 [-0.154, -0.031]] |
| hs | 0.504 | -0.090 [-0.188, +0.025] | 1 | 0.504 / 0.593 (10) [-0.090 [-0.188, +0.025]] |
| hs_conf | 0.561 | -0.032 [-0.065, -0.001] | 0 | 0.543 / 0.613 (10) [-0.070 [-0.154, +0.015]] |
| pyin_step1 | 0.609 | +0.015 [-0.023, +0.056] | 2 | 0.543 / 0.635 (10) [-0.092 [-0.402, +0.176]] |
| none | 0.593 | +0.000 [+0.000, +0.000] | 0 | None / None (0) [+0.000 [+0.000, +0.000]] |

| re-laned by | contour fast 50 ms | contour score.py (100 ms) | exact lanes (100 ms) | exact lanes fast | F1@50 | worst song exact diff |
|---|---|---|---|---|---|---|
| pyin | 0.564 -> 0.519 (-0.045 [-0.089, +0.005]) | 0.624 -> 0.612 (-0.012 [-0.022, -0.003]) | 0.26 -> 0.256 (-0.005 [-0.013, +0.002]) | 0.199 -> 0.225 (+0.026 [-0.028, +0.092]) | 0.742 -> 0.742 | -0.032 |
| pyin_conf | 0.564 -> 0.511 (-0.053 [-0.094, -0.006]) | 0.624 -> 0.61 (-0.013 [-0.023, -0.004]) | 0.26 -> 0.254 (-0.006 [-0.014, +0.001]) | 0.199 -> 0.208 (+0.009 [-0.049, +0.082]) | 0.742 -> 0.742 | -0.032 |
| cqt | 0.564 -> 0.403 (-0.161 [-0.220, -0.110]) | 0.624 -> 0.596 (-0.027 [-0.042, -0.013]) | 0.26 -> 0.255 (-0.005 [-0.014, +0.003]) | 0.199 -> 0.214 (+0.015 [-0.034, +0.064]) | 0.742 -> 0.742 | -0.031 |
| cqt_conf | 0.564 -> 0.488 (-0.076 [-0.115, -0.037]) | 0.624 -> 0.607 (-0.017 [-0.027, -0.007]) | 0.26 -> 0.254 (-0.006 [-0.013, +0.001]) | 0.199 -> 0.191 (-0.009 [-0.057, +0.044]) | 0.742 -> 0.742 | -0.028 |
| hs | 0.564 -> 0.45 (-0.114 [-0.167, -0.048]) | 0.624 -> 0.599 (-0.024 [-0.037, -0.012]) | 0.26 -> 0.255 (-0.005 [-0.017, +0.006]) | 0.199 -> 0.22 (+0.020 [-0.056, +0.104]) | 0.742 -> 0.742 | -0.041 |
| hs_conf | 0.564 -> 0.479 (-0.085 [-0.117, -0.051]) | 0.624 -> 0.608 (-0.015 [-0.025, -0.006]) | 0.26 -> 0.255 (-0.006 [-0.014, +0.002]) | 0.199 -> 0.2 (+0.001 [-0.038, +0.042]) | 0.742 -> 0.742 | -0.028 |
| pyin_step1 | 0.564 -> 0.519 (-0.045 [-0.078, -0.012]) | 0.624 -> 0.613 (-0.010 [-0.016, -0.005]) | 0.26 -> 0.261 (+0.000 [-0.007, +0.008]) | 0.199 -> 0.222 (+0.023 [-0.017, +0.064]) | 0.742 -> 0.742 | -0.017 |
| none | 0.564 -> 0.518 (-0.046 [-0.079, -0.019]) | 0.624 -> 0.614 (-0.009 [-0.015, -0.004]) | 0.26 -> 0.259 (-0.001 [-0.008, +0.005]) | 0.199 -> 0.207 (+0.008 [-0.035, +0.057]) | 0.742 -> 0.742 | -0.028 |

**all_charts** n=10: ours 0.503, humans' ceiling {'mean': 0.561, 'n_songs': 10}
| variant | agreement (fallback ours) | minus ours [CI] | songs >= +0.10 | confident subset: tracker / ours (songs) [diff CI] |
|---|---|---|---|---|
| pyin | 0.5 | -0.002 [-0.026, +0.020] | 0 | 0.49 / 0.527 (10) [-0.037 [-0.148, +0.044]] |
| pyin_conf | 0.491 | -0.012 [-0.035, +0.011] | 0 | 0.484 / 0.528 (10) [-0.045 [-0.162, +0.057]] |
| cqt | 0.395 | -0.108 [-0.137, -0.074] | 0 | 0.395 / 0.503 (10) [-0.108 [-0.137, -0.074]] |
| cqt_conf | 0.482 | -0.020 [-0.038, -0.004] | 0 | 0.462 / 0.524 (10) [-0.063 [-0.112, -0.016]] |
| hs | 0.454 | -0.048 [-0.106, +0.018] | 1 | 0.454 / 0.503 (10) [-0.048 [-0.106, +0.018]] |
| hs_conf | 0.486 | -0.017 [-0.040, +0.004] | 0 | 0.483 / 0.526 (10) [-0.042 [-0.107, +0.020]] |
| pyin_step1 | 0.516 | +0.013 [-0.002, +0.034] | 0 | 0.575 / 0.564 (10) [+0.010 [-0.147, +0.149]] |
| none | 0.503 | +0.000 [+0.000, +0.000] | 0 | None / None (0) [+0.000 [+0.000, +0.000]] |

| re-laned by | contour fast 50 ms | contour score.py (100 ms) | exact lanes (100 ms) | exact lanes fast | F1@50 | worst song exact diff |
|---|---|---|---|---|---|---|
| pyin | 0.48 -> 0.448 (-0.032 [-0.063, +0.003]) | 0.555 -> 0.543 (-0.011 [-0.021, -0.003]) | 0.23 -> 0.228 (-0.002 [-0.008, +0.003]) | 0.203 -> 0.204 (+0.001 [-0.025, +0.025]) | 0.649 -> 0.649 | -0.022 |
| pyin_conf | 0.48 -> 0.44 (-0.039 [-0.074, -0.001]) | 0.555 -> 0.543 (-0.012 [-0.022, -0.004]) | 0.23 -> 0.227 (-0.003 [-0.009, +0.002]) | 0.203 -> 0.196 (-0.007 [-0.028, +0.013]) | 0.649 -> 0.649 | -0.022 |
| cqt | 0.48 -> 0.366 (-0.114 [-0.140, -0.087]) | 0.555 -> 0.528 (-0.026 [-0.044, -0.011]) | 0.23 -> 0.225 (-0.006 [-0.014, +0.001]) | 0.203 -> 0.202 (-0.001 [-0.034, +0.033]) | 0.649 -> 0.649 | -0.031 |
| cqt_conf | 0.48 -> 0.42 (-0.060 [-0.085, -0.034]) | 0.555 -> 0.539 (-0.016 [-0.026, -0.006]) | 0.23 -> 0.227 (-0.003 [-0.009, +0.002]) | 0.203 -> 0.199 (-0.004 [-0.035, +0.028]) | 0.649 -> 0.649 | -0.02 |
| hs | 0.48 -> 0.416 (-0.064 [-0.115, -0.003]) | 0.555 -> 0.534 (-0.021 [-0.034, -0.009]) | 0.23 -> 0.226 (-0.005 [-0.013, +0.003]) | 0.203 -> 0.205 (+0.002 [-0.034, +0.040]) | 0.649 -> 0.649 | -0.032 |
| hs_conf | 0.48 -> 0.424 (-0.055 [-0.087, -0.022]) | 0.555 -> 0.54 (-0.015 [-0.024, -0.007]) | 0.23 -> 0.225 (-0.005 [-0.011, +0.000]) | 0.203 -> 0.186 (-0.017 [-0.042, +0.009]) | 0.649 -> 0.649 | -0.024 |
| pyin_step1 | 0.48 -> 0.449 (-0.031 [-0.063, +0.001]) | 0.555 -> 0.545 (-0.009 [-0.016, -0.004]) | 0.23 -> 0.228 (-0.002 [-0.007, +0.003]) | 0.203 -> 0.2 (-0.003 [-0.033, +0.026]) | 0.649 -> 0.649 | -0.013 |
| none | 0.48 -> 0.443 (-0.036 [-0.062, -0.014]) | 0.555 -> 0.546 (-0.009 [-0.015, -0.003]) | 0.23 -> 0.229 (-0.001 [-0.005, +0.002]) | 0.203 -> 0.206 (+0.003 [-0.017, +0.023]) | 0.649 -> 0.649 | -0.016 |

| song | re-laned by | contour fast 50 | exact 100 | notes moved | (primary chart) |
|---|---|---|---|---|---|
| pm2 | pyin | 0.584 -> 0.552 | 0.307 -> 0.29 | 780 | |
| pm2 | pyin_conf | 0.584 -> 0.552 | 0.307 -> 0.29 | 780 | |
| pm2 | cqt | 0.584 -> 0.442 | 0.307 -> 0.276 | 1135 | |
| pm2 | cqt_conf | 0.584 -> 0.555 | 0.307 -> 0.279 | 941 | |
| pm2 | hs | 0.584 -> 0.419 | 0.307 -> 0.274 | 1091 | |
| pm2 | hs_conf | 0.584 -> 0.548 | 0.307 -> 0.284 | 900 | |
| pm2 | pyin_step1 | 0.584 -> 0.558 | 0.307 -> 0.29 | 734 | |
| pm2 | none | 0.584 -> 0.549 | 0.307 -> 0.279 | 727 | |
| sooth | pyin | 0.473 -> 0.435 | 0.254 -> 0.257 | 258 | |
| sooth | pyin_conf | 0.473 -> 0.457 | 0.254 -> 0.256 | 236 | |
| sooth | cqt | 0.473 -> 0.451 | 0.254 -> 0.256 | 303 | |
| sooth | cqt_conf | 0.473 -> 0.435 | 0.254 -> 0.251 | 236 | |
| sooth | hs | 0.473 -> 0.391 | 0.254 -> 0.253 | 316 | |
| sooth | hs_conf | 0.473 -> 0.462 | 0.254 -> 0.258 | 254 | |
| sooth | pyin_step1 | 0.473 -> 0.462 | 0.254 -> 0.255 | 179 | |
| sooth | none | 0.473 -> 0.462 | 0.254 -> 0.253 | 167 | |
| troop | pyin | 0.57 -> 0.509 | 0.239 -> 0.207 | 721 | |
| troop | pyin_conf | 0.57 -> 0.509 | 0.239 -> 0.207 | 721 | |
| troop | cqt | 0.57 -> 0.453 | 0.239 -> 0.213 | 939 | |
| troop | cqt_conf | 0.57 -> 0.496 | 0.239 -> 0.224 | 692 | |
| troop | hs | 0.57 -> 0.512 | 0.239 -> 0.226 | 851 | |
| troop | hs_conf | 0.57 -> 0.518 | 0.239 -> 0.211 | 721 | |
| troop | pyin_step1 | 0.57 -> 0.529 | 0.239 -> 0.228 | 654 | |
| troop | none | 0.57 -> 0.537 | 0.239 -> 0.235 | 556 | |
| s01 | pyin | 0.561 -> 0.482 | 0.194 -> 0.195 | 129 | |
| s01 | pyin_conf | 0.561 -> 0.482 | 0.194 -> 0.195 | 129 | |
| s01 | cqt | 0.561 -> 0.412 | 0.194 -> 0.208 | 146 | |
| s01 | cqt_conf | 0.561 -> 0.456 | 0.194 -> 0.208 | 124 | |
| s01 | hs | 0.561 -> 0.456 | 0.194 -> 0.215 | 133 | |
| s01 | hs_conf | 0.561 -> 0.456 | 0.194 -> 0.2 | 106 | |
| s01 | pyin_step1 | 0.561 -> 0.509 | 0.194 -> 0.198 | 86 | |
| s01 | none | 0.561 -> 0.526 | 0.194 -> 0.204 | 112 | |
| s02 | pyin | 0.476 -> 0.524 | 0.269 -> 0.277 | 28 | |
| s02 | pyin_conf | 0.476 -> 0.429 | 0.269 -> 0.269 | 24 | |
| s02 | cqt | 0.476 -> 0.333 | 0.269 -> 0.277 | 23 | |
| s02 | cqt_conf | 0.476 -> 0.333 | 0.269 -> 0.269 | 18 | |
| s02 | hs | 0.476 -> 0.619 | 0.269 -> 0.265 | 27 | |
| s02 | hs_conf | 0.476 -> 0.333 | 0.269 -> 0.281 | 19 | |
| s02 | pyin_step1 | 0.476 -> 0.333 | 0.269 -> 0.273 | 20 | |
| s02 | none | 0.476 -> 0.333 | 0.269 -> 0.269 | 9 | |
| s04 | pyin | 0.5 -> 0.625 | 0.231 -> 0.24 | 20 | |
| s04 | pyin_conf | 0.5 -> 0.625 | 0.231 -> 0.24 | 20 | |
| s04 | cqt | 0.5 -> 0.125 | 0.231 -> 0.238 | 29 | |
| s04 | cqt_conf | 0.5 -> 0.5 | 0.231 -> 0.231 | 1 | |
| s04 | hs | 0.5 -> 0.312 | 0.231 -> 0.243 | 26 | |
| s04 | hs_conf | 0.5 -> 0.375 | 0.231 -> 0.233 | 15 | |
| s04 | pyin_step1 | 0.5 -> 0.562 | 0.231 -> 0.233 | 14 | |
| s04 | none | 0.5 -> 0.5 | 0.231 -> 0.231 | 0 | |
| s06 | pyin | 0.664 -> 0.51 | 0.207 -> 0.202 | 213 | |
| s06 | pyin_conf | 0.664 -> 0.5 | 0.207 -> 0.196 | 210 | |
| s06 | cqt | 0.664 -> 0.53 | 0.207 -> 0.2 | 257 | |
| s06 | cqt_conf | 0.664 -> 0.556 | 0.207 -> 0.196 | 186 | |
| s06 | hs | 0.664 -> 0.533 | 0.207 -> 0.212 | 250 | |
| s06 | hs_conf | 0.664 -> 0.556 | 0.207 -> 0.2 | 204 | |
| s06 | pyin_step1 | 0.664 -> 0.553 | 0.207 -> 0.194 | 202 | |
| s06 | none | 0.664 -> 0.526 | 0.207 -> 0.205 | 188 | |
| s07 | pyin | 0.49 -> 0.439 | 0.199 -> 0.19 | 291 | |
| s07 | pyin_conf | 0.49 -> 0.439 | 0.199 -> 0.19 | 291 | |
| s07 | cqt | 0.49 -> 0.402 | 0.199 -> 0.189 | 366 | |
| s07 | cqt_conf | 0.49 -> 0.381 | 0.199 -> 0.193 | 316 | |
| s07 | hs | 0.49 -> 0.348 | 0.199 -> 0.158 | 386 | |
| s07 | hs_conf | 0.49 -> 0.366 | 0.199 -> 0.178 | 325 | |
| s07 | pyin_step1 | 0.49 -> 0.487 | 0.199 -> 0.214 | 263 | |
| s07 | none | 0.49 -> 0.462 | 0.199 -> 0.215 | 242 | |
| s10 | pyin | 0.813 -> 0.72 | 0.421 -> 0.428 | 133 | |
| s10 | pyin_conf | 0.813 -> 0.72 | 0.421 -> 0.428 | 133 | |
| s10 | cqt | 0.813 -> 0.579 | 0.421 -> 0.418 | 139 | |
| s10 | cqt_conf | 0.813 -> 0.841 | 0.421 -> 0.426 | 145 | |
| s10 | hs | 0.813 -> 0.598 | 0.421 -> 0.432 | 149 | |
| s10 | hs_conf | 0.813 -> 0.813 | 0.421 -> 0.427 | 107 | |
| s10 | pyin_step1 | 0.813 -> 0.738 | 0.421 -> 0.444 | 90 | |
| s10 | none | 0.813 -> 0.813 | 0.421 -> 0.421 | 0 | |
| s12 | pyin | 0.509 -> 0.397 | 0.284 -> 0.271 | 108 | |
| s12 | pyin_conf | 0.509 -> 0.397 | 0.284 -> 0.271 | 108 | |
| s12 | cqt | 0.509 -> 0.302 | 0.284 -> 0.278 | 131 | |
| s12 | cqt_conf | 0.509 -> 0.328 | 0.284 -> 0.266 | 108 | |
| s12 | hs | 0.509 -> 0.31 | 0.284 -> 0.273 | 130 | |
| s12 | hs_conf | 0.509 -> 0.362 | 0.284 -> 0.276 | 124 | |
| s12 | pyin_step1 | 0.509 -> 0.457 | 0.284 -> 0.277 | 98 | |
| s12 | none | 0.509 -> 0.474 | 0.284 -> 0.279 | 97 | |

score.py check (primary, contour / exact, here vs score json): [('pm2', {'here': 0.533, 'score_json': 0.5328, 'exact_here': 0.307, 'exact_json': 0.3073}), ('sooth', {'here': 0.667, 'score_json': 0.6674, 'exact_here': 0.254, 'exact_json': 0.2541}), ('troop', {'here': 0.521, 'score_json': 0.5208, 'exact_here': 0.239, 'exact_json': 0.2387}), ('s01', {'here': 0.508, 'score_json': 0.5081, 'exact_here': 0.194, 'exact_json': 0.1937}), ('s02', {'here': 0.598, 'score_json': 0.5982, 'exact_here': 0.269, 'exact_json': 0.2692}), ('s04', {'here': 0.673, 'score_json': 0.6729, 'exact_here': 0.231, 'exact_json': 0.2312}), ('s06', {'here': 0.561, 'score_json': 0.5606, 'exact_here': 0.207, 'exact_json': 0.2069}), ('s07', {'here': 0.734, 'score_json': 0.7336, 'exact_here': 0.199, 'exact_json': 0.1991}), ('s10', {'here': 0.809, 'score_json': 0.8089, 'exact_here': 0.421, 'exact_json': 0.4206}), ('s12', {'here': 0.631, 'score_json': 0.6314, 'exact_here': 0.284, 'exact_json': 0.2838})]

---

## Addendum (2026-11-08): an ML tracker, torchcrepe (the owner allowed the install)

torchcrepe 0.0.24 (with resampy 0.4.3) installed into a throwaway folder in memory only (`uv pip install --target`;
the shared venv has no pip; nothing went into it; deleted afterwards), on the same 10 songs' fast-run pairs with the
first spike's scripts: the full model at a 10 ms hop, the same model on frames inside the note only, and the tiny
model at 5 ms; each frame decoded on its own (no Viterbi: smoothing hurt pYIN); periodicity as the confidence.

**Verdict: no.** Every variant is below our own directions (ours 0.593 on the primaries): full -0.175 [-0.282,
-0.077], confident pairs -0.075 [-0.170, -0.006], the best (tiny, steps only) -0.052 [-0.190, +0.080]. Where the human
moves, CREPE's sign is right 0.568 (2,364 pairs; ours 0.636, pYIN 0.81 where it stepped): 0.50 to 0.66 by confidence
quartile, 0.585 with octave errors folded. It steps on most pairs, 36 % of its steps 7 semitones or more: noise on
60-125 ms notes of distorted, often polyphonic stems. Re-laning by it, or by a per-run rank fit, lowers the contour
(-0.09 to -0.24). CPU time: the full model 99 s wall a minute of audio on this machine's 4 cores, the tiny 11.6 s.
Not tried: a polyphonic transcriber (basic_pitch), chroma features, pitch on the full mix. The humans agree with each
other 0.821 against our 0.592 on these pairs; no tracker measured closes any of it. Scripts: eval/m8/contour-ml/.
