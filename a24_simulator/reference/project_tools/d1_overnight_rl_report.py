"""Full amount-study analysis; no simulation, training, fitting or ADB calls."""
import csv,gzip,hashlib,html,json,statistics
from datetime import datetime,timezone
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from tools import d1_overnight_rl_amount as x

PUBLIC=x.PUBLIC
REPRESENTATIVE_CONDITION=9  # First fresh seed/sustained/mean, fixed before outcomes.
def table(path,rows):
    if not rows:return
    keys=list(dict.fromkeys(k for q in rows for k in q))
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(rows)
def label(role):
    fixed={'L0':'기한 우선 리스트 L0','Band':'Band 판단규칙 대응','Triton':'Triton 판단규칙 대응','Rule':'같은 후보 비학습 선택기'}
    if role in fixed:return fixed[role]
    if role.startswith('NoWait'):return '대기 제거 seed'+role[6:]
    if role.startswith('NoThermal'):return '명시 열특징 제거 seed'+role[9:]
    return 'PPO seed'+role[3:].replace('_',' · 학습')
def schedule(item):return [(q['id'],q.get('backend'),q.get('dispatch_ns'),q.get('response_ns'),q.get('lane_available_ns'),q['status']) for q in item['result']['ledger']]
def load(q):return x.x.read_raw(q['identity']) if q.get('reused_completed') else x.read_raw(q['identity'])
def payload_digest(value):
    """Include archived policy objects by class and their saved attributes.

The training primitive digest covers tensors/RNG dictionaries. Controller
archives also contain the unchanged ServiceActual object, so compare its full
typed state rather than pretending it is a JSON scalar or pickle-byte hash.
"""
    def canonical(v):
        if isinstance(v,(x.torch.Tensor,np.ndarray,np.generic)):return x.r.training._canonical(v)
        if isinstance(v,dict):return {str(k):canonical(z) for k,z in v.items()}
        if isinstance(v,(tuple,list)):return [canonical(z) for z in v]
        if isinstance(v,set):return sorted((canonical(z) for z in v),key=lambda z:json.dumps(z,sort_keys=True))
        if v is None or isinstance(v,(str,int,float,bool)):return v
        if hasattr(v,'__dict__'):return dict(object_class=type(v).__module__+'.'+type(v).__qualname__,attributes=canonical(vars(v)))
        raise TypeError('unsupported archive state '+str(type(v)))
    return hashlib.sha256(json.dumps(canonical(value),sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def save(fig,name):
    fig.tight_layout();fig.savefig(PUBLIC/(name+'.png'),dpi=150);svg=PUBLIC/(name+'.svg');fig.savefig(svg)
    svg.write_text('\n'.join(line.rstrip() for line in svg.read_text(encoding='utf-8').splitlines())+'\n',encoding='utf-8');plt.close(fig)
def source_identity(reg):
    amendment=x.read(x.LOCAL/'host_save_amendment.json') if (x.LOCAL/'host_save_amendment.json').exists() else None
    storage=x.read(x.LOCAL/'storage_hold_amendment.json') if (x.LOCAL/'storage_hold_amendment.json').exists() else None
    effective=dict(reg['source_sha256'])
    if amendment:effective['tools/d1_overnight_rl_amount.py']=amendment['repaired_driver_sha256']
    if storage:effective['tools/d1_overnight_rl_amount.py']=storage['repaired_driver_sha256']
    return dict(contract_sha256=x.sha(PUBLIC/'execution_contract.json'),host_save_amendment_sha256=x.sha(PUBLIC/'host_save_amendment.json') if amendment else None,
        storage_hold_amendment_sha256=x.sha(PUBLIC/'storage_hold_amendment.json') if storage else None,
        sources={n:dict(original_registered_file_sha256=digest,executed_file_sha256=effective[n],canonical_lf_sha256=hashlib.sha256((x.ROOT/n).read_bytes().replace(b'\r\n',b'\n')).hexdigest()) for n,digest in reg['source_sha256'].items()})

def analysis_contract():
    reg=x.check();path=PUBLIC/'analysis_contract.json'
    contract=dict(task=x.TASK,registered_utc=datetime.now(timezone.utc).isoformat(),execution_contract_sha256=x.sha(x.LOCAL/'registration.json'),
        representative_condition=REPRESENTATIVE_CONDITION,representative_rule='first fresh confirmation arrival seed, sustained family, mean context; no outcome selection',
        repeated_seed_selection='all11/23/37 terminal512',confidence='descriptive paired arrival-seed clustered bootstrap across four fresh seeds; contexts are sensitivities, not independent repetitions',
        confidence_rng=92701,bootstrap_replicates=2000,adoption='original zero-epsilon all-condition gate unchanged; Pareto maps descriptive and not adoption relaxation')
    if path.exists():return x.read(path)
    x.write(path,contract);return contract

def run():
    reg=x.check();analysis=analysis_contract();result=x.read(x.LOCAL/'completion.json');assert result['status']=='completed'
    versions=dict(python='.'.join(map(str,x.sys.version_info[:3])),torch=str(x.torch.__version__),numpy=np.__version__,platform='Windows CPU',training_settings=reg['training_settings'])
    previous_versions=x.read(x.x.PUBLIC/'runtime_versions.json')
    if any(versions[k]!=previous_versions[k] for k in ('python','torch','numpy','training_settings')):raise ValueError('runtime/settings differ from original32 learner')
    x.write(PUBLIC/'runtime_versions.json',dict(versions,original32_versions_match=True,time_recorded='post-run unchanged installation, actual matching versions checked; runner source manifest has no independent package lock'))
    data=x.read(x.LOCAL/'inputs.json');rows=list(result['rows']);old=x.read(x.x.LOCAL/'completion.json')['rows']
    rows.extend(dict(q,scope='development',identity=f'dev_{q["policy"]}_{q["condition"]:02d}',reused_completed=True) for q in old if q['policy'].startswith('PPO'))
    for q in rows:
        if 'normal_planned' not in q:
            tickets=data['development'][q['condition']]['tickets'];q['normal_planned']=sum(t['priority']=='normal' for t in tickets);q['urgent_planned']=len(tickets)-q['normal_planned']
    table(PUBLIC/'comparison.csv',rows)
    old_ledger={q['identity']:q for q in x.x.Budget().rows};reused_verified=0
    for q in rows:
        if not q.get('reused_completed'):continue
        entry=old_ledger[q['identity']];path=x.x.LOCAL/'items'/(q['identity']+'.json.gz')
        if entry['status']!='completed' or x.sha(path)!=entry['sha256']:raise ValueError('reused prior native evidence changed')
        raw=x.x.read_raw(q['identity'])
        if any(q[k]!=v for k,v in raw['row'].items()):raise ValueError('reused completed metrics differ from durable artifact')
        reused_verified+=1
    summaries=[];roles=list(dict.fromkeys((q['scope'],q['policy']) for q in rows))
    for scope,role in roles:
        subset=[q for q in rows if q['scope']==scope and q['policy']==role];normal=sum(q['normal_planned'] for q in subset);failed=sum(q['normal_failure'] for q in subset)
        summaries.append(dict(scope=scope,policy=role,name_ko=label(role),conditions=len(subset),planned=sum(q['planned'] for q in subset),completed=sum(q['completed'] for q in subset),incomplete=sum(q['incomplete'] for q in subset),
            urgent_failure=sum(q['urgent_failure'] for q in subset),normal_failure=failed,normal_on_time_rate=(normal-failed)/normal,
            mean_urgent_p95_ms=statistics.mean(q['urgent_p95_ms'] for q in subset),mean_normal_ms=statistics.mean(q['normal_mean_ms'] for q in subset),
            mean_energy_j=statistics.mean(q['energy_j'] for q in subset),mean_peak_ap_c=statistics.mean(q['peak_ap_c'] for q in subset),native_seconds=sum(q['native_seconds'] for q in subset)))
    table(PUBLIC/'summary.csv',summaries)
    paired=[];controls=[];equivalence=[];alias_groups={};alias_inputs={};mask_count=0;planned_count=0;callback_seconds=0;native_seconds=0;learning=[];episode_logs=[]
    final=[q for q in rows if q['scope']=='confirmation'];by={(q['condition'],q['policy']):q for q in final}
    for q in final:
        if q['policy'] in ('Band','Triton','Rule'):continue
        for role in ('Band','Triton','Rule'):
            b=by[q['condition'],role];service_ok=q['planned']==q['completed']==b['completed']==b['planned'] and all(q[k]<=b[k] for k in ('incomplete','urgent_failure','normal_failure','urgent_p95_ms'))
            de=q['energy_j']-b['energy_j'];dt=q['peak_ap_c']-b['peak_ap_c']
            status='서비스 악화' if not service_ok else ('열·에너지 개선' if de<0 and dt<0 else '열 개선' if de==0 and dt<0 else '에너지 개선' if de<0 and dt==0 else '동일' if de==0 and dt==0 else '상충 또는 비용 악화')
            paired.append(dict(condition=q['condition'],arrival_seed=q['arrival_seed'],family=q['family'],context=q['context'],policy=q['policy'],baseline=role,service_nonworse=service_ok,classification_ko=status,
                delta_urgent_failure=q['urgent_failure']-b['urgent_failure'],delta_normal_failure=q['normal_failure']-b['normal_failure'],delta_urgent_p95_ms=q['urgent_p95_ms']-b['urgent_p95_ms'],delta_energy_j=de,delta_peak_ap_c=dt))
    table(PUBLIC/'paired_differences.csv',paired)
    for q in rows:
        raw=load(q);tickets=data['development' if q['scope']=='development' else 'confirmation'][q['condition']]['tickets'];x.x.previous.audit(raw['result'],tickets)
        ss=raw['snapshots'];mask_count+=len(ss)
        for s in ss:
            assert s['mask'][s['chosen']] and not np.any(np.asarray(s['mask'],bool)&~np.asarray(s['physical_mask'],bool))
        controls.append(dict(scope=q['scope'],condition=q['condition'],policy=q['policy'],snapshots=len(ss),multiple_admitted=sum(sum(s['mask'])>1 for s in ss),non_L0=sum(s['chosen']!=0 for s in ss),
            selected_cooling=sum(s['actions'][s['chosen']]['kind']=='cool_wait' for s in ss),selected_resource_wait=sum(s['actions'][s['chosen']]['kind']=='resource_wait' for s in ss),
            selected_single=sum(s['actions'][s['chosen']]['kind']=='single' for s in ss),selected_bundle=sum(s['actions'][s['chosen']]['kind']=='bundle' for s in ss),
            selected_slots=json.dumps([sum(s['chosen']==i for s in ss) for i in range(8)]),actual_extra_cooling_s=raw['total_extra_wait'],max_request_cooling_s=max(raw['request_wait'].values(),default=0),
            callback_count=len(raw['callback_seconds']),callback_total_s=sum(raw['callback_seconds']),callback_max_ms=max(raw['callback_seconds'],default=0)*1000,projection_calls=raw['projection_calls'],projection_seconds=raw['projection_seconds']))
        if q['scope']=='confirmation' and q['policy']=='Rule' and ss:
            first=ss[0];key=hashlib.sha256(json.dumps({k:first[k] for k in ('state','candidates','mask','physical_mask')},sort_keys=True,separators=(',',':')).encode()).hexdigest();alias_inputs[key]=first
            arrived=sorted([t for t in tickets if t['arrival_ns']<=first['now_ns']],key=lambda t:t['ordinal']);mapping={t['id']:f'known_{i}' for i,t in enumerate(arrived)}
            known=[dict((k,v) for k,v in t.items() if k!='id') for t in arrived]
            owners=[dict(task=t['task'],backend=t['backend'],arrival_ns=t['arrival_ns'],dispatch_ns=t['dispatch_ns']) for t in raw['result']['ledger'] if t.get('dispatch_ns',1e30)<first['now_ns']<t.get('lane_available_ns',-1)]
            actions=[dict(kind=a['kind'],until_ns=a.get('until_ns'),jobs=[dict(request=mapping.get(j['request_id'],'owned_or_unknown'),backend=j['backend']) for j in a.get('jobs',[])]) for a in first['actions']]
            public=dict(now_ns=first['now_ns'],known_requests=known,owners_before_first_decision=owners,derived_risk=first['risk'],normalized_actions=actions)
            alias_groups.setdefault(key,[]).append(dict(condition=q['condition'],arrival_seed=q['arrival_seed'],family=q['family'],context=q['context'],first_rule_action_kind=first['actions'][first['chosen']]['kind'],
                normalized_public_state_and_action_sha256=hashlib.sha256(json.dumps(public,sort_keys=True,separators=(',',':')).encode()).hexdigest(),raw_request_ids_differ=True))
        if q['policy'].startswith('PPO'):
            comparison={z['policy']:z for z in rows if z['scope']==q['scope'] and z['condition']==q['condition'] and z['policy'] in ('Band','L0','Rule')}
            equivalence.append(dict(scope=q['scope'],condition=q['condition'],policy=q['policy'],same_Band=schedule(raw)==schedule(load(comparison['Band'])),same_L0=schedule(raw)==schedule(load(comparison['L0'])),same_Rule=schedule(raw)==schedule(load(comparison['Rule']))))
    table(PUBLIC/'decisions.csv',controls);table(PUBLIC/'schedule_equivalence.csv',equivalence)
    added_failures=[]
    for seed in x.SEEDS:
        for case in data['confirmation']:
            i=case['condition'];target=load(by[i,f'PPO{seed}_512']);band=load(by[i,'Band']);removed=next(q for q in rows if q['scope']=='no_wait' and q['policy']==f'NoWait{seed}' and q['condition']==i);no_wait=load(removed)
            bjobs={q['id']:q for q in band['result']['ledger']};njobs={q['id']:q for q in no_wait['result']['ledger']}
            differences=[(q,bjobs[q['id']]) for q in target['result']['ledger'] if (q.get('backend'),q.get('dispatch_ns'))!=(bjobs[q['id']].get('backend'),bjobs[q['id']].get('dispatch_ns'))]
            first=min(differences,key=lambda z:min(z[0].get('dispatch_ns',1e30),z[1].get('dispatch_ns',1e30))) if differences else None
            for q in target['result']['ledger']:
                b=bjobs[q['id']]
                if q['priority']!='normal' or not q['late_success'] or b['late_success']:continue
                added_failures.append(dict(seed=seed,condition=i,family=case['family'],context=case['context'],request_id=q['id'],arrival_s=q['arrival_ns']/1e9,
                    Band_response_ms=b['response_ns']/1e6,PPO_response_ms=q['response_ns']/1e6,NoWait_response_ms=njobs[q['id']]['response_ns']/1e6,still_late_without_both_wait_types=njobs[q['id']]['late_success'],
                    first_different_request_id=first[0]['id'] if first else None,first_different_task=first[0]['task'] if first else None,
                    first_Band_backend=first[1].get('backend') if first else None,first_PPO_backend=first[0].get('backend') if first else None,
                    first_Band_dispatch_s=first[1].get('dispatch_ns',0)/1e9 if first else None,first_PPO_dispatch_s=first[0].get('dispatch_ns',0)/1e9 if first else None,
                    causal_scope='retrospective earliest dispatch divergence and joint-NoWait diagnostic, not proof of the sole cause'))
    table(PUBLIC/'added_service_failures.csv',added_failures)
    aliases=[]
    for key,v in alias_groups.items():
        if len({q['family'] for q in v})<2:continue
        first=alias_inputs[key];selection=[]
        for seed in x.SEEDS:
            network=x.load_learner(seed,x.LOCAL/'checkpoints'/f'seed{seed}_ep512.pt').network
            with x.torch.no_grad():distribution,_=network(x.torch.tensor(first['state'],dtype=x.torch.float32)[None],x.torch.tensor(first['candidates'],dtype=x.torch.float32)[None],x.torch.tensor(first['mask'],dtype=x.torch.bool)[None])
            scores=distribution.logits[0].numpy();chosen=0 if scores[0]==scores.max() else int(scores.argmax());actual=[]
            for item in v:
                raw=load(by[item['condition'],f'PPO{seed}_512']);s=raw['snapshots'][0]
                same=all(s[field]==first[field] for field in ('state','candidates','mask','physical_mask'))
                if not same or s['chosen']!=chosen:raise ValueError('initial alias/network actual choice mismatch')
                actual.append(dict(condition=item['condition'],chosen=s['chosen'],action_kind=s['actions'][s['chosen']]['kind']))
            selection.append(dict(seed=seed,deterministic_selected_slot=chosen,action_kind=first['actions'][chosen]['kind'],actual_first_choices=actual,physical_and_admitted=True))
        aliases.append(dict(full_policy_tensor_and_masks_sha256=key,states=v,normalized_public_state_and_actions_identical=len({q['normalized_public_state_and_action_sha256'] for q in v})==1,deterministic_terminal_selections=selection))
    x.write(PUBLIC/'initial_input_aliases.json',dict(groups=aliases,
        scope='first actual encoder state+candidate+mask+physical_mask; pre-decision public requests/owners/actions normalized only for trace-specific request IDs',
        interpretation='matching initial inputs can hide different unseen arrivals. More training cannot reveal absent future information, but can learn expected risk; no claim of globally impossible POMDP/RL improvement',new_native=0))
    # Inspect every newly consumed native result, including all actual training.
    native_budget=x.Budget()
    for v in native_budget.rows:
        assert v['status']=='completed';path=x.LOCAL/'items'/(v['identity']+'.json.gz');assert x.sha(path)==v['sha256'];raw=x.read_raw(v['identity']);x.x.previous.audit(raw['result'],v['case']['tickets'])
        planned_count+=raw['row']['planned'];assert raw['row']['completed']==raw['row']['planned'];callback_seconds+=sum(raw['callback_seconds']);native_seconds+=raw['row']['native_seconds']
    for seed in x.SEEDS:
        learner=x.read(x.LOCAL/f'learning_{seed}.json')
        for q in learner['updates']:
            learning.append(dict(seed=seed,episodes=q['accepted_episodes'],update=q['update'],frames=q['frames'],sampled_choices=q['sampled_choices'],lambda_J=q['lambda_after'][0],lambda_urgent_misses=q['lambda_after'][1],lambda_normal_misses=q['lambda_after'][2],lambda_urgent_p95=q['lambda_after'][3],lambda_completion=q['lambda_after'][4],direct_energy_max=q['direct_energy_max'],actor_gradient_max=max(v['gradients']['actor'] for v in q['steps']),critic_gradient_max=max(v['gradients']['critic'] for v in q['steps']),
                weighted_minibatch_entropy_mean=statistics.mean(v['entropy'] for v in q['steps']),combined_component_means=json.dumps(q['combined_component_means']),optimizer_steps=q['optimizer_steps_cumulative'],seconds=q['seconds'],early_stop=q['early_stop']))
        for q in learner['episodes']:episode_logs.append(dict(seed=seed,episode=q['number'],sampled_choices=q['sampled_choices'],frames=q['frames'],costs=json.dumps(q['costs']),**q['row']))
    table(PUBLIC/'learning_updates.csv',learning);table(PUBLIC/'learning_episodes.csv',episode_logs)
    grouped=[];intervals=[];rng=np.random.default_rng(analysis['confidence_rng'])
    for policy in ('PPO11_512','PPO23_512','PPO37_512'):
        for baseline in ('Band','Triton','Rule'):
            subset=[q for q in paired if q['policy']==policy and q['baseline']==baseline]
            for family in ('low','queue','burst','sustained'):
                s=[q for q in subset if q['family']==family]
                grouped.append(dict(policy=policy,baseline=baseline,family=family,conditions=len(s),service_losses=sum(not q['service_nonworse'] for q in s),mean_delta_energy_j=statistics.mean(q['delta_energy_j'] for q in s),mean_delta_peak_ap_c=statistics.mean(q['delta_peak_ap_c'] for q in s),mean_delta_urgent_p95_ms=statistics.mean(q['delta_urgent_p95_ms'] for q in s),added_normal_failures=sum(q['delta_normal_failure'] for q in s)))
            for metric in ('delta_energy_j','delta_peak_ap_c','delta_urgent_p95_ms'):
                vals=np.array([statistics.mean(q[metric] for q in subset if q['arrival_seed']==seed) for seed in x.FINAL_SEEDS]);resample=rng.choice(vals,(2000,len(vals)),replace=True).mean(1)
                intervals.append(dict(policy=policy,baseline=baseline,metric=metric,independent_arrival_seeds=4,mean=float(vals.mean()),low95=float(np.quantile(resample,.025)),high95=float(np.quantile(resample,.975)),interpretation='descriptive four-seed clustered bootstrap; not physical-confidence or independent48 trials'))
    table(PUBLIC/'family_differences.csv',grouped);table(PUBLIC/'descriptive_intervals.csv',intervals)
    plt.rcParams['font.family']='Malgun Gothic';plt.rcParams['axes.unicode_minus']=False
    fig,axes=plt.subplots(2,2,figsize=(11,7))
    for seed in x.SEEDS:
        s=sorted([q for q in summaries if q['scope']=='development' and q['policy'].startswith(f'PPO{seed}_')],key=lambda q:int(q['policy'].split('_')[1]));eps=[int(q['policy'].split('_')[1]) for q in s]
        for ax,key,name in zip(axes.flat,('normal_failure','mean_urgent_p95_ms','mean_energy_j','mean_peak_ap_c'),('일반 기한 실패(건)','긴급 P95 평균(ms)','전체 에너지 평균(J)','최고 AP 평균(°C)')):
            ax.plot(eps,[q[key] for q in s],marker='o',label=f'seed {seed}');ax.set_title(name);ax.set_xlabel('누적 학습 에피소드');ax.grid(alpha=.2)
    axes[0,0].legend();fig.suptitle('같은 PPO learner의 학습량 비교 · 개발24조건');save(fig,'01_learning_amount')
    ff=[q for q in summaries if q['scope']=='confirmation'];fig,axes=plt.subplots(2,2,figsize=(12,8));labs=[label(q['policy']) for q in ff]
    for ax,key,name in zip(axes.flat,('normal_failure','mean_urgent_p95_ms','mean_energy_j','mean_peak_ap_c'),('일반 기한 실패(건)','긴급 P95 평균(ms)','전체 에너지 평균(J)','최고 AP 평균(°C)')):
        ax.bar(range(len(ff)),[q[key] for q in ff]);ax.set_xticks(range(len(ff)),labs,rotation=35,ha='right');ax.set_title(name);ax.grid(axis='y',alpha=.2)
    fig.suptitle('새 확인48조건 · 세 seed 모두 평가');save(fig,'02_final_kpi')
    fig,axes=plt.subplots(3,1,figsize=(12,8));symbols={'서비스 악화':0,'상충 또는 비용 악화':1,'동일':2,'에너지 개선':3,'열 개선':4,'열·에너지 개선':5}
    for ax,policy in zip(axes,('PPO11_512','PPO23_512','PPO37_512')):
        vals=np.array([[symbols[next(q['classification_ko'] for q in paired if q['policy']==policy and q['baseline']==role and q['condition']==i)] for i in range(48)] for role in ('Band','Triton','Rule')]);ax.imshow(vals,aspect='auto',vmin=0,vmax=5,cmap='viridis');ax.set_yticks(range(3),('Band','Triton','같은 후보 Rule'));ax.set_title(label(policy));ax.set_xlabel('확인 조건0..47')
    fig.suptitle('조건별 지도: 0서비스악화 /1상충·비용악화 /2동일 /3에너지 /4열 /5공동개선');save(fig,'03_condition_map')
    fig,axes=plt.subplots(2,1,figsize=(12,7));rep=[]
    for offset,role in enumerate(('Band','Rule','PPO11_512','PPO23_512','PPO37_512')):
        q=by[REPRESENTATIVE_CONDITION,role];raw=load(q)
        for ticket in raw['result']['ledger']:
            if 'dispatch_ns' not in ticket:continue
            a=ticket['dispatch_ns']/1e9;b=ticket['lane_available_ns']/1e9;y=offset*3+(0 if ticket['backend']=='CPU' else 1);axes[0].broken_barh([(a,b-a)],(y,.8),facecolors='#166ca5' if ticket['task']=='classification' else '#ef8c27')
            rep.append(dict(policy=role,request_id=ticket['id'],task=ticket['task'],backend=ticket['backend'],arrival_s=ticket['arrival_ns']/1e9,dispatch_s=a,available_s=b,response_ms=ticket['response_ns']/1e6,late=ticket['late_success']))
        axes[1].plot([z[0] for z in raw['curve']],[z[1] for z in raw['curve']],label=label(role))
    axes[0].set_xlim(35,55);axes[0].set_yticks([i*3+.8 for i in range(5)],[label(z) for z in ('Band','Rule','PPO11_512','PPO23_512','PPO37_512')]);axes[0].set_title('실행 시간표 · 각정책 CPU/GPU 두줄');axes[0].set_xlabel('시간(s)');axes[1].set_ylabel('모형 AP(°C)');axes[1].set_xlabel('시간(s)');axes[1].legend(fontsize=8);fig.suptitle('사전 고정 대표: 첫 확인seed · 지속 부하 · mean');save(fig,'04_schedule_ap');table(PUBLIC/'representative_schedule.csv',rep)
    fig,axes=plt.subplots(1,2,figsize=(11,4))
    for seed in x.SEEDS:
        s=[q for q in learning if q['seed']==seed];axes[0].plot([q['episodes'] for q in s],[q['lambda_J'] for q in s],label=f'seed {seed}');axes[1].plot([q['episodes'] for q in s],[q['sampled_choices'] for q in s],label=f'seed {seed}')
    axes[0].set_title('에너지 승수 λJ');axes[1].set_title('8에피소드 update의 실제 표본 선택 수')
    for ax in axes:ax.set_xlabel('누적 학습 에피소드');ax.legend();ax.grid(alpha=.2)
    save(fig,'05_learning_activity')
    inventory=x.read(x.LOCAL/'checkpoint_inventory.json');lineage=x.read(x.LOCAL/'lineage_verification.json');x.write(PUBLIC/'checkpoint_inventory.json',inventory);x.write(PUBLIC/'lineage_verification.json',lineage)
    diagnostics=[];roundtrips=[]
    for seed in x.SEEDS:
        original=x.torch.load(x.x.LOCAL/'checkpoints'/f'seed{seed}_ep32.pt',map_location='cpu',weights_only=False)
        restored=x.load_learner(seed).snapshot();same32={k:payload_digest(original[k])==payload_digest(restored[k]) for k in original}
        if not all(same32.values()):raise ValueError('extended original32 restore mismatch')
        roundtrips.append(dict(seed=seed,episodes=32,status='PASS',all_payload_fields_exact=same32,actual_additional_learning=0))
        for ep in x.TARGETS:
            z=x.torch.load(x.LOCAL/'checkpoints'/f'seed{seed}_ep{ep}.pt',map_location='cpu',weights_only=False);actor=lambda value:{k:v for k,v in value.items() if k.startswith('actor.')};s=[q for q in controls if q['scope']=='development' and q['policy']==f'PPO{seed}_{ep}'];steps=[float(v['step']) for v in z['optimizer']['state'].values()]
            restored=x.load_learner(seed,x.LOCAL/'checkpoints'/f'seed{seed}_ep{ep}.pt').snapshot();same={k:payload_digest(z[k])==payload_digest(restored[k]) for k in z}
            if not all(same.values()):raise ValueError('terminal checkpoint load snapshot mismatch')
            roundtrips.append(dict(seed=seed,episodes=ep,status='PASS',all_payload_fields_exact=same,actual_additional_learning=0))
            diagnostics.append(dict(seed=seed,episodes=ep,update_count=z['update_count'],optimizer_steps=z['optimizer_steps'],Adam_parameter_step_min=min(steps),Adam_parameter_step_max=max(steps),
                actor_weights_changed_from_terminal32=x.r.training.state_digest(actor(original['network']))!=x.r.training.state_digest(actor(z['network'])),network_changed_from32=x.r.training.state_digest(original['network'])!=x.r.training.state_digest(z['network']),
                lambda_J=float(z['multipliers'][0]),development_multiple_choice_events=sum(q['multiple_admitted'] for q in s),development_non_L0_choices=sum(q['non_L0'] for q in s),development_selected_cooling=sum(q['selected_cooling'] for q in s),development_selected_resource_wait=sum(q['selected_resource_wait'] for q in s),
                explanation='same fixed development24; training episodes use different registered traces, reward alone is not KPI improvement'))
    x.write(PUBLIC/'training_diagnostics.json',diagnostics)
    x.write(PUBLIC/'checkpoint_roundtrip.json',dict(status='PASS',archives=roundtrips,new_environment_starts=0,new_learning_starts=0,
        limitation='complete learner payload load/snapshot identity only; no new actual terminal512 training replay. Prior same-source pilot real4-episode replay remains separate evidence'))
    x.write(PUBLIC/'source_identity.json',source_identity(reg))
    x.write(PUBLIC/'policy_definitions.json',dict(schema_id=x.r.SCHEMA,
        L0=dict(policy_id=x.r.L0,controller='tools.d1_rolling_list_rl.Controller mode=L0',reference_and_fallback=True),
        Rule=dict(policy_id=x.r.RULE,controller='tools.d1_rolling_list_rl.Controller mode=RULE',same_input_candidates_masks=True),
        PPO=dict(policy_id=x.r.PPO,controller='tools.d1_rolling_list_rl.Controller mode=PPO',algorithm='native PyTorch masked PPO, same settings and learner',learning_seeds=list(x.SEEDS),terminal_episode_counts=list(x.TARGETS)),
        Band=dict(policy_id=x.h.prior.external.BAND,scope='whole-request limited adaptation, not original Band subgraph runtime'),
        Triton=dict(policy_id=x.h.prior.triton.OFF,scope='request scheduling adaptation with CPU/GPU resources, not actual Triton server'),
        engine_record_note='controller ABI retains inherited execution adapter identity; report role/policy_id and frozen schema identify the actual selection rule'))
    x.write(PUBLIC/'input_plan.json',dict(inputs_sha256=reg['inputs_sha256'],training_seeds=list(x.TRAIN_SEEDS),confirmation_seeds=list(x.FINAL_SEEDS),
        generator='tools.d1_rolling_list_rl_run.cases; train=True for common480; train=False for confirmation48',development_cases='docs/results/rolling_list_rl_pilot_08/cases.json development',initial='docs/results/rolling_hybrid_pilot_07/thermal_equivalence_fixture.json initial',raw_train_trace_shared=False))
    verification=dict(status='PASS',checked_utc=datetime.now(timezone.utc).isoformat(),registered_head=reg['head'],uncommitted_own_driver_at_run=True,
        learner_policy_source_closure_unchanged=True,host_only_driver_save_amendment_recorded=(x.LOCAL/'host_save_amendment.json').exists(),host_save_failures_preserved=native_budget.used()['host_save_failures_preserved'],
        storage_hold_recorded=(x.LOCAL/'storage_hold_amendment.json').exists(),clock_and_caps_reset=False,
        all_new_native_artifact_hashes_and_phase_lane_audits=True,new_native=len(native_budget.rows),new_learning=native_budget.used()['learning_starts'],all_new_scheduled_requests=planned_count,all_new_completed_requests=planned_count,
        report_rows=len(rows),mask_snapshots_checked=mask_count,original_terminal32_exact_restore=lineage['status'],terminal_archive_inventory=inventory['status'],
        actual_native_seconds=native_seconds,actual_PC_callback_seconds=callback_seconds,new_PPO_update_seconds=sum(q['seconds'] for q in learning if q['episodes']>32),
        reused_prior_native_artifacts_sha_verified=reused_verified,reused_evaluations_charged_new_native=0,
        elapsed_wall_clock_seconds=(x.LOCAL/'completion.json').stat().st_mtime-datetime.fromisoformat(reg['registered_utc']).timestamp(),phone_callback_energy_supported=False,device_commands=0,model_fit_calls=0,experiment_ready=False)
    x.write(PUBLIC/'verification.json',verification);x.write(PUBLIC/'result.json',dict(summary=summaries,confirmation_gates=result['confirmation_gates'],development_gates=result['development_gates'],consumption=result['consumption'],verification=verification,methodology='same learner extension; old32 preserved/new nested480 common cases; no claim of convergence'))
    finaltable=''.join(f"<tr><td>{html.escape(q['name_ko'])}</td><td>{q['normal_failure']}</td><td>{q['mean_urgent_p95_ms']:.3f}</td><td>{q['mean_energy_j']:.6f}</td><td>{q['mean_peak_ap_c']:.6f}</td></tr>" for q in ff)
    page=f'''<!doctype html><html lang="ko"><meta charset="utf-8"><title>PPO 학습량 비교</title><style>body{{max-width:1200px;margin:30px auto;font:17px Arial;background:#f5f7fb;color:#132238}}section{{background:white;padding:25px;margin:18px 0;border-radius:12px}}table{{border-collapse:collapse;width:100%}}td,th{{border-bottom:1px solid #d9e2f1;padding:12px;text-align:left}}img{{max-width:100%}}a{{color:#0963b5}}</style><h1>같은 PPO를 더 학습하면 달라지는가?</h1><p>3seed · terminal32→64→128→256→512 · 추가학습1440 · 새확인48조건. 최고seed선택0·기기실행0.</p><section><h2>새 확인 결과</h2><table><tr><th>정책</th><th>일반기한실패</th><th>긴급P95 평균ms</th><th>평균J</th><th>평균최고AP°C</th></tr>{finaltable}</table><p>전체 요청을 완료했는지 먼저 확인하고 비용을 해석한다. 반올림 표가 같은 것도 조건별 exact 차이는 CSV에서 확인한다.</p></section>'''
    for name in ('01_learning_amount','02_final_kpi','03_condition_map','04_schedule_ap','05_learning_activity'):page+=f'<section><img src="{name}.png" alt="{name}"></section>'
    page+='<section><h2>판정 범위</h2><p>기존 all-condition zero-epsilon 기준은 유지했다. 부하별/Pareto 표는 새 해석 자료이며 채택기준 완화가 아니다. AP는 기기 내부 추정 채널이고 최고 표면온도가 아니다. 냉각에 따른 처리속도 회복은 모델링되지 않는다. 작은 J/AP 차이를 실제 휴대폰 절감으로 확정하지 않는다.</p><p><a href="comparison.csv">전체 비교 CSV</a> · <a href="paired_differences.csv">대응 차이</a> · <a href="learning_updates.csv">학습 update</a> · <a href="checkpoint_inventory.json">상태 보존</a> · <a href="verification.json">검증</a></p></section></html>'
    (PUBLIC/'index.html').write_text(page,encoding='utf-8')
    print(json.dumps(dict(summary=ff,gates={k:dict(promising=v['promising'],maintenance=v['maintenance_pass']) for k,v in result['confirmation_gates'].items()},verification=verification,consumption=result['consumption']),ensure_ascii=False,indent=2))

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('command',choices=('prepare_analysis','report'));args=p.parse_args()
    if args.command=='prepare_analysis':print(json.dumps(analysis_contract()))
    else:run()
