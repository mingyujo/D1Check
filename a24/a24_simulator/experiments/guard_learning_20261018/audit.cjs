'use strict';
// Saved-only independent JS arithmetic/NN replay. No Python or native producer.
const fs=require('fs'),path=require('path'),crypto=require('crypto'),zlib=require('zlib');
const root=path.resolve(__dirname,'../..'),read=p=>JSON.parse(fs.readFileSync(p));
const sha=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex'),need=(v,s)=>{checks++;if(!v)throw Error(s);};
let checks=0,worst=0;const close=(a,b,s,tol=3e-7)=>{worst=Math.max(worst,Math.abs(a-b));need(Math.abs(a-b)<=tol,s+' '+Math.abs(a-b));};
const W=require('../work_window_20261017/reaccount.cjs'),T=require('../sustained_load_20261017/tensor_reader.cjs');
function dense(x,w,b,n,tanh=false){const y=new Float64Array(n);for(let i=0;i<n;i++){let v=b[i];for(let j=0;j<x.length;j++)v+=w[i*x.length+j]*x[j];y[i]=tanh?Math.tanh(v):v;}return y;}
function critic(weights,x,mask){const enc=x.map(a=>dense(a,weights['encode.0.weight'],weights['encode.0.bias'],48,true)),mean=new Float64Array(48),max=new Float64Array(48).fill(-Infinity),n=mask.filter(Boolean).length;for(let i=0;i<19;i++)if(mask[i])for(let j=0;j<48;j++){mean[j]+=enc[i][j]/n;max[j]=Math.max(max[j],enc[i][j]);}const c=new Float64Array(96);c.set(mean);c.set(max,48);return dense(dense(c,weights['critic.0.weight'],weights['critic.0.bias'],64,true),weights['critic.2.weight'],weights['critic.2.bias'],5);}
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
 const inputs=read(op.inputs.path),design=[...inputs.training,...inputs.evaluation],records=[],nets=new Map();let nn=0,greedy=0,sampled=0,minmargin=Infinity,ties=0;const refs=new Map();
 for(const src of op.evaluation_reference_metrics)for(const row of read(src.path).rows)if(row.policy==='EDF')refs.set(row.case,row.common.end_ns);
 for(const row of res.rows.filter(r=>r.kind==='REFERENCE')){const raw=JSON.parse(zlib.gunzipSync(fs.readFileSync(path.join(out,row.label+'.raw.json.gz')))).result;need(raw.requests.every(q=>q.available_ns!==null),'Every training reference completed');refs.set(row.case,Math.max(...raw.requests.map(q=>q.available_ns)));}
 need(read(path.join(out,'STOCHASTIC_REPLAY.json')).status==='PASS'&&read(path.join(out,'STOCHASTIC_REPLAY.json')).episodes===96&&read(path.join(out,'STOCHASTIC_REPLAY.json')).exact_saved_optimizer_update_replays===48,'All sampled training episodes replayed');
 const integrate=(r,end)=>{const m=W.integrate(r,end,c,H);return {...m,baseline_percent:100*m.baseline_fraction};};
 for(const row of res.rows){
  if(row.network_sha256&&!nets.has(row.network_sha256))nets.set(row.network_sha256,T.network(path.join(out,row.network_file),row.network_sha256));const net=nets.get(row.network_sha256);
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
  const binding=op.bank_map[row.case],bank=JSON.parse(zlib.gunzipSync(fs.readFileSync(binding.path))),jobmap=new Map(bank.jobs.map(j=>[j.request_id,j]));
  for(const job of q){const expected=jobmap.get(job.request_id);need(expected&&job.queue_entry_ns===expected.queue_entry_ns&&job.scheduled_arrival_ns===expected.scheduled_arrival_ns&&job.deadline_ns===expected.deadline_ns,'Frozen public/latent bank request binding');if(job.route!==null)need(JSON.stringify(job.timing)===JSON.stringify(expected.routes[job.route]),'Exact engine-only latent draw');}
  if(row.network_sha256){
   need(row.network_sha256===net.digest,'Frozen full network digest');need(sha(path.join(out,row.label+'.frames.pt.gz'))===row.frames_sha256,'Preserved frames SHA');
   for(const a of raw.calls.filter(a=>!a.common_coalescing)){
    need(a.x.length===19&&a.x.every(x=>x.length===32&&x.every(Number.isFinite))&&a.mask.length===19&&a.mask[a.chosen],'NN ABI/mask');
    need(a.fixed_ATC_prior_logit===0&&!a.future_actual_work_used&&!a.future_arrivals_used,'Public-only neural policy');
    const logits=T.logits(net.net,a.x,a.mask),mx=Math.max(...logits),lp=logits[a.chosen]-mx-Math.log(logits.reduce((sum,x)=>sum+Math.exp(x-mx),0)),value=critic(net.net,a.x,a.mask);close(a.old_logp,lp,'Independent every selected neural log probability',2e-4);for(let k=0;k<5;k++)close(a.critic_value[k],value[k],'Independent critic forward',2e-4);need(a.collect===(row.kind==='TRAIN'),'Stochastic versus greedy provenance');let best=0;for(let j=1;j<19;j++)if(logits[j]>logits[best])best=j;
    if(row.kind==='EVAL')need(best===a.chosen,'Independent Float64 greedy network argmax '+row.label+' at '+a.time_ns);else need(a.mask[a.chosen],'Stochastic selected action physically allowed');
    const sorted=logits.filter(Number.isFinite).sort((a,b)=>b-a);if(sorted.length>1){const margin=sorted[0]-sorted[1];minmargin=Math.min(minmargin,margin);if(margin===0)ties++;}
    nn++;if(row.kind==='EVAL')greedy++;else sampled++;if(nn%64===0)await new Promise(resolve=>setTimeout(resolve,10));
   }
  }
  const spec0=design.find(x=>x.id===row.case),drain0=spec0.drain_stop_s*1e9,loss=[0,0];for(const job of q){if(job.response_ns===null||job.response_ns>drain0)continue;const late=Math.max(0,(job.response_ns-job.deadline_ns)/1e9);loss[job.priority==='U'?0:1]+=(Number(late>1e-9)+.2*Math.min(5,late/Math.max(.05,(job.deadline_ns-job.scheduled_arrival_ns)/1e9)))/row.n;}for(let k=0;k<2;k++)close(loss[k],m.cost_vector[k+2],'Independent retained deadline penalties',1e-9);
  if(row.policy==='REPAIR_OFF_NN')for(const call of raw.calls.filter(a=>!a.common_coalescing)){
   let bound=0;for(const job of call.nominal_ready)bound+=Math.max(...['CPU','GPU'].map(r=>call.nominal_vectors[job.request_id+'|'+r].reduce((a,b)=>a+b,0)));for(const job of call.nominal_owners)bound+=job.remaining+job.vector.slice(job.stage+1).reduce((a,b)=>a+b,0);
   const expected=call.time_ns/1e9+Math.max(.5,.5+bound/c.minimum_speed+.2);for(const forecast of call.forecasts){close(forecast.forecast_end_s,expected,'Public-only common local forecast horizon',1e-9);need(forecast.local_normalizer===forecast.visible_jobs&&forecast.visible_jobs<=10,'Local-only forecast normalizer');}}
  if(true){
   const spec=design.find(x=>x.id===row.case),drain=integrate(r,Math.round(spec.drain_stop_s*1e9)),last=q.every(x=>x.available_ns!==null)?Math.max(...q.map(x=>x.available_ns)):null;
   close(drain.total_J_proxy,m.total_J_proxy,'Original energy');for(const k of ['on_time','urgent_on_time','response_missing','incomplete'])need(drain[k]===m[k],'SLA '+k);
   const latency=q.filter(x=>x.response_ns!==null&&x.response_ns<=Math.round(spec.drain_stop_s*1e9)).map(x=>(x.response_ns-x.scheduled_arrival_ns)/1e9).sort((a,b)=>a-b);
   if(latency.length)close(latency[Math.ceil(.95*latency.length)-1],m.P95_completed_response_s,'Independent P95',1e-12);
   const supply=integrate(r,Math.round(spec.supply_stop_s*1e9)),before=integrate(r,Math.round((spec.supply_stop_s-60)*1e9));
   let work=0,execution=0;for(const t of r.trace){if(t.start_ns>=spec.supply_stop_s*1e9)break;const dt=(Math.min(t.end_ns,spec.supply_stop_s*1e9)-t.start_ns)/1e9;for(const a of t.active)if(a.stage===1){work+=dt*t.speeds[a.route];execution+=dt;}}
   const queueEvents=[];for(const x of q){queueEvents.push([x.queue_entry_ns,1]);if(x.dispatch_ns!==null)queueEvents.push([x.dispatch_ns,-1]);}
   queueEvents.sort((a,b)=>a[0]-b[0]||b[1]-a[1]);let pending=0,peakqueue=0;for(const [,delta] of queueEvents){pending+=delta;need(pending>=0,'Queue accounting');peakqueue=Math.max(peakqueue,pending);}
   need(row.reference_end_ns===refs.get(row.case),'Fixed reference endpoint from separate EDF data');
   records.push({label:row.label,case:row.case,policy:row.policy,kind:row.kind,reference_end_ns:row.reference_end_ns,reward_audit:row.reward_audit,condition:spec.condition,n:row.n,original:m,completion:last===null?null:integrate(r,last),supply,
    queue_peak:peakqueue,mean_queue_wait_s:q.every(x=>x.dispatch_ns!==null)?q.reduce((s,x)=>s+(x.dispatch_ns-x.queue_entry_ns)/1e9,0)/q.length:null,
    post_supply_clearance_s:last===null?null:Math.max(0,last/1e9-spec.supply_stop_s),completion_J_proxy_per_request:last===null?null:integrate(r,last).total_J_proxy/q.length,
    last60_supply_mean_AP_c:(supply.temperature_area-before.temperature_area)/60,active_execution_mean_speed:work/execution,
    completion_energy_defined:last!==null,all_completed:last!==null,post_completion_activation_tail_J_proxy:last===null?null:H*c.idle_tail_s,raw_sha256:row.raw_sha256,__raw:{trace:r.trace,requests:q},__spec:spec});
  }
  console.log('AUDITED',row.label,'checks',checks,'NN',nn);
 }
 for(const row of records){const end=row.reference_end_ns;row.common=integrate(row.__raw,end);row.same_work_common_eligible=row.completion!==null&&row.completion.end_ns<=end;delete row.__raw;delete row.__spec;}
 const summary=[];
 for(const row of res.rows.filter(r=>r.network_sha256)){const r=records.find(x=>x.label===row.label);if(row.policy==='REPAIR_OFF_NN'){
 const raw=JSON.parse(zlib.gunzipSync(fs.readFileSync(path.join(out,row.label+'.raw.json.gz')))).result,spec=design.find(x=>x.id===row.case),peak=Math.max(...raw.trace.filter(t=>t.start_ns<row.reference_end_ns).map(t=>Math.max(t.state.temperature_c,W.partial(t,(Math.min(t.end_ns,row.reference_end_ns)-t.start_ns)/1e9,c,H).temperature_c)),spec.temperature_c);
 const expected=[(r.completion||integrate(raw,Math.round(spec.drain_stop_s*1e9))).total_J_proxy/(row.n*.35),(r.common.mean_AP_c-26)/10+.1*Math.max(0,peak-32)/5,...r.original.cost_vector.slice(2)];expected[4]+=raw.requests.filter(q=>q.available_ns===null||q.available_ns>row.reference_end_ns).length/row.n;
 for(let i=0;i<5;i++)close(row.reward_audit.cost_sum[i],expected[i],'Independent repaired reward telescope',2e-6);
 }else for(let i=0;i<5;i++)close(row.reward_audit.cost_sum[i],r.original.cost_vector[i],'Original reward remains unchanged',2e-6);}
 for(const arm of op.arms){const info=read(path.join(out,arm+'.LEARNING.json')),tr=res.rows.filter(r=>r.kind==='TRAIN'&&r.policy===arm);need(tr.length===32&&info.new_updates===16&&info.new_episodes===32&&info.new_Adam_steps>0,'Equal finite learning budget');need(info.initial_digest===res.initial_network_sha256&&info.final_digest!==info.initial_digest,'Actual NN changed');T.network(path.join(out,arm+'.FINAL_EP032.pt.gz'),info.final_digest);
 for(let i=0;i<32;i++){const expected=i===31?info.final_digest:tr[i+1].network_sha256;T.network(path.join(out,tr[i].label+'.AFTER.pt.gz'),expected);if(i%2===0)need(expected===tr[i].network_sha256,'No early PPO update');else need(expected!==tr[i].network_sha256,'Every paired PPO update changes network');}}
 save(path.join(out,'WORK_METRICS.json'),{rows:records,summary,definitions:'Completion null unless all requests AVAILABLE; same-walltime supply energy/AP and censored common window explicit',measured_J:null});
 save(path.join(out,'AUDIT.json'),{status:'PASS',utc:new Date().toISOString(),command:process.argv,checks,max_absolute_error:worst,independent_greedy_NN_frames:greedy,sampled_NN_banks_checked:sampled,total_NN_banks:nn,
  neural_replay:'Every EVAL greedy argmax independently replayed in Float64; TRAIN banks/masks and saved same-Torch stochastic RNG replay separately checked',distinct_verified_networks:nets.size,tensor_digest_verified:true,minimum_choice_margin:Number.isFinite(minmargin)?minmargin:null,exact_ties:ties,
  result_sha256:sha(path.join(out,'RESULT.json')),work_metrics_sha256:sha(path.join(out,'WORK_METRICS.json')),operation_sha256:sha(opfile),
  new_environment_START:0,new_Python_processes:0,new_training:0,cooperative_yield:true,original_artifacts_preserved:true,undefined_completion_energy_preserved:true,thermal_invariant_upper_c:thermal.refined_invariant_upper_c});
 console.log(JSON.stringify({status:'PASS',checks,NN:nn,worst,summary}));
}
main().catch(e=>{console.error(e.stack);process.exitCode=1;});
