'use strict';
const fs=require('fs'),path=require('path'),crypto=require('crypto'),cp=require('child_process');
const root=path.resolve(__dirname,'../..'),repo=path.dirname(root),read=p=>JSON.parse(fs.readFileSync(p));
const pin=p=>({path:p,sha256:crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex'),bytes:fs.statSync(p).size}),save=(p,v)=>fs.writeFileSync(p,JSON.stringify(v,null,2)+'\n',{flag:'wx'});
const d=require('./design.cjs').design();let checks=0;const need=(v,s)=>{checks++;if(!v)throw Error(s);};
for(const c of d.cases){
 const ref=d.cases.find(r=>r.condition.pattern===c.condition.pattern&&r.condition.rate_multiplier===1),f=c.condition.rate_multiplier;
 need(c.n<=3072&&c.n>48,'Request cap');need(c.supply_stop_s===155&&c.service_stop_s===755&&c.drain_stop_s===785,'Common windows');
 need(Math.abs(c.n/f-ref.n)<48,'Rate/count rounding within one48requestcycle');
 for(const [i,q] of c.input.requests.entries()){
  const proto=ref.input.requests[i%48],unscaled=proto.arrival_s-35+Math.floor(i/48)*c.base_cycle_s;
  need(q.ordinal===i&&q.arrival_s>=35&&q.arrival_s<155,'Fixed120s supply');
  need(Math.abs((q.arrival_s-35)*f-unscaled)<=1e-7,'Only arrival intervals compressed');
  need(Math.abs((q.deadline_s-q.arrival_s)-(proto.deadline_s-proto.arrival_s))<=1e-7,'Relative deadline unchanged');
  need(q.profile===proto.profile&&q.priority===proto.priority,'Same task and priority sequence');
 }
}
const thermal=read(path.join(__dirname,'THERMAL_PURE_TEST.json'));need(thermal.status==='PASS'&&thermal.refined_invariant_upper_c<60,'Bounded stable model');
save(path.join(__dirname,'PURE_TEST_RESULT.json'),{status:'PASS',checks,new_environment_START:0});save(path.join(__dirname,'INPUTS.json'),d);
const external='C:/Users/user/Documents/ChatGPT/산공회마무리/S26-D1Check/s26_simulator/experiments/sustained_load_v1/BUDGET_RESERVATION.json',ext=read(external);
need(ext.previous_global_reserved===125790&&ext.global_reserved===125838,'Known parallel S26 reservation accounting');
fs.copyFileSync(external,path.join(__dirname,'EXTERNAL_S26_BUDGET_SNAPSHOT.json'),fs.constants.COPYFILE_EXCL);
const budget={utc:new Date().toISOString(),previous:pin(path.join(root,'experiments/sustained_load_20261017/BUDGET_RESERVATION.json')),
 known_parallel_S26:pin(path.join(__dirname,'EXTERNAL_S26_BUDGET_SNAPSHOT.json')),previous_global_reserved:ext.global_reserved,new_reservation:36,
 global_reserved:ext.global_reserved+36,global_cap:ext.global_cap,cap:36,planned_START:32,allocation:{P0:2,density:30},
 old_coupled38_savings8_sustained4_RR1_untouched:true,new_training:0,new_physical_fit:0,frozen_bank_restores:1,automatic_retry:false,
 global_accounting:'Tracked snapshot including known parallel S26+48, not a fresh all-host census',user_authority:'Increase work amount per fixed time and analyze load sensitivity; verify no unbounded thermal rise'};
need(budget.global_reserved<=budget.global_cap,'Global tracked cap');save(path.join(__dirname,'BUDGET_RESERVATION.json'),budget);
const parentPath=path.join(root,'experiments/coupled_345_20261017/OPERATION.json'),parent=read(parentPath),cpPath=path.join(root,'results/COUPLED_345_20261017_01/SEED_3701_EP064.pt.gz');
const sources=['design.cjs','prepare.cjs','run_density.py','audit.cjs','diagnose.cjs','figures.py','report.cjs','thermal_guard.cjs'].map(f=>pin(path.join(__dirname,f)));
save(path.join(__dirname,'OPERATION.json'),{schema:'A24-load-density-operation-v1',utc:new Date().toISOString(),
 base_commit:cp.execFileSync('git',['rev-parse','HEAD'],{cwd:repo,encoding:'utf8'}).trim(),parent_operation:pin(parentPath),registration:parent.registration,physics:parent.physics,
 inputs:pin(path.join(__dirname,'INPUTS.json')),checkpoint:pin(cpPath),sources:[...parent.sources,...sources,
  pin(path.join(root,'experiments/work_window_20261017/reaccount.cjs')),pin(path.join(root,'experiments/sustained_load_20261017/tensor_reader.cjs'))],
 input_pins:[...parent.input_pins,pin(parentPath),pin(cpPath),...['INPUTS.json','BUDGET_RESERVATION.json','PURE_TEST_RESULT.json','THERMAL_PURE_TEST.json','EXTERNAL_S26_BUDGET_SNAPSHOT.json','AST_RESULT.json'].map(f=>pin(path.join(__dirname,f))),
  ...['FRESH_02_EDF.raw.json.gz','FRESH_02_RL_S3701.raw.json.gz','SELECTION_FROZEN.json'].map(f=>pin(path.join(root,parent.output_dir,f)))],
 parent_output:parent.output_dir,output_dir:'results/LOAD_DENSITY_20261017_01',environment_cap:36,planned_START:32,rate_multipliers:d.rate_multipliers,
 learner_seed:3701,checkpoint_episode:64,node_executable:'C:/Program Files/nodejs/node.exe',
 fixed_supply_s:120,post_supply_dispatch_allowance_s:600,completion_objective:'All requests to lastAVAILABLE; common3policy end for same-walltime AP; null if censored',
 physics_and_policy_unchanged:true,relative_deadlines_unchanged:true,temperature_clipping_added:false,new_training:0,new_physical_fit:0,new_device_actions:0,
 own_Python_limit:1,global_Python_limit:2,min_free_GiB:8,wall_clock_limit_s:7200,pre_START_transient_slot_wait_s:30,pre_START_wait_consumes_environment:false,
 saved_audit_and_figures_in_same_Python_process:true,automatic_retry:false,original_artifacts_immutable:true,measured_J:null,
 extrapolation:'Frozen short-training NN; larger queues/horizon outside training. Same600s catchup for every factor, distinct from earlier+15s generation.'});
console.log(JSON.stringify({status:'REGISTERED',checks,global_reserved:budget.global_reserved,planned_START:32,cap:36,cases:d.cases.map(c=>({id:c.id,n:c.n,multiplier:c.condition.rate_multiplier}))}));
