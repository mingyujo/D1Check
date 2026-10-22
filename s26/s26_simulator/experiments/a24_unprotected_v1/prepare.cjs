'use strict';
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto'),z=require('node:zlib');
const H=__dirname,R=path.resolve(H,'../..'),source=path.join(H,'source');fs.mkdirSync(source,{recursive:true});
const sha=b=>crypto.createHash('sha256').update(b).digest('hex'),write=(n,x)=>fs.writeFileSync(path.join(H,n),JSON.stringify(x,null,2)+'\n',{flag:'wx'});
const replace=(s,a,b)=>{if(s.split(a).length!==2)throw Error('Source boundary '+a);return s.replace(a,b);};
const files=['s26_simulator.cjs','multi_simulator.cjs','nominal_rollout.cjs','multi_timing.cjs','resource_contract.cjs','midpoint_work.cjs','dynamic_cost_math_v2.cjs'],pins=[];
for(const n of files){const p=path.join(R,'experiments/sustained_load_v1/source',n),b=fs.readFileSync(p);let s=b.toString();
 if(n==='multi_simulator.cjs'){
  s=replace(s,"class MultiSimulator extends base.Simulator{","const {Physics}=require('../physics.cjs');\nclass MultiSimulator extends base.Simulator{");
  s=replace(s,"this.waitDose=0;}","this.waitDose=0;this.physics=Physics.fromPast(config.power_model,config.thermal_model,{baseline:this.context.targets.POWER_API.baseline.median_api_w,skin:this.hist[1],AP0:this.anchorAP},this.intervals,0);this.heldAP=this.physics.temperature();this.curve2=[[0,this.heldAP,this.physics.power()]];this.integrals=[];}\n temperature(){return this.physics?this.physics.temperature():super.temperature()}\n setActivity(a){super.setActivity(a);if(this.physics)this.physics.active(a)}\n advance(dt){const p=this.physics,t=this.time,J=p.J,H=p.H;super.advance(dt);p.advance(dt);if(t>=35)this.integrals.push([t,this.time,p.J-J,p.H-H]);if(!this.curve2.length||this.time-this.curve2.at(-1)[0]>=.25-1e-9)this.curve2.push([this.time,p.temperature(),p.power()]);}");
  s=replace(s,'temperatureAt(offset){','temperatureAt(offset){if(this.physics){const p=this.physics.clone();p.advance(offset);return p.temperature()}');
  s=replace(s,"return {time:this.time,horizon_s:","return {physics_context:{AP0:this.physics.AP0,skin:this.physics.skin,baseline:this.physics.baseline},wait_used_s:this.waitDose,time:this.time,horizon_s:");
  s=replace(s,'if(this.ready.length&&this.time<this.config.dispatch_stop_s','if(this.time>=this.waitUntil-1e-9&&this.ready.length&&this.time<this.config.dispatch_stop_s');
  s=replace(s,"if(a.kind==='DISPATCH'){","if(a.kind==='WAIT'){this.waitDose+=a.wait_s;this.waitUntil=Math.min(this.config.dispatch_stop_s,this.time+a.wait_s);this.decisions.push({time:this.time,action:a});continue;}if(a.kind==='DISPATCH'){");
  s=replace(s,'this.selectCPU();this.setActivity(rc.activity(this.owners,this.cpu,this.model));let dt=this.config.horizon_s-this.time;','this.selectCPU();this.setActivity(rc.activity(this.owners,this.cpu,this.model));let dt=this.config.horizon_s-this.time;if(this.waitUntil>this.time+1e-9)dt=Math.min(dt,this.waitUntil-this.time);');
  s=replace(s,'const r=super.result();',"const r=require('../result.cjs').summarize(this);");
 }
 if(n==='nominal_rollout.cjs'){
  s=replace(s,'function rollout(obs,packet,nom,model,first){','function rollout(obs,packet,nom,model,first,physics){');
  s=replace(s,'let firstPending=Boolean(first);','const waitUntil=obs.time+(first?.wait_s??0);let firstPending=Boolean(first&&!first.wait_s);');
  s=replace(s,'else if(eligible.length){','else if(time>=waitUntil-1e-10&&eligible.length){');
  s=replace(s,"if(!owners.length){if(ready.length)throw Error('Nominal deadlock');break;}","if(!owners.length){if(ready.length&&time<waitUntil){physics.advance(waitUntil-time);time=waitUntil;continue;}if(ready.length)throw Error('Nominal deadlock');break;}");
  s=replace(s,'const active=rc.activity(owners,cpu,model),rates=new Map;let dt=Infinity;','const active=rc.activity(owners,cpu,model),rates=new Map;physics.active(active);let dt=Math.min(.05,obs.horizon_s-time);if(time<waitUntil)dt=Math.min(dt,waitUntil-time);');
  s=s.replaceAll('nom[o.route].identity,obs.sensor.AP,peers','nom[o.route].identity,physics.temperature(),peers');
  s=replace(s,"time+=dt;if(time>(obs.horizon_s??180))throw Error('Nominal completion outside registered horizon');","physics.advance(dt);time+=dt;if(time>=obs.horizon_s-1e-10)break;");
  s=replace(s,'for(const o of done){plans.push','for(const o of [...done,...owners.map(o=>({...o,end:time}))]){plans.push');
  s=replace(s,"const responses=done.filter(x=>Number.isFinite(x.deadline)).map(o=>({ordinal:o.ordinal,response:o.response,deadline:o.deadline}));","physics.active(Array(9).fill(0));physics.advance(Math.max(0,obs.horizon_s-physics.time));const responses=[...done,...owners,...ready].filter(x=>Number.isFinite(x.deadline)).map(o=>({ordinal:o.ordinal,response:o.response??null,deadline:o.deadline}));");
 }
 fs.writeFileSync(path.join(source,n),s,{flag:'wx'});pins.push({file:n,parent_sha256:sha(b),new_sha256:sha(Buffer.from(s))});
}
fs.writeFileSync(path.join(source,'multi_actions.cjs'),"module.exports=require('../policy.cjs');\n",{flag:'wx'});
const packetPath=path.join(R,'experiments/multiresource_v1/PACKET.json.gz'),packet=JSON.parse(z.gunzipSync(fs.readFileSync(packetPath))),context=packet.scenarios.find(s=>s.context_index===0).context;
const cases=[];function make(id,n,rate,mix,phase){const duration=n/rate,requests=Array.from({length:n},(_,i)=>{const group=Math.floor(i/16),within=i%16,det=(within+group)% (mix===.75?4:2)===0;return {ordinal:i,offset_ns:Math.round((35+group*16/rate)*1e9),task_id:det?'detection':'classification',priority:det?'normal':'urgent',deadline_ms:det?2000:800};});return{id,n,rate,mix,duration,phase,stream:phase==='TRAIN'?271080000:phase==='DEV'?271180000:271280000,context,requests,horizon_s:35+duration+90,dispatch_stop_s:35+duration+45,censor_s:35+duration+60};}
for(const n of[48,96,128])for(const rate of[8,16])for(const mix of[.5,.75])cases.push(make('TRAIN_'+n+'_'+rate+'_'+mix,n,rate,mix,'TRAIN'));
for(const n of[128,256])for(const rate of[8,16])for(const mix of[.5,.75])cases.push(make('DEV_'+n+'_'+rate+'_'+mix,n,rate,mix,'DEV'));
for(const n of[128,512,2048])for(const rate of[8,16])for(const mix of[.5,.75])cases.push(make('EVAL_'+n+'_'+rate+'_'+mix,n,rate,mix,'EVAL'));
write('INPUTS.json',{schema:'S26_A24_UNPROTECTED_INPUTS_V1',context_scope:'C0 only; synthetic request/mix/rate extrapolation',cases});
write('SOURCE_MAP.json',{source_pins:pins,packet:{path:packetPath,sha256:sha(fs.readFileSync(packetPath))},prior_immutable_results_preserved:true,preparation_only:true});
console.log(JSON.stringify({status:'SOURCE_AND_INPUT_PREPARED',train:12,dev:8,eval:12,new_environment:0}));
