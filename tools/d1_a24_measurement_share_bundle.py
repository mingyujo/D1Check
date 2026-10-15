"""Publish immutable closed A24 evidence grouped by registered block; never calls ADB.

Active visits are read only at a fixed snapshot: only closed per-session raw is
copied; active sessions get status metadata. Legacy failed/rejected attempts and
supplemental same-run recovery remain distinct from normal completion.
"""
import argparse
import collections
import copy
import csv
import datetime
import hashlib
import io
import json
from pathlib import Path
import re
import time
import zipfile


def digest(b):return hashlib.sha256(b).hexdigest()
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def encode(x):return (json.dumps(x,ensure_ascii=False,indent=2)+'\n').encode('utf-8')
PRIVATE=re.compile(rb'(?:[A-Za-z]:[\\/]+Users[\\/]|(?-i:\bR[0-9]{2}[A-Z0-9]{8}\b)|\b172\.(?:1[6-9]|2[0-9]|3[01])\.\d+\.\d+|\b192\.168\.\d+\.\d+|PRIVATE KEY|ghp_[A-Za-z0-9]{20}|\badb-(?-i:[A-Z0-9]{8,})-)',re.I)
PRIVATE_NAMES={'session_manifest.json','identity.json','transport_manifest.json','device_registration.json','config.json','authorization.json'}


def csv_bytes(rows):
    s=io.StringIO(newline='');keys=list(dict.fromkeys(k for row in rows for k in row))
    w=csv.DictWriter(s,fieldnames=keys);w.writeheader();w.writerows(rows)
    return s.getvalue().encode('utf-8-sig')


def write_zip(path,members):
    if path.exists():raise FileExistsError('write-once bundle')
    if len(members)!=len(set(members)):raise ValueError('duplicate archive member')
    for name in members:
        if name.startswith('/') or '..' in Path(name).parts or '\\' in name:raise ValueError('unsafe member path')
        if PRIVATE.search(members[name]):raise ValueError('private bytes in public member: '+name)
    manifest=[{'path':name,'bytes':len(b),'sha256':digest(b)} for name,b in sorted(members.items())]
    with zipfile.ZipFile(path,'x',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for name,b in sorted(members.items()):z.writestr(name,b)
        z.writestr('FILE_SHA256.json',encode({'members':manifest,'raw_members_modified':False}))
    with zipfile.ZipFile(path) as z:
        if set(z.namelist())!={*members,'FILE_SHA256.json'}:raise ValueError('archive membership differs')
        for x in manifest:
            if digest(z.read(x['path']))!=x['sha256']:raise ValueError('archive byte verification failed')
    return {'filename':path.name,'bytes':path.stat().st_size,'sha256':digest(path.read_bytes()),'members':len(manifest)}


def completed(raw):
    p=raw/'requests.json'
    if not p.exists():return 0
    x=read(p)
    return sum(r.get('terminal_status') in {'COMPLETED','COMPLETED_DRAIN'} for r in x)


def public_manifest(m):
    keys=['session_id','plan_id','plan_sha256','stage','block','recipe','arm','policy_id','order','route','concurrency','wait_ms',
          'cpu_threads','sensor_period_ms','source_commit','source_manifest_sha256','apk_sha256','input_seed','bank_sha256',
          'warmup_input','requests','AP_window_s','energy_windows_s','service_cutoff_ns','sensor_end_ns','resident_mode','runtime_scope']
    out={k:copy.deepcopy(m[k]) for k in keys if k in m}
    out['models']={k:{name:copy.deepcopy(spec[name]) for name in ['model','runtime','execution'] if name in spec}
                   for k,spec in m.get('models',{}).items()}
    out['derived_public_projection_not_original_manifest']=True
    if PRIVATE.search(encode(out)):raise ValueError('private field in manifest projection')
    return out


def collect_raw(raw,prefix,members,excluded):
    if not raw.exists():return
    for p in sorted(raw.rglob('*')):
        if not p.is_file():continue
        rel=p.relative_to(raw).as_posix();name=prefix+'/'+rel;b=p.read_bytes()
        reason=None
        if p.name in PRIVATE_NAMES or 'logcat' in p.name.lower():reason='PRIVATE_IDENTITY_MANIFEST_OR_UNFILTERED_LOG'
        elif p.suffix.lower() not in {'.json','.jsonl','.csv','.tsv','.txt'}:reason='BINARY_MODEL_INPUT_OR_UNAPPROVED_ARTIFACT'
        elif PRIVATE.search(b):reason='PRIVATE_PATH_OR_DEVICE_ID_IN_ORIGINAL_BYTES'
        if reason:excluded.append({'path':name,'bytes':len(b),'sha256':digest(b),'reason':reason})
        else:members[name]=b


def collect_preAPP_sidecars(root,sid,members,excluded):
    """Closed-session host cooling reads stay outside the app observation window."""
    for folder in ['pre_app_cooldown_v2','pre_app_cooldown']:
        for suffix in ['.jsonl','.ready.json']:
            p=root/folder/(sid+suffix)
            if not p.is_file():continue
            name='host_preAPP/'+sid+'/'+folder+'/'+p.name;b=p.read_bytes()
            if PRIVATE.search(b):excluded.append({'path':name,'bytes':len(b),'sha256':digest(b),'reason':'PRIVATE_PATH_OR_DEVICE_ID_IN_ORIGINAL_BYTES'})
            else:members[name]=b


def unlaunched_preAPP_evidence(root,sid,plan_id,outcome):
    """Retain an unconsumed refusal before the unique later actual execution."""
    if outcome.get('APP_launch_intent') is not False:raise ValueError('duplicate session has prior APP intent')
    raw=root/'raw'/sid;registry=root/'registry'/'a24-laptop-measurement-v1'/plan_id/sid
    for folder in [raw,registry]:
        if not folder.exists():continue
        allowed={'host_hal_partial.jsonl'} if folder==raw else {'host_hal_partial.jsonl','PRESTART_REJECT.json'}
        if any(p.name not in allowed or not p.is_file() for p in folder.iterdir()):raise ValueError('duplicate prior session has execution artifacts')
        sensor=folder/'host_hal_partial.jsonl'
        if sensor.exists() and sensor.stat().st_size:raise ValueError('duplicate prior session has samples')
    refusal=registry/'PRESTART_REJECT.json'
    if not refusal.exists():raise ValueError('duplicate prior session lacks unconsumed refusal receipt')
    receipt=read(refusal)
    if receipt.get('START') is not False or receipt.get('session_run_consumed') is not False:raise ValueError('duplicate prior session consumed a run')
    for name in ['measurement_adb_commands.jsonl','adb_commands.jsonl']:
        log=root/name
        if not log.exists():continue
        for line in log.read_bytes().splitlines():
            args=json.loads(line).get('argv',[])
            if 'am' in args and 'start' in args and sid in args:raise ValueError('duplicate prior session has APP command')
    prefix='unlaunched_preAPP_refusals/'+root.name+'/'+sid
    members={prefix+'/outcome_original.json':(root/(sid+'.outcome.json')).read_bytes(),
             prefix+'/PRESTART_REJECT_original.json':refusal.read_bytes()}
    for name,b in members.items():
        if PRIVATE.search(b):raise ValueError('private preAPP refusal receipt')
    return members


def closed_passive_binding_evidence(root,sid,plan_id):
    """Only proven APP0 waits; other closed sessions in that visit stay separate."""
    stop=read(root/'WINDOW_STOPPED.json');proof=read(root/(sid+'.preapp_stop.json'))
    if (proof.get('APP')!=0 or proof.get('binding_created') is not True
            or proof.get('reason')!='USER_STOP_AFTER_CURRENT' or stop.get('reason')!='PRE_APP_COOLDOWN_STOP'
            or not (root/'STOP_AFTER_CURRENT.json').is_file()):raise ValueError('unproved passive binding')
    if any(p.exists() for p in [root/'raw'/sid,root/'registry'/'a24-laptop-measurement-v1'/plan_id/sid,
                               root/(sid+'.outcome.json')]):raise ValueError('passive binding has execution artifacts')
    launches=[]
    for name in ['adb_commands.jsonl','measurement_adb_commands.jsonl']:
        p=root/name
        if p.exists():
            for line in p.read_bytes().splitlines():
                args=json.loads(line).get('argv',[])
                if 'am' in args and 'start' in args and 'session_id' in args:launches.append(args[args.index('session_id')+1])
    outcomes=stop.get('outcomes',[])
    if (sid in launches or stop.get('new_APP_intents')!=len(launches) or len(launches)!=len(outcomes)
            or sorted(launches)!=sorted(x.get('session_id','') for x in outcomes)
            or any(x.get('APP_launch_intent') is not True or x.get('session_id')==sid for x in outcomes)):
        raise ValueError('passive binding APP delivery/outcomes differ')
    prefix='closed_passive_bindings/'+root.name+'/'+sid
    members={prefix+'/'+p.name:p.read_bytes() for p in [root/'WINDOW_STOPPED.json',root/'STOP_AFTER_CURRENT.json',root/(sid+'.preapp_stop.json')]}
    sidecars={};excluded=[];collect_preAPP_sidecars(root,sid,sidecars,excluded)
    members.update({prefix+'/'+name:b for name,b in sidecars.items()})
    if excluded:members[prefix+'/EXCLUDED_PRIVATE.json']=encode(excluded)
    return members


def snapshot(config,out,private_out):
    if out.exists() or private_out.exists():raise FileExistsError('new public/private output required')
    cutoff_epoch=time.time_ns()
    cutoff=datetime.datetime.fromtimestamp(cutoff_epoch/1e9,datetime.timezone.utc).isoformat()
    plans={};records=[];payload={};seen=set();launches=[];source_catalogs={}
    for folder in config['source_catalog_directories']:
        for p in Path(folder).rglob('*.json'):
            if 'source' not in p.name.lower():continue
            try:x=read(p)
            except (ValueError,UnicodeError):continue
            if isinstance(x,dict) and isinstance(x.get('files'),list) and x.get('schema')=='a24-preparation-source-manifest-v1':
                source_catalogs[digest(p.read_bytes())]=(p,x)
    for family in config['families']:
        job=read(family['job']);plan=read(job['plan']);plans[family['id']]=(job,plan)
        roots=[Path(p) for p in family['roots']]
        outcomes={};root_of={};outcome_shas={};app_records=collections.defaultdict(list)
        preAPP=collections.defaultdict(dict);preAPP_counts=collections.Counter();app_roots={}
        for root in roots:
            # Read complete lines from a fixed prefix, never modify active logs.
            for name in ['measurement_adb_commands.jsonl','adb_commands.jsonl']:
                log=root/name
                if not log.exists():continue
                b=log.read_bytes();lines=b[:b.rfind(b'\n')+1].splitlines()
                for line in lines:
                    x=json.loads(line);args=x.get('argv',[])
                    if x.get('start_wall_ns',0)>cutoff_epoch:continue
                    if 'am' in args and 'start' in args and 'session_id' in args:
                        sid=args[args.index('session_id')+1]
                        rec={'session_id':sid,'start_wall_ns':x.get('start_wall_ns'),'end_wall_ns':x.get('end_wall_ns'),
                             'exit':x.get('exit'),'original_record_sha256':digest(line),'timeout':bool(x.get('timeout_seconds'))}
                        app_records[sid].append(rec);launches.append({'family':family['id'],**rec});app_roots[sid]=root
            for p in root.glob('*.outcome.json'):
                if p.stat().st_mtime_ns>cutoff_epoch:continue
                x=read(p);sid=x['session_id']
                if sid in outcomes:
                    previous=unlaunched_preAPP_evidence(root_of[sid],sid,plan['plan_id'],outcomes[sid])
                    preAPP[sid].update(previous);preAPP_counts[sid]+=1
                outcomes[sid]=x;root_of[sid]=root;outcome_shas[sid]=digest(p.read_bytes())
        for row in plan['sessions']:
            sid=row['session_id']
            if sid in seen:raise ValueError('duplicate planned session across families')
            seen.add(sid);outcome=outcomes.get(sid);root=root_of.get(sid)
            if sid in app_roots and app_roots[sid]!=root:
                if outcome:
                    preAPP[sid].update(unlaunched_preAPP_evidence(root,sid,plan['plan_id'],outcome));preAPP_counts[sid]+=1
                outcome=None;root=app_roots[sid]
            if root is None:
                candidates=[r for r in roots if (r/'bindings'/sid).exists()]
                for candidate in candidates:
                    if (candidate/(sid+'.preapp_stop.json')).exists():
                        if app_records[sid]:raise ValueError('passive binding has an APP record')
                        preAPP[sid].update(closed_passive_binding_evidence(candidate,sid,plan['plan_id']))
                    elif len(candidates)>1:raise ValueError('ambiguous unstarted binding')
                root=candidates[-1] if candidates else roots[-1]
            raw=root/'raw'/sid;supp=root/'read_only_recovery'/sid/'recovered_app'
            status=outcome['status'] if outcome else 'IN_PROGRESS_AT_SNAPSHOT' if app_records.get(sid) else 'NOT_ATTEMPTED_RETIRED_PLAN' if family.get('retired') else 'NOT_ATTEMPTED_AT_SNAPSHOT'
            if outcome and status=='COMPLETE_TRACE_RECOVERED':
                if not (raw/'journal_closed.json').exists():raise ValueError('normal completed outcome without closure')
                closure=read(raw/'journal_closed.json')
                if closure.get('status')!='SYNCED_AND_CLOSED':raise ValueError('normal closure not synced')
            # Do not touch raw/manifest of an active session.
            mpath=next((p for p in [raw/'session_manifest.json',root/'bindings'/sid/'session_manifest.json',
                                  Path(job['prepared_manifests'])/(sid+'.json')] if p.exists()),None) if outcome else None
            m=read(mpath) if mpath else {}
            record={k:row.get(k) for k in ['session_id','stage','block','recipe','arm','request_count','plan_ordinal','bank_sha256','input_seed']}
            record.update(family=family['id'],status=status,reason=(outcome or {}).get('reason',''),
                recorded_APP_commands=len(app_records[sid]),same_ID_APP_replays=max(0,len(app_records[sid])-1),
                MAIN_START_recorded=bool(list((root/'registry').glob('**/'+sid+'/START.json'))) if outcome else None,
                raw_requests_completed=completed(raw) if outcome else None,
                supplemental_same_run_completed=completed(supp) if outcome else None,
                normal_comparison_eligible=status=='COMPLETE_TRACE_RECOVERED',
                prior_unconsumed_preAPP_refusals=preAPP_counts[sid],
                source_catalog_sha256=m.get('source_manifest_sha256'),source_commit_declared=m.get('source_commit'),
                APK_sha256=m.get('apk_sha256'),original_manifest_sha256=digest(mpath.read_bytes()) if mpath else None,
                outcome_sha256=outcome_shas.get(sid) if outcome else None)
            if PRIVATE.search(encode(record)):
                record['reason']='PRIVATE_DIAGNOSTIC_DETAIL_RETAINED_LOCALLY'
            records.append(record)
            members=dict(preAPP[sid]);excluded=[]
            if outcome:
                original_outcome=(root/(sid+'.outcome.json')).read_bytes()
                if not PRIVATE.search(original_outcome):members['host_outcomes/'+sid+'.json']=original_outcome
                else:excluded.append({'path':'host_outcomes/'+sid+'.json','sha256':digest(original_outcome),'bytes':len(original_outcome),'reason':'PRIVATE_PATH_OR_DEVICE_ID_IN_ORIGINAL_BYTES'})
                collect_raw(raw,'raw/'+sid,members,excluded)
                collect_raw(supp,'supplemental_same_run_raw/'+sid,members,excluded)
                collect_preAPP_sidecars(root,sid,members,excluded)
                if m:members['public_manifests/'+sid+'.json']=encode(public_manifest(m))
                for p in (root/'registry').glob('**/'+sid+'/*.json'):
                    if p.name not in {'START.json','COMPLETE.json','FAIL.json','PRESTART_REJECT.json','CANCEL.json'}:continue
                    b=p.read_bytes()
                    if not PRIVATE.search(b):members['host_receipts/'+sid+'/'+p.name]=b
                for q in ['block_reference.json','references/'+str(row.get('gate_block_id',''))+'.json']:
                    p=root/q
                    if p.is_file() and not PRIVATE.search(p.read_bytes()):members['references/'+p.name]=p.read_bytes()
            payload[sid]=(members,excluded)
    out.mkdir(parents=True);(out/'blocks').mkdir();(out/'sources').mkdir();private_out.mkdir(parents=True)
    source_index=[]
    for key in sorted({r['source_catalog_sha256'] for r in records if r['source_catalog_sha256']}):
        if key not in source_catalogs:
            source_index.append({'sha256':key,'status':'CATALOG_NOT_FOUND_LOCALLY'});continue
        p,catalog=source_catalogs[key];b=p.read_bytes()
        if PRIVATE.search(b):raise ValueError('private source catalog')
        (out/'sources'/(key+'.json')).write_bytes(b)
        source_index.append({'sha256':key,'source_base_commit':catalog.get('source_base_commit'),
                             'files':len(catalog['files']),'status':'EXACT_CATALOG_INCLUDED'})
    groups=collections.defaultdict(list)
    for r in records:groups[(r['family'],r['stage'],r['block'])].append(r)
    bundles=[]
    def bundle(key,rows,suffix=''):
        family,stage,block=key;name='_'.join([family,stage,block]+([suffix] if suffix else []))+'.zip';members={};excluded=[]
        if not re.fullmatch(r'[A-Za-z0-9_.-]+',name):raise ValueError('unsafe bundle filename')
        for r in rows:
            part,skip=payload[r['session_id']];members.update(part);excluded.extend(skip)
        if not any(r['status'] not in {'NOT_ATTEMPTED_AT_SNAPSHOT','NOT_ATTEMPTED_RETIRED_PLAN'} for r in rows):return
        tally=dict(collections.Counter(r['status'] for r in rows));n=sum(r['normal_comparison_eligible'] for r in rows)
        info={'snapshot_UTC':cutoff,'family':family,'stage':stage,'block':block,'planned_arms':len(rows),'normal_completed':n,
              'all_arms_normally_completed':n==len(rows),'status_counts':tally,'replays_recorded':sum(r['same_ID_APP_replays'] for r in rows),
              'failed_or_partial_raw_not_promoted':True,'energy_J_validated':False,'surface_temperature_verified':False,
              'source_catalogs':sorted({r['source_catalog_sha256'] for r in rows if r['source_catalog_sha256']}),
              'APK_versions':sorted({r['APK_sha256'] for r in rows if r['APK_sha256']}),
              'changes_notes':config['changes_notes'].get(family,[])}
        members['BLOCK_STATUS.json']=encode(info);members['attempts.csv']=csv_bytes(rows);members['VERSIONS.json']=encode(rows);members['EXCLUDED_PRIVATE_OR_BINARY.json']=encode(excluded)
        members['README.md']=(f'# A24 {family} / {stage} / {block}\n\n'+
            f'공개 스냅샷 {cutoff}. 정상 완료 {n}/{len(rows)}군. 실패·중지·미시도·진행 중은 BLOCK_STATUS.json과 attempts.csv에 그대로 남겼다.\n\n'+
            'raw/와 supplemental_same_run_raw/는 회수한 원자료의 원래 바이트다. 후자는 실패 원실행의 추가 읽기 전용 회수이며 정상 결과로 승격하지 않았다. public_manifests/는 식별 정보를 제외한 파생 설정이다. 파일별 SHA는 FILE_SHA256.json에 있다.\n\n'+
            '모델·APK·승인 이미지·키·개인 식별 설정과 전체 시스템로그는 포함하지 않는다. 모델/입력/텐서의 SHA와 출처는 public_manifests/ 및 공유폴더 sources/에서 확인한다. 검증된 J·표면온도·정책 채택 결과가 아니다.\n').encode('utf-8')
        meta=write_zip(out/'blocks'/name,members)
        bundles.append({**meta,**{k:info[k] for k in ['family','stage','block','planned_arms','normal_completed','all_arms_normally_completed','status_counts']},'subset_recipe':suffix or None})
    for key,rows in sorted(groups.items()):
        bundle(key,rows)
        if sum(r['normal_comparison_eligible'] for r in rows)<len(rows):
            byrecipe=collections.defaultdict(list)
            for r in rows:byrecipe[r['recipe']].append(r)
            for recipe,rs in byrecipe.items():
                if len(rs)>1 and all(r['normal_comparison_eligible'] for r in rs):bundle(key,rs,recipe)
    (out/'attempts_all.csv').write_bytes(csv_bytes(records));(out/'APP_commands_no_private_ids.csv').write_bytes(csv_bytes(launches))
    (out/'BLOCK_BUNDLES.json').write_bytes(encode(bundles));(out/'SOURCE_CATALOGS.json').write_bytes(encode(source_index))
    summary={'schema':'a24-shared-block-evidence-snapshot-v1','snapshot_UTC':cutoff,'registered_rows':len(records),
             'status_counts':dict(collections.Counter(r['status'] for r in records)),'recorded_APP_command_count':len(launches),
             'same_ID_APP_replays':sum(r['same_ID_APP_replays'] for r in records),'bundles':len(bundles),
             'included_original_members_byte_identical':True,'private_or_binary_exclusions_explicit':True,
             'copied_active_raw':False,'device_commands':0,'physical_J_validated':False,
             'script_sha256':digest(Path(__file__).read_bytes()),'source_catalogs_missing':[x['sha256'] for x in source_index if x['status']!='EXACT_CATALOG_INCLUDED']}
    (out/'SNAPSHOT.json').write_bytes(encode(summary))
    # A private input manifest for later audit, never staged into Git.
    (private_out/'config.json').write_bytes(encode(config));(private_out/'records.json').write_bytes(encode(records))
    print(json.dumps(summary,ensure_ascii=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('config',type=Path);p.add_argument('output',type=Path);p.add_argument('private_audit',type=Path)
    a=p.parse_args();snapshot(read(a.config),a.output,a.private_audit)
