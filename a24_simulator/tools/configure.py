"""Create a local execution registration from frozen package pins."""
from pathlib import Path
import json,os
P=Path(__file__).resolve().parents[1]
def main():
    r=json.loads((P/'models/registration.json').read_text(encoding='utf-8'))
    # Only package-owned source/checkpoint paths move. Historical input paths
    # are provenance IDs and resolve through the verified PATH_MAP.
    prefix=r.get('package_root_at_publication',str(P))
    def relocate(x):
        if isinstance(x,dict):return {k:relocate(v) for k,v in x.items()}
        if isinstance(x,list):return [relocate(v) for v in x]
        if isinstance(x,str) and x.replace('\\','/').startswith(prefix.replace('\\','/')+'/'):
            return str(P/x.replace('\\','/')[len(prefix.replace('\\','/'))+1:])
        return x
    r=relocate(r);r['output_dir']=str(P/'runtime');r['cache_roots']=[]
    (P/'runtime').mkdir(exist_ok=True)
    original=Path(r['worker_lock_path'])
    if not original.exists():
        original=P/'runtime/worker.lock'
        if not original.exists():original.write_bytes(b'0')
    r['worker_lock_path']=str(original)
    r['known_PS_producer_paths']=[]
    target=P/'runtime/registration.json'
    text=json.dumps(r,ensure_ascii=False,indent=2)+'\n'
    if target.exists() and target.read_text(encoding='utf-8')!=text:
        raise RuntimeError('Local registration differs; preserve previous runs and use a fresh copied folder')
    if not target.exists():target.write_text(text,encoding='utf-8')
    print('Local registration ready; no simulation started')
if __name__=='__main__':main()
