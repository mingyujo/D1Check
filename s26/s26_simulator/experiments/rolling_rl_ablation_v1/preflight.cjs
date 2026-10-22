'use strict';
const fs=require('fs'),path=require('path'),z=require('zlib'),assert=require('assert'),H=__dirname,R=path.resolve(H,'../..');
const read=p=>JSON.parse((p.endsWith('.gz')?z.gunzipSync(fs.readFileSync(p)):fs.readFileSync(p)).toString('utf8').replace(/^\uFEFF/,''));
const packet=read(path.join(R,'experiments/multiresource_v1/PACKET.json.gz')),pm=read(path.join(R,'experiments/capacity_power_v1/artifacts/G001/MODEL.json')),tm=read(path.join(R,'experiments/pipeline_thermal_v1/artifacts/G001/MODEL.json'));
packet.multi.models.CPU3={...packet.multi.models.CENTRAL,cpu_workers:3};
const old=require('../route_group_learning_v1/policy.cjs'),fresh=require('./policy.cjs'),nom=require('./source/multi_timing.cjs').nominal(packet),protocol=read(path.join(H,'PROTOCOL.json'));
const raw=read(path.join(R,'experiments/route_witness_pilot_v1/artifacts/G001/TRAIN_DIAGNOSIS_CPU3_0_SPLIT75.raw.json.gz'));
const candidates=raw.policy_decisions.filter(d=>d.public_observation&&d.public_observation.ready.length),samples=[candidates[0],...candidates.filter(d=>d.public_observation.owners.length&&d.public_observation.ready.some(q=>q.task==='classification')).filter((d,i)=>i%100===0).slice(0,5)];
let checks=0,eventBanks=0;const fixtures=[];
for(const sample of samples){const obs=structuredClone(sample.public_observation);obs.cost_state.activity9={intervals:raw.activity.map(xs=>xs.filter(([a,b])=>a<obs.time&&b>0).map(([a,b,v])=>[a,Math.min(b,obs.time),v]))};let first,second;
 const cfg={mode:'MATCHED_ROLLING',variant:'REPAIR',balance:{scales:protocol.shared_scores.scales,dual:[.98,.98],classFactors:[1,1],tail:.02,rank_feature:true}};
 const plant={model:'CPU3',power_model:pm,thermal_model:tm,dispatch_stop_s:raw.dispatch_stop_s};
 old.configure({...cfg,choose:b=>{first=structuredClone(b);return b.mask.findIndex(Boolean);}});old.select(structuredClone(obs),packet,nom,plant);
 fresh.configure({...cfg,choose:b=>{second=structuredClone(b);return b.mask.findIndex(Boolean);}});fresh.select(structuredClone(obs),packet,nom,plant);
 for(const k of ['x','mask','actions','forecasts','constraints','forecast_ready','decision_ready','forecast_horizon_s']){assert.deepStrictEqual(second[k],first[k],k);checks++;}
 assert(second.actions.length<=27);assert(second.constraints.deadline_action_mask===false);assert(second.constraints.post_NN_override===false);
 for(let i=0;i<second.actions.length;i++){assert(Number.isFinite(second.scores[i]));assert(second.mask[i]);checks+=2;}
 if(second.actions.some(a=>a.kind==='WAIT_EVENT'))eventBanks++;
 fixtures.push(second);
}
assert(eventBanks>0);fs.writeFileSync(path.join(H,'PREFLIGHT_BANKS.json'),JSON.stringify(fixtures)+'\n',{flag:'wx'});
const proof={status:'PASS',saved_TRAIN_banks:samples.length,eventBanks,checks,unchanged:['candidate order','physical masks','32 features','all forecasts','action definitions','rolling horizons'],only_change:'Expose common causal scores/observed mix to all selectors',new_environment:0,new_training:0};
fs.writeFileSync(path.join(H,'PREFLIGHT.json'),JSON.stringify(proof,null,2)+'\n',{flag:'wx'});console.log(JSON.stringify(proof));
