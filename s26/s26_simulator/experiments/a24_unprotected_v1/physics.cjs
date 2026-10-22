'use strict';
// Exact analytic capacity-power -> passive thermal cascade, fitted models frozen.
const {steps}=require('../capacity_power_v1/replay.cjs');
const dot=(a,b)=>a.reduce((s,x,j)=>s+x*b[j],0),zeros=()=>Array(5).fill(0);
const proxy=a=>[[0,1,4,5].some(j=>a[j]>0),a[1]>0,a[2]>0,a[3]>0,a.slice(0,8).some(x=>x>0)].map(Number);
class Physics{
 constructor(pm,tm,context,start=-30){
  this.pm=pm;this.tm=tm;Object.assign(this,context);this.time=start;this.v=zeros();this.vd=zeros();this.z=[zeros(),zeros(),zeros()];this.box=0;this.heat=[0,0];this.pending=[];this.J=0;this.H=0;this.anchor=0;
  this.c=pm.coef.map((x,j)=>x/pm.scale[j]);this.B0=this.c[0]+this.baseline*this.c[1];this.cb=this.c.slice(2,7);this.ct=[this.c.slice(7,12),this.c.slice(12,17),this.c.slice(17)];
 }
 clone(){const p=Object.assign(Object.create(Physics.prototype),this);p.v=this.v.slice();p.vd=this.vd.slice();p.z=this.z.map(x=>x.slice());p.heat=this.heat.slice();p.pending=this.pending.map(x=>[x[0],x[1].slice()]);return p;}
 set(v){if(v.some((x,j)=>x!==this.v[j])){this.v=v.slice();this.pending.push([this.time+.5,v.slice()]);}}
 active(a){this.set(proxy(a));}
 temperature(){const m=this.tm,idle=this.skin+m.delta_C,age=this.time-this.anchor;return idle+(this.AP0-idle)*(m.w_fast*Math.exp(-age/m.tau_fast_s)+(1-m.w_fast)*Math.exp(-age/m.tau_slow_s))+m.gain_fast*this.heat[0]+m.gain_slow*this.heat[1];}
 power(){return this.B0+this.box+this.ct.reduce((s,row,k)=>s+dot(row,this.z[k]),0);}
 segment(dt){
  const taus=[1,10,60],m=this.tm,ht=[m.tau_fast_s,m.tau_slow_s],G=[m.gain_fast,m.gain_slow],slope=2*dot(this.cb,this.v.map((x,j)=>x-this.vd[j]));
  const A=this.ct.map((row,k)=>dot(row,this.z[k].map((x,j)=>x-this.v[j]))),constant=this.B0+this.box+this.ct.reduce((s,row)=>s+dot(row,this.v),0),q=taus.map(t=>-Math.expm1(-dt/t));
  const area=constant*dt+.5*slope*dt*dt+A.reduce((s,a,k)=>s+a*taus[k]*q[k],0);
  if(this.time>=0){const integral=area-this.baseline*dt,age=this.time,idle=this.skin+m.delta_C;let H=idle*dt+(this.AP0-idle)*(m.w_fast*ht[0]*Math.exp(-age/ht[0])*-Math.expm1(-dt/ht[0])+(1-m.w_fast)*ht[1]*Math.exp(-age/ht[1])*-Math.expm1(-dt/ht[1]));
   for(let j=0;j<2;j++){const decay=Math.exp(-dt/ht[j]),qq=-Math.expm1(-dt/ht[j]);const kernels=taus.map(pt=>pt===ht[j]?(dt/ht[j])*decay:(Math.exp(-dt/pt)-decay)/(1-ht[j]/pt));const next=decay*this.heat[j]+(constant-this.baseline)*qq+slope*(dt-ht[j]*qq)+dot(A,kernels);H+=G[j]*(integral-ht[j]*(next-this.heat[j]));this.heat[j]=next;}this.J+=area;this.H+=H;
  }
  this.z=this.z.map((row,k)=>row.map((x,j)=>(1-q[k])*x+q[k]*this.v[j]));this.box+=slope*dt;this.time+=dt;
 }
 advance(dt){const end=this.time+dt;if(!(dt>=0&&Number.isFinite(end)))throw Error('Physics advance');
  while(this.time<end-1e-12){while(this.pending.length&&this.pending[0][0]<=this.time+1e-12)this.vd=this.pending.shift()[1];const next=Math.min(end,this.pending[0]?.[0]??end,this.time<0?0:end);this.segment(next-this.time);}
  while(this.pending.length&&this.pending[0][0]<=end+1e-12)this.vd=this.pending.shift()[1];
 }
 static fromPast(pm,tm,ctx,intervals,t){const p=new Physics(pm,tm,ctx);for(const [at,v]of steps(intervals)){if(at>t)break;p.advance(at-p.time);p.set(v);}p.advance(t-p.time);return p;}
}
module.exports={Physics,proxy};
