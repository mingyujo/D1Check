"""Public semantic candidates and queue/alternative-route observations."""
import copy,math,numpy as np
from fluid import VisibleFluid
CAP=16;ACTIONS=35;WIDTH=40;NS=1_000_000_000
def tie(q):return q['scheduled_arrival_ns'],q['ordinal'],q['request_id']

class PackingEncoder:
    def __init__(self,nominal,physics,case,learner=None,collect=False,expert=None):
        self.nominal,self.physics,self.case,self.learner,self.collect,self.expert=nominal,physics,case,learner,collect,expert
        self.waited=set();self.wait_per_head={};self.frames=[];self.calls=[];self.teacher_masks=[]
    def encode(self,state):
        now=state['now_ns']/NS;q=state['queue'];busy={o['route'] for o in state['owners']};free=[r for r in ('CPU','GPU') if r not in busy];T=state['sensor']['temperature_c']
        vectors={(j['request_id'],r):self.nominal.vector(j,r,state) for j in [*q,*state['owners']] for r in ('CPU','GPU')};fluid=VisibleFluid(state,vectors,self.physics)
        due=lambda j:(j['deadline_ns'],*tie(j));selected={}
        # Up to four public deadline representatives per task/priority class.
        for task in ('C','D'):
            for priority in ('U','N'):
                for fit in (True,False):
                    local=sorted([j for j in q if j['task']==task and j['priority']==priority and fluid.feasible[j['request_id']]==fit],key=due)
                    for j in local[:1]+local[-1:]:selected[j['request_id']]=j
        for j in sorted(q,key=due):
            if len(selected)>=CAP:break
            selected[j['request_id']]=j
        chosen=sorted(selected.values(),key=due);assert len(chosen)<=CAP
        actions=[dict(kind='DISPATCH',request_id=j['request_id'],route=r) for j in chosen for r in free];head=min(q,key=tie)
        for wait in (.05,.2,.5):
            if state['wait_used_ns']/NS+wait<=12. and self.wait_per_head.get(head['request_id'],0.)+wait<=1.5:actions.append(dict(kind='WAIT',wait_ns=round(wait*NS)))
        X=np.zeros((ACTIONS,WIDTH),np.float32);mask=np.zeros(ACTIONS,bool);scores=np.zeros(ACTIONS,np.float32);lookup={j['request_id']:j for j in chosen};details=[]
        avg=sum(fluid.profiles[j['request_id']][r]['duration'] for j in q for r in free)/(len(q)*len(free));feasible_fraction=sum(fluid.feasible.values())/len(q)
        for i,a in enumerate(actions):
            j=lookup[a['request_id']] if a['kind']=='DISPATCH' else head;r=a.get('route',free[0]);other='GPU' if r=='CPU' else 'CPU';v=fluid.profiles[j['request_id']][r];alt=fluid.profiles[j['request_id']][other];slack=j['deadline_ns']/NS-now-v['response'];ttl=(j['deadline_ns']-j['scheduled_arrival_ns'])/NS
            atc=math.log((2 if j['priority']=='U' else 1)/max(.001,v['duration']))-max(0,j['deadline_ns']/NS-now-v['duration'])/max(.2,2*avg)
            first=fluid.first(j,r) if a['kind']=='DISPATCH' else dict(regret=fluid.rate*a['wait_ns']/NS,finish_increase=a['wait_ns']/NS)
            gpu_fraction=fluid.base['gpu_counts'][j['task']]/max(1,fluid.groups[j['task']]['n']);sensor=state['sensor'];row=[1.,float(j['task']=='C'),float(r=='CPU'),float(r=='GPU'),float(a['kind']=='WAIT'),float(j['priority']=='U'),(now-j['scheduled_arrival_ns']/NS)/10.,(j['deadline_ns']/NS-now)/10.,v['response']/2.,v['duration']/2.,atc/5.,len(q)/24.,sum(jj['priority']=='U' for jj in q)/24.,float('CPU' in free),float('GPU' in free),(T-26)/10.,sensor['shared_z'],self.physics.speed(T,'CPU',1),self.physics.speed(T,'GPU',1),len(busy)/2.,a.get('wait_ns',0)/NS,state['wait_used_ns']/(12*NS),self.physics.solo[('classification' if j['task']=='C' else 'detection')+'_'+r],v['energy']/.35,float(slack>=0),max(0.,-slack)/max(.05,ttl),(alt['response']+fluid.owner_loads[other])/max(.05,ttl),feasible_fraction,first['regret']/.35,gpu_fraction,fluid.groups[j['task']]['n']/24.,fluid.groups['D' if j['task']=='C' else 'C']['n']/24.,alt['response']/2.,alt['duration']/2.,alt['energy']/.35,fluid.owner_loads['CPU']/2.,fluid.owner_loads['GPU']/2.,(alt['energy']-v['energy'])/.35,first['finish_increase']/2.,sensor['increment_so_far']/(self.case['n']*.35)]
            assert len(row)==WIDTH
            for k,x in enumerate(row):row[k]=x if abs(x)<=5 else math.copysign(5+math.log1p(abs(x)-5),x)
            X[i]=row;mask[i]=True;scores[i]=first['regret'];details.append(dict(first=first,feasible=slack>=0,public_task=j['task'],public_priority=j['priority'],public_class_feasible=fluid.feasible[j['request_id']]))
        return dict(x=X,mask=mask,scores=scores),actions,chosen,details,fluid
    def __call__(self,state):
        q=state['queue'];head=min(q,key=tie);busy={o['route'] for o in state['owners']};free=[r for r in ('CPU','GPU') if r not in busy]
        if self.expert is not None:target_action=self.expert(state)
        else:target_action=None
        if len(q)==1 and not busy and head['request_id'] not in self.waited and state['wait_used_ns']+50_000_000<=12*NS:
            duration=min(sum(self.nominal.vector(head,r,state))/self.physics.speed(state['sensor']['temperature_c'],r,1) for r in free)
            if duration+.05<(head['deadline_ns']-state['now_ns'])/NS:
                self.waited.add(head['request_id']);action=dict(kind='WAIT',wait_ns=50_000_000)
                if target_action is not None:assert target_action==action,'Same expert/public shared admission'
                self.calls.append(dict(time_ns=state['now_ns'],action=action,common_coalescing=True));return action
        bank,actions,chosen,details,fluid=self.encode(state)
        target_mask=None
        if target_action is not None:
            target=next(j for j in q if j['request_id']==target_action['request_id']);fit=fluid.feasible[target['request_id']]
            target_mask=np.array([a['kind']=='DISPATCH' and a['route']==target_action['route'] and d['public_task']==target['task'] and d['public_priority']==target['priority'] and d['public_class_feasible']==fit for a,d in zip(actions,details)]+[False]*(ACTIONS-len(actions)),bool)
            assert target_mask.any(),'Public class representation for every expert label'
            index=int(np.flatnonzero(target_mask)[0]);frame=dict(x=bank['x'].copy(),mask=bank['mask'].copy(),scores=bank['scores'].copy(),index=index,time_ns=state['now_ns'],teacher_mask=target_mask)
            self.frames.append(frame);self.teacher_masks.append(target_mask);action=target_action
        elif self.learner is not None:
            index,frame=self.learner.choose(bank,self.collect);frame['time_ns']=state['now_ns'];self.frames.append(frame);action=actions[index]
        else:
            legal=[i for i,a in enumerate(actions) if a['kind']=='DISPATCH'];feasible=[i for i in legal if details[i]['feasible']]
            index=max(feasible,key=lambda i:(bank['x'][i,10],-i)) if feasible else min(legal,key=lambda i:(bank['scores'][i],i));action=actions[index]
        if action['kind']=='WAIT':self.wait_per_head[head['request_id']]=self.wait_per_head.get(head['request_id'],0.)+action['wait_ns']/NS
        self.calls.append(dict(time_ns=state['now_ns'],action=copy.deepcopy(action),chosen=index,actions=actions,x=bank['x'].tolist(),mask=bank['mask'].tolist(),forecast_scores=bank['scores'].tolist(),common_coalescing=False,packing_details=details,packing_candidates=chosen,fluid_base=fluid.base,fluid_owners=fluid.owner_loads,fluid_groups=fluid.groups,full_public_queue_size=len(q),future_actual_work_used=self.expert is not None,future_arrivals_used=self.expert is not None,teacher_mask=target_mask.tolist() if target_mask is not None else None,fixed_ATC_prior_logit=0.,sensor=dict(state['sensor'])))
        return copy.deepcopy(action)
