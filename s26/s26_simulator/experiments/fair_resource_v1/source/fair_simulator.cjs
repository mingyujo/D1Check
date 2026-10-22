'use strict';
const base = require('./s26_simulator_v2.cjs'), actions = require('./fair_actions.cjs');
class FairSimulator extends base.ResourceSimulator {
  constructor(packet,scenario,config) {
    if (!actions.POLICIES.includes(config.policy)) throw Error('Unknown fair policy');
    super(packet,scenario,{...config,policy:base.OWN_POLICY});
    this.config = {...this.config,...config};
  }
  choose() {
    if (!this.ready.length || this.time >= 120-1e-9) return null;
    const obs=this.publicObservation(),key=JSON.stringify([obs.ready.map(q=>q.ordinal),obs.owners,obs.sensor.time]);
    if(this.lastDecisionKey===key)return null;this.lastDecisionKey=key;
    const result=actions.select(obs,this.publicNominalModel,this.config.action_options??{},this.config.policy);
    if(result.kind==='NONE')return null;
    this.decisionTrace.push({time:this.time,public_observation:obs,action:result});
    if(result.kind==='WAIT') {
      if(this.owners.length)throw Error('WAIT cannot stop an owner');
      this.waitDose+=result.dose_s;this.waitUntil=Math.min(120,this.time+result.dose_s);this.lastDecisionKey=null;
      this.events.push([this.time,'WAIT_START',null,this.waitUntil-this.time]);return 'WAIT';
    }
    const q=this.ready.find(q=>q.ordinal===result.ordinal);
    if(!q||!base.legal(result.route,this.owners))throw Error('Illegal fair action');return {q,route:result.route};
  }
  result() {
    const r=super.result();
    return {...r,action_generation:'FAIR001_G001',routing_contract:{...r.routing_contract,
      classification_routes:actions.ROUTES.slice(0,3),method:'FIFO/EDF among dispatchable ready requests with the original common deadline/energy/heat route allocator',
      same_nominal_candidates_and_WAIT_as:'ROLLING_ATC_ROUTE_V2'},
      evidence:{...r.evidence,resource_selection:'Same CPU/GPU/NPU, public fields, pair mask, nominal model and WAIT eligibility; request order is FIFO or EDF',new_RL:0}};
  }
}
module.exports = {...base,Simulator:FairSimulator,FairSimulator};
