'use strict';
// Minimal teacher inputs: physical legality, causal preferred route and EDF key.
const crypto=require('node:crypto');
const clip=x=>Math.max(-10,Math.min(10,x));
const FIFO=(a,b)=>a.arrival-b.arrival||a.ordinal-b.ordinal;
function teacher(bank){
 const valid=bank.actions.map((a,i)=>i).filter(i=>bank.mask[i]);
 const p=valid.filter(i=>bank.actions[i].kind==='DISPATCH'&&bank.x[i][31]>.5);
 if(p.length)return p.sort((i,j)=>bank.x[i][8]-bank.x[j][8]||bank.actions[i].ordinal-bank.actions[j].ordinal||i-j)[0];
 const i=valid.find(i=>bank.actions[i].kind==='WAIT_EVENT');
 if(i===undefined)throw Error('No preferred legal dispatch or owner event');return i;
}
function finish(obs,all,ready,config,state,rc){
 const actions=all.filter(a=>ready.some(q=>q.ordinal===a.q.ordinal))
  .sort((a,b)=>a.q.deadline-b.q.deadline||FIFO(a.q,b.q)||rc.ROUTES.indexOf(a.route)-rc.ROUTES.indexOf(b.route))
  .map(a=>({kind:'DISPATCH',ordinal:a.q.ordinal,route:a.route}));
 const head=obs.ready.slice().sort((a,b)=>a.deadline-b.deadline||FIFO(a,b))[0];
 for(const wait_s of [.02,.05])if(obs.time+wait_s<config.dispatch_stop_s)actions.push({kind:'WAIT',wait_s,ordinal:head.ordinal});
 if(obs.owners.length&&obs.time<config.dispatch_stop_s)actions.push({kind:'WAIT_EVENT',ordinal:head.ordinal});
 if(!state.standalone&&actions.length>27)throw Error('Original capped action limit');
 const width=state.standalone?actions.length:27,x=Array.from({length:width},()=>Array(32).fill(0)),mask=Array(width).fill(false);
 actions.forEach((a,i)=>{const q=obs.ready.find(q=>q.ordinal===a.ordinal);mask[i]=true;x[i][8]=clip((q.deadline-obs.time)/2);x[i][31]=a.kind==='WAIT_EVENT'?-1:Number(a.kind==='DISPATCH'&&a.route===obs.preferred_routes[q.ordinal]);});
 const bank={x,mask,actions,scores:[],forecasts:[],time_ns:Math.round(obs.time*1e9),ready_total:obs.ready.length,decision_ready:ready.length,
  constraints:{physical_slots_only:true,deadline_action_mask:false,critical_request_override:false,fixed_ATC_prior:false,post_NN_override:false},
  representation:state.standalone?'TEACHER_ALL_READY_NO_ATC_NO_ROLLING':'CAPPED_TEACHER_NO_ROLLING'};
 const i=state.choose(bank);if(!mask[i])throw Error('Illegal teacher action');
 return {...actions[i],forecast_calls:0,decision_index:i,bank_digest:crypto.createHash('sha256').update(JSON.stringify({x,mask})).digest('hex')};
}
function standalone(obs,config,state,rc){
 const all=[];for(const q of obs.ready)for(const route of rc.allowed(q))if(rc.legal(route,obs.owners,obs.capacity))all.push({q,route});
 if(!all.length)return {kind:'NONE',candidates:[]};
 return finish(obs,all,obs.ready,config,state,rc);
}
module.exports={finish,standalone,teacher};
