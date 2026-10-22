'use strict';
// Diagnostic replay on fixed old power paths. No policy/timing/environment rerun.
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto'),z=require('node:zlib');
const HERE=__dirname,ROOT=path.resolve(HERE,'../..'),S=path.join(ROOT,'experiments/sustained_load_v1');
const {advance}=require('../thermal_balance_v1/thermal_rc.cjs');
const read=p=>JSON.parse((p.endsWith('.gz')?z.gunzipSync(fs.readFileSync(p)):fs.readFileSync(p)).toString('utf8').replace(/^\uFEFF/,''));
const sha=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex'),write=(name,v)=>fs.writeFileSync(path.join(HERE,name),JSON.stringify(v)+'\n',{flag:'wx'});
const modelPath=path.join(HERE,'artifacts/G001/MODEL.json'),packetPath=path.join(ROOT,'experiments/multiresource_v1/PACKET.json.gz'),supportPath=path.join(HERE,'../thermal_balance_v1/artifacts/G001/MARGINAL_SUPPORT.json');
const names=['SHORT_CENTRAL_EDF','LONG64_CENTRAL_EDF','LONG64_CENTRAL_ATC','LONG256_LOW_ATC'];
const rawPaths=names.map(n=>path.join(S,'artifacts/G001/raw/SUSTAINED_G001_'+n+'.json.gz'));
const op={schema:'S26_SAVED_POWER_THERMAL_DIAGNOSTIC_V1',utc:new Date().toISOString(),pins:[__filename,modelPath,packetPath,supportPath,path.join(HERE,'../thermal_balance_v1/thermal_rc.cjs'),...rawPaths].map(p=>({path:p,sha256:sha(p)})),new_fit:0,new_policy_environments:0,new_RL:0};
write('SAVED_POWER_OPERATION.json',op);
const m=read(modelPath),packet=read(packetPath),ctx=packet.scenarios.find(s=>s.context_index===0).context.initial_context.targets,limits=read(supportPath).limits;
const rows=rawPaths.map((p,k)=>{
 const raw=read(p),r=raw.simulation,curve=r.curve,AP0=curve[0][1],idle=ctx.AP.anchor.SKIN+m.delta_C,base=ctx.POWER_API.baseline.median_api_w;
 let xf=0,xs=0,peak=AP0,end=AP0;const f={tau_s:m.tau_fast_s,gain_C_per_API_W:1,delta_C:0},s={...f,tau_s:m.tau_slow_s},c={SKIN:0,baseline_API_W:base};
 for(let j=1;j<curve.length;j++){const [t,AP,pw]=curve[j],prev=curve[j-1];xf=advance(xf,prev[2],pw,t-prev[0],c,f);xs=advance(xs,prev[2],pw,t-prev[0],c,s);
  end=idle+(AP0-idle)*(m.w_fast*Math.exp(-t/m.tau_fast_s)+(1-m.w_fast)*Math.exp(-t/m.tau_slow_s))+m.gain_fast*xf+m.gain_slow*xs;peak=Math.max(peak,end);}
 const powerPeak=Math.max(...curve.map(x=>x[2])),powerOK=powerPeak<=limits.power_API_W[1]&&Math.min(...curve.map(x=>x[2]))>=limits.power_API_W[0],temperatureOK=peak<=limits.AP_C[1]&&end>=limits.AP_C[0];
 return {case:names[k],old_curve_peak_AP_C:Math.max(...curve.map(x=>x[1])),diagnostic_two_RC_peak_AP_C:peak,diagnostic_two_RC_end_AP_C:end,
   predicted_power_peak_API_W:powerPeak,power_within_marginal_measurements:powerOK,temperature_within_marginal_measurements:temperatureOK,
   status:'UNSUPPORTED_FOR_POLICY_COMPARISON',policy_temperature_C:null,
   reason:'Fixed old wall-phase power forecast has not been validated for service/waiting/joint sustained state. Diagnostic temperatures are not adopted plant outputs.'};
});
for(const p of op.pins)if(sha(p.path)!==p.sha256)throw Error('Changed pin');
write('SAVED_POWER_RESULT.json',{status:'DIAGNOSTIC_ONLY_NOT_A_POLICY_RESULT',rows,limits,
 initialization:'At saved curve t0 AP; initial SKIN/past baseline context0. Future old predicted power is linearly interpolated from 0.5s saved samples. Prior thermal modes are not identified.',
 scope:'No rerouting, response-time or deadline recalculation. Replacing the thermal equation alone does not validate the old power path.',
 operation_sha256:sha(path.join(HERE,'SAVED_POWER_OPERATION.json')),new_fit:0,new_policy_environments:0,new_RL:0});
console.log(JSON.stringify(rows));
