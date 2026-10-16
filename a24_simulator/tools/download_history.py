"""Explicit optional full-history download; never called by the simulator."""
from pathlib import Path
import hashlib,json,urllib.request,zipfile,argparse
P=Path(__file__).resolve().parents[1]
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--restore',action='store_true');a=ap.parse_args()
    spec=json.loads((P/'data/HISTORY_ARCHIVE.json').read_text(encoding='utf-8'))
    if not spec.get('download_url'):raise RuntimeError('Publication URL missing')
    target=P/'history'/spec['name'];target.parent.mkdir(exist_ok=True)
    if not target.exists():
        tmp=target.with_suffix('.download')
        if tmp.exists():raise RuntimeError('Partial download exists; inspect before a new attempt')
        with urllib.request.urlopen(spec['download_url']) as r,tmp.open('xb') as f:
            while b:=r.read(2**20):f.write(b)
        tmp.rename(target)
    h=hashlib.sha256()
    with target.open('rb') as f:
        for b in iter(lambda:f.read(2**20),b''):h.update(b)
    if h.hexdigest()!=spec['sha256'] or target.stat().st_size!=spec['bytes']:raise RuntimeError('Archive SHA/size mismatch')
    if a.restore:
        with zipfile.ZipFile(target) as z:
            rows=json.loads(z.read('MANIFEST.json'));root=P/'history/restored'
            for row in rows:
                rel=Path(row['path'])
                if rel.is_absolute() or '..' in rel.parts:raise RuntimeError('Unsafe historical path')
                data=z.read('objects/'+row['sha256'])
                if hashlib.sha256(data).hexdigest()!=row['sha256']:raise RuntimeError('Historical object mismatch')
                out=root/rel;out.parent.mkdir(parents=True,exist_ok=True)
                if out.exists() and out.read_bytes()!=data:raise RuntimeError('Refuse conflicting restored file')
                if not out.exists():out.write_bytes(data)
    print('PASS exact history SHA; restored' if a.restore else 'PASS exact history SHA')
if __name__=='__main__':main()
