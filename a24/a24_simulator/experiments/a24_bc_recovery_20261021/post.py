"""Saved TRAIN/optimizer/frozen Torch+NumPy audit, report and recoverable proof."""
from study import *

def numpy_logits(net,x,mask):
    weights={k:v.detach().numpy().astype(np.float64) for k,v in net.state_dict().items()}
    def linear(a,name):return a@weights[name+'.weight'].T+weights[name+'.bias']
    e=np.tanh(linear(np.asarray(x,np.float64),'encode.0'));mask=np.asarray(mask,bool);mean=(e*mask[:,:,None]).sum(1)/mask.sum(1)[:,None];maximum=np.where(mask[:,:,None],e,-1e9).max(1);ctx=np.concatenate([mean,maximum],-1)
    logits=linear(np.tanh(linear(np.concatenate([e,np.broadcast_to(ctx[:,None],(len(e),36,96))],-1),'actor.0')),'actor.2').squeeze(-1)
    return np.where(mask,logits,-1e9)

def audit():
    result=read(O/'RESULT.json');op=read(H/'OPERATION.json');verify(op['pins']);assert result['new_TRAIN']==6 and result['science_START']<=19
    if not result['fit']:raise ValueError('No recovered checkpoint; preserve failures before reporting')
    initial=loadpt(CHECKPOINT);state=loadpt(O/'BC.RECOVERED.pt.gz');trace=loadpt(O/'BC.TRAINING_TRACE.pt.gz');data=loadpt(O/'TRAIN_FRAMES.pt.gz');frames=data['frames'];model=Learner(state=state)
    assert len(frames)==trace['frames'] and all(f['split']=='TRAIN' for f in frames);evalids={x['case']['id'] for x in read(H/'INPUTS.json')['evaluation']};assert not ({f['source_case'] for f in frames}&evalids)
    for f in frames:
        assert f['teacher_mask'].any() and not (f['teacher_mask'] & ~f['mask']).any() and f['teacher_mask'][f['index']]
        assert f['index']==int(np.where(f['mask'],f['scores'],np.inf).argmin()) and np.isfinite(f['x']).all() and f['filter_applied']
    expected=trace['epochs']*math.ceil(len(frames)/256);assert expected==trace['new_BC_steps']==state['bc_steps']-initial['bc_steps']
    assert len(trace['optimizer']['state'])==6 and all(int(v['step'])==expected for v in trace['optimizer']['state'].values())
    for k in initial['network']:
        if k.startswith('critic.'):assert torch.equal(initial['network'][k],state['network'][k])
    for key in ('actor_optimizer','critic_optimizer','action_rng','shuffle_rng'):equal(initial[key],state[key])
    assert state['network_sha256']!=initial['network_sha256'] and digest(model.net)==state['network_sha256']
    chunks=[frames[i:i+128] for i in range(0,len(frames),128)];good=0;per={};group_counts={}
    for part in chunks:
        with torch.no_grad():pred=model.net(torch.from_numpy(np.stack([f['x'] for f in part])),torch.from_numpy(np.stack([f['mask'] for f in part])))[0].argmax(-1).numpy()
        for i,f in enumerate(part):v=int(f['teacher_mask'][pred[i]]);good+=v;per[f['group']]=per.get(f['group'],0)+v;group_counts[f['group']]=group_counts.get(f['group'],0)+1
    assert abs(good/len(frames)-trace['logs'][-1]['compatible_accuracy'])<1e-7
    nn=ties=0;maxregret=0.;coverage={};binding_checks=0
    for row in result['rows']:
        if row['status']!='COMPLETE':continue
        raw=read(R/row['raw']['path']);states=raw['result']['decisions']
        if row['kind']=='TRAIN':
            labels=loadpt(R/row['labels']['path'])['frames'];assert len(labels)==len(states)
            for f,d,c in zip(labels,states,raw['calls']):
                assert f['public_state_sha256']==B.L.digest(d['public_state']) and f['time_ns']==d['time_ns'] and np.array_equal(f['x'],np.asarray(c['x'],np.float32)) and np.array_equal(f['mask'],c['mask']);binding_checks+=1
        if row['policy']=='BC_RECOVERED':
            for start in range(0,len(raw['calls']),128):
                part=raw['calls'][start:start+128];x=np.asarray([f['x'] for f in part],np.float32);mask=np.asarray([f['mask'] for f in part],bool)
                with torch.no_grad():torchpred=model.net(torch.from_numpy(x),torch.from_numpy(mask))[0].argmax(-1).numpy()
                logits=numpy_logits(model.net,x,mask)
                for i,f in enumerate(part):
                    assert int(torchpred[i])==f['chosen'];regret=float(logits[i].max()-logits[i,f['chosen']]);maxregret=max(maxregret,regret);assert regret<2e-6;ties+=int(logits[i].argmax()!=f['chosen']);nn+=1
        if states:coverage[row['label']]=dict(states=len(states),min_temperature_C=min(d['public_state']['sensor']['temperature_c'] for d in states),max_temperature_C=max(d['public_state']['sensor']['temperature_c'] for d in states),max_queue=max(len(d['public_state']['queue']) for d in states))
        print('PY_SAVED_AUDIT',row['label'],flush=True)
    equal(model.snapshot(),state);assert sha(CHECKPOINT)==op['checkpoint']['sha256'];verify([result['fit']['checkpoint']]);verify(op['pins'])
    new(O/'AUDIT_PY.json',dict(status='PASS',TRAIN_frames=len(frames),TRAIN_compatible_correct=good,TRAIN_compatible_accuracy=good/len(frames),per_group={g:per[g]/group_counts[g] for g in per},source_state_bindings=binding_checks,BC_new_steps=expected,optimizer_parameters=6,critic_and_PPO_optimizers_unchanged=True,NN_frames=nn,Float64_argmax_regret=maxregret,Float64_rounding_ties=ties,frozen_checkpoint_all_RNG_unchanged=True,coverage=coverage,new_environment=0,new_BC_fit=0))

def report():
    r=read(O/'RESULT.json');a=read(O/'ACCOUNTING.json');js=read(O/'AUDIT_JS.json');py=read(O/'AUDIT_PY.json');fit=read(O/'BC_TRAINING.json');assert js['status']==py['status']=='PASS'
    lines=['# 기존 A24 BC 보완·교사 직접 실행 비교','','기존 A24 ORIGINAL·CPU3/GPU1·beta.25·50특징망과 교사 비용식을 유지했다. 기존망/결과는 보존했다. 새 TRAIN6·BC1fit·교사/보완BC EVAL12의 유한19단위이며 기존 기준선·BC24세션은 저장 재사용이다. 새공통판/S26/실기기/PPO/물리fit/기존 완료 재시작0이다.','',f"현재 망에서 warm start하고 필터 일치·새 TRAIN의 기존BC 방문/오류상태·42℃ 고온 시작을 반영했다. 최종 학습자료{fit['frames']}개, {fit['epochs']}epoch, 새{fit['new_BC_steps']}회 갱신. 같은 보완 자료의 기존망 일치율{100*fit['initial_compatible_accuracy']:.3f}% → 보완망{100*fit['logs'][-1]['compatible_accuracy']:.3f}%다. 원1320개80.758%와 직접 같은 분모의 비교가 아니다. 학습일치율은 최종 정책 성능이나 일반화 보증이 아니다.",'','## 부하별 두 패턴 비교','','소비J*·AP는 case별 여섯 정책에 같은 완료 창을 적용한 패턴별 값의 평균이다. 전체/긴급 정시율은 전체 도착을 합친 분모, 긴급P95는 응답 지연을 합친 조건부95백분위다. 이전 표와 집계 끝이 달라지면 원 BC/기준선 소비도 달라질 수 있다.','', '|부하|정책|소비J*|AP ℃|전체 정시%|긴급 정시%|긴급P95 s|미응답/미완료|','|---:|---|---:|---:|---:|---:|---:|---:|']
    names={'FIFO_DYN':'FIFO','EDF_DYN':'EDF','RR_DYN':'RR','BC_OLD':'기존 BC+필터','TEACHER':'교사 직접+필터','BC_RECOVERED':'보완 BC+필터'}
    for row in a['aggregates']:
        s=row['service'];p=lambda g:100*s[g]['on']/s[g]['n'] if s[g]['n'] else 0
        if row['status']=='COMPLETE':lines.append(f"|{row['load']}|{names[row['policy']]}|{row['J']:.3f}|{row['AP']:.3f}|{p('ALL'):.2f}|{p('U'):.2f}|{s['U']['P95']:.3f}|{s['ALL']['missing']}/{s['ALL']['incomplete']}|")
        else:lines.append(f"|{row['load']}|{names[row['policy']]}|미정|미정|부분|부분|부분|실패/미완료 확인|")
    lines+=['','## 기존 BC와 교사 대비 변화','','|부하|비교 기준|소비 절감J*|절감%|AP 변화℃|전체정시 변화%p|긴급정시 변화%p|긴급P95 변화s|','|---:|---|---:|---:|---:|---:|---:|---:|']
    for d in a['deltas']:
        if d['reference'] in ('BC_OLD','TEACHER'):lines.append(f"|{d['load']}|{names[d['reference']]}|{d['energy_saving_J']:.3f}|{d['energy_saving_percent']:.3f}|{d['AP_change_C']:+.3f}|{d['all_on_change_pp']:+.3f}|{d['urgent_on_change_pp']:+.3f}|{d['urgent_P95_change_s']:+.3f}|")
    lines+=['','## 판정·범위','','위 표의 손해를 포함해 판단한다. 소비 절감 양수는 감소, AP/P95 변화 양수는 증가다. 평가 결과를 보고 재학습/재선정/추가시도하지 않았고 기존 채택 정책을 자동 교체하지 않는다. TRAIN6개는 기존 BC 행동에 교사 라벨을 붙인 off-policy 자료이며 새 보완 BC의 반복 DAgger가 아니다.','', '기존 성적을 본 benchmark의 보완 비교다. EVAL 상태·정답을 학습에 쓰지는 않았으나 새 독립 확인 실험이라고 주장하지 않는다. 실측 표본·공개 명목/물리fit 공유·두 반복 패턴·가상CPU3·미교정J*·D_GPU 파생값과 제어기 계산시간/전력 누락의 한계를 유지한다. BC도 모든 롤링 예측을 계산하므로 계산비용 절감을 입증한 구현이 아니다.','',f"검산: 독립 JS {js['checks']}검사(물리{js['independent_math_checks']}·저장{js['decision_checks']}판단), TRAIN출처 {py['source_state_bindings']}결합, 보완BC Torch/별도NumPy {py['NN_frames']}선택·Float64최대 regret {py['Float64_argmax_regret']:.3g} PASS. 원 가중치와 평가 전후 전체망/optimizer/RNG 불변을 확인했다.",'','[전체36행·공통창·모든기준선 차이](ACCOUNTING.json) · [과학실행 전량](RESULT.json) · [JS검산](AUDIT_JS.json) · [학습/NN검산](AUDIT_PY.json) · [학습기록](BC_TRAINING.json) · [사전규약](../../experiments/a24_bc_recovery_20261021/PROTOCOL.md)']
    with (O/'REPORT_KO.md').open('x',encoding='utf8') as f:f.write('\n'.join(lines)+'\n')
    new(O/'CONTINUE_RUNNING.md.json',dict(status='COMPLETE_REVIEW_REQUIRED',report='REPORT_KO.md',automatic_extra_runs=False,adopted=False,original_policy_preserved=True))

def seal():
    op=read(H/'OPERATION.json');verify(op['pins']);files=[pin(p) for folder in (H,O) for p in folder.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.name!='FINAL_PROOF.json']
    new(O/'FINAL_PROOF.json',dict(status='PASS',utc=stamp(),HEAD=subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip(),working_tree_uncommitted=True,files=files,source_pins_verified=len(op['pins']),old_policy_and_results_preserved=True,new_measurements=0,adopted=False,published=False))

if __name__=='__main__':
    if sys.argv[1:]==['--audit']:audit()
    elif sys.argv[1:]==['--report']:report()
    elif sys.argv[1:]==['--seal']:seal()
    else:raise SystemExit('Explicit --audit/--report/--seal required')
