# The web UI: what to improve (a second model's review, 2026-11-07)

Read: DESIGN 4.4-4.5, the guide's sections 4-6, server.py, jobs.py, index.html, app.js, app.css, the Listen
report. Seen: the four screens through a stand-in server on main's code (no charting; a golden folder copied under a
made-up name, its preview rendered by preview.py in 12 s), Chromium at 1280x860 and 700 px, light and dark; the
shots were looked at and deleted. The page is sound: responsive, dark mode right, no console errors, the guards and
the SSE resume work. The findings are about what the friend meets, not about bugs. None of the twelve touches
anything that charts; "size" is a builder's hours with tests, a judgement.

## The improvements, most valuable first

1. **The finished chart lands below the fold.** When the result comes, "Ready" and the install button sit under the
   nine completed stage rows (the Done screen at y=1025 in an 860 px window; 1200 px with the update box). After a
   10-40 minute wait, often in a background tab, he sees a list of green ticks and must scroll. `finish()`
   (app.js:423) only unhides `#done-screen`. Change: fold the stages into one line ("Charted in 12 min 43 s", a
   `<details>` for the rows), scroll the Done screen into view, set `document.title` while it runs ("take 3 of 4 -
   songcharter") and when it ends ("Ready - songcharter"), and give the tab a real favicon (`index.html:7` is
   `data:,`). 2-3 h. Quick win.

2. **"Install into Clone Hero" is the last thing on the page.** The Done screen's order is text, lyrics line,
   preview, pages, flags, Listen, then "Play it" (`index.html:146-199`). His job is to install; the preview and
   Listen are for a look. Change: put "Play it" first, right under "Ready", the preview and Listen after it, and
   the `<pre>` summary (engine lines such as "agreement 0.91") inside a `<details>`. 1-2 h. Quick win.

3. **No idea how long it will take.** The progress screen shows elapsed time per stage and "take 3 of 4", no
   total and no estimate; DESIGN 4.5 promised "time estimates". The guide carries them as prose. Change: a line
   under the title, "Usually about N-M minutes for a song of this length", from the song's duration (the upload
   knows the file; `ffprobe` is already there) and per-minute rates measured on the golden runs, scaled by takes and
   CPU/GPU; refine from the last chart's `stage_end` seconds kept in `state/`. 3-5 h. v0.4 if the rates are easy to
   fix, else later.

4. **"Keep the PC awake" is on him.** The guide says to set sleep to Never. Change: `navigator.wakeLock.request
   ("screen")` while a job runs (Edge/Chrome on localhost allow it), released at the end; it holds only while the tab
   is visible, so the guide's line stays. Plus one sentence on the progress screen: "Keep the black songcharter window
   open. You can close this tab and come back: the page picks the chart up again." 1 h. Quick win.

5. **The Linux path on the Done screen.** "The song folder is in /home/.../songs/<name>" (`app.js:408`, from the
   result event). He cannot open it, and "Open folder" appears only after an install. Change: drop the path from
   the sentence; let `POST /api/open` take `"built"` (the result's folder) so "Open folder" works before an install
   too; show the Windows (`\\wsl$`) form only in the hover text. 1-2 h.

6. **Flags without a way to the picture.** "Worth a look" says "guitar 1:12-1:19 (Verse 2): ..." and the pages are
   thumbnails named Page 1, 2, 3 (unreadable at 9.5 rem, each opening in a new tab). Change: parse the flag's mm:ss
   and link it to its page (`floor(start/60)+1`, `page_s` from the result), and open the pages and the overview in an
   in-page lightbox (one `<dialog>`, `app.js` only) rather than a new tab. The overview (1620 px wide) shown at 820
   px is not readable either; a lightbox fixes that too. 2-3 h.

7. **The Songs folder asked as a bare text field.** Off Documents, "songcharter did not find your Clone Hero Songs
   folder: give it below" with an empty box (`app.js:617`): a non-technical person types a Windows path. The browser
   cannot pick a folder's path. Change: prefill with the best guess always (today only when none is found), and try
   Clone Hero's own settings for the songs path (DESIGN says its keys are unverified, M4-08: verify on the owner's PC
   first). 2-4 h, the verification on a real PC the gate. Later.

8. **The options form is 2,000 px of fields he never changes.** Expert is a disabled checked box, "Guitar takes"
   a number box whose only told use is typing 1, Device, "Make a preview", Lyrics, Pictures. Change: "Chart it" at
   the top as well; a two-way choice "Best chart (4 takes, about 12 min) / Quick chart (1 take, about 5 min)" in
   place of the number box (the number stays under "More"); Lyrics and Pictures in a `<details>`; Device and
   preview under "More options". 2-3 h. Judgement: v0.4 if the owner agrees the defaults are right for him.

9. **One song at a time, nothing remembered.** A second drop while a chart runs gives "A chart is running
   already", and "Chart another song" forgets the last one (no list, no re-install). An evening's queue of songs
   and a "Your charts" list (name, date, Install, Open) would fit how he uses it. jobs.py's one-job design is the
   cost: 8-16 h. Later, and worth a design note first.

10. **Listen does not point at the flag.** The box is below the flags with its own Part/Level; a flag for the
    guitar at 1:12 should start the guitar's render there (`audio.currentTime`). 1 h, with 6.

11. **The drop zone has `tabindex=0` but no key handler**, so Enter/Space does nothing (`app.js:230`). Add a
    keydown that opens the picker. 0.5 h.

12. **The update box sits above a running chart** and says "close the songcharter window" while one charts.
    Hide it (or add "after this chart is done") while a job runs; show it again at the end. 0.5 h.

## For v0.4 (quick wins): 1, 2, 4, and 11-12 as one small order; 3 and 8 if the owner wants the estimates in.
## Later: 5-7, 9-10 (9 after a design note).

Not seen: a real install, a Listen render (the Listen report's screenshot covers it), the page on Edge.

## The orchestrator's routing (2026-11-07)

The owner left the choices to the orchestrator: items 1, 2, 3 (the time estimate, which DESIGN 4.5 promised), 4, 11 and 12 become M7-10 for v0.4; 8 (the quick/best choice) and 5-7, 9-10 wait for a UI pass after v0.4 (M5-99).
