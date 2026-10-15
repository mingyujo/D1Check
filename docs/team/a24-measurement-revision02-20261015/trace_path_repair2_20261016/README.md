# Perfetto 설정 경로 수정: 새 OFF/ON 대조 2회

**현재 PC구현·검증 및 직렬대기 등록 완료, 새APP·MAIN·세션소비0**이다. 실제기기에서수정된경로로계측에성공했다고아직표시하지않는다. [현재진행](../LIVE_PROGRESS.md)과실제원장을대조한다.

기존보완ON은 `/data/local/tmp`에전달한설정을Perfetto프로세스가읽지못해errno13/exit1로본요청전에실패했다. 원실패·APP예산1·32미실시와자체종료/자원반환/닫힘증거를보존했다. [원인·미실행8계속](../supplement8_after_trace_error_20261016/README.md).

[공식설정문서](https://perfetto.dev/docs/concepts/config)와[공식Android안내](https://perfetto.dev/docs/learning-more/android)는Android12이상에서 `/data/misc/perfetto-configs`를설정폴더로안내한다(2026-10-16조회). 별도controller의설정전달경로만이폴더로바꿨다. 원controller·APK·스케줄링·준비추론·MAIN판정·trace설정바이트/210초/64MiB상한은그대로다. 보호설정이나권한을바꾸는경로가아니다.

## 고정 범위와 예산

새ID로 **동일분류GPU32건 OFF → ON, 총2회·64본요청**만수행한다. 기존요청은행바이트·모델/입력·도착/기한을유지하고첫OFF의준비후첫적격안정60초에서고정한기준을ON과공유한다. ±0.5℃·0.1℃/분·최대공백10초·준비후600초는불변이다. 오래전OFF의시작상태와다른날의ON을그냥짝짓지않는다.

사용자의오류자율해결·완료지시를공정한수정검증2시도로제한했다. **기존103회원장·범위를보존하고별도2회/계산상최대105**를둔다. 사용자가숫자105를직접지정했거나무제한재시도를승인했다고기록하지않는다. 옛실패ID재실행·예산환급·원독립확인40성공대체는0이다. 새자료는실패를본뒤추가한계측검증자료다.

현재미실행8완료 → 이새OFF/ON2 → 새같은비교군6을단일기기에서직렬로수행한다. 구큐17·구새6대기는HELD보존하며, 새감독메타 `output/A24FOLLOW18/WAIT_PIPELINE_ONCE.py`/OWNER/LIVE/각STARTED/STOPPED/QUEUE_STOPPED를확인한다. 대기중기기명령0이고각실행직전동일폰/APK·SOC10%이상·비충전·화면·프로세스·미사용ID를다시읽어확인한다.

## PC 검증과 실제 검증의 구분

PC3검사와실제2manifest의2authorization결합이통과했다. 정확히OFF/ON2·동일입력·기준공유를검사하고입력/trace설정/기준분리/추가시도를차단했다. controller원문대조에서등록import·자기경로·설명문과Perfetto설정폴더만다름을확인했다. **전체AST가동일하다고표시하지않고, 설정경로변경을명시**한다. 새APK빌드·설치는0이다.

메타 `output/A24TRACE2/job.json`, 향후원물 `Documents/A24TRACE2`, 별도원장 `A24TRACE2_GLOBAL`. source187은기존보완source183+새trace관련4파일이며, 미실행8감사의동일한파일수187과는내용·SHA가다르다. 정확한버전은아래SHA와실제시작context로확인한다.

[고정계획](plan.json) · [실행계약](EXECUTION_CONTRACT.json) · [PC2승인결합](PC_VERIFICATION.json) · [원문변경범위](LIFECYCLE_IDENTITY.json) · [소스SHA](SOURCE_SHA256.json) · [분석계약](ANALYSIS_CONTRACT.json) · [유한예산](BUDGET.json).

```powershell
python -B -m unittest discover -s tools -p test_d1_a24_tracepair.py -v
python -B tools/d1_a24_tracepair_runner.py inspect output/A24TRACE2/job.json
# inspect는최초시작전전용. OWNER/원물/APP가있으면기존명령을재호출하지않는다.
```

실제trace회수성공과ftrace자료원/유실검증·계측오버헤드해석은별도로검사한다. 표면온도·하드웨어전력계·검증된에너지J가아니며 Jnull/AP HAL·표면미검증/experiment_ready=false를유지한다. 새2/새6을원독립5반복CI에합산하지않는다.
