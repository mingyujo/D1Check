'use strict';
// A separate UTF-8 metadata repair; preserve the consumed original attempt.
const fs=require('fs'),path=require('path'),crypto=require('crypto');
const root=path.resolve(__dirname,'../..'),repo=path.dirname(root);
const read=p=>JSON.parse(fs.readFileSync(p)),sha=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
const pin=p=>({path:path.relative(repo,p).replaceAll('\\','/'),sha256:sha(p),bytes:fs.statSync(p).size});
const op=read(path.join(__dirname,'OPERATION.json')),out=path.join(root,op.output_dir);
const rows=fs.readFileSync(path.join(out,'verification_receipts.jsonl'),'utf8').trim().split(/\r?\n/).map(JSON.parse);
const failed=rows.find(r=>r.stage==='environment'&&r.event==='VERIFY_FAIL');
if(!failed||fs.existsSync(path.join(out,'ENVIRONMENT.json')))throw Error('Exact failed metadata attempt required');
const original=path.join(__dirname,'capture_environment.py'),repaired=path.join(__dirname,'capture_environment_v2.py');
const before=fs.readFileSync(original,'utf8');
const after=before.replace("(out / 'START.json').read_text()", "(out / 'START.json').read_text(encoding='utf-8')");
if(before===after)throw Error('Expected one UTF-8 read repair');
fs.writeFileSync(repaired,after,{flag:'wx'});
const oldDriver=path.join(__dirname,'postrun.cjs'),newDriver=path.join(__dirname,'postrun_v2.cjs');
const driver=fs.readFileSync(oldDriver,'utf8').replace(
 "environment:{entry:'capture_environment.py'", "environment_v2:{entry:'capture_environment_v2.py'").replace(
 'POSTRUN_DRIVER_OPERATION.json','POSTRUN_DRIVER_OPERATION_V2.json');
if(driver===fs.readFileSync(oldDriver,'utf8'))throw Error('Expected separate repair stage');
fs.writeFileSync(newDriver,driver,{flag:'wx'});
const failureFile=path.join(out,'ENVIRONMENT_CAPTURE_FAILURE_01.json');
fs.writeFileSync(failureFile,JSON.stringify({schema:'A24-coupled345-metadata-only-failure-v1',failed_receipt:failed,
 error:"UnicodeDecodeError: Windows cp949 default cannot read UTF-8 START.json containing a Korean path",
 output_written:false,repair:'Separate capture_environment_v2 explicitly reads UTF-8; old source/failed receipt unchanged',
 new_environment_START:0,simulation_restarts:0,scientific_results_changed:false},null,2)+'\n',{flag:'wx'});
fs.writeFileSync(path.join(__dirname,'POSTRUN_DRIVER_OPERATION_V2.json'),JSON.stringify({
 schema:'A24-coupled345-metadata-repair-driver-v2',utc:new Date().toISOString(),source:pin(newDriver),
 pins:[pin(original),pin(repaired),pin(oldDriver),pin(failureFile)],
 scope:'New environment_v2 metadata identity only; no repeat of the consumed environment stage or any simulation',
 new_environment_START:0,new_fit:0,simulation_results_unchanged:true},null,2)+'\n',{flag:'wx'});
console.log('Preserved metadata failure and registered a separate UTF-8-only repair');
