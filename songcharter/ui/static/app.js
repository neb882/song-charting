// songcharter's page (M4-04): drop a song, choose the options, follow the chart, cancel it. No framework, no build
// step. Every request sends X-Songcharter: 1 (the server's guard for anything but a GET). The job's events come over
// a streamed fetch of /api/jobs/current/events (Server-Sent Events), which can send that header too, and which
// resumes after the last event it saw when the connection drops; a reload reattaches to the current job.
"use strict";

const HEADER = { "X-Songcharter": "1" };
const CLOSING = new Set(["result", "error", "cancelled"]);
const LABELS = {
  decode: "Read the song", separate: "Separate the instruments", drums: "Drums", bass: "Bass",
  sections: "Sections", guitar: "Guitar", assemble: "Build and check the chart", preview: "Preview",
};
const DISMISSED = "songcharter.dismissed";   // sessionStorage: the finished job "Chart another song" put away

const $ = (id) => document.getElementById(id);
const state = { status: null, upload: null, job: null, stages: {}, offset: 0, ticker: null, follow: 0 };

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
  text($("options-error"), "").hidden = true;
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
      text(stageRow("guitar").takes, `take ${ev.index} of ${ev.count}`);
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
}

// ------------------------------------------------------------------------------------------------ start

async function start() {
  setupDrop();
  $("options").addEventListener("submit", chartIt);
  $("options").elements.solos.addEventListener("change", soloNames);
  $("other-song").addEventListener("click", again);
  $("cancel").addEventListener("click", cancel);
  $("again").addEventListener("click", again);
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
