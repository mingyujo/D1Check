'use strict';
// All fixed conditions/seeds/harms; no refitting, retraining or winner selection.
const fs=require('fs'),path=require('path'),z=require('zlib'),crypto=require('crypto');
const root=path.resolve(__dirname,'../..'),read=p=>JSON.parse(fs.readFileSync(p)),sha=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
const op=read(path.join(__dirname,'OPERATION.json')),out=path.join(root,op.output_dir),r=read(path.join(out,'RESULT.json'));
const audit=read(path.join(out,'AUDIT.json')),selection=read(path.join(out,'SELECTION_FROZEN.json'));
if(audit.result_sha256!==sha(path.join(out,'RESULT.json')))throw Error('Require audited exact result');
const fresh=r.rows.filter(r=>r.kind==='FRESH'),label=row=>row.policy==='RL'?'RL_S'+row.label.split('_S').at(-1):row.policy;
const groups=[...new Set(fresh.map(label))],avg=(v,f)=>v.reduce((s,x)=>s+f(x),0)/v.length,sum=(v,f)=>v.reduce((s,x)=>s+f(x),0);
function aggregate(v){return {conditions:v.length,planned:sum(v,r=>r.n),on_time:sum(v,r=>r.metrics.on_time),
 urgent_planned:sum(v,r=>r.metrics.urgent_planned),urgent_on_time:sum(v,r=>r.metrics.urgent_on_time),response_missing:sum(v,r=>r.metrics.response_missing),incomplete:sum(v,r=>r.metrics.incomplete),
 mean_total_J_proxy:avg(v,r=>r.metrics.total_J_proxy),mean_increment_J_proxy:avg(v,r=>r.metrics.increment_J_proxy),
 mean_full_tail_increment_J_proxy:avg(v,r=>r.metrics.full_tail_increment_J_proxy),mean_AP_c:avg(v,r=>r.metrics.mean_AP_c),
 mean_peak_AP_c:avg(v,r=>r.metrics.peak_AP_c),mean_throttled_execution_s:avg(v,r=>r.metrics.execution_throttled_s),
 mean_conditional_P95_s:avg(v,r=>r.metrics.P95_completed_response_s),mean_wait_s:avg(v,r=>r.metrics.wait_s),mean_objective:avg(v,r=>r.metrics.objective),
 route_counts:Object.fromEntries(['C_CPU','C_GPU','D_CPU','D_GPU'].map(k=>[k,sum(v,r=>r.metrics.route_counts[k])]))};}
const means=groups.map(policy=>({policy,...aggregate(fresh.filter(r=>label(r)===policy))}));
const byTemperature=groups.flatMap(policy=>[26,39].map(T=>({policy,initial_T:T,...aggregate(fresh.filter(r=>label(r)===policy&&r.condition.temperature_c===T))})));
function differences(aa,bb){
 const pairs=aa.map(a=>{const b=bb.find(b=>b.case===a.case);if(!b)throw Error('Unpaired comparison');return {case:a.case,condition:a.condition,
  total_J_proxy:a.metrics.total_J_proxy-b.metrics.total_J_proxy,increment_J_proxy:a.metrics.increment_J_proxy-b.metrics.increment_J_proxy,
  AP_c:a.metrics.mean_AP_c-b.metrics.mean_AP_c,peak_c:a.metrics.peak_AP_c-b.metrics.peak_AP_c,
  on_time:a.metrics.on_time-b.metrics.on_time,urgent_on_time:a.metrics.urgent_on_time-b.metrics.urgent_on_time,
  response_missing:a.metrics.response_missing-b.metrics.response_missing,objective:a.metrics.objective-b.metrics.objective};});
 return {pairs,conditions:pairs.length,mean_total_delta_J_proxy:avg(pairs,x=>x.total_J_proxy),mean_AP_delta_c:avg(pairs,x=>x.AP_c),
  total_on_time_delta:sum(pairs,x=>x.on_time),total_urgent_delta:sum(pairs,x=>x.urgent_on_time),
  energy_improved_conditions:pairs.filter(x=>x.total_J_proxy< -1e-8).length,AP_improved_conditions:pairs.filter(x=>x.AP_c< -1e-8).length,
  simultaneous_energy_AP_improvements:pairs.filter(x=>x.total_J_proxy< -1e-8&&x.AP_c< -1e-8).length,
  conditions_with_ontime_harm:pairs.filter(x=>x.on_time<0).length};
}
const bestSeed=selection.selected.seed,best='RL_S'+bestSeed;
const versusEDF=groups.filter(p=>p!=='EDF').map(policy=>({policy,...differences(fresh.filter(r=>label(r)===policy),fresh.filter(r=>r.policy==='EDF'))}));
const versusExact=op.learner_seeds.map(seed=>({seed,...differences(fresh.filter(r=>label(r)==='RL_S'+seed),fresh.filter(r=>r.policy==='EXACT'))}));
const raw=row=>JSON.parse(z.gunzipSync(fs.readFileSync(path.join(out,row.label+'.raw.json.gz'))));
const trajectories=[];
for(const seed of op.learner_seeds){
 const cases=[];let stateDifferent=0,informative=0,decisions=0,zeroDifferent=0;
 for(const a of fresh.filter(r=>label(r)==='RL_S'+seed)){
  const b=fresh.find(r=>r.case===a.case&&r.policy==='EXACT'),ar=raw(a),br=raw(b),bq=new Map(br.result.requests.map(q=>[q.request_id,q]));
  const dispatch=x=>x.result.decisions.filter(d=>d.action.kind==='DISPATCH').map(d=>[d.time_ns,d.action.request_id,d.action.route]);
  cases.push({case:a.case,dispatch_timeline_exact_same:JSON.stringify(dispatch(ar))===JSON.stringify(dispatch(br)),
   request_count:a.n,route_changed:ar.result.requests.filter(q=>q.route!==bq.get(q.request_id).route).length,
   dispatch_clock_changed:ar.result.requests.filter(q=>q.dispatch_ns!==bq.get(q.request_id).dispatch_ns).length,
   response_clock_changed:ar.result.requests.filter(q=>q.response_ns!==bq.get(q.request_id).response_ns).length});
  for(const c of ar.calls.filter(c=>!c.common_coalescing)){
   decisions++;if(c.mask.filter(Boolean).length<=1)continue;informative++;
   const legal=c.mask.flatMap((x,i)=>x?[i]:[]);const expected=legal.reduce((a,b)=>c.forecast_scores[b]<c.forecast_scores[a]?b:a);
   stateDifferent+=Number(expected!==c.chosen);zeroDifferent+=Number(c.chosen!==legal[0]);
  }
 }
 trajectories.push({seed,cases,conditions:cases.length,exact_same_conditions:cases.filter(c=>c.dispatch_timeline_exact_same).length,
  planned:sum(cases,c=>c.request_count),route_changed:sum(cases,c=>c.route_changed),dispatch_clock_changed:sum(cases,c=>c.dispatch_clock_changed),
  neural_decisions:decisions,informative_decisions:informative,same_state_differs_from_exact:stateDifferent,
  same_state_differs_from_zero_initial_NN:zeroDifferent,forced_common_coalescing_excluded:true});
}
const ablations=[];
for(const policy of ['EDF','EXACT','RL']){
 const reference=fresh.filter(r=>policy==='RL'?label(r)===best:r.policy===policy);
 ablations.push({kind:'FEEDBACK_OFF',policy,...differences(r.rows.filter(r=>r.kind==='FEEDBACK_OFF'&&r.policy===policy),reference)});
}
ablations.push({kind:'COST_MISMATCH',policy:'APPROX versus EXACT',...differences(r.rows.filter(r=>r.kind==='COST_MISMATCH'),fresh.filter(r=>r.policy==='EXACT'))});
for(const strength of [.5,1.5])ablations.push({kind:'STRENGTH',strength,policy:best,...differences(r.rows.filter(r=>r.kind==='STRENGTH'&&r.strength===strength),fresh.filter(r=>label(r)===best))});
const timestep=['EXACT','RL'].map(policy=>({policy,...differences(r.rows.filter(r=>r.kind==='TIMESTEP'&&r.policy===policy),fresh.filter(r=>policy==='RL'?label(r)===best:r.policy===policy))}));
const curves=op.learner_seeds.map(seed=>{
 const rows=r.rows.filter(r=>r.kind==='TRAIN'&&r.label.startsWith('TRAIN_S'+seed+'_'));
 const training=read(path.join(out,'TRAINING_S'+seed+'.json'));
 return {seed,episodes:training.episodes,updates:training.updates,Adam_steps:training.Adam_steps,
  first32:aggregate(rows.slice(0,32)),last32:aggregate(rows.slice(-32)),convergence_proven:false};
});
const spread={};
for(const key of ['mean_total_J_proxy','mean_increment_J_proxy','mean_AP_c','on_time']){
 const x=means.map(r=>r[key]);spread[key]={min:Math.min(...x),max:Math.max(...x),range:Math.max(...x)-Math.min(...x)};
 if(key.includes('J_proxy'))spread[key].range_percent_of_min=100*spread[key].range/spread[key].min;
}
const result={schema:'A24-coupled345-all-policy-analysis-v1',source_result_sha256:sha(path.join(out,'RESULT.json')),source_audit_sha256:sha(path.join(out,'AUDIT.json')),
 means,byTemperature,versusEDF,versusExact,trajectories,ablations,timestep,curves,spread,
 selection,selected_name:best,all_three_seeds_reported:true,physical_accuracy_verified:false,measured_J:null,
 old_model_numbers_are_not_directly_comparable:'new hypothetical RC/progress and common35-to-drain energy window',
 sensitivity_does_not_retrain:true,new_environment_START:0};
fs.writeFileSync(path.join(out,'ANALYSIS.json'),JSON.stringify(result,null,2)+'\n',{flag:'wx'});
console.log(JSON.stringify({means,spread,trajectories:trajectories.map(({cases,...x})=>x),ablations:ablations.map(({pairs,...x})=>x),timestep},null,2));
