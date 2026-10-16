"""Synthetic resource/mask and numerical-extension checks, zero environments."""
import copy,json,sys,os,statistics
from pathlib import Path
HERE=Path(__file__).resolve().parent
import lab_backend as lab
from four_route_model import FourRouteTiming,extend_gains,extend_profile,extend_thermal,conditional_energy,original_context
import policy_bridge_four_route as bridge
import interactive_kernel as engine
import thermal_four_route as thermal

checks=[]
def check(name,condition):
    if not condition:raise AssertionError(name)
    checks.append(name)

def main():
    lab.runtime_guard.process_guard(Path(os.environ['A24_LAB_GUARD_ENTRY']),[])
    lab.free_guard([HERE,'D:/'])
    evidence=json.loads((HERE/'DG_TIMING_EVIDENCE.json').read_text(encoding='utf-8'))
    q=lambda rid,task:dict(request_id=rid,ordinal=int(rid[1:]),task=task,priority='U' if task=='C' else 'N',group=0,scheduled_arrival_ns=0,queue_entry_ns=0,deadline_ns=2_000_000_000)
    queue=[q('q0','C'),q('q1','D')]
    estimates={r['request_id']:{b:dict(occupancy_ns=100000000,response_ns=80000000,energy_proxy_j=.1) for b in ('CPU','GPU')} for r in queue}
    obs=dict(now_ns=0,queue=queue,owners={},estimates=estimates,sensor={'AP_c':27.,'power_w':2.,'age_s':0.,'recent_activity':{}},history={},alpha=.95,heat_weight=.5)
    for task in ('C','D'):
        bank=bridge.build_bank(obs);actions=[a for i,a in enumerate(bank['actions']) if bank['mask'][i] and a['kind']=='DISPATCH' and next(q for q in queue if q['request_id']==a['request_id'])['task']==task]
        check(task+' CPU and GPU mask legal', {a['route'] for a in actions}=={'CPU','GPU'})
    for owner_task in ('C','D'):
        for owner_route in ('CPU','GPU'):
            for task in ('C','D'):
                one=q('q2',task);o=copy.deepcopy(obs);o.update(queue=[one],owners={owner_route:dict(request_id='old',task=owner_task,dispatch_ns=0,phase_index=0)},estimates={'q2':estimates['q0']})
                bank=bridge.build_bank(o);routes={a['route'] for i,a in enumerate(bank['actions']) if bank['mask'][i] and a['kind']=='DISPATCH'}
                check(f'{owner_task}/{owner_route} owner permits other lane for {task}',routes==({'CPU','GPU'}-{owner_route}))
                check('NPU remains masked '+owner_task+owner_route+task,not any(bank['mask'][i] and a.get('route')=='NPU' for i,a in enumerate(bank['actions'])))
    check('Gain transfer preserves original4',extend_gains([.58,.71,.47,.88])[:4]==[.58,.71,.47,.88])
    check('Gain transfer DG and all pair states',len(extend_gains([.58,.71,.47,.88]))==8)
    check('Physical nonnegative projection',min(extend_gains([2,.1,.1,.1]))>=0)
    check('Existing DG public registry preserved', 'D_GPU' in original_context({'compatibility':{'public_models':{'D_GPU':{'model':{'sha256':'existing'}}}}})['compatibility']['public_models'])
    check('Only newly added transfer registry removed for parent matching', 'D_GPU' not in original_context({'compatibility':{'public_models':{'D_GPU':{'historical_GPU_timing_transfer_unverified_current_APK':True}}}})['compatibility']['public_models'])
    original={'domains':['x'],'coefficients':[25.,0.,.3,.58,.71,.47,.88],'model_sha256':'original'}
    extended=extend_thermal(original)
    check('Thermal baseline and original four gains unchanged',extended['coefficients'][:7]==original['coefficients'])
    check('Original thermal untouched',len(original['coefficients'])==7)
    profile=extend_profile({'measured35':{'baseline_w':1.},'cost_anchor':{'energy_increment_w':dict(zip(thermal.STATES[:4],[.58,.71,.47,.88]))}})
    for cpu_task in ('C','D'):
        for gpu_task in ('C','D'):
            s={'activity_coverage_s':[0.,2.],'owner_intervals':[dict(request_id='a',task=cpu_task,route='CPU',start_s=0.,end_s=1.),dict(request_id='b',task=gpu_task,route='GPU',start_s=0.,end_s=1.)]}
            z=conditional_energy(s,profile,0.,2.)
            check('Cost all pair '+cpu_task+gpu_task,z['historical_conditional_J']>=2. and abs(sum(z['state_seconds'].values())-2)<1e-12)
            check('Thermal state all pair '+cpu_task+gpu_task,len(thermal.activity_segments({**s,'activity_coverage_s':[0.,2.]}))==2)
    tensor=next(x['input_tensor_sha256'] for x in evidence['rows'] if x['cell']=='detection_GPU_normal')
    model_sha=evidence['identities'][0]['model_sha256']['detection_CPU']
    registry={task+'_'+route:{'model':{'sha256':model_sha}} for task in ('C','D') for route in ('CPU','GPU')}
    template={'device':'A24','bank':'M128','compatibility':{'public_models':registry,'public_apk_sha256':'synthetic'},'service_stop_ns':3*lab.NS,'drain_stop_ns':5*lab.NS,'observation_end_ns':5*lab.NS,'initial_ap_c':27.}
    class Mock:
        strict=True;feature_mode='exact_public';metadata={'model_digest':'synthetic-base'}
        def admission(self,*a,**kw):return {'scheduled_to_actual_ns':0,'actual_to_queue_ns':0}
        def redispatch(self,*a,**kw):return {'delay_ns':0,'evidence':'SYNTHETIC'}
        def nominal(self,*a,**kw):return dict(occupancy_ns=42000000,response_ns=33000000)
        def draw_latent_serial(self,*a,**kw):return dict(sample_id='unit',stages_ns=[10000000,20000000,3000000,4000000,5000000],selection={},source={})
        def progress_rates(self,*a,**kw):return {'rates':[1.]*5,'evidence':'SYNTHETIC_ORIGINAL_PAIR'}
    for cpu_task in ('C','D'):
        for gpu_task in ('C','D'):
            public=copy.deepcopy(template);public['requests']=[{**q('q0',cpu_task),'bank':'M128','input_sha256':'image','tensor_sha256':tensor,'model_sha256':model_sha},{**q('q1',gpu_task),'bank':'M128','input_sha256':'image','tensor_sha256':tensor,'model_sha256':model_sha}]
            contexts={r['request_id']:{**public,'_requests_by_id':{r['request_id']:r}} for r in public['requests']}
            model=FourRouteTiming(Mock(),contexts,evidence)
            wanted={'q0':'CPU','q1':'GPU'}
            def policy(state):
                busy={o['route'] for o in state['owners']}
                for r in sorted(state['queue'],key=lambda r:r['ordinal']):
                    if wanted[r['request_id']] not in busy:return dict(kind='DISPATCH',request_id=r['request_id'],route=wanted[r['request_id']])
                return {'kind':'RESOURCE_WAIT'}
            result=engine.simulate_protocol(public,model,'FROZEN_RL_REPLAY',execution_guard={'durable_START_consumed':True,'start_id':'SYNTHETIC_FIXTURE_NOT_ENVIRONMENT','registration_sha256':'unit'},scenario_key=['unit',cpu_task,gpu_task],admission_protocol='SERIAL',redispatch_mode='ZERO_EXPLICIT_BASELINE',zero_baseline_id='unit',pair_scope='READY_QUEUE',frozen_policy=policy,frozen_policy_binding={'replay_only':True,'checkpoint_sha256':'unit','input_contract_sha256':'unit'},concurrency_mode='DATA_DERIVED_PROGRESS',unidentified_overlap='SERIAL_INDEPENDENT')
            check('Closed loop four-pair '+cpu_task+gpu_task,result['metrics']['response_completed']==2 and result['metrics']['overlap_ns']>0)
            check('AVAILABLE resource boundary '+cpu_task+gpu_task,all(r['available_ns']>=r['response_ns']>=r['dispatch_ns'] for r in result['requests']))
            if gpu_task=='D':check('DG provenance saved '+cpu_task,'DG_transfer' in result['requests'][1]['timing'])
    check('Historical ratio pool8/two roles',len(model.ratios)==8 and len({r['role'] for r in model.ratios})==2)
    check('Missing energy coverage is unknown',conditional_energy({},profile)['historical_conditional_J'] is None)
    out=Path(sys.argv[1]);lab.write_new(out,{'status':'PASS','check_count':len(checks),'checks':checks,'new_environment':0,'synthetic_only':True,'new_training':0,'measured_J':None,'utc':lab.now()})
    print(json.dumps({'status':'PASS','checks':len(checks),'new_environment':0}))
if __name__=='__main__':main()
