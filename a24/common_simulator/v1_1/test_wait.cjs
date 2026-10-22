'use strict';
const assert=require('assert'),old=require('../v1/method.cjs'),fixed=require('./method.cjs'),{Engine}=require('../v1/engine.cjs');
class P{constructor(){this.time=0;this.T=26;this.J=0;this.H=0;this.ambient_c=26;}clone(){return Object.assign(new P,this);}exportState(){return {...this};}temperature(){return this.T;}power(){return 1;}advance(dt,owners){this.time+=dt;this.J+=dt*(1+owners.length);this.H+=26*dt;}}
const profile={id:'SYNTHETIC',allowed:{C:['CPU','GPU'],D:['CPU']},owner_capacity:{CPU:1,GPU:1,NPU:0},cpu_service_workers:3,energy_scale:1,baselinePower:1,resource_evidence:'SYNTHETIC',response_contract:{C:'output',D:'persist'},createPhysics:()=>new P,fromPublic:s=>Object.assign(new P,s),nominalPhases:()=>[{work:.1,response_at:.08,cpu_service:true}],actualPhases:()=>[{work:.2,response_at:.18,cpu_service:true}],rate:()=>1,publicRate:()=>1,advance:(p,o,c,dt)=>p.advance(dt,o)};
const q=id=>({id,ordinal:+id,task:'C',priority:'U',arrival_s:0,ready_s:0,deadline_s:1,source_kind:'SYNTHETIC'});
let checks=0;
function snapshot(progress){return {time_s:0,dispatch_stop_s:2,queue:[q('2')],owners:[{...q('1'),route:'CPU',stage:0,phase_progress_public:progress,phase_elapsed_s:progress,response_s:null,dispatch_s:0}],sensor:{temperature_c:26,ambient_c:26,power:1,cost_state:new P().exportState()},wait_used_s:0};}
const stale=snapshot(.1),action={kind:'WAIT_EVENT'};
assert.throws(()=>old.forecast(profile,stale,action,stale.queue,1),/WAIT_EVENT requires owner/);checks++;
const out=fixed.forecast(profile,stale,action,stale.queue,1);assert.ok(out.comparison_complete!==false&&!out.capped&&out.cost.every(Number.isFinite));checks++;
assert.deepStrictEqual(fixed.encode(profile,stale).mask.map(Boolean).length,27);checks++;
const active=snapshot(.03);assert.deepStrictEqual(fixed.encode(profile,active),old.encode(profile,active));checks++;
const partial=snapshot(.1);partial.queue[0].deadline_s=.12;partial.owners.push({...q('3'),route:'GPU',stage:0,phase_progress_public:.01,phase_elapsed_s:.01,response_s:null,dispatch_s:0});
assert.ok(fixed.forecast(profile,partial,action,partial.queue,1).cost[2]<old.forecast(profile,partial,action,partial.queue,1).cost[2]);checks++;
for(const a of [{kind:'DISPATCH',id:'2',route:'GPU'},{kind:'WAIT',wait_s:.02}]){assert.deepStrictEqual(fixed.forecast(profile,stale,a,stale.queue,1),old.forecast(profile,stale,a,stale.queue,1));checks++;}
const e=new Engine(profile,[q('1'),q('2')],new P(),{start_s:0,end_s:.5});e.admit();e.dispatch({kind:'DISPATCH',id:'1',route:'CPU'});e.owners[0].public_progress=.1;
assert.equal(e.owners.length,1);assert.equal(e.done.length,0);checks++;
e.ready=[];e.owners=[];assert.throws(()=>e.apply({kind:'WAIT_EVENT'}),/requires owner/);checks++;
console.log(JSON.stringify({status:'PASS',checks,new_environment:0,new_training:0,synthetic_regression:true}));
