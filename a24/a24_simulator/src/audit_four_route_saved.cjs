'use strict';
// Independent saved arithmetic; does not run a policy, NN or physical model.
const fs=require('fs'),path=require('path'),crypto=require('crypto'),zlib=require('zlib');
const W=__dirname,O=path.resolve(W,'../../outputs',path.basename(W));
const out=process.argv[2];if(!out||fs.existsSync(out))throw Error('Fresh saved-audit namespace required');fs.mkdirSync(out,{recursive:true});
const read=p=>JSON.parse(fs.readFileSync(p,'utf8').replace(/^\uFEFF/,''));
const hash=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
let checks=0;const need=(x,m)=>{checks++;if(!x)throw Error(m);},close=(a,b,m,t=1e-8)=>need(Number.isFinite(a)&&Number.isFinite(b)&&Math.abs(a-b)<=t,m+': '+a+' / '+b);
try{
 const reg=read(path.join(O,'REGISTRATION.json')),ui=read(path.join(O,'UI_ACTUAL_01/RESULT.json')),suite=read(path.join(O,'suites',ui.actual_suite,'RESULT.json')),qa={cases:suite.cases.map(c=>c.batch_id)};
 fs.writeFileSync(path.join(out,'REGISTERED.json'),JSON.stringify({source_sha256:hash(__filename),registration_sha256:hash(path.join(O,'REGISTRATION.json')),qa_sha256:hash(path.join(O,'UI_ACTUAL_01/COMPLETE.json')),cases:qa.cases,new_environment:0,NN_inference:0,automatic_retry:false,utc:new Date().toISOString()})+'\n',{flag:'wx'});
 for(const p of [...reg.source_pins,...reg.input_pins,...reg.protected_HTML])need(hash(p.path)===p.sha256,'Source/input/HTML SHA '+p.path);
 const profile=read(path.join(O,'NUMERICAL_PREFLIGHT_02/FOUR_ROUTE_MODELS.json')).profile;
 const ledger=fs.readFileSync(path.join(O,'receipts.jsonl'),'utf8').trim().split(/\r?\n/).map(JSON.parse);
 const selected=ledger.filter(x=>qa.cases.includes(x.batch_id));
 for(const event of ['START','PREPARED','COMPLETE'])need(selected.filter(x=>x.event===event).length===14,event+' count');need(!selected.some(x=>x.event==='FAIL'),'No consumed FAIL hidden');
 const effects=[]; const derivation=require('./verify_four_route_derivation.cjs');derivation.verify({read,need,close,reg,O,path});
 for(const id of qa.cases){const dir=path.join(O,'batches',id),result=read(path.join(dir,'RESULT.json'));need(hash(path.join(dir,'RESULT.json'))===read(path.join(dir,'COMPLETE.json')).result_sha256,'Batch result seal');const base=result.rows.find(r=>r.policy==='FIFO_SERIAL_CG');
  for(const r of result.rows){const rawPath=path.join(dir,r.policy+'.json.gz'),done=read(path.join(dir,r.policy+'.COMPLETE.json'));need(hash(rawPath)===done.raw_sha256,'Raw SHA');const raw=JSON.parse(zlib.gunzipSync(fs.readFileSync(rawPath)));if(done.frames)need(hash(done.frames.path)===done.frames.sha256,'NN inputs SHA');
   derivation.verifyRaw({read,need,close,raw,r,O,path});const q=r.requests,completed=q.filter(x=>x.response_ns!==null&&x.response_ns<=210e9),ontime=completed.filter(x=>x.response_ns<=x.deadline_ns);need(q.length===r.metrics.planned&&q.length===result.input.requests.length,'Full denominator');need(completed.length===r.metrics.response_completed&&ontime.length===r.metrics.on_time,'Deadline counts');need(q.length-completed.length===r.metrics.response_missing,'Missing count');
   const lat=completed.map(x=>(x.response_ns-x.scheduled_arrival_ns)/1e9).sort((a,b)=>a-b);if(completed.length===q.length)close(lat[Math.ceil(.95*lat.length)-1],r.deadlines.P95_all_requested_response_s,'P95 nearest rank');
   for(const p of ['U','N']){const part=q.filter(x=>x.priority===p);need(part.length===r.by_priority[p].planned,'Priority denominator');need(part.filter(x=>x.response_ns!==null&&x.response_ns<=210e9&&x.response_ns<=x.deadline_ns).length===r.by_priority[p].on_time,'Priority ontime');}
   const points=r.AP.t_s.map((t,i)=>[t,r.AP.ap_c[i]]).filter(x=>x[0]>=35&&x[0]<=180);let area=0;for(let i=1;i<points.length;i++)area+=(points[i][0]-points[i-1][0])*(points[i][1]+points[i-1][1])/2;close(area/145,r.AP_mean_c,'AP trapezoid mean');close(Math.max(...points.map(x=>x[1])),r.AP_peak_c,'AP peak');close(points.at(-1)[1],r.AP_endpoint_c,'AP180');
   const marks=[...new Set([0,180,...r.gantt.flatMap(x=>[Math.max(0,Math.min(180,x.start_s)),Math.max(0,Math.min(180,x.end_s))])])].sort((a,b)=>a-b);let energy=profile.measured35.baseline_w*180;
   for(let i=1;i<marks.length;i++){const a=marks[i-1],b=marks[i],active=r.gantt.filter(x=>x.start_s<b&&x.end_s>a);need(active.length<=2&&new Set(active.map(x=>x.route)).size===active.length,'Nonpreemptive/max2 interval');if(active.length){let names=active.map(x=>(x.task==='C'?'classification':'detection')+'_'+x.route).sort();const state=names.join('+');need(state in profile.cost_anchor.energy_increment_w,'Supported cost state');energy+=(b-a)*profile.cost_anchor.energy_increment_w[state];}}
   close(energy,r.J_proxy,'Independent energy including baseline');need(r.measured_J===null&&r.energy_CI===null,'Measured energy remains unknown');
   const actualWait=raw.prediction.decisions.filter(d=>d.action.kind==='WAIT').reduce((a,d)=>a+Math.max(0,Math.min(d.action.wait_ns,180e9-d.time_ns)),0)/1e9;close(actualWait,r.wait_s,'Actual cutoff WAIT');
   if(r.policy.startsWith('ROLLING_ATC_RL'))need(r.actor_decisions>0&&done.audit.status==='PASS_SAVED_CLOCK_RESOURCE_NN_ARITHMETIC','NN inference audit present');
   effects.push({batch:id,requests:q.length,policy:r.policy,on_time:r.metrics.on_time,delta_on_time:r.metrics.on_time-base.metrics.on_time,AP_mean_C:r.AP_mean_c,delta_AP_mean_C:r.AP_mean_c-base.AP_mean_c,AP_peak_C:r.AP_peak_c,delta_peak_C:r.AP_peak_c-base.AP_peak_c,J_proxy:r.J_proxy,delta_J_proxy:r.J_proxy-base.J_proxy,wait_s:r.wait_s,actor_decisions:r.actor_decisions});
  }
 }
 const paused=fs.readFileSync('C:/Users/chomg/.codex/automations/a24/automation.toml','utf8');need(/^status\s*=\s*"PAUSED"/m.test(paused),'Automation PAUSED');
 fs.writeFileSync(path.join(out,'COMPLETE.json'),JSON.stringify({status:'PASS_INDEPENDENT_SAVED_INPUT_CLOCK_DEADLINE_AP_ENERGY_RESOURCE_ARITHMETIC',checks,cases:qa.cases,effects,source_pin_count:reg.source_pins.length,protected_original_HTML:reg.protected_HTML,START:14,COMPLETE:14,FAIL:0,environment_cap:reg.environment_cap,shared_parent_START:reg.parent_START,shared_total_START:reg.parent_START+14,remaining:reg.environment_cap-14,global_actual_plus_reserved:120774,global_cap:137712,automation:'PAUSED',new_environment:0,new_NN:0,physical_accuracy_verified:false},null,2)+'\n',{flag:'wx'});
}catch(e){fs.writeFileSync(path.join(out,'FAILURE.json'),JSON.stringify({checks,error:e.stack},null,2)+'\n',{flag:'wx'});throw e;}
