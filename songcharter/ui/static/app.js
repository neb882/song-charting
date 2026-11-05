// songcharter's page (M4-04, M4-06, M4-11): drop a song, choose the options (the lyrics and the pictures too), follow
// the chart, cancel it; then the album art, the preview, the zip, the install into Clone Hero, and the diagnostics in
// the footer. No framework, no build
// step. Every request sends X-Songcharter: 1 (the server's guard for anything but a GET). The job's events come over
// a streamed fetch of /api/jobs/current/events (Server-Sent Events), which can send that header too, and which
// resumes after the last event it saw when the connection drops; a reload reattaches to the current job.
"use strict";

const HEADER = { "X-Songcharter": "1" };
const CLOSING = new Set(["result", "error", "cancelled"]);
const LABELS = {
  decode: "Read the song", separate: "Separate the instruments", drums: "Drums", bass: "Bass",
  sections: "Sections", lyrics: "Lyrics", guitar: "Guitar", assemble: "Build and check the chart", preview: "Preview",
};
const DISMISSED = "songcharter.dismissed";   // sessionStorage: the finished job "Chart another song" put away

const $ = (id) => document.getElementById(id);
const state = { status: null, upload: null, job: null, stages: {}, offset: 0, ticker: null, follow: 0, ch: null,
  images: { album_art: null, background: null }, sending: 0 };
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
  // a file dropped beside the zone must not navigate away from the page
  window.addEventListener("dragover", (e) => e.preventDefault());
  window.addEventListener("drop", (e) => e.preventDefault());
  $("file").addEventListener("change", (e) => { const f = e.target.files[0]; if (f) upload(f); e.target.value = ""; });
}

// ------------------------------------------------------------------------------------------------ options

const META = { title: "name", artist: "artist", album: "album", year: "year", genre: "genre" };

function fillOptions(up) {
  const form = $("options");
  form.reset();
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
  $("chart").disabled = true;
  const done = () => { state.sending -= 1; $("chart").disabled = state.sending > 0; };
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
  $("chart").disabled = true;
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
    $("chart").disabled = false;
  }
}

// ------------------------------------------------------------------------------------------------ progress

function resetProgress(job) {
  state.stages = {};
  $("stages").replaceChildren();
  $("warnings").replaceChildren();
  $("fallbacks").replaceChildren();
  $("cancel").disabled = false;
  $("cancel").hidden = false;
  text($("progress-title"), "3. Charting");
  text($("progress-song"), job && job.upload ? job.upload.name : "");
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
      break;
    }
    case "stage_end": {
      const row = stageRow(ev.stage);
      row.ended = true;
      setRow(row, ev.cached ? "cached" : "done", "✓");
      text(row.detail, ev.detail);
      text(row.time, ev.cached ? `${seconds(ev.seconds)} (cached)` : seconds(ev.seconds));
      text(row.takes, "");
      break;
    }
    case "take":
      // a take run again on the CPU after its GPU run failed says so (the banner above gives why)
      text(stageRow("guitar").takes,
           `take ${ev.index} of ${ev.count}${ev.device === "cpu" ? " (on the CPU)" : ""}`);
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
      stopRunningRows("stopped");
      finish(ev.ok ? "Ready" : "The check failed",
             ev.ok ? `The song folder is in ${ev.folder}` :
               `The build did not pass the check. It is in ${ev.folder} for a look.`, ev.summary);
      loadResults();
      return true;
    case "error":
      stopRunningRows("stopped");
      finish("It did not finish", ev.message, null);
      return true;
    case "cancelled":
      stopRunningRows("cancelled");
      finish("Cancelled", "The chart was cancelled. What it had worked out is kept, so the same song goes faster next time.", null);
      return true;
    default:
      break;
  }
  return false;
}

function finish(title, message, summary) {
  $("results").hidden = true;
  clearInterval(state.ticker);
  state.ticker = null;
  $("cancel").hidden = true;
  text($("done-title"), title);
  text($("done-text"), message);
  const pre = $("summary");
  pre.hidden = !summary;
  text(pre, summary || "");
  $("done-screen").hidden = false;
}

async function follow(token) {
  let last = -1;
  for (;;) {
    if (token !== state.follow) return;
    try {
      const headers = { ...HEADER };
      if (last >= 0) headers["Last-Event-ID"] = String(last);
      const r = await fetch("/api/jobs/current/events", { headers, cache: "no-store" });
      if (r.status === 404) return;
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
      // the connection dropped: try again, from the last event seen
    }
    await new Promise((ok) => setTimeout(ok, 2000));
  }
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
  dropError("");
  show("drop-screen");
  refreshStatus();   // a session of charts fills the disk: the header measures it again for the next song
}

async function refreshStatus() {
  try {
    const r = await api("GET", "/api/status");
    if (r.status !== 200) return;
    state.status = r.data;
    renderStatus(r.data);
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
  renderArt(res.art, res.name, res.job);
  renderLyrics(res.lyrics);
  renderPreview(res.preview, res.job);
  $("export-box").hidden = !res.installable;
  text($("export-msg"), "").hidden = true;
  $("open-exports").hidden = true;
  $("results").hidden = false;
  if (res.installable) loadCloneHero();
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

function thumb(url, label, cls) {
  const a = make("a");
  a.href = url;
  a.target = "_blank";
  a.rel = "noopener";
  const img = make("img", cls);
  img.src = url;
  img.alt = label;
  a.append(img, make("span", "small", label));
  return a;
}

function renderPreview(pv, job) {
  const has = !!(pv && pv.overview);
  $("preview").hidden = !has;
  $("no-preview").hidden = has;
  if (!has) {
    text($("no-preview"), `No preview: ${(pv && pv.why) || "no reason given"}`);
    return;
  }
  const v = `?job=${encodeURIComponent(job)}`;   // a new chart's pictures, not the browser's copy of the last one's
  $("overview").src = pv.overview + v;
  $("overview-link").href = pv.overview + v;
  $("pages").replaceChildren(...pv.pages.map((u, i) => thumb(u + v, `Page ${i + 1}`, "thumb")));
  const flags = pv.flags.length ? pv.flags : ["Nothing flagged."];
  $("flags").replaceChildren(...flags.map((f) => make("li", null, f)));
  $("remarks").replaceChildren(...pv.remarks.map((f) => make("li", null, f)));
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
  $("options").addEventListener("submit", chartIt);
  $("options").elements.solos.addEventListener("change", soloNames);
  $("other-song").addEventListener("click", again);
  $("cancel").addEventListener("click", cancel);
  $("again").addEventListener("click", again);
  $("ch-form").addEventListener("submit", saveFolder);
  $("ch-change").addEventListener("click", () => renderCloneHero(true));
  $("install").addEventListener("click", () => install(false));
  $("replace").addEventListener("click", () => install(true));
  $("zip").addEventListener("click", exportZip);
  $("open-song").addEventListener("click", () => openFolder("song", $("open-msg")));
  $("open-exports").addEventListener("click", () => openFolder("exports", $("export-msg")));
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
  let dismissed = null;
  try { dismissed = sessionStorage.getItem(DISMISSED); } catch (e) { dismissed = null; }
  if (st.job && (st.job.state === "running" || st.job.job !== dismissed)) attach();
}

document.addEventListener("DOMContentLoaded", start);
