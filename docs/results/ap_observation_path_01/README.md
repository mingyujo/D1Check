# AP 관측 경로·PC 입력 경계

[적용 판정](../../AP_OBSERVATION_PATH_PC_20261008.md) · [조회 시간](query_timings.csv) · [owner gate1630](owner_gate_replay.csv) · [예측진입20](forecast_integration.csv) · [요약](summary.json).

현재APK는numericAP직접읽기와실행중APconsumer가없다. 기존host는Current HAL AP를3명령으로읽고시작전AP승인1회만앱에전달한다. host→PC예측API는구현/검증했고현재앱자체AP피드백은unavailable이다. source허가/권한/조회주기/기기설정/Android/APK변경0.

1630기존관측의3명령host span중앙값0.328초/P95.437초. host기록timestamp는filewrite/flush전이므로실제consumer수신을대체하지않는다. 명시consumer callback시각이없으면`host_receipt_is_proxy=true`. 앱수신/적용ack가없어전달지연null. host/device clock직접차감/thermal status·headroom의AP대체0.

공유Git만으로실행한다. 관측조회/예측재학습/정책배치/기기명령이없다.

```powershell
python -X utf8 -B -m unittest tools.test_d1_ap_observation_bridge -v
python -X utf8 -B -m tools.d1_ap_delivery_readout --check-shared
```

원자료가있으면시간대조를새PC폴더에다시생성할수있다(19,473client기록읽기, ADB실행0).

```powershell
python -X utf8 -B -m tools.d1_ap_delivery_readout --external '<D1Check_Arrival_Extension>' --output output/ap_delivery_reproduction
```

`forecast_fixtures.json`은20원기록에서AP/상대시각/manifest hash를추출한익명별칭의파서/예측fixture다. 실제live송신/앱수신이아니며공유fixture시계도독립syntheticdomain이다. 실제manifest/소유권검사는owner_gate_replay와source_alias_hashes에별도로남겼다. APsource/HPM제한은[공식온도API](https://developer.android.com/reference/android/os/HardwarePropertiesManager#getDeviceTemperatures(int,%20int))·[headroom API](https://developer.android.com/reference/android/os/PowerManager#getThermalHeadroom(int))에서확인했다.
