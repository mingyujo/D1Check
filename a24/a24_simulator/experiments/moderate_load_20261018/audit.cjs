'use strict';
// Saved-only independent JS arithmetic/NN replay. No Python or native producer.
const fs=require('fs'),path=require('path'),crypto=require('crypto'),zlib=require('zlib');
const root=path.resolve(__dirname,'../..'),read=p=>JSON.parse(fs.readFileSync(p));
const sha=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex'),need=(v,s)=>{checks++;if(!v)throw Error(s);};
let checks=0,worst=0;const close=(a,b,s,tol=3e-7)=>{worst=Math.max(worst,Math.abs(a-b));need(Math.abs(a-b)<=tol,s+' '+Math.abs(a-b));};
const W=require('../work_window_20261017/reaccount.cjs'),T=require('../sustained_load_20261017/tensor_reader.cjs');
const save=(p,v)=>fs.writeFileSync(p,JSON.stringify(v,null,2)+'\n',{flag:'wx'});
async function main(){
 const opfile=path.join(__dirname,'OPERATION.json'),op=read(opfile),out=path.join(root,op.output_dir),res=read(path.join(out,'RESULT.json')),c=op.physics,thermal=read(path.join(__dirname,'THERMAL_PURE_TEST.json'));
 for(const p of [...op.sources,...op.input_pins])need(sha(p.path)===p.sha256,'Source/input SHA '+p.path);
 need(res.operation_sha256===sha(opfile),'Bound result');need(!fs.existsSync(path.join(out,'AUDIT.json')),'Audit consumed');
 const receipts=fs.readFileSync(path.join(out,'receipts.jsonl'),'utf8').trim().split('\n').map(JSON.parse);
 need(receipts.filter(e=>e.event==='START').length===op.planned_START&&receipts.filter(e=>e.event==='COMPLETE').length===op.planned_START&&!receipts.some(e=>e.event==='FAIL'),'Exact complete native lifecycles');
 need(new Set(receipts.filter(e=>e.event==='START').map(e=>e.identity)).size===op.planned_START,'Unique identities');
 const model=read(path.join(root,'results/STATE_COST_IDENTIFICATION_20261017_01/MODEL.json')),solo=Object.fromEntries(model.supported_states.map((s,i)=>[s,model.coefficients_W_proxy[i]]));
 const H=solo.classification_GPU+solo.detection_CPU-solo['classification_GPU+detection_CPU'];delete solo['classification_GPU+detection_CPU'];solo.detection_GPU=.6013808404579677;
 const net=T.network(op.checkpoint.path,res.network_sha256),design=read(op.inputs.path).cases,records=[];let nn=0,minmargin=Infinity,ties=0;
 const integrate=(r,end)=>{const m=W.integrate(r,end,c,H);return {...m,baseline_percent:100*m.baseline_fraction};};
 for(const row of res.rows){
  const rawfile=path.join(out,row.label+'.raw.json.gz');need(sha(rawfile)===row.raw_sha256,'Raw SHA');const raw=JSON.parse(zlib.gunzipSync(fs.readFileSync(rawfile))),r=raw.result,q=r.requests,m=row.metrics;
  need(q.length===row.n,'All arrivals retained');for(const k of Object.keys(c))close(r.config[k],c[k],'Frozen physics',0);
  const lanes={},pointer={CPU:0,GPU:0},sums=new Map(q.map(x=>[x.request_id,new Float64Array(5)]));
  for(const route of ['CPU','GPU']){lanes[route]=q.filter(x=>x.route===route).sort((a,b)=>a.dispatch_ns-b.dispatch_ns);const jobs=lanes[route];for(let i=1;i<jobs.length;i++)need(jobs[i-1].available_ns!==null&&jobs[i-1].available_ns<=jobs[i].dispatch_ns,'Exclusive occupancy');}
  let previous=35e9,temperature=r.initial_ap_c;
  for(const t of r.trace){
   need(t.start_ns===previous&&t.end_ns>previous,'Causal trace');previous=t.end_ns;const dt=(t.end_ns-t.start_ns)/1e9;close(dt,t.dt,'dt',1e-12);close(t.state.temperature_c,temperature,'Continuous thermal state');
   need(Math.max(t.state.temperature_c,t.next_state.temperature_c)<=thermal.refined_invariant_upper_c+1e-7,'Universal thermal invariant');
   need(new Set(t.active.map(a=>a.route)).size===t.active.length&&t.active.length<=2,'Owners');let dyn=0;
   const leak=Math.exp(Math.max(-Math.log(3),Math.min(Math.log(3),c.strength*c.leakage_per_c*(t.state.temperature_c-c.reference_c))));
   for(const a of t.active){
    const f=a.stage===1?Math.max(c.minimum_speed,1/(1+c.strength*(a.route==='CPU'?c.cpu_slope:c.gpu_slope)*Math.max(0,t.state.temperature_c-c.onset_c))):1;
    close(f,t.speeds[a.route],'Speed',1e-12);const label=(a.task==='C'?'classification':'detection')+'_'+a.route;
    dyn+=(solo[label]-H)*((1-c.leakage_fraction)*f**3+c.leakage_fraction*leak);
    const jobs=lanes[a.route];while(pointer[a.route]+1<jobs.length&&jobs[pointer[a.route]+1].dispatch_ns<=t.start_ns)pointer[a.route]++;
    const job=jobs[pointer[a.route]];need(job&&job.dispatch_ns<=t.start_ns&&job.task===a.task,'Owner binding');
    const stage=['execution_start_ns','output_ready_ns','persist_complete_ns','worker_release_ns','available_ns'].filter(k=>job[k]!=null&&job[k]<=t.start_ns).length;
    need(stage===a.stage,'Phase binding');sums.get(job.request_id)[stage]+=dt*f;
   }
   close(dyn*dt,t.dynamic,'Independent dynamic energy');close(c.baseline*dt,t.baseline,'Baseline');
   // Independently calculated left-state dynamic power, prior audited closed RC integral.
   const independent={...t,dynamic:dyn*dt},part=W.partial(independent,dt,c,H);
   close(part.increment,t.increment,'Independent total increment');close(part.temperature_area,t.temperature_area,'Independent thermal area');
   close(part.temperature_c,t.next_state.temperature_c,'Independent RC temperature');close(part.shared_z,t.next_state.shared_z,'Shared state');temperature=part.temperature_c;
  }
  for(const job of q){if(job.available_ns!==null)for(let i=0;i<5;i++)close(sums.get(job.request_id)[i],job.timing.stages_ns[i]/1e9,'Conserved latent phase work');
   if(job.dispatch_ns!==null)need(job.dispatch_ns>=job.queue_entry_ns,'Public arrival before dispatch');
   need(job.response_ns===null||job.response_ns===job[job.task==='C'?'output_ready_ns':'persist_complete_ns'],'Response boundary');}
  need(raw.calls.length===r.decisions.length,'Every actual decision has a call');
  for(let i=0;i<raw.calls.length;i++){const a=raw.calls[i],d=r.decisions[i];need(a.time_ns===d.time_ns&&JSON.stringify(a.action)===JSON.stringify(d.action),'Action to event binding');}
  if(row.policy.includes('_NN')){
   need(row.network_sha256===net.digest,'Frozen full network digest');need(sha(path.join(out,row.label+'.frames.pt.gz'))===row.frames_sha256,'Preserved frames SHA');
   for(const a of raw.calls.filter(a=>!a.common_coalescing)){
    need(a.x.length===19&&a.x.every(x=>x.length===32&&x.every(Number.isFinite))&&a.mask.length===19&&a.mask[a.chosen],'NN ABI/mask');
    need(a.fixed_ATC_prior_logit===0&&!a.future_actual_work_used&&!a.future_arrivals_used,'Public-only neural policy');
    const logits=T.logits(net.net,a.x,a.mask);let best=0;for(let j=1;j<19;j++)if(logits[j]>logits[best])best=j;
    need(best===a.chosen,'Independent Float64 network argmax '+row.label+' at '+a.time_ns);
    const sorted=logits.filter(Number.isFinite).sort((a,b)=>b-a);if(sorted.length>1){const margin=sorted[0]-sorted[1];minmargin=Math.min(minmargin,margin);if(margin===0)ties++;}
    nn++;if(nn%64===0)await new Promise(resolve=>setTimeout(resolve,10));
   }
  }
  if(row.kind==='DENSITY'){
   const spec=design.find(x=>x.id===row.case),drain=integrate(r,Math.round(spec.drain_stop_s*1e9)),last=q.every(x=>x.available_ns!==null)?Math.max(...q.map(x=>x.available_ns)):null;
   close(drain.total_J_proxy,m.total_J_proxy,'Original energy');for(const k of ['on_time','urgent_on_time','response_missing','incomplete'])need(drain[k]===m[k],'SLA '+k);
   const latency=q.filter(x=>x.response_ns!==null&&x.response_ns<=Math.round(spec.drain_stop_s*1e9)).map(x=>(x.response_ns-x.scheduled_arrival_ns)/1e9).sort((a,b)=>a-b);
   if(latency.length)close(latency[Math.ceil(.95*latency.length)-1],m.P95_completed_response_s,'Independent P95',1e-12);
   const supply=integrate(r,Math.round(spec.supply_stop_s*1e9)),before=integrate(r,Math.round((spec.supply_stop_s-60)*1e9));
   let work=0,execution=0;for(const t of r.trace){if(t.start_ns>=spec.supply_stop_s*1e9)break;const dt=(Math.min(t.end_ns,spec.supply_stop_s*1e9)-t.start_ns)/1e9;for(const a of t.active)if(a.stage===1){work+=dt*t.speeds[a.route];execution+=dt;}}
   const queueEvents=[];for(const x of q){queueEvents.push([x.queue_entry_ns,1]);if(x.dispatch_ns!==null)queueEvents.push([x.dispatch_ns,-1]);}
   queueEvents.sort((a,b)=>a[0]-b[0]||b[1]-a[1]);let pending=0,peakqueue=0;for(const [,delta] of queueEvents){pending+=delta;need(pending>=0,'Queue accounting');peakqueue=Math.max(peakqueue,pending);}
   records.push({label:row.label,case:row.case,policy:row.policy,condition:spec.condition,n:row.n,original:m,completion:last===null?null:integrate(r,last),supply,
    queue_peak:peakqueue,mean_queue_wait_s:q.every(x=>x.dispatch_ns!==null)?q.reduce((s,x)=>s+(x.dispatch_ns-x.queue_entry_ns)/1e9,0)/q.length:null,
    post_supply_clearance_s:last===null?null:Math.max(0,last/1e9-spec.supply_stop_s),completion_J_proxy_per_request:last===null?null:integrate(r,last).total_J_proxy/q.length,
    last60_supply_mean_AP_c:(supply.temperature_area-before.temperature_area)/60,active_execution_mean_speed:work/execution,
    completion_energy_defined:last!==null,all_completed:last!==null,post_completion_activation_tail_J_proxy:last===null?null:H*c.idle_tail_s,raw_sha256:row.raw_sha256,__raw:{trace:r.trace,requests:q},__spec:spec});
  }
  console.log('AUDITED',row.label,'checks',checks,'NN',nn);
 }
 for(const row of records){const peers=records.filter(x=>x.case===row.case&&x.policy!=='GUARD_OFF_NN'),complete=peers.every(x=>x.completion!==null),end=complete?Math.max(...peers.map(x=>x.completion.end_ns)):Math.round(row.__spec.drain_stop_s*1e9);row.common=integrate(row.__raw,end);row.common_fallback_to_registered_drain=!complete;delete row.__raw;delete row.__spec;}
 const sum=(a,f)=>a.reduce((s,x)=>s+f(x),0),summary=[];
 for(const factor of op.rate_multipliers){
  const local=records.filter(r=>r.condition.rate_multiplier===factor),refs=Object.fromEntries(local.filter(r=>r.policy==='EDF').map(r=>[r.case,r])),B=Object.values(refs),all=local.every(r=>r.completion!==null);
  const base=all?sum(B,r=>r.completion.total_J_proxy):null,commonbase=sum(B,r=>r.common.total_J_proxy),supplybase=sum(B,r=>r.supply.total_J_proxy);
  for(const policy of op.policies){const g=local.filter(r=>r.policy===policy),J=all?sum(g,r=>r.completion.total_J_proxy):null;
   summary.push({supply_s:null,rate_multiplier:factor,policy,requests:sum(g,r=>r.n),mean_completion_duration_s:g.every(r=>r.completion!==null)?sum(g,r=>r.completion.duration_s)/4:null,
    mean_completion_total_J_proxy:J===null?null:J/4,completion_saving_percent:all?100*(1-J/base):null,
    common_saving_percent:100*(1-sum(g,r=>r.common.total_J_proxy)/commonbase),supply_saving_percent:100*(1-sum(g,r=>r.supply.total_J_proxy)/supplybase),complete_work_energy_comparison_defined:all,
    mean_supply_total_J_proxy:sum(g,r=>r.supply.total_J_proxy)/4,supply_baseline_percent:100*sum(g,r=>r.supply.baseline_J_proxy)/sum(g,r=>r.supply.total_J_proxy),
    completion_baseline_percent:J===null?null:100*sum(g,r=>r.completion.baseline_J_proxy)/J,completion_J_proxy_per_request:J===null?null:J/sum(g,r=>r.n),mean_supply_AP_c:sum(g,r=>r.supply.mean_AP_c)/4,
    mean_common_AP_c:sum(g,r=>r.common.mean_AP_c)/4,mean_common_AP_delta_c:sum(g,r=>r.common.mean_AP_c-refs[r.case].common.mean_AP_c)/4,
    mean_supply_AP_delta_c:sum(g,r=>r.supply.mean_AP_c-refs[r.case].supply.mean_AP_c)/4,mean_last60_AP_c:sum(g,r=>r.last60_supply_mean_AP_c)/4,
    on_time:sum(g,r=>r.original.on_time),urgent_on_time:sum(g,r=>r.original.urgent_on_time),urgent_planned:sum(g,r=>r.original.urgent_planned),response_missing:sum(g,r=>r.original.response_missing),incomplete:sum(g,r=>r.original.incomplete),
    on_time_delta:sum(g,r=>r.original.on_time-refs[r.case].original.on_time),urgent_delta:sum(g,r=>r.original.urgent_on_time-refs[r.case].original.urgent_on_time),
    no_SLA_harm_every_case:g.every(r=>r.original.on_time>=refs[r.case].original.on_time&&r.original.urgent_on_time>=refs[r.case].original.urgent_on_time&&r.original.incomplete===0&&r.original.response_missing===0)});
  }
 }
 need(res.network_and_training_RNG_unchanged,'Full runtime frozen');
 save(path.join(out,'WORK_METRICS.json'),{rows:records,summary,definitions:'Completion null unless all requests AVAILABLE; same-walltime supply energy/AP and censored common window explicit',measured_J:null});
 const choice=[];for(const row of res.rows){const raw=JSON.parse(zlib.gunzipSync(fs.readFileSync(path.join(out,row.label+'.raw.json.gz')))),r=raw.result,ds=r.decisions.filter(x=>x.action.kind==='DISPATCH'),spec=design.find(x=>x.id===row.case);let occupied=0;
 for(const t of r.trace){const a=Math.max(35e9,t.start_ns),b=Math.min(spec.supply_stop_s*1e9,t.end_ns);if(b>a)occupied+=(b-a)/1e9*t.active.length;}
 const multiple=ds.filter(x=>x.public_state.queue.length>1).length,both=ds.filter(x=>x.public_state.owners.length===0).length,joint=ds.filter(x=>x.public_state.queue.length>1&&x.public_state.owners.length===0).length;
 need(ds.length===row.n,'One dispatch per arrival');choice.push({label:row.label,case:row.case,policy:row.policy,condition:row.condition,dispatches:ds.length,multiple_ready_percent:100*multiple/ds.length,both_routes_free_percent:100*both/ds.length,joint_choice_percent:100*joint/ds.length,supply_route_utilization:occupied/(2*spec.condition.supply_s),wait_s:r.wait_used_ns/1e9});}
 let prefix=0;for(const a of design.filter(x=>x.condition.supply_s===60)){const b=design.find(x=>x.condition.supply_s===120&&x.condition.pattern===a.condition.pattern&&x.condition.rate_multiplier===a.condition.rate_multiplier),sa=JSON.parse(zlib.gunzipSync(fs.readFileSync(path.join(out,a.id+'.BANK.json.gz')))),sb=JSON.parse(zlib.gunzipSync(fs.readFileSync(path.join(out,b.id+'.BANK.json.gz'))));
 need(JSON.stringify(sa.jobs)===JSON.stringify(sb.jobs.slice(0,sa.jobs.length)),'Exact latent/admission 60/120 prefix');for(const [k,v]of Object.entries(sa.nominal_vectors))need(JSON.stringify(v)===JSON.stringify(sb.nominal_vectors[k]),'Public nominal prefix');prefix+=sa.jobs.length;}
 save(path.join(out,'CHOICE_DIAGNOSIS.json'),{rows:choice,dispatch_only_excludes_WAIT:true,exact_prefix_jobs:prefix});
 save(path.join(out,'AUDIT.json'),{status:'PASS',utc:new Date().toISOString(),command:process.argv,checks,max_absolute_error:worst,independent_NN_frames:nn,
  neural_replay:'Every saved actual neural input bank; independent Float64 implementation; argmax checked, not bitwise Torch logits',network_sha256:net.digest,tensor_digest_verified:true,minimum_choice_margin:Number.isFinite(minmargin)?minmargin:null,exact_ties:ties,
  result_sha256:sha(path.join(out,'RESULT.json')),work_metrics_sha256:sha(path.join(out,'WORK_METRICS.json')),operation_sha256:sha(opfile),
  new_environment_START:0,new_Python_processes:0,new_training:0,cooperative_yield:true,original_artifacts_preserved:true,undefined_completion_energy_preserved:true,thermal_invariant_upper_c:thermal.refined_invariant_upper_c});
 console.log(JSON.stringify({status:'PASS',checks,NN:nn,worst,summary}));
}
main().catch(e=>{console.error(e.stack);process.exitCode=1;});
