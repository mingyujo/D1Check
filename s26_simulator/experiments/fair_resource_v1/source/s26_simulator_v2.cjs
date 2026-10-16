'use strict';
// Same source-bound physical plant as SIM001; this generation repairs the action interface.
const base=require('./s26_simulator.cjs'),actions=require('./rolling_action_v2.cjs');
const OWN_POLICY='ROLLING_ATC_ROUTE_V2';
const SUPPORTED=['FIFO_SERIAL_CPU_V2','FIFO_SERIAL_CG_V1','EDD_SERIAL_CG_V1','FIFO_PAIR_CG_V1','EDF_PAIR_CG_V1','FIFO_WAIT_CG_V1','FIFO_SERIAL_CN_V1','FIFO_PAIR_CN_V1',OWN_POLICY];
function validatePolicy(p){if(!SUPPORTED.includes(p))throw Error('Unimplemented policy ID: '+p);return p}
class ResourceSimulator extends base.Simulator{
 constructor(packet,scenario,config={}){
  validatePolicy(config.policy??scenario.policy);super(packet,scenario,config);
  this.decisionTrace=[];this.lastDecisionKey=null;
  if((config.policy??scenario.policy)===OWN_POLICY)this.publicNominalModel=actions.publicNominals(packet,scenario);
 }
 publicObservation(){return {time:this.time,
   ready:this.ready.map(q=>({ordinal:q.ordinal,task:q.task,priority:q.priority,arrival:q.arrival,deadline:q.deadline})),
   owners:this.owners.map(o=>({route:o.route,dispatch:o.times.dispatch})),
   sensor:{AP:this.heldAP,time:this.heldTime},sensor_history:this.sensorTrace.map(x=>({AP:x.AP,time:x.time})),
   initial_AP:this.anchorAP,wait_used_s:this.waitDose};}
 choose(){
  const policy=this.config.policy??this.scenario.policy;
  if(policy==='FIFO_SERIAL_CPU_V2'){
   if(!this.ready.length||this.owners.length||this.time>=120-1e-9)return null;
   const q=this.ready.slice().sort((a,b)=>a.arrival-b.arrival||a.ordinal-b.ordinal)[0];return {q,route:q.task==='detection'?'detection_CPU':'classification_CPU'};
  }
  if(policy!==OWN_POLICY)return super.choose();
  if(!this.ready.length||this.time>=120-1e-9)return null;
  const obs=this.publicObservation(),key=JSON.stringify([obs.ready.map(q=>q.ordinal),obs.owners,obs.sensor.time]);
  if(this.lastDecisionKey===key)return null;this.lastDecisionKey=key;
  const result=actions.select(obs,this.publicNominalModel,this.config.action_options??{});
  if(result.kind==='NONE')return null;
  this.decisionTrace.push({time:this.time,public_observation:obs,action:result});
  if(result.kind==='WAIT'){
   if(this.owners.length)throw Error('WAIT cannot stop an owner');this.waitDose+=result.dose_s;this.waitUntil=Math.min(120,this.time+result.dose_s);this.lastDecisionKey=null;this.events.push([this.time,'WAIT_START',null,this.waitUntil-this.time]);return 'WAIT';
  }
  const q=this.ready.find(x=>x.ordinal===result.ordinal);if(!q||!base.legal(result.route,this.owners))throw Error('Invalid dynamic action');return {q,route:result.route};
 }
 result(){const r=super.result(),counts=Object.fromEntries(actions.ROUTES.map(route=>[route,r.requests.filter(q=>q.route===route).length]));
  return {...r,action_generation:'SIM002_G001',policy_decisions:this.decisionTrace,policy_route_counts:counts,
   public_nominal_model:this.publicNominalModel??null,
   routing_contract:{policy:r.policy,classification_routes:r.policy===OWN_POLICY?this.config.action_options?.classification_routes??actions.ROUTES.slice(0,3):null,detection_route:'detection_CPU',pairs:actions.PAIRS,nonpreemptive:true,maximum_owners:2,public_observation_only:true,new_RL:0,
    method:'Untrained rolling ATC heuristic with request-level route decisions; not PPO/RL result',
    physical_source:'Same immutable SIM001 plant, coefficients, timing, phase-residual transfer and API assumptions; conditional phase repair not yet adopted',
    limitation:'Nominal deadline screen and single-job cost proxies do not guarantee realized feasibility or physical savings'},
   evidence:{...r.evidence,resource_selection:r.policy===OWN_POLICY?'Each arrived classification request considers CPU/GPU/NPU; supported mask is applied at dispatch':'Fixed-reference or P0 policy',new_RL:0}};
 }
}
module.exports={...base,ResourceSimulator,Simulator:ResourceSimulator,validatePolicy,SUPPORTED,OWN_POLICY};
