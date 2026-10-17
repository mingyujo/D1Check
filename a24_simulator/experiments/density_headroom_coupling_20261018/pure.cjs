'use strict';
// Independent pure equations, no Python, requests, environment or fitting.
const fs=require('fs'),path=require('path'),crypto=require('crypto');
const root=path.resolve(__dirname,'../..'),read=p=>JSON.parse(fs.readFileSync(p));
const c=read(path.join(root,'experiments/load_density_20261017/OPERATION.json')).physics;
const model=read(path.join(root,'results/STATE_COST_IDENTIFICATION_20261017_01/MODEL.json'));
const solo=Object.fromEntries(model.supported_states.map((s,i)=>[s,model.coefficients_W_proxy[i]]));solo.detection_GPU=.6013808404579677;
const H=solo.classification_GPU+solo.detection_CPU-solo['classification_GPU+detection_CPU'];delete solo['classification_GPU+detection_CPU'];
const upper=read(path.join(root,'experiments/load_density_20261017/THERMAL_PURE_TEST.json')).refined_invariant_upper_c,U=upper-26;
const pmax=H+(['CPU','GPU'].map(r=>Math.max(...Object.entries(solo).filter(([k])=>k.endsWith('_'+r)).map(([,v])=>v))-H).reduce((a,b)=>a+b,0))*(.8+.2*Math.exp(.025*U));
const L=Math.max(U,12*pmax)/25+1e-8,step=.05;let checks=0,maxViolation=0;
for(let trial=0;trial<32;trial++){
 let T=26,E=0,A=0,D=0,low=0,high=0;
 for(let i=0;i<2000;i++){
  let active=[];
  if(trial<16){for(let r=0;r<2;r++)if((trial>>r)&1)active.push({task:((trial>>(r+2))&1)?'detection':'classification',route:r?'GPU':'CPU',stage:1});}
  else if(i%23<17){active=[{task:(i+trial)%3?'detection':'classification',route:i%2?'CPU':'GPU',stage:i%11?1:0}];if(i%3)active.push({task:(i+trial)%2?'classification':'detection',route:i%2?'GPU':'CPU',stage:i%7?1:2});}
  const dt=active.length?.1:.37,decay=Math.exp(-dt/25),one=-Math.expm1(-dt/25);let P=active.length?H:0;
  for(const a of active){
   const slope=a.route==='CPU'?.07:.045,f=a.stage===1?Math.max(.45,1/(1+slope*Math.max(0,T-32))):1;
   P+=(solo[a.task+'_'+a.route]-H)*(.8*f**3+.2*Math.exp(.025*(T-26)));
   if(a.stage===1){const k=Math.floor((T-26)/step),lo=26+k*step,hi=Math.min(upper,lo+step),fmax=Math.max(.45,1/(1+slope*Math.max(0,lo-32))),fmin=Math.max(.45,1/(1+slope*Math.max(0,hi-32))),w=f*dt;low+=(lo-26)*w/fmax;high+=((hi-26)/fmin-U/fmax)*w;}
  }
  const area=(T-26)*25*one+12*P*(dt-25*one);T=26+(T-26)*decay+12*P*one;E+=P*dt;A+=area;D+=dt;
  for(const violation of [low-2*A-L*.1*D,2*A-((2*U+L*.1)*D+high),12*E-25*U-A,A-12*E,T-upper]){checks++;maxViolation=Math.max(maxViolation,violation);if(violation>1e-7)throw Error('Necessary coupling inequality violated '+violation);}
 }
}
const file=path.join(__dirname,'PURE_TEST_RESULT.json');fs.writeFileSync(file,JSON.stringify({status:'PASS',checks,max_positive_violation:maxViolation,new_environment_START:0,new_LP_solves:0,new_training:0,new_physical_fit:0,source_sha256:crypto.createHash('sha256').update(fs.readFileSync(__filename)).digest('hex'),scope:'Independent fixed/alternating pure state transitions, not request simulation'},null,2)+'\n',{flag:'wx'});
console.log(JSON.stringify({status:'PASS',checks,maxViolation,new_environment_START:0}));
