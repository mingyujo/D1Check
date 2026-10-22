'use strict';
// Saved records only. No policy, environment, model forward, or training runs.
const fs=require('fs'),path=require('path'),z=require('zlib'),crypto=require('crypto'),assert=require('assert');
const H=__dirname,S=path.resolve(H,'../..'),P=path.resolve(H,'../route_group_learning_v1'),O=path.join(H,'artifacts/G001');
const read=p=>JSON.parse((p.endsWith('.gz')?z.gunzipSync(fs.readFileSync(p)):fs.readFileSync(p)).toString('utf8').replace(/^\uFEFF/,''));
const sha=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
const save=(p,x)=>fs.writeFileSync(p,JSON.stringify(x,null,2)+'\n',{flag:'wx'});
const result=read(path.join(O,'RESULT.json')),op=read(path.join(H,'OPERATION.json')),cases=read(path.join(H,'INPUTS.json')).cases;
const {steps,coupled}=require('../thermal_review_v3/cascade.cjs');
const pm=read(path.join(S,'experiments/capacity_power_v1/artifacts/G001/MODEL.json')),tm=read(path.join(S,'experiments/pipeline_thermal_v1/artifacts/G001/MODEL.json'));
let checks=0,requests=0,dispatches=0,maxAP=0,maxP=0,maxJ=0,maxCPU=0;const need=(v,s)=>{checks++;if(!v)throw Error(s)};
save(path.join(H,'AUDIT_OPERATION.json'),{utc:new Date().toISOString(),scope:'16 saved records:4 new nonpreemptive queueRR plus12 reused FIFO/EDF/selected881087; independent pointer/queue ordering and saved physics; original NN audit binding',new_environment:0,pins:[__filename,path.join(O,'RESULT.json'),path.join(O,'receipts.jsonl'),path.join(H,'OPERATION.json')].map(p=>({path:p,sha256:sha(p)}))});
need(result.START===4&&result.COMPLETE===4&&result.FAIL===0&&result.REUSE===12&&result.rows.length===16,'Finite census');
for(const pin of op.pins)need(sha(pin.path)===pin.sha256,'Frozen input/source '+pin.path);
const receipts=fs.readFileSync(path.join(O,'receipts.jsonl'),'utf8').trim().split(/\r?\n/).map(JSON.parse);
for(const event of ['START','COMPLETE'])need(receipts.filter(x=>x.event===event).length===4,'Durable4 '+event);
need(receipts.filter(x=>x.event==='REUSE').length===12&&!receipts.some(x=>x.event==='FAIL'),'All reuse and no failed hidden runs');
need(new Set(receipts.filter(x=>x.event==='START').map(x=>x.identity)).size===4,'Unique new identities');
need(read(path.join(P,'artifacts/G001/NN_AUDIT.json')).status==='PASS_NUMPY_FORWARD_EXACT_ACTION_RNG_AND_ADAM_REPLAY','Original NN/BC/PPO replay proof');
need(read(path.join(P,'artifacts/G001/AUDIT.json')).status==='PASS_SAVED_CONCURRENCY_SERVICE_AND_INDEPENDENT_PHYSICS','Original saved plant audit proof');
const pairs=new Map;
function pure(row,raw){
 need(raw.forecast_calls===0&&raw.wait_s===0,'Pure FIFO/EDF no forecasts or proactive WAIT');if(!row.reused_environment)need(raw.route_context_evidence.preferences.length===0,'New FIFO has no teacher preferences');
 const planned=raw.planned_requests,dispatched=new Set,byID=new Map(raw.requests.map(q=>[q.ordinal,q])),order=['GPU','NPU','CPU'];
 for(const d of raw.policy_decisions){
  const obs=d.public_observation,a=d.action;need(a.kind==='DISPATCH','Only dispatch');
  const ready=planned.filter(q=>q.readyAt<=d.time+1e-9&&!dispatched.has(q.ordinal));
  assert.deepStrictEqual(obs.ready.map(q=>q.ordinal).sort((a,b)=>a-b),ready.map(q=>q.ordinal).sort((a,b)=>a-b));checks++;
  const owners=raw.requests.filter(q=>dispatched.has(q.ordinal)&&(q.available===null||q.available>d.time+1e-9)),busy=owners.map(q=>q.route.split('_').at(-1));
  assert.deepStrictEqual(obs.owners.map(q=>[q.ordinal,q.route]).sort((a,b)=>a[0]-b[0]),owners.map(q=>[q.ordinal,q.route]).sort((a,b)=>a[0]-b[0]));checks++;
  const options=ready.flatMap(q=>(q.task==='detection'?['CPU']:order).filter(r=>!busy.includes(r)).map(r=>({q,r}))).sort((a,b)=>(row.method==='EDF'?a.q.deadline-b.q.deadline:0)||a.q.arrival-b.q.arrival||a.q.ordinal-b.q.ordinal||order.indexOf(a.r)-order.indexOf(b.r));
  need(owners.length<3&&options.length>0,'Runnable physical queue');need(a.ordinal===options[0].q.ordinal&&a.route===options[0].q.task+'_'+options[0].r,'Independent FIFO/EDF ordering and fixed routing');dispatched.add(a.ordinal);dispatches++;
 }
 for(const n of raw.pure_no_action??[]){
  const active=raw.requests.filter(q=>q.route&&q.times.dispatch<=n.time+1e-9&&(q.available===null||q.available>n.time+1e-9)),busy=active.map(q=>q.route.split('_').at(-1));
  const ready=planned.filter(q=>{const r=byID.get(q.ordinal);return q.readyAt<=n.time+1e-9&&(!r.route||r.times.dispatch>n.time+1e-9)});
  for(const task of ['classification','detection'])need(ready.filter(q=>q.task===task).length===n.ready_counts[task],'No hidden ready job');
  need(active.length>=3||!ready.some(q=>(q.task==='detection'?['CPU']:order).some(r=>!busy.includes(r))),'No voluntary idle when runnable');
 }
 need(dispatched.size===raw.requests.filter(q=>q.route).length,'All dispatches tracked');
}

function auditRR(row,raw){
 need(raw.forecast_calls===0&&raw.wait_s===0&&raw.route_context_evidence.preferences.length===0,'RR no forecasts/teacher/proactive wait');
 const order=['GPU','NPU','CPU'],tasks=['classification','detection'],planned=raw.planned_requests,dispatched=new Set;let cursor=0,ix=0;
 for(const turn of raw.rr_turns){
  need(turn.before===cursor&&turn.capacity===3,'RR persisted cursor and capacity');const a=turn.action;
  const ready=planned.filter(q=>q.readyAt<=turn.time+1e-9&&!dispatched.has(q.ordinal)),owners=raw.requests.filter(q=>dispatched.has(q.ordinal)&&(q.available===null||q.available>turn.time+1e-9)),busy=owners.map(q=>q.route.split('_').at(-1));
  assert.deepStrictEqual(turn.ready.slice().sort((a,b)=>a-b),ready.map(q=>q.ordinal).sort((a,b)=>a-b));checks++;
  assert.deepStrictEqual(turn.owners.map(q=>[q.ordinal,q.route]).sort((a,b)=>a[0]-b[0]),owners.map(q=>[q.ordinal,q.route]).sort((a,b)=>a[0]-b[0]));checks++;
  const candidates=ready.flatMap(q=>(q.task==='detection'?['CPU']:order).filter(r=>!busy.includes(r)).map(r=>({q,r}))).sort((a,b)=>((tasks.indexOf(a.q.task)-cursor+2)%2)-((tasks.indexOf(b.q.task)-cursor+2)%2)||a.q.arrival-b.q.arrival||a.q.ordinal-b.q.ordinal||order.indexOf(a.r)-order.indexOf(b.r));
  if(owners.length>=3||!candidates.length)need(a.kind==='NONE'&&turn.after===cursor&&a.rr_next===cursor,'NONE only when no executable queue, preserve pointer');
  else{
   const q=candidates[0].q,r=candidates[0].r;need(a.kind==='DISPATCH'&&a.ordinal===q.ordinal&&a.route===q.task+'_'+r,'Independent work-conserving queue RR and FIFO inside queue');cursor=1-tasks.indexOf(q.task);need(turn.after===cursor&&a.rr_next===cursor,'Advance pointer after successful dispatch');
   const d=raw.policy_decisions[ix++];need(d&&d.time===turn.time&&d.action.ordinal===a.ordinal&&d.action.route===a.route,'Every dispatched action matches RR trace');dispatched.add(a.ordinal);dispatches++;
  }
 }
 need(ix===raw.policy_decisions.length&&dispatched.size===raw.requests.filter(q=>q.route).length,'All RR decisions and requests accounted');
}

for(const row of result.rows){
 const c=cases.find(x=>x.id===row.input),rawpath=path.join(O,row.label+'.raw.json.gz');need(c&&c.stream===row.stream,'Same registered input and latent stream');need(sha(rawpath)===row.raw_sha256,'Raw SHA');
 if(row.reused_environment){const proof=row.reuse_proof;need(sha(proof.row_path)===proof.row_sha256&&sha(proof.raw_path)===proof.raw_sha256&&sha(rawpath)===proof.raw_sha256,'Exact original bytes, no rerun');const old=read(proof.row_path);for(const k of ['input','seed','J','AP_mean','AP_peak','unfinished','network_sha256'])need(row[k]===old[k],'Old metrics unchanged '+k);}
 const raw=read(rawpath),ctx=c.context.initial_context.targets;requests+=c.n;need(raw.requests.length===c.n&&raw.cpu_workers===3,'Same complete arrivals and CPU3');need(raw.routing_contract.nonpreemptive&&raw.routing_contract.reserve_until==='AVAILABLE','Same reservation boundary');
 const original=new Map(c.requests.map(q=>[q.ordinal,q]));
 for(const q of raw.requests){const p=original.get(q.ordinal);need(q.arrival===p.offset_ns/1e9,'Same arrival');need(Math.abs(q.deadline-q.arrival-p.deadline_ms/1000)<1e-9,'Same deadline');need(q.task===p.task_id&&q.priority===p.priority,'Same request class');need(q.task!=='detection'||q.route===null||q.route==='detection_CPU','Detection CPU only');if(q.route){need(q.times.dispatch>=q.arrival-1e-9,'Causal dispatch');if(q.response!==null)need(Math.abs(q.response-(q.priority==='urgent'?q.times.output_ready:q.times.readback_end))<1e-8,'Same response boundary');}}
 for(const pr of ['all','urgent','normal']){const qs=raw.requests.filter(q=>pr==='all'||q.priority===pr),done=qs.filter(q=>q.response!==null),lat=done.map(q=>q.response-q.arrival).sort((a,b)=>a-b);need(qs.length===row.service[pr].planned,'All-arrival denominator');need(done.length===row.service[pr].completed,'Response completion');need(done.filter(q=>q.response<=q.deadline+1e-9).length===row.service[pr].on_time,'Ontime numerator');need(Math.abs((lat[Math.ceil(.95*lat.length)-1]??0)-(row.service[pr].p95_s??0))<1e-8,'P95 definition');}
 need(raw.requests.filter(q=>q.available===null).length===row.unfinished,'Unfinished included');
 const grants=raw.cpu_intervals.flatMap(g=>[[g.start,1],[g.end,-1]]).sort((a,b)=>a[0]-b[0]||a[1]-b[1]);let active=0,last=35,extra=0;for(const[t,d]of grants){if(t>last)extra+=(t-last)*Math.max(0,active-1);active+=d;need(active>=0&&active<=3,'CPU3 bound');maxCPU=Math.max(maxCPU,active);last=t;}need(active===0&&Math.abs(extra-row.extra_cpu_core_s)<1e-6,'Extra core integral');
 const events=raw.requests.filter(q=>q.route).flatMap(q=>[[q.times.dispatch,1,q.route.split('_').at(-1)],[q.available??raw.observation_end_s,-1,q.route.split('_').at(-1)]]).sort((a,b)=>a[0]-b[0]||a[1]-b[1]);const slots={CPU:0,GPU:0,NPU:0};for(const[t,d,s]of events){slots[s]+=d;need(slots[s]>=0&&slots[s]<=1&&Object.values(slots).reduce((a,b)=>a+b,0)<=3,'Same slots and max owners until AVAILABLE');}
 const times=[...new Set([0,35,raw.observation_end_s,...raw.curve.map(x=>x[0])])].sort((a,b)=>a-b),anchor=ctx.AP.anchor,reference=coupled(steps(raw.activity),times,ctx.POWER_API.baseline.median_api_w,0,anchor.AP,anchor.SKIN,pm,tm),lookup=new Map(times.map((t,i)=>[t,reference[i]]));
 for(const[t,AP,P]of raw.curve){const x=lookup.get(t);maxAP=Math.max(maxAP,Math.abs(AP-x[1]));maxP=Math.max(maxP,Math.abs(P-x[0]));checks+=2;}
 const J=lookup.get(raw.observation_end_s)[2]-lookup.get(0)[2];maxJ=Math.max(maxJ,Math.abs(J-row.J));need(Math.abs(J-row.J)<1e-6,'Independent total energy');need(Math.abs(raw.integrals.reduce((s,x)=>s+x[3],0)/(raw.observation_end_s-35)-row.AP_mean)<1e-8,'Time mean AP');need(Math.abs(Math.max(...raw.curve.map(x=>x[1]))-row.AP_peak)<1e-8,'Peak sampled AP');need(Math.abs(raw.baseline_API_W*raw.observation_end_s-row.baseline_J)<1e-8,'Baseline retained');
 need(row.physical_validation===false,'No physical validation relabeling');
 if(['FIFO','EDF'].includes(row.method))pure(row,raw);else if(row.method==='OURS')need(row.seed===881087&&row.network_sha256==='3d7a54534146fef5da8b12782e8c6e46005e8aff91bd9329910ebd8a89dd4c31','Exact selected actor');else if(row.method==='RR')auditRR(row,raw);else need(false,'Unknown method');
 const planned=raw.planned_requests.map(({completed,...q})=>q);if(!pairs.has(c.id))pairs.set(c.id,{window:row.observation_s,planned,methods:[]});const pair=pairs.get(c.id);assert.deepStrictEqual(pair.planned,planned);need(pair.window===row.observation_s,'Identical observation window');pair.methods.push(row.method);console.log('FOUR_RR_SAVED_AUDIT',result.rows.indexOf(row)+1,checks);
}
for(const pair of pairs.values())assert.deepStrictEqual(pair.methods.slice().sort(),['EDF','FIFO','OURS','RR']);
need(pairs.size===4&&maxAP<1e-7&&maxP<1e-7,'All matched cohorts and independent physics');
const proof={status:'PASS',utc:new Date().toISOString(),cases:16,request_count:requests,checks,pure_dispatches:dispatches,max_AP_error_C:maxAP,max_power_error_API_W:maxP,max_energy_error_API_J:maxJ,max_CPU_grants:maxCPU,new_environment:0,new_training:0,new_RR_evaluations_audited:4,original_FIFO_EDF_selected_NN_reuse:12,physical_validation:false};
save(path.join(O,'AUDIT.json'),proof);console.log('FOUR_RR_SAVED_AUDIT_PASS',JSON.stringify(proof));
