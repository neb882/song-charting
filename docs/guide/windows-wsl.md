# songcharter {{VERSION}} on Windows

songcharter turns a song file into a Clone Hero chart. It runs in WSL, the Linux that comes with Windows (here,
Ubuntu), so you set that up first, once.

## 1. Before you start

- **Windows 11**, or Windows 10 version 2004 or later (Settings > System > About shows the version).
- **About 20 GB free on C:**, and room for up to 8 GB more: when WSL runs short of memory during a chart, it keeps
  some of it in a file on C: (its swap file), which can grow to 8 GB.
- **The NVIDIA driver, 580 or newer**, from nvidia.com or the NVIDIA app. To check: open Command Prompt (Start menu,
  type `cmd`), type `nvidia-smi`, press Enter, and read "Driver Version".
- **Virtualization on:** Task Manager (Ctrl+Shift+Esc) > Performance > CPU shows "Virtualization: Enabled". If it
  says Disabled, turn it on in the PC's BIOS/UEFI settings, where it is called Intel VT-x or AMD SVM. How you get
  there depends on the PC: search the web for your PC or motherboard model and "enable virtualization".

## 2. Set up WSL, once

1. Right-click the Start button and choose "Terminal (Admin)" (on Windows 10: "Windows PowerShell (Admin)"), and
   answer Yes when Windows asks.
2. Type `wsl --update` and press Enter. When it finishes, type `wsl --install -d Ubuntu` and press Enter. (The
   update comes first because an older WSL installs an older Ubuntu. Naming Ubuntu matters: without it, a PC where
   WSL is already there gets no Linux at all, and the Start menu shows only "WSL Settings".)
3. Restart the PC when it finishes.
4. After the restart, an Ubuntu window opens (if not, open "Ubuntu" from the Start menu). Choose a user name, in
   lower-case letters with no spaces, and a password. Nothing shows while you type the password: that is normal.

- **No "Ubuntu" in the Start menu, only "WSL Settings"?** Then no Linux was installed. In Terminal (Admin), type
  `wsl --install -d Ubuntu` and press Enter, and restart if it asks. `wsl -l -v` lists what is installed: Ubuntu
  should be there.

- An error 0x80370102 or 0x80070003 means virtualization is off (see section 1).
- **Never install an NVIDIA driver inside Ubuntu.** The Windows driver already works there.

## 3. Install songcharter

In the Ubuntu window, paste this line and press Enter. (The button at the right of the box copies it; in the Ubuntu
window, a right-click or Ctrl+V pastes.)

```
curl -fsSLO https://github.com/neb882/song-charting/releases/download/v{{VERSION}}/install.sh && echo "{{INSTALL_SHA256}}  install.sh" | sha256sum -c - && bash install.sh
```

It downloads the installer, checks that it is the right file ("install.sh: OK"), and runs it. If it says
"install.sh: FAILED" instead, it stops there and runs nothing: don't run it another way, ask whoever sent you this
page.

- It shows how much it will download (about 4 GB with an NVIDIA GPU) and how long that takes, then asks
  "Continue? [Y/n]". Press Enter. (Enter answers yes to a question that ends in [Y/n].)
- If it stops halfway, paste the same line again: it carries on from where it stopped.
- If it says the guitar runs on the CPU because the driver is older than 580: update the driver, then paste the line
  again. It switches to the GPU build (about 3 GB).
- If it says the GPU is out of reach (this can happen after a Windows update): restart Windows, then paste the line
  again. It switches to the GPU build too.
- At the end, it sets how much memory WSL may use and restarts WSL, and the window closes.
- **When a new version is out,** songcharter's page says so in a box at the top, with the new version's install
  line and a **Copy** button (the page looks once a day, or an hour after a look that failed). To update: close the songcharter window, open Ubuntu from
  the Start menu, paste the line (a right-click or Ctrl+V) and press Enter, as above. If it says songcharter is still
  running, it has changed nothing: close the songcharter window, then paste the line again. Your charts, your Clone
  Hero folder and the big downloads are kept, so it fetches only what changed: usually a minute or two. "Later" hides
  the box until the page is opened again.
- **A song you charted with an older version and chart again:** "Install into Clone Hero" asks whether to replace
  the older chart, even when its folder has another name, so Clone Hero does not list the song twice.

## 4. Start songcharter

- Open the Start menu, type `songcharter` and press Enter. A window opens: keep it open while you use songcharter
  (closing it stops songcharter). Then your browser opens songcharter's page.
- If the shortcut does not work: open "Ubuntu" from the Start menu, type `songcharter` and press Enter.

## 5. Chart a song

- **Chart first, play after.** While a song charts, songcharter uses most of the PC's memory: on a 16 GB PC, Windows
  has about 4 GB left until the chart is done. Don't run games then.
- **How long it takes:** about 4 to 14 minutes for a 4-minute song with the default options (a busy or long song
  takes longer: a 9-minute song can take over half an hour). The page says how long when the chart starts, and the
  browser tab's title says what it is doing. Most of that is the guitar: songcharter charts it 4 times over (4
  "takes") and combines them into a better chart, and the page shows which take it is on ("take 2 of 4"). At the
  top of the options you choose "Best chart" (4 takes) or "Quick chart" (1 take), each with its minutes for your
  song: a 4-minute song's quick chart takes about 2 to 7 minutes. Once the first take is done, the page says how
  many more minutes it should take, from how long that take took. These times are estimates. (On a PC without a
  graphics card songcharter makes 1 take, and the page says so.)
- **If a guitar take fails on the graphics card** (a game, Clone Hero or a browser left open can take the memory it
  needs), songcharter runs that take again on the CPU, once a song, and carries on. The page says so: a note at the
  top, and "take 3 of 4 (on the CPU)". That take takes a few minutes longer. If a second take fails, or a take was
  stopped because the PC ran out of memory, the chart stops and the page says what to try.
- **A very long or very busy song's guitar** may be transcribed in pieces (more than the guitar model takes in one
  go), which songcharter joins into one chart; the Done screen then shows a note that says so.
- **Keep the PC awake while a song charts:** a chart takes long enough for the PC to go to sleep. While songcharter's
  page is on screen, it keeps the screen on and the PC awake; behind another tab, or with the browser minimized, it
  cannot. So for the evening, set its sleep to Never in Windows' power settings.
- **You can close the page while a song charts:** keep the songcharter window open (closing it stops the
  chart). To come back, start songcharter again from the Start menu: the page shows the chart where it is.
- Drop the song file on the page (or use "Choose a file"), then press "Chart it". The options you rarely need (the
  number of takes, the device, the preview) are under "More options".
- **Several songs for an evening:** drop several song files at once (or choose several), pick Best or Quick once for
  all of them, and press "Chart them": songcharter charts them one after the other, by itself, while you are away. The
  list under the chart shows each song: "Install" and "Look" (its own Done screen) once it is done, "Remove" while it
  waits; more songs can be added while one charts ("Add songs"). Keep your PC awake while these chart: in Windows
  Settings, set Sleep to Never for now (the page says so under the list); a PC that sleeps stops charting until it
  wakes. Leaving the page in front helps too. Cancel stops only the song charting; "Pause after this song" stops the list after
  it. If the songcharter window closes, the list waits: start songcharter again and press "Carry on". Lyrics and
  pictures are for one song at a time.
- **Your charts:** every song you have charted stays listed under "Your charts" on the first screen (folded once the
  list is long: click it to open it; the Done screen has a "Your charts" button too), newest first, with whether it
  passed its check. "Install" puts it into Clone Hero again (into a new Songs folder, say, or after you deleted it
  there), "Open" shows its folder, "Download the stems" gives the separated instruments when you saved them, and
  "Look" shows its preview and Listen for a day or so after charting. Nothing is deleted from the page: to delete a
  chart, Open its folder and delete it in Windows.
- **Lyrics, if you want them on screen:** before "Chart it", open "Lyrics" and paste the song's words into the box,
  one line for each sung line. songcharter times the words you paste to the singing; it never looks lyrics up. The
  first song with lyrics downloads 1.26 GB, once.
- **Pictures, if you want them:** a song file with its own cover picture gets it as the album art. Under "Pictures"
  (open it) in the options you can choose another album art, and a background image to show behind the highway (JPEG, PNG or
  WebP). To see song backgrounds in Clone Hero, turn on Settings > Gameplay > "Use Song Backgrounds".
- **When you miss a note, that instrument's sound stops** until you hit again, as on Clone Hero's official songs: the
  guitar, bass and drums each get a sound file of their own (made from the separated instruments, so a little of the
  guitar can still be heard in the rest while it is muted). If you would rather the music never drops out, tick "One
  audio file" under "Audio" in the options.
- **The separated instruments for sampling:** tick "Also save the separated instruments (stems)" under "Audio". The
  six instruments (drums, bass, guitar, piano, vocals, and "other" for the rest) are saved as lossless FLAC files
  that line up with your song file, in a folder beside the song's; the options say how much disk they take (about
  190 MB for a 4-minute song). When the song is done, "Download the stems" saves them as one zip to your Downloads
  folder. Piano and "other" come out the least clean.
- When it is done, the page shows "Ready" at the top with the song's name, "Open folder" (the song's folder in
  Windows' File Explorer) and "Install into Clone Hero" right under it. Press Install (the preview and Listen,
  further down, are there for a look first if you want one). The first time, it may ask where your Clone Hero Songs
  folder is: the box then holds a guess, where Clone Hero usually keeps it; change it to your Songs folder if yours
  is elsewhere.
- **The preview's pictures** open larger on the page when you click them (Escape, or Close, puts them away; the
  arrow keys go to the page before or after). Under "Worth a look", each time is a link to the page that shows it,
  and "Listen here" plays the chart from just before it.
- **Listen to the chart** without playing it: under the preview, choose a part and a level and press "Listen". After
  a few seconds the page plays the chart over the song, a tone for each note (green lowest, orange highest; HOPOs
  softer than strums) or a drum sound for each hit. Listen for a note that comes late or not at all, a part playing
  where the song is quiet, or a sustain that ends too early.
- In Clone Hero: Settings > General > Scan Songs.
- **Before you play, close the songcharter window** (and any Ubuntu window). WSL keeps the memory it took while one
  is open; once they are closed, WSL stops and Windows gets that memory back. That can take a minute.

## 6. If something goes wrong

- **Turn off any VPN while installing:** it can block or slow the downloads.
- **If downloads keep failing with certificate errors**, usually after the PC slept and WSL's clock went wrong: in
  Terminal (right-click Start), type `wsl --shutdown`, then open Ubuntu and paste the install line again.
- The "Diagnostics" link at the bottom of songcharter's page saves a zip to your Downloads folder (logs and settings,
  no audio). Send it. Or, in Ubuntu, type `songcharter diagnostics --out diagnostics.zip`: the line that
  starts "in Windows:" says where the zip is.

## 7. Remove it

- In Ubuntu, type `songcharter uninstall`. It removes songcharter and its Start-menu shortcut. When it asks about the
  downloads, answer No (press Enter) to keep them: a later reinstall then downloads only about 1 MB. If it asks to
  restore `.wslconfig`, answer Yes (y) to give WSL back the memory setting it had before songcharter.
- To remove everything, after `songcharter uninstall`: in Terminal (Admin), type `wsl --unregister Ubuntu`. (`songcharter uninstall` prints this
  line at its end, with your Ubuntu's name.)

  **Warning: this deletes everything in that Ubuntu, not only songcharter. Use it only if you keep nothing else
  there.**

## 8. Licences

songcharter's code is MIT, apart from its port of the ADTOF drums model, which is for non-commercial use only. So
are some of the models it downloads (see
[NOTICE.txt](https://github.com/neb882/song-charting/blob/v{{VERSION}}/packaging/NOTICE.txt)). Charts you make are
yours; song.ogg is made from your recording, and sharing it is sharing the song.
