from pathlib import Path
import ast,importlib.util,io,json,subprocess,sys,unittest
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'reference/model_integration'))
import runtime_guard as G

def main():
    sys.path.insert(0,str(HERE));from pure_resources import inspect
    guard=inspect(Path(__file__).resolve());volumes=G.free_guard([ROOT,'D:/'])
    sys.path.insert(0,str(HERE));spec=importlib.util.spec_from_file_location('learning_producer_preflight',HERE/'run_learning.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    G.require(Path(m.execute.__code__.co_filename).resolve()==(ROOT/'experiments/coupled_345_20261017/engine.py').resolve(),'Physical engine unchanged')
    test_spec=importlib.util.spec_from_file_location('learning_snapshot_tests',HERE/'test_contracts.py')
    test_contracts=importlib.util.module_from_spec(test_spec);test_spec.loader.exec_module(test_contracts)
    stream=io.StringIO();r=unittest.TextTestRunner(stream=stream,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(test_contracts.Tests))
    from resource_learning import inspect as inspect_native
    native_guard=inspect_native(Path(__file__).resolve(),768*1024**2)
    asts=[];scripts=[]
    for p in HERE.glob('*.py'):
        ast.parse(p.read_text(encoding='utf-8'));asts.append(dict(path=str(p),sha256=G.sha(p)))
    for p in HERE.glob('*.cjs'):
        subprocess.run(['C:/Program Files/nodejs/node.exe','--check',str(p)],check=True);scripts.append(dict(path=str(p),sha256=G.sha(p)))
    G.write_new(HERE/'PREFLIGHT_RESULT_V3.json',dict(status='PASS' if r.wasSuccessful() else 'FAIL',tests=r.testsRun,failures=len(r.failures),errors=len(r.errors),log=stream.getvalue(),AST=asts,Node_check=scripts,guard=guard,native_resource_guard=native_guard,volumes=volumes,producer_import_pass=True,new_environment_START=0,new_training=0,frozen_bank_restores=0))
    print(stream.getvalue(),flush=True);G.require(r.wasSuccessful(),'Preserve test failure; no native start')

if __name__=='__main__':main()
