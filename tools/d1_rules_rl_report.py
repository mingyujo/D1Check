"""Read-only CSV/plots/Korean offline report from the preserved study artifacts."""
from __future__ import annotations
import argparse
import csv
import html
import gzip
import json
import math
from pathlib import Path
import statistics
from datetime import datetime,timezone
import shutil
from tools import d1_rules_rl_common as c
from tools import d1_rl_amount_campaign as a
from tools import d1_rules_rl_evaluation as e

METRICS=('energy_j','peak_ap_c','thermal_degree_seconds','urgent_p95_ms','normal_mean_ms')


def csv_write(path,rows):
    fields=list(dict.fromkeys(k for r in rows for k in r))
    if not fields:fields=['status']
    with Path(path).open('w',encoding='utf8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
        for row in rows:w.writerow({k:json.dumps(value,ensure_ascii=False) if isinstance(value,(list,dict)) else value for k,value in row.items()})


def jsonl(path):
    if not Path(path).exists():return []
    return [json.loads(line) for line in Path(path).read_text(encoding='utf8').splitlines()]


def csv_read(path):
    result=[]
    with Path(path).open(encoding='utf8',newline='') as f:
        for row in csv.DictReader(f):
            value={}
            for key,item in row.items():
                if item=='':value[key]=None
                elif item in ('True','False'):value[key]=item=='True'
                else:
                    try:value[key]=json.loads(item)
                    except (ValueError,TypeError):value[key]=item
            result.append(value)
    return result


def snapshots(folder):
    state=c.read(folder/'rl/state.json');training=[];validation=[];milestones=[]
    for identity,meta in state['learners'].items():
        path=folder/'rl'/meta['file']
        if c.digest(path)!=meta['sha256']:raise ValueError('snapshot checkpoint changed; retry read after current update commits')
        payload=a.v.torch.load(path,map_location='cpu',weights_only=False)
        training.extend(payload['training_records']);validation.extend(payload['validation_records'])
    for m in state['milestones']:
        record=dict(m)
        record['terminal_available']=c.digest(folder/'rl'/m['terminal_file'])==m['terminal_sha256']
        milestones.append(record)
    return state,training,validation,milestones


def final_rows(folder):
    path=folder/'evaluation/state.json'
    if not path.exists():return [],dict(status='not_opened',cursor=0)
    state=c.read(path);rows=[]
    for i in range(state['cursor']):
        row=e.read_gzip(folder/'evaluation/items'/f'{i:06d}.json.gz')['row']
        if 'missed_eligible_complete' in row:
            row['raw_missed_counter_including_reference_not_audited']=row.pop('missed_eligible_complete')
        rows.append(row)
    return rows,state


def paired(rows,reference):
    refs={(r['trace_seed'],r['family'],r['context']):r for r in rows if r['policy']==reference}
    results=[]
    for row in rows:
        key=row['trace_seed'],row['family'],row['context']
        if key not in refs or row['policy']==reference:continue
        base=refs[key];full=(row['completed']==row['planned'] and row['equal_work'] and
            row['urgent_service_failure']==0 and row['normal_service_failure']==0)
        delta={k:row[k]-base[k] if row.get(k) is not None and base.get(k) is not None else None for k in METRICS}
        objectives=[delta[k] for k in METRICS[:3]]
        joint=full and all(x is not None and x<=1e-9 for x in objectives) and any(x<-1e-9 for x in objectives)
        strict=full and all(x is not None and x<-1e-9 for x in objectives)
        results.append(dict(reference=reference,policy=row['policy'],kind=row['kind'],variant=row.get('variant'),
            learning_seed=row.get('learning_seed'),episodes=row.get('episodes'),trace_seed=row['trace_seed'],family=row['family'],context=row['context'],
            stratum='primary' if row['family'] in ('low','sustained') else 'overload_stress',
            planned=row['planned'],completed=row['completed'],incomplete=row['planned']-row['completed'],
            urgent_failures=row['urgent_service_failure'],normal_failures=row['normal_service_failure'],
            full_service=full,joint_nonworsening=joint,strict_joint=strict,
            validation_eligible=row.get('validation_eligible'),
            **{k:row.get(k) for k in METRICS},
            delta_failures=row['urgent_service_failure']+row['normal_service_failure']-base['urgent_service_failure']-base['normal_service_failure'],
            **{'delta_'+k:value for k,value in delta.items()}))
    return results


def aggregate(pairs):
    result=[]
    for key in sorted({(r['reference'],r['policy'],r['stratum']) for r in pairs}):
        rs=[r for r in pairs if (r['reference'],r['policy'],r['stratum'])==key];first=rs[0]
        item=dict(reference=key[0],policy=key[1],stratum=key[2],kind=first['kind'],variant=first['variant'],
            learning_seed=first['learning_seed'],episodes=first['episodes'],cases=len(rs),
            expected_cases=96,planned=sum(r['planned'] for r in rs),completed=sum(r['completed'] for r in rs),
            incomplete=sum(r['incomplete'] for r in rs),urgent_failures=sum(r['urgent_failures'] for r in rs),
            normal_failures=sum(r['normal_failures'] for r in rs),full_service_cases=sum(r['full_service'] for r in rs),
            joint_cases=sum(r['joint_nonworsening'] for r in rs),strict_joint_cases=sum(r['strict_joint'] for r in rs),
            validation_eligible=first['validation_eligible'],sample_scope='conditional previously-seen synthetic cases, not independent phone sessions')
        for metric in METRICS:
            values=[r['delta_'+metric] for r in rs]
            item['mean_delta_'+metric]=statistics.mean(values) if all(x is not None for x in values) else None
            absolute=[r[metric] for r in rs]
            item['mean_'+metric]=statistics.mean(absolute) if all(x is not None for x in absolute) else None
        item['service_success_fraction']=(item['planned']-item['urgent_failures']-item['normal_failures'])/item['planned']
        result.append(item)
    return result


def micro_readout(folder):
    rows=jsonl(folder/'recombination/rows.jsonl');results=[]
    refs={(r['stage'],r['seed'],r['pattern'],r['context']):r for r in rows if r['policy']=='EFT_REFERENCE'}
    for row in rows:
        if row['policy']=='EFT_REFERENCE':continue
        ref=refs[row['stage'],row['seed'],row['pattern'],row['context']]
        results.append(dict(stage=row['stage'],seed=row['seed'],pattern=row['pattern'],context=row['context'],policy=row['policy'],
            planned=row['planned'],completed=row['completed'],deadline_met=row['deadline_met'],
            incomplete=row['planned']-row['completed'],
            **{'delta_'+k:row[k]-ref[k] if row.get(k) is not None and ref.get(k) is not None else None for k in METRICS},
            decision_host_total_s=row.get('decision_host_total_s'),decision_host_max_ms=row.get('decision_host_max_ms'),
            projections=row.get('projections'),raw_missed_counter_not_used=row.get('missed_eligible_complete')))
    return results


def figures(out,training,validation,groups,micro):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    identities=[f'{variant}_{seed}' for variant,seed in a.IDENTITIES]
    for filename,fields,title in [
        ('01_validation',('urgent_failures','normal_failures','mean_J','mean_peak','mean_area','mean_urgent_p95'),'Development validation, same 24 cases'),
        ('02_training',('energy_J','WAIT_fraction','rollout_transitions','loss','entropy','clip_fraction'),'Training, seed-specific')]:
        fig,axes=plt.subplots(2,3,figsize=(14,7.5));source=validation if filename=='01_validation' else training
        for ax,metric in zip(axes.flat,fields):
            for identity in identities:
                rs=[r for r in source if r['identity']==identity]
                if not rs:continue
                ys=[(r['WAIT_actions']/r['rollout_transitions']) if metric=='WAIT_fraction' else r.get(metric) for r in rs]
                ax.plot([r['episodes'] for r in rs],ys,label=identity,lw=1.2)
            ax.set_title(metric);ax.set_xlabel('episodes');ax.grid(alpha=.25)
        axes[0,0].legend(fontsize=7);fig.suptitle(title);fig.tight_layout()
        fig.savefig(out/(filename+'.png'),dpi=150);fig.savefig(out/(filename+'.svg'));plt.close(fig)
    primary=[r for r in groups if r['reference']=='SHARED_EFT' and r['stratum']=='primary' and r['kind'] in ('latest','best')]
    fig,axes=plt.subplots(1,3,figsize=(14,4.5))
    colors=plt.get_cmap('tab10')
    for ax,metric,title in zip(axes,('mean_delta_energy_j','mean_delta_peak_ap_c','mean_delta_thermal_degree_seconds'),('Energy delta J','Peak AP delta C','AP burden delta C s')):
        for color_index,identity in enumerate(identities):
            for kind,style in [('latest','--'),('best','-')]:
                rs=sorted([r for r in primary if r['policy'].startswith(identity+'_') and r['kind']==kind],key=lambda r:r['episodes'])
                if rs:ax.plot([r['episodes'] for r in rs],[r[metric] for r in rs],style,marker='o',ms=3,label=identity+' '+kind,color=colors(color_index))
        ax.axhline(0,color='k',lw=.6);ax.set_title(title);ax.set_xlabel('episodes');ax.grid(alpha=.25)
    if primary:
        handles,labels=axes[0].get_legend_handles_labels();fig.legend(handles,labels,fontsize=7,ncol=6,loc='upper center',bbox_to_anchor=(.5,.95))
    fig.suptitle('Final test, primary96: latest dashed / validation best solid');fig.tight_layout(rect=(0,0,1,.80))
    fig.savefig(out/'03_latest_best.png',dpi=150);fig.savefig(out/'03_latest_best.svg');plt.close(fig)
    fig,axes=plt.subplots(1,3,figsize=(13,4))
    for ax,metric in zip(axes,('delta_energy_j','delta_peak_ap_c','delta_urgent_p95_ms')):
        for policy,color in [('PREFIX3_IMMEDIATE','#286eaa'),('COMPLETE3_IMMEDIATE','#c26a20')]:
            rs=[r for r in micro if r['policy']==policy and r['stage']=='confirmation']
            ax.scatter(range(len(rs)),[r[metric] for r in rs],s=22,label=policy,color=color)
        ax.axhline(0,color='k',lw=.6);ax.set_title(metric);ax.set_xlabel('conditional microcase');ax.grid(alpha=.25)
    axes[0].legend(fontsize=7);fig.tight_layout();fig.savefig(out/'04_recombination.png',dpi=150);fig.savefig(out/'04_recombination.svg');plt.close(fig)
    fig,axes=plt.subplots(2,3,figsize=(14,7.5))
    for ax,identity in zip(axes.flat,identities):
        for kind,style in [('latest','--'),('best','-')]:
            rs=sorted([r for r in primary if r['policy'].startswith(identity+'_') and r['kind']==kind],key=lambda r:r['episodes'])
            if not rs:continue
            ax.plot([r['episodes'] for r in rs],[r['full_service_cases'] for r in rs],style,marker='o',label=kind)
            bad=[r for r in rs if not r['validation_eligible']]
            ax.scatter([r['episodes'] for r in bad],[r['full_service_cases'] for r in bad],marker='x' if kind=='latest' else '+',color='#ad3434',s=60,zorder=5)
        ax.set_title(identity);ax.set_xlabel('episodes');ax.set_ylabel('full service cases /96');ax.set_ylim(0,100);ax.grid(alpha=.25);ax.legend(fontsize=8)
    fig.suptitle('Final primary service: red x = ineligible latest; red + = ineligible best');fig.tight_layout()
    fig.savefig(out/'05_final_service.png',dpi=150);fig.savefig(out/'05_final_service.svg');plt.close(fig)


def dashboard(out,summary,validation,groups,micro):
    data=json.dumps(dict(summary=summary,validation=validation,groups=groups,micro=micro),ensure_ascii=False).replace('</','<\/')
    page='''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>규칙 재조합·PPO 학습량</title>
<style>body{font:15px system-ui;max-width:1450px;margin:28px auto;padding:0 20px;color:#172635;background:#f4f6fa}h1{margin-bottom:8px}section{background:white;padding:20px;margin:18px 0;border-radius:10px}.note{background:#fff0ce;padding:14px}img{width:100%;max-width:1300px}table{border-collapse:collapse;font-size:12px;width:100%}th,td{padding:7px;border-bottom:1px solid #d4dce4;text-align:right}th:first-child,td:first-child{text-align:left}select{margin:8px;padding:7px}.scroll{overflow:auto;max-height:600px}a{color:#165c9c}code{overflow-wrap:anywhere}pre{white-space:pre-wrap;overflow-wrap:anywhere}</style>
<h1>규칙 재조합과 PPO 학습량 비교</h1><p><a href="README.md">계약·재현</a> · <a href="../../../REQUEST_RULES_RL_AMOUNT_20261007.md">한국어 보고서</a> · <a href="validation.csv">검증 CSV</a> · <a href="final_results.csv">최종 CSV</a> · <a href="paired_differences.csv">짝 차이</a> · <a href="checkpoint_manifest.json">체크포인트</a></p>
<p id="finding"></p>
<p class="note">동결 모형의 PC 결과입니다. 기기 명령 0. 기존에 노출된 검증·시험 자료의 대응 비교이며 실기기 절감·새 독립 검증·수렴을 입증하지 않습니다. 미완료/미확인은 0으로 채우지 않습니다.</p>
<section><h2>진행·소비</h2><p id="compact"></p><details><summary>실행 장부 상세</summary><pre id="status"></pre></details></section>
<section><h2>재조합: 즉시 행동·최대3도착요청</h2><p id="micro"></p><img src="04_recombination.png" alt="확인 microcase의 J·AP 최고·긴급P95 차이"></section>
<section><h2>개발 검증과 학습</h2><p>각 선은 학습 seed 한 개입니다. 아래 곡선으로 연장을 판단하고, 최종 시험으로 checkpoint를 고르지 않았습니다.</p><img src="01_validation.png" alt="개발 검증의 서비스와 J/AP 곡선"><img src="02_training.png" alt="seed별 학습 곡선"></section>
<section><h2>최종 시험: 마지막 정책과 검증 선택 정책</h2><p>점선 latest / 실선 best. 빨간 x는 마지막 정책, 빨간 +는 검증 선택 정책의 개발 검증 부적격 표시입니다. 전체 조건의 비용 차이는 서비스 부적격일 때 진단값입니다.</p><img src="05_final_service.png" alt="학습량별 마지막·검증 선택의 최종 전량·기한 충족"><img src="03_latest_best.png" alt="학습량별 마지막·검증 선택의 최종 비용 차이">
<label>기준<select id="ref"><option>SHARED_EFT</option><option>EFT_REFERENCE</option><option>CPU_REFERENCE</option><option>SPLIT_REFERENCE</option><option>SHARED_EDF</option><option>PREFIX3_IMMEDIATE</option><option>COMPLETE3_IMMEDIATE</option></select></label>
<label>조건<select id="stratum"><option value="primary">주 조건</option><option value="overload_stress">과부하</option></select></label>
<label>학습 seed<select id="seed"><option value="all">전체</option><option>11</option><option>23</option><option>37</option></select></label>
<label>정책<select id="kind"><option value="all">전체</option><option>latest</option><option>best</option><option>recombination</option><option>baseline</option></select></label>
<div class="scroll"><table><thead><tr><th>정책</th><th>검증 적격</th><th>조건</th><th>예정/완료</th><th>실패 긴급/일반</th><th>전체 서비스 성공%</th><th>완료긴급P95 평균 ms</th><th>전량·기한 조건</th><th>공동 비악화 조건</th><th>ΔJ</th><th>ΔAP최고 °C</th><th>Δ면적 °C·s</th><th>Δ긴급P95 ms</th><th>Δ일반 ms</th></tr></thead><tbody id="rows"></tbody></table></div><p>검증 부적격 정책의 공동 비악화 조건은 진단값입니다. 일부 조건의 이득으로 정책 전체를 채택하지 않습니다. 응답P95는 조건별P95 평균이며 pooled P95가 아닙니다.</p></section>
<script>const D=DATA;document.getElementById('status').textContent=JSON.stringify(D.summary,null,2);const names={running:'학습 진행',training_completed:'학습 종료',budget_stopped:'예산 종료',not_opened:'시험 미개방',completed:'평가 완료'};document.getElementById('compact').textContent='RL '+(names[D.summary.training_status]||D.summary.training_status)+' · '+(names[D.summary.evaluation_status]||D.summary.evaluation_status)+' | 환경 실행: 재조합 '+D.summary.environment_runs.recombination+' / RL '+D.summary.environment_runs.rl+' | 저장된 학습 '+D.summary.valid_committed_training_episodes+'에피소드 | 6개 공통 비교 지점 '+(D.summary.common_episode_points.join(', ')||'아직 미확보')+' | '+new Date(D.summary.updated_utc).toLocaleString('ko-KR',{timeZone:'Asia/Seoul'});document.getElementById('micro').textContent='개발에서 EFT를 고정했습니다. 완성 조합은 유효 가지를 더 찾았지만 작은 에너지 이득에 긴급 응답·AP 최고값의 대가가 있었습니다. 정확한 숫자는 보고서와 CSV를 확인하세요.';
if(D.summary.evaluation_status==='completed'){const selected=D.groups.filter(x=>x.reference==='SHARED_EFT'&&x.stratum==='primary'&&x.kind==='best');const counts=D.summary.common_episode_points.map(n=>selected.filter(x=>x.episodes===n&&x.validation_eligible).length);const joint=selected.filter(x=>x.validation_eligible).reduce((sum,x)=>sum+x.joint_cases,0);document.getElementById('finding').textContent='선택 정책 검증 적격: '+counts.join(' → ')+'개/6. 강한 SHARED_EFT 대비 적격 선택 정책의 공동 개선 '+joint+'건. 일부 서비스 개선·회귀와 에너지–열–응답 상충이 남았습니다. 8,192 상한 도달·수렴 미확인입니다.';}else{document.getElementById('finding').textContent='학습량 비교를 진행 중입니다. 최종 정책 동결 뒤 시험을 판독합니다.';}
const fmt=v=>v===null||v===undefined?'미확인':typeof v==='number'?Number(v.toPrecision(7)).toString():String(v);const esc=v=>String(v).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));function draw(){const r=document.getElementById('ref').value,s=document.getElementById('stratum').value,seed=document.getElementById('seed').value,k=document.getElementById('kind').value;document.getElementById('rows').innerHTML=D.groups.filter(x=>x.reference===r&&x.stratum===s&&(seed==='all'||String(x.learning_seed)===seed)&&(k==='all'||x.kind===k)).map(x=>'<tr>'+[x.policy,x.validation_eligible===null?'기준/규칙':x.validation_eligible?'적격':'부적격',x.cases+'/96',x.planned+'/'+x.completed,x.urgent_failures+'/'+x.normal_failures,100*x.service_success_fraction,x.mean_urgent_p95_ms,x.full_service_cases,x.joint_cases,x.mean_delta_energy_j,x.mean_delta_peak_ap_c,x.mean_delta_thermal_degree_seconds,x.mean_delta_urgent_p95_ms,x.mean_delta_normal_mean_ms].map(v=>'<td>'+esc(fmt(v))+'</td>').join('')+'</tr>').join('');}for(const id of ['ref','stratum','seed','kind'])document.getElementById(id).addEventListener('change',draw);draw();</script></html>'''.replace('DATA',data)
    (out/'index.html').write_text(page,encoding='utf8')


def run(folder=c.OUTPUT,out=c.BUNDLE,plots=True):
    folder=Path(folder);out=Path(out);out.mkdir(parents=True,exist_ok=True)
    state,training,validation,milestones=snapshots(folder)
    rows,evaluation=final_rows(folder);pairs=[]
    for reference in (*a.v.load_plan()['baselines'],r_prefix(),r_complete()):pairs.extend(paired(rows,reference))
    groups=aggregate(pairs);micro=micro_readout(folder)
    budget=c.Budget(folder);ledger=jsonl(folder/'consumption.jsonl')
    optimizer_events=[x for x in ledger if x['event']=='optimizer']
    summary=dict(updated_utc=c.utc(),training_status=state['status'],evaluation_status=evaluation['status'],
        environment_runs=budget.counts,training_episodes_including_replay=budget.training,
        PPO_updates_executed=budget.optimizers,
        Adam_steps_known=sum(x['minibatches'] for x in optimizer_events if x.get('minibatches') is not None),
        Adam_step_count_unknown_fixture_updates=sum(x.get('minibatches') is None for x in optimizer_events),
        valid_committed_training_episodes=sum(m['episodes'] for m in state['learners'].values()),
        committed_PPO_updates=sum(m['update'] for m in state['learners'].values()),
        common_episode_points=sorted(n for n in {m['episodes'] for m in milestones}
            if len([m for m in milestones if m['episodes']==n])==6),
        final_rows=len(rows),reused_evaluation_rows=evaluation.get('reused',0),
        unresolved_environment_entries=budget.pending,device_commands=0,experiment_ready=False,
        context='retrospective conditional frozen-model comparison; no physical policy/convergence claim')
    # Full per-condition comparisons against all seven controls remain local.
    # Two principal references plus complete aggregate tables keep Git modest.
    shared_pairs=[p for p in pairs if p['reference'] in ('SHARED_EFT','EFT_REFERENCE')]
    for name,records in [('training.csv',training),('validation.csv',validation),('final_results.csv',rows),
        ('paired_differences.csv',shared_pairs),('policy_summary.csv',groups),('recombination_paired.csv',micro)]:csv_write(out/name,records)
    if pairs:
        fields=list(dict.fromkeys(k for row in pairs for k in row))
        with gzip.open(folder/'all_reference_pairs.csv.gz','wt',encoding='utf8',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader();writer.writerows(pairs)
        c.atomic(out/'local_pair_manifest.json',dict(file='output/rules_rl_amount_20261007_v1/all_reference_pairs.csv.gz',
            sha256=c.digest(folder/'all_reference_pairs.csv.gz'),rows=len(pairs),shared_rows=len(shared_pairs)))
    c.atomic(out/'summary.json',summary);c.atomic(out/'checkpoint_manifest.json',dict(milestones=milestones,learners=state['learners']))
    if plots:figures(out,training,validation,groups,micro)
    dashboard(out,summary,validation,groups,micro)
    for source,destination in [('campaign.json','campaign.json'),('rl_contract_before_run.json','rl_contract.json'),
        ('recombination/contract_before_run.json','recombination_contract.json'),
        ('recombination/freeze_before_confirmation.json','recombination_freeze.json'),
        ('recombination/first_decision_branch_audit.json','branch_audit.json'),
        ('rl/extension_decision_before_test.json','extension_decision.json'),
        ('final_comparison_freeze.json','final_freeze.json')]:
        path=folder/source
        if path.exists():shutil.copyfile(path,out/destination)
    c.atomic(out/'report_verification.json',dict(source_head='9e1975bfd4cb96587e7cfb5b18b85f5409ff0b83',
        working_tree='related implementation/docs/results modified; user files preserved',verified_utc=c.utc(),
        new_environment_runs=0,new_training=0,rows=len(rows),validation_records=len(validation),
        files={p.name:c.digest(p) for p in out.iterdir() if p.is_file() and p.name!='report_verification.json'}))
    return summary


def r_prefix():return 'PREFIX3_IMMEDIATE'
def r_complete():return 'COMPLETE3_IMMEDIATE'


def reproduce_shared(source,out):
    source=Path(source);out=Path(out);out.mkdir(parents=True,exist_ok=True)
    verification=c.read(source/'report_verification.json')
    required=['summary.json','training.csv','validation.csv','policy_summary.csv','recombination_paired.csv']
    for name in required:
        if c.digest(source/name)!=verification['files'][name]:raise ValueError('shared source changed: '+name)
    summary=c.read(source/'summary.json');training=csv_read(source/'training.csv');validation=csv_read(source/'validation.csv')
    groups=csv_read(source/'policy_summary.csv');micro=csv_read(source/'recombination_paired.csv')
    figures(out,training,validation,groups,micro);dashboard(out,summary,validation,groups,micro)
    c.atomic(out/'shared_reproduction.json',dict(environment_runs=0,training=0,
        source_verification_sha256=c.digest(source/'report_verification.json'),
        source_files={name:c.digest(source/name) for name in required},
        png_identical={name:c.digest(source/name)==c.digest(out/name) for name in
            ('01_validation.png','02_training.png','03_latest_best.png','04_recombination.png','05_final_service.png')}))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--folder',default=str(c.OUTPUT));p.add_argument('--output',default=str(c.BUNDLE));p.add_argument('--no-plots',action='store_true');p.add_argument('--shared-source')
    args=p.parse_args()
    if args.shared_source:reproduce_shared(args.shared_source,args.output)
    else:print(json.dumps(run(args.folder,args.output,not args.no_plots),ensure_ascii=False,indent=2))
