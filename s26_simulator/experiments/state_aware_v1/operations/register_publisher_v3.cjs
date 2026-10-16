'use strict';
const fs=require('fs'),path=require('path'),crypto=require('crypto');
const O=__dirname,old=path.join(O,'publish_state_fast.cjs'),dest=path.join(O,'publish_state_fast_v3.cjs');
const sha=f=>crypto.createHash('sha256').update(fs.readFileSync(f)).digest('hex');
const before=fs.readFileSync(old,'utf8');
const target="path.join(O,fs.existsSync(path.join(O,'PUBLISH_FAST_OPERATION_V2.json'))?'PUBLISH_FAST_OPERATION_V2.json':'PUBLISH_FAST_OPERATION.json')";
if(!before.includes(target))throw Error('Expected publisher operation lookup absent');
let after=before.replace(target,"path.join(O,'PUBLISH_FAST_OPERATION_V3.json')");
const list="'POSTRUN_OPERATION.json','PUBLISH_FAST_OPERATION.json'";
if(!after.includes(list))throw Error('Expected obsolete publication receipt entry absent');
after=after.replace(list,"'POSTRUN_OPERATION.json','PUBLISH_FAST_OPERATION_V3.json'");
fs.writeFileSync(dest,after,{flag:'wx'});
fs.writeFileSync(path.join(O,'PUBLISH_FAST_OPERATION_V3.json'),JSON.stringify({
 status:'REGISTERED_BEFORE_DERIVED_PUBLIC_REPORT',created_utc:new Date().toISOString(),source:dest,source_sha256:sha(dest),
 parent_source:old,parent_source_sha256:sha(old),
 repair:'Publication receipt path only: V2 registration exists while obsolete unversioned receipt does not. Preserve prior source/operations; no report arithmetic or policy changes.',
 requires:['AUDIT_FAST_V1/RESULT.json','BINDING_RESULT.json','ANALYSIS_V1/SUMMARY.json'],new_policy_environments:0,new_fit:0,new_RL:0
},null,2)+'\n',{flag:'wx'});
console.log('Registered publisher V3: receipt-path repair only');
