'use strict';
const D=require('../competition_cost_20261017/competition_design.cjs');
const rates=[.25,.4,.55,.7,.85,1,1.2],durations=[60,120,240],policies=['FIFO_CPU','EDF_CPU','FIFO_GPU','EDF_GPU','REPAIR_PPO'];
function make(rate,duration,pattern,rep=0,phase=1){
 const seed=20281221+rep*10+pattern,base=D.build(.5,D.SPEC.patterns[pattern],[.65,.95][pattern],seed),q=base.input.requests,cycle=Math.max(...q.map(x=>x.arrival_s))-35+1.5,requests=[];
 for(let i=0;i<3073;i++){const proto=q[i%48],arrival=+(35+(proto.arrival_s-35+Math.floor(i/48)*cycle)/rate).toFixed(8);if(arrival>=35+duration)break;requests.push({...proto,ordinal:i,arrival_s:arrival,deadline_s:+(arrival+proto.deadline_s-proto.arrival_s).toFixed(8)});}
 if(!requests.length||requests.length>3072)throw Error('Finite request cap');
 return {id:`LW${phase}_R${Math.round(rate*1000)}_T${duration}_P${pattern}_S${rep}`,n:requests.length,input:{...base.input,requests},temperature_c:26,condition:{pattern:D.SPEC.patterns[pattern],pattern_index:pattern,mix:.5,reference_load:[.65,.95][pattern],rate_multiplier:rate,supply_s:duration,rep,phase,seed,n:requests.length},supply_stop_s:35+duration,service_stop_s:35+duration+600,drain_stop_s:35+duration+630,observation_end_s:35+duration+780,work_window:[35,35+duration+600],base_cycle_s:cycle,common_potential_key:['A24_LOAD_WINDOW20261018',seed]};
}
const initial=()=>rates.flatMap(r=>durations.flatMap(t=>[0,1].map(p=>make(r,t,p))));
module.exports={rates,durations,policies,make,initial};
