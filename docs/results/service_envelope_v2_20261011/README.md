# 서비스 Envelope V2: 부분 개선과 전체 실패

새171/192환경·학습0·오류0·11187/11187요청 완료. native gate2+개발24+새 확인48×3역할144+대표1을 보존했다. 개발 Band/Triton48행은 이전 완료 SHA로 재사용했고 새환경으로 세지 않았다.

CPU-only 개별 응답 보호로만 탈락한273개 저장 슬롯이 개정 근거다. 반복 슬롯이지 독립 이득273회가 아니다. 일반 기한/위반/지각 기준은 유지하되 개별 응답 불변을 제거했고 참조 P95를 드레인 ECT 앞에 두었다. 이는 일부 과제약과 순위의 정렬이며 전체 미래 P95 보장을 뜻하지 않는다.

| 정책 | 일반 기한 위반 | 조건별 P95 평균ms | 평균 ΔJ | 평균 ΔAP°C |
|---|---:|---:|---:|---:|
| Band | 42 | 338.107524 | +0.000000 | +0.000000 |
| Triton | 39 | 372.576200 | +0.448761 | +0.019623 |
| CostV2 | 45 | 364.197697 | -0.069924 | -0.004618 |

**전체 원strict FAIL·유망0·최종 자동채택0**이다. 평균 비용 감소를 일반 추가 위반/P95 악화와 바꾸지 않는다. V1과 V2는 서로 다른 새 확인 seed이므로 표의42/45나AP평균을 직접 전후 개선으로 합치지 않는다.

## 부하군별 범위

- low: Band 대비 통과9/12, Triton 대비 통과12/12, ΔJ+0.000000J/ΔAP-0.006681°C/ΔP95+0.000000ms/일반위반차+0.
- queue: Band 대비 통과12/12, Triton 대비 통과12/12, ΔJ+0.000000J/ΔAP+0.000000°C/ΔP95+0.000000ms/일반위반차+0.
- burst: Band 대비 통과9/12, Triton 대비 통과6/12, ΔJ+0.010812J/ΔAP-0.002558°C/ΔP95+0.000000ms/일반위반차+3.
- sustained: Band 대비 통과4/12, Triton 대비 통과6/12, ΔJ-0.290509J/ΔAP-0.009235°C/ΔP95+104.360689ms/일반위반차+0.

사전 고정한 부하군의 조건부 결과는 전체 통과 판정을 대체하지 않는다. 정책에 미래 trace의 low/burst 이름을 넣어 유리한 경우만 실행하지 않았다. 현재 관측 도착 이력으로 미래 몰림을 보장할 수 없다.

실제 냉각 선택258회/추가56.120375초, slot0 외 선택258회. 대표96은 Band exact=True이며 새 기기 재생0이다. AP는 표면 온도가 아니고 작은모형차이는폰절감입증이아니다. 기존 실측4회/원PPO512/새V1학습을 보존했다.

[화면](index.html) · [CSV](comparison.csv) · [부하군/선택](summary.json) · [설정](execution_contract.json) · [기능/원장 검증](verification.json)

```powershell
python -B -X utf8 -m unittest tools.test_d1_service_envelope_v2_policy -v
python -B -X utf8 -m tools.d1_service_envelope_v2_run check
python -B -X utf8 -m tools.d1_service_envelope_v2_report
```

현재 workspace 원gz 후처리이며 새환경/학습/기기/fit0이다. 완료run/등록을 반복해예산을초기화하지않는다. 기존V1 actor를V2로재사용하지않는다.


## Stored ledger diagnosis

[Service loss diagnosis](service_loss_diagnosis.json): the three extra normal misses are the same burst request22 at seed835110102 across three sensitivity contexts, not three independent losses. Cooling0 in these cases. First shared-prefix divergence is CPU classification rather than GPU classification+CPU detection; subsequent D22 CPU dispatch is165.216ms later. The observed D count1 makes its minimum arrival gap unavailable, while existing public mixed-arrival D-utilization estimate is3.84518. Extending congestion protection from cooling to routing is a future registered hypothesis, not a confirmed fix. Long-context service is not WCET.
