'use strict';
const fs=require('fs'),path=require('path'),assert=require('node:assert/strict'),{plan}=require('./service_guard.cjs');let checks=0;
const q=(ordinal,priority,deadline)=>({ordinal,priority,task:priority==='urgent'?'classification':'detection',arrival:0,deadline});
const u=q(0,'urgent',.8),n=q(1,'normal',2),fresh=q(2,'normal',3);
function p(mode,time,ready,owners=[],response=.1){
 const obs={time,ready,owners:owners.map(route=>({ordinal:99,route})),capacity:3};const a=[],c=[];
 for(const x of ready)for(const route of x.priority==='urgent'?['classification_CPU','classification_NPU','classification_GPU']:['detection_CPU'])if(!owners.some(o=>o.split('_').at(-1)===route.split('_').at(-1))){a.push({kind:'DISPATCH',ordinal:x.ordinal,route});c.push({ordinal:x.ordinal,route,response,occupied:.2});}
 a.push({kind:'WAIT',ordinal:ready[0].ordinal,wait_s:.02});return {v:plan(mode,obs,a,c,{response,occupied:.2}),a};
}
function check(cond){assert.ok(cond);checks++;}
let x=p('BC_FULL',0,[u,n]);check(x.v===null);
x=p('BC_DISPATCH_ONLY',0,[u,n]);check(x.v.allowed_indices.length===4);check(x.v.allowed_indices.every(i=>x.a[i].kind==='DISPATCH'));
x=p('BC_PROGRESS_GUARD',.6,[u,n]);check(x.v.reason==='URGENT_NOMINAL_RISK');check(x.v.allowed_indices.every(i=>x.a[i].ordinal===0));
x=p('BC_PROGRESS_GUARD',2.1,[n,fresh]);check(x.v.reason==='NORMAL_ALREADY_LATE_PROGRESS');check(x.v.allowed_indices.every(i=>x.a[i].ordinal===1));
x=p('BC_RESOURCE_GUARD',0,[u,n]);check(x.v.allowed_indices.every(i=>x.a[i].route!=='classification_CPU'&&x.a[i].route!=='classification_GPU'));
x=p('BC_RESOURCE_GUARD',0,[u],['classification_NPU']);check(x.v.allowed_indices.length===0);
x=p('BC_RESOURCE_GUARD',.6,[u],['classification_NPU']);check(x.v.allowed_indices.length===1&&x.a[x.v.allowed_indices[0]].route==='classification_GPU');
x=p('BC_RESOURCE_GUARD',2.1,[n,fresh]);check(x.v.allowed_indices.length===1&&x.a[x.v.allowed_indices[0]].ordinal===1);
x=p('BC_RESOURCE_GUARD',.6,[u],['classification_NPU','classification_GPU']);check(x.v.allowed_indices.length===0);
for(const mode of ['BC_DISPATCH_ONLY','BC_PROGRESS_GUARD','BC_RESOURCE_GUARD'])for(const t of [0,.4,.7,1,2.1]){
 x=p(mode,t,[u,n,fresh]);check(x.v.allowed_indices.every(i=>Number.isInteger(i)&&i>=0&&i<x.a.length&&x.a[i].kind==='DISPATCH'));
}
const out={status:'PASS',utc:new Date().toISOString(),checks,new_environments:0,new_training:0,fixture_scope:'Public queue and stub nominal timings only; not a physical performance test',original_checkpoint_unchanged:true};
fs.writeFileSync(path.join(__dirname,'PREFLIGHT.json'),JSON.stringify(out,null,2)+'\n',{flag:'wx'});console.log(JSON.stringify(out));
