'use strict';const rc=require('./source/resource_contract.cjs');let mode;
function configure(x){mode=x.mode;if(!['EDF_CPU_RESERVED','EDF_GPU_FIXED'].includes(mode))throw Error('Unknown static control');}
function select(obs){const sorted=obs.ready.slice().sort((a,b)=>a.deadline-b.deadline||a.arrival-b.arrival||a.ordinal-b.ordinal);for(const q of sorted){const routes=q.task==='detection'?['detection_CPU']:mode==='EDF_GPU_FIXED'?['classification_GPU']:['classification_GPU','classification_NPU'];for(const route of routes)if(rc.legal(route,obs.owners,obs.capacity))return {kind:'DISPATCH',ordinal:q.ordinal,route,forecast_calls:0};}return {kind:'NONE'};}
const cacheStats=()=>({queries:0,computations:0,hits:0,capacity:0,numerical_failures:0});module.exports={configure,select,cacheStats};
