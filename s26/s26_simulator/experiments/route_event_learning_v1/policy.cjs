'use strict';
const rc=require('./source/resource_contract.cjs'),tm=require('./source/multi_timing.cjs'),{rollout}=require('./source/nominal_rollout.cjs'),{Physics}=require('./physics.cjs'),{select:edf}=require('../plain_edf_v1/select.cjs');
const WEIGHTS=[.5,.5,8,4,30],ACTIONS=27,WIDTH=32;let state;
function configure(options){state={...options,waitByHead:new Map,forecasts:0,actual:0,hits:0,calls:0,numerical_failures:0};}
const FIFO=(a,b)=>a.arrival-b.arrival||a.ordinal-b.ordinal;
function ranks(obs,packet,nom,model){const candidates=[];for(const q of obs.ready)for(const r of rc.allowed(q))if(rc.legal(r,obs.owners,obs.capacity)){const p=tm.lengths(packet,nom,r,obs.sensor.AP,[],model,q.priority);candidates.push({q,route:r,p});}
 const mean=candidates.reduce((s,x)=>s+x.p.occupied,0)/Math.max(1,candidates.length);for(const c of candidates)c.ATC=Math.log((c.q.priority==='urgent'?2:1)/c.p.occupied)-Math.max(0,c.q.deadline-obs.time-c.p.response)/(2*Math.max(mean,1e-9));
 return candidates;
}
function evaluate(obs,packet,nom,model,first,past){const physics=past.clone(),J=physics.J,H=physics.H,start=physics.time;
 const roll=rollout(obs,packet,nom,model,first,physics),span=physics.time-start,APmean=(physics.H-H)/Math.max(span,1e-9),energy=physics.J-J-physics.B0*span;
 const late=roll.responses.map(r=>{const q=[...obs.ready,...obs.owners].find(q=>q.ordinal===r.ordinal);return {priority:q.priority,deadline:r.deadline,response:r.response,relative_deadline:q.deadline-q.arrival};});
 const n=Math.max(1,late.length),cost=[Math.max(0,energy)/n,Math.max(0,APmean-physics.skin)/10,0,0,0];
 for(const r of late){if(r.response===null)cost[4]+=1/n;else{const d=Math.max(0,r.response-r.deadline);cost[r.priority==='urgent'?2:3]+=(Number(d>1e-9)+(state.balance?.tail??.2)*Math.min(5,d/Math.max(.05,r.relative_deadline)))/n;}}
 if(roll.numerical_failure){cost[4]=Math.max(1,cost[4]);state.numerical_failures++;}
 return {nominal_failure:roll.numerical_failure,cost,energy,AP_mean:APmean,AP_end:physics.temperature(),candidate_response:roll.responses.find(x=>x.ordinal===first?.ordinal)?.response??null,nominal_unfinished:late.filter(x=>x.response===null).length,nominal_scope:'Candidate union plus observed owners; frozen nominal vectors; no future actual work/arrivals',forecast_calls:1};
}

function routeContext(obs){
 if(!state.seenTasks){state.seenTasks=new Set;state.recentTasks=[];state.preferred=new Map;state.classCounter=0;state.taskTrace=[];state.preferenceTrace=[];}
 const observed=[...obs.ready,...obs.owners.map(o=>({...o,task:o.task??o.route.split('_')[0]}))].sort(FIFO);
 for(const q of observed)if(!state.seenTasks.has(q.ordinal)){state.seenTasks.add(q.ordinal);state.taskTrace.push({ordinal:q.ordinal,task:q.task,time:obs.time});state.recentTasks.push(q.task);if(state.recentTasks.length>64)state.recentTasks.shift();}
 const mix=state.recentTasks.length<16?.75:state.recentTasks.filter(t=>t==='classification').length/state.recentTasks.length;
 for(const q of obs.ready.slice().sort(FIFO))if(!state.preferred.has(q.ordinal)){
  let r='detection_CPU';if(q.task==='classification'){r=mix<=.625?'classification_NPU':state.classCounter%4===3?'classification_GPU':'classification_NPU';state.classCounter++;}state.preferred.set(q.ordinal,r);state.preferenceTrace.push({ordinal:q.ordinal,route:r,time:obs.time,observed_mix:mix,seen_count:state.recentTasks.length,class_counter:state.classCounter});
 }
 return {...obs,preferred_routes:Object.fromEntries(obs.ready.map(q=>[q.ordinal,state.preferred.get(q.ordinal)])),observed_classification_mix:mix};
}

function select(obs,packet,nom,config){
 const model=packet.multi.models[config.model];state.calls++;if(state.balance)obs=routeContext(obs);
 if(state.mode==='EDF'||state.mode==='EDF_NPU_FIRST'||state.mode==='EDF_GPU_FIRST')return edf(obs,state.mode==='EDF'?['CPU','GPU','NPU']:state.mode==='EDF_GPU_FIRST'?['GPU','NPU','CPU']:['NPU','GPU','CPU']);
 const all=ranks(obs,packet,nom,model);if(!all.length)return {kind:'NONE',candidates:[]};
 const ranked=all.slice().sort((a,b)=>b.ATC-a.ATC||FIFO(a.q,b.q)||a.p.response-b.p.response||a.p.occupied-b.p.occupied||a.route.localeCompare(b.route));
 if(state.mode==='ATC_SALVAGE'){for(const c of ranked){const slack=c.q.deadline-obs.time-c.p.response,prob=1/(1+Math.exp(Math.max(-60,Math.min(60,-slack/Math.max(.05,.15*c.p.response)))));c.salvage=c.ATC+Math.log(.02+.98*prob);}ranked.sort((a,b)=>b.salvage-a.salvage||FIFO(a.q,b.q)||a.route.localeCompare(b.route));return {kind:'DISPATCH',ordinal:ranked[0].q.ordinal,route:ranked[0].route,forecast_calls:0};}
 if(state.mode==='ATC')return {kind:'DISPATCH',ordinal:ranked[0].q.ordinal,route:ranked[0].route,forecast_calls:0};
 const queue=obs.ready.slice().sort((a,b)=>a.deadline-b.deadline||FIFO(a,b)),set=new Set;
 const buckets=new Map;for(const q of obs.ready.slice().sort(FIFO)){const k=q.task+'|'+q.priority+(state.balance?'|'+obs.preferred_routes[q.ordinal]:'');if(!buckets.has(k))buckets.set(k,[]);buckets.get(k).push(q);}const bucketRows=[...buckets].sort((a,b)=>a[0].localeCompare(b[0])).map(x=>x[1]);
 if(state.variant!=='FROZEN_BASE'){
  const proposed=[queue[0],...bucketRows.flatMap(a=>[a[0],a.at(-1)]),...ranked.slice(0,6).map(x=>x.q),...queue];for(const q of proposed){if(set.size>=8)break;set.add(q.ordinal);}
 }else{for(const q of queue.slice(0,4))set.add(q.ordinal);set.add(obs.ready.slice().sort(FIFO)[0].ordinal);for(const r of ranked){set.add(r.q.ordinal);if(set.size>=Math.min(8,obs.ready.length))break;}}
 const ready=queue.filter(q=>set.has(q.ordinal)).slice(0,8),forecastSet=new Set(ready.map(q=>q.ordinal));
 if(state.variant!=='FROZEN_BASE')for(let k=0;k<obs.ready.length&&forecastSet.size<Math.min(32,obs.ready.length);k++)for(const a of bucketRows)for(const q of [a[k],a[a.length-1-k]])if(q&&forecastSet.size<32)forecastSet.add(q.ordinal);
 const forecastReady=state.variant!=='FROZEN_BASE'?queue.filter(q=>forecastSet.has(q.ordinal)):ready;
 const publicWork=forecastReady.reduce((s,q)=>s+Math.min(...rc.allowed(q).map(r=>tm.lengths(packet,nom,r,obs.sensor.AP,[],model,q.priority).occupied)),0);
 const forecastHorizon=state.variant!=='FROZEN_BASE'?Math.min(obs.horizon_s,obs.time+Math.max(10,3*publicWork+3*obs.owners.length)):obs.horizon_s;
 const visible={...obs,ready:forecastReady,horizon_s:forecastHorizon},past=require('./public_observer.cjs').past(obs,config.power_model,config.thermal_model,state);
 const actions=all.filter(x=>ready.some(q=>q.ordinal===x.q.ordinal)).sort((a,b)=>a.q.deadline-b.q.deadline||FIFO(a.q,b.q)||rc.ROUTES.indexOf(a.route)-rc.ROUTES.indexOf(b.route)).map(x=>({kind:'DISPATCH',ordinal:x.q.ordinal,route:x.route,nom:x.p,ATC:x.ATC}));
 const head=queue[0];
 if(state.balance){
  for(const wait_s of [.02,.05])if(obs.time+wait_s<config.dispatch_stop_s)actions.push({kind:'WAIT',wait_s,ordinal:head.ordinal,nom:ranked[0].p,ATC:ranked[0].ATC});
  if(obs.owners.length&&obs.time<config.dispatch_stop_s)actions.push({kind:'WAIT_EVENT',ordinal:head.ordinal,nom:ranked[0].p,ATC:ranked[0].ATC});
 }else{
  for(const wait_s of [.05,.2,.5])if((state.mode==='ENERGY_ONLY'||obs.wait_used_s+wait_s<=12+1e-9&&(state.waitByHead.get(head.ordinal)??0)+wait_s<=1.5+1e-9)&&obs.time+wait_s<config.dispatch_stop_s)actions.push({kind:'WAIT',wait_s,ordinal:head.ordinal,nom:ranked[0].p,ATC:ranked[0].ATC});
 }
 if(actions.length>ACTIONS)throw Error('Action capacity');
 const memo=new Map;const x=Array.from({length:ACTIONS},()=>Array(WIDTH).fill(0)),mask=Array(ACTIONS).fill(false),scores=Array(ACTIONS).fill(0),forecasts=[];
 for(let i=0;i<actions.length;i++){const a=actions[i],q=obs.ready.find(q=>q.ordinal===a.ordinal),key=JSON.stringify([a.kind,q.task,q.priority,q.arrival,q.deadline,a.route,a.wait_s]);let f=memo.get(key);if(f)state.hits++;else{f=evaluate(visible,packet,nom,model,a.kind==='WAIT_EVENT'?{wait_event:true}:a.kind==='WAIT'?{wait_s:a.wait_s}:{ordinal:a.ordinal,route:a.route},past);state.actual++;if(!f.nominal_failure)memo.set(key,f);}forecasts.push(f);state.forecasts++;mask[i]=true;const b=state.balance;scores[i]=state.mode==='ENERGY_ONLY'?f.cost[0]:b?f.cost[0]/b.scales[0]+f.cost[1]/b.scales[1]+b.dual[0]*f.cost[2]*b.classFactors[0]+b.dual[1]*f.cost[3]*b.classFactors[1]+3*f.cost[4]:f.cost.reduce((s,v,j)=>s+WEIGHTS[j]*v,0);
  const r=a.route??'',free=['CPU','GPU','NPU'].map(b=>!obs.owners.some(o=>rc.slot(o.route)===b)?1:0);
  const row=[1,Number(q.task==='classification'),Number(r.endsWith('_CPU')),Number(r.endsWith('_GPU')),Number(r.endsWith('_NPU')),Number(a.kind==='WAIT'||a.kind==='WAIT_EVENT'),Number(q.priority==='urgent'),(obs.time-q.arrival)/10,(q.deadline-obs.time)/2,a.nom.response/2,a.nom.occupied/2,a.ATC/5,obs.ready.length/64,obs.ready.filter(q=>q.priority==='urgent').length/64,...free,(obs.sensor.AP-30)/10,past.power()/10,obs.wait_used_s/12,obs.owners.length/3,...f.cost,(f.AP_end-30)/10,(visible.horizon_s-obs.time)/100,(f.candidate_response===null?10:f.candidate_response-obs.time)/2,f.nominal_unfinished/8,a.wait_s??0,(obs.time-obs.sensor.time)/3];
  if(state.balance)row[31]=a.kind==='WAIT_EVENT'?-1:Number(a.kind==='DISPATCH'&&a.route===obs.preferred_routes[q.ordinal]);if(row.length!==WIDTH||row.some(v=>!Number.isFinite(v)))throw Error('Public feature ABI');x[i]=row.map(v=>Math.max(-10,Math.min(10,v)));
 }
 const bank={x,mask,scores,time_ns:Math.round(obs.time*1e9),actions:actions.map(a=>({kind:a.kind,ordinal:a.ordinal,route:a.route,wait_s:a.wait_s})),forecasts,
  constraints:{physical_slots_only:true,deadline_action_mask:false,critical_request_override:false,fixed_ATC_prior:false,post_NN_override:false},ready_total:obs.ready.length,forecast_ready:forecastReady.length,decision_ready:ready.length,forecast_horizon_s:visible.horizon_s,representation:state.variant??'BASE'};
 const index=['EXACT','ENERGY_ONLY'].includes(state.mode)?scores.slice(0,actions.length).reduce((best,v,i)=>v<scores[best]?i:best,0):state.choose(bank);
 if(!mask[index])throw Error('Illegal NN action; no rescue/fallback');const selected={...bank.actions[index],forecast_calls:actions.length,decision_index:index,bank_digest:require('node:crypto').createHash('sha256').update(JSON.stringify({x,mask})).digest('hex')};
 if(selected.kind==='WAIT')state.waitByHead.set(head.ordinal,(state.waitByHead.get(head.ordinal)??0)+selected.wait_s);
 return selected;
}
const cacheStats=()=>({queries:state?.forecasts??0,computations:state?.actual??0,hits:state?.hits??0,capacity:27,numerical_failures:state?.numerical_failures??0});
const contextStats=()=>({task_seen:state?.taskTrace??[],preferences:state?.preferenceTrace??[],scope:'Seen-ready public task metadata only; preference is a feature/nominal continuation, never an actual action mask.'});module.exports={select,configure,cacheStats,contextStats,WIDTH,ACTIONS};
