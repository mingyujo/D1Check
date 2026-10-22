'use strict';
// Deterministic EDF reference; no timing, thermal, energy, forecast, or NN imports.
const RESOURCE_ORDER=Object.freeze(['CPU','GPU','NPU']);
const slot=route=>route.endsWith('_GPU')?'GPU':route.endsWith('_NPU')?'NPU':route.endsWith('_CPU')?'CPU':null;
const allowed=q=>q.task==='classification'?['CPU','GPU','NPU']:q.task==='detection'?['CPU']:[];
function select(obs,resourceOrder=RESOURCE_ORDER){
 if(!Number.isFinite(obs.time)||!Number.isInteger(obs.capacity)||obs.capacity<1||obs.capacity>3)throw Error('Invalid public state');
 if(resourceOrder.length!==3||new Set(resourceOrder).size!==3||resourceOrder.some(r=>!RESOURCE_ORDER.includes(r)))throw Error('Expected fixed CPU/GPU/NPU permutation');
 const busy=new Set();
 for(const o of obs.owners){const r=slot(o.route);if(!r||busy.has(r))throw Error('Invalid/duplicate held slot');busy.add(r);}
 const ready=obs.ready.slice();
 for(const q of ready)if(!Number.isFinite(q.arrival)||!Number.isFinite(q.deadline)||!Number.isInteger(q.ordinal)||q.arrival>obs.time||!allowed(q).length)throw Error('Invalid arrived request');
 if(obs.owners.length>=obs.capacity)return {kind:'NONE',reason:'RESOURCE_WAIT',forecast_calls:0};
 const executable=ready.filter(q=>allowed(q).some(r=>!busy.has(r)));
 if(!executable.length)return {kind:'NONE',reason:'NO_EXECUTABLE_ARRIVED_REQUEST',forecast_calls:0};
 executable.sort((a,b)=>a.deadline-b.deadline||a.arrival-b.arrival||a.ordinal-b.ordinal);
 const q=executable[0],r=resourceOrder.find(r=>allowed(q).includes(r)&&!busy.has(r));
 return {kind:'DISPATCH',ordinal:q.ordinal,route:q.task+'_'+r,forecast_calls:0,
   policy:'PLAIN_EDF_FIXED_RESOURCE_ORDER',resource_order:resourceOrder.slice(),
   evidence:'Absolute deadline/arrival/ordinal only; held slots remain reserved until AVAILABLE; no voluntary WAIT'};
}
module.exports={select,RESOURCE_ORDER};
