'use strict';
const D=require('../competition_cost_20261017/competition_design.cjs');
function training(){const cases=[];
 for(const [p,pattern]of D.SPEC.patterns.entries()){
  const seed=20271151+p,load=[.65,.95][p],base=D.build(.5,pattern,load,seed),q=base.input.requests,cycle=Math.max(...q.map(x=>x.arrival_s))-35+1.5;
  for(const [f,duration]of [[.75,60],[.9,120],[1.05,60],[3,120]]){
   const requests=[];for(let i=0;i<3073;i++){const proto=q[i%48],arrival=+(35+(proto.arrival_s-35+Math.floor(i/48)*cycle)/f).toFixed(8);if(arrival>=35+duration)break;requests.push({...proto,ordinal:i,arrival_s:arrival,deadline_s:+(arrival+proto.deadline_s-proto.arrival_s).toFixed(8)});}
   if(requests.length>3072)throw Error('3072 cap');cases.push({id:'TRAINMID_'+Math.round(f*100)+'_'+p,n:requests.length,input:{...base.input,requests},temperature_c:26,condition:{pattern,mix:.5,reference_load:load,rate_multiplier:f,supply_s:duration,n:requests.length,temperature_c:26},supply_stop_s:35+duration,work_window:[35,35+duration+600],service_stop_s:35+duration+600,drain_stop_s:35+duration+630,observation_end_s:35+duration+780,base_cycle_s:cycle,common_potential_key:['GUARD_LEARNING20261018',seed]});
  }
 }
 return {cases,passes:4,arms:['FT_ON_NN','FT_OFF_NN','REPAIR_OFF_NN'],fixed_final_new_episode:32,checkpoint_selection:'Final EP32 fixed before results; no evaluation selection',reuse_initial_checkpoint:true};
}
module.exports={training};
