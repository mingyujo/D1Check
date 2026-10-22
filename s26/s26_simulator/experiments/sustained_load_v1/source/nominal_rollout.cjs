'use strict';
// Nominal public-queue event calculation, not a sampled policy environment.
const rc=require('./resource_contract.cjs'),tm=require('./multi_timing.cjs');
function rollout(obs,packet,nom,model,first){
 let time=obs.time,ticket=0,cpu=null,cpuPhase=null,calls=0;const owners=[],ready=obs.ready.slice(),done=[],spans=Array.from({length:9},()=>[]),plans=[];
 function enter(o,phase,left){o.phase=phase;o.left=left;o.phase_progress=0;o.cpu_ticket=++ticket;o.cpu_service_s=['ADMISSION','POST'].includes(phase)?tm.service(packet,o.route,phase,left,model):0;}
 function make(q,route,original){const p=tm.lengths(packet,nom,route,obs.sensor.AP,[],model,q.priority),o={...q,route,p,progress:0,response:null,start:time,infer_start:null,infer_end:null};if(original){const keys=['dispatch','execution_start','host_inference_start','host_inference_return','output_ready'],phases=['GAP','ADMISSION','INFER','RETURN_GAP','POST'];let ix=0;for(let i=1;i<keys.length;i++)if(Number.isFinite(q.times?.[keys[i]]))ix=i;const elapsed=Math.max(0,time-(q.times?.[keys[ix]]??q.dispatch)),length=[p.gap,p.admission,p.infer,p.ret,p.post][ix];enter(o,phases[ix],Math.max(.0005,length-elapsed));if(ix===2){o.progress=Math.min(.75,elapsed/Math.max(1e-9,p.infer));o.infer_start=time}if(ix===4){o.post_total=o.left;o.readback_at=o.left*nom[route].readback_fraction;if(q.priority==='urgent')o.response=q.times.output_ready;else if(Number.isFinite(q.times?.readback_end))o.response=q.times.readback_end;}}else enter(o,'GAP',p.gap);owners.push(o);return o;}
 for(const q of obs.owners)make(q,q.route,true);
 function transition(o){if(o.phase==='GAP')enter(o,'ADMISSION',o.p.admission);else if(o.phase==='ADMISSION'){enter(o,'INFER',0);o.progress=0;o.infer_start=time;}else if(o.phase==='INFER'){o.infer_end=time;enter(o,'RETURN_GAP',o.p.ret)}else if(o.phase==='RETURN_GAP'){if(o.priority==='urgent')o.response=time;enter(o,'POST',o.p.post);o.post_total=o.p.post;o.readback_at=o.p.post*nom[o.route].readback_fraction;}else{owners.splice(owners.indexOf(o),1);o.end=time;done.push(o)}}
 let firstPending=Boolean(first);
 while(owners.length||ready.length){if(++calls>(obs.nominal_event_cap??20000))throw Error('Nominal rollout event cap');
  for(const o of owners.slice()){if(o.phase==='POST'&&o.priority==='normal'&&o.response===null&&o.phase_progress>=o.readback_at-1e-10)o.response=time;for(let k=0;k<8&&owners.includes(o)&&(o.phase==='INFER'?o.progress>=1-1e-10:o.left<=1e-10);k++)transition(o);}
  const same=cpu&&cpu.phase===cpuPhase;cpu=model.cpu_service==='none'?owners.find(x=>x.phase==='INFER'&&rc.slot(x.route)==='CPU')??null:rc.chooseCPU(owners,same?cpu:null);cpuPhase=cpu?.phase;
  const eligible=ready.filter(q=>rc.allowed(q).some(r=>rc.legal(r,owners,obs.capacity)));let chosen=null;
  if(firstPending){const q=ready.find(q=>q.ordinal===first.ordinal);if(q&&rc.legal(first.route,owners,obs.capacity)){chosen={q,route:first.route};firstPending=false}else throw Error('First candidate not currently legal');}
  else if(eligible.length){eligible.sort((a,b)=>a.deadline-b.deadline||rc.FIFO(a,b));const q=eligible[0],routes=rc.allowed(q).filter(r=>rc.legal(r,owners,obs.capacity));routes.sort((a,b)=>tm.lengths(packet,nom,a,obs.sensor.AP,owners.filter(o=>o.phase==='INFER'),model,q.priority).response-tm.lengths(packet,nom,b,obs.sensor.AP,owners.filter(o=>o.phase==='INFER'),model,q.priority).response||a.localeCompare(b));chosen={q,route:routes[0]};}
  if(chosen){ready.splice(ready.indexOf(chosen.q),1);make(chosen.q,chosen.route,false);continue;}
  if(!owners.length){if(ready.length)throw Error('Nominal deadlock');break;}
  const active=rc.activity(owners,cpu,model),rates=new Map;let dt=Infinity;
  for(const o of owners){if(o.phase==='INFER'){if(rc.slot(o.route)==='CPU'&&o!==cpu)continue;const peers=owners.filter(p=>p!==o&&p.phase==='INFER'&&(rc.slot(p.route)!=='CPU'||p===cpu)),d=tm.duration(packet,nom[o.route].identity,obs.sensor.AP,peers,model,nom[o.route].residual);rates.set(o,1/d);dt=Math.min(dt,(1-o.progress)*d)}else if(!rc.needsCPU(o)||o===cpu){dt=Math.min(dt,o.left);if(rc.needsCPU(o))dt=Math.min(dt,o.cpu_service_s-o.phase_progress);if(o.phase==='POST'&&o.priority==='normal'&&o.response===null&&o.readback_at>o.phase_progress+1e-10)dt=Math.min(dt,o.readback_at-o.phase_progress);}}
  if(!(dt>1e-11&&Number.isFinite(dt)))throw Error('Nominal event advance');
  for(let j=0;j<9;j++)if(active[j]){const prev=spans[j].at(-1);if(prev&&Math.abs(prev[1]-time)<1e-10&&prev[2]===active[j])prev[1]=time+dt;else spans[j].push([time,time+dt,active[j]])}
  for(const o of owners){if(o.phase==='INFER'){if(rates.has(o))o.progress+=dt*rates.get(o)}else if(!rc.needsCPU(o)||o===cpu){o.left-=dt;o.phase_progress+=dt}}
  time+=dt;if(time>(obs.horizon_s??180))throw Error('Nominal completion outside registered horizon');
 }
 for(const o of done){plans.push({ordinal:o.ordinal,route:o.route,priority:o.priority,start:o.start,end:o.end,response:o.response,infer_start:o.infer_start,infer_end:o.infer_end,estimated_owner:obs.owners.some(x=>x.ordinal===o.ordinal)})}
 const responses=done.filter(x=>Number.isFinite(x.deadline)).map(o=>({ordinal:o.ordinal,response:o.response,deadline:o.deadline}));
 return {plans,responses,activity:spans,misses:responses.filter(x=>x.response===null||x.response>x.deadline+1e-9).length,max_lateness:Math.max(0,...responses.map(x=>x.response===null?(obs.horizon_s??180)-x.deadline:x.response-x.deadline)),nominal_events:calls};
}
module.exports={rollout};
