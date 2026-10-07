# 원 규칙 출처와 코드 경계

`tools/d1_external_rules.py`의 Band HEFT 제어 흐름은 Seoul National University의 Apache-2.0 코드(2023)를 바탕으로 whole-request 단위에 맞춘 Python adaptation이다. 원 저작권·라이선스 고지는 module docstring에 명시하며 원본 전체는 배포하지 않는다. Apache-2.0 원 라이선스는 `BAND_LICENSE.txt`에 함께 제공한다. 원본 버전과 파일 SHA는 `sources.json`에 기록한다.

Ente는 공개 코드에서 관찰한 건강 판정·활동 timer의 행동 명세를 별도 코드로 표현했다. Ente 프로그램·사진/모델·Rust/ONNX runtime·소스 파일을 이 공유물에 포함하지 않는다. 원 Ente 저장소의 라이선스는 AGPL-3.0이며 attribution과 원 코드 위치를 `sources.json`과 `mapping.md`에 기록했다. 외부 앱이나 전체 구현을 직접 실행했다는 뜻이 아니다.

출처 URL과 버전·SHA는 원 규칙 감사용이다. 원본 파일 내려받기는 공식 공개 URL만 사용했고, 일부 raw/GitHub API 접속 timeout은 다른 공식 API 읽기로 복구했다. 접근 통제를 우회하지 않았다. NPU 정책 구현의 구체 임계값은 이번 감사에서 미확인이다.
