"""Saved-only stronger bounds; zero environments, bank restores or fitting."""
from pathlib import Path
import ast,gzip,json,subprocess,sys,time
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path[:0]=[str(HERE),str(ROOT/'experiments/density_headroom_20261018'),str(ROOT/'experiments/coupled_345_20261017'),str(ROOT/'reference/model_integration')]
import runtime_guard as G
from dynamics import Physics,Config
from bounds import envelopes,build,lift
from coupling import strengthen,phase_upper
import numpy as np


def read(p):
    p=Path(p);return json.loads(gzip.decompress(p.read_bytes()) if p.suffix=='.gz' else p.read_bytes())


def saved(p,x):
    b=gzip.compress(G.canonical(x).encode(),mtime=0)
    with Path(p).open('xb') as f:f.write(b)


def main():
    for p in HERE.glob('*.py'):ast.parse(p.read_text(encoding='utf-8'),filename=str(p))
    op=read(HERE/'OPERATION.json');out=ROOT/op['output_dir'];parent=ROOT/op['parent_output']
    G.require('--published' in sys.argv,'Publish saved-only registration first')
    for p in [*op['sources'],*op['input_pins']]:G.pin(p)
    G.OWN_TOKENS+=('density_headroom_coupling_20261018','density_headroom_20261018','load_density_20261017','coupled_345_20261017')
    guard=G.process_guard(Path(__file__).resolve());vol=G.free_guard([ROOT,'D:/']);G.require(not out.exists(),'Preserve consumed saved operation')
    import msvcrt
    lock=(ROOT/'runtime/worker.lock').open('r+b');lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
    count=0;began=time.monotonic()
    try:
        out.mkdir();G.write_new(out/'START.json',dict(utc=G.now(),guard=guard,volumes=vol,operation_sha256=G.sha(HERE/'OPERATION.json'),command=sys.argv,new_environment_START=0))
        try:
            physics=Physics(read(ROOT/'results/STATE_COST_IDENTIFICATION_20261017_01/MODEL.json'),Config(**op['physics']))
            old=read(parent/'EVALUATION.json');bounds=old['bounds'];originals=ROOT/'results/LOAD_DENSITY_20261017_01';rows=[];proofs=[];maxlift=0
            env0=envelopes(physics,op['original_thermal_upper_c'],.05)
            for cid in dict.fromkeys(r['case'] for r in old['rows']):
                jobs=read(parent/(cid+'.BANK.json.gz'))['jobs'];proof=phase_upper(jobs,physics,env0);proofs.append(dict(case=cid,**proof));env=envelopes(physics,proof['upper'],.05)
                local=[r for r in old['rows'] if r['case']==cid];base=[r for r in local if r['source']=='ORIGINAL'];cache={r['policy']:read(originals/(r['label']+'.raw.json.gz'))['result'] for r in base}
                G.require(max(r['original']['peak_AP_c'] for r in local)<=proof['upper']+1e-7,'Phase barrier excludes a real observed trace')
                print('PHASE_BARRIER',cid,round(proof['upper'],6),flush=True)
                for b in [b for b in bounds if b['case']==cid]:
                    G.process_guard(Path(__file__).resolve());G.free_guard([ROOT,'D:/']);G.require(count<40 and time.monotonic()-began<op['wall_clock_limit_s'],'Saved finite LP cap')
                    kind=b['kind'];p,meta=build(jobs,physics,env,b['targets'],b['finish_limit'],None if kind=='energy' else b['common_end_s'])
                    extra=strengthen(p,meta,jobs,physics,env)
                    for r in base:
                        lifted=lift(jobs,cache[r['policy']],physics,env,p,meta,round((785 if kind=='energy' else b['common_end_s'])*1e9))
                        if kind=='energy':lifted[extra['energy_variable']]=r['completion']['increment_J_proxy']
                        include=all(r['original'][k]>=v for k,v in b['targets'].items());err=p.error(lifted,include_counts=include);maxlift=max(maxlift,float(err))
                        G.require(err<3e-5,'Coupled relaxation excludes real reference '+r['label']+' '+str(err))
                    s=p.certificate(op['LP_seconds']);count+=1;lower=s['lower_bound']+meta['constant_offset'];best=max(lower,b['lower'])
                    label=cid+'_'+b['tier']+'_'+kind;cert=out/(label+'.CERT.json.gz')
                    saved(cert,dict(problem=s,constant_offset=meta['constant_offset'],coupling=extra,phase_proof=proof,kind=kind,case=cid,tier=b['tier']))
                    eligible=[r for r in local if r['source']!='P0' and r['completion'] is not None and r['original']['response_missing']==r['original']['incomplete']==0 and all(r['original'][k]>=v for k,v in b['targets'].items()) and (kind=='energy' or r['same_work_common_eligible'])]
                    actual=min(r['completion']['total_J_proxy'] if kind=='energy' else r['common']['mean_AP_c'] for r in eligible)
                    G.require(best<=actual+1e-5,'Lower bound exceeds a found feasible schedule')
                    row={**b,'old_lower':b['lower'],'new_coupled_lower':lower,'lower':best,'old_maximum_reduction':b['maximum_reduction'],
                         'maximum_reduction':100*(1-best/b['reference_EDF']) if kind=='energy' else b['reference_EDF']-best,
                         'certificate':cert.name,'certificate_sha256':G.sha(cert),'new_status':s['status'],'new_dual_available':s['dual_available'],
                         'selected_bound':'new coupled dual' if lower>b['lower'] else 'original dual retained',
                         'phase_upper_c':proof['upper'],'old_certificate':b['certificate'],'old_certificate_sha256':b['certificate_sha256']}
                    rows.append(row);print('TIGHT_BOUND',label,'max reduction',round(row['maximum_reduction'],6),'old',round(b['maximum_reduction'],6),flush=True)
            G.require(count==40,'Exact saved solve count')
            for p in [*op['sources'],*op['input_pins']]:G.pin(p)
            G.write_new(out/'PHASE_PROOFS.json',dict(rows=proofs,new_environment_START=0))
            G.write_new(out/'EVALUATION.json',dict(rows=old['rows'],bounds=rows,new_environment_START=0,original_rows_preserved=True))
            G.write_new(out/'RESULT.json',dict(status='SAVED_COUPLED_BOUND_COMPLETED',LP_solves=40,new_environment_START=0,frozen_bank_restores=0,new_physical_fit=0,new_training=0,
                         operation_sha256=G.sha(HERE/'OPERATION.json'),evaluation_sha256=G.sha(out/'EVALUATION.json'),phase_sha256=G.sha(out/'PHASE_PROOFS.json'),max_reference_lift_error=maxlift))
            G.write_new(out/'COMPLETE.json',dict(utc=G.now(),result_sha256=G.sha(out/'RESULT.json'),elapsed_s=time.monotonic()-began))
            subprocess.run([op['node_executable'],str(HERE/'audit.cjs')],check=True)
            import figures
            figures.main(out)
            subprocess.run([op['node_executable'],str(HERE/'report.cjs')],check=True)
        except BaseException as exc:
            name='POSTPROCESS_FAILURE.json' if (out/'COMPLETE.json').exists() else 'FAILURE.json'
            G.write_new(out/name,dict(utc=G.now(),error=str(exc),LP_solves=count,new_environment_START=0,automatic_retry=False));raise
    finally:
        lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1);lock.close()


if __name__=='__main__':main()
