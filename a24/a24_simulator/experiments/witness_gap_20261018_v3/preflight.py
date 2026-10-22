"""Reuse unchanged selector proof; add the actual engine receipt boundary."""
import ast,hashlib,inspect,json,time
from factors import *
def main():
    old=read(HERE.parent/'witness_gap_20261018/PREFLIGHT.json')
    assert old['status']=='PASS' and old['exact_original_selector_decisions']==2194
    previous=HERE.parent/'witness_gap_20261018/factors.py'
    assert previous.read_bytes()==(HERE/'factors.py').read_bytes(),'Same validated factor implementation'
    assert "guard.get('start_id')" in inspect.getsource(B.execute),'Original engine entry contract'
    source=(HERE/'run_factors.py').read_text(encoding='utf8');tree=ast.parse(source)
    receipts=[n for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='dict' and {'event','identity','durable_START_consumed'}<={k.arg for k in n.keywords}]
    assert len(receipts)==1 and 'start_id' in {k.arg for k in receipts[0].keywords},'Actual producer receipt meets engine entry'
    parsed=[]
    for p in HERE.glob('*.py'):ast.parse(p.read_text(encoding='utf8'));parsed.append(dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
    import run_factors
    B.G.write_new(HERE/'PREFLIGHT.json',dict(status='PASS',contracts=6,exact_original_selector_decisions=2194,reused_original_selector_proof=str(HERE.parent/'witness_gap_20261018/PREFLIGHT.json'),same_factor_source_sha256=hashlib.sha256(previous.read_bytes()).hexdigest(),actual_engine_receipt_contract=True,AST=parsed,producer_import_pass=True,new_environment_START=0,new_NN_forward=0,new_optimizer_steps=0))
    print('FACTOR_V2_PREFLIGHT_PASS',flush=True)
if __name__=='__main__':main()
