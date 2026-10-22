"""Public teacher, explicit ranks, optional event wait and thermal lookahead."""
import copy,math
from common_transfer import PackingEncoder,tie,np,NS,WIDTH,ACTIONS
from transfer_rolling import predict
class Policy:
    def __init__(self,nominal,physics,case,learner=None,collect=False,stage=1,demo=False):
        self.base=PackingEncoder(nominal,physics,case);self.nominal=nominal;self.physics=physics;self.case=case;self.learner=learner;self.collect=collect;self.stage=stage;self.demo=demo;self.calls=[];self.frames=[];self.last_event=None
    def encode(self,state):
        bank,actions,chosen,details,fluid=self.base.encode(state);q=state['queue'];due=lambda q:(q['deadline_ns'],*tie(q));edf=sorted(q,key=due);fifo=sorted(q,key=tie)
        X=np.zeros((ACTIONS,WIDTH),np.float32);mask=np.zeros(ACTIONS,bool);scores=np.zeros(ACTIONS,np.float32)
        X[:35,:40]=bank['x'];mask[:35]=bank['mask'];scores[:35]=bank['scores'];base_count=len(actions);rolling=[]
        if self.stage>=3 and state['owners'] and state['wait_used_ns']<12*NS:
            head=min(q,key=tie);remaining=min(12*NS-state['wait_used_ns'],int(1.5*NS))
            if remaining>0:
                actions.append(dict(kind='WAIT_EVENT',max_wait_ns=remaining));i=len(actions)-1;mask[i]=True
                # Reuse the public WAIT representation, without an actual future time.
                first_wait=next((j for j,a in enumerate(actions[:-1]) if a['kind']=='WAIT'),None)
                if first_wait is not None:X[i,:40]=X[first_wait,:40]
                else:X[i,:40]=X[0,:40];X[i,4]=1.;X[i,20]=0.
                X[i,4]=1.;X[i,20]=0.;X[i,42]=1.;scores[i]=0.
        for i,a in enumerate(actions):
            if a['kind']=='DISPATCH':
                rid=a['request_id'];X[i,40]=next(j for j,x in enumerate(edf) if x['request_id']==rid)/max(1,len(edf)-1);X[i,41]=next(j for j,x in enumerate(fifo) if x['request_id']==rid)/max(1,len(fifo)-1)
        if self.stage>=4:
            vectors={(j['request_id'],r):self.nominal.vector(j,r,state) for j in [*q,*state['owners']] for r in ('CPU','GPU')}
            for i,a in enumerate(actions):
                p=predict(state,chosen,vectors,self.physics,a);rolling.append(p)
                X[i,43:48]=[p['total_J']/max(.35,p['visible']*.35),p['heat_Cs']/max(3.,p['visible']*3.),p['late_U'],p['late_N'],p['duration_s']/10.]
        return dict(x=X,mask=mask,scores=scores),actions,chosen,details,fluid,rolling,base_count
    def __call__(self,state):
        # Identical shared admission as FIFO/EDF/parent; not a NN deadline guard.
        q=state['queue'];head=min(q,key=tie);busy={o['route'] for o in state['owners']};free=[r for r in ('CPU','GPU') if r not in busy]
        if len(q)==1 and not busy and head['request_id'] not in self.base.waited and state['wait_used_ns']+50_000_000<=12*NS:
            duration=min(sum(self.nominal.vector(head,r,state))/self.physics.speed(state['sensor']['temperature_c'],r,1) for r in free)
            if duration+.05<(head['deadline_ns']-state['now_ns'])/NS:
                self.base.waited.add(head['request_id']);a=dict(kind='WAIT',wait_ns=50_000_000);self.calls.append(dict(time_ns=state['now_ns'],action=a,common_coalescing=True));return a
        bank,actions,chosen,details,fluid,rolling,base_count=self.encode(state)
        if self.demo or self.learner is None:
            legal=[i for i,a in enumerate(actions) if a['kind']=='DISPATCH'];feasible=[i for i in legal if details[i]['feasible']]
            index=max(feasible,key=lambda i:(bank['x'][i,10],-i)) if feasible else min(legal,key=lambda i:(bank['scores'][i],i))
            a=actions[index];target=next(q for q in q if q['request_id']==a['request_id'])
            compatible=np.array([x['kind']=='DISPATCH' and x['route']==a['route'] and next(q for q in state['queue'] if q['request_id']==x['request_id'])['task']==target['task'] and next(q for q in state['queue'] if q['request_id']==x['request_id'])['priority']==target['priority'] and next(q for q in state['queue'] if q['request_id']==x['request_id'])['deadline_ns']==target['deadline_ns'] for x in actions]+[False]*(ACTIONS-len(actions)))
            frame=dict(**bank,index=index,time_ns=state['now_ns'],teacher_mask=compatible,group=target['task']+'_'+a['route'])
        else:
            index,frame=self.learner.choose(bank,self.collect);frame['time_ns']=state['now_ns'];a=actions[index]
        self.frames.append(frame)
        if a['kind']=='WAIT':self.base.wait_per_head[head['request_id']]=self.base.wait_per_head.get(head['request_id'],0.)+a['wait_ns']/NS
        self.calls.append(dict(time_ns=state['now_ns'],action=copy.deepcopy(a),chosen=index,actions=copy.deepcopy(actions),x=bank['x'].tolist(),mask=bank['mask'].tolist(),forecast_scores=bank['scores'].tolist(),common_coalescing=False,stage=self.stage,base_action_count=base_count,rolling=rolling,packing_details=details,packing_candidates=chosen,future_actual_work_used=False,future_arrivals_used=False,fixed_ATC_prior_logit=0.,post_NN_override=False))
        return copy.deepcopy(a)
