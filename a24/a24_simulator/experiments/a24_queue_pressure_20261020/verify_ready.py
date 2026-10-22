"""Readiness without environment or policy inference."""
import ast,subprocess,sys,shutil
from study import H,O,R,A,read,new,stamp,verify,public_and_contexts,cases,B,C,CHECKPOINT,loadpt

def main():
    assert not O.exists() and not (H/'OPERATION.json').exists()
    for p in H.glob('*.py'):ast.parse(p.read_text(encoding='utf-8'),filename=str(p))
    subprocess.run(['node','--check',str(H/'audit_report.cjs')],check=True)
    op=read(H/'PROPOSAL.json');verify(op['pins'])
    assert op['planned_START']==16 and op['budget']['derived_total']==137741
    assert 'Ran 8 tests' in (H/'TESTS.log').read_text(encoding='utf-8') and '\nOK' in (H/'TESTS.log').read_text(encoding='utf-8')
    cs=[]
    for c in cases():
        public,contexts,parent=public_and_contexts(c)
        assert len(public['requests'])==len(contexts)==c['n']
        lookup=next(iter(contexts.values()))['_requests_by_id']
        assert all(ctx['_requests_by_id'] is lookup for ctx in contexts.values())
        bank=read(H/'banks'/(c['id']+'.BANK.json.gz'));model=B.BankModel(bank['jobs'],contexts)
        nominal=B.SavedNominal(public,[dict(nominal_vectors=bank['nominal_vectors'])])
        for q in (public['requests'][0],public['requests'][-1]):
            model.request_context(public,q)
            for r in ('CPU','GPU'):assert len(nominal.vector(q,r,dict()))==5
        cs.append(dict(case=c['id'],n=c['n'],load=c['condition']['rate_multiplier']))
    snap=loadpt(CHECKPOINT);assert snap['network_sha256']=='779d3d3bf08181d042e7ab682c41da94a4ec87366c02cfa2c2fa715900662bc2'
    assert (snap['episodes'],snap['updates'],snap['steps'])==(0,0,0)
    import psutil
    new(H/'READINESS.json',dict(status='PASS',utc=stamp(),pins_verified=len(op['pins']),input_contract_tests=8,existing_dynamic_contract_tests=24,cases=cs,checkpoint_network_sha256=snap['network_sha256'],new_environment=0,new_training=0,new_fit=0,new_NN_execution=0,available_disk_bytes=shutil.disk_usage(R).free,available_memory_bytes=psutil.virtual_memory().available,python=sys.version,HEAD=op['HEAD']))
    print('PRESSURE_READY',len(op['pins']),'pins',cs,'new START0')
if __name__=='__main__':main()
