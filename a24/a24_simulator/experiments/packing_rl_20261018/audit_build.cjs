'use strict';
const fs=require('fs'),path=require('path'),d=__dirname;
let s=fs.readFileSync(path.join(d,'../deep_repair_20261018/audit.cjs'),'utf8');
s=s.replace("T=require('../sustained_load_20261017/tensor_reader.cjs')","T=require('./tensor_reader.cjs'),F=require('./feature_audit.cjs')").replace('i<19','i<35').replace('j<19','j<35');
s=s.replace("res.new_START===308||res.new_START===338","res.new_START===192").replace('a.x.length===19','a.x.length===35').replace('x.length===32','x.length===40').replace('a.mask.length===19','a.mask.length===35');
const anchor="  if(row.network_sha256){\n   need(row.network_sha256===net.digest";
if(!s.includes(anchor))throw Error('Independent feature insertion site');
s=s.replace(anchor,`  if(row.kind!=='EXPERT'){
   const nom=row.case.startsWith('DENSITY_')?JSON.parse(zlib.gunzipSync(fs.readFileSync(op.public_nominals.path)))[row.case]:bank.nominal_vectors,history=new Map();
   for(let i=0;i<raw.calls.length;i++)F.verify(raw.calls[i],r.decisions[i].public_state,nom,c,solo,H,row.n,history,need,close);
  }
`+anchor);
const begin=s.indexOf(' const summary=[];'),end=s.indexOf(' for(const arm of op.arms)',begin);if(begin<0||end<0)throw Error('Reward audit replacement site');
s=s.slice(0,begin)+` const summary=[];
 for(const row of res.rows.filter(r=>r.network_sha256)){
  const raw=JSON.parse(zlib.gunzipSync(fs.readFileSync(path.join(out,row.label+'.raw.json.gz')))).result,rec=records.find(r=>r.label===row.label),audit=row.reward_audit,reference=op.reward_references[row.case],finish=rec.completion.end_ns,commonEnd=reference.reference_end_ns,E0=reference.completion_total_J_proxy,Q0=(reference.mean_AP_c-c.idle_c)*(commonEnd/1e9-35),es=[0],qs=[0];
  for(const t of raw.trace){es.push(es.at(-1)+t.increment);qs.push(qs.at(-1)+t.temperature_area-c.idle_c*t.dt);}
  function prefix(time){if(time<=35e9)return [0,0];let lo=0,hi=raw.trace.length;while(lo<hi){const mid=(lo+hi)>>>1;if(raw.trace[mid].start_ns<=time)lo=mid+1;else hi=mid;}const i=lo-1;if(time>=raw.trace.at(-1).end_ns)return [es.at(-1),qs.at(-1)];const tr=raw.trace[i],dt=(time-tr.start_ns)/1e9,part=W.partial(tr,dt,c,H);return [es[i]+part.increment,qs[i]+part.temperature_area-c.idle_c*dt];}
  const calls=JSON.parse(zlib.gunzipSync(fs.readFileSync(path.join(out,row.label+'.raw.json.gz')))).calls.filter(a=>!a.common_coalescing);need(audit.prefix_records.length===calls.length,'Every neural reward prefix');let prior=0;
  for(let i=0;i<calls.length;i++){const actual=audit.prefix_records[i],end=i+1<calls.length?calls[i+1].time_ns:Math.max(finish,commonEnd),eEnd=Math.min(end,finish),qEnd=Math.min(end,commonEnd),E=prefix(eEnd)[0]+c.baseline*(eEnd/1e9-35),Q=Math.max(0,prefix(qEnd)[1]),value=row.reward_kind==='PACKING_JOINT_COMPLETION'?Math.max(E/E0,Q/Q0):E/E0;need(actual.end_ns===end,'Causal reward endpoint');close(actual.completion_energy_prefix_J_proxy,E,'Completion total prefix',2e-6);close(actual.heat_excess_prefix_Cs,Q,'Common heat prefix',2e-6);close(actual.value,value,'Normalized objective prefix',2e-7);close(actual.cost0,2*(value-prior),'Reward telescope',2e-7);prior=value;}
  close(audit.cost_sum[0],2*prior,'Final completion objective',2e-6);close(audit.cost_sum[1],0,'No duplicated cost channel',1e-12);for(let k=2;k<4;k++)close(audit.cost_sum[k],row.metrics.cost_vector[k],'Unchanged soft deadline counts',2e-6);close(audit.cost_sum[4],row.metrics.cost_vector[4]+raw.requests.filter(q=>q.available_ns===null||q.available_ns>commonEnd).length/row.n,'Retained common-window unfinished penalty',2e-6);
 }
`+s.slice(end);
// The Float32/F64 neural tolerance is inherited unchanged; exact Torch replay is mandatory.
fs.writeFileSync(path.join(d,'audit.cjs'),s,{flag:'wx'});fs.copyFileSync(path.join(d,'../deep_repair_20261018/THERMAL_PURE_TEST.json'),path.join(d,'THERMAL_PURE_TEST.json'),fs.constants.COPYFILE_EXCL);
console.log('PACKING_INDEPENDENT_AUDIT_BUILT');
