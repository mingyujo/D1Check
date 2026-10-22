'use strict';
const fs=require('fs'),path=require('path'),crypto=require('crypto'),cp=require('child_process');
const H=__dirname,A=path.resolve(H,'../..'),R=path.dirname(A),P=path.join(A,'experiments/a24_s26_method_20261019'),read=p=>JSON.parse(fs.readFileSync(p)),save=(n,v)=>fs.writeFileSync(path.join(H,n),JSON.stringify(v,null,2)+'\n',{flag:'wx'});
const {make}=require('../a24_load_window_20261018/design.cjs');
function input(rate,duration,pattern,rep,phase,extra={}) {const c=make(rate,duration,pattern,rep,9);c.id=`CEM48_${phase}_R${rate*1000}_T${duration}_P${pattern}_S${rep}`;c.common_potential_key=['A24_CEM_MATCHED_20261019',rep,pattern];Object.assign(c.condition,extra);return c;}
const training=[];for(let si=0;si<2;si++)for(let g=1;g<=6;g++)for(let p=0;p<2;p++)training.push(input(g%2?.4:.55,g%2?60:120,p,100+si*10+g,'TRAIN',{learner_index:si,generation:g}));
const development=[...[[.4,60],[.55,120]].flatMap(([r,t])=>[0,1].map(p=>input(r,t,p,150,'DEV')))];
const evaluation=[...[[.4,60],[.55,120],[.7,120],[.55,240]].flatMap(([r,t])=>[0,1].map(p=>input(r,t,p,160,'EVAL')))];
save('POLICY_INPUTS.json',{training,development,evaluation,training_streams_shared_by_algorithms:true,evaluation_never_used_for_selection:true});
function pin(p){const b=fs.readFileSync(p);return {path:path.resolve(p),bytes:b.length,sha256:crypto.createHash('sha256').update(b).digest('hex')};}
const old=read(path.join(P,'OPERATION.json'));let pins=old.pins.map(p=>{const now=pin(p.path);if(now.sha256!==p.sha256)throw Error('Parent source drift '+p.path);return now;});
for(const n of ['learner.py','objective.py','run_policy.py','register_policy.cjs','preflight.py','POLICY_INPUTS.json','POLICY_PROTOCOL.md','BUDGET_RESERVATION.json','PREFLIGHT.json'])pins.push(pin(path.join(H,n)));
pins.push(pin(path.join(A,'results/A24_IDENTIFICATION_20261019_01/RESULT.json')));
for(const profile of old.profiles)pins.push(pin(path.join(A,'results/A24_S26_METHOD_20261019_01',profile+'.PPO.FINAL.pt.gz')));
pins=[...new Map(pins.map(p=>[p.path,p])).values()];
save('POLICY_OPERATION.json',{schema:'A24_MATCHED_CEM_PPO48_V1',utc:new Date().toISOString(),base_commit:cp.execFileSync('git',['rev-parse','HEAD'],{cwd:R,encoding:'utf8'}).trim(),parent:old.parent,profiles:old.profiles,policies:['FIFO_CPU','EDF_CPU','FIFO_GPU','EDF_GPU','TEACHER','OLD_PPO','INITIAL_S0','INITIAL_S1','CEM_S0','CEM_S1','PPO48_S0','PPO48_S1'],seeds:[202610191,202610193],planned_START:724,scientific_unit_cap:832,policy_environment_cap:736,conditional_extra_12_skipped:true,physical_fit_count:40,pins,output_dir:'results/A24_CEM_MATCHED_20261019_01',wall_clock_limit_s:14400,new_device:0,NPU:0});
console.log(JSON.stringify({TRAIN:training.length,DEV:development.length,EVAL:evaluation.length,pins:pins.length}));
