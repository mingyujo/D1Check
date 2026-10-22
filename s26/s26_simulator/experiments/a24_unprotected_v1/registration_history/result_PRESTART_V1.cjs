'use strict';
function summarize(sim){
 const rows=sim.requests.map(q=>{const o=sim.done.find(o=>o.ordinal===q.ordinal)||sim.owners.find(o=>o.ordinal===q.ordinal);return{ordinal:q.ordinal,task:q.task,priority:q.priority,arrival:q.arrival,deadline:q.deadline,route:o?.route??null,response:o?.response??null,available:o?.times.AVAILABLE??null,times:o?.times??null};});
 const service={};for(const pr of['all','urgent','normal']){const a=rows.filter(x=>pr==='all'||x.priority===pr),responded=a.filter(x=>Number.isFinite(x.response)),dt=responded.map(x=>x.response-x.arrival).sort((a,b)=>a-b);service[pr]={planned:a.length,completed:responded.length,on_time:responded.filter(x=>x.response<=x.deadline+1e-9).length,p95_s:dt[Math.ceil(.95*dt.length)-1]??null};}
 const completed=rows.filter(x=>x.available!==null),unfinished=rows.length-completed.length,curve=sim.curve2.concat([[sim.time,sim.temperature(),sim.physics.power()]]),max=Math.max(...curve.map(x=>x[1])),min=Math.min(...curve.map(x=>x[1]));
 return {schema:'S26_UNPROTECTED_CONDITIONAL_V1',service,unfinished,requests:rows,curve,integrals:sim.integrals,events:sim.events,physics_J:sim.physics.J,physics_H:sim.physics.H,
 observation_end_s:sim.time,actual_work_span_s:unfinished?null:Math.max(...completed.map(x=>x.available))-35,
 outside_marginal_AP:min<26||max>46.6,AP_peak_sampled:max,AP_mean:sim.integrals.reduce((s,x)=>s+x[3],0)/Math.max(1,sim.time-35),
 baseline_API_W:sim.physics.B0,api_energy:sim.integrals.reduce((s,x)=>s+x[2],0),baseline_API_J:sim.physics.B0*Math.max(0,sim.time-35),
 wait_s:sim.waitDose,adopted:false,physical_validation:false,policy_superiority_claim_allowed:false,
 limitations:'Frozen candidate power/thermal failed prior measured accuracy gate; this is exploratory conditional policy evidence, not certified S26 savings. No invented throttling, no temperature clip.'};
}
module.exports={summarize};
