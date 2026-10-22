'use strict';
const fs=require('fs'),path=require('path'),z=require('zlib'),assert=require('node:assert/strict');
const H=__dirname,S=path.resolve(H,'../..'),F=path.join(S,'experiments/rolling_rl_ablation_v1'),G=path.join(S,'experiments/route_group_learning_v1');
const read=p=>JSON.parse((p.endsWith('.gz')?z.gunzipSync(fs.readFileSync(p)):fs.readFileSync(p)).toString('utf8').replace(/^\uFEFF/,''));
const clone=x=>JSON.parse(JSON.stringify(x)),clean=x=>JSON.stringify(x);
const original=require(path.join(G,'policy.cjs')),derived=require('./policy.cjs'),{teacher}=require('../teacher_components_20261019/helpers.cjs');
const packet=read(path.join(S,'experiments/multiresource_v1/PACKET.json.gz'));packet.multi.models.CPU3={...packet.multi.models.CENTRAL,cpu_workers:3};
const nom=require(path.join(G,'source/multi_timing.cjs')).nominal(packet),protocol=read(path.join(H,'PROTOCOL.json'));
const config={model:'CPU3',capacity:3,dispatch_stop_s:500,power_model:read(path.join(S,'experiments/capacity_power_v1/artifacts/G001/MODEL.json')),thermal_model:read(path.join(S,'experiments/pipeline_thermal_v1/artifacts/G001/MODEL.json'))};
const row=read(path.join(F,'artifacts/G001/RESULT.json')).rows.find(r=>r.method==='TEACHER_RULE'),raw=read(path.join(F,'artifacts/G001',row.label+'.raw.json.gz'));
const observations=raw.policy_decisions.filter(d=>d.public_observation).map(d=>d.public_observation),fixtures=[];
for(const i of [0,1,10,100,500,900]){const o=clone(observations[i]);o.cost_state.activity9={intervals:raw.activity.map(xs=>xs.filter(x=>x[0]<o.time).map(([s,e,w])=>[s,Math.min(e,o.time),w]))};fixtures.push(o);}
for(const n of [1,4,8,12,24,40]){const o=clone(fixtures[0]);o.ready=Array.from({length:n},(_,i)=>({ordinal:10000+i,task:i%3?'classification':'detection',priority:i%3?'urgent':'normal',arrival:o.time-.001*(n-i),deadline:o.time+(i%3?.8:2)+(i%4)*.02}));fixtures.push(o);}
const tied=clone(fixtures.at(-1));tied.ready.forEach(q=>q.deadline=tied.time-40);fixtures.push(tied);
let checks=0;const need=(v,s)=>{checks++;assert.ok(v,s);};
function run(mod,o,rolling,ATC,standalone=false){let bank;mod.configure({mode:'MATCHED_ROLLING',variant:'REPAIR',useRolling:rolling,useATC:ATC,standalone,balance:{scales:protocol.shared_scores.scales,dual:[.98,.98],classFactors:[1,1],tail:.02,rank_feature:true},choose:b=>{bank=clone(b);return teacher(b);}});const action=mod.select(clone(o),packet,nom,config);return {bank,action,telemetry:mod.telemetry?.()};}
for(const o of fixtures){
 const old=run(original,o,true,true),full=run(derived,o,true,true),nr=run(derived,o,false,true),na=run(derived,o,true,false),both=run(derived,o,false,false),pure=run(derived,o,false,false,true);
 need(clean(old.bank)===clean(full.bank),'Full32 feature bank byte-compatible with original');need(clean(old.action)===clean(full.action),'Full selected action byte-compatible');
 need(clean(full.bank?.actions)===clean(nr.bank?.actions),'No-rolling retains original candidate actions');
 for(let i=0;i<(nr.bank?.actions.length??0);i++)for(let k=0;k<32;k++)need(nr.bank.x[i][k]===(k>=21&&k<=29?0:full.bank.x[i][k]),'Only forecast feature range removed');
 need(clean(na.bank?.actions)===clean(both.bank?.actions),'NoATC candidate set independent of rolling');
 need(nr.telemetry.rollout_calls===0&&both.telemetry.rollout_calls===0,'No rolling calls');need(na.telemetry.ATC_evaluations===0&&both.telemetry.ATC_evaluations===0,'No ATC calculations');
 need(pure.telemetry.nominal_timing_calls===0&&pure.telemetry.rollout_calls===0,'Pure teacher no planner/timing');
 if(na.bank)need(na.bank.x.every(x=>x[11]===0),'ATC feature zero');
}
// Actual forbidden rollout call must throw, even if instrumentation were wrong.
const roll=require(path.join(G,'source/nominal_rollout.cjs')),saved=roll.rollout;roll.rollout=()=>{throw Error('FORBIDDEN_ROLLOUT');};delete require.cache[require.resolve('./policy.cjs')];const guarded=require('./policy.cjs');
for(const o of fixtures){run(guarded,o,false,true);run(guarded,o,false,false);checks+=2;}roll.rollout=saved;
const out={status:'PASS',utc:new Date().toISOString(),fixtures:fixtures.length,checks,new_environments:0,full_bank_exact:true,no_rolling_preserves_nonforecast_features:true,forbidden_rollout_guard:true,crowded_ready_max:40};
fs.writeFileSync(path.join(H,'PREFLIGHT_ABI.json'),JSON.stringify(out,null,2)+'\n',{flag:'wx'});process.stdout.write(JSON.stringify(out)+'\n');
