"""Development-only policy-context model and independent prospective evaluation."""
import copy
import itertools
import math
from pathlib import Path
import numpy as np
from tools import d1_arrival_plan as p
from tools import d1_energy_thermal as energy
from tools import d1_arrival_recorded_replay_analysis as states
from tools import d1_ap_background_contrast_readout as ap_readout
from tools import d1_ap_completion_model as ap
from tools import d1_ap_model_completion as common
from tools import d1_arrival_explore as engine
from tools import d1_arrival_explore_batch as batch
from tools import d1_arrival_policy_screen as screen
from tools import d1_arrival_energy_analysis as logs

POLICIES=engine.ONLINE_STUDY
STATES=('classification_CPU','detection_CPU','classification_GPU','classification_GPU+detection_CPU')
FIELDS=('dispatch_ns','execution_start_ns','output_ready_ns','persist_complete_ns','worker_release_ns','lane_available_ns')
ROOT=Path(__file__).resolve().parents[1]
PARAMETERS=ROOT/'docs/results/ap_preparation_memory_01/final/candidate.json'


def requests(role,session='pc'):
    if role not in ('development','confirmation'):raise ValueError('role')
    step=500 if role=='development' else 550
    return [dict(ordinal=i,request_id=f'{session}-{i}',task_id='classification' if i%4==1 else 'detection',
        priority='urgent' if i%4==1 else 'normal',offset_ms=35000+i*step,deadline_ms=1500 if i%4==1 else 6000) for i in range(96)]


def energy_at(case,a,b):
    result=energy.integrate(case['power_samples'],case.get('origin_ns',0)+round(a*1e9),case.get('origin_ns',0)+round(b*1e9),1000)
    if result['full_energy_j'] is None:raise ValueError('missing power interval')
    return result['full_energy_j']


def exposure(segments,a,b):
    x=np.zeros(4);covered=0.
    for s in segments:
        dt=max(0.,min(b,s['end_s'])-max(a,s['start_s']))
        if not dt:continue
        covered+=dt;key=states.state_key(s['state'])
        if key=='resident_idle':continue
        if key not in STATES:raise ValueError('unsupported state '+key)
        x[STATES.index(key)]+=dt
    if abs(covered-(b-a))>1e-6:raise ValueError('incomplete state interval')
    return x


def load_case(file,plan,entry):
    folder=Path(plan['output_root'])/f"{entry['index']:02d}_{entry['session_id']}";art=folder/'artifacts'
    if p.read(folder/'validated.json')['status']!='eligible_descriptive_only':raise ValueError('not eligible')
    # Existing AP reader has a legacy count validator. Use a private data copy with
    # only that count dispatch adapted; no old evidence or function is modified.
    m=p.read(Path(file).parent/entry['manifest']);origin=p.read(art/'common_boundary.json')['start_ns']
    rows=p.read(art/'requests.json');ev=logs.read_lines(art/'progress.jsonl')
    if len(rows)!=96 or any(r['terminal_status']!='succeeded' for r in rows):raise ValueError('full denominator')
    if p.read(art/'manifest.json')!=m or p.read(art/'cleanup.json')['status']!='completed':raise ValueError('manifest/cleanup')
    baseline=[e['mono_ns'] for e in ev if (e.get('phase'),e.get('kind'))==('resident_baseline','phase_start')]
    cooling=[e['mono_ns'] for e in ev if (e.get('phase'),e.get('kind'))==('resident_cooling','phase_end')]
    if len(baseline)!=1 or len(cooling)!=1:raise ValueError('phase boundaries')
    if any(not origin+35e9<=r['dispatch_ns']<r['lane_available_ns']<origin+120e9 for r in rows):raise ValueError('work window')
    th=logs.read_lines(folder/'thermal.jsonl');good=[r for r in th if r.get('AP') not in ('',None) and r.get('thermal_status')=='0']
    if any(not r['before_ns']<=r['mono_ns']<=r['after_ns'] for r in good):raise ValueError('AP bracket')
    pre=[dict(t=(r['mono_ns']-origin)/1e9,ap=float(r['AP']),lo=(r['before_ns']-origin)/1e9,hi=(r['after_ns']-origin)/1e9) for r in good if baseline[0]<=r['before_ns']<=r['after_ns']<origin+35e9]
    post=[r for r in good if origin+35e9<=r['before_ns']<=r['after_ns']<=cooling[0]]
    ts=[(r['mono_ns']-origin)/1e9 for r in post];end=(cooling[0]-origin)/1e9
    if not ts or len(ts)<20 or ts[0]-35>10 or end-ts[-1]>10 or any(not 0<b-a<=10 for a,b in zip(ts,ts[1:])):raise ValueError('AP coverage')
    segments=states.observed_segments(rows,origin);segments.append(dict(start_s=120.,end_s=end,state='idle'))
    samples=[dict(e,mono_ns=(e['snapshot_start_ns']+e['sensor_read_end_ns'])//2) for e in ev if e.get('kind')=='power_sample']
    relative=[dict(r,**{k:r[k]-origin for k in FIELDS+('scheduled_arrival_ns','actual_arrival_ns')}) for r in rows]
    result=dict(id=entry['phase'],study_phase=plan['study_phase'],policy=m['policy'],condition=m['policy'],manifest_requests=m['requests'],
        origin_ns=origin,inputs=dict(preload=pre,query_s=ts,segments=segments),observed_ap_c=[float(r['AP']) for r in post],power_samples=samples,rows=relative,
        first_dispatch_s=min(r['dispatch_ns'] for r in relative)/1e9,last_lane_s=max(r['lane_available_ns'] for r in relative)/1e9,
        common_start_ap_c=p.read(art/'start_ap.accepted.json')['ap_c'])
    result['preload_power_w']=energy_at(result,10,30)/20
    result['observed_120s_j']=energy_at(result,0,120)
    return result


def nnls(x,y):
    solutions=[np.zeros(x.shape[1])]
    for n in range(1,x.shape[1]+1):
        for use in itertools.combinations(range(x.shape[1]),n):
            z=np.zeros(x.shape[1]);z[list(use)]=np.linalg.lstsq(x[:,use],y,rcond=None)[0]
            if np.all(z>=0):solutions.append(z)
    return min(solutions,key=lambda z:float(np.sum((x@z-y)**2)))


def develop(cases):
    if len(cases)!=3 or [c['policy'] for c in cases]!=list(POLICIES) or any(c['study_phase']!='development' for c in cases):raise ValueError('designated development only')
    xs=[];ys=[];service={};params=p.read(PARAMETERS)['fixed_parameters'];axs=[];ays=[]
    for c in cases:
        for a in range(35,120,5):
            xs.append(exposure(c['inputs']['segments'],a,a+5));ys.append(energy_at(c,a,a+5)-c['preload_power_w']*5)
        a,x,_=ap.basis(c,params,params['ap_cooling_rate_per_s']);axs.extend(x[:,0]/math.sqrt(len(a)));ays.extend((np.array(c['observed_ap_c'])-a)/math.sqrt(len(a)))
        cells={}
        for r in c['rows']:
            key=r['task_id']+'_'+r['selected_backend']+'_'+r['priority']
            cells.setdefault(key,[]).append([r[b]-r[a] for a,b in zip(FIELDS,FIELDS[1:])])
        means={k:np.mean(v,axis=0).tolist() for k,v in cells.items()}
        service[c['policy']]=dict(phase_means_ns=means,counts={k:len(v) for k,v in cells.items()})
    x=np.array(xs);y=np.array(ys);sv=np.linalg.svd(x,compute_uv=False)
    if np.linalg.matrix_rank(x)!=4:raise ValueError('energy increments unidentified; no confirmation')
    ax=np.array(axs);ay=np.array(ays)
    if ax@ax<=1e-12:raise ValueError('AP gain unidentified')
    power=nnls(x,y);gain=max(0.,float(ax@ay/(ax@ax)))
    return dict(version='online-policy-model-v1',energy_increment_w=dict(zip(STATES,power.tolist())),energy_design_singular_values=sv.tolist(),
        energy_fit_rmse_j=float(np.mean((x@power-y)**2)**.5),ap=dict(beta=params['ap_cooling_rate_per_s'],k=gain,g=0.,parameters=params),
        service=service,development_ids=[c['id'] for c in cases],accuracy_pass=None,experiment_ready=False,
        scope='A24 96 registered requests at 500/550ms, these three policies, same APK/resident; pre35 observations required; no independent throttle model')


def service_config(frozen,policy):
    spec=frozen['service'][policy];cells={};vectors={}
    for key,d in spec['phase_means_ns'].items():
        response=sum(d[:2 if key.endswith('urgent') else 3])
        cells[key]=dict(joint={'dispatch_to_lane_ns':dict(median_ns=sum(d)),'dispatch_to_response_ns':dict(median_ns=response)},
            observed_phases={'start_to_output_ready_ns':dict(median_ns=d[1])})
        vectors[key]=[dict(source_request_id='development_phase_mean_not_independent_draw',durations_ns=d) for _ in range(4)]
    return dict(protocol='online-context-service-v1',policy=policy,cells=cells),dict(cells=vectors)


def validate_service(config,vectors,requests,policy,settings):
    if policy not in POLICIES or config['policy']!=policy or settings['interference']!=1 or settings['predicted_interference']!=1:raise ValueError('service context')
    if len(requests)!=96 or any(r['task']!=('classification' if r['ordinal']%4==1 else 'detection') or r['priority']!=('urgent' if r['ordinal']%4==1 else 'normal') for r in requests):raise ValueError('unregistered workload')
    times=[r['arrival_ns'] for r in sorted(requests,key=lambda r:r['ordinal'])]
    if times not in ([35000000000+i*step for i in range(96)] for step in (500000000,550000000)):
        raise ValueError('unsupported arrival interval')
    expected={'detection_CPU_normal','classification_CPU_urgent' if policy==POLICIES[0] else 'classification_GPU_urgent'}
    if set(config['cells'])!=expected or set(vectors['cells'])!=expected:raise ValueError('unsupported service cells')
    for key,v in vectors['cells'].items():
        if key not in config['cells'] or len(v)!=4 or any(len(r['durations_ns'])!=5 or any(not math.isfinite(x) or x<0 for x in r['durations_ns']) for r in v):raise ValueError('phase vector')


def forecast(initial,manifest_requests,policy,frozen):
    # Explicit initial whitelist: post35 AP/power and actual future rows excluded.
    config,vectors=service_config(frozen,policy);settings=batch.defaults('explore')
    settings.update(interference=1,predicted_interference=1,decision_ns=0,record_ns=0,dispatch_ns=0,
                    static_map={'classification':'GPU','detection':'CPU'},static_parallel=True)
    tickets=[dict(id=q['request_id'],task=q['task_id'],priority=q['priority'],ordinal=q['ordinal'],arrival_ns=q['offset_ms']*1_000_000,deadline_offset_ns=q['deadline_ms']*1_000_000) for q in manifest_requests]
    result=engine.simulate(config,vectors,tickets,policy=policy,settings=settings,seed=201)
    if any(r['status']!='succeeded' for r in result['ledger']):raise ValueError('forecast incomplete; no partial full cost')
    segments=screen.occupancy(result,'sustained_mixed',1,201,policy)
    return result,segments


def costs(segments,initial,queries,model,end):
    inc=np.array([model['energy_increment_w'][k] for k in STATES])
    mode=model.get('energy_baseline_mode','session_preload')
    if mode=='session_preload':base=initial['preload_power_w']
    elif mode=='pooled_resident_v1':base=model['resident_w']
    else:raise ValueError('unregistered energy baseline mode')
    if not math.isfinite(base) or base<=0:raise ValueError('preload power')
    curve=[]
    for t in range(121):curve.append(dict(common_s=t,predicted_j=base*t+float(exposure(segments,0,t)@inc)))
    aps=copy.deepcopy(segments)
    if aps[-1]['end_s']<=120:aps.append(dict(start_s=120.,end_s=end,state='idle'))
    vals,init=ap.predict(dict(inputs=dict(preload=initial['preload'],query_s=queries,segments=aps)),model['ap'])
    return dict(energy_path=curve,whole_120s_j=curve[-1]['predicted_j'],prospective_35_120s_j=curve[-1]['predicted_j']-curve[35]['predicted_j'],ap_path=vals,initial=init)


def evaluate(cases,model):
    result=[]
    for c in cases:
        initial=dict(preload=c['inputs']['preload'],preload_power_w=c['preload_power_w'])
        forecast_rows,forecast_segments=forecast(initial,c['manifest_requests'],c['policy'],model)
        outputs={};query=c['inputs']['query_s'];end=c['inputs']['segments'][-1]['end_s']
        for name,seg in [('actual_schedule_conditional',c['inputs']['segments']),('arrival_forecast',forecast_segments)]:
            out=costs(seg,initial,query,model,end);out['energy_signed_error_j']=out['whole_120s_j']-c['observed_120s_j']
            out['energy_relative_error']=out['energy_signed_error_j']/c['observed_120s_j'];out['ap_scores']=common.score(c['observed_ap_c'],out['ap_path'])
            original_ap=dict(model['ap'],k=1.,g=0.)
            apseg=copy.deepcopy(seg)
            if apseg[-1]['end_s']<=120:apseg.append(dict(start_s=120.,end_s=end,state='idle'))
            out['original_m0_ap_path']=ap.predict(dict(inputs=dict(preload=initial['preload'],query_s=query,segments=apseg)),original_ap)[0]
            out['original_m0_scores']=common.score(c['observed_ap_c'],out['original_m0_ap_path'])
            powers=model.get('original_whole_device_power_w')
            out['original_power_120s_j']=None if powers is None else sum(max(0.,min(120.,s['end_s'])-s['start_s'])*powers[states.state_key(s['state'])] for s in seg if s['start_s']<120)
            outputs[name]=out
        predicted={r['id']:r for r in forecast_rows['ledger']};timing=[]
        for r in c['rows']:
            y=predicted[r['request_id']];field='output_ready_ns' if r['priority']=='urgent' else 'persist_complete_ns'
            timing.append(dict(id=r['request_id'],priority=r['priority'],actual_response_ms=(r[field]-r['scheduled_arrival_ns'])/1e6,
                predicted_response_ms=(y[field]-y['arrival_ns'])/1e6,dispatch_error_ms=(y['dispatch_ns']-r['dispatch_ns'])/1e6,lane_error_ms=(y['lane_available_ns']-r['lane_available_ns'])/1e6,
                deadline_ms=next(q['deadline_ms'] for q in c['manifest_requests'] if q['request_id']==r['request_id'])))
        service={}
        for source in ('actual','predicted'):
            for priority in ('urgent','normal','all'):
                rows=[r for r in timing if priority=='all' or r['priority']==priority];v=[r[source+'_response_ms'] for r in rows]
                service[source+'_'+priority]=dict(planned=len(rows),completed=len(rows),p95_ms=sorted(v)[math.ceil(.95*len(v))-1],deadline_met=sum(a<=r['deadline_ms'] for a,r in zip(v,rows)))
        result.append(dict(id=c['id'],phase=c['study_phase'],policy=c['policy'],observed_120s_j=c['observed_120s_j'],common_start_ap_c=c['common_start_ap_c'],
            outputs=outputs,service=service,timing=timing,forecast_ledger=forecast_rows['ledger'],actual_rows=c['rows'],actual_segments=c['inputs']['segments'],
            ap_query_s=query,observed_ap_c=c['observed_ap_c'],observed_energy_path=[dict(common_s=t,observed_j=energy_at(c,0,t)) for t in range(1,121)],
            accuracy_pass=None,experiment_ready=False,independent_sessions=1))
    return result
