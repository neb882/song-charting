"""Unpack a .sng fully: every file + song.ini rebuilt from the sng metadata block.
usage: python -I sng_unpack.py <file.sng> <outdir>"""
import struct, sys, os
import numpy as np
def unpack(path, outdir):
    b=open(path,'rb').read()
    assert b[:6]==b'SNGPKG', 'not sng'
    mask=np.frombuffer(b[10:26],dtype=np.uint8); p=26
    mlen,mcount=struct.unpack_from('<QQ',b,p); p+=16
    meta=[]
    for _ in range(mcount):
        kl=struct.unpack_from('<i',b,p)[0]; p+=4; k=b[p:p+kl].decode(); p+=kl
        vl=struct.unpack_from('<i',b,p)[0]; p+=4; v=b[p:p+vl].decode(errors='replace'); p+=vl
        meta.append((k,v))
    flen,fcount=struct.unpack_from('<QQ',b,p); p+=16
    files=[]
    for _ in range(fcount):
        nl=b[p]; p+=1; name=b[p:p+nl].decode(); p+=nl
        cl,ci=struct.unpack_from('<QQ',b,p); p+=16
        files.append((name,cl,ci))
    os.makedirs(outdir,exist_ok=True)
    for name,cl,ci in files:
        data=np.frombuffer(b[ci:ci+cl],dtype=np.uint8)
        i=np.arange(cl,dtype=np.int64)
        key=(mask[i%16]^(i&0xFF).astype(np.uint8))
        safe=os.path.basename(name)
        assert safe and safe not in ('.','..')
        open(os.path.join(outdir,safe),'wb').write((data^key).tobytes())
    with open(os.path.join(outdir,'song.ini'),'w',encoding='utf-8') as f:
        f.write('[song]\n')
        for k,v in meta:
            if k=='loading_phrase': continue   # free text; not needed
            f.write('%s = %s\n'%(k,v))
    return meta,files
if __name__=='__main__':
    meta,files=unpack(sys.argv[1],sys.argv[2])
    print('files:',', '.join('%s(%d)'%(f[0],f[1]) for f in files))
