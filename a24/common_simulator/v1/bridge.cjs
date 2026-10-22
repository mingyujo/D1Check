'use strict';
const fs=require('fs'),path=require('path'),{a24Profile,s26Profile,matchedResourceScenario,S26Physics}=require('./profiles.cjs');
const {Engine}=require('./engine.cjs'),method=require('./method.cjs');
const V=path.resolve(__dirname,'../../a24_simulator/experiments/s26_virtual_transfer_20261018/vendor/s26_simulator/experiments');
const {Physics:NativeS26}=require(path.join(V,'route_group_learning_v1/physics.cjs'));
const DATA=path.resolve(__dirname,'../../a24_simulator/experiments/a24_s26_common_20261020/PROFILES.json');
function loadProfile(device,{scenario='COMMON_BACKEND1_CPU3',data=JSON.parse(fs.readFileSync(DATA))}={}){
 if(!['A24','S26'].includes(device))throw Error('Known device profile required');
 const p=device==='A24'?a24Profile(data.A24):s26Profile(data.S26);
 if(scenario==='COMMON_BACKEND1_CPU3')return matchedResourceScenario(p);
 if(scenario==='LEGACY_REFERENCE')return p;
 throw Error('Explicit resource scenario');
}
function a24Observation(source,profile,observedMetadata={}){
 const request=q=>{q={...(observedMetadata[q.request_id]??{}),...q};if(!Number.isFinite(q.queue_entry_ns)||!Number.isInteger(q.ordinal)||q.queue_entry_ns>source.now_ns)throw Error('Observed A24 request entry/ordinal required');return {id:q.request_id,ordinal:q.ordinal,task:q.task,priority:q.priority,arrival_s:q.scheduled_arrival_ns/1e9,ready_s:q.queue_entry_ns/1e9,deadline_s:q.deadline_ns/1e9};};
 const owners=source.owners.map(o=>({...request(o),route:o.route,stage:o.stage,phase_progress_public:o.public_progress_s,phase_elapsed_s:(source.now_ns-o.phase_start_ns)/1e9,dispatch_s:o.dispatch_ns/1e9,response_s:o.response_ns===null?null:o.response_ns/1e9}));
 const phys=profile.fromPublic({T:source.sensor.temperature_c,z:source.sensor.shared_z,J:source.sensor.increment_so_far??0,H:0,time:source.now_ns/1e9});phys.advance(0,owners);
 return {time_s:source.now_ns/1e9,queue:source.queue.map(request),owners,sensor:{temperature_c:phys.temperature(),ambient_c:phys.ambient_c,power:phys.power(),cost_state:phys.exportState()},wait_used_s:source.wait_used_ns/1e9,dispatch_stop_s:source.dispatch_stop_s??source.now_ns/1e9+60};
}
function s26Observation(source,readyTimes,{scenario='COMMON_BACKEND1_CPU3',data=JSON.parse(fs.readFileSync(DATA))}={}){
 const key=q=>'s26-'+q.ordinal,task=q=>q.task==='classification'||q.route?.startsWith('classification_')?'C':'D';
 const request=q=>{if(!Number.isFinite(readyTimes[q.ordinal])||readyTimes[q.ordinal]>source.time+1e-9)throw Error('Observed ready entry time required; arrival is not an implicit replacement');return {id:key(q),ordinal:q.ordinal,task:task(q),priority:q.priority==='urgent'?'U':'N',arrival_s:q.arrival,ready_s:readyTimes[q.ordinal],deadline_s:q.deadline};};
 const nativeData={...data.S26,context:source.physics_context,pre_activity:source.cost_state.activity9.intervals},profile=loadProfile('S26',{scenario,data:{...data,S26:nativeData}});
 const phys=new S26Physics(nativeData,NativeS26.fromPast(nativeData.power,nativeData.thermal,nativeData.context,nativeData.pre_activity,source.time));
 const owners=source.owners.map(o=>{
  const q=request(o),route=o.route.split('_').at(-1),phases=profile.nominalPhases(q,route,phys.temperature()),keys=['dispatch','execution_start','host_inference_start','host_inference_return','output_ready'];let stage=0;
  for(let k=1;k<keys.length;k++)if(Number.isFinite(o.times?.[keys[k]]))stage=k;
  const elapsed=Math.max(0,source.time-(o.times?.[keys[stage]]??o.dispatch)),nom=method.estimate(profile,{sensor:{temperature_c:phys.temperature(),cost_state:phys.exportState()},owners:[]},q,route);
  const workRate=stage===2?1/Math.max(1e-9,nom.occupied-phases.filter((ph,k)=>k!==2).reduce((s,ph)=>s+ph.work,0)):1;
  return {...q,route,stage,phase_elapsed_s:elapsed,phase_progress_public:Math.min(phases[stage].work,elapsed*workRate),dispatch_s:o.dispatch,response_s:q.task==='C'?(o.times?.output_ready??null):(o.times?.readback_end??null)};
 });
 return {profile,snapshot:{time_s:source.time,queue:source.ready.map(request),owners,sensor:{temperature_c:phys.temperature(),ambient_c:phys.ambient_c,power:phys.power(),cost_state:phys.exportState(),raw_sample:{temperature_c:source.sensor.AP,time_s:source.sensor.time}},wait_used_s:source.wait_used_s??0,dispatch_stop_s:source.dispatch_stop_s??source.horizon_s}};
}
function frame(snapshot,bank,index){return {version:method.VERSION,split:'TRAIN',x:bank.x,mask:bank.mask,teacher_mask:method.compatibleTargets(snapshot,bank,index),group:bank.actions[index].kind==='DISPATCH'?snapshot.queue.find(q=>q.id===bank.actions[index].id).task+'_'+bank.actions[index].route:bank.actions[index].kind};}
function describe(profile){return {version:method.VERSION,device:profile.id,resource_scenario:profile.resource_scenario??'LEGACY_REFERENCE',owner_capacity:profile.owner_capacity,cpu_service_workers:profile.cpu_service_workers,allowed:profile.allowed,response_contract:profile.response_contract,resource_evidence:profile.resource_evidence,energy_unit:profile.energy_unit,energy_scale:profile.energy_scale,assumptions:profile.assumptions,feature_names:method.FEATURE_NAMES,feature_width:method.WIDTH,max_actions:method.MAX_ACTIONS};}
if(require.main===module){if(process.argv[2]!=='describe')throw Error('Explicit describe required; no automatic environment or training');console.log(JSON.stringify(['A24','S26'].map(id=>describe(loadProfile(id))),null,2));}
module.exports={loadProfile,a24Observation,s26Observation,frame,describe};
