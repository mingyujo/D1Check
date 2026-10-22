import ast,datetime,hashlib,json,msvcrt,re,shutil,time
from pathlib import Path
W=Path(__file__).resolve().parents[1];R=W/'S26-D1Check';S=R/'s26_simulator';P=S/'experiments/final_three_policy_v1';H=S/'experiments/final_four_rr_v1'
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8-sig'))
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def put(p,x):
 with Path(p).open('x',encoding='utf-8',newline='\n') as f:json.dump(x,f,ensure_ascii=False,indent=2);f.write('\n')
def text(p,s):Path(p).write_text(s,encoding='utf-8',newline='\n')
utc=datetime.datetime.now(datetime.timezone.utc).isoformat();assert not H.exists();assert read(P/'artifacts/G001/AUDIT.json')['status']=='PASS'
lock=(W/'D1Check/a24_simulator/runtime/worker.lock').open('r+b');locked=False;deadline=time.monotonic()+300
try:
 while not locked:
  try:lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1);locked=True
  except OSError:
   if time.monotonic()>deadline:raise
   print('WAIT_SHARED_REGISTRATION_LOCK',flush=True);time.sleep(10)
 H.mkdir();(H/'source').mkdir();(H/'history').mkdir()
 for p in (P/'source').iterdir():
  if p.is_file():shutil.copyfile(p,H/'source'/p.name)
 for name in ['physics.cjs','public_observer.cjs','result.cjs']:shutil.copyfile(P/name,H/name)
 server=(P/'server.cjs').read_text(encoding='utf-8').replace("policy:'PURE_FIFO_EDF'","policy:'TASK_QUEUE_RR'").replace("raw.pure_no_action=policy.none();","raw.pure_no_action=policy.none();raw.rr_turns=policy.turns();")
 text(H/'server.cjs',server)
 cases=read(P/'INPUTS.json')['cases'];assert len(cases)==4
 put(H/'INPUTS.json',dict(cases=cases,source=str(P/'INPUTS.json'),source_sha256=sha(P/'INPUTS.json')))
 reused=[]
 for row in read(P/'artifacts/G001/RESULT.json')['rows']:
  if row['method'] not in ['FIFO','EDF','OURS']:continue
  rp=P/'artifacts/G001'/(row['label']+'.json');raw=P/'artifacts/G001'/(row['label']+'.raw.json.gz');assert sha(raw)==row['raw_sha256']
  reused.append(dict(method=row['method'],row=row,row_path=str(rp),row_sha256=sha(rp),raw_path=str(raw),raw_sha256=sha(raw)))
 assert len(reused)==12
 put(H/'REUSE_PLAN.json',dict(rows=reused,new_environment=0,selected_seed=881087))
 prior=P/'BUDGET_RESERVATION.json';peer=W/'D1Check/a24_simulator/experiments/a24_cem_greedy_20261019/BUDGET_RESERVATION.json';assert read(prior)['known_conservative_after']==137754 and read(peer)['known_conservative_after']==137686
 put(H/'BUDGET_RESERVATION.json',dict(utc=utc,known_conservative_before=137754,new_global_reservation=4,known_conservative_after=137758,original_shared_cap=137712,finite_amended_cap=137758,environment_cap=4,planned_START=4,no_refunds=True,not_fresh_all_host_census=True,
  authority='User explicitly requested RR comparison and selected nonpreemptive task-queue RR; earlier authorized logically justified constraint relaxation.',finite_exception_reason='Four RR-only evaluations on the exact original four inputs. All12 existing FIFO/EDF/selected-model rows reused. No new training, physical fits or completed-case reruns.',parent_reservation=dict(path=str(prior),sha256=sha(prior)),peer_snapshot=dict(path=str(peer),sha256=sha(peer))))
 protocol=dict(schema='S26_FINAL_FOUR_TASK_QUEUE_RR_V1',utc=utc,primary_methods=['FIFO','EDF','RR','OURS'],user_selected_RR='작업종류별 큐를 번갈아 선택하는 비선점 RR (권장)',
  RR=dict(type='Nonpreemptive work-conserving task-queue cyclic dispatcher, NOT operating-system time-quantum SCHED_RR',queues=['classification','detection'],initial_next_queue='classification',quantum='one admitted request, not CPU time',within_queue='earliest arrival then ordinal among physically executable ready requests',skip='Skip a queue if it has no physically executable request, never idle while another queue can execute',pointer='After dispatch point to the other task queue; after NONE retain current pointer',routing=['GPU','NPU','CPU'],priorities_used=False,deadlines_used=False,preemption=False,proactive_WAIT=False),
  common=read(P/'PROTOCOL.json')['common'],primary_route_order=['GPU','NPU','CPU'],OURS='Original frozen881087 rolling+ATC+publicBC+PPO argmax, no deadline protection; no new forward, training or environment',
  comparison='Whole policy comparison with common plant/input/stream/window/legal routes/CPU3/nonpreemption. RR alternates dispatch opportunities rather than equalizing CPU seconds. Classification is urgent and detection normal in this source cohort.',accounting=dict(new_RR=4,reused_FIFO=4,reused_EDF=4,reused_OURS=4,primary_rows=16,environment_cap=4),physical_gate='FAIL',new_training=0,new_measurements=0,new_physical_fit=0,
  figures='Show absolute metrics and EDF-referenced differences with units, positive/negative effects, zero reference, stated zoomed dot axes, all4 paired inputs. No invented significance or best-case selection.')
 put(H/'PROTOCOL.json',protocol)
 selector=r'''
'use strict';
const QUEUES=['classification','detection'],RESOURCES=['GPU','NPU','CPU'];
function select(obs,method,order,cursor){
 if(method!=='RR'||![0,1].includes(cursor)||order.join('|')!==RESOURCES.join('|'))throw Error('Unregistered RR definition');
 const busy=new Set(obs.owners.map(o=>o.route.split('_').at(-1))),none={kind:'NONE',forecast_calls:0,rr_before:cursor,rr_next:cursor};
 if(obs.owners.length>=obs.capacity)return {...none,reason:'CAPACITY'};
 for(let step=0;step<2;step++){
  const qi=(cursor+step)%2,task=QUEUES[qi],routes=task==='detection'?['CPU']:order;
  const free=routes.filter(r=>!busy.has(r));if(!free.length)continue;
  const ready=obs.ready.filter(q=>q.task===task).sort((a,b)=>a.arrival-b.arrival||a.ordinal-b.ordinal);if(!ready.length)continue;
  return {kind:'DISPATCH',ordinal:ready[0].ordinal,route:task+'_'+free[0],forecast_calls:0,policy:'NONPREEMPTIVE_TASK_QUEUE_RR',rr_before:cursor,rr_next:1-qi,rr_selected_queue:task,rr_skipped_queue:step===1,resource_order:order.slice()};
 }
 return {...none,reason:'NO_PHYSICALLY_EXECUTABLE_QUEUE'};
}
module.exports={select,QUEUES};
'''
 text(H/'select.cjs',selector)
 policy=r'''
'use strict';
const rr=require('./select.cjs');let state;
function configure(options){if(options.method!=='RR')throw Error('RR only');state={...options,cursor:0,none:[],turns:[],calls:0};}
function select(obs){state.calls++;const before=state.cursor,a=rr.select(obs,state.method,state.order,before);if(a.kind==='DISPATCH')state.cursor=a.rr_next;
 state.turns.push({time:obs.time,before,after:state.cursor,capacity:obs.capacity,ready:obs.ready.map(q=>q.ordinal),owners:obs.owners.map(o=>({ordinal:o.ordinal,route:o.route})),action:a});
 if(a.kind==='NONE')state.none.push({time:obs.time,capacity:obs.capacity,owners:obs.owners.map(o=>({ordinal:o.ordinal,route:o.route})),ready_counts:{classification:obs.ready.filter(q=>q.task==='classification').length,detection:obs.ready.filter(q=>q.task==='detection').length},action:a});return a;
}
module.exports={configure,select,none:()=>state.none,turns:()=>state.turns,cacheStats:()=>({queries:0,computations:0,hits:0,numerical_failures:0}),contextStats:()=>({preferences:[],task_seen:[],pure:true,RR_definition:'nonpreemptive task queue RR',next_queue:rr.QUEUES[state.cursor],selector_calls:state.calls})};
'''
 text(H/'policy.cjs',policy)
 driver=(P/'run.py').read_text(encoding='utf-8').replace('FIFO','RR').replace('FINAL_THREE','FINAL_FOUR_RR').replace('COMPLETE_RR_EDF_ADOPTED_POLICY_AND_BC_CONTROL','COMPLETE_FIFO_EDF_RR_ADOPTED_POLICY')
 driver=driver.replace("source['extra_CPU_core_s']","source.get('extra_cpu_core_s',source.get('extra_CPU_core_s',0))")
 text(H/'run.py',driver);ast.parse(driver)
 preflight=r'''
'use strict';const fs=require('fs'),path=require('path'),assert=require('assert'),cp=require('child_process'),crypto=require('crypto'),H=__dirname,read=p=>JSON.parse(fs.readFileSync(p,'utf8').replace(/^\uFEFF/,'')),sha=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
let checks=0;const need=(v,s)=>{checks++;assert(v,s)};const {select}=require('./select.cjs'),tasks=['classification','detection'],order=['GPU','NPU','CPU'];
for(const pin of read(path.join(H,'OPERATION.json')).pins)need(sha(pin.path)===pin.sha256,'Frozen source '+pin.path);
for(const f of fs.readdirSync(H).filter(x=>x.endsWith('.cjs')))cp.execFileSync('node',['--check',path.join(H,f)]);
for(let k=0;k<120;k++)for(let bits=0;bits<8;bits++)for(let cur=0;cur<2;cur++){
 const owners=['CPU','GPU','NPU'].filter((r,i)=>bits&(1<<i)).map((r,i)=>({ordinal:100+i,route:'classification_'+r})),ready=Array.from({length:k%13},(_,i)=>({ordinal:i,task:tasks[(i+k)%2],arrival:(i*7)%5,priority:i%2?'urgent':'normal',deadline:k-i})),obs={time:100,capacity:3,owners,ready},a=select(obs,'RR',order,cur),busy=owners.map(o=>o.route.split('_').at(-1));
 const runnable=ready.flatMap(q=>(q.task==='detection'?['CPU']:order).filter(r=>!busy.includes(r)).map(r=>({q,r})));const candidate=runnable.sort((a,b)=>((tasks.indexOf(a.q.task)-cur+2)%2)-((tasks.indexOf(b.q.task)-cur+2)%2)||a.q.arrival-b.q.arrival||a.q.ordinal-b.q.ordinal||order.indexOf(a.r)-order.indexOf(b.r))[0];
 if(owners.length>=3||!candidate)need(a.kind==='NONE'&&a.rr_next===cur,'Blocked queue skips, no pointer advance on NONE');else need(a.kind==='DISPATCH'&&a.ordinal===candidate.q.ordinal&&a.route===candidate.q.task+'_'+candidate.r&&a.rr_next===1-tasks.indexOf(candidate.q.task),'Independent queue rotation/FIFO/routing');
 const mutated=JSON.parse(JSON.stringify(obs));for(const q of mutated.ready){q.deadline+=1000;q.priority=q.priority==='urgent'?'normal':'urgent';}assert.deepStrictEqual(select(mutated,'RR',order,cur),a);checks++;
}
const P=path.resolve(H,'../final_three_policy_v1');assert.deepStrictEqual(read(path.join(H,'INPUTS.json')).cases,read(path.join(P,'INPUTS.json')).cases);checks++;
for(const f of fs.readdirSync(path.join(H,'source')))need(sha(path.join(H,'source',f))===sha(path.join(P,'source',f)),'Same complete plant and nominal source');for(const f of ['physics.cjs','result.cjs','public_observer.cjs'])need(sha(path.join(H,f))===sha(path.join(P,f)),'Same physics/summary');
need(!/require\s*\(/.test(fs.readFileSync(path.join(H,'select.cjs'),'utf8')),'No forecast/physics/NN imports');
fs.writeFileSync(path.join(H,'PREFLIGHT.json'),JSON.stringify({status:'PASS',checks,new_environment:0,RR:'nonpreemptive classification/detection queue rotation; one dispatch per turn',initial_cursor:0,deadline_priority_invariance:true,plant_byte_identical:true},null,2),{flag:'wx'});console.log('FOUR_RR_PREFLIGHT_PASS',checks);
'''
 text(H/'preflight.cjs',preflight)
 # Start from the already completed independent saved-record physics auditor.
 audit=(P/'audit.cjs').read_text(encoding='utf-8').replace("AUDIT_OPERATION_V3.json","AUDIT_OPERATION.json").replace('THREE_SAVED_AUDIT','FOUR_RR_SAVED_AUDIT')
 audit=audit.replace('16 saved records:4 new FIFO and12 exact reused original EDF/selected881087/BC controls; full-queue ordering, service, slots, independent saved physics, old NN audit binding','16 saved records:4 new nonpreemptive queueRR plus12 reused FIFO/EDF/selected881087; independent pointer/queue ordering and saved physics; original NN audit binding')
 audit=audit.replace("else need(row.method==='BC_CONTROL'&&row.seed===881000,'Secondary BC control');","else if(row.method==='RR')auditRR(row,raw);else need(false,'Unknown method');")
 audit=audit.replace("['BC_CONTROL','EDF','FIFO','OURS']","['EDF','FIFO','OURS','RR']").replace('new_FIFO_evaluations_audited:4,original_EDF_selected_NN_BC_reuse:12','new_RR_evaluations_audited:4,original_FIFO_EDF_selected_NN_reuse:12')
 rr_audit=r'''
function auditRR(row,raw){
 need(raw.forecast_calls===0&&raw.wait_s===0&&raw.route_context_evidence.preferences.length===0,'RR no forecasts/teacher/proactive wait');
 const order=['GPU','NPU','CPU'],tasks=['classification','detection'],planned=raw.planned_requests,dispatched=new Set;let cursor=0,ix=0;
 for(const turn of raw.rr_turns){
  need(turn.before===cursor&&turn.capacity===3,'RR persisted cursor and capacity');const a=turn.action;
  const ready=planned.filter(q=>q.readyAt<=turn.time+1e-9&&!dispatched.has(q.ordinal)),owners=raw.requests.filter(q=>dispatched.has(q.ordinal)&&(q.available===null||q.available>turn.time+1e-9)),busy=owners.map(q=>q.route.split('_').at(-1));
  assert.deepStrictEqual(turn.ready.slice().sort((a,b)=>a-b),ready.map(q=>q.ordinal).sort((a,b)=>a-b));checks++;
  assert.deepStrictEqual(turn.owners.map(q=>[q.ordinal,q.route]).sort((a,b)=>a[0]-b[0]),owners.map(q=>[q.ordinal,q.route]).sort((a,b)=>a[0]-b[0]));checks++;
  const candidates=ready.flatMap(q=>(q.task==='detection'?['CPU']:order).filter(r=>!busy.includes(r)).map(r=>({q,r}))).sort((a,b)=>((tasks.indexOf(a.q.task)-cursor+2)%2)-((tasks.indexOf(b.q.task)-cursor+2)%2)||a.q.arrival-b.q.arrival||a.q.ordinal-b.q.ordinal||order.indexOf(a.r)-order.indexOf(b.r));
  if(owners.length>=3||!candidates.length)need(a.kind==='NONE'&&turn.after===cursor&&a.rr_next===cursor,'NONE only when no executable queue, preserve pointer');
  else{
   const q=candidates[0].q,r=candidates[0].r;need(a.kind==='DISPATCH'&&a.ordinal===q.ordinal&&a.route===q.task+'_'+r,'Independent work-conserving queue RR and FIFO inside queue');cursor=1-tasks.indexOf(q.task);need(turn.after===cursor&&a.rr_next===cursor,'Advance pointer after successful dispatch');
   const d=raw.policy_decisions[ix++];need(d&&d.time===turn.time&&d.action.ordinal===a.ordinal&&d.action.route===a.route,'Every dispatched action matches RR trace');dispatched.add(a.ordinal);dispatches++;
  }
 }
 need(ix===raw.policy_decisions.length&&dispatched.size===raw.requests.filter(q=>q.route).length,'All RR decisions and requests accounted');
}
'''
 audit=audit.replace('for(const row of result.rows){',rr_audit+'\nfor(const row of result.rows){',1)
 text(H/'audit.cjs',audit)
 block='<!-- S26_FOUR_RR_CURRENT_BEGIN -->\n2026-10-19 사용자선택 비선점작업큐RR을 FIFO/EDF/우리881087와같은85%·4입력·CPU3에서추가비교등록. RR은분류/탐지큐1건씩순환·큐내FIFO·실행불가큐skip·GPU>NPU>CPU·납기/우선순위/예측/NN/자발WAIT0. RR4회만새평가, 기존FIFO/EDF/우리12SHA재사용·새학습/실측/fit/완료재실행0. 사용자유한비교추가권한에따라보수로컬예약137754+4=137758(전hostcensus/환급0). 다음: 사전검증과RR4회→독립전수검산→4방법차이/절대값그래프와보고서. 원채택정책·물리정확도FAIL유지.\n<!-- S26_FOUR_RR_CURRENT_END -->\n\n'
 for rel in ['s26_simulator/STATUS.md','docs/PROJECT_STATUS.md','docs/PROJECT_PLAN.md','docs/DECISIONS.md']:
  p=R/rel;shutil.copyfile(p,H/'history'/rel.replace('/','__'));old=p.read_text(encoding='utf-8-sig');m=re.match(r'<!-- S26_FINAL_POLICY_ADOPTED_BEGIN -->.*?<!-- S26_FINAL_POLICY_ADOPTED_END -->\s*',old,re.S);assert m;text(p,old[:m.end()]+block+old[m.end():])
 shutil.copyfile(S/'CORE_MANIFEST.json',H/'history/CORE_MANIFEST_BEFORE_RR.json')
 pins=[dict(path=str(p),sha256=sha(p)) for p in sorted(H.rglob('*')) if p.is_file() and 'history' not in p.parts]
 for p in [P/'FINAL_PROOF.json',P/'MANIFEST.json',P/'artifacts/G001/RESULT.json',P/'artifacts/G001/AUDIT.json',S/'FINAL_POLICY.json',S/'FINAL_POLICY_KO.md',S/'experiments/route_group_learning_v1/artifacts/G001/S881087_FINAL.pt.gz',S/'experiments/route_group_learning_v1/artifacts/G001/NN_AUDIT.json',S/'experiments/route_group_learning_v1/artifacts/G001/AUDIT.json',S/'experiments/multiresource_v1/PACKET.json.gz',S/'experiments/capacity_power_v1/artifacts/G001/MODEL.json',S/'experiments/pipeline_thermal_v1/artifacts/G001/MODEL.json']:
  pins.append(dict(path=str(p),sha256=sha(p)))
 put(H/'OPERATION.json',dict(schema='S26_FINAL_FOUR_RR_EXECUTION_V1',utc=utc,environment_cap=4,wall_cap_s=3600,shared_mutex=str(W/'D1Check/a24_simulator/runtime/worker.lock'),ownheavy_limit=1,global_Python_limit=3,min_free_MiB=1536,disk_min_GiB=8,pins=pins,new_training=0,new_physical_fit=0,physical_validation=False))
 put(H/'CURRENT_STATE.json',dict(status='REGISTERED_PENDING_PREFLIGHT',START=0,planned_RR=4))
 print(json.dumps(dict(status='REGISTERED',new_RR=4,REUSE=12,definition='nonpreemptive task-queue RR',finite_local_union_after=137758)))
finally:
 if locked:lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)
 lock.close()
