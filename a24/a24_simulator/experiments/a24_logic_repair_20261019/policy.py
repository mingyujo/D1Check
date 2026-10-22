"""Versioned logic repair: same 36x48 representation and frozen NN contract."""
import copy,math
from common_transfer import np,NS,tie,ACTIONS,WIDTH
from policy_repair import Policy as OldPolicy
from .forecast import predict_actions

class Policy(OldPolicy):
    def encode(self,s):
        q=s['queue'];edf=sorted(q,key=lambda j:(j['deadline_ns'],*tie(j)));fifo=sorted(q,key=tie)
        chosen={j['request_id']:j for j in edf[:4]+fifo[:1]}
        for task in ('C','D'):
            for p in ('U','N'):
                a=[j for j in edf if j['task']==task and j['priority']==p]
                if a:chosen[a[0]['request_id']]=a[0]
        for j in edf:
            if len(chosen)>=8:break
            chosen[j['request_id']]=j
        chosen=sorted(chosen.values(),key=lambda j:(j['deadline_ns'],*tie(j)))[:8];visible={j['request_id']:j for j in chosen}
        for j in edf:
            if len(visible)>=32:break
            visible[j['request_id']]=j
        vectors={(j['request_id'],r):self.nominal.vector(j,r,s) for j in [*visible.values(),*s['owners']] for r in ('CPU','GPU')}
        free=[r for r in ('CPU','GPU') if sum(o['route']==r for o in s['owners'])<(3 if r=='CPU' else 1)]
        actions=[dict(kind='DISPATCH',request_id=j['request_id'],route=r) for j in chosen for r in free]
        actions.extend([dict(kind='WAIT',wait_ns=d) for d in (20_000_000,50_000_000)])
        if s['owners']:actions.append(dict(kind='WAIT_EVENT',max_wait_ns=500_000_000))
        X=np.zeros((ACTIONS,WIDTH),np.float32);mask=np.zeros(ACTIONS,bool);scores=np.zeros(ACTIONS,np.float32);forecasts=predict_actions(s,actions,list(visible.values()),vectors,self.physics,self.case)
        sensor=s['sensor'];now=s['now_ns']/NS;T=sensor['temperature_c']
        for i,(a,f) in enumerate(zip(actions,forecasts)):
            c=f['cost']
            score=c[0]/.35+c[1]+12*c[2]+6*c[3]+3*c[4];scores[i]=score
            j=visible[a['request_id']] if a['kind']=='DISPATCH' else edf[0];route=a.get('route','CPU');vec=vectors[j['request_id'],route];ttl=max(.05,(j['deadline_ns']-j['scheduled_arrival_ns'])/NS)
            thermal=sensor.get('heat',[0.,0.]);v=sensor.get('v',[0.,0.,0.]);z=sensor.get('z',[0.,0.,0.])
            row=[1.,float(a['kind']=='DISPATCH'),float(a['kind']=='WAIT'),float(a['kind']=='WAIT_EVENT'),float(route=='CPU'),float(route=='GPU'),float(j['task']=='C'),float(j['priority']=='U'),(now-j['scheduled_arrival_ns']/NS)/10,(j['deadline_ns']/NS-now)/10,sum(vec)/2,sum(vec[:2 if j['task']=='C' else 3])/2,ttl/10,len(q)/32,sum(x['priority']=='U' for x in q)/32,len(s['owners'])/4,float('CPU' in free),float('GPU' in free),(T-26)/10,sensor['shared_z'],*c,(f['AP_end']-26)/10,(f['peak']-26)/10,(f['H_s']-now)/30,score/10,a.get('wait_ns',0)/NS,s['wait_used_ns']/NS/max(1,self.case['supply_stop_s']-35),sum(o['route']=='CPU' for o in s['owners'])/3,float(self.physics.profile=='UNION'),float(self.physics.profile=='S26_STYLE'),*thermal,*v,*z,sensor['increment_so_far']/max(1,self.case['n']*.35),self.physics.speed(T,'CPU',1,j['task']),self.physics.speed(T,'GPU',1,j['task']),len(visible)/32,float(f['capped']),f['steps']/800]
            assert len(row)==WIDTH,len(row)
            X[i]=[x if abs(x)<=5 else math.copysign(5+math.log1p(abs(x)-5),x) for x in row];mask[i]=True
        return dict(x=X,mask=mask,scores=scores,forecasts=forecasts),actions
    def __call__(self,s):
        if self.mode.startswith(('FIFO','EDF')):return super().__call__(s)
        bank,actions=self.encode(s)
        if self.learner:
            i,frame=self.learner.choose(bank,self.collect);frame['time_ns']=s['now_ns'];self.frames.append(frame)
        else:
            i=min(range(len(actions)),key=lambda i:(bank['scores'][i],i));teacher=np.zeros(ACTIONS,bool);teacher[i]=True;a=actions[i]
            group=('WAIT_EVENT' if a['kind']=='WAIT_EVENT' else 'WAIT' if a['kind']=='WAIT' else next(j for j in s['queue'] if j['request_id']==a['request_id'])['task']+'_'+a['route'])
            self.frames.append(dict(**{k:bank[k] for k in ('x','mask','scores')},index=i,time_ns=s['now_ns'],teacher_mask=teacher,group=group))
        a=copy.deepcopy(actions[i]);self.calls.append(dict(time_ns=s['now_ns'],action=a,chosen=i,actions=actions,x=bank['x'].tolist(),mask=bank['mask'].tolist(),forecast_scores=bank['scores'].tolist(),forecasts=bank['forecasts'],future_information=False,post_NN_override=False));return a
