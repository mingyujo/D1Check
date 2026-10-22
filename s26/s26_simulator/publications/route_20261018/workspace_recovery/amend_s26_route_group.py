"""Complete preSTART registration of causal tie-rank representation and rare-group fit."""
import json
from pathlib import Path
W=Path(__file__).resolve().parent.parent;H=W/'S26-D1Check/s26_simulator/experiments/route_group_learning_v1'
def read(n):return json.loads((H/n).read_text(encoding='utf-8'))
assert not (H/'OPERATION.json').exists() and not (H/'artifacts').exists()
p=H/'run.py';s=p.read_text(encoding='utf-8').replace('tail=.02)','tail=.02,rank_feature=True)').replace("'public_preflight='SAVED_PUBLIC_PREFLIGHT.json'", "'public_preflight='PREFLIGHT_PUBLIC_BANK.json'");p.write_text(s,encoding='utf-8')
p=H/'audit_nn.py';s=p.read_text(encoding='utf-8');needle="                if not f['collect']:need(int(logits[i].argmax())==f['index'],'Exact neural final choice')"
assert s.count(needle)==1
s=s.replace(needle,"""                if row['seed']>=881000:
                    order=list(dict.fromkeys(a['ordinal'] for a in f['candidate_actions'] if a['kind']=='DISPATCH'))
                    for j,a in enumerate(f['candidate_actions']):
                        if a['kind']=='DISPATCH':need(abs(float(f['x'][j,30])-order.index(a['ordinal'])/max(1,len(order)-1))<1e-7,'Causal public EDF/FIFO candidate rank, no future or override')
                if not f['collect']:need(int(logits[i].argmax())==f['index'],'Exact neural final choice')""");p.write_text(s,encoding='utf-8')
p=H/'report.py';s=p.read_text(encoding='utf-8').replace('experiments/route_event_learning_v1/','experiments/route_group_learning_v1/').replace("BC_accuracy=bc['logs'][-1]['TRAIN_demonstration_accuracy']", "BC_accuracy=bc['logs'][-1]['TRAIN_demonstration_accuracy'],BC_compatible_accuracy=bc['logs'][-1]['TRAIN_compatible_accuracy'],BC_group_accuracy=bc['logs'][-1]['TRAIN_group_accuracy']")
s=s.replace('TRAIN 규칙 시연으로 경로별', '저장 TRAIN 시연의 입력만 공개 후보 EDF/FIFO 순위로 다시 부호화했다(새 환경 실행0). DISPATCH의 기존 항상0이던30번 입력에 현재 후보 순위를 제공하고 WAIT 시간 입력은 유지했다. 이는 동률을 구별할 정보이며 납기 가능성으로 후보를 제거하지 않는다. 앞 사건 RL 고정 대조에는 이 새 입력을 적용하지 않았다. TRAIN 규칙 시연으로 경로별').replace('LR0.0001·KL중단·샘플링온도0.35','각 seed N512·85% 두 배합2episode/1update, LR0.0001·KL중단·샘플링온도0.35')
s=s.replace("lines=['# S26 사건 기반 대기·경로 예측·균형 보상 RL 결과'", "lines=['# S26 희소 경로 학습·공개 후보순위 보완 RL 결과'")
pos=s.index("for g in groups:lines.append")
s=s[:pos]+"lines.insert(3,'TRAIN 호환정답 일치율 '+format(summary['BC_compatible_accuracy'],'.3%')+'·행동/경로군별 '+str(summary['BC_group_accuracy'])+'다. 같은 공개 EDF 기한·같은 경로의 동률 요청은 학습 목표 확률을 합산했다. 이는 평가 정시율이나 서로 다른 잠재 실행의 물리적 동일성을 보증하지 않는다.')\n"+s[pos:];p.write_text(s,encoding='utf-8')
x=read('PROTOCOL.json');x['preSTART_representation_amendment']='Feature30 DISPATCH previously constant0 now public candidate EDF/FIFO rank, WAIT duration unchanged. Older event control keeps old feature. Saved TRAIN demonstration frames are copied and reencoded from candidate actions only. Preference31 remains. No runtime masks/priors/override.';x['BC']+=' Compatible dispatch targets require same physical route and same observed EDF deadline; other public EDF ties are legitimate alternatives, not proof of equal latent work.';(H/'PROTOCOL.json').write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')
x=read('SOURCE_DERIVATION.json');x['byte_identical']=[r for r in x['byte_identical'] if r['path']!='policy.cjs'];x['changed']+=' Candidate rank feature30 is new only for new NN; frozen old event control uses old input. Physics/source engine/nominal continuation unchanged.';(H/'SOURCE_DERIVATION.json').write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')
print('GROUP_PRESTART_RARE_ROUTE_AND_PUBLIC_RANK_AMENDMENT_READY')
