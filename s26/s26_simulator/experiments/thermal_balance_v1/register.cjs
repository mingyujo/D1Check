'use strict';
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const HERE=__dirname,ROOT=path.resolve(HERE,'../..'),WORKSPACE=path.resolve(ROOT,'../..');
const pin=p=>({path:p,bytes:fs.statSync(p).size,sha256:crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex')});
const old=path.join(ROOT,'experiments/multiresource_v1/calibration'),rows=JSON.parse(fs.readFileSync(path.join(old,'results/OOF_ROWS.json'),'utf8'));
const power=new Set(rows.filter(r=>r.target==='POWER_API').map(r=>r.id));
const groups=[...new Set(rows.filter(r=>r.target==='AP'&&power.has(r.id)).map(r=>r.group))].sort();
const grid=[5,10,20,40,80,160,320],planned=(groups.length+1)*grid.length;
if(planned>224)throw Error('Fit cap');
const op={schema:'S26_THERMAL_BALANCE_OPERATION_V1',utc:new Date().toISOString(),base_commit:'b0b1c7df1775fcae3ba2944ed5df6d800382b4cc',
  source:Object.fromEntries(['rc_model.py','calibrate.py','thermal_rc.cjs','test_rc.cjs','audit.py','run.py','DESIGN.md','register.cjs'].map(f=>[f,pin(path.join(HERE,f))])),
  inputs:{sessions:pin(path.join(old,'MATERIALIZED_SESSIONS.json.gz')),old_OOF:pin(path.join(old,'results/OOF_ROWS.json')),old_usage:pin(path.join(old,'results/USE_LEDGER.json')),
    diagnosis:pin(path.join(ROOT,'experiments/sustained_load_v1/artifacts/G001/AP_TERM_DIAGNOSIS.json')),
    sustained_summary:pin(path.join(ROOT,'experiments/sustained_load_v1/artifacts/G001/SUMMARY.json'))},
  groups,tau_grid_s:grid,planned_fit_START:planned,fit_cap:224,wall_cap_s:900,
  output:path.join(HERE,'artifacts/G001'),shared_byte_mutex:path.join(WORKSPACE,'D1Check/a24_simulator/runtime/worker.lock'),
  new_policy_environments:0,new_RL:0,new_measurements:0,new_environment_reservation:0,
  deployment_gate:'Measured-power replay only; no adoption without sustained power/service and device thermal-mitigation evidence',
  fit_role:'All-seen development, group OOF; no independent phone validation',failed_fit_retry:false};
const out=path.join(HERE,'OPERATION.json');fs.writeFileSync(out,JSON.stringify(op)+'\n',{flag:'wx'});
console.log(JSON.stringify({status:'REGISTERED',groups:groups.length,planned_fit_START:planned,cap:224,new_policy_environments:0,operation:pin(out)}));
