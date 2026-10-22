'use strict';
const C=require('./common.cjs'),{fs,path}=C,{spawnSync}=require('node:child_process');
const op=C.read(path.join(C.HERE,'OPERATION.json')),recovery=C.read(path.join(C.HERE,'RECOVERY_OPERATION.json')),opSHA=C.sha(fs.readFileSync(path.join(C.HERE,'OPERATION.json'))),recoverySHA=C.sha(fs.readFileSync(path.join(C.HERE,'RECOVERY_OPERATION.json')));C.verify(op);C.verify(recovery);
if(C.sha(fs.readFileSync(recovery.prefix_journal.path))!==recovery.prefix_journal.sha256)throw Error('Prefix journal changed');
for(const p of recovery.prefix)for(const f of [p.raw,p.prepared])if(C.sha(fs.readFileSync(f.path))!==f.sha256)throw Error('Prefix data changed');
C.write(path.join(op.output,'RECOVERY_START.json'),{utc:new Date().toISOString(),recovery_sha256:recoverySHA,reused_actual_P0:4,failed_identity_retry:false});
let started=5,complete=4,fail=1,begin=Date.now(),fresh=0;const errors=[C.read(recovery.failed.path)];
function append(name,item){const fd=fs.openSync(path.join(op.output,name),'a');try{fs.writeFileSync(fd,JSON.stringify(item)+'\n');fs.fsyncSync(fd)}finally{fs.closeSync(fd)}}
for(const spec of recovery.unstarted){
 if(started>=op.environment_cap||(Date.now()-begin)/1000>op.wall_seconds)throw Error('Recovery finite cap');
 C.verify(op);C.verify(recovery);const disk=fs.statfsSync(C.ROOT);if(disk.bavail*disk.bsize<8*1024**3)throw Error('8GiB reserve');
 const receipt={event:'START',id:spec.id,utc:new Date().toISOString(),operation_sha256:opSHA,recovery_sha256:recoverySHA,sequence:++started};fresh++;append('receipts.jsonl',receipt);console.log('START',started,spec.id,'N',spec.n);
 const child=spawnSync(process.execPath,[path.join(C.HERE,'case.cjs'),spec.id],{cwd:C.HERE,encoding:'utf8',timeout:op.case_wall_seconds*1000,maxBuffer:2*1024**2});
 if(child.status===0){const row=C.read(path.join(op.output,'prepared',spec.id+'.json'));append('rows.jsonl',row);append('receipts.jsonl',{...receipt,event:'COMPLETE',raw_sha256:row.raw_sha256,utc:new Date().toISOString()});complete++;console.log('COMPLETE',spec.id,'on',row.metrics.on_time+'/'+spec.n,'J',row.metrics.total_API_J===null?'CENSORED':row.metrics.total_API_J.toFixed(3),'peak',row.metrics.AP_peak.toFixed(2));
  if(spec.kind==='P0'){const proof=spawnSync(process.execPath,[path.join(C.HERE,'edf_replay.cjs')],{cwd:C.HERE,encoding:'utf8',maxBuffer:2*1024**2});console.log(proof.stdout);if(proof.status!==0)throw Error('EDF pure induction gate '+proof.stderr);}
 }else{const error={id:spec.id,status:child.status,signal:child.signal,error:String(child.error??''),stderr:child.stderr,stdout:child.stdout};errors.push(error);C.write(path.join(op.output,spec.id+'.failure.json'),error);append('receipts.jsonl',{...receipt,event:'FAIL',utc:new Date().toISOString()});fail++;console.log('FAIL',spec.id,String(child.stderr??child.error).slice(-500));if(spec.kind==='P0')break;}
 C.write(path.join(op.output,'RECOVERY_PROGRESS_'+started+'.json'),{started,complete,fail,last:spec.id});
}
C.verify(op);C.verify(recovery);C.write(path.join(op.output,'TERMINAL.json'),{status:complete===41&&fail===1?'COMPLETED_ALL_COMPARISONS_PRESERVED_PREFLIGHT_FAIL':'RECOVERY_FINISHED_WITH_ADDITIONAL_FAILURES',started,complete,fail,planned:42,fresh_recovery_starts:fresh,reused_prefix:5,errors,elapsed_recovery_s:(Date.now()-begin)/1000,operation_sha256:opSHA,recovery_sha256:recoverySHA,new_RL:0,new_fit:0,automatic_retry:false,failed_identity_retry:false});
console.log(JSON.stringify({status:'RECOVERY_TERMINAL',started,complete,fail,elapsed_s:(Date.now()-begin)/1000}));
