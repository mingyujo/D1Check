'use strict';
const fs=require('fs'),path=require('path'),z=require('zlib'),vm=require('vm'),crypto=require('crypto');
const R=path.resolve(__dirname,'../../..'),A=path.join(R,'a24_simulator'),O=path.join(A,'results/A24_S26_MATCHED_BC_20261022_01'),H=path.join(A,'experiments/a24_s26_matched_bc_20261022');
const read=p=>JSON.parse(p.endsWith('.gz')?z.gunzipSync(fs.readFileSync(p)):fs.readFileSync(p));const sha=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
const {step,integral}=require(path.join(A,'experiments/a24_s26_method_20261019/audit.cjs'));let checks=0,maxerr=0,phaseChecks=0,policyChecks=0;
function ok(x,m){checks++;if(!x)throw Error(m);}
function near(a,b,m,tol=3e-7){maxerr=Math.max(maxerr,Math.abs(a-b));ok(Number.isFinite(a)&&Number.isFinite(b)&&Math.abs(a-b)<=tol,m+': '+a+' / '+b);}
const riskModel={task_margin_s:{C:0,D:0}};
const oldAuditPath=path.join(A,'experiments/a24_nn_urgent_tie_20261021/audit.cjs'),src=fs.readFileSync(oldAuditPath,'utf8'),sandbox={ok,near,riskModel,regressionChoices:0};vm.createContext(sandbox);let bankCode=src.slice(src.indexOf('function dominance'),src.indexOf('const result=read'));
bankCode=bankCode.replace(" const riskBest=allowed.map","\n let riskAllowed=allowed,guardGate=idle.slice();\n if(c.deadline_wait_guard){\n  const lookupQ=new Map(s.queue.map(q=>[q.request_id,q])),slack={},fastest={};\n  for(let i=0;i<c.actions.length;i++){\n   const a=c.actions[i];if(!idle[i]||a.kind!=='DISPATCH')continue;const q=lookupQ.get(a.request_id);if(q.priority!=='U')continue;\n   const f=c.forecasts[i],end=f.responses_s[q.request_id]??f.H_s,v=q.deadline_ns/1e9-end-riskModel.task_margin_s[q.task];\n   if(slack[q.request_id]===undefined||v>slack[q.request_id]){slack[q.request_id]=v;fastest[q.request_id]=i;}\n  }\n  const blocked=[],reasons=[];\n  for(let i=0;i<c.actions.length;i++){\n   const a=c.actions[i];if(!idle[i]||a.kind==='DISPATCH')continue;const w=(a.wait_ns??a.max_wait_ns??0)/1e9,critical=Object.keys(slack).filter(id=>slack[id]<=w+config.tick_s+1e-8);\n   if(critical.length){guardGate[i]=false;blocked.push(i);reasons.push({index:i,wait_bound_s:w,critical_ready_urgent_ids:critical});}\n  }\n  ok(JSON.stringify(blocked)===JSON.stringify(c.deadline_wait_guard.blocked_wait_indices),'Independent deadline WAIT exclusions');\n  ok(JSON.stringify(guardGate)===JSON.stringify(c.guard_mask),'Guard physical mask');\n  ok(JSON.stringify(fastest)===JSON.stringify(c.deadline_wait_guard.fastest_dispatch_indices),'Fastest public dispatch candidate');\n  for(const [id,v] of Object.entries(slack))near(v,c.deadline_wait_guard.urgent_slack_s[id],'Public urgent latest-start slack',1e-10);\n  ok(JSON.stringify(reasons)===JSON.stringify(c.deadline_wait_guard.reasons),'WAIT bounds and causal critical IDs');\n  near(c.deadline_wait_guard.tick_s,config.tick_s,'Guard tick',1e-12);ok(c.deadline_wait_guard.future_information===false,'No future guard input');\n  riskAllowed=c.actions.map((_,i)=>i).filter(i=>guardGate[i]);ok(riskAllowed.length>0,'Guard retains action');\n }\n"+" const riskBest=riskAllowed.map");
bankCode=bankCode.replace("mask=idle.map((v,i)=>!!v&&i<riskPairs.length", "mask=guardGate.map((v,i)=>!!v&&i<riskPairs.length");
vm.runInContext(bankCode+';globalThis.checkBank=auditBank;',sandbox);
const result=read(path.join(O,'RESULT.json')),derived=[];
for(const row of result.rows){
 if(row.status!=='COMPLETE')continue;
 const file=path.join(R,row.raw.path);ok(sha(file)===row.raw.sha256,'Raw fingerprint');const d=read(file),r=d.result,bank=read(path.join(R,row.bank.path)),jobs=new Map(bank.jobs.map(q=>[q.request_id,q])),work=new Map;let previous=null;
 ok(r.requests.length===d.case.n,'All arrivals');near(r.trace[0].start_ns/1e9,35,'Trace origin');near(r.trace.at(-1).end_ns/1e9,d.case.observation_end_s,'Fixed observation end',1e-9);
 for(const t of r.trace){
  ok(t.end_ns>t.start_ns,'Clock increases');if(previous)ok(t.start_ns===previous.end_ns,'Contiguous trace');previous=t;near(t.dt,(t.end_ns-t.start_ns)/1e9,'dt',1e-12);ok(t.active.filter(q=>q.route==='CPU').length<=3&&t.active.filter(q=>q.route==='GPU').length<=1,'Capacity');const x=step(t.state,t.active,t.dt,r.config,'ORIGINAL');near(x.state.temperature_c,t.next_state.temperature_c,'T');near(x.state.shared_z,t.next_state.shared_z,'Shared tail');near(x.J,t.increment,'Energy');near(x.H,t.temperature_area,'Thermal area');phaseChecks+=4;
  for(const q of t.active){near(x.rates[q.request_id],t.speeds[q.request_id],'Rate',1e-12);const k=q.request_id+'|'+q.stage;work.set(k,(work.get(k)||0)+t.dt*x.rates[q.request_id]);}
 }
 for(const q of r.requests){
  const j=jobs.get(q.request_id);ok(q.queue_entry_ns===j.queue_entry_ns&&q.scheduled_arrival_ns===j.scheduled_arrival_ns&&q.deadline_ns===j.deadline_ns,'Frozen input');ok(q.priority===(q.task==='C'?'U':'N')&&q.deadline_ns-q.scheduled_arrival_ns===(q.task==='C'?800000000:2000000000),'S26 request/deadline criteria');
  if(q.route)ok(JSON.stringify(q.timing.stages_ns)===JSON.stringify(j.routes[q.route].stages_ns),'SERIAL latent vector');
  if(q.available_ns!==null){for(let k=0;k<5;k++)near(work.get(q.request_id+'|'+k)||0,q.timing.stages_ns[k]/1e9,'Phase work conserved',8e-9);ok(q.response_ns===(q.task==='C'?q.output_ready_ns:q.persist_complete_ns),'Response boundary');}
 }
 ok(d.calls.length===r.decisions.length,'Decision binding');
 for(let i=0;i<d.calls.length;i++){
  const c=d.calls[i],s=r.decisions[i].public_state;ok(JSON.stringify(c.action)===JSON.stringify(r.decisions[i].action),'Chosen action binding');ok(s.queue.every(q=>q.queue_entry_ns<=s.now_ns),'Causal queue');
  if(c.forecasts){sandbox.riskModel={task_margin_s:d.risk};sandbox.checkBank(s,c,bank,r.config,null,row.policy.startsWith('TEACHER')?'TEACHER_RISK':row.policy);policyChecks++;}
  else{
   const tie=(a,b)=>a.scheduled_arrival_ns-b.scheduled_arrival_ns||a.ordinal-b.ordinal||a.request_id.localeCompare(b.request_id);let q;
   if(row.policy==='RR_DYN'){
    const task=c.turn_before,group=s.queue.filter(q=>q.task===task);q=(group.length?group:s.queue).slice().sort(tie)[0];ok(c.turn_after===(q.task==='C'?'D':'C'),'RR rotation');
   }else q=s.queue.slice().sort((a,b)=>(row.policy==='EDF_DYN'?a.deadline_ns-b.deadline_ns:0)||tie(a,b))[0];
   ok(q.request_id===c.action.request_id,'Baseline request order');const estimates=c.estimates.map(e=>{const v=bank.nominal_vectors[q.request_id+'|'+e.route],f=Math.max(r.config.minimum_speed,1/(1+r.config.strength*(e.route==='CPU'?r.config.cpu_slope:r.config.gpu_slope)*Math.max(0,s.sensor.temperature_c-r.config.onset_c))),cpu=s.owners.filter(q=>q.route==='CPU'&&q.stage===1).length,rate=f/(e.route==='CPU'?1+.25*cpu:1),stop=q.task==='C'?2:3,answer=v.slice(0,stop).reduce((a,b)=>a+b,0)-v[1]+v[1]/rate;near(answer,e.response_after_dispatch_s,'Baseline estimate',1e-10);return {route:e.route,value:answer,tie:e.tie_sha256};});estimates.sort((a,b)=>a.value-b.value||a.tie.localeCompare(b.tie));ok(c.action.route===estimates[0].route,'Baseline shortest public response');
  }
 }
 const svc={};
 for(const cls of ['ALL','U','N']){
  const qq=r.requests.filter(q=>cls==='ALL'||q.priority===cls),ans=qq.filter(q=>q.response_ns!==null&&q.response_ns<=Math.round(d.case.observation_end_s*1e9)),lat=ans.map(q=>(q.response_ns-q.scheduled_arrival_ns)/1e9).sort((a,b)=>a-b);svc[cls]={n:qq.length,on:ans.filter(q=>q.response_ns<=q.deadline_ns).length,missing:qq.length-ans.length,incomplete:qq.filter(q=>q.available_ns===null||q.available_ns>Math.round(d.case.observation_end_s*1e9)).length,P95:lat.length?lat[Math.ceil(.95*lat.length)-1]:null};for(const k of ['n','on','missing','incomplete'])ok(svc[cls][k]===row.metrics.service[cls][k],'Service count '+k);near(svc[cls].P95,row.metrics.service[cls].P95,'Session P95',1e-12);
 }
 const end=Math.round(d.case.observation_end_s*1e9),account=integral(r,'ORIGINAL',end),pre=35*r.config.baseline;near(account.J+pre,row.metrics.J,'Energy 0 to fixed end',1e-6);near(account.AP,row.metrics.AP,'AP 35 to fixed end',1e-9);
 const supply=integral(r,'ORIGINAL',Math.round(d.case.supply_stop_s*1e9)),completed=r.requests.every(q=>q.available_ns!==null),finish=completed?Math.max(Math.round(d.case.supply_stop_s*1e9),...r.requests.map(q=>q.available_ns)):null,done=finish===null?null:integral(r,'ORIGINAL',finish);derived.push({label:row.label,J:account.J+pre,AP:account.AP,service:svc,supply_J:supply.J+pre,supply_AP:supply.AP,finish_ns:finish,own_completion_J:done?done.J+pre:null,trace_length:r.trace.length});
 console.log('AUDITED',row.label);
}
const events=fs.readFileSync(path.join(O,'receipts.jsonl'),'utf8').trim().split('\n').map(JSON.parse),starts=events.filter(r=>r.event==='START');ok(starts.length<=105&&starts.length===result.counts.START,'Budget');ok(new Set(starts.map(s=>s.start_id)).size===starts.length,'Unique science identities');for(const s of starts)ok(events.filter(r=>r.start_id===s.start_id&&['COMPLETE','FAIL'].includes(r.event)).length===1,'One terminal record per START');

const calibration=read(path.join(O,'RISK_CALIBRATION.json')),rv={C:[],D:[]};let ci=0;
for(const row of result.rows.filter(r=>r.kind==='TRAIN_CAL')){
 const d=read(path.join(R,row.raw.path)),qs=new Map(d.result.requests.map(q=>[q.request_id,q]));
 for(const c of d.calls){if(c.action.kind!=='DISPATCH')continue;const q=qs.get(c.action.request_id),p=c.forecasts[c.chosen].responses_s[q.request_id];if(q.response_ns===null||p===undefined)continue;
  const residual=q.response_ns/1e9-p,v=calibration.samples[ci++];ok(v.split==='TRAIN'&&v.case===row.case&&v.request_id===q.request_id&&v.raw_sha256===row.raw.sha256,'Calibration TRAIN binding');near(v.residual_s,residual,'TRAIN residual',1e-12);rv[q.task].push(residual);
 }
}
ok(ci===calibration.samples.length,'All calibration samples');for(const task of ['C','D']){rv[task].sort((a,b)=>a-b);ok(rv[task].length>=20,'Q90 minimum');near(calibration.task_margin_s[task],Math.max(0,rv[task][Math.ceil(.9*rv[task].length)-1]),'TRAIN q90',1e-12);}
const freeze=read(path.join(O,'FREEZE.json')),firstEval=Math.min(...events.filter(e=>e.event==='START'&&e.kind==='EVAL').map(e=>e.unix));ok(freeze.unix<firstEval&&freeze.fit_stage===2&&freeze.no_EVAL_selection,'Frozen stage2 before EVAL');

fs.writeFileSync(path.join(O,'AUDIT_JS.json'),JSON.stringify({status:'PASS',checks,max_abs_error:maxerr,independent_physics_checks:phaseChecks,policy_decisions:policyChecks,teacher_verifier_sha256:sha(oldAuditPath),script_sha256:sha(__filename),derived,new_environments:0,new_fits:0}),{flag:'wx'});console.log('AUDIT_JS_PASS',checks,maxerr);
