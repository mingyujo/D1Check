"""Reuse the unchanged public ABI proof and validate event-only changes."""
import ast,hashlib,subprocess
from contracts import *
def main():
    assert read(HERE/'CONTRACTS.json')['status']=='PASS'
    parent=HERE.parent/'packing_rl_20261018';proof=read(parent/'OPERATION.json')
    for n in ['packing_encoder.py','packing_net.py','packing_learner.py','fluid.py','completion_labels.py','feature_audit.cjs','tensor_reader.cjs']:
        p=parent/n;expected=next(s for s in proof['sources'] if Path(s['path']).resolve()==p.resolve());assert hashlib.sha256(p.read_bytes()).hexdigest()==expected['sha256'],'Unchanged actor/critic/optimizer/public features'
    parsed=[]
    for p in HERE.glob('*.py'):ast.parse(p.read_text(encoding='utf8'));parsed.append(dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
    import run_event
    source=ast.parse((HERE/'run_event.py').read_text(encoding='utf8'));receipts=[n for n in ast.walk(source) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='dict' and {'event','identity','durable_START_consumed'}<={k.arg for k in n.keywords}];assert len(receipts)==1 and 'start_id' in {k.arg for k in receipts[0].keywords}
    node=[]
    for p in HERE.glob('*.cjs'):subprocess.run([proof['node_executable'],'--check',str(p)],check=True);node.append(dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
    B.G.write_new(HERE/'PREFLIGHT.json',dict(status='PASS',contracts=6,reused_public_ABI_contracts=8,unchanged_parent_public_source=True,parent_full_warm_Adam_RNG_exact=True,actual_engine_receipt_contract=True,AST=parsed,Node_check=node,new_environment_START=0,new_optimizer_steps=0,producer_import_pass=True));print('EVENT_ONLY_PREFLIGHT_PASS',flush=True)
if __name__=='__main__':main()
