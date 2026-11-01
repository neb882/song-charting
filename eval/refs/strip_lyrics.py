"""Copy a chart file, dropping vocal/lyric data (never prints it).
.mid : drops tracks PART VOCALS / HARM1-3 / PART HARM*, and any 'lyrics' meta events elsewhere.
.chart: drops [Events] lines  E "lyric ..." / E "phrase_start" / E "phrase_end".
usage: python -I strip_lyrics.py <in> <out>   -> prints counts only"""
import sys, re
def strip_mid(src, dst):
    import mido
    m = mido.MidiFile(src)
    keep = []; dropped_tracks = 0; dropped_ev = 0
    for t in m.tracks:
        nm = (t.name or '').strip().upper()
        if nm in ('PART VOCALS', 'HARM1', 'HARM2', 'HARM3') or nm.startswith('PART HARM'):
            dropped_tracks += 1; continue
        nt = mido.MidiTrack(); carry = 0
        for msg in t:
            if msg.type == 'lyrics':
                carry += msg.time; dropped_ev += 1; continue
            if carry: msg = msg.copy(time=msg.time + carry); carry = 0
            nt.append(msg)
        keep.append(nt)
    m.tracks = keep
    m.save(dst)
    return dropped_tracks, dropped_ev
def strip_chart(src, dst):
    raw = open(src, 'rb').read()
    txt = raw.decode('utf-8-sig', errors='replace')
    out = []; sec = None; n = 0
    for line in txt.splitlines(keepends=True):
        s = line.strip()
        if s.startswith('['): sec = s
        if sec == '[Events]' and re.search(r'=\s*E\s+"(lyric\b|phrase_start|phrase_end)', s):
            n += 1; continue
        out.append(line)
    open(dst, 'w', encoding='utf-8', newline='').write(''.join(out))
    return 0, n
if __name__ == '__main__':
    src, dst = sys.argv[1], sys.argv[2]
    r = strip_mid(src, dst) if src.lower().endswith('.mid') else strip_chart(src, dst)
    print('dropped tracks=%d events=%d' % r)
