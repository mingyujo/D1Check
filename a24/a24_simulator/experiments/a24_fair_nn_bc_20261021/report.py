"""Generate complete Korean comparison/interpretation from saved results only."""
import json,math
from pathlib import Path
H=Path(__file__).resolve().parent;R=H.parents[2];O=R/'a24_simulator/results/A24_FAIR_NN_BC_20261021_01'
def read(n):return json.loads((O/n).read_text(encoding='utf8'))
def write(n,s):
    with (O/n).open('x',encoding='utf8',newline='\n') as f:f.write(s.rstrip()+'\n')
names={'FIFO_DYN':'FIFO','EDF_DYN':'EDF','RR_DYN':'RR','TEACHER_OLD':'이전 교사','BC_OLD':'이전 신경망 BC','TEACHER_FAIR':'새 교사','COST_IMITATION':'이전 비용회귀 모방(참고)','BC_NEURAL_FAIR':'새 교사로 학습한 신경망 BC'}
a,py,diag,result=read('ACCOUNTING.json'),read('AUDIT_PY.json'),read('DIAGNOSTICS.json'),read('RESULT.json')
js,labels=read('AUDIT_JS.json'),read('AUDIT_LABELS_JS.json')
errors=read('ERROR_ANALYSIS.json')
def pct(s):return 100*s['on']/s['n']
def table(rows,patterns=False):
    out=['|요청/초|'+('패턴|' if patterns else '')+'정책|예측 소비 J*|평균 AP ℃|전체 정시 %|일반 정시 %|긴급 정시 %|전체 P95 초|일반 P95 초|긴급 P95 초|미응답/미완료|','|---:|'+('---|' if patterns else '')+'---|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
    for x in rows:
        s=x['service'];v=x['common'] if patterns else x
        out.append(f"|{x['load']}|"+(x['pattern']+'|' if patterns else '')+f"{names[x['policy']]}|{v['J']:.6f}|{v['AP']:.6f}|{pct(s['ALL']):.4f}|{pct(s['N']):.4f}|{pct(s['U']):.4f}|{s['ALL']['P95']:.6f}|{s['N']['P95']:.6f}|{s['U']['P95']:.6f}|{s['ALL']['missing']}/{s['ALL']['incomplete']}|")
    return '\n'.join(out)
main=[x for x in a['aggregates'] if x['policy'] in ('FIFO_DYN','EDF_DYN','RR_DYN','TEACHER_FAIR','BC_NEURAL_FAIR')]
refs=[x for x in a['aggregates'] if x['policy'] not in ('FIFO_DYN','EDF_DYN','RR_DYN','TEACHER_FAIR','BC_NEURAL_FAIR')]
deltas=['|요청/초|비교 대상|소비 절감 J*|소비 절감 %|전체 정시 차 %p|일반 정시 차 %p|긴급 정시 차 %p|긴급 P95 차 초|','|---:|---|---:|---:|---:|---:|---:|---:|']
for x in a['deltas']:
    if x['policy']!='BC_NEURAL_FAIR':continue
    deltas.append(f"|{x['load']}|{names[x['reference']]}|{x['energy_saving_J']:+.6f}|{x['energy_saving_percent']:+.6f}|{x['all_on_change_pp']:+.6f}|{x['normal_on_change_pp']:+.6f}|{x['urgent_on_change_pp']:+.6f}|{x['urgent_P95_change_s']:+.6f}|")
evalcases=[x for x in py['cases'] if x['kind']=='EVAL'];total=sum(x['calls'] for x in evalcases);correct=sum(round(x['compatible_accuracy']*x['calls']) for x in evalcases);multi=sum(x['nontrivial_n'] for x in evalcases);multigood=sum(round(x['nontrivial_accuracy']*x['nontrivial_n']) for x in evalcases if x['nontrivial_n'])
train=py['final_TRAIN_same_denominator'];fits=py['fit_audits'];steps=sum(x['optimizer_steps'] for x in fits)
summary=[]
for rate in (1,4):
    x=next(x for x in a['aggregates'] if x['load']==rate and x['policy']=='BC_NEURAL_FAIR');t=next(x for x in a['aggregates'] if x['load']==rate and x['policy']=='TEACHER_FAIR');old=next(x for x in a['aggregates'] if x['load']==rate and x['policy']=='BC_OLD');e=next(x for x in a['deltas'] if x['load']==rate and x['policy']=='BC_NEURAL_FAIR' and x['reference']=='EDF_DYN')
    summary.append(f"{rate}건/초: 새NN 전체정시{pct(x['service']['ALL']):.3f}%/일반{pct(x['service']['N']):.3f}%/긴급{pct(x['service']['U']):.3f}%. EDF비 소비절감{e['energy_saving_J']:+.3f}J*/{e['energy_saving_percent']:+.3f}%·전체정시{e['all_on_change_pp']:+.3f}%p·일반{e['normal_on_change_pp']:+.3f}%p·긴급{e['urgent_on_change_pp']:+.3f}%p·긴급P95{e['urgent_P95_change_s']:+.6f}초. 새교사비 소비{x['J']-t['J']:+.3f}J*·전체정시{x['service']['ALL']['on']-t['service']['ALL']['on']:+d}건·일반{x['service']['N']['on']-t['service']['N']['on']:+d}건·긴급{x['service']['U']['on']-t['service']['U']['on']:+d}건. 이전NN비 전체정시{x['service']['ALL']['on']-old['service']['ALL']['on']:+d}/일반{x['service']['N']['on']-old['service']['N']['on']:+d}/긴급{x['service']['U']['on']-old['service']['U']['on']:+d}건·소비{x['J']-old['J']:+.3f}J*.")
write('REPORT_KO.md',f'''# 기존 BC 신경망을 새 교사로 학습한 동일 S26식 입력 비교

2026-10-21 · A24-FAIR-NNBC-03 · branch codex/a24-simulator-handoff-20261016 · HEAD ac3a5af569e04bc6be01f1ef976b9dd4eb6558cf + 로컬 미커밋/미게시.

이번 모델은 **기존50특징36후보 신경망 Net과 cec00807 가중치를 이어받은 행동분류형 BC**다. 비용회귀모델/비용회귀손실은 사용하지 않았다. 새교사 규칙은 직전 봉인본 그대로 유지했다. 새교사/구NN의 저장 TRAIN 상태를 새라벨로 학습한 뒤1차망이직접방문한TRAIN6상태를집계해추가학습했다. 기존완료실험/새교사평가는재시작하지않았다.

{chr(10).join(summary)}

## 요청한 다섯 정책

{table(main)}

1건/초는두패턴합계1200건(U312/N888),4건/초는4800건(U1177/N3623)이다. 균등/8건묶음각600초 공급,정시율은모든도착건수합산·P95는드레인까지응답한지연을모은nearest-rank·J*/AP는패턴평균이다. 각case8정책의가장늦은AVAILABLE까지같은창으로재계산했다. 예정도착/기한/입장지터/양경로private5단계는직전은행exact이며 A24 ORIGINAL/CPU3/GPU1/beta.25물리를유지한다. S26의물리계수를A24에대입하지않았다. RR은C/D요청군교대·군내FIFO·비선점이고기준선장치배정은현재가용최소예측응답이다.

## 이전 결과도 참고로 전량 보존

{table(refs)}

새신경망BC의비교대상대비차이다. 소비절감은대상−새NN,정시/P95변화는새NN−대상이다. 모든음수손해/양수지연도그대로보고한다.

{chr(10).join(deltas)}

## 학습과 실제 모방률

Net의50→48 encoder·mean/max문맥·144→64→1 actor·critic구조를그대로사용했다.50입력중49개는동일하며28번교사공개비용만새교사비용으로갱신했다. 원입력에도교사비용이있었고추가미래정보는없다. 같은공통서비스마스크안에서신경망logit argmax로선택하며교사행동덮어쓰기0이다. 라벨은실제허용최소비용+1e-8의후보집합으로좁히고그룹균형분류손실을쓴다. 단일후보상태는선택여지가없어학습gradient에서제외하고전체정확도에는남겼다.

최종동일TRAIN분모{train['final']['n']:,}상태에서원망→최종망의전체모방률{100*train['initial']['all']:.4f}→{100*train['final']['all']:.4f}%,복수후보{100*train['initial']['nontrivial']:.4f}→{100*train['final']['nontrivial']:.4f}%다. 새교사라벨·새입력마스크를같이적용한동일분모비교이며과거다른라벨의83.95%와직접비교하지않는다.1차/2차각최대256epoch·실제총{steps:,}Adam갱신이고원critic/PPO카운터는유지했다. 가상42℃조건은기존TRAIN표본의온도가정대조다.

동결EVAL전체{correct:,}/{total:,}선택({100*correct/total:.4f}%)·복수후보{multigood:,}/{multi:,}({100*multigood/multi:.4f}%)가교사비용정답과호환된다. 전체일치율에는공통규칙으로하나만남은상태가포함된다. 모방100%/수렴/교사성능동일을전제하지않으며교사대비차이는표와원인보고서를따른다. 원신경망/새교사/새학습망은별도파일로보존했다.

## 실행과 검증

새2fit+TRAIN6+EVAL4=12 START/COMPLETE12·FAIL/SKIP0이며 [RESULT.json](RESULT.json)/[영수증](receipts.jsonl)에보존했다. 기존28평가저장재사용으로32행/16집계행,추가튜닝/새실측/물리fit/PPO/기존identity재시작/게시·자동채택0이다. 로컬예약합산137933은전호스트census/사용자직접숫자상한이아니다.

과학전47검사,독립JS {js['checks']:,}(물리{js['independent_math_checks']:,}),별도JS TRAIN라벨{labels['labels']:,}상태/{labels['checks']:,}검사,별도Torch/NumPy실제NN {py['neural_frames']:,}선택/Float64최대argmax차{py['Float64_argmax_max_regret']:.3g}·TRAIN출처{py['TRAIN_source_bindings']:,}결합·원망/전체평가checkpoint/optimizer/RNG불변PASS다. 물리정확성/실기기절감의검증으로확장하지않는다.

[전체32행](ALL_ROWS_KO.md) · [모방오차/큐/모든손해](INTERPRETATION_KO.md) · [집계 원자료](ACCOUNTING.json) · [재개/봉인](CONTINUE_RUNNING.md).
''')
write('ALL_ROWS_KO.md','# 동일 입력의 전체8정책32행\n\n기존28완료저장재사용+새신경망EVAL4다. 새TRAIN6은평가표분모와별도이며추가반복/독립표본으로합치지않는다. 모든도착기준정시율/미응답/미완료·같은case8정책소비창이다.\n\n'+table(sorted(a['rows'],key=lambda x:(x['load'],x['pattern'],list(names).index(x['policy']))),True)+'\n\n[집계와판정](REPORT_KO.md) · [행별창/분모](ACCOUNTING.json)\n')
ct=['|case|평가선택 수|전체호환 %|복수후보 수|복수후보호환 %|교사 exact선택 수|최대교사비용차|','|---|---:|---:|---:|---:|---:|---:|']
for x in evalcases:ct.append(f"|{x['case']}|{x['calls']}|{100*x['compatible_accuracy']:.4f}|{x['nontrivial_n']}|{100*x['nontrivial_accuracy']:.4f}|{x['teacher_exact']}|{x['max_teacher_regret']:.9g}|")
qt=['|요청/초|패턴|정책|일반 큐 평균 초|일반 큐 P95 초|일반탐지 큐 평균 초|일반탐지 큐 P95 초|정책WAIT 초|','|---:|---|---|---:|---:|---:|---:|---:|']
neural=[]
for x in diag['rows']:
    if x['policy'] in ('EDF_DYN','BC_OLD','TEACHER_FAIR','BC_NEURAL_FAIR'):
        n=x['groups']['N']['queue'];v=x['groups']['D_N']['queue'];qt.append(f"|{x['rate']}|{x['pattern']}|{names[x['policy']]}|{n['mean']:.6f}|{n['P95']:.6f}|{v['mean']:.6f}|{v['P95']:.6f}|{x['WAIT_s']:.6f}|")
    if x['policy']=='BC_NEURAL_FAIR':neural.append(x)
write('INTERPRETATION_KO.md',f'''# 기존 신경망 BC 보완: 결과·오차·한계

## 조건별 모든 성과와 손해

{chr(10).join(summary)}

위의성과/손해를같이해석한다. 같은교사를쓴신경망과직접교사정책의차이및이전BC와차이는별개다. 이번에는새교사규칙/공통서비스마스크와새라벨학습을함께적용했으므로이전BC비차이를신경망학습하나의순수인과효과로주장하지않는다. 별도비용회귀모델은이번정책/학습에사용하지않았으며표의참고행으로만보존했다.

## 실제 신경망이 얼마나 교사를 따랐는가

{chr(10).join(ct)}

정답은공통마스크안의실제교사최소비용+1e-8 후보이며,과거같은task/priority/deadline/route라면허용하던넓은호환라벨과구분한다. TRAIN정확도99.5%/행동군99%/loss.05의사전충분성기준과단순성능개선을혼동하지않는다. EVAL에서일치가좋아도추가학습/epoch선정에사용하지않았다. 원50특징Net을warm start하고공개교사비용28번만갱신했기때문에모델/입력/라벨ABI변경을명시하며과거망을조용히교체하지않는다.

**사전충분모방기준은미달이다.** 최종TRAIN전체93.690/복수후보92.337%,최종WAIT군81.496/WAIT_EVENT89.796%로선택오차가남았다. EVAL전체{100*correct/total:.4f}%·복수후보{100*multigood/multi:.4f}%이며원망보다학습은개선했지만완전모방을달성하지못했다.고부하성과일부가교사를넘었다고BC가더좋은전략을학습했다고일반화하지않는다.

EVAL에서순수최소비용허용차를벗어난선택은묶음1건/s173/균등4건/s844/묶음4건/s1161회다. 이중교사비용차≤.01은각168/800/1073회로대부분차이가작지만,고부하20회는.1을넘고최대.542792다. 신경망은입력에교사공개비용이있어도그밖상태특징/후보문맥을함께쓴비선형logit이므로항상최소비용후보를고르도록구조적으로보장되지않는다. 독립NumPy의actualargmax차0으로구현출력오류는확인하지못했다. score특징float32가같아진오류는전체2178중1회여서단순반올림이대부분의원인이라고설명할수없다.

모든EVAL상태의온도/큐는TRAIN의기본범위(26~41.9975℃/최대큐14)안이고예측800step축소0/공개32초과0이다. 이는세부상태분포/일반화까지동일하다는뜻은아니지만단순고온·최대큐범위초과/cap을주원인으로돌릴증거는없다. [상태별오류와같은요청손익](ERROR_ANALYSIS.json)에범위/작은비용차/큰오류/손해예시를보존했다.

## 저부하 손해와 고부하 개선을 분리

1건/s균등은전정책정시100%·행동/응답동일이고,새NN의저부하손해는묶음에서생겼다. 새교사정시였으나새NN지각인긴급7건과반대3건으로순4건손해다. 예를들어같은긴급분류 common-000396(도착427.0/기한427.8초)은새교사CPU배정427.041103/응답427.193020,새NN CPU배정427.864820/응답427.988786초로배정지연이지각과연결된다. 다른긴급탐지 common-000255는새NN이더일찍배정했지만CPU→GPU경로차이로284.120810→284.431320초응답이되어기한284.2초를넘었다. 이는전체궤적의같은요청관측이며특정한번의오류만바꾸면복구된다는인과증명은아니다.

4건/s는새교사비균등전체+16건/묶음−6건으로합계+10건,긴급+13/일반−3건이다. 소비−1.398J*/.104%와반대로긴급P95+.040382초·일반P95+.021392초손해가있다. EDF비일반정시는−12건/.331%p·일반P95+.375451초이며이전BC비일반+259건/긴급합계변화0·소비+11.314J*/.846%다. 즉일반밀림이크게줄었어도모든기준선/교사보다완전히좋은정책으로판정하지않는다.

## 일반 요청 지연과 WAIT

{chr(10).join(qt)}

정책WAIT는다른owner의생산적실행과겹칠수있어그대로전체시스템유휴시간이아니다. 새교사역시명목롤링의서비스제약이며미래실제작업량/후속경합/실제재호출을완벽예측하지못한다. 따라서공통서비스보호가실제정시100%/EDF비일반정시비악화를보증하지않는다. 소수의다른행동이후속상태와경합/온도를바꾸므로같은상태에서의교사비용차와최종실제성과는다르다.

새NN의case별WAIT불일치·임박보호·예측축소/공개cap·최대/평균교사비용차·실제지각배정/열경합분해는 [DIAGNOSTICS.json](DIAGNOSTICS.json)에전량보존했다. 지각분해는실제선택경로의private solo작업과실제시각에대한사후진단이며대체가능일정/최적성증명이아니다. 다음절의유한단위외추가ablation/학습으로성적을고르지않았다.

새NN고부하일반지각20건은균등1/묶음19건이다. 실제배정시선택경로private solo작업을더해도이미늦는것은5건이고나머지15건은열/CPU경합에의한진행량저하가추가돼야지각한다. 명목교사마스크와신경망잔여오차를함께고려해야하며BC오차하나로모든지각을설명하지않는다.

## 재현과 해석 범위

소스/입력/원망/기존결과는고정SHA로검증했고2fit의실제optimizer/gradient대상·critic불변/PPO카운터불변·셔플RNG를보존했다. 별도Torch/NumPy는실제NN출력을검산했고별도JS는물리/서비스마스크/예측비용/실제정답후보를검산했다. 저장TRAIN상태재예측은학습출처감사이며새환경/평가실행이아니다. 새망은최종등록fit에서동결한망이며EVAL성적에따른망선정/조정0이다.

기존benchmark를본후의수정비교이며새실기기holdout/일반화/통계적유의성/최적성은미입증이다. 가상CPU3·미교정J*·단순열/경합·원측정세션공유·롤링/제어계산비용누락을유지한다. 신경망을썼다는것만으로교사보다빠름/저소비/좋은정책임을뜻하지않는다. 기존정책자동교체/추가과학실행/게시0이다.

[요청한5정책/절대값](REPORT_KO.md) · [전체32행](ALL_ROWS_KO.md) · [완료/재개](CONTINUE_RUNNING.md).
''')
write('CONTINUE_RUNNING.md',f'''# A24-FAIR-NNBC-03 완료·재개

기존50특징36후보신경망/cec00807 warm start·새교사공통마스크/정확비용호환분류라벨·2fit과TRAIN방문상태집계를수행했다. 비용회귀모델/손실/PPO0이다. 기존28완료저장재사용+새NN EVAL4=32행/16집계행이며이전완료를재시작하지않는다.

branch codex/a24-simulator-handoff-20261016 · HEAD ac3a5af569e04bc6be01f1ef976b9dd4eb6558cf + 로컬미커밋/미게시. 새과학2fit+TRAIN6+EVAL4=12 START상한/실제영수증은 [receipts.jsonl](receipts.jsonl),로컬예약합산137933은전호스트census가아니다. 자동추가학습/실험·재시도/채택/게시0이다.

{chr(10).join(summary)}

최종동일TRAIN {train['final']['n']}상태에서전체{100*train['initial']['all']:.4f}→{100*train['final']['all']:.4f}%·복수후보{100*train['initial']['nontrivial']:.4f}→{100*train['final']['nontrivial']:.4f}%, EVAL전체{100*correct/total:.4f}%·복수후보{100*multigood/multi:.4f}%다. 모방충분성과실제성과는별도판정이다.

[집계/검증](REPORT_KO.md) · [모든행](ALL_ROWS_KO.md) · [원인/손해](INTERPRETATION_KO.md) · [Torch/NumPy/학습출처](AUDIT_PY.json) · [독립물리/마스크](AUDIT_JS.json) · [독립TRAIN라벨](AUDIT_LABELS_JS.json) · [모든진단](DIAGNOSTICS.json) · [최종봉인](FINAL_PROOF.json) · [재확인](FINAL_RECHECK.json).

다음은보고서/변경diff검토와사용자질문응답이다. 본실행종료후새과학프로세스는없으며추가예약하지않았다. 후속은새입력/소스/유한범위/identity로별도등록한다.
''')
print('REPORTS_WRITTEN',len(a['rows']),len(a['aggregates']),summary,flush=True)
