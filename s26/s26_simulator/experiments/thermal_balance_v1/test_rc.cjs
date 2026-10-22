'use strict';
const fs=require('node:fs'),{advance,support,replay}=require('./thermal_rc.cjs');
if(process.argv[2]==='replay'){
 const input=JSON.parse(fs.readFileSync(0,'utf8'));
 process.stdout.write(JSON.stringify(input.cases.map(e=>({id:e.id,predicted:replay(e,input.models[e.model])}))));
}else{
 let checks=0;function near(a,b,tol=1e-9){checks++;if(Math.abs(a-b)>tol)throw Error('Physics invariant '+a+' vs '+b)}
 const context={SKIN:28,baseline_API_W:.6},m={tau_s:60,delta_C:1,gain_C_per_API_W:2};
 for(const p of [.6,1,2,4]){
  const eq=29+2*(p-.6);near(advance(31,p,p,86400,context,m),eq);
  const t=advance(31,p,p,30,context,m);near(t,eq+(31-eq)*Math.exp(-.5));
  near(advance(advance(31,p,p,13,context,m),p,p,17,context,m),t);
  if(t<Math.min(eq,31)||t>Math.max(eq,31))throw Error('Passive convex bound');checks++;
 }
 const hot=advance(31,4,4,600,context,m),cool=advance(hot,.6,.6,300,context,m);
 if(!(cool<hot&&cool>=29))throw Error('Cooling');checks++;
 // Analytic ramp forcing: for unit ramp from0 to1 over tau, filtered level = exp(-1).
 const rampContext={SKIN:0,baseline_API_W:0},rampModel={tau_s:10,delta_C:0,gain_C_per_API_W:1};
 near(advance(0,0,1,10,rampContext,rampModel),Math.exp(-1));
 near(advance(advance(0,0,.3,3,rampContext,rampModel),.3,1,7,rampContext,rampModel),Math.exp(-1));
 near(advance(34,2,2,0,context,m),34);
 const s=support({AP_C:100},{AP_C:[26,46.6]});if(s.status!=='UNSUPPORTED')throw Error('Unsupported must not be clamped');checks++;
 console.log(JSON.stringify({status:'PASS',checks,scope:'Equilibrium/cooling/semigroup/ramp/zero-step/support; no phone proof'}));
}
