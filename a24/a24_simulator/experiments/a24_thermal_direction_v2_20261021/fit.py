"""Finite train-only direction-aware calibration; never alters evaluation labels."""
import json,time
from collections import defaultdict,Counter
import numpy as np
from scipy.optimize import lsq_linear,minimize
from prepare import H,R,A,O,PREV,FIRST,read,write,sha,pin,split
from thermal_model import segments,convolution,matrix,window_pairs

def cls(x):return 'rise' if x>=.2-1e-10 else 'fall' if x<=-.2+1e-10 else 'stable'
class Study:
    def __init__(self,data):
        self.data=data;self.cfg=data['config'];self.dc=data['direction_config'];self.cases={c['session']:c for c in data['cases']};self.cache={};self.memo={};self.count=0
        for row in [json.loads(line) for line in (FIRST/'FIT_LEDGER.jsonl').read_text().splitlines()]:
            if row['event']=='COMPLETE' and not row['model']['hinge_strength']:
                m=dict(row['model']);m['identity']='DIRECTION01_FIXED_ZERO_HINGE/'+m['identity']
                self.memo[(tuple(m['training_sessions']),(m['tau_fast_s'],m['tau_slow_s']),m['transport_s'],0.)]=m
        self.fixed_baselines_reused=len(self.memo)
        self.candidates=[(lag,w) for lag in self.dc['transport_s'] for w in self.dc['hinge_strength']]
        taus={tuple(t) for rows in data['frozen_tau'].values() for t in rows.values()}|{tuple(t) for t in data['deployment_tau'].values()}
        for c in self.cases.values():
            conv={t:convolution(c,segments(c),t) for t in sorted({t for pair in taus for t in pair}|{t for t in self.dc['transport_s'] if t})}
            ids=np.array([i for i,o in enumerate(c['observations']) if c['fit_window_s'][0]<=o['t']<=c['fit_window_s'][1]],int);obs=[c['observations'][i] for i in ids]
            self.cache[c['session']]={'matrices':{(tf,ts,lag):matrix(c,conv,tf,ts,lag) for tf,ts in taus for lag in self.dc['transport_s']},
                'indices':ids,'pairs':np.array(window_pairs(obs),int).reshape(-1,2),'truth':np.array([o['observed_c'] for o in obs])}
    def log(self,row):
        with (O/'FIT_LEDGER.jsonl').open('a',encoding='utf-8',newline='\n') as f:f.write(json.dumps(row,ensure_ascii=False,allow_nan=False,separators=(',',':'))+'\n')
    def fit(self,ids,tau,lag,weight,label):
        key=(tuple(ids),tuple(tau),lag,weight)
        if key in self.memo:
            self.log({'event':'REUSE','id':label,'source_id':self.memo[key]['identity']});return self.memo[key]
        self.count+=1;assert self.count<=self.dc['fit_limit'];start=time.time();self.log({'event':'START','index':self.count,'id':label,'training_sessions':ids,'tau_s':tau,'transport_s':lag,'hinge_strength':weight})
        try:
            xx=[];yy=[];hinges=defaultdict(list)
            for sid in ids:
                c=self.cases[sid];z=self.cache[sid];x=z['matrices'][(*tau,lag)][z['indices']];y=z['truth']-c['initial_c'];pairs=z['pairs']
                w=(self.cfg['level_weight'] if len(pairs) else 1.)/len(y);xx.append(x*np.sqrt(w));yy.append(y*np.sqrt(w))
                if len(pairs):
                    i,j=pairs[:,0],pairs[:,1];dx=x[j]-x[i];dy=y[j]-y[i];w=np.sqrt(self.cfg['delta_weight']/len(pairs));xx.append(dx*w);yy.append(dy*w)
                    for d in ['rise','fall','stable']:
                        ix=[k for k,v in enumerate(dy) if cls(v)==d]
                        if ix:hinges[d].append(dx[ix])
            ridge=np.sqrt(self.cfg['ridge']);xx.append(np.eye(10)*ridge);yy.append(np.array(self.cfg['prior'])*ridge);x=np.vstack(xx);y=np.concatenate(yy)
            lower=np.array(self.cfg['lower_bounds']);upper=np.array(self.cfg['upper_bounds']);solver_info={}
            if not weight:
                result=lsq_linear(x,y,bounds=(lower,upper),method='bvls',tol=1e-10,max_iter=100);assert result.success,result.message;theta=result.x;solver_info={'message':result.message,'optimality':float(result.optimality)}
            else:
                hh=[];target=[];ww=[];margin=self.dc['hinge_margin_C']
                for d,session_rows in hinges.items():
                    for dx in session_rows:
                        w=1./(3*len(session_rows)*len(dx))
                        if d=='stable':hh.extend([dx,-dx]);target.extend([np.full(len(dx),-(.2-margin))]*2);ww.extend([np.full(len(dx),w)]*2)
                        else:hh.append(dx if d=='rise' else -dx);target.append(np.full(len(dx),.2+margin));ww.append(np.full(len(dx),w))
                hh=np.vstack(hh);target=np.concatenate(target);ww=np.concatenate(ww)*weight*len(ids);gram=x.T@x;rhs=x.T@y
                def objective(theta):
                    r=np.maximum(0,target-hh@theta)
                    return float(.5*theta@gram@theta-rhs@theta+.5*np.sum(ww*r*r)),gram@theta-rhs-hh.T@(ww*r)
                initial=self.memo.get((tuple(ids),tuple(tau),lag,0.))
                theta0=np.array(initial['coefficients'] if initial else self.cfg['prior'])
                options={k:v for k,v in self.dc['optimizer'].items() if k!='method'}
                result=minimize(objective,theta0,jac=True,method=self.dc['optimizer']['method'],bounds=list(zip(lower,upper)),options=options)
                theta=result.x;grad=objective(theta)[1];pg=np.where((theta<=lower+1e-7)&(grad>0)|((theta>=upper-1e-7)&(grad<0)),0,grad)
                assert result.success and np.max(np.abs(pg))<1e-4,(result.message,float(np.max(np.abs(pg))))
                solver_info={'message':str(result.message),'iterations':int(result.nit),'projected_gradient':float(np.max(np.abs(pg)))}
            model={'schema':'A24-direction-aware-two-thermal-states-v2','tau_fast_s':tau[0],'tau_slow_s':tau[1],'transport_s':lag,'hinge_strength':weight,
                'coefficients':theta.tolist(),'coefficient_names':self.cfg['coefficient_names'],'identity':label,'training_sessions':ids,
                'training_groups':sorted({self.cases[s]['group'] for s in ids}),'fresh_confirmation':False,'not_physical_identification':True,
                'hinge_normalization':self.dc['hinge_normalization']}
            self.memo[key]=model;self.log({'event':'COMPLETE','index':self.count,'id':label,'elapsed_s':time.time()-start,'model':model,'solver':solver_info});return model
        except BaseException as error:self.log({'event':'FAIL','index':self.count,'id':label,'error':repr(error),'automatic_retry':False});raise
    def predict(self,sid,model):
        c=self.cases[sid];x=self.cache[sid]['matrices'][(model['tau_fast_s'],model['tau_slow_s'],model['transport_s'])]
        return c['initial_c']+x@np.array(model['coefficients'])
    def score(self,ids,model):
        rows=[]
        for sid in ids:
            z=self.cache[sid];pred=self.predict(sid,model)[z['indices']];y=z['truth'];e=pred-y;conf={d:[] for d in ['rise','fall','stable']};delta=[]
            for i,j in z['pairs']:
                dy=y[j]-y[i];dp=pred[j]-pred[i];d=cls(dy);conf[d].append(cls(dp)==d);delta.append(abs(dp-dy))
            rows.append({'session':sid,'MAE_C':float(np.mean(np.abs(e))),'delta_MAE_C':float(np.mean(delta)) if delta else 0.,
                'direction':{d:{'n':len(v),'correct':int(sum(v))} for d,v in conf.items()}})
        return rows
    def select(self,ids,tau,label):
        folds=split([self.cases[s] for s in ids],3);rank=[]
        for lag,weight in self.candidates:
            rows=[]
            for k,groups in enumerate(folds):
                train=[s for s in ids if self.cases[s]['group'] not in groups];test=[s for s in ids if self.cases[s]['group'] in groups];assert train and test
                model=self.fit(train,tau,lag,weight,f'{label}/L{int(lag)}_W{int(weight)}/INNER{k}');rows.extend(self.score(test,model))
            accuracy={d:100*sum(r['direction'][d]['correct'] for r in rows)/sum(r['direction'][d]['n'] for r in rows) for d in ['rise','fall','stable']}
            rank.append({'transport_s':lag,'hinge_strength':weight,'MAE_C':sum(r['MAE_C'] for r in rows)/len(rows),'delta_MAE_C':sum(r['delta_MAE_C'] for r in rows)/len(rows),
                'direction_accuracy_pct':accuracy,'balanced_direction_accuracy_pct':sum(accuracy.values())/3,'per_session':rows})
        base=next(r for r in rank if not r['transport_s'] and not r['hinge_strength'])
        for r in rank:r['eligible']=bool(r['MAE_C']<=base['MAE_C']+.05+1e-12 and r['delta_MAE_C']<=base['delta_MAE_C']+.05+1e-12 and r['direction_accuracy_pct']['stable']>=base['direction_accuracy_pct']['stable']-5-1e-10)
        chosen=min([r for r in rank if r['eligible']],key=lambda r:(-r['balanced_direction_accuracy_pct'],-min(r['direction_accuracy_pct'].values()),r['MAE_C'],r['delta_MAE_C'],r['transport_s'],r['hinge_strength']))
        return (chosen['transport_s'],chosen['hinge_strength']),rank
    def run(self):
        oof=[];ablations=[]
        for family in ['m8','old']:
            ids=sorted(s for s,c in self.cases.items() if c['family']==family)
            for k,groups in enumerate(self.data['outer_groups'][family]):
                train=[s for s in ids if self.cases[s]['group'] not in groups];test=[s for s in ids if self.cases[s]['group'] in groups];tau=self.data['frozen_tau'][family][str(k)]
                (lag,weight),rank=self.select(train,tau,f'{family}/OUTER{k}');model=self.fit(train,tau,lag,weight,f'{family}/OUTER{k}/SELECTED')
                plain=self.fit(train,tau,lag,0.,f'{family}/OUTER{k}/NO_DIRECTION_LOSS');no_delay=self.fit(train,tau,0.,weight,f'{family}/OUTER{k}/NO_TRANSPORT')
                write(O/f'{family}_OUTER_{k}.json',{'model':model,'matched_no_direction':plain,'matched_no_transport':no_delay,'inner_ranking':rank,'held_groups':groups,'held_sessions':test,'frozen_tau_from_V1':tau})
                for sid in test:
                    assert self.cases[sid]['group'] not in model['training_groups']
                    oof.append({'session':sid,'family':family,'group':self.cases[sid]['group'],'outer_fold':k,'model_identity':model['identity'],'AP_C':self.predict(sid,model).tolist()})
                    ablations.append({'session':sid,'family':family,'outer_fold':k,'NO_DIRECTION_LOSS':self.predict(sid,plain).tolist(),'NO_TRANSPORT':self.predict(sid,no_delay).tolist()})
                print(json.dumps({'family':family,'outer':k,'selected_transport_s':lag,'hinge_strength':weight,'fits':self.count},ensure_ascii=False),flush=True)
            tau=self.data['deployment_tau'][family];(lag,weight),rank=self.select(ids,tau,f'{family}/DEPLOYMENT_SELECTION');model=self.fit(ids,tau,lag,weight,f'{family}/DEPLOYMENT_NOT_OOF')
            plain=self.fit(ids,tau,lag,0.,f'{family}/DEPLOYMENT_NO_DIRECTION');no_delay=self.fit(ids,tau,0.,weight,f'{family}/DEPLOYMENT_NO_TRANSPORT')
            write(O/f'{family}_DEPLOYMENT_MODEL.json',model);write(O/f'{family}_DEPLOYMENT_SELECTION.json',rank)
        assert self.count<=360 and len(oof)==len(ablations)==106
        write(O/'OOF_PREDICTIONS.json',{'status':'NESTED_GROUP_OOF_DIRECTION_REPAIR','cases':oof,'fresh_confirmation':False})
        write(O/'ABLATION_PREDICTIONS.json',{'cases':ablations,'new_fits_after_selection_only':True,'evaluation_reselection':False})
        write(O/'FIT_COMPLETE.json',{'fits':self.count,'fit_limit':360,'failures':0,'fixed_zero_hinge_baselines_reused':self.fixed_baselines_reused,'OOF_sessions':106,'policy_environments':0,'new_measurements':0,'fresh_confirmation':False})
def main():
    reg=read(O/'REGISTRATION.json')
    for p in [reg['inputs'],*reg['sources']]:assert sha(R/p['path'])==p['sha256']
    Study(read(O/'INPUTS.json')).run()
    for p in [reg['inputs'],*reg['sources']]:assert sha(R/p['path'])==p['sha256']
if __name__=='__main__':main()
