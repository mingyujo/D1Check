'use strict';
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto'),HERE=__dirname,ROOT=path.resolve(HERE,'../..'),P=path.join(HERE,'../thermal_balance_v1');
const pin=p=>({path:p,sha256:crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex')});
const prior=JSON.parse(fs.readFileSync(path.join(P,'OPERATION.json'),'utf8'));
const op={schema:'S26_TWO_MODE_THERMAL_V1',utc:new Date().toISOString(),base_commit:prior.base_commit,
 source:['run.py','replay.cjs','DESIGN.md','register.cjs'].map(f=>pin(path.join(HERE,f))).concat(['calibrate.py','rc_model.py','thermal_rc.cjs'].map(f=>pin(path.join(P,f)))),
 inputs:{prepared:pin(path.join(P,'artifacts/G001/PREPARED.json.gz')),single_OOF:pin(path.join(P,'artifacts/G001/OOF_ROWS.json.gz')),single_proof:pin(path.join(P,'artifacts/G001/FINAL_HANDOFF_PROOF.json'))},
 groups:prior.groups,tau_grid_s:prior.tau_grid_s,planned_fit_START:1176,fit_cap:1200,wall_cap_s:900,
 shared_byte_mutex:prior.shared_byte_mutex,output:path.join(HERE,'artifacts/G001'),new_policy_environments:0,new_RL:0,new_measurements:0,new_environment_reservation:0,adopted:false,all_seen_development:true};
fs.writeFileSync(path.join(HERE,'OPERATION.json'),JSON.stringify(op)+'\n',{flag:'wx'});console.log(JSON.stringify({status:'REGISTERED',fits:1176,new_policy_environments:0}));
