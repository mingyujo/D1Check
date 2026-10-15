"""Offline report supplement: actual initial AP, preparation and host versions.

Reads recovered traces only. Initial-value subtraction is descriptive, never a
causal adjustment or a calibrated surface-temperature measurement.
"""
import argparse
import csv
import datetime
import json
from pathlib import Path
from d1_a24_laptop_validator import load_json, sha256, NS, PROTOCOL


def host_inference_overlap_ns(events, requests):
    backend={r['request_id']:r['backend'] for r in requests if r.get('backend')}
    opened={};intervals={'CPU':[],'GPU':[]}
    for e in events:
        if e['kind']!='phase' or e.get('stage')!='host_inference':continue
        rid=e['request_id']
        if e['edge']=='start':
            assert rid not in opened,'duplicate inference start'
            opened[rid]=e['mono_ns']
        elif e['edge'] in {'succeeded','failed'}:
            start=opened.pop(rid)
            assert e['mono_ns']>=start,'inference clock reversal'
            intervals[backend[rid]].append((start,e['mono_ns']))
        else:raise ValueError('unknown recorded host-inference edge')
    assert not opened,'incomplete inference call interval'
    for values in intervals.values():
        values.sort()
        assert all(a[1]<=b[0] for a,b in zip(values,values[1:])),'same-lane inference calls overlap'
    return sum(max(0,min(b,d)-max(a,c)) for a,b in intervals['CPU'] for c,d in intervals['GPU'])


def export(job_path, report):
    job=load_json(job_path);root=Path(job['run_root']);plan=load_json(Path(job['plan']))
    audit=[json.loads(s) for s in (root/'adb_commands.jsonl').read_text(encoding='utf-8').splitlines()]
    rows=[]
    for row in plan['sessions']:
        sid=row['session_id'];raw=root/'raw'/sid;analysis=report/(sid+'.analysis.json')
        if not analysis.exists():continue
        a=load_json(analysis);origin=a['trace']['common_origin_ns']
        m=load_json(raw/'session_manifest.json')
        samples=[json.loads(s) for s in (raw/'host_hal_raw.jsonl').read_text(encoding='utf-8').splitlines()]
        before=[s for s in samples if s['device_elapsed_after_ns']<=origin]
        last=max(before,key=lambda x:x['device_elapsed_after_ns']) if before else None
        ap=[v['value_c'] for v in last['sensors'] if v['sensor_name']=='AP' and v['sensor_type']==0] if last else []
        initial=ap[0] if len(ap)==1 else None
        starts=[x for x in audit if 'am' in x['argv'] and 'start' in x['argv'] and sid in ' '.join(x['argv'])]
        assert len(starts)==1,'actual APP launch must be unique, not replayed'
        start=load_json(root/'registry'/PROTOCOL/row['plan_id']/sid/'START.json')
        reference=root/'references'/(row['gate_block_id']+'.json')
        events=[json.loads(s) for s in (raw/'events.jsonl').read_text(encoding='utf-8').splitlines()]
        inference_overlap=host_inference_overlap_ns(events,load_json(raw/'requests.json'))
        assert inference_overlap<=a['trace']['actual_pair_overlap_ns'],'inference overlap outside occupied lanes'
        cold=root/'pre_app_cooldown_v2'/(sid+'.ready.json')
        if not cold.exists():cold=root/'pre_app_cooldown'/(sid+'.ready.json')
        tz=datetime.timezone(datetime.timedelta(hours=9))
        def kst(ns):return datetime.datetime.fromtimestamp(ns/NS,tz).isoformat()
        rows.append({k:row[k] for k in ['session_id','block','recipe','arm','policy_id','reference_role']}|{
            'APP_start_KST':kst(starts[0]['start_wall_ns']),'MAIN_start_KST':kst(start['host_wall_ns']),
            'APP_to_MAIN_s':(start['host_wall_ns']-starts[0]['start_wall_ns'])/NS,
            'reference_Tref_c':load_json(reference)['Tref_c'],'reference_sha256':sha256(reference),
            'last_preMAIN_reported_AP_c':initial,
            'last_preMAIN_read_end_to_origin_s':(origin-last['device_elapsed_after_ns'])/NS if last else None,
            'actual_sensor_cache_age_s':None,'AP_mean_c':a['thermal']['mean_reported_AP_c'],
            'AP_observed_peak_c':a['thermal']['highest_observed_AP_c'],
            'AP_mean_minus_preMAIN_descriptive_c':a['thermal']['mean_reported_AP_c']-initial if initial is not None and a['thermal']['mean_reported_AP_c'] is not None else None,
            'AP_peak_minus_preMAIN_descriptive_c':a['thermal']['highest_observed_AP_c']-initial if initial is not None else None,
            'warmup_inferences':sum(e['kind']=='warmup_result' for e in events),
            'lane_occupancy_overlap_s':a['trace']['actual_pair_overlap_ns']/NS,
            'host_inference_call_overlap_s':inference_overlap/NS,
            'hardware_internal_execution_overlap_verified':False,
            'recorded_pre_APP_passive_s':load_json(cold)['observed_device_elapsed_s'] if cold.exists() else None,
            'manifest_sha256_actual':sha256(raw/'session_manifest.json'),
            'source_manifest_sha256_actual':m['source_manifest_sha256'],
            'manifest_source_commit_is_preparation_base':m['source_commit'],
            'host_preparation_revision':m.get('host_continuation','ORIGINAL_DEV8_V1'),
            'energy_J':None,'surface_temperature_verified':False,'causal_thermal_effect_claim':False})
    path=report/'run_context.csv';assert not path.exists(),'write-once context'
    names=list(dict.fromkeys(k for r in rows for k in r))
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,names);w.writeheader();w.writerows(rows)
    import matplotlib;matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.font_manager import FontProperties
    plt.rcParams['font.family']=FontProperties(fname=r'C:\Windows\Fonts\malgun.ttf').get_name()
    plt.rcParams['axes.unicode_minus']=False
    # First registered block, fixed without outcome ranking, even for later40 runs.
    selected=[r for r in rows if r['block']==rows[0]['block']] if rows else []
    names_ko={'BASE':'직렬 기준','PAIR_G':'병행 허용','ORDER':'납기순 EDD','WAIT200':'200ms 대기','CPU':'분류 CPU','GPU':'분류 GPU'}
    labels=[r['recipe']+' · '+names_ko[r['arm']] for r in selected]
    fig,axes=plt.subplots(1,2,figsize=(14,6));x=list(range(len(selected)))
    axes[0].plot(x,[r['last_preMAIN_reported_AP_c'] for r in selected],'o',label='본측정 직전 읽기값')
    axes[0].plot(x,[r['AP_observed_peak_c'] for r in selected],'s',label='공통 관측창 최고 읽기값')
    axes[0].set_ylabel('HAL AP 읽기값 (℃)');axes[0].legend()
    axes[1].bar(x,[r['AP_peak_minus_preMAIN_descriptive_c'] for r in selected],color='#477b9f')
    axes[1].set_ylabel('최고값 - 본측정 직전값 (℃)')
    for ax in axes:ax.set_xticks(x,labels,rotation=65,ha='right',fontsize=9)
    fig.suptitle('시작 상태를 함께 확인해야 하는 온도 비교')
    fig.text(.5,.015,'시작값을 뺀 수치도 보정된 인과효과·실제 표면온도·에너지 절감을 뜻하지 않습니다.',ha='center',fontsize=10)
    fig.tight_layout(rect=(0,.035,1,.95))
    name='07_시작상태와_보고온도'
    fig.savefig(report/(name+'.png'),dpi=160);fig.savefig(report/(name+'.svg'));plt.close(fig)
    html=report/'index.html';text=html.read_text(encoding='utf-8')
    stage_note='개발 기능검증: 독립 확인 완료가 아닙니다.' if plan['stage']=='DEV' else '등록된 확인 실측: 에너지·표면온도 검증과 구분합니다.'
    warning=f'<p><b>{stage_note}</b> 시작 AP와 실제 호스트 소스를 군별로 기록했습니다. <a href="run_context.csv">시작 상태·소스·대기·워밍업 원장</a>을 함께 보십시오. J는 계산 불가이며, AP는 HAL 읽기값입니다.</p>'
    text=text.replace('<h1>A24 실제 요청 흐름 비교</h1>','<h1>A24 실제 요청 흐름 비교</h1>'+warning)
    html.write_text(text+f'<img src="{name}.png" alt="시작 상태와 관측 최고 AP">',encoding='utf-8')
    print(json.dumps({'status':'OFFLINE_CONTEXT_EXPORTED','sessions':len(rows),'device_commands':0,'causal_thermal_effect_claim':False}))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('job',type=Path);p.add_argument('report',type=Path);a=p.parse_args();export(a.job,a.report)
