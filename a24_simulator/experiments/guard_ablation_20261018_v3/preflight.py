"""One Python after the active producer exits; snapshots only, no episode."""
from pathlib import Path
import ast,hashlib,io,json,subprocess,sys,time,unittest
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'reference/model_integration'))
import runtime_guard as G
G.OWN_TOKENS+=('guard_ablation_20261018_v3','density_headroom_20261018','density_headroom_coupling_20261018')


def main():
    # Fail BEFORE claiming the snapshot slot or writing its result if another
    # Python producer remains active. Never overlap the original native run.
    sys.path.insert(0,str(HERE));from pure_resources import inspect
    guard=inspect(Path(__file__).resolve());volumes=G.free_guard([ROOT,'D:/'])
    sources=[]
    for p in HERE.glob('*.py'):
        ast.parse(p.read_text(encoding='utf-8'),filename=str(p));sources.append(dict(path=str(p),sha256=G.sha(p)))
    scripts=[]
    for p in HERE.glob('*.cjs'):
        subprocess.run(['C:/Program Files/nodejs/node.exe','--check',str(p)],check=True)
        scripts.append(dict(path=str(p),sha256=G.sha(p)))
    import importlib.util
    spec=importlib.util.spec_from_file_location('ablation_producer_preflight',HERE/'run.py')
    producer=importlib.util.module_from_spec(spec);spec.loader.exec_module(producer)
    G.require(Path(producer.labels.__code__.co_filename).resolve()==(ROOT/'experiments/coupled_345_20261017/rewards.py').resolve(),'Explicit coupled reward import')
    from parallel_resources import inspect as inspect_native
    native_guard=inspect_native(Path(__file__).resolve(),768*1024**2)
    G.require(native_guard['global_limit']==3 and native_guard['own_A24_limit']==1,'Authorized independent native resource contract')
    import test_contracts
    stream=io.StringIO();result=unittest.TextTestRunner(stream=stream,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(test_contracts.Tests))
    payload=dict(status='PASS' if result.wasSuccessful() else 'FAIL',utc=G.now(),tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),log=stream.getvalue(),
                 AST=sources,Node_check=scripts,guard=guard,native_resource_guard=native_guard,volumes=volumes,new_environment_START=0,new_LP_solves=0,new_training=0,new_physical_fit=0)
    G.write_new(HERE/'PREFLIGHT_RESULT.json',payload);print(json.dumps(payload,ensure_ascii=False),flush=True)
    G.require(result.wasSuccessful(),'Preserve failed snapshot tests; do not start native operation')


if __name__=='__main__':main()
