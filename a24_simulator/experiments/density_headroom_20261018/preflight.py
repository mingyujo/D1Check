"""Guarded AST check only; no timing bank restore or native environment."""
from pathlib import Path
import ast,sys
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'reference/model_integration'))
import runtime_guard as G
if __name__=='__main__':
    G.OWN_TOKENS+=('density_headroom_20261018','load_density_20261017','coupled_345_20261017')
    guard=G.process_guard(Path(__file__).resolve());vol=G.free_guard([ROOT,'D:/'])
    import msvcrt
    lock=(ROOT/'runtime/worker.lock').open('r+b');lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
    try:
        files=list(HERE.glob('*.py'))
        for p in files:ast.parse(p.read_text(encoding='utf-8'),filename=str(p))
        target=HERE/('AST_RESULT_V2.json' if (HERE/'AST_RESULT.json').exists() else 'AST_RESULT.json')
        G.write_new(target,dict(status='PASS',files=[dict(path=p.name,sha256=G.sha(p)) for p in files],guard=guard,volumes=vol,new_environment_START=0))
        print('AST_PASS',len(files),'new_environment0',flush=True)
    finally:
        lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1);lock.close()
