"""Basic LSF and explicit whole-request adaptations of Band's LSF scheduler.

Reference only: Band commit 8600d4960ccb6f121221f6d252da8dbef2db160b.
This is not a build or reproduction of the complete Band inference framework.
"""
import copy,hashlib,math
VERSION='A24_LSF_BAND_REQUEST_ADAPT_V1'
MODES=('LSF_DYN','BAND_LSF_ALL','BAND_LSF_DROP')

def tie(q):return q['scheduled_arrival_ns'],q['ordinal'],q['request_id']
def route_tie(q,r):return hashlib.sha256((q['request_id']+'|'+r).encode()).hexdigest()

class Policy:
    def __init__(self,nominal,physics,mode):
        if mode not in MODES or physics.cpu_slots!=3:raise ValueError('Unsupported LSF config')
        self.nominal,self.physics,self.mode=nominal,physics,mode;self.calls=[];self.wait_calls=[]

    def vector(self,q,route,s):
        v=list(self.nominal.vector(q,route,s))
        if len(v)!=5 or any(not math.isfinite(x) or x<0 for x in v):raise ValueError('Invalid public nominal')
        return v

    def estimates(self,s):
        owners=s['owners'];T=s['sensor']['temperature_c']
        if not math.isfinite(T):raise ValueError('Invalid temperature')
        counts={r:sum(o['route']==r for o in owners) for r in ('CPU','GPU')}
        if any(o['route'] not in counts for o in owners) or counts['CPU']>3 or counts['GPU']>1:raise ValueError('Invalid owners')
        n=sum(o['route']=='CPU' and o['stage']==1 for o in owners)
        free=[r for r in counts if counts[r]<(3 if r=='CPU' else 1)]
        remaining=[]
        for o in owners:
            route=o['route'];v=self.vector(o,route,s);stage=o['stage']
            if stage not in range(5) or o['public_progress_s']<0:raise ValueError('Invalid public owner progress')
            rem=[0.]*stage+[max(0.,v[stage]-o['public_progress_s'])]+v[stage+1:]
            rate=self.physics.speed(T,route,1,o['task'])/(1+self.physics.beta*max(0,n-int(stage==1)) if route=='CPU' else 1.)
            occupied=sum(rem)-rem[1]+rem[1]/rate
            remaining.append(dict(request_id=o['request_id'],route=route,nominal_vector_s=v,remaining_work_s=rem,rate=rate,remaining_occupancy_s=occupied))
        release_jobs={r:None if r in free else min((x for x in remaining if x['route']==r),key=lambda x:(x['remaining_occupancy_s'],x['request_id'])) for r in counts}
        releases={r:0. if release_jobs[r] is None else release_jobs[r]['remaining_occupancy_s'] for r in counts}
        jobs=[]
        for q in s['queue']:
            opts=[]
            for route in ('CPU','GPU'):
                if self.mode=='LSF_DYN' and route not in free:continue
                v=self.vector(q,route,s);other_infer=n
                if route=='CPU' and route not in free:
                    first=next(o for o in owners if o['request_id']==release_jobs[route]['request_id'])
                    other_infer=min(2,max(0,n-int(first['stage']==1)))
                factor=1+self.physics.beta*other_infer if route=='CPU' else 1.
                rate=self.physics.speed(T,route,1,q['task'])/factor
                boundary=2 if q['task']=='C' else 3
                response=sum(v[:boundary])-v[1]+v[1]/rate
                wait=0. if self.mode=='LSF_DYN' else releases[route]
                opts.append(dict(route=route,nominal_vector_s=v,rate=rate,wait_s=wait,response_s=response,total_response_s=wait+response,tie_sha256=route_tie(q,route)))
            if not opts:continue
            best=min(opts,key=lambda x:(x['total_response_s'],x['tie_sha256']))
            slack=(q['deadline_ns']-s['now_ns'])/1e9-best['total_response_s']
            jobs.append(dict(request_id=q['request_id'],slack_s=slack,best_route=best['route'],total_response_s=best['total_response_s'],route_options=opts))
        byid={q['request_id']:q for q in s['queue']}
        jobs.sort(key=lambda x:(x['slack_s'],*tie(byid[x['request_id']])))
        return free,releases,remaining,jobs

    def __call__(self,s):
        q=s['queue']
        if len({x['request_id'] for x in q})!=len(q) or any(x['task'] not in ('C','D') or x['scheduled_arrival_ns']>s['now_ns'] or x['queue_entry_ns']>s['now_ns'] for x in q):raise ValueError('Invalid public queue')
        free,releases,remaining,jobs=self.estimates(s)
        action=dict(kind='RESOURCE_WAIT');skipped=[]
        if free:
            for j in jobs:
                if self.mode=='BAND_LSF_DROP' and j['slack_s']<0:
                    action=dict(kind='DROP',request_id=j['request_id'],reason='PUBLIC_PREDICTED_SLO_VIOLATION');break
                if j['best_route'] in free:
                    action=dict(kind='DISPATCH',request_id=j['request_id'],route=j['best_route']);break
                skipped.append(j['request_id'])
        record=dict(time_ns=s['now_ns'],action=copy.deepcopy(action),mode=self.mode,free_routes=free,release_estimates_s=releases,owner_estimates=remaining,ranked_jobs=[{k:v for k,v in j.items() if k!='route_options'} for j in jobs],selected_options=next((j['route_options'] for j in jobs if j['request_id']==action.get('request_id')),[]),skipped_busy_best=skipped,future_information=False,new_NN_execution=False,rolling_horizon=False,full_Band_runtime=False,window='all visible queued requests',tie='planned arrival/ordinal/id; route SHA256',version=VERSION)
        if action['kind']=='RESOURCE_WAIT':self.wait_calls.append(dict(public_state=copy.deepcopy(s),**record))
        else:self.calls.append(record)
        return action
