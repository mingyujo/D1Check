'use strict';
const fs=require('fs'),path=require('path'),crypto=require('crypto');
const root=path.resolve(__dirname,'../..');
const read=p=>JSON.parse(fs.readFileSync(p,'utf8'));
const pin=p=>({path:path.relative(root,p).replaceAll('\\','/'),sha256:crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex'),bytes:fs.statSync(p).size});
const save=(p,q)=>fs.writeFileSync(p,JSON.stringify(q,null,2)+'\n',{flag:'wx'});
const base=pin(path.join(root,'results/STATE_COST_IDENTIFICATION_20261017_01/MODEL.json'));
save(path.join(__dirname,'COST_BUNDLE.json'),{schema:'A24-shared-activation-bundle-v1',steady_model:base,
 shared_scale:1,idle_decay_s:.9,role:'research hypothesis; not calibrated device energy',
 scale_grid:[0,.5,1,1.5],idle_decay_grid_s:[0,.225,.9,3.6],
 parameter_selection_by_policy_gap:false,old_default_changed:false,
 source_rationale:[{url:'https://source.android.com/docs/core/power/values',claim:'Android distinguishes awake, idle and active component power; numerical examples are not A24 parameters'},
 {url:'https://www.kernel.org/doc/html/latest/admin-guide/pm/cpufreq.html',claim:'CPU frequency responds to utilization and governor state; this does not identify A24 idle decay or a CPU/GPU shared rail'}],
 current_user_authority:'2026-10-17: all parts may be modified with a logical rationale; hypotheses remain explicit',
 measured_J:null,new_physical_fit:0,new_environment_START:0,NN_updates:0});
const oldInputs=read(path.join(root,'experiments/rl_cost_20261017/INPUTS.json')).fresh_eval;
const newInputs=read(path.join(root,'experiments/choice_opportunities_20261017/INPUTS_V2.json')).cases;
const schedules=[];
for(const [i,c] of oldInputs.entries())for(const policy of ['EDF_CPU_FIRST','FIFO_CPU_FIRST','ROLLING_ATC','ROLLING_ATC_RL_COST','RR_CPU_FIRST']){
 const id='FRESH_'+String(i).padStart(2,'0')+'_'+policy,dir=path.join(root,'results/RL_COST_20261017_01');
 schedules.push({collection:'FRESH12',case:'FRESH_'+String(i).padStart(2,'0'),policy,id,
  window:c.work_window,n:c.n,summary:pin(path.join(dir,id+'.json')),raw:pin(path.join(dir,id+'.raw.json.gz'))});
}
for(const c of newInputs)for(const policy of ['EDF','COST_PRIOR','COALESCED_COST']){
 const id=c.id+'_'+policy,dir=path.join(root,'results/CHOICE_OPPORTUNITIES_V2_20261017_01');
 schedules.push({collection:'CHOICE_V2',case:c.id,policy,id,window:c.work_window,n:c.n,
  summary:pin(path.join(dir,id+'.json')),raw:pin(path.join(dir,id+'.raw.json.gz'))});
}
if(schedules.length!==72)throw Error('Unexpected finite scope');
save(path.join(__dirname,'OPERATION.json'),{schema:'A24-shared-activation-saved-operation-v1',created_utc:new Date().toISOString(),
 output_dir:'results/SHARED_ACTIVATION_20261017_01',
 source_pins:['shared_cost.py','cost_adapter.py','test_shared_cost.py','prepare.cjs','run_saved.py','audit_saved.py'].map(p=>pin(path.join(__dirname,p))),
 input_pins:[base,...['MODEL.json','NATIVE_RELATIVE_MODEL.json','VALIDATION.json'].map(p=>pin(path.join(root,'results/STATE_COST_IDENTIFICATION_20261017_01',p))),
 ...['state_cost.py','relative_drain.py','fit_cost.py'].map(p=>pin(path.join(root,'experiments/competition_cost_20261017',p))),
 pin(path.join(root,'reference/model_integration/runtime_guard.py')),
 pin(path.join(root,'experiments/rl_cost_20261017/INPUTS.json')),
 pin(path.join(root,'experiments/choice_opportunities_20261017/INPUTS_V2.json')),
 pin(path.join(__dirname,'COST_BUNDLE.json'))],schedules,
 comparison:'all saved schedules, all 16 scenario settings, no outcome-based model selection',
 nominal_parameters:{shared_scale:1,idle_decay_s:.9},scenarios:[0,.5,1,1.5].flatMap(shared_scale=>[0,.225,.9,3.6].map(idle_decay_s=>({shared_scale,idle_decay_s}))),
 analysis_operation_cap:1,automatic_retry:false,new_environment_START:0,new_fit:0,NN_updates:0,new_device_measurements:0,
 budget:'No new reservation or transfer: original RL256 = 223 old + 25 choice starts + 8 unused; RR unused1 separate',
 interpretation:'logical scheduling model; validation of algebra/software is separate from physical A24 validation',
 independent_confirmation:false});
console.log('Registered saved-only72 x16 scenarios; no environment, fit, or learning.');
