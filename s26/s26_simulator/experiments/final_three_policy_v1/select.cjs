 'use strict';
// Pure FIFO/EDF: only arrived job ordering and held physical resources.
const RESOURCE_ORDER=['CPU','GPU','NPU'];
const slot=r=>r.split('_').at(-1),allowed=q=>q.task==='classification'?RESOURCE_ORDER:q.task==='detection'?['CPU']:[];
function select(obs,method,order){
 if(!['FIFO','EDF'].includes(method)||order.length!==3||new Set(order).size!==3||order.some(r=>!RESOURCE_ORDER.includes(r)))throw Error('Invalid frozen policy');
 const busy=new Set(obs.owners.map(o=>slot(o.route)));
 if(obs.owners.length>=obs.capacity)return {kind:'NONE',reason:'CAPACITY',forecast_calls:0};
 const runnable=obs.ready.filter(q=>allowed(q).some(r=>!busy.has(r)));
 if(!runnable.length)return {kind:'NONE',reason:'NO_PHYSICALLY_EXECUTABLE_JOB',forecast_calls:0};
 runnable.sort((a,b)=>(method==='EDF'?a.deadline-b.deadline:0)||a.arrival-b.arrival||a.ordinal-b.ordinal);
 const q=runnable[0],r=order.find(r=>allowed(q).includes(r)&&!busy.has(r));
 return {kind:'DISPATCH',ordinal:q.ordinal,route:q.task+'_'+r,forecast_calls:0,policy:'PLAIN_'+method,resource_order:order.slice()};
}
module.exports={select};
