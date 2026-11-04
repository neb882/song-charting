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

Run as written; note each answer (A1–A16). About three hours.

**Prepare (Windows):**

1. `nvidia-smi` in a Windows terminal shows driver 580 or newer.
2. **Start with no `.wslconfig`, as on the friend's PC.**
   - Rename `%UserProfile%\.wslconfig` to `.wslconfig.owner` (if it exists), then `wsl --shutdown`.
   - The install writes the friend's file in step 5. Your other distros run with that file, or WSL's defaults, until
     step 18 restores yours.
3. *(Optional, only if you agreed to M4-00 question 1, and only if the switch is not greyed out)* Windows Security >
   App & browser control > Smart App Control: **On**. That it can be turned on after setup is reported for 25H2 with
   the April 2026 update, and is unsettled. If it is greyed out, skip this step and note it.
4. Terminal (Admin): `wsl --update`, then `wsl --install -d Ubuntu-26.04`. This is the same Ubuntu 26.04.1 image the
   friend's "Ubuntu" gets, as a separately named distro [doc: Microsoft's DistributionInfo.json]. Make a user.

**Install and use (follow the guide, M4-07, from its section 3):**

5. Paste the guide's install line, with ` --windows-ram-gb 16` added after `bash install.sh`, so it writes the
   `.wslconfig` of a 16 GB PC. Before the pre-release exists: `bash install.sh --from <folder> --windows-ram-gb 16`.
   - **A1:** total time, and the download size it announced.
   - **A2:** the lane and reason (expected `cu132`).
   - **A3:** did it say it wrote `.wslconfig` (`memory=12GB`, `swap=8GB`), and print the restart message before the
     window closed?
6. Start menu > "songcharter". In the window that opens, before using the page: `songcharter doctor` in another
   Ubuntu-26.04 window.
   - **A4:** `memory_matches_config` true, and `MemTotal` about 12 GB?
   - **A5:** does the page open in the browser? (With SAC on: does the shortcut run at all?) The header should say
     "GPU: NVIDIA GeForce RTX 5070 (12 GB)" and "guitar on the GPU".
7. Chart the test song's MP3 (the friend's file) with **Guitar takes: 1**. **A6:** the total and the guitar stage's
   time.
8. Chart it again with the defaults (4 takes on the GPU). **A7:** the guitar stage's time.
9. Chart Take Me Out (`input.wav`) with the defaults. The director scores it on Linux with `eval/scorer/score.py`.
10. **Cancel:** start any song, and press Cancel once the guitar row shows "take 1".
    - **A8:** cancelled within 30 s?
    - Afterwards, does `ps -eo args | grep -E 'node|songcharter.cli'` in the distro show anything?
11. **Closing the window mid-chart:** start a song, close the songcharter window during the guitar stage, then
    reopen Ubuntu-26.04. **A9:** does the same `ps` show no `node` and no `songcharter.cli`? (SIGHUP must kill the
    job.)
12. **A non-ASCII name:** drag a song file named, for example, `Déjà Vü – Test.mp3` from Windows Explorer onto the
    page, and chart it with 1 take. **A10:** uploaded, charted, and its folder name readable?
13. **Clone Hero:** "Install into Clone Hero" for the test song.
    - **A11:** did it find the Songs folder by itself (is your Documents in OneDrive)?
    - Then install the same chart again: the page should offer "Replace the older chart?". Accept, and check that one
      folder of that name is left.
    - In Clone Hero: Scan Songs, and play the test song on Expert. **A12:** in sync? Anything odd?
14. **Offline:** turn Windows' network off, close the songcharter window, start it again from the Start menu, and
    chart a song not charted before. **A13:** does it finish?
15. **The fallback address:**
    - add `localhostForwarding=false` to `[wsl2]` in `.wslconfig`, `wsl --shutdown`, and start songcharter from the
      Start menu;
    - **A14:** does the page open on WSL's own address (`http://172.x.x.x:8765/`), and does an upload work there?
    - Then remove that line and `wsl --shutdown`.
16. Copy only the song-folder lines of `Documents\Clone Hero\settings.ini`, with their key names. **A15.**
17. The page's "Diagnostics" link. Send the zip with the answers.

**Uninstall, reinstall, the older distro, clean up:**

18. **Uninstall and reinstall:**
    - in the distro: `songcharter uninstall`, answer **No**, then paste the install line again;
    - **A16:** time; did it download anything? Is there exactly one "songcharter" in the Start menu, the reinstall
      having overwritten the shortcut, and does it start?
    - Then `wsl --unregister Ubuntu-26.04`.
19. **The older-distro variant, install only:** `wsl --install -d Ubuntu-22.04`, make a user, paste the install
    line, and note whether it finishes and what `songcharter doctor` says. Then `wsl --unregister Ubuntu-22.04`. CI
    covers the same in a container (M4-05); this is the real WSL image.
20. Restore `.wslconfig.owner` to `.wslconfig`, `wsl --shutdown`, and turn Smart App Control back off if step 3
    turned it on.

**Pass** (DESIGN 5, M4, for what v0.1 covers):
- the install finishes without help; lane `cu132`;
- every take's transcriber ran on `cuda` (`pipeline.json`, in the zip);
- `doctor`'s `autochart_cuda` is ok;
- the test song with 1 take in **8 min or less**: the 4070's target, so the 5070 should beat it. A7 is recorded.
  - Rule [decision]: if 4 takes add more than 12 min to the guitar stage, the default on CUDA under WSL goes to 1
    take, a one-line change in `guitar_takes`.
- **Memory:** inside 12 GB, no stage is killed (no "Killed", no OOM line in the logs), and the lowest available RAM
  and peak swap per stage are recorded. If swap passes 4 GB in a stage, the director decides between the librosa
  sections and a smaller WSL margin before the friend's run.
- VRAM per stage is recorded; no CUDA out-of-memory fallback.
- **Take Me Out against the human chart:** guitar F1@50 ≥ 0.845 (0.880 − 0.035), drums ≥ 0.927 (0.947 − 0.02), bass
  reported (M3's rules).
- The install wrote `memory=12GB` and `swap=8GB`, and after the restart `memory_matches_config` is true.
- Cancel and closing the window both leave no process.
- The non-ASCII file charts.
- 409 → replace leaves one folder.
- The offline run finishes; the fallback address works.
- The song plays in Clone Hero after a rescan.
- The reinstall downloads nothing and leaves one shortcut.
- The 22.04 result is recorded (a failure there is a guide note, since the guide runs `wsl --update` first).
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

## Added at M4-01's merge

- **The cu126 allin1 pairing is untested on real hardware:** torch 2.14.1+cu126 with torchaudio 2.11.1+cpu. A cpu
  stand-in passed. If either PC gets the cu126 lane (a driver under 580), run allin1's probe there once
  (`songcharter doctor` reports it) and record the result. On the cu132 lane this does not apply.
- **The guitar engine's own memory** (the M4-02 golden run saw autochart's node engine killed at 12.8 GB once, against
  4.2–5.7 GB in reruns of the same song). A plausible cause, from its code: on the CPU, the decode loop leaves the
  past key and value tensors, about 77 MB a step at 1,914 tokens, to V8's garbage collector, which a busy CPU can
  starve; and its sessions set no intra-op thread limit. Measure the node process's own VmRSS and VmHWM every second
  from `/proc/<pid>/status`, with `NODE_OPTIONS=--trace-gc`, over at least 5 runs of one song, idle and under CPU
  load, on the cuda lane and, if time allows, forced to the CPU. A peak near the WSL memory cap blocks the release.
- **The friend's GPU, from his `nvidia-smi` (2026-11-03):** RTX 4070 with 12,282 MiB, a driver new enough for the cu132 lane,
  WDDM, driving the display. So he gets the cu132 lane and the guitar on CUDA. At idle 2.6 GB of VRAM is already in use
  by desktop apps: about 9.5 GB is left. Record the per-stage VRAM peaks against
  that, with those apps open and closed.
- **Other software with kernel drivers:** anti-cheat drivers and other GPU vendors' utilities are common on gaming PCs.
  If WSL2's virtualization does not install or start, record what `wsl` says; if the PC has a second graphics adapter,
  check that doctor names the NVIDIA GPU and that CUDA uses it.

## Added at M4-04's merge

- **The page from Windows:** check the self-check (`curl.exe` from WSL) and that the page opens in the Windows
  browser, both tested only with stand-ins. Record WSL's NAT address: the fallback assumes it is inside
  172.16.0.0/12 and stops otherwise. Under `networkingMode=mirrored`, the server must stop rather than listen on
  the PC's LAN address; check that it does, and that nothing listens on a non-loopback address (`ss -ltn`).
- `explorer.exe` and the shortcut's `ui --from-shortcut` are likewise tested only with stand-ins.

## Added at M4-10's merge

- Chart one song with `--lyrics` (the owner's own text for the test song, never committed or shown) and check that
  Clone Hero shows the lyrics in time; scan-chart's `hasLyrics` is the only check so far.
- The aligner on CUDA: its time, its VRAM peak, and that its times match the CPU's (determinism is checked on the
  CPU only).
