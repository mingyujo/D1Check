'use strict';
const crypto=require('crypto'),rc=require('./resource_contract.cjs'),timing=require('./multi_timing.cjs'),cost=require('./multi_cost.cjs');
const digest=x=>crypto.createHash('sha256').update(JSON.stringify(x)).digest('hex');
const memo=new WeakMap(),CACHE_CAPACITY=4096;
function cacheStats(packet){const s=memo.get(packet);return {queries:s?.queries??0,hits:s?.hits??0,computations:s?.computations??0,capacity:CACHE_CAPACITY}}
function frozen(x){if(x&&typeof x==='object'&&!Object.isFrozen(x)){for(const v of Object.values(x))frozen(v);Object.freeze(x)}return x}
function forecast(obs,packet,nom,model,first,publicSHA){let s=memo.get(packet);if(!s){s={values:new Map,queries:0,hits:0,computations:0};memo.set(packet,s)}s.queries++;const key=publicSHA+'|'+JSON.stringify(model)+'|'+JSON.stringify(first);if(s.values.has(key)){const value=s.values.get(key);s.values.delete(key);s.values.set(key,value);s.hits++;return value}s.computations++;const value=frozen(cost.evaluate(obs,packet,cost.rollout(obs,packet,nom,model,first),model));s.values.set(key,value);if(s.values.size>CACHE_CAPACITY)s.values.delete(s.values.keys().next().value);return value}
function select(obs,packet,nom,config){
 const model=packet.multi.models[config.model],legalQs=obs.ready.filter(q=>rc.allowed(q).some(r=>rc.legal(r,obs.owners,config.capacity)));if(!legalQs.length)return {kind:'NONE',candidates:[]};
 const fastest=q=>Math.min(...rc.allowed(q).map(r=>timing.lengths(packet,nom,r,obs.sensor.AP,[],model,q.priority).response)),meanP=legalQs.reduce((s,q)=>s+fastest(q),0)/legalQs.length;
 const atc=q=>{const p=fastest(q);return 1/p*Math.exp(-Math.max(q.deadline-obs.time-p,0)/(2*Math.max(meanP,1e-9)))};
 legalQs.sort((a,b)=>config.policy==='FIFO'?rc.FIFO(a,b):config.policy==='EDF'?a.deadline-b.deadline||rc.FIFO(a,b):atc(b)-atc(a)||rc.FIFO(a,b));
 const q=legalQs[0],request_ranks=legalQs.map(x=>({ordinal:x.ordinal,ATC:atc(x),deadline:x.deadline})),forecasts=[],publicSHA=digest(obs);
 for(const route of rc.allowed(q))if(rc.legal(route,obs.owners,config.capacity)){
  const e=forecast(obs,packet,nom,model,{ordinal:q.ordinal,route},publicSHA);forecasts.push({route,ordinal:q.ordinal,...e});
 }
 const ref=forecast(obs,packet,nom,model,null,publicSHA),bestRisk=forecasts.slice().sort((a,b)=>a.misses-b.misses||a.max_lateness-b.max_lateness)[0],tier=forecasts.filter(x=>x.misses===bestRisk.misses&&Math.abs(x.max_lateness-bestRisk.max_lateness)<1e-10);
 const scales={J:Math.max(1,Math.abs(ref.J)),H:Math.max(1,Math.abs(ref.AP_area))};for(const f of forecasts){f.score=f.J/scales.J+f.AP_area/scales.H;f.thermal_eligible=f.AP_area<=ref.AP_area+1e-8&&f.peak<=ref.peak+1e-8}
 let choices=tier,thermal_fallback=false;if(config.allocator==='NO_THERMAL_HARM'){const eligible=tier.filter(x=>x.thermal_eligible);if(eligible.length)choices=eligible;else{thermal_fallback=true;choices=tier.slice().sort((a,b)=>Math.max(0,a.AP_area-ref.AP_area)-Math.max(0,b.AP_area-ref.AP_area)||Math.max(0,a.peak-ref.peak)-Math.max(0,b.peak-ref.peak)||a.J-b.J||a.route.localeCompare(b.route));}}
 if(!thermal_fallback)choices=choices.slice().sort((a,b)=>config.allocator==='WEIGHTED'?a.score-b.score||a.route.localeCompare(b.route):a.J-b.J||a.route.localeCompare(b.route));
 const selected=choices[0];return {kind:'DISPATCH',ordinal:q.ordinal,route:selected.route,selected,reference:ref,candidates:forecasts,request_ranks,thermal_fallback,public_digest:digest(obs),forecast_calls:forecasts.length+1,planner_scope:'Public arrived queue only; estimated residual owner release, measured median phase estimates, deterministic earliest-response EDD tail. No sampled future observations.'};
}
module.exports={select,digest,forecast,cacheStats};
