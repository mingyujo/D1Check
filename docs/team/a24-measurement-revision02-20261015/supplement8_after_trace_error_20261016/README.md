# 계측 경로 오류 보존과 미실행 8조건 계속

**05:01:17 KST에 미실행8을 최초 시작했다.** 로컬 메타 `output/A24SUP12C1/job.json`, 원물 `Documents/A24SUP12C1`, 기존 보완12의 전역원장 `A24SUP12_GLOBAL`을 공유한다. 현재실행여부는 [고정현황](../LIVE_PROGRESS.md)과 실제owner/START/outcome/stop으로 확인한다. 같은 명령을 중복 호출하지 않는다.

## 실제 오류와 복구

기존 보완12에서 유휴2·분류GPU32의PerfettoOFF가 정상 완료된 뒤, ON은04:54:28 KST에본요청시작전실패했다. 실제 stderr는 `/data/local/tmp/a24-…-perfetto.pbtxt`를열지못했다는errno13/Permission denied이며명령exit1·0.079초다. 원outcome `FAILED_PRESERVED`, APP1/본요청0/예정32미실시·원예산소비를그대로보존했다. 설치·모델·성능·전류단위의실패로해석하지않는다.

같은APP/START를재전송하지않고, 앱의준비후600초대기가스스로끝나도록기다렸다. **05:00:21**에같은실행을읽기로추가회수해 `SYNCED_AND_CLOSED`·`DRAINED`/실제반환·32건UNFINISHED·MAIN이벤트/START/claim/승인업로드부재를검증하고닫힌자기프로세스부재를확인했다. 준비추론파일8개는원자료에남아있으며본요청성공으로계수하지않는다. 원실패를정상으로고치거나예산을돌려주지않았다.

[Perfetto공식설정안내](https://perfetto.dev/docs/concepts/config)와 [Android실행안내](https://perfetto.dev/docs/learning-more/android)는Android12이상의설정파일에 `/data/misc/perfetto-configs`를안내한다. 별도의경로수정검증을준비하고있다. 이8조건은모두PerfettoOFF이므로경로문제와분리해계속한다. 현재파일접근거부를숨기거나권한·보호설정을변경하지않는다.

## 미실행8의 고정 범위

원보완12의ordinal4~11을그대로사용한다: 최초기능CPU252 → 최초개발CPU252 → 옛확인저부하PAIR64 → 옛중단혼합EDD128 → W1CPU252 → W3GPU252 → C9EDD128 → R2PAIR128. **8조건·1,456본요청**이다. 처음3정상32와미실시ON32를더하면원보완12의예정1,520과일치한다. 원실패ON의32를0성공·계산없는에너지0으로대체하지않는다.

새ID를발명해기소비4개를반복하는경로가아니다. 기존보완계획의아직미사용인8개ID만새방문에서처음실행한다. 원계획·8조건의처방/요청/도착/기한·모델/입력·APK·MAIN±0.5℃/안정60초/0.1℃분/최대공백10초/준비후600초·완료/반환을유지한다. 원85+보완12=97의예산을그대로사용하며추가예산0이다. 앞4개APP소비와후속8을같은전역원장으로계수한다.

원보완12전체가이번재개만으로정상12가되는것은아니다. 이8이모두완료돼도 **11정상+ON실패1**이다. 새로운OFF/ON대조2개와새저부하2/혼합4는별도범위이며원독립확인40을채우는자료가아니다.

## 검증과 버전

- 엄격한실패검증기PC3: MAIN흔적·미닫힘·START/claim·성공또는불명확한trace시작을차단한다.
- 미실행범위PC1: 정확한앞4상태와8개미사용순서만허용하고추가/기소비/다른실패를차단한다.
- 실제8개manifest의authorization결합PC통과, 신선한동일기기/APK·SOC·비충전·화면·프로세스·미사용경로검사후시작했다.
- 원source183에감사/검증4파일만추가한 **source187 SHA `0e32c1e169ad86bd377afe92c35ee6a969a4f84fbdff2033909c6583a65af0c2`**. 원179·기존controller·앱코드/APK는불변이다. runtimeHEAD054742f+명시된WIP/정확한파일SHA로구분하며실제childPID18920·parenttool1054다.

[추가실행계약](EXECUTION_CONTRACT.json) · [PC8검산](PC_VERIFICATION.json) · [원실패닫힘증거](CLOSED_FAILURE_RECOVERY.json) · [실제시작버전](RUNTIME_CONTEXT.json) · [소스SHA](SOURCE_SHA256.json).

```powershell
# 다음은 PC 검사이며 실제 실행을 재시작하지 않는다.
python -B -m unittest discover -s tools -p test_d1_a24_failed_trace_prestart.py -v
python -B -m unittest discover -s tools -p test_d1_a24_supplement_continue.py -v
# inspect는 시작전전용이다. 이미worker/원물/APP가있으면다시실행하지않는다.
```

J미판정/AP HAL·물리표면미검증/experiment_ready=false를유지한다. 새자료를보정에썼으면독립검증이라고부르지않는다. 같은폰재연결최대20분·SOC10%이상·비충전·사용자중지/이동우선이며, 마지막5분저장예약은유지한다.
