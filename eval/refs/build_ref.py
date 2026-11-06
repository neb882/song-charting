"""Build refs/<id>/ from an unpacked .sng folder.
usage: python -I build_ref.py <unpacked dir> <refs/id dir> <md5>
An audio file ffmpeg cannot open, or one with no samples (a package's stub stem: a 135-byte drums.opus), is left
out of the mix and named in build_meta.json's stems_skipped; a package with no usable audio is an error. Every
ffmpeg runs with -nostdin and stdin from /dev/null: build_refs.sh calls this inside a loop that reads its list from
a pipe, and an ffmpeg reading its stdin would eat the list's next lines.
The chart is the file named exactly notes.mid or notes.chart (a notes.mid.backup or a notes.old.mid beside it is
not one); when a package holds both, notes.mid: it is the one scan-chart reads (scanChartFolder puts a .mid before a
.chart), and build_meta.json names the other as chart_not_used. strip_lyrics.py reads a MIDI that mido refuses."""
import sys, os, json, subprocess, shutil
import numpy as np, soundfile as sf
SCAN = os.environ.get('SONGCHARTER_SCAN_CHART') or os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..',
                                                                'tools', 'scan-chart', 'scan.cjs')
STRIP = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'strip_lyrics.py')
AUDIO_EXT = ('.ogg', '.opus', '.mp3', '.wav', '.flac')
EXCLUDE = ('crowd', 'preview')
CHARTS = ('notes.mid', 'notes.chart')   # exact names, in the order scan-chart prefers them
SR = 44100
def run(cmd, **kw):
    return subprocess.run(cmd, stdin=subprocess.DEVNULL, **kw)
def decode(path):
    raw = run(['ffmpeg', '-nostdin', '-v', 'error', '-i', path, '-vn', '-ac', '2', '-ar', str(SR), '-f', 'f32le', '-'],
              capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.float32).reshape(-1, 2)
def pick_chart(files):
    """(the chart file, the chart files it was preferred to): exact names only, notes.mid before notes.chart."""
    found = [c for c in CHARTS if c in files]
    if not found: raise SystemExit('no notes.mid or notes.chart in the package (files: %s)' % ', '.join(files))
    return found[0], found[1:]
def usable(src, files):
    """The audio files that decode to samples, and the others with why (never ffmpeg's text: a file name only)."""
    sigs, skipped = {}, []
    for f in files:
        p = os.path.join(src, f)
        try:
            s = decode(p)
        except subprocess.CalledProcessError:
            skipped.append({'file': f, 'bytes': os.path.getsize(p), 'why': 'ffmpeg cannot open it'})
            continue
        if not len(s):
            skipped.append({'file': f, 'bytes': os.path.getsize(p), 'why': 'no samples'})
            continue
        sigs[f] = s
    return sigs, skipped
def main(src, out, md5):
    os.makedirs(out, exist_ok=True)
    files = sorted(os.listdir(src))
    chart, unused = pick_chart(files)           # before the audio work: a package with no chart costs nothing
    audio = [f for f in files if f.lower().endswith(AUDIO_EXT)]
    listed = [f for f in audio if os.path.splitext(f)[0].lower() not in EXCLUDE]
    excluded = [f for f in audio if f not in listed]
    sigs, skipped = usable(src, listed)
    if not sigs:
        raise SystemExit('no usable audio in %s (skipped: %s)' % (src, ', '.join(s['file'] for s in skipped) or 'none'))
    used = [f for f in listed if f in sigs]
    n = max(len(s) for s in sigs.values())
    mix = np.zeros((n, 2), dtype=np.float64)
    for f, s in sigs.items(): mix[:len(s)] += s
    peak = float(np.max(np.abs(mix)))
    gain = 1.0 if peak <= 0.999 else 0.999 / peak
    mix *= gain
    sf.write(os.path.join(out, 'input.wav'), mix.astype(np.float32), SR, subtype='PCM_16')
    run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-i', os.path.join(out, 'input.wav'), '-c:a', 'libmp3lame',
         '-q:a', '0', os.path.join(out, 'input.mp3')], check=True)
    ref = os.path.join(out, 'ref'); os.makedirs(ref, exist_ok=True)
    r = run([sys.executable, '-I', STRIP, os.path.join(src, chart), os.path.join(ref, chart)],
            capture_output=True, text=True, check=True).stdout.strip()
    shutil.copy(os.path.join(src, 'song.ini'), os.path.join(ref, 'song.ini'))
    # 1 s of silence as the stub audio scan-chart needs
    run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=mono', '-t', '1',
         '-c:a', 'libvorbis', os.path.join(ref, 'song.ogg')], check=True)
    notes = run(['node', SCAN, ref, '--notes'], capture_output=True, text=True, check=True).stdout
    open(os.path.join(out, 'ref_notes.json'), 'w').write(notes)
    meta = dict(md5=md5, stems_summed=used, stems_excluded=excluded, stems_skipped=skipped,
                mix_peak_before_gain=peak, mix_gain=gain, sample_rate=SR, duration_s=n / SR, chart_file=chart,
                lyric_strip=r)
    if unused: meta['chart_not_used'] = unused
    json.dump(meta, open(os.path.join(out, 'build_meta.json'), 'w'), indent=1)
    print(json.dumps(meta))
if __name__ == '__main__':
    main(*sys.argv[1:4])
