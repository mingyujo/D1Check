"""Report unexecuted device preparation without inventing a phone result."""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

from tools import d1_overnight_device_replay as r
from tools import d1_arrival_plan as p


def main():
    active=r.BASE/'plan/collection_plan_source_v2.json'
    integrity=r.check(active);plan=p.read(active);built=p.read(r.BASE/'build_receipt_v2.json')
    with zipfile.ZipFile(built['apk_path']) as z:
        native=any(r.build.VERSION.encode() in z.read(n) for n in z.namelist() if n.endswith('.dex'))
    if not native:raise ValueError('built APK does not contain the registered native opt-in version')
    test=subprocess.run([sys.executable,'-B','-X','utf8','-m','unittest','tools.test_d1_overnight_device_replay','-v'],
        cwd=r.ROOT,capture_output=True,timeout=60,check=True)
    (r.BASE/'preparation_host_tests.txt').write_bytes(test.stdout+test.stderr)
    free=shutil.disk_usage(r.BASE).free
    verification=dict(status='prepared_storage_blocked' if free<4*1024**3 else 'prepared_ready_unexecuted',
        host_tests=5,jvm_tests=built['tests'],native_opt_in_dex_present=native,
        apk_sha256=built['apk_sha256'],package=built['candidate']['package'],
        signer_sha256=built['candidate']['signer_sha256'],source_snapshot_sha256=built['source_snapshot_receipt_sha256'],
        original_Android_worktree_changed=False,active_plan_sha256=integrity['plan_sha256'],
        schedules_sha256=plan['source_schedules']['sha256'],physical_sessions=0,installs=0,explicit_inference=0,
        owner_lock_present=False,registry_claim_present=False,execution_clock_started=False,
        host_free_bytes=free,required_host_free_bytes=4*1024**3,
        failure_point='preclaim host-space gate, before any ObservedDevice construction',
        auto_review_rejection=dict(action='Remove-Item on two newly generated Gradle intermediate directories',
            reason='blocked by policy; no further reason supplied',deleted_files=0,
            preserved='all sources, APKs, test XML, raw evidence, previous output and user working changes'),
        new_data_fit_calls=0,experiment_ready=False)
    r.write(r.PUBLIC/'preparation_verification.json',verification)
    identity=p.read(r.BASE/'guarded_project_receipt.json')
    r.write(r.PUBLIC/'source_snapshot_identity.json',dict(original_code=identity['original_code'],
        snapshot_files=identity['snapshot_files'],patch_sha256=identity['patch_sha256'],
        source_snapshot_sha256=built['source_snapshot_receipt_sha256'],apk_sha256=built['apk_sha256'],
        private_snapshot_not_distributed=True,android_worktree_changed=False))
    bundle=p.read(plan['source_schedules']['path'])
    r.write(r.PUBLIC/'frozen_schedules.json',bundle)
    rows=[]
    for policy in bundle['policies']:
        metric=policy['pc_metrics']
        rows.append(f"<tr><td>{policy['policy_id']}</td><td>{metric['completed']}/96</td><td>{metric['urgent_failure']}/{metric['normal_failure']}</td><td>{metric['urgent_p95_ms']:.3f}</td><td>{metric['normal_mean_ms']:.3f}</td><td>{metric['energy_j']:.6f}</td><td>{metric['peak_ap_c']:.6f}</td></tr>")
    r.PUBLIC.joinpath('index.html').write_text('''<!doctype html><html lang="ko"><meta charset="utf-8"><title>A24 전향 실측 준비</title>
<style>body{font-family:Arial,Malgun Gothic,sans-serif;margin:32px;max-width:1200px;color:#263043}table{border-collapse:collapse}td,th{padding:9px;border:1px solid #ccc}.block{background:#fff0ce;padding:18px}a{color:#166f9f}</style>
<h1>A24 동결 일정 전향 실측 준비</h1>
<div class="block"><b>준비·검증 완료, 기기 실측은 0회입니다.</b> 호스트 저장공간 사전검사에서 중단했습니다. 실제 phone 결과나 절감 근거로 읽으면 안 됩니다.</div>
<p>기존 앱의 온라인 판단을 이식한 비교가 아닙니다. 같은 96건을 대상으로 PC에서 동결한 Band 대응/리스트 선택 일정의 release·CPU/GPU 배정을 A24에서 재생할 계획입니다. 실제 AVAILABLE과 CG_DC 병행 제한을 유지합니다.</p>
<p>계획: ABBA 4세션 · 요청384 + warmup32 · 설치 상한1 · 90분 중 마지막10분 보존. 현재 실행 clock/registry 없음.</p>
<h2>기기 결과와 구분한 사전 PC 계획 예측</h2>
<table><tr><th>정책</th><th>모형 완료</th><th>긴급/일반 실패</th><th>긴급 P95 ms</th><th>일반 평균 ms</th><th>모형 J</th><th>모형 최고 AP °C</th></tr>'''+''.join(rows)+'''</table>
<p>두 계획의 작은 AP/J 차이는 실제 휴대폰 절감 증거가 아닙니다. 현재 선택 후보는 전체 조건 기준을 별도로 통과해야 합니다.</p>
<h2>검증</h2><p>새 native opt-in+기존 계약 JVM10, host5 통과. APK dex에 새 version 실물 확인, 기존 프로젝트 서명과 package/version 일치. 사용자 Android 작업트리 수정0.</p>
<p><a href="execution_contract.json">사전 계약</a> · <a href="preparation_verification.json">저장공간·0회 근거</a> · <a href="preexecution_source_amendment.json">미실행 source 개정</a> · <a href="frozen_schedules.json">PC 동결 두 일정</a> · <a href="source_snapshot_identity.json">private source 스냅샷 해시</a></p>
</html>''',encoding='utf-8')
    report=f'''# A24 동결 일정 전향 실측 준비 — 저장공간 차단

2026-10-11 사용자 A24 연결·필요한 추가 실측·오류 수정·회의 준비 승인에 따른 새 작업 `OVERNIGHT-FROZEN-PLAN-DEVICE-01`이다. **기기 실행0·추론0·설치0·새 fit0**이다. 현재 완료한 것은 코드·APK·실행계획·JVM/host 검증이며 실제 스케줄링 성과가 아니다.

## 사전 고정 범위

공통시작+35초부터350ms 간격의96건(긴급 분류48·일반 탐지48), 1.5초/6초 기한, 같은 입력·모델·CPU1·검증CG_DC2병행만 사용한다. Band 대응/기존 리스트 선택 두 PC 일정을 ABBA 순서로재생한다. 예정 본384＋warmup32=416·runtime16·설치최대1·기기clock90분/마지막10분저장이다. 선택된 대표 trace를 유리하게 바꾸지 않았다.

기존 APK는 source정책 이름과일괄CPU/GPU/24요청만 지원해 새 일반동결일정을그대로실행할수없었다. 기존 사용자 Android 변경은 수정하지않고별도private 전체프로젝트snapshot에 `{r.build.VERSION}` opt-in을추가했다. 분류CPU/GPU·탐지CPU, 실제owner에따라 미검증분류CPU＋분류GPU 병행금지, 실제AVAILABLE까지요청보존, legacy응답/저장/worker/lane경계를유지한다. 실행프로그램 전체/온라인Band/RL의직접실행이아니라 계획실행가능·예측정합 검증이다.

## 검증과 오류 보존

- host5＋JVM10 PASS; native opt-in version의실제dex포함확인. 새APK `{built['apk_sha256']}`. 프로젝트기존서명·동일package/version 확인, update-r 자료보존예정이다.
- 처음Gradle SDK환경누락, Kotlin sourceSets override가원source를남긴문제, 기본서명차이를사전검사에서차단했다. 오류로그/미설치APK/테스트XML/원source를보존하고전체source snapshot＋기존project서명으로격리빌드했다.
- IE의첫export는common−35s 상대좌표였다. PC원장자체는35s도착이었다. 실측전에common0 export와원장576행roundtrip을검산하여고정했고원relative자료를보존했다. 추가시뮬레이션/성과선정0이다.
- 공유code의개인SDK/JBR경로literal은환경기반으로교체했다. 이미등록된미실행계획은보존하고source만개정한별도계획SHA `{integrity['plan_sha256']}`를기록했다. APK/일정/예산/판정불변,실행clock재설정0이다.

## 실측을 시작하지 못한 이유

`run`은ObservedDevice 생성전4GiB host여유를확인한다. 실제여유 `{free}` bytes여서 claim/registry/owner/설치/세션을 만들기전에중단했다. 등록된기준은낮추지않았다. 추가실측결과는없고예정값을실제성공으로대체하지않는다.

이과제에서새로생성한두Gradle중간물만정리하려했지만자동승인검토가Remove-Item 명령을거절했다. 도구가밝힌이유는 `blocked by policy`이며더구체적인설명은없었다. 삭제0·원자료/사용자파일/다른작업보존. 두중간물을회수해도약583MB로4GiB에는부족하다. 제한을다른shell로우회하지않았다.

## 다음 실행과 증거

저장공간이4GiB이상복구되고동일source/APK/일정·기기gate가통과하면아직미소비한현재계획에서4세션을시작할수있다. clock은첫claim부터시작한다. 원중단실험의clock/seed/budget를초기화한것이아니다. 실제연결된transport를명시하고새결과로계수재적합0·판정기준조정0을유지한다.

PC검증: `python -B -X utf8 -m unittest tools.test_d1_overnight_device_replay -v`.
계획점검: `python -B -X utf8 -m tools.d1_overnight_device_replay check --plan output/overnight_device_20261011_v1/plan/collection_plan_source_v2.json`.
실제기기실행은같은`--plan`과현재확인된`--serial`을명시한`run`이다. 실행후 `python -B -X utf8 -m tools.d1_overnight_device_report`로전체도착분모/실제응답/실제AVAILABLE/조건부J/같은AP/초기상태차이를판독한다. A실제점유조건부/B동결PC계획의모형오차도새fit0으로분리한다.

[오프라인준비화면](results/overnight_device_20261011/index.html), [0회·저장공간검증](results/overnight_device_20261011/preparation_verification.json), [계약](results/overnight_device_20261011/execution_contract.json), [source개정](results/overnight_device_20261011/preexecution_source_amendment.json), [동결두일정](results/overnight_device_20261011/frozen_schedules.json). 공개파일은작은code/설정/해시만이며APK·키·모델binary·raw·개인경로를공유하지않는다. 실제APK에포함된user WIP는private snapshot과전체hash로특정했고Git원본과조용히합치지않았다.
'''
    (r.ROOT/'docs/OVERNIGHT_DEVICE_REPLAY_20261011.md').write_text(report,encoding='utf-8')
    (r.PUBLIC/'README.md').write_text('# A24 동결 일정 전향 실측 준비\n\n**실측0회입니다.** host저장공간4GiB기준미달로claim전에중단했습니다. 준비code/JVM10/host5는PASS입니다.\n\n[index.html](index.html)과[준비검증](preparation_verification.json),[실행계약](execution_contract.json)을보세요. PC예측은실제결과와분리했습니다.\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in verification.items() if k!='auto_review_rejection'},ensure_ascii=False,indent=2))


if __name__=='__main__':main()
