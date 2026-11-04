# songcharter {{VERSION}} on Windows

songcharter turns a song file into a Clone Hero chart. It runs in WSL, the Linux that comes with Windows (here,
Ubuntu), so you set that up first, once.

## 1. Before you start

- **Windows 11**, or Windows 10 version 2004 or later (Settings > System > About shows the version).
- **About 20 GB free on C:**.
- **The NVIDIA driver, 580 or newer**, from nvidia.com or the NVIDIA app. To check: open Command Prompt (Start menu,
  type `cmd`), type `nvidia-smi`, press Enter, and read "Driver Version".
- **Virtualization on:** Task Manager (Ctrl+Shift+Esc) > Performance > CPU shows "Virtualization: Enabled". If it
  says Disabled, turn it on in the PC's BIOS/UEFI settings, where it is called Intel VT-x or AMD SVM. How you get
  there depends on the PC: search the web for your PC or motherboard model and "enable virtualization".

## 2. Set up WSL, once

1. Right-click the Start button and choose "Terminal (Admin)" (on Windows 10: "Windows PowerShell (Admin)"), and
   answer Yes when Windows asks.
2. Type `wsl --update` and press Enter. When it finishes, type `wsl --install` and press Enter. (The update comes
   first because an older WSL installs an older Ubuntu.)
3. Restart the PC when it finishes.
4. After the restart, an Ubuntu window opens (if not, open "Ubuntu" from the Start menu). Choose a user name, in
   lower-case letters with no spaces, and a password. Nothing shows while you type the password: that is normal.

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

## 4. Start songcharter

- Open the Start menu, type `songcharter` and press Enter. A window opens: keep it open while you use songcharter
  (closing it stops songcharter). Then your browser opens songcharter's page.
- If the shortcut does not work: open "Ubuntu" from the Start menu, type `songcharter` and press Enter.

## 5. Chart a song

- **Chart first, play after.** While a song charts, songcharter uses most of the PC's memory: on a 16 GB PC, Windows
  has about 4 GB left for a few minutes. Don't run games then.
- Drop the song file on the page (or use "Choose a file"), then press "Chart it".
- **Lyrics, if you want them on screen:** before "Chart it", paste the song's words into the "Paste lyrics" box,
  one line for each sung line. songcharter times the words you paste to the singing; it never looks lyrics up. The
  first song with lyrics downloads 1.26 GB, once.
- When it is done, look at the preview, then press "Install into Clone Hero". The first time, it may ask where your
  Clone Hero Songs folder is.
- In Clone Hero: Settings > General > Scan Songs.

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
