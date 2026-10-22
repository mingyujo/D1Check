'use strict';
// Saved results only: independent physics superposition and resource arithmetic.
const fs=require('fs'),path=require('path'),z=require('zlib'),crypto=require('crypto'),H=__dirname,R=path.resolve(H,'../..'),O=path.join(H,'artifacts/G001');
const read=p=>JSON.parse((p.endsWith('.gz')?z.gunzipSync(fs.readFileSync(p)):fs.readFileSync(p)).toString('utf8').replace(/^\uFEFF/,'')),sha=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex'),write=(p,x)=>fs.writeFileSync(p,JSON.stringify(x,null,2)+'\n',{flag:'wx'});
const result=read(path.join(O,'RESULT.json')),op=read(path.join(H,'OPERATION.json')),cases=read(path.join(H,'INPUTS.json')).cases,receipts=fs.readFileSync(path.join(O,'receipts.jsonl'),'utf8').trim().split(/\r?\n/).map(JSON.parse);
write(path.join(H,'AUDIT_OPERATION.json'),{utc:new Date().toISOString(),new_environment:0,pins:[__filename,path.join(O,'RESULT.json'),path.join(O,'receipts.jsonl')].map(p=>({path:p,sha256:sha(p)}))});
const pm=read(path.join(R,'experiments/capacity_power_v1/artifacts/G001/MODEL.json')),tm=read(path.join(R,'experiments/pipeline_thermal_v1/artifacts/G001/MODEL.json')),{coupled,steps}=require('../thermal_review_v3/cascade.cjs');
let checks=0,requests=0,maxAP=0,maxPower=0,maxJ=0,maxGrant=0;
const need=(ok,msg)=>{checks++;if(!ok)throw Error(msg)},byInput=new Map;
need(result.START===114&&result.COMPLETE===114&&result.FAIL===0,'Full finite114 census');
for(const event of ['START','COMPLETE'])need(receipts.filter(r=>r.event===event).length===114,'Receipt census '+event);
need(!receipts.some(r=>r.event==='FAIL'),'No hidden failed rows');
need(new Set(result.rows.map(r=>r.label)).size===114,'No duplicate labels');
for(const p of op.pins)need(sha(p.path)===p.sha256,'Frozen dependency '+p.path);

let eventActions=0,preferenceAssignments=0;
function eventAudit(row,raw){
 let dose=0;const planned=new Map(raw.planned_requests.map(q=>[q.ordinal,q]));
 for(const d of raw.policy_decisions){
  if(d.action.kind==='WAIT')dose+=d.action.wait_s;
  if(d.action.kind==='WAIT_EVENT'){
   eventActions++;need(Number.isFinite(d.wait_end)&&d.wait_end>=d.time-1e-9,'Event wait endpoint');dose+=d.wait_end-d.time;
   const owners=raw.requests.filter(q=>q.route&&q.times.dispatch<=d.time+1e-9&&(q.available===null||q.available>d.time+1e-9));
   const expected=Math.min(raw.dispatch_stop_s,...owners.map(q=>q.available??raw.observation_end_s),...raw.planned_requests.filter(q=>q.readyAt>d.time+1e-9).map(q=>q.readyAt));
   need(owners.length>0||d.wait_end-d.time<1e-8,'Event requires active work');need(Math.abs(d.wait_end-expected)<1e-7,'Wait ends at first observable ready/release/dispatch-stop event');
  }
 }
 need(Math.abs(dose-row.wait_s)<1e-6,'Fixed/event wait total');
 const ctx=raw.route_context_evidence;if(!ctx)return;
 const seen=new Set;for(const t of ctx.task_seen){need(!seen.has(t.ordinal),'Unique public task observation');seen.add(t.ordinal);need(planned.get(t.ordinal).readyAt<=t.time+1e-8,'No future task visibility');need(planned.get(t.ordinal).task===t.task,'Observed task identity');}
 let classes=0;const assigned=new Set;
 for(const p of ctx.preferences){
  preferenceAssignments++;need(!assigned.has(p.ordinal),'Unique preference assignment');assigned.add(p.ordinal);
  const history=ctx.task_seen.filter(t=>t.time<=p.time).slice(-64),mix=history.length<16?.75:history.filter(t=>t.task==='classification').length/history.length;
  need(history.some(t=>t.ordinal===p.ordinal)||ctx.task_seen.some(t=>t.ordinal===p.ordinal&&t.time<=p.time+1e-9),'Preference after public observation');need(p.seen_count===history.length&&Math.abs(p.observed_mix-mix)<1e-10,'Causal recent64 mix');
  let expected='detection_CPU';if(planned.get(p.ordinal).task==='classification'){expected=mix<=.625?'classification_NPU':classes%4===3?'classification_GPU':'classification_NPU';classes++;}
  need(p.route===expected&&p.class_counter===classes,'Causal preference feature, no deadline input');
 }
}

for(const row of result.rows){
 const rawfile=path.join(O,row.label+'.raw.json.gz');need(sha(rawfile)===row.raw_sha256,'Raw SHA '+row.label);const raw=read(rawfile),c=cases.find(c=>c.id===row.input),ctx=c.context.initial_context.targets,K=row.model==='CPU3'?3:1;
 need(raw.requests.length===c.n,'All arrivals denominator');requests+=c.n;
 const original=new Map(c.requests.map(q=>[q.ordinal,q]));
 for(const q of raw.requests){const p=original.get(q.ordinal);need(q.arrival===p.offset_ns/1e9,'Preserved arrival');need(Math.abs(q.deadline-q.arrival-p.deadline_ms/1000)<1e-9,'Preserved deadline');need(q.task!=='detection'||q.route==='detection_CPU'||q.route===null,'Detection support');if(q.route){need(q.route.startsWith(q.task+'_'),'Supported route');need(q.times.dispatch>=q.arrival-1e-9,'Causal dispatch');if(q.response!==null)need(Math.abs(q.response-(q.priority==='urgent'?q.times.output_ready:q.times.readback_end))<1e-8,'Actual response boundary');}}
 const cpu=[];for(const g of raw.cpu_intervals){need(g.end>=g.start,'Nonnegative CPU grant');cpu.push([g.start,1],[g.end,-1]);}cpu.sort((a,b)=>a[0]-b[0]||a[1]-b[1]);let active=0,previous=35,extra=0;
 for(const[t,d]of cpu){if(t>previous)extra+=(t-previous)*Math.max(0,active-1);active+=d;need(active>=0&&active<=K,'CPU concurrency cap');maxGrant=Math.max(maxGrant,active);previous=t;}
 need(active===0,'All grants closed');if(raw.extra_cpu_core_s!==undefined)need(Math.abs(extra-raw.extra_cpu_core_s)<1e-6,'Extra CPU core-time integral');
 if(K===3)need(raw.shared_cpu_wait_s<1e-7,'CPU3 service work progresses without serialized wait');
 const ev=[];for(const q of raw.requests)if(q.route){ev.push([q.times.dispatch,1,q.route.split('_').at(-1)]);ev.push([q.available??raw.observation_end_s,-1,q.route.split('_').at(-1)]);}ev.sort((a,b)=>a[0]-b[0]||a[1]-b[1]);const slots={CPU:0,GPU:0,NPU:0};for(const[t,d,s]of ev){slots[s]+=d;need(slots[s]>=0&&slots[s]<=1,'Resource slot until AVAILABLE');need(Object.values(slots).reduce((a,b)=>a+b,0)<=3,'Owner capacity');}
 for(const pr of ['all','urgent','normal']){const qs=raw.requests.filter(q=>pr==='all'||q.priority===pr),responded=qs.filter(q=>q.response!==null),dt=responded.map(q=>q.response-q.arrival).sort((a,b)=>a-b);need(qs.length===row.service[pr].planned,'Class denominator');need(responded.length===row.service[pr].completed,'Class completion');need(responded.filter(q=>q.response<=q.deadline+1e-9).length===row.service[pr].on_time,'Class ontime');need(Math.abs((dt[Math.ceil(.95*dt.length)-1]??0)-(row.service[pr].p95_s??0))<1e-8,'Response P95');}
 if(row.mode==='EDF_GPU_FIRST'){const select=require('../plain_edf_v1/select.cjs').select;for(const d of raw.policy_decisions){const a=select(d.public_observation,['GPU','NPU','CPU']);need(a.ordinal===d.action.ordinal&&a.route===d.action.route,'Plain EDF independently reproduced');}}
 const times=[...new Set([0,35,raw.observation_end_s,...raw.curve.map(x=>x[0])])].sort((a,b)=>a-b),a=ctx.AP.anchor,reference=coupled(steps(raw.activity),times,ctx.POWER_API.baseline.median_api_w,0,a.AP,a.SKIN,pm,tm),lookup=new Map(times.map((t,i)=>[t,reference[i]]));
 for(const[t,AP,P]of raw.curve){const x=lookup.get(t);maxAP=Math.max(maxAP,Math.abs(AP-x[1]));maxPower=Math.max(maxPower,Math.abs(P-x[0]));checks+=2;}
 const J=lookup.get(raw.observation_end_s)[2]-lookup.get(0)[2];maxJ=Math.max(maxJ,Math.abs(J-row.J));need(Math.abs(J-row.J)<1e-6,'Independent whole-observation energy');
 need(Math.abs(raw.integrals.reduce((s,x)=>s+x[3],0)/(raw.observation_end_s-35)-row.AP_mean)<1e-8,'AP time mean');need(row.physical_validation===false,'No physical certification');
 if(['DEV','EVAL'].includes(row.kind)){const key=row.kind+'|'+row.model+'|'+row.input;if(!byInput.has(key))byInput.set(key,[]);byInput.get(key).push(row);}
 eventAudit(row,raw);
 if((result.rows.indexOf(row)+1)%50===0)console.log('SAVED_AUDIT',result.rows.indexOf(row)+1,checks);
}
for(const rr of byInput.values()){need(rr.length===9,'All9 policies per input/scenario');const times=rr.map(r=>r.observation_s);need(Math.max(...times)-Math.min(...times)<1e-8,'Same observation window');}
need(maxAP<1e-7&&maxPower<1e-7,'Independent superposition accuracy');
const freeze=read(path.join(O,'SELECTION_FROZEN.json')),freezeHash=sha(path.join(O,'SELECTION_FROZEN.json'));need(receipts.filter(r=>r.kind==='EVAL').every(r=>r.selection_sha256===freezeHash),'Frozen before fresh EVAL');need(freeze.utc<receipts.find(r=>r.kind==='EVAL').utc,'Time order DEV freeze');
write(path.join(O,'AUDIT.json'),{status:'PASS_SAVED_CONCURRENCY_SERVICE_AND_INDEPENDENT_PHYSICS',utc:new Date().toISOString(),cases:114,request_count:requests,checks,max_AP_error_C:maxAP,max_power_error_API_W:maxPower,max_energy_error_API_J:maxJ,max_actual_CPU_grants:maxGrant,event_wait_actions:eventActions,causal_preference_assignments:preferenceAssignments,new_environment:0,new_training:0,physical_validation:false});
console.log('SAVED_AUDIT_PASS',checks,requests,maxAP,maxJ);
