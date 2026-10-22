"""Synthetic public states across Python producer and independent JS auditor; no engine."""
import json
import subprocess
from pathlib import Path
from test_lsf import Nominal, Physics, q, state, owner
from lsf_policy import Policy, MODES

H = Path(__file__).resolve().parent
samples = [state([q(1)]), state([q(1, due=.001)]), state([q(1, 'D'), q(2)]),
           state([q(1)], [owner(i, stage=4) for i in range(3)]),
           state([q(1)], [owner(0, stage=0), owner(1), owner(2)]),
           state([q(1)], [owner(i) for i in range(3)] + [owner(4, 'GPU')]), state([])]
rows = []
for mode in MODES:
    for s in samples:
        n = Nominal(); actor = Policy(n, Physics(), mode); actor(s)
        vectors = {x['request_id']+'|'+r:n.vector(x,r,s) for x in s['queue']+s['owners'] for r in ('CPU','GPU')}
        rows.append(dict(s=s, call=(actor.calls or actor.wait_calls)[-1], vectors=vectors))
js = """const fs=require('fs'),{auditLSF}=require('./audit_lsf_helpers.cjs');
const p={minimum_speed:.1,strength:0,cpu_slope:0,gpu_slope:0,onset_c:26};
let checks=0;const ok=(v,m)=>{checks++;if(!v)throw Error(m)},near=(a,b,m,t)=>ok(Number.isFinite(a)&&Number.isFinite(b)&&Math.abs(a-b)<=t,m);
const rows=JSON.parse(fs.readFileSync(0,'utf8'));for(const r of rows)auditLSF(r.s,r.call,r.vectors,p,ok,near);
console.log(JSON.stringify({status:'PASS',synthetic_states:rows.length,checks,new_environment:0}));"""
proc = subprocess.run(['node', '-e', js], input=json.dumps(rows), text=True, encoding='utf-8', cwd=H, capture_output=True)
assert proc.returncode == 0, proc.stderr
with (H/'AUDIT_HELPER_TESTS.log').open('x',encoding='utf-8') as f:f.write(proc.stdout)
print(proc.stdout.strip())
