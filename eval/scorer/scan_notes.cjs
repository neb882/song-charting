// Usage: node scan_notes.cjs <song folder>
// Same output as tools/scan-chart/scan.cjs --notes, except:
//  - the chart file is picked the way scan-chart/Clone Hero picks it (notes.mid preferred over notes.chart),
//  - the song.ini chart modifiers (hopo_frequency, eighthnote_hopo, sustain_cutoff_threshold, chord_snap_threshold,
//    multiplier_note, song_length, pro_drums, five_lane_drums) are passed to parseChartFile,
//  - each note also carries msLength, and the top level carries delay / chart_offset / chartFile.
// Sections, lyrics and vocal tracks are NOT printed.
const path = require('path'), fs = require('fs');
const sc = require(path.join(__dirname, '..', '..', 'tools', 'scan-chart', 'node_modules', 'scan-chart'));
const dir = process.argv[2];
const files = fs.readdirSync(dir).filter(f => fs.statSync(path.join(dir, f)).isFile())
  .map(f => ({ fileName: f, data: new Uint8Array(fs.readFileSync(path.join(dir, f))) }));
const r = sc.scanChartFolder(files);
const nd = r.notesData;
const out = {
  playable: r.playable,
  folderIssues: r.folderIssues, metadataIssues: r.metadataIssues,
  instruments: nd && nd.instruments, drumType: nd && nd.drumType,
  chartIssues: nd && nd.chartIssues, noteCounts: nd && nd.noteCounts,
  tempoMarkerCount: nd && nd.tempoMarkerCount, effectiveLength: nd && nd.effectiveLength,
  delay: r.delay, chart_offset: r.chart_offset,
};
const isChart = f => /^notes\.(chart|mid)$/i.test(f.fileName);
const cands = files.filter(f => /\.(chart|mid)$/i.test(f.fileName))
  .sort((a, b) => (isChart(b) - isChart(a)) || ((/\.mid$/i.test(b.fileName)) - (/\.mid$/i.test(a.fileName))));
if (cands.length) {
  const chartFile = cands[0];
  const mods = {};
  for (const k of ['song_length', 'hopo_frequency', 'eighthnote_hopo', 'multiplier_note', 'sustain_cutoff_threshold',
                   'chord_snap_threshold', 'five_lane_drums', 'pro_drums']) if (r[k] !== undefined && r[k] !== null) mods[k] = r[k];
  out.chartFile = chartFile.fileName; out.iniChartModifiers = mods;
  try {
    const p = sc.parseChartFile(chartFile.data, /\.mid$/i.test(chartFile.fileName) ? 'mid' : 'chart', mods);
    const types = Object.fromEntries(Object.entries(sc.noteTypes).map(([k, v]) => [v, k]));
    const flags = n => Object.entries(sc.noteFlags).filter(([, v]) => v && (n & v)).map(([k]) => k);
    out.resolution = p.resolution;
    out.tempos = p.tempos; out.timeSignatures = p.timeSignatures;
    out.tracks = p.trackData.map(t => ({
      instrument: t.instrument, difficulty: t.difficulty,
      notes: t.noteEventGroups.flatMap(g => g.map(n => ({ tick: n.tick, ms: n.msTime, type: types[n.type], length: n.length,
        msLength: n.msLength, flags: flags(n.flags) }))),
    }));
  } catch (e) { out.parseError = String(e && e.message || e); }
}
console.log(JSON.stringify(out));
