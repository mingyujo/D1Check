"""Record the user's adoption of the existing published S26 teacher-initialized policy."""
import datetime,hashlib,json,shutil,subprocess
from pathlib import Path
W=Path(__file__).resolve().parents[1];R=W/'S26-D1Check';S=R/'s26_simulator';G=S/'experiments/route_group_learning_v1';P=G/'artifacts/G001';H=S/'final_policy_20261019'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def put(p,x):
 with p.open('x',encoding='utf-8',newline='\n') as f:json.dump(x,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')
assert not H.exists() and not (S/'FINAL_POLICY.json').exists(),'Existing adoption must be reviewed rather than overwritten'
H.mkdir();(H/'history').mkdir();(H/'workspace_recovery').mkdir()
utc=datetime.datetime.now(datetime.timezone.utc).isoformat();head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip()
snapshot=S/'publications/route_20261018/SNAPSHOT_FILES.json';published={x['path']:x for x in read(snapshot)['files']};selection=read(P/'SELECTION_FROZEN.json');assert selection['selected']==881087
inspection=read(W/'recovery/S26_FINAL_CANDIDATE_INSPECTION.json');selected=inspection['items']['selected'];bc=inspection['items']['BC_control']
for item in [selected,bc]:
 p=S/item['path'];key=p.relative_to(R).as_posix();assert sha(p)==item['file_sha256']==published[key]['sha256'];assert p.stat().st_size==published[key]['bytes']
summary=read(P/'COMPARISON_SUMMARY.json');groups={x['method']:x for x in summary['groups'] if x['load']==.85};pooled={x['method']:x for x in read(P/'POOLED_SERVICE_SUMMARY.json')['groups']}
assert groups['DEV_SELECTED_EVENT_PPO']['on_percent']==97.0703125 and groups['EVENT_PPO']['rows']==12
assert read(P/'AUDIT.json')['status'].startswith('PASS') and read(P/'NN_AUDIT.json')['status'].startswith('PASS')
source_files=[p for p in G.iterdir() if p.is_file() and p.suffix in ['.py','.cjs']]+[p for p in (G/'source').rglob('*') if p.is_file()]
source_files += [P/'S881087_FINAL.pt.gz',P/'BC_COMMON_FINAL.pt.gz',P/'SELECTION_FROZEN.json',P/'COMPARISON_SUMMARY.json',P/'POOLED_SERVICE_SUMMARY.json',P/'AUDIT.json',P/'NN_AUDIT.json',P/'TRAINING_COMPLETE.json',G/'PROTOCOL.json',G/'OPERATION.json',G/'INPUTS.json',S/'experiments/multiresource_v1/PACKET.json.gz',S/'experiments/capacity_power_v1/artifacts/G001/MODEL.json',S/'experiments/pipeline_thermal_v1/artifacts/G001/MODEL.json']
source_files=list(dict.fromkeys(source_files));pins=[]
for p in source_files:
 key=p.relative_to(R).as_posix();digest=sha(p);assert key in published and published[key]['sha256']==digest,'Published source changed: '+key;pins.append(dict(path=key,sha256=digest,bytes=p.stat().st_size))
entry_files=['s26_simulator/START_HERE.md','s26_simulator/STATUS.md','s26_simulator/HANDOFF.md','s26_simulator/docs/NEXT_STEPS.md','s26_simulator/AGENTS.md','docs/PROJECT_STATUS.md','docs/PROJECT_PLAN.md','docs/DECISIONS.md']
for rel in [*entry_files,'s26_simulator/CORE_MANIFEST.json']:shutil.copyfile(R/rel,H/'history'/rel.replace('/','__'))
contract=dict(schema='S26_FINAL_RESEARCH_POLICY_ADOPTION_V1',adopted_local_date='2026-10-19',recorded_utc=utc,status='ADOPTED_EXISTING_FROZEN_POLICY_CONDITIONAL_SIMULATION',user_instruction='그럼 우리 최종은 이걸로 가자',git_HEAD_at_adoption=head,
 methodology=dict(name='rolling+ATC+teacher-initialization+PPO',teacher_learning=True,teacher='Saved public-model heuristic demonstrations, route-group weighting and compatible public EDF ties; no runtime teacher override.',PPO=True,PPO_incremental_benefit_demonstrated=False,deadline_protection=False,post_neural_override=False,online_learning=False,prior_teacher_free_restriction='Applied to the separate controlled ablation; the latest user instruction adopts this existing teacher-initialized policy.'),
 representative=dict(seed=881087,checkpoint=selected,selection_source='Original DEV-only selection before the original EVAL, not the best seed selected from EVAL.',selection_record='s26_simulator/experiments/route_group_learning_v1/artifacts/G001/SELECTION_FROZEN.json',selection_sha256=sha(P/'SELECTION_FROZEN.json'),ensemble=False),
 teacher_control=bc,
 runtime=dict(source_directory='s26_simulator/experiments/route_group_learning_v1',driver='s26_simulator/experiments/route_group_learning_v1/run.py',server='s26_simulator/experiments/route_group_learning_v1/server.cjs',selector='s26_simulator/experiments/route_group_learning_v1/policy.cjs',network='s26_simulator/experiments/route_group_learning_v1/nn_train.py',mode='RL',variant='REPAIR',model='CPU3',capacity=3,route_slots=dict(CPU=1,GPU=1,NPU=1),reserve_until='AVAILABLE',nonpreemptive=True,
   neural=dict(features=32,actions=27,encoder='32->48 tanh + mean/max pooling',actor='144->64->1',critic='96->64->5',total_stored_parameters=17462,temperature=.35,training_selection='categorical sampling',evaluated_inference_selection='argmax of physically masked logits, first index on tie',feature30='Public candidate EDF/FIFO rank',feature31='Match to public observed-history route preference'),
   saved_balance=selected['balance'],evaluation_balance_override=dict(classFactors='[1/p,1/(1-p)] for the known nominal scenario mixture p',supported_evidence_p=[.5,.75],unknown_online_mixture_validated=False),
   important_binding='Use the checkpoint with its original features, route-preference/nominal-rollout controller, balance and frozen physics. Do not load it into the newer32parameter teacher-free framework.'),
 primary_evidence=dict(source='s26_simulator/experiments/route_group_learning_v1/artifacts/G001/COMPARISON_SUMMARY.json',nominal_load=.85,requests_each=1024,fixed_templates=2,latent_draws_per_template=2,baseline=groups['EDF_GPU_FIRST'],representative=groups['DEV_SELECTED_EVENT_PPO'],three_seed_aggregate=groups['EVENT_PPO'],BC_control=groups['BC_FROZEN'],pooled_service={k:pooled[k] for k in ['EDF_GPU_FIRST','DEV_SELECTED_EVENT_PPO','EVENT_PPO','BC_FROZEN']},aggregation_note='Headline urgent/normal percentages are unweighted means of session ratios. Pooled class rates use all arrivals and are stored separately; do not mix the two.'),
 claims=dict(policy_bundle_improved_on_its_registered_EDF_cohort=True,PPO_additional_benefit=False,RL_only_causal_improvement=False,real_device_savings_certified=False,physical_accuracy_gate='FAIL',CPU3_extra_power_heat_interference_measured=False,new_independent_validation_on_adoption=False),
 preservation=dict(keep_BC_control=True,keep_all_three_original_seeds=True,keep_teacher_free_PPO_CEM_and_FIFO_EDF_results=True,keep_failures_checkpoints_RNG_and_audits=True,secondary_reports=['s26_simulator/S26_MATCHED_PPO_CEM_RESULTS_KO.md','s26_simulator/S26_FIVE_POLICY_RESULTS_KO.md','s26_simulator/S26_FINAL_SCRATCH_RL_RESULTS_KO.md'],never_relabel_secondary_results_as_selected_policy_results=True),
 scope=dict(new_environment=0,new_training=0,new_measurements=0,new_physical_fits=0,new_budget_reservation=0,automations_changed=False,device_deployment=False),
 publication=dict(existing_policy_snapshot='s26-route-policy-20261018',existing_snapshot_already_published=True,this_adoption_marker_uploaded=False,original_publication_receipt_preserved=True),
 integrity=dict(published_snapshot_manifest='s26_simulator/publications/route_20261018/SNAPSHOT_FILES.json',snapshot_manifest_sha256=sha(snapshot),source_pins=pins))
put(S/'FINAL_POLICY.json',contract);shutil.copyfile(W/'recovery/S26_FINAL_CANDIDATE_INSPECTION.json',H/'CHECKPOINT_INSPECTION.json')
human=f'''# S26 최종 연구 정책 확정 — 2026-10-19

사용자의 “그럼 우리 최종은 이걸로 가자” 결정에 따라 **롤링+ATC+공개 교사학습 초기화+PPO, 납기 보호 없음**을 최종안으로 채택했다. 기존에 좋은 격차를 보인 `route_group_learning_v1` 정책이며, 교사 없이 처음부터 학습한 최근32파라미터 PPO/CEM은 별도 대조 실험으로 보존한다.

## 최종 기본 모델

- 단일 모델: **seed 881087**, 원 DEV에서 최종 평가 전에 선정했던 모델을 그대로 사용한다. 세 seed 평균·앙상블·평가 최고 seed로 대체하지 않는다.
- 체크포인트: [S881087_FINAL.pt.gz](experiments/route_group_learning_v1/artifacts/G001/S881087_FINAL.pt.gz)
- SHA256: `{selected['file_sha256']}`. 이미 게시한 복원용 스냅샷의 파일 SHA와 같다.
- 머신 설정: [FINAL_POLICY.json](FINAL_POLICY.json). 원 정책·특징·명목 예측·balance·전력/열 엔진과 묶어서 사용해야 한다.
- 검증된 평가 동작은 **물리적 합법 행동의 logit argmax**, 동률 첫 index다. 학습 때는 온도0.35 categorical sampling이었다. 이를 최근 sampled32 정책의 배포 방식으로 바꾸지 않는다.

## 채택 근거: 원85% 평가 결과

아래는 같은 원 평가 표본에서의 비교다. 입력당1024요청·두 도착/상황 template×잠재 작업량2개=4회/고정정책, PPO 전체는3seed×4회다. CPU3는 공통 서비스 병렬 가정이다.

| 방법 | 전체 API-J | 평균 AP/℃ | 전체 정시율 | 긴급 정시율 | 미완료 |
|---|---:|---:|---:|---:|---:|
| 원 단순 EDF(GPU→NPU→CPU) | 833.273 | 39.335 | 96.704% | 100.000% | 0 |
| 교사학습 직후·PPO 전 고정 대조 | 777.781 | 38.684 | 97.070% | 100.000% | 0 |
| 보완 PPO 3seed 평가 평균 | 777.827 | 38.685 | 97.062% | 100.000% | 0 |
| **최종 단일 모델881087** | **777.831** | **38.685** | **97.070%** | **100.000%** | **0** |

최종 단일 모델은 원 EDF 대비 전체 소비 **6.6535% 감소**, 평균 AP **0.6503℃ 감소**, 전체 정시율 **0.3662%p 증가**다. 연구 요약에 쓰던 “6.654%·0.650℃·97.062%”는 **3seed 평균**이다. 단일 기본 모델의 정시율97.070%와 혼용하지 않는다.

PPO 평균은 교사학습 직후 모델보다 소비가0.006% 높고 전체 정시율이0.008%p 낮았다. **PPO 자체의 추가 효과는 입증하지 않았다.** 성과는 경로 선택·사건 대기·후보/특징 표현·교사학습 초기화를 포함한 전체 정책의 조건부 성과로 설명한다. PPO 전 고정 모델은 대조군으로 계속 보존한다.

## 방법론을 고정하는 범위

롤링 예측으로 최대32개 관측 ready 작업을 평가하고, ATC·작업종류·우선순위·오래된/새 요청을 포함한 후보 최대8개와 CPU/GPU/NPU 배정·20/50ms·사건대기를 최대27개 행동으로 구성한다. 공개32특징을 set encoder와 actor에 넣어 최종 행동을 정한다. 분류는 CPU/GPU/NPU, 탐지는 CPU만 지원한다. CPU/GPU/NPU route 슬롯은 각1개·CPU 서비스는 최대3개·비선점·실제 AVAILABLE까지 예약한다.

공개 교사 시연을 경로군별 가중치와 공개 EDF 동률 호환 목표로 학습하고, 같은 교사 초기 가중치에서3개 PPO seed를 학습했다. 채택 모델은 그중 원 DEV 선정881087이다. 기존 체크포인트를 채택하는 결정이므로 최근 “교사·과거 초기 가중치 제외” 통제 실험과 구분한다.

공개 최근64개 관측 요청의 비중으로 경로 선호를 만들고 후속 명목 예측/특징에 사용한다. 실제 미래 작업시간을 넣거나 NN 행동을 뒤에서 덮어쓰지 않는다. 평가에서는 알려진 명목 혼합 비율 p=0.5/0.75로 `classFactors=[1/p,1/(1-p)]`를 설정했다. 임의의 미지 온라인 배합에서 검증됐다고 설명하지 않는다.

**납기 가능성 mask, 임박 요청 강제, 고정 logit prior, NN 뒤 규칙 교체는 없다.** 물리적 지원 경로·슬롯만 제한하며, 납기는 soft 보상으로 반영한다. 최종 가중치·정책·열계수·기한·입력 분모를 이번 채택 과정에서 바꾸지 않았다.

## 다른 실험과 한계

- 이번은 이미 본 여러 연구 결과를 바탕으로 사용자가 기존 정책을 채택한 결정이다. 새 독립 평가·실기기 배포·새 학습을 수행한 결과가 아니다.
- 최근 [FIFO/EDF/교사 없는 PPO·CEM 비교](S26_FIVE_POLICY_RESULTS_KO.md)는 다른8개 잠재 표본 및 NPU 우선 EDF의 결과다. 거기에 원 정책이 평가된 것으로 표를 합치거나6.654% 절감을 그 기준선에 전용하지 않는다.
- 에너지는 외부 전력계로 교정하지 않은 API-J, AP는 센서 모형 예측이다. 전력/열 정확도 gate FAIL·CPU3 추가 전력/열·간섭 미측정·제어/NN 기기 비용 미측정이라는 실제 한계는 유지한다. 실기기 절감 인증으로 쓰지 않는다.
- 원 표의 긴급·일반 비율은 세션별 비율 평균이다. 선택 모델의 일반 정시율은 세션 평균94.140625%, 전체 일반 도착을 합친 비율92.1875%다. 둘을 다른 표의 분모와 혼용하지 않는다.
- 모든 실패·원자료·교사 직후 모델·원3seed·교사 없는 최신 실험과 부정 결과를 보존한다. 완료 실험 재실행·새 학습·예약 재개는 이번 결정에 포함되지 않는다.

## 확인·인계

[원 결과와 방법론](publications/route_20261018/README.md) → [최종 설정](FINAL_POLICY.json) → [원 DEV 선정](experiments/route_group_learning_v1/artifacts/G001/SELECTION_FROZEN.json) 순서로 읽는다. 파일 확인은 `python s26_simulator/verify_final_policy.py`로 한다. 이 명령은 SHA·설정·기존 결과 연결만 확인하며 모델 forward/학습/시뮬레이션을 실행하지 않는다.

원 정책과 자료는 기존 GitHub 릴리스 `s26-route-policy-20261018`에 보관돼 있다. 이번 **최종 채택 표시와 인계 문서 변경은 로컬**이며 새 게시·커밋은 하지 않았다.
'''
(S/'FINAL_POLICY_KO.md').write_text(human,encoding='utf-8',newline='\n')
block='''<!-- S26_FINAL_POLICY_ADOPTED_BEGIN -->
2026-10-19 사용자 확정: 최종 연구 정책은 **롤링+ATC+공개 교사학습 초기화+PPO, 납기 보호 없음**이다. 정본은 s26_simulator/FINAL_POLICY_KO.md·FINAL_POLICY.json. 단일 기본 모델은 원 DEV 선정 **881087**, route_group_learning_v1/artifacts/G001/S881087_FINAL.pt.gz이며 원 정책/특징/balance와 함께 사용한다. 체크포인트 SHA 4a2c5b1d38da76bdef7f33c6eee6a4c69451130a68eb8e7168f0d760d37e2e34. 기존85% 단일 모델은 원 GPU우선 EDF 대비 소비−6.6535%·평균AP−0.6503℃·정시96.704→97.070%, 미완료0이다. 발표3seed평균은 소비−6.654%·평균AP−0.650℃·정시97.062%로 단일 모델과 구분한다. PPO의 교사학습 직후 대비 추가 이득은 미입증이며 전체 정책의 성과로 설명한다. 평가 배포는 원 argmax이고 최근 교사없는32파라미터 sampledNN과 혼용하지 않는다. 이전 교사배제 지시는 별도 통제 실험의 조건이며 이번 최신 결정은 기존 교사 포함 정책 채택이다. 모든 원자료/실패/BC대조/3seed/교사없는PPO·CEM/FIFO·EDF 결과는 보존. 새환경/학습/실측/물리fit/예약/기기배포0·정확도gateFAIL·CPU3미측정·실기기인증불가. 이 채택 표시의 새 GitHub 게시0. 다음 최대3: (1) 확정 방법론으로 보고서·발표 정리, (2) 원자료/모델/대조 보존, (3) 새 검증은 별도 사용자 요청 후 등록. 아래는 앞선 실험의 역사이며 최종 기본 모델 선택은 이 블록을 우선한다.
<!-- S26_FINAL_POLICY_ADOPTED_END -->

'''
for rel in entry_files:
 p=R/rel;p.write_text(block+p.read_text(encoding='utf-8-sig'),encoding='utf-8',newline='\n')
put(H/'DECISION.json',dict(status='ADOPTED',utc=utc,scope='Administrative adoption of existing frozen policy and honest claim/metadata binding only',new_environment=0,new_training=0,new_fits=0,new_measurements=0,new_reservation=0,uploaded=False,checkpoint_sha256=selected['file_sha256'],git_HEAD=head))
for name in ['adopt_s26_final_policy.py','inspect_s26_final_candidate.py']:shutil.copyfile(W/'recovery'/name,H/'workspace_recovery'/name)
print(json.dumps(dict(status='ADOPTED_PENDING_READ_ONLY_VERIFICATION',seed=881087,checkpoint_sha256=selected['file_sha256'],source_pins=len(pins),new_environment=0,new_training=0),ensure_ascii=False))
