# 새 계측 ON 원본의 PC 검증

새 ON 원본에 기존 공식 trace processor v58.2를 적용해 CPU 사건·주파수 자료와 보고된 손실 통계를 조회했다. 상세 숫자는 TRACE_AUDIT.json 및 CSV에 보존한다. 보고된 손실이 0이어도 모든 사건 완전 수집의 증명은 아니다. GPU 내부 실행·전력 J 검증이나 OFF/ON 오버헤드 비교가 아니다.

[검증 JSON](TRACE_AUDIT.json) · [원본 trace ZIP](../../a24_measurement_share_20261016/followon_resumed_01/FAILED5_ON_original_trace.zip)

`config_write_into_file_no_flush=1` 경고를 보존한다. 전체 적재 방식 경고와 보고된 data_loss 통계를 구분하며, 경고를 삭제해 무결성 PASS로 만들지 않았다.
