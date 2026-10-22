"""Independent saved-data error analysis. No parameter selection or fitting."""
import bisect, csv, gzip, hashlib, json, math, statistics
from collections import Counter, defaultdict
from pathlib import Path
from prepare import H,R,A,O,read,write,sha,pin

def mean(v):return sum(v)/len(v) if v else None
def quantile(v,p):
    if not v:return None
    v=sorted(v);x=(len(v)-1)*p;i=int(x);return v[i]+(v[min(i+1,len(v)-1)]-v[i])*(x-i)
def metrics(errors):
    e=list(errors)
    return {'n':len(e),'MAE_C':mean([abs(x) for x in e]),'RMSE_C':math.sqrt(mean([x*x for x in e])) if e else None,
        'bias_C':mean(e),'P95_abs_C':quantile([abs(x) for x in e],.95),'max_abs_C':max(map(abs,e),default=None),
        'within_0_5C_pct':100*mean([abs(x)<=.5 for x in e]) if e else None,
        'within_1C_pct':100*mean([abs(x)<=1 for x in e]) if e else None}
def csvwrite(p,rows):
    if not rows:return
    fields=list(dict.fromkeys(k for row in rows for k in row))
    with p.open('x',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader();writer.writerows(rows)
def direction(delta,threshold):
    if delta>=threshold-1e-10:return 'rise'
    if delta<=-threshold+1e-10:return 'fall'
    return 'stable'

def windows(obs,pred,width=20,threshold=.2):
    rows=[];excluded=Counter();i=0
    while i<len(obs)-1:
        j=bisect.bisect_left([o['t'] for o in obs],obs[i]['t']+width,lo=i+1)
        if j>=len(obs):excluded['short_tail_samples']+=len(obs)-i-1;break
        if max(obs[k+1]['t']-obs[k]['t'] for k in range(i,j))>10:
            excluded['gap_windows']+=1;excluded['gap_samples']+=j-i;i=j;continue
        dy=obs[j]['observed_c']-obs[i]['observed_c'];dp=pred[j]-pred[i];dt=obs[j]['t']-obs[i]['t']
        errors=[pred[k]-obs[k]['observed_c'] for k in range(i+1,j+1)]
        rows.append({'lo_s':obs[i]['t'],'hi_s':obs[j]['t'],'first_index':i,'end_index':j,
            'direction':direction(dy,threshold),'predicted_direction':direction(dp,threshold),'direction_correct':direction(dy,threshold)==direction(dp,threshold),
            'observed_delta_C':dy,'predicted_delta_C':dp,'delta_error_C':dp-dy,
            'observed_rate_C_min':60*dy/dt,'predicted_rate_C_min':60*dp/dt,'rate_error_C_min':60*(dp-dy)/dt,
            **metrics(errors)})
        i=j
    return rows,dict(excluded)

def integrate_gauge(s,lo,hi):
    t=s['power_t'];v=s['power_w'];value=covered=0.
    for i in range(len(t)-1):
        a=max(lo,t[i]);b=min(hi,t[i+1])
        if b>a:
            if t[i+1]-t[i]>2:return None
            value+=(b-a)*v[i];covered+=b-a
    return value if abs(covered-(hi-lo))<1e-6 else None

def independent(c,tick,initial,profile,queries):
    # Separate Python implementation of the same fixed RC equations.
    cfg=profile['config'];T=c['initial_c'] if initial=='observed_pre' else 26.;z=0.;J=Hsum=0.;time=35.;event=0
    ev=sorted([(o[k],kind,o['id'],o) for o in c['owners'] for k,kind in [('start_s',1),('end_s',0)]],key=lambda a:(a[0],a[1],a[2]))
    active={}
    while event<len(ev) and ev[event][0]<=35:
        _,kind,key,o=ev[event];event+=1
        if kind:active[key]=o
        else:active.pop(key,None)
    if active:z=1.
    out={};labels={'C':'classification','D':'detection'}
    for query in queries:
        while time<query-1e-10:
            while event<len(ev) and ev[event][0]<=time+1e-10:
                _,kind,key,o=ev[event];event+=1
                if kind:active[key]=o;z=1.
                else:active.pop(key,None)
            end=min(query,time+tick,ev[event][0] if event<len(ev) else math.inf);dt=end-time
            assert dt>0
            tau=cfg['thermal_tau_s'];tail=cfg['idle_tail_s'];decay=math.exp(-dt/tau);one=-math.expm1(-dt/tau)
            leak=math.exp(max(-math.log(3),min(math.log(3),cfg['strength']*cfg['leakage_per_c']*(T-cfg['reference_c']))))
            dynamic=0.
            for o in active.values():
                speed=max(cfg['minimum_speed'],1/(1+cfg['strength']*cfg['cpu_slope' if o['route']=='CPU' else 'gpu_slope']*max(0,T-cfg['onset_c']))) if o['stage']==1 else 1.
                dynamic+=(profile['solo'][labels[o['task']]+'_'+o['route']]-profile['shared'])*((1-cfg['leakage_fraction'])*speed**3+cfg['leakage_fraction']*leak)
            if active:
                z=1.;shared_energy=profile['shared']*dt
                force=cfg['thermal_resistance']*(dynamic+profile['shared'])*one
                area=cfg['thermal_resistance']*(dynamic+profile['shared'])*(dt-tau*one)
            else:
                oz=-math.expm1(-dt/tail);shared_energy=profile['shared']*z*tail*oz
                k=cfg['thermal_resistance']*profile['shared']*z*tail/(tail-tau)
                force=k*(math.exp(-dt/tail)-decay);area=k*(tail*oz-tau*one);z*=math.exp(-dt/tail)
            J+=cfg['baseline']*dt+dynamic*dt+shared_energy
            Hsum+=cfg['idle_c']*dt+(T-cfg['idle_c'])*tau*one+area
            T=cfg['idle_c']+(T-cfg['idle_c'])*decay+force;time=end
        out[query]=(T,J,Hsum)
    return out

def main():
    packet=read(O/'INPUTS.json');pred=json.loads(gzip.decompress((O/'PREDICTIONS.json.gz').read_bytes()));reg=read(O/'REGISTRATION.json')
    for p in [reg['inputs'],*reg['sources']]:assert sha(R/p['path'])==p['sha256'],p['path']
    pc={c['session']:c for c in packet['cases']};old={'A24_'+s['id']:s for s in packet['legacy_power']}
    samples=[];session_rows=[];direction_rows=[];exclusions=[];energy=[];auditmax={'T':0.,'J':0.,'H':0.};checks=0
    for result in pred['cases']:
        c=pc[result['session']];obs=c['observations'];ys=[o['observed_c'] for o in obs]
        for mode in result['modes']:
            label=f"tick{mode['tick']}_{mode['initial']}";base={'session':c['session'],'source':c['source'],'family':c['family'],'schedule_kind':c['schedule_kind'],'mode':label}
            values=mode['AP'];errors=[p-y for p,y in zip(values,ys)]
            op=max(range(len(obs)),key=lambda i:ys[i]);pp=max(range(len(obs)),key=lambda i:values[i])
            session_rows.append({**base,'window_s':obs[-1]['t']-obs[0]['t'],'initial_C':c['initial_c'],'initial_age_s':35-c['initial_time_s'],
                'observed_peak_C':ys[op],'predicted_peak_C':values[pp],'peak_error_C':values[pp]-ys[op],
                'first_observed_peak_s':obs[op]['t'],'first_predicted_sample_peak_s':obs[pp]['t'],'sample_peak_time_error_s':obs[pp]['t']-obs[op]['t'],
                'persistence_initial_MAE_C':mean([abs(c['initial_c']-y) for y in ys]),**metrics(errors)})
            for i,(o,p) in enumerate(zip(obs,values)):
                samples.append({**base,'index':i,'t_s':o['t'],'observed_C':o['observed_c'],'predicted_C':p,'error_C':p-o['observed_c'],
                    'phase':'recovery' if c['last_work_s'] is None or o['t']>c['last_work_s'] else 'work_present'})
            for width,threshold in [(20,.2),(10,.2),(40,.2),(20,.1),(20,.3)]:
                rows,excluded=windows(obs,values,width,threshold)
                for row in rows:direction_rows.append({**base,'width_s':width,'threshold_C':threshold,**row})
                exclusions.append({**base,'width_s':width,'threshold_C':threshold,**excluded})
            if c['session'] in old:
                for w in mode['power_windows']:
                    observed=integrate_gauge(old[c['session']],w['lo'],w['hi']);estimated=w['predicted_J_proxy'];duration=w['hi']-w['lo']
                    diag=estimated+(old[c['session']]['pre_w']-packet['profile']['config']['baseline'])*duration
                    energy.append({**base,**w,'observed_gauge_J_proxy':observed,'signed_error_J_proxy':estimated-observed if observed is not None else None,
                        'relative_error_pct_proxy':100*(estimated-observed)/observed if observed else None,
                        'pre_baseline_only_diagnostic_J_proxy':diag,'pre_baseline_error_J_proxy':diag-observed if observed is not None else None,
                        'absolute_measured_J':None,'absolute_accuracy_PASS':False})
            queries=sorted({*[o['t'] for o in obs],*[w[k] for w in mode['power_windows'] for k in ('lo','hi')]})
            mathout=independent(c,mode['tick'],mode['initial'],packet['profile'],queries)
            for o,value in zip(obs,values):
                diff=abs(mathout[o['t']][0]-value);auditmax['T']=max(auditmax['T'],diff);checks+=1;assert diff<1e-8
            for w in mode['power_windows']:
                diff=abs(mathout[w['hi']][1]-mathout[w['lo']][1]-w['predicted_J_proxy']);auditmax['J']=max(auditmax['J'],diff);checks+=1;assert diff<1e-7
            for field,idx in [('T',0),('J',1),('H',2)]:
                diff=abs(mathout[queries[-1]][idx]-mode['end_state'][field]);auditmax[field]=max(auditmax[field],diff);checks+=1;assert diff<1e-6
    # Aggregate raw AP separately by source contract. Macro excludes session-length weighting.
    grouped=defaultdict(list)
    for row in samples:grouped[(row['family'],row['mode'],'all')].append(row);grouped[(row['family'],row['mode'],row['phase'])].append(row)
    overall=[]
    for (family,mode,phase),rows in sorted(grouped.items()):
        bysession=defaultdict(list)
        for row in rows:bysession[row['session']].append(row['error_C'])
        overall.append({'family':family,'mode':mode,'phase':phase,'sessions':len(bysession),'session_equal_MAE_C':mean([mean([abs(e) for e in v]) for v in bysession.values()]),**metrics([x['error_C'] for x in rows])})
    dg=defaultdict(list)
    for row in direction_rows:dg[(row['family'],row['mode'],row['width_s'],row['threshold_C'],row['direction'])].append(row)
    directions=[]
    for (family,mode,width,threshold,d),rows in sorted(dg.items()):
        errors=[];by=defaultdict(list)
        for row in rows:
            c=pc[row['session']];ps=next(x for x in pred['cases'] if x['session']==row['session']);m=next(x for x in ps['modes'] if f"tick{x['tick']}_{x['initial']}"==mode)
            e=[m['AP'][k]-c['observations'][k]['observed_c'] for k in range(row['first_index']+1,row['end_index']+1)];errors.extend(e);by[row['session']].extend(e)
        directions.append({'family':family,'mode':mode,'width_s':width,'threshold_C':threshold,'direction':d,'windows':len(rows),'sessions':len(by),
            'session_equal_MAE_C':mean([mean([abs(e) for e in v]) for v in by.values()]),'direction_accuracy_pct':100*mean([r['direction_correct'] for r in rows]),
            'rate_MAE_C_min':mean([abs(r['rate_error_C_min']) for r in rows]),'rate_bias_C_min':mean([r['rate_error_C_min'] for r in rows]),
            'delta_MAE_C':mean([abs(r['delta_error_C']) for r in rows]),
            'predicted_rise':sum(r['predicted_direction']=='rise' for r in rows),'predicted_fall':sum(r['predicted_direction']=='fall' for r in rows),
            'predicted_stable':sum(r['predicted_direction']=='stable' for r in rows),**metrics(errors)})
    timing=[];cfg=packet['profile']['config']
    for q in packet['timing']:
        actual=q['observed_vector'];nominal=packet['profile']['nominal'][q['route']];response_i=2 if q['route'].startswith('C') else 3
        for target,n,y in [('INFER',nominal[1],actual[1]),('dispatch_to_response',sum(nominal[:response_i]),sum(actual[:response_i])),('dispatch_to_available',sum(nominal),sum(actual))]:
            timing.append({**q,'target':target,'observed_s':y,'nominal_predicted_s':n,'error_s':n-y,'relative_error_pct':100*(n-y)/y if y else None})
    tg=defaultdict(list)
    for row in timing:tg[(row['route'],row['target'],row['protocol'])].append(row)
    timing_summary=[]
    for (route,target,protocol),rows in sorted(tg.items()):
        timing_summary.append({'route':route,'target':target,'protocol':protocol,'requests':len(rows),'sessions':len({r['session'] for r in rows}),
            'nominal_s':rows[0]['nominal_predicted_s'],'observed_mean_s':mean([r['observed_s'] for r in rows]),'observed_P95_s':quantile([r['observed_s'] for r in rows],.95),
            'MAE_ms':1000*mean([abs(r['error_s']) for r in rows]),'bias_ms':1000*mean([r['error_s'] for r in rows]),
            'median_absolute_relative_error_pct':statistics.median([abs(r['relative_error_pct']) for r in rows if r['relative_error_pct'] is not None]),
            'hardware_verified_requests':sum(r['hardware_verified'] for r in rows),'fresh_holdout':False,'end_to_end_accuracy':False})
    results={'overall_AP':overall,'direction_AP':directions,'session_AP':session_rows,'timing_summary':timing_summary,
        'screening':packet['screening'],'all_arrival_status':packet['all_arrival_status'],'energy':energy,
        'fits':0,'policy_environments':0,'phone_measurements':0,'fresh_confirmation':False,'absolute_energy_accuracy_PASS':False,
        'conditional_schedule_validation_only':True}
    csvwrite(O/'AP_SAMPLES.csv',samples);csvwrite(O/'AP_SESSIONS.csv',session_rows);csvwrite(O/'AP_DIRECTIONS.csv',directions)
    csvwrite(O/'AP_WINDOWS.csv',direction_rows);csvwrite(O/'AP_WINDOW_EXCLUSIONS.csv',exclusions)
    csvwrite(O/'AP_OVERALL.csv',overall);csvwrite(O/'ENERGY_PROXY.csv',energy);csvwrite(O/'TIMING_STATIC.csv',timing)
    csvwrite(O/'TIMING_SUMMARY.csv',timing_summary);csvwrite(O/'SCREENING.csv',packet['screening'])
    write(O/'FINDINGS.json',results)
    write(O/'ARITHMETIC_AUDIT.json',{'status':'PASS','checks':checks,'max_difference':auditmax,'implementation':'independent Python RC vs current JS A24Physics; all saved cases/four modes',
        'empirical_accuracy_PASS':None,'source_pins_unchanged':all(sha(R/p['path'])==p['sha256'] for p in [reg['inputs'],*reg['sources']])})
    print(json.dumps({'status':'COMPLETE','sessions':len(pc),'raw_samples':len(samples),'direction_windows':len(direction_rows),'checks':checks,'max_diff':auditmax},ensure_ascii=False))

if __name__=='__main__':main()
