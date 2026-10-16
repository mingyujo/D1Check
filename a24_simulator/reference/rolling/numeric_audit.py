"""Registered cost-only numerical verification, zero new environments."""
from pathlib import Path
import sys,json,os,time,traceback
W=Path(__file__).parent;sys.path.insert(0,str(W/'source_generations/A24INT_G002'))
import registry,a24_cost_adapter,audit_a24
def main():
 op=registry.read(registry.O/'NUMERIC_OPERATION_REGISTERED.json')
 if registry.sha(Path(__file__))!=op['source_sha256']:raise RuntimeError('numeric operator SHA')
 if (registry.O/'NUMERIC_AUDIT.json').exists():raise RuntimeError('numeric audit already consumed; read saved result')
 if any(x.get('identity')=='A24_FIXED_MODEL_NUMERIC_G002_001' for x in registry.events(registry.O/'cost_audit_receipts.jsonl')):raise RuntimeError('numeric identity consumed; no automatic cost replay')
 lock=registry.owner_lock();guards=registry.guard('A24INT_G002')
 registry.append(registry.O/'cost_audit_receipts.jsonl',{'event':'START','identity':'A24_FIXED_MODEL_NUMERIC_G002_001','models':2,'wrapper_instances':6,
  'operation_sha256':registry.sha(registry.O/'NUMERIC_OPERATION_REGISTERED.json'),'operator_sha256':registry.sha(Path(__file__)),'generation':'A24INT_G002','guards':guards,
  'scope':'COST_ONLY','new_environment':0,'pid':os.getpid(),'unix':time.time()})
 try:
  initial=registry.read(registry.O/'INITIAL_CONTEXTS.json')['contexts'][0]
  models=a24_cost_adapter.modelsload()
  result=audit_a24.run_numeric_tests(initial,models)
  result['namespace_preflight']=models['namespace_proof']
  registry.save(registry.O/'NUMERIC_AUDIT.json',result)
  registry.append(registry.O/'cost_audit_receipts.jsonl',{'event':'COMPLETE','identity':'A24_FIXED_MODEL_NUMERIC_G002_001','sha256':registry.sha(registry.O/'NUMERIC_AUDIT.json'),'unix':time.time()})
 except BaseException as error:
  registry.append(registry.O/'cost_audit_receipts.jsonl',{'event':'FAIL','identity':'A24_FIXED_MODEL_NUMERIC_G002_001','error':str(error),'type':type(error).__name__,'traceback':traceback.format_exc(),'unix':time.time(),'new_environment':0})
  raise
 print(json.dumps({'status':result['status'],'new_environment':0,'cost_wrapper_instances':6}),flush=True)
if __name__=='__main__':main()
