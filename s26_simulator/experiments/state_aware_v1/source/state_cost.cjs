'use strict';
const math=require('./dynamic_cost_math_v2.cjs'),old=require('./rolling_action_v2.cjs'),crypto=require('crypto');
const PHASES=['GAP','ADMISSION','INFER','RETURN_GAP','POST'];
const KEYS=['dispatch','execution_start','host_inference_start','host_inference_return','output_ready','AVAILABLE'];
const ACTIVITY_ROUTES=['classification_CPU','detection_CPU','classification_GPU','classification_NPU'];
const digest=x=>crypto.createHash('sha256').update(JSON.stringify(x)).digest('hex');
function phaseLengths(nom,route,AP,peer){const n=nom.routes[route];return [n.gap_s,n.admission_s,old.duration(nom.timing,n.identity,AP,peer)*n.residual,n.return_s,n.post_s]}
function publicState(jobs,obs,context,pre){
 const prefixes=jobs.map(o=>({ordinal:o.ordinal,route:o.route,priority:o.priority,times:Object.fromEntries(Object.entries(o.times).filter(([k,v])=>KEYS.includes(k)&&Number.isFinite(v)&&v<=obs.time+1e-10))}));
 const ints=pre.map(a=>a.map(v=>v.slice()));
 for(const q of prefixes){const t=q.times;for(let j=0;j<5;j++){const l=t[KEYS[j]],r=t[KEYS[j+1]]??obs.time;if(!Number.isFinite(l)||r<=l)continue;const k=j===1?4:j===2?ACTIVITY_ROUTES.indexOf(q.route):j===4?5:7;ints[k].push([l,Math.min(r,obs.time),1])}}
 const windows=prefixes.map(q=>[q.times.dispatch,q.times.AVAILABLE??obs.time]);addUnion(ints,windows);
 const targets={AP:{anchor:JSON.parse(JSON.stringify(context.targets.AP.anchor))},POWER_API:{baseline:{median_api_w:context.targets.POWER_API.baseline.median_api_w}}};
 return {prefixes,activity9:{intervals:ints},history_start_s:-30,targets};
}
function addUnion(ints,windows){const ev=windows.flatMap(([l,r])=>r>l?[[l,1],[r,-1]]:[]).sort((a,b)=>a[0]-b[0]||a[1]-b[1]);let n=0,t=ev[0]?.[0];for(let i=0;i<ev.length;){let u=ev[i][0];if(u>t&&n){ints[6].push([t,u,1]);if(n>1)ints[8].push([t,u,n-1])}while(i<ev.length&&ev[i][0]===u)n+=ev[i++][1];t=u}}
function planOwner(o,nom,obs){
 const t=o.times;let ix=0;for(let i=0;i<5;i++)if(Number.isFinite(t[KEYS[i]]))ix=i;
 const lens=phaseLengths(nom,o.route,obs.sensor.AP,Number(obs.owners.length>1)),elapsed=Math.max(0,obs.time-t[KEYS[ix]]);
 lens[ix]=Math.max(ix===2?.25*lens[ix]:.0005,lens[ix]-elapsed);
 return {route:o.route,ordinal:o.ordinal,priority:o.priority,start:obs.time,phases:PHASES.slice(ix).map((p,j)=>({phase:p,duration_s:lens[ix+j]})),assumption:'Public elapsed + median residual with explicit floor; estimated release never changes actual legal mask'};
}
function appendPlan(ints,plan){let t=plan.start;for(const p of plan.phases){const r=t+p.duration_s,k=p.phase==='ADMISSION'?4:p.phase==='INFER'?ACTIVITY_ROUTES.indexOf(plan.route):p.phase==='POST'?5:7;if(r>t)ints[k].push([t,r,1]);t=r}return [plan.start,t]}
function forecast(obs,nom,models,route,priority,refine=1){
 const publicDigest=digest(obs),state=obs.cost_state;if(!state)throw Error('Missing public cost state');
 const ownerPlans=state.prefixes.filter(q=>!Number.isFinite(q.times.AVAILABLE)).map(o=>planOwner(o,nom,obs));
 const lens=phaseLengths(nom,route,obs.sensor.AP,0),candidate={route,priority,start:obs.time,phases:PHASES.map((phase,i)=>({phase,duration_s:lens[i]}))};
 const combined=JSON.parse(JSON.stringify([...ownerPlans,candidate])),inferBases=combined.map(p=>p.phases.find(x=>x.phase==='INFER')?.duration_s??null);
 // Symmetric nominal interference, using predicted INFER intervals, never actual latent progress.
 for(let iteration=0;iteration<3;iteration++){
  const spans=combined.map(p=>{let t=p.start;for(const x of p.phases){if(x.phase==='INFER')return[t,t+x.duration_s];t+=x.duration_s}return null});
  combined.forEach((p,i)=>{if(!spans[i])return;let overlap=0;spans.forEach((s,j)=>{if(s&&i!==j)overlap+=Math.max(0,Math.min(s[1],spans[i][1])-Math.max(s[0],spans[i][0]))});const fraction=Math.min(1,overlap/(spans[i][1]-spans[i][0]));const ix=nom.timing.spec.labels.indexOf('OVERLAP:'+p.route),beta=ix<0?0:nom.timing.coef[ix];p.phases.find(x=>x.phase==='INFER').duration_s=inferBases[i]*Math.exp(beta*fraction)})
 }
 const base=state.activity9.intervals.map(a=>a.map(x=>x.slice())),windows=ownerPlans.map(p=>appendPlan(base,p));addUnion(base,windows);
 const both=state.activity9.intervals.map(a=>a.map(x=>x.slice())),all=combined,ws=all.map(p=>appendPlan(both,p));addUnion(both,ws);
 const end=180,ts=new Set([obs.time,end,obs.sensor.time]);
 const put=x=>{if(x>=obs.time&&x<=end)ts.add(Math.round(x*1e10)/1e10)};
 for(let t=obs.time;t<end;){const age=t-obs.time,dt=(age<2?.05:age<15?.25:age<60?1:5)/refine;t=Math.min(end,t+dt);put(t)}
 for(const xs of state.activity9.intervals)for(const [l,r]of xs){put(l+.5);put(r+.5)}
 for(const p of [...ownerPlans,...all]){let t=p.start;put(t);put(t+.5);for(const x of p.phases){t+=x.duration_s;put(t);put(t+.5)}}
 const times=[...ts].sort((a,b)=>a-b),session=ints=>({...state,activity9:{intervals:ints}});
 const bp=math.predict(models.power,session(base),times),cp=math.predict(models.power,session(both),times),bt=math.predict(models.AP,session(base),times),ct=math.predict(models.AP,session(both),times);
 const sensorIx=times.indexOf(obs.sensor.time),offset=obs.sensor.AP-bt[sensorIx];let J=0,H=0,peak=-Infinity;for(let i=1;i<times.length;i++){if(times[i-1]<obs.time-1e-9)continue;const dt=times[i]-times[i-1];J+=dt*((cp[i]-bp[i])+(cp[i-1]-bp[i-1]))/2;H+=dt*((ct[i]-bt[i])+(ct[i-1]-bt[i-1]))/2;peak=Math.max(peak,ct[i]+offset)}
 const scales={J:Math.max(1e-9,...old.ROUTES.map(r=>Math.abs(nom.routes[r].incremental_J_proxy))),H:Math.max(1e-9,...old.ROUTES.map(r=>Math.abs(nom.routes[r].AP_area_proxy)))};
 return {incremental_J:J,incremental_AP_area:H,normalized_energy_heat:J/scales.J+H/scales.H,predicted_AP_peak:peak,current_AP:obs.sensor.AP,current_owners:obs.owners.map(o=>o.route),public_digest:publicDigest,grid_points:times.length,grid_digest:digest(times),owner_plans:all.slice(0,-1),candidate_plan:all.at(-1),symmetric_interference_iterations:3,nominal_forecast_only:true,refinement:refine};
}
module.exports={PHASES,KEYS,digest,publicState,phaseLengths,planOwner,forecast};
