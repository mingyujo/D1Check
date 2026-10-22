"""Fresh public slot-aware representation; no post-NN deadline protection."""
import copy,math
from common_transfer import np,NS,tie,ACTIONS,WIDTH

class Policy:
    def __init__(self,nominal,physics,case,mode,learner=None,collect=False):
        self.nominal=nominal;self.physics=physics;self.case=case;self.mode=mode;self.learner=learner;self.collect=collect;self.frames=[];self.calls=[]
    def encode(self,s):
        q=s['queue'];now=s['now_ns']/NS;T=s['sensor']['temperature_c'];owners=s['owners'];slots=self.physics.cpu_slots
        free=[r for r in ('CPU','GPU') if sum(o['route']==r for o in owners)<(slots if r=='CPU' else 1)]
        due=lambda j:(j['deadline_ns'],*tie(j));edf=sorted(q,key=due);fifo=sorted(q,key=tie);chosen={}
        for a in (edf[:8],fifo[:8]):
            for j in a:chosen[j['request_id']]=j
        for j in edf:
            if len(chosen)>=16:break
            chosen[j['request_id']]=j
        chosen=sorted(chosen.values(),key=due);lookup={j['request_id']:j for j in chosen}
        v={(j['request_id'],r):self.nominal.vector(j,r,s) for j in [*q,*owners] for r in ('CPU','GPU')}
        loads={r:sum(sum(v[o['request_id'],r][o['stage']:])-min(v[o['request_id'],r][o['stage']],o['public_progress_s']) for o in owners if o['route']==r) for r in ('CPU','GPU')}
        def profile(j,r):
            vec=v[j['request_id'],r];f=self.physics.speed(T,r,1)/(1+self.physics.beta*max(0,sum(o['route']=='CPU' and o['stage']==1 for o in owners)) if r=='CPU' else 1)
            duration=sum(vec)-vec[1]+vec[1]/f;response=sum(vec[:2 if j['task']=='C' else 3])-vec[1]+vec[1]/f
            power=self.physics.solo[('classification' if j['task']=='C' else 'detection')+'_'+r]
            energy=power*duration
            return duration,response,energy
        backlog=sum(min(profile(j,r)[0] for r in ('CPU','GPU')) for j in q)
        actions=[dict(kind='DISPATCH',request_id=j['request_id'],route=r) for j in chosen for r in free]
        if s['wait_used_ns']+.05*NS<=12*NS:actions.append(dict(kind='WAIT',wait_ns=50_000_000))
        if owners and s['wait_used_ns']<12*NS:actions.append(dict(kind='WAIT_EVENT',max_wait_ns=min(500_000_000,12*NS-s['wait_used_ns'])))
        X=np.zeros((ACTIONS,WIDTH),np.float32);mask=np.zeros(ACTIONS,bool);scores=np.zeros(ACTIONS,np.float32)
        for i,a in enumerate(actions):
            j=lookup[a['request_id']] if a['kind']=='DISPATCH' else edf[0];r=a.get('route',free[0]);other='GPU' if r=='CPU' else 'CPU'
            duration,response,energy=profile(j,r);alt=profile(j,other);ttl=max(.05,(j['deadline_ns']-j['scheduled_arrival_ns'])/NS);slack=j['deadline_ns']/NS-now-response
            age=max(0,now-j['scheduled_arrival_ns']/NS);weight=2. if j['priority']=='U' else 1.
            # Local public heuristic; no claim that this is a global optimum.
            score=energy/.35+.25*duration+8*weight*max(0.,-slack)/ttl+2*weight*float(slack<0)-.3*weight*age/ttl
            if a['kind']!='DISPATCH':score=4+backlog/(slots+1)+s['wait_used_ns']/NS
            row=[1.,float(j['task']=='C'),float(r=='CPU'),float(r=='GPU'),float(a['kind']!='DISPATCH'),float(j['priority']=='U'),age/10,(j['deadline_ns']/NS-now)/10,response/2,duration/2,weight/max(.01,duration)/5,len(q)/24,sum(jj['priority']=='U' for jj in q)/24,float('CPU' in free),float('GPU' in free),(T-26)/10,s['sensor']['shared_z'],self.physics.speed(T,'CPU',1),self.physics.speed(T,'GPU',1),len(owners)/(slots+1),a.get('wait_ns',0)/NS,s['wait_used_ns']/(12*NS),slots/3,energy/.35,float(slack>=0),max(0.,-slack)/ttl,alt[1]/ttl,backlog/10,score/10,loads['CPU']/10,loads['GPU']/10,sum(jj['task']=='C' for jj in q)/24,alt[1]/2,alt[0]/2,alt[2]/.35,self.physics.beta,self.physics.c.thermal_resistance/12,(alt[2]-energy)/.35,sum(o['route']=='CPU' for o in owners)/3,s['sensor']['increment_so_far']/(self.case['n']*.35),next(k for k,x in enumerate(edf) if x['request_id']==j['request_id'])/max(1,len(q)-1),next(k for k,x in enumerate(fifo) if x['request_id']==j['request_id'])/max(1,len(q)-1),float(a['kind']=='WAIT_EVENT'),sum(o['route']=='CPU' and o['stage']==1 for o in owners)/3,backlog/max(1,slots),energy*max(0,T-26)/3,loads[r]/10,len(q)/(slots+1)]
            assert len(row)==WIDTH
            X[i]=[x if abs(x)<=5 else math.copysign(5+math.log1p(abs(x)-5),x) for x in row];mask[i]=True;scores[i]=score
        return dict(x=X,mask=mask,scores=scores),actions
    def __call__(self,s):
        if self.mode.startswith(('FIFO','EDF')):
            # Direct baseline avoids constructing unused NN/teacher features.
            # Request and route order are identical to the encoded definition.
            first=min(s['queue'],key=tie if self.mode.startswith('FIFO') else lambda j:(j['deadline_ns'],*tie(j)))
            priority=('CPU','GPU') if self.mode.endswith('CPU') else ('GPU','CPU')
            free=[r for r in priority if sum(o['route']==r for o in s['owners'])<(self.physics.cpu_slots if r=='CPU' else 1)]
            a=dict(kind='DISPATCH',request_id=first['request_id'],route=free[0]);self.calls.append(dict(time_ns=s['now_ns'],action=copy.deepcopy(a),direct_baseline=True));return a
        bank,actions=self.encode(s)
        if self.mode.startswith(('FIFO','EDF')):
            first=min(s['queue'],key=tie if self.mode.startswith('FIFO') else lambda j:(j['deadline_ns'],*tie(j)))
            priority=('CPU','GPU') if self.mode.endswith('CPU') else ('GPU','CPU')
            legal=[i for i,a in enumerate(actions) if a['kind']=='DISPATCH' and a['request_id']==first['request_id']]
            i=min(legal,key=lambda i:priority.index(actions[i]['route']));frame=None
        elif self.learner:
            i,frame=self.learner.choose(bank,self.collect);frame['time_ns']=s['now_ns'];self.frames.append(frame)
        else:
            legal=[i for i,a in enumerate(actions) if a['kind']=='DISPATCH'];i=min(legal,key=lambda i:(bank['scores'][i],i));a=actions[i];j=next(j for j in s['queue'] if j['request_id']==a['request_id'])
            teacher=np.zeros(ACTIONS,bool);teacher[i]=True
            frame=dict(**bank,index=i,time_ns=s['now_ns'],teacher_mask=teacher,group=j['task']+'_'+a['route']);self.frames.append(frame)
        a=copy.deepcopy(actions[i]);self.calls.append(dict(time_ns=s['now_ns'],action=a,chosen=i,actions=actions,x=bank['x'].tolist(),mask=bank['mask'].tolist(),forecast_scores=bank['scores'].tolist(),future_information=False,post_NN_override=False));return a
