"""Full-input/capped-calendar descriptive evidence; no fitting or simulation."""
import argparse
import csv
import gzip
import html
import json
import statistics
from pathlib import Path
from tools import d1_method_followup as f


def records(path):
    return [json.loads(line) for line in gzip.decompress(Path(path).read_bytes()).decode('utf8').splitlines()]


def verify_registered_source(file,digest,root):
    current=f.x.p.ROOT/file
    if f.x.p.digest(current)==digest:return 'current'
    if file=='tools/d1_arrival_explore.py':
        from tools.d1_compatible_timing_backfill import verify_legacy_engine
        return verify_legacy_engine(digest)
    if file=='tools/d1_industrial_scheduling.py':
        archive=root/'source_snapshots/d1_industrial_scheduling.py'
        if f.x.p.digest(archive)!=digest:raise ValueError('historical search source hash mismatch')
        expected=archive.read_text(encoding='utf8').replace('time.monotonic()-began>timeout:',
            'time.monotonic()-began>=timeout:')
        if current.read_text(encoding='utf8')!=expected:raise ValueError('search source changed beyond zero-time equality guard')
        return 'exact_archive_plus_verified_zero_time_guard_only'
    # Preserve the exact earlier source, and accept only the explicitly added
    # policy namespace. Physical accounting/controller bodies must be identical.
    if file!='tools/d1_empirical_request_policy.py':raise ValueError('registered source changed '+file)
    candidates=list((root/'source_snapshots').glob('d1_empirical_request_policy*.py'))
    matching=[a for a in candidates if f.x.p.digest(a)==digest]
    if len(matching)!=1:raise ValueError('historical source archive hash mismatch')
    archive=matching[0]
    original=archive.read_text(encoding='utf8')
    import re
    expected=re.sub(r'^RECEDING_POLICIES = .*\n','',original,flags=re.M)
    expected=expected.replace("INDUSTRIAL_POLICIES = ('ATC_QUEUED_GUARD_V1', 'CPU_BOTTLENECK_GUARD_V1', 'INDUSTRIAL_OFFLINE_REPLAY_V1')\n",
        "INDUSTRIAL_POLICIES = ('ATC_QUEUED_GUARD_V1', 'CPU_BOTTLENECK_GUARD_V1', 'INDUSTRIAL_OFFLINE_REPLAY_V1')\nRECEDING_POLICIES = ('PARETO_BEAM_SERVICE_V1', 'PARETO_BEAM_IMMEDIATE_V2')\n")
    expected=expected.replace('*INDUSTRIAL_POLICIES, *RECEDING_POLICIES)', '*INDUSTRIAL_POLICIES)')
    expected=expected.replace('*CONDITION_POLICIES, *INDUSTRIAL_POLICIES)', '*CONDITION_POLICIES, *INDUSTRIAL_POLICIES, *RECEDING_POLICIES)')
    if current.read_text(encoding='utf8')!=expected:raise ValueError('accounting implementation changed beyond namespace')
    return 'exact_archive_plus_verified_namespace_only_extension'


def exposure(record,frozen):
    rows=[]
    for state in ('idle',*frozen['energy_increment_w']):
        seconds=sum(max(0.,min(120.,s['end_s'])-max(0.,s['start_s'])) for s in record['segments'] if s['state']==state)
        slope=frozen['ap']['parameters']['ap_slope_at_30_c_per_s']
        label='resident_idle' if state=='idle' else state
        rows.append(dict(state=state,seconds=seconds,incremental_j=0. if state=='idle' else seconds*frozen['energy_increment_w'][state],
            integrated_heating_input_c=seconds*(slope[label]-slope['resident_idle'])))
    return rows


def energy(record,t,frozen,initial):
    return t*initial['preload_power_w']+sum(max(0.,min(t,s['end_s'])-max(0.,s['start_s']))*
        frozen['energy_increment_w'][s['state']] for s in record['segments'] if s['state']!='idle')


def aggregate_candidates(pairs):
    """Group the supplied candidates, without the old fixed-policy whitelist."""
    grouped={}
    for r in pairs:grouped.setdefault((r['stage'],r['envelope'],r['policy']),[]).append(r)
    return [dict(stage=k[0],envelope=k[1],policy=k[2],cases=len(rs),
        planned=sum(r['planned'] for r in rs),deadline_met=sum(r['deadline_met'] for r in rs),
        full_service_cases=sum(r['full_service'] for r in rs),
        joint_nonworsening_cases=sum(r['joint_nonworsening'] for r in rs),
        **{'mean_'+field:statistics.mean(r[field] for r in rs) if all(r[field] is not None for r in rs) else None
            for field in ('delta_energy_j','delta_peak_ap_c','delta_thermal_degree_seconds',
                'delta_urgent_p95_ms','delta_normal_mean_ms','delta_deadline_met')}) for k,rs in grouped.items()]


def build(root):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    root=Path(root);run=root/'run_v1';calendar=root/'calendar_v1'
    rs=records(run/'records.jsonl.gz');cs=records(calendar/'records.jsonl.gz')
    beam_records={name:records(root/name/'records.jsonl.gz') for name in ('beam_v1','beam_v2')}
    frozen,case=f.x.p.inputs(f.x.p.BUNDLE);initial=case['initial']
    for folder in (run,calendar,root/'beam_v1',root/'beam_v2'):
        registration=json.loads((folder/'registered_before_run.json').read_text(encoding='utf8'))
        for file,digest in registration['hashes'].items():
            verify_registered_source(file,digest,root)
    pairs=f.compare([r['meta'] for r in rs]);groups=f.aggregate(pairs)
    exp=[];curves=[];requests=[]
    refs={(r['meta']['stage'],r['meta']['envelope'],r['meta']['seed'],r['meta']['scenario']):r for r in rs if r['meta']['policy']=='EFT_REFERENCE'}
    identified=[('run_v1',r) for r in rs]+[(name,r) for name,rr in beam_records.items() for r in rr]
    for study,r in identified:
        m=r['meta'];ss=exposure(r,frozen)
        if abs(sum(s['seconds'] for s in ss)-120)>1e-7:raise ValueError('unmapped state interval')
        if abs(sum(s['incremental_j'] for s in ss)+120*initial['preload_power_w']-m['energy_j'])>1e-7:raise ValueError('incomplete common accounting')
        exp.extend(dict(study=study,stage=m['stage'],envelope=m['envelope'],seed=m['seed'],scenario=m['scenario'],policy=m['policy'],**s) for s in ss)
        if (m['stage'],m['envelope'],m['seed'],m['scenario'])==('new_seed_confirmation','g0.45_c0.5_b4',223001,'mean'):
            b=refs[m['stage'],m['envelope'],m['seed'],m['scenario']]
            for q,z in zip(r['ledger'],b['ledger']):
                if q['id']!=z['id']:raise ValueError('unpaired request')
                requests.append(dict(policy=m['policy'],ordinal=q['ordinal'],task=q['task'],backend=q['backend'],eft_backend=z['backend'],
                    response_delta_ms=(q['response_ns']-z['response_ns'])/1e6,
                    dispatch_delta_ms=(q['dispatch_ns']-z['dispatch_ns'])/1e6))
            for t in range(181):
                curves.append(dict(policy=m['policy'],time_s=t,modeled_j=energy(r,t,frozen,initial) if t<=120 else None,
                    modeled_ap_c=r['predicted_ap_path'][t-35] if t>=35 else None,
                    observed_j=None,observed_ap_c=None,evidence='PC prediction, no new phone observation'))
    f.x.old.csv_write(root/'state_exposure.csv',exp);f.x.old.csv_write(root/'representative_request_deltas.csv',requests)
    f.x.old.csv_write(root/'representative_curves.csv',curves)
    chosen=[r for r in rs if (r['meta']['stage'],r['meta']['envelope'],r['meta']['seed'],r['meta']['scenario'])==
        ('new_seed_confirmation','g0.45_c0.5_b4',223001,'mean')]
    chosen+= [r for r in cs if (r['meta']['envelope'],r['meta']['seed'],r['meta']['mode'])==
        ('g0.45_c0.5_b4',223001,'min_J_under_EFT_peak') and r['status']=='replayed_incumbent']
    names=['EFT','ATC + guard','CPU bottleneck + guard','Offline peak-capped MIP'][:len(chosen)]
    cols=['#64748b','#c2410c','#15803d','#9333ea']
    fig,axes=plt.subplots(4,1,figsize=(11,12),layout='constrained')
    for i,(r,name,col) in enumerate(zip(chosen,names,cols)):
        for q in r['ledger']:
            y=2*i+(q['backend']=='GPU')
            axes[0].broken_barh([(q['dispatch_ns']/1e9,(q['lane_available_ns']-q['dispatch_ns'])/1e9)],(y-.35,.7),facecolors=col)
        axes[1].plot(range(121),[energy(r,t,frozen,initial)-energy(chosen[0],t,frozen,initial) for t in range(121)],color=col,label=name)
        axes[2].plot(range(35,181),r['predicted_ap_path'],color=col,label=name)
        axes[3].plot(range(35,181),[a-b for a,b in zip(r['predicted_ap_path'],chosen[0]['predicted_ap_path'])],color=col,label=name)
    axes[0].set_yticks(range(2*len(chosen)),[f'{n} {b}' for n in names for b in ('CPU','GPU')]);axes[0].set_xlim(35,65)
    axes[0].set_title('48-request queue / seed223001 / mean service: PC schedules, NOT device measurements')
    axes[1].set(xlabel='Common time (s)',ylabel='Modeled cumulative J difference vs EFT',xlim=(0,120));axes[1].legend(fontsize=8)
    axes[2].set(xlabel='Common time (s)',ylabel='Modeled AP (C)',xlim=(35,180))
    axes[3].set(xlabel='Common time (s)',ylabel='Modeled AP difference vs EFT (C)',xlim=(35,180))
    for ax in axes:ax.grid(alpha=.2)
    fig.savefig(root/'comparison.png',dpi=140);fig.savefig(root/'comparison.svg');plt.close(fig)
    svg=root/'comparison.svg';svg.write_bytes(('\n'.join(line.rstrip() for line in svg.read_text(encoding='utf8').splitlines())+'\n').encode())
    beam_groups=[]
    for name,rr in beam_records.items():
        for row in aggregate_candidates(f.compare([r['meta'] for r in rr])):
            beam_groups.append(dict(study=name,**row))
    f.x.old.csv_write(root/'beam_groups.csv',beam_groups)
    table=[]
    for r in groups:
        if r['stage']!='new_seed_confirmation':continue
        vals=[r['envelope'],r['policy'],f"{r['deadline_met']}/{r['planned']}",f"{r['joint_nonworsening_cases']}/{r['cases']}"]
        vals += [f"{r[k]:+.6f}" if r[k] is not None else 'unknown' for k in
            ('mean_delta_energy_j','mean_delta_peak_ap_c','mean_delta_thermal_degree_seconds','mean_delta_urgent_p95_ms','mean_delta_normal_mean_ms')]
        table.append('<tr>'+''.join('<td>'+html.escape(str(v))+'</td>' for v in vals)+'</tr>')
    off=[]
    for r in cs:
        m=r['meta'];vals=[m['envelope'],m['seed'],m['mode'],m['status'],m['solver_gap'],m['delta_energy_j'],m['delta_peak_ap_c'],m['joint_nonworsening_in_replay']]
        off.append('<tr>'+''.join('<td>'+html.escape(str(v) if v is not None else 'unknown')+'</td>' for v in vals)+'</tr>')
    beam_table=[]
    for r in beam_groups:
        if r['stage']!='new_seed_confirmation':continue
        vals=[r['study'],r['envelope'],r['policy'],f"{r['deadline_met']}/{r['planned']}",f"{r['joint_nonworsening_cases']}/{r['cases']}"]
        vals += [f"{r[k]:+.6f}" if r[k] is not None else 'unknown' for k in
            ('mean_delta_energy_j','mean_delta_peak_ap_c','mean_delta_thermal_degree_seconds','mean_delta_urgent_p95_ms','mean_delta_normal_mean_ms')]
        beam_table.append('<tr>'+''.join('<td>'+html.escape(str(v))+'</td>' for v in vals)+'</tr>')
    page='''<!doctype html><html lang="ko"><meta charset="utf-8"><title>전체 요청 방법론 비교</title>
<style>body{font:16px/1.6 system-ui;max-width:1250px;margin:30px auto;padding:0 20px;color:#182a3a}table{border-collapse:collapse;font-size:12px}td,th{border:1px solid #ccd3dd;padding:7px}img{width:100%}.note{padding:16px;background:#fff3d5}</style>
<h1>전체 요청의 서비스·에너지·AP 상충</h1><p>새 PC 계산 264건과 offline 일정 재생 8건입니다. 각 단계의 저장 EFT 24건을 재사용했습니다. 모든 입력은 48요청이며 동결 계수는 변경하지 않았습니다. 새 seed 확인은 소프트웨어 평가이며 독립 실기기 검증이 아닙니다.</p>
<div class="note">방법론 이름 대신 전체 도착 분모·응답·같은 120초 J·35–180초 AP를 비교합니다. 공동 비악화는 전체 기한 충족과 EFT 대비 J·최고 AP·AP 부담 면적의 비악화입니다. P95 비악화나 정확도 PASS를 뜻하지 않습니다. controller 비용 0 가정, 상태 지원 제한, experiment_ready=false를 유지합니다.</div>
<h2>ATC·CPU 병목: 새 seed 223001/223002 × 처리시간 3문맥</h2><table><tr><th>입력</th><th>방법</th><th>기한</th><th>공동 비악화</th><th>ΔJ</th><th>Δ최고AP</th><th>ΔAP면적</th><th>Δ긴급P95 ms</th><th>Δ일반평균 ms</th></tr>'''+''.join(table)+'''</table>
<h2>현재 큐 다단계 탐색: 각 단계의 같은 seed EFT와 대조</h2><p>v1은 현재 큐의 유예가 미래 요청의 여유를 소모해 기한 위반을 만들었습니다. v2는 사후 개발로 첫 행동을 즉시 배정으로 제한했습니다. v1의 새 seed는 323001/323002, v2는 423001/423002이며 서로를 같은 요청의 직접 대조로 해석하지 않습니다. 두 단계 모두 공동 비악화 사례 0건으로 기본 정책에 채택하지 않습니다.</p>
<table><tr><th>단계</th><th>입력</th><th>방법</th><th>기한</th><th>공동 비악화</th><th>ΔJ</th><th>Δ최고AP</th><th>ΔAP면적</th><th>Δ긴급P95 ms</th><th>Δ일반평균 ms</th></tr>'''+''.join(beam_table)+'''</table>
<h2>미래 입력을 아는 offline 참고 일정</h2><p>20ms 격자의 혼합정수계획에서 보수적 점유를 계획하고 원래 5단계 이벤트 엔진으로 재생했습니다. gap은 격자 문제의 추가 전력 목적 gap입니다. 연속시간 최적성·실기기 효과를 증명하지 않으며 timeout incumbent를 최적해로 부르지 않습니다. J·최고 AP 동시 감소 사례도 AP 면적과 응답 비용을 별도 보고합니다.</p>
<table><tr><th>입력</th><th>seed</th><th>목적/제약</th><th>상태</th><th>격자solver gap</th><th>재생 ΔJ</th><th>재생 Δ최고AP</th><th>공동 비악화</th></tr>'''+''.join(off)+'''</table>
<h2>상충을 만드는 동결식의 항</h2><p>평균 처리시간에서 분류 CPU 1건을 탐지 CPU와 완전히 겹치는 분류 GPU로 바꾸면 ΔJ=−0.043247J이지만 AP 가열 입력 적분은 +0.031437°C입니다. 이는 물리적 열량이 아닙니다. 같은 초기조건·g=0에서 무한 시간의 부호 있는 AP 차이 적분은 +0.736232°C·s입니다. 이를 유한창 최고 AP나 양의 부담 면적의 불가능 증명으로 바꾸지 않습니다.</p>
<h2>대표 PC 일정과 모형 경로</h2><img src="comparison.png" alt="PC schedules and modeled energy-temperature tradeoffs"><p>queue 50%, seed223001, mean의 모형 그림이며 새 실측 그림이 아닙니다. 다른 seed 결과는 각자의 EFT와 대조합니다.</p>
<p><a href="README.md">계약·한계·재현</a> · <a href="run_v1/groups.csv">ATC/병목</a> · <a href="beam_groups.csv">큐 탐색</a> · <a href="energy_heat_bounds.csv">동결식 상충 경계</a> · <a href="state_exposure.csv">상태 점유 분해</a> · <a href="calendar_v1/results.csv">offline 참고 결과</a></p></html>'''
    (root/'index.html').write_text(page,encoding='utf8')
    f.x.p.write(root/'report_verification.json',dict(records=len(rs)+sum(map(len,beam_records.values())),common_energy_integrals=True,
        same_initial_frozen_hashes=True,offline_records=len(cs),device_commands=0,experiment_ready=False,
        historical_observer_source='exact archived bytes; current differs only by candidate namespace',
        historical_search_source='exact archived bytes; current differs only by >= timeout equality guard',
        current_observer_sha256=f.x.p.digest(Path(f.x.p.__file__)),
        report_source_sha256=f.x.p.digest(Path(__file__))))


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--root',default=str(f.ROOT));args=ap.parse_args();build(args.root)
