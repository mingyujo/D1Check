'use strict';
// Saved-only audit in a separate language. No producer/engine imports.
const fs=require('fs'),path=require('path'),zlib=require('zlib'),crypto=require('crypto');
const H=__dirname,A=path.resolve(H,'../..'),R=path.dirname(A),O=path.join(A,'results/A24_DYNAMIC_ROUTE600_20261020_01'),Q=path.join(A,'results/A24_ATC_BC600_20261019_01'),P=path.join(A,'results/A24_DURATION_040_20261019_01');
const read=p=>JSON.parse(p.endsWith('.gz')?zlib.gunzipSync(fs.readFileSync(p)):fs.readFileSync(p));
const sha=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
const save=(n,x)=>fs.writeFileSync(path.join(O,n),JSON.stringify(x,null,2)+'\n',{flag:'wx'});
const {step,integral}=require('../a24_s26_method_20261019/audit.cjs');
let checks=0,maxerr=0;
function ok(v,m){checks++;if(!v)throw Error(m);}
function near(a,b,m,tol=3e-7){maxerr=Math.max(maxerr,Math.abs(a-b));ok(Number.isFinite(a)&&Number.isFinite(b)&&Math.abs(a-b)<=tol,`${m}: ${a} != ${b}`);}
const result=read(path.join(O,'RESULT.json')),op=read(path.join(H,'OPERATION.json'));
ok(result.START===6&&result.COMPLETE+result.FAIL===6,'Six new START only');
for(const p of op.pins){const f=path.join(R,p.path);ok(sha(f)===p.sha256&&fs.statSync(f).size===p.bytes,'Registered source/input '+p.path);}
const allReceipts=fs.readFileSync(path.join(O,'receipts.jsonl'),'utf8').trim().split('\n').map(JSON.parse);
ok(allReceipts.every(r=>r.kind==='EVAL')&&result.new_BC_fit===0&&result.new_training===0,'No fits or training');
const receipts=allReceipts.filter(r=>r.kind==='EVAL');
ok(receipts.filter(r=>r.event==='START').length===6,'Six durable START');
ok(receipts.filter(r=>r.event==='COMPLETE').length===result.COMPLETE,'COMPLETE census');
ok(receipts.filter(r=>r.event==='FAIL').length===result.FAIL,'FAIL census');
ok(new Set(receipts.filter(r=>r.event==='START').map(r=>r.start_id)).size===6,'Unique START IDs');
const originals=read(path.join(P,'RESULT.json')).rows.filter(r=>r.condition.supply_s===600);
const all=[...originals.map(r=>({...r,raw:{path:path.relative(R,path.join(P,r.label+'.raw.json.gz')),sha256:r.raw_sha256},reused:true})),...read(path.join(A,'results/A24_BC_600_20261019_01/RESULT.json')).rows.map(r=>({...r,reused:true})),...read(path.join(Q,'RESULT.json')).rows.map(r=>({...r,reused:true})),...read(path.join(A,'results/A24_IDLE_WAIT600_20261019_01/RESULT.json')).rows.map(r=>({...r,reused:true})),...read(path.join(A,'results/A24_RR_600_20261020_01/RESULT.json')).rows.map(r=>({...r,reused:true})),...result.rows.map(r=>({...r,reused:false}))];
ok(all.length===20,'Fourteen saved comparators and six new dynamic rows');
let derived=[];
const rawCache=new Map();
for(const row of all){
 const file=path.join(R,row.raw.path);ok(sha(file)===row.raw.sha256,'Stored raw hash');
 const d=read(file);rawCache.set(row.label,d);
 if(row.status==='FAIL'){ok(d.partial_not_complete_trace&&row.metrics===null,'Guard failure not fabricated');derived.push({label:row.label,case:row.case,policy:row.policy,failed:true,failure:row.failure,reused:row.reused,raw:row.raw});continue;}
 const r=d.result,c=d.case,bank=Object.fromEntries(read(path.join(A,'experiments/a24_duration_040_20261019/banks',c.id+'.BANK.json.gz')).jobs.map(j=>[j.request_id,j]));
 const nominalVectors=read(path.join(A,'experiments/a24_duration_040_20261019/banks',c.id+'.BANK.json.gz')).nominal_vectors;
 const qmap=new Map(r.requests.map(q=>[q.request_id,q])),work=new Map();
 ok(r.requests.length===c.n&&new Set(r.requests.map(q=>q.request_id)).size===c.n,'All arrivals once');
 for(const q of r.requests){const src=c.input.requests[q.ordinal];ok(q.scheduled_arrival_ns===Math.round(src.arrival_s*1e9)&&q.deadline_ns===Math.round(src.deadline_s*1e9)&&q.task===src.profile[0]&&q.priority===src.priority,'Same public requests');ok(q.queue_entry_ns===bank[q.request_id].queue_entry_ns,'Same admission');if(q.route)ok(JSON.stringify(q.timing.stages_ns)===JSON.stringify(bank[q.request_id].routes[q.route].stages_ns),'Same latent route work');}
 let prev=null;
 for(const t of r.trace){
  ok(t.end_ns>t.start_ns,'Positive clock');near(t.dt,(t.end_ns-t.start_ns)/1e9,'dt',1e-12);
  if(prev){ok(t.start_ns===prev.end_ns,'Contiguous clock');near(t.state.temperature_c,prev.next_state.temperature_c,'T continuity',1e-10);const dispatchReset=r.requests.some(q=>q.dispatch_ns===t.start_ns);near(t.state.shared_z,dispatchReset?1:prev.next_state.shared_z,'Tail continuity or explicit dispatch reset',1e-10);}prev=t;
  ok(t.active.filter(j=>j.route==='CPU').length<=3&&t.active.filter(j=>j.route==='GPU').length<=1,'Capacity');
  const a=step(t.state,t.active,t.dt,r.config,'ORIGINAL');near(a.state.temperature_c,t.next_state.temperature_c,'Independent T');near(a.state.shared_z,t.next_state.shared_z,'Independent tail');near(a.J,t.increment,'Independent E');near(a.H,t.temperature_area,'Independent AP area');
  for(const j of t.active){near(a.rates[j.request_id],t.speeds[j.request_id],'Progress rate',1e-12);const q=qmap.get(j.request_id);ok(q&&q.route===j.route&&q.dispatch_ns<=t.start_ns&&(q.available_ns===null||q.available_ns>=t.end_ns),'Nonpreemptive ownership');const k=j.request_id+'|'+j.stage;work.set(k,(work.get(k)||0)+t.dt*a.rates[j.request_id]);}
 }
 for(const q of r.requests)if(q.available_ns!==null){for(let k=0;k<5;k++)near(work.get(q.request_id+'|'+k)||0,q.timing.stages_ns[k]/1e9,'Conserved five-stage work',7e-9);ok(q.response_ns===(q.task==='C'?q.output_ready_ns:q.persist_complete_ns),'C/D response boundary');}
 ok(d.calls.length===r.decisions.length,'Actor call census');let capped=0,forecasts=0;
 let rrTurn='C';
 for(let i=0;i<d.calls.length;i++){
  const call=d.calls[i],dec=r.decisions[i],s=dec.public_state;
  ok(s.now_ns===dec.time_ns&&s.queue.every(q=>q.queue_entry_ns<=s.now_ns),'Causal visible queue');
  if(dec.action.kind==='DISPATCH')ok(s.queue.some(q=>q.request_id===dec.action.request_id),'Visible dispatch');
  if(row.policy==='RR_CPU'){
   const free=['CPU','GPU'].filter(route=>s.owners.filter(o=>o.route===route).length<(route==='CPU'?3:1));
   ok(call.turn_before===rrTurn&&call.future_information===false&&call.NN_execution===false,'RR public-only turn before');
   const local=s.queue.filter(q=>q.task===rrTurn),pool=local.length?local:s.queue;
   if(pool.length&&free.length){
    const q=pool.slice().sort((a,b)=>a.scheduled_arrival_ns-b.scheduled_arrival_ns||a.ordinal-b.ordinal||a.request_id.localeCompare(b.request_id))[0];
    ok(dec.action.kind==='DISPATCH'&&dec.action.request_id===q.request_id&&dec.action.route===free[0],'RR class turn, within-class FIFO and CPU3 availability');
    rrTurn=q.task==='C'?'D':'C';
    ok(call.selected_task===q.task&&call.empty_class_skipped===!Boolean(local.length),'RR actual class and skip log');
   }else ok(dec.action.kind==='RESOURCE_WAIT','Only resource wait without legal dispatch');
   ok(call.turn_after===rrTurn&&JSON.stringify(call.action)===JSON.stringify(dec.action),'RR action and next turn');
   ok(JSON.stringify(call.free_routes)===JSON.stringify(free),'RR free-route log');
  }
  if(row.policy.endsWith('_DYN')){
   const free=['CPU','GPU'].filter(route=>s.owners.filter(o=>o.route===route).length<(route==='CPU'?3:1));
   const fifo=(a,b)=>a.scheduled_arrival_ns-b.scheduled_arrival_ns||a.ordinal-b.ordinal||a.request_id.localeCompare(b.request_id);
   const pool=row.policy==='RR_DYN'?(s.queue.filter(q=>q.task===rrTurn).length?s.queue.filter(q=>q.task===rrTurn):s.queue):s.queue;
   const q=pool.slice().sort(row.policy==='EDF_DYN'?(a,b)=>a.deadline_ns-b.deadline_ns||fifo(a,b):fifo)[0];
   ok(call.future_information===false&&call.NN_execution===false&&call.rolling_horizon===false&&call.voluntary_WAIT===false,'Public one-request estimator only');
   ok(dec.action.kind==='DISPATCH'&&q.request_id===dec.action.request_id,'Request order first');
   ok(JSON.stringify(call.free_routes)===JSON.stringify(free)&&call.estimates.length===free.length,'Only free routes compared');
   const estimates=[];
   for(const route of free){
    const v=nominalVectors[q.request_id+'|'+route],p=r.config,T=s.sensor.temperature_c;
    const f=Math.max(p.minimum_speed,1/(1+p.strength*(route==='CPU'?p.cpu_slope:p.gpu_slope)*Math.max(0,T-p.onset_c)));
    const factor=route==='CPU'?1+.25*s.owners.filter(o=>o.route==='CPU'&&o.stage===1).length:1;
    const rate=f/factor,resp=v.slice(0,q.task==='C'?2:3).reduce((a,b)=>a+b,0)-v[1]+v[1]/rate;
    const tie=crypto.createHash('sha256').update(q.request_id+'|'+route).digest('hex');
    const logged=call.estimates.find(x=>x.route===route);
    ok(logged&&JSON.stringify(logged.nominal_vector_s)===JSON.stringify(v),'Exact public nominal not latent');
    near(logged.thermal_rate,f,'Independent present thermal speed',1e-12);near(logged.contention_factor,factor,'Present CPU execution count',1e-12);
    near(logged.progress_rate,rate,'Independent present speed',1e-12);near(logged.response_after_dispatch_s,resp,'Independent response estimate',1e-12);
    ok(logged.tie_sha256===tie,'No fixed route tie priority');estimates.push({route,resp,tie});
   }
   estimates.sort((a,b)=>a.resp-b.resp||a.tie.localeCompare(b.tie));
   ok(dec.action.route===estimates[0].route&&JSON.stringify(dec.action)===JSON.stringify(call.action),'Minimum predicted response route');
   if(row.policy==='RR_DYN'){ok(call.turn_before===rrTurn,'RR request turn before');rrTurn=q.task==='C'?'D':'C';ok(call.turn_after===rrTurn,'RR request turn after');}
   else ok(call.turn_before===null&&call.turn_after===null,'No RR in FIFO/EDF');
  }
  if(row.policy==='IDLE_BC'){
   const physical=call.physical_mask,expected=physical.slice(),vectors=call.forecasts.map(f=>[...f.cost,f.AP_end,f.peak]);
   ok(Array.isArray(physical)&&physical.length===36,'Physical mask logged');
   if(!s.owners.length&&s.queue.length){const queued=new Set(s.queue.map(q=>q.request_id));
    for(let w=0;w<call.actions.length;w++)if(physical[w]&&call.actions[w].kind==='WAIT'){
     for(let j=0;j<call.actions.length;j++){
      const a=call.actions[j],d=call.forecasts[j],f=call.forecasts[w];
      if(!physical[j]||a.kind!=='DISPATCH'||!queued.has(a.request_id)||!['CPU','GPU'].includes(a.route))continue;
      if(![d,f].every(v=>v.comparison_complete===true&&v.capped===false&&v.no_future_arrivals===true&&v.no_future_latents===true&&v.cost.length===5&&[...v.cost,v.AP_end,v.peak,v.H_s].every(Number.isFinite)))continue;
      if(Math.abs(d.H_s-f.H_s)>1e-8||JSON.stringify(d.visible_ids.slice().sort())!==JSON.stringify(f.visible_ids.slice().sort())||!d.visible_ids.includes(a.request_id))continue;
      let worse=false,strict=false;for(let k=0;k<7;k++){const x=vectors[j][k],y=vectors[w][k],t=1e-9+1e-9*Math.max(Math.abs(x),Math.abs(y));if(x-y>t)worse=true;if(y-x>t)strict=true;}
      if(!worse&&strict){expected[w]=false;break;}
     }
    }
   }
   ok(expected.length===call.mask.length&&expected.every((v,j)=>v===call.mask[j]),'Independent new-state idle dominance mask');
   ok(expected[call.chosen]&&call.pre_NN_forecast_filter===true,'Pre-NN guard and eligible choice');
   const removed=expected.map((v,j)=>!v&&physical[j]?j:null).filter(v=>v!==null);
   ok(call.idle_wait_guard.applied===Boolean(removed.length)&&JSON.stringify(call.idle_wait_guard.removed.map(r=>r.index))===JSON.stringify(removed),'Recorded guard explanation');
  }
  if(call.forecasts){const ids=new Set([...s.queue,...s.owners].map(q=>q.request_id));ok(call.future_information===false&&call.post_NN_override===false,'No future inputs/override');ok(JSON.stringify(call.actions[call.chosen])===JSON.stringify(call.action),'Selected action returned');for(const f of call.forecasts){forecasts++;capped+=Number(f.capped);ok(f.no_future_arrivals&&f.no_future_latents&&f.visible_ids.every(id=>ids.has(id)),'Public forecast IDs');}}
 }
 const service={};for(const p of ['ALL','U','N']){const qs=r.requests.filter(q=>p==='ALL'||q.priority===p),ans=qs.filter(q=>q.response_ns!==null&&q.response_ns<=c.drain_stop_s*1e9),lat=ans.map(q=>(q.response_ns-q.scheduled_arrival_ns)/1e9).sort((a,b)=>a-b);service[p]={n:qs.length,on:ans.filter(q=>q.response_ns<=q.deadline_ns).length,missing:qs.length-ans.length,P95:lat.length?lat[Math.ceil(.95*lat.length)-1]:null,latencies_s:lat};}
 const incomplete=r.requests.filter(q=>q.available_ns===null||q.available_ns>c.drain_stop_s*1e9).length;
 for(const task of ['C','D'])for(const route of ['CPU','GPU'])ok(row.metrics.route_counts[task+'_'+route]===r.requests.filter(q=>q.task===task&&q.route===route).length,'Independent route census');
 ok(service.ALL.on===row.metrics.on_time&&service.U.on===row.metrics.urgent_on_time&&incomplete===row.metrics.incomplete,'Independent service census');
 near(integral(r,'ORIGINAL',c.drain_stop_s*1e9).J,row.metrics.total_J_proxy,'Producer total J',4e-6);
 const finish=incomplete?null:Math.max(c.supply_stop_s*1e9,...r.requests.map(q=>q.available_ns));
 const own=finish===null?null:integral(r,'ORIGINAL',finish);
 const ownTail=finish===null?null:integral(r,'ORIGINAL',finish+30e9).J-30*r.config.baseline;
 if(row.score&&finish!==null)near(ownTail,row.score.own_with_activity_tail_J,'Own+activity tail',4e-6);
 derived.push({label:row.label,case:c.id,policy:row.policy,pattern:c.condition.pattern_index,reused:row.reused,raw:row.raw,service,incomplete,finish_ns:finish,own,own_tail_J:ownTail,supply:integral(r,'ORIGINAL',c.supply_stop_s*1e9),wait_s:row.metrics.wait_s,route_counts:row.metrics.route_counts,decisions:d.calls.length,capped_forecasts:capped,forecasts});
}
for(const row of derived.filter(r=>!r.failed)){
 const same=derived.filter(r=>r.case===row.case),d=rawCache.get(row.label);
 const end=same.every(r=>!r.failed&&r.finish_ns!==null)?Math.max(d.case.supply_stop_s*1e9,...same.map(r=>r.finish_ns)):d.case.drain_stop_s*1e9;
 row.common_end_ns=end;row.common=integral(d.result,'ORIGINAL',end);
}
const mean=a=>a.reduce((s,x)=>s+x,0)/a.length,groups=[];
for(const policy of ['FIFO_CPU','EDF_CPU','RR_CPU','FIFO_DYN','EDF_DYN','RR_DYN','OLD_PPO','BC','ATC_BC','IDLE_BC']){
 const rr=derived.filter(r=>r.policy===policy),complete=rr.filter(r=>!r.failed),failed=rr.length-complete.length;
 if(failed){groups.push({policy,patterns:rr.length,failed,service:null,common_J:null,AP:null});continue;}
 const service={};for(const p of ['ALL','U','N']){const lat=rr.flatMap(r=>r.service[p].latencies_s).sort((a,b)=>a-b);service[p]={n:rr.reduce((s,r)=>s+r.service[p].n,0),on:rr.reduce((s,r)=>s+r.service[p].on,0),missing:rr.reduce((s,r)=>s+r.service[p].missing,0),mean_session_P95_s:mean(rr.map(r=>r.service[p].P95)),pooled_P95_s:lat.length?lat[Math.ceil(.95*lat.length)-1]:null};}
 groups.push({policy,patterns:rr.length,failed:0,service,common_J:mean(rr.map(r=>r.common.J)),AP:mean(rr.map(r=>r.common.AP)),peak:mean(rr.map(r=>r.common.peak)),supply_J:mean(rr.map(r=>r.supply.J)),own_tail_J:mean(rr.map(r=>r.own_tail_J)),incomplete:rr.reduce((s,r)=>s+r.incomplete,0),wait_s:mean(rr.map(r=>r.wait_s)),capped_forecasts:rr.reduce((s,r)=>s+r.capped_forecasts,0)});
}
const bc=groups.find(g=>g.policy==='IDLE_BC'),comparisons=[];
if(!bc.failed)for(const base of groups.filter(g=>g.policy!=='IDLE_BC')){
 const per=derived.filter(r=>r.policy==='IDLE_BC').map(r=>{const b=derived.find(b=>b.case===r.case&&b.policy===base.policy);return {pattern:r.pattern,joint:r.service.U.on===r.service.U.n&&r.service.ALL.on/r.service.ALL.n>=.95&&r.incomplete===0&&r.service.ALL.missing===0&&['ALL','U','N'].every(k=>r.service[k].on>=b.service[k].on)&&r.common.J<b.common.J&&r.own_tail_J<b.own_tail_J&&r.common.AP<b.common.AP&&r.common.peak<=b.common.peak};});
 comparisons.push({baseline:base.policy,saved_common_J:base.common_J-bc.common_J,saving_pct:100*(1-bc.common_J/base.common_J),AP_delta:bc.AP-base.AP,peak_delta:bc.peak-base.peak,U_P95_delta_s:bc.service.U.mean_session_P95_s-base.service.U.mean_session_P95_s,ALL_P95_delta_s:bc.service.ALL.mean_session_P95_s-base.service.ALL.mean_session_P95_s,own_tail_saving_pct:100*(1-bc.own_tail_J/base.own_tail_J),per_pattern:per,both_patterns_joint:per.every(p=>p.joint)});
}
save('DERIVED.json',derived);save('SUMMARY.json',{groups,IDLE_BC_comparisons:comparisons,old_results_rerun:0,new_EVAL_START:result.START,new_BC_fit:0,local_only:true,logic_repair_applied:true});
save('AUDIT.json',{status:'PASS',utc:new Date().toISOString(),checks,max_absolute_error:maxerr,rows:derived.length,new_environment:0,source_sha256:sha(__filename),dispatch_reset_checked:true,analytic_reference_sha256:sha(path.join(A,'experiments/a24_s26_method_20261019/audit.cjs')),code_version:op.code_version,endpoint_peak_definition_preserved:true});
console.log(JSON.stringify({status:'PASS',checks,maxerr,rows:derived.length,groups:groups.map(g=>({policy:g.policy,J:g.common_J,AP:g.AP,U95:g.service?.U?.mean_session_P95_s,ALL:g.service?.ALL?.on,U:g.service?.U?.on})),comparisons}));
