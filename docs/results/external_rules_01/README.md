# 기존 시스템 판단 규칙의 PC 비교

EXTERNAL-RULES-11, 2026-10-07. [오프라인 화면](index.html) · [한국어 보고서](../../REQUEST_EXTERNAL_RULES_PC_20261007.md) · [사전 대응표](mapping.md) · [원 출처·commit·파일 SHA](sources.json).

Ente Android의 건강·활동에 따른 배경 시작 허용, Band 기본 HEFT의 요청/worker 선택 흐름을 별도 adapter에서 실행한다. Ente 상태 predicate 자체는 A 수준이고, 일반 탐지 요청에 적용한 일정과 Band whole-request 축약은 **제한적 재현 B**다. 외부 프로그램 전체·원 논문 시스템·제품 우열 비교가 아니다.

**완료:** 1,056행/69,696예정 요청·18관련검증·전체lane/분모 감사·8PNG/SVG·공유그림 동일재현·오프라인필터 통과. 본비교 실패/진단1,057환경+fixture6=이번1,063환경. Band 적용은 지속12조건 전량·기한 유지/강한EFT 대비평균J−0.131672/최고AP−0.021760/면적−1.817722. 우리열·에너지2규칙은 지속12조건 모두기한위반이있었다. Ente 일부합성상태는큰지연·미완료. 정확한 원수치와범위는보고서/전체CSV를따른다.

## 계약과 지원

- `contract.json`, `mapping.md`, `inputs.json`, `sources.json`을 결과 전에 고정했다. 4 seed×4 부하×3 처리문맥=48조건. 자원 배정8정책384행, 시작 허용7합성 상태×2정책672행, 합계1,056행. 정책 조정·RL·추가 실측0.
- A24 동결 `online-policy-model-v1`과 초기 preload를 그대로 쓴다. 분류CPU/GPU·탐지CPU, 검증된 분류GPU+탐지CPU 병행만 허용한다. 탐지GPU/S26/NPU·새 전력/열/스로틀 계수를 넣지 않는다. 평균·짧은·긴 문맥은 개발 자료의 전체5단계 시간벡터 민감도이며 새로운 독립 추론 반복이 아니다.
- 긴급 응답은 output_ready, 일반 응답은 persist_complete. 저장/worker release 뒤 실제 lane 반환까지 자원 점유를 유지한다. 전체 예정 요청의 완료·기한 실패를 먼저 보고한다. 0~120초 전체기기 J, AP35~180초. 미완료는 부분 처리 J로 표시하고 AP180·완전 작업 절감 판정을 null/차단한다. AP 안전 한도 및 초과 시간은 미확인이다.
- 자원 비교: 항상 시작 허용, 기존 CPU/SPLIT/EFT/공유EDF/공유EFT/에너지AP/큐에너지AP를 설정 변경 없이 비교한다. 강한 동적 대조는 공유EFT다. 정적 CPU·분류GPU/탐지CPU를 함께 보고 고정 배정의 손익도 남긴다.
- 시작 허용 비교: 양쪽 모두 원 EFT 하위 배정. Ente gate는 일반 탐지 시작에만 작용하고 긴급 분류는 동일하게 허용한다. 배터리·BAT·OS thermal·활동은 사전 고정한 외생 합성 신호이며 실측 행동이나 AP 변환값이 아니다. Ente foreground gallery/override=false, consent·모델 준비·네트워크·app resumed 같은 나머지 전제는 성립하는 범위다. stream arbitration/사진 전체 pipeline/앱 lock·다운로드는 재현 범위 밖이다.
- Band: reserve=false·전체 FIFO window, 같은 model/progress 중복 검색 제거, 최소예상계획이 가장 큰 요청 우선, busy-best worker yield를 보존한다. expected는 원 Invoke 시간에서 전체5단계 lane 시간으로 바꾸었고 완료 관측 뒤 EMA .1로 갱신한다. subgraph/전송/DSP/NPU/worker 내부 예약을 제거한 핵심 단위 변경이 있으므로 원 Band 알고리즘과 동일하다고 쓰지 않는다. 원 SLO는 미지정 경로이며 우리 기한은 외부 서비스 평가다.
- Band LSF early-drop, MediaPipe LIVE_STREAM busy-drop은 전량 완료 요구와 맞지 않아 주 비교 보류. LiteRT의 scheduling metadata 전달은 독립 요청 배정 정책으로 취급하지 않는다. NPU Manager의 load/priority/선점 기능은 확인됐지만 현재 엔진의 NPU 모델·비용·입력과 구체 source 정책 commit이 미확인이다.

## 작은 검증과 오류 기록

source 조건·20%/42°C/120초/15초 경계, 열 상태/지원불가 fallback, FIFO·worker 동점, largest-shortest 순위, busy yield, 관측 뒤 EMA, no-future/private lane 거부, 원 EFT 일정 보존, 미완료/비선점의14검증을 먼저 통과했다. 최초10개 pilot을 본 배치에서 재사용한다.

198개 저장 뒤 기존 엔진의 독립 반올림 때문에 절대 시각 차와 상대 응답이1ns 다른 검사가 실패했다. 정책·기한 판정·원 데이터는 유지하고 감사에만 표현 차1ns를 허용했다. 2ns 차를 거부하는 추가 경계 검증과 부분 J/분모/null AP의2검증을 통과했다. 실패 당시 raw/error·사전 소스·수정 소스와 진단1환경을 보존한다. 완료198행은 재계산하지 않는다. 등록된1,056개 성공 비교 범위와 실패/진단을 포함한 실제 소비를 구분한다.

777행 뒤 내부2,400초 시간검사 종료와 사용자 중지를 보존했다. 최신 재개 지시로777개 SHA를 확인하고 남은279행에만 별도1,200초 운영구간을 등록했다. 원 비교 입력/판정/정책·전체소비는 초기화하지 않았다. raw없는 공유 checkout의 새 결과폴더 I/O와0재계산 캐시 재호출 시험을2환경으로 확인했다. evaluator는 공유 기존 CSV를 덮어쓰지 않고 자기 폴더에 저장하며 report가 명시된 출력폴더로 공유 CSV를 내보낸다.

## 재현

Windows Python3.11/기존 NumPy·Matplotlib·Torch 환경에서 실행한다. 기기 명령·설치는 필요 없다. 준비는 이미 공유된 계약/입력을 쓰며, 등록 완료 자료를 다시 조사해 임계값을 바꾸지 않는다.

```powershell
$env:MKL_THREADING_LAYER='SEQUENTIAL'
python -B -m unittest tools.test_d1_external_rules tools.test_d1_external_rules_report -v
# 별도 새 경로에서 동일1,056조건 재현; 기존 raw/결과를 덮어쓰지 않는다.
python -B -m tools.d1_external_rules_study run --folder output/external_rules_20261007_reproduction
python -B -m tools.d1_external_rules_report --folder output/external_rules_20261007_reproduction --output output/external_rules_20261007_reproduction_report
```

학습·환경 실행 없이 공유 CSV와 대표 기록으로 그림/화면만 다시 만든다.

```powershell
python -B -m tools.d1_external_rules_report --shared --output output/external_rules_20261007_figures
```

공유물은 작은 코드·계약/출처·입력·CSV·대표 기록·PNG/SVG·검증 JSON이다. 전체 raw 1,056묶음·worker 로그·조사 원문은 로컬 `output/external_rules_20261007_v1/`에 보존하며 모델 binary·키·개인 경로를 포함하지 않는다. `experiment_ready=false`·원 기본/strict는 유지한다.
