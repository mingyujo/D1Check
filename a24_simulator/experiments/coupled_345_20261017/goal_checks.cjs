'use strict';
// Preserve original substantive goal, and separate rule spread from NN outliers.
const fs=require('fs'),path=require('path'),crypto=require('crypto');
const root=path.resolve(__dirname,'../..'),read=p=>JSON.parse(fs.readFileSync(p)),op=read(path.join(__dirname,'OPERATION.json'));
const out=path.join(root,op.output_dir),a=read(path.join(out,'ANALYSIS.json')),r=read(path.join(out,'RESULT.json'));
const policy=row=>row.policy==='RL'?'RL_S'+row.label.split('_S').at(-1):row.policy;
const fresh=r.rows.filter(row=>row.kind==='FRESH'),policies=[...new Set(fresh.map(policy))];
const targets={total_cost_reduction_fraction:.10,mean_AP_reduction_c:.5,on_time_harm:0,urgent_on_time_harm:0,response_missing_harm:0,incomplete_harm:0};
const rules=a.means.filter(x=>!x.policy.startsWith('RL')),neural=a.means.filter(x=>x.policy.startsWith('RL'));
function ranges(rows){const out={policies:rows.map(x=>x.policy)};for(const key of ['mean_total_J_proxy','mean_increment_J_proxy','mean_AP_c','on_time']){const q=rows.map(x=>x[key]);out[key]={min:Math.min(...q),max:Math.max(...q),range:Math.max(...q)-Math.min(...q)};if(key.includes('J_proxy'))out[key].range_percent_of_min=100*out[key].range/out[key].min;}return out;}
const goals=[];
for(const p of policies.filter(p=>p!=='EDF')){
 const cases=[];
 for(const row of fresh.filter(row=>policy(row)===p)){
  const b=fresh.find(b=>b.case===row.case&&b.policy==='EDF'),m=row.metrics,e=b.metrics;
  cases.push({case:row.case,total_reduction_percent:100*(1-m.total_J_proxy/e.total_J_proxy),AP_reduction_c:e.mean_AP_c-m.mean_AP_c,
   on_time_delta:m.on_time-e.on_time,urgent_delta:m.urgent_on_time-e.urgent_on_time,
   missing_delta:m.response_missing-e.response_missing,incomplete_delta:m.incomplete-e.incomplete,
   original_joint_goal_PASS:m.total_J_proxy<=.9*e.total_J_proxy&&m.mean_AP_c<=e.mean_AP_c-.5&&m.on_time>=e.on_time&&m.urgent_on_time>=e.urgent_on_time&&m.response_missing<=e.response_missing&&m.incomplete<=e.incomplete});
 }
 goals.push({policy:p,conditions:cases.length,original_joint_goal_pass_conditions:cases.filter(x=>x.original_joint_goal_PASS).length,cases});
}
const allCasePareto=[];
for(const p of policies)for(const q of policies)if(p!==q){
 const aa=fresh.filter(row=>policy(row)===p);let strict=false;
 const dominates=aa.every(row=>{const b=fresh.find(b=>b.case===row.case&&policy(b)===q),x=row.metrics,y=b.metrics;
  strict ||= x.total_J_proxy<y.total_J_proxy-1e-7||x.mean_AP_c<y.mean_AP_c-1e-7||x.on_time>y.on_time;
  return x.total_J_proxy<=y.total_J_proxy+1e-7&&x.mean_AP_c<=y.mean_AP_c+1e-7&&x.on_time>=y.on_time&&x.urgent_on_time>=y.urgent_on_time&&x.response_missing<=y.response_missing&&x.incomplete<=y.incomplete;
 });
 if(dominates&&strict)allCasePareto.push({a:p,b:q});
}
const value={schema:'A24-coupled345-original-goal-checks-v1',targets,all_policy_range:ranges(a.means),non_neural_range:ranges(rules),neural_seed_range:ranges(neural),
 goals,all_condition_Pareto_dominance:allCasePareto,posthoc_rule_winner_selected:false,physical_accuracy_verified:false,new_environment_START:0,
 source_result_sha256:crypto.createHash('sha256').update(fs.readFileSync(path.join(out,'RESULT.json'))).digest('hex')};
fs.writeFileSync(path.join(out,'GOAL_CHECKS.json'),JSON.stringify(value,null,2)+'\n',{flag:'wx'});
console.log(JSON.stringify({non_neural_range:value.non_neural_range,neural_seed_range:value.neural_seed_range,goals:goals.map(({cases,...x})=>x),allCasePareto},null,2));
