'use strict';
const fs=require('fs'),path=require('path'),crypto=require('crypto'),zlib=require('zlib');
const root=path.resolve(__dirname,'../..'),read=p=>JSON.parse(fs.readFileSync(p)),sha=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
const op=read(path.join(__dirname,'OPERATION.json')),out=path.join(root,op.output_dir),result=read(path.join(out,'RESULT.json')),cache=new Map();
const rows=result.rows.filter(r=>r.kind==='DENSITY').map(row=>{
 const file=path.join(out,row.label+'.raw.json.gz');if(sha(file)!==row.raw_sha256)throw Error('Raw pin');
 const r=JSON.parse(zlib.gunzipSync(fs.readFileSync(file))).result,dispatch=r.decisions.filter(x=>x.action.kind==='DISPATCH');cache.set(row.label,r.requests);
 if(dispatch.length!==r.requests.filter(x=>x.dispatch_ns!==null).length)throw Error('Dispatch count');
 return {label:row.label,condition:row.condition,policy:row.policy,n:row.n,dispatches:dispatch.length,
  multiple_ready_percent:100*dispatch.filter(x=>x.public_state.queue.length>1).length/dispatch.length,
  both_routes_free_percent:100*dispatch.filter(x=>x.public_state.owners.length===0).length/dispatch.length,wait_s:r.wait_used_ns/1e9};
});
let admission=0,work=0;
for(const p of [0,1])for(const policy of ['EDF','ATC','RL'])for(const factor of op.rate_multipliers.filter(f=>f!==3)){
 const tag=f=>String(Math.round(f*100)).padStart(3,'0'),short=cache.get('DENSITY_'+tag(factor)+'_'+p+'_'+policy),long=cache.get('DENSITY_300_'+p+'_'+policy);
 for(let i=0;i<short.length;i++){
  const a=short[i],b=long[i];if(a.request_id!==b.request_id||a.queue_entry_ns-a.scheduled_arrival_ns!==b.queue_entry_ns-b.scheduled_arrival_ns)throw Error('Admission delay prefix');admission++;
  if(a.route===b.route&&a.route!==null){if(JSON.stringify(a.timing.stages_ns)!==JSON.stringify(b.timing.stages_ns)||a.timing.sample_id!==b.timing.sample_id)throw Error('Latent work prefix');work++;}
 }
}
fs.writeFileSync(path.join(out,'CHOICE_DIAGNOSIS.json'),JSON.stringify({utc:new Date().toISOString(),new_environment_START:0,result_sha256:sha(path.join(out,'RESULT.json')),admission_prefix_checks:admission,same_route_work_prefix_checks:work,rows},null,2)+'\n',{flag:'wx'});
console.log(JSON.stringify({status:'PASS',rows:rows.length,admission_prefix_checks:admission,work_prefix_checks:work}));
