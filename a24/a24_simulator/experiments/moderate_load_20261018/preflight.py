from pathlib import Path
import ast,importlib.util,json,subprocess,sys
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'reference/model_integration'))
import runtime_guard as G

def main():
    sys.path.insert(0,str(HERE));from pure_resources import inspect
    guard=inspect(Path(__file__).resolve());volumes=G.free_guard([ROOT,'D:/'])
    spec=importlib.util.spec_from_file_location('moderate_producer_preflight',HERE/'run_moderate.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    G.require(Path(m.execute.__code__.co_filename).resolve()==(ROOT/'experiments/coupled_345_20261017/engine.py').resolve(),'Unchanged physical engine import')
    G.require(Path(m.GuardController.__call__.__code__.co_filename).resolve()==(ROOT/'experiments/guard_ablation_20261018_v3/guard_controller.py').resolve(),'Audited guard controller')
    from resource_moderate import inspect as inspect_native
    native_guard=inspect_native(Path(__file__).resolve(),768*1024**2)
    sources=[]
    for p in HERE.glob('*.py'):
        ast.parse(p.read_text(encoding='utf-8'));sources.append(dict(path=str(p),sha256=G.sha(p)))
    scripts=[]
    for p in HERE.glob('*.cjs'):
        subprocess.run(['C:/Program Files/nodejs/node.exe','--check',str(p)],check=True);scripts.append(dict(path=str(p),sha256=G.sha(p)))
    G.write_new(HERE/'PREFLIGHT_RESULT_V2.json',dict(status='PASS',AST=sources,Node_check=scripts,producer_import_pass=True,guard=guard,native_resource_guard=native_guard,volumes=volumes,new_environment_START=0,new_training=0,frozen_bank_restores=0))
    print('MODERATE_PREFLIGHT_PASS',len(sources),len(scripts),flush=True)

if __name__=='__main__':main()
