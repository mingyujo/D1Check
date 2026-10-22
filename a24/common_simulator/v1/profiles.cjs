'use strict';
const path=require('path');
const V=path.resolve(__dirname,'../../a24_simulator/experiments/s26_virtual_transfer_20261018/vendor/s26_simulator/experiments');
const nativeTiming=require(path.join(V,'route_group_learning_v1/source/multi_timing.cjs'));
const nativeBase=require(path.join(V,'route_group_learning_v1/source/s26_simulator.cjs'));
const {Physics:NativeS26}=require(path.join(V,'route_group_learning_v1/physics.cjs'));
const labels={C:'classification',D:'detection'};
class A24Physics{
 constructor(data){this.data=data;this.c=data.config;this.T=data.initial_temperature_c;this.z=0;this.J=0;this.H=0;this.lastDynamic=0;this.time=35;this.ambient_c=this.c.idle_c;}
 clone(){const p=Object.create(A24Physics.prototype);Object.assign(p,this);return p;}
 exportState(){return {T:this.T,z:this.z,J:this.J,H:this.H,lastDynamic:this.lastDynamic,time:this.time};}
 temperature(){return this.T;}
 power(){return this.c.baseline+this.lastDynamic+this.data.shared*this.z;}
 speed(T,r){return Math.max(this.c.minimum_speed,1/(1+this.c.strength*(r==='CPU'?this.c.cpu_slope:this.c.gpu_slope)*Math.max(0,T-this.c.onset_c)));}
 advance(dt,owners){
  const c=this.c,T=this.T,z=this.z,shared=this.data.shared,decay=Math.exp(-dt/c.thermal_tau_s),one=-Math.expm1(-dt/c.thermal_tau_s);
  let dynamic=0;const leak=Math.exp(Math.max(-Math.log(3),Math.min(Math.log(3),c.strength*c.leakage_per_c*(T-c.reference_c))));
  for(const o of owners){const f=o.stage===1?this.speed(T,o.route):1;dynamic+=(this.data.solo[labels[o.task]+'_'+o.route]-shared)*((1-c.leakage_fraction)*f**3+c.leakage_fraction*leak);}
  let sharedE=0,force=0,area=0;
  if(owners.length){this.z=1;sharedE=shared*dt;force=c.thermal_resistance*(dynamic+shared)*one;area=c.thermal_resistance*(dynamic+shared)*(dt-c.thermal_tau_s*one);}
  else{const tz=c.idle_tail_s,tt=c.thermal_tau_s,oz=-Math.expm1(-dt/tz);this.z=z*Math.exp(-dt/tz);sharedE=shared*z*tz*oz;
   if(Math.abs(tz-tt)<1e-9){force=c.thermal_resistance*shared*z*dt/tt*decay;area=c.thermal_resistance*shared*z*tt*(1-(1+dt/tt)*decay);}
   else{const k=c.thermal_resistance*shared*z*tz/(tz-tt);force=k*(Math.exp(-dt/tz)-decay);area=k*(tz*oz-tt*one);}}
  this.T=c.idle_c+(T-c.idle_c)*decay+force;this.J+=c.baseline*dt+dynamic*dt+sharedE;this.H+=c.idle_c*dt+(T-c.idle_c)*c.thermal_tau_s*one+area;this.lastDynamic=dynamic;this.time+=dt;
 }
}
function a24Profile(data){
 const p={id:'A24',energy_unit:'J_PROXY',energy_scale:data.energy_scale,baselinePower:data.config.baseline,ambient_c:data.config.idle_c,
  allowed:{C:['CPU','GPU'],D:['CPU','GPU']},owner_capacity:{CPU:3,GPU:1,NPU:0},cpu_service_workers:3,
  resource_evidence:'Legacy A24 virtual CPU3 owners; unmeasured. Not identified device hardware capacity.',
  response_contract:{C:'output_ready',D:'persist_complete'},assumptions:['CPU3 and beta .25 are hypotheses','GPU path host service is unresolved in the five-stage legacy bank'],
  createPhysics:()=>new A24Physics(data),fromPublic:s=>Object.assign(new A24Physics(data),s),
  nominalPhases(q,r){const v=data.nominal[q.task+'_'+r];return v.map((work,k)=>({name:['DISPATCH_GAP','INFER','PERSIST','RELEASE','AVAILABLE_GAP'][k],work,cpu_service:r==='CPU'&&k===1,response_at:k===(q.task==='C'?1:2)?work:undefined}));},
  actualPhases(q,r){if(!q.private_work?.[r])throw Error('Explicit immutable actual work required');return p.nominalPhases(q,r).map((ph,k)=>({...ph,work:q.private_work[r][k],response_at:ph.response_at===undefined?undefined:q.private_work[r][k]}));},
  rate(o,owners,cpus,phys,offset){if(o.stage!==1)return 1;const preview=phys.clone();preview.advance(offset,owners);const n=owners.filter(x=>x.route==='CPU'&&x.stage===1&&cpus.has(x.id)).length;return preview.speed(preview.T,o.route)/(o.route==='CPU'?1+data.beta*Math.max(0,n-1):1);},
  publicRate(...args){return p.rate(...args);},advance:(phys,owners,cpus,dt)=>phys.advance(dt,owners),onDispatch:phys=>{phys.z=1;}
 };return p;
}
function activity(owners,cpus){const a=Array(9).fill(0);for(const o of owners){if(o.stage===2)a[['C_CPU','D_CPU','C_GPU','C_NPU'].indexOf(o.task+'_'+o.route)]++;else if(o.stage===1||o.stage===4)a[o.stage===1?4:5]++;else a[7]++;}a[6]=Number(owners.length>0);return a;}
class S26Physics{
 constructor(data,native=null){this.data=data;this.p=native??NativeS26.fromPast(data.power,data.thermal,data.context,data.pre_activity,35);this.J=this.p.J;this.H=this.p.H;this.ambient_c=data.context.skin+data.thermal.delta_C;this.time=this.p.time;}
 clone(){return new S26Physics(this.data,this.p.clone());}
 exportState(){const keys=['time','v','vd','z','box','heat','pending','J','H','anchor'];return Object.fromEntries(keys.map(k=>[k,structuredClone(this.p[k])]));}
 temperature(){return this.p.temperature();}power(){return this.p.power();}
 advance(dt,owners,cpus){this.p.active(activity(owners,cpus));this.p.advance(dt);this.J=this.p.J;this.H=this.p.H;this.time=this.p.time;}
}
function s26Profile(data){
 const packet=data.packet,nom=nativeTiming.nominal(packet),model=data.model;
 const p={id:'S26',energy_unit:'API_J',energy_scale:data.energy_scale,baselinePower:new S26Physics(data).p.B0,ambient_c:data.context.skin+data.thermal.delta_C,
  allowed:{C:['CPU','GPU','NPU'],D:['CPU']},owner_capacity:{CPU:1,GPU:1,NPU:1},cpu_service_workers:model.cpu_workers,
  resource_evidence:'One logical owner per backend; shared CPU service workers are a separate virtual hypothesis.',
  response_contract:{C:'output_ready',D:'readback_end'},assumptions:['CPU3 service workers are unmeasured','Detection GPU/NPU unsupported'],
  createPhysics:()=>new S26Physics(data),fromPublic:s=>{const phys=new S26Physics(data);Object.assign(phys.p,structuredClone(s));phys.J=phys.p.J;phys.H=phys.p.H;phys.time=phys.p.time;return phys;},
  nominalPhases(q,r,T=30){const route=labels[q.task]+'_'+r,x=nativeTiming.lengths(packet,nom,route,T,[],model,q.priority==='U'?'urgent':'normal');return [
   {name:'GAP',work:x.gap},{name:'ADMISSION',work:x.admission,cpu_work:nativeTiming.service(packet,route,'ADMISSION',x.admission,model)},
   {name:'INFER',work:1,cpu_service:r==='CPU',identity:nom[route].identity,residual:nom[route].residual},
   {name:'RETURN_GAP',work:x.ret,response_at:q.task==='C'?x.ret:undefined},
   {name:'POST',work:x.post,cpu_work:nativeTiming.service(packet,route,'POST',x.post,model),response_at:q.task==='D'?x.post*nom[route].readback_fraction:undefined}];},
  actualPhases(q,r,T){if(!q.private_phases?.[r])throw Error('Explicit immutable S26 route phases required');return structuredClone(q.private_phases[r]);},
  rate(o,owners,cpus,phys,offset){if(o.stage!==2)return 1;const preview=phys.clone();preview.advance(offset,owners,cpus);const ph=o.phases[o.stage],peers=owners.filter(x=>x!==o&&x.stage===2&&(x.route!=='CPU'||cpus.has(x.id))).map(x=>({route:labels[x.task]+'_'+x.route}));return 1/nativeTiming.duration(packet,ph.identity,preview.temperature(),peers,model,ph.residual);},
  publicRate(o,owners,cpus,phys,offset){const n={...o,phases:p.nominalPhases(o,o.route,phys.temperature())};return p.rate(n,owners.map(x=>x.id===o.id?n:x),cpus,phys,offset);},
  advance:(phys,owners,cpus,dt)=>phys.advance(dt,owners,cpus)
 };return p;
}
function matchedResourceScenario(profile){
 // Same experimental resource semantics; never labelled measured device capacity.
 const p={...profile,owner_capacity:{CPU:1,GPU:1,NPU:profile.allowed.C.includes('NPU')?1:0},cpu_service_workers:3,
  resource_evidence:'COMMON_BACKEND1_CPU3: shared hypothesis, one owner per supported backend and three shared CPU services.',
  resource_scenario:'COMMON_BACKEND1_CPU3',assumptions:[...profile.assumptions,'Host work uses a common full observed wall upper proxy, not measured CPU utilization.']};
 const convert=phases=>phases.map((ph,k)=>{const host=profile.id==='A24'?[2,3].includes(k):[1,4].includes(k);return {...ph,cpu_work:host?ph.work:ph.cpu_work};});
 p.nominalPhases=(...args)=>convert(profile.nominalPhases(...args));p.actualPhases=(...args)=>convert(profile.actualPhases(...args));
 return p;
}
function privateS26Phases(data,q,route,template){
 const full=labels[q.task]+'_'+route;if(template.route!==full||template.overlap_fraction!==0||template.priority_transfer)throw Error('Exact nonoverlap task/route template required');
 const identity={...template,domain:'M8_READBACK_RENAME_RESPONSE'},v=template.offset_s,admission=v.host_inference_start_ns-v.execution_start_ns,post=v.lane_available_ns-v.output_ready_ns;
 if(q.task==='D'&&!Number.isFinite(v.readback_end_ns))throw Error('Detection semantic response marker missing');
 return [{name:'GAP',work:v.execution_start_ns},
  {name:'ADMISSION',work:admission,cpu_work:nativeTiming.service(data.packet,full,'ADMISSION',admission,data.model)},
  {name:'INFER',work:1,cpu_service:route==='CPU',identity,residual:template.inference_s/nativeBase.timing(data.packet.timing,identity,template.AP??30,0)},
  {name:'RETURN_GAP',work:v.output_ready_ns-v.host_inference_return_ns,response_at:q.task==='C'?v.output_ready_ns-v.host_inference_return_ns:undefined},
  {name:'POST',work:post,cpu_work:nativeTiming.service(data.packet,full,'POST',post,data.model),response_at:q.task==='D'?v.readback_end_ns-v.output_ready_ns:undefined}];
}
module.exports={a24Profile,s26Profile,A24Physics,S26Physics,activity,matchedResourceScenario,privateS26Phases};
