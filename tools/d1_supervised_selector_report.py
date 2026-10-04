"""Verify saved causal selections and ledgers, then report without new simulation."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import html
import json
import math
from pathlib import Path
import pickle
import statistics
from tools import d1_supervised_selector as m
from tools import d1_request_ppo as rl
p=m.p


def report(folder):
    folder=Path(folder)
    freeze=json.loads((folder/'freeze_before_final.json').read_text(encoding='utf8'))
    spec=json.loads((folder/'preregistered.json').read_text(encoding='utf8'))
    summary=json.loads((folder/'summary.json').read_text(encoding='utf8'))
    for path,sha in freeze['hashes'].items():
        assert p.digest(p.ROOT/path)==sha,path
    assert p.digest(folder/'local_models.pkl')==freeze['model_sha256']
    # This pickle was generated locally by this run and its frozen hash checked.
    models=pickle.loads((folder/'local_models.pkl').read_bytes())
    envs={e['id']:e for e in m.s.envelopes()}
    for d in freeze['decisions']:
        c=m.choose(models[d['model']],m.previous(envs[d['envelope']],d['seed']),d['mode'],freeze['bounds'])
        assert c=={k:d[k] for k in ('policy','reason','predictions')}
    rows=m.read(folder/'results.csv')
    key=lambda r:(r['envelope'],int(r['seed']),r['scenario'],r['policy'])
    ix={key(r):r for r in rows};assert len(ix)==len(rows)
    expected=set()
    for e in envs:
        for seed in spec['spec']['final_seeds']:
            policies={'EFT_REFERENCE','SPLIT_REFERENCE','CPU_REFERENCE'}|{
                d['policy'] for d in freeze['decisions'] if d['envelope']==e and d['seed']==seed}
            expected|={(e,seed,sc,pol) for sc in m.s.a.old.SCENARIOS for pol in policies}
    assert set(ix)==expected
    model,case=p.inputs(p.BUNDLE);initial=case['initial'];seen=set();maxdiff=0.;requests=0
    with (folder/'local_ledgers.jsonl').open(encoding='utf8') as f:
        for line in f:
            item=json.loads(line);r=item['meta'];k=key(r);assert k not in seen;seen.add(k)
            ledger=item['ledger'];tickets=m.s.workload(envs[r['envelope']],int(r['seed']))
            assert len(ledger)==len(tickets)==48;requests+=48
            for q,z in zip(tickets,ledger):
                assert all(q[t]==z[t] for t in ('id','ordinal','arrival_ns','task','priority','deadline_offset_ns'))
                times=[z[t] for t in ('dispatch_ns',*m.s.a.old.engine.FIELDS) if t in z]
                assert times==sorted(times) and (not times or times[0]>=q['arrival_ns'])
            for backend in ('CPU','GPU'):
                jobs=sorted([z for z in ledger if z.get('backend')==backend],key=lambda z:z.get('dispatch_ns',120e9))
                assert all(a.get('lane_available_ns',120e9)<=b.get('dispatch_ns',120e9) for a,b in zip(jobs,jobs[1:]))
            urgent=sorted(z['response_ns']/1e6 for z in ledger if z['priority']=='urgent' and 'response_ns' in z)
            normal=[z['response_ns']/1e6 for z in ledger if z['priority']=='normal' and 'response_ns' in z]
            metrics=dict(urgent_p95_ms=urgent[math.ceil(.95*len(urgent))-1] if urgent else None,
                         normal_mean_ms=statistics.mean(normal) if normal else None)
            rr,(segments,_,_,_)=rl.outcome(dict(ledger=ledger,metrics=metrics),initial,model)
            for field,v in rr.items():
                if field in ('actions','controllable_decisions'):continue
                w=ix[k][field]
                assert (v is None and w is None) or (v is not None and w is not None and abs(v-w)<1e-8),(k,field)
            j=120*initial['preload_power_w']+sum(max(0,min(120,z['end_s'])-z['start_s'])*model['energy_increment_w'][z['state']]
                for z in segments if z['state']!='idle')
            maxdiff=max(maxdiff,abs(j-r['energy_j']))
    assert seen==expected and maxdiff<1e-8
    # Cost-model diagnostics on the evaluated policy subset, not all 8 actions.
    errors=[]
    for name,ms in models.items():
        for eid,seed,_,policy in sorted(ix):
            if any(z['model']==name and z['envelope']==eid and z['seed']==seed and z['policy']==policy for z in errors):continue
            xs=[ix[eid,seed,sc,policy] for sc in m.s.a.old.SCENARIOS]
            x=m.vector(m.features(m.previous(envs[eid],seed),0),policy)
            pred=[float(mm.predict([x])[0]) for mm in ms]
            actual=[max(1-r['deadline_met']/r['planned'] for r in xs)]+[
                statistics.mean(r[t] for r in xs) for t in m.TARGETS[1:]]
            errors.append(dict(model=name,envelope=eid,seed=seed,policy=policy,withheld=m.holdout(envs[eid]),
                **{f'pred_{t}':v for t,v in zip(m.TARGETS,pred)},
                **{f'actual_{t}':v for t,v in zip(m.TARGETS,actual)},
                **{f'error_{t}':v-w for t,v,w in zip(m.TARGETS,pred,actual)}))
    m.s.save_rows(folder/'prediction_errors.csv',errors)
    agg=[];detail=[];reasons=[]
    for name in m.MODELS:
        for mode in m.MODES:
            ds=[d for d in freeze['decisions'] if d['model']==name and d['mode']==mode]
            for reason,count in Counter(d['reason'] for d in ds).items():
                reasons.append(dict(model=name,mode=mode,reason=reason,windows=count,total=54))
            for subset in ('all','seen_envelopes','withheld_envelopes'):
                selected=[d for d in ds if subset=='all' or d['withheld']==(subset=='withheld_envelopes')]
                xs=[ix[d['envelope'],d['seed'],sc,d['policy']] for d in selected for sc in m.s.a.old.SCENARIOS]
                for ref in ('EFT_REFERENCE','SPLIT_REFERENCE','CPU_REFERENCE'):
                    bs=[ix[r['envelope'],r['seed'],r['scenario'],ref] for r in xs]
                    stat=m.group_result(xs,bs)
                    stat.update(full_service_cases=sum(r['completed']==r['planned']==r['deadline_met'] for r in xs),
                        worse_service_cases=sum(r['deadline_met']<b['deadline_met'] for r,b in zip(xs,bs)),
                        reference_full_service_cases=sum(b['completed']==b['planned']==b['deadline_met'] for b in bs),
                        joint_gain_cases=sum(m.s.useful(r,b) for r,b in zip(xs,bs)))
                    agg.append(dict(model=name,mode=mode,subset=subset,reference=ref,selected=freeze['selected'][mode]==name,**stat))
            for d in ds:
                for sc in m.s.a.old.SCENARIOS:
                    r=ix[d['envelope'],d['seed'],sc,d['policy']];b=ix[d['envelope'],d['seed'],sc,'EFT_REFERENCE']
                    detail.append(dict(model=name,mode=mode,envelope=d['envelope'],seed=d['seed'],scenario=sc,
                        selected=freeze['selected'][mode]==name,withheld=d['withheld'],policy=d['policy'],reason=d['reason'],
                        deadline_met=r['deadline_met'],planned=r['planned'],reference_deadline_met=b['deadline_met'],
                        delta_j=r['energy_j']-b['energy_j'],delta_peak_ap_c=r['peak_ap_c']-b['peak_ap_c'],
                        delta_urgent_p95_ms=r['urgent_p95_ms']-b['urgent_p95_ms']))
    m.s.save_rows(folder/'metrics.csv',agg);m.s.save_rows(folder/'decisions.csv',detail);m.s.save_rows(folder/'fallback.csv',reasons)
    chosen=[r for r in agg if r['selected'] and r['subset']=='all']
    p.write(folder/'evaluation.json',dict(selected=freeze['selected'],metrics=chosen,fallback=reasons,
        no_device_confirmation=True,experiment_ready=False))
    verify=dict(result='PASS',utc=datetime.now(timezone.utc).isoformat(),base_head=spec['spec']['base_head'],uncommitted=True,
        cases=len(rows),requests=requests,source_and_physical_hashes_unchanged=True,decision_reproduction=True,
        ledger_and_metrics_recomputed=True,max_independent_energy_difference_j=maxdiff,
        raw_sha256=p.digest(folder/'local_ledgers.jsonl'),device_commands=0,simulation_reruns=0)
    p.write(folder/'verification.json',verify)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(2,1,figsize=(13,7),sharex=True)
    for ax,mode,field,label in zip(axes,m.MODES,('delta_j','delta_peak_ap_c'),('Energy difference vs EFT (J)','Peak AP difference vs EFT (C)')):
        vals=[];colors=[]
        for eid in envs:
            ds=[r for r in detail if r['selected'] and r['mode']==mode and r['envelope']==eid]
            vals.append(statistics.mean(r[field] for r in ds))
            colors.append('#bd4b3a' if any(r['deadline_met']<r['planned'] for r in ds) else '#237c78')
        ax.bar(range(27),vals,color=colors);ax.axhline(0,color='black',linewidth=.8);ax.set_ylabel(label)
        ax.set_title(mode+' selected learner: '+freeze['selected'][mode])
    axes[-1].set_xticks(range(27),[e.replace('g','').replace('_c',' / ').replace('_b',' / ') for e in envs],rotation=65,ha='right',fontsize=7)
    fig.suptitle('Synthetic frozen-model evaluation; red = any deadline miss (not a device result)')
    fig.tight_layout();fig.savefig(folder/'comparison.png',dpi=140);plt.close(fig)
    table=''.join('<tr>'+''.join('<td>'+html.escape(str(r[k]) if not isinstance(r[k],float) else f'{r[k]:.6f}')+'</td>' for k in
        ('model','mode','reference','deadline_met','planned','full_service_cases','worse_service_cases','mean_delta_energy_j','mean_delta_peak_ap_c'))+'</tr>' for r in chosen)
    page='''<!doctype html><html lang="ko"><meta charset="utf-8"><title>지도학습 정책 선택기</title>
<style>body{font:16px sans-serif;max-width:1200px;margin:40px auto;line-height:1.6}td,th{border:1px solid #ccc;padding:6px}table{border-collapse:collapse}img{width:100%}</style>
<h1>이전 요청 기록으로 선택하는 지도학습 스케줄러</h1>
<p>PC 합성입력 평가. 실측 절감·strict 검증·기한 보장 아님. 미래 trace/실현 처리시간을 선택기에 입력하지 않음.</p>
<p>이전48요청과 다음48요청이 같은 부하 분포라는 가정. 이전 이력의 열은 이어붙이지 않고 동일 initial0 사용.
콜드스타트·분포 변화·요청별 정책 전환·다른 AP 초기조건은 미검증. EFT fallback도 서비스 보장 아님.</p>
<p>18부하 조합·36이력으로 학습,9조합 통째 제외. 저장 자료로 두 모형 선정 후 새2seed×27조합×3처리문맥 확인.
학습에 쓰지 않은 조합도 이전 연구에서는 본 조건이며 물리모형의 독립 실기기 확인이 아님.</p>
<h2>선정 모형의 전체162조건 — 실패도 포함</h2><table><tr><th>모형</th><th>목적</th><th>기준</th><th>기한충족</th><th>요청분모</th><th>전 요청 충족 사례</th><th>기준보다 서비스 악화</th><th>ΔJ</th><th>Δ최고AP</th></tr>'''+table+'''</table>
<img src="comparison.png" alt="조건별 비용차이와 기한 실패 표시"><p>음수는 해당 비용 감소. 에너지/열 목적 그림은 다른 선택이며 공동 개선을 뜻하지 않음.</p>
<p><a href="metrics.csv">모든 모형·학습/미학습 조합·기준별 수치</a> · <a href="decisions.csv">결정·실패·응답차이</a> · <a href="fallback.csv">fallback</a> · <a href="../README.md">설계·결론·재현</a></p></html>'''
    (folder/'index.html').write_text(page,encoding='utf8')
    print(json.dumps(dict(verification=verify,selected=freeze['selected'],metrics=chosen),indent=2))


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--folder',required=True);args=ap.parse_args();report(args.folder)
