'use strict';
const fs=require('fs'),path=require('path'),crypto=require('crypto'),cp=require('child_process');
const root=path.resolve(__dirname,'../..'),read=p=>JSON.parse(fs.readFileSync(p,'utf8'));
const sha=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
const pin=p=>({path:path.relative(root,p).replaceAll('\\','/'),sha256:sha(p),bytes:fs.statSync(p).size});
const v1=path.join(root,'results/CHOICE_OPPORTUNITIES_20261017_01'),v2=path.join(root,'results/CHOICE_OPPORTUNITIES_V2_20261017_01');
const frontier=read(path.join(v1,'CLOSED_FRONTIER.json')),terminal=read(path.join(v2,'COMPLETE.json')),analysis=read(path.join(v2,'ANALYSIS.json'));
if(frontier.START!==13||frontier.COMPLETE!==12||frontier.FAIL!==1||terminal.new_COMPLETE!==12||analysis.checks!==4765)throw Error('Final frontier changed');
const old=path.join(root,'results/RL_COST_20261017_01/COMPLETE.json'),oldTerminal=read(old);
if(oldTerminal.new_COMPLETE!==223||223+13+12+8!==256)throw Error('Allocation conservation');
const files=[path.join(v1,'CLOSED_FRONTIER.json'),path.join(v1,'receipts.jsonl'),
 path.join(v2,'COMPLETE.json'),path.join(v2,'RESULT.json'),path.join(v2,'ANALYSIS.json'),path.join(v2,'receipts.jsonl'),
 ...['OPERATION.json','OPERATION_V2.json','BUDGET_TRANSFER.json','BUDGET_TRANSFER_V2.json','observer.py','observer_v2.py',
 'run.py','run_v2.py','summarize_v2.cjs','record_final.cjs','test_design.cjs','test_observer.py','test_coalescing.py'].map(p=>path.join(__dirname,p)),
 path.join(root,'docs/CHOICE_OPPORTUNITIES.md'),path.join(root,'CONTINUE.json'),old];
const legacy=path.join(root,'runtime/receipts.jsonl'),saved=path.join(root,'results/COMPETITION_WITNESS_AUDIT_20261017_01/SAVED_SHARED_RECEIPTS.jsonl');
if(sha(legacy)!==sha(saved))throw Error('Original consumption must not be reset');
const proof={schema:'A24-choice-opportunity-final-handoff-v1',status:'COMPLETE_DEVELOPMENT_VARIANT_ONLY',created_utc:new Date().toISOString(),
 base_commit:'51117e2a1139a1532ba20f1efb8916fa335f6f38',commit_before_final:cp.execFileSync('git',['rev-parse','HEAD'],{cwd:root,encoding:'utf8'}).trim(),
 this_task:{START:25,COMPLETE:24,FAIL:1,new_NN_execution:0,new_training:0,new_model_fit:0,new_device_measurement:0},
 V1:{START:13,COMPLETE:12,FAIL:1,failed_identity_retried:false,initial_contract_complete:false,failed_AP_reason_not_saved:true},
 V2:{START:12,COMPLETE:12,FAIL:0,saved_checks:4765,AP_unknown_conditions:0,primary:analysis.primary},
 budget:{original_RL_reserved:256,original_RL_consumed:223,this_task_consumed:25,unallocated:8,
  unchanged_RR_unallocated:1,global_reservation_increment:0,old_global_reserved_snapshot:124838,global_cap:137712,
  global_actual_current_not_claimed:true,legacy_shared_ledger_sha256:sha(legacy)},
 interactive_default_replaced:false,original_physics_modified:false,original_protection_modified:false,
 measured_J:null,physical_goal_verified:false,RL_superiority_verified:false,recurring_automation:false,periodic_GitHub_check:false,
 evidence:files.map(pin),limitations:['C50% and two packet sizes only; iterative development, not fresh independent confirmation',
  'Aggregate on-time unchanged but condition-level -1/+1; cost slightly worse',
  'Initial +10 percentage point targets not established; new coalescing comparison target passed',
  'V1 AP failure retained without the missing detailed original reason; never reproduced or refunded']};
fs.writeFileSync(path.join(v2,'FINAL_HANDOFF_PROOF.json'),JSON.stringify(proof,null,2)+'\n',{flag:'wx'});
console.log(JSON.stringify({status:proof.status,START:25,COMPLETE:24,FAIL:1,checks:4765,evidence:files.length}));
