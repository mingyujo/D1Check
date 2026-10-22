'use strict';
const rc=require('./source/resource_contract.cjs'),tm=require('./source/multi_timing.cjs'),{rollout}=require('./source/nominal_rollout.cjs'),{Physics}=require('./physics.cjs'),{select:edf}=require('../plain_edf_v1/select.cjs');
const WEIGHTS=[.5,.5,8,4,30],ACTIONS=27,WIDTH=32;let state;
function configure(options){state={...options,waitByHead:new Map,forecasts:0,calls:0};}
const FIFO=(a,b)=>a.arrival-b.arrival||a.ordinal-b.ordinal;
function ranks(obs,packet,nom,model){const candidates=[];for(const q of obs.ready)for(const r of rc.allowed(q))if(rc.legal(r,obs.owners,obs.capacity)){const p=tm.lengths(packet,nom,r,obs.sensor.AP,[],model,q.priority);candidates.push({q,route:r,p});}
 const mean=candidates.reduce((s,x)=>s+x.p.occupied,0)/Math.max(1,candidates.length);for(const c of candidates)c.ATC=Math.log((c.q.priority==='urgent'?2:1)/c.p.occupied)-Math.max(0,c.q.deadline-obs.time-c.p.response)/(2*Math.max(mean,1e-9));
 return candidates;
}
function evaluate(obs,packet,nom,model,first,past){const physics=past.clone(),J=physics.J,H=physics.H,start=physics.time;
 const roll=rollout(obs,packet,nom,model,first,physics),span=physics.time-start,APmean=(physics.H-H)/Math.max(span,1e-9),energy=physics.J-J-physics.B0*span;
 const late=roll.responses.map(r=>{const q=[...obs.ready,...obs.owners].find(q=>q.ordinal===r.ordinal);return {priority:q.priority,deadline:r.deadline,response:r.response,relative_deadline:q.deadline-q.arrival};});
 const n=Math.max(1,late.length),cost=[Math.max(0,energy)/n,Math.max(0,APmean-physics.skin)/10,0,0,0];
 for(const r of late){if(r.response===null)cost[4]+=1/n;else{const d=Math.max(0,r.response-r.deadline);cost[r.priority==='urgent'?2:3]+=(Number(d>1e-9)+.2*Math.min(5,d/Math.max(.05,r.relative_deadline)))/n;}}
 return {cost,energy,AP_mean:APmean,AP_end:physics.temperature(),candidate_response:roll.responses.find(x=>x.ordinal===first?.ordinal)?.response??null,nominal_unfinished:late.filter(x=>x.response===null).length,nominal_scope:'Candidate union plus observed owners; frozen nominal vectors; no future actual work/arrivals',forecast_calls:1};
}
function select(obs,packet,nom,config){
 const model=packet.multi.models[config.model];state.calls++;
 if(state.mode==='EDF'||state.mode==='EDF_NPU_FIRST')return edf(obs,state.mode==='EDF'?['CPU','GPU','NPU']:['NPU','GPU','CPU']);
 const all=ranks(obs,packet,nom,model);if(!all.length)return {kind:'NONE',candidates:[]};
 const ranked=all.slice().sort((a,b)=>b.ATC-a.ATC||FIFO(a.q,b.q)||a.p.response-b.p.response||a.p.occupied-b.p.occupied||a.route.localeCompare(b.route));
 if(state.mode==='ATC')return {kind:'DISPATCH',ordinal:ranked[0].q.ordinal,route:ranked[0].route,forecast_calls:0};
 const queue=obs.ready.slice().sort((a,b)=>a.deadline-b.deadline||FIFO(a,b)),set=new Set(queue.slice(0,4).map(q=>q.ordinal));set.add(obs.ready.slice().sort(FIFO)[0].ordinal);
 for(const r of ranked){set.add(r.q.ordinal);if(set.size>=Math.min(8,obs.ready.length))break;}
 const ready=queue.filter(q=>set.has(q.ordinal)).slice(0,8),visible={...obs,ready},past=Physics.fromPast(config.power_model,config.thermal_model,obs.physics_context,obs.cost_state.activity9.intervals,obs.time);
 const actions=all.filter(x=>ready.some(q=>q.ordinal===x.q.ordinal)).sort((a,b)=>a.q.deadline-b.q.deadline||FIFO(a.q,b.q)||rc.ROUTES.indexOf(a.route)-rc.ROUTES.indexOf(b.route)).map(x=>({kind:'DISPATCH',ordinal:x.q.ordinal,route:x.route,nom:x.p,ATC:x.ATC}));
 const head=queue[0];for(const wait_s of[.05,.2,.5])if(obs.wait_used_s+wait_s<=12+1e-9&&(state.waitByHead.get(head.ordinal)??0)+wait_s<=1.5+1e-9&&obs.time+wait_s<config.dispatch_stop_s)actions.push({kind:'WAIT',wait_s,ordinal:head.ordinal,nom:ranked[0].p,ATC:ranked[0].ATC});
 if(actions.length>ACTIONS)throw Error('Action capacity');
 const x=Array.from({length:ACTIONS},()=>Array(WIDTH).fill(0)),mask=Array(ACTIONS).fill(false),scores=Array(ACTIONS).fill(0),forecasts=[];
 for(let i=0;i<actions.length;i++){const a=actions[i],q=obs.ready.find(q=>q.ordinal===a.ordinal),f=evaluate(visible,packet,nom,model,a.kind==='WAIT'?{wait_s:a.wait_s}:{ordinal:a.ordinal,route:a.route},past);forecasts.push(f);state.forecasts++;mask[i]=true;scores[i]=f.cost.reduce((s,v,j)=>s+WEIGHTS[j]*v,0);
  const r=a.route??'',free=['CPU','GPU','NPU'].map(b=>!obs.owners.some(o=>rc.slot(o.route)===b)?1:0);
  const row=[1,Number(q.task==='classification'),Number(r.endsWith('_CPU')),Number(r.endsWith('_GPU')),Number(r.endsWith('_NPU')),Number(a.kind==='WAIT'),Number(q.priority==='urgent'),(obs.time-q.arrival)/10,(q.deadline-obs.time)/2,a.nom.response/2,a.nom.occupied/2,a.ATC/5,obs.ready.length/64,obs.ready.filter(q=>q.priority==='urgent').length/64,...free,(obs.sensor.AP-30)/10,past.power()/10,obs.wait_used_s/12,obs.owners.length/3,...f.cost,(f.AP_end-30)/10,(obs.horizon_s-obs.time)/100,(f.candidate_response===null?10:f.candidate_response-obs.time)/2,f.nominal_unfinished/8,0,1];
  if(row.length!==WIDTH||row.some(v=>!Number.isFinite(v)))throw Error('Public feature ABI');x[i]=row.map(v=>Math.max(-10,Math.min(10,v)));
 }
 const bank={x,mask,scores,time_ns:Math.round(obs.time*1e9),actions:actions.map(a=>({kind:a.kind,ordinal:a.ordinal,route:a.route,wait_s:a.wait_s})),forecasts,
  constraints:{physical_slots_only:true,deadline_action_mask:false,critical_request_override:false,fixed_ATC_prior:false,post_NN_override:false},ready_total:obs.ready.length,forecast_ready:ready.length};
 const index=state.mode==='EXACT'?scores.slice(0,actions.length).reduce((best,v,i)=>v<scores[best]?i:best,0):state.choose(bank);
 if(!mask[index])throw Error('Illegal NN action; no rescue/fallback');const selected={...bank.actions[index],forecast_calls:actions.length,decision_index:index,bank_digest:require('node:crypto').createHash('sha256').update(JSON.stringify({x,mask})).digest('hex')};
 if(selected.kind==='WAIT')state.waitByHead.set(head.ordinal,(state.waitByHead.get(head.ordinal)??0)+selected.wait_s);
 return selected;
}
const cacheStats=()=>({queries:state?.forecasts??0,computations:state?.forecasts??0,hits:0,capacity:0});
module.exports={select,configure,cacheStats,WIDTH,ACTIONS};
