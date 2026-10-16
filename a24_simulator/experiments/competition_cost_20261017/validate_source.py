"""One registered pure-test/compile operation; no raw dataset/model initialization."""
from pathlib import Path
import ast,hashlib,importlib,json,os,sys,unittest
ROOT=Path(__file__).resolve().parents[2];ENTRY=Path(__file__).resolve()
sys.path.insert(0,str(ROOT/'reference/model_integration'))
import runtime_guard as G
G.OWN_TOKENS+=('competition_cost_20261017','s26-state-aware-atc-','state_recovery_owner')
def run(path):
    op=G.read(path);G.require(op['schema']=='A24-competition-cost-pure-tests-v1','Schema')
    for s in op['source_pins']:G.pin(s)
    reg=G.read(ROOT/'models/registration.json')
    G.process_guard(ENTRY,reg['known_PS_producer_paths']);G.free_guard([ROOT,'D:/'])
    out=ROOT/op['output_dir'];G.require(not out.exists(),'Already consumed test operation')
    out.mkdir(parents=True,exist_ok=False)
    G.write_new(out/'START.json',dict(operation_sha256=G.sha(path),utc=G.now()))
    try:
        parsed=[]
        for s in op['source_pins']:
            if s['path'].endswith('.py'):
                ast.parse(Path(s['path']).read_text(encoding='utf-8'),filename=s['path']);parsed.append(s['sha256'])
        import test_state_cost,state_cost,relative_drain
        suite=unittest.defaultTestLoader.loadTestsFromModule(test_state_cost)
        result=unittest.TextTestRunner(verbosity=2).run(suite)
        G.require(result.wasSuccessful(),'Pure fixture failure')
        for s in op['source_pins']:G.pin(s)
        G.write_new(out/'RESULT.json',dict(status='PURE_TESTS_AND_AST_PASS',tests=result.testsRun,
                     Python_AST_files=len(parsed),source_pins=op['source_pins'],new_environment=0,
                     model_spec=state_cost.SPEC,relative_model_spec=relative_drain.SPEC,utc=G.now()))
        G.write_new(out/'COMPLETE.json',dict(result_sha256=G.sha(out/'RESULT.json'),utc=G.now()))
    except BaseException as e:
        G.write_new(out/'FAILURE.json',dict(error=str(e),automatic_retry=False,utc=G.now()));raise
if __name__=='__main__':run(sys.argv[1])
