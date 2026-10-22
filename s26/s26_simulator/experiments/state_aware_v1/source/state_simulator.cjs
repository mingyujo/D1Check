'use strict';
const base=require('./s26_simulator_v2.cjs'),actions=require('./state_actions.cjs'),cost=require('./state_cost.cjs');
class StateSimulator extends base.ResourceSimulator{
 constructor(packet,scenario,config){if(!actions.POLICIES.includes(config.policy))throw Error('Unknown state policy');super(packet,scenario,{...config,policy:base.OWN_POLICY});this.config={...this.config,...config};this.publicJobs=[];this.models={AP:packet.AP,power:packet.power};}
 dispatch(x){super.dispatch(x);this.publicJobs.push(this.owners.find(o=>o.ordinal===x.q.ordinal));}
 publicObservation(){const obs=super.publicObservation();return {...obs,cost_state:cost.publicState(this.publicJobs,obs,this.scenario.context.initial_context,this.scenario.context.pre_activity9.intervals)};}
 choose(){
  if(!this.ready.length||this.time>=120-1e-9)return null;
  const obs=this.publicObservation(),key=JSON.stringify([obs.ready.map(q=>q.ordinal),obs.owners,obs.sensor.time]);if(key===this.lastDecisionKey)return null;this.lastDecisionKey=key;
  const result=actions.select(obs,this.publicNominalModel,this.models,this.config.policy,this.config.action_options??{});if(result.kind==='NONE')return null;
  this.decisionTrace.push({time:this.time,public_observation:obs,action:result});
  if(result.kind==='WAIT'){if(this.owners.length)throw Error('WAIT while owned');this.waitDose+=result.dose_s;this.waitUntil=Math.min(120,this.time+result.dose_s);this.lastDecisionKey=null;this.events.push([this.time,'WAIT_START',null,this.waitUntil-this.time]);return 'WAIT';}
  const q=this.ready.find(q=>q.ordinal===result.ordinal);if(!q||!base.legal(result.route,this.owners))throw Error('State action illegal');return {q,route:result.route};
 }
 result(){const r=super.result();return {...r,action_generation:'STATE001_G001',routing_contract:{...r.routing_contract,classification_routes:['classification_CPU','classification_GPU','classification_NPU'],method:'Same mask/deadlines; STATIC vs public-state candidate cost forecasts; FIFO/EDF/ATC ordering',public_phase_prefix_only:true,new_RL:0},evidence:{...r.evidence,priority_transfer:'Urgent detection uses existing measured normal-detection phase vector and output_ready response; post/release remain unchanged',state_forecast:'Estimated owner residual and same frozen physics; not actual future observation',new_RL:0}};}
}
module.exports={...base,Simulator:StateSimulator,StateSimulator};
