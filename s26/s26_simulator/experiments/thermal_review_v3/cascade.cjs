'use strict';
// Exact passive cascade on an already saved activity path. This is not a scheduler.
const {steps}=require('../capacity_power_v1/replay.cjs');
const dot=(a,b)=>a.reduce((s,v,j)=>s+v*b[j],0);
function coupled(step,times,baseline,anchor,AP0,skin,power,thermal,start=-30){
 if(!times.length||times[0]<anchor||anchor<start||times.some((t,j)=>!Number.isFinite(t)||(j&&t<=times[j-1])))throw Error('Invalid query times');
 const ht=[thermal.tau_fast_s,thermal.tau_slow_s],gains=[thermal.gain_fast,thermal.gain_slow];
 if(ht.some(t=>!(t>0))||gains.some(g=>!(g>=0))||!(thermal.w_fast>=0&&thermal.w_fast<=1))throw Error('Invalid passive parameters');
 const c=power.coef.map((x,j)=>x/power.scale[j]);if(c.some(x=>!Number.isFinite(x)||x<0))throw Error('Invalid nonnegative power');
 const B0=c[0]+baseline*c[1],cb=c.slice(2,7),ct=[c.slice(7,12),c.slice(12,17),c.slice(17,22)],taus=[1,10,60];
 const changes=new Map(step),delays=new Map(step.map(([t,v])=>[t+.5,v]));
 const grid=[...new Set([start,anchor,...times,...step.map(x=>x[0]).filter(t=>t<=times.at(-1)),...step.map(x=>x[0]+.5).filter(t=>t<=times.at(-1))])].sort((a,b)=>a-b);
 let v=Array(5).fill(0),vd=v.slice(),z=Array.from({length:3},()=>Array(5).fill(0)),box=0,heat=[0,0],area=0,previous=start;
 const values=new Map;
 for(const t of grid){
  const dt=t-previous,slope=2*dot(cb,v.map((x,j)=>x-vd[j]));
  const A=ct.map((row,k)=>dot(row,z[k].map((x,j)=>x-v[j]))),constant=B0+box+ct.reduce((s,row)=>s+dot(row,v),0),q=taus.map(tau=>-Math.expm1(-dt/tau));
  if(previous>=anchor&&dt>0)heat=heat.map((h,j)=>{
   const decay=Math.exp(-dt/ht[j]),qq=-Math.expm1(-dt/ht[j]);
   const kernels=taus.map(pt=>pt===ht[j]?(dt/ht[j])*decay:(Math.exp(-dt/pt)-decay)/(1-ht[j]/pt));
   return decay*h+(constant-baseline)*qq+slope*(dt-ht[j]*qq)+dot(A,kernels);
  });
  area+=constant*dt+.5*slope*dt*dt+A.reduce((s,a,k)=>s+a*taus[k]*q[k],0);
  z=z.map((row,k)=>row.map((x,j)=>(1-q[k])*x+q[k]*v[j]));box+=slope*dt;
  if(t>=anchor){
   const idle=skin+thermal.delta_C,age=t-anchor,decay=thermal.w_fast*Math.exp(-age/ht[0])+(1-thermal.w_fast)*Math.exp(-age/ht[1]);
   values.set(t,[B0+box+ct.reduce((s,row,k)=>s+dot(row,z[k]),0),idle+(AP0-idle)*decay+dot(gains,heat),area]);
  }
  if(changes.has(t))v=changes.get(t);if(delays.has(t))vd=delays.get(t);previous=t;
 }
 const result=times.map(t=>values.get(t));if(result.some(r=>r.some(x=>!Number.isFinite(x))))throw Error('Nonfinite cascade');return result;
}
function policySupport({powerRange,temperatureRange,limits,accuracyGate,jointValidated}){
 const reasons=[];
 if(accuracyGate!==true)reasons.push('PREDICTED_POWER_THERMAL_ACCURACY_GATE_FAILED');
 if(jointValidated!==true)reasons.push('SUSTAINED_SHARED_CPU_TRIPLE_NOT_VALIDATED');
 for(const [name,range,bounds] of [['POWER_API_W',powerRange,limits.power_API_W],['AP_C',temperatureRange,limits.AP_C]])
  if(!Array.isArray(range)||range.length!==2||range.some(x=>!Number.isFinite(x))||range[0]>range[1]||range[0]<bounds[0]||range[1]>bounds[1])reasons.push(name+'_OUTSIDE_MARGINAL_MEASUREMENTS');
 return {status:reasons.length?'UNSUPPORTED_FOR_POLICY_COMPARISON':'WITHIN_DECLARED_SUPPORT',reasons,policy_temperature_C:null,physical_validation:false};
}
module.exports={steps,coupled,policySupport};
