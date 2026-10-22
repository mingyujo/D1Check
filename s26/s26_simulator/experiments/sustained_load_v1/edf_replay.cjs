'use strict';
// Stored-state induction: never rerun the consumed preflight-failed EDF environment.
const assert=require('node:assert/strict'),C=require('./common.cjs'),{path}=C;
const op=C.read(path.join(C.HERE,'OPERATION.json'));C.verify(op);
const row=C.read(path.join(op.output,'prepared/P0_CENTRAL_ATC.json')),raw=C.read(row.raw_path),sim=raw.simulation;
const reference=C.read(op.cases.find(s=>s.id==='P0_CENTRAL_EDF').old_raw),by=new Map(reference.requests.map(q=>[q.ordinal,q]));let checks=0,forecasts=0;
for(const q of sim.requests){const r=by.get(q.ordinal);assert.equal(q.route,r.route);assert.ok(Math.abs(q.response-r.response)<1e-8);checks+=2;for(const k of Object.keys(r.times))if(r.times[k]!==null){assert.ok(Math.abs(q.times[k]-r.times[k])<1e-8);checks++;}}
const packet=C.read(C.packetPath),actions=require('./source/multi_actions.cjs'),nom=require('./source/multi_timing.cjs').nominal(packet);
for(const d of sim.policy_decisions){
 const obs={...d.public_observation,cost_state:{...d.public_observation.cost_state,activity9:{intervals:sim.activity.map(xs=>xs.filter(x=>x[0]<d.time).map(([l,r,w])=>[l,Math.min(r,d.time),w]))}}};
 assert.equal(C.sha(Buffer.from(JSON.stringify(obs))),d.action.public_digest);
 const a=actions.select(obs,packet,nom,{...raw.spec.config,policy:'EDF'});forecasts+=a.forecast_calls;
 assert.equal(a.ordinal,d.action.ordinal);assert.equal(a.route,d.action.route);checks+=3;
}
assert.ok(forecasts+60<=1000);
const proof={status:'PURE_EDF_ACTION_INDUCTION_PASS',actual_completed_ATC_reference:'P0_CENTRAL_ATC',matched_saved_EDF_requests:sim.requests.length,public_states:sim.policy_decisions.length,checks,forecasts,induction:'Identical initial packet/stream, deterministic engine and every action; policy name is used only by ordering. New ATC clock/route trace equals saved EDF, and EDF selects the same action on every new ATC public state.',actual_EDF_environment_retry:false,preserved_failed_identity:'P0_CENTRAL_EDF',new_policy_environments:0,new_fit:0,new_RL:0};
C.write(path.join(op.output,'RECOVERY_EDF_PURE_PROOF.json'),proof);console.log(JSON.stringify(proof));
