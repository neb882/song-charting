// Usage: node scan.cjs <song folder> [--notes]
// Prints JSON: playable, folder/metadata/chart issues, and (with --notes) every parsed note with its
// time in ms and its strum/hopo/tap/cymbal flags, as Clone Hero would read them.
const path = require('path'), fs = require('fs');
const sc = require('scan-chart');
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
};
if (process.argv.includes('--notes')) {
  const chartFile = files.find(f => f.fileName === 'notes.chart' || f.fileName === 'notes.mid');
  const p = sc.parseChartFile(chartFile.data, chartFile.fileName.endsWith('.mid') ? 'mid' : 'chart',
    { pro_drums: r.pro_drums, five_lane_drums: r.five_lane_drums });
  const types = Object.fromEntries(Object.entries(sc.noteTypes).map(([k, v]) => [v, k]));
  const flags = n => Object.entries(sc.noteFlags).filter(([, v]) => v && (n & v)).map(([k]) => k);
  out.resolution = p.resolution;
  out.tempos = p.tempos; out.timeSignatures = p.timeSignatures; out.sections = p.sections;
  out.tracks = p.trackData.map(t => ({
    instrument: t.instrument, difficulty: t.difficulty,
    starPower: t.starPowerSections, solos: t.soloSections, activation: t.drumFreestyleSections,
    notes: t.noteEventGroups.flatMap(g => g.map(n => ({ tick: n.tick, ms: n.msTime, type: types[n.type], length: n.length, flags: flags(n.flags) }))),
  }));
}
console.log(JSON.stringify(out));
