"""Saved-only ceilings for the new moderate inputs; no environment or fitting."""
from pathlib import Path
import ast,gzip,json,subprocess,sys,time
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path[:0]=[str(ROOT/'experiments/density_headroom_coupling_20261018'),str(ROOT/'experiments/density_headroom_20261018'),str(ROOT/'experiments/coupled_345_20261017'),str(ROOT/'reference/model_integration')]
import runtime_guard as G
from resource_bounds import wait_resources
from dynamics import Physics,Config
from bounds import envelopes,build,lift
from coupling import strengthen,phase_upper

def read(p):
    p=Path(p);b=p.read_bytes();return json.loads(gzip.decompress(b) if p.suffix=='.gz' else b)

def saved(p,x):
    with Path(p).open('xb') as f:f.write(gzip.compress(G.canonical(x).encode(),mtime=0))

def main():
    op=read(HERE/'OPERATION.json');out=ROOT/op['output_dir'];parent=ROOT/op['parent_output'];opsha=G.sha(HERE/'OPERATION.json')
    G.require('--published' in sys.argv,'Publish finite saved-only registration first')
    for p in [*op['sources'],*op['input_pins']]:G.pin(p)
    G.require(not out.exists(),'Consumed operation; preserve failure')
    G.OWN_TOKENS+=('moderate_headroom_20261018','guard_learning_20261018','moderate_load_20261018','coupled_345_20261017')
    guard=wait_resources(Path(__file__).resolve(),768*1024**2,time.monotonic()+1800);vol=G.free_guard([ROOT,'D:/'])
    import msvcrt
    lockpath=ROOT/'runtime/a24_local_worker.lock'
    if not lockpath.exists():lockpath.write_bytes(b'0')
    lock=lockpath.open('r+b');lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
    count=0;started=time.monotonic()
    try:
        out.mkdir();G.write_new(out/'START.json',dict(utc=G.now(),operation_sha256=opsha,guard=guard,volumes=vol,new_environment_START=0))
        try:
            physics=Physics(read(ROOT/'results/STATE_COST_IDENTIFICATION_20261017_01/MODEL.json'),Config(**op['physics']))
            allrows=read(parent/'ALL_ROWS_WITH_REASONS.json')['rows'];cases=read(op['inputs']['path'])['cases'];bounds=[];proofs=[];liftchecks=0;maxerror=0.
            env0=envelopes(physics,op['original_thermal_upper_c'],.05)
            for case in cases:
                cid=case['id'];jobs=read(ROOT/op['moderate_output']/(cid+'.BANK.json.gz'))['jobs'];proof=phase_upper(jobs,physics,env0);proofs.append(dict(case=cid,**proof));env=envelopes(physics,proof['upper'],.05)
                local=[r for r in allrows if r['case']==cid];edf=next(r for r in local if r['policy']=='EDF');on=next(r for r in local if r['policy']=='GUARD_ON_NN');H=edf['common']['end_ns']/1e9
                G.require(all(r['original']['peak_AP_c']<=proof['upper']+1e-7 for r in local),'Phase bound includes all actual policies')
                references=[r for r in local if r['policy'] in ('EDF','ATC','GUARD_ON_NN')]
                cache={r['label']:read(ROOT/op['moderate_output']/(r['label']+'.raw.json.gz'))['result'] for r in references}
                print('MODERATE_PHASE',cid,round(proof['upper'],6),flush=True)
                for tier in ('EDF','STRONG'):
                    targets={k:edf['original'][k] if tier=='EDF' else max(edf['original'][k],on['original'][k]) for k in ('on_time','urgent_on_time')}
                    for kind in ('energy','temperature'):
                        wait_resources(Path(__file__).resolve(),512*1024**2+len(jobs)*128*1024,started+op['wall_clock_limit_s']);G.free_guard([ROOT,'D:/']);G.require(count<80 and time.monotonic()-started<op['wall_clock_limit_s'],'Finite saved LP cap')
                        finish=case['drain_stop_s'] if kind=='energy' else H
                        p,meta=build(jobs,physics,env,targets,finish,None if kind=='energy' else H);extra=strengthen(p,meta,jobs,physics,env)
                        for r in references:
                            value=lift(jobs,cache[r['label']],physics,env,p,meta,round((case['drain_stop_s'] if kind=='energy' else H)*1e9))
                            if kind=='energy':value[extra['energy_variable']]=r['completion']['increment_J_proxy']
                            include=all(r['original'][k]>=v for k,v in targets.items());err=p.error(value,include_counts=include);maxerror=max(maxerror,float(err));liftchecks+=1
                            G.require(err<3e-5,'Necessary relaxation excludes reference '+r['label']+' '+str(err))
                        cert=p.certificate(op['LP_seconds']);count+=1;lower=cert['lower_bound']+meta['constant_offset'];filename=cid+'_'+tier+'_'+kind+'.CERT.json.gz'
                        saved(out/filename,dict(problem=cert,constant_offset=meta['constant_offset'],coupling=extra,phase_proof=proof,variable_names=p.names,inequality_tags=p.tags,kind=kind,case=cid,tier=tier))
                        eligible=[r for r in local if r['completion'] is not None and r['original']['response_missing']==r['original']['incomplete']==0 and all(r['original'][k]>=v for k,v in targets.items()) and (kind=='energy' or r['same_work_common_eligible'])]
                        actual=min((r['completion']['total_J_proxy'] if kind=='energy' else r['common']['mean_AP_c'] for r in eligible),default=None)
                        if actual is not None:G.require(lower<=actual+1e-5,'Bound excludes found eligible policy')
                        reference=edf['completion']['total_J_proxy'] if kind=='energy' else edf['common']['mean_AP_c']
                        bounds.append(dict(case=cid,condition=case['condition'],tier=tier,kind=kind,targets=targets,common_end_s=H,finish_limit=finish,reference_EDF=reference,lower=lower,maximum_reduction=100*(1-lower/reference) if kind=='energy' else reference-lower,achieved=actual,found_reduction=None if actual is None else (100*(1-actual/reference) if kind=='energy' else reference-actual),eligible_schedules=len(eligible),eligible_status='Found' if eligible else '동시보존 일정 미발견',certificate=filename,certificate_sha256=G.sha(out/filename),solver_status=cert['status'],dual_available=cert['dual_available'],phase_upper_c=proof['upper']))
                        print('MODERATE_BOUND',cid,tier,kind,'max',round(bounds[-1]['maximum_reduction'],6),'found',bounds[-1]['found_reduction'],flush=True)
            G.require(count==80,'Exact saved solve count')
            for p in [*op['sources'],*op['input_pins']]:G.pin(p)
            G.write_new(out/'PHASE_PROOFS.json',dict(rows=proofs,new_environment_START=0))
            G.write_new(out/'EVALUATION.json',dict(rows=allrows,bounds=bounds,all_original_rows_preserved=True,new_environment_START=0))
            G.write_new(out/'RESULT.json',dict(status='COMPLETED_SAVED_MODERATE_BOUNDS',LP_solves=count,new_environment_START=0,new_training=0,new_physical_fit=0,frozen_bank_restores=0,reference_lift_checks=liftchecks,max_reference_lift_error=maxerror,operation_sha256=opsha,evaluation_sha256=G.sha(out/'EVALUATION.json')))
            G.write_new(out/'COMPLETE.json',dict(utc=G.now(),result_sha256=G.sha(out/'RESULT.json'),elapsed_s=time.monotonic()-started))
            subprocess.run([op['node_executable'],str(HERE/'audit.cjs')],check=True)
            subprocess.run([op['node_executable'],str(HERE/'report.cjs')],check=True)
        except BaseException as exc:
            G.write_new(out/('POSTPROCESS_FAILURE.json' if (out/'COMPLETE.json').exists() else 'FAILURE.json'),dict(utc=G.now(),error=str(exc),LP_solves=count,new_environment_START=0,automatic_retry=False));raise
    finally:
        lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1);lock.close()

if __name__=='__main__':main()
