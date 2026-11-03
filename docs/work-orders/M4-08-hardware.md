# M4-08: the hardware runs (the owner's PC, then the friend's)

**Not a build order.** No agent can do it: it needs real Windows PCs with NVIDIA GPUs. The director prepares it,
the owner runs part A, the friend runs part B, and the director reads the diagnostics bundles and writes the
results into DESIGN and PROGRESS.

**Input:** the `songcharter-setup-X.exe` and `songcharter-X-portable.zip` from M4-07's green CI run, after the full
review workflow over the integrated v0.1 (M4-00, section 4).

## Intent

Nothing of v0.1 has run on a Windows PC with a GPU. CI proves the CPU lane on a server image with no display adapter.
These two runs answer what only hardware can:
- the cu132 lane on native Windows;
- the guitar on WebGPU and its speed, and so the 4-take default there;
- VRAM and RAM;
- path lengths on real profiles;
- SmartScreen and Smart App Control;
- Clone Hero's own folders.

Part B is also the Windows spike PROGRESS still lists under M1a.

## Part A: the owner's RTX 5070 PC, native Windows (not WSL)

**Before:**
- `nvidia-smi` in a Windows terminal shows driver 580 or newer. The 5070 needs it for the cu132 lane; the cu126
  build has no kernels for it.
- Clone Hero is installed.
- The test song's MP3, the one the friend plays, and Take Me Out's `input.wav` are copied to the Windows side, for
  example `Downloads\`.

**Steps.** Write down each answer.

1. Run the setup. Does SmartScreen show "Windows protected your PC"? Install without admin; the bootstrap window
   runs.
   - **A1:** the bootstrap's time, and its last lines (lane and reason; expected `cu132`).
2. The page opens. **A2:** the header text. Expected "GPU: NVIDIA GeForce RTX 5070 (12 GB)" and "guitar on WebGPU".
3. Chart the test song with **Guitar takes: 1**, everything else default.
   - **A3:** the total time, and the guitar stage's time (the progress page shows both).
4. Chart it again with the defaults: 4 takes on a GPU. The caches make every stage but the guitar quick.
   - **A4:** the guitar stage's time.
   - Rule [decision, M4-00 risk 1]: if A4 minus A3's guitar time is over 12 min, the default on WebGPU becomes 1
     take.
5. During one more run of any song, press Cancel during the guitar stage.
   - **A5:** does the page say cancelled within 30 s? Are any `node.exe` or `python.exe` from songcharter still in
     Task Manager's Details tab after that?
6. Chart Take Me Out with the defaults. The director scores it on Linux against the human chart with
   `eval/scorer/score.py`.
7. Install the test song into Clone Hero with the button. Did it find the Songs folder by itself?
   - In Clone Hero: Settings > General > Scan Songs, then play it on Expert.
   - **A7:** in sync? Anything odd?
8. Turn the network off (Wi-Fi off, or unplug), close the songcharter window, start songcharter again from the
   Start Menu, and chart a song never charted before.
   - **A8:** does it finish?
9. Open `Documents\Clone Hero\settings.ini` in Notepad. **A9:** copy only the lines that name a folder (the song
   folder settings), with their key names.
10. Start Menu, "songcharter: diagnostics". Send the zip from the desktop with A1–A9.
11. Uninstall from Settings > Apps, and answer No to the question. Then reinstall: the bootstrap should take
    minutes, not the first time's.

**Pass** (DESIGN 5, M4, for what v0.1 covers):
- install and run without errors; the lane is `cu132`, and the guitar is on `webgpu` (`pipeline.json`: the
  transcriber's device for every take);
- the test song passes the gate, with the same section and star-power counts as the Linux build within ±10 %
  [decision];
- Take Me Out against the human chart:
  - guitar F1@50 at least 0.880 − 0.035 = 0.845 (M3's rule: the best tool's 0.880 minus the 0.035 spread);
  - drums at least 0.947 − 0.02 = 0.927 (M3's rule against ADTOF);
  - bass reported;
- no CPU fallback that `doctor` did not predict;
- the lowest available RAM over each run is 4 GB or more (DESIGN's "peak RAM within the PC's RAM minus 4 GB"), and
  no stage ran out of GPU memory;
- cancel leaves no process behind; the offline run finishes; the song plays in Clone Hero after a rescan.

## Part B: the friend's RTX 4070 PC

**Before**, the director writes and the owner sends:
- the setup file, through whichever channel M4-00 open question 1 settles;
- the test song's MP3, if he does not have it, with the same file rule as v1;
- five lines of instructions:
  1. "Run the file. If Windows says 'Windows protected your PC', click More info, then Run anyway."
  2. "Let the setup finish; it downloads about 3 GB."
  3. "Drop a song into the page that opens, then press Chart it."
  4. "When it is done, press Install into Clone Hero, then Scan Songs in Clone Hero."
  5. "Send us the file from Start Menu > songcharter: diagnostics."

**Steps for him**, with no help unless he is stuck. Note every question he asks: each one is a v0.2 fix.

1. Install and let the setup finish.
2. Chart the test song once with **Guitar takes: 1**, and once with the defaults.
3. Chart one song of his own choice with the defaults; install it into Clone Hero and play it.
4. Send the diagnostics zip, and say what felt wrong or slow.

**Pass:** DESIGN 5, M4's acceptance for the friend's 4070, for what v0.1 covers. The director reads each from the
bundle:
- it installs and runs without help;
- the 1-take test song finishes in 8 min or less (the 6:52 song; DESIGN's target names a 7-min song);
- the 4-take run's time is recorded;
- the lowest available RAM is 4 GB or more at every stage, and no CUDA out-of-memory fallback happened;
- `doctor.json`'s path check is ok on his profile, with no path error in any log;
- every CPU fallback that happened was shown (in `pipeline.json`'s `fallbacks` and the UI);
- the songs play in Clone Hero after a rescan.

**Also record for PROGRESS** (the M1a spike): the GPU, driver and compute capability; his RAM; the Smart App Control
state; SmartScreen's behaviour.

## Done means

- A report in `docs/work-orders/M4-08-results.md`, written by the director from the two bundles and the answers:
  each pass line with its number, and the decisions it triggers (the WebGPU takes default; `settings.ini` parsing
  for M4-99; Smart App Control instructions).
- PROGRESS: M4 "done" if both parts pass, or the fix orders it needs.

## Depends on

M4-07 (a CI-built installer), and the owner's and the friend's time.
