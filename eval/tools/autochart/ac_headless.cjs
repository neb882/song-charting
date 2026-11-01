#!/usr/bin/env node
// Headless driver for dvar0/autochart's REAL engine (engine/bin/autochart-engine.cjs,
// onnxruntime-node), without Electron. It writes the same job.json the app's
// electron/engineManager.cjs writes, runs one engine process per difficulty
// (the app runs one job per take), then assembles the song folder the way the
// app's final-chart + Clone Hero export do (src/services/chartVersions.js
// createFinalChartVersion, electron/libraryStore.cjs buildSongIni /
// writeCloneHeroAudio). This file is our own code; it does not modify the app.
//
// usage: node ac_headless.cjs --audio <file> --out <song folder> --work <scratch dir>
// env:   AC_DIFFICULTIES  expert (default) | all | comma list of easy,medium,hard,expert
//        AC_SEED          fixed decoder seed (default 20260609, the engine's default seed;
//                         the app's UI default is a random seed)
//        AC_TEMPERATURE / AC_TOP_P   default 0.95 / 0.98 (the app's "Standard" preset)
//        AC_MAX_TOKENS    watchdog token cap per job (default 8192 = the model's own budget)
//        AC_TIMEOUT_S     wall-clock cap per engine job (default 3600)
//        AC_STALL_S       kill if the decoder emits no progress for this long (default 900)
//        AC_TITLE / AC_ARTIST  metadata (default: input file name / "Unknown Artist")
"use strict";

const fs = require("fs");
const fsp = require("fs/promises");
const path = require("path");
const crypto = require("crypto");
const { spawn, execFileSync } = require("child_process");
// cpu (default), cuda or webgpu. The engine falls back to CPU by itself if the device fails; check the log.
const DEVICE = process.env.AC_DEVICE || "cpu";

const HERE = __dirname;
const APP_ROOT = process.env.AC_APP_ROOT || path.join(HERE, "src");
const ENGINE_ROOT = path.join(APP_ROOT, "engine");
const MODELS = process.env.AC_MODELS || path.join(HERE, "models");
const GENERATOR_ID = "autochart.fretformer.v2-onnx";
const SLOT_ORDER = ["easy", "medium", "hard", "expert"]; // app FINAL_SLOT_ORDER
const RUN_ORDER = ["expert", "hard", "medium", "easy"]; // expert first; later jobs reuse its separation + beat map
const SECTION = { easy: "EasySingle", medium: "MediumSingle", hard: "HardSingle", expert: "ExpertSingle" };

function arg(name, fallback = null) {
  const i = process.argv.indexOf(name);
  return i >= 0 && process.argv[i + 1] ? process.argv[i + 1] : fallback;
}
function log(msg) { process.stderr.write(`[autochart] ${msg}\n`); }
function envNum(name, fallback) {
  const v = Number(process.env[name]);
  return Number.isFinite(v) && String(process.env[name] || "").trim() !== "" ? v : fallback;
}
function fail(msg) { const e = new Error(msg); e.userFacing = true; throw e; }

function findSection(lines, name) {
  for (let i = 0; i < lines.length; i++) {
    if (lines[i].trim() !== `[${name}]`) continue;
    let open = i + 1;
    while (open < lines.length && lines[open].trim() !== "{") open++;
    let close = open + 1;
    while (close < lines.length && lines[close].trim() !== "}") close++;
    if (open >= lines.length || close >= lines.length) return null;
    return { header: i, bodyStart: open + 1, bodyEnd: close, close };
  }
  return null;
}
function sectionBody(text, name) {
  const lines = text.split(/\r?\n/);
  const s = findSection(lines, name);
  return s ? lines.slice(s.bodyStart, s.bodyEnd) : null;
}
function removeSection(text, name) {
  const lines = text.split(/\r?\n/);
  const s = findSection(lines, name);
  if (!s) return text;
  return [...lines.slice(0, s.header), ...lines.slice(s.close + 1)].join("\n");
}
function timingKey(text) {
  const song = (sectionBody(text, "Song") || []).filter((l) => /^\s*(Resolution|Offset)\s*=/.test(l)).map((l) => l.trim());
  return JSON.stringify([song, (sectionBody(text, "SyncTrack") || []).map((l) => l.trim())]);
}
// shared/chartProvenance.js updateChartMetadata, same behavior for our fields.
function updateSongFields(text, fields) {
  return text.replace(/(^﻿?[ \t]*\[Song\][ \t]*\r?\n[ \t]*\{[ \t]*)([^]*?)(^[ \t]*\})/im, (_, open, body, close) => {
    const pending = new Map(Object.entries(fields).map(([k, v]) => [k.toLowerCase(), [k, String(v ?? "").trim()]]));
    const lines = body.split(/\r?\n/).filter((line) => !pending.has(line.match(/^\s*([^=]+?)\s*=/)?.[1]?.toLowerCase()));
    while (lines.length && !lines[lines.length - 1].trim()) lines.pop();
    while (lines.length && !lines[0].trim()) lines.shift();
    for (const [key, value] of pending.values()) if (value) lines.push(`  ${key} = "${value}"`);
    return `${open}\n${lines.join("\n")}\n${close}`;
  });
}
function iniValue(v) { return String(v ?? "").replace(/\r\n?|[\n\u2028\u2029]/g, " ").trim(); }

async function sha256File(file) {
  const h = crypto.createHash("sha256");
  await new Promise((resolve, reject) => fs.createReadStream(file).on("data", (c) => h.update(c)).on("end", resolve).on("error", reject));
  return h.digest("hex");
}

function runEngineJob(jobPath, outputDir, { maxTokens, timeoutS, stallS, ffmpeg, label }) {
  return new Promise((resolve) => {
    const eventsPath = path.join(outputDir, "..", "events.ndjson");
    const events = fs.createWriteStream(eventsPath);
    const env = { ...process.env, AUTOCHART_FFMPEG_PATH: ffmpeg };
    delete env.ELECTRON_RUN_AS_NODE;
    const t0 = Date.now();
    const child = spawn(process.execPath, [path.join(ENGINE_ROOT, "bin", "autochart-engine.cjs"), "generate", "--job", jobPath], {
      cwd: ENGINE_ROOT, env, stdio: ["ignore", "pipe", "pipe"],
    });
    let killedFor = "";
    let stage = "";
    let lastProgress = Date.now();
    let maxTokenCount = 0;
    const kill = (why) => { if (!killedFor) { killedFor = why; log(`${label}: killing engine: ${why}`); child.kill("SIGKILL"); } };
    const wall = setTimeout(() => kill(`wall-clock timeout ${timeoutS}s`), timeoutS * 1000);
    const stall = setInterval(() => {
      if (stage === "transcription" && Date.now() - lastProgress > stallS * 1000) kill(`no decoder progress for ${stallS}s`);
    }, 5000);
    let buf = "";
    child.stdout.on("data", (chunk) => {
      events.write(chunk);
      buf += chunk.toString("utf8");
      let nl;
      while ((nl = buf.indexOf("\n")) >= 0) {
        const line = buf.slice(0, nl); buf = buf.slice(nl + 1);
        let e; try { e = JSON.parse(line); } catch { continue; }
        const t = ((Date.now() - t0) / 1000).toFixed(1);
        if (e.type === "stage" && (e.status === "completed" || e.status === "failed" || e.status === "skipped" || (e.status === "running" && e.stage !== stage))) {
          if (e.status === "running") { stage = e.stage; lastProgress = Date.now(); }
          log(`${label} ${t}s stage ${e.stage} ${e.status}${e.device ? ` device=${e.device}` : ""}${e.cache ? ` cache=${e.cache}` : ""}${e.nTokens ? ` nTokens=${e.nTokens}` : ""}`);
        } else if (e.type === "partial_chart") {
          lastProgress = Date.now();
          maxTokenCount = Math.max(maxTokenCount, Number(e.tokenCount) || 0);
          if (maxTokenCount > maxTokens) kill(`token cap ${maxTokens} exceeded (${maxTokenCount})`);
        } else if (e.type === "runtime_fallback") {
          log(`${label} runtime fallback ${e.from} -> ${e.to}: ${e.reason}`);
        } else if (e.type === "error") {
          log(`${label} engine error: ${e.message}`);
        } else if (e.type === "log" && /decode loop|decoded \d+ tokens|beat:|wrote /.test(String(e.message))) {
          log(`${label} ${t}s ${String(e.message).slice(0, 220)}`);
        }
      }
    });
    child.stderr.on("data", (c) => { events.write(c); process.stderr.write(c); });
    child.on("close", (code, signal) => {
      clearTimeout(wall); clearInterval(stall); events.end();
      resolve({ code, signal, killedFor, wallSeconds: (Date.now() - t0) / 1000, maxTokenCount, eventsPath });
    });
  });
}

async function main() {
  const audioIn = path.resolve(arg("--audio") || fail("missing --audio"));
  const outDir = path.resolve(arg("--out") || fail("missing --out"));
  const work = path.resolve(arg("--work") || fail("missing --work"));
  if (!fs.existsSync(audioIn)) fail(`input audio not found: ${audioIn}`);
  const ffmpeg = process.env.AUTOCHART_FFMPEG_PATH || execFileSync("bash", ["-lc", "command -v ffmpeg"]).toString().trim();
  const diffEnv = String(process.env.AC_DIFFICULTIES || "expert").trim().toLowerCase();
  const wanted = diffEnv === "all" ? SLOT_ORDER.slice() : diffEnv.split(",").map((s) => s.trim()).filter(Boolean);
  for (const d of wanted) if (!SECTION[d]) fail(`unknown difficulty: ${d}`);
  const seed = Math.trunc(envNum("AC_SEED", 20260609));
  const temperature = envNum("AC_TEMPERATURE", 0.95);
  const topP = envNum("AC_TOP_P", 0.98);
  const maxTokens = Math.trunc(envNum("AC_MAX_TOKENS", 8192));
  const timeoutS = envNum("AC_TIMEOUT_S", 3600);
  const stallS = envNum("AC_STALL_S", 900);
  const title = process.env.AC_TITLE || path.basename(audioIn, path.extname(audioIn));
  const artist = process.env.AC_ARTIST || "Unknown Artist";

  const manifest = JSON.parse(await fsp.readFile(path.join(ENGINE_ROOT, "manifest.json"), "utf8"));
  const generator = manifest.generators.find((g) => g.id === GENERATOR_ID) || fail(`${GENERATOR_ID} not in engine manifest`);
  if (!fs.existsSync(path.join(MODELS, generator.models.onnxFolder, "manifest.json"))) fail(`models missing under ${MODELS}; run fetch_models.sh`);

  // electron/engineManager.cjs cacheAudio(): the engine reads a copy named source<ext>, keyed by SHA-256.
  const cacheDir = path.join(work, "engine-cache");
  const sha = await sha256File(audioIn);
  const ext = (path.extname(audioIn) || ".ogg").toLowerCase();
  const audioDir = path.join(cacheDir, "audio", sha.slice(0, 2), sha);
  await fsp.mkdir(audioDir, { recursive: true });
  const audioPath = path.join(audioDir, `source${ext}`);
  await fsp.copyFile(audioIn, audioPath);
  const demucsWorkspace = path.join(cacheDir, "features", "fretformer_demucs_v1", sha, "demucs_default");
  const timingWorkspace = path.join(cacheDir, "features", "fretformer_timing_v1", sha);
  await fsp.mkdir(demucsWorkspace, { recursive: true });
  await fsp.mkdir(timingWorkspace, { recursive: true });

  const knobs = Object.fromEntries((generator.capabilities.descriptorKnobs || []).map((k) => [k, null]));
  const takes = {};
  const runs = [];
  for (const difficulty of RUN_ORDER.filter((d) => wanted.includes(d))) {
    const jobId = crypto.randomUUID();
    const jobDir = path.join(work, "jobs", `${difficulty}-${jobId}`);
    const outputDir = path.join(jobDir, "output");
    await fsp.mkdir(outputDir, { recursive: true });
    // src/data/generationSettings.js DEFAULT_GENERATION_CONTROLS + resolveGenerationSettings,
    // with a fixed seed instead of the UI's random one.
    const controls = {
      presetId: "standard", difficulty, temperature: String(temperature), topP: String(topP),
      timingDetector: "beat_this_custom_timing", timingSmoothing: true, leadInSilenceSeconds: "0",
      seedMode: "fixed", seed: String(seed), stripSustains: false, knobs, guidanceScale: 2, solos: true, forceSolo: false,
    };
    const resolved = {
      difficulty, temperature, topP, stripSustains: false, sustainsLockedOff: true,
      timingDetector: "beat_this_custom_timing", detector: "beat_this_custom_timing", timingRaw: true, bpmTolerance: 0,
      timingSmoothing: { enabled: true, method: "line-fit", bpmRound: 0.5 },
      leadInSilenceSeconds: 0, leadInSilenceMs: 0, seed, knobs, knobsActive: false, guidanceScale: 2, solos: true, forceSolo: false,
    };
    const job = {
      schemaVersion: 1, jobId, generatorId: GENERATOR_ID, generatorLabel: generator.label, generator,
      engineVersion: manifest.engineVersion,
      audioPath, audioSha256: sha, originalAudioSha256: sha, audioIdentity: null,
      sourceTransform: { kind: "original", leadInSilenceSeconds: 0, leadInSilenceMs: 0, key: "lead-in:0", label: "No lead-in" },
      outputDir, cacheDir, title, metadata: { title, artist },
      difficulty, stripSustains: false,
      generation: { generatorId: GENERATOR_ID, presetId: "standard", presetName: "Standard", modified: true, controls, resolved },
      timingDevice: DEVICE, transcriberDevice: DEVICE, demucsDevice: DEVICE, hardwareMode: DEVICE, keepStems: false,
      demucsWorkspace, timingWorkspace,
      engine: { platform: process.platform, runtime: null, modelsFolder: MODELS, modelRoots: [MODELS] },
      createdAt: Date.now(),
    };
    const jobPath = path.join(jobDir, "job.json");
    await fsp.writeFile(jobPath, `${JSON.stringify(job, null, 2)}\n`);
    log(`${difficulty}: engine job ${jobPath}`);
    const r = await runEngineJob(jobPath, outputDir, { maxTokens, timeoutS, stallS, ffmpeg, label: difficulty });
    const resultPath = path.join(outputDir, "result.json");
    const result = fs.existsSync(resultPath) ? JSON.parse(await fsp.readFile(resultPath, "utf8")) : null;
    const reportPath = path.join(outputDir, "chart", "full_song_report.json");
    const report = fs.existsSync(reportPath) ? JSON.parse(await fsp.readFile(reportPath, "utf8")) : null;
    runs.push({ difficulty, jobDir, exitCode: r.code, signal: r.signal, killedFor: r.killedFor, wallSeconds: r.wallSeconds,
      status: result?.status || null, error: result?.error || null, failedStage: result?.failedStage || null,
      nTokens: report?.token_stats?.n_tokens ?? null, nBeats: report?.token_stats?.n_beats ?? null,
      generationSeconds: report?.token_stats?.generation_seconds ?? null, noteLines: report?.note_line_count ?? null,
      devices: result?.provenance?.runtime?.devices || null, cachedStages: result?.provenance?.runtime?.cachedStages || null,
      tempoBpm: report?.timing?.tempoBpm ?? null, audioDuration: report?.timing?.audioDuration ?? null });
    if (r.killedFor) fail(`${difficulty}: ${r.killedFor}`);
    if (r.code !== 0 || result?.status !== "completed") fail(`${difficulty}: engine failed (exit ${r.code}${r.signal ? ` ${r.signal}` : ""}) ${result?.failedStage || ""} ${result?.error || ""}`);
    if (report?.token_stats?.n_tokens >= maxTokens) log(`${difficulty}: WARNING decoder used its whole ${maxTokens}-token budget; the end of the chart may be missing`);
    takes[difficulty] = { text: await fsp.readFile(result.chartPath, "utf8"), report, result };
  }

  // createFinalChartVersion: one shared beat map; base text = first assigned slot (easy..expert order).
  const assigned = SLOT_ORDER.filter((d) => takes[d]);
  const key0 = timingKey(takes[assigned[0]].text);
  for (const d of assigned) if (timingKey(takes[d].text) !== key0) fail(`takes do not share one beat map (${d})`);
  let chart = takes[assigned[0]].text;
  for (const d of SLOT_ORDER) chart = removeSection(chart, SECTION[d]);
  for (const d of assigned) {
    const body = sectionBody(takes[d].text, SECTION[d]) || fail(`${d}: chart has no [${SECTION[d]}]`);
    chart = `${chart.replace(/\s*$/, "")}\n[${SECTION[d]}]\n{\n${body.join("\n")}\n}\n`;
  }
  const prov = {
    autochart_provenance_version: "1", autochart_ai_generated: "true",
    autochart_generated_difficulties: assigned.join(","), autochart_generator: GENERATOR_ID,
  };
  chart = updateSongFields(chart, { Charter: "Autochart", Genre: "", ...prov });

  await fsp.mkdir(outDir, { recursive: true });
  await fsp.writeFile(path.join(outDir, "notes.chart"), chart);
  // libraryStore.cjs writeCloneHeroAudio (no lead-in): copy .ogg, else Vorbis q5.
  const songOgg = path.join(outDir, "song.ogg");
  if (ext === ".ogg") await fsp.copyFile(audioPath, songOgg);
  else execFileSync(ffmpeg, ["-hide_banner", "-loglevel", "error", "-y", "-i", audioPath, "-map", "0:a:0", "-vn", "-c:a", "libvorbis", "-q:a", "5", songOgg]);
  const durationSec = Number(takes[assigned[0]].report?.timing?.audioDuration) || 0;
  // libraryStore.cjs buildSongIni
  const ini = [
    ["name", iniValue(title) || "Untitled"], ["artist", artist], ["charter", "Autochart"], ...Object.entries(prov),
    ["autochart_export", "1"],
    ["loading_phrase", `Contains AI-generated guitar difficulties: ${prov.autochart_generated_difficulties}. Generated with Autochart.`],
    ["song_length", durationSec ? Math.round(durationSec * 1000) : ""],
  ].map(([k, v]) => [k, iniValue(v)]).filter(([, v]) => v).map(([k, v]) => `${k} = ${v}`);
  await fsp.writeFile(path.join(outDir, "song.ini"), `[song]\n${ini.join("\n")}\n`);

  // Run records (no .chart files here, so Clone Hero won't see a second song).
  const logDir = path.join(outDir, "autochart_run");
  await fsp.mkdir(logDir, { recursive: true });
  for (const run of runs) {
    for (const f of ["job.json", "events.ndjson", "output/result.json", "output/timing.json", "output/chart/full_song_report.json"]) {
      const src = path.join(run.jobDir, f);
      if (fs.existsSync(src)) await fsp.copyFile(src, path.join(logDir, `${run.difficulty}_${path.basename(f)}`));
    }
  }
  const summary = { tool: "autochart", generatorId: GENERATOR_ID, engineVersion: manifest.engineVersion, input: audioIn,
    inputSha256: sha, seed, temperature, topP, difficulties: assigned, maxTokens, timeoutS, stallS, ffmpeg, runs };
  await fsp.writeFile(path.join(logDir, "summary.json"), `${JSON.stringify(summary, null, 2)}\n`);
  process.stdout.write(`${JSON.stringify(summary)}\n`);
}

main().catch((err) => {
  log(`FAILED: ${err.message}`);
  process.exit(1);
});
