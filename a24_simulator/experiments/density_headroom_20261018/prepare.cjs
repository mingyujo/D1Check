'use strict';
const fs=require('fs'),path=require('path'),crypto=require('crypto'),cp=require('child_process');
const root=path.resolve(__dirname,'../..'),repo=path.dirname(root),read=p=>JSON.parse(fs.readFileSync(p)),sha=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
const pin=p=>({path:p,sha256:sha(p),bytes:fs.statSync(p).size}),save=(p,x)=>fs.writeFileSync(p,JSON.stringify(x,null,2)+'\n',{flag:'wx'});
const parentPath=path.join(root,'experiments/load_density_20261017/OPERATION.json'),parent=read(parentPath),previous=read(path.join(root,'experiments/load_density_20261017/BUDGET_RESERVATION.json'));
if(!read(path.join(__dirname,'PURE_TEST_RESULT_V2.json')).successful||read(path.join(__dirname,'AST_RESULT_V2.json')).status!=='PASS')throw Error('Pure math/AST checks required');
for(const p of read(path.join(__dirname,'AST_RESULT_V2.json')).files)if(sha(path.join(__dirname,p.path))!==p.sha256)throw Error('AST version mismatch');
const external=path.join(repo,'../S26-D1Check/s26_simulator/experiments/sustained_load_v1/BUDGET_RESERVATION.json');
if(sha(external)!==sha(path.join(root,'experiments/load_density_20261017/EXTERNAL_S26_BUDGET_SNAPSHOT.json')))throw Error('Refresh parallel budget snapshot before reservation');
const budget={utc:new Date().toISOString(),previous:pin(path.join(root,'experiments/load_density_20261017/BUDGET_RESERVATION.json')),known_parallel_S26:pin(external),
 previous_global_reserved:previous.global_reserved,new_reservation:88,global_reserved:previous.global_reserved+88,global_cap:previous.global_cap,
 cap:88,planned_START:82,allocation:{P0:2,offline_witness:80},LP_solves:40,LP_seconds_each:15,
 old_coupled38_savings8_sustained4_density4_RR1_untouched:true,frozen_bank_restores:1,new_physical_fit:0,new_training:0,new_device_actions:0,
 automatic_retry:false,global_accounting:'Tracked snapshot including known parallel S26 reservation; not a fresh all-host actual START census',
 user_authority:'2026-10-18: same model/inputs, deadline-preserving thermal/energy schedules and optimistic savings upper bounds; show every row with exclusion reasons'};
if(budget.global_reserved>budget.global_cap)throw Error('Global tracked cap');save(path.join(__dirname,'BUDGET_RESERVATION.json'),budget);
const local=['bounds.py','actors.py','run.py','audit.cjs','figures.py','report.cjs','test_contracts.py','preflight.py','prepare.cjs'].map(f=>pin(path.join(__dirname,f)));
const ref=path.join(root,parent.output_dir),references=read(path.join(ref,'WORK_METRICS.json')).rows;
const extra=[pin(parentPath),...['RESULT.json','COMPLETE.json','AUDIT.json','WORK_METRICS.json'].map(f=>pin(path.join(ref,f))),
 ...references.map(r=>pin(path.join(ref,r.label+'.raw.json.gz'))),...['PURE_TEST_RESULT_V2.json','AST_RESULT_V2.json','BUDGET_RESERVATION.json'].map(f=>pin(path.join(__dirname,f)))];
const dedup=a=>[...new Map(a.map(p=>[p.path.toLowerCase(),p])).values()];
const thermal=read(path.join(root,'experiments/load_density_20261017/THERMAL_PURE_TEST.json'));
save(path.join(__dirname,'OPERATION.json'),{schema:'A24-density-headroom-v1',utc:new Date().toISOString(),base_commit:cp.execFileSync('git',['rev-parse','HEAD'],{cwd:repo,encoding:'utf8'}).trim(),
 parent_operation:pin(parentPath),registration:parent.registration,physics:parent.physics,inputs:parent.inputs,
 sources:dedup([...parent.sources,...local]),input_pins:dedup([...parent.input_pins,...extra]),parent_output:parent.output_dir,output_dir:'results/DENSITY_HEADROOM_20261018_01',
 environment_cap:88,planned_START:82,LP_cap:40,LP_seconds:15,temperature_step_c:.05,thermal_upper_c:thermal.refined_invariant_upper_c,
 common_end_ns:Object.fromEntries(references.filter(r=>r.policy==='EDF').map(r=>[r.case,r.common.end_ns])),
 SLA_tiers:{EDF:'Preserve original EDF total and urgent ontime counts; all jobs AVAILABLE',STRONG:'Preserve componentwise max of original EDF/RL ontime counts; all jobs AVAILABLE'},
 witness_recipes:['ENERGY','TOTAL','REGRET','LP_ROUTE','HEAT','COOL35','COOL36','SLA_ENERGY'],
 knowledge:'Offline full future route potentials; physical feasibility witnesses, not deployable online policy claims',
 energy_scope:'Own full completion, no extra makespan cap beyond original drain; baseline included',
 thermal_scope:'Original three-policy common endpoint frozen; full completion required by that endpoint for thermal qualification',
 bound_scope:'Continuous assignment + independent thermal work fractions + necessary release/deadline capacities; bounded-power RC deposition LP; repaired boxed duals with margins',
 all_rows_displayed:true,exclusion_reasons_required:true,native_rows_in_report:82,original_rows_in_report:30,
 new_training:0,new_physical_fit:0,new_device_actions:0,original_artifacts_immutable:true,automatic_retry:false,
 own_Python_limit:1,global_Python_limit:2,min_free_GiB:8,wall_clock_limit_s:7200,pre_START_transient_slot_wait_s:30,
 node_executable:'C:/Program Files/nodejs/node.exe',saved_audit_and_figures_in_same_producer:true});
console.log(JSON.stringify({status:'REGISTERED',planned_START:82,cap:88,LP:40,global_reserved:budget.global_reserved,all_rows:112}));
