'use strict';
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto'),zlib=require('node:zlib');
const HERE=__dirname,ROOT=path.resolve(HERE,'../..'),OLD=path.join(ROOT,'experiments/multiresource_v1/source/MULTI001_G004');
const hash=b=>crypto.createHash('sha256').update(b).digest('hex');
const save=(n,x)=>fs.writeFileSync(path.join(HERE,n),JSON.stringify(x,null,2)+'\n',{flag:'wx'});
function replace(text,from,to,n=1){const count=text.split(from).length-1;if(count!==n)throw Error('Source pattern count '+from+' '+count);return text.split(from).join(to)}
const files=['s26_simulator.cjs','multi_simulator.cjs','multi_actions.cjs','multi_cost.cjs','nominal_rollout.cjs','multi_timing.cjs','resource_contract.cjs','midpoint_work.cjs','dynamic_cost_math_v2.cjs'];
fs.mkdirSync(path.join(HERE,'source'),{recursive:true});const pins=[];
for(const name of files){const original=fs.readFileSync(path.join(OLD,name));let text=original.toString('utf8');
 if(name==='s26_simulator.cjs'){
  text=replace(text,"timing_variant:'CENTRAL',...config","timing_variant:'CENTRAL',horizon_s:180,dispatch_stop_s:120,censor_s:150,forecast_cap:5000,nominal_event_cap:20000,...config");
  text=text.replaceAll('this.time>=120','this.time>=this.config.dispatch_stop_s').replaceAll('this.time<120','this.time<this.config.dispatch_stop_s').replaceAll('120-this.time','this.config.dispatch_stop_s-this.time').replaceAll('Math.min(120,','Math.min(this.config.dispatch_stop_s,');
  text=text.replaceAll('this.time<180','this.time<this.config.horizon_s').replaceAll('180-this.time','this.config.horizon_s-this.time').replaceAll('this.time>=150','this.time>=this.config.censor_s').replaceAll('this.time<150','this.time<this.config.censor_s').replaceAll('150-this.time','this.config.censor_s-this.time');
  text=replace(text,'end=this.censored?150:180','end=this.censored?this.config.censor_s:this.config.horizon_s');
  text=replace(text,'A/145','A/(this.config.horizon_s-35)');
  text=replace(text,'J_API0_180:this.censored?null:J','J_observed_prefix:J,J_API0_180:this.censored?null:J');
 }
 if(name==='multi_simulator.cjs'){
  text=replace(text,'return {time:this.time,capacity:this.config.capacity','return {time:this.time,horizon_s:this.config.horizon_s,nominal_event_cap:this.config.nominal_event_cap,capacity:this.config.capacity');
  text=text.replaceAll('this.time<180','this.time<this.config.horizon_s').replaceAll('180-this.time','this.config.horizon_s-this.time').replaceAll('this.time>=150','this.time>=this.config.censor_s').replaceAll('this.time<150','this.time<this.config.censor_s').replaceAll('150-this.time','this.config.censor_s-this.time').replaceAll('this.time<120','this.time<this.config.dispatch_stop_s').replaceAll('120-this.time','this.config.dispatch_stop_s-this.time');
  text=replace(text,"this.nominal_forecasts>5000","this.nominal_forecasts>this.config.forecast_cap");
  text=replace(text,'this.decisions.push({time:this.time,public_observation:obs,action:a});',"this.decisions.push({time:this.time,public_observation:{...obs,cost_state:{...obs.cost_state,activity9:{encoding:'FINAL_ACTIVITY_PREFIX',at:obs.time}}},action:a});");
  text=replace(text,"generation:'MULTI001_G004'","generation:'SUSTAINED001_G001',observation_horizon_s:this.config.horizon_s,dispatch_stop_s:this.config.dispatch_stop_s,censor_s:this.config.censor_s");
 }
 if(name==='nominal_rollout.cjs'){
  text=replace(text,'if(++calls>20000)','if(++calls>(obs.nominal_event_cap??20000))');
  text=replace(text,"if(time>180)throw Error('Nominal completion outside180; do not truncate silently');","if(time>(obs.horizon_s??180))throw Error('Nominal completion outside registered horizon');");
  text=replace(text,'?180-x.deadline','?(obs.horizon_s??180)-x.deadline');
 }
 if(name==='multi_cost.cjs')text=fs.readFileSync(path.join(HERE,'fast_cost.cjs'),'utf8');
 const bytes=Buffer.from(text);fs.writeFileSync(path.join(HERE,'source',name),bytes,{flag:'wx'});pins.push({name,parent_sha256:hash(original),source_sha256:hash(bytes),changed:hash(original)!==hash(bytes)});
}
const packet=JSON.parse(zlib.gunzipSync(fs.readFileSync(path.join(ROOT,'experiments/multiresource_v1/PACKET.json.gz'))));
const context=packet.scenarios.find(s=>s.context_index===0).context;
const designs=[['SHORT',128,16],['LONG64',512,64],['LONG256',2048,256],['DENSE64',2048,64]];
const inputs=designs.map(([id,n,duration])=>({id,n,duration_s:duration,context,requests:Array.from({length:n},(_,i)=>{const group=Math.floor(i/16),within=i%16,isDet=(within+group+2)%4===0;return {ordinal:i,offset_ns:Math.round((35+group*duration/(n/16))*1e9),task_id:isDet?'detection':'classification',priority:isDet?'normal':'urgent',deadline_ms:isDet?2000:800,synthetic_request_id:'SUSTAINED_'+id+'_'+i}})}));
save('SOURCE_MAP.json',{generation:'SUSTAINED001_G001',files:pins,parent_core_sha256:hash(fs.readFileSync(path.join(ROOT,'CORE_MANIFEST.json')))});
save('INPUTS.json',{schema:'S26_SUSTAINED_INPUT_V1',stream:271020701,inputs});
console.log(JSON.stringify({status:'PREPARED_NOT_EXECUTED',sources:files.length,inputs:inputs.map(x=>({id:x.id,n:x.n,duration_s:x.duration_s})),new_environments:0}));
