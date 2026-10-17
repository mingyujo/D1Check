'use strict';
const fs=require('fs'),path=require('path'),crypto=require('crypto');
const root=path.resolve(__dirname,'../..'),old=path.join(root,'experiments/choice_opportunities_20261017');
const D=require('../competition_cost_20261017/competition_design.cjs');
const read=p=>JSON.parse(fs.readFileSync(p,'utf8')),pin=p=>({path:p,sha256:crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex'),bytes:fs.statSync(p).size});
const save=(p,q)=>fs.writeFileSync(p,JSON.stringify(q,null,2)+'\n',{flag:'wx'});
const parent=read(path.join(old,'BUDGET_TRANSFER.json')),child=read(path.join(old,'BUDGET_TRANSFER_V2.json'));
if(parent.old_unused_after!==5||child.parent_unallocated_after!==3)throw Error('Inspect remaining budget');
const prior=read(path.join(root,'results/CHOICE_OPPORTUNITIES_V2_20261017_01/RESULT.json'));
if(prior.new_START!==12||prior.new_COMPLETE!==12)throw Error('Unexpected frontier');
const cases=[];
for(const [i,packet] of [2,4].entries()){
 const original=D.build(.5,D.SPEC.patterns[i],.95,20269123);
 for(const arm of ['REFERENCE','PACKET']){
  const input=JSON.parse(JSON.stringify(original.input));
  if(arm==='PACKET')input.requests=input.requests.map((q,j)=>{const a=+(35+Math.floor(j/packet)*packet*.8).toFixed(8);return {...q,arrival_s:a,deadline_s:+(a+q.deadline_s-q.arrival_s).toFixed(8)};});
  const hi=+(Math.max(...input.requests.map(q=>q.arrival_s))+15).toFixed(8);
  cases.push({id:'C50_P'+packet+'_'+arm,pair:'C50_P'+packet,arm,packet,n:48,input,
   work_window:[35,hi],service_stop_s:hi,drain_stop_s:+(hi+30).toFixed(8),observation_end_s:+(hi+180).toFixed(8),
   common_potential_key:['A24_SHARED_COST_POLICY_20261017',20269123,packet]});
 }
}
save(path.join(__dirname,'INPUTS.json'),{schema:'A24-shared-cost-policy-input-v1',cases,new_seed:20269123,
 development_followup:true,prior_saved_comparison_informed_decision_to_test_cost_aware_actions:true,
 independent_confirmation:false,parameter_tuning_by_result:false});
save(path.join(__dirname,'BUDGET_TRANSFER.json'),{schema:'A24-last-unallocated-envelope-transfer-v1',
 original_unallocated_pin:pin(path.join(old,'BUDGET_TRANSFER.json')),child_unallocated_pin:pin(path.join(old,'BUDGET_TRANSFER_V2.json')),
 closed_v2_pin:pin(path.join(root,'results/CHOICE_OPPORTUNITIES_V2_20261017_01/RESULT.json')),
 old_consumed:248,original_unallocated_transferred:5,child_unallocated_transferred:3,transferred:8,
 unallocated_after:0,global_reservation_increment:0,RR_unused1_untouched:true,
 conservation:'223 old RL + 25 choice START + 8 newly allocated = 256; no failed identity re-run'});
const oldop=read(path.join(old,'OPERATION_V2.json'));
const extra=['shared_policy.py','run_policy.py','prepare.cjs','test_policy.py','audit_policy.cjs'].map(p=>pin(path.join(__dirname,p)));
const sharedDir=path.join(root,'experiments/shared_activation_20261017');
extra.push(...['shared_cost.py','COST_BUNDLE.json'].map(p=>pin(path.join(sharedDir,p))));
save(path.join(__dirname,'OPERATION.json'),{...oldop,schema:'A24-shared-cost-policy-operation-v1',created_utc:new Date().toISOString(),
 sources:[...oldop.sources,...extra],inputs:pin(path.join(__dirname,'INPUTS.json')),budget:pin(path.join(__dirname,'BUDGET_TRANSFER.json')),
 output_dir:'results/SHARED_COST_POLICY_20261017_01',environment_cap:8,planned_START:8,policies:['COALESCED_COST','SHARED_COST'],
 primary:'Paired new-model total/increment/full-tail cost with all service/AP harms; no guaranteed win',
 new_policy:'minimum exact full-episode nominal marginal energy among same protected actions; same coalescing',
 new_cost_shared_scale:1,new_cost_idle_decay_s:.9,new_NN:0,source_physics_unchanged:true,
 unknown_pair_and_idle_tail_are_hypotheses:true,model_parameters_selected_by_policy_gap:false});
console.log('Registered4 new inputs x2 same-mask policies; last8 transferred, global+0, RR untouched.');
