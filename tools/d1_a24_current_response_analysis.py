"""Predeclared descriptive excitation-to-API response; no sensor-only delay/J calibration."""
import argparse
import csv
import json
import statistics
from pathlib import Path
from d1_a24_laptop_validator import load_json,sha256


def crossing(samples,threshold,after,before,period_s,direction=1):
    """First of two successive observed reads; no interpolation across sparse gaps."""
    selected=[(t,v) for t,v in samples if after<=t<=before]
    for (t,v),(t2,v2) in zip(selected,selected[1:]):
        if 0<t2-t<=2.5*period_s and direction*(v-threshold)>=0 and direction*(v2-threshold)>=0:return t-after
    return None


def pulse_response(samples,on,off,pre_begin,post_end,period_s):
    # samples contain read midpoint, discharge-positive API raw integer.
    before=[v for t,v in samples if max(pre_begin,on-10)<=t<on]
    late_on=[v for t,v in samples if max(on,off-4)<=t<=off]
    late_post=[v for t,v in samples if max(off,post_end-10)<=t<=post_end]
    result={'baseline_samples':len(before),'late_on_samples':len(late_on),'late_post_samples':len(late_post),'rise_t10_s':None,'rise_t50_s':None,'fall_t50_s':None}
    if min(len(before),len(late_on),len(late_post))<5:return {**result,'status':'INSUFFICIENT_READS'}
    base=statistics.median(before);plateau=statistics.median(late_on);post=statistics.median(late_post)
    mad=statistics.median(abs(v-base) for v in before);delta=plateau-base
    result.update(baseline_raw=base,late_on_raw=plateau,late_post_raw=post,delta_raw=delta,baseline_MAD_raw=mad)
    if delta<=0 or delta<=3*mad:return {**result,'status':'NO_CLEAR_INCREASE_ABOVE_BASELINE_VARIATION'}
    result['rise_t10_s']=crossing(samples,base+.1*delta,on,off,period_s)
    result['rise_t50_s']=crossing(samples,base+.5*delta,on,off,period_s)
    if plateau>post:
        result['fall_t50_s']=crossing(samples,post+.5*(plateau-post),off,post_end,period_s,-1)
    result['status']='OBSERVED_RESPONSE' if result['rise_t50_s'] is not None else 'NO_T50_CROSSING_WITHIN_ON_WINDOW'
    return result


def analyze(root,out):
    assert not out.exists(),'new write-once analysis destination required'
    rows=[json.loads(line) for line in (root/'events.jsonl').read_text().splitlines()]
    config=load_json(root/'config.json');closure=load_json(root/'journal_closed.json');summary=load_json(root/'summary.json')
    assert sha256(root/'events.jsonl')==closure['events_sha256']
    assert [x['sequence'] for x in rows]==list(range(len(rows)))
    assert all(a['mono_ns']<=b['mono_ns'] for a,b in zip(rows,rows[1:]))
    origin=rows[0]['mono_ns'];sensors=[x for x in rows if x['kind']=='sensor_sample']
    invalid=[x for x in sensors if x['current_raw'] is None or x['current_raw']>0 or x['plugged']!=0]
    def read_time(x):return ((x['current_read_start_ns']+x['current_read_end_ns'])/2-origin)/1e9
    samples=[(read_time(x),-x['current_raw']) for x in sensors if x not in invalid]
    controls=[]
    for i,period in enumerate(config['idle_control_periods_ms']):
        rs=[x for x in sensors if x['phase']=='CONTROL_'+str(i)];vs=[-x['current_raw'] for x in rs if x not in invalid]
        times=[read_time(x) for x in rs]
        controls.append({'control':i,'period_ms':period,'samples':len(rs),'invalid':sum(x in invalid for x in rs),
            'median_discharge_raw':statistics.median(vs) if vs else None,'min_raw':min(vs) if vs else None,'max_raw':max(vs) if vs else None,
            'median_actual_read_interval_s':statistics.median(b-a for a,b in zip(times,times[1:])) if len(times)>1 else None,
            'query_thread_CPU_ms_excluding_log_write':sum(x['sampler_thread_cpu_ns'] for x in rs)/1e6})
    pulses=[]
    for i,p in enumerate(config['pulses']):
        es=[x for x in rows if x['phase'].startswith('PULSE_'+str(i)+'_')]
        starts=[x for x in es if x['kind']=='load_start'];ends=[x for x in es if x['kind']=='load_end']
        item={'pulse':i,**p}
        if len(starts)!=1 or len(ends)!=1:
            pulses.append({**item,'status':'PULSE_NOT_COMPLETED'});continue
        assert starts[0]['resource']==ends[0]['resource']==p['resource']
        onset=(starts[0]['execution_boundary_ns']-origin)/1e9;off=(ends[0]['execution_boundary_ns']-origin)/1e9
        begin=next(x['mono_ns'] for x in es if x['kind']=='phase_start')/1e9-origin/1e9
        postend=max(x['mono_ns'] for x in es)/1e9-origin/1e9
        affected=[x for x in invalid if begin<=read_time(x)<=postend]
        measured=pulse_response(samples,onset,off,begin,postend,p['period_ms']/1000) if not affected else {'status':'INVALID_CURRENT_READ_PRESERVED'}
        pulses.append({**item,'on_s':onset,'off_s':off,'actual_on_duration_s':off-onset,'batches':ends[0]['batches'],**measured})
    # Development observations are descriptive; held-out values are shown separately.
    report={'schema':'a24-current-response-analysis-v1','status':summary['status'],'completed_pulses':summary['completed_pulses'],
        'sensor_reads':len(sensors),'invalid_reads':len(invalid),'pulses':pulses,'idle_controls':controls,
        'physical_J_validated':False,'API_units_verified':False,'sensor_only_delay_identified':False,
        'time_correction_applied':False,'controls_are_short_ordered_observations_not_meter_calibration':True,
        'load':'synthetic one-thread CPU arithmetic / offscreen GLES3 shader; not model inference',
        'rule':'pre-last10s median, on-last4s median, post-last10s median; positive delta>3*preMAD; two consecutive crossings; no time shifting',
        'source_sha256':sha256(Path(__file__)),'events_sha256':sha256(root/'events.jsonl')}
    out.mkdir(parents=True)
    (out/'analysis.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    for name,rs in [('pulses',pulses),('idle_controls',controls)]:
        columns=list(dict.fromkeys(k for r in rs for k in r))
        with (out/(name+'.csv')).open('w',newline='',encoding='utf-8') as f:
            writer=csv.DictWriter(f,fieldnames=columns);writer.writeheader();writer.writerows(rs)
    print(json.dumps({'status':report['status'],'sensor_reads':len(sensors),'invalid_reads':len(invalid),'pulses':pulses}))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('root',type=Path);parser.add_argument('out',type=Path)
    a=parser.parse_args();analyze(a.root,a.out)
