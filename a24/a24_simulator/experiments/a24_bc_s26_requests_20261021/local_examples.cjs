'use strict';
// Saved examples only; no engine or policy invocation.
const fs=require('fs'),path=require('path'),z=require('zlib');
const R=path.resolve(__dirname,'../../..'),O=path.join(R,'a24_simulator/results/A24_BC_S26_REQUESTS_20261021_01');
const read=p=>JSON.parse(p.endsWith('.gz')?z.gunzipSync(fs.readFileSync(p)):fs.readFileSync(p));
const result=read(path.join(O,'RESULT.json')),rows=[];
for(const row of result.rows.filter(x=>x.status==='COMPLETE'&&['BC_RECOVERED','TEACHER','EDF_DYN'].includes(x.policy))){
 const d=read(path.join(R,row.raw.path)),routes={};
 for(const q of d.result.requests){const key=q.task+'_'+q.priority+'_'+q.route;routes[key]=(routes[key]??0)+1;}
 const examples=[];
 if(row.policy==='BC_RECOVERED')for(let i=0;i<d.calls.length;i++){
  const c=d.calls[i],s=d.result.decisions[i].public_state,allowed=c.actions.map((_,k)=>k).filter(k=>c.mask[k]);
  const teacher=allowed.reduce((a,b)=>c.forecast_scores[b]<c.forecast_scores[a]?b:a),gap=c.forecast_scores[c.chosen]-c.forecast_scores[teacher];
  if(gap<=0)continue;
  const q=new Map(s.queue.map(x=>[x.request_id,x]));
  examples.push({decision_index:i,time_s:s.now_ns/1e9,temperature_C:s.sensor.temperature_c,owners:s.owners.length,queue_size:s.queue.length,
    score_regret:gap,BC:c.action,teacher:c.actions[teacher],BC_request:q.get(c.action.request_id)??null,teacher_request:q.get(c.actions[teacher].request_id)??null,
    BC_cost:c.forecasts[c.chosen].cost,teacher_cost:c.forecasts[teacher].cost,forecast_horizon_reduced:c.forecasts[0].horizon_reduced});
 }
 examples.sort((a,b)=>b.score_regret-a.score_regret);
 rows.push({label:row.label,rate:row.condition.requests_per_second,pattern:row.condition.pattern,policy:row.policy,route_by_task_priority:routes,largest3_local_disagreements:examples.slice(0,3)});
}
fs.writeFileSync(path.join(O,'LOCAL_DISAGREEMENTS.json'),JSON.stringify({status:'PASS',rows,scope:'Descriptive saved-state examples; no causal intervention',new_environment:0,new_fit:0},null,2)+'\n',{flag:'wx'});
console.log('SAVED_LOCAL_EXAMPLES',rows.length);
