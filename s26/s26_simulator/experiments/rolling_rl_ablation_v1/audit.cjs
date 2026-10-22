'use strict';
// Saved records only; independent analytic physics and selector arithmetic.
const fs=require('fs'),path=require('path'),z=require('zlib'),crypto=require('crypto'),readline=require('readline'),assert=require('assert'),H=__dirname,R=path.resolve(H,'../..'),O=path.join(H,'artifacts/G001');
const read=p=>JSON.parse((p.endsWith('.gz')?z.gunzipSync(fs.readFileSync(p)):fs.readFileSync(p)).toString('utf8').replace(/^\uFEFF/,'')),sha=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex'),write=(p,x)=>fs.writeFileSync(p,JSON.stringify(x,null,2)+'\n',{flag:'wx'});
const {coupled,steps}=require('../thermal_review_v3/cascade.cjs');
const pm=read(path.join(R,'experiments/capacity_power_v1/artifacts/G001/MODEL.json')),tm=read(path.join(R,'experiments/pipeline_thermal_v1/artifacts/G001/MODEL.json'));
const result=read(path.join(O,'RESULT.json')),op=read(path.join(H,'OPERATION.json')),inputs=read(path.join(H,'INPUTS.json')).cases,protocol=read(path.join(H,'PROTOCOL.json'));
write(path.join(H,'AUDIT_OPERATION.json'),{utc:new Date().toISOString(),scope:'All40 saved results and full bank traces; no new policy environment/training/fit',pins:[__filename,path.join(O,'RESULT.json'),path.join(O,'receipts.jsonl'),path.join(H,'OPERATION.json')].map(p=>({path:p,sha256:sha(p)}))});
let checks=0,requests=0,banks=0,waitEvents=0,neuralCalls=0,maxAP=0,maxP=0,maxJ=0,maxCPU=0;const need=(ok,msg)=>{checks++;if(!ok)throw Error(msg)},receipts=fs.readFileSync(path.join(O,'receipts.jsonl'),'utf8').trim().split(/\r?\n/).map(JSON.parse);
const rules={
 ROLLING_COST:b=>{const ix=b.mask.flatMap((v,i)=>v?[i]:[]),low=Math.min(...ix.map(i=>b.scores[i]));return ix.filter(i=>b.scores[i]<=low+1e-12).sort((i,j)=>b.x[j][11]-b.x[i][11]||b.actions[i].ordinal-b.actions[j].ordinal||i-j)[0];},
 TEACHER_RULE:b=>{const ix=b.mask.flatMap((v,i)=>v?[i]:[]),pref=ix.filter(i=>b.actions[i].kind==='DISPATCH'&&b.x[i][31]>.5);return pref.length?pref.sort((i,j)=>b.x[i][8]-b.x[j][8]||b.actions[i].ordinal-b.actions[j].ordinal||i-j)[0]:ix.find(i=>b.actions[i].kind==='WAIT_EVENT');}
};
async function auditBanks(row,raw){
 let count=0,seenAt=0;const ctx=raw.route_context_evidence.task_seen,history=[];
 const stream=readline.createInterface({input:fs.createReadStream(path.join(O,row.label+'.banks.jsonl.gz')).pipe(z.createGunzip()),crlfDelay:Infinity});
 for await(const line of stream){const rec=JSON.parse(line),b=rec.bank,d=raw.policy_decisions[count++],a=b.actions[rec.index];banks++;
  need(Boolean(d),'Every saved bank has exactly one action');need(b.mask.length===27&&b.x.length===27&&b.actions.length<=27,'Same physical action ABI');need(b.x.every(x=>x.length===32&&x.every(Number.isFinite)),'Same feature ABI');
  need(b.constraints.physical_slots_only&&['deadline_action_mask','critical_request_override','fixed_ATC_prior','post_NN_override'].every(k=>b.constraints[k]===false),'No deadline guard or override');
  need(b.mask[rec.index]&&a.kind===d.action.kind&&a.ordinal===d.action.ordinal&&(a.route??null)===(d.action.route??null)&&(a.wait_s??null)===(d.action.wait_s??null),'No post-selector replacement');
  need(d.action.decision_index===rec.index,'Decision index recorded');need(Math.abs(b.time_ns/1e9-d.time)<1e-8,'Same decision clock');
  need(d.action.bank_digest===crypto.createHash('sha256').update(JSON.stringify({x:b.x,mask:b.mask})).digest('hex'),'Same original candidate-bank digest');
  while(seenAt<ctx.length&&ctx[seenAt].time<=d.time+1e-10){history.push(ctx[seenAt++]);if(history.length>64)history.shift();}
  const mix=history.length<16?.75:history.filter(t=>t.task==='classification').length/history.length;
  need(Math.abs(mix-b.public_recent_mix)<1e-12,'No future workload ratio in common cost');
  const scales=protocol.shared_scores.scales;
  for(let i=0;i<b.actions.length;i++){const c=b.forecasts[i].cost,score=c[0]/scales[0]+c[1]/scales[1]+.98*c[2]/Math.max(1/64,mix)+.98*c[3]/Math.max(1/64,1-mix)+3*c[4];need(Math.abs(score-b.scores[i])<1e-10,'Independent common objective score');need(b.mask[i],'Every constructed physical candidate remains selectable');}
  for(let i=b.actions.length;i<27;i++)need(!b.mask[i],'Only padding is masked');
  if(rules[row.method])need(rec.index===rules[row.method](b),'Independent no-network selector '+row.method);
  if(a.kind==='WAIT_EVENT'){
   waitEvents++;need(Number.isFinite(d.wait_end)&&d.wait_end>=d.time-1e-9,'Event wait endpoint');
   const owners=raw.requests.filter(q=>q.route&&q.times.dispatch<=d.time+1e-9&&(q.available===null||q.available>d.time+1e-9));
   const next=Math.min(raw.dispatch_stop_s,...owners.map(q=>q.available??raw.observation_end_s),...raw.planned_requests.filter(q=>q.readyAt>d.time+1e-9).map(q=>q.readyAt));
   need(owners.length>0||d.wait_end-d.time<1e-8,'Event requires active work');need(Math.abs(d.wait_end-next)<1e-7,'Same event wait wake-up rule');
  }
 }
 need(count===row.decisions&&count===raw.policy_decisions.length,'Full bank/action census');
 need(row.neural_calls===(row.seed===null?0:count),'No neural calls in no-RL rules');neuralCalls+=row.neural_calls;
}
async function main(){
 need(result.START===40&&result.COMPLETE===40&&result.FAIL===0,'Complete finite40 census');
 for(const type of ['START','COMPLETE'])need(receipts.filter(r=>r.event===type).length===40,'All durable receipts '+type);
 need(!receipts.some(r=>r.event==='FAIL'),'No hidden failed cases');need(new Set(receipts.filter(r=>r.event==='START').map(r=>r.identity)).size===40,'Unique START identities');
 for(const pin of op.pins)need(sha(pin.path)===pin.sha256,'Frozen source/checkpoint '+pin.path);
 const paired=new Map;
 for(const row of result.rows){
  const c=inputs.find(c=>c.id===row.input),rawpath=path.join(O,row.label+'.raw.json.gz');need(sha(rawpath)===row.raw_sha256,'Raw SHA');need(sha(path.join(O,row.label+'.banks.jsonl.gz'))===row.banks_sha256,'Full bank trace SHA');
  const raw=read(rawpath),ctx=c.context.initial_context.targets;requests+=c.n;need(raw.requests.length===c.n,'All arrivals included');need(raw.cpu_workers===3,'Same CPU3');
  need(raw.routing_contract.reserve_until==='AVAILABLE'&&raw.routing_contract.nonpreemptive,'Same resource contract');
  const original=new Map(c.requests.map(q=>[q.ordinal,q]));
  for(const q of raw.requests){const p=original.get(q.ordinal);need(q.arrival===p.offset_ns/1e9,'Same fixed arrival');need(Math.abs(q.deadline-q.arrival-p.deadline_ms/1000)<1e-9,'Same deadline');need(q.task!=='detection'||q.route===null||q.route==='detection_CPU','Same supported detection route');if(q.route){need(q.route.startsWith(q.task+'_'),'Supported task/route');need(q.times.dispatch>=q.arrival-1e-9,'Causal dispatch');if(q.response!==null)need(Math.abs(q.response-(q.priority==='urgent'?q.times.output_ready:q.times.readback_end))<1e-8,'Actual response boundary');}}
  for(const pr of ['all','urgent','normal']){const qs=raw.requests.filter(q=>pr==='all'||q.priority===pr),done=qs.filter(q=>q.response!==null),dt=done.map(q=>q.response-q.arrival).sort((a,b)=>a-b);need(qs.length===row.service[pr].planned,'All-arrival class denominator');need(done.length===row.service[pr].completed,'Class completion');need(done.filter(q=>q.response<=q.deadline+1e-9).length===row.service[pr].on_time,'Class ontime');need(Math.abs((dt[Math.ceil(.95*dt.length)-1]??0)-(row.service[pr].p95_s??0))<1e-8,'Completed-response P95');}
  need(raw.requests.filter(q=>q.available===null).length===row.unfinished,'Unavailable requests retained');
  const grants=[];for(const g of raw.cpu_intervals){need(g.end>=g.start,'Positive service grant');grants.push([g.start,1],[g.end,-1]);}grants.sort((a,b)=>a[0]-b[0]||a[1]-b[1]);let active=0,last=35,extra=0;
  for(const[t,d]of grants){if(t>last)extra+=(t-last)*Math.max(0,active-1);active+=d;need(active>=0&&active<=3,'CPU3 service bound');maxCPU=Math.max(maxCPU,active);last=t;}need(active===0&&Math.abs(extra-row.extra_cpu_core_s)<1e-6,'Extra-core time integral');
  const events=[];for(const q of raw.requests)if(q.route){events.push([q.times.dispatch,1,q.route.split('_').at(-1)]);events.push([q.available??raw.observation_end_s,-1,q.route.split('_').at(-1)]);}events.sort((a,b)=>a[0]-b[0]||a[1]-b[1]);const slots={CPU:0,GPU:0,NPU:0};for(const[t,d,s]of events){slots[s]+=d;need(slots[s]>=0&&slots[s]<=1,'Same route slots until AVAILABLE');need(Object.values(slots).reduce((a,b)=>a+b,0)<=3,'Same max owners3');}
  const times=[...new Set([0,35,raw.observation_end_s,...raw.curve.map(x=>x[0])])].sort((a,b)=>a-b),anchor=ctx.AP.anchor,reference=coupled(steps(raw.activity),times,ctx.POWER_API.baseline.median_api_w,0,anchor.AP,anchor.SKIN,pm,tm),lookup=new Map(times.map((t,i)=>[t,reference[i]]));
  for(const[t,AP,P]of raw.curve){const v=lookup.get(t);maxAP=Math.max(maxAP,Math.abs(AP-v[1]));maxP=Math.max(maxP,Math.abs(P-v[0]));checks+=2;}
  const J=lookup.get(raw.observation_end_s)[2]-lookup.get(0)[2];maxJ=Math.max(maxJ,Math.abs(J-row.J));need(Math.abs(J-row.J)<1e-6,'Independent whole-window total energy');
  need(Math.abs(raw.integrals.reduce((s,x)=>s+x[3],0)/(raw.observation_end_s-35)-row.AP_mean)<1e-8,'Time-mean AP');need(Math.abs(Math.max(...raw.curve.map(x=>x[1]))-row.AP_peak)<1e-8,'Same peak sample definition');
  need(Math.abs(raw.baseline_API_W*raw.observation_end_s-row.baseline_J)<1e-8,'Whole-window baseline included');need(row.physical_validation===false,'Preserved physical gate failure');
  const planned=raw.planned_requests.map(({completed,...q})=>q);if(!paired.has(row.input))paired.set(row.input,{window:row.observation_s,planned,methods:[]});const pair=paired.get(row.input);need(Math.abs(pair.window-row.observation_s)<1e-8,'Same observation window');assert.deepStrictEqual(pair.planned,planned);pair.methods.push(row.method);checks++;
  await auditBanks(row,raw);console.log('FAIR_SAVED_AUDIT',result.rows.indexOf(row)+1,checks,banks);
 }
 for(const pair of paired.values()){need(pair.methods.length===5&&new Set(pair.methods).size===5,'All5 selectors for each input');}
 need(maxAP<1e-7&&maxP<1e-7,'Independent same thermal/power model');
 const proof={status:'PASS',utc:new Date().toISOString(),cases:40,request_count:requests,checks,banks,neural_decisions:neuralCalls,event_wait_actions:waitEvents,max_CPU_grants:maxCPU,max_AP_error_C:maxAP,max_power_error_API_W:maxP,max_energy_error_API_J:maxJ,shared_bank_preflight:read(path.join(H,'PREFLIGHT.json')),rule_preflight:read(path.join(H,'RULE_PREFLIGHT.json')),new_environment:0,new_training:0,physical_validation:false};
 write(path.join(O,'AUDIT.json'),proof);console.log('FAIR_SAVED_AUDIT_PASS',JSON.stringify(proof));
}
main().catch(e=>{console.error(e.stack);process.exitCode=1;});
