'use strict';
// Dispatch choices exclude WAIT; includes a proof of the zero-NN EDF control.
const fs=require('fs'),path=require('path'),z=require('zlib'),crypto=require('crypto');
const root=path.resolve(__dirname,'../..'),read=p=>JSON.parse(fs.readFileSync(p)),sha=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
const op=read(path.join(__dirname,'OPERATION.json')),out=path.join(root,op.output_dir),result=read(path.join(out,'RESULT.json')),audit=read(path.join(out,'AUDIT.json'));
if(audit.result_sha256!==sha(path.join(out,'RESULT.json')))throw Error('Requires audited bytes');
const rows=[];let checks=0;
const equal=(a,b)=>JSON.stringify(a)===JSON.stringify(b);
for(const row of result.rows.filter(r=>r.kind==='FRESH')){
 const raw=JSON.parse(z.gunzipSync(fs.readFileSync(path.join(out,row.label+'.raw.json.gz'))));
 const v={label:row.label,case:row.case,policy:row.policy,dispatch:0,multiple_physical_ready_requests:0,
  multiple_candidate_requests:0,two_free_routes:0,joint_multiple_request_and_both_free:0,
  voluntary_WAIT_calls:0,common_coalescing_calls:0,cap_removed_ready_count:0,zero_NN_is_EDF_proof_calls:0};
 for(const [j,c] of raw.calls.entries()){
  const d=raw.result.decisions[j],s=d.public_state;
  if(c.common_coalescing){v.common_coalescing_calls++;continue;}
  const dispatch=c.actions.filter(a=>a.kind==='DISPATCH'),requests=new Set(dispatch.map(a=>a.request_id)),routes=new Set(dispatch.map(a=>a.route));
  const edf=[...s.queue].sort((a,b)=>a.deadline_ns-b.deadline_ns||a.scheduled_arrival_ns-b.scheduled_arrival_ns||a.ordinal-b.ordinal||a.request_id.localeCompare(b.request_id))[0];
  const free=['CPU','GPU'].filter(r=>!s.owners.some(o=>o.route===r));
  const expected={kind:'DISPATCH',request_id:edf.request_id,route:free[0]};
  if(!equal(c.actions[0],expected))throw Error('Canonical initial NN/EDF proof');checks++;v.zero_NN_is_EDF_proof_calls++;
  if(row.policy==='EDF'&&!equal(c.action,expected))throw Error('EDF action differs from zero-logit initial NN');
  if(c.action.kind==='WAIT'){v.voluntary_WAIT_calls++;continue;}
  v.dispatch++;v.multiple_physical_ready_requests+=Number(s.queue.length>1);v.multiple_candidate_requests+=Number(requests.size>1);
  v.two_free_routes+=Number(routes.size===2);v.joint_multiple_request_and_both_free+=Number(routes.size===2&&requests.size>1);
  v.cap_removed_ready_count+=s.queue.length-requests.size;
 }
 if(v.dispatch!==row.n-row.metrics.response_missing&&v.dispatch>row.n)throw Error('Dispatch denominator');
 rows.push(v);
}
const policy=r=>r.policy==='RL'?'RL_S'+r.label.split('_S').at(-1):r.policy;
const groups=[...new Set(rows.map(policy))].map(p=>{
 const v=rows.filter(r=>policy(r)===p),sum=k=>v.reduce((s,r)=>s+r[k],0),n=sum('dispatch');
 return {policy:p,conditions:v.length,dispatch:n,multiple_physical_ready_percent:100*sum('multiple_physical_ready_requests')/n,
  multiple_candidate_request_percent:100*sum('multiple_candidate_requests')/n,two_free_route_percent:100*sum('two_free_routes')/n,
  joint_choice_percent:100*sum('joint_multiple_request_and_both_free')/n,WAIT_chosen:sum('voluntary_WAIT_calls'),
  common_coalescing_calls:sum('common_coalescing_calls'),cap_removed_ready_count:sum('cap_removed_ready_count')};
});
const value={schema:'A24-coupled345-dispatch-choice-diagnostics-v1',checks,groups,rows,
 WAIT_excluded_from_multiple_request_and_dispatch_denominators:true,
 initial_zero_logit_NN_equals_EDF_with_common_coalescing:true,
 scope:'finite saved public states plus zero-actor-output architecture; not a trained-NN superiority test',new_environment_START:0};
fs.writeFileSync(path.join(out,'CHOICE_DIAGNOSTICS.json'),JSON.stringify(value,null,2)+'\n',{flag:'wx'});
console.log(JSON.stringify({checks,groups},null,2));
