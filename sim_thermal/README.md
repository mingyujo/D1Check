# sim_thermal — 열·에너지 평가층 v1 (1겹)

**SYNTHETIC 입력으로만 돌렸다. 파이프라인 검증 전용 — 어떤 주장에도 쓰지 않는다.**

- 조민규 엔진·회계(`tools/d1_arrival_explore.py`, `tools/d1_energy_thermal.py` 등)는 **이 저장소에 넣지 않는다**.
  `origin/feature/arrival-scheduling-20260923` @ `36632fadf67f52791d8681e18027927ba05f0011` 을 따로 추출해 import 한다
- 여기 있는 것은 그의 계층에 없는 것뿐: 파라미터 → 그의 상태 profile 변환, `t_skin_max` 초과 시간·횟수, 열 제약 순위, sweep
- 평가만 한다: NPU lane 추가·발열에 의한 실행 지연 반영은 불가능 (2겹 몫)

```
git archive 36632fadf67f52791d8681e18027927ba05f0011 tools docs | tar -x -C <추출폴더>
py sim_thermal/run.py --jo-root <추출폴더> --out <새 출력 폴더>
```

계약·사전등록·결과: `산공학회\D1_ondevice\sim\평가층_계약_v1.md`, `평가층_사전등록_v1.md`(22:40 KST, 실행 전), `평가층_결과_0926.md`, `평가층_민감도_0926.md`
