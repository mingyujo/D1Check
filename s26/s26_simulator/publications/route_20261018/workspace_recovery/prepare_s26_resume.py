"""Seal explicit checkpoint-manager continuation; environment budget unchanged."""
import ast,datetime,difflib,hashlib,importlib.util,json,sys
from pathlib import Path
W=Path(__file__).resolve().parent.parent;target=Path(sys.argv[1]).resolve();H=target.parent;O=H/'artifacts/G001'
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
driver=W/'recovery/resume_s26_repair.py';spec=importlib.util.spec_from_file_location('registered_resume_driver',driver);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
source=target.read_text(encoding='utf-8-sig');changed=m.transformed(source);a=ast.parse(source);b=ast.parse(changed)
def inner(tree,name):return next(n for n in ast.walk(tree)if isinstance(n,ast.FunctionDef)and n.name==name)
assert ast.dump(inner(a,'simulate'),include_attributes=False)==ast.dump(inner(b,'simulate'),include_attributes=False),'Environment/learning body must remain exactly identical'
boundary=read(O/'CHECKPOINT_BOUNDARY_STOP_V2.json');receipts=[json.loads(x)for x in(O/'receipts.jsonl').read_text(encoding='utf-8').splitlines()if x];starts=[x for x in receipts if x['event']=='START'];complete=[x for x in receipts if x['event']=='COMPLETE'];assert len(starts)==len(complete)==boundary['START']and not any(x['event']=='FAIL'for x in receipts)
assert not(O/'RESULT.json').exists();original=read(H/'OPERATION.json');began=datetime.datetime.fromisoformat(read(O/'START.json')['utc']);now=datetime.datetime.now(datetime.timezone.utc);remaining=max(1,int(original['wall_cap_s']-(now-began).total_seconds()));pins=[dict(path=str(p),sha256=sha(p))for p in[driver,Path(__file__),W/'recovery/s26_resources_v2.py',target,H/'OPERATION.json',O/'CHECKPOINT_BOUNDARY_STOP_V2.json']]
for p in O.glob('*_CASE_ORDER.json'):pins.append(dict(path=str(p),sha256=sha(p)))
record=dict(schema='S26_MANAGER_ONLY_CHECKPOINT_RESUME_V2',utc=now.isoformat(),original_run_path=str(target),original_run_sha256=sha(target),original_operation_sha256=sha(H/'OPERATION.json'),transformed_source_sha256=hashlib.sha256(changed.encode()).hexdigest(),unchanged_simulate_AST_sha256=hashlib.sha256(ast.dump(inner(a,'simulate'),include_attributes=False).encode()).hexdigest(),prior_START=len(starts),prior_COMPLETE=len(complete),prior_FAIL=0,unstarted=512-len(starts),combined_planned_START=512,new_reservation=0,remaining_wall_cap_s=remaining,reason='Current A24 successor is separately registered as run_learning_v2.py. Verify peer sources against their actual operation pins instead of hardcoded run.py filenames. Preserve original target file/hash and checkpoint/RNG/Adam, acknowledge only byte/state-identical saved checkpoints and skip completed environment identities.',policy_physics_learner_inputs_unchanged=True,pins=pins)
with(H/'OPERATION_RESOURCE_RESUME_V2.json').open('x',encoding='utf-8')as f:json.dump(record,f,ensure_ascii=False,indent=2)
with(H/'prestart_history/RESOURCE_RESUME_V2.patch').open('x',encoding='utf-8')as f:f.write(''.join(difflib.unified_diff(source.splitlines(True),changed.splitlines(True),fromfile='original_sealed_run.py',tofile='registered_manager_resume_v2')))
from s26_resources_v2 import inspect
probe=inspect();print(json.dumps(dict(status='CHECKPOINT_MANAGER_SEALED_UNCHANGED_SIMULATE_AST',prior_START=len(starts),unstarted=record['unstarted'],remaining_wall_cap_s=remaining,peer_resource_probe=probe)),flush=True)
