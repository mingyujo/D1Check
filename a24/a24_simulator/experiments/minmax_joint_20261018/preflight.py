from pathlib import Path
import ast,importlib.util,io,subprocess,sys,unittest
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'deep_repair_20261018'))
from common import B,ROOT
from resources import inspect

def main():
    guard=inspect(Path(__file__),1024**3);B.G.free_guard([ROOT,'D:/'])
    assert B.G.sha(HERE/'THERMAL_PURE_TEST.json')==B.G.sha(HERE.parent/'deep_repair_20261018'/'THERMAL_PURE_TEST.json'),'Frozen thermal proof alias'
    spec=importlib.util.spec_from_file_location('minmax_joint_tests',HERE/'tests.py');tests=importlib.util.module_from_spec(spec);spec.loader.exec_module(tests)
    stream=io.StringIO();r=unittest.TextTestRunner(stream=stream,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(tests.Tests))
    # Load the actual producer without starting it, catching import-path failures.
    spec=importlib.util.spec_from_file_location('queue_context_producer',HERE/'run.py');producer=importlib.util.module_from_spec(spec);spec.loader.exec_module(producer)
    assert producer.HERE==HERE and producer.PublicController.__module__=='queue_controller'
    warm=producer.loadpt(ROOT/'results/QUEUE_CONTEXT_20261018_01/CONTEXT_BC_ONLY.FINAL_WARM.pt.gz')
    initial=producer.Learner(warm,anchor=True)
    producer.equal(initial.snapshot(),producer.loadpt(ROOT/'results/QUEUE_CONTEXT_20261018_01/CONTEXT_BC_PPO_OFF_TRAIN_001.BEFORE.pt.gz'))
    asts=[];scripts=[]
    for p in HERE.glob('*.py'):ast.parse(p.read_text(encoding='utf-8'));asts.append(dict(path=str(p),sha256=B.G.sha(p)))
    for p in HERE.glob('*.cjs'):subprocess.run(['C:/Program Files/nodejs/node.exe','--check',str(p)],check=True);scripts.append(dict(path=str(p),sha256=B.G.sha(p)))
    print(stream.getvalue(),flush=True);B.G.write_new(HERE/'PREFLIGHT.json',dict(status='PASS' if r.wasSuccessful() else 'FAIL',tests=r.testsRun,log=stream.getvalue(),AST=asts,Node_check=scripts,guard=guard,actual_producer_import='PASS',paired_initial_actor_critic_Adam_RNG_exact=True,new_environment_START=0,new_physical_fit=0));B.G.require(r.wasSuccessful(),'Joint objective preflight failed')
if __name__=='__main__':main()
