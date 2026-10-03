# 배경 활동 개발4 Run02 — 수집 완료·시스템 trace 계약 부적격

> 2026-10-03 PC 정정: 이 문서의 과거 J 결과는 10~30초 초기화로 보존한다. 동결 모형의 −20~30초 계약 복원과 선택된 적격 네 세션의 정정값은 [후속 판독](../background_identification_pc_v1/README.md)을 따른다. 과거 수치 재현에는 `--legacy-preload-window`를 추가한다. AP·원자료·실행 판정은 변경하지 않았다.

## 결과와 경계

2026-10-03 사용자 `ㄱㄱ`로 새 plan_v3의 1회 실행을 승인했다. 실행 HEAD `afe2e67253e42ac88ca51120a1c07267cccf650a`, 작업 트리는 깨끗했다. 실제 branch/worktree/원격 HEAD 일치와 기기 없는 Check를 확인한 뒤 현재 devices 조회1회로 유일 A24 transport를 선택했다. 이후 실행기에서 모델·fingerprint·하드웨어·설치본·환경을 확인했고 transport 전환은 없었다. 설치된 APK가 후보 SHA `9d8d55c2742b485e18f8a0812b70bf33ed66f9185c6d47b80c39f086e73fd932`와 동일해 배포 없이 진행했다.

**수집 4/4 완료, 시스템 trace의 사전 내용 적격성은 4/4 부적격**이다. 원래 FINAL_RECEIPT의 `completed_descriptive_only`는 수집·앱 적격성 판정이며 시스템 trace 내용이나 독립 모형 확인 PASS가 아니다. 사전 동결 코드·계획·APK·gate·timeout·조회 주기·부하를 실행 중 바꾸지 않았다. 새 계획/재시도/추가 실행·후보 적합은 없다. 종료된 v2와 그 원자료를 보존했다.

## 실제 소비와 종료

|항목|실제 / 승인 상한|
|---|---:|
|개발 / 독립 확인|4 / 4; 확인0|
|본 요청 / warmup / 추가 적격성|192 / 192; 32 / 32; 0 / 0|
|총 명시적 추론 / runtime|224 / 224; 16 / 16|
|staging / 파일|4 / 4; 28 / 28|
|설치본 host pull / trace pull|1 / 1; 4 / 4|
|APK push / 설치|0 / 0; 0 / 0|
|ADB|3,260 / 13,036 (실행기3,259 + 착수 선택1)|
|기기 작업 누적|1,243.243초 / 4,454초 (실행기1,241.094 + 선택2.150)|
|첫 조회→entry 종료 wall|1,263.596초; 명령 사이 공백 포함|
|재시도 / 대체 / 추가 세션|각0|

고정 관측은 4×(baseline30+common120+cooling60)=840초, 대기는 3×90초다. 나머지는 준비·조회·회수·cleanup이다. 정상 소요시간을 timeout 합계로 보고하지 않는다. 공식 공통창은 각 `common_boundary.json`의 start→planned_end 정확히120초이며 실제 common_end는 15–87ms 늦어도 적분창을 늘리지 않았다. 본192의 시작·반환·output_ready·저장·worker_release·lane_available를 회수했고 전부 succeeded다. runtime_start/return 각16, warmup_start/return 각32를 원문 events로 확인했다. 호출 미확인·미완료0은 이 기록에 근거하며 기록 부재에서 추론하지 않았다.

- 각 세션 앱 `cleanup.json=completed`, sampler_failure=null. 정상 finish_requested가 기록됐고 lifecycle_cancelled/앱 실패는 이번 자료에서 관측하지 않았다. 과거 원인이 해결됐다고 해석하지 않는다.
- 각 세션 앱 증거 회수 후 host force-stop1회, 4세션 총4회. 정상 앱 cleanup과 host 정리는 다른 사실이다. 마지막 저장 command3253 ps에 대상 패키지/전용 process 부재, 뒤 thermal0; 이는 종료 시점 증거이며 현재 상태를 새로 조회한 것은 아니다.
- 자신의 detached trace stop·stat·pull 각각 수행, 원격 trace 삭제0. trace 크기17MB 안팎·pull SHA 보존. 네 trace의 파일 회수 성공과 내용 적격성 실패를 구분한다.
- Python exit0·entry error null, 종료 뒤 PC에서 parent/child PID 부재 확인. checkpoint의 상세 host_identity=null 한계도 보존한다. PID만으로 다른 프로세스의 소유권을 인정하거나 종료하지 않았다.
- ADB client returned3,239/nonzero20, timeout0. nonzero는 도움말 exit1/파일 부재 확인 등의 허용된 경로이며 종료하지 않은 client나 연결 소실은 기록되지 않았다. daemon/reconnect/설정/다른 앱을 조작하지 않았다. 실행 후 추가 기기 명령0.

## 실제 점유·초기조건·진단 계산

CPU96: 분류CPU 7.981초 +탐지CPU29.872초 +resident idle82.147초. PAR96: 분류GPU 단독0.435초 +분류GPU·탐지CPU 병행13.154초 +탐지CPU 단독17.384초 +resident idle89.028초. C0 전·후는 resident idle120초다. 이 상태는 dispatch→lane_available에 근거하며 단순 제출간격으로 병행을 보장하지 않았다. 96개 요청은 CPU/PAR 각각 등록대로48분류:48탐지다. 둘 다 전체 도착 분모의 deadline 서비스 성공96/96, 완료 응답 P95는 CPU5351.028ms/PAR659.090ms였다. 개발 대조1회씩의 관측이며 독립 정책 우월성 증거가 아니다.

공유 동결 모형 SHA `5682082a936b7c83efeee747ceeb64fd0c64f0bef8765bbf1b90b807db872db2`의 기존 전력 increment·AP beta/k/g를 그대로 사용했다. 과거 fixed-regimen 모형과 혼동하거나 다시 맞추지 않았다. 에너지는 실제 일정과 **각 세션의 부하 전 common10–30초 평균 전력**에 조건부로 계산했다. AP는 baseline부터common35초 이전의 AP만 초기화에 사용했다. 이후 관측 AP·전류를 예측 입력으로 넣지 않았다. 0–120초 에너지 전체가 세션 시작 전의 순수 prospective 예측이라는 뜻은 아니다. 예정 도착부터의 E2E 예측을 새로 검증하지 않았다.

|조건|시작AP°C|관측120초J|조건부 예측J|예측−관측J|AP MAE°C|AP 최대오차°C|
|---|---:|---:|---:|---:|---:|---:|
|C0_PRE|27.6|138.729|135.832|-2.897|0.631|0.777|
|CPU_URGENT_ONLINE_V1|27.9|171.210|161.438|-9.772|0.207|0.903|
|B2_PARALLEL_ONLINE_V1|28.1|157.006|152.319|-4.688|0.278|1.105|
|C0_POST|28.2|141.342|142.755|+1.413|0.228|0.296|

AP 점수 창은 common35초부터 마지막 냉각 AP까지: C0_PRE177.945초, CPU179.234초, PAR178.192초, C0_POST177.588초다. 전력 점수의120초와 혼동하지 않는다. AP 전체곡선 최고온도 부호오차는 각각 +0.655/−0.468/+0.421/+0.296°C다. 사전 정확도 허용폭이 없으므로 PASS/null 정확도 판정을 임의로 만들지 않았다. 현재 모델에는 이번 질문의 등록된 온도 한도 초과시간 기준이 없어 새 숫자를 만들지 않았다.

원래 개발 시작32.5–34.0°C 범위 대비 모든 시작 AP는 밖이다. numeric AP observe-v2는 유효·신선한 값으로 시작하되 이 하한을 실행 차단으로 복사하지 않았다. 낮은 AP를 안전 인증하거나 strict 초기조건을 확대하지 않는다. 프로토콜은 self CPU·과거 입력·system trace가 추가된 개발 블록이며 추가 계측 비용은 관측 J에 포함돼 있다. 초기 AP·배터리·열 이력·관측 프로토콜이 달라 CPU/PAR 총J를 곧바로 순위/절감으로 쓰지 않는다. raw=mA는 조건부 해석, 절대 전류·에너지 정확도 미인증이다. BAT온도·SOC/사용시간·throttle·정책 효과 검증은 아니다.

## trace와 과거 입력 판독

공식 Windows TraceProcessor v58.2-add693d8b의 로컬 cached exe를 사용했다. [공식 wrapper](https://get.perfetto.dev/trace_processor)의 Windows SHA·바이트 크기와 일치하며 [provenance](processor_provenance.json)에 기록했다. 원래4 SQL의 exit는 전부0이며 BOOTTIME clock equality 검사는 통과했다. **네 loss.csv에 config_write_into_file_no_flush=1**이 있어 기존 `d1_background_activity_readout.summarize`가 전부 거부했다.

[버전 고정 공식 stats 정의](https://github.com/google/perfetto/blob/v58.2/src/trace_processor/storage/stats.h)에 따르면 이는 write_into_file을 켠 상태에서 flush_period_ms를 지정하지 않은 kError이며 processor 메모리 사용 증가에 관한 진단이다. 이것만으로 실제 sched 데이터 손실·무선 단절·기기 결함을 확정하지 않는다. 현재 config에는 file_write_period_ms=5000이 있으나 **file write 주기와 producer flush 주기는 서로 다르다**. 과거 안내의 “flush5초” 표현은 정확하지 않았으며 이 구분을 이번에 기록했다. 실행 중 config를 수정하거나 오류 행을 빼서 사전 계약을 사후 통과시키지 않았다.

따라서 system benchmark/tracer/other/unknown CPU 귀속 결과는 null/contract_ineligible이다. 원래 SQL CSV·flags·완전 trace는 외부에 보존해 다음 PC 판독에서 재사용할 수 있다. 공식 경고의 성격과 CPU coverage·loss를 구분하는 별도 PC 검토가 필요하며, 이 결과가 즉시 새 실측을 요구하지는 않는다. future config 수정 역시 이 실행의 원래 판정을 소급 변경하지 않는다. 시스템 trace 정보로 GPU/무선 rail power나 에너지 원인을 식별했다고 하지 않는다.

별도로 앱 power_sample의 self_cpu_ms는 정상 증가했다. 공통120초 누적 CPU delta(표본간 보간)는 C0_PRE7.378/CPU46.406/PAR47.106/C0_POST7.339 CPU초다. CPU초는 앱 프로세스의 합산 CPU 시간이며 wall초나 기기 전체 CPU 점유가 아니다. AP/전력과의 공변 관측이지 원인 입증이 아니다.

각 세션 causal_power_input14개, 합계56개가 available이고 ready≤issue·window_end≤issue·future_AP=false를 검증했다. 실제 관측 격자는 약10.8초이며 과거10초 창이다. 온디바이스 task_residual_w=null은 계약대로 유지했고 새로운 gamma를 적합/채택하지 않았다. 독립 확인0, 현재 기본/strict/experiment_ready=false 불변이다.

추가 PC 조회(기기 명령0)에서 네 trace 모두 `config_write_into_file_discard=1`, severity=data_loss도 확인했다. 원래 SQL은 severity=error 또는 일부 이름 패턴만 포함해 이 행을 놓쳤다. 위 flush 오류 때문에 최종 검사는 이미 거부됐지만 **data_loss severity 전체를 포함하지 않은 판독 결함**이 별도로 있다. DISCARD 구성의 위험 경고와 실제 손실량은 구분하며, 실제 손실량을 여기서 임의 추정하지 않는다. [추가 flags](trace_flags.json). 기록된 file write 주기와 실제 flush 주기/버퍼 설정을 PC에서 수정·검증하고, 다음 계획에서 trace 적격성을 세션마다 판정해야 한다. 기존 결과/사전 부적격은 보존한다.

## 산출물·재현·다음 PC 행동

- [판독 요약](summary.json), [소비·해시](consumption.json), [오차표](metrics.csv), [에너지 CSV](energy_paths.csv), [AP CSV](ap_paths.csv), [그림](paths.png), [대시보드](index.html).
- 원본 `C:/Users/LG/Documents/D1Check_Arrival_Extension/background_activity_run_v3/FINAL_RECEIPT.json`; journal·명령·4세션 artifacts/trace 포함17,051파일·205,776,672byte. 원본 hash inventory와 분석은 분리된 `background_activity_run_v3_pc_analysis`에 보존했다. 원본 내용은 수정하지 않았다.
- 계획 `background_activity_plan_v3/collection_plan.json` SHA dbec1de3…ff501, registry BACKGROUND-ACTIVITY-DEVELOPMENT-03은 소비/종료 상태다. consumed Check가 기기 전에 차단됨을 확인했다. 계획을 재개하지 않는다.
- readout 새 코드의 결측/보간·초기화 정보누설·C0 정상 처리·원래 trace 오류/null·소비 미확인 차단2검사 통과. 처음 fixture의 JSONL 마지막 newline 누락으로 본문 전에 실패한 것을 고쳤으며 assertion은 유지했다. 새 APK 빌드0. 이것은 PC 분석 검증이며 장시간/기기 독립 예측 PASS가 아니다.

저장소 root에서(새 출력 폴더 사용, 기존 산출물 덮어쓰기 금지):
```powershell
python -B -m unittest tools.test_d1_background_activity_result
python -B -m tools.d1_background_activity_result --plan C:/Users/LG/Documents/D1Check_Arrival_Extension/background_activity_plan_v3/collection_plan.json --exports C:/Users/LG/Documents/D1Check_Arrival_Extension/background_activity_run_v3_pc_analysis --output '<새 PC 판독 출력>'
```

다음 행동 하나: **확보한 네 trace에서 flush 설정 경고와 실제 loss/clock/CPU coverage를 분리하는 PC 판독 보완**. 기존 사전 계약의 부적격 기록을 보존하면서 추가로 무엇을 관측할 수 있는지 판정한다. 새 기기 실행·다른 후보 적합·독립 확인은 이 턴에서 자동 생성/수행하지 않는다.
