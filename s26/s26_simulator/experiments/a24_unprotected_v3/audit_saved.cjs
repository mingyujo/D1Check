'use strict';
// New generation only; independent saved arithmetic, never execute an environment.
const fs=require('node:fs'),path=require('node:path'),z=require('node:zlib'),crypto=require('node:crypto');
const H=__dirname,R=path.resolve(H,'../..'),O=path.join(H,'artifacts/G001');
const read=p=>JSON.parse((p.endsWith('.gz')?z.gunzipSync(fs.readFileSync(p)):fs.readFileSync(p)).toString('utf8').replace(/^\uFEFF/,'')),sha=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex'),write=(p,x)=>fs.writeFileSync(p,JSON.stringify(x,null,2)+'\n',{flag:'wx'});
if(fs.existsSync(path.join(H,'AUDIT_OPERATION.json')))throw Error('Audit namespace already consumed');
const op=read(path.join(H,'OPERATION.json')),result=read(path.join(O,'RESULT.json')),receipts=fs.readFileSync(path.join(O,'receipts.jsonl'),'utf8').trim().split(/\r?\n/).map(JSON.parse),inputs=read(path.join(H,'INPUTS.json')).cases;
const pm=read(path.join(R,'experiments/capacity_power_v1/artifacts/G001/MODEL.json')),tm=read(path.join(R,'experiments/pipeline_thermal_v1/artifacts/G001/MODEL.json')),{coupled,steps}=require('../thermal_review_v3/cascade.cjs');
const auditOp={schema:'S26_NEW_UNPROTECTED_SAVED_AUDIT_V1',utc:new Date().toISOString(),pins:[__filename,path.join(H,'OPERATION.json'),path.join(O,'RESULT.json'),path.join(O,'receipts.jsonl'),path.join(R,'experiments/thermal_review_v3/cascade.cjs')].map(p=>({path:p,sha256:sha(p)})),new_environment_instances:0,new_training:0};write(path.join(H,'AUDIT_OPERATION.json'),auditOp);
let checks=0,maxAP=0,maxPower=0,maxEnergy=0,maxDense=0,requestCount=0,peakPredictedPower=0;const audited=[],outsidePower=[];
function need(ok,m){checks++;if(!ok)throw Error(m);}
need(receipts.filter(x=>x.event==='START').length===result.START,'START census');need(receipts.filter(x=>x.event==='COMPLETE').length===result.COMPLETE,'COMPLETE census');need(result.FAIL===0,'Unexpected failure omitted');
 need(new Set(result.rows.map(x=>x.label)).size===result.rows.length,'No duplicate saved labels');
 if(result.combined_START!==undefined){const inheritance=read(path.join(H,'INHERITANCE.json'));need(result.START+inheritance.prior_START===result.combined_START,'Combined START');need(result.COMPLETE+inheritance.prior_COMPLETE_receipts===result.combined_COMPLETE_receipts,'Combined COMPLETE receipts');need(inheritance.prior_FAIL===result.combined_FAIL,'Preserved FAIL');need(result.rows.length===527&&result.combined_START===528&&result.combined_FAIL===2,'Full lineage census');need(!result.rows.some(x=>x.label==='S271081_TRAIN_006'),'Failed training not replaced');}
 const paired=new Map;for(const r of result.rows.filter(r=>r.kind==='EVAL')){if(!paired.has(r.input))paired.set(r.input,[]);paired.get(r.input).push(r);}for(const rows of paired.values()){need(rows.length===7,'All seven policies retained');need(new Set(rows.map(x=>x.stream)).size===1,'Matched EVAL latent stream');}
for(const p of op.pins)need(sha(p.path)===p.sha256,'Source/input drift '+p.path);
for(const row of result.rows){
 const p=path.join(O,row.label+'.raw.json.gz');need(sha(p)===row.raw_sha256,'Raw changed '+row.label);const r=read(p),c=inputs.find(c=>c.id===row.input),ctx=c.context.initial_context.targets,a=ctx.AP.anchor,by=new Map(c.requests.map(q=>[q.ordinal,q])),N=c.n;
 need(r.requests.length===N,'All arrivals retained');requestCount+=N;
 if(row.policy==='EDF'||row.policy==='EDF_NPU_FIRST'){const choose=require('../plain_edf_v1/select.cjs').select;for(const decision of r.policy_decisions){const expected=choose(decision.public_observation,row.policy==='EDF'?['CPU','GPU','NPU']:['NPU','GPU','CPU']);need(expected.ordinal===decision.action.ordinal&&expected.route===decision.action.route,'Independent plain EDF choice');}}
 need((row.nominal_forecast_numerical_failures??0)===(r.nominal_compute.numerical_failure_forecasts??0),'Forecast diagnostic census');
 for(const q of r.requests){const original=by.get(q.ordinal);need(q.arrival===original.offset_ns/1e9,'Arrival');need(Math.abs(q.deadline-q.arrival-original.deadline_ms/1000)<1e-9,'Deadline');
  if(q.route!==null){need(q.route.startsWith(q.task+'_'),'Task route');need(q.task!=='detection'||q.route==='detection_CPU','Detection support');const t=q.times;need(t.dispatch>=q.arrival-1e-9,'No future dispatch');
   let prev=t.dispatch;for(const k of ['execution_start','host_inference_start','host_inference_return','output_ready','persist_complete','worker_release','AVAILABLE'])if(Number.isFinite(t[k])){need(t[k]>=prev-1e-8,'Phase order '+k);prev=t[k];}
   if(q.response!==null)need(Math.abs(q.response-(q.priority==='urgent'?t.output_ready:t.readback_end))<1e-8,'Actual response boundary');
  }
 }
 for(const pr of['all','urgent','normal']){const qs=r.requests.filter(q=>pr==='all'||q.priority===pr),responded=qs.filter(q=>q.response!==null),on=responded.filter(q=>q.response<=q.deadline+1e-9);need(on.length===row.service[pr].on_time,'Service numerator');need(qs.length===row.service[pr].planned,'Service denominator');need(responded.length===row.service[pr].completed,'Response completeness');}
 const ev=[];for(const q of r.requests)if(q.route!==null){ev.push([q.times.dispatch,1,q.route.split('_').at(-1)]);ev.push([q.available??r.observation_end_s,-1,q.route.split('_').at(-1)]);}ev.sort((a,b)=>a[0]-b[0]||a[1]-b[1]);const busy={CPU:0,GPU:0,NPU:0};
 for(const[t,d,slot]of ev){busy[slot]+=d;need(busy[slot]>=0&&busy[slot]<=1,'Physical slot collision');need(Object.values(busy).reduce((s,v)=>s+v,0)<=3,'Capacity');}
 let cpuEnd=-Infinity;for(const x of r.cpu_intervals){need(x.start>=cpuEnd-1e-8&&x.end>=x.start,'Shared CPU exclusivity');cpuEnd=x.end;}
 const sampleTimes=[...new Set([0,35,...r.curve.map(x=>x[0])])].filter(t=>t<=r.observation_end_s).sort((a,b)=>a-b),ref=coupled(steps(r.activity),sampleTimes,ctx.POWER_API.baseline.median_api_w,0,a.AP,a.SKIN,pm,tm),lookup=new Map(sampleTimes.map((t,i)=>[t,ref[i]]));
 for(const [t,T,P]of r.curve){const independent=lookup.get(t);maxAP=Math.max(maxAP,Math.abs(T-independent[1]));maxPower=Math.max(maxPower,Math.abs(P-independent[0]));peakPredictedPower=Math.max(peakPredictedPower,P);checks+=2;}
 if(r.curve.some(x=>x[2]<.13485732||x[2]>19.962810488))outsidePower.push(row.label);
 const independentJ=lookup.get(r.observation_end_s)[2]-lookup.get(35)[2];maxEnergy=Math.max(maxEnergy,Math.abs(independentJ-row.api_J));need(Math.abs(independentJ-row.api_J)<1e-6,'Independent energy');
 const fullJ=lookup.get(r.observation_end_s)[2]-lookup.get(0)[2];maxEnergy=Math.max(maxEnergy,Math.abs(fullJ-r.physics_J));need(Math.abs(fullJ-r.physics_J)<1e-6,'Whole-observation energy');
 const sumJ=r.integrals.reduce((s,x)=>s+x[2],0),sumH=r.integrals.reduce((s,x)=>s+x[3],0);need(Math.abs(sumJ-row.api_J)<1e-8,'Energy interval telescope');need(Math.abs(sumH/(row.observation_s-35)-row.AP_mean)<1e-8,'Temperature time mean');
 if(row.reward_telescope_error!==undefined){maxDense=Math.max(maxDense,row.reward_telescope_error);need(row.reward_telescope_error<1e-7,'Reward telescopes');}
 need(row.physical_validation===false&&row.policy_superiority_claim_allowed===false,'Conditional status retained');audited.push(row.label);
 if(audited.length%40===0)console.log(JSON.stringify({status:'AUDIT_PROGRESS',cases:audited.length,checks}));
}
need(maxAP<1e-7&&maxPower<1e-7,'Independent physical cascade');
for(const p of auditOp.pins)need(sha(p.path)===p.sha256,'Audit input changed');
const audit={status:'PASS_NEW_SAVED_PHYSICAL_CONTRACT_AND_ARITHMETIC',utc:new Date().toISOString(),cases:audited.length,request_count:requestCount,checks,max_AP_reference_error_C:maxAP,max_power_reference_error_API_W:maxPower,max_energy_reference_error_API_J:maxEnergy,max_reward_telescope_error:maxDense,max_predicted_sample_power_API_W:peakPredictedPower,power_outside_marginal_case_labels:outsidePower,NN_independent_replay_pending:true,physical_accuracy_validated:false,new_environment_instances:0,new_training:0};write(path.join(O,'AUDIT.json'),audit);console.log(JSON.stringify(audit));
