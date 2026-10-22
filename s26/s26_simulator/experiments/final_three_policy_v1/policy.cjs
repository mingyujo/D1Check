 'use strict';
const pure=require('./select.cjs');let state;
function configure(options){state={...options,none:[],calls:0};}
function select(obs){state.calls++;const a=pure.select(obs,state.method,state.order);
 if(a.kind==='NONE')state.none.push({time:obs.time,capacity:obs.capacity,owners:obs.owners.map(o=>({ordinal:o.ordinal,route:o.route})),ready_counts:{classification:obs.ready.filter(q=>q.task==='classification').length,detection:obs.ready.filter(q=>q.task==='detection').length},action:a});return a;}
const cacheStats=()=>({queries:0,computations:0,hits:0,numerical_failures:0});
const contextStats=()=>({preferences:[],task_seen:[],pure:true,method:state?.method,order:state?.order,selector_calls:state?.calls});
module.exports={configure,select,cacheStats,contextStats,none:()=>state.none};
