"""Saved-only complete comparison and paired TRAIN evidence, without model selection."""
import json
from pathlib import Path
H=Path(__file__).resolve().parent;R=H.parents[2];O=R/'a24_simulator/results/A24_NN_MARGIN_EXACT_20261021_01'
def read(n):return json.loads((O/n).read_text(encoding='utf8'))
def write(n,s):
    with (O/n).open('x',encoding='utf8',newline='\n') as f:f.write(s.rstrip()+'\n')
a,py,diag,result=read('ACCOUNTING.json'),read('AUDIT_PY.json'),read('DIAGNOSTICS.json'),read('RESULT.json');js,lab,matched=read('AUDIT_JS.json'),read('AUDIT_LABELS_JS.json'),read('MATCHED_REQUESTS.json')
names={'FIFO_DYN':'FIFO','EDF_DYN':'EDF','RR_DYN':'RR','TEACHER_OLD':'원 교사','BC_OLD':'원 신경망 BC','TEACHER_FAIR':'새 교사','COST_IMITATION':'비용회귀 모방(이전 참고)','BC_NEURAL_PREVIOUS':'직전 신경망 BC','BC_NEURAL_REPAIRED':'보완 신경망 BC'}
def pct(s):return 100*s['on']/s['n']
def table(rows,pattern=False):
    out=['|요청/초|'+('패턴|' if pattern else '')+'정책|소비 J*|평균 AP ℃|전체 정시 %|일반 정시 %|긴급 정시 %|전체 P95 초|일반 P95 초|긴급 P95 초|미응답/미완료|','|---:|'+('---|' if pattern else '')+'---|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
    for x in rows:
        s=x['service'];v=x['common'] if pattern else x
        out.append(f"|{x['load']}|"+(x['pattern']+'|' if pattern else '')+f"{names[x['policy']]}|{v['J']:.6f}|{v['AP']:.6f}|{pct(s['ALL']):.4f}|{pct(s['N']):.4f}|{pct(s['U']):.4f}|{s['ALL']['P95']:.6f}|{s['N']['P95']:.6f}|{s['U']['P95']:.6f}|{s['ALL']['missing']}/{s['ALL']['incomplete']}|")
    return '\n'.join(out)
def delta(rate,reference):return next(x for x in a['deltas'] if x['load']==rate and x['policy']=='BC_NEURAL_REPAIRED' and x['reference']==reference)
main=[x for x in a['aggregates'] if x['policy'] in ('FIFO_DYN','EDF_DYN','RR_DYN','TEACHER_FAIR','BC_NEURAL_REPAIRED')];refs=[x for x in a['aggregates'] if x['policy'] not in ('FIFO_DYN','EDF_DYN','RR_DYN','TEACHER_FAIR','BC_NEURAL_REPAIRED')]
summary=[]
for rate in (1,4):
    x=next(x for x in a['aggregates'] if x['load']==rate and x['policy']=='BC_NEURAL_REPAIRED');t=next(x for x in a['aggregates'] if x['load']==rate and x['policy']=='TEACHER_FAIR');p=next(x for x in a['aggregates'] if x['load']==rate and x['policy']=='BC_NEURAL_PREVIOUS');e=delta(rate,'EDF_DYN');pd=delta(rate,'BC_NEURAL_PREVIOUS')
    summary.append(f"{rate}건/초: 보완NN 전체정시{pct(x['service']['ALL']):.4f}%/일반{pct(x['service']['N']):.4f}%/긴급{pct(x['service']['U']):.4f}%. EDF비 소비절감{e['energy_saving_J']:+.6f}J*/{e['energy_saving_percent']:+.4f}%·전체정시{e['all_on_change_pp']:+.4f}%p·일반{e['normal_on_change_pp']:+.4f}%p·긴급{e['urgent_on_change_pp']:+.4f}%p·긴급P95{e['urgent_P95_change_s']:+.6f}초. 직전NN비 전체{x['service']['ALL']['on']-p['service']['ALL']['on']:+d}/일반{x['service']['N']['on']-p['service']['N']['on']:+d}/긴급{x['service']['U']['on']-p['service']['U']['on']:+d}건·소비절감{pd['energy_saving_J']:+.6f}J*·긴급P95{pd['urgent_P95_change_s']:+.6f}초. 새교사비 전체{x['service']['ALL']['on']-t['service']['ALL']['on']:+d}/일반{x['service']['N']['on']-t['service']['N']['on']:+d}/긴급{x['service']['U']['on']-t['service']['U']['on']:+d}건·소비{x['J']-t['J']:+.6f}J*·긴급P95{x['service']['U']['P95']-t['service']['U']['P95']:+.6f}초.")
paired=py['paired_TRAIN'];control,treatment=paired;ev=[x for x in py['cases'] if x['kind']=='EVAL'];calls=sum(x['calls'] for x in ev);good=sum(x['compatible_correct'] for x in ev);multi=sum(x['nontrivial_n'] for x in ev);mgood=sum(x['nontrivial_correct'] for x in ev)
steps=sum(p['optimizer_steps'] for p in paired);dt=['|요청/초|비교대상|소비절감 J*|소비절감 %|전체정시차 %p|일반정시차 %p|긴급정시차 %p|긴급P95차 초|','|---:|---|---:|---:|---:|---:|---:|---:|']
for x in a['deltas']:
    if x['policy']=='BC_NEURAL_REPAIRED':dt.append(f"|{x['load']}|{names[x['reference']]}|{x['energy_saving_J']:+.6f}|{x['energy_saving_percent']:+.4f}|{x['all_on_change_pp']:+.4f}|{x['normal_on_change_pp']:+.4f}|{x['urgent_on_change_pp']:+.4f}|{x['urgent_P95_change_s']:+.6f}|")
ct=['|표현|TRAIN 상태|정확행동모방 %|복수후보정확행동 %|BC epoch|Adam step|','|---|---:|---:|---:|---:|---:|']
for x in paired:ct.append(f"|{'보완 상대비용' if x['relative'] else '대조 절대비용'}|{x['final']['n']}|{100*x['final']['all']:.4f}|{100*x['final']['nontrivial']:.4f}|{x['epochs']}|{x['optimizer_steps']}|")
et=['|case|선택 수|정확행동모방 %|복수후보 수|복수후보정확행동 %|교사 exact 수|최대교사비용차|','|---|---:|---:|---:|---:|---:|---:|']
for x in ev:et.append(f"|{x['case']}|{x['calls']}|{100*x['compatible_accuracy']:.4f}|{x['nontrivial_n']}|{100*x['nontrivial_accuracy']:.4f}|{x['teacher_exact']}|{x['max_teacher_regret']:.9g}|")
write('REPORT_KO.md',f'''# 신경망 BC 잔여오차·저부하 손해 보완 후 동일 S26식 입력 비교

2026-10-21 · A24-NNBC-MARGIN-04B · branch codex/a24-simulator-handoff-20261016 · HEAD ac3a5af569e04bc6be01f1ef976b9dd4eb6558cf + 로컬 미커밋/미게시.

{chr(10).join(summary)}

## 요청한 다섯 정책

{table(main)}

1건/초는 두패턴 합계1200건(U312/N888),4건/초는4800건(U1177/N3623)이다. 각600초 공급·균등/8건묶음·동일예정도착/기한/입장/양경로private작업 은행exact·A24 ORIGINAL/CPU3/GPU1/beta.25다. 정시율은모든도착분모합산·P95는드레인까지응답을합친nearest-rank·J*/AP는두패턴평균이다.9정책이같은case에서모두AVAILABLE인최종시각(최소공급종료)까지같은소비창으로재계산했다. S26식요청조건을사용하지만S26물리계수를A24에대입하지않는다. RR은C/D군교대·군내FIFO·비선점이다.

## 이전 네 정책도 보존

{table(refs)}

보완NN대비소비절감은대상−새NN,정시/P95변화는새NN−대상이다. 음수소비절감/정시손해·양수P95손해를그대로보고한다.

{chr(10).join(dt)}

## 원인 확인과 신경망 보완

직전오류상태의원28번교사비용입력차는저부하묶음중앙9.72e-5/고부하균등9.25e-5로작았다. 같은공개비용을현재허용후보평균/표준편차로정규화해28번특징만바꿨다. 신경망구조/나머지49입력·새교사/서비스마스크/물리/ATC/롤링은유지했다. 후보정답index/rank/one-hot을입력에넣지않았고출력은학습한NN logit argmax이며교사덮어쓰기0이다. 비용회귀모델/손실도없다.

분류CE에오답최고logit와정답최고logit의margin.5 hinge를.25가중치로추가하고행동군가중치[.5,2]를썼다. 직전TRAIN7892상태와직전49f053망이새TRAIN6에서방문한상태를합쳤다. EVAL 상태/정답은학습에넣지않았다. 원절대표현 대조fit과 정규화fit은 같은 초기49f053/자료/seed20265021/분류손실/그룹가중치/256epoch·step수이며28번표현만달랐다.

{chr(10).join(ct)}

위대응TRAIN비교에서정규화판−대조판의전체정확도는{100*(treatment['final']['all']-control['final']['all']):+.4f}%p·복수후보{100*(treatment['final']['nontrivial']-control['final']['nontrivial']):+.4f}%p다. 이는통제한학습자료에서표현변경의효과이며EVAL정책전체효과의완전분리는아니다. 정규화판을사전에평가정책으로정했고대조성적/EVAL성적으로모델을고르지않았다.

동결EVAL은전체{good}/{calls}({100*good/calls:.4f}%)·복수후보{mgood}/{multi}({100*mgood/multi:.4f}%)가교사비용정답과호환된다. 정확한행동index일치와비용허용차1e-8 호환을구분한다. 호환100%라도다른허용동점행동은실제궤적을바꿀수있으며별도최적화/계산절감/완전모방을자동주장하지않는다.

위학습/평가의정답은이번부터교사가고른정확index하나이므로위비율은**정확행동모방률**이다. 원비용호환mask는별도보존했고새입력/학습에정답index를제공한것은아니다. 동점후보의private작업량차이때문에넓은비용호환만으로실제궤적동일을보장하지못해정답을좁혔다. 과거비용호환81.777%와는정답기준/방문상태가다르다.

{chr(10).join(et)}

## 실행·검증과 범위

TRAIN6+BC2fit+EVAL4=12 START상한의실제기록은 [RESULT.json](RESULT.json)/[영수증](receipts.jsonl)을따른다. 기존32완료저장재사용+새EVAL4=36행/18집계행이며원완료identity재시작0이다. 새망/대조망/자료/optimizer/RNG/실제NN선택을보존했다. 로컬예약합산137945는전호스트census가아니다.

사전23700검사·독립JS{js['checks']:,}(물리{js['independent_math_checks']:,})·독립TRAIN라벨/정규화JS{lab['labels']:,}상태/{lab['checks']:,}검사·별도Torch/NumPy실제NN{py['neural_frames']:,}선택/최대argmax차{py['Float64_argmax_max_regret']:.3g}·TRAIN출처{py['TRAIN_source_bindings']:,}결합·대응fit의자료/seed/셔플/step일치·원망/평가checkpoint/optimizer/RNG불변PASS다. 총실제Adam갱신{steps:,}회다.

J*는미교정모형의예측소비이며실측절감이아니다. 기존benchmark를본후의수정이고독립실기기holdout/일반화/최적성/전조건우위를입증하지않는다. 가상CPU3·열/경합가정·원측정세션공유·제어계산비용누락을유지한다. 새실측/물리fit/PPO/후속튜닝/자동추가실험·채택/게시0이다.

[모든36행](ALL_ROWS_KO.md) · [저부하/남은오차/모든손해](INTERPRETATION_KO.md) · [같은요청손익](MATCHED_REQUESTS.json) · [완료/봉인](CONTINUE_RUNNING.md).
''')
write('ALL_ROWS_KO.md','# 동일 S26식 입력의9정책36행\n\n기존32완료저장재사용+새보완NN4평가다. 두새BCfit/새TRAIN6은평가도착분모에합치지않는다. 같은case9정책공통창이며전도착정시와미응답/미완료를보고한다.\n\n'+table(sorted(a['rows'],key=lambda x:(x['load'],x['pattern'],list(names).index(x['policy']))),True)+'\n\n[집계/판정](REPORT_KO.md) · [원집계/창](ACCOUNTING.json)\n')
qtable=['|요청/초|패턴|정책|일반 큐 평균 초|일반 큐 P95 초|일반탐지 큐 평균 초|정책WAIT 초|','|---:|---|---|---:|---:|---:|---:|']
for x in diag['rows']:
    if x['policy'] in ('EDF_DYN','TEACHER_FAIR','BC_NEURAL_PREVIOUS','BC_NEURAL_REPAIRED'):
        n=x['groups']['N']['queue'];dn=x['groups']['D_N']['queue'];qtable.append(f"|{x['rate']}|{x['pattern']}|{names[x['policy']]}|{n['mean']:.6f}|{n['P95']:.6f}|{dn['mean']:.6f}|{x['WAIT_s']:.6f}|")
low=next(x for x in matched['rows'] if x['case'].endswith('R1_burst'));ex=next(x for x in low['comparisons'] if x['reference']=='BC_NEURAL_PREVIOUS')['previous_lowload_examples'];examples=['|요청ID|기한 초|직전응답 초|보완응답 초|직전경로|보완경로|보완정시|','|---|---:|---:|---:|---|---|---|']
for x in ex:examples.append(f"|{x['id']}|{x['deadline_s']:.6f}|{x['reference_response_s']:.9f}|{x['new_response_s']:.9f}|{x['reference_route']}|{x['new_route']}|{x['new_on_time']}|")
write('INTERPRETATION_KO.md',f'''# 잔여 모방오차와 저부하 손해의 원인·보완 판정

## 같은 조건의 성과와 모든 손해

{chr(10).join(summary)}

조건별전체/일반/긴급정시·소비·응답꼬리지연을같이판정한다. 단일집계이득을모든요청의개선/전조건우위로해석하지않으며모든36행을전량보존했다.

## 확인한 표현 문제와 대응 학습 증거

앞선신경망은작은비용차를절대비용/10특징으로입력받았다. 실제오류후보/교사후보의입력차는묶음1건/s중앙약.000097로작았고다른행동/요청/상태특징이함께비선형logit을만들었다. 반올림동일은직전2178오류중1회,원Torch/NumPy출력차0·큐/온도기본범위이탈0·예측cap0여서단순float반올림/고온범위초과/cap오류로대부분을설명할근거는없었다. [사전저장진단](../../experiments/a24_nn_margin_exact_20261021/PRECHANGE_DIAG.json)을보존했다.

{chr(10).join(ct)}

서로같은초기망/자료/샘플순서/RNG/가중치/분류+margin손실/256epoch/step에서입력28만바꾼대응비교다. 정상화후정답을쉽게표현할수있었는지는위정확도차로판정한다. 정규화가다른자료에서도항상좋다는증명은아니며새손실자체의인과효과를별도분리하지않았다. 각망을EVAL에서시험해성적을고른것도아니다.

## 저부하에서 실제 지각했던 같은 요청

{chr(10).join(examples)}

위사례는직전저부하손해의세요청을sameID/예정도착/입장/기한/private작업그대로연결했다. 배정시각/장치경로/응답의전체기록은 [MATCHED_REQUESTS.json](MATCHED_REQUESTS.json)에있다. 단일의사결정만바꿔실험한것이아니므로다른경합/열/후속선택을분리한인과효과로확대하지않는다. 회복하지못한요청과새로손해본요청도같은JSON의정시손익에남겼다.

## 실제 모방오차·배정 지연

{chr(10).join(et)}

EVAL전체호환{100*good/calls:.4f}%/복수후보{100*mgood/multi:.4f}%이며정확index일치와호환을구분한다. 남은불일치의평균/P95/최대교사비용차·교사배정시NN대기·그반대·일반임박보호호출·예측축소/공개32초과를 [DIAGNOSTICS.json](DIAGNOSTICS.json)에보고했다. 높은모방률만으로실제정시/소비비악화를보증하지않는다. 새교사도명목롤링과현재공개상태만보므로실제private작업량/후속경합/재호출과차이가있다.

{chr(10).join(qtable)}

정책WAIT는기존owner의생산적실행과겹칠수있어모두전시스템유휴로해석하지않는다. 실제비용차는공통서비스마스크안에서계산되며대체가능최적일정의증거가아니다.

## 학습·검증과 결론의 경계

원50특징Net/직전49f053를계승하고교사비용28번표현/BC분류손실을보완했다. 정답행동/rank/one-hot/teacherfallback/비용회귀/PPO0이다. 같은시점에teacher서비스규칙/물리/명목/ATC/롤링/입력을바꾸지않아직전NN비차이를정책규칙변경과섞지않았다. 미래도착/private작업정보노출0이며EVAL상태/라벨학습0이다. 두fit은고정256epoch/동일초기망으로정규화판을미리최종정책으로지정했다.

독립JS정규화/라벨/물리·Torch/NumPy실제NN선택·학습출처/대응RNG/step·전후망/optimizer/RNG불변을검증했다. 구현검산은실기기정확성/실측절감증명이아니다. 알려진benchmark수정·가상CPU3·미교정J*·제어비용누락/측정세션공유한계를유지하고기존정책을자동대체하지않는다. 모든START/실패/SKIP는영수증을따르며자동추가학습/실험·재시도/게시0이다.

[주표/모든차이](REPORT_KO.md) · [모든36행](ALL_ROWS_KO.md) · [재개/봉인](CONTINUE_RUNNING.md).
''')
write('CONTINUE_RUNNING.md',f'''# A24-NNBC-MARGIN-04B 완료·재개

학습/평가를종료한결과의재개문서다. 원완료identity를재시작하지않는다. TRAIN6+BC2fit+EVAL4의유한12 START상한,기존32평가저장재사용/36행18집계행이며실제영수증은 [receipts.jsonl](receipts.jsonl)이다.

branch codex/a24-simulator-handoff-20261016 · HEAD ac3a5af569e04bc6be01f1ef976b9dd4eb6558cf + 로컬미커밋/미게시·자동채택0. 로컬예약합산137945는전호스트census/사용자직접숫자상한이아니다.

{chr(10).join(summary)}

대응TRAIN자료{treatment['final']['n']}상태/256epoch×2/실제Adam{steps}갱신이다. 원절대표현전체{100*control['final']['all']:.4f}%/복수후보{100*control['final']['nontrivial']:.4f}%, 정규화표현전체{100*treatment['final']['all']:.4f}%/복수후보{100*treatment['final']['nontrivial']:.4f}%, EVAL전체{100*good/calls:.4f}%/복수후보{100*mgood/multi:.4f}%다. 정규화판을사전선정했고EVAL모델선정0이다.

[주비교](REPORT_KO.md) · [전행](ALL_ROWS_KO.md) · [원인/손해](INTERPRETATION_KO.md) · [실제NN/대응fit/출처](AUDIT_PY.json) · [독립물리/정규화](AUDIT_JS.json) · [독립TRAIN라벨](AUDIT_LABELS_JS.json) · [같은요청손익](MATCHED_REQUESTS.json) · [봉인](FINAL_PROOF.json) · [재확인](FINAL_RECHECK.json).

다음은결과/변경diff검토와사용자질문응답이다. 이후새과학실행/튜닝/실측/물리fit/PPO/원완료재시작/자동추가·채택/게시를예약하지않았다. 후속은새소스/입력/유한범위/identity로별도등록한다.
''')
print('REPORTS_WRITTEN',len(a['rows']),len(a['aggregates']),summary,flush=True)
