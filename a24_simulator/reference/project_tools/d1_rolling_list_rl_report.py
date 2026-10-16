"""Analyze completed bounded pilot; no environment, fit, learning or device."""
import csv,gzip,hashlib,html,json,statistics
from datetime import datetime,timezone
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from tools import d1_rolling_list_rl_run as x

PUBLIC=x.PUBLIC
def table(path,rows):
    if not rows:return
    keys=list(dict.fromkeys(k for row in rows for k in row))
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=keys);writer.writeheader();writer.writerows(rows)
def names(role):
    fixed={'L0':'기한 우선 리스트 L0','Band':'Band 판단규칙 대응','Triton':'Triton 판단규칙 대응','OriginalV2':'기존 공동 롤링','Rule':'같은 후보 비학습 선택기'}
    if role in fixed:return fixed[role]
    if role.startswith('NoWait'):return '대기 제거 · seed'+role[6:]
    if role.startswith('NoThermal'):return '명시 열특징 제거 · seed'+role[9:]
    return 'PPO seed'+role[3:].replace('_',' · 학습')
def identity(role,condition):
    if role.startswith('NoWait'):return f'nowait_{role[6:]}_{condition:02d}'
    if role.startswith('NoThermal'):return f'nothermal_{role[9:]}_{condition:02d}'
    return f'dev_{role}_{condition:02d}'
def schedule(raw):return [(q['id'],q.get('backend'),q.get('dispatch_ns'),q.get('response_ns'),q.get('lane_available_ns'),q['status']) for q in raw['result']['ledger']]
def save(fig,name):
    fig.tight_layout();fig.savefig(PUBLIC/(name+'.png'),dpi=150);svg=PUBLIC/(name+'.svg');fig.savefig(svg)
    svg.write_text('\n'.join(line.rstrip() for line in svg.read_text(encoding='utf-8').splitlines())+'\n',encoding='utf-8');plt.close(fig)


def old_wait_diagnosis():
    """Read the earlier completed pilot only, using arrival timestamps at the wait."""
    parent=x.previous;completion=parent.read(parent.LOCAL/'completion.json');out=[]
    for case in parent.read(parent.LOCAL/'inputs.json')['cases']:
        i=case['condition']
        load=lambda role:json.loads(gzip.decompress((parent.LOCAL/'items'/f'pilot_{role}_{i:03d}.json.gz').read_bytes()))
        old=load('Band');candidate=load('ExecutionPrefix');by={q['id']:q for q in old['result']['ledger']}
        waits=[d['now_ns'] for d in candidate['result']['decisions'] if d.get('action_kind')=='cool_wait']
        first=min(waits) if waits else None
        for q in candidate['result']['ledger']:
            if q['priority']!='normal' or not q['late_success'] or by[q['id']]['late_success']:continue
            out.append(dict(condition=i,seed=case['seed'],family=case['family'],context=case['context'],request_id=q['id'],
                reference_response_ms=by[q['id']]['response_ns']/1e6,new_response_ms=q['response_ns']/1e6,
                first_cooling_s=first/1e9 if first is not None else None,request_arrival_s=q['arrival_ns']/1e9,
                arrived_at_first_cooling=first is not None and q['arrival_ns']<=first,
                queued_D_at_first_cooling=sum(z['task']=='detection' and z['arrival_ns']<=first<z['dispatch_ns'] for z in candidate['result']['ledger']) if first is not None else None))
    table(PUBLIC/'prior_added_deadline_failures.csv',out)
    return dict(added_normal_failures=len(out),not_yet_arrived_at_first_cooling=sum(not q['arrived_at_first_cooling'] for q in out),new_native=0,
        interpretation='later arrival risk is outside current-queue protection; first wait alone is not proved to be the sole cause')


def run():
    reg=x.check();result=x.read(x.LOCAL/'completion.json');assert result['status']=='completed'
    rows=result['rows'];roles=list(dict.fromkeys(v['policy'] for v in rows));by={(v['condition'],v['policy']):v for v in rows}
    assert len(by)==len(rows)
    controls=[];equivalence=[];summaries=[];learning=[];alias_groups={};samples=0;opportunities=0
    for row in rows:
        raw=x.read_raw(identity(row['policy'],row['condition']));tickets=x.read(x.LOCAL/'inputs.json')['development'][row['condition']]['tickets']
        x.previous.audit(raw['result'],tickets);snapshots=raw['snapshots'];callbacks=raw['callback_seconds'];ledger=raw['result']['ledger']
        row['urgent_planned']=sum(q['priority']=='urgent' for q in ledger);row['normal_planned']=sum(q['priority']=='normal' for q in ledger)
        for step in snapshots:
            physical=np.array(step['physical_mask'],dtype=bool);mask=np.array(step['mask'],dtype=bool)
            assert mask[step['chosen']] and not (mask & ~physical).any()
            samples+=1;opportunities+=sum(mask)>1
        controls.append(dict(condition=row['condition'],policy=row['policy'],callback_count=len(callbacks),callback_total_s=sum(callbacks),callback_max_ms=max(callbacks,default=0)*1000,
            projection_calls=raw['projection_calls'],projection_seconds=raw['projection_seconds'],snapshots=len(snapshots),multiple_admitted=sum(sum(s['mask'])>1 for s in snapshots),
            non_L0=sum(s['chosen']!=0 for s in snapshots),selected_cooling=sum(s['actions'][s['chosen']]['kind']=='cool_wait' for s in snapshots),
            cooling_count=raw['cooling_count'],actual_cooling_s=raw['total_extra_wait'],max_request_cooling_s=max(raw['request_wait'].values(),default=0),
            classification_CPU=sum(q['task']=='classification' and q.get('backend')=='CPU' for q in ledger),classification_GPU=sum(q['task']=='classification' and q.get('backend')=='GPU' for q in ledger),
            selected_resource_wait=sum(s['actions'][s['chosen']]['kind']=='resource_wait' for s in snapshots),admission_rejections=json.dumps(raw['admission_rejections'],sort_keys=True)))
        if row['policy'].startswith('PPO'):
            equivalence.append(dict(condition=row['condition'],policy=row['policy'],same_L0=schedule(raw)==schedule(x.read_raw(identity('L0',row['condition']))),same_Rule=schedule(raw)==schedule(x.read_raw(identity('Rule',row['condition']))),same_Band=schedule(raw)==schedule(x.read_raw(identity('Band',row['condition'])))))
        if row['policy']=='Rule' and snapshots:
            s=snapshots[0];key=hashlib.sha256(json.dumps({k:s[k] for k in ('state','candidates','mask')},sort_keys=True,separators=(',',':')).encode()).hexdigest()
            alias_groups.setdefault(key,[]).append(dict(condition=row['condition'],family=row['family'],context=row['context'],arrival_seed=row['arrival_seed']))
    for role in roles:
        subset=[v for v in rows if v['policy']==role];planned=sum(v['planned'] for v in subset);normal=sum(v['normal_planned'] for v in subset);fail=sum(v['normal_failure'] for v in subset)
        summaries.append(dict(policy=role,name_ko=names(role),conditions=len(subset),planned=planned,completed=sum(v['completed'] for v in subset),incomplete=sum(v['incomplete'] for v in subset),
            urgent_planned=sum(v['urgent_planned'] for v in subset),normal_planned=normal,urgent_failure=sum(v['urgent_failure'] for v in subset),normal_failure=fail,normal_on_time_completion_rate=(normal-fail)/normal,
            mean_urgent_p95_ms=statistics.mean(v['urgent_p95_ms'] for v in subset),mean_normal_ms=statistics.mean(v['normal_mean_ms'] for v in subset),mean_energy_j=statistics.mean(v['energy_j'] for v in subset),mean_peak_ap_c=statistics.mean(v['peak_ap_c'] for v in subset),native_seconds=sum(v['native_seconds'] for v in subset)))
    differences=[]
    for role in roles:
        if role in ('L0','Band','Triton'):continue
        for row in [q for q in rows if q['policy']==role]:
            for reference in ('L0','Band','Triton','Rule'):
                base=by[(row['condition'],reference)]
                differences.append(dict(policy=role,baseline=reference,condition=row['condition'],family=row['family'],context=row['context'],
                    **{'delta_'+k:row[k]-base[k] for k in ('incomplete','urgent_failure','normal_failure','urgent_p95_ms','normal_mean_ms','energy_j','peak_ap_c')}))
    for seed in x.SEEDS:
        for log in x.read(x.LOCAL/f'learning_{seed}.json')['updates']:
            learning.append(dict(seed=seed,update=log['update'],episodes=log['accepted_episodes'],frames=log['frames'],sampled_choices=log['sampled_choices'],optimizer_steps=log['optimizer_steps_cumulative'],
                actor_gradient_max=max(v['gradients']['actor'] for v in log['steps']),critic_gradient_max=max(v['gradients']['critic'] for v in log['steps']),
                direct_energy_max=log['direct_energy_max'],lambda_J=log['lambda_after'][0],lambda_normal=log['lambda_after'][3],seconds=log['seconds'],gamma=log['gamma']))
    table(PUBLIC/'comparison.csv',rows);table(PUBLIC/'policy_summary.csv',summaries);table(PUBLIC/'paired_differences.csv',differences);table(PUBLIC/'control_cost.csv',controls);table(PUBLIC/'schedule_equivalence.csv',equivalence);table(PUBLIC/'learning_updates.csv',learning)
    x.write(PUBLIC/'initial_observation_aliases.json',dict(scope='first public decision only; identical encoded input, not future arrival disclosure',groups=[dict(input_hash=k,conditions=v) for k,v in alias_groups.items() if len(v)>1]))
    diagnosis=old_wait_diagnosis();x.write(PUBLIC/'prior_wait_diagnosis.json',diagnosis)
    final=dict(status='completed',task=x.TASK,summary=summaries,gates=result['gates'],non_learning_gates={role:x.gate_rows(rows,role) for role in ('Rule','OriginalV2')},consumption=result['consumption'],
        policy_checkpoint_choice='all terminal32;16 kept as learning-stage diagnostic',training_episodes_per_seed=32,updates_per_seed=4,learning_seed_count=3,
        source_sha256=reg['source_sha256'],resume_verification=x.read(x.LOCAL/'resume_verification.json'),prior_wait_diagnosis=diagnosis,
        mask_snapshot_audits=samples,multiple_admitted_snapshots=opportunities,final_confirmation=0,automatic_adoption=False,
        model_fit_calls=0,device_commands=0,thermal_service_feedback=False,surface_temperature=None,thermal_limit_exceed_seconds=None,phone_control_energy=None,
        development_scope_only=True,experiment_ready=False,generated_utc=datetime.now(timezone.utc).isoformat())
    x.write(PUBLIC/'summary.json',final)
    plt.rcParams.update({'font.family':'Malgun Gothic','axes.unicode_minus':False,'font.size':10,'svg.fonttype':'none'})
    final_roles=['L0','Band','Triton','OriginalV2','Rule']+[f'PPO{s}_32' for s in x.SEEDS]
    subset=[next(s for s in summaries if s['policy']==role) for role in final_roles];labels=['L0','Band','Triton','원 롤링','비학습 규칙','PPO11','PPO23','PPO37']
    fig,axes=plt.subplots(1,3,figsize=(15,4))
    for ax,key,title in zip(axes,['normal_failure','mean_urgent_p95_ms','mean_normal_ms'],['일반 기한실패 (전체 도착 분모)','긴급P95 조건 평균 (ms)','일반 응답 조건 평균 (ms)']):
        ax.bar(range(8),[s[key] for s in subset],color=['#aaa','#789','#ba7','#79b','#685']+['#397']*3);ax.set_xticks(range(8),labels,rotation=25);ax.set_title(title);ax.grid(axis='y',alpha=.2)
    save(fig,'서비스와_완료')
    fig,axes=plt.subplots(1,2,figsize=(12,4))
    for ax,key,title in zip(axes,['mean_energy_j','mean_peak_ap_c'],['기기 전체 J120 조건 평균','모형 최고 AP 조건 평균 (°C)']):
        values=[s[key] for s in subset];ax.bar(range(8),values,color=['#aaa','#789','#ba7','#79b','#685']+['#397']*3);ax.set_xticks(range(8),labels,rotation=25);ax.set_title(title);ax.set_ylim(min(values)*.995,max(values)*1.005)
    fig.suptitle('확대된 축 · 작은 모형 차이를 실기기 절감으로 확정하지 않음');save(fig,'에너지와_모형온도')
    fig,axes=plt.subplots(1,3,figsize=(14,4))
    for seed in x.SEEDS:
        ss=[s for s in summaries if s['policy'] in (f'PPO{seed}_16',f'PPO{seed}_32')]
        for ax,key in zip(axes,['normal_failure','mean_energy_j','mean_peak_ap_c']):ax.plot([16,32],[s[key] for s in ss],'-o',label='seed'+str(seed))
    for ax,title in zip(axes,['같은 개발조건 일반 기한실패','같은 개발조건 평균 에너지 (J)','같은 개발조건 평균 최고 AP (°C)']):ax.set_title(title);ax.set_xticks([16,32]);ax.set_xlabel('학습 에피소드');ax.grid(alpha=.2);ax.legend();ax.ticklabel_format(axis='y',style='plain',useOffset=False)
    save(fig,'학습량과_개발성능')
    fig,axes=plt.subplots(1,3,figsize=(12,7))
    for ax,seed in zip(axes,x.SEEDS):
        data=np.array([[by[(i,f'PPO{seed}_32')]['normal_failure']-by[(i,'Rule')]['normal_failure'],by[(i,f'PPO{seed}_32')]['energy_j']-by[(i,'Rule')]['energy_j'],by[(i,f'PPO{seed}_32')]['peak_ap_c']-by[(i,'Rule')]['peak_ap_c']] for i in range(24)])
        # Separate units per column; annotate actual values rather than treating units as one objective.
        norm=np.max(np.abs(data),axis=0);norm[norm==0]=1;ax.imshow(data/norm,aspect='auto',cmap='RdBu_r',vmin=-1,vmax=1)
        for i in range(24):
            for j in range(3):ax.text(j,i,f'{data[i,j]:.3g}',ha='center',va='center',fontsize=7)
        ax.set_xticks(range(3),['기한실패Δ','에너지ΔJ','최고APΔ°C']);ax.set_yticks(range(24));ax.set_title('규칙 기준 PPO'+str(seed)+' 변화')
    fig.suptitle('조건별 실제 차이 · 색은 열별 정규화, 단위 합산 아님');save(fig,'조건별_RL추가효과')
    fig,axes=plt.subplots(1,2,figsize=(11,4))
    for seed in x.SEEDS:
        pair=[next(s for s in summaries if s['policy']==role) for role in (f'PPO{seed}_32',f'NoWait{seed}')]
        for ax,key in zip(axes,['normal_failure','mean_peak_ap_c']):ax.plot([0,1],[s[key] for s in pair],'-o',label='seed'+str(seed))
    for ax,title in zip(axes,['일반 기한실패','최고 AP 조건 평균 (°C)']):ax.set_title(title);ax.set_xticks([0,1],['원 PPO','평가 대기 제거']);ax.grid(alpha=.2);ax.legend();ax.ticklabel_format(axis='y',style='plain',useOffset=False)
    fig.suptitle('같은 weights의 평가 진단 · 구성요소별 재학습 인과효과 아님');save(fig,'대기행동_제거')
    visible=[dict(정책=names(s['policy']),완료=f"{s['completed']}/{s['planned']}",긴급실패=s['urgent_failure'],일반실패=s['normal_failure'],긴급P95_ms=f"{s['mean_urgent_p95_ms']:.3f}",일반응답_ms=f"{s['mean_normal_ms']:.3f}",에너지_J=f"{s['mean_energy_j']:.6f}",최고AP_C=f"{s['mean_peak_ap_c']:.6f}") for s in summaries]
    grid='<table><tr>'+''.join('<th>'+k+'</th>' for k in visible[0])+'</tr>'+''.join('<tr>'+''.join('<td>'+html.escape(str(v))+'</td>' for v in q.values())+'</tr>' for q in visible)+'</table>'
    verdict='개발 유망 후보 있음 · 최종 채택 미확정' if any(v['promising'] for key,v in result['gates'].items() if key.endswith('_32')) else '전조건 RL 채택 기준 미달 · 기준 정책 유지'
    page='<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>롤링 리스트 PPO 작은 파일럿</title><style>body{font:15px Malgun Gothic,system-ui;background:#f6f8fa;color:#20343f;margin:28px}main{max-width:1280px;margin:auto}p{line-height:1.7}table{border-collapse:collapse;background:white}td,th{border:1px solid #cdd8de;padding:7px;font-size:13px}img{width:100%;background:white}h2{margin-top:30px}.scroll{overflow:auto}.card{padding:18px;background:white;border-left:5px solid #397}</style><main>'
    page+='<h1>롤링 리스트 + 같은 후보 선택 PPO</h1><p class="card"><strong>'+verdict+'</strong><br>학습seed11·23·37 각32에피소드 · 16/32 같은 개발24조건 비교 · 실제Adam/부분배치 재개4학습 exact</p><p>기본·복귀·학습참조·예측후속은 리스트L0입니다. Band는 비교군입니다. 상태에는 공개된 큐·도착 이력·누적 대기와 실측 기반 모형추정만 있습니다. 마스킹과 예측허용은 실제 미래기한 보장이 아닙니다. 원모형의 냉각→처리속도 회복은 여전히 미지원입니다.</p><p><a href="README.md">한국어 판독</a> · <a href="execution_contract.json">실행 전 계약</a> · <a href="comparison.csv">전량 CSV</a> · <a href="paired_differences.csv">조건별 대응차이</a> · <a href="learning_updates.csv">실제 학습·gradient·승수</a> · <a href="control_cost.csv">마스크·선택·대기·PC부담</a></p>'
    page+='<h2>모든 seed와 학습 단계</h2><p>응답/J/AP는조건별평균,실패는예정긴급/일반전체분모입니다. 3문맥은민감도이며독립반복이아닙니다. 개발자료결과이며새최종확인0입니다.</p><div class="scroll">'+grid+'</div>'
    for name in ('서비스와_완료','에너지와_모형온도','학습량과_개발성능','조건별_RL추가효과','대기행동_제거'):page+='<h2>'+name.replace('_',' ')+'</h2><img alt="'+name+'" src="'+name+'.svg">'
    page+='<p>기기 실행/새모형적합0 · 표면온도/안전한도 초과/폰 판단에너지 계산불가. PC시간을폰 제어시간이나전력으로전용하지않습니다. 작은학습의실패를RL일반실패/수렴완료로부르지않습니다. 기본·strict·experiment_ready=false 유지.</p></main></html>'
    (PUBLIC/'index.html').write_text(page,encoding='utf-8')
    print(json.dumps(dict(summary=summaries,gates={k:dict(promising=v['promising'],maintenance=v['maintenance_pass'],Rule_maintenance=v['same_bank_Rule_maintenance']) for k,v in result['gates'].items()},consumption=result['consumption'],learning=learning),indent=2))

if __name__=='__main__':run()
