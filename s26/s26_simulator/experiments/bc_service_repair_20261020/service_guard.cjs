'use strict';
// Explicit post-BC admissibility guard. Does not change the original NN or physical mask.
const edf=(a,b)=>a.deadline-b.deadline||a.arrival-b.arrival||a.ordinal-b.ordinal;
function plan(mode,obs,actions,candidates,npu){
 if(mode==='BC_FULL')return null;
 if(!['BC_DISPATCH_ONLY','BC_PROGRESS_GUARD','BC_RESOURCE_GUARD'].includes(mode))throw Error('Unknown repair');
 let allowed=actions.map((a,i)=>({a,i})).filter(x=>x.a.kind==='DISPATCH');
 const classes=obs.ready.filter(q=>q.priority==='urgent').sort(edf),normal=obs.ready.filter(q=>q.priority==='normal').sort(edf),busy=new Set(obs.owners.map(o=>o.route.split('_').at(-1)));
 let pressure=false,maxOverrun=null;
 if(mode==='BC_RESOURCE_GUARD'&&classes.length){
  let t=obs.time+(busy.has('NPU')?npu.occupied:0);maxOverrun=-Infinity;
  for(const q of classes){maxOverrun=Math.max(maxOverrun,t+npu.response-q.deadline);t+=npu.occupied;}
  pressure=maxOverrun>0;
  // CPU inference slot remains physically supported; this policy reserves it for detection.
  allowed=allowed.filter(({a})=>a.route==='detection_CPU'||a.route==='classification_NPU'||a.route==='classification_GPU'&&busy.has('NPU')&&pressure);
 }
 let reason='NO_INTENTIONAL_IDLE',forced=null;
 if(mode!=='BC_DISPATCH_ONLY'){
  const u=classes[0];const cu=u?allowed.filter(x=>x.a.ordinal===u.ordinal):[];
  const timing=x=>candidates.find(c=>c.ordinal===x.a.ordinal&&c.route===x.a.route);
  // One additional nominal occupancy is the fixed lookahead; no fitted safety margin.
  const risk=cu.length&&cu.some(x=>obs.time+timing(x).response+timing(x).occupied>=u.deadline);
  if(cu.length&&(risk||pressure)){
   const feasible=cu.filter(x=>obs.time+timing(x).response<=u.deadline);
   if(feasible.length)allowed=feasible;
   else{const fastest=Math.min(...cu.map(x=>timing(x).response));allowed=cu.filter(x=>timing(x).response===fastest);}
   reason='URGENT_NOMINAL_RISK';forced=u.ordinal;
  }else if(normal.length&&obs.time>=normal[0].deadline){
   const oldest=allowed.filter(x=>x.a.ordinal===normal[0].ordinal);
   if(oldest.length){allowed=oldest;reason='NORMAL_ALREADY_LATE_PROGRESS';forced=normal[0].ordinal;}
  }
 }
 return {mode,allowed_indices:allowed.map(x=>x.i),reason,forced_ordinal:forced,pressure,max_nominal_overrun_s:maxOverrun,
  context:{time:obs.time,capacity:obs.capacity,ready:obs.ready.map(q=>({ordinal:q.ordinal,task:q.task,priority:q.priority,arrival:q.arrival,deadline:q.deadline})),owners:obs.owners.map(o=>({ordinal:o.ordinal,route:o.route})),nominal_candidates:candidates,nominal_NPU:npu},
  constants:{urgent_lookahead_occupancies:1,normal_age_trigger:'absolute_deadline',extra_margin_s:0},
  limitations:'Nominal predictions are not certified upper bounds. This explicit guard changes original BC behavior; no actual future arrivals/progress are read.'};
}
module.exports={plan};
