"""Offline reporting from saved artifacts only; no simulation or learning."""
import collections
import csv
import datetime as dt
import gzip
import hashlib
import html
import json
import os
from pathlib import Path
import statistics as st
import sys

BASE = Path(__file__).resolve().parent
ROOT = BASE/'bundle/D1Check-desktop-cpu-20261011'
TASK = ROOT/'output/desktop_joint_amount_amount512_desktop_20261011_a'
OUT = BASE.parent/'outputs'
sys.path.insert(0,str(ROOT))
from tools import d1_joint_amount_cli as cli
import numpy as np
os.environ['MPLCONFIGDIR']=str(BASE/'mplconfig')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
plt.rcParams.update({'font.family':'Malgun Gothic','axes.unicode_minus':False,'font.size':10,'svg.fonttype':'none'})

def read(p):
    return json.loads(p.read_text(encoding='utf-8'))

def write(p,q):
    p.write_text(json.dumps(q,ensure_ascii=False,indent=2),encoding='utf-8')

def csvwrite(p,rows):
    keys = list(dict.fromkeys(k for q in rows for k in q))
    with p.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(rows)

def mean(values):
    return st.fmean(values) if values else None

def percentile(values,q):
    return float(np.percentile(values,q)) if values else None

def svg_plot(name,fig):
    fig.savefig(OUT/(name+'.png'),dpi=150,bbox_inches='tight')
    fig.savefig(OUT/(name+'.svg'),bbox_inches='tight')
    svg=OUT/(name+'.svg')
    svg.write_text('\n'.join(line.rstrip() for line in svg.read_text(encoding='utf-8').splitlines())+'\n',encoding='utf-8')
    plt.close(fig)
    return '<svg'+(OUT/(name+'.svg')).read_text(encoding='utf-8').split('<svg',1)[1]

def main():
    OUT.mkdir(exist_ok=True)
    done=read(TASK/'completion.json');reg=read(TASK/'registration.json');audit=read(BASE/'final_verification.json')
    rows=done['rows'];confirmed=[q for q in rows if q['scope']=='confirmation']
    order=['Band','Triton','JointList','CostList','PPO11_512','PPO23_512','PPO37_512']
    summaries=[];detailed=[];curves=collections.defaultdict(list)
    for role in order:
        group=[q for q in confirmed if q['policy']==role]
        callbacks=[];native=[];snapshots=0;projections=0;decisions=0
        for q in group:
            tag=role if role in order[:4] else role[3:].split('_')[0]
            raw=json.loads(gzip.decompress((TASK/'items'/f'confirmation_{tag}_{q["condition"]:02d}.json.gz').read_bytes()))
            c=raw['callback_seconds'];callbacks+=c;native.append(q['native_seconds']);snapshots+=len(raw['snapshots']);projections+=raw['projection_calls']
            decisions+=len(raw['result'].get('decisions',[]))
            curves[role].append(raw['curve'])
            detailed.append(dict(q,callback_count=len(c),callback_mean_ms=mean(c)*1000 if c else None,callback_p95_ms=percentile(c,95)*1000 if c else None,callback_sum_seconds=sum(c),projection_calls=raw['projection_calls'],projection_seconds=raw['projection_seconds'],snapshots=len(raw['snapshots']),informative_snapshots=sum(sum(s['mask'])>1 for s in raw['snapshots'])))
        summaries.append(dict(policy=role,conditions=len(group),planned=sum(q['planned'] for q in group),completed=sum(q['completed'] for q in group),incomplete=sum(q['incomplete'] for q in group),urgent_planned=sum(q['urgent_planned'] for q in group),normal_planned=sum(q['normal_planned'] for q in group),urgent_failure=sum(q['urgent_failure'] for q in group),normal_failure=sum(q['normal_failure'] for q in group),mean_condition_urgent_p95_ms=mean([q['urgent_p95_ms'] for q in group]),worst_condition_urgent_p95_ms=max(q['urgent_p95_ms'] for q in group),mean_condition_normal_response_ms=mean([q['normal_mean_ms'] for q in group]),mean_condition_j120=mean([q['energy_j'] for q in group]),mean_condition_peak_ap_c=mean([q['peak_ap_c'] for q in group]),worst_condition_peak_ap_c=max(q['peak_ap_c'] for q in group),callback_count=len(callbacks),callback_mean_ms=mean(callbacks)*1000 if callbacks else None,callback_p95_ms=percentile(callbacks,95)*1000 if callbacks else None,callback_sum_seconds=sum(callbacks),pc_native_seconds=sum(native),projection_calls=projections,snapshots=snapshots))
    csvwrite(OUT/'confirmation48.csv',detailed)
    csvwrite(OUT/'all_evaluations.csv',rows)
    csvwrite(OUT/'summary.csv',summaries)
    deltas=[]
    by={(q['condition'],q['policy']):q for q in confirmed}
    for role in order[2:]:
        for baseline in order[:4]:
            if role==baseline:continue
            for i in range(48):
                a,b=by[i,role],by[i,baseline]
                q=dict(condition=i,arrival_seed=a['arrival_seed'],family=a['family'],context=a['context'],policy=role,baseline=baseline)
                for k in ('incomplete','urgent_failure','normal_failure','urgent_p95_ms','energy_j','peak_ap_c'):
                    q['delta_'+k]=a[k]-b[k]
                deltas.append(q)
    csvwrite(OUT/'paired_condition_deltas.csv',deltas)
    old=list(csv.DictReader((BASE/'repo/docs/results/service_joint_rl_20261011/comparison.csv').open(encoding='utf-8-sig')))
    old64={ (int(q['learning_seed']),int(q['condition'])):q for q in old if q['episodes']=='64' and q['scope']!='confirmation'}
    paired=[]
    for q in rows:
        if q['scope']!='development':continue
        p=old64[q['learning_seed'],q['condition']]
        assert (int(p['arrival_seed']),p['family'],p['context'],int(p['planned']))==(q['arrival_seed'],q['family'],q['context'],q['planned'])
        d=dict(seed=q['learning_seed'],condition=q['condition'],arrival_seed=q['arrival_seed'],family=q['family'],context=q['context'],scope='already_seen_development_same24')
        for k in ('planned','completed','incomplete','urgent_failure','normal_failure','urgent_p95_ms','energy_j','peak_ap_c'):
            d[k+'_64']=float(p[k]);d[k+'_512']=q[k];d['delta_'+k]=q[k]-float(p[k])
        paired.append(d)
    assert len(paired)==72
    csvwrite(OUT/'development64_to512.csv',paired)
    states=[];updates=[]
    for seed in (11,23,37):
        p=cli.x.r.torch.load(TASK/'checkpoints'/f'seed{seed}_ep512.pt',map_location='cpu',weights_only=False)
        states.append(dict(seed=seed,episodes=p['accepted_episodes'],updates=p['update_count'],optimizer_steps=p['optimizer_steps'],multipliers=p['multipliers'].tolist(),sha256=cli.x.sha(TASK/'checkpoints'/f'seed{seed}_ep512.pt')))
        for q in p['logs']:
            updates.append(dict(seed=seed,episodes=q['accepted_episodes'],update=q['update'],optimizer_steps=q['optimizer_steps_cumulative'],informative_actions=q['sampled_choices'],actor_gradient_max=max(s['gradients']['actor'] for s in q['steps']),lambda_J=q['lambda_after'][0],lambda_incomplete=q['lambda_after'][1],lambda_urgent=q['lambda_after'][2],lambda_normal=q['lambda_after'][3],lambda_P95=q['lambda_after'][4],batch_mean_J_minus_JointList=q['dual_valid_means'][0],batch_mean_absolute_normal_failure=q['dual_valid_means'][3],update_seconds=q['seconds'],early_stop=q['early_stop'],scope='original64' if q['accepted_episodes']<=64 else 'desktop_extension'))
    csvwrite(OUT/'learning_updates.csv',updates)
    stages=[json.loads(s) for s in (BASE/'logs/stages.jsonl').read_text(encoding='utf-8').splitlines()]
    runs=[s for s in stages if s['stage'].startswith('run_')]
    timings=dict(run_wall_seconds=sum(s['wall_seconds'] for s in runs),run_cpu_seconds=sum(s['cpu']['cpu_seconds'] for s in runs),run_active_seconds=audit['clock']['consumed_active_seconds'],active_cap_seconds=14400,save_reserve_seconds=600,verification_unit_smoke_prepare_seconds=sum(s['wall_seconds'] for s in stages if not s['stage'].startswith('run_')),stages=stages,verification_first_stage_cpu_scope='venv redirector only; excluded from CPU total',download_install_and_preflight_wall_seconds=(dt.datetime.fromisoformat(stages[0]['started_utc']).timestamp()-(BASE/'DESKTOP_AUTO_RUN_PROMPT_20261011.md').stat().st_mtime),download_install_time_precision='combined wall interval from downloaded prompt file mtime to first verification start; includes document review, downloads, initial incompatible-package probe and installation; not separate precise installer CPU measurements')
    timings['elapsed_from_first_run_start_seconds']=(dt.datetime.fromisoformat(runs[-1]['finished_utc'])-dt.datetime.fromisoformat(runs[0]['started_utc'])).total_seconds()
    timings['paused_wall_seconds']=timings['elapsed_from_first_run_start_seconds']-timings['run_wall_seconds']
    timings['verification_unit_smoke_prepare_seconds']=sum(s['wall_seconds'] for s in stages if s['stage'] in ('verify','unit','smoke','prepare'))
    timings['post_run_verification_seconds']=sum(s['wall_seconds'] for s in stages if s['stage'].startswith('final_'))
    gates=done['gates'];summary=dict(task=reg['task'],summary=summaries,states=states,consumption=done['consumption'],smoke_native=3,smoke_learning=0,timings=timings,gates=gates,global_project_lineage_base_native=14735,global_project_lineage_base_learning=3181,global_project_lineage_with_this_desktop_native=14735+2200+3,global_project_lineage_with_this_desktop_learning=3181+1344,automatic_adoption=False,experiment_ready=False,strict_changed=False,device_commands=0)
    write(OUT/'result.json',summary);write(OUT/'execution_contract.json',reg);write(OUT/'final_verification.json',audit)
    write(OUT/'bundle_verification.json',read(BASE/'bundle_verification.json'));write(OUT/'registry_verification.json',read(BASE/'registry_verification.json'));write(OUT/'timings.json',timings)
    write(OUT/'environment.json',read(BASE/'environment.json'))
    write(OUT/'host_errors.json',read(BASE/'host_errors.json'))
    write(OUT/'pause_verification.json',read(BASE/'pause_verification.json'))
    chart_html=[]
    fig,axes=plt.subplots(2,2,figsize=(13,8),constrained_layout=True)
    for index,(ax,key,title) in enumerate(zip(axes.flat,['normal_failure','mean_condition_urgent_p95_ms','mean_condition_j120','mean_condition_peak_ap_c'],['일반 기한 실패 합계 (건)','조건별 긴급 P95 평균 (ms)','120초 모형 J 평균의 Band 대비 차이 (J)','최고 AP 조건 평균의 Band 대비 차이 (°C)'])):
        vals=[q[key] for q in summaries]
        if index>=2:
            vals=[v-summaries[0][key] for v in vals]
        ax.bar(order,vals,color=['#607d8b']*4+['#2466a7','#a25136','#3d8053']);ax.set_title(title);ax.tick_params(axis='x',rotation=35);ax.grid(axis='y',alpha=.2)
        if index>=2:
            ax.axhline(0,color='black',linewidth=.8)
            for xpos,value in enumerate(vals):
                ax.annotate(f'{value:+.6f}',(xpos,value),xytext=(0,4 if value>=0 else -12),textcoords='offset points',ha='center',fontsize=8)
            ax.margins(y=.22)
    fig.suptitle('새 48조건 · 7정책 동일 입력 비교 / 실기기 측정 아님',fontsize=15)
    chart_html.append(svg_plot('confirmation_kpi',fig))
    fig,axes=plt.subplots(2,1,figsize=(12,7),constrained_layout=True)
    for seed in (11,23,37):
        group=[q for q in updates if q['seed']==seed]
        axes[0].plot([q['episodes'] for q in group],[q['batch_mean_J_minus_JointList'] for q in group],label=f'초기화 seed {seed}')
        axes[1].plot([q['episodes'] for q in group],[q['batch_mean_absolute_normal_failure'] for q in group],label=f'초기화 seed {seed}')
    for ax in axes:
        ax.axvline(64,color='black',linestyle='--',alpha=.5);ax.legend();ax.grid(alpha=.2);ax.set_xlabel('누적 학습 에피소드 / 세 모델의 sampling RNG는 공유')
    axes[0].set_ylabel('8에피소드 batch의 J-JointList (J)');axes[1].set_ylabel('8에피소드 batch의 일반 실패 (건)')
    fig.suptitle('실제 PPO 학습 로그 / 학습 비용의 변화가 최종 우위를 뜻하지 않음',fontsize=14)
    chart_html.append(svg_plot('learning_trace',fig))
    fig,ax=plt.subplots(figsize=(12,5),constrained_layout=True)
    curve_rows=[]
    for role in order:
        lengths={len(c) for c in curves[role]};assert len(lengths)==1
        times=[c[0] for c in curves[role][0]]
        assert times[0]==35 and times[-1]==180
        vals=np.asarray([[q[1] for q in curve] for curve in curves[role]])
        ax.plot(times,vals.mean(0),label=role,alpha=.8)
        for t,avg in zip(times,vals.mean(0)):curve_rows.append(dict(policy=role,time_seconds=t,mean_model_ap_c=float(avg)))
    csvwrite(OUT/'ap35_180.csv',curve_rows)
    ax.set(title='48조건 평균 모형 AP 경로 / 겹치는 곡선은 동일값에 가까움',xlabel='시간 (초)',ylabel='모형 AP (°C)');ax.legend(ncols=4);ax.grid(alpha=.2)
    chart_html.append(svg_plot('model_ap_path',fig))
    header='|정책|완료/예정|긴급 실패|일반 실패|긴급 P95 평균 ms|J120 평균 J|최고 AP 평균 °C|\n|---|---:|---:|---:|---:|---:|---:|\n'
    table=header+'\n'.join(f'|{q["policy"]}|{q["completed"]}/{q["planned"]}|{q["urgent_failure"]}|{q["normal_failure"]}|{q["mean_condition_urgent_p95_ms"]:.3f}|{q["mean_condition_j120"]:.6f}|{q["mean_condition_peak_ap_c"]:.6f}|' for q in summaries)
    dev=[]
    for seed in (11,23,37):
        group=[q for q in paired if q['seed']==seed]
        dev.append(f'- seed {seed}: 일반 실패 {sum(q["normal_failure_64"] for q in group):.0f}→{sum(q["normal_failure_512"] for q in group):.0f}, 긴급 P95 조건평균 변화 {mean([q["delta_urgent_p95_ms"] for q in group]):+.6f}ms, J {mean([q["delta_energy_j"] for q in group]):+.6f}J, AP {mean([q["delta_peak_ap_c"] for q in group]):+.6f}°C.')
    gate_lines='\n'.join(f'- {role}: maintenance_pass={q["maintenance_pass"]}, promising={q["promising"]}, promising_families={q["promising_families"]}.' for role,q in gates.items())
    conclusion='세 PPO 모두 원 strict 최종 기준 미달이며 자동 채택은 0이다.' if not any(q['promising'] for q in gates.values()) else '일부 모형 기준 후보가 있으나 자동 채택은 0이며 실기기 우위는 미입증이다.'
    report=f'''# D1Check 데스크톱 64→512 학습량 연장 결과

{conclusion} 승인된 학습·평가 실행은 완료했다. 추가 학습 1,344회와 환경 2,200회 전량 완료, native 오류 0회다. 별도 기능 smoke는 3환경·72요청·학습0이다.

## 실행과 보존

- task `{reg['task']}`. 원 64 상태의 세 actor/critic/Adam/승수 및 공유 round-robin sampling RNG를 보존해 각 448회 추가했다. 세 독립 sampling stream이 아니다.
- 세 모델 각각 512에피소드·64update·실제 Adam step은 [상태 영수증](final_verification.json)에 기록했다. 원 dependency/settings/schema와 96개 ZIP 파일, 2,200 item SHA, 요청 원장, 선택 mask를 검산했다. 공유 session은 마지막 학습 경계1792환경/1344학습을 담고 최종 원장은 평가를 포함해2200환경이다.
- 실제 `REQUEST_STOP` 중지·재개 1회: 환경 경계에서 세 모델/partial batch/공유 RNG/cursor/소비를 저장, clock 정상 닫힘을 확인 후 같은 task로 재개했다. 강제 종료·예산/clock 초기화·학습 cached replay 0회.
- 상한 환경2300/학습1344/활성240분·저장10분. 실행 프로세스 wall 합계 {timings['run_wall_seconds']/60:.3f}분, 중지휴식을 포함한 최초run→완료 wall {timings['elapsed_from_first_run_start_seconds']/60:.3f}분, 누적 active {timings['run_active_seconds']/60:.3f}분, Windows process-tree CPU {timings['run_cpu_seconds']/60:.3f}분. 중지휴식 {timings['paused_wall_seconds']:.3f}초는 active에서 제외된다.
- 다운로드·설치·문서 점검 합산 wall {timings['download_install_and_preflight_wall_seconds']:.3f}초, verify/unit/smoke/prepare 명령 wall {timings['verification_unit_smoke_prepare_seconds']:.3f}초. 전자는 다운로드 프롬프트 mtime부터 첫검증까지의 합산 구간이며 설치 개별 CPU시간은 측정하지 않았다. 상세 [시간 원장](timings.json).
- parent 종료 소비500/192 유지. 이 V1 계보는2700환경/1536학습이다. STATUS의 전체 관련계보 기저14735/3181에 이번2200＋smoke3/1344만 더해16938/4525로 기록한다. 모든 과거 PPO를 합산한 프로젝트 총계는 아니다.
- Windows11 64bit/Ryzen5 5600/약16GB RAM/Python3.11.9/NumPy2.4.6/Torch2.11.0+cpu/Matplotlib3.10.9. 기존 호스트 NumPy2.1.3/Torch2.7.1+cu118는 유지하고 별도 venv를 썼다. 패키지 import 기본 스레드는6이지만 동결 learner는1스레드와 결정적 PyTorch 연산을 설정한다. OS/CPU 간 학습 비트 동일성을 주장하지 않는다. 다운로드 파일/venv/패키지 설치의 별도 시각 경계와 설치 구간은 [환경 영수증](environment.json)에 기록했다. 파일 시각은 네트워크/설치 전체 stopwatch와 구분한다.

## 같은 새 48조건의 원단위 결과

4 arrival seed×4부하×3모형문맥의 48조건이며 48독립 실측이 아니다. 7정책이 동일한 ticket/profile/initial/settings를 사용한다. 긴급 P95 표의 값은 48개 조건별 P95의 산술평균이며 모든 요청을 합친 pooled P95가 아니다. AP는35~180초 모형 내부 채널이고 J는120초 동결 모형 비용이다.

{table}

원 zero-epsilon gate를 그대로 재계산했다. gate 비교군은 Band/Triton/CostList이고 JointList도 원단위 대응 CSV에 함께 비교했다.

{gate_lines}

PC 판단시간은 callback 기록의 평균/P95/합계로 [요약 CSV](summary.csv)와 [48조건 CSV](confirmation48.csv)에 기록했다. 이 시간은 폰 온라인 제어비용이 아니다. 모든 조건의 완료·실패·응답·J·AP 차이는 [대응 차이](paired_condition_deltas.csv)를 따른다.

## 64와512의 학습량 비교 범위

원64의 공개 저장 결과와 이번512의 **이미 본 개발24**를 같은 arrival/family/context/planned로 대응시켰다. 새 독립 확인으로 부르지 않는다.

{chr(10).join(dev)}

신규 확인48에는 계획된512 세 PPO와 네 비교군만 실행했다. 다른 seed의 과거64 확인자료와 새512 자료를 직접 대응 효과로 합치지 않는다. 새48의64 actor 추가평가는 실행하지 않았으므로 학습량의 독립 인과효과·수렴을 확정할 수 없다. [개발 대응72행](development64_to512.csv)과 [실제 학습로그](learning_updates.csv)를 함께 보존한다.

## 한계와 다음 행동

학습량 증가만으로 개선을 보장하지 않는다. V1의 허용된 예측 비용 개선후보0이라는 기존 제약을 보존했으며 정책/보상/mask/기한/지원/optimizer/판정 기준 변경0이다. 기존 기본·strict·experiment_ready=false를 유지한다. 휴대폰/ADB/추가실측/NPU/새모형/하이퍼파라미터 탐색0이다. 냉각에 따른 속도 회복·표면 최고온도·폰 제어비용·실기기 절감은 이번 모형으로 새로 입증하지 않았다.

다음 행동은 이번 대응 결과를 검토하고, 제약과 최종KPI의 정렬이 필요하면 별도 설계·새승인·새독립자료로 검토하는 것이다. 이 task는 완료되었으며 남은 상한으로 자동 재실행하거나 확대하지 않는다.

## 보존 파일과 검증

[오프라인 화면](index.html) · [계약](execution_contract.json) · [전체 평가CSV](all_evaluations.csv) · [SHA/원장 검산](final_verification.json) · [ZIP검산](bundle_verification.json) · [seed이력 검산](registry_verification.json). 원 raw/item/PT/원장/동결 source는 로컬 archive에 보존하고 Git에는 작은 코드·설정·보고서만 반영한다. Git 반영·원격HEAD 결과는 별도 영수증으로 남긴다.

기능 검증 명령은 `python -B -X utf8 -m tools.d1_joint_amount_cli`, 지정13 unittest, 지정 `run-smoke`이며 모두 PASS다. 실행기준HEAD는8175aac95c82fa70860e07e2e7566797b92b7736, ZIP SHA는4d7e0fcf65591a2ec015604fb69ea8f10358c72e28f1703a18989f6f8546241c다.

사소한 호스트 오류: registry receipt 검사 첫 시도에서 공개 저장소에 없는 로컬 cases.json을 읽어 FileNotFoundError가 났다. 공개115파일/가용 receipt와 원export313seed/3구간을 구분해 검사했고 source/registry 수정 없이 충돌0을 확인했다. Git CLI dry-run은 인증부재로 실패하여 연결된 GitHub 앱의 commit/ref 경로를 사용했다. 첫 verify CPU시간은 venv redirector만 측정되어 총CPU에서 제외하고, 이후 stage는 Windows job의 자손까지 측정했다. 모든 오류는 환경/학습 소비0이며 원 로그를 보존한다.
'''
    (OUT/'README.md').write_text(report,encoding='utf-8')
    htmlrows=''.join('<tr>'+''.join(f'<td>{html.escape(str(v))}</td>' for v in [q['policy'],f"{q['completed']}/{q['planned']}",q['urgent_failure'],q['normal_failure'],f"{q['mean_condition_urgent_p95_ms']:.3f}",f"{q['mean_condition_j120']:.6f}",f"{q['mean_condition_peak_ap_c']:.6f}"])+'</tr>' for q in summaries)
    page=f'''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>D1Check 데스크톱 학습 결과</title><style>body{{font:16px 'Malgun Gothic',sans-serif;max-width:1200px;margin:40px auto;padding:0 24px;background:#f5f7fa;color:#192a3a}}header,section{{background:white;padding:24px;margin:20px 0;border-radius:12px}}h1{{font-size:30px}}table{{border-collapse:collapse;width:100%;font-size:14px}}td,th{{border-bottom:1px solid #ddd;padding:9px;text-align:right}}td:first-child,th:first-child{{text-align:left}}svg{{width:100%;height:auto}}.badge{{background:#e7eef4;padding:10px;border-radius:6px}}a{{color:#2466a7}}.note{{color:#516070}}</style><header><h1>64→512 실제 학습·평가 완료</h1><p class="badge">{conclusion}</p><p>3모델 각448추가 · 총1344학습 · 2200환경 · 오류0 · 별도smoke3 · 휴대폰/ADB/실측0</p><p>active {timings['run_active_seconds']/60:.2f}분 / 상한240분 · 저장예약10분 · 전체원장·공유RNG·Adam 보존</p></header><section><h2>새48조건 동일 입력 비교</h2><table><thead><tr><th>정책</th><th>완료/예정</th><th>긴급실패</th><th>일반실패</th><th>긴급P95 평균 ms</th><th>J120 평균 J</th><th>최고AP 평균 °C</th></tr></thead><tbody>{htmlrows}</tbody></table><p class="note">4arrival×4부하×3문맥. 독립실측 아님. P95는 조건별P95 평균, AP는 모형 채널이며 표면온도 아님.</p></section>'''+''.join('<section>'+s+'</section>' for s in chart_html)+f'''<section><h2>같은 개발24의64→512 대응</h2><p>이미 본 개발자료이며 새 독립확인이 아니다.</p><ul>{''.join('<li>'+html.escape(s[2:])+'</li>' for s in dev)}</ul><p>학습량의 인과효과·수렴·실기기 절감은 미확정. 기존 기본·strict·experiment_ready=false 유지.</p><a href="README.md">한국어 상세보고서</a> · <a href="confirmation48.csv">전체48조건CSV</a> · <a href="learning_updates.csv">실제학습로그</a> · <a href="final_verification.json">SHA·상태·원장검증</a></section></html>'''
    page=page.replace('</style>','h1{font-size:clamp(22px,3vw,30px);text-wrap:balance}.table-scroll{overflow-x:auto}table{min-width:740px}</style>')
    page=page.replace('<h2>새48조건 동일 입력 비교</h2><table>','<h2>새48조건 동일 입력 비교</h2><div class="table-scroll"><table>')
    page=page.replace('</tbody></table><p class="note">','</tbody></table></div><p class="note">')
    (OUT/'index.html').write_text('\n'.join(line.rstrip() for line in page.splitlines())+'\n',encoding='utf-8')
    print(json.dumps(dict(output_files=len(list(OUT.iterdir())),summary=summaries,states=states,timings={k:v for k,v in timings.items() if k!='stages'},gates={k:{n:v[n] for n in ('maintenance_pass','promising','promising_families')} for k,v in gates.items()}),ensure_ascii=False,indent=2))

if __name__=='__main__':
    main()
