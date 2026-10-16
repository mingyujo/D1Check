# A24 미실행·실패 보완 결과

기존 실패 5건에 각각 새 ID를 부여한 후속 진단이다. 이전 실패는 그대로 남기며 독립 확인 40건의 성공으로 대체하지 않는다. 기존 최종 보고서는 이전 시점의 스냅샷으로 보존했다.

이번 실패 보완 **5/5건 정상, 480/480요청 완료**. 원 L64 미실행 조건은 APP 0회로, 기존 27.1℃ 기준 이하의 사전 안정 조건을 10분 안에 맞추지 못해 보존 종료했다. MAIN 기준 완화·기존 ID 재전송·예산 환급은 없다.

관련 여섯 묶음을 중복 없이 합산하면 **63/69등록 정상, 8,392/8,936요청 완료**다. 원 독립 확인은 37/40정상이며 미실행·실패 분모를 계속 보존한다. 누적 계산상 소비는 109/110이고 별도 전류 진단은 이 원장 밖이다.

| 새 진단 | 완료/예정 | 긴급 P95 | 긴급 기한 내 | 일반 기한 내 | 평균/최고 AP |
|---|---:|---:|---:|---:|---:|
| 혼합 EDD 재확인① | 128/128 | 9010.5ms | 26/96 | 5/32 | 28.808/29.9℃ |
| 저부하 직렬 | 64/64 | 279.7ms | 32/32 | 32/32 | 28.831/29.4℃ |
| 혼합 CPU·GPU 병행 | 128/128 | 1452.7ms | 96/96 | 32/32 | 29.071/30.6℃ |
| 혼합 EDD 재확인② | 128/128 | 9086.4ms | 28/96 | 5/32 | 29.032/30.1℃ |
| 분류 GPU·계측 ON | 32/32 | 274.4ms | 32/32 | 0/0 | 28.521/28.8℃ |

**정상 수집은 기한 준수 성공과 다르다.** 혼합 EDD 두 반복은 긴급 기한 내 26/96·28/96, 일반은 각각 5/32였다. 혼합 병행 반복은 긴급 96/96·일반 32/32였다. 아래 지표로 서비스 실패를 숨기지 않는다.

각 진단은 **자기 준비 후 최초 안정 60초**를 기준으로 삼았다. 서로 다른 시작 상태이므로 위 표의 AP 숫자로 정책 우열을 판정하지 않는다. C9/R2는 이전 보완12에서도, ON은 수정 OFF/ON 묶음에서도 성공 자료가 있으며 이번 반복은 추가 진단이다. ON 단독 결과는 계측 오버헤드 비교가 아니다.

실제 성공은 요청 보존·자원 용량·응답/worker/lane 반환 경계·출력 품질·저장 닫힘을 확인한 것이다. 예측 모형의 독립 검증이나 에너지 절감 확인을 뜻하지 않는다. **J는 미판정**, AP HAL은 물리 표면온도 검증이 아니며 `experiment_ready=false`다. 기존 APK·모델·입력·동결179 소스를 유지했고 S26/NPU·데스크톱 학습·다른 worktree는 변경하지 않았다.

- [오프라인 대시보드](index.html) · [실패5 상세 CSV·그림](failed5/index.html) · [원40 최신 집계](original40/index.html)
- [원자료 ZIP·SHA](../a24_measurement_share_20261016/followon_resumed_01/README.md) · [공개 원자료 재계산](public_reproduction/VERIFICATION.json)
- [새 계약·원 실패 대응표](../../team/a24-measurement-revision02-20261015/failed5_followon_20261016/README.md) · [이전 최종 스냅샷](../a24_final_measurements_20261016/README.md)

PC 재현(기기 실행 없음):

```powershell
python -B -m unittest discover -s tools -p test_d1_a24_failed5.py -v
python -B -m unittest discover -s tools -p test_d1_a24_confirm_remaining.py -v
python -B tools/d1_a24_public_reproduce.py docs/results/a24_followon_measurements_20261016/PUBLIC_REPLAY_CONTRACT.json output/a24_followon_public_replay_fresh
```

재계산 출력은 사용하지 않은 새 폴더를 지정한다. 개인 식별 manifest·APK·라이선스 미확인 모델·승인 이미지는 SHA와 제외 사유만 공유한다. 나머지 원자료는 원본 바이트와 파일별 SHA를 보존한다.

[원 L64 미실행 근거](ORIGINAL_SLOT_DEFERRAL.json): 114회 읽기에서 AP 27.4~27.7℃, 마지막27.5℃였고 27.1℃ 이하 표본은0이었다.

[새 ON trace PC 검증](trace_audit/README.md): CPU sched_switch236075·wakeup124600·frequency47348 사건을 확인했다. 보고된 비영 data_loss 통계는 없지만 전체적재 방식 경고1은 보존했으며 완전 수집이나 GPU 내부 실행·전력 검증을 뜻하지 않는다.
