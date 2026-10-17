'use strict';
const fs=require('fs'),path=require('path'),z=require('zlib'),crypto=require('crypto'),W=require('../work_window_20261017/reaccount.cjs'),T=require('../sustained_load_20261017/tensor_reader.cjs');
const root=path.resolve(__dirname,'../..'),read=p=>JSON.parse(String(p).endsWith('.gz')?z.gunzipSync(fs.readFileSync(p)):fs.readFileSync(p)),sha=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
let checks=0,worst=0,NN=0;const need=(v,s)=>{checks++;if(!v)throw Error(s);},close=(a,b,s,tol=4e-7)=>{worst=Math.max(worst,Math.abs(a-b));need(Math.abs(a-b)<=tol,s+' '+Math.abs(a-b));};
const save=(p,x)=>fs.writeFileSync(p,JSON.stringify(x,null,2)+'\n',{flag:'wx'});
const same=require('node:util').isDeepStrictEqual;
async function main(){
 const op=read(path.join(__dirname,'OPERATION.json')),out=path.join(root,op.output_dir),res=read(path.join(out,'RESULT.json')),c=op.physics,parent=path.join(root,op.summary_output),old=read(path.join(parent,'EVALUATION.json'));
 for(const p of [...op.sources,...op.input_pins])need(sha(p.path)===p.sha256,'Frozen pin');
 need(read(path.join(out,'COMPLETE.json')).result_sha256===sha(path.join(out,'RESULT.json'))&&res.operation_sha256===sha(path.join(__dirname,'OPERATION.json')),'Result binding');
 const receipts=fs.readFileSync(path.join(out,'receipts.jsonl'),'utf8').trim().split('\n').map(JSON.parse);
 need(receipts.filter(r=>r.event==='START').length===40&&receipts.filter(r=>r.event==='COMPLETE').length===40&&!receipts.some(r=>r.event==='FAIL'),'Exact forty successful native episodes');
 need(new Set(receipts.filter(r=>r.event==='START').map(r=>r.identity)).size===40,'Unique native identities');
 need(res.new_training===0&&JSON.stringify(res.deadline_cost_weights)==='[8,4,30]','Original deadline penalty retained');
 const reward=read(path.join(__dirname,'SAVED_REWARD_DIAGNOSIS.json'));
 for(const [file,key,filter] of [['results/LOAD_DENSITY_20261017_01/WORK_METRICS.json','long_rows',r=>true],['results/COUPLED_345_20261017_01/RESULT.json','short_training_rows',r=>r.kind==='TRAIN']]){
  const source=read(path.join(root,file)).rows.filter(filter);need(source.length===reward[key].length,'All reward-window diagnostic rows');
  for(let i=0;i<source.length;i++){const r=source[i],m=r.original||r.metrics,peak=.1*Math.max(0,m.peak_AP_c-32)/5,h=m.cost_vector[1]-peak,rec=reward[key][i];need(rec.label===r.label,'Reward source label');close(rec.heat_energy_ratio,h/m.cost_vector[0],'Independent RC cost relation',1e-12);close(rec.difference_from_1_point4,h-1.4*m.cost_vector[0],'Independent reward duplication residual',1e-12);}
 }
 const nets={NN:T.network(op.checkpoint.path,res.networks.NN),ZERO:T.network(path.join(out,'ZERO_SNAPSHOT.pt.gz'),res.networks.ZERO)};
 for(const [key,weights] of Object.entries(nets.NN.net))for(let i=0;i<weights.length;i++)need(nets.ZERO.net[key][i]===(key==='actor.2.weight'||key==='actor.2.bias'?0:weights[i]),'Zero only final actor layer');
 const m=read(path.join(root,'results/STATE_COST_IDENTIFICATION_20261017_01/MODEL.json')),solo=Object.fromEntries(m.supported_states.map((s,i)=>[s,m.coefficients_W_proxy[i]]));
 const H=solo.classification_GPU+solo.detection_CPU-solo['classification_GPU+detection_CPU'];delete solo['classification_GPU+detection_CPU'];solo.detection_GPU=.6013808404579677;
 const records=[],summaries=[],compact=new Map(),phase=read(path.join(parent,'PHASE_PROOFS.json')).rows;
 for(const row of res.rows){
  const rawfile=path.join(out,row.label+'.raw.json.gz');need(sha(rawfile)===row.raw_sha256,'Raw SHA');const raw=read(rawfile),r=raw.result,q=r.requests;
  if(row.guard_enabled&&row.neural_head==='NN'){
   const before=read(path.join(root,op.original_output,row.case+'_RL.raw.json.gz'));need(same(r.trace,before.result.trace),'Independent every-term original physical reproduction');
   for(let i=0;i<q.length;i++)for(const k of ['request_id','route','queue_entry_ns','dispatch_ns','response_ns','execution_start_ns','output_ready_ns','persist_complete_ns','worker_release_ns','available_ns'])need(q[i][k]===before.result.requests[i][k],'Independent original clocks');
   need(raw.calls.length===before.calls.length,'Original call count');for(let i=0;i<raw.calls.length;i++)for(const k of ['time_ns','action','chosen','actions','x','mask','forecasts','forecast_scores','common_coalescing'])need(same(raw.calls[i][k],before.calls[i][k]),'Independent original neural bank '+k);
  }
  need(q.length===row.n,'All arrivals denominator');for(const k of Object.keys(c))close(r.config[k],c[k],'Same Physics',0);
  const bank=new Map(read(path.join(root,op.potential_output,row.case+'.BANK.json.gz')).jobs.map(j=>[j.request_id,j])),lanes={},pointer={CPU:0,GPU:0},work=new Map(q.map(x=>[x.request_id,[0,0,0,0,0]]));
  for(const route of ['CPU','GPU']){lanes[route]=q.filter(x=>x.route===route).sort((a,b)=>a.dispatch_ns-b.dispatch_ns);for(let i=1;i<lanes[route].length;i++)need(lanes[route][i-1].available_ns<=lanes[route][i].dispatch_ns,'Exclusive lane');}
  let previous=35e9,temp=r.initial_ap_c;
  for(const t of r.trace){
   need(t.start_ns===previous&&t.end_ns>previous,'Causal contiguous trace');previous=t.end_ns;const dt=(t.end_ns-t.start_ns)/1e9;close(dt,t.dt,'dt',1e-12);close(temp,t.state.temperature_c,'Continuous T');
   need(Math.max(t.state.temperature_c,t.next_state.temperature_c)<=phase.find(p=>p.case===row.case).upper+1e-7,'Same bank thermal barrier');
   need(t.active.length<=2&&new Set(t.active.map(a=>a.route)).size===t.active.length,'Owners');let dynamic=0;
   const leak=Math.exp(Math.max(-Math.log(3),Math.min(Math.log(3),c.strength*c.leakage_per_c*(temp-c.reference_c))));
   for(const a of t.active){const f=a.stage===1?Math.max(c.minimum_speed,1/(1+c.strength*(a.route==='CPU'?c.cpu_slope:c.gpu_slope)*Math.max(0,temp-c.onset_c))):1;
    close(f,t.speeds[a.route],'Thermal speed',1e-12);dynamic+=(solo[(a.task==='C'?'classification':'detection')+'_'+a.route]-H)*((1-c.leakage_fraction)*f**3+c.leakage_fraction*leak);
    const lane=lanes[a.route];while(pointer[a.route]+1<lane.length&&lane[pointer[a.route]+1].dispatch_ns<=t.start_ns)pointer[a.route]++;
    const job=lane[pointer[a.route]],stage=['execution_start_ns','output_ready_ns','persist_complete_ns','worker_release_ns','available_ns'].filter(k=>job[k]!=null&&job[k]<=t.start_ns).length;
    need(job.task===a.task&&stage===a.stage&&job.dispatch_ns<=t.start_ns,'Owner/phase binding');work.get(job.request_id)[stage]+=dt*f;
   }
   close(dynamic*dt,t.dynamic,'Dynamic integral');close(c.baseline*dt,t.baseline,'Baseline');const p=W.partial({...t,dynamic:dynamic*dt},dt,c,H);
   close(p.increment,t.increment,'Increment');close(p.temperature_c,t.next_state.temperature_c,'RC');close(p.temperature_area,t.temperature_area,'Thermal area');temp=p.temperature_c;
  }
  for(const job of q){const j=bank.get(job.request_id);need(j.queue_entry_ns===job.queue_entry_ns,'Admission unchanged');if(job.dispatch_ns!=null)need(JSON.stringify(j.routes[job.route].stages_ns)===JSON.stringify(job.timing.stages_ns)&&job.dispatch_ns>=job.queue_entry_ns,'Same realized work');if(job.available_ns!=null)for(let k=0;k<5;k++)close(work.get(job.request_id)[k],job.timing.stages_ns[k]/1e9,'Conserved work');}
  need(raw.calls.length===r.decisions.length,'Every actor call');let waited=0,unsafeChosen=0,expandedStates=0,clipped=0,NNcalls=0,omitted=0,totalReady=0,globalCapStates=0,headCapStates=0;const featureCaps=Array(32).fill(0);
  const perHead=new Map();
  for(let i=0;i<raw.calls.length;i++){
   const a=raw.calls[i],d=r.decisions[i],s=d.public_state,action=a.action;need(a.time_ns===d.time_ns&&JSON.stringify(action)===JSON.stringify(d.action),'Event/action binding');
   if(action.kind==='WAIT')waited+=action.wait_ns;
   need(waited<=12e9,'Original global WAIT budget');if(a.common_coalescing)continue;
   need(a.fixed_ATC_prior_logit===0&&!a.future_actual_work_used&&!a.future_arrivals_used,'Pure NN public inputs, fixed prior zero');
   const visible=new Set([...s.queue,...s.owners].flatMap(q=>['CPU','GPU'].map(r=>q.request_id+'|'+r)));
   need(Object.keys(a.nominal_vectors).length===visible.size&&Object.keys(a.nominal_vectors).every(k=>visible.has(k)),'No future job in actor nominal bank');
   const head=[...s.queue].sort((a,b)=>a.scheduled_arrival_ns-b.scheduled_arrival_ns||a.ordinal-b.ordinal)[0],free=['CPU','GPU'].filter(r=>!s.owners.some(o=>o.route===r));
   if(s.wait_used_ns/1e9+.05>12)globalCapStates++;if((perHead.get(head.request_id)||0)+.05>1.5)headCapStates++;
   const occ=(q,route)=>a.nominal_vectors[q.request_id+'|'+route].reduce((a,b)=>a+b,0)/Math.max(c.minimum_speed,1/(1+c.strength*(route==='CPU'?c.cpu_slope:c.gpu_slope)*Math.max(0,s.sensor.temperature_c-c.onset_c)));
   let expanded=false;
   for(const dose of [.05,.2,.5]){
    const deadlineSafe=s.queue.every(q=>q.priority!=='U'||d.time_ns/1e9+dose+Math.min(occ(q,'CPU'),occ(q,'GPU'))<=q.deadline_ns/1e9);
    const capSafe=s.wait_used_ns/1e9+dose<=12&&(perHead.get(head.request_id)||0)+dose<=1.5;
    const present=a.actions.some(x=>x.kind==='WAIT'&&x.wait_ns===Math.round(dose*1e9));need(present===(capSafe&&(!row.guard_enabled||deadlineSafe)),'Exact configurable WAIT mask');
    if(!deadlineSafe&&present)expanded=true;
    if(action.kind==='WAIT'&&action.wait_ns===Math.round(dose*1e9)&&!deadlineSafe)unsafeChosen++;
   }
   if(expanded)expandedStates++;if(action.kind==='WAIT')perHead.set(head.request_id,(perHead.get(head.request_id)||0)+action.wait_ns/1e9);
   need(a.x.length===19&&a.x.every(x=>x.length===32&&x.every(Number.isFinite))&&a.mask.length===19&&a.mask[a.chosen],'Original neural ABI');
   const logits=T.logits(nets[row.neural_head].net,a.x,a.mask);let best=0;for(let j=1;j<19;j++)if(logits[j]>logits[best])best=j;need(best===a.chosen,'Independent NN argmax '+row.label+' '+a.time_ns);
   if(a.x.some((x,j)=>a.mask[j]&&x[11]===10))clipped++;
   for(let k=0;k<32;k++)if(a.x.some((x,j)=>a.mask[j]&&Math.abs(x[k])===10))featureCaps[k]++;
   const candidates=new Set(a.actions.filter(x=>x.kind==='DISPATCH').map(x=>x.request_id)).size;need(candidates<=8,'Original candidate cap');omitted+=s.queue.length-candidates;totalReady+=s.queue.length;
   NN++;NNcalls++;if(NN%64===0)await new Promise(resolve=>setTimeout(resolve,1));
  }
  need(waited===r.wait_used_ns,'Every WAIT counted');need(row.reward_audit.max_telescope_error<=1e-6,'Original penalty/reward telescope');
  const drain=W.integrate(r,785e9,c,H);for(const k of ['on_time','urgent_on_time','incomplete','response_missing'])need(drain[k]===row.metrics[k],'SLA denominator');close(drain.total_J_proxy,row.metrics.total_J_proxy,'Original energy');
  const latency=q.filter(j=>j.response_ns!=null&&j.response_ns<=785e9).map(j=>(j.response_ns-j.scheduled_arrival_ns)/1e9).sort((a,b)=>a-b);if(latency.length)close(latency[Math.ceil(.95*latency.length)-1],row.metrics.P95_completed_response_s,'P95',1e-12);
  const ref=old.rows.find(x=>x.case===row.case&&x.source==='ORIGINAL'&&x.policy==='RL'),last=q.every(j=>j.available_ns!==null)?Math.max(...q.map(j=>j.available_ns)):null;
  records.push({label:row.label,case:row.case,policy:row.policy,condition:row.condition,source:'GUARD_ABLATION',n:row.n,original:row.metrics,completion:last===null?null:W.integrate(r,last,c,H),common:W.integrate(r,ref.common.end_ns,c,H),same_work_common_eligible:last!==null&&last<=ref.common.end_ns,
   raw_path:op.output_dir+'/'+row.label+'.raw.json.gz',raw_sha256:row.raw_sha256,guard_enabled:row.guard_enabled,neural_head:row.neural_head});
  const rec=records.at(-1);for(const b of old.bounds.filter(b=>b.case===row.case))if(rec.completion&&row.metrics.response_missing===0&&row.metrics.incomplete===0&&Object.entries(b.targets).every(([k,v])=>row.metrics[k]>=v)&&(b.kind==='energy'||rec.same_work_common_eligible))need(b.lower<=(b.kind==='energy'?rec.completion.total_J_proxy:rec.common.mean_AP_c)+1e-5,'Same relaxation contains no-guard schedule');
  summaries.push({label:row.label,case:row.case,policy:row.policy,NN_calls:NNcalls,expanded_deadline_unsafe_WAIT_states:expandedStates,chosen_deadline_unsafe_WAIT:unsafeChosen,queue_feature_clipped_calls:clipped,all32_feature_cap_calls:featureCaps,omitted_ready_sum:omitted,total_ready_sum:totalReady,global_WAIT_cap_blocked_states:globalCapStates,head_WAIT_cap_blocked_states:headCapStates});
  compact.set(row.label,q.map(j=>({request_id:j.request_id,route:j.route,dispatch_ns:j.dispatch_ns,response_ns:j.response_ns,available_ns:j.available_ns})));
  console.log('AUDITED',row.label,'checks',checks,'NN',NN);
 }
 const differences=[];for(const cid of [...new Set(records.map(r=>r.case))])for(const [a,b] of [['GUARD_ON_NN','GUARD_OFF_NN'],['GUARD_ON_NN','GUARD_ON_ZERO'],['GUARD_OFF_NN','GUARD_OFF_ZERO'],['GUARD_ON_ZERO','GUARD_OFF_ZERO']]){
  const x=compact.get(cid+'_'+a),y=new Map(compact.get(cid+'_'+b).map(j=>[j.request_id,j]));differences.push({case:cid,a,b,requests:x.length,route_changed:x.filter(j=>j.route!==y.get(j.request_id).route).length,
   any_route_or_dispatch_changed:x.filter(j=>j.route!==y.get(j.request_id).route||j.dispatch_ns!==y.get(j.request_id).dispatch_ns).length});}
 need(res.rows.filter(r=>r.exact_original_checks>0).length===10,'All ten exact original-model/neural controls');
 save(path.join(out,'EVALUATION.json'),{rows:[...old.rows,...records],bounds:old.bounds,new_environment_START:0,all_previous112_preserved:true,removed_rows:0});
 save(path.join(out,'DIAGNOSIS.json'),{rows:summaries,differences,new_environment_START:0,new_training:0,deadline_weights_unchanged:[8,4,30]});
 save(path.join(out,'AUDIT.json'),{status:'PASS',checks,max_absolute_error:worst,independent_NN_frames:NN,new_environment_START:0,new_training:0,exact_original_controls:10,
  result_sha256:sha(path.join(out,'RESULT.json')),evaluation_sha256:sha(path.join(out,'EVALUATION.json')),diagnosis_sha256:sha(path.join(out,'DIAGNOSIS.json')),utc:new Date().toISOString()});
 console.log(JSON.stringify({status:'PASS',checks,NN,worst}));
}
main().catch(e=>{console.error(e.stack);process.exitCode=1;});
