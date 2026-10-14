"""Offline exports/figures for registered A24 attempts; no ADB or experiment execution."""
from __future__ import annotations
import argparse,csv,json,math,statistics
from pathlib import Path
from d1_a24_laptop_validator import load_json,sha256
from d1_a24_measurement_analysis import analyze

CONTRASTS=[('L64','PAIR_G','BASE','저부하 병행'),('C252','GPU','CPU','분류 자원'),
           ('M128','ORDER','BASE','납기순'),('M128','PAIR_G','BASE','혼합 병행'),('M128','WAIT200','BASE','200ms 대기')]


def save_csv(path:Path,rows:list[dict]):
    names=list(dict.fromkeys(k for row in rows for k in row))
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,names);w.writeheader();w.writerows(rows)


def export(job:dict,contract:dict,out:Path,stage:str):
    root=Path(job['run_root']);plan=load_json(Path(job['plan']));out.mkdir(parents=True,exist_ok=False)
    refspec=load_json(Path(job.get('quality_references',Path(job['gate']).parent/'quality_references_v1.json')))
    refs={}
    for k,v in refspec.items():
        p=Path(v['path']);assert sha256(p)==v['sha256'],'quality reference changed';refs[k]=load_json(p)
    sessions=[];attempts=[];requests=[];ap_series=[];api_series=[];timelines=[]
    for row in plan['sessions']:
        if row['stage']!=stage:continue
        sid=row['session_id'];raw=root/'raw'/sid;outcome=root/(sid+'.outcome.json')
        status=load_json(outcome)['status'] if outcome.exists() else 'NOT_ATTEMPTED'
        head={k:row[k] for k in ['session_id','stage','block','recipe','arm']}
        attempts.append(head|{'status':status,'planned_requests':row['request_count']})
        if status!='COMPLETE_TRACE_RECOVERED':
            recovery=root/'read_only_recovery'/sid/'recovered_app'
            evidence=recovery if recovery.exists() else raw
            manifest=load_json(evidence/'session_manifest.json') if (evidence/'session_manifest.json').exists() else load_json(Path(job['prepared_manifests'])/(sid+'.json'))
            actual={r['request_id']:r for r in load_json(evidence/'requests.json')} if (evidence/'requests.json').exists() else {}
            attempts[-1]['supplemental_closed_app_recovered']=(recovery/'journal_closed.json').exists()
            attempts[-1]['actual_requests_completed']=sum(r.get('terminal_status') in {'COMPLETED','COMPLETED_DRAIN'} for r in actual.values())
            for q in manifest['requests']:
                requests.append(head|{'request_id':q['request_id'],'ordinal':q['ordinal'],'task':q['task'],
                    'planned_relative_arrival_ns':q['scheduled_arrival_ns'],'planned_relative_deadline_ns':q['deadline_ns'],
                    'terminal_status':'NOT_STARTED_OR_UNRECOVERED','attempt_status':status,'comparison_eligible':False}|actual.get(q['request_id'],{}))
            continue
        result=analyze(raw,contract,refs,(root/'logcat'/f'{sid}.txt').read_text(encoding='utf-8',errors='replace'))
        assert result['decoded_quality']['failures']==0,'decoded quality failed; never select a favorable subset'
        (out/f'{sid}.analysis.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        flat=head|{'planned':result['trace']['planned'],'completed':result['trace']['completed_in_service'],
            'failed':result['trace']['failed'],'unfinished':result['trace']['unfinished'],
            'mean_AP_c':result['thermal']['mean_reported_AP_c'],'observed_peak_AP_c':result['thermal']['highest_observed_AP_c'],
            'thermal_window_status':result['thermal']['status'],'energy_J':None,'energy_status':result['energy']['status'],
            'actual_overlap_s':result['trace']['actual_pair_overlap_ns']/1e9,
            'actual_WAIT_s':result['trace']['wait_actual_ns']/1e9,
            'decision_time_ms':None,'actual_control_energy_J':None}
        for task in ['C','D']:
            for key,value in result['service'][task].items():flat[f'{task}_{key}']=value
        sessions.append(flat);origin=result['trace']['common_origin_ns']
        for request in load_json(raw/'requests.json'):
            requests.append(head|request|{'attempt_status':status,'comparison_eligible':True})
            if request.get('dispatch_ns') is not None and request.get('lane_available_ns') is not None:
                timelines.append(head|{'request_id':request['request_id'],'task':request['task'],'backend':request['backend'],
                    'dispatch_s':(request['dispatch_ns']-origin)/1e9,'available_s':(request['lane_available_ns']-origin)/1e9,
                    'response_s':(request['response_complete_ns']-origin)/1e9})
        for line in (raw/'host_hal_raw.jsonl').read_text(encoding='utf-8').splitlines():
            record=json.loads(line)
            for sensor in record['sensors']:
                if sensor['sensor_name']==contract['AP_name'] and sensor['sensor_type']==contract['AP_type']:
                    ap_series.append(head|{'read_midpoint_s':((record['device_elapsed_before_ns']+record['device_elapsed_after_ns'])/2-origin)/1e9,
                        'reported_AP_c':sensor['value_c'],'cache_age_ns':None})
        for line in (raw/'events.jsonl').read_text(encoding='utf-8').splitlines():
            event=json.loads(line)
            if event['kind']=='sensor_sample':
                api_series.append(head|{k:event.get(k) for k in ['read_start_ns','read_end_ns','current_raw','current_unit','voltage_raw','voltage_unit','charge_counter_raw','charge_unit','battery_level','plugged']})
    for name,rows in [('sessions',sessions),('attempts',attempts),('requests',requests),('reported_AP',ap_series),('battery_API_unvalidated',api_series),('timeline',timelines)]:save_csv(out/(name+'.csv'),rows)
    paired=[];grouped={}
    for recipe,treatment,baseline,label in CONTRASTS:
        for block in sorted({s['block'] for s in sessions}):
            a=[s for s in sessions if (s['block'],s['recipe'],s['arm'])==(block,recipe,treatment)]
            b=[s for s in sessions if (s['block'],s['recipe'],s['arm'])==(block,recipe,baseline)]
            if not a or not b:
                paired.append({'comparison':label,'block':block,'status':'MISSING_REGISTERED_PAIR'});continue
            a,b=a[0],b[0]
            row={'comparison':label,'block':block,'status':'PAIRED','delta_energy_J':None,
                'zero_pair_treatment':recipe=='L64' and a['actual_overlap_s']==b['actual_overlap_s']==0}
            for key in ['mean_AP_c','observed_peak_AP_c','C_response_P95_ms_service_successes','C_on_time_rate_all_planned','D_on_time_rate_all_planned','completed']:
                row['delta_'+key]=a[key]-b[key] if a[key] is not None and b[key] is not None else None
            row['service_nonworsening']=(a['completed']==a['planned']==b['completed']==b['planned'] and
                all(row['delta_'+k] is None or row['delta_'+k]>=0 for k in ['C_on_time_rate_all_planned','D_on_time_rate_all_planned']) and
                (row['delta_C_response_P95_ms_service_successes'] is None or row['delta_C_response_P95_ms_service_successes']<=0))
            paired.append(row)
    save_csv(out/'paired.csv',paired)
    from scipy.stats import t
    intervals=[]
    for label in [c[3] for c in CONTRASTS]:
        for key in ['delta_mean_AP_c','delta_observed_peak_AP_c','delta_C_response_P95_ms_service_successes','delta_C_on_time_rate_all_planned','delta_D_on_time_rate_all_planned']:
            values=[r[key] for r in paired if r['comparison']==label and isinstance(r.get(key),(float,int))]
            n=len(values);mean=statistics.mean(values) if n else None
            width=float(t.ppf(.975,n-1))*statistics.stdev(values)/math.sqrt(n) if n>=2 else None
            intervals.append({'comparison':label,'metric':key,'n_independent_blocks':n,'mean':mean,'lower95':mean-width if width is not None else None,
                'upper95':mean+width if width is not None else None,'method':'unadjusted paired Student-t; exploratory; missing pairs not imputed'})
    save_csv(out/'paired_intervals.csv',intervals)
    provenance={'stage':stage,'plan_sha256':sha256(Path(job['plan'])),'source_sha256':sha256(Path(job['source_manifest'])),
        'APK_sha256':load_json(Path(job['apk_identity']))['apk_sha256'],
        'analysis_contract':contract,'numeric_forecaster':'NOT_CREATED_NO_MODEL_ACCURACY_CLAIM','energy_calibrated':False,
        'attempts':len(attempts),'complete_sessions':len(sessions),'no_device_calls':True,'representative_rule':'first registered block with both M128 BASE/PAIR_G; selected without performance ranking'}
    (out/'provenance.json').write_text(json.dumps(provenance,ensure_ascii=False,indent=2),encoding='utf-8')
    figures(out,sessions,ap_series,timelines)
    print(json.dumps({'stage':stage,'completed_sessions':len(sessions),'planned_sessions':len(attempts),'output':str(out)}))


def figures(out,sessions,ap,timelines):
    import matplotlib;matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.font_manager import FontProperties
    font=FontProperties(fname=r'C:\Windows\Fonts\malgun.ttf');plt.rcParams['font.family']=font.get_name();plt.rcParams['axes.unicode_minus']=False
    recipes={'L64':'저부하 64건','C252':'분류 252건','M128':'혼합 128건'}
    arms={'BASE':'직렬 기준','PAIR_G':'병행 허용','ORDER':'납기순 EDD','WAIT200':'200ms 대기','CPU':'분류 CPU','GPU':'분류 GPU'}
    labels=[f"{recipes.get(s['recipe'],s['recipe'])} · {arms.get(s['arm'],s['arm'])}\n{s['block']} {s['arm']}" for s in sessions]
    def finish(fig,name):
        fig.tight_layout();fig.savefig(out/(name+'.png'),dpi=160);fig.savefig(out/(name+'.svg'));plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(13,5));x=range(len(sessions))
    axes[0].bar(x,[s['C_response_P95_ms_service_successes'] or 0 for s in sessions]);axes[0].set_ylabel('긴급 P95 응답 (ms)')
    axes[1].bar(x,[100*(s['C_on_time_rate_all_planned'] or 0) for s in sessions],label='긴급');axes[1].plot(x,[100*s['D_on_time_rate_all_planned'] if s['D_on_time_rate_all_planned'] is not None else float('nan') for s in sessions],'o-',label='일반');axes[1].set_ylabel('전체 예정 요청 대비 기한 내 완료 (%)');axes[1].legend()
    for ax in axes:ax.set_xticks(list(x),labels,rotation=90,fontsize=7)
    finish(fig,'01_응답과_기한준수')
    fig,ax=plt.subplots(figsize=(13,5));ax.bar(x,[s['mean_AP_c'] if s['mean_AP_c'] is not None else float('nan') for s in sessions],label='평균 AP 읽기값');ax.plot(x,[s['observed_peak_AP_c'] for s in sessions],'o-',label='관측 최고 AP 읽기값');ax.set_xticks(list(x),labels,rotation=90,fontsize=7);ax.set_ylabel('HAL 보고 온도 (℃)');ax.legend();finish(fig,'02_보고된_AP_온도')
    blocks=sorted({s['block'] for s in sessions if s['recipe']=='M128'})
    selected=next((b for b in blocks if {s['arm'] for s in sessions if s['block']==b and s['recipe']=='M128'}>={'BASE','PAIR_G'}),None)
    if selected:
        fig,axes=plt.subplots(2,1,figsize=(13,6),sharex=True)
        for ax,arm in zip(axes,['BASE','PAIR_G']):
            for r in timelines:
                if (r['block'],r['recipe'],r['arm'])==(selected,'M128',arm):
                    y=0 if r['backend']=='CPU' else 1;ax.broken_barh([(r['dispatch_s'],r['available_s']-r['dispatch_s'])],(y-.3,.6),facecolors='#2878b5' if r['task']=='C' else '#d98d27')
            ax.set_yticks([0,1],['CPU 통로','GPU 통로']);ax.set_title('직렬 기준' if arm=='BASE' else '분류 GPU + 탐지 CPU 병행')
        axes[-1].set_xlabel('공통 시작부터 시간 (초)');finish(fig,'03_같은_혼합요청_실행시간표')
        fig,ax=plt.subplots(figsize=(11,4))
        for arm,label in [('BASE','직렬 기준'),('PAIR_G','병행 허용')]:
            rows=[r for r in ap if (r['block'],r['recipe'],r['arm'])==(selected,'M128',arm) and 0<=r['read_midpoint_s']<=210];ax.plot([r['read_midpoint_s'] for r in rows],[r['reported_AP_c'] for r in rows],label=label)
        ax.set_xlabel('공통 시작부터 시간 (초)');ax.set_ylabel('보고된 AP 온도 (℃)');ax.legend();finish(fig,'04_같은_혼합요청_AP경로')
    text='에너지 J: 계산 불가\n전류·전하 보고 단위 불일치\n임의 단위 보정·절감 판정 없음'
    fig,ax=plt.subplots(figsize=(8,3));ax.axis('off');ax.text(.5,.5,text,ha='center',va='center',fontsize=16);finish(fig,'05_에너지_계측의_제한')
    import numpy as np
    conditions=sorted({(s['recipe'],s['arm']) for s in sessions});all_blocks=sorted({s['block'] for s in sessions})
    fig,axes=plt.subplots(1,2,figsize=(12,max(4,len(conditions)*.65)))
    for ax,task,title in zip(axes,['C','D'],['긴급 기한 내 완료율','일반 기한 내 완료율']):
        grid=np.full((len(conditions),len(all_blocks)),np.nan)
        for i,condition in enumerate(conditions):
            for k,block in enumerate(all_blocks):
                match=[s for s in sessions if (s['recipe'],s['arm'])==condition and s['block']==block]
                if match and match[0][f'{task}_on_time_rate_all_planned'] is not None:grid[i,k]=100*match[0][f'{task}_on_time_rate_all_planned']
        im=ax.imshow(grid,vmin=0,vmax=100,cmap='YlGn',aspect='auto');ax.set_title(title);ax.set_xticks(range(len(all_blocks)),all_blocks)
        ax.set_yticks(range(len(conditions)),[recipes.get(r,r)+' · '+arms.get(a,a) for r,a in conditions],fontsize=9)
        for i in range(len(conditions)):
            for k in range(len(all_blocks)):ax.text(k,i,f'{grid[i,k]:.1f}%' if np.isfinite(grid[i,k]) else '해당 없음',ha='center',va='center',fontsize=8)
        fig.colorbar(im,ax=ax,label='%')
    finish(fig,'06_조건별_기한준수_지도')
    html='''<!doctype html><meta charset="utf-8"><title>A24 실측 비교</title><style>body{font-family:Malgun Gothic,sans-serif;max-width:1400px;margin:28px auto;padding:0 20px;color:#17283a}img{width:100%;border:1px solid #ddd;border-radius:12px;margin:12px 0}a{margin-right:16px}</style><h1>A24 실제 요청 흐름 비교</h1><p>서비스·HAL 읽기값을 비교합니다. 표면 온도·센서 정확도·검증된 에너지 절감을 뜻하지 않습니다. 실패·미실행은 attempts.csv에 보존했습니다.</p>'''
    html+=''.join(f'<a href="{name}.csv">{name}.csv</a>' for name in ['sessions','attempts','requests','paired','paired_intervals','reported_AP','battery_API_unvalidated'])
    html+=''.join(f'<img src="{p.name}" alt="{p.stem}">' for p in sorted(out.glob('*.png')))
    (out/'index.html').write_text(html,encoding='utf-8')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('job',type=Path);p.add_argument('contract',type=Path);p.add_argument('output',type=Path);p.add_argument('--stage',choices=['F','DEV','CONFIRM'],required=True);a=p.parse_args();export(load_json(a.job),load_json(a.contract),a.output,a.stage)
