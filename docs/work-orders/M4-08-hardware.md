# M4-08: the hardware runs (the owner's 5070, then the friend's PC)

**Not a build order.** It needs real Windows PCs with NVIDIA GPUs. The director prepares it, the owner runs part A,
the friend runs part B, and the director reads the diagnostics zips and writes `M4-08-results.md`, DESIGN and
PROGRESS.

**Input:** a green `main` after M4-07, and the full review workflow over the integrated v0.1 (M4-00, section 5). The
release assets come from `build.sh` on `main`: the director attaches them to a draft, or the owner builds them in
WSL with `bash packaging/release/build.sh 0.1.0-rc1 dist`. Before the pre-release exists, part A uses `install.sh
--from <folder>`.

## Intent

CI proves the cpu lane on Ubuntu 26.04 in a container. Only the PCs can show:
- the cu132 lane and autochart's CUDA provider in WSL;
- the time of a 7-minute song with 1 and 4 takes;
- peak RAM inside a 12 GB WSL (the friend's 16 GB PC), and VRAM;
- the localhost route to the Windows browser;
- the Start-menu shortcut under Smart App Control;
- the Songs folder on Windows;
- antivirus effects;
- whether the guide can be followed.

## Part A: the owner's RTX 5070 PC, a fresh distro that mimics the friend's

Run as written; note each answer (A1–A12).

**Prepare (Windows):**

1. `nvidia-smi` in a Windows terminal shows driver 580 or newer.
2. **Mimic the friend's memory.** Copy `%UserProfile%\.wslconfig` to `.wslconfig.owner` (if it exists), then set
   `[wsl2]` to `memory=12GB` and `swap=8GB`. Then `wsl --shutdown`. Your other distros get 12 GB until step 15
   restores the file.
3. *(Only if you agreed, M4-00 question 1)* Windows Security > App & browser control > Smart App Control: **On**.
4. Terminal (Admin): `wsl --install -d Ubuntu-26.04`. This is the same Ubuntu 26.04.1 image the friend's "Ubuntu"
   gets, as a separately named distro [doc: Microsoft's DistributionInfo.json]. Make a user.

**Install and use (follow the guide, M4-07, from its section 3):**

5. Paste the guide's install line, or `bash install.sh --from <folder>` before the pre-release exists.
   - **A1:** total time, and the download size it announced.
   - **A2:** the lane and reason (expected `cu132`).
   - Did it keep the 12 GB `.wslconfig`? It should keep any memory of 12 GB or more.
   - At the end, the window closes (WSL restarts).
6. Start menu > "songcharter".
   - **A3:** does the page open in the browser? (With SAC on: does the shortcut run at all?)
   - **A4:** the header: expected "GPU: NVIDIA GeForce RTX 5070 (12 GB)" and "guitar on the GPU".
7. Chart the test song's MP3 (the friend's file) with **Guitar takes: 1**. **A5:** the total and the guitar stage's
   time.
8. Chart it again with the defaults (4 takes on the GPU). **A6:** the guitar stage's time.
9. Chart Take Me Out (`input.wav`) with the defaults. The director scores it on Linux with
   `eval/scorer/score.py`.
10. Start any song, and press Cancel once the guitar row shows "take 1".
    - **A7:** cancelled within 30 s?
    - Afterwards, in the distro, does `ps -eo args | grep -E 'node|songcharter.cli'` show anything?
11. "Install into Clone Hero". **A8:** did it find the Songs folder by itself (is your Documents in OneDrive)?
    - Then in Clone Hero: Scan Songs, and play the test song on Expert. **A9:** in sync? Anything odd?
12. Turn Windows' network off, close the songcharter window, start it again from the Start menu, and chart a song
    not charted before. **A10:** does it finish?
13. Copy only the song-folder lines of `Documents\Clone Hero\settings.ini`, with their key names. **A11.**
14. The page's "Diagnostics" link. Send the zip with A1–A12.

**Uninstall and clean up:**

15. In the distro: `songcharter uninstall`, answer **No**. Then paste the install line again.
    - **A12:** time; did it download anything?
    - Then:
      - `wsl --unregister Ubuntu-26.04`;
      - restore `.wslconfig.owner` to `.wslconfig`, and `wsl --shutdown`;
      - turn Smart App Control back off if step 3 turned it on.

**Pass** (DESIGN 5, M4, for what v0.1 covers):
- the install finishes without help; lane `cu132`;
- every take's transcriber ran on `cuda` (`pipeline.json`, in the zip);
- `doctor`'s `autochart_cuda` is ok;
- the test song with 1 take in **8 min or less**: the 4070's target, so the 5070 should beat it. A6 is recorded.
  - Rule [decision]: if 4 takes add more than 12 min to the guitar stage, the default on CUDA under WSL goes to 1
    take, a one-line change in `guitar_takes`.
- **Memory:** inside 12 GB, no stage is killed (no "Killed", no OOM line in the logs), and the lowest available RAM
  and peak swap per stage are recorded. If swap passes 4 GB in a stage, the director decides between the librosa
  sections and a smaller WSL margin before the friend's run.
- VRAM per stage is recorded; no CUDA out-of-memory fallback.
- **Take Me Out against the human chart:** guitar F1@50 ≥ 0.845 (0.880 − 0.035), drums ≥ 0.927 (0.947 − 0.02), bass
  reported (M3's rules).
- Cancel leaves no process; the offline run finishes; the song plays in Clone Hero after a rescan; the reinstall
  downloads nothing.
- Every guide step was clear, or the unclear ones are listed for M4-07.

**Then** the owner (or a session, if allowed) creates the pre-release (M4-07).

## Part B: the friend's PC (Smart App Control on, 16–32 GB)

**Before**, the owner sends him the pre-release link: its notes are the guide.

**He follows the guide alone.** Note every question he asks: each one is a guide fix.

1. He sets up WSL and installs songcharter.
2. He charts the test song once with **Guitar takes: 1** and once with the defaults.
3. He charts one song of his choice, installs it into Clone Hero, and plays it.
4. He sends the diagnostics zip, and what felt wrong or slow.

**Pass** (DESIGN 5, M4, for what v0.1 covers), read from his zip:
- installed and ran without help;
- the shortcut worked under Smart App Control (or the Ubuntu fallback, noted);
- the 1-take test song in 8 min or less, and the 4-take time recorded;
- no stage killed for memory; RAM, swap and VRAM per stage recorded; no CUDA out-of-memory;
- every CPU fallback shown;
- the songs play after a rescan.

Also record for PROGRESS (the M1a spike): GPU, driver, compute capability, Windows build, RAM (`windows_ram_mb`),
and WSL memory.

## Done means

- `docs/work-orders/M4-08-results.md`, written by the director: each pass line with its number, and the decisions it
  triggers:
  - the 4-take default under WSL;
  - the memory margin;
  - parsing Clone Hero's `settings.ini` (M4-99);
  - guide fixes.
- PROGRESS: M4 "done" if both parts pass, or the fix orders it needs.

## Depends on

M4-07, the full review workflow, and the owner's and the friend's time.
