
'use strict';
const QUEUES=['classification','detection'],RESOURCES=['GPU','NPU','CPU'];
function select(obs,method,order,cursor){
 if(method!=='RR'||![0,1].includes(cursor)||order.join('|')!==RESOURCES.join('|'))throw Error('Unregistered RR definition');
 const busy=new Set(obs.owners.map(o=>o.route.split('_').at(-1))),none={kind:'NONE',forecast_calls:0,rr_before:cursor,rr_next:cursor};
 if(obs.owners.length>=obs.capacity)return {...none,reason:'CAPACITY'};
 for(let step=0;step<2;step++){
  const qi=(cursor+step)%2,task=QUEUES[qi],routes=task==='detection'?['CPU']:order;
  const free=routes.filter(r=>!busy.has(r));if(!free.length)continue;
  const ready=obs.ready.filter(q=>q.task===task).sort((a,b)=>a.arrival-b.arrival||a.ordinal-b.ordinal);if(!ready.length)continue;
  return {kind:'DISPATCH',ordinal:ready[0].ordinal,route:task+'_'+free[0],forecast_calls:0,policy:'NONPREEMPTIVE_TASK_QUEUE_RR',rr_before:cursor,rr_next:1-qi,rr_selected_queue:task,rr_skipped_queue:step===1,resource_order:order.slice()};
 }
 return {...none,reason:'NO_PHYSICALLY_EXECUTABLE_QUEUE'};
}
module.exports={select,QUEUES};
