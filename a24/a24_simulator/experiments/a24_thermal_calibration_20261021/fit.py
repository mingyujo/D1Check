"""Registered nested group CV and deployment fits, finite 336 fit calls."""
import gzip,hashlib,json,time
from collections import Counter
import numpy as np
import scipy
from scipy.optimize import lsq_linear
from prepare import H,R,A,O,read,write,pin,sha,split
from thermal_model import segments,convolution,matrix,window_pairs

class Study:
    def __init__(self,data):
        self.data=data;self.cfg=data['config'];self.cases={c['session']:c for c in data['cases']};self.cache={};self.count=0
        self.candidates=[(f,s) for f in self.cfg['tau_fast_s'] for s in self.cfg['tau_slow_s']]
        for c in self.cases.values():
            seg=segments(c);conv={tau:convolution(c,seg,tau) for tau in sorted(set(self.cfg['tau_fast_s']+self.cfg['tau_slow_s']))}
            ids=[i for i,o in enumerate(c['observations']) if c['fit_window_s'][0]<=o['t']<=c['fit_window_s'][1]]
            obs=[c['observations'][i] for i in ids];pairs=window_pairs(obs)
            self.cache[c['session']]={'matrices':{(f,s):matrix(c,conv,f,s) for f,s in self.candidates},'indices':np.array(ids,int),
                'pairs':np.array(pairs,int).reshape(-1,2),'truth':np.array([o['observed_c'] for o in obs]),'all_truth':np.array([o['observed_c'] for o in c['observations']])}

    def log(self,row):
        with (O/'FIT_LEDGER.jsonl').open('a',encoding='utf-8',newline='\n') as file:file.write(json.dumps(row,ensure_ascii=False,allow_nan=False,separators=(',',':'))+'\n')

    def fit(self,ids,tau,identity):
        self.count+=1;assert self.count<=self.cfg['fit_limit'];start=time.time()
        self.log({'event':'START','index':self.count,'id':identity,'tau_s':tau,'training_sessions':list(ids)})
        try:
            xx=[];yy=[]
            for sid in ids:
                c=self.cases[sid];cache=self.cache[sid];x=cache['matrices'][tau][cache['indices']];y=cache['truth']-c['initial_c'];pairs=cache['pairs']
                weight=self.cfg['level_weight'] if len(pairs) else 1.;w=mathsqrt(weight/len(y));xx.append(x*w);yy.append(y*w)
                if len(pairs):
                    i=pairs[:,0];j=pairs[:,1];w=mathsqrt(self.cfg['delta_weight']/len(pairs));xx.append((x[j]-x[i])*w);yy.append((y[j]-y[i])*w)
            ridge=mathsqrt(self.cfg['ridge']);xx.append(np.eye(10)*ridge);yy.append(np.array(self.cfg['prior'])*ridge)
            result=lsq_linear(np.vstack(xx),np.concatenate(yy),bounds=(self.cfg['lower_bounds'],self.cfg['upper_bounds']),method='bvls',tol=1e-10,max_iter=100)
            assert result.success,(identity,result.message)
            model={'schema':'A24-contextual-two-thermal-states-v1','tau_fast_s':tau[0],'tau_slow_s':tau[1],
                'coefficient_names':self.cfg['coefficient_names'],'coefficients':result.x.tolist(),'training_sessions':list(ids),'identity':identity,
                'training_groups':sorted({self.cases[sid]['group'] for sid in ids}),'not_physical_identification':True,'fresh_confirmation':False}
            self.log({'event':'COMPLETE','index':self.count,'id':identity,'elapsed_s':time.time()-start,'solver_cost':result.cost,'model':model})
            return model
        except BaseException as error:
            self.log({'event':'FAIL','index':self.count,'id':identity,'error':repr(error),'automatic_retry':False});raise

    def predict(self,sid,model):
        c=self.cases[sid];x=self.cache[sid]['matrices'][(model['tau_fast_s'],model['tau_slow_s'])]
        return c['initial_c']+x@np.array(model['coefficients'])

    def score(self,ids,model):
        rows=[]
        for sid in ids:
            cache=self.cache[sid];pred=self.predict(sid,model)[cache['indices']];e=pred-cache['truth'];pairs=cache['pairs']
            delta=np.mean(np.abs(e[pairs[:,1]]-e[pairs[:,0]])) if len(pairs) else 0.
            mae=float(np.mean(np.abs(e)));rows.append({'session':sid,'MAE_C':mae,'delta_MAE_C':float(delta),'score':mae+self.cfg['selection_delta_weight']*float(delta)})
        return rows

    def select(self,ids,label):
        folds=split([self.cases[sid] for sid in ids],self.cfg['inner_folds']);rank=[]
        for tau in self.candidates:
            scores=[]
            for k,groups in enumerate(folds):
                train=[sid for sid in ids if self.cases[sid]['group'] not in groups];test=[sid for sid in ids if self.cases[sid]['group'] in groups]
                assert train and test and not ({self.cases[s]['group'] for s in train}&{self.cases[s]['group'] for s in test})
                model=self.fit(train,tau,f'{label}/F{int(tau[0])}_S{int(tau[1])}/INNER{k}')
                scores.extend(self.score(test,model))
            assert len(scores)==len(ids)
            rank.append({'tau_fast_s':tau[0],'tau_slow_s':tau[1],'score':sum(r['score'] for r in scores)/len(scores),'per_session':scores})
        choice=min(rank,key=lambda r:(r['score'],r['tau_fast_s'],r['tau_slow_s']))
        return (choice['tau_fast_s'],choice['tau_slow_s']),rank

    def run(self):
        oof=[];receipts=[];deployment={}
        for family in ['m8','old']:
            ids=sorted(sid for sid,c in self.cases.items() if c['family']==family)
            for k,groups in enumerate(self.data['outer_groups'][family]):
                train=[s for s in ids if self.cases[s]['group'] not in groups];test=[s for s in ids if self.cases[s]['group'] in groups]
                tau,ranking=self.select(train,f'{family}/OUTER{k}')
                model=self.fit(train,tau,f'{family}/OUTER{k}/FINAL_TRAIN_ONLY')
                assert not (set(groups)&set(model['training_groups']))
                receipt={'family':family,'outer_fold':k,'held_groups':groups,'held_sessions':test,'model':model,'inner_ranking':ranking}
                receipts.append(receipt);write(O/f'{family}_OUTER_{k}.json',receipt)
                for sid in test:oof.append({'session':sid,'family':family,'group':self.cases[sid]['group'],'outer_fold':k,'model_identity':model['identity'],'AP_C':self.predict(sid,model).tolist()})
                print(json.dumps({'family':family,'outer':k,'fits_complete':self.count,'held_sessions':len(test),'chosen_tau_s':tau},ensure_ascii=False),flush=True)
            tau,ranking=self.select(ids,f'{family}/DEPLOYMENT_SELECTION')
            model=self.fit(ids,tau,f'{family}/DEPLOYMENT_NOT_OOF')
            deployment[family]=model;write(O/f'{family}_DEPLOYMENT_MODEL.json',model);write(O/f'{family}_DEPLOYMENT_SELECTION.json',ranking)
        assert self.count==336 and len(oof)==106 and len({r['session'] for r in oof})==106
        write(O/'OOF_PREDICTIONS.json',{'status':'NESTED_GROUP_OUT_OF_FOLD','cases':oof,'fresh_confirmation':False,'target_leakage_into_same_outer_fit':False})
        write(O/'FIT_COMPLETE.json',{'fits':self.count,'groups':{f:len({c['group'] for c in self.cases.values() if c['family']==f}) for f in ['m8','old']},
            'deployment_models':{f:pin(O/f'{f}_DEPLOYMENT_MODEL.json') for f in deployment},'numpy_version':np.__version__,'scipy_version':scipy.__version__,
            'policy_environments':0,'device_measurements':0,'BC_PPO_updates':0,'fresh_confirmation':False})

def mathsqrt(x):return x**.5
def main():
    reg=read(O/'REGISTRATION.json')
    for p in [reg['inputs'],*reg['sources']]:assert sha(R/p['path'])==p['sha256']
    Study(read(O/'INPUTS.json')).run()
    for p in [reg['inputs'],*reg['sources']]:assert sha(R/p['path'])==p['sha256']
if __name__=='__main__':main()
