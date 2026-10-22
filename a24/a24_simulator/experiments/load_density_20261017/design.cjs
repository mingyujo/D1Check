'use strict';
const D=require('../competition_cost_20261017/competition_design.cjs');
const FACTORS=[.5,1,1.5,2,3],tag=f=>String(Math.round(f*100)).padStart(3,'0');
function design(){
 const cases=[];
 for(const [p,pattern] of D.SPEC.patterns.entries()){
  const seed=20271031+p,load=[.65,.95][p],base=D.build(.5,pattern,load,seed),q=base.input.requests;
  const cycle=Math.max(...q.map(x=>x.arrival_s))-35+1.5;
  for(const factor of FACTORS){
   const requests=[];
   for(let i=0;i<3073;i++){
    const proto=q[i%48],offset=Math.floor(i/48)*cycle,arrival=+(35+(proto.arrival_s-35+offset)/factor).toFixed(8);
    if(arrival>=155)break;
    requests.push({...proto,ordinal:i,arrival_s:arrival,deadline_s:+(arrival+proto.deadline_s-proto.arrival_s).toFixed(8)});
   }
   if(requests.length>3072)throw Error('User3072cap');
   cases.push({id:'DENSITY_'+tag(factor)+'_'+p,n:requests.length,input:{...base.input,requests},temperature_c:26,
    condition:{pattern,mix:.5,reference_load:load,rate_multiplier:factor,supply_s:120,n:requests.length,temperature_c:26},
    supply_stop_s:155,work_window:[35,755],service_stop_s:755,drain_stop_s:785,observation_end_s:935,
    base_cycle_s:cycle,common_potential_key:['LOAD_DENSITY20261017',seed]});
  }
 }
 return {schema:'A24-load-density-v1',cases,policies:['EDF','ATC','RL'],rate_multipliers:FACTORS,
  fixed_supply_s:120,common_post_supply_dispatch_allowance_s:600,
  changed:'Arrival intervals compressed only; relative deadlines and every per-request latent potential unchanged across factors',
  new_training:false,new_physical_data:false};
}
module.exports={design,FACTORS,tag};
