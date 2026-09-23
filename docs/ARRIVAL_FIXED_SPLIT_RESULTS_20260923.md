# ARRIVAL-FIXED-01: 연결 중단 및 부분 결과

2026-09-23. **STOPPED_TECHNICAL_CONNECTION_NO_RETRY / 전체 평가 미완료**.
최소안27세션 승인은 `minimum_approval.json`, 동결 계획은 [설계 계약](ARRIVAL_FIXED_SPLIT_COMPARISON_20260923.md)을 따른다.
기존27세션 독립 평가의 `conditional_joint_primary_pass=false`는 그대로다. 이번 자료로 기존 FAIL을 변경하지 않는다.

## 실행·중단·회수

- 시작 HEAD `97225b1b4c2a493b34e986daedd64562478aad5f`, branch `feature/arrival-scheduling-20260923`, 시작 worktree clean.
- 충전 후13:19 KST에 같은 SM-A245N/serial R59W802RW5F/fingerprint, 배터리56%·충전 없음·32.0°C·thermal0·앱 프로세스 부재와 plan/source/APK hash를 확인했다.
- 승인된 명령 한 번 실행. 설치 `-r`, 초기/세션 사이120초 cooling, 기존 APK/정책/threshold/입력/4 resident runtime/CPU threads1 유지. 실행 중 KPI를 열람하거나 정책·분석 규칙을 바꾸지 않았다.
- 13:19:18~14:28:08 KST, **68.82분** 후 중단. 24번째 시도(index23)의 첫 `dumpsys thermalservice`에서 ADB device not found가 발생했다. Activity 실행·warmup 전 실패다. 이어진 force-stop도 연결 단절로 실패해 두 오류를 원본 그대로 보존했다.
- 사용자 재연결 후 동일 기기를 다시 식별했다. 해당24번째 UUID의 device output은 없고, 계획 내 output은 완료23세션만 존재했다. 미시도3세션 output도 없다. 새 Activity를 실행하지 않았다.
- 14:31 KST에 project force-stop·전체 process inventory로 프로세스 부재 확인. thermal0·배터리51%. 최초 cleanup 실패 기록을 지우지 않고 별도 `fixed_split_comparison_recovery_v1/recovery_receipt.json`에 복구 성공을 기록했다.
- **24/27시도 소비, 23세션 검증 완료, 실행 전 기술적 실패1, 미시도3. retry0·대체0·추가0.** 남은 세션을 이어 실행하지 않는다. 단순 재연결은 동결된 중단 규칙을 해제하는 승인이 아니다.

plan SHA `9812ce6ec8d04c43e9a072bf15d712a222304ca96e2a0033d564748decaa213f`;
APK SHA `1a8448abe1c78432870f1848676de61faefa83f64c9a6a3732d79f7a121f3612`.
측정에 영향을 주는 코드·APK·정책 변경 없음. 새 분석기는 사전에 정한 계산을 PC에서 구현했으며 별도 파일이다.

## 분모와 품질

| 정책 | 완료/계획 세션 | urgent 실행/계획 | normal 실행/계획 | 성공/계획 평가 요청 |
|---|---:|---:|---:|---:|
| CPU_URGENT | 8/9 | 13/15 | 37/39 | 50/54 |
| FIXED_SPLIT | 7/9 | 11/15 | 31/39 | 42/54 |
| CONDITIONAL | 8/9 | 13/15 | 37/39 | 50/54 |
| 전체 | **23/27** | **37/45** | **105/117** | **142/162** |

실제 도착142건 모두 성공: 실패·거절·만료·도착 후 미완료·late success0.
실제 도착 기준 성공률142/142=100%, 전체 계획 커버리지142/162=87.65%를 분리한다.
미실행20건은 실패 시도24의8건과 미시도25~27의12건이며 전체 계획 분모에서 제외하지 않는다. 미실행 요청을 성공·모델 실패·0ms 응답으로 대체하지 않는다.
warmup은184/216호출: 완료23세션 각각8호출, 나머지32호출 미실행. 개별 warmup event ledger가 아니라 `before_workload` 도달 전8호출 완료 코드 경로로 확인한 수다.

urgent deadline 위반0/37, normal 기한 내 완료105/105. 모두 engineering scenario(urgent2초/normal8초)이며 정책 우수성 근거가 아니다.
최대 arrival lag2.591ms(<100ms), 관측 thermal status는 전부0, memory admission257/257 admit.
표본 PSS 최대432.31MiB, 세션별 표본 평균의 전체 평균348.16MiB. true peak/headroom 또는 에너지로 해석하지 않는다.
완료23세션의 manifest/event/ledger/payload hash·배정 규칙·runtime/host cleanup을 재검증했다.
새 원본566파일의 분석 전후 hash 불변, 이전 연구 원본/분석/그림/plan/APK758파일도 불변이다.

## 조건별 기술값

아래는 각 정책의 **완료 세션 평균**이다. burst의 n이3/2/3으로 다르므로 이 표의 단순 평균 차이를 주 paired 효과로 사용하지 않는다.
긴급 지표는 세션별 nearest-rank P95=**긴급2건의 최댓값**(queue는1건)이며 모집단 P95가 아니다.

| 조건 | 정책 | 완료 n | 긴급 세션 max ms | 일반 평균 ms | makespan s | throughput req/s |
|---|---|---:|---:|---:|---:|---:|
| burst | CPU_URGENT | 3 | 419.57 | 1971.19 | 3.970 | 2.015 |
| burst | FIXED_SPLIT | 2 | 248.12 | 3592.27 | 6.952 | 1.151 |
| burst | CONDITIONAL | 3 | 425.44 | 1360.27 | 2.767 | 2.891 |
| low | CPU_URGENT | 2 | 152.95 | 626.99 | 9.161 | 0.437 |
| low | FIXED_SPLIT | 2 | 152.43 | 1187.73 | 9.172 | 0.436 |
| low | CONDITIONAL | 2 | 163.69 | 619.56 | 9.178 | 0.436 |
| queue | CPU_URGENT | 3 | 173.58 | 1477.04 | 3.202 | 1.874 |
| queue | FIXED_SPLIT | 3 | 145.72 | 2980.03 | 5.793 | 1.036 |
| queue | CONDITIONAL | 3 | 176.62 | 1098.17 | 2.490 | 2.413 |

응답은 예정 도착 기준 urgent→output_ready, normal→persist_complete.
makespan은 workload_start→마지막 기록 worker_release, throughput은 성공수/해당 makespan이다. 초기화·warmup·cooling·staging/회수는 이 throughput 구간 밖이다.
정책 집계는 세션 동일 가중이며, 전체 요청을 풀링한 percentile 또는 전체 wall-time throughput과 다르다.

## 사전 주 비교: 조건부−고정 분리

조건별 완전한 paired block만 대응했다. 주 burst는3개 중2개뿐이므로 **사전97.5% 주 CI는 산출하지 않는다**.
low도2/3으로 interval을 생략한다. queue는3/3이라 사전 지정 보조 분석의 pointwise95% paired t CI만 표시한다.
이는 전체 계획의 완료·확정적 정책 우월성·동등성·비열등성 판정이 아니다.

| 조건 | 완전 pair | 긴급 절대차 ms / 상대차 | 일반 평균 절대차 ms / 상대차 |
|---|---:|---:|---:|
| burst(주) | 2/3 | **+179.18 / +72.27%**, CI 미산출 | **−2216.13 / −61.69%**, CI 미산출 |
| low | 2/3 | +11.26 / +7.39%, CI 미산출 | −568.17 / −47.84%, CI 미산출 |
| queue(보조) | 3/3 | +30.90 / +21.19%, 상대95% CI[+4.41%,+37.97%] | −1881.86 / −63.15%, 상대95% CI[−66.86%,−59.43%] |

상대차는 각 block `(C−F)/F`의 평균이다. 조건별 n을 합쳐 하나의 주 표본 수로 쓰지 않는다.
주 burst 완전2pair에서 makespan 차 −4.175s(−60.06%), throughput 차 +1.730req/s(+150.35%)도 기술값이며 CI 미산출이다.
7개 완전 pair 모두에서 C는 F보다 긴급 세션 max가 크고 normal 평균응답은 작았다(burst2/2, low2/2, queue3/3 각각 같은 방향).
이는 현재 관측의 방향 일관성이지 누락 자료를 포함한 모집단 순위 안정성 증명은 아니다.

같은 기간 CPU 대조군도 보존한다. burst U−F(2pair)는 긴급+71.87%, normal−44.87%로 비슷한 상충을 보였다.
burst C−U는3pair에서 긴급+1.44%(pointwise95% CI −3.81~+6.69%), normal−31.00%(−34.15~−27.85%), makespan−30.30%, throughput+43.46%다.
이 보조 CI는 작은 n의 paired t 가정하 기술이며, 긴급의 구간이0을 포함한다고 동등/비열등 또는 '성능 유지'로 판정하지 않는다.
이번 측정에는 FIFO가 없어 새로운 우선순위 변경 효과를 직접 분리하지 않는다. 과거 FIFO 비교는 별도 자료와 기존 판정을 유지한다.

## 계산비용·메모리와 해석

burst의 기록된 선택 비용 합/세션은 U5.445ms(n3), F5.192ms(n2), C6.273ms(n3).
전체 정책별 세션 평균 PSS는 U346.13MiB(n8), F352.89MiB(n7), C346.06MiB(n8), 표본 최대는408.42/418.89/432.31MiB다.
조건 구성·n이 달라 이 전체 평균만으로 메모리 우월성을 판정하지 않는다. 원값은 session_kpi.csv에 있다.
`policy_compute_ns`는 성공적으로 선택한 호출만 기록하며 빈 큐/선택 불가 호출을 포함한 총 정책 CPU 비용이 아니다. 응답시간에는 그 대기가 포함된다.
worker_release timestamp 이후 event fsync/dispatch callback이 있어 실제 lane 재사용 가능 시점까지의 비용을 완전히 계측했다고 주장하지 않는다.

관측은 **조건부 선택이 고정 분리를 모든 지표에서 지배하지 않음**을 보여 준다. 고정 분리는 urgent CPU를 확보해 긴급 응답에 유리했고, normal GPU 제한은 일반 응답·처리효율 비용과 함께 나타났다.
조건부는 일반 처리효율에서 유리했지만 긴급 응답 비용이 있었다. 이것은 현재 두 규칙의 관측 차이이며 GPU overlap의 인과 효과를 별도로 식별한 결과가 아니다.
low에서는 makespan이 긴 유휴 도착 간격에 지배되어 처리효율 차이가 작다. deadline 전부0%도 정책 차별 지표가 아니다.
허용 가능한 긴급 지연 증가나 normal 이득의 가치를 사전 합의하지 않았으므로 보편적 승자를 선택하지 않는다. 단순 비유의는 비슷함의 근거가 아니다.

적용 범위는 A24·현재 분류/탐지 모델과 고정 입력·4 resident runtime·비선점·관측 thermal0이다.
다기기·다른 모델/입력·역할반전·임의 도착/overlap·열부하·에너지·통역/OCR·OS 스케줄링으로 일반화하지 않는다.
새 시뮬레이션은 실행하지 않았다. 종단간 응답을 서비스시간으로 넣어 대기시간을 중복 계산하지 않는다.

## 산출물·검증·재현

외부 root: `C:/Users/LG/Documents/D1Check_Arrival_Extension/`.

- 원본/실행 manifest: `fixed_split_comparison_minimum_run_v1/` (`run_attempt.json`, `run_error.json`, 각 attempt/validated/artifacts/host_cleanup).
- 복구: `fixed_split_comparison_recovery_v1/recovery_receipt.json`; 최초 연결·cleanup 실패를 보존한 별도 overlay.
- 최종 부분 분석: `fixed_split_comparison_minimum_analysis_v3/FINAL_REPORT.md`, `summary.json`, `session_kpi.csv`, `denominators.csv`, `paired_effects.csv`, `request_timeline.csv`, `raw_inventory.json`, `FINAL_RECEIPT.json`.
- 그림: `01_policy_kpi`, `02_conditional_fixed_effects`, `03_representative_gantt` 각각 PNG/SVG. 간트는 결과 무관 첫 burst replicate0 세 정책 전부이며 공통 시간축을 사용한다.
- 분석 출력v1/v2는 그림 표기·축 개선 전 초안으로 보존한다. v1/v2/v3의 summary/session/denominator/raw inventory는 semantic-equal이고 수치/판정 변경 없음.
- Python 분석 테스트5 PASS(작은 n의 t CI, paired 상대차, 실패 시 주 CI 억제, 동률/0분모, 중간 결과 분석 거부), synthetic 그림 생성 PASS, 실제142요청/23세션 artifact 분석 PASS, PNG 시각 점검. 무관한 빌드·실측 반복 없음.

PC 분석 재현(새 output 경로 사용, ADB 호출 없음):

```powershell
python -B -m tools.d1_arrival_fixed_analysis --plan 'C:\Users\LG\Documents\D1Check_Arrival_Extension\fixed_split_comparison_minimum_v2\comparison_plan.json' --results 'C:\Users\LG\Documents\D1Check_Arrival_Extension\fixed_split_comparison_minimum_run_v1' --output 'C:\Users\LG\Documents\D1Check_Arrival_Extension\fixed_split_comparison_reproduction_new'
python -B -m unittest tools.test_d1_arrival_fixed_analysis -v
```

기존 RUN_MINIMUM_AFTER_APPROVAL.ps1 **재실행 금지**. 이번 run은 복구까지 끝난 기술적 중단 상태다.
남은3시도를 이용해 failed FIXED_SPLIT을 바꾸거나 마지막 low3세션을 계속하는 것은 동결 규칙과 다르므로 수행하지 않는다.
추가 측정이 필요하면 현재 부분 결과를 공개한 상태의 별도 전향적 계획·새 예산으로 설계해야 한다. 우선 팀에서 긴급 지연과 일반 효율의 허용 상충을 검토하는 것을 권장한다.
계획/구현/PC 검증/부분 실측·복구/부분 분석은 완료, **27세션 전체 평가와 주 비교 추론은 미완료**다.
