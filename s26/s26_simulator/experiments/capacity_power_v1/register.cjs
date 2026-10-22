'use strict';
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto'),HERE=__dirname,ROOT=path.resolve(HERE,'../..');
const pin=p=>({path:p,sha256:crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex')});
const prior=JSON.parse(fs.readFileSync(path.join(ROOT,'experiments/thermal_balance_v1/OPERATION.json'),'utf8'));
const op={schema:'S26_CAPACITY_POWER_OPERATION_V1',utc:new Date().toISOString(),base_commit:prior.base_commit,
 source:['DESIGN.md','power.py','run.py','replay.cjs','register.cjs'].map(f=>pin(path.join(HERE,f))).concat(['calibrate.py','rc_model.py'].map(f=>pin(path.join(ROOT,'experiments/thermal_balance_v1',f)))),
 inputs:{sessions:prior.inputs.sessions,old_OOF:prior.inputs.old_OOF,
   thermal_prepared:pin(path.join(ROOT,'experiments/thermal_balance_v1/artifacts/G001/PREPARED.json.gz')),
   two_RC_profiles:pin(path.join(ROOT,'experiments/thermal_balance_v2/artifacts/G001/PROFILES.json')),
   two_RC_OOF:pin(path.join(ROOT,'experiments/thermal_balance_v2/artifacts/G001/OOF_ROWS.json.gz'))},
 groups:prior.groups,planned_fit_START:28,fit_cap:32,wall_cap_s:900,output:path.join(HERE,'artifacts/G001'),shared_byte_mutex:prior.shared_byte_mutex,
 existing_data_only_user_instruction:true,new_policy_environments:0,new_RL:0,new_measurements:0,new_environment_reservation:0,adopted:false};
fs.writeFileSync(path.join(HERE,'OPERATION.json'),JSON.stringify(op)+'\n',{flag:'wx'});console.log(JSON.stringify({status:'REGISTERED',fits:28,new_policy_environments:0}));
