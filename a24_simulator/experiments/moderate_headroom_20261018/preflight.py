from pathlib import Path
import ast,importlib.util,json,subprocess,sys
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path[:0]=[str(HERE),str(ROOT/'reference/model_integration')]
import runtime_guard as G
from pure_resources import inspect

def main():
    guard=inspect(Path(__file__).resolve());volumes=G.free_guard([ROOT,'D:/'])
    spec=importlib.util.spec_from_file_location('moderate_saved_producer',HERE/'run.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    G.require(Path(m.build.__code__.co_filename).resolve()==(ROOT/'experiments/density_headroom_20261018/bounds.py').resolve(),'Original relaxation unchanged')
    G.require(Path(m.strengthen.__code__.co_filename).resolve()==(ROOT/'experiments/density_headroom_coupling_20261018/coupling.py').resolve(),'Original necessary coupling unchanged')
    from resource_bounds import inspect as inspect_native
    native_guard=inspect_native(Path(__file__).resolve(),768*1024**2)
    asts=[];scripts=[]
    for p in HERE.glob('*.py'):
        ast.parse(p.read_text(encoding='utf-8'));asts.append(dict(path=str(p),sha256=G.sha(p)))
    for p in HERE.glob('*.cjs'):
        subprocess.run(['C:/Program Files/nodejs/node.exe','--check',str(p)],check=True);scripts.append(dict(path=str(p),sha256=G.sha(p)))
    G.write_new(HERE/'PREFLIGHT_RESULT_V2.json',dict(status='PASS',AST=asts,Node_check=scripts,original_bound_sources_unchanged=True,producer_import_pass=True,guard=guard,native_resource_guard=native_guard,volumes=volumes,new_environment_START=0,new_LP_solves=0,new_training=0))
    print('SAVED_MODERATE_PREFLIGHT_PASS',len(asts),len(scripts),flush=True)

if __name__=='__main__':main()
