"""Compress only arrival intervals of frozen .4 patterns; no environment."""
import copy,json
from pathlib import Path
from study import H,A,R,old,read,new,pin,saved,B

def main():
    assert not (H/'INPUTS.json').exists() and not (H/'banks').exists()
    (H/'banks').mkdir();design=read(old.D/'INPUTS.json');cases=[];sources=[]
    for factor in (2,3):
        for pattern,base in enumerate(design['base_cases']):
            c=copy.deepcopy(base);n=base['n'];reps=10*factor;c['id']=f'QP_R{400*factor}_T600_P{pattern}_S160';c['n']=n*reps
            c['condition']={**base['condition'],'rate_multiplier':round(.4*factor,1),'supply_s':600,'n':c['n'],'arrival_factor_vs_040':factor,'repetition_period_s':60/factor,'exact_periodic_extension':True}
            c.update(supply_stop_s=635,service_stop_s=1235,drain_stop_s=1265,observation_end_s=1415,work_window=[35,1235],source_base_n=n,source_base_case_id=base['id'],arrival_compression_factor=factor)
            c['input']['requests']=[]
            srcfile=old.D/'banks'/f'D040_T60_P{pattern}_S160.BANK.json.gz';src=read(srcfile)
            pubfile=old.P/f'D040_T60_P{pattern}_S160.PUBLIC.json';public=copy.deepcopy(read(pubfile)['public']);public['requests']=[]
            proto=read(pubfile)['public']['requests'];bank=dict(jobs=[],nominal_vectors={})
            for k in range(reps):
                for j,q0 in enumerate(base['input']['requests']):
                    ordinal=k*n+j;rid='user-'+str(ordinal).zfill(5)
                    oldarrival=round(q0['arrival_s']*1e9);arrival=35_000_000_000+round((oldarrival-35_000_000_000)/factor)+k*(60_000_000_000//factor)
                    ttl=round(q0['deadline_s']*1e9)-oldarrival;due=arrival+ttl
                    q={**q0,'ordinal':ordinal,'arrival_s':arrival/1e9,'deadline_s':due/1e9};c['input']['requests'].append(q)
                    v=copy.deepcopy(src['jobs'][j]);oldid=v['request_id'];delta=v['queue_entry_ns']-v['scheduled_arrival_ns']
                    v.update(request_id=rid,ordinal=ordinal,scheduled_arrival_ns=arrival,deadline_ns=due,queue_entry_ns=arrival+delta);bank['jobs'].append(v)
                    for route in ('CPU','GPU'):bank['nominal_vectors'][rid+'|'+route]=src['nominal_vectors'][oldid+'|'+route]
                    public['requests'].append({**proto[j],'request_id':rid,'ordinal':ordinal,'scheduled_arrival_ns':arrival,'deadline_ns':due})
            public.update(service_stop_ns=1235_000_000_000,drain_stop_ns=1265_000_000_000,observation_end_ns=1415_000_000_000,public_scenario_sha256=B.L.digest(c['input']))
            saved(H/'banks'/(c['id']+'.BANK.json.gz'),bank);new(H/'banks'/(c['id']+'.PUBLIC.json'),dict(public=public,source_public=pin(pubfile),arrival_factor=factor))
            sources.append(dict(case=c['id'],source_bank=pin(srcfile),source_public=pin(pubfile),source_base_n=n,factor=factor,repetitions=reps))
            cases.append(c)
    new(H/'INPUTS.json',dict(cases=cases,source_cases=sources,reference_load=.4,load_levels=[.8,1.2],independent_replicates=False,new_latent_sampling=0,new_nominal_fitting=0,new_environment=0))
    print('PREPARED',[(c['id'],c['n']) for c in cases])
if __name__=='__main__':main()
