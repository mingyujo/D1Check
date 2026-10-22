'use strict';
const {Engine}=require('./engine.cjs'),method=require('./method.cjs'),{publicRequest}=require('./contract.cjs'),{service}=require('./evaluation.cjs'),{describe}=require('./bridge.cjs');
function runRegistered(profile,requests,options){
 if(!options?.receipt?.start_id||!options.receipt.durable_START_consumed)throw Error('A new registered workload START is required');
 if(profile.resource_scenario!=='COMMON_BACKEND1_CPU3')throw Error('Common study requires matched resource scenario');
 if(!['FIFO','EDF','LSF','RR','TEACHER','BC'].includes(options.policy))throw Error('Explicit shared policy');
 if(options.policy==='BC'&&typeof options.choose!=='function')throw Error('New common-schema BC checkpoint selector required; no teacher fallback');
 const engine=new Engine(profile,requests,profile.createPhysics(),{...options,mode:'REGISTERED'}),banks=[];
 const start_s=engine.time,startJ=engine.physics.J,startH=engine.physics.H;
 const direct=['FIFO','EDF','LSF','RR'].includes(options.policy)?method.baseline(profile,options.policy):null;
 const selector=s=>{
  if(direct)return direct(s);
  const bank=method.encode(profile,s,{idle_filter:options.idle_filter!==false,max_steps:800});if(!bank)return {kind:'RESOURCE_WAIT'};
  const index=options.policy==='TEACHER'?method.teacher(bank):options.choose(bank);
  if(!Number.isInteger(index)||!bank.mask[index])throw Error('Illegal common selector action; no override');
  banks.push({time_s:s.time_s,bank,index});return bank.actions[index];
 };
 engine.run(selector);
 const returned=new Map([...engine.done,...engine.owners].map(o=>[o.id,o]));
 const records=requests.map(q=>{const o=returned.get(q.id);return {...publicRequest(q),route:o?.route??null,response_s:o?.response_s??null,available_s:o?.available_s??null,dispatch_s:o?.dispatch_s??null};});
 return {version:method.VERSION,status:engine.capped?'FAIL_EVENT_CAP':'COMPLETE',receipt:options.receipt,profile:describe(profile),policy:options.policy,records,service:service(records,engine.end),J:engine.capped?null:engine.physics.J-startJ,H:engine.capped?null:engine.physics.H-startH,start_s,end_s:engine.end,preparation_J:startJ,partial_integrals:engine.capped?{J:engine.physics.J-startJ,H:engine.physics.H-startH,through_s:engine.time}:null,energy_unit:profile.energy_unit,trace:engine.trace,events:engine.events,decisions:engine.decisions,banks,no_post_NN_override:true,new_training:0};
}
module.exports={runRegistered};
