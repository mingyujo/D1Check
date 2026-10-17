// Independent saved arithmetic/physical/NN-link census; never runs an environment.
const fs=require('fs'),path=require('path'),zlib=require('zlib'),crypto=require('crypto');
const root=path.resolve(__dirname,'../..'),out=path.join(root,'results/RL_COST_20261017_01');
const read=p=>JSON.parse(fs.readFileSync(p,'utf8').replace(/^\uFEFF/,'')),sha=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
let checks=0;function need(x,s){checks++;if(!x)throw Error(s)}function close(a,b,s){need(Math.abs(a-b)<=1e-7*Math.max(1,Math.abs(a),Math.abs(b)),s+': '+a+' / '+b)}
const op=read(process.argv[2]);for(const p of op.pins)need(sha(p.path)===p.sha256&&fs.statSync(p.path).size===p.bytes,'registered pin');
const result=read(path.join(out,'RESULT.json')),terminal=read(path.join(out,'COMPLETE.json')),nn=read(path.join(out,'NN_AUDIT.json'));
need(terminal.result_sha256===sha(path.join(out,'RESULT.json')),'terminal SHA');need(nn.status.startsWith('PASS_EXACT'),'exact NN audit');
const design=read(path.join(__dirname,'INPUTS.json')),cost=read(path.join(root,'results/STATE_COST_IDENTIFICATION_20261017_01/MODEL.json'));
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

const rows=[],actor_summaries=[];
function caseFor(label){
 if(label.startsWith('TRAIN_'))return design.train[Number(label.slice(6))-1];
 if(label.startsWith('DEV_EDF_'))return design.dev[Number(label.slice(8))];
 if(label.startsWith('DEV_EP'))return design.dev[Number(label.split('_').at(-1))];
 if(label.startsWith('FRESH_'))return design.fresh_eval[Number(label.split('_')[1])];
 if(label.startsWith('HISTORICAL_'))return design.historical.find(c=>c.n===Number(label.slice(11)));
 if(label.startsWith('CONTROL_'))return design.fresh_eval[Number(label.slice(8))];
 throw Error('unknown input binding '+label);
}
try{
 const receipts=fs.readFileSync(path.join(out,'receipts.jsonl'),'utf8').trim().split(/\r?\n/).map(JSON.parse);
 const starts=receipts.filter(r=>r.event==='START'),completed=receipts.filter(r=>r.event==='COMPLETE');
 need(starts.length===223&&completed.length===223&&receipts.every(r=>r.event!=='FAIL'),'all223 environments terminal');
 need(new Set(starts.map(r=>r.identity)).size===223,'unique consumed identities');
 for(const end of completed){
  const file=path.join(out,end.label+'.json'),r=read(file),c=caseFor(end.label),rawfile=path.join(out,end.label+'.raw.json.gz');
  need(sha(file)===end.result_sha256&&sha(rawfile)===end.raw_sha256,'receipt output links');
  const raw=JSON.parse(zlib.gunzipSync(fs.readFileSync(rawfile)));auditArithmetic(c,r,raw);
  if(r.policy.startsWith('ROLLING_ATC_RL_COST')||r.policy==='ATC_COST_NO_NN'){
   const calls=JSON.parse(zlib.gunzipSync(fs.readFileSync(path.join(out,end.label+'.actor_calls.json.gz'))));
   const summary={label:end.label,calls:calls.length,multiple_legal_calls:0,critical_focus_calls:0,nominal_fallback_calls:0,removed_actions:0,dispatch:{},voluntary_WAIT_calls:0,voluntary_WAIT_s:0,resource_WAIT_calls:0};
   let dispatch=0;for(const call of calls){need(call.mask[call.chosen_index]===true,'actual mask selected');
    need(call.public_state.now_ns===call.time_ns&&call.public_state.queue.every(q=>q.queue_entry_ns<=call.time_ns),'causal public call');
    summary.multiple_legal_calls+=Number(call.mask.filter(Boolean).length>1);
    summary.critical_focus_calls+=Number(call.protection.critical_request!==null);
    summary.nominal_fallback_calls+=Number(call.protection.nominal_recovery_fallback);
    summary.removed_actions+=call.protection.removed_actions;
    if(call.action.kind==='DISPATCH'){dispatch++;const q=call.public_state.queue.find(q=>q.request_id===call.action.request_id);need(!!q,'Chosen request in public ready queue');const key=q.task+'_'+call.action.route;summary.dispatch[key]=(summary.dispatch[key]||0)+1;}
    if(call.action.kind==='WAIT'){summary.voluntary_WAIT_calls++;summary.voluntary_WAIT_s+=call.action.wait_ns/1e9;}
    if(call.action.kind==='RESOURCE_WAIT')summary.resource_WAIT_calls++;
   }
   need(dispatch===raw.prediction.decisions.filter(d=>d.action.kind==='DISPATCH').length,'actor/applied dispatch count');
   actor_summaries.push(summary);
  }
  rows.push({label:end.label,n:c.n,policy:r.policy,on_time:r.metrics.on_time,raw_sha256:sha(rawfile)});
 }
 const seal=read(path.join(out,'SELECTION_FROZEN.json'));
 need(seal.evaluation_outcomes_opened===0&&JSON.stringify(seal.selected)===JSON.stringify(result.selected),'DEV selection freeze');
 need(result.fresh.length===12&&result.historical.length===7&&result.controls.length===12,'all declared cohorts');
 const frozencp=seal.selected.checkpoint;need(sha(frozencp.path)===frozencp.sha256,'selected checkpoint exact');
 fs.writeFileSync(path.join(out,'SAVED_AUDIT.json'),JSON.stringify({status:'PASS',checks,new_outputs:rows.length,rows,actor_summaries,
   NN_AUDIT_sha256:sha(path.join(out,'NN_AUDIT.json')),result_sha256:sha(path.join(out,'RESULT.json')),new_environment:0,measured_J:null},null,2)+'\n',{flag:'wx'});
 console.log(JSON.stringify({status:'PASS',checks,outputs:rows.length}));
}catch(e){fs.writeFileSync(path.join(out,'SAVED_AUDIT_FAILURE.json'),JSON.stringify({error:String(e),checks}),{flag:'wx'});throw e}
