'use strict';
const fs=require('fs'),path=require('path'),z=require('zlib'),H=__dirname,S=path.resolve(H,'../..');
const read=p=>JSON.parse((p.endsWith('.gz')?z.gunzipSync(fs.readFileSync(p)):fs.readFileSync(p)).toString('utf8').replace(/^\uFEFF/,''));
const delegate=require('./policy.cjs'),protocol=read(path.join(H,'PROTOCOL.json')),cases=read(path.join(H,'INPUTS.json')).cases;
let buffer='';function line(){const b=Buffer.alloc(65536);while(!buffer.includes('\n')){let n;try{n=fs.readSync(0,b);}catch(e){if(e.code==='EAGAIN')continue;throw e;}if(!n)return null;buffer+=b.toString('utf8',0,n);}const at=buffer.indexOf('\n'),s=buffer.slice(0,at);buffer=buffer.slice(at+1);return s;}
function send(x){const b=Buffer.from(JSON.stringify(x)+'\n');let at=0;while(at<b.length){try{at+=fs.writeSync(1,b,at,b.length-at);}catch(e){if(e.code==='EAGAIN')continue;throw e;}}}
const originalPolicy=require.resolve('../rolling_rl_ablation_v1/policy.cjs');require.cache[originalPolicy]={id:originalPolicy,filename:originalPolicy,loaded:true,exports:delegate};
const {MultiSimulator}=require('../rolling_rl_ablation_v1/source/multi_simulator.cjs');
const packet=read(path.join(S,'experiments/multiresource_v1/PACKET.json.gz')),power=read(path.join(S,'experiments/capacity_power_v1/artifacts/G001/MODEL.json')),thermal=read(path.join(S,'experiments/pipeline_thermal_v1/artifacts/G001/MODEL.json'));
packet.multi.models.CPU3={...packet.multi.models.CENTRAL,cpu_workers:3};
let sim;
try{
 const cmd=JSON.parse(line()),c=cases.find(c=>c.id===cmd.input),m=protocol.methods.find(m=>m.id===cmd.method);if(!c||!m)throw Error('Unregistered identity');
 delegate.configure({mode:m.mode??'MATCHED_ROLLING',variant:'REPAIR',useRolling:m.rolling,useATC:m.ATC,standalone:m.standalone??false,guardMode:cmd.method,balance:{scales:protocol.shared_scores.scales,dual:[.98,.98],classFactors:[1,1],tail:.02,rank_feature:true},choose:bank=>{
  const recent=delegate.contextStats().task_seen.slice(-64),mix=recent.length<16?.75:recent.filter(q=>q.task==='classification').length/recent.length,s=protocol.shared_scores.scales;
  bank={...bank,original_scores:bank.scores,scores:bank.forecasts.map(f=>f.cost[0]/s[0]+f.cost[1]/s[1]+.98*f.cost[2]/Math.max(1/64,mix)+.98*f.cost[3]/Math.max(1/64,1-mix)+3*f.cost[4]),public_recent_mix:mix};
  send({type:'BANK',bank});const reply=JSON.parse(line());if(!Number.isInteger(reply.index))throw Error('Expected selector index');return reply.index;
 }});
 sim=new MultiSimulator(packet,{id:c.id,context:c.context,requests:c.requests},{stream:c.stream,model:'CPU3',capacity:3,policy:'MATCHED_ROLLING',allocator:'NO_POST_SELECTOR_ALLOCATOR',dt_s:.01,power_dt_s:.025,horizon_s:c.horizon_s,dispatch_stop_s:c.dispatch_stop_s,censor_s:c.censor_s,forecast_cap:1000000,nominal_event_cap:20000,power_model:power,thermal_model:thermal});
 send({type:'DONE',result:sim.run(),telemetry:delegate.telemetry()});
}catch(error){send({type:'FAIL',error:String(error.stack||error),time:sim?.time,public_observation:sim?.publicObservation(),activity:sim?.intervals,phase_trace:sim?.phase_trace,sensor:sim?.sensorTrace,automatic_retry:false});process.exitCode=1;}
