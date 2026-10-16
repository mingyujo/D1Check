"""Read-only PPO learning-amount diagnosis; never silently initializes a learner."""
from __future__ import annotations
import argparse
import copy
import csv
from datetime import datetime, timezone
import html
import json
import math
from pathlib import Path
import random
import statistics
import time

from tools import d1_queue_ppo_v2 as v

VERSION='queue-ppo-learning-amount-review-v1'
BUNDLE=v.q.p.ROOT/'docs/results/request_ppo_01/queue_learning_amount_v1'


class TerminalArchiveSession(v.Session):
    """Future-run producer only: preserve each final training state before clearing.

    No CLI starts this session. Existing runs cannot acquire lost optimizer/RNG
    retrospectively. The immutable archive adds PC I/O, no environment action.
    """
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.s['sources']['tools/d1_queue_ppo_learning_amount.py']=v.q.p.digest(Path(__file__))

    def step(self):
        s=self.s;cfg=s['config']
        terminal=(s['phase']=='validate' and s['update']==cfg['updates']
                  and s['validation_index']==len(cfg['validation'])-1)
        if terminal:
            net,opt=self.network,self.optimizer;identity=cfg['learners'][s['learner']]
        super().step()
        if terminal:
            payload=dict(version='queue-ppo-terminal-training-state-v1',identity=list(identity),update=cfg['updates'],
                episodes=cfg['updates']*cfg['batch'],network=copy.deepcopy(net.state_dict()),
                optimizer=copy.deepcopy(opt.state_dict()),multipliers=s['multipliers'].copy(),
                python_rng=random.getstate(),numpy_rng=v.np.random.get_state(),torch_rng=v.torch.get_rng_state(),
                selected=copy.deepcopy(s['selected'][-1]),initial=s['initial'],frozen=s['frozen'],
                plan=s['plan'],config=cfg,sources=s['sources'],
                normalization='per_optimizer_batch_only_no_running_statistics',phase='after_final_validation_before_next_learner')
            name=f'terminal_{identity[0]}_seed{identity[1]}_update{cfg["updates"]}.pt'
            path=self.folder/name
            if path.exists():raise ValueError('terminal archive already exists; no overwrite')
            temporary=path.with_suffix('.tmp')
            with temporary.open('xb') as f:
                v.torch.save(payload,f);f.flush();v.durable.os.fsync(f.fileno())
            v.durable.os.replace(temporary,path)
            s.setdefault('terminal_archives',[]).append(dict(identity=list(identity),file=name,sha256=v.q.p.digest(path)))


def optimizer_presentations(n,minibatches,epochs=4,batch=256):
    """Sample presentations, with repetitions; inferred from unchanged loop sizes."""
    if n<=0 or not 0<=minibatches<=epochs*math.ceil(n/batch):raise ValueError('invalid optimizer accounting')
    batches=math.ceil(n/batch);complete,remainder=divmod(minibatches,batches)
    return complete*n+remainder*batch


def require_exact_states(states,identities,updates):
    missing=[]
    fields=('network','optimizer','multipliers','python_rng','numpy_rng','torch_rng')
    for identity in identities:
        state=states.get(tuple(identity))
        if state is None:missing.append(dict(identity=list(identity),missing=list(fields)+['terminal_update_identity']))
        else:
            absent=[k for k in fields if state.get(k) is None]
            if state.get('update')!=updates:absent.append('terminal_update_identity')
            if state.get('identity')!=list(identity):absent.append('learner_identity')
            if state.get('network') is not None and not all(any(k.startswith(prefix) for k in state['network']) for prefix in ('actor.','value.')):
                absent.append('actor_and_critic')
            if state.get('optimizer') is not None:
                moments=state['optimizer'].get('state',{})
                if not moments or any(not {'step','exp_avg','exp_avg_sq'}<=set(x) for x in moments.values()):
                    absent.append('Adam_moments_and_step')
            if absent:missing.append(dict(identity=list(identity),missing=absent))
    if missing:raise ValueError('EXACT_EXTENSION_BLOCKED: '+json.dumps(missing))


def audit(source):
    if v.q.LOCK.exists():raise ValueError('active or unresolved PPO owner; no duplicate work')
    source=Path(source);manifest=json.loads((source/'run_manifest.json').read_text(encoding='utf8'))
    v.durable.require_sources(manifest['sources'])
    inventory=[];archives={}
    if not list(source.glob('state_*.pt')):raise ValueError('original checkpoint files unavailable')
    for path in sorted(source.glob('state_*.pt')):
        state=v.torch.load(path,map_location='cpu',weights_only=False)
        inventory.append(dict(file=path.name,sha256=v.q.p.digest(path),bytes=path.stat().st_size,
            status=state['status'],phase=state['phase'],learner=state['learner'],update=state['update'],
            network_present=state['network'] is not None,optimizer_present=state['optimizer'] is not None,
            selected_only=[dict(variant=a['variant'],seed=a['seed'],selected_update=a['update']) for a in state['selected']],
            global_rng_scope='after_freeze_and_final_test_not_per_learner_terminal',
            remaining_multiplier_identity=list(state['config']['learners'][-1])))
        if path.name==json.loads((source/'checkpoint.json').read_text(encoding='utf8'))['file']:
            if v.q.p.digest(path)!=json.loads((source/'checkpoint.json').read_text(encoding='utf8'))['sha256']:
                raise ValueError('source checkpoint integrity')
            counts=state['counts']
        del state
    for path in sorted(source.glob('terminal_*_update*.pt')):
        state=v.torch.load(path,map_location='cpu',weights_only=False)
        archives[tuple(state['identity'])]=state
    identities=[(a,s) for a in manifest['plan']['variants'] for s in manifest['plan']['learning_seeds']]
    ready=True;reason=None
    try:require_exact_states(archives,identities,manifest['plan']['budget']['updates_per_learner'])
    except ValueError as exc:ready=False;reason=str(exc)
    latest=json.loads((source/'LATEST_RECEIPT.json').read_text(encoding='utf8'))
    receipt=json.loads((source/latest['file']).read_text(encoding='utf8'))
    if receipt['counts']!=counts or receipt['status']!='budget_stopped':raise ValueError('source termination mismatch')
    return dict(version=VERSION,extension_ready=ready,status='CHECK_BLOCKED_MISSING_STATE' if not ready else 'CHECK_STATE_PRESENT_REQUIRES_IMPORT_VALIDATION',
        reason=reason,required_learners=[list(i) for i in identities],available_terminal_states=len(archives),
        inventory=inventory,original_receipt=receipt,claim_created=False,additional_training_episodes=0,
        additional_environment_runs=0,device_commands=0)


def csv_save(path,rows):
    names=list(dict.fromkeys(k for r in rows for k in r))
    with Path(path).open('w',encoding='utf8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=names);writer.writeheader();writer.writerows(rows)


def read_csv(path):
    with Path(path).open(encoding='utf8',newline='') as f:return list(csv.DictReader(f))


def typed_csv(path):
    rows=read_csv(path)
    for row in rows:
        for key,value in row.items():
            if value=='':row[key]=None
            elif value in ('True','False'):row[key]=value=='True'
            elif key in ('seed','update','episodes'):row[key]=int(value)
            else:
                try:row[key]=float(value)
                except ValueError:pass
    return rows


def plot_shared(output):
    output=Path(output)
    if output.exists():raise ValueError('existing plot output; no overwrite')
    data=json.loads((BUNDLE/'summary.json').read_text(encoding='utf8'))
    output.mkdir(parents=True,exist_ok=False)
    plots(output,typed_csv(BUNDLE/'training_curve.csv'),typed_csv(BUNDLE/'validation_curve.csv'),
          typed_csv(BUNDLE/'policy_results.csv'),data)
    print('Shared CSV/JSON plots reproduced; raw checkpoint not read; learning/device calls 0')


def training_rows(notes):
    result=[];totals={}
    for row in notes:
        if row['stage']!='training':continue
        key=(row['variant'],row['seed']);n=row['decisions'];k=row['minibatch_updates']
        current=totals.setdefault(key,dict(transitions=0,presentations=0))
        current['transitions']+=n;presented=optimizer_presentations(n,k);current['presentations']+=presented
        if not 0<=row['WAIT_actions']<=n or not 0<=row['single_legal_decisions']<=n:raise ValueError('invalid decisions')
        result.append(dict(variant=key[0],seed=key[1],update=row['update'],episodes=row['learner_episodes'],
            environment_transitions=None,rollout_transitions=n,cumulative_rollout_transitions=current['transitions'],
            optimizer_sample_presentations=presented,cumulative_optimizer_sample_presentations=current['presentations'],
            WAIT_actions=row['WAIT_actions'],WAIT_fraction=row['WAIT_actions']/n,single_legal_fraction=row['single_legal_decisions']/n,
            policy_controllable_transitions=n-row['single_legal_decisions'],
            mean_urgent_failure_fraction=row['mean_costs'][0],mean_normal_failure_fraction=row['mean_costs'][1],
            exact_training_failure_counts=None,training_incomplete_counts=None,mean_J=row['energy_J'],
            mean_positive_scaled_AP_area_cost=row['mean_costs'][2],mean_positive_AP_peak_cost=row['mean_costs'][3],
            training_absolute_AP_peak=None,training_absolute_AP_area=None,training_urgent_P95=None,training_normal_response=None,
            loss=row['loss'],kl=row['kl'],entropy=row['entropy'],minibatch_updates=k,
            original_elapsed_s=row['elapsed_s']))
    for key in totals:
        group=[r for r in result if (r['variant'],r['seed'])==key]
        if [r['update'] for r in group]!=list(range(1,129)) or group[-1]['episodes']!=1024:
            raise ValueError('incomplete/duplicate original training updates')
    return result


def validation_rows(raw,train,notes):
    training={(r['variant'],r['seed'],r['update']):r for r in train}
    keys={(r['variant'],r['seed'],r['update']):r['selection_key'] for r in notes if r['stage']=='validation_primary_only'}
    result=[]
    groups=sorted({(r['variant'],int(r['seed']),int(r['update'])) for r in raw})
    for variant,seed,update in groups:
        group=[r for r in raw if (r['variant'],int(r['seed']),int(r['update']))==(variant,seed,update)]
        if len(group)!=24:raise ValueError('validation denominator changed')
        key=keys[(variant,seed,update)];t=training.get((variant,seed,update))
        result.append(dict(variant=variant,seed=seed,update=update,episodes=update*8,
            cumulative_environment_transitions=None,cumulative_rollout_transitions=t['cumulative_rollout_transitions'] if t else 0,
            cumulative_optimizer_sample_presentations=t['cumulative_optimizer_sample_presentations'] if t else 0,
            cases=len(group),planned=sum(int(r['planned']) for r in group),completed=sum(int(r['completed']) for r in group),
            urgent_failures=sum(int(r['urgent_service_failure']) for r in group),normal_failures=sum(int(r['normal_service_failure']) for r in group),
            urgent_failure_fraction=sum(int(r['urgent_service_failure']) for r in group)/sum(int(r['urgent_n']) for r in group),
            normal_failure_fraction=sum(int(r['normal_service_failure']) for r in group)/sum(int(r['normal_n']) for r in group),
            incomplete=sum(int(r['planned'])-int(r['completed']) for r in group),
            service_violation_cases=int(key[1]),thermal_violation_cases=int(key[3]),
            mean_J=statistics.mean(float(r['energy_j']) for r in group),
            mean_AP_peak_C=statistics.mean(float(r['peak_ap_c']) for r in group),
            mean_AP_area_Cs=statistics.mean(float(r['thermal_degree_seconds']) for r in group),
            mean_case_urgent_P95_ms=statistics.mean(float(r['urgent_p95_ms']) for r in group),
            mean_case_normal_response_ms=statistics.mean(float(r['normal_mean_ms']) for r in group)))
    if len(result)!=30:raise ValueError('validation checkpoints missing')
    return result


def policy_rows(rows,pairs,selected):
    refs={(r['trace_seed'],r['family'],r['context']):r for r in rows if r['policy']=='SHARED_EFT'}
    result=[];selection={f'{s["variant"]}_seed{s["seed"]}':s for s in selected}
    for policy in dict.fromkeys(r['policy'] for r in rows):
        for stratum,families in [('primary',('low','sustained')),('overload_stress',('queue','burst'))]:
            group=[r for r in rows if r['policy']==policy and r['family'] in families]
            paired=[r for r in pairs if r['policy']==policy and r['stratum']==stratum]
            delta={k:[float(r[k])-float(refs[(r['trace_seed'],r['family'],r['context'])][k]) for r in group]
                for k in ('energy_j','peak_ap_c','thermal_degree_seconds','urgent_p95_ms','normal_mean_ms')}
            good=sum(r['equal_work']=='True' and int(r['urgent_service_failure'])==int(r['normal_service_failure'])==0 for r in group)
            meta=selection.get(policy,{})
            result.append(dict(policy=policy,variant=meta.get('variant'),seed=meta.get('seed'),stratum=stratum,cases=len(group),
                episodes=1024 if meta else None,selected_update=meta.get('update'),selected_update0=meta.get('update')==0 if meta else None,
                validation_eligible=meta.get('eligible'),service_good_cases=good,
                urgent_failures=sum(int(r['urgent_service_failure']) for r in group),normal_failures=sum(int(r['normal_service_failure']) for r in group),
                incomplete=sum(int(r['planned'])-int(r['completed']) for r in group),
                heat_nonworse_cases=sum(delta['peak_ap_c'][i]<=v.design.EPS and delta['thermal_degree_seconds'][i]<=v.design.EPS for i in range(len(group))),
                mean_delta_J=statistics.mean(delta['energy_j']),mean_delta_peak_C=statistics.mean(delta['peak_ap_c']),
                mean_delta_area_Cs=statistics.mean(delta['thermal_degree_seconds']),mean_delta_urgent_P95_ms=statistics.mean(delta['urgent_p95_ms']),
                mean_delta_normal_response_ms=statistics.mean(delta['normal_mean_ms']),
                joint_nonworsening=sum(r['joint_nonworsening']=='True' for r in paired),strict_joint=sum(r['strict_joint_improvement']=='True' for r in paired),
                means_scope='all_matched_cases_diagnostic_if_service_or_selection_ineligible'))
    return result


def plots(folder,train,validation,policies,summary):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.family':'Malgun Gothic','axes.unicode_minus':False})
    colors=['#2166ac','#4393c3','#92c5de','#b2182b','#d6604d','#f4a582']
    identities=sorted({(r['variant'],r['seed']) for r in validation})
    def draw(ax,x,y):
        for color,key in zip(colors,identities):
            group=[r for r in validation if (r['variant'],r['seed'])==key]
            ax.plot([r[x] for r in group],[r[y] for r in group],marker='o',color=color,label=f'{key[0]}/{key[1]}')
        ax.grid(alpha=.2)
    fig,axes=plt.subplots(1,2,figsize=(14,5))
    draw(axes[0],'cumulative_rollout_transitions','urgent_failure_fraction');draw(axes[1],'cumulative_rollout_transitions','thermal_violation_cases')
    for ax in axes:ax.set_xlabel('누적 기록된 학습 rollout transition');ax.legend(fontsize=8)
    axes[0].set_ylabel('검증 긴급 실패율');axes[1].set_ylabel('검증 열 악화 조건 수 /24')
    fig.suptitle('기존 1,024에피소드 분석 · 전체 환경 transition 미기록 · 연장 미실행');fig.tight_layout();fig.savefig(folder/'01_transition_validation.png',dpi=150);plt.close(fig)
    fig,axes=plt.subplots(2,2,figsize=(14,8))
    for ax,y,label in zip(axes.flat,['urgent_failure_fraction','mean_J','mean_AP_peak_C','mean_AP_area_Cs'],['검증 긴급 실패율','검증 평균 J (0–120초)','검증 평균 AP 최고 (°C)','검증 평균 AP 부담 면적 (°C·s,35–180초)']):
        draw(ax,'episodes',y);ax.set_xlabel('누적 학습 에피소드');ax.set_ylabel(label)
    axes[0,0].legend(fontsize=8);fig.suptitle('같은 기존 검증 24조건 · 2,048/4,096점은 미실행');fig.tight_layout();fig.savefig(folder/'02_episode_validation.png',dpi=150);plt.close(fig)
    main=[r for r in policies if r['seed'] is not None and r['stratum']=='primary'];labels=[r['policy'] for r in main]
    fig,axes=plt.subplots(2,2,figsize=(14,8))
    for ax,k,title in zip(axes.flat,['mean_delta_J','mean_delta_peak_C','mean_delta_area_Cs','service_good_cases'],['SHARED_EFT 대비 평균 ΔJ','SHARED_EFT 대비 평균 ΔAP 최고 (°C)','SHARED_EFT 대비 평균 ΔAP 면적 (°C·s)','전체 기한·작업량 충족 조건 /96']):
        ax.bar(labels,[r[k] for r in main],color=colors);ax.axhline(0,color='#666',linewidth=.7);ax.set_title(title);ax.tick_params(axis='x',labelrotation=30);ax.grid(axis='y',alpha=.2)
    fig.suptitle('기존 예산의 선택 정책 · 모든 학습 seed · 부적격 결과는 진단값');fig.tight_layout();fig.savefig(folder/'03_seed_results.png',dpi=150);plt.close(fig)
    fig,axes=plt.subplots(1,3,figsize=(16,5))
    for ax,y,title in zip(axes,['mean_delta_peak_C','mean_delta_area_Cs','mean_delta_urgent_P95_ms'],['AP 최고 변화 (°C)','AP 부담 면적 변화 (°C·s)','긴급 P95 변화 (ms,조건별 평균)']):
        for color,r in zip(colors,main):
            ax.scatter(r['mean_delta_J'],r[y],color=color,marker='o' if r['validation_eligible'] else 'x',label=r['policy'])
        ax.axhline(0,color='#777',linewidth=.7);ax.axvline(0,color='#777',linewidth=.7);ax.set_xlabel('SHARED_EFT 대비 평균 ΔJ');ax.set_ylabel(title);ax.grid(alpha=.2)
    axes[0].legend(fontsize=8);fig.suptitle('같은 주평가 96조건 · 부적격 평균은 정책 순위에 사용하지 않음');fig.tight_layout();fig.savefig(folder/'04_EFT_tradeoff.png',dpi=150);plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(13,5));c=summary['original_logical_counts']
    axes[0].bar(['학습','검증','시험','참조'],[c[k] for k in ('training','validation','test','reference')]);axes[0].set_ylabel('기존 환경 실행 횟수')
    axes[1].bar(['원 실행','후속 평가','이번 연장'],[summary['original_active_s']/60,summary['followup_active_s']/60,0]);axes[1].set_ylabel('활성 시간 (분)')
    fig.suptitle('기존 예산과 별도 평가의 실제 소비 · 추가 본학습 0 (PC fixture 별도): 연장 이득 미판정');fig.tight_layout();fig.savefig(folder/'05_consumption.png',dpi=150);plt.close(fig)


def analyze(source,evaluation,output):
    started=time.monotonic();output=Path(output)
    if output.exists():raise ValueError('existing analysis output; no overwrite')
    source=Path(source);evaluation=Path(evaluation);report=audit(source)
    combined=json.loads((evaluation/'summary.json').read_text(encoding='utf8'))
    if not combined['combined_evaluation_complete']:raise ValueError('final evaluation incomplete')
    followup=json.loads((evaluation/json.loads((evaluation/'LATEST_RECEIPT.json').read_text())['file']).read_text())
    if followup['status']!='completed' or followup['original_error'] is not None:raise ValueError('evaluation not normally complete')
    input_paths=[source/'journal.jsonl',source/'run_manifest.json',source/'freeze_before_test.json',
        evaluation/'validation.csv',evaluation/'test.csv',evaluation/'paired_differences.csv',evaluation/'summary.json',
        source/'checkpoint.json',source/'LATEST_RECEIPT.json',evaluation/'LATEST_RECEIPT.json']
    input_paths.extend(sorted(source.glob('state_*.pt')))
    for actor in combined['selected']:
        path=source/actor['filename']
        if v.q.p.digest(path)!=actor['sha256']:raise ValueError('frozen actor changed')
        input_paths.append(path)
    hashes={str(p.resolve().relative_to(v.q.p.ROOT)).replace('\\','/'):v.q.p.digest(p) for p in input_paths}
    notes=[json.loads(line) for line in (source/'journal.jsonl').read_text(encoding='utf8').splitlines()]
    train=training_rows(notes);validation=validation_rows(read_csv(evaluation/'validation.csv'),train,notes)
    table=read_csv(evaluation/'test.csv');paired=read_csv(evaluation/'paired_differences.csv')
    if len(table)!=2112 or len(paired)!=2112 or len({(r['trace_seed'],r['family'],r['context'],r['policy']) for r in table})!=2112:
        raise ValueError('final comparison denominator')
    policies=policy_rows(table,paired,combined['selected'])
    if len(train)!=768:raise ValueError('training learner denominator')
    seeds=[]
    for key in sorted({(r['variant'],r['seed']) for r in train}):
        group=[r for r in train if (r['variant'],r['seed'])==key];last=group[-1]
        choice=next(a for a in combined['selected'] if (a['variant'],a['seed'])==key)
        seeds.append(dict(variant=key[0],seed=key[1],episodes=last['episodes'],updates=last['update'],
            environment_transitions=None,rollout_transitions=last['cumulative_rollout_transitions'],
            optimizer_sample_presentations=last['cumulative_optimizer_sample_presentations'],
            WAIT_fraction=sum(r['WAIT_actions'] for r in group)/sum(r['rollout_transitions'] for r in group),
            single_legal_fraction=sum(r['single_legal_fraction']*r['rollout_transitions'] for r in group)/sum(r['rollout_transitions'] for r in group),
            selected_update=choice['update'],selected_update0=choice['update']==0,validation_eligible=choice['eligible'],
            terminal_weights_available_in_selected_actor=choice['update']==128,terminal_optimizer_present=False,
            per_learner_terminal_rng_present=False,extension_ready=False))
    summary=dict(version=VERSION,status='BLOCKED_EXACT_EXTENSION_STATE_MISSING',extension_ready=False,
        original_logical_counts=combined['logical_original_plus_followup'],original_active_s=report['original_receipt']['elapsed_s'],
        followup_active_s=followup['elapsed_s'],seeds=seeds,additional_training_episodes=0,additional_environment_runs=0,
        hypothetical_extension_environment_runs=27672,environment_transition_scope='full environment transitions unrecorded; rollout/optimizer presentations reported separately',
        learning_amount_effect=None,global_convergence=None,independent_device_effect=None,
        sources_sha256=hashes,experiment_ready=False,device_commands=0)
    output.mkdir(parents=True,exist_ok=False)
    v.q.atomic(output/'checkpoint_inventory.json',report);csv_save(output/'training_curve.csv',train)
    csv_save(output/'validation_curve.csv',validation);csv_save(output/'seed_accounting.csv',seeds);csv_save(output/'policy_results.csv',policies)
    v.q.atomic(output/'summary.json',summary);plots(output,train,validation,policies,summary)
    images=['01_transition_validation.png','02_episode_validation.png','03_seed_results.png','04_EFT_tradeoff.png','05_consumption.png']
    body='<h1>PPO 학습량 분석: 정확한 연장 상태 누락</h1><p>기존 1,024에피소드 결과. 연장 0회, 효과 미판정. 학습량 부족·수렴·강화학습 일반 실패를 확정하지 않는다.</p>'
    body+='<p>전체 환경 transition은 미기록이다. 학습 rollout과 optimizer 반복 표본 제시를 구분한다. 확인 자료·PC 수치를 실기기 절감으로 확대하지 않는다.</p>'
    body+=''.join(f'<figure><img style="max-width:100%" src="{html.escape(name)}"><figcaption>{html.escape(name)}</figcaption></figure>' for name in images)
    (output/'index.html').write_text('<!doctype html><meta charset="utf-8">'+body,encoding='utf8')
    if any(v.q.p.digest(v.q.p.ROOT/name)!=sha for name,sha in hashes.items()):raise ValueError('original input changed during analysis')
    v.q.atomic(output/'ANALYSIS_RECEIPT.json',dict(status='analysis_completed_extension_blocked',elapsed_s=time.monotonic()-started,
        training_updates=0,environment_runs=0,device_commands=0,claim_created=False,original_inputs_preserved=True,
        analyzed_training_updates=len(train),analyzed_final_table_rows=combined['table_rows']))
    print(json.dumps(summary,ensure_ascii=False,default=str))


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--action',choices=['Check','Analyze','PlotShared'],default='Check')
    parser.add_argument('--source',default='output/queue_ppo_feasible_v2');parser.add_argument('--evaluation',default='output/queue_ppo_v2_evaluation_v1')
    parser.add_argument('--output',default='output/queue_ppo_learning_amount_review_v1');args=parser.parse_args()
    if args.action=='Check':print(json.dumps(audit(args.source),ensure_ascii=False,indent=2))
    elif args.action=='PlotShared':plot_shared(args.output)
    else:analyze(args.source,args.evaluation,args.output)


if __name__=='__main__':main()
