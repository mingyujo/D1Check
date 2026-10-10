"""Saved-result visualization/verification; no fitting or device execution."""
import argparse
import csv
import html
import json
import math
from pathlib import Path
import numpy as np
from tools import d1_recovery_service as s


def table(path):
    with Path(path).open(encoding='utf8', newline='') as f:
        return list(csv.DictReader(f))


def verify(output):
    out = Path(output); data = s.read(out/'inputs.json'); candidate = s.read(out/'candidate.json')
    if s.sha(out/'candidate.json') != s.read(out/'development_freeze.json')['candidate_sha256']:
        raise ValueError('candidate changed after development freeze')
    expected = s.evaluate(data, candidate, s.read(s.MODEL)); actual = table(out/'prediction_errors.csv')
    if len(expected) != len(actual):
        raise ValueError('score denominator')
    error = 0.
    for a, b in zip(expected, actual):
        for k in ('session', 'cell', 'model', 'metric'):
            if a[k] != b[k]:
                raise ValueError('score identity')
        for k in ('observed_mean_ms', 'predicted_ms', 'signed_ms', 'mae_ms'):
            if a[k] is None:
                if b[k] != '':
                    raise ValueError('missing prediction filled')
            else:
                error = max(error, abs(a[k]-float(b[k])))
    if error > 1e-12:
        raise ValueError('serialized metrics differ')
    phase_error = max(abs(sum(r[k] for k in s.PHASES)-r['lane_total']) for r in data['requests'])
    if phase_error > 1e-8:
        raise ValueError('phase partition mismatch')
    for r in data['requests']:
        if r['ap_before_c'] is not None and r['ap_query_end_s'] > r['dispatch_s']:
            raise ValueError('future AP in request association')
    # The actual predictor is invariant to all future observations and timings.
    perturbed = json.loads(json.dumps(data)); future = [r for r in perturbed['requests'] if r['role']=='confirmation']
    for r in future:
        r['ap_before_c'] = 99.; r['execution_to_output'] = 99999.; r['invocation_overlap'] = .999
    if s.fit_candidate(s.summarize(data)) != s.fit_candidate(s.summarize(perturbed)):
        raise ValueError('confirmation contaminated fit')
    original_hash = s.read(s.BUNDLE/'registration.json')['frozen_model_sha256']
    if s.sha(s.MODEL) != original_hash:
        raise ValueError('original frozen model modified')
    mask = {(r['session'], r['cell']): r['extrapolation']=='True' for r in actual
            if r['role']=='confirmation' and r['model']=='pre_AP_candidate' and r['metric']=='lane_total'}
    scope_rows = []
    for scope in ('all', 'within_dev_AP', 'outside_dev_AP'):
        for metric in ('execution_to_output', 'lane_total'):
            for model in ('original_frozen', 'history_fixed_control', 'pre_AP_candidate'):
                use = [r for r in actual if r['role']=='confirmation' and r['metric']==metric and r['model']==model
                       and (scope=='all' or mask[(r['session'], r['cell'])]==(scope=='outside_dev_AP'))]
                scope_rows.append(dict(scope=scope, metric=metric, model=model, session_cells=len(use),
                                       physical_sessions=len({r['session'] for r in use}),
                                       mean_request_mae_ms=sum(float(r['mae_ms']) for r in use)/len(use)))
    s.csv_write(out/'ap_scope_comparison.csv', scope_rows)
    within = sum(h['raw_gain_per_c'] > 0 for h in candidate['heads'].values() if h['raw_gain_per_c'] is not None)
    return dict(score_rows=len(actual), score_max_difference=error, phase_rows=len(data['requests']),
                lane_partition_max_difference_ms=phase_error, future_AP_leakage=False,
                confirmation_fit_leakage=False, positive_dev_cell_gains=within,
                physical_target_sessions=8, statistical_session_independence_certified=False,
                frozen_model_unchanged=True, device_commands=0, new_fits=0)


def render(output):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams['font.family'] = 'Malgun Gothic'
    plt.rcParams['axes.unicode_minus'] = False
    out = Path(output); sums = table(out/'session_phases.csv'); diffs = table(out/'recovery_contrasts.csv')
    scores = table(out/'prediction_errors.csv'); init = table(out/'initial_conditions.csv')
    contexts = [('CPU','classification_CPU'), ('CPU','detection_CPU'), ('PAR','classification_GPU'), ('PAR','detection_CPU')]
    labels = ['CPU 정책 · 분류 CPU', 'CPU 정책 · 탐지 CPU', 'PAR 정책 · 분류 GPU', 'PAR 정책 · 탐지 CPU']
    images = []
    def save(fig, name):
        fig.savefig(out/(name+'.png'), dpi=135); fig.savefig(out/(name+'.svg')); plt.close(fig)
        p = out/(name+'.svg'); p.write_text('\n'.join(x.rstrip() for x in p.read_text(encoding='utf8').splitlines())+'\n', encoding='utf8')
        images.append(name+'.png')
    fig, axes = plt.subplots(2, 2, figsize=(12,8), constrained_layout=True)
    for i, (policy, cell) in enumerate(contexts):
        ax = axes.flat[i]
        for role, marker, color in [('development','o','#a64b36'), ('confirmation','s','#176aa0')]:
            rr = [r for r in sums if r['role']==role and r['policy']==policy and r['cell']==cell and r['stage']=='target']
            rr.sort(key=lambda r:int(r['gap_s']))
            xx = [float(r['pre_target_ap_c']) for r in rr]; yy = [float(r['execution_to_output']) for r in rr]
            ax.plot(xx,yy,marker=marker,color=color,label='개발' if role=='development' else '이미 본 확인')
            for x,y,r in zip(xx,yy,rr):
                ax.annotate(r['gap_s']+'초', (x,y), xytext=(5,5), textcoords='offset points', fontsize=9)
        ax.set_title(labels[i]); ax.set_xlabel('실제 첫 부하 전 AP (°C)'); ax.set_ylabel('phase2 세션 평균 (ms)'); ax.legend(fontsize=9)
    fig.suptitle('회복기간·AP와 처리시간 · 연결선은 동일 block 관측이며 인과 회복 곡선이 아님')
    save(fig,'ap_service')
    fig, axes = plt.subplots(1,2,figsize=(13,4.8),constrained_layout=True)
    for ax,metric in zip(axes,('invocation','lane_total')):
        for j,role in enumerate(('development','confirmation')):
            rr = [next(r for r in diffs if (r['role'],r['policy'],r['cell'],r['metric'])==(role,p,c,metric)) for p,c in contexts]
            ax.bar(np.arange(4)+(.18 if j else -.18),[float(r['relative_percent']) for r in rr],.36,
                   label='개발' if j==0 else '이미 본 확인',color='#a64b36' if j==0 else '#176aa0')
        ax.axhline(0,color='#333',lw=.8); ax.set_xticks(range(4),['CPU/분류','CPU/탐지','PAR/분류GPU','PAR/탐지CPU'],rotation=15)
        ax.set_ylabel('180-30 상대차 (%)'); ax.set_title('실제 추론 반환' if metric=='invocation' else 'dispatch→lane 해제'); ax.legend()
    fig.suptitle('긴 회복 후 처리시간 변화 · 음수는 단축, 양수는 증가 · 세션 쌍은 조건별1개')
    save(fig,'recovery_differences')
    fig,axes = plt.subplots(2,1,figsize=(13,8),constrained_layout=True)
    names=('original_frozen','history_fixed_control','pre_AP_candidate')
    ids = list(dict.fromkeys((r['session'],r['cell']) for r in scores if r['role']=='confirmation'))
    for ax,metric in zip(axes,('execution_to_output','lane_total')):
        for j,(name,color,label) in enumerate(zip(names,('#777','#176aa0','#bd6335'),('기존 동결','같은 개발 고정시간','시작 AP 후보(외삽 포함)'))):
            rr=[next(r for r in scores if (r['session'],r['cell'],r['metric'],r['model'])==(identity,cell,metric,name)) for identity,cell in ids]
            ax.bar(np.arange(len(ids))+(j-1)*.25,[float(r['mae_ms']) for r in rr],.25,label=label,color=color)
        ax.set_xticks(range(len(ids)),[identity.replace('confirmation_','')+'\n'+cell.replace('classification','분류').replace('detection','탐지') for identity,cell in ids],fontsize=8)
        ax.set_ylabel('요청 MAE (ms)'); ax.set_title('phase2' if metric=='execution_to_output' else '5phase 합계 · 큐 응답 오차가 아님'); ax.legend(fontsize=9)
    fig.suptitle('확인4세션·8 cell 전량 · 고정시간 재보정 이득과 AP 입력 효과를 분리')
    save(fig,'prediction_errors')
    fig,axes=plt.subplots(4,1,figsize=(13,10),constrained_layout=True)
    target=[r for r in sums if r['stage']=='target']
    for i,(policy,cell) in enumerate(contexts):
        rr=[r for r in target if (r['policy'],r['cell'])==(policy,cell)]
        rr.sort(key=lambda r:(r['role'],int(r['gap_s']))); bottom=np.zeros(len(rr))
        for phase in s.PHASES:
            values=np.array([float(r[phase]) for r in rr]); axes[i].bar(range(len(rr)),values,bottom=bottom,label=phase); bottom+=values
        axes[i].set_xticks(range(len(rr)),[r['role']+'/'+r['gap_s'] for r in rr]); axes[i].set_ylabel('ms'); axes[i].set_title(labels[i],fontsize=10)
        if i==0:axes[i].legend(fontsize=7,ncol=3)
    fig.suptitle('관측5phase · 전처리와 실제 invocation은 phase2 안에 있음')
    save(fig,'five_phases')
    rows=''.join('<tr>'+''.join('<td>'+html.escape(r[k])+'</td>' for k in ('role','policy','cell','metric','relative_percent','pre_AP_180_minus_30_c'))+'</tr>' for r in diffs if r['metric']=='invocation')
    page='''<!doctype html><html lang="ko"><meta charset="utf-8"><title>회복 이력과 5phase 처리시간</title>
    <style>body{font:16px/1.7 sans-serif;max-width:1250px;margin:25px auto;padding:20px}aside{background:#fff0d4;padding:20px}img{max-width:100%}td,th{border:1px solid #ddd;padding:7px}table{border-collapse:collapse}</style>
    <h1>회복 이력과 처리시간: 기존 자료의 사후 분석</h1>
    <aside><b>냉각→속도 회복 법칙 미확인, AP 후보 미채택.</b> 개발4/이미 본 확인4 부하 세션과 C0 4개를 재사용했다.
    같은 개발자료의 고정시간 대조는 기존 동결보다 확인 오차가 줄었지만, AP 입력은 그 대조보다 악화했다.
    기본/RL/strict/experiment_ready=false 불변이며 새 실측0이다.</aside>
    <p>등록된 회복30/180초에 baseline30초와 첫 요청까지35초가 더해 실제 마지막 준비 부하 이후 약95/245초다.
    개발에서는 긴 회복의 시작 AP가 +0.3°C였고 확인에서는 −0.2~−0.5°C였다. 초기 온도와 실행 순서가 교차하여 회복시간을 냉각량으로 대체하지 않는다.</p>
    <p>시작 AP 후보는 부하 전 표본 하나만 사용하고 target 안에서 처리시간을 갱신하지 않는다. 이것은 동적 회복 모형이나 예정 도착부터의 종단간 검증이 아니다.
    미래 AP와 실제 겹침은 잔차/연관 진단에만 사용한다. 확인 4/8 cell은 개발 초기AP 범위 밖 외삽이고 범위 안4개도 새로운 독립 확인이 아니다.</p>
    <p><a href="../README.md">계약·재현</a> · <a href="../../../RECOVERY_SERVICE_RESULTS_20261010.md">한국어 판독</a> ·
    <a href="initial_conditions.csv">실제 초기조건</a> · <a href="recovery_contrasts.csv">전체 구간 비교</a> ·
    <a href="ordinal_contrasts.csv">요청 순서별 비교</a> · <a href="prediction_errors.csv">모든 오차</a> ·
    <a href="ap_scope_comparison.csv">초기 AP 범위 안/밖 분해</a> · <a href="candidate.json">미채택 후보</a> · <a href="development_freeze.json">개발 동결</a></p>
    <table><tr><th>역할</th><th>정책</th><th>작업/자원</th><th>경계</th><th>180−30 처리시간 %</th><th>초기 AP 차 °C</th></tr>'''+rows+'</table>'
    page+=''.join('<img src="'+name+'" alt="'+name+'">' for name in images)+'</html>'
    (out/'index.html').write_text(page,encoding='utf8')
    return dict(images=images,new_fits=0,device_commands=0)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('--output',required=True)
    parser.add_argument('--verify-only',action='store_true')
    args=parser.parse_args(); checks=verify(args.output)
    pictures = (dict(images=[p.name for p in sorted(Path(args.output).glob('*.png'))],
                     reused_existing_figures=True, new_fits=0, device_commands=0)
                if args.verify_only else render(args.output))
    s.write(Path(args.output)/'readout_verification.json',dict(checks=checks,pictures=pictures,
        source_sha256=s.sha(__file__),ap_recovery_model_solved=False))
    print(json.dumps(dict(checks=checks,pictures=pictures)))
