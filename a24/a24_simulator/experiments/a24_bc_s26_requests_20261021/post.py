"""Saved-only audit and diagnostic analysis; never runs a simulator or a fit."""
import collections,hashlib,json,math,sys
from pathlib import Path
import study as S
H,R,O=S.H,S.R,S.O
read,new,pin,verify=S.read,S.new,S.pin,S.verify

def numpy_logits(net,x,mask):
    np=S.P.np
    w={k:v.detach().numpy().astype(np.float64) for k,v in net.state_dict().items()}
    def linear(a,name):return a@w[name+'.weight'].T+w[name+'.bias']
    e=np.tanh(linear(np.asarray(x,np.float64),'encode.0'));m=np.asarray(mask,bool)
    ctx=np.concatenate(((e*m[:,:,None]).sum(1)/m.sum(1)[:,None],np.where(m[:,:,None],e,-1e9).max(1)),axis=-1)
    z=linear(np.tanh(linear(np.concatenate((e,np.broadcast_to(ctx[:,None],(len(e),36,96))),axis=-1),'actor.0')),'actor.2').squeeze(-1)
    return np.where(m,z,-1e9)

def audit():
    np,torch=S.P.np,S.P.torch
    op=read(H/'OPERATION.json');verify(op['source_pins']);result=read(O/'RESULT.json')
    supplement=read(H/'SUPPLEMENTAL_SOURCES.json');verify(supplement['pins'])
    starts=[json.loads(v) for v in (O/'receipts.jsonl').read_text(encoding='utf8').splitlines() if json.loads(v)['event']=='START']
    import datetime
    assert datetime.datetime.fromisoformat(supplement['utc'].replace('Z','+00:00'))<min(datetime.datetime.fromisoformat(v['utc']) for v in starts)
    state=S.loadpt(S.CHECKPOINT);net=S.Learner(state=state);before=net.snapshot()
    assert state['network_sha256']==S.NETWORK and result['network_sha256']==S.NETWORK
    inputs=read(H/'INPUTS.json')['cases'];lookup={x['case']['id']:x for x in inputs}
    binding=replay=nn=ties=0;maxregret=0.;coverage={}
    for row in result['rows']:
        verify([row['raw']])
        if row['status']!='COMPLETE':continue
        item=lookup[row['case']];source=read(R/item['source_common_bank']['path']);bank=read(R/item['bank']['path']);d=read(R/row['raw']['path'])
        assert len(d['result']['requests'])==len(source['requests'])==len(bank['jobs'])
        arrivals=collections.Counter(q['scheduled_arrival_ns'] for q in bank['jobs'])
        assert max(arrivals.values())==(8 if row['condition']['pattern']=='burst' else 1)
        assert sorted(set(arrivals.values()))==([8] if row['condition']['pattern']=='burst' else [1])
        times=sorted(arrivals);expected_gap=round((8 if row['condition']['pattern']=='burst' else 1)/row['condition']['requests_per_second']*1e9)
        assert all(b-a==expected_gap for a,b in zip(times,times[1:]))
        for q,b,src in zip(d['result']['requests'],bank['jobs'],source['requests']):
            assert q['request_id']==src['id']==b['request_id'] and q['task']==src['task'] and q['priority']==src['priority']
            assert q['scheduled_arrival_ns']==round(src['arrival_s']*1e9) and q['deadline_ns']==round(src['deadline_s']*1e9) and q['queue_entry_ns']==round(src['ready_s']*1e9)
            if q['route'] is not None:assert q['timing']['stages_ns']==[round(x*1e9) for x in src['private_work'][q['route']]]
            binding+=1
        states=[v['public_state'] for v in d['result']['decisions']]
        assert len(states)==len(d['calls'])
        drain=round(item['case']['drain_stop_s']*1e9)
        assert row['metrics']['response_missing']==sum(q['response_ns'] is None or q['response_ns']>drain for q in d['result']['requests'])
        assert row['metrics']['incomplete']==sum(q['available_ns'] is None or q['available_ns']>drain for q in d['result']['requests'])
        if row['policy'].endswith('_DYN'):
            actor=S.DynamicPolicy(S.P.Nominal(bank['nominal_vectors']),S.P.physics(),row['policy'])
            for s,c in zip(states,d['calls']):assert actor(s)==c['action'];replay+=1
        if row['policy']=='BC_RECOVERED':
            for start in range(0,len(d['calls']),128):
                part=d['calls'][start:start+128];x=np.asarray([v['x'] for v in part],np.float32);m=np.asarray([v['mask'] for v in part],bool)
                with torch.no_grad():pred=net.net(torch.from_numpy(x),torch.from_numpy(m))[0].argmax(-1).numpy()
                logits=numpy_logits(net.net,x,m)
                for i,c in enumerate(part):
                    assert c['mask'][c['chosen']] and int(pred[i])==c['chosen']
                    regret=float(logits[i].max()-logits[i,c['chosen']]);maxregret=max(maxregret,regret);assert regret<2e-6
                    nn+=1;ties+=int(logits[i].argmax()!=c['chosen'])
        coverage[row['label']]=dict(states=len(states),min_temperature_C=min(s['sensor']['temperature_c'] for s in states),max_temperature_C=max(s['sensor']['temperature_c'] for s in states),max_queue=max(len(s['queue']) for s in states))
        print('PY_SAVED_AUDIT',row['label'],flush=True)
    S.equal(net.snapshot(),before);S.equal(S.loadpt(S.CHECKPOINT),state);verify(op['source_pins']);verify([op['checkpoint']])
    new(O/'AUDIT_PY.json',dict(status='PASS',source_request_bindings=binding,baseline_replayed_decisions=replay,NN_frames=nn,
        Float64_argmax_max_regret=maxregret,Float64_rounding_ties=ties,all_checkpoint_optimizer_RNG_unchanged=True,coverage=coverage,new_environment=0,new_fit=0))

def describe(values):
    v=sorted(values)
    return dict(n=len(v),mean=sum(v)/len(v) if v else None,P95=v[max(0,math.ceil(.95*len(v))-1)] if v else None,max=max(v) if v else None)

def analysis():
    result=read(O/'RESULT.json');accounting=read(O/'ACCOUNTING.json');train=read(S.P.O/'TRAIN_DIAGNOSTICS.json')
    traincov=train['selected_TRAIN_coverage'];diagnostics=[]
    for row in result['rows']:
        if row['status']!='COMPLETE':continue
        d=read(R/row['raw']['path']);requests=d['result']['requests'];states=d['result']['decisions'];calls=d['calls']
        groups={}
        item=next(x for x in read(H/'INPUTS.json')['cases'] if x['case']['id']==row['case']);bank=read(R/item['bank']['path'])
        jobs_by_id={q['request_id']:q for q in bank['jobs']}
        for task in ('C','D'):
            for priority in ('U','N'):
                jobs=[q for q in requests if q['task']==task and q['priority']==priority]
                answered=[q for q in jobs if q['response_ns'] is not None and q['response_ns']<=round(d['case']['drain_stop_s']*1e9)]
                late=[q for q in answered if q['response_ns']>q['deadline_ns']]
                stages=lambda q,route:sum(jobs_by_id[q['request_id']]['routes'][route]['stages_ns'][:2 if task=='C' else 3])
                mechanism=collections.Counter()
                for q in late:
                    if q['queue_entry_ns']+min(stages(q,r) for r in ('CPU','GPU'))>q['deadline_ns']:
                        mechanism['entry_plus_fastest_solo_work_already_late']+=1
                    elif q['dispatch_ns']+stages(q,q['route'])>q['deadline_ns']:
                        mechanism['dispatch_plus_chosen_solo_work_already_late']+=1
                    else:mechanism['late_only_after_progress_slowdown']+=1
                groups[task+'_'+priority]=dict(n=len(jobs),on=sum(q['response_ns']<=q['deadline_ns'] for q in answered),
                    missing=len(jobs)-len(answered),incomplete=sum(q['available_ns'] is None or q['available_ns']>round(d['case']['drain_stop_s']*1e9) for q in jobs),
                    responses_after_drain=sum(q['response_ns'] is not None and q['response_ns']>round(d['case']['drain_stop_s']*1e9) for q in jobs),
                    dispatched_after_deadline=sum(q['dispatch_ns'] is not None and q['dispatch_ns']>q['deadline_ns'] for q in jobs),
                    admission_s=describe([(q['queue_entry_ns']-q['scheduled_arrival_ns'])/1e9 for q in jobs]),
                    ready_to_dispatch_s=describe([(q['dispatch_ns']-q['queue_entry_ns'])/1e9 for q in jobs if q['dispatch_ns'] is not None]),
                    dispatch_to_response_s=describe([(q['response_ns']-q['dispatch_ns'])/1e9 for q in answered]),
                    response_s=describe([(q['response_ns']-q['scheduled_arrival_ns'])/1e9 for q in answered]),
                    lateness_s=describe([max(0,(q['response_ns']-q['deadline_ns'])/1e9) for q in answered]),late_path_partition=dict(mechanism),
                    late_path_partition_scope='Saved work lower bounds and realized timestamps; not proof of an alternative feasible schedule')
        actions=collections.Counter(v['action']['kind'] for v in states);route_counts=collections.Counter(q['task']+'_'+str(q['route']) for q in requests)
        neural=dict(calls=0,teacher_exact=0,teacher_compatible=0,WAIT_when_teacher_dispatch=0,dispatch_when_teacher_WAIT=0,
            idle_WAIT=0,idle_WAIT_when_teacher_dispatch=0,forecast_horizon_reduced=0,queue_over8=0,queue_over32=0,
            outside_TRAIN_temperature=0,outside_TRAIN_queue=0,normal_dispatch_with_urgent_ready=0,
            urgent_omitted_from_candidates=0,max_consecutive_WAIT=0)
        regrets=[];streak=0;cost_differences={};per_group=collections.defaultdict(lambda:dict(n=0,compatible=0))
        for dec,c in zip(states,calls):
            s=dec['public_state'];q={x['request_id']:x for x in s['queue']};action=dec['action']
            if action['kind']=='DISPATCH' and q[action['request_id']]['priority']=='N' and any(x['priority']=='U' for x in q.values()):neural['normal_dispatch_with_urgent_ready']+=1
            if row['policy'] not in ('TEACHER','BC_RECOVERED'):continue
            allowed=[i for i,v in enumerate(c['mask']) if v];teacher=min(allowed,key=lambda k:(c['forecast_scores'][k],k));index=c['chosen'];ta=c['actions'][teacher]
            compat=S.P.compatible_targets(s,c['actions'],teacher)
            neural['calls']+=1;neural['teacher_exact']+=index==teacher;neural['teacher_compatible']+=bool(compat[index])
            neural['WAIT_when_teacher_dispatch']+=action['kind']!='DISPATCH' and ta['kind']=='DISPATCH'
            neural['dispatch_when_teacher_WAIT']+=action['kind']=='DISPATCH' and ta['kind']!='DISPATCH'
            neural['idle_WAIT']+=not s['owners'] and action['kind']=='WAIT'
            neural['idle_WAIT_when_teacher_dispatch']+=not s['owners'] and action['kind']=='WAIT' and ta['kind']=='DISPATCH'
            neural['forecast_horizon_reduced']+=bool(c['forecasts'][0]['horizon_reduced'])
            neural['queue_over8']+=len(q)>8;neural['queue_over32']+=len(q)>32
            neural['outside_TRAIN_temperature']+=not traincov['min_temperature_C']-1e-6<=s['sensor']['temperature_c']<=traincov['max_temperature_C']+1e-6
            neural['outside_TRAIN_queue']+=len(q)>traincov['max_queue']
            candidates={a['request_id'] for a in c['actions'] if a['kind']=='DISPATCH'}
            neural['urgent_omitted_from_candidates']+=any(v['priority']=='U' and rid not in candidates for rid,v in q.items())
            streak=streak+1 if action['kind']!='DISPATCH' else 0;neural['max_consecutive_WAIT']=max(neural['max_consecutive_WAIT'],streak)
            regrets.append(c['forecast_scores'][index]-c['forecast_scores'][teacher])
            group=ta['kind'] if ta['kind']!='DISPATCH' else q[ta['request_id']]['task']+'_'+ta['route']
            per_group[group]['n']+=1;per_group[group]['compatible']+=bool(compat[index])
            key=ta['kind']+'->'+action['kind'];cost_differences[key]=cost_differences.get(key,0)+1
        # Serialized latent work and nominal phases are both unchanged; this is a descriptive diagnostic.
        ratios={}
        for task in ('C','D'):
            for device in ('CPU','GPU'):
                v=[q for q in bank['jobs'] if q['task']==task]
                ratios[task+'_'+device]=describe([q['routes'][device]['stages_ns'][1]/1e9/bank['nominal_vectors'][q['request_id']+'|'+device][1] for q in v])
        trace=d['result']['trace'];duration=sum(t['dt'] for t in trace if t['start_ns']<635e9)
        losses=collections.defaultdict(lambda:dict(thermal_s=0.,contention_s=0.,total_s=0.))
        config=d['result']['config']
        for t in trace:
            ncpu=sum(v['route']=='CPU' and v['stage']==1 for v in t['active'])
            for v in t['active']:
                if v['stage']!=1:continue
                route=v['route'];slope=config['cpu_slope'] if route=='CPU' else config['gpu_slope']
                f=max(config['minimum_speed'],1/(1+config['strength']*slope*max(0,t['state']['temperature_c']-config['onset_c'])))
                contention=1+.25*max(0,ncpu-1) if route=='CPU' else 1.
                loss=losses[v['request_id']]
                loss['thermal_s']+=t['dt']*(1-f)
                loss['contention_s']+=t['dt']*f*(1-1/contention)
                loss['total_s']+=t['dt']*(1-t['speeds'][v['request_id']])
        for loss in losses.values():assert abs(loss['thermal_s']+loss['contention_s']-loss['total_s'])<1e-8
        for key,g in groups.items():
            task,priority=key.split('_');answered=[q for q in requests if q['task']==task and q['priority']==priority and q['response_ns'] is not None and q['response_ns']<=round(d['case']['drain_stop_s']*1e9)]
            g['inference_slowdown_s']={name:describe([losses[q['request_id']][name] for q in answered]) for name in ('thermal_s','contention_s','total_s')}
            for q in answered:
                ideal=sum(jobs_by_id[q['request_id']]['routes'][q['route']]['stages_ns'][:2 if task=='C' else 3])/1e9
                observed=(q['response_ns']-q['dispatch_ns'])/1e9
                assert abs(observed-ideal-losses[q['request_id']]['total_s'])<1e-7
        active_stats={}
        for device in ('CPU','GPU'):
            active_stats[device+'_mean_owners_in_supply']=sum(t['dt']*sum(v['route']==device for v in t['active']) for t in trace if t['start_ns']<635e9)/duration
        record=dict(label=row['label'],case=row['case'],rate=row['condition']['requests_per_second'],pattern=row['condition']['pattern'],policy=row['policy'],groups=groups,
            actions=dict(actions),routes=dict(route_counts),wait_s=d['result']['wait_used_ns']/1e9,
            neural=neural,teacher_local_cost_regret=describe(regrets),teacher_action_to_selected=cost_differences,
            teacher_group_compatibility=dict(per_group),immutable_inference_work_to_nominal_ratio=ratios,
            active=active_stats,controller_wall=describe(d['actor_call_wall_s']),controller_in_simulated_time=False)
        diagnostics.append(record);print('SAVED_DIAGNOSTICS',row['label'],flush=True)
    new(O/'DIAGNOSTICS.json',dict(status='PASS',rows=diagnostics,selected_TRAIN_coverage=traincov,
        interpretation='Descriptive evidence and matched-state teacher disagreement; not an intervention or causal ablation',new_environment=0,new_fit=0))
    findings=[]
    for x in accounting['rows']:
        if x['status']!='COMPLETE':continue
        if x['policy']!='BC_RECOVERED':continue
        for y in accounting['rows']:
            if y['case']!=x['case'] or y['status']!='COMPLETE' or y['policy']=='BC_RECOVERED':continue
            n=dict(case=x['case'],rate=x['load'],pattern=x['pattern'],reference=y['policy'],energy_saving_J=y['common']['J']-x['common']['J'],
                   energy_saving_percent=100*(1-x['common']['J']/y['common']['J']),AP_change_C=x['common']['AP']-y['common']['AP'],
                   peak_change_C=x['common']['peak']-y['common']['peak'],max_queue_change=x['max_queue']-y['max_queue'])
            for g in ('ALL','U','N'):
                n[g+'_on_change_pp']=100*(x['service'][g]['on']/x['service'][g]['n']-y['service'][g]['on']/y['service'][g]['n'])
                n[g+'_P95_change_s']=x['service'][g]['P95']-y['service'][g]['P95']
            findings.append(n)
    new(O/'FINDINGS.json',dict(aggregates=accounting['aggregates'],aggregate_deltas=accounting['deltas'],case_deltas=findings,
        diagnostics='DIAGNOSTICS.json',new_environment=0,new_fit=0,adopted=False))

def report():
    a=read(O/'ACCOUNTING.json');d=read(O/'DIAGNOSTICS.json');js=read(O/'AUDIT_JS.json');py=read(O/'AUDIT_PY.json');assert js['status']==py['status']==d['status']=='PASS'
    names={'FIFO_DYN':'FIFO','EDF_DYN':'EDF','RR_DYN':'RR','TEACHER':'교사규칙','BC_RECOVERED':'동결 보완 BC'}
    text=['# 보완 A24 BC의 S26식 요청 평가 결과','','방금 보완한 cec00807/50특징36후보망을 재학습 없이 동결했다. 기존 A24 ORIGINAL·CPU점유3/GPU1·beta.25·교사/롤링/필터를 유지하고 공통판의 예정요청·기한·입장·잠재작업·명목벡터를 그대로 사용했다. 장치당owner1인 앞선 공통판과 자원조건이 다르며, 공통50/27망으로 대체하지 않았다.','',
          '600초 공급·도착률1/4건/s·균등/8건묶음의5정책20새평가다. 소비J*·AP는5정책 공통완료창에서 패턴별 값의 평균, 정시율은 전체도착 분모, 긴급P95는 두패턴 응답을 합친 nearest-rank다. 별도 공급창/일반서비스도 ACCOUNTING.json에 보존했다.','',
          '|건/초|정책|예측 소비J*|AP℃|전체정시%|긴급정시%|긴급P95초|미응답/미완료|최대큐|',
          '|---:|---|---:|---:|---:|---:|---:|---:|---:|']
    for x in a['aggregates']:
        s=x['service'];rate=lambda g:100*s[g]['on']/s[g]['n'] if s[g]['n'] else 0
        if x['status']=='COMPLETE':text.append(f"|{x['load']}|{names[x['policy']]}|{x['J']:.3f}|{x['AP']:.3f}|{rate('ALL'):.2f}|{rate('U'):.2f}|{s['U']['P95']:.3f}|{s['ALL']['missing']}/{s['ALL']['incomplete']}|{x['max_queue']}|")
        else:text.append(f"|{x['load']}|{names[x['policy']]}|부분|부분|부분|부분|부분|실패/미완료|부분|")
    text+=['','## 보완 BC의 기준선/교사 대비 변화','','소비절감 양수는 개선, AP/P95 변화 양수는 증가다.','','|건/초|기준|소비절감J*|절감%|AP변화℃|전체정시변화%p|긴급정시변화%p|긴급P95변화초|','|---:|---|---:|---:|---:|---:|---:|---:|']
    for x in a['deltas']:text.append(f"|{x['load']}|{names[x['reference']]}|{x['energy_saving_J']:.3f}|{x['energy_saving_percent']:.3f}|{x['AP_change_C']:+.3f}|{x['all_on_change_pp']:+.3f}|{x['urgent_on_change_pp']:+.3f}|{x['urgent_P95_change_s']:+.3f}|")
    text+=['','## 동결 BC 방문상태 진단','','교사호환은 같은 BC 방문상태의 공개 롤링 최소비용 교사와의 비교다. 교사 전체 실행과 같은 궤적 또는 동일 최종성과를 뜻하지 않는다.','',
           '|건/초|패턴|BC호출|교사호환%|교사는즉시배정·BC대기|그중빈시스템|TRAIN큐범위초과|예측축소|최장연속WAIT|',
           '|---:|---|---:|---:|---:|---:|---:|---:|---:|']
    for x in d['rows']:
        if x['policy']!='BC_RECOVERED':continue
        n=x['neural'];text.append(f"|{x['rate']}|{x['pattern']}|{n['calls']}|{100*n['teacher_compatible']/n['calls']:.2f}|{n['WAIT_when_teacher_dispatch']}|{n['idle_WAIT_when_teacher_dispatch']}|{n['outside_TRAIN_queue']}|{n['forecast_horizon_reduced']}|{n['max_consecutive_WAIT']}|")
    text+=['','## 검증과 범위','',
        f"입력24014검사·독립 JS{js['checks']}검사(물리{js['independent_math_checks']})·입력결합{py['source_request_bindings']}건·기준선재생{py['baseline_replayed_decisions']}·Torch/별도NumPy{py['NN_frames']}선택/maxregret{py['Float64_argmax_max_regret']} PASS다. 원checkpoint·optimizer·RNG와 입력/원결과 SHA를 유지했다.",'',
        '알려진 공통 benchmark의 동결 정책 평가다. 가상CPU3·미교정 전력/열·D_GPU 파생값·명목과물리fit 공유·두 합성 패턴과 제어기 시간/전력 미가산의 한계를 유지한다. 새독립 실기기 확인이나 계산 검산을 통한 물리정확도 승격이 아니다. 추가재학습/결과선정/기존완료재시작/원망변경/자동채택/게시0이다.','',
        '[패턴별20행](ALL_ROWS_KO.md) · [원인분석](INTERPRETATION_KO.md) · [정밀집계](ACCOUNTING.json) · [패턴별변화](FINDINGS.json) · [지각/WAIT진단](DIAGNOSTICS.json) · [실행전량](RESULT.json) · [재개](CONTINUE_RUNNING.md)','']
    with (O/'REPORT_KO.md').open('x',encoding='utf8') as f:f.write('\n'.join(text))
    rows=['# 패턴별 전체20행','','모든정시율의분모는전체도착이다. 같은case의5정책에같은소비/AP종료창을쓴다. P95는예정도착부터응답까지다.','',
          '|건/초|패턴|정책|소비J*|평균AP℃|최고AP℃|전체정시/도착|긴급정시/도착|일반정시/도착|긴급P95초|WAIT초|CPU/GPU건수|최대큐|미응답/미완료|',
          '|---:|---:|---|---:|---:|---:|---|---|---|---:|---:|---|---:|---|']
    for x in a['rows']:
        if x['status']!='COMPLETE':rows.append(f"|{x['load']}|{x['pattern']}|{names[x['policy']]}|실패/부분|||||||||||");continue
        c=x['common'];s=x['service'];routes=x['route_counts']
        rows.append(f"|{x['load']}|{x['pattern']}|{names[x['policy']]}|{c['J']:.6f}|{c['AP']:.6f}|{c['peak']:.6f}|{s['ALL']['on']}/{s['ALL']['n']}|{s['U']['on']}/{s['U']['n']}|{s['N']['on']}/{s['N']['n']}|{s['U']['P95']:.6f}|{x['wait_s']:.6f}|{routes['CPU']}/{routes['GPU']}|{x['max_queue']}|{s['ALL']['missing']}/{s['ALL']['incomplete']}|")
    rows+=['','[집계](REPORT_KO.md) · [원인/한계](INTERPRETATION_KO.md) · [공통창·모든응답표본](ACCOUNTING.json)','']
    with (O/'ALL_ROWS_KO.md').open('x',encoding='utf8') as f:f.write('\n'.join(rows))

if __name__=='__main__':
    if sys.argv[1:]==['--audit']:audit()
    elif sys.argv[1:]==['--analysis']:analysis()
    elif sys.argv[1:]==['--report']:report()
    else:raise SystemExit('Explicit --audit/--analysis/--report required')
