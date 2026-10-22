'use strict';
const fs=require('fs'),path=require('path');
const H=__dirname,R=path.resolve(H,'../../..'),O=path.join(R,'a24_simulator/results/A24_THERMAL_DIRECTION_20261021_02');
const {DirectionPhysics, directionA24Profile}=require('./calibrated_profile.cjs');
const read=p=>JSON.parse(fs.readFileSync(path.join(O,p),'utf8'));const input=read('INPUTS.json'),oof=new Map(read('OOF_PREDICTIONS.json').cases.map(c=>[c.session,c]));
const results=[];let checks=0,maxTemp=0,maxPartition=0;
for(const c of input.cases){
 const held=oof.get(c.session),model=read(`${c.family}_OUTER_${held.outer_fold}.json`).model;
 if(model.training_groups.includes(c.group))throw Error('Held group leaked into fit');
 const context={initial_ap_c:c.initial_c,pre_slope_C_s:c.pre_slope_C_s};
 const profile=directionA24Profile(input.original_profile,model,context),p=profile.createPhysics();
 const ev=c.owners.flatMap(o=>[{t:o.start_s,kind:1,o},{t:o.end_s,kind:0,o}]).sort((a,b)=>a.t-b.t||a.kind-b.kind||a.o.id.localeCompare(b.o.id));
 let i=0,t=35;const active=new Map(),values=[];
 while(i<ev.length&&ev[i].t<=35){const e=ev[i++];if(e.kind)active.set(e.o.id,e.o);else active.delete(e.o.id);}
 for(let q=0;q<c.observations.length;q++){
  const target=c.observations[q].t;
  while(t<target-1e-10){
   while(i<ev.length&&ev[i].t<=t+1e-10){const e=ev[i++];if(e.kind){active.set(e.o.id,e.o);p.z=1;}else active.delete(e.o.id);}
   const end=Math.min(target,t+.1,i<ev.length?ev[i].t:Infinity);if(end<=t)throw Error('No progress');p.advance(end-t,[...active.values()]);t=end;
  }
  const err=Math.abs(p.temperature()-held.AP_C[q]);maxTemp=Math.max(maxTemp,err);if(err>1e-8)throw Error('Matrix/runtime mismatch');checks++;
  values.push(p.temperature());
 }
 const clone=p.clone(),restored=profile.fromPublic(p.exportState());
 for(const n of [clone,restored]){n.advance(1.25,[]);checks++;}
 if(Math.abs(clone.T-restored.T)>1e-10||Math.abs(clone.H-restored.H)>1e-8||Math.abs(clone.J-restored.J)>1e-8)throw Error('Clone/restore mismatch');
 const one=p.clone(),two=p.clone();one.advance(2,[]);two.advance(.7,[]);two.advance(1.3,[]);
 const diff=Math.max(Math.abs(one.T-two.T),Math.abs(one.H-two.H));maxPartition=Math.max(maxPartition,diff);if(diff>1e-8)throw Error('Thermal partition invariance');checks++;
 results.push({session:c.session,AP_C:values,end_state:p.exportState()});
}
// Runtime completeness is separate from empirical qualification.
if(!Number.isFinite(new DirectionPhysics(input.original_profile,read('m8_DEPLOYMENT_MODEL.json'),{initial_ap_c:28,pre_slope_C_s:0}).T))throw Error('Deployment model init');
fs.writeFileSync(path.join(O,'RUNTIME_REPLAY.json'),JSON.stringify({status:'PASS',cases:results,checks,maxTemp,maxPartition,new_policy_environments:0}),{flag:'wx'});
process.stdout.write(JSON.stringify({status:'RUNTIME_MATH_PASS',cases:results.length,checks,maxTemp,maxPartition})+'\n');
