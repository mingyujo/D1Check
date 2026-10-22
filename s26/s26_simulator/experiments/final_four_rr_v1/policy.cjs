
'use strict';
const rr=require('./select.cjs');let state;
function configure(options){if(options.method!=='RR')throw Error('RR only');state={...options,cursor:0,none:[],turns:[],calls:0};}
function select(obs){state.calls++;const before=state.cursor,a=rr.select(obs,state.method,state.order,before);if(a.kind==='DISPATCH')state.cursor=a.rr_next;
 state.turns.push({time:obs.time,before,after:state.cursor,capacity:obs.capacity,ready:obs.ready.map(q=>q.ordinal),owners:obs.owners.map(o=>({ordinal:o.ordinal,route:o.route})),action:a});
 if(a.kind==='NONE')state.none.push({time:obs.time,capacity:obs.capacity,owners:obs.owners.map(o=>({ordinal:o.ordinal,route:o.route})),ready_counts:{classification:obs.ready.filter(q=>q.task==='classification').length,detection:obs.ready.filter(q=>q.task==='detection').length},action:a});return a;
}
module.exports={configure,select,none:()=>state.none,turns:()=>state.turns,cacheStats:()=>({queries:0,computations:0,hits:0,numerical_failures:0}),contextStats:()=>({preferences:[],task_seen:[],pure:true,RR_definition:'nonpreemptive task queue RR',next_queue:rr.QUEUES[state.cursor],selector_calls:state.calls})};
