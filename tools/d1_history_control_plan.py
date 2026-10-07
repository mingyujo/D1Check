"""Opt-in history campaign. Prepare/Check are PC-only; Run requires explicit approval."""
import argparse
import copy
import hashlib
import json
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path
from tools import d1_background_activity_plan as bg
from tools import d1_arrival_plan as p
from tools import d1_arrival_energy_collection as old
from tools import d1_arrival_timing_calibration as cal
from tools import d1_apk_identity as apk
from tools import d1_history_control_analysis as analysis

ROOT=bg.ROOT
NAME='ENERGY-AP-HISTORY-CONTROL-01'
FOLDER='energy_ap_history_control_plan_v1'
DESIGN=ROOT/'docs/results/history_control_plan_01/design.json'
TRACE=ROOT/'tools/perfetto/history_control.pbtxt'
require=old.require


def budget():
    b=dict(bg.prior.BUDGET,sessions=12,development_sessions=6,confirmation_sessions=6,
        requests=1920,conditioning_requests=1152,target_requests=768,warmup=96,
        explicit_inference=2016,runtime_creations=48,staging=12,staging_files=84,
        installed_host_pulls=1,apk_transfers=1,installs=1,installation_seconds=600,
        host_poll_seconds=925,recovery_seconds=120,cleanup_seconds=45,
        app_drain_seconds=0,app_watchdog_seconds=900,stage_gate_seconds=120,
        trace_start_seconds=90,app_launch_seconds=26,trace_recovery_seconds=120,
        trace_content_audit_seconds=40,trace_max_seconds=1000,trace_max_bytes=134217728,
        trace_host_pulls=12,intersession_cooling_seconds=90,transport_selection_seconds=15,
        development_freeze_seconds=300,final_analysis_seconds=300,
        per_session_adb_commands=7600,adb_commands=200+12*7600,
        external_selection_adb_commands=0,adb_recovery_cleanup_reserve=500,
        fixed_registered_seconds=5220,fixed_intersession_seconds=990)
    b['session_seconds']=sum(b[k] for k in ('stage_gate_seconds','trace_start_seconds',
        'app_launch_seconds','host_poll_seconds','recovery_seconds','cleanup_seconds','trace_recovery_seconds'))
    b['history_poll_recovery_reserve']=sum(b[k] for k in ('app_launch_seconds','host_poll_seconds','recovery_seconds','cleanup_seconds'))
    b['total_seconds']=600+12*b['session_seconds']+990+300+300+15
    require(b['total_seconds']<=21600 and b['requests']+b['warmup']==2016,'budget arithmetic')
    return b


def identity():
    files=[Path(__file__),ROOT/'tools/d1_history_recovery_campaign.py',ROOT/'tools/d1_postapproval_observation.py',Path(analysis.__file__),Path(bg.__file__),DESIGN,TRACE,
        Path(bg.inputs.__file__),ROOT/'tools/d1_background_activity_readout.py',
        Path(analysis.m.__file__),Path(analysis.m.thermal.__file__),Path(analysis.m.memory.__file__),
        Path(analysis.m.base.__file__),Path(analysis.states.__file__),
        *[ROOT/f'tools/perfetto/background_{n}.sql' for n in ('sched','frequency','loss','clock','cpu')]]
    return old.identity()|{f.relative_to(ROOT).as_posix():p.digest(f) for f in files}


def script_text():
    return bg.prior.script_text({}).replace('d1_arrival_ap_confirmation','d1_history_control_plan').replace(
        'python -B',"& 'C:/Users/LG/AppData/Local/Programs/Python/Python311/python.exe' -X utf8 -B")


def specification(source_file,build_file,output):
    source_file,build_file,output=map(Path,(source_file,build_file,output))
    source,build=p.read(source_file),p.read(build_file)
    require(old.apk_sources(build['source_code'])==old.apk_sources(cal.code_identity()),'APK/source mismatch')
    require(p.digest(build['apk_path'])==build['apk_sha256'],'APK drift')
    candidate=apk.inspect(build['apk_path'],source['apk_preflight']['toolchain'])
    require(candidate['signer_sha256']==source['apk_preflight']['candidate']['signer_sha256'],'project signer')
    plan=copy.deepcopy(source)
    for k in list(plan):
        if k.startswith(('separated_','ap_','resident_','recorded_','online_','study_','previous_','campaign_')):plan.pop(k)
    plan.update(history_control=True,background_activity_contrast=True,installed_only=False,
        online_policy_study=True,online_configuration_owner_v1=True,study_phase='development',
        experiment_id=NAME,approval='not_approved',experiment_ready=False,
        status='PC_READY_DEVICE_UNVERIFIED_NOT_APPROVED',minimum_host_free_bytes=4*2**30,
        budget=budget(),source_code=identity(),
        source_plan=dict(path=str(source_file.resolve()),sha256=p.digest(source_file)),
        build_receipt=str(build_file.resolve()),build_receipt_sha256=p.digest(build_file),
        apk_path=build['apk_path'],apk_sha256=build['apk_sha256'],
        apk_preflight=dict(source['apk_preflight'],candidate=candidate),
        analysis_contract=dict(path=str(DESIGN),sha256=p.digest(DESIGN)),
        input_bundle=dict(path=str(DESIGN),sha256=p.digest(DESIGN)),
        activity_model=dict(path=str(analysis.m.MODEL),sha256=analysis.m.MODEL_SHA),
        output_root=str(output.parent/'energy_ap_history_control_run_v1'),
        registry=str(output.parent/'history_control_registry'/NAME),entries=[],
        history_trace=dict(path=str(TRACE),sha256=p.digest(TRACE),duration_ms=1000000,max_bytes=134217728),
        measurement_protocol_change='same-resident registered conditioning/recovery/target; 900s watchdog; 1000s trace 128MiB; numeric gate before conditioning only; target numeric coverage checked from host observations, not a second handshake; opt-in postapproval progress listing starts at least 2s after previous result, one recorded silent gap per session with fresh thermal/screen; mandatory environment failures remain fatal',
        analysis_scope='conditional registered-history diagnostic; no default/strict adoption; no accuracy PASS',
        prewarmup_observation='precommon-observation-gap-v3',
        postapproval_observation='postapproval-listing-gap-v1',postapproval_environment='postapproval-environment-lease-v1')
    plan['trace_content_audit']=dict(source['trace_content_audit'],window='conditioning_start_to_target_end',trace_recovery_seconds=120)
    template=p.read(source_file.parent/source['entries'][0]['manifest']);manifests=[]
    policies=dict(C0='C0',CPU='CPU_URGENT_ONLINE_V1',PAR='B2_PARALLEL_ONLINE_V1')
    for i,cell in enumerate(p.read(DESIGN)['entries']):
        m=copy.deepcopy(template)
        for k in list(m):
            if k.startswith(('policy_study','power_identification','resident_control','replay_','source_')):m.pop(k)
        sid=str(uuid.uuid5(uuid.NAMESPACE_URL,NAME+'/'+cell['id']));policy=policies[cell['target_policy']]
        def rows(kind):
            values=bg.inputs.requests('confirmation',sid)
            for r in values:r['request_id']=str(uuid.uuid5(uuid.NAMESPACE_URL,sid+'/'+kind+'/'+str(r['ordinal'])))
            return values
        target=[] if policy=='C0' else rows('target')
        m.update(experiment_id=NAME,session_id=sid,phase=cell['id'],scenario='burst' if policy=='C0' else 'separated_power',
            policy='RECORDED_B2_REPLAY_V1' if policy=='C0' else policy,requests=target,
            conditioning_requests=rows('conditioning'),history_control_version=analysis.VERSION,
            history_role=cell['role'],history_recovery_seconds=cell['recovery_pause_seconds'],history_target_policy=policy,
            maximum_duration_ms=900000,background_observation_version=bg.VERSION,background_observation_role='development',
            power_sampling_version='online-power-phase-audit-v1',power_sample_period_ms=900,
            start_ap_gate='numeric-ap-observe-v2',apk_sha256=build['apk_sha256'])
        if policy=='C0':m.update(resident_control_version='resident-control-pair-v1',resident_control_role='no_load_control',replay_version='recorded-b2-dispatch-gate-v1')
        else:m['power_identification_version']='separated-power-input-v1'
        for s in m['models'].values():s['identity']['session_id']=sid;s['target']['apk_sha256']=build['apk_sha256']
        rel='manifests/'+sid+'.json';manifests.append(m)
        plan['entries'].append(dict(index=i,phase=cell['id'],role=cell['role'],condition=policy,scenario=m['scenario'],policy=m['policy'],
            session_id=sid,manifest=rel,manifest_sha256=hashlib.sha256(p.canonical(m)).hexdigest(),
            requests=len(target),conditioning_requests=96,warmup=8,runtime_creations=4))
    plan['run_script_sha256']=hashlib.sha256(script_text().encode('utf8')).hexdigest()
    return plan,manifests


def check(file):
    file=Path(file);plan=p.read(file)
    if plan.get('history_recovery_child'):
        from tools.d1_history_recovery_campaign import check_child
        return check_child(file)
    require(file.parent.name==FOLDER and not Path(plan['registry']).exists() and not Path(plan['output_root']).exists(),'consumed/occupied')
    require(shutil.disk_usage(file.parent).free>=plan['minimum_host_free_bytes'],'4GiB disk admission')
    expected,ms=specification(plan['source_plan']['path'],plan['build_receipt'],file.parent)
    require(expected==plan and (file.parent/'RUN_AFTER_APPROVAL.ps1').read_text(encoding='utf8')==script_text(),'plan/script drift')
    for x in [plan['frozen_model'],plan['activity_model'],*plan['source_files'].values(),*plan['references'].values()]:require(p.digest(x['path'])==x['sha256'],'binding drift')
    require(p.digest(analysis.m.MODEL)==analysis.m.MODEL_SHA,'frozen model drift')
    audit=plan['trace_content_audit'];require(p.digest(audit['processor_path'])==audit['processor_sha256'],'trace processor drift')
    for e,m in zip(plan['entries'],ms):require(p.digest(file.parent/e['manifest'])==e['manifest_sha256'] and p.read(file.parent/e['manifest'])==m,'manifest drift')
    return dict(status=plan['status'],plan_sha256=p.digest(file),budget=budget(),device_commands=0)


def prepare(source,build,output):
    output=Path(output);require(output.name==FOLDER and not output.exists(),'fresh plan only')
    plan,ms=specification(source,build,output)
    require(not Path(plan['registry']).exists() and not Path(plan['output_root']).exists(),'occupied')
    output.mkdir();(output/'manifests').mkdir()
    for e,m in zip(plan['entries'],ms):cal.write_new(output/e['manifest'],m)
    (output/'RUN_AFTER_APPROVAL.ps1').write_text(script_text(),encoding='utf8',newline='\n')
    cal.write_new(output/'collection_plan.json',plan)
    return check(output/'collection_plan.json')


def load_cases(plan,root,entries):
    cases=[]
    for e in entries:
        folder=Path(root)/f"{e['index']:02d}_{e['session_id']}"
        require(p.read(folder/'validated.json')['status']=='eligible_descriptive_only','session eligibility')
        require(p.digest(folder/'input_manifest.json')==e['manifest_sha256'],'executed manifest drift')
        cases.append(analysis.load_case(folder,p.read(folder/'input_manifest.json')))
    return cases


def reuse_entry(plan,root,entry):
    config=plan['history_reuse']
    reuse=next(x for x in config['entries'] if x['index']==entry['index']) if 'entries' in config else config
    source=Path(reuse['source_folder'])
    require({str(f.relative_to(source)):p.digest(f) for f in source.rglob('*') if f.is_file()}==reuse['file_sha256'],'reused raw drift')
    manifest=p.read(source/'input_manifest.json')
    require(p.digest(source/'input_manifest.json')==entry['manifest_sha256'],'reused manifest drift')
    stats=analysis.validate(source,manifest,plan)
    target=Path(root)/f"{entry['index']:02d}_{entry['session_id']}"
    shutil.copytree(source,target,ignore=shutil.ignore_patterns('validated.json','reuse_provenance.json'))
    stats.update(reused_evidence=True,reused_source_sha256=reuse['file_sha256']['input_manifest.json'],new_device_calls=0)
    cal.write_new(target/'validated.json',stats)
    cal.write_new(target/'reuse_provenance.json',reuse)
    return stats


def reuse_first(plan,root):return reuse_entry(plan,root,plan['entries'][0])


def freeze_verify(plan,root):
    root=Path(root);receipt=p.read(root/'history_freeze_receipt.json');freeze=p.read(root/'history_candidate_freeze.json')
    require(p.digest(root/'history_candidate_freeze.json')==receipt['sha256'],'candidate drift')
    require(freeze['source_code']==plan['source_code']==identity(),'analysis code drift')
    require(freeze['frozen_model_sha256']==p.digest(analysis.m.MODEL)==analysis.m.MODEL_SHA,'original model drift')
    for path,digest in freeze['development_evidence'].items():require(p.digest(root/path)==digest,'development evidence drift')
    return freeze


def pc_stage(plan,root,action,seconds):
    # Bounded child; no device capabilities, no detached owner, preserve original exception.
    with (Path(root)/(action+'.log')).open('xb') as log:
        subprocess.run([sys.executable,'-X','utf8','-B','-m','tools.d1_history_control_plan',action,
            '--plan',str(Path(root)/'frozen_collection_plan.json')],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,
            timeout=seconds,check=True)


def before_entry(plan,root,entry,complete,hard):
    b=plan['budget'];remaining=len(plan['entries'])-entry['index']
    reserve=remaining*b['session_seconds']+(remaining if entry['index'] else remaining-1)*b['intersession_cooling_seconds']+b['final_analysis_seconds']
    if entry['index']<=6:reserve+=b['development_freeze_seconds']
    require(hard-time.monotonic()>=reserve,'remaining campaign reservation')
    if entry['index']==6:
        require(len(complete)==6 and all(x['status']=='eligible_descriptive_only' for x in complete),'six eligible development sessions')
        pc_stage(plan,root,'freeze',b['development_freeze_seconds'])
    if entry['index']>=6:freeze_verify(plan,root)


def freeze(plan,root):
    root=Path(root);cases=load_cases(plan,root,plan['entries'][:6])
    original_only=plan.get('original_model_confirmation',False)
    if original_only:
        comparator=plan['fixed_memory_comparator'];require(p.digest(comparator['path'])==comparator['sha256'],'rejected comparator drift')
        previous=p.read(comparator['path']);require(previous['status']=='development_gate_stop','prior rejection must be preserved')
        result=dict(candidate=previous['candidate'],development_ids=[c['id'] for c in cases])
    else:
        result=analysis.develop(cases,p.read(analysis.m.MODEL));cal.write_new(root/'history_development_result.json',result)
        require(result['status']=='ready_to_freeze','development gate failed; no confirmation')
    evidence={str(f.relative_to(root)):p.digest(f) for e in plan['entries'][:6]
        for f in (root/f"{e['index']:02d}_{e['session_id']}").rglob('*') if f.is_file() and f.name not in ('system_activity.pftrace',)}
    obj=dict(version=analysis.VERSION,candidate=result['candidate'],development_ids=result['development_ids'],
        source_code=plan['source_code'],frozen_model_sha256=analysis.m.MODEL_SHA,development_evidence=evidence,
        prediction_inputs='preconditioning AP + actual registered schedule; no target postload AP/current',
        accuracy_pass=None,strict_support=False,experiment_ready=False)
    if original_only:
        obj.update(selected_model='ORIGINAL_FROZEN',memory_candidate_status='rejected; fixed secondary comparator only',
            new_fit_calls=0,original_model_sha256=analysis.m.MODEL_SHA,prior_development_gate='development_gate_stop',
            original_prediction_inputs='actual target schedule + permitted target pre-load AP and idle power; no post-load AP/current')
    cal.write_new(root/'history_candidate_freeze.json',obj)
    from tools.d1_arrival_device import utc
    cal.write_new(root/'history_freeze_receipt.json',dict(sha256=p.digest(root/'history_candidate_freeze.json'),utc=utc()))


def finish_analysis(plan,root):
    freeze_verify(plan,root);pc_stage(plan,root,'analyze',plan['budget']['final_analysis_seconds'])


def analyze(plan,root):
    root=Path(root);f=freeze_verify(plan,root);cases=load_cases(plan,root,plan['entries'])
    rows=[dict(analysis.evaluate(c,p.read(analysis.m.MODEL),f['candidate']),role=c['role']) for c in cases]
    cal.write_new(root/'history_analysis.json',dict(rows=rows,freeze_sha256=p.digest(root/'history_candidate_freeze.json'),accuracy_pass=None,experiment_ready=False))
    flat=[]
    for r in rows:
        for name in ('frozen','candidate'):
            flat.append(dict(id=r['id'],role=r['role'],gap=r['gap'],policy=r['target_policy'],model=name,
                **r[name],observed_j=r['observed_j'],predicted_j=r['predicted_j'],signed_j=r['signed_j']))
    analysis.m.table(root/'history_metrics.csv',flat)


def main():
    cli=argparse.ArgumentParser();cli.add_argument('action',choices=['prepare','check','run','freeze','analyze'])
    for name in ('plan','source','build','output','adb','serial','expected-sha'):cli.add_argument('--'+name)
    cli.add_argument('--approved',action='store_true');a=cli.parse_args()
    if a.action=='prepare':r=prepare(a.source,a.build,a.output)
    elif a.action=='check':r=check(a.plan)
    elif a.action in ('freeze','analyze'):
        plan=p.read(a.plan);root=Path(a.plan).parent
        require(root==Path(plan['output_root']) and (root/'frozen_collection_plan.json').is_file(),'owned run required')
        require(plan['source_code']==identity(),'source drift')
        r=freeze(plan,root) if a.action=='freeze' else analyze(plan,root)
    else:
        from tools.d1_arrival_energy_collection_device import run
        r=run(a.plan,a.adb,a.serial,a.expected_sha,a.approved)
    print(json.dumps(r,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
