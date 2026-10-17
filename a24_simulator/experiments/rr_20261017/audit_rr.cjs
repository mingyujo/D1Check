// Saved-only independent cost/thermal/clock/resource and rule-decision audit.
const fs=require('fs'),path=require('path'),zlib=require('zlib'),crypto=require('crypto');
const root=path.resolve(__dirname,'../..'),out=path.join(root,'results/RR_20261017_01');
const read=p=>JSON.parse(fs.readFileSync(p,'utf8').replace(/^\uFEFF/,'')),sha=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
let checks=0;function need(x,s){checks++;if(!x)throw Error(s)}function close(a,b,s){need(Math.abs(a-b)<=1e-7*Math.max(1,Math.abs(a),Math.abs(b)),s+': '+a+' / '+b)}
const op=read(process.argv[2]);for(const p of op.pins)need(sha(p.path)===p.sha256 && fs.statSync(p.path).size===p.bytes,'Registered pin');
const terminal=read(path.join(out,'COMPLETE.json')),result=read(path.join(out,'RESULT.json'));need(terminal.result_sha256===sha(path.join(out,'RESULT.json')),'Terminal link');
need(result.new_START===7 && result.new_COMPLETE===7 && result.new_FAIL===0 && result.NN_execution===0,'Run counts/no NN');
const design=read(path.join(root,'experiments/rules_no_rl_20261017/INPUTS.json')),cost=read(path.join(root,'results/STATE_COST_IDENTIFICATION_20261017_01/MODEL.json'));
const states=cost.supported_states,beta=cost.coefficients_W_proxy,solo=Object.fromEntries(states.map((s,i)=>[s,beta[i]]));solo.detection_GPU=.6013808404579677;
function auditArithmetic(c,r,raw){
 const q=raw.prediction.requests,m=r.metrics;need(q.length===c.n,'All planned rows');
 const events=[];let on=0,urgent=0,missing=0,incomplete=0,late=0;const latencies=[];
  for(let i=0;i<q.length;i++){
   const v=q[i],input=c.input.requests[i];need(v.ordinal===i && v.request_id==='user-'+String(i).padStart(5,'0'),'request identity');
   need(v.task===input.profile[0] && v.priority===input.priority && v.scheduled_arrival_ns===Math.round(input.arrival_s*1e9) && v.deadline_ns===Math.round(input.deadline_s*1e9),'public input binding');
   need(v.response_ns===v[(v.task==='C'?'output_ready':'persist_complete')+'_ns'],'response boundary');
   if(v.response_ns==null)missing++;else {on+=v.response_ns<=v.deadline_ns;urgent+=v.priority==='U'&&v.response_ns<=v.deadline_ns;late+=Math.max(0,v.response_ns-v.deadline_ns)/1e9;latencies.push((v.response_ns-v.scheduled_arrival_ns)/1e9)}
   if(v.available_ns==null)incomplete++;
   if(v.dispatch_ns!=null){need(v.dispatch_ns>=v.queue_entry_ns && v.queue_entry_ns>=v.scheduled_arrival_ns,'queue clock');let last=v.dispatch_ns;
    for(const key of ['execution_start_ns','output_ready_ns','persist_complete_ns','worker_release_ns','lane_available_ns'])if(v[key]!=null){need(v[key]>=last,'phase order');last=v[key]}
    events.push({t:v.dispatch_ns/1e9,on:true,v},{t:(v.available_ns==null?c.observation_end_s:v.available_ns/1e9),on:false,v});
   }
  }
  for(const [a,b,s] of [[on,m.on_time,'ontime'],[urgent,m.urgent_on_time,'urgent'],[missing,m.response_missing,'missing'],[incomplete,m.incomplete,'incomplete']])need(a===b,s);
  latencies.sort((a,b)=>a-b);close(latencies[Math.ceil(.95*latencies.length)-1],m.P95_completed_response_s,'P95');close(late,m.tardiness_lower_bound_s,'tardiness');
  const active=new Map(),segments=[];let cursor=0,overlap=0;
  events.sort((a,b)=>a.t-b.t || Number(a.on)-Number(b.on));
  for(const e of events){if(e.t>cursor){const state=[...active.values()].map(x=>(x.task==='C'?'classification':'detection')+'_'+x.route).sort().join('+')||'idle';segments.push([cursor,e.t,state]);if(active.size===2)overlap+=e.t-cursor;cursor=e.t}
   if(e.on){need(!active.has(e.v.route),'lane free before dispatch');active.set(e.v.route,e.v)}else{need(active.get(e.v.route)?.request_id===e.v.request_id,'AVAILABLE actual owner');active.delete(e.v.route)}need(active.size<=2,'maximum2');
  }
  const end=Math.round(c.observation_end_s*1e9)/1e9;if(cursor<end)segments.push([cursor,end,'idle']);
  const lo=m.window_s[0],hi=m.window_s[1];let z=[0,0,0,0],increment=0,transfer=0;
  for(const [a,b,state] of segments){const edges=[a,...[lo,hi].filter(x=>x>a&&x<b),b].sort((x,y)=>x-y);
   for(let j=0;j<edges.length-1;j++){const x=edges[j],y=edges[j+1],dt=y-x,u=states.map(s=>Number(s===state)),k=-Math.expm1(-dt/cost.tau_s);
    const integ=z.map((old,i)=>u[i]*dt+(old-u[i])*cost.tau_s*k);z=z.map((old,i)=>u[i]+(old-u[i])*(1-k));
    if(x>=lo-1e-9&&y<=hi+1e-9){increment+=integ.reduce((s,v,i)=>s+v*beta[i],0);if(state!=='idle'&&!states.includes(state))transfer+=dt*state.split('+').reduce((s,p)=>s+solo[p],0)}
   }
  }
  const base=1.204399931712509*(hi-lo);close(base,m.baseline_J_proxy,'baseline');close(increment,m.supported_increment_J_proxy,'causal cost');close(transfer,m.transferred_increment_J_proxy,'unmeasured transfer');close(base+increment+transfer,m.total_J_proxy,'total');close(100*base/m.total_J_proxy,m.baseline_share_percent,'baseline share');close(overlap,m.overlap_s,'overlap');
  const t=raw.summary.AP.t_s,y=raw.summary.AP.ap_c;let area=0,peak=-Infinity;
  for(let i=0;i<t.length-1;i++){const a=Math.max(lo,t[i]),b=Math.min(hi,t[i+1]);if(a>=b)continue;const y0=y[i]+(y[i+1]-y[i])*(a-t[i])/(t[i+1]-t[i]),y1=y[i]+(y[i+1]-y[i])*(b-t[i])/(t[i+1]-t[i]);area+=(y0+y1)*(b-a)/2;peak=Math.max(peak,y0,y1)}
  close(area/(hi-lo),m.mean_AP_c,'AP mean');close(peak,m.peak_AP_c,'AP peak');

}
function order(a,b){for(let i=0;i<a.length;i++){if(a[i]<b[i])return -1;if(a[i]>b[i])return 1}return 0}
function auditPolicy(r,raw){
 const diag={dispatch:0,multiple_ready:0,two_free:0,selected_differs_from_EDF_head:0,planned_FIFO_vs_queue_entry_head:0,ATC_numeric_ties:0,maximum_ready:0};
 const trace=raw.prediction.rule_decision_audit||[];let atc=0,rr=0,turn='C';
 for(const d of raw.prediction.decisions){const s=d.public_state,a=d.action,q=s.queue,owners=s.owners,free=['CPU','GPU'].filter(route=>owners.every(o=>o.route!==route));
  need(a.kind==='DISPATCH','No voluntary WAIT rule');need(q.every(v=>v.queue_entry_ns<=d.time_ns),'No future ready member');need(free.includes(a.route),'Legal free resource');
  const edf=[...q].sort((x,y)=>order([x.deadline_ns,x.scheduled_arrival_ns,x.ordinal,x.request_id],[y.deadline_ns,y.scheduled_arrival_ns,y.ordinal,y.request_id]))[0];
  const fifo=[...q].sort((x,y)=>order([x.scheduled_arrival_ns,x.ordinal,x.request_id],[y.scheduled_arrival_ns,y.ordinal,y.request_id]))[0];
  const entry=[...q].sort((x,y)=>order([x.queue_entry_ns,x.ordinal,x.request_id],[y.queue_entry_ns,y.ordinal,y.request_id]))[0];
  diag.dispatch++;diag.multiple_ready+=q.length>1;diag.two_free+=free.length===2;diag.maximum_ready=Math.max(diag.maximum_ready,q.length);diag.selected_differs_from_EDF_head+=a.request_id!==edf.request_id;diag.planned_FIFO_vs_queue_entry_head+=fifo.request_id!==entry.request_id;
  if(r.policy==='EDF_CPU_FIRST'){need(a.request_id===edf.request_id && a.route===free[0],'EDF minimum deadline, CPU-first');continue}
  if(r.policy==='FIFO_CPU_FIRST'){need(a.request_id===fifo.request_id && a.route===free[0],'FIFO scheduled arrival, CPU-first');continue}
  if(r.policy==='RR_CPU_FIRST'){
   const preferred=q.filter(x=>x.task===turn),pool=preferred.length?preferred:q;
   const head=[...pool].sort((x,y)=>order([x.scheduled_arrival_ns,x.ordinal,x.request_id],[y.scheduled_arrival_ns,y.ordinal,y.request_id]))[0];
   const t=trace[rr++];need(t && t.time_ns===d.time_ns && t.turn_before===turn,'RR turn/time continuity');
   need(a.request_id===head.request_id && a.route===free[0],'RR next class, within-class FIFO, CPU-first');
   turn=head.task==='C'?'D':'C';need(t.turn_after===turn && t.selected_task===head.task && t.empty_class_skipped===!preferred.length,'RR transition/empty skip');
   continue;
  }
  const t=trace[atc++];need(t.time_ns===d.time_ns && t.action.request_id===a.request_id && t.action.route===a.route,'ATC trace/action link');
  need(t.nominal_calls.length===q.length*free.length,'Exact native query coverage');
  const valid=t.nominal_calls.filter(x=>x.status==='OK'),mean=valid.reduce((s,x)=>s+x.occupancy_ns,0)/valid.length,lookup=Object.fromEntries(q.map(x=>[x.request_id,x]));
  for(const x of valid){need(free.includes(x.route) && lookup[x.request_id] && x.occupancy_ns>0 && x.response_ns<=x.occupancy_ns,'Nominal public/route support');const v=lookup[x.request_id];x.score=Math.log((v.priority==='U'?2:1)/(x.occupancy_ns/1e9))-Math.max(v.deadline_ns-d.time_ns-x.response_ns,0)/(2*mean)}
  const best=Math.max(...valid.map(x=>x.score)),chosen=valid.find(x=>x.request_id===a.request_id && x.route===a.route);need(chosen && best-chosen.score<1e-11,'ATC maximum score numerical audit');diag.ATC_numeric_ties+=valid.filter(x=>Math.abs(x.score-best)<1e-11).length>1;
 }
 need(diag.dispatch===r.n,'All jobs dispatched');if(r.policy==='RR_CPU_FIRST')need(rr===trace.length,'All RR turns audited');if(r.policy==='ROLLING_ATC')need(atc===trace.length,'ATC whole trace');diag.deadline_by_task_priority=[];for(const task of ['C','D'])for(const priority of ['U','N']){const group=raw.prediction.requests.filter(q=>q.task===task && q.priority===priority);diag.deadline_by_task_priority.push({task,priority,planned:group.length,on_time:group.filter(q=>q.response_ns!==null&&q.response_ns<=q.deadline_ns).length,missing:group.filter(q=>q.response_ns===null).length})}return diag;
}
try{
 const audit=[];
 for(let i=0;i<result.cases.length;i++){const c=design.cases[i],stored=result.cases[i];need(c.n===stored.n && c.n<=3072,'Registered length');
  for(const r of stored.rows){const file=root+'/'+r.source_result_path,rawfile=path.join(path.dirname(file),r.label+'.raw.json.gz');need(sha(rawfile)===r.raw_sha256,'Raw byte SHA');const raw=JSON.parse(zlib.gunzipSync(fs.readFileSync(rawfile)));auditArithmetic(c,r,raw);audit.push({n:c.n,policy:r.policy,...auditPolicy(r,raw),raw_sha256:r.raw_sha256})}
  const windows=stored.rows.map(r=>JSON.stringify(r.metrics.window_s));need(new Set(windows).size===1,'Same policy windows');
 }
 const receipts=fs.readFileSync(path.join(out,'receipts.jsonl'),'utf8').trim().split(/\r?\n/).map(JSON.parse),counts=Object.fromEntries(['START','PREPARED','COMPLETE','FAIL'].map(e=>[e,receipts.filter(r=>r.event===e).length]));
 need(counts.START===7 && counts.COMPLETE===7 && counts.FAIL===0,'Every terminal ledger');
 fs.writeFileSync(path.join(out,'AUDIT.json'),JSON.stringify({status:'PASS',checks,rows:audit,counts,NN_execution:0,new_environment_START:0,operation_sha256:sha(process.argv[2]),result_sha256:sha(path.join(out,'RESULT.json'))},null,2)+'\n',{flag:'wx'});console.log(JSON.stringify({status:'PASS',checks,rows:audit.length,counts}));
}catch(e){fs.writeFileSync(path.join(out,'AUDIT_FAILURE.json'),JSON.stringify({error:String(e),checks}),{flag:'wx'});throw e}