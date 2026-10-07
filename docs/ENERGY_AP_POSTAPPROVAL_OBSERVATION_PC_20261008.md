# 승인 후 진행 관측 분리: PC 검증·v3 실행 계약 — 2026-10-08

이 변경은 [v2 무출력 listing timeout](ENERGY_AP_HISTORY_RECOVERY_RUN02_20261008.md)의 내부 원인을 밝혔다는 수정이 아니다. 단순 진행 관찰과 필수 환경 관측의 실패 의미를 분리한 **별도 opt-in host 프로토콜**이다. 사용자 최신 자율 수정/실행 지시에 따라 신규 v3를 준비·동결했고 기기 실행 결과는 종료 뒤 별도 기록한다.

## 수정·소유권

- `postapproval-listing-gap-v1`은 registered-history-control-v1/ numeric-ap-observe-v2 조합에만 허용. 잘못된 context/version은 기기 명령 전에 거부한다. flag 없는 기존 경로는 승인 후 즉시중단 동작을 유지한다.
- warmup와 numeric AP 승인을 전달한 뒤 진행 listing만 기존약0.25초loop에서**직전query결과후최소2초**로 줄인다. 필수 thermal2초/화면10초 관측은 계속 수행한다. timeout은3초불변, watchdog/전체deadline/모형/요청/승인/AP범위는불변.
- 정확한 동일cmd의 무출력timeout·root_reaped=true·반환exit존재·관측deadline30초이상·세션gap0일때만1회progress unknown으로기록한다. stderr/부분stdout/명시연결실패/미종료client/증거부재는중단한다.
- 원오류/stack/result/deadline을 `postapproval_observation_gap.json`에 먼저 저장한다. 저장실패는 원오류를 보존하며 중단한다. 이후정규loop에서fresh thermal bracket과화면을반드시확인하고다음진행조회로넘어간다. 승인/추론/설치재전달0, 같은실패cmd의즉석재시도0. 다음정규진행조회도 동일cmd인 점과 bounded재관측이라는 의미를 숨기지 않는다. 두번째실패는중단하며 첫증거는덮지않는다.
- gap파일은 성공/앱완료/연결정상증거가 아니다. terminal파일 발견뒤기존회수·자료적격성·환경coverage검사를 그대로 적용한다. 원deadline/ADBcap과회수/cleanup슬롯을늘리지않는다. 기존parent/child와단일cleanup책임은유지한다.

## 계측 영향·검증

모델/runtime/resident/sampler900ms/입력/실험상태/시작AP/trace는변경하지않았다. Android/APK 변경0. host listing 횟수/기기출력전송 감소와 gap뒤추가fresh환경조회가 기기전체J/AP에 영향을 줄수있다. 비용을추정해빼지않고 **프로토콜전이자료**로분리한다. 기존동결모형은그대로적용하고strict지원/정확도PASS를확장하지않는다.

검증39건: 실제poll로warmup→AP승인→원무출력timeoutfixture→fresh환경→terminal조회, 승인각1/명령간격, 두번째gap, thermal실패, 화면위반, 예산/시간reserve, 기록실패/원stack, 부분출력/연결오류/미reap/명령불일치/잘못된version차단. legacy6·이력개발/동결/확인·회수·cleanup관련회귀포함. Popen격리로실제기기0. 관측주기변경의실기기에너지영향/실제연결안정성은PC테스트로검증하지않았다. 첫회기간격fixture의예상호출순서오류1을실제fresh순서와2초간격assert로수정했고현재39PASS.

```powershell
python -X utf8 -B -m unittest tools.test_d1_postapproval_observation tools.test_d1_preparation_observation tools.test_d1_history_control tools.test_d1_history_recovery_campaign tools.test_d1_energy_device_lifecycle_cleanup
```

## 신규 v3·승인 범위

- campaign: `C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_history_recovery_plan_v3/campaign_plan.json`
- SHA `2a4f3443f817ca202b4ab2a5511e202c959c1098c601691ac3231776f6096213`, primary `e64cda9689ec97549c21835a145b5711416abd2648922e4ce092d82c16663a65`.
- APK기존 `history_control_build_v1` SHA `3840bfb161b038ae61f34cd4215f8fe88bc511ec4e5f87cccc3b58e02c8768be`, source/서명Check확인. 현재설치본이같으면전송/설치생략.
- 최신사용자승인으로새캠페인1회, 개발6→등록g후보동결→확인6. 새계획소비기록은독립적이며이전v2의104추론/623명령/251.720초도최종보고에별도로보존한다. v2미소비초기화/재개는없다.
- 정상1920작업+96warmup=2016추론/runtime48/staging12·84파일/ADB91400/19557초예약. 새v3캠페인상한2120추론/13시도/runtime52/staging13·91파일/설치본pull·APKpush·install각2/ADB99240/21600초·마무리600초. 모든worstcase를동시에소진하며완주한다는뜻은아니다. 이새6시간이전종료캠페인의wallclock재개라고표현하지않는다.
- 명시연결오류이면sameendpoint20조회/최대20분대기1회, 동일기기/manifest/앱terminal증거확인시읽기회수1회120초20명령. host/클라이언트실제종료확인필수. 자동connect/pair/daemon/settings/transport전환0.
- 재현코드앱결함·적격개발0·첫실패일때만원receipt/원인review/관련검증/서명/source/계측불변을확인하고남은전체block+마무리예약안에서보완1회. 늦은실패의완료자료를변경APK와섞지않고, 모형gate실패/환경부적격/기록손상/상한소진을자동우회하지않는다. 개발gate실패면확인0이며결과분석으로종료한다.

```powershell
& 'C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_history_recovery_plan_v3/RUN_AFTER_APPROVAL.ps1' -Action Check
& 'C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_history_recovery_plan_v3/RUN_AFTER_APPROVAL.ps1' -Action Run -Approved -Serial '<승인된현재A24 transport>' -ExpectedPlanSha256 '2a4f3443f817ca202b4ab2a5511e202c959c1098c601691ac3231776f6096213'
```

이번사용자가제공한현재IP경로에고정해실행기내현재식별/환경을확인한다. 다른mDNS연결은해제하지않는다. 두연결존재가v2timeout원인이라는증거는없다.
