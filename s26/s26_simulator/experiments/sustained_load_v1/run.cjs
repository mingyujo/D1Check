'use strict';
const C=require('./common.cjs'),{fs,path}=C,{spawnSync}=require('node:child_process');
const op=C.read(path.join(C.HERE,'OPERATION.json')),opSHA=C.sha(fs.readFileSync(path.join(C.HERE,'OPERATION.json')));C.verify(op);
if(fs.existsSync(op.output))throw Error('Consumed output namespace; automatic retry forbidden');
fs.mkdirSync(path.join(op.output,'raw'),{recursive:true});fs.mkdirSync(path.join(op.output,'prepared'));let started=0,complete=0,fail=0;const rows=[],errors=[],begin=Date.now();
function append(name,item){const fd=fs.openSync(path.join(op.output,name),'a');try{fs.writeFileSync(fd,JSON.stringify(item)+'\n');fs.fsyncSync(fd)}finally{fs.closeSync(fd)}}
for(const spec of op.cases){
 if(started>=op.environment_cap||(Date.now()-begin)/1000>op.wall_seconds)throw Error('Finite registered cap reached');
 const s=fs.statfsSync(C.ROOT);if(s.bavail*s.bsize<8*1024**3)throw Error('8GiB reserve');
 const receipt={event:'START',id:spec.id,utc:new Date().toISOString(),operation_sha256:opSHA,sequence:++started};append('receipts.jsonl',receipt);console.log('START',started,spec.id,'N',spec.n);
 const result=spawnSync(process.execPath,[path.join(C.HERE,'case.cjs'),spec.id],{cwd:C.HERE,encoding:'utf8',timeout:op.case_wall_seconds*1000,maxBuffer:2*1024**2});
 if(result.status===0){const row=C.read(path.join(op.output,'prepared',spec.id+'.json'));rows.push(row);append('rows.jsonl',row);append('receipts.jsonl',{...receipt,event:'COMPLETE',raw_sha256:row.raw_sha256,utc:new Date().toISOString()});complete++;console.log('COMPLETE',spec.id,'on',row.metrics.on_time+'/'+spec.n,'J',row.metrics.total_API_J===null?'UNAVAILABLE_CENSORED':row.metrics.total_API_J.toFixed(3),'APpeak',row.metrics.AP_peak.toFixed(2));}
 else{const error={id:spec.id,status:result.status,signal:result.signal,error:String(result.error??''),stderr:result.stderr,stdout:result.stdout};errors.push(error);C.write(path.join(op.output,spec.id+'.failure.json'),error);append('receipts.jsonl',{...receipt,event:'FAIL',utc:new Date().toISOString()});fail++;console.log('FAIL',spec.id,String(result.stderr??result.error).slice(-300));if(spec.kind==='P0')break;}
 C.write(path.join(op.output,'PROGRESS_'+started+'.json'),{started,complete,fail,last:spec.id});
}
C.verify(op);C.write(path.join(op.output,'TERMINAL.json'),{status:complete===op.planned_START?'COMPLETED_ALL_CASES':'COMPLETED_WITH_FAILURE_OR_P0_STOP',started,complete,fail,planned:op.planned_START,errors,elapsed_s:(Date.now()-begin)/1000,operation_sha256:opSHA,new_RL:0,new_fit:0,automatic_retry:false});
console.log(JSON.stringify({status:'TERMINAL',started,complete,fail,elapsed_s:(Date.now()-begin)/1000}));
