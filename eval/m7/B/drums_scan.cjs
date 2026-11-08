// M7-01 B-e: Expert drums of one chart folder (argv[2]) through scan-chart, as eval/scorer/scan_notes.cjs reads it
// (same ini modifiers). Prints JSON: resolution, tempos, time signatures, drumType, delay/chart_offset, the Expert
// drum notes (tick, ms, type, flags) and drum fill (freestyle) sections. No text, sections, lyrics or vocals.
const path = require('path'), fs = require('fs');
const sc = require(path.join(path.dirname(process.env.SONGCHARTER_SCAN_CHART), 'node_modules', 'scan-chart'));
const dir = process.argv[2];
const files = fs.readdirSync(dir).filter(f => fs.statSync(path.join(dir, f)).isFile())
  .map(f => ({ fileName: f, data: new Uint8Array(fs.readFileSync(path.join(dir, f))) }));
const r = sc.scanChartFolder(files);
const out = { drumType: r.notesData && r.notesData.drumType };
const isChart = f => /^notes\.(chart|mid)$/i.test(f.fileName);
const cands = files.filter(f => /\.(chart|mid)$/i.test(f.fileName))
  .sort((a, b) => (isChart(b) - isChart(a)) || ((/\.mid$/i.test(b.fileName)) - (/\.mid$/i.test(a.fileName))));
const mods = {};
for (const k of ['song_length', 'hopo_frequency', 'eighthnote_hopo', 'multiplier_note', 'sustain_cutoff_threshold',
                 'chord_snap_threshold', 'five_lane_drums', 'pro_drums']) if (r[k] !== undefined && r[k] !== null) mods[k] = r[k];
const p = sc.parseChartFile(cands[0].data, /\.mid$/i.test(cands[0].fileName) ? 'mid' : 'chart', mods);
const types = Object.fromEntries(Object.entries(sc.noteTypes).map(([k, v]) => [v, k]));
const flags = n => Object.entries(sc.noteFlags).filter(([, v]) => v && (n & v)).map(([k]) => k);
out.resolution = p.resolution; out.tempos = p.tempos; out.timeSignatures = p.timeSignatures;
const t = p.trackData.find(t => t.instrument === 'drums' && t.difficulty === 'expert');
if (t) {
  out.notes = t.noteEventGroups.flatMap(g => g.map(n => ({ tick: n.tick, ms: n.msTime, type: types[n.type], flags: flags(n.flags) })));
  out.fills = (t.drumFreestyleSections || []).map(x => ({ tick: x.tick, length: x.length, isCoda: x.isCoda }));
}
console.log(JSON.stringify(out));
