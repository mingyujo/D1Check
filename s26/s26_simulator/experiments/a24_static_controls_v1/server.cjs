'use strict';
const fs=require('node:fs'),path=require('node:path'),z=require('node:zlib'),H=__dirname,R=path.resolve(H,'../..');
const read=p=>JSON.parse((p.endsWith('.gz')?z.gunzipSync(fs.readFileSync(p)):fs.readFileSync(p)).toString('utf8').replace(/^\uFEFF/,''));
const policy=require('./policy.cjs'),{MultiSimulator}=require('./source/multi_simulator.cjs');
const packet=read(path.join(R,'experiments/multiresource_v1/PACKET.json.gz')),inputs=read(path.join(H,'INPUTS.json')).cases;
const power=read(path.join(R,'experiments/capacity_power_v1/artifacts/G001/MODEL.json')),thermal=read(path.join(R,'experiments/pipeline_thermal_v1/artifacts/G001/MODEL.json'));
let buffer='';function line(){const b=Buffer.alloc(65536);while(!buffer.includes('\n')){let n;try{n=fs.readSync(0,b);}catch(e){if(e.code==="EAGAIN")continue;throw e;}if(!n)return null;buffer+=b.toString('utf8',0,n);}const at=buffer.indexOf('\n'),s=buffer.slice(0,at);buffer=buffer.slice(at+1);return s;}
const send=x=>{const b=Buffer.from(JSON.stringify(x)+"\n");let at=0;while(at<b.length){try{at+=fs.writeSync(1,b,at,b.length-at);}catch(e){if(e.code==="EAGAIN")continue;throw e;}}};
for(;;){const l=line();if(l===null)break;const cmd=JSON.parse(l);let sim;try{
 const c=inputs.find(x=>x.id===cmd.input);if(!c)throw Error('Unregistered input');
 policy.configure({mode:cmd.mode,choose:bank=>{send({type:'BANK',bank});const m=JSON.parse(line());if(!Number.isInteger(m.index))throw Error('Expected NN index');return m.index;}});
 sim=new MultiSimulator(packet,{id:c.id,context:c.context,requests:c.requests},{stream:cmd.stream,model:'CENTRAL',capacity:3,policy:cmd.mode,allocator:'NO_POST_NN_ALLOCATOR',dt_s:cmd.dt_s??.01,power_dt_s:.025,horizon_s:c.horizon_s,dispatch_stop_s:c.dispatch_stop_s,censor_s:c.censor_s,forecast_cap:1000000,nominal_event_cap:20000,power_model:power,thermal_model:thermal});
 const result=sim.run();send({type:'DONE',result});
 }catch(error){send({type:'FAIL',error:String(error.stack||error),time:sim?.time,public_observation:sim?.publicObservation(),activity:sim?.intervals,phase_trace:sim?.phase_trace,sensor:sim?.sensorTrace,physics:sim?.physics,done:sim?.done?.map(o=>({ordinal:o.ordinal,response:o.response,times:o.times})),automatic_retry:false});}}
