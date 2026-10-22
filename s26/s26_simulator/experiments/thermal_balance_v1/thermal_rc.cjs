'use strict';
// Independent JS deployment prototype; this module is not attached to the frozen plant.
function advance(T,p0,p1,dt,context,model){
  if(!(dt>=0&&model.tau_s>0&&model.gain_C_per_API_W>=0))throw Error('Invalid passive RC parameters');
  const d=dt/model.tau_s,q=-Math.expm1(-d),linear=d<1e-5?d/2-d*d/6+d**3/24:1-q/d;
  const idle=context.SKIN+model.delta_C,base=context.baseline_API_W,G=model.gain_C_per_API_W;
  return idle+(T-idle)*Math.exp(-d)+G*((p0-base)*q+(p1-p0)*linear);
}
function support(input,limits){
  const reasons=[];
  for(const [key,bounds] of Object.entries(limits)){
    const vals=Array.isArray(input[key])?input[key]:[input[key]];
    if(!vals.length||vals.some(v=>!Number.isFinite(v)||v<bounds[0]||v>bounds[1]))reasons.push(key);
  }
  return {status:reasons.length?'UNSUPPORTED':'WITHIN_MARGINAL_MEASURED_RANGES',reasons,physical_validation:false};
}
function replay(ep,model){
  const ts=ep.power_times,pw=ep.power_values,queries=ep.times,anchor=ep.anchor_s;
  if(ts[0]>anchor||queries[0]<anchor||queries.at(-1)>ts.at(-1))throw Error('Unmeasured endpoint extrapolation');
  const knots=[...new Set([anchor,...ts.filter(t=>t>anchor&&t<queries.at(-1)),...queries])].sort((a,b)=>a-b);
  let j=0;const values=new Map;let T=ep.anchor_AP;
  function power(t){while(j+1<ts.length&&ts[j+1]<t)j++;if(t===ts[j])return pw[j];if(j+1===ts.length)return pw[j];return pw[j]+(pw[j+1]-pw[j])*(t-ts[j])/(ts[j+1]-ts[j]);}
  let previous=knots[0],p0=power(previous);values.set(previous,T);
  const context={SKIN:ep.skin,baseline_API_W:ep.baseline};
  for(const t of knots.slice(1)){const p1=power(t);T=advance(T,p0,p1,t-previous,context,model);values.set(t,T);previous=t;p0=p1;}
  return queries.map(t=>values.get(t));
}
module.exports={advance,support,replay};
