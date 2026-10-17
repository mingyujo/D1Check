'use strict';
// Independent scalar proof calculation. No request engine or LP solver.
function derive(jobs,c,solo,H,U){
 const speed=(T,r)=>Math.max(c.minimum_speed,1/(1+c.strength*(r==='CPU'?c.cpu_slope:c.gpu_slope)*Math.max(0,T-c.onset_c)));
 const pmax=H+['CPU','GPU'].reduce((a,r)=>a+Math.max(...Object.entries(solo).filter(([k])=>k.endsWith('_'+r)).map(([,v])=>v))-H,0)*
   (1-c.leakage_fraction+c.leakage_fraction*Math.exp(c.leakage_per_c*(U-c.reference_c)));
 const L=Math.max(U-c.idle_c,c.thermal_resistance*pmax)/c.thermal_tau_s+1e-8,eta=L*c.tick_s,routes={};
 let extra=0;
 for(const r of ['CPU','GPU']){
  const slope=r==='CPU'?c.cpu_slope:c.gpu_slope,f=speed(U,r);
  const derivative=-3*(1-c.leakage_fraction)*slope*f**4+c.leakage_fraction*c.leakage_per_c*Math.exp(c.leakage_per_c*(U-c.reference_c));
  if(c.strength!==1||f<=c.minimum_speed||derivative>=0)throw Error('Proof assumptions fail');
  const A=Math.max(...Object.entries(solo).filter(([k])=>k.endsWith('_'+r)).map(([,v])=>v-H));
  const delta=A*(1-c.leakage_fraction)*(1-f**3);let rho=0,burst=0;
  for(const j of jobs){const v=j.routes[r].stages_ns.map(x=>x/1e9),non=v.reduce((a,b)=>a+b,0)-v[1]+4e-9;rho=Math.max(rho,non/(non+Math.max(0,v[1]-1e-12)));burst=Math.max(burst,2*non);}
  routes[r]={A,rho,burst,delta,derivative_upper:derivative};extra+=rho*delta;
 }
 const mapping=B=>c.idle_c+c.thermal_resistance*(H+extra+Object.entries(routes).reduce((a,[r,v])=>a+v.A*((1-c.leakage_fraction)*speed(B-eta,r)**3+c.leakage_fraction*Math.exp(c.leakage_per_c*(B-eta-c.reference_c))),0));
 let lo=c.onset_c+eta,hi=U;
 if(mapping(hi)>hi)return {upper:U,original_upper:U,strengthened:false,routes,eta};
 if(mapping(lo)>=lo)for(let i=0;i<100;i++){const mid=(lo+hi)/2;if(mapping(mid)>mid)lo=mid;else hi=mid;}
 else hi=lo;
 const burst=c.thermal_resistance/c.thermal_tau_s*Object.values(routes).reduce((a,d)=>a+d.delta*d.burst,0),upper=Math.min(U,hi+burst+1e-6);
 return {upper,original_upper:U,strengthened:upper<U,routes,eta,crossing_temperature:hi,convolution_burst_c:burst,map_at_crossing:mapping(hi)};
}
module.exports={derive};
