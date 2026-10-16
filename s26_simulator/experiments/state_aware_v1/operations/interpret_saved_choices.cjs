'use strict';
const fs=require('fs'),path=require('path'),crypto=require('crypto');const O=__dirname,B=path.resolve(O,'../..'),D=path.join(B,'work/S26-GITHUB-HANDOFF-20261016/repository/s26_simulator/experiments/state_aware_v1');
const read=f=>JSON.parse(fs.readFileSync(f,'utf8').replace(/^\uFEFF/,'')),digest=x=>crypto.createHash('sha256').update(JSON.stringify(x)).digest('hex');
if(read(path.join(O,'AUDIT_FAST_V1/RESULT.json')).status!=='PASS')throw Error('Full audit required');
const rows=fs.readFileSync(path.join(O,'PRODUCTION/ROWS.jsonl'),'utf8').trim().split(/\r?\n/).map(JSON.parse).filter(x=>x.phase==='STATE_MAIN');
const result={status:'PASS',source:'Post-audit descriptive inspection only; no policy change or new simulator',main_conditions:48,EDF_ATC_STATE_identical_physical_traces:0,classification_choices:0,GPU_NPU_both_forecast:0,GPU_lower_score:0,GPU_lower_J_higher_AP_area:0,GPU_lower_both_J_AP_area:0,GPU_negative_marginal_J:0,min_delivered_AP:null,max_delivered_AP:null,new_policy_environments:0,new_fit:0,new_RL:0};
for(const row of rows.filter(x=>x.config.policy==='ATC_STATE')){
 const own=read(row.raw_path),other=rows.find(x=>x.config.policy==='EDF_STATE'&&x.config.scenario===row.config.scenario&&x.config.stream===row.config.stream);
 if(!other)throw Error('Missing matched EDF');const edf=read(other.raw_path);
 const trace=r=>({events:r.events.map(e=>e.slice(0,4)),activity:r.activity,curve:r.curve,service:r.service});
 if(digest(trace(own))===digest(trace(edf)))result.EDF_ATC_STATE_identical_physical_traces++;
 for(const d of own.policy_decisions){const a=d.action;if(a.kind!=='DISPATCH'||!a.route.startsWith('classification'))continue;result.classification_choices++;const ap=d.public_observation.sensor.AP;result.min_delivered_AP=result.min_delivered_AP===null?ap:Math.min(ap,result.min_delivered_AP);result.max_delivered_AP=result.max_delivered_AP===null?ap:Math.max(ap,result.max_delivered_AP);
  const g=a.candidates.find(x=>x.ordinal===a.ordinal&&x.route==='classification_GPU'&&x.permitted)?.state_forecast,n=a.candidates.find(x=>x.ordinal===a.ordinal&&x.route==='classification_NPU'&&x.permitted)?.state_forecast;if(!g||!n)continue;result.GPU_NPU_both_forecast++;result.GPU_lower_score+=Number(g.normalized_energy_heat<n.normalized_energy_heat);result.GPU_lower_J_higher_AP_area+=Number(g.incremental_J<n.incremental_J&&g.incremental_AP_area>n.incremental_AP_area);result.GPU_lower_both_J_AP_area+=Number(g.incremental_J<n.incremental_J&&g.incremental_AP_area<n.incremental_AP_area);result.GPU_negative_marginal_J+=Number(g.incremental_J<0);
 }
}
if(result.EDF_ATC_STATE_identical_physical_traces!==48)throw Error('Inspect nonidentical traces before claiming equality');
fs.writeFileSync(path.join(O,'SAVED_CHOICE_INTERPRETATION.json'),JSON.stringify(result,null,2)+'\n',{flag:'wx'});fs.copyFileSync(path.join(O,'SAVED_CHOICE_INTERPRETATION.json'),path.join(D,'SAVED_CHOICE_INTERPRETATION.json'),fs.constants.COPYFILE_EXCL);fs.copyFileSync(__filename,path.join(D,'operations/interpret_saved_choices.cjs'),fs.constants.COPYFILE_EXCL);console.log(JSON.stringify(result));
