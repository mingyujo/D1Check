import ast, datetime, hashlib, json, msvcrt, shutil, time
from pathlib import Path

W=Path(__file__).resolve().parents[1]; R=W/'S26-D1Check'; S=R/'s26_simulator'
P=S/'experiments/route_group_learning_v1'; F=S/'experiments/five_policy_v1'; H=S/'experiments/final_three_policy_v1'
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8-sig'))
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def put(p,x):
 with Path(p).open('x',encoding='utf-8',newline='\n') as f: json.dump(x,f,ensure_ascii=False,indent=2);f.write('\n')
utc=datetime.datetime.now(datetime.timezone.utc).isoformat()
assert not H.exists()
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
 for name in ['select.cjs','policy.cjs']:shutil.copyfile(F/name,H/name)
 server=(F/'server.cjs').read_text(encoding='utf-8').replace("require('./exact_lengths_cache.cjs').install();\n",'')
 (H/'server.cjs').write_text(server,encoding='utf-8')
 cases=[c for c in read(P/'INPUTS.json')['cases'] if c['phase']=='EVAL' and c['nominal_load_ratio']==.85]
 assert len(cases)==4 and all(c['n']==1024 for c in cases)
 put(H/'INPUTS.json',dict(cases=cases,source=str(P/'INPUTS.json'),source_sha256=sha(P/'INPUTS.json')))
 ids={c['id'] for c in cases};source_rows=[]
 for row in read(P/'artifacts/G001/RESULT.json')['rows']:
  if row['input'] not in ids:continue
  method='EDF' if row['mode']=='EDF_GPU_FIRST' else 'OURS' if row['seed']==881087 else 'BC_CONTROL' if row['seed']==881000 else None
  if not method:continue
  p=P/'artifacts/G001'/(row['label']+'.raw.json.gz');assert sha(p)==row['raw_sha256']
  source_rows.append(dict(method=method,row=row,row_path=str(P/'artifacts/G001'/(row['label']+'.json')),row_sha256=sha(P/'artifacts/G001'/(row['label']+'.json')),raw_path=str(p),raw_sha256=sha(p)))
 assert len(source_rows)==12
 put(H/'REUSE_PLAN.json',dict(rows=source_rows,new_environment=0,selected_seed=881087,BC_control_secondary_only=True))
 peer=W/'D1Check/a24_simulator/experiments/a24_cem_greedy_20261019/BUDGET_RESERVATION.json'
 five=F/'BUDGET_RESERVATION.json';a=read(peer);b=read(five)
 assert a['known_conservative_before']==b['known_conservative_before']==137542
 before=137542+a['new_reservation']+b['new_global_reservation']
 assert before==137750
 put(H/'BUDGET_RESERVATION.json',dict(utc=utc,known_conservative_before=before,new_global_reservation=4,known_conservative_after=before+4,original_shared_cap=137712,finite_amended_cap=before+4,planned_START=4,environment_cap=4,no_refunds=True,
  reconciliation='Independent sibling reservations after common137542: A24+144 and S26+64. Using max137686 would miss64. Existing local union lower bound137750; no evidence of refunded usage.',
  authority='User: 어떤 제약 때문에 막힐 때 논리적인 근거가 있다면 제약 풀고 진행해도돼',
  finite_exception_reason='Four missing FIFO evaluations are necessary for the explicitly requested FIFO/EDF/adopted-policy same-input report. No retraining/reselection or completed-case rerun. Amendment applies only to these four new identities, not new peer quota.',
  not_fresh_all_host_census=True,new_training=0,new_measurements=0,new_fits=0,
  sources=[dict(path=str(p),sha256=sha(p)) for p in [peer,five]]))
 protocol=dict(schema='S26_FINAL_FIFO_EDF_OURS_V1',utc=utc,request='FIFO, EDF, 우리꺼로 비교해줘야지',
  primary_methods=['FIFO','EDF','OURS'],secondary_control='BC_CONTROL',primary_route_order=['GPU','NPU','CPU'],
  routing_rationale='Retain original adopted-policy GPU-first EDF comparator. FIFO gets exactly the same fixed static order. No post-evaluation route-order selection. This is not a strongest-route-baseline claim; prior NPU-first other-cohort results remain separate.',
  FIFO='Full observed physically executable queue, arrival then ordinal; same fixed GPU/NPU/CPU order; no lookahead/ATC/NN/proactive WAIT/deadline protection.',
  EDF='Reuse exact original pure GPU-first EDF; equivalence to frozen pure selector tested without environment runs.',
  OURS='Reuse exact original DEV-selected881087 argmax policy; rolling/ATC/public BC/PPO, no deadline protection; no new forward or environment.',
  common=dict(load=.85,n=1024,cases=4,templates=2,latent_draws_per_template=2,CPU_workers=3,route_slots=dict(CPU=1,GPU=1,NPU=1),nonpreemptive=True,reserve_until='AVAILABLE',input_and_latent_and_window_exactly_original=True),
  accounting=dict(new_FIFO=4,reused_EDF=4,reused_OURS=4,reused_secondary_BC=4,logical_primary=12,logical_including_control=16,environment_cap=4),
  physical_gate='FAIL',new_training=0,new_measurements=0,new_physical_fit=0,resource_orders=dict(GPU=['GPU','NPU','CPU']))
 put(H/'PROTOCOL.json',protocol)
 prefix=(F/'run.py').read_text(encoding='utf-8').split('def main(op):')[0]
 driver=r'''
def main(op):
    start=time.monotonic();rows=[];count=0
    def verify():
        for pin in op['pins']:assert sha(pin['path'])==pin['sha256'],'Changed pin '+pin['path']
    verify()
    for c in read(H/'INPUTS.json')['cases']:
        resource=guard(start+op['wall_cap_s']);verify();assert count<op['environment_cap'];count+=1
        label=c['id']+'__FIFO_GPU';rec=dict(event='START',utc=now(),count=count,label=label,identity=hashlib.sha256((sha(H/'OPERATION.json')+'|'+label).encode()).hexdigest(),input=c['id'],stream=c['stream'],method='FIFO')
        append(O/'receipts.jsonl',rec);begin=time.monotonic()
        try:
            p=subprocess.run(['node',str(H/'server.cjs')],input=json.dumps(dict(input=c['id'],method='FIFO',order=['GPU','NPU','CPU']))+'\n',capture_output=True,text=True,encoding='utf-8',timeout=max(1,op['wall_cap_s']-(time.monotonic()-start)))
            if p.stderr:append(O/'ENGINE_STDERR.jsonl',dict(label=label,stderr=p.stderr))
            assert p.returncode==0,p.stderr[-1000:];messages=[json.loads(x) for x in p.stdout.splitlines() if x.strip()];assert len(messages)==1 and messages[0]['type']=='DONE',str(messages)[:1000]
            raw=messages[0]['result'];save(O/(label+'.raw.json.gz'),raw)
            row=dict(label=label,kind='EVAL',method='FIFO',input=c['id'],stream=c['stream'],seed=None,n=c['n'],mix=c['mix'],load=.85,service=raw['service'],unfinished=raw['unfinished'],J=raw['physics_J'],AP_mean=raw['AP_mean'],AP_peak=raw['AP_peak_sampled'],baseline_J=raw['baseline_API_W']*raw['observation_end_s'],observation_s=raw['observation_end_s'],work_s=raw['actual_work_span_s'],extra_cpu_core_s=raw['extra_cpu_core_s'],wait_s=raw['wait_s'],raw_sha256=sha(O/(label+'.raw.json.gz')),resource_order=['GPU','NPU','CPU'],reused_environment=False,physical_validation=False,wall_s=time.monotonic()-begin,resource=resource)
            save(O/(label+'.json'),row);rows.append(row);append(O/'receipts.jsonl',{**rec,'event':'COMPLETE','utc':now(),'raw_sha256':row['raw_sha256']});print('FIFO_COMPLETE',count,label,round(row['J'],3),row['service']['all']['on_time'],flush=True)
        except BaseException as e:append(O/'receipts.jsonl',{**rec,'event':'FAIL','error':str(e),'automatic_retry':False});raise
    for reuse in read(H/'REUSE_PLAN.json')['rows']:
        source=reuse['row'];assert sha(reuse['row_path'])==reuse['row_sha256'] and sha(reuse['raw_path'])==source['raw_sha256']
        label='REUSE_'+reuse['method']+'_'+source['label'];shutil.copyfile(reuse['raw_path'],O/(label+'.raw.json.gz'))
        c=next(c for c in read(H/'INPUTS.json')['cases'] if c['id']==source['input'])
        row={**source,'label':label,'source_label':source['label'],'method':reuse['method'],'stream':c['stream'],'extra_cpu_core_s':source['extra_CPU_core_s'],'reused_environment':True,'reuse_proof':{k:v for k,v in reuse.items() if k!='row'}}
        save(O/(label+'.json'),row);rows.append(row);append(O/'receipts.jsonl',dict(event='REUSE',utc=now(),label=label,input=c['id'],method=row['method'],raw_sha256=row['raw_sha256'],new_environment=0))
    verify();assert count==4 and len(rows)==16
    save(O/'RESULT.json',dict(status='COMPLETE_FIFO_EDF_ADOPTED_POLICY_AND_BC_CONTROL',START=4,COMPLETE=4,FAIL=0,REUSE=12,rows=rows,new_training=0,new_measurements=0,new_fits=0,physical_validation=False))
    print('FINAL_THREE_ALL_COMPLETE',flush=True)
if __name__=='__main__':
    op=read(H/'OPERATION.json');assert not O.exists() and read(H/'PREFLIGHT.json')['status']=='PASS';lock=Path(op['shared_mutex']).open('r+b');locked=False;deadline=time.monotonic()+14400
    try:
        while not locked:
            try:lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1);locked=True
            except OSError:
                if time.monotonic()>deadline:raise
                print('WAIT_SHARED_MUTEX',flush=True);time.sleep(10)
        resource=guard(deadline);O.mkdir(parents=True);save(O/'START.json',dict(utc=now(),pid=os.getpid(),operation_sha256=sha(H/'OPERATION.json'),resource=resource))
        try:main(op)
        except BaseException as e:save(O/'FAILURE.json',dict(utc=now(),error=str(e),traceback=traceback.format_exc(),automatic_retry=False));raise
    finally:
        if locked:lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)
        lock.close()
'''
 (H/'run.py').write_text(prefix+driver,encoding='utf-8');ast.parse(prefix+driver)
 preflight=r'''
'use strict';const fs=require('fs'),path=require('path'),assert=require('assert'),cp=require('child_process'),crypto=require('crypto'),H=__dirname,read=p=>JSON.parse(fs.readFileSync(p,'utf8').replace(/^\uFEFF/,'')),sha=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
const {select}=require('./select.cjs'),oldEDF=require('../plain_edf_v1/select.cjs').select;let checks=0;const need=(v,s)=>{checks++;assert(v,s)};
for(const pin of read(path.join(H,'OPERATION.json')).pins)need(sha(pin.path)===pin.sha256,'Frozen source');
for(const f of fs.readdirSync(H).filter(x=>x.endsWith('.cjs')))cp.execFileSync('node',['--check',path.join(H,f)]);
for(let k=0;k<100;k++)for(let bits=0;bits<8;bits++)for(const method of ['FIFO','EDF']){
 const order=['GPU','NPU','CPU'],owners=['CPU','GPU','NPU'].filter((r,i)=>bits&(1<<i)).map((r,i)=>({ordinal:100+i,route:'classification_'+r})),ready=Array.from({length:k%12},(_,i)=>({ordinal:i,task:(i+k)%3?'classification':'detection',priority:i%2?'urgent':'normal',arrival:i*.01,deadline:((k+i*7)%13)*.1})),obs={time:10,capacity:3,owners,ready},a=select(obs,method,order),busy=owners.map(o=>o.route.split('_').at(-1));
 const pairs=ready.flatMap(q=>(q.task==='detection'?['CPU']:order).filter(r=>!busy.includes(r)).map(r=>({q,r}))).sort((a,b)=>(method==='EDF'?a.q.deadline-b.q.deadline:0)||a.q.arrival-b.q.arrival||a.q.ordinal-b.q.ordinal||order.indexOf(a.r)-order.indexOf(b.r));
 need(owners.length>=3||!pairs.length?a.kind==='NONE':a.kind==='DISPATCH'&&a.ordinal===pairs[0].q.ordinal&&a.route===pairs[0].q.task+'_'+pairs[0].r,'Independent full-queue ordering');
 if(method==='EDF'){const b=oldEDF(obs,order);need(a.kind===b.kind&&(a.kind==='NONE'||a.ordinal===b.ordinal&&a.route===b.route),'Original EDF exact behavior');}
}
const P=path.resolve(H,'../route_group_learning_v1');for(const f of fs.readdirSync(path.join(H,'source')))need(sha(path.join(H,'source',f))===sha(path.join(P,'source',f)),'Original plant/nominal source unchanged');for(const f of ['physics.cjs','public_observer.cjs','result.cjs'])need(sha(path.join(H,f))===sha(path.join(P,f)),'Original physics/summary unchanged');
assert.deepStrictEqual(read(path.join(H,'INPUTS.json')).cases,read(path.join(P,'INPUTS.json')).cases.filter(c=>c.phase==='EVAL'&&c.nominal_load_ratio===.85));checks++;
need(!/require\s*\(/.test(fs.readFileSync(path.join(H,'select.cjs'),'utf8')),'No forecast/thermal/NN selector imports');
fs.writeFileSync(path.join(H,'PREFLIGHT.json'),JSON.stringify({status:'PASS',checks,new_environment:0,new_training:0,old_EDF_behavior_equivalent:true,original_plant_byte_identical:true},null,2),{flag:'wx'});console.log('FINAL_THREE_PREFLIGHT_PASS',checks);
'''
 (H/'preflight.cjs').write_text(preflight,encoding='utf-8')
 for rel in ['s26_simulator/STATUS.md','docs/PROJECT_STATUS.md','docs/PROJECT_PLAN.md','docs/DECISIONS.md','s26_simulator/CORE_MANIFEST.json']:
  p=R/rel;shutil.copyfile(p,H/'history'/rel.replace('/','__'))
  if p.suffix=='.md':
   block='<!-- S26_FINAL_THREE_CURRENT_BEGIN -->\n2026-10-19 사용자수정 FIFO/EDF/우리최종모델 보고서비교를 final_three_policy_v1에등록. 원85%·N1024·4입력·CPU3·GPU>NPU>CPU 기준선유지, 빠진FIFO4회만추가하며EDF4/선정881087모델4/보조BC4를SHA재사용. 새학습/기기측정/물리fit/평가모델재선정0. 원장이공통137542뒤A24+144와S26+64로분기했음을반영한로컬합집합최소137750; 사용자논리적제약완화허용을근거로이번필수4회에한해137754까지유한변경,다른프로젝트새쿼터/환급/전host최신census주장0. 다음: 사전검증→FIFO4회→전수검산및두보고서주표3방법수정. 최종정책/물리정확도FAIL은그대로유지.\n<!-- S26_FINAL_THREE_CURRENT_END -->\n\n'
   p.write_text(block+p.read_text(encoding='utf-8-sig'),encoding='utf-8')
 pins=[dict(path=str(p),sha256=sha(p)) for p in sorted(H.rglob('*')) if p.is_file() and 'history' not in p.parts]
 for p in [S/'FINAL_POLICY.json',S/'FINAL_POLICY_KO.md',P/'INPUTS.json',P/'artifacts/G001/RESULT.json',P/'artifacts/G001/AUDIT.json',P/'artifacts/G001/NN_AUDIT.json',P/'artifacts/G001/S881087_FINAL.pt.gz',S/'experiments/multiresource_v1/PACKET.json.gz',S/'experiments/capacity_power_v1/artifacts/G001/MODEL.json',S/'experiments/pipeline_thermal_v1/artifacts/G001/MODEL.json',S/'experiments/plain_edf_v1/select.cjs']:
  pins.append(dict(path=str(p),sha256=sha(p)))
 put(H/'OPERATION.json',dict(schema='S26_FINAL_THREE_EXECUTION_V1',utc=utc,environment_cap=4,wall_cap_s=3600,shared_mutex=str(W/'D1Check/a24_simulator/runtime/worker.lock'),ownheavy_limit=1,global_Python_limit=3,min_free_MiB=1536,disk_min_GiB=8,git_HEAD='5f2bd713bce5a3c404d271ff954ebddb11b2e195',pins=pins,new_training=0,physical_validation=False))
 put(H/'CURRENT_STATE.json',dict(status='REGISTERED_PENDING_PREFLIGHT',START=0,planned=4))
 print(json.dumps(dict(status='REGISTERED',new_FIFO=4,reuse=12,primary_methods=['FIFO','EDF','OURS'],known_local_union_after=137754)))
finally:
 if locked:lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)
 lock.close()
