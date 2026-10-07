# 외부 코드 귀속과 재현 범위

tools/d1_triton_rules.py의 RateState는 NVIDIA Triton core의 rate_limiter.cc/.h에서 확인한 callback, allocation, scaled-priority control flow를 Python으로 적용한다.

- 원 저장소: https://github.com/triton-inference-server/core
- 고정 commit: 3af839d613da6995051f9bcfab00efe2eac87d4c
- Copyright NVIDIA CORPORATION & AFFILIATES. 원 소스 BSD-3-Clause 조건은 TRITON_LICENSE.txt에 보존한다.
- 서버·외부 모델·원 binary를 실행/공유하지 않는다. D1Check 전체 요청·실제 lane 재사용 경계로 바꾼 제한적 재현이다.
- StarPU는 조사만 수행했다. 원 구현/모델을 번들에 배포하지 않는다.
