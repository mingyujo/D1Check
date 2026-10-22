'use strict';
const assert=require('node:assert/strict');
const C=require('./common.cjs'),{fs,path}=C,packet=C.read(C.packetPath),inputs=C.read(path.join(C.HERE,'INPUTS.json')).inputs;
const old=path.join(C.ROOT,'experiments/multiresource_v1/source/MULTI001_G004'),fresh=path.join(C.HERE,'source');
const oldCost=require(path.join(old,'multi_cost.cjs')),newCost=require(path.join(fresh,'multi_cost.cjs')),tm=require(path.join(fresh,'multi_timing.cjs'));
const oldActions=require(path.join(old,'multi_actions.cjs')),newActions=require(path.join(fresh,'multi_actions.cjs'));let checks=0,forecasts=0,maxJ=0,maxAP=0;
for(const x of inputs){assert.equal(x.requests.length,x.n);assert.equal(x.requests.filter(q=>q.priority==='normal').length,x.n/4);assert.equal(new Set(x.requests.map(q=>q.ordinal)).size,x.n);checks+=3;for(const q of x.requests){assert.equal(q.deadline_ms,q.priority==='urgent'?800:2000);assert.ok(q.offset_ns>=35e9&&q.offset_ns<(35+x.duration_s)*1e9);checks+=2;}}
for(const n of [128,512]){const a=inputs.find(x=>x.n===n&&x.n/x.duration_s===8),b=inputs.find(x=>x.id==='LONG256');for(let i=0;i<n;i++){for(const k of ['ordinal','offset_ns','task_id','priority','deadline_ms']){assert.equal(a.requests[i][k],b.requests[i][k]);checks++;}}}
for(const spec of C.p0Cases()){
 const raw=C.read(spec.old_raw),decisions=raw.policy_decisions;
 for(const index of [0,Math.floor(decisions.length/2),decisions.length-1]){
  const obs=decisions[index].public_observation,nom=tm.nominal(packet),model=packet.multi.models[spec.config.model];
  const a=oldActions.select(obs,packet,nom,spec.config),b=newActions.select(obs,packet,nom,spec.config);
  assert.equal(a.kind,b.kind);assert.equal(a.ordinal,b.ordinal);assert.equal(a.route,b.route);checks+=3;
  for(const first of [null,...a.candidates.map(f=>({ordinal:a.ordinal,route:f.route}))]){
   const roll=oldCost.rollout(obs,packet,nom,model,first),x=oldCost.evaluate(obs,packet,roll,model),y=newCost.evaluate(obs,packet,roll,model);forecasts++;
   maxJ=Math.max(maxJ,Math.abs(x.J-y.J));maxAP=Math.max(maxAP,Math.abs(x.AP_area-y.AP_area));
   for(const k of ['J','AP_area','peak']){assert.ok(Math.abs(x[k]-y[k])<1e-7,k+' '+Math.abs(x[k]-y[k]));checks++;}
   assert.equal(x.misses,y.misses);checks++;
  }
 }
 // Independent closed-form constant baseline extreme, without a plant rollout.
 const scenario=packet.scenarios.find(s=>s.id===spec.config.scenario),zero=Array.from({length:9},()=>[]);
 assert.ok(Math.abs(C.energy(packet,scenario,zero,0,180)-180*C.baseline(packet,scenario))<1e-12);checks++;
}
assert.ok(forecasts<=1000);C.write(path.join(C.HERE,'PURE_TEST_RESULT.json'),{status:'PASS',checks,forecasts,max_J_difference:maxJ,max_AP_area_difference:maxAP,new_policy_environments:0,new_fit:0,new_RL:0});
console.log(JSON.stringify({status:'PASS',checks,forecasts,maxJ,maxAP}));
