"""PC-only GitHub progress and immutable closed-block publishing.

Reads existing local evidence, never imports a measurement executor or calls
ADB. Git stages only this task's live page and newly generated result folders.
Run once without --push before initial review; --watch --push is one writer.
"""
import argparse
import collections
import datetime as dt
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

from d1_a24_laptop_validator import load_json, sha256
from d1_a24_measurement_share_bundle import snapshot, encode, csv_bytes

ROOT=Path(__file__).resolve().parents[1]
LIVE=Path('docs/team/a24-measurement-revision02-20261015')
RESULTS=Path('docs/results/a24_measurement_share_20261016/automatic_checkpoints')
META=ROOT/'output/A24FOLLOW16/publication'
BRANCH='codex/a24-laptop-prep-20261014'


def utc():return dt.datetime.now(dt.timezone.utc)


def git(*args):
    return subprocess.check_output(['git',*args],cwd=ROOT,stderr=subprocess.STDOUT).decode('utf-8',errors='replace').strip()


def specifications():
    specs=[]
    entries=[('C10','output/A24R02C10/job.json')]
    pointer=META.parent/'LIVE_BINDING.json'
    if pointer.exists():
        b=load_json(pointer)
        entries += [(x['label'],x['job']) for x in b.get('additional_original_visits',[])]
        entries += [(x['label'],x['job']) for x in b.get('additional_matched_visits',[])]
    entries += [('EXTRA4_ORDER','output/A24R02R3/job.json'),('SUP12','output/A24SUP12/job.json')]
    for name,relative in entries:
        job=load_json(ROOT/relative);plan=load_json(Path(job['plan']));rows=plan['sessions']
        if name.startswith('C') and name[1:].isdigit():
            ids=load_json(Path(job['window_file']))['registered_session_ids'];byid={r['session_id']:r for r in rows};rows=[byid[s] for s in ids]
        elif name=='EXTRA4_ORDER':rows=rows[-1:]
        specs.append((name,relative,job,plan,rows))
    return specs


def reservation_root(name,job):
    if name=='SUP12':return Path(job['supplement_global_root'])
    if name=='EXTRA4_ORDER':return Path(job['extra4_global_root'])
    if name=='REBASE6':return Path(job['rebaseline_global_root'])
    return Path(load_json(Path(job['global_binding']))['global_reservation_root'])


def publication_signature(specs):
    """A stage starting is publishable progress even before its first closure."""
    result=[]
    for name,_,job,_,rows in specs:
        root=Path(job['run_root']);reservations=reservation_root(name,job)
        result.append((name,root.exists(),(reservations/'ACTIVE_OWNER.json').exists(),
            tuple(r['session_id'] for r in rows if (reservations/'reservations'/r['session_id']/'APP_LAUNCH_INTENT.json').exists()),
            tuple(sorted((q.name,sha256(q)) for q in root.glob('*.outcome.json'))),
            (root/'WINDOW_STOPPED.json').exists()))
    return tuple(result)


def refresh():
    META.mkdir(parents=True,exist_ok=True)
    pointer=META.parent/'LIVE_BINDING.json'
    binding=load_json(pointer) if pointer.exists() else {'active_original_meta':'output/A24R02C10','queue_meta':'output/A24FOLLOW16'}
    active_meta=Path(binding['active_original_meta'])
    observed=subprocess.run([sys.executable,'-B',str(active_meta/'PC_OBSERVE.py')],cwd=ROOT,capture_output=True,timeout=45)
    if observed.returncode:raise RuntimeError('PC observation failed; preserve last public status')
    state=load_json(ROOT/active_meta/'LIVE_STATUS.json');groups=[];newpaths=[];seen={}
    for name,relative,job,plan,rows in specifications():
        root=Path(job['run_root']);outcomes={}
        for row in rows:
            p=root/(row['session_id']+'.outcome.json')
            if p.is_file():outcomes[row['session_id']]=load_json(p)
        seen[name]={'registered':len(rows),'APP':0,'normal':sum(x['status']=='COMPLETE_TRACE_RECOVERED' for x in outcomes.values()),
            'rejected':sum(x['status']=='PRESTART_REJECT' for x in outcomes.values()),
            'host_failed':sum(x['status']=='FAILED_PRESERVED' for x in outcomes.values()),'ended':(root/'WINDOW_STOPPED.json').exists()}
        globalroot=reservation_root(name,job)
        seen[name].update(APP=sum((globalroot/'reservations'/r['session_id']/'APP_LAUNCH_INTENT.json').exists() for r in rows),
            run_root_started=root.exists(),worker_lock_present=(globalroot/'ACTIVE_OWNER.json').exists())
        pending=next((r for r in rows if r['session_id'] not in outcomes),None)
        if pending and root.exists() and not seen[name]['ended']:
            seen[name]['pending_prescription']=pending['prescription_id']
        blockgroups=collections.defaultdict(list)
        for r in rows:blockgroups[(r['block'],r['recipe'])].append(r)
        for (block,recipe),rs in blockgroups.items():
            label=name+'_'+block+'_'+recipe;folder=RESULTS/label
            if not (ROOT/folder).exists() and any(r['session_id'] in outcomes for r in rs):
                complete=all(r['session_id'] in outcomes for r in rs)
                # A closed session is immutable; never copy an active raw tree.
                normal=all(outcomes.get(r['session_id'],{}).get('status')=='COMPLETE_TRACE_RECOVERED' for r in rs)
                if (complete and normal) or seen[name]['ended']:
                    safe=True
                    for r in rs:
                        outcome=outcomes.get(r['session_id'])
                        if not outcome:continue
                        raw=root/'raw'/r['session_id']
                        if outcome['status']=='COMPLETE_TRACE_RECOVERED':
                            safe=safe and (raw/'journal_closed.json').is_file() and load_json(raw/'journal_closed.json')['status']=='SYNCED_AND_CLOSED'
                        else:
                            proof=root/'read_only_recovery'/r['session_id']/'CLOSED_FAILURE_RECOVERY.json'
                            safe=safe and proof.is_file() and load_json(proof).get('own_device_process_absent') is True
                    if safe:
                        private=META/label;private.mkdir()
                        # This subset is a publication view, NEVER an execution
                        # plan or a new independent validation registration.
                        view={**plan,'sessions':rs,'session_count':len(rs),'publication_view_only':True,
                            'original_execution_plan_sha256':sha256(Path(job['plan'])),'execution_authorized':False}
                        (private/'PUBLICATION_VIEW_NOT_EXECUTABLE.json').write_bytes(encode(view))
                        pubjob={**job,'plan':str(private/'PUBLICATION_VIEW_NOT_EXECUTABLE.json')}
                        (private/'job_publication_only.json').write_bytes(encode(pubjob))
                        cfg=load_json(ROOT/'output/a24_share_20261015/config_final_confirm.json')
                        cfg['families']=[{'id':name,'job':str(private/'job_publication_only.json'),'roots':[str(root)]}]
                        cfg['source_catalog_directories'] += [str(ROOT/'output/A24R02R1'),str(ROOT/'output/A24R02R2'),
                            str(ROOT/'output/A24R02R3'),str(ROOT/'output/A24SUP12'),str(Path(job['source_manifest']).parent)]
                        cfg['changes_notes'][name]=['Publication-only subset of original registered rows; not a new execution plan.',
                            'Only closed original raw bytes; no live raw or original scientific settings modified.',
                            'Original failures and separate post-observation supplement are not pooled; J unvalidated; AP HAL readout only.']
                        snapshot(cfg,ROOT/folder,private/'audit')
                        for r in rs:
                            recovery=root/'read_only_recovery'/r['session_id']
                            proof=recovery/'CLOSED_FAILURE_RECOVERY.json'
                            if proof.exists():
                                receipt=ROOT/folder/'execution_receipts';receipt.mkdir(exist_ok=True)
                                (receipt/(r['session_id']+'_failure_proof.json')).write_bytes(proof.read_bytes())
                                no_main=recovery/'recovered_app'/'NO_MAIN_READONLY_OBSERVATIONS.json'
                                if no_main.exists():(receipt/(r['session_id']+'_no_MAIN_observations.json')).write_bytes(no_main.read_bytes())
                        (ROOT/folder/'README.md').write_text('# A24 닫힌 비교 묶음 원자료\n\n'
                            +'이 폴더는 기존 등록 행의 공유용 부분 뷰이며 실행계획·독립 반복을 새로 만든 것이 아니다. '
                            +'정상 완료/시작 거절/미실행과 예정 작업량은 attempts_all.csv 및 각 ZIP의 BLOCK_STATUS.json을 확인한다. '
                            +'원자료는 원바이트이며 FILE_SHA256.json과 ZIP SHA로 검산했다. 진행 중 원자료는 복사하지 않았다. '
                            +'모델·APK·승인 이미지·키·개인 경로/기기식별 설정은 제외하고 SHA/제외 사유를 남겼다. '
                            +'J는 미판정이고 AP는 HAL 보고값이며 표면온도는 미검증이다.\n\n'
                            +'[ZIP 목록·SHA](BLOCK_BUNDLES.json) · [전체 행](attempts_all.csv) · [소스 SHA](SOURCE_CATALOGS.json)\n',encoding='utf-8')
                        newpaths.append(folder)
            if (ROOT/folder/'BLOCK_BUNDLES.json').exists():groups.append({'label':label,'path':folder.as_posix(),'bundles':load_json(ROOT/folder/'BLOCK_BUNDLES.json')})
    t=utc();stamp=t.astimezone(dt.timezone(dt.timedelta(hours=9))).strftime('%Y-%m-%d %H:%M:%S KST')
    sup=seen['SUP12'];matched=seen.get('REBASE6',{'APP':0,'normal':0});grand=state['project_consumed']+sup['APP']+matched['APP']
    cap=103 if 'REBASE6' in seen else 97
    rejected=state['original_C9_prestart_rejected']+sum(x['rejected']+x['host_failed'] for name,x in seen.items() if name.startswith('C') and name[1:].isdigit())
    active_groups=[name for name,x in seen.items() if x['run_root_started'] and x['worker_lock_present'] and not x['ended']]
    active_text='진행 중: '+', '.join(name+' ('+seen[name].get('pending_prescription','회수')+')' for name in active_groups) if active_groups else '기기 실행 원장 없음; 후속 큐·종료 영수증 확인'
    data={'updated_UTC':t.isoformat(),'updated_KST':stamp,'original_confirm':state,'separate_followon':seen,
        'original85_cap':85,'supplement12_cap':12,'matched_rebaseline_cap':6 if 'REBASE6' in seen else 0,
        'combined_ceiling':cap,'combined_consumed':grand,
        'original_confirm_rejections_total':rejected,
        'active_measurement_groups':active_groups,
        'energy_J':None,'surface_temperature_verified':False,'experiment_ready':False,'published_closed_groups':groups,
        'publisher_device_commands':0,'publication_is_not_measurement_completion':True}
    (ROOT/LIVE/'LIVE_PROGRESS.json').write_bytes(encode(data))
    lines=['# A24 실측 진행 현황','', '**마지막 갱신: '+stamp+'**','',
        '**현재 전체 상태: '+active_text+'**','',
        '- 원래 독립 확인: **'+str(state['normal_confirm_total'])+'/40 정상 완료**, 시작 전 실패·거절 '+str(rejected)+'회 보존. 현재 단계 `'+state['phase']+'`. 실패·미완료는 아래 원장과 각 묶음 상태를 함께 확인한다.',
        '- 기존85회: '+str(state['project_consumed'])+'회 소비(진행·거절 포함). 별도 실패 보완12: '+str(sup['normal'])+'회 정상 완료 / '+str(sup['APP'])+'회 APP 시도. 완료율과 예산 소비율은 다르다.',
        '- 시작온도 대응의 별도 같은 비교군6: '+str(matched['normal'])+'회 정상 / '+str(matched['APP'])+'회 APP. 합산 '+str(grand)+'회 소비 / 제한적 회계 상한'+str(cap)+'회이며, 추가6은 사용자 자율처리 지시를 구체화한 범위다.',
        '- 원확인, 관측후 개정혼합4, 과거실패 새ID 보완12는 서로 합산해 독립 성공 횟수를 늘리지 않는다.',
        '- J 미판정 / AP는 HAL 보고값·표면온도 미검증 / experiment_ready=false. 미완료를 절감으로 해석하지 않는다.',
        '', '## 최신 원자료 ZIP·CSV·버전/SHA','',
        '- [개정혼합4: 2정상·1시작거절·1미실행 시점의 원자료](../../results/a24_measurement_share_20261016/stable_reference_extra4_01/README.md)',
        '- [C9 시작거절 원자료·실패 포함 전체 원장](../../results/a24_measurement_share_20261016/confirmation_visit_09/README.md)',
        '- [이전 C8 원자료·그림·원장](../../results/a24_measurement_share_20261015/confirmation_visit_08/README.md)']
    for group in groups:lines.append('- ['+group['label']+' 원자료 ZIP·CSV·소스 SHA](../../../'+group['path']+'/README.md)')
    lines += ['', '## 계획·재개·해석','', '- [실측 원장과 중지·재개 방법](MEASUREMENT_RUNBOOK.md)',
        '- [실패 보완12의 고정 범위·새 ID·예산·검증](failed_supplement12_20261016/README.md)',
        '- [시작온도 대응의 같은 비교군6: 별도 개발 반복](matched_rebaseline6_20261016/README.md)',
        '- [기계 판독용 현재 상태](LIVE_PROGRESS.json)','',
        '종료한 비교 묶음은 닫힘 증거와 파일 SHA를 확인해 공개한다. 실행 중 원물은 복사하지 않는다. '
        '외부 확인은 이 파일의 마지막 갱신 시각과 원격 커밋 시각을 함께 본다. '
        '네트워크·인증·충돌이 발생하면 이를 우회하거나 다른 작업을 수정하지 않고 공개 업로드를 멈춘다.\n']
    (ROOT/LIVE/'LIVE_PROGRESS.md').write_text('\n'.join(lines),encoding='utf-8')
    return newpaths,data


def publish():
    if git('branch','--show-current')!=BRANCH:raise RuntimeError('unexpected publishing branch')
    if git('diff','--cached','--name-only'):raise RuntimeError('foreign staged changes; preserve and hold publisher')
    newpaths,data=refresh()
    paths=[str(LIVE/'LIVE_PROGRESS.md'),str(LIVE/'LIVE_PROGRESS.json'),*[str(p) for p in newpaths]]
    for path in paths:git('add','-f','--',path)
    if not git('diff','--cached','--name-only'):return
    git('-c','core.whitespace=cr-at-eol','diff','--cached','--check')
    git('commit','-m','Publish closed A24 blocks and current measurement progress')
    head=git('rev-parse','HEAD');git('push','origin','HEAD:refs/heads/'+BRANCH)
    remote=git('ls-remote','origin','refs/heads/'+BRANCH).split()[0]
    if remote!=head:raise RuntimeError('actual remote HEAD differs; preserve and hold')
    receipt={'published_UTC':utc().isoformat(),'HEAD':head,'actual_remote_HEAD':remote,
        'new_closed_group_paths':[p.as_posix() for p in newpaths],'publisher_device_commands':0}
    (META/('PUSH_'+head+'.json')).write_bytes(encode(receipt))
    print(json.dumps(receipt),flush=True)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--push',action='store_true');p.add_argument('--watch',action='store_true')
    a=p.parse_args()
    if not a.watch:
        if a.push:publish()
        else:
            newpaths,data=refresh();print(json.dumps({'status':'PC_PUBLICATION_PREPARED_NO_GIT_PUSH','new_groups':[p.as_posix() for p in newpaths]}))
        return
    META.mkdir(parents=True,exist_ok=True);lock=META/'WATCH_OWNER.json'
    with lock.open('x',encoding='utf-8') as f:json.dump({'started_UTC':utc().isoformat(),'push':a.push},f)
    last=0;signature=None
    try:
        while not (META/'STOP_PUBLISHER.json').exists():
            spec=specifications();current=publication_signature(spec)
            if time.time()-last>=3600 or current!=signature:
                if a.push:publish()
                else:refresh()
                signature=current;last=time.time()
            pointer=META.parent/'LIVE_BINDING.json'
            if pointer.exists():
                b=load_json(pointer);active=load_json(ROOT/b['active_original_meta']/'job.json')
                matched_done=all((Path(load_json(ROOT/x['job'])['run_root'])/'WINDOW_STOPPED.json').exists()
                    for x in b.get('additional_matched_visits',[]))
                if (ROOT/b['queue_meta']/'QUEUE_STOPPED.json').exists() and (Path(active['run_root'])/'WINDOW_STOPPED.json').exists() and matched_done:break
            time.sleep(30)
    except Exception as error:
        (META/'WATCH_STOPPED.json').write_bytes(encode({'status':'PUBLICATION_HELD','reason':str(error),'UTC':utc().isoformat(),
            'device_measurements_interrupted':False}));raise


if __name__=='__main__':main()
