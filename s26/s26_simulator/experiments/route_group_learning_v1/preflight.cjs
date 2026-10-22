'use strict';
// Public nominal bank calculations on saved TRAIN snapshots only. No plant run.
const fs=require('fs'),path=require('path'),z=require('zlib'),H=__dirname,R=path.resolve(H,'../..'),read=p=>JSON.parse((p.endsWith('.gz')?z.gunzipSync(fs.readFileSync(p)):fs.readFileSync(p)).toString('utf8').replace(/^\uFEFF/,''));
const packet=read(path.join(R,'experiments/multiresource_v1/PACKET.json.gz')),pm=read(path.join(R,'experiments/capacity_power_v1/artifacts/G001/MODEL.json')),tm=read(path.join(R,'experiments/pipeline_thermal_v1/artifacts/G001/MODEL.json'));packet.multi.models.CPU3={...packet.multi.models.CENTRAL,cpu_workers:3};
const policy=require('./policy.cjs'),timing=require('./source/multi_timing.cjs'),nom=timing.nominal(packet),raw=read(path.join(R,'experiments/route_witness_pilot_v1/artifacts/G001/TRAIN_DIAGNOSIS_CPU3_0_SPLIT75.raw.json.gz'));
const candidates=raw.policy_decisions.filter(d=>d.public_observation&&d.public_observation.ready.length>0),samples=[candidates[0],...candidates.filter(d=>d.public_observation.owners.length>0&&d.public_observation.ready.some(q=>q.task==='classification')).filter((d,i)=>i%100===0).slice(0,5)];let banks=0,eventBanks=0,checks=0;
for(const d of samples){const obs=structuredClone(d.public_observation);obs.cost_state.activity9={intervals:raw.activity.map(xs=>xs.filter(([a,b])=>a<obs.time&&b>0).map(([a,b,v])=>[a,Math.min(b,obs.time),v]))};
 policy.configure({mode:'DEMO',variant:'REPAIR',balance:{scales:[.7,.8],dual:[1,1],classFactors:[2,2],tail:.02},choose:bank=>{
  banks++;if(bank.actions.length>27)throw Error('Bank capacity');
  for(let i=0;i<bank.actions.length;i++){if(bank.x[i].some(x=>!Number.isFinite(x)))throw Error('Nonfinite feature');if(![-1,0,1].includes(bank.x[i][31]))throw Error('Preference/event feature');if(bank.forecasts[i].nominal_failure)throw Error('Nominal event/route continuation failed');checks+=3;}
  const event=bank.actions.findIndex(a=>a.kind==='WAIT_EVENT');if(event>=0){eventBanks++;if(!obs.owners.length||bank.x[event][31]!==-1)throw Error('Event physical definition');return event;}
  const first=bank.actions.findIndex((a,i)=>a.kind==='DISPATCH'&&bank.x[i][31]===1);if(first<0)throw Error('Initial preferred dispatch missing');return first;
 }});
 policy.select(obs,packet,nom,{model:'CPU3',power_model:pm,thermal_model:tm,dispatch_stop_s:raw.dispatch_stop_s});
}
if(!eventBanks||banks!==samples.length)throw Error('Event preflight coverage');
const proof={status:'PASS_SAVED_PUBLIC_EVENT_BANK_PREFLIGHT',banks,eventBanks,checks,new_environment:0,new_training:0,new_fits:0,source:'TRAIN-only route pilot snapshots; activity clamped to observation time, no actual future work/arrival events exposed.'};fs.writeFileSync(path.join(H,'PREFLIGHT_PUBLIC_BANK.json'),JSON.stringify(proof,null,2)+'\n',{flag:'wx'});console.log(JSON.stringify(proof));
