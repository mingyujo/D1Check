'use strict';
// Small saved-data diagnostic only; no model fit, environment or policy execution.
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto'),z=require('node:zlib');
const HERE=__dirname,ROOT=path.resolve(HERE,'../..'),P=path.join(ROOT,'experiments/multiresource_v1/calibration'),S=path.join(ROOT,'experiments/sustained_load_v1');
const sha=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex'),pin=p=>({path:p,sha256:sha(p)});
const read=p=>JSON.parse((p.endsWith('.gz')?z.gunzipSync(fs.readFileSync(p)):fs.readFileSync(p)).toString('utf8').replace(/^\uFEFF/,''));
const write=(p,v)=>fs.writeFileSync(path.join(HERE,p),JSON.stringify(v)+'\n',{flag:'wx'});
const names=['SHORT_CENTRAL_EDF','LONG64_CENTRAL_EDF','LONG64_CENTRAL_ATC','LONG256_LOW_ATC'];
const mathPath=path.join(S,'source/dynamic_cost_math_v2.cjs');
const op={schema:'S26_POST_WALL_DOMAIN_DIAGNOSIS_V1',utc:new Date().toISOString(),pins:[__filename,mathPath,path.join(P,'MATERIALIZED_SESSIONS.json.gz'),path.join(P,'results/OOF_ROWS.json'),...names.map(n=>path.join(S,'artifacts/G001/raw/SUSTAINED_G001_'+n+'.json.gz'))].map(pin),new_fit:0,new_policy_environments:0,new_RL:0};
write('DOMAIN_DIAGNOSIS_OPERATION_V2.json',op);
const math=require(mathPath),ss=read(path.join(P,'MATERIALIZED_SESSIONS.json.gz')),rows=new Map(read(path.join(P,'results/OOF_ROWS.json')).filter(r=>r.target==='AP').map(r=>[r.id,r]));
let maxPost=-Infinity,maxAbsolutePost=-Infinity,maxRecord=null;const spans=[];
for(const s of ss){const r=rows.get(s.session_uid||s.id);if(!r)continue;
 const a=s.targets.AP.anchor,anchor=a.time_s??a.t_s,za=math.stateSeries(s.activity9.intervals,[anchor],.06,-30)[0][5],states=math.stateSeries(s.activity9.intervals,r.times,.06,-30);
 for(let j=0;j<r.times.length;j++)if(states[j][5]-za>maxPost){maxPost=states[j][5]-za;maxRecord={id:r.id,group:r.group,time_s:r.times[j],anchored_POST_state:maxPost};}
 for(const state of states)maxAbsolutePost=Math.max(maxAbsolutePost,state[5]);
 const all=s.activity9.intervals.slice(0,6).flat().filter(x=>x[1]>0);
 spans.push({id:r.id,group:r.group,observed_end_s:r.times.at(-1),phase_wall_span_s:all.length?Math.max(...all.map(x=>x[1]))-Math.max(0,Math.min(...all.map(x=>x[0]))):0,
  post_wall_integral_s:s.activity9.intervals[5].reduce((sum,[a,b,w])=>sum+Math.max(0,b-Math.max(0,a))*w,0)});
}
const comparisons=names.map(n=>{
 const raw=read(path.join(S,'artifacts/G001/raw/SUSTAINED_G001_'+n+'.json.gz')),r=raw.simulation;
 if(!r.curve.length||r.curve.some(x=>!Array.isArray(x)||x.length!==3||x.some(v=>!Number.isFinite(v))))throw Error('Stored curve ABI must be [time,AP,power]');
 const peak=r.curve.reduce((a,b)=>b[1]>a[1]?b:a),t=peak[0];
 const states=math.stateSeries(r.activity,[t],.06,-30)[0];
 let cpuPost=0,cpuInfer=0,totalCPU=0;for(const x of r.cpu_intervals){const dt=x.end-x.start;totalCPU+=dt;if(x.phase==='POST')cpuPost+=dt;if(x.phase==='INFER')cpuInfer+=dt;}
 const postWall=r.activity[5].reduce((sum,[a,b,w])=>sum+Math.max(0,b-Math.max(0,a))*w,0);
 if(!Number.isFinite(states[5]))throw Error('Missing POST state');
 return {case:n,stored_curve_peak_time_s:t,stored_curve_peak_AP_C:peak[1],POST_state_at_peak:states[5],
  relative_to_max_measured_absolute_POST_state:states[5]/maxAbsolutePost,post_wall_integral_owner_s:postWall,
  modelled_CPU_POST_service_s:cpuPost,modelled_total_CPU_service_s:totalCPU,modelled_CPU_infer_service_s:cpuInfer,
  shared_CPU_wait_owner_s:r.shared_cpu_wait_s,POST_wall_to_modelled_CPU_POST_ratio:cpuPost?postWall/cpuPost:null,
  note:'CPU service follows frozen LOW/CENTRAL assumptions, not measured core utilization. POST state comparison at saved samples; no physical heat decomposition.'};
});
for(const p of op.pins)if(sha(p.path)!==p.sha256)throw Error('Changed pin');
const result={status:'SAVED_INPUT_DOMAIN_DIAGNOSIS_COMPLETE',max_POST_state_at_eligible_measured_AP_times:maxRecord,comparisons,
 max_absolute_POST_state_at_eligible_measured_AP_times:maxAbsolutePost,
 recorded_AP_sessions_ending_after256:spans.filter(s=>s.observed_end_s>=256).length,measured_phase_span_over256_sessions:spans.filter(s=>s.phase_wall_span_s>=256).length,
 longest_phase_spans:spans.sort((a,b)=>b.phase_wall_span_s-a.phase_wall_span_s).slice(0,5),
 warning:'Long recorded sessions exist; they do not establish the new shared-CPU waiting or triple-resource joint domain.',
 predecessor:'V1 preserved; helper expected object curve but stored ABI is numeric triplets. Peak fields were missing/null. No model fit/environment or original result changed.',
 operation_sha256:sha(path.join(HERE,'DOMAIN_DIAGNOSIS_OPERATION_V2.json')),new_fit:0,new_policy_environments:0,new_RL:0};
write('DOMAIN_DIAGNOSIS_V2.json',result);console.log(JSON.stringify(result));
