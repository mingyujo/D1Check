'use strict';
// Input-only development: arrivals change; task, priority and relative due dates do not.
const D=require('../competition_cost_20261017/competition_design.cjs');
const SPEC={schema:'A24-choice-opportunity-design-v1',seed:20269117,n:48,
 mixes:[.25,.5,.75],packet_sizes:[2,4],seconds_per_request:.8,
 reference_load:.95,start_s:35,tail_s:15,
 purpose:'Expose simultaneous request and route choices, not maximize measured policy advantage',
 selection_by_policy_result:false,physical_capacity:{CPU:1,GPU:1,total:2},
 protection_changed:false,relative_deadlines_changed:false,
 primary_thresholds:{two_free_rate_gain_pp:10,multiple_request_rate_gain_pp:10},
 independent_evaluation:false,scope:'preregistered development witnesses; no RL training'};
function generate(){
 const cases=[];
 for(const [mi,mix] of SPEC.mixes.entries())for(const [pi,packet]of SPEC.packet_sizes.entries()){
  const base=D.build(mix,D.SPEC.patterns[pi],SPEC.reference_load,SPEC.seed);
  const pair='C'+Math.round(mix*100)+'_P'+packet;
  for(const arm of ['REFERENCE','PACKET']){
   const input=JSON.parse(JSON.stringify(base.input));
   if(arm==='PACKET')input.requests=input.requests.map((q,i)=>{
    const arrival=+(SPEC.start_s+Math.floor(i/packet)*packet*SPEC.seconds_per_request).toFixed(8);
    return {...q,arrival_s:arrival,deadline_s:+(arrival+q.deadline_s-q.arrival_s).toFixed(8)};
   });
   const hi=+(Math.max(...input.requests.map(q=>q.arrival_s))+SPEC.tail_s).toFixed(8);
   cases.push({id:pair+'_'+arm,pair,arm,mix,packet,n:48,input,
    work_window:[35,hi],service_stop_s:hi,drain_stop_s:hi+30,observation_end_s:hi+180,
    common_potential_key:['A24_CHOICE_OPPORTUNITY_20261017',SPEC.seed,pair]});
  }
 }
 return {schema:SPEC.schema,spec:SPEC,cases};
}
module.exports={SPEC,generate};
