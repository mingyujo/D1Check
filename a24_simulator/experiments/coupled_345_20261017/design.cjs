'use strict';
const D=require('../competition_cost_20261017/competition_design.cjs');
function build(seed,mix,pattern,load,n,T,label){
 const base=D.build(mix,pattern,load,seed),q=base.input.requests,cycle=Math.max(...q.map(x=>x.arrival_s))-35+1.5;
 const input={...base.input,requests:Array.from({length:n},(_,i)=>{const x=q[i%48],offset=Math.floor(i/48)*cycle;return {...x,ordinal:i,arrival_s:+(x.arrival_s+offset).toFixed(8),deadline_s:+(x.deadline_s+offset).toFixed(8)}})};
 const hi=+(Math.max(...input.requests.map(x=>x.arrival_s))+15).toFixed(8);
 return {id:label,n,input,temperature_c:T,condition:{mix,pattern,load,n,temperature_c:T},
  work_window:[35,hi],service_stop_s:hi,drain_stop_s:+(hi+30).toFixed(8),observation_end_s:+(hi+180).toFixed(8),
  common_potential_key:['COUPLED345',seed,n]};
}
function design(){
 const train=Array.from({length:128},(_,i)=>build(20270101+i,[.25,.5,.75][i%3],D.SPEC.patterns[Math.floor(i/9)%2],[.65,.95][Math.floor(i/18)%2],i%4===3?96:48,[26,33,39][Math.floor(i/3)%3],'TRAIN_'+String(i).padStart(3,'0')));
 const dev=Array.from({length:6},(_,i)=>build(20270401+i,[.25,.5,.75][i%3],D.SPEC.patterns[i%2],[.65,.95][i%2],48,i<3?26:39,'DEV_'+i));
 const fresh=Array.from({length:12},(_,i)=>{const j=i%6;return build(20270501+j,[.25,.5,.75][Math.floor(j/2)],D.SPEC.patterns[j%2],[.65,.95][j%2],j%2?96:48,i<6?26:39,'FRESH_'+String(i).padStart(2,'0'));});
 const p0=[0,1].map(i=>build(20270011+i,.5,D.SPEC.patterns[i],.65,12,26,'P0_'+i));
 return {schema:'A24-coupled345-inputs-v1',train,dev,fresh,p0,
  partition:'New simulation recipes/seeds; same historical physical data. Fresh results never used for selection.',
  matched_temperature_pairs:'fresh0..5 and6..11 have identical input/work potentials and different initial temperature hypotheses',
  new_physical_data:false,posthoc_policy_filter:false};
}
module.exports={design,build};
