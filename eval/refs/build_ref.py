"""Build refs/<id>/ from an unpacked .sng folder.
usage: python -I build_ref.py <unpacked dir> <refs/id dir> <md5>"""
import sys, os, json, subprocess, shutil, glob
import numpy as np, soundfile as sf
SCAN = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'tools', 'scan-chart', 'scan.cjs')
STRIP = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'strip_lyrics.py')
AUDIO_EXT = ('.ogg', '.opus', '.mp3', '.wav', '.flac')
EXCLUDE = ('crowd', 'preview')
SR = 44100
def decode(path):
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', path, '-vn', '-ac', '2', '-ar', str(SR), '-f', 'f32le', '-'],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.float32).reshape(-1, 2)
def main(src, out, md5):
    os.makedirs(out, exist_ok=True)
    files = sorted(os.listdir(src))
    audio = [f for f in files if f.lower().endswith(AUDIO_EXT)]
    used = [f for f in audio if os.path.splitext(f)[0].lower() not in EXCLUDE]
    excluded = [f for f in audio if f not in used]
    sigs = {f: decode(os.path.join(src, f)) for f in used}
    n = max(len(s) for s in sigs.values())
    mix = np.zeros((n, 2), dtype=np.float64)
    for f, s in sigs.items(): mix[:len(s)] += s
    peak = float(np.max(np.abs(mix)))
    gain = 1.0 if peak <= 0.999 else 0.999 / peak
    mix *= gain
    sf.write(os.path.join(out, 'input.wav'), mix.astype(np.float32), SR, subtype='PCM_16')
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', os.path.join(out, 'input.wav'), '-c:a', 'libmp3lame', '-q:a', '0',
                    os.path.join(out, 'input.mp3')], check=True)
    ref = os.path.join(out, 'ref'); os.makedirs(ref, exist_ok=True)
    chart = [f for f in files if f in ('notes.chart', 'notes.mid')]
    assert len(chart) == 1, chart
    r = subprocess.run([sys.executable, '-I', STRIP, os.path.join(src, chart[0]), os.path.join(ref, chart[0])],
                       capture_output=True, text=True, check=True).stdout.strip()
    shutil.copy(os.path.join(src, 'song.ini'), os.path.join(ref, 'song.ini'))
    # 1 s of silence as the stub audio scan-chart needs
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=mono', '-t', '1',
                    '-c:a', 'libvorbis', os.path.join(ref, 'song.ogg')], check=True)
    notes = subprocess.run(['node', SCAN, ref, '--notes'], capture_output=True, text=True, check=True).stdout
    open(os.path.join(out, 'ref_notes.json'), 'w').write(notes)
    meta = dict(md5=md5, stems_summed=used, stems_excluded=excluded, mix_peak_before_gain=peak, mix_gain=gain,
                sample_rate=SR, duration_s=n / SR, chart_file=chart[0], lyric_strip=r)
    json.dump(meta, open(os.path.join(out, 'build_meta.json'), 'w'), indent=1)
    print(json.dumps(meta))
if __name__ == '__main__':
    main(*sys.argv[1:4])
