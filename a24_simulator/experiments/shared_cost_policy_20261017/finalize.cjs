'use strict';
const fs=require('fs'),path=require('path'),crypto=require('crypto'),cp=require('child_process');
const root=path.resolve(__dirname,'../..'),repo=path.dirname(root);
const read=p=>JSON.parse(fs.readFileSync(p)),pin=p=>({path:path.relative(root,p).replaceAll('\\','/'),sha256:crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex'),bytes:fs.statSync(p).size});
const modelOut=path.join(root,'results/SHARED_ACTIVATION_20261017_01'),policyOut=path.join(root,'results/SHARED_COST_POLICY_V2_20261017_01');
const a=read(path.join(modelOut,'AUDIT.json')),b=read(path.join(policyOut,'AUDIT.json')),r=read(path.join(policyOut,'RESULT.json'));
if(a.checks!==20462||b.checks!==4019||r.new_START!==8||r.new_COMPLETE!==8||r.new_FAIL!==0)throw Error('Unexpected frontier');
const continueFile=path.join(root,'CONTINUE.json'),prior=read(continueFile);
const current={status:'HYPOTHESIS_MODEL_AND_COST_AWARE_DEVELOPMENT_COMPLETE',
 report:'docs/SHARED_ACTIVATION_COST.md',model_bundle:'experiments/shared_activation_20261017/COST_BUNDLE.json',
 observer:'experiments/shared_activation_20261017/cost_adapter.py',
 saved_revaluation:'results/SHARED_ACTIVATION_20261017_01/COMPARISON.json',
 policy_operation:'experiments/shared_cost_policy_20261017/OPERATION_V2.json',
 policy_result:'results/SHARED_COST_POLICY_V2_20261017_01/ANALYSIS.json',
 new_environment_START:8,new_COMPLETE:8,new_FAIL:0,unique_contract_tests:26,saved_arithmetic_and_binding_checks:27001,
 original_RL_envelope:{cap:256,old_RL_consumed:223,choice_consumed:25,cost_policy_consumed:8,remaining:0},
 separate_RR_remaining:1,global_new_reservation:0,new_NN_training:0,new_fit:0,new_device_measurements:0,
 logical_hypotheses:['shared active component transferred to unmeasured pairs','idle decay0.9s reference scenario'],
 shared_scale:1,idle_decay_s:.9,total_cost_change_percent:-.022571475252242124,
 unchanged_schedule_cases:3,conditions:4,physical_energy_accuracy_verified:false,robust_policy_superiority:false,
 zero_shared_assumption_reverses_energy_ranking:true,original_interactive_default_unchanged:true,measured_J:null};
if(prior.shared_activation_cost_development)throw Error('Already finalized');
fs.writeFileSync(continueFile,JSON.stringify({shared_activation_cost_development:current,...prior},null,2)+'\n');
const files=[];
for(const directory of [modelOut,policyOut])for(const f of fs.readdirSync(directory))files.push(path.join(directory,f));
for(const f of ['shared_activation_20261017/OPERATION.json','shared_activation_20261017/COST_BUNDLE.json',
 'shared_cost_policy_20261017/OPERATION_V2.json','shared_cost_policy_20261017/BUDGET_TRANSFER.json',
 'shared_cost_policy_20261017/AUDIT_OPERATION_V2.json'])files.push(path.join(root,'experiments',f));
files.push(continueFile,__filename,path.join(root,'docs/SHARED_ACTIVATION_COST.md'),path.join(root,'docs/CHOICE_OPPORTUNITIES.md'),path.join(root,'README.md'),path.join(repo,'docs/PROJECT_STATUS.md'));
const proof={schema:'A24-shared-cost-final-handoff-proof-v1',utc:new Date().toISOString(),
 verification_base_commit:cp.execFileSync('git',['rev-parse','HEAD'],{cwd:repo,encoding:'utf8'}).trim(),
 worktree_at_capture:cp.execFileSync('git',['status','--short'],{cwd:repo,encoding:'utf8'}).trim(),
 unique_contract_tests:26,saved_arithmetic_and_binding_checks:27001,
 new_environment_START:8,new_COMPLETE:8,new_FAIL:0,original_envelope_consumed:256,original_envelope_remaining:0,
 prestart_import_failure_preserved:true,audit_first_attempt_failure_preserved:true,environment_restart:0,
 new_global_reservation:0,new_fit:0,new_NN_training:0,new_device_measurements:0,measured_J:null,
 physical_energy_accuracy_verified:false,parameter_sensitivity_is_CI:false,
 files:files.map(pin)};
fs.writeFileSync(path.join(policyOut,'FINAL_HANDOFF_PROOF.json'),JSON.stringify(proof,null,2)+'\n',{flag:'wx'});
console.log(JSON.stringify({status:'FINALIZED',pins:files.length,unique_tests:26,checks:27001,new_START:8,remaining:0}));
