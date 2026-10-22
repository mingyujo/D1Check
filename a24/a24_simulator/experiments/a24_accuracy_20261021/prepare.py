"""Project already saved measurements; no fitting, training or policy rollout."""
import gzip, hashlib, json, math, subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

H=Path(__file__).resolve().parent
R=H.parents[2]
A=R/'a24_simulator'
O=A/'results/A24_ACCURACY_20261021_02'

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p): return json.loads(p.read_text(encoding='utf-8-sig'))
def write(p,x):
    with p.open('x',encoding='utf-8',newline='\n') as f: json.dump(x,f,ensure_ascii=False,allow_nan=False,separators=(',',':'))
def finite(x): return isinstance(x,(float,int)) and math.isfinite(x)
def pin(p): return {'path':p.relative_to(R).as_posix(),'sha256':sha(p),'bytes':p.stat().st_size}
def unpack(p):
    b=gzip.decompress((A/p['stored']).read_bytes())
    assert hashlib.sha256(b).hexdigest()==p['sha256']
    return json.loads(b)

def main():
    O.mkdir(exist_ok=False)
    manifest=read(A/'data/CORE_MANIFEST.json')
    dataset=next(x for x in manifest if x['name']=='MODEL_INPUTS.json')
    oldpin=read(A/'experiments/competition_cost_20261017/COST_OPERATION.json')['historical_power_pin']
    data=unpack(dataset); legacy=unpack(oldpin)
    assert len(data['sessions'])==115 and len(legacy)==35
    cases=[];screen=[];timing=[];all_status=Counter()
    for s in data['sessions']:
        sid=s['session_id']; source=s['source_generation']; reason=[]
        native=s['source_family']=='m8'
        obs=sorted([o for o in s['observations'] if o.get('channel')=='AP' and finite(o.get('ap_c'))],key=lambda x:x['t_s'])
        pres=[o for o in obs if finite(o.get('hi_s')) and o['hi_s']<=35 and o['t_s']<=35]
        initial=pres[-1] if pres else None
        if not s['target_eligibility'].get('ap_fit'): reason.append('source_AP_ineligible')
        if not initial: reason.append('no_AP_returned_before_35')
        elif 35-initial['t_s']>10: reason.append('initial_AP_older_than_10s')
        if not s.get('activity_coverage_s') or s['activity_coverage_s'][0]>35: reason.append('activity_start_unknown')
        intervals=[]
        for q in s.get('requests',[]):
            status=q.get('status',q.get('declared_terminal_status','UNKNOWN'));all_status[status]+=1
            if q.get('complete_vector') and status=='COMPLETED' and q.get('route') in ('CPU','GPU'):
                points=[q.get(k) for k in ('dispatch_s','execution_start_s','output_ready_s','persist_complete_s','worker_release_s','available_s')]
                if all(finite(x) for x in points) and all(b>=a for a,b in zip(points,points[1:])):
                    for stage,(lo,hi) in enumerate(zip(points,points[1:])):
                        if hi>lo:intervals.append({'start_s':lo,'end_s':hi,'id':q['request_id'],'task':q['task'],'route':q['route'],'stage':stage})
                    timing.append({'session':sid,'source':source,'protocol':s['protocol'],'source_timing_eligible':s['target_eligibility'].get('timing_fit',False),
                        'request_id':q['request_id'],'route':q['task']+'_'+q['route'],'status':status,'observed_response_boundary':q.get('response_boundary'),
                        'dispatch_s':points[0],'observed_vector':[b-a for a,b in zip(points,points[1:])],
                        'hardware_verified':q.get('actual_hardware_delegate_verified',False),
                        'model_identity_verified':q.get('route_selected_model_identity_verified',False)})
                else:reason.append('nonfinite_or_reversed_phase_clock')
            elif native and finite(q.get('dispatch_s')):reason.append('started_request_without_complete_vector')
        if native:
            if len(s.get('owner_intervals',[]))!=sum(q.get('complete_vector',False) for q in s['requests']):reason.append('owner_phase_count_mismatch')
            schedule_kind='observed_five_phase'
        elif s['state_intervals']:
            schedule_kind='historical_collapsed_state_INFER_proxy'
            prior=0.
            for i,x in enumerate(s['state_intervals']):
                if abs(x['start_s']-prior)>1e-6: reason.append('historical_activity_gap')
                prior=x['end_s']
                state=x['state'].replace(':','_')
                if state=='idle':continue
                for j,k in enumerate(state.split('+')):
                    task,route=k.rsplit('_',1)
                    intervals.append({'start_s':x['start_s'],'end_s':x['end_s'],'id':f'{sid}_{i}_{j}','task':{'classification':'C','detection':'D'}[task],'route':route,'stage':1})
        else:
            schedule_kind='not_reconstructible';reason.append('five_phase_or_state_schedule_unavailable')
        post=[{'t':o['t_s'],'observed_c':o['ap_c'],'lo':o.get('lo_s'),'hi':o.get('hi_s')} for o in obs if o['t_s']>35 and o['t_s']<=s.get('activity_coverage_s',[0,0])[1]]
        if len(post)<2:reason.append('insufficient_post_AP')
        if any(b['t']<=a['t'] for a,b in zip(post,post[1:])):reason.append('duplicate_or_reversed_AP_clock')
        reason=sorted(set(reason))
        screen.append({'session':sid,'source':source,'source_family':s['source_family'],'protocol':s['protocol'],'included':not reason,'reasons':reason,
            'observed_requests':len(s['requests']),'post_AP':len(post),'AP_total':len(obs),'schedule_kind':schedule_kind,
            'original_role':s.get('original_role'),'current_role':s.get('role'),'sensor_contract_qualified':s['compatibility'].get('ap_sensor_contract_qualified',False),
            'APK_verified':s['compatibility'].get('installed_APK_verified',False)})
        if reason:continue
        cases.append({'session':sid,'source':source,'family':s['source_family'],'protocol':s['protocol'],'schedule_kind':schedule_kind,
            'initial_c':initial['ap_c'],'initial_time_s':initial['t_s'],'initial_return_hi_s':initial['hi_s'],
            'activity_end_s':s['activity_coverage_s'][1],'owners':intervals,'observations':post,
            'last_work_s':max([x['end_s'] for x in intervals],default=None)})
    packet={'schema':'A24-current-accuracy-saved-v1','profile':read(A/'experiments/a24_s26_common_20261020/PROFILES.json')['A24'],
        'cases':cases,'legacy_power':legacy,'timing':timing,'screening':screen,'all_arrival_status':dict(all_status),
        'fresh_confirmation':False,'fits':0,'policy_environments':0,'new_device_measurements':0}
    write(O/'INPUTS.json',packet)
    sources=[H/'PROTOCOL.md',*sorted(H.glob('*.py')),*sorted(H.glob('*.cjs')),R/'common_simulator/v1/profiles.cjs',
        A/'experiments/a24_s26_common_20261020/PROFILES.json',A/'experiments/competition_cost_20261017/COST_OPERATION.json',
        A/'results/STATE_COST_IDENTIFICATION_20261017_01/MODEL.json',A/'data/CORE_MANIFEST.json',A/dataset['stored'],A/oldpin['stored'],
        A/'experiments/a24_duration_040_20261019/banks/D040_T600_P0_S160.BANK.json.gz']
    write(O/'REGISTRATION.json',{'utc':datetime.now(timezone.utc).isoformat(),'HEAD':subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip(),
        'dirty_worktree':True,'inputs':pin(O/'INPUTS.json'),'sources':[pin(p) for p in dict.fromkeys(sources)],
        'source_dataset_uncompressed_sha256':dataset['sha256'],'source_legacy_uncompressed_sha256':oldpin['sha256'],
        'included':len(cases),'excluded':len(screen)-len(cases),'by_source':dict(Counter(c['source'] for c in cases)),
        'fits':0,'policy_environments':0,'phone_measurements':0,'fresh_confirmation':False})
    print(json.dumps({'status':'PREPARED','included':len(cases),'excluded':len(screen)-len(cases),'timing_vectors':len(timing),'all_arrivals':dict(all_status)},ensure_ascii=False))

if __name__=='__main__':main()
