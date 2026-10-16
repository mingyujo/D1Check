// Saved-only posthoc diagnosis. No simulation, model fit, training or network.
const fs=require('fs'),path=require('path'),z=require('zlib'),crypto=require('crypto'),cp=require('child_process');
const root=path.resolve(__dirname,'../..'),out=path.join(root,'results/POLICY_GAP_REVIEW_20261016');
const read=p=>JSON.parse(fs.readFileSync(p,'utf8')),pin=p=>({path:path.relative(root,p).replaceAll('\\','/'),sha256:crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex'),bytes:fs.statSync(p).size});
const resultPath=path.join(root,'results/PROTECTED48_V2_20261016_01/RESULT.json'),terminal=read(path.join(path.dirname(resultPath),'COMPLETE.json'));
if(pin(resultPath).sha256!==terminal.result_sha256)throw Error('Completed result SHA differs');
if(fs.existsSync(out))throw Error('Review output already exists; no overwrite');
const d=read(resultPath),NEW='ROLLING_ATC_RL_PROTECTED48',EDF='EDF_CPU_FIRST';
const stats={actor_calls:0,both_resources_busy_calls:0,dispatch_calls:0,multiple_ready_dispatch:0,heterogeneous_task_dispatch:0,heterogeneous_deadline_dispatch:0,heterogeneous_priority_dispatch:0,FIFO_EDF_head_diff_on_RL_public_state:0,RL_EDF_head_diff_on_RL_public_state:0,voluntary_WAIT_legal_calls:0,voluntary_WAIT_selected:0,free_one_resource_dispatch:0,free_two_resources_dispatch:0,multiple_requests_after_mask:0,one_request_after_mask:0,removed_candidate_occurrences:0,critical_request_calls:0};
const tie=(a,b)=>a.scheduled_arrival_ns-b.scheduled_arrival_ns||a.ordinal-b.ordinal||a.request_id.localeCompare(b.request_id);
const conditionRows=[];let sameRoutes=0,sameResponse=0;
for(const c of d.fresh_cases){
 const r=c.rows.find(x=>x.policy===NEW),e=c.rows.find(x=>x.policy===EDF),map=new Map(e.gantt.map(x=>[x.request_id,x])),req=new Map(e.requests.map(x=>[x.request_id,x]));
 const traceSame=r.gantt.every(x=>JSON.stringify(x)===JSON.stringify(map.get(x.request_id)));
 conditionRows.push({index:c.index,label:c.label,pattern:c.label.includes('steady')?'steady':'burst',trace_exact_same:traceSame,AP_exact_same:JSON.stringify(r.AP)===JSON.stringify(e.AP),energy_same:Math.abs(c.metrics.find(x=>x.policy===NEW).total_J_proxy-c.metrics.find(x=>x.policy===EDF).total_J_proxy)<1e-8});
 sameRoutes+=r.requests.filter(q=>q.route===req.get(q.request_id).route).length;sameResponse+=r.requests.filter(q=>q.response_ns===req.get(q.request_id).response_ns).length;
 for(const b of r.protection_decisions){
  stats.actor_calls++;const s=b.public_state,q=s.queue,free=2-s.owners.length;
  if(!free)stats.both_resources_busy_calls++;
  stats.removed_candidate_occurrences+=b.protection.removed_actions;
  stats.critical_request_calls+=b.protection.critical_request!==null;
  if(b.mask.slice(72,75).some(Boolean))stats.voluntary_WAIT_legal_calls++;
  if(b.action.kind==='WAIT')stats.voluntary_WAIT_selected++;
  if(b.action.kind!=='DISPATCH')continue;
  stats.dispatch_calls++;stats[free===1?'free_one_resource_dispatch':'free_two_resources_dispatch']++;
  const ids=new Set(b.mask.slice(0,72).flatMap((v,i)=>v?[Math.floor(i/3)]:[]));
  if(ids.size>1)stats.multiple_requests_after_mask++;else if(ids.size===1)stats.one_request_after_mask++;
  const fifo=q.slice().sort(tie)[0],edf=q.slice().sort((a,b)=>a.deadline_ns-b.deadline_ns||tie(a,b))[0];
  stats.FIFO_EDF_head_diff_on_RL_public_state+=fifo.request_id!==edf.request_id;
  stats.RL_EDF_head_diff_on_RL_public_state+=b.action.request_id!==edf.request_id;
  if(q.length>1){stats.multiple_ready_dispatch++;stats.heterogeneous_task_dispatch+=new Set(q.map(x=>x.task)).size>1;stats.heterogeneous_deadline_dispatch+=new Set(q.map(x=>x.deadline_ns)).size>1;stats.heterogeneous_priority_dispatch+=new Set(q.map(x=>x.priority)).size>1;}
 }
}
const manifest=read(path.join(root,'data/CORE_MANIFEST.json')),spec=manifest.find(x=>x.name==='A24_measured35.json'),profilePath=path.join(root,spec.stored),profile=JSON.parse(z.gunzipSync(fs.readFileSync(profilePath)));
const x=profile.cost_anchor.energy_increment_w,a=x.classification_CPU,b=x.detection_CPU,c=x.classification_GPU,p=x['classification_GPU+detection_CPU'];
const powers={...x,detection_GPU:Math.max(0,c+b-a),'classification_CPU+detection_GPU':p,'classification_CPU+classification_GPU':Math.max(0,a+p-b),'detection_CPU+detection_GPU':Math.max(0,b+p-a)};
const discount=p-c-b;
function reconstruct(r){
 const [lo,hi]=r.diagnostics.common_work_window_s,times={classification_CPU:0,classification_GPU:0,detection_CPU:0,detection_GPU:0};
 for(const g of r.gantt)times[(g.task==='C'?'classification':'detection')+'_'+g.route]+=Math.max(0,Math.min(hi,g.end_s)-Math.max(lo,g.start_s));
 return Object.entries(times).reduce((s,[k,v])=>s+powers[k]*v,0)+discount*r.metrics.overlap_ns/1e9;
}
let maxDeltaError=0;
for(const cc of d.fresh_cases){const n=cc.rows.find(r=>r.policy===NEW),e=cc.rows.find(r=>r.policy===EDF),nm=cc.metrics.find(r=>r.policy===NEW),em=cc.metrics.find(r=>r.policy===EDF);maxDeltaError=Math.max(maxDeltaError,Math.abs((nm.increment_J_proxy-em.increment_J_proxy)-(reconstruct(n)-reconstruct(e))));}
if(maxDeltaError>1e-7)throw Error('Fixed observer reconstruction differs');
const edf=d.aggregate.fresh.find(x=>x.policy===EDF),windows=d.fresh_cases.map(c=>c.common_work_window_s[1]-c.common_work_window_s[0]);
const sources=['experiments/edf_cpu_first_20261016/policy.py','experiments/protected48_v2_20261016/protected_policy.py','src/policy_bridge_four_route.py','src/four_route_model.py','src/thermal_four_route.py','reference/model_integration/timing_model.py','src/bulk_design.cjs'].map(n=>pin(path.join(root,n)));
const review={schema:'A24-policy-gap-saved-review-v1',status:'COMPLETE_SAVED_ONLY_POSTHOC_REVIEW',source_head:cp.execFileSync('git',['rev-parse','HEAD'],{encoding:'utf8'}).trim(),source_pin:pin(__filename),input_pins:[pin(resultPath),pin(profilePath)],source_pins:sources,
 scope:{fresh_simulation_conditions:24,requests_per_policy:1152,posthoc_diagnosis:true,new_environments:0,new_fit:0,new_training:0,network:0,automation_changed:false},
 decision_stats:stats,identical_route_requests:sameRoutes,identical_response_time_requests:sameResponse,condition_comparisons:conditionRows,
 baseline:{power_W:profile.measured35.baseline_w,mean_J:edf.baseline_J_proxy,total_share_percent:100*edf.baseline_J_proxy/edf.total_J_proxy},
 work_windows_s:{min:Math.min(...windows),mean:windows.reduce((s,x)=>s+x,0)/windows.length,max:Math.max(...windows)},
 energy_observer:{powers_W:powers,shared_pair_discount_W:discount,delta_reconstruction_max_error_J:maxDeltaError,expression:'sum(solo route power * owner duration in common window) + shared_pair_discount_W * overlap_seconds',temperature_power_feedback:false},
 comparison_semantics:'Head differences apply alternative rules to RL observed states; not paired same-clock EDF trajectories. Busy RESOURCE_WAIT is not voluntary cooling WAIT. No causal effect/accuracy proof from counters.',
 measured_J:null,physical_goal_validated:false,utc:new Date().toISOString()};
fs.mkdirSync(out,{recursive:false});fs.writeFileSync(path.join(out,'REVIEW.json'),JSON.stringify(review,null,2)+'\n',{flag:'wx'});
console.log(JSON.stringify({status:review.status,stats,identical_conditions:conditionRows.filter(x=>x.trace_exact_same).length,observer_delta_error_J:maxDeltaError,source_head:review.source_head}));
