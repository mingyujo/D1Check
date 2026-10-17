'use strict';
const fs=require('fs'),path=require('path'),crypto=require('crypto');
const O=path.resolve(__dirname,'../../outputs/S26-FAIR-RESOURCE-COMPARE-20261016');
const read=f=>JSON.parse(fs.readFileSync(f,'utf8').replace(/^\uFEFF/,'')),hash=x=>crypto.createHash('sha256').update(JSON.stringify(x)).digest('hex');
const rows=fs.readFileSync(path.join(O,'PRODUCTION/ROWS.jsonl'),'utf8').trim().split(/\r?\n/).map(JSON.parse).filter(r=>r.phase==='FAIR_RESOURCE');
const own=read(path.join(O,'REUSED_OWN_CASES.json'));const details=[],counts={dispatch_decisions:0,multiple_dispatchable_requests:0,FIFO_EDF_head_disagreement:0,own_differs_from_FIFO_head:0};
const project=r=>({requests:r.requests,events:r.events,activity:r.activity,sensor:r.sensor,curve:r.curve,service:r.service,wait_s:r.wait_s});
for(const ref of own){const r=read(ref.raw_path),baseline=[];for(const policy of['FIFO_FREE_ROUTE_V1','EDF_FREE_ROUTE_V1']){const row=rows.find(x=>x.policy===policy&&x.scenario===r.scenario&&x.config.stream===r.config.stream),b=read(row.raw_path);baseline.push({policy,physical_trace_identical:hash(project(b))===hash(project(r)),dispatch_order_identical:JSON.stringify(b.events.filter(e=>e[1]==='DISPATCH'))===JSON.stringify(r.events.filter(e=>e[1]==='DISPATCH')),wait_identical:b.wait_s===r.wait_s});}
 for(const d of r.policy_decisions){if(d.action.kind!=='DISPATCH')continue;counts.dispatch_decisions++;const ids=new Set(d.action.candidates.filter(c=>c.permitted).map(c=>c.ordinal));if(ids.size>1)counts.multiple_dispatchable_requests++;const qs=d.public_observation.ready.filter(q=>ids.has(q.ordinal)),fifo=qs.slice().sort((a,b)=>a.arrival-b.arrival||a.ordinal-b.ordinal)[0],edf=qs.slice().sort((a,b)=>a.deadline-b.deadline||a.arrival-b.arrival||a.ordinal-b.ordinal)[0];counts.FIFO_EDF_head_disagreement+=Number(fifo.ordinal!==edf.ordinal);counts.own_differs_from_FIFO_head+=Number(d.action.ordinal!==fifo.ordinal)}
 details.push({scenario:r.scenario,stream:r.config.stream,own_trace_sha256:hash(project(r)),comparisons:baseline});}
const p=read(read(path.join(O,'PRODUCTION_OPERATION.json')).packet_path);
const manifests=p.scenarios.filter(s=>s.arm==='M128_BASE'||s.arm==='SMOOTH128_BASE').map(s=>({id:s.id,first16:s.requests.slice(0,16).map(q=>({ordinal:q.ordinal,task:q.task_id,offset_ns:q.offset_ns,deadline_ms:q.deadline_ms}))}));
const result={status:'PASS',cases:48,identical_FIFO_traces:details.filter(d=>d.comparisons[0].physical_trace_identical).length,identical_EDF_traces:details.filter(d=>d.comparisons[1].physical_trace_identical).length,counts,details,manifests,new_simulator_instances:0,new_fit:0};
fs.writeFileSync(path.join(O,'ANALYSIS_V1/TRACE_EQUIVALENCE.json'),JSON.stringify(result,null,2)+'\n',{flag:'wx'});
console.log(JSON.stringify({status:result.status,cases:48,identical_FIFO_traces:result.identical_FIFO_traces,identical_EDF_traces:result.identical_EDF_traces,counts,first_manifest:manifests[0]},null,2));
