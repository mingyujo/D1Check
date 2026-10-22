'use strict';
const fs=require('fs'),path=require('path'),z=require('zlib'),H=__dirname,R=path.resolve(H,'../..');
const read=p=>JSON.parse((p.endsWith('.gz')?z.gunzipSync(fs.readFileSync(p)):fs.readFileSync(p)).toString('utf8').replace(/^\uFEFF/,''));
const policy=require('./policy.cjs'),{MultiSimulator}=require('./source/multi_simulator.cjs');
const packet=read(path.join(R,'experiments/multiresource_v1/PACKET.json.gz')),cases=read(path.join(H,'INPUTS.json')).cases,protocol=read(path.join(H,'PROTOCOL.json'));
const power=read(path.join(R,'experiments/capacity_power_v1/artifacts/G001/MODEL.json')),thermal=read(path.join(R,'experiments/pipeline_thermal_v1/artifacts/G001/MODEL.json'));
packet.multi.models.CPU3={...packet.multi.models.CENTRAL,cpu_workers:3};
let buffer='';function line(){const b=Buffer.alloc(65536);while(!buffer.includes('\n')){let n;try{n=fs.readSync(0,b);}catch(e){if(e.code==='EAGAIN')continue;throw e;}if(!n)return null;buffer+=b.toString('utf8',0,n);}const at=buffer.indexOf('\n'),s=buffer.slice(0,at);buffer=buffer.slice(at+1);return s;}
function send(x){const b=Buffer.from(JSON.stringify(x)+'\n');let at=0;while(at<b.length){try{at+=fs.writeSync(1,b,at,b.length-at);}catch(e){if(e.code==='EAGAIN')continue;throw e;}}}
for(;;){const l=line();if(l===null)break;const cmd=JSON.parse(l);let sim;try{
 const c=cases.find(c=>c.id===cmd.input);if(!c)throw Error('Unregistered input');
 policy.configure({mode:'MATCHED_ROLLING',variant:'REPAIR',balance:{scales:protocol.shared_scores.scales,dual:[.98,.98],classFactors:[1,1],tail:.02,rank_feature:true},choose:bank=>{send({type:'BANK',bank});const reply=JSON.parse(line());if(!Number.isInteger(reply.index))throw Error('Expected selector index');return reply.index;}});
 sim=new MultiSimulator(packet,{id:c.id,context:c.context,requests:c.requests},{stream:c.stream,model:'CPU3',capacity:3,policy:'MATCHED_ROLLING',allocator:'NO_POST_SELECTOR_ALLOCATOR',dt_s:.01,power_dt_s:.025,horizon_s:c.horizon_s,dispatch_stop_s:c.dispatch_stop_s,censor_s:c.censor_s,forecast_cap:1000000,nominal_event_cap:20000,power_model:power,thermal_model:thermal});
 send({type:'DONE',result:sim.run()});
}catch(error){send({type:'FAIL',error:String(error.stack||error),time:sim?.time,public_observation:sim?.publicObservation(),activity:sim?.intervals,phase_trace:sim?.phase_trace,sensor:sim?.sensorTrace,automatic_retry:false});}}
