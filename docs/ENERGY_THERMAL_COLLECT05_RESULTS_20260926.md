# COLLECT-05 결과 — resident AP 준비 대기 상한에서 중단

실행 당시 브랜치 HEAD `79a0027512f2cf4cca0dc2afc74c67c40505ce3d`/clean. 승인된 [계약](ENERGY_THERMAL_TEMPERATURE_PREP_20260926.md)과 plan_v9 SHA-256 `3f794c9ac01066777e9e0d9553f8494bd00c5fc8b60dbdebd95f66a1cc35bfc2`를 **한 번** 실행했다. 원본 `C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_collection_run_v5`, 소비 registry `energy_collection_registry/ENERGY-THERMAL-COLLECT-05/stopped.json`은 `stopped_no_resume`다.

동일 A24·fingerprint·서명과 배터리67%/31.6°C·비충전·thermal0·화면 설정 gate를 확인했다. 기존 설치본은 다른 APK 해시였으므로 승인 범위에서 전송1·업데이트 설치1회 수행했고, 설치 후 후보 SHA `c631095a…350d` 일치를 확인했다. 개발 첫 세션 전 배터리67%, 둘째 전65%; 설정 변경·재시도·대체·추가0. 총 설치·실행·회수·cleanup은 **1,389.359초 / 16,080초**였다.

| 단계·소비 | 실제 / 계획 |
|---|---:|
| 개발 | 2시도·1완료·1온도 준비 gate 중단·2미시도 / 4 |
| 확인 | 0시도·4미시도 / 4 |
| runtime / warmup | 반환8 / 32; 완료16 / 64 |
| 적격성 / 작업 / 전체 진단 | 완료4 / 16; 완료870 / 6,960; 완료874 / 6,976 |
| 명시적 추론 / staging | 완료 근거890 / 7,040; 2회·14파일 / 8회·56파일 |

첫 `CC_DG_serial`은 870개 작업·앱/host cleanup을 마친 **적격 직렬 1세션**이다. 준비 106.818초 후 공식 AP baseline 중앙값31.5°C. 다음 `CC_DG_parallel`은 runtime4·warmup8·적격성2까지 완료했지만, **351.176초** 준비 대기 후 중단됐다. 126개 준비 AP 표본은 32.3~33.5°C로 사전 anchor 범위 31.25~31.75°C에 도달하지 않았다. 마지막 60초 창은 중앙값32.4°C·범위1.0°C였다. 공식 baseline·병행 load arm은 없었고 **동결 및 확인도 없다**. 화면 관측117회는 모두 통과했고, 관측 thermal status는 0이었다. 단일 결과로 주변온도·잔열·다른 부하의 원인을 분리할 수 없다.

첫 직렬 조건의 작업 완료까지 328.424초·기기 전체 에너지 **557.844J**, idle 대비 추가 소비 추정176.932J는 **A24 전류 mA 해석을 전제한 단일 세션 기술값**이다. 고정480.091초 관측창은730.957J·추가 소비174.140J. 준비 구간도125.052J로 따로 기록했다. 준비부터 냉각까지 커버된 구간1207.979J에는 0.539초 미커버가 있어 전체 에너지 확정값이 아니다. 병행 표본이 없으므로 직렬/병행의 시간·에너지·발열 손익은 판정할 수 없다.

첫 앱 cleanup은 확인했다. 둘째 앱 cleanup 파일은 유효하게 회수되지 않아 **미확인**이고, host force-stop·프로세스 부재·thermal0은 확인했다. 영(0) 호출을 로그 누락만으로 가정하지 않는다. receipt의 보수적 상한은 원본에 남아 있다. 이번에는 host의 probe arm 부재와 회수 phase 기록으로 공식 baseline·병행 load **진입 근거가 없음**을 추가 확인했다. 기존 FAIL·부분 결과·동결40값·20null·종료 계획·`experiment_ready=false`는 보존한다.

Git 공유 [작은 요약](results/energy_collection_execution_05/README.md)과 별도로, 원본 `energy_collection_run_v5/FINAL_REPORT.md`, 재현 스크립트 `energy_collection_analysis_v5/REPRODUCE.py` 및 상세 `summary.json`은 로컬 전용이며 GitHub에 없다. PC 재현 명령:

```powershell
python -B C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_collection_analysis_v5/REPRODUCE.py
```

다음은 추가 실측 없이 이 두 시도의 AP 시간 경로와 준비 비용을 검토해 **같은 anchor를 충족하는 설계가 실제로 가능한지** 판단하는 것이다. 현재 자료만으로 전체 8세션 재수집·gate 완화·에너지 절감 주장을 정당화하지 않는다.
