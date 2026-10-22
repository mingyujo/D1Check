'use strict';
const fs=require('node:fs'),{advance}=require('../thermal_balance_v1/thermal_rc.cjs');
function predict(ep,m){
 const ts=ep.power_times,pw=ep.power_values,queries=ep.times,anchor=ep.anchor_s;
 if(ts[0]>anchor||queries[0]<anchor||queries.at(-1)>ts.at(-1))throw Error('Unmeasured endpoint');
 const knots=[...new Set([anchor,...ts.filter(t=>t>anchor&&t<queries.at(-1)),...queries])].sort((a,b)=>a-b);
 let j=0,xf=0,xs=0,prev=anchor;const values=new Map;
 function power(t){while(j+1<ts.length&&ts[j+1]<t)j++;return j+1===ts.length?pw[j]:pw[j]+(pw[j+1]-pw[j])*(t-ts[j])/(ts[j+1]-ts[j]);}
 let p0=power(anchor)-ep.baseline;values.set(anchor,ep.anchor_AP);
 const ctx={SKIN:0,baseline_API_W:0},f={tau_s:m.tau_fast_s,gain_C_per_API_W:1,delta_C:0},s={...f,tau_s:m.tau_slow_s};
 for(const t of knots.slice(1)){const p1=power(t)-ep.baseline;xf=advance(xf,p0,p1,t-prev,ctx,f);xs=advance(xs,p0,p1,t-prev,ctx,s);
  const decay=m.w_fast*Math.exp(-(t-anchor)/m.tau_fast_s)+(1-m.w_fast)*Math.exp(-(t-anchor)/m.tau_slow_s),idle=ep.skin+m.delta_C;
  values.set(t,idle+(ep.anchor_AP-idle)*decay+m.gain_fast*xf+m.gain_slow*xs);prev=t;p0=p1;}
 return queries.map(t=>values.get(t));
}
if(process.argv[2]==='test'){
 const m={tau_fast_s:10,tau_slow_s:80,w_fast:.3,delta_C:0,gain_fast:1,gain_slow:2};
 const ep={anchor_s:0,anchor_AP:30,skin:28,baseline:.5,power_times:[0,4000],power_values:[2,2],times:[0,40,4000]};
 const p=predict(ep,m),eq=28+3*1.5;if(p[0]!==30||Math.abs(p[2]-eq)>1e-9||p.some(x=>x<30||x>eq))throw Error('Passive equilibrium');
 const c=predict({...ep,anchor_AP:40,power_values:[.5,.5]},m);if(!(c[1]<40&&c[2]>=28&&Math.abs(c[2]-28)<1e-9))throw Error('Cooling');
 console.log(JSON.stringify({status:'PASS',checks:5,scope:'Two-mode anchor, positive bounded heating, equilibrium, cooling'}));
}else{const input=JSON.parse(fs.readFileSync(0,'utf8'));process.stdout.write(JSON.stringify(input.cases.map(e=>({id:e.id,predicted:predict(e,input.models[e.model])}))));}
