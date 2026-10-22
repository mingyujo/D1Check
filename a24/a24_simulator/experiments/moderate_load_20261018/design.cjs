'use strict';
const D=require('../competition_cost_20261017/competition_design.cjs');
const FACTORS=[.6,.75,.9,1.05,1.2],tag=f=>String(Math.round(f*100)).padStart(3,'0');
function design(){const cases=[];for(const [p,pattern]of D.SPEC.patterns.entries()){
 const seed=20271121+p,load=[.65,.95][p],base=D.build(.5,pattern,load,seed),q=base.input.requests,cycle=Math.max(...q.map(x=>x.arrival_s))-35+1.5;
 for(const factor of FACTORS)for(const duration of [60,120]){const requests=[];
 for(let i=0;i<3073;i++){const proto=q[i%48],arrival=+(35+(proto.arrival_s-35+Math.floor(i/48)*cycle)/factor).toFixed(8);if(arrival>=35+duration)break;
 requests.push({...proto,ordinal:i,arrival_s:arrival,deadline_s:+(arrival+proto.deadline_s-proto.arrival_s).toFixed(8)});}
 if(requests.length>3072)throw Error('3072 cap');cases.push({id:'MID_'+tag(factor)+'_'+p+'_'+duration,n:requests.length,input:{...base.input,requests},temperature_c:26,
 condition:{pattern,mix:.5,reference_load:load,rate_multiplier:factor,supply_s:duration,n:requests.length,temperature_c:26},supply_stop_s:35+duration,work_window:[35,35+duration+600],service_stop_s:35+duration+600,drain_stop_s:35+duration+630,observation_end_s:35+duration+780,base_cycle_s:cycle,common_potential_key:['MODERATE_LOAD20261018',seed]});}}
 return {schema:'A24-moderate-duration-rate-v1',cases,policies:['EDF','ATC','GUARD_ON_NN','GUARD_OFF_NN'],rate_multipliers:FACTORS,fixed_physics:true};}
module.exports={design,FACTORS,tag};
