// songcharter's page (M4-04, M4-06, M4-11, M5-07, M6-09, M7-10, M8-04): drop a song, choose Best or Quick (on a GPU)
// and the options (the rest folded: the takes, device and preview, the lyrics, the pictures), follow the chart (how
// long it usually takes, and how long is left once the first take is timed; the tab's title saying where it is, the
// screen kept awake), cancel it; then "Ready" scrolled into view with the song's name and Open folder, the install
// into Clone Hero first, the zip, the album art, the preview (its pages in a lightbox, each flag linked to its page
// and to Listen at its time) and the chart to listen to, and the diagnostics in the footer; above it all, the update
// notice when a newer version is out, put away while a chart runs. No framework, no build step. Every request sends
// X-Songcharter: 1 (the server's guard for anything but a GET). The job's events come over a streamed fetch of
// /api/jobs/current/events (Server-Sent Events), which can send that header too, and which resumes after the last
// event it saw when the connection drops; a reload reattaches to the current job.
"use strict";

const HEADER = { "X-Songcharter": "1" };
const CLOSING = new Set(["result", "error", "cancelled"]);
const LABELS = {
  decode: "Read the song", separate: "Separate the instruments", drums: "Drums", bass: "Bass",
  sections: "Sections", lyrics: "Lyrics", guitar: "Guitar", assemble: "Build and check the chart", preview: "Preview",
};
const DISMISSED = "songcharter.dismissed";   // sessionStorage: the finished job "Chart another song" put away
// the status asked again this long (ms) after the start while it has no `update`: the server's check starts once this
// page is served, so the first status usually comes before its answer (one request, 5 s at most for each of two)
const UPDATE_ASKS = [2000, 6000, 15000];
// the job's events asked for again this many times in a row, 2 s apart, before the page says songcharter has stopped
// (M7-10's review: a closed songcharter window stops the chart, and the page went on holding the screen awake)
const FOLLOW_TRIES = 10;

const APP = "songcharter";   // the tab's title, after what the page is doing
const $ = (id) => document.getElementById(id);
const state = { status: null, upload: null, job: null, stages: {}, offset: 0, ticker: null, follow: 0, ch: null,
  images: { album_art: null, background: null }, sending: 0, version: null, update: null, later: false,
  listen: { parts: {}, job: null }, running: false, wake: null, remaining: null, asking: false,
  box: { items: [], at: 0 } };
// the Listen control's names for the parts and levels the chart has (the results' `listen`)
const PART_NAMES = { guitar: "Guitar", bass: "Bass", drums: "Drums" };
const LEVEL_NAMES = { expert: "Expert", hard: "Hard", medium: "Medium", easy: "Easy" };
// the pictures' pickers: the option each sets (an image upload's id) and what its line says when none is chosen
const PICTURES = { album_art: "None chosen: the song file's own picture, if it has one", background: "None chosen" };

function show(screen) {
  for (const id of ["drop-screen", "options-screen", "progress-screen", "done-screen"]) $(id).hidden = id !== screen;
}

function text(el, value) { el.textContent = value == null ? "" : String(value); return el; }

function make(tag, cls, value) {
  const el = document.createElement(tag);
  if (cls) el.className = cls;
  if (value != null) el.textContent = value;
  return el;
}

async function api(method, path, body) {
  const init = { method, headers: { ...HEADER }, cache: "no-store" };
  if (body !== undefined) {
    init.headers["Content-Type"] = "application/json";
    init.body = JSON.stringify(body);
  }
  const r = await fetch(path, init);
  let data = null;
  try { data = await r.json(); } catch (e) { data = null; }
  return { status: r.status, data: data || {} };
}

function stageLabel(name) { return LABELS[name] || name; }

function seconds(s) {
  s = Math.max(0, Math.round(s));
  return s < 60 ? `${s} s` : `${Math.floor(s / 60)} min ${String(s % 60).padStart(2, "0")} s`;
}

function serverNow() { return Date.now() / 1000 + state.offset; }

function mmss(s) {
  s = Math.max(0, Math.round(s));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

// the tab's title: what the page is doing, so a tab in the background says it too
function setTitle(what) { document.title = what ? `${what} - ${APP}` : APP; }

// ------------------------------------------------------------------------------------------------ the header

function renderStatus(st) {
  const dev = st.device || {};
  const gpu = st.gpu;
  if (dev.chosen === "cuda" && gpu) {
    const gb = gpu.vram_mb ? ` (${Math.round(gpu.vram_mb / 1024)} GB)` : "";
    text($("machine"), `GPU: ${gpu.name}${gb}`);
  } else if (dev.chosen === "cuda") {
    text($("machine"), "GPU: CUDA");
  } else if (dev.chosen) {
    text($("machine"), `CPU mode: ${dev.reason || "no GPU"}`);
  } else {
    text($("machine"), st.error ? `The machine check failed: ${st.error}` : "This PC was not checked");
  }
  if (st.guitar_device === "cuda") text($("guitar"), "guitar on the GPU");
  else if (st.guitar_device) text($("guitar"), `guitar on the CPU: ${st.guitar_reason || ""}`);
  else text($("guitar"), "");
  // doctor's problems (the disk measured again on every status): shown, never blocking "Chart it"
  const problems = st.problems || [];
  $("problems").replaceChildren(...problems.map((p) => make("li", null, p)));
  $("problems").hidden = !problems.length;
  const notes = $("notes");
  notes.replaceChildren(...(st.notes || []).map((n) => make("li", null, n)));
  $("details").hidden = !(st.notes || []).length;
}

// ------------------------------------------------------------------------------------------------ the update notice

// The status's `update` ({"version", "line", "url"}): the box under the header with the install line, a Copy button
// and the release page; "Later" puts it away for this page load. It never stops anything else on the page.
function renderUpdate(up, have) {
  const box = $("update");
  // while a chart runs, its line ("close the songcharter window") would stop the chart: shown again at its end
  if (!up || state.later || state.running) { box.hidden = true; return; }
  const yours = have ? ` (you have ${have})` : "";
  if (up.line) {
    text($("update-text"), `songcharter ${up.version} is out${yours}. To update: close the songcharter window, open Ubuntu from the Start menu, paste this line and press Enter:`);
  } else {
    text($("update-text"), `songcharter ${up.version} is out${yours}. Its release page has the line to paste in Ubuntu, and the steps:`);
  }
  $("update-copy-row").hidden = !up.line;
  if ($("update-line").value !== (up.line || "")) {   // a new line: the Copy button starts again
    $("update-line").value = up.line || "";
    $("update-copied").hidden = true;
    text($("update-copy"), "Copy");
  }
  const link = $("update-url");
  link.hidden = !(typeof up.url === "string" && up.url.startsWith("https://"));
  if (!link.hidden) link.href = up.url;
  box.hidden = false;
}

async function showUpdate(up) {
  state.update = up || null;
  if (up && !state.later && state.version == null) {   // "you have": the version this server runs
    try { state.version = (await api("GET", "/api/hello")).data.version || ""; } catch (e) { state.version = ""; }
  }
  renderUpdate(state.update, state.version);
}

// navigator.clipboard is there only in a secure context, which localhost is and the fallback address is not: there
// the button selects the line for the person to copy
async function copyLine() {
  const line = $("update-line");
  const said = $("update-copied");
  const clip = typeof navigator !== "undefined" ? navigator.clipboard : undefined;
  if (clip && typeof clip.writeText === "function") {
    try {
      await clip.writeText(line.value);
      text($("update-copy"), "Copied");
      text(said, "Copied. In the Ubuntu window, a right-click or Ctrl+V pastes it.").hidden = false;
      return;
    } catch (e) {
      // refused: select it instead
    }
  }
  line.focus();
  line.select();
  text($("update-copy"), "Select and copy");
  text(said, "This browser does not let the page copy here: the line is selected, so press Ctrl+C to copy it.").hidden = false;
}

function later() {
  state.later = true;
  $("update").hidden = true;
}

function askForUpdate() {
  if (state.update || state.later) return;
  refreshStatus();
}

// ------------------------------------------------------------------------------------------------ drop and upload

function dropError(message) {
  const el = $("drop-error");
  el.hidden = !message;
  text(el, message);
}

function upload(file) {
  dropError("");
  $("upload").hidden = false;
  text($("upload-name"), `Uploading ${file.name}…`);
  const bar = $("upload-bar");
  bar.value = 0;
  const xhr = new XMLHttpRequest();
  xhr.open("POST", "/api/upload");
  xhr.setRequestHeader("X-Songcharter", "1");
  xhr.setRequestHeader("X-Filename", encodeURIComponent(file.name));
  xhr.upload.addEventListener("progress", (e) => { if (e.lengthComputable) bar.value = e.loaded / e.total; });
  xhr.addEventListener("load", () => {
    $("upload").hidden = true;
    let data = {};
    try { data = JSON.parse(xhr.responseText); } catch (e) { data = {}; }
    if (xhr.status === 200) {
      state.upload = data;
      fillOptions(data);
      show("options-screen");
    } else if (xhr.status === 415) {
      dropError(`That is not a song file songcharter takes. ${data.error || ""}`);
    } else {
      dropError(data.error || `The upload failed (${xhr.status}).`);
    }
  });
  xhr.addEventListener("error", () => { $("upload").hidden = true; dropError("The upload failed: is songcharter still running?"); });
  xhr.send(file);
}

function setupDrop() {
  const zone = $("drop");
  for (const kind of ["dragenter", "dragover"]) {
    zone.addEventListener(kind, (e) => { e.preventDefault(); zone.classList.add("over"); });
  }
  for (const kind of ["dragleave", "drop"]) zone.addEventListener(kind, () => zone.classList.remove("over"));
  zone.addEventListener("drop", (e) => {
    e.preventDefault();
    const file = e.dataTransfer && e.dataTransfer.files[0];
    if (file) upload(file);
  });
  // the zone takes the keyboard's focus (tabindex 0): Enter or Space opens the file chooser, as a click on its button
  zone.addEventListener("keydown", (e) => {
    if ((e.key === "Enter" || e.key === " ") && !e.altKey && !e.ctrlKey && !e.metaKey && !e.shiftKey) {
      e.preventDefault();   // Space would scroll the page
      $("file").click();
    }
  });
  // a file dropped beside the zone must not navigate away from the page
  window.addEventListener("dragover", (e) => e.preventDefault());
  window.addEventListener("drop", (e) => e.preventDefault());
  $("file").addEventListener("change", (e) => { const f = e.target.files[0]; if (f) upload(f); e.target.value = ""; });
}

// ------------------------------------------------------------------------------------------------ options

const META = { title: "name", artist: "artist", album: "album", year: "year", genre: "genre" };

// the two "Chart it" buttons, at the top of the options and at their end
function chartButtons(disabled) {
  for (const id of ["chart", "chart-top"]) $(id).disabled = disabled;
}

// Best or Quick (M8-04): on a PC that charts the guitar on the GPU, a choice between the defaults (4 takes) and 1
// take, each with its minutes for this song (the upload's `choices`); elsewhere one take, said in a line. The choice
// only fills the "Guitar takes" box under More options (Best: empty, the default; Quick: 1), so what is sent is what
// that box says, as before; a number typed there checks the matching choice, or neither.
function minutes(est) {
  return est && est.low_min > 0 && est.high_min > 0 ? `about ${est.low_min} to ${est.high_min} minutes` : "";
}

function fillChoice(choices) {
  const c = choices || {};
  const best = minutes(c.best), quick = minutes(c.quick);
  $("choice").hidden = !c.gpu;
  $("choice-cpu").hidden = !!c.gpu;
  if (c.gpu) {
    const takes = (c.best && c.best.takes) || 4;
    text($("best-label"), `Best chart (${takes} guitar takes${best ? `, ${best}` : ""})`);
    text($("quick-label"), `Quick chart (1 take${quick ? `, ${quick}` : ""})`);
  } else {
    text($("choice-cpu"), "This PC charts the guitar on the CPU, so it makes 1 guitar take" +
      (best ? `: ${best} for this song.` : "."));
  }
}

function chosen() {
  const on = [...$("options").querySelectorAll("input[name=how]")].find((r) => r.checked);
  return on ? on.value : null;
}

function choose() {
  $("options").elements.takes.value = chosen() === "quick" ? "1" : "";
}

function typedTakes() {
  const v = $("options").elements.takes.value.trim();
  const want = v === "" ? "best" : v === "1" ? "quick" : null;
  for (const r of $("options").querySelectorAll("input[name=how]")) r.checked = r.value === want;
}

function fillOptions(up) {
  const form = $("options");
  form.reset();
  for (const id of ["more", "lyrics-box", "pictures-box"]) $(id).open = false;
  fillChoice(up.choices);
  text($("song-name"), `${up.name} (${(up.bytes / 1e6).toFixed(1)} MB)`);
  const tags = up.tags || {}, origin = up.origin || {};
  for (const [field, key] of Object.entries(META)) {
    const input = form.elements[field];
    const value = tags[key];
    // a placeholder ("Unknown") stays a placeholder: left empty, the chart gets it all the same
    input.value = value != null && origin[key] !== "default" ? String(value) : "";
    input.placeholder = origin[key] === "default" && value != null ? String(value) : "";
  }
  const d = (state.status && state.status.defaults) || {};
  for (const box of form.querySelectorAll("input[name=instruments]")) {
    box.checked = !d.instruments || d.instruments.includes(box.value);
  }
  soloNames();
  for (const key of Object.keys(PICTURES)) clearPicture(key);
  text($("options-error"), "").hidden = true;
}

// ------------------------------------------------------------------------------------------------ the pictures

function clearPicture(key) {
  state.images[key] = null;
  text($(`${key}-name`), PICTURES[key]);
  $(`${key}-remove`).hidden = true;
  text($(`${key}-error`), "").hidden = true;
}

// a picture goes up as the song does (POST /api/upload/image); the chart gets its upload id
function uploadPicture(key, file) {
  clearPicture(key);
  text($(`${key}-name`), `Uploading ${file.name}…`);
  state.sending += 1;
  chartButtons(true);
  const done = () => { state.sending -= 1; chartButtons(state.sending > 0); };
  const xhr = new XMLHttpRequest();
  xhr.open("POST", "/api/upload/image");
  xhr.setRequestHeader("X-Songcharter", "1");
  xhr.setRequestHeader("X-Filename", encodeURIComponent(file.name));
  xhr.addEventListener("load", () => {
    done();
    let data = {};
    try { data = JSON.parse(xhr.responseText); } catch (e) { data = {}; }
    if (xhr.status === 200) {
      state.images[key] = data.id;
      text($(`${key}-name`), `${data.name} (${data.width}×${data.height})`);
      $(`${key}-remove`).hidden = false;
    } else {
      clearPicture(key);
      text($(`${key}-error`), data.error || `The upload failed (${xhr.status}).`).hidden = false;
    }
  });
  xhr.addEventListener("error", () => {
    done();
    clearPicture(key);
    text($(`${key}-error`), "The upload failed: is songcharter still running?").hidden = false;
  });
  xhr.send(file);
}

function setupPictures() {
  for (const key of Object.keys(PICTURES)) {
    $(`${key}-file`).addEventListener("change", (e) => {
      const f = e.target.files[0];
      if (f) uploadPicture(key, f);
      e.target.value = "";
    });
    $(`${key}-remove`).addEventListener("click", () => clearPicture(key));
  }
}

function soloNames() {
  $("solo-names-label").hidden = $("options").elements.solos.value !== "names";
}

function readOptions() {
  const form = $("options"), f = form.elements;
  const options = {};
  for (const field of Object.keys(META)) {
    const v = f[field].value.trim();
    if (v) options[field] = v;
  }
  options.instruments = [...form.querySelectorAll("input[name=instruments]:checked")].map((b) => b.value);
  options.levels = [...form.querySelectorAll("input[name=levels]:checked")].map((b) => b.value);
  if (f.solos.value === "names") {
    options.solos = f.solo_names.value.split(",").map((s) => s.trim()).filter(Boolean);
  } else {
    options.solos = f.solos.value;
  }
  const takes = f.takes.value.trim();
  if (takes) options.takes = Number(takes);
  options.device = f.device.value;
  options.preview = f.preview.checked;
  const lyrics = f.lyrics.value;   // as pasted; the server keeps it out of every record
  if (lyrics.trim()) options.lyrics = lyrics;
  for (const key of Object.keys(PICTURES)) if (state.images[key]) options[key] = state.images[key];
  return options;
}

async function chartIt(e) {
  e.preventDefault();
  const err = $("options-error");
  err.hidden = true;
  const options = readOptions();
  if (options.takes !== undefined && !Number.isInteger(options.takes)) {
    text(err, "Guitar takes is a whole number: 1, or 3 or more.").hidden = false;
    return;
  }
  chartButtons(true);
  try {
    const r = await api("POST", "/api/jobs", { upload: state.upload.id, options });
    if (r.status === 202) {
      attach();
    } else if (r.status === 409) {
      text(err, "A chart is running already: showing it.").hidden = false;
      attach();
    } else {
      text(err, r.data.error || `It could not start (${r.status}).`).hidden = false;
    }
  } catch (x) {
    text(err, "songcharter does not answer: is it still running?").hidden = false;
  } finally {
    chartButtons(false);
  }
}

// ------------------------------------------------------------------------------------------------ progress

// "Usually about N to M minutes ..." (the job's estimate: the server's estimate.for_job), or "" without one
function estimateText(est) {
  if (!est || !(est.low_min > 0) || !(est.high_min > 0)) return "";
  const length = est.seconds > 0 ? ` (${mmss(est.seconds)})` : "";
  const range = `Usually about ${est.low_min} to ${est.high_min} minutes for a song of this length${length}`;
  if (!est.takes) return `${range}. That is an estimate.`;
  const where = est.device === "cuda" ? "the GPU" : "the CPU";
  return `${range}, with ${est.takes} guitar take${est.takes === 1 ? "" : "s"} on ${where}. That is an estimate: ` +
         "a dense song takes longer, as the guitar's time grows with the notes it writes.";
}

// M8-04: how long is left once the guitar's first take is timed (the job's `remaining`: estimate.remaining on the
// server, from when the second take started, or the guitar ended), counted down on the page's clock; the first
// estimate stays above it, struck through
function roundMinutes(low, high) {   // estimate.round_minutes
  let lo = Math.max(1, Math.floor(low / 60));
  let hi = Math.ceil(high / 60);
  if (lo >= 30) lo = Math.floor(lo / 5) * 5;
  if (hi >= 30) hi = Math.ceil(hi / 5) * 5;
  return [lo, Math.max(hi, lo + 1)];
}

function remainingText(rem, now) {
  if (!rem || !(rem.high_s > 0) || rem.from == null) return "";
  const gone = Math.max(0, now - rem.from);
  const low = rem.low_s - gone, high = rem.high_s - gone;
  if (high <= 0) return "Nearly done, or taking longer than estimated.";
  const [lo, hi] = roundMinutes(Math.max(0, low), high);
  return `About ${lo} to ${hi} more minutes` + (rem.takes_left > 0 ?
    ", from how long the first guitar take took." : ": the guitar is done.");
}

function renderRemaining() {
  const line = remainingText(state.remaining, serverNow());
  text($("progress-remaining"), line).hidden = !line;
  $("progress-estimate").classList.toggle("struck", !!line);
}

// the job's snapshot carries `remaining`: asked for when a take or the guitar's end may have changed it
async function askRemaining() {
  if (state.asking) return;
  state.asking = true;
  try {
    const r = await api("GET", "/api/jobs/current");
    if (r.status === 200 && state.job && r.data.job === state.job.job && state.running) {
      state.remaining = r.data.remaining || null;
      renderRemaining();
    }
  } catch (e) {
    // the events' own retries say when songcharter is gone
  } finally {
    state.asking = false;
  }
}

function resetProgress(job) {
  state.stages = {};
  state.remaining = (job && job.remaining) || null;
  $("stages").replaceChildren();
  $("warnings").replaceChildren();
  $("fallbacks").replaceChildren();
  $("cancel").disabled = false;
  $("cancel").hidden = false;
  text($("progress-title"), "3. Charting");
  text($("progress-song"), job && job.upload ? job.upload.name : "");
  const est = estimateText(job && job.estimate);
  text($("progress-estimate"), est).hidden = !est;
  renderRemaining();
  $("progress-keep").hidden = false;
  $("stages-box").open = true;   // the rows while it runs; folded into one line at the end
  text($("stages-line"), "").hidden = true;
}

function stageRow(name) {
  if (state.stages[name]) return state.stages[name];
  const li = make("li", "stage pending");
  const icon = make("span", "icon", "○");
  const label = make("span", "label", stageLabel(name));
  const time = make("span", "time");
  const detail = make("div", "detail");
  const takes = make("div", "takes");
  li.append(icon, label, time, detail, takes);
  $("stages").append(li);
  const row = { li, icon, label, time, detail, takes, started: null, ended: false };
  state.stages[name] = row;
  return row;
}

function setRow(row, cls, icon) {
  row.li.className = `stage ${cls}`;
  text(row.icon, icon);
}

function tick() {
  for (const row of Object.values(state.stages)) {
    if (row.started != null && !row.ended) text(row.time, seconds(serverNow() - row.started));
  }
  if (state.remaining) renderRemaining();
}

function stopRunningRows(how) {
  for (const row of Object.values(state.stages)) {
    if (row.started != null && !row.ended) {
      row.ended = true;
      setRow(row, "stopped", "✕");
      text(row.time, how);
    }
  }
}

function handle(ev) {
  switch (ev.event) {
    case "plan":
      for (const name of ev.stages || []) stageRow(name);
      break;
    case "stage_start": {
      const row = stageRow(ev.stage);
      row.started = ev.at;
      row.ended = false;
      setRow(row, "running", "◐");
      text(row.detail, ev.detail);
      setTitle(stageLabel(ev.stage));
      break;
    }
    case "stage_end": {
      const row = stageRow(ev.stage);
      row.ended = true;
      setRow(row, ev.cached ? "cached" : "done", "✓");
      text(row.detail, ev.detail);
      text(row.time, ev.cached ? `${seconds(ev.seconds)} (cached)` : seconds(ev.seconds));
      text(row.takes, "");
      if (ev.stage === "guitar" && state.running) askRemaining();
      break;
    }
    case "take":
      // a take run again on the CPU after its GPU run failed says so (the banner above gives why)
      text(stageRow("guitar").takes,
           `take ${ev.index} of ${ev.count}${ev.device === "cpu" ? " (on the CPU)" : ""}`);
      setTitle(`${stageLabel("guitar")}: take ${ev.index} of ${ev.count}`);
      if (state.running && !state.remaining) askRemaining();   // from the second take on, the server times the first
      break;
    case "warning":
      $("warnings").append(make("li", null, ev.text));
      break;
    case "fallback": {
      const where = ev.to === "cpu" ? "the CPU" : ev.to;
      $("fallbacks").append(make("p", "banner", `${stageLabel(ev.stage)} runs on ${where}: ${ev.reason}`));
      break;
    }
    case "result": {
      stopRunningRows("stopped");
      const name = songName(ev.folder);
      finish(ev.ok ? "Ready" : "The check failed",
             ev.ok ? `${name} is charted and passed its check.` :
               `${name} did not pass the check, so it is kept for a look (Open folder), not for Clone Hero.`,
             ev.summary, { at: ev.at, line: "Charted in", report: !ev.ok });
      loadResults();
      return true;
    }
    case "error":
      stopRunningRows("stopped");
      finish("It did not finish", ev.message, null, { at: ev.at, line: "Stopped after", open: true });
      return true;
    case "cancelled":
      stopRunningRows("cancelled");
      finish("Cancelled",
             "The chart was cancelled. What it had worked out is kept, so the same song goes faster next time.", null,
             { at: ev.at, line: "Cancelled after" });
      return true;
    default:
      break;
  }
  return false;
}

// The end (M7-10): the stages folded into one line ("Charted in 12 min 43 s"; the rows stay open after an error,
// to show where it stopped), the tab's title, the screen let go to sleep, the update notice back, and the Done
// screen scrolled to the top of the window: "Ready", then "Install into Clone Hero". `how`: the closing event's
// time (`at`), the folded line's words (`line`), whether the rows stay open (`open`), the build's report (`report`)
// and the tab's title when it is not `title` (`tab`).
function finish(title, message, summary, how) {
  how = how || {};
  $("results").hidden = true;
  clearInterval(state.ticker);
  state.ticker = null;
  $("cancel").hidden = true;
  const started = state.job && state.job.started;
  const took = how.at != null && started != null ? how.at - started : null;
  const line = took != null && took >= 0 && how.line ? `${how.line} ${seconds(took)}` : "The stages";
  text($("stages-line"), line).hidden = false;
  $("stages-box").open = !!how.open;
  $("progress-estimate").hidden = true;
  $("progress-remaining").hidden = true;
  state.remaining = null;
  $("progress-keep").hidden = true;
  $("built-row").hidden = true;   // shown with the results, for a chart that has a folder
  text($("built-msg"), "").hidden = true;
  text($("done-title"), title);
  text($("done-text"), message);
  setTitle(how.tab || title);
  text($("summary"), summary || "");
  $("summary-box").hidden = !summary;
  $("summary-box").open = !!how.report;   // the engines' lines, for a look; open when the check failed
  state.running = false;
  letSleep();
  renderUpdate(state.update, state.version);
  $("done-screen").hidden = false;
  toDone();
}

// the song's name, as its folder has it (the Linux path is not one he can open: M8-04), without a failed build's
// ".failed"
function songName(folder) {
  const name = String(folder || "").split("/").filter(Boolean).pop() || "The song";
  return name.endsWith(".failed") ? name.slice(0, -".failed".length) : name;
}

// the Done screen at the top of the window (as far as the page's height allows: again once the results are in)
function toDone() {
  const done = $("done-screen");
  if (!done.hidden && typeof done.scrollIntoView === "function") done.scrollIntoView({ block: "start" });
}

// ------------------------------------------------------------------------------------------------ the wake lock

// While a chart runs, a screen wake lock keeps the screen, and so the PC, awake. The browser lets it go when the tab
// is hidden (another tab, the window minimized), so it is asked for again when the tab is in view again; the chart
// lets it go at its end. Where the API is missing (an older browser; the fallback address, not a secure context) or
// refuses, nothing happens: the guide's sleep setting covers that.
async function holdAwake() {
  const wl = typeof navigator !== "undefined" ? navigator.wakeLock : undefined;
  if (!state.running || state.wake || !wl || typeof wl.request !== "function") return;
  const asking = {};   // one request at a time
  state.wake = asking;
  let lock = null;
  try { lock = await wl.request("screen"); } catch (e) { lock = null; }
  if (state.wake !== asking || !state.running) {   // let go meanwhile: the chart ended
    if (state.wake === asking) state.wake = null;
    if (lock) lock.release().catch(() => {});
    return;
  }
  state.wake = lock;
  if (lock) lock.addEventListener("release", () => { if (state.wake === lock) state.wake = null; });
}

function letSleep() {
  const lock = state.wake;
  state.wake = null;
  if (lock && typeof lock.release === "function") lock.release().catch(() => {});
}

function visible() {
  if (document.visibilityState === "visible") holdAwake();
}

async function follow(token) {
  let last = -1, failed = 0;
  for (;;) {
    if (token !== state.follow) return;
    try {
      const headers = { ...HEADER };
      if (last >= 0) headers["Last-Event-ID"] = String(last);
      const r = await fetch("/api/jobs/current/events", { headers, cache: "no-store" });
      if (token !== state.follow) return;
      if (r.status === 404) {   // a songcharter started again, with no job: this chart stopped with the old one
        gone(false);
        return;
      }
      if (r.status !== 200) throw new Error(`the events answered ${r.status}`);
      failed = 0;
      const reader = r.body.getReader();
      const decoder = new TextDecoder();
      let buf = "";
      for (;;) {
        const { value, done } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        let cut;
        while ((cut = buf.indexOf("\n\n")) >= 0) {
          const block = buf.slice(0, cut);
          buf = buf.slice(cut + 2);
          let id = null, data = "";
          for (const line of block.split("\n")) {
            if (line.startsWith("id: ")) id = Number(line.slice(4));
            else if (line.startsWith("data: ")) data += line.slice(6);
          }
          if (!data || token !== state.follow) continue;
          if (id != null) last = id;
          if (handle(JSON.parse(data))) return;
        }
      }
    } catch (e) {
      // the connection dropped, or songcharter does not answer: try again, from the last event seen
      failed += 1;
      if (failed >= FOLLOW_TRIES && token === state.follow) {   // it does not answer any more
        gone(true);
        return;
      }
    }
    await new Promise((ok) => setTimeout(ok, 2000));
  }
}

// The chart's songcharter is gone: a songcharter started since has no job (its window was closed, which stops
// the chart), or nothing answers any more (`down`): the window may have been closed, or the page may only have lost
// it for a while (after the PC sleeps, say) while the chart runs on, so a reload, which reattaches, comes first (the
// v0.4.0 gate's advisor). The page ends the chart as a cancel does: the screen let go, the title, the update notice
// back, and what to do.
function gone(down) {
  stopRunningRows("stopped");
  const kept = "what it had worked out is kept, so it goes faster.";
  finish("songcharter stopped", down ?
    "songcharter is not answering. If the songcharter window is still open, reload this page (press F5) to " +
    "follow the chart. If the window was closed, which stops the chart, start songcharter again from the Start " +
    `menu, then chart the song again: ${kept}` :
    "songcharter was closed while it charted (closing its window stops the chart) and has been started " +
    `again. Chart the song again: ${kept}`, null, { open: true, tab: "Stopped" });
}

async function attach() {
  const r = await api("GET", "/api/jobs/current");
  if (r.status !== 200) return;
  const job = r.data;
  state.job = job;
  state.offset = (job.now || Date.now() / 1000) - Date.now() / 1000;
  resetProgress(job);
  $("done-screen").hidden = true;
  show("progress-screen");
  setTitle("Charting");
  state.running = job.state === "running";   // a finished job's events end it again at once
  renderUpdate(state.update, state.version);
  holdAwake();
  clearInterval(state.ticker);
  state.ticker = setInterval(tick, 1000);
  state.follow += 1;
  follow(state.follow);
}

async function cancel() {
  if (!window.confirm("Cancel this chart? What it has worked out so far is kept for the next try.")) return;
  $("cancel").disabled = true;
  try {
    const r = await api("POST", "/api/jobs/current/cancel");
    if (r.status !== 200 && r.status !== 409) $("cancel").disabled = false;
  } catch (e) {
    $("cancel").disabled = false;
  }
}

function again() {
  if (state.job) {
    try { sessionStorage.setItem(DISMISSED, state.job.job); } catch (e) { /* private mode: no matter */ }
  }
  state.follow += 1;
  state.job = null;
  state.upload = null;
  state.running = false;
  letSleep();
  stopListening();
  closeBox();
  dropError("");
  show("drop-screen");
  setTitle(null);
  refreshStatus();   // a session of charts fills the disk: the header measures it again for the next song
}

async function refreshStatus() {
  try {
    const r = await api("GET", "/api/status");
    if (r.status !== 200) return;
    state.status = r.data;
    renderStatus(r.data);
    showUpdate(r.data.update);
  } catch (e) {
    // the server is gone: the next request says so
  }
}

// ------------------------------------------------------------------------------------------------ the Done screen

async function loadResults() {
  let r;
  try { r = await api("GET", "/api/jobs/current/results"); } catch (e) { return; }
  if (r.status !== 200) return;
  const res = r.data;
  renderBuilt(res);
  renderArt(res.art, res.name, res.job);
  renderLyrics(res.lyrics);
  renderListen(res.listen, res.job);   // before the preview, whose flags offer Listen for the parts it has
  renderPreview(res.preview, res.job);
  $("export-box").hidden = !res.installable;
  text($("export-msg"), "").hidden = true;
  $("open-exports").hidden = true;
  $("results").hidden = false;
  toDone();
  if (res.installable) loadCloneHero();
}

// Open folder under "Ready" (M8-04): the result's folder, before an install too, by name only (POST /api/open
// "built": the server opens its own result's folder); the Windows form of its path only as the button's hover text
function renderBuilt(res) {
  $("built-row").hidden = !res.folder;
  $("open-built").title = res.windows_path || "";
}

// the album art beside the song's name, and a line when there is a background
function renderArt(art, name, job) {
  const has = !!(art && art.album_art);
  $("art").hidden = !has;
  if (has) {
    $("album-art").src = `${art.album_art}?job=${encodeURIComponent(job)}`;   // this chart's, not a cached one
    text($("art-name"), name);
    text($("art-from"), art.album_from === "given" ? "Album art: your picture" :
      art.album_from === "embedded" ? "Album art: the song file's own picture" : "");
  }
  $("background-line").hidden = !(art && art.background);
}

function renderLyrics(ly) {
  const line = $("lyrics-line");
  line.hidden = !ly;
  $("lyrics-low").hidden = !(ly && ly.added && ly.low);
  if (!ly) return;
  text(line, ly.added ? `Lyrics: ${ly.words} words in ${ly.phrases} phrases` : `Lyrics not added: ${ly.why || "no reason given"}`);
}

// a link that opens the lightbox at `at` (its href stays the picture, for a middle click or a new tab)
function boxLink(a, at) {
  a.href = state.box.items[at].url;
  a.addEventListener("click", (e) => {
    if (e.button || e.ctrlKey || e.metaKey || e.shiftKey) return;   // a new tab, as the browser does it
    e.preventDefault();
    openBox(at);
  });
  return a;
}

function thumb(at, cls) {
  const item = state.box.items[at];
  const a = boxLink(make("a"), at);
  const img = make("img", cls);
  img.src = item.url;
  img.alt = item.label;
  a.append(img, make("span", "small", item.label));
  return a;
}

// A flag's line: its start (m:ss.s) a link to its page in the lightbox, and "Listen here" when the Listen box has its
// part (`at`: the server's {"part", "start", "page"} for the flag, null when its text is not a flag's)
function flagItem(textOf, at) {
  const li = make("li");
  const m = at ? /\d+:\d{2}(?:\.\d+)?/.exec(textOf) : null;
  if (!m || !at.page) {
    li.append(textOf);
    return li;
  }
  const link = boxLink(make("a", "flag-at", m[0]), at.page);   // items[0] is the overview: page n is items[n]
  link.title = `Page ${at.page}`;
  li.append(textOf.slice(0, m.index), link, textOf.slice(m.index + m[0].length));
  const levels = state.listen.parts[at.part] || [];
  if (levels.length) {
    const b = make("button", "plain small-button", "Listen here");
    b.type = "button";
    b.addEventListener("click", () => listenHere(at.part, at.start));
    li.append(" ", b);
  }
  return li;
}

function renderPreview(pv, job) {
  const has = !!(pv && pv.overview);
  $("preview").hidden = !has;
  $("no-preview").hidden = has;
  if (!has) {
    text($("no-preview"), `No preview: ${(pv && pv.why) || "no reason given"}`);
    state.box.items = [];
    return;
  }
  const v = `?job=${encodeURIComponent(job)}`;   // a new chart's pictures, not the browser's copy of the last one's
  state.box.items = [{ url: pv.overview + v, label: "Overview" },
                     ...pv.pages.map((u, i) => ({ url: u + v, label: `Page ${i + 1}` }))];
  $("overview").src = pv.overview + v;
  boxLink($("overview-link"), 0);
  $("pages").replaceChildren(...pv.pages.map((u, i) => thumb(i + 1, "thumb")));
  const at = pv.at || [];
  $("flags").replaceChildren(...(pv.flags.length ? pv.flags.map((f, i) => flagItem(f, at[i] || null)) :
                                 [make("li", null, "Nothing flagged.")]));
  $("remarks").replaceChildren(...pv.remarks.map((f) => make("li", null, f)));
}

// ------------------------------------------------------------------------------------------------ the lightbox

// One <dialog> for the overview and the pages (M8-04): opened modal, so Escape closes it (the browser's own), the
// arrow keys go to the page before or after, and a click beside the picture closes it
function openBox(at) {
  const box = $("lightbox");
  showBox(at);
  if (!box.open && typeof box.showModal === "function") box.showModal();
}

function showBox(at) {
  const items = state.box.items;
  if (!items.length) return;
  state.box.at = Math.max(0, Math.min(items.length - 1, at));
  const item = items[state.box.at];
  $("lightbox-img").src = item.url;
  $("lightbox-img").alt = item.label;
  text($("lightbox-title"), `${item.label} (${state.box.at + 1} of ${items.length})`);
  $("lightbox-full").href = item.url;
  $("lightbox-prev").disabled = state.box.at === 0;
  $("lightbox-next").disabled = state.box.at === items.length - 1;
}

function closeBox() {
  const box = $("lightbox");
  if (box.open && typeof box.close === "function") box.close();
}

function boxKey(e) {
  if (e.key === "ArrowLeft" || e.key === "ArrowRight") {
    e.preventDefault();
    showBox(state.box.at + (e.key === "ArrowLeft" ? -1 : 1));
  }
}

function setupBox() {
  const box = $("lightbox");
  box.addEventListener("keydown", boxKey);
  box.addEventListener("click", (e) => { if (e.target === box) closeBox(); });   // the backdrop
  $("lightbox-close").addEventListener("click", closeBox);
  $("lightbox-prev").addEventListener("click", () => showBox(state.box.at - 1));
  $("lightbox-next").addEventListener("click", () => showBox(state.box.at + 1));
}

// Listen: the part and the level (those the chart has), a button that has the server make them into sound over
// the song (a few seconds, kept for the next time), and the player
function option(value, label) {
  const o = make("option", null, label);
  o.value = value;
  return o;
}

function stopListening() {
  const player = $("listen-audio");
  player.pause();
  player.removeAttribute("src");
  player.hidden = true;
}

function renderListen(ls, job) {
  const parts = (ls && ls.parts) || {};
  const names = Object.keys(parts).filter((p) => parts[p] && parts[p].length);
  state.listen = { parts, job };
  stopListening();
  text($("listen-msg"), "").hidden = true;
  $("listen-box").hidden = !names.length;
  if (!names.length) return;
  $("listen-part").replaceChildren(...names.map((p) => option(p, PART_NAMES[p] || p)));
  $("listen-part").value = names[0];   // the guitar when the chart has it
  listenLevels();
}

function listenLevels() {
  const levels = state.listen.parts[$("listen-part").value] || [];
  const keep = $("listen-level").value;
  $("listen-level").replaceChildren(...levels.map((l) => option(l, LEVEL_NAMES[l] || l)));
  $("listen-level").value = levels.includes(keep) ? keep : levels[0];
}

// "Listen here" on a flag (M8-04): the Listen box set to the flag's part on Expert, and the render played from a
// second before the flag's start
function listenHere(part, start) {
  closeBox();
  $("listen-part").value = part;
  listenLevels();
  const levels = state.listen.parts[part] || [];
  if (levels.includes("expert")) $("listen-level").value = "expert";
  const box = $("listen-box");
  if (typeof box.scrollIntoView === "function") box.scrollIntoView({ block: "nearest" });
  return listenTo(Math.max(0, start - 1));
}

async function listenTo(from) {
  const at = typeof from === "number" && from > 0 ? from : 0;
  const part = $("listen-part").value;
  const level = $("listen-level").value;
  const what = `${PART_NAMES[part] || part} on ${LEVEL_NAMES[level] || level}`;
  const msg = $("listen-msg");
  const player = $("listen-audio");
  stopListening();
  $("listen").disabled = true;
  text(msg, `Making the ${what} into sound: a few seconds…`).hidden = false;
  try {
    const r = await api("POST", "/api/jobs/current/listen", { part, level });
    if (r.status === 200) {
      text(msg, `${what}, over the song. Listen for a tone that comes late or not at all, ` +
                "or tones where the song is quiet.");
      player.src = `${r.data.url}?job=${encodeURIComponent(state.listen.job)}`;   // this chart's, not a cached one
      if (at > 0) {   // the start position before the file is read, and again once its length is known
        player.currentTime = at;
        player.addEventListener("loadedmetadata", () => { player.currentTime = at; }, { once: true });
      }
      player.hidden = false;
      if (at > 0 && typeof player.scrollIntoView === "function") player.scrollIntoView({ block: "nearest" });
      const playing = player.play();
      if (playing && playing.catch) playing.catch(() => { /* the browser wants a click on the player first */ });
    } else {
      text(msg, r.data.error || `It could not be made (${r.status}).`);
    }
  } catch (x) {
    text(msg, "songcharter does not answer: is it still running?");
  } finally {
    $("listen").disabled = false;
  }
}

function installMessage(message, opts) {
  opts = opts || {};
  $("install-msg").hidden = !message;
  text($("install-text"), message);
  $("install-text").className = opts.error ? "error" : "";
  $("replace").hidden = !opts.replace;
  $("open-song").hidden = !opts.open;
  text($("open-msg"), "").hidden = true;
  const zip = $("blocked-zip");
  zip.hidden = !opts.zip;
  if (opts.zip) zip.href = opts.zip;
  else zip.removeAttribute("href");
}

async function loadCloneHero() {
  installMessage("");
  let r;
  try { r = await api("GET", "/api/clonehero"); } catch (e) { return; }
  state.ch = r.data;
  renderCloneHero(false);
}

function renderCloneHero(editing) {
  const ch = state.ch || {};
  const known = !!ch.folder;
  const form = $("ch-form");
  form.hidden = known && !editing;
  $("install").hidden = !known || editing;
  $("ch-change").hidden = !known || editing;
  text($("ch-error"), "").hidden = true;
  if (known) {
    const where = ch.windows_path || ch.folder;
    text($("ch-where"), `Into ${where}` + (ch.source === "documents" ? " (found in your Documents)" : ""));
  } else if (ch.guess) {   // the field holds the guess: said so, as nothing is there (M8-04)
    text($("ch-where"), "songcharter did not find your Clone Hero Songs folder. The box holds a guess, where Clone " +
      "Hero usually keeps it, but no folder is there: change it to your Songs folder, then press Use this folder.");
  } else {
    text($("ch-where"), "songcharter did not find your Clone Hero Songs folder: give it below.");
  }
  if (form.hidden === false) form.elements.folder.value = ch.windows_path || ch.folder || ch.guess || "";
}

async function saveFolder(e) {
  e.preventDefault();
  const err = $("ch-error");
  err.hidden = true;
  $("ch-save").disabled = true;
  try {
    const r = await api("POST", "/api/clonehero", { folder: $("ch-form").elements.folder.value });
    if (r.status === 200) {
      state.ch = r.data;
      renderCloneHero(false);
    } else {
      text(err, r.data.error || `That folder could not be used (${r.status}).`).hidden = false;
    }
  } catch (x) {
    text(err, "songcharter does not answer: is it still running?").hidden = false;
  } finally {
    $("ch-save").disabled = false;
  }
}

async function install(replace) {
  installMessage("");
  $("install").disabled = true;
  $("replace").disabled = true;
  try {
    const r = await api("POST", "/api/jobs/current/install", { replace });
    const d = r.data;
    if (r.status === 200) {
      installMessage("Done. In Clone Hero, open Settings > General and press Scan Songs." + (d.note ? `\n(${d.note})` : ""),
                     { open: true });
    } else if (r.status === 409 && d.exists && d.ours) {
      installMessage(`This song is in Clone Hero already (${d.windows_path || d.folder}), from an earlier chart. Replace the older chart?`,
                     { replace: true });
    } else if (r.status === 409 && d.exists) {
      installMessage(`A folder named like this song is in Clone Hero already (${d.windows_path || d.folder}), and songcharter did not make it, so it stays as it is. Rename or move it in Windows first, or save the zip.`,
                     { error: true });
    } else if (r.status === 403 && d.blocked) {
      installMessage("Windows did not let songcharter finish writing into that folder. Security software, or OneDrive syncing it, can do that.\n" +
                     "Try again in a moment, or save the zip and extract it there yourself." +
                     (d.under_onedrive ? "\nYour Songs folder is inside OneDrive." : "") +
                     (d.older ? `\nYour older chart is kept in ${d.older} for now: the next install moves it out of the Songs folder.` : ""),
                     { error: true, zip: d.zip_url });
    } else {
      installMessage(d.error || `It could not be installed (${r.status}).`, { error: true });
    }
  } catch (x) {
    installMessage("songcharter does not answer: is it still running?", { error: true });
  } finally {
    $("install").disabled = false;
    $("replace").disabled = false;
  }
}

function download(url, name) {
  const a = make("a");
  a.href = url;
  a.download = name || "";
  document.body.append(a);
  a.click();
  a.remove();
}

async function exportZip() {
  const msg = $("export-msg");
  $("zip").disabled = true;
  try {
    const r = await api("POST", "/api/jobs/current/export/zip");
    if (r.status === 200) {
      download(r.data.url, r.data.name);
      text(msg, `The zip is ${r.data.name}: your browser saves it, into Downloads unless you chose another folder.`).hidden = false;
      $("open-exports").hidden = !r.data.windows_path;
    } else {
      text(msg, r.data.error || `The zip could not be made (${r.status}).`).hidden = false;
    }
  } catch (x) {
    text(msg, "songcharter does not answer: is it still running?").hidden = false;
  } finally {
    $("zip").disabled = false;
  }
}

async function openFolder(what, where) {
  try {
    const r = await api("POST", "/api/open", { what });
    if (r.status === 200 && !r.data.opened) {
      text(where, `Open it yourself: ${r.data.windows_path || r.data.path}`).hidden = false;
    } else if (r.status !== 200) {
      text(where, r.data.error || `It could not be opened (${r.status}).`).hidden = false;
    }
  } catch (x) {
    text(where, "songcharter does not answer: is it still running?").hidden = false;
  }
}

// ------------------------------------------------------------------------------------------------ start

async function start() {
  setupDrop();
  setupPictures();
  setupBox();
  $("options").addEventListener("submit", chartIt);
  for (const r of $("options").querySelectorAll("input[name=how]")) r.addEventListener("change", choose);
  $("options").elements.takes.addEventListener("input", typedTakes);
  $("open-built").addEventListener("click", () => openFolder("built", $("built-msg")));
  $("options").elements.solos.addEventListener("change", soloNames);
  $("other-song").addEventListener("click", again);
  $("cancel").addEventListener("click", cancel);
  $("again").addEventListener("click", again);
  $("ch-form").addEventListener("submit", saveFolder);
  $("ch-change").addEventListener("click", () => renderCloneHero(true));
  $("install").addEventListener("click", () => install(false));
  $("replace").addEventListener("click", () => install(true));
  $("zip").addEventListener("click", exportZip);
  $("listen-part").addEventListener("change", listenLevels);
  $("listen").addEventListener("click", () => listenTo(0));
  $("open-song").addEventListener("click", () => openFolder("song", $("open-msg")));
  $("open-exports").addEventListener("click", () => openFolder("exports", $("export-msg")));
  $("update-copy").addEventListener("click", copyLine);
  $("update-later").addEventListener("click", later);
  document.addEventListener("visibilitychange", visible);
  show("drop-screen");
  let st;
  try {
    st = (await api("GET", "/api/status")).data;
  } catch (e) {
    text($("machine"), "songcharter does not answer: start it again from the Start menu.");
    return;
  }
  state.status = st;
  renderStatus(st);
  showUpdate(st.update);
  if (!st.update) for (const ms of UPDATE_ASKS) setTimeout(askForUpdate, ms);
  let dismissed = null;
  try { dismissed = sessionStorage.getItem(DISMISSED); } catch (e) { dismissed = null; }
  if (st.job && (st.job.state === "running" || st.job.job !== dismissed)) attach();
}

document.addEventListener("DOMContentLoaded", start);
