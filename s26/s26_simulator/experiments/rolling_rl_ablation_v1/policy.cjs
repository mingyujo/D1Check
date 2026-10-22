'use strict';
// Same immutable candidate/rolling implementation for every selector.
const delegate=require('../route_group_learning_v1/policy.cjs');
function configure(options){
 delegate.configure({...options,choose:bank=>{
  const recent=delegate.contextStats().task_seen.slice(-64),mix=recent.length<16?.75:recent.filter(q=>q.task==='classification').length/recent.length;
  const s=options.balance.scales,u=Math.max(1/64,mix),n=Math.max(1/64,1-mix);
  const shared=bank.forecasts.map(f=>f.cost[0]/s[0]+f.cost[1]/s[1]+.98*f.cost[2]/u+.98*f.cost[3]/n+3*f.cost[4]);
  return options.choose({...bank,original_scores:bank.scores,scores:shared,public_recent_mix:mix,common_score_weights:[1,1,.98,.98,3]});
 }});
}
module.exports={...delegate,configure};
