# M4-08: results

Written by the director from the owner's notes and screenshots. Hardware facts, times and sizes only (CLAUDE.md): a
PC is described by what a check needs.

## Part A, the core set (2026-11-04, the owner's RTX 5070 PC)

The owner ran the core set in a fresh Ubuntu-26.04 distro, from the published v0.1.0 pre-release, with
`--windows-ram-gb 16` so the install wrote a 16 GB PC's `.wslconfig`. The PC: an RTX 5070 (12 GB), a driver new enough
for the cu132 lane, more than 16 GB of RAM, C: with ample space.

| Check | Result |
|---|---|
| A17: the line from the release page | installs: "install.sh: OK", the app's tarball and uv checked against their hashes, no failure; the licence prompt names the release's NOTICE.txt at its tag |
| A1: the download announced | about 4.2 GB (3.2 GB of Python packages for cu132, then about 1 GB of Node, autochart, models); the install's total time was not recorded |
| A2: the lane | `cu132` (compute capability 12.0, a driver new enough) |
| A3: WSL's memory | wrote `memory=12GB` and `swap=8GB` ("Windows has 16 GB of RAM"), printed the restart message; the owner had started the distro from PowerShell, so the session returned there |
| The install's last lines | doctor OK; WSL had about 16 GB before the restart, so no "under 8 GB" problem on this PC |
| A4: after the restart | `.wslconfig memory 12.0 GB: in force`; MemTotal 12,249,896 kB; swap 0 of 8 GB; doctor OK |
| A5: the page | opens; the header says "GPU: NVIDIA GeForce RTX 5070 (12 GB)" and "guitar on the GPU", with no memory note |
| `autochart_cuda` | loads (CUDA 15 nodes, CPU 2); allin1 runs on CUDA |
| The server | listens on 127.0.0.1:8765 only |
| A6: the test song, 1 take | about 5 min 3 s in all (target 8 min): decode 1 s, separate 9 s (cuda), drums 4 s, bass 18 s, sections 40 s (allin1, cuda), guitar 3 min 24 s, build 16 s, preview 11 s; gate OK (0 errors, 3 warnings), playable, 0 chart issues |
| A7: the defaults | the 3 takes after the cached first: 9 min 27 s (566.6 s, about 189 s a take); 601.1 s in all; gate OK |
| The solos | the 1-take charts (this one on the GPU, and the release gate's on the CPU) leave guitar gaps in the solos (about 5:51-5:55 and 6:12-6:22); the 4-take chart has none there (its one flagged gap is 2:49.0-2:50.7, one measure). The 4-take default fills them. |
| Lyrics | 557 words in 72 phrases, median word score 0.488 (the warning is under 0.25); the lyrics stage 27 s with the first-use download of the aligner's weights |
| Memory | every chart finished under `memory=12GB`, none killed; the loggers' per-stage RAM, swap and VRAM figures were not collected |

**Not run** (the owner chose to send the release to the friend after the core charts): the install into Clone Hero
and playing it (A11, A12, and the lyrics in Clone Hero), cancel (A8), closing the window mid-chart (A9), the
diagnostics zip's checks (A24), and the rest of part A (A10, A13, A16, A18-A23, Take Me Out). Part B covers the
install into Clone Hero and playing on the friend's PC.

**Seen on the way** (polish, PROGRESS's deferred list): an HF Hub "unauthenticated requests" warning and npm's
deprecation warnings during the install; allin1's download bars as wide as the terminal; no "done" line after the
ADTOF weights' download; an MP3 with no artist tag charts as "Unknown" (the file name is not read for "Artist -
Title"); the song folder's name is cut at 40 characters mid-word; with Documents in OneDrive and no `Clone Hero\Songs`
folder there, the page asks for the Songs folder, filled with its guess.

## Part B, the friend's PC

Not yet run.
