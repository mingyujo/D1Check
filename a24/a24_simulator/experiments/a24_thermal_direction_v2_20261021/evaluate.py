"""Compare held-group predictions with the old RC at identical raw samples."""
import csv,gzip,json,math,statistics
from collections import defaultdict
from prepare import H,R,A,O,OLD,PREV,FIRST,read,write,pin,sha
from thermal_model import window_pairs

def mean(v):return sum(v)/len(v) if v else None
def quantile(v,p):
    v=sorted(v)
    if not v:return None
    t=(len(v)-1)*p;i=int(t);return v[i]+(v[min(i+1,len(v)-1)]-v[i])*(t-i)
def metrics(e):
    return {'n':len(e),'MAE_C':mean([abs(x) for x in e]),'RMSE_C':math.sqrt(mean([x*x for x in e])) if e else None,'bias_C':mean(e),
        'P95_abs_C':quantile([abs(x) for x in e],.95),'max_abs_C':max(map(abs,e),default=None),'within_0_5C_pct':100*mean([abs(x)<=.5 for x in e]) if e else None}
def cls(delta,threshold):return 'rise' if delta>=threshold-1e-10 else 'fall' if delta<=-threshold+1e-10 else 'stable'
def csvwrite(p,rows):
    fields=list(dict.fromkeys(k for r in rows for k in r))
    with p.open('x',encoding='utf-8-sig',newline='') as file:
        w=csv.DictWriter(file,fieldnames=fields);w.writeheader();w.writerows(rows)

def main():
    inp=read(O/'INPUTS.json');old={r['session']:r for r in json.loads(gzip.decompress((OLD/'PREDICTIONS.json.gz').read_bytes()))['cases']};new={r['session']:r for r in read(O/'OOF_PREDICTIONS.json')['cases']}
    prev={r['session']:r for r in read(PREV/'OOF_PREDICTIONS.json')['cases']};first={r['session']:r for r in read(FIRST/'OOF_PREDICTIONS.json')['cases']}
    ablations={r['session']:r for r in read(O/'ABLATION_PREDICTIONS.json')['cases']}
    samples=[];sessions=[];windows=[];labels={};fits=read(O/'FIT_COMPLETE.json');assert fits['fits']<=360
    for c in inp['cases']:
        sid=c['session'];before=next(m['AP'] for m in old[sid]['modes'] if m['tick']==.05 and m['initial']=='observed_pre')
        preds={'ORIGINAL_RC':before,'CALIBRATED_V1_OOF':prev[sid]['AP_C'],'CALIBRATED_OOF':new[sid]['AP_C'],
            'DIRECTION01_OOF':first[sid]['AP_C'],'NO_DIRECTION_LOSS':ablations[sid]['NO_DIRECTION_LOSS'],'NO_TRANSPORT':ablations[sid]['NO_TRANSPORT'],
            'INITIAL_AP_FIXED':[c['initial_c']]*len(before)}
        model=read(O/f"{c['family']}_OUTER_{new[sid]['outer_fold']}.json")['model'];assert c['group'] not in model['training_groups'] and sid not in model['training_sessions']
        for scope in ['registered','full'] if c['family']=='m8' else ['full']:
            ids=[i for i,o in enumerate(c['observations']) if scope=='full' or o['t']<=180];obs=[c['observations'][i] for i in ids]
            for policy,allpred in preds.items():
                pp=[allpred[i] for i in ids];ys=[o['observed_c'] for o in obs];e=[p-y for p,y in zip(pp,ys)]
                base={'session':sid,'family':c['family'],'group':c['group'],'scope':scope,'policy':policy,'outer_fold':new[sid]['outer_fold']}
                sessions.append({**base,'first_s':obs[0]['t'],'last_s':obs[-1]['t'],**metrics(e),
                    'observed_peak_C':max(ys),'predicted_peak_C':max(pp),'peak_error_C':max(pp)-max(ys)})
                for i,(o,p) in enumerate(zip(obs,pp)):
                    samples.append({**base,'index':i,'t_s':o['t'],'observed_C':o['observed_c'],'predicted_C':p,'error_C':p-o['observed_c'],
                        'phase':'recovery' if c['last_work_s'] is None or o['t']>c['last_work_s'] else 'work_present'})
                for width,threshold in [(20,.2),(10,.2),(40,.2),(20,.1),(20,.3)]:
                    for i,j in window_pairs(obs,width):
                        dy=ys[j]-ys[i];dp=pp[j]-pp[i];dt=obs[j]['t']-obs[i]['t'];key=(sid,scope,width,threshold,i,j)
                        label=cls(dy,threshold)
                        if key in labels:assert labels[key]==label
                        labels[key]=label
                        windows.append({**base,'width_s':width,'threshold_C':threshold,'direction':label,'predicted_direction':cls(dp,threshold),'direction_correct':cls(dp,threshold)==label,
                            'i':i,'j':j,'lo_s':obs[i]['t'],'hi_s':obs[j]['t'],'observed_delta_C':dy,'predicted_delta_C':dp,'delta_error_C':dp-dy,
                            'rate_error_C_min':60*(dp-dy)/dt,**metrics(e[i+1:j+1])})
    allsummary=[];groups=defaultdict(list)
    for row in samples:
        for phase in ['all',row['phase']]:groups[(row['family'],row['scope'],row['policy'],phase)].append(row)
    for (family,scope,policy,phase),rows in sorted(groups.items()):
        by=defaultdict(list)
        for row in rows:by[row['session']].append(row['error_C'])
        allsummary.append({'family':family,'scope':scope,'policy':policy,'phase':phase,'sessions':len(by),'session_equal_MAE_C':mean([mean([abs(x) for x in v]) for v in by.values()]),**metrics([r['error_C'] for r in rows])})
    dirs=[];dg=defaultdict(list)
    for row in windows:dg[(row['family'],row['scope'],row['policy'],row['width_s'],row['threshold_C'],row['direction'])].append(row)
    for (family,scope,policy,width,threshold,d),rows in sorted(dg.items()):
        n=sum(r['n'] for r in rows)
        dirs.append({'family':family,'scope':scope,'policy':policy,'width_s':width,'threshold_C':threshold,'direction':d,'windows':len(rows),'n':n,
            'MAE_C':sum(r['MAE_C']*r['n'] for r in rows)/n,'RMSE_C':math.sqrt(sum(r['RMSE_C']**2*r['n'] for r in rows)/n),'bias_C':sum(r['bias_C']*r['n'] for r in rows)/n,
            'direction_accuracy_pct':100*mean([r['direction_correct'] for r in rows]),'delta_MAE_C':mean([abs(r['delta_error_C']) for r in rows]),
            'rate_MAE_C_min':mean([abs(r['rate_error_C_min']) for r in rows]),'rate_bias_C_min':mean([r['rate_error_C_min'] for r in rows]),
            'predicted_rise':sum(r['predicted_direction']=='rise' for r in rows),'predicted_fall':sum(r['predicted_direction']=='fall' for r in rows),'predicted_stable':sum(r['predicted_direction']=='stable' for r in rows)})
    comparisons=[];worsening=[]
    for c in inp['cases']:
        scope='registered' if c['family']=='m8' else 'full';rr=[r for r in sessions if r['session']==c['session'] and r['scope']==scope];before=next(r for r in rr if r['policy']=='CALIBRATED_V1_OOF');after=next(r for r in rr if r['policy']=='CALIBRATED_OOF')
        row={'session':c['session'],'family':c['family'],'group':c['group'],'scope':scope,'before_MAE_C':before['MAE_C'],'after_MAE_C':after['MAE_C'],'change_C':after['MAE_C']-before['MAE_C'],
            'before_peak_error_C':before['peak_error_C'],'after_peak_error_C':after['peak_error_C']}
        comparisons.append(row)
        if row['change_C']>1e-10:worsening.append(row)
    gg=defaultdict(list)
    for row in comparisons:gg[(row['family'],row['group'])].append(row)
    group_summary=[{'family':family,'group':group,'sessions':len(rows),'before_MAE_C':mean([r['before_MAE_C'] for r in rows]),'after_MAE_C':mean([r['after_MAE_C'] for r in rows]),'worsened_sessions':sum(r['change_C']>1e-10 for r in rows)} for (family,group),rows in sorted(gg.items())]
    confusion=[]
    for family,scope in [('m8','registered'),('m8','full'),('old','full')]:
        for policy in ['ORIGINAL_RC','CALIBRATED_V1_OOF','CALIBRATED_OOF','DIRECTION01_OOF','NO_DIRECTION_LOSS','NO_TRANSPORT','INITIAL_AP_FIXED']:
            rows=[r for r in dirs if (r['family'],r['scope'],r['policy'],r['width_s'],r['threshold_C'])==(family,scope,policy,20,.2)]
            confusion.append({'family':family,'scope':scope,'policy':policy,'windows':sum(r['windows'] for r in rows),
                'overall_direction_accuracy_pct':sum(r['direction_accuracy_pct']*r['windows'] for r in rows)/sum(r['windows'] for r in rows),
                'balanced_direction_accuracy_pct':mean([r['direction_accuracy_pct'] for r in rows])})
    result={'overall':allsummary,'directions':dirs,'session_comparisons':comparisons,'worsening':worsening,'group_summary':group_summary,'direction_overall':confusion,
        'OOF_groups':{'m8':22,'old':5},'fits':fits['fits'],'fresh_confirmation':False,'policy_environments':0,'new_measurements':0,'absolute_energy_accuracy_PASS':None}
    write(O/'FINDINGS.json',result);csvwrite(O/'AP_SAMPLES.csv',samples);csvwrite(O/'AP_SESSIONS.csv',sessions);csvwrite(O/'AP_WINDOWS.csv',windows)
    csvwrite(O/'AP_OVERALL.csv',allsummary);csvwrite(O/'AP_DIRECTIONS.csv',dirs);csvwrite(O/'SESSION_COMPARISON.csv',comparisons);csvwrite(O/'GROUP_COMPARISON.csv',group_summary)
    csvwrite(O/'WORSENING.csv',worsening or [{'note':'No worsened session by primary-window MAE'}])
    write(O/'EVALUATION_RECEIPT.json',{'source':pin(H/'evaluate.py'),'OOF_source':pin(O/'OOF_PREDICTIONS.json'),'baseline_source':pin(OLD/'PREDICTIONS.json.gz'),
        'samples':len(samples),'windows':len(windows),'sessions':106,'new_fits':0,'new_predictions':0})
    print(json.dumps({'status':'EVALUATION_COMPLETE','samples':len(samples),'windows':len(windows),'worsening':worsening,'direction_overall':confusion},ensure_ascii=False))
if __name__=='__main__':main()
