'use strict';
const fs=require('fs'),path=require('path'),crypto=require('crypto'),cp=require('child_process');
const root=path.resolve(__dirname,'../..'),repo=path.dirname(root),read=p=>JSON.parse(fs.readFileSync(p));
const pin=p=>({path:p,sha256:crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex'),bytes:fs.statSync(p).size});
const save=(p,v)=>fs.writeFileSync(p,JSON.stringify(v,null,2)+'\n',{flag:'wx'});
const parentFile=path.join(root,'experiments/coupled_345_20261017/OPERATION.json'),parent=read(parentFile);
if(!read(path.join(__dirname,'PURE_TEST_RESULT.json')).successful)throw Error('Pure contracts required');
const prior=read(path.join(root,'experiments/coupled_345_20261017/BUDGET_RESERVATION.json'));
const budget={schema:'A24-savings-limit-separate-reservation-v1',utc:new Date().toISOString(),
 previous:pin(path.join(root,'experiments/coupled_345_20261017/BUDGET_RESERVATION.json')),
 previous_global_reserved:prior.global_reserved,new_reservation:288,global_reserved:prior.global_reserved+288,global_cap:prior.global_cap,
 planned_START:280,cap:288,allocation:{P0:2,full_clairvoyant_witness:36,micro_reference:2,micro_list_plans:240},
 unused_coupled345_38_untouched:true,old_RL256_remaining:0,separate_RR1_untouched:true,
 restored_frozen_timing_bank:1,new_physical_fit:0,new_training:0,MILP_solves:24,MILP_time_cap_seconds_each:10,
 global_accounting:'Tracked snapshot; not a fresh census of actual START on every host',
 user_authority:'2026-10-17: explicitly check the possible scheduling savings limit',automatic_retry:false};
if(budget.global_reserved>budget.global_cap)throw Error('Tracked global cap');
save(path.join(__dirname,'BUDGET_RESERVATION.json'),budget);
const sources=['math_bounds.py','actors.py','run.py','audit.py','report.cjs','figure.py','test_bounds.py','prepare.cjs'].map(f=>pin(path.join(__dirname,f)));
const scipy=path.join('C:/Users/user/anaconda3/Lib/site-packages/scipy/optimize/_milp.py');
save(path.join(__dirname,'OPERATION.json'),{schema:'A24-savings-limit-offline-diagnosis-v1',utc:new Date().toISOString(),
 base_commit:cp.execFileSync('git',['rev-parse','HEAD'],{cwd:repo,encoding:'utf8'}).trim(),
 parent_operation:pin(parentFile),registration:parent.registration,inputs:parent.inputs,physics:parent.physics,
 sources:[...parent.sources,...sources,pin(path.join(root,'reference/model_integration/timing_model.py')),pin(scipy)],
 input_pins:[...parent.input_pins,pin(parentFile),...['RESULT.json','COMPLETE.json','AUDIT.json'].map(f=>pin(path.join(root,parent.output_dir,f))),
  ...['BUDGET_RESERVATION.json','PURE_TEST_RESULT.json','AST_RESULT.json'].map(f=>pin(path.join(__dirname,f)))],
 parent_output:parent.output_dir,output_dir:'results/SAVINGS_LIMIT_20261017_01',environment_cap:288,planned_START:280,
 P0_indices:[0,9],micro_indices:[0,6],micro_subset:'first2 C and first2 D by original ordinal; preserve arrivals/deadlines/potential key/windows',
 micro_optimality_scope:'exact over120 specified lane-assignment/order list plans only; not all continuous-time schedules',
 full_witness_policies:['TRUTH_EXACT','TRUTH_ATC','ENERGY_ROUTE'],full_witnesses_are_not_global_optima:true,
 temperature_interval_step_c:.01,MILP_seconds_per_solve:10,MILP_node_cap:100000,
 objective:'Lower bounds for energy and mean temperature, preserving EDF on-time/urgent counts and all responses/AVAILABLE; bracket with saved feasible schedules',
 physical_constraints:'one CPU, one GPU, nonpreemptive AVAILABLE ownership; same service/drain windows and common baseline',
 relaxation:'all future route potentials; independent thermal states; necessary-only interval demand; no claim of online attainability',
 wall_clock_limit_s:3600,own_Python_limit:1,global_Python_limit:2,min_free_GiB:8,
 new_physical_fit:0,new_training:0,new_device_actions:0,automatic_retry:false,original_artifacts_immutable:true,measured_J:null});
console.log('Registered280 native executions in new288 reservation; analytical/MILP bounds explicit; no original-op restart.');
