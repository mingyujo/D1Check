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
