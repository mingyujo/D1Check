'use strict';
// Independent arithmetic implementation. Does not import the Python policy.
const crypto = require('crypto');

function auditLSF(s, call, vectors, p, ok, near) {
  const mode = call.mode, owners = s.owners;
  const counts = Object.fromEntries(['CPU','GPU'].map(r=>[r, owners.filter(o=>o.route===r).length]));
  const free = ['CPU','GPU'].filter(r=>counts[r]<(r==='CPU'?3:1));
  const n = owners.filter(o=>o.route==='CPU' && o.stage===1).length;
  const speed = r=>Math.max(p.minimum_speed, 1/(1+p.strength*(r==='CPU'?p.cpu_slope:p.gpu_slope)*Math.max(0,s.sensor.temperature_c-p.onset_c)));
  const vec = (q,r)=>vectors[q.request_id+'|'+r];
  const tie = (id,r)=>crypto.createHash('sha256').update(id+'|'+r).digest('hex');
  const remaining = owners.map(o=>{
    const v=vec(o,o.route), rem=v.map((x,k)=>k<o.stage?0:k===o.stage?Math.max(0,x-o.public_progress_s):x);
    const rate=speed(o.route)/(o.route==='CPU'?1+.25*Math.max(0,n-Number(o.stage===1)):1);
    return {request_id:o.request_id,route:o.route,nominal_vector_s:v,remaining_work_s:rem,rate,
      remaining_occupancy_s:rem.reduce((a,b)=>a+b,0)-rem[1]+rem[1]/rate};
  });
  const releaseJobs={}, releases={};
  for(const r of ['CPU','GPU']) {
    releaseJobs[r]=free.includes(r)?null:remaining.filter(x=>x.route===r).sort((a,b)=>a.remaining_occupancy_s-b.remaining_occupancy_s||a.request_id.localeCompare(b.request_id))[0];
    releases[r]=releaseJobs[r]?.remaining_occupancy_s??0;
  }
  const jobs=[];
  for(const q of s.queue) {
    const opts=[];
    for(const r of ['CPU','GPU']) {
      if(mode==='LSF_DYN' && !free.includes(r)) continue;
      const v=vec(q,r);let others=n;
      if(r==='CPU' && !free.includes(r)) {
        const first=owners.find(o=>o.request_id===releaseJobs[r].request_id);
        others=Math.min(2,Math.max(0,n-Number(first.stage===1)));
      }
      const rate=speed(r)/(r==='CPU'?1+.25*others:1), boundary=q.task==='C'?2:3;
      const response=v.slice(0,boundary).reduce((a,b)=>a+b,0)-v[1]+v[1]/rate;
      const wait=mode==='LSF_DYN'?0:releases[r];
      opts.push({route:r,nominal_vector_s:v,rate,wait_s:wait,response_s:response,total_response_s:wait+response,tie_sha256:tie(q.request_id,r)});
    }
    if(!opts.length) continue;
    const best=opts.slice().sort((a,b)=>a.total_response_s-b.total_response_s||a.tie_sha256.localeCompare(b.tie_sha256))[0];
    jobs.push({request_id:q.request_id,slack_s:(q.deadline_ns-s.now_ns)/1e9-best.total_response_s,
      best_route:best.route,total_response_s:best.total_response_s,route_options:opts,q});
  }
  jobs.sort((a,b)=>a.slack_s-b.slack_s||a.q.scheduled_arrival_ns-b.q.scheduled_arrival_ns||a.q.ordinal-b.q.ordinal||a.request_id.localeCompare(b.request_id));
  let expected={kind:'RESOURCE_WAIT'};const skipped=[];
  if(free.length) for(const j of jobs) {
    if(mode==='BAND_LSF_DROP' && j.slack_s<0) {
      expected={kind:'DROP',request_id:j.request_id,reason:'PUBLIC_PREDICTED_SLO_VIOLATION'};break;
    }
    if(free.includes(j.best_route)) {
      expected={kind:'DISPATCH',request_id:j.request_id,route:j.best_route};break;
    }
    skipped.push(j.request_id);
  }
  ok(call.full_Band_runtime===false && call.future_information===false && call.new_NN_execution===false && call.rolling_horizon===false,'Declared request adaptation only');
  ok(call.time_ns===s.now_ns && JSON.stringify(call.free_routes)===JSON.stringify(free),'LSF time/free routes');
  for(const r of ['CPU','GPU']) near(call.release_estimates_s[r],releases[r],'Public worker release estimate',1e-12);
  ok(call.owner_estimates.length===remaining.length,'Owner count');
  for(let i=0;i<remaining.length;i++) {
    const a=call.owner_estimates[i],b=remaining[i];
    ok(a.request_id===b.request_id && a.route===b.route && JSON.stringify(a.nominal_vector_s)===JSON.stringify(b.nominal_vector_s),'Only visible owner nominal');
    for(let k=0;k<5;k++) near(a.remaining_work_s[k],b.remaining_work_s[k],'Observed public progress only',1e-12);
    near(a.rate,b.rate,'Owner rate',1e-12);near(a.remaining_occupancy_s,b.remaining_occupancy_s,'Owner remaining occupancy',1e-12);
  }
  ok(call.ranked_jobs.length===jobs.length,'All visible jobs ranked');
  for(let i=0;i<jobs.length;i++) {
    const a=call.ranked_jobs[i],b=jobs[i];
    ok(a.request_id===b.request_id && a.best_route===b.best_route,'Least slack priority');
    near(a.slack_s,b.slack_s,'Slack',1e-12);near(a.total_response_s,b.total_response_s,'Predicted response including worker wait',1e-12);
  }
  ok(call.action.kind===expected.kind && call.action.request_id===expected.request_id && call.action.route===expected.route && call.action.reason===expected.reason,'Independent LSF/Band adaptation action');
  ok(JSON.stringify(call.skipped_busy_best)===JSON.stringify(skipped),'Skipped busy plans');
  const options=jobs.find(j=>j.request_id===expected.request_id)?.route_options??[];
  ok(call.selected_options.length===options.length,'Selected public route option count');
  for(let i=0;i<options.length;i++) {
    const a=call.selected_options[i],b=options[i];
    ok(a.route===b.route && a.tie_sha256===b.tie_sha256 && JSON.stringify(a.nominal_vector_s)===JSON.stringify(b.nominal_vector_s),'Selected nominal route');
    for(const key of ['rate','wait_s','response_s','total_response_s']) near(a[key],b[key],'Selected prediction '+key,1e-12);
  }
  return expected;
}
module.exports={auditLSF};
