'use strict';
// Saved corpus projection. Every original request remains a row, including failures.
const fs=require('fs'),path=require('path'),crypto=require('crypto');
const B=path.resolve(__dirname,'../..');
const helper=require('../S26-PREDICTIVE-IMPROVEMENT-20261016/extract_conditional_rows.cjs');
const sha=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
const hash=x=>crypto.createHash('sha256').update(JSON.stringify(x)).digest('hex');
const read=p=>JSON.parse(fs.readFileSync(p,'utf8').replace(/^\uFEFF/,''));
const ns=x=>Number.isSafeInteger(x)&&x>=0?x:null;
const names=['dispatch_ns','execution_start_ns','host_inference_start_ns','host_inference_return_ns','output_ready_ns','persist_complete_ns','readback_start_ns','readback_end_ns','worker_release_ns','lane_available_ns'];
function integral(intervals){const ev=intervals.flatMap(([l,r])=>[[l,1],[r,-1]]).sort((a,b)=>a[0]-b[0]);const pieces=[];let t=null,a=0,sum=0;for(let i=0;i<ev.length;){let u=ev[i][0];if(t!==null&&u>t&&a){pieces.push([t,u,a,sum]);sum+=(u-t)*a;}while(i<ev.length&&ev[i][0]===u)a+=ev[i++][1];t=u;}return x=>{let l=0,r=pieces.length;while(l<r){let m=(l+r)>>1;if(pieces[m][0]<x)l=m+1;else r=m;}if(!l)return 0;let p=pieces[l-1];return p[3]+Math.max(0,Math.min(x,p[1])-p[0])*p[2];};}
function main(op){
 const out=op.output_dir;fs.mkdirSync(out,{recursive:false});
 const data=read(op.normalized_path),payload=read(op.forecast_payload_path),bundle=read(op.cost_bundle_path);
 if(data.sessions.length!==207)throw Error('207 physical sessions required');
 const f=fs.openSync(path.join(out,'ROWS.jsonl.part'),'wx'),sessions=[],seen=new Set(),counts={rows:0,inference_eligible:0,phase_eligible:0,OLD:0,M8:0,excluded:{}};
 try{for(const s of data.sessions){
  const uid=s.session_uid??s.id,qs=s.whole_vectors||[],ap=helper.APPoints(s),bank=helper.rawBank(s),phaseCounts={};
  const peer={};for(const route of ['classification_CPU','classification_GPU','classification_NPU','detection_CPU'])peer[route]=integral(qs.filter(q=>q.task_id+'_'+q.selected_backend===route&&ns(q.host_inference_start_ns)!==null&&ns(q.host_inference_return_ns)!==null&&q.host_inference_return_ns>=q.host_inference_start_ns).map(q=>[q.host_inference_start_ns,q.host_inference_return_ns]));
  for(let i=0;i<qs.length;i++){
   const q=qs[i],role=helper.roleOf(s,q),route=q.task_id+'_'+q.selected_backend,models=(s.compatibility?.runtime_models||[]).filter(m=>m.key===route),runtime=models.length===1?models[0]:null,proof=(s.compatibility?.runtime_return_proofs||[]).find(m=>m.key===route);
   const id=hash([s.physical_session_key,q.request_id??null,i]);if(seen.has(id))throw Error('Duplicate physical request');seen.add(id);
   const t=Object.fromEntries(names.map(k=>[k,ns(q[k])]));const start=t.host_inference_start_ns,end=t.host_inference_return_ns;
   const reasons=[];if(role.role!=='MAIN_REGISTERED_REQUEST')reasons.push('NOT_REGISTERED_MAIN');if(q.terminal_status!=='succeeded')reasons.push('NOT_SUCCEEDED');if(!Object.hasOwn(peer,route))reasons.push('UNSUPPORTED_ROUTE');if(start===null||end===null||end<=start)reasons.push('INFERENCE_INTERVAL_MISSING_OR_INVALID');if(!runtime?.model_sha256)reasons.push('MODEL_IDENTITY_MISSING');
   let a=null;if(start!==null)for(const p of ap.points)if(p.available_upper_ns<=start&&p.sample_time_ns<=start&&(!a||p.sample_time_ns>a.sample_time_ns))a=p;
   const other=route==='detection_CPU'?['classification_GPU','classification_NPU']:route==='classification_CPU'?[]:['detection_CPU'];
   const overlap=start!==null&&end>start?other.reduce((v,k)=>v+peer[k](end)-peer[k](start),0)/(end-start):null;
   const phaseValid=s.domain==='M8_READBACK_RENAME_RESPONSE'&&names.every(k=>t[k]!==null)&&names.every((k,j)=>!j||t[k]>=t[names[j-1]]);
   const r={id,session:uid,physical_session_key:s.physical_session_key,index:i,request_id:q.request_id,ordinal:q.ordinal??i,group:s.cv_group??s.cohort,cohort:s.cohort,pool:s.source_pool,domain:s.domain,policy:s.policy,bank:bank.raw_bank_label,registered_bank_key:bank.registered_bank_key,role:role.role,terminal:q.terminal_status,route,priority:q.priority,model_sha256:runtime?.model_sha256??null,image_sha256:s.manifest?.image?.sha256??null,engine:proof?.engine??s.compatibility?.engine??null,version:proof?.litert_version??s.compatibility?.litert_version??null,cpu_threads:proof?.compiled_model_options?.cpu_options?.num_threads??runtime?.cpu_threads??null,gpu_precision:proof?.compiled_model_options?.gpu_options?.precision??runtime?.gpu_precision??null,apk:s.compatibility?.apk_sha256??null,AP:a?.value_c??null,AP_age_s:a?(start-a.sample_time_ns)/1e9:null,AP_source:a,overlap_fraction:overlap,inference_s:start!==null&&end>start?(end-start)/1e9:null,phase_eligible:phaseValid,inference_eligible:reasons.length===0,exclusions:reasons,timestamps_ns:t,common_start_ns:s.common_start_ns,scheduled_arrival_ns:q.scheduled_arrival_ns??null,deadline_ns:q.deadline_ns??null,source_raw_sha256:s.selected_source?.progress_sha256??null};
   fs.writeSync(f,JSON.stringify(r)+'\n');counts.rows++;counts[s.source_pool]++;counts.inference_eligible+=Number(r.inference_eligible);counts.phase_eligible+=Number(phaseValid);for(const reason of reasons)counts.excluded[reason]=(counts.excluded[reason]||0)+1;phaseCounts[route]=(phaseCounts[route]||0)+1;
  }
  sessions.push({id:uid,group:s.cv_group??s.cohort,pool:s.source_pool,domain:s.domain,bank:bank.raw_bank_label,policy:s.policy,rows:qs.length,phaseCounts,AP_points:ap.points.length,AP_invalid:ap.invalid,selected_source:s.selected_source,physical_session_key:s.physical_session_key,compatibility:s.compatibility,manifest_requests:s.manifest?.requests??null});
  process.stdout.write(JSON.stringify({session:uid,rows:counts.rows})+'\n');
 }fs.fsyncSync(f);}finally{fs.closeSync(f);}
 fs.renameSync(path.join(out,'ROWS.jsonl.part'),path.join(out,'ROWS.jsonl'));
 if(counts.rows!==88688)throw Error('Original 88688 denominator mismatch');
 const slim={schema:'S26_COST_SLIM_V1',targets:Object.fromEntries(Object.entries(bundle.targets).map(([k,v])=>[k,{parameter_sha256:v.parameter_sha256,model:Object.fromEntries(['target','spec','raw_basis_coefficients','history_normalization','domain_enabled','domains'].map(n=>[n,n==='history_normalization'&&v.model[n]?{mean:v.model[n].mean,scale:v.model[n].scale}:v.model[n]]))}]))};
 for(const[n,x]of Object.entries({'SESSIONS.json':sessions,'COST.json':slim,'CONTEXTS.json':payload.contexts}))fs.writeFileSync(path.join(out,n),JSON.stringify(x)+'\n',{flag:'wx'});
 const files=Object.fromEntries(['ROWS.jsonl','SESSIONS.json','COST.json','CONTEXTS.json'].map(n=>[n,{sha256:sha(path.join(out,n)),bytes:fs.statSync(path.join(out,n)).size}]));
 fs.writeFileSync(path.join(out,'EXTRACTION_RESULT.json'),JSON.stringify({status:'PASS',scope:'SAVED_DATA_PROJECTION_NOT_FIT_OR_NEW_MEASUREMENTS',counts,sessions:sessions.length,files,AP_availability:'Original raw HAL sample/completion upper, latest completed prior to inference start; stale ages retained',phase_eligibility:'Complete ordered M8 readback joint phase template only. Old inference prefixes remain eligible separately.',cross_contract_transfer:'Not applied by extraction; later model must explicitly register pooling assumptions'},null,2)+'\n',{flag:'wx'});
}
if(require.main===module)main(read(process.argv[2]));module.exports={integral,main};
