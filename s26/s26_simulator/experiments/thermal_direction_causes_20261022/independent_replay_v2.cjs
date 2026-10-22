'use strict';
// Independent scalar recurrence for base power/heat and the39 learned residual inputs.
const fs=require('node:fs'),zlib=require('node:zlib');
const {steps}=require('../capacity_power_v1/replay.cjs');
const taus=[10,60,160,320],powerTaus=[1,10,60];
const dot=(a,b)=>a.reduce((s,x,j)=>s+x*b[j],0);
function history(e){
 const obs=e.AP_observations.filter(o=>o.available_upper_s<=e.anchor&&o.t_s>=e.anchor-30).sort((a,b)=>a.t_s-b.t_s),recent=obs.filter(o=>o.t_s>=e.anchor-20),short=obs.filter(o=>o.t_s>=e.anchor-10);
 const mean=a=>a.reduce((s,v)=>s+v,0)/a.length;
 const slope=(rr,key)=>{rr=rr.filter(o=>typeof o[key]==='number');if(rr.length<2||rr.every(o=>o[key]===rr[0][key]))return 0;const mt=mean(rr.map(o=>o.t_s)),my=mean(rr.map(o=>o[key]));let num=0,den=0;for(const o of rr){num+=(o.t_s-mt)*(o[key]-my);den+=(o.t_s-mt)**2;}return den>0?num/den:0;};
 const yy=recent.map(o=>o.AP),delta=yy.slice(1).map((y,j)=>y-yy[j]),changed=delta.map((v,j)=>Math.abs(v)>1e-9?j:-1).filter(j=>j>=0);let last=changed.length?recent[changed.at(-1)+1].t_s:(recent.length?recent[0].t_s:e.anchor);
 if(yy.length&&Math.abs(yy.at(-1)-e.AP0)>1e-9)last=e.anchor;
 const m=yy.length?mean(yy):0,sd=yy.length?Math.sqrt(mean(yy.map(y=>(y-m)**2))):0,lastobs=recent.at(-1);
 return [slope(short,'AP')*10,slope(recent,'SKIN')*10,slope(recent,'BAT')*10,yy.length?(e.AP0-m)/10:0,sd/10,yy.length?(Math.max(...yy)-Math.min(...yy))/10:0,(e.anchor-last)/30,delta.length?changed.length/delta.length:0,changed.length?delta[changed.at(-1)]:0,lastobs&&typeof lastobs.SKIN==='number'?(e.skin-lastobs.SKIN)/10:0,lastobs&&typeof lastobs.BAT==='number'?(e.BAT-lastobs.BAT)/10:0,recent.length/15];
}
function replay(e,models){
 const hx=history(e);
 const first=models.MARGIN_BALANCED.frozen_trend.frozen_HGB,pm=first.base_power_model,tm=first.base_thermal_model;
 const c=pm.coef.map((x,j)=>x/pm.scale[j]),cb=c.slice(2,7),ct=[c.slice(7,12),c.slice(12,17),c.slice(17,22)],B0=c[0]+e.baseline*c[1];
 const step=steps(e.intervals),changes=new Map(step),delays=new Map(step.map(([t,v])=>[t+.5,v])),queries=new Set(e.times);
 const end=e.times.at(-1),grid=[...new Set([-30,e.anchor,...e.times,...step.map(x=>x[0]).filter(t=>t<=end),...step.map(x=>x[0]+.5).filter(t=>t<=end)])].sort((a,b)=>a-b);
 let v=Array(5).fill(0),vd=Array(5).fill(0),zz=powerTaus.map(()=>Array(5).fill(0)),box=0,heat=Array(4).fill(0),activity=taus.map(()=>Array(5).fill(0)),prev=-30;
 const ctx=[1,(e.AP0-e.skin)/10,(e.BAT-e.skin)/10,e.slope*10,e.baseline],result=[]; let pv=Array(5).fill(0),last=Array(5).fill(e.anchor);
 for(const t of grid){
  if(changes.has(t)){const nv=changes.get(t);for(let j=0;j<5;j++)if(nv[j]!==pv[j])last[j]=Math.max(t,e.anchor);pv=nv;}
  const dt=t-prev,slope=2*dot(cb,v.map((x,j)=>x-vd[j])),aa=ct.map((row,k)=>dot(row,zz[k].map((x,j)=>x-v[j]))),constant=B0+box+ct.reduce((s,row)=>s+dot(row,v),0);
  if(prev>=e.anchor&&dt>0){
   heat=heat.map((h,j)=>{const tau=taus[j],decay=Math.exp(-dt/tau),q=-Math.expm1(-dt/tau);return decay*h+(constant-e.baseline)*q+slope*(dt-tau*q)+aa.reduce((s,a,k)=>s+a*(tau===powerTaus[k]?(dt/tau)*decay:(Math.exp(-dt/powerTaus[k])-decay)/(1-tau/powerTaus[k])),0);});
   activity=activity.map((row,k)=>row.map((x,j)=>Math.exp(-dt/taus[k])*x+-Math.expm1(-dt/taus[k])*v[j]));
  }
  zz=zz.map((row,k)=>row.map((x,j)=>Math.exp(-dt/powerTaus[k])*x+-Math.expm1(-dt/powerTaus[k])*v[j]));box+=slope*dt;
  if(queries.has(t)){
   const age=t-e.anchor,idle=e.skin+tm.delta_C,decay=tm.w_fast*Math.exp(-age/tm.tau_fast_s)+(1-tm.w_fast)*Math.exp(-age/tm.tau_slow_s);
   const base=idle+(e.AP0-idle)*decay+tm.gain_fast*heat[taus.indexOf(tm.tau_fast_s)]+tm.gain_slow*heat[taus.indexOf(tm.tau_slow_s)];
   const X=[...activity.flat(),...heat,...[10,160,320].flatMap(tau=>ctx.map(x=>-Math.expm1(-age/tau)*x))];
   const apply=(xx,m)=>{let raw=m.baseline_prediction||0;for(const tree of m.trees){let node=tree[0];while(!node.leaf)node=tree[xx[node.feature]<=node.threshold?node.left:node.right];raw+=node.value;}return raw;}; const previous=base+X[24]*apply([...X,base],first); const xx=[...X,base,previous,age/320,...last.map((v,j)=>(t-v)*(pv[j]>0?1:-1)/320)]; const balanced=previous+X[24]*apply(xx,models.MARGIN_BALANCED.frozen_trend); const xx60=[...xx,balanced,...hx]; const pred=Object.fromEntries(Object.entries(models).map(([kind,m])=>[kind,balanced+X[24]*apply(xx60,m)]));
   result.push({time:t,base,previous,balanced,pred});
  }
  if(changes.has(t))v=changes.get(t);if(delays.has(t))vd=delays.get(t);prev=t;
 }
 return {id:e.id,values:result};
}
const data=JSON.parse(zlib.gunzipSync(fs.readFileSync(process.argv[2])).toString('utf8'));
const out=data.cases.map(e=>replay(e,data.models[e.group]));
fs.writeFileSync(process.argv[3],zlib.gzipSync(Buffer.from(JSON.stringify(out))));
