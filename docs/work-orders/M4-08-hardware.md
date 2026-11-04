# M4-08: the hardware runs (the owner's 5070, then the friend's PC)

**Not a build order.** It needs real Windows PCs with NVIDIA GPUs. The director prepares it, the owner runs part A,
the friend runs part B, and the director reads the diagnostics zips and writes `M4-08-results.md`, DESIGN and
PROGRESS.

**Input:** a green `main` after M4-07, the full review workflow over the integrated v0.1 (M4-00, section 5; run at
the release gate), and the advisor's review of the release candidate with its fixes merged. **The release comes
first** [decision] (the advisor on the release candidate, finding 3): the owner tags `main`, builds the assets from
the tag and publishes the pre-release (R1-R4 below), and part A then installs with the guide's line copied from the
release page, as the friend will. So the download, the hash checks and the licence prompt's link are tried before he
meets them, which `--from` and CI's local server cannot show. One version string, `0.1.0`, everywhere (the tarball,
the app's folder, doctor): GitHub's pre-release flag is what marks it a candidate.

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

## The release, before part A (the owner)

Publishing needs the owner's yes: a session prepares, the owner publishes.

- **R1.** In a clean clone: `git tag v0.1.0 <main's commit> && git push origin v0.1.0`, then `git checkout v0.1.0`.
  build.sh archives HEAD, so the tarball is the tagged tree.
- **R2.** `bash packaging/release/build.sh 0.1.0 dist`. It names any uncommitted change: there must be none.
- **R3.** Publish the pre-release with M4-07's recipe (`gh release create v0.1.0 --prerelease ...` with
  `dist/GUIDE.md` as its notes and the three other files of `dist/`), or by hand on the release page with the same
  files and notes.
- **R4.** If part A fails [decision]: the owner deletes the pre-release and the tag (`gh release delete v0.1.0
  --cleanup-tag`, then `git tag -d v0.1.0`; or by hand), the fix is made on `main`, and R1-R3 are done again at the
  fixed commit. The friend gets the link only once part A passes.

## Part A: the owner's RTX 5070 PC, a fresh distro that mimics the friend's

Run as written; note each answer (A1–A24). About four hours; steps 15 and 19 may be left out when time runs short.

**Prepare (Windows):**

1. `nvidia-smi` in a Windows terminal shows driver 580 or newer.
2. **Start with no `.wslconfig`, as on the friend's PC.**
   - Rename `%UserProfile%\.wslconfig` to `.wslconfig.owner` (if it exists), then `wsl --shutdown`.
   - The install writes the friend's file in step 5. Your other distros run with that file, or WSL's defaults, until
     step 20 restores yours.
3. *(Optional, only if you agreed to M4-00 question 1, and only if the switch is not greyed out)* Windows Security >
   App & browser control > Smart App Control: **On**. That it can be turned on after setup is reported for 25H2 with
   the April 2026 update, and is unsettled. If it is greyed out, skip this step and note it.
4. Terminal (Admin): `wsl --update`, then `wsl --install -d Ubuntu-26.04`. This is the same Ubuntu 26.04.1 image the
   friend's "Ubuntu" gets, as a separately named distro [doc: Microsoft's DistributionInfo.json]. Make a user.

**Install and use (follow the guide, M4-07, from its section 3):**

5. Paste the guide's install line, copied from the release page, with ` --windows-ram-gb 16` added after
   `bash install.sh`, so it writes the `.wslconfig` of a 16 GB PC.
   - **A1:** total time, the download size it announced, and C:'s free space before the install (the guide asks
     about 20 GB, and up to 8 GB more for WSL's swap file, which grows on C: when it is used).
   - **A2:** the lane and reason (expected `cu132`).
   - **A3:** did it say it wrote `.wslconfig` (`memory=12GB`, `swap=8GB`), and print the restart message? Then did
     the window close by itself, as the guide's section 3 says, or stay open (Windows Terminal can keep a tab open
     with "[process exited with code ...]")?
   - **A17:** the line from the release page installs in the fresh distro: "install.sh: OK", then no SHA-256
     failure (the app's tarball and uv are checked against their hashes), and the licence prompt's link (the
     release's NOTICE.txt at `blob/v0.1.0/`) opens in a browser.
   - **The install's last lines** (the advisor's finding 7): copy them from "doctor:" to the end, with user names
     and paths left out. A "WSL has ... under 8 GB" problem there, before the restart the install then runs, can
     happen on a PC that reports under about 15.2 GiB (PROGRESS, deferred): note whether it did.
6. Start menu > "songcharter". In the window that opens, before using the page: `songcharter doctor` in another
   Ubuntu-26.04 window.
   - **A4:** `memory_matches_config` true, and `MemTotal` about 12 GB?
   - **A5:** does the page open in the browser? (With SAC on: does the shortcut run at all?) The header should say
     "GPU: NVIDIA GeForce RTX 5070 (12 GB)" and "guitar on the GPU".
7. Chart the test song's MP3 (the friend's file) with **Guitar takes: 1**. **A6:** the total and the guitar stage's
   time.
   - **VRAM, for every chart in steps 7-9:** before it, Windows' `nvidia-smi` in Command Prompt (the memory used);
     during it, the peak (`nvidia-smi --query-gpu=memory.used --format=csv -l 2` in another window, or Task Manager >
     Performance > GPU, "Dedicated GPU memory").
8. Chart it again with the defaults (4 takes on the GPU). **A7:** the guitar stage's time. It measures 3 takes, not
   4: the first is cached from step 7 (A6). That is the time the 3 extra takes add, which the takes rule below
   needs: record it as such, not as a cold 4-take time.
   - **A18, the same chart twice from cold:** delete the cache's work and scratch folders (`rm -rf
     ~/.cache/songcharter/work ~/.cache/songcharter/ac`), chart the test song with the defaults, and copy its
     notes.chart aside (the Done screen names its folder); delete them again, chart it again the same way, then
     `cmp` the two notes.chart files. Byte-identical or not, the result goes into DESIGN (section 1, Determinism)
     and PROGRESS.
   - **A19, VRAM with programs open:** during the first of A18's charts, have a browser playing a video and a chat
     app open, as the friend's PC will: the free VRAM before and the peak during it, and whether any take failed or
     fell back to the CPU.
   - **A22, what CUDA buys the guitar:** chart the test song once more with **Device: CPU** and Guitar takes: 1 (the
     guitar's take runs again on the CPU). Record its guitar stage's time beside A6's CUDA take. DESIGN's C2 row
     says a GPU barely helps the transcription: the GPU smoke test's CUDA takes took 177-217 s, against 217 s for a
     take on the dev container's CPU.
9. Chart Take Me Out (`input.wav`) with the defaults. The director scores it on Linux with `eval/scorer/score.py`.
10. **Cancel:** start any song, and press Cancel once the guitar row shows "take 1".
    - **A8:** cancelled within 30 s?
    - Afterwards, does `ps -eo args | grep -E 'node|songcharter.cli'` in the distro show anything?
    - **A23, a GPU failure on purpose:** chart a song not charted before with the defaults and, during take 2, start
      a program that fills the GPU's memory. What does the Done screen say? Expected: "The guitar's GPU run failed in
      take k of n; ...", what to try, then autochart's lines, each on its own line. Close that program and chart the
      same song again: does it finish, running only the takes that had not finished?
11. **Closing the window mid-chart:** start a song, close the songcharter window during the guitar stage, then
    reopen Ubuntu-26.04. **A9:** does the same `ps` show no `node` and no `songcharter.cli`? (SIGHUP must kill the
    job.)
    - **A20, memory after a chart:** after a chart that finished, close the songcharter window (and every Ubuntu
      window) and watch *Vmmem* (or *VmmemWSL*) in Task Manager: how long until its memory is back? The guide says
      it can take a minute.
    - **A21, sleep mid-chart:** once, let the PC sleep during a chart's guitar stage (Start > Power > Sleep), and
      wake it a few minutes later. Does the job finish? Is WSL's clock right afterwards (`date` in Ubuntu against
      Windows' clock: the guide's section 6 case)?
12. **A non-ASCII name:** drag a song file named, for example, `Déjà Vü – Test.mp3` from Windows Explorer onto the
    page, and chart it with 1 take. **A10:** uploaded, charted, and its folder name readable?
13. **Clone Hero:** "Install into Clone Hero" for the test song.
    - **A11:** did it find the Songs folder by itself (is your Documents in OneDrive)?
    - Then install the same chart again: the page should offer "Replace the older chart?". Accept, and check that one
      folder of that name is left.
    - In Clone Hero: Scan Songs (is it at Settings > General > Scan Songs, as the guide and the page's install
      message say?), and play the test song on Expert. **A12:** in sync? Anything odd? The menu path as found.
14. **Offline:** turn Windows' network off, close the songcharter window, start it again from the Start menu, and
    chart a song not charted before. **A13:** does it finish?
15. **The fallback address** *(optional when time runs short: the friend's fresh PC will not have
    localhostForwarding off)*:
    - add `localhostForwarding=false` to `[wsl2]` in `.wslconfig`, `wsl --shutdown`, and start songcharter from the
      Start menu;
    - **A14:** does the page open on WSL's own address (`http://172.x.x.x:8765/`), and does an upload work there?
    - Then remove that line and `wsl --shutdown`.
16. Copy only the song-folder lines of `Documents\Clone Hero\settings.ini`, with their key names. **A15.**
17. The page's "Diagnostics" link. Send the zip with the answers.
    - **A24:** from the tag's checkout, `python3 packaging/ci/check_no_audio.py <the zip>` passes. After the lyrics
      chart ("Added at M4-10's merge"), the zip holds none of the pasted text: the script below reads the text (in
      a file of your own, `lyrics.txt`, never committed) and the zip, and prints only `yes` (three pasted words in a
      row found in a member) or `no`, never a word. Three in a row, because a single word cannot tell a leak from a
      log's own words.

      ```
      python3 - lyrics.txt diagnostics.zip <<'EOF'
      import re, sys, zipfile
      words = lambda text: re.findall(r"[^\W_]+", text.lower())
      runs = lambda ws: {tuple(ws[i:i + 3]) for i in range(len(ws) - 2)}
      pasted = set().union(*[runs(words(line)) for line in open(sys.argv[1], encoding="utf-8")])
      z = zipfile.ZipFile(sys.argv[2])
      print("yes" if any(runs(words(z.read(n).decode("utf-8", "replace"))) & pasted for n in z.namelist()) else "no")
      EOF
      ```

**Uninstall, reinstall, the older distro, clean up:**

18. **Uninstall and reinstall:**
    - in the distro: `songcharter uninstall`, answer **No**, then paste the install line again;
    - **A16:** time; did it download anything but install.sh and the app's tarball (about 1 MB)? Is there exactly
      one "songcharter" in the Start menu, the reinstall having overwritten the shortcut? Does the page start from
      it, and chart a song (1 take is enough)?
    - Then `wsl --unregister Ubuntu-26.04`.
19. **The older-distro variant, install only** *(optional when time runs short: the guide runs `wsl --update`
    first, and CI covers 22.04)*: `wsl --install -d Ubuntu-22.04`, make a user, paste the install
    line, and note whether it finishes and what `songcharter doctor` says. Then `wsl --unregister Ubuntu-22.04`. CI
    covers the same in a container (M4-05); this is the real WSL image.
20. Restore `.wslconfig.owner` to `.wslconfig`, `wsl --shutdown`, and turn Smart App Control back off if step 3
    turned it on.

**Pass** (DESIGN 5, M4, for what v0.1 covers):
- the line from the release page installs, its hashes check and the licence prompt's link opens (A17); the install
  finishes without help; lane `cu132`;
- every take's transcriber ran on `cuda` (`pipeline.json`, in the zip);
- `doctor`'s `autochart_cuda` is ok;
- the test song with 1 take in **8 min or less**: the 4070's target, so the 5070 should beat it. A7 is recorded
  (3 takes: see step 8), and so is A22 beside A6.
  - Rule [decision], judged on the friend's 4070 (part B's times), not on the 5070, where the 3 extra takes added
    10.7 min in the GPU smoke test: if 4 takes add more than 12 min to the guitar stage there, the default on CUDA
    under WSL goes to 1 take, a one-line change in `guitar_takes`, for v0.1.1.
- **Determinism (A18):** the two cold charts' notes.chart compared, and DESIGN and PROGRESS say what was found,
  whichever way it falls [decision]: identical, the rule holds for 4 CUDA takes on one machine; different, DESIGN
  and PROGRESS say that CUDA takes vary between runs and that the rule holds on the CPU.
- **Memory:** inside 12 GB, no stage is killed (no "Killed", no OOM line in the logs), and the lowest available RAM
  and peak swap per stage are recorded. If swap passes 4 GB in a stage, the director decides between the librosa
  sections and a smaller WSL margin before the friend's run.
- VRAM per stage is recorded, with the free VRAM before each chart and its peak, once with programs open (A19); no
  CUDA out-of-memory fallback. The failure on purpose (A23) shows the advice, then autochart's lines, and the next
  chart finishes.
- A20 and A21 are recorded: the guide's "close the window before you play" and "keep the PC awake" rest on
  them.
- **Take Me Out against the human chart:** guitar F1@50 ≥ 0.845 (0.880 − 0.035), drums ≥ 0.927 (0.947 − 0.02), bass
  reported (M3's rules).
- The install wrote `memory=12GB` and `swap=8GB`, and after the restart `memory_matches_config` is true.
- Cancel and closing the window both leave no process.
- The non-ASCII file charts.
- 409 → replace leaves one folder.
- The offline run finishes; the fallback address works (if step 15 ran).
- The song plays in Clone Hero after a rescan.
- The reinstall downloads only install.sh and the app's tarball (about 1 MB: no Python package, Node or model) and
  leaves one shortcut, and the page starts from it and charts (A16).
- The diagnostics zip passes `check_no_audio.py` and holds none of the pasted text (A24).
- The 22.04 result is recorded, if step 19 ran (a failure there is a guide note, since the guide runs `wsl --update`
  first).
- Every guide step was clear, or the unclear ones are listed for M4-07.

**Then** the owner sends the friend the pre-release's link (part B). If part A failed, R4 first.

## Part B: the friend's PC (Smart App Control on, 16–32 GB)

**Before**, the owner sends him the pre-release link: its notes are the guide. With it, a few lines of his own:
- where "Guitar takes" is (on the page, in the options under Guitar: type 1 there for the 1-take chart);
- to save the diagnostics zip (the page's Diagnostics link) after his **last** chart, since it keeps only the newest
  5 work folders and 10 logs.

**He follows the guide alone.** Note every question he asks: each one is a guide fix.

1. He sets up WSL and installs songcharter.
2. He charts the test song once with **Guitar takes: 1** and once with the defaults.
3. He charts one song of his choice, installs it into Clone Hero, and plays it.
4. He sends the diagnostics zip, saved after his last chart, and what felt wrong or slow.

**Pass** (DESIGN 5, M4, for what v0.1 covers), read from his zip:
- installed and ran without help;
- the shortcut worked under Smart App Control (or the Ubuntu fallback, noted);
- the 1-take test song in 8 min or less, and the 4-take time recorded: the takes rule (part A's pass list) is
  judged on these;
- the install's last lines: the problems and notes of the zip's doctor.json (the install's, which its closing summary
  printed), and whether a "WSL has ... under 8 GB" problem was among them;
- no stage killed for memory; RAM, swap and VRAM per stage recorded; no CUDA out-of-memory;
- every CPU fallback shown;
- the songs play after a rescan.

Also record for PROGRESS (the M1a spike), as requirements (CLAUDE.md): the GPU and its VRAM, whether the driver
is new enough for the cu132 lane, compute capability, RAM (`windows_ram_mb`, rounded as the memory rule reads it),
and WSL memory; no exact driver, Windows or WSL versions.

## Done means

- `docs/work-orders/M4-08-results.md`, written by the director: each pass line with its number, and the decisions it
  triggers:
  - the 4-take default under WSL;
  - the memory margin;
  - parsing Clone Hero's `settings.ini` (M4-99);
  - guide fixes.
- `M4-08-results.md` quotes nothing personal from the zips or the terminal: no user names, profile or home paths,
  machine names or song titles. Hardware facts, times and sizes only, a PC described by what a check needs.
- A18's result in DESIGN (section 1, Determinism) and PROGRESS.
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
- **The friend's GPU:** an RTX 4070 (12 GB) driving the display, on a driver new enough for the cu132 lane, so he gets
  the guitar on CUDA. At idle the desktop already holds some of its VRAM: about 9.5 GB is left. Record the per-stage
  VRAM peaks against that, with the usual programs open and closed.
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

## Added at M4-06's merge

- **Install into Clone Hero, on Windows:** the Songs folder found (including a OneDrive-moved Documents), the copy
  and renames on `/mnt/c`, a replace (409, then Replace), and the chart playing after Scan Songs. With OneDrive or
  antivirus holding the folder if that can be arranged: the retries, and the zip offered when blocked.
- Whether Clone Hero lists a dot-folder in Songs (a `.tmp` or `.old` of ours left by a blocked install).
- **Open folder:** explorer.exe on a `C:\...` and a `\\wsl.localhost\...` path, and on a song whose name has a comma
  (explorer may read commas as separators).
- **Save as a zip:** where it lands, with a non-ASCII song name.

## Added at M4-05's merge

- The cpu lane's baseline from CI (ubuntu:26.04, GitHub's runner): install 2.8 GB; a 30 s clip charted in 47-74 s
  (separate 13 s, bass 8 s, sections 7 s, guitar 15 s on run 1); a reinstall after No in 5-7 s, nothing downloaded
  (from `--from`'s folder; the guide's line fetches install.sh and the app's tarball).
  Record the cu132 lane's equivalents on the 5070 against them.

## Added at the release gate's fixes

Each was tested with stand-ins only; only the real install shows them.
- **Lyrics on the installed app:** the first song charted from the page with lyrics pasted downloads the aligner's
  weights once (1.26 GB; its progress lines go to the job's log, not the page): its time, and "Lyrics: N words in M
  phrases" on the Done screen.
  A second song with lyrics downloads nothing. CI only shows that the launcher's variables let the download start.
- **The Done screen after a real chart on the GPU:** "Install into Clone Hero" and the zip are there at once, with no
  reload (the process's exit, CUDA's teardown included, takes longer than the tests' stand-in).
- **The header after the install's WSL restart** (step 6, before using the page): no "WSL has 7.8 GB of memory, under
  11 GB: allin1 is left out" note, and no "restart WSL" note.
- **The licence prompt** on the first install names the release's NOTICE.txt at its tag: does that link open?
- **uv's cache** is `~/.local/share/songcharter/runtime/uv-cache`: its `du -sh`, and no `~/.cache/uv` made by the
  install.
- **The memory rule rounds Windows' RAM up** (the owner's decision): on the friend's PC, record the RAM Windows
  reports (doctor's "Windows RAM") and the `memory=` the install wrote (12GB for a 16 GB PC, whatever it reports).
- **A GPU out of reach** (nvidia-smi failing, as after some Windows updates) cannot be arranged at will: if it happens
  on a first install, the warning at its end, and `songcharter doctor`'s note once the GPU answers.

## Added at the release gate

The GPU smoke test (2026-11-04, the owner's 5070, through the real installer in an isolated HOME with the Windows side
off; WSL had 22 GB, not 12) measured the cold chart of the test song with the friend's defaults. Recheck these with
`memory=12GB`, as A's distro has it:
- **VRAM:** the peak was 8,987 MiB of 12,227 (GPU 99%), during the guitar's takes. The friend's 4070 also has 12 GB,
  but Windows' desktop holds some of it (about 9.5 GB was free when it was last read): record the free VRAM before
  the chart and the peak during it, and whether any take fell back to the CPU.
- **RAM:** the chart's process tree peaked at 11.09 GiB RSS, during the sections (allin1), with no swap used. Under
  `memory=12GB` that is close to the limit: record the peak, and the swap used, from the job's memory samples.
- **Time:** cold 959 s for the 412 s song (the guitar 854 s: 4 takes of about 177-217 s each, 3.9 times one take);
  warm 37 s. Record A's times beside these.
- **The solos:** the CPU chart (1 take) of the test song leaves guitar gaps in solos 3C-3D (about 5:45-6:15) where the
  stem plays. Look at the same span in the 4-take chart's preview, and say whether the gaps are there too.
