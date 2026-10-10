"""Export required WIP prerequisites as a separate, canonical, reviewable bundle."""
from __future__ import annotations

import difflib
import hashlib
import json
from pathlib import Path
import re
import subprocess

from tools import d1_overnight_device_replay as replay
from tools import d1_arrival_plan as p

BASE_HEAD='0d6535b486ef144acd641e64fd5f60eb297b43dd'
PKG='benchmark-runner/src/modelProbe/java/com/example/d1check/benchmarkrunner/'
TEST='benchmark-runner/src/testModelProbe/java/com/example/d1check/benchmarkrunner/'
FILES=(
    'tools/d1_energy_collection_device.py',
    'tools/d1_simulation_model_v2.py',
    'tools/d1_simulation_model_v3_thermal.py',
    PKG+'ArrivalEnergyActivity.kt',
    PKG+'EnergyCollectionActivity.kt',
    PKG+'EnergyResidentIdentification.kt',
    PKG+'ArrivalBatteryGate.kt',
    PKG+'EnergySamplerShutdown.kt',
    TEST+'EnergyResidentIdentificationTest.kt',
    TEST+'ArrivalBatteryGateTest.kt',
    TEST+'EnergySamplerShutdownTest.kt',
)


def canonical(data):
    return data.decode('utf-8-sig').replace('\r\n','\n').replace('\r','\n').encode('utf-8')


def main():
    target=replay.PUBLIC/'source_bundle'
    if target.exists():raise ValueError('write-once source prerequisite archive')
    target.mkdir();records=[];patch=[]
    frozen=p.read(replay.BASE/'guarded_project_receipt.json')['original_code']
    plan=p.read(replay.BASE/'plan/collection_plan_source_v2.json')
    for rel in FILES:
        file=replay.ROOT/rel;original=file.read_bytes();original_sha=hashlib.sha256(original).hexdigest()
        expected=frozen.get(rel) or plan['source_code'].get(rel)
        if expected is None or expected!=original_sha:raise ValueError('live source differs from device registration: '+rel)
        data=canonical(original)
        if re.search(rb'[A-Za-z]:[/\\]Users[/\\][^/\\\s]+',data):
            raise ValueError('personal path literal in source bundle')
        result=subprocess.run(['git','show',BASE_HEAD+':'+rel],cwd=replay.ROOT,capture_output=True,timeout=30)
        before=canonical(result.stdout) if result.returncode==0 else b''
        folder=target/'prerequisites'/rel;folder.parent.mkdir(parents=True,exist_ok=True);folder.write_bytes(data)
        hunks=list(difflib.unified_diff(before.decode().splitlines(True),data.decode().splitlines(True),
            fromfile='a/'+rel if result.returncode==0 else '/dev/null',tofile='b/'+rel))
        if hunks:
            patch.append('diff --git a/'+rel+' b/'+rel+'\n')
            if result.returncode!=0:patch.append('new file mode 100644\n')
            patch.extend(hunks)
        records.append(dict(path=rel,base_exists=result.returncode==0,base_head=BASE_HEAD,
            original_sha256=original_sha,canonical_utf8_lf_sha256=hashlib.sha256(data).hexdigest(),
            canonical_base_sha256=hashlib.sha256(before).hexdigest() if result.returncode==0 else None,
            transformation='UTF-8 without BOM; CRLF/CR -> LF only',content_change_beyond_line_endings=False,
            source_role='actual prerequisite WIP before opt-in replay patch'))
    (target/'portable_prerequisites.patch').write_text(''.join(patch),encoding='utf-8',newline='\n')
    # Prove the cumulative clean-base prerequisite + separate opt-in patch, without
    # changing the user's working tree or the already frozen device code.
    android_pre={rel:canonical((replay.ROOT/rel).read_bytes()).decode() for rel in (PKG+'ArrivalEnergyActivity.kt',PKG+'ArrivalRecordedReplay.kt')}
    transforms={PKG+'ArrivalEnergyActivity.kt':replay.build.activity_source,PKG+'ArrivalRecordedReplay.kt':replay.build.replay_source}
    runtime=[]
    snapshot=replay.BASE/'guarded_project'
    for rel,source in android_pre.items():
        transformed=transforms[rel](source).encode()
        actual=canonical((snapshot/rel).read_bytes())
        if transformed!=actual:raise ValueError('prerequisite plus opt-in transform differs from executed Android snapshot')
        runtime.append(dict(path=rel,executed_canonical_sha256=hashlib.sha256(actual).hexdigest(),
            prerequisite_plus_opt_in_matches_executed_snapshot=True))
    receipt=dict(status='PASS_required_WIP_preserved_separate_bundle',base_head=BASE_HEAD,
        prerequisite_files=records,runtime_match=runtime,
        patch_sha256=p.digest(target/'portable_prerequisites.patch'),
        opt_in_patch_sha256=p.digest(replay.PUBLIC/'frozen_plan_replay_v2.patch'),
        private_apk_sha256=plan['apk_sha256'],original_user_sources_modified=0,
        APK_models_keys_raw_personal_paths_distributed=0,
        scope='source prerequisites for PC verification and same runtime compile; not a fresh device budget or bit-identical APK promise')
    ptarget=target/'manifest.json';ptarget.write_bytes(p.canonical(receipt))
    text=f'''# Separate source prerequisites for the frozen-plan replay

Base Git HEAD: `{BASE_HEAD}`. The live repository has preserved user WIP. The
actual device build used that WIP plus the opt-in frozen-plan patch. This bundle
lets a reviewer reproduce the needed code without staging the original WIP.

`prerequisites/` holds 11 necessary source/test files only. Original byte SHA and
UTF-8/LF SHA are both in `manifest.json`; only BOM/line endings were normalized.
The two executed Android classes are independently checked against the private
build snapshot after applying the same opt-in transformation.

Use a separate clean checkout or review directory, never overwrite the user's
working copy. From a checkout at the base HEAD, apply
`portable_prerequisites.patch`, then make the new overnight tools available from
the result commit. Run:

```powershell
git apply --check docs/results/overnight_device_20261011/source_bundle/portable_prerequisites.patch
git apply docs/results/overnight_device_20261011/source_bundle/portable_prerequisites.patch
python -B -X utf8 -m unittest tools.test_d1_overnight_device_replay -v
```

The isolated build helper applies the separate replay opt-in transform to its
private copy. Do not apply `frozen_plan_replay_v2.patch` to the source and then
run that transform again. SDK/JBR are environment-derived; the existing project
signing key and exact measured model/input artifacts must already be available
locally and are deliberately excluded. Build timestamps/toolchain and signing
configuration may prevent bit-identical APK reproduction; recorded SHA pins
the actual artifact, not a claim that all rebuilds have that SHA.

Do not reuse the consumed session UUIDs/registry or acquire a new device budget
from a fresh checkout. The published schedules and metrics are available for
read-only reconstruction. A new physical run requires its own bounded approved
ID and plan; no fresh execution is triggered by this source bundle.
'''
    (target/'README.md').write_text(text,encoding='utf-8')
    print(json.dumps({k:v for k,v in receipt.items() if k not in ('prerequisite_files','runtime_match')},indent=2))


def flatten_existing():
    """Portable copies only; preserve the original source tree and manifest v1."""
    target=replay.PUBLIC/'source_bundle';old=p.read(target/'manifest.json')
    if (target/'manifest_v2.json').exists():raise ValueError('flat archive already registered')
    flat=target/'flat';flat.mkdir(exist_ok=False);records=[]
    for index,entry in enumerate(old['prerequisite_files']):
        relative=f"flat/{index:02d}_{Path(entry['path']).name}"
        original=target/'prerequisites'/entry['path'];data=original.read_bytes()
        if hashlib.sha256(data).hexdigest()!=entry['canonical_utf8_lf_sha256']:
            raise ValueError('original archived source drift')
        (target/relative).write_bytes(data)
        records.append(dict(entry,logical_path=entry['path'],archive_path=relative,
            original_deep_archive_preserved=True))
    result=dict(old,archive_manifest_version=2,archive_layout='flat_no_nested_repository_path',
        prerequisite_files=records,base_manifest_v1_sha256=p.digest(target/'manifest.json'),
        migration_reason='Windows MAX_PATH in longer review checkout; source bytes/native contract unchanged',
        Git_omit='source_bundle/prerequisites/**; preserved locally only',
        original_source_bytes_modified=0,new_native_or_device_runs=0)
    (target/'manifest_v2.json').write_bytes(p.canonical(result))
    (target/'README.md').write_text('''# 동결 재생 실행을 위한 별도 source prerequisite

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
''',encoding='utf-8')
    print(json.dumps(dict(status='PASS_flat_portable_archive_v2',files=len(records),
        manifest_v1_preserved=True,original_deep_files_preserved=True,
        native_or_device_runs=0,manifest_v2_sha256=p.digest(target/'manifest_v2.json')),indent=2))


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['export','flatten'],nargs='?',default='export')
    a=parser.parse_args();main() if a.action=='export' else flatten_existing()
