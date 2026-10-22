"""Resume only unstarted cases after a pre-START RAM halt; scientific AST pinned."""
import ast,copy,datetime,hashlib,json
from pathlib import Path
W=Path(__file__).resolve().parent.parent;H=W/'S26-D1Check/s26_simulator/experiments/route_energy_v1';O=H/'artifacts/G001'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
assert not (H/'OPERATION_RESUME_V2.json').exists()
receipts=[json.loads(x) for x in (O/'receipts.jsonl').read_text(encoding='utf-8').splitlines() if x]
assert len([r for r in receipts if r['event']=='START'])==168 and len([r for r in receipts if r['event']=='COMPLETE'])==168 and not any(r['event']=='FAIL' for r in receipts)
assert read(O/'FAILURE.json')['error']=='RAM headroom' and (O/'TRAINING_COMPLETE.json').exists()
original=(H/'run.py').read_text(encoding='utf-8');s=original
a="H=Path(__file__).resolve().parent;R=H.parents[1];W=H.parents[3]"
b="W=Path(__file__).resolve().parent.parent;H=W/'S26-D1Check/s26_simulator/experiments/route_energy_v1';R=H.parents[1];sys.path.insert(0,str(H))"
assert s.count(a)==1;s=s.replace(a,b)
start=s.index('def snapshot_resources(');end=s.index('def main(op,O):',start)
s=s[:start]+'''def snapshot_resources(min_MiB=1536):
    import psutil,gc
    end=time.monotonic()+3600;last=0
    while True:
        gc.collect();processes=[p.info for p in psutil.process_iter(['pid','name','cmdline']) if (p.info['name'] or '').lower() in ['python.exe','python3.exe']]
        free=psutil.virtual_memory().available;good=len(processes)<=3 and free>=min_MiB*1024**2 and all(shutil.disk_usage(p).free>=8*1024**3 for p in [W,Path('D:/')])
        if good:return dict(utc=now(),free_bytes=free,python=processes,minimum_MiB=min_MiB,real_host_inventory=True)
        if time.monotonic()>=end:raise RuntimeError('Finite resource wait elapsed before START')
        if time.monotonic()-last>=30:print('RESOURCE_WAIT_RESUME_V2',len(processes),round(free/1048576),flush=True);last=time.monotonic()
        time.sleep(5)
'''+s[end:]
a='torch.set_num_threads(1);count=0;rows=[];selection=None;started=time.monotonic()'
b="torch.set_num_threads(1);count=168;selection=None;started=time.monotonic();old_receipts=[json.loads(x) for x in (O/'receipts.jsonl').read_text(encoding='utf-8').splitlines() if x];rows=[read(O/(r['label']+'.json')) for r in old_receipts if r['event']=='COMPLETE'];assert len(rows)==168;prior_by_label={r['label']:r for r in rows}"
assert s.count(a)==1;s=s.replace(a,b)
engine_line="engine=subprocess.Popen(['node',str(H/'server.cjs')],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=(O/'ENGINE_STDERR.txt').open('x'),text=True,encoding='utf-8',bufsize=1)"
replacement="""engine=None
    def reset_engine():
        nonlocal engine
        if engine is not None:
            engine.stdin.close()
            try:engine.wait(timeout=20)
            except subprocess.TimeoutExpired:engine.terminate();engine.wait(timeout=10)
            engine=None
        resource=snapshot_resources(1536)
        append(O/'RESOURCE_CHECKS_RESUME_V2.jsonl',dict(count=count,**resource))
        engine=subprocess.Popen(['node',str(H/'server.cjs')],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=(O/'ENGINE_STDERR_RESUME_V2.txt').open('a'),text=True,encoding='utf-8',bufsize=1)
"""
assert s.count(engine_line)==1;s=s.replace(engine_line,replacement)
a="        verify();assert count<op['environment_cap'] and time.monotonic()-started<op['wall_cap_s']"
b="""        if label in prior_by_label:
            saved=prior_by_label[label]
            assert saved['input']==c['id'] and saved['mode']==mode and saved['kind']==kind and saved['model']==model and saved['seed']==(learner.seed if learner else None)
            assert sha(O/(label+'.raw.json.gz'))==saved['raw_sha256']
            return saved,None
        verify();assert count<op['environment_cap'] and time.monotonic()-started<op['wall_cap_s']"""
assert s.count(a)==1;s=s.replace(a,b)
a="if count%8==0:append(O/'RESOURCE_CHECKS.jsonl',snapshot_resources())"
assert s.count(a)==1;s=s.replace(a,'if count%8==0:reset_engine()')
start=s.index('        # Four counted numerical environments');end=s.index('        def evaluate(c,phase,i,model):',start)
initialization="""        parent=load(op['parent_checkpoint']);frozen=Learner(481083);frozen.restore(parent);frozen_digest=digest(frozen.net)
        training=read(O/'TRAINING_COMPLETE.json');scales=training['scales'];nets={};loaded=[]
        for model in ['CENTRAL','CPU3']:
            for seed in op['seeds']:
                file=O/f'{model}_S{seed}_FINAL.pt.gz';snapshot=load(file);learner=Learner(seed);learner.restore(snapshot['learner']);learner.balance=copy.deepcopy(snapshot['balance']);assert learner.episodes==16 and learner.updates==8 and not learner.pending;nets[(model,seed)]=learner;loaded.append(dict(model=model,seed=seed,checkpoint_sha256=sha(file),network_sha256=digest(learner.net)))
        save(O/'RESUME_LOADED_V2.json',dict(utc=now(),prior_START=168,prior_COMPLETE=168,prior_FAIL=0,remaining_START=252,training_reexecution=0,loaded=loaded,original_failure_sha256=sha(O/'FAILURE.json')))
"""
s=s[:start]+initialization+s[end:]
a="        engine.stdin.close()\n        try:engine.wait(timeout=15)\n        except subprocess.TimeoutExpired:engine.terminate();engine.wait(timeout=10)"
b="        if engine is not None:\n            engine.stdin.close()\n            try:engine.wait(timeout=15)\n            except subprocess.TimeoutExpired:engine.terminate();engine.wait(timeout=10)"
assert s.count(a)==1;s=s.replace(a,b)
start=s.index("if __name__=='__main__':")
s=s[:start]+'''if __name__=='__main__':
    op=read(H/'OPERATION.json');resume_op=read(H/'OPERATION_RESUME_V2.json');O=H/'artifacts/G001'
    for pin in [*op['pins'],*resume_op['pins']]:assert sha(pin['path'])==pin['sha256']
    assert not (O/'RESUME_START_V2.json').exists(),'Consumed resume; no automatic retry'
    lock=Path(op['shared_mutex']).open('r+b');locked=False;deadline=time.monotonic()+3600
    try:
        while not locked:
            try:lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1);locked=True
            except OSError:
                if time.monotonic()>=deadline:raise
                time.sleep(5)
        resource=snapshot_resources(1536);save(O/'RESUME_START_V2.json',dict(utc=now(),pid=os.getpid(),operation_sha256=sha(H/'OPERATION_RESUME_V2.json'),prior_START=168,resource=resource))
        try:main(op,O)
        except BaseException as e:save(O/'RESUME_FAILURE_V2.json',dict(utc=now(),error=str(e),traceback=traceback.format_exc(),automatic_retry=False));raise
    finally:
        if locked:lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)
        lock.close()
'''
def scientific(node):
    fn=copy.deepcopy(next(n for n in ast.walk(ast.parse(node)) if isinstance(n,ast.FunctionDef) and n.name=='simulate'))
    fn.body=[n for n in fn.body if not (isinstance(n,ast.If) and (ast.unparse(n.test)=='count % 8 == 0' or ast.unparse(n.test)=='label in prior_by_label'))]
    return ast.dump(fn,include_attributes=False)
assert scientific(original)==scientific(s),'Scientific simulate AST changed'
target=W/'recovery/run_s26_route_resume_v2.py';target.write_text(s,encoding='utf-8');compile(s,str(target),'exec')
op=dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),schema='S26_ROUTE_RESOURCE_RESUME_V2',parent_operation_sha256=sha(H/'OPERATION.json'),original_failure_sha256=sha(O/'FAILURE.json'),prior_START=168,prior_COMPLETE=168,prior_FAIL=0,new_START=252,total_planned_START=420,environment_cap_preserved=448,new_global_reservation=0,resource_only=True,scientific_simulate_AST_equal=True,scientific_AST_sha256=hashlib.sha256(scientific(s).encode()).hexdigest(),host_resource='Real host process/RAM inventory; Python<=3, ownS26one. Close/reopen equivalent stateless Node engine at complete8case boundaries; wait rather than abort for RAM>=1536MiB, volume>=8GiB.',preservation='Original run/source/OP/failure/receipts/checkpoints unchanged. Reuse168 complete results by exact identity; restore6 final learners and common frozen parent. No training repeats, no discarded action draws, no new physical assumptions.',pins=[dict(path=str(p),sha256=sha(p)) for p in [Path(__file__),target,H/'OPERATION.json',O/'FAILURE.json',O/'TRAINING_COMPLETE.json',*O.glob('*_FINAL.pt.gz')]])
with (H/'OPERATION_RESUME_V2.json').open('x',encoding='utf-8') as f:json.dump(op,f,ensure_ascii=False,indent=2)
flowfile=W/'recovery/S26_ROUTE_ACTIVE_FLOW.json';flow=read(flowfile);flow.update(status='RESOURCE_ONLY_RESUME_SEALED_PRIOR168_COMPLETE',updated_utc=op['utc'],main_original_session=34133,main_original_status='Ended preSTART169 RAM guard;168START/168COMPLETE/0FAIL; preserved',resume_entry=str(target),resume_remaining=252,old_post_sessions_stopped=[51418,92573,27071],pilot_session=37132,pilot_status='COMPLETE18_TRAIN_ONLY',witness_future='54new DEV/EVAL, reuse18 pilot TRAIN, cap80 preserved',event_followup='route_event_learning_v1:134planned/cap144; sources under implementation, not sealed or started',known_conservative_union=129158,do_next='Start registered resume only; no original run.py restart. Then saved audits/report/serviceLP and witness54, then finish registered event-policy implementation/training/evaluation. No current automatic queues remain.')
flowfile.write_text(json.dumps(flow,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('RESOURCE_RESUME_V2_SEALED;168_COMPLETE_PRESERVED;252_UNSTARTED_ONLY;SIMULATE_AST_IDENTICAL')
