'use strict';
// Pure equation checks, not requests/episodes, calibration or device data.
const fs=require('fs'),path=require('path'),crypto=require('crypto');
const root=path.resolve(__dirname,'../..'),read=p=>JSON.parse(fs.readFileSync(p)),sha=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
function analyze(c,model){
 const solo=Object.fromEntries(model.supported_states.map((s,i)=>[s,model.coefficients_W_proxy[i]]));
 const H=solo.classification_GPU+solo.detection_CPU-solo['classification_GPU+detection_CPU'];solo.detection_GPU=.6013808404579677;
 const maximumCPU=Math.max(solo.classification_CPU,solo.detection_CPU),maximumGPU=Math.max(solo.classification_GPU,solo.detection_GPU),D=maximumCPU+maximumGPU-2*H;
 const capPower=H+D*(1-c.leakage_fraction+c.leakage_fraction*3),loose=c.idle_c+c.thermal_resistance*capPower;
 const uncapped=T=>H+D*(1-c.leakage_fraction+c.leakage_fraction*Math.exp(c.strength*c.leakage_per_c*(T-c.reference_c)));
 const equilibriumMap=T=>c.idle_c+c.thermal_resistance*uncapped(T);
 if(!(equilibriumMap(loose)<loose&&Math.exp(c.strength*c.leakage_per_c*(loose-c.reference_c))<3))throw Error('Uncapped low-temperature invariant proof failed');
 let a=c.idle_c,b=loose;for(let i=0;i<90;i++){const mid=(a+b)/2;if(equilibriumMap(mid)>mid)a=mid;else b=mid;}
 const upper=b+1e-8,derivativeBound=c.thermal_resistance*D*c.leakage_fraction*c.strength*c.leakage_per_c*Math.exp(c.strength*c.leakage_per_c*(loose-c.reference_c));
 if(!(derivativeBound<1&&equilibriumMap(upper)<=upper))throw Error('Unique stable upper root');
 const cells=[];let steps=0,largest=26;
 for(const cpuTask of ['classification','detection'])for(const gpuTask of ['classification','detection'])for(const cpuExecution of [false,true])for(const gpuExecution of [false,true]){
  let T=26,last=26;const dt=c.tick_s,decay=Math.exp(-dt/c.thermal_tau_s),one=-Math.expm1(-dt/c.thermal_tau_s);
  for(let i=0;i<Math.round(3600/dt);i++){
   const leak=Math.exp(Math.min(Math.log(3),Math.max(-Math.log(3),c.strength*c.leakage_per_c*(T-c.reference_c))));let P=H;
   for(const [task,route,execution,slope] of [[cpuTask,'CPU',cpuExecution,c.cpu_slope],[gpuTask,'GPU',gpuExecution,c.gpu_slope]]){
    const f=execution?Math.max(c.minimum_speed,1/(1+c.strength*slope*Math.max(0,T-c.onset_c))):1;
    P+=(solo[task+'_'+route]-H)*((1-c.leakage_fraction)*f**3+c.leakage_fraction*leak);
   }
   last=T;T=c.idle_c+(T-c.idle_c)*decay+c.thermal_resistance*P*one;steps++;largest=Math.max(largest,T);
   if(T>upper+1e-8||T<c.idle_c-1e-8)throw Error('Thermal invariant violation');
  }
  if(Math.abs(T-last)>1e-9)throw Error('No constant-load thermal convergence');
  cells.push({cpuTask,gpuTask,cpuExecution,gpuExecution,temperature_after3600_s:T,last_step_delta_c:T-last});
 }
 return {status:'PASS',new_environment_START:0,new_physical_fit:0,temperature_clipping_added:false,shared_W_proxy:H,
  bounded_power_upper_W_proxy:capPower,loose_upper_c:loose,refined_invariant_upper_c:upper,
  refined_bound_does_not_require_leakage_cap:true,uncapped_equilibrium_map_at_loose_c:equilibriumMap(loose),uncapped_map_derivative_upper:derivativeBound,
  fixed_state_transition_checks:steps,constant_load_cells:cells.length,max_observed_pure_temperature_c:largest,cells,
  proof:'ForT in[idle,U], f<=1 and uncapped leakage power<=P_upper(U); RC step is a convex combination ofT and idle+R*P<=U. Idle tail power<=H, and dispatch changesz only. U is the first upper root; derivative<1 proves unique stable worst-phase equilibrium inside interval.',
  scope:'Current hypothesis config, initialAP26C (or any initial within invariant interval). Pure fixed-phase tests are not actual inference/device observations; not an A24 physical temperature certificate.'};
}
if(require.main===module){
 const parent=path.join(root,'experiments/coupled_345_20261017/OPERATION.json'),model=path.join(root,'results/STATE_COST_IDENTIFICATION_20261017_01/MODEL.json');
 const result={utc:new Date().toISOString(),parent_operation_sha256:sha(parent),cost_model_sha256:sha(model),...analyze(read(parent).physics,read(model))};
 fs.writeFileSync(path.join(__dirname,'THERMAL_PURE_TEST.json'),JSON.stringify(result,null,2)+'\n',{flag:'wx'});
 console.log(JSON.stringify({status:result.status,upper_c:result.refined_invariant_upper_c,loose_upper_c:result.loose_upper_c,pure_checks:result.fixed_state_transition_checks,new_environment_START:0}));
}
module.exports={analyze};
