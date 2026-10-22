import ast,json
from pathlib import Path
root=Path(__file__).resolve().parents[1]/'S26-D1Check/s26_simulator/experiments/a24_unprotected_v1'
checked=[]
for p in sorted(root.glob('*.py')):
    ast.parse(p.read_text(encoding='utf-8-sig'),filename=str(p));checked.append(p.name)
proof=dict(status='PASS_PYTHON_AST_NO_IMPORT_OR_ENVIRONMENT',files=checked,new_environment_instances=0,new_training=0)
with(root/'PYTHON_AST_REV7.json').open('x',encoding='utf-8')as f:json.dump(proof,f)
print(json.dumps(proof))
