'use strict';
const path=require('path');
const {CalibratedPhysics,calibratedA24Profile,forcing}=require(path.resolve(__dirname,'../a24_thermal_calibration_20261021/calibrated_profile.cjs'));
function advancePair(core,sensor,u,tau,lag,dt){
 const e=Math.exp(-dt/tau),one=-Math.expm1(-dt/tau),next=u+(core-u)*e;
 if(!lag)return {core:next,sensor:next,area:core*tau*one+u*(dt-tau*one)};
 const q=Math.exp(-dt/lag),oq=-Math.expm1(-dt/lag);
 if(Math.abs(tau-lag)<1e-9)return {core:next,sensor:u+(sensor-u)*q+(core-u)*(dt/tau)*e,
  area:u*dt+(sensor-u)*tau*one+(core-u)*tau*(1-(1+dt/tau)*e)};
 const k=(core-u)*tau/(tau-lag);
 return {core:next,sensor:u+(sensor-u)*q+k*(e-q),area:u*dt+(sensor-u)*lag*oq+k*(tau*one-lag*oq)};
}
class DirectionPhysics extends CalibratedPhysics{
 constructor(data,model,context){
  if(model.schema!=='A24-direction-aware-two-thermal-states-v2')throw Error('Direction calibration schema');
  super(data,{...model,schema:'A24-contextual-two-thermal-states-v1'},context);this.calibration=model;this.sensorFast=0;this.sensorSlow=0;
 }
 clone(){const p=Object.create(DirectionPhysics.prototype);Object.assign(p,this);return p;}
 exportState(){return {...super.exportState(),sensorFast:this.sensorFast,sensorSlow:this.sensorSlow};}
 advance(dt,owners){
  const m=this.calibration,b=m.coefficients,tf=m.tau_fast_s,ts=m.tau_slow_s,lag=m.transport_s,s=this.time-this.origin,oldH=this.H;
  const f=advancePair(this.heatFast,this.sensorFast,forcing(owners,b,2),tf,lag,dt),slow=advancePair(this.heatSlow,this.sensorSlow,forcing(owners,b,6),ts,lag,dt);
  const es=Math.exp(-s/ts),ef=Math.exp(-s/tf),os=-Math.expm1(-dt/ts),of=-Math.expm1(-dt/tf);
  const baseArea=this.initialAP*dt+b[0]*(dt-ts*es*os)+b[1]*this.preSlope*60*(ts*es*os-tf*ef*of);
  super.advance(dt,owners);this.heatFast=f.core;this.heatSlow=slow.core;this.sensorFast=f.sensor;this.sensorSlow=slow.sensor;
  this.T=this.initialAP+b[0]*(1-Math.exp(-(s+dt)/ts))+b[1]*this.preSlope*60*(Math.exp(-(s+dt)/ts)-Math.exp(-(s+dt)/tf))+f.sensor+slow.sensor;
  this.H=oldH+baseArea+f.area+slow.area;
 }
}
function directionA24Profile(data,model,context){
 const base=calibratedA24Profile(data,{...model,schema:'A24-contextual-two-thermal-states-v1'},context);
 return {...base,profile_version:'A24_DIRECTION_AWARE_THERMAL_V2',
  assumptions:[...base.assumptions,'AP response transport is an empirical causal state, not uniquely identified sensor or material physics.','Direction classification uses the same continuous temperature curve and unchanged 0.2C threshold.'],
  createPhysics:()=>new DirectionPhysics(data,model,context),fromPublic:s=>Object.assign(new DirectionPhysics(data,model,{initial_ap_c:s.initialAP,pre_slope_C_s:s.preSlope}),s)};
}
module.exports={DirectionPhysics,directionA24Profile,advancePair};
