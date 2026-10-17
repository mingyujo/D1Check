'use strict';
const D=require('../competition_cost_20261017/competition_design.cjs');
function design(){
 const cases=[];
 for(const [p,pattern] of D.SPEC.patterns.entries()){
  const seed=20271031+p,load=[.65,.95][p],base=D.build(.5,pattern,load,seed);
  const q=base.input.requests,cycle=Math.max(...q.map(x=>x.arrival_s))-35+1.5;
  for(const duration of [120,300,600]){
   const requests=[];
   for(let i=0;i<3073;i++){
    const x=q[i%48],offset=Math.floor(i/48)*cycle,arrival=+(x.arrival_s+offset).toFixed(8);
    if(arrival>=35+duration)break;
    requests.push({...x,ordinal:i,arrival_s:arrival,deadline_s:+(x.deadline_s+offset).toFixed(8)});
   }
   if(requests.length>3072)throw Error('User request cap3072');
   const id='SUPPLY_'+duration+'_'+p,hi=35+duration+15;
   cases.push({id,n:requests.length,input:{...base.input,requests},temperature_c:26,
    condition:{mix:.5,pattern,load,supply_s:duration,n:requests.length,temperature_c:26},
    supply_stop_s:35+duration,work_window:[35,hi],service_stop_s:hi,drain_stop_s:hi+30,observation_end_s:hi+180,
    cycle_s:cycle,common_potential_key:['SUSTAINED20261017',seed]});
  }
 }
 return {schema:'A24-sustained-load-inputs-v1',cases,policies:['EDF','ATC','RL'],
  prefix_contract:'Identical public requests and latent potential keys across durations within each pattern',
  new_physical_data:false,new_training:false};
}
module.exports={design};
