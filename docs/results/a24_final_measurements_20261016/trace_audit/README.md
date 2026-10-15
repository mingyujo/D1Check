# Perfetto 원본의 PC 자료원·유실 검사

원본을 바꾸거나 다시 계측하지 않고 공식 Trace Processor **v58.2-add693d8b**로 분석했다. 기기 생산자는 v49.0이다. [원본 ZIP과 SHA](../../a24_measurement_share_20261016/perfetto_path_repair_raw_trace_01/README.md) · [기계 판정](TRACE_AUDIT.json) · [실제 SQL 실행](SQL_EXECUTION.json) · [추가 질의](ADDITIONAL_SQL_EXECUTION.json).

| 확인 항목 | 관측 결과 |
|---|---|
| 자료원 | `sched_switch` 240,820개, `sched_wakeup` 126,992개, `cpu_frequency` 48,586개 |
| CPU 주파수 | 8개 CPU 모두 표본 존재 |
| 추적 구간 | 209.932966초; 앱 공통 시작 대비 -0.211912385~209.721053166초 |
| 공통창 | 서비스 0~120초와 AP 판정 35~180초를 포함. 앱 210초 꼬리의 마지막 약 0.279초는 미포함 |
| 시간축 | `trace_time_clock_id=6`(BOOTTIME), 앱의 elapsedRealtimeNanos와 대응 |
| 유실 통계 | 조회한 `severity=data_loss`의 비영(非零) 항목 없음. ftrace overrun/dropped/commit-overrun 및 중앙 buffer overwrite/discard 값0 |
| 별도 경고 | `config_write_into_file_no_flush=1`; compact sched switch skip8, 끝이 열린 sched slice8도 보존 |
| 버퍼/상한 | 중앙 버퍼 8MiB, 파일 크기 상한64MiB. 두 값을 혼동하지 않음 |

**“모든 이벤트가 완전하다”는 판정은 아니다.** 원본에 보고된 유실 지표가 없다는 제한적 관측이다. 초기/종료 경계와 위 skip·미포함 꼬리를 숨기지 않았다. GPU 커널·fence·하드웨어 전력·물리 표면온도를 확인한 자료도 아니다. 앱 lane 점유의 겹침과 GPU 내부 실행 증거는 구분한다.

`config_write_into_file_no_flush`는 원 프로필의 `write_into_file`에 `flush_period_ms`가 없는 데서 나온다. 해당 버전의 설명과 실제 stderr는 **분석기가 전체 trace를 메모리에 적재해 메모리 사용이 커지는 경고**라고 명시한다. 이 이름의 `error`만으로 실제 이벤트 유실이 있었다고 단정하지 않았다. 프로필과 원 영수증 `RAW_TRACE_ONLY_SOURCES_AND_LOSS_UNVERIFIED`는 그대로 보존하고 이 PC 검사를 별도로 추가했다. [버전 고정 공식 통계 정의](https://github.com/google/perfetto/blob/v58.2/src/trace_processor/storage/stats.h) · [공식 버퍼·유실 설명](https://perfetto.dev/docs/concepts/buffers) · [시간축 정의](https://perfetto.dev/docs/reference/trace-config-proto).

OFF/ON의 긴급 P95는 각각 **274.741156 / 275.051386ms**였다. 이는 동일 입력32건씩의 **1쌍**이며 계측 부하0, 온도 개선 또는 통계적으로 확정된 오버헤드를 뜻하지 않는다. AP 평균은29.091113 /28.920086℃였지만 순서·초기 상태 허용범위·변동이 있어 성능 이득으로 해석하지 않는다.

## PC에서 재현

1. [고정 공식 Windows 실행파일 정보](WINDOWS_BINARY_MANIFEST.json)의 URL에서 파일을 받아 byte count와 SHA를 대조한다. 실행파일은 저장소에 재배포하지 않았다.
2. 위 원본 ZIP을 풀고 다음 명령을 실행한다. SQL은 이 폴더에 모두 있다.

```powershell
Get-FileHash .\trace_processor_shell.exe -Algorithm SHA256
# adfa6bad3d72be3ba9b83fa2b17b69fa13b3ab1cad0f42e52b86188bd5f0f997
.\trace_processor_shell.exe --version
.\trace_processor_shell.exe query -f .\ftrace_event_types.sql .\instrumentation.pftrace
.\trace_processor_shell.exe query -f .\all_health_and_buffer_stats.sql .\instrumentation.pftrace
.\trace_processor_shell.exe query -f .\CPU_frequency_sources.sql .\instrumentation.pftrace
```

[전체 비영 통계](stats_nonzero.csv) · [원본 경고 stderr](stats_nonzero.stderr.txt) · [전체 health·buffer 통계](all_health_and_buffer_stats.csv) · [ftrace 통계](ftrace_stats.csv) · [자료원별 수](ftrace_event_types.csv) · [CPU별 주파수 표본](CPU_frequency_sources.csv) · [추적 경계](trace_bounds.csv). 이 PC 검사에서 ADB·추론·새 계측0이다.
