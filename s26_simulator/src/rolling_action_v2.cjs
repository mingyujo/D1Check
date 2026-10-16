'use strict';
// The selector sees only this public observation and frozen nominal estimates.
// It never receives a simulator, sampled residual, actual remaining work or future arrival.
const math=require('./dynamic_cost_math_v2.cjs');
const ROUTES=['classification_CPU','classification_GPU','classification_NPU','detection_CPU'];
const PAIRS=[['classification_GPU','detection_CPU'],['classification_NPU','detection_CPU']];
const legal=(route,owners)=>owners.length===0||(owners.length===1&&PAIRS.some(p=>p.includes(route)&&p.includes(owners[0].route)&&route!==owners[0].route));
const median=a=>{a=a.slice().sort((a,b)=>a-b);const n=a.length;return n%2?a[(n-1)/2]:(a[n/2-1]+a[n/2])/2};
function duration(m,r,AP,peer){
 const labels=m.spec.labels,x=labels.map(()=>0),set=(n,v)=>{const j=labels.indexOf(n);if(j>=0)x[j]=v};
 const b='BASE:'+r.route+'|'+r.model_sha256;if(!labels.includes(b))throw Error('Unsupported nominal model/route');set(b,1);
 const cats=[r.domain??'UNKNOWN',r.apk??'UNKNOWN',[r.engine,r.version,r.cpu_threads,r.gpu_precision].map(v=>v==null?'None':String(v)).join('|'),r.image_sha256??'UNKNOWN'];cats.forEach((v,j)=>set('NUISANCE'+j+':'+v,1));set('AP:'+r.route,(AP-30)/10);set('OVERLAP:'+r.route,peer);
 const y=x.reduce((s,v,j)=>s+v*m.coef[j],0);if(!(y>-20&&y<Math.log(60)))throw Error('Nominal time outside supported numerical bound');return Math.exp(y);
}
function publicNominals(packet,scenario){
 const out={},models=packet.timing,session={history_start_s:-30,activity9:{intervals:scenario.context.pre_activity9.intervals.map(a=>a.map(v=>v.slice()))},targets:scenario.context.initial_context.targets};
 const t0=35,times=Array.from({length:161},(_,i)=>t0+i*.05).concat(Array.from({length:53},(_,i)=>t0+9+i));
 const baselineP=math.predict(packet.power,session,times),baselineT=math.predict(packet.AP,session,times);
 for(const route of ROUTES){
  const pool=packet.templates.filter(p=>p.route===route);if(!pool.length)throw Error('No measured phase templates for '+route);
  const identity={...pool[0],domain:'M8_READBACK_RENAME_RESPONSE'},medianOffset=k=>median(pool.map(p=>p.offset_s[k]).filter(Number.isFinite));
  const gap=medianOffset('execution_start_ns'),admission=median(pool.map(p=>p.offset_s.host_inference_start_ns-p.offset_s.execution_start_ns)),ret=median(pool.map(p=>p.offset_s.output_ready_ns-p.offset_s.host_inference_return_ns)),post=median(pool.map(p=>p.offset_s.lane_available_ns-p.offset_s.output_ready_ns));
  const residual=median(pool.map(p=>p.inference_s/duration(models,{...p,domain:'M8_READBACK_RENAME_RESPONSE'},p.AP??30,p.overlap_fraction??0)));
  const infer=duration(models,identity,30,0)*residual,occupied=gap+admission+infer+ret+post,readbackFraction=route==='detection_CPU'?median(pool.map(p=>(p.offset_s.readback_end_ns-p.offset_s.output_ready_ns)/(p.offset_s.lane_available_ns-p.offset_s.output_ready_ns))):0;
  const intervals=session.activity9.intervals.map(a=>a.map(v=>v.slice())),add=(k,a,b)=>{if(b>a)intervals[k].push([t0+a,t0+b,1])};
  add(7,0,gap);add(4,gap,gap+admission);add(['classification_CPU','detection_CPU','classification_GPU','classification_NPU'].indexOf(route),gap+admission,gap+admission+infer);add(7,gap+admission+infer,gap+admission+infer+ret);add(5,occupied-post,occupied);add(6,0,occupied);
  const hypothetical={...session,activity9:{intervals}},pp=math.predict(packet.power,hypothetical,times),tt=math.predict(packet.AP,hypothetical,times);let incrementalJ=0,thermalArea=0;
  for(let i=1;i<times.length;i++){const dt=times[i]-times[i-1];incrementalJ+=dt*((pp[i]-baselineP[i])+(pp[i-1]-baselineP[i-1]))/2;thermalArea+=dt*((tt[i]-baselineT[i])+(tt[i-1]-baselineT[i-1]))/2}
  out[route]={route,identity,gap_s:gap,admission_s:admission,return_s:ret,post_s:post,residual,readback_fraction:readbackFraction,nominal_inference_s:infer,nominal_occupied_s:occupied,incremental_J_proxy:incrementalJ,AP_area_proxy:thermalArea,phase_source_count:pool.length};
 }
 return {routes:out,timing:models,proxy_scope:'Frozen common-model single-job perturbation over61s and fixed30C inference reference; planning proxy, not measured or realized savings',future_actual_inputs:false};
}
function estimate(nom,route,AP,peer,priority){const r=nom.routes[route],infer=duration(nom.timing,r.identity,AP,peer)*r.residual,pre=r.gap_s+r.admission_s,output=pre+infer+r.return_s;return {occupied_s:output+r.post_s,response_s:output+(priority==='normal'?r.post_s*r.readback_fraction:0)}}
function select(obs,nom,options={}){
 const classRoutes=options.classification_routes??ROUTES.slice(0,3),allowed=q=>q.task==='detection'?['detection_CPU']:classRoutes;
 if(!classRoutes.length||classRoutes.some(r=>!ROUTES.slice(0,3).includes(r)))throw Error('Unsupported classification route contract');
 if(!obs.ready.length)return {kind:'NONE',candidates:[]};
 const AP=obs.sensor.AP,scales={J:Math.max(1e-9,...ROUTES.map(r=>Math.abs(nom.routes[r].incremental_J_proxy))),H:Math.max(1e-9,...ROUTES.map(r=>Math.abs(nom.routes[r].AP_area_proxy)))};
 const fastest=q=>Math.min(...allowed(q).map(r=>estimate(nom,r,AP,0,q.priority).response_s)),meanP=obs.ready.reduce((s,q)=>s+fastest(q),0)/obs.ready.length,candidates=[];
 for(const q of obs.ready)for(const route of allowed(q)){
  const permitted=legal(route,obs.owners),est=estimate(nom,route,AP,Number(obs.owners.length>0),q.priority),slack=q.deadline-obs.time-est.response_s;
  let misses=Number(slack<0),maxLate=Math.max(0,-slack);
  // One-step conservative contention check of other arrived jobs. No synthetic future requests.
  for(const other of obs.ready){if(other.ordinal===q.ordinal)continue;const earliest=Math.min(...allowed(other).map(r=>{
    const conflict=!legal(r,[{route}]),wait=conflict?est.occupied_s:0;return obs.time+wait+estimate(nom,r,AP,Number(!conflict),other.priority).response_s;
   }));if(earliest>other.deadline)misses++;maxLate=Math.max(maxLate,earliest-other.deadline)}
  const atc=1/est.response_s*Math.exp(-Math.max(slack,0)/(2*Math.max(meanP,1e-9)));
  const utility=nom.routes[route].incremental_J_proxy/scales.J+nom.routes[route].AP_area_proxy/scales.H;
  candidates.push({ordinal:q.ordinal,route,permitted,response_estimate_s:est.response_s,occupied_estimate_s:est.occupied_s,slack_s:slack,predicted_ready_misses:misses,predicted_max_lateness_s:Math.max(0,maxLate),ATC:atc,energy_proxy:nom.routes[route].incremental_J_proxy,heat_proxy:nom.routes[route].AP_area_proxy,normalized_energy_heat:utility});
 }
 const feasible=candidates.filter(c=>c.permitted);if(!feasible.length)return {kind:'NONE',candidates};
 // First protect arrived deadlines. Then use ATC to pick a request; compare all supported routes of that request by energy/heat.
 const requestRank=feasible.slice().sort((a,b)=>a.predicted_ready_misses-b.predicted_ready_misses||a.predicted_max_lateness_s-b.predicted_max_lateness_s||b.ATC-a.ATC||a.ordinal-b.ordinal)[0];
 const same=feasible.filter(c=>c.ordinal===requestRank.ordinal&&c.predicted_ready_misses===requestRank.predicted_ready_misses&&Math.abs(c.predicted_max_lateness_s-requestRank.predicted_max_lateness_s)<1e-12),best=same.sort((a,b)=>a.normalized_energy_heat-b.normalized_energy_heat||a.response_estimate_s-b.response_estimate_s||a.route.localeCompare(b.route))[0];
 // A short wait is allowed only when every owner is AVAILABLE, cooling has already been observed,
 // and each arrived request retains nominal deadline slack. Never stop a running job.
 const recent=obs.sensor_history.slice(-2),wait=options.wait_step_s??.05,cap=options.wait_cap_s??2;
 if(options.allow_wait!==false&&obs.owners.length===0&&recent.length===2&&obs.wait_used_s+wait<=cap+1e-12){
  const dt=recent[1].time-recent[0].time,slope=dt>0?(recent[1].AP-recent[0].AP)/dt:0;
  if(slope<-.01&&AP>obs.initial_AP+.5&&obs.ready.every(q=>q.deadline-obs.time-fastest(q)>wait+.05))return {kind:'WAIT',dose_s:wait,candidates,reason:'Observed cooling and positive nominal slack for all arrived jobs'};
 }
 return {kind:'DISPATCH',ordinal:best.ordinal,route:best.route,candidates,selected:best,reason:'Rolling ready-queue deadline screen + ATC request priority + energy/heat route choice'};
}
module.exports={ROUTES,PAIRS,legal,duration,publicNominals,estimate,select};
