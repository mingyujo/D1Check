import math

def summarize(qs,end):
    out={}
    for group in ['ALL','U','N']:
        rows=[q for q in qs if group=='ALL' or q['priority']==group];answered=[q for q in rows if q['response_ns'] is not None and q['response_ns']<=round(end*1e9)];lat=sorted((q['response_ns']-q['scheduled_arrival_ns'])/1e9 for q in answered);out[group]={'n':len(rows),'on':sum(q['response_ns']<=q['deadline_ns'] for q in answered),'missing':len(rows)-len(answered),'incomplete':sum(q['available_ns'] is None or q['available_ns']>round(end*1e9) for q in rows),'P95':lat[math.ceil(.95*len(lat))-1] if lat else None,'latencies':lat}
    return out

def metrics(result,case):
    t=case['observation_end_s'];baseline=result['config']['baseline'];trace=result['trace'];inc=sum(s['increment'] for s in trace);area=sum(s['temperature_area'] for s in trace)
    return {'J':baseline*t+inc,'increment_J':inc,'pre35_baseline_J':35*baseline,'AP':area/(t-35),'peak':max(s['peak'] for s in trace),'energy_per_request':(baseline*t+inc)/case['n'],'service':summarize(result['requests'],t),'censor_service':summarize(result['requests'],case['censor_s']),'route_counts':{task+'_'+route:sum(q['task']==task and q['route']==route for q in result['requests']) for task in ['C','D'] for route in ['CPU','GPU']}}

def evaluate_setting(rows):
    assert rows and all(r['status']=='COMPLETE' for r in rows)
    mixes=sorted({r['condition']['mix'] for r in rows});tests=[];service=[]
    for mix in mixes:
        bc=[r for r in rows if r['policy']=='BC_NEURAL_URGENT' and r['condition']['mix']==mix];assert bc
        alln=sum(r['metrics']['service']['ALL']['n'] for r in bc);un=sum(r['metrics']['service']['U']['n'] for r in bc);on=sum(r['metrics']['service']['ALL']['on'] for r in bc);uon=sum(r['metrics']['service']['U']['on'] for r in bc);service.append({'mix':mix,'all':on/alln,'urgent':uon/un,'missing':sum(r['metrics']['service']['ALL']['missing'] for r in bc),'incomplete':sum(r['metrics']['service']['ALL']['incomplete'] for r in bc)})
        J=sum(r['metrics']['J'] for r in bc)/len(bc);T=sum(r['metrics']['AP'] for r in bc)/len(bc)
        for p in ['FIFO_DYN','EDF_DYN','RR_DYN']:
            ref=[r for r in rows if r['policy']==p and r['condition']['mix']==mix];assert len(ref)==len(bc);rJ=sum(r['metrics']['J'] for r in ref)/len(ref);rT=sum(r['metrics']['AP'] for r in ref)/len(ref);rn=sum(r['metrics']['service']['ALL']['n'] for r in ref);ron=sum(r['metrics']['service']['ALL']['on'] for r in ref);tests.append({'mix':mix,'reference':p,'energy_saving_pct':100*(1-J/rJ),'AP_reduction_C':rT-T,'all_on_change':on/alln-ron/rn})
    no_missing=all(s['missing']==s['incomplete']==0 for s in service);allok=min(s['all'] for s in service)>=.95;u=min(s['urgent'] for s in service);tier=0 if no_missing and allok and u>=1.-1e-12 else 1 if no_missing and allok and u>=.99 else 2;joint=0 if all(s['energy_saving_pct']>1e-9 and s['AP_reduction_C']>1e-9 and s['all_on_change']>=-1e-12 for s in tests) else 1
    return {'service_tier':tier,'joint_tier':joint,'min_urgent':u,'mean_all':sum(s['all'] for s in service)/len(service),'min_energy_saving_pct':min(s['energy_saving_pct'] for s in tests),'min_AP_reduction_C':min(s['AP_reduction_C'] for s in tests),'service':service,'comparisons':tests}

def ranking(setting,s):
    if s['service_tier']==s['joint_tier']==0:return (0,0,-s['min_energy_saving_pct'],-s['min_AP_reduction_C'],-setting['n'],-setting['load'],-setting['burst'],setting['id'])
    return (s['service_tier'],s['joint_tier'],-s['min_urgent'],-s['mean_all'],-s['min_energy_saving_pct'],-s['min_AP_reduction_C'],-setting['n'],setting['id'])
