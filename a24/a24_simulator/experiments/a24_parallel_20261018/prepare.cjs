const fs=require('fs'),path=require('path'),crypto=require('crypto'),cp=require('child_process');
const H=__dirname,A=path.resolve(H,'../..'),R=path.dirname(A),sha=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex'),read=p=>JSON.parse(fs.readFileSync(p)),save=(p,v)=>fs.writeFileSync(p,JSON.stringify(v,null,2)+'\n',{flag:'wx'}),pin=p=>({path:path.resolve(p),bytes:fs.statSync(p).size,sha256:sha(p)});
let engine=fs.readFileSync(path.join(A,'experiments/public_transfer_20261018/event_engine.py'),'utf8');
const changes=[
 ["from dynamics import NS,advance_jobs,objectives,weighted","from dynamics import NS,objectives,weighted\nfrom physics_parallel import advance_jobs"],
 ["len(owners)<2","len(owners)<physics.cpu_slots+1"],
 ["rid not in queue or route in owners or route not in ('CPU','GPU')","rid not in queue or route not in ('CPU','GPU') or sum(j['route']==route for j in owners.values()) >= (physics.cpu_slots if route=='CPU' else 1)"],
 ["owners[route]=dict(request_id=rid","slot=next(i for i in range(physics.cpu_slots if route=='CPU' else 1) if (route,i) not in owners)\n            owners[route,slot]=dict(request_id=rid"],
 ["rate=physics.speed(state['temperature_c'],j['route'],j['stage'])","rate=physics.rates(state['temperature_c'],list(owners.values()))[j['request_id']]"],
 ["('task','route','stage')","('request_id','task','route','stage')"],
 ["dt*terms['speeds'][j['route']]","dt*terms['speeds'][j['request_id']]"],
 ["t['speeds'][r['route']]","t['speeds'][r['request_id']]"],
 ["event_wait=dict(start_ns=now,owners={r:j['request_id'] for r,j in owners.items()},","event_wait=dict(start_ns=now,owners={r:j['request_id'] for r,j in owners.items()},"],
];
for(const [before,after] of changes){if(!engine.includes(before))throw Error('Missing transformation '+before);engine=engine.replaceAll(before,after);}
// Tuple slot keys are internal only; WAIT metadata records plain lists.
engine=engine.replace("new_pair_progress='EXPLICIT_INDEPENDENT_PLUS_THERMAL_SPEED'","new_pair_progress='VIRTUAL_MULTI_CPU_POSITIVE_POWER_WITH_CONTENTION'");
fs.writeFileSync(path.join(H,'engine_parallel.py'),engine,{flag:'wx'});
save(path.join(H,'ENGINE_DERIVATION.json'),{parent:pin(path.join(A,'experiments/public_transfer_20261018/event_engine.py')),changes,child:pin(path.join(H,'engine_parallel.py')),original_overwritten:false});
const base=read(path.join(A,'experiments/public_transfer_20261018/OPERATION.json'));
const profiles=[{id:'CPU1_B0_K1',slots:1,beta:0,k:1},{id:'CPU2_B25_K1',slots:2,beta:.25,k:1},{id:'CPU3_B25_K1',slots:3,beta:.25,k:1},{id:'CPU3_B0_K1',slots:3,beta:0,k:1},{id:'CPU3_B25_K2',slots:3,beta:.25,k:2}];
const ids=[100,200,300].flatMap(n=>[0,1].map(p=>'DENSITY_'+n+'_'+p));
const sources=[...base.sources,...fs.readdirSync(H).filter(n=>/\.(py|cjs|md)$/.test(n)).map(n=>pin(path.join(H,n)))];
const unique=xs=>[...new Map(xs.map(p=>[p.path.toLowerCase(),p])).values()];
save(path.join(H,'BUDGET_RESERVATION.json'),{conservative_before:133494,new_reservation:240,conservative_after:133734,shared_cap:137712,not_fresh_all_host_census:true,no_refunds:true,planned_environments:228,BC_fits:1,planned_scientific_units:229});
save(path.join(H,'OPERATION.json'),{schema:'A24-VIRTUAL-CPU-PARALLEL-V1',utc:new Date().toISOString(),base_commit:cp.execFileSync('git',['rev-parse','HEAD'],{encoding:'utf8'}).trim(),output_dir:'results/A24_PARALLEL_20261018_01',physics:base.physics,registration:base.registration,inputs:base.inputs,bank_map:base.bank_map,public_nominals:base.public_nominals,reward_references:base.reward_references,profiles,primary:'CPU3_B25_K1',evaluation_ids:ids,teacher_profile_indices:[2,1,2,0,2,1,2,0],policies:['FIFO_CPU','EDF_CPU','FIFO_GPU','EDF_GPU','PUBLIC_COST','BC','PPO'],seed:10881087,BC_epochs:64,PPO_train:8,PPO_updates:4,checkpoint_selection:'EP8 fixed before new evaluation',planned_START:228,scientific_unit_cap:240,wall_clock_limit_s:10800,own_Python_limit:1,global_Python_limit:3,single_threaded:true,private_A24_mutex:'runtime/a24_local_worker.lock',sources:unique(sources),input_pins:unique(base.input_pins.concat([base.inputs,base.public_nominals,...Object.values(base.bank_map),pin(path.join(A,'results/STATE_COST_IDENTIFICATION_20261017_01/MODEL.json'))])),formal_untouched_holdout:false,original_NN_reused:false,S26_coefficients_reused:false,new_fit:0,new_device:0,automatic_retry:false});
const note='## 2026-10-18 A24·S26 별도 결론 및 A24 가상 CPU 병렬 진단 사전등록\n\n최신 사용자 결정은 기기별 결론 우선·불성립 시 S26 중심이다. 원 A24 부정 결과와 S26 CPU1 손해를 보존하며 A24 고유 시간/전력/RC 가설에서 CPU 슬롯1/2/3·경합0/.25·열저항1/2배의5프로필×원6부하×7정책을 진단한다. 새 공개 슬롯특징/BC1fit/PPO8회4update, 총228환경/229과학단위 cap240·보수133734/137712 snapshot을 사전 고정한다. S26 계수/가중치 전용0·실측0·전력/경합은 가상이며 전체 손해/미완료를 공개한다. [설계](../a24_simulator/experiments/a24_parallel_20261018/README.md). 현재 새 환경0·S26 진행 중과 자원 mutex를 공유하며 순차 실행한다.\n\n';
for(const n of ['PROJECT_STATUS.md','PROJECT_PLAN.md','DECISIONS.md']){const p=path.join(R,'docs',n);fs.writeFileSync(p,note+fs.readFileSync(p,'utf8'));}
console.log(JSON.stringify({registered:true,planned:228,scientific_units:229,new_native:0,sources:sources.length}));
