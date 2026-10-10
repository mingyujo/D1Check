# 동결 재생 실행을 위한 별도 source prerequisite

공유용 파일은 `flat/00_...` 형태의 11개 사본과 `manifest_v2.json`이다.
각 `logical_path`는 원 저장소 상대 경로, `archive_path`는 짧은 공유 경로다.
원본 byte SHA와 UTF-8/LF SHA를 유지했고, 원 deep 사본과 `manifest.json`
v1은 로컬에 그대로 보존했다. 긴 checkout 경로의 Windows MAX_PATH 때문에
원 deep 사본은 Git 공유 대상에서 제외한다. 실제 실행·소스·APK·정책·계수는
바뀌지 않았고 추가 기기·학습 실행은 없다.

기준 Git HEAD는 `0d6535b486ef144acd641e64fd5f60eb297b43dd`이다.
원 user WIP를 덮어쓰지 말고 별도 checkout/review 폴더에서 검토한다.
`portable_prerequisites.patch`를 clean base에 적용하거나, v2 manifest의
각 archive 사본을 checkout의 같은 logical 상대 경로에 복사한다.

```powershell
git apply --check docs/results/overnight_device_20261011/source_bundle/portable_prerequisites.patch
git apply docs/results/overnight_device_20261011/source_bundle/portable_prerequisites.patch
python -B -X utf8 -m unittest tools.test_d1_overnight_device_replay -v
python -B -X utf8 -m tools.d1_overnight_device_verify
```

원 Android 두 클래스에 같은 opt-in 변환을 적용한 결과가 실제 private build
snapshot의 canonical SHA와 같음을 manifest에 기록했다. 격리 build helper가
opt-in 변환을 적용하므로 먼저 replay patch를 적용한 뒤 변환을 또 실행하지
않는다. 기존 프로젝트 서명 key·정확한 모델/input artifact는 로컬에 필요하고
공유하지 않는다. toolchain/build timestamp 차이 때문에 rebuild가 같은 APK
byte SHA를 만들었다고 가정하지 않는다.

순수 unit과 공유 verifier는 기기·학습·새 환경·새 clock을 생성하지 않는다.
이미 소비한 session UUID/registry를 새 실행에 재사용하거나, clean checkout을
통해 새 기기 예산을 만들지 않는다. source bundle은 재현용 code 보존이며
새 물리 실행을 자동 승인하는 계약이 아니다.
