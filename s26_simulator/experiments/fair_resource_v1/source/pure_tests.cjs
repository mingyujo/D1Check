'use strict';
const assert=require('node:assert/strict'),fs=require('fs');
const a=require('./fair_actions.cjs'),b=require('./rolling_action_v2.cjs');let checks=0;
const test=(v,label)=>{checks++;assert.ok(v,label)};
const labels=a.ROUTES.map(r=>'BASE:'+r+'|test');
const nom={timing:{spec:{labels},coef:[-2,-1,-3,-1]},routes:Object.fromEntries(a.ROUTES.map((r,i)=>[r,{identity:{route:r,model_sha256:'test'},residual:1,gap_s:.001,admission_s:.001,return_s:.001,post_s:.001,readback_fraction:r==='detection_CPU'?1:0,incremental_J_proxy:[3,2,1,4][i],AP_area_proxy:[3,2,1,4][i]}]))};
const q=(ordinal,deadline,task='classification')=>({ordinal,task,priority:task==='classification'?'urgent':'normal',arrival:ordinal*.001,deadline});
const obs={time:.02,ready:[q(0,2),q(1,.8)],owners:[],sensor:{AP:30,time:0},sensor_history:[],initial_AP:30,wait_used_s:0};
for(const policy of a.POLICIES){
 let r=a.select(obs,nom,{},policy);test(r.ordinal===(policy.startsWith('FIFO')?0:1),'FIFO/EDF order');test(r.route==='classification_NPU','free NPU allocation');
 test(JSON.stringify(r.candidates)===JSON.stringify(b.select(obs,nom,{}).candidates),'same exact nominal candidates');
 for(const route of a.ROUTES.slice(0,3)){r=a.select(obs,nom,{classification_routes:[route]},policy);test(r.route===route,'all class routes selectable')}
 const busy={...obs,ready:[q(0,2),q(1,3,'detection')],owners:[{route:'classification_NPU',dispatch:0}]};r=a.select(busy,nom,{},policy);test(r.ordinal===1&&r.route==='detection_CPU','dispatchable backfill shared support');
 r=a.select({...obs,owners:[{route:'classification_NPU'},{route:'detection_CPU'}]},nom,{},policy);test(r.kind==='NONE','capacity2');
 const cool={...obs,ready:[q(0,10)],sensor:{AP:32,time:1},sensor_history:[{AP:33,time:0},{AP:32,time:1}],time:1.2};
 r=a.select(cool,nom,{},policy);test(r.kind==='WAIT'&&r.dose_s===.05,'identical WAIT predicate');
 test(a.select({...cool,wait_used_s:2},nom,{},policy).kind==='DISPATCH','WAIT cap');
 test(a.select({...cool,owners:[{route:'detection_CPU'}]},nom,{},policy).kind==='DISPATCH','no WAIT while owned');
}
test(JSON.stringify(obs.ready)===JSON.stringify([q(0,2),q(1,.8)]),'no mutation of ready inputs');
assert.throws(()=>a.select(obs,nom,{},'OTHER'));checks++;
const result={status:'PASS',checks,new_policy_environments:0,new_Simulator:0,new_NN:0,new_fit:0};
fs.writeFileSync(process.argv[2],JSON.stringify(result,null,2)+'\n',{flag:'wx'});console.log(JSON.stringify(result));
