'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),z=require('node:zlib');
const {Physics}=require('./physics.cjs'),reference=require('../thermal_review_v3/cascade.cjs');let checks=0,max=0;
const pm={coef:[1,0,...Array(20).fill(.1)],scale:Array(22).fill(1)},tm={tau_fast_s:10,tau_slow_s:320,w_fast:.4,delta_C:0,gain_fast:1,gain_slow:2};
const intervals=Array.from({length:9},()=>[]);intervals[5]=[[0,20,3]];intervals[6]=[[0,20,3]];const times=[0,.25,.5,1,10,20,21,60,300];
const rows=reference.coupled(reference.steps(intervals),times,.6,0,31,30,pm,tm),p=Physics.fromPast(pm,tm,{baseline:.6,AP0:31,skin:30},intervals,0);let at=0;
for(let j=0;j<times.length;j++){const t=times[j];while(at<2){const next=at===0?0:20;if(next>t)break;p.advance(next-p.time);p.active(at===0?[0,0,0,0,0,3,1,0,0]:Array(9).fill(0));at++;}p.advance(t-p.time);const a=[p.power(),p.temperature(),p.J],b=[rows[j][0],rows[j][1],rows[j][2]-30];for(let k=0;k<3;k++){max=Math.max(max,Math.abs(a[k]-b[k]));checks++;}}
assert(max<1e-8);
const q=p.clone();q.advance(1);assert(p.time===300&&q.time===301);checks++;
// A constant power input has an independently known passive-filter solution and area.
const power={coef:[2,0,...Array(20).fill(0)],scale:Array(22).fill(1)},f=new Physics(power,tm,{baseline:.6,AP0:31,skin:30},0);f.advance(5);
const exact=30+.4*Math.exp(-.5)+.6*Math.exp(-5/320)+1.4*(1-Math.exp(-.5))+2.8*(1-Math.exp(-5/320));assert(Math.abs(f.temperature()-exact)<1e-10);assert(Math.abs(f.J-10)<1e-10);checks+=2;
const R=path.resolve(__dirname,'../..'),packet=JSON.parse(z.gunzipSync(fs.readFileSync(path.join(R,'experiments/multiresource_v1/PACKET.json.gz')))),ctx=packet.scenarios.find(s=>s.context_index===0).context;
const cfg={model:'CENTRAL',capacity:3,dispatch_stop_s:100,power_model:JSON.parse(fs.readFileSync(path.join(R,'experiments/capacity_power_v1/artifacts/G001/MODEL.json'))),thermal_model:JSON.parse(fs.readFileSync(path.join(R,'experiments/pipeline_thermal_v1/artifacts/G001/MODEL.json')))};
const obs={time:35,capacity:3,horizon_s:130,wait_used_s:0,ready:[{ordinal:0,task:'classification',priority:'urgent',arrival:34,deadline:34.001},{ordinal:1,task:'detection',priority:'normal',arrival:34,deadline:34.002}],owners:[],sensor:{AP:31.1,time:34},physics_context:{AP0:31.1,skin:31.3,baseline:ctx.initial_context.targets.POWER_API.baseline.median_api_w},cost_state:{activity9:{intervals:ctx.pre_activity9.intervals},targets:ctx.initial_context.targets}};
const policy=require('./policy.cjs'),nom=require('./source/multi_timing.cjs').nominal(packet);let bank;
policy.configure({mode:'RL',choose:b=>{bank=b;return b.actions.findIndex(a=>a.kind==='WAIT'&&a.wait_s===.05);}});const a=policy.select(obs,packet,nom,cfg);
assert(a.kind==='WAIT');assert(bank.actions.filter(a=>a.kind==='DISPATCH').length===4);assert(bank.mask.filter(Boolean).length===7);assert(bank.constraints.deadline_action_mask===false);assert(bank.x.length===27&&bank.x.every(x=>x.length===32));checks+=5;
policy.configure({mode:'EDF'});assert(policy.select(obs,packet,nom,cfg).ordinal===0);checks++;
console.log(JSON.stringify({status:'PASS_PURE_PHYSICS_AND_UNPROTECTED_ACTION_CONTRACT',checks,max_reference_cascade_error:max,nominal_counterfactuals:bank.actions.length,actual_environment_instances:0,new_training:0,late_dispatch_and_WAIT_candidates_retained:true}));
