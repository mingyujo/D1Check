'use strict';
// Opt-in thermal profile; the frozen shared factory and results are untouched.
const path=require('path');
const {A24Physics,a24Profile}=require(path.resolve(__dirname,'../../../common_simulator/v1/profiles.cjs'));
function forcing(owners,coef,start){
 const n={C_CPU:0,C_GPU:0,D_CPU:0,D_GPU:0};
 for(const o of owners){const k=o.task+'_'+o.route;if(!(k in n))throw Error('Unsupported route '+k);n[k]++;}
 const g=coef.slice(start,start+4),dg=Math.max(0,g[2]+g[1]-g[0]);
 // Directly identified: three solo routes and CG_DC. Everything else is a
 // declared additive transfer, never a measured CPU3 or D_GPU validation.
 return Math.max(0,n.C_CPU*g[0]+n.C_GPU*g[1]+n.D_CPU*g[2]+n.D_GPU*dg+Math.min(n.C_GPU,n.D_CPU)*(g[3]-g[1]-g[2]));
}
class CalibratedPhysics extends A24Physics{
 constructor(data,model,context){
  if(model.schema!=='A24-contextual-two-thermal-states-v1')throw Error('Calibration schema');
  if(!Number.isFinite(context?.initial_ap_c)||!Number.isFinite(context?.pre_slope_C_s))throw Error('Explicit causal/scenario initial AP and pretrend required');
  super({...data,initial_temperature_c:context.initial_ap_c});
  this.calibration=model;this.initialAP=context.initial_ap_c;this.preSlope=Math.max(-.05,Math.min(.05,context.pre_slope_C_s));this.heatFast=0;this.heatSlow=0;this.origin=35;
  this.ambient_c=this.initialAP+model.coefficients[0]; // conditional reference, not measured air temperature
 }
 clone(){const p=Object.create(CalibratedPhysics.prototype);Object.assign(p,this);return p;}
 exportState(){return {...super.exportState(),initialAP:this.initialAP,preSlope:this.preSlope,heatFast:this.heatFast,heatSlow:this.heatSlow,origin:this.origin};}
 advance(dt,owners){
  if(!(dt>=0))throw Error('Nonnegative elapsed time required');
  const m=this.calibration,b=m.coefficients,tf=m.tau_fast_s,ts=m.tau_slow_s,s=this.time-this.origin,oldH=this.H;
  const df=Math.exp(-dt/tf),ds=Math.exp(-dt/ts),of=-Math.expm1(-dt/tf),os=-Math.expm1(-dt/ts);
  const uf=forcing(owners,b,2),us=forcing(owners,b,6),ef0=Math.exp(-s/tf),es0=Math.exp(-s/ts);
  const levelArea=this.initialAP*dt+b[0]*(dt-ts*es0*os)+b[1]*this.preSlope*60*(ts*es0*os-tf*ef0*of);
  const heatArea=this.heatFast*tf*of+uf*(dt-tf*of)+this.heatSlow*ts*os+us*(dt-ts*os);
  // Preserve the old conditional power law evaluated at the new temperature.
  // Absolute energy and temperature->speed accuracy remain unvalidated.
  super.advance(dt,owners);
  this.heatFast=this.heatFast*df+uf*of;this.heatSlow=this.heatSlow*ds+us*os;
  this.T=this.initialAP+b[0]*(1-es0*ds)+b[1]*this.preSlope*60*(es0*ds-ef0*df)+this.heatFast+this.heatSlow;
  this.H=oldH+levelArea+heatArea;
 }
}
function calibratedA24Profile(data,model,context){
 const p=a24Profile(data);return {...p,profile_version:'A24_CONTEXTUAL_THERMAL_V1',thermal_calibration:model.identity,
  ambient_c:context.initial_ap_c+model.coefficients[0],
  assumptions:[...p.assumptions,'Initial AP/pretrend contextual reference is not measured ambient temperature.','Calibrated thermal supported states: C_CPU,C_GPU,D_CPU,CG_DC; other occupancies are unvalidated transfers.','Existing power/speed equations are retained, with new temperature input; policy outcomes must be reevaluated separately.'],
  createPhysics:()=>new CalibratedPhysics(data,model,context),
  fromPublic:s=>Object.assign(new CalibratedPhysics(data,model,{initial_ap_c:s.initialAP,pre_slope_C_s:s.preSlope}),s)};
}
module.exports={CalibratedPhysics,calibratedA24Profile,forcing};
