"""Find an original source by name and export its byte-verified copy."""
from pathlib import Path
import argparse,json,sys,shutil
P=Path(__file__).resolve().parents[1];sys.path.insert(0,str(P/'reference/model_integration'))
from runtime_guard import pin
def main():
    ap=argparse.ArgumentParser();ap.add_argument('name');ap.add_argument('--sha');ap.add_argument('--export');a=ap.parse_args()
    rows=json.loads((P/'data/CORE_MANIFEST.json').read_text(encoding='utf-8'))
    rows=[r for r in rows if a.name.lower() in r['name'].lower() and (not a.sha or r['sha256'].startswith(a.sha))]
    if not a.export:
        for r in rows:print(r['name'],r['bytes'],r['sha256'],r['original_path'])
    else:
        hashes={r['sha256'] for r in rows}
        if len(hashes)!=1:raise RuntimeError('Select exactly one content SHA with --sha')
        r=rows[0];target=Path(a.export)
        if target.exists():raise RuntimeError('Export target exists; no overwrite')
        source=pin({'path':r['original_path'],'sha256':r['sha256'],'bytes':r['bytes']})
        target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target);print('Exported exact bytes',r['sha256'])
if __name__=='__main__':main()
