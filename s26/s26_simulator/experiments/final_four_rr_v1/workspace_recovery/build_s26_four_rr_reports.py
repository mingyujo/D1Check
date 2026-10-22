from pathlib import Path
_helper=Path(__file__).with_name('build_s26_contrast_reports.py')
exec(compile(_helper.read_text(encoding='utf-8').split('\ndef honest():')[0],str(_helper),'exec'))
from reportlab.platypus import Image
OUT=ROOT/'output/S26_RR_20261019';QA=ROOT/'tmp/pdfs/s26_four_rr';QA.mkdir(parents=True,exist_ok=True)
SCI=ROOT/'S26-D1Check/s26_simulator/experiments/final_four_rr_v1';D=json.loads((SCI/'artifacts/G001/SUMMARY.json').read_text(encoding='utf-8'))
MS=['FIFO','EDF','RR','OURS'];NAMES={'FIFO':'FIFO','EDF':'EDF','RR':'RR 큐 순환','OURS':'우리 최종 정책'}
def table(r):
    r.table(['방법','전체 소비\nAPI J','평균 AP\n℃','전체 정시율\n%','긴급 정시율\n%','미완료'],[[NAMES[m],f"{D[m]['J']:.3f}",f"{D[m]['AP_mean']:.3f}",f"{D[m]['service']['all']['pooled_on_percent']:.3f}",f"{D[m]['service']['urgent']['pooled_on_percent']:.3f}",str(D[m]['unfinished'])] for m in MS],[132,80,70,82,82,46])
def changes(r):
    r.table(['우리 정책의 비교 대상','전체 API 소비 차이','평균 AP 차이','전체 정시율 차이'],[[b,f"{-D['OURS']['versus_'+b]['energy_percent']:.3f}% 감소",f"{-D['OURS']['versus_'+b]['AP_C']:.3f}℃ 감소",f"{D['OURS']['versus_'+b]['on_pp']:.3f}%p 증가"] for b in ['FIFO','EDF','RR']],[132,120,120,120])
def chart_page(r):
    r.start('같은 입력에서의 EDF 대비 차이')
    im=Image(str(OUT/'02_gap_vs_EDF.png'));im.drawHeight=WIDTH*im.imageHeight/im.imageWidth;im.drawWidth=WIDTH;r.put(im,after=8)
    r.p('양수는 EDF보다 유리하다는 뜻이다. 에너지는 방법별 평균 소비끼리의 상대 차이, 온도는 평균 AP의 절대 차이, 정시율은 %p 차이다. 점 4개는 입력별 대응 차이이며 신뢰구간이 아니다. 모형 결과를 실기기 효과로 해석하지 않는다.','small')
    r.p('RR과 FIFO의 전체 정시율은 같고 소비·평균 AP 차이는 작다. 우리 정책은 평균 소비·평균 AP·전체 정시율에서 EDF보다 유리했다. 입력별 점은 같은 도착 템플릿을 공유한 잠재 작업량의 변동이므로 독립 실기기 반복 측정으로 해석하지 않는다.','small')
def refs(r):
    r.refs([1,2,3,4])
    r.p('[5] <link href="https://pubs.opengroup.org/onlinepubs/9799919799/functions/V2_chap02.html" color="#235A85">The Open Group POSIX Scheduling Policies</link>. 표준 SCHED_RR은 타임퀀텀에 따른 실행 교체를 포함한다. 본 비교는 사용자 선택에 따라 별도로 정의한 비선점 작업 큐 순환 디스패처다.','small')

def fact():
    r=Report(OUT/'S26_FIFO_EDF_RR_우리정책_최종보고서_사실중심.pdf','FIFO EDF RR 우리 정책 사실 중심',5)
    r.start('네 방법의 동일 조건 결과',first=True)
    r.title('S26 다중 자원 스케줄링 최종 보고서','FIFO EDF RR 우리 정책 비교  사실 중심 버전')
    r.p('<b>같은 85% 명목 부하·CPU3·4입력에서 우리 최종 단일 정책은 FIFO·EDF·RR보다 전체 모형 소비와 평균 AP가 낮고 전체 정시율이 높았다.</b> 우리 정책은 롤링+ATC+공개 교사학습 초기화+PPO, seed 881087이며 납기 보호는 없다. 전체 정책의 조건부 결과로 해석하고 PPO의 추가 효과와 구분한다.')
    r.h('주 비교 결과')
    table(r)
    r.p('방법마다 4세션×1,024요청이며 전체 정시율 분모는 4,096건이다. 긴급 2,560건의 정시율은 모두 100%, 미완료는 모두 0이다. 에너지와 AP는 세션 평균이며 API J는 외부 전력계로 교정하지 않은 API-J, AP는 센서 온도 모형 예측이다. 우리 행은 3개 seed 평균이 아닌 최종 단일 모델이다.','small')
    changes(r)
    r.p('RR은 이번 입력에서 FIFO와 거의 같았다. RR 소비는 FIFO보다 약 0.0843% 높고 평균 AP는 약 0.0099℃ 높으며 전체 정시율은 같다. 격차를 만들기 위해 RR의 규칙·입력·열계수를 사후 조정하지 않았다.')
    r.h('비교 범위')
    r.p('분류는 CPU·GPU·NPU, 탐지는 CPU만 지원한다. FIFO·EDF·RR의 자원 순서는 원 평가의 GPU→NPU→CPU로 같게 고정했다. 우리 정책은 같은 지원 경로에서 자원과 대기를 선택한다. 모든 방법의 비선점·AVAILABLE까지 점유·기한·전력/열·도착과 잠재 작업량·관측창을 유지했다.')
    r.p('RR 4회만 새 평가했고 기존 FIFO·EDF·우리 모델 각 4회는 SHA를 확인해 재사용했다. 새 학습·물리 fit·기기 측정·완료 실험 재실행은 없다. 동일한 4입력의 16기록·16,384요청 저장 계산 검사는 548,406회 통과했다.','small')

    r.start('RR의 정의와 공통 평가 조건')
    r.table(['방법','요청과 실행 경로를 선택하는 방식'],[
        ['FIFO','실행 가능한 관측 ready 큐의 도착순·ordinal 동률 순. 고정 자원 순서.'],
        ['EDF','같은 큐의 절대 마감순, 동률은 도착·ordinal 순. FIFO와 같은 자원 순서.'],
        ['RR 큐 순환','분류·탐지 큐를 한 건씩 순환. 큐 내부 FIFO. 실행할 수 없는 큐는 건너뜀.'],
        ['우리 최종 정책','롤링·ATC 후보와 예측 특징으로 신경망이 요청·경로·대기를 함께 선택.'],
    ],[124,368])
    r.h('사용자가 선택한 비선점 작업 큐 RR')
    r.p('RR의 두 큐는 분류와 탐지다. 초기 다음 큐는 분류로 고정한다. 현재 다음 큐에서 실행 가능한 가장 오래된 요청 한 건을 배정한 뒤 다른 큐로 포인터를 옮긴다. 그 큐가 비었거나 필요한 자원이 점유 중이면 다른 큐를 살핀다. 어느 큐도 실행할 수 없을 때만 NONE을 반환하고 포인터를 유지한다. 기한과 긴급·일반 우선순위는 선택에 사용하지 않는다.')
    r.p('순환 단위는 요청 배정 기회 한 번이다. 실행 중 추론을 중단·재개하지 않고 CPU 실행시간을 똑같이 나누지도 않는다. 표준 OS의 타임퀀텀 SCHED_RR과 다르므로 결과의 RR은 항상 “비선점 작업 큐 RR”로 읽는다.[5] 분류=긴급·탐지=일반이라는 원 입력의 결합도 유지된다.')
    r.h('관측창과 작업 경과')
    r.table(['방법','관측창 평균 초','작업 경과 평균 초','기저 API J'],[[NAMES[m],f"{D[m]['observation_s']:.3f}",f"{D[m]['work_s']:.3f}",f"{D[m]['baseline_J']:.3f}"] for m in MS],[154,110,118,110])
    r.p('전체 소비는 관측 시작부터 끝까지 기저와 냉각을 포함한다. 평균 AP는 35초부터 종료까지 계산한다. 작업 경과는 첫 도착부터 마지막 실제 AVAILABLE까지이며 자원별 실행시간 합계가 아니다. CPU3은 서비스 최대 3개 병렬이라는 미측정 가정이며 논리 route 슬롯은 CPU·GPU·NPU 각 1개다.')
    r.p('우리 정책은 최대 8개 요청 후보·32개 관측 ready 요청 예측·최대 27개 행동·32개 특징을 사용한다. 평가에서는 물리적으로 합법인 행동 logit의 argmax를 선택한다. 미래 실제 작업량, 납기 가능성 마스크, 임박 요청 강제, 신경망 뒤 규칙 교체는 없다.','small')

    chart_page(r)

    r.start('응답 지연과 PPO 추가 기여의 한계')
    r.table(['방법','전체 P95 초','긴급 P95 초','일반 정시율 %'],[[NAMES[m],f"{D[m]['service']['all']['mean_case_P95_s']:.3f}",f"{D[m]['service']['urgent']['mean_case_P95_s']:.3f}",f"{D[m]['service']['normal']['pooled_on_percent']:.3f}"] for m in MS],[160,110,110,112])
    r.p('P95는 완료 응답의 회차별 P95를 평균한 값이다. 일반 정시율은 전체 일반 도착 1,536건의 pooled 비율이다. 우리 정책은 전체 응답 P95가 낮지만 긴급 P95는 FIFO·EDF·RR보다 길었다. 긴급 정시율 100% 유지와 모든 요청군의 응답성 개선은 구분해야 한다.')
    r.h('원인 분리를 위한 보조 대조')
    r.table(['보조 대조','전체 API J','평균 AP ℃','전체 정시율 %'],[
        ['교사학습 직후 고정','777.781','38.684','97.070'],
        ['최종 단일 PPO 모델','777.831','38.685','97.070'],
    ],[214,94,92,92])
    r.p('PPO 후속 모델은 교사학습 직후보다 소비가 약 0.0065% 높고 정시율은 같았다. 원 3seed 평균도 교사 직후 대비 소비 약 0.006% 증가·정시율 약 0.008%p 감소였다. FIFO·EDF·RR 대비 성과를 PPO만의 독립 효과로 귀속할 수 없다. 경로 선호·대기·표현·교사 초기화의 개별 기여도 분리되지 않았다.')
    r.h('모형 결과를 해석하는 범위')
    r.p('전력·열 실측 정확도 gate는 FAIL이다. CPU3 추가 코어 소비·열·간섭과 기기에서의 예측·NN·제어 비용은 미측정이다. AP 적격 관측 지원은 약 26~46.6℃이며 밖은 외삽이다. 계산 검산 PASS는 실기기 절감 인증이 아니다. 열계수 k를 2·3·4배로 늘린 가상기기나 임의 온도 상한을 이번 결과에 넣지 않았다.')
    r.p('고정 두 도착 템플릿의 잠재 작업량 2개씩에 대한 결과이며 넓은 일반화나 통계적 우월성을 입증하지 않는다. GPU 우선 정적 기준선의 비교이므로 모든 경로 순서의 가장 강한 기준정책에 대한 우위로 확대하지 않는다. 교사 없는 별도 PPO·CEM 실험의 불리한 결과도 기존 자료에 보존한다.','small')

    r.start('RL과 CEM을 검토할 근거와 참고 자료')
    r.p('ATC 계열은 납기·처리 요구량·지연 비용을 반영하는 우선순위 규칙으로 발전했다.[1] 여기서는 처리 순서뿐 아니라 실행 장치와 대기를 정해야 하고, 현재 선택이 이후 큐·자원 상태에 영향을 준다. 이 통합 선택을 정책 함수로 표현해 경험으로 학습할 방법론적 근거가 있다. 다중 자원 배정을 학습 문제로 다룬 DeepRM은 관련 선행 사례다.[2]')
    r.p('PPO는 환경 경험과 보상으로 정책을 갱신하는 강화학습 알고리즘이다.[3] 최종안은 공개 규칙 시연의 행동 복제라는 지도학습 후 PPO를 적용했다. 공통 교사 모델은 10epoch·120 optimizer step, PPO는 seed당 512요청 2episode·1 update였다. 881087은 원 DEV에서 EVAL 전에 선정했다. 최종 계열 채택은 여러 결과를 본 뒤의 결정이며 새 독립 확인 실험이 아니다.')
    r.p('CEM은 후보 정책을 회차 성과로 평가해 좋은 파라미터 영역으로 탐색 분포를 옮기는 확률적 최적화 대안이다. 시뮬레이터 내부 미분 없이 정책을 직접 탐색할 수 있다. 잡음이 있는 평가에서는 elite 선택이 기대 보상과 다른 분위수 기준을 선호할 수 있다.[4] CEM은 최종 기본 모델에 들어 있지 않다.')
    r.p('<b>도입 근거는 요청·자원·대기의 통합 선택을 학습·탐색으로 정하는 데 있다.</b> 산업공학적 방법이므로 RL·CEM이 반드시 필요하다는 논리는 성립하지 않는다. 고정 규칙이나 예측 비용 최소 선택도 대안이며, 추가 성능 기여는 대조로 따로 입증해야 한다.')
    refs(r)
    r.p('[6] 최종 모델 seed 881087, 체크포인트 SHA256 앞 16자리 4a2c5b1d38da76bd. <link href="https://github.com/mingyujo/D1Check/blob/codex/s26-simulator-handoff-20261016/s26_simulator/publications/route_20261018/README.md" color="#235A85">원 정책 공개 자료</link>. 이번 원자료·RR 정의·등록·검산·요약은 로컬 experiments/final_four_rr_v1, 그림 수치는 comparison_data.csv 및 SUMMARY.json에 연결한다. 원 자료와 이전 보고서는 보존했으며 새 GitHub 게시를 하지 않았다.','small')
    return r.finish()

def positive():
    r=Report(OUT/'S26_FIFO_EDF_RR_우리정책_최종보고서_성과강조_비판용.pdf','FIFO EDF RR 우리 정책 성과 중심 예시',4,biased=True)
    r.start('네 방법의 성과 비교',first=True)
    r.title('S26 다중 자원 스케줄링 최종 보고서','FIFO EDF RR 우리 정책 비교  성과 강조 예시')
    r.p('<b>비판용 선택적 서술 예시.</b> 같은 원자료에서 유리한 성과를 중심으로 서술했다. 수치는 사실 중심 버전과 같고 새로 만들지 않았다. 생략한 대조와 한계는 마지막 페이지에 명시한다.','small')
    r.p('우리 하이브리드 정책은 CPU·GPU·NPU 경로 선택과 대기를 통합해 FIFO·EDF·RR보다 전체 소비와 평균 AP를 낮추고 전체 정시율을 높였다. 납기 강제 보호 없이 전량 처리와 긴급 정시율 100%를 유지했다. 최종안은 롤링+ATC+공개 교사학습 초기화+PPO의 단일 모델 881087이다.')
    table(r)
    changes(r)
    r.p('우리 정책의 전체 소비는 777.831 API-J로 FIFO 840.480, EDF 833.273, RR 841.189 API-J보다 낮았다. 평균 AP는 우리 38.685℃로 FIFO 39.434℃·EDF 39.335℃·RR 39.444℃보다 낮았다. 전체 정시율도 우리 97.070%로 가장 높았다.')
    r.p('RR은 분류·탐지 큐를 한 건씩 순환하는 비선점 방식이다. 네 방법 모두 같은 명목 85%·CPU3·4입력×1,024요청을 사용했다. FIFO·EDF·RR의 경로 순서는 GPU→NPU→CPU로 같게 고정했다. 우리 모델의 가중치나 대표 seed를 이번 결과에 맞춰 다시 고르지 않았다.')

    r.start('통합 의사결정 구조와 채택 근거')
    r.p('FIFO는 도착순, EDF는 마감순, RR은 작업종류별 큐를 번갈아 선택한다. 우리 정책은 ATC가 제공한 후보와 롤링 예측 정보를 받아 신경망이 요청·실행 경로·대기를 함께 결정한다. 현재의 배정이 다음 요청의 선택 여지를 바꾸는 관계를 통합 정책 함수로 다룬다.')
    r.h('RL 또는 CEM을 검토한 이유')
    r.p('다중 자원 배정을 경험 기반 학습으로 다루는 DeepRM은 관련 선행 사례다.[2] 우리 최종안은 공개 규칙을 행동 복제로 익힌 뒤, 에너지·열·납기를 함께 반영한 보상으로 PPO를 적용했다. PPO는 환경 경험을 이용한 정책 갱신 방법이다.[3] CEM은 회차 성과로 후보 정책 가중치를 직접 탐색하는 비교 대안이며 최종 모델에는 포함하지 않았다.[4]')
    r.h('완료와 전체 응답 지연')
    r.table(['방법','완료 도착 대비','전체 정시 건수','전체 P95 초'],[[NAMES[m],'4096 / 4096',str(D[m]['service']['all']['on_time']),f"{D[m]['service']['all']['mean_case_P95_s']:.3f}"] for m in MS],[150,128,110,104])
    r.p('우리 정책은 모든 요청을 완료하면서 정시 건수가 FIFO·RR보다 6건, EDF보다 15건 많았다. 전체 완료 응답 P95 회차 평균도 가장 짧았다. 관측창 평균 245.558초와 공통 기저 172.828 API-J를 포함한 전체 소비 기준으로 차이를 제시했다.')
    r.p('기존 평가 자료를 재사용하고 부족한 RR 4회만 추가했다. 같은 전력·열·지원 경로·납기·비선점·AVAILABLE 점유를 유지했으며 추가 학습이나 물리계수 변경은 없었다. 최종 정책은 같은 조건의 세 기준정책에 대해 전체 소비·평균 AP·전체 정시율이 함께 개선되는 결과를 보였다.')
    r.refs([2,3,4])

    chart_page(r)

    r.start('성과 중심 서술에서 생략한 정보')
    r.p('<b>수치가 맞더라도 대조와 범위를 생략하면 결론을 과도하게 받아들일 수 있다.</b> 이 페이지는 앞선 성과 중심 본문의 비교 주석이다. 실제 성능 입증 자료로 단독 사용하지 않는다.')
    r.h('정책 전체 성과와 PPO의 추가 효과')
    r.p('교사학습 직후 모델은 777.781 API-J·정시율 97.070%로, 최종 PPO 모델의 777.831 API-J·97.070%보다 소비가 낮고 정시율은 같다. 이 대조를 빼면 FIFO·EDF·RR 대비 절감이 PPO의 보상 학습 때문에 생긴 것으로 오해할 수 있다. 경로 선호·대기·특징·교사 초기화를 포함한 정책 전체의 성과로 설명해야 한다.')
    r.h('긴급 정시율과 응답 지연')
    r.p('긴급 정시율은 네 방법 모두 100%지만 긴급 P95 회차 평균은 FIFO 0.366초·EDF 0.340초·RR 0.367초·우리 0.604초다. 전체 P95가 짧아도 모든 요청군의 지연을 줄인 것은 아니다. 전체 정시율 차이도 FIFO·RR 대비 0.146%p, EDF 대비 0.366%p로 큰 폭의 납기 개선이라고 쓰기 어렵다.')
    r.h('RR의 의미와 그림의 축')
    r.p('RR은 OS 타임퀀텀 선점 방식이 아니라 사용자가 선택한 비선점 분류·탐지 큐 순환이다. CPU 사용시간의 균등 배분을 보장하지 않는다. 그림의 온도·정시율 점그래프는 확대 축이며 수치와 범위를 함께 읽어야 한다. EDF 대비 차이에서 에너지 단위 %와 정시율 단위 %p를 바꿔 쓰면 안 된다. 입력별 점 4개는 신뢰구간이 아니다.')
    r.h('모형의 한계와 일반화')
    r.p('전력·열 정확도 gate는 FAIL이고 API-J/AP는 모형 예측이다. CPU3 전력·열·간섭과 기기에서의 예측·NN·제어 비용은 미측정이다. AP 실측 지원 상단 46.6℃ 밖은 외삽이다. GPU 우선 정적 기준선과 고정 두 템플릿의 결과를 가장 강한 모든 기준선·기기·분포의 우위로 확대할 수 없다.')
    r.p('RL·CEM은 통합 행동 선택 함수를 학습·탐색으로 정하는 대안이다. 산업공학 방법이므로 필수라는 근거는 없다. 선행 논문은 검토할 이유를 주지만 우리 정책의 추가 성능 기여를 대신 증명하지 않는다. 교사 없는 별도 실험의 불리한 결과도 보존한다. 사실 중심 버전과 함께 읽어야 한다.','small')
    return r.finish()

outputs=[fact(),positive()]
manifest={'date':'2026-10-19','outputs':outputs,'primary_methods':MS,'RR_definition':'Nonpreemptive classification/detection queue rotation, one dispatch per turn; skip unexecutable queues; FIFO inside queue','source_summary':str(SCI/'artifacts/G001/SUMMARY.json'),'source_summary_sha256':hashlib.sha256((SCI/'artifacts/G001/SUMMARY.json').read_bytes()).hexdigest(),'new_RR_environments':4,'reused_environments':12,'new_training':0,'new_measurements':0,'original_reports_preserved':True}
(QA/'REPORT_MANIFEST.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8',newline='\n')
print(json.dumps({'reports':2,'report_pages':9,'primary_methods':MS},ensure_ascii=False))
