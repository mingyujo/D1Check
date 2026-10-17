'use strict';
// Independent saved-only physical arithmetic, original WAIT mask, and boxed
// dual certificate evaluation. No Python, fitting, scheduling or LP solve.
const fs=require('fs'),path=require('path'),z=require('zlib'),crypto=require('crypto');
const root=path.resolve(__dirname,'../..'),read=p=>JSON.parse(String(p).endsWith('.gz')?z.gunzipSync(fs.readFileSync(p)):fs.readFileSync(p));
const sha=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
let checks=0,worst=0;const need=(v,s)=>{checks++;if(!v)throw Error(s);},close=(a,b,s,tol=4e-7)=>{worst=Math.max(worst,Math.abs(a-b));need(Math.abs(a-b)<=tol,s+' '+Math.abs(a-b));};
const save=(p,v)=>fs.writeFileSync(p,JSON.stringify(v,null,2)+'\n',{flag:'wx'}),W=require('../work_window_20261017/reaccount.cjs');
async function main(){
 const op=read(path.join(__dirname,'OPERATION.json')),out=path.join(root,op.output_dir),parent=path.join(root,op.parent_output),res=read(path.join(out,'RESULT.json')),bounds=read(path.join(out,'BOUNDS.json')),terminal=read(path.join(out,'COMPLETE.json')),c=op.physics;
 for(const p of [...op.sources,...op.input_pins])need(sha(p.path)===p.sha256,'Frozen source/input');
 need(terminal.result_sha256===sha(path.join(out,'RESULT.json'))&&terminal.bounds_sha256===sha(path.join(out,'BOUNDS.json')),'Native terminal binding');
 const receipts=fs.readFileSync(path.join(out,'receipts.jsonl'),'utf8').trim().split('\n').map(JSON.parse);
 need(receipts.filter(r=>r.event==='START').length===82&&receipts.filter(r=>r.event==='COMPLETE').length===82&&!receipts.some(r=>r.event==='FAIL'),'82 finite complete lifecycles');
 need(new Set(receipts.filter(r=>r.event==='START').map(r=>r.identity)).size===82,'Unique START identities');
 for(const p of res.banks)need(sha(path.join(out,p.file))===p.sha256,'Bank/nominal binding');
 const model=read(path.join(root,'results/STATE_COST_IDENTIFICATION_20261017_01/MODEL.json')),solo=Object.fromEntries(model.supported_states.map((s,i)=>[s,model.coefficients_W_proxy[i]]));
 const H=solo.classification_GPU+solo.detection_CPU-solo['classification_GPU+detection_CPU'];delete solo['classification_GPU+detection_CPU'];solo.detection_GPU=.6013808404579677;
 const refs=read(path.join(parent,'WORK_METRICS.json')).rows,records=[];let certs=0,waitChecks=0;
 for(const row of res.rows){
  const rawfile=path.join(out,row.label+'.raw.json.gz');need(sha(rawfile)===row.raw_sha256,'Native raw SHA');const raw=read(rawfile),r=raw.result,q=r.requests;
  const bank=new Map(read(path.join(out,row.case+'.BANK.json.gz')).jobs.map(j=>[j.request_id,j])),nominal=read(path.join(out,row.case+'.NOMINALS.json.gz'));
  need(q.length===row.n,'All arrivals');for(const key of Object.keys(c))close(r.config[key],c[key],'Same model',0);
  const lanes={},cursor={CPU:0,GPU:0},progress=new Map(q.map(x=>[x.request_id,[0,0,0,0,0]]));
  for(const route of ['CPU','GPU']){lanes[route]=q.filter(j=>j.route===route).sort((a,b)=>a.dispatch_ns-b.dispatch_ns);for(let i=1;i<lanes[route].length;i++)need(lanes[route][i-1].available_ns<=lanes[route][i].dispatch_ns,'Exclusive nonpreemptive lane');}
  let previous=35e9,T=r.initial_ap_c;
  for(const t of r.trace){
   need(t.start_ns===previous&&t.end_ns>previous,'Causal trace');previous=t.end_ns;const dt=(t.end_ns-t.start_ns)/1e9;close(dt,t.dt,'Interval',1e-12);close(T,t.state.temperature_c,'Continuous T');
   need(t.active.length<=2&&new Set(t.active.map(a=>a.route)).size===t.active.length,'Physical owners');
   need(Math.max(t.state.temperature_c,t.next_state.temperature_c)<=op.thermal_upper_c+1e-7,'Thermal invariant');
   let dyn=0;const leak=Math.exp(c.leakage_per_c*(t.state.temperature_c-c.reference_c));
   for(const a of t.active){
    const f=a.stage===1?Math.max(c.minimum_speed,1/(1+(a.route==='CPU'?c.cpu_slope:c.gpu_slope)*Math.max(0,t.state.temperature_c-c.onset_c))):1;
    close(f,t.speeds[a.route],'Speed',1e-12);dyn+=(solo[(a.task==='C'?'classification':'detection')+'_'+a.route]-H)*((1-c.leakage_fraction)*f**3+c.leakage_fraction*leak);
    const jobs=lanes[a.route];while(cursor[a.route]+1<jobs.length&&jobs[cursor[a.route]+1].dispatch_ns<=t.start_ns)cursor[a.route]++;
    const job=jobs[cursor[a.route]],stage=['execution_start_ns','output_ready_ns','persist_complete_ns','worker_release_ns','available_ns'].filter(k=>job[k]!=null&&job[k]<=t.start_ns).length;
    need(job.dispatch_ns<=t.start_ns&&job.task===a.task&&stage===a.stage,'Owner/phase binding');progress.get(job.request_id)[stage]+=dt*f;
   }
   close(dyn*dt,t.dynamic,'Independent dynamic integral');close(c.baseline*dt,t.baseline,'Baseline');
   const part=W.partial({...t,dynamic:dyn*dt},dt,c,H);close(part.increment,t.increment,'Increment');close(part.temperature_c,t.next_state.temperature_c,'RC');close(part.temperature_area,t.temperature_area,'Thermal area');T=part.temperature_c;
  }
  for(const job of q){
   const j=bank.get(job.request_id);need(j.queue_entry_ns===job.queue_entry_ns,'Original admission');
   if(job.dispatch_ns!=null){need(JSON.stringify(j.routes[job.route].stages_ns)===JSON.stringify(job.timing.stages_ns),'Immutable latent work');need(job.dispatch_ns>=job.queue_entry_ns,'Release before dispatch');}
   if(job.available_ns!=null)for(let k=0;k<5;k++)close(progress.get(job.request_id)[k],job.timing.stages_ns[k]/1e9,'Conserved work');
  }
  need(raw.calls.length===r.decisions.length,'Every actual actor call');let waited=0;const perHead=new Map();
  for(let i=0;i<r.decisions.length;i++){
   const d=r.decisions[i],a=d.action,s=d.public_state,call=raw.calls[i];need(call.time_ns===d.time_ns&&JSON.stringify(call.action)===JSON.stringify(a),'Action binding');
   if(a.kind==='WAIT'){
    waited+=a.wait_ns;need(waited<=12e9,'Original global WAIT cap');
    if(row.kind!=='P0'&&!call.common_coalescing){
     const head=[...s.queue].sort((a,b)=>a.scheduled_arrival_ns-b.scheduled_arrival_ns||a.ordinal-b.ordinal)[0],dose=a.wait_ns/1e9;
     perHead.set(head.request_id,(perHead.get(head.request_id)||0)+dose);need(perHead.get(head.request_id)<=1.5+1e-8,'Original per-head WAIT cap');
     for(const j of s.queue.filter(j=>j.priority==='U')){const occ=['CPU','GPU'].map(route=>{const v=nominal[j.request_id+'|'+route];need(Array.isArray(v),'Recorded public nominal WAIT vector');const f=Math.max(c.minimum_speed,1/(1+(route==='CPU'?c.cpu_slope:c.gpu_slope)*Math.max(0,s.sensor.temperature_c-c.onset_c)));return v.reduce((a,b)=>a+b,0)/f;});need(d.time_ns/1e9+dose+Math.min(...occ)<=j.deadline_ns/1e9+1e-8,'Original urgent WAIT mask');waitChecks++;}
    }
   }else need(a.kind==='DISPATCH','No unbudgeted idle action');
  }
  need(waited===r.wait_used_ns,'Every WAIT accounted');
  const drain=W.integrate(r,785e9,c,H);for(const k of ['on_time','urgent_on_time','response_missing','incomplete'])need(drain[k]===row.metrics[k],'SLA denominator '+k);close(drain.total_J_proxy,row.metrics.total_J_proxy,'Original accounting');
  const lat=q.filter(j=>j.response_ns!=null&&j.response_ns<=785e9).map(j=>(j.response_ns-j.scheduled_arrival_ns)/1e9).sort((a,b)=>a-b);if(lat.length)close(lat[Math.ceil(.95*lat.length)-1],row.metrics.P95_completed_response_s,'Independent P95',1e-12);
 if(row.kind==='WITNESS'||row.kind==='P0'){
   const b=refs.find(x=>x.case===row.case&&x.policy==='EDF'),last=q.every(j=>j.available_ns!==null)?Math.max(...q.map(j=>j.available_ns)):null,common=W.integrate(r,b.common.end_ns,c,H);
   records.push({label:row.label,case:row.case,condition:row.condition,policy:row.policy,source:row.kind,n:row.n,original:row.metrics,
     completion:last===null?null:W.integrate(r,last,c,H),common,same_work_common_eligible:last!==null&&last<=b.common.end_ns,
     raw_sha256:row.raw_sha256,raw_path:op.output_dir+'/'+row.label+'.raw.json.gz'});
  }
  console.log('AUDITED',row.label,'checks',checks);await new Promise(resolve=>setTimeout(resolve,1));
 }
 for(const b of bounds.rows){
  const file=path.join(out,b.certificate);need(sha(file)===b.certificate_sha256,'LP certificate binding');const cert=read(file),p=cert.problem,n=p.cost.length,residual=[...p.cost];let dual=0;
  for(const [rows,rhs,lambda,ineq] of [[p.equal_rows,p.equal_rhs,p.equal_dual,false],[p.inequality_rows,p.inequality_rhs,p.inequality_dual,true]]){
   need(rows.length===rhs.length&&rhs.length===lambda.length,'Certificate dimensions');
   for(let i=0;i<rows.length;i++){need(Number.isFinite(lambda[i])&&(!ineq||lambda[i]<=0),'Legal dual multiplier');dual+=rhs[i]*lambda[i];for(const [j,a] of rows[i])residual[j]-=a*lambda[i];}
  }
  for(let j=0;j<n;j++){need(Number.isFinite(p.lower[j])&&Number.isFinite(p.upper[j])&&p.upper[j]>=p.lower[j],'Finite certificate box');dual+=residual[j]*(residual[j]>=0?p.lower[j]:p.upper[j]);}
  close(dual,p.repaired_dual,'Independent boxed dual',2e-6);close(dual-p.numerical_margin+cert.constant_offset,b.lower,'Bound metadata',2e-6);need(p.numerical_margin>=1e-4,'Conservative numerical margin');certs++;
 }
 for(const r of refs)records.push({...r,source:'ORIGINAL',same_work_common_eligible:true,raw_path:op.parent_output+'/'+r.label+'.raw.json.gz'});
 save(path.join(out,'EVALUATION.json'),{rows:records,bounds:bounds.rows,new_environment_START:0,definitions:'Energy through own lastAVAILABLE; thermal at frozen original3policy common end, with full completion by that end. Offline witnesses, no online or global optimum claim.'});
 save(path.join(out,'AUDIT.json'),{status:'PASS',checks,max_absolute_error:worst,LP_certificates:certs,independent_WAIT_checks:waitChecks,
   utc:new Date().toISOString(),result_sha256:sha(path.join(out,'RESULT.json')),bounds_sha256:sha(path.join(out,'BOUNDS.json')),evaluation_sha256:sha(path.join(out,'EVALUATION.json')),new_environment_START:0,new_LP_solves:0});
 console.log(JSON.stringify({status:'PASS',checks,certificates:certs,worst}));
}
main().catch(e=>{console.error(e.stack);process.exitCode=1;});
