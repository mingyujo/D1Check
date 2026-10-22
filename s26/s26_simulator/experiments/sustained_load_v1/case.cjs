'use strict';
const C=require('./common.cjs'),{fs,path,zlib}=C,op=C.read(path.join(C.HERE,'OPERATION.json'));C.verify(op);
const spec=op.cases.find(x=>x.id===process.argv[2]);if(!spec)throw Error('Unregistered identity');
const packet=C.read(C.packetPath),input=spec.kind==='P0'?null:C.read(path.join(C.HERE,'INPUTS.json')).inputs.find(x=>x.id===spec.input_id);
const scenario=input?{id:input.id,context:input.context,requests:input.requests}:packet.scenarios.find(x=>x.id===spec.config.scenario);
const {MultiSimulator}=require('./source/multi_simulator.cjs'),destination=path.join(op.output,'raw',spec.id+'.json.gz');let sim;
function curveIntegral(curve,a,b){let total=0;for(let i=1;i<curve.length;i++){const [l,y]=curve[i-1],[r,z]=curve[i];if(r<=a||l>=b)continue;const lo=Math.max(l,a),hi=Math.min(r,b),v=t=>y+(z-y)*(t-l)/(r-l);total+=(hi-lo)*(v(lo)+v(hi))/2;}return total;}
try{
 sim=new MultiSimulator(packet,scenario,spec.config);const r=sim.run();
 const last=Math.max(35,...r.requests.map(q=>q.times.AVAILABLE)),power=C.baseline(packet,scenario),end=spec.config.horizon_s,supplyEnd=35+spec.duration_s;
 const metrics={policy:spec.config.policy,model:spec.config.model,input:spec.input_id??'P0',n:spec.n,duration_s:spec.duration_s,horizon_s:end,planned:r.service.all.planned,completed:r.service.all.completed,on_time:r.service.all.on_time,U_on:r.service.urgent.on_time,U_planned:r.service.urgent.planned,N_on:r.service.normal.on_time,N_planned:r.service.normal.planned,P95_s:r.service.all.p95_s,unfinished:r.unfinished,right_censored:r.right_censored_at150,total_API_J:r.J_API0_180,baseline_API_J:power*end,above_baseline_API_J:r.J_API0_180-power*end,API_J_per_planned:r.J_API0_180/spec.n,baseline_fraction:power*end/r.J_API0_180,own_work_API_J:C.energy(packet,scenario,r.activity,35,last),supply_API_J:C.energy(packet,scenario,r.activity,35,supplyEnd),last_available_s:last,work_span_s:last-35,AP_observation_mean:r.AP35_180_mean,AP_supply_mean:curveIntegral(r.curve,35,supplyEnd)/spec.duration_s,AP_supply_last60_mean:curveIntegral(r.curve,Math.max(35,supplyEnd-60),supplyEnd)/Math.min(60,spec.duration_s),AP_peak:r.AP_peak_sampled,AP_end:r.AP180,AP_outside_fit:r.AP_peak_sampled>46.6||Math.min(...r.curve.map(p=>p[1]))<26,CPU_wait_s:r.shared_cpu_wait_s,max_ready:r.max_ready_queue,routes:r.policy_route_counts,forecast_calls:r.forecast_calls};
 metrics.observed_end_s=r.right_censored_at150?spec.config.censor_s:end;
 metrics.observed_prefix_API_J=r.J_observed_prefix;
 metrics.original_180s_window_exceeded=end>180;
 metrics.last_completed_available_s=last;
 if(r.right_censored_at150){metrics.above_baseline_API_J=null;metrics.API_J_per_planned=null;metrics.baseline_fraction=null;}
 if(r.unfinished){metrics.own_work_API_J=null;metrics.last_available_s=null;metrics.work_span_s=null;}
 if(spec.kind==='P0'){
  const old=C.read(spec.old_raw),oldBy=new Map(old.requests.map(q=>[q.ordinal,q]));let checks=0,maxDiff=0;
  if(r.requests.length!==old.requests.length)throw Error('P0 request count');
  for(const q of r.requests){const z=oldBy.get(q.ordinal);if(q.route!==z.route)throw Error('P0 route changed #'+q.ordinal);checks++;
   for(const [a,b] of [[q.response,z.response],...Object.keys(z.times).filter(k=>z.times[k]!==null).map(k=>[q.times[k],z.times[k]])]){if(!Number.isFinite(a)||Math.abs(a-b)>1e-8)throw Error('P0 clock changed');maxDiff=Math.max(maxDiff,Math.abs(a-b));checks++;}}
  for(const k of ['J_API0_180','AP35_180_mean','AP180','AP_peak_sampled']){if(Math.abs(r[k]-old[k])>1e-7)throw Error('P0 physical '+k);checks++;}
  metrics.P0={status:'PASS',checks,max_clock_difference_s:maxDiff};
 }
 // Original fixed-window names are retained only within this nested legacy-shaped payload.
 C.binary(destination,zlib.gzipSync(Buffer.from(JSON.stringify({schema:'S26_SUSTAINED_CASE_V1',spec,metrics,simulation:r})),{level:6}));
 const row={id:spec.id,kind:spec.kind,metrics,raw_sha256:C.sha(fs.readFileSync(destination)),raw_path:destination};C.write(path.join(op.output,'prepared',spec.id+'.json'),row);console.log(JSON.stringify(row));
}catch(error){
 const partial={schema:'S26_SUSTAINED_FAILED_CASE_V1',spec,error:String(error.stack??error),time:sim?.time,done:sim?.done?.map(q=>({ordinal:q.ordinal,route:q.route,response:q.response,times:q.times})),active:sim?.owners?.map(q=>({ordinal:q.ordinal,route:q.route,phase:q.phase,progress:q.progress,times:q.times})),ready:sim?.ready?.length,activity:sim?.intervals};
 C.binary(path.join(op.output,'raw',spec.id+'.failed.json.gz'),zlib.gzipSync(Buffer.from(JSON.stringify(partial))));throw error;
}
