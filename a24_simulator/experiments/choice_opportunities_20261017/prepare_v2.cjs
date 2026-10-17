'use strict';
const fs=require('fs'),path=require('path'),crypto=require('crypto');
const D=require('../competition_cost_20261017/competition_design.cjs'),root=path.resolve(__dirname,'../..');
const read=p=>JSON.parse(fs.readFileSync(p,'utf8')),sha=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
const pin=p=>({path:path.resolve(p),sha256:sha(p),bytes:fs.statSync(p).size});
const save=(p,x)=>fs.writeFileSync(p,JSON.stringify(x,null,2)+'\n',{flag:'wx'});
const oldout=path.join(root,'results/CHOICE_OPPORTUNITIES_20261017_01');
const receipts=fs.readFileSync(path.join(oldout,'receipts.jsonl'),'utf8').trim().split(/\r?\n/).map(JSON.parse);
const starts=receipts.filter(r=>r.event==='START'),ends=receipts.filter(r=>r.event==='COMPLETE'),fails=receipts.filter(r=>r.event==='FAIL');
if(starts.length!==13||ends.length!==12||fails.length!==1)throw Error('Inspect changed prior frontier before transfer');
const partial={schema:'A24-choice-opportunity-closed-frontier-v1',START:13,COMPLETE:12,FAIL:1,
 failed:fails,failed_prediction_saved:false,original_AP_unknown_reason_not_saved:true,
 automatic_restart:false,closed:true,rows:ends.map(r=>read(path.join(oldout,r.label+'.json'))),
 interpretation:'Packet input alone exposes a queue-admission/work-conserving tradeoff; all successes and failure retained'};
save(path.join(oldout,'CLOSED_FRONTIER.json'),partial);
const cases=[];
for(const [pi,packet] of [2,4].entries()){
 const base=D.build(.5,D.SPEC.patterns[pi],.95,20269119),pair='C50_P'+packet;
 for(const arm of ['REFERENCE','PACKET']){
  const input=JSON.parse(JSON.stringify(base.input));
  if(arm==='PACKET')input.requests=input.requests.map((q,i)=>{const a=+(35+Math.floor(i/packet)*packet*.8).toFixed(8);return {...q,arrival_s:a,deadline_s:+(a+q.deadline_s-q.arrival_s).toFixed(8)};});
  const hi=+(Math.max(...input.requests.map(q=>q.arrival_s))+15).toFixed(8);
  cases.push({id:pair+'_'+arm,pair,arm,mix:.5,packet,n:48,input,work_window:[35,hi],
   service_stop_s:hi,drain_stop_s:+(hi+30).toFixed(8),observation_end_s:+(hi+180).toFixed(8),
   common_potential_key:['A24_CHOICE_COALESCING_V2_20261017',20269119,pair]});
 }
}
save(path.join(__dirname,'INPUTS_V2.json'),{schema:'A24-choice-coalescing-inputs-v2',cases,
 development_iteration:true,design_feedback:'First v1 pairs showed different admission completion times and immediate dispatch prevented ready-queue competition',
 primary_target:'Within packet cases, COALESCED_COST increases multiple-ready requests versus COST_PRIOR without sacrificing both-free rate',
 limits:'Nominal protection retained; all timing/late/UNKNOWN outcomes reported; not independently held-out confirmation'});
save(path.join(__dirname,'BUDGET_TRANSFER_V2.json'),{schema:'A24-closed-child-allocation-transfer-v2',
 parent:pin(path.join(__dirname,'BUDGET_TRANSFER.json')),frontier:pin(path.join(oldout,'CLOSED_FRONTIER.json')),
 receipts:pin(path.join(oldout,'receipts.jsonl')),parent_cap:28,parent_consumed:13,
 transferred:12,parent_unallocated_after:3,global_reservation_increment:0,
 original_RL_envelope_conservation:'223 old RL + 13 v1 consumed + 12 v2 allocated + 3 v1 unused + 5 original unallocated = 256',
 current_user_authority:'Improve choice opportunities; continuation in a new source/input generation, no failed identity rerun'});
const previous=read(path.join(__dirname,'OPERATION.json'));
const sources=[...previous.sources,...['observer_v2.py','run_v2.py','prepare_v2.cjs','test_coalescing.py'].map(p=>pin(path.join(__dirname,p)))];
save(path.join(__dirname,'OPERATION_V2.json'),{...previous,schema:'A24-choice-coalescing-operation-v2',created_utc:new Date().toISOString(),sources,
 inputs:pin(path.join(__dirname,'INPUTS_V2.json')),budget:pin(path.join(__dirname,'BUDGET_TRANSFER_V2.json')),
 output_dir:'results/CHOICE_OPPORTUNITIES_V2_20261017_01',environment_cap:12,planned_START:12,
 policies:['EDF','COST_PRIOR','COALESCED_COST'],AP_unknown_is_preserved:true,
 coalescing:'50ms existing legal WAIT, only both-free and one physically ready candidate; no future arrivals used'});
console.log('V1 closed 12 COMPLETE + 1 FAIL. V2: new seed 20269119, 4 inputs x 3 policies = 12; no new global reservation.');
