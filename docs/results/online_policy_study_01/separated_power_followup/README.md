# 준비 조회 누락을 분리한 후속 수집

과거 원인 자체는 미확정. silent3초 listing timeout1회 직후 회수는 성공했다. 새 opt-in은 **warmup 승인 전** silent timeout/client reap 증거가 있을 때만1회 관측누락으로 보존한다. 원래 stack/result를 남기고 다음 정규poll에서 상태를 다시 확인한다. 이는 제한된 읽기 재확인 허용이며 실행 재시도0과 구분한다. 즉시 재명령/timeout연장/endpoint전환/재연결0. 두 번째timeout·명시적연결오류·환경/품질실패·승인후실패는중단. 관측누락은gate통과가아니며 승인파일은품질검증후한번만전달한다. 남은시간30초이하/기록실패면중단한다.

완료CPU개발1을 원본해시로 재사용, 남은PAR/SER개발2→기존절차계수동결→혼합확인6. 입력/APK/900ms sensor/공통창/모형/후속부하조건은동일. 준비조회누락 허용과 세션시점/초기조건 차이는 별도protocol metadata로 남긴다. 기존소비계획재개0, 성공자료제외0, 확인재적합0. 가열·설정변경0. 기존모드 fail-fast 유지. 연결 자체의 고장을 해결했다는 주장은 하지 않는다.

새plan_v2 SHA `7e220ae69265491943529380798174d989a0b68144a2e72f2804a6e8998b1384`. 예산8세션/본768+warmup64=832/runtime32/stage8·56/pull2/APKpush·설치0/고정1680초/전체7520초/ADB26000. 개발2090+동결180+확인5250; 동일APK불일치면중단. 실행재시도·대체·추가세션0, 준비관측누락허용 최대1/세션(기존명령·시간상한내).

관련PC9검사(관측3/후속2/기존경계4) 통과. 실제poll/공유root→가짜세션/선행import+동결/소비차단 및 원문CPUimport를 검증했다. 실기기안정성 보장아님. Check 기기0, 소스외부보존 separated_power_source_v2. Android변경/빌드0. 설치본5c284190…ba4c와 프로젝트서명 확인을 실행기에 맡긴다.

```powershell
& 'C:/Users/LG/Documents/D1Check_Arrival_Extension/separated_power_plan_v2/RUN_AFTER_APPROVAL.ps1' -Action Run -Approved -ExpectedPlanSha256 '7e220ae69265491943529380798174d989a0b68144a2e72f2804a6e8998b1384'
```

사용자의 수정·계속실행 승인으로1회 진행한다. 원본출력 separated_power_run_v2; 기존run_v1은stopped_no_resume보존. 기본/strict/experiment_ready=false유지. 확인결과를보고기준완화나후속계수탐색을하지않는다.

## Run02 결과와 공식창 승인 경계 보완

Run02는 병행개발1완료 후 직렬개발의 **warmup 승인 뒤 resident baseline**에서 thermalservice2초timeout으로중단. 이전 설명의 warmup승인전 추정은 회수 progress로 정정한다. 본96/warmup16/runtime8/staging2·14/pull1/APK0/ADB781/408.805초. 병행개발120초167.188049J/96완료·46마감/초기29.6°C. 두 번째 앱cleanup미회수, 계획상force-stop/최종ps부재. 같은root재실행0, listing gap사용0. 원본/receipt separated_power_run_v2, 작은판독 separated_power_run02 보존.

plan_v3 초안은 미소비로보존하며 실행하지 않는다. warmup이전만 허용하면 실제실패경계를 해결하지못하므로, **공식창/startAP 승인 전**의 읽기전용 listing/thermalbracket silent/reaped timeout1회만 관측누락으로 다루는 v4로동결한다. 앱 sampler는 준비중에도 thermal0/BAT0..35/비충전/배터리20이상/화면/메모리gate를계속강제한다. host실패표본으로 승인을허용하지않고 다음정규poll의 새thermalbracket이성공해야후속gate/공식창승인이가능하다. 값부적격·명시적연결실패·두번째누락·공식창승인후실패는즉시중단. timeout/주기/실행상한은연장하지않는다. host상태미확인은앱성공이아니다. baseline AP 누락은분석의기존coverage규칙으로별도차단하며0보간하지않는다.

기존CPU+PAR 적격2를모든파일해시로보존하고SER개발1→동결→확인6만실행한다. 새상한7세션/본672+warmup56=728/runtime28/staging7·49/pull2/APK0/고정1470초/전체6730초/ADB22800. root개발1300+동결180+확인5250. 실행재시도0, 읽기재확인용관측누락허용1/세션만별도표시. 동일APK5c284190…ba4c재사용/Android변경0. 부하조건·900ms계측·기존모형/strict불변. 준비기록의프로토콜차이와다른시점은보존한다.

실제poll의 warmup→baseline→common승인 경계까지 fakePC검증8건, 기존계획/모형/root4건통과(총12). 최초개별테스트만으로장시간안정성을주장하지않는다. 실행판정은원본3개적격/식별통과후확인6, 오차기준사후완화0.

## 최종 상태

plan_v4 SHA `a631fa2edab1f65f763fbb4d3115637116e7674130ca784ce49c3b5269105a95` 1회 완료. 모든 위 Run 명령은 역사적 기록이며 소비 계획을 다시 실행하지 않는다. [최종 결과·오차·소비](../separated_power_final/README.md). v2 중단·v3 미소비 초안 보존. 실제 성공 실행의 관측누락 사용0회.
