'use strict';
const old=require('./rolling_action_v2.cjs'),cost=require('./state_cost.cjs');
const POLICIES=['FIFO_STATIC','EDF_STATIC','ATC_STATIC','FIFO_STATE','EDF_STATE','ATC_STATE'];
function select(obs,nom,models,policy,options={}){
 if(!POLICIES.includes(policy))throw Error('Unknown state study policy');
 const result=old.select(obs,nom,options);if(result.kind!=='DISPATCH')return result;
 const candidates=result.candidates,legal=candidates.filter(c=>c.permitted),ids=new Set(legal.map(c=>c.ordinal));let ordinal;
 if(policy.startsWith('ATC'))ordinal=result.ordinal;
 else ordinal=obs.ready.filter(q=>ids.has(q.ordinal)).sort((a,b)=>(policy.startsWith('EDF')?a.deadline-b.deadline:0)||a.arrival-b.arrival||a.ordinal-b.ordinal)[0].ordinal;
 const routes=legal.filter(c=>c.ordinal===ordinal),risk=routes.slice().sort((a,b)=>a.predicted_ready_misses-b.predicted_ready_misses||a.predicted_max_lateness_s-b.predicted_max_lateness_s)[0];
 const choices=routes.filter(c=>c.predicted_ready_misses===risk.predicted_ready_misses&&Math.abs(c.predicted_max_lateness_s-risk.predicted_max_lateness_s)<1e-12);
 const q=obs.ready.find(q=>q.ordinal===ordinal),stateful=policy.endsWith('STATE');
 if(stateful)for(const c of choices)c.state_forecast=cost.forecast(obs,nom,models,c.route,q.priority);
 const score=c=>stateful?c.state_forecast.normalized_energy_heat:c.normalized_energy_heat;
 const best=choices.slice().sort((a,b)=>score(a)-score(b)||a.response_estimate_s-b.response_estimate_s||a.route.localeCompare(b.route))[0];
 return {kind:'DISPATCH',ordinal,route:best.route,selected:best,candidates,method:policy,reason:'Shared actual mask/deadline risk; distinct ordering and static/state-conditioned allocation'};
}
module.exports={POLICIES,select};
