'use strict';
// One event loop for both devices and visible-only nominal rollout.
const {validateProfile,validateRequests,legal,publicRequest}=require('./contract.cjs');
const EPS=1e-10;
class Engine{
 constructor(profile,requests,physics,{start_s=35,end_s=65,dispatch_stop_s=end_s,mode='CONFORMANCE',receipt=null,nominal=false,event_cap=50000,tick_s=.05}={}){
  this.p=validateProfile(profile);validateRequests(requests);
  if(!['CONFORMANCE','NOMINAL','REGISTERED'].includes(mode))throw Error('Explicit run mode');
  if(mode==='NOMINAL'&&!nominal)throw Error('Nominal mode cannot execute private actual work');
  if(!(end_s>start_s&&Number.isFinite(end_s)&&tick_s>0&&Number.isInteger(event_cap)&&event_cap>0))throw Error('Finite clock/step/cap required');
  if(!Number.isFinite(physics.time)||Math.abs(physics.time-start_s)>1e-8)throw Error('Physics and event clock must share the same start');
  if(mode==='REGISTERED'&&(!receipt?.start_id||receipt.durable_START_consumed!==true))throw Error('Durable registered START required');
  if(mode==='CONFORMANCE'&&requests.some(q=>q.source_kind!=='SYNTHETIC'))throw Error('Measured workloads require registered mode');
  this.requests=structuredClone(requests).sort((a,b)=>a.ready_s-b.ready_s||a.ordinal-b.ordinal);this.at=0;this.time=start_s;this.end=end_s;this.stop=dispatch_stop_s;this.tick=tick_s;this.cap=event_cap;this.nominal=nominal;
  this.physics=physics;this.ready=[];this.owners=[];this.done=[];this.decisions=[];this.trace=[];this.events=[];this.grants=new Map;this.ticket=0;this.waitUntil=start_s;this.eventWait=null;this.wait_used_s=0;this.capped=false;
 }
 clone(){const copy=Object.create(Engine.prototype);Object.assign(copy,this);for(const k of ['requests','ready','owners','done','decisions','trace','events','eventWait'])copy[k]=structuredClone(this[k]);copy.grants=new Map(this.grants);copy.physics=this.physics.clone();return copy;}
 snapshot(){return {time_s:this.time,queue:this.ready.map(publicRequest),owners:this.owners.map(o=>({...publicRequest(o),route:o.route,stage:o.stage,phase_elapsed_s:o.phase_elapsed_s,phase_progress_public:o.public_progress,response_s:o.response_s,dispatch_s:o.dispatch_s})),sensor:{temperature_c:this.physics.temperature(),ambient_c:this.physics.ambient_c,power:this.physics.power(),cost_state:this.physics.exportState()},wait_used_s:this.wait_used_s,dispatch_stop_s:this.stop};}
 phase(o){return o.phases[o.stage];}
 enter(o){o.progress=0;o.public_progress=0;o.phase_elapsed_s=0;o.ticket=++this.ticket;}
 settle(){
  for(const o of this.owners.slice())for(let k=0;k<32&&this.owners.includes(o);k++){
   const ph=this.phase(o);
   if(o.response_s===null&&Number.isFinite(ph.response_at)&&o.progress>=ph.response_at-EPS){o.response_s=this.time;this.events.push({kind:'RESPONSE',id:o.id,time_s:this.time});}
   if(o.progress<ph.work-EPS)break;
   o.stage++;if(o.stage===o.phases.length){o.available_s=this.time;this.owners.splice(this.owners.indexOf(o),1);this.done.push(o);this.events.push({kind:'AVAILABLE',id:o.id,time_s:this.time});break;}this.enter(o);
  }
 }
 admit(){let fresh=false;while(this.at<this.requests.length&&this.requests[this.at].ready_s<=this.time+EPS){this.ready.push(this.requests[this.at++]);fresh=true;}return fresh;}
 cpuEligible(o){const ph=this.phase(o);return ph.cpu_service===true||Number.isFinite(ph.cpu_work)&&o.progress<ph.cpu_work-EPS;}
 selectCPU(){
  const eligible=this.owners.filter(o=>this.cpuEligible(o)),retained=eligible.filter(o=>this.grants.get(o.id)===o.stage),rest=eligible.filter(o=>!retained.includes(o)).sort((a,b)=>a.ticket-b.ticket||a.ordinal-b.ordinal);
  const chosen=retained.concat(rest).slice(0,this.p.cpu_service_workers);this.grants=new Map(chosen.map(o=>[o.id,o.stage]));return new Set(chosen.map(o=>o.id));
 }
 dispatch(a){
  const q=this.ready.find(q=>q.id===a.id);if(!q||!legal(this.p,q,a.route,this.owners))throw Error('Illegal dispatch');
  const phases=this.nominal?this.p.nominalPhases(q,a.route,this.physics.temperature()):this.p.actualPhases(q,a.route,this.physics.temperature());
  if(!phases.length||phases.some(x=>!Number.isFinite(x.work)||x.work<0))throw Error('Invalid phase vector');
  const o={...publicRequest(q),route:a.route,phases:structuredClone(phases),stage:0,response_s:null,available_s:null,dispatch_s:this.time};this.enter(o);this.owners.push(o);this.ready.splice(this.ready.indexOf(q),1);this.events.push({kind:'DISPATCH',id:o.id,route:o.route,time_s:this.time});this.p.onDispatch?.(this.physics);this.settle();
 }
 apply(a){
  if(a.kind==='DISPATCH')this.dispatch(a);
  else if(a.kind==='WAIT'){if(!(a.wait_s>0&&Number.isFinite(a.wait_s)))throw Error('Positive WAIT required');this.waitUntil=Math.min(this.stop,this.time+a.wait_s);this.wait_used_s+=this.waitUntil-this.time;}
  else if(a.kind==='WAIT_EVENT'){if(!this.owners.length)throw Error('WAIT_EVENT requires owner');this.eventWait={ids:this.owners.map(o=>o.id),start:this.time};}
  else if(a.kind!=='RESOURCE_WAIT')throw Error('Unknown action');
 }
 advance(){
  const cpus=this.selectCPU();let dt=Math.min(this.tick,this.end-this.time);
  for(const t of [this.requests[this.at]?.ready_s,this.waitUntil,this.stop])if(t>this.time+EPS)dt=Math.min(dt,t-this.time);
  const working=this.owners.filter(o=>!this.cpuEligible(o)||cpus.has(o.id));
  const rate=(o,d)=>this.p.rate(o,this.owners,cpus,this.physics,d);
  const boundaries=o=>{const ph=this.phase(o),xs=[ph.work];if(Number.isFinite(ph.cpu_work)&&ph.cpu_work>o.progress+EPS)xs.push(ph.cpu_work);if(o.response_s===null&&Number.isFinite(ph.response_at)&&ph.response_at>o.progress+EPS)xs.push(ph.response_at);return Math.min(...xs)-o.progress;};
  for(const o of working){const rem=boundaries(o);if(rem<=EPS)throw Error('Unsettled phase boundary');if(dt*rate(o,dt/2)>=rem){let lo=0,hi=dt;for(let k=0;k<48;k++){const mid=(lo+hi)/2;if(mid*rate(o,mid/2)>=rem)hi=mid;else lo=mid;}dt=(lo+hi)/2;}}
  if(!(dt>0&&Number.isFinite(dt)))throw Error('Nonpositive event step');
  const rates=working.map(o=>[o,rate(o,dt/2),this.p.publicRate(o,this.owners,cpus,this.physics,dt/2)]),T=this.physics.temperature(),J=this.physics.J,H=this.physics.H,cost_state=this.physics.exportState();
  this.p.advance(this.physics,this.owners,cpus,dt);
  for(const o of this.owners){o.phase_elapsed_s+=dt;const r=rates.find(x=>x[0]===o);if(r){o.progress+=dt*r[1];o.public_progress+=dt*r[2];}}
  this.trace.push({start_s:this.time,end_s:this.time+dt,J:this.physics.J-J,H:this.physics.H-H,T,next_T:this.physics.temperature(),cost_state,owners:this.owners.map(o=>({id:o.id,task:o.task,route:o.route,stage:o.stage})),cpu_services:[...cpus]});this.time+=dt;
 }
 run(selector){
  let steps=0;
  while(this.time<=this.end+EPS){
   this.settle();const arrived=this.admit();
   if(this.eventWait&&(arrived||this.eventWait.ids.some(id=>!this.owners.some(o=>o.id===id))||this.time>=this.stop-EPS)){this.wait_used_s+=this.time-this.eventWait.start;this.eventWait=null;}
   if(this.time>=this.end-EPS)break;
   if(++steps>this.cap){this.capped=true;break;}
   let micro=0;
   while(this.ready.length&&this.time<this.stop-EPS&&this.time>=this.waitUntil-EPS&&!this.eventWait){
    if(++micro>this.requests.length+100)throw Error('Micro decision cap');const s=this.snapshot(),a=selector(s);
    if(a.kind==='RESOURCE_WAIT')break;
    this.decisions.push({time_s:this.time,public_state:s,action:structuredClone(a)});this.apply(a);if(a.kind!=='DISPATCH')break;
   }
   this.advance();
  }
  this.settle();return this;
 }
}
module.exports={Engine,EPS};
