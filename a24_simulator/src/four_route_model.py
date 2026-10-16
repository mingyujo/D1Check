"""Four CPU/GPU cells, with declared historical and additive extrapolation.

Original measured cells are delegated unchanged. New DG timing/heat/cost are
model predictions with provenance, never new current-device measurements.
"""
from __future__ import annotations
import copy, hashlib, json, statistics
from pathlib import Path
from timing_model import NS, BOUNDARIES, context_of, context_for_route, digest, public_snapshot, feature_stratum
import thermal_four_route

OLD_STATES=thermal_four_route.STATES[:4]
NEW_STATES=thermal_four_route.STATES[4:]
TRANSFER_SPEC={'method':'task-device additive + shared CPU/GPU interaction; nonnegative projection',
               'DG':'max(0,DC+CG-CC)','CC_DG':'CG_DC','CC_CG':'max(0,CC+CG_DC-DC)','DC_DG':'max(0,DC+CG_DC-CC)',
               'current_DG_measurement':False,'same_model_for_all_policies':True}

def extend_gains(values):
    a,c,b,p=map(float,values)
    return [*map(float,values),max(0.,c+b-a),p,max(0.,a+p-c),max(0.,c+p-a)]

def extend_thermal(original):
    model=copy.deepcopy(original);old_width=7;out=[]
    for i in range(len(model['domains'])):
        old=model['coefficients'][i*old_width:(i+1)*old_width]
        out.extend([*old[:3],*extend_gains(old[3:])])
    model['coefficients']=out
    model['feature_names']=[domain+'::'+name for domain in model['domains'] for name in thermal_four_route.LOCAL_FEATURES]
    model['original_model_sha256']=original['model_sha256']
    model['four_route_transfer_spec']=copy.deepcopy(TRANSFER_SPEC)
    model['model_sha256']=digest({k:v for k,v in model.items() if k!='model_sha256'})
    return model

def extend_profile(original):
    p=copy.deepcopy(original);powers=p['cost_anchor']['energy_increment_w']
    values=extend_gains([powers[k] for k in OLD_STATES])
    for key,value in zip(thermal_four_route.STATES,values): powers[key]=value
    p['four_route_transfer_spec']=copy.deepcopy(TRANSFER_SPEC)
    p['original_profile_sha256_semantic']=digest(original)
    p['derived_profile_sha256']=digest(p)
    return p

def labels(active):
    routes=[x['route'] for x in active]
    if len(routes)>2 or len(routes)!=len(set(routes)) or any(r not in ('CPU','GPU') for r in routes):
        raise ValueError('Resource occupancy violation')
    return '+'.join(sorted(('classification' if x['task']=='C' else 'detection')+'_'+x['route'] for x in active)) or 'resident_idle'

def conditional_energy(session, profile, start_s=0.,end_s=180.):
    coverage=session.get('activity_coverage_s')
    if not coverage or coverage[0]>start_s or coverage[1]<end_s:
        return {'status':'UNKNOWN_ACTIVITY_COVERAGE','historical_conditional_J':None,'measured_J':None,'energy_error_J':None}
    intervals=session.get('owner_intervals',[]);marks=sorted({start_s,end_s,*[max(start_s,min(end_s,float(x[k]))) for x in intervals for k in ('start_s','end_s')]})
    occupancy={k:0. for k in (*thermal_four_route.STATES,'resident_idle')}
    for a,b in zip(marks,marks[1:]):
        key=labels([x for x in intervals if x['start_s']<b and x['end_s']>a]);occupancy[key]+=b-a
    powers=profile['cost_anchor']['energy_increment_w'];base=profile['measured35']['baseline_w']*(end_s-start_s)
    terms={k:occupancy[k]*powers[k] for k in thermal_four_route.STATES}
    return {'status':'FOUR_ROUTE_CONDITIONAL_HISTORICAL_PROXY_WITH_DECLARED_FACTOR_TRANSFER','window_s':[start_s,end_s],
            'state_seconds':occupancy,'baseline_J':base,'increment_terms_J':terms,'historical_conditional_J':base+sum(terms.values()),
            'measured_J':None,'energy_error_J':None,'independent_energy_saving_validated':False,
            'unmeasured_state_seconds':{k:occupancy[k] for k in NEW_STATES},'transfer_spec':TRANSFER_SPEC}

def original_context(context):
    c=copy.deepcopy(context);registry=c.get('compatibility',{}).get('public_models',{})
    if registry.get('D_GPU',{}).get('historical_GPU_timing_transfer_unverified_current_APK') is True:
        registry.pop('D_GPU',None)
    return c

class FourRouteTiming:
    def __init__(self, inner, contexts, evidence):
        self.inner,self.contexts=inner,contexts;rows=evidence['rows'];self.ratios=[];self.nominal_cache={}
        for gpu in rows:
            if gpu['cell']!='detection_GPU_normal':continue
            cpu=next(r for r in rows if r['cell']=='detection_CPU_normal' and r['role']==gpu['role'] and r['ordinal']==gpu['ordinal'])
            if not gpu['gpu_delegate_verified'] or cpu['input_tensor_sha256']!=gpu['input_tensor_sha256']:raise ValueError('Historical DG pairing invalid')
            if len(gpu['durations_ns'])!=5 or min(cpu['durations_ns'])<=0:raise ValueError('Five-stage historical vector invalid')
            self.ratios.append({'stages_ratio':[a/b for a,b in zip(gpu['durations_ns'],cpu['durations_ns'])],
                                'GPU_source_id':gpu['source_request_id'],'CPU_source_id':cpu['source_request_id'],
                                'tensor_sha256':gpu['input_tensor_sha256'],'role':gpu['role'],'ordinal':gpu['ordinal']})
        if len(self.ratios)!=8:raise ValueError('Expected 8 matched ratios, two historical role sessions')
        for identity in evidence['identities']:
            if identity['model_sha256']['detection_GPU']!=identity['model_sha256']['detection_CPU']:raise ValueError('Source model identity differs')
        self.metadata=copy.deepcopy(inner.metadata);self.metadata.update(original_model_digest=inner.metadata['model_digest'],
             model_digest=digest([inner.metadata['model_digest'],self.ratios,TRANSFER_SPEC]),
             route_scope=['C_CPU','C_GPU','D_CPU','D_GPU'],DG_timing_status='HISTORICAL_STAGE_RATIO_CURRENT_CPU_TRANSFER_NOT_VERIFIED_CURRENT_GPU')
    def __getattr__(self,k):return getattr(self.inner,k)
    def request_context(self,template,request):
        source=self.contexts[request['request_id']];return context_of(source,request,self.strict)
    def admission(self,context,task,key,**kw):return self.inner.admission(original_context(context),task,key,**kw)
    def redispatch(self,action,state,key,**kw):
        a=copy.deepcopy(action);a['context']=original_context(a['context'])
        if a['task']=='D' and a['route']=='GPU':a.update(route='CPU',context=context_for_route(a['context'],'D','CPU'))
        return self.inner.redispatch(a,state,key,**kw)
    def _cpu_context(self,context):
        c=context_for_route(original_context(context),'D','CPU')
        if c['tensor_sha256'] not in {r['tensor_sha256'] for r in self.ratios}:raise ValueError('DG tensor not bound to historical ratio evidence')
        return c
    def nominal(self,context,task,route,protocol='SERIAL',state=None):
        if (task,route)!=('D','GPU'):return self.inner.nominal(original_context(context),task,route,protocol,state)
        c=self._cpu_context(context);cache=digest([c,feature_stratum(state or {},self.inner.feature_mode)])
        if cache not in self.nominal_cache:
            pool=self.inner._pool(self.inner.samples,c,'D','CPU','SERIAL',state)
            vectors=[[max(0,round(v*r)) for v,r in zip(s['stages_ns'],ratio['stages_ratio'])] for s in pool for ratio in self.ratios]
            self.nominal_cache[cache]={'occupancy_ns':round(statistics.median(map(sum,vectors))),
                'response_ns':round(statistics.median(sum(v[:3]) for v in vectors)),'support_requests':len(pool),
                'historical_ratio_requests':8,'historical_ratio_sessions':2,'validation_status':'TRANSFER_PREDICTION_UNVALIDATED','energy_proxy_j':None,'thermal_feedback':None}
        return copy.deepcopy(self.nominal_cache[cache])
    def draw_latent_serial(self,action,state,key):
        a=copy.deepcopy(action);a['context']=original_context(a['context'])
        if (a['task'],a['route'])!=('D','GPU'):return self.inner.draw_latent_serial(a,state,key)
        a.update(route='CPU',context=self._cpu_context(action['context']));base=self.inner.draw_latent_serial(a,state,key)
        i=int(digest(['DG_HISTORICAL_RATIO',key]),16)%len(self.ratios);ratio=self.ratios[i]
        v=[max(0,round(x*r)) for x,r in zip(base['stages_ns'],ratio['stages_ratio'])]
        out=copy.deepcopy(base);out.update(sample_id='DG_MODEL_TRANSFER:'+base['sample_id']+':'+str(i),stages_ns=v,
              DG_transfer={'base_serial_vector_ns':base['stages_ns'],'historical_ratio':ratio,'current_GPU_observation':False},
              latent_work_coordinate='PREDICTED_DG_SERIAL_NS_FROM_CURRENT_CPU_AND_HISTORICAL_PAIRED_VECTOR_RATIOS')
        out['selection']['DG_ratio_index']=i;return out
    def progress_rates(self,action,state,**kw):
        pair={(o['task'],o['route']) for o in state.get('owners',[])}
        if pair=={('C','GPU'),('D','CPU')}:
            a=copy.deepcopy(action);a['context']=original_context(a['context']);return self.inner.progress_rates(a,state,**kw)
        return {'rates':[1.]*5,'evidence':'UNMEASURED_PAIR_EXPLICIT_INDEPENDENT_SERVICE_EXTRAPOLATION','public_pair':sorted(pair),
                'interference_measured':False,'future_overlap_used':False}
