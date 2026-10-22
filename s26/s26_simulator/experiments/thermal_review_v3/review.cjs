'use strict';
// Saved-artifact postprocessing only: no simulator, optimizer, device, or Python process.
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto'),z=require('node:zlib');
const H=__dirname,R=path.resolve(H,'../..'),out=path.join(H,'artifacts/G001');
const {steps,coupled,policySupport}=require('./cascade.cjs');
const sha=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
const read=p=>JSON.parse((p.endsWith('.gz')?z.gunzipSync(fs.readFileSync(p)):fs.readFileSync(p)).toString('utf8').replace(/^\uFEFF/,''));
const write=(p,x)=>fs.writeFileSync(p,JSON.stringify(x,null,2)+'\n',{flag:'wx'});
const at=(dir,file)=>path.join(R,'experiments',dir,file),g=(dir,file)=>at(dir,'artifacts/G001/'+file);
if(fs.existsSync(out)||fs.existsSync(path.join(H,'OPERATION.json')))throw Error('Consumed postprocessing namespace');
const oldPower=at('thermal_balance_v2','SAVED_POWER_RESULT.json'),oldOp=read(at('thermal_balance_v2','SAVED_POWER_OPERATION.json'));
const raw=oldOp.pins.filter(x=>x.path.endsWith('.json.gz')&&x.path.includes('SUSTAINED_G001_'));
const files=[__filename,path.join(H,'cascade.cjs'),at('capacity_power_v1','replay.cjs'),g('capacity_power_v1','MODEL.json'),g('pipeline_thermal_v1','MODEL.json'),g('pipeline_thermal_v1','RESULT.json'),g('pipeline_thermal_v1','AUDIT.json'),g('capacity_power_v1','AUDIT.json'),g('thermal_balance_v1','MARGINAL_SUPPORT.json'),at('multiresource_v1','PACKET.json.gz'),oldPower,at('thermal_balance_v2','SAVED_POWER_OPERATION.json'),...raw.map(x=>x.path)];
const op={schema:'S26_EXISTING_DATA_FINAL_THERMAL_REVIEW_V3',utc:new Date().toISOString(),pins:files.map(p=>({path:path.relative(R,p).replaceAll('\\','/'),sha256:sha(p)})),new_fit:0,new_policy_environments:0,new_RL:0,new_measurements:0,heavy_worker:false,scope:'Small saved-artifact arithmetic only; global Python worker count unchanged. No new policy evaluation.'};
write(path.join(H,'OPERATION.json'),op);fs.mkdirSync(out,{recursive:true});
try{
 const pm=read(g('capacity_power_v1','MODEL.json')),tm=read(g('pipeline_thermal_v1','MODEL.json')),gate=read(g('pipeline_thermal_v1','RESULT.json'));
 const packet=read(at('multiresource_v1','PACKET.json.gz')),targets=packet.scenarios.find(s=>s.context_index===0).context.initial_context.targets;
 const baseline=targets.POWER_API.baseline.median_api_w,skin=targets.AP.anchor.SKIN,limits=read(g('thermal_balance_v1','MARGINAL_SUPPORT.json')).limits;
 const prior=read(oldPower),rows=[],curves=[];let checks=0,maxPowerError=0,maxPulseError=0;
 // Independent composite Simpson integration of analytic pulse power, including repeated tau.
 const intervals=Array.from({length:9},()=>[]);intervals[5]=[[0,20,3]];intervals[6]=[[0,20,3]];
 const toyPower={coef:[1,0,...Array(20).fill(.1)],scale:Array(22).fill(1)},toyThermal={tau_fast_s:10,tau_slow_s:320,w_fast:.4,delta_C:0,gain_fast:1,gain_slow:2};
 const pulse=t=>1+.2*(Math.min(1,Math.max(0,t/.5))-Math.min(1,Math.max(0,(t-20)/.5))+[1,10,60].reduce((s,tau)=>s+(t<=20?-Math.expm1(-t/tau):Math.exp(-(t-20)/tau)-Math.exp(-t/tau)),0));
 function integrate(f,t){let sum=0;const knots=[0,...[.5,20,20.5].filter(x=>x<t),t];for(let k=1;k<knots.length;k++){const a=knots[k-1],b=knots[k],n=Math.max(200,2*Math.ceil((b-a)/.002)),h=(b-a)/n;let s=f(a)+f(b);for(let j=1;j<n;j++)s+=(j%2?4:2)*f(a+j*h);sum+=h*s/3;}return sum;}
 const times=[.25,.5,1,10,20,21,60,300],pred=coupled(steps(intervals),times,.6,0,31,30,toyPower,toyThermal);
 for(let j=0;j<times.length;j++){
  const t=times[j],expected=30+.4*Math.exp(-t/10)+.6*Math.exp(-t/320)+integrate(u=>Math.exp(-(t-u)/10)*(pulse(u)-.6)/10,t)+2*integrate(u=>Math.exp(-(t-u)/320)*(pulse(u)-.6)/320,t);
  maxPulseError=Math.max(maxPulseError,Math.abs(pred[j][0]-pulse(t)),Math.abs(pred[j][1]-expected),Math.abs(pred[j][2]-30-integrate(pulse,t)));checks+=3;
 }
 if(maxPulseError>1e-8)throw Error('Independent pulse integration failed');
 const powerReplay=require('../capacity_power_v1/replay.cjs');
 for(const pin of raw){
  if(sha(pin.path)!==pin.sha256)throw Error('Changed saved case');
  const saved=read(pin.path),sim=saved.simulation,times=sim.curve.map(x=>x[0]),st=steps(sim.activity.intervals||sim.activity);
  const curve=coupled(st,times,baseline,times[0],sim.curve[0][1],skin,pm,tm),powers=curve.map(x=>x[0]),temps=curve.map(x=>x[1]);
  const independent=powerReplay.predict(powerReplay.features(st,times,baseline),pm);
  for(let j=0;j<times.length;j++){maxPowerError=Math.max(maxPowerError,Math.abs(independent[j]-powers[j]));checks++;}
  const name=path.basename(pin.path).replace('SUSTAINED_G001_','').replace('.json.gz',''),pr=prior.rows.find(r=>r.case===name);
  rows.push({case:name,old_curve_peak_AP_C:Math.max(...sim.curve.map(x=>x[1])),old_predicted_power_peak_API_W:pr.predicted_power_peak_API_W,thermal_only_peak_AP_C:pr.diagnostic_two_RC_peak_AP_C,
    diagnostic_capacity_power_peak_API_W:Math.max(...powers),diagnostic_pipeline_peak_AP_C:Math.max(...temps),diagnostic_pipeline_end_AP_C:temps.at(-1),diagnostic_API_J:curve.at(-1)[2]-curve[0][2],
    ...policySupport({powerRange:[Math.min(...powers),Math.max(...powers)],temperatureRange:[Math.min(...temps),Math.max(...temps)],limits,accuracyGate:gate.accuracy_gate_pass,jointValidated:false})});
  curves.push({case:name,sample_dt_s:.5,columns:['time_s','power_API_W','AP_C','cumulative_API_J_from_minus30'],rows:curve.map((r,j)=>[times[j],...r])});
 }
 if(maxPowerError>1e-7)throw Error('Independent power disagreement');
 // Limiting input calculation demonstrates finite equilibrium without a temperature clamp.
 const c=pm.coef.map((x,j)=>x/pm.scale[j]),powerUpper=c[0]+baseline*c[1]+c.slice(2).reduce((s,x)=>s+x,0),idle=skin+tm.delta_C;
 const upper=idle+(tm.gain_fast+tm.gain_slow)*(powerUpper-baseline);
 const constant=[[-30,Array(5).fill(0)],[0,Array(5).fill(1)]],saturation=coupled(constant,[0,3600,7200],baseline,0,31.1,skin,pm,tm);
 if(Math.abs(saturation.at(-1)[1]-upper)>1e-6)throw Error('Finite equilibrium mismatch');checks++;
 const rejected=policySupport({powerRange:[.6,1],temperatureRange:[30,40],limits,accuracyGate:false,jointValidated:false});
 if(rejected.status!=='UNSUPPORTED_FOR_POLICY_COMPARISON'||rejected.reasons.length!==2||rows.some(r=>r.policy_temperature_C!==null))throw Error('Failed accuracy gate accepted');checks++;
 for(const pin of op.pins)if(sha(path.join(R,pin.path))!==pin.sha256)throw Error('Pin changed '+pin.path);
 const result={status:'FIXED_ACTIVITY_DIAGNOSTIC_ONLY_NOT_ADOPTED',rows,limits,baseline_API_W:baseline,skin_C:skin,initialization:'Saved curve t0 AP, zero latent heat at t0; power history from t=-30. Earlier latent heat is unobserved. All activity timings, routing, responses and deadlines are held fixed.',
   sampled_peaks_only:true,model_all_five_proxies_held_at_one:{power_limit_API_W:powerUpper,AP_equilibrium_C:upper,physical_cap:false,reachable_joint_state_verified:false,reason:'Finite does not mean supported or safe; this limiting input still exceeds observed AP range. No clipping or invented throttling.'},
   accuracy_gate_pass:gate.accuracy_gate_pass,adopted:false,new_fit:0,new_policy_environments:0,new_RL:0,new_measurements:0};
 write(path.join(out,'RESULT.json'),result);fs.writeFileSync(path.join(out,'CURVES.json.gz'),z.gzipSync(Buffer.from(JSON.stringify(curves))),{flag:'wx'});
 write(path.join(out,'AUDIT.json'),{status:'PASS_MATH_AND_REJECTION_ONLY',checks,max_independent_Simpson_error:maxPulseError,max_independent_power_error:maxPowerError,physical_validation:false});
 write(path.join(out,'FINAL_PROOF.json'),{status:'SAVED_DIAGNOSTIC_AND_GATE_COMPLETE',operation_sha256:sha(path.join(H,'OPERATION.json')),artifacts:Object.fromEntries(['RESULT.json','CURVES.json.gz','AUDIT.json'].map(n=>[n,sha(path.join(out,n))])),new_fit:0,new_policy_environments:0});
 console.log(JSON.stringify({rows,checks,maxPulseError,maxPowerError,finite_limiting_AP_C:upper}));
}catch(error){write(path.join(out,'FAILURE.json'),{error:String(error.stack||error),automatic_retry:false});throw error;}
