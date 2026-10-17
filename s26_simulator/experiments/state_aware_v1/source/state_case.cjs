'use strict';
const fs=require('fs'),crypto=require('crypto'),{Simulator}=require('./state_simulator.cjs'),read=p=>JSON.parse(fs.readFileSync(p,'utf8').replace(/^\uFEFF/,''));
const[packetPath,configPath,rawPath]=process.argv.slice(2),config=read(configPath),packet=read(packetPath),scenario=packet.scenarios.find(s=>s.id===config.scenario);
if(!scenario)throw Error('Scenario outside sealed packet');const sim=new Simulator(packet,scenario,config),result=sim.run();
result.planned_requests=sim.requests.map(q=>({ordinal:q.ordinal,task:q.task,priority:q.priority,arrival:q.arrival,deadline:q.deadline,readyAt:q.readyAt,enqueueTemplate:q.enqueueTemplate,burstIndex:q.burstIndex,completed:sim.done.some(o=>o.ordinal===q.ordinal)}));
result.active_at_censor=sim.owners.map(o=>({ordinal:o.ordinal,route:o.route,phase:o.phase,times:o.times,progress:o.progress}));result.logical_identity=config.identity;result.configuration_sha256=crypto.createHash('sha256').update(fs.readFileSync(configPath)).digest('hex');result.packet_sha256=crypto.createHash('sha256').update(fs.readFileSync(packetPath)).digest('hex');
const fd=fs.openSync(rawPath+'.part','wx');try{fs.writeFileSync(fd,JSON.stringify(result)+'\n');fs.fsyncSync(fd)}finally{fs.closeSync(fd)}fs.renameSync(rawPath+'.part',rawPath);
process.stdout.write(JSON.stringify({id:config.identity,on_time:result.service.all.on_time,completed:result.service.all.completed,J:result.J_API0_180,AP:result.AP35_180_mean,routes:result.policy_route_counts,decisions:result.policy_decisions.length})+'\n');
