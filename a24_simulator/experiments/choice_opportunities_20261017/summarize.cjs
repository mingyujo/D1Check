'use strict';
// Independent saved-only receipt/clock/capacity and opportunity reconciliation.
const fs=require('fs'),path=require('path'),zlib=require('zlib'),crypto=require('crypto');
const root=path.resolve(__dirname,'../..'),out=path.join(root,'results/CHOICE_OPPORTUNITIES_20261017_01');
const read=p=>JSON.parse(fs.readFileSync(p,'utf8'));
const sha=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
let checks=0;const need=(b,m)=>{checks++;if(!b)throw Error(m);};
const result=read(path.join(out,'RESULT.json')),terminal=read(path.join(out,'COMPLETE.json'));
need(sha(path.join(out,'RESULT.json'))===terminal.result_sha256,'Terminal result SHA');
const op=read(path.join(__dirname,'OPERATION.json'));
for(const p of [...op.sources,op.inputs,op.budget,op.cost_model,op.registration])need(sha(p.path)===p.sha256&&fs.statSync(p.path).size===p.bytes,'Frozen source/input pin');
const receipts=fs.readFileSync(path.join(out,'receipts.jsonl'),'utf8').trim().split(/\r?\n/).map(JSON.parse);
const starts=receipts.filter(r=>r.event==='START'),ends=receipts.filter(r=>r.event==='COMPLETE');
need(starts.length===24&&ends.length===24&&!receipts.some(r=>r.event==='FAIL'),'All 24 terminal exactly once');
need(new Set(starts.map(r=>r.identity)).size===24,'Unique START identities');
for(const row of result.rows){
 const label=row.case+'_'+row.policy,file=path.join(out,label+'.json'),raw=path.join(out,label+'.raw.json.gz');
 const receipt=ends.find(r=>r.label===label);
 need(sha(file)===receipt.result_sha256&&sha(raw)===receipt.raw_sha256&&sha(raw)===row.raw_sha256,'Output links');
 const data=JSON.parse(zlib.gunzipSync(fs.readFileSync(raw))),q=data.prediction.requests;
 const decisions=data.prediction.decisions.filter(d=>d.action.kind==='DISPATCH');
 need(q.length===48&&decisions.length===48&&data.opportunities.length===48,'Census denominator');
 const done=new Set();let on=0,urgent=0;
 for(let i=0;i<decisions.length;i++){
  const d=decisions[i],t=d.time_ns,request=q.find(r=>r.request_id===d.action.request_id);
  const active=q.filter(r=>done.has(r.request_id)&&r.available_ns>t);
  need(active.length<2&&!active.some(r=>r.route===d.action.route),'One CPU and one GPU lane');
  const obs=data.opportunities[i];need(obs.time_ns===t,'Actual dispatch clock');
  need(obs.two_physical_routes===(active.length===0),'Both lanes free independently reconstructed');
  const ready=q.filter(r=>!done.has(r.request_id)&&r.queue_entry_ns!=null&&r.queue_entry_ns<=t);
  need(obs.requests_before===ready.length,'Ready queue/candidate census');
  need(obs.requests_after>=1&&obs.requests_after<=obs.requests_before,'Protected request count');
  need(request.dispatch_ns===t&&request.queue_entry_ns<=t&&t>=request.scheduled_arrival_ns,'Arrival and queue clocks');
  const response=request.task==='C'?request.output_ready_ns:request.persist_complete_ns;
  need(request.response_ns===response&&request.available_ns>=response,'Response and AVAILABLE boundaries');
  on+=Number(response<=request.deadline_ns);urgent+=Number(request.priority==='U'&&response<=request.deadline_ns);
  if(row.policy==='EDF'){
   const head=ready.sort((a,b)=>a.deadline_ns-b.deadline_ns||a.scheduled_arrival_ns-b.scheduled_arrival_ns||a.ordinal-b.ordinal)[0];
   const expected=active.some(r=>r.route==='CPU')?'GPU':'CPU';
   need(d.action.request_id===head.request_id&&d.action.route===expected,'Actual EDF CPU-first rule');
  }
  done.add(request.request_id);
 }
 need(on===row.metrics.on_time&&urgent===row.metrics.urgent_on_time,'Deadline totals');
 const o=row.opportunities;
 need(o.two_free_routes===data.opportunities.filter(x=>x.two_physical_routes).length,'Two-free aggregate');
 need(o.multiple_requests_after===data.opportunities.filter(x=>x.requests_after>1).length,'Multiple requests exclude WAIT/routes');
}
function aggregate(policy,arm){
 const v=result.rows.filter(r=>r.policy===policy&&r.arm===arm),s=k=>v.reduce((a,r)=>a+r.opportunities[k],0),n=s('decision_opportunities');
 return {policy,arm,conditions:v.length,dispatch:n,multiple_requests_before:s('multiple_requests_before'),
  multiple_requests_after:s('multiple_requests_after'),two_free_routes:s('two_free_routes'),
  multiple_request_percent:100*s('multiple_requests_after')/n,two_free_percent:100*s('two_free_routes')/n,
  protection_removed_actions:s('removed_actions'),critical_dispatch:s('critical_focus'),
  on_time:v.reduce((s,r)=>s+r.metrics.on_time,0),urgent_on_time:v.reduce((s,r)=>s+r.metrics.urgent_on_time,0),
  responded:v.reduce((s,r)=>s+r.metrics.responded,0),AVAILABLE_by_window_end:v.reduce((s,r)=>s+r.metrics.AVAILABLE_by_window_end,0),
  mean_total_J_proxy:v.reduce((s,r)=>s+r.metrics.total_J_proxy,0)/v.length,
  mean_increment_J_proxy:v.reduce((s,r)=>s+r.metrics.increment_J_proxy,0)/v.length,
  mean_AP_c:v.reduce((s,r)=>s+r.metrics.mean_AP_c,0)/v.length,
  mean_window_s:v.reduce((s,r)=>s+r.metrics.duration_s,0)/v.length};
}
const aggregates=op.policies.flatMap(p=>['REFERENCE','PACKET'].map(a=>aggregate(p,a)));
const outcomes=op.policies.map(policy=>{const a=aggregates.find(r=>r.policy===policy&&r.arm==='REFERENCE'),b=aggregates.find(r=>r.policy===policy&&r.arm==='PACKET');
 return {policy,multiple_request_gain_pp:b.multiple_request_percent-a.multiple_request_percent,
  two_free_gain_pp:b.two_free_percent-a.two_free_percent,
  primary_PASS:b.multiple_request_percent-a.multiple_request_percent>=10&&b.two_free_percent-a.two_free_percent>=10};});
const value={schema:'A24-choice-opportunity-analysis-v1',status:'PASS_SAVED_RECONCILIATION',checks,aggregates,outcomes,
 all_primary_PASS:outcomes.every(r=>r.primary_PASS),result_sha256:terminal.result_sha256,
 new_environment:0,NN_training:0,measured_J:null,
 cross_arm_cost_delta_is_policy_saving:false,development_only:true,
 per_pair:result.rows.map(r=>({case:r.case,policy:r.policy,opportunities:r.opportunities,metrics:r.metrics}))};
fs.writeFileSync(path.join(out,'ANALYSIS.json'),JSON.stringify(value,null,2)+'\n',{flag:'wx'});
console.log(JSON.stringify({checks,aggregates,outcomes},null,2));
