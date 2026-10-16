"""Build an isolated frozen-plan replay without editing the Android working tree."""
from __future__ import annotations

import argparse
import difflib
import json
import os
from pathlib import Path
import shutil
import subprocess

from tools import d1_arrival_plan as p
from tools import d1_arrival_timing_calibration as cal
from tools import d1_apk_identity as apk

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'output/overnight_device_20261011_v1'
PUBLIC = ROOT / 'docs/results/overnight_device_20261011'
VERSION = 'frozen-plan-96-cpu-gpu-replay-v2'


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as stream:
        stream.write(p.canonical(value))


def replace_once(text, before, after):
    if text.count(before) != 1:
        raise ValueError('Android source drift; required match count != 1')
    return text.replace(before, after)


def replay_source(original):
    out = replace_once(original, '    const val COMPARISON_VERSION = "recorded-policy-comparison-v1"',
        '    const val COMPARISON_VERSION = "recorded-policy-comparison-v1"\n'
        f'    const val FROZEN_PLAN_VERSION = "{VERSION}"\n\n'
        '    /** Exact opt-in 96-request device-validation trace. This is not an online policy. */\n'
        '    fun validateFrozenRequests(scenario: String, requests: List<ArrivalEnergyContract.Request>) {\n'
        '        require(scenario == "frozen_plan_periodic96")\n'
        '        require(requests.size == 96 && requests.map { it.id }.toSet().size == 96)\n'
        '        requests.forEachIndexed { i, q ->\n'
        '            val urgent = i % 2 == 0\n'
        '            require(q.ordinal == i && q.offsetMs == 35_000L + i * 350L)\n'
        '            require(q.task == (if (urgent) "classification" else "detection"))\n'
        '            require(q.priority == (if (urgent) "urgent" else "normal"))\n'
        '            require(q.deadlineMs == (if (urgent) 1500L else 6000L))\n'
        '        }\n'
        '    }')
    out = replace_once(out,
        '        require(version == VERSION || version == COMPARISON_VERSION)\n'
        '        require(if (version == VERSION) sourcePolicy == "B2_PC"\n'
        '                else sourcePolicy in setOf("CPU_URGENT", "B2_PC"))',
        '        require(version in setOf(VERSION, COMPARISON_VERSION, FROZEN_PLAN_VERSION))\n'
        '        if (version == FROZEN_PLAN_VERSION) require(sourcePolicy.isNotBlank())\n'
        '        else require(if (version == VERSION) sourcePolicy == "B2_PC"\n'
        '                else sourcePolicy in setOf("CPU_URGENT", "B2_PC"))')
    out = replace_once(out,
        '            require(entry.backend == (if (sourcePolicy == "CPU_URGENT") "CPU"\n'
        '                else if (entry.task == "classification") "GPU" else "CPU"))',
        '            if (version == FROZEN_PLAN_VERSION) {\n'
        '                require(entry.backend in setOf("CPU", "GPU"))\n'
        '                require(entry.task != "detection" || entry.backend == "CPU")\n'
        '            } else require(entry.backend == (if (sourcePolicy == "CPU_URGENT") "CPU"\n'
        '                else if (entry.task == "classification") "GPU" else "CPU"))')
    out = replace_once(out,
        '               elapsedNs: Long, freeCpu: Boolean, freeGpu: Boolean): ArrivalPolicy.Choice? {',
        '               elapsedNs: Long, freeCpu: Boolean, freeGpu: Boolean,\n'
        '               runningTasks: Map<String,String> = emptyMap(), version: String = VERSION): ArrivalPolicy.Choice? {')
    out = replace_once(out,
        '                (if (entry.backend == "CPU") freeCpu else freeGpu) }',
        '                (if (entry.backend == "CPU") freeCpu else freeGpu) &&\n'
        '                (version != FROZEN_PLAN_VERSION ||\n'
        '                    !(entry.task == "classification" &&\n'
        '                      runningTasks[if (entry.backend == "CPU") "GPU" else "CPU"] == "classification")) }')
    return out


def activity_source(original):
    out = replace_once(original,
        '            } else ArrivalEnergyContract.validateSession(m.getString("scenario"), requests, controlVersion, controlRole)',
        '            } else if (m.optString("replay_version") == ArrivalRecordedReplay.FROZEN_PLAN_VERSION) {\n'
        '                check(policy == ArrivalRecordedReplay.POLICY && controlVersion.isEmpty() && controlRole.isEmpty())\n'
        '                ArrivalRecordedReplay.validateFrozenRequests(m.getString("scenario"), requests)\n'
        '            } else ArrivalEnergyContract.validateSession(m.getString("scenario"), requests, controlVersion, controlRole)')
    out = replace_once(out,
        '                check(replayVersion in setOf(ArrivalRecordedReplay.VERSION, ArrivalRecordedReplay.COMPARISON_VERSION))\n'
        '                val sourcePolicy = if (replayVersion == ArrivalRecordedReplay.COMPARISON_VERSION)',
        '                check(replayVersion in setOf(ArrivalRecordedReplay.VERSION, ArrivalRecordedReplay.COMPARISON_VERSION, ArrivalRecordedReplay.FROZEN_PLAN_VERSION))\n'
        '                val sourcePolicy = if (replayVersion != ArrivalRecordedReplay.VERSION)')
    out = replace_once(out,
        '            val busy = mutableMapOf("CPU" to false, "GPU" to false)',
        '            val busy = mutableMapOf("CPU" to false, "GPU" to false)\n'
        '            val replayRunningTasks = mutableMapOf<String,String>()')
    out = replace_once(out,
        '                            !busy.getValue("CPU"), !busy.getValue("GPU"))',
        '                            !busy.getValue("CPU"), !busy.getValue("GPU"), replayRunningTasks,\n'
        '                            m.getString("replay_version"))')
    out = replace_once(out,
        '                    busy[choice.backend] = true',
        '                    busy[choice.backend] = true\n'
        '                    replayRunningTasks[choice.backend] = choice.ticket.task')
    out = replace_once(out,
        '                                observed.release(key); busy[choice.backend] = false',
        '                                observed.release(key); busy[choice.backend] = false\n'
        '                                replayRunningTasks.remove(choice.backend)')
    return out


TEST_SOURCE = '''package com.example.d1check.benchmarkrunner

import org.junit.Assert.*
import org.junit.Test

class OvernightFrozenPlanTest {
    private fun requests() = (0 until 96).map { i ->
        val urgent = i % 2 == 0
        ArrivalEnergyContract.Request("id-$i",i,if (urgent) "classification" else "detection",
            if (urgent) "urgent" else "normal",35_000L+i*350L,if (urgent) 1500L else 6000L)
    }
    private fun entries() = requests().map { q -> ArrivalRecordedReplay.Entry(q.id,q.ordinal,q.task,
        q.offsetMs*1_000_000L,q.offsetMs*1_000_000L+250_000_000L,
        if (q.task=="detection" || q.ordinal%4==0) "CPU" else "GPU","source/${q.ordinal}") }
    @Test fun acceptsOnlyExactNewTraceAndSupportedResources() {
        val req=requests(); val rows=entries()
        ArrivalRecordedReplay.validateFrozenRequests("frozen_plan_periodic96",req)
        ArrivalRecordedReplay.validate(rows,req,ArrivalRecordedReplay.FROZEN_PLAN_VERSION,"IE_FROZEN")
        for (bad in listOf(rows.map { it.copy(backend="NPU") }, rows.map { if (it.task=="detection") it.copy(backend="GPU") else it })) {
            try { ArrivalRecordedReplay.validate(bad,req,ArrivalRecordedReplay.FROZEN_PLAN_VERSION,"IE_FROZEN"); fail("unsupported") }
            catch (_: IllegalArgumentException) {}
        }
        try { ArrivalRecordedReplay.validateFrozenRequests("frozen_plan_periodic96",req.map { it.copy(offsetMs=it.offsetMs+1) }); fail("shifted") }
        catch (_: IllegalArgumentException) {}
        try { ArrivalRecordedReplay.validate(rows,req); fail("legacy broadened") }
        catch (_: IllegalArgumentException) {}
    }
    @Test fun busyLaneAndReleasePreserveRequest() {
        val rows=entries().associateBy { it.id }
        val waiting=requests().take(2).map { ArrivalPolicy.Ticket(it.id,it.task,it.priority,it.ordinal) }
        assertNull(ArrivalRecordedReplay.choose(waiting,rows,35_249_999_999L,true,true))
        assertNull(ArrivalRecordedReplay.choose(waiting,rows,35_900_000_000L,false,true))
        assertEquals("id-0",ArrivalRecordedReplay.choose(waiting,rows,35_900_000_000L,true,true)!!.ticket.id)
        assertEquals(2,waiting.size)
        assertEquals("id-1",ArrivalRecordedReplay.choose(waiting.drop(1),rows,35_900_000_000L,true,true)!!.ticket.id)
    }
    @Test fun lateActualReleaseCannotCreateUnmeasuredClassCpuGpuPair() {
        val rows=entries().associateBy { it.id }
        val waiting=requests().take(3).map { ArrivalPolicy.Ticket(it.id,it.task,it.priority,it.ordinal) }
        val version=ArrivalRecordedReplay.FROZEN_PLAN_VERSION
        assertNull(ArrivalRecordedReplay.choose(waiting.take(1),rows,36_000_000_000L,true,false,mapOf("GPU" to "classification"),version))
        assertEquals("id-1",ArrivalRecordedReplay.choose(waiting,rows,36_000_000_000L,true,false,mapOf("GPU" to "classification"),version)!!.ticket.id)
        assertNull(ArrivalRecordedReplay.choose(waiting.drop(2),rows,36_000_000_000L,false,true,mapOf("CPU" to "classification"),version))
        assertEquals("id-2",ArrivalRecordedReplay.choose(waiting.drop(2),rows,36_000_000_000L,false,true,mapOf("CPU" to "detection"),version)!!.ticket.id)
        assertEquals(3,waiting.size)
    }
}
'''


INIT_SOURCE = '''def dest = System.getenv('D1_OVERNIGHT_BUILD_ROOT')
def snapshot = System.getenv('D1_OVERNIGHT_SOURCE_SNAPSHOT')
if (!dest || !snapshot) throw new GradleException('isolated roots required')
gradle.beforeProject { project ->
    project.layout.buildDirectory.set(new File(dest, project.path.replace(':', '_')))
    project.afterEvaluate {
        if (project.path == ':benchmark-runner') {
            project.android.sourceSets.getByName('modelProbe').java.setSrcDirs([new File(snapshot,'modelProbe')])
            project.android.sourceSets.getByName('testModelProbe').java.setSrcDirs([new File(snapshot,'testModelProbe')])
        }
    }
}
'''


def prepare():
    target = BASE / 'build_snapshot'
    if target.exists():
        raise ValueError('snapshot already prepared; do not reset')
    target.mkdir(parents=True)
    PUBLIC.mkdir(parents=True, exist_ok=True)
    before = cal.code_identity()
    for name in ('modelProbe', 'testModelProbe'):
        shutil.copytree(ROOT / f'benchmark-runner/src/{name}/java', target / name)
    package = Path('com/example/d1check/benchmarkrunner')
    diffs = []
    for name, transform in [('ArrivalRecordedReplay.kt', replay_source), ('ArrivalEnergyActivity.kt', activity_source)]:
        file = target / 'modelProbe' / package / name
        old = file.read_text(encoding='utf-8')
        new = transform(old)
        file.write_text(new, encoding='utf-8', newline='\n')
        rel = f'benchmark-runner/src/modelProbe/java/{package.as_posix()}/{name}'
        diffs.extend(difflib.unified_diff(old.splitlines(True),new.splitlines(True),fromfile='a/'+rel,tofile='b/'+rel))
    (target / 'testModelProbe' / package / 'OvernightFrozenPlanTest.kt').write_text(TEST_SOURCE,encoding='utf-8',newline='\n')
    patch = PUBLIC / 'frozen_plan_replay_v2.patch'
    patch.write_text(''.join(diffs),encoding='utf-8',newline='\n')
    (PUBLIC / 'OvernightFrozenPlanTest.kt').write_text(TEST_SOURCE,encoding='utf-8',newline='\n')
    (PUBLIC / 'isolated_build.gradle').write_text(INIT_SOURCE,encoding='utf-8',newline='\n')
    if cal.code_identity() != before:
        raise ValueError('Android working sources changed during snapshot')
    result = dict(status='snapshot_not_built',original_code=before,
        snapshot_files={str(x.relative_to(target)):p.digest(x) for x in target.rglob('*') if x.is_file()},
        patch_sha256=p.digest(patch),source_snapshot=str(target),version=VERSION,
        android_worktree_changed=False,new_model_or_npu_actions=0)
    write(BASE / 'snapshot_receipt.json',result)
    return result


def build():
    guarded = (BASE/'guarded_project_receipt.json').exists()
    receipt_file=BASE/('guarded_project_receipt.json' if guarded else 'snapshot_receipt.json')
    receipt = p.read(receipt_file)
    target = Path(receipt['source_snapshot'])
    for rel,digest in receipt['snapshot_files'].items():
        if p.digest(target / rel) != digest:
            raise ValueError('snapshot drift')
    prior_attempts = len(list(BASE.glob('isolated_build*')))
    if prior_attempts >= 4:
        raise ValueError('bounded build repair attempts exhausted')
    out = BASE / ('isolated_build' if not prior_attempts else f'isolated_build_{prior_attempts+1}')
    out.mkdir(exist_ok=False)
    sdk_root=os.environ.get('ANDROID_HOME') or str(Path(os.environ['LOCALAPPDATA'])/'Android/Sdk')
    jbr_root=os.environ.get('D1_ANDROID_STUDIO_JBR') or str(Path(os.environ['ProgramFiles'])/'Android/Android Studio/jbr')
    env = dict(os.environ,D1_OVERNIGHT_BUILD_ROOT=str(out / 'build'),D1_OVERNIGHT_SOURCE_SNAPSHOT=str(target),
        ANDROID_HOME=sdk_root,JAVA_HOME=jbr_root,
        ANDROID_USER_HOME=str(ROOT/'.android-user'))
    project=Path(receipt['project_snapshot']) if guarded else ROOT
    command = [str(ROOT/'gradlew.bat'),'-p',str(project),'--no-configuration-cache','--init-script',str(PUBLIC/'isolated_build.gradle'),
        ':benchmark-runner:testModelProbeUnitTest','--tests','*ArrivalRecordedReplayTest',
        '--tests','*OvernightFrozenPlanTest','--tests','*ArrivalEnergyContractTest',
        ':benchmark-runner:assembleModelProbe','-PenableModelProbe=true','--console=plain']
    write(out / 'build_attempt.json',dict(command=command,snapshot_receipt_sha256=p.digest(receipt_file)))
    with (out/'build.log').open('xb') as log:
        subprocess.run(command,cwd=project,env=env,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=1800)
    apks = list((out/'build').glob('*/outputs/apk/modelProbe/*.apk'))
    if len(apks) != 1:
        raise ValueError('one isolated APK required')
    prior = p.read(ROOT/'output/model_v3_expert_20261010_v1/hybrid/plan/collection_plan.json')
    candidate = apk.inspect(apks[0],prior['apk_preflight']['toolchain'])
    if candidate['package'] != prior['apk_preflight']['candidate']['package'] or candidate['signer_sha256'] != prior['apk_preflight']['candidate']['signer_sha256']:
        raise ValueError('project package or signer changed')
    xmls = list((out/'build').glob('*/test-results/testModelProbeUnitTest/TEST-*.xml'))
    import xml.etree.ElementTree as et
    suites=[et.parse(x).getroot() for x in xmls]
    if not suites or not any('OvernightFrozenPlanTest' in s.attrib['name'] for s in suites) or any(int(s.attrib.get('failures',0))+int(s.attrib.get('errors',0)) for s in suites):
        raise ValueError('JVM validation incomplete')
    result=dict(status='built_tested_not_installed',apk_path=str(apks[0]),apk_sha256=p.digest(apks[0]),
        candidate=candidate,source_snapshot_receipt_sha256=p.digest(receipt_file),
        command=command,tests=sum(int(s.attrib['tests']) for s in suites),
        xml_sha256={str(x.relative_to(out)):p.digest(x) for x in xmls},
        version=VERSION,android_worktree_changed=False)
    write(BASE/('build_receipt_v2.json' if guarded else 'build_receipt.json'),result)
    return result


def guarded_project():
    """Full project copy avoids AGP Kotlin roots captured before afterEvaluate."""
    destination=BASE/'guarded_project'
    if destination.exists():raise ValueError('guarded project already frozen')
    destination.mkdir()
    before=cal.code_identity()
    for name in ('app','benchmark-runner','telemetry-contract','gradle'):
        shutil.copytree(ROOT/name,destination/name,ignore=shutil.ignore_patterns('build','.cxx','.gradle','.kotlin'))
    for name in ('build.gradle.kts','settings.gradle.kts','gradle.properties','gradlew','gradlew.bat'):
        shutil.copy2(ROOT/name,destination/name)
    package=Path('com/example/d1check/benchmarkrunner');diffs=[]
    for name,transform in [('ArrivalRecordedReplay.kt',replay_source),('ArrivalEnergyActivity.kt',activity_source)]:
        file=destination/'benchmark-runner/src/modelProbe/java'/package/name
        old=file.read_text(encoding='utf-8');new=transform(old);file.write_text(new,encoding='utf-8',newline='\n')
        rel=f'benchmark-runner/src/modelProbe/java/{package.as_posix()}/{name}'
        diffs.extend(difflib.unified_diff(old.splitlines(True),new.splitlines(True),fromfile='a/'+rel,tofile='b/'+rel))
    test=destination/'benchmark-runner/src/testModelProbe/java'/package/'OvernightFrozenPlanTest.kt'
    test.write_text(TEST_SOURCE,encoding='utf-8',newline='\n')
    shutil.copy2(PUBLIC/'frozen_plan_replay_v2.patch',BASE/'uninstalled_first_patch_v1.patch')
    (PUBLIC/'frozen_plan_replay_v2.patch').write_text(''.join(diffs),encoding='utf-8',newline='\n')
    (PUBLIC/'OvernightFrozenPlanTest.kt').write_text(TEST_SOURCE,encoding='utf-8',newline='\n')
    init="""def dest = System.getenv('D1_OVERNIGHT_BUILD_ROOT')
if (!dest) throw new GradleException('isolated build root required')
gradle.beforeProject { project ->
    project.layout.buildDirectory.set(new File(dest, project.path.replace(':', '_')))
}
"""
    (PUBLIC/'isolated_build.gradle').write_text(init,encoding='utf-8',newline='\n')
    if cal.code_identity()!=before:raise ValueError('repository Android working sources changed')
    result=dict(status='guarded_project_frozen_not_built',project_snapshot=str(destination),source_snapshot=str(destination),
        original_code=before,snapshot_files={str(x.relative_to(destination)):p.digest(x) for x in destination.rglob('*') if x.is_file()},
        prior_snapshot_receipt_sha256=p.digest(BASE/'snapshot_receipt.json'),
        patch_sha256=p.digest(PUBLIC/'frozen_plan_replay_v2.patch'),version=VERSION,
        android_worktree_changed=False,reason='CG_DC runtime owner guard and full source-root isolation; no device run yet')
    write(BASE/'guarded_project_receipt.json',result)
    return result


if __name__ == '__main__':
    args=argparse.ArgumentParser();args.add_argument('action',choices=['prepare','guarded-project','build']);a=args.parse_args()
    result=prepare() if a.action=='prepare' else guarded_project() if a.action=='guarded-project' else build()
    print(json.dumps({k:v for k,v in result.items() if k not in ('snapshot_files','original_code')},indent=2))
