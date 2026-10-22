"""Finite inherited-constant nested group calibration, with unchanged labels."""
import json,time,itertools,shutil,ctypes
from collections import defaultdict
import numpy as np
from scipy.optimize import minimize
from prepare import H,R,A,O,PREV,FIRST,TAIL,MODE01,read,write,sha,split
from thermal_model import segments,convolution,matrix,window_pairs,SCHEMA
def settings(m):return tuple(m.get(k) for k in ['schema','tau_fast_s','tau_slow_s','transport_s','tau_middle_s','robust_delta_C','hinge_strength','middle_enabled','context_enabled'])
def cls(x):return 'rise' if x>=.2-1e-10 else 'fall' if x<=-.2+1e-10 else 'stable'
class Memory(ctypes.Structure):
    _fields_=[('length',ctypes.c_ulong),('load',ctypes.c_ulong),('totalPhys',ctypes.c_ulonglong),('availPhys',ctypes.c_ulonglong),('totalPage',ctypes.c_ulonglong),('availPage',ctypes.c_ulonglong),('totalVirtual',ctypes.c_ulonglong),('availVirtual',ctypes.c_ulonglong),('availExtended',ctypes.c_ulonglong)]
def resources():
    m=Memory();m.length=ctypes.sizeof(m);assert ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m));assert m.availPhys>=1024**3,'RAM below 1GiB';assert shutil.disk_usage(R).free>=4*1024**3,'Disk below 4GiB'
class Study:
    def __init__(self,data):
        self.data=data;self.cases={c['session']:c for c in data['cases']};self.cache={};self.memo={};self.old={};self.count=0
        for folder in [FIRST,PREV,TAIL]:
            for line in (folder/'FIT_LEDGER.jsonl').read_text().splitlines():
                row=json.loads(line)
                if row['event']=='COMPLETE':
                    m=row['model'];self.old[(tuple(m['training_sessions']),settings(m))]=m
        for line in (MODE01/'FIT_LEDGER.jsonl').read_text().splitlines():
            row=json.loads(line)
            if row['event']=='COMPLETE':
                m=row['model'];key=(tuple(m['training_sessions']),m['tau_fast_s'],m['tau_slow_s'],m['transport_s'],m['idle_tau_ratio'],m['robust_delta_C'],m['hinge_strength'],m['context_enabled']);self.memo[key]=m
        self.previous_candidate_models_reused=len(self.memo)
        taus={10.,30.,60.,180.,1800.,5.,15.}
        for c in self.cases.values():
            ids=np.array([i for i,o in enumerate(c['observations']) if c['fit_window_s'][0]<=o['t']<=c['fit_window_s'][1]],int);obs=[c['observations'][i] for i in ids]
            self.cache[c['session']]={'conv':{t:convolution(c,segments(c),t) for t in taus},'indices':ids,'pairs':np.array(window_pairs(obs),int).reshape(-1,2),'truth':np.array([o['observed_c'] for o in obs]),'matrix':{}}
    def log(self,row):
        with (O/'FIT_LEDGER.jsonl').open('a',encoding='utf-8',newline='\n') as f:f.write(json.dumps(row,allow_nan=False,separators=(',',':'))+'\n')
    def design(self,sid,m):
        z=self.cache[sid];key=(m['schema'],m['tau_fast_s'],m['tau_slow_s'],m['transport_s'],m.get('tau_middle_s'),m.get('middle_enabled',True),m.get('context_enabled',True),m.get('idle_tau_ratio'))
        if key not in z['matrix']:z['matrix'][key]=matrix(self.cases[sid],z['conv'],m)
        return z['matrix'][key]
    def baseline(self,ids,inherited,label):
        key=(tuple(ids),settings(inherited));assert key in self.old,('missing frozen baseline',label)
        m=self.old[key];self.log({'event':'REUSE_PREVIOUS','id':label,'source_id':m['identity'],'training_sessions':ids});return m
    def fit(self,ids,inherited,ratio,delta,weight,label,context=True):
        key=(tuple(ids),inherited['tau_fast_s'],inherited['tau_slow_s'],inherited['transport_s'],ratio,delta,weight,context)
        if key in self.memo:self.log({'event':'REUSE_NEW','id':label,'source_id':self.memo[key]['identity']});return self.memo[key]
        resources();self.count+=1;assert self.count<=48;start=time.time();self.log({'event':'START','index':self.count,'id':label,'training_sessions':ids})
        try:
            m={'schema':SCHEMA,'tau_fast_s':inherited['tau_fast_s'],'tau_slow_s':inherited['tau_slow_s'],'transport_s':inherited['transport_s'],'idle_tau_ratio':ratio,'robust_delta_C':delta,'hinge_strength':weight,'context_enabled':context}
            xx=[];yy=[];levels=[];hinges=defaultdict(list)
            for sid in ids:
                c=self.cases[sid];z=self.cache[sid];x=self.design(sid,m)[z['indices']];y=z['truth']-c['initial_c'];pairs=z['pairs'];levels.append((x,y,(.75 if len(pairs) else 1.)/len(y)))
                if len(pairs):
                    i,j=pairs[:,0],pairs[:,1];dx=x[j]-x[i];dy=y[j]-y[i];w=np.sqrt(.25/len(pairs));xx.append(dx*w);yy.append(dy*w)
                    for d in ['rise','fall','stable']:
                        ix=[k for k,v in enumerate(dy) if cls(v)==d]
                        if ix:hinges[d].append(dx[ix])
            prior=np.zeros(11);prior[1]=1;xx.append(np.eye(11)*.01);yy.append(prior*.01);x=np.vstack(xx);y=np.concatenate(yy);gram=x.T@x;rhs=x.T@y
            hh=[];target=[];ww=[]
            for d,rows in hinges.items():
                for dx in rows:
                    w=weight*len(ids)/(3*len(rows)*len(dx))
                    if d=='stable':hh.extend([dx,-dx]);target.extend([np.full(len(dx),-.18)]*2);ww.extend([np.full(len(dx),w)]*2)
                    else:hh.append(dx if d=='rise' else -dx);target.append(np.full(len(dx),.22));ww.append(np.full(len(dx),w))
            hh=np.vstack(hh);target=np.concatenate(target);ww=np.concatenate(ww)
            lx=np.vstack([x for x,y,w in levels]);ly=np.concatenate([y for x,y,w in levels]);lw=np.concatenate([np.full(len(y),w) for x,y,w in levels])
            if not delta:gram+=lx.T@(lw[:,None]*lx);rhs+=lx.T@(lw*ly)
            def objective(theta):
                v=.5*theta@gram@theta-rhs@theta;g=gram@theta-rhs
                if delta:
                    e=lx@theta-ly;q=np.sqrt(1+(e/delta)**2);v+=np.sum(lw*delta**2*(q-1));g+=lx.T@(lw*e/q)
                r=np.maximum(0,target-hh@theta);v+=.5*np.sum(ww*r*r);g-=hh.T@(ww*r)
                return float(v),g
            lower=np.array([-2.,0.,0.]+[0.]*8);upper=np.array([2.,2.,2.]+[20.]*8)
            if not context:upper[2]=0
            old=self.baseline(ids,inherited,label+'/WARM_START');b=old['coefficients'];theta0=np.array([b[0],b[1],b[2],*b[3:7],*b[11:15]] if 'three' in old['schema'] else [b[0],b[1],0.,*b[2:6],*b[6:10]])
            result=minimize(objective,theta0,jac=True,method='L-BFGS-B',bounds=list(zip(lower,upper)),options={'maxiter':2000,'ftol':1e-13,'gtol':1e-8,'maxls':50})
            theta=result.x;grad=objective(theta)[1];pg=np.where(((theta<=lower+1e-7)&(grad>0))|((theta>=upper-1e-7)&(grad<0))|(upper==lower),0,grad)
            assert result.success and np.max(np.abs(pg))<1e-4,(result.message,float(np.max(np.abs(pg))))
            m.update(coefficients=theta.tolist(),coefficient_names=['background_offset_C','pre_trend_multiplier','initial_recovery_multiplier',*[f'{s}_{k}' for s in ['fast','slow'] for k in ['CC','CG','DC','CG_DC']]],identity=label,training_sessions=ids,training_groups=sorted({self.cases[s]['group'] for s in ids}),fresh_confirmation=False,not_physical_identification=True)
            self.memo[key]=m;self.log({'event':'COMPLETE','index':self.count,'id':label,'elapsed_s':time.time()-start,'model':m,'solver':{'message':str(result.message),'iterations':int(result.nit),'projected_gradient':float(np.max(abs(pg)))}});return m
        except BaseException as e:self.log({'event':'FAIL','index':self.count,'id':label,'error':repr(e),'automatic_retry':False});raise
    def predict(self,sid,m):return self.cases[sid]['initial_c']+self.design(sid,m)@np.array(m['coefficients'])
    def score(self,ids,m):
        rows=[]
        for sid in ids:
            z=self.cache[sid];pred=self.predict(sid,m)[z['indices']];y=z['truth'];conf={d:[] for d in ['rise','fall','stable']};delta=[]
            for i,j in z['pairs']:
                dy=y[j]-y[i];dp=pred[j]-pred[i];conf[cls(dy)].append(cls(dp)==cls(dy));delta.append(abs(dp-dy))
            rows.append({'session':sid,'MAE_C':float(np.mean(abs(pred-y))),'delta_MAE_C':float(np.mean(delta)) if delta else 0.,'direction':{d:{'n':len(v),'correct':int(sum(v))} for d,v in conf.items()}})
        return rows
    def select(self,ids,inherited,label):
        folds=split([self.cases[s] for s in ids]);rank=[]
        for candidate in [None,*itertools.product([.25,.5,1.],[0.,.15],[2.,8.])]:
            rows=[]
            for k,groups in enumerate(folds):
                train=[s for s in ids if self.cases[s]['group'] not in groups];test=[s for s in ids if self.cases[s]['group'] in groups];assert train and test
                m=self.baseline(train,inherited,f'{label}/BASE/INNER{k}') if candidate is None else self.fit(train,inherited,*candidate,f'{label}/R{candidate[0]}_D{candidate[1]}_W{candidate[2]}/INNER{k}')
                rows.extend(self.score(test,m))
            accuracy={d:100*sum(r['direction'][d]['correct'] for r in rows)/sum(r['direction'][d]['n'] for r in rows) for d in ['rise','fall','stable']}
            rank.append({'candidate':candidate,'MAE_C':float(np.mean([r['MAE_C'] for r in rows])),'P90_session_MAE_C':float(np.quantile([r['MAE_C'] for r in rows],.9)),'delta_MAE_C':float(np.mean([r['delta_MAE_C'] for r in rows])),'direction_accuracy_pct':accuracy,'balanced_direction_accuracy_pct':sum(accuracy.values())/3,'per_session':rows})
        base=rank[0]
        for r in rank:r['eligible']=bool(r['candidate'] is None or (r['MAE_C']<=base['MAE_C']+.005+1e-12 and r['P90_session_MAE_C']<=base['P90_session_MAE_C']+.01+1e-12 and r['delta_MAE_C']<=base['delta_MAE_C']+.01+1e-12 and r['direction_accuracy_pct']['rise']>=base['direction_accuracy_pct']['rise']-1e-10 and r['direction_accuracy_pct']['fall']>=base['direction_accuracy_pct']['fall']-1e-10 and r['direction_accuracy_pct']['stable']>=base['direction_accuracy_pct']['stable']-1-1e-10))
        chosen=min([r for r in rank if r['eligible']],key=lambda r:(-r['balanced_direction_accuracy_pct'],-min(r['direction_accuracy_pct'][d]-base['direction_accuracy_pct'][d] for d in ['rise','fall']),r['MAE_C'],r['delta_MAE_C'],abs(1-r['candidate'][0]) if r['candidate'] else 0,(r['candidate'][2],r['candidate'][1]) if r['candidate'] else (0,0)))
        return chosen['candidate'],rank
    def run(self):
        oof=[];ablations=[]
        for family in ['m8','old']:
            ids=sorted(s for s,c in self.cases.items() if c['family']==family)
            for k in [*range(5),'deployment']:
                groups=self.data['outer_groups'][family][k] if k!='deployment' else [];train=[s for s in ids if self.cases[s]['group'] not in groups];test=[s for s in ids if self.cases[s]['group'] in groups];inherited=self.data['inherited'][family][str(k)];label=f'{family}/{k}'
                candidate,rank=self.select(train,inherited,label)
                model=self.baseline(train,inherited,label+'/FALLBACK') if candidate is None else self.fit(train,inherited,*candidate,label+'/SELECTED')
                matched={}
                for name,ratio,context,weight in [('SAME_HEAT_COOL',1.,True,candidate[2] if candidate else 0.),('NO_CONTEXT',candidate[0] if candidate else 1.,False,candidate[2] if candidate else 0.),('NO_DIRECTION',candidate[0] if candidate else 1.,True,0.)]:
                    matched[name]=model if candidate is None else self.fit(train,inherited,ratio,candidate[1],weight,label+'/'+name,context)
                receipt={'model':model,'matched':matched,'inner_ranking':rank,'held_groups':groups,'held_sessions':test,'inherited_model':inherited}
                write(O/(f'{family}_OUTER_{k}.json' if k!='deployment' else f'{family}_DEPLOYMENT_SELECTION.json'),receipt)
                if k=='deployment':write(O/f'{family}_DEPLOYMENT_MODEL.json',model)
                for sid in test:
                    assert self.cases[sid]['group'] not in model['training_groups'];oof.append({'session':sid,'family':family,'group':self.cases[sid]['group'],'outer_fold':k,'model_identity':model['identity'],'AP_C':self.predict(sid,model).tolist()});ablations.append({'session':sid,'family':family,'outer_fold':k,**{n:self.predict(sid,m).tolist() for n,m in matched.items()}})
                print(json.dumps({'family':family,'outer':k,'candidate':candidate,'fits':self.count}),flush=True)
        assert len(oof)==len(ablations)==106
        write(O/'OOF_PREDICTIONS.json',{'status':'NESTED_GROUP_OOF_MODES_REPAIR','cases':oof,'fresh_confirmation':False});write(O/'ABLATION_PREDICTIONS.json',{'cases':ablations,'evaluation_reselection':False});write(O/'FIT_COMPLETE.json',{'fits':self.count,'previous_candidate_models_reused':self.previous_candidate_models_reused,'fit_limit':48,'failures':0,'OOF_sessions':106,'policy_environments':0,'new_measurements':0,'fresh_confirmation':False})
def main():
    reg=read(O/'REGISTRATION.json')
    for p in [reg['inputs'],*reg['sources']]:assert sha(R/p['path'])==p['sha256']
    Study(read(O/'INPUTS.json')).run()
    for p in [reg['inputs'],*reg['sources']]:assert sha(R/p['path'])==p['sha256']
if __name__=='__main__':main()
