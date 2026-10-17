'use strict';
// Posthoc saved-only description; never changes native source, actions or selection.
const fs=require('fs'),path=require('path'),crypto=require('crypto'),zlib=require('zlib');
const root=path.resolve(__dirname,'../..'),read=p=>JSON.parse(fs.readFileSync(p));
const sha=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
const op=read(path.join(__dirname,'OPERATION.json')),amend=read(path.join(__dirname,'SAVED_AUDIT_V2.json')),out=path.join(root,amend.report_output_dir),result=read(path.join(out,'RESULT.json'));
const cache=new Map();
const records=result.rows.filter(r=>r.kind==='SUSTAINED').map(row=>{
 const p=path.join(out,row.label+'.raw.json.gz');if(sha(p)!==row.raw_sha256)throw Error('Raw SHA');
 const r=JSON.parse(zlib.gunzipSync(fs.readFileSync(p))).result,dispatch=r.decisions.filter(d=>d.action.kind==='DISPATCH');
 cache.set(row.label,r.requests);
 if(dispatch.length!==r.requests.filter(q=>q.dispatch_ns!==null).length||dispatch.length>row.n)throw Error('Dispatch accounting');
 const multiple=dispatch.filter(d=>d.public_state.queue.length>1).length,both=dispatch.filter(d=>d.public_state.owners.length===0).length;
 return {label:row.label,condition:row.condition,policy:row.policy,n:row.n,dispatches:dispatch.length,
  multiple_ready:multiple,multiple_ready_percent:100*multiple/dispatch.length,both_routes_free:both,both_routes_free_percent:100*both/dispatch.length,
  wait_s:r.wait_used_ns/1e9,raw_sha256:row.raw_sha256};
});
let admissionPrefixChecks=0,sameRouteWorkPrefixChecks=0;
for(const pattern of [0,1])for(const policy of ['EDF','ATC','RL'])for(const d of [120,300]){
 const shorter=cache.get('SUPPLY_'+d+'_'+pattern+'_'+policy),longer=cache.get('SUPPLY_600_'+pattern+'_'+policy);
 for(let i=0;i<shorter.length;i++){
  const a=shorter[i],b=longer[i];
  if(a.request_id!==b.request_id||a.queue_entry_ns!==b.queue_entry_ns)throw Error('Admission prefix differs');admissionPrefixChecks++;
  if(a.route===b.route&&a.route!==null){
   if(JSON.stringify(a.timing.stages_ns)!==JSON.stringify(b.timing.stages_ns)||a.timing.sample_id!==b.timing.sample_id)throw Error('Observed latent prefix differs');sameRouteWorkPrefixChecks++;
  }
 }
}
fs.writeFileSync(path.join(out,'CHOICE_DIAGNOSIS.json'),JSON.stringify({utc:new Date().toISOString(),
 source_sha256:sha(__filename),result_sha256:sha(path.join(out,'RESULT.json')),posthoc_saved_only:true,new_environment_START:0,new_training:0,
 admission_prefix_checks:admissionPrefixChecks,same_route_work_prefix_checks:sameRouteWorkPrefixChecks,
 limitation:'Observed controller states; not the maximum freedom across all possible schedules. Duration prefixes are correlated.',rows:records},null,2)+'\n',{flag:'wx'});
console.log(JSON.stringify(records));
