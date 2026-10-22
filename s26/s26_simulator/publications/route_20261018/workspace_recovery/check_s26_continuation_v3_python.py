import ast,json,hashlib
from pathlib import Path
root=Path(__file__).resolve().parents[1]/'S26-D1Check/s26_simulator/experiments/a24_unprotected_v3'
checked=[]
for p in sorted(root.glob('*.py')):
    tree=ast.parse(p.read_text(encoding='utf-8-sig'),filename=str(p))
    for node in ast.walk(tree):
        if isinstance(node,ast.Dict):
            assert not any(isinstance(k,ast.Name) for k in node.keys),'Unexpected bare name dictionary key in '+str(p)
    checked.append(dict(file=p.name,sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
proof=dict(status='PASS_AST_AND_NO_BARE_NAME_LITERAL_KEYS',files=checked,new_environment_instances=0,new_training=0)
with(root/'PYTHON_STATIC_CHECK.json').open('x',encoding='utf-8')as f:json.dump(proof,f)
print(json.dumps(proof))

