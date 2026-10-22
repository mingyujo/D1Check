import time,math,warnings
import numpy as np
from scipy.optimize import linprog,lsq_linear,OptimizeWarning
from scipy.sparse import csr_matrix,eye,bmat
from common import *
from energy_model import SETTINGS,SCHEMA,prior,design,bounds,predict_source_mean,constant
def solve_L1(x,y,w,low,high,ridge=.0001):
    n,p=x.shape;xx=csr_matrix(x);ii=eye(n,format='csr');ip=eye(p,format='csr')
    matrix=bmat([[xx,-ii,None],[-xx,-ii,None],[ip,None,-ip],[-ip,None,-ip]],format='csr');rhs=np.r_[y,-y,np.zeros(2*p)];cost=np.r_[np.zeros(p),w,np.full(p,ridge)]
    with warnings.catch_warnings():
        warnings.filterwarnings('ignore',message='Unrecognized options detected',category=OptimizeWarning)
        ans=linprog(cost,A_ub=matrix,b_ub=rhs,bounds=[*zip(low,high),*([(0,None)]*(n+p))],method='highs',options={'threads':1,'parallel':False,'primal_feasibility_tolerance':1e-8,'dual_feasibility_tolerance':1e-8})
    assert ans.success,(ans.status,ans.message)
    beta=ans.x[:p];value=float(w@abs(x@beta-y)+ridge*np.sum(abs(beta)));dual=ans.ineqlin.marginals;lo=ans.lower.marginals[:p];hi=ans.upper.marginals[:p];bound=float(rhs@dual+low@lo+high@hi)
    assert abs(value-ans.fun)<1e-7 and abs(value-bound)<1e-7
    return beta,{'objective':value,'dual_objective':bound,'dual_inequality':dual.tolist(),'dual_lower_coefficients':lo.tolist(),'dual_upper_coefficients':hi.tolist(),'rows':n,'columns':p,'solver_message':ans.message,'iterations':int(ans.nit),'HiGHS_threads':1}
class Study:
    def __init__(self,data):
        self.data=data;self.cs={c['session']:c for c in data['cases']};self.memo={};self.count=0;self.selections=[];self.priors={};self.cache={}
        for line in (PREV/'FIT_LEDGER.jsonl').read_text().splitlines():
            r=json.loads(line)
            if r['event']=='COMPLETE':
                m=r['model'];self.priors[(tuple(sorted(m['training_sessions'])),m['tau_s'],m['offset_enabled'])]=m
    def log(self,row):
        with (O/'FIT_LEDGER.jsonl').open('a',encoding='utf-8',newline='\n') as f:f.write(json.dumps(row,allow_nan=False,separators=(',',':'))+'\n');f.flush();os.fsync(f.fileno())
    def train_arrays(self,ids,setting,ref):
        xx=[];yy=[];ww=[]
        for sid in ids:
            c=self.cs[sid];windows=[(w['lo'],w['hi']) for w in c['train_windows']]+[tuple(c['primary'])];dt=np.array([b-a for a,b in windows]);x=design(c,windows,setting,ref)*dt[:,None]/100
            truth=np.array([w['observed_source_energy'] for w in c['train_windows']]+[c['observed_primary_source_energy']]);y=(truth-c['pre_mean']*dt)/(ref*100);weights=np.r_[np.full(len(dt)-1,1-setting['total_weight']),setting['total_weight']]/len(ids);xx.append(x);yy.append(y);ww.append(weights)
        return np.vstack(xx),np.concatenate(yy),np.concatenate(ww)
    def fit_new(self,ids,setting,label):
        key=('V2',tuple(sorted(ids)),setting['background'],setting['tau_s'],setting['total_weight'])
        if key in self.memo:self.log({'event':'REUSE_NEW','id':label,'source_id':self.memo[key]['identity']});return self.memo[key]
        resources();self.count+=1;assert self.count<=600;start=time.time();self.log({'event':'START','index':self.count,'id':label,'kind':'V2','training_sessions':ids})
        try:
            ref=float(np.median([self.cs[s]['pre_mean'] for s in ids]));x,y,w=self.train_arrays(ids,setting,ref);lo,hi=bounds(setting);beta,cert=solve_L1(x,y,w,lo,hi)
            m={'kind':'V2','schema':SCHEMA,**setting,'reference_power':ref,'coefficients':beta.tolist(),'training_sessions':ids,'training_groups':sorted({self.cs[s]['group'] for s in ids}),'identity':label,'family':self.cs[ids[0]]['family'],'absolute_J_verified':False}
            with (O/'FIT_CERTIFICATES.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps({'id':label,**cert},allow_nan=False,separators=(',',':'))+'\n')
            self.memo[key]=m;self.log({'event':'COMPLETE','index':self.count,'id':label,'elapsed_s':time.time()-start,'model':m,'L1_primal_dual_gap':abs(cert['objective']-cert['dual_objective'])});return m
        except BaseException as e:self.log({'event':'FAIL','id':label,'error':repr(e),'automatic_retry':False});raise
    def old_model(self,ids,k,label):
        setting=prior.SETTINGS[k];key=(tuple(sorted(ids)),setting['tau_s'],setting['offset_enabled'])
        if key in self.priors:
            p=self.priors[key];self.log({'event':'REUSE_PREVIOUS','id':label,'source_id':p['identity'],'training_sessions':ids})
        else:
            resources();self.count+=1;assert self.count<=600;self.log({'event':'START','id':label,'index':self.count,'kind':'V1_NEW_COMBINATION','training_sessions':ids})
            try:
                xx=[];yy=[];cols=[0,1,2,3,4] if setting['offset_enabled'] else [1,2,3,4]
                for sid in ids:
                    c=self.cs[sid];windows=[(w['lo'],w['hi']) for w in c['train_windows']]+[tuple(c['primary'])];x=prior.design(c,windows,setting['tau_s'])[:,cols];y=np.array([w['observed_relative_power'] for w in c['train_windows']]+[c['observed_primary_source_energy']/(c['primary'][1]-35)/c['pre_power']])-1;weights=np.sqrt(np.r_[np.full(len(y)-1,.75/(len(y)-1)),.25]/len(ids));xx.append(x*weights[:,None]);yy.append(y*weights)
                x=np.vstack(xx+[np.eye(len(cols))*math.sqrt(.001)]);y=np.concatenate(yy+[np.zeros(len(cols))]);lo=[-.3 if col==0 else 0 for col in cols];hi=[.3 if col==0 else 4 for col in cols];ans=lsq_linear(x,y,bounds=(lo,hi),tol=1e-12,max_iter=500,lsq_solver='exact');assert ans.success;beta=np.zeros(5);beta[cols]=ans.x
                p={'schema':prior.SCHEMA,**setting,'coefficients':beta.tolist(),'constant_only':False,'identity':label,'training_sessions':ids,'training_groups':sorted({self.cs[s]['group'] for s in ids}),'family':self.cs[ids[0]]['family']};self.priors[key]=p;self.log({'event':'COMPLETE','id':label,'index':self.count,'model':{'kind':'V1','prior_model':p,'training_sessions':ids,'training_groups':p['training_groups'],'identity':label,'family':p['family']}})
            except BaseException as e:self.log({'event':'FAIL','id':label,'error':repr(e),'automatic_retry':False});raise
        return {'kind':'V1','prior_model':p,'training_sessions':p['training_sessions'],'training_groups':p['training_groups'],'identity':label,'family':p['family']}
    def metric(self,ids,m):
        rows=[]
        for sid in ids:
            c=self.cs[sid];windows=[(w['lo'],w['hi']) for w in c['train_windows']]+[tuple(c['primary'])];dt=np.array([b-a for a,b in windows]);estimated=predict_source_mean(c,windows,m)*dt;actual=np.array([w['observed_source_energy'] for w in c['train_windows']]+[c['observed_primary_source_energy']]);scale=1 if c['family']=='old' else c['pre_power'];err=abs(estimated-actual)
            rows.append({'session':sid,'group':c['group'],'MAE_energy':float(err[-1]/scale),'window_sum_AE_energy':float(np.sum(err[:-1])/scale),'APE_pct':float(100*err[-1]/actual[-1]),'window_MAPE_pct':float(100*np.mean(err[:-1]/actual[:-1]))})
        return rows
    def score(self,rows):
        groups=sorted({r['group'] for r in rows})
        avg=lambda key:float(np.mean([np.mean([r[key] for r in rows if r['group']==g]) for g in groups]))
        mae=avg('MAE_energy');win=avg('window_sum_AE_energy');mape=avg('APE_pct');wmape=avg('window_MAPE_pct')
        return {'group_MAE':mae,'group_window_sum_AE':win,'score':mae+.1*win,'group_MAPE_pct':mape,'group_window_MAPE_pct':wmape,'previous_selection_score':mape+.25*wmape,'P90_APE_pct':float(np.quantile([r['APE_pct'] for r in rows],.9))}
    def select(self,ids,label):
        bins=split([self.cs[s] for s in ids],3);allrows=[[] for _ in range(26)];receipts=[]
        for k,groups in enumerate(bins):
            tr=[s for s in ids if self.cs[s]['group'] not in groups];te=[s for s in ids if self.cs[s]['group'] in groups];assert tr and te;receipts.append({'fold':k,'training_sessions':tr,'held_sessions':te,'held_groups':groups})
            for j,kind in enumerate(['PRE_MEDIAN','PRE_MEAN']):allrows[j].extend(self.metric(te,constant(kind)))
            for j in range(8):allrows[j+2].extend(self.metric(te,self.old_model(tr,j,f'{label}/INNER{k}/V1C{j}')))
            for j,setting in enumerate(SETTINGS):allrows[j+10].extend(self.metric(te,self.fit_new(tr,setting,f'{label}/INNER{k}/V2C{j}')))
        scores=[self.score(rows) for rows in allrows];old_indices=[0,*range(2,10)];reference=min(old_indices,key=lambda j:(scores[j]['previous_selection_score'],old_indices.index(j)));ref=scores[reference]
        eligible=[j for j,s in enumerate(scores) if s['group_MAPE_pct']<=ref['group_MAPE_pct']+1e-9 and s['P90_APE_pct']<=ref['P90_APE_pct']+2+1e-9];assert reference in eligible;winner=min(eligible,key=lambda j:(scores[j]['score'],j))
        record={'id':label,'training_sessions':ids,'inner':receipts,'reference_index':reference,'winner_index':winner,'candidates':[{'index':j,'kind':'PRE_MEDIAN' if j==0 else 'PRE_MEAN' if j==1 else 'V1' if j<10 else 'V2','setting':None if j<2 else prior.SETTINGS[j-2] if j<10 else SETTINGS[j-10],'eligible':j in eligible,**s} for j,s in enumerate(scores)]};self.selections.append(record)
        if winner<2:
            m=constant('PRE_MEDIAN' if winner==0 else 'PRE_MEAN');m.update(identity=label+'/CONSTANT',family=self.cs[ids[0]]['family'],selection_training_sessions=ids);return m
        if winner<10:return self.old_model(ids,winner-2,label+'/SELECTED_V1')
        return self.fit_new(ids,SETTINGS[winner-10],label+'/SELECTED_V2')
def main():
    data=read(O/'INPUTS.json');reg=read(O/'REGISTRATION.json');check_sources(reg);s=Study(data);pred=[]
    for family in ['old','m8']:
        ids=[c['session'] for c in data['cases'] if c['family']==family]
        for k,groups in enumerate(data['outer_groups'][family]):
            tr=[i for i in ids if s.cs[i]['group'] not in groups];te=[i for i in ids if s.cs[i]['group'] in groups];m=s.select(tr,f'{family}/OUTER{k}');write(O/f'{family}_OUTER_{k}.json',{'model':m,'held_groups':groups,'held_sessions':te})
            for sid in te:
                c=s.cs[sid];assert c['group'] not in m['training_groups'];ev=[(w['lo'],w['hi']) for w in c['eval_windows']];tw=[(w['lo'],w['hi']) for w in c['train_windows']];pred.append({'session':sid,'family':family,'group':c['group'],'outer_fold':k,'model':m,'eval_relative_mean_power':(predict_source_mean(c,ev,m)/c['pre_power']).tolist(),'ten_second_relative_mean_power':(predict_source_mean(c,tw,m)/c['pre_power']).tolist()})
            print(json.dumps({'state':'OUTER_COMPLETE','family':family,'fold':k,'fits':s.count,'kind':m['kind'],'setting':{n:m.get(n) for n in ['background','tau_s','total_weight']}}),flush=True)
        write(O/f'{family}_DEPLOYMENT_MODEL.json',s.select(ids,f'{family}/DEPLOYMENT'))
    write(O/'INNER_SELECTIONS.json',s.selections);write(O/'OOF_PREDICTIONS.json',pred);write(O/'FIT_COMPLETE.json',{'fits':s.count,'fit_limit':600,'fit_failures':0,'cases':len(pred),'policy_environments':0,'new_measurements':0,'fresh_confirmation':False});check_sources(reg)
    print(json.dumps({'state':'FIT_COMPLETE','fits':s.count,'cases':len(pred)}),flush=True)
if __name__=='__main__':main()
