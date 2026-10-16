"""Terminal-only PC publication. Frozen comparators, no fitting or device access."""
import argparse
import gzip
import hashlib
import html
import json
import math
from pathlib import Path
import numpy as np
from tools import d1_ap_tail_observation_plan as plan_module

p=plan_module


def read(file):return json.loads(Path(file).read_text(encoding='utf-8-sig'))


def write(file,value):
    Path(file).write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf8',newline='\n')


def measured_energy(c,lo,hi):
    """Only measured, short-gap power segments; no zero-filled endpoint or gap."""
    t=np.asarray(c['power_t']);w=np.asarray(c['power_w']);duration=hi-lo
    if not math.isfinite(duration) or duration<=0:raise ValueError('energy window')
    covered=energy=0.
    for a,b,pa,pb in zip(t,t[1:],w,w[1:]):
        left,right=max(float(a),lo),min(float(b),hi)
        if right<=left or b-a>2.5 or not np.isfinite([pa,pb]).all():continue
        x=pa+(pb-pa)*(left-a)/(b-a);y=pa+(pb-pa)*(right-a)/(b-a)
        covered+=right-left;energy+=(x+y)/2*(right-left)
    return dict(full_energy_j=energy if abs(covered-duration)<1e-6 else None,
                covered_energy_j=energy if covered else None,covered_s=covered,missing_s=max(0.,duration-covered))


def phase_score(c,pred,lo,hi):
    use=[i for i,t in enumerate(c['q']) if lo<=t<=hi]
    if len(use)<2:return dict(samples=len(use),mae_c=None,max_absolute_error_c=None)
    obs=[c['ap'][i] for i in use];y=[pred[i] for i in use]
    return dict(samples=len(use),start_s=c['q'][use[0]],end_s=c['q'][use[-1]],
                **p.j.m.base.common.score(obs,y),observed_change_c=obs[-1]-obs[0],predicted_change_c=y[-1]-y[0],
                direction_match=bool(np.sign(obs[-1]-obs[0])==np.sign(y[-1]-y[0])),
                observed_peak_c=max(obs),predicted_peak_c=max(y))


def assess_case(c,original,models):
    # Targets and measured power are not passed into the prediction API.
    if not c['q'] or len(c['q'])!=len(c['ap']):raise ValueError('AP target coverage')
    predictions={'FROZEN':p.j.m.predict(c,c['actual'],original,dict(name='FROZEN'))[0]}
    predictions.update({name:p.tail.predict(c,original,model)[0] for name,model in models.items()})
    end=c['actual'][-1]['end_s'];metrics=[]
    for name,y in predictions.items():
        for phase,lo,hi in [('full_AP',35.,end),('registered600',35.,635.),('recovery1920',635.,end)]:
            metrics.append(dict(model=name,phase=phase,**phase_score(c,y,lo,hi)))
    energy=[]
    for phase,lo,hi in [('reference120',0.,120.),('registered600',35.,635.),('recovery1920',635.,end)]:
        cov=measured_energy(c,lo,hi);obs=cov['full_energy_j']
        y=p.j.m.energy_prediction(c,c['actual'],original,dict(name='FROZEN'),hi)-p.j.m.energy_prediction(c,c['actual'],original,dict(name='FROZEN'),lo)
        energy.append(dict(phase=phase,start_s=lo,end_s=hi,predicted_j=y,observed_j=obs,**cov,
            signed_error_j=y-obs if obs is not None else None,absolute_error_j=abs(y-obs) if obs is not None else None,
            relative_error=(y-obs)/obs if obs else None))
    return predictions,metrics,energy


def consumption(root,plan,receipt,external_commands):
    result=dict(receipt_status=receipt['status'],sessions=[],external_adb_commands=external_commands,
                internal_adb_commands=receipt.get('adb_command_slots'),explicit_inference=receipt.get('explicit_inference'),
                elapsed_seconds=receipt.get('elapsed_seconds'),approval_budget=plan['budget'])
    result['total_adb_commands']=result['internal_adb_commands']+external_commands if result['internal_adb_commands'] is not None else None
    result['failure_progress_counts']=receipt.get('last_session_progress',{}).get('counts')
    for entry in plan['entries']:
        folder=root/f"{entry['index']:02d}_{entry['session_id']}";item=dict(index=entry['index'],profile=entry['profile'],work_cap=entry['work_requests'],
            status='not_attempted' if not (folder/'attempt.json').exists() else 'attempted_not_validated')
        if (folder/'validated.json').exists():
            s=read(folder/'validated.json');item.update({k:s[k] for k in ('work_calls','warmup_calls','eligibility_calls','runtimes','status','elapsed_seconds')})
        for name,key in [('artifacts/cleanup.json','app_cleanup'),('host_cleanup.json','host_cleanup')]:
            if (folder/name).exists():item[key]=read(folder/name)
        result['sessions'].append(item)
    counts=result['failure_progress_counts']
    if counts:
        inferred={name:value['actual_started_upper'] if value['confirmed_started_at_least']==value['confirmed_returned']==value['actual_started_upper'] else None for name,value in counts.items()}
        result['failed_session_exact_counts_from_complete_bounds']=inferred
        result['failed_session_confirmed_explicit_inference']=sum(inferred[n] for n in ('warmup','eligibility','load')) if all(inferred.get(n) is not None for n in ('warmup','eligibility','load')) else None
    return result


def publish(plan_file,output,external_commands=0):
    plan_file=Path(plan_file);plan=read(plan_file);root=Path(plan['output_root']);receipt=read(root/'FINAL_RECEIPT.json')
    if receipt['status'] not in ('completed_regimen_diagnostic_only','stopped_no_resume'):raise ValueError('not terminal')
    if p.old.p.digest(plan_file)!=read(Path(plan['registry'])/'claimed.json')['plan_sha256']:raise ValueError('claimed plan drift')
    models=p.verify_frozen(plan);original=read(plan['original_model']['path'])
    out=Path(output);out.mkdir(parents=True,exist_ok=False)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    summary=consumption(root,plan,receipt,external_commands);write(out/'consumption.json',summary)
    if summary['total_adb_commands'] is not None and summary['total_adb_commands']>plan['budget']['adb_command_slots']:
        raise ValueError('aggregate ADB budget exceeded; preserve receipt')
    metrics=[];energy=[];curves=[];sessions=[];segments=[];inputs=[];inventory={}
    colors=dict(FROZEN='tab:orange',LOAD_SLOW='tab:green',CLOCK_SHIFT='tab:red')
    for entry in plan['entries']:
        folder=root/f"{entry['index']:02d}_{entry['session_id']}";label=entry['profile']
        for name in ('validated.json','input_manifest.json','thermal.jsonl','host_cleanup.json','artifacts/progress.jsonl',
                     'artifacts/cleanup.json','artifacts/start_ap.accepted.json','artifacts/summary.json'):
            if (folder/name).exists():inventory[label+'/'+name]=p.old.p.digest(folder/name)
        if not (folder/'validated.json').exists():continue
        stats=read(folder/'validated.json');c=stats['analysis_case'];inputs.append(c)
        predictions,rows,energies=assess_case(c,original,models)
        for r in rows:metrics.append(dict(session=label,**r))
        for r in energies:
            recorded=stats['energy_windows'][r['phase']]
            for k in ('observed_j','predicted_j','signed_error_j'):
                if r[k] is None or recorded[k] is None:
                    if r[k]!=recorded[k]:raise ValueError('null/coverage differs from host validation')
                elif abs(r[k]-recorded[k])>1e-6:raise ValueError('energy reproduction mismatch')
            energy.append(dict(session=label,**r))
        accepted=read(folder/'artifacts/start_ap.accepted.json')
        sessions.append(dict(session=label,role='independent block confirmation of fixed comparators, no refit',
            work_calls=stats['work_calls'],warmup_calls=stats['warmup_calls'],eligibility_calls=stats['eligibility_calls'],
            ap_start_c=accepted['ap_c'],pre_ap_last_c=c['pre'][-1]['ap'],pre_reference_is_ambient=False,
            in_candidate_development_pre_last_range=26.5<=c['pre'][-1]['ap']<=28.8,
            in_legacy_start_range=32.5<=accepted['ap_c']<=34.0,
            ap_samples=len(c['q']),power_samples=len(c['power_t']),max_ap_gap_s=max(np.diff(c['q'])),
            max_power_gap_s=max(np.diff(c['power_t'])),actual_common_end_s=c['common_end_s'],actual_observation_end_s=c['actual'][-1]['end_s'],
            actual_last_lane_s=c['last_lane_s'],strict_support=False,accuracy_pass=None,
            state_exposure_s=json.dumps(p.j.m.base.exposure(c['actual'],35,c['common_end_s']).tolist())))
        segments.extend(dict(session=label,**s) for s in c['actual'])
        for i,t in enumerate(c['q']):
            curves.append(dict(session=label,t_s=t,observed_c=c['ap'][i],**{name:y[i] for name,y in predictions.items()}))
        fig,axes=plt.subplots(3,1,figsize=(13,10),sharex=True)
        x=np.array(c['q'])-35.;obs=np.array(c['ap']);axes[0].plot(x,obs,color='black',label='observed AP')
        axes[0].scatter([r['t']-35 for r in c['pre']],[r['ap'] for r in c['pre']],s=6,c='gray',label='pre-load AP (initial input)')
        for name,y in predictions.items():
            axes[0].plot(x,y,color=colors[name],label=name+' (diagnostic)')
            axes[1].plot(x,np.array(y)-obs,color=colors[name],label=name)
        axes[1].axhline(0,c='gray',lw=.8)
        for s in c['actual']:
            state=p.j.m.thermal.state_key(s['state'])
            if state!='resident_idle':axes[2].plot([s['start_s']-35,s['end_s']-35],[p.tail.s.STATES.index(state)+1]*2,lw=5,c='tab:blue')
        axes[2].set_yticks(range(5),['idle']+list(p.tail.s.STATES));axes[2].axvline(600,c='gray',ls='--')
        axes[0].set_ylabel('AP (C)');axes[1].set_ylabel('prediction - observation (C)');axes[2].set_xlabel('seconds since registered common start')
        axes[0].legend();axes[1].legend();fig.suptitle(label+' | frozen coefficients; long horizon extrapolation; no accuracy PASS')
        fig.tight_layout();fig.savefig(out/(label+'_ap.png'));plt.close(fig)
        # Delta paths are a decomposition only, not a new corrected prediction.
        fig,ax=plt.subplots(figsize=(13,4));ax.plot(x,obs-obs[0],c='black',label='observed delta')
        for name,y in predictions.items():ax.plot(x,np.array(y)-y[0],c=colors[name],label=name+' delta')
        ax.set(xlabel='seconds since common start',ylabel='change from first post-load AP sample (C)',title=label+' | initial-offset decomposition only')
        ax.legend();fig.tight_layout();fig.savefig(out/(label+'_delta.png'));plt.close(fig)
        # Display only a covered cumulative path; do not manufacture the final cooling endpoint.
        et=[];eo=[];ep=[]
        for t in c['q'][::5]:
            if t<=35:continue
            r=measured_energy(c,35.,t);et.append(t-35);eo.append(r['full_energy_j'])
            ep.append(p.j.m.energy_prediction(c,c['actual'],original,dict(name='FROZEN'),t)-p.j.m.energy_prediction(c,c['actual'],original,dict(name='FROZEN'),35))
        fig,ax=plt.subplots(figsize=(13,4));ax.plot(et,[np.nan if v is None else v for v in eo],c='black',label='observed covered prefix')
        ax.plot(et,ep,c='tab:orange',label='unchanged frozen energy equation');ax.set(xlabel='seconds since common start',ylabel='cumulative J',title=label+' | endpoint gaps remain missing; A24 raw=mA conditional')
        ax.legend();fig.tight_layout();fig.savefig(out/(label+'_energy.png'));plt.close(fig)
    for name,rows in [('metrics.csv',metrics),('energy.csv',energy),('curves.csv',curves),('sessions.csv',sessions),('states.csv',segments)]:p.tail.s.csv_write(out/name,rows)
    if inputs:
        (out/'inputs.json.gz').write_bytes(gzip.compress(json.dumps(inputs,allow_nan=False).encode('utf8'),mtime=0))
    write(out/'inventory.json',dict(raw_files=inventory,receipt_sha256=p.old.p.digest(root/'FINAL_RECEIPT.json'),
        plan_sha256=p.old.p.digest(plan_file),candidates_sha256=plan['frozen_candidates']['sha256'],original_model_sha256=plan['original_model']['sha256']))
    headings=''.join('<h2>'+html.escape(s['session'])+'</h2>'+''.join('<img style="max-width:100%" src="'+s['session']+'_'+kind+'.png">' for kind in ('ap','delta','energy')) for s in sessions)
    links='<a href="consumption.json">실제 소비/cleanup</a>'
    if sessions:links+=' · <a href="metrics.csv">구간별 AP 오차</a> · <a href="energy.csv">J 창/coverage</a> · <a href="sessions.csv">세션·초기 조건</a>'
    app_error=receipt.get('app_terminal_evidence',{}).get('session_failure.json',{}).get('message',receipt.get('error',''))
    note='고정 모형의 실제 일정 조건부 외삽 진단입니다.' if sessions else '등록 block을 완료하지 못했습니다. 원본 오류: '+html.escape(app_error)+'. 완성된 관측–예측 비교 그림이나 전체 block 예측오차를 만들지 않습니다.'
    page='<!doctype html><html lang="ko"><meta charset="utf-8"><title>긴 C0·부하 회복 확인</title><style>body{font:17px/1.7 system-ui;max-width:1100px;margin:32px auto}aside{background:#fff2ce;padding:18px}table{border-collapse:collapse}td,th{padding:9px;border-bottom:1px solid #bbb}</style><h1>긴 무부하 대조·부하 회복</h1><aside>'+note+' 계수 재적합0·기본/RL/strict/experiment_ready=false 유지. 한 C0→부하 block은 물리 원인·τ·반복 안정성·정책 우월성을 보장하지 않습니다.</aside><p>종료 상태: '+html.escape(receipt['status'])+' · 적격 세션 '+str(len(sessions))+'/2</p>'+links+headings
    (out/'index.html').write_text(page,encoding='utf8',newline='\n')
    write(out/'summary.json',dict(receipt_status=receipt['status'],validated_sessions=len(sessions),fit_calls=0,
        time_identified=False,default_changed=False,strict_support=False,accuracy_pass=None,experiment_ready=False))
    return dict(output=str(out),validated_sessions=len(sessions),metrics_rows=len(metrics),energy_rows=len(energy),fit_calls=0)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--plan',required=True);parser.add_argument('--output',required=True)
    parser.add_argument('--external-adb-commands',type=int,default=0);args=parser.parse_args()
    print(json.dumps(publish(args.plan,args.output,args.external_adb_commands),ensure_ascii=False))
