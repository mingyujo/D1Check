from pathlib import Path
import ast,io,json,subprocess,unittest
from common import B,HERE,ROOT
from resources import inspect
def main():
    guard=inspect(Path(__file__),1024**3);B.G.free_guard([ROOT,'D:/'])
    import tests
    stream=io.StringIO();r=unittest.TextTestRunner(stream=stream,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(tests.Tests))
    asts=[];scripts=[]
    for p in HERE.glob('*.py'):ast.parse(p.read_text(encoding='utf-8'));asts.append(dict(path=str(p),sha256=B.G.sha(p)))
    for p in HERE.glob('*.cjs'):subprocess.run(['C:/Program Files/nodejs/node.exe','--check',str(p)],check=True);scripts.append(dict(path=str(p),sha256=B.G.sha(p)))
    print(stream.getvalue(),flush=True);B.G.write_new(HERE/'PREFLIGHT_V2.json',dict(status='PASS' if r.wasSuccessful() else 'FAIL',tests=r.testsRun,log=stream.getvalue(),AST=asts,Node_check=scripts,guard=guard,new_environment_START=0,new_physical_fit=0));B.G.require(r.wasSuccessful(),'Preflight failed')
if __name__=='__main__':main()
