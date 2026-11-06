"""Copy a chart file, dropping vocal/lyric data (never prints it).
.mid : drops tracks PART VOCALS / HARM1-3 / PART HARM*, and any 'lyrics' meta events elsewhere. Every other byte is
       copied as it is: the file is walked event by event, not read into a MIDI library and written back. A library
       refuses what the charting tools read: a Phase Shift sysex whose difficulty byte is 0xFF ("every difficulty"
       for a tap or open marker; mido: ValueError, and clip=True turns it into 0x7F, which scan-chart no longer reads
       as "all"), and a channel event in running status straight after a sysex (mido keeps the sysex as the running
       status and reads the next bytes as a sysex: EOFError). The walk follows midi-file's rules, the parser behind
       scan-chart: the running status is kept across sysex and meta events, the header's track count bounds the
       tracks read, and what follows the last track is not read.
.chart: drops [Events] lines  E "lyric ..." / E "phrase_start" / E "phrase_end".
usage: python -I strip_lyrics.py <in> <out>   -> prints counts only"""
import sys, re, struct
VOCAL_TRACKS = ('PART VOCALS', 'HARM1', 'HARM2', 'HARM3')
def _vlq(b, p):
    """The variable-length number at b[p]: (value, the position after it)."""
    v = 0
    while True:
        if p >= len(b): raise ValueError('MIDI: a variable-length number runs past its track')
        c = b[p]; p += 1; v = (v << 7) | (c & 0x7F)
        if not c & 0x80: return v, p
def _put_vlq(v):
    out = [v & 0x7F]; v >>= 7
    while v: out.append(0x80 | (v & 0x7F)); v >>= 7
    return bytes(reversed(out))
def _is_vocal(name):
    name = name.strip().upper()
    return name in VOCAL_TRACKS or name.startswith('PART HARM')
def strip_track(body):
    """One MTrk's bytes -> (the bytes without its lyrics events, how many were dropped), or None for a vocal track."""
    out = bytearray(); q = 0; last = None; carry = 0; dropped = 0; named = False
    while q < len(body):
        start = q
        delta, q = _vlq(body, q)
        if q >= len(body): raise ValueError('MIDI: an event with no status byte')
        s = body[q]; kind = None
        if s == 0xFF:
            if q + 1 >= len(body): raise ValueError('MIDI: a meta event with no type')
            kind = body[q + 1]; n, data = _vlq(body, q + 2); end = data + n
        elif s in (0xF0, 0xF7):
            n, data = _vlq(body, q + 1); end = data + n
        elif s >= 0xF1:
            raise ValueError('MIDI: an unknown status byte')
        elif s >= 0x80:
            last = s; end = q + (2 if s >> 4 in (0xC, 0xD) else 3)
        else:                                   # running status: the last channel status, kept across sysex and meta
            if last is None: raise ValueError('MIDI: running status before any status byte')
            end = q + (1 if last >> 4 in (0xC, 0xD) else 2)
        if end > len(body): raise ValueError('MIDI: an event runs past its track')
        if kind == 0x03 and not named:          # the track's name (mido's track.name is the first one too)
            named = True
            if _is_vocal(body[data:end].decode('latin-1')): return None
        if kind == 0x05:                        # lyrics: its delta goes to the next event
            carry += delta; dropped += 1
        else:
            out += body[start:q] if not carry else _put_vlq(delta + carry)
            out += body[q:end]; carry = 0
        q = end
    return bytes(out), dropped
def strip_mid(src, dst):
    b = open(src, 'rb').read()
    if len(b) < 14 or b[:4] != b'MThd': raise ValueError('MIDI: no MThd header')
    head = 8 + struct.unpack('>I', b[4:8])[0]
    ntrk = struct.unpack('>H', b[10:12])[0]
    keep = []; dropped_tracks = dropped_ev = 0; p = head
    for _ in range(ntrk):                       # as midi-file reads: at most the header's count, to the end of the data
        if p >= len(b): break
        if b[p:p + 4] != b'MTrk' or p + 8 > len(b): raise ValueError('MIDI: no MTrk header at a track')
        n = struct.unpack('>I', b[p + 4:p + 8])[0]
        r = strip_track(b[p + 8:p + 8 + n]); p += 8 + n
        if r is None: dropped_tracks += 1; continue
        keep.append(b'MTrk' + struct.pack('>I', len(r[0])) + r[0]); dropped_ev += r[1]
    h = bytearray(b[:head]); h[10:12] = struct.pack('>H', len(keep))
    open(dst, 'wb').write(bytes(h) + b''.join(keep))
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
