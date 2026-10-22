'use strict';
// Saved-only, separate-language analytic reconstruction, never imports producer.
const fs=require('fs'),path=require('path'),zlib=require('zlib'),crypto=require('crypto'),vm=require('vm');
const H=__dirname,A=path.resolve(H,'../..'),O=path.join(A,'results/A24_S26_METHOD_20261019_01');
const read=p=>JSON.parse(p.endsWith('.gz')?zlib.gunzipSync(fs.readFileSync(p)):fs.readFileSync(p)),sha=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex'),save=(n,x)=>fs.writeFileSync(path.join(O,n),JSON.stringify(x,null,2)+'\n',{flag:'wx'});
const shape=read(path.join(H,'SHAPE.json')),op=read(path.join(H,'OPERATION.json')),power=read(path.join(A,'results/STATE_COST_IDENTIFICATION_20261017_01/MODEL.json')),solo=Object.fromEntries(power.supported_states.map((k,i)=>[k,power.coefficients_W_proxy[i]]));solo.detection_GPU=.6013808404579677;const shared=solo.classification_GPU+solo.detection_CPU-solo['classification_GPU+detection_CPU'];delete solo['classification_GPU+detection_CPU'];
const legacy=fs.readFileSync(path.join(A,'experiments/a24_parallel_20261018/audit_v2.cjs'),'utf8'),old=vm.runInNewContext(legacy.slice(legacy.indexOf('function transition('),legacy.indexOf('let derived=[]'))+';({transition})',{solo,shared});
let checks=0,maxerr=0;
function ok(v,m){checks++;if(!v)throw Error(m);}
function near(a,b,m,tol=3e-7){maxerr=Math.max(maxerr,Math.abs(a-b));ok(Number.isFinite(a)&&Number.isFinite(b)&&Math.abs(a-b)<=tol,m+': '+a+' != '+b);}
function step(st,active,dt,p,profile){
 if(profile==='ORIGINAL'){const t=old.transition(st,active,dt,p,{slots:3,beta:.25});return {state:{temperature_c:t.T,shared_z:t.z},J:t.J,H:t.area,rates:t.rates};}
 const s=structuredClone(st),rates={},n=active.filter(j=>j.route==='CPU'&&j.stage===1).length;
 for(const j of active){let f=1;if(j.stage===1)f=profile==='S26_STYLE'?Math.min(1.2,Math.max(.45,Math.exp(-shape.slopes_per_c[j.task+'_'+j.route]*(st.temperature_c-p.reference_c)))):Math.max(p.minimum_speed,1/(1+p.strength*(j.route==='CPU'?p.cpu_slope:p.gpu_slope)*Math.max(0,st.temperature_c-p.onset_c)));rates[j.request_id]=f/(j.route==='CPU'&&j.stage===1?1+.25*Math.max(0,n-1):1);}
 const max=r=>Math.max(0,...active.filter(j=>j.route===r).map(j=>solo[(j.task==='C'?'classification':'detection')+'_'+r]-shared)),v=[max('CPU'),max('GPU'),active.length?shared:0];
 if(JSON.stringify(v)!==JSON.stringify(s.v)){s.v=v;s.pending.push([s.time_s+.5,v.slice()]);}
 const cb=[1,shape.gpu_box_fraction,1],tail=1-shape.gpu_box_fraction,end=s.time_s+dt;let J=0,H=0,T=st.temperature_c;
 while(s.time_s<end-1e-12){
  while(s.pending.length&&s.pending[0][0]<=s.time_s+1e-12)s.vd=s.pending.shift()[1];
  const h=Math.min(end,s.pending[0]?.[0]??end)-s.time_s,ramp=2*cb.reduce((a,c,i)=>a+c*(s.v[i]-s.vd[i]),0),constant=s.box+tail*s.v[1],expAmp=tail*(s.z[1]-s.v[1]),E=constant*h+ramp*h*h/2+expAmp*-Math.expm1(-h);
  let tempArea,T1;
  if(profile==='UNION'){
   const tau=p.thermal_tau_s,one=-Math.expm1(-h/tau),oldT=T-p.idle_c,newT=oldT*Math.exp(-h/tau)+p.thermal_resistance*(constant*one+ramp*(h-tau*one)+expAmp*(Math.exp(-h)-Math.exp(-h/tau))/(1-tau));
   T1=p.idle_c+newT;tempArea=p.idle_c*h+tau*(oldT-newT)+p.thermal_resistance*E;
  }else{
   const taus=shape.thermal_taus_s,G=shape.thermal_gains,w=[shape.initial_fast_weight,1-shape.initial_fast_weight];tempArea=p.idle_c*h+(s.initial_c-p.idle_c)*taus.reduce((a,t,i)=>a+w[i]*t*Math.exp(-s.time_s/t)*-Math.expm1(-h/t),0);
   s.heat=s.heat.map((oldHeat,i)=>{const tau=taus[i],d=Math.exp(-h/tau),one=-Math.expm1(-h/tau),kernel=tau===1?h/tau*d:(Math.exp(-h)-d)/(1-tau),newHeat=oldHeat*d+constant*one+ramp*(h-tau*one)+expAmp*kernel;tempArea+=G[i]*(E-tau*(newHeat-oldHeat));return newHeat;});
   T1=p.idle_c+(s.initial_c-p.idle_c)*taus.reduce((a,t,i)=>a+w[i]*Math.exp(-(s.time_s+h)/t),0)+s.heat.reduce((a,x,i)=>a+G[i]*x,0);
  }
  s.box+=ramp*h;s.z=s.z.map((a,i)=>v[i]+(a-v[i])*Math.exp(-h));s.time_s+=h;J+=E;H+=tempArea;T=T1;
 }
 while(s.pending.length&&s.pending[0][0]<=end+1e-12)s.vd=s.pending.shift()[1];s.temperature_c=T;s.shared_z=active.length?1:0;return {state:s,J:Math.max(0,J),H,rates};
}
function integral(r,profile,end){let J=0,H=0,peak=r.initial_ap_c;for(const t of r.trace){if(t.start_ns>=end)break;const dt=(Math.min(end,t.end_ns)-t.start_ns)/1e9,a=step(t.state,t.active,dt,r.config,profile);J+=a.J+r.config.baseline*dt;H+=a.H;peak=Math.max(peak,t.state.temperature_c,a.state.temperature_c);}return {J,AP:H/(end/1e9-35),peak};}
function withTail(r,profile,end,amount){if(end===null)return null;const later=Math.min(r.trace.at(-1).end_ns,end+30e9),extra=integral(r,profile,later).J-amount-r.config.baseline*(later-end)/1e9;return amount+Math.max(0,extra);}
function audit(){
 const result=read(path.join(O,'RESULT.json'));ok(result.COMPLETE===240&&result.FAIL===0,'Complete census');for(const p of op.pins)ok(sha(p.path)===p.sha256,'Pinned input/source '+p.path);
 const receipts=fs.readFileSync(path.join(O,'receipts.jsonl'),'utf8').trim().split('\n').map(JSON.parse);ok(receipts.filter(x=>x.event==='START').length===240&&receipts.filter(x=>x.event==='COMPLETE').length===240,'Durable receipts');ok(new Set(receipts.filter(x=>x.event==='START').map(x=>x.start_id)).size===240,'Unique START ids');
 let derived=[],expectedRewards=[];const bankcache=new Map();
 for(const row of result.rows){
  const file=path.join(O,row.label+'.raw.json.gz');ok(sha(file)===row.raw_sha256,'Raw hash');const d=read(file),r=d.result,profile=row.profile.id;ok(sha(row.bank_path)===row.bank_sha256,'Bank hash');if(!bankcache.has(row.bank_path))bankcache.set(row.bank_path,Object.fromEntries(Object.values(read(row.bank_path).jobs).map(q=>[q.request_id,q])));const bank=bankcache.get(row.bank_path),qmap=new Map(r.requests.map(q=>[q.request_id,q])),work=new Map();
  ok(r.requests.length===d.case.n&&new Set(r.requests.map(q=>q.ordinal)).size===d.case.n,'All arrivals retained');
  for(const q of r.requests){const src=d.case.input.requests[q.ordinal];ok(q.scheduled_arrival_ns===Math.round(src.arrival_s*1e9)&&q.deadline_ns===Math.round(src.deadline_s*1e9)&&q.task===src.profile[0]&&q.priority===src.priority,'Identical public input');ok(q.queue_entry_ns===bank[q.request_id].queue_entry_ns,'Frozen admission');if(q.route)ok(JSON.stringify(q.timing.stages_ns)===JSON.stringify(bank[q.request_id].routes[q.route].stages_ns),'Immutable SERIAL route work');}
  let prev=null,prefixJ=[0],prefixH=[0];
  for(const t of r.trace){
   ok(t.end_ns>t.start_ns,'Positive clock');near(t.dt,(t.end_ns-t.start_ns)/1e9,'dt',1e-12);if(prev){ok(t.start_ns===prev.end_ns,'Contiguous');near(t.state.temperature_c,prev.next_state.temperature_c,'T continuity',1e-10);}prev=t;
   ok(t.active.filter(x=>x.route==='CPU').length<=3&&t.active.filter(x=>x.route==='GPU').length<=1,'Capacity');const a=step(t.state,t.active,t.dt,r.config,profile);near(a.state.temperature_c,t.next_state.temperature_c,'Independent temperature');near(a.J,t.increment,'Independent energy');near(a.H,t.temperature_area,'Independent AP integral');
   prefixJ.push(prefixJ.at(-1)+a.J+r.config.baseline*t.dt);prefixH.push(prefixH.at(-1)+a.H);
   if(profile!=='ORIGINAL'){near(a.state.box,t.next_state.box,'Box history',1e-9);for(let k=0;k<3;k++)near(a.state.z[k],t.next_state.z[k],'Exp history',1e-9);for(let k=0;k<2;k++)near(a.state.heat[k],t.next_state.heat[k],'Heat state',1e-9);}
   for(const j of t.active){near(a.rates[j.request_id],t.speeds[j.request_id],'Progress rate',1e-12);const q=qmap.get(j.request_id);ok(q&&q.route===j.route&&q.dispatch_ns<=t.start_ns&&(q.available_ns===null||q.available_ns>=t.end_ns),'Nonpreemptive ownership');const k=j.request_id+'|'+j.stage;work.set(k,(work.get(k)||0)+t.dt*a.rates[j.request_id]);}
  }
  for(const q of r.requests)if(q.available_ns!==null){for(let k=0;k<5;k++)near(work.get(q.request_id+'|'+k)||0,q.timing.stages_ns[k]/1e9,'Immutable phase work',7e-9);ok(q.response_ns===(q.task==='C'?q.output_ready_ns:q.persist_complete_ns),'Response boundary');}
  for(const decision of r.decisions){const s=decision.public_state,a=decision.action;ok(s.now_ns===decision.time_ns&&s.queue.every(q=>q.queue_entry_ns<=s.now_ns),'Causal visible queue');if(a.kind==='DISPATCH')ok(s.queue.some(q=>q.request_id===a.request_id),'Visible selected request');if(row.policy.startsWith('FIFO')||row.policy.startsWith('EDF')){const first=s.queue.slice().sort((a,b)=>(row.policy.startsWith('EDF')?a.deadline_ns-b.deadline_ns:0)||a.scheduled_arrival_ns-b.scheduled_arrival_ns||a.ordinal-b.ordinal||a.request_id.localeCompare(b.request_id))[0],priority=row.policy.endsWith('CPU')?['CPU','GPU']:['GPU','CPU'],route=priority.find(rr=>s.owners.filter(o=>o.route===rr).length<(rr==='CPU'?3:1));ok(a.kind==='DISPATCH'&&a.request_id===first.request_id&&a.route===route,'Independent FIFO/EDF');}}
  ok(d.calls.length===r.decisions.length,'One decision per actor call');
  for(let ci=0;ci<d.calls.length;ci++){const call=d.calls[ci];if(call.forecasts){const snap=r.decisions[ci].public_state,visible=new Set([...snap.queue,...snap.owners].map(q=>q.request_id));ok(call.actions.length===call.forecasts.length,'Forecast action alignment');for(let fi=0;fi<call.forecasts.length;fi++){const f=call.forecasts[fi];ok(f.no_future_arrivals&&f.no_future_latents&&f.visible_ids.length<=36&&f.visible_ids.every(id=>visible.has(id)),'Only current public IDs in bounded forecast');ok(f.cost.every(Number.isFinite),'Finite costs');near(call.forecast_scores[fi],f.cost[0]/.35+f.cost[1]+12*f.cost[2]+6*f.cost[3]+3*f.cost[4],'Forecast score',1e-5);}if(row.policy==='TEACHER'){const best=Math.min(...call.forecast_scores.slice(0,call.actions.length));near(call.forecast_scores[call.chosen],best,'Teacher scores include WAIT',1e-7);}}}
  const service={};for(const p of ['ALL','U','N']){const qs=r.requests.filter(q=>p==='ALL'||q.priority===p),ans=qs.filter(q=>q.response_ns!==null&&q.response_ns<=d.case.drain_stop_s*1e9),lat=ans.map(q=>(q.response_ns-q.scheduled_arrival_ns)/1e9).sort((a,b)=>a-b);service[p]={n:qs.length,on:ans.filter(q=>q.response_ns<=q.deadline_ns).length,missing:qs.length-ans.length,P95:lat.length?lat[Math.ceil(.95*lat.length)-1]:null};}
  ok(service.ALL.on===row.metrics.on_time&&service.U.on===row.metrics.urgent_on_time,'Actual deadlines');const incomplete=r.requests.filter(q=>q.available_ns===null||q.available_ns>d.case.drain_stop_s*1e9).length;ok(incomplete===row.metrics.incomplete,'Incomplete retained');
  const finish=r.requests.every(q=>q.available_ns!==null)?Math.max(...r.requests.map(q=>q.available_ns)):null;
  near(integral(r,profile,d.case.drain_stop_s*1e9).J,row.metrics.total_J_proxy,'Producer total independently reconstructed',4e-6);
  near(integral(r,profile,d.case.service_stop_s*1e9).AP,row.metrics.mean_AP_c,'Producer AP independently reconstructed',4e-7);
  if(row.kind==='TRAIN'){
   const H=(d.case.supply_stop_s+30)*1e9;let prior=[0,0,0,0,0],costs=[];
   const prefix=end=>{if(end<=35e9)return {J:0,AP:26};let lo=0,hi=r.trace.length-1;while(lo<hi){const mid=Math.ceil((lo+hi)/2);if(r.trace[mid].start_ns<=end)lo=mid;else hi=mid-1;}const t=r.trace[lo],dt=(end-t.start_ns)/1e9,a=step(t.state,t.active,dt,r.config,profile);return {J:prefixJ[lo]+a.J+r.config.baseline*dt,AP:(prefixH[lo]+a.H)/(end/1e9-35)};};
   for(let i=0;i<d.calls.length;i++){const end=i+1<d.calls.length?d.calls[i+1].time_ns:d.case.drain_stop_s*1e9,cut=Math.min(end,H),physical=prefix(cut),val=[physical.J/(d.case.n*.35),Math.max(0,(physical.AP-26)*(cut/1e9-35))/((H/1e9-35)*10),0,0,0];
    for(const q of r.requests){const late=Math.max(0,((q.response_ns===null?end:Math.min(end,q.response_ns))-q.deadline_ns)/1e9),idx=q.priority==='U'?2:3,den=Math.max(1,r.requests.filter(x=>x.priority===q.priority).length),ttl=Math.max(.05,(q.deadline_ns-q.scheduled_arrival_ns)/1e9);val[idx]+=(Number(late>1e-9)+.02*Math.min(5,late/ttl))/den;}
    if(i===d.calls.length-1)val[4]=incomplete/d.case.n;costs.push(val.map((x,j)=>x-prior[j]));prior=val;
   }expectedRewards.push({label:row.label,costs,sum:prior});
  }
  derived.push({label:row.label,kind:row.kind,profile,case:row.case,policy:row.policy,condition:d.case.condition,service,incomplete,finish_ns:finish,completion:finish===null?null:integral(r,profile,finish),supply:integral(r,profile,d.case.supply_stop_s*1e9),wait_s:row.metrics.wait_s,route_counts:row.metrics.route_counts,decisions:r.decisions.length});
  console.log('SAVED_AUDIT',row.label,checks);
 }
 for(const g of derived.filter(x=>x.kind==='EVAL')){const all=derived.filter(x=>x.kind==='EVAL'&&x.profile===g.profile&&x.case===g.case);ok(all.length===8,'All eight policies each model/input');const raw=read(path.join(O,g.label+'.raw.json.gz')),H=all.every(x=>x.finish_ns!==null)?Math.max(raw.case.supply_stop_s*1e9,...all.map(x=>x.finish_ns)):raw.case.drain_stop_s*1e9;g.common_end_ns=H;g.common=integral(raw.result,g.profile,H);g.baseline_J=raw.result.config.baseline*(H/1e9-35);g.increment_J=g.common.J-g.baseline_J;}
 for(const g of derived.filter(x=>x.kind==='EVAL')){const raw=read(path.join(O,g.label+'.raw.json.gz'));g.completion_with_30s_activity_tail_J=g.completion===null?null:withTail(raw.result,g.profile,g.finish_ns,g.completion.J);g.common_with_30s_activity_tail_J=g.finish_ns!==null&&g.finish_ns<=g.common_end_ns?withTail(raw.result,g.profile,g.common_end_ns,g.common.J):null;}
 for(const g of derived.filter(x=>x.kind==='EVAL')){const all=derived.filter(x=>x.kind==='EVAL'&&x.case===g.case);ok(all.length===24,'All three models/eight policies');const raw=read(path.join(O,g.label+'.raw.json.gz')),H=all.every(x=>x.finish_ns!==null)?Math.max(raw.case.supply_stop_s*1e9,...all.map(x=>x.finish_ns)):raw.case.drain_stop_s*1e9;g.cross_model_end_ns=H;g.cross_model_common=integral(raw.result,g.profile,H);}
 save('DERIVED.json',derived);save('EXPECTED_TRAIN_REWARDS.json',expectedRewards);save('AUDIT.json',{status:'PASS',checks,max_absolute_error:maxerr,rows:derived.length,source_sha256:sha(__filename),new_environment:0,independent_physics_latent_work_service_baselines:true,peak_is_integration_trace_endpoint_peak:true});return derived;
}
module.exports={step,integral};if(require.main===module)audit();
