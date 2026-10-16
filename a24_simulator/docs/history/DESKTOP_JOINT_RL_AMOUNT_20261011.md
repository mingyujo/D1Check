# 데스크톱에서 같은 V1 learner의 학습량을 늘리는 경로

**구현된 CLI는 기본읽기검증만한다. 실제추가학습은이번에0회다.** 미지의다른PC에서실행했다고주장하지않는다. 현재지원은공동서비스 envelope V1＋absolute-service objective v2의원terminal64 세개에서시작하는별도학습량실험이다. 더많이학습하면개선된다는보장은없고, 현재허용된예측비용개선후보0이라는제약은먼저검토할필요가있다.

```powershell
$env:MKL_THREADING_LAYER='SEQUENTIAL'
python -B -X utf8 -m tools.d1_joint_amount_cli
python -B -X utf8 -m unittest tools.test_d1_joint_amount_session tools.test_d1_joint_amount_ledger -v
```

원실행은세초기화seed 모델＋공유round-robin global sampling RNG다. 동일연장은11→23→37 모델을복원하고마지막37의session RNG에서이어간다. 이후에는전3learner actor/critic/Adam/승수/partial/RNG 상태와공유session RNG,case/next-seed 커서를하나의`session_latest.pt`로원자보존한다. learner별복원만으로전체중지/연속동일성을주장하지않는다. 별도독립3stream이나새 service-envelope V2를쓰려면fresh설계/가중치가필요하다.

예시 명령은 **사용자가데스크톱에서새범위·예산으로실행할때만** 사용한다. 아래는64→128 각64episode추가,총192학습이다. 공통teacher64＋학습192＋개발24×3=72＋신규확인48×7=336이므로664환경이필요하다. root500/192 완료소비는초기화하지않고장부에따로계승한다.

```powershell
python -B -X utf8 -m tools.d1_joint_amount_cli prepare --task amount128_a --target 128 --arrival-start 860010001 --confirm-seeds 860020101 860020102 860020103 860020104 --native-cap 700 --learning-cap 192 --active-minutes 60 --reserve-minutes 5
python -B -X utf8 -m tools.d1_joint_amount_cli run --task amount128_a
```

한작업의지원범위는각learner 추가8..480episode(8배수),원64 기준최대544까지다. 무제한학습이나현재CLI로544 뒤연속체인을지원한다고표시하지않는다. target512라면추가448×3=1344학습/2200환경이므로새명시적예산으로준비할수있다. 알고리즘·모형·보상·mask/schema가같아야하며V2actor에V1을전용하지않는다.

새training seed는학습/개발/확인에서분리하고원등록범위와겹치지않는지검사한다. standalone에는전체프로젝트에서내보낸 `arrival_seed_registry.json`이필수다. `arrival_seed_registry_v1`의used/reserved seeds와닫힌구간을모두검사하고원registry SHA를새task에서잠근다. 이파일이없는전체Git workspace에서만원registration/contract 검색을사용한다. 기존개발24는이미본자료임을표시하며최종확인4새arrival seed×4부하×3문맥48에는Band/Triton/JointList/CostList와세PPO를같은trace로실행한다. 원요청분모·기한·응답/AVAILABLE·J/AP 원단위전조건gate를사용하고자동채택은0이다.

일시중지는작업폴더 `output/desktop_joint_amount_<task>/REQUEST_STOP` 빈파일을만들면모든reference/학습/최종기준선/PPO평가의환경 경계에서멈춘다. 재개는파일을제거하고같은run을호출한다. `clock.json`에실제run 세션의누적active시간을저장하고, 정상중지후긴휴식은차감하지않는다. 재개때이전active소비를빼므로상한초기화나무제한연장이아니다. 마지막저장예약을남겼고완료task 재등록은거절한다. 갑작스런종료로running clock의정상닫힘이없으면자동재개를거절한다. 시뮬레이션이소비됐지만전체session이저장되지않으면소비/cursor 불일치를거절하며cached 학습을재실행처럼쓰지않는다.

준비물은모바일팀의최소JSON4개/NumPy·Torch 및원profile/initial model,원registration·label-only revision·source identity,원terminal64 세개다. APK·ADB·Kotlin·TFLite모델binary는PC학습에필요하지않는다. 저장경로와dependencies의원raw SHA는보존한다. portable 복사본의3미사용ADB기본경로치환은정확logical path/old hash/new hash/receipt의허용범위에만받아들이고새task의실제portable canonicalSHA를추가로잠근다. 원정책/실측계수나checkpoint.dependencies를재작성하지않는다.

```powershell
python -B -X utf8 -m tools.d1_joint_amount_cli verify --portable-manifest core_manifest.json
```

현재PC에서원세archive/공유session 복원·중간seed커서/RNG draw 동일·atomic PT·V2거부·원dependency/공개SHA 잠금·소비장부reload·학습cap·학습cache 재실행차단·누적active중지/재개·불명clock거부·최종평가중지·registry seed/폐구간/파서,총13순수검사를통과했다. 이검사에서는환경/추가PPO optimizer step/기기명령이0이다. 실제확장run의전체통합실행과다른PC 성능/환경은아직검증하지않았으므로우선작은새작업으로확인해야한다.
