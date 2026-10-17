'use strict';
const fs=require('fs'),path=require('path'),zlib=require('zlib'),crypto=require('crypto');
const root=path.resolve(__dirname,'../..'),out=path.join(root,'results/CHOICE_OPPORTUNITIES_V2_20261017_01');
const read=p=>JSON.parse(fs.readFileSync(p,'utf8')),sha=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
let checks=0;function need(v,s){checks++;if(!v)throw Error(s);}
const op=read(path.join(__dirname,'OPERATION_V2.json')),r=read(path.join(out,'RESULT.json')),terminal=read(path.join(out,'COMPLETE.json'));
need(sha(path.join(out,'RESULT.json'))===terminal.result_sha256,'Result terminal SHA');
for(const p of [...op.sources,op.inputs,op.budget,op.cost_model,op.registration])need(sha(p.path)===p.sha256&&fs.statSync(p.path).size===p.bytes,'Frozen source/input bytes');
const receipts=fs.readFileSync(path.join(out,'receipts.jsonl'),'utf8').trim().split(/\r?\n/).map(JSON.parse);
const starts=receipts.filter(x=>x.event==='START'),ends=receipts.filter(x=>x.event==='COMPLETE');
need(starts.length===12&&ends.length===12&&!receipts.some(x=>x.event==='FAIL'),'12 unique complete environments');
need(new Set(starts.map(x=>x.identity)).size===12,'Unique consumption');
const derived=[];
for(const row of r.rows){
 const label=row.case+'_'+row.policy,file=path.join(out,label+'.json'),raw=path.join(out,label+'.raw.json.gz'),receipt=ends.find(x=>x.label===label);
 need(sha(file)===receipt.result_sha256&&sha(raw)===receipt.raw_sha256,'Saved byte links');
 const d=JSON.parse(zlib.gunzipSync(fs.readFileSync(raw))),q=d.prediction.requests;
 const calls=d.actor_calls.filter(c=>c.action.kind==='DISPATCH'),decisions=d.prediction.decisions.filter(x=>x.action.kind==='DISPATCH');
 need(calls.length===48&&decisions.length===48&&d.opportunities.length===48,'Dispatch-only denominator');
 const done=new Set();let multi=0,both=0,joint=0,on=0,urgent=0;
 for(let i=0;i<48;i++){
  const c=calls[i],decision=decisions[i],o=d.opportunities[i],t=decision.time_ns;
  need(c.time_ns===t&&o.time_ns===t&&JSON.stringify(c.action)===JSON.stringify(decision.action),'Actor-applied clock/action');
  const active=q.filter(x=>done.has(x.request_id)&&x.available_ns>t);
  need(active.length<2&&!active.some(x=>x.route===c.action.route),'CPU/GPU lane exclusion');
  const ready=q.filter(x=>!done.has(x.request_id)&&x.queue_entry_ns!=null&&x.queue_entry_ns<=t);
  need(ready.length===o.requests_before,'Physical ready queue census');
  const slots=new Set(c.mask.slice(0,72).flatMap((v,j)=>v?[Math.floor(j/3)]:[]));
  need(slots.size===o.requests_after,'Protected mask census independently from saved calls');
  need(o.two_physical_routes===(active.length===0),'Both-free census from completed schedule');
  if(row.policy!=='EDF')need(c.mask[c.chosen_index],'Actual protected action legal');
  else{
   const head=[...ready].sort((a,b)=>a.deadline_ns-b.deadline_ns||a.scheduled_arrival_ns-b.scheduled_arrival_ns||a.ordinal-b.ordinal)[0];
   need(c.action.request_id===head.request_id&&c.action.route===(active.some(x=>x.route==='CPU')?'GPU':'CPU'),'Unchanged EDF rule');
  }
  const chosen=q.find(x=>x.request_id===c.action.request_id);need(chosen.dispatch_ns===t&&chosen.scheduled_arrival_ns<=chosen.queue_entry_ns&&chosen.queue_entry_ns<=t,'Request clocks');
  need(chosen.response_ns===(chosen.task==='C'?chosen.output_ready_ns:chosen.persist_complete_ns)&&chosen.available_ns>=chosen.response_ns,'Response boundary/AVAILABLE');
  on+=Number(chosen.response_ns<=chosen.deadline_ns);urgent+=Number(chosen.priority==='U'&&chosen.response_ns<=chosen.deadline_ns);
  multi+=Number(slots.size>1);both+=Number(active.length===0);joint+=Number(slots.size>1&&active.length===0);done.add(chosen.request_id);
 }
 need(on===row.metrics.on_time&&urgent===row.metrics.urgent_on_time,'All deadline outcomes');
 const waits=d.actor_calls.filter(c=>c.action.kind==='WAIT');
 need(waits.length===row.opportunities.coalescing_WAIT_calls,'Separate WAIT count');
 for(const c of waits){
  need(c.mask[c.chosen_index]&&c.action.wait_ns===50e6,'Existing protected 50ms WAIT');
  need(c.public_state.owners.length===0&&c.public_state.queue.length===1,'WAIT uses only current idle/single-ready state');
 }
 if(row.AP_status!=='CONDITIONAL_AP_PREDICTION')need(row.metrics.mean_AP_c===null&&!!row.AP_reason,'AP UNKNOWN retained as null/reason');
 derived.push({...row,multiple_requests_after:multi,two_free_routes:both,joint_choices:joint});
}
const aggregates=[];
for(const policy of op.policies)for(const arm of ['REFERENCE','PACKET']){
 const v=derived.filter(x=>x.policy===policy&&x.arm===arm),n=v.length*48,sum=k=>v.reduce((s,x)=>s+x[k],0);
 const temp=v.filter(x=>Number.isFinite(x.metrics.mean_AP_c));
 aggregates.push({policy,arm,conditions:v.length,dispatch:n,multiple_request_percent:100*sum('multiple_requests_after')/n,
  two_free_percent:100*sum('two_free_routes')/n,joint_choice_percent:100*sum('joint_choices')/n,
  on_time:v.reduce((s,x)=>s+x.metrics.on_time,0),urgent_on_time:v.reduce((s,x)=>s+x.metrics.urgent_on_time,0),
  response_missing:v.reduce((s,x)=>s+x.metrics.response_missing,0),AVAILABLE_by_window_end:v.reduce((s,x)=>s+x.metrics.AVAILABLE_by_window_end,0),
  coalescing_WAIT_calls:v.reduce((s,x)=>s+x.opportunities.coalescing_WAIT_calls,0),
  mean_total_J_proxy:v.reduce((s,x)=>s+x.metrics.total_J_proxy,0)/v.length,
  mean_increment_J_proxy:v.reduce((s,x)=>s+x.metrics.increment_J_proxy,0)/v.length,
  mean_AP_c:temp.length===v.length?temp.reduce((s,x)=>s+x.metrics.mean_AP_c,0)/v.length:null,
  AP_unknown_conditions:v.length-temp.length});
}
const a=aggregates.find(x=>x.policy==='COST_PRIOR'&&x.arm==='PACKET'),b=aggregates.find(x=>x.policy==='COALESCED_COST'&&x.arm==='PACKET');
const primary={multiple_request_gain_pp:b.multiple_request_percent-a.multiple_request_percent,
 two_free_gain_pp:b.two_free_percent-a.two_free_percent,
 PASS:b.multiple_request_percent>a.multiple_request_percent&&b.two_free_percent>=a.two_free_percent};
const value={schema:'A24-choice-coalescing-saved-analysis-v2',status:'PASS_SAVED_RECONCILIATION',checks,aggregates,primary,
 result_sha256:terminal.result_sha256,development_only:true,new_environment:0,new_training:0,measured_J:null,
 joint_choice_is_secondary_diagnostic:true,cross_arm_cost_difference_is_policy_saving:false,rows:derived};
fs.writeFileSync(path.join(out,'ANALYSIS.json'),JSON.stringify(value,null,2)+'\n',{flag:'wx'});
console.log(JSON.stringify({checks,aggregates,primary},null,2));
