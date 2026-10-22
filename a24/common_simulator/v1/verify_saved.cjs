'use strict';
const fs=require('fs'),path=require('path'),assert=require('assert/strict'),crypto=require('crypto');
const {a24Profile}=require('./profiles.cjs'),{loadProfile,a24Observation,s26Observation,frame,describe}=require('./bridge.cjs'),m=require('./method.cjs');
const H=path.resolve(__dirname,'../../a24_simulator/experiments/a24_s26_common_20261020');
const input=JSON.parse(fs.readFileSync(path.join(H,'SAVED_CHECK_INPUTS.json'))),data=JSON.parse(fs.readFileSync(path.join(H,'PROFILES.json')));
let checks=0,max_error=0;const ok=(v,msg)=>{checks++;assert.ok(v,msg);},near=(a,b)=>{max_error=Math.max(max_error,Math.abs(a-b));ok(Number.isFinite(a)&&Number.isFinite(b)&&Math.abs(a-b)<1e-8,`${a} != ${b}`);};
for(const x of input.A24_one_step){const p=a24Profile(data.A24),phys=p.fromPublic({T:x.state.temperature_c,z:x.state.shared_z,J:0,H:0,time:35}),owners=x.active.map(a=>({id:a.request_id,task:a.task,route:a.route,stage:a.stage}));phys.advance(x.dt,owners);for(const [k,v] of Object.entries({T:phys.T,z:phys.z,J:phys.J,H:phys.H}))near(v,x.expected[k]);}
const observations=[];
for(const x of input.public_observations){
 let profile,snapshot;
 if(x.device==='A24'){profile=loadProfile('A24');snapshot=a24Observation(x.snapshot,profile,x.metadata);}
 else({profile,snapshot}=s26Observation(x.snapshot,x.ready_times));
 const before=JSON.stringify(snapshot),profileBefore=JSON.stringify(describe(profile));
 const nativeLegal=snapshot.owners.every(o=>snapshot.owners.filter(v=>v.route===o.route).length<=profile.owner_capacity[o.route]);
 if(!nativeLegal){
  // A saved CPU3-owner state cannot be relabelled as backend1. Explicitly reject it.
  assert.throws(()=>m.encode(profile,snapshot),/exceeds selected resource scenario/);checks++;
  observations.push({device:x.device,time_s:snapshot.time_s,status:'REJECTED_NATIVE_RESOURCE_STATE',reason:'Legacy state exceeds matched backend-owner capacity; initialize a new registered scenario instead.'});continue;
 }
 const bank=m.encode(profile,snapshot,{max_steps:800});ok(bank!==null,'At least one supported free action');
 ok(bank.x.length===27&&bank.x.every(row=>row.length===50&&row.every(Number.isFinite)),'Common features');
 ok(JSON.stringify(snapshot)===before&&JSON.stringify(describe(profile))===profileBefore,'No observation/profile mutation');
 const i=m.teacher(bank);ok(bank.mask[i]===true,'Legal common teacher');
 ok(bank.forecasts.every(f=>f.no_future_arrivals&&f.no_future_latents&&f.comparison_complete),'Visible-only common comparison');
 ok(bank.forecasts.every(f=>Math.abs(f.H_s-bank.forecasts[0].H_s)<1e-8),'Every candidate same horizon');
 const ids=new Set([...snapshot.queue,...snapshot.owners].map(q=>q.id));ok(bank.forecasts.every(f=>f.visible_ids.every(id=>ids.has(id))),'No unseen ID');
 const labels=m.compatibleTargets(snapshot,bank,i);ok(labels[i],'Compatible target includes exact teacher');
 for(const mode of ['FIFO','EDF','LSF','RR']){const a=m.baseline(profile,mode)(snapshot);ok(a.kind==='DISPATCH'||a.kind==='RESOURCE_WAIT','Shared baseline action');}
 observations.push({device:x.device,time_s:snapshot.time_s,status:'PASS',queue:snapshot.queue.length,owners:snapshot.owners.length,candidates:bank.actions.length,visible:bank.visible_ids.length,teacher:bank.actions[i],reduced_horizon:bank.forecasts[0].horizon_reduced,horizon_s:bank.forecasts[0].H_s,NN_abi:[27,50],new_environment:0});
 console.log('COMMON_SAVED_STATE',x.device,snapshot.time_s,bank.actions.length,'actions',bank.visible_ids.length,'visible');
}
for(const device of ['A24','S26'])ok(observations.some(x=>x.device===device&&x.status==='PASS'),device+' real saved states validated');
const result={status:'PASS',checks,max_error,one_step_physics:input.A24_one_step.length,observations,matched_resource_rejections:observations.filter(x=>x.status!=='PASS').length,new_environment:0,new_training:0,new_NN_execution:0,legacy_result_overwritten:0,profiles:['A24','S26'].map(id=>describe(loadProfile(id))),source_sha256:crypto.createHash('sha256').update(fs.readFileSync(__filename)).digest('hex')};
const output=process.argv[2]??'SAVED_STATE_VERIFICATION_V3.json';if(path.basename(output)!==output||!output.endsWith('.json'))throw Error('New local verification filename required');
fs.writeFileSync(path.join(H,output),JSON.stringify(result,null,2),{flag:'wx'});console.log('SAVED_COMMON_PASS',checks,'checks; one-step max error',max_error,'; measured episodes 0');
