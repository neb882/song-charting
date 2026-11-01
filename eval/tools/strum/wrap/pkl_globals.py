"""Static scan of PyTorch .pt zip checkpoints: list every GLOBAL the pickle
would import, WITHOUT unpickling (pickletools.genops only parses opcodes)."""
import sys, zipfile, pickletools, collections

def globals_in(path):
    z = zipfile.ZipFile(path)
    pk = [n for n in z.namelist() if n.endswith('/data.pkl') or n == 'data.pkl']
    data = z.read(pk[0])
    found = collections.Counter()
    strings = []  # recent string pushes, for STACK_GLOBAL
    top_keys = []
    for op, arg, pos in pickletools.genops(data):
        if op.name in ('SHORT_BINUNICODE', 'BINUNICODE', 'UNICODE', 'BINUNICODE8'):
            strings.append(arg)
        if op.name == 'GLOBAL':
            found[arg.replace(' ', '.')] += 1
        elif op.name == 'STACK_GLOBAL' and len(strings) >= 2:
            found[strings[-2] + '.' + strings[-1]] += 1
    return found, strings

for p in sys.argv[1:]:
    g, s = globals_in(p)
    keys = [x for x in s if x in ('config', 'model_state_dict', 'epoch', 'best_f1', 'norm_mean', 'norm_std', 'optimizer_state_dict', 'metrics', 'model', 'model_type')]
    print(p.split('weights_hf/')[-1])
    print('   globals:', dict(g))
    print('   top-level-ish keys seen:', sorted(set(keys)))
