"""ENERGY-THERMAL-COLLECTION-PREP-02. prepare/check are PC-only; run requires approval.
New namespace; no old plan can be resumed. Explicit fixed work, not a policy evaluation.
"""
from __future__ import annotations
import argparse
import copy
import json
import math
import statistics
import uuid
from pathlib import Path
from tools import d1_arrival_plan as p
from tools import d1_arrival_timing_calibration as cal
from tools.d1_energy_thermal import require, integrate

PROTOCOL='energy-thermal-collection-v2'
EXPERIMENT='ENERGY-THERMAL-COLLECT-02'
KEYS=('classification_CPU','classification_GPU','detection_CPU','detection_GPU')
PAIRS={'CC_DG':('classification_CPU','detection_GPU'),'CG_DC':('classification_GPU','detection_CPU')}
CONDITIONS=[('CC_DG','serial'),('CC_DG','parallel'),('CG_DC','serial'),('CG_DC','parallel')]
BUDGET=dict(sessions=8,development=4,confirmation=4,work_requests=6960,eligibility_requests=16,
    diagnostic_requests=6976,warmup=64,explicit_inference=7040,runtime_creations=32,
    apk_transfers=1,installs=1,retry=0,replacement=0,additional=0,
    total_seconds=13200,installation_seconds=600,freeze_seconds=600,session_seconds=1500,
    stage_gate_seconds=120,host_poll_seconds=1220,recovery_seconds=60,cleanup_seconds=45,
    baseline_seconds=120,common_work_seconds=480,cooling_seconds=180)
HOST_FILES=['tools/d1_energy_collection.py','tools/d1_energy_collection_device.py',
    'tools/d1_energy_screen.py',
    'tools/d1_adb_observed_client.py','tools/d1_recorded_process.py','tools/d1_collection_recovery.py',
    'tools/d1_logger_v4.py','tools/d1_probe_compare.py','tools/d1_energy_thermal.py']

def identity():
    return cal.code_identity() | {n:p.digest(cal.ROOT/n) for n in HOST_FILES}

def layout():
    # Serial before unverified long pair in each stage. Reverse pair order at confirmation.
    return [(phase,*c) for phase in ('development','confirmation') for c in
            (CONDITIONS if phase=='development' else CONDITIONS[2:]+CONDITIONS[:2])]

def prepare(source, build, references, output):
    from tools import d1_apk_identity as apk
    source=Path(source);build=Path(build);output=Path(output)
    require(not output.exists(),'new output only')
    old=p.read(source);receipt=p.read(build)
    require(cal.apk_sources(receipt['source_code'])==cal.apk_sources(identity()),'APK source mismatch')
    require(p.digest(receipt['apk_path'])==receipt['apk_sha256'],'APK changed')
    template=p.read(source.parent/old['entries'][0]['manifest'])
    refs={}
    for f in sorted(Path(references).rglob('*.result.json')):
        r=p.read(f);k=r['task_id']+'_'+r['requested_backend']
        if k not in refs and r['image_sha256']==template['images'][0]['sha256']:
            refs[k]=dict(path=str(f.resolve()),sha256=p.digest(f))
    require(set(refs)==set(KEYS),'four same-input development output references required')
    output.mkdir(parents=True);(output/'manifests').mkdir()
    candidate=apk.inspect(receipt['apk_path'],old['apk_preflight']['toolchain'])
    require(candidate['signer_sha256']==old['apk_preflight']['candidate']['signer_sha256'],'project signer mismatch')
    plan=dict(protocol=PROTOCOL,experiment_id=EXPERIMENT,status='PREPARED_NOT_APPROVED',experiment_ready=False,
        budget=BUDGET,seed=2026092502,source_code=identity(),build_receipt=str(build.resolve()),build_receipt_sha256=p.digest(build),
        apk_path=receipt['apk_path'],apk_sha256=receipt['apk_sha256'],
        apk_preflight=dict(old['apk_preflight'],candidate=candidate),device_fingerprint=old['device_fingerprint'],
        device_hardware_serial='R59W802RW5F',source_plan=dict(path=str(source.resolve()),sha256=p.digest(source)),
        output_root=str(output.parent/'energy_collection_run_v2'),registry=str(output.parent/'energy_collection_registry'/EXPERIMENT),
        battery_start_percent=20,battery_min_percent=20,battery_max_temperature_tenths_c=350,require_unplugged=True,
        screen_contract=old['screen_contract'],source_files={k:v for k,v in old['source_files'].items() if k!='collection_estimates.json'},
        references=refs,entries=[],acceptance=dict(power_coverage=.95,max_gap_seconds=2.5,thermal_max_gap_seconds=10,
            thermal_min_coverage=.95,clock_bracket_max_seconds=2,ap_signal_min_c=.3,paired_baseline_ap_tolerance_c=.5,
            classification_score_tolerance=.001,detection_score_tolerance=.001,detection_box_px=2,
            accuracy_margin=None,meaning='record/identity/equivalence eligibility only; no accuracy or optimization PASS'),
        analysis=dict(current_ua_per_raw=1000,unit_status='likely_mA_not_absolute_accuracy_certified',
            thermal_reference='per-session resident baseline AP median; not ambient or safety limit',
            freeze='condition phase mean whole-device power and empirical AP endpoints; development only',
            confirmation='report signed/absolute errors without retuning; no invented tolerance',
            unsupported=['arbitrary stagger','request pacing','all duty','repeated batch cooling prediction','new policy superiority']))
    for i,(phase,pair,mode) in enumerate(layout()):
        sid=str(uuid.uuid5(uuid.NAMESPACE_URL,f'{EXPERIMENT}/{phase}/{pair}/{mode}'))
        m=dict(protocol=PROTOCOL,experiment_id=EXPERIMENT,session_id=sid,phase=phase,pair=pair,mode=mode,
            models=copy.deepcopy(template['models']),images=template['images'],cpu_threads=1,experiment_ready=False,
            apk_sha256=plan['apk_sha256'],device_fingerprint=plan['device_fingerprint'],maximum_duration_ms=1200000,
            baseline_seconds=120,common_work_seconds=480,cooling_seconds=180,
            counts={'classification':678,'detection':192},probe_counts={'classification':1,'detection':1},warmup_count=8,
            memory_contract='android-low-memory-resident-v1',thermal_gate=0)
        for spec in m['models'].values():
            spec['identity']['session_id']=sid;spec['target']['apk_sha256']=plan['apk_sha256']
        f=output/'manifests'/f'{sid}.json';cal.write_new(f,m)
        plan['entries'].append(dict(index=i,phase=phase,pair=pair,mode=mode,session_id=sid,
            manifest='manifests/'+f.name,manifest_sha256=p.digest(f)))
    file=output/'collection_plan.json';cal.write_new(file,plan)
    script=f'''param([ValidateSet("Check","Run")][string]$Action="Check",[switch]$Approved,[string]$Serial)
$ErrorActionPreference="Stop"
Set-Location '{cal.ROOT.as_posix()}'
$plan = Join-Path $PSScriptRoot 'collection_plan.json'
if ($Action -eq 'Check') {{ python -B -m tools.d1_energy_collection check --plan $plan }}
else {{
  if (!$Approved -or !$Serial) {{ throw 'Explicit new plan approval and serial required' }}
  python -B -m tools.d1_energy_collection run --plan $plan --expected-sha {p.digest(file)} --approved --serial $Serial --adb 'C:/Users/LG/AppData/Local/Android/Sdk/platform-tools/adb.exe'
}}
if ($LASTEXITCODE -ne 0) {{ throw 'Failed; no automatic retry/resume' }}
'''
    (output/'RUN_AFTER_APPROVAL.ps1').write_text(script,encoding='utf-8-sig')
    return check(file)

def check(file):
    from tools import d1_apk_identity as apk
    file=Path(file);plan=p.read(file)
    require(plan['protocol']==PROTOCOL and plan['experiment_id']==EXPERIMENT,'namespace')
    require(plan['budget']==BUDGET and not plan['experiment_ready'],'budget/readiness')
    require(plan['source_code']==identity(),'source changed; regenerate a NEW plan')
    require(p.digest(plan['build_receipt'])==plan['build_receipt_sha256'],'build receipt')
    require(cal.apk_sources(p.read(plan['build_receipt'])['source_code'])==cal.apk_sources(identity()),'APK sources')
    require(p.digest(plan['apk_path'])==plan['apk_sha256'],'APK hash')
    for k,v in plan['apk_preflight']['tool_sha256'].items():require(p.digest(plan['apk_preflight']['toolchain'][k])==v,'tool identity')
    require(apk.inspect(plan['apk_path'],plan['apk_preflight']['toolchain'])==plan['apk_preflight']['candidate'],'signed candidate')
    for v in list(plan['source_files'].values())+list(plan['references'].values())+[plan['source_plan']]:
        require(p.digest(v['path'])==v['sha256'],'input/reference changed')
    require(len(plan['entries'])==8 and len({e['session_id'] for e in plan['entries']})==8,'session budget')
    for i,e in enumerate(plan['entries']):
        m=p.read(file.parent/e['manifest']);require(p.digest(file.parent/e['manifest'])==e['manifest_sha256'],'manifest hash')
        require((e['phase'],e['pair'],e['mode'])==layout()[i] and e['index']==i,'order')
        require(all(m[k]==e[k] for k in ['phase','pair','mode','session_id']),'entry binding')
        require(m['counts']=={'classification':678,'detection':192} and m['warmup_count']==8 and
            m['probe_counts']=={'classification':1,'detection':1},'call cap')
        require(m['apk_sha256']==plan['apk_sha256'] and m['device_fingerprint']==plan['device_fingerprint'] and
            m['maximum_duration_ms']==1200000 and not m['experiment_ready'],'APK/device/timeout')
        require((m['baseline_seconds'],m['common_work_seconds'],m['cooling_seconds'],m['cpu_threads'])==(120,480,180,1),'time/thread contract')
        require(set(m['models'])==set(KEYS) and len(m['images'])==1,'resident/input')
        for k,s in m['models'].items():
            require(s['identity']['session_id']==e['session_id'] and s['target']['apk_sha256']==plan['apk_sha256'] and
                s['runtime']['cpu_threads']==1 and k==s['model']['task_id']+'_'+s['execution']['backend'],'model binding')
    require(not Path(plan['registry']).exists() and not Path(plan['output_root']).exists(),'consumed/existing output: no resume')
    return dict(status='PC_READY_DEVICE_UNVERIFIED',plan_sha256=p.digest(file),budget=BUDGET,device_commands=0)

def progress_prefix(raw):
    """Only newline-terminated, contiguous JSON records are confirmed."""
    records=[];lines=raw.splitlines(keepends=True)
    for index,line in enumerate(lines):
        if not line.endswith(b'\n'):return records,len(lines)-index
        try:records.append(json.loads(line))
        except (ValueError,UnicodeError):return records,len(lines)-index
    return records,0

def progress_consumption(raw,launched):
    records,partial_lines=progress_prefix(raw)
    limits={'runtime':4,'warmup':8,'eligibility':2,'load':870};out={}
    for name,cap in limits.items():
        if name=='runtime':starts=[r for r in records if r.get('kind')=='runtime_start'];ends=[r for r in records if r.get('kind')=='runtime_return']
        elif name=='warmup':starts=[r for r in records if r.get('kind')=='warmup_start'];ends=[r for r in records if r.get('kind')=='warmup_return']
        else:
            phase='eligibility_probe' if name=='eligibility' else 'load'
            starts=[r for r in records if r.get('kind')=='request_start' and r.get('phase')==phase]
            ends=[r for r in records if r.get('kind')=='lane_available' and r.get('phase')==phase]
        key=lambda r:r.get('id',r.get('key'))
        lower=len({key(r) for r in starts}|{key(r) for r in ends});returned=len({key(r) for r in ends})
        require(lower<=cap and returned<=cap,'progress exceeds budget')
        out[name]=dict(confirmed_started_at_least=lower,confirmed_returned=returned,actual_started_upper=cap if launched else 0,
            missing_completion_is_not_success=True)
    return dict(records=len(records),partial_lines=partial_lines,counts=out)

def quality(reference,candidate):
    from tools.d1_probe_compare import compare_decoded
    for k in ('task_id','model_sha256','image_sha256','input_tensor_sha256','requested_backend','adapter_contract'):
        require(candidate[k]==reference[k],'output identity '+k)
    a,b=reference['results'],candidate['results']
    if reference['task_id']=='detection':require(compare_decoded(a,b)['passed'],'detection equivalence')
    else:
        require(len(a)==len(b)==5,'classification top5')
        for x,y in zip(a,b):
            require(x['label']==y['label'] and x['class_index']==y['class_index'] and math.isfinite(y['score']) and
                abs(x['score']-y['score'])<=.001,'classification equivalence')
    expected='CPU' if candidate['requested_backend']=='CPU' else 'unverified_requires_host_delegate_log'
    require(candidate['actual_backend']==expected,'raw backend')

def validate_rows(rows, pair, mode, counts):
    require(len(rows)==sum(counts),'full denominator required')
    fields=('scheduled_arrival_ns','dispatch_ns','execution_start_ns','invocation_start_ns','invocation_end_ns',
            'output_ready_ns','persist_complete_ns','worker_release_ns','lane_available_ns')
    require(len({r['id'] for r in rows})==len(rows),'duplicate requests')
    for r in rows:
        ts=[r[k] for k in fields];require(all(type(t)==int and t>=0 for t in ts) and ts==sorted(ts),'clock/boundary order')
        require(r['terminal_status']=='succeeded','failed/unfinished')
    for key,n in zip(PAIRS[pair],counts):
        rr=sorted((r for r in rows if r['key']==key),key=lambda r:r['dispatch_ns'])
        require(len(rr)==n,'task/backend denominator')
        require(all(a['lane_available_ns']<=b['dispatch_ns'] for a,b in zip(rr,rr[1:])),'early lane reuse')
    spans=sorted([(r['dispatch_ns'],1) for r in rows]+[(r['lane_available_ns'],-1) for r in rows])
    busy=0
    for _,delta in spans:
        busy+=delta;require(0<=busy<=(1 if mode=='serial' else 2),'concurrency')
    aa=[r for r in rows if r['key']==PAIRS[pair][0]];bb=[r for r in rows if r['key']==PAIRS[pair][1]]
    overlap=sum(max(0,min(a['invocation_end_ns'],b['invocation_end_ns'])-max(a['invocation_start_ns'],b['invocation_start_ns'])) for a in aa for b in bb)
    if mode=='parallel':require(overlap>0,'no host API overlap observed; parallel unsupported')
    return dict(requests=len(rows),host_api_overlap_ns=overlap,kernel_overlap_verified=False)

def state_intervals(rows,start,end):
    """Whole-device occupancy partition; includes actual one-lane tails and idle."""
    edges=sorted({start,end}|{r[k] for r in rows for k in ('dispatch_ns','lane_available_ns') if start<r[k]<end})
    spans=[]
    for a,b in zip(edges,edges[1:]):
        keys=sorted(r['key'] for r in rows if r['dispatch_ns']<=a<r['lane_available_ns'])
        spans.append(dict(start_ns=a,end_ns=b,state='+'.join(keys) or 'resident_idle'))
    return spans

def power_by_state(samples,intervals):
    sums={}
    for span in intervals:
        x=integrate(samples,span['start_ns'],span['end_ns'],1000)
        total=sums.setdefault(span['state'],dict(duration_s=0.,covered_s=0.,covered_energy_j=0.))
        for k in total:total[k]+=x[k] or 0
    for total in sums.values():
        total['mean_power_w']=total['covered_energy_j']/total['covered_s'] if total['covered_s'] else None
        total['complete_energy_j']=total['covered_energy_j'] if abs(total['duration_s']-total['covered_s'])<1e-6 else None
    return sums

def thermal_burden(thermal,start,end,reference,sensor='AP'):
    """Piecewise-linear positive area; no extrapolation or bridging >10s gaps."""
    out=0.;covered=0.
    for a,b in zip(thermal,thermal[1:]):
        if a.get(sensor,'')=='' or b.get(sensor,'')=='' or b['mono_ns']-a['mono_ns']>10e9:continue
        lo,hi=max(start,a['mono_ns']),min(end,b['mono_ns'])
        if hi<=lo:continue
        dt=b['mono_ns']-a['mono_ns'];ta=float(a[sensor])-reference;tb=float(b[sensor])-reference
        x=ta+(tb-ta)*(lo-a['mono_ns'])/dt;y=ta+(tb-ta)*(hi-a['mono_ns'])/dt;seconds=(hi-lo)/1e9
        if x*y<0:area=seconds*max(x,y)**2/(2*abs(y-x))
        else:area=seconds*(max(0,x)+max(0,y))/2
        out+=area;covered+=seconds
    return dict(degree_seconds=out,covered_seconds=covered,reference_c=reference,
        meaning='above own resident baseline; not damage/safety/ambient threshold')

def counter_windows(samples,start,end):
    from tools.d1_energy_thermal import discharge_w
    windows=[(start,end)]+[(a,min(a+120_000_000_000,end)) for a in range(start,end,120_000_000_000)
        if min(a+120_000_000_000,end)-a>=60_000_000_000]
    rows=[]
    for a,b in windows:
        ss=[s for s in samples if a<=s['mono_ns']<=b and s.get('charge_valid')]
        if len(ss)<2:
            rows.append(dict(start_ns=a,end_ns=b,status='counter_missing'));continue
        charge=covered=0.
        for x,y in zip(ss,ss[1:]):
            dt=(y['mono_ns']-x['mono_ns'])/1e9
            if dt<=2.5 and discharge_w(x,1000) is not None and discharge_w(y,1000) is not None:
                charge+=-(x['current_raw']+y['current_raw'])/2*1000*dt/3600;covered+=dt
        delta=ss[0]['charge_counter_raw']-ss[-1]['charge_counter_raw']
        rows.append(dict(start_ns=ss[0]['mono_ns'],end_ns=ss[-1]['mono_ns'],covered_s=covered,counter_decrease_uah=delta,
            distinct_counter_values=len({s['charge_counter_raw'] for s in ss}),integrated_uah_mA_hypothesis=charge,
            ratio_mA=charge/delta if delta>0 else None,ratio_uA=charge/1000/delta if delta>0 else None,
            status='quantized_internal_consistency_not_ground_truth'))
    return rows

def summarize_session(folder,manifest,plan):
    from tools import d1_energy_thermal as energy
    root=Path(folder);m=p.read(manifest)
    require(p.digest(root/'manifest.json')==p.digest(manifest),'output manifest')
    require(p.read(root/'cleanup.json')['status']=='completed' and p.read(root/'summary.json')['status']=='completed','app cleanup/completion')
    rows=p.read(root/'load.requests.json');probe=p.read(root/'eligibility_probe.requests.json')
    validation=validate_rows(rows,m['pair'],m['mode'],[678,192]);validate_rows(probe,m['pair'],m['mode'],[1,1])
    for r in rows+probe:quality(p.read(plan['references'][r['key']]['path']),p.read(root/(r['id']+'.result.json')))
    events=[json.loads(x) for x in (root/'progress.jsonl').read_text(encoding='utf-8').splitlines()]
    require([r['sequence'] for r in events]==list(range(len(events))) and all(r['session_id']==m['session_id'] for r in events),'journal loss/identity')
    require(all(a['mono_ns']<=b['mono_ns'] for a,b in zip(events,events[1:])),'event clock')
    for kind,n in [('runtime_start',4),('runtime_return',4),('warmup_start',8),('warmup_return',8),('request_start',872),('lane_available',872)]:
        require(sum(r['kind']==kind for r in events)==n,'event consumption '+kind)
    samples=[r for r in events if r['kind']=='power_sample']
    require(all(r['plugged']==0 and r['thermal_status']==0 and r['admission_reason']=='admit' and r['interactive'] for r in samples),'environment failure')
    thermal=[json.loads(x) for x in (root.parent/'thermal.jsonl').read_text(encoding='utf-8').splitlines()]
    phases={}
    for phase in ('resident_baseline','load','post_work_wait','resident_cooling'):
        starts=[r['mono_ns'] for r in events if r['phase']==phase and r['kind']=='phase_start']
        ends=[r['mono_ns'] for r in events if r['phase']==phase and r['kind']=='phase_end']
        require(len(starts)==len(ends)==1,'phase boundary')
        start,end=starts[0],ends[0]
        integ=energy.integrate(samples,start,end,1000)
        require(integ['covered_s']>=.95*integ['duration_s'],'power coverage')
        tt=[t for t in thermal if start<=t['mono_ns']<=end]
        ap=[float(t['AP']) for t in tt if t['AP']!='']
        require(len(ap)>=2 and all(t['sampling_uncertainty_ns']<=2e9 for t in tt),'AP/clock coverage')
        require(len(ap)>=.95*len(tt),'AP missing samples')
        require(max([tt[0]['mono_ns']-start,end-tt[-1]['mono_ns']]+[b['mono_ns']-a['mono_ns'] for a,b in zip(tt,tt[1:])])<=10e9,'thermal gaps')
        phases[phase]=dict(start_ns=start,end_ns=end,energy=integ,ap_start_c=ap[0],ap_end_c=ap[-1],ap_peak_c=max(ap),ap_median_c=statistics.median(ap))
    base=phases['resident_baseline']['ap_median_c']
    require(max(t['ap_peak_c'] for t in phases.values())-base>=.3,'AP signal insufficient for thermal freeze')
    load_start=phases['load']['start_ns'];common_end=phases['post_work_wait']['end_ns'];cool_end=phases['resident_cooling']['end_ns']
    require(479<= (common_end-load_start)/1e9 <=481,'common window')
    completion=max(r['persist_complete_ns'] for r in rows)
    idle_w=phases['resident_baseline']['energy']['mean_power_w']
    spans=state_intervals(rows,load_start,common_end)
    metrics={}
    for label,end in [('equal_work',completion),('common_window',common_end),('including_cooling',cool_end)]:
        x=integrate(samples,load_start,end,1000);x['increment_above_resident_idle_j']=x['covered_energy_j']-idle_w*x['covered_s']
        x['completed_work']=870;x['unfinished']=0;x['thermal_burden']=thermal_burden(thermal,load_start,end,base)
        metrics[label]=x
    metrics['occupancy_states']=power_by_state(samples,spans)
    metrics['service']={priority:dict(count=len(rr),mean_response_ns=statistics.mean(
        r['output_ready_ns' if priority=='urgent' else 'persist_complete_ns']-r['scheduled_arrival_ns'] for r in rr),
        deadline_violation=None,deadline='not defined; fixed-work collection not UX evaluation') for priority in ('urgent','normal')
        for rr in [[r for r in rows if r['priority']==priority]]}
    counters=[s for s in samples if s.get('charge_valid') and load_start<=s['mono_ns']<=cool_end]
    metrics['counter']=dict(first=counters[0]['charge_counter_raw'] if counters else None,last=counters[-1]['charge_counter_raw'] if counters else None,
        distinct_values=len({s['charge_counter_raw'] for s in counters}),unit='nominal uAh, not external ground truth')
    metrics['unit_diagnostics']=counter_windows(samples,load_start,cool_end)
    return dict(status='eligible_descriptive_only',condition=m['pair']+'_'+m['mode'],validation=validation,phases=phases,
        metrics=metrics,
        warmup=8,eligibility_requests=2,work_requests=870,unit_hypothesis_ua_per_raw=1000,absolute_accuracy_certified=False,
        independent_sessions=1,accuracy_pass=None,experiment_ready=False,
        input_hashes={str(f.resolve()):p.digest(f) for f in root.glob('*') if f.is_file()})

def main():
    cli=argparse.ArgumentParser();sub=cli.add_subparsers(dest='action',required=True)
    q=sub.add_parser('prepare')
    for arg in ('source','build','references','output'):q.add_argument('--'+arg,required=True)
    q=sub.add_parser('check');q.add_argument('--plan',required=True)
    q=sub.add_parser('run')
    for arg in ('plan','adb','serial','expected-sha'):q.add_argument('--'+arg,required=True)
    q.add_argument('--approved',action='store_true')
    a=cli.parse_args()
    if a.action=='prepare':result=prepare(a.source,a.build,a.references,a.output)
    elif a.action=='check':result=check(a.plan)
    else:
        from tools.d1_energy_collection_device import run
        result=run(a.plan,a.adb,a.serial,a.expected_sha,a.approved)
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
