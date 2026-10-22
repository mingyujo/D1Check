'use strict';
// Saved-only independent service/physics/cost accounting. Never calls an engine.
const fs=require('fs'),path=require('path'),z=require('zlib'),crypto=require('crypto');
const R=path.resolve(__dirname,'../../..'),O=path.join(R,'a24_simulator/results/A24_BC_S26_REQUESTS_20261021_01');
const read=p=>JSON.parse(p.endsWith('.gz')?z.gunzipSync(fs.readFileSync(p)):fs.readFileSync(p)),save=(n,x)=>fs.writeFileSync(path.join(O,n),JSON.stringify(x,null,2)+'\n',{flag:'wx'});
const {step,integral}=require('../a24_s26_method_20261019/audit.cjs');
let checks=0,maxerr=0;function ok(v,m){checks++;if(!v)throw Error(m);}function near(a,b,m,tol=3e-7){maxerr=Math.max(maxerr,Math.abs(a-b));ok(Number.isFinite(a)&&Number.isFinite(b)&&Math.abs(a-b)<=tol,m+': '+a+' vs '+b);}
function service(qs){const result={};for(const g of ['ALL','U','N']){const rows=qs.filter(q=>g==='ALL'||q.priority===g),answered=rows.filter(q=>q.response_ns!==null),lat=answered.map(q=>(q.response_ns-q.scheduled_arrival_ns)/1e9).sort((a,b)=>a-b);result[g]={n:rows.length,on:answered.filter(q=>q.response_ns<=q.deadline_ns).length,missing:rows.length-answered.length,incomplete:rows.filter(q=>q.available_ns===null).length,P95:lat.length?lat[Math.ceil(.95*lat.length)-1]:null,latencies:lat};}return result;}
function dominance(a,b){const ta=[...a.cost,a.AP_end,a.peak],tb=[...b.cost,b.AP_end,b.peak];let strict=false;for(let k=0;k<7;k++){const t=1e-9+1e-9*Math.max(Math.abs(ta[k]),Math.abs(tb[k]));if(ta[k]>tb[k]+t)return false;if(ta[k]<tb[k]-t)strict=true;}return strict;}
function checkGuard(s,c){
 const mask=c.physical_mask.slice();if(!s.owners.length)for(let i=0;i<c.actions.length;i++)if(c.actions[i].kind==='WAIT')for(let j=0;j<c.actions.length;j++)if(c.actions[j].kind==='DISPATCH'){
  const a=c.forecasts[j],b=c.forecasts[i];if(!a.capped&&!b.capped&&a.comparison_complete&&b.comparison_complete&&Math.abs(a.H_s-b.H_s)<=1e-8&&JSON.stringify([...a.visible_ids].sort())===JSON.stringify([...b.visible_ids].sort())&&dominance(a,b)){mask[i]=false;break;}
 }ok(JSON.stringify(mask)===JSON.stringify(c.mask),'Independent idle WAIT mask');
}
const result=read(path.join(O,'RESULT.json')),inputs=read(path.join(__dirname,'INPUTS.json')),op=read(path.join(__dirname,'OPERATION.json'));
for(const p of op.source_pins){const f=path.join(R,p.path),b=fs.readFileSync(f);ok(b.length===p.bytes&&crypto.createHash('sha256').update(b).digest('hex')===p.sha256,'Source/input pin '+p.path);}
const receipts=fs.readFileSync(path.join(O,'receipts.jsonl'),'utf8').trim().split('\n').map(JSON.parse),starts=receipts.filter(r=>r.event==='START');ok(starts.length<=20&&starts.length===result.science_START,'Bounded START census');ok(new Set(starts.map(r=>r.start_id)).size===starts.length,'Unique START identities');for(const r of starts)ok(receipts.filter(v=>v.start_id===r.start_id&&['COMPLETE','FAIL'].includes(v.event)).length===1,'One terminal record per START');
const newRows=result.rows,all=newRows;ok(all.length===20,'All five policies / four cases');
let phaseChecks=0,callChecks=0;const physical=[];
for(const row of newRows.filter(r=>r.status==='COMPLETE')){
 const d=read(path.join(R,row.raw.path)),r=d.result,work=new Map;let previous=null;
 for(const t of r.trace){
  ok(t.end_ns>t.start_ns,'Positive clock');if(previous)ok(t.start_ns===previous.end_ns,'Contiguous integration');previous=t;
  ok(t.active.filter(q=>q.route==='CPU').length<=3&&t.active.filter(q=>q.route==='GPU').length<=1,'CPU3/GPU1');const a=step(t.state,t.active,t.dt,r.config,'ORIGINAL');near(a.state.temperature_c,t.next_state.temperature_c,'T');near(a.state.shared_z,t.next_state.shared_z,'Tail');near(a.J,t.increment,'J');near(a.H,t.temperature_area,'H');phaseChecks+=4;
  for(const q of t.active){near(a.rates[q.request_id],t.speeds[q.request_id],'Progress rate',1e-12);const k=q.request_id+'|'+q.stage;work.set(k,(work.get(k)||0)+t.dt*a.rates[q.request_id]);}
 }
 const bank=read(path.join(R,row.bank.path)),jobs=new Map(bank.jobs.map(q=>[q.request_id,q]));
 for(const q of r.requests){const b=jobs.get(q.request_id);ok(q.queue_entry_ns===b.queue_entry_ns&&q.scheduled_arrival_ns===b.scheduled_arrival_ns&&q.deadline_ns===b.deadline_ns,'Frozen arrival/deadline/admission');if(q.route)ok(JSON.stringify(q.timing.stages_ns)===JSON.stringify(b.routes[q.route].stages_ns),'Immutable realized work');if(q.available_ns!==null){for(let k=0;k<5;k++)near(work.get(q.request_id+'|'+k)||0,q.timing.stages_ns[k]/1e9,'Conserved phase work',8e-9);ok(q.response_ns===(q.task==='C'?q.output_ready_ns:q.persist_complete_ns),'Response boundary');}}
 ok(d.calls.length===r.decisions.length,'Every decision saved');
 for(let i=0;i<d.calls.length;i++){
  const c=d.calls[i],s=r.decisions[i].public_state;if(row.policy.endsWith('_DYN')){ok(JSON.stringify(c.action)===JSON.stringify(r.decisions[i].action),'Baseline action saved');ok(c.future_information===false&&c.voluntary_WAIT===false,'Public baseline without voluntary WAIT');callChecks++;continue;}const allowed=c.actions.map((_,k)=>k).filter(k=>c.mask[k]);ok(c.mask[c.chosen]&&JSON.stringify(c.action)===JSON.stringify(c.actions[c.chosen])&&JSON.stringify(c.action)===JSON.stringify(r.decisions[i].action),'Legal selected action');checkGuard(s,c);
  if(row.policy==='TEACHER')ok(c.chosen===allowed.reduce((a,b)=>c.forecast_scores[b]<c.forecast_scores[a]?b:a),'Teacher minimum');
  const ids=new Set([...s.queue,...s.owners].map(q=>q.request_id));ok(s.queue.every(q=>q.queue_entry_ns<=s.now_ns),'Ready observations only');
  for(let j=0;j<c.actions.length;j++){const f=c.forecasts[j],score=f.cost[0]/.35+f.cost[1]+12*f.cost[2]+6*f.cost[3]+3*f.cost[4];near(Math.fround(score),c.forecast_scores[j],'Teacher cost formula',1e-5);ok(f.no_future_arrivals&&f.no_future_latents&&f.visible_ids.every(id=>ids.has(id)),'No hidden request');near(f.H_s,c.forecasts[0].H_s,'Same candidate horizon',1e-8);}
  callChecks++;
 }
 physical.push({label:row.label,trace_segments:r.trace.length,calls:d.calls.length});console.log('SAVED_AUDIT',row.label,d.calls.length);
}
const metadata=[];
for(const row of all){
 if(row.status!=='COMPLETE'){metadata.push({...row,common:null,service:null});continue;}
 const d=read(path.join(R,row.raw.path)),r=d.result,svc=service(r.requests);ok(svc.ALL.on===row.metrics.on_time&&svc.U.on===row.metrics.urgent_on_time,'Independent service');
 metadata.push({label:row.label,case:row.case,policy:row.policy,load:row.condition.rate_multiplier,pattern:row.condition.pattern_index,status:row.status,reused:!!row.reused,raw:row.raw,service:svc,finish_ns:r.requests.every(q=>q.available_ns!==null)?Math.max(d.case.supply_stop_s*1e9,...r.requests.map(q=>q.available_ns)):null,supply_stop_ns:d.case.supply_stop_s*1e9,drain_stop_ns:d.case.drain_stop_s*1e9,wait_s:r.wait_used_ns/1e9,max_queue:Math.max(...r.decisions.map(q=>q.public_state.queue.length)),route_counts:Object.fromEntries(['CPU','GPU'].map(route=>[route,r.requests.filter(q=>q.route===route).length])),calls:d.calls.length});
}
for(const row of metadata.filter(r=>r.status==='COMPLETE')){
 const peers=metadata.filter(r=>r.case===row.case),end=peers.every(r=>r.status==='COMPLETE'&&r.finish_ns!==null)?Math.max(row.supply_stop_ns,...peers.map(r=>r.finish_ns)):row.drain_stop_ns;
 const d=read(path.join(R,row.raw.path));ok(d.result.trace.at(-1).end_ns>=end,'Common window covered');row.common_end_ns=end;row.common=integral(d.result,'ORIGINAL',end);row.supply=integral(d.result,'ORIGINAL',row.supply_stop_ns);
}
const aggregates=[];
for(const load of [1,4])for(const policy of ['FIFO_DYN','EDF_DYN','RR_DYN','TEACHER','BC_RECOVERED']){
 const rows=metadata.filter(r=>r.load===load&&r.policy===policy),complete=rows.length===2&&rows.every(r=>r.status==='COMPLETE'&&r.common);const svc={};for(const g of ['ALL','U','N']){const lat=rows.filter(r=>r.service).flatMap(r=>r.service[g].latencies).sort((a,b)=>a-b);svc[g]={n:rows.reduce((a,r)=>a+(r.service?.[g].n??0),0),on:rows.reduce((a,r)=>a+(r.service?.[g].on??0),0),missing:rows.reduce((a,r)=>a+(r.service?.[g].missing??0),0),incomplete:rows.reduce((a,r)=>a+(r.service?.[g].incomplete??0),0),P95:lat.length?lat[Math.ceil(.95*lat.length)-1]:null};}
 aggregates.push({load,policy,status:complete?'COMPLETE':'PARTIAL',patterns:rows.length,J:complete?rows.reduce((a,r)=>a+r.common.J,0)/2:null,AP:complete?rows.reduce((a,r)=>a+r.common.AP,0)/2:null,peak:complete?Math.max(...rows.map(r=>r.common.peak)):null,service:svc,wait_s:complete?rows.reduce((a,r)=>a+r.wait_s,0)/2:null,max_queue:Math.max(...rows.map(r=>r.max_queue??0))});
}
const deltas=[];for(const a of aggregates.filter(r=>r.policy==='BC_RECOVERED'&&r.status==='COMPLETE'))for(const b of aggregates.filter(r=>r.load===a.load&&r.policy!=='BC_RECOVERED'&&r.status==='COMPLETE'))deltas.push({load:a.load,reference:b.policy,energy_saving_J:b.J-a.J,energy_saving_percent:100*(1-a.J/b.J),AP_change_C:a.AP-b.AP,all_on_change_pp:100*(a.service.ALL.on/a.service.ALL.n-b.service.ALL.on/b.service.ALL.n),urgent_on_change_pp:100*(a.service.U.on/a.service.U.n-b.service.U.on/b.service.U.n),urgent_P95_change_s:a.service.U.P95-b.service.U.P95});
save('ACCOUNTING.json',{rows:metadata,aggregates,deltas,common_window_recomputed:true,old_results_rerun:0});save('AUDIT_JS.json',{status:'PASS',checks,max_abs_error:maxerr,independent_math_checks:phaseChecks,decision_checks:callChecks,physical,new_environment:0,new_fit:0});console.log('AUDIT_PASS',checks);
