"""Finite nested GROUP validation. Every trained identity is recorded exactly once."""
import time,math
from collections import defaultdict
import numpy as np
from scipy.optimize import lsq_linear
from common import *
from energy_model import design,constant,predict_mean,SCHEMA,SETTINGS
class Study:
    def __init__(self,data):self.data=data;self.cases={c['session']:c for c in data['cases']};self.memo={};self.cache={};self.count=0;self.selections=[]
    def log(self,r):
        with (O/'FIT_LEDGER.jsonl').open('a',encoding='utf-8',newline='\n') as f:f.write(json.dumps(r,allow_nan=False,separators=(',',':'))+'\n');f.flush();os.fsync(f.fileno())
    def matrix(self,sid,tau):
        key=(sid,tau)
        if key not in self.cache:
            c=self.cases[sid];windows=[(w['lo'],w['hi']) for w in c['train_windows']]+[tuple(c['primary'])]
            self.cache[key]=design(c,windows,tau)
        return self.cache[key]
    def fit(self,ids,setting,identity):
        key=(tuple(sorted(ids)),setting['tau_s'],setting['offset_enabled'])
        if key in self.memo:self.log({'event':'REUSE','id':identity,'source_id':self.memo[key]['identity']});return self.memo[key]
        resources();self.count+=1;assert self.count<=300;start=time.time();self.log({'event':'START','id':identity,'index':self.count,'training_sessions':ids})
        try:
            xx=[];yy=[];cols=[0,1,2,3,4] if setting['offset_enabled'] else [1,2,3,4]
            for sid in ids:
                c=self.cases[sid];x=self.matrix(sid,setting['tau_s'])[:,cols];y=np.array([w['observed_relative_power'] for w in c['train_windows']]+[c['observed_primary_source_energy']/(c['primary'][1]-35)/c['pre_power']])-1
                weights=np.r_[np.full(len(y)-1,.75/(len(y)-1)),.25]/len(ids);scale=np.sqrt(weights);xx.append(x*scale[:,None]);yy.append(y*scale)
            x=np.vstack(xx+[np.eye(len(cols))*math.sqrt(.001)]);y=np.concatenate(yy+[np.zeros(len(cols))]);low=np.array([-.3 if col==0 else 0. for col in cols]);high=np.array([.3 if col==0 else 4. for col in cols])
            ans=lsq_linear(x,y,bounds=(low,high),tol=1e-12,max_iter=500,lsq_solver='exact');assert ans.success,ans.message
            beta=np.zeros(5);beta[cols]=ans.x;gradient=x.T@(x@ans.x-y);pg=np.where(((ans.x<=low+1e-7)&(gradient>0))|((ans.x>=high-1e-7)&(gradient<0)),0,gradient);assert np.max(abs(pg))<1e-6,(ans.message,pg.tolist())
            m={'schema':SCHEMA,**setting,'coefficients':beta.tolist(),'constant_only':False,'identity':identity,'training_sessions':ids,'training_groups':sorted({self.cases[s]['group'] for s in ids}),'family':self.cases[ids[0]]['family'],'absolute_unit_verified':False,'source_contract':'W_PROXY' if self.cases[ids[0]]['family']=='old' else 'NORMALIZED_RAW_IV'}
            self.memo[key]=m;self.log({'event':'COMPLETE','id':identity,'index':self.count,'elapsed_s':time.time()-start,'model':m,'solver':{'message':str(ans.message),'rank':int(np.linalg.matrix_rank(x)),'projected_gradient_max':float(np.max(abs(pg)))}});return m
        except BaseException as e:self.log({'event':'FAIL','id':identity,'index':self.count,'error':repr(e),'automatic_retry':False});raise
    def metric(self,ids,m):
        rows=[]
        for sid in ids:
            c=self.cases[sid];truth=np.array([w['observed_relative_power'] for w in c['train_windows']]);pred=np.ones(len(truth)+1) if m.get('constant_only') else 1+self.matrix(sid,m['tau_s'])@np.array(m['coefficients'])
            actual=c['observed_primary_source_energy']/(c['primary'][1]-35)/c['pre_power'];rows.append({'session':sid,'group':c['group'],'total_APE':float(abs(pred[-1]-actual)/actual),'window_APE':float(np.mean(abs(pred[:-1]-truth)/truth))})
        return rows
    def score(self,rows):
        groups=sorted({r['group'] for r in rows});total=float(np.mean([np.mean([r['total_APE'] for r in rows if r['group']==g]) for g in groups]));window=float(np.mean([np.mean([r['window_APE'] for r in rows if r['group']==g]) for g in groups]));return {'total_group_MAPE':total,'window_group_MAPE':window,'score':total+.25*window}
    def select(self,ids,label):
        cs=[self.cases[s] for s in ids];bins=split(cs,3);allrows=[[] for _ in range(9)];receipts=[]
        for k,groups in enumerate(bins):
            train=[s for s in ids if self.cases[s]['group'] not in groups];test=[s for s in ids if self.cases[s]['group'] in groups];assert train and test and not ({self.cases[s]['group'] for s in train}&set(groups))
            receipts.append({'fold':k,'train_sessions':train,'test_sessions':test,'test_groups':groups})
            allrows[0].extend(self.metric(test,constant()))
            for j,setting in enumerate(SETTINGS):allrows[j+1].extend(self.metric(test,self.fit(train,setting,f'{label}/INNER{k}/C{j}')))
        scores=[self.score(rows) for rows in allrows];winner=min(range(9),key=lambda k:(scores[k]['score'],k));self.selections.append({'id':label,'training_sessions':ids,'inner':receipts,'candidates':[{'candidate_index':i-1,'setting':SETTINGS[i-1] if i else 'constant_only',**s} for i,s in enumerate(scores)],'winner_index':winner-1})
        if winner==0:
            m=constant();m.update(identity=label+'/CONSTANT',family=self.cases[ids[0]]['family'],selection_training_sessions=ids);return m
        return self.fit(ids,SETTINGS[winner-1],label+'/SELECTED')
    def prediction(self,sid,m,fold):
        c=self.cases[sid];assert c['group'] not in m['training_groups'];windows=[(w['lo'],w['hi']) for w in c['eval_windows']]
        em=predict_mean(c,windows,m);tw=[(w['lo'],w['hi']) for w in c['train_windows']];tp=predict_mean(c,tw,m)
        return {'session':sid,'family':c['family'],'group':c['group'],'outer_fold':fold,'model':m,'eval_relative_mean_power':em.tolist(),'ten_second_relative_mean_power':tp.tolist()}
def main():
    data=read(O/'INPUTS.json');reg=read(O/'REGISTRATION.json');check_sources(reg);s=Study(data);pred=[]
    for family in ['old','m8']:
        ids=[c['session'] for c in data['cases'] if c['family']==family]
        for k,groups in enumerate(data['outer_groups'][family]):
            train=[sid for sid in ids if s.cases[sid]['group'] not in groups];test=[sid for sid in ids if s.cases[sid]['group'] in groups]
            m=s.select(train,f'{family}/OUTER{k}');write(O/f'{family}_OUTER_{k}.json',{'model':m,'held_groups':groups,'held_sessions':test})
            pred.extend(s.prediction(sid,m,k) for sid in test)
            print(json.dumps({'state':'OUTER_COMPLETE','family':family,'fold':k,'fit_count':s.count,'held_sessions':len(test),'selected_tau':m['tau_s'],'offset':m['offset_enabled'],'constant':m['constant_only']}),flush=True)
        m=s.select(ids,f'{family}/DEPLOYMENT');write(O/f'{family}_DEPLOYMENT_MODEL.json',m)
    write(O/'INNER_SELECTIONS.json',s.selections);write(O/'OOF_PREDICTIONS.json',pred);write(O/'FIT_COMPLETE.json',{'fits':s.count,'fit_cap':300,'fit_failures':0,'sessions':len(pred),'policy_environments':0,'new_measurements':0,'fresh_confirmation':False});check_sources(reg)
    print(json.dumps({'state':'FIT_COMPLETE','fits':s.count,'sessions':len(pred)}),flush=True)
if __name__=='__main__':main()
