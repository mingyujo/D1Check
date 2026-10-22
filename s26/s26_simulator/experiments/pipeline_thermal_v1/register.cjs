'use strict';
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto'),HERE=__dirname,ROOT=path.resolve(HERE,'../..');
const pin=p=>({path:p,sha256:crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex')});
const p=path.join(ROOT,'experiments/capacity_power_v1'),prior=JSON.parse(fs.readFileSync(path.join(p,'OPERATION.json'),'utf8'));
const profiles=JSON.parse(fs.readFileSync(prior.inputs.two_RC_profiles.path,'utf8'));
const pairs=Object.fromEntries(profiles.map(r=>{const m=r.fits.find(m=>m.id===r.selected);return [r.group??'FULL',[m.tau_fast_s,m.tau_slow_s]];}));
const inputs={sessions:prior.inputs.sessions,prepared:prior.inputs.thermal_prepared,previous_conditional:pin(path.join(p,'artifacts/G001/CONDITIONAL_AP_ROWS.json.gz')),oracle:prior.inputs.two_RC_OOF,prior_profiles:prior.inputs.two_RC_profiles};
const op={schema:'S26_PREDICTED_POWER_THERMAL_PIPELINE_V1',utc:new Date().toISOString(),source:['DESIGN.md','basis.py','run.py','register.cjs'].map(f=>pin(path.join(HERE,f))).concat([path.join(p,'power.py'),path.join(ROOT,'experiments/thermal_balance_v2/run.py'),path.join(ROOT,'experiments/thermal_balance_v1/calibrate.py'),path.join(ROOT,'experiments/thermal_balance_v1/rc_model.py')].map(pin)),
 inputs,power_models:Object.fromEntries([...prior.groups,'FULL'].map(g=>[g,pin(path.join(p,'artifacts/G001/models',g+'.json'))])),groups:prior.groups,pairs,
 basis_taus:[...new Set(Object.values(pairs).flat())].sort((a,b)=>a-b),planned_fit_START:56,fit_cap:64,wall_cap_s:900,output:path.join(HERE,'artifacts/G001'),shared_byte_mutex:prior.shared_byte_mutex,
 existing_data_only:true,new_policy_environments:0,new_RL:0,new_measurements:0,new_environment_reservation:0,adopted:false};
fs.writeFileSync(path.join(HERE,'OPERATION.json'),JSON.stringify(op)+'\n',{flag:'wx'});console.log(JSON.stringify({status:'REGISTERED',fits:56,basis_taus:op.basis_taus}));
