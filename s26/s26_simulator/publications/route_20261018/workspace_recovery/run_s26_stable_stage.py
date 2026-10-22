"""Resource binding and syntax validation; unchanged scientific target execution."""
import ast,datetime,hashlib,json,runpy,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;target=Path(sys.argv[1]).resolve();sys.path.insert(0,str(HERE));sys.path.insert(0,str(target.parent))
import s26_resources,s26_resources_v2
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
for p in(target,target.parent/'nn_train.py',target.parent/'audit_nn.py'):ast.parse(p.read_text(encoding='utf-8-sig'))
op=json.loads((target.parent/'OPERATION.json').read_text(encoding='utf-8-sig'))
for p in op['pins']:assert sha(p['path'])==p['sha256'],'Prelaunch source/input pin '+p['path']
record=dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),target=str(target),target_sha256=sha(target),operation_sha256=sha(target.parent/'OPERATION.json'),binding='Only imported wait_ready bound to registered-peer resource manager; target scientific body unchanged',new_environment=0,pins=[dict(path=str(p),sha256=sha(p))for p in(Path(__file__),HERE/'s26_resources_v2.py',target)])
with(target.parent/'RESOURCE_MANAGER_V2.json').open('x',encoding='utf-8')as f:json.dump(record,f,indent=2)
s26_resources.wait_ready=s26_resources_v2.wait_ready
runpy.run_path(str(target),run_name='__main__')
