"""Only urgent WAIT deadline mask is configurable; every other baseline line retained."""
import copy
import math
import numpy as np
from dynamics import NS,advance_jobs,objectives,weighted

CAP=8;ACTIONS=19;WIDTH=32


def tie(q):return q['scheduled_arrival_ns'],q['ordinal'],q['request_id']


class GuardController:
    def __init__(self,nominal,physics,case,mode,learner=None,collect=False,deadline_guard=True):
        self.nominal,self.physics,self.case,self.mode=nominal,physics,case,mode
        self.learner,self.collect=learner,collect
        self.deadline_guard=deadline_guard
        self.waited=set();self.wait_per_head={};self.turn='C';self.calls=[];self.frames=[]

    def __call__(self,state):
        now=state['now_ns']/NS;queue=state['queue'];busy={o['route'] for o in state['owners']}
        free=[r for r in ('CPU','GPU') if r not in busy]
        if not queue or not free:return dict(kind='RESOURCE_WAIT')
        vectors={(q['request_id'],r):self.nominal.vector(q,r,state) for q in [*queue,*state['owners']] for r in ('CPU','GPU')}
        def occurrence(q,r):return sum(vectors[q['request_id'],r])/self.physics.speed(state['sensor']['temperature_c'],r,1)
        mean_occ=np.mean([occurrence(x,y) for x in queue for y in free])
        def atc(q,r):
            dur=occurrence(q,r);slack=q['deadline_ns']/NS-now-dur
            return math.log((2 if q['priority']=='U' else 1)/max(.001,dur))-max(0.,slack)/max(.2,2*mean_occ)
        head=min(queue,key=tie)
        # Shared admission coalescing for every baseline and every neural actor.
        if len(queue)==1 and not busy and head['request_id'] not in self.waited and state['wait_used_ns']+50_000_000<=12*NS:
            if min(occurrence(head,r) for r in free)+.05< head['deadline_ns']/NS-now:
                self.waited.add(head['request_id']);action=dict(kind='WAIT',wait_ns=50_000_000)
                self.calls.append(dict(time_ns=state['now_ns'],action=action,common_coalescing=True,sensor=dict(state['sensor'])))
                return action
        # Union preserves EDF/FIFO/RR/ATC heads while bounding neural compute.
        edf=sorted(queue,key=lambda q:(q['deadline_ns'],*tie(q)))
        rr=min([q for q in queue if q['task']==self.turn] or queue,key=tie)
        ranked=sorted(queue,key=lambda q:max(atc(q,r) for r in free),reverse=True)
        selected={q['request_id']:q for q in [*edf[:4],head,rr,*ranked[:2]]}
        chosen=sorted(selected.values(),key=lambda q:(q['deadline_ns'],*tie(q)))
        if len(chosen)>CAP:raise ValueError('Candidate union bound')
        actions=[]
        for q in chosen:
            for r in free:actions.append(dict(kind='DISPATCH',request_id=q['request_id'],route=r))
        for wait in (.05,.2,.5):
            feasible=(not self.deadline_guard) or all(q['priority']!='U' or now+wait+min(occurrence(q,r) for r in ('CPU','GPU'))<=q['deadline_ns']/NS for q in queue)
            if feasible and state['wait_used_ns']/NS+wait<=12 and self.wait_per_head.get(head['request_id'],0.)+wait<=1.5:
                actions.append(dict(kind='WAIT',wait_ns=round(wait*NS)))
        exact=self.mode in ('EXACT','RL','APPROX')
        X=np.zeros((ACTIONS,WIDTH),np.float32);mask=np.zeros(ACTIONS,bool);scores=np.zeros(ACTIONS,np.float32)
        forecasts=[];lookup={q['request_id']:q for q in chosen}
        owner_remaining=[]
        for o in state['owners']:
            v=vectors[o['request_id'],o['route']]
            owner_remaining.append(dict(request_id=o['request_id'],task=o['task'],route=o['route'],stage=o['stage'],
                remaining=max(.002,v[o['stage']]-o['public_progress_s']),vector=v))
        for i,a in enumerate(actions):
            q=lookup[a['request_id']] if a['kind']=='DISPATCH' else head
            r=a.get('route',free[0]);v=vectors[q['request_id'],r]
            cold_response=sum(v[:2 if q['task']=='C' else 3]);cold=sum(v)
            forecast=self.preview(state,chosen,owner_remaining,vectors,a) if exact else None
            forecasts.append(forecast);mask[i]=True
            costs=forecast['costs'] if forecast else [0.]*5
            scores[i]=weighted(costs) if forecast else 0.
            f=state['sensor'];temp=f['temperature_c']
            X[i]=np.clip([1.,float(q['task']=='C'),float(r=='CPU'),float(r=='GPU'),float(a['kind']=='WAIT'),
                float(q['priority']=='U'),(now-q['scheduled_arrival_ns']/NS)/10.,(q['deadline_ns']/NS-now)/10.,
                cold_response/2.,cold/2.,atc(q,r)/5.,len(queue)/24.,sum(x['priority']=='U' for x in queue)/24.,
                float('CPU' in free),float('GPU' in free),(temp-26.)/10.,f['shared_z'],
                self.physics.speed(temp,'CPU',1),self.physics.speed(temp,'GPU',1),len(busy)/2.,
                a.get('wait_ns',0)/NS,state['wait_used_ns']/(12*NS),self.physics.solo[('classification' if q['task']=='C' else 'detection')+'_'+r],
                *costs,(forecast['peak']-26.)/10. if forecast else 0.,
                (forecast['candidate_response']-now)/5. if forecast and forecast['candidate_response'] is not None else 0.,
                (self.case['service_stop_s']-now)/100.,f['increment_so_far']/(self.case['n']*.35)],-10,10)
        bank=dict(x=X,mask=mask,scores=scores)
        if self.mode=='RL':
            index,frame=self.learner.choose(bank,self.collect)
            frame['time_ns']=state['now_ns'];self.frames.append(frame)
        elif self.mode=='EXACT':index=min(range(len(actions)),key=lambda i:(scores[i],i))
        elif self.mode=='APPROX':
            # Same horizon/jobs/thermal/deadline score, replace only its energy
            # head with nominal additive work without history/shared/DVFS cost.
            index=min(range(len(actions)),key=lambda i:(weighted([
                forecasts[i]['nominal_additive_energy']/(self.case['n']*.35),*forecasts[i]['costs'][1:]]),i))
        else:
            if self.mode=='EDF':target=edf[0];route=free[0]
            elif self.mode=='FIFO':target=head;route=free[0]
            elif self.mode=='RR':target=rr;route=free[0]
            elif self.mode=='ATC':target,route=max(((q,r) for q in chosen for r in free),key=lambda x:(atc(*x),-x[0]['ordinal'],x[1]=='CPU'))
            else:raise ValueError('Unknown policy')
            index=next(i for i,a in enumerate(actions) if a['kind']=='DISPATCH' and a['request_id']==target['request_id'] and a['route']==route)
        if not mask[index]:raise ValueError('Masked action')
        action=actions[index]
        if action['kind']=='DISPATCH':self.turn='D' if lookup[action['request_id']]['task']=='C' else 'C'
        else:self.wait_per_head[head['request_id']]=self.wait_per_head.get(head['request_id'],0.)+action['wait_ns']/NS
        self.calls.append(dict(time_ns=state['now_ns'],action=copy.deepcopy(action),chosen=index,actions=actions,
            x=X.tolist(),mask=mask.tolist(),forecast_scores=scores.tolist(),forecasts=forecasts,
            sensor=dict(state['sensor']),common_coalescing=False,
            nominal_vectors={rid+'|'+route:v for (rid,route),v in vectors.items()} if exact else None,
            nominal_owners=owner_remaining if exact else None,nominal_ready=chosen if exact else None,
            fixed_ATC_prior_logit=0.,future_actual_work_used=False,future_arrivals_used=False))
        return copy.deepcopy(action)

    def preview(self,public,ready,initial_owners,vectors,first):
        """Complete currently visible jobs with a common EDF continuation only.

        Real and nominal work differ; the transition and objective do not.
        Future arrivals and current latent remaining work are absent.
        """
        now=public['now_ns']/NS;start=now;end=self.case['drain_stop_s'];state={k:public['sensor'][k] for k in ('temperature_c','shared_z')}
        initial_T=state['temperature_c'];peak=public['sensor']['peak_c'];energy=area=0.
        approximate=sum(self.physics.solo[('classification' if j['task']=='C' else 'detection')+'_'+j['route']]*(j['remaining']+sum(j['vector'][j['stage']+1:])) for j in initial_owners)
        jobs=copy.deepcopy(initial_owners);pending={q['request_id']:q for q in ready}
        answers={o['request_id']:o['response_ns']/NS for o in public['owners'] if o.get('response_ns') is not None}
        allrows={q['request_id']:q for q in [*ready,*public['owners']]}
        def settle():
            for j in list(jobs):
                while j['remaining']<=1e-11:
                    if (j['task']=='C' and j['stage']==1) or (j['task']=='D' and j['stage']==2):answers[j['request_id']]=now
                    j['stage']+=1
                    if j['stage']==5:jobs.remove(j);break
                    j['remaining']=j['vector'][j['stage']]
        def dispatch(q,r):
            nonlocal approximate
            v=vectors[q['request_id'],r]
            approximate+=sum(v)*self.physics.solo[('classification' if q['task']=='C' else 'detection')+'_'+r]
            jobs.append(dict(request_id=q['request_id'],task=q['task'],route=r,stage=0,remaining=v[0],vector=v))
            pending.pop(q['request_id']);state['shared_z']=1.;settle()
        wait_until=start+first.get('wait_ns',0)/NS
        if first['kind']=='DISPATCH':dispatch(pending[first['request_id']],first['route'])
        steps=0
        while now<end-1e-10:
            settle()
            if now>=wait_until:
                while pending and len(jobs)<2:
                    free=[r for r in ('CPU','GPU') if r not in {j['route'] for j in jobs}]
                    q=min(pending.values(),key=lambda q:(q['deadline_ns'],*tie(q)))
                    r=min(free,key=lambda r:sum(vectors[q['request_id'],r])/self.physics.speed(state['temperature_c'],r,1))
                    dispatch(q,r)
            if not jobs and not pending:
                dt=end-now
            else:
                dt=min(self.physics.c.tick_s,end-now)
                if now<wait_until:dt=min(dt,wait_until-now)
                for j in jobs:dt=min(dt,max(1e-9,j['remaining']/self.physics.speed(state['temperature_c'],j['route'],j['stage'])))
            state,terms=advance_jobs(self.physics,state,jobs,dt)
            energy+=terms['increment'];area+=terms['temperature_area'];peak=max(peak,terms['peak']);now+=dt;steps+=1
            if steps>5000:raise ValueError('Nominal continuation cap')
        settle()
        passive=self.physics.c.idle_c*(end-start)+(initial_T-self.physics.c.idle_c)*self.physics.c.thermal_tau_s*(-math.expm1(-(end-start)/self.physics.c.thermal_tau_s))
        heat=max(0.,area-passive);tail=self.physics.shared*self.physics.c.idle_tail_s*state['shared_z']
        labelled=[dict(priority=q.get('priority','N'),arrival_s=q.get('scheduled_arrival_ns',public['now_ns'])/NS,
            deadline_s=q.get('deadline_ns',round(end*NS))/NS,response_s=answers.get(rid)) for rid,q in allrows.items()]
        costs=objectives(energy+tail,heat,peak,labelled,self.case['n'])
        return dict(costs=costs,energy=energy,nominal_additive_energy=approximate,heat_area=heat,peak=peak,
            candidate_response=answers.get(first.get('request_id')),nominal_only=True,visible_jobs=len(allrows),
            nominal_unfinished=sum(x['response_s'] is None for x in labelled),
            current_temperature_c=initial_T,current_shared_z=public['sensor']['shared_z'],
            integration='SAME_dynamics.advance_jobs',future_arrivals_used=False)
