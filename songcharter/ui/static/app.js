// songcharter's page (M4-04, M4-06, M4-11, M5-07, M6-09, M7-10, M8-04): drop a song, choose Best or Quick (on a GPU)
// and the options (the rest folded: the takes, device and preview, the lyrics, the pictures), follow the chart (how
// long it usually takes, and how long is left once the first take is timed; the tab's title saying where it is, the
// screen kept awake), cancel it; then "Ready" scrolled into view with the song's name and Open folder, the install
// into Clone Hero first, the zip, the album art, the preview (its pages in a lightbox, each flag linked to its page
// and to Listen at its time) and the chart to listen to, and the diagnostics in the footer; above it all, the update
// notice when a newer version is out, put away while a chart runs. No framework, no build step. Every request sends
// X-Songcharter: 1 (the server's guard for anything but a GET). The job's events come over a streamed fetch of
// /api/jobs/current/events (Server-Sent Events), which can send that header too, and which resumes after the last
// event it saw when the connection drops; a reload reattaches to the current job. M8-10: a queue of songs, which the
// server runs (it starts the next itself): a drop of several songs shares one options form, the list under the
// progress screen gives each song's state with Install and Look (its own Done screen, by its job id), and the tab's
// title, the wake lock, the update notice and the whole queue's estimate go across the songs.
"use strict";

const HEADER = { "X-Songcharter": "1" };
const CLOSING = new Set(["result", "error", "cancelled"]);
const LABELS = {
  decode: "Read the song", separate: "Separate the instruments", drums: "Drums", bass: "Bass",
  sections: "Sections", lyrics: "Lyrics", guitar: "Guitar", assemble: "Build and check the chart", preview: "Preview",
  stems: "Save the stems",
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
  box: { items: [], at: 0 }, queue: null, queueKey: null, uploads: [], shown: null, note: "" };
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

// ... and while a queue runs, where in it the page is: "2 of 6: Guitar: take 3 of 4"
function progressTitle(what) { setTitle(queuePrefix() + what); }

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
  if (!up || state.later || state.running || waitingCount() > 0) { box.hidden = true; return; }
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

// The song files, each uploaded in turn (`rest` the ones after this one; `got` the answers so far, `failed` the
// refusals): one gets the options form as before, several share one (M8-10)
function upload(file, rest, got, failed) {
  rest = rest || [];
  got = got || [];
  failed = failed || [];
  if (!got.length && !failed.length) dropError("");
  $("upload").hidden = false;
  const total = got.length + failed.length + rest.length + 1, n = got.length + failed.length + 1;
  text($("upload-name"), total > 1 ? `Uploading ${file.name} (${n} of ${total})…` : `Uploading ${file.name}…`);
  const bar = $("upload-bar");
  bar.value = 0;
  const who = total > 1 ? `${file.name}: ` : "";
  const next = () => {
    if (rest.length) upload(rest[0], rest.slice(1), got, failed);
    else uploaded(got, failed);
  };
  const xhr = new XMLHttpRequest();
  xhr.open("POST", "/api/upload");
  xhr.setRequestHeader("X-Songcharter", "1");
  xhr.setRequestHeader("X-Filename", encodeURIComponent(file.name));
  xhr.upload.addEventListener("progress", (e) => { if (e.lengthComputable) bar.value = e.loaded / e.total; });
  xhr.addEventListener("load", () => {
    let data = {};
    try { data = JSON.parse(xhr.responseText); } catch (e) { data = {}; }
    if (xhr.status === 200) got.push(data);
    else if (xhr.status === 415) failed.push(`${who}That is not a song file songcharter takes. ${data.error || ""}`);
    else failed.push(`${who}${data.error || `The upload failed (${xhr.status}).`}`);
    next();
  });
  xhr.addEventListener("error", () => { failed.push(`${who}The upload failed: is songcharter still running?`); next(); });
  xhr.send(file);
}

function uploaded(got, failed) {
  $("upload").hidden = true;
  if (!got.length) { dropError(failed.join("\n")); return; }
  state.upload = got[0];
  state.uploads = got;
  if (got.length === 1) fillOptions(got[0]);
  else fillMany(got);
  if (failed.length) text($("options-error"), failed.join("\n")).hidden = false;
  show("options-screen");
}

function uploadFiles(files) {
  const list = [...(files || [])];
  state.note = "";   // the last drop's refusals go with the next drop
  renderQueue();
  if (list.length) upload(list[0], list.slice(1));
}

function setupDrop() {
  const zone = $("drop");
  for (const kind of ["dragenter", "dragover"]) {
    zone.addEventListener(kind, (e) => { e.preventDefault(); zone.classList.add("over"); });
  }
  for (const kind of ["dragleave", "drop"]) zone.addEventListener(kind, () => zone.classList.remove("over"));
  zone.addEventListener("drop", (e) => {
    e.preventDefault();
    uploadFiles(e.dataTransfer && e.dataTransfer.files);
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
  $("file").addEventListener("change", (e) => { uploadFiles(e.target.files); e.target.value = ""; });
  // the progress screen's Add songs strip (M8-10): the drop screen, for the upload's progress, then the options
  const strip = $("add-drop");
  const adding = (files) => { show("drop-screen"); $("back-row").hidden = !state.running; uploadFiles(files); };
  for (const kind of ["dragenter", "dragover"]) {
    strip.addEventListener(kind, (e) => { e.preventDefault(); strip.classList.add("over"); });
  }
  for (const kind of ["dragleave", "drop"]) strip.addEventListener(kind, () => strip.classList.remove("over"));
  strip.addEventListener("drop", (e) => { e.preventDefault(); adding(e.dataTransfer && e.dataTransfer.files); });
  strip.addEventListener("keydown", (e) => {
    if ((e.key === "Enter" || e.key === " ") && !e.altKey && !e.ctrlKey && !e.metaKey && !e.shiftKey) {
      e.preventDefault();
      $("add-file").click();
    }
  });
  $("add-file").addEventListener("change", (e) => { adding(e.target.files); e.target.value = ""; });
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

function fillChoice(choices, many) {
  const c = choices || {};
  const best = minutes(c.best), quick = minutes(c.quick);
  $("choice").hidden = !c.gpu;
  $("choice-cpu").hidden = !!c.gpu;
  if (c.gpu) {
    const takes = (c.best && c.best.takes) || 4;
    // several songs: no minutes here (each song's own are in the list, and the whole queue's under it)
    text($("best-label"), many ? `Best charts (${takes} guitar takes)` :
      `Best chart (${takes} guitar takes${best ? `, ${best}` : ""})`);
    text($("quick-label"), many ? "Quick charts (1 take)" : `Quick chart (1 take${quick ? `, ${quick}` : ""})`);
  } else {
    text($("choice-cpu"), "This PC charts the guitar on the CPU, so it makes 1 guitar take" +
      (best && !many ? `: ${best} for this song.` : "."));
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

function fillOptions(up, many) {
  const form = $("options");
  form.reset();
  for (const id of ["more", "lyrics-box", "pictures-box"]) $(id).open = false;
  fillChoice(up.choices, many);
  // a song's own fields only for a drop of one; lyrics only for a song that starts at once (M8-10)
  for (const id of ["song-box", "lyrics-box", "pictures-box"]) $(id).hidden = !!many;
  $("song-names").hidden = !many;
  for (const id of ["chart", "chart-top"]) text($(id), many ? "Chart them" : "Chart it");
  lockLyrics();
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
  stemsSize([up]);
  text($("options-error"), "").hidden = true;
}

// how much disk the stems take (pipeline.stems_bytes: six stems of 24-bit stereo at 44.1 kHz, about half of it as
// FLAC): about 0.8 MB a second of the song, 190 MB for 4 minutes
const STEMS_MB_PER_S = 44100 * 2 * 3 * 6 * 0.5 / 1e6;

function stemsSize(ups) {
  const known = ups.length > 0 && ups.every((u) => u.seconds > 0);
  const mb = Math.round(ups.reduce((sum, u) => sum + (u.seconds || 0), 0) * STEMS_MB_PER_S);
  text($("stems-size"), known ? `About ${mb} MB of disk ${ups.length > 1 ? "for these songs" : "for this song"}.`
    : "About 190 MB of disk for a 4-minute song.");
}

// ------------------------------------------------------------------------------------------------ the pictures

// lyrics only for a song that starts at once: the box locked while a song charts or waits, and open again at the
// end (the review's P-F2)
function lockLyrics() {
  const busy = queueBusy();
  $("lyrics-wait").hidden = !busy;
  const box = $("options").elements && $("options").elements.lyrics;
  if (box) box.disabled = busy;
}

// the options form is being filled (a song or several uploaded, not yet sent): a song's end, or the next one's
// start, never takes it away (the review's P-F2)
function adding() { return state.uploads.length > 0 && !$("options-screen").hidden; }

// several songs (M8-10): one form, shared; each song takes its own tags, as a chart with the Song fields blank does
function fillMany(ups) {
  fillOptions(ups[0], true);
  text($("song-name"), `${ups.length} songs, charted one after the other with these options:`);
  $("song-names").replaceChildren(...ups.map((u) => make("li", null, `${u.name} (${(u.bytes / 1e6).toFixed(1)} MB)`)));
  stemsSize(ups);
}

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
  const many = state.uploads.length > 1;   // the shared form: no song's own fields, lyrics or pictures
  for (const field of many ? [] : Object.keys(META)) {
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
  options.stems = f.stems.checked;           // per song, so the queue keeps them for a waiting one (M8-12)
  options.one_audio = f.one_audio.checked;
  if (many) return options;
  const lyrics = f.lyrics.value;   // as pasted; the server keeps it out of every record
  if (lyrics.trim() && !f.lyrics.disabled) options.lyrics = lyrics;
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
  const ups = state.uploads.length ? state.uploads : [state.upload];
  const refused = [];
  let started = false;
  try {
    for (const up of ups) {   // in turn: the first starts at once when nothing charts, the rest wait
      const r = await api("POST", "/api/jobs", { upload: up.id, options });
      if (r.status === 202) started = started || !!r.data.job;
      else refused.push({ name: up.name, status: r.status, error: r.data.error || `It could not start (${r.status}).` });
    }
  } catch (x) {
    refused.push({ name: "", status: 0, error: "songcharter does not answer: is it still running?" });
  } finally {
    chartButtons(false);
  }
  if (refused.length === ups.length) {   // nothing added: the form stays, with why
    const many = ups.length > 1;
    text(err, refused.map((x) => (many && x.name ? `${x.name}: ` : "") + x.error).join("\n")).hidden = false;
    return;
  }
  state.uploads = [];
  await refreshQueue();
  // some were added and some refused (the list full, say): said where the page lands, above the list (the review's
  // P-F1), until the next drop
  state.note = refusedNote(refused);
  renderQueue();
  if (started || queueCharting()) {
    attach();
  } else {   // the list is paused (after a restart, say): the songs wait in it, on the drop screen
    show("drop-screen");
    $("back-row").hidden = true;
  }
}

function refusedNote(refused) {
  const full = refused.filter((x) => x.status === 409 && x.name);
  const parts = [];
  if (full.length) {
    const n = full.length, max = (state.queue && state.queue.max) || 20;
    parts.push(`${n === 1 ? "1 song was" : `${n} songs were`} not added (${max} ${max === 1 ? "is" : "are"} ` +
      `waiting already): ${full.map((x) => x.name).join(", ")}. Drop ${n === 1 ? "it" : "them"} again once some ` +
      "are charted.");
  }
  for (const x of refused.filter((y) => !full.includes(y))) {
    parts.push(x.name ? `${x.name} was not added: ${x.error}` : x.error);
  }
  return parts.join(" ");
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
      progressTitle(stageLabel(ev.stage));
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
      progressTitle(`${stageLabel("guitar")}: take ${ev.index} of ${ev.count}`);
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
    case "result":
    case "error":
    case "cancelled":
      stopRunningRows(ev.event === "cancelled" ? "cancelled" : "stopped");
      closed(closing(ev));
      return true;
    default:
      break;
  }
  return false;
}

// A closing event's words, for the end of a chart and for a finished song's Look (M8-10): the Done screen's title and
// text, the build's report, how the stages fold, whether there are results, and the song's state in the list
function closing(ev) {
  if (ev.event === "result") {
    const name = songName(ev.folder);
    return { title: ev.ok ? "Ready" : "The check failed",
      message: ev.ok ? `${name} is charted and passed its check.` :
        `${name} did not pass the check, so it is kept for a look (Open folder), not for Clone Hero.`,
      summary: ev.summary, how: { at: ev.at, line: "Charted in", report: !ev.ok }, results: true,
      outcome: ev.ok ? "ready" : "check_failed" };
  }
  if (ev.event === "error") {
    return { title: "It did not finish", message: ev.message, summary: null,
      how: { at: ev.at, line: "Stopped after", open: true }, results: false, outcome: "not_finished" };
  }
  return { title: "Cancelled",
    message: "The chart was cancelled. What it had worked out is kept, so the same song goes faster next time.",
    summary: null, how: { at: ev.at, line: "Cancelled after" }, results: false, outcome: "cancelled" };
}

// A chart's end: with more songs to come (the list as last read: songs waiting, not paused) the page waits for the
// server to start the next and follows it, the screen kept awake; else the Done screen, as for one song
function closed(c) {
  if (moreToCome()) between(c);
  else closedNow(c);
}

function closedNow(c) {
  const was = state.job && state.job.job;
  finish(c.title, c.message, c.summary, { ...c.how, tab: endTitle(c.outcome) || c.how.tab });
  if (c.results) loadResults();
  settleQueue(was);
}

// the list read again until the song that just ended is no longer charting in it: its result comes a second or so
// before its process has exited, which the server waits for before it records the end
async function settleQueue(job) {
  for (let i = 0; i < 10; i++) {
    await refreshQueue();
    if (!entries().some((e) => e.job === job && e.state === "charting")) return;
    await new Promise((ok) => setTimeout(ok, 1000));
  }
}

async function between(c) {
  const was = state.job && state.job.job;
  clearInterval(state.ticker);
  state.ticker = null;
  $("cancel").hidden = true;
  text($("progress-title"), "Starting the next song…");
  for (let i = 0; i < 30; i++) {
    await refreshQueue();
    const q = state.queue;
    if (q && q.entries.some((e) => e.state === "charting" && e.job && e.job !== was)) { attach(adding()); return; }
    if (!q || q.paused || !q.entries.some((e) => e.state === "waiting")) break;
    await new Promise((ok) => setTimeout(ok, 1000));
  }
  closedNow(c);
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
  setTitle(how.tab || title);
  state.running = false;
  letSleep();
  lockLyrics();
  renderUpdate(state.update, state.version);
  showDone(title, message, summary, how);
}

// the Done screen's own part: for the chart that just ended, and for a finished song's Look (M8-10)
function showDone(title, message, summary, how) {
  $("results").hidden = true;
  $("built-row").hidden = true;   // shown with the results, for a chart that has a folder
  text($("built-msg"), "").hidden = true;
  text($("done-title"), title);
  text($("done-text"), message);
  text($("summary"), summary || "");
  $("summary-box").hidden = !summary;
  $("summary-box").open = !!(how && how.report);   // the engines' lines, for a look; open when the check failed
  text($("again"), state.running ? "Back to the chart" : "Add a song");
  if (adding()) return;   // under the form he is filling: in the list, with Look, until he leaves it
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
// back, and what to do. The heading and the tab say which (the gate's note): "songcharter is not answering" and "Not
// answering" when nothing answers, "songcharter stopped" and "Stopped" when one started since has no job.
function gone(down) {
  stopRunningRows("stopped");
  const kept = "what it had worked out is kept, so it goes faster.";
  finish(down ? "songcharter is not answering" : "songcharter stopped", down ?
    "songcharter is not answering. If the songcharter window is still open, reload this page (press F5) to " +
    "follow the chart. If the window was closed, which stops the chart, start songcharter again from the Start " +
    `menu, then chart the song again: ${kept}` :
    "songcharter was closed while it charted (closing its window stops the chart) and has been started " +
    `again. Chart the song again: ${kept}`, null, { open: true, tab: down ? "Not answering" : "Stopped" });
}

// `quiet` (the next song, or one started elsewhere, while he fills the options form): followed without taking the
// form away; it shows once he sends or leaves the form
async function attach(quiet) {
  const r = await api("GET", "/api/jobs/current");
  if (r.status !== 200) return;
  const job = r.data;
  state.job = job;
  state.offset = (job.now || Date.now() / 1000) - Date.now() / 1000;
  resetProgress(job);
  if (!quiet) {
    $("done-screen").hidden = true;
    show("progress-screen");
  }
  progressTitle("Charting");
  state.running = job.state === "running";   // a finished job's events end it again at once
  renderUpdate(state.update, state.version);
  holdAwake();
  clearInterval(state.ticker);
  state.ticker = setInterval(tick, 1000);
  state.follow += 1;
  follow(state.follow);
  renderQueue();
}

async function cancel() {
  if (!window.confirm("Cancel this chart? What it has worked out so far is kept for the next try.")) return;
  $("cancel").disabled = true;
  try {
    // the job this page shows: a Cancel confirmed after its song ended never reaches the next (the review's S-S1)
    const which = state.job && state.job.job;
    const r = await api("POST", `/api/jobs/${encodeURIComponent(which || "current")}/cancel`);
    if (r.status !== 200 && r.status !== 409) $("cancel").disabled = false;
  } catch (e) {
    $("cancel").disabled = false;
  }
}

function again() {
  state.uploads = [];   // the form, if any, is left
  if (state.running) {   // a finished song's Look while the next charts: back to the chart (M8-10)
    stopListening();
    closeBox();
    $("done-screen").hidden = true;
    show("progress-screen");
    return;
  }
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
  $("back-row").hidden = true;
  setTitle(null);
  refreshStatus();   // a session of charts fills the disk: the header measures it again for the next song
}

async function refreshStatus() {
  try {
    const r = await api("GET", "/api/status");
    if (r.status !== 200) return;
    state.status = r.data;
    renderStatus(r.data);
    setQueue(r.data.queue);
    showUpdate(r.data.update);
  } catch (e) {
    // the server is gone: the next request says so
  }
}

// ------------------------------------------------------------------------------------------------ the queue (M8-10)

// The server's list (GET /api/queue, and /api/status's `queue`): each song with its state, Install and Look once
// finished, Remove while it waits; Pause after this song, Carry on and Clear the list; the whole queue's estimate.
const FINISHED = new Set(["ready", "check_failed", "not_finished", "cancelled"]);
const STATE_WORDS = { waiting: "Waiting", charting: "Charting now", ready: "Ready",
  check_failed: "The check failed (kept for a look)", not_finished: "Did not finish", cancelled: "Cancelled" };
const END_WORDS = [["ready", "ready"], ["check_failed", "check failed"], ["not_finished", "did not finish"],
  ["cancelled", "cancelled"], ["waiting", "waiting"]];

function entries() { return (state.queue && state.queue.entries) || []; }
function waitingCount() { return entries().filter((e) => e.state === "waiting").length; }
function queueCharting() { return entries().find((e) => e.state === "charting") || null; }
function queueBusy() { return !!queueCharting() || waitingCount() > 0 || state.running; }
function moreToCome() { return !!state.queue && !state.queue.paused && waitingCount() > 0; }
// the evening's songs: those added since the list was last idle (the server's `run`)
function runEntries(q) { return q && q.entries ? q.entries.filter((e) => e.run === q.run) : []; }

function queuePrefix() {
  const run = runEntries(state.queue);
  if (run.length < 2 || !state.job) return "";
  const at = run.findIndex((e) => e.job === state.job.job);
  return at >= 0 ? `${at + 1} of ${run.length}: ` : "";
}

// the tab's title at the queue's end: "6 ready", "5 ready, 1 did not finish" (the song that just ended counted as
// `outcome`); null for one song
function endTitle(outcome) {
  const run = runEntries(state.queue);
  if (run.length < 2) return null;
  const counts = {};
  for (const e of run) {
    const st = state.job && e.job === state.job.job ? outcome : e.state;
    counts[st] = (counts[st] || 0) + 1;
  }
  return END_WORDS.filter(([k]) => counts[k]).map(([k, w]) => `${counts[k]} ${w}`).join(", ");
}

function hoursMinutes(min) {
  return min < 60 ? `${min} min` : `${Math.floor(min / 60)} h` + (min % 60 ? ` ${min % 60} min` : "");
}

function leftText(q) {
  const run = runEntries(q);
  if (!q || !q.left || run.length < 2 || !(q.left.high_s > 0)) return "";
  const [lo, hi] = roundMinutes(q.left.low_s, q.left.high_s);
  return `All ${run.length} songs: about ${hoursMinutes(lo)} to ${hoursMinutes(hi)} more`;
}

function pausedText(q) {
  if (q.paused === "restart") {
    const n = q.restarted || waitingCount();
    return `${n} song${n === 1 ? " was" : "s were"} waiting when songcharter closed. Carry on charts ` +
      `${n === 1 ? "it" : "them"}; Clear the list lets ${n === 1 ? "it" : "them"} go.`;
  }
  if (q.paused === "you") return "Paused after this song: Carry on charts the rest.";
  if (q.paused === "failures") {
    return "Two songs in a row did not finish, so the queue is paused: see why with Look. Carry on tries the rest.";
  }
  return q.why || "The queue is paused: Carry on goes on.";
}

function setQueue(q) {
  state.queue = q && Array.isArray(q.entries) ? q : null;
  renderQueue();
}

async function refreshQueue() {
  let r;
  try { r = await api("GET", "/api/queue"); } catch (e) { return; }
  if (r.status !== 200) return;
  setQueue(r.data);
  // a song the server started while this page followed none (Carry on in another tab, say): followed
  const c = queueCharting();
  if (c && c.job && !state.running && (!state.job || state.job.job !== c.job)) attach(adding());
}

function smallButton(label, f, cls) {
  const b = make("button", cls || "plain small-button", label);
  b.type = "button";
  b.addEventListener("click", f);
  return b;
}

function queueRow(e) {
  const li = make("li", e.state);
  li.append(make("span", "queue-name", e.chart || e.name), " ");
  let word = STATE_WORDS[e.state] || e.state;
  if (e.state === "not_finished" && e.error) word += `: ${e.error}`;
  if (e.state === "waiting" && e.estimate && e.estimate.low_min > 0) {
    word += ` (usually about ${e.estimate.low_min} to ${e.estimate.high_min} minutes)`;
  }
  li.append(make("span", "queue-state", word));
  const actions = make("span", "queue-actions");
  const msg = make("span", "queue-msg small");
  msg.hidden = true;
  if (e.state === "ready" && e.job) actions.append(smallButton("Install", () => installFrom(e, msg), "small-button"));
  if (FINISHED.has(e.state) && e.job) actions.append(smallButton("Look", () => look(e.job)));
  if (e.state === "waiting") actions.append(smallButton("Remove", () => removeEntry(e)));
  li.append(actions, msg);
  if (e.lyrics_lost) {   // the review's S-S2: pasted lyrics are never kept, so a restart lost them
    li.append(make("span", "queue-msg small warn-text", "Its pasted lyrics were not kept when songcharter closed: " +
      "add it again with its lyrics, or chart it without."));
  }
  return li;
}

function renderQueue() {
  const q = state.queue;
  const list = entries();
  $("queue-box").hidden = !list.length;
  const key = JSON.stringify(list);
  if (key !== state.queueKey) {   // the rows made again only when a song changed (a click is not lost)
    state.queueKey = key;
    $("queue-list").replaceChildren(...list.map(queueRow));
  }
  const paused = q && q.paused;
  $("queue-paused").hidden = !paused;
  if (paused) text($("queue-paused-text"), pausedText(q));
  $("queue-clear").hidden = paused !== "restart";
  const charting = queueCharting(), waiting = waitingCount();
  $("queue-actions").hidden = !!charting || !!paused || !list.length;
  const left = leftText(q);
  text($("queue-left"), left).hidden = !left;
  $("queue-keep").hidden = !(waiting > 0 || (charting && runEntries(q).length > 1));
  $("pause").hidden = !(charting && waiting > 0 && !paused);
  text($("queue-note"), state.note).hidden = !state.note;
  lockLyrics();
}

async function queueAction(path, body) {
  let r;
  try { r = await api("POST", path, body); } catch (e) { return null; }
  if (r.status === 200) setQueue(r.data);
  return r;
}

function removeEntry(e) { return queueAction("/api/queue/remove", { entry: e.id }); }
function pauseQueue() { return queueAction("/api/queue/pause"); }

async function carryOn() {
  const r = await queueAction("/api/queue/carry-on");
  if (r && r.status === 200 && queueCharting()) attach();
}

async function clearList() {
  const waiting = waitingCount();
  if (waiting && !window.confirm(`Clear the list? The ${waiting === 1 ? "song" : `${waiting} songs`} waiting ` +
    "will not be charted; the charts already made stay.")) return;
  await queueAction("/api/queue/clear");
}

// Install from the list: the song's own chart by its job id; a song in Clone Hero already asks before replacing
async function installFrom(e, msg, replace) {
  text(msg, "Installing…").hidden = false;
  try {
    const r = await api("POST", `/api/jobs/${encodeURIComponent(e.job)}/install`, { replace: !!replace });
    const d = r.data;
    if (r.status === 200) {
      text(msg, "Installed. In Clone Hero, open Settings > General and press Scan Songs.");
    } else if (r.status === 409 && d.exists && d.ours) {
      if (window.confirm(`${e.chart || e.name} is in Clone Hero already, from an earlier chart. Replace the older chart?`)) {
        return installFrom(e, msg, true);
      }
      text(msg, "Not installed: the older chart stays.");
    } else if (r.status === 400 && /Songs folder/.test(d.error || "")) {
      text(msg, "songcharter does not know your Clone Hero Songs folder yet: press Look, and give it there.");
    } else if (r.status === 403) {
      text(msg, "Windows did not let songcharter finish writing into the Songs folder: press Look to try again, or to save the zip.");
    } else {
      text(msg, d.error || `It could not be installed (${r.status}).`);
    }
  } catch (x) {
    text(msg, "songcharter does not answer: is it still running?");
  }
  return null;
}

// Look: a finished song's own Done screen (its result, preview and flags, Listen, the zip), by its job id
async function look(job) {
  let r;
  try { r = await api("GET", `/api/jobs/${encodeURIComponent(job)}`); } catch (e) { return; }
  if (r.status !== 200) return;
  const ev = (r.data.events || []).filter((x) => CLOSING.has(x.event)).pop();
  if (!ev) return;
  stopListening();
  closeBox();
  state.uploads = [];   // the form, if any, is left: the Look's own screen (the review's P-F2)
  show(state.running ? "progress-screen" : null);
  const c = closing(ev);
  state.shown = job;
  showDone(c.title, c.message, c.summary, c.how);
  if (c.results) await loadResults(job);
}

// ------------------------------------------------------------------------------------------------ the Done screen

// the Done screen's routes name the song it shows by its job id (M8-10: a finished song's, after the next started)
function jobPath(rest) { return `/api/jobs/${encodeURIComponent(state.shown || "current")}${rest}`; }

async function loadResults(job) {
  let r;
  try { r = await api("GET", `/api/jobs/${encodeURIComponent(job || "current")}/results`); } catch (e) { return; }
  if (r.status !== 200) return;
  const res = r.data;
  state.shown = res.job || job || null;
  renderBuilt(res);
  renderArt(res.art, res.name, res.job);
  renderLyrics(res.lyrics);
  renderListen(res.listen, res.job);   // before the preview, whose flags offer Listen for the parts it has
  renderPreview(res.preview, res.job);
  renderStems(res.stems);
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
  const item = state.box.items[at];
  if (!item) return a;   // nothing to show: no link, and the rest of the Done screen still renders
  a.href = item.url;
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
  if (!m || !at.page || !state.box.items[at.page]) {
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
  text($("lightbox-title"), state.box.at === 0 ? item.label : `Page ${state.box.at} of ${items.length - 1}`);
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
    const r = await api("POST", jobPath("/listen"), { part, level });
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
    const r = await api("POST", jobPath("/install"), { replace });
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

// the stems the run saved (M8-12): their folder beside the song's, and a zip of them to download
function renderStems(st) {
  $("stems-box").hidden = !st;
  text($("stems-msg"), "").hidden = true;
  if (!st) return;
  text($("stems-line"), `${st.files.length} instruments as lossless files (${Math.round(st.bytes / 1e6)} MB), in the folder "${st.name}" beside the song's. Piano and "other" come out the least clean.`);
}

async function exportStems() {
  const msg = $("stems-msg");
  $("stems-zip").disabled = true;
  text(msg, "Making the zip: a few seconds…").hidden = false;
  try {
    const r = await api("POST", jobPath("/export/stems"));
    if (r.status === 200) {
      download(r.data.url, r.data.name);
      text(msg, `The zip is ${r.data.name}: your browser saves it, into Downloads unless you chose another folder.`).hidden = false;
    } else {
      text(msg, r.data.error || `The zip could not be made (${r.status}).`).hidden = false;
    }
  } catch (x) {
    text(msg, "songcharter does not answer: is it still running?").hidden = false;
  } finally {
    $("stems-zip").disabled = false;
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
    const r = await api("POST", jobPath("/export/zip"));
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
  text(where, "").hidden = true;   // an earlier refusal goes once this one is asked
  try {
    const r = await api("POST", "/api/open", what === "built" && state.shown ? { what, job: state.shown } : { what });
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
  $("stems-zip").addEventListener("click", exportStems);
  $("listen-part").addEventListener("change", listenLevels);
  $("listen").addEventListener("click", () => listenTo(0));
  $("open-song").addEventListener("click", () => openFolder("song", $("open-msg")));
  $("open-exports").addEventListener("click", () => openFolder("exports", $("export-msg")));
  $("update-copy").addEventListener("click", copyLine);
  $("update-later").addEventListener("click", later);
  $("pause").addEventListener("click", pauseQueue);
  $("carry-on").addEventListener("click", carryOn);
  $("queue-clear").addEventListener("click", clearList);
  $("queue-clear-all").addEventListener("click", clearList);
  $("back").addEventListener("click", () => show("progress-screen"));
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
  setQueue(st.queue);
  showUpdate(st.update);
  setInterval(refreshQueue, 5000);   // the list's states, and a song the server starts by itself
  if (!st.update) for (const ms of UPDATE_ASKS) setTimeout(askForUpdate, ms);
  let dismissed = null;
  try { dismissed = sessionStorage.getItem(DISMISSED); } catch (e) { dismissed = null; }
  if (st.job && (st.job.state === "running" || st.job.job !== dismissed)) attach();
}

document.addEventListener("DOMContentLoaded", start);
