'use strict';
// Separate process, explicitly registered module binding. Parent files untouched.
const fs=require('fs'),path=require('path'),z=require('zlib'),crypto=require('crypto'),H=__dirname,R=path.resolve(H,'../..'),P=path.join(R,'experiments/route_energy_v1'),O=path.join(H,'artifacts/G001');
const read=p=>JSON.parse((p.endsWith('.gz')?z.gunzipSync(fs.readFileSync(p)):fs.readFileSync(p)).toString('utf8').replace(/^\uFEFF/,'')),sha=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex'),write=(p,x)=>fs.writeFileSync(p,JSON.stringify(x)+'\n',{flag:'wx'}),append=(p,x)=>{const fd=fs.openSync(p,'a');try{fs.writeSync(fd,JSON.stringify(x)+'\n');fs.fsyncSync(fd);}finally{fs.closeSync(fd);}};
const op=read(path.join(H,'OPERATION.json'));if(fs.existsSync(O))throw Error('Consumed witness namespace; no retry');fs.mkdirSync(O,{recursive:true});
const packet=read(path.join(R,'experiments/multiresource_v1/PACKET.json.gz')),power=read(path.join(R,'experiments/capacity_power_v1/artifacts/G001/MODEL.json')),thermal=read(path.join(R,'experiments/pipeline_thermal_v1/artifacts/G001/MODEL.json')),cases=read(path.join(P,'INPUTS.json')).cases;
packet.multi.models.CPU3={...packet.multi.models.CENTRAL,cpu_workers:3};packet.multi.models.CENTRAL.cpu_workers=1;
const policy=require(path.join(P,'policy.cjs')),rc=require(path.join(P,'source/resource_contract.cjs')),{MultiSimulator}=require(path.join(P,'source/multi_simulator.cjs')),parent={rows:fs.readdirSync(path.join(P,'artifacts/G001')).filter(n=>/^REFERENCE_.*\.json$/.test(n)).map(n=>read(path.join(P,'artifacts/G001',n)))};
let mode,assignment,assignment_trace,counter,count=0,rows=[],selection=null;const begin=Date.now();
policy.select=obs=>{
 for(const q of obs.ready.slice().sort((a,b)=>a.arrival-b.arrival||a.ordinal-b.ordinal))if(q.task==='classification'&&!assignment.has(q.ordinal)){
  const route=mode==='CPU_ONLY'?'CPU':mode==='GPU_ONLY'?'GPU':mode==='NPU_ONLY'?'NPU':mode==='SPLIT75'?(counter%4===3?'GPU':'NPU'):(counter%8===7?'GPU':'NPU');assignment.set(q.ordinal,'classification_'+route);assignment_trace.push({ordinal:q.ordinal,observed_time:obs.time,route:'classification_'+route,index:counter});counter++;
 }
 const eligible=obs.ready.map(q=>({q,route:q.task==='detection'?'detection_CPU':assignment.get(q.ordinal)})).filter(x=>rc.legal(x.route,obs.owners,obs.capacity)).sort((a,b)=>a.q.deadline-b.q.deadline||a.q.arrival-b.q.arrival||a.q.ordinal-b.q.ordinal);
 return eligible.length?{kind:'DISPATCH',ordinal:eligible[0].q.ordinal,route:eligible[0].route,forecast_calls:0}:{kind:'NONE'};
};
function simulate(c,model,m,kind,i){
 for(const p of op.pins)if(sha(p.path)!==p.sha256)throw Error('Witness source drift '+p.path);
 if(count>=op.environment_cap||(Date.now()-begin)/1000>op.wall_cap_s)throw Error('Finite witness cap');
 mode=m;assignment=new Map;assignment_trace=[];counter=0;policy.configure({mode:'WITNESS',variant:'REPAIR'});
 const label=kind+'_'+model+'_'+i+'_'+mode,start={event:'START',utc:new Date().toISOString(),label,input:c.id,model,method:mode,selection_sha256:selection,stream:c.stream};append(path.join(O,'receipts.jsonl'),start);count++;
 try{
  const sim=new MultiSimulator(packet,{id:c.id,context:c.context,requests:c.requests},{stream:c.stream,model,capacity:3,policy:'WITNESS',allocator:'CAUSAL_FIXED_ROUTE_EDF',dt_s:.01,power_dt_s:.025,horizon_s:c.horizon_s,dispatch_stop_s:c.dispatch_stop_s,censor_s:c.censor_s,forecast_cap:1000000,nominal_event_cap:20000,power_model:power,thermal_model:thermal}),r=sim.run();
  r.witness_assignment=assignment_trace;r.witness_method=mode;r.witness_new_RL=0;
  const bytes=z.gzipSync(Buffer.from(JSON.stringify(r)),{level:4});fs.writeFileSync(path.join(O,label+'.raw.json.gz'),bytes,{flag:'wx'});
  const ref=parent.rows.find(x=>x.input===c.id&&x.model===model&&x.seed===481083&&x.kind===(kind==='TRAIN_DIAGNOSIS'?'TRAIN_REFERENCE':kind));if(!ref)throw Error('No matched parent frozen reference');
  const row={label,kind,input:c.id,model,method:mode,n:c.n,mix:c.mix,service:r.service,J:r.physics_J,AP_mean:r.AP_mean,AP_peak:r.AP_peak_sampled,unfinished:r.unfinished,extra_CPU_core_s:r.extra_cpu_core_s,shared_CPU_wait_s:r.shared_cpu_wait_s,observation_s:r.observation_end_s,routes:r.policy_route_counts,reference_frozen_label:ref.label,reference_frozen_J:ref.J,reference_frozen_AP:ref.AP_mean,reference_frozen_service:ref.service,J_delta_frozen_percent:100*(r.physics_J/ref.J-1),AP_delta_frozen_C:r.AP_mean-ref.AP_mean,raw_sha256:sha(path.join(O,label+'.raw.json.gz')),physical_validation:false};
  rows.push(row);write(path.join(O,label+'.json'),row);append(path.join(O,'receipts.jsonl'),{...start,event:'COMPLETE',utc:new Date().toISOString(),raw_sha256:row.raw_sha256});console.log(JSON.stringify({count,label,on:r.service.all.on_time,n:c.n,J:r.physics_J,delta_frozen_percent:row.J_delta_frozen_percent}),null,0);
 }catch(e){append(path.join(O,'receipts.jsonl'),{...start,event:'FAIL',error:String(e.stack||e),automatic_retry:false});write(path.join(O,'FAILURE.json'),{error:String(e.stack||e),consumed:count,automatic_retry:false});throw e;}
}
for(const phase of ['TRAIN']){
 const inputs=cases.filter(c=>c.phase===phase&&c.nominal_load_ratio===.85&&(phase!=='TRAIN'||c.n===1024));
 for(let i=0;i<inputs.length;i++)for(const model of ['CENTRAL','CPU3'])for(const m of ['CPU_ONLY','GPU_ONLY','NPU_ONLY','SPLIT75','SPLIT87'])if(!(model==='CPU3'&&m==='CPU_ONLY'))simulate(inputs[i],model,m,phase==='TRAIN'?'TRAIN_DIAGNOSIS':phase,i);
 if(phase==='DEV'){
  const chosen={},scores=[];
  for(const model of ['CENTRAL','CPU3']){
   const options=[];for(const m of ['CPU_ONLY','GPU_ONLY','NPU_ONLY','SPLIT75','SPLIT87']){const rr=rows.filter(r=>r.kind==='DEV'&&r.model===model&&r.method===m);if(!rr.length)continue;const harm=rr.reduce((s,r)=>s+['urgent','normal'].reduce((a,k)=>a+Math.max(0,(r.reference_frozen_service[k].on_time-r.service[k].on_time)/r.service[k].planned-.005)**2,0),0),energy=rr.reduce((s,r)=>s+r.J/r.reference_frozen_J,0)/rr.length,missing=rr.reduce((s,r)=>s+r.unfinished,0);options.push({method:m,key:[missing,harm,energy,m],gate:missing===0&&harm<1e-12&&energy<=.95,energy});}
   options.sort((a,b)=>{for(let j=0;j<4;j++){if(a.key[j]<b.key[j])return -1;if(a.key[j]>b.key[j])return 1;}return 0;});chosen[model]=options[0];scores.push({model,options});
  }
  write(path.join(O,'SELECTION_FROZEN.json'),{utc:new Date().toISOString(),chosen,scores,conditional_new_RL_gate:Object.values(chosen).some(c=>c.gate),rule:'DEV only; missing, squared class deficit beyond0.5pp, energy, name'});selection=sha(path.join(O,'SELECTION_FROZEN.json'));
 }
}
if(count!==18||rows.length!==18)throw Error('Full18 witness census');
write(path.join(O,'RESULT.json'),{status:'ALL18_TRAIN_ROUTE_PILOTS_COMPLETE',START:count,COMPLETE:count,FAIL:0,rows,selection_sha256:selection,physical_validation:false,new_RL:0});write(path.join(O,'COMPLETE.json'),{utc:new Date().toISOString(),START:count});console.log('WITNESS_COMPLETE',count);
