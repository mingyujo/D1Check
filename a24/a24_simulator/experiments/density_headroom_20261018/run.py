"""Finite frozen-model density headroom diagnosis. No fitting or learning."""
from pathlib import Path
import gc,gzip,json,os,subprocess,sys,time
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];ENTRY=Path(__file__).resolve()
sys.path.insert(0,str(ROOT/'experiments/coupled_345_20261017'))
from bootstrap import L,G,registration,public_input,save_binary,Nominal
from dynamics import Physics,Config
from engine import run as execute,metrics
sys.path.insert(0,str(HERE))
from bounds import envelopes,build,lift
from actors import Actor,Replay,RECIPES
import numpy as np
import torch
torch.set_num_threads(1)
G.OWN_TOKENS+=('density_headroom_20261018','load_density_20261017','coupled_345_20261017','savings_limit_20261017')
os.environ['A24_LAB_GUARD_ENTRY']=str(ENTRY)


def read(p):
    p=Path(p);b=p.read_bytes();return json.loads(gzip.decompress(b) if p.suffix=='.gz' else b)


def saved(p,x):save_binary(p,gzip.compress(L.canonical(x).encode(),mtime=0))


def extract(public,model,key):
    jobs=[]
    for q in public['requests']:
        context,_=model.request_context(public,q);potential=[key,q['ordinal'],q['request_id']]
        admission=model.admission(context,q['task'],potential,protocol='SERIAL')
        entry=q['scheduled_arrival_ns']+admission['scheduled_to_actual_ns']+admission['actual_to_queue_ns']
        job={k:q[k] for k in ('request_id','ordinal','task','priority','scheduled_arrival_ns','deadline_ns')}
        job.update(queue_entry_ns=entry,admission=admission,routes={})
        state=dict(now_ns=entry,queue=[{**q,'queue_entry_ns':entry}],owners=[],initial_ap_c=public['initial_ap_c'])
        for r in ('CPU','GPU'):
            chosen=dict(request_id=q['request_id'],task=q['task'],route=r,context=L.context_for_route(context,q['task'],r))
            job['routes'][r]=model.draw_latent_serial(chosen,state,potential)
        jobs.append(job)
    return jobs


def main():
    op=read(HERE/'OPERATION.json');opsha=L.sha(HERE/'OPERATION.json');out=ROOT/op['output_dir'];parent=ROOT/op['parent_output']
    L.need('--published' in sys.argv,'Publish registration first')
    for p in [*op['sources'],*op['input_pins']]:L.pin(p)
    L.need(not out.exists(),'Consumed namespace; no automatic retry')
    guard=G.process_guard(ENTRY);volumes=G.free_guard([ROOT,'D:/'])
    import msvcrt
    lock=(ROOT/'runtime/worker.lock').open('r+b');lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
    started=time.monotonic();count=0;solves=0;rows=[];bounds=[];bindings=0;lift_checks=0
    try:
        out.mkdir();L.write_new(out/'START.json',dict(utc=L.now(),operation_sha256=opsha,guard=guard,volumes=volumes,
            HEAD=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),command=sys.argv))
        try:
            base,_,_=L.initialize(registration(op));L.need(base.feature_mode=='exact_public','Independent frozen route potentials')
            catalog=read(L.pin(registration(op)['catalog_pin']))
            physics=Physics(read(ROOT/'results/STATE_COST_IDENTIFICATION_20261017_01/MODEL.json'),Config(**op['physics']))
            design=read(op['inputs']['path'])['cases'];refs=read(parent/'WORK_METRICS.json')['rows']
            env=envelopes(physics,op['thermal_upper_c'],op['temperature_step_c'])
            def slot():
                began=time.monotonic()
                while True:
                    try:G.process_guard(ENTRY);break
                    except RuntimeError as exc:
                        if not any(s in str(exc) for s in ('Global Python leaf limit','Other own Python producer alive')) or time.monotonic()-began>=30:raise
                        print('PRE_START_SLOT_WAIT',str(exc),flush=True);time.sleep(5)
                G.free_guard([ROOT,'D:/'])
                L.need(time.monotonic()-started<op['wall_clock_limit_s'],'Wall cap')
            def native(case,public,model,actor,label,kind,policy):
                nonlocal count
                slot();L.need(count<op['environment_cap'],'Environment cap')
                receipt=dict(event='START',label=label,case=case['id'],kind=kind,policy=policy,utc=L.now(),identity=L.digest([opsha,label]),
                             start_id=L.digest([opsha,label]),durable_START_consumed=True,operation_sha256=opsha)
                L.append(out/'receipts.jsonl',receipt);count+=1;print('START',count,label,'n',case['n'],flush=True)
                try:
                    r=execute(public,model,actor,physics,case['common_potential_key'],receipt);m=metrics(r,case,physics)
                    raw=out/(label+'.raw.json.gz');saved(raw,dict(result=r,calls=actor.calls,offline_future_work_known=True))
                    row=dict(label=label,case=case['id'],kind=kind,policy=policy,n=case['n'],condition=case['condition'],metrics=m,raw_sha256=L.sha(raw))
                    L.write_new(out/(label+'.json'),row);rows.append(row)
                    L.append(out/'receipts.jsonl',{**receipt,'event':'COMPLETE','utc':L.now(),'raw_sha256':L.sha(raw),'result_sha256':L.sha(out/(label+'.json'))})
                    print('COMPLETE',label,'on',m['on_time'],'/',case['n'],'wait',round(m['wait_s'],3),'elapsed',round(time.monotonic()-started,1),flush=True)
                    return r
                except BaseException as exc:
                    L.append(out/'receipts.jsonl',{**receipt,'event':'FAIL','error':str(exc),'automatic_retry':False});raise
            for ci,case in enumerate(design):
                slot();local=[r for r in refs if r['case']==case['id']]
                public,contexts=public_input(case,catalog);public['initial_ap_c']=case['temperature_c'];model=L.Model(base,contexts)
                jobs=extract(public,model,case['common_potential_key']);bank={j['request_id']:j for j in jobs};old={}
                for row in local:
                    raw=parent/(row['label']+'.raw.json.gz');L.need(L.sha(raw)==row['raw_sha256'],'Original raw SHA')
                    result=read(raw)['result'];old[row['policy']]=result
                    for q in result['requests']:
                        j=bank[q['request_id']];draw=j['routes'][q['route']]
                        L.need(j['queue_entry_ns']==q['queue_entry_ns'] and list(draw['stages_ns'])==list(q['timing']['stages_ns']) and draw['sample_id']==q['timing']['sample_id'],'Exact existing potential binding')
                        bindings+=1
                saved(out/(case['id']+'.BANK.json.gz'),dict(jobs=jobs,source_case_sha256=L.digest(case),offline_only=True))
                if ci in (0,9):
                    r=native(case,public,model,Replay(old['EDF']['decisions']),'P0_'+case['id'],'P0','REPLAY_EDF')
                    for a,b in zip(r['requests'],old['EDF']['requests']):
                        for k in ('request_id','route','queue_entry_ns','dispatch_ns','response_ns','execution_start_ns','output_ready_ns','persist_complete_ns','worker_release_ns','available_ns'):
                            L.need(a.get(k)==b.get(k),'Exact engine/model replay '+k)
                    L.need(r['trace']==old['EDF']['trace'],'Exact P0 every trace term');del r
                ref=next(r for r in local if r['policy']=='EDF');rl=next(r for r in local if r['policy']=='RL')
                targets={'EDF':{k:ref['original'][k] for k in ('on_time','urgent_on_time')},
                         'STRONG':{k:max(ref['original'][k],rl['original'][k]) for k in ('on_time','urgent_on_time')}}
                strong=next(r for r in local if all(r['original'][k]>=targets['STRONG'][k] for k in targets['STRONG']))
                H=ref['common']['end_ns']/1e9;preferred={}
                for tier,target in targets.items():
                    for kind in ('energy','temperature'):
                        slot();L.need(solves<op['LP_cap'],'LP cap')
                        p,meta=build(jobs,physics,env,target,case['drain_stop_s'] if kind=='energy' else H,None if kind=='energy' else H)
                        for row in local:
                            lifted=lift(jobs,old[row['policy']],physics,env,p,meta,round((case['drain_stop_s'] if kind=='energy' else H)*1e9))
                            include=all(row['original'][k]>=target[k] for k in target)
                            error=p.error(lifted,include_counts=include)
                            L.need(error<3e-5,'Relaxation excludes existing trace '+row['label']+' '+str(error));lift_checks+=len(p.eq)+len(p.ub)
                            observed=row['completion']['total_J_proxy'] if kind=='energy' else row['common']['mean_AP_c']
                            L.need(float(np.dot(p.cost,lifted))+meta['constant_offset']<=observed+3e-5,'Relaxed objective exceeds actual trace')
                        s=p.certificate(op['LP_seconds']);solves+=1
                        if tier=='STRONG' and kind=='energy' and s['x'] is not None:
                            preferred={j['request_id']:max(('CPU','GPU'),key=lambda r:s['x'][meta['x'][i,r]]) for i,j in enumerate(jobs)}
                        lower=s['lower_bound']+meta['constant_offset']
                        name=case['id']+'_'+tier+'_'+kind
                        saved(out/(name+'.CERT.json.gz'),dict(problem=s,constant_offset=meta['constant_offset'],kind=kind,case=case['id'],tier=tier,
                              targets=target,finish_limit=meta['finish_limit'],thermal_end=meta['thermal_end'],envelope=env))
                        bound=dict(case=case['id'],condition=case['condition'],tier=tier,kind=kind,targets=target,lower=lower,status=s['status'],
                                   dual_available=s['dual_available'],reference_EDF=ref['completion']['total_J_proxy'] if kind=='energy' else ref['common']['mean_AP_c'],
                                   maximum_reduction=(100*(1-lower/ref['completion']['total_J_proxy'])) if kind=='energy' else ref['common']['mean_AP_c']-lower,
                                   common_end_s=H,finish_limit=meta['finish_limit'],certificate=name+'.CERT.json.gz')
                        bound['certificate_sha256']=L.sha(out/(name+'.CERT.json.gz'))
                        bounds.append(bound);print('BOUND',name,'max reduction',round(bound['maximum_reduction'],6),'status',s['status'],flush=True)
                        del p,s,lifted;gc.collect()
                protected=[q['request_id'] for q in old[strong['policy']]['requests'] if q['response_ns'] is not None and q['response_ns']<=q['deadline_ns']]
                nominal=Nominal(model,public)
                for recipe in RECIPES:
                    actor=Actor(recipe,jobs,physics,nominal,preferred,protected)
                    r=native(case,public,model,actor,case['id']+'_'+recipe,'WITNESS',recipe)
                    del r,actor;gc.collect()
                saved(out/(case['id']+'.NOMINALS.json.gz'),{rid+'|'+route:v for (rid,route),v in nominal.request_cache.items()})
                del old,model,jobs,nominal;gc.collect()
            L.need(count==op['planned_START'] and solves==op['LP_cap'],'Exact finite counts')
            for p in [*op['sources'],*op['input_pins']]:L.pin(p)
            L.write_new(out/'BOUNDS.json',dict(rows=bounds,LP_solves=solves,bindings=bindings,lift_constraint_checks=lift_checks,
                       relaxation='Continuous route assignment, independent thermal work fractions and deposition, necessary-only deadline capacity; repaired numerical duals, not attainable plans'))
            banks=[dict(file=p.name,sha256=L.sha(p)) for p in sorted(out.glob('*.BANK.json.gz'))]+[dict(file=p.name,sha256=L.sha(p)) for p in sorted(out.glob('*.NOMINALS.json.gz'))]
            L.write_new(out/'RESULT.json',dict(status='COMPLETED_OFFLINE_DENSITY_HEADROOM',rows=rows,banks=banks,new_START=count,new_COMPLETE=count,new_FAIL=0,
                         operation_sha256=opsha,LP_solves=solves,new_training=0,new_physical_fit=0,measured_J=None))
            L.write_new(out/'COMPLETE.json',dict(utc=L.now(),result_sha256=L.sha(out/'RESULT.json'),bounds_sha256=L.sha(out/'BOUNDS.json'),elapsed_s=time.monotonic()-started,new_START=count,new_COMPLETE=count))
            subprocess.run([op['node_executable'],str(HERE/'audit.cjs')],check=True)
            import figures
            figures.main(out)
            subprocess.run([op['node_executable'],str(HERE/'report.cjs')],check=True)
        except BaseException as exc:
            name='POSTPROCESS_FAILURE.json' if (out/'COMPLETE.json').exists() else 'FAILURE.json'
            L.write_new(out/name,dict(utc=L.now(),error=str(exc),new_START=count,LP_solves=solves,automatic_retry=False));raise
    finally:
        lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1);lock.close()


if __name__=='__main__':main()
