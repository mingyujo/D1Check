'use strict';
const fs=require('fs'),path=require('path'),crypto=require('crypto'),cp=require('child_process');
const {generate}=require('./design.cjs'),root=path.resolve(__dirname,'../..');
const read=p=>JSON.parse(fs.readFileSync(p,'utf8'));
const sha=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
const pin=p=>({path:path.resolve(p),sha256:sha(p),bytes:fs.statSync(p).size});
const save=(p,x)=>fs.writeFileSync(p,JSON.stringify(x,null,2)+'\n',{flag:'wx'});
const proofPath=path.join(root,'results/RL_COST_20261017_01/FINAL_HANDOFF_PROOF.json');
const proof=read(proofPath),oldBudget=path.join(root,'experiments/rl_cost_20261017/BUDGET_RESERVATION.json');
const old=read(oldBudget),terminal=read(path.join(root,'results/RL_COST_20261017_01/COMPLETE.json'));
if(old.new_reservation!==256||terminal.new_COMPLETE!==223||proof.completed.RL_START!==223||proof.completed.RL_FAIL!==0)throw Error('Prior allocation is not terminal');
const rows=fs.readFileSync(path.join(root,'results/RL_COST_20261017_01/receipts.jsonl'),'utf8').trim().split(/\r?\n/).map(JSON.parse);
if(rows.filter(r=>r.event==='START').length!==223||rows.some(r=>r.event==='FAIL'))throw Error('Old consumption frontier differs');
save(path.join(__dirname,'INPUTS.json'),generate());
save(path.join(__dirname,'BUDGET_TRANSFER.json'),{schema:'A24-closed-allocation-transfer-v1',
 authority:'2026-10-17 current user request: improve item 1 (choice opportunities)',
 parent_budget:pin(oldBudget),parent_terminal:pin(path.join(root,'results/RL_COST_20261017_01/COMPLETE.json')),
 parent_handoff:pin(proofPath),parent_receipts:pin(path.join(root,'results/RL_COST_20261017_01/receipts.jsonl')),
 old_reserved:256,old_consumed:223,old_unused_before:33,transferred:28,old_unused_after:5,
 new_reservation:0,global_reservation_increment:0,global_reserved_at_parent_registration:124838,global_cap:137712,
 conservation:'223 consumed + 28 transferred + 5 unallocated = old allocation 256',
 no_parent_restart:true,must_publish_before_execution:true,new_expected_START:24,
 actual_global_START_at_parent_handoff:31712,actual_global_START_is_historical_snapshot:true});
const sources=['design.cjs','observer.py','run.py','prepare.cjs','test_design.cjs'].map(p=>pin(path.join(__dirname,p)));
for(const p of ['src/lab_backend.py','src/four_route_model.py','src/thermal_four_route.py',
 'experiments/rl_cost_20261017/rl_policy.py','experiments/long_scale_20261017/bridge_long.py',
 'experiments/long_scale_20261017/kernel_long.py','experiments/long_scale_20261017/fast_thermal.py',
 'experiments/rules_no_rl_20261017/shared_exact.py','experiments/competition_cost_20261017/state_cost.py',
 'experiments/edf_cpu_first_20261016/policy.py','reference/model_integration/runtime_guard.py'])sources.push(pin(path.join(root,p)));
save(path.join(__dirname,'OPERATION.json'),{schema:'A24-choice-opportunity-operation-v1',created_utc:new Date().toISOString(),
 base_commit:cp.execFileSync('git',['rev-parse','HEAD'],{cwd:root,encoding:'utf8'}).trim(),
 sources,inputs:pin(path.join(__dirname,'INPUTS.json')),budget:pin(path.join(__dirname,'BUDGET_TRANSFER.json')),
 registration:pin(path.join(root,'models/registration.json')),
 cost_model:pin(path.join(root,'results/STATE_COST_IDENTIFICATION_20261017_01/MODEL.json')),
 output_dir:'results/CHOICE_OPPORTUNITIES_20261017_01',environment_cap:28,planned_START:24,
 policies:['EDF','COST_PRIOR'],NN_execution:0,NN_training:0,new_fit:0,
 protection_changed:false,relative_deadlines_changed:false,physical_capacity_changed:false,
 automatic_retry:false,evaluation_role:'development paired-input diagnostic; not untouched confirmation',
 new_device_measurements:0,measured_J:null,recurring_automation:false,periodic_GitHub_check:false});
console.log('REGISTERED: 6 fresh matched input pairs x 2 fixed policies = 24 START; transfer 28 of closed RL allocation, new reservation 0');
