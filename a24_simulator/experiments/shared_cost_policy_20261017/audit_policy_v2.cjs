'use strict';
const fs=require('fs'),path=require('path'),crypto=require('crypto'),zlib=require('zlib');
const root=path.resolve(__dirname,'../..'),op=JSON.parse(fs.readFileSync(path.join(__dirname,'OPERATION_V2.json'))),out=path.join(root,op.output_dir);
const read=p=>JSON.parse(fs.readFileSync(p)),sha=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
let checks=0,maxError=0;function need(v,s){checks++;if(!v)throw Error(s);}
function close(a,b,s){maxError=Math.max(maxError,Math.abs(a-b));need(Math.abs(a-b)<1e-7,s);}
const auditOperation=read(path.join(__dirname,'AUDIT_OPERATION_V2.json'));
for(const p of auditOperation.pins)need(sha(p.path)===p.sha256&&fs.statSync(p.path).size===p.bytes,'New auditor/input pins');
const base=read(path.join(root,'results/STATE_COST_IDENTIFICATION_20261017_01/MODEL.json'));
const power=Object.fromEntries(base.supported_states.map((s,i)=>[s,base.coefficients_W_proxy[i]]));power.detection_GPU=.6013808404579677;
const discount=power.classification_GPU+power.detection_CPU-power['classification_GPU+detection_CPU'];
const task=r=>(r.task==='C'?'classification':'detection')+'_'+r.route;
function energy(owners,lo,hi,scale=1,tau=.9,full=false){
 const H=discount*scale,delta=(a,b)=>Math.max(0,Math.min(a.end_s,b.end_s,hi)-Math.max(a.start_s,b.start_s,lo));
 let work=0,known=0,unknown=0;
 for(const r of owners)work+=power[task(r)]*Math.max(0,Math.min(hi,r.end_s)-Math.max(lo,r.start_s));
 for(const a of owners.filter(r=>r.route==='CPU'))for(const b of owners.filter(r=>r.route==='GPU')){
  if(a.task==='D'&&b.task==='C')known+=delta(a,b);else unknown+=delta(a,b);
 }
 const busy=[];
 for(const r of owners.filter(r=>r.start_s<hi).sort((a,b)=>a.start_s-b.start_s)){
  const a=r.start_s,b=Math.min(hi,r.end_s);
  if(busy.length&&a<=busy.at(-1)[1])busy.at(-1)[1]=Math.max(busy.at(-1)[1],b);else busy.push([a,b]);
 }
 let tail=0;
 if(tau)for(let i=0;i<busy.length;i++){
  const end=busy[i][1],a=Math.max(lo,end),b=Math.min(hi,busy[i+1]?.[0]??hi);
  if(b>a)tail+=H*tau*(Math.exp(-(a-end)/tau)-Math.exp(-(b-end)/tau));
 }
 if(full&&busy.length)tail+=H*tau;
 return {work,known:-discount*known,unknown:-H*unknown,tail,increment:work-discount*known-H*unknown+tail};
}
const episode=(owners,scale=1,tau=.9)=>owners.length?energy(owners,0,Math.max(...owners.map(r=>r.end_s)),scale,tau,true).increment:0;
const result=read(path.join(out,'RESULT.json')),terminal=read(path.join(out,'COMPLETE.json'));
need(sha(path.join(out,'RESULT.json'))===terminal.result_sha256,'Terminal binding');
for(const p of [...op.sources,op.inputs,op.budget,op.cost_model,op.registration])need(sha(p.path)===p.sha256&&fs.statSync(p.path).size===p.bytes,'Frozen bytes');
const receipts=fs.readFileSync(path.join(out,'receipts.jsonl'),'utf8').trim().split(/\r?\n/).map(JSON.parse);
const starts=receipts.filter(r=>r.event==='START'),ends=receipts.filter(r=>r.event==='COMPLETE');
need(starts.length===8&&ends.length===8&&!receipts.some(r=>r.event==='FAIL'),'Exact8 environments');
need(new Set(starts.map(r=>r.identity)).size===8,'Unique START consumption');
const inputs=read(op.inputs.path).cases,raws=new Map();
for(const row of result.rows){
 const label=row.case+'_'+row.policy,rawFile=path.join(out,label+'.raw.json.gz'),file=path.join(out,label+'.json');
 const receipt=ends.find(r=>r.label===label);
 need(sha(rawFile)===row.raw_sha256&&sha(rawFile)===receipt.raw_sha256&&sha(file)===receipt.result_sha256,'Result bytes');
 const raw=JSON.parse(zlib.gunzipSync(fs.readFileSync(rawFile))),q=raw.prediction.requests,owners=raw.summary.gantt;
 raws.set(label,raw);const c=inputs.find(c=>c.id===row.case),[lo,hi]=c.work_window;
 const direct=energy(owners,lo,hi);
 close(row.new_cost.increment_J_proxy,direct.increment,'Direct new increment');
 close(row.new_cost.total_J_proxy,direct.increment+(hi-lo)*base.reference_baseline_W_proxy,'Same baseline');
 close(row.new_cost.full_episode_increment_J_proxy,episode(owners),'Complete remaining tail');
 const calls=raw.actor_calls.filter(r=>r.action.kind==='DISPATCH'),decisions=raw.prediction.decisions.filter(r=>r.action.kind==='DISPATCH');
 need(calls.length===48&&q.length===48&&decisions.length===48&&raw.opportunities.length===48,'Dispatch denominator');
 const done=new Set();let on=0,urgent=0;
 for(let i=0;i<calls.length;i++){
  const call=calls[i],action=call.action,t=call.time_ns,request=q.find(r=>r.request_id===action.request_id);
  need(t===decisions[i].time_ns&&JSON.stringify(action)===JSON.stringify(decisions[i].action),'Actor applied');
  need(call.mask[call.chosen_index]&&request.route===action.route&&request.dispatch_ns===t,'Protected legal action/route/clock');
  const active=q.filter(r=>done.has(r.request_id)&&r.available_ns>t);
  need(active.length<2&&!active.some(r=>r.route===action.route),'One CPU one GPU');
  need(request.queue_entry_ns<=t&&request.scheduled_arrival_ns<=request.queue_entry_ns,'Ready public request');
  need(request.response_ns===(request.task==='C'?request.output_ready_ns:request.persist_complete_ns)&&request.available_ns>=request.response_ns,'Response/AVAILABLE');
  on+=Number(request.response_ns<=request.deadline_ns);urgent+=Number(request.priority==='U'&&request.response_ns<=request.deadline_ns);done.add(request.request_id);
 }
 close(on,row.metrics.on_time,'All ontime');close(urgent,row.metrics.urgent_on_time,'All urgent outcomes');
 const waits=raw.actor_calls.filter(r=>r.action.kind==='WAIT');
 for(const call of waits)need(call.mask[call.chosen_index]&&call.action.wait_ns===50e6&&call.public_state.owners.length===0&&call.public_state.queue.length===1,'Same protected coalescing');
 close(waits.length,row.opportunities.coalescing_WAIT_calls,'WAIT separate');
 if(row.policy==='SHARED_COST'){
  need(raw.marginal_audits.length===48,'Every new selection has public nominal cost record');
  for(const [decisionIndex,audit] of raw.marginal_audits.entries()){
   const call=calls[decisionIndex],now=audit.time_ns/1e9;
   need(call.time_ns===audit.time_ns,'Sequential decision clock; same-clock calls remain distinct');
   need(call.chosen_index===audit.chosen,'Chosen score applied');
   const prefix=owners.filter(r=>r.start_s<now).map(r=>({...r,end_s:Math.min(now,r.end_s)}));
   const before=[...prefix,...audit.nominal_reservations],old=episode(before);
   const legal=call.mask.slice(0,72).flatMap((v,i)=>v?[String(i)]:[]);
   need(JSON.stringify(Object.keys(audit.costs).sort())===JSON.stringify([...legal].sort()),'Every and only final legal candidate scored');
   let minimum=Infinity;
   for(const index of legal){
    const candidate=audit.nominal_candidates[index],cost=audit.costs[index];
    need(candidate.start_s===now&&candidate.end_s>now,'Public candidate starts now');
    const e=episode([...before,candidate])-old;
    close(e,cost.marginal_full_episode_J_proxy,'Independent exact nominal marginal');minimum=Math.min(minimum,e);
   }
   close(audit.costs[audit.chosen].marginal_full_episode_J_proxy,minimum,'Minimum cost among same protected actions');
   need(!audit.uses_future_actual_duration&&!audit.uses_future_arrival,'No declared future truth');
  }
 }else need(raw.marginal_audits.length===0,'Frozen baseline chooser');
}
const sensitivity=[];
for(const scale of [0,.5,1,1.5])for(const tau of [0,.225,.9,3.6]){
 const pairs=[];
 for(const c of inputs){
  const a=result.rows.find(r=>r.case===c.id&&r.policy==='SHARED_COST'),b=result.rows.find(r=>r.case===c.id&&r.policy==='COALESCED_COST');
  const ar=raws.get(c.id+'_SHARED_COST'),br=raws.get(c.id+'_COALESCED_COST');
  const delta=energy(ar.summary.gantt,...c.work_window,scale,tau).increment-energy(br.summary.gantt,...c.work_window,scale,tau).increment;
  pairs.push({case:c.id,total_delta_J_proxy:delta,full_episode_delta_J_proxy:episode(ar.summary.gantt,scale,tau)-episode(br.summary.gantt,scale,tau),
   on_time_delta:a.metrics.on_time-b.metrics.on_time,urgent_delta:a.metrics.urgent_on_time-b.metrics.urgent_on_time,
   AP_delta_c:a.metrics.mean_AP_c===null||b.metrics.mean_AP_c===null?null:a.metrics.mean_AP_c-b.metrics.mean_AP_c});
 }
 sensitivity.push({shared_scale:scale,idle_decay_s:tau,pairs,mean_total_delta_J_proxy:pairs.reduce((s,p)=>s+p.total_delta_J_proxy,0)/4});
}
const aggregates=op.policies.map(policy=>{
 const rows=result.rows.filter(r=>r.policy===policy),sum=k=>rows.reduce((s,r)=>s+r.metrics[k],0),mean=k=>rows.reduce((s,r)=>s+r.new_cost[k],0)/rows.length;
 return {policy,conditions:rows.length,requests:192,on_time:sum('on_time'),urgent_on_time:sum('urgent_on_time'),response_missing:sum('response_missing'),incomplete:sum('incomplete'),
  mean_AP_c:rows.every(r=>r.metrics.mean_AP_c!==null)?sum('mean_AP_c')/4:null,mean_total_J_proxy:mean('total_J_proxy'),mean_increment_J_proxy:mean('increment_J_proxy'),mean_full_episode_J_proxy:mean('full_episode_increment_J_proxy'),
  mean_route_work_J_proxy:mean('additive_route_J_proxy'),mean_known_pair_credit_J_proxy:mean('identified_pair_credit_J_proxy'),
  mean_assumed_pair_credit_J_proxy:mean('hypothesized_pair_credit_J_proxy'),mean_idle_tail_J_proxy:mean('hypothesized_idle_tail_J_proxy')};
});
const nominal=sensitivity.find(r=>r.shared_scale===1&&r.idle_decay_s===.9);
const changes=inputs.map(c=>{
 const a=raws.get(c.id+'_SHARED_COST').prediction.requests,b=raws.get(c.id+'_COALESCED_COST').prediction.requests;
 const byId=new Map(b.map(q=>[q.request_id,q]));
 return {case:c.id,route_changes:a.filter(q=>q.route!==byId.get(q.request_id).route).length,
  dispatch_clock_changes:a.filter(q=>q.dispatch_ns!==byId.get(q.request_id).dispatch_ns).length};
});
const analysis={status:'PASS_SAVED_POLICY_AND_COST_RECONCILIATION',checks,max_absolute_cost_error:maxError,aggregates,nominal,changes,sensitivity,
 assumptions_shared_between_policies:true,posthoc_sensitivity_does_not_retrain_policies:true,independent_confirmation:false,
 new_START:8,new_COMPLETE:8,new_FAIL:0,NN_training:0,new_fit:0,measured_J:null,
 original_RL_envelope:'223 old +25 choice +8 cost policy =256 consumed; remaining0; RR remaining1 separate'};
fs.writeFileSync(path.join(out,'ANALYSIS.json'),JSON.stringify(analysis,null,2)+'\n',{flag:'wx'});
fs.writeFileSync(path.join(out,'AUDIT.json'),JSON.stringify({status:'PASS',checks,max_absolute_cost_error:maxError,result_sha256:sha(path.join(out,'RESULT.json')),analysis_sha256:sha(path.join(out,'ANALYSIS.json'))},null,2)+'\n',{flag:'wx'});
console.log(JSON.stringify({checks,maxError,aggregates,nominal,changes},null,2));
